from frappe.model.document import Document


class VATReturnExtensionBase(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		kz39: DF.Currency
		kz83: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		period_code: DF.Data | None
		period_label: DF.Data | None
		vat_return: DF.Link | None
	# end: auto-generated types

	pass
