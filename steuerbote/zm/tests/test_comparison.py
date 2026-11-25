from datetime import date
from unittest import TestCase

from steuerbote.steuerbote.report.ustva_kennzahlen.comparison import Thresholds
from steuerbote.zm.comparison import Earlier, before_start, compare, comparison_hints, earlier
from steuerbote.zm.findings import Code
from steuerbote.zm.lines import Art, Override, build
from steuerbote.zm.period import ReportingPeriod
from steuerbote.zm.rhythm import Coverage, Rhythm, Rule, coverage
from steuerbote.zm.tests.support import AUSTRIA, FIGURES, FRANCE, SPAIN, d, invoice

MARCH = ReportingPeriod.month(2026, 3)
MAY = ReportingPeriod.month(2026, 5)
BEFORE_APRIL = Earlier(Coverage(MARCH, (3,), (3,)), Coverage(MARCH, (3,), (3,)))


def statement(*amounts, overrides=None):
	return build(amounts, FIGURES, overrides=overrides)


def month(number: int, year: int = 2026) -> ReportingPeriod:
	return ReportingPeriod.month(year, number)


class EarlierTest(TestCase):
	"""The Lieferungen compare with the previous Meldezeitraum of the same kind, the sonstige Leistungen with the
	last earlier one that reports them (§ 18a Absatz 2 Satz 2 UStG)."""

	MONTHLY = (Rule(2026, 1, Rhythm.MONTHLY),)

	def test_june_compares_the_sonstige_leistungen_of_its_quarter_with_march(self):
		before = earlier(self.MONTHLY, coverage(self.MONTHLY, month(6)))
		self.assertEqual(before.goods, Coverage(MAY, (5,), ()))
		self.assertEqual(before.services, Coverage(MARCH, (3,), (1, 2, 3)))
		self.assertEqual(before.arts, (Art.L, Art.D, Art.S))
		self.assertEqual([before.period(art) for art in (Art.L, Art.D, Art.S)], [MAY, MAY, MARCH])

	def test_july_holds_no_sonstige_leistungen_and_compares_none(self):
		before = earlier(self.MONTHLY, coverage(self.MONTHLY, month(7)))
		self.assertEqual((before.goods, before.services), (Coverage(month(6), (6,), (4, 5, 6)), None))
		self.assertEqual(before.arts, (Art.L, Art.D))
		self.assertEqual(before.period(Art.S), month(6))

	def test_each_month_with_its_own_sonstige_leistungen(self):
		rules = (Rule(2026, 1, Rhythm.MONTHLY, services_monthly=True),)
		before = earlier(rules, coverage(rules, month(6)))
		self.assertEqual(
			(before.goods, before.services), (Coverage(MAY, (5,), (5,)), Coverage(MAY, (5,), (5,)))
		)

	def test_a_quarter_and_the_months_before_the_first_rule(self):
		rules = (Rule(2026, 1, Rhythm.QUARTERLY),)
		first, second = ReportingPeriod.quarter(2026, 1), ReportingPeriod.quarter(2026, 2)
		self.assertEqual(
			earlier(rules, coverage(rules, second)).services, Coverage(first, (1, 2, 3), (1, 2, 3))
		)
		fourth = ReportingPeriod.quarter(2025, 4)
		self.assertEqual(
			earlier(rules, coverage(rules, first)).services, Coverage(fourth, (10, 11, 12), (10, 11, 12))
		)
		before = earlier(self.MONTHLY, coverage(self.MONTHLY, MARCH))
		self.assertEqual(before.goods, Coverage(month(2), (2,), ()))
		self.assertEqual(before.services, Coverage(month(12, 2025), (12,), (12,)))


class CompareTest(TestCase):
	"""The ZM beside the previous Meldezeitraum, with the rule of the report „UStVA Kennzahlen“: a change exceeds
	both thresholds of the VAT Return Settings, 50 % and 100 euros unless set."""

	def test_a_row_per_line_of_either_period(self):
		current = statement(invoice("1", "12000.00"), invoice("2", "300.00", kennzahl="21", vat_id=SPAIN))
		previous = statement(invoice("0", "5000.00"), invoice("9", "800.00", vat_id=FRANCE))
		rows = compare(current, previous, Thresholds().exceeded)
		self.assertEqual(
			[(row.vat_id, row.art, row.current, row.previous) for row in rows],
			[
				(AUSTRIA, Art.L, d("12000"), d("5000")),
				(SPAIN, Art.S, d("300"), d("0")),
				(FRANCE, Art.L, d("0"), d("800")),
			],
		)
		self.assertEqual([row.flagged for row in rows], [True, True, True])
		self.assertEqual([row.difference for row in rows], [d("7000"), d("300"), d("-800")])
		self.assertEqual([row.difference_percent for row in rows], [d("140.00"), None, d("-100.00")])

	def test_only_the_arts_with_an_earlier_meldezeitraum(self):
		current = statement(invoice("1", "100.00"), invoice("2", "300.00", kennzahl="21", vat_id=SPAIN))
		previous = statement(invoice("9", "900.00", kennzahl="21", vat_id=FRANCE))
		rows = compare(current, previous, Thresholds().exceeded, (Art.L, Art.D))
		self.assertEqual([(row.vat_id, row.art) for row in rows], [(AUSTRIA, Art.L)])

	def test_small_changes_are_not_flagged(self):
		rows = compare(
			statement(invoice("1", "1050.00")), statement(invoice("0", "1000.00")), Thresholds().exceeded
		)
		self.assertEqual([row.flagged for row in rows], [False])
		thresholds = Thresholds.of(1, 10)
		self.assertEqual(
			[
				row.flagged
				for row in compare(
					statement(invoice("1", "1050.00")),
					statement(invoice("0", "1000.00")),
					thresholds.exceeded,
				)
			],
			[True],
		)

	def test_the_amounts_as_reported(self):
		current = statement(
			invoice("1", "99.99"), overrides={(AUSTRIA, Art.L): Override(d("500"), "Nachberechnung")}
		)
		rows = compare(current, statement(invoice("0", "99.99")), Thresholds().exceeded)
		self.assertEqual([(row.current, row.previous) for row in rows], [(d("500"), d("99"))])

	def test_lines_that_report_nothing_are_left_out(self):
		rows = compare(
			statement(invoice("1", "0.50"), invoice("2", "10.00", party=None, vat_id=None)),
			statement(),
			Thresholds().exceeded,
		)
		self.assertEqual(rows, ())


class HintsTest(TestCase):
	def test_a_hint_per_flagged_row(self):
		current = statement(
			invoice("1", "12000.00"),
			invoice("2", "300.00", kennzahl="21", vat_id=SPAIN),
			invoice("3", "100.00", vat_id=FRANCE),
		)
		previous = statement(invoice("0", "5000.00"), invoice("9", "100.00", vat_id=FRANCE))
		hints = comparison_hints(compare(current, previous, Thresholds().exceeded), BEFORE_APRIL, FIGURES)
		self.assertEqual([hint.code for hint in hints], [Code.PREVIOUS_PERIOD, Code.PREVIOUS_PERIOD])
		self.assertEqual(
			[hint.text for hint in hints],
			[
				f"Die Zeile {AUSTRIA} (L) liegt mit 12.000,00 € um 140,0 % über der Vorperiode März 2026 (5.000,00 €).",
				f"Die Zeile {SPAIN} (S) liegt mit 300,00 € über der Vorperiode März 2026 (0,00 €).",
			],
		)
		self.assertFalse(hints[0].blocking)

	def test_a_line_that_falls(self):
		rows = compare(statement(), statement(invoice("0", "800.00")), Thresholds().exceeded)
		self.assertEqual(
			comparison_hints(rows, BEFORE_APRIL, FIGURES)[0].text,
			f"Die Zeile {AUSTRIA} (L) liegt mit 0,00 € um 100,0 % unter der Vorperiode März 2026 (800,00 €).",
		)

	def test_each_art_names_the_meldezeitraum_it_is_set_against(self):
		before = Earlier(Coverage(MAY, (5,), ()), Coverage(MARCH, (3,), (1, 2, 3)))
		current = statement(invoice("1", "900.00"), invoice("2", "300.00", kennzahl="21", vat_id=SPAIN))
		texts = [
			hint.text
			for hint in comparison_hints(
				compare(current, statement(), Thresholds().exceeded), before, FIGURES
			)
		]
		self.assertEqual(
			texts,
			[
				f"Die Zeile {AUSTRIA} (L) liegt mit 900,00 € über der Vorperiode Mai 2026 (0,00 €).",
				f"Die Zeile {SPAIN} (S) liegt mit 300,00 € über der Vorperiode März 2026 (0,00 €).",
			],
		)


class BeforeTheStartTest(TestCase):
	"""Before the start of the books in Steuerbote the ledger holds no lines to compare with."""

	def test_a_meldezeitraum_before_the_start_is_not_compared(self):
		before = Earlier(Coverage(ReportingPeriod.quarter(2026, 4), (10, 11, 12), ()), None)
		finding = before_start(before, date(2027, 1, 1))
		self.assertEqual(finding.code, Code.BEFORE_START)
		self.assertFalse(finding.blocking)
		self.assertEqual(
			finding.text,
			"Kein Vorperiodenvergleich mit IV. Kalendervierteljahr 2026: Es liegt vor dem Start der Bücher in "
			"Steuerbote am 1. Januar 2027.",
		)

	def test_the_sonstige_leistungen_compare_with_their_own_meldezeitraum(self):
		before = Earlier(Coverage(month(1, 2027), (1,), ()), Coverage(month(12), (12,), (10, 11, 12)))
		self.assertIn("Dezember 2026", before_start(before, date(2027, 1, 1)).text)
		self.assertIsNone(before_start(before, date(2026, 12, 1)))

	def test_without_a_start_everything_is_compared(self):
		self.assertIsNone(before_start(BEFORE_APRIL, None))
		self.assertIsNone(before_start(BEFORE_APRIL, date(2026, 3, 1)))
