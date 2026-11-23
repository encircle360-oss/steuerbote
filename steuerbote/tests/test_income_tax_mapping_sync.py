"""Tests for steuerbote.income_tax_mapping_sync, plain unittest without Frappe so that every test runner collects
them."""

import json
from unittest import TestCase

from steuerbote.income_tax_mapping_sync import (
	ACCOUNT,
	FILE_FORMAT,
	MissingAccount,
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
from steuerbote.kst.categories import AccountRule, Category, Mapping, TradingClass
from steuerbote.kst.defaults import CHARTS, default_accounts, default_mapping
from steuerbote.ustva.mapping import MappingError, WatchedAccount, WatchLevel

# Invented rows of a company with SKR03: the Körperschaftsteuer, a trading account with its class, a trading account
# without one, and a watched account at each level.
RULE_ROWS = [
	{
		"account": "2200 - Körperschaftsteuer - M",
		"account_number": "2200",
		"category": "kst",
		"trading_class": None,
	},
	{"account_number": "2654", "category": "trading_unclassified", "trading_class": "derivatives"},
	{"account_number": "2166", "category": "trading_unclassified", "trading_class": ""},
]
WATCHED_ROWS = [
	{"account_number": "2250", "level": "blocking"},
	{"account_number": "4126", "level": "hint"},
]
# Accounts of an invented company with SKR03: the taxes, a watched account, a bank, which the defaults leave out.
COMPANY_ACCOUNTS = {"2200", "2208", "4320", "2250", "4126", "1200"}


class RowsToMappingTest(TestCase):
	def test_builds_rules_and_watched_accounts_from_rows(self):
		mapping = rows_to_mapping("SKR03", RULE_ROWS, WATCHED_ROWS)
		self.assertEqual(
			mapping,
			Mapping(
				"SKR03",
				(
					AccountRule("2200", Category.KST),
					AccountRule("2654", Category.TRADING_UNCLASSIFIED, TradingClass.DERIVATIVES),
					AccountRule("2166", Category.TRADING_UNCLASSIFIED),
				),
				(WatchedAccount("2250", WatchLevel.BLOCKING), WatchedAccount("4126", WatchLevel.HINT)),
			),
		)

	def test_a_rule_needs_a_category_of_the_core(self):
		for row, message in (
			({"account_number": "2200"}, "account 2200: no category"),
			({"account_number": "2200", "category": ""}, "account 2200: no category"),
			(
				{"account_number": "2200", "category": "Körperschaftsteuer"},
				"account 2200: category must be one of kst, solz, .*, not 'Körperschaftsteuer'",
			),
		):
			with self.subTest(row=row), self.assertRaisesRegex(MappingError, message):
				rows_to_mapping("SKR03", [row], [])

	def test_a_trading_class_is_one_of_the_core_and_only_for_a_trading_account(self):
		with self.assertRaisesRegex(
			MappingError,
			"account 2654: trading class must be one of shares, derivatives, funds, taxable, not 'cfd'",
		):
			rows_to_mapping(
				"SKR03",
				[{"account_number": "2654", "category": "trading_unclassified", "trading_class": "cfd"}],
				[],
			)
		with self.assertRaisesRegex(MappingError, "a trading class needs the category trading_unclassified"):
			rows_to_mapping(
				"SKR03", [{"account_number": "2200", "category": "kst", "trading_class": "shares"}], []
			)

	def test_a_row_without_account_number_is_refused_by_its_account_or_its_row(self):
		for row, message in (
			({"account": "Steuern - M", "category": "kst"}, "account Steuern - M has no account number"),
			({"idx": 3, "category": "kst"}, "rule in row 3 has no account"),
			({"category": "kst"}, "rule has no account"),
		):
			with self.subTest(row=row), self.assertRaisesRegex(MappingError, message):
				rows_to_mapping("SKR03", [row], [])
		with self.assertRaisesRegex(MappingError, "watched account in row 2 has no account"):
			rows_to_mapping("SKR03", [], [{"idx": 2, "level": "hint"}])

	def test_a_watched_account_without_level_blocks_and_one_with_another_is_refused(self):
		mapping = rows_to_mapping("SKR03", [], [{"account_number": "2250", "level": ""}])
		self.assertEqual(mapping.watched, (WatchedAccount("2250", WatchLevel.BLOCKING),))
		with self.assertRaisesRegex(MappingError, "account 2250: level must be blocking or hint, not 'warn'"):
			rows_to_mapping("SKR03", [], [{"account_number": "2250", "level": "warn"}])

	def test_the_validation_of_the_core_applies(self):
		with self.assertRaisesRegex(MappingError, "account 2200 has more than one rule"):
			rows_to_mapping("SKR03", [RULE_ROWS[0], RULE_ROWS[0]], [])
		with self.assertRaisesRegex(MappingError, "account 2200 is mapped and watched"):
			rows_to_mapping("SKR03", [RULE_ROWS[0]], [{"account_number": "2200", "level": "hint"}])


class DefaultsForAccountsTest(TestCase):
	def test_keeps_the_defaults_whose_accounts_exist_in_the_order_of_the_defaults(self):
		defaults = defaults_for_accounts("SKR03", COMPANY_ACCOUNTS)
		self.assertEqual(
			defaults.rule_rows,
			[
				{"account_number": "2200", "category": "kst", "trading_class": None},
				{"account_number": "2208", "category": "solz", "trading_class": None},
				{"account_number": "4320", "category": "gewst", "trading_class": None},
			],
		)
		self.assertEqual(
			defaults.watched_rows,
			[{"account_number": "2250", "level": "blocking"}, {"account_number": "4126", "level": "hint"}],
		)

	def test_lists_the_accounts_of_the_defaults_the_company_lacks_with_their_labels(self):
		missing = defaults_for_accounts("SKR03", COMPANY_ACCOUNTS).missing
		self.assertEqual(len(missing), len(default_accounts("SKR03")) - 5)
		self.assertEqual(
			[account.account_number for account in missing], sorted(a.account_number for a in missing)
		)
		self.assertEqual(missing[0], MissingAccount("2004", "Verluste durch Verschmelzung und Umwandlung"))
		self.assertIn(MissingAccount("2203", "Körperschaftsteuer für Vorjahre"), missing)
		self.assertNotIn("1200", {account.account_number for account in missing})

	def test_a_watched_account_keeps_the_level_the_company_gave_it(self):
		defaults = defaults_for_accounts(
			"SKR03", COMPANY_ACCOUNTS, {"2250": "hint", "4126": "", "2200": "hint"}
		)
		self.assertEqual(
			defaults.watched_rows,
			[{"account_number": "2250", "level": "hint"}, {"account_number": "4126", "level": "hint"}],
		)
		self.assertEqual(
			defaults.rule_rows[0], {"account_number": "2200", "category": "kst", "trading_class": None}
		)

	def test_every_account_of_the_defaults_gives_back_the_default_mapping(self):
		for chart in CHARTS:
			numbers = {account.number for account in default_accounts(chart)}
			defaults = defaults_for_accounts(chart, numbers)
			with self.subTest(chart=chart):
				self.assertEqual(defaults.missing, [])
				self.assertEqual(
					rows_to_mapping(chart, defaults.rule_rows, defaults.watched_rows), default_mapping(chart)
				)

	def test_a_chart_without_defaults_is_refused(self):
		with self.assertRaisesRegex(KeyError, "no default Income Tax Mapping"):
			defaults_for_accounts("Eigener Kontenrahmen", COMPANY_ACCOUNTS)


class ItemsTest(TestCase):
	def test_an_account_carries_its_rule_or_its_level(self):
		self.assertEqual(
			items_of_rows(RULE_ROWS, WATCHED_ROWS),
			{
				(ACCOUNT, "2200"): {"place": "rule", "category": "kst", "trading_class": None},
				(ACCOUNT, "2654"): {
					"place": "rule",
					"category": "trading_unclassified",
					"trading_class": "derivatives",
				},
				(ACCOUNT, "2166"): {
					"place": "rule",
					"category": "trading_unclassified",
					"trading_class": None,
				},
				(ACCOUNT, "2250"): {"place": "watched", "level": "blocking"},
				(ACCOUNT, "4126"): {"place": "watched", "level": "hint"},
			},
		)

	def test_an_account_has_one_place(self):
		for rules, watched, message in (
			([RULE_ROWS[0], RULE_ROWS[0]], [], "account 2200 has more than one rule"),
			([], [WATCHED_ROWS[0], WATCHED_ROWS[0]], "account 2250 is watched twice"),
			(
				[RULE_ROWS[0]],
				[{"account_number": "2200", "level": "hint"}],
				"account 2200 is mapped and watched",
			),
		):
			with self.subTest(message=message), self.assertRaisesRegex(MappingError, message):
				items_of_rows(rules, watched)

	def test_a_row_the_core_cannot_read_is_refused(self):
		with self.assertRaisesRegex(MappingError, "account 2200: no category"):
			items_of_rows([{"account_number": "2200"}], [])

	def test_the_items_of_a_mapping_are_those_of_its_rows(self):
		self.assertEqual(
			items_of_mapping(rows_to_mapping("SKR03", RULE_ROWS, WATCHED_ROWS)),
			items_of_rows(RULE_ROWS, WATCHED_ROWS),
		)

	def test_the_defaults_for_some_accounts_are_what_vorgaben_laden_takes_over(self):
		items = default_items("SKR03", COMPANY_ACCOUNTS)
		self.assertEqual(
			list(items),
			[(ACCOUNT, number) for number in ("2200", "2208", "4320", "2250", "4126")],
		)
		self.assertEqual(items[(ACCOUNT, "4126")], {"place": "watched", "level": "hint"})

	def test_the_defaults_for_every_account_are_the_items_of_the_default_mapping(self):
		for chart in CHARTS:
			with self.subTest(chart=chart):
				numbers = {account.number for account in default_accounts(chart)}
				self.assertEqual(default_items(chart, numbers), items_of_mapping(default_mapping(chart)))

	def test_items_give_back_the_rows_they_came_from(self):
		rows = rows_of_items(items_of_rows(RULE_ROWS, WATCHED_ROWS))
		self.assertEqual(
			rows.rule_rows,
			[
				{"account_number": "2200", "category": "kst", "trading_class": None},
				{
					"account_number": "2654",
					"category": "trading_unclassified",
					"trading_class": "derivatives",
				},
				{"account_number": "2166", "category": "trading_unclassified", "trading_class": None},
			],
		)
		self.assertEqual(rows.watched_rows, WATCHED_ROWS)
		self.assertEqual(items_of_rows(*rows), items_of_rows(RULE_ROWS, WATCHED_ROWS))


class BodyTest(TestCase):
	def setUp(self):
		self.items = items_of_rows(RULE_ROWS, WATCHED_ROWS)

	def test_the_body_holds_rules_and_watched_accounts_as_texts(self):
		self.assertEqual(
			body_of_items(self.items),
			{
				"rules": [
					{"account_number": "2200", "category": "kst", "trading_class": None},
					{
						"account_number": "2654",
						"category": "trading_unclassified",
						"trading_class": "derivatives",
					},
					{"account_number": "2166", "category": "trading_unclassified", "trading_class": None},
				],
				"watched": WATCHED_ROWS,
			},
		)

	def test_the_body_gives_back_its_items_and_the_dump_is_canonical_json(self):
		self.assertEqual(items_of_body(body_of_items(self.items)), self.items)
		self.assertEqual(load_items(dump_items(self.items)), self.items)
		dumped = dump_items(self.items)
		self.assertEqual(
			dumped, json.dumps(json.loads(dumped), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
		)
		self.assertNotIn(" ", dumped.replace("2200 - ", ""))

	def test_a_body_of_another_shape_is_refused(self):
		for body, message in (
			([], "a mapping holds rules, watched"),
			({"rules": []}, "a mapping holds rules, watched"),
			({"rules": {}, "watched": []}, "rules must be a list"),
			(
				{"rules": [{"account_number": "2200"}], "watched": []},
				"each of the rules holds account_number",
			),
			(
				{
					"rules": [{"account_number": 2200, "category": "kst", "trading_class": None}],
					"watched": [],
				},
				"rules: account_number cannot be 2200",
			),
			(
				{"rules": [], "watched": [{"account_number": "2250", "level": "warn"}]},
				"level must be blocking or hint",
			),
		):
			with self.subTest(body=body), self.assertRaisesRegex(MappingError, message):
				items_of_body(body)

	def test_stored_defaults_that_are_no_json_are_refused(self):
		with self.assertRaisesRegex(MappingError, "the stored defaults are no JSON"):
			load_items("{")

	def test_the_file_holds_the_mapping_and_the_defaults_it_took_over(self):
		defaults = default_items("SKR03", COMPANY_ACCOUNTS)
		body = file_body(self.items, defaults)
		self.assertEqual(set(body), {"mapping", "defaults"})
		self.assertEqual(items_of_file_body(body), (self.items, defaults))
		self.assertEqual(items_of_file_body(file_body(self.items, None)), (self.items, None))
		with self.assertRaisesRegex(MappingError, "the body of the file holds mapping and defaults"):
			items_of_file_body({"mapping": body_of_items(self.items)})
		self.assertEqual(FILE_FORMAT, "steuerbote/income-tax-mapping")
