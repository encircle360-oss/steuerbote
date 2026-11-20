from frappe.model.document import Document


class ZMRule(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		reason: DF.SmallText | None
		rhythm: DF.Literal["monthly", "quarterly", "yearly"]
		services_monthly: DF.Check
		valid_from_month: DF.Int
		year: DF.Int
	# end: auto-generated types

	pass
