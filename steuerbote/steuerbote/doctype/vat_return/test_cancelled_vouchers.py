"""A filing names the vouchers behind its deviations, hints and late changes. A voucher may be cancelled, amended or
deleted after Berechnen, with „Unveränderliches Hauptbuch aktivieren“ in the Accounts Settings or without it: the
return stays calculable and savable, and no row of a filing keeps a voucher from being cancelled or deleted."""

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.steuerbote.report.ustva_kennzahlen.ustva_kennzahlen import execute
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)

IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

COMPANY = "Steuerbote Test Stornierte Belege GmbH"
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
	"1200": ("Bank", "Asset"),
}
NOTE = "Erfunden: abgegeben in Mein ELSTER."
LEDGERS = {"without the immutable ledger": 0, "with the immutable ledger": 1}


def set_up_company() -> dict[str, str]:
	"""The company of both test cases, made by the first that runs; returns its accounts by number."""
	if not frappe.db.exists("Company", COMPANY):
		make_company(COMPANY, "STSB")
		for number, (name, root_type) in ACCOUNTS.items():
			make_account(COMPANY, number, name, root_type)
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)
	return {
		number: frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})
		for number in ACCOUNTS
	}


class TestCancelledVouchers(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.account = set_up_company()

	def setUp(self):
		frappe.db.savepoint("cancelled_vouchers_test")
		self.addCleanup(frappe.db.rollback, save_point="cancelled_vouchers_test")

	def deviating_entry(self, day: str):
		"""Umsatzsteuer without a base: a deviation of the Verprobung at 19 %, which names the entry."""
		a = self.account
		return post_journal_entry(COMPANY, day, [(a["1776"], 95, 0), (a["1200"], 0, 95)])

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

	def cancel(self, entry, immutable: int, day: str) -> None:
		with (
			self.change_settings("Accounts Settings", {"enable_immutable_ledger": immutable}),
			self.freeze_time(f"{day} 10:00:00"),
		):
			entry.reload()
			entry.cancel()

	def test_a_return_stays_calculable_after_the_voucher_of_a_deviation_is_cancelled(self):
		for (ledger, immutable), month in zip(LEDGERS.items(), (3, 4), strict=True):
			with self.subTest(ledger=ledger):
				entry = self.deviating_entry(f"2026-{month:02d}-10")
				doc = self.calculated(month)
				self.assertIn(entry.name, [row.voucher_no for row in doc.deviations])
				self.cancel(entry, immutable, f"2026-{month + 1:02d}-04")
				doc.calculate()
				doc.reload()
				self.assertIn(doc.status, ("Berechnet", "Bereit"))

	def test_a_draft_that_names_a_cancelled_voucher_still_saves(self):
		for (ledger, immutable), month in zip(LEDGERS.items(), (5, 6), strict=True):
			with self.subTest(ledger=ledger):
				entry = self.deviating_entry(f"2026-{month:02d}-10")
				doc = self.calculated(month)
				self.cancel(entry, immutable, f"2026-{month:02d}-20")
				doc.reload()
				doc.remarks = NOTE
				doc.save()
				self.assertIn(entry.name, [row.voucher_no for row in doc.deviations])

	def test_a_draft_that_names_a_deleted_voucher_still_saves_and_keeps_naming_it(self):
		entry = self.deviating_entry("2026-07-10")
		doc = self.calculated(7)
		self.cancel(entry, 0, "2026-07-20")
		frappe.delete_doc("Journal Entry", entry.name)
		doc.reload()
		doc.remarks = NOTE
		doc.save()
		self.assertIn(entry.name, [row.voucher_no for row in doc.deviations])

	def test_a_filed_return_keeps_no_voucher_of_its_rows_from_being_cancelled_or_deleted(self):
		for (ledger, immutable), month in zip(LEDGERS.items(), (8, 9), strict=True):
			with self.subTest(ledger=ledger):
				entry = self.deviating_entry(f"2026-{month:02d}-10")
				doc = self.calculated(month)
				doc.remarks = NOTE
				doc.save()
				doc.mark_filed_outside(NOTE)
				self.assertIn(entry.name, [row.voucher_no for row in doc.deviations])
				self.cancel(entry, immutable, f"2026-{month + 1:02d}-04")
				self.assertEqual(frappe.db.get_value("Journal Entry", entry.name, "docstatus"), 2)
				if not immutable:
					frappe.delete_doc("Journal Entry", entry.name)
					self.assertFalse(frappe.db.exists("Journal Entry", entry.name))

	def test_every_row_that_names_a_voucher_accepts_a_cancelled_or_missing_one(self):
		entry = self.deviating_entry("2026-10-10")
		self.cancel(entry, 0, "2026-10-20")
		for doctype in (
			"VAT Return Deviation",
			"VAT Return Hint",
			"VAT Return Late Change",
			"Recapitulative Statement Hint",
			"Recapitulative Statement Voucher",
		):
			for voucher_no in (entry.name, "ACC-JV-ERFUNDEN-0001"):
				with self.subTest(doctype=doctype, voucher_no=voucher_no):
					row = frappe.get_doc(
						{"doctype": doctype, "voucher_type": "Journal Entry", "voucher_no": voucher_no}
					)
					self.assertEqual(row.get_invalid_links(is_submittable=True), ([], []))
					self.assertEqual(row.voucher_no, voucher_no)

	def test_the_journal_entry_an_annual_filing_proposed_may_be_cancelled_or_gone(self):
		entry = self.deviating_entry("2026-10-12")
		self.cancel(entry, 0, "2026-10-21")
		for doctype, fieldname in (
			("Corporate Income Tax Return", "provisions_entry"),
			("Annual Accounts", "appropriation_entry"),
		):
			for voucher_no in (entry.name, "ACC-JV-ERFUNDEN-0002"):
				with self.subTest(doctype=doctype, voucher_no=voucher_no):
					filing = frappe.new_doc(doctype)
					filing.set(fieldname, voucher_no)
					invalid, cancelled = filing.get_invalid_links(is_submittable=True)
					self.assertEqual([link for link in (*invalid, *cancelled) if link[0] == fieldname], [])


class TestCancellationPeriod(IntegrationTestCase):
	"""A cancelled voucher was never a supply or an invoice of its period. Before that period is filed, its reversal
	takes it out of the period; after the filing, the cancellation is a change after the filing, which the setting
	„Belege für abgegebene Zeiträume“ sends to a corrected return or to the period open when it was made."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.account = set_up_company()

	def setUp(self):
		frappe.db.savepoint("cancellation_period_test")
		self.addCleanup(frappe.db.rollback, save_point="cancellation_period_test")

	def sale(self, day: str):
		a = self.account
		return post_journal_entry(
			COMPANY, day, [(a["1400"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)]
		)

	calculated = TestCancelledVouchers.calculated
	cancel = TestCancelledVouchers.cancel

	def kz81(self, doc) -> float:
		return next((row.amount for row in doc.kennzahlen if row.kennzahl == "81"), 0)

	def file(self, month: int) -> None:
		with self.freeze_time(f"2026-{month + 1:02d}-02 09:00:00"):
			doc = self.calculated(month)
			doc.remarks = NOTE
			doc.save()
			doc.mark_filed_outside(NOTE)

	def test_a_voucher_cancelled_before_its_month_is_filed_counts_in_neither_month(self):
		for (ledger, immutable), month in zip(LEDGERS.items(), (2, 4), strict=True):
			with self.subTest(ledger=ledger):
				entry = self.sale(f"2026-{month:02d}-10")
				self.cancel(entry, immutable, f"2026-{month + 1:02d}-04")
				self.assertEqual(self.kz81(self.calculated(month)), 0)
				self.assertEqual(self.kz81(self.calculated(month + 1)), 0)

	def test_after_the_filing_with_the_corrected_return_the_cancellation_asks_for_the_correction(self):
		for (ledger, immutable), month in zip(LEDGERS.items(), (6, 8), strict=True):
			with self.subTest(ledger=ledger):
				entry = self.sale(f"2026-{month:02d}-10")
				self.file(month)
				self.cancel(entry, immutable, f"2026-{month + 1:02d}-04")
				later = self.calculated(month + 1)
				self.assertEqual(self.kz81(later), 0)
				(row,) = [row for row in later.late_changes if row.voucher_no == entry.name]
				self.assertEqual(row.kind, "Cancelled after Filing")
				self.assertIn("Kz 10", row.message)

	def test_in_the_current_period_the_cancellation_after_the_filing_is_reported_there(self):
		frappe.db.set_value("VAT Return Settings", COMPANY, "late_documents", "Current Period")
		for (ledger, immutable), month in zip(LEDGERS.items(), (2, 4), strict=True):
			with self.subTest(ledger=ledger):
				entry = self.sale(f"2026-{month:02d}-10")
				self.file(month)
				self.cancel(entry, immutable, f"2026-{month + 1:02d}-04")
				later = self.calculated(month + 1)
				self.assertEqual(self.kz81(later), -100)
				(row,) = [row for row in later.late_changes if row.voucher_no == entry.name]
				self.assertEqual(row.kind, "Cancelled after Filing")
				_columns, rows = execute(
					{"company": COMPANY, "year": 2026, "rhythm": "monthly", "period_index": month + 1}
				)
				(shown,) = [
					row
					for row in rows
					if row.get("voucher_no") == entry.name and row.get("account") == self.account["8400"]
				]
				self.assertEqual((shown["print_link"], float(shown["amount"])), ("Cancelled voucher", -100.0))
