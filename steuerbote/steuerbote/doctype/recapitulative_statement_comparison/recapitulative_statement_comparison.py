from frappe.model.document import Document


class RecapitulativeStatementComparison(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		art: DF.Literal["L", "D", "S"]
		current: DF.Currency
		difference: DF.Currency
		difference_percent: DF.Percent
		flagged: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		previous: DF.Currency
		vat_id: DF.Data | None
	# end: auto-generated types

	pass
