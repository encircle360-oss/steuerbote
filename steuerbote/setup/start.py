"""Start mit Steuerbote im laufenden Betrieb: a company whose books before a day were kept outside Steuerbote.

The company names the first day its books in ERPNext are complete, the start of the books (books start in the VAT
Return Settings). A Voranmeldungszeitraum that begins before it lies before the start: Steuerbote does not compute it,
since the ledger holds only the opening balances of that time, and takes it as filed outside. What later filings need
of that time, the company enters once as filed, a Voranmeldung vor Steuerbote (PriorFiling) with the source document
of the filing and a reason:

- The Sondervorauszahlung is one eleventh of the Vorauszahlungen of the previous year, Kz 83 of its Voranmeldungen
  with the Sondervorauszahlung Kz 39 credited in them (§ 47 Absatz 1 UStDV, Zeile 8 of form USt 1 H).
- The Voranmeldungszeitraum follows the tax of the previous year (§ 18 Absatz 2 UStG), which year_tax() takes from the
  Voranmeldungen of a whole year as the same sum.
- A quarterly Zusammenfassende Meldung needs the Lieferungen of the four quarters before (§ 18a Absatz 1 Satz 2 UStG),
  Kz 41 and 42 of the Voranmeldungen, which deliveries() gives by month.

The filings that need such months are the Sondervorauszahlung of the year of the start, when it is due after the
start, on 10 February (§ 48 Absatz 2 UStDV), and of every later year, so missing_months() names the months of the year
before a start in January or February and those of the year of the start before it, from the month the company began.

The annual returns carry amounts from the last notices of the Finanzamt: the loss carried forward (§ 10d EStG), the
Fehlbetrag (§ 10a GewStG) and the steuerliches Einlagekonto (§ 27 KStG), as the Annual Filing Settings hold them.
missing_carry_forwards() names those without an amount as of the end of the last year whose returns were filed outside
Steuerbote. The Voranmeldungen of the last periods before the start are paid in the new year; prior_payments() finds
such payments on the accounts of the Vorauszahlungen, which the Umsatzsteuererklärung then leaves out of the
Vorauszahlungen of the year. checklist() gives what the setup shows or checks for such a start, in the order a user works through it.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from steuerbote.steuerbote.doctype.annual_filing_settings.rules import CarryForward, CarryForwardKind
from steuerbote.ustva.calculation import LedgerLine, require_cents
from steuerbote.ustva.period import Period, day_label
from steuerbote.ustva.rounding import ZERO

MONTHS = 12
# The Sondervorauszahlung of a year is due on 10 February (§ 48 Absatz 2 UStDV): a start up to February still files
# it, from the Voranmeldungen of the year before.
LAST_MONTH_BEFORE_SONDERVORAUSZAHLUNG = 2

NOT_FIRST_OF_MONTH = "The books in Steuerbote start on the first day of a month, not on {0}."
NOT_BEFORE_START = (
	"{0} begins on or after the start of the books in Steuerbote on {1}: Steuerbote computes it from the books, so "
	"it takes no Voranmeldung filed before Steuerbote for it."
)
START_MISSING = (
	"If the books of the company begin in ERPNext with opening balances, enter that day as Books Start in the VAT "
	"Return Settings: the Voranmeldungen before it were filed outside Steuerbote."
)
START_SET = "The books of the company begin in ERPNext on {0}; Steuerbote computes the Voranmeldungen from that day on."
OPENING_FLAGGED = (
	"The opening balances of {0} stay out of the Voranmeldung: no Journal Entry of that day books on an account of the "
	"VAT Return Mapping without the flag Exclude from VAT Return."
)
OPENING_UNFLAGGED = (
	"Journal Entries of {0} book on accounts of the VAT Return Mapping without the flag Exclude from VAT Return and go "
	"into the Voranmeldung: {1}. Post opening balances as an Opening Entry or tick the flag."
)
PRIOR_COMPLETE = (
	"The Voranmeldungen filed before Steuerbote are entered for every month before {0} that the Sondervorauszahlung, "
	"the Voranmeldungszeitraum and the Zusammenfassende Meldung read."
)
PRIOR_MISSING = (
	"Enter the Voranmeldungen filed before Steuerbote, as filed with Kz 83, 39, 41, 42 and 21, as VAT Return Prior "
	"Filings: {0}."
)
PRIOR_PAYMENTS_CLEAN = (
	"Payments and refunds of the Voranmeldungen filed before Steuerbote are booked on the prior-year VAT account, "
	"not on the accounts of the Vorauszahlungen of {0}."
)
PRIOR_PAYMENTS_FOUND = (
	"These payments on the accounts of the Vorauszahlungen pay Kz 83 of Voranmeldungen filed before Steuerbote: {0}. "
	"The Umsatzsteuererklärung leaves them out of the Vorauszahlungen of the year; book such payments on the prior-year "
	"VAT account."
)
DAUERFRIST_INFO = (
	"If the Finanzamt granted the Dauerfristverlängerung before Steuerbote, give the VAT Return Settings its row for "
	"{0}; a monthly filer files the Sondervorauszahlung of {0} as a Dauerfristverlängerung without the Antrag."
)
ANNUAL_SETTINGS_MISSING = (
	"Make the Annual Filing Settings and enter the carry-forwards of the last notices as of {0}, 0 as well."
)
CARRY_FORWARDS_COMPLETE = "The carry-forwards of the last notices as of {0} are entered."
CARRY_FORWARDS_MISSING = (
	"Enter the carry-forwards of the last notices as of {0} in the Annual Filing Settings, 0 as well, and confirm "
	"them against the notice: {1}."
)
PREPAYMENTS_INFO = (
	"Enter the Vorauszahlungen of Körperschaftsteuer, Solidaritätszuschlag and Gewerbesteuer for {0} that the "
	"notices set in the Annual Filing Settings."
)
PRIOR_YEAR_ACCOUNTS_INFO = (
	"The first Jahresabschluss in Steuerbote shows {0} from the festgestellter Jahresabschluss of {0}: enter its "
	"amounts under Vorjahr von Hand."
)
MESSAGES = (
	NOT_FIRST_OF_MONTH,
	NOT_BEFORE_START,
	START_MISSING,
	START_SET,
	OPENING_FLAGGED,
	OPENING_UNFLAGGED,
	PRIOR_COMPLETE,
	PRIOR_MISSING,
	PRIOR_PAYMENTS_CLEAN,
	PRIOR_PAYMENTS_FOUND,
	DAUERFRIST_INFO,
	ANNUAL_SETTINGS_MISSING,
	CARRY_FORWARDS_COMPLETE,
	CARRY_FORWARDS_MISSING,
	PREPAYMENTS_INFO,
	PRIOR_YEAR_ACCOUNTS_INFO,
)

# The carry-forwards a GmbH or UG takes from its notices into every Körperschaft- and Gewerbesteuererklärung.
FIRST_YEAR_KINDS = (CarryForwardKind.LOSS, CarryForwardKind.FEHLBETRAG, CarryForwardKind.EINLAGEKONTO)


class StartError(ValueError):
	"""A start or a prior filing that does not fit; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


def check_start(start: date) -> date:
	"""The start of the books, the first day of a month, so that every Voranmeldungszeitraum lies wholly before or
	after it."""
	if start.day != 1:
		raise StartError(NOT_FIRST_OF_MONTH, day_label(start))
	return start


def before_start(period_start: date, start: date | None) -> bool:
	"""Whether a period beginning on ``period_start`` lies before the start of the books, whose ledger is then not
	complete; nothing does without a start."""
	return start is not None and period_start < start


def check_prior_period(period: Period, start: date | None) -> None:
	"""A Voranmeldung filed before Steuerbote is one of a period before the start."""
	if start is not None and not before_start(period.start, start):
		raise StartError(NOT_BEFORE_START, period.label, day_label(start))


@dataclass(frozen=True, slots=True)
class PriorFiling:
	"""A Voranmeldung filed before Steuerbote, as filed: its period, the name of its record, the day it was filed and
	Kz 83, the Sondervorauszahlung its Kz 39 credited, and Kz 41, 42 and 21."""

	period: Period
	name: str
	filed_on: date
	kz83: Decimal
	kz39: Decimal = ZERO
	kz41: Decimal = ZERO
	kz42: Decimal = ZERO
	kz21: Decimal = ZERO

	def __post_init__(self) -> None:
		for amount in (self.kz83, self.kz39, self.kz41, self.kz42, self.kz21):
			require_cents(amount)

	@property
	def months(self) -> tuple[tuple[int, int], ...]:
		return tuple(
			(self.period.year, month) for month in range(self.period.first_month, self.period.last_month + 1)
		)


def latest(filings: Iterable[PriorFiling]) -> tuple[PriorFiling, ...]:
	"""The filing of each period that counts, in the order of time: the latest filed, a correction replaces the filing
	before it; of two filed on the same day the one given first, as callers list the latest made first."""
	found: dict[Period, PriorFiling] = {}
	for filed in filings:
		known = found.get(filed.period)
		if known is None or filed.filed_on > known.filed_on:
			found[filed.period] = filed
	return tuple(sorted(found.values(), key=lambda filed: filed.period.start))


def overlapping(filed: PriorFiling, others: Iterable[PriorFiling]) -> PriorFiling | None:
	"""A filing of another period that covers a month of ``filed``; one of the same period corrects it instead."""
	months = set(filed.months)
	return next(
		(other for other in others if other.period != filed.period and months.intersection(other.months)),
		None,
	)


def covered(filings: Iterable[PriorFiling]) -> frozenset[tuple[int, int]]:
	"""The months the filings cover, by year and month."""
	return frozenset(month for filed in filings for month in filed.months)


def year_tax(filings: Iterable[PriorFiling], year: int, first_month: int = 1) -> Decimal | None:
	"""The tax of ``year`` by its Voranmeldungen: Kz 83 with the Sondervorauszahlung credited in Kz 39, so before that
	payment; None unless the latest filings cover each month from ``first_month``, the month a company began in."""
	of_year = [filed for filed in latest(filings) if filed.period.year == year]
	if not {(year, month) for month in range(first_month, MONTHS + 1)} <= covered(of_year):
		return None
	return sum((filed.kz83 + filed.kz39 for filed in of_year), ZERO)


def deliveries(filings: Iterable[PriorFiling]) -> dict[tuple[int, int], Decimal]:
	"""Kz 41 and 42 of the latest filings by month, the amount of a quarter in its first month: the threshold of the
	Zusammenfassende Meldung sums them by quarter."""
	found: dict[tuple[int, int], Decimal] = {}
	for filed in latest(filings):
		first, *rest = filed.months
		found[first] = filed.kz41 + filed.kz42
		found.update(dict.fromkeys(rest, ZERO))
	return found


def missing_months(
	start: date | None, began: date | None, filings: Iterable[PriorFiling]
) -> tuple[tuple[int, int], ...]:
	"""The months before the start that later filings read and no filing covers: those of the year before a start in
	January or February, whose Voranmeldungen make the Sondervorauszahlung due after it, and those of the year of the
	start before it; none before the month the company began."""
	if start is None:
		return ()
	first_year = start.year - 1 if start.month <= LAST_MONTH_BEFORE_SONDERVORAUSZAHLUNG else start.year
	month = (first_year, 1)
	if began is not None:
		month = max(month, (began.year, began.month))
	known = covered(filings)
	found = []
	while month < (start.year, start.month):
		if month not in known:
			found.append(month)
		month = (month[0] + 1, 1) if month[1] == MONTHS else (month[0], month[1] + 1)
	return tuple(found)


@dataclass(frozen=True, slots=True)
class PriorPayment:
	"""A voucher on the accounts of the Vorauszahlungen that pays Kz 83 of a Voranmeldung filed before Steuerbote, its
	``amount`` debit less credit, a refund negative."""

	voucher: str
	amount: Decimal
	filing: PriorFiling


def prior_payments(lines: Iterable[LedgerLine], filings: Iterable[PriorFiling]) -> tuple[PriorPayment, ...]:
	"""The vouchers of ``lines``, the postings on the accounts of the Vorauszahlungen, that pay Kz 83 of the latest
	filing of a period before Steuerbote: in the first year a payment there is the Vorauszahlung of the last periods
	before the start, which the Vorauszahlungssoll of the new year does not hold (USt 2 E, Zeilen 124 bis 126). A voucher
	pays a filing when its amount over all its lines is that Kz 83, not zero; each voucher and each filing pays once, the
	latest periods first, since the new year pays them, and the vouchers in the order given."""
	amounts: dict[str, Decimal] = {}
	for entry in lines:
		key = entry.voucher or ""
		amounts[key] = amounts.get(key, ZERO) + entry.debit - entry.credit
	found = []
	for filed in reversed(latest(filings)):
		if not filed.kz83:
			continue
		voucher = next(
			(key for key, amount in amounts.items() if key and amount == filed.kz83),
			None,
		)
		if voucher is not None:
			found.append(PriorPayment(voucher, amounts.pop(voucher), filed))
	return tuple(sorted(found, key=lambda payment: payment.filing.period.start))


def missing_carry_forwards(stated: Iterable[CarryForward], as_of: date) -> tuple[CarryForwardKind, ...]:
	"""The kinds of FIRST_YEAR_KINDS without an amount stated as of the day, in their order."""
	known = {carry_forward.kind for carry_forward in stated if carry_forward.as_of == as_of}
	return tuple(kind for kind in FIRST_YEAR_KINDS if kind not in known)


def first_annual_year(start: date) -> int:
	"""The first year whose annual returns Steuerbote computes: the books cover it whole."""
	return start.year if (start.month, start.day) == (1, 1) else start.year + 1


class Item(Enum):
	START = "start"
	OPENING_ENTRIES = "opening_entries"
	PRIOR_RETURNS = "prior_returns"
	PRIOR_PAYMENTS = "prior_payments"
	DAUERFRIST = "dauerfrist"
	CARRY_FORWARDS = "carry_forwards"
	PREPAYMENTS = "prepayments"
	PRIOR_YEAR_ACCOUNTS = "prior_year_accounts"


@dataclass(frozen=True, slots=True)
class Facts:
	"""What the site says about the start: the start of the books, the Journal Entries of its day that the Voranmeldung
	would count, the months missing_months() names, whether the company has Annual Filing Settings and the
	carry-forwards missing_carry_forwards() names."""

	start: date | None
	unflagged: tuple[str, ...] = ()
	missing_prior: tuple[tuple[int, int], ...] = ()
	annual_settings: bool = False
	missing_carry_forwards: tuple[CarryForwardKind, ...] = ()
	prior_payments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Check:
	"""An item of the checklist: ``done`` is True or False where the site tells, None for an item it only shows; without
	a start of the books the checklist only says what one is for, since a company whose books are complete needs none."""

	item: Item
	done: bool | None
	template: str
	values: tuple = ()


def checklist(facts: Facts) -> tuple[Check, ...]:
	"""What a start with opening balances needs, in the order a user works through it."""
	start = facts.start
	if start is None:
		return (Check(Item.START, None, START_MISSING),)
	day = day_label(start)
	annual_year = first_annual_year(start)
	year_end = day_label(date(annual_year - 1, MONTHS, 31))
	checks = [Check(Item.START, True, START_SET, (day,))]
	if facts.unflagged:
		checks.append(
			Check(Item.OPENING_ENTRIES, False, OPENING_UNFLAGGED, (day, ", ".join(facts.unflagged)))
		)
	else:
		checks.append(Check(Item.OPENING_ENTRIES, True, OPENING_FLAGGED, (day,)))
	if facts.missing_prior:
		labels = ", ".join(Period.month(*month).label for month in facts.missing_prior)
		checks.append(Check(Item.PRIOR_RETURNS, False, PRIOR_MISSING, (labels,)))
	else:
		checks.append(Check(Item.PRIOR_RETURNS, True, PRIOR_COMPLETE, (day,)))
	if facts.prior_payments:
		checks.append(
			Check(Item.PRIOR_PAYMENTS, False, PRIOR_PAYMENTS_FOUND, (", ".join(facts.prior_payments),))
		)
	else:
		checks.append(Check(Item.PRIOR_PAYMENTS, True, PRIOR_PAYMENTS_CLEAN, (start.year,)))
	checks.append(Check(Item.DAUERFRIST, None, DAUERFRIST_INFO, (start.year,)))
	if not facts.annual_settings:
		checks.append(Check(Item.CARRY_FORWARDS, False, ANNUAL_SETTINGS_MISSING, (year_end,)))
	elif facts.missing_carry_forwards:
		kinds = ", ".join(str(kind) for kind in facts.missing_carry_forwards)
		checks.append(Check(Item.CARRY_FORWARDS, False, CARRY_FORWARDS_MISSING, (year_end, kinds)))
	else:
		checks.append(Check(Item.CARRY_FORWARDS, True, CARRY_FORWARDS_COMPLETE, (year_end,)))
	checks.append(Check(Item.PREPAYMENTS, None, PREPAYMENTS_INFO, (annual_year,)))
	checks.append(Check(Item.PRIOR_YEAR_ACCOUNTS, None, PRIOR_YEAR_ACCOUNTS_INFO, (annual_year - 1,)))
	return tuple(checks)
