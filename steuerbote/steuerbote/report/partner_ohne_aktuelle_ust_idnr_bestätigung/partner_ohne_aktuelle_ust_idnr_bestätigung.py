"""Partner ohne aktuelle USt-IdNr-Bestätigung: the worklist of a company, every customer and supplier it deals with
whose USt-IdNr. lacks a current confirmation, with where it stands (steuerbote.vatid.partners.Standing): no
confirmation, too old, invalid, no answer, a number the BZSt does not confirm or a malformed one, only a simple
confirmation for want of an address or although one is known, or another name or address registered. Below them the
partners with a number that deal with no company yet, which no company asks about by itself.

steuerbote.steuerbote.partner_vat_ids reads the partners and their confirmations; this module only makes the rows.
"""

from typing import Any

import frappe
from frappe import _

from steuerbote.steuerbote import partner_vat_ids

COMPANY = "company"
PARTY_TYPE = "party_type"
FILTERS = (COMPANY, PARTY_TYPE)
NO_REQUESTER = "{0} has no own USt-IdNr. in its VAT Return Settings, so Steuerbote confirms nothing for it."
AUTOMATIC_OFF = "The automatic check is off for {0}: Steuerbote confirms a partner only when someone presses „Confirm VAT ID“ on the partner or on an invoice. Switch it on in Set Up Steuerbote or in the VAT Return Settings."
STANDING_NOTES = {
	"Missing": "No confirmation yet.",
	"Expired": "The latest confirmation is older than the settings allow.",
	"Invalid": "The latest answer found the number invalid.",
	"No Answer": "No query about the number was answered yet.",
	"Address Missing": "Only a simple confirmation: the partner lacks the name or the town of the qualified query.",
	"Not Qualified": "Only a simple confirmation, although name and town are known now.",
	"Details Differ": "The member state has another name or address registered.",
	"German VAT ID, Not Checked": "Not checked yet. VIES checks a German USt-IdNr. for its validity alone, without name or address; it is not the confirmation of § 18e UStG.",
	"Not Assigned": "Deals with no company yet, so no company asks about the number by itself. Press „Confirm VAT ID“ on the partner, or „Confirm VAT ID of the Customer“ on its first invoice.",
}


def execute(filters: dict | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
	filters = frappe._dict(filters or {})
	company = filters.get(COMPANY)
	if not company:
		frappe.throw(_("Choose the company."))
	frappe.has_permission("Company", "read", doc=company, throw=True)
	policy = partner_vat_ids.company_policy(company)
	if policy is None:
		return get_columns(), [], _(NO_REQUESTER).format(company)
	chosen = filters.get(PARTY_TYPE)
	types = (chosen,) if chosen in partner_vat_ids.PARTY_TYPES else partner_vat_ids.PARTY_TYPES
	message = None if policy.on_change or policy.renewal else _(AUTOMATIC_OFF).format(company)
	return get_columns(), [_row(row) for row in partner_vat_ids.worklist(company, types)], message


def get_columns() -> list[dict[str, Any]]:
	return [
		{
			"fieldname": "party_type",
			"label": _("Party Type"),
			"fieldtype": "Link",
			"options": "DocType",
			"width": 110,
		},
		{
			"fieldname": "party",
			"label": _("Party"),
			"fieldtype": "Dynamic Link",
			"options": "party_type",
			"width": 220,
		},
		{"fieldname": "tax_id", "label": _("VAT ID"), "fieldtype": "Data", "width": 150},
		{"fieldname": "standing", "label": _("Confirmation Standing"), "fieldtype": "Data", "width": 170},
		{"fieldname": "asked_on", "label": _("Latest Answer"), "fieldtype": "Date", "width": 110},
		{"fieldname": "age", "label": _("Age (Days)"), "fieldtype": "Int", "width": 90},
		{"fieldname": "result", "label": _("Result"), "fieldtype": "Data", "width": 90},
		{
			"fieldname": "confirmation",
			"label": _("VAT ID Confirmation"),
			"fieldtype": "Link",
			"options": "VAT ID Confirmation",
			"width": 160,
		},
		{"fieldname": "note", "label": _("Note"), "fieldtype": "Data", "width": 360},
	]


def _row(row: dict) -> dict[str, Any]:
	standing = row["standing"].value
	answer = row["answer"]
	return {
		"party_type": row["party_type"],
		"party": row["party"],
		"tax_id": row["tax_id"],
		"standing": _(standing),
		"asked_on": answer.asked_on if answer else None,
		"age": row["age"],
		"result": _(answer.outcome.value) if answer else "",
		"confirmation": row["record"],
		"note": row["problem"] or _(STANDING_NOTES[standing]),
	}
