"""When form USt 1 H is due, and which Voranmeldung credits the Sondervorauszahlung (§ 48 UStDV, § 108 AO)."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.dauerfrist.form import Context
from steuerbote.dauerfrist.period import (
	Obligation,
	antrag_deadline,
	crediting_period,
	obligation,
	sondervorauszahlung_deadline,
)
from steuerbote.steuerbote.doctype.vat_return.bridge import sondervorauszahlung_values
from steuerbote.ustva import Period, Rhythm

# Public holidays in every state: Christi Himmelfahrt 2029 and Pfingstmontag 2030 fall on a 10th.
ASCENSION_2029 = date(2029, 5, 10)
WHIT_MONDAY_2030 = date(2030, 6, 10)
DF = Context.DAUERFRISTVERLAENGERUNG
SVZ = Context.UMSATZSTEUERSONDERVORAUSZAHLUNG


class AntragDeadlineTest(TestCase):
	def test_is_due_when_the_first_voranmeldung_it_covers_is_due(self):
		self.assertEqual(antrag_deadline(Period.month(2027, 1)), date(2027, 2, 10))
		self.assertEqual(antrag_deadline(Period.month(2027, 7)), date(2027, 8, 10))
		self.assertEqual(antrag_deadline(Period.quarter(2026, 1)), date(2026, 4, 10))

	def test_is_due_without_the_month_it_applies_for(self):
		first = Period.month(2027, 1)
		self.assertEqual(antrag_deadline(first), first.deadline(dauerfristverlaengerung=False))
		self.assertLess(antrag_deadline(first), first.deadline(dauerfristverlaengerung=True))

	def test_a_saturday_moves_it_to_monday(self):
		self.assertEqual(date(2027, 4, 10).weekday(), 5)
		self.assertEqual(antrag_deadline(Period.quarter(2027, 1)), date(2027, 4, 12))

	def test_a_public_holiday_moves_it_to_the_next_working_day(self):
		self.assertEqual(antrag_deadline(Period.month(2029, 4), holidays={ASCENSION_2029}), date(2029, 5, 11))
		self.assertEqual(
			antrag_deadline(Period.month(2030, 5), holidays={WHIT_MONDAY_2030}), date(2030, 6, 11)
		)


class SondervorauszahlungDeadlineTest(TestCase):
	def test_is_the_tenth_of_february(self):
		self.assertEqual(sondervorauszahlung_deadline(2027), date(2027, 2, 10))
		self.assertEqual(sondervorauszahlung_deadline(2028), date(2028, 2, 10))

	def test_a_weekend_moves_it_to_monday(self):
		self.assertEqual(date(2029, 2, 10).weekday(), 5)
		self.assertEqual(sondervorauszahlung_deadline(2029), date(2029, 2, 12))
		self.assertEqual(date(2030, 2, 10).weekday(), 6)
		self.assertEqual(sondervorauszahlung_deadline(2030), date(2030, 2, 11))

	def test_a_public_holiday_moves_it_to_the_next_working_day(self):
		self.assertEqual(sondervorauszahlung_deadline(2027, holidays={date(2027, 2, 10)}), date(2027, 2, 11))

	def test_holidays_and_a_weekend_add_up(self):
		holidays = {date(2028, 2, 10), date(2028, 2, 11)}
		self.assertEqual(date(2028, 2, 11).weekday(), 4)
		self.assertEqual(sondervorauszahlung_deadline(2028, holidays=holidays), date(2028, 2, 14))

	def test_falls_on_the_day_the_december_voranmeldung_is_due_with_the_extension(self):
		self.assertEqual(
			Period.month(2026, 12).deadline(dauerfristverlaengerung=True), sondervorauszahlung_deadline(2027)
		)

	def test_refuses_what_is_no_year(self):
		with self.assertRaisesRegex(ValueError, "four-digit year"):
			sondervorauszahlung_deadline(0)


class ObligationTest(TestCase):
	def test_a_quarterly_filer_applies_with_the_first_quarter_to_cover(self):
		self.assertEqual(
			obligation(2027, Rhythm.QUARTERLY, Period.quarter(2027, 1)),
			Obligation(DF, date(2027, 4, 12), antrag=True),
		)

	def test_a_quarterly_filer_does_not_repeat_the_antrag(self):
		self.assertIsNone(obligation(2028, Rhythm.QUARTERLY))

	def test_a_monthly_filer_applies_with_the_sondervorauszahlung(self):
		self.assertEqual(
			obligation(2027, Rhythm.MONTHLY, Period.month(2027, 1)),
			Obligation(SVZ, date(2027, 2, 10), antrag=True),
		)

	def test_a_monthly_filer_who_applies_during_the_year_pays_with_the_antrag(self):
		self.assertEqual(
			obligation(2027, Rhythm.MONTHLY, Period.month(2027, 7)),
			Obligation(SVZ, date(2027, 8, 10), antrag=True),
		)

	def test_a_monthly_filer_registers_the_sondervorauszahlung_every_year(self):
		self.assertEqual(obligation(2029, Rhythm.MONTHLY), Obligation(SVZ, date(2029, 2, 12), antrag=False))

	def test_passes_the_holidays_on(self):
		self.assertEqual(
			obligation(2029, Rhythm.MONTHLY, Period.month(2029, 4), holidays={ASCENSION_2029}),
			Obligation(SVZ, date(2029, 5, 11), antrag=True),
		)
		self.assertEqual(
			obligation(2027, Rhythm.MONTHLY, holidays={date(2027, 2, 10)}),
			Obligation(SVZ, date(2027, 2, 11), antrag=False),
		)

	def test_takes_the_value_of_the_rhythm(self):
		self.assertEqual(obligation(2029, "monthly").context, SVZ)  # type: ignore[arg-type]
		with self.assertRaises(ValueError):
			obligation(2029, "none")  # type: ignore[arg-type]

	def test_the_first_period_lies_in_the_year(self):
		with self.assertRaisesRegex(ValueError, "lies in 2026, not in 2027"):
			obligation(2027, Rhythm.MONTHLY, Period.month(2026, 12))

	def test_the_first_period_has_the_rhythm_of_the_filer(self):
		with self.assertRaisesRegex(ValueError, "quarterly period for a monthly filer"):
			obligation(2027, Rhythm.MONTHLY, Period.quarter(2027, 1))

	def test_is_immutable(self):
		with self.assertRaises(AttributeError):
			obligation(2029, Rhythm.MONTHLY).antrag = True  # type: ignore[union-attr,misc]


class CreditingPeriodTest(TestCase):
	def test_is_december_for_a_monthly_filer(self):
		self.assertEqual(crediting_period(2026, Rhythm.MONTHLY), Period.month(2026, 12))

	def test_is_the_fourth_quarter_for_a_quarterly_filer(self):
		self.assertEqual(crediting_period(2026, Rhythm.QUARTERLY), Period.quarter(2026, 4))

	def test_is_the_last_period_of_the_extension_when_it_ends_during_the_year(self):
		self.assertEqual(crediting_period(2026, Rhythm.MONTHLY, last_month=9), Period.month(2026, 9))
		self.assertEqual(crediting_period(2026, Rhythm.QUARTERLY, last_month=8), Period.quarter(2026, 3))
		self.assertEqual(crediting_period(2026, "quarterly", last_month=1), Period.quarter(2026, 1))  # type: ignore[arg-type]

	def test_refuses_a_month_outside_the_year(self):
		for month in (0, 13, True, "12"):
			with self.subTest(month=month), self.assertRaisesRegex(ValueError, "between 1 and 12"):
				crediting_period(2026, Rhythm.MONTHLY, last_month=month)  # type: ignore[arg-type]

	def test_refuses_what_is_no_year(self):
		with self.assertRaisesRegex(ValueError, "four-digit year"):
			crediting_period(0, Rhythm.MONTHLY)

	def test_is_the_period_whose_vat_return_takes_kz39(self):
		for rhythm, last in ((Rhythm.MONTHLY, 12), (Rhythm.QUARTERLY, 4)):
			for index in range(1, last + 1):
				period = Period(2026, rhythm, index)
				with self.subTest(period=period.label):
					credited = bool(sondervorauszahlung_values(period, True, Decimal("4000.00")))
					self.assertEqual(credited, period == crediting_period(2026, rhythm))
