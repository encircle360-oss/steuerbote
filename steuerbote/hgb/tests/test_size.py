"""The size classes of §§ 267, 267a HGB with the thresholds of 2024."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.hgb.size import (
	HEADCOUNT_CONVENTIONS,
	YEARS,
	Counting,
	Criteria,
	SizeClass,
	SizeError,
	Thresholds,
	UnknownYearError,
	average_employees,
	exceeds,
	headcount_dates,
	indicated_class,
	thresholds_for,
)

CLOSING_2026 = date(2026, 12, 31)


def criteria(bilanzsumme: str, umsatzerloese: str, arbeitnehmer: str, closing_date: date = CLOSING_2026):
	return Criteria(closing_date, Decimal(bilanzsumme), Decimal(umsatzerloese), Decimal(arbeitnehmer))


class SizeClassTest(TestCase):
	def test_orders_the_classes_from_kleinst_to_gross(self):
		self.assertEqual(
			list(SizeClass), [SizeClass.KLEINST, SizeClass.KLEIN, SizeClass.MITTELGROSS, SizeClass.GROSS]
		)
		self.assertLess(SizeClass.KLEINST, SizeClass.KLEIN)
		self.assertLess(SizeClass.MITTELGROSS, SizeClass.GROSS)
		self.assertGreater(SizeClass.GROSS, SizeClass.KLEINST)
		self.assertLessEqual(SizeClass.KLEIN, SizeClass.KLEIN)
		self.assertGreaterEqual(SizeClass.KLEIN, SizeClass.KLEIN)

	def test_names_each_class_as_the_law_does(self):
		self.assertEqual(
			[(size.value, size.reference) for size in SizeClass],
			[
				("Kleinstkapitalgesellschaft", "§ 267a Abs. 1 HGB"),
				("kleine Kapitalgesellschaft", "§ 267 Abs. 1 HGB"),
				("mittelgroße Kapitalgesellschaft", "§ 267 Abs. 2 HGB"),
				("große Kapitalgesellschaft", "§ 267 Abs. 3 HGB"),
			],
		)

	def test_names_each_class_with_its_code_of_the_gcd_module(self):
		self.assertEqual([size.gcd for size in SizeClass], ["KstK", "KK", "MK", "GK"])

	def test_a_kleinstkapitalgesellschaft_is_a_small_company(self):
		self.assertEqual(
			[size.is_small for size in SizeClass], [True, True, False, False], "§ 267a Abs. 1 and 2 HGB"
		)

	def test_compares_only_with_size_classes(self):
		with self.assertRaises(TypeError):
			SizeClass.KLEIN < 2  # noqa: B015


class ThresholdsTest(TestCase):
	def test_measures_2026_with_the_thresholds_of_2024(self):
		thresholds = thresholds_for(2026)
		self.assertEqual(
			(thresholds.kleinst, thresholds.klein, thresholds.mittelgross),
			(
				Thresholds(Decimal("450000"), Decimal("900000"), 10),
				Thresholds(Decimal("7500000"), Decimal("15000000"), 50),
				Thresholds(Decimal("25000000"), Decimal("50000000"), 250),
			),
		)

	def test_cites_the_law_that_raised_them_and_when_it_applies(self):
		source = " ".join(thresholds_for(2026).source.split())
		self.assertIn("BGBl. 2024 I Nr. 120", source)
		self.assertIn("Art. 93 Abs. 1 HGBEG", source)
		self.assertIn("nach dem 31. Dezember 2023 beginnende Geschäftsjahr", source)

	def test_knows_2026_only(self):
		self.assertEqual(tuple(YEARS), (2026,))
		self.assertEqual(YEARS[2026].year, 2026)
		with self.assertRaises(UnknownYearError):
			thresholds_for(2027)

	def test_a_year_is_an_int(self):
		for year in ("2026", 2026.0, True):
			with self.subTest(year=year), self.assertRaises(TypeError):
				thresholds_for(year)  # type: ignore[arg-type]

	def test_is_read_only(self):
		with self.assertRaises(TypeError):
			YEARS[2027] = YEARS[2026]  # type: ignore[index]


class CriteriaTest(TestCase):
	def test_takes_decimals_only(self):
		with self.assertRaises(TypeError):
			Criteria(CLOSING_2026, 1000.0, Decimal("1"), Decimal("1"))  # type: ignore[arg-type]
		with self.assertRaises(TypeError):
			Criteria(CLOSING_2026, Decimal("1"), Decimal("1"), 3)  # type: ignore[arg-type]

	def test_refuses_negative_amounts_and_headcounts(self):
		for values in (("-1", "0", "0"), ("0", "-1", "0"), ("0", "0", "-0.25")):
			with self.subTest(values=values), self.assertRaises(ValueError):
				criteria(*values)


class ExceedsTest(TestCase):
	klein = Thresholds(Decimal("7500000"), Decimal("15000000"), 50)

	def test_two_of_three_criteria_above_the_thresholds_exceed_them(self):
		self.assertTrue(exceeds(criteria("7500000.01", "15000000.01", "0"), self.klein))
		self.assertTrue(exceeds(criteria("7500000.01", "0", "50.25"), self.klein))
		self.assertTrue(exceeds(criteria("0", "15000000.01", "51"), self.klein))

	def test_one_criterion_above_does_not(self):
		self.assertFalse(exceeds(criteria("99000000", "0", "0"), self.klein))

	def test_a_criterion_at_its_threshold_is_not_above_it(self):
		self.assertFalse(exceeds(criteria("7500000", "15000000", "50"), self.klein))


class IndicatedClassTest(TestCase):
	"""The class the criteria of one Abschlussstichtag point to: at most two of three thresholds exceeded."""

	thresholds = thresholds_for(2026)

	def test_a_small_company_within_the_kleinst_thresholds_is_kleinst(self):
		self.assertIs(indicated_class(criteria("120000", "300000", "2"), self.thresholds), SizeClass.KLEINST)

	def test_one_criterion_above_the_kleinst_thresholds_keeps_it_kleinst(self):
		self.assertIs(indicated_class(criteria("2000000", "300000", "2"), self.thresholds), SizeClass.KLEINST)

	def test_two_criteria_above_make_it_klein(self):
		self.assertIs(
			indicated_class(criteria("450000.01", "900000.01", "2"), self.thresholds), SizeClass.KLEIN
		)
		self.assertIs(
			indicated_class(criteria("400000", "950000", "10.25"), self.thresholds), SizeClass.KLEIN
		)

	def test_above_the_klein_thresholds_it_is_mittelgross(self):
		self.assertIs(
			indicated_class(criteria("8000000", "16000000", "20"), self.thresholds), SizeClass.MITTELGROSS
		)

	def test_above_the_mittelgross_thresholds_it_is_gross(self):
		self.assertIs(
			indicated_class(criteria("30000000", "60000000", "20"), self.thresholds), SizeClass.GROSS
		)

	def test_at_every_threshold_it_stays_in_the_smaller_class(self):
		self.assertIs(indicated_class(criteria("450000", "900000", "10"), self.thresholds), SizeClass.KLEINST)
		self.assertIs(
			indicated_class(criteria("7500000", "15000000", "50"), self.thresholds), SizeClass.KLEIN
		)
		self.assertIs(
			indicated_class(criteria("25000000", "50000000", "250"), self.thresholds), SizeClass.MITTELGROSS
		)


class HeadcountDatesTest(TestCase):
	def test_counts_on_the_four_quarter_ends_of_the_calendar_year(self):
		self.assertEqual(
			headcount_dates(CLOSING_2026),
			(date(2026, 3, 31), date(2026, 6, 30), date(2026, 9, 30), date(2026, 12, 31)),
		)

	def test_takes_the_last_four_quarter_ends_up_to_another_closing_date(self):
		self.assertEqual(
			headcount_dates(date(2026, 6, 30)),
			(date(2025, 9, 30), date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30)),
		)
		self.assertEqual(
			headcount_dates(date(2026, 11, 15)),
			(date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30), date(2026, 9, 30)),
		)


class AverageEmployeesTest(TestCase):
	"""§ 267 Abs. 5 HGB: der vierte Teil der Summe der Zahlen der vier Stichtage."""

	def counts(self, *numbers: int) -> dict[date, int]:
		return dict(zip(headcount_dates(CLOSING_2026), numbers, strict=True))

	def test_is_a_quarter_of_the_sum_of_the_four_headcounts(self):
		self.assertEqual(average_employees(self.counts(10, 11, 10, 10), CLOSING_2026), Decimal("10.25"))

	def test_keeps_the_quarters_exactly(self):
		self.assertEqual(str(average_employees(self.counts(1, 0, 0, 0), CLOSING_2026)), "0.25")
		self.assertEqual(average_employees(self.counts(0, 0, 0, 0), CLOSING_2026), Decimal("0"))

	def test_needs_exactly_the_four_days(self):
		counts = self.counts(1, 2, 3, 4)
		del counts[date(2026, 6, 30)]
		with self.assertRaises(SizeError):
			average_employees(counts, CLOSING_2026)
		with self.assertRaises(SizeError):
			average_employees({**self.counts(1, 2, 3, 4), date(2026, 1, 31): 5}, CLOSING_2026)

	def test_counts_whole_people(self):
		with self.assertRaises(TypeError):
			average_employees({**self.counts(1, 2, 3, 4), date(2026, 3, 31): 1.5}, CLOSING_2026)
		with self.assertRaises(TypeError):
			average_employees({**self.counts(1, 2, 3, 4), date(2026, 3, 31): True}, CLOSING_2026)
		with self.assertRaises(ValueError):
			average_employees(self.counts(1, -1, 3, 4), CLOSING_2026)


class HeadcountConventionsTest(TestCase):
	def test_counts_staff_abroad_but_not_apprentices_as_the_law_says(self):
		by_whom = {convention.who: convention for convention in HEADCOUNT_CONVENTIONS}
		abroad = by_whom["im Ausland beschäftigte Arbeitnehmer"]
		apprentices = by_whom["zu ihrer Berufsausbildung Beschäftigte"]
		self.assertEqual((abroad.counting, abroad.reference), (Counting.COUNTED, "§ 267 Abs. 5 HGB"))
		self.assertEqual(
			(apprentices.counting, apprentices.reference), (Counting.NOT_COUNTED, "§ 267 Abs. 5 HGB")
		)

	def test_leaves_part_timers_and_geschaeftsfuehrer_unverified(self):
		unverified = [
			convention.who
			for convention in HEADCOUNT_CONVENTIONS
			if convention.counting is Counting.UNVERIFIED
		]
		self.assertEqual(unverified, ["Teilzeitbeschäftigte, je Kopf gezählt", "Geschäftsführer"])
		for convention in HEADCOUNT_CONVENTIONS:
			with self.subTest(who=convention.who):
				self.assertEqual(convention.counting is Counting.UNVERIFIED, convention.reference == "")
