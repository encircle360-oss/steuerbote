"""A return for a period that has not ended is not ready, and a return whose Kz 41, 42 or 21 holds turnover tells
that the settings name no rhythm of the Zusammenfassende Meldung for its months (steuerbote/ustva/obligations.py)."""

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)

IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

COMPANY = "Steuerbote Test Pflichten GmbH"
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"8125": ("Steuerfreie innergemeinschaftliche Lieferungen", "Income"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}
NOTE = "Erfunden: abgegeben in Mein ELSTER."


class TestObligations(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STPF")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)
		ensure_fiscal_year(COMPANY, "2026-01-01")
		frappe.cache.delete_value("fiscal_years")

	def setUp(self):
		frappe.db.savepoint("obligations_test")
		self.addCleanup(frappe.db.rollback, save_point="obligations_test")

	def new_return(self, month: int, **fields):
		return frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": month,
				**fields,
			}
		).insert()

	def calculate(self, doc):
		doc.calculate()
		doc.reload()
		return doc

	def codes(self, doc) -> list[str]:
		return [row.code for row in doc.hints]

	def test_a_period_that_has_not_ended_is_not_ready_and_files_only_with_remarks(self):
		a = self.account
		post_journal_entry(
			COMPANY, "2026-11-10", [(a["1400"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)]
		)
		with self.freeze_time("2026-11-25 09:00:00"):
			doc = self.calculate(self.new_return(11))
			self.assertEqual((doc.status, doc.ready), ("Berechnet", 0))
			self.assertIn("ZEITRAUM-NICHT-ABGELAUFEN", self.codes(doc))
			with self.assertRaisesRegex(frappe.ValidationError, "November 2026"):
				doc.make_import_file()
			with self.assertRaisesRegex(frappe.ValidationError, "November 2026"):
				doc.mark_filed_outside(filed_via="mein_elster")
		with self.freeze_time("2026-12-01 09:00:00"):
			doc = self.calculate(frappe.get_doc("VAT Return", doc.name))
			self.assertEqual((doc.status, doc.ready), ("Bereit", 1))
			self.assertNotIn("ZEITRAUM-NICHT-ABGELAUFEN", self.codes(doc))

	def test_a_period_that_has_not_begun_is_not_ready_either(self):
		with self.freeze_time("2026-11-25 09:00:00"):
			doc = self.calculate(self.new_return(12))
			self.assertEqual(doc.status, "Berechnet")
			self.assertIn("ZEITRAUM-NICHT-ABGELAUFEN", self.codes(doc))

	def test_turnover_of_the_zm_without_its_rhythm_gets_a_warning(self):
		a = self.account
		post_journal_entry(COMPANY, "2026-09-10", [(a["1400"], 8000, 0), (a["8125"], 0, 8000)])
		doc = self.calculate(self.new_return(9))
		self.assertIn("ZM-OHNE-RHYTHMUS", self.codes(doc))
		self.assertEqual(doc.status, "Bereit")
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		settings.append("zm_rules", {"year": 2026, "valid_from_month": 7, "rhythm": "quarterly"})
		settings.save()
		doc = self.calculate(frappe.get_doc("VAT Return", doc.name))
		self.assertNotIn("ZM-OHNE-RHYTHMUS", self.codes(doc))

	def test_no_warning_on_the_zm_without_its_turnover(self):
		a = self.account
		post_journal_entry(
			COMPANY, "2026-08-10", [(a["1400"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)]
		)
		self.assertNotIn("ZM-OHNE-RHYTHMUS", self.codes(self.calculate(self.new_return(8))))

	def test_a_second_draft_of_an_open_period_names_the_first(self):
		first = self.new_return(5)
		frappe.clear_messages()
		second = self.new_return(5)
		self.assertIn(first.name, " ".join(str(message) for message in frappe.get_message_log()))
		self.assertTrue(second.name)

	def test_a_filed_return_is_not_cancellable_and_a_draft_has_nothing_to_cancel(self):
		a = self.account
		post_journal_entry(
			COMPANY, "2026-04-10", [(a["1400"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)]
		)
		doc = self.calculate(self.new_return(4))
		self.assertFalse(doc.cancellable())
		doc.mark_filed_outside(filed_via="mein_elster")
		self.assertFalse(frappe.get_doc("VAT Return", doc.name).cancellable())

	def test_a_corrected_return_names_what_it_adds_and_says_when_it_changes_nothing(self):
		a = self.account
		post_journal_entry(
			COMPANY, "2026-03-10", [(a["1400"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)]
		)
		filed = self.calculate(self.new_return(3))
		filed.mark_filed_outside(filed_via="mein_elster")
		unchanged = self.calculate(self.new_return(3, is_correction=1))
		self.assertIn("BERICHTIGUNG-OHNE-AENDERUNG", self.codes(unchanged))
		self.assertEqual(unchanged.late_changes, [])
		late = post_journal_entry(
			COMPANY, "2026-03-20", [(a["1400"], 238, 0), (a["8400"], 0, 200), (a["1776"], 0, 38)]
		)
		changed = self.calculate(frappe.get_doc("VAT Return", unchanged.name))
		self.assertNotIn("BERICHTIGUNG-OHNE-AENDERUNG", self.codes(changed))
		self.assertEqual(
			[(row.voucher_no, row.kind) for row in changed.late_changes], [(late.name, "Booked after Filing")]
		)
		self.assertIn("reported by this corrected return", changed.late_changes[0].message)
