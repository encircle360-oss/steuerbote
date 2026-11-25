"""Which Voranmeldungszeitraum a posting belongs to, and what happens to a posting for a period already filed.

**The tax date.** Under the Soll-Versteuerung the tax on a supply arises „mit Ablauf des
Voranmeldungszeitraums, in dem die Leistungen ausgeführt worden sind“ (§ 13 Abs. 1 Nr. 1 Buchst. a Satz 1
UStG), whenever the invoice is written; „Der Zeitpunkt der Leistung ist entscheidend, für welchen
Voranmeldungszeitraum ein Umsatz zu berücksichtigen ist“ (UStAE 13.1 Abs. 1 Satz 6). A posting counts on its
tax date: by the basis SERVICE_DATE the date of the supply its voucher names (``Booking.service_date``, see
service_date()), else its posting date; by the basis POSTING_DATE always its posting date.

- A delivery is performed when the customer gets the power of disposal or the transport begins (UStAE 13.1
  Abs. 2), a service when it is completed, a service over a time when that time ends, unless the parties agreed
  on Teilleistungen (UStAE 13.1 Abs. 3, § 13 Abs. 1 Nr. 1 Buchst. a Sätze 2 und 3 UStG). So the end of a billing
  period dates its supply, and a Delivery Note its delivery.
- A credit note or a debit note changes the base when it is issued: „Die Berichtigungen ... sind für den
  Besteuerungszeitraum vorzunehmen, in dem die Änderung der Bemessungsgrundlage eingetreten ist“ (§ 17 Abs. 1
  Satz 8 UStG). It counts on its posting date.
- Payments received before the supply are taxed when received (§ 13 Abs. 1 Nr. 1 Buchst. a Satz 4 UStG) and
  are booked on that day; payments, Journal Entries, payroll and purchase invoices name no supply and count on
  their posting dates. The input tax needs the supply and the invoice (§ 15 Abs. 1 Satz 1 Nr. 1 UStG), and „Fallen
  Empfang der Leistung und Empfang der Rechnung zeitlich auseinander, ist der Vorsteuerabzug für den
  Besteuerungszeitraum zulässig, in dem erstmalig beide Voraussetzungen erfüllt sind“ (UStAE 15.2 Abs. 2 Satz 6):
  the posting date of the purchase invoice, which is never before the invoice is there.
- The intra-community deliveries of Kz 41 are reported in the period „in dem die Rechnung für diesen Umsatz
  ausgestellt wird, spätestens jedoch“ in that of the month after the supply (§ 18b Satz 2 UStG), and the
  Zusammenfassende Meldung reads the vouchers of Kz 41, 42 and 21 by posting date. The accounts of these three
  Kennzahlen keep the posting date (invoice_date_accounts), so the Voranmeldung and the Zusammenfassende Meldung
  report the same vouchers in the same periods.

**A posting for a filed period.** A posting is late when it was booked after its tax period was filed. With
the treatment CORRECTION it stays in its tax period, whose filed return then needs a corrected return (Kz 10;
§ 18 Abs. 1 Satz 1 UStG with § 153 Abs. 1 AO); a corrected return filed after the booking holds it, so it is
late only after the latest filing. With CURRENT_PERIOD it goes to the first period of the same year that was not
filed yet when it was booked, the period being prepared then, as many bookkeepers do; the first filing of its
period decides, so a later corrected return of that period does not take it back. With no such period left in
the year it stays in its tax period and needs a corrected return, since a Besteuerungszeitraum is the calendar
year (§ 16 Abs. 1 Satz 2 UStG) and the annual return holds it in its own year. Either way every posting is
reported in exactly one period: placements are a function of the posting, the periods and their filings.

**Before the start of the books.** A company that starts with Steuerbote in the middle of its life keeps its books
in ERPNext from a day on; the Voranmeldungen of the periods before were filed outside Steuerbote, from other books.
No booking in ERPNext is in such a return, so each period before the start counts as filed before any booking
(filed_outside): a booking that belongs there is late, whenever it was entered, and either needs a corrected return
where that period was filed or goes to the period open when it was booked. The periods before the start are those
filed before Steuerbote, else those of the rules, else the months (periods_with_the_books), so that no such booking
counts by its date alone.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Collection, Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise

from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.kennzahlen import BALANCE_KENNZAHL, SONDERVORAUSZAHLUNG_KENNZAHL
from steuerbote.ustva.mapping import Mapping
from steuerbote.ustva.period import Period
from steuerbote.ustva.rounding import ZERO


class PeriodBasis(StrEnum):
	"""The setting „Zuordnung zum Voranmeldungszeitraum“ of the VAT Return Settings."""

	SERVICE_DATE = "By Service Date"
	POSTING_DATE = "By Posting Date"


class LateTreatment(StrEnum):
	"""The setting „Belege für abgegebene Zeiträume“ of the VAT Return Settings."""

	CORRECTION = "Corrected Return"
	CURRENT_PERIOD = "Current Period"


DEFAULT_BASIS = PeriodBasis.SERVICE_DATE
DEFAULT_TREATMENT = LateTreatment.CORRECTION

# Kz 41 by the invoice (§ 18b Satz 2 UStG); Kz 42 and 21 by the supply (§ 18b Satz 3 UStG), which the
# Zusammenfassende Meldung reads by posting date, so the Voranmeldung does as well.
INVOICE_DATE_KENNZAHLEN = frozenset({"41", "42", "21"})
# Kz 83 follows from the others, Kz 39 from the settings.
UNCOMPARED_KENNZAHLEN = frozenset({BALANCE_KENNZAHL, SONDERVORAUSZAHLUNG_KENNZAHL})


def service_date(
	*,
	to_date: date | None,
	from_date: date | None,
	delivery_date: date | None,
	is_return: bool,
	is_debit_note: bool,
) -> date | None:
	"""The date of the supply a Sales Invoice names: the end of its billing period, else its start, else the
	latest of its Delivery Notes; none for a credit note or a debit note, which count when they are issued."""
	if is_return or is_debit_note:
		return None
	return to_date or from_date or delivery_date


def invoice_date_accounts(mapping: Mapping) -> frozenset[str]:
	"""The accounts of Kz 41, 42 and 21, which keep the posting date under every basis."""
	return frozenset(
		rule.account_number for rule in mapping.rules if rule.kennzahl in INVOICE_DATE_KENNZAHLEN
	)


@dataclass(frozen=True, slots=True)
class Booking:
	"""The postings of one voucher on one account on one posting date, when they were booked, and the date of
	the supply the voucher names, if any."""

	account_number: str
	voucher: str
	posting_date: date
	booked_at: datetime
	debit: Decimal = ZERO
	credit: Decimal = ZERO
	service_date: date | None = None

	def __post_init__(self) -> None:
		if not self.voucher:
			raise ValueError("a booking names its voucher")
		self.line()

	def line(self) -> LedgerLine:
		return LedgerLine(self.account_number, self.debit, self.credit, self.voucher)


@dataclass(frozen=True, slots=True)
class Filing:
	"""When the returns of a period were filed: the first time and the latest, a corrected return."""

	period: Period
	first: datetime
	latest: datetime

	def __post_init__(self) -> None:
		if self.latest < self.first:
			raise ValueError(f"the latest filing of {self.period.label} cannot precede the first")


@dataclass(frozen=True, slots=True)
class Placement:
	"""Where a booking is reported: ``tax_period`` holds its tax date, ``period`` reports it. Both are None for a
	date outside the periods given, which counts by itself."""

	booking: Booking
	tax_date: date
	tax_period: Period | None
	period: Period | None
	late: bool

	@property
	def moved(self) -> bool:
		return self.period != self.tax_period

	@property
	def needs_correction(self) -> bool:
		return self.late and not self.moved

	@property
	def date(self) -> date:
		"""The day the booking counts on: its tax date, or the first day of the period it moved to."""
		if self.moved and self.period is not None:
			return self.period.start
		return self.tax_date


class Assignment:
	"""Places bookings into the Voranmeldungszeiträume ``periods``, given in order without overlap, with the
	filings of these periods, by ``basis`` and ``treatment``."""

	__slots__ = ("_basis", "_filings", "_invoice_date_accounts", "_periods", "_treatment")

	def __init__(
		self,
		basis: PeriodBasis,
		treatment: LateTreatment,
		periods: Iterable[Period],
		filings: Iterable[Filing] = (),
		invoice_date_accounts: Collection[str] = (),
	) -> None:
		self._basis = PeriodBasis(basis)
		self._treatment = LateTreatment(treatment)
		self._periods: tuple[Period, ...] = tuple(periods)
		for earlier, later in pairwise(self._periods):
			if earlier.end >= later.start:
				raise ValueError(f"periods must be in order without overlap: {earlier.label}, {later.label}")
		self._filings: dict[Period, Filing] = {filing.period: filing for filing in filings}
		self._invoice_date_accounts = frozenset(invoice_date_accounts)

	def tax_date(self, booking: Booking) -> date:
		if (
			self._basis is PeriodBasis.SERVICE_DATE
			and booking.service_date is not None
			and booking.account_number not in self._invoice_date_accounts
		):
			return booking.service_date
		return booking.posting_date

	def place(self, booking: Booking) -> Placement:
		tax_date = self.tax_date(booking)
		tax_period = self._period_of(tax_date)
		filing = self._filings.get(tax_period) if tax_period is not None else None
		if filing is None:
			return Placement(booking, tax_date, tax_period, tax_period, late=False)
		if self._treatment is LateTreatment.CORRECTION:
			return Placement(
				booking, tax_date, tax_period, tax_period, late=booking.booked_at > filing.latest
			)
		if booking.booked_at <= filing.first:
			return Placement(booking, tax_date, tax_period, tax_period, late=False)
		return Placement(
			booking, tax_date, tax_period, self._open_at(tax_period, booking.booked_at), late=True
		)

	def lines(self, bookings: Iterable[Booking], period: Period) -> list[LedgerLine]:
		"""The ledger lines reported in ``period``; for a period of another rhythm, those of its days."""
		return self.lines_between(bookings, period.start, period.end)

	def lines_between(self, bookings: Iterable[Booking], start: date, end: date) -> list[LedgerLine]:
		return [booking.line() for booking in bookings if start <= self.place(booking).date <= end]

	def late(self, bookings: Iterable[Booking]) -> list[Placement]:
		"""The late bookings, in the order they were booked."""
		placements = (self.place(booking) for booking in bookings)
		return sorted((placement for placement in placements if placement.late), key=_booked_at)

	def late_vouchers(self, bookings: Iterable[Booking]) -> list[Placement]:
		"""The first late booking of each voucher and tax period, in the order they were booked."""
		seen: set[tuple[str, Period | None]] = set()
		found = []
		for placement in self.late(bookings):
			key = (placement.booking.voucher, placement.tax_period)
			if key not in seen:
				seen.add(key)
				found.append(placement)
		return found

	def _period_of(self, day: date) -> Period | None:
		return next((period for period in self._periods if period.contains(day)), None)

	def _open_at(self, tax_period: Period, booked_at: datetime) -> Period:
		"""The first period after ``tax_period`` in its year that was not filed when the booking was made; the tax
		period itself when the year has none left."""
		for period in self._periods:
			if period.year != tax_period.year or period.start <= tax_period.end:
				continue
			filing = self._filings.get(period)
			if filing is None or filing.first > booked_at:
				return period
		return tax_period


def _booked_at(placement: Placement) -> tuple[datetime, str]:
	return placement.booking.booked_at, placement.booking.voucher


def periods_with_the_books(
	periods: Iterable[Period], prior: Iterable[Period], start: date | None, years: Iterable[int]
) -> tuple[Period, ...]:
	"""The periods of the years in order: before ``start`` those filed before Steuerbote (``prior``), else those of the
	rules (``periods``), else the month; from ``start`` on those of the rules. Without a start, the rules alone."""
	periods = tuple(periods)
	if start is None:
		return periods
	prior = tuple(prior)
	found: list[Period] = []
	for year in years:
		for month in range(1, 13):
			first = date(year, month, 1)
			candidates = (*prior, *periods, Period.month(year, month)) if first < start else periods
			period = next((period for period in candidates if period.contains(first)), None)
			if period is not None and period not in found:
				found.append(period)
	return tuple(sorted(found, key=lambda period: period.start))


def filed_outside(periods: Iterable[Period], start: date | None) -> tuple[Filing, ...]:
	"""A filing before any booking for each period before ``start``."""
	return tuple(
		Filing(period, datetime.min, datetime.min)
		for period in periods
		if start is not None and period.start < start
	)


@dataclass(frozen=True, slots=True)
class Change:
	"""A Kennzahl whose amount by today's ledger differs from the amount its filed return took from the ledger."""

	kennzahl: str
	filed: Decimal
	now: Decimal

	@property
	def difference(self) -> Decimal:
		return self.now - self.filed


def changes(filed: ReadOnlyMapping[str, Decimal], now: ReadOnlyMapping[str, Decimal]) -> tuple[Change, ...]:
	"""The Kennzahlen of a filed period whose ledger amounts differ today, in the order of ``filed`` and then of
	``now``; Kz 83 and Kz 39 are left out."""
	numbers = [number for number in (*filed, *now) if number not in UNCOMPARED_KENNZAHLEN]
	found = []
	for number in dict.fromkeys(numbers):
		before, after = filed.get(number, ZERO), now.get(number, ZERO)
		if before != after:
			found.append(Change(number, before, after))
	return tuple(found)
