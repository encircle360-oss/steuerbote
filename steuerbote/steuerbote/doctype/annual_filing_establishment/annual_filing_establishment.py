from frappe.model.document import Document


class AnnualFilingEstablishment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		ags: DF.Data
		from_date: DF.Date
		hebenummer: DF.Data | None
		municipality: DF.Data
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		postal_code: DF.Data
		to_date: DF.Date | None
	# end: auto-generated types

	pass
