from datetime import date
from unittest import TestCase

from steuerbote.deadlines.holidays import easter_sunday, nationwide


class EasterTest(TestCase):
	def test_easter_sunday_of_the_gregorian_calendar(self):
		self.assertEqual(
			[easter_sunday(year) for year in (2024, 2025, 2026, 2027, 2038)],
			[date(2024, 3, 31), date(2025, 4, 20), date(2026, 4, 5), date(2027, 3, 28), date(2038, 4, 25)],
		)


class NationwideTest(TestCase):
	def test_the_holidays_of_every_state_of_a_year(self):
		"""The holidays every state law names, and the Tag der Deutschen Einheit (Art. 2 Abs. 2 Einigungsvertrag): a
		deadline that ends on one of them moves wherever the Finanzamt or the BZSt sits (§ 108 Abs. 3 AO)."""
		self.assertEqual(
			sorted(nationwide([2026])),
			[
				date(2026, 1, 1),
				date(2026, 4, 3),
				date(2026, 4, 6),
				date(2026, 5, 1),
				date(2026, 5, 14),
				date(2026, 5, 25),
				date(2026, 10, 3),
				date(2026, 12, 25),
				date(2026, 12, 26),
			],
		)

	def test_several_years_at_once(self):
		self.assertEqual(len(nationwide(range(2026, 2029))), 27)
		self.assertIn(date(2027, 3, 26), nationwide([2027]))
