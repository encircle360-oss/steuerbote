"""The deadlines of the companies of a site, and the daily reminder of those not filed.

steuerbote.deadlines computes the deadlines from plain data. This module reads that data from the site: the rules
of the VAT Return Settings and the day they were made; the years, the size history and the day of the Annual Filing
Settings, with the last days of the Fiscal Years and the day the company was founded (Company.date_of_establishment);
the VAT Returns, Recapitulative Statements and VAT Return Extensions of a company and its annual documents, each with
the day it was filed and the status it holds; the holidays of its Holiday List (steuerbote.holiday_list) and, for a
Meldezeitraum without a Recapitulative Statement, whether its ledger holds anything to report
(steuerbote.zm_sources). A document is filed once it is submitted, or sent through Steuerbote with an outcome that
ELSTER accepted or that is unknown, even if it was cancelled or discarded since (transmission.filings). The report
Offene Fristen shows the deadlines, and annual_deadline() gives an annual document its Fälligkeitsdatum.

The annual documents are read through the registry steuerbote.deadlines.annual.DOCTYPES, by the fields every annual
document carries (steuerbote.jahresmeldung.lifecycle.standard_fields).

send_reminders() runs once a day (scheduler_events in hooks.py). For each company with VAT Return Settings or Annual
Filing Settings whose VAT Return Settings name recipients, it sends one e-mail in German with the deadlines that are
not filed and fall due within the days of notice of those settings, or are overdue, and records each of them with its
recipients in a Deadline Reminder; a deadline reminded on a day is not reminded again that day. The e-mail has a text
part of its own with the address of every link (templates/emails/steuerbote_deadline_reminder), and the Error Log of
the job is written in the language of the site. A company without a Holiday List gets the holidays of every state
(steuerbote.holiday_list), and its deadlines say so. check_setup() is the step of Steuerbote einrichten that names
what would let a deadline drop out or a reminder reach nobody.
"""

from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	cint,
	escape_html,
	formatdate,
	get_absolute_url,
	get_url,
	get_url_to_report,
	getdate,
	validate_email_address,
)

from steuerbote import deadlines, holiday_list, zm_sources
from steuerbote.deadlines import Deadline, Filing, Kind, Note, Status, annual
from steuerbote.setup.steps import Note as StepNote
from steuerbote.setup.steps import Outcome, StepResult
from steuerbote.steuerbote.doctype.annual_filing_settings.annual_filing_settings import settings_of
from steuerbote.steuerbote.doctype.deadline_reminder.deadline_reminder import DOCTYPE as REMINDER
from steuerbote.steuerbote.doctype.deadline_reminder.deadline_reminder import reminder_name
from steuerbote.steuerbote.doctype.elster_transmission.transmission import filings
from steuerbote.steuerbote.doctype.recapitulative_statement.bridge import reporting_period
from steuerbote.steuerbote.doctype.recapitulative_statement.recapitulative_statement import (
	DOCTYPE as RECAPITULATIVE_STATEMENT,
)
from steuerbote.steuerbote.doctype.vat_return.vat_return import DOCTYPE as VAT_RETURN
from steuerbote.steuerbote.doctype.vat_return_extension.vat_return_extension import (
	DOCTYPE as VAT_RETURN_EXTENSION,
)
from steuerbote.steuerbote.doctype.vat_return_settings import rules as vat_rules
from steuerbote.ustva import Mapping
from steuerbote.ustva.period import Period, Rhythm
from steuerbote.zm.rhythm import Coverage

SETTINGS = "VAT Return Settings"
ANNUAL_SETTINGS = "Annual Filing Settings"
MAPPING = "VAT Return Mapping"
TRANSMISSION = "ELSTER Transmission"
FISCAL_YEAR = "Fiscal Year"
REPORT = "Offene Fristen"
SUBMITTED = 1
CANCELLED = 2
# The reminder goes to addresses, not to users with a language of their own, and names the filings in German.
EMAIL_LANGUAGE = "de"
EMAIL_DATE_FORMAT = "dd.mm.yyyy"
# Each e-mail is about one company, so its table leaves out the column of the company.
EMAIL_COLUMNS = ("kind", "period_label", "due", "days", "status", "document", "document_status", "note")
SAVEPOINT = "steuerbote_deadline_reminder"
NOTE_SEPARATOR = "; "
# The templates of the e-mail under templates/emails, whose text part keeps the addresses of the links.
EMAIL_TEMPLATE = "steuerbote_deadline_reminder"
# Lines and padding of the table as HTML attributes, which mail clients show without a style sheet.
TABLE_ATTRIBUTES = 'border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse"'
# The fields every annual document carries that tell whether and when it filed its deadlines.
ANNUAL_FIELDS = ("name", "year", "status", "docstatus", "filed_via", "filed_on", "modified")


def companies() -> list[str]:
	"""Every company with VAT Return Settings or Annual Filing Settings, by name."""
	return sorted({*frappe.get_all(SETTINGS, pluck="name"), *frappe.get_all(ANNUAL_SETTINGS, pluck="name")})


def has_settings(company: str) -> bool:
	"""Whether the company has VAT Return Settings or Annual Filing Settings, and so deadlines."""
	return bool(frappe.db.exists(SETTINGS, company) or frappe.db.exists(ANNUAL_SETTINGS, company))


def company_deadlines(company: str, today: date, horizon_days: int) -> list[Deadline]:
	"""The deadlines of the company due within ``horizon_days`` days from ``today``, or overdue and not filed."""
	settings = frappe.get_doc(SETTINGS, company) if frappe.db.exists(SETTINGS, company) else None
	return deadlines_of(company, settings, today, horizon_days)


def deadlines_of(company: str, settings: Document | None, today: date, horizon_days: int) -> list[Deadline]:
	"""The deadlines of the company from its VAT Return Settings, where it has them, and from its Annual Filing
	Settings, as company_deadlines() gives them."""
	vat_rules: dict[str, Any] = {}
	if settings is not None:
		vat_rules = {
			"period_rules": settings.get_period_rules(),
			"prepayments": settings.get_prepayments(),
			"zm_rules": settings.get_zm_rules(),
			"since": getdate(settings.creation),
			"books_start": getdate(settings.books_start) if settings.get("books_start") else None,
		}
	rules = deadlines.CompanyRules(company, annual=annual_rules(company), **vat_rules)
	return deadlines.upcoming(
		rules,
		documents(company),
		today,
		horizon_days,
		holiday_list.holidays(company),
		reportable=reportable(company),
		document_types=document_types(),
		holidays_complete=holiday_list.has_list(company),
	)


def annual_rules(company: str) -> deadlines.AnnualRules | None:
	"""What the Annual Filing Settings of the company, its Fiscal Years and the day it was founded say about its
	annual deadlines; None without the settings, which hold the Steuerberatung, the early orders and the size class of
	each year."""
	settings = settings_of(company)
	if settings is None:
		return None
	return deadlines.AnnualRules(
		years=settings.get_years(),
		fiscal_year_ends=fiscal_year_ends(company),
		size_history=settings.get_size_history(),
		founded_on=_date(frappe.db.get_value("Company", company, "date_of_establishment")),
		since=getdate(settings.creation),
	)


def annual_deadline(company: str, kind: Kind, year: int, *, opening_balance: bool = False) -> date | None:
	"""The day the annual filing of ``kind`` for ``year`` is due, as Offene Fristen lists it: the Fälligkeitsdatum an
	annual document gives as its compute_deadline, with ``opening_balance`` for the Eröffnungsbilanz of the E-Bilanz.
	None where the company owes none, such as without Annual Filing Settings or in a year before the first."""
	rules = annual_rules(company)
	if rules is None:
		return None
	return deadlines.annual_due(
		rules, kind, year, holiday_list.holidays(company), opening_balance=opening_balance
	)


def fiscal_year_ends(company: str) -> list[date]:
	"""The last days of the Fiscal Years of the company that are not disabled: those that name it, and those that
	name no company and so serve every company, as ERPNext reads them (Fiscal Year Company)."""
	ends = []
	for row in frappe.get_all(FISCAL_YEAR, filters={"disabled": 0}, fields=["name", "year_end_date"]):
		named = [entry.company for entry in frappe.get_cached_doc(FISCAL_YEAR, row.name).companies]
		if not named or company in named:
			ends.append(getdate(row.year_end_date))
	return ends


def document_types() -> dict[Kind, str]:
	"""The DocType of each kind of deadline: those of the Voranmeldung, the Zusammenfassende Meldung and the
	Sondervorauszahlung, and the annual DocTypes of the registry."""
	found = {kind: doctype for kind, doctype in deadlines.DOCUMENT_TYPES.items() if kind not in annual.KINDS}
	for doctype, entry in annual.DOCTYPES.items():
		found.update(dict.fromkeys(entry.kinds, doctype))
	return found


def documents(company: str) -> list[Filing]:
	"""The VAT Returns, Recapitulative Statements and VAT Return Extensions of the company and its annual documents,
	the latest first, with the day each was filed and the status it holds."""
	return [*_vat_returns(company), *_statements(company), *_extensions(company), *_annual_documents(company)]


def _vat_returns(company: str) -> list[Filing]:
	"""A return is filed once it is submitted, or sent through Steuerbote even if it was cancelled since
	(vat_return.filings); a return cancelled without that never reached the Finanzamt."""
	rows = frappe.get_all(
		VAT_RETURN,
		filters={"company": company},
		fields=["name", "year", "rhythm", "period_index", "docstatus", "status", "modified"],
		order_by="creation desc",
	)
	sent = _days_filed(VAT_RETURN, [row.name for row in rows])
	found = []
	for row in rows:
		filed_on = sent.get(row.name) or (getdate(row.modified) if row.docstatus == SUBMITTED else None)
		if row.docstatus == CANCELLED and filed_on is None:
			continue
		period = Period(cint(row.year), Rhythm(row.rhythm), cint(row.period_index))
		found.append(Filing(Kind.VORANMELDUNG, period, row.name, filed_on, row.status))
	return found


def _days_filed(doctype: str, names: list[str]) -> dict[str, date]:
	"""The day each of the documents was filed by its latest record that files it: the day noted for a filing outside
	Steuerbote, or else the day its transmission finished."""
	records = filings(doctype, names)
	if not records:
		return {}
	days = {
		row.name: getdate(row.filed_on or row.finished_at or row.started_at)
		for row in frappe.get_all(
			TRANSMISSION,
			filters={"name": ["in", [record.name for record in records]]},
			fields=["name", "filed_on", "finished_at", "started_at"],
		)
	}
	filed: dict[str, date] = {}
	for record in records:
		filed.setdefault(record.document, days[record.name])
	return filed


def _statements(company: str) -> list[Filing]:
	"""A statement is filed once it is submitted, or sent through Steuerbote even if it was discarded since; a
	statement discarded without that never reached the BZSt."""
	rows = frappe.get_all(
		RECAPITULATIVE_STATEMENT,
		filters={"company": company},
		fields=["name", "year", "period_kind", "period_index", "docstatus", "status", "filed_on", "modified"],
		order_by="creation desc",
	)
	sent = _days_filed(RECAPITULATIVE_STATEMENT, [row.name for row in rows])
	found = []
	for row in rows:
		filed_on = sent.get(row.name) or _noted_filing(row)
		if row.docstatus == CANCELLED and filed_on is None:
			continue
		period = reporting_period(row.period_kind, cint(row.year), cint(row.period_index))
		found.append(Filing(Kind.ZUSAMMENFASSENDE_MELDUNG, period, row.name, filed_on, row.status))
	return found


def _extensions(company: str) -> list[Filing]:
	"""A form is filed once it is submitted, or sent through Steuerbote even if it was discarded since. A filed form
	cancelled for its correction stays filed with the Finanzamt; any other cancelled form files nothing."""
	rows = frappe.get_all(
		VAT_RETURN_EXTENSION,
		filters={"company": company},
		fields=["name", "year", "docstatus", "status", "filed_on", "modified"],
		order_by="creation desc",
	)
	sent = _days_filed(VAT_RETURN_EXTENSION, [row.name for row in rows])
	found = []
	for row in rows:
		filed_on = sent.get(row.name) or _noted_filing(row)
		if row.docstatus == CANCELLED and filed_on is None:
			continue
		found.append(Filing(Kind.SONDERVORAUSZAHLUNG, cint(row.year), row.name, filed_on, row.status))
	return found


def _annual_documents(company: str) -> list[Filing]:
	"""The annual documents of the company in each DocType of the registry, the latest first, read by the fields
	every annual document carries; the day a Senden or the note of a filing outside Steuerbote files one
	comes from its ELSTER Transmissions (transmission.filings), and the Bilanzart of an E-Bilanz tells its
	Eröffnungsbilanz apart."""
	found: list[Filing] = []
	for doctype, entry in annual.DOCTYPES.items():
		opening = entry.opening_balance_field
		if opening and not frappe.get_meta(doctype).has_field(opening):
			opening = None
		rows = frappe.get_all(
			doctype,
			filters={"company": company},
			fields=[*ANNUAL_FIELDS, *([opening] if opening else [])],
			order_by="creation desc",
		)
		sent = _days_filed(doctype, [row.name for row in rows])
		found += deadlines.annual_filings(
			entry.kinds,
			[
				deadlines.AnnualDocument(
					row.name,
					cint(row.year),
					row.status,
					getdate(row.modified),
					docstatus=cint(row.docstatus),
					filed_via=row.filed_via or None,
					filed_on=_date(row.filed_on),
					sent_on=sent.get(row.name),
					opening_balance=bool(opening) and row.get(opening) == annual.OPENING_BALANCE,
				)
				for row in rows
			],
		)
	return found


def _noted_filing(row: frappe._dict) -> date | None:
	"""The day a statement or a form was filed, from the note of its filing that submits it."""
	if row.docstatus == SUBMITTED:
		return getdate(row.filed_on or row.modified)
	return getdate(row.filed_on) if row.docstatus == CANCELLED and row.filed_on else None


def _date(value: object) -> date | None:
	"""A date field as a date; getdate of nothing would give today."""
	return getdate(value) if value else None


def reportable(company: str) -> Callable[[Coverage], bool]:
	"""Whether a Meldezeitraum of the company without a Recapitulative Statement has anything to report: a voucher
	that adds to Kz 41 or 42 in its goods months or to Kz 21 in its services months, read as "Berechnen" reads
	them (zm_sources.shares). Without a VAT Return Mapping that fits the year, Steuerbote cannot tell, and the
	Meldezeitraum counts."""
	mappings: dict[int, Mapping | None] = {}

	def has_something_to_report(coverage: Coverage) -> bool:
		year = coverage.period.year
		if year not in mappings:
			mappings[year] = _mapping(company, year)
		mapping = mappings[year]
		if mapping is None:
			return True
		return any(share.amount for share in zm_sources.shares(company, coverage, mapping))

	return has_something_to_report


def _mapping(company: str, year: int) -> Mapping | None:
	if not frappe.db.exists(MAPPING, company):
		return None
	try:
		return frappe.get_doc(MAPPING, company).to_mapping(year)
	except frappe.ValidationError:
		# to_mapping tells the user why the mapping does not fit the form; nobody here asked for the mapping.
		frappe.clear_last_message()
		return None


def column_labels(language: str | None = None) -> dict[str, str]:
	"""The labels of the columns of the report Offene Fristen, which the table of the reminder shows as well."""
	return {
		"company": _("Company", lang=language),
		"kind": _("Kind of Deadline", lang=language),
		"period_label": _("Time Period", lang=language),
		"due": _("Due On", lang=language),
		"days": _("Days Left", lang=language),
		"status": _("Status", lang=language),
		"document": _("Filing Document", lang=language),
		"document_status": _("State of the Document", lang=language),
		"note": _("Deadline Note", lang=language),
	}


def note_texts(language: str | None = None) -> dict[Note, str]:
	"""What each note of a deadline says (steuerbote.deadlines.annual.Note)."""
	return {
		Note.ADVISOR: _("Prepared by a Steuerberatung (§ 149 Abs. 3 AO)", lang=language),
		Note.EARLY_REQUEST: _("Ordered early by the Finanzamt (§ 149 Abs. 4 AO)", lang=language),
		Note.WITH_KST: _("No deadline of its own: with the Körperschaftsteuererklärung", lang=language),
		Note.OPENING_BALANCE: _(
			"Eröffnungsbilanz of the founding year (§ 5b Abs. 1 Satz 4 EStG); its deadline is assumed",
			lang=language,
		),
		Note.ASSUMED_CLASS: _(
			"No size class for the fiscal year: eight months (§ 42a Abs. 2 GmbHG)", lang=language
		),
		Note.ON_WEEKEND: _("On a weekend; whether § 193 BGB moves the day is unverified", lang=language),
		Note.DAUERFRIST_NOT_RECORDED: _(
			"No Dauerfristverlängerung entered for the year, but one for an earlier year, which holds until it is given up or revoked (§ 46 UStDV): enter the year in the VAT Return Settings, with the extension or without it",
			lang=language,
		),
		Note.NATIONWIDE_HOLIDAYS: _(
			"The company has no holiday list: only the holidays of every state move the day (§ 108 Abs. 3 AO)",
			lang=language,
		),
	}


def note_text(deadline: Deadline, language: str | None = None) -> str:
	"""The notes of the deadline in one line."""
	texts = note_texts(language)
	return NOTE_SEPARATOR.join(texts[note] for note in deadline.notes)


def document_link(deadline: Deadline, absolute: bool = False, language: str | None = None) -> str:
	"""A link to the document of the deadline, or for a deadline without one to a new document of its period."""
	route = _document_route(deadline)
	label = document_label(deadline, language)
	href = get_url(route) if absolute else route
	return f'<a href="{escape_html(href)}">{escape_html(label)}</a>'


def document_label(deadline: Deadline, language: str | None = None) -> str:
	"""The name of the document of the deadline, or the text of the link to a new one."""
	return deadline.document_name or _("Create Document", lang=language)


def _document_route(deadline: Deadline) -> str:
	if deadline.document_name:
		return get_absolute_url(deadline.document_type, deadline.document_name)
	values = urlencode(deadlines.new_document_values(deadline))
	return f"{get_absolute_url(deadline.document_type, 'new')}?{values}"


HOLIDAY_LIST_SET = "The holidays of the Holiday List {0} move the deadlines of {1} (§ 108 Abs. 3 AO); it should hold the holidays of the state of the Finanzamt."
HOLIDAY_LIST_MISSING = "{0} has no Default Holiday List, so only the holidays of every state move its deadlines (§ 108 Abs. 3 AO). Set the list of the state of its Finanzamt in the company, so that a holiday of that state such as Fronleichnam moves them too."
NO_RECIPIENTS = "The VAT Return Settings name no recipients of the reminder, so nobody is reminded of the deadlines of {0}; the report Offene Fristen shows them."
INVALID_RECIPIENTS = (
	"These entries of the recipients of the reminder are no e-mail addresses and get no reminder: {0}."
)
NO_OUTGOING_ACCOUNT = "The site has no default outgoing e-mail account, so the reminder of the deadlines reaches nobody. Review the Email Queue before an account is switched on: every mail waiting there goes out with it."
RECIPIENTS_SET = (
	"The reminder goes to {0} every day while a deadline is not filed, from {1} days before it is due."
)
NO_VAT_RETURN_STATED = "The Annual Filing Settings state that {0} owes no Umsatzsteuererklärung for {1}: {2}. This is the statement of the company, made with its Steuerberatung; Steuerbote does not judge the status for VAT."
DAUERFRIST_CARRIED = "The VAT Return Settings have the Dauerfristverlängerung for {0} but no row for {1}. It holds until it is given up or revoked (§ 46 UStDV), and a monthly filer pays the Sondervorauszahlung of every year by 10 February (§ 48 Abs. 2 UStDV): enter {1}, with the extension or without it."
SETUP_MESSAGES = (
	HOLIDAY_LIST_SET,
	HOLIDAY_LIST_MISSING,
	NO_RECIPIENTS,
	INVALID_RECIPIENTS,
	NO_OUTGOING_ACCOUNT,
	RECIPIENTS_SET,
	DAUERFRIST_CARRIED,
	NO_VAT_RETURN_STATED,
)


def check_setup(context: Any) -> StepResult:
	"""Fristen und Erinnerung, a step of Steuerbote einrichten: whether the holidays, the Dauerfristverlängerung of the
	year and the reminder are set so that no deadline drops out or moves unseen and the reminder reaches someone."""
	company = context.company
	settings = frappe.get_doc(SETTINGS, company)
	notes: list[StepNote] = []
	holiday_list_name = frappe.db.get_value("Company", company, "default_holiday_list")
	if holiday_list_name:
		notes.append(StepNote(HOLIDAY_LIST_SET, (holiday_list_name, company)))
	else:
		notes.append(StepNote(HOLIDAY_LIST_MISSING, (company,), open=True))
	year = getdate(context.today).year
	carried = vat_rules.carried_dauerfrist(settings.get_prepayments(), year)
	if carried:
		notes.append(StepNote(DAUERFRIST_CARRIED, (carried, year), open=True))
	invalid = invalid_recipients(settings.deadline_recipients)
	if invalid:
		notes.append(StepNote(INVALID_RECIPIENTS, (", ".join(invalid),), open=True))
	recipients = [
		entry for line in (settings.deadline_recipients or "").splitlines() if (entry := line.strip())
	]
	valid = [entry for entry in recipients if entry not in invalid]
	if not valid:
		notes.append(StepNote(NO_RECIPIENTS, (company,), open=True))
	else:
		notes.append(StepNote(RECIPIENTS_SET, (", ".join(valid), cint(settings.reminder_days))))
		if not outgoing_account():
			notes.append(StepNote(NO_OUTGOING_ACCOUNT, open=True))
	annual = settings_of(company)
	for row in annual.get_years() if annual else ():
		if row.no_vat_return:
			reason = _(row.no_vat_return_reason or "")
			notes.append(StepNote(NO_VAT_RETURN_STATED, (company, row.year, reason)))
	outcome = Outcome.UNDECIDED if any(note.open for note in notes) else Outcome.SKIPPED
	return StepResult(outcome, tuple(notes), (SETTINGS, settings.name))


def send_reminders() -> None:
	"""The daily job: the reminder of every company with VAT Return Settings or Annual Filing Settings, each in a
	savepoint of its own, so that a company whose reminder fails leaves those of the others."""
	today = getdate()
	for company in companies():
		frappe.db.savepoint(SAVEPOINT)
		try:
			remind(company, today)
		except Exception:
			frappe.db.rollback(save_point=SAVEPOINT)
			frappe.log_error(
				title=_("The reminder of the deadlines of {0} failed", lang=site_language()).format(company),
				reference_doctype=SETTINGS,
				reference_name=company,
			)
		else:
			frappe.db.release_savepoint(SAVEPOINT)


def remind(company: str, today: date) -> bool:
	"""Send the recipients of the company one e-mail with its deadlines that are not filed and due within the days
	of notice or overdue, those reminded today already left out, and record each. True when it sends one. Recipients
	and days of notice are those of the VAT Return Settings; a company without them has nobody to remind."""
	if not frappe.db.exists(SETTINGS, company):
		return False
	settings = frappe.get_doc(SETTINGS, company)
	recipients = recipients_of(company, settings.deadline_recipients)
	if not recipients:
		return False
	due = [
		deadline
		for deadline in deadlines_of(company, settings, today, cint(settings.reminder_days))
		if deadline.status is not Status.FILED
		and not frappe.db.exists(REMINDER, _record_name(deadline, today))
	]
	if not due:
		return False
	for deadline in due:
		frappe.get_doc(
			{
				"doctype": REMINDER,
				"company": company,
				"kind": deadline.kind.value,
				"period_label": deadline.period_label,
				"due_date": deadline.due,
				"sent_on": today,
				"recipients": "\n".join(recipients),
			}
		).insert(ignore_permissions=True)
	html = reminder_message(company, due, today)
	frappe.sendmail(
		recipients=recipients,
		subject=_("Steuerbote: open deadlines of {0}", lang=EMAIL_LANGUAGE).format(company),
		message=html,
		template=EMAIL_TEMPLATE,
		args={"html": html, "text": reminder_text(company, due, today)},
		reference_doctype=SETTINGS,
		reference_name=company,
		add_unsubscribe_link=0,
	)
	return True


def site_language() -> str:
	"""The language of the site, in which the Error Log of the daily job is written, whatever the context it runs in."""
	return frappe.db.get_single_value("System Settings", "language") or EMAIL_LANGUAGE


def invalid_recipients(text: str | None) -> list[str]:
	"""The lines of the field that are no e-mail address."""
	return [
		entry
		for line in (text or "").splitlines()
		if (entry := line.strip()) and not validate_email_address(entry)
	]


def outgoing_account() -> bool:
	"""Whether the site has a default outgoing e-mail account, without which no reminder leaves it."""
	return bool(frappe.db.exists("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}))


def recipients_of(company: str, text: str | None) -> list[str]:
	"""The e-mail addresses of the field, one per line. An entry that is no address gets no reminder, and the Error
	Log says so."""
	found, invalid = [], []
	for line in (text or "").splitlines():
		entry = line.strip()
		if not entry:
			continue
		addresses = validate_email_address(entry)
		if addresses:
			found.extend(address.strip() for address in addresses.split(","))
		else:
			invalid.append(entry)
	if invalid:
		language = site_language()
		frappe.log_error(
			title=_("The reminder of the deadlines of {0} skips addresses", lang=language).format(company),
			message=_("These entries are no e-mail addresses and get no reminder: {0}", lang=language).format(
				", ".join(invalid)
			),
			reference_doctype=SETTINGS,
			reference_name=company,
		)
	return found


def reminder_message(company: str, items: list[Deadline], today: date) -> str:
	"""The body of the reminder: the deadlines as the report shows them, with links to their documents."""
	language = EMAIL_LANGUAGE
	labels = column_labels(language)
	head = "".join(f"<th>{escape_html(labels[field])}</th>" for field in EMAIL_COLUMNS)
	rows = "".join(_message_row(item, today, language) for item in items)
	intro = _("These deadlines of {0} are not filed yet:", lang=language).format(company)
	report = f'<a href="{escape_html(get_url_to_report(REPORT))}">{escape_html(REPORT)}</a>'
	outro = _(
		"The report {0} shows every deadline. This reminder comes every day until a deadline is filed; its recipients and its days of notice are set in the VAT Return Settings.",
		lang=language,
	).format(report)
	table = f"<table {TABLE_ATTRIBUTES}><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"
	return f"<p>{escape_html(intro)}</p>{table}<p>{outro}</p>"


def reminder_text(company: str, items: list[Deadline], today: date) -> str:
	"""The text part of the reminder: each deadline on its lines, with the address of its document and of the report,
	for a mail client that shows no HTML."""
	language = EMAIL_LANGUAGE
	labels = column_labels(language)
	blocks = [_("These deadlines of {0} are not filed yet:", lang=language).format(company)]
	for item in items:
		state = f", {labels['document_status']}: {item.document_status}" if item.document_status else ""
		lines = [
			f"{item.kind.value} {item.period_label}",
			f"{labels['due']}: {formatdate(item.due, EMAIL_DATE_FORMAT)} ({labels['days']}: {item.days_left(today)})",
			f"{labels['status']}: {item.status.value}{state}",
			f"{labels['document']}: {document_label(item, language)} {get_url(_document_route(item))}",
		]
		note = note_text(item, language)
		if note:
			lines.append(f"{labels['note']}: {note}")
		blocks.append("\n".join(lines))
	blocks.append(
		_(
			"The report {0} shows every deadline. This reminder comes every day until a deadline is filed; its recipients and its days of notice are set in the VAT Return Settings.",
			lang=language,
		).format(f"{REPORT} ({get_url_to_report(REPORT)})")
	)
	return "\n\n".join(blocks) + "\n"


def _message_row(item: Deadline, today: date, language: str) -> str:
	cells = (
		escape_html(item.kind.value),
		escape_html(item.period_label),
		formatdate(item.due, EMAIL_DATE_FORMAT),
		str(item.days_left(today)),
		escape_html(item.status.value),
		document_link(item, absolute=True, language=language),
		escape_html(item.document_status or ""),
		escape_html(note_text(item, language)),
	)
	return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


def _record_name(deadline: Deadline, today: date) -> str:
	return reminder_name(deadline.company, deadline.kind.value, deadline.period_label, deadline.due, today)
