"""Anlage GK line 11 and KSt 1 F lines 17 and 18 of the Körperschaftsteuererklärung from the E-Bilanz, on the Frappe
test site with the invented company of steuerbote/tests/annual_integration.py and the HGB-Taxonomie 6.9 installed: the
E-Bilanz a new return names and Berechnen takes, line 11 of an Einheitsbilanz and of a Handelsbilanz with its
Überleitung, the books that changed since the E-Bilanz was calculated, an E-Bilanz of another kind refused, the
Gewerbesteuererklärung on the Körperschaftsteuer of the return, and the Steuerbilanz of the E-Bilanz filed for the
previous year in KSt 1 F. Every name, number and amount is invented.
"""

from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.tests import annual_integration as data
from steuerbote.tests.annual_integration import (
	CORPORATE,
	EBILANZ,
	TRADE,
	blocking_codes,
	calculated,
	finding_codes,
	line,
	money,
)
from steuerbote.tests.ebilanz import configured, taxonomy_root

DIFFERS = "KST-EBILANZ-ABWEICHUNG"
SOURCE = "KST-EIGENKAPITAL-QUELLE"


def d(value: str) -> Decimal:
	return Decimal(value)


def values(doc, *fields: str) -> dict[str, Decimal]:
	return {field: money(doc.get(field)) for field in fields}


class TestIncomeTaxFromEBilanz(IntegrationTestCase):
	"""One class, so that the company and its books are made once; each test takes out its documents and postings."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.enterClassContext(configured(taxonomy_root()))
		cls.account = data.make_company_with_books()

	def setUp(self):
		super().setUp()
		self.addCleanup(data.discard)

	def test_berechnen_takes_line_11_from_the_e_bilanz_of_the_year_and_names_it(self):
		ebilanz = calculated(EBILANZ)
		self.assertEqual(money(ebilanz.net_income), d("59490.00"))
		doc = data.new_document(CORPORATE)
		self.assertEqual(doc.electronic_balance_sheet, ebilanz.name)
		doc.calculate()
		doc.reload()
		self.assertEqual(doc.electronic_balance_sheet, ebilanz.name)
		self.assertEqual(
			values(doc, "net_income", "zve", "kst", "solz"),
			{
				"net_income": d("59490.00"),
				"zve": d("78040.00"),
				"kst": d("11706.00"),
				"solz": d("643.83"),
			},
		)
		row = line(doc, "E8002001")
		self.assertEqual((money(row.ledger_amount), money(row.form_amount)), (d("59490.00"), d("59490.00")))
		self.assertNotIn(DIFFERS, finding_codes(doc))

	def test_without_a_calculated_e_bilanz_line_11_is_the_jahresueberschuss_of_the_books(self):
		data.new_document(EBILANZ)
		doc = calculated(CORPORATE)
		self.assertFalse(doc.electronic_balance_sheet)
		self.assertEqual(
			values(doc, "net_income", "zve"), {"net_income": d("59490.00"), "zve": d("78040.00")}
		)

	def test_postings_since_the_e_bilanz_hold_the_return_back_until_it_is_calculated_again(self):
		"""The provisions loop: posting the provisions lowers the Jahresüberschuss of the books, so the E-Bilanz is
		calculated again before the return, and the zu versteuerndes Einkommen stays."""
		ebilanz = calculated(EBILANZ)
		doc = calculated(CORPORATE)
		before = values(doc, "zve", "kst", "solz", "kst_balance", "solz_balance")
		data.submitted_provisions(doc)
		doc.reload()
		doc.calculate()
		doc.reload()
		self.assertIn(DIFFERS, blocking_codes(doc))
		ebilanz.reload()
		ebilanz.calculate()
		ebilanz.reload()
		self.assertEqual(money(ebilanz.net_income), d("54770.17"))
		doc.reload()
		doc.calculate()
		doc.reload()
		self.assertNotIn(DIFFERS, finding_codes(doc))
		self.assertEqual(values(doc, *before), before)
		self.assertEqual(money(doc.net_income), d("54770.00"))

	def test_a_handelsbilanz_gives_line_11_its_ueberleitung_to_the_steuerbilanz(self):
		"""§ 5b Abs. 1 Satz 2 EStG; § 5 Abs. 4a EStG keeps the Rückstellung für drohende Verluste out of the
		Steuerbilanz, so the zu versteuerndes Einkommen is that of the books without it."""
		data.post_drohverlust(self, self.account)
		ebilanz = calculated(EBILANZ, accounting_standard="HGBM", tax_finance_book=data.TAX_BOOK)
		self.assertEqual(
			values(ebilanz, "net_income", "tax_net_income"),
			{"net_income": d("57490.00"), "tax_net_income": d("59490.00")},
		)
		doc = calculated(CORPORATE)
		row = line(doc, "E8002001")
		self.assertEqual((money(row.ledger_amount), money(row.form_amount)), (d("57490.00"), d("59490.00")))
		self.assertEqual(
			values(doc, "net_income", "zve"), {"net_income": d("59490.00"), "zve": d("78040.00")}
		)
		self.assertFalse(
			{DIFFERS, "KST-UEBERLEITUNG-FEHLT", "KST-UEBERLEITUNG-DOPPELT"} & set(finding_codes(doc))
		)

	def test_the_gewerbesteuererklaerung_computes_on_the_e_bilanz_of_the_koerperschaftsteuererklaerung(self):
		data.post_drohverlust(self, self.account)
		calculated(EBILANZ, accounting_standard="HGBM", tax_finance_book=data.TAX_BOOK)
		calculated(CORPORATE)
		trade = calculated(TRADE)
		self.assertEqual(
			values(trade, "profit", "gewerbeertrag", "messbetrag", "gewst", "balance"),
			{
				"profit": d("78040.00"),
				"gewerbeertrag": d("78000.00"),
				"messbetrag": d("2730.00"),
				"gewst": d("10920.00"),
				"balance": d("2920.00"),
			},
		)

	def test_an_eroeffnungsbilanz_is_no_e_bilanz_of_line_11(self):
		opening = data.new_document(EBILANZ, statement_type="Eröffnungsbilanz")
		with self.assertRaisesRegex(frappe.ValidationError, "takes the E-Bilanz of the Jahresabschluss"):
			data.new_document(CORPORATE, electronic_balance_sheet=opening.name)

	def test_kst_1_f_takes_the_steuerbilanz_of_the_e_bilanz_filed_for_the_previous_year(self):
		filed = data.filed_ebilanz_of_2025(self, "45000.40", "25000")
		doc = calculated(CORPORATE, previous_equity=40000, previous_nominal_capital=25000)
		self.assertEqual(
			(money(line(doc, "E8201001").form_amount), money(line(doc, "E8201101").form_amount)),
			(d("45000.00"), d("25000.00")),
		)
		(finding,) = (row for row in doc.findings if row.code == SOURCE)
		self.assertEqual(finding.blocking, 0)
		self.assertIn(filed, finding.text)
