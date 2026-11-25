from frappe.model.document import Document


class AnnualFilingYear(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		adopted_on: DF.Date | None
		advisor_prepares: DF.Check
		early_request_gewst: DF.Date | None
		early_request_kst: DF.Date | None
		early_request_ust: DF.Date | None
		exempt_264_3: DF.Check
		exempt_264_3_reason: DF.SmallText | None
		kleinunternehmer: DF.Check
		no_vat_return: DF.Check
		no_vat_return_note: DF.SmallText | None
		no_vat_return_reason: DF.Literal[
			"", "Not an Unternehmer (§ 2 UStG)", "Released by the Finanzamt", "Other Reason"
		]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		year: DF.Int
	# end: auto-generated types

	pass
