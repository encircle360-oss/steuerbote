from unittest import TestCase

from steuerbote.elster.steuernummer import (
	SCHEMES,
	STATE_CODES,
	STATES,
	SteuernummerError,
	ZeroSteuernummerError,
	from_elster,
	to_elster,
	validate,
)

# The table "Aufbau einer Steuernummer" of the ELSTER help topic "Wo ist meine Steuernummer?",
# https://www.elster.de/eportal/helpGlobal?themaGlobal=wo_ist_meine_steuernummer, row by row:
# Bundesland, Standardschema der Länder, vereinheitlichtes Bundesschema.
ELSTER_TABLE = (
	("Baden-Württemberg", "FF/BBB/UUUUP", "28FF0BBBUUUUP"),
	("Bayern", "FFF/BBB/UUUUP", "9FFF0BBBUUUUP"),
	("Berlin", "FF/BBB/UUUUP", "11FF0BBBUUUUP"),
	("Brandenburg", "FFF/BBB/UUUUP", "3FFF0BBBUUUUP"),
	("Bremen", "FF/BBB/UUUUP", "24FF0BBBUUUUP"),
	("Hamburg", "FF/BBB/UUUUP", "22FF0BBBUUUUP"),
	("Hessen", "0FF/BBB/UUUUP", "26FF0BBBUUUUP"),
	("Mecklenburg-Vorpommern", "FFF/BBB/UUUUP", "4FFF0BBBUUUUP"),
	("Niedersachsen", "FF/BBB/UUUUP", "23FF0BBBUUUUP"),
	("Nordrhein-Westfalen", "FFF/BBBB/UUUP", "5FFF0BBBBUUUP"),
	("Rheinland-Pfalz", "FF/BBB/UUUUP", "27FF0BBBUUUUP"),
	("Saarland", "FFF/BBB/UUUUP", "1FFF0BBBUUUUP"),
	("Sachsen", "FFF/BBB/UUUUP", "3FFF0BBBUUUUP"),
	("Sachsen-Anhalt", "FFF/BBB/UUUUP", "3FFF0BBBUUUUP"),
	("Schleswig-Holstein", "FF/BBB/UUUUP", "21FF0BBBUUUUP"),
	("Thüringen", "FFF/BBB/UUUUP", "4FFF0BBBUUUUP"),
)

# Invented numbers, one per state, as issued and as ELSTER takes them.
EXAMPLES = {
	"BW": ("12/345/67890", "2812034567890"),
	"BY": ("123/456/78901", "9123045678901"),
	"BE": ("21/345/67890", "1121034567890"),
	"BB": ("048/123/45678", "3048012345678"),
	"HB": ("71/345/67890", "2471034567890"),
	"HH": ("41/345/67890", "2241034567890"),
	"HE": ("012/345/67890", "2612034567890"),
	"MV": ("081/234/56789", "4081023456789"),
	"NI": ("51/345/67890", "2351034567890"),
	"NW": ("123/4567/8901", "5123045678901"),
	"RP": ("61/345/67890", "2761034567890"),
	"SL": ("012/345/67890", "1012034567890"),
	"SN": ("201/234/56789", "3201023456789"),
	"ST": ("101/234/56789", "3101023456789"),
	"SH": ("81/345/67890", "2181034567890"),
	"TH": ("151/234/56789", "4151023456789"),
}

FULLWIDTH_DIGITS = str.maketrans("0123456789", "".join(chr(0xFF10 + digit) for digit in range(10)))
ARABIC_INDIC_ZERO = chr(0x0660)


class SchemeTableTest(TestCase):
	def test_states_and_schemes_follow_the_elster_table(self):
		self.assertEqual(
			[(STATES[code], scheme.standard, scheme.federal) for code, scheme in SCHEMES.items()],
			list(ELSTER_TABLE),
		)

	def test_states_carry_their_iso_codes(self):
		self.assertEqual(
			list(STATES),
			["BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH"],
		)
		self.assertEqual(set(SCHEMES), set(STATES))

	def test_state_codes_find_the_code_by_name(self):
		self.assertEqual(len(STATE_CODES), 16)
		for code, name in STATES.items():
			self.assertEqual(STATE_CODES[name], code)

	def test_every_federal_scheme_has_13_places_and_the_letters_of_its_standard_scheme(self):
		for code, scheme in SCHEMES.items():
			with self.subTest(state=code):
				self.assertEqual(len(scheme.federal), 13)
				letters = [char for char in scheme.standard if char.isalpha()]
				self.assertEqual([char for char in scheme.federal if char.isalpha()], letters)

	def test_tables_are_read_only(self):
		with self.assertRaises(TypeError):
			STATES["XX"] = "Nirgendwo"  # type: ignore[index]
		with self.assertRaises(TypeError):
			SCHEMES["BW"] = SCHEMES["BY"]  # type: ignore[index]
		with self.assertRaises(TypeError):
			STATE_CODES["Nirgendwo"] = "XX"  # type: ignore[index]


class ToElsterTest(TestCase):
	def test_converts_one_number_of_every_state(self):
		self.assertEqual(set(EXAMPLES), set(STATES))
		for code, (issued, elster) in EXAMPLES.items():
			with self.subTest(state=code):
				self.assertEqual(to_elster(code, issued), elster)

	def test_validate_accepts_the_issued_numbers(self):
		for code, (issued, _) in EXAMPLES.items():
			with self.subTest(state=code):
				self.assertIsNone(validate(code, issued))

	def test_accepts_the_digits_without_separators(self):
		self.assertEqual(to_elster("BW", "1234567890"), "2812034567890")
		self.assertEqual(to_elster("NW", "12345678901"), "5123045678901")
		self.assertEqual(to_elster("HE", "01234567890"), "2612034567890")

	def test_accepts_blanks_in_place_of_slashes_and_around_the_number(self):
		self.assertEqual(to_elster("HE", "012 345 67890"), "2612034567890")
		self.assertEqual(to_elster("BW", " 12/345/67890 "), "2812034567890")
		self.assertEqual(to_elster("BW", "12/345 67890"), "2812034567890")

	def test_states_with_the_same_federal_prefix_convert_alike(self):
		for code in ("BB", "SN", "ST"):
			self.assertEqual(to_elster(code, "201/234/56789"), "3201023456789")
		for code in ("MV", "TH"):
			self.assertEqual(to_elster(code, "151/234/56789"), "4151023456789")

	def test_refuses_a_number_of_another_shape(self):
		for code, issued in (
			("BW", "123/456/78901"),
			("BY", "12/345/67890"),
			("BY", "123/4567/8901"),
			("NW", "123/456/78901"),
			("BW", "12/345/6789"),
			("BW", "123456789"),
			("BW", "12345678901"),
			("BW", ""),
			("BW", "   "),
		):
			with (
				self.subTest(state=code, tax_number=issued),
				self.assertRaisesRegex(SteuernummerError, "not a Steuernummer of"),
			):
				to_elster(code, issued)

	def test_names_the_expected_shape(self):
		with self.assertRaisesRegex(SteuernummerError, r"Nordrhein-Westfalen: expected FFF/BBBB/UUUP"):
			to_elster("NW", "123/456/78901")

	def test_hessen_keeps_its_leading_zero(self):
		for issued in ("12/345/67890", "112/345/67890", "11234567890"):
			with (
				self.subTest(tax_number=issued),
				self.assertRaisesRegex(SteuernummerError, "expected 0FF/BBB/UUUUP"),
			):
				to_elster("HE", issued)

	def test_separators_stand_between_all_groups_or_none(self):
		for issued in ("12/34567890", "1234567/890", "12/345/678/90", "12//345/6789", "/12/345/67890"):
			with self.subTest(tax_number=issued), self.assertRaises(SteuernummerError):
				to_elster("BW", issued)

	def test_only_ascii_digits_count(self):
		for issued in (
			"12/345/6789O",
			"12/345/6789-",
			"12/345/67890".translate(FULLWIDTH_DIGITS),
			f"12/345/6789{ARABIC_INDIC_ZERO}",
			"12.345.67890",
		):
			with self.subTest(tax_number=issued), self.assertRaises(SteuernummerError):
				to_elster("BW", issued)

	def test_the_13_digit_form_is_not_the_issued_form(self):
		with self.assertRaises(SteuernummerError):
			to_elster("BW", "2812034567890")

	def test_refuses_a_number_of_nothing_but_zeros(self):
		"""Every digit of a Steuernummer stands for the Finanzamt, the Bezirk, the taxpayer or the check (ELSTER table
		above); a number of zeros names none of them, so it is refused without ERiC."""
		for state, number in (("NW", "000/0000/0000"), ("BY", "000 000 00000"), ("HE", "000/000/00000")):
			with self.subTest(state=state), self.assertRaises(ZeroSteuernummerError) as caught:
				to_elster(state, number)
			self.assertIsInstance(caught.exception, SteuernummerError)
		self.assertEqual(to_elster("NW", "000/0000/0001"), "5000000000001")

	def test_refuses_unknown_states(self):
		for state in ("XX", "bw", "Bayern", "", None, 9):
			with self.subTest(state=state), self.assertRaisesRegex(SteuernummerError, "unknown state"):
				to_elster(state, "12/345/67890")  # type: ignore[arg-type]

	def test_a_tax_number_is_text(self):
		for tax_number in (1234567890, None, b"12/345/67890"):
			with self.subTest(tax_number=tax_number), self.assertRaisesRegex(SteuernummerError, "is text"):
				validate("BW", tax_number)  # type: ignore[arg-type]


class FromElsterTest(TestCase):
	def test_converts_one_number_of_every_state_back(self):
		for code, (issued, elster) in EXAMPLES.items():
			with self.subTest(state=code):
				self.assertEqual(from_elster(code, elster), issued)

	def test_ignores_blanks_around_the_number(self):
		self.assertEqual(from_elster("BW", " 2812034567890 "), "12/345/67890")

	def test_refuses_a_number_of_another_state(self):
		with self.assertRaisesRegex(SteuernummerError, r"of Rheinland-Pfalz: expected 27FF0BBBUUUUP"):
			from_elster("RP", "2812034567890")

	def test_refuses_numbers_off_the_federal_scheme(self):
		for elster in (
			"2812134567890",
			"281203456789",
			"28120345678901",
			"28/12/0/345/67890",
			"281203456789O",
			"",
		):
			with (
				self.subTest(elster_tax_number=elster),
				self.assertRaisesRegex(SteuernummerError, "not a 13-digit Steuernummer"),
			):
				from_elster("BW", elster)

	def test_refuses_unknown_states_and_other_types(self):
		with self.assertRaisesRegex(SteuernummerError, "unknown state"):
			from_elster("XX", "2812034567890")
		with self.assertRaisesRegex(SteuernummerError, "is text"):
			from_elster("BW", 2812034567890)  # type: ignore[arg-type]
