"""The Sondervorauszahlung in Kz 38 of form USt 1 H: one test per rule of § 47 UStDV and of the Anleitung USt 5 E."""

from datetime import date, datetime
from decimal import Decimal
from unittest import TestCase

from steuerbote.dauerfrist.calculation import (
	expected_sondervorauszahlung,
	months_of_activity,
	previous_year_base,
	sondervorauszahlung,
)

# USt 5 E 2026, Beispiel: Kz 83 of the Voranmeldungen 2025 sum up to 39.000 €, and the Voranmeldung for
# December credited the Sondervorauszahlung 2025 of 5.000 € in Kz 39.
EXAMPLE_KZ83 = (*[Decimal("3500.00")] * 11, Decimal("500.00"))
EXAMPLE_KZ39 = Decimal("5000.00")


class SondervorauszahlungTest(TestCase):
	def test_is_one_eleventh_of_the_base(self):
		self.assertEqual(sondervorauszahlung(Decimal("11000.00")), Decimal("1000"))

	def test_example_of_the_anleitung(self):
		self.assertEqual(sum(EXAMPLE_KZ83), Decimal("39000.00"))
		base = previous_year_base(EXAMPLE_KZ83, EXAMPLE_KZ39)
		self.assertEqual(base, Decimal("44000.00"))
		self.assertEqual(sondervorauszahlung(base), Decimal("4000"))

	def test_drops_the_cents_of_one_eleventh(self):
		self.assertEqual(sondervorauszahlung(Decimal("43999.99")), Decimal("3999"))

	def test_drops_the_cents_instead_of_rounding_them(self):
		self.assertEqual(sondervorauszahlung(Decimal("54.99")), Decimal("4"))
		self.assertEqual(sondervorauszahlung(Decimal("10.99")), Decimal("0"))

	def test_is_zero_for_a_surplus(self):
		self.assertEqual(sondervorauszahlung(Decimal("-2500.00")), Decimal("0"))

	def test_is_zero_for_a_base_of_zero(self):
		self.assertEqual(sondervorauszahlung(Decimal("0.00")), Decimal("0"))

	def test_is_whole_euros_as_elster_takes_them(self):
		self.assertEqual(str(sondervorauszahlung(Decimal("44000.00"))), "4000")
		self.assertEqual(str(sondervorauszahlung(Decimal("-0.01"))), "0")
		self.assertEqual(str(sondervorauszahlung(Decimal("1.1E+5"))), "10000")

	def test_refuses_floats(self):
		with self.assertRaises(TypeError):
			sondervorauszahlung(44000.0)  # type: ignore[arg-type]

	def test_refuses_a_base_that_is_no_amount(self):
		for base in (Decimal("NaN"), Decimal("Infinity")):
			with self.subTest(base=base), self.assertRaisesRegex(ValueError, "not an amount"):
				sondervorauszahlung(base)


class PreviousYearBaseTest(TestCase):
	def test_sums_kz83_of_the_voranmeldungen(self):
		self.assertEqual(
			previous_year_base([Decimal("1200.00"), Decimal("-300.50"), Decimal("0.00")]), Decimal("899.50")
		)

	def test_adds_the_sondervorauszahlung_credited_in_kz39(self):
		self.assertEqual(previous_year_base([Decimal("500.00")], Decimal("5000.00")), Decimal("5500.00"))

	def test_a_surplus_reduces_the_base(self):
		self.assertEqual(previous_year_base([Decimal("-800.00"), Decimal("300.00")]), Decimal("-500.00"))

	def test_takes_any_iterable_of_kz83(self):
		self.assertEqual(previous_year_base(iter(EXAMPLE_KZ83)), Decimal("39000.00"))

	def test_a_whole_year_is_not_converted(self):
		self.assertEqual(str(previous_year_base(EXAMPLE_KZ83, EXAMPLE_KZ39, months_active=12)), "44000.00")

	def test_converts_part_of_a_year_into_an_annual_sum(self):
		self.assertEqual(previous_year_base([Decimal("20000.00")], months_active=8), Decimal("30000"))
		self.assertEqual(sondervorauszahlung(Decimal("30000")), Decimal("2727"))

	def test_the_annual_sum_keeps_its_fraction_until_kz38(self):
		base = previous_year_base([Decimal("1000.00")], months_active=7)
		self.assertEqual(base.quantize(Decimal("0.0001")), Decimal("1714.2857"))
		self.assertEqual(sondervorauszahlung(base), Decimal("155"))

	def test_converts_kz39_with_the_vorauszahlungen(self):
		self.assertEqual(
			previous_year_base([Decimal("1500.00")], Decimal("500.00"), months_active=6), Decimal("4000")
		)

	def test_needs_the_voranmeldungen_of_the_previous_year(self):
		with self.assertRaisesRegex(ValueError, "Kz 83 of at least one Voranmeldung"):
			previous_year_base([])

	def test_refuses_amounts_that_are_not_cents(self):
		for kz83, kz39 in (
			([Decimal("1.001")], Decimal("0")),
			([Decimal("NaN")], Decimal("0")),
			([Decimal("1.00")], Decimal("0.005")),
			([Decimal("1.00")], Decimal("Infinity")),
		):
			with self.subTest(kz83=kz83, kz39=kz39), self.assertRaisesRegex(ValueError, "in cents"):
				previous_year_base(kz83, kz39)

	def test_refuses_floats(self):
		with self.assertRaises(TypeError):
			previous_year_base([100.0])  # type: ignore[list-item]
		with self.assertRaises(TypeError):
			previous_year_base([Decimal("100.00")], 5.0)  # type: ignore[arg-type]

	def test_refuses_a_negative_kz39(self):
		with self.assertRaisesRegex(ValueError, "Kz 39 takes no negative amount"):
			previous_year_base([Decimal("100.00")], Decimal("-5.00"))

	def test_months_lie_within_a_year(self):
		for months in (0, 13, True, "8", 7.0):
			with self.subTest(months=months), self.assertRaisesRegex(ValueError, "between 1 and 12"):
				previous_year_base([Decimal("100.00")], months_active=months)  # type: ignore[arg-type]


class MonthsOfActivityTest(TestCase):
	def test_counts_the_months_from_the_start_to_december(self):
		self.assertEqual(months_of_activity(2026, date(2026, 5, 1)), 8)
		self.assertEqual(months_of_activity(2026, date(2026, 1, 1)), 12)

	def test_counts_a_started_month_in_full(self):
		self.assertEqual(months_of_activity(2026, date(2026, 5, 31)), 8)
		self.assertEqual(months_of_activity(2026, date(2026, 12, 31)), 1)

	def test_a_business_that_began_before_the_year_was_active_all_year(self):
		self.assertEqual(months_of_activity(2026, date(2019, 3, 1)), 12)

	def test_takes_the_day_of_a_point_in_time(self):
		self.assertEqual(months_of_activity(2026, datetime(2026, 11, 30, 23, 59)), 2)

	def test_refuses_a_start_after_the_year(self):
		with self.assertRaisesRegex(ValueError, "began after 2026"):
			months_of_activity(2026, date(2027, 1, 1))

	def test_refuses_what_is_no_year(self):
		for year in ("2026", True, 0, 10000):
			with self.subTest(year=year), self.assertRaisesRegex(ValueError, "four-digit year"):
				months_of_activity(year, date(2026, 5, 1))  # type: ignore[arg-type]

	def test_refuses_what_is_no_date(self):
		with self.assertRaises(TypeError):
			months_of_activity(2026, "2026-05-01")  # type: ignore[arg-type]


class ExpectedSondervorauszahlungTest(TestCase):
	def test_is_the_average_vorauszahlung_of_a_calendar_month(self):
		self.assertEqual(expected_sondervorauszahlung(Decimal("15000.00"), months_active=10), Decimal("1500"))

	def test_counts_the_months_of_activity_of_the_year(self):
		months = months_of_activity(2027, date(2027, 3, 15))
		self.assertEqual(months, 10)
		self.assertEqual(expected_sondervorauszahlung(Decimal("15000.00"), months), Decimal("1500"))

	def test_drops_the_cents(self):
		self.assertEqual(str(expected_sondervorauszahlung(Decimal("10000.00"), months_active=3)), "3333")

	def test_is_zero_for_an_expected_surplus(self):
		self.assertEqual(expected_sondervorauszahlung(Decimal("-1200.00"), months_active=6), Decimal("0"))
		self.assertEqual(str(expected_sondervorauszahlung(Decimal("0.00"), months_active=6)), "0")

	def test_refuses_amounts_that_are_not_cents(self):
		for expected in (Decimal("1.001"), Decimal("NaN")):
			with self.subTest(expected=expected), self.assertRaisesRegex(ValueError, "in cents"):
				expected_sondervorauszahlung(expected, months_active=6)

	def test_refuses_floats(self):
		with self.assertRaises(TypeError):
			expected_sondervorauszahlung(1200.0, months_active=6)  # type: ignore[arg-type]

	def test_months_lie_within_a_year(self):
		for months in (0, 13, False):
			with self.subTest(months=months), self.assertRaisesRegex(ValueError, "between 1 and 12"):
				expected_sondervorauszahlung(Decimal("1200.00"), months_active=months)
