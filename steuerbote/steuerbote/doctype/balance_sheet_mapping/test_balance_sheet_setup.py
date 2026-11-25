"""Steuerbote einrichten makes the Balance Sheet Mapping of a company through the hook steuerbote_setup_steps: with the
defaults of its chart for the taxonomy, the accounts they give no place and the taxonomy it waits for, without rows for
a chart of its own or an ambiguous one, and not again once the company has one, unless that one waits for the defaults
of today, as a mapping made while they were the empty table of revision 0."""

from contextlib import contextmanager
from datetime import date
from types import MappingProxyType
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import balance_mapping_sync
from steuerbote.ebilanz import defaults as ebilanz_defaults
from steuerbote.setup.steps import Note, Outcome
from steuerbote.steuerbote import setup
from steuerbote.steuerbote.doctype.balance_sheet_mapping import balance_sheet_mapping
from steuerbote.steuerbote.doctype.balance_sheet_mapping import setup as step
from steuerbote.tests.helpers import make_account, make_company
from steuerbote.ustva import WatchLevel
from steuerbote.xbrl.mapping import DefaultExcluded, DefaultRule, Defaults, DefaultWatched
from steuerbote.xbrl.tests import positions

# The tests build their own companies and accounts and need none of ERPNext's test records.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Account"]

MAPPING = "Balance Sheet Mapping"
SKR04_COMPANY = "Steuerbote Test Einrichtung Bilanz GmbH"
OWN_COMPANY = "Steuerbote Test Einrichtung Bilanz Eigen GmbH"
AMBIGUOUS_COMPANY = "Steuerbote Test Einrichtung Bilanz Zwei GmbH"
TODAY = date(2026, 11, 23)
# SKR04: the three accounts of its signature, a bank and the Gezeichnetes Kapital.
SKR04_ACCOUNTS = {
	"4400": ("Erlöse 19 % USt", "Income"),
	"3806": ("Umsatzsteuer 19 %", "Liability"),
	"1406": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1800": ("Bank", "Asset"),
	"2900": ("Gezeichnetes Kapital", "Equity"),
}
OWN_ACCOUNTS = {"100": ("Umsatz", "Income"), "200": ("Bank", "Asset")}
# The signatures of SKR03 and of SKR04 at once.
AMBIGUOUS_ACCOUNTS = {
	**{number: SKR04_ACCOUNTS[number] for number in ("4400", "3806", "1406")},
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
}
DEFAULTS = Defaults(
	"SKR04",
	"6.9",
	rules=(
		DefaultRule("1800-1849", "bs.ass.currAss.cashEquiv.bank", opposite="bs.eqLiab.liab.bank"),
		DefaultRule("2900", "bs.eqLiab.equity.subscribed.corp"),
		DefaultRule("4400", "is.netIncome.netSales"),
	),
	watched=(DefaultWatched("1406", WatchLevel.HINT),),
	excluded=(DefaultExcluded("9000-9009", "Saldenvorträge der Klasse 9"),),
)


def company_with(name: str, abbr: str, accounts: dict[str, tuple[str, str]]) -> None:
	make_company(name, abbr)
	for number, (label, root_type) in accounts.items():
		if not frappe.db.exists("Account", {"company": name, "account_number": number}):
			make_account(name, number, label, root_type)


def result_of(done, key: str):
	(result,) = (result for found, result in done if found.key == key)
	return result


@contextmanager
def at_revision_0():
	"""The empty table of revision 0, before the defaults of the DATEV charts."""
	with (
		patch.object(balance_mapping_sync, "defaults_for", return_value=Defaults("SKR04", "6.9")),
		patch.object(ebilanz_defaults, "REVISIONS", MappingProxyType({"6.9": 0})),
	):
		yield


class IntegrationTestBalanceSheetSetup(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for name, abbr, accounts in (
			(SKR04_COMPANY, "STEB4", SKR04_ACCOUNTS),
			(OWN_COMPANY, "STEBE", OWN_ACCOUNTS),
			(AMBIGUOUS_COMPANY, "STEBZ", AMBIGUOUS_ACCOUNTS),
		):
			company_with(name, abbr, accounts)

	def setUp(self):
		super().setUp()
		for company in (SKR04_COMPANY, OWN_COMPANY, AMBIGUOUS_COMPANY):
			for doctype in (MAPPING, "Income Tax Mapping", "VAT Return Mapping", "VAT Return Settings"):
				frappe.delete_doc_if_exists(doctype, company, force=True)
		self.installed(None)

	def installed(self, view) -> None:
		patcher = patch.object(balance_sheet_mapping, "position_taxonomy", return_value=view)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_the_setup_runs_the_step_of_the_hook_last(self):
		"""Last of the steps that make a document; only the steps on the USt-IdNrn. of partners and on the ERiC
		Settings follow it."""
		self.assertEqual(
			[found.key for found in setup.setup_steps()][-5:],
			[
				"balance_sheet_mapping",
				"vat_id_label",
				"erpnext_germany_vat_id_check",
				"vat_id_automatic_check",
				"eric_settings",
			],
		)

	def test_makes_the_mapping_with_the_defaults_of_revision_0_and_leaves_every_account_open(self):
		with (
			patch.object(balance_mapping_sync, "defaults_for", return_value=Defaults("SKR04", "6.9")),
			patch.object(ebilanz_defaults, "REVISIONS", MappingProxyType({"6.9": 0})),
		):
			result = result_of(setup.run(SKR04_COMPANY, TODAY), "balance_sheet_mapping")
		self.assertEqual((result.outcome, result.document), (Outcome.CREATED, (MAPPING, SKR04_COMPANY)))
		mapping = frappe.get_doc(MAPPING, SKR04_COMPANY)
		self.assertEqual(
			(mapping.chart, mapping.taxonomy_version, mapping.defaults_version, mapping.rules),
			("SKR04", "6.9", "SKR04 Taxonomie 6.9 2026.0", []),
		)
		self.assertEqual(
			result.notes,
			(
				Note(step.MAPPING_WITH_DEFAULTS, ("SKR04 Taxonomie 6.9 2026.0", 0, 0, 0)),
				Note(step.WITHOUT_PLACE, (len(SKR04_ACCOUNTS),), open=True),
				Note(step.CHECK_WITH_ADVISER, open=True),
				Note(step.TAXONOMY_MISSING, ("6.9",), open=True),
			),
		)
		self.assertEqual(
			setup.text_of(result.notes[0]),
			"Made the Balance Sheet Mapping with the defaults SKR04 Taxonomie 6.9 2026.0: account rules 0, watched "
			"accounts 0, accounts outside the Bilanz and the GuV 0.",
		)

	def test_makes_the_mapping_with_the_defaults_of_the_datev_chart_and_leaves_no_account_open(self):
		result = result_of(setup.run(SKR04_COMPANY, TODAY), "balance_sheet_mapping")
		mapping = frappe.get_doc(MAPPING, SKR04_COMPANY)
		self.assertEqual(
			[(row.account_number, row.concept) for row in mapping.rules],
			[
				("1406", "bs.ass.currAss.receiv.other.vat"),
				("1800", "bs.ass.currAss.cashEquiv.bank"),
				("2900", "bs.eqLiab.equity.subscribed.corp"),
				("3806", "bs.eqLiab.liab.other.theroffTax"),
				(
					"4400",
					"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.generalRateVAT",
				),
			],
		)
		self.assertEqual(
			result.notes,
			(
				Note(step.MAPPING_WITH_DEFAULTS, ("SKR04 Taxonomie 6.9 2026.4", 5, 0, 0)),
				Note(step.CHECK_WITH_ADVISER, open=True),
				Note(step.TAXONOMY_MISSING, ("6.9",), open=True),
			),
		)

	def test_makes_the_mapping_with_the_rows_of_the_defaults_for_the_accounts_of_the_company(self):
		self.installed(positions.view())
		with patch.object(balance_mapping_sync, "defaults_for", return_value=DEFAULTS):
			result = result_of(setup.run(SKR04_COMPANY, TODAY), "balance_sheet_mapping")
		mapping = frappe.get_doc(MAPPING, SKR04_COMPANY)
		self.assertEqual(
			[(row.account_number, row.concept) for row in mapping.rules],
			[
				("1800", "bs.ass.currAss.cashEquiv.bank"),
				("2900", "bs.eqLiab.equity.subscribed.corp"),
				("4400", "is.netIncome.netSales"),
			],
		)
		self.assertEqual([(row.account_number, row.level) for row in mapping.watched], [("1406", "hint")])
		self.assertEqual(
			result.notes,
			(
				Note(step.MAPPING_WITH_DEFAULTS, ("SKR04 Taxonomie 6.9 2026.4", 3, 1, 0)),
				Note(step.WITHOUT_PLACE, (1,), open=True),
				Note(step.CHECK_WITH_ADVISER, open=True),
			),
		)

	def test_a_second_run_leaves_the_mapping_as_it_is(self):
		setup.run(SKR04_COMPANY, TODAY)
		modified = frappe.db.get_value(MAPPING, SKR04_COMPANY, "modified")
		result = result_of(setup.run(SKR04_COMPANY, TODAY), "balance_sheet_mapping")
		self.assertEqual(
			(result.outcome, result.notes, result.document),
			(
				Outcome.SKIPPED,
				(Note(step.MAPPING_EXISTS, (SKR04_COMPANY, "SKR04")),),
				(MAPPING, SKR04_COMPANY),
			),
		)
		self.assertEqual(frappe.db.get_value(MAPPING, SKR04_COMPANY, "modified"), modified)

	def test_gives_a_mapping_of_revision_0_the_defaults_of_today_as_it_gives_a_new_one(self):
		"""A mapping made while the defaults were the empty table of revision 0 took them over without rows: the next
		run loads the defaults of today into it with the points they leave open, and the run after leaves it."""
		with at_revision_0():
			setup.run(SKR04_COMPANY, TODAY)
		self.assertEqual(
			frappe.db.get_value(MAPPING, SKR04_COMPANY, "defaults_version"), "SKR04 Taxonomie 6.9 2026.0"
		)
		result = result_of(setup.run(SKR04_COMPANY, TODAY), "balance_sheet_mapping")
		self.assertEqual((result.outcome, result.document), (Outcome.CREATED, (MAPPING, SKR04_COMPANY)))
		mapping = frappe.get_doc(MAPPING, SKR04_COMPANY)
		self.assertEqual(
			(mapping.defaults_version, [row.account_number for row in mapping.rules]),
			("SKR04 Taxonomie 6.9 2026.4", ["1406", "1800", "2900", "3806", "4400"]),
		)
		self.assertEqual(
			result.notes,
			(
				Note(step.MAPPING_FILLED, (SKR04_COMPANY, "SKR04 Taxonomie 6.9 2026.4", 5, 0, 0)),
				Note(step.CHECK_WITH_ADVISER, open=True),
				Note(step.TAXONOMY_MISSING, ("6.9",), open=True),
			),
		)
		self.assertEqual(
			setup.text_of(result.notes[0]),
			f"The Balance Sheet Mapping of {SKR04_COMPANY} had no rows and now holds the defaults SKR04 Taxonomie "
			"6.9 2026.4: account rules 5, watched accounts 0, accounts outside the Bilanz and the GuV 0.",
		)
		again = result_of(setup.run(SKR04_COMPANY, TODAY), "balance_sheet_mapping")
		self.assertEqual(again.outcome, Outcome.SKIPPED)

	def test_leaves_a_mapping_with_rows_as_it_is_whatever_defaults_it_took_over(self):
		"""A row the company gave its mapping of revision 0 by hand keeps the setup out; the defaults of today reach it
		through Vorgaben aktualisieren."""
		with at_revision_0():
			setup.run(SKR04_COMPANY, TODAY)
		mapping = frappe.get_doc(MAPPING, SKR04_COMPANY)
		bank = frappe.db.get_value("Account", {"company": SKR04_COMPANY, "account_number": "1800"})
		mapping.append("watched", {"account": bank, "level": WatchLevel.HINT.value})
		mapping.save()
		modified = frappe.db.get_value(MAPPING, SKR04_COMPANY, "modified")
		result = result_of(setup.run(SKR04_COMPANY, TODAY), "balance_sheet_mapping")
		self.assertEqual(
			(result.outcome, result.notes),
			(Outcome.SKIPPED, (Note(step.MAPPING_EXISTS, (SKR04_COMPANY, "SKR04")),)),
		)
		self.assertEqual(
			frappe.db.get_value(MAPPING, SKR04_COMPANY, ["defaults_version", "modified"]),
			("SKR04 Taxonomie 6.9 2026.0", modified),
		)

	def test_a_chart_of_its_own_gets_an_empty_mapping_and_an_open_point(self):
		result = result_of(setup.run(OWN_COMPANY, TODAY), "balance_sheet_mapping")
		mapping = frappe.get_doc(MAPPING, OWN_COMPANY)
		self.assertEqual(
			(mapping.chart, mapping.rules, mapping.defaults_version), ("Eigener Kontenrahmen", [], None)
		)
		self.assertEqual(
			(result.outcome, result.notes),
			(
				Outcome.CREATED,
				(
					Note(step.OWN_CHART_EMPTY, (OWN_COMPANY,), open=True),
					Note(step.TAXONOMY_MISSING, ("6.9",), open=True),
				),
			),
		)

	def test_an_ambiguous_chart_gets_an_empty_mapping_and_asks_for_the_chart(self):
		self.installed(positions.view())
		result = result_of(setup.run(AMBIGUOUS_COMPANY, TODAY), "balance_sheet_mapping")
		self.assertEqual(frappe.db.get_value(MAPPING, AMBIGUOUS_COMPANY, "chart"), "Eigener Kontenrahmen")
		self.assertEqual(result.notes, (Note(step.AMBIGUOUS_CHART, (AMBIGUOUS_COMPANY,), open=True),))

	def test_the_report_names_the_step_with_its_document(self):
		report = setup.set_up(SKR04_COMPANY)
		(entry,) = (found for found in report["steps"] if found["key"] == "balance_sheet_mapping")
		self.assertEqual(
			(entry["label"], entry["outcome"], entry["doctype"], entry["name"]),
			("Balance Sheet Mapping", "created", MAPPING, SKR04_COMPANY),
		)
		self.assertEqual([note["open"] for note in entry["notes"]], [False, True, True])
