from frappe.model.document import Document

from steuerbote.steuerbote.recorded_vouchers import RecordedVoucherRow


class RecapitulativeStatementHint(RecordedVoucherRow, Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		code: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		party: DF.Data | None
		severity: DF.Literal["Fehler", "Hinweis"]
		text: DF.SmallText | None
		voucher_no: DF.DynamicLink | None
		voucher_type: DF.Link | None
	# end: auto-generated types

	pass
