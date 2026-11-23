from frappe.model.document import Document


class ElectronicBalanceSheetTransfer(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		current: DF.Currency
		derived: DF.Check
		kind: DF.Literal["Wertänderung", "Umgliederung", "Umgliederung und Wertänderung"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		position: DF.Data
		position_label: DF.SmallText | None
		previous: DF.Currency
		reason: DF.SmallText | None
	# end: auto-generated types

	pass
