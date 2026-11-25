"""Three steps of Steuerbote einrichten for the USt-IdNrn. of partners (hook steuerbote_setup_steps): the label of
ERPNext's Tax ID, the VAT ID check of erpnext_germany beside Steuerbote's, and the automatic check of the company.
None changes anything on its own: each says what it finds and offers its change as an action of the page, which only
a System Manager runs.

The automatic check, a confirmation when a partner changes and the daily renewal, is off until the company switches
it on here or in its VAT Return Settings: it sends the data of partners to the BZSt and VIES, which nothing may start
merely because the app was installed or updated.

ERPNext keeps one tax identifier per party and company, tax_id, and every app that reads it, Steuerbote included, takes
it as the USt-IdNr.; ERPNext's German translation calls it „Steuernummer“, so users enter the Steuernummer there. The
action labels the field „USt-IdNr.“ on Company, Customer and Supplier through Property Setters, which a later update of
ERPNext keeps. The Steuernummer of a partner has a field of its own (steuernummer), and so has a number from outside
the EU (foreign_tax_id).

erpnext_germany checks the USt-IdNrn. of all customers and suppliers at VIES in a job of its own, with the default
company as requester, and keeps the results in its DocType VAT ID Check. Steuerbote never reads those as proof. Where
erpnext_germany is installed, the action stops that job by the flag Stopped of its Scheduled Job Type, which bench
migrate keeps; its records stay as they are, and the app stays installed for its other functions.
"""

import frappe
from frappe import _
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from steuerbote import vatid
from steuerbote.setup.steps import Action, Note, Outcome, StepResult

TAX_ID = "tax_id"
LABELLED_DOCTYPES = ("Company", "Customer", "Supplier")
LABEL = "VAT ID"
DESCRIPTION = (
	"The USt-IdNr. with its country code, such as ATU12345678. The Steuernummer has a field of its own."
)
GERMANY_APP = "erpnext_germany"
GERMANY_JOB = "erpnext_germany.tasks.all"
JOB_TYPE = "Scheduled Job Type"
MANAGER = "System Manager"

LABELLED = "ERPNext's Tax ID reads „USt-IdNr.“ on Company, Customer and Supplier."
LABEL_MISLEADS = "ERPNext calls its Tax ID „Steuernummer“ in German, but Steuerbote and the other apps read it as the USt-IdNr.: an entered Steuernummer would be taken for one. Relabel it on Company, Customer and Supplier; the Steuernummer of a partner has a field of its own."
LABEL_OWN = "{0} carries a label of its own for the Tax ID, which Steuerbote leaves as it is."
RELABEL = "Relabel as USt-IdNr."
GERMANY_ABSENT = "erpnext_germany is not installed: Steuerbote alone confirms USt-IdNrn."
GERMANY_NO_JOB = "erpnext_germany is installed without its VAT ID job."
GERMANY_STOPPED = "The VAT ID job of erpnext_germany is stopped; its VAT ID Check records stay as they are, and Steuerbote does not read them as proof."
GERMANY_OVERLAP = "erpnext_germany runs a job at every tick of the scheduler that checks enabled customers and suppliers with a USt-IdNr. at VIES, each again three months after its last completed check, with the VAT ID of the default company as requester, and keeps the results in VAT ID Check, which Steuerbote does not read as proof. Steuerbote confirms the same numbers at the BZSt. Stop the job of erpnext_germany so that each number is asked about once; the app stays installed for its other functions."
STOP_GERMANY = "Stop the VAT ID Job of erpnext_germany"
SETTINGS = "VAT Return Settings"
AUTOMATIC_FIELDS = ("vat_id_check_on_change", "vat_id_renewal")
AUTOMATIC_ON = "The automatic check of USt-IdNrn. is on for {0}: a changed partner and every partner whose confirmation is due are confirmed in the background. It asks about the enabled customers with a USt-IdNr. that {0} deals with, by an account of its own on the partner or a submitted invoice, quotation or order, and with „Confirm Suppliers“ about such suppliers; a partner that deals with no company is asked about only by the button, for the company of the user."
AUTOMATIC_OFF = "The automatic check of USt-IdNrn. is off for {0}: Steuerbote confirms a partner only when someone presses „Confirm VAT ID“ on the partner or on an invoice, so partners stay „Not Checked“ until then. Switched on, it confirms a partner in the background when it is created or changed and renews every confirmation that is due each morning: the own USt-IdNr. of the company, the USt-IdNr. of the partner and, where known, its name and address go to the BZSt, and to VIES of the European Commission when the BZSt cannot answer. It asks about the enabled customers with a USt-IdNr. that {0} deals with, by an account of its own on the partner or a submitted invoice, quotation or order, and with „Confirm Suppliers“ about such suppliers; a partner that deals with no company is asked about only by the button, for the company of the user."
AUTOMATIC_PARTLY = "Only one of „Confirm When a Partner Changes“ and „Renew Confirmations Daily“ is on for {0}; the action switches on both."
AUTOMATIC_NEEDS_VAT_ID = "Enter the own USt-IdNr. of {0} in the VAT Return Settings first: without it Steuerbote confirms nothing for the company."
SWITCH_ON = "Switch On the Automatic Check"
MESSAGES = (
	LABELLED,
	LABEL_MISLEADS,
	LABEL_OWN,
	RELABEL,
	GERMANY_ABSENT,
	GERMANY_NO_JOB,
	GERMANY_STOPPED,
	GERMANY_OVERLAP,
	STOP_GERMANY,
	AUTOMATIC_ON,
	AUTOMATIC_OFF,
	AUTOMATIC_PARTLY,
	AUTOMATIC_NEEDS_VAT_ID,
	SWITCH_ON,
)


def check_tax_id_label(context) -> StepResult:
	"""The step vat_id_label: done when the Tax ID reads „USt-IdNr.“ everywhere; otherwise it offers the relabelling,
	and leaves alone a label someone set by hand."""
	labels = {doctype: _label_of(doctype) for doctype in LABELLED_DOCTYPES}
	own = [Note(LABEL_OWN, (doctype,)) for doctype, label in labels.items() if label not in (None, LABEL)]
	if None not in labels.values():
		return StepResult(Outcome.SKIPPED, tuple(own) or (Note(LABELLED),))
	notes = (Note(LABEL_MISLEADS, open=True), *own)
	return StepResult(Outcome.UNDECIDED, notes, action=Action(RELABEL, f"{__name__}.relabel_tax_id"))


def _label_of(doctype: str) -> str | None:
	return frappe.db.get_value(
		"Property Setter", {"doc_type": doctype, "field_name": TAX_ID, "property": "label"}, "value"
	)


@frappe.whitelist(methods=["POST"])
def relabel_tax_id(company: str | None = None) -> None:
	"""The action of vat_id_label: label the Tax ID „USt-IdNr.“ where it carries ERPNext's label; ``company`` is the
	company of the page, which the label does not depend on."""
	frappe.only_for(MANAGER, message=True)
	for doctype in LABELLED_DOCTYPES:
		if _label_of(doctype) is not None:
			continue
		for name, value in (("label", LABEL), ("description", DESCRIPTION)):
			make_property_setter(
				doctype,
				TAX_ID,
				name,
				value,
				"Data",
				validate_fields_for_doctype=False,
				is_system_generated=False,
			)
		frappe.clear_cache(doctype=doctype)


def check_erpnext_germany(context) -> StepResult:
	"""The step erpnext_germany_vat_id_check: where erpnext_germany is installed and its job runs, it explains the overlap
	and offers to stop the job."""
	if GERMANY_APP not in frappe.get_installed_apps():
		return StepResult(Outcome.SKIPPED, (Note(GERMANY_ABSENT),))
	job = _germany_job()
	if job is None:
		return StepResult(Outcome.SKIPPED, (Note(GERMANY_NO_JOB),))
	if job.stopped:
		return StepResult(Outcome.SKIPPED, (Note(GERMANY_STOPPED),), (JOB_TYPE, job.name))
	return StepResult(
		Outcome.UNDECIDED,
		(Note(GERMANY_OVERLAP, open=True),),
		(JOB_TYPE, job.name),
		Action(STOP_GERMANY, f"{__name__}.stop_erpnext_germany_check"),
	)


def _germany_job() -> frappe._dict | None:
	return frappe.db.get_value(JOB_TYPE, {"method": GERMANY_JOB}, ["name", "stopped"], as_dict=True)


@frappe.whitelist(methods=["POST"])
def stop_erpnext_germany_check(company: str | None = None) -> None:
	"""The action of erpnext_germany_vat_id_check: set its Scheduled Job Type to Stopped."""
	frappe.only_for(MANAGER, message=True)
	job = _germany_job()
	if job is None:
		frappe.throw(_("erpnext_germany is installed without its VAT ID job."))
	doc = frappe.get_doc(JOB_TYPE, job.name)
	doc.stopped = 1
	doc.save()


def check_automatic_check(context) -> StepResult:
	"""The step vat_id_automatic_check: done when the company confirms on a change and renews daily; otherwise it says
	what the automatic check sends and to whom, and offers to switch both on, once the company has its own USt-IdNr."""
	company = context.company
	values = frappe.db.get_value(SETTINGS, company, ["ust_idnr", *AUTOMATIC_FIELDS], as_dict=True)
	document = (SETTINGS, company)
	if not vatid.is_german(values.ust_idnr):
		return StepResult(Outcome.UNDECIDED, (Note(AUTOMATIC_NEEDS_VAT_ID, (company,), open=True),), document)
	switched = [bool(values.get(field)) for field in AUTOMATIC_FIELDS]
	if all(switched):
		return StepResult(Outcome.SKIPPED, (Note(AUTOMATIC_ON, (company,)),), document)
	notes = [Note(AUTOMATIC_OFF, (company,), open=True)]
	if any(switched):
		notes.append(Note(AUTOMATIC_PARTLY, (company,)))
	return StepResult(
		Outcome.UNDECIDED, tuple(notes), document, Action(SWITCH_ON, f"{__name__}.enable_automatic_check")
	)


@frappe.whitelist(methods=["POST"])
def enable_automatic_check(company: str | None = None) -> None:
	"""The action of vat_id_automatic_check: switch on the confirmation on a change and the daily renewal of the
	company."""
	frappe.only_for(MANAGER, message=True)
	if not company or not frappe.db.exists(SETTINGS, company):
		frappe.throw(_("There is no company {0}.").format(company or ""))
	frappe.db.set_value(SETTINGS, company, dict.fromkeys(AUTOMATIC_FIELDS, 1))
