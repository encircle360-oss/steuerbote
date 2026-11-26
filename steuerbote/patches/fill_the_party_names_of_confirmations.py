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
	records = frappe.get_all(
		DOCTYPE,
		filters={"party_type": ["in", list(PARTY_NAME_FIELDS)], "party": ["is", "set"]},
		fields=["name", "party_type", "party"],
	)
	for party_type, field in PARTY_NAME_FIELDS.items():
		parties = sorted({row.party for row in records if row.party_type == party_type})
		names = dict(
			frappe.get_all(
				party_type, filters={"name": ["in", parties or [""]]}, fields=["name", field], as_list=True
			)
		)
		for row in records:
			if row.party_type == party_type and row.party in names:
				frappe.db.set_value(DOCTYPE, row.name, "party_name", names[row.party], update_modified=False)
