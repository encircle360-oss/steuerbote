"""The deadlines of the companies of a site, and the daily reminder of those not filed.

steuerbote.deadlines computes the deadlines from plain data. This module reads that data from the site: the rules
of the VAT Return Settings and the day they were made, the VAT Returns, Recapitulative Statements and VAT Return
Extensions of a company with the day each was filed, the holidays of its Holiday List (steuerbote.holiday_list)
and, for a Meldezeitraum without a Recapitulative Statement, whether its ledger holds anything to report
(steuerbote.zm_sources). The report Offene Fristen shows the deadlines.

send_reminders() runs once a day (scheduler_events in hooks.py). For each company whose settings name recipients,
it sends one e-mail in German with the deadlines that are not filed and fall due within the days of notice of the
settings, or are overdue, and records each of them in a Deadline Reminder; a deadline reminded on a day is not
reminded again that day.
"""

from collections.abc import Callable
from datetime import date
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
from steuerbote.deadlines import Deadline, Filing, Kind, Status
from steuerbote.steuerbote.doctype.deadline_reminder.deadline_reminder import DOCTYPE as REMINDER
from steuerbote.steuerbote.doctype.deadline_reminder.deadline_reminder import reminder_name
from steuerbote.steuerbote.doctype.recapitulative_statement.bridge import reporting_period
from steuerbote.steuerbote.doctype.elster_transmission.transmission import filings
from steuerbote.steuerbote.doctype.vat_return.vat_return import DOCTYPE as VAT_RETURN
from steuerbote.ustva import Mapping
from steuerbote.ustva.period import Period, Rhythm
from steuerbote.zm.rhythm import Coverage

SETTINGS = "VAT Return Settings"
MAPPING = "VAT Return Mapping"
TRANSMISSION = "ELSTER Transmission"
REPORT = "Offene Fristen"
SUBMITTED = 1
CANCELLED = 2
# The reminder goes to addresses, not to users with a language of their own, and names the filings in German.
EMAIL_LANGUAGE = "de"
EMAIL_DATE_FORMAT = "dd.mm.yyyy"
# Each e-mail is about one company, so its table leaves out the column of the company.
EMAIL_COLUMNS = ("kind", "period_label", "due", "days", "status", "document")
SAVEPOINT = "steuerbote_deadline_reminder"


def company_deadlines(company: str, today: date, horizon_days: int) -> list[Deadline]:
	"""The deadlines of the company due within ``horizon_days`` days from ``today``, or overdue and not filed."""
	return deadlines_of(frappe.get_doc(SETTINGS, company), today, horizon_days)


def deadlines_of(settings: Document, today: date, horizon_days: int) -> list[Deadline]:
	"""The deadlines of the company of the settings, as company_deadlines() gives them."""
	company = settings.company
	rules = deadlines.CompanyRules(
		company,
		period_rules=settings.get_period_rules(),
		prepayments=settings.get_prepayments(),
		zm_rules=settings.get_zm_rules(),
		since=getdate(settings.creation),
	)
	return deadlines.upcoming(
		rules,
		documents(company),
		today,
		horizon_days,
		holiday_list.holidays(company),
		reportable=reportable(company),
	)


def documents(company: str) -> list[Filing]:
	"""The VAT Returns, Recapitulative Statements and VAT Return Extensions of the company, the latest first, with
	the day each was filed."""
	return [*_vat_returns(company), *_statements(company), *_extensions(company)]


def _vat_returns(company: str) -> list[Filing]:
	"""A return is filed once it is submitted, or sent through Steuerbote even if it was cancelled since
	(vat_return.filings); a return cancelled without that never reached the Finanzamt."""
	rows = frappe.get_all(
		"VAT Return",
		filters={"company": company},
		fields=["name", "year", "rhythm", "period_index", "docstatus", "modified"],
		order_by="creation desc",
	)
	sent = _days_filed([row.name for row in rows])
	found = []
	for row in rows:
		filed_on = sent.get(row.name) or (getdate(row.modified) if row.docstatus == SUBMITTED else None)
		if row.docstatus == CANCELLED and filed_on is None:
			continue
		period = Period(cint(row.year), Rhythm(row.rhythm), cint(row.period_index))
		found.append(Filing(Kind.VORANMELDUNG, period, row.name, filed_on))
	return found


def _days_filed(returns: list[str]) -> dict[str, date]:
	"""The day each of the returns was filed by its latest record that files it: the day noted for a filing outside
	Steuerbote, or else the day its transmission finished."""
	records = filings(VAT_RETURN, returns)
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
		filed.setdefault(record.vat_return, days[record.name])
	return filed


def _statements(company: str) -> list[Filing]:
	rows = frappe.get_all(
		"Recapitulative Statement",
		filters={"company": company, "docstatus": ["<", CANCELLED]},
		fields=["name", "year", "period_kind", "period_index", "docstatus", "filed_on", "modified"],
		order_by="creation desc",
	)
	return [
		Filing(
			Kind.ZUSAMMENFASSENDE_MELDUNG,
			reporting_period(row.period_kind, cint(row.year), cint(row.period_index)),
			row.name,
			_noted_filing(row),
		)
		for row in rows
	]


def _extensions(company: str) -> list[Filing]:
	"""A filed form cancelled for its correction stays filed with the Finanzamt; any other cancelled form files
	nothing."""
	rows = frappe.get_all(
		"VAT Return Extension",
		filters={"company": company},
		fields=["name", "year", "docstatus", "filed_on", "modified"],
		order_by="creation desc",
	)
	return [
		Filing(Kind.SONDERVORAUSZAHLUNG, cint(row.year), row.name, _noted_filing(row))
		for row in rows
		if row.docstatus != CANCELLED or row.filed_on
	]


def _noted_filing(row: frappe._dict) -> date | None:
	"""The day a statement or a form was filed, from the note of its filing that submits it."""
	if row.docstatus == SUBMITTED:
		return getdate(row.filed_on or row.modified)
	return getdate(row.filed_on) if row.docstatus == CANCELLED and row.filed_on else None


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
	}


def document_link(deadline: Deadline, absolute: bool = False, language: str | None = None) -> str:
	"""A link to the document of the deadline, or for a deadline without one to a new document of its period."""
	if deadline.document_name:
		route = get_absolute_url(deadline.document_type, deadline.document_name)
		label = deadline.document_name
	else:
		values = urlencode(deadlines.new_document_values(deadline))
		route = f"{get_absolute_url(deadline.document_type, 'new')}?{values}"
		label = _("Create Document", lang=language)
	href = get_url(route) if absolute else route
	return f'<a href="{escape_html(href)}">{escape_html(label)}</a>'


def send_reminders() -> None:
	"""The daily job: the reminder of every company, each in a savepoint of its own, so that a company whose reminder
	fails leaves those of the others."""
	today = getdate()
	for company in frappe.get_all(SETTINGS, pluck="name", order_by="name"):
		frappe.db.savepoint(SAVEPOINT)
		try:
			remind(company, today)
		except Exception:
			frappe.db.rollback(save_point=SAVEPOINT)
			frappe.log_error(
				title=_("The reminder of the deadlines of {0} failed").format(company),
				reference_doctype=SETTINGS,
				reference_name=company,
			)
		else:
			frappe.db.release_savepoint(SAVEPOINT)


def remind(company: str, today: date) -> bool:
	"""Send the recipients of the company one e-mail with its deadlines that are not filed and due within the days
	of notice or overdue, those reminded today already left out, and record each. True when it sends one."""
	settings = frappe.get_doc(SETTINGS, company)
	recipients = recipients_of(company, settings.deadline_recipients)
	if not recipients:
		return False
	due = [
		deadline
		for deadline in deadlines_of(settings, today, cint(settings.reminder_days))
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
			}
		).insert(ignore_permissions=True)
	frappe.sendmail(
		recipients=recipients,
		subject=_("Steuerbote: open deadlines of {0}", lang=EMAIL_LANGUAGE).format(company),
		message=reminder_message(company, due, today),
		reference_doctype=SETTINGS,
		reference_name=company,
		add_unsubscribe_link=0,
	)
	return True


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
		frappe.log_error(
			title=_("The reminder of the deadlines of {0} skips addresses").format(company),
			message=_("These entries are no e-mail addresses and get no reminder: {0}").format(
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
	table = f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"
	return f"<p>{escape_html(intro)}</p>{table}<p>{outro}</p>"


def _message_row(item: Deadline, today: date, language: str) -> str:
	cells = (
		escape_html(item.kind.value),
		escape_html(item.period_label),
		formatdate(item.due, EMAIL_DATE_FORMAT),
		str(item.days_left(today)),
		escape_html(item.status.value),
		document_link(item, absolute=True, language=language),
	)
	return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


def _record_name(deadline: Deadline, today: date) -> str:
	return reminder_name(deadline.company, deadline.kind.value, deadline.period_label, deadline.due, today)
