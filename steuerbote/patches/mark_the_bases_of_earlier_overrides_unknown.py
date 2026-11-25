"""Overrides and corrections from before Steuerbote kept their basis have an unknown basis.

The patch set_the_basis_of_overrides gave each of them the amount its row held on the day of the update. That is the
amount of the last calculation, which may already include a late booking the override then hides, and the patch kept
no record of which bases it wrote. Every override and correction of a document created before that patch ran is
therefore marked basis_unknown, except a line by hand, which has no computed amount to hide. Its document holds it
until a change of its amount or reason confirms it against the amount its row shows (steuerbote.jahresmeldung.overrides,
steuerbote.zm.lines, the bridge of the Voranmeldung). An override entered under 0.15.0 on such a document is marked as
well and is confirmed once more.

The patch runs after the DocTypes are migrated, when the columns exist, and only sets marks, so it can run again.
"""

import frappe

from steuerbote.patches.set_the_basis_of_overrides import BASES

EARLIER_PATCH = "steuerbote.patches.set_the_basis_of_overrides"

# Each table of BASES with the DocType of the document that holds it.
PARENTS = {
	"Recapitulative Statement Line": "Recapitulative Statement",
	"VAT Return Kennzahl": "VAT Return",
	"Annual Accounts Line": "Annual Accounts",
	"Annual VAT Return Line": "Annual VAT Return",
	"Corporate Income Tax Return Line": "Corporate Income Tax Return",
	"Trade Tax Return Line": "Trade Tax Return",
	"Electronic Balance Sheet Position": "Electronic Balance Sheet",
}


def execute() -> None:
	since = frappe.db.get_value("Patch Log", {"patch": EARLIER_PATCH}, "creation", order_by="creation asc")
	if since is None:
		return
	for doctype, reason, basis, _amount in BASES:
		row = frappe.qb.DocType(doctype)
		document = frappe.qb.DocType(PARENTS[doctype])
		earlier = frappe.qb.from_(document).select(document.name).where(document.creation < since)
		query = (
			frappe.qb.update(row)
			.set(row[f"{basis}_unknown"], 1)
			.where(row.parenttype == PARENTS[doctype])
			.where(row[reason].isnotnull() & (row[reason] != ""))
			.where(row.parent.isin(earlier))
		)
		if frappe.db.has_column(doctype, "manual"):
			query = query.where(row.manual == 0)
		query.run()
