"""The Handelsbilanz of the E-Bilanz against the Jahresabschluss of its year, without a bench: what the comparison takes
of the statement of the invented Kleinstkapitalgesellschaft of steuerbote/hgb/tests/companies.py for each
Bilanzierungsstandard, what rounding leaves, and the findings for a Jahresabschluss festgestellt or not, one not
calculated, and none."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.ebilanz.positions import AccountingStandard
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import build
from steuerbote.hgb.tests.companies import KLEINST_2025, KLEINST_2026, PARENTS
from steuerbote.jahresmeldung.findings import Severity
from steuerbote.steuerbote.doctype.electronic_balance_sheet import bridge, comparison
from steuerbote.steuerbote.doctype.electronic_balance_sheet.comparison import (
	DIFFERENCE,
	MISSING,
	Accounts,
	Difference,
)

HGBM = AccountingStandard.HANDELSBILANZ
HAOE = AccountingStandard.EINHEITSBILANZ
AO = AccountingStandard.STEUERBILANZ
NAME = "JA-2026-00001"


def d(value: str) -> Decimal:
	return Decimal(value)


def statement():
	"""The Jahresabschluss 2026 of the Beispiel Werkstatt GmbH, a Kleinstkapitalgesellschaft: Summe Aktiva 78,671.50
	euros, of them 18,400.40 Anlagevermögen, and a Jahresüberschuss of 19,000."""
	return build(2026, SizeClass.KLEINST, KLEINST_2026, parents=PARENTS, prior=KLEINST_2025)


def books() -> dict[str, Decimal]:
	"""The amounts in euros and cents the E-Bilanz of the same books reports for the positions of the statement."""
	found = statement()
	sheet = found.balance_sheet
	amounts = {line.position.concept: line.amount for line in (*sheet.aktiva, *sheet.passiva)}
	amounts.update(
		{
			"bs.ass": sheet.aktiva_total,
			"bs.eqLiab": sheet.passiva_total,
			"is.netIncome": found.income_statement.net_income,
		}
	)
	return amounts


class ComparedTest(TestCase):
	def test_a_handelsbilanz_takes_every_position_of_the_bilanz_the_sums_and_the_jahresueberschuss(self):
		compared = comparison.compared(statement(), HGBM)
		self.assertEqual(
			[concept for concept, _label, _amount in compared],
			[
				"bs.ass.fixAss",
				"bs.ass.currAss",
				"bs.ass.prepaidExp",
				"bs.ass.defTax",
				"bs.ass.SurplusFromOffsetting",
				"bs.ass.deficitNotCoveredByCapital",
				"bs.eqLiab.equity",
				"bs.eqLiab.accruals",
				"bs.eqLiab.liab",
				"bs.eqLiab.defIncome",
				"bs.eqLiab.defTax",
				"bs.ass",
				"bs.eqLiab",
				"is.netIncome",
			],
		)
		self.assertEqual(compared[0], ("bs.ass.fixAss", "Anlagevermögen", d("18401")))

	def test_the_jahresabschluss_counts_in_the_full_euros_of_its_offenlegung(self):
		compared = {concept: amount for concept, _label, amount in comparison.compared(statement(), HGBM)}
		self.assertEqual(
			(compared["bs.ass"], compared["bs.eqLiab"], compared["is.netIncome"]),
			(d("78672"), d("78672"), d("19000")),
		)

	def test_an_einheitsbilanz_takes_the_summe_aktiva_and_the_jahresueberschuss(self):
		self.assertEqual(
			comparison.compared(statement(), HAOE),
			(
				("bs.ass", "Summe Aktiva", d("78672")),
				("is.netIncome", "Jahresüberschuss/Jahresfehlbetrag", d("19000")),
			),
		)

	def test_a_steuerbilanz_takes_nothing(self):
		self.assertEqual(comparison.compared(statement(), AO), ())


class DifferencesTest(TestCase):
	def test_the_books_of_the_jahresabschluss_differ_in_nothing_but_rounding(self):
		amounts = books()
		self.assertEqual(comparison.differences(statement(), HGBM, amounts.get), ())
		self.assertEqual(comparison.differences(statement(), HAOE, amounts.get), ())

	def test_a_euro_or_more_is_a_difference(self):
		for amount, differs in (
			("78672.99", False),
			("78673.00", True),
			("78671.00", True),
			("78671.01", False),
		):
			with self.subTest(amount=amount):
				amounts = {**books(), "bs.ass": d(amount)}
				found = comparison.differences(statement(), HAOE, amounts.get)
				self.assertEqual([item.concept for item in found], ["bs.ass"] if differs else [])

	def test_a_position_the_e_bilanz_does_not_carry_is_left_out(self):
		amounts = {concept: amount for concept, amount in books().items() if concept != "bs.ass.currAss"}
		amounts["bs.eqLiab.liab"] = d("0")
		found = comparison.differences(statement(), HGBM, amounts.get)
		self.assertEqual([item.concept for item in found], ["bs.eqLiab.liab"])

	def test_a_difference_names_both_amounts(self):
		amounts = {**books(), "bs.ass.currAss": d("60791.10")}
		(found,) = comparison.differences(statement(), HGBM, amounts.get)
		self.assertEqual(found, Difference("bs.ass.currAss", "Umlaufvermögen", d("60791.10"), d("59791")))
		self.assertEqual(found.amount, d("1000.10"))


class FindingsTest(TestCase):
	def amounts(self) -> dict[str, Decimal]:
		return {**books(), "bs.ass": d("77671.50"), "is.netIncome": d("18000.00")}

	def test_a_festgestellter_jahresabschluss_that_differs_holds_the_e_bilanz_back(self):
		found = comparison.findings(Accounts(NAME, statement(), True), HAOE, self.amounts().get)
		self.assertEqual(
			[(item.code, item.severity, item.reference) for item in found],
			[(DIFFERENCE, Severity.ERROR, "bs.ass"), (DIFFERENCE, Severity.ERROR, "is.netIncome")],
		)
		self.assertTrue(
			found[0].text.startswith(
				"Summe Aktiva [bs.ass] beträgt in der E-Bilanz 77.671,50 €, im festgestellten Jahresabschluss "
				"JA-2026-00001 78.672,00 €: ein Unterschied von -1.000,50 €."
			)
		)
		self.assertIn("(Quelle: § 5 Abs. 1 Satz 1, § 5b Abs. 1 Satz 1 und 2 EStG", found[0].text)

	def test_a_jahresabschluss_not_festgestellt_that_differs_gives_a_hint(self):
		found = comparison.findings(Accounts(NAME, statement(), False), HAOE, self.amounts().get)
		self.assertEqual({item.severity for item in found}, {Severity.HINT})
		self.assertIn(
			"im Jahresabschluss JA-2026-00001, der nicht festgestellt ist, 78.672,00 €", found[0].text
		)

	def test_a_jahresabschluss_that_agrees_gives_nothing(self):
		self.assertEqual(comparison.findings(Accounts(NAME, statement(), True), HGBM, books().get), ())

	def test_a_jahresabschluss_not_calculated_gives_a_hint_that_nothing_was_compared(self):
		(waiting,) = comparison.findings(Accounts(NAME, None, False), HAOE, books().get)
		self.assertEqual((waiting.code, waiting.severity, waiting.reference), (MISSING, Severity.HINT, NAME))
		self.assertTrue(waiting.text.startswith("Der Jahresabschluss JA-2026-00001 ist nicht berechnet"))

	def test_without_a_jahresabschluss_nothing_is_compared(self):
		self.assertEqual(comparison.findings(None, HGBM, books().get), ())

	def test_a_steuerbilanz_is_compared_with_no_jahresabschluss(self):
		self.assertEqual(comparison.findings(Accounts(NAME, None, False), AO, books().get), ())
		accounts = Accounts(NAME, statement(), True)
		self.assertEqual(comparison.findings(accounts, AO, self.amounts().get), ())

	def test_the_codes_are_among_those_of_steuerbote(self):
		self.assertEqual(comparison.CODES, (DIFFERENCE, MISSING))
		self.assertTrue(set(comparison.CODES) <= set(bridge.CODES))
