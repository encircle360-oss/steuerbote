"""Steuerbote einrichten makes the Income Tax Mapping of a company through the hook steuerbote_setup_steps: with the
defaults of its chart and the points left to the user, without rules for a chart of its own or an ambiguous one, and
not again once the company has one."""

from datetime import date

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.kst.defaults import default_accounts
from steuerbote.setup.steps import Note, Outcome
from steuerbote.steuerbote import setup
from steuerbote.steuerbote.doctype.income_tax_mapping import setup as step
from steuerbote.tests.helpers import make_account, make_company

# The tests build their own companies and accounts and need none of ERPNext's test records.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Account"]

MAPPING = "Income Tax Mapping"
SKR03_COMPANY = "Steuerbote Test Einrichtung Ertragsteuern GmbH"
OWN_COMPANY = "Steuerbote Test Einrichtung Ertragsteuern Eigen GmbH"
AMBIGUOUS_COMPANY = "Steuerbote Test Einrichtung Ertragsteuern Zwei GmbH"
TODAY = date(2026, 11, 23)
# SKR03: the three accounts of its signature, the Körperschaftsteuer and the Gewerbesteuer, a trading account and a
# watched account.
SKR03_ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"2200": ("Körperschaftsteuer", "Expense"),
	"4320": ("Gewerbesteuer", "Expense"),
	"2654": ("Erträge aus anderen Wertpapieren und Ausleihungen des Umlaufvermögens", "Income"),
	"2250": ("Aufwendungen aus der Zuführung und Auflösung von latenten Steuern", "Expense"),
}
OWN_ACCOUNTS = {"100": ("Umsatz", "Income"), "200": ("Steuer", "Liability")}
# The signatures of SKR03 and of SKR04 at once.
AMBIGUOUS_ACCOUNTS = {
	**{number: SKR03_ACCOUNTS[number] for number in ("8400", "1776", "1576")},
	"4400": ("Erlöse 19 % USt", "Income"),
	"3806": ("Umsatzsteuer 19 %", "Liability"),
	"1406": ("Abziehbare Vorsteuer 19 %", "Asset"),
}
COMPANIES = ((SKR03_COMPANY, "STEE3", SKR03_ACCOUNTS), (OWN_COMPANY, "STEEE", OWN_ACCOUNTS))


def company_with(name: str, abbr: str, accounts: dict[str, tuple[str, str]]) -> None:
	make_company(name, abbr)
	for number, (label, root_type) in accounts.items():
		if not frappe.db.exists("Account", {"company": name, "account_number": number}):
			make_account(name, number, label, root_type)


def result_of(done, key: str):
	(result,) = (result for found, result in done if found.key == key)
	return result


class IntegrationTestIncomeTaxSetup(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for name, abbr, accounts in (*COMPANIES, (AMBIGUOUS_COMPANY, "STEEZ", AMBIGUOUS_ACCOUNTS)):
			company_with(name, abbr, accounts)

	def setUp(self):
		for company in (SKR03_COMPANY, OWN_COMPANY, AMBIGUOUS_COMPANY):
			for doctype in (MAPPING, "VAT Return Mapping", "VAT Return Settings"):
				frappe.delete_doc_if_exists(doctype, company, force=True)

	def test_the_setup_runs_the_step_of_the_hook_after_its_own(self):
		self.assertEqual(
			[found.key for found in setup.setup_steps()],
			["vat_return_settings", "vat_return_mapping", "filing_period", "income_tax_mapping"],
		)

	def test_makes_the_mapping_with_the_defaults_and_leaves_the_classes_and_the_check_open(self):
		done = setup.run(SKR03_COMPANY, TODAY)
		result = result_of(done, "income_tax_mapping")
		self.assertEqual((result.outcome, result.document), (Outcome.CREATED, (MAPPING, SKR03_COMPANY)))
		mapping = frappe.get_doc(MAPPING, SKR03_COMPANY)
		self.assertEqual((mapping.chart, mapping.defaults_version), ("SKR03", "SKR03 2026.1"))
		self.assertEqual(
			[(row.account_number, row.category) for row in mapping.rules],
			[("2200", "kst"), ("4320", "gewst"), ("2654", "trading_unclassified")],
		)
		self.assertEqual([(row.account_number, row.level) for row in mapping.watched], [("2250", "blocking")])
		self.assertEqual(
			result.notes,
			(
				Note(step.MAPPING_WITH_DEFAULTS, ("SKR03", 3, 1)),
				Note(step.DEFAULTS_MISSING, (len(default_accounts("SKR03")) - 4,)),
				Note(step.TRADING_WITHOUT_CLASS, ("2654",), open=True),
				Note(step.CHECK_WITH_ADVISER, open=True),
			),
		)
		self.assertEqual(
			setup.text_of(result.notes[0]),
			"Made the Income Tax Mapping with the defaults of SKR03: account rules 3, watched accounts 1.",
		)

	def test_a_second_run_leaves_the_mapping_as_it_is(self):
		setup.run(SKR03_COMPANY, TODAY)
		modified = frappe.db.get_value(MAPPING, SKR03_COMPANY, "modified")
		result = result_of(setup.run(SKR03_COMPANY, TODAY), "income_tax_mapping")
		self.assertEqual(
			(result.outcome, result.notes, result.document),
			(
				Outcome.SKIPPED,
				(Note(step.MAPPING_EXISTS, (SKR03_COMPANY, "SKR03")),),
				(MAPPING, SKR03_COMPANY),
			),
		)
		self.assertEqual(frappe.db.get_value(MAPPING, SKR03_COMPANY, "modified"), modified)

	def test_a_chart_of_its_own_gets_an_empty_mapping_and_an_open_point(self):
		result = result_of(setup.run(OWN_COMPANY, TODAY), "income_tax_mapping")
		mapping = frappe.get_doc(MAPPING, OWN_COMPANY)
		self.assertEqual((mapping.chart, mapping.rules, mapping.watched), ("Eigener Kontenrahmen", [], []))
		self.assertEqual(
			(result.outcome, result.notes),
			(Outcome.CREATED, (Note(step.OWN_CHART_EMPTY, (OWN_COMPANY,), open=True),)),
		)

	def test_an_ambiguous_chart_gets_an_empty_mapping_and_asks_for_the_chart(self):
		result = result_of(setup.run(AMBIGUOUS_COMPANY, TODAY), "income_tax_mapping")
		self.assertEqual(frappe.db.get_value(MAPPING, AMBIGUOUS_COMPANY, "chart"), "Eigener Kontenrahmen")
		self.assertEqual(result.notes, (Note(step.AMBIGUOUS_CHART, (AMBIGUOUS_COMPANY,), open=True),))

	def test_the_report_names_the_step_with_its_document(self):
		report = setup.set_up(SKR03_COMPANY)
		(entry,) = (found for found in report["steps"] if found["key"] == "income_tax_mapping")
		self.assertEqual(
			(entry["label"], entry["outcome"], entry["doctype"], entry["name"]),
			("Income Tax Mapping", "created", MAPPING, SKR03_COMPANY),
		)
		self.assertEqual([note["open"] for note in entry["notes"]], [False, False, True, True])
