"""steuerbote/annual_accounts_sources.py on the Frappe test site, with the invented Kleinstkapitalgesellschaft of
steuerbote/tests/annual_accounts.py and the HGB-Taxonomie 6.9: the books of the fiscal year and of the year before on
the positions of the Handelsbilanz, with the earlier result on the closing account, the hierarchy of the taxonomy, and
the settings, the mapping, the name and the founding of the company."""

from datetime import date
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import annual_accounts_sources
from steuerbote.steuerbote.annual_filing import fiscal_year_ending_in
from steuerbote.tests import annual_accounts as data
from steuerbote.tests.annual_accounts import KLEINST
from steuerbote.tests.helpers import make_company

WITHOUT_SETTINGS = "Steuerbote Test Jahresabschluss ohne Einstellungen GmbH"
BANK = "bs.ass.currAss.cashEquiv.bank"
CARRIED_FORWARD = "bs.eqLiab.equity.retainedEarnings"


class TestAnnualAccountsSources(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.enterClassContext(data.installed_taxonomy())
		cls.accounts = data.make_company_with_books(KLEINST)
		make_company(WITHOUT_SETTINGS, "STJO")

	def test_reads_the_books_of_the_year_and_of_the_year_before_on_their_positions(self):
		fiscal_year = fiscal_year_ending_in(KLEINST.name, data.YEAR).name
		sources = annual_accounts_sources.statement_sources(KLEINST.name, fiscal_year)
		current = {balance.concept: (balance.amount, balance.source) for balance in sources.balances}
		self.assertEqual(current[BANK], (Decimal("38100.00"), self.accounts["1200"]))
		self.assertEqual(current[CARRIED_FORWARD], (Decimal("-12100.00"), self.accounts["0860"]))
		self.assertEqual(sum((balance.amount for balance in sources.balances), Decimal(0)), Decimal(0))
		prior = {balance.concept: balance.amount for balance in sources.prior}
		self.assertEqual((prior[BANK], prior.get(CARRIED_FORWARD)), (Decimal("37100.00"), None))
		self.assertEqual(sources.prior_dates, (date(2025, 1, 1), date(2025, 12, 31)))
		self.assertEqual(sources.parents[BANK], "bs.ass.currAss.cashEquiv")
		self.assertEqual([finding.code for finding in sources.findings], ["BILANZ-ERGEBNISVORTRAG"])
		self.assertEqual((sources.chart, sources.closing_account), ("SKR03", data.CLOSING_ACCOUNT))

	def test_a_company_needs_its_settings_and_its_mapping(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Enter the Annual Filing Settings of"):
			annual_accounts_sources.settings(WITHOUT_SETTINGS)
		with self.assertRaisesRegex(frappe.ValidationError, "has no Balance Sheet Mapping"):
			annual_accounts_sources.mapping(WITHOUT_SETTINGS)
		self.assertEqual(annual_accounts_sources.mapping(KLEINST.name).chart, "SKR03")

	def test_names_the_company_and_the_year_it_was_founded_in(self):
		self.assertEqual(annual_accounts_sources.company_name(KLEINST.name), KLEINST.name)
		self.assertFalse(annual_accounts_sources.founded_in(KLEINST.name, "2026-01-01", "2026-12-31"))
		frappe.db.set_value("Company", KLEINST.name, "date_of_establishment", "2026-02-01")
		self.addCleanup(frappe.db.set_value, "Company", KLEINST.name, "date_of_establishment", None)
		self.assertTrue(annual_accounts_sources.founded_in(KLEINST.name, "2026-01-01", "2026-12-31"))
		self.assertEqual(annual_accounts_sources.founded_on(KLEINST.name), date(2026, 2, 1))
