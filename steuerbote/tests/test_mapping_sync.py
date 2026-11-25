"""Tests for steuerbote.mapping_sync, plain unittest without Frappe so that every test runner collects them."""

import json
from decimal import Decimal
from typing import Any
from unittest import TestCase

from steuerbote.mapping_sync import (
	ACCOUNT,
	ANNUAL_FIELD,
	ANNUAL_RULE,
	CHECK,
	FILE_FORMAT,
	annual_default_items,
	annual_rows_for_accounts,
	annual_rows_of_items,
	annual_rules_of_rows,
	annual_split,
	body_of_items,
	check_annual_rows,
	choices_of_rows,
	default_items,
	defaults_for_accounts,
	dump_items,
	file_body,
	items_of_body,
	items_of_file_body,
	items_of_mapping,
	items_of_rows,
	load_items,
	rows_of_items,
	rows_to_mapping,
)
from steuerbote.ustjahr.split import AnnualRule, Choice, How, SplitError
from steuerbote.ustjahr.years import LATEST_YEAR as ANNUAL_YEAR
from steuerbote.ustva import (
	DEFAULTS,
	LATEST_YEAR,
	AccountRule,
	LedgerLine,
	Mapping,
	MappingError,
	Side,
	TaxCheck,
	UnknownYearError,
	WatchedAccount,
	WatchLevel,
	calculate,
	default_mapping,
)

CREDIT = Side.CREDIT
DEBIT = Side.DEBIT
HINT = WatchLevel.HINT


def rule_row(account_number: str | None, kennzahl: Any = "81", side: Any = "credit", **fields: Any) -> dict:
	return {"account_number": account_number, "kennzahl": kennzahl, "side": side, **fields}


def check_row(label: Any = "Umsatzsteuer 19 %", base: Any = "8400", tax: Any = "1776", **fields: Any) -> dict:
	return {"label": label, "base_accounts": base, "tax_accounts": tax, **fields}


def mapping_of(rule_rows=(), check_rows=(), watched_rows=(), chart="SKR03", year=LATEST_YEAR) -> Mapping:
	return rows_to_mapping(chart, rule_rows, check_rows, watched_rows, year)


def only_rule(**fields: Any) -> AccountRule:
	(rule,) = mapping_of([rule_row(**fields)]).rules
	return rule


def accounts_of(mapping: Mapping) -> set[str]:
	return {
		*(rule.account_number for rule in mapping.rules),
		*(account for check in mapping.checks for account in (*check.base_accounts, *check.tax_accounts)),
		*(watched.account_number for watched in mapping.watched),
	}


def with_floats(rule_rows: list[dict]) -> list[dict]:
	"""The rows as Frappe stores them: a Float field holds a float, and 0 when it is empty."""
	return [{**row, "tax_rate": float(row["tax_rate"] or 0)} for row in rule_rows]


class RowsToMappingTest(TestCase):
	def test_builds_rules_checks_and_watched_accounts_from_rows(self):
		mapping = mapping_of(
			[
				rule_row("8400", "81", "credit"),
				rule_row("3123", "46", "debit", tax_rate=19.0),
				rule_row("1576", "66", "debit"),
			],
			[check_row("Umsatzsteuer 19 %", "8400", "1776", side="credit")],
			[{"account_number": "1548"}],
		)
		self.assertEqual(
			mapping,
			Mapping(
				"SKR03",
				(
					AccountRule("8400", "81", CREDIT),
					AccountRule("3123", "46", DEBIT, Decimal("19")),
					AccountRule("1576", "66", DEBIT),
				),
				(TaxCheck("Umsatzsteuer 19 %", ("8400",), ("1776",), CREDIT),),
				(WatchedAccount("1548"),),
				LATEST_YEAR,
			),
		)

	def test_keeps_the_chart_and_validates_against_the_given_year(self):
		mapping = mapping_of([rule_row("8400")], chart="Eigener Kontenrahmen", year=2026)
		self.assertEqual((mapping.chart, mapping.year), ("Eigener Kontenrahmen", 2026))
		with self.assertRaisesRegex(UnknownYearError, "2019"):
			mapping_of([rule_row("8400")], year=2019)

	def test_ignores_the_other_fields_of_a_frappe_row(self):
		row = rule_row("8400", name="abc123", idx=1, parent="X GmbH", account="8400 - Erlöse - X")
		self.assertEqual(mapping_of([row]).rules, (AccountRule("8400", "81", CREDIT),))

	def test_validation_of_the_core_applies(self):
		with self.assertRaisesRegex(MappingError, "account 8400 is mapped twice"):
			mapping_of([rule_row("8400", "81"), rule_row("8400", "86")])
		with self.assertRaisesRegex(MappingError, "account 8400: unknown Kennzahl 99"):
			mapping_of([rule_row("8400", "99")])


class RuleRowTest(TestCase):
	def test_rate_keeps_the_digits_frappe_stores_as_a_float(self):
		self.assertEqual(
			only_rule(account_number="3123", kennzahl="46", tax_rate=19.0).tax_rate, Decimal("19")
		)
		self.assertEqual(str(only_rule(account_number="3123", kennzahl="46", tax_rate=10.7).tax_rate), "10.7")

	def test_rate_given_as_text_or_decimal_is_taken_as_written(self):
		self.assertEqual(only_rule(account_number="3123", kennzahl="46", tax_rate="7").tax_rate, Decimal("7"))
		self.assertEqual(
			only_rule(account_number="3123", kennzahl="46", tax_rate=Decimal("5.5")).tax_rate, Decimal("5.5")
		)

	def test_empty_rate_means_no_rate(self):
		for rate in (None, "", 0, 0.0, -0.0, "0", Decimal("0.00")):
			with self.subTest(rate=rate):
				self.assertIsNone(only_rule(account_number="8400", tax_rate=rate).tax_rate)

	def test_rate_that_is_not_a_number_is_refused(self):
		with self.assertRaisesRegex(MappingError, "account 3123: tax rate 'nineteen' is not a number"):
			mapping_of([rule_row("3123", "46", "debit", tax_rate="nineteen")])

	def test_rate_outside_a_percentage_is_refused(self):
		for rate in (100.0, -19.0, float("nan"), float("inf")):
			with self.subTest(rate=rate), self.assertRaisesRegex(MappingError, "account 3123: tax rate"):
				mapping_of([rule_row("3123", "46", "debit", tax_rate=rate)])

	def test_kennzahl_is_read_without_surrounding_blanks(self):
		self.assertEqual(only_rule(account_number="8400", kennzahl=" 81 ").kennzahl, "81")

	def test_missing_kennzahl_is_refused(self):
		for kennzahl in (None, "", "  "):
			with (
				self.subTest(kennzahl=kennzahl),
				self.assertRaisesRegex(MappingError, "account 8400: no Kennzahl"),
			):
				mapping_of([rule_row("8400", kennzahl)])

	def test_side_is_credit_or_debit(self):
		self.assertIs(only_rule(account_number="8400", side="credit").side, CREDIT)
		self.assertIs(only_rule(account_number="1576", kennzahl="66", side="debit").side, DEBIT)
		for side in (None, "", "left", "Credit"):
			with (
				self.subTest(side=side),
				self.assertRaisesRegex(
					MappingError, f"account 8400: side must be credit or debit, not {side!r}"
				),
			):
				mapping_of([rule_row("8400", side=side)])

	def test_additional_kennzahl_reports_the_balance_once_more(self):
		bad_debt = only_rule(account_number="2406", also_kennzahl=" 50", also_side="debit")
		self.assertEqual((bad_debt.also_kennzahl, bad_debt.also_side), ("50", DEBIT))

	def test_empty_additional_kennzahl_and_side_mean_none(self):
		for value in (None, ""):
			with self.subTest(value=value):
				plain = only_rule(account_number="8400", also_kennzahl=value, also_side=value)
				self.assertIsNone(plain.also_kennzahl)
				self.assertIsNone(plain.also_side)

	def test_additional_side_must_be_credit_or_debit(self):
		with self.assertRaisesRegex(MappingError, "account 2406: side must be credit or debit, not 'left'"):
			mapping_of([rule_row("2406", also_kennzahl="50", also_side="left")])

	def test_additional_kennzahl_and_side_go_together(self):
		with self.assertRaisesRegex(MappingError, "account 2406: also_kennzahl and also_side go together"):
			mapping_of([rule_row("2406", also_kennzahl="50")])

	def test_account_numbers_are_compared_as_written(self):
		with self.assertRaisesRegex(MappingError, "' 8400' is not an account number"):
			mapping_of([rule_row(" 8400")])

	def test_account_without_number_is_refused_by_its_name(self):
		for number in (None, ""):
			with (
				self.subTest(number=number),
				self.assertRaisesRegex(MappingError, "account Bank - X has no account number"),
			):
				mapping_of([rule_row(number, account="Bank - X")])

	def test_row_without_account_is_refused_by_its_row_number(self):
		with self.assertRaisesRegex(MappingError, "rule in row 3 has no account"):
			mapping_of([rule_row(None, idx=3)])
		with self.assertRaisesRegex(MappingError, "^rule has no account$"):
			mapping_of([rule_row(None)])


class CheckRowTest(TestCase):
	def test_accounts_are_separated_by_commas_blanks_or_line_breaks(self):
		(check,) = mapping_of(
			[rule_row(number) for number in ("8400", "8401", "8402", "8403")],
			[check_row(base="8400, 8401,8402\n8403 ", tax=" 1776,\n")],
		).checks
		self.assertEqual(check.base_accounts, ("8400", "8401", "8402", "8403"))
		self.assertEqual(check.tax_accounts, ("1776",))

	def test_side_is_credit_unless_the_row_says_debit(self):
		rules = [rule_row("8400")]
		for side in (None, "", "credit"):
			with self.subTest(side=side):
				self.assertIs(mapping_of(rules, [check_row(side=side)]).checks[0].side, CREDIT)
		self.assertIs(mapping_of(rules, [check_row(side="debit")]).checks[0].side, DEBIT)

	def test_wrong_side_is_refused(self):
		with self.assertRaisesRegex(
			MappingError, "check 'Umsatzsteuer 19 %': side must be credit or debit, not 'left'"
		):
			mapping_of([rule_row("8400")], [check_row(side="left")])

	def test_label_is_read_without_surrounding_blanks(self):
		self.assertEqual(
			mapping_of([rule_row("8400")], [check_row(" Umsatzsteuer 19 % ")]).checks[0].label,
			"Umsatzsteuer 19 %",
		)

	def test_check_needs_a_label_and_accounts(self):
		rules = [rule_row("8400")]
		for label in (None, "", " "):
			with self.subTest(label=label), self.assertRaisesRegex(MappingError, "a tax check needs a label"):
				mapping_of(rules, [check_row(label)])
		for base, tax in ((None, "1776"), ("8400", ""), (" , ", "1776")):
			with (
				self.subTest(base=base, tax=tax),
				self.assertRaisesRegex(MappingError, "needs base accounts and tax accounts"),
			):
				mapping_of(rules, [check_row(base=base, tax=tax)])

	def test_base_accounts_must_be_mapped(self):
		with self.assertRaisesRegex(MappingError, "check 'Umsatzsteuer 19 %': account 8300 is not mapped"):
			mapping_of([rule_row("8400")], [check_row(base="8400, 8300")])


class DerivedBaseRowTest(TestCase):
	"""The Kennzahl a check gives the base of a voucher that books its tax but none of its bases."""

	rules = (rule_row("3125", "84", "debit", tax_rate=19.0),)

	def check(self, **fields: Any) -> TaxCheck:
		(check,) = mapping_of(self.rules, [check_row("13b", "3125", "1787", **fields)]).checks
		return check

	def test_the_kennzahl_of_the_row_is_taken_without_blanks(self):
		self.assertEqual(self.check(derived_base="84").derived_base, "84")
		self.assertEqual(self.check(derived_base=" 84 ").derived_base, "84")

	def test_an_empty_field_derives_nothing(self):
		for empty in (None, "", " "):
			with self.subTest(empty=empty):
				self.assertIsNone(self.check(derived_base=empty).derived_base)
		self.assertIsNone(self.check().derived_base)

	def test_the_core_refuses_a_kennzahl_that_takes_no_derived_base(self):
		with self.assertRaisesRegex(MappingError, "check '13b': Kennzahl 81 takes no base derived"):
			self.check(derived_base="81")

	def test_an_item_names_the_kennzahl_only_when_there_is_one(self):
		items = items_of_rows(
			self.rules,
			[check_row("13b", "3125", "1787", derived_base="84"), check_row("other", "3125", "1785")],
			[],
		)
		self.assertEqual(
			items[(CHECK, "13b")],
			{"base_accounts": "3125", "tax_accounts": "1787", "side": "credit", "derived_base": "84"},
		)
		self.assertEqual(
			items[(CHECK, "other")], {"base_accounts": "3125", "tax_accounts": "1785", "side": "credit"}
		)

	def test_the_rows_of_items_give_it_back(self):
		items = items_of_rows(self.rules, [check_row("13b", "3125", "1787", derived_base="84")], [])
		self.assertEqual(rows_of_items(items).check_rows[0]["derived_base"], "84")
		self.assertEqual(items_of_rows(*rows_of_items(items)), items)

	def test_the_body_holds_it_only_when_there_is_one(self):
		items = items_of_rows(
			self.rules,
			[check_row("13b", "3125", "1787", derived_base="84"), check_row("other", "3125", "1785")],
			[],
		)
		first, second = body_of_items(items)["checks"]
		self.assertEqual(first["derived_base"], "84")
		self.assertNotIn("derived_base", second)
		self.assertEqual(items_of_body(body_of_items(items)), items)

	def test_a_body_of_an_earlier_version_without_it_is_read(self):
		body = {
			"rules": [
				{
					"account_number": "3125",
					"kennzahl": "84",
					"side": "debit",
					"tax_rate": "19",
					"also_kennzahl": None,
					"also_side": None,
				}
			],
			"checks": [
				{"label": "13b", "base_accounts": ["3125"], "tax_accounts": ["1787"], "side": "credit"}
			],
			"watched": [],
		}
		self.assertEqual(
			items_of_body(body)[(CHECK, "13b")],
			{"base_accounts": "3125", "tax_accounts": "1787", "side": "credit"},
		)

	def test_a_body_with_a_kennzahl_of_another_shape_is_refused(self):
		body = body_of_items(
			items_of_rows(self.rules, [check_row("13b", "3125", "1787", derived_base="84")], [])
		)
		body["checks"][0]["derived_base"] = 84
		with self.assertRaisesRegex(MappingError, "checks: derived_base cannot be 84"):
			items_of_body(body)

	def test_the_defaults_give_it_to_the_checks_the_company_keeps(self):
		_, check_rows, _, _ = defaults_for_accounts(
			"SKR03", LATEST_YEAR, frozenset({"3123", "1787", "8400", "1776", "3425", "1774"})
		)
		self.assertEqual(
			[(row["label"], row.get("derived_base")) for row in check_rows],
			[
				("Umsatzsteuer 19 %", None),
				("Umsatzsteuer aus innergemeinschaftlichem Erwerb 19 %", "89"),
				("Umsatzsteuer nach § 13b UStG 19 %", "84"),
			],
		)
		mapping = rows_to_mapping(
			"SKR03",
			*defaults_for_accounts("SKR03", LATEST_YEAR, frozenset({"3123", "1787"}))[:3],
			LATEST_YEAR,
		)
		self.assertEqual(mapping.checks[0].derived_base, "84")


class WatchedRowTest(TestCase):
	def test_watched_accounts_are_taken_by_number(self):
		watched = [{"account_number": "1548", "account": "1548 - Vorsteuer - X"}, {"account_number": "1725"}]
		self.assertEqual(
			mapping_of(watched_rows=watched).watched, (WatchedAccount("1548"), WatchedAccount("1725"))
		)

	def test_the_level_of_a_row_is_taken(self):
		watched = [
			{"account_number": "8603", "level": "hint"},
			{"account_number": "1548", "level": "blocking"},
		]
		self.assertEqual(
			mapping_of(watched_rows=watched).watched, (WatchedAccount("8603", HINT), WatchedAccount("1548"))
		)

	def test_a_row_without_level_blocks(self):
		for level in (None, ""):
			with self.subTest(level=level):
				(watched,) = mapping_of(watched_rows=[{"account_number": "1548", "level": level}]).watched
				self.assertIs(watched.level, WatchLevel.BLOCKING)

	def test_an_unknown_level_is_refused(self):
		with self.assertRaisesRegex(
			MappingError, "account 8603: level must be blocking or hint, not 'warning'"
		):
			mapping_of(watched_rows=[{"account_number": "8603", "level": "warning"}])

	def test_an_account_watched_twice_is_refused(self):
		watched = [{"account_number": "8603", "level": "hint"}, {"account_number": "8603"}]
		with self.assertRaisesRegex(MappingError, "account 8603 is watched twice"):
			mapping_of(watched_rows=watched)

	def test_watched_account_without_number_is_refused(self):
		with self.assertRaisesRegex(MappingError, "account Bank - X has no account number"):
			mapping_of(watched_rows=[{"account": "Bank - X", "account_number": None}])
		with self.assertRaisesRegex(MappingError, "watched account in row 2 has no account"):
			mapping_of(watched_rows=[{"idx": 2}])

	def test_watched_account_cannot_be_mapped(self):
		with self.assertRaisesRegex(MappingError, "account 8400 is watched but also mapped or checked"):
			mapping_of([rule_row("8400")], watched_rows=[{"account_number": "8400"}])


class DefaultsForAccountsTest(TestCase):
	"""The accounts of the Frappe test: a company with a handful of SKR03 accounts."""

	accounts = frozenset({"8400", "1776", "1576", "3123", "1787", "8336"})

	def setUp(self):
		self.rule_rows, self.check_rows, self.watched_rows, self.missing = defaults_for_accounts(
			"SKR03", LATEST_YEAR, self.accounts
		)

	def test_rules_are_those_whose_account_exists_in_the_order_of_the_defaults(self):
		self.assertEqual(
			self.rule_rows,
			[
				rule_row("8400", "81", "credit", tax_rate=None, also_kennzahl=None, also_side=None),
				rule_row("8336", "21", "credit", tax_rate=None, also_kennzahl=None, also_side=None),
				rule_row("3123", "46", "debit", tax_rate=Decimal("19"), also_kennzahl=None, also_side=None),
				rule_row("1576", "66", "debit", tax_rate=None, also_kennzahl=None, also_side=None),
			],
		)

	def test_checks_keep_the_accounts_that_exist_and_drop_the_others(self):
		self.assertEqual(
			self.check_rows,
			[
				check_row("Umsatzsteuer 19 %", "8400", "1776", side="credit"),
				check_row(
					"Umsatzsteuer nach § 13b UStG 19 %", "3123", "1787", side="credit", derived_base="84"
				),
			],
		)

	def test_no_watched_account_exists(self):
		self.assertEqual(self.watched_rows, [])

	def test_missing_lists_the_default_accounts_the_company_lacks_sorted(self):
		expected = sorted(accounts_of(default_mapping("SKR03", LATEST_YEAR)) - self.accounts)
		self.assertEqual(self.missing, expected)
		self.assertIn("8401", self.missing)
		self.assertIn("1771", self.missing)
		self.assertNotIn("8400", self.missing)

	def test_the_rows_give_a_valid_mapping(self):
		mapping = rows_to_mapping("SKR03", self.rule_rows, self.check_rows, self.watched_rows, LATEST_YEAR)
		self.assertEqual(mapping.rule_for("3123"), AccountRule("3123", "46", DEBIT, Decimal("19")))
		self.assertEqual([check.tax_accounts for check in mapping.checks], [("1776",), ("1787",)])


class ReducingTheDefaultsTest(TestCase):
	def reduce(self, accounts, chart="SKR03"):
		return defaults_for_accounts(chart, LATEST_YEAR, frozenset(accounts))

	def test_a_check_keeps_every_base_and_tax_account_that_exists(self):
		_, check_rows, _, _ = self.reduce({"8400", "8410", "2406", "1776"})
		self.assertEqual(
			check_rows, [check_row("Umsatzsteuer 19 %", "8400, 8410, 2406", "1776", side="credit")]
		)

	def test_a_check_without_a_base_account_is_dropped(self):
		rule_rows, check_rows, _, _ = self.reduce({"1776"})
		self.assertEqual((rule_rows, check_rows), ([], []))

	def test_a_check_without_a_tax_account_is_dropped_and_its_rules_stay(self):
		rule_rows, check_rows, _, _ = self.reduce({"8400"})
		self.assertEqual([row["account_number"] for row in rule_rows], ["8400"])
		self.assertEqual(check_rows, [])

	def test_watched_accounts_are_kept_when_they_exist(self):
		_, _, watched_rows, _ = self.reduce({"1725", "1548", "8400"})
		self.assertEqual(
			watched_rows,
			[
				{"account_number": "1548", "level": "blocking"},
				{"account_number": "1725", "level": "blocking"},
			],
		)

	def test_watched_accounts_carry_the_level_of_the_defaults(self):
		_, _, watched_rows, _ = self.reduce({"8603", "1548"})
		self.assertEqual(
			watched_rows,
			[{"account_number": "1548", "level": "blocking"}, {"account_number": "8603", "level": "hint"}],
		)

	def test_the_levels_a_company_set_are_kept(self):
		_, _, watched_rows, _ = defaults_for_accounts(
			"SKR03", LATEST_YEAR, frozenset({"8603", "1548", "1725"}), {"1548": "hint", "8603": "blocking"}
		)
		self.assertEqual(
			watched_rows,
			[
				{"account_number": "1548", "level": "hint"},
				{"account_number": "1725", "level": "blocking"},
				{"account_number": "8603", "level": "blocking"},
			],
		)

	def test_an_empty_level_of_the_company_takes_the_level_of_the_defaults(self):
		_, _, watched_rows, _ = defaults_for_accounts(
			"SKR03", LATEST_YEAR, frozenset({"8603"}), {"8603": None}
		)
		self.assertEqual(watched_rows, [{"account_number": "8603", "level": "hint"}])

	def test_levels_of_accounts_the_defaults_do_not_watch_change_nothing(self):
		kept = defaults_for_accounts(
			"SKR03", LATEST_YEAR, frozenset({"8400", "2654"}), {"8400": "hint", "2654": "hint"}
		)
		self.assertEqual(kept, self.reduce({"8400", "2654"}))
		self.assertEqual(kept.watched_rows, [])

	def test_a_bad_debt_keeps_its_additional_kennzahl(self):
		rule_rows, _, _, _ = self.reduce({"2406"})
		self.assertEqual(
			rule_rows,
			[rule_row("2406", "81", "credit", tax_rate=None, also_kennzahl="50", also_side="debit")],
		)

	def test_members_of_a_range_count_on_their_own(self):
		rule_rows, _, _, missing = self.reduce({"8405"})
		self.assertEqual([row["account_number"] for row in rule_rows], ["8405"])
		self.assertIn("8400", missing)

	def test_accounts_outside_the_defaults_are_ignored(self):
		rule_rows, check_rows, watched_rows, missing = self.reduce({"1200", "9999"})
		self.assertEqual((rule_rows, check_rows, watched_rows), ([], [], []))
		self.assertFalse({"1200", "9999"} & set(missing))

	def test_without_accounts_everything_is_missing(self):
		rule_rows, check_rows, watched_rows, missing = self.reduce(set())
		self.assertEqual((rule_rows, check_rows, watched_rows), ([], [], []))
		self.assertEqual(missing, sorted(accounts_of(default_mapping("SKR03", LATEST_YEAR))))

	def test_unknown_chart_and_year_are_refused(self):
		with self.assertRaisesRegex(KeyError, "no default mapping for chart 'Eigener Kontenrahmen'"):
			defaults_for_accounts("Eigener Kontenrahmen", LATEST_YEAR, frozenset())
		with self.assertRaisesRegex(UnknownYearError, "2019"):
			defaults_for_accounts("SKR03", 2019, frozenset())


class RealDefaultsTest(TestCase):
	def test_every_account_of_the_defaults_gives_back_the_default_mapping(self):
		for chart in DEFAULTS:
			with self.subTest(chart=chart):
				default = default_mapping(chart, LATEST_YEAR)
				rule_rows, check_rows, watched_rows, missing = defaults_for_accounts(
					chart, LATEST_YEAR, frozenset(accounts_of(default))
				)
				self.assertEqual(missing, [])
				self.assertEqual(
					rows_to_mapping(chart, rule_rows, check_rows, watched_rows, LATEST_YEAR), default
				)

	def test_the_rows_survive_the_floats_frappe_stores(self):
		for chart in DEFAULTS:
			with self.subTest(chart=chart):
				default = default_mapping(chart, LATEST_YEAR)
				rule_rows, check_rows, watched_rows, _ = defaults_for_accounts(
					chart, LATEST_YEAR, frozenset(accounts_of(default))
				)
				stored = rows_to_mapping(chart, with_floats(rule_rows), check_rows, watched_rows, LATEST_YEAR)
				self.assertEqual(stored, default)

	def test_any_part_of_the_chart_gives_a_valid_mapping(self):
		for chart in DEFAULTS:
			numbers = sorted(accounts_of(default_mapping(chart, LATEST_YEAR)))
			for start, step in ((0, 2), (1, 2), (0, 3), (2, 5), (3, 7)):
				with self.subTest(chart=chart, start=start, step=step):
					accounts = frozenset(numbers[start::step])
					rule_rows, check_rows, watched_rows, missing = defaults_for_accounts(
						chart, LATEST_YEAR, accounts
					)
					mapping = rows_to_mapping(chart, rule_rows, check_rows, watched_rows, LATEST_YEAR)
					self.assertLessEqual(accounts_of(mapping), accounts)
					self.assertEqual(missing, sorted(set(numbers) - accounts))

	def test_the_verified_month_comes_out_as_with_the_full_defaults(self):
		"""The month of VerifiedMonthTest in the core tests, with the defaults reduced to its accounts."""
		lines = [
			LedgerLine("8400", credit=Decimal("1000.00")),
			LedgerLine("1776", credit=Decimal("190.00")),
			LedgerLine("8336", credit=Decimal("2000.00")),
			LedgerLine("8338", credit=Decimal("500.00")),
			LedgerLine("3123", debit=Decimal("300.00")),
			LedgerLine("1787", credit=Decimal("57.00")),
			LedgerLine("1577", debit=Decimal("57.00")),
			LedgerLine("1576", debit=Decimal("95.00")),
		]
		rule_rows, check_rows, watched_rows, _ = defaults_for_accounts(
			"SKR03", LATEST_YEAR, frozenset(line.account_number for line in lines)
		)
		reduced = calculate(lines, rows_to_mapping("SKR03", rule_rows, check_rows, watched_rows, LATEST_YEAR))
		full = calculate(lines, default_mapping("SKR03", LATEST_YEAR))
		self.assertEqual(dict(reduced.values), dict(full.values))
		self.assertEqual(reduced.kz83, Decimal("95.00"))
		self.assertEqual(reduced.reported("47"), Decimal("57.00"))
		self.assertEqual(
			[check.label for check in reduced.checks],
			["Umsatzsteuer 19 %", "Umsatzsteuer nach § 13b UStG 19 %"],
		)
		self.assertTrue(reduced.ready)


RULE_8400 = {
	"place": "rule",
	"kennzahl": "81",
	"side": "credit",
	"tax_rate": None,
	"also_kennzahl": None,
	"also_side": None,
}


class ItemsOfRowsTest(TestCase):
	"""The rows as items of steuerbote.mappings.diff: one per account with its place, one per Verprobung."""

	def test_an_account_carries_its_rule_and_a_check_its_accounts(self):
		items = items_of_rows(
			[rule_row("8400"), rule_row("3123", "46", "debit", tax_rate=19.0)],
			[check_row(base="8400", tax="1776")],
			[{"account_number": "1548", "level": "hint"}],
		)
		self.assertEqual(
			items,
			{
				(ACCOUNT, "8400"): RULE_8400,
				(ACCOUNT, "3123"): {**RULE_8400, "kennzahl": "46", "side": "debit", "tax_rate": "19"},
				(ACCOUNT, "1548"): {"place": "watched", "level": "hint"},
				(CHECK, "Umsatzsteuer 19 %"): {
					"base_accounts": "8400",
					"tax_accounts": "1776",
					"side": "credit",
				},
			},
		)
		self.assertEqual(
			list(items),
			[(ACCOUNT, "8400"), (ACCOUNT, "3123"), (ACCOUNT, "1548"), (CHECK, "Umsatzsteuer 19 %")],
		)

	def test_a_rate_reads_the_same_however_it_was_stored(self):
		for stored in (19.0, "19", "19.00", Decimal("19"), Decimal("1.9E+1")):
			with self.subTest(stored=stored):
				(fields,) = items_of_rows([rule_row("3123", "46", "debit", tax_rate=stored)], [], []).values()
				self.assertEqual(fields["tax_rate"], "19")
		(fields,) = items_of_rows([rule_row("3123", "46", "debit", tax_rate=5.50)], [], []).values()
		self.assertEqual(fields["tax_rate"], "5.5")
		for empty in (0, 0.0, None, ""):
			with self.subTest(empty=empty):
				(fields,) = items_of_rows([rule_row("8400", tax_rate=empty)], [], []).values()
				self.assertIsNone(fields["tax_rate"])

	def test_the_accounts_of_a_check_read_sorted(self):
		(fields,) = items_of_rows([], [check_row(base="8401,\n8400  8338", tax="1776, 1775")], []).values()
		self.assertEqual(
			(fields["base_accounts"], fields["tax_accounts"]), ("8338, 8400, 8401", "1775, 1776")
		)

	def test_an_additional_kennzahl_is_part_of_the_rule(self):
		(fields,) = items_of_rows([rule_row("2400", also_kennzahl="50", also_side="debit")], [], []).values()
		self.assertEqual((fields["also_kennzahl"], fields["also_side"]), ("50", "debit"))

	def test_an_account_has_one_place(self):
		for rules, watched, refusal in (
			([rule_row("8400"), rule_row("8400", "86")], [], "account 8400 is mapped twice"),
			([], [{"account_number": "1548"}, {"account_number": "1548"}], "account 1548 is watched twice"),
			(
				[rule_row("8400")],
				[{"account_number": "8400"}],
				"account 8400 is watched but also mapped or checked",
			),
		):
			with self.subTest(refusal=refusal), self.assertRaisesRegex(MappingError, refusal):
				items_of_rows(rules, [], watched)

	def test_a_label_names_one_check(self):
		with self.assertRaisesRegex(MappingError, "two tax checks have the label 'Umsatzsteuer 19 %'"):
			items_of_rows([], [check_row(), check_row(base="8401")], [])

	def test_a_row_the_core_cannot_read_is_refused(self):
		with self.assertRaisesRegex(MappingError, "side must be credit or debit"):
			items_of_rows([rule_row("8400", side="left")], [], [])


class DefaultItemsTest(TestCase):
	def test_the_defaults_for_some_accounts_are_what_vorgaben_laden_takes_over(self):
		items = default_items("SKR03", LATEST_YEAR, {"8400", "1776", "1548", "8603"})
		self.assertEqual(
			items,
			{
				(ACCOUNT, "8400"): RULE_8400,
				(ACCOUNT, "1548"): {"place": "watched", "level": "blocking"},
				(ACCOUNT, "8603"): {"place": "watched", "level": "hint"},
				(CHECK, "Umsatzsteuer 19 %"): {
					"base_accounts": "8400",
					"tax_accounts": "1776",
					"side": "credit",
				},
			},
		)

	def test_the_defaults_for_every_account_are_the_items_of_the_default_mapping(self):
		for chart, mapping in DEFAULTS.items():
			with self.subTest(chart=chart):
				self.assertEqual(
					default_items(chart, LATEST_YEAR, accounts_of(mapping)),
					items_of_mapping(default_mapping(chart, LATEST_YEAR)),
				)


class RowsOfItemsTest(TestCase):
	def test_items_give_back_the_rows_they_came_from(self):
		for chart, mapping in DEFAULTS.items():
			with self.subTest(chart=chart):
				items = items_of_mapping(mapping)
				self.assertEqual(items_of_rows(*rows_of_items(items)), items)
				self.assertEqual(items_of_mapping(mapping_of(*rows_of_items(items), chart=chart)), items)

	def test_the_rows_are_those_of_the_doctype_by_account_number(self):
		rows = rows_of_items(
			{
				(ACCOUNT, "3123"): {**RULE_8400, "kennzahl": "46", "side": "debit", "tax_rate": "19"},
				(CHECK, "Umsatzsteuer 19 %"): {
					"base_accounts": "8400",
					"tax_accounts": "1776",
					"side": "credit",
				},
				(ACCOUNT, "1548"): {"place": "watched", "level": "hint"},
				(ACCOUNT, "8400"): RULE_8400,
			}
		)
		self.assertEqual(
			rows.rule_rows,
			[
				rule_row("3123", "46", "debit", tax_rate=Decimal("19"), also_kennzahl=None, also_side=None),
				rule_row("8400", tax_rate=None, also_kennzahl=None, also_side=None),
			],
		)
		self.assertEqual(rows.check_rows, [{**check_row(), "side": "credit"}])
		self.assertEqual(rows.watched_rows, [{"account_number": "1548", "level": "hint"}])


class BodyTest(TestCase):
	"""The plain data of the stored defaults and of the file of a mapping."""

	def setUp(self):
		self.items = items_of_mapping(DEFAULTS["SKR03"])

	def test_the_body_holds_rules_checks_and_watched_accounts_as_texts(self):
		body = body_of_items(
			{
				(ACCOUNT, "3123"): {**RULE_8400, "kennzahl": "46", "side": "debit", "tax_rate": "19"},
				(ACCOUNT, "1548"): {"place": "watched", "level": "hint"},
				(CHECK, "Umsatzsteuer 19 %"): {
					"base_accounts": "8400, 8401",
					"tax_accounts": "1776",
					"side": "credit",
				},
			}
		)
		self.assertEqual(
			body,
			{
				"rules": [
					{
						"account_number": "3123",
						"kennzahl": "46",
						"side": "debit",
						"tax_rate": "19",
						"also_kennzahl": None,
						"also_side": None,
					}
				],
				"checks": [
					{
						"label": "Umsatzsteuer 19 %",
						"base_accounts": ["8400", "8401"],
						"tax_accounts": ["1776"],
						"side": "credit",
					}
				],
				"watched": [{"account_number": "1548", "level": "hint"}],
			},
		)

	def test_the_body_gives_back_its_items(self):
		self.assertEqual(items_of_body(body_of_items(self.items)), self.items)
		self.assertEqual(items_of_body(json.loads(json.dumps(body_of_items(self.items)))), self.items)

	def test_dump_and_load_give_back_the_items(self):
		text = dump_items(self.items)
		self.assertEqual(load_items(text), self.items)
		self.assertEqual(text, dump_items(load_items(text)))

	def test_the_dump_is_canonical_json(self):
		self.assertEqual(
			dump_items({(ACCOUNT, "1548"): {"place": "watched", "level": "hint"}}),
			'{"checks":[],"rules":[],"watched":[{"account_number":"1548","level":"hint"}]}',
		)

	def test_load_refuses_a_text_that_is_no_json(self):
		with self.assertRaisesRegex(MappingError, "no JSON"):
			load_items("{rules: []")

	def test_a_body_of_another_shape_is_refused(self):
		good = body_of_items(self.items)
		rule = good["rules"][0]
		check = good["checks"][0]
		for body, refusal in (
			([], "a mapping holds rules, checks, watched"),
			({"rules": [], "checks": []}, "a mapping holds"),
			({**good, "levels": []}, "a mapping holds"),
			({**good, "rules": {}}, "rules must be a list"),
			({**good, "rules": ["8400"]}, "each of the rules holds account_number, kennzahl"),
			({**good, "rules": [{**rule, "note": "x"}]}, "each of the rules holds"),
			(
				{**good, "watched": [{"account_number": "1548"}]},
				"each of the watched holds account_number, level",
			),
			({**good, "rules": [{**rule, "kennzahl": 81}]}, "rules: kennzahl cannot be 81"),
			({**good, "rules": [{**rule, "tax_rate": 19.0}]}, "rules: tax_rate cannot be 19.0"),
			(
				{**good, "checks": [{**check, "base_accounts": "8400"}]},
				"checks: base_accounts cannot be '8400'",
			),
			(
				{**good, "checks": [{**check, "tax_accounts": [1776]}]},
				r"checks: tax_accounts cannot be \[1776\]",
			),
			({**good, "checks": [{**check, "label": ["x"]}]}, r"checks: label cannot be \['x'\]"),
		):
			with self.subTest(refusal=refusal), self.assertRaisesRegex(MappingError, refusal):
				items_of_body(body)


class FileBodyTest(TestCase):
	"""The body of the file of a mapping: its rows and the rows of the defaults it took over."""

	def setUp(self):
		self.items = items_of_mapping(DEFAULTS["SKR04"])
		self.defaults = default_items("SKR04", LATEST_YEAR, {"4400", "3806"})

	def test_the_body_holds_the_mapping_and_its_defaults(self):
		self.assertEqual(
			file_body(self.items, self.defaults),
			{"mapping": body_of_items(self.items), "defaults": body_of_items(self.defaults)},
		)
		self.assertEqual(file_body(self.items, None)["defaults"], None)

	def test_the_body_gives_back_the_mapping_and_its_defaults(self):
		for defaults in (self.defaults, None):
			with self.subTest(defaults=bool(defaults)):
				body = json.loads(json.dumps(file_body(self.items, defaults)))
				self.assertEqual(items_of_file_body(body), (self.items, defaults))

	def test_a_body_of_another_shape_is_refused(self):
		good = file_body(self.items, None)
		for body in ([], {"mapping": good["mapping"]}, {**good, "more": 1}):
			with (
				self.subTest(body=type(body).__name__),
				self.assertRaisesRegex(MappingError, "the body of the file holds mapping and defaults"),
			):
				items_of_file_body(body)
		with self.assertRaisesRegex(MappingError, "a mapping holds"):
			items_of_file_body({**good, "defaults": {"rules": []}})

	def test_the_format_names_the_vat_return_mapping(self):
		self.assertEqual(FILE_FORMAT, "steuerbote/vat-return-mapping")


def annual_row(
	account_number: str | None, annual_field: Any = "E3100801", side: Any = "debit", **fields: Any
) -> dict:
	return {"account_number": account_number, "annual_field": annual_field, "side": side, **fields}


class ChoicesOfRowsTest(TestCase):
	"""What a rule row says for the annual return: its annual field and the paragraph of its line."""

	def test_a_rule_row_with_an_annual_field_or_a_paragraph_is_a_choice(self):
		rows = [
			rule_row("8910", annual_field="E3003505"),
			rule_row("8100", "48", paragraph="4 Nummer 14"),
			rule_row("8400"),
		]
		self.assertEqual(
			choices_of_rows(rows), (Choice("8910", "E3003505"), Choice("8100", paragraph="4 Nummer 14"))
		)

	def test_blank_fields_make_no_choice_and_texts_are_read_on_one_line(self):
		rows = [
			rule_row("8400", annual_field=" ", paragraph=""),
			rule_row("8401", annual_field=None, paragraph=None),
			rule_row("8100", "48", annual_field=" E3104502 ", paragraph=" 4 Nummer\n14 "),
		]
		self.assertEqual(choices_of_rows(rows), (Choice("8100", "E3104502", "4 Nummer 14"),))

	def test_a_rule_row_without_its_account_is_refused(self):
		with self.assertRaisesRegex(MappingError, "rule in row 3 has no account"):
			choices_of_rows([rule_row(None, annual_field="E3003505", idx=3)])


class AnnualRulesOfRowsTest(TestCase):
	"""The rows of the accounts only the annual return reads."""

	def test_rows_become_annual_rules_with_their_side_and_paragraph(self):
		rows = [
			annual_row("3552"),
			annual_row("3075", "E3102804", "debit", paragraph=" "),
			annual_row("8106", "E3103902", "credit", paragraph="4 Nummer 2,\n§ 8"),
		]
		self.assertEqual(
			annual_rules_of_rows(rows),
			(
				AnnualRule("3552", "E3100801", Side.DEBIT),
				AnnualRule("3075", "E3102804", Side.DEBIT),
				AnnualRule("8106", "E3103902", Side.CREDIT, "4 Nummer 2, § 8"),
			),
		)

	def test_a_row_needs_its_account_its_field_and_a_side(self):
		for row, refusal in (
			(annual_row(None, idx=2), "row for the annual return only in row 2 has no account"),
			(annual_row("3552", annual_field=" "), "account 3552: no annual field"),
			(annual_row("3552", side="left"), "account 3552: side must be credit or debit, not 'left'"),
			(annual_row("3552", side=None), "account 3552: side must be credit or debit, not None"),
		):
			with self.subTest(refusal=refusal), self.assertRaisesRegex(MappingError, refusal):
				annual_rules_of_rows([row])


class AnnualSplitTest(TestCase):
	"""The split of the rows for the annual return, which the annual return of U3 calls."""

	rules = (rule_row("8400"), rule_row("8910"), rule_row("1558", "64", "debit"), rule_row("8130", "42"))
	checks = (check_row(base="8400, 8910"),)

	def test_the_rows_split_with_the_roles_of_the_chart_and_the_rows_for_the_annual_return(self):
		result = annual_split("SKR03", self.rules, self.checks, [], [annual_row("3552")], ANNUAL_YEAR)
		self.assertEqual(
			{number: (assignment.field, assignment.how) for number, assignment in result.assignments.items()},
			{
				"8400": ("E3003303", How.DEFAULT),
				"8910": ("E3003405", How.ROLE),
				"1558": ("E3008701", How.ROLE),
				"8130": ("E3101801", How.DEFAULT),
				"3552": ("E3100801", How.ANNUAL),
			},
		)
		self.assertEqual(result.mapping.year, ANNUAL_YEAR)

	def test_the_annual_field_of_a_rule_comes_before_its_role(self):
		rules = [rule_row("8400"), rule_row("8910", annual_field="E3003505", paragraph=None)]
		result = annual_split("SKR03", rules, [], [], [], ANNUAL_YEAR)
		self.assertEqual((result.field_of("8910"), result.assignment("8910").how), ("E3003505", How.RULE))

	def test_a_chart_of_its_own_has_no_roles(self):
		with self.assertRaisesRegex(SplitError, "Account 1558 feeds Kennzahl 64"):
			annual_split("Eigener Kontenrahmen", self.rules, self.checks, [], [], ANNUAL_YEAR)
		rules = [rule_row("8910"), rule_row("1558", "64", "debit", annual_field="E3008701")]
		result = annual_split("Eigener Kontenrahmen", rules, [], [], [], ANNUAL_YEAR)
		self.assertEqual((result.field_of("8910"), result.field_of("1558")), ("E3003303", "E3008701"))

	def test_the_core_refuses_what_does_not_fit(self):
		with self.assertRaisesRegex(MappingError, "unknown Kennzahl 99"):
			annual_split("SKR03", [rule_row("8400", "99")], [], [], [], ANNUAL_YEAR)
		with self.assertRaisesRegex(
			SplitError, "Account 8400 feeds Kennzahl 81 of the Voranmeldung, so its line"
		):
			annual_split("SKR03", [rule_row("8400")], [], [], [annual_row("8400")], ANNUAL_YEAR)
		with self.assertRaisesRegex(UnknownYearError, "2027"):
			annual_split("SKR03", [rule_row("8400")], [], [], [], ANNUAL_YEAR + 1)


class AnnualItemsTest(TestCase):
	"""The annual field of a mapped account and an account only the annual return reads are items of their own."""

	def test_an_annual_field_and_a_row_for_the_annual_return_are_items_after_the_others(self):
		items = items_of_rows(
			[rule_row("8910", annual_field="E3003505"), rule_row("8100", "48", paragraph=" 4 Nummer 14 ")],
			[],
			[{"account_number": "3075", "level": "blocking"}],
			[annual_row("3075", "E3102804"), annual_row("3552", paragraph="x")],
		)
		self.assertEqual(list(items)[:3], [(ACCOUNT, "8910"), (ACCOUNT, "8100"), (ACCOUNT, "3075")])
		self.assertEqual(
			list(items.items())[3:],
			[
				((ANNUAL_FIELD, "8910"), {"annual_field": "E3003505", "paragraph": None}),
				((ANNUAL_FIELD, "8100"), {"annual_field": None, "paragraph": "4 Nummer 14"}),
				((ANNUAL_RULE, "3075"), {"annual_field": "E3102804", "side": "debit", "paragraph": None}),
				((ANNUAL_RULE, "3552"), {"annual_field": "E3100801", "side": "debit", "paragraph": "x"}),
			],
		)

	def test_rows_without_anything_for_the_annual_return_give_the_items_they_gave(self):
		items = items_of_rows([rule_row("8400", annual_field="", paragraph=None)], [check_row()], [])
		self.assertEqual(list(items), [(ACCOUNT, "8400"), (CHECK, "Umsatzsteuer 19 %")])

	def test_an_account_has_one_row_for_the_annual_return_only(self):
		with self.assertRaisesRegex(MappingError, "account 3552 has two rows for the annual return only"):
			items_of_rows([], [], [], [annual_row("3552"), annual_row("3552", "E3101701")])

	def test_the_defaults_give_the_rows_for_the_annual_return_of_the_accounts_a_company_has(self):
		numbers = {"8400", "3552", "3075", "5552"}
		self.assertEqual(
			annual_rows_for_accounts("SKR03", ANNUAL_YEAR, numbers),
			[annual_row("3552", paragraph=None), annual_row("3075", "E3102804", paragraph=None)],
		)
		self.assertEqual(
			annual_default_items("SKR03", ANNUAL_YEAR, numbers),
			{
				(ANNUAL_RULE, "3552"): {"annual_field": "E3100801", "side": "debit", "paragraph": None},
				(ANNUAL_RULE, "3075"): {"annual_field": "E3102804", "side": "debit", "paragraph": None},
			},
		)
		self.assertEqual(
			annual_rows_for_accounts("SKR04", ANNUAL_YEAR, numbers), [annual_row("5552", paragraph=None)]
		)

	def test_a_chart_of_its_own_has_no_rows_for_the_annual_return_in_its_defaults(self):
		self.assertEqual(annual_rows_for_accounts("Eigener Kontenrahmen", ANNUAL_YEAR, {"3552"}), [])
		self.assertEqual(annual_default_items("Eigener Kontenrahmen", ANNUAL_YEAR, {"3552"}), {})


class AnnualRowsOfItemsTest(TestCase):
	def test_an_annual_field_goes_back_into_the_row_of_its_rule(self):
		items = {
			(ANNUAL_FIELD, "8910"): {"annual_field": "E3003505", "paragraph": None},
			(ACCOUNT, "8910"): RULE_8400,
			(ACCOUNT, "8400"): RULE_8400,
			(ANNUAL_RULE, "3552"): {"annual_field": "E3100801", "side": "debit", "paragraph": None},
		}
		rows = rows_of_items(items)
		self.assertEqual(
			rows.rule_rows,
			[
				rule_row(
					"8910",
					tax_rate=None,
					also_kennzahl=None,
					also_side=None,
					annual_field="E3003505",
					paragraph=None,
				),
				rule_row("8400", tax_rate=None, also_kennzahl=None, also_side=None),
			],
		)
		self.assertEqual(annual_rows_of_items(items), [annual_row("3552", paragraph=None)])

	def test_an_annual_field_without_the_rule_of_its_account_is_refused(self):
		items = {(ANNUAL_FIELD, "8910"): {"annual_field": "E3003505", "paragraph": None}}
		with self.assertRaisesRegex(MappingError, "account 8910 has an annual field but no rule"):
			rows_of_items(items)
		watched = {**items, (ACCOUNT, "8910"): {"place": "watched", "level": "hint"}}
		with self.assertRaisesRegex(MappingError, "account 8910 has an annual field but no rule"):
			rows_of_items(watched)

	def test_the_rows_give_back_their_items(self):
		rules = [rule_row("8910", annual_field="E3003505", paragraph="x"), rule_row("8400")]
		annual = [annual_row("3552", paragraph=None)]
		items = items_of_rows(rules, [], [], annual)
		rows = rows_of_items(items)
		self.assertEqual(items_of_rows(*rows, annual_rows_of_items(items)), items)


class AnnualBodyTest(TestCase):
	"""The annual fields and the rows for the annual return in the stored defaults and the file of a mapping."""

	def setUp(self):
		self.items = items_of_rows(
			[rule_row("8910", annual_field="E3003505"), rule_row("8400")],
			[check_row(base="8400, 8910")],
			[],
			[annual_row("3552")],
		)

	def test_the_body_holds_them_in_parts_of_their_own(self):
		body = body_of_items(self.items)
		self.assertEqual(
			body["annual_fields"], [{"account_number": "8910", "annual_field": "E3003505", "paragraph": None}]
		)
		self.assertEqual(
			body["annual_rules"],
			[{"account_number": "3552", "annual_field": "E3100801", "side": "debit", "paragraph": None}],
		)
		self.assertEqual([rule["account_number"] for rule in body["rules"]], ["8910", "8400"])
		self.assertNotIn("annual_field", body["rules"][0])

	def test_a_body_without_them_has_the_parts_it_had(self):
		body = body_of_items(items_of_rows([rule_row("8400")], [], []))
		self.assertEqual(set(body), {"rules", "checks", "watched"})

	def test_the_body_and_the_dump_give_back_the_items(self):
		self.assertEqual(items_of_body(json.loads(json.dumps(body_of_items(self.items)))), self.items)
		self.assertEqual(load_items(dump_items(self.items)), self.items)

	def test_a_body_with_parts_of_another_shape_is_refused(self):
		good = body_of_items(self.items)
		choice, annual = good["annual_fields"][0], good["annual_rules"][0]
		for body, refusal in (
			({**good, "annual_fields": {}}, "annual_fields must be a list"),
			({**good, "annual_fields": [{**choice, "side": "debit"}]}, "each of the annual_fields holds"),
			({**good, "annual_rules": [{"account_number": "3552"}]}, "each of the annual_rules holds"),
			({**good, "annual_rules": [{**annual, "side": 1}]}, "annual_rules: side cannot be 1"),
			(
				{**good, "annual_fields": [{**choice, "account_number": "9999"}]},
				"account 9999 has an annual field but no rule",
			),
			({**good, "annual": []}, "a mapping holds rules, checks, watched"),
		):
			with self.subTest(refusal=refusal), self.assertRaisesRegex(MappingError, refusal):
				items_of_body(body)


class CheckAnnualRowsTest(TestCase):
	"""What saving the mapping checks for the annual return: the annual fields and the rows for the annual return only
	that the company gave, against the latest form, while a line the annual return asks for is left to it."""

	def check(self, rules, annual=(), checks=(), watched=(), chart="SKR03") -> None:
		check_annual_rows(chart, rules, checks, watched, annual, ANNUAL_YEAR)

	def test_annual_fields_and_rows_that_fit_pass(self):
		self.check(
			[rule_row("8910", annual_field="E3003505"), rule_row("8100", "48", paragraph="4 Nummer 14")],
			[annual_row("3552"), annual_row("3075", "E3102804")],
			watched=[{"account_number": "3075"}],
		)

	def test_an_annual_field_that_is_not_a_line_of_its_kennzahl_is_refused(self):
		for rules, refusal in (
			(
				[rule_row("8910", annual_field="E3003703")],
				"Account 8910 feeds Kennzahl 81 of the Voranmeldung, which",
			),
			([rule_row("8910", annual_field="E9999999")], "Form USt 2 A 2026 has no field E9999999"),
			([rule_row("8400", paragraph="4 Nummer 14")], "names no paragraph, so account 8400 gives none"),
		):
			with self.subTest(refusal=refusal), self.assertRaisesRegex(SplitError, refusal):
				self.check(rules)

	def test_a_row_for_the_annual_return_only_needs_an_account_no_kennzahl_takes_and_a_field_it_can_feed(
		self,
	):
		for annual, refusal in (
			(annual_row("8400"), "Account 8400 feeds Kennzahl 81 of the Voranmeldung, so its line"),
			(annual_row("1776"), "Account 1776 is a tax account of the Verprobung"),
			(annual_row("3552", "E3011101"), "Account 3552 cannot feed field E3011101 in line 124"),
		):
			with self.subTest(refusal=refusal), self.assertRaisesRegex(SplitError, refusal):
				self.check([rule_row("8400")], [annual], checks=[check_row()])
		with self.assertRaisesRegex(MappingError, "account 3552: no annual field"):
			self.check([rule_row("8400")], [annual_row("3552", "")])

	def test_an_account_of_kz_64_without_its_line_is_left_to_the_annual_return(self):
		"""The Voranmeldung needs no line for it; the annual return asks for one (split.NO_DEFAULT)."""
		self.check([rule_row("1550", "64", "debit")], chart="Eigener Kontenrahmen")
		self.check([rule_row("8400", "64", "debit"), rule_row("8910", "64", "debit")])
		with self.assertRaisesRegex(
			SplitError, "Account 1550 feeds Kennzahl 64 of the Voranmeldung, which field"
		):
			self.check(
				[rule_row("1550", "64", "debit", annual_field="E3003303")], chart="Eigener Kontenrahmen"
			)

	def test_an_account_of_a_kennzahl_without_a_line_is_left_out_unless_it_names_one(self):
		"""Kz 39 has no line: the annual return takes the Sondervorauszahlung into its Vorauszahlungssoll."""
		self.check([rule_row("1781", "39", "debit"), rule_row("8400")])
		with self.assertRaisesRegex(
			SplitError, "Account 1781 feeds Kennzahl 39 of the Voranmeldung, which field"
		):
			self.check([rule_row("1781", "39", "debit", annual_field="E3003303")])
		with self.assertRaisesRegex(
			SplitError, "Account 1781 feeds Kennzahl 39 of the Voranmeldung, so its line"
		):
			self.check([rule_row("1781", "39", "debit")], [annual_row("1781")])

	def test_rules_the_form_of_the_annual_return_does_not_take_leave_the_check_to_the_voranmeldung(self):
		"""Saving checks the rules against the form of the Voranmeldung first, which may know a Kennzahl the latest
		form of the annual return does not."""
		self.check([rule_row("8400", "99", annual_field="E3003303")])
