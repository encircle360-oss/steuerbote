"""The ledger of the Voranmeldung by Voranmeldungszeitraum: the bookings of steuerbote.ledger with the date of the
supply of a Sales Invoice, and their places by the VAT Return Settings and the filings (steuerbote.vat_periods)."""

from datetime import date, datetime

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.ledger import load_bookings, load_lines
from steuerbote.patches import set_the_assignment_to_the_voranmeldungszeitraum as patch
from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)
from steuerbote.tests.late_documents import ACCOUNTS, delivery_note, filed_return, sales_invoice, set_rule
from steuerbote.ustva import LedgerLine, Period
from steuerbote.ustva.assignment import PeriodBasis
from steuerbote.vat_periods import VatLedger, accounts_by_invoice_date, filings

COMPANY = "Steuerbote Test Leistungsdatum GmbH"
JULY = Period.month(2026, 7)
AUGUST = Period.month(2026, 8)
SEPTEMBER = Period.month(2026, 9)


class VatPeriodsTest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STLD")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)

	def setUp(self):
		frappe.db.savepoint("vat_periods_test")
		self.addCleanup(frappe.db.rollback, save_point="vat_periods_test")

	def invoice(self, name: str, posting: str, booked: str, **fields) -> str:
		return sales_invoice(COMPANY, self.account, name, posting, booked, **fields)

	def file(self, period: Period, at: str) -> None:
		filed_return(COMPANY, period, at)

	def set_rule(self, basis: str = "By Service Date", late: str = "Corrected Return") -> None:
		set_rule(COMPANY, basis, late)

	def vouchers(self, lines: list[LedgerLine]) -> list[str]:
		return sorted({line.voucher for line in lines})

	def test_new_settings_take_the_legal_rule_and_the_corrected_return(self):
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		self.assertEqual(
			(settings.period_basis, settings.late_documents), ("By Service Date", "Corrected Return")
		)

	def test_the_patch_gives_settings_without_a_rule_the_defaults_and_keeps_a_choice(self):
		frappe.db.set_value(
			"VAT Return Settings", COMPANY, {"period_basis": "", "late_documents": "Current Period"}
		)
		patch.execute()
		self.assertEqual(
			frappe.db.get_value("VAT Return Settings", COMPANY, ["period_basis", "late_documents"]),
			("By Service Date", "Current Period"),
		)

	def test_the_bookings_of_a_sales_invoice_carry_the_end_of_its_billing_period(self):
		voucher = self.invoice(
			"SINV-LD-0001", "2026-08-03", "2026-08-03 09:00:00", from_date="2026-07-01", to_date="2026-07-31"
		)
		bookings = [
			b for b in load_bookings(COMPANY, "2026-07-01", "2026-07-31", True) if b.voucher == voucher
		]
		self.assertEqual(len(bookings), 3)
		self.assertEqual({b.service_date for b in bookings}, {date(2026, 7, 31)})
		self.assertEqual({b.posting_date for b in bookings}, {date(2026, 8, 3)})
		self.assertEqual({b.booked_at for b in bookings}, {datetime(2026, 8, 3, 9)})

	def test_by_posting_date_an_invoice_of_a_later_month_is_not_read_for_the_month_of_its_supply(self):
		voucher = self.invoice("SINV-LD-0002", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31")
		self.assertNotIn(
			voucher, {b.voucher for b in load_bookings(COMPANY, "2026-07-01", "2026-07-31", False)}
		)

	def test_a_delivery_note_dates_the_supply_of_an_invoice_without_a_billing_period(self):
		voucher = self.invoice("SINV-LD-0003", "2026-08-05", "2026-08-05 09:00:00")
		delivery_note(COMPANY, "DN-LD-0003", "2026-07-30", "SINV-LD-0003")
		ledger = VatLedger(COMPANY, date(2026, 1, 1), date(2026, 12, 31))
		self.assertIn(voucher, self.vouchers(ledger.lines(JULY)))
		self.assertNotIn(voucher, self.vouchers(ledger.lines(AUGUST)))

	def test_by_service_date_the_month_of_the_supply_reports_the_invoice(self):
		voucher = self.invoice("SINV-LD-0004", "2026-09-20", "2026-09-20 09:00:00", to_date="2026-07-31")
		ledger = VatLedger.for_period(COMPANY, SEPTEMBER)
		self.assertIn(voucher, self.vouchers(ledger.lines(JULY)))
		self.assertNotIn(voucher, self.vouchers(ledger.lines(SEPTEMBER)))
		self.assertEqual(ledger.posting_dates(JULY)[voucher], date(2026, 9, 20))

	def test_by_posting_date_the_month_of_the_posting_reports_it(self):
		self.set_rule("By Posting Date")
		voucher = self.invoice("SINV-LD-0005", "2026-09-20", "2026-09-20 09:00:00", to_date="2026-07-31")
		ledger = VatLedger.for_period(COMPANY, SEPTEMBER)
		self.assertIs(ledger.basis, PeriodBasis.POSTING_DATE)
		self.assertIn(voucher, self.vouchers(ledger.lines(SEPTEMBER)))
		self.assertNotIn(voucher, self.vouchers(ledger.lines(JULY)))

	def test_a_credit_note_counts_when_it_is_issued(self):
		voucher = self.invoice(
			"SINV-LD-0006",
			"2026-09-20",
			"2026-09-20 09:00:00",
			net="-100.00",
			tax="-19.00",
			to_date="2026-07-31",
			is_return=1,
		)
		ledger = VatLedger.for_period(COMPANY, SEPTEMBER)
		self.assertIn(voucher, self.vouchers(ledger.lines(SEPTEMBER)))

	def test_an_intra_community_delivery_keeps_the_date_of_its_invoice(self):
		self.assertIn("8125", accounts_by_invoice_date(COMPANY))
		voucher = self.invoice(
			"SINV-LD-0007",
			"2026-08-03",
			"2026-08-03 09:00:00",
			tax="0",
			to_date="2026-07-31",
			revenue="8125",
		)
		ledger = VatLedger.for_period(COMPANY, AUGUST)

		def revenue_of(period: Period) -> list[str]:
			return [line.voucher for line in ledger.lines(period) if line.account_number == "8125"]

		self.assertEqual(revenue_of(AUGUST), [voucher])
		self.assertEqual(revenue_of(JULY), [])

	def test_a_journal_entry_counts_on_its_posting_date(self):
		a = self.account
		ensure_fiscal_year(COMPANY, "2026-08-31")
		entry = post_journal_entry(
			COMPANY, "2026-08-31", [(a["1200"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)]
		)
		ledger = VatLedger.for_period(COMPANY, AUGUST)
		self.assertIn(f"Journal Entry:{entry.name}", self.vouchers(ledger.lines(AUGUST)))

	def test_a_year_is_the_sum_of_its_months(self):
		self.invoice("SINV-LD-0008", "2026-09-20", "2026-09-20 09:00:00", to_date="2026-07-31")
		self.invoice("SINV-LD-0009", "2026-07-20", "2026-07-20 09:00:00")
		ledger = VatLedger.for_year(COMPANY, 2026)
		months = [line for month in range(1, 13) for line in ledger.lines(Period.month(2026, month))]
		self.assertCountEqual(ledger.lines_between(date(2026, 1, 1), date(2026, 12, 31)), months)

	def test_a_filing_is_recorded_with_its_first_and_latest_time(self):
		self.file(JULY, "2026-08-10 12:00:00")
		(filing,) = filings(COMPANY, [2026])
		self.assertEqual(filing.period, JULY)
		self.assertEqual(
			(filing.first, filing.latest), (datetime(2026, 8, 10, 12), datetime(2026, 8, 10, 12))
		)

	def test_an_invoice_booked_after_the_filing_of_its_month_needs_a_corrected_return(self):
		self.file(JULY, "2026-08-10 12:00:00")
		voucher = self.invoice("SINV-LD-0010", "2026-09-20", "2026-09-20 09:00:00", to_date="2026-07-31")
		ledger = VatLedger.for_period(COMPANY, SEPTEMBER)
		(late,) = [placement for placement in ledger.late() if placement.booking.voucher == voucher]
		self.assertEqual((late.tax_period, late.period), (JULY, JULY))
		self.assertTrue(late.needs_correction)
		self.assertIn(voucher, self.vouchers(ledger.lines(JULY)))
		self.assertEqual(ledger.filed_before(SEPTEMBER), [JULY])

	def test_in_the_current_period_it_goes_to_the_month_open_when_it_was_booked(self):
		self.set_rule(late="Current Period")
		self.file(JULY, "2026-08-10 12:00:00")
		voucher = self.invoice("SINV-LD-0011", "2026-09-20", "2026-09-20 09:00:00", to_date="2026-07-31")
		ledger = VatLedger.for_period(COMPANY, SEPTEMBER)
		self.assertIn(voucher, self.vouchers(ledger.lines(AUGUST)))
		self.assertNotIn(voucher, self.vouchers(ledger.lines(JULY)))

	def test_load_lines_still_reads_by_posting_date(self):
		voucher = self.invoice("SINV-LD-0012", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31")
		self.assertIn(voucher, self.vouchers(load_lines(COMPANY, "2026-08-01", "2026-08-31")))
