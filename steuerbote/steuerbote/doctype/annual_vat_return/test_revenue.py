"""The Umsatzerlöse of the year against the sales of the Umsatzsteuererklärung 2026, without a bench: the lines that
hold the Lieferungen und sonstigen Leistungen, the rounding of the lines and the tolerance, and the hint by the source
of the Umsatzerlöse. Every name and amount is invented."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.steuerbote.doctype.annual_vat_return import revenue
from steuerbote.steuerbote.doctype.annual_vat_return.revenue import Revenue, Source
from steuerbote.ustjahr.form import Severity, catalogue_for

CATALOGUE = catalogue_for(2026)
SALES_19 = "E3003303"
"""Line 24, Kz 177: Lieferungen und sonstige Leistungen zu 19 %."""
WERTABGABE_19 = "E3003405"
"""Line 25, Kz 178: Lieferungen nach § 3 Absatz 1b UStG zu 19 %."""
EU_SALES = "E3103301"
"""Line 42, Kz 741: innergemeinschaftliche Lieferungen an Abnehmer mit Umsatzsteuer-Identifikationsnummer."""
VORSTEUER = "E3006201"
"""Line 85, Kz 320: Vorsteuerbeträge aus Rechnungen von anderen Unternehmern."""
TOLERANCE = Decimal("100")
ACCOUNTS = Revenue(Decimal("250000.40"), Source.ACCOUNTS, "JA-2026-00001")


def d(value: str) -> Decimal:
	return Decimal(value)


def amounts(**values: str) -> dict[str, Decimal]:
	named = {"sales": SALES_19, "wertabgabe": WERTABGABE_19, "eu": EU_SALES, "vorsteuer": VORSTEUER}
	return {named[key]: d(value) for key, value in values.items()}


class SalesFieldsTest(TestCase):
	def test_the_lines_of_the_lieferungen_und_sonstigen_leistungen(self):
		self.assertEqual(
			[field.line for field in revenue.sales_fields(CATALOGUE)],
			[24, 27, 30, 33, 34, 35, 42, 43, 44, 45, 46, 47, 48, 49, 51, 52, 53, 54, 65, 76, 78, 80, 81],
		)

	def test_the_unentgeltlichen_wertabgaben_earn_no_umsatzerloese(self):
		lines = {field.line for field in revenue.sales_fields(CATALOGUE)}
		self.assertEqual(lines & {25, 26, 28, 29, 31, 32}, set())

	def test_every_line_takes_a_kennzahl_of_the_sales_of_the_voranmeldung(self):
		for field in revenue.sales_fields(CATALOGUE):
			with self.subTest(line=field.line):
				self.assertIn(field.ustva, revenue.SALES)
				self.assertTrue(field.format.whole_euros)


class FindingsTest(TestCase):
	def found(self, given: Revenue | None, tolerance: Decimal = TOLERANCE, **values: str):
		return revenue.findings(CATALOGUE, amounts(**values), given, tolerance)

	def test_a_year_without_umsatzerloese_compares_nothing(self):
		self.assertEqual(self.found(None, sales="1000"), ())

	def test_the_cents_of_a_line_are_no_difference(self):
		self.assertEqual(self.found(ACCOUNTS, tolerance=d("0"), sales="250000"), ())

	def test_a_difference_within_a_euro_a_line_and_the_tolerance_gives_no_hint(self):
		self.assertEqual(self.found(ACCOUNTS, sales="200000", eu="49899"), ())
		(hint,) = self.found(ACCOUNTS, sales="200000", eu="49898")
		self.assertEqual(hint.values[4], "102.40")

	def test_the_hint_names_both_figures_the_lines_and_the_difference(self):
		(hint,) = self.found(ACCOUNTS, sales="240000", eu="5000", wertabgabe="3000", vorsteuer="7000")
		self.assertEqual((hint.code, hint.severity), ("SB-UMSATZERLOESE", Severity.HINT))
		self.assertFalse(hint.blocking)
		self.assertEqual(hint.fields, (SALES_19, EU_SALES))
		self.assertEqual(
			hint.text,
			"The Umsatzerlöse of the festgestellter Jahresabschluss JA-2026-00001 are 250000.40 euros, the "
			"Bemessungsgrundlagen of the Lieferungen und sonstigen Leistungen of the return 245000.00 euros (lines 24, "
			"42): a difference of 5000.40 euros, more than a euro a line and the tolerance of 100.00 euros. Sales of "
			"fixed assets, Anzahlungen and Erlöse that no line of the return takes explain such a difference; check it.",
		)

	def test_sales_beyond_the_umsatzerloese_give_a_negative_difference(self):
		(hint,) = self.found(ACCOUNTS, sales="260000")
		self.assertEqual(hint.values[2:5], ("260000.00", "24", "-9999.60"))

	def test_the_umsatzerloese_of_a_filed_e_bilanz(self):
		filed = Revenue(d("250000.40"), Source.EBILANZ, "EB-2026-00001")
		(hint,) = self.found(filed, sales="200000")
		self.assertEqual(hint.template, revenue.FROM_EBILANZ)
		self.assertTrue(
			hint.text.startswith("The Umsatzerlöse of the filed E-Bilanz EB-2026-00001 are 250000.40 euros")
		)

	def test_a_return_without_sales_says_so(self):
		(hint,) = self.found(ACCOUNTS, vorsteuer="7000")
		self.assertEqual((hint.template, hint.fields), (revenue.NONE_FROM_ACCOUNTS, ()))
		self.assertTrue(
			hint.text.startswith("The Umsatzerlöse of the festgestellter Jahresabschluss JA-2026-00001")
		)
		filed = Revenue(d("250000.40"), Source.EBILANZ, "EB-2026-00001")
		(hint,) = self.found(filed)
		self.assertEqual(hint.template, revenue.NONE_FROM_EBILANZ)

	def test_the_messages_are_those_of_the_hint(self):
		self.assertEqual(
			revenue.MESSAGES,
			(
				revenue.FROM_ACCOUNTS,
				revenue.FROM_EBILANZ,
				revenue.NONE_FROM_ACCOUNTS,
				revenue.NONE_FROM_EBILANZ,
			),
		)
