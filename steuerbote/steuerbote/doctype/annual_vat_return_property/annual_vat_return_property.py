from frappe.model.document import Document


class AnnualVATReturnProperty(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		extent_of_use: DF.Float
		first_use: DF.Date | None
		input_tax_deducted: DF.Currency
		input_tax_total: DF.Currency
		kind_of_use: DF.SmallText | None
		location: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
	# end: auto-generated types

	pass
