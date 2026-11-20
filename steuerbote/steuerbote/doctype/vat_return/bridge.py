"""Pure Python between the VAT Return document and the core in steuerbote.ustva.

Nothing here imports Frappe. The module turns the core's result into the rows of the return's tables,
computes the sums of the form over the amounts as filed and hands the return as filed to the ELSTER XML in
steuerbote.elster, so that the controller only moves data and every rule is tested without a bench. Amounts
are computed by the core alone, and so are the Vorperiodenvergleich and the hints of
steuerbote.ustva.plausibility, whose results become the rows of the tables "comparison" and "hints".
"""

from collections.abc import Iterable, Sequence
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol

from steuerbote.elster import ustva_xml
from steuerbote.ustva import (
	Kennzahl,
	LedgerLine,
	Mapping,
	Period,
	UstvaResult,
	calculate,
	catalogue_for,
	plausibility,
)
from steuerbote.ustva.kennzahlen import BALANCE_KENNZAHL, SONDERVORAUSZAHLUNG_KENNZAHL
from steuerbote.ustva.rounding import ZERO, to_cents


class Row(Protocol):
	"""A row of the Kennzahlen table: a dict, or a child document of Frappe, which reads the same way."""

	def get(self, key: str, default: Any = None) -> Any: ...


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


def final_amounts(rows: Sequence[Row], year: int) -> dict[str, Decimal]:
	"""The amount each Kennzahl of the rows is filed with, Kz 83 as filing() computes it."""
	return {row["kennzahl"]: row["final"] for row in filing(rows, year).rows}


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


def comparison_rows(comparison: plausibility.Comparison) -> list[dict[str, Any]]:
	"""The rows of the Vorperiodenvergleich.

	A Currency or Percent field stores no blank, so a value the comparison does not know holds 0: the
	values of a period without catalogue, and the share of a Kennzahl without an earlier amount. The row
	says whether each earlier period is known, so that the form can leave the values of an unknown one
	blank.
	"""
	known = {
		"previous_period_known": int(comparison.previous_period.known),
		"previous_year_known": int(comparison.previous_year.known),
	}
	return [
		{
			"kennzahl": row.kennzahl,
			"label": row.label,
			"current": row.current,
			"previous_period": _or_zero(row.previous_period),
			"previous_year": _or_zero(row.previous_year),
			"difference": _or_zero(row.difference),
			"difference_percent": _or_zero(row.difference_percent),
			"flagged": int(row.flagged),
			**known,
		}
		for row in comparison.rows
	]


def _or_zero(value: Decimal | None) -> Decimal:
	return ZERO if value is None else value


def hint_rows(hints: Iterable[plausibility.Hint]) -> list[dict[str, Any]]:
	return [
		{
			"severity": hint.severity.value,
			"code": hint.code.value,
			"text": hint.text,
			"voucher_type": hint.voucher_type,
			"voucher_no": hint.voucher_no,
			"party": hint.party,
		}
		for hint in hints
	]


# The field of the VAT Return Settings that holds each part of the Datenlieferant (ustva_xml.DATENLIEFERANT).
DATENLIEFERANT_FIELDS: ReadOnlyMapping[str, str] = MappingProxyType(
	{
		"name": "filer_name",
		"street": "street",
		"postal_code": "postal_code",
		"city": "city",
		"phone": "phone",
		"email": "email",
	}
)


def filer(settings: Row) -> ustva_xml.Filer:
	"""The company as ELSTER names it, from its VAT Return Settings.

	Without a name of its own, the Datenlieferant carries the name of the company.
	"""
	datenlieferant = {attribute: settings.get(field) for attribute, field in DATENLIEFERANT_FIELDS.items()}
	return ustva_xml.Filer(
		steuernummer=settings.get("elster_tax_number") or "",
		**{**datenlieferant, "name": datenlieferant["name"] or settings.get("company")},
		wid_nr=settings.get("wid_nr"),
	)


def voranmeldung(return_: Row, period: Period, reported_before: Iterable[str] = ()) -> ustva_xml.Voranmeldung:
	"""The return as filed: the final amount of each row, Kz 83 as the return keeps it, and its further details.

	``reported_before`` are the Kennzahlen of the returns that a corrected return replaces, see ``reported``.
	"""
	amounts = {
		number: to_amount(row.get("final"))
		for row in return_.get("kennzahlen") or ()
		if (number := _number(row)) != BALANCE_KENNZAHL
	}
	corrected = _checked(return_.get("is_correction"))
	return ustva_xml.Voranmeldung(
		period,
		{**amounts, BALANCE_KENNZAHL: to_amount(return_.get("kz83"))},
		corrected=corrected,
		attachments=_checked(return_.get("attachments")),
		no_sepa_mandate=_checked(return_.get("no_sepa_mandate")),
		offset_requested=_checked(return_.get("offset_requested")),
		supplementary_code=return_.get("supplementary_code") or None,
		begruendung=return_.get("kz500_begruendung") or None,
		regelbesteuerung_from=to_date(return_.get("regelbesteuerung_from")),
		reported_before=frozenset(reported_before) if corrected else frozenset(),
	)


def to_date(value: object) -> date | None:
	"""The value of a Date field: a date from the database, an ISO date from the form, or nothing."""
	if isinstance(value, date):
		return value
	return date.fromisoformat(str(value)) if value else None


def reported(rows: Iterable[Row]) -> frozenset[str]:
	"""The Kennzahlen with an amount in the rows of a filed return, Kz 83 aside, which is always written."""
	return frozenset(
		number for row in rows if (number := _number(row)) != BALANCE_KENNZAHL and to_amount(row.get("final"))
	)


def _number(row: Row) -> str:
	return str(row.get("kennzahl") or "").strip()


def _checked(value: object) -> bool:
	"""The value of a check field; Frappe hands out 0 and 1, or nothing."""
	return bool(int(value or 0))
