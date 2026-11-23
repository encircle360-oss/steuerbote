"""Tests for steuerbote.balance_mapping_sync, plain unittest without Frappe so that every test runner collects them."""

import json
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
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import Balance, RemainingTerm, build
from steuerbote.ustva import WatchLevel
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
from steuerbote.xbrl.taxonomy import BALANCE_SHEET, INCOME_STATEMENT
from steuerbote.xbrl.tests import positions, real

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

	def test_the_file_holds_the_mapping_and_the_defaults_it_took_over(self):
		self.assertEqual(file_body(ITEMS, None), {"mapping": BODY, "defaults": None})
		self.assertEqual(items_of_file_body({"mapping": BODY, "defaults": BODY}), (ITEMS, ITEMS))
		self.assertEqual(items_of_file_body({"mapping": BODY, "defaults": None}), (ITEMS, None))
		with self.assertRaises(MappingError) as caught:
			items_of_file_body({"mapping": BODY})
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


class KontennachweisTest(TestCase):
	"""The input of the E-Bilanz: the value of each position and the Kontensalden, one per account with a balance."""

	def test_the_value_of_each_position_adds_up_its_accounts_in_its_direction(self):
		"""„Entspricht die Soll/Haben-Auszeichnung eines Kontos der Soll/Haben-Auszeichnung der Position, dann ist der
		Kontensaldo unverändert ... zu addieren“ (Technischer Leitfaden zur HGB-Taxonomie 6.9, A.13)."""
		self.assertEqual(
			sync.position_values(placed_balances()),
			{
				"bs.ass.currAss.cashEquiv.bank": Decimal("30000"),
				"bs.eqLiab.liab.bank": Decimal("500"),
				"bs.ass.currAss.receiv.trade": Decimal("2000"),
				"bs.eqLiab.liab.other": Decimal("1500"),
				"bs.eqLiab.equity.subscribed.corp": Decimal("25000"),
				"is.netIncome.netSales": Decimal("5000"),
			},
		)

	def test_a_davon_position_has_its_value_besides(self):
		self.assertEqual(
			sync.davon_values(placed_balances(), positions.view()),
			{"bs.ass.currAss.receiv.trade.above1year": Decimal("2000")},
		)

	def test_one_kontensaldo_per_account_on_the_position_its_value_counts_in(self):
		"""„der dem Konto zugeordneten Position (technisch: QName), der Kontonummer ..., der Kontobezeichnung ... und
		dem Kontosaldo“ (Leitfaden A.12); „Die Summe der Werte zum Element „Kontosaldo“ soll dem Wert der
		Taxonomieposition entsprechen“ (Technischer Leitfaden 6.10, B.12.1). An account without a label is described
		by its name."""
		lines = sync.kontennachweis(placed_balances())
		self.assertEqual(
			[(line.position_name, line.account_number, line.description, line.amount) for line in lines],
			[
				("de-gaap-ci:bs.ass.currAss.cashEquiv.bank", "1800", "Bank", Decimal("30000")),
				("de-gaap-ci:bs.ass.currAss.receiv.trade", "1210", "Forderungen", Decimal("2000")),
				(
					"de-gaap-ci:bs.eqLiab.equity.subscribed.corp",
					"2900",
					"Gezeichnetes Kapital",
					Decimal("25000"),
				),
				("de-gaap-ci:bs.eqLiab.liab.bank", "1810", "Bank 2", Decimal("500")),
				("de-gaap-ci:bs.eqLiab.liab.other", "3500", "Darlehen", Decimal("1500")),
				("de-gaap-ci:is.netIncome.netSales", "4400", "Erlöse 19 %", Decimal("5500")),
				("de-gaap-ci:is.netIncome.netSales", "4401", "4401 - Erlöse - MG", Decimal("-500")),
			],
		)
		by_position = {}
		for line in lines:
			by_position[line.position] = by_position.get(line.position, Decimal(0)) + line.amount
		self.assertEqual(by_position, sync.position_values(placed_balances()))


class JahresabschlussTest(TestCase):
	"""The books of an invented small GmbH in SKR04 through the mapping into the Jahresabschluss of
	steuerbote/hgb/statement.py and the values of the E-Bilanz, against the package 6.9 (steuerbote/xbrl/tests/
	real.py)."""

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

	def test_the_kontensalden_of_the_e_bilanz_add_up_to_the_values_of_their_positions(self):
		placement = place(self.mapping, self.books, real.view(), Purpose.BOTH)
		lines = sync.kontennachweis(placement)
		self.assertEqual(len(lines), 9)
		self.assertEqual(
			sum(line.amount for line in lines if line.position.startswith("bs.ass")), Decimal("40950")
		)
		self.assertEqual(sync.position_values(placement)["bs.eqLiab.liab.other.theroffTax"], Decimal("950"))


def account(number: str, label: str, part: Part = Part.BALANCE_SHEET, debit: str = "0", credit: str = "0"):
	return AccountBalance(f"{number} - {label} - SG", number, label, part, Decimal(debit), Decimal(credit))
