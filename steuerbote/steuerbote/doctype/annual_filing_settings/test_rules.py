from dataclasses import FrozenInstanceError
from datetime import date
from unittest import TestCase

from steuerbote.steuerbote.doctype.annual_filing_settings import rules as rules_module
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import (
	MESSAGES,
	ROW_TEXT_LENGTHS,
	TEXT_LENGTHS,
	Address,
	LegalForm,
	SettingsError,
	StreetSplit,
	YearSettings,
	check_years,
	early_request_window,
	elster_text,
	german_postal_code,
	legal_form,
	legal_status,
	rechtsform,
	split_street,
	year_settings,
)


class LegalFormTest(TestCase):
	def test_a_gmbh_and_a_ug_are_the_legal_forms_steuerbote_files_for(self):
		self.assertEqual([form.value for form in LegalForm], ["GmbH", "UG"])
		self.assertIs(legal_form("UG"), LegalForm.UG)
		for value in ("AG", "gmbh", "", None):
			with self.subTest(value=value), self.assertRaisesRegex(SettingsError, "is not a legal form"):
				legal_form(value)

	def test_the_rechtsform_of_kst_1_and_gewst_1_a(self):
		"""RECHTSFORM_KOERPERSCHAFTEN_V3 and RECHTSFORM_GEWERBESTEUER_V2: 350 GmbH, 370 UG (haftungsbeschränkt)."""
		self.assertEqual((rechtsform("GmbH"), rechtsform(LegalForm.UG)), ("350", "370"))
		with self.assertRaisesRegex(SettingsError, "KG is not a legal form"):
			rechtsform("KG")

	def test_the_legal_status_of_the_gcd_files_a_ug_as_a_gmbh_in_the_disclosure(self):
		self.assertEqual((legal_status("GmbH"), legal_status("UG")), ("GMBH", "UG"))
		self.assertEqual(
			(legal_status("GmbH", disclosure=True), legal_status("UG", disclosure=True)), ("GMBH", "GMBH")
		)
		with self.assertRaises(SettingsError):
			legal_status("eG", disclosure=True)


class ElsterTextTest(TestCase):
	def test_keeps_a_text_on_one_line_in_the_character_set_of_elster(self):
		self.assertEqual(elster_text("  Kaiser-Wilhelm-\nStraße  ", "Straße", 30), "Kaiser-Wilhelm- Straße")
		self.assertEqual(elster_text("Müller \N{EN DASH} „Beratung“", "Name", 55), 'Müller - "Beratung"')

	def test_an_empty_text_is_none(self):
		for value in (None, "", "   "):
			with self.subTest(value=value):
				self.assertIsNone(elster_text(value, "Straße", 30))

	def test_refuses_a_text_longer_than_the_form_takes(self):
		self.assertEqual(elster_text("x" * 24, "Ort des Sitzes", 24), "x" * 24)
		with self.assertRaises(SettingsError) as raised:
			elster_text("x" * 25, "Ort des Sitzes", 24)
		self.assertEqual(str(raised.exception), "Ort des Sitzes has 25 characters; ELSTER takes at most 24.")

	def test_refuses_characters_elster_does_not_take(self):
		with self.assertRaises(SettingsError) as raised:
			elster_text("Łódź", "Ort", 29)
		self.assertEqual(
			str(raised.exception),
			"Ort contains characters ELSTER does not take: 'Ł' (U+0141), 'ź' (U+017A).",
		)

	def test_the_lengths_are_those_of_the_forms(self):
		"""GewSt 1 A line 4; KSt 1 lines 6 and 7; USt 2 A line 9; AbsStr and AbsOrt of the Vorsatz; the Mitwirkung
		of USt 2 A and KSt 1 lines 100 to 102."""
		self.assertEqual(
			dict(TEXT_LENGTHS),
			{
				"business_purpose": 25,
				"management_seat": 24,
				"registered_seat": 24,
				"street": 30,
				"house_number_suffix": 6,
				"address_supplement": 25,
				"postal_code": 12,
				"city": 29,
				"advisor_name": 55,
				"advisor_first_name": 55,
				"advisor_street": 55,
				"advisor_town": 55,
				"advisor_phone": 55,
				"advisor_details": 55,
				"advisor_client_number": 60,
				"advisor_clerk": 55,
			},
		)
		self.assertEqual(
			{table: dict(lengths) for table, lengths in ROW_TEXT_LENGTHS.items()},
			{
				"shareholders": {
					"shareholder_name": 999,
					"street": 999,
					"postal_code_and_town": 999,
					"foreign_id": 999,
				},
				"establishments": {"municipality": 999, "hebenummer": 28},
			},
		)


class SplitStreetTest(TestCase):
	def test_splits_the_house_number_and_its_suffix_off_the_street(self):
		for text, expected in (
			("Hauptstraße 1", StreetSplit("Hauptstraße", "1")),
			("Musterweg 12a", StreetSplit("Musterweg", "12", "a")),
			("Musterweg 12 a", StreetSplit("Musterweg", "12", "a")),
			("Musterstr. 12-14", StreetSplit("Musterstr.", "12", "-14")),
			("Am Brunnen 1000", StreetSplit("Am Brunnen", "1000")),
			("  Lange   Gasse 7  ", StreetSplit("Lange Gasse", "7")),
		):
			with self.subTest(text=text):
				self.assertEqual(split_street(text), expected)

	def test_splits_at_the_last_digits_after_a_blank(self):
		self.assertEqual(split_street("Straße des 17. Juni 112"), StreetSplit("Straße des 17. Juni", "112"))
		self.assertEqual(split_street("Q 7, 17"), StreetSplit("Q 7", "17"))

	def test_a_street_without_a_house_number_stays_whole(self):
		for text in ("Am Markt", "Musterstraße 12345", "Musterstraße12"):
			with self.subTest(text=text):
				self.assertEqual(split_street(text), StreetSplit(text))

	def test_an_empty_street_gives_none(self):
		for text in (None, "", "  "):
			with self.subTest(text=text):
				self.assertIsNone(split_street(text))


class AddressTest(TestCase):
	def test_writes_street_house_number_and_suffix_on_one_line(self):
		address = Address("Musterweg", "12", "a", "Hinterhaus", "80331", "München")
		self.assertEqual(address.street_line, "Musterweg 12a")
		self.assertTrue(address.in_germany)
		self.assertEqual(Address("Am Markt").street_line, "Am Markt")
		self.assertIsNone(Address().street_line)

	def test_the_house_number_is_digits_only_at_most_four(self):
		for number in ("12a", "12345", "", " 1", "-1"):
			with self.subTest(number=number), self.assertRaisesRegex(SettingsError, "is not a house number"):
				Address("Musterweg", number)

	def test_a_house_number_needs_its_street_and_a_suffix_its_house_number(self):
		with self.assertRaisesRegex(SettingsError, "A house number needs its street."):
			Address(None, "12")
		with self.assertRaisesRegex(SettingsError, "A house number suffix needs its house number."):
			Address("Musterweg", None, "a")

	def test_a_german_postal_code_has_five_digits_not_beginning_with_00(self):
		for code in ("01067", "80331", "99998"):
			with self.subTest(code=code):
				self.assertEqual(Address(postal_code=code).postal_code, code)
		for code in ("00123", "8033", "803311", "A-1010", ""):
			with (
				self.subTest(code=code),
				self.assertRaisesRegex(SettingsError, "is not a German postal code"),
			):
				Address(postal_code=code)

	def test_a_postal_code_abroad_has_its_own_form(self):
		address = Address(postal_code="A-1010", city="Wien", country="Austria")
		self.assertFalse(address.in_germany)
		self.assertEqual(address.postal_code, "A-1010")

	def test_the_vorsatz_takes_street_house_number_and_suffix_in_30_characters(self):
		self.assertEqual(len(Address("x" * 25, "1234").street_line), 30)
		with self.assertRaises(SettingsError) as raised:
			Address("x" * 25, "1234", "a")
		self.assertEqual(
			str(raised.exception),
			"Street, house number and suffix make 31 characters; the Vorsatz of an Erklärung takes at most 30.",
		)

	def test_german_postal_code_returns_the_code(self):
		self.assertEqual(german_postal_code("10115"), "10115")


class YearSettingsTest(TestCase):
	def test_a_year_without_anything_set(self):
		year = YearSettings(2026)
		self.assertFalse(year.advisor_prepares)
		self.assertEqual(
			year.early_requests,
			{
				"Umsatzsteuererklärung": None,
				"Körperschaftsteuererklärung": None,
				"Gewerbesteuererklärung": None,
			},
		)
		with self.assertRaises(FrozenInstanceError):
			year.year = 2027  # type: ignore[misc]

	def test_the_year_has_four_digits(self):
		for value in (0, 999, 10000, True, 2026.0, "2026", None):
			with self.subTest(value=value), self.assertRaisesRegex(SettingsError, "is not a four-digit year"):
				YearSettings(value)  # type: ignore[arg-type]

	def test_the_finanzamt_asks_early_only_for_erklaerungen_a_steuerberatung_prepares(self):
		"""§ 149 Abs. 4 Satz 1 AO: „Erklärungen im Sinne des Absatzes 3“."""
		self.assertEqual(
			YearSettings(2026, advisor_prepares=True, early_request_kst=date(2027, 9, 30)).early_requests[
				"Körperschaftsteuererklärung"
			],
			date(2027, 9, 30),
		)
		with self.assertRaises(SettingsError) as raised:
			YearSettings(2026, early_request_gewst=date(2027, 9, 30))
		self.assertEqual(
			str(raised.exception),
			"The Finanzamt can ask for the Gewerbesteuererklärung of 2026 early only when a Steuerberatung prepares "
			"it (§ 149 Abs. 4 AO).",
		)

	def test_an_early_request_lies_from_the_deadline_of_absatz_2_on_and_before_the_end_of_february(self):
		"""§ 149 Abs. 4 AO: before the last day of February of the second year, never shorter than seven months."""
		self.assertEqual(early_request_window(2026), (date(2027, 7, 31), date(2028, 2, 29)))
		self.assertEqual(early_request_window(2027), (date(2028, 7, 31), date(2029, 2, 28)))
		for day in (date(2027, 7, 31), date(2028, 2, 28)):
			with self.subTest(day=day):
				YearSettings(2026, advisor_prepares=True, early_request_ust=day)
		for day in (date(2027, 7, 30), date(2028, 2, 29), date(2028, 3, 1)):
			with self.subTest(day=day), self.assertRaises(SettingsError) as raised:
				YearSettings(2026, advisor_prepares=True, early_request_ust=day)
		self.assertEqual(
			str(raised.exception),
			"The Finanzamt can ask for the Umsatzsteuererklärung of 2026 for a day from 31. Juli 2027 on and before "
			"29. Februar 2028 (§ 149 Abs. 4 AO), not for 1. März 2028.",
		)

	def test_a_kleinunternehmer_files_no_umsatzsteuererklaerung_to_ask_for(self):
		"""§ 19 Abs. 1 Satz 2 UStG: § 18 Absatz 1 bis 4 UStG do not apply."""
		YearSettings(2026, kleinunternehmer=True, advisor_prepares=True, early_request_kst=date(2027, 8, 31))
		with self.assertRaisesRegex(
			SettingsError, "A Kleinunternehmer files no Umsatzsteuererklärung for 2026"
		):
			YearSettings(
				2026, kleinunternehmer=True, advisor_prepares=True, early_request_ust=date(2027, 8, 31)
			)

	def test_an_exemption_under_264_3_hgb_states_its_reason(self):
		YearSettings(2026, exempt_264_3=True, exempt_264_3_reason="Konzernabschluss der Muttergesellschaft")
		for reason in (None, "", "  "):
			with (
				self.subTest(reason=reason),
				self.assertRaisesRegex(
					SettingsError, "The exemption of 2026 under § 264 Abs. 3 HGB needs its reason."
				),
			):
				YearSettings(2026, exempt_264_3=True, exempt_264_3_reason=reason)

	def test_a_year_has_one_row(self):
		years = [YearSettings(2026), YearSettings(2027)]
		check_years(years)
		with self.assertRaisesRegex(SettingsError, "The year 2026 is entered twice."):
			check_years([*years, YearSettings(2026, advisor_prepares=True)])

	def test_finds_the_settings_of_a_year(self):
		years = [YearSettings(2026, advisor_prepares=True), YearSettings(2027)]
		self.assertTrue(year_settings(years, 2026).advisor_prepares)
		self.assertIsNone(year_settings(years, 2025))


class SettingsErrorTest(TestCase):
	def test_keeps_the_template_and_its_values_for_the_translation(self):
		error = SettingsError(rules_module.TEXT_TOO_LONG, "Ort", 30, 29)
		self.assertEqual(str(error), "Ort has 30 characters; ELSTER takes at most 29.")
		self.assertEqual((error.template, error.values), (rules_module.TEXT_TOO_LONG, ("Ort", 30, 29)))
		self.assertIsInstance(error, ValueError)

	def test_messages_lists_every_template_of_the_module(self):
		templates = [
			value
			for name, value in vars(rules_module).items()
			if name.isupper() and isinstance(value, str) and value.endswith(".")
		]
		self.assertCountEqual(MESSAGES, templates)
		self.assertEqual(len(set(MESSAGES)), len(MESSAGES))
