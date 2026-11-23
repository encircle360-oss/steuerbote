"""The ledger lines of the Wirtschaftsjahr summed per category, with the postings behind each amount."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.kst.categories import AccountRule, Category, Contribution, Mapping, TradingClass, classify
from steuerbote.kst.tests.support import credit, debit
from steuerbote.ustva.calculation import AccountBalance
from steuerbote.ustva.mapping import WatchedAccount, WatchLevel

SKR03 = Mapping(
	"SKR03",
	(
		AccountRule("2200", Category.KST),
		AccountRule("2204", Category.KST),
		AccountRule("2655", Category.DIVIDENDS),
		AccountRule("2654", Category.TRADING_UNCLASSIFIED),
		AccountRule("4210", Category.RENT_IMMOVABLE),
		AccountRule("2219", Category.FOREIGN_TAX),
	),
	(WatchedAccount("4289"), WatchedAccount("4650", WatchLevel.HINT)),
)


def with_class(trading_class: TradingClass | None) -> Mapping:
	return Mapping("SKR03", (AccountRule("2654", Category.TRADING_UNCLASSIFIED, trading_class),))


class AmountTest(TestCase):
	def test_counts_an_expense_on_the_debit_side_net_of_refunds(self):
		result = classify([debit("2200", "2500.00"), credit("2204", "300.00", "JV-2")], SKR03)
		self.assertEqual(result.amount(Category.KST), Decimal("2200.00"))

	def test_counts_an_income_on_the_credit_side(self):
		result = classify([credit("2655", "8000.00"), debit("2655", "100.00", "JV-2")], SKR03)
		self.assertEqual(result.amount(Category.DIVIDENDS), Decimal("7900.00"))

	def test_an_account_without_rule_counts_in_no_category(self):
		result = classify([credit("8400", "1000.00"), debit("4210", "200.00")], SKR03)
		self.assertEqual(set(result.amounts), {Category.RENT_IMMOVABLE})
		self.assertEqual(result.amount(Category.DONATIONS), Decimal("0"))

	def test_sums_several_categories(self):
		result = classify([debit("2200", "10.00"), debit("4210", "5.00")], SKR03)
		self.assertEqual(result.amount(Category.KST, Category.RENT_IMMOVABLE), Decimal("15.00"))


class ContributionTest(TestCase):
	def test_keeps_the_postings_of_each_account_and_voucher_in_the_order_of_their_first_line(self):
		result = classify(
			[
				debit("2200", "2500.00", "JV-2"),
				credit("2204", "300.00", "JV-1"),
				debit("2200", "2500.00", "JV-3"),
				debit("2200", "1.00", "JV-2"),
			],
			SKR03,
		)
		self.assertEqual(
			result.contributions(Category.KST),
			(
				Contribution(Category.KST, "2200", "JV-2", Decimal("2501.00"), Decimal("0")),
				Contribution(Category.KST, "2200", "JV-3", Decimal("2500.00"), Decimal("0")),
				Contribution(Category.KST, "2204", "JV-1", Decimal("0"), Decimal("300.00")),
			),
		)
		self.assertEqual(
			[contribution.amount for contribution in result.contributions(Category.KST)],
			[Decimal("2501.00"), Decimal("2500.00"), Decimal("-300.00")],
		)

	def test_lines_without_voucher_count_as_one_voucher(self):
		result = classify([debit("2200", "1.00", None), debit("2200", "2.00", None)], SKR03)
		(contribution,) = result.contributions(Category.KST)
		self.assertIsNone(contribution.voucher)
		self.assertEqual(contribution.amount, Decimal("3.00"))

	def test_an_income_counts_credit_less_debit(self):
		contribution = Contribution(Category.DIVIDENDS, "2655", "JV-1", Decimal("100.00"), Decimal("8000.00"))
		self.assertEqual(contribution.amount, Decimal("7900.00"))


class TradingClassTest(TestCase):
	"""A class splits a trading account voucher by voucher into gains and losses."""

	LINES = (
		credit("2654", "40000.00", "TRADE-1"),
		debit("2654", "55000.00", "TRADE-2"),
		credit("2654", "10.00", "TRADE-3"),
		debit("2654", "10.00", "TRADE-3"),
	)

	def test_shares_give_gains_and_losses_of_paragraph_8b(self):
		result = classify(self.LINES, with_class(TradingClass.SHARES))
		self.assertEqual(result.amount(Category.SHARE_GAIN), Decimal("40000.00"))
		self.assertEqual(result.amount(Category.SHARE_LOSS), Decimal("55000.00"))
		self.assertEqual([c.voucher for c in result.contributions(Category.SHARE_GAIN)], ["TRADE-1"])
		self.assertEqual(result.unclassified, ())

	def test_termingeschaefte_give_gains_and_losses_of_paragraph_15_absatz_4(self):
		result = classify(self.LINES, with_class(TradingClass.DERIVATIVES))
		self.assertEqual(result.amount(Category.DERIVATIVES_GAIN), Decimal("40000.00"))
		self.assertEqual(result.amount(Category.DERIVATIVES_LOSS), Decimal("55000.00"))
		self.assertEqual([c.voucher for c in result.contributions(Category.DERIVATIVES_LOSS)], ["TRADE-2"])

	def test_investment_funds_net_into_their_later_category(self):
		result = classify(self.LINES, with_class(TradingClass.FUNDS))
		self.assertEqual(result.amount(Category.FUNDS), Decimal("-15000.00"))
		self.assertEqual(result.later, (Category.FUNDS,))

	def test_a_fully_taxable_result_needs_no_category(self):
		result = classify(self.LINES, with_class(TradingClass.TAXABLE))
		self.assertEqual(dict(result.amounts), {})
		self.assertEqual(result.unclassified, ())

	def test_a_voucher_that_nets_to_zero_is_neither_gain_nor_loss(self):
		result = classify(self.LINES[2:], with_class(TradingClass.SHARES))
		self.assertEqual(dict(result.amounts), {})

	def test_a_trading_account_without_class_holds_the_filing_back(self):
		result = classify(self.LINES, with_class(None))
		self.assertEqual(result.amount(Category.TRADING_UNCLASSIFIED), Decimal("-15000.00"))
		self.assertEqual(
			result.unclassified, (AccountBalance("2654", Decimal("55010.00"), Decimal("40010.00")),)
		)

	def test_an_unclassified_trading_account_without_balance_holds_nothing_back(self):
		result = classify(self.LINES[2:], with_class(None))
		self.assertEqual(result.unclassified, ())


class HoldBackTest(TestCase):
	def test_lists_the_watched_accounts_with_a_balance_by_level(self):
		result = classify([debit("4289", "50.00"), debit("4650", "1400.00"), debit("4650", "0.00")], SKR03)
		self.assertEqual(result.watched, (AccountBalance("4289", Decimal("50.00"), Decimal("0")),))
		self.assertEqual(result.hinted, (AccountBalance("4650", Decimal("1400.00"), Decimal("0")),))

	def test_a_watched_account_without_balance_is_not_listed(self):
		result = classify([debit("4289", "50.00"), credit("4289", "50.00", "JV-2")], SKR03)
		self.assertEqual(result.watched, ())

	def test_lists_the_later_categories_with_a_balance(self):
		self.assertEqual(classify([debit("2219", "12.00")], SKR03).later, (Category.FOREIGN_TAX,))
		self.assertEqual(classify([debit("2219", "12.00"), credit("2219", "12.00", "JV-2")], SKR03).later, ())
