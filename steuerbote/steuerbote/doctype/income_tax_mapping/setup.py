"""The step of Steuerbote einrichten that makes the Income Tax Mapping of a company.

hooks.py names it in steuerbote_setup_steps, so that steuerbote.steuerbote.setup runs it after its own steps: it makes
the Income Tax Mapping with the defaults of SKR03 or SKR04 for the accounts the company has (load_defaults), or one
without rules for a chart of its own or an ambiguous one, and leaves a mapping the company has as it is. The trading
accounts of the defaults get no class, and the defaults wait for the Steuerberatung, so the step leaves both open.
"""

import frappe

from steuerbote.kst.categories import Category
from steuerbote.kst.defaults import DEFAULTS
from steuerbote.setup import chart as charts
from steuerbote.setup.steps import Note, Outcome, StepResult
from steuerbote.steuerbote.setup import SetupContext

MAPPING = "Income Tax Mapping"
OWN_CHART = "Eigener Kontenrahmen"

MAPPING_EXISTS = (
	"The Income Tax Mapping of {0} exists already with the chart {1}; the setup leaves it as it is."
)
MAPPING_WITH_DEFAULTS = (
	"Made the Income Tax Mapping with the defaults of {0}: account rules {1}, watched accounts {2}."
)
DEFAULTS_MISSING = (
	"{0} accounts of the defaults do not exist in the company and were left out; Vorgaben laden in the mapping names "
	"them."
)
TRADING_WITHOUT_CLASS = (
	"Set the trading class of the accounts {0} with the Steuerberatung: until then a balance on one of them holds the "
	"declaration back."
)
CHECK_WITH_ADVISER = (
	"Let the Steuerberatung check the Income Tax Mapping before the first Körperschaftsteuererklärung and "
	"Gewerbesteuererklärung."
)
OWN_CHART_EMPTY = (
	"Neither the template of its chart of accounts nor its accounts show SKR03 or SKR04, so the Income Tax Mapping of "
	"{0} has no rules yet: give each account of the Körperschaftsteuer and the Gewerbesteuer a rule or watch it."
)
AMBIGUOUS_CHART = (
	"The template or the accounts of {0} point to SKR03 and SKR04 at once, so the Income Tax Mapping has no rules yet: "
	"choose the chart in the mapping and load its defaults."
)
MESSAGES = (
	MAPPING_EXISTS,
	MAPPING_WITH_DEFAULTS,
	DEFAULTS_MISSING,
	TRADING_WITHOUT_CLASS,
	CHECK_WITH_ADVISER,
	OWN_CHART_EMPTY,
	AMBIGUOUS_CHART,
)


def run(context: SetupContext) -> StepResult:
	"""The Income Tax Mapping, if the company has none."""
	company = context.company
	if frappe.db.exists(MAPPING, company):
		chart = frappe.db.get_value(MAPPING, company, "chart")
		return StepResult(Outcome.SKIPPED, (Note(MAPPING_EXISTS, (company, chart)),), (MAPPING, company))
	detection = context.chart
	mapping = frappe.new_doc(MAPPING)
	mapping.company = company
	if detection.chart not in DEFAULTS:
		mapping.chart = OWN_CHART
		mapping.insert()
		template = AMBIGUOUS_CHART if detection.basis is charts.Basis.AMBIGUOUS else OWN_CHART_EMPTY
		return StepResult(Outcome.CREATED, (Note(template, (company,), open=True),), (MAPPING, mapping.name))
	mapping.chart = detection.chart
	missing = mapping.load_defaults()
	mapping.insert()
	notes = [Note(MAPPING_WITH_DEFAULTS, (mapping.chart, len(mapping.rules), len(mapping.watched)))]
	if missing:
		notes.append(Note(DEFAULTS_MISSING, (len(missing),)))
	if unclassified := [
		row.account_number
		for row in mapping.rules
		if row.category == Category.TRADING_UNCLASSIFIED and not row.trading_class
	]:
		notes.append(Note(TRADING_WITHOUT_CLASS, (", ".join(unclassified),), open=True))
	notes.append(Note(CHECK_WITH_ADVISER, open=True))
	return StepResult(Outcome.CREATED, tuple(notes), (MAPPING, mapping.name))
