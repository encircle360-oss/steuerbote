"""The VAT Return Settings decide how the tax of the bases at a statutory rate (Kz 81, 86, 89 and 93) enters the sums
and Kz 83 (statutory_tax). Settings saved before this field existed get the default: the tax of the form, from the base
in full euros, as Steuerbote computed it until then (steuerbote.ustva.calculation.StatutoryTax).

The patch runs after the DocTypes are migrated, when the column exists, and fills only empty values, so it can run
again and leaves a choice made in the settings as it is.
"""

import frappe

from steuerbote.ustva.calculation import DEFAULT_STATUTORY_TAX

SETTINGS = "VAT Return Settings"


def execute() -> None:
	table = frappe.qb.DocType(SETTINGS)
	(
		frappe.qb.update(table)
		.set(table.statutory_tax, DEFAULT_STATUTORY_TAX.value)
		.where(table.statutory_tax.isnull() | (table.statutory_tax == ""))
	).run()
