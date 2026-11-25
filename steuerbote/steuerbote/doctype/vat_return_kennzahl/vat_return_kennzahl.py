from frappe.model.document import Document


class VATReturnKennzahl(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		final: DF.Currency
		kennzahl: DF.Data
		kind: DF.Data | None
		label: DF.SmallText | None
		line: DF.Int
		override: DF.Currency
		override_reason: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		reported: DF.Currency
		tax: DF.Currency
	# end: auto-generated types

	pass
