"""The step of Steuerbote einrichten that names what the ERiC Settings still need before an Erklärung goes over ERiC.

hooks.py names it in steuerbote_setup_steps as the last step. The Vorsatz of every Erklärung, USt, KSt and GewSt,
carries the copyright notice of the maker of the tax software (rules 10435 and 6; steuerbote/elster/vorsatz.py), which
Steuerbote takes from the ERiC Settings and without which no Erklärung runs with ERiC (eric_settings.vorsatz_copyright).
The step names it before the first run, which would otherwise be refused; it changes nothing.
"""

import frappe

from steuerbote.setup.steps import Note, Outcome, StepResult
from steuerbote.steuerbote.setup import SetupContext

SETTINGS = "ERiC Settings"

COPYRIGHT_SET = (
	"The ERiC Settings name the Copyright Notice {0}, which the Vorsatz of every Erklärung carries."
)
COPYRIGHT_MISSING = (
	"Enter the Copyright Notice in the ERiC Settings, such as (c) 2026 Beispiel GmbH, München: the Vorsatz of every "
	"Umsatzsteuer-, Körperschaftsteuer- and Gewerbesteuererklärung carries it, and without it none goes over ERiC."
)
MESSAGES = (COPYRIGHT_SET, COPYRIGHT_MISSING)


def run(context: SetupContext) -> StepResult:
	"""Whether the ERiC Settings name the copyright notice the Erklärungen need."""
	copyright_notice = frappe.get_single(SETTINGS).copyright
	if copyright_notice:
		return StepResult(Outcome.SKIPPED, (Note(COPYRIGHT_SET, (copyright_notice,)),), (SETTINGS, SETTINGS))
	return StepResult(Outcome.UNDECIDED, (Note(COPYRIGHT_MISSING, open=True),), (SETTINGS, SETTINGS))
