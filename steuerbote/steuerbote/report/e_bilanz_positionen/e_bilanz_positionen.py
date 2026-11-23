"""E-Bilanz Positionen: the positions of the E-Bilanz of a company, year and Bilanzart as a tree, each opening to the
accounts behind it, with a hint where the Umsatzerlöse differ from Kz 81, 86, 41 and 45 of the Voranmeldungen filed for
the year.

The report reads the E-Bilanz as Berechnen wrote it, the filed one that no Berichtigung replaced or else the newest
draft, and the Voranmeldungen as the Umsatzsteuererklärung reads them (steuerbote/ustjahr_sources.py); rows.py turns
both into its rows, without Frappe.
"""

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, fmt_money

from steuerbote import ustjahr_sources
from steuerbote.jahresmeldung.lifecycle import Status
from steuerbote.steuerbote.report.e_bilanz_positionen import rows

DOCTYPE = "Electronic Balance Sheet"
FILTERS = ("company", "year", "statement_type")


def execute(filters: dict | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	filters = frappe._dict(filters or {})
	if any(filters.get(name) in (None, "") for name in FILTERS):
		return get_columns(), []
	frappe.has_permission("Company", "read", doc=filters.company, throw=True)
	name = ebilanz_of(filters.company, cint(filters.year), filters.statement_type)
	if name is None:
		return get_columns(), [
			note(
				_("There is no E-Bilanz for {0}, {1} and {2} yet.").format(
					filters.company, cint(filters.year), _(filters.statement_type)
				)
			)
		]
	doc = frappe.get_doc(DOCTYPE, name)
	doc.check_permission("read")
	positions = [row.as_dict() for row in doc.positions]
	found = rows.report_rows(positions, [row.as_dict() for row in doc.accounts])
	currency = frappe.get_cached_value("Company", doc.company, "default_currency")
	for row in found:
		row["currency"] = currency
	hint = rows.revenue_note(
		rows.revenue(positions, ustjahr_sources.filed_voranmeldungen(doc.company, cint(doc.year)))
	)
	notes = [note(_("E-Bilanz {0}, {1}.").format(doc.name, _(doc.status)))]
	if hint is not None:
		template, values = hint
		notes.append(note(_(template).format(*(_money(value, currency) for value in values))))
	return get_columns(), notes + found


def ebilanz_of(company: str, year: int, statement_type: str) -> str | None:
	"""The E-Bilanz of the key: the filed one that no Berichtigung replaced, else the newest draft."""
	for filters in ({"docstatus": 1, "status": Status.FILED.value}, {"docstatus": 0}):
		names = frappe.get_all(
			DOCTYPE,
			filters={"company": company, "year": year, "statement_type": statement_type, **filters},
			order_by="creation desc",
			limit=1,
			pluck="name",
		)
		if names:
			return names[0]
	return None


def note(text: str) -> dict[str, Any]:
	"""A row of its own that tells the reader something about the report."""
	return {"key": None, "parent_key": None, "indent": 0, "label": text, "bold": 0}


def get_columns() -> list[dict[str, Any]]:
	money = {"fieldtype": "Currency", "options": "currency", "width": 140}
	return [
		{"fieldname": "key", "label": _("Position"), "fieldtype": "Data", "width": 280},
		{"fieldname": "label", "label": _("Description"), "fieldtype": "Data", "width": 360},
		{"fieldname": "component", "label": _("Report Component"), "fieldtype": "Data", "width": 90},
		{"fieldname": "mark", "label": _("Mark of the Taxonomy"), "fieldtype": "Data", "width": 120},
		{"fieldname": "ledger_amount", "label": _("Ledger Amount"), **money},
		{"fieldname": "reported", "label": _("Amount Reported"), **money},
		{
			"fieldname": "account",
			"label": _("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"width": 220,
		},
		{"fieldname": "account_number", "label": _("Account Number"), "fieldtype": "Data", "width": 110},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
	]


def _money(value: object, currency: str) -> object:
	return fmt_money(value, 2, currency) if not isinstance(value, int) else value
