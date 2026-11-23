"""The Überleitungsrechnung of the Handelsbilanz of the invented GmbH, on the mini taxonomy: its tuples with the entries
of every total, the steuerlicher Ausgleichsposten, the Sammelposten, the Steuerbilanz that results, and the refusals."""

from dataclasses import replace
from decimal import Decimal
from unittest import TestCase

from steuerbote.ebilanz.calculation import AccountBalance, calculate
from steuerbote.ebilanz.positions import structure
from steuerbote.ebilanz.tests.taxonomy import gaap, view
from steuerbote.ebilanz.tests.test_calculation import BOOKS, case
from steuerbote.ebilanz.ueberleitung import KIND, TRANSFER, Kind, Transfer, ueberleitung
from steuerbote.xbrl.checks import Severity
from steuerbote.xbrl.facts import Item, Period, Tuple

D = Decimal
AT, OVER = Period.STICHTAG, Period.WIRTSCHAFTSJAHR
CHANGE, MOVE = Kind.WERTAENDERUNG, Kind.UMGLIEDERUNG
# The Handelsbilanz capitalises software of its own, which the Steuerbilanz may not (§ 5 Abs. 2 EStG), against its
# sales for the mini taxonomy's want of „andere aktivierte Eigenleistungen“.
HANDELSBILANZ = (
	*BOOKS,
	AccountBalance("0144", "Selbst geschaffene Software", "bs.ass.fixAss.intan.selfmade", D("5000.00")),
	AccountBalance("4820", "Andere aktivierte Eigenleistungen", "is.netIncome.netSales", D("-5000.00")),
)
SOFTWARE = Transfer(
	CHANGE, "bs.ass.fixAss.intan.selfmade", D("-5000.00"), reason="Aktivierungsverbot § 5 Abs. 2 EStG"
)
SALES = Transfer(CHANGE, "is.netIncome.netSales", D("-5000.00"), reason="Aktivierungsverbot § 5 Abs. 2 EStG")
ACCRUAL = Transfer(
	CHANGE, "bs.eqLiab.accruals.other", D("-1000.00"), reason="Drohverlustrückstellung, § 5 Abs. 4a EStG"
)


def of(*transfers, books=HANDELSBILANZ, **fields):
	calculation = calculate(structure(view(), case(**{"accounting_standard": "HGBM", **fields})), books)
	return ueberleitung(calculation, transfers)


def codes(found) -> list[str]:
	return [finding.code for finding in found.findings]


class EntriesTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.found = of(SOFTWARE, SALES, ACCRUAL)

	def test_writes_one_tuple_per_kind_with_an_entry_for_every_total(self):
		"""Leitfaden A.11, B.15.1; the examples of the ERiC documentation transfer each total as well."""
		(group,) = self.found.groups
		self.assertEqual(group.kind, CHANGE)
		self.assertEqual(group.transfers, (SOFTWARE, SALES, ACCRUAL))
		entries = {entry.position: (entry.current, entry.previous) for entry in group.entries}
		self.assertEqual(
			entries,
			{
				gaap("bs.ass"): (D("-5000.00"), None),
				gaap("bs.ass.fixAss"): (D("-5000.00"), None),
				gaap("bs.ass.fixAss.intan"): (D("-5000.00"), None),
				gaap("bs.ass.fixAss.intan.selfmade"): (D("-5000.00"), None),
				gaap("bs.eqLiab"): (D("-5000.00"), None),
				gaap("bs.eqLiab.equity"): (D("-4000.00"), None),
				gaap("bs.eqLiab.equity.netIncome.taxBalanceGenerally"): (D("-4000.00"), None),
				gaap("bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts"): (
					D("-4000.00"),
					None,
				),
				gaap("bs.eqLiab.accruals"): (D("-1000.00"), None),
				gaap("bs.eqLiab.accruals.other"): (D("-1000.00"), None),
				gaap("is.netIncome"): (D("-4000.00"), None),
				gaap("is.netIncome.netSales"): (D("-5000.00"), None),
				gaap("is.netIncome.collItemChangeProfitHbst"): (D("1000.00"), None),
			},
		)
		self.assertEqual(self.found.findings, ())

	def test_the_steuerbilanz_is_the_handelsbilanz_with_its_changes(self):
		"""Leitfaden B.15.1; the Jahresüberschuss of the Bilanz with the Ausgleichsposten is that of the GuV (rule
		170405070)."""
		steuerbilanz = self.found.steuerbilanz
		self.assertEqual(steuerbilanz[(gaap("bs.ass.fixAss.intan.selfmade"), AT)], D("0.00"))
		self.assertEqual(steuerbilanz[(gaap("bs.ass"), AT)], D("110500.00"))
		self.assertEqual(steuerbilanz[(gaap("bs.eqLiab"), AT)], D("110500.00"))
		self.assertEqual(steuerbilanz[(gaap("bs.eqLiab.equity"), AT)], D("68500.00"))
		self.assertEqual(steuerbilanz[(gaap("is.netIncome"), OVER)], D("41000.00"))
		self.assertEqual(
			steuerbilanz[(gaap("bs.eqLiab.equity.netIncome"), AT)]
			+ steuerbilanz[
				(gaap("bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts"), AT)
			],
			steuerbilanz[(gaap("is.netIncome"), OVER)],
		)

	def test_its_facts_are_a_tuple_per_group_with_the_kind_and_the_entries(self):
		(transfer,) = self.found.facts()
		self.assertEqual(transfer.concept, TRANSFER)
		kind, first, *_, last = transfer.children
		self.assertEqual(kind, Tuple(KIND, (Item(CHANGE.value, OVER, ""),)))
		self.assertEqual(
			first,
			Tuple(
				gaap("hbst.transfer.bsAss"),
				(
					Item(gaap("hbst.transfer.bsAss.name"), OVER, gaap("bs.ass")),
					Item(gaap("hbst.transfer.bsAss.changeValueActualPeriod"), OVER, D("-5000.00")),
				),
			),
		)
		self.assertEqual(last.concept, gaap("hbst.transfer.isChangeNetIncome"))
		self.assertEqual(
			[child.value for child in last.children],
			[gaap("is.netIncome.collItemChangeProfitHbst"), D("1000.00")],
		)


class EarlierYearsTest(TestCase):
	def test_a_change_of_earlier_years_goes_to_the_ausgleichsposten_of_the_last_stichtag(self):
		earlier = Transfer(
			CHANGE,
			"bs.eqLiab.accruals.other",
			D("0.00"),
			D("-500.00"),
			reason="Rückstellung aus 2025, steuerlich",
		)
		found = of(SOFTWARE, SALES, earlier)
		(group,) = found.groups
		entries = {entry.position: (entry.current, entry.previous) for entry in group.entries}
		self.assertEqual(entries[gaap("bs.eqLiab.accruals.other")], (D("0.00"), D("-500.00")))
		self.assertEqual(
			entries[gaap("bs.eqLiab.equity.netIncome.taxBalanceGenerally.finalPrev")],
			(D("0.00"), D("500.00")),
		)
		self.assertEqual(entries[gaap("bs.eqLiab")], (D("-5000.00"), None))
		self.assertEqual(found.steuerbilanz[(gaap("bs.eqLiab.accruals.other"), AT)], D("2500.00"))
		self.assertEqual(found.findings, ())
		(transfer,) = found.facts()
		accrual = next(
			child
			for child in transfer.children
			if child.children[0].value == gaap("bs.eqLiab.accruals.other")
		)
		self.assertEqual(
			[child.concept for child in accrual.children],
			[
				gaap("hbst.transfer.bsEqLiab.name"),
				gaap("hbst.transfer.bsEqLiab.changeValueActualPeriod"),
				gaap("hbst.transfer.bsEqLiab.changeValuePreviousPeriod"),
			],
		)


class UmgliederungTest(TestCase):
	def test_an_umgliederung_moves_amounts_in_a_tuple_of_its_own(self):
		moves = (
			Transfer(MOVE, "bs.ass.fixAss.tan", D("-2000.00"), reason="Software war unter Grundstücken"),
			Transfer(
				MOVE,
				"bs.ass.fixAss.intan.concessionBrands",
				D("2000.00"),
				reason="Software war unter Grundstücken",
			),
		)
		found = of(*moves, SOFTWARE, SALES)
		self.assertEqual([group.kind for group in found.groups], [MOVE, CHANGE])
		entries = {entry.position: entry.current for entry in found.groups[0].entries}
		self.assertEqual(
			entries,
			{
				gaap("bs.ass.fixAss.intan"): D("2000.00"),
				gaap("bs.ass.fixAss.intan.concessionBrands"): D("2000.00"),
				gaap("bs.ass.fixAss.tan"): D("-2000.00"),
			},
		)
		self.assertEqual(found.findings, ())

	def test_an_umgliederung_that_changes_the_eigenkapital_is_a_hint(self):
		found = of(
			SOFTWARE, SALES, Transfer(MOVE, "bs.ass.fixAss.tan", D("-2000.00"), reason="halbe Umgliederung")
		)
		(hint,) = found.findings
		self.assertEqual((hint.code, hint.severity), ("EB-UMGLIEDERUNG", Severity.HINT))
		self.assertEqual([group.kind for group in found.groups], [MOVE, CHANGE])

	def test_the_ausgleichsposten_of_umgliederungen_only_go_into_a_tuple_of_wertaenderungen(self):
		found = of(
			Transfer(MOVE, "bs.ass.fixAss.tan", D("-2000.00"), reason="halbe Umgliederung"),
			books=BOOKS,
		)
		self.assertEqual([group.kind for group in found.groups], [MOVE, CHANGE])
		self.assertEqual(found.groups[1].transfers, ())


class RefusalsTest(TestCase):
	def test_a_steuerbilanz_has_no_ueberleitung(self):
		"""Leitfaden B.16.1, rule 170205095."""
		steuerbilanz = calculate(structure(view(), case()), BOOKS)
		found = ueberleitung(steuerbilanz, (ACCRUAL,))
		self.assertEqual((codes(found), found.groups), (["170205095"], ()))
		self.assertEqual(found.steuerbilanz, steuerbilanz.amounts())
		self.assertEqual(ueberleitung(steuerbilanz, ()).findings, ())

	def test_a_handelsbilanz_has_an_entry_and_one_that_counts(self):
		"""Rule 170205100 and structural error 170145132."""
		self.assertEqual(codes(of(books=BOOKS)), ["170205100"])
		cancelled = (
			Transfer(CHANGE, "bs.eqLiab.accruals.other", D("100.00"), reason="Grund"),
			Transfer(CHANGE, "bs.eqLiab.accruals.other", D("-100.00"), reason="Grund"),
		)
		self.assertEqual(codes(of(*cancelled, books=BOOKS)), ["170145132"])

	def test_refuses_entries_steuerbote_does_not_take(self):
		found = of(
			SOFTWARE,
			SALES,
			Transfer(CHANGE, "bs.unknown", D("1.00"), reason="Grund"),
			Transfer(CHANGE, "bs.eqLiab.liab.bank.upTo1year", D("1.00"), reason="Grund"),
			Transfer(CHANGE, "bs.eqLiab.accruals", D("1.00"), reason="Grund"),
			Transfer(
				CHANGE, "bs.eqLiab.equity.netIncome.taxBalanceGenerally.finalPrev", D("1.00"), reason="Grund"
			),
			Transfer(CHANGE, "is.netIncome.collItemChangeProfitHbst", D("1.00"), reason="Grund"),
			Transfer(CHANGE, "bs.eqLiab.accruals.other", None, reason="Grund"),
			Transfer(CHANGE, "is.netIncome.tax", D("1.00"), D("1.00"), reason="Grund"),
			Transfer(CHANGE, "bs.eqLiab.accruals.other", D("1.00")),
		)
		self.assertEqual(
			codes(found),
			[
				"170145086",
				"EB-DAVON",
				"EB-UEBERLEITUNG-SUMME",
				"EB-UEBERLEITUNG-BERECHNET",
				"EB-UEBERLEITUNG-BERECHNET",
				"170145129",
				"EB-UEBERLEITUNG-VORPERIODE",
				"EB-UEBERLEITUNG-BEGRUENDUNG",
			],
		)
		self.assertEqual(found.groups[0].transfers, (SOFTWARE, SALES))

	def test_takes_an_entry_of_a_total_the_books_fill_themselves(self):
		"""A Mussfeld of the HGB-Taxonomie 6.9 such as „sonstige Rückstellungen“ adds up positions the books may leave
		empty: with nothing below it, an entry changes it as it changes any position (Leitfaden B.15.1)."""
		books = tuple(
			replace(balance, concept="bs.ass.currAss.cashEquiv")
			if balance.concept == gaap("bs.ass.currAss.cashEquiv.bank")
			else balance
			for balance in HANDELSBILANZ
		)
		cash = Transfer(CHANGE, "bs.ass.currAss.cashEquiv", D("-500.00"), reason="Bewertung")
		found = of(SOFTWARE, SALES, cash, books=books)
		self.assertEqual(found.findings, ())
		entries = {entry.position: entry.current for entry in found.groups[0].entries}
		self.assertEqual(entries[gaap("bs.ass.currAss.cashEquiv")], D("-500.00"))
		self.assertEqual(entries[gaap("bs.ass.currAss")], D("-500.00"))
		self.assertEqual(found.steuerbilanz[(gaap("bs.ass.currAss.cashEquiv"), AT)], D("68000.00"))
		below = Transfer(CHANGE, "bs.ass.currAss.cashEquiv.cash", D("100.00"), reason="Kassenfehlbetrag")
		found = of(SOFTWARE, SALES, cash, below, books=books)
		self.assertEqual(
			[(finding.code, finding.reference) for finding in found.findings],
			[("EB-UEBERLEITUNG-SUMME", "bs.ass.currAss.cashEquiv")],
		)
		self.assertEqual(found.groups[0].transfers, (SOFTWARE, SALES, below))

	def test_a_position_steuerlich_not_permitted_is_zero_after_the_ueberleitung(self):
		"""Leitfaden B.15.2."""
		half = Transfer(CHANGE, "bs.ass.fixAss.intan.selfmade", D("-4000.00"), reason="Grund")
		(finding,) = of(half, SALES).findings
		self.assertEqual(
			(finding.code, finding.reference), ("EB-UEBERLEITUNG-STEUERLICH", "bs.ass.fixAss.intan.selfmade")
		)
		self.assertIn("1.000,00 €", finding.text)

	def test_takes_amounts_in_euros_and_cents(self):
		with self.assertRaises(ValueError):
			Transfer(CHANGE, "bs.ass", D("0.001"))
		with self.assertRaises(ValueError):
			Transfer(CHANGE, "bs.ass", None, True)
		transfer = Transfer("de-gaap-ci:hbst.transfer.kind.reclassificationChangeValue", "bs.ass", None)
		self.assertEqual((transfer.kind, transfer.position), (Kind.BEIDES, gaap("bs.ass")))
