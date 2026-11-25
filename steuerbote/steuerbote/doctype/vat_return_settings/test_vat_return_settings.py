from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.model.document import Document
from frappe.tests import IntegrationTestCase
from frappe.translate import clear_cache as clear_translation_cache

from steuerbote.tests.helpers import insert_record, make_user
from steuerbote.ustva import Rhythm
from steuerbote.zm.rhythm import Rhythm as ZmRhythm
from steuerbote.zm.rhythm import Rule as ZmRule

# ERPNext's test records for Company expect its setup wizard, which the app's test site never runs.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company"]

COMPANY = "Steuerbote Test Einstellungen GmbH"
ABBR = "STBEIN"
# Has a phone, an email and a primary address with a phone and an email of its own, all invented.
CONTACT_COMPANY = "Steuerbote Test Datenlieferant GmbH"
CONTACT = {"phone_no": "089 7654321", "email": "steuern@example.org"}
ACCOUNTANT = "steuerbote-einstellungen-buchhaltung@example.com"
MANAGER = "steuerbote-einstellungen-leitung@example.com"


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
		make_company(CONTACT_COMPANY, "STBDL")
		frappe.db.set_value("Company", CONTACT_COMPANY, CONTACT)
		# Saving an address renders it with the default Address Template, which only the setup wizard makes, so
		# the address is written as ERPNext keeps it.
		address = insert_record(
			"Address",
			name=f"{CONTACT_COMPANY}-Billing",
			address_title=CONTACT_COMPANY,
			address_type="Billing",
			address_line1="Musterstraße 12",
			pincode="80331",
			city="München",
			country="Germany",
			phone="089 1111111",
			email_id="zentrale@example.org",
			is_primary_address=1,
			is_your_company_address=1,
		)
		insert_record(
			"Dynamic Link",
			name=f"{address}-Link",
			parent=address,
			parenttype="Address",
			parentfield="links",
			idx=1,
			link_doctype="Company",
			link_name=CONTACT_COMPANY,
		)

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
				"period_rules": [{"year": 2026, "rhythm": "monthly", "valid_from_month": 1}],
				**values,
			}
		)

	def test_refuses_a_steuernummer_whose_check_digit_eric_refuses(self):
		"""EricPruefeSteuernummer of the installed ERiC (steuerbote.eric.service.steuernummer_valid); without a runtime
		it cannot say, and the settings are saved."""
		adapter = "steuerbote.steuerbote.doctype.vat_return.transmission_adapter.steuernummer_valid"
		with (
			patch(adapter, return_value=False) as checked,
			self.assertRaisesRegex(frappe.ValidationError, "ERiC refuses the Steuernummer 123/456/78901"),
		):
			self.make_settings().insert()
		checked.assert_called_once_with("9123045678901")
		with patch(adapter, return_value=None):
			self.make_settings().insert()
		with patch(adapter, return_value=False) as checked:
			frappe.get_doc("VAT Return Settings", COMPANY).save()
		checked.assert_not_called()

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
		with self.assertRaisesRegex(frappe.ValidationError, "No filing period is set for month 12 of 2025"):
			settings.rhythm_for(2025, 12)
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

	def test_keeps_the_datenlieferant_and_the_wid_nr_as_elster_takes_it(self):
		self.make_settings(
			filer_name="Beispiel GmbH",
			street="Hauptstraße 1",
			postal_code="80331",
			city="München",
			phone="089 1234567",
			email="erika@example.org",
			wid_nr="de 123456788",
		).insert()
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		self.assertEqual(
			(settings.filer_name, settings.street, settings.postal_code, settings.city),
			("Beispiel GmbH", "Hauptstraße 1", "80331", "München"),
		)
		self.assertEqual(
			(settings.phone, settings.email, settings.wid_nr),
			("089 1234567", "erika@example.org", "DE123456788"),
		)

	def contact_settings(self, **values: object) -> Document:
		settings = self.make_settings(company=CONTACT_COMPANY, **values).insert()
		self.addCleanup(frappe.delete_doc, "VAT Return Settings", settings.name)
		return settings

	def test_an_empty_datenlieferant_comes_from_the_company_and_its_address(self):
		"""The DatenLieferant of the file for ELSTER holds name, street, postal code, town, phone and email
		(Jahresdokumentation UStVA 2026, sheet "Anmeldungssteuern - Felder")."""
		settings = self.contact_settings()
		self.assertEqual(
			(
				settings.filer_name,
				settings.street,
				settings.postal_code,
				settings.city,
				settings.phone,
				settings.email,
			),
			(CONTACT_COMPANY, "Musterstraße 12", "80331", "München", "089 7654321", "steuern@example.org"),
		)

	def test_what_the_user_entered_stays_and_an_emptied_field_is_filled_again(self):
		settings = self.contact_settings(filer_name="Beispiel Holding", street="Postfach 10 20 30")
		self.assertEqual(
			(settings.filer_name, settings.street, settings.city),
			("Beispiel Holding", "Postfach 10 20 30", "München"),
		)
		settings.city = ""
		settings.save()
		self.assertEqual(frappe.db.get_value("VAT Return Settings", CONTACT_COMPANY, "city"), "München")

	def test_phone_and_email_come_from_the_address_when_the_company_has_none(self):
		frappe.db.set_value("Company", CONTACT_COMPANY, {"phone_no": None, "email": None})
		self.addCleanup(frappe.db.set_value, "Company", CONTACT_COMPANY, CONTACT)
		settings = self.contact_settings()
		self.assertEqual((settings.phone, settings.email), ("089 1111111", "zentrale@example.org"))

	def test_without_an_address_only_the_name_comes_from_the_company(self):
		settings = self.make_settings().insert()
		self.assertEqual(
			(settings.filer_name, settings.street, settings.postal_code, settings.city),
			(COMPANY, None, None, None),
		)

	def test_refuses_a_wid_nr_of_another_shape(self):
		with self.assertRaisesRegex(frappe.ValidationError, "is not a Wirtschafts-Identifikationsnummer"):
			self.make_settings(wid_nr="DE12345678").insert()

	def test_refuses_a_datenlieferant_that_elster_does_not_take(self):
		with self.assertRaisesRegex(frappe.ValidationError, "town of the Datenlieferant contains characters"):
			self.make_settings(city="Łódź").insert()
		with self.assertRaisesRegex(frappe.ValidationError, "has 31 characters, ELSTER takes at most 30"):
			self.make_settings(street="x" * 31).insert()
		self.assertFalse(frappe.db.exists("VAT Return Settings", COMPANY))

	def test_takes_the_ust_idnr_from_the_tax_id_of_the_company_when_it_is_one(self):
		frappe.db.set_value("Company", COMPANY, "tax_id", "de 987 654 328")
		try:
			self.assertEqual(self.make_settings().insert().ust_idnr, "DE987654328")
			frappe.delete_doc("VAT Return Settings", COMPANY)
			self.assertEqual(self.make_settings(ust_idnr="DE123456788").insert().ust_idnr, "DE123456788")
			frappe.delete_doc("VAT Return Settings", COMPANY)
			frappe.db.set_value("Company", COMPANY, "tax_id", "DE987654321")
			self.assertIsNone(self.make_settings().insert().ust_idnr)
			frappe.delete_doc("VAT Return Settings", COMPANY)
			frappe.db.set_value("Company", COMPANY, "tax_id", "123/456/78901")
			self.assertIsNone(self.make_settings().insert().ust_idnr)
		finally:
			frappe.db.set_value("Company", COMPANY, "tax_id", None)

	def test_refuses_an_ust_idnr_that_is_not_german(self):
		with self.assertRaisesRegex(frappe.ValidationError, r"ATU12345678 is not a German USt-IdNr\."):
			self.make_settings(ust_idnr="ATU12345678").insert()

	def test_refuses_an_ust_idnr_or_a_w_idnr_with_a_wrong_check_digit(self):
		"""ERiC refuses them in the ZM and the Voranmeldung (validation with ERiC 44.3.6.0)."""
		with self.assertRaisesRegex(frappe.ValidationError, r"DE123456789 is not a valid German USt-IdNr\."):
			self.make_settings(ust_idnr="DE123456789").insert()
		with self.assertRaisesRegex(frappe.ValidationError, r"W-IdNr\. DE123456789 is not valid"):
			self.make_settings(wid_nr="DE123456789").insert()

	def test_the_teilnehmernummer_of_the_zm_is_optional_and_one_the_bzst_assigns(self):
		"""Jahresdokumentation ZMDO 2, rule 170015024: seven or eight digits from 0300000 on; without one the ZM
		writes 1111111, „da das BZSt keine neuen Teilnehmernummern vergibt“."""
		self.assertIsNone(self.make_settings().insert().teilnehmernummer)
		frappe.delete_doc("VAT Return Settings", COMPANY)
		self.assertEqual(
			self.make_settings(teilnehmernummer=" 0300 000 ").insert().teilnehmernummer, "0300000"
		)
		frappe.delete_doc("VAT Return Settings", COMPANY)
		for number in ("0299999", "123456", "12a4567"):
			with (
				self.subTest(number=number),
				self.assertRaisesRegex(
					frappe.ValidationError, f"{number} is not a Teilnehmernummer of the BZSt"
				),
			):
				self.make_settings(teilnehmernummer=number).insert()

	def test_sorts_and_reads_the_rhythm_of_the_zusammenfassende_meldung(self):
		self.make_settings(
			zm_rules=[
				{"year": 2026, "valid_from_month": 5, "rhythm": "monthly", "services_monthly": 1},
				{"year": 2026, "valid_from_month": 1, "rhythm": "quarterly", "reason": "Unter 50.000 Euro"},
			]
		).insert()
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		self.assertEqual(
			[(row.idx, row.valid_from_month, row.rhythm) for row in settings.zm_rules],
			[(1, 1, "quarterly"), (2, 5, "monthly")],
		)
		self.assertEqual(
			settings.get_zm_rules(),
			[
				ZmRule(2026, 1, ZmRhythm.QUARTERLY),
				ZmRule(2026, 5, ZmRhythm.MONTHLY, services_monthly=True),
			],
		)

	def test_refuses_a_rhythm_of_the_zusammenfassende_meldung_the_core_refuses(self):
		for rules, message in (
			([{"year": 2026, "valid_from_month": 5, "rhythm": "quarterly"}], "in month 1, 4, 7 or 10"),
			(
				[{"year": 2026, "valid_from_month": 1, "rhythm": "quarterly", "services_monthly": 1}],
				"only when it is filed monthly",
			),
			(
				[
					{"year": 2026, "valid_from_month": 1, "rhythm": "yearly"},
					{"year": 2026, "valid_from_month": 7, "rhythm": "monthly"},
				],
				"covers the calendar year 2026",
			),
		):
			with self.subTest(message=message), self.assertRaisesRegex(frappe.ValidationError, message):
				self.make_settings(zm_rules=rules).insert()

	def test_an_accounts_user_reads_the_settings_and_an_accounts_manager_changes_them(self):
		"""Steuernummer, rhythm, Sondervorauszahlung and tolerance of the Verprobung decide what is filed and with
		which Finanzamt, so only who may file a return may change them."""
		self.make_settings().insert()
		for user, role, may_change in (
			(ACCOUNTANT, "Accounts User", False),
			(MANAGER, "Accounts Manager", True),
		):
			make_user(user, role)
			with self.subTest(role=role), self.set_user(user):
				self.assertTrue(frappe.has_permission("VAT Return Settings", "read", COMPANY))
				settings = frappe.get_doc("VAT Return Settings", COMPANY)
				settings.tolerance = 100
				if may_change:
					settings.save()
				else:
					with self.assertRaises(frappe.PermissionError):
						settings.save()
				self.assertEqual(frappe.has_permission("VAT Return Settings", "create"), may_change)
