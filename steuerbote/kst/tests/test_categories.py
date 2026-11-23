"""The categories of the Income Tax Mapping, the classes of trading results and the mapping of a company."""

from unittest import TestCase

from steuerbote.kst.categories import (
	CATEGORIES,
	LATER,
	TRADING_CATEGORIES,
	AccountRule,
	Category,
	Mapping,
	Nature,
	TradingClass,
)
from steuerbote.ustva.mapping import MappingError, WatchedAccount, WatchLevel


class CategoryTest(TestCase):
	def test_names_the_categories_of_the_income_tax_mapping(self):
		self.assertEqual(
			[category.value for category in Category],
			[
				"kst",
				"solz",
				"kapest",
				"gewst",
				"foreign_tax",
				"ancillary",
				"supervisory_board",
				"gifts_nondeductible",
				"entertainment_nondeductible",
				"entertainment_deductible",
				"other_nondeductible",
				"donations",
				"tax_free",
				"investment_grant",
				"dividends",
				"share_gain",
				"share_loss",
				"share_writedown",
				"share_writeup",
				"share_sale_costs",
				"derivatives_gain",
				"derivatives_loss",
				"funds",
				"iab_deduction",
				"iab_addback",
				"interest",
				"annuities",
				"silent_partner",
				"rent_movable",
				"rent_movable_ev",
				"rent_immovable",
				"licences",
				"property_tax_own",
				"trading_unclassified",
			],
		)

	def test_describes_every_category_with_its_law(self):
		self.assertEqual(set(CATEGORIES), set(Category))
		for category, info in CATEGORIES.items():
			with self.subTest(category=category):
				self.assertTrue(info.label)
				self.assertRegex(info.law, r"§ \d+")

	def test_income_is_counted_on_the_credit_side_and_expenses_on_the_debit_side(self):
		income = {category for category, info in CATEGORIES.items() if info.nature is Nature.INCOME}
		self.assertEqual(
			income,
			{
				Category.TAX_FREE,
				Category.INVESTMENT_GRANT,
				Category.DIVIDENDS,
				Category.SHARE_GAIN,
				Category.SHARE_WRITEUP,
				Category.DERIVATIVES_GAIN,
				Category.FUNDS,
				Category.IAB_ADDBACK,
				Category.TRADING_UNCLASSIFIED,
			},
		)

	def test_foreign_taxes_and_investment_funds_wait_for_later_modules(self):
		self.assertEqual(LATER, frozenset({Category.FOREIGN_TAX, Category.FUNDS}))
		self.assertTrue(CATEGORIES[Category.FOREIGN_TAX].later)
		self.assertFalse(CATEGORIES[Category.KST].later)

	def test_the_deductible_part_of_entertainment_only_gives_a_hint(self):
		self.assertTrue(CATEGORIES[Category.ENTERTAINMENT_DEDUCTIBLE].hint_only)
		self.assertEqual(
			{c for c, info in CATEGORIES.items() if info.hint_only}, {Category.ENTERTAINMENT_DEDUCTIBLE}
		)


class TradingClassTest(TestCase):
	"""A trading account takes its treatment from a class the Steuerberatung decides, never from a default."""

	def test_names_the_classes(self):
		self.assertEqual(
			[trading_class.value for trading_class in TradingClass],
			["shares", "derivatives", "funds", "taxable"],
		)

	def test_maps_the_gains_and_losses_of_each_class_to_a_category(self):
		self.assertEqual(
			TRADING_CATEGORIES,
			{
				TradingClass.SHARES: (Category.SHARE_GAIN, Category.SHARE_LOSS),
				TradingClass.DERIVATIVES: (Category.DERIVATIVES_GAIN, Category.DERIVATIVES_LOSS),
				TradingClass.FUNDS: (Category.FUNDS, Category.FUNDS),
				TradingClass.TAXABLE: None,
			},
		)

	def test_a_class_belongs_to_a_trading_account_only(self):
		AccountRule("2654", Category.TRADING_UNCLASSIFIED, TradingClass.DERIVATIVES)
		AccountRule("2654", Category.TRADING_UNCLASSIFIED)
		with self.assertRaisesRegex(
			MappingError, "account 2726: a trading class needs the category trading_unclassified"
		):
			AccountRule("2726", Category.SHARE_GAIN, TradingClass.SHARES)

	def test_takes_the_values_of_a_form(self):
		rule = AccountRule("2654", "trading_unclassified", "derivatives")  # type: ignore[arg-type]
		self.assertIs(rule.category, Category.TRADING_UNCLASSIFIED)
		self.assertIs(rule.trading_class, TradingClass.DERIVATIVES)
		with self.assertRaises(ValueError):
			AccountRule("2654", "shares")  # type: ignore[arg-type]


class MappingTest(TestCase):
	def test_finds_the_rule_of_an_account(self):
		mapping = Mapping("SKR03", (AccountRule("2200", Category.KST), AccountRule("4320", Category.GEWST)))
		self.assertEqual(mapping.rule_for("4320"), AccountRule("4320", Category.GEWST))
		self.assertIsNone(mapping.rule_for("8400"))

	def test_watches_accounts_at_their_level(self):
		mapping = Mapping(
			"SKR03",
			(AccountRule("2200", Category.KST),),
			(WatchedAccount("4289"), WatchedAccount("4650", WatchLevel.HINT)),
		)
		self.assertEqual(mapping.watched_at(WatchLevel.BLOCKING), frozenset({"4289"}))
		self.assertEqual(mapping.watched_at(WatchLevel.HINT), frozenset({"4650"}))

	def test_a_bare_account_number_is_watched_at_the_blocking_level(self):
		mapping = Mapping("SKR03", (), ("4289",))  # type: ignore[arg-type]
		self.assertEqual(mapping.watched, (WatchedAccount("4289", WatchLevel.BLOCKING),))

	def test_an_account_has_one_rule(self):
		with self.assertRaisesRegex(MappingError, "account 2200 has more than one rule"):
			Mapping("SKR03", (AccountRule("2200", Category.KST), AccountRule("2200", Category.SOLZ)))

	def test_an_account_is_either_mapped_or_watched(self):
		with self.assertRaisesRegex(MappingError, "account 2200 is mapped and watched"):
			Mapping("SKR03", (AccountRule("2200", Category.KST),), (WatchedAccount("2200"),))
		with self.assertRaisesRegex(MappingError, "account 4289 is watched twice"):
			Mapping("SKR03", (), (WatchedAccount("4289"), WatchedAccount("4289", WatchLevel.HINT)))

	def test_refuses_what_is_no_account_number(self):
		with self.assertRaisesRegex(MappingError, "' 2200' is not an account number"):
			AccountRule(" 2200", Category.KST)

	def test_rules_and_watched_accounts_are_sequences(self):
		with self.assertRaisesRegex(MappingError, "rules must be a sequence of AccountRule"):
			Mapping("SKR03", "2200")  # type: ignore[arg-type]
		with self.assertRaisesRegex(MappingError, "watched must be a sequence"):
			Mapping("SKR03", (), "4289")  # type: ignore[arg-type]
