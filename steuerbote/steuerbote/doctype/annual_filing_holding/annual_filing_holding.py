from frappe.model.document import Document


class AnnualFilingHolding(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		bought_on: DF.Date | None
		country: DF.Link | None
		holding_name: DF.Data
		identifier: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		percent_at_start_of_ez: DF.Percent
		percent_on_1_january: DF.Percent
		sold_on: DF.Date | None
		year: DF.Int
	# end: auto-generated types

	pass
