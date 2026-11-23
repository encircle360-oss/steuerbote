from frappe.model.document import Document


class VATReturnMappingRule(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		account: DF.Link
		account_number: DF.Data | None
		also_kennzahl: DF.Data | None
		also_side: DF.Literal["", "credit", "debit"]
		annual_field: DF.Data | None
		kennzahl: DF.Data
		paragraph: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		side: DF.Literal["credit", "debit"]
		tax_rate: DF.Float
	# end: auto-generated types

	pass
