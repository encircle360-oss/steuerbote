from datetime import date
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.client import get as client_get
from frappe.model.document import Document
from frappe.tests import IntegrationTestCase
from frappe.translate import clear_cache as clear_translation_cache

from steuerbote.steuerbote.doctype.annual_filing_settings import annual_filing_settings as settings_module
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import (
	CarryForwardKind,
	ShareholderKind,
	SizeClass,
	Tax,
)
from steuerbote.tests.helpers import make_account, make_company, make_settings, make_user

# ERPNext's test records for Company and Account expect its setup wizard, which the app's test site never runs.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "Country", "Finance Book"]

COMPANY = "Steuerbote Test Jahresmeldungen GmbH"
# Has no VAT Return Settings.
OTHER_COMPANY = "Steuerbote Test Jahresmeldungen ohne Einstellungen GmbH"
ACCOUNTANT = "steuerbote-jahresmeldungen-buchhaltung@example.com"
MANAGER = "steuerbote-jahresmeldungen-leitung@example.com"
# Invented: the first ten digits of an Identifikationsnummer repeat one digit, these repeat none.
IDNR = "12345678903"
WID_NR = "DE123456789"
AGS = "09162000"


def shareholder(name: str = "Erika Mustermann", percent: float = 100, **values: object) -> dict:
	return {
		"shareholder_name": name,
		"kind": ShareholderKind.NATURAL_PERSON.value,
		"percent": percent,
		"nominal_amount": 25000 * percent / 100,
		"from_date": "2026-01-01",
		"street": "Musterweg 1",
		"postal_code_and_town": "80331 München",
		**values,
	}


class IntegrationTestAnnualFilingSettings(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		make_company(COMPANY, "STJM")
		make_company(OTHER_COMPANY, "STJO")
		make_settings(
			COMPANY, [(2026, "monthly", 1)], street="Musterstraße 12a", postal_code="80331", city="München"
		)
		cls.retained_earnings = make_account(COMPANY, "0860", "Gewinnvortrag vor Verwendung", "Equity")
		cls.bank = make_account(COMPANY, "1200", "Bank", "Asset")
		cls.other_equity = make_account(OTHER_COMPANY, "0860", "Gewinnvortrag vor Verwendung", "Equity")

	def setUp(self) -> None:
		super().setUp()
		for company in (COMPANY, OTHER_COMPANY):
			frappe.delete_doc_if_exists("Annual Filing Settings", company)

	def make(self, company: str = COMPANY, **values: object) -> Document:
		return frappe.get_doc(
			{"doctype": "Annual Filing Settings", "company": company, "legal_form": "GmbH", **values}
		)

	def test_one_document_per_company_named_after_it(self):
		settings = self.make().insert()
		self.assertEqual(settings.name, COMPANY)
		self.assertEqual(
			(settings.country, settings.accounting_standard, settings.kleinst_mode),
			("Germany", "HAOE", "Hinterlegung"),
		)
		with self.assertRaises(frappe.DuplicateEntryError):
			self.make().insert()

	def test_the_legal_form_gives_the_rechtsform_of_the_erklaerungen_and_the_legal_status_of_the_gcd(self):
		with self.assertRaises(frappe.MandatoryError):
			self.make(legal_form=None).insert()
		gmbh = self.make().insert()
		self.assertEqual((gmbh.rechtsform(), gmbh.legal_status()), ("350", "GMBH"))
		ug = self.make(company=OTHER_COMPANY, legal_form="UG").insert()
		self.assertEqual(
			(ug.rechtsform(), ug.legal_status(), ug.legal_status(disclosure=True)), ("370", "UG", "GMBH")
		)

	def test_the_steuernummer_for_kst_and_gewst_takes_the_format_of_the_vat_return_settings(self):
		settings = self.make().insert()
		self.assertIsNone(settings.elster_income_tax_number)
		self.assertEqual(settings.elster_tax_number(), "9123045678901")
		settings.income_tax_number = " 123/456/78902 "
		settings.save()
		self.assertEqual(
			(settings.income_tax_number, settings.elster_income_tax_number),
			("123/456/78902", "9123045678902"),
		)
		self.assertEqual(settings.elster_tax_number(), "9123045678902")
		settings.income_tax_number = "12/345/67890"
		with self.assertRaisesRegex(frappe.ValidationError, "format FFF/BBB/UUUUP of Bayern"):
			settings.save()

	def test_a_steuernummer_for_kst_and_gewst_needs_the_bundesland_of_the_vat_return_settings(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "takes the format of the Bundesland of the VAT Return"
		):
			self.make(company=OTHER_COMPANY, income_tax_number="123/456/78902").insert()

	def test_take_address_proposes_the_street_of_the_vat_return_settings_split_at_its_last_digits(self):
		settings = self.make()
		settings.fill_address()
		self.assertEqual(
			(
				settings.street,
				settings.house_number,
				settings.house_number_suffix,
				settings.postal_code,
				settings.city,
			),
			("Musterstraße", "12", "a", "80331", "München"),
		)
		self.assertFalse(frappe.db.exists("Annual Filing Settings", COMPANY))
		settings.insert()
		self.assertEqual(settings.get_address().street_line, "Musterstraße 12a")

	def test_take_address_needs_vat_return_settings_unless_asked_quietly(self):
		settings = self.make(company=OTHER_COMPANY)
		with self.assertRaisesRegex(
			frappe.ValidationError, "has no VAT Return Settings to take the address from"
		):
			settings.fill_address()
		settings.fill_address(quiet=True)
		self.assertIsNone(settings.street)
		with self.assertRaisesRegex(frappe.ValidationError, "Select the company first"):
			self.make(company=None).fill_address()

	def test_refuses_an_address_the_forms_would_not_take(self):
		for values, message in (
			({"street": "Musterweg", "house_number": "12a"}, "12a is not a house number"),
			({"postal_code": "8033"}, "8033 is not a German postal code"),
			({"street": "x" * 26, "house_number": "1234"}, "make 31 characters; the Vorsatz"),
			({"city": "Łódź"}, "Town contains characters ELSTER does not take"),
			({"business_purpose": "x" * 26}, "Business Purpose has 26 characters; ELSTER takes at most 25"),
			({"advisor_street": "y" * 56}, "has 56 characters; ELSTER takes at most 55"),
		):
			with self.subTest(values=values), self.assertRaisesRegex(frappe.ValidationError, message):
				self.make(**values).insert()
		address = self.make(postal_code="A-1010", city="Wien", country="Austria").insert().get_address()
		self.assertFalse(address.in_germany)

	def test_the_register_comes_from_the_company_where_erpnext_germany_adds_it(self):
		self.assertEqual(settings_module.company_register(COMPANY), {})
		register = {
			"register_court": "Amtsgericht Musterstadt",
			"register_type": "HRB",
			"register_number": "12345",
		}
		with patch.object(settings_module, "company_register", return_value=register):
			settings = self.make(register_number="HRB 999").insert()
		self.assertEqual(
			(settings.register_court, settings.register_type, settings.register_number),
			("Amtsgericht Musterstadt", "HRB", "HRB 999"),
		)

	def test_the_years_keep_one_row_each_in_the_order_of_the_years(self):
		settings = self.make(
			years=[
				{"year": 2027, "kleinunternehmer": 1},
				{"year": 2026, "advisor_prepares": 1, "early_request_kst": "2027-09-30"},
			]
		).insert()
		self.assertEqual([(row.idx, row.year) for row in settings.years], [(1, 2026), (2, 2027)])
		year = settings.year_settings(2026)
		self.assertTrue(year.advisor_prepares)
		self.assertEqual(year.early_request_kst, date(2027, 9, 30))
		self.assertTrue(settings.year_settings(2027).kleinunternehmer)
		self.assertIsNone(settings.year_settings(2025))
		settings.append("years", {"year": 2026})
		with self.assertRaisesRegex(frappe.ValidationError, "The year 2026 is entered twice."):
			settings.save()

	def test_the_finanzamt_asks_early_only_within_the_days_of_149_abs_4_ao(self):
		for row, message in (
			({"year": 2026, "early_request_ust": "2027-09-30"}, "only when a Steuerberatung prepares it"),
			(
				{"year": 2026, "advisor_prepares": 1, "early_request_gewst": "2027-07-30"},
				"for a day from 31. Juli 2027 on and before 29. Februar 2028",
			),
			(
				{
					"year": 2026,
					"advisor_prepares": 1,
					"kleinunternehmer": 1,
					"early_request_ust": "2027-09-30",
				},
				"A Kleinunternehmer files no Umsatzsteuererklärung for 2026",
			),
			({"year": 2026, "exempt_264_3": 1, "exempt_264_3_reason": "x"}, None),
		):
			with self.subTest(row=row):
				frappe.delete_doc_if_exists("Annual Filing Settings", COMPANY)
				if message is None:
					self.make(years=[row]).insert()
				else:
					with self.assertRaisesRegex(frappe.ValidationError, message):
						self.make(years=[row]).insert()

	def test_only_the_jahresabschluss_writes_the_day_of_its_feststellung(self):
		settings = self.make(years=[{"year": 2026, "adopted_on": "2027-05-01"}]).insert()
		self.assertIsNone(settings.years[0].adopted_on)
		settings_module.record_adoption(COMPANY, 2026, date(2027, 6, 15))
		settings.reload()
		self.assertEqual(settings.years[0].adopted_on, date(2027, 6, 15))
		settings.years[0].adopted_on = "2027-01-01"
		settings.save()
		self.assertEqual(
			frappe.get_doc("Annual Filing Settings", COMPANY).years[0].adopted_on, date(2027, 6, 15)
		)
		settings.set("years", [])
		with self.assertRaisesRegex(
			frappe.ValidationError, "The year 2026 holds the Feststellung of its Jahresabschluss"
		):
			settings.save()
		settings.reload()
		settings.record_adoption(2027, date(2028, 5, 2))
		settings.record_adoption(2026, None)
		settings.reload()
		self.assertEqual(
			[(row.year, row.adopted_on) for row in settings.years], [(2026, None), (2027, date(2028, 5, 2))]
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Enter the Annual Filing Settings of"):
			settings_module.record_adoption(OTHER_COMPANY, 2026, date(2027, 6, 15))

	def test_the_shareholders_with_their_numbers_as_the_kst_1_takes_them(self):
		settings = self.make(
			shareholders=[
				shareholder(
					"Erika Mustermann",
					60,
					idnr="123 456 789 03",
					tax_number="123/456/78903",
					tax_number_state="Bayern",
				),
				shareholder(
					"Beispiel Beteiligungs GmbH",
					40,
					kind=ShareholderKind.CORPORATION.value,
					wid_nr="de 123456789",
				),
			]
		).insert()
		self.assertEqual(
			[(row.idnr, row.wid_nr) for row in settings.shareholders], [(IDNR, None), (None, WID_NR)]
		)
		first, second = settings.get_shareholders()
		self.assertEqual(
			(first.tax_number, first.percent, first.nominal_amount),
			("9123045678903", Decimal(60), Decimal(15000)),
		)
		self.assertIs(second.kind, ShareholderKind.CORPORATION)

	def test_refuses_shares_that_do_not_add_up_and_numbers_of_another_shape_without_naming_them(self):
		with self.assertRaisesRegex(frappe.ValidationError, "add up to 98 %; ELSTER takes 99 to 100 %"):
			self.make(shareholders=[shareholder("Anna", 58), shareholder("Bert", 40)]).insert()
		for values, message in (
			(
				{"kind": ShareholderKind.CORPORATION.value, "idnr": IDNR},
				"only a natural person has an Identifikationsnummer",
			),
			({"idnr": "1234567890"}, "an Identifikationsnummer has eleven digits"),
			({"tax_number": "123/456/78903"}, "without its Bundesland the Steuernummer is the 13-digit form"),
			({"nominal_amount": 100.5}, "in full euros above 0"),
		):
			with self.subTest(values=values), self.assertRaises(frappe.ValidationError) as raised:
				self.make(shareholders=[shareholder(**values)]).insert()
			self.assertIn(message, str(raised.exception))
			self.assertNotIn(values.get("idnr") or values.get("tax_number") or "§§", str(raised.exception))

	def test_a_row_without_its_mandatory_values_is_left_to_the_mandatory_check(self):
		with self.assertRaises(frappe.MandatoryError):
			self.make(
				shareholders=[shareholder("Anna", 60), shareholder("Bert", 40, from_date=None)]
			).insert()

	def test_an_accounts_user_reads_the_settings_without_the_numbers_of_the_shareholders(self):
		"""§ 139b Abs. 2 AO: the Identifikationsnummer only for the Körperschaftsteuererklärung."""
		self.make(
			shareholders=[shareholder(idnr=IDNR, tax_number="9123045678903", foreign_id="X-1")]
		).insert()
		make_user(ACCOUNTANT, "Accounts User")
		make_user(MANAGER, "Accounts Manager")
		with self.set_user(ACCOUNTANT):
			self.assertTrue(frappe.has_permission("Annual Filing Settings", "read", COMPANY))
			self.assertFalse(frappe.has_permission("Annual Filing Settings", "write", COMPANY))
			(row,) = client_get("Annual Filing Settings", COMPANY)["shareholders"]
			self.assertEqual(row["shareholder_name"], "Erika Mustermann")
			self.assertEqual(
				{fieldname: row.get(fieldname) for fieldname in ("idnr", "tax_number", "foreign_id")},
				dict.fromkeys(("idnr", "tax_number", "foreign_id")),
			)
			self.assertNotIn(IDNR, str(row))
			settings = frappe.get_doc("Annual Filing Settings", COMPANY)
			settings.business_purpose = "Softwareentwicklung"
			with self.assertRaises(frappe.PermissionError):
				settings.save()
		with self.set_user(MANAGER):
			(row,) = client_get("Annual Filing Settings", COMPANY)["shareholders"]
			self.assertEqual((row["idnr"], row["tax_number"]), (IDNR, "9123045678903"))
			settings = frappe.get_doc("Annual Filing Settings", COMPANY)
			settings.shareholders[0].idnr = "98765432105"
			settings.save()
		self.assertEqual(
			frappe.get_doc("Annual Filing Settings", COMPANY).shareholders[0].idnr, "98765432105"
		)

	def test_keeps_no_version_that_would_log_the_numbers(self):
		settings = self.make(shareholders=[shareholder(idnr=IDNR)]).insert()
		settings.shareholders[0].idnr = "98765432105"
		settings.save(ignore_version=False)
		self.assertEqual(
			frappe.get_all("Version", filters={"ref_doctype": "Annual Filing Settings", "docname": COMPANY}),
			[],
		)

	def test_a_director_holds_one_office_at_a_time(self):
		settings = self.make(
			directors=[
				{"director_name": "Erika Mustermann", "from_date": "2026-01-01", "is_shareholder": 1},
				{"director_name": "Max Mustermann", "from_date": "2026-07-01"},
			]
		).insert()
		first, second = settings.get_directors()
		self.assertEqual(
			(first.role, first.signs, first.is_shareholder, second.signs),
			("Geschäftsführer", True, True, True),
		)
		settings.append("directors", {"director_name": "erika mustermann", "from_date": "2026-03-01"})
		with self.assertRaisesRegex(
			frappe.ValidationError, "Rows 1 and 3 of the managing directors name Erika Mustermann"
		):
			settings.save()

	def test_the_betriebsstaetten_and_hebesaetze_of_the_gewerbesteuer(self):
		settings = self.make(
			establishments=[
				{"municipality": "München", "postal_code": "80331", "ags": AGS, "from_date": "2026-01-01"}
			],
			trade_tax_rates=[
				{"ags": AGS, "year": 2027, "hebesatz": 490, "source": "Haushaltssatzung 2027"},
				{
					"ags": AGS,
					"year": 2026,
					"hebesatz": 490,
					"source": "Haushaltssatzung 2026",
					"source_date": "2026-01-15",
				},
			],
		).insert()
		self.assertEqual([row.year for row in settings.trade_tax_rates], [2026, 2027])
		self.assertEqual(settings.hebesatz(AGS, 2026).hebesatz, Decimal(490))
		self.assertIsNone(settings.hebesatz(AGS, 2028))
		self.assertEqual([place.ags for place in settings.get_establishments()], [AGS])
		for rows, message in (
			(
				{"trade_tax_rates": [{"ags": AGS, "year": 2027, "hebesatz": 250, "source": "x"}]},
				"sets at least 280 %",
			),
			(
				{"trade_tax_rates": [{"ags": AGS, "year": 2026, "hebesatz": 199, "source": "x"}]},
				"sets at least 200 %",
			),
			(
				{"trade_tax_rates": [{"ags": "17000000", "year": 2026, "hebesatz": 300, "source": "x"}]},
				"is not an Amtlicher",
			),
			(
				{
					"establishments": [
						{
							"municipality": "München",
							"postal_code": "8033",
							"ags": AGS,
							"from_date": "2026-01-01",
						}
					]
				},
				"8033 is not a German postal code",
			),
		):
			with self.subTest(message=message), self.assertRaisesRegex(frappe.ValidationError, message):
				self.make(company=OTHER_COMPANY, **rows).insert()

	def test_holdings_vorauszahlungen_carry_forwards_and_sizes(self):
		settings = self.make(
			holdings=[
				{
					"holding_name": "Beispiel AG",
					"year": 2026,
					"percent_on_1_january": 12.5,
					"percent_at_start_of_ez": 12.5,
				}
			],
			prepayments=[
				{"tax": "GewSt", "year": 2026, "due_date": "2026-02-15", "amount": 250, "ags": AGS},
				{"tax": "KSt", "year": 2026, "due_date": "2026-03-10", "amount": 1000},
			],
			carry_forwards=[
				{"kind": CarryForwardKind.LOSS.value, "as_of": "2025-12-31", "amount": 5000, "confirmed": 1}
			],
			size_history=[
				{
					"fiscal_year_end": "2025-12-31",
					"size_class": "Kleinst",
					"source": "Jahresabschluss 2025",
					"employees": 2.25,
				}
			],
		).insert()
		self.assertEqual(settings.get_holdings()[0].percent_on_1_january, Decimal("12.5"))
		self.assertEqual(
			[(p.tax, p.ags) for p in settings.get_prepayments()], [(Tax.GEWST, AGS), (Tax.KST, None)]
		)
		(carry_forward,) = settings.get_carry_forwards()
		self.assertTrue(carry_forward.confirmed)
		self.assertIs(settings.get_size_history()[0].size_class, SizeClass.KLEINST)
		for rows, message in (
			(
				{
					"prepayments": [
						{"tax": "KSt", "year": 2026, "due_date": "2026-03-10", "amount": 1, "ags": AGS}
					]
				},
				"goes to the Finanzamt",
			),
			(
				{
					"carry_forwards": [
						{"kind": CarryForwardKind.FEHLBETRAG.value, "as_of": "2025-12-31", "amount": 1}
					]
					* 2
				},
				"as of 31. Dezember 2025 is entered twice",
			),
			(
				{"holdings": [{"holding_name": "Beispiel AG", "year": 2026}] * 2},
				"The holding in Beispiel AG for 2026 is entered twice",
			),
			(
				{
					"size_history": [{"fiscal_year_end": "2025-12-31", "size_class": "Klein", "source": "x"}]
					* 2
				},
				"ending on 31. Dezember 2025 is entered twice",
			),
			(
				{"excluded_employment_types": [{"employment_type": "Apprentice"}] * 2},
				"The Employment Type Apprentice is listed twice",
			),
		):
			with self.subTest(message=message), self.assertRaisesRegex(frappe.ValidationError, message):
				self.make(company=OTHER_COMPANY, **rows).insert()

	def test_a_message_names_the_option_of_its_row(self):
		with self.assertRaisesRegex(frappe.ValidationError, r"Loss Carried Forward \(§ 10d EStG\) as of"):
			self.make(
				carry_forwards=[{"kind": CarryForwardKind.LOSS.value, "as_of": "2025-12-31", "amount": -1}]
			).insert()

	def test_the_closing_account_is_one_a_period_closing_voucher_takes(self):
		settings = self.make(closing_account=self.retained_earnings).insert()
		self.assertEqual(settings.closing_account, self.retained_earnings)
		for account in (self.bank, self.other_equity):
			with (
				self.subTest(account=account),
				self.assertRaisesRegex(frappe.ValidationError, "must be a Liability or Equity account"),
			):
				settings.closing_account = account
				settings.save()

	def test_lists_the_employment_types_left_out_of_the_headcount(self):
		settings = self.make(excluded_employment_types=[{"employment_type": " Apprentice "}]).insert()
		self.assertEqual(settings.employment_types_not_counted(), ["Apprentice"])

	def test_frappe_reads_the_german_translations_of_the_settings(self):
		clear_translation_cache()
		self.assertEqual(frappe._("Annual Filing Settings", lang="de"), "Einstellungen Jahresmeldungen")
		self.assertEqual(frappe._("Take Address", lang="de"), "Anschrift übernehmen")
