"""The VAT Return, the Zusammenfassende Meldung and the Dauerfristverlängerung are numbered by the year they are
for: a form USt 1 H for 2027 is made in November 2026, a Voranmeldung for December in the January after it."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from steuerbote.tests.helpers import ensure_fiscal_year, make_company, make_settings

# Files the Voranmeldung and the Zusammenfassende Meldung monthly from January 2026.
COMPANY = "Steuerbote Test Nummernkreis GmbH"


class NamingTest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STNK")
		make_settings(
			COMPANY,
			[(2026, "monthly", 1)],
			zm_rules=[{"year": 2026, "valid_from_month": 1, "rhythm": "monthly", "services_monthly": 1}],
		)

	def test_a_document_made_in_2026_for_2027_carries_2027(self):
		with self.freeze_time("2026-11-20 10:00:00"):
			statement = frappe.get_doc(
				{
					"doctype": "Recapitulative Statement",
					"company": COMPANY,
					"year": 2027,
					"period_kind": "month",
					"period_index": 1,
				}
			).insert()
			extension = frappe.get_doc(
				{"doctype": "VAT Return Extension", "company": COMPANY, "year": 2027}
			).insert()
		self.assertRegex(statement.name, r"^ZM-2027-\d{5}$")
		self.assertRegex(extension.name, r"^DFV-2027-\d{5}$")
		self.assertEqual([getdate(doc.creation).year for doc in (statement, extension)], [2026, 2026])

	def test_the_voranmeldung_for_december_made_in_january_carries_its_year(self):
		with self.freeze_time("2027-01-15 10:00:00"):
			vat_return = frappe.get_doc(
				{
					"doctype": "VAT Return",
					"company": COMPANY,
					"year": 2026,
					"rhythm": "monthly",
					"period_index": 12,
				}
			).insert()
		self.assertRegex(vat_return.name, r"^UStVA-2026-\d{5}$")
		self.assertEqual(getdate(vat_return.creation).year, 2027)

	def test_the_umsatzsteuererklaerung_for_2026_made_in_2027_carries_2026(self):
		ensure_fiscal_year(COMPANY, "2026-06-30")
		with self.freeze_time("2027-03-01 10:00:00"):
			annual = frappe.get_doc(
				{"doctype": "Annual VAT Return", "company": COMPANY, "year": 2026}
			).insert()
		self.assertRegex(annual.name, r"^UStE-2026-\d{5}$")
		self.assertEqual(getdate(annual.creation).year, 2027)

	def test_the_koerperschaft_and_gewerbesteuererklaerung_for_2026_made_in_2027_carry_2026(self):
		ensure_fiscal_year(COMPANY, "2026-06-30")
		with self.freeze_time("2027-03-01 10:00:00"):
			corporate = frappe.get_doc(
				{"doctype": "Corporate Income Tax Return", "company": COMPANY, "year": 2026}
			).insert()
			trade = frappe.get_doc({"doctype": "Trade Tax Return", "company": COMPANY, "year": 2026}).insert()
		self.assertRegex(corporate.name, r"^KSt-2026-\d{5}$")
		self.assertRegex(trade.name, r"^GewSt-2026-\d{5}$")
		self.assertEqual(trade.corporate_income_tax_return, corporate.name)
		self.assertEqual([getdate(doc.creation).year for doc in (corporate, trade)], [2027, 2027])

	def test_the_jahresabschluss_for_2026_made_in_2027_carries_2026(self):
		ensure_fiscal_year(COMPANY, "2026-06-30")
		with self.freeze_time("2027-03-01 10:00:00"):
			accounts = frappe.get_doc(
				{"doctype": "Annual Accounts", "company": COMPANY, "year": 2026}
			).insert()
		self.assertRegex(accounts.name, r"^JA-2026-\d{5}$")
		self.assertEqual(getdate(accounts.creation).year, 2027)
