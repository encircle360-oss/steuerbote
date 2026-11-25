"""The annual return against the filed Voranmeldungen: period by period and Kennzahl by Kennzahl.

The annual return is computed from the ledger of the year (steuerbote/ustjahr/calculation.py), the Voranmeldungen
were filed from the ledger of their periods as it was then. reconcile() sets them against each other with every
column from a source of its own:

- filed: the Kennzahlen as each latest filed Voranmeldung of a period filed them, after the corrections of the
  company, with the exact amount of the ledger then and the amount of the form (steuerbote/ustjahr/soll.py, Filed);
- ledger now: the run of the Voranmeldung on today's ledger for each period, twelve or four results of the core
  (steuerbote/ustva/calculation.py);
- annual: the lines of the annual return that take the amounts of each Kennzahl (steuerbote/ustjahr/form.py), as
  the ledger, the accounts only the annual return reads, the lines by hand and the corrections give them.

For each Kennzahl of the Voranmeldung the difference of the annual return to the filed Voranmeldungen splits into

- late: postings dated in a filed period after its filing, such as closing entries (§ 17 Absatz 1 Satz 8 UStG puts
  a change of the base into the period it happens in, so a change after the year belongs to the next one);
- corrections: what the company corrected in a Voranmeldung that the books never got;
- unfiled: the periods without a filed Voranmeldung;
- rounding: the rounding of the annual return less that of the Voranmeldungen, both against the exact ledger;
- annual-only: the accounts only the annual return reads, the lines by hand and the corrections of the annual return;
- rest: what none of these explains, the ledger of the year against that of its periods.

The rest is zero when the run over the year and the runs per period read the same ledger, because the lines of each
Kennzahl add up to it (steuerbote/ustjahr/split.py); anything else blocks the return. Kz 820 against the Kz 83 of
the periods splits the same way, with two parts of the Vorauszahlungssoll besides: the Sondervorauszahlung that
Kz 39 did not credit, and a Soll that a corrected return or the Finanzamt set.

Hints: a period whose ledger changed after its filing, since whether that needs a corrected Voranmeldung (§ 153
Absatz 1 AO) is for the company to decide with its Steuerberatung (unverified whether the annual return alone may
correct it); the Vorsteuer, which Steuerbote takes by the posting date of the invoice while the deduction needs the
invoice in hand (§ 15 Absatz 1 Satz 1 Nummer 1 Satz 2 UStG), a documented limit; and, from journal_entries(), the
Journal Entries of the year on tax accounts that lack the flag Exclude from VAT Return, which a clearing of the tax
accounts needs.
"""

from collections.abc import Collection, Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from steuerbote.ustjahr import text
from steuerbote.ustjahr.calculation import AnnualResult, entries
from steuerbote.ustjahr.form import KZ_816, KZ_820, Field, Finding, Severity, catalogue_for
from steuerbote.ustjahr.soll import Filed, Soll
from steuerbote.ustva.calculation import LedgerLine, UstvaResult
from steuerbote.ustva.kennzahlen import (
	BALANCE_KENNZAHL,
	SONDERVORAUSZAHLUNG_KENNZAHL,
	Effect,
	Kennzahl,
	Kind,
)
from steuerbote.ustva.kennzahlen import catalogue_for as ustva_catalogue_for
from steuerbote.ustva.mapping import Mapping
from steuerbote.ustva.period import Period
from steuerbote.ustva.rounding import HUNDRED, ZERO

INVOICE_LINE = "E3006201"

NO_RUN = "{0} has a filed Voranmeldung but no run on today's ledger."
OTHER_YEAR = "{0} is no Voranmeldungszeitraum of {1}."
LATE = (
	"The ledger of {0} changed Kz 83 by {1} euros since its Voranmeldung was filed. Whether a corrected Voranmeldung "
	"is due (§ 153 Absatz 1 AO) the company decides with its Steuerberatung; the annual return takes the ledger as "
	"it is."
)
REST = (
	"The lines of Kz {0} hold {1} euros that the Voranmeldungen on today's ledger do not explain: the ledger of the "
	"year and that of its periods differ."
)
REST_OF_KZ_820 = (
	"Kz 820 holds {0} euros that the Voranmeldungen on today's ledger do not explain: the ledger of the year and that "
	"of its periods differ."
)
INVOICE = (
	"Steuerbote takes the Vorsteuer of {0} by the posting date of its invoice, while the deduction needs the invoice "
	"in hand (§ 15 Absatz 1 Satz 1 Nummer 1 Satz 2 UStG): an invoice that arrived after {0} gives Vorsteuer of the "
	"year it arrived."
)
JOURNAL_ENTRY = (
	"{0} Journal Entries of {1} move tax accounts without the flag Exclude from VAT Return, such as {2}: a clearing of "
	"the tax accounts needs the flag, a correction does not. The report UStVA Kennzahlen shows the vouchers of each Kennzahl."
)
NAMED_JOURNAL_ENTRIES = 5
MESSAGES = (NO_RUN, OTHER_YEAR, LATE, REST, REST_OF_KZ_820, INVOICE, JOURNAL_ENTRY)


class ReconciliationError(ValueError):
	"""The runs of the periods do not fit the filed Voranmeldungen; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


class Cause(Enum):
	"""Why Kz 83 of a period differs from today's ledger."""

	NONE = "none"
	LATE_POSTINGS = "late postings"
	CORRECTIONS = "corrections"
	LATE_POSTINGS_AND_CORRECTIONS = "late postings and corrections"
	NOT_FILED = "not filed"


@dataclass(frozen=True, slots=True)
class PeriodLine:
	"""A Voranmeldungszeitraum: Kz 83 and Kz 39 as filed, and Kz 83 of today's ledger with the same Kz 39.

	``late`` is what the ledger changed since the filing, ``corrections`` what the company corrected in the
	Voranmeldung; ``vat_return`` is None for a period without a filed Voranmeldung.
	"""

	period: Period
	vat_return: str | None
	kz83: Decimal
	kz39: Decimal
	kz83_now: Decimal
	late: Decimal
	corrections: Decimal

	@property
	def difference(self) -> Decimal:
		return self.kz83_now - self.kz83

	@property
	def cause(self) -> Cause:
		if self.vat_return is None:
			return Cause.NOT_FILED
		if self.late and self.corrections:
			return Cause.LATE_POSTINGS_AND_CORRECTIONS
		if self.late:
			return Cause.LATE_POSTINGS
		if self.corrections:
			return Cause.CORRECTIONS
		return Cause.NONE


@dataclass(frozen=True, slots=True)
class KennzahlLine:
	"""A Kennzahl of the Voranmeldung over the year: as filed, by the ledger then and now, and in the annual return.

	``annual`` is the sum of its lines as the annual return files them. Their difference to ``filed`` is the sum of
	``late``, ``corrections``, ``unfiled``, ``rounding``, ``annual_only`` and ``rest``, each exact.
	"""

	kennzahl: str
	filed: Decimal
	filed_ledger: Decimal
	ledger_now: Decimal
	annual: Decimal
	late: Decimal
	corrections: Decimal
	unfiled: Decimal
	rounding: Decimal
	annual_only: Decimal
	rest: Decimal

	@property
	def difference(self) -> Decimal:
		return self.annual - self.filed


@dataclass(frozen=True, slots=True)
class BalanceLine:
	"""Kz 820 against the Kz 83 of the periods: Kz 820 is the sum of the other amounts, each exact.

	``sondervorauszahlung`` is the Sondervorauszahlung that Kz 39 credited less that of the settings, ``soll`` the
	Vorauszahlungssoll from the Voranmeldungen less the one filed, which a corrected return or the Finanzamt set.
	"""

	kz820: Decimal
	late: Decimal
	corrections: Decimal
	unfiled: Decimal
	sondervorauszahlung: Decimal
	soll: Decimal
	rounding: Decimal
	annual_only: Decimal
	rest: Decimal


@dataclass(frozen=True, slots=True)
class Reconciliation:
	"""The periods in the order of the year, the Kennzahlen with an amount in the order of the Voranmeldung, Kz 820,
	and the findings."""

	periods: tuple[PeriodLine, ...]
	kennzahlen: tuple[KennzahlLine, ...]
	balance: BalanceLine
	findings: tuple[Finding, ...]

	@property
	def ready(self) -> bool:
		"""Nothing is left that the reconciliation does not explain."""
		return not self.balance.rest and not any(line.rest for line in self.kennzahlen)

	def kennzahl(self, number: str) -> KennzahlLine:
		for line in self.kennzahlen:
			if line.kennzahl == number:
				return line
		raise KeyError(number)


def reconcile(
	result: AnnualResult,
	soll: Soll,
	now: ReadOnlyMapping[Period, UstvaResult],
	reported: ReadOnlyMapping[str, Decimal] | None = None,
) -> Reconciliation:
	"""The annual return against the Voranmeldungen that ``soll`` sums up.

	``now`` holds the run of the Voranmeldung on today's ledger for every period of the year with a filed
	Voranmeldung, and may hold others; ``reported`` holds the amounts of the annual return after the corrections of
	the company, those of the form by default.
	"""
	for period in now:
		if period.year != result.year:
			raise ReconciliationError(OTHER_YEAR, period.label, result.year)
	filed = {entry.period: entry for entry in soll.filed}
	for period in filed:
		if period not in now:
			raise ReconciliationError(NO_RUN, period.label)
	catalogue = catalogue_for(result.year)
	ustva = ustva_catalogue_for(result.year)
	amounts = result.reported if reported is None else reported
	periods = tuple(
		_period_line(period, filed.get(period), now[period])
		for period in sorted(now, key=lambda key: key.start)
	)
	kennzahlen = tuple(
		line
		for number in ustva
		if (line := _kennzahl_line(number, catalogue.children(number), filed, now, result, amounts))
		is not None
	)
	balance = _balance(result, soll, now, filed, periods, amounts, ustva)
	findings = [
		Finding("BUCHUNG-NACH-ABGABE", Severity.HINT, LATE, (line.period.label, _euros(line.late)))
		for line in periods
		if line.vat_return is not None and line.late
	]
	findings += [
		Finding("ABGLEICH-REST", Severity.ERROR, REST, (line.kennzahl, _euros(line.rest)))
		for line in kennzahlen
		if line.rest
	]
	if balance.rest:
		findings.append(Finding("ABGLEICH-REST", Severity.ERROR, REST_OF_KZ_820, (_euros(balance.rest),)))
	invoices = result.values.get(INVOICE_LINE)
	if invoices is not None and invoices.amount:
		findings.append(
			Finding("VORSTEUER-RECHNUNG", Severity.HINT, INVOICE, (result.year,), (INVOICE_LINE,))
		)
	return Reconciliation(periods, kennzahlen, balance, tuple(findings))


def journal_entries(
	year: int, lines: Iterable[LedgerLine], mapping: Mapping, vouchers: Collection[str]
) -> tuple[Finding, ...]:
	"""One hint at the Journal Entries of the year that move a tax account without the flag Exclude from VAT Return,
	with their number and the first of them by name.

	``vouchers`` names the vouchers of ``lines`` that are Journal Entries; steuerbote/ledger.py leaves out those with
	the flag, so every one here lacks it. A tax account is an account of a tax Kennzahl or a tax account of a
	Verprobung. The amount is the debit less the credit on the account in the voucher.
	"""
	catalogue = mapping.catalogue
	taxes = {rule.account_number for rule in mapping.rules if catalogue[rule.kennzahl].kind is Kind.TAX}
	taxes |= {account for check in mapping.checks for account in check.tax_accounts}
	moved: dict[tuple[str, str], Decimal] = {}
	for line in lines:
		if line.voucher in vouchers and line.account_number in taxes:
			key = (line.voucher, line.account_number)
			moved[key] = moved.get(key, ZERO) + line.debit - line.credit
	vouchers_moved = list(dict.fromkeys(voucher for (voucher, _account), amount in moved.items() if amount))
	if not vouchers_moved:
		return ()
	names = [voucher.partition(":")[2] or voucher for voucher in vouchers_moved[:NAMED_JOURNAL_ENTRIES]]
	more = " …" if len(vouchers_moved) > NAMED_JOURNAL_ENTRIES else ""
	return (
		Finding(
			"JOURNALBUCHUNG-STEUERKONTO",
			Severity.HINT,
			JOURNAL_ENTRY,
			(len(vouchers_moved), year, ", ".join(names) + more),
		),
	)


def _period_line(period: Period, entry: Filed | None, run: UstvaResult) -> PeriodLine:
	if entry is None:
		return PeriodLine(period, None, ZERO, ZERO, run.kz83, ZERO, ZERO)
	at_filing = entry.lines.get(BALANCE_KENNZAHL)
	reported = entry.kz83 if at_filing is None else at_filing.reported
	kz83_now = run.prepayment - entry.kz39
	return PeriodLine(
		period, entry.name, entry.kz83, entry.kz39, kz83_now, kz83_now - reported, reported - entry.kz83
	)


def _kennzahl_line(
	number: str,
	children: tuple[Field, ...],
	filed: ReadOnlyMapping[Period, Filed],
	now: ReadOnlyMapping[Period, UstvaResult],
	result: AnnualResult,
	amounts: ReadOnlyMapping[str, Decimal],
) -> KennzahlLine | None:
	if not children:
		return None
	final = reported = filed_ledger = ZERO
	for entry in filed.values():
		value = entry.lines.get(number)
		if value is not None:
			final += value.final
			reported += value.reported
			filed_ledger += value.amount
	ledger_filed = ledger_unfiled = ZERO
	for period, run in now.items():
		value = run.values.get(number)
		amount = ZERO if value is None else value.amount
		if period in filed:
			ledger_filed += amount
		else:
			ledger_unfiled += amount
	annual = form = exact = ledger = ZERO
	for child in children:
		annual += child.sign * amounts.get(child.element, ZERO)
		annual_value = result.values.get(child.element)
		if annual_value is not None:
			form += child.sign * annual_value.form
			exact += child.sign * annual_value.amount
			ledger += child.sign * annual_value.ledger
	if not any((final, reported, filed_ledger, ledger_filed, ledger_unfiled, annual, exact)):
		return None
	ledger_now = ledger_filed + ledger_unfiled
	return KennzahlLine(
		kennzahl=number,
		filed=final,
		filed_ledger=filed_ledger,
		ledger_now=ledger_now,
		annual=annual,
		late=ledger_filed - filed_ledger,
		corrections=reported - final,
		unfiled=ledger_unfiled,
		rounding=(form - exact) - (reported - filed_ledger),
		annual_only=(exact - ledger) + (annual - form),
		rest=ledger - ledger_now,
	)


def _balance(
	result: AnnualResult,
	soll: Soll,
	now: ReadOnlyMapping[Period, UstvaResult],
	filed: ReadOnlyMapping[Period, Filed],
	periods: tuple[PeriodLine, ...],
	amounts: ReadOnlyMapping[str, Decimal],
	ustva: ReadOnlyMapping[str, Kennzahl],
) -> BalanceLine:
	catalogue = catalogue_for(result.year)
	as_form = entries(catalogue, result.reported, soll.amount)
	as_filed = entries(catalogue, amounts, soll.amount)
	exact = sum((catalogue.effect(element) * value.amount for element, value in result.values.items()), ZERO)
	ledger = sum((catalogue.effect(element) * value.ledger for element, value in result.values.items()), ZERO)
	prepayments = sum((run.prepayment for run in now.values()), ZERO)
	exact_now = sum((_exact_prepayment(run, ustva) for run in now.values()), ZERO)
	filed_lines = [line for line in periods if line.vat_return is not None]
	return BalanceLine(
		kz820=as_filed[KZ_820],
		late=sum((line.late for line in filed_lines), ZERO),
		corrections=sum((line.corrections for line in filed_lines), ZERO),
		unfiled=sum((run.prepayment for period, run in now.items() if period not in filed), ZERO),
		sondervorauszahlung=soll.credited - soll.sondervorauszahlung,
		soll=soll.computed - soll.amount,
		rounding=(as_form[KZ_816] - exact) - (prepayments - exact_now),
		annual_only=(exact - ledger) + (as_filed[KZ_816] - as_form[KZ_816]),
		rest=ledger - exact_now,
	)


def _exact_prepayment(run: UstvaResult, ustva: ReadOnlyMapping[str, Kennzahl]) -> Decimal:
	"""Line 48 of a Voranmeldung from the exact amounts of its run, with the tax of a base at its exact rate."""
	total = ZERO
	for number, value in run.values.items():
		kennzahl = ustva[number]
		if number in (BALANCE_KENNZAHL, SONDERVORAUSZAHLUNG_KENNZAHL) or kennzahl.effect is Effect.NONE:
			continue
		amount = value.amount * kennzahl.rate / HUNDRED if kennzahl.rate is not None else value.amount
		total += amount if kennzahl.effect is Effect.INCREASES else -amount
	return total


def _euros(amount: Decimal) -> str:
	return text.euros(amount)
