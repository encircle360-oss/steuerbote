"""Kz 500 keeps the keys of its select field instead of the codes 1 to 4.

The VAT Return and the VAT Return Extension offered the codes of line 55 of USt 1 A and line 12 of USt 1 H, the
Annual VAT Return those of line 23 of USt 2 A, without their text. The fields now offer keys that read as the form
(SUPPLEMENTARY_INFORMATION of the bridges), and a document from before holds a code, which the patch turns into its
key, filed and cancelled documents alike: their Nutzdaten carry the code as before. The ELSTER Transmissions keep the
Nutzdaten they sent, with the code, and stay as they are.

The patch runs after the DocTypes are migrated and changes only codes, so it can run again.
"""

import frappe

from steuerbote.steuerbote.doctype.annual_vat_return import bridge as annual_bridge
from steuerbote.steuerbote.doctype.vat_return import bridge

FIELDS = (
	("VAT Return", "supplementary_code", bridge.SUPPLEMENTARY_INFORMATION),
	("VAT Return Extension", "supplementary_code", bridge.SUPPLEMENTARY_INFORMATION),
	("Annual VAT Return", "kz500", annual_bridge.SUPPLEMENTARY_INFORMATION),
)


def execute() -> None:
	for doctype, fieldname, keys in FIELDS:
		table = frappe.qb.DocType(doctype)
		for key, code in keys.items():
			frappe.qb.update(table).set(table[fieldname], key).where(table[fieldname] == code).run()
