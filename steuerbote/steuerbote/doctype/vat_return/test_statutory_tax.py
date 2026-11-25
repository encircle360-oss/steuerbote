"""The setting „Steuer zu Umsätzen mit festem Steuersatz“ of the VAT Return Settings on a VAT Return: Berechnen records
it, Kz 83, the print format, the file for Mein ELSTER and the report UStVA Kennzahlen follow it, and the tax of a
base goes with the base into the period the settings assign it to. The amounts are invented."""

import html
import re
from decimal import Decimal
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import ustjahr_sources
from steuerbote.patches import set_the_tax_on_turnover_at_a_statutory_rate as patch
from steuerbote.steuerbote.doctype.vat_return.vat_return import mapping_for
from steuerbote.steuerbote.report.ustva_kennzahlen.ustva_kennzahlen import execute
from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	make_account,
	make_company,
	make_mapping,
	make_settings,
)
from steuerbote.tests.late_documents import ACCOUNTS, sales_invoice
from steuerbote.ustva import Period, StatutoryTax

IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

COMPANY = "Steuerbote Test Steuer wie gebucht GmbH"
SETTINGS = "VAT Return Settings"
FROM_BASE = "From the Base in Full Euros"
AS_BOOKED = "As Booked"
PRINT_FORMAT = "Umsatzsteuer-Voranmeldung"


def money(value) -> Decimal:
	return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def cells(markup: str) -> str:
	"""The printed text with every table cell closed by " |", so that a line of the form reads as one string."""
	text = re.sub(r"<(style|script)\b.*?</\1>", " ", markup, flags=re.DOTALL | re.IGNORECASE)
	text = re.sub(r"</t[dh]>", " |", text)
	text = re.sub(r"<br\s*/?>", " ", text)
	text = re.sub(r"<[^>]+>", " ", text)
	return re.sub(r"\s+", " ", html.unescape(text))


class TestStatutoryTax(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STWG")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(
			COMPANY,
			[(2026, "monthly", 1)],
			street="Hauptstraße 1",
			postal_code="80331",
			city="München",
		)
		make_mapping(COMPANY)
		ensure_fiscal_year(COMPANY, "2026-01-01")
		frappe.cache.delete_value("fiscal_years")

	def setUp(self):
		frappe.db.savepoint("statutory_tax_test")
		self.addCleanup(frappe.db.rollback, save_point="statutory_tax_test")

	def choose(self, value: str) -> None:
		frappe.db.set_value(SETTINGS, COMPANY, "statutory_tax", value)

	def three_invoices(self, month: int) -> None:
		"""Three invoices of 33.33 euros with 6.33 euros of tax each: Kz 81 of 99 euros, 18.99 euros booked."""
		for number in (1, 2, 3):
			day = f"2026-{month:02d}-1{number}"
			sales_invoice(
				COMPANY, self.account, f"SINV-WG-{month}{number}", day, f"{day} 09:00:00", "33.33", "6.33"
			)

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

	def row(self, doc, kennzahl: str):
		return next(row for row in doc.kennzahlen if row.kennzahl == kennzahl)

	def printed(self, doc) -> str:
		return cells(frappe.get_print("VAT Return", doc.name, print_format=PRINT_FORMAT, no_letterhead=1))

	def test_new_settings_take_the_tax_of_the_form(self):
		self.assertEqual(frappe.db.get_value(SETTINGS, COMPANY, "statutory_tax"), FROM_BASE)

	def test_the_patch_gives_settings_without_the_setting_the_default_and_keeps_a_choice(self):
		frappe.db.set_value(SETTINGS, COMPANY, "statutory_tax", "")
		patch.execute()
		self.assertEqual(frappe.db.get_value(SETTINGS, COMPANY, "statutory_tax"), FROM_BASE)
		self.choose(AS_BOOKED)
		patch.execute()
		self.assertEqual(frappe.db.get_value(SETTINGS, COMPANY, "statutory_tax"), AS_BOOKED)

	def test_from_the_base_kz83_holds_the_tax_of_the_form(self):
		self.three_invoices(3)
		doc = self.calculated(3)
		self.assertEqual(doc.statutory_tax, FROM_BASE)
		self.assertEqual(
			(money(self.row(doc, "81").reported), money(self.row(doc, "81").tax)), (99, money(18.81))
		)
		self.assertEqual(money(doc.kz83), money(18.81))
		self.assertIn(
			"13 | Steuerpflichtige Umsätze zum Steuersatz von 19 % | 81 | 99 | | 18,81 |", self.printed(doc)
		)

	def test_as_booked_kz83_is_the_balance_of_the_tax_account(self):
		self.choose(AS_BOOKED)
		self.three_invoices(3)
		doc = self.calculated(3)
		self.assertEqual(doc.statutory_tax, AS_BOOKED)
		self.assertEqual(
			(money(self.row(doc, "81").reported), money(self.row(doc, "81").tax)), (99, money(18.99))
		)
		self.assertEqual((money(doc.output_tax), money(doc.kz83)), (money(18.99), money(18.99)))
		self.assertEqual(money(self.row(doc, "83").final), money(18.99))
		self.assertIn(
			"13 | Steuerpflichtige Umsätze zum Steuersatz von 19 % | 81 | 99 | | 18,99 |", self.printed(doc)
		)
		url = doc.make_import_file()
		content = Path(frappe.get_doc("File", {"file_url": url}).get_full_path()).read_bytes()
		self.assertIn(b"<Kz81>99</Kz81>", content)
		self.assertIn(b"<Kz83>18.99</Kz83>", content)

	def test_the_return_keeps_its_setting_until_it_is_calculated_again(self):
		self.choose(AS_BOOKED)
		self.three_invoices(3)
		doc = self.calculated(3)
		self.choose(FROM_BASE)
		doc.remarks = "Erfunden."
		doc.save()
		doc.reload()
		self.assertEqual((doc.statutory_tax, money(doc.kz83)), (AS_BOOKED, money(18.99)))
		doc.calculate()
		doc.reload()
		self.assertEqual((doc.statutory_tax, money(doc.kz83)), (FROM_BASE, money(18.81)))

	def test_an_overridden_base_takes_the_tax_of_the_form(self):
		self.choose(AS_BOOKED)
		self.three_invoices(3)
		doc = self.calculated(3)
		row = self.row(doc, "81")
		row.override = 100
		row.override_reason = "Erfunden: Rechnung im April gebucht."
		doc.save()
		doc.reload()
		self.assertEqual(money(doc.kz83), money(19.00))

	def test_the_tax_of_a_base_below_one_euro_goes_with_it_into_the_month_of_the_supply(self):
		self.choose(AS_BOOKED)
		sales_invoice(
			COMPANY,
			self.account,
			"SINV-WG-CENT",
			"2026-05-04",
			"2026-05-04 09:00:00",
			"0.80",
			"0.15",
			to_date="2026-04-30",
		)
		april = self.calculated(4)
		self.assertEqual(
			(money(self.row(april, "81").reported), money(self.row(april, "81").tax)), (0, money(0.15))
		)
		self.assertEqual(money(april.kz83), money(0.15))
		may = self.calculated(5)
		self.assertEqual([row.kennzahl for row in may.kennzahlen], ["83"])
		self.assertEqual(money(may.kz83), 0)

	def test_the_report_sums_the_tax_as_the_return_does(self):
		self.three_invoices(3)
		for value, expected in ((FROM_BASE, 18.81), (AS_BOOKED, 18.99)):
			self.choose(value)
			_columns, rows = execute(
				{"company": COMPANY, "year": 2026, "rhythm": "monthly", "period_index": 3}
			)
			line_37 = next(row for row in rows if row.get("line") == 37 and row.get("kennzahl") is None)
			with self.subTest(value=value):
				self.assertEqual(money(line_37["reported"]), money(expected))

	def test_the_runs_of_the_annual_return_take_the_tax_of_the_setting(self):
		self.three_invoices(3)
		march = Period.month(2026, 3)
		for setting, expected in ((StatutoryTax.FROM_BASE, 18.81), (StatutoryTax.AS_BOOKED, 18.99)):
			runs = ustjahr_sources.period_runs(
				COMPANY, [march], mapping_for(COMPANY, 2026), Decimal("0.01"), setting
			)
			with self.subTest(setting=setting):
				self.assertEqual(money(runs[march].kz83), money(expected))
