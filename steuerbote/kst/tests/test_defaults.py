"""The defaults of the Income Tax Mapping for SKR03 and SKR04: every account the DATEV charts valid for 2026 hand to
the Körperschaftsteuer or the Gewerbesteuer has one place, and each category feeds a line of the computation."""

import hashlib
import re
from collections import Counter
from unittest import TestCase

from steuerbote.gewst import chain as gewst_chain
from steuerbote.kst import chain as kst_chain
from steuerbote.kst.categories import CATEGORIES, Category
from steuerbote.kst.defaults import (
	ACCOUNTS,
	CHARTS,
	DATEV_EDITION,
	NON_DEDUCTIBLE_DONATIONS,
	OUTSIDE,
	REASONS,
	REVISION,
	DefaultAccount,
	Outside,
	Reason,
	default_accounts,
	default_mapping,
	defaults_version,
)
from steuerbote.mappings.transfer import canonical_json
from steuerbote.ustva.mapping import WatchLevel

# The accounts the column Programmverbindung of the DATEV charts „Gültig für 2026“ marks K or G (SKR 03, Art.-Nr.
# 11174; SKR 04, Art.-Nr. 11175).
FLAGGED = {
	"SKR03": frozenset(
		[
			"0800",
			"0809",
			"0810",
			"0811",
			"0812",
			"0813",
			"0819",
			"0840",
			"0841",
			"0842",
			"0843",
			"0844",
			"0845",
			"0846",
			"0848",
			"0851",
			"0852",
			"0855",
			"0856",
			"0860",
			"0868",
			"2004",
			"2100",
			"2102",
			"2104",
			"2105",
			"2107",
			"2108",
			"2109",
			"2110",
			"2111",
			"2113",
			"2114",
			"2115",
			"2116",
			"2117",
			"2118",
			"2119",
			"2120",
			"2123",
			"2124",
			"2125",
			"2126",
			"2127",
			"2128",
			"2129",
			"2130",
			"2148",
			"2200",
			"2203",
			"2204",
			"2208",
			"2209",
			"2210",
			"2213",
			"2216",
			"2218",
			"2219",
			"2250",
			"2255",
			"2260",
			"2265",
			"2281",
			"2283",
			"2308",
			"2313",
			"2318",
			"2324",
			"2326",
			"2328",
			"2375",
			"2380",
			"2381",
			"2382",
			"2383",
			"2384",
			"2385",
			"2387",
			"2389",
			"2390",
			"2440",
			"2441",
			"2490",
			"2493",
			"2494",
			"2504",
			"2603",
			"2614",
			"2615",
			"2616",
			"2618",
			"2625",
			"2626",
			"2653",
			"2655",
			"2656",
			"2658",
			"2682",
			"2713",
			"2714",
			"2716",
			"2724",
			"2726",
			"2744",
			"2745",
			"2746",
			"2747",
			"2790",
			"2794",
			"3170",
			"3175",
			"3180",
			"3185",
			"4126",
			"4128",
			"4129",
			"4137",
			"4148",
			"4154",
			"4158",
			"4168",
			"4197",
			"4210",
			"4211",
			"4215",
			"4219",
			"4220",
			"4222",
			"4289",
			"4320",
			"4397",
			"4550",
			"4570",
			"4575",
			"4635",
			"4636",
			"4637",
			"4652",
			"4654",
			"4655",
			"4672",
			"4679",
			"4810",
			"4871",
			"4872",
			"4873",
			"4876",
			"4948",
			"4949",
			"4958",
			"4959",
			"4960",
			"4961",
			"4963",
			"4964",
			"4965",
			"4975",
			"4976",
			"4977",
			"8819",
			"8839",
			"8852",
			"8994",
			"9297",
			"9890",
			"9906",
			"9908",
			"9916",
			"9917",
			"9970",
			"9972",
			"9976",
			"9978",
			"9984",
		]
	),
	"SKR04": frozenset(
		[
			"2900",
			"2901",
			"2902",
			"2903",
			"2906",
			"2908",
			"2909",
			"2920",
			"2925",
			"2926",
			"2927",
			"2928",
			"2929",
			"2930",
			"2937",
			"2950",
			"2960",
			"2961",
			"2962",
			"2970",
			"2978",
			"4824",
			"4852",
			"4858",
			"4867",
			"4904",
			"4906",
			"4913",
			"4914",
			"4916",
			"4980",
			"4981",
			"4982",
			"5970",
			"5975",
			"5980",
			"5985",
			"6026",
			"6028",
			"6029",
			"6038",
			"6068",
			"6074",
			"6078",
			"6118",
			"6148",
			"6290",
			"6291",
			"6310",
			"6313",
			"6314",
			"6315",
			"6316",
			"6317",
			"6319",
			"6390",
			"6391",
			"6392",
			"6393",
			"6394",
			"6395",
			"6397",
			"6398",
			"6437",
			"6498",
			"6550",
			"6560",
			"6565",
			"6620",
			"6621",
			"6622",
			"6642",
			"6644",
			"6645",
			"6672",
			"6689",
			"6823",
			"6824",
			"6833",
			"6834",
			"6835",
			"6836",
			"6837",
			"6838",
			"6840",
			"6856",
			"6857",
			"6858",
			"6875",
			"6892",
			"6898",
			"6904",
			"6906",
			"6908",
			"6968",
			"7003",
			"7004",
			"7005",
			"7006",
			"7008",
			"7014",
			"7015",
			"7103",
			"7104",
			"7106",
			"7107",
			"7140",
			"7190",
			"7194",
			"7204",
			"7208",
			"7214",
			"7255",
			"7300",
			"7302",
			"7304",
			"7305",
			"7306",
			"7308",
			"7309",
			"7310",
			"7311",
			"7313",
			"7316",
			"7317",
			"7318",
			"7319",
			"7320",
			"7323",
			"7324",
			"7325",
			"7326",
			"7327",
			"7328",
			"7329",
			"7350",
			"7351",
			"7366",
			"7390",
			"7394",
			"7399",
			"7451",
			"7551",
			"7600",
			"7603",
			"7604",
			"7607",
			"7608",
			"7609",
			"7610",
			"7630",
			"7633",
			"7638",
			"7639",
			"7641",
			"7643",
			"7645",
			"7646",
			"7648",
			"7649",
			"7680",
			"7755",
			"9297",
			"9890",
			"9906",
			"9908",
			"9916",
			"9917",
			"9970",
			"9972",
			"9976",
			"9978",
			"9984",
		]
	),
}
# The defaults beyond the marks: the Bewirtungskosten for the hint, the accounts of the trading results, and the
# accounts of ERPNext's templates de_kontenplan_SKR03.json and de_kontenplan_SKR04.json (version 16).
# Accounts DATEV does not mark K whose balance may hold Bezüge, Gewinne or Gewinnminderungen aus Anteilen of § 8b KStG:
# income from holdings of no named legal form holds the filing back, the others ask for a look.
HOLDING_INCOME = {"SKR03": {"2600", "2619"}, "SKR04": {"7000", "7009"}}
SHARE_RESULTS = {
	"SKR03": {"2620", "2640", "2725", "2325", "4870", "4875", "4877", "4878"},
	"SKR04": {"7010", "7020", "4905", "6905", "7200", "7210", "7207", "7217"},
}
UNMARKED = {
	"SKR03": {
		"4650": Category.ENTERTAINMENT_DEDUCTIBLE,
		"2654": Category.TRADING_UNCLASSIFIED,
		"2166": Category.TRADING_UNCLASSIFIED,
		"2121": Category.INTEREST,
		"4665": Category.OTHER_NONDEDUCTIBLE,
		"2723": Category.SHARE_GAIN,
		"2323": Category.SHARE_LOSS,
		**dict.fromkeys(HOLDING_INCOME["SKR03"] | SHARE_RESULTS["SKR03"]),
	},
	"SKR04": {
		"6640": Category.ENTERTAINMENT_DEDUCTIBLE,
		"7115": Category.TRADING_UNCLASSIFIED,
		"6883": Category.TRADING_UNCLASSIFIED,
		"7640": Category.GEWST,
		"7642": Category.GEWST,
		"7644": Category.GEWST,
		"6396": Category.DONATIONS,
		"7007": Category.DIVIDENDS,
		"7340": Category.INTEREST,
		"7349": Category.INTEREST,
		"4901": Category.SHARE_GAIN,
		"6903": Category.SHARE_LOSS,
		"7464": None,
		"7563": None,
		"7452": None,
		**dict.fromkeys(HOLDING_INCOME["SKR04"] | SHARE_RESULTS["SKR04"]),
	},
}
# The pin of the content of each version: a change of the defaults raises REVISION and pins the new digest here.
DIGESTS = {
	"SKR03 2026.1": "fdb7ce2ffaa9ecfe8e737d626d66cc2ddf85b4a078216b7af620552f3c8a9b98",
	"SKR04 2026.1": "17da0b1384181b59cbbaf2e13c211f7edb7c230e002ed092da4496298bc23bb7",
	"SKR03 2026.2": "376ec2feb66839740f67718bbb9df56cd2a18af31ca24d3d54810c5158d2ce25",
	"SKR04 2026.2": "eff6e6e325ec06430bdfc93b8dd9c96d0f8db009ee07507ab7073a7d1b9b66ab",
	"SKR03 2026.3": "3eb40f62030abbc7b50c02ea421233b66082c9eaeb30c5e0b55c778401896732",
	"SKR04 2026.3": "eff6e6e325ec06430bdfc93b8dd9c96d0f8db009ee07507ab7073a7d1b9b66ab",
}


def places(chart: str) -> dict[str, tuple]:
	"""Every account of the defaults of the chart with its place, the category, the level or why it stays outside."""
	found: dict[str, tuple] = {}
	for account in default_accounts(chart):
		found[account.number] = (account.category or account.level,)
	for reason, numbers in OUTSIDE[chart].items():
		for number in numbers:
			found[number] = (reason,)
	return found


def category_of(chart: str, number: str) -> Category | None:
	rule = default_mapping(chart).rule_for(number)
	return None if rule is None else rule.category


class PlacesTest(TestCase):
	def test_every_account_the_chart_marks_k_or_g_has_one_place(self):
		for chart in CHARTS:
			with self.subTest(chart=chart):
				numbers = [account.number for account in default_accounts(chart)]
				numbers += [number for group in OUTSIDE[chart].values() for number in group]
				self.assertEqual([number for number, count in Counter(numbers).items() if count > 1], [])
				self.assertEqual(sorted(FLAGGED[chart] - set(numbers)), [])

	def test_an_account_the_chart_does_not_mark_is_one_of_the_few_named(self):
		for chart in CHARTS:
			with self.subTest(chart=chart):
				unmarked = {
					account.number: account.category
					for account in default_accounts(chart)
					if account.number not in FLAGGED[chart]
				}
				self.assertEqual(unmarked, UNMARKED[chart])
				outside = {number for group in OUTSIDE[chart].values() for number in group}
				self.assertLessEqual(outside, FLAGGED[chart])

	def test_skr04_mirrors_skr03_but_for_the_accounts_of_the_templates(self):
		def count(chart: str, leave_out: set[str]) -> Counter:
			return Counter(
				account.category or account.level
				for account in default_accounts(chart)
				if account.number not in leave_out
			)

		templates = {
			"2121",
			"4665",
			"7640",
			"7642",
			"7644",
			"6396",
			"7007",
			"7340",
			"7349",
			"4901",
			"6903",
			"2723",
			"2323",
			"7464",
			"7563",
			"7452",
		}
		self.assertEqual(count("SKR03", templates), count("SKR04", templates))
		self.assertEqual(
			{chart: len(default_accounts(chart)) for chart in CHARTS}, {"SKR03": 151, "SKR04": 159}
		)

	def test_the_equity_is_left_to_kst_1_f_and_the_partnerships_and_the_reserved_range_are_left_out(self):
		self.assertEqual(
			{chart: {reason: len(numbers) for reason, numbers in OUTSIDE[chart].items()} for chart in CHARTS},
			{
				"SKR03": {Outside.EQUITY: 22, Outside.PARTNERSHIP: 17, Outside.RESERVED: 1},
				"SKR04": {Outside.EQUITY: 22, Outside.PARTNERSHIP: 17, Outside.RESERVED: 0},
			},
		)
		self.assertIn("0800", OUTSIDE["SKR03"][Outside.EQUITY])
		self.assertIn("2900", OUTSIDE["SKR04"][Outside.EQUITY])
		self.assertEqual(OUTSIDE["SKR03"][Outside.RESERVED], ("2130",))
		for chart in CHARTS:
			with self.subTest(chart=chart):
				self.assertIsNone(default_mapping(chart).rule_for(OUTSIDE[chart][Outside.EQUITY][0]))


class CategoriesTest(TestCase):
	def test_the_taxes_on_income_of_anlage_gk_lines_81_to_84(self):
		expected = {
			Category.KST: ({"2200", "2203", "2204"}, {"7600", "7603", "7604"}),
			Category.SOLZ: ({"2208", "2209", "2210", "2216"}, {"7608", "7609", "7607", "7633"}),
			Category.KAPEST: ({"2213"}, {"7630"}),
			Category.GEWST: ({"4320", "2281", "2283"}, {"7610", "7641", "7643", "7640", "7642", "7644"}),
			Category.FOREIGN_TAX: ({"2218", "2219"}, {"7638", "7639"}),
		}
		for category, (skr03, skr04) in expected.items():
			with self.subTest(category=category):
				self.assertEqual(self.numbers("SKR03", category), skr03)
				self.assertEqual(self.numbers("SKR04", category), skr04)

	def test_the_nebenleistungen_aufsichtsrat_and_non_deductible_expenses_of_lines_88_to_90(self):
		expected = {
			Category.ANCILLARY: (
				{"2102", "2104", "2105", "2108", "4397", "2658", "2653"},
				{"7302", "7304", "7306", "7308", "6437", "7106", "7107"},
			),
			Category.SUPERVISORY_BOARD: ({"2385"}, {"6875"}),
			Category.GIFTS_NONDEDUCTIBLE: ({"4635", "4636", "4637"}, {"6620", "6621", "6622"}),
			Category.ENTERTAINMENT_NONDEDUCTIBLE: ({"4654"}, {"6644"}),
			Category.OTHER_NONDEDUCTIBLE: ({"4652", "4655", "2308", "4665"}, {"6642", "6645", "6968"}),
			Category.ENTERTAINMENT_DEDUCTIBLE: ({"4650"}, {"6640"}),
		}
		for category, (skr03, skr04) in expected.items():
			with self.subTest(category=category):
				self.assertEqual(self.numbers("SKR03", category), skr03)
				self.assertEqual(self.numbers("SKR04", category), skr04)
		self.assertIsNone(category_of("SKR03", "2386"), "the deductible half of the Aufsichtsratsvergütungen")

	def test_the_zuwendungen_of_line_92_and_those_anlage_z_does_not_deduct(self):
		self.assertEqual(
			self.numbers("SKR03", Category.DONATIONS),
			{"2380", "2381", "2382", "2383", "2384", "2387", "2389", "2390"},
		)
		self.assertEqual(
			self.numbers("SKR04", Category.DONATIONS),
			{"6390", "6391", "6392", "6393", "6394", "6395", "6396", "6397", "6398"},
		)
		self.assertEqual(
			dict(NON_DEDUCTIBLE_DONATIONS), {"SKR03": {"2380", "2384"}, "SKR04": {"6390", "6394"}}
		)
		for chart in CHARTS:
			with self.subTest(chart=chart):
				self.assertLessEqual(NON_DEDUCTIBLE_DONATIONS[chart], self.numbers(chart, Category.DONATIONS))

	def test_the_accounts_of_8b_kstg(self):
		expected = {
			Category.DIVIDENDS: (
				{"2615", "2616", "2625", "2626", "2655", "2656"},
				{"7005", "7006", "7014", "7015", "7103", "7104", "7007"},
			),
			Category.SHARE_GAIN: (
				{"2726", "2724", "8839", "2318", "8852", "2723"},
				{"4906", "4904", "4852", "4858", "4867", "4901"},
			),
			Category.SHARE_LOSS: (
				{"2326", "2324", "8819", "2313", "2328", "2323"},
				{"6906", "6904", "6892", "6898", "6908", "6903"},
			),
			Category.SHARE_SALE_COSTS: ({"4976", "4977"}, {"6857", "6858"}),
			Category.SHARE_WRITEUP: ({"2713", "2714", "2716"}, {"4913", "4914", "4916"}),
			Category.SHARE_WRITEDOWN: ({"4871", "4873", "4876"}, {"7204", "7255", "7214"}),
		}
		for category, (skr03, skr04) in expected.items():
			with self.subTest(category=category):
				self.assertEqual(self.numbers("SKR03", category), skr03)
				self.assertEqual(self.numbers("SKR04", category), skr04)

	def test_the_investitionsabzugsbetrag_of_7g_and_the_tax_free_income(self):
		for chart in CHARTS:
			with self.subTest(chart=chart):
				self.assertEqual(self.numbers(chart, Category.IAB_DEDUCTION), {"9970"})
				self.assertEqual(self.numbers(chart, Category.IAB_ADDBACK), {"9972"})
				for number in ("9916", "9917"):
					self.assertEqual(self.watched(chart)[number], (WatchLevel.BLOCKING, Reason.IAB_EARLIER))
				self.assertIsNone(category_of(chart, "9971"))
		self.assertEqual(self.numbers("SKR03", Category.INVESTMENT_GRANT), {"2744"})
		self.assertEqual(self.numbers("SKR03", Category.TAX_FREE), {"2746", "2747"})
		self.assertEqual(self.numbers("SKR04", Category.TAX_FREE), {"4981", "4982"})

	def test_the_financing_parts_and_the_grundsteuer_of_the_gewerbesteuer(self):
		expected = {
			Category.INTEREST: (
				{
					"2100",
					"2109",
					"2110",
					"2114",
					"2115",
					"2116",
					"2117",
					"2118",
					"2119",
					"2120",
					"2121",
					"2123",
					"2124",
					"2125",
					"2126",
					"2129",
					"8994",
				},
				{
					"7300",
					"7309",
					"7310",
					"7316",
					"7350",
					"7351",
					"7317",
					"7318",
					"7319",
					"7320",
					"7323",
					"7324",
					"7325",
					"7326",
					"7329",
					"7340",
					"7349",
					"4824",
				},
			),
			Category.ANNUITIES: ({"2127"}, {"7327"}),
			Category.SILENT_PARTNER: ({"2493"}, {"7399"}),
			Category.RENT_MOVABLE: (
				{"3170", "4570", "4810", "4958", "4960", "4961", "4963", "4965"},
				{"5970", "6560", "6498", "6833", "6835", "6836", "6838", "6840"},
			),
			Category.RENT_MOVABLE_EV: ({"4575"}, {"6565"}),
			Category.RENT_IMMOVABLE: (
				{"3175", "4210", "4211", "4215", "4220", "4222", "4550"},
				{"5975", "6310", "6317", "6316", "6315", "6313", "6550"},
			),
			Category.LICENCES: ({"3180", "4964"}, {"5980", "6837"}),
			Category.PROPERTY_TAX_OWN: ({"2375"}, {"7680"}),
		}
		for category, (skr03, skr04) in expected.items():
			with self.subTest(category=category):
				self.assertEqual(self.numbers("SKR03", category), skr03)
				self.assertEqual(self.numbers("SKR04", category), skr04)

	def test_the_trading_accounts_get_no_class(self):
		for chart, numbers in (("SKR03", {"2654", "2166"}), ("SKR04", {"7115", "6883"})):
			with self.subTest(chart=chart):
				self.assertEqual(self.numbers(chart, Category.TRADING_UNCLASSIFIED), numbers)
				self.assertEqual(
					[rule.account_number for rule in default_mapping(chart).rules if rule.trading_class], []
				)

	def test_every_category_of_the_defaults_feeds_a_line_or_holds_the_filing_back(self):
		fed = {category for step in (*kst_chain.STEPS, *gewst_chain.STEPS) for category in step.categories}
		for chart in CHARTS:
			used = {rule.category for rule in default_mapping(chart).rules}
			with self.subTest(chart=chart):
				self.assertEqual(
					{
						category
						for category in used - fed
						if not (CATEGORIES[category].later or CATEGORIES[category].hint_only)
					},
					{Category.TRADING_UNCLASSIFIED},
				)

	def numbers(self, chart: str, category: Category) -> set[str]:
		return {rule.account_number for rule in default_mapping(chart).rules if rule.category is category}

	def watched(self, chart: str) -> dict[str, tuple]:
		return {
			account.number: (account.level, account.reason)
			for account in default_accounts(chart)
			if account.level is not None
		}


class WatchedTest(TestCase):
	def test_watches_at_the_level_sperrt_what_needs_a_decision_or_a_line_by_hand(self):
		expected = {
			"SKR03": {
				"2107",
				"2111",
				"2148",
				"2682",
				"2250",
				"2255",
				"2260",
				"2265",
				"2440",
				"2441",
				"2004",
				"2504",
				"2490",
				"2494",
				"2790",
				"2794",
				"2603",
				"2614",
				"2618",
				"4872",
				"2745",
				"9890",
				"9906",
				"9908",
				"9916",
				"9917",
				"9976",
				"9978",
				"9984",
			},
			"SKR04": {
				"7305",
				"7311",
				"7366",
				"7140",
				"7645",
				"7649",
				"7646",
				"7648",
				"6290",
				"6291",
				"7551",
				"7451",
				"7390",
				"7394",
				"7190",
				"7194",
				"7004",
				"7003",
				"7008",
				"7208",
				"7755",
				"9890",
				"9906",
				"9908",
				"9916",
				"9917",
				"9976",
				"9978",
				"9984",
				"7464",
				"7563",
				"7452",
			},
		}
		for chart in CHARTS:
			with self.subTest(chart=chart):
				self.assertEqual(
					default_mapping(chart).watched_at(WatchLevel.BLOCKING),
					expected[chart] | HOLDING_INCOME[chart],
				)

	def test_watches_at_the_level_hinweis_what_asks_for_a_look(self):
		self.assertEqual(
			default_mapping("SKR03").watched_at(WatchLevel.HINT),
			{"4126", "4129", "4975"} | SHARE_RESULTS["SKR03"],
		)
		self.assertEqual(
			default_mapping("SKR04").watched_at(WatchLevel.HINT),
			{"6026", "6029", "6856"} | SHARE_RESULTS["SKR04"],
		)

	def test_holds_back_income_from_holdings_of_no_named_legal_form(self):
		"""A dividend of a Kapitalgesellschaft is exempt under § 8b Abs. 1 KStG only on an account of its category; DATEV
		marks Erträge aus Beteiligungen without the legal form not K, so its balance is fully taxed unless the company
		books it apart or gives the account its category."""
		for chart in CHARTS:
			with self.subTest(chart=chart):
				self.assertLessEqual(
					HOLDING_INCOME[chart], default_mapping(chart).watched_at(WatchLevel.BLOCKING)
				)

	def test_every_reason_says_why(self):
		self.assertEqual(set(REASONS), set(Reason))
		used = {account.reason for chart in CHARTS for account in default_accounts(chart) if account.reason}
		self.assertEqual(used, set(Reason))
		for reason, text in REASONS.items():
			with self.subTest(reason=reason):
				self.assertTrue(text.endswith("."))
				self.assertRegex(text, r"§|R \d|H \d")


class AccountTest(TestCase):
	def test_every_account_has_its_label_without_the_marks_of_the_footnotes(self):
		for chart in CHARTS:
			for account in default_accounts(chart):
				with self.subTest(chart=chart, account=account.number):
					self.assertTrue(account.label)
					self.assertIsNone(re.search(r"\d\)$", account.label))
					self.assertEqual(account.label.count("("), account.label.count(")"))
		self.assertEqual(
			{account.number: account.label for account in default_accounts("SKR04")}["7639"],
			"Anrechnung/Abzug ausländischer Quellensteuer",
		)

	def test_a_default_has_a_category_or_a_level_with_its_reason(self):
		for fields in (
			{},
			{"category": Category.KST, "level": WatchLevel.BLOCKING, "reason": Reason.TANTIEME},
			{"level": WatchLevel.HINT},
			{"category": Category.KST, "reason": Reason.TANTIEME},
		):
			with self.subTest(fields=fields), self.assertRaises(ValueError):
				DefaultAccount("2200", "Körperschaftsteuer", **fields)

	def test_the_accounts_of_a_chart_are_those_of_its_mapping(self):
		for chart in CHARTS:
			mapping = default_mapping(chart)
			with self.subTest(chart=chart):
				self.assertEqual(
					{account.number for account in ACCOUNTS[chart]},
					{rule.account_number for rule in mapping.rules}
					| {watched.account_number for watched in mapping.watched},
				)
				self.assertEqual(mapping.chart, chart)


class VersionTest(TestCase):
	def test_the_version_names_the_chart_the_datev_edition_and_the_revision(self):
		self.assertEqual((DATEV_EDITION, REVISION), (2026, 3))
		self.assertEqual([defaults_version(chart) for chart in CHARTS], ["SKR03 2026.3", "SKR04 2026.3"])

	def test_a_chart_without_defaults_has_none(self):
		for function in (defaults_version, default_mapping, default_accounts):
			with (
				self.subTest(function=function.__name__),
				self.assertRaisesRegex(
					KeyError, "no default Income Tax Mapping for chart 'Eigener Kontenrahmen'"
				),
			):
				function("Eigener Kontenrahmen")

	def test_a_version_always_means_the_same_defaults(self):
		for chart in CHARTS:
			with self.subTest(chart=chart):
				content = [
					(
						account.number,
						account.label,
						account.category,
						account.level and account.level.value,
						account.reason,
					)
					for account in default_accounts(chart)
				]
				digest = hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()
				self.assertEqual(
					digest,
					DIGESTS.get(defaults_version(chart)),
					f"The defaults of {chart} changed: raise REVISION in defaults.py and pin the digest of the new "
					"version in DIGESTS.",
				)
