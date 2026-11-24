"""One year of the annual filings of the invented company of steuerbote/tests/annual_integration.py, on the Frappe test
site with the HGB-Taxonomie 6.9 installed, in the order of work docs/jahresmeldungen.md gives the year: the provisions
from a first Körperschaftsteuererklärung, the Jahresabschluss festgestellt with them, the E-Bilanz compared with it,
the Körperschaftsteuererklärung on the E-Bilanz with the zu versteuerndes Einkommen it had, the
Gewerbesteuererklärung on it and the Umsatzsteuererklärung against the Umsatzerlöse, with Offene Fristen listing every
annual kind of the year and marking those filed; and the year whose Jahresabschluss is festgestellt before the
provisions, which the E-Bilanz finds until the amended Jahresabschluss is festgestellt again. Every name, number and
amount is invented.
"""

from decimal import Decimal

from frappe.tests import IntegrationTestCase

from steuerbote.deadlines.annual import KINDS
from steuerbote.steuerbote.report.offene_fristen.offene_fristen import execute
from steuerbote.tests import annual_integration as data
from steuerbote.tests.annual_integration import (
	AFTER_ADOPTION,
	COMPANY,
	CORPORATE,
	EBILANZ,
	FILED_NOTE,
	REMARKS,
	TRADE,
	VAT,
	blocking_codes,
	calculated,
	finding_codes,
	line,
	money,
)
from steuerbote.tests.ebilanz import configured, taxonomy_root

COMPARED = ("SB-JA-ABWEICHUNG", "SB-JA-FEHLT")
HORIZON = 365
"""Days from AFTER_ADOPTION to the end of 2027, which take in the Offenlegung of the Jahresabschluss 2026."""
TAXES = ("zve", "kst", "solz", "kst_balance", "solz_balance")


def d(value: str) -> Decimal:
	return Decimal(value)


def values(doc, *fields: str) -> dict[str, Decimal]:
	return {field: money(doc.get(field)) for field in fields}


def compared(doc) -> list[str]:
	return [code for code in finding_codes(doc) if code in COMPARED]


class TestAnnualYear(IntegrationTestCase):
	"""One class, so that the company and its books are made once; each test takes out its documents and postings."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.enterClassContext(configured(taxonomy_root()))
		cls.account = data.make_company_with_books()

	def setUp(self):
		super().setUp()
		self.addCleanup(data.discard)

	def deadlines(self) -> dict[str, str]:
		"""The status of each annual deadline of 2026 Offene Fristen lists on AFTER_ADOPTION, by its kind."""
		with self.freeze_time(AFTER_ADOPTION):
			_columns, rows = execute({"company": COMPANY, "horizon": HORIZON})
		annual = {kind.value for kind in KINDS}
		return {
			row["kind"]: row["status"]
			for row in rows
			if row["kind"] in annual and row["period_label"] == "2026"
		}

	def test_the_year_in_the_order_of_its_work(self):
		self.assertEqual(self.deadlines(), dict.fromkeys((kind.value for kind in KINDS), "Fehlt"))
		corporate = calculated(CORPORATE, remarks=REMARKS)
		first = values(corporate, *TAXES)
		self.assertEqual(
			first,
			{
				"zve": d("78040.00"),
				"kst": d("11706.00"),
				"solz": d("643.83"),
				"kst_balance": d("1706.00"),
				"solz_balance": d("93.83"),
			},
		)
		data.submitted_provisions(corporate)
		with self.freeze_time(AFTER_ADOPTION):
			accounts = data.festgestellt()
		self.assertEqual(
			(money(accounts.net_income), money(accounts.umsatzerloese)), (d("54770.17"), d("200000.00"))
		)
		ebilanz = calculated(EBILANZ, remarks=REMARKS)
		self.assertEqual((ebilanz.annual_accounts, compared(ebilanz)), (accounts.name, []))
		self.assertEqual(money(ebilanz.net_income), d("54770.17"))
		corporate.reload()
		corporate.calculate()
		corporate.reload()
		self.assertEqual(corporate.electronic_balance_sheet, ebilanz.name)
		self.assertEqual(values(corporate, *TAXES), first)
		self.assertEqual(money(line(corporate, "E8002001").form_amount), d("54770.00"))
		self.assertNotIn("KST-EBILANZ-ABWEICHUNG", finding_codes(corporate))
		trade = calculated(TRADE)
		self.assertEqual(
			values(trade, "profit", "gewst", "balance"),
			{"profit": d("78040.00"), "gewst": d("10920.00"), "balance": d("2920.00")},
		)
		vat = calculated(VAT)
		self.assertNotIn("SB-UMSATZERLOESE", finding_codes(vat))
		with self.freeze_time(AFTER_ADOPTION):
			ebilanz.mark_filed_outside(note=FILED_NOTE)
			corporate.reload()
			corporate.mark_filed_outside(filed_via="mein_elster")
		self.assertEqual(
			self.deadlines(),
			{
				"Umsatzsteuererklärung": "Offen",
				"Körperschaftsteuererklärung": "Abgegeben",
				"Gewerbesteuererklärung": "Offen",
				"E-Bilanz": "Abgegeben",
				"Feststellung Jahresabschluss": "Abgegeben",
				"Offenlegung Jahresabschluss": "Offen",
			},
		)

	def test_a_jahresabschluss_festgestellt_before_the_provisions_holds_the_e_bilanz_back(self):
		corporate = calculated(CORPORATE, remarks=REMARKS)
		with self.freeze_time(AFTER_ADOPTION):
			accounts = data.festgestellt()
		data.submitted_provisions(corporate)
		ebilanz = calculated(EBILANZ)
		self.assertEqual(blocking_codes(ebilanz).count("SB-JA-ABWEICHUNG"), 1)
		(found,) = (row for row in ebilanz.findings if row.code == "SB-JA-ABWEICHUNG")
		self.assertEqual(found.reference, "is.netIncome")
		self.assertTrue(
			found.text.startswith(
				"Jahresüberschuss/Jahresfehlbetrag [is.netIncome] beträgt in der E-Bilanz 54.770,17 €, im "
				f"festgestellten Jahresabschluss {accounts.name} 59.490,00 €: ein Unterschied von -4.719,83 €."
			)
		)
		with self.freeze_time(AFTER_ADOPTION):
			accounts.cancel()
			amendment = data.amended(accounts)
		ebilanz.reload()
		ebilanz.calculate()
		ebilanz.reload()
		self.assertEqual((ebilanz.annual_accounts, compared(ebilanz)), (amendment.name, []))
