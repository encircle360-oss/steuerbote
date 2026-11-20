"""The plausibility rule of a USt-IdNr. from another member state and the structure per member state.

The fixture eu_mitgliedstaaten.json is the BZSt's list of member states for the confirmation,
https://api.evatr.vies.bzst.de/v1/info/eu_mitgliedstaaten, retrieved on 20 November 2026.
"""

import json
from pathlib import Path
from unittest import TestCase

from steuerbote.vatid.ustid import (
	MAX_LENGTH,
	MEMBER_STATES,
	MIN_LENGTH,
	REFUSED,
	checked_pair,
	is_german,
	is_plausible,
	normalize,
	problem,
	structure_hint,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Made-up numbers with the structure the BZSt's Merkblatt gives each member state, and without it.
FITTING = {
	"AT": ("ATU12345678",),
	"BE": ("BE0123456789",),
	"BG": ("BG123456789", "BG1234567890"),
	"CY": ("CY12345678X",),
	"CZ": ("CZ12345678", "CZ123456789", "CZ1234567890"),
	"DK": ("DK12345678",),
	"EE": ("EE123456789",),
	"EL": ("EL123456789",),
	"ES": ("ESA1234567B", "ES12345678Z", "ESX12345678", "ES123456789"),
	"FI": ("FI12345678",),
	"FR": ("FR12345678901", "FRAB123456789", "FR1A123456789", "FRA1123456789"),
	"HR": ("HR12345678901",),
	"HU": ("HU12345678",),
	"IE": ("IE1234567A", "IE1A23456B", "IE1234567WA"),
	"IT": ("IT12345678901",),
	"LT": ("LT123456789", "LT123456789012"),
	"LU": ("LU12345678",),
	"LV": ("LV12345678901",),
	"MT": ("MT12345678",),
	"NL": ("NL123456789B01", "NL12345678+*AB"),
	"PL": ("PL1234567890",),
	"PT": ("PT123456789",),
	"RO": ("RO12345", "RO1234567890"),
	"SE": ("SE123456789001",),
	"SI": ("SI12345678",),
	"SK": ("SK1234567890",),
	"XI": ("XI123456789", "XI123456789012", "XIGD123", "XIHA123"),
}
NOT_FITTING = {
	"AT": ("ATU1234567", "AT123456789", "ATX12345678"),
	"BE": ("BE123456789",),
	"BG": ("BG12345678", "BG12345678901"),
	"CY": ("CY123456789",),
	"CZ": ("CZ1234567", "CZ12345678901"),
	"DK": ("DK1234567X",),
	"EE": ("EE12345678",),
	"EL": ("EL12345678",),
	"ES": ("ES1234567", "ES12A456789"),
	"FI": ("FI1234567",),
	"FR": ("FR1234567890", "FR12A45678901"),
	"HR": ("HR1234567890",),
	"HU": ("HU1234567",),
	"IE": ("IE12345678", "IE1234567XA", "IE1234567AJ"),
	"IT": ("IT1234567890",),
	"LT": ("LT1234567890",),
	"LU": ("LU1234567",),
	"LV": ("LV1234567890",),
	"MT": ("MT1234567",),
	"NL": ("NL123456789B0",),
	"PL": ("PL123456789",),
	"PT": ("PT12345678",),
	"RO": ("RO01234", "RO12345678901"),
	"SE": ("SE123456789012",),
	"SI": ("SI1234567",),
	"SK": ("SK123456789",),
	"XI": ("XI12345678", "XIGD1234", "XIAB123"),
}


class NormalizeTest(TestCase):
	def test_keeps_letters_digits_plus_and_star_in_capitals(self):
		self.assertEqual(normalize(" atu 123.456-78 "), "ATU12345678")
		self.assertEqual(normalize("nl 1234.56.789.b01"), "NL123456789B01")
		self.assertEqual(normalize("NL12345678+*ab"), "NL12345678+*AB")

	def test_drops_every_other_character(self):
		self.assertEqual(normalize("FR/12_345\t678,901;ü"), "FR12345678901")
		self.assertEqual(normalize(" .-/ "), "")

	def test_refuses_what_is_not_text(self):
		for value in (None, 12345678, b"ATU12345678"):
			with self.subTest(value=value), self.assertRaises(TypeError):
				normalize(value)


class MemberStatesTest(TestCase):
	def test_are_those_of_the_bzst_without_germany(self):
		listed = json.loads((FIXTURES / "eu_mitgliedstaaten.json").read_text(encoding="utf-8"))
		names = {entry["alpha2"]: entry["name"] for entry in listed if entry["alpha2"] != "DE"}
		self.assertEqual({code: state.name for code, state in MEMBER_STATES.items()}, names)
		self.assertEqual(list(MEMBER_STATES), sorted(names))

	def test_greece_is_el_and_northern_ireland_xi(self):
		self.assertEqual(MEMBER_STATES["EL"].name, "Griechenland")
		self.assertEqual(MEMBER_STATES["XI"].name, "Nordirland")
		self.assertNotIn("GR", MEMBER_STATES)

	def test_each_code_is_its_key(self):
		for code, state in MEMBER_STATES.items():
			self.assertEqual(state.code, code)

	def test_every_member_state_has_examples(self):
		self.assertEqual(set(FITTING), set(MEMBER_STATES))
		self.assertEqual(set(NOT_FITTING), set(MEMBER_STATES))


class PlausibilityTest(TestCase):
	def test_the_lengths_are_those_eric_enforces_for_a_zm_line(self):
		self.assertEqual((MIN_LENGTH, MAX_LENGTH), (7, 14))

	def test_accepts_a_number_of_every_other_member_state(self):
		for code, numbers in FITTING.items():
			for number in numbers:
				with self.subTest(code=code, number=number):
					self.assertTrue(is_plausible(number))
					self.assertIsNone(problem(number))

	def test_accepts_a_number_written_with_blanks_and_dots_in_small_letters(self):
		self.assertTrue(is_plausible("atu 123 456 78"))
		self.assertTrue(is_plausible("BE 0123.456.789"))

	def test_refuses_a_german_number(self):
		self.assertFalse(is_plausible("DE123456789"))
		self.assertEqual(problem("DE 123 456 789"), REFUSED["DE"])
		self.assertIn("§ 18e Nr. 1 UStG", REFUSED["DE"])

	def test_refuses_a_british_number_and_points_to_xi(self):
		self.assertFalse(is_plausible("GB123456789"))
		self.assertEqual(problem("GB123456789"), REFUSED["GB"])
		self.assertIn("XI", REFUSED["GB"])

	def test_names_el_for_a_greek_number_with_gr(self):
		self.assertFalse(is_plausible("GR123456789"))
		self.assertEqual(problem("GR123456789"), REFUSED["GR"])
		self.assertIn("EL", REFUSED["GR"])

	def test_refuses_a_country_code_outside_the_member_states(self):
		for number in ("US123456789", "CHE123456789", "MC12345678901", "NO123456789"):
			with self.subTest(number=number):
				self.assertFalse(is_plausible(number))
				self.assertEqual(
					problem(number),
					f"{number[:2]} ist kein Länderkennzeichen eines anderen Mitgliedstaats der EU.",
				)

	def test_refuses_a_number_without_a_country_code_of_two_letters(self):
		for number in ("123456789", "A12345678", "1ATU12345678"):
			with self.subTest(number=number):
				self.assertFalse(is_plausible(number))
				self.assertEqual(
					problem(number),
					f"{number} beginnt nicht mit einem Länderkennzeichen aus zwei Buchstaben.",
				)

	def test_needs_seven_to_fourteen_characters(self):
		self.assertTrue(is_plausible("ATU1234"))
		self.assertTrue(is_plausible("NL123456789B01"))
		self.assertFalse(is_plausible("ATU123"))
		self.assertFalse(is_plausible("NL123456789B012"))
		self.assertEqual(problem("AT U123"), "Eine USt-IdNr. hat 7 bis 14 Zeichen, ATU123 hat 6.")

	def test_a_missing_number_is_not_plausible(self):
		for value in (None, "", "   ", "-./", 12345678):
			with self.subTest(value=value):
				self.assertFalse(is_plausible(value))
				self.assertEqual(problem(value), "Die USt-IdNr. fehlt.")


class StructureHintTest(TestCase):
	def test_says_nothing_about_a_number_with_the_structure_of_its_member_state(self):
		for code, numbers in FITTING.items():
			for number in numbers:
				with self.subTest(code=code, number=number):
					self.assertIsNone(structure_hint(number))

	def test_names_the_structure_the_bzst_gives_the_member_state(self):
		for code, numbers in NOT_FITTING.items():
			state = MEMBER_STATES[code]
			for number in numbers:
				with self.subTest(code=code, number=number):
					self.assertTrue(is_plausible(number))
					self.assertEqual(
						structure_hint(number),
						f"{number} hat nicht den Aufbau, den das BZSt für {state.name} beschreibt "
						f"(Stellen nach dem Länderkennzeichen): {state.structure}.",
					)

	def test_reads_the_number_as_normalize_does(self):
		self.assertIsNone(structure_hint("atu 123 456 78"))
		self.assertIn("Österreich", structure_hint("at u 123 456 7"))

	def test_leaves_an_implausible_number_to_problem(self):
		for value in (None, "", "DE123456789", "GB123456789", "ATU123"):
			with self.subTest(value=value):
				self.assertIsNone(structure_hint(value))

	def test_a_romanian_number_filled_up_with_zeros_gets_the_hint_of_the_merkblatt(self):
		self.assertTrue(is_plausible("RO01234"))
		self.assertIn("nicht mit 0 beginnend", structure_hint("RO01234"))


class GermanNumberTest(TestCase):
	def test_is_de_and_nine_digits(self):
		self.assertTrue(is_german("DE123456789"))
		self.assertTrue(is_german("de 123 456 789"))

	def test_refuses_anything_else(self):
		for value in ("DE12345678", "DE1234567890", "DEU12345678", "ATU12345678", "", None, 123456789):
			with self.subTest(value=value):
				self.assertFalse(is_german(value))


class CheckedPairTest(TestCase):
	def test_normalizes_both_numbers(self):
		self.assertEqual(checked_pair("atu 123 456 78", "de 123 456 789"), ("ATU12345678", "DE123456789"))

	def test_refuses_a_requested_number_that_is_not_plausible(self):
		with self.assertRaisesRegex(ValueError, "DE987654321"):
			checked_pair("DE987654321", "DE123456789")

	def test_refuses_an_asking_number_that_is_not_german(self):
		with self.assertRaisesRegex(ValueError, "ATU87654321"):
			checked_pair("ATU12345678", "ATU87654321")
