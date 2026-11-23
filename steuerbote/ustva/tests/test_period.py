from datetime import date
from unittest import TestCase

from steuerbote.ustva.period import Period, Rhythm, day_label, deadline_holidays


class PeriodTest(TestCase):
	def test_monthly_periods_cover_their_month(self):
		january = Period.month(2026, 1)
		self.assertEqual(january.start, date(2026, 1, 1))
		self.assertEqual(january.end, date(2026, 1, 31))
		february_leap_year = Period.month(2028, 2)
		self.assertEqual(february_leap_year.end, date(2028, 2, 29))
		self.assertEqual(Period.month(2026, 2).end, date(2026, 2, 28))

	def test_quarterly_periods_cover_three_months(self):
		second = Period.quarter(2026, 2)
		self.assertEqual(second.start, date(2026, 4, 1))
		self.assertEqual(second.end, date(2026, 6, 30))
		self.assertEqual(Period.quarter(2026, 4).end, date(2026, 12, 31))

	def test_elster_codes(self):
		self.assertEqual(Period.month(2026, 1).code, "01")
		self.assertEqual(Period.month(2026, 12).code, "12")
		self.assertEqual(Period.quarter(2026, 1).code, "41")
		self.assertEqual(Period.quarter(2026, 4).code, "44")

	def test_labels_follow_the_form(self):
		self.assertEqual(Period.month(2026, 3).label, "März 2026")
		self.assertEqual(Period.quarter(2026, 3).label, "III. Kalendervierteljahr 2026")

	def test_a_day_reads_with_the_name_of_its_month(self):
		self.assertEqual(day_label(date(2026, 11, 20)), "20. November 2026")
		self.assertEqual(day_label(date(2026, 3, 1)), "1. März 2026")

	def test_index_must_fit_the_rhythm(self):
		with self.assertRaisesRegex(ValueError, "between 1 and 12"):
			Period.month(2026, 13)
		with self.assertRaisesRegex(ValueError, "between 1 and 4"):
			Period.quarter(2026, 5)
		with self.assertRaisesRegex(ValueError, "between 1 and 12"):
			Period.month(2026, 0)
		with self.assertRaisesRegex(ValueError, "between 1 and 12"):
			Period(2026, Rhythm.MONTHLY, "1")  # type: ignore[arg-type]

	def test_year_must_be_a_year(self):
		with self.assertRaisesRegex(ValueError, "four-digit year"):
			Period.month(0, 1)
		with self.assertRaisesRegex(ValueError, "four-digit year"):
			Period.month("2026", 1)  # type: ignore[arg-type]

	def test_booleans_are_neither_years_nor_indexes(self):
		with self.assertRaisesRegex(ValueError, "four-digit year"):
			Period(True, Rhythm.MONTHLY, 1)  # type: ignore[arg-type]
		with self.assertRaisesRegex(ValueError, "between 1 and 12"):
			Period.month(2026, True)  # type: ignore[arg-type]

	def test_rhythm_accepts_the_value_of_the_enum(self):
		self.assertIs(Period(2026, "quarterly", 1).rhythm, Rhythm.QUARTERLY)  # type: ignore[arg-type]
		with self.assertRaises(ValueError):
			Period(2026, "yearly", 1)  # type: ignore[arg-type]

	def test_containing_a_date(self):
		self.assertEqual(Period.containing(date(2026, 5, 17), Rhythm.MONTHLY), Period.month(2026, 5))
		self.assertEqual(Period.containing(date(2026, 5, 17), Rhythm.QUARTERLY), Period.quarter(2026, 2))
		self.assertEqual(Period.containing(date(2026, 12, 31), "quarterly"), Period.quarter(2026, 4))  # type: ignore[arg-type]

	def test_contains(self):
		quarter = Period.quarter(2026, 1)
		self.assertTrue(quarter.contains(date(2026, 1, 1)))
		self.assertTrue(quarter.contains(date(2026, 3, 31)))
		self.assertFalse(quarter.contains(date(2026, 4, 1)))

	def test_previous_and_next_cross_the_year(self):
		self.assertEqual(Period.month(2026, 1).previous(), Period.month(2025, 12))
		self.assertEqual(Period.month(2026, 12).next(), Period.month(2027, 1))
		self.assertEqual(Period.quarter(2026, 1).previous(), Period.quarter(2025, 4))
		self.assertEqual(Period.quarter(2026, 4).next(), Period.quarter(2027, 1))
		self.assertEqual(Period.month(2026, 6).next(), Period.month(2026, 7))
		self.assertEqual(Period.quarter(2026, 2).previous(), Period.quarter(2026, 1))

	def test_period_is_immutable(self):
		with self.assertRaises(AttributeError):
			Period.month(2026, 1).year = 2027  # type: ignore[misc]


class DeadlineTest(TestCase):
	def test_tenth_day_after_the_end_of_the_period(self):
		self.assertEqual(Period.month(2026, 1).deadline(), date(2026, 2, 10))
		self.assertEqual(Period.quarter(2026, 1).deadline(), date(2026, 4, 10))

	def test_dauerfristverlaengerung_adds_one_month(self):
		self.assertEqual(Period.month(2026, 1).deadline(dauerfristverlaengerung=True), date(2026, 3, 10))
		self.assertEqual(Period.quarter(2026, 4).deadline(dauerfristverlaengerung=True), date(2027, 2, 10))

	def test_december_is_due_in_the_next_year(self):
		self.assertEqual(Period.month(2026, 12).deadline(), date(2027, 1, 11))

	def test_weekend_moves_the_deadline_to_monday(self):
		self.assertEqual(date(2026, 10, 10).weekday(), 5)
		self.assertEqual(Period.month(2026, 9).deadline(), date(2026, 10, 12))
		self.assertEqual(date(2027, 1, 10).weekday(), 6)
		self.assertEqual(Period.month(2026, 12).deadline(), date(2027, 1, 11))

	def test_public_holidays_move_the_deadline_further(self):
		holidays = {date(2026, 10, 12)}
		self.assertEqual(Period.month(2026, 9).deadline(holidays=holidays), date(2026, 10, 13))

	def test_holiday_followed_by_weekend(self):
		holidays = {date(2026, 4, 10)}
		self.assertEqual(date(2026, 4, 10).weekday(), 4)
		self.assertEqual(Period.quarter(2026, 1).deadline(holidays=holidays), date(2026, 4, 13))


class DeadlineHolidaysTest(TestCase):
	"""§ 108 Absatz 3 AO moves a deadline off a Sunday, a public holiday or a Saturday, not off another weekly day
	off of the company."""

	def test_the_days_of_a_holiday_list_without_its_weekly_days_off(self):
		days = [
			(date(2026, 5, 25), 0),
			(date(2026, 5, 29), 1),
			(date(2026, 12, 25), False),
			(date(2026, 12, 26), True),
		]
		self.assertEqual(deadline_holidays(days), frozenset({date(2026, 5, 25), date(2026, 12, 25)}))
		self.assertEqual(deadline_holidays([]), frozenset())

	def test_a_weekly_day_off_moves_no_deadline(self):
		self.assertEqual(date(2026, 12, 10).weekday(), 3)
		thursdays_off = deadline_holidays([(date(2026, 12, 10), 1)])
		self.assertEqual(Period.month(2026, 11).deadline(holidays=thursdays_off), date(2026, 12, 10))
