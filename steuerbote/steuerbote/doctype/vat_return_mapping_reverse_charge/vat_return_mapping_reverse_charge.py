from frappe.model.document import Document


class VATReturnMappingReverseCharge(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		classification: DF.Literal["EU Service", "Other Reverse Charge"]
		note: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		reference_doctype: DF.Literal[
			"Supplier", "Purchase Invoice", "Journal Entry", "Purchase Taxes and Charges Template"
		]
		reference_name: DF.DynamicLink
	# end: auto-generated types

	pass
