from frappe.model.document import Document


class VATReturnRegisterReconciliation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		account: DF.Link | None
		compared: DF.Check
		difference: DF.Currency
		explanation: DF.SmallText | None
		kennzahl: DF.Data | None
		ledger_amount: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		register: DF.Literal["Sales Register", "Purchase Register"]
		register_amount: DF.Currency
		subject: DF.SmallText | None
	# end: auto-generated types

	pass
