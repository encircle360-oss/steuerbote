"""The checks of the Bilanzzuordnung against the HGB-Taxonomie 6.9 of esteuer.de (steuerbote/xbrl/tests/real.py)."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.hgb.statement import RemainingTerm
from steuerbote.xbrl import mapping
from steuerbote.xbrl.mapping import Mapping, Part, Rule
from steuerbote.xbrl.tests import real

GROSS_SALES = "is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales"
LIMITED_DEDUCTIBLE = "is.netIncome.regular.operatingTC.otherCost.limitedDeductible"
SAMPLE = (
	("0135", "bs.ass.fixAss.intan.concessionBrands", None, Part.BALANCE_SHEET),
	("0520", "bs.ass.fixAss.tan.otherEquipm.passengerCars", None, Part.BALANCE_SHEET),
	("0670", "bs.ass.fixAss.tan.otherEquipm.gwg", None, Part.BALANCE_SHEET),
	("0675", "bs.ass.fixAss.tan.otherEquipm.gwgsammelposten", None, Part.BALANCE_SHEET),
	("1600", "bs.ass.currAss.cashEquiv.cash", None, Part.BALANCE_SHEET),
	("1800", "bs.ass.currAss.cashEquiv.bank", "bs.eqLiab.liab.bank.other", Part.BALANCE_SHEET),
	("1200", "bs.ass.currAss.receiv.trade.other", None, Part.BALANCE_SHEET),
	("1406", "bs.ass.currAss.receiv.other.vat", None, Part.BALANCE_SHEET),
	("2900", "bs.eqLiab.equity.subscribed.corp", None, Part.BALANCE_SHEET),
	("2970", "bs.eqLiab.equity.retainedEarnings", None, Part.BALANCE_SHEET),
	("3035", "bs.eqLiab.accruals.tax.gewst", None, Part.BALANCE_SHEET),
	("3040", "bs.eqLiab.accruals.tax.kst", None, Part.BALANCE_SHEET),
	("3095", "bs.eqLiab.accruals.other", None, Part.BALANCE_SHEET),
	("3300", "bs.eqLiab.liab.trade.genOther", None, Part.BALANCE_SHEET),
	("3510", "bs.eqLiab.liab.shareholders.gmbh", None, Part.BALANCE_SHEET),
	("3806", "bs.eqLiab.liab.other.theroffTax", None, Part.BALANCE_SHEET),
	("4400", f"{GROSS_SALES}.generalRateVAT", None, Part.INCOME_STATEMENT),
	("4125", f"{GROSS_SALES}.taxExemptUStG4_1b", None, Part.INCOME_STATEMENT),
	("4338", f"{GROSS_SALES}.untaxable", None, Part.INCOME_STATEMENT),
	("6024", "is.netIncome.regular.operatingTC.staff.salaries.managerPartner", None, Part.INCOME_STATEMENT),
	("6027", "is.netIncome.regular.operatingTC.staff.salaries.misc", None, Part.INCOME_STATEMENT),
	("6640", f"{LIMITED_DEDUCTIBLE}.entertainment.deductible", None, Part.INCOME_STATEMENT),
	("6644", f"{LIMITED_DEDUCTIBLE}.entertainment.nonDeductible", None, Part.INCOME_STATEMENT),
	("6610", f"{LIMITED_DEDUCTIBLE}.gifts.deductible", None, Part.INCOME_STATEMENT),
	("6620", f"{LIMITED_DEDUCTIBLE}.gifts.nondeductible", None, Part.INCOME_STATEMENT),
	("7600", "is.netIncome.tax.kst", None, Part.INCOME_STATEMENT),
	("7610", "is.netIncome.tax.gewst", None, Part.INCOME_STATEMENT),
	("6220", "is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.other", None, Part.INCOME_STATEMENT),
	("6260", "is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.lowValueAs", None, Part.INCOME_STATEMENT),
	("6310", "is.netIncome.regular.operatingTC.otherCost.leaseFix.other", None, Part.INCOME_STATEMENT),
	("6315", "is.netIncome.regular.operatingTC.otherCost.leaseFix.shareholders", None, Part.INCOME_STATEMENT),
)
"""SKR04 accounts with the positions the research on the E-Bilanz proposes for them as a pattern of the defaults
(stufe3-research-ebilanz.md, 3.3, after the DATEV-Kontenrahmen „Gültig für 2026“ and the taxonomy 6.9); 6315 stands for
the rent paid to a shareholder."""


class SamplePositionsTest(TestCase):
	def test_the_positions_of_the_pattern_pass_the_checks_of_the_mapping(self):
		sample = Mapping(
			"SKR04", rules=[Rule(number, concept, opposite) for number, concept, opposite, _part in SAMPLE]
		)
		parts = {number: part for number, _concept, _opposite, part in SAMPLE}
		self.assertEqual(
			[problem.message for problem in mapping.check(sample, real.view(), parts)],
			[],
		)

	def test_the_bank_with_a_credit_balance_goes_to_the_verbindlichkeiten_gegenueber_kreditinstituten(self):
		taxonomy = real.view()
		self.assertEqual(mapping.part_of(taxonomy, "bs.eqLiab.liab.bank.other"), Part.BALANCE_SHEET)
		self.assertNotEqual(
			taxonomy.concept("bs.ass.currAss.cashEquiv.bank").balance,
			taxonomy.concept("bs.eqLiab.liab.bank.other").balance,
		)

	def test_the_remaining_terms_and_shareholders_go_with_forderungen_and_verbindlichkeiten(self):
		rules = [
			Rule("1200", "bs.ass.currAss.receiv.trade.other", remaining_term=RemainingTerm.OVER_FIVE_YEARS),
			Rule("3300", "bs.eqLiab.liab.trade.genOther", remaining_term=RemainingTerm.UP_TO_ONE_YEAR),
			Rule("3510", "bs.eqLiab.liab.shareholders.gmbh", shareholder=True),
			Rule("0880", "bs.ass.fixAss.fin.loansToSharehold", shareholder=True),
			Rule("0960", "bs.ass.fixAss.fin.otherLoans", shareholder=True),
		]
		self.assertEqual(mapping.check(Mapping("SKR04", rules=rules), real.view()), ())
		self.assertEqual(
			[
				problem.refusal
				for problem in mapping.check(
					Mapping(
						"SKR04",
						rules=[
							Rule("2900", "bs.eqLiab.equity.subscribed.corp", shareholder=True),
							Rule(
								"1800",
								"bs.ass.currAss.cashEquiv.bank",
								remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
							),
						],
					),
					real.view(),
				)
			],
			[mapping.SHAREHOLDER, mapping.REMAINING_TERM],
		)

	def test_refuses_the_positions_a_gmbh_does_not_report(self):
		"""Positions of a partnership and of the Umsatzkostenverfahren, abstract and non-monetary ones and those outside
		the Bilanz and the GuV, as the taxonomy 6.9 marks them."""
		cases = {
			"bs.eqLiab.equity.subscribed.limitedLiablePartners": mapping.LEGAL_FORM,
			"is.netIncome.regular.operatingCOGS.grossOpProfit.netSales": mapping.COST_OF_SALES,
			"bs": mapping.ABSTRACT,
			"bs.eqLiab.equity.capIncreaseContributionsInclPremium.dateHR": mapping.NOT_MONETARY,
			"BVV.profitLoss": mapping.NOT_A_STATEMENT_POSITION,
		}
		for concept, refusal in cases.items():
			with self.subTest(concept=concept):
				(problem,) = mapping.check(Mapping("SKR04", rules=[Rule("9999", concept)]), real.view())
				self.assertEqual(problem.refusal, refusal)


class PlacementTest(TestCase):
	def test_a_davon_position_counts_in_the_position_above_it(self):
		"""The Restlaufzeiten of the Verbindlichkeiten gegenüber Kreditinstituten and the interest from affiliated
		companies are „davon“ positions outside the calculation of the taxonomy 6.9."""
		taxonomy = real.view()
		self.assertEqual(
			mapping.position_of(taxonomy, "bs.eqLiab.liab.bank.upTo1year"), "bs.eqLiab.liab.bank"
		)
		self.assertEqual(
			mapping.position_of(taxonomy, "is.netIncome.regular.fin.netInterest.income.assoc"),
			"is.netIncome.regular.fin.netInterest.income",
		)
		self.assertEqual(
			mapping.position_of(taxonomy, "bs.eqLiab.liab.bank.other"), "bs.eqLiab.liab.bank.other"
		)

	def test_the_auffangpositionen_are_those_the_label_marks(self):
		"""„erkennbar durch die Formulierungen im beschreibenden Text „nicht zuordenbar“ oder „ohne Zuordnung““
		(Leitfaden A.10.4); a definitionGuidance that names them marks no position."""
		taxonomy = real.view()
		for concept, expected in (
			("bs.ass.currAss.receiv.other.misc", True),
			("bs.eqLiab.liab.trade.misc", True),
			(f"{GROSS_SALES}.unknownVAT", True),
			("bs.ass.fixAss.tan.other", False),
			("bs.ass.currAss.cashEquiv.bank", False),
		):
			with self.subTest(concept=concept):
				self.assertEqual(mapping.catch_all(taxonomy, concept), expected)


CURRENCY_LOSS = "is.netIncome.regular.operatingTC.otherCost.currLoss"
CURRENCY_GAINS = "is.netIncome.regular.operatingTC.otherOpRevenue.currGains"


class CurrencyTest(TestCase):
	"""Erträge und Aufwendungen aus der Währungsumrechnung stand apart in the GuV (§ 277 Abs. 5 Satz 2 HGB), and § 246
	Abs. 2 Satz 1 HGB forbids netting them; ERPNext's Wechselkursneubewertung books both onto one account."""

	def place(self, *balances: mapping.AccountBalance) -> mapping.Placement:
		rules = (
			Rule("6880", CURRENCY_LOSS, opposite=CURRENCY_GAINS),
			Rule("4840", CURRENCY_GAINS, opposite=CURRENCY_LOSS),
		)
		return mapping.place(
			Mapping("SKR04", rules=rules), mapping.Books(balances), real.view(), mapping.Purpose.BOTH
		)

	def balance(self, number: str, debit: str, credit: str) -> mapping.AccountBalance:
		return mapping.AccountBalance(
			number, number, number, Part.INCOME_STATEMENT, Decimal(debit), Decimal(credit)
		)

	def test_an_account_with_gains_and_losses_of_the_year_gets_a_hint(self):
		placement = self.place(self.balance("6880", "300.00", "1000.00"), self.balance("4840", "0", "50.00"))
		(found,) = [finding for finding in placement.findings if finding.code == mapping.Code.CURRENCY_NETTED]
		self.assertEqual(found.severity, mapping.Severity.HINT)
		self.assertEqual(
			found.text,
			"Konto 6880 bucht im Jahr Erträge und Aufwendungen aus der Währungsumrechnung (Haben 1.000,00 €, Soll "
			"300,00 €) und zeigt nur ihren Saldo von 700,00 €. Die GuV weist beide gesondert aus (§ 277 Abs. 5 Satz 2 "
			"HGB), verrechnet werden dürfen sie nicht (§ 246 Abs. 2 Satz 1 HGB): Buchen Sie Erträge und Aufwendungen "
			"aus der Währungsumrechnung auf getrennte Konten, auch wo die Wechselkursneubewertung von ERPNext beide auf "
			"ein Konto bucht.",
		)
		(gain,) = [item for item in placement.placed if item.balance.number == "6880"]
		self.assertEqual(gain.concept, CURRENCY_GAINS)

	def test_an_account_of_one_direction_gets_none(self):
		placement = self.place(self.balance("6880", "300.00", "0"), self.balance("4840", "0", "50.00"))
		self.assertNotIn(mapping.Code.CURRENCY_NETTED, [finding.code for finding in placement.findings])
