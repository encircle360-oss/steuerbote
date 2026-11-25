"""Berechnen warns where a voucher books Vorsteuer at another rate than its purchase account names
(steuerbote/ustva/input_tax.py); the warning never holds the return."""

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

COMPANY = "Steuerbote Test Vorsteuer GmbH"
ACCOUNTS = {
	"3300": ("Wareneingang 7 % Vorsteuer", "Expense"),
	"3400": ("Wareneingang 19 % Vorsteuer", "Expense"),
	"1571": ("Abziehbare Vorsteuer 7 %", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1600": ("Verbindlichkeiten aus Lieferungen und Leistungen", "Liability"),
}


class TestInputTaxHints(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STVS")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)
		a = cls.account
		cls.wrong = post_journal_entry(
			COMPANY, "2026-06-15", [(a["3300"], 1000, 0), (a["1576"], 190, 0), (a["1600"], 0, 1190)]
		)
		cls.right = post_journal_entry(
			COMPANY, "2026-06-16", [(a["3400"], 1000, 0), (a["1576"], 190, 0), (a["1600"], 0, 1190)]
		)

	def test_warns_of_19_percent_input_tax_on_a_7_percent_purchase_and_files_it_as_booked(self):
		doc = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": 6,
			}
		).insert()
		doc.calculate()
		doc.reload()
		warnings = [row for row in doc.hints if row.code == "VORSTEUER-ABWEICHUNG"]
		self.assertEqual(
			[(row.voucher_type, row.voucher_no, row.severity) for row in warnings],
			[("Journal Entry", self.wrong.name, "Warnung")],
		)
		self.assertIn("3300 (7 % Vorsteuer)", warnings[0].text)
		self.assertEqual(next(row.amount for row in doc.kennzahlen if row.kennzahl == "66"), 380)
		self.assertEqual(doc.status, "Bereit")
