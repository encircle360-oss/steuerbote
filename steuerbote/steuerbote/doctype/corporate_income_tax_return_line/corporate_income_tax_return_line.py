from frappe.model.document import Document


class CorporateIncomeTaxReturnLine(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		correction: DF.Currency
		correction_reason: DF.SmallText | None
		feldkennung: DF.Data
		form: DF.Literal["KSt1", "GK", "ZVE", "WA", "Verluste", "Z", "KSt1F"]
		form_amount: DF.Currency
		label: DF.SmallText | None
		ledger_amount: DF.Currency
		line: DF.Data | None
		manual: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		reported: DF.Currency
	# end: auto-generated types

	pass
