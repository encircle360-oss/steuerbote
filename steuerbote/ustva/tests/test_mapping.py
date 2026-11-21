from decimal import Decimal
from typing import ClassVar
from unittest import TestCase

from steuerbote.ustva.kennzahlen import LATEST_YEAR, UnknownYearError, catalogue_for
from steuerbote.ustva.mapping import (
	AccountRule,
	Mapping,
	MappingError,
	Side,
	TaxCheck,
	WatchedAccount,
	WatchLevel,
)


def rule(account: str, kennzahl: str, side: Side = Side.CREDIT, rate: str | None = None) -> AccountRule:
	return AccountRule(account, kennzahl, side, Decimal(rate) if rate else None)


def bad_debt(also_kennzahl: str) -> AccountRule:
	return AccountRule("2406", "81", Side.CREDIT, also_kennzahl=also_kennzahl, also_side=Side.DEBIT)


class AccountRuleTest(TestCase):
	def test_side_accepts_the_value_of_the_enum(self):
		self.assertIs(AccountRule("8400", "81", "credit").side, Side.CREDIT)  # type: ignore[arg-type]
		self.assertIs(AccountRule("1576", "66", "debit").side, Side.DEBIT)  # type: ignore[arg-type]

	def test_unknown_side_is_rejected(self):
		with self.assertRaises(ValueError):
			AccountRule("8400", "81", "left")  # type: ignore[arg-type]

	def test_rate_must_be_decimal(self):
		with self.assertRaises(TypeError):
			AccountRule("3123", "46", Side.DEBIT, 19)  # type: ignore[arg-type]
		with self.assertRaises(TypeError):
			AccountRule("3123", "46", Side.DEBIT, 19.0)  # type: ignore[arg-type]

	def test_account_number_must_be_a_non_empty_string_without_padding(self):
		for account in (8400, None, "", " ", " 8400", "8400 ", "8400\n"):
			with self.subTest(account=account), self.assertRaisesRegex(MappingError, "not an account number"):
				AccountRule(account, "81", Side.CREDIT)  # type: ignore[arg-type]

	def test_rate_must_be_a_finite_percentage_above_0_and_below_100(self):
		for rate in ("0", "-0", "100", "-19", "119", "NaN", "sNaN", "Infinity", "-Infinity"):
			with self.subTest(rate=rate), self.assertRaisesRegex(MappingError, "tax rate"):
				AccountRule("3123", "46", Side.DEBIT, Decimal(rate))

	def test_rates_inside_the_range_are_kept(self):
		for rate in ("19", "7", "10.7", "0.01", "99.99"):
			self.assertEqual(AccountRule("3123", "46", Side.DEBIT, Decimal(rate)).tax_rate, Decimal(rate))


class AlsoKennzahlTest(TestCase):
	"""A rule may report its balance to a second, informational Kennzahl, such as Kz 50 for bad debts."""

	def test_rules_report_to_no_second_kennzahl_by_default(self):
		plain = AccountRule("8400", "81", Side.CREDIT)
		self.assertIsNone(plain.also_kennzahl)
		self.assertIsNone(plain.also_side)

	def test_also_kennzahl_and_also_side_go_together(self):
		with self.assertRaisesRegex(MappingError, "account 2406: also_kennzahl and also_side go together"):
			AccountRule("2406", "81", Side.CREDIT, also_kennzahl="50")
		with self.assertRaisesRegex(MappingError, "account 2406: also_kennzahl and also_side go together"):
			AccountRule("2406", "81", Side.CREDIT, also_side=Side.DEBIT)

	def test_also_side_accepts_the_value_of_the_enum(self):
		also = AccountRule("2406", "81", Side.CREDIT, also_kennzahl="50", also_side="debit")  # type: ignore[arg-type]
		self.assertIs(also.also_side, Side.DEBIT)
		with self.assertRaises(ValueError):
			AccountRule("2406", "81", Side.CREDIT, also_kennzahl="50", also_side="left")  # type: ignore[arg-type]

	def test_informational_kennzahlen_are_accepted(self):
		self.assertEqual(Mapping("test", (bad_debt("50"),)).rule_for("2406").also_kennzahl, "50")
		minderung = AccountRule("1579", "66", Side.DEBIT, also_kennzahl="37", also_side=Side.CREDIT)
		self.assertEqual(Mapping("test", (minderung,)).rule_for("1579").also_side, Side.CREDIT)

	def test_also_kennzahl_must_be_known_and_hold_an_amount(self):
		cases = {
			"99": "account 2406: unknown Kennzahl 99",
			"10": "account 2406: Kennzahl 10 holds no amount",
			"83": "account 2406: Kennzahl 83 is computed, not mapped",
		}
		for number, message in cases.items():
			with self.subTest(number=number), self.assertRaisesRegex(MappingError, message):
				Mapping("test", (bad_debt(number),))

	def test_also_kennzahl_must_not_change_the_amount_owed(self):
		for number in ("86", "66", "65", "39"):
			with (
				self.subTest(number=number),
				self.assertRaisesRegex(
					MappingError, f"account 2406: Kennzahl {number} changes the amount owed"
				),
			):
				Mapping("test", (bad_debt(number),))

	def test_also_kennzahl_must_not_need_a_tax_of_its_own(self):
		with self.assertRaisesRegex(MappingError, "account 2406: Kennzahl 46 has a tax Kennzahl of its own"):
			Mapping("test", (bad_debt("46"),))

	def test_also_kennzahl_must_differ_from_the_kennzahl_of_the_rule(self):
		twice = AccountRule("8125", "41", Side.CREDIT, also_kennzahl="41", also_side=Side.CREDIT)
		with self.assertRaisesRegex(
			MappingError, "account 8125: also_kennzahl 41 is the rule's own Kennzahl"
		):
			Mapping("test", (twice,))


class TaxCheckTest(TestCase):
	def test_accounts_must_be_sequences_not_strings(self):
		with self.assertRaisesRegex(MappingError, "not a string"):
			TaxCheck("x", "8400", ("1776",))  # type: ignore[arg-type]
		with self.assertRaisesRegex(MappingError, "not a string"):
			TaxCheck("x", ("8400",), "1776")  # type: ignore[arg-type]

	def test_accounts_are_stored_as_tuples(self):
		check = TaxCheck("x", ["8400"], ["1776"], "credit")  # type: ignore[arg-type]
		self.assertEqual(check.base_accounts, ("8400",))
		self.assertEqual(check.tax_accounts, ("1776",))
		self.assertIs(check.side, Side.CREDIT)

	def test_account_numbers_must_be_non_empty_strings(self):
		with self.assertRaisesRegex(MappingError, "not an account number"):
			TaxCheck("x", (8400,), ("1776",))  # type: ignore[list-item]
		with self.assertRaisesRegex(MappingError, "not an account number"):
			TaxCheck("x", ("8400",), ("",))

	def test_padded_account_numbers_are_rejected(self):
		with self.assertRaisesRegex(MappingError, "not an account number"):
			TaxCheck("x", (" 8400",), ("1776",))
		with self.assertRaisesRegex(MappingError, "not an account number"):
			TaxCheck("x", ("8400",), ("1776 ",))


class RuleValidationTest(TestCase):
	def test_unknown_kennzahl_is_rejected(self):
		with self.assertRaisesRegex(MappingError, "unknown Kennzahl 99"):
			Mapping("test", (rule("8400", "99"),))

	def test_account_mapped_twice_is_rejected(self):
		with self.assertRaisesRegex(MappingError, "8400 is mapped twice"):
			Mapping("test", (rule("8400", "81"), rule("8400", "86")))

	def test_flag_kennzahl_cannot_take_an_account(self):
		with self.assertRaisesRegex(MappingError, "holds no amount"):
			Mapping("test", (rule("8400", "10"),))

	def test_balance_kennzahl_cannot_take_an_account(self):
		with self.assertRaisesRegex(MappingError, "83 is computed"):
			Mapping("test", (rule("1780", "83"),))

	def test_rate_on_a_statutory_base_is_rejected(self):
		with self.assertRaisesRegex(MappingError, "81 takes no tax rate"):
			Mapping("test", (rule("8400", "81", rate="19"),))

	def test_rate_on_a_tax_kennzahl_is_rejected(self):
		with self.assertRaisesRegex(MappingError, "66 takes no tax rate"):
			Mapping("test", (rule("1576", "66", Side.DEBIT, "19"),))

	def test_tax_cannot_be_derived_and_mapped_at_the_same_time(self):
		with self.assertRaisesRegex(
			MappingError, "47 is derived from account 3123 and mapped from account 1787"
		):
			Mapping("test", (rule("3123", "46", Side.DEBIT, "19"), rule("1787", "47")))

	def test_tax_of_a_reported_pair_may_be_mapped_directly(self):
		mapping = Mapping("test", (rule("3123", "46", Side.DEBIT), rule("1787", "47")))
		self.assertEqual(mapping.rule_for("1787").kennzahl, "47")


class ReportedTaxValidationTest(TestCase):
	"""A base whose tax the form reports in its own Kennzahl must feed that Kennzahl one way or the other."""

	PAIRS: ClassVar[dict[str, str]] = {
		"35": "36",
		"76": "80",
		"95": "98",
		"94": "96",
		"46": "47",
		"73": "74",
		"84": "85",
	}

	def test_the_pairs_are_those_of_the_form(self):
		pairs = {
			number: k.tax_kennzahl for number, k in catalogue_for(2026).items() if k.tax_kennzahl is not None
		}
		self.assertEqual(pairs, self.PAIRS)

	def test_reverse_charge_base_without_tax_is_rejected(self):
		with self.assertRaisesRegex(
			MappingError,
			"Kennzahl 47 is fed by nothing: give the rules of Kennzahl 46 a tax rate or map a tax account to 47",
		):
			Mapping("test", (rule("3123", "46", Side.DEBIT),))
		with self.assertRaisesRegex(
			MappingError,
			"Kennzahl 85 is fed by nothing: give the rules of Kennzahl 84 a tax rate or map a tax account to 85",
		):
			Mapping("test", (rule("3125", "84", Side.DEBIT), rule("1577", "67", Side.DEBIT)))

	def test_every_base_with_a_tax_kennzahl_needs_its_tax(self):
		for base, tax in self.PAIRS.items():
			with (
				self.subTest(base=base),
				self.assertRaisesRegex(MappingError, f"Kennzahl {tax} is fed by nothing"),
			):
				Mapping("test", (rule("3000", base, Side.DEBIT),))

	def test_mix_of_rated_and_unrated_rules_is_rejected(self):
		with self.assertRaisesRegex(MappingError, "Kennzahl 46: mix of rated and unrated rules"):
			Mapping("test", (rule("3123", "46", Side.DEBIT, "19"), rule("3113", "46", Side.DEBIT)))

	def test_mix_is_rejected_even_when_a_tax_account_feeds_the_tax(self):
		rules = (rule("3125", "84", Side.DEBIT), rule("3115", "84", Side.DEBIT, "7"), rule("1787", "85"))
		with self.assertRaisesRegex(MappingError, "Kennzahl 84: mix of rated and unrated rules"):
			Mapping("test", rules)

	def test_rates_on_every_rule_of_a_base_are_accepted(self):
		rules = (rule("3123", "46", Side.DEBIT, "19"), rule("3113", "46", Side.DEBIT, "7"))
		self.assertEqual(Mapping("test", rules).rules, rules)

	def test_tax_account_without_a_mapped_base_is_accepted(self):
		self.assertEqual(Mapping("test", (rule("1787", "47"),)).rule_for("1787").kennzahl, "47")


class CheckValidationTest(TestCase):
	def test_label_is_required(self):
		with self.assertRaisesRegex(MappingError, "needs a label"):
			Mapping("test", (rule("8400", "81"),), (TaxCheck("", ("8400",), ("1776",)),))

	def test_accounts_are_required(self):
		with self.assertRaisesRegex(MappingError, "needs base accounts and tax accounts"):
			Mapping("test", (rule("8400", "81"),), (TaxCheck("x", (), ("1776",)),))
		with self.assertRaisesRegex(MappingError, "needs base accounts and tax accounts"):
			Mapping("test", (rule("8400", "81"),), (TaxCheck("x", ("8400",), ()),))

	def test_base_account_must_be_mapped(self):
		with self.assertRaisesRegex(MappingError, "account 8300 is not mapped"):
			Mapping("test", (rule("8400", "81"),), (TaxCheck("x", ("8300",), ("1771",)),))

	def test_base_account_must_carry_a_rate(self):
		with self.assertRaisesRegex(MappingError, "41 carries no tax rate"):
			Mapping("test", (rule("8125", "41"),), (TaxCheck("x", ("8125",), ("1776",)),))

	def test_tax_account_cannot_be_checked_twice(self):
		rules = (rule("8400", "81"), rule("8300", "86"))
		with self.assertRaisesRegex(MappingError, "1776 is checked twice"):
			Mapping("test", rules, (TaxCheck("a", ("8400",), ("1776",)), TaxCheck("b", ("8300",), ("1776",))))

	def test_base_account_cannot_be_listed_twice_in_one_check(self):
		with self.assertRaisesRegex(MappingError, "base account 8400 is checked twice"):
			Mapping("test", (rule("8400", "81"),), (TaxCheck("x", ("8400", "8400"), ("1776",)),))

	def test_base_account_cannot_be_in_two_checks(self):
		checks = (TaxCheck("a", ("8400",), ("1776",)), TaxCheck("b", ("8400",), ("1775",)))
		with self.assertRaisesRegex(MappingError, "base account 8400 is checked twice"):
			Mapping("test", (rule("8400", "81"),), checks)

	def test_tax_account_of_a_check_cannot_be_mapped(self):
		rules = (rule("8400", "81"), rule("1776", "69"))
		with self.assertRaisesRegex(
			MappingError, "check 'Umsatzsteuer 19 %': tax account 1776 is also mapped to Kennzahl 69"
		):
			Mapping("test", rules, (TaxCheck("Umsatzsteuer 19 %", ("8400",), ("1776",)),))

	def test_base_account_cannot_be_its_own_tax_account(self):
		with self.assertRaisesRegex(MappingError, "tax account 8400 is also mapped to Kennzahl 81"):
			Mapping("test", (rule("8400", "81"),), (TaxCheck("x", ("8400",), ("8400",)),))


class WatchedValidationTest(TestCase):
	def test_watched_account_cannot_be_mapped(self):
		with self.assertRaisesRegex(MappingError, "8400 is watched but also mapped or checked"):
			Mapping("test", (rule("8400", "81"),), watched=("8400",))

	def test_watched_account_cannot_be_checked(self):
		with self.assertRaisesRegex(MappingError, "1776 is watched but also mapped or checked"):
			Mapping("test", (rule("8400", "81"),), (TaxCheck("x", ("8400",), ("1776",)),), ("1776",))

	def test_watched_must_be_a_sequence(self):
		with self.assertRaisesRegex(MappingError, "not a string"):
			Mapping("test", (), watched="1779")  # type: ignore[arg-type]

	def test_watched_account_numbers_must_not_be_padded(self):
		with self.assertRaisesRegex(MappingError, "not an account number"):
			Mapping("test", (), watched=("1779 ",))

	def test_an_account_number_is_watched_at_the_blocking_level(self):
		mapping = Mapping("test", (), watched=("1548", WatchedAccount("8603", WatchLevel.HINT)))
		self.assertEqual(mapping.watched, (WatchedAccount("1548"), WatchedAccount("8603", WatchLevel.HINT)))

	def test_an_account_watched_twice_is_rejected_whatever_its_levels(self):
		for second in ("1548", WatchedAccount("1548", WatchLevel.HINT)):
			with (
				self.subTest(second=second),
				self.assertRaisesRegex(MappingError, "account 1548 is watched twice"),
			):
				Mapping("test", (), watched=("1548", second))

	def test_an_account_watched_for_a_hint_cannot_be_mapped_or_checked_either(self):
		hint = WatchLevel.HINT
		with self.assertRaisesRegex(MappingError, "8400 is watched but also mapped or checked"):
			Mapping("test", (rule("8400", "81"),), watched=(WatchedAccount("8400", hint),))
		with self.assertRaisesRegex(MappingError, "1776 is watched but also mapped or checked"):
			Mapping(
				"test",
				(rule("8400", "81"),),
				(TaxCheck("x", ("8400",), ("1776",)),),
				(WatchedAccount("1776", hint),),
			)


class WatchedAccountTest(TestCase):
	def test_a_watched_account_blocks_unless_it_is_watched_for_a_hint(self):
		self.assertIs(WatchedAccount("1548").level, WatchLevel.BLOCKING)
		self.assertIs(WatchedAccount("8603", WatchLevel.HINT).level, WatchLevel.HINT)

	def test_the_levels_are_blocking_and_hint(self):
		self.assertEqual([level.value for level in WatchLevel], ["blocking", "hint"])

	def test_level_accepts_the_value_of_the_enum(self):
		self.assertIs(WatchedAccount("8603", "hint").level, WatchLevel.HINT)  # type: ignore[arg-type]
		self.assertIs(WatchedAccount("1548", "blocking").level, WatchLevel.BLOCKING)  # type: ignore[arg-type]

	def test_unknown_level_is_rejected(self):
		with self.assertRaises(ValueError):
			WatchedAccount("8603", "warning")  # type: ignore[arg-type]

	def test_account_number_must_be_a_non_empty_string_without_padding(self):
		for account in (8603, None, "", " 8603", "8603 "):
			with self.subTest(account=account), self.assertRaisesRegex(MappingError, "not an account number"):
				WatchedAccount(account)  # type: ignore[arg-type]


class LookupTest(TestCase):
	def test_finds_the_rule_of_an_account(self):
		mapping = Mapping("test", (rule("8400", "81"),))
		self.assertEqual(mapping.rule_for("8400"), rule("8400", "81"))

	def test_unmapped_account_has_no_rule(self):
		self.assertIsNone(Mapping("test", ()).rule_for("1200"))

	def test_rate_for_prefers_the_rate_of_the_rule_over_the_statutory_rate(self):
		mapping = Mapping("test", (rule("8300", "86"), rule("3113", "46", Side.DEBIT, "7")))
		self.assertEqual(mapping.rate_for(mapping.rule_for("8300")), Decimal("7"))
		self.assertEqual(mapping.rate_for(mapping.rule_for("3113")), Decimal("7"))

	def test_rate_for_rejects_a_base_without_rate(self):
		mapping = Mapping("test", (rule("8125", "41"),))
		with self.assertRaisesRegex(MappingError, "41 carries no tax rate"):
			mapping.rate_for(mapping.rule_for("8125"))

	def test_watched_at_lists_the_accounts_of_a_level_in_their_order(self):
		hint = WatchLevel.HINT
		mapping = Mapping(
			"test",
			(),
			watched=("1725", WatchedAccount("8606", hint), "1548", WatchedAccount("8603", hint)),
		)
		self.assertEqual(mapping.watched_at(WatchLevel.BLOCKING), ("1725", "1548"))
		self.assertEqual(mapping.watched_at(hint), ("8606", "8603"))
		self.assertEqual(Mapping("test", ()).watched_at(hint), ())

	def test_sequences_are_stored_as_tuples_and_the_mapping_is_immutable(self):
		mapping = Mapping("test", [rule("8400", "81")], [TaxCheck("x", ["8400"], ["1776"])], ["1779"])  # type: ignore[arg-type]
		self.assertIsInstance(mapping.rules, tuple)
		self.assertIsInstance(mapping.checks, tuple)
		self.assertIsInstance(mapping.watched, tuple)
		with self.assertRaises(AttributeError):
			mapping.chart = "other"  # type: ignore[misc]


class YearTest(TestCase):
	def test_mapping_defaults_to_the_latest_form(self):
		mapping = Mapping("test", (rule("8400", "81"),))
		self.assertEqual(mapping.year, LATEST_YEAR)
		self.assertEqual(mapping.catalogue["81"].line, 13)

	def test_for_year_keeps_the_rules_and_changes_the_year(self):
		mapping = Mapping("test", (rule("8400", "81"),), year=2026)
		same = mapping.for_year(2026)
		self.assertEqual(same, mapping)
		self.assertEqual(same.rules, mapping.rules)

	def test_for_year_keeps_the_levels_of_the_watched_accounts(self):
		mapping = Mapping("test", (), watched=("1548", WatchedAccount("8603", WatchLevel.HINT)))
		self.assertEqual(mapping.for_year(2026).watched, mapping.watched)

	def test_year_without_catalogue_is_refused(self):
		with self.assertRaisesRegex(UnknownYearError, "2019"):
			Mapping("test", (rule("8400", "81"),), year=2019)
		with self.assertRaisesRegex(UnknownYearError, str(LATEST_YEAR + 1)):
			Mapping("test", (rule("8400", "81"),)).for_year(LATEST_YEAR + 1)

	def test_year_must_be_an_int(self):
		for year in ("2026", 2026.0, Decimal("2026"), True, None):
			with self.subTest(year=year), self.assertRaisesRegex(TypeError, "year must be an int"):
				Mapping("test", (rule("8400", "81"),), year=year)  # type: ignore[arg-type]
		with self.assertRaisesRegex(TypeError, "year must be an int, not str"):
			Mapping("test", (rule("8400", "81"),)).for_year("2026")  # type: ignore[arg-type]
