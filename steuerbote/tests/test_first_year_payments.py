"""The first year of a company in Steuerbote, on a site: what the report UStVA Kennzahlen says about the watched accounts,
and the payments of the new year that belong to the Voranmeldungen filed before Steuerbote (steuerbote/setup/start.py).

The company kept its books with a tax adviser until the end of 2025 and starts in ERPNext on 1 January 2026 with opening
entries, 1.900 € of them on „Vorsteuer in Folgeperiode/im Folgejahr abziehbar“, which January releases and February
fills anew. Its Voranmeldungen for November and December 2025 were filed before Steuerbote; it pays them in January and
February 2026 on the account of the Vorauszahlungen, beside the Sondervorauszahlung 2026 on its own account. The company,
its accounts and every amount are invented."""

from datetime import date

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.setup import start
from steuerbote.steuerbote import setup
from steuerbote.steuerbote.report.ustva_kennzahlen.ustva_kennzahlen import execute
from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)

COMPANY = "Steuerbote Test Zahlungen vor Steuerbote GmbH"
ABBR = "STZV"
ACCOUNTS = {
	"1548": ("Vorsteuer in Folgeperiode/im Folgejahr abziehbar", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1780": ("Umsatzsteuer-Vorauszahlungen", "Liability"),
	"1781": ("Umsatzsteuer-Vorauszahlungen 1/11", "Liability"),
	"1790": ("Umsatzsteuer Vorjahr", "Liability"),
	"1200": ("Bank", "Asset"),
	"0800": ("Gezeichnetes Kapital", "Equity"),
	"8400": ("Erlöse 19 % USt", "Income"),
}
ADDRESS = {
	"street": "Musterweg",
	"house_number": "12",
	"postal_code": "80331",
	"city": "München",
	"country": "Germany",
}
ANNUAL = "Annual VAT Return"


def prior_filing(month: int, kz83: int, kz39: int = 0, filed_on: str = "2026-01-10") -> str:
	doc = frappe.get_doc(
		{
			"doctype": "VAT Return Prior Filing",
			"company": COMPANY,
			"year": 2025,
			"rhythm": "monthly",
			"period_index": month,
			"filed_on": filed_on,
			"kz83": kz83,
			"kz39": kz39,
			"source_document": "Übermittlungsprotokoll der Steuerberatung",
			"reason": "Vor dem Start der Bücher in ERPNext abgegeben",
		}
	).insert()
	doc.submit()
	return doc.name


def notes(month: int) -> list[str]:
	_columns, rows = execute({"company": COMPANY, "year": 2026, "rhythm": "monthly", "period_index": month})
	return [
		row["label"]
		for row in rows
		if not row["indent"] and row.get("kennzahl") is None and row.get("line") is None
	]


class FirstYearPaymentsTest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for year in (2025, 2026):
			ensure_fiscal_year(COMPANY, date(year, 6, 30))
		make_company(COMPANY, ABBR)
		a = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(
			COMPANY, [(2026, "monthly", 1)], [(2026, True, "2681.00")], books_start=date(2026, 1, 1)
		)
		make_mapping(COMPANY)
		frappe.get_doc(
			{"doctype": "Annual Filing Settings", "company": COMPANY, "legal_form": "GmbH", **ADDRESS}
		).insert(ignore_permissions=True)
		post_journal_entry(
			COMPANY,
			"2026-01-01",
			[(a["1200"], 30000, 0), (a["1548"], 1900, 0), (a["1790"], 0, 6900), (a["0800"], 0, 25000)],
			is_opening="Yes",
		)
		post_journal_entry(COMPANY, "2026-01-15", [(a["1576"], 1900, 0), (a["1548"], 0, 1900)])
		post_journal_entry(COMPANY, "2026-02-20", [(a["1548"], 500, 0), (a["1200"], 0, 500)])
		cls.november = prior_filing(11, 900, filed_on="2025-12-10")
		cls.december = prior_filing(12, 1200, 2500, filed_on="2026-02-10")
		cls.paid_november = post_journal_entry(
			COMPANY, "2026-01-12", [(a["1780"], 900, 0), (a["1200"], 0, 900)]
		)
		cls.paid_december = post_journal_entry(
			COMPANY, "2026-02-10", [(a["1780"], 1200, 0), (a["1200"], 0, 1200)]
		)
		post_journal_entry(COMPANY, "2026-02-10", [(a["1781"], 2681, 0), (a["1200"], 0, 2681)])

	def tearDown(self):
		for name in frappe.get_all(ANNUAL, filters={"company": COMPANY}, pluck="name"):
			frappe.delete_doc(ANNUAL, name, force=True, ignore_permissions=True)

	def test_the_report_says_what_the_return_says_of_a_release(self):
		"""January releases the Vorsteuer carried in: the return is ready, and the report names the release, not a
		block."""
		found = notes(1)
		self.assertTrue(any(text.startswith("Konto 1548 ") and "des Saldos auf" in text for text in found))
		self.assertFalse(any("Sperrt" in text for text in found))

	def test_the_report_names_an_account_that_holds_the_return_back(self):
		found = notes(2)
		self.assertTrue(any(text.startswith("Konto 1548 ") and "„Sperrt“" in text for text in found))

	def test_payments_of_the_returns_filed_before_are_no_vorauszahlungen_of_the_year(self):
		"""Without them the ledger shows the 2.681 € of the Sondervorauszahlung, the Vorauszahlungssoll of a year
		without a Voranmeldung filed through Steuerbote: no hint on the payments."""
		doc = frappe.get_doc({"doctype": ANNUAL, "company": COMPANY, "year": 2026}).insert()
		doc.calculate()
		doc.reload()
		codes = [row.code for row in doc.findings]
		self.assertNotIn("ZAHLUNGEN", codes)
		named = [row.text for row in doc.findings if row.code == "SB-ZAHLUNG-VOR-START"]
		self.assertEqual(len(named), 2)
		self.assertTrue(any(self.paid_november.name in text and self.november in text for text in named))
		self.assertTrue(any(self.paid_december.name in text and self.december in text for text in named))

	def test_the_setup_names_them_in_its_checklist(self):
		result = setup.check_books_start(setup.SetupContext(COMPANY, date(2026, 3, 1), None, {}))
		(note,) = (note for note in result.notes if note.template == start.PRIOR_PAYMENTS_FOUND)
		self.assertTrue(note.open)
		self.assertIn(self.paid_november.name, note.values[0])
		self.assertIn(self.paid_december.name, note.values[0])
