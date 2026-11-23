"""The bridge of the E-Bilanz between the Electronic Balance Sheet and steuerbote.ebilanz, on the mini taxonomy of the
tests of steuerbote/ebilanz and the invented GmbH of their tests: the case and the books, the corrections and lines by
hand, the rows of the positions, the Kontensalden, the Anlagenspiegel and the Überleitung, the Betriebsvermögensvergleich,
the E-Bilanz of the document as stored, and the findings of Steuerbote."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.balance_mapping_sync import DAVON_REASON
from steuerbote.ebilanz.anlagenspiegel import Row, ValueType
from steuerbote.ebilanz.calculation import AccountBalance, Adjustment, EquityChanges, calculate
from steuerbote.ebilanz.instance import Sources, build
from steuerbote.ebilanz.positions import AccountingStandard, StatementType, structure
from steuerbote.ebilanz.tests.taxonomy import gaap, view
from steuerbote.ebilanz.tests.test_anlagenspiegel import LAND, SOFTWARE
from steuerbote.ebilanz.tests.test_calculation import BOOKS, case
from steuerbote.ebilanz.tests.test_gcd import MASTER
from steuerbote.ebilanz.tests.test_ueberleitung import ACCRUAL, HANDELSBILANZ, SALES
from steuerbote.ebilanz.tests.test_ueberleitung import SOFTWARE as SELFMADE
from steuerbote.ebilanz.ueberleitung import Kind, Transfer, ueberleitung
from steuerbote.jahresmeldung.findings import DATA_LENGTH, Severity
from steuerbote.jahresmeldung.overrides import OverrideError
from steuerbote.steuerbote.doctype.electronic_balance_sheet import bridge
from steuerbote.steuerbote.doctype.electronic_balance_sheet.bridge import (
	DERIVED_REASON,
	BridgeError,
	CategoryValues,
	Unposted,
)
from steuerbote.xbrl import mapping
from steuerbote.xbrl.facts import Periods
from steuerbote.xbrl.mapping import Part, Placed, Placement, Purpose, Rule

D = Decimal
YEAR = (date(2026, 1, 1), date(2026, 12, 31))
EQUITY = EquityChanges(previous_equity=D("27500.00"))
BANK = "bs.ass.currAss.cashEquiv.bank"
SALES_POSITION = "is.netIncome.netSales"
DAVON = "is.netIncome.netSales.statutoryDuties.membershipFees"


def ebilanz(sources=None, **fields):
	return build(
		structure(view(), case(**fields)),
		MASTER,
		sources or Sources(BOOKS, assets=(SOFTWARE, LAND), equity=EQUITY),
	)


def by_concept(rows) -> dict[str, dict]:
	return {row["concept"]: row for row in rows}


def position(concept: str, computed: str = "0", **fields) -> dict:
	return {"concept": concept, "computed": computed, "correction": 0, "correction_reason": "", **fields}


class CaseTest(TestCase):
	def test_a_jahresabschluss_closes_at_the_end_of_the_fiscal_year(self):
		"""Rule 170205072."""
		found = bridge.case_of("GmbH", *YEAR, "Jahresabschluss", "HAOE")
		self.assertEqual(found.periods, Periods(*YEAR, date(2026, 12, 31)))
		self.assertEqual(
			(found.statement_type, found.accounting_standard),
			(StatementType.JAHRESABSCHLUSS, AccountingStandard.EINHEITSBILANZ),
		)

	def test_an_eroeffnungsbilanz_closes_on_the_first_day(self):
		"""Rule 170205081, Leitfaden B.14.3.1.6; a short first fiscal year from March."""
		found = bridge.case_of("UG", date(2026, 3, 1), date(2026, 12, 31), "Eröffnungsbilanz", "AO")
		self.assertEqual(found.periods.balance_sheet_date, date(2026, 3, 1))
		self.assertTrue(found.opening)
		self.assertFalse(found.prior)

	def test_refuses_another_bilanzart_or_standard(self):
		with self.assertRaises(BridgeError) as raised:
			bridge.case_of("GmbH", *YEAR, "Zwischenbilanz", "HAOE")
		self.assertEqual(
			(raised.exception.template, raised.exception.values),
			(bridge.NO_STATEMENT_TYPE, ("Zwischenbilanz",)),
		)
		with self.assertRaises(BridgeError) as raised:
			bridge.case_of("GmbH", *YEAR, "Jahresabschluss", "IFRS")
		self.assertEqual(raised.exception.template, bridge.NO_ACCOUNTING_STANDARD)

	def test_the_rules_of_the_balance_sheet_of_the_standard_count(self):
		"""Leitfaden B.13: the Einheitsbilanz counts the rules for both, the Handelsbilanz and the Steuerbilanz their own."""
		self.assertEqual(
			[bridge.purpose_of(standard) for standard in ("HAOE", "HGBM", "AO")],
			[Purpose.BOTH, Purpose.COMMERCIAL, Purpose.TAX],
		)

	def test_the_balances_come_from_the_finance_book_of_the_balance_sheet(self):
		self.assertEqual(bridge.balance_book("HAOE", "HB", "StB"), "HB")
		self.assertEqual(bridge.balance_book("HGBM", "HB", "StB"), "HB")
		self.assertEqual(bridge.balance_book("AO", "HB", "StB"), "StB")
		self.assertIsNone(bridge.balance_book("AO", "HB", None))
		self.assertIsNone(bridge.balance_book("HAOE", "", "StB"))

	def test_a_handelsbilanz_reads_the_depreciation_of_both_books(self):
		self.assertEqual(bridge.finance_books("HGBM", None, "Steuerbilanz"), ("", "Steuerbilanz"))
		self.assertEqual(bridge.finance_books("HGBM", "HB", None), ("HB",))
		self.assertEqual(bridge.finance_books("HAOE", None, "Steuerbilanz"), ("",))
		self.assertEqual(bridge.finance_books("AO", "HB", "Steuerbilanz"), ("Steuerbilanz",))


class AdjustmentsTest(TestCase):
	def test_a_correction_with_its_reason_and_a_line_by_hand_are_adjustments(self):
		rows = [
			position(BANK, "68500", correction=70000, correction_reason="Kontoauszug zum 31.12."),
			position("bs.eqLiab.accruals.other", "3000"),
			{
				"concept": "de-gaap-ci:is.netIncome.tax",
				"correction": 9500,
				"correction_reason": "Bescheid",
				"manual": 1,
			},
		]
		self.assertEqual(
			bridge.adjustments_of(rows),
			(
				Adjustment(BANK, D("70000.00"), "Kontoauszug zum 31.12."),
				Adjustment("is.netIncome.tax", D("9500.00"), "Bescheid"),
			),
		)
		self.assertEqual(bridge.corrected(rows), frozenset({gaap(BANK)}))
		self.assertEqual(bridge.by_hand(rows), frozenset({gaap("is.netIncome.tax")}))

	def test_a_correction_to_zero_counts_and_an_amount_without_reason_is_refused(self):
		"""docs/roadmap.md, Grundsätze: a deviation is explained."""
		(found,) = bridge.adjustments_of(
			[position(BANK, "68500", correction=0, correction_reason="Konto aufgelöst")]
		)
		self.assertEqual(found.amount, D("0.00"))
		with self.assertRaises(OverrideError):
			bridge.adjustments_of([position(BANK, "68500", correction=1)])

	def test_a_row_without_its_position_is_refused_by_its_number(self):
		with self.assertRaises(BridgeError) as raised:
			bridge.adjustments_of([{"idx": 4, "concept": " ", "correction": 1, "correction_reason": "x"}])
		self.assertEqual(raised.exception.values, (4, "Positions"))


class SavedRowsTest(TestCase):
	"""What a save keeps of the tables that Berechnen fills and the company enters into."""

	def test_a_line_by_hand_names_its_position_without_the_prefix(self):
		rows = bridge.lines_by_hand(
			[
				position(BANK, "1"),
				{
					"concept": " de-gaap-ci:is.netIncome.tax ",
					"manual": 1,
					"correction": 1,
					"correction_reason": "x",
				},
			]
		)
		self.assertEqual([row["concept"] for row in rows], [BANK, "is.netIncome.tax"])

	def test_a_position_berechnen_reports_takes_no_line_by_hand(self):
		with self.assertRaises(BridgeError) as raised:
			bridge.lines_by_hand(
				[position(BANK, "1"), {"idx": 2, "concept": f"de-gaap-ci:{BANK}", "manual": 1}]
			)
		self.assertEqual((raised.exception.template, raised.exception.values), (bridge.DOUBLED, (2, BANK)))
		with self.assertRaises(BridgeError) as raised:
			bridge.lines_by_hand([{"concept": "", "manual": 1}])
		self.assertEqual(raised.exception.values, (1, "Positions"))

	def test_a_row_of_a_category_keeps_what_berechnen_wrote_and_takes_the_columns_by_hand(self):
		stored = [
			{
				"name": "a",
				"asset_category": "Software",
				"value_type": "StB",
				"manual": 0,
				"cost_begin": 100,
				"erp_adjustment": -5,
				"writeups": 0,
			},
			{"name": "b", "position": "bs.ass.fixAss.tan", "manual": 1, "cost_begin": 1},
			{
				"name": "c",
				"asset_category": "Grundstücke",
				"value_type": "StB",
				"manual": 0,
				"cost_begin": 30,
			},
		]
		sent = [
			{
				"name": "a",
				"asset_category": "Anders",
				"manual": 0,
				"cost_begin": 999,
				"erp_adjustment": 0,
				"writeups": 5,
				"reason": "Zuschreibung",
			},
			{"name": "b", "position": "bs.ass.fixAss.tan", "manual": 1, "cost_begin": 2},
			{
				"name": None,
				"position": "bs.ass.fixAss.intan.concessionBrands",
				"asset_category": "Software",
				"manual": 0,
				"erp_adjustment": 7,
				"cost_begin": 3,
			},
		]
		first, by_hand, new, kept = bridge.kept_assets(stored, sent)
		self.assertEqual(
			(first["asset_category"], first["cost_begin"], first["erp_adjustment"], first["writeups"]),
			("Software", 100, -5, 5),
		)
		self.assertEqual(first["reason"], "Zuschreibung")
		self.assertEqual((by_hand["cost_begin"], by_hand["manual"]), (2, 1))
		self.assertEqual(
			(new["manual"], new["asset_category"], new["erp_adjustment"], new["cost_begin"]),
			(1, None, D("0"), 3),
		)
		self.assertEqual(kept["name"], "c")

	def test_an_entry_of_the_finance_book_stays_as_berechnen_wrote_it(self):
		stored = [
			{"name": "a", "position": "bs.ass", "current": 5, "derived": 1},
			{"name": "b", "position": "bs.eqLiab.accruals.other", "current": 1, "derived": 0},
			{"name": "c", "position": "is.netIncome.netSales", "current": 2, "derived": 1},
		]
		sent = [
			{"name": "a", "position": "bs.eqLiab", "current": 9, "derived": 0},
			{"name": "b", "position": "bs.eqLiab.accruals.other", "current": 3, "derived": 1},
			{"name": None, "position": "bs.ass.fixAss.tan", "current": 4, "derived": 1},
		]
		derived, by_hand, new, kept = bridge.kept_transfers(stored, sent)
		self.assertEqual((derived["position"], derived["current"], derived["derived"]), ("bs.ass", 5, 1))
		self.assertEqual((by_hand["current"], by_hand["derived"]), (3, 0))
		self.assertEqual((new["position"], new["derived"]), ("bs.ass.fixAss.tan", 0))
		self.assertEqual(kept["name"], "c")

	def test_a_new_document_keeps_what_the_company_entered(self):
		rows = [
			{
				"asset_category": "Software",
				"value_type": "StB",
				"manual": 0,
				"cost_begin": 100,
				"writeups": 5,
				"reason": " Zuschreibung ",
			},
			{"asset_category": "Alt", "manual": 0},
			{"position": "bs.ass.fixAss.tan", "manual": 1, "cost_begin": 30, "reason": "Grundstück"},
		]
		category, other, by_hand = bridge.asset_inputs(rows)
		self.assertEqual(
			category,
			{
				"asset_category": "Software",
				"value_type": "StB",
				"manual": 0,
				**dict.fromkeys(bridge.MANUAL_COLUMNS, D("0.00")),
				"writeups": D("5.00"),
				"reason": "Zuschreibung",
			},
		)
		self.assertEqual(other["value_type"], "StB")
		self.assertEqual(
			(by_hand["manual"], by_hand["cost_begin"], by_hand["reason"]), (1, D("30.00"), "Grundstück")
		)
		self.assertEqual(
			bridge.transfer_inputs(
				[
					{"kind": "Umgliederung", "position": "bs.ass", "current": 1, "derived": 0, "name": "x"},
					{"derived": 1},
				]
			),
			[
				{
					"kind": "Umgliederung",
					"position": "bs.ass",
					"current": 1,
					"previous": None,
					"reason": None,
					"derived": 0,
				}
			],
		)

	def test_what_berechnen_reads_besides_the_positions(self):
		values = {
			"accounting_standard": "HGBM",
			"tax_finance_book": "Steuerbilanz",
			"bvv_contributions": 25000.0,
		}
		assets = [
			{
				"asset_category": "Software",
				"value_type": "StB",
				"manual": 0,
				"cost_begin": 100,
				"writeups": 5.0,
				"reason": "Zuschreibung",
			},
			{"position": "bs.ass.fixAss.tan", "manual": 1, "cost_begin": 30, "reason": "Grundstück"},
		]
		transfers = [
			{"kind": "Wertänderung", "position": "bs.ass", "current": 1.0, "reason": "x"},
			{"derived": 1, "current": 9},
		]
		found = bridge.inputs(values, assets, transfers)
		self.assertEqual(
			found,
			bridge.inputs(
				{**values, "bvv_contributions": "25000", "bvv_withdrawals": None},
				[{**assets[0], "cost_begin": 999, "writeups": "5"}, assets[1]],
				transfers[:1],
			),
		)
		for changed in (
			bridge.inputs({**values, "bvv_contributions": 1}, assets, transfers),
			bridge.inputs({**values, "accounting_standard": "HAOE"}, assets, transfers),
			bridge.inputs(values, [{**assets[0], "reason": "anders"}, assets[1]], transfers),
			bridge.inputs(values, [assets[0], {**assets[1], "cost_begin": 31}], transfers),
			bridge.inputs(values, assets, [{**transfers[0], "previous": 2}]),
		):
			self.assertNotEqual(found, changed)


class PositionRowsTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.ebilanz = ebilanz()
		cls.rows = bridge.position_rows(cls.ebilanz)

	def test_each_position_with_an_amount_in_the_order_of_the_presentation(self):
		rows = by_concept(self.rows)
		self.assertEqual(
			(rows[BANK]["computed"], rows[BANK]["ledger_amount"], rows[BANK]["tax_amount"]),
			(D("68500.00"), D("68500.00"), D("68500.00")),
		)
		self.assertEqual(rows[SALES_POSITION]["computed"], D("119000.00"))
		self.assertEqual(rows["bs.ass"]["computed"], D("110500.00"))
		self.assertEqual(
			{
				key: rows[BANK][key]
				for key in ("label", "component", "mark", "depth", "parent_concept", "davon_of", "nil")
			},
			{
				"label": "Guthaben bei Kreditinstituten",
				"component": "B",
				"mark": "rechnerisch notwendig",
				"depth": 3,
				"parent_concept": "bs.ass.currAss.cashEquiv",
				"davon_of": "",
				"nil": 0,
			},
		)
		concepts = [row["concept"] for row in self.rows]
		self.assertLess(concepts.index("bs.ass"), concepts.index(BANK))
		self.assertLess(concepts.index(BANK), concepts.index("is.netIncome"))
		self.assertLess(concepts.index("is.netIncome"), concepts.index("BVV.profitLoss"))

	def test_a_mussfeld_without_an_amount_is_nil(self):
		"""Leitfaden B.14.2.3."""
		row = by_concept(self.rows)["bs.eqLiab.equity.profitLoss"]
		self.assertEqual((row["nil"], row["computed"], row["tax_amount"]), (1, D("0"), D("0")))
		self.assertNotIn("bs.ass.currAss.cashEquiv.cash", by_concept(self.rows))

	def test_the_betriebsvermoegensvergleich_has_rows_of_its_own(self):
		"""Leitfaden B.14.3.2.12: the Betriebsvermögen of 67.500 € less that of 27.500 € gives the Jahresüberschuss."""
		rows = by_concept(self.rows)
		self.assertEqual(rows["BVV.profitLoss"]["computed"], D("40000.00"))
		self.assertEqual(rows["BVV.profitLoss.assetsCurrentYear"]["tax_amount"], D("67500.00"))
		self.assertEqual(rows["BVV.profitLoss.assetsCurrentYear"]["ledger_amount"], D("0"))
		self.assertEqual(
			(rows["BVV.profitLoss.contribution"]["nil"], rows["BVV.profitLoss.contribution"]["component"]),
			(1, "BVV"),
		)

	def test_a_corrected_position_shows_the_amount_of_the_books_and_its_sum_the_correction(self):
		sources = Sources(
			BOOKS, (Adjustment(BANK, D("70000.00"), "Kontoauszug"),), (SOFTWARE, LAND), equity=EQUITY
		)
		rows = by_concept(bridge.position_rows(ebilanz(sources), adjusted={gaap(BANK)}))
		self.assertEqual(rows[BANK]["computed"], D("68500.00"))
		self.assertEqual(rows["bs.ass"]["computed"], D("112000.00"))

	def test_a_corrected_davon_position_shows_the_value_of_the_bilanzzuordnung(self):
		sources = Sources(
			BOOKS,
			(Adjustment(DAVON, D("100.00"), DAVON_REASON), Adjustment(DAVON, D("150.00"), "Satzung")),
			(SOFTWARE, LAND),
			equity=EQUITY,
		)
		rows = by_concept(bridge.position_rows(ebilanz(sources), {DAVON: D("100.00")}, adjusted={DAVON}))
		self.assertEqual(
			(
				rows[DAVON]["computed"],
				rows[DAVON]["davon_of"],
				rows[DAVON]["parent_concept"],
				rows[DAVON]["mark"],
			),
			(D("100.00"), SALES_POSITION, "is.netIncome.netSales.statutoryDuties", "davon"),
		)

	def test_a_line_by_hand_keeps_its_own_row(self):
		sources = Sources(
			BOOKS,
			(Adjustment("is.netIncome.tax", D("9500.00"), "Bescheid"),),
			(SOFTWARE, LAND),
			equity=EQUITY,
		)
		rows = by_concept(bridge.position_rows(ebilanz(sources), manual={"is.netIncome.tax"}))
		self.assertNotIn("is.netIncome.tax", rows)
		self.assertEqual(rows["is.netIncome"]["computed"], D("39500.00"))

	def test_the_steuerbilanz_of_a_handelsbilanz_beside_it(self):
		"""Leitfaden B.15.1: the Steuerbilanz is the Handelsbilanz with its changes, the Ausgleichsposten of its own."""
		sources = Sources(HANDELSBILANZ, transfers=(SELFMADE, SALES, ACCRUAL), equity=EQUITY)
		rows = by_concept(bridge.position_rows(ebilanz(sources, accounting_standard="HGBM")))
		self.assertEqual(
			(
				rows["bs.ass.fixAss.intan.selfmade"]["computed"],
				rows["bs.ass.fixAss.intan.selfmade"]["tax_amount"],
			),
			(D("5000.00"), D("0.00")),
		)
		balance = rows["bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts"]
		self.assertEqual(
			(balance["nil"], balance["computed"], balance["tax_amount"]), (1, D("0"), D("-4000.00"))
		)
		self.assertEqual(rows["is.netIncome.collItemChangeProfitHbst"]["tax_amount"], D("1000.00"))


class AccountsAndTotalsTest(TestCase):
	def test_each_account_on_its_position_in_the_direction_of_the_position(self):
		"""Leitfaden A.13 and B.12: the Erlösschmälerung counts against the Umsatzerlöse."""
		rows = bridge.account_rows(ebilanz(), {"4700": "4700 - Erlösschmälerungen - BW"})
		row = next(row for row in rows if row["account_number"] == "4700")
		self.assertEqual(
			row,
			{
				"position": SALES_POSITION,
				"position_label": "Umsatzerlöse",
				"account": "4700 - Erlösschmälerungen - BW",
				"account_number": "4700",
				"account_label": "Erlösschmälerungen",
				"amount": D("-1000.00"),
			},
		)
		self.assertEqual(len(rows), len(BOOKS))
		self.assertIsNone(rows[0]["account"])

	def test_the_accounts_of_erpnext_by_their_number(self):
		balance = mapping.AccountBalance("1800 - Bank - BW", "1800", "Bank", Part.BALANCE_SHEET, D("10"))
		placement = Placement((Placed(balance, Rule("1800", BANK), BANK, BANK, D("10")),), (), ())
		self.assertEqual(bridge.account_names(placement), {"1800": "1800 - Bank - BW"})

	def test_the_totals_of_the_handelsbilanz_and_of_the_steuerbilanz(self):
		"""Rule 170405114: the Betriebsvermögen is the Eigenkapital less the „nicht gedeckter Fehlbetrag“."""
		self.assertEqual(
			bridge.totals(ebilanz()),
			{
				"total_assets": D("110500.00"),
				"total_equity_and_liabilities": D("110500.00"),
				"net_income": D("40000.00"),
				"tax_net_income": D("40000.00"),
				"tax_equity": D("67500.00"),
			},
		)
		sources = Sources(HANDELSBILANZ, transfers=(SELFMADE, SALES, ACCRUAL), equity=EQUITY)
		found = bridge.totals(ebilanz(sources, accounting_standard="HGBM"))
		self.assertEqual(
			(found["net_income"], found["tax_net_income"], found["tax_equity"]),
			(D("45000.00"), D("41000.00"), D("68500.00")),
		)
		empty = bridge.totals(ebilanz(Sources(())))
		self.assertEqual(set(empty.values()), {D("0")})


class AnlagenspiegelTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.structure = structure(view(), case())
		cls.software = CategoryValues(
			"Software",
			"0135",
			cost_begin=D("15000.00"),
			additions=D("3000.00"),
			adjustment=D("-500.00"),
			depreciation_begin=D("4000.00"),
			depreciation=D("2000.00"),
		)

	def test_the_assets_add_up_per_category_in_the_order_of_the_names(self):
		self.assertEqual(
			bridge.by_category(
				[
					CategoryValues("Software", "0135", additions=D("3000.00")),
					CategoryValues("Fahrzeuge", "0320", D("20000.00")),
					CategoryValues("Software", "0135", D("12000.00"), depreciation=D("1500.00")),
				]
			),
			[
				CategoryValues("Fahrzeuge", "0320", D("20000.00")),
				CategoryValues("Software", "0135", D("12000.00"), D("3000.00"), depreciation=D("1500.00")),
			],
		)
		self.assertEqual(bridge.by_category([]), [])

	def test_the_ueberleitung_sums_up_what_each_asset_has_more_in_the_steuerbilanz(self):
		"""Leitfaden B.14.12.1 c, d: a plot of land without depreciation has the same values in both books."""
		land = CategoryValues("Grundstücke", "0215", D("30000.00"))
		commercial = {
			"ACC-ASS-2026-00001": CategoryValues(
				"Software", "0135", additions=D("3000.00"), depreciation=D("500.00")
			),
			"ACC-ASS-2026-00002": CategoryValues(
				"Software", "0135", D("12000.00"), depreciation=D("1500.00")
			),
			"ACC-ASS-2026-00003": land,
			"ACC-ASS-2026-00004": CategoryValues(
				"Fahrzeuge", "0320", D("20000.00"), depreciation=D("4000.00")
			),
		}
		tax = {
			**commercial,
			"ACC-ASS-2026-00001": CategoryValues(
				"Software", "0135", additions=D("3000.00"), depreciation=D("1000.00")
			),
			"ACC-ASS-2026-00002": CategoryValues(
				"Software", "0135", D("12000.00"), depreciation=D("3000.00")
			),
			"ACC-ASS-2026-00005": CategoryValues(
				"Fahrzeuge", "0320", additions=D("800.00"), depreciation=D("800.00")
			),
		}
		self.assertEqual(
			bridge.transfer_values(tax, commercial),
			[
				CategoryValues("Fahrzeuge", "0320", additions=D("800.00"), depreciation=D("800.00")),
				CategoryValues("Software", "0135", depreciation=D("2000.00")),
			],
		)
		self.assertEqual(bridge.transfer_values({"ACC-ASS-2026-00003": land}, commercial), [])

	def test_a_row_per_category_on_the_position_of_its_fixed_asset_account(self):
		stored = [
			{
				"asset_category": "Software",
				"value_type": "StB",
				"depreciation_extraordinary": 500,
				"reason": "Wertminderung",
			},
			{"asset_category": "Software", "value_type": "HB", "writeups": 7},
			{"position": "bs.ass.fixAss.tan", "manual": 1, "cost_begin": 1},
		]
		(row,) = bridge.category_rows(
			[self.software], {"0135": "bs.ass.fixAss.intan.concessionBrands"}, "StB", stored
		)
		self.assertEqual(
			row,
			{
				"position": "bs.ass.fixAss.intan.concessionBrands",
				"value_type": "StB",
				"asset_category": "Software",
				"manual": 0,
				"cost_begin": D("15000.00"),
				"additions": D("3000.00"),
				"disposals": D("0"),
				"erp_adjustment": D("-500.00"),
				"depreciation_begin": D("4000.00"),
				"depreciation_regular": D("2000.00"),
				"depreciation_disposals": D("0"),
				**dict.fromkeys(bridge.MANUAL_COLUMNS, D("0.00")),
				"depreciation_extraordinary": D("500.00"),
				"reason": "Wertminderung",
			},
		)
		(unplaced,) = bridge.category_rows([self.software], {}, "StB")
		self.assertEqual((unplaced["position"], unplaced["reason"]), ("", ""))

	def test_the_ueberleitung_of_a_category_is_what_the_steuerbilanz_has_more(self):
		"""Leitfaden B.14.12.1 c, d."""
		tax = CategoryValues("Software", "0135", D("15000.00"), D("3000.00"), depreciation=D("3000.00"))
		self.assertTrue(self.software.less(self.software).empty)
		self.assertFalse(tax.less(self.software).empty)
		self.assertEqual(tax.less(self.software).plus(self.software), tax)
		self.assertEqual(
			tax.less(self.software),
			CategoryValues(
				"Software",
				"0135",
				adjustment=D("500.00"),
				depreciation_begin=D("-4000.00"),
				depreciation=D("1000.00"),
			),
		)

	def test_the_rows_by_hand_as_the_document_holds_them(self):
		stored = [
			{"asset_category": "Software", "value_type": "StB"},
			{
				"position": " de-gaap-ci:bs.ass.fixAss.tan ",
				"manual": 1,
				"cost_begin": "30000",
				"reason": " Grundstück ",
			},
		]
		(row,) = bridge.rows_by_hand(stored)
		self.assertEqual(
			(
				row["position"],
				row["value_type"],
				row["cost_begin"],
				row["reason"],
				row["manual"],
				row["asset_category"],
			),
			("bs.ass.fixAss.tan", "StB", D("30000.00"), "Grundstück", 1, None),
		)

	def test_the_rows_go_to_the_anlagenspiegel_of_the_core(self):
		rows = [
			{
				"position": "bs.ass.fixAss.intan.concessionBrands",
				"value_type": "StB",
				"asset_category": "Software",
				"cost_begin": 15000,
				"additions": 0,
				"reason": "",
			},
			{"position": "", "value_type": "StB", "asset_category": "Ohne Konto"},
			{
				"position": "bs.ass.fixAss.tan",
				"value_type": "HB",
				"cost_begin": 30000,
				"reason": "Grundstück",
			},
		]
		self.assertEqual(
			bridge.assets_of(rows),
			(
				Row(
					"bs.ass.fixAss.intan.concessionBrands",
					ValueType.STEUERBILANZ,
					cost_begin=D("15000.00"),
					source="Software",
				),
				Row(
					"bs.ass.fixAss.tan",
					ValueType.HANDELSBILANZ,
					cost_begin=D("30000.00"),
					reason="Grundstück",
				),
			),
		)
		with self.assertRaises(BridgeError) as raised:
			bridge.assets_of([{"position": "bs.ass.fixAss.tan", "value_type": "IFRS"}])
		self.assertEqual(raised.exception.values, (1, "IFRS"))

	def test_each_row_with_its_label_and_its_values_at_the_end_of_the_period(self):
		"""Leitfaden B.14.12.1: Buchwert = Anschaffungs- und Herstellungskosten ./. kumulierte Abschreibungen +
		Zuschreibungen."""
		(row,) = bridge.category_rows(
			[self.software], {"0135": "bs.ass.fixAss.intan.concessionBrands"}, "StB"
		)
		(found, unknown, unplaced) = bridge.fixed_asset_rows(
			self.structure,
			[
				{**row, "depreciation_extraordinary": D("500.00")},
				{"position": "bs.unknown", "value_type": "StB"},
				{"position": "", "value_type": "StB"},
			],
		)
		self.assertEqual(
			(found["position_label"], found["cost_end"], found["depreciation_end"], found["book_value_end"]),
			("entgeltlich erworbene Konzessionen", D("18000.00"), D("6500.00"), D("11500.00")),
		)
		self.assertEqual((unknown["position_label"], unknown["book_value_end"]), ("", D("0")))
		self.assertEqual((unplaced["position_label"], unplaced["cost_end"]), ("", D("0")))

	def test_an_adjustment_of_erpnext_is_taken_up_by_the_columns_by_hand(self):
		"""Leitfaden B.14.12.1; the report Asset Depreciations and Balances adds it to the Anschaffungskosten."""
		(row,) = bridge.category_rows(
			[self.software], {"0135": "bs.ass.fixAss.intan.concessionBrands"}, "StB"
		)
		(found,) = bridge.asset_findings(self.structure, [row])
		self.assertEqual(
			(found.code, found.severity, found.reference), ("SB-ANLAGE-ANPASSUNG", Severity.ERROR, "Software")
		)
		self.assertIn("-500,00 €", found.text)
		self.assertIn("0,00 €", found.text)
		taken = {**row, "depreciation_extraordinary": D("500.00"), "reason": "Wertminderung"}
		self.assertEqual(bridge.asset_findings(self.structure, [taken]), [])
		self.assertEqual(bridge.asset_findings(self.structure, [{"position": "", "manual": 1}]), [])

	def test_a_category_without_a_row_of_the_anlagenspiegel_holds_it_back(self):
		(row,) = bridge.category_rows([self.software], {"0135": BANK}, "StB")
		(unplaced,) = bridge.category_rows([self.software], {}, "StB")
		found = bridge.asset_findings(self.structure, [row, unplaced])
		self.assertEqual([finding.code for finding in found], ["SB-ANLAGE-POSITION", "SB-ANLAGE-POSITION"])
		long_name = "K" * 200
		(row,) = bridge.category_rows([CategoryValues(long_name, "")], {}, "StB")
		(found,) = bridge.asset_findings(self.structure, [row])
		self.assertEqual(len(found.reference), DATA_LENGTH)
		self.assertTrue(found.reference.endswith("…"))


class UeberleitungTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.structure = structure(view(), case(accounting_standard="HGBM"))

	def test_the_difference_of_the_finance_books_split_into_earlier_and_current_years(self):
		"""Leitfaden A.11, B.15.1: Deltawerte of the current and of earlier fiscal years; the Eigenkapital differs by the
		steuerlicher Ausgleichsposten alone."""
		commercial = (
			AccountBalance("0135", "EDV-Software", "bs.ass.fixAss.intan.concessionBrands", D("12000.00")),
			AccountBalance("4400", "Erlöse", SALES_POSITION, D("-1000.00")),
			AccountBalance("2970", "Gewinnvortrag", "bs.eqLiab.equity.retainedEarnings", D("-500.00")),
		)
		tax = (
			AccountBalance("0135", "EDV-Software", "bs.ass.fixAss.intan.concessionBrands", D("11000.00")),
			AccountBalance("4400", "Erlöse", SALES_POSITION, D("-1200.00")),
			AccountBalance("2970", "Gewinnvortrag", "bs.eqLiab.equity.retainedEarnings", D("-300.00")),
			AccountBalance("9999", "Unbekannt", "bs.unknown", D("5.00")),
		)
		opening_commercial = (
			AccountBalance("0135", "EDV-Software", "bs.ass.fixAss.intan.concessionBrands", D("14000.00")),
		)
		opening_tax = (
			AccountBalance("0135", "EDV-Software", "bs.ass.fixAss.intan.concessionBrands", D("13600.00")),
		)
		self.assertEqual(
			bridge.derived_transfers(self.structure, commercial, tax, opening_commercial, opening_tax),
			(
				Transfer(
					Kind.WERTAENDERUNG,
					"bs.ass.fixAss.intan.concessionBrands",
					D("-600.00"),
					D("-400.00"),
					DERIVED_REASON,
				),
				Transfer(Kind.WERTAENDERUNG, SALES_POSITION, D("200.00"), None, DERIVED_REASON),
			),
		)
		self.assertEqual(bridge.derived_transfers(self.structure, commercial, commercial), ())

	def test_a_difference_of_earlier_years_alone(self):
		balance = AccountBalance("0135", "EDV-Software", "bs.ass.fixAss.intan.concessionBrands", D("100.00"))
		changed = AccountBalance("0135", "EDV-Software", "bs.ass.fixAss.intan.concessionBrands", D("90.00"))
		(found,) = bridge.derived_transfers(self.structure, (balance,), (changed,), (balance,), (changed,))
		self.assertEqual((found.current, found.previous), (None, D("-10.00")))

	def test_the_entries_derived_and_by_hand(self):
		stored = [
			{
				"kind": "Wertänderung",
				"position": "bs.ass.fixAss.intan.selfmade",
				"current": -5000,
				"derived": 1,
			},
			{
				"kind": "Umgliederung",
				"position": " de-gaap-ci:bs.eqLiab.accruals.other ",
				"current": "-1000",
				"previous": 0,
				"reason": " Drohverlust ",
			},
		]
		rows = bridge.transfer_rows((SELFMADE,), stored)
		self.assertEqual(
			rows,
			[
				{
					"kind": "Wertänderung",
					"position": "bs.ass.fixAss.intan.selfmade",
					"current": D("-5000.00"),
					"previous": D("0"),
					"reason": SELFMADE.reason,
					"derived": 1,
				},
				{
					"kind": "Umgliederung",
					"position": "bs.eqLiab.accruals.other",
					"current": D("-1000.00"),
					"previous": D("0.00"),
					"reason": "Drohverlust",
					"derived": 0,
				},
			],
		)
		labelled = bridge.labelled_transfers(self.structure, [*rows, {"position": "bs.unknown"}])
		self.assertEqual(
			[row["position_label"] for row in labelled],
			["selbst geschaffene Schutzrechte", "sonstige Rückstellungen", ""],
		)
		self.assertEqual(
			bridge.transfers_of(rows),
			(
				Transfer(
					Kind.WERTAENDERUNG, "bs.ass.fixAss.intan.selfmade", D("-5000.00"), None, SELFMADE.reason
				),
				Transfer(Kind.UMGLIEDERUNG, "bs.eqLiab.accruals.other", D("-1000.00"), None, "Drohverlust"),
			),
		)
		self.assertEqual(
			bridge.transfers_of([{"position": "bs.eqLiab.accruals.other", "current": 1}])[0].kind,
			Kind.WERTAENDERUNG,
		)

	def test_refuses_an_entry_of_another_kind_or_without_a_position(self):
		with self.assertRaises(BridgeError) as raised:
			bridge.transfers_of([{"kind": "Storno", "position": "bs.ass"}])
		self.assertEqual(raised.exception.values, (1, "Storno"))
		with self.assertRaises(BridgeError) as raised:
			bridge.transfers_of([{"kind": "Wertänderung", "position": ""}, {"kind": "Wertänderung"}])
		self.assertEqual(raised.exception.values, (1, "Überleitungsrechnung"))


class BetriebsvermoegenTest(TestCase):
	def test_the_betriebsvermoegen_of_balances(self):
		"""Rule 170405114: Eigenkapital less the „nicht durch Eigenkapital gedeckter Fehlbetrag“."""
		found = structure(view(), case())
		self.assertEqual(bridge.equity_of(found, BOOKS), D("67500.00"))
		deficit = (
			AccountBalance("1800", "Bank", BANK, D("1000.00")),
			AccountBalance(
				"2900", "Gezeichnetes Kapital", "bs.eqLiab.equity.subscribed.corp", D("-25000.00")
			),
			AccountBalance("2990", "Fehlbetrag", "bs.ass.deficitNotCoveredByCapital", D("24000.00")),
		)
		self.assertEqual(bridge.equity_of(found, deficit), D("1000.00"))
		self.assertEqual(bridge.equity_of(found, ()), D("0"))

	def test_the_ausgleichsposten_of_the_last_stichtag_of_the_ueberleitung(self):
		"""Leitfaden B.14.3.2.12: the Betriebsvermögen of the Steuerbilanz at the beginning of the year."""
		calculated = calculate(structure(view(), case(accounting_standard="HGBM")), HANDELSBILANZ)
		earlier = Transfer(
			Kind.WERTAENDERUNG,
			"bs.ass.fixAss.intan.selfmade",
			D("-1000.00"),
			D("-3000.00"),
			"§ 5 Abs. 2 EStG",
		)
		self.assertEqual(bridge.last_ausgleichsposten(ueberleitung(calculated, (earlier,))), D("-3000.00"))
		self.assertEqual(bridge.last_ausgleichsposten(ueberleitung(calculated, (SELFMADE,))), D("0"))

	def test_what_the_books_do_not_say(self):
		"""Leitfaden B.14.3.2.12: zero is NIL, counted as zero."""
		self.assertEqual(
			bridge.equity_changes(
				D("27500.00"),
				override=30000,
				founding=25000,
				contributions="500",
				withdrawals=1000,
				adjustments=0,
			),
			EquityChanges(D("27500.00"), None, D("1000.00"), D("25500.00")),
		)
		self.assertEqual(
			bridge.equity_changes(D("27500.00"), override=0, override_reason=" Bescheid "),
			EquityChanges(D("0.00"), None, None, None),
		)
		self.assertEqual(
			bridge.equity_changes(D("0"), adjustments=12), EquityChanges(D("0"), D("12.00"), None, None)
		)


class StoredTest(TestCase):
	"""The E-Bilanz of the document as it is stored, for the Nutzdaten, the XBRL file and the checks before them."""

	@classmethod
	def setUpClass(cls):
		cls.sources = Sources(
			BOOKS,
			(
				Adjustment(DAVON, D("100.00"), DAVON_REASON),
				Adjustment(BANK, D("70000.00"), "Kontoauszug"),
				Adjustment("bs.eqLiab.accruals.other", D("1500.00"), "Gutachten"),
			),
			(SOFTWARE, LAND),
			equity=EQUITY,
		)
		cls.original = ebilanz(cls.sources)
		positions = bridge.position_rows(
			cls.original, {DAVON: D("100.00")}, adjusted={gaap(BANK), gaap("bs.eqLiab.accruals.other")}
		)
		for row in positions:
			row.update({"correction": 0, "correction_reason": "", "manual": 0, "reported": row["computed"]})
			if row["concept"] == BANK:
				row.update(
					{"correction": 70000, "correction_reason": "Kontoauszug", "reported": D("70000.00")}
				)
		positions.append(
			{
				"concept": "bs.eqLiab.accruals.other",
				"correction": 1500,
				"correction_reason": "Gutachten",
				"manual": 1,
				"reported": D("1500.00"),
			}
		)
		cls.positions = [
			row for row in positions if row["concept"] != "bs.eqLiab.accruals.other" or row["manual"]
		]
		cls.accounts = bridge.account_rows(cls.original)
		cls.fixed_assets = [
			{
				"position": "bs.ass.fixAss.intan.concessionBrands",
				"value_type": "StB",
				"asset_category": "Software",
				"cost_begin": 15000,
				"additions": 3000,
				"depreciation_begin": 4000,
				"depreciation_regular": 2000,
			},
			{
				"position": "bs.ass.fixAss.tan",
				"value_type": "StB",
				"asset_category": "Grundstücke",
				"cost_begin": 30000,
			},
		]

	def stored(self, positions=None, accounts=None):
		return build(
			structure(view(), case()),
			MASTER,
			bridge.sources_of(
				structure(view(), case()),
				positions=positions or self.positions,
				accounts=accounts or self.accounts,
				fixed_assets=self.fixed_assets,
				equity=EQUITY,
			),
		)

	def test_gives_the_e_bilanz_berechnen_wrote(self):
		stored = self.stored()
		self.assertEqual(stored.report, self.original.report)
		self.assertEqual(stored.findings, self.original.findings)
		self.assertEqual(stored.xml(), self.original.xml())
		self.assertEqual(bridge.differences(stored, self.positions), [])

	def test_the_sources_of_the_document(self):
		found = bridge.sources_of(
			structure(view(), case()),
			positions=self.positions,
			accounts=self.accounts,
			transfers=[{"kind": "Wertänderung", "position": "bs.ass", "current": 1, "reason": "x"}],
			first_year=True,
		)
		self.assertEqual(found.adjustments[0], Adjustment(DAVON, D("100.00"), DAVON_REASON))
		self.assertEqual(
			found.adjustments[1:],
			(
				Adjustment(BANK, D("70000.00"), "Kontoauszug"),
				Adjustment("bs.eqLiab.accruals.other", D("1500.00"), "Gutachten"),
			),
		)
		self.assertEqual(found.balances, BOOKS)
		self.assertEqual(len(found.transfers), 1)
		self.assertTrue(found.first_year)
		unknown = bridge.sources_of(
			structure(view(), case()),
			positions=(),
			accounts=[
				{"position": "bs.unknown", "account_number": "1", "account_label": "x", "amount": "-5"}
			],
		)
		self.assertEqual(unknown.balances, (AccountBalance("1", "x", "bs.unknown", D("-5.00")),))
		gone = bridge.sources_of(
			structure(view(), case()),
			positions=[{"concept": "bs.gone", "davon_of": "bs.ass", "computed": 5}],
			accounts=(),
		)
		self.assertEqual(gone.adjustments, ())
		with self.assertRaises(BridgeError) as raised:
			bridge.sources_of(
				structure(view(), case()), positions=(), accounts=[{"position": "", "amount": 1}]
			)
		self.assertEqual(raised.exception.values, (1, "Account Balances"))

	def test_names_the_positions_the_stored_document_no_longer_gives(self):
		positions = [
			*(row for row in self.positions if row["concept"] != "bs.ass"),
			{"concept": "bs.ass", "reported": D("1.00")},
			{"concept": "BVV.profitLoss", "reported": D("2.00")},
		]
		self.assertEqual(
			bridge.differences(self.stored(), positions),
			[("bs.ass", D("1.00"), D("112000.00")), ("BVV.profitLoss", D("2.00"), D("40000.00"))],
		)


class FindingsTest(TestCase):
	def test_the_findings_of_the_bilanzzuordnung_with_their_source_and_reference(self):
		found = (
			mapping.Finding(
				mapping.Code.UNPLACED,
				mapping.Severity.ERROR,
				"Kein Platz.",
				"§ 246 Abs. 1 Satz 1 HGB",
				"1590",
			),
			mapping.Finding(
				mapping.Code.CATCH_ALL,
				mapping.Severity.HINT,
				"Auffang.",
				"Leitfaden A.10.4",
				"",
				"bs.ass.other",
			),
		)
		first, second = bridge.placement_findings(Placement((), (), found))
		self.assertEqual(
			(first.code, first.severity, first.text, first.reference),
			("BILANZ-OHNE-PLATZ", Severity.ERROR, "Kein Platz. (Quelle: § 246 Abs. 1 Satz 1 HGB)", "1590"),
		)
		self.assertEqual((second.severity, second.reference), (Severity.HINT, "bs.ass.other"))

	def test_a_changed_taxonomy_holds_the_e_bilanz_back(self):
		"""§ 5b Abs. 1 Satz 1 EStG."""
		self.assertEqual(bridge.taxonomy_finding("6.9", True, ""), ())
		(found,) = bridge.taxonomy_finding(
			"6.9", False, "Die HGB-Taxonomie 6.9 weicht vom Manifest ab: verändert: package/x.xsd."
		)
		self.assertEqual(
			(found.code, found.severity, found.reference),
			("SB-TAXONOMIE", Severity.ERROR, "HGB-Taxonomie 6.9"),
		)
		self.assertTrue(found.text.startswith("Die HGB-Taxonomie 6.9 weicht vom Manifest ab"))

	def test_depreciation_not_posted_up_to_the_bilanzstichtag_holds_it_back(self):
		"""§ 253 Abs. 3 Satz 1 HGB: one finding per asset and finance book."""
		found = bridge.depreciation_findings(
			[
				Unposted("ACC-ASS-2026-00001", date(2026, 12, 31), D("250.00")),
				Unposted("ACC-ASS-2026-00001", date(2026, 11, 30), D("250.00")),
				Unposted("ACC-ASS-2026-00002", date(2026, 12, 31), D("100.00"), "Steuerbilanz"),
			],
			date(2026, 12, 31),
		)
		self.assertEqual(
			[finding.reference for finding in found], ["ACC-ASS-2026-00001", "ACC-ASS-2026-00002"]
		)
		self.assertIn("500,00 € ab dem 30.11.2026", found[0].text)
		self.assertIn("im Finanzbuch Steuerbilanz", found[1].text)
		self.assertTrue(all(finding.blocking for finding in found))
		self.assertEqual(bridge.depreciation_findings([], date(2026, 12, 31)), [])

	def test_a_missing_period_closing_voucher_is_a_hint_only(self):
		(found,) = bridge.closing_finding("Jahresabschluss", ())
		self.assertEqual((found.code, found.severity), ("SB-PERIODENABSCHLUSS", Severity.HINT))
		self.assertEqual(bridge.closing_finding("Jahresabschluss", ("PCV-2026",)), ())
		self.assertEqual(bridge.closing_finding("Eröffnungsbilanz", ()), ())

	def test_each_book_holds_the_depreciation_of_each_asset_once(self):
		"""ERPNext counts the entries without a finance book in every book (steuerbote/balances.py)."""
		scheduled = {
			"ACC-ASS-2026-00001": frozenset({""}),
			"ACC-ASS-2026-00002": frozenset({"Handelsbilanz", "Steuerbilanz"}),
			"ACC-ASS-2026-00003": frozenset({"Steuerbilanz"}),
			"ACC-ASS-2026-00004": frozenset({"", "Steuerbilanz"}),
			"ACC-ASS-2026-00005": frozenset(),
		}
		self.assertEqual(
			[(finding.code, finding.reference) for finding in bridge.schedule_findings(scheduled, ("",))],
			[
				("SB-ANLAGE-PLAN", "ACC-ASS-2026-00002"),
				("SB-ANLAGE-PLAN", "ACC-ASS-2026-00003"),
				("SB-ANLAGE-PLAN", "ACC-ASS-2026-00005"),
			],
		)
		found = bridge.schedule_findings(scheduled, ("Handelsbilanz", "Steuerbilanz"))
		self.assertEqual(
			[(finding.code, finding.reference) for finding in found],
			[
				("SB-ANLAGE-PLAN", "ACC-ASS-2026-00003"),
				("SB-ANLAGE-PLAN", "ACC-ASS-2026-00005"),
				("SB-ANLAGE-DOPPELT", "ACC-ASS-2026-00004"),
				("SB-ANLAGE-PLAN", "ACC-ASS-2026-00005"),
			],
		)
		self.assertTrue(all(finding.severity is Severity.ERROR for finding in found))
		self.assertIn(
			"hat aber keinen aktiven Abschreibungsplan im Finanzbuch Handelsbilanz und keinen ohne Finanzbuch",
			found[0].text,
		)
		self.assertIn("im Finanzbuch Steuerbilanz stünden beide Abschreibungen", found[2].text)
		(without,) = bridge.schedule_findings({"ACC-ASS-2026-00005": frozenset()}, ("",))
		self.assertIn("keinen aktiven Abschreibungsplan ohne Finanzbuch: In den Büchern", without.text)
		self.assertEqual(bridge.schedule_findings({}, ("",)), [])

	def test_every_template_is_one_the_frappe_layer_translates(self):
		self.assertEqual(
			set(bridge.MESSAGES),
			{
				bridge.NO_STATEMENT_TYPE,
				bridge.NO_ACCOUNTING_STANDARD,
				bridge.NO_VALUE_TYPE,
				bridge.NO_KIND,
				bridge.NO_POSITION,
				bridge.DOUBLED,
			},
		)
		self.assertEqual(bridge.TABLES, ("Positions", "Account Balances", "Überleitungsrechnung"))

	def test_the_codes_of_steuerbote_begin_with_sb_and_name_one_finding_each(self):
		self.assertEqual(len(set(bridge.CODES)), len(bridge.CODES))
		self.assertTrue(all(code.startswith("SB-") for code in bridge.CODES))
