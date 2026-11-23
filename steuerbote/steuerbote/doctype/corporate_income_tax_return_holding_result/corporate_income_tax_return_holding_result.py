from frappe.model.document import Document


class CorporateIncomeTaxReturnHoldingResult(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		book_value: DF.Currency
		exemption: DF.Data | None
		financing_costs: DF.Currency
		holding_name: DF.Data
		kind: DF.Literal["Dividends", "Sale", "Write-up", "Write-down"]
		other_costs: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		percent_at_start_of_ez: DF.Percent
		percent_on_1_january: DF.Percent
		result_date: DF.Date | None
		sale_costs: DF.Currency
		sale_price: DF.Currency
	# end: auto-generated types

	pass
