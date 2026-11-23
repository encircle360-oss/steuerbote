from frappe.model.document import Document


class CorporateIncomeTaxReturnCredit(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		capital_gains_tax: DF.Currency
		certificate_date: DF.Date | None
		issuer: DF.Data
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		solz: DF.Currency
	# end: auto-generated types

	pass
