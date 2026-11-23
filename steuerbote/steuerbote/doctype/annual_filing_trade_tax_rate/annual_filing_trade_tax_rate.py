from frappe.model.document import Document


class AnnualFilingTradeTaxRate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		ags: DF.Data
		hebesatz: DF.Percent
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		source: DF.Data
		source_date: DF.Date | None
		year: DF.Int
	# end: auto-generated types

	pass
