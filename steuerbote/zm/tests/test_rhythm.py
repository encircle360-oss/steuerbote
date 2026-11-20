from datetime import date
from unittest import TestCase

from steuerbote.zm.errors import ZmError
from steuerbote.zm.findings import Code
from steuerbote.zm.period import ReportingPeriod
from steuerbote.zm.rhythm import (
	THRESHOLD,
	Rhythm,
	Rule,
	check_notices,
	check_rules,
	coverage,
	exceeded_in,
	goods_period,
	rule_for,
	services_period,
	threshold_findings,
	threshold_window,
)
from steuerbote.zm.tests.support import FIGURES, d

MONTHLY = Rhythm.MONTHLY
QUARTERLY = Rhythm.QUARTERLY
YEARLY = Rhythm.YEARLY


def month(year: int, number: int) -> ReportingPeriod:
	return ReportingPeriod.month(year, number)


class RuleTest(TestCase):
	def test_a_rule_holds_from_a_year_and_month(self):
		rule = Rule(2026, 5, "monthly", services_monthly=True)  # type: ignore[arg-type]
		self.assertEqual((rule.start, rule.rhythm, rule.services_monthly), ((2026, 5), MONTHLY, True))

	def test_a_quarter_starts_in_month_1_4_7_or_10(self):
		self.assertEqual(Rule(2026, 7, QUARTERLY).start, (2026, 7))
		with self.assertRaisesRegex(ZmError, "month 1, 4, 7 or 10"):
			Rule(2026, 5, QUARTERLY)

	def test_a_year_starts_in_january(self):
		"""§ 18a Absatz 9 UStG: the ZM „bis zum 25. Tag nach Ablauf jedes Kalenderjahres“."""
		with self.assertRaisesRegex(ZmError, "starts in January"):
			Rule(2026, 4, YEARLY)

	def test_services_go_into_each_monthly_zm_only_for_a_monthly_filer(self):
		"""§ 18a Absatz 3 UStG: „Soweit der Unternehmer [...] die Zusammenfassende Meldung entsprechend Absatz 1
		bis zum 25. Tag nach Ablauf jedes Kalendermonats übermittelt, kann er die nach Absatz 2 vorgesehenen
		Angaben in die Meldung für den jeweiligen Meldezeitraum aufnehmen.“"""
		with self.assertRaisesRegex(ZmError, "only when it is filed monthly"):
			Rule(2026, 1, QUARTERLY, services_monthly=True)
		with self.assertRaises(TypeError):
			Rule(2026, 1, MONTHLY, services_monthly=1)  # type: ignore[arg-type]

	def test_year_month_and_rhythm_must_exist(self):
		with self.assertRaisesRegex(ZmError, "four-digit year"):
			Rule(26, 1, MONTHLY)
		with self.assertRaisesRegex(ZmError, "four-digit year"):
			Rule(True, 1, MONTHLY)  # type: ignore[arg-type]
		with self.assertRaisesRegex(ZmError, "not a month"):
			Rule(2026, 13, MONTHLY)
		with self.assertRaisesRegex(ZmError, "not a month"):
			Rule(2026, "1", MONTHLY)  # type: ignore[arg-type]
		with self.assertRaisesRegex(ZmError, "monthly, quarterly or yearly"):
			Rule(2026, 1, "weekly")  # type: ignore[arg-type]


class CheckRulesTest(TestCase):
	def test_one_rule_per_start(self):
		with self.assertRaisesRegex(ZmError, "entered twice"):
			check_rules([Rule(2026, 1, MONTHLY), Rule(2026, 1, QUARTERLY)])

	def test_a_yearly_rule_covers_whole_years(self):
		check_rules([Rule(2026, 1, YEARLY), Rule(2027, 1, QUARTERLY)])
		with self.assertRaisesRegex(ZmError, "covers the calendar year 2026"):
			check_rules([Rule(2026, 1, YEARLY), Rule(2026, 5, MONTHLY)])

	def test_rules_in_any_order(self):
		check_rules([Rule(2027, 1, MONTHLY), Rule(2026, 1, QUARTERLY), Rule(2026, 5, MONTHLY)])


class RuleForTest(TestCase):
	def test_the_latest_rule_that_has_started(self):
		rules = [Rule(2025, 1, QUARTERLY), Rule(2026, 5, MONTHLY)]
		self.assertIs(rule_for(rules, 2026, 4).rhythm, QUARTERLY)
		self.assertIs(rule_for(rules, 2026, 5).rhythm, MONTHLY)
		self.assertIs(rule_for(rules, 2027, 12).rhythm, MONTHLY)

	def test_no_rhythm_before_the_first_rule(self):
		with self.assertRaisesRegex(ZmError, "No rhythm"):
			rule_for([Rule(2026, 1, MONTHLY)], 2025, 12)

	def test_month_must_be_a_month(self):
		with self.assertRaises(ValueError):
			rule_for([Rule(2026, 1, MONTHLY)], 2026, 0)


class GoodsPeriodTest(TestCase):
	"""The Meldezeitraum of the Lieferungen (Art L and D) of a month."""

	def test_monthly(self):
		"""§ 18a Absatz 1 Satz 1 UStG: „bis zum 25. Tag nach Ablauf jedes Kalendermonats (Meldezeitraum)“."""
		self.assertEqual(goods_period([Rule(2026, 1, MONTHLY)], 2026, 8), month(2026, 8))

	def test_quarterly(self):
		"""§ 18a Absatz 1 Satz 2 UStG: „bis zum 25. Tag nach Ablauf des Kalendervierteljahres“."""
		self.assertEqual(goods_period([Rule(2026, 1, QUARTERLY)], 2026, 8), ReportingPeriod.quarter(2026, 3))

	def test_yearly(self):
		self.assertEqual(goods_period([Rule(2026, 1, YEARLY)], 2026, 8), ReportingPeriod.calendar_year(2026))

	def test_threshold_exceeded_in_the_second_month(self):
		"""BZSt „Fristen“: quarterly so far, 57,000 euros in May: „M muss nun bis zum 25. Juni eine ZM für die
		Monate April und Mai abgeben. Die ZM für Juni und alle folgenden Monate ist dann bis zum 25. Tag nach
		Ablauf des jeweiligen Kalendermonats zu übermitteln.“"""
		rules = [Rule(2026, 1, QUARTERLY), Rule(2026, 5, MONTHLY)]
		april_and_may = ReportingPeriod.two_months(2026, 2)
		self.assertEqual(goods_period(rules, 2026, 4), april_and_may)
		self.assertEqual(goods_period(rules, 2026, 5), april_and_may)
		self.assertEqual(april_and_may.deadline(), date(2026, 6, 25))
		self.assertEqual(goods_period(rules, 2026, 6), month(2026, 6))
		self.assertEqual(goods_period(rules, 2026, 3), ReportingPeriod.quarter(2026, 1))

	def test_threshold_exceeded_in_february(self):
		"""Anleitung zur ZM, Beispiel 2: deliveries of 75,000 euros by February; „M ist verpflichtet, die Umsätze
		bis zum 25. März 01 dem Bundeszentralamt für Steuern zu melden“, in a ZM for January and February."""
		rules = [Rule(2026, 1, QUARTERLY), Rule(2026, 2, MONTHLY)]
		self.assertEqual(goods_period(rules, 2026, 1), ReportingPeriod.two_months(2026, 1))
		self.assertEqual(goods_period(rules, 2026, 1).deadline(), date(2026, 3, 25))

	def test_threshold_exceeded_in_the_third_month_reports_the_quarter(self):
		rules = [Rule(2026, 1, QUARTERLY), Rule(2026, 6, MONTHLY)]
		for number in (4, 5, 6):
			with self.subTest(number):
				self.assertEqual(goods_period(rules, 2026, number), ReportingPeriod.quarter(2026, 2))
		self.assertEqual(goods_period(rules, 2026, 7), month(2026, 7))

	def test_back_to_quarterly_with_a_quarter(self):
		rules = [Rule(2026, 1, MONTHLY), Rule(2026, 7, QUARTERLY)]
		self.assertEqual(goods_period(rules, 2026, 6), month(2026, 6))
		self.assertEqual(goods_period(rules, 2026, 7), ReportingPeriod.quarter(2026, 3))

	def test_a_first_rule_in_the_middle_of_a_quarter_starts_with_its_month(self):
		self.assertEqual(goods_period([Rule(2026, 5, MONTHLY)], 2026, 5), month(2026, 5))

	def test_two_monthly_rules_in_a_quarter(self):
		rules = [
			Rule(2026, 1, QUARTERLY),
			Rule(2026, 5, MONTHLY),
			Rule(2026, 6, MONTHLY, services_monthly=True),
		]
		self.assertEqual(goods_period(rules, 2026, 4), ReportingPeriod.two_months(2026, 2))
		self.assertEqual(goods_period(rules, 2026, 6), month(2026, 6))


class ServicesPeriodTest(TestCase):
	"""The Meldezeitraum of the sonstige Leistungen (Art S) of a month."""

	def test_quarterly_and_yearly_like_the_goods(self):
		"""§ 18a Absatz 2 Satz 1 UStG: „bis zum 25. Tag nach Ablauf jedes Kalendervierteljahres“."""
		self.assertEqual(
			services_period([Rule(2026, 1, QUARTERLY)], 2026, 2), ReportingPeriod.quarter(2026, 1)
		)
		self.assertEqual(
			services_period([Rule(2026, 1, YEARLY)], 2026, 2), ReportingPeriod.calendar_year(2026)
		)

	def test_monthly_filers_report_the_quarter_in_its_last_month(self):
		"""§ 18a Absatz 2 Satz 2 UStG: „in der Zusammenfassenden Meldung für den letzten Monat des
		Kalendervierteljahres“."""
		rules = [Rule(2026, 1, MONTHLY)]
		for number in (4, 5, 6):
			with self.subTest(number):
				self.assertEqual(services_period(rules, 2026, number), month(2026, 6))

	def test_monthly_filers_may_report_them_each_month(self):
		"""§ 18a Absatz 3 UStG: „in die Meldung für den jeweiligen Meldezeitraum“."""
		rules = [Rule(2026, 1, MONTHLY, services_monthly=True)]
		self.assertEqual(services_period(rules, 2026, 4), month(2026, 4))

	def test_the_quarter_of_the_threshold(self):
		rules = [Rule(2026, 1, QUARTERLY), Rule(2026, 5, MONTHLY)]
		for number in (4, 5, 6):
			with self.subTest(number):
				self.assertEqual(services_period(rules, 2026, number), month(2026, 6))
		each_month = [Rule(2026, 1, QUARTERLY), Rule(2026, 5, MONTHLY, services_monthly=True)]
		self.assertEqual(services_period(each_month, 2026, 4), ReportingPeriod.two_months(2026, 2))
		self.assertEqual(services_period(each_month, 2026, 6), month(2026, 6))


class CoverageTest(TestCase):
	def test_a_monthly_zm_in_the_last_month_of_a_quarter(self):
		found = coverage([Rule(2026, 1, MONTHLY)], month(2026, 6))
		self.assertEqual((found.goods, found.services), ((6,), (4, 5, 6)))
		self.assertEqual(found.goods_span, (date(2026, 6, 1), date(2026, 6, 30)))
		self.assertEqual(found.services_span, (date(2026, 4, 1), date(2026, 6, 30)))

	def test_a_monthly_zm_without_services(self):
		found = coverage([Rule(2026, 1, MONTHLY)], month(2026, 4))
		self.assertEqual((found.goods, found.services, found.services_span), ((4,), (), None))

	def test_the_first_monthly_zm_after_the_threshold(self):
		rules = [Rule(2026, 1, QUARTERLY), Rule(2026, 5, MONTHLY)]
		found = coverage(rules, ReportingPeriod.two_months(2026, 2))
		self.assertEqual((found.goods, found.services), ((4, 5), ()))
		self.assertEqual(coverage(rules, month(2026, 6)).services, (4, 5, 6))

	def test_a_quarter_and_a_year(self):
		quarter = coverage([Rule(2026, 1, QUARTERLY)], ReportingPeriod.quarter(2026, 2))
		self.assertEqual((quarter.goods, quarter.services), ((4, 5, 6), (4, 5, 6)))
		year = coverage([Rule(2026, 1, YEARLY)], ReportingPeriod.calendar_year(2026))
		self.assertEqual((year.goods, year.services), (tuple(range(1, 13)), tuple(range(1, 13))))

	def test_months_before_the_first_rule_have_no_lines(self):
		found = coverage([Rule(2026, 5, MONTHLY)], month(2026, 6))
		self.assertEqual((found.goods, found.services), ((6,), (5, 6)))

	def test_a_period_the_rules_do_not_give(self):
		with self.assertRaisesRegex(ZmError, "no Zusammenfassende Meldung for II. Kalendervierteljahr 2026"):
			coverage([Rule(2026, 1, MONTHLY)], ReportingPeriod.quarter(2026, 2))
		with self.assertRaisesRegex(ZmError, "entered twice"):
			coverage([Rule(2026, 1, MONTHLY), Rule(2026, 1, MONTHLY)], month(2026, 1))


def deliveries(**amounts: str) -> dict[tuple[int, int], object]:
	"""Kz 41 and 42 by month, keyed like m2026_05."""
	return {(int(key[1:5]), int(key[6:])): d(value) for key, value in amounts.items()}


class ThresholdTest(TestCase):
	"""§ 18a Absatz 1 Satz 2 and 3 UStG: more than 50,000 euros of Lieferungen in the current or one of the four
	previous Kalendervierteljahre exclude the quarterly ZM."""

	def test_the_threshold(self):
		self.assertEqual(THRESHOLD, d("50000"))

	def test_the_month_in_which_the_quarter_exceeds_it(self):
		self.assertEqual(exceeded_in(deliveries(m2026_04="20000.00", m2026_05="37000.00"), 2026, 2), 5)
		self.assertEqual(exceeded_in(deliveries(m2026_01="50000.01"), 2026, 1), 1)

	def test_fifty_thousand_euros_are_not_more(self):
		self.assertIsNone(exceeded_in(deliveries(m2026_04="30000.00", m2026_06="20000.00"), 2026, 2))

	def test_credit_notes_count_as_they_fall(self):
		amounts = deliveries(m2026_04="45000.00", m2026_05="-5000.00", m2026_06="10000.00")
		self.assertIsNone(exceeded_in(amounts, 2026, 2))
		self.assertEqual(exceeded_in(deliveries(m2026_04="51000.00", m2026_05="-5000.00"), 2026, 2), 4)

	def test_amounts_are_cents(self):
		with self.assertRaises(TypeError):
			exceeded_in({(2026, 4): 60000.0}, 2026, 2)  # type: ignore[dict-item]

	def test_the_window_reaches_four_quarters_back(self):
		self.assertEqual(threshold_window(month(2026, 5)), (date(2025, 4, 1), date(2026, 5, 31)))
		self.assertEqual(
			threshold_window(ReportingPeriod.calendar_year(2026)), (date(2025, 1, 1), date(2026, 12, 31))
		)

	def test_quarterly_rule_against_an_excess_in_the_second_month(self):
		amounts = deliveries(m2026_04="20000.00", m2026_05="37000.00")
		found = threshold_findings(
			[Rule(2026, 1, QUARTERLY)], ReportingPeriod.quarter(2026, 2), amounts, FIGURES
		)
		self.assertEqual([finding.code for finding in found], [Code.THRESHOLD])
		self.assertEqual(
			found[0].text,
			"Im II. Kalendervierteljahr 2026 ergeben Kz 41 und 42 bis Mai 2026 zusammen 57.000,00 €, mehr als "
			"50.000,00 €. Ab Mai 2026 ist die ZM deshalb monatlich abzugeben, die erste für den Meldezeitraum April "
			"und Mai 2026 (§ 18a Absatz 1 Satz 3 UStG).",
		)
		self.assertTrue(found[0].blocking)

	def test_rules_that_switch_in_the_month_of_the_excess(self):
		amounts = deliveries(m2026_04="20000.00", m2026_05="37000.00")
		rules = [Rule(2026, 1, QUARTERLY), Rule(2026, 5, MONTHLY)]
		self.assertEqual(threshold_findings(rules, ReportingPeriod.two_months(2026, 2), amounts, FIGURES), ())
		self.assertEqual(threshold_findings(rules, month(2026, 6), amounts, FIGURES), ())

	def test_an_excess_in_the_third_month_leaves_the_quarter(self):
		amounts = deliveries(m2026_06="60000.00")
		rules = [Rule(2026, 1, QUARTERLY)]
		self.assertEqual(threshold_findings(rules, ReportingPeriod.quarter(2026, 2), amounts, FIGURES), ())

	def test_one_of_the_four_previous_quarters(self):
		amounts = deliveries(m2025_02="60000.00")
		rules = [Rule(2025, 1, QUARTERLY)]
		found = threshold_findings(rules, ReportingPeriod.quarter(2026, 1), amounts, FIGURES)
		self.assertEqual(
			[finding.text for finding in found],
			[
				"Im I. Kalendervierteljahr 2025 ergeben Kz 41 und 42 zusammen 60.000,00 €, mehr als 50.000,00 €. "
				"Bis einschließlich I. Kalendervierteljahr 2026 ist die ZM deshalb monatlich abzugeben "
				"(§ 18a Absatz 1 Satz 2 UStG)."
			],
		)
		self.assertEqual(threshold_findings(rules, ReportingPeriod.quarter(2026, 2), amounts, FIGURES), ())

	def test_monthly_filers_are_never_held_back(self):
		amounts = deliveries(m2026_04="90000.00", m2025_04="90000.00")
		self.assertEqual(threshold_findings([Rule(2025, 1, MONTHLY)], month(2026, 4), amounts, FIGURES), ())

	def test_a_yearly_rule_against_any_excess(self):
		"""An excess of 50,000 euros in a quarter makes the ZM monthly after § 18a Absatz 1 Satz 2 and 3 UStG, so it
		rules a yearly rule out, also in the third month of the quarter."""
		amounts = deliveries(m2026_03="60000.00")
		found = threshold_findings(
			[Rule(2026, 1, YEARLY)], ReportingPeriod.calendar_year(2026), amounts, FIGURES
		)
		self.assertEqual(len(found), 1)
		self.assertEqual(
			found[0].text,
			"Im I. Kalendervierteljahr 2026 ergeben Kz 41 und 42 bis März 2026 zusammen 60.000,00 €, mehr als "
			"50.000,00 €. Ab März 2026 ist die ZM deshalb monatlich abzugeben, die erste für den Meldezeitraum "
			"I. Kalendervierteljahr 2026 (§ 18a Absatz 1 Satz 3 UStG).",
		)

	def test_findings_by_quarter(self):
		amounts = deliveries(m2025_01="60000.00", m2025_05="70000.00")
		found = threshold_findings(
			[Rule(2025, 1, QUARTERLY)], ReportingPeriod.quarter(2026, 1), amounts, FIGURES
		)
		self.assertEqual(
			[finding.text[:31] for finding in found],
			["Im I. Kalendervierteljahr 2025 ", "Im II. Kalendervierteljahr 2025"],
		)


class NoticesTest(TestCase):
	"""Anzeige and Widerruf after § 18a Absatz 1 UStG, as ZMDO takes them (rules 170015008, 170015012 and
	170015013)."""

	def test_the_anzeige_comes_with_a_monthly_zm(self):
		check_notices(month(2026, 5), anzeige=True, widerruf=False)
		for period in (ReportingPeriod.quarter(2026, 2), ReportingPeriod.two_months(2026, 2)):
			with self.subTest(period.label), self.assertRaisesRegex(ZmError, "only with a monthly"):
				check_notices(period, anzeige=True, widerruf=False)

	def test_the_widerruf_comes_with_a_quarter_or_its_last_month(self):
		check_notices(ReportingPeriod.quarter(2026, 2), anzeige=False, widerruf=True)
		check_notices(month(2026, 6), anzeige=False, widerruf=True)
		for period in (
			month(2026, 5),
			ReportingPeriod.two_months(2026, 2),
			ReportingPeriod.calendar_year(2026),
		):
			with self.subTest(period.label), self.assertRaisesRegex(ZmError, "third month of a quarter"):
				check_notices(period, anzeige=False, widerruf=True)

	def test_not_both(self):
		with self.assertRaisesRegex(ZmError, "both"):
			check_notices(month(2026, 6), anzeige=True, widerruf=True)

	def test_neither(self):
		check_notices(ReportingPeriod.calendar_year(2026), anzeige=False, widerruf=False)
