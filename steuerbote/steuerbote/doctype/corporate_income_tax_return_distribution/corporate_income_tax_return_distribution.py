from frappe.model.document import Document


class CorporateIncomeTaxReturnDistribution(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		certified_reduction: DF.Currency
		kind: DF.Literal["Ordinary Distribution", "Hidden Distribution", "Liquidation Advance"]
		outflow_date: DF.Date
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		resolution_date: DF.Date | None
	# end: auto-generated types

	pass
