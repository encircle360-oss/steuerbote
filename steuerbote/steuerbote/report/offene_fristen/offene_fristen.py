"""Offene Fristen: the deadlines of the Umsatzsteuer-Voranmeldung, the Zusammenfassende Meldung and the
Sondervorauszahlung of one company or of every company with VAT Return Settings, due within the horizon or overdue
and not filed, by due date.

steuerbote.steuerbote.deadlines reads the settings and the documents of each company, and steuerbote.deadlines
computes its deadlines, as for the daily reminder; this module only makes the rows.
"""

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, getdate

from steuerbote.deadlines import Deadline
from steuerbote.steuerbote.deadlines import SETTINGS, column_labels, company_deadlines, document_link

COMPANY = "company"
HORIZON = "horizon"
FILTERS = (COMPANY, HORIZON)
# The days ahead without a horizon; the filter of the script starts with the same number.
DEFAULT_HORIZON = 60
COLUMNS = (
	{"fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 220},
	{"fieldname": "kind", "fieldtype": "Data", "width": 210},
	{"fieldname": "period_label", "fieldtype": "Data", "width": 200},
	{"fieldname": "due", "fieldtype": "Date", "width": 110},
	{"fieldname": "days", "fieldtype": "Int", "width": 80},
	{"fieldname": "status", "fieldtype": "Data", "width": 110},
	{"fieldname": "document", "fieldtype": "Data", "width": 180},
)


def execute(filters: dict | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	filters = frappe._dict(filters or {})
	horizon = DEFAULT_HORIZON if filters.get(HORIZON) in (None, "") else cint(filters.get(HORIZON))
	if horizon < 0:
		frappe.throw(_("The horizon is a number of days from 0 on."))
	today = getdate()
	found = [
		deadline
		for company in _companies(filters.get(COMPANY))
		for deadline in company_deadlines(company, today, horizon)
	]
	found.sort(key=lambda deadline: (deadline.due, deadline.company))
	return get_columns(), [_row(deadline, today) for deadline in found]


def get_columns() -> list[dict[str, Any]]:
	"""The columns, with the labels the reminder shows as well."""
	labels = column_labels()
	return [{**column, "label": labels[column["fieldname"]]} for column in COLUMNS]


def _companies(company: str | None) -> list[str]:
	"""The company of the filter, or every company with settings that the user may read."""
	if company:
		frappe.has_permission("Company", "read", doc=company, throw=True)
		return [company] if frappe.db.exists(SETTINGS, company) else []
	return [
		name
		for name in frappe.get_all(SETTINGS, pluck="name", order_by="name")
		if frappe.has_permission("Company", "read", doc=name)
	]


def _row(deadline: Deadline, today: date) -> dict[str, Any]:
	return {
		"company": deadline.company,
		"kind": deadline.kind.value,
		"period_label": deadline.period_label,
		"due": deadline.due,
		"days": deadline.days_left(today),
		"status": deadline.status.value,
		"document": document_link(deadline),
	}
