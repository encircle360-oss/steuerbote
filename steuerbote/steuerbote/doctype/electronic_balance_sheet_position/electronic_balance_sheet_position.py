from frappe.model.document import Document


class ElectronicBalanceSheetPosition(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		component: DF.Literal["", "B", "GuV", "BVV"]
		computed: DF.Currency
		concept: DF.Data
		correction: DF.Currency
		correction_reason: DF.SmallText | None
		davon_of: DF.Data | None
		depth: DF.Int
		label: DF.SmallText | None
		ledger_amount: DF.Currency
		manual: DF.Check
		mark: DF.Literal["", "Muss", "Summenmuss", "Auffang", "rechnerisch notwendig", "davon"]
		nil: DF.Check
		parent: DF.Data
		parent_concept: DF.Data | None
		parentfield: DF.Data
		parenttype: DF.Data
		reported: DF.Currency
		tax_amount: DF.Currency
	# end: auto-generated types

	pass
