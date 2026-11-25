"""The VAT Return Settings decide how a booking finds its Voranmeldungszeitraum (period_basis) and what happens to a
booking for a period already filed (late_documents). Settings saved before these fields existed get the defaults:
by service date, the legal rule, and a corrected return of the filed period (steuerbote.ustva.assignment).

The patch runs after the DocTypes are migrated, when the columns exist, and fills only empty values, so it can run
again and leaves a choice made in the settings as it is.
"""

import frappe

from steuerbote.ustva.assignment import DEFAULT_BASIS, DEFAULT_TREATMENT

SETTINGS = "VAT Return Settings"


def execute() -> None:
	table = frappe.qb.DocType(SETTINGS)
	for field, default in (("period_basis", DEFAULT_BASIS), ("late_documents", DEFAULT_TREATMENT)):
		(
			frappe.qb.update(table)
			.set(table[field], default.value)
			.where(table[field].isnull() | (table[field] == ""))
		).run()
