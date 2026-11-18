"""Pure Python between the VAT Return document and the core in steuerbote.ustva.

Nothing here imports Frappe. The module finds the Voranmeldungszeitraum a return is for, turns the core's
result into the rows of the return's tables and computes the sums of the form over the amounts as filed,
so that the controller only moves data and every rule is tested without a bench. Amounts are computed by
the core alone.
"""

from collections.abc import Callable, Collection, Iterable, Sequence
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol

from steuerbote.ustva import (
	Kennzahl,
	LedgerLine,
	Mapping,
	Period,
	Rhythm,
	UstvaResult,
	calculate,
	catalogue_for,
)
from steuerbote.ustva.kennzahlen import BALANCE_KENNZAHL, SONDERVORAUSZAHLUNG_KENNZAHL
from steuerbote.ustva.rounding import ZERO, to_cents

MONTHS_PER_QUARTER = 3


class Row(Protocol):
	"""A row of the Kennzahlen table: a dict, or a child document of Frappe, which reads the same way."""

	def get(self, key: str, default: Any = None) -> Any: ...


class NoSuchPeriodError(ValueError):
	"""No month or quarter with this number fits the rhythm the company files in."""


class AmbiguousPeriodError(ValueError):
	"""The number names a month and a quarter of the year, both of which the company files."""


def resolve_period(year: int, number: int, rhythm_of_month: Callable[[int], Rhythm]) -> Period:
	"""The Voranmeldungszeitraum with this number: month 1 to 12 or quarter 1 to 4, by the company's rhythm.

	``rhythm_of_month`` gives the rhythm a month of the year is filed in. The rhythm can change at the start
	of a quarter, so the number is read as a month and as a quarter, and the reading whose first month is
	filed in that rhythm is the period. A month that the rules refuse, such as one without a filing
	obligation, rules out only the reading it belongs to.
	"""
	readings = [(Rhythm.MONTHLY, 12, number), (Rhythm.QUARTERLY, 4, (number - 1) * MONTHS_PER_QUARTER + 1)]
	periods: list[Period] = []
	refusals: list[Exception] = []
	for rhythm, last, first_month in readings:
		if not 1 <= number <= last:
			continue
		try:
			filed_in = Rhythm(rhythm_of_month(first_month))
		except Exception as refusal:
			refusals.append(refusal)
			continue
		if filed_in is rhythm:
			periods.append(Period(year, rhythm, number))
	if len(periods) > 1:
		raise AmbiguousPeriodError(f"{number} is a month and a quarter of {year}")
	if periods:
		return periods[0]
	if refusals:
		raise refusals[0]
	raise NoSuchPeriodError(f"{year} has no Voranmeldungszeitraum {number}")


def sondervorauszahlung_values(period: Period, has_dauerfrist: bool, amount: Decimal) -> dict[str, Decimal]:
	"""Kz 39 for the extra values of the core: the Sondervorauszahlung, in the last period of the year.

	§ 48 Absatz 4 Satz 1 UStDV: „Die festgesetzte Sondervorauszahlung ist bei der Festsetzung der
	Vorauszahlung für den letzten Voranmeldungszeitraum des Besteuerungszeitraums zu berücksichtigen, für den
	die Fristverlängerung gilt.“ The form says the same of Kz 39: „in der Regel nur in der letzten
	Voranmeldung des Besteuerungszeitraums auszufüllen“.
	"""
	if has_dauerfrist and amount and period.next().year != period.year:
		return {SONDERVORAUSZAHLUNG_KENNZAHL: amount}
	return {}


def reduce_mapping(mapping: Mapping, account_numbers: Collection[str]) -> Mapping:
	"""The mapping restricted to the accounts a company has.

	Rules and watched accounts are kept for the accounts that exist. A check keeps its existing base and tax
	accounts and is dropped when either side is left empty, because it would compare against nothing.
	"""
	existing = frozenset(account_numbers)
	checks = []
	for check in mapping.checks:
		bases = tuple(account for account in check.base_accounts if account in existing)
		taxes = tuple(account for account in check.tax_accounts if account in existing)
		if bases and taxes:
			checks.append(replace(check, base_accounts=bases, tax_accounts=taxes))
	return replace(
		mapping,
		rules=tuple(rule for rule in mapping.rules if rule.account_number in existing),
		checks=tuple(checks),
		watched=tuple(account for account in mapping.watched if account in existing),
	)


@dataclass(frozen=True, slots=True)
class Override:
	"""An amount the user files instead of the computed one, with the reason why."""

	amount: Decimal
	reason: str


class RowProblem(Enum):
	UNKNOWN = "unknown"
	DUPLICATE = "duplicate"
	NO_AMOUNT = "no_amount"
	COMPUTED = "computed"
	MISSING_REASON = "missing_reason"


class RowError(ValueError):
	"""A row of the Kennzahlen table that cannot be filed as it is."""

	def __init__(self, problem: RowProblem, kennzahl: str) -> None:
		super().__init__(f"Kennzahl {kennzahl!r}: {problem.value}")
		self.problem = problem
		self.kennzahl = kennzahl


@dataclass(frozen=True, slots=True)
class _Entry:
	kennzahl: Kennzahl
	reported: Decimal
	override: Override | None


def to_amount(value: object) -> Decimal:
	"""The value of a currency field in cents; Frappe hands out floats, strings or nothing."""
	return to_cents(Decimal(str(value or ZERO)))


def _entries(rows: Iterable[Row], catalogue: ReadOnlyMapping[str, Kennzahl]) -> list[_Entry]:
	"""Read the rows, refusing what cannot be filed.

	An override takes effect once it has a reason, so an amount of zero can be filed too. An override
	without a reason is refused rather than ignored, since its author expects it to count.
	"""
	entries: list[_Entry] = []
	seen: set[str] = set()
	for row in rows:
		number = str(row.get("kennzahl") or "").strip()
		kennzahl = catalogue.get(number)
		if kennzahl is None:
			raise RowError(RowProblem.UNKNOWN, number)
		if number in seen:
			raise RowError(RowProblem.DUPLICATE, number)
		seen.add(number)
		reason = str(row.get("override_reason") or "").strip()
		amount = to_amount(row.get("override"))
		if number == BALANCE_KENNZAHL and (reason or amount):
			raise RowError(RowProblem.COMPUTED, number)
		if not kennzahl.holds_amount:
			raise RowError(RowProblem.NO_AMOUNT, number)
		if amount and not reason:
			raise RowError(RowProblem.MISSING_REASON, number)
		override = Override(amount, reason) if reason else None
		entries.append(_Entry(kennzahl, to_amount(row.get("reported")), override))
	return entries


def overrides_of(rows: Iterable[Row], catalogue: ReadOnlyMapping[str, Kennzahl]) -> dict[str, Override]:
	"""The overrides in the rows, by Kennzahl, to carry them over a new calculation."""
	return {entry.kennzahl.number: entry.override for entry in _entries(rows, catalogue) if entry.override}


def kennzahl_rows(
	result: UstvaResult,
	catalogue: ReadOnlyMapping[str, Kennzahl],
	overrides: ReadOnlyMapping[str, Override],
) -> list[dict[str, Any]]:
	"""A row per Kennzahl of the result and per override, in the order of the form."""
	position = {number: index for index, number in enumerate(catalogue)}
	rows = []
	for number in sorted(set(result.values) | set(overrides), key=position.__getitem__):
		kennzahl = catalogue[number]
		value = result.values.get(number)
		override = overrides.get(number)
		rows.append(
			{
				**_description(kennzahl),
				"amount": value.amount if value else ZERO,
				"reported": value.reported if value else ZERO,
				"override": override.amount if override else ZERO,
				"override_reason": override.reason if override else "",
			}
		)
	return rows


@dataclass(frozen=True, slots=True)
class Filing:
	"""The return as filed: per row, in the order given, the Kennzahl described and its final amount, and
	the sums of the form over the final amounts."""

	rows: tuple[dict[str, Any], ...]
	totals: dict[str, Decimal]


def filing(rows: Sequence[Row], year: int) -> Filing:
	"""Final amounts and the form's sums: an override with a reason replaces the reported amount.

	The sums come from the core, which takes the final amounts as extra values on an empty ledger; Kz 83
	follows from them and is never taken from a row.
	"""
	catalogue = catalogue_for(year)
	entries = _entries(rows, catalogue)
	amounts = {
		entry.kennzahl.number: entry.override.amount if entry.override else entry.reported
		for entry in entries
		if entry.kennzahl.number != BALANCE_KENNZAHL
	}
	form = calculate((), Mapping(chart="", rules=(), year=year), extra_values=amounts)
	return Filing(
		rows=tuple(
			{
				**_description(entry.kennzahl),
				"final": form.kz83
				if entry.kennzahl.number == BALANCE_KENNZAHL
				else form.reported(entry.kennzahl.number),
			}
			for entry in entries
		),
		totals={
			"output_tax": form.output_tax,
			"input_tax": form.input_tax,
			"other_tax": form.other_tax,
			"sondervorauszahlung": form.sondervorauszahlung,
			"kz83": form.kz83,
		},
	)


def _description(kennzahl: Kennzahl) -> dict[str, Any]:
	return {
		"kennzahl": kennzahl.number,
		"line": kennzahl.line,
		"label": kennzahl.label,
		"kind": kennzahl.kind.value,
	}


def check_rows(result: UstvaResult) -> list[dict[str, Any]]:
	return [
		{
			"label": check.label,
			"computed_tax": check.computed_tax,
			"booked_tax": check.booked_tax,
			"difference": check.difference,
			"deviations": len(check.deviations),
			"passed": int(check.passed),
		}
		for check in result.checks
	]


def split_voucher(voucher: str | None) -> tuple[str, str]:
	"""Voucher type and name from the voucher key ``"<voucher type>:<voucher name>"`` of steuerbote.ledger."""
	if voucher is None:
		return "", ""
	voucher_type, _, voucher_no = voucher.partition(":")
	return voucher_type, voucher_no


def deviation_rows(result: UstvaResult) -> list[dict[str, Any]]:
	rows = []
	for check in result.checks:
		for deviation in check.deviations:
			voucher_type, voucher_no = split_voucher(deviation.voucher)
			rows.append(
				{
					"check_label": check.label,
					"voucher_type": voucher_type,
					"voucher_no": voucher_no,
					"computed_tax": deviation.computed_tax,
					"booked_tax": deviation.booked_tax,
					"difference": deviation.difference,
				}
			)
	return rows


def unmapped_rows(
	result: UstvaResult, lines: Iterable[LedgerLine], account_names: ReadOnlyMapping[str, str]
) -> list[dict[str, Any]]:
	"""The watched accounts with a balance, with the account's name and its debits and credits in the period."""
	debits = dict.fromkeys(result.unmapped, ZERO)
	credits = dict.fromkeys(result.unmapped, ZERO)
	for ledger_line in lines:
		if ledger_line.account_number in debits:
			debits[ledger_line.account_number] += ledger_line.debit
			credits[ledger_line.account_number] += ledger_line.credit
	return [
		{
			"account_number": number,
			"account": account_names.get(number, ""),
			"debit": debits[number],
			"credit": credits[number],
		}
		for number in result.unmapped
	]
