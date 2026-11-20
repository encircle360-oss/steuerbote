from unittest import TestCase

from steuerbote.steuerbote.report.ustva_kennzahlen.comparison import Thresholds
from steuerbote.zm.comparison import compare, comparison_hints
from steuerbote.zm.findings import Code
from steuerbote.zm.lines import Art, Override, build
from steuerbote.zm.period import ReportingPeriod
from steuerbote.zm.tests.support import AUSTRIA, FIGURES, FRANCE, SPAIN, d, invoice

MARCH = ReportingPeriod.month(2026, 3)


def statement(*amounts, overrides=None):
	return build(amounts, FIGURES, overrides=overrides)


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
		hints = comparison_hints(compare(current, previous, Thresholds().exceeded), MARCH, FIGURES)
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
			comparison_hints(rows, MARCH, FIGURES)[0].text,
			f"Die Zeile {AUSTRIA} (L) liegt mit 0,00 € um 100,0 % unter der Vorperiode März 2026 (800,00 €).",
		)
