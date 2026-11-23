from frappe.model.document import Document


class AnnualFilingPrepayment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		ags: DF.Data | None
		amount: DF.Currency
		due_date: DF.Date
		notice_date: DF.Date | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		tax: DF.Literal["KSt", "SolZ", "GewSt"]
		year: DF.Int
	# end: auto-generated types

	pass
