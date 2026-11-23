from frappe.model.document import Document


class AnnualVATReturnLine(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		correction: DF.Currency
		correction_reason: DF.SmallText | None
		feldkennung: DF.Data
		form_amount: DF.Currency
		formatkennzeichen: DF.Data | None
		kennzahl: DF.Data | None
		label: DF.SmallText | None
		ledger_amount: DF.Currency
		line: DF.Int
		manual: DF.Check
		paragraph: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		reported: DF.Currency
		ustva: DF.Data | None
	# end: auto-generated types

	pass
