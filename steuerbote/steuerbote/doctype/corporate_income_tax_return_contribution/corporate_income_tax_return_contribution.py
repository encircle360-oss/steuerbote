from frappe.model.document import Document


class CorporateIncomeTaxReturnContribution(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		contribution_date: DF.Date
		description: DF.Data | None
		kind: DF.Literal["Cash Contribution", "Contribution in Kind"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		shareholder: DF.Data
		treatment: DF.Literal[
			"Booked to Profit and Paid",
			"Booked to Profit, Not Paid",
			"Not Booked to Profit",
			"Other Contribution",
		]
	# end: auto-generated types

	pass
