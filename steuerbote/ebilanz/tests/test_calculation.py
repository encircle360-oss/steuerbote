"""The amounts of the E-Bilanz of an invented GmbH from the balances of its books, on the mini taxonomy: signs, sums,
the Jahresüberschuss of the Bilanz, refused balances, corrections, lines by hand, the previous year of a Handelsbilanz
and the Betriebsvermögensvergleich."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.ebilanz.calculation import (
	AccountBalance,
	Adjustment,
	EquityChanges,
	betriebsvermoegensvergleich,
	calculate,
)
from steuerbote.ebilanz.positions import Case, structure
from steuerbote.ebilanz.tests.taxonomy import gaap, view
from steuerbote.xbrl.facts import Period, Periods

D = Decimal
YEAR = Periods(date(2026, 1, 1), date(2026, 12, 31))
WITH_PRIOR = Periods(date(2026, 1, 1), date(2026, 12, 31), None, date(2025, 1, 1), date(2025, 12, 31))
AT, OVER = Period.STICHTAG, Period.WIRTSCHAFTSJAHR

# An invented GmbH in its second year: software, land, a bank account, its Stammkapital and Gewinnvortrag, a loan, a
# Rückstellung, sales with an Erlösschmälerung, the cost of goods and the Körperschaftsteuer. Each balance is debit
# minus credit, as the books give it.
BOOKS = (
	AccountBalance("0135", "EDV-Software", "bs.ass.fixAss.intan.concessionBrands", D("12000.00")),
	AccountBalance("0215", "Unbebaute Grundstücke", "bs.ass.fixAss.tan", D("30000.00")),
	AccountBalance("1800", "Bank", "bs.ass.currAss.cashEquiv.bank", D("68500.00")),
	AccountBalance("2900", "Gezeichnetes Kapital", "bs.eqLiab.equity.subscribed.corp", D("-25000.00")),
	AccountBalance(
		"2970", "Gewinnvortrag vor Verwendung", "bs.eqLiab.equity.retainedEarnings", D("-2500.00")
	),
	AccountBalance(
		"3150", "Verbindlichkeiten gegenüber Kreditinstituten", "bs.eqLiab.liab.bank", D("-40000.00")
	),
	AccountBalance("3070", "Sonstige Rückstellungen", "bs.eqLiab.accruals.other", D("-3000.00")),
	AccountBalance("4400", "Erlöse 19 % USt", "is.netIncome.netSales", D("-120000.00")),
	AccountBalance("4700", "Erlösschmälerungen", "is.netIncome.netSales", D("1000.00")),
	AccountBalance("5400", "Wareneingang 19 % Vorsteuer", "is.netIncome.materialServices", D("70000.00")),
	AccountBalance("7600", "Körperschaftsteuer", "is.netIncome.tax", D("9000.00")),
)


def case(**fields) -> Case:
	return Case(**{"legal_form": "GmbH", "periods": YEAR, **fields})


def of(*balances, adjustments=(), **fields):
	return calculate(structure(view(), case(**fields)), balances, adjustments)


def codes(found) -> list[str]:
	return [finding.code for finding in found.findings]


class SignsAndSumsTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.found = of(*BOOKS)

	def test_a_balance_counts_in_the_direction_of_its_position(self):
		"""Leitfaden A.13: an Erlösschmälerung on a debit account counts against the Umsatzerlöse, a credit position."""
		self.assertEqual(self.found.amount("is.netIncome.netSales"), D("119000.00"))
		self.assertEqual(self.found.amount("bs.eqLiab.equity.subscribed.corp"), D("25000.00"))
		self.assertEqual(self.found.amount("bs.ass.currAss.cashEquiv.bank"), D("68500.00"))
		lines = {line.account: line for line in self.found.lines}
		self.assertEqual(
			(lines["4700"].concept, lines["4700"].amount), (gaap("is.netIncome.netSales"), D("-1000.00"))
		)
		self.assertEqual(lines["2900"].amount, D("25000.00"))

	def test_totals_follow_the_calculation_linkbase_with_its_weights(self):
		expected = {
			"bs.ass.fixAss.intan": "12000.00",
			"bs.ass.fixAss": "42000.00",
			"bs.ass.currAss": "68500.00",
			"bs.ass": "110500.00",
			"bs.eqLiab.equity": "67500.00",
			"bs.eqLiab.liab": "40000.00",
			"bs.eqLiab.accruals": "3000.00",
			"bs.eqLiab": "110500.00",
			"is.netIncome": "40000.00",
		}
		for name, value in expected.items():
			with self.subTest(name=name):
				self.assertEqual(self.found.amount(name), D(value))

	def test_the_bilanz_shows_the_result_of_the_guv(self):
		"""Rule 170405070: without a Bilanzgewinn the Jahresüberschuss of the Bilanz is that of the GuV."""
		self.assertEqual(self.found.amount("bs.eqLiab.equity.netIncome"), D("40000.00"))
		self.assertEqual(self.found.value("bs.eqLiab.equity.netIncome").ledger, D("40000.00"))
		self.assertEqual(self.found.findings, ())

	def test_a_position_without_an_amount_has_no_value(self):
		self.assertIsNone(self.found.value("bs.eqLiab.equity.profitLoss"))
		self.assertIsNone(self.found.amount("bs.ass.deficitNotCoveredByCapital"))
		self.assertIsNone(self.found.value("bs.unknown"))
		self.assertEqual(self.found.value("bs.ass", AT).period, AT)

	def test_its_items_send_each_amount_and_the_mussfelder_without_one_as_nil(self):
		"""Leitfaden B.14.2.3 and B.14.10."""
		facts = {(item.concept, item.period): item.value for item in self.found.facts()}
		self.assertEqual(facts[(gaap("bs.ass"), AT)], D("110500.00"))
		self.assertEqual(facts[(gaap("is.netIncome"), OVER)], D("40000.00"))
		for name in (
			"bs.eqLiab.equity.profitLoss",
			"bs.eqLiab.equity.netIncome.taxBalanceGenerally",
			"bs.eqLiab.equity.netIncome.taxBalanceGenerally.finalPrev",
			"bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts",
		):
			with self.subTest(name=name):
				self.assertIsNone(facts[(gaap(name), AT)])
		self.assertNotIn((gaap("bs.ass.currAss.cashEquiv.cash"), AT), facts)
		self.assertNotIn((gaap("BVV.profitLoss"), OVER), facts)
		self.assertEqual(next(iter(facts)), (gaap("bs.ass"), AT))
		self.assertEqual(self.found.amounts()[(gaap("bs.ass"), AT)], D("110500.00"))


class RefusedBalancesTest(TestCase):
	def refused(self, concept: str | None) -> tuple[str, str]:
		found = of(*BOOKS, AccountBalance("9999", "Testkonto", concept, D("100.00")))
		(finding,) = found.findings[:1]
		self.assertTrue(finding.blocking)
		return finding.code, finding.reference

	def test_a_balance_without_a_position_blocks(self):
		self.assertEqual(self.refused(None), ("EB-NICHT-ZUGEORDNET", "9999"))

	def test_a_balance_on_a_position_the_e_bilanz_has_not_blocks(self):
		for concept in (
			"bs.unknown",
			"bs.eqLiab.equity.subscribed.limitedLiablePartners",
			"is.netIncome.costOfSales",
			"bs.ass.fixAss.intan.selfmade",
			"bs.eqLiab.liab.colEntity",
		):
			with self.subTest(concept=concept):
				self.assertEqual(self.refused(concept), ("EB-POSITION", concept))

	def test_a_balance_on_a_position_the_e_bilanz_computes_blocks(self):
		for concept in ("BVV.profitLoss.contribution", "bs.eqLiab.equity.netIncome"):
			with self.subTest(concept=concept):
				self.assertEqual(self.refused(concept), ("EB-BERECHNET", concept))

	def test_a_balance_on_the_bilanzgewinn_or_the_sammelposten_blocks(self):
		"""Rule 170405081 and structural error 170155121 of the Jahresdokumentation 6.9."""
		self.assertEqual(
			self.refused("bs.eqLiab.equity.profitLoss"), ("170405081", "bs.eqLiab.equity.profitLoss")
		)
		self.assertEqual(
			self.refused("is.netIncome.collItemChangeProfitHbst"),
			("170155121", "is.netIncome.collItemChangeProfitHbst"),
		)

	def test_a_balance_on_a_davon_position_blocks(self):
		for concept in (
			"bs.eqLiab.liab.bank.upTo1year",
			"is.netIncome.netSales.statutoryDuties.membershipFees",
		):
			with self.subTest(concept=concept):
				self.assertEqual(self.refused(concept), ("EB-DAVON", concept))

	def test_an_account_without_a_balance_is_left_out(self):
		found = of(*BOOKS, AccountBalance("9999", "", None, D("0.00")))
		self.assertEqual(found.findings, ())
		self.assertEqual(len(found.lines), len(BOOKS))

	def test_a_balance_on_a_total_with_positions_under_it_blocks(self):
		"""Leitfaden A.10.3: the amount belongs on a position under the total."""
		found = of(*BOOKS, AccountBalance("0100", "", "bs.ass.fixAss.intan", D("500.00")))
		finding = next(finding for finding in found.findings if finding.code == "EB-SUMME")
		self.assertEqual(finding.reference, "bs.ass.fixAss.intan")
		self.assertIn("Konten 0100", finding.text)
		self.assertIn("„Immaterielle Vermögensgegenstände, nicht zuordenbar“", finding.text)
		self.assertEqual(found.amount("bs.ass.fixAss.intan"), D("12500.00"))

	def test_a_balance_on_a_total_without_positions_under_it_is_its_amount(self):
		found = of(
			AccountBalance("0100", "Immaterielle Vermögensgegenstände", "bs.ass.fixAss.intan", D("500.00")),
			AccountBalance("2900", "Gezeichnetes Kapital", "bs.eqLiab.equity.subscribed.corp", D("-500.00")),
		)
		self.assertEqual(found.amount("bs.ass.fixAss.intan"), D("500.00"))
		self.assertEqual(found.findings, ())

	def test_a_total_without_a_candidate_names_none(self):
		found = of(*BOOKS, AccountBalance("3000", "", "bs.eqLiab.accruals", D("-10.00")))
		finding = next(finding for finding in found.findings if finding.code == "EB-SUMME")
		self.assertTrue(finding.text.endswith("auf eine Position darunter."))


class ChecksTest(TestCase):
	def test_aktiva_and_passiva_agree(self):
		"""Rule 170205010 of the Jahresdokumentation 6.9 (Leitfaden B.14.3.2.2)."""
		found = of(*BOOKS, AccountBalance("1000", "Kasse", "bs.ass.currAss.cashEquiv.bank", D("250.00")))
		(finding,) = found.findings
		self.assertEqual((finding.code, finding.reference), ("170205010", "bs.ass"))
		self.assertIn("110.750,00 €", finding.text)
		self.assertIn("Es fehlen 250,00 €", finding.text)

	def test_a_bilanz_without_amounts_has_neither_sum(self):
		"""Rules 170205011 and 170205012."""
		self.assertEqual(codes(of()), ["170205011", "170205012"])


class AdjustmentsTest(TestCase):
	def test_a_correction_replaces_the_amount_of_the_books_and_the_totals_follow(self):
		correction = Adjustment(
			"bs.ass.fixAss.intan.concessionBrands", D("11000.00"), "Abschreibung nachgeholt"
		)
		found = of(*BOOKS, adjustments=(correction,))
		value = found.value("bs.ass.fixAss.intan.concessionBrands")
		self.assertEqual(
			(value.ledger, value.amount, value.adjustment), (D("12000.00"), D("11000.00"), correction)
		)
		self.assertEqual(found.value("bs.ass").ledger, D("110500.00"))
		self.assertEqual(found.amount("bs.ass"), D("109500.00"))
		self.assertEqual(codes(found), ["170205010"])

	def test_a_line_by_hand_gives_a_position_without_balances_its_amount(self):
		line = Adjustment(
			"bs.eqLiab.liab.bank.upTo1year.shareholders", D("1000.00"), "Darlehen eines Gesellschafters"
		)
		found = of(*BOOKS, adjustments=(line,))
		value = found.value("bs.eqLiab.liab.bank.upTo1year.shareholders")
		self.assertEqual((value.ledger, value.amount), (None, D("1000.00")))
		self.assertEqual(found.amount("bs.eqLiab.liab.bank"), D("40000.00"))
		facts = {(item.concept, item.period): item.value for item in found.facts()}
		self.assertIsNone(facts[(gaap("bs.eqLiab.liab.bank.upTo1year"), AT)])
		self.assertEqual(found.findings, ())

	def test_a_total_and_a_position_the_e_bilanz_has_not_are_not_corrected(self):
		found = of(
			*BOOKS,
			adjustments=(
				Adjustment("bs.ass.fixAss", D("1.00"), "Grund"),
				Adjustment("bs.eqLiab.equity.netIncome", D("1.00"), "Grund"),
				Adjustment("BVV.profitLoss.contribution", D("1.00"), "Grund"),
				Adjustment("bs.unknown", D("1.00"), "Grund"),
			),
		)
		self.assertEqual(
			codes(found), ["EB-KORREKTUR-SUMME", "EB-KORREKTUR-SUMME", "EB-POSITION", "EB-POSITION"]
		)
		self.assertEqual(found.amount("bs.ass"), D("110500.00"))

	def test_an_adjustment_says_why_and_is_an_amount_in_cents(self):
		with self.assertRaises(ValueError):
			Adjustment("bs.ass", D("1.00"), " ")
		with self.assertRaises(ValueError):
			Adjustment("bs.ass", D("1.005"), "Grund")
		self.assertEqual(Adjustment("bs.ass", D("1"), "Grund").concept, gaap("bs.ass"))


class AccountBalanceTest(TestCase):
	def test_takes_an_amount_in_euros_and_cents_of_a_named_account(self):
		with self.assertRaises(TypeError):
			AccountBalance("1800", "Bank", "bs.ass", 1.5)
		with self.assertRaises(TypeError):
			AccountBalance("1800", "Bank", "bs.ass", True)
		with self.assertRaises(ValueError):
			AccountBalance("1800", "Bank", "bs.ass", D("NaN"))
		with self.assertRaises(ValueError):
			AccountBalance(" ", "Bank", "bs.ass", D("1.00"))
		self.assertEqual(AccountBalance("1800", "Bank", "bs.ass", D("1.00")).concept, gaap("bs.ass"))


class PreviousYearTest(TestCase):
	"""Only a Handelsbilanz shows the previous year (Leitfaden B.8.3)."""

	def test_a_handelsbilanz_computes_the_previous_year_as_well(self):
		prior = tuple(
			AccountBalance(
				balance.account, balance.description, balance.concept, balance.amount / 2, prior=True
			)
			for balance in BOOKS
		)
		found = calculate(
			structure(view(), case(accounting_standard="HGBM", periods=WITH_PRIOR)),
			(*BOOKS, *prior),
			(Adjustment("bs.ass.fixAss.tan", D("15000.00"), "Vorjahr laut Jahresabschluss", prior=True),),
		)
		self.assertEqual(found.amount("bs.ass", Period.VORJAHR_STICHTAG), D("55250.00"))
		self.assertEqual(found.amount("is.netIncome", Period.VORJAHR), D("20000.00"))
		self.assertEqual(found.amount("bs.eqLiab.equity.netIncome", Period.VORJAHR_STICHTAG), D("20000.00"))
		self.assertEqual(found.findings, ())
		periods = {item.period for item in found.facts()}
		self.assertEqual(periods, {AT, OVER, Period.VORJAHR_STICHTAG, Period.VORJAHR})

	def test_an_unbalanced_previous_year_says_so(self):
		found = calculate(
			structure(view(), case(accounting_standard="HGBM", periods=WITH_PRIOR)),
			(*BOOKS, AccountBalance("1800", "Bank", "bs.ass.currAss.cashEquiv.bank", D("10.00"), prior=True)),
		)
		self.assertEqual(codes(found), ["170205012"])
		self.assertIn("des Vorjahres", found.findings[0].text)
		self.assertEqual(found.findings[0].reference, "bs.eqLiab")

	def test_a_steuerbilanz_takes_no_previous_year(self):
		with self.assertRaises(ValueError):
			of(AccountBalance("1800", "Bank", "bs.ass.currAss.cashEquiv.bank", D("1.00"), prior=True))
		with self.assertRaises(ValueError):
			of(*BOOKS, adjustments=(Adjustment("bs.ass.fixAss.tan", D("1.00"), "Grund", prior=True),))


class EroeffnungsbilanzTest(TestCase):
	def test_an_eroeffnungsbilanz_has_no_result_and_its_jahresueberschuss_is_nil(self):
		opening = Periods(date(2026, 3, 1), date(2026, 12, 31), date(2026, 3, 1))
		found = of(
			AccountBalance("1800", "Bank", "bs.ass.currAss.cashEquiv.bank", D("25000.00")),
			AccountBalance(
				"2900", "Gezeichnetes Kapital", "bs.eqLiab.equity.subscribed.corp", D("-25000.00")
			),
			statement_type="EB",
			periods=opening,
		)
		self.assertEqual(found.findings, ())
		facts = {(item.concept, item.period): item.value for item in found.facts()}
		self.assertIsNone(facts[(gaap("bs.eqLiab.equity.netIncome"), AT)])
		self.assertNotIn((gaap("is.netIncome"), OVER), facts)


class BetriebsvermoegensvergleichTest(TestCase):
	"""Leitfaden B.14.3.2.12, rules 170405109 and 170405114 of the Jahresdokumentation 6.9."""

	@classmethod
	def setUpClass(cls):
		cls.found = of(*BOOKS)

	def compare(self, changes: EquityChanges):
		return betriebsvermoegensvergleich(self.found.structure, self.found.amounts(), changes)

	def test_the_betriebsvermoegen_at_the_end_is_the_eigenkapital_and_the_result_that_of_the_guv(self):
		found = self.compare(EquityChanges(previous_equity=D("27500.00")))
		self.assertEqual(found.amounts[gaap("BVV.profitLoss.assetsCurrentYear")], D("67500.00"))
		self.assertEqual(found.amounts[gaap("BVV.profitLoss.assetsPreviousYear")], D("27500.00"))
		self.assertEqual(found.amounts[gaap("BVV.profitLoss")], D("40000.00"))
		self.assertEqual(found.findings, ())
		facts = {item.concept: item.value for item in found.facts()}
		self.assertIsNone(facts[gaap("BVV.profitLoss.contribution")])
		self.assertIsNone(facts[gaap("BVV.profitLoss.assetsPreviousYear.capAdjustments")])
		self.assertNotIn(gaap("BVV.profitLoss.EStG6b"), facts)

	def test_einlagen_and_ausschuettungen_enter_with_their_signs(self):
		found = self.compare(
			EquityChanges(
				previous_equity=D("20000.00"),
				capital_adjustments=D("0.00"),
				withdrawals=D("2500.00"),
				contributions=D("10000.00"),
			)
		)
		self.assertEqual(found.amounts[gaap("BVV.profitLoss")], D("40000.00"))
		self.assertEqual(found.findings, ())

	def test_a_missing_einlage_says_how_much_is_missing(self):
		(finding,) = self.compare(EquityChanges(previous_equity=D("2500.00"))).findings
		self.assertEqual((finding.code, finding.reference), ("170405109", "BVV.profitLoss"))
		self.assertIn("65.000,00 €", finding.text)
		self.assertIn("25.000,00 €", finding.text)

	def test_the_finding_says_in_which_direction_the_betriebsvermoegen_lacks_a_change(self):
		"""An Eigenkapital that grew beyond the Jahresüberschuss lacks Einlagen, one that shrank lacks Entnahmen or
		Ausschüttungen; the amount is named without a sign."""
		(missing_einlage,) = self.compare(EquityChanges(previous_equity=D("2500.00"))).findings
		self.assertIn("Es fehlen Einlagen von 25.000,00 €", missing_einlage.text)
		self.assertIn("„Weitere Einlagen“", missing_einlage.text)
		(missing_ausschuettung,) = self.compare(EquityChanges(previous_equity=D("37500.00"))).findings
		self.assertIn("Es fehlen Entnahmen oder Ausschüttungen von 10.000,00 €", missing_ausschuettung.text)
		self.assertIn("„Entnahmen und Ausschüttungen“", missing_ausschuettung.text)
		self.assertNotIn("-", missing_ausschuettung.text.split("Es fehlen")[1])

	def test_takes_amounts_in_cents(self):
		with self.assertRaises(ValueError):
			EquityChanges(withdrawals=D("0.001"))
