from frappe.model.document import Document


class ElectronicBalanceSheetAccount(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		account: DF.Link | None
		account_label: DF.Data | None
		account_number: DF.Data | None
		amount: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		position: DF.Data | None
		position_label: DF.SmallText | None
	# end: auto-generated types

	pass
