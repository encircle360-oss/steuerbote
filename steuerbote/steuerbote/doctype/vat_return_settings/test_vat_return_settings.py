from decimal import Decimal

import frappe
from frappe.model.document import Document
from frappe.tests import IntegrationTestCase
from frappe.translate import clear_cache as clear_translation_cache

from steuerbote.ustva import Rhythm

# ERPNext's test records for Company expect its setup wizard, which the app's test site never runs.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company"]

COMPANY = "Steuerbote Test Einstellungen GmbH"
ABBR = "STBEIN"


def make_company(name: str, abbr: str) -> str:
	"""A company without chart of accounts and warehouses, which the settings do not need.

	ERPNext gives the default warehouses of a company the warehouse type "Transit", which only its
	setup wizard creates.
	"""
	if not frappe.db.exists("Company", name):
		ignore_chart_of_accounts = frappe.local.flags.ignore_chart_of_accounts
		frappe.local.flags.ignore_chart_of_accounts = True
		try:
			frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": name,
					"abbr": abbr,
					"default_currency": "EUR",
					"country": "Germany",
				}
			).insert()
		finally:
			frappe.local.flags.ignore_chart_of_accounts = ignore_chart_of_accounts
	return name


class IntegrationTestVATReturnSettings(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		make_company(COMPANY, ABBR)

	def setUp(self) -> None:
		super().setUp()
		frappe.delete_doc_if_exists("VAT Return Settings", COMPANY)

	def make_settings(self, **values: object) -> Document:
		return frappe.get_doc(
			{
				"doctype": "VAT Return Settings",
				"company": COMPANY,
				"state": "Bayern",
				"tax_number": "123/456/78901",
				**values,
			}
		)

	def test_derives_the_elster_tax_number_and_keeps_the_defaults(self):
		self.make_settings(elster_tax_number="0000000000000").insert()
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		self.assertEqual(settings.name, COMPANY)
		self.assertEqual(settings.elster_tax_number, "9123045678901")
		self.assertEqual(settings.chart, "SKR03")
		self.assertEqual(settings.taxation_type, "Soll")
		self.assertEqual(settings.tolerance, 0.01)

	def test_follows_a_new_tax_number(self):
		settings = self.make_settings().insert()
		settings.state = "Nordrhein-Westfalen"
		settings.tax_number = "123/4567/8901"
		settings.save()
		self.assertEqual(
			frappe.db.get_value("VAT Return Settings", COMPANY, "elster_tax_number"), "5123045678901"
		)

	def test_refuses_a_tax_number_of_another_shape(self):
		with self.assertRaisesRegex(frappe.ValidationError, "format FFF/BBB/UUUUP of Bayern"):
			self.make_settings(tax_number="12/345/67890").insert()
		self.assertFalse(frappe.db.exists("VAT Return Settings", COMPANY))

	def test_a_missing_tax_number_is_left_to_the_mandatory_check(self):
		with self.assertRaises(frappe.MandatoryError):
			self.make_settings(tax_number=None).insert()

	def test_looks_up_the_rules_of_the_saved_rows(self):
		self.make_settings(
			period_rules=[
				{"year": 2026, "rhythm": "monthly", "valid_from_month": 1},
				{"year": 2026, "rhythm": "quarterly", "valid_from_month": 7},
				{"year": 2028, "rhythm": "none", "valid_from_month": 1},
			],
			prepayments=[
				{"year": 2026, "dauerfristverlaengerung": 1, "sondervorauszahlung": 1234.56},
				{"year": 2027, "dauerfristverlaengerung": 0},
			],
		).insert()
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		self.assertIs(settings.rhythm_for(2025, 12), Rhythm.MONTHLY)
		self.assertIs(settings.rhythm_for(2026, 6), Rhythm.MONTHLY)
		self.assertIs(settings.rhythm_for(2026, 7), Rhythm.QUARTERLY)
		self.assertIs(settings.rhythm_for(2027, 3), Rhythm.QUARTERLY)
		with self.assertRaisesRegex(frappe.ValidationError, "No Voranmeldung is due for month 1 of 2028"):
			settings.rhythm_for(2028, 1)
		self.assertTrue(settings.has_dauerfrist(2026))
		self.assertFalse(settings.has_dauerfrist(2027))
		self.assertFalse(settings.has_dauerfrist(2028))
		self.assertEqual(settings.sondervorauszahlung(2026), Decimal("1234.56"))
		self.assertEqual(settings.sondervorauszahlung(2027), Decimal("0"))

	def test_sorts_the_period_rules(self):
		self.make_settings(
			period_rules=[
				{"year": 2026, "rhythm": "quarterly", "valid_from_month": 7},
				{"year": 2025, "rhythm": "quarterly", "valid_from_month": 1},
				{"year": 2026, "rhythm": "monthly", "valid_from_month": 1},
			]
		).insert()
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		self.assertEqual(
			[(row.idx, row.year, row.valid_from_month) for row in settings.period_rules],
			[(1, 2025, 1), (2, 2026, 1), (3, 2026, 7)],
		)

	def test_refuses_a_rule_that_does_not_start_a_quarter(self):
		with self.assertRaisesRegex(frappe.ValidationError, "1, 4, 7 or 10, not in month 5"):
			self.make_settings(
				period_rules=[{"year": 2026, "rhythm": "quarterly", "valid_from_month": 5}]
			).insert()

	def test_refuses_two_rules_with_the_same_start(self):
		with self.assertRaisesRegex(frappe.ValidationError, "of 2026 from month 7 is entered twice"):
			self.make_settings(
				period_rules=[
					{"year": 2026, "rhythm": "quarterly", "valid_from_month": 7},
					{"year": 2026, "rhythm": "monthly", "valid_from_month": 7},
				]
			).insert()

	def test_refuses_two_rows_for_the_same_year(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "Dauerfristverlängerung of 2026 is entered twice"
		):
			self.make_settings(
				prepayments=[
					{"year": 2026, "dauerfristverlaengerung": 1},
					{"year": 2026, "dauerfristverlaengerung": 0},
				]
			).insert()

	def test_frappe_reads_the_german_translations_of_the_app(self):
		clear_translation_cache()
		self.assertEqual(
			frappe._("VAT Return Settings", lang="de"), "Einstellungen Umsatzsteuer-Voranmeldung"
		)
		self.assertEqual(frappe._("Filing Period", lang="de"), "Voranmeldungszeitraum")

	def test_refuses_a_sondervorauszahlung_without_dauerfristverlaengerung(self):
		with self.assertRaisesRegex(frappe.ValidationError, "requires the Dauerfristverlängerung"):
			self.make_settings(
				prepayments=[{"year": 2026, "dauerfristverlaengerung": 0, "sondervorauszahlung": 500}]
			).insert()
