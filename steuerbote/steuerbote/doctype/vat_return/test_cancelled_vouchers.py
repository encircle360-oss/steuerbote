"""A filing names the vouchers behind its deviations, hints and late changes. A voucher may be cancelled, amended or
deleted after Berechnen, with „Unveränderliches Hauptbuch aktivieren“ in the Accounts Settings or without it: the
return stays calculable and savable, and no row of a filing keeps a voucher from being cancelled or deleted."""

import frappe
from frappe.tests import IntegrationTestCase

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


class TestCancelledVouchers(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STSB")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)

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
