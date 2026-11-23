from frappe.model.document import Document


class AnnualFilingDirector(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		director_name: DF.Data
		from_date: DF.Date
		is_shareholder: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		role: DF.Data | None
		signs: DF.Check
		to_date: DF.Date | None
	# end: auto-generated types

	pass
