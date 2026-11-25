"""Overrides of the Zusammenfassende Meldung and the Voranmeldung and corrections of the annual documents keep the amount
they were made against (override_basis, correction_basis), so that a later change of the ledger holds their document
instead of hiding behind them. One made before the field existed takes the amount its row holds, the one the ledger or
Berechnen gave at its last calculation, against which it was last confirmed.

The patch runs after the DocTypes are migrated, when the columns exist, and fills only rows with a reason and an empty
basis, so it can run again and leaves a basis set since as it is.
"""

import frappe

# Each table, the column of its basis and that of the amount the basis is taken from.
BASES = (
	("Recapitulative Statement Line", "override_reason", "override_basis", "amount"),
	("VAT Return Kennzahl", "override_reason", "override_basis", "amount"),
	("Annual Accounts Line", "correction_reason", "correction_basis", "amount"),
	("Annual VAT Return Line", "correction_reason", "correction_basis", "form_amount"),
	("Corporate Income Tax Return Line", "correction_reason", "correction_basis", "form_amount"),
	("Trade Tax Return Line", "correction_reason", "correction_basis", "form_amount"),
	("Electronic Balance Sheet Position", "correction_reason", "correction_basis", "computed"),
)


def execute() -> None:
	for doctype, reason, basis, amount in BASES:
		table = frappe.qb.DocType(doctype)
		(
			frappe.qb.update(table)
			.set(table[basis], table[amount])
			.where(table[reason].isnotnull() & (table[reason] != ""))
			.where(table[basis].isnull() | (table[basis] == 0))
		).run()
