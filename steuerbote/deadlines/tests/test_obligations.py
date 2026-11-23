"""Which filings the VAT Return Settings owe and when each is due: the Voranmeldung with the
Dauerfristverlängerung of its year, the Zusammenfassende Meldung and the Sondervorauszahlung, each moved off
weekends and the holidays of the company."""

from datetime import date
from unittest import TestCase

from steuerbote.deadlines.obligations import (
	Kind,
	Obligation,
	first_voranmeldungszeitraum,
	obligations,
	sondervorauszahlungen,
	voranmeldungen,
	zusammenfassende_meldungen,
)
from steuerbote.steuerbote.doctype.vat_return_settings.rules import PeriodRule, Prepayment
from steuerbote.ustva.period import Period
from steuerbote.zm import rhythm as zm_rhythm
from steuerbote.zm.errors import ZmError
from steuerbote.zm.period import ReportingPeriod

MONTHLY = (PeriodRule(2026, "monthly"),)
QUARTERLY = (PeriodRule(2026, "quarterly"),)
DAUERFRIST_2026 = (Prepayment(2026, dauerfristverlaengerung=True),)
ZM_MONTHLY = (zm_rhythm.Rule(2026, 1, "monthly"),)
# Both Christmas holidays are public holidays in every state.
CHRISTMAS_2026 = frozenset({date(2026, 12, 25), date(2026, 12, 26)})


def labels(found) -> list[tuple[str, date]]:
	return [(item.label, item.due) for item in found]


class VoranmeldungenTest(TestCase):
	def test_owes_one_for_each_month_due_on_the_tenth_day_after_it(self):
		self.assertEqual(
			list(voranmeldungen(MONTHLY, (), until=date(2026, 3, 10))),
			[
				Obligation(Kind.VORANMELDUNG, Period.month(2026, 1), "Januar 2026", date(2026, 2, 10)),
				Obligation(Kind.VORANMELDUNG, Period.month(2026, 2), "Februar 2026", date(2026, 3, 10)),
			],
		)

	def test_owes_nothing_due_after_the_day_given(self):
		self.assertEqual(
			labels(voranmeldungen(MONTHLY, (), until=date(2026, 3, 9))), [("Januar 2026", date(2026, 2, 10))]
		)

	def test_a_deadline_on_a_sunday_moves_to_monday(self):
		self.assertEqual(date(2027, 1, 10).weekday(), 6)
		found = labels(voranmeldungen(MONTHLY, (), until=date(2027, 1, 31)))
		self.assertEqual(found[-1], ("Dezember 2026", date(2027, 1, 11)))

	def test_a_holiday_moves_it_to_the_next_working_day(self):
		found = labels(voranmeldungen(MONTHLY, (), until=date(2026, 12, 31), holidays={date(2026, 12, 10)}))
		self.assertEqual(found[-1], ("November 2026", date(2026, 12, 11)))

	def test_the_dauerfristverlaengerung_of_its_year_moves_it_by_one_month(self):
		found = labels(voranmeldungen(MONTHLY, DAUERFRIST_2026, until=date(2027, 3, 10)))
		self.assertEqual(found[0], ("Januar 2026", date(2026, 3, 10)))
		self.assertEqual(
			found[-4:],
			[
				("November 2026", date(2027, 1, 11)),
				("Dezember 2026", date(2027, 2, 10)),
				("Januar 2027", date(2027, 2, 10)),
				("Februar 2027", date(2027, 3, 10)),
			],
		)

	def test_owes_one_for_each_quarter_of_a_quarterly_filer(self):
		self.assertEqual(
			labels(voranmeldungen(QUARTERLY, (), until=date(2027, 1, 31))),
			[
				("I. Kalendervierteljahr 2026", date(2026, 4, 10)),
				("II. Kalendervierteljahr 2026", date(2026, 7, 10)),
				("III. Kalendervierteljahr 2026", date(2026, 10, 12)),
				("IV. Kalendervierteljahr 2026", date(2027, 1, 11)),
			],
		)

	def test_a_change_of_rhythm_takes_effect_with_its_quarter(self):
		rules = (PeriodRule(2026, "monthly"), PeriodRule(2026, "quarterly", 4))
		self.assertEqual(
			[item.period for item in voranmeldungen(rules, (), until=date(2026, 7, 31))],
			[Period.month(2026, 1), Period.month(2026, 2), Period.month(2026, 3), Period.quarter(2026, 2)],
		)

	def test_a_month_exempt_from_the_voranmeldungen_owes_none(self):
		rules = (PeriodRule(2026, "none"), PeriodRule(2026, "monthly", 7))
		self.assertEqual(
			labels(voranmeldungen(rules, (), until=date(2026, 9, 10))),
			[("Juli 2026", date(2026, 8, 10)), ("August 2026", date(2026, 9, 10))],
		)

	def test_owes_nothing_before_the_first_rule_or_without_one(self):
		rules = (PeriodRule(2026, "monthly", 10),)
		self.assertEqual(
			labels(voranmeldungen(rules, (), until=date(2026, 11, 10))),
			[("Oktober 2026", date(2026, 11, 10))],
		)
		self.assertEqual(list(voranmeldungen((), (), until=date(2026, 12, 31))), [])


class ZusammenfassendeMeldungenTest(TestCase):
	def test_owes_one_for_each_meldezeitraum_due_on_the_25th_day_after_it(self):
		found = list(zusammenfassende_meldungen(ZM_MONTHLY, until=date(2026, 3, 25)))
		self.assertEqual(
			labels(found), [("Januar 2026", date(2026, 2, 25)), ("Februar 2026", date(2026, 3, 25))]
		)
		self.assertEqual(
			found[0],
			Obligation(
				Kind.ZUSAMMENFASSENDE_MELDUNG,
				ReportingPeriod.month(2026, 1),
				"Januar 2026",
				date(2026, 2, 25),
				zm_rhythm.coverage(ZM_MONTHLY, ReportingPeriod.month(2026, 1)),
			),
		)

	def test_holidays_and_a_weekend_move_it_to_the_next_working_day(self):
		found = labels(
			zusammenfassende_meldungen(ZM_MONTHLY, until=date(2026, 12, 31), holidays=CHRISTMAS_2026)
		)
		self.assertEqual(found[-1], ("November 2026", date(2026, 12, 28)))

	def test_a_quarter_ending_on_a_saturday_is_due_on_monday(self):
		rules = (zm_rhythm.Rule(2026, 1, "quarterly"),)
		self.assertEqual(
			labels(zusammenfassende_meldungen(rules, until=date(2026, 4, 30))),
			[("I. Kalendervierteljahr 2026", date(2026, 4, 27))],
		)

	def test_monthly_filing_from_the_middle_of_a_quarter_owes_its_months_so_far_together(self):
		rules = (zm_rhythm.Rule(2026, 1, "quarterly"), zm_rhythm.Rule(2026, 2, "monthly"))
		self.assertEqual(
			labels(zusammenfassende_meldungen(rules, until=date(2026, 4, 30))),
			[("Januar und Februar 2026", date(2026, 3, 25)), ("März 2026", date(2026, 4, 27))],
		)

	def test_a_yearly_meldung_is_due_in_january(self):
		rules = (zm_rhythm.Rule(2026, 1, "yearly"),)
		self.assertEqual(
			labels(zusammenfassende_meldungen(rules, until=date(2027, 1, 31))),
			[("Kalenderjahr 2026", date(2027, 1, 25))],
		)

	def test_owes_nothing_without_a_rule(self):
		self.assertEqual(list(zusammenfassende_meldungen((), until=date(2026, 12, 31))), [])

	def test_refuses_broken_rules(self):
		rules = (zm_rhythm.Rule(2026, 1, "monthly"), zm_rhythm.Rule(2026, 1, "quarterly"))
		with self.assertRaises(ZmError):
			list(zusammenfassende_meldungen(rules, until=date(2026, 3, 31)))


class SondervorauszahlungenTest(TestCase):
	def test_a_monthly_filer_with_the_extension_pays_by_10_february(self):
		prepayments = (*DAUERFRIST_2026, Prepayment(2027, dauerfristverlaengerung=True))
		self.assertEqual(
			list(sondervorauszahlungen(MONTHLY, prepayments, until=date(2027, 12, 31))),
			[
				Obligation(Kind.SONDERVORAUSZAHLUNG, 2026, "2026", date(2026, 2, 10)),
				Obligation(Kind.SONDERVORAUSZAHLUNG, 2027, "2027", date(2027, 2, 10)),
			],
		)

	def test_a_holiday_moves_it_to_the_next_working_day(self):
		self.assertEqual(
			labels(
				sondervorauszahlungen(
					MONTHLY, DAUERFRIST_2026, until=date(2026, 12, 31), holidays={date(2026, 2, 10)}
				)
			),
			[("2026", date(2026, 2, 11))],
		)

	def test_owes_nothing_due_after_the_day_given(self):
		self.assertEqual(list(sondervorauszahlungen(MONTHLY, DAUERFRIST_2026, until=date(2026, 2, 9))), [])

	def test_a_year_without_the_extension_owes_none(self):
		self.assertEqual(
			list(sondervorauszahlungen(MONTHLY, (Prepayment(2026),), until=date(2026, 12, 31))), []
		)

	def test_a_quarterly_filer_owes_none(self):
		self.assertEqual(
			list(sondervorauszahlungen(QUARTERLY, DAUERFRIST_2026, until=date(2026, 12, 31))), []
		)

	def test_a_year_without_a_voranmeldungszeitraum_owes_none(self):
		rules = (PeriodRule(2027, "monthly"),)
		self.assertEqual(list(sondervorauszahlungen(rules, DAUERFRIST_2026, until=date(2027, 12, 31))), [])

	def test_a_company_whose_voranmeldungen_begin_later_in_the_year_pays_with_its_first(self):
		rules = (PeriodRule(2026, "none"), PeriodRule(2026, "monthly", 4))
		self.assertEqual(date(2026, 5, 10).weekday(), 6)
		self.assertEqual(
			labels(sondervorauszahlungen(rules, DAUERFRIST_2026, until=date(2026, 12, 31))),
			[("2026", date(2026, 5, 11))],
		)


class FirstVoranmeldungszeitraumTest(TestCase):
	def test_is_the_first_period_of_the_year_the_rules_set(self):
		self.assertEqual(first_voranmeldungszeitraum(MONTHLY, 2026), Period.month(2026, 1))
		self.assertEqual(first_voranmeldungszeitraum(MONTHLY, 2027), Period.month(2027, 1))
		rules = (PeriodRule(2026, "none"), PeriodRule(2026, "quarterly", 7))
		self.assertEqual(first_voranmeldungszeitraum(rules, 2026), Period.quarter(2026, 3))

	def test_is_none_for_a_year_without_one(self):
		self.assertIsNone(first_voranmeldungszeitraum(MONTHLY, 2025))
		self.assertIsNone(first_voranmeldungszeitraum((PeriodRule(2026, "none"),), 2026))


class ObligationsTest(TestCase):
	def test_lists_the_voranmeldungen_the_meldungen_and_the_sondervorauszahlung(self):
		found = obligations(MONTHLY, DAUERFRIST_2026, ZM_MONTHLY, until=date(2026, 3, 10))
		self.assertEqual(
			[(item.kind, item.label, item.due) for item in found],
			[
				(Kind.VORANMELDUNG, "Januar 2026", date(2026, 3, 10)),
				(Kind.ZUSAMMENFASSENDE_MELDUNG, "Januar 2026", date(2026, 2, 25)),
				(Kind.SONDERVORAUSZAHLUNG, "2026", date(2026, 2, 10)),
			],
		)

	def test_passes_the_holidays_to_every_kind(self):
		holidays = {date(2026, 2, 10), date(2026, 2, 25), date(2026, 3, 10)}
		found = obligations(MONTHLY, DAUERFRIST_2026, ZM_MONTHLY, until=date(2026, 3, 31), holidays=holidays)
		self.assertEqual(
			[(item.kind, item.label, item.due) for item in found],
			[
				(Kind.VORANMELDUNG, "Januar 2026", date(2026, 3, 11)),
				(Kind.ZUSAMMENFASSENDE_MELDUNG, "Januar 2026", date(2026, 2, 26)),
				(Kind.ZUSAMMENFASSENDE_MELDUNG, "Februar 2026", date(2026, 3, 25)),
				(Kind.SONDERVORAUSZAHLUNG, "2026", date(2026, 2, 11)),
			],
		)

	def test_the_kinds_are_named_as_the_filings(self):
		self.assertEqual(
			[kind.value for kind in Kind],
			[
				"Umsatzsteuer-Voranmeldung",
				"Zusammenfassende Meldung",
				"Sondervorauszahlung",
				"Umsatzsteuererklärung",
				"Körperschaftsteuererklärung",
				"Gewerbesteuererklärung",
				"E-Bilanz",
				"Feststellung Jahresabschluss",
				"Offenlegung Jahresabschluss",
			],
		)

	def test_an_obligation_has_no_notes_unless_given(self):
		owed = Obligation(Kind.SONDERVORAUSZAHLUNG, 2027, "2027", date(2027, 2, 10))
		self.assertEqual((owed.coverage, owed.notes), (None, ()))
