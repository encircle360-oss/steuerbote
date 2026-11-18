from frappe.model.document import Document


class VATReturnDeviation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		booked_tax: DF.Currency
		check_label: DF.Data | None
		computed_tax: DF.Currency
		difference: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		voucher_no: DF.DynamicLink | None
		voucher_type: DF.Link | None
	# end: auto-generated types

	pass
