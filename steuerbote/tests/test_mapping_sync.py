"""Tests for steuerbote.mapping_sync, plain unittest without Frappe so that every test runner collects them."""

import json
from decimal import Decimal
from typing import Any
from unittest import TestCase

from steuerbote.mapping_sync import (
	ACCOUNT,
	CHECK,
	FILE_FORMAT,
	body_of_items,
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
				check_row("Umsatzsteuer nach § 13b UStG 19 %", "3123", "1787", side="credit"),
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
