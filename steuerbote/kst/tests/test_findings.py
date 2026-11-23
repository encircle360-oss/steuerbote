"""The findings of the Körperschaftsteuer: what holds the filing back, and what someone should look at."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.kst.categories import AccountRule, Category, Mapping
from steuerbote.kst.chain import Code, Finding, KstInputs, Severity, compute
from steuerbote.kst.holdings import Holding, HoldingResult
from steuerbote.kst.tests.support import FIGURES, credit, debit
from steuerbote.ustva.mapping import WatchedAccount, WatchLevel

ZERO = Decimal("0")
MAPPING = Mapping(
	"SKR03",
	(
		AccountRule("2654", Category.TRADING_UNCLASSIFIED),
		AccountRule("2166", Category.TRADING_UNCLASSIFIED),
		AccountRule("2219", Category.FOREIGN_TAX),
		AccountRule("2650", Category.FUNDS),
		AccountRule("4650", Category.ENTERTAINMENT_DEDUCTIBLE),
		AccountRule("4654", Category.ENTERTAINMENT_NONDEDUCTIBLE),
		AccountRule("2655", Category.DIVIDENDS),
		AccountRule("2383", Category.DONATIONS),
		AccountRule("2110", Category.INTEREST),
		AccountRule("9970", Category.IAB_DEDUCTION),
		AccountRule("9972", Category.IAB_ADDBACK),
	),
	(WatchedAccount("4289"), WatchedAccount("4672", WatchLevel.HINT)),
)


def findings(*lines, **kwargs) -> tuple[Finding, ...]:
	"""The findings of the lines; a loss waives the Verlustrücktrag unless the test chooses otherwise."""
	kwargs.setdefault("loss_carry_back", ZERO)
	return compute(KstInputs(2026, tuple(lines), MAPPING, **kwargs), FIGURES).findings


def codes(*lines, **kwargs) -> list[str]:
	return [finding.code for finding in findings(*lines, **kwargs)]


class FindingTest(TestCase):
	def test_an_error_blocks_and_a_hint_does_not(self):
		self.assertTrue(Finding(Code.WATCHED, Severity.ERROR, "Text", "§ 8 KStG").blocking)
		self.assertFalse(Finding(Code.INTEREST_BARRIER, Severity.HINT, "Text", "§ 4h EStG").blocking)

	def test_a_clean_year_has_no_findings_and_is_ready(self):
		result = compute(KstInputs(2026, (credit("8400", "1000.00"),), MAPPING), FIGURES)
		self.assertEqual(result.findings, ())
		self.assertTrue(result.ready)

	def test_a_blocking_finding_holds_the_filing_back(self):
		result = compute(KstInputs(2026, (debit("4289", "10.00"),), MAPPING), FIGURES)
		self.assertFalse(result.ready)


class TradingTest(TestCase):
	def test_each_trading_account_without_class_blocks_with_its_result_in_the_order_of_the_accounts(self):
		first, second = findings(credit("2654", "40000.00", "T-1"), debit("2166", "55000.00", "T-2"))
		self.assertEqual((first.code, second.code), (Code.UNCLASSIFIED_TRADING, Code.UNCLASSIFIED_TRADING))
		self.assertEqual((first.severity, second.severity), (Severity.ERROR, Severity.ERROR))
		self.assertIn("Konto 2166", first.text)
		self.assertIn("55.000,00 €", first.text)
		self.assertIn("Konto 2654", second.text)
		self.assertIn("40.000,00 €", second.text)
		self.assertIn("§ 15 Absatz 4 Satz 3 EStG", first.reference)


class LaterTest(TestCase):
	def test_foreign_taxes_block_until_the_anlage_aest_exists(self):
		(found,) = findings(debit("2219", "120.00"))
		self.assertEqual((found.code, found.severity), (Code.FOREIGN_TAX, Severity.ERROR))
		self.assertIn("120,00 €", found.text)
		self.assertIn("§ 26 KStG", found.reference)

	def test_investment_funds_block_until_the_invstg_is_computed(self):
		(found,) = findings(credit("2650", "700.00"))
		self.assertEqual((found.code, found.severity), (Code.FUNDS, Severity.ERROR))
		self.assertIn("§ 20 InvStG", found.reference)


class WatchedTest(TestCase):
	def test_a_watched_account_with_a_balance_blocks_or_gives_a_hint_by_its_level(self):
		self.assertEqual(
			[(f.code, f.severity) for f in findings(debit("4289", "50.00"), debit("4672", "20.00"))],
			[(Code.WATCHED, Severity.ERROR), (Code.WATCHED_HINT, Severity.HINT)],
		)
		self.assertIn("Konto 4289", findings(debit("4289", "50.00"))[0].text)


class EntertainmentTest(TestCase):
	"""§ 4 Absatz 5 Satz 1 Nummer 2 EStG: 30 % of entertainment are not deductible."""

	def test_hints_at_entertainment_booked_without_its_nondeductible_part(self):
		(found,) = findings(debit("4650", "1400.00"))
		self.assertEqual((found.code, found.severity), (Code.ENTERTAINMENT, Severity.HINT))
		self.assertIn("1.400,00 €", found.text)
		self.assertIn("600,00 €", found.text)

	def test_is_quiet_when_the_nondeductible_part_is_booked(self):
		self.assertEqual(codes(debit("4650", "1400.00"), debit("4654", "600.00")), [])


class HoldingsTest(TestCase):
	def test_hints_at_dividends_of_no_holding_taxed_as_streubesitz(self):
		(found,) = findings(credit("2655", "8000.00"))
		self.assertEqual((found.code, found.severity), (Code.STREUBESITZ, Severity.HINT))
		self.assertIn("8.000,00 €", found.text)

	def test_blocks_dividends_of_the_holdings_beyond_the_ledger(self):
		holding = HoldingResult(Holding("Beta GmbH", Decimal("12"), Decimal("12")), Decimal("12000.00"))
		(found,) = findings(credit("2655", "10000.00"), holdings=(holding,))
		self.assertEqual((found.code, found.severity), (Code.EXCESS_DIVIDENDS, Severity.ERROR))
		self.assertIn("2.000,00 €", found.text)

	def test_names_the_trading_book_of_absatz_7(self):
		(found,) = findings(credit("8400", "1.00"), trading_book=True)
		self.assertEqual((found.code, found.severity), (Code.TRADING_BOOK, Severity.HINT))
		self.assertIn("Zeile 16", found.text)


class LossesTest(TestCase):
	def test_a_loss_needs_the_verlustruecktrag_or_its_waiver(self):
		(found,) = findings(debit("4120", "30000.00"), loss_carry_back=None)
		self.assertEqual((found.code, found.severity), (Code.CARRY_BACK_MISSING, Severity.ERROR))
		self.assertIn("8900343", found.reference)
		self.assertEqual(codes(debit("4120", "30000.00"), loss_carry_back=ZERO), [])

	def test_a_verlustruecktrag_beyond_the_loss_blocks(self):
		(found,) = findings(debit("4120", "30000.00"), loss_carry_back=Decimal("30001"))
		self.assertEqual((found.code, found.severity), (Code.CARRY_BACK_TOO_HIGH, Severity.ERROR))
		self.assertIn("30.001,00 €", found.text)

	def test_zuwendungen_beyond_20_percent_need_the_turnover(self):
		(found,) = findings(credit("8400", "1000.00"), debit("2383", "500.00"))
		self.assertEqual((found.code, found.severity), (Code.TURNOVER_MISSING, Severity.ERROR))
		self.assertIn("8900101", found.reference)
		self.assertEqual(
			codes(credit("8400", "1000.00"), debit("2383", "500.00"), turnover_and_wages=ZERO), []
		)


class CreditsTest(TestCase):
	"""Rule 8912019: the Solidaritätszuschlag of Anlage WA line 3 is 5.5 % of line 2 within 0.05 €."""

	def test_hints_at_a_solidaritaetszuschlag_that_is_not_5_5_percent_of_the_kapitalertragsteuer(self):
		(found,) = findings(
			credit("8400", "1.00"), capital_gains_tax_credit=Decimal("5000.00"), solz_credit=Decimal("270.00")
		)
		self.assertEqual((found.code, found.severity), (Code.SOLZ_ON_KAPEST, Severity.HINT))
		self.assertIn("270,00 €", found.text)
		self.assertIn("275,00 €", found.text)

	def test_is_quiet_within_five_cents(self):
		self.assertEqual(
			codes(
				credit("8400", "1.00"),
				capital_gains_tax_credit=Decimal("5000.00"),
				solz_credit=Decimal("275.05"),
			),
			[],
		)
		self.assertEqual(codes(credit("8400", "1.00"), solz_credit=Decimal("10.00")), [])


class InterestAndIabTest(TestCase):
	def test_hints_at_the_zinsschranke_from_three_million_euro_of_interest(self):
		(found,) = findings(credit("8400", "4000000.00"), debit("2110", "3000000.00"))
		self.assertEqual((found.code, found.severity), (Code.INTEREST_BARRIER, Severity.HINT))
		self.assertEqual(codes(credit("8400", "4000000.00"), debit("2110", "2999999.99")), [])

	def test_an_investitionsabzugsbetrag_beyond_200_000_euro_blocks(self):
		found = codes(credit("8400", "100000.00"), debit("9970", "200001.00"), credit("9971", "200001.00"))
		self.assertEqual(found, [Code.IAB_LIMIT])

	def test_hints_at_an_investitionsabzugsbetrag_with_a_profit_beyond_200_000_euro(self):
		found = findings(credit("8400", "250000.00"), debit("9970", "10000.00"), credit("9971", "10000.00"))
		self.assertEqual([(f.code, f.severity) for f in found], [(Code.IAB_PROFIT, Severity.HINT)])
		self.assertIn("250.000,00 €", found[0].text)
		self.assertEqual(
			codes(
				credit("8400", "250000.00"),
				debit("9970", "10000.00"),
				credit("9971", "10000.00"),
				credit("9972", "60000.00"),
				debit("9973", "60000.00"),
			),
			[Code.IAB_PROFIT],
		)
		self.assertEqual(
			codes(credit("8400", "200000.00"), debit("9970", "10000.00"), credit("9971", "10000.00")), []
		)
