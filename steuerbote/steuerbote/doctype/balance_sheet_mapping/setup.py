"""The step of Steuerbote einrichten that makes the Balance Sheet Mapping of a company.

hooks.py names it in steuerbote_setup_steps after the step of the Income Tax Mapping, so that
steuerbote.steuerbote.setup runs it after its own: it makes the Balance Sheet Mapping with the defaults of SKR03 or
SKR04 for the latest version of the taxonomy (load_defaults, steuerbote/ebilanz/defaults.py), or one without rows for a
chart of its own or an ambiguous one, and leaves a mapping the company has as it is, unless that one waits for the
defaults of today (waits_for_defaults): it has no rows and took over others or none, as a mapping made while the
defaults were the empty table of revision 0, and gets them as a new one does. It leaves open what it cannot decide: the
accounts of the company the defaults give no place, a balance on which holds the E-Bilanz and the Jahresabschluss back,
the check by the Steuerberatung, and the HGB-Taxonomie, against which saving checks the positions once it is
installed.
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
MAPPING_FILLED = (
	"The Balance Sheet Mapping of {0} had no rows and now holds the defaults {1}: account rules {2}, watched accounts "
	"{3}, accounts outside the Bilanz and the GuV {4}."
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
	MAPPING_FILLED,
	MAPPING_WITH_DEFAULTS,
	WITHOUT_PLACE,
	CHECK_WITH_ADVISER,
	TAXONOMY_MISSING,
	OWN_CHART_EMPTY,
	AMBIGUOUS_CHART,
)


def run(context: SetupContext) -> StepResult:
	"""The Balance Sheet Mapping, if the company has none, or the defaults of today for one that waits for them."""
	company = context.company
	exists = frappe.db.exists(MAPPING, company)
	if exists:
		mapping = frappe.get_doc(MAPPING, company)
		if not mapping.waits_for_defaults():
			return StepResult(
				Outcome.SKIPPED, (Note(MAPPING_EXISTS, (company, mapping.chart)),), (MAPPING, company)
			)
	else:
		mapping = frappe.new_doc(MAPPING)
		mapping.company = company
	detection = context.chart
	# The step names the taxonomy it waits for in its notes, so saving leaves the alert of the form out.
	mapping.flags.taxonomy_noted = True
	if exists:
		without_place = mapping.load_defaults()
		mapping.save()
		notes = [Note(MAPPING_FILLED, (company, *_counted(mapping))), *_open_points(without_place)]
	elif detection.chart not in CHARTS:
		mapping.chart = OWN_CHART
		mapping.insert()
		template = AMBIGUOUS_CHART if detection.basis is charts.Basis.AMBIGUOUS else OWN_CHART_EMPTY
		notes = [Note(template, (company,), open=True)]
	else:
		mapping.chart = detection.chart
		without_place = mapping.load_defaults()
		mapping.insert()
		notes = [Note(MAPPING_WITH_DEFAULTS, _counted(mapping)), *_open_points(without_place)]
	if balance_sheet_mapping.position_taxonomy(mapping.taxonomy_version) is None:
		notes.append(Note(TAXONOMY_MISSING, (mapping.taxonomy_version,), open=True))
	return StepResult(Outcome.CREATED, tuple(notes), (MAPPING, mapping.name))


def _counted(mapping: balance_sheet_mapping.BalanceSheetMapping) -> tuple[object, ...]:
	"""The defaults the mapping holds, and its rules, watched accounts and accounts outside the Bilanz and the GuV
	counted."""
	return (mapping.defaults_version, len(mapping.rules), len(mapping.watched), len(mapping.excluded))


def _open_points(without_place: list[str]) -> list[Note]:
	"""What the defaults leave to the user: the accounts of the company they give no place, and the check by the
	Steuerberatung."""
	notes = [Note(WITHOUT_PLACE, (len(without_place),), open=True)] if without_place else []
	return [*notes, Note(CHECK_WITH_ADVISER, open=True)]
