from unittest import TestCase

from steuerbote.zm.ustid import (
	NORTHERN_IRELAND,
	OTHER_MEMBER_STATES,
	Refusal,
	clean,
	country_prefix,
	normalize,
	refusal,
)

# „Liste der Länderkennzeichen“ of the ELSTER help „Import von Meldelisten zur Zusammenfassenden Meldung“,
# read on 2026-11-20, without GB and XI, which the rules below treat on their own.
HELP_PAGE_COUNTRY_CODES = (
	"AT",
	"BE",
	"BG",
	"CY",
	"CZ",
	"DK",
	"EE",
	"EL",
	"ES",
	"FI",
	"FR",
	"HR",
	"HU",
	"IE",
	"IT",
	"LT",
	"LU",
	"LV",
	"MT",
	"NL",
	"PL",
	"PT",
	"RO",
	"SE",
	"SI",
	"SK",
)


class CleanTest(TestCase):
	def test_keeps_letters_digits_plus_and_asterisk_in_upper_case(self):
		self.assertEqual(clean(" atu 123.456-78 "), "ATU12345678")
		self.assertEqual(clean("NL123456789b01"), "NL123456789B01")
		self.assertEqual(clean("IE1234567*+"), "IE1234567*+")

	def test_nothing_is_empty(self):
		self.assertEqual(clean(None), "")
		self.assertEqual(clean(" - "), "")


class CountryCodesTest(TestCase):
	def test_the_other_26_member_states_as_the_help_page_lists_them(self):
		self.assertEqual(sorted(OTHER_MEMBER_STATES), list(HELP_PAGE_COUNTRY_CODES))
		self.assertEqual(len(OTHER_MEMBER_STATES), 26)

	def test_greece_is_el(self):
		self.assertIn("EL", OTHER_MEMBER_STATES)
		self.assertNotIn("GR", OTHER_MEMBER_STATES)


class NormalizeTest(TestCase):
	def test_examples_of_the_help_page_pass_unchanged(self):
		for vat_id in ("FRWL247100014", "HR12345678903", "IE8Z49289F", "ESW0068209F", "IT00000008888"):
			with self.subTest(vat_id):
				self.assertEqual(normalize(vat_id), vat_id)

	def test_spaces_dots_and_dashes_are_dropped(self):
		self.assertEqual(normalize("ATU 12345678"), "ATU12345678")
		self.assertEqual(normalize("fr-12.345.678.901"), "FR12345678901")

	def test_at_least_seven_and_at_most_fourteen_characters(self):
		self.assertEqual(normalize("BE12345"), "BE12345")
		self.assertIsNone(normalize("BE1234"))
		self.assertEqual(normalize("NL123456789B01"), "NL123456789B01")
		self.assertIsNone(normalize("NL123456789B012"))
		self.assertEqual(refusal("BE1234"), Refusal.FORMAT)

	def test_starts_with_two_letters(self):
		self.assertIsNone(normalize("1234567890"))
		self.assertIsNone(normalize("A1234567890"))
		self.assertEqual(refusal(""), Refusal.FORMAT)

	def test_refuses_german_numbers(self):
		"""ZMDO rule 170045014: „Es dürfen keine inländischen UstId-Nummern angegeben werden.“"""
		self.assertIsNone(normalize("DE123456789"))
		self.assertEqual(refusal("DE123456789"), Refusal.DOMESTIC)

	def test_refuses_british_numbers(self):
		"""BZSt FAQ: GB is „nur für die Meldezeiträume bis zum Ablauf des Übergangszeitraumes am 31.12.2020“."""
		self.assertIsNone(normalize("GB123456789"))
		self.assertEqual(refusal("GB123456789"), Refusal.UNITED_KINGDOM)

	def test_refuses_the_iso_code_of_greece_and_unknown_codes(self):
		self.assertIsNone(normalize("GR123456789"))
		self.assertEqual(refusal("GR123456789"), Refusal.UNKNOWN_COUNTRY)
		self.assertEqual(refusal("CH123456789"), Refusal.UNKNOWN_COUNTRY)
		self.assertEqual(normalize("EL123456789"), "EL123456789")

	def test_northern_ireland_only_for_goods(self):
		"""ZMDO rule 170045021: „Nordirische UStIDs (Präfix XI) dürfen nicht für sonstige Leistungen verwendet
		werden.“"""
		self.assertEqual(normalize("XI123456789"), "XI123456789")
		self.assertIsNone(normalize("XI123456789", services=True))
		self.assertEqual(refusal("XI123456789", services=True), Refusal.NORTHERN_IRELAND_SERVICES)
		self.assertEqual(normalize("ATU12345678", services=True), "ATU12345678")


class CountryPrefixTest(TestCase):
	def test_iso_codes_and_country_names_of_erpnext(self):
		self.assertEqual(country_prefix("AT"), "AT")
		self.assertEqual(country_prefix("Austria"), "AT")
		self.assertEqual(country_prefix(" france "), "FR")

	def test_greece_is_el_by_any_name(self):
		self.assertEqual(country_prefix("GR"), "EL")
		self.assertEqual(country_prefix("Greece"), "EL")
		self.assertEqual(country_prefix("EL"), "EL")

	def test_monaco_counts_as_france(self):
		self.assertEqual(country_prefix("Monaco"), "FR")

	def test_northern_ireland_by_its_code(self):
		self.assertEqual(country_prefix("xi"), NORTHERN_IRELAND)

	def test_no_prefix_outside_the_other_member_states(self):
		self.assertIsNone(country_prefix("Germany"))
		self.assertIsNone(country_prefix("United Kingdom"))
		self.assertIsNone(country_prefix(None))
		self.assertIsNone(country_prefix(""))
