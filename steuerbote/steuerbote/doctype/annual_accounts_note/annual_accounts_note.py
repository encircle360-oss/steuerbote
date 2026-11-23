from frappe.model.document import Document


class AnnualAccountsNote(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		answer: DF.Literal["", "ja", "nein", "entfällt"]
		code: DF.Data
		label: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		published: DF.Check
		reference: DF.Data | None
		requirement: DF.Data | None
		text: DF.Text | None
	# end: auto-generated types

	pass
