"""The step of Steuerbote einrichten that makes the Balance Sheet Mapping of a company.

hooks.py names it in steuerbote_setup_steps after the step of the Income Tax Mapping, so that
steuerbote.steuerbote.setup runs it after its own: it makes the Balance Sheet Mapping with the defaults of SKR03 or
SKR04 for the latest version of the taxonomy (load_defaults, steuerbote/ebilanz/defaults.py), or one without rows for a
chart of its own or an ambiguous one, and leaves a mapping the company has as it is. It leaves open what it cannot
decide: the accounts of the company the defaults give no place, a balance on which holds the E-Bilanz and the
Jahresabschluss back, the check by the Steuerberatung, and the HGB-Taxonomie, against which saving checks the
positions once it is installed.
"""

import frappe

from steuerbote.ebilanz.defaults import CHARTS
from steuerbote.setup import chart as charts
from steuerbote.setup.steps import Note, Outcome, StepResult
from steuerbote.steuerbote.doctype.balance_sheet_mapping import balance_sheet_mapping
from steuerbote.steuerbote.setup import SetupContext

MAPPING = "Balance Sheet Mapping"
OWN_CHART = "Eigener Kontenrahmen"

MAPPING_EXISTS = (
	"The Balance Sheet Mapping of {0} exists already with the chart {1}; the setup leaves it as it is."
)
MAPPING_WITH_DEFAULTS = (
	"Made the Balance Sheet Mapping with the defaults {0}: account rules {1}, watched accounts {2}, accounts outside "
	"the Bilanz and the GuV {3}."
)
WITHOUT_PLACE = (
	"{0} accounts of the company have no place in the Balance Sheet Mapping yet: give each a position or the reason why "
	"it lies outside the Bilanz and the GuV, since a balance on one of them holds the E-Bilanz and the Jahresabschluss "
	"back. Konten prüfen in the mapping lists them."
)
CHECK_WITH_ADVISER = "Let the Steuerberatung check the Balance Sheet Mapping before the first E-Bilanz and the first Jahresabschluss."
TAXONOMY_MISSING = (
	"Install the HGB-Taxonomie {0} with Install Taxonomy in the ERiC Settings: saving the Balance Sheet Mapping checks "
	"its positions against it."
)
OWN_CHART_EMPTY = (
	"Neither the template of its chart of accounts nor its accounts show SKR03 or SKR04, so the Balance Sheet Mapping "
	"of {0} has no rows yet: give each account a position or the reason why it lies outside the Bilanz and the GuV."
)
AMBIGUOUS_CHART = (
	"The template or the accounts of {0} point to SKR03 and SKR04 at once, so the Balance Sheet Mapping has no rows "
	"yet: choose the chart in the mapping and load its defaults."
)
MESSAGES = (
	MAPPING_EXISTS,
	MAPPING_WITH_DEFAULTS,
	WITHOUT_PLACE,
	CHECK_WITH_ADVISER,
	TAXONOMY_MISSING,
	OWN_CHART_EMPTY,
	AMBIGUOUS_CHART,
)


def run(context: SetupContext) -> StepResult:
	"""The Balance Sheet Mapping, if the company has none."""
	company = context.company
	if frappe.db.exists(MAPPING, company):
		chart = frappe.db.get_value(MAPPING, company, "chart")
		return StepResult(Outcome.SKIPPED, (Note(MAPPING_EXISTS, (company, chart)),), (MAPPING, company))
	detection = context.chart
	mapping = frappe.new_doc(MAPPING)
	mapping.company = company
	# The step names the taxonomy it waits for in its notes, so saving leaves the alert of the form out.
	mapping.flags.taxonomy_noted = True
	if detection.chart not in CHARTS:
		mapping.chart = OWN_CHART
		mapping.insert()
		template = AMBIGUOUS_CHART if detection.basis is charts.Basis.AMBIGUOUS else OWN_CHART_EMPTY
		notes = [Note(template, (company,), open=True)]
	else:
		mapping.chart = detection.chart
		without_place = mapping.load_defaults()
		mapping.insert()
		notes = [
			Note(
				MAPPING_WITH_DEFAULTS,
				(mapping.defaults_version, len(mapping.rules), len(mapping.watched), len(mapping.excluded)),
			)
		]
		if without_place:
			notes.append(Note(WITHOUT_PLACE, (len(without_place),), open=True))
		notes.append(Note(CHECK_WITH_ADVISER, open=True))
	if balance_sheet_mapping.position_taxonomy(mapping.taxonomy_version) is None:
		notes.append(Note(TAXONOMY_MISSING, (mapping.taxonomy_version,), open=True))
	return StepResult(Outcome.CREATED, tuple(notes), (MAPPING, mapping.name))
