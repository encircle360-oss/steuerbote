from frappe.model.document import Document


class VATReturnMappingCheck(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		base_accounts: DF.SmallText
		derived_base: DF.Data | None
		label: DF.Data
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		side: DF.Literal["credit", "debit"]
		tax_accounts: DF.SmallText
	# end: auto-generated types

	pass
