"""The Anlagenspiegel (brutto) of the invented GmbH from the rows of its assets, on the mini taxonomy: rows, the rows
above them, the columns of the value development, value types and the checks a and e to j of Leitfaden B.14.12.1."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.ebilanz.anlagenspiegel import (
	BOOK_VALUE,
	CHANGES,
	TAX_TRANSFER,
	Row,
	ValueType,
	anlagenspiegel,
)
from steuerbote.ebilanz.calculation import calculate
from steuerbote.ebilanz.positions import structure
from steuerbote.ebilanz.tests.taxonomy import gaap, view
from steuerbote.ebilanz.tests.test_calculation import BOOKS, case
from steuerbote.xbrl.facts import Period

D = Decimal
HB, UE, STB = ValueType.HANDELSBILANZ, ValueType.UEBERLEITUNG, ValueType.STEUERBILANZ
SOFTWARE = Row(
	"bs.ass.fixAss.intan.concessionBrands",
	cost_begin=D("15000.00"),
	additions=D("3000.00"),
	depreciation_begin=D("4000.00"),
	depreciation_regular=D("2000.00"),
	source="Software",
)
LAND = Row("bs.ass.fixAss.tan", cost_begin=D("30000.00"), source="Grundstücke")


class EinheitsbilanzTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.calculation = calculate(structure(view(), case()), BOOKS)

	def of(self, *rows, first_year=False):
		return anlagenspiegel(
			self.calculation.structure,
			rows,
			handelsbilanz=self.calculation.amounts(),
			first_year=first_year,
		)

	def codes(self, *rows, **options) -> list[str]:
		return [finding.code for finding in self.of(*rows, **options).findings]

	def test_has_a_row_per_position_and_the_rows_above_it_in_steuerbilanzwerten(self):
		found = self.of(SOFTWARE, LAND)
		self.assertEqual(
			[(line.position, line.value_type) for line in found.lines],
			[
				(gaap("bs.ass.fixAss"), STB),
				(gaap("bs.ass.fixAss.intan"), STB),
				(gaap("bs.ass.fixAss.intan.concessionBrands"), STB),
				(gaap("bs.ass.fixAss.tan"), STB),
			],
		)
		self.assertEqual(found.findings, ())
		self.assertEqual(found.line("bs.ass.fixAss.intan.concessionBrands").rows, (SOFTWARE,))
		self.assertEqual(found.line("bs.ass.fixAss").rows, ())
		self.assertIsNone(found.line("bs.ass.fixAss", HB))

	def test_the_columns_add_up_as_the_anhang_says(self):
		software = self.of(SOFTWARE, LAND).line("bs.ass.fixAss.intan.concessionBrands")
		self.assertEqual(software.values[gaap("gross")], D("18000.00"))
		self.assertEqual(software.values[gaap("accDepr.DeprPeriod")], D("2000.00"))
		self.assertEqual(software.values[gaap("accDepr")], D("6000.00"))
		self.assertEqual(software.book_value, D("12000.00"))
		self.assertIsNone(software.values[gaap("revaluation")])

	def test_a_row_above_adds_up_the_rows_under_it(self):
		total = self.of(SOFTWARE, LAND).line("bs.ass.fixAss")
		self.assertEqual(total.values[gaap("gross")], D("48000.00"))
		self.assertEqual(total.book_value, D("42000.00"))

	def test_rows_of_the_same_position_add_up(self):
		halves = (
			Row("bs.ass.fixAss.tan", cost_begin=D("10000.00"), source="Grundstücke Nord"),
			Row("bs.ass.fixAss.tan", cost_begin=D("20000.00"), source="Grundstücke Süd"),
		)
		found = self.of(SOFTWARE, *halves)
		self.assertEqual(found.line("bs.ass.fixAss.tan").book_value, D("30000.00"))
		self.assertEqual(found.line("bs.ass.fixAss.tan").rows, halves)
		self.assertEqual(found.findings, ())

	def test_sends_each_column_in_its_scenario_and_the_mussfelder_without_amount_as_nil(self):
		"""Leitfaden B.14.12.1 a, A.14.2.1."""
		facts = self.of(SOFTWARE, LAND).facts()
		row = ((CHANGES, gaap("bs.ass.fixAss.tan")), (TAX_TRANSFER, STB.value))
		values = {item.concept: item.value for item in facts if item.dimensions == row}
		self.assertEqual(values[BOOK_VALUE], D("30000.00"))
		self.assertIsNone(values[gaap("gross.movements")])
		self.assertIsNone(values[gaap("accDepr.DeprPeriod.EStG7g_2")])
		self.assertNotIn(gaap("gross.release"), values)
		self.assertNotIn(gaap("all_Prev_period"), values)
		self.assertTrue(all(item.period is Period.WIRTSCHAFTSJAHR for item in facts))

	def test_without_assets_sends_the_anlagevermoegen_with_a_buchwert_of_zero(self):
		"""As the Eröffnungsbilanz of the ERiC documentation does (Leitfaden B.9.2)."""
		opening = calculate(structure(view(), case()), BOOKS[2:4])
		found = anlagenspiegel(opening.structure, (), handelsbilanz=opening.amounts())
		(line,) = found.lines
		self.assertEqual((line.position, line.book_value), (gaap("bs.ass.fixAss"), D("0")))
		self.assertEqual(found.findings, ())

	def test_the_buchwert_is_that_of_the_bilanz(self):
		"""Leitfaden B.14.12.1 f; structural error 170185136."""
		self.assertEqual(self.codes(), ["170185136"])
		found = self.of(SOFTWARE)
		self.assertEqual(
			[(finding.code, finding.reference) for finding in found.findings],
			[("170185136", "bs.ass.fixAss")],
		)
		self.assertIn("12.000,00 €", found.findings[0].text)

	def test_the_previous_buchwert_is_the_cost_less_the_depreciation_at_the_beginning(self):
		"""Leitfaden B.14.12.1 h; structural error 170185137."""
		kept = Row(
			"bs.ass.fixAss.intan.concessionBrands",
			cost_begin=D("15000.00"),
			additions=D("3000.00"),
			depreciation_begin=D("4000.00"),
			depreciation_regular=D("2000.00"),
			prior_book_value=D("11000.00"),
			source="Software",
		)
		land = Row(
			"bs.ass.fixAss.tan",
			cost_begin=D("30000.00"),
			prior_book_value=D("30000.00"),
			source="Grundstücke",
		)
		found = self.of(kept, land)
		self.assertEqual(found.findings, ())
		self.assertEqual(found.line("bs.ass.fixAss").values[gaap("all_Prev_period")], D("41000.00"))
		wrong = Row(
			"bs.ass.fixAss.tan",
			cost_begin=D("30000.00"),
			prior_book_value=D("29000.00"),
			source="Grundstücke",
		)
		self.assertEqual(self.codes(SOFTWARE, wrong), ["170185137", "170185137"])

	def test_in_the_first_year_nothing_begins_with_an_amount(self):
		self.assertEqual(
			self.codes(SOFTWARE, LAND, first_year=True),
			["EB-ANLAGENSPIEGEL-ANFANG", "EB-ANLAGENSPIEGEL-ANFANG", "EB-ANLAGENSPIEGEL-ANFANG"],
		)

	def test_a_column_or_a_row_by_hand_says_why(self):
		writeup = Row(
			"bs.ass.fixAss.tan", cost_begin=D("29000.00"), writeups=D("1000.00"), source="Grundstücke"
		)
		self.assertEqual(self.codes(SOFTWARE, writeup), ["EB-ANLAGENSPIEGEL-BEGRUENDUNG"])
		explained = Row(
			"bs.ass.fixAss.tan",
			cost_begin=D("29000.00"),
			writeups=D("1000.00"),
			source="Grundstücke",
			reason="Wertaufholung nach § 6 Abs. 1 Nr. 2 Satz 3 EStG",
		)
		self.assertEqual(self.codes(SOFTWARE, explained), [])
		self.assertEqual(explained.manual, ("writeups",))
		by_hand = Row("bs.ass.fixAss.tan", cost_begin=D("30000.00"))
		self.assertEqual(self.codes(SOFTWARE, by_hand), ["EB-ANLAGENSPIEGEL-BEGRUENDUNG"])

	def test_refuses_a_row_of_no_position_of_the_case_and_a_value_type_of_a_handelsbilanz(self):
		"""Leitfaden B.14.12.1 f and j."""
		found = self.of(
			SOFTWARE,
			LAND,
			Row("bs.ass.fixAss.intan.selfmade", cost_begin=D("1.00"), source="Entwicklung"),
			Row("bs.ass.currAss", cost_begin=D("1.00"), source="Vorräte"),
			Row("bs.ass.fixAss.unknown", cost_begin=D("1.00"), source="?"),
			Row("bs.ass.fixAss.tan", HB, cost_begin=D("1.00"), source="Grundstücke"),
		)
		self.assertEqual(
			[(finding.code, finding.reference) for finding in found.findings],
			[
				("EB-ANLAGENSPIEGEL-ZEILE", "bs.ass.fixAss.intan.selfmade"),
				("EB-ANLAGENSPIEGEL-ZEILE", "bs.ass.currAss"),
				("EB-ANLAGENSPIEGEL-ZEILE", "bs.ass.fixAss.unknown"),
				("EB-ANLAGENSPIEGEL-WERT", "bs.ass.fixAss.tan"),
			],
		)
		self.assertIn("nur Steuerbilanzwerte", found.findings[-1].text)


class HandelsbilanzTest(TestCase):
	"""Leitfaden B.14.12.1 c, d, e and i."""

	@classmethod
	def setUpClass(cls):
		cls.structure = structure(view(), case(accounting_standard="HGBM"))
		cls.handelsbilanz = {
			(gaap("bs.ass.fixAss"), Period.STICHTAG): D("47000.00"),
			(gaap("bs.ass.fixAss.intan"), Period.STICHTAG): D("17000.00"),
			(gaap("bs.ass.fixAss.intan.selfmade"), Period.STICHTAG): D("5000.00"),
		}
		cls.steuerbilanz = {
			(gaap("bs.ass.fixAss"), Period.STICHTAG): D("42000.00"),
			(gaap("bs.ass.fixAss.intan"), Period.STICHTAG): D("12000.00"),
		}

	def of(self, *rows):
		return anlagenspiegel(
			self.structure, rows, handelsbilanz=self.handelsbilanz, steuerbilanz=self.steuerbilanz
		)

	def rows(self, transfer: str = "-5000.00"):
		return (
			Row("bs.ass.fixAss.intan.concessionBrands", HB, cost_begin=D("12000.00"), source="Software"),
			Row("bs.ass.fixAss.intan.selfmade", HB, additions=D("5000.00"), source="Entwicklung"),
			Row("bs.ass.fixAss.intan.selfmade", UE, additions=D(transfer), source="Entwicklung"),
			Row("bs.ass.fixAss.tan", HB, cost_begin=D("30000.00"), source="Grundstücke"),
		)

	def test_derives_the_steuerbilanzwerte_from_handelsbilanzwerten_and_ueberleitungswerten(self):
		found = self.of(*self.rows())
		lines = {(line.position, line.value_type): line for line in found.lines}
		self.assertEqual(lines[(gaap("bs.ass.fixAss.intan"), HB)].book_value, D("17000.00"))
		self.assertEqual(lines[(gaap("bs.ass.fixAss.intan"), UE)].book_value, D("-5000.00"))
		self.assertEqual(lines[(gaap("bs.ass.fixAss.intan"), STB)].book_value, D("12000.00"))
		self.assertEqual(lines[(gaap("bs.ass.fixAss.tan"), STB)].book_value, D("30000.00"))
		self.assertEqual(found.findings, ())

	def test_sends_the_steuerbilanzwert_zero_of_a_position_steuerlich_not_permitted(self):
		"""With Überleitungswerten the Anlagenspiegel holds Handels- and Steuerbilanzwerte of every position (Leitfaden
		B.14.12.1 c), the Steuerbilanzwert of a position „steuerlich“ not permitted being zero (i). ERiC 44.3.6.0 refuses
		it without the Steuerbilanzwert with structural error 170185133 (validation of Bilanz_6.9)."""
		found = self.of(*self.rows())
		self.assertIsNotNone(found.line("bs.ass.fixAss.intan.selfmade", HB))
		self.assertEqual(found.line("bs.ass.fixAss.intan.selfmade", STB).book_value, D("0.00"))
		self.assertEqual(found.findings, ())

	def test_its_handelsbilanzwert_and_ueberleitungswert_add_up_to_zero(self):
		found = self.of(*self.rows(transfer="-4000.00"))
		codes = [finding.code for finding in found.findings]
		self.assertIn("EB-ANLAGENSPIEGEL-STEUERLICH", codes)
		self.assertIn("170185136", codes)

	def test_a_handelsbilanz_without_ueberleitung_sends_handelsbilanzwerte_only(self):
		found = anlagenspiegel(
			self.structure,
			(Row("bs.ass.fixAss.tan", HB, cost_begin=D("30000.00"), source="Grundstücke"),),
			handelsbilanz={},
		)
		self.assertEqual({line.value_type for line in found.lines}, {HB})

	def test_takes_no_steuerbilanzwerte_of_its_own(self):
		found = self.of(Row("bs.ass.fixAss.tan", STB, cost_begin=D("30000.00"), source="Grundstücke"))
		self.assertEqual(found.findings[0].code, "EB-ANLAGENSPIEGEL-WERT")
		self.assertIn("leitet", found.findings[0].text)


class RowTest(TestCase):
	def test_takes_amounts_in_euros_and_cents(self):
		for value in (D("1.001"), 1, True):
			with self.subTest(value=value), self.assertRaises(ValueError):
				Row("bs.ass.fixAss.tan", cost_begin=value)
		row = Row("bs.ass.fixAss.tan", "de-gaap-ci:dim_comBal", additions=D("1.00"))
		self.assertEqual((row.position, row.value_type), (gaap("bs.ass.fixAss.tan"), HB))
		self.assertEqual(row.amounts(), {gaap("gross.addition"): D("1.00")})
		self.assertEqual(ValueType.UEBERLEITUNG.label, "Überleitungswert")
