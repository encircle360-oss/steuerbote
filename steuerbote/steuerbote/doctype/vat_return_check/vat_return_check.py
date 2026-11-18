from frappe.model.document import Document


class VATReturnCheck(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		booked_tax: DF.Currency
		computed_tax: DF.Currency
		deviations: DF.Int
		difference: DF.Currency
		label: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		passed: DF.Check
	# end: auto-generated types

	pass
