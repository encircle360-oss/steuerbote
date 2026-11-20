from frappe.model.document import Document


class RecapitulativeStatementReconciliation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		art: DF.Literal["L", "D", "S"]
		balanced: DF.Check
		deviating_vouchers: DF.Int
		difference: DF.Currency
		filed: DF.Currency
		filed_known: DF.Check
		kennzahl: DF.Data | None
		ledger: DF.Currency
		manual: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		reported: DF.Currency
		statement: DF.Currency
	# end: auto-generated types

	pass
