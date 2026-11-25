"""Steuerbote einrichten on a site: what the setup makes for a company, what it leaves as it is, and that a second
run changes nothing."""

from datetime import date
from unittest.mock import patch

import frappe
from frappe import _
from frappe.tests import IntegrationTestCase
from frappe.utils import fmt_money, formatdate

from steuerbote.setup.steps import Note, Outcome, StepResult
from steuerbote.steuerbote import setup
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	make_user,
	post_journal_entry,
)

# Invented companies; the USt-IdNr. is the example of the OpenAPI document of the eVatR API.
SKR03_COMPANY = "Steuerbote Test Einrichtung SKR03 GmbH"
SKR04_COMPANY = "Steuerbote Test Einrichtung SKR04 GmbH"
OWN_COMPANY = "Steuerbote Test Einrichtung Eigen GmbH"
SET_UP_COMPANY = "Steuerbote Test Einrichtung Vorhanden GmbH"
TAXED_COMPANY = "Steuerbote Test Einrichtung Vorjahr GmbH"
SMALL_COMPANY = "Steuerbote Test Einrichtung Klein GmbH"
YOUNG_COMPANY = "Steuerbote Test Einrichtung Neu GmbH"
HOOK_COMPANY = "Steuerbote Test Einrichtung Schritte GmbH"
OWN_VAT_ID = "DE123456788"
BEGAN = "2026-05-12"
TODAY = date(2026, 11, 23)
NEXT_YEAR = date(2027, 1, 15)
ACCOUNTANT = "steuerbote-einrichtung-buchhaltung@example.com"
SETTINGS = "VAT Return Settings"
MAPPING = "VAT Return Mapping"
NOTE_TITLE = "Steuerbote Test Einrichtung"

# SKR03: the three accounts of its signature, a watched account and the receivables of a sale.
SKR03_ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1548": ("Vorsteuer im Folgejahr abziehbar", "Asset"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}
SKR04_ACCOUNTS = {
	"4400": ("Erlöse 19 % USt", "Income"),
	"3806": ("Umsatzsteuer 19 %", "Liability"),
	"1406": ("Abziehbare Vorsteuer 19 %", "Asset"),
}
OWN_ACCOUNTS = {"100": ("Umsatz", "Income"), "200": ("Steuer", "Liability")}


def company_with(name: str, abbr: str, accounts: dict[str, tuple[str, str]], **fields) -> dict[str, str]:
	"""The company with the accounts, by number; ``fields`` go to the company, such as its Tax ID."""
	make_company(name, abbr)
	if fields:
		frappe.db.set_value("Company", name, fields)
	return {
		number: frappe.db.get_value("Account", {"company": name, "account_number": number})
		or make_account(name, number, label, root_type)
		for number, (label, root_type) in accounts.items()
	}


def sale(company: str, accounts: dict[str, str], posting_date: str, base: int) -> None:
	"""A sale at 19 % with its tax, as the Verprobung expects it."""
	tax = base * 19 // 100
	post_journal_entry(
		company,
		posting_date,
		[(accounts["1400"], base + tax, 0), (accounts["8400"], 0, base), (accounts["1776"], 0, tax)],
	)


def remove_setup(company: str) -> None:
	frappe.delete_doc_if_exists(MAPPING, company, force=True)
	frappe.delete_doc_if_exists(SETTINGS, company, force=True)


def outcomes(done) -> dict[str, Outcome]:
	return {step.key: result.outcome for step, result in done}


def result_of(done, key: str) -> StepResult:
	(result,) = (result for step, result in done if step.key == key)
	return result


def texts_of(done, key: str) -> list[str]:
	return [setup.text_of(note) for note in result_of(done, key).notes]


def hook_step(context: setup.SetupContext) -> StepResult:
	"""A step another module adds through the hook: it sees the chart of the company and the steps before it."""
	before = ", ".join(sorted(context.results))
	return StepResult(Outcome.CREATED, (Note("{0}: {1}", (context.chart.chart, before)),))


def failing_step(context: setup.SetupContext) -> StepResult:
	"""A step that writes, then refuses: what it wrote goes with it."""
	frappe.get_doc({"doctype": "Note", "title": NOTE_TITLE, "public": 0}).insert()
	frappe.throw(_("The step needs the settings first."))


def broken_step(context: setup.SetupContext) -> StepResult:
	raise RuntimeError("a bug in a step")


class hooked:
	"""The hook steuerbote_setup_steps with the entries; every other hook as the site has it."""

	def __init__(self, entries: list[dict]):
		original = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			return entries if hook == setup.STEPS_HOOK else original(hook, *args, **kwargs)

		self.patch = patch.object(frappe, "get_hooks", side_effect=get_hooks)

	def __enter__(self):
		return self.patch.__enter__()

	def __exit__(self, *exc):
		return self.patch.__exit__(*exc)


class CompanySetupTest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company_with(SKR03_COMPANY, "STES3", SKR03_ACCOUNTS, tax_id=OWN_VAT_ID)
		company_with(SKR04_COMPANY, "STES4", SKR04_ACCOUNTS, chart_of_accounts="SKR04 mit Kontonummern")
		company_with(OWN_COMPANY, "STESE", OWN_ACCOUNTS)
		company_with(SET_UP_COMPANY, "STESV", SKR03_ACCOUNTS)
		cls.taxed = company_with(TAXED_COMPANY, "STESJ", SKR03_ACCOUNTS)
		cls.small = company_with(SMALL_COMPANY, "STESK", SKR03_ACCOUNTS)
		company_with(YOUNG_COMPANY, "STESN", SKR03_ACCOUNTS, date_of_establishment=BEGAN)
		company_with(HOOK_COMPANY, "STESS", SKR03_ACCOUNTS)

	def setUp(self):
		# These tests check the steps of the Voranmeldung; a step a module adds through the hook has tests of its own.
		without_hooked_steps = hooked([])
		without_hooked_steps.__enter__()
		self.addCleanup(without_hooked_steps.__exit__, None, None, None)
		for company in (
			SKR03_COMPANY,
			SKR04_COMPANY,
			OWN_COMPANY,
			SET_UP_COMPANY,
			TAXED_COMPANY,
			SMALL_COMPANY,
			YOUNG_COMPANY,
			HOOK_COMPANY,
		):
			remove_setup(company)

	def test_makes_the_settings_and_the_mapping_with_the_defaults_of_the_chart(self):
		done = setup.run(SKR03_COMPANY, TODAY)
		self.assertEqual(
			outcomes(done),
			{
				"vat_return_settings": Outcome.CREATED,
				"vat_return_mapping": Outcome.CREATED,
				"filing_period": Outcome.UNDECIDED,
			},
		)
		settings = frappe.get_doc(SETTINGS, SKR03_COMPANY)
		self.assertEqual(
			(settings.chart, settings.taxation_type, settings.ust_idnr, settings.filer_name),
			("SKR03", "Soll", OWN_VAT_ID, SKR03_COMPANY),
		)
		self.assertFalse(settings.state or settings.tax_number)
		self.assertEqual((settings.period_rules, settings.prepayments), ([], []))
		mapping = frappe.get_doc(MAPPING, SKR03_COMPANY)
		self.assertEqual(mapping.chart, "SKR03")
		self.assertEqual(
			[(row.account_number, row.kennzahl) for row in mapping.rules], [("8400", "81"), ("1576", "66")]
		)
		self.assertEqual([row.tax_accounts for row in mapping.checks], ["1776"])
		self.assertEqual([(row.account_number, row.level) for row in mapping.watched], [("1548", "blocking")])

	def test_without_a_company_it_asks_for_one(self):
		with self.assertRaisesRegex(frappe.ValidationError, "There is no company"):
			setup.set_up()

	def test_reports_what_it_made_and_what_is_left_to_the_user(self):
		done = setup.run(SKR03_COMPANY, TODAY)
		settings = result_of(done, "vat_return_settings")
		self.assertEqual(settings.document, (SETTINGS, SKR03_COMPANY))
		self.assertEqual(
			[(note.template, note.open) for note in settings.notes],
			[
				(setup.SETTINGS_MADE, False),
				(setup.VAT_ID_TAKEN, False),
				(setup.DATENLIEFERANT_TAKEN, False),
				(setup.DATENLIEFERANT_MISSING, True),
				(setup.STATE_AND_TAX_NUMBER, True),
			],
		)
		self.assertEqual(
			texts_of(done, "vat_return_settings")[3],
			"Enter the missing parts of the Datenlieferant in the VAT Return Settings, which the file for Mein ELSTER "
			"and ERiC need: Street and House Number, Postal Code, Town.",
		)
		self.assertEqual(
			texts_of(done, "vat_return_settings")[:3],
			[
				f"Made the VAT Return Settings of {SKR03_COMPANY} with the chart SKR03, Soll-Versteuerung, the "
				"Voranmeldungszeitraum by service date, a corrected return for bookings of a filed period and no "
				"Dauerfristverlängerung.",
				f"USt-IdNr. {OWN_VAT_ID} taken from the Tax ID of the company.",
				"Datenlieferant taken from the company and its address: Name.",
			],
		)
		self.assertEqual(
			texts_of(done, "vat_return_mapping"),
			[
				"Made the VAT Return Mapping with the defaults of SKR03: account rules 2, tax checks 1, watched "
				"accounts 1.",
				"The chart SKR03 follows from the accounts 1576, 1776, 8400 of the company.",
				f"{len(frappe.get_doc(MAPPING, SKR03_COMPANY).load_defaults())} accounts of the defaults do not "
				"exist in the company and were left out.",
				"Check Tax Templates finds every account of the tax templates of the company placed in the mapping.",
			],
		)
		filing_period = result_of(done, "filing_period")
		self.assertEqual(
			[(note.template, note.values, note.open) for note in filing_period.notes],
			[(setup.NO_CATALOGUE, (2025,), False), (setup.ENTER_FILING_PERIOD, (), True)],
		)

	def test_a_second_run_changes_nothing_and_says_so(self):
		first = setup.report(SKR03_COMPANY, setup.run(SKR03_COMPANY, TODAY))
		modified = {
			doctype: frappe.db.get_value(doctype, SKR03_COMPANY, "modified")
			for doctype in (SETTINGS, MAPPING)
		}
		second = setup.report(SKR03_COMPANY, setup.run(SKR03_COMPANY, TODAY))
		self.assertTrue(first["changed"])
		self.assertFalse(second["changed"])
		self.assertEqual(
			[(step["key"], step["outcome"]) for step in second["steps"]],
			[
				("vat_return_settings", "skipped"),
				("vat_return_mapping", "skipped"),
				("filing_period", "undecided"),
			],
		)
		self.assertEqual(
			{
				doctype: frappe.db.get_value(doctype, SKR03_COMPANY, "modified")
				for doctype in (SETTINGS, MAPPING)
			},
			modified,
		)
		self.assertEqual(
			[note["open"] for note in second["steps"][0]["notes"]],
			[False, True],
			"the Bundesland and the Steuernummer are still to be entered",
		)

	def test_the_status_before_the_setup_says_what_it_would_make_and_writes_nothing(self):
		before = setup.setup_status(SKR03_COMPANY)
		self.assertTrue(before["before"])
		self.assertEqual(
			[(step["key"], step["outcome"]) for step in before["steps"]],
			[
				("vat_return_settings", "created"),
				("vat_return_mapping", "created"),
				("filing_period", "undecided"),
			],
		)
		self.assertFalse(frappe.db.exists(SETTINGS, SKR03_COMPANY))
		self.assertFalse(frappe.db.exists(MAPPING, SKR03_COMPANY))
		setup.set_up(SKR03_COMPANY)
		after = setup.setup_status(SKR03_COMPANY)
		self.assertEqual(
			[(step["key"], step["outcome"]) for step in after["steps"]][:2],
			[("vat_return_settings", "skipped"), ("vat_return_mapping", "skipped")],
		)

	def test_the_status_needs_a_company(self):
		with self.assertRaisesRegex(frappe.ValidationError, "There is no company"):
			setup.setup_status()

	def test_leaves_the_settings_and_the_mapping_a_company_has(self):
		make_settings(SET_UP_COMPANY, [(2026, "quarterly", 1)])
		make_mapping(SET_UP_COMPANY)
		modified = {
			doctype: frappe.db.get_value(doctype, SET_UP_COMPANY, "modified")
			for doctype in (SETTINGS, MAPPING)
		}
		done = setup.run(SET_UP_COMPANY, TODAY)
		self.assertEqual(set(outcomes(done).values()), {Outcome.SKIPPED})
		self.assertEqual(
			[(note.template, note.values) for step, result in done for note in result.notes],
			[
				(setup.SETTINGS_EXIST, (SET_UP_COMPANY,)),
				(setup.MAPPING_EXISTS, (SET_UP_COMPANY, "SKR03")),
				(setup.PERIODS_EXIST, ()),
			],
		)
		self.assertEqual(
			{
				doctype: frappe.db.get_value(doctype, SET_UP_COMPANY, "modified")
				for doctype in (SETTINGS, MAPPING)
			},
			modified,
		)

	def test_gives_a_mapping_without_rows_the_defaults_as_it_gives_a_new_one(self):
		"""A mapping made by hand without rows took over no defaults: the setup loads those of today into it and says
		so, and a second run leaves it."""
		frappe.get_doc({"doctype": MAPPING, "company": SET_UP_COMPANY, "chart": "SKR03"}).insert()
		done = setup.run(SET_UP_COMPANY, TODAY)
		result = result_of(done, "vat_return_mapping")
		self.assertEqual((result.outcome, result.document), (Outcome.CREATED, (MAPPING, SET_UP_COMPANY)))
		mapping = frappe.get_doc(MAPPING, SET_UP_COMPANY)
		self.assertEqual(mapping.defaults_version, "SKR03 2026.4")
		self.assertEqual(
			[(row.account_number, row.kennzahl) for row in mapping.rules], [("8400", "81"), ("1576", "66")]
		)
		self.assertEqual([row.tax_accounts for row in mapping.checks], ["1776"])
		self.assertEqual([(row.account_number, row.level) for row in mapping.watched], [("1548", "blocking")])
		self.assertEqual(
			texts_of(done, "vat_return_mapping"),
			[
				f"The VAT Return Mapping of {SET_UP_COMPANY} had no rows and now holds the defaults SKR03 2026.4: "
				"account rules 2, tax checks 1, watched accounts 1.",
				f"{len(mapping.load_defaults())} accounts of the defaults do not exist in the company and were left "
				"out.",
				"Check Tax Templates finds every account of the tax templates of the company placed in the mapping.",
			],
		)
		self.assertEqual(outcomes(setup.run(SET_UP_COMPANY, TODAY))["vat_return_mapping"], Outcome.SKIPPED)

	def test_leaves_a_mapping_with_rows_as_it_is_whatever_defaults_it_took_over(self):
		"""Newer defaults reach a mapping with rows through Vorgaben aktualisieren only."""
		make_mapping(SET_UP_COMPANY).db_set("defaults_version", "SKR03 2025.4")
		modified = frappe.db.get_value(MAPPING, SET_UP_COMPANY, "modified")
		result = result_of(setup.run(SET_UP_COMPANY, TODAY), "vat_return_mapping")
		self.assertEqual(
			(result.outcome, result.notes),
			(Outcome.SKIPPED, (Note(setup.MAPPING_EXISTS, (SET_UP_COMPANY, "SKR03")),)),
		)
		self.assertEqual(
			frappe.db.get_value(MAPPING, SET_UP_COMPANY, ["defaults_version", "modified"]),
			("SKR03 2025.4", modified),
		)

	def test_takes_the_chart_from_the_template_of_the_company(self):
		done = setup.run(SKR04_COMPANY, TODAY)
		mapping = frappe.get_doc(MAPPING, SKR04_COMPANY)
		self.assertEqual(
			(mapping.chart, [row.account_number for row in mapping.rules]), ("SKR04", ["4400", "1406"])
		)
		self.assertEqual(frappe.db.get_value(SETTINGS, SKR04_COMPANY, "chart"), "SKR04")
		self.assertIn(
			"The chart SKR04 follows from the template SKR04 mit Kontonummern the chart of accounts of the company "
			"was made from.",
			texts_of(done, "vat_return_mapping"),
		)

	def test_a_company_copied_from_another_takes_its_template(self):
		frappe.db.set_value(
			"Company",
			OWN_COMPANY,
			{"create_chart_of_accounts_based_on": "Existing Company", "existing_company": SKR04_COMPANY},
		)
		try:
			self.assertEqual(setup.chart_template(OWN_COMPANY), "SKR04 mit Kontonummern")
		finally:
			frappe.db.set_value(
				"Company", OWN_COMPANY, {"create_chart_of_accounts_based_on": None, "existing_company": None}
			)

	def test_a_chart_of_its_own_gets_an_empty_mapping_and_an_open_point(self):
		done = setup.run(OWN_COMPANY, TODAY)
		mapping = frappe.get_doc(MAPPING, OWN_COMPANY)
		self.assertEqual(
			(mapping.chart, mapping.rules, mapping.checks, mapping.watched),
			("Eigener Kontenrahmen", [], [], []),
		)
		self.assertEqual(frappe.db.get_value(SETTINGS, OWN_COMPANY, "chart"), "Eigener Kontenrahmen")
		self.assertEqual(
			[(note.template, note.open) for note in result_of(done, "vat_return_mapping").notes],
			[(setup.OWN_CHART_EMPTY, True)],
		)
		self.assertEqual(outcomes(done)["vat_return_mapping"], Outcome.CREATED)

	def test_an_own_chart_computes_no_tax_of_the_previous_year(self):
		done = setup.run(OWN_COMPANY, NEXT_YEAR)
		self.assertEqual(result_of(done, "filing_period").notes[0], Note(setup.NO_DEFAULTS, (2026,)))

	def test_proposes_the_month_when_the_tax_of_the_previous_year_was_above_9000_euros(self):
		sale(TAXED_COMPANY, self.taxed, "2026-03-10", 60000)
		done = setup.run(TAXED_COMPANY, NEXT_YEAR)
		self.assertEqual(outcomes(done)["filing_period"], Outcome.CREATED)
		self.assertEqual(
			[
				(row.year, row.rhythm, row.valid_from_month)
				for row in frappe.get_doc(SETTINGS, TAXED_COMPANY).period_rules
			],
			[(2027, "monthly", 1)],
		)
		self.assertEqual(
			texts_of(done, "filing_period"),
			[
				f"Proposed: monthly from Januar 2027, because the tax of 2026 comes to "
				f"{fmt_money(11400, currency='EUR')} by the ledger (§ 18 Absatz 2 Sätze 1 and 2 UStG).",
				"The Finanzamt sets the Voranmeldungszeitraum: compare the proposal with what it set.",
			],
		)

	def test_proposes_the_quarter_and_names_the_exemption_up_to_2000_euros(self):
		sale(SMALL_COMPANY, self.small, "2026-06-10", 10000)
		done = setup.run(SMALL_COMPANY, NEXT_YEAR)
		self.assertEqual(
			[(row.year, row.rhythm) for row in frappe.get_doc(SETTINGS, SMALL_COMPANY).period_rules],
			[(2027, "quarterly")],
		)
		self.assertEqual(
			[note.template for note in result_of(done, "filing_period").notes],
			[setup.PROPOSED_FROM_TAX, setup.EXEMPTION_POSSIBLE, setup.CHECK_WITH_FINANZAMT],
		)

	def test_without_postings_of_the_previous_year_there_is_no_proposal(self):
		done = setup.run(SKR03_COMPANY, NEXT_YEAR)
		self.assertEqual(outcomes(done)["filing_period"], Outcome.UNDECIDED)
		self.assertEqual(frappe.get_doc(SETTINGS, SKR03_COMPANY).period_rules, [])
		self.assertEqual(result_of(done, "filing_period").notes[0], Note(setup.NO_POSTINGS, (2026,)))

	def test_a_company_that_began_the_year_before_files_monthly_from_2027(self):
		done = setup.run(YOUNG_COMPANY, NEXT_YEAR)
		self.assertEqual(
			[
				(row.year, row.rhythm, row.valid_from_month)
				for row in frappe.get_doc(SETTINGS, YOUNG_COMPANY).period_rules
			],
			[(2027, "monthly", 1)],
		)
		self.assertEqual(
			texts_of(done, "filing_period")[0],
			f"Proposed: monthly from Januar 2027, because the company began on {formatdate(BEGAN)}, and in the "
			"year it begins and the next the month is the Voranmeldungszeitraum (§ 18 Absatz 2 Satz 4 UStG).",
		)

	def test_a_company_that_began_in_2026_gets_no_proposal_for_2026(self):
		done = setup.run(YOUNG_COMPANY, TODAY)
		self.assertEqual(outcomes(done)["filing_period"], Outcome.UNDECIDED)
		self.assertEqual(
			result_of(done, "filing_period").notes,
			(
				Note(setup.STARTED_THIS_YEAR, (date(2026, 5, 12), 2026)),
				Note(setup.ENTER_FILING_PERIOD, open=True),
			),
		)

	def test_steps_of_the_hook_run_after_the_steps_they_need(self):
		entries = [
			{
				"key": "income_tax_mapping",
				"label": "VAT Return Mapping",
				"order": 5,
				"needs": ["vat_return_mapping"],
				"run": "steuerbote.tests.test_company_setup.hook_step",
			}
		]
		with hooked(entries):
			done = setup.run(HOOK_COMPANY, TODAY)
		self.assertEqual(
			[step.key for step, _result in done],
			["vat_return_settings", "vat_return_mapping", "income_tax_mapping", "filing_period"],
		)
		self.assertEqual(
			texts_of(done, "income_tax_mapping"), ["SKR03: vat_return_mapping, vat_return_settings"]
		)

	def test_a_failing_step_is_rolled_back_and_a_step_that_needs_it_does_not_run(self):
		entries = [
			{
				"key": "failing",
				"label": "Filing Period",
				"order": 1,
				"run": "steuerbote.tests.test_company_setup.failing_step",
			},
			{
				"key": "after_failing",
				"label": "VAT Return Mapping",
				"order": 2,
				"needs": ["failing"],
				"run": "steuerbote.tests.test_company_setup.hook_step",
			},
			{
				"key": "broken",
				"label": "VAT Return Settings",
				"order": 3,
				"run": "steuerbote.tests.test_company_setup.broken_step",
			},
		]
		shown = list(frappe.local.message_log)
		with hooked(entries):
			done = setup.run(HOOK_COMPANY, TODAY)
		self.assertEqual(
			frappe.local.message_log, shown, "the message of the failing step stays in its report"
		)
		self.assertEqual(
			outcomes(done),
			{
				"failing": Outcome.FAILED,
				"after_failing": Outcome.BLOCKED,
				"broken": Outcome.FAILED,
				"vat_return_settings": Outcome.CREATED,
				"vat_return_mapping": Outcome.CREATED,
				"filing_period": Outcome.UNDECIDED,
			},
		)
		self.assertEqual(texts_of(done, "failing"), ["The step stopped: The step needs the settings first."])
		self.assertEqual(
			texts_of(done, "after_failing"),
			["Not run: it needs Filing Period, which did not create or find its document."],
		)
		self.assertEqual(texts_of(done, "broken"), [setup.STEP_BROKE])
		self.assertFalse(frappe.db.exists("Note", {"title": NOTE_TITLE}))

	def test_a_broken_entry_of_the_hook_is_refused_with_its_reason(self):
		with (
			hooked([{"key": "Broken", "label": "Broken", "order": 1, "run": "steuerbote.tests.run"}]),
			self.assertRaisesRegex(frappe.ValidationError, "Broken is not the key of a setup step"),
		):
			setup.setup_steps()

	def test_only_system_and_accounts_managers_set_up_a_company(self):
		make_user(ACCOUNTANT, "Accounts User")
		frappe.set_user(ACCOUNTANT)
		try:
			with self.assertRaises(frappe.PermissionError):
				setup.set_up(SKR03_COMPANY)
		finally:
			frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists(SETTINGS, SKR03_COMPANY))

	def test_set_up_refuses_a_company_that_does_not_exist(self):
		with self.assertRaisesRegex(frappe.ValidationError, "There is no company"):
			setup.set_up("Steuerbote Test Einrichtung Unbekannt GmbH")

	def test_the_report_names_each_step_with_its_document(self):
		result = setup.set_up(SKR03_COMPANY)
		self.assertTrue(result["changed"])
		self.assertEqual(
			[
				(step["label"], step["doctype"], step["document_label"], step["name"])
				for step in result["steps"]
			],
			[
				("VAT Return Settings", SETTINGS, SETTINGS, SKR03_COMPANY),
				("VAT Return Mapping", MAPPING, MAPPING, SKR03_COMPANY),
				("Filing Period", SETTINGS, SETTINGS, SKR03_COMPANY),
			],
		)
