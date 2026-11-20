from frappe.model.document import Document


class RecapitulativeStatementLine(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		art: DF.Literal["L", "D", "S"]
		blocked: DF.Check
		confirmation: DF.Link | None
		confirmation_date: DF.Date | None
		confirmation_outcome: DF.Literal["", "valid", "invalid", "unknown"]
		confirmation_service: DF.Literal["", "bzst", "vies"]
		confirmation_status: DF.Data | None
		consultation_id: DF.Data | None
		filed_amount: DF.Currency
		in_file: DF.Check
		manual: DF.Check
		override: DF.Currency
		override_reason: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		party: DF.Data | None
		reported: DF.Currency
		vat_id: DF.Data | None
	# end: auto-generated types

	pass
