"""Each VAT ID Confirmation keeps the name of its customer or supplier beside its ID.

Records from before the field name their partner by ID alone, which reads as a bare number where ERPNext names
partners by a naming series. The patch gives each record of a customer or supplier the name the partner has now;
afterwards a new name of the partner reaches its records when the partner is saved (partner_vat_ids.on_party_update),
and a new ID through the link, as Frappe renames it.

The patch runs after the DocTypes are migrated and writes the name the partner has, so it can run again.
"""

import frappe

from steuerbote.steuerbote.doctype.vat_id_confirmation.vat_id_confirmation import (
	DOCTYPE,
	PARTY_NAME_FIELDS,
)


def execute() -> None:
	record = frappe.qb.DocType(DOCTYPE)
	for party_type, field in PARTY_NAME_FIELDS.items():
		party = frappe.qb.DocType(party_type)
		name = frappe.qb.from_(party).select(party[field]).where(party.name == record.party)
		frappe.qb.update(record).set(record.party_name, name).where(record.party_type == party_type).run()
