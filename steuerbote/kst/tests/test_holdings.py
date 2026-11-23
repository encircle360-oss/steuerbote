"""§ 8b KStG per holding: which dividends are exempt, and the lines 156 to 201 of Anlage GK."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.kst.holdings import Exemption, Holding, HoldingResult, exemption, p8b
from steuerbote.kst.years import YEARS

YEAR = YEARS[2026]
ZERO = Decimal("0")


def holding(name: str, share: str, ez_share: str | None = None, acquired: str = "0") -> Holding:
	return Holding(name, Decimal(share), Decimal(ez_share or share), Decimal(acquired))


def result(name: str, share: str, dividends: str, **kwargs: str) -> HoldingResult:
	return HoldingResult(
		holding(name, share), Decimal(dividends), **{k: Decimal(v) for k, v in kwargs.items()}
	)


def compute(**kwargs: object):
	amounts = {
		"dividends": ZERO,
		"gains": ZERO,
		"sale_costs": ZERO,
		"losses": ZERO,
		"writedowns": ZERO,
		"writeups": ZERO,
	}
	amounts.update({key: Decimal(value) for key, value in kwargs.items() if key in amounts})  # type: ignore[arg-type]
	return p8b(
		YEAR,
		holdings=kwargs.get("holdings", ()),  # type: ignore[arg-type]
		trading_book=bool(kwargs.get("trading_book", False)),
		**amounts,
	)


class ExemptionTest(TestCase):
	"""§ 8b Absatz 1, 4 und 7 KStG."""

	def test_dividends_of_a_holding_of_10_percent_at_the_start_of_the_year_are_exempt(self):
		self.assertIs(exemption(holding("Beta GmbH", "10"), YEAR), Exemption.EXEMPT)

	def test_dividends_of_a_holding_below_10_percent_are_taxed_as_streubesitz(self):
		self.assertIs(exemption(holding("Gamma AG", "9.99"), YEAR), Exemption.STREUBESITZ)

	def test_an_acquisition_of_10_percent_during_the_year_counts_as_at_the_start_of_the_year(self):
		self.assertIs(exemption(holding("Delta GmbH", "0", acquired="10"), YEAR), Exemption.EXEMPT)

	def test_an_acquisition_below_10_percent_does_not_count_even_if_the_holding_grows_beyond(self):
		self.assertIs(exemption(holding("Delta GmbH", "5", acquired="6"), YEAR), Exemption.STREUBESITZ)

	def test_the_trading_book_of_absatz_7_taxes_every_holding(self):
		self.assertIs(exemption(holding("Beta GmbH", "50"), YEAR, trading_book=True), Exemption.TRADING_BOOK)


class HoldingTest(TestCase):
	def test_a_holding_has_a_name(self):
		with self.assertRaisesRegex(ValueError, "a holding needs a name"):
			holding(" ", "10")

	def test_shares_are_percentages(self):
		for share in ("-1", "100.01", "NaN"):
			with (
				self.subTest(share=share),
				self.assertRaisesRegex(ValueError, "Beta GmbH: .* is a percentage"),
			):
				holding("Beta GmbH", share)
		with self.assertRaises(TypeError):
			Holding("Beta GmbH", 10.0, Decimal("10"))  # type: ignore[arg-type]

	def test_dividends_and_costs_are_amounts_in_cents_of_at_least_zero(self):
		with self.assertRaisesRegex(ValueError, "Beta GmbH: the dividends"):
			result("Beta GmbH", "12", "-1.00")
		with self.assertRaisesRegex(ValueError, "Beta GmbH: the other costs"):
			result("Beta GmbH", "12", "1.00", other_costs="0.001")


class DividendsTest(TestCase):
	def test_exempt_dividends_with_their_five_percent_in_lines_156_and_160(self):
		found = compute(dividends="12000.00", holdings=(result("Beta GmbH", "12", "12000.00"),))
		self.assertEqual(
			(found.exempt_dividends.exact, found.exempt_dividends.declared),
			(Decimal("12000.00"), Decimal("12000")),
		)
		self.assertEqual(found.dividends_nondeductible.declared, Decimal("600"))
		self.assertEqual(found.taxed_dividends, ZERO)

	def test_streubesitz_dividends_stay_in_the_income(self):
		found = compute(dividends="8000.00", holdings=(result("Gamma AG", "0.01", "8000.00"),))
		self.assertEqual(found.exempt_dividends.declared, ZERO)
		self.assertEqual(found.dividends_nondeductible.declared, ZERO)
		self.assertEqual(found.taxed_dividends, Decimal("8000.00"))

	def test_dividends_of_no_holding_count_as_streubesitz(self):
		found = compute(dividends="20000.00", holdings=(result("Beta GmbH", "12", "12000.00"),))
		self.assertEqual(found.unassigned_dividends, Decimal("8000.00"))
		self.assertEqual(found.taxed_dividends, Decimal("8000.00"))
		self.assertEqual(found.excess_dividends, ZERO)

	def test_names_dividends_of_the_holdings_beyond_those_of_the_ledger(self):
		found = compute(dividends="10000.00", holdings=(result("Beta GmbH", "12", "12000.00"),))
		self.assertEqual(found.excess_dividends, Decimal("2000.00"))
		self.assertEqual(found.unassigned_dividends, ZERO)

	def test_keeps_the_exemption_of_each_holding_and_whether_an_acquisition_counted(self):
		bought = HoldingResult(holding("Delta GmbH", "0", acquired="25"), Decimal("1000.00"))
		found = compute(dividends="9000.00", holdings=(result("Gamma AG", "1", "8000.00"), bought))
		self.assertEqual([h.exemption for h in found.holdings], [Exemption.STREUBESITZ, Exemption.EXEMPT])
		self.assertEqual([h.acquisition_counts for h in found.holdings], [False, True])


class SharesTest(TestCase):
	def test_gains_are_exempt_and_five_percent_of_them_are_added_back(self):
		found = compute(gains="30000.00")
		self.assertEqual(found.gains.declared, Decimal("30000"))
		self.assertEqual(found.gains_nondeductible.declared, Decimal("1500"))

	def test_sale_costs_reduce_the_gains(self):
		found = compute(gains="30000.00", sale_costs="500.00")
		self.assertEqual(found.gains.exact, Decimal("29500.00"))
		self.assertEqual(found.losses.exact, ZERO)

	def test_sale_costs_beyond_the_gains_add_to_the_losses(self):
		found = compute(gains="100.00", sale_costs="300.00", losses="1000.00")
		self.assertEqual(found.gains.exact, ZERO)
		self.assertEqual(found.losses.exact, Decimal("1200.00"))

	def test_losses_and_writedowns_are_added_back_in_full(self):
		found = compute(losses="12000.00", writedowns="4000.00")
		self.assertEqual(found.losses.declared, Decimal("12000"))
		self.assertEqual(found.writedowns.declared, Decimal("4000"))

	def test_writeups_are_exempt_and_count_in_the_five_percent(self):
		found = compute(gains="1000.00", writeups="1000.00")
		self.assertEqual(found.writeups.declared, Decimal("1000"))
		self.assertEqual(found.gains_nondeductible.declared, Decimal("100"))

	def test_line_201_adds_the_lines_160_166c_181_and_188_and_subtracts_156_166b_and_176(self):
		found = compute(
			dividends="20000.00",
			holdings=(result("Beta GmbH", "12", "12000.00"), result("Gamma AG", "1", "8000.00")),
			gains="30000.00",
			losses="12000.00",
			writedowns="4000.00",
		)
		self.assertEqual(found.total.declared, Decimal("-23900"))
		self.assertEqual(found.total.exact, Decimal("-23900.00"))


class RoundingTest(TestCase):
	"""Rules 8956007, 8956020, 8956040, 8956042, 8956044 and 8905506 of Jahresdokumentation_E30_2025.ods."""

	def test_rounds_the_exempt_dividends_and_the_gains_and_writeups_up(self):
		found = compute(
			dividends="12000.01",
			holdings=(result("Beta GmbH", "12", "12000.01"),),
			gains="0.01",
			writeups="0.50",
		)
		self.assertEqual(found.exempt_dividends.declared, Decimal("12001"))
		self.assertEqual(found.gains.declared, Decimal("1"))
		self.assertEqual(found.writeups.declared, Decimal("1"))

	def test_takes_five_percent_of_the_declared_amounts_rounded_down(self):
		found = compute(
			dividends="12019.00", holdings=(result("Beta GmbH", "12", "12019.00"),), gains="39.00"
		)
		self.assertEqual(found.dividends_nondeductible.declared, Decimal("600"))
		self.assertEqual(found.dividends_nondeductible.exact, Decimal("600.95"))
		self.assertEqual(found.gains_nondeductible.declared, Decimal("1"))

	def test_rounds_the_losses_down_and_the_writedowns_half_up(self):
		found = compute(losses="12000.99", writedowns="4000.50")
		self.assertEqual(found.losses.declared, Decimal("12000"))
		self.assertEqual(found.writedowns.declared, Decimal("4001"))


class TradingBookTest(TestCase):
	"""§ 8b Absatz 7 KStG: shares of the trading book are taxed in full, gains and losses as any other."""

	def test_corrects_nothing(self):
		found = compute(
			dividends="12000.00",
			holdings=(result("Beta GmbH", "12", "12000.00"),),
			gains="30000.00",
			losses="12000.00",
			writedowns="4000.00",
			writeups="10.00",
			trading_book=True,
		)
		for line in (
			found.exempt_dividends,
			found.dividends_nondeductible,
			found.gains,
			found.losses,
			found.writeups,
			found.gains_nondeductible,
			found.writedowns,
			found.total,
		):
			self.assertEqual((line.exact, line.declared), (ZERO, ZERO))
		self.assertEqual(found.taxed_dividends, Decimal("12000.00"))
		self.assertEqual([h.exemption for h in found.holdings], [Exemption.TRADING_BOOK])
