"""The balance sheet and the income statement of a size class from the balances of the books."""

import random
from decimal import Decimal
from unittest import TestCase

from steuerbote.hgb.schemes import Level, VermerkKind, balance_sheet_scheme
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import (
	Balance,
	Code,
	ProfitPresentation,
	RemainingTerm,
	Severity,
	build,
	entered,
	in_full_euros,
	ug_reserve_minimum,
)

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

SHORT = RemainingTerm.UP_TO_ONE_YEAR
# An invented GmbH: Stammkapital 25,000 €, a profit carried forward, one year of trade.
BOOKS = (
	Balance(BANK, Decimal("37929.50"), source="1200 Bank"),
	Balance(
		TRADE_RECEIVABLES,
		Decimal("5950.50"),
		remaining_term=SHORT,
		source="1400 Forderungen aus Lieferungen und Leistungen",
	),
	Balance(VAT_RECEIVABLE, Decimal("400.00"), remaining_term=SHORT, source="1576 Abziehbare Vorsteuer 19 %"),
	Balance(SUBSCRIBED, Decimal("-25000.00"), source="0800 Gezeichnetes Kapital"),
	Balance(CARRIED_FORWARD, Decimal("-3000.00"), source="0860 Gewinnvortrag vor Verwendung"),
	Balance(TAX_PROVISIONS, Decimal("-1500.00"), source="0963 Körperschaftsteuerrückstellung"),
	Balance(
		TRADE_PAYABLES,
		Decimal("-2380.00"),
		remaining_term=SHORT,
		source="1600 Verbindlichkeiten aus Lieferungen und Leistungen",
	),
	Balance(VAT_PAYABLE, Decimal("-1900.00"), remaining_term=SHORT, source="1776 Umsatzsteuer 19 %"),
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
	Balance(
		SHAREHOLDER_LOAN,
		Decimal("-40000.00"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		source="0755 Darlehen des Gesellschafters",
	),
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
			][:6],
			[
				("bs.eqLiab.equity", Decimal("0.00")),
				("bs.eqLiab.equity.subscribed", Decimal("25000.00")),
				("bs.eqLiab.equity.capRes", Decimal("0")),
				("bs.eqLiab.equity.retainedEarnings", Decimal("-30000.00")),
				("bs.eqLiab.equity.netIncome", Decimal("-5000.00")),
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


LOAN_RECEIVABLE = "bs.ass.currAss.receiv.other.loans"
SOCIAL_SECURITY = "bs.eqLiab.liab.other.thereoffSocSec"
PENSIONS = f"{GKV}.staff.social.pensions"
UNCALLED = "bs.eqLiab.equity.subscribed.unpaidCap"
VERMERK_PARENTS = {
	**PARENTS,
	LOAN_RECEIVABLE: "bs.ass.currAss.receiv.other",
	SOCIAL_SECURITY: "bs.eqLiab.liab.other",
	"bs.eqLiab.liab.other.other": "bs.eqLiab.liab.other",
	PENSIONS: f"{GKV}.staff.social",
	UNCALLED: "bs.eqLiab.equity.subscribed",
}
LONG = RemainingTerm.ONE_TO_FIVE_YEARS
# The invented GmbH of BOOKS with a loan to an employee, social security and a loan of its shareholder.
WITH_VERMERKE = (
	*BOOKS[:1],
	Balance(BANK, Decimal("-2830.00"), source="1210 Kontokorrent"),
	*BOOKS[1:],
	Balance(LOAN_RECEIVABLE, Decimal("3000.00"), remaining_term=LONG, source="1340 Darlehen an Mitarbeiter"),
	Balance(
		SOCIAL_SECURITY,
		Decimal("-870.00"),
		remaining_term=SHORT,
		source="1742 Verbindlichkeiten soziale Sicherheit",
	),
	Balance(
		SHAREHOLDER_LOAN,
		Decimal("-300.00"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		source="0755 Darlehen des Gesellschafters",
	),
	Balance(
		"bs.eqLiab.liab.other.other",
		Decimal("-100.00"),
		shareholder=True,
		remaining_term=SHORT,
		source="1755 Verrechnungskonto Gesellschafter",
	),
	Balance(PENSIONS, Decimal("1100.00"), source="4168 Aufwendungen für Altersversorgung"),
)


def vermerke(line) -> dict[VermerkKind, Decimal]:
	return {vermerk.vermerk.kind: vermerk.amount for vermerk in line.vermerke}


class VermerkAmountsTest(TestCase):
	"""The „davon“ amounts of § 268 Abs. 4 and 5 HGB, § 42 Abs. 3 GmbHG and § 266 Abs. 3 HGB."""

	def test_klein_notes_the_remaining_terms_and_the_shareholders_at_its_roman_numerals_and_letters(self):
		sheet = build(2026, SizeClass.KLEIN, WITH_VERMERKE, parents=VERMERK_PARENTS).balance_sheet
		self.assertEqual(
			vermerke(sheet.line("bs.ass.currAss.receiv")),
			{
				VermerkKind.RECEIVABLES_OVER_ONE_YEAR: Decimal("3000.00"),
				VermerkKind.SHAREHOLDERS: Decimal("0"),
			},
		)
		self.assertEqual(
			vermerke(sheet.line("bs.eqLiab.liab")),
			{
				VermerkKind.LIABILITIES_UP_TO_ONE_YEAR: Decimal("5250.00"),
				VermerkKind.LIABILITIES_OVER_ONE_YEAR: Decimal("300.00"),
				VermerkKind.SHAREHOLDERS: Decimal("400.00"),
			},
		)
		self.assertEqual(sheet.line("bs.eqLiab.liab").amount, Decimal("5550.00"))

	def test_kleinst_notes_the_receivables_at_the_umlaufvermoegen_and_counts_only_the_receivables(self):
		statement = build(2026, SizeClass.KLEINST, WITH_VERMERKE, parents=VERMERK_PARENTS)
		self.assertEqual(statement.findings, ())
		line = statement.balance_sheet.line("bs.ass.currAss")
		self.assertEqual(vermerke(line)[VermerkKind.RECEIVABLES_OVER_ONE_YEAR], Decimal("3000.00"))
		self.assertEqual(
			[vermerk.vermerk.label for vermerk in line.vermerke],
			[
				"davon Forderungen mit einer Restlaufzeit von mehr als einem Jahr",
				"davon Forderungen gegen Gesellschafter",
			],
		)

	def test_the_larger_classes_note_each_item(self):
		sheet = build(2026, SizeClass.GROSS, WITH_VERMERKE, parents=VERMERK_PARENTS).balance_sheet
		self.assertEqual(
			vermerke(sheet.line("bs.eqLiab.liab.other")),
			{
				VermerkKind.TAXES: Decimal("1900.00"),
				VermerkKind.SOCIAL_SECURITY: Decimal("870.00"),
				VermerkKind.LIABILITIES_UP_TO_ONE_YEAR: Decimal("2870.00"),
				VermerkKind.LIABILITIES_OVER_ONE_YEAR: Decimal("0"),
			},
		)
		self.assertEqual(
			vermerke(sheet.line(SHAREHOLDER_LOAN)),
			{
				VermerkKind.LIABILITIES_UP_TO_ONE_YEAR: Decimal("0"),
				VermerkKind.LIABILITIES_OVER_ONE_YEAR: Decimal("300.00"),
			},
		)
		self.assertEqual(
			vermerke(sheet.line("bs.ass.currAss.receiv.other"))[VermerkKind.RECEIVABLES_OVER_ONE_YEAR],
			Decimal("3000.00"),
		)

	def test_the_income_statement_notes_its_davon_amounts(self):
		income = build(2026, SizeClass.KLEIN, WITH_VERMERKE, parents=VERMERK_PARENTS).income_statement
		self.assertEqual(
			vermerke(income.line(f"{GKV}.staff.social")), {VermerkKind.PENSIONS: Decimal("1100.00")}
		)
		self.assertEqual(income.line(f"{GKV}.staff").amount, Decimal("37100.00"))

	def test_uncalled_capital_is_offset_and_leaves_the_eingefordertes_kapital(self):
		books = (
			*BOOKS,
			Balance(UNCALLED, Decimal("12500.00"), source="0820 Ausstehende Einlagen, nicht eingefordert"),
		)
		line = build(2026, SizeClass.KLEIN, books, parents=VERMERK_PARENTS).balance_sheet.line(
			"bs.eqLiab.equity.subscribed"
		)
		self.assertEqual(
			(line.label, line.amount, vermerke(line)),
			(
				"Eingefordertes Kapital",
				Decimal("12500.00"),
				{VermerkKind.UNCALLED_CAPITAL: Decimal("-12500.00")},
			),
		)
		plain = build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS).balance_sheet.line(
			"bs.eqLiab.equity.subscribed"
		)
		self.assertEqual(plain.label, "Gezeichnetes Kapital")


class RemainingTermFindingsTest(TestCase):
	def test_a_balance_without_a_remaining_term_where_the_class_notes_one_is_an_error(self):
		books = (
			*BOOKS,
			Balance(SHAREHOLDER_LOAN, Decimal("-500.00"), source="0755 Darlehen des Gesellschafters"),
		)
		statement = build(2026, SizeClass.KLEIN, books, parents=PARENTS)
		findings = [finding for finding in statement.findings if finding.code is Code.REMAINING_TERM_UNKNOWN]
		self.assertEqual(
			[(finding.severity, finding.concept, finding.amount, finding.reference) for finding in findings],
			[(Severity.ERROR, SHAREHOLDER_LOAN, Decimal("-500.00"), "§ 268 Abs. 5 Satz 1 HGB")],
		)
		self.assertIn("0755 Darlehen des Gesellschafters", findings[0].text)

	def test_names_a_receivable_without_a_remaining_term_once(self):
		books = (Balance(TRADE_RECEIVABLES, Decimal("10.00")), Balance(TRADE_RECEIVABLES, Decimal("0")))
		for size_class in SizeClass:
			with self.subTest(size_class=size_class):
				statement = build(2026, size_class, books)
				findings = [
					finding for finding in statement.findings if finding.code is Code.REMAINING_TERM_UNKNOWN
				]
				self.assertEqual([finding.reference for finding in findings], ["§ 268 Abs. 4 Satz 1 HGB"])


class UnitemizedTest(TestCase):
	def test_a_balance_a_class_shows_only_in_a_total_is_an_error(self):
		books = (*BOOKS, Balance("bs.eqLiab.equity", Decimal("-10.00"), source="0890 Eigenkapital"))
		klein = build(2026, SizeClass.KLEIN, books, parents=PARENTS)
		(finding,) = [finding for finding in klein.findings if finding.code is Code.UNITEMIZED]
		self.assertEqual(
			(finding.severity, finding.concept, finding.reference),
			(Severity.ERROR, "bs.eqLiab.equity", "§ 266 Abs. 1 Satz 3 HGB"),
		)

	def test_a_class_that_shows_no_position_under_it_takes_it(self):
		books = (*BOOKS, Balance("bs.eqLiab.equity", Decimal("-10.00")))
		kleinst = build(2026, SizeClass.KLEINST, books, parents=PARENTS)
		self.assertNotIn(Code.UNITEMIZED, [finding.code for finding in kleinst.findings])

	def test_so_does_an_item_of_the_income_statement_without_its_parts(self):
		books = (*BOOKS, Balance(f"{GKV}.staff", Decimal("10.00")))
		statement = build(2026, SizeClass.KLEIN, books, parents=PARENTS)
		(finding,) = [finding for finding in statement.findings if finding.code is Code.UNITEMIZED]
		self.assertEqual((finding.concept, finding.reference), (f"{GKV}.staff", "§ 275 Abs. 2 HGB"))


# The invented GmbH of BOOKS a year earlier, its founding year.
PRIOR_BOOKS = (
	Balance(BANK, Decimal("27000.00")),
	Balance(TRADE_RECEIVABLES, Decimal("3000.00"), remaining_term=SHORT),
	Balance(SUBSCRIBED, Decimal("-25000.00")),
	Balance(TAX_PROVISIONS, Decimal("-800.00")),
	Balance(TRADE_PAYABLES, Decimal("-1200.00"), remaining_term=SHORT),
	Balance(SALES_19, Decimal("-40000.00")),
	Balance(RENT, Decimal("12000.00")),
	Balance(MANAGER, Decimal("24200.00")),
	Balance(KST, Decimal("800.00")),
)


class PriorYearTest(TestCase):
	"""§ 265 Abs. 2 HGB: „zu jedem Posten der entsprechende Betrag des vorhergehenden Geschäftsjahrs“."""

	def setUp(self):
		self.statement = build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS, prior=PRIOR_BOOKS)
		self.sheet = self.statement.balance_sheet

	def test_each_line_carries_the_amount_of_the_previous_year(self):
		self.assertEqual(
			[(line.position.concept, line.amount, line.prior) for line in self.sheet.aktiva[4:9]],
			[
				("bs.ass.currAss", Decimal("44280.00"), Decimal("30000.00")),
				("bs.ass.currAss.inventory", Decimal("0"), Decimal("0")),
				("bs.ass.currAss.receiv", Decimal("6350.50"), Decimal("3000.00")),
				("bs.ass.currAss.securities", Decimal("0"), Decimal("0")),
				("bs.ass.currAss.cashEquiv", Decimal("37929.50"), Decimal("27000.00")),
			],
		)
		self.assertEqual(self.sheet.line("bs.eqLiab.equity.netIncome").prior, Decimal("3000.00"))
		self.assertEqual(self.statement.income_statement.line(SALES).prior, Decimal("40000.00"))

	def test_gives_the_totals_the_result_the_sales_and_the_bilanzsumme_of_the_previous_year(self):
		self.assertEqual(
			(self.sheet.prior_aktiva_total, self.sheet.prior_passiva_total, self.sheet.prior_bilanzsumme),
			(Decimal("30000.00"), Decimal("30000.00"), Decimal("30000.00")),
		)
		income = self.statement.income_statement
		self.assertEqual(
			(income.prior_net_income, income.prior_sales), (Decimal("3000.00"), Decimal("40000.00"))
		)

	def test_the_vermerke_carry_the_previous_year_too(self):
		vermerk = self.sheet.line("bs.eqLiab.liab").vermerke[0]
		self.assertEqual(
			(vermerk.vermerk.kind, vermerk.amount, vermerk.prior),
			(VermerkKind.LIABILITIES_UP_TO_ONE_YEAR, Decimal("4280.00"), Decimal("1200.00")),
		)

	def test_without_a_previous_year_no_line_has_one(self):
		statement = build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS)
		self.assertEqual({line.prior for line in statement.balance_sheet.aktiva}, {None})
		self.assertIsNone(statement.balance_sheet.prior_aktiva_total)
		self.assertIsNone(statement.income_statement.prior_net_income)
		self.assertEqual(
			{vermerk.prior for vermerk in statement.balance_sheet.line("bs.eqLiab.liab").vermerke}, {None}
		)

	def test_the_findings_of_the_previous_year_say_so(self):
		statement = build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS, prior=PRIOR_BOOKS[1:])
		(finding,) = statement.findings
		self.assertEqual((finding.code, finding.prior_year), (Code.NOT_BALANCED, True))
		self.assertTrue(finding.text.startswith("Vorjahr: "))
		self.assertFalse(any(finding.prior_year for finding in self.statement.findings))


class EnteredPriorYearTest(TestCase):
	"""The first Vorjahr is entered by hand from the last festgestellter Jahresabschluss."""

	def setUp(self):
		scheme = balance_sheet_scheme(2026)
		self.prior = (
			entered(scheme.position("bs.ass.currAss"), Decimal("30000.00")),
			entered(scheme.position("bs.eqLiab.equity"), Decimal("28000.00")),
			entered(scheme.position("bs.eqLiab.accruals"), Decimal("800.00")),
			entered(scheme.position("bs.eqLiab.liab"), Decimal("1200.00"), remaining_term=SHORT),
		)

	def test_turns_an_amount_of_a_position_into_a_balance_of_its_side(self):
		self.assertEqual(
			[(balance.concept, balance.amount, balance.source) for balance in self.prior],
			[
				("bs.ass.currAss", Decimal("30000.00"), "Vorjahr"),
				("bs.eqLiab.equity", Decimal("-28000.00"), "Vorjahr"),
				("bs.eqLiab.accruals", Decimal("-800.00"), "Vorjahr"),
				("bs.eqLiab.liab", Decimal("-1200.00"), "Vorjahr"),
			],
		)
		self.assertIs(self.prior[-1].remaining_term, SHORT)

	def test_a_kleinst_takes_its_previous_year_at_the_letters(self):
		statement = build(2026, SizeClass.KLEINST, BOOKS, parents=PARENTS, prior=self.prior)
		sheet = statement.balance_sheet
		self.assertEqual(sheet.line("bs.eqLiab.equity").prior, Decimal("28000.00"))
		self.assertEqual((sheet.prior_aktiva_total, sheet.prior_passiva_total), (Decimal("30000.00"),) * 2)
		self.assertEqual(statement.findings, ())

	def test_the_result_of_a_previous_year_entered_by_hand_comes_with_it(self):
		prior = (
			entered(balance_sheet_scheme(2026).position("bs.ass.currAss.cashEquiv"), Decimal("28000.00")),
			entered(balance_sheet_scheme(2026).position("bs.eqLiab.equity.subscribed"), Decimal("25000.00")),
		)
		statement = build(
			2026, SizeClass.KLEIN, BOOKS, parents=PARENTS, prior=prior, prior_net_income=Decimal("3000.00")
		)
		self.assertEqual(statement.balance_sheet.line("bs.eqLiab.equity.netIncome").prior, Decimal("3000.00"))
		self.assertEqual(statement.income_statement.prior_net_income, Decimal("3000.00"))
		self.assertEqual(statement.findings, ())


class ShownTest(TestCase):
	"""§ 265 Abs. 8 HGB: a position without an amount in either year need not be shown."""

	def test_a_line_without_an_amount_in_either_year_is_not_shown(self):
		sheet = build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS, prior=PRIOR_BOOKS).balance_sheet
		self.assertFalse(sheet.line("bs.ass.currAss.inventory").shown)
		self.assertTrue(sheet.line("bs.ass.currAss.receiv").shown)

	def test_a_line_with_an_amount_in_the_previous_year_only_is_shown(self):
		prior = (
			*PRIOR_BOOKS,
			Balance("bs.ass.prepaidExp", Decimal("100.00")),
			Balance(BANK, Decimal("-100.00")),
		)
		sheet = build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS, prior=prior).balance_sheet
		line = sheet.line("bs.ass.prepaidExp")
		self.assertEqual((line.amount, line.prior, line.shown), (Decimal("0"), Decimal("100.00"), True))

	def test_the_eigenkapital_and_the_gezeichnetes_kapital_are_always_shown(self):
		sheet = build(2026, SizeClass.KLEIN, ()).balance_sheet
		self.assertEqual(
			[line.position.concept for line in sheet.aktiva + sheet.passiva if line.shown],
			["bs.eqLiab.equity", "bs.eqLiab.equity.subscribed"],
		)

	def test_the_results_of_the_income_statement_are_always_shown(self):
		income = build(2026, SizeClass.KLEIN, ()).income_statement
		self.assertEqual(
			[line.position.concept for line in income.lines if line.shown],
			["is.netIncome.eat", "is.netIncome"],
		)

	def test_a_vermerk_without_an_amount_in_either_year_is_not_shown(self):
		sheet = build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS).balance_sheet
		self.assertEqual(
			[(vermerk.vermerk.kind, vermerk.shown) for vermerk in sheet.line("bs.eqLiab.liab").vermerke],
			[
				(VermerkKind.LIABILITIES_UP_TO_ONE_YEAR, True),
				(VermerkKind.LIABILITIES_OVER_ONE_YEAR, False),
				(VermerkKind.SHAREHOLDERS, False),
			],
		)


LEGAL_RESERVE = "bs.eqLiab.equity.revenueRes.legal"
BILANZGEWINN = "bs.eqLiab.equity.profitLoss"
AFTER = ProfitPresentation.AFTER_PARTIAL_APPROPRIATION
# The invented company of BOOKS as an UG that puts a quarter of its Jahresüberschuss into the gesetzliche Rücklage.
APPROPRIATED = (
	*BOOKS,
	Balance(LEGAL_RESERVE, Decimal("-2625.00"), source="0846 Gesetzliche Rücklage"),
	Balance(BILANZGEWINN, Decimal("2625.00"), source="2496 Einstellungen in die gesetzliche Rücklage"),
)


def concepts(lines) -> list[str]:
	return [line.position.concept for line in lines]


class ProfitPresentationTest(TestCase):
	"""§ 268 Abs. 1 HGB: after part of the result is appropriated, the Bilanzgewinn replaces IV. and V."""

	def test_before_the_appropriation_the_balance_sheet_shows_the_profit_carried_forward_and_the_result(self):
		sheet = build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS).balance_sheet
		self.assertIn(CARRIED_FORWARD, concepts(sheet.passiva))
		self.assertIn("bs.eqLiab.equity.netIncome", concepts(sheet.passiva))
		self.assertNotIn(BILANZGEWINN, concepts(sheet.passiva))

	def test_after_part_of_it_the_bilanzgewinn_takes_their_place(self):
		sheet = build(2026, SizeClass.KLEIN, APPROPRIATED, parents=PARENTS, presentation=AFTER).balance_sheet
		self.assertEqual(
			[(line.position.concept, line.position.marker, line.amount) for line in sheet.passiva[:6]],
			[
				("bs.eqLiab.equity", "A.", Decimal("38500.00")),
				("bs.eqLiab.equity.subscribed", "I.", Decimal("25000.00")),
				("bs.eqLiab.equity.capRes", "II.", Decimal("0")),
				("bs.eqLiab.equity.revenueRes", "III.", Decimal("2625.00")),
				(BILANZGEWINN, "IV.", Decimal("10875.00")),
				("bs.eqLiab.equity.deficitNotCoveredByCapital", "", Decimal("0")),
			],
		)

	def test_notes_the_profit_carried_forward_in_the_bilanzgewinn(self):
		sheet = build(
			2026, SizeClass.KLEIN, APPROPRIATED, parents=PARENTS, presentation=AFTER, prior=PRIOR_BOOKS
		)
		(vermerk,) = sheet.balance_sheet.line(BILANZGEWINN).vermerke
		self.assertEqual(
			(vermerk.vermerk.kind, vermerk.amount, vermerk.prior, vermerk.shown),
			(VermerkKind.PROFIT_CARRIED_FORWARD, Decimal("3000.00"), Decimal("0"), True),
		)
		self.assertEqual(sheet.balance_sheet.line(BILANZGEWINN).prior, Decimal("3000.00"))

	def test_a_bilanzgewinn_before_the_appropriation_is_an_error(self):
		statement = build(2026, SizeClass.KLEIN, APPROPRIATED, parents=PARENTS)
		(finding,) = [finding for finding in statement.findings if finding.code is Code.APPROPRIATION]
		self.assertEqual(
			(finding.severity, finding.concept, finding.amount, finding.reference),
			(Severity.ERROR, BILANZGEWINN, Decimal("2625.00"), "§ 268 Abs. 1 Satz 2 HGB"),
		)
		after = build(2026, SizeClass.KLEIN, APPROPRIATED, parents=PARENTS, presentation=AFTER)
		self.assertEqual(after.findings, ())
		empty = build(2026, SizeClass.KLEIN, (*BOOKS, Balance(BILANZGEWINN, Decimal("0"))), parents=PARENTS)
		self.assertEqual(empty.findings, ())

	def test_kleinst_shows_the_eigenkapital_alike_either_way(self):
		for presentation in ProfitPresentation:
			with self.subTest(presentation=presentation):
				sheet = build(
					2026, SizeClass.KLEINST, APPROPRIATED, parents=PARENTS, presentation=presentation
				).balance_sheet
				self.assertEqual(sheet.line("bs.eqLiab.equity").amount, Decimal("38500.00"))


class UgReserveTest(TestCase):
	"""§ 5a Abs. 3 Satz 1 GmbHG: a quarter of the Jahresüberschuss less a Verlustvortrag aus dem Vorjahr."""

	def test_takes_a_quarter_of_the_jahresueberschuss(self):
		self.assertEqual(ug_reserve_minimum(Decimal("10500.00"), Decimal("3000.00")), Decimal("2625.00"))

	def test_takes_the_verlustvortrag_off_first_and_rounds_up_to_the_cent(self):
		self.assertEqual(ug_reserve_minimum(Decimal("10000.01"), Decimal("-1000.00")), Decimal("2250.01"))

	def test_takes_nothing_from_a_jahresueberschuss_the_verlustvortrag_uses_up_or_from_a_jahresfehlbetrag(
		self,
	):
		self.assertEqual(ug_reserve_minimum(Decimal("800.00"), Decimal("-1000.00")), Decimal("0.00"))
		self.assertEqual(ug_reserve_minimum(Decimal("-500.00"), Decimal("4000.00")), Decimal("0.00"))


EURO = Decimal("1")


def whole(value: Decimal | None) -> bool:
	return value is None or value == value.quantize(EURO)


def visible_children(sheet, lines):
	"""Each line of a side with the lines right under it among those the class shows."""
	concepts = {line.position.concept for line in lines}
	children: dict[str, list] = {line.position.concept: [] for line in lines}
	for line in lines:
		parent = sheet.scheme.parent(line.position.concept)
		while parent is not None and parent.concept not in concepts:
			parent = sheet.scheme.parent(parent.concept)
		if parent is not None:
			children[parent.concept].append(line)
	return children


class FullEurosTest(TestCase):
	"""The Jahresabschluss of the Offenlegung in full euros, with every total still the sum of its lines."""

	def test_rounds_every_line_to_full_euros_and_keeps_the_sums(self):
		statement = in_full_euros(build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS))
		sheet = statement.balance_sheet
		self.assertEqual(
			[(line.position.concept, line.amount) for line in sheet.aktiva if line.amount],
			[
				("bs.ass.currAss", Decimal("44280")),
				("bs.ass.currAss.receiv", Decimal("6350")),
				("bs.ass.currAss.cashEquiv", Decimal("37930")),
			],
		)
		self.assertEqual((sheet.aktiva_total, sheet.passiva_total), (Decimal("44280"),) * 2)
		self.assertEqual(sheet.line("bs.eqLiab.equity.subscribed").amount, Decimal("25000"))

	def test_the_jahresueberschuss_of_both_statements_stays_the_same(self):
		books = (*BOOKS, Balance(SALES_19, Decimal("-0.40")), Balance(BANK, Decimal("0.40")))
		statement = in_full_euros(build(2026, SizeClass.KLEIN, books, parents=PARENTS))
		self.assertEqual(statement.income_statement.net_income, Decimal("10500"))
		self.assertEqual(statement.balance_sheet.line("bs.eqLiab.equity.netIncome").amount, Decimal("10500"))
		self.assertEqual(statement.income_statement.line(SALES).amount, Decimal("60000"))
		self.assertEqual(statement.income_statement.sales, Decimal("60000"))

	def test_rounds_the_vermerke_within_their_lines(self):
		books = (
			Balance(BANK, Decimal("2681.20")),
			Balance(TRADE_PAYABLES, Decimal("-2380.60"), remaining_term=SHORT),
			Balance(SHAREHOLDER_LOAN, Decimal("-300.60"), remaining_term=LONG),
		)
		line = in_full_euros(build(2026, SizeClass.KLEIN, books, parents=PARENTS)).balance_sheet.line(
			"bs.eqLiab.liab"
		)
		self.assertEqual(line.amount, Decimal("2681"))
		self.assertEqual(
			vermerke(line),
			{
				VermerkKind.LIABILITIES_UP_TO_ONE_YEAR: Decimal("2380"),
				VermerkKind.LIABILITIES_OVER_ONE_YEAR: Decimal("301"),
				VermerkKind.SHAREHOLDERS: Decimal("301"),
			},
		)

	def test_rounds_the_previous_year_and_the_figures_of_the_size_criteria_too(self):
		prior = (*PRIOR_BOOKS, Balance(BANK, Decimal("0.60")), Balance(SALES_19, Decimal("-0.60")))
		statement = in_full_euros(build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS, prior=prior))
		sheet, income = statement.balance_sheet, statement.income_statement
		self.assertEqual(sheet.line("bs.ass.currAss.cashEquiv").prior, Decimal("27001"))
		self.assertEqual(
			(sheet.prior_aktiva_total, sheet.prior_passiva_total, sheet.prior_bilanzsumme),
			(Decimal("30001"),) * 3,
		)
		self.assertEqual((income.prior_net_income, income.prior_sales), (Decimal("3001"), Decimal("40001")))
		self.assertEqual(
			(sheet.bilanzsumme, sheet.equity, sheet.deficit),
			(Decimal("44280"), Decimal("38500"), Decimal("0")),
		)

	def test_lets_the_fehlbetrag_go_where_a_side_cannot_keep_it_and_still_adds_up(self):
		books = (
			Balance(BANK, Decimal("-1.00")),
			Balance(CARRIED_FORWARD, Decimal("0.50")),
			Balance(TRADE_PAYABLES, Decimal("0.50"), remaining_term=SHORT),
		)
		sheet = in_full_euros(build(2026, SizeClass.KLEIN, books, parents=PARENTS)).balance_sheet
		letters = [line.amount for line in sheet.aktiva if line.position.level is Level.LETTER]
		self.assertEqual(sheet.aktiva_total, sum(letters))
		self.assertEqual(sheet.aktiva_total, sheet.passiva_total)

	def test_keeps_the_findings(self):
		books = (*BOOKS, Balance("bs.unknown.concept", Decimal("5.00")))
		statement = build(2026, SizeClass.KLEIN, books, parents=PARENTS)
		self.assertEqual(in_full_euros(statement).findings, statement.findings)

	def test_every_line_stays_within_a_euro_and_every_total_the_sum_of_its_lines(self):
		randomness = random.Random(20261231)  # noqa: S311 - invented books, repeatable, no secret
		for round_ in range(60):
			books = random_books(randomness)
			prior = random_books(randomness)
			for size_class in (SizeClass.KLEINST, SizeClass.KLEIN, SizeClass.GROSS):
				exact = build(2026, size_class, books, parents=VERMERK_PARENTS, prior=prior)
				rounded = in_full_euros(exact)
				with self.subTest(round=round_, size_class=size_class):
					self.check_full_euros(exact, rounded)

	def check_full_euros(self, exact, rounded):
		sheet = rounded.balance_sheet
		self.assertEqual(sheet.aktiva_total, sheet.passiva_total)
		self.assertEqual(sheet.prior_aktiva_total, sheet.prior_passiva_total)
		for exact_lines, lines in (
			(exact.balance_sheet.aktiva, sheet.aktiva),
			(exact.balance_sheet.passiva, sheet.passiva),
			(exact.income_statement.lines, rounded.income_statement.lines),
		):
			for before, after in zip(exact_lines, lines, strict=True):
				self.assertTrue(whole(after.amount) and whole(after.prior))
				self.assertLess(abs(after.amount - before.amount), EURO)
				self.assertLess(abs(after.prior - before.prior), EURO)
				for vermerk in after.vermerke:
					self.assertTrue(whole(vermerk.amount) and whole(vermerk.prior))
		for lines in (sheet.aktiva, sheet.passiva):
			for concept, children in visible_children(sheet, lines).items():
				if children:
					line = sheet.line(concept)
					self.assertEqual(line.amount, sum(child.amount for child in children))
					self.assertEqual(line.prior, sum(child.prior for child in children))
		income = rounded.income_statement
		self.assertEqual(income.line("is.netIncome").amount, income.net_income)
		self.assertEqual(
			income.net_income,
			income.line("is.netIncome.eat").amount - income.line("is.netIncome.otherTaxes").amount,
		)
		if sheet.size_class is not SizeClass.KLEINST:
			self.assertEqual(sheet.line("bs.eqLiab.equity.netIncome").amount, income.net_income)
			self.assertEqual(sheet.line("bs.eqLiab.equity.netIncome").prior, income.prior_net_income)


def random_books(randomness: random.Random) -> tuple[Balance, ...]:
	"""Invented books with cents everywhere that balance, as books do."""

	def cents(low: int, high: int) -> Decimal:
		return Decimal(randomness.randint(low * 100, high * 100)) / 100

	sales, rent, salaries, pensions = cents(10000, 90000), cents(0, 20000), cents(0, 50000), cents(0, 3000)
	receivables, loan, payables, social, other = (
		cents(0, 9000),
		cents(0, 5000),
		cents(0, 7000),
		cents(0, 2000),
		cents(0, 900),
	)
	net_income = sales - rent - salaries - pensions
	bank = Decimal("25000") + net_income + payables + social + other - receivables - loan
	return (
		Balance(BANK, bank),
		Balance(TRADE_RECEIVABLES, receivables, remaining_term=SHORT),
		Balance(LOAN_RECEIVABLE, loan, remaining_term=LONG),
		Balance(SUBSCRIBED, Decimal("-25000")),
		Balance(TRADE_PAYABLES, -payables, remaining_term=SHORT),
		Balance(SOCIAL_SECURITY, -social, remaining_term=SHORT),
		Balance("bs.eqLiab.liab.other.other", -other, shareholder=True, remaining_term=LONG),
		Balance(SALES_19, -sales),
		Balance(RENT, rent),
		Balance(MANAGER, salaries),
		Balance(PENSIONS, pensions),
	)


class SubscribedCapitalTest(TestCase):
	"""§ 272 Abs. 1 HGB: the Gezeichnetes Kapital at its Nennbetrag, before the uncalled contributions are offset."""

	def test_gives_the_gezeichnetes_kapital_of_every_class(self):
		books = (*BOOKS, Balance(UNCALLED, Decimal("12500.00")), Balance(BANK, Decimal("-12500.00")))
		for size_class in SizeClass:
			with self.subTest(size_class=size_class):
				sheet = build(
					2026, size_class, books, parents=VERMERK_PARENTS, prior=PRIOR_BOOKS
				).balance_sheet
				self.assertEqual(
					(sheet.subscribed_capital, sheet.prior_subscribed_capital),
					(Decimal("25000.00"), Decimal("25000.00")),
				)

	def test_has_none_of_a_previous_year_without_one(self):
		self.assertIsNone(
			build(2026, SizeClass.KLEIN, BOOKS, parents=PARENTS).balance_sheet.prior_subscribed_capital
		)

	def test_keeps_it_in_full_euros(self):
		sheet = in_full_euros(
			build(2026, SizeClass.KLEINST, BOOKS, parents=PARENTS, prior=PRIOR_BOOKS)
		).balance_sheet
		self.assertEqual((sheet.subscribed_capital, sheet.prior_subscribed_capital), (Decimal("25000"),) * 2)
