"""The Handelsbilanz of the E-Bilanz against the Jahresabschluss of its year, on the Frappe test site with the invented
company of steuerbote/tests/annual_integration.py and the HGB-Taxonomie 6.9 installed: the Jahresabschluss a new
E-Bilanz names and lists among its connections, books that agree with it, a posting after the Feststellung, a
Jahresabschluss not festgestellt or not calculated, a Handelsbilanz whose Überleitung is no difference, and a
Jahresabschluss cancelled after Berechnen, before and after the E-Bilanz is filed. Every name, number and amount is
invented.
"""

from decimal import Decimal

import frappe
from frappe.desk.notifications import get_open_count
from frappe.tests import IntegrationTestCase

from steuerbote.tests import annual_integration as data
from steuerbote.tests.annual_integration import (
	ABBR,
	ACCOUNTS_DOCTYPE,
	AFTER_ADOPTION,
	EBILANZ,
	FILED_NOTE,
	calculated,
	money,
)
from steuerbote.tests.ebilanz import configured, taxonomy_root

DIFFERS = "SB-JA-ABWEICHUNG"
MISSING = "SB-JA-FEHLT"
LATE_RENT = (("6310", "1000", 0), ("1800", 0, "1000"))
"""Rent of 1,000 euros posted after the Jahresabschluss: Summe Aktiva and Jahresüberschuss are 1,000 euros less."""
REMARKS = "Mit der Steuerberatung abgestimmt: Die Handelsbilanz ist die des Jahresabschlusses."


def d(value: str) -> Decimal:
	return Decimal(value)


def compared(doc) -> list[tuple[str, str, int]]:
	"""The findings of the comparison: code, position or Jahresabschluss, and whether it holds the E-Bilanz back."""
	return [(row.code, row.reference, row.blocking) for row in doc.findings if row.code in (DIFFERS, MISSING)]


class TestEBilanzAndAnnualAccounts(IntegrationTestCase):
	"""One class, so that the company and its books are made once; each test takes out its documents and postings."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.enterClassContext(configured(taxonomy_root()))
		cls.account = data.make_company_with_books()

	def setUp(self):
		super().setUp()
		self.addCleanup(data.discard)

	def festgestellt(self):
		with self.freeze_time(AFTER_ADOPTION):
			return data.festgestellt()

	def post_late_rent(self) -> None:
		data.post_for_the_test(self, self.account, f"JV-{ABBR}-MIETE-NACHTRAG", "2026-12-31", LATE_RENT)

	def test_a_new_e_bilanz_names_the_festgestellten_jahresabschluss_whose_books_it_reads(self):
		accounts = self.festgestellt()
		ebilanz = data.new_document(EBILANZ)
		self.assertEqual(ebilanz.annual_accounts, accounts.name)
		ebilanz.calculate()
		ebilanz.reload()
		self.assertEqual(ebilanz.annual_accounts, accounts.name)
		self.assertEqual(
			(money(ebilanz.total_assets), money(ebilanz.net_income)), (d("104490.00"), d("59490.00"))
		)
		self.assertEqual(compared(ebilanz), [])

	def test_the_jahresabschluss_lists_the_e_bilanzen_that_name_it_among_its_connections(self):
		accounts = calculated(ACCOUNTS_DOCTYPE)
		ebilanz = data.new_document(EBILANZ)
		dashboard = frappe.get_meta(ACCOUNTS_DOCTYPE).get_dashboard_data()
		self.assertEqual(dashboard.fieldname, "annual_accounts")
		self.assertEqual([group["items"] for group in dashboard.transactions], [[EBILANZ]])
		(links,) = (
			links
			for links in get_open_count(ACCOUNTS_DOCTYPE, accounts.name)["count"]["external_links_found"]
			if links["doctype"] == EBILANZ
		)
		self.assertEqual((links["count"], ebilanz.annual_accounts), (1, accounts.name))

	def test_a_posting_after_the_feststellung_holds_the_e_bilanz_back(self):
		accounts = self.festgestellt()
		self.post_late_rent()
		ebilanz = calculated(EBILANZ)
		self.assertEqual(compared(ebilanz), [(DIFFERS, "bs.ass", 1), (DIFFERS, "is.netIncome", 1)])
		self.assertEqual((ebilanz.ready, ebilanz.status), (0, "Berechnet"))
		(total, _net_income) = (row.text for row in ebilanz.findings if row.code == DIFFERS)
		self.assertTrue(
			total.startswith(
				f"Summe Aktiva [bs.ass] beträgt in der E-Bilanz 103.490,00 €, im festgestellten Jahresabschluss "
				f"{accounts.name} 104.490,00 €: ein Unterschied von -1.000,00 €."
			)
		)

	def test_a_jahresabschluss_not_festgestellt_that_differs_gives_a_hint(self):
		accounts = calculated(ACCOUNTS_DOCTYPE)
		self.post_late_rent()
		ebilanz = calculated(EBILANZ)
		self.assertEqual(ebilanz.annual_accounts, accounts.name)
		self.assertEqual(compared(ebilanz), [(DIFFERS, "bs.ass", 0), (DIFFERS, "is.netIncome", 0)])

	def test_a_jahresabschluss_not_calculated_gives_a_hint_and_none_gives_nothing(self):
		ebilanz = calculated(EBILANZ)
		self.assertFalse(ebilanz.annual_accounts)
		self.assertEqual(compared(ebilanz), [])
		accounts = data.new_document(ACCOUNTS_DOCTYPE)
		ebilanz.calculate()
		ebilanz.reload()
		self.assertEqual(ebilanz.annual_accounts, accounts.name)
		self.assertEqual(compared(ebilanz), [(MISSING, accounts.name, 0)])

	def test_a_handelsbilanz_is_compared_before_its_ueberleitung(self):
		"""The Rückstellung für drohende Verluste counts in the Handelsbilanz and in the Jahresabschluss alike; the
		Überleitung that takes it out of the Steuerbilanz (§ 5 Abs. 4a EStG) is no difference."""
		data.post_drohverlust(self, self.account)
		self.festgestellt()
		ebilanz = calculated(EBILANZ, accounting_standard="HGBM", tax_finance_book=data.TAX_BOOK)
		self.assertEqual(
			(money(ebilanz.net_income), money(ebilanz.tax_net_income)), (d("57490.00"), d("59490.00"))
		)
		self.assertEqual(compared(ebilanz), [])

	def test_a_handelsbilanz_names_each_position_that_differs(self):
		self.festgestellt()
		self.post_late_rent()
		ebilanz = calculated(EBILANZ, accounting_standard="HGBM", tax_finance_book=data.TAX_BOOK)
		self.assertEqual(
			compared(ebilanz),
			[
				(DIFFERS, "bs.ass.currAss", 1),
				(DIFFERS, "bs.eqLiab.equity", 1),
				(DIFFERS, "bs.ass", 1),
				(DIFFERS, "bs.eqLiab", 1),
				(DIFFERS, "is.netIncome", 1),
			],
		)

	def test_a_jahresabschluss_cancelled_since_berechnen_holds_the_filing_back(self):
		accounts = self.festgestellt()
		ebilanz = calculated(EBILANZ, remarks=REMARKS)
		accounts.cancel()
		ebilanz.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "was cancelled since Berechnen compared"):
			ebilanz.check_fit_for_filing()
		ebilanz.calculate()
		ebilanz.reload()
		self.assertFalse(ebilanz.annual_accounts)
		self.assertEqual(compared(ebilanz), [])
		ebilanz.check_fit_for_filing()

	def test_a_filed_e_bilanz_holds_no_cancellation_of_its_jahresabschluss_back(self):
		accounts = self.festgestellt()
		ebilanz = calculated(EBILANZ, remarks=REMARKS)
		with self.freeze_time(AFTER_ADOPTION):
			ebilanz.mark_filed_outside(note=FILED_NOTE)
			accounts.cancel()
		self.assertEqual(frappe.db.get_value(ACCOUNTS_DOCTYPE, accounts.name, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value(EBILANZ, ebilanz.name, "annual_accounts"), accounts.name)
		ebilanz.reload()
		correction = frappe.get_doc(EBILANZ, ebilanz.make_correction())
		self.assertFalse(correction.annual_accounts)
