"""Tests for steuerbote.balance_mapping_sync, plain unittest without Frappe so that every test runner collects them."""

import json
from datetime import date
from decimal import Decimal
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from steuerbote import balance_mapping_sync as sync
from steuerbote.balance_mapping_sync import (
	ACCOUNT,
	EXCLUDED,
	FILE_FORMAT,
	RULE,
	WATCHED,
	body_of_items,
	default_items,
	defaults_rows,
	dump_items,
	file_body,
	items_of_body,
	items_of_file_body,
	items_of_mapping,
	items_of_rows,
	load_items,
	rows_of_items,
	rows_of_mapping,
	rows_to_mapping,
)
from steuerbote.ebilanz.calculation import AccountBalance as EBilanzBalance
from steuerbote.ebilanz.calculation import Adjustment, calculate
from steuerbote.ebilanz.positions import Case, structure
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import Balance, RemainingTerm, build
from steuerbote.ustva import WatchLevel
from steuerbote.xbrl.changes import LiftError
from steuerbote.xbrl.facts import Periods
from steuerbote.xbrl.mapping import (
	AccountBalance,
	Books,
	DefaultExcluded,
	DefaultRule,
	Defaults,
	DefaultWatched,
	Excluded,
	Mapping,
	MappingError,
	Part,
	Purpose,
	Rule,
	Watched,
	place,
)
from steuerbote.xbrl.taxonomy import BALANCE_SHEET, GAAP_PREFIX, INCOME_STATEMENT
from steuerbote.xbrl.tests import positions, real
from steuerbote.xbrl.tests import test_changes as lift_case

BANK = "bs.ass.currAss.cashEquiv.bank"
BANK_LIABILITY = "bs.eqLiab.liab.bank.other"
SUBSCRIBED = "bs.eqLiab.equity.subscribed.corp"
TRADE_PAYABLES = "bs.eqLiab.liab.trade.genOther"


def rule_row(account_number: str | None, concept: Any = BANK, **fields: Any) -> dict:
	return {"account_number": account_number, "concept": concept, **fields}


MAPPING = Mapping(
	"SKR04",
	rules=(
		Rule("1800", BANK, opposite=BANK_LIABILITY),
		Rule("2900", SUBSCRIBED, purpose=Purpose.COMMERCIAL),
		Rule("3300", TRADE_PAYABLES, shareholder=True, remaining_term=RemainingTerm.UP_TO_ONE_YEAR),
	),
	watched=(Watched("1460", WatchLevel.HINT),),
	excluded=(Excluded("9000", "Saldenvorträge der Klasse 9"),),
)
ITEMS = {
	(ACCOUNT, "1800"): {
		"place": RULE,
		"concept": BANK,
		"opposite_concept": BANK_LIABILITY,
		"purpose": "both",
		"shareholder": None,
		"remaining_term": None,
	},
	(ACCOUNT, "2900"): {
		"place": RULE,
		"concept": SUBSCRIBED,
		"opposite_concept": None,
		"purpose": "commercial",
		"shareholder": None,
		"remaining_term": None,
	},
	(ACCOUNT, "3300"): {
		"place": RULE,
		"concept": TRADE_PAYABLES,
		"opposite_concept": None,
		"purpose": "both",
		"shareholder": "1",
		"remaining_term": "up to one year",
	},
	(ACCOUNT, "1460"): {"place": WATCHED, "level": "hint"},
	(ACCOUNT, "9000"): {"place": EXCLUDED, "reason": "Saldenvorträge der Klasse 9"},
}
BODY = {
	"rules": [
		{
			"account_number": "1800",
			"concept": BANK,
			"opposite_concept": BANK_LIABILITY,
			"purpose": "both",
			"shareholder": False,
			"remaining_term": None,
		},
		{
			"account_number": "2900",
			"concept": SUBSCRIBED,
			"opposite_concept": None,
			"purpose": "commercial",
			"shareholder": False,
			"remaining_term": None,
		},
		{
			"account_number": "3300",
			"concept": TRADE_PAYABLES,
			"opposite_concept": None,
			"purpose": "both",
			"shareholder": True,
			"remaining_term": "up to one year",
		},
	],
	"watched": [{"account_number": "1460", "level": "hint"}],
	"excluded": [{"account_number": "9000", "reason": "Saldenvorträge der Klasse 9"}],
}


class RowsToMappingTest(TestCase):
	def test_builds_rules_watched_and_excluded_accounts_from_rows(self):
		mapping = rows_to_mapping(
			"SKR04",
			[
				rule_row(
					"1800", f"de-gaap-ci:{BANK}", opposite_concept=BANK_LIABILITY, purpose="", shareholder=0
				),
				rule_row("2900", SUBSCRIBED, purpose="commercial", remaining_term=""),
				rule_row("3300", TRADE_PAYABLES, shareholder=1, remaining_term="up to one year"),
			],
			[{"account_number": "1460", "level": "hint"}],
			[{"account_number": "9000", "reason": " Saldenvorträge der\nKlasse 9 "}],
			"6.9",
		)
		self.assertEqual(mapping, MAPPING)

	def test_a_row_without_purpose_or_level_takes_the_default(self):
		"""A rule counts for both balance sheets and a watched account blocks unless its row says otherwise, as the
		defaults of the DocType have it."""
		mapping = rows_to_mapping(
			"SKR04", [rule_row("1800", purpose=None)], [{"account_number": "1460"}], [], "6.9"
		)
		self.assertEqual(
			(mapping.rules[0].purpose, mapping.watched[0].level), (Purpose.BOTH, WatchLevel.BLOCKING)
		)

	def test_ignores_the_other_fields_of_a_frappe_row(self):
		mapping = rows_to_mapping(
			"SKR04",
			[rule_row("1800", name="row-1", idx=1, account="1800 - Bank - MG", concept_label="Bank")],
			[],
			[],
			"6.9",
		)
		self.assertEqual(mapping.rules, (Rule("1800", BANK),))

	def test_validation_of_the_core_applies(self):
		with self.assertRaises(MappingError):
			rows_to_mapping("SKR04", [rule_row("1800"), rule_row("1800", SUBSCRIBED)], [], [], "6.9")
		with self.assertRaises(MappingError):
			rows_to_mapping("SKR04", [rule_row("1800", "")], [], [], "6.9")

	def test_a_row_without_account_is_refused_by_its_row_number(self):
		with self.assertRaises(MappingError) as caught:
			rows_to_mapping("SKR04", [], [{"idx": 3}], [], "6.9")
		self.assertEqual((caught.exception.template, caught.exception.values), (sync.NO_ACCOUNT, (3,)))
		with self.assertRaises(MappingError) as caught:
			rows_to_mapping("SKR04", [], [], [{"account": "9000 - Vortrag - MG", "reason": "x"}], "6.9")
		self.assertEqual(
			(caught.exception.template, caught.exception.values),
			(sync.NO_ACCOUNT_NUMBER, ("9000 - Vortrag - MG",)),
		)

	def test_rows_of_a_mapping_give_it_back(self):
		rows = rows_of_mapping(MAPPING)
		self.assertEqual(rows_to_mapping("SKR04", *rows, "6.9"), MAPPING)
		self.assertEqual(rows.rule_rows[2]["shareholder"], 1)
		self.assertEqual(rows.rule_rows[0]["remaining_term"], None)


TAX_RECEIVABLE = "bs.ass.currAss.receiv.other.vat"
TAX_LIABILITY = "bs.eqLiab.liab.other.theroffTax"
NETTED = Mapping(
	"SKR04",
	rules=(
		Rule("1406", TAX_RECEIVABLE, opposite=TAX_LIABILITY, netting="Umsatzsteuer"),
		Rule("3806", TAX_LIABILITY, opposite=TAX_RECEIVABLE, netting="Umsatzsteuer"),
	),
)


class NettingGroupTest(TestCase):
	"""The netting group of a rule (steuerbote.xbrl.mapping.Rule.netting) in the rows, the items, the body of the stored
	defaults and the file; a body written before the field existed reads as rules without a group."""

	def test_a_row_names_the_netting_group_of_its_rule(self):
		rows = rows_of_mapping(NETTED)
		self.assertEqual([row["netting_group"] for row in rows.rule_rows], ["Umsatzsteuer", "Umsatzsteuer"])
		self.assertEqual(rows_to_mapping("SKR04", *rows, "6.9"), NETTED)
		self.assertIsNone(rows_of_mapping(MAPPING).rule_rows[0]["netting_group"])

	def test_an_item_names_the_group_only_where_the_rule_has_one(self):
		items = items_of_mapping(NETTED)
		self.assertEqual(items[(ACCOUNT, "1406")]["netting_group"], "Umsatzsteuer")
		self.assertNotIn("netting_group", items_of_mapping(MAPPING)[(ACCOUNT, "1800")])
		self.assertEqual(rows_of_items(items), rows_of_mapping(NETTED))

	def test_the_body_holds_the_group_where_a_rule_has_one_and_reads_the_body_without_it(self):
		body = body_of_items(items_of_mapping(NETTED))
		self.assertEqual([row["netting_group"] for row in body["rules"]], ["Umsatzsteuer", "Umsatzsteuer"])
		self.assertEqual(items_of_body(body), items_of_mapping(NETTED))
		self.assertEqual(body_of_items(ITEMS), BODY)
		self.assertEqual(items_of_body(BODY), ITEMS)
		with self.assertRaises(MappingError):
			items_of_body({**body, "rules": [{**body["rules"][0], "netting_group": 1}]})


class ItemsTest(TestCase):
	"""What Vorgaben aktualisieren and the file of a mapping compare (steuerbote/mappings/diff.py): one item per
	account, so that a change of its place is one difference."""

	def test_each_account_is_an_item_with_its_place_and_its_fields_as_text(self):
		self.assertEqual(items_of_mapping(MAPPING), ITEMS)
		self.assertEqual(list(items_of_mapping(MAPPING)), list(ITEMS))

	def test_items_of_rows_read_the_rows_as_the_core_does(self):
		rows = rows_of_mapping(MAPPING)
		self.assertEqual(items_of_rows(*rows), ITEMS)

	def test_rows_of_items_give_the_rows_back(self):
		self.assertEqual(rows_of_items(ITEMS), rows_of_mapping(MAPPING))

	def test_the_body_holds_the_rows_by_kind_with_the_flag_as_yes_or_no(self):
		self.assertEqual(body_of_items(ITEMS), BODY)
		self.assertEqual(items_of_body(BODY), ITEMS)
		self.assertEqual(items_of_body(json.loads(json.dumps(BODY))), ITEMS)

	def test_the_stored_defaults_are_the_canonical_json_of_the_body(self):
		text = dump_items(ITEMS)
		self.assertEqual(text, json.dumps(BODY, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
		self.assertEqual(load_items(text), ITEMS)
		with self.assertRaises(MappingError) as caught:
			load_items("{")
		self.assertEqual(caught.exception.template, sync.NOT_JSON)

	def test_a_body_of_another_shape_is_refused(self):
		for body in (
			[],
			{"rules": []},
			{**BODY, "checks": []},
			{**BODY, "rules": {}},
			{**BODY, "watched": [{"account_number": "1460"}]},
			{**BODY, "excluded": [{"account_number": 9000, "reason": "x"}]},
			{**BODY, "rules": [{**BODY["rules"][0], "shareholder": "yes"}]},
			{**BODY, "rules": [{**BODY["rules"][0], "concept": None}]},
		):
			with self.subTest(body=body), self.assertRaises(MappingError):
				items_of_body(body)

	def test_the_file_holds_the_version_of_the_taxonomy_the_mapping_and_the_defaults_it_took_over(self):
		"""The positions of the rows are those of one version of the taxonomy, so the file names it."""
		self.assertEqual(
			file_body("6.9", ITEMS, None), {"taxonomy_version": "6.9", "mapping": BODY, "defaults": None}
		)
		self.assertEqual(
			items_of_file_body({"taxonomy_version": "6.9", "mapping": BODY, "defaults": BODY}),
			("6.9", ITEMS, ITEMS),
		)
		self.assertEqual(
			items_of_file_body({"taxonomy_version": "6.9", "mapping": BODY, "defaults": None}),
			("6.9", ITEMS, None),
		)
		for body in (
			{"mapping": BODY, "defaults": None},
			{"taxonomy_version": 6.9, "mapping": BODY, "defaults": None},
			{"taxonomy_version": "6.9", "mapping": BODY},
			[],
		):
			with self.subTest(body=body), self.assertRaises(MappingError) as caught:
				items_of_file_body(body)
			self.assertEqual(caught.exception.template, sync.NOT_A_FILE_BODY)
		self.assertEqual(FILE_FORMAT, "steuerbote/balance-sheet-mapping")

	def test_every_template_is_one_the_frappe_layer_translates(self):
		self.assertEqual(
			set(sync.MESSAGES),
			{
				sync.NO_ACCOUNT,
				sync.NO_ACCOUNT_NUMBER,
				sync.NOT_JSON,
				sync.NOT_A_BODY,
				sync.BAD_ROWS,
				sync.NOT_A_FILE_BODY,
			},
		)


TEST_DEFAULTS = Defaults(
	"SKR04",
	"6.9",
	rules=(DefaultRule("1800-1849", BANK, opposite=BANK_LIABILITY), DefaultRule("2900", SUBSCRIBED)),
	watched=(DefaultWatched("1460", WatchLevel.HINT),),
	excluded=(DefaultExcluded("9000-9009", "Saldenvorträge der Klasse 9"),),
)


class DefaultsRowsTest(TestCase):
	def setUp(self):
		patcher = patch.object(sync, "defaults_for", return_value=TEST_DEFAULTS)
		self.defaults_for = patcher.start()
		self.addCleanup(patcher.stop)

	def test_the_defaults_of_a_chart_give_rows_for_the_accounts_a_company_has(self):
		rows = defaults_rows("SKR04", "6.9", {"1810", "1460", "9001", "4400"})
		self.defaults_for.assert_called_with("SKR04", "6.9")
		self.assertEqual(
			rows_to_mapping("SKR04", *rows, "6.9"),
			Mapping(
				"SKR04",
				rules=(Rule("1810", BANK, opposite=BANK_LIABILITY),),
				watched=(Watched("1460", WatchLevel.HINT),),
				excluded=(Excluded("9001", "Saldenvorträge der Klasse 9"),),
			),
		)

	def test_a_watched_account_keeps_the_level_of_the_company(self):
		rows = defaults_rows("SKR04", "6.9", {"1460"}, {"1460": "blocking"})
		self.assertEqual(rows.watched_rows, [{"account_number": "1460", "level": "blocking"}])

	def test_the_default_items_take_the_levels_of_the_defaults(self):
		self.assertEqual(
			default_items("SKR04", "6.9", {"1460", "2900"}),
			{
				(ACCOUNT, "2900"): {
					"place": RULE,
					"concept": SUBSCRIBED,
					"opposite_concept": None,
					"purpose": "both",
					"shareholder": None,
					"remaining_term": None,
				},
				(ACCOUNT, "1460"): {"place": WATCHED, "level": "hint"},
			},
		)

	def test_names_the_accounts_of_a_company_the_defaults_leave_without_a_place(self):
		self.assertEqual(sync.without_defaults("SKR04", "6.9", {"1810", "4400", "0027"}), ("0027", "4400"))


def placed_balances():
	"""Books of a small GmbH on the positions of the extended mini taxonomy (steuerbote/xbrl/tests/positions.py)."""
	rules = (
		Rule("1800", "bs.ass.currAss.cashEquiv.bank", opposite="bs.eqLiab.liab.bank"),
		Rule("1810", "bs.ass.currAss.cashEquiv.bank", opposite="bs.eqLiab.liab.bank"),
		Rule(
			"1210", "bs.ass.currAss.receiv.trade.above1year", remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS
		),
		Rule("3500", "bs.eqLiab.liab.other", shareholder=True, remaining_term=RemainingTerm.UP_TO_ONE_YEAR),
		Rule("2900", "bs.eqLiab.equity.subscribed.corp"),
		Rule("4400", "is.netIncome.netSales"),
		Rule("4401", "is.netIncome.netSales"),
	)
	books = Books(
		(
			AccountBalance("1800 - Bank - MG", "1800", "Bank", Part.BALANCE_SHEET, Decimal("30000")),
			AccountBalance("1810 - Bank 2 - MG", "1810", "Bank 2", Part.BALANCE_SHEET, credit=Decimal("500")),
			AccountBalance(
				"1210 - Forderungen - MG", "1210", "Forderungen", Part.BALANCE_SHEET, Decimal("2000")
			),
			AccountBalance(
				"3500 - Darlehen - MG", "3500", "Darlehen", Part.BALANCE_SHEET, credit=Decimal("1500")
			),
			AccountBalance(
				"2900 - Kapital - MG",
				"2900",
				"Gezeichnetes Kapital",
				Part.BALANCE_SHEET,
				credit=Decimal("25000"),
			),
			AccountBalance(
				"4400 - Erlöse - MG", "4400", "Erlöse 19 %", Part.INCOME_STATEMENT, credit=Decimal("5500")
			),
			AccountBalance("4401 - Erlöse - MG", "4401", "", Part.INCOME_STATEMENT, Decimal("500")),
		)
	)
	return place(Mapping("SKR04", rules=rules), books, positions.view(), Purpose.BOTH)


class StatementBalancesTest(TestCase):
	"""The input of the Jahresabschluss: „Balance(concept, amount, shareholder, remaining_term, source)“ with the
	balance as debit minus credit (steuerbote/hgb/statement.py)."""

	def test_each_placed_balance_is_a_balance_of_the_statement_with_the_flags_of_its_rule(self):
		self.assertEqual(
			sync.statement_balances(placed_balances()),
			(
				Balance("bs.ass.currAss.cashEquiv.bank", Decimal("30000"), source="1800 - Bank - MG"),
				Balance("bs.eqLiab.liab.bank", Decimal("-500"), source="1810 - Bank 2 - MG"),
				Balance(
					"bs.ass.currAss.receiv.trade.above1year",
					Decimal("2000"),
					remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
					source="1210 - Forderungen - MG",
				),
				Balance(
					"bs.eqLiab.liab.other",
					Decimal("-1500"),
					shareholder=True,
					remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
					source="3500 - Darlehen - MG",
				),
				Balance("bs.eqLiab.equity.subscribed.corp", Decimal("-25000"), source="2900 - Kapital - MG"),
				Balance("is.netIncome.netSales", Decimal("-5500"), source="4400 - Erlöse - MG"),
				Balance("is.netIncome.netSales", Decimal("500"), source="4401 - Erlöse - MG"),
			),
		)


class EBilanzBalancesTest(TestCase):
	"""The input of the E-Bilanz (steuerbote/ebilanz/calculation.py): „an AccountBalance per account, its number and
	description, the position it maps to ... and its balance as debit minus credit“, and the „davon“ positions as
	lines by hand, since a davon position takes no balance of the books."""

	def test_each_placed_balance_is_an_account_balance_on_the_position_its_value_counts_in(self):
		"""An account without a label is described by its name, as the elements of a Kontensaldo „dürfen nicht leer
		übermittelt werden“ (Technischer Leitfaden zur HGB-Taxonomie 6.9, B.12)."""
		self.assertEqual(
			sync.ebilanz_balances(placed_balances()),
			(
				EBilanzBalance("1800", "Bank", "bs.ass.currAss.cashEquiv.bank", Decimal("30000")),
				EBilanzBalance("1810", "Bank 2", "bs.eqLiab.liab.bank", Decimal("-500")),
				EBilanzBalance("1210", "Forderungen", "bs.ass.currAss.receiv.trade", Decimal("2000")),
				EBilanzBalance("3500", "Darlehen", "bs.eqLiab.liab.other", Decimal("-1500")),
				EBilanzBalance(
					"2900", "Gezeichnetes Kapital", "bs.eqLiab.equity.subscribed.corp", Decimal("-25000")
				),
				EBilanzBalance("4400", "Erlöse 19 %", "is.netIncome.netSales", Decimal("-5500")),
				EBilanzBalance("4401", "4401 - Erlöse - MG", "is.netIncome.netSales", Decimal("500")),
			),
		)

	def test_the_balances_of_the_previous_year_are_marked_for_the_handelsbilanz(self):
		self.assertEqual(
			{balance.prior for balance in sync.ebilanz_balances(placed_balances(), prior=True)}, {True}
		)

	def test_a_davon_position_has_its_value_besides(self):
		self.assertEqual(
			sync.davon_values(placed_balances(), positions.view()),
			{"bs.ass.currAss.receiv.trade.above1year": Decimal("2000")},
		)

	def test_a_davon_position_is_a_line_by_hand_with_the_sum_of_its_accounts(self):
		self.assertEqual(
			sync.ebilanz_davon_lines(placed_balances(), positions.view()),
			(Adjustment("bs.ass.currAss.receiv.trade.above1year", Decimal("2000"), sync.DAVON_REASON),),
		)
		(line,) = sync.ebilanz_davon_lines(placed_balances(), positions.view(), prior=True)
		self.assertTrue(line.prior)


class JahresabschlussTest(TestCase):
	"""The books of an invented small GmbH in SKR04 through the mapping into the Jahresabschluss of
	steuerbote/hgb/statement.py and the calculation of the E-Bilanz (steuerbote/ebilanz/calculation.py), against the
	package 6.9 (steuerbote/xbrl/tests/real.py)."""

	def setUp(self):
		up_to_one_year = RemainingTerm.UP_TO_ONE_YEAR
		gross_sales = "is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales"
		self.mapping = Mapping(
			"SKR04",
			rules=(
				Rule("0135", "bs.ass.fixAss.intan.concessionBrands"),
				Rule("1200", "bs.ass.currAss.receiv.trade.other", remaining_term=up_to_one_year),
				Rule("1800", "bs.ass.currAss.cashEquiv.bank", opposite="bs.eqLiab.liab.bank.other"),
				Rule("2900", "bs.eqLiab.equity.subscribed.corp"),
				Rule("3300", "bs.eqLiab.liab.trade.genOther", remaining_term=up_to_one_year),
				Rule("3806", "bs.eqLiab.liab.other.theroffTax", remaining_term=up_to_one_year),
				Rule("4400", f"{gross_sales}.generalRateVAT"),
				Rule("6310", "is.netIncome.regular.operatingTC.otherCost.leaseFix.other"),
				Rule(
					"6640",
					"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.entertainment.deductible",
				),
			),
		)
		self.books = Books(
			(
				account("0135", "EDV-Software", debit="2000"),
				account("1200", "Forderungen aus Lieferungen und Leistungen", debit="5950"),
				account("1800", "Bank", debit="33000"),
				account("2900", "Gezeichnetes Kapital", credit="25000"),
				account("3300", "Verbindlichkeiten aus Lieferungen und Leistungen", credit="1190"),
				account("3806", "Umsatzsteuer 19 %", credit="950"),
				account("4400", "Erlöse 19 % USt", Part.INCOME_STATEMENT, credit="20000"),
				account("6310", "Miete", Part.INCOME_STATEMENT, debit="6000"),
				account("6640", "Bewirtungskosten", Part.INCOME_STATEMENT, debit="190"),
			)
		)

	def test_the_jahresabschluss_balances_with_the_result_of_the_guv(self):
		taxonomy = real.view()
		placement = place(self.mapping, self.books, taxonomy, Purpose.COMMERCIAL)
		self.assertEqual((placement.findings, placement.left_out), ((), ()))
		statement = build(
			2026,
			SizeClass.KLEIN,
			sync.statement_balances(placement),
			parents=taxonomy.parents((BALANCE_SHEET, INCOME_STATEMENT)),
		)
		self.assertEqual([finding.text for finding in statement.findings if finding.blocking], [])
		self.assertEqual(statement.income_statement.net_income, Decimal("13810"))
		self.assertEqual(statement.balance_sheet.difference, Decimal(0))
		self.assertEqual(statement.balance_sheet.aktiva_total, Decimal("40950"))

	def test_the_e_bilanz_takes_the_balances_and_a_davon_position_and_balances_as_well(self):
		"""The same books with interest from an affiliated company through the calculation of the E-Bilanz of an
		Einheitsbilanz (steuerbote/ebilanz/calculation.py): each account a Kontensaldo on the position its value counts
		in, the davon position a line by hand, and Aktiva equal to Passiva with the Jahresüberschuss of the GuV."""
		taxonomy = real.view()
		interest = "is.netIncome.regular.fin.netInterest.income"
		mapping = Mapping("SKR04", rules=(*self.mapping.rules, Rule("7100", f"{interest}.assoc")))
		books = Books(
			(
				*(balance for balance in self.books.balances if balance.number != "1800"),
				account("1800", "Bank", debit="33100"),
				account(
					"7100", "Zinserträge aus verbundenen Unternehmen", Part.INCOME_STATEMENT, credit="100"
				),
			)
		)
		placement = place(mapping, books, taxonomy, Purpose.BOTH)
		calculated = calculate(
			structure(taxonomy, Case("GmbH", Periods(date(2026, 1, 1), date(2026, 12, 31)))),
			sync.ebilanz_balances(placement),
			sync.ebilanz_davon_lines(placement, taxonomy),
		)
		self.assertEqual(calculated.findings, ())
		self.assertEqual(len(calculated.lines), 10)
		self.assertEqual(
			(calculated.lines[-1].account, calculated.lines[-1].concept),
			("7100", f"{GAAP_PREFIX}:{interest}"),
		)
		self.assertEqual(
			(calculated.amount(f"{interest}.assoc"), calculated.amount(interest)),
			(Decimal("100"), Decimal("100")),
		)
		self.assertEqual(
			(calculated.amount("bs.ass"), calculated.amount("bs.eqLiab"), calculated.amount("is.netIncome")),
			(Decimal("41050"), Decimal("41050"), Decimal("13910")),
		)


def account(number: str, label: str, part: Part = Part.BALANCE_SHEET, debit: str = "0", credit: str = "0"):
	return AccountBalance(f"{number} - {label} - SG", number, label, part, Decimal(debit), Decimal(credit))


class LiftedItemsTest(TestCase):
	"""Auf neue Taxonomie heben and the import of a file of an earlier version, on the items of a mapping: the invented
	SKR04 company of steuerbote/xbrl/tests/test_changes.py through the changes of the mini taxonomies."""

	def test_lifts_the_items_through_the_changes_against_the_view_of_the_later_version(self):
		items = items_of_mapping(lift_case.SKR04)
		lifted, found = sync.lifted_items(
			"SKR04",
			items,
			"6.9",
			"6.10",
			taxonomy=lift_case.target(),
			parts=lift_case.PARTS,
			steps=(lift_case.MINI_CHANGES,),
		)
		self.assertEqual(lifted[(ACCOUNT, "1350")]["concept"], lift_case.DIGITAL)
		self.assertEqual(lifted[(ACCOUNT, "0440")], {"place": WATCHED, "level": WatchLevel.BLOCKING.value})
		unchanged = {key: fields for key, fields in items.items() if key[1] not in ("0440", "1350")}
		self.assertEqual({key: lifted[key] for key in unchanged}, unchanged)
		self.assertEqual(found.renamed, (("1350", lift_case.CRYPTO, lift_case.DIGITAL),))
		self.assertEqual([decision.rule.account_number for decision in found.to_decide], ["0440"])
		self.assertEqual(found.mussfelder, (lift_case.GRUNDSTEUER,))
		self.assertEqual(found.mapping.taxonomy_version, "6.10")

	def test_the_changes_of_6_10_rename_no_position(self):
		items = items_of_mapping(Mapping("SKR04", rules=(Rule("1800", BANK, opposite=BANK_LIABILITY),)))
		lifted, found = sync.lifted_items("SKR04", items, "6.9", "6.10")
		self.assertEqual(lifted, items)
		self.assertEqual((found.renamed, found.to_decide), ((), ()))

	def test_climbs_to_a_later_version_only(self):
		with self.assertRaisesRegex(LiftError, "not from 6.10 to 6.9"):
			sync.lifted_items("SKR04", {}, "6.10", "6.9")
