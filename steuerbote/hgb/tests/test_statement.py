"""The balance sheet and the income statement of a size class from the balances of the books."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import Balance, Code, Severity, build

GKV = "is.netIncome.regular.operatingTC"
SALES = f"{GKV}.grossTradingProfit.totalOutput.netSales"
SALES_19 = f"{SALES}.grossSales.generalRateVAT"
RENT = f"{GKV}.otherCost.leaseFix"
SALARIES = f"{GKV}.staff.salaries"
MANAGER = f"{SALARIES}.managerPartner"
INCOME_TAX = "is.netIncome.tax"
KST = "is.netIncome.tax.kst"
BANK = "bs.ass.currAss.cashEquiv.bank"
TRADE_RECEIVABLES = "bs.ass.currAss.receiv.trade"
VAT_RECEIVABLE = "bs.ass.currAss.receiv.other.vat"
SUBSCRIBED = "bs.eqLiab.equity.subscribed.corp"
CARRIED_FORWARD = "bs.eqLiab.equity.retainedEarnings"
TAX_PROVISIONS = "bs.eqLiab.accruals.tax"
TRADE_PAYABLES = "bs.eqLiab.liab.trade"
VAT_PAYABLE = "bs.eqLiab.liab.other.theroffTax.vat"

# An extract of the calculation linkbase of the HGB taxonomy 6.9: each concept with the one it adds up to.
PARENTS = {
	BANK: "bs.ass.currAss.cashEquiv",
	VAT_RECEIVABLE: "bs.ass.currAss.receiv.other",
	SUBSCRIBED: "bs.eqLiab.equity.subscribed",
	VAT_PAYABLE: "bs.eqLiab.liab.other.theroffTax",
	"bs.eqLiab.liab.other.theroffTax": "bs.eqLiab.liab.other",
	"bs.ass.other": "bs.ass",
	SALES_19: f"{SALES}.grossSales",
	f"{SALES}.grossSales": SALES,
	RENT: f"{GKV}.otherCost",
	MANAGER: SALARIES,
	KST: INCOME_TAX,
	f"{GKV}.cooperative.Refunds": GKV,
	GKV: "is.netIncome.eat",
}

# An invented GmbH: Stammkapital 25,000 €, a profit carried forward, one year of trade.
BOOKS = (
	Balance(BANK, Decimal("37929.50"), source="1200 Bank"),
	Balance(TRADE_RECEIVABLES, Decimal("5950.50"), source="1400 Forderungen aus Lieferungen und Leistungen"),
	Balance(VAT_RECEIVABLE, Decimal("400.00"), source="1576 Abziehbare Vorsteuer 19 %"),
	Balance(SUBSCRIBED, Decimal("-25000.00"), source="0800 Gezeichnetes Kapital"),
	Balance(CARRIED_FORWARD, Decimal("-3000.00"), source="0860 Gewinnvortrag vor Verwendung"),
	Balance(TAX_PROVISIONS, Decimal("-1500.00"), source="0963 Körperschaftsteuerrückstellung"),
	Balance(
		TRADE_PAYABLES, Decimal("-2380.00"), source="1600 Verbindlichkeiten aus Lieferungen und Leistungen"
	),
	Balance(VAT_PAYABLE, Decimal("-1900.00"), source="1776 Umsatzsteuer 19 %"),
	Balance(SALES_19, Decimal("-60000.00"), source="8400 Erlöse 19 % USt"),
	Balance(RENT, Decimal("12000.00"), source="4210 Miete"),
	Balance(MANAGER, Decimal("36000.00"), source="4124 Geschäftsführergehälter der GmbH-Gesellschafter"),
	Balance(KST, Decimal("1500.00"), source="2200 Körperschaftsteuer"),
)


def amounts(lines) -> dict[str, Decimal]:
	return {line.position.concept: line.amount for line in lines}


class BalanceTest(TestCase):
	def test_takes_a_decimal_amount(self):
		with self.assertRaises(TypeError):
			Balance(BANK, 100.0)  # type: ignore[arg-type]

	def test_is_neither_a_shareholder_balance_nor_one_with_a_remaining_term_unless_flagged(self):
		balance = Balance(BANK, Decimal("1"))
		self.assertEqual((balance.shareholder, balance.remaining_term, balance.source), (False, None, ""))


class AggregationTest(TestCase):
	"""Each balance lands on the nearest position above its concept and adds up in the direction of the position."""

	def setUp(self):
		self.statement = build(2026, SizeClass.GROSS, BOOKS, parents=PARENTS)
		self.balance_sheet = amounts(
			self.statement.balance_sheet.aktiva + self.statement.balance_sheet.passiva
		)
		self.income = amounts(self.statement.income_statement.lines)

	def test_a_balance_on_the_concept_of_a_position_lands_on_it(self):
		self.assertEqual(self.balance_sheet[TRADE_RECEIVABLES], Decimal("5950.50"))
		self.assertEqual(self.balance_sheet[TAX_PROVISIONS], Decimal("1500.00"))

	def test_a_balance_below_a_position_adds_up_through_the_taxonomy(self):
		self.assertEqual(self.balance_sheet["bs.ass.currAss.cashEquiv"], Decimal("37929.50"))
		self.assertEqual(self.balance_sheet["bs.ass.currAss.receiv.other"], Decimal("400.00"))
		self.assertEqual(self.balance_sheet["bs.eqLiab.liab.other"], Decimal("1900.00"))
		self.assertEqual(self.balance_sheet["bs.eqLiab.equity.subscribed"], Decimal("25000.00"))

	def test_a_position_adds_up_the_positions_under_it(self):
		self.assertEqual(self.balance_sheet["bs.ass.currAss.receiv"], Decimal("6350.50"))
		self.assertEqual(self.balance_sheet["bs.ass.currAss"], Decimal("44280.00"))
		self.assertEqual(self.balance_sheet["bs.eqLiab.liab"], Decimal("4280.00"))

	def test_assets_and_expenses_count_debit_balances_positive_the_rest_credit_balances(self):
		self.assertEqual(self.income[SALES], Decimal("60000.00"))
		self.assertEqual(self.income[f"{GKV}.otherCost"], Decimal("12000.00"))
		self.assertEqual(self.income[SALARIES], Decimal("36000.00"))
		self.assertEqual(self.income[f"{GKV}.staff"], Decimal("36000.00"))
		self.assertEqual(self.income[INCOME_TAX], Decimal("1500.00"))

	def test_a_balance_on_the_other_side_of_its_position_counts_negative(self):
		statement = build(2026, SizeClass.KLEIN, (Balance(BANK, Decimal("-120.00")),), parents=PARENTS)
		self.assertEqual(
			amounts(statement.balance_sheet.aktiva)["bs.ass.currAss.cashEquiv"], Decimal("-120.00")
		)

	def test_the_results_add_up_the_items_above_them_with_their_signs(self):
		self.assertEqual(self.income["is.netIncome.eat"], Decimal("10500.00"))
		self.assertEqual(self.income["is.netIncome"], Decimal("10500.00"))
		self.assertEqual(self.statement.income_statement.net_income, Decimal("10500.00"))

	def test_a_class_has_the_lines_of_its_positions(self):
		klein = build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS).balance_sheet
		self.assertNotIn(TRADE_RECEIVABLES, amounts(klein.aktiva))
		self.assertEqual(amounts(klein.aktiva)["bs.ass.currAss.receiv"], Decimal("6350.50"))
		kleinst = build(2026, SizeClass.KLEINST, BOOKS, parents=PARENTS).balance_sheet
		self.assertEqual(
			list(amounts(kleinst.aktiva)),
			[
				"bs.ass.fixAss",
				"bs.ass.currAss",
				"bs.ass.prepaidExp",
				"bs.ass.defTax",
				"bs.ass.SurplusFromOffsetting",
				"bs.ass.deficitNotCoveredByCapital",
			],
		)

	def test_a_line_names_the_accounts_behind_it(self):
		lines = {line.position.concept: line for line in self.statement.balance_sheet.passiva}
		self.assertEqual(lines["bs.eqLiab.liab.other"].sources, ("1776 Umsatzsteuer 19 %",))
		self.assertEqual(lines["bs.eqLiab.liab"].sources, ())

	def test_the_books_of_the_example_raise_no_finding(self):
		self.assertEqual(
			[
				finding
				for finding in self.statement.findings
				if finding.code in (Code.UNPLACED, Code.COMPUTED)
			],
			[],
		)


class PlacementFindingsTest(TestCase):
	def test_a_balance_without_a_position_above_it_is_an_error(self):
		statement = build(
			2026,
			SizeClass.KLEIN,
			(Balance("bs.unknown.concept", Decimal("5.00"), source="9999 Neu"),),
			parents=PARENTS,
		)
		(finding,) = statement.findings
		self.assertEqual(
			(finding.code, finding.severity, finding.concept, finding.amount),
			(Code.UNPLACED, Severity.ERROR, "bs.unknown.concept", Decimal("5.00")),
		)
		self.assertIn("9999 Neu", finding.text)
		self.assertTrue(finding.blocking)

	def test_a_balance_on_a_position_the_statement_computes_is_an_error(self):
		for concept in (
			"bs.ass.other",
			"bs.eqLiab.equity.netIncome",
			f"{GKV}.cooperative.Refunds",
			"is.netIncome.eat",
		):
			with self.subTest(concept=concept):
				statement = build(
					2026, SizeClass.KLEIN, (Balance(concept, Decimal("1.00")),), parents=PARENTS
				)
				self.assertEqual([finding.code for finding in statement.findings], [Code.COMPUTED])

	def test_a_davon_concept_the_hierarchy_leaves_out_lands_on_the_position_of_its_vermerk(self):
		statement = build(
			2026, SizeClass.GROSS, (Balance("bs.eqLiab.liab.securities.convertible", Decimal("-10")),)
		)
		self.assertEqual(amounts(statement.balance_sheet.passiva)["bs.eqLiab.liab.securities"], Decimal("10"))

	def test_a_cycle_in_the_hierarchy_leaves_the_balance_without_a_position(self):
		statement = build(
			2026, SizeClass.KLEIN, (Balance("x.a", Decimal("1")),), parents={"x.a": "x.b", "x.b": "x.a"}
		)
		self.assertEqual([finding.code for finding in statement.findings], [Code.UNPLACED])

	def test_cites_the_schemes_in_each_finding(self):
		statement = build(
			2026, SizeClass.KLEIN, (Balance("x.a", Decimal("1")), Balance("bs.ass", Decimal("1")))
		)
		self.assertEqual(
			[finding.reference for finding in statement.findings], ["§§ 266, 275 HGB", "§§ 266, 275 HGB"]
		)


class TotalsTest(TestCase):
	def setUp(self):
		self.statement = build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS)
		self.sheet = self.statement.balance_sheet

	def test_the_balance_sheet_takes_the_jahresueberschuss_of_the_income_statement(self):
		self.assertEqual(self.sheet.line("bs.eqLiab.equity.netIncome").amount, Decimal("10500.00"))
		self.assertEqual(self.sheet.line("bs.eqLiab.equity").amount, Decimal("38500.00"))
		self.assertEqual(self.sheet.equity, Decimal("38500.00"))

	def test_both_sides_add_up_to_the_same_total(self):
		self.assertEqual(
			(self.sheet.aktiva_total, self.sheet.passiva_total, self.sheet.difference),
			(Decimal("44280.00"), Decimal("44280.00"), Decimal("0")),
		)
		self.assertEqual(self.statement.findings, ())

	def test_books_that_do_not_balance_hold_the_statement_back(self):
		statement = build(2026, SizeClass.KLEIN, BOOKS[1:], parents=PARENTS)
		(finding,) = statement.findings
		self.assertEqual(
			(finding.code, finding.severity, finding.amount, finding.reference),
			(
				Code.NOT_BALANCED,
				Severity.ERROR,
				Decimal("-37929.50"),
				"§ 242 Abs. 1, § 266 Abs. 1 Satz 1 HGB",
			),
		)
		self.assertEqual(statement.balance_sheet.difference, Decimal("-37929.50"))

	def test_gives_the_bilanzsumme_and_the_umsatzerloese_of_the_size_criteria(self):
		self.assertEqual(self.sheet.bilanzsumme, Decimal("44280.00"))
		self.assertEqual(self.statement.income_statement.sales, Decimal("60000.00"))

	def test_finds_a_line_by_the_concept_of_its_position(self):
		self.assertEqual(self.sheet.line("bs.ass.currAss.receiv").amount, Decimal("6350.50"))
		self.assertEqual(self.statement.income_statement.line(SALARIES).amount, Decimal("36000.00"))
		with self.assertRaises(KeyError):
			self.sheet.line(TRADE_RECEIVABLES)


SHAREHOLDER_LOAN = "bs.eqLiab.liab.shareholders"
# An invented GmbH whose losses have used up its Eigenkapital, financed by a loan of its shareholder.
LOSSES = (
	Balance(BANK, Decimal("30000.00"), source="1200 Bank"),
	Balance(SUBSCRIBED, Decimal("-25000.00"), source="0800 Gezeichnetes Kapital"),
	Balance(CARRIED_FORWARD, Decimal("30000.00"), source="0868 Verlustvortrag vor Verwendung"),
	Balance(SHAREHOLDER_LOAN, Decimal("-40000.00"), source="0755 Darlehen des Gesellschafters"),
	Balance(RENT, Decimal("5000.00"), source="4210 Miete"),
)


class DeficitTest(TestCase):
	"""§ 268 Abs. 3 HGB: an Eigenkapital used up by losses shows as a Fehlbetrag at the end of the Aktiva."""

	def setUp(self):
		self.sheet = build(2026, SizeClass.KLEIN, LOSSES, parents=PARENTS).balance_sheet

	def test_shows_the_excess_of_the_passiva_as_a_fehlbetrag_at_the_end_of_the_aktiva(self):
		self.assertEqual(self.sheet.aktiva[-1].position.concept, "bs.ass.deficitNotCoveredByCapital")
		self.assertEqual(self.sheet.aktiva[-1].amount, Decimal("10000.00"))
		self.assertEqual(self.sheet.deficit, Decimal("10000.00"))

	def test_brings_the_eigenkapital_to_zero_with_the_same_amount(self):
		self.assertEqual(
			[
				(line.position.concept, line.amount)
				for line in self.sheet.passiva
				if line.position.marker != "III."
			][:7],
			[
				("bs.eqLiab.equity", Decimal("0.00")),
				("bs.eqLiab.equity.subscribed", Decimal("25000.00")),
				("bs.eqLiab.equity.capRes", Decimal("0")),
				("bs.eqLiab.equity.retainedEarnings", Decimal("-30000.00")),
				("bs.eqLiab.equity.netIncome", Decimal("-5000.00")),
				("bs.eqLiab.equity.profitLoss", Decimal("0")),
				("bs.eqLiab.equity.deficitNotCoveredByCapital", Decimal("10000.00")),
			],
		)
		self.assertEqual(self.sheet.equity, Decimal("0"))

	def test_both_sides_rise_by_the_fehlbetrag(self):
		self.assertEqual((self.sheet.aktiva_total, self.sheet.passiva_total), (Decimal("40000.00"),) * 2)

	def test_leaves_the_fehlbetrag_out_of_the_bilanzsumme_of_the_size_criteria(self):
		self.assertEqual(self.sheet.bilanzsumme, Decimal("30000.00"), "§ 267 Abs. 4a Satz 2 HGB")

	def test_kleinst_shows_an_eigenkapital_of_zero(self):
		sheet = build(2026, SizeClass.KLEINST, LOSSES, parents=PARENTS).balance_sheet
		self.assertEqual(sheet.line("bs.eqLiab.equity").amount, Decimal("0"))
		self.assertEqual(sheet.line("bs.ass.deficitNotCoveredByCapital").amount, Decimal("10000.00"))

	def test_a_positive_eigenkapital_leaves_no_fehlbetrag(self):
		sheet = build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS).balance_sheet
		self.assertEqual(sheet.deficit, Decimal("0"))
		self.assertEqual(sheet.line("bs.eqLiab.equity.deficitNotCoveredByCapital").amount, Decimal("0"))
