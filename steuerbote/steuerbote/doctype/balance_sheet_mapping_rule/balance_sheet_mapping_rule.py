from frappe.model.document import Document


class BalanceSheetMappingRule(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		account: DF.Link
		account_number: DF.Data | None
		concept: DF.Data
		concept_label: DF.Data | None
		opposite_concept: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		purpose: DF.Literal["both", "commercial", "tax"]
		remaining_term: DF.Literal["", "up to one year", "one to five years", "over five years"]
		shareholder: DF.Check
	# end: auto-generated types

	pass
