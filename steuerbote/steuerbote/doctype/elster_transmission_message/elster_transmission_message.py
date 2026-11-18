from frappe.model.document import Document


class ELSTERTransmissionMessage(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		code: DF.Data | None
		field: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		severity: DF.Literal["error", "hint"]
		text: DF.SmallText | None
	# end: auto-generated types

	pass
