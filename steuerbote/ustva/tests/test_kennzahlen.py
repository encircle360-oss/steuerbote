from dataclasses import replace
from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva.kennzahlen import (
	BALANCE_KENNZAHL,
	CATALOGUES,
	INPUT_TAX_LINES,
	KENNZAHLEN,
	LATEST_YEAR,
	OTHER_TAX_LINES,
	OUTPUT_TAX_LINES,
	SONDERVORAUSZAHLUNG_KENNZAHL,
	Effect,
	Kennzahl,
	Kind,
	UnknownYearError,
	_index,
	catalogue_for,
)

B, T, F, D, C = Kind.BASE, Kind.TAX, Kind.FLAG, Kind.DATE, Kind.CODE
NONE, UP, DOWN = Effect.NONE, Effect.INCREASES, Effect.REDUCES

# Kennzahl: (line, kind, effect, rate, tax Kennzahl) as printed on form USt 1 A 2026.
FORM_UST_1_A_2026 = {
	"10": (10, F, NONE, None, None),
	"22": (11, F, NONE, None, None),
	"70": (12, D, NONE, None, None),
	"81": (13, B, UP, "19", None),
	"86": (14, B, UP, "7", None),
	"87": (15, B, NONE, None, None),
	"35": (16, B, NONE, None, "36"),
	"36": (16, T, UP, None, None),
	"77": (17, B, NONE, None, None),
	"76": (18, B, NONE, None, "80"),
	"80": (18, T, UP, None, None),
	"41": (19, B, NONE, None, None),
	"44": (20, B, NONE, None, None),
	"49": (21, B, NONE, None, None),
	"43": (22, B, NONE, None, None),
	"48": (23, B, NONE, None, None),
	"91": (24, B, NONE, None, None),
	"89": (25, B, UP, "19", None),
	"93": (26, B, UP, "7", None),
	"90": (27, B, NONE, None, None),
	"95": (28, B, NONE, None, "98"),
	"98": (28, T, UP, None, None),
	"94": (29, B, NONE, None, "96"),
	"96": (29, T, UP, None, None),
	"46": (30, B, NONE, None, "47"),
	"47": (30, T, UP, None, None),
	"73": (31, B, NONE, None, "74"),
	"74": (31, T, UP, None, None),
	"84": (32, B, NONE, None, "85"),
	"85": (32, T, UP, None, None),
	"42": (33, B, NONE, None, None),
	"60": (34, B, NONE, None, None),
	"21": (35, B, NONE, None, None),
	"45": (36, B, NONE, None, None),
	"66": (38, T, DOWN, None, None),
	"61": (39, T, DOWN, None, None),
	"62": (40, T, DOWN, None, None),
	"67": (41, T, DOWN, None, None),
	"63": (42, T, DOWN, None, None),
	"59": (43, T, DOWN, None, None),
	"64": (44, T, DOWN, None, None),
	"65": (46, T, UP, None, None),
	"69": (47, T, UP, None, None),
	"39": (49, T, DOWN, None, None),
	"83": (50, T, NONE, None, None),
	"50": (51, B, NONE, None, None),
	"37": (52, T, NONE, None, None),
	"29": (53, F, NONE, None, None),
	"26": (54, F, NONE, None, None),
	"500": (55, C, NONE, None, None),
}
CATALOGUE_2026 = CATALOGUES[2026]


class CatalogueTest(TestCase):
	def test_covers_exactly_the_kennzahlen_of_form_ust_1_a_2026(self):
		self.assertEqual(set(CATALOGUE_2026), set(FORM_UST_1_A_2026))

	def test_every_kennzahl_matches_the_form(self):
		for number, (line, kind, effect, rate, tax_kennzahl) in FORM_UST_1_A_2026.items():
			kennzahl = CATALOGUE_2026[number]
			with self.subTest(kennzahl=number):
				self.assertEqual(kennzahl.number, number)
				self.assertEqual(kennzahl.line, line)
				self.assertIs(kennzahl.kind, kind)
				self.assertIs(kennzahl.effect, effect)
				self.assertEqual(kennzahl.rate, Decimal(rate) if rate else None)
				self.assertEqual(kennzahl.tax_kennzahl, tax_kennzahl)
				self.assertTrue(kennzahl.label)

	def test_form_derives_the_tax_only_for_the_19_and_7_percent_bases(self):
		derived = {number for number, kennzahl in CATALOGUE_2026.items() if kennzahl.derives_tax}
		self.assertEqual(derived, {"81", "86", "89", "93"})

	def test_bases_with_a_separate_tax_point_to_a_tax_kennzahl_on_the_same_line(self):
		for year, catalogue in CATALOGUES.items():
			for kennzahl in catalogue.values():
				if kennzahl.tax_kennzahl is not None:
					tax = catalogue[kennzahl.tax_kennzahl]
					with self.subTest(year=year, kennzahl=kennzahl.number):
						self.assertIs(tax.kind, Kind.TAX)
						self.assertEqual(tax.line, kennzahl.line)
						self.assertIs(tax.effect, Effect.INCREASES)

	def test_holds_amount(self):
		self.assertTrue(CATALOGUE_2026["81"].holds_amount)
		self.assertTrue(CATALOGUE_2026["66"].holds_amount)
		for number in ("10", "70", "500"):
			self.assertFalse(CATALOGUE_2026[number].holds_amount, number)

	def test_the_sums_of_the_form(self):
		self.assertEqual(BALANCE_KENNZAHL, "83")
		self.assertEqual(SONDERVORAUSZAHLUNG_KENNZAHL, "39")
		increases = {k.line for k in CATALOGUE_2026.values() if k.effect is Effect.INCREASES}
		reduces = {k.line for k in CATALOGUE_2026.values() if k.effect is Effect.REDUCES}
		self.assertEqual(increases - set(OUTPUT_TAX_LINES), set(OTHER_TAX_LINES))
		self.assertEqual(reduces - set(INPUT_TAX_LINES), {CATALOGUE_2026["39"].line})

	def test_catalogue_is_read_only(self):
		with self.assertRaises(TypeError):
			CATALOGUE_2026["81"] = CATALOGUE_2026["86"]  # type: ignore[index]

	def test_duplicate_numbers_are_rejected(self):
		kennzahl = Kennzahl("81", 13, "x", Kind.BASE, Effect.INCREASES, Decimal("19"))
		with self.assertRaisesRegex(ValueError, "81"):
			_index((kennzahl, kennzahl))


class FormSumsTest(TestCase):
	"""Every Kennzahl that changes the amount owed has to enter one of the sums the form computes."""

	def test_every_kennzahl_with_an_effect_enters_exactly_one_sum_in_every_catalogue(self):
		for year, catalogue in CATALOGUES.items():
			for kennzahl in catalogue.values():
				if kennzahl.effect is Effect.NONE:
					continue
				sums = (
					kennzahl.effect is Effect.INCREASES and kennzahl.line in OUTPUT_TAX_LINES,
					kennzahl.effect is Effect.REDUCES and kennzahl.line in INPUT_TAX_LINES,
					kennzahl.effect is Effect.INCREASES and kennzahl.line in OTHER_TAX_LINES,
					kennzahl.number == SONDERVORAUSZAHLUNG_KENNZAHL,
				)
				with self.subTest(year=year, kennzahl=kennzahl.number):
					self.assertEqual(sums.count(True), 1)
			with self.subTest(year=year):
				self.assertEqual(dict(_index(tuple(catalogue.values()))), dict(catalogue))

	def test_catalogue_with_a_kennzahl_outside_the_sums_is_rejected(self):
		moved = tuple(replace(k, line=37) if k.number == "66" else k for k in CATALOGUE_2026.values())
		with self.assertRaisesRegex(ValueError, "Kennzahl 66 on line 37 changes the amount owed"):
			_index(moved)

	def test_effects_must_fit_the_sum_of_their_line(self):
		broken = {
			"output tax that reduces": Kennzahl("47", 30, "x", Kind.TAX, Effect.REDUCES),
			"input tax that increases": Kennzahl("66", 38, "x", Kind.TAX, Effect.INCREASES),
			"tax between the sums": Kennzahl("36", 33, "x", Kind.TAX, Effect.INCREASES),
			"tax after the sums": Kennzahl("69", 48, "x", Kind.TAX, Effect.INCREASES),
			"base with a rate outside lines 13 to 32": Kennzahl(
				"81", 45, "x", Kind.BASE, Effect.INCREASES, Decimal("19")
			),
		}
		for case, kennzahl in broken.items():
			with (
				self.subTest(case),
				self.assertRaisesRegex(ValueError, f"Kennzahl {kennzahl.number} on line"),
			):
				_index((kennzahl,))

	def test_sondervorauszahlung_is_a_sum_of_its_own_and_kennzahlen_without_effect_need_none(self):
		sondervorauszahlung = Kennzahl(SONDERVORAUSZAHLUNG_KENNZAHL, 49, "x", Kind.TAX, Effect.REDUCES)
		base_without_effect = Kennzahl("21", 35, "x", Kind.BASE)
		catalogue = _index((sondervorauszahlung, base_without_effect))
		self.assertEqual(set(catalogue), {"39", "21"})


class KennzahlInvariantsTest(TestCase):
	def test_only_a_base_carries_a_rate(self):
		with self.assertRaisesRegex(ValueError, "only a base carries a rate"):
			Kennzahl("66", 38, "x", Kind.TAX, Effect.REDUCES, Decimal("19"))

	def test_only_a_base_points_to_a_tax_kennzahl(self):
		with self.assertRaisesRegex(ValueError, "only a base points"):
			Kennzahl("36", 16, "x", Kind.TAX, Effect.INCREASES, tax_kennzahl="35")

	def test_a_base_derives_or_reports_its_tax_not_both(self):
		with self.assertRaisesRegex(ValueError, "not both"):
			Kennzahl("81", 13, "x", Kind.BASE, Effect.INCREASES, Decimal("19"), "36")

	def test_a_base_without_rate_cannot_change_the_amount_owed(self):
		with self.assertRaisesRegex(ValueError, "cannot change the amount owed"):
			Kennzahl("41", 19, "x", Kind.BASE, Effect.INCREASES)

	def test_flags_cannot_change_the_amount_owed(self):
		with self.assertRaisesRegex(ValueError, "only amounts change"):
			Kennzahl("10", 10, "x", Kind.FLAG, Effect.INCREASES)


class CatalogueByYearTest(TestCase):
	def test_latest_year_is_the_newest_catalogue(self):
		self.assertEqual(LATEST_YEAR, max(CATALOGUES))
		self.assertIs(catalogue_for(LATEST_YEAR), KENNZAHLEN)
		self.assertIs(catalogue_for(2026), CATALOGUES[2026])

	def test_unknown_year_is_refused_with_the_known_years(self):
		with self.assertRaisesRegex(UnknownYearError, "no Kennzahlen catalogue for 2019; known years: 2026"):
			catalogue_for(2019)
		self.assertTrue(issubclass(UnknownYearError, ValueError))

	def test_registry_is_read_only(self):
		with self.assertRaises(TypeError):
			CATALOGUES[2027] = KENNZAHLEN  # type: ignore[index]
