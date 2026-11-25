"""The ledger of the Voranmeldung by Voranmeldungszeitraum, as steuerbote.ustva.assignment places it.

The VAT Return Settings of a company say how a booking finds its period (period_basis: by the date of the supply
or by the posting date) and what happens to a booking for a period already filed (late_documents: it stays there
for a corrected return, or it goes to the period open when it was booked). A period counts as filed with the
records that file its returns (transmission.filings: a Senden that ELSTER accepted or whose outcome is unknown,
or the note of a filing outside Steuerbote), the first and the latest of them by the time they were recorded.

VatLedger reads the bookings of a time once (ledger.load_bookings) and gives the ledger lines of each period in
it, the late bookings and, for a filed period, which Kennzahlen the ledger gives other amounts today than the
return filed for it. The Voranmeldung, its report UStVA Kennzahlen and the Umsatzsteuererklärung read their lines
here, so a year is the sum of its periods under the same rule.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import frappe
from frappe.model.document import Document
from frappe.utils import cint, get_datetime

from steuerbote.ledger import load_bookings
from steuerbote.steuerbote.doctype.elster_transmission.transmission import filings as filing_records
from steuerbote.steuerbote.doctype.vat_return_settings import rules
from steuerbote.ustva import LedgerLine, Period, Rhythm
from steuerbote.ustva.assignment import (
	DEFAULT_BASIS,
	DEFAULT_TREATMENT,
	INVOICE_DATE_KENNZAHLEN,
	Assignment,
	Filing,
	LateTreatment,
	PeriodBasis,
	Placement,
)

VAT_RETURN = "VAT Return"
KENNZAHL = "VAT Return Kennzahl"
SETTINGS = "VAT Return Settings"
MAPPING = "VAT Return Mapping"
MAPPING_RULE = "VAT Return Mapping Rule"
FILED = "Abgegeben"


def basis_of(settings: Document | None) -> PeriodBasis:
	"""The basis of the settings; settings saved before the field existed take the default."""
	return PeriodBasis((settings and settings.get("period_basis")) or DEFAULT_BASIS)


def treatment_of(settings: Document | None) -> LateTreatment:
	return LateTreatment((settings and settings.get("late_documents")) or DEFAULT_TREATMENT)


def filings(company: str, years: Iterable[int]) -> list[Filing]:
	"""When the Voranmeldungszeiträume of the company in these years were filed, first and latest."""
	returns = frappe.get_all(
		VAT_RETURN,
		filters={"company": company, "year": ["in", list(years)]},
		fields=["name", "year", "rhythm", "period_index"],
	)
	periods = {
		entry.name: Period(cint(entry.year), Rhythm(entry.rhythm), cint(entry.period_index))
		for entry in returns
	}
	times: dict[Period, list] = {}
	for record in filing_records(VAT_RETURN, list(periods)):
		if record.finished_at:
			times.setdefault(periods[record.document], []).append(get_datetime(record.finished_at))
	return [Filing(period, min(found), max(found)) for period, found in times.items()]


class VatLedger:
	"""The bookings of the company from ``start`` to ``end`` placed into the Voranmeldungszeiträume of these years by
	its settings; the accounts of Kz 41, 42 and 21 in its VAT Return Mapping keep the posting date. A company
	without settings has no periods and counts every booking by its date with the defaults."""

	def __init__(self, company: str, start: date, end: date) -> None:
		settings = frappe.get_doc(SETTINGS, company) if frappe.db.exists(SETTINGS, company) else None
		years = range(start.year, end.year + 1)
		periods = (
			[period for year in years for period in rules.periods_of(settings.get_period_rules(), year)]
			if settings is not None
			else []
		)
		filed = filings(company, years)
		self.company = company
		self.basis = basis_of(settings)
		self.treatment = treatment_of(settings)
		self.assignment = Assignment(
			self.basis, self.treatment, periods, filed, accounts_by_invoice_date(company)
		)
		self.periods = tuple(periods)
		self.filed = frozenset(filing.period for filing in filed)
		self.bookings = load_bookings(company, start, end, self.basis is PeriodBasis.SERVICE_DATE)
		self.placements = [self.assignment.place(booking) for booking in self.bookings]

	@classmethod
	def for_period(cls, company: str, period: Period) -> VatLedger:
		"""The ledger a return of ``period`` needs: from the start of the year before, for the comparison with the
		previous year and the periods filed before it, to the end of the period."""
		return cls(company, date(period.year - 1, 1, 1), period.end)

	@classmethod
	def for_year(cls, company: str, year: int) -> VatLedger:
		return cls(company, date(year, 1, 1), date(year, 12, 31))

	def lines(self, period: Period) -> list[LedgerLine]:
		"""The ledger lines ``period`` reports, as Assignment.lines gives them, from the placements made once."""
		return self.lines_between(period.start, period.end)

	def lines_between(self, start: date, end: date) -> list[LedgerLine]:
		return [placement.booking.line() for placement in self.placements if start <= placement.date <= end]

	def posting_dates(self, period: Period) -> dict[str, date]:
		"""The first posting date of each voucher reported in ``period``, by voucher key."""
		dates: dict[str, date] = {}
		for placement in self.placements:
			booking = placement.booking
			if period.contains(placement.date):
				known = dates.get(booking.voucher)
				dates[booking.voucher] = min(known, booking.posting_date) if known else booking.posting_date
		return dates

	def late(self) -> list[Placement]:
		"""The first late booking of each voucher and period."""
		return self.assignment.late_vouchers(self.bookings)

	def filed_before(self, period: Period) -> list[Period]:
		"""The filed periods before ``period`` in the time of the ledger, in order."""
		return [earlier for earlier in self.periods if earlier in self.filed and earlier.start < period.start]


def accounts_by_invoice_date(company: str) -> frozenset[str]:
	"""The accounts the VAT Return Mapping of the company gives Kz 41, 42 or 21 (assignment.invoice_date_accounts)."""
	return frozenset(
		frappe.get_all(
			MAPPING_RULE,
			filters={
				"parenttype": MAPPING,
				"parent": company,
				"kennzahl": ["in", sorted(INVOICE_DATE_KENNZAHLEN)],
			},
			pluck="account_number",
		)
	)


def filed_amounts(company: str, period: Period) -> dict[str, Decimal] | None:
	"""The ledger amounts the return filed for the period took, by Kennzahl; None without one."""
	name = frappe.db.get_value(
		VAT_RETURN,
		{
			"company": company,
			"year": period.year,
			"period_code": period.code,
			"docstatus": 1,
			"status": FILED,
		},
		"name",
		order_by="creation desc",
	)
	if not name:
		return None
	rows = frappe.get_all(
		KENNZAHL, filters={"parenttype": VAT_RETURN, "parent": name}, fields=["kennzahl", "amount"]
	)
	return {row.kennzahl: Decimal(str(row.amount or 0)).quantize(Decimal("0.01")) for row in rows}
