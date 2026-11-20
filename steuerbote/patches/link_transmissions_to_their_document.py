"""An ELSTER Transmission names the document it transmits by document_type and document, a Dynamic Link, since the
Dauerfristverlängerung goes to ELSTER as well. Records from before name a VAT Return in the field vat_return.

The patch runs after the DocTypes are migrated, when the new columns exist. Frappe keeps the column of a field
that left the DocType, so the value of vat_return is still there to move; bench trim-tables removes the column.
A record that names its document already keeps it, so the patch can run again.
"""

import frappe

TRANSMISSION = "ELSTER Transmission"
OLD_FIELD = "vat_return"
VAT_RETURN = "VAT Return"


def execute() -> None:
	if not frappe.db.has_column(TRANSMISSION, OLD_FIELD):
		return
	table = frappe.qb.DocType(TRANSMISSION)
	old = table[OLD_FIELD]
	(
		frappe.qb.update(table)
		.set(table.document_type, VAT_RETURN)
		.set(table.document, old)
		.where(old.isnotnull() & (old != ""))
		.where(table.document.isnull() | (table.document == ""))
	).run()
