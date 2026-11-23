from frappe.model.document import Document


class AnnualAccountsSignatory(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		function: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		place: DF.Data | None
		signatory_name: DF.Data
		signed_on: DF.Date | None
	# end: auto-generated types

	pass
