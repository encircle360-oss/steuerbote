from datetime import date
from decimal import Decimal
from types import MappingProxyType
from unittest import TestCase

from steuerbote.ustva.obligations import (
	ZM_KENNZAHLEN,
	correction_hints,
	has_ended,
	period_hints,
	zm_rhythm_hints,
)
from steuerbote.ustva.period import Period
from steuerbote.ustva.plausibility import SEVERITIES, Code, Severity

NOVEMBER = Period.month(2026, 11)
FOURTH_QUARTER = Period.quarter(2026, 4)


class Figures:
	def money(self, amount: Decimal) -> str:
		return f"{amount:.2f} €"

	def percent(self, value: Decimal) -> str:
		return f"{value} %"


class HasEndedTest(TestCase):
	def test_a_period_ends_with_its_last_day(self):
		self.assertFalse(has_ended(NOVEMBER, date(2026, 11, 25)))
		self.assertFalse(has_ended(NOVEMBER, date(2026, 11, 30)))
		self.assertTrue(has_ended(NOVEMBER, date(2026, 12, 1)))
		self.assertFalse(has_ended(FOURTH_QUARTER, date(2026, 12, 31)))
		self.assertTrue(has_ended(FOURTH_QUARTER, date(2027, 1, 1)))

	def test_a_period_that_has_not_begun_has_not_ended(self):
		self.assertFalse(has_ended(Period.month(2026, 12), date(2026, 11, 25)))


class PeriodHintsTest(TestCase):
	def test_a_period_that_has_not_ended_gets_a_warning(self):
		(hint,) = period_hints(NOVEMBER, date(2026, 11, 25))
		self.assertEqual(hint.code, Code.PERIOD_NOT_ENDED)
		self.assertIs(hint.severity, Severity.WARNING)
		self.assertEqual(
			hint.text,
			"November 2026 endet erst am 30. November 2026. Die Steuer entsteht mit Ablauf des Voranmeldungszeitraums "
			"(§ 13 Abs. 1 Nr. 1 Buchst. a UStG), und die Voranmeldung wird nach seinem Ablauf abgegeben (§ 18 Abs. 1 "
			"Satz 1 UStG): Bis dahin ist die Meldung nicht bereit. Berechnen Sie sie nach dem 30. November 2026 erneut.",
		)

	def test_an_ended_period_gets_none(self):
		self.assertEqual(period_hints(NOVEMBER, date(2026, 12, 1)), [])


class ZmRhythmHintsTest(TestCase):
	def test_the_kennzahlen_of_the_zusammenfassende_meldung(self):
		self.assertEqual(ZM_KENNZAHLEN, ("41", "42", "21"))

	def test_a_kennzahl_of_the_zm_without_a_rhythm_for_its_months_gets_a_warning(self):
		(hint,) = zm_rhythm_hints(
			{"41": Decimal("8000.00"), "21": Decimal("5000.00"), "81": Decimal("100.00")},
			["Oktober 2026", "November 2026"],
			Figures(),
		)
		self.assertEqual(hint.code, Code.ZM_WITHOUT_RHYTHM)
		self.assertIs(hint.severity, Severity.WARNING)
		self.assertEqual(
			hint.text,
			"Kz 41 meldet 8000.00 € und Kz 21 5000.00 €, aber die Einstellungen nennen für Oktober 2026 und November 2026 "
			"keinen Rhythmus der Zusammenfassenden Meldung. Für innergemeinschaftliche Lieferungen, Dreiecksgeschäfte und "
			"sonstige Leistungen, deren Steuer der Empfänger in einem anderen Mitgliedstaat schuldet, ist eine "
			"Zusammenfassende Meldung abzugeben (§ 18a Abs. 1 und 2 UStG): Tragen Sie den Rhythmus in den Einstellungen "
			"Umsatzsteuer-Voranmeldung ein, dann kennt Steuerbote die Meldung und ihre Frist.",
		)

	def test_no_warning_without_an_amount_or_without_a_month_lacking_its_rhythm(self):
		self.assertEqual(zm_rhythm_hints({"41": Decimal("8000.00")}, [], Figures()), [])
		self.assertEqual(
			zm_rhythm_hints({"41": Decimal("0.00"), "81": Decimal("10.00")}, ["November 2026"], Figures()), []
		)

	def test_a_negative_amount_needs_the_meldung_as_well(self):
		(hint,) = zm_rhythm_hints({"42": Decimal("-300.00")}, ["November 2026"], Figures())
		self.assertIn("Kz 42 meldet -300.00 €, aber", hint.text)

	def test_the_codes_are_warnings(self):
		self.assertIs(SEVERITIES[Code.PERIOD_NOT_ENDED], Severity.WARNING)
		self.assertIs(SEVERITIES[Code.ZM_WITHOUT_RHYTHM], Severity.WARNING)


class CorrectionHintsTest(TestCase):
	FILED = MappingProxyType({"81": Decimal("1000"), "83": Decimal("190.00")})

	def test_a_corrected_return_that_files_what_was_filed_says_so(self):
		(hint,) = correction_hints(dict(self.FILED), self.FILED, "UStVA-0001")
		self.assertEqual(hint.code, Code.CORRECTION_UNCHANGED)
		self.assertIs(hint.severity, Severity.HINT)
		self.assertEqual(
			hint.text,
			"Die berichtigte Anmeldung meldet dieselben Beträge wie die abgegebene Meldung UStVA-0001: Sie ändert "
			"nichts. Abgegeben wird sie nur, wenn sich eine Angabe außerhalb der Beträge ändert.",
		)

	def test_a_change_or_a_kennzahl_of_zero_decides(self):
		self.assertEqual(
			correction_hints({"81": Decimal("1500"), "83": Decimal("285.00")}, self.FILED, "U"), []
		)
		self.assertEqual(len(correction_hints({**self.FILED, "86": Decimal("0")}, self.FILED, "U")), 1)
		self.assertEqual(correction_hints({"83": Decimal("190.00")}, self.FILED, "U"), [])

	def test_without_a_filed_return_there_is_nothing_to_compare(self):
		self.assertEqual(correction_hints(dict(self.FILED), None, "U"), [])
