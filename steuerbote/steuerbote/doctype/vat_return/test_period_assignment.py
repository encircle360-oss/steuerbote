"""A VAT Return computes its period from the bookings the VAT Return Settings assign to it (steuerbote.vat_periods),
records the rule, and shows what changed after the filing of a period: on the return being prepared and on the
filed one."""

from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.steuerbote.report.ustva_kennzahlen.ustva_kennzahlen import execute
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_sales_invoice,
)
from steuerbote.tests.late_documents import ACCOUNTS, filed_return, sales_invoice, set_rule
from steuerbote.ustva import Period

IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

COMPANY = "Steuerbote Test Nachzügler GmbH"
JULY = Period.month(2026, 7)
SEPTEMBER = Period.month(2026, 9)


class TestPeriodAssignment(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STNZ")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)

	def setUp(self):
		frappe.db.savepoint("period_assignment_test")
		self.addCleanup(frappe.db.rollback, save_point="period_assignment_test")

	def invoice(self, name: str, posting: str, booked: str, **fields) -> str:
		return sales_invoice(COMPANY, self.account, name, posting, booked, **fields)

	def calculated(self, month: int):
		doc = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": month,
			}
		).insert()
		doc.calculate()
		doc.reload()
		return doc

	def amount(self, doc, kennzahl: str) -> Decimal:
		row = next((row for row in doc.kennzahlen if row.kennzahl == kennzahl), None)
		return Decimal(str(row.amount)) if row else Decimal(0)

	def test_the_month_of_the_supply_reports_an_invoice_written_later_and_the_return_records_the_rule(self):
		self.invoice("SINV-NZ-0001", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31")
		july = self.calculated(7)
		self.assertEqual(self.amount(july, "81"), Decimal("1000.00"))
		self.assertEqual((july.period_basis, july.late_treatment), ("By Service Date", "Corrected Return"))
		self.assertEqual(self.amount(self.calculated(8), "81"), Decimal(0))

	def test_by_posting_date_the_month_of_the_invoice_reports_it(self):
		set_rule(COMPANY, "By Posting Date")
		self.invoice("SINV-NZ-0002", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31")
		august = self.calculated(8)
		self.assertEqual(self.amount(august, "81"), Decimal("1000.00"))
		self.assertEqual(august.period_basis, "By Posting Date")

	def test_the_hints_set_the_invoice_against_the_month_of_its_supply(self):
		a = self.account
		post_sales_invoice(
			COMPANY,
			"SINV-NZ-0006",
			"Testkunde",
			"2026-08-03",
			[(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)],
			items=[(a["8400"], 1000)],
			taxes=[(a["1776"], 190)],
			to_date="2026-07-31",
		)
		codes = {row.code for row in self.calculated(7).hints} | {
			row.code for row in self.calculated(8).hints
		}
		self.assertNotIn("ABGLEICH-RECHNUNGEN", codes)

	def test_the_report_shows_the_invoice_in_the_month_of_its_supply(self):
		self.invoice("SINV-NZ-0003", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31")
		_columns, rows = execute({"company": COMPANY, "year": 2026, "rhythm": "monthly", "period_index": 7})
		self.assertIn("SINV-NZ-0003", {row.get("voucher_no") for row in rows})

	def test_a_late_invoice_asks_for_the_corrected_return_on_the_current_and_on_the_filed_return(self):
		july = filed_return(COMPANY, JULY, "2026-08-10 12:00:00")
		self.invoice("SINV-NZ-0004", "2026-09-20", "2026-09-20 09:00:00", to_date="2026-07-31")
		september = self.calculated(9)
		self.assertEqual(self.amount(september, "81"), Decimal(0))
		rows = [(row.period_label, row.kind, row.voucher_no) for row in september.late_changes]
		self.assertIn(("Juli 2026", "Booked after Filing", "SINV-NZ-0004"), rows)
		self.assertIn(("Juli 2026", "Changed since Filing", None), rows)
		changes = july.changes_since_filing()
		self.assertTrue(any(row["needs_correction"] for row in changes))
		self.assertIn("SINV-NZ-0004", {row["voucher_no"] for row in changes})

	def test_in_the_current_period_the_late_invoice_is_reported_in_the_month_being_prepared(self):
		set_rule(COMPANY, late="Current Period")
		july = filed_return(COMPANY, JULY, "2026-08-10 12:00:00")
		self.invoice("SINV-NZ-0005", "2026-09-05", "2026-09-05 09:00:00", to_date="2026-07-31")
		august = self.calculated(8)
		self.assertEqual(self.amount(august, "81"), Decimal("1000.00"))
		self.assertEqual(august.late_treatment, "Current Period")
		(row,) = august.late_changes
		self.assertEqual((row.period_label, row.voucher_no), ("Juli 2026", "SINV-NZ-0005"))
		changes = july.changes_since_filing()
		self.assertEqual([row["voucher_no"] for row in changes], ["SINV-NZ-0005"])
		self.assertFalse(changes[0]["needs_correction"])

	def test_a_filed_return_makes_its_corrected_return_once(self):
		july = filed_return(COMPANY, JULY, "2026-08-10 12:00:00")
		name = july.make_correction()
		correction = frappe.get_doc("VAT Return", name)
		self.assertEqual((correction.is_correction, correction.period_index, correction.docstatus), (1, 7, 0))
		self.assertEqual(july.make_correction(), name)

	def test_only_a_filed_return_makes_a_corrected_return(self):
		with self.assertRaises(frappe.ValidationError):
			self.calculated(10).make_correction()
