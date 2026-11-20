from dataclasses import FrozenInstanceError
from decimal import Decimal
from unittest import TestCase

from steuerbote.steuerbote.doctype.vat_return_settings import rules as rules_module
from steuerbote.steuerbote.doctype.vat_return_settings.rules import (
	DUPLICATE_RULE,
	MESSAGES,
	FilingRhythm,
	NoVoranmeldungError,
	PeriodRule,
	Prepayment,
	SettingsError,
	check_period_rules,
	check_prepayments,
	check_zm_rules,
	has_dauerfrist,
	own_vat_id,
	rhythm_for,
	sondervorauszahlung,
	zm_rule,
)
from steuerbote.ustva import Rhythm
from steuerbote.zm import rhythm as zm_rhythm

MONTHLY, QUARTERLY = Rhythm.MONTHLY, Rhythm.QUARTERLY


class PeriodRuleTest(TestCase):
	def test_takes_the_values_of_the_select_field(self):
		self.assertIs(PeriodRule(2026, "monthly").rhythm, FilingRhythm.MONTHLY)
		self.assertIs(PeriodRule(2026, "quarterly").rhythm, FilingRhythm.QUARTERLY)
		self.assertIs(PeriodRule(2026, "none").rhythm, FilingRhythm.NONE)
		self.assertIs(PeriodRule(2026, FilingRhythm.NONE).rhythm, FilingRhythm.NONE)

	def test_refuses_other_rhythms(self):
		for rhythm in ("yearly", "Monthly", "", None, MONTHLY, 1):
			with self.subTest(rhythm=rhythm), self.assertRaisesRegex(SettingsError, "is not a filing period"):
				PeriodRule(2026, rhythm)  # type: ignore[arg-type]

	def test_starts_in_january_unless_told_otherwise(self):
		self.assertEqual(PeriodRule(2026, "monthly").start, (2026, 1))
		self.assertEqual(PeriodRule(2026, "quarterly", 7).start, (2026, 7))

	def test_a_change_starts_with_a_kalendervierteljahr(self):
		for month in (1, 4, 7, 10):
			self.assertEqual(PeriodRule(2026, "quarterly", month).valid_from_month, month)
		for month in (0, 2, 3, 5, 6, 8, 9, 11, 12, 13, -2, True, 4.0, "4", None):
			with (
				self.subTest(month=month),
				self.assertRaisesRegex(SettingsError, "can only change in month 1, 4, 7 or 10"),
			):
				PeriodRule(2026, "quarterly", month)  # type: ignore[arg-type]

	def test_the_year_has_four_digits(self):
		for year in (0, 26, 999, 10000, True, 2026.0, "2026", None):
			with self.subTest(year=year), self.assertRaisesRegex(SettingsError, "is not a four-digit year"):
				PeriodRule(year, "monthly")  # type: ignore[arg-type]

	def test_is_immutable(self):
		with self.assertRaises(FrozenInstanceError):
			PeriodRule(2026, "monthly").year = 2027  # type: ignore[misc]


class RhythmForTest(TestCase):
	def test_without_rules_there_is_no_filing_period(self):
		with self.assertRaisesRegex(SettingsError, "No filing period is set for month 3 of 2026"):
			rhythm_for([], 2026, 3)

	def test_a_rule_holds_from_its_month_until_the_next_rule(self):
		rules = [PeriodRule(2026, "monthly"), PeriodRule(2026, "quarterly", 7)]
		self.assertIs(rhythm_for(rules, 2026, 1), MONTHLY)
		self.assertIs(rhythm_for(rules, 2026, 6), MONTHLY)
		self.assertIs(rhythm_for(rules, 2026, 7), QUARTERLY)
		self.assertIs(rhythm_for(rules, 2026, 12), QUARTERLY)

	def test_the_last_rule_of_an_earlier_year_carries_on(self):
		rules = [
			PeriodRule(2024, "quarterly"),
			PeriodRule(2025, "monthly"),
			PeriodRule(2025, "quarterly", 10),
		]
		self.assertIs(rhythm_for(rules, 2024, 3), QUARTERLY)
		self.assertIs(rhythm_for(rules, 2025, 9), MONTHLY)
		self.assertIs(rhythm_for(rules, 2026, 1), QUARTERLY)
		self.assertIs(rhythm_for(rules, 2030, 12), QUARTERLY)

	def test_the_order_of_the_rules_does_not_matter(self):
		rules = [PeriodRule(2026, "quarterly", 7), PeriodRule(2025, "quarterly"), PeriodRule(2026, "monthly")]
		self.assertIs(rhythm_for(rules, 2025, 12), QUARTERLY)
		self.assertIs(rhythm_for(rules, 2026, 6), MONTHLY)
		self.assertIs(rhythm_for(reversed(rules), 2026, 8), QUARTERLY)

	def test_months_before_the_first_rule_have_no_filing_period(self):
		with self.assertRaisesRegex(SettingsError, "month 6 of 2026"):
			rhythm_for([PeriodRule(2026, "quarterly", 7)], 2026, 6)

	def test_a_month_without_voranmeldung_is_a_clear_error(self):
		rules = [PeriodRule(2026, "quarterly"), PeriodRule(2026, "none", 7), PeriodRule(2027, "monthly")]
		self.assertIs(rhythm_for(rules, 2026, 6), QUARTERLY)
		with self.assertRaisesRegex(NoVoranmeldungError, r"^No Voranmeldung is due for month 9 of 2026\.$"):
			rhythm_for(rules, 2026, 9)
		self.assertIs(rhythm_for(rules, 2027, 1), MONTHLY)

	def test_asks_for_a_month_of_a_year(self):
		for month in (0, 13, True, "5", None):
			with self.subTest(month=month), self.assertRaisesRegex(ValueError, "between 1 and 12"):
				rhythm_for([], 2026, month)  # type: ignore[arg-type]
		with self.assertRaisesRegex(SettingsError, "is not a four-digit year"):
			rhythm_for([], "2026", 1)  # type: ignore[arg-type]


class PrepaymentTest(TestCase):
	PREPAYMENTS = (
		Prepayment(2026, dauerfristverlaengerung=True, sondervorauszahlung=Decimal("1234.56")),
		Prepayment(2027, dauerfristverlaengerung=True),
		Prepayment(2028),
	)

	def test_the_dauerfristverlaengerung_counts_for_its_year_only(self):
		self.assertTrue(has_dauerfrist(self.PREPAYMENTS, 2026))
		self.assertTrue(has_dauerfrist(self.PREPAYMENTS, 2027))
		self.assertFalse(has_dauerfrist(self.PREPAYMENTS, 2028))
		self.assertFalse(has_dauerfrist(self.PREPAYMENTS, 2029))
		self.assertFalse(has_dauerfrist([], 2026))

	def test_the_sondervorauszahlung_of_a_year(self):
		self.assertEqual(sondervorauszahlung(self.PREPAYMENTS, 2026), Decimal("1234.56"))
		self.assertEqual(sondervorauszahlung(self.PREPAYMENTS, 2027), Decimal("0"))
		self.assertEqual(sondervorauszahlung(self.PREPAYMENTS, 2029), Decimal("0"))
		self.assertIsInstance(sondervorauszahlung([], 2026), Decimal)

	def test_a_sondervorauszahlung_needs_the_dauerfristverlaengerung(self):
		with self.assertRaisesRegex(
			SettingsError,
			r"^The Sondervorauszahlung of 2026 requires the Dauerfristverlängerung of that year\.$",
		):
			Prepayment(2026, dauerfristverlaengerung=False, sondervorauszahlung=Decimal("100.00"))

	def test_the_sondervorauszahlung_is_an_amount_in_cents(self):
		for amount in (Decimal("0.001"), Decimal("NaN"), Decimal("Infinity")):
			with (
				self.subTest(amount=amount),
				self.assertRaisesRegex(SettingsError, "must be an amount in cents"),
			):
				Prepayment(2026, dauerfristverlaengerung=True, sondervorauszahlung=amount)
		with self.assertRaises(TypeError):
			Prepayment(2026, dauerfristverlaengerung=True, sondervorauszahlung=100.0)  # type: ignore[arg-type]

	def test_the_dauerfristverlaengerung_is_yes_or_no(self):
		for flag in (1, "1", None):
			with self.subTest(flag=flag), self.assertRaises(TypeError):
				Prepayment(2026, dauerfristverlaengerung=flag)  # type: ignore[arg-type]

	def test_the_year_has_four_digits(self):
		with self.assertRaisesRegex(SettingsError, "is not a four-digit year"):
			Prepayment(26)


class CheckTest(TestCase):
	def test_a_year_and_month_start_one_rule_only(self):
		check_period_rules(
			[PeriodRule(2026, "monthly"), PeriodRule(2026, "quarterly", 7), PeriodRule(2027, "monthly")]
		)
		with self.assertRaisesRegex(
			SettingsError, r"^The filing period of 2026 from month 7 is entered twice\.$"
		):
			check_period_rules(
				[PeriodRule(2026, "quarterly", 7), PeriodRule(2026, "monthly"), PeriodRule(2026, "none", 7)]
			)

	def test_a_year_has_one_row_for_its_dauerfristverlaengerung(self):
		check_prepayments([Prepayment(2026, dauerfristverlaengerung=True), Prepayment(2027)])
		with self.assertRaisesRegex(
			SettingsError, r"^The Dauerfristverlängerung of 2026 is entered twice\.$"
		):
			check_prepayments(
				[Prepayment(2026, dauerfristverlaengerung=True), Prepayment(2027), Prepayment(2026)]
			)


class OwnVatIdTest(TestCase):
	"""The company asks with its own German USt-IdNr. to confirm the USt-IdNrn. of its customers."""

	def test_keeps_the_number_entered_as_the_confirmation_writes_it(self):
		self.assertEqual(own_vat_id("de 123 456 789", None), "DE123456789")
		self.assertEqual(own_vat_id("DE123456789", "DE987654321"), "DE123456789")

	def test_takes_the_tax_id_of_the_company_when_it_is_a_german_ust_idnr(self):
		self.assertEqual(own_vat_id(None, "DE 987654321"), "DE987654321")
		self.assertEqual(own_vat_id("", "de987654321"), "DE987654321")

	def test_leaves_it_empty_when_the_tax_id_is_none(self):
		for tax_id in (None, "", "123/456/78901", "ATU12345678", "DE12345678"):
			with self.subTest(tax_id=tax_id):
				self.assertIsNone(own_vat_id(None, tax_id))

	def test_refuses_a_number_that_is_not_german(self):
		for value in ("ATU12345678", "DE12345678", "DE1234567890", "123456789"):
			with (
				self.subTest(value=value),
				self.assertRaisesRegex(SettingsError, r"is not a German USt-IdNr\.: DE and nine digits\.$"),
			):
				own_vat_id(value, "DE987654321")


class ZmRuleTest(TestCase):
	"""The rows of the rhythm of the Zusammenfassende Meldung become the rules of steuerbote.zm.rhythm."""

	def test_takes_the_values_of_the_row(self):
		self.assertEqual(
			zm_rule(2026, 5, "monthly", True),
			zm_rhythm.Rule(2026, 5, zm_rhythm.Rhythm.MONTHLY, services_monthly=True),
		)
		self.assertIs(zm_rule(2026, 4, "quarterly", False).rhythm, zm_rhythm.Rhythm.QUARTERLY)
		self.assertIs(zm_rule(2026, 1, "yearly", False).rhythm, zm_rhythm.Rhythm.YEARLY)

	def test_a_broken_row_is_a_settings_error_with_the_template_of_the_core(self):
		cases = (
			((2026, 5, "quarterly", False), zm_rhythm.NOT_A_QUARTER_START, (2026, 5)),
			((2026, 4, "yearly", False), zm_rhythm.NOT_A_YEAR_START, (2026, 4)),
			((2026, 4, "quarterly", True), zm_rhythm.SERVICES_MONTHLY_ONLY, (2026, 4)),
			((2026, 4, "weekly", False), zm_rhythm.NOT_A_RHYTHM, ("weekly",)),
			((26, 1, "monthly", False), zm_rhythm.NOT_A_YEAR, (26,)),
			((2026, 13, "monthly", False), zm_rhythm.NOT_A_MONTH, (13,)),
		)
		for values, template, filled in cases:
			with self.subTest(values=values), self.assertRaises(SettingsError) as raised:
				zm_rule(*values)
			self.assertEqual((raised.exception.template, raised.exception.values), (template, filled))

	def test_checks_the_rules_together(self):
		check_zm_rules([zm_rule(2026, 1, "quarterly", False), zm_rule(2026, 5, "monthly", False)])
		with self.assertRaises(SettingsError) as raised:
			check_zm_rules([zm_rule(2026, 4, "monthly", False), zm_rule(2026, 4, "quarterly", False)])
		self.assertEqual(
			(raised.exception.template, raised.exception.values), (zm_rhythm.DUPLICATE_RULE, (2026, 4))
		)
		with self.assertRaises(SettingsError) as raised:
			check_zm_rules([zm_rule(2026, 1, "yearly", False), zm_rule(2026, 7, "monthly", False)])
		self.assertEqual(raised.exception.template, zm_rhythm.YEAR_NOT_WHOLE)


class SettingsErrorTest(TestCase):
	def test_keeps_the_template_and_its_values_for_the_translation(self):
		error = SettingsError(DUPLICATE_RULE, 2026, 7)
		self.assertEqual(str(error), "The filing period of 2026 from month 7 is entered twice.")
		self.assertEqual(error.template, DUPLICATE_RULE)
		self.assertEqual(error.values, (2026, 7))
		self.assertIsInstance(error, ValueError)

	def test_messages_lists_every_template_of_the_module(self):
		templates = [
			value
			for name, value in vars(rules_module).items()
			if name.isupper() and isinstance(value, str) and "{0}" in value
		]
		self.assertCountEqual(MESSAGES, templates)
