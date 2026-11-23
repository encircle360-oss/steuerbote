"""compute(): the Körperschaftsteuer from the ledger lines of the Wirtschaftsjahr and the inputs of the settings."""

from dataclasses import replace
from decimal import Decimal
from unittest import TestCase

from steuerbote.kst.categories import AccountRule, Category, Contribution, Mapping, TradingClass
from steuerbote.kst.chain import KstInputs, ManualLine, compute
from steuerbote.kst.holdings import Holding, HoldingResult
from steuerbote.kst.tests.support import FIGURES, credit, debit

ZERO = Decimal("0")
MAPPING = Mapping(
	"SKR03",
	(
		AccountRule("2200", Category.KST),
		AccountRule("2208", Category.SOLZ),
		AccountRule("2216", Category.SOLZ),
		AccountRule("2213", Category.KAPEST),
		AccountRule("4320", Category.GEWST),
		AccountRule("4397", Category.ANCILLARY),
		AccountRule("4635", Category.GIFTS_NONDEDUCTIBLE),
		AccountRule("4654", Category.ENTERTAINMENT_NONDEDUCTIBLE),
		AccountRule("4650", Category.ENTERTAINMENT_DEDUCTIBLE),
		AccountRule("2383", Category.DONATIONS),
		AccountRule("2655", Category.DIVIDENDS),
		AccountRule("2625", Category.DIVIDENDS),
		AccountRule("2726", Category.SHARE_GAIN),
		AccountRule("2326", Category.SHARE_LOSS),
		AccountRule("4876", Category.SHARE_WRITEDOWN),
		AccountRule("2654", Category.TRADING_UNCLASSIFIED, TradingClass.DERIVATIVES),
		AccountRule("2166", Category.TRADING_UNCLASSIFIED, TradingClass.DERIVATIVES),
		AccountRule("2744", Category.INVESTMENT_GRANT),
		AccountRule("2747", Category.TAX_FREE),
		AccountRule("9970", Category.IAB_DEDUCTION),
		AccountRule("2110", Category.INTEREST),
	),
)
BETA = Holding("Beta GmbH", Decimal("12"), Decimal("12"))


def inputs(*lines, **kwargs) -> KstInputs:
	return KstInputs(2026, tuple(lines), MAPPING, **kwargs)


class NetIncomeTest(TestCase):
	"""Anlage GK line 11: the Jahresüberschuss of the ledger and the Überleitung to the Steuerbilanz."""

	def test_is_the_credits_less_the_debits_of_all_lines(self):
		result = compute(
			inputs(credit("8400", "220000.00"), debit("4120", "120000.00"), debit("2200", "10000.00")),
			FIGURES,
		)
		line = result.lines["net_income"]
		self.assertEqual((line.exact, line.declared), (Decimal("90000.00"), Decimal("90000")))

	def test_takes_a_given_jahresueberschuss_such_as_that_of_the_e_bilanz(self):
		result = compute(inputs(credit("8400", "1.00"), net_income=Decimal("86338.60")), FIGURES)
		line = result.lines["net_income"]
		self.assertEqual((line.exact, line.declared), (Decimal("86338.60"), Decimal("86339")))

	def test_adds_the_ueberleitung_as_manual_lines_with_their_reasons(self):
		reconciliation = ManualLine(
			"net_income", Decimal("-1500.00"), "Drohverlustrückstellung, § 5 Absatz 4a EStG"
		)
		result = compute(inputs(credit("8400", "10000.00"), manual=(reconciliation,)), FIGURES)
		line = result.lines["net_income"]
		self.assertEqual(
			(line.exact, line.declared, line.ledger),
			(Decimal("8500.00"), Decimal("8500"), Decimal("10000.00")),
		)
		self.assertEqual(line.manual, (reconciliation,))


class LedgerLinesTest(TestCase):
	def test_a_line_sums_its_categories_and_keeps_the_postings_behind_it(self):
		result = compute(
			inputs(
				debit("4654", "600.00", "JV-1"), debit("4635", "300.00", "JV-2"), debit("4650", "1400.00")
			),
			FIGURES,
		)
		line = result.lines["nondeductible"]
		self.assertEqual((line.exact, line.declared), (Decimal("900.00"), Decimal("900")))
		self.assertEqual(
			line.contributions,
			(
				Contribution(Category.GIFTS_NONDEDUCTIBLE, "4635", "JV-2", Decimal("300.00"), ZERO),
				Contribution(Category.ENTERTAINMENT_NONDEDUCTIBLE, "4654", "JV-1", Decimal("600.00"), ZERO),
			),
		)

	def test_declares_whole_euros_rounded_half_up(self):
		result = compute(inputs(debit("2208", "642.40"), debit("2216", "275.00", "JV-2")), FIGURES)
		self.assertEqual(result.lines["solidarity_surcharge"].declared, Decimal("917"))
		result = compute(inputs(debit("2200", "0.50")), FIGURES)
		self.assertEqual(result.lines["corporate_tax"].declared, Decimal("1"))

	def test_a_line_without_postings_is_zero(self):
		result = compute(inputs(credit("8400", "1.00")), FIGURES)
		line = result.lines["ancillary"]
		self.assertEqual((line.exact, line.declared, line.contributions, line.manual), (ZERO, ZERO, (), ()))

	def test_manual_lines_correct_a_line_of_the_ledger(self):
		correction = ManualLine("ancillary", Decimal("50.00"), "Säumniszuschlag auf Konto 4900 gebucht")
		result = compute(inputs(debit("4397", "200.00"), manual=(correction,)), FIGURES)
		line = result.lines["ancillary"]
		self.assertEqual(
			(line.exact, line.declared, line.ledger), (Decimal("250.00"), Decimal("250"), Decimal("200.00"))
		)

	def test_a_manual_step_takes_its_amount_from_manual_lines_only(self):
		vga = ManualLine("hidden_distributions", Decimal("3000.00"), "Überhöhte Miete an den Gesellschafter")
		result = compute(inputs(credit("8400", "1.00"), manual=(vga,)), FIGURES)
		self.assertEqual(result.lines["hidden_distributions"].declared, Decimal("3000"))
		self.assertEqual(result.lines["business_income"].declared, Decimal("3001"))

	def test_refuses_manual_lines_where_the_computation_decides(self):
		for key in (
			"business_income",
			"p8b_total",
			"corporate_income_tax",
			"kst_prepayments",
			"investment_funds",
		):
			with (
				self.subTest(step=key),
				self.assertRaisesRegex(ValueError, f"step {key} takes no manual line"),
			):
				ManualLine(key, Decimal("1.00"), "Grund")

	def test_a_manual_line_needs_a_known_step_an_amount_in_cents_and_a_reason(self):
		with self.assertRaisesRegex(ValueError, "no step 'vga'"):
			ManualLine("vga", Decimal("1.00"), "Grund")
		with self.assertRaisesRegex(ValueError, "an amount in cents"):
			ManualLine("hidden_distributions", Decimal("1.001"), "Grund")
		with self.assertRaisesRegex(ValueError, "a reason"):
			ManualLine("hidden_distributions", Decimal("1.00"), "  ")


class ParagraphEightBTest(TestCase):
	def test_the_lines_of_paragraph_8b_with_the_postings_of_their_categories(self):
		result = compute(
			inputs(
				credit("2625", "12000.00", "DIV-1"),
				credit("2726", "30000.00", "SALE-1"),
				debit("2326", "12000.00", "SALE-2"),
				debit("4876", "4000.00", "TW-1"),
				holdings=(HoldingResult(BETA, Decimal("12000.00")),),
			),
			FIGURES,
		)
		declared = {key: result.lines[key].declared for key in result.lines if key.startswith("p8b")}
		self.assertEqual(
			declared,
			{
				"p8b_dividends": Decimal("12000"),
				"p8b_dividends_nondeductible": Decimal("600"),
				"p8b_gains": Decimal("30000"),
				"p8b_losses": Decimal("12000"),
				"p8b_writeups": ZERO,
				"p8b_gains_nondeductible": Decimal("1500"),
				"p8b_writedowns": Decimal("4000"),
				"p8b_total": Decimal("-23900"),
			},
		)
		self.assertEqual([c.voucher for c in result.lines["p8b_dividends"].contributions], ["DIV-1"])
		self.assertEqual(result.p8b.holdings[0].result.holding, BETA)

	def test_the_trading_book_of_absatz_7_corrects_nothing(self):
		result = compute(
			inputs(
				credit("2625", "12000.00"),
				holdings=(HoldingResult(BETA, Decimal("12000.00")),),
				trading_book=True,
			),
			FIGURES,
		)
		self.assertEqual(result.lines["p8b_total"].declared, ZERO)


class DerivativesTest(TestCase):
	def test_adds_back_the_net_loss_of_the_termingeschaefte(self):
		result = compute(inputs(credit("2654", "40000.00", "T-1"), debit("2166", "55000.00", "T-2")), FIGURES)
		self.assertEqual(result.lines["derivatives_loss"].declared, Decimal("15000"))
		self.assertEqual(result.lines["derivatives_offset"].declared, ZERO)
		self.assertEqual([c.voucher for c in result.lines["derivatives_loss"].contributions], ["T-1", "T-2"])
		self.assertEqual(result.derivatives.remaining, Decimal("15000"))

	def test_sets_a_net_gain_against_the_carry_forward_of_the_pool(self):
		result = compute(
			inputs(credit("2654", "4000.00"), derivatives_carry_forward=Decimal("10000")), FIGURES
		)
		self.assertEqual(result.lines["derivatives_offset"].declared, Decimal("4000"))
		self.assertEqual(result.lines["business_income"].declared, ZERO)


class BusinessIncomeTest(TestCase):
	"""Anlage GK line 300: rule 8906062 adds the declared lines with their signs."""

	def test_adds_the_declared_lines_with_their_signs(self):
		result = compute(
			inputs(
				credit("8400", "100000.00"),
				debit("2200", "10000.00"),
				debit("4397", "200.00"),
				credit("2744", "5000.00"),
				credit("2747", "300.00"),
				debit("9970", "1000.00"),
				credit("9971", "1000.00"),
			),
			FIGURES,
		)
		self.assertEqual(result.lines["net_income"].declared, Decimal("95100"))
		self.assertEqual(result.lines["iab_deduction"].declared, Decimal("1000"))
		self.assertEqual(result.lines["investment_grant"].declared, Decimal("5000"))
		self.assertEqual(result.lines["tax_free"].declared, Decimal("300"))
		self.assertEqual(result.lines["business_income"].declared, Decimal("99000"))
		self.assertEqual(result.business_income, Decimal("99000"))

	def test_sums_the_rounded_lines_and_keeps_the_exact_sum_beside_them(self):
		result = compute(inputs(credit("8400", "1000.50"), debit("2200", "0.50")), FIGURES)
		self.assertEqual(result.lines["net_income"].declared, Decimal("1000"))
		self.assertEqual(result.lines["corporate_tax"].declared, Decimal("1"))
		line = result.lines["business_income"]
		self.assertEqual((line.exact, line.declared), (Decimal("1000.50"), Decimal("1001")))

	def test_the_later_steps_count_nothing_yet(self):
		mapping = replace(MAPPING, rules=(*MAPPING.rules, AccountRule("2650", Category.FUNDS)))
		result = compute(KstInputs(2026, (credit("2650", "700.00"),), mapping), FIGURES)
		line = result.lines["investment_funds"]
		self.assertEqual((line.exact, line.declared), (ZERO, ZERO))
		self.assertEqual(len(line.contributions), 1)
		self.assertEqual(result.business_income, Decimal("700"))

	def test_refuses_a_year_without_data(self):
		with self.assertRaises(ValueError):
			compute(KstInputs(2099, (), MAPPING), FIGURES)
