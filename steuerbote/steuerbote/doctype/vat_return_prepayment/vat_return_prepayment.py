from frappe.model.document import Document


class VATReturnPrepayment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		dauerfristverlaengerung: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		sondervorauszahlung: DF.Currency
		year: DF.Int
	# end: auto-generated types

	pass
