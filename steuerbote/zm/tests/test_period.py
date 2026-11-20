from datetime import date
from unittest import TestCase

from steuerbote.zm.period import Kind, ReportingPeriod


class ReportingPeriodTest(TestCase):
	def test_a_month(self):
		march = ReportingPeriod.month(2026, 3)
		self.assertIs(march.kind, Kind.MONTH)
		self.assertEqual((march.start, march.end), (date(2026, 3, 1), date(2026, 3, 31)))
		self.assertEqual(march.months, (3,))
		self.assertEqual(march.label, "März 2026")

	def test_a_quarter(self):
		second = ReportingPeriod.quarter(2026, 2)
		self.assertIs(second.kind, Kind.QUARTER)
		self.assertEqual((second.start, second.end), (date(2026, 4, 1), date(2026, 6, 30)))
		self.assertEqual(second.months, (4, 5, 6))
		self.assertEqual(second.label, "II. Kalendervierteljahr 2026")

	def test_the_first_two_months_of_a_quarter(self):
		"""§ 18a Absatz 1 Satz 3 UStG: the ZM for the month in which the threshold is exceeded „und die bereits
		abgelaufenen Kalendermonate dieses Kalendervierteljahres“."""
		april_and_may = ReportingPeriod.two_months(2026, 2)
		self.assertIs(april_and_may.kind, Kind.TWO_MONTHS)
		self.assertEqual((april_and_may.start, april_and_may.end), (date(2026, 4, 1), date(2026, 5, 31)))
		self.assertEqual(april_and_may.label, "April und Mai 2026")
		self.assertEqual(ReportingPeriod(2026, 4, 5), april_and_may)

	def test_the_calendar_year(self):
		year = ReportingPeriod.calendar_year(2026)
		self.assertIs(year.kind, Kind.YEAR)
		self.assertEqual((year.start, year.end), (date(2026, 1, 1), date(2026, 12, 31)))
		self.assertEqual(year.months, tuple(range(1, 13)))
		self.assertEqual(year.label, "Kalenderjahr 2026")

	def test_the_months_of_a_quarter_from_its_start_are_the_quarter(self):
		self.assertEqual(ReportingPeriod(2026, 7, 9), ReportingPeriod.quarter(2026, 3))

	def test_other_spans_are_no_meldezeitraum(self):
		for first, last in ((2, 3), (3, 4), (1, 4), (5, 7), (0, 0), (13, 13), (2, 1), (1, 11)):
			with self.subTest(first=first, last=last), self.assertRaisesRegex(ValueError, "no Meldezeitraum"):
				ReportingPeriod(2026, first, last)

	def test_year_and_months_must_be_numbers(self):
		with self.assertRaisesRegex(ValueError, "four-digit year"):
			ReportingPeriod.month(0, 1)
		with self.assertRaisesRegex(ValueError, "four-digit year"):
			ReportingPeriod.month("2026", 1)  # type: ignore[arg-type]
		with self.assertRaisesRegex(ValueError, "four-digit year"):
			ReportingPeriod.month(True, 1)  # type: ignore[arg-type]
		with self.assertRaisesRegex(ValueError, "no Meldezeitraum"):
			ReportingPeriod.month(2026, True)  # type: ignore[arg-type]
		with self.assertRaisesRegex(ValueError, "no Meldezeitraum"):
			ReportingPeriod(2026, 1, "1")  # type: ignore[arg-type]
		with self.assertRaisesRegex(ValueError, "no Meldezeitraum"):
			ReportingPeriod.quarter(2026, 5)

	def test_contains(self):
		quarter = ReportingPeriod.quarter(2026, 1)
		self.assertTrue(quarter.contains(date(2026, 3, 31)))
		self.assertFalse(quarter.contains(date(2026, 4, 1)))

	def test_period_is_immutable(self):
		with self.assertRaises(AttributeError):
			ReportingPeriod.month(2026, 1).year = 2027  # type: ignore[misc]


class QuartTest(TestCase):
	"""The field quart of the ERiC data type ZMDO (Jahresdokumentation ZMDO 2, sheet „ZMDO - Felder“)."""

	def test_months_are_21_to_32(self):
		self.assertEqual(ReportingPeriod.month(2026, 1).quart, 21)
		self.assertEqual(ReportingPeriod.month(2026, 12).quart, 32)

	def test_two_months_are_11_to_14(self):
		self.assertEqual([ReportingPeriod.two_months(2026, q).quart for q in (1, 2, 3, 4)], [11, 12, 13, 14])

	def test_quarters_are_1_to_4_and_the_year_5(self):
		self.assertEqual([ReportingPeriod.quarter(2026, q).quart for q in (1, 2, 3, 4)], [1, 2, 3, 4])
		self.assertEqual(ReportingPeriod.calendar_year(2026).quart, 5)

	def test_from_quart_reads_every_code_back(self):
		for code in (*range(1, 6), *range(11, 15), *range(21, 33)):
			with self.subTest(code):
				self.assertEqual(ReportingPeriod.from_quart(2026, code).quart, code)
		self.assertEqual(ReportingPeriod.from_quart(2026, 12), ReportingPeriod.two_months(2026, 2))

	def test_from_quart_refuses_other_codes(self):
		for code in (0, 6, 10, 15, 20, 33, "21", True):
			with self.subTest(code), self.assertRaisesRegex(ValueError, "not a quart"):
				ReportingPeriod.from_quart(2026, code)  # type: ignore[arg-type]


class PreviousTest(TestCase):
	def test_the_period_of_the_same_kind_before(self):
		self.assertEqual(ReportingPeriod.month(2026, 1).previous(), ReportingPeriod.month(2025, 12))
		self.assertEqual(ReportingPeriod.month(2026, 7).previous(), ReportingPeriod.month(2026, 6))
		self.assertEqual(ReportingPeriod.quarter(2026, 1).previous(), ReportingPeriod.quarter(2025, 4))
		self.assertEqual(ReportingPeriod.quarter(2026, 3).previous(), ReportingPeriod.quarter(2026, 2))
		self.assertEqual(ReportingPeriod.two_months(2026, 1).previous(), ReportingPeriod.two_months(2025, 4))
		self.assertEqual(ReportingPeriod.two_months(2026, 3).previous(), ReportingPeriod.two_months(2026, 2))
		self.assertEqual(ReportingPeriod.calendar_year(2026).previous(), ReportingPeriod.calendar_year(2025))


class DeadlineTest(TestCase):
	"""§ 18a Absatz 1 Satz 1 UStG: „bis zum 25. Tag nach Ablauf“ of the Meldezeitraum, moved by § 108 Absatz 3 AO."""

	def test_25th_day_after_the_end_of_the_period(self):
		self.assertEqual(ReportingPeriod.month(2026, 1).deadline(), date(2026, 2, 25))
		self.assertEqual(ReportingPeriod.month(2026, 2).deadline(), date(2026, 3, 25))
		self.assertEqual(ReportingPeriod.quarter(2026, 4).deadline(), date(2027, 1, 25))
		self.assertEqual(ReportingPeriod.calendar_year(2026).deadline(), date(2027, 1, 25))

	def test_bzst_example_april_and_may_are_due_on_25_june(self):
		"""BZSt „Fristen“: 57,000 euros in May; „M muss nun bis zum 25. Juni eine ZM für die Monate April und Mai
		abgeben.“"""
		self.assertEqual(ReportingPeriod.two_months(2026, 2).deadline(), date(2026, 6, 25))

	def test_no_dauerfristverlaengerung(self):
		"""BZSt „Fristen“: „Die Regelungen über die Dauerfristverlängerung für die Abgabe der
		Umsatzsteuer-Voranmeldungen gelten nicht für die ZM.“ deadline() takes no such argument."""
		with self.assertRaises(TypeError):
			ReportingPeriod.month(2026, 1).deadline(dauerfristverlaengerung=True)  # type: ignore[call-arg]

	def test_saturday_moves_the_deadline_to_monday(self):
		self.assertEqual(date(2026, 4, 25).weekday(), 5)
		self.assertEqual(ReportingPeriod.quarter(2026, 1).deadline(), date(2026, 4, 27))

	def test_sunday_moves_the_deadline_to_monday(self):
		self.assertEqual(date(2026, 10, 25).weekday(), 6)
		self.assertEqual(ReportingPeriod.month(2026, 9).deadline(), date(2026, 10, 26))

	def test_a_public_holiday_moves_the_deadline(self):
		whit_monday = date(2026, 5, 25)
		self.assertEqual(ReportingPeriod.month(2026, 4).deadline(), whit_monday)
		self.assertEqual(ReportingPeriod.month(2026, 4).deadline(holidays={whit_monday}), date(2026, 5, 26))

	def test_holidays_and_the_weekend_after_them(self):
		christmas = {date(2026, 12, 25), date(2026, 12, 26)}
		self.assertEqual(ReportingPeriod.month(2026, 11).deadline(holidays=christmas), date(2026, 12, 28))
