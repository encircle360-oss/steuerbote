from frappe.model.document import Document

from steuerbote.steuerbote.recorded_vouchers import RecordedVoucherRow


class VATReturnLateChange(RecordedVoucherRow, Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		booked_at: DF.Datetime | None
		kind: DF.Literal["Booked after Filing", "Cancelled after Filing", "Changed since Filing"]
		message: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		period_label: DF.Data | None
		voucher_no: DF.DynamicLink | None
		voucher_type: DF.Link | None
	# end: auto-generated types

	pass
