from frappe.model.document import Document

from steuerbote.steuerbote.recorded_vouchers import RecordedVoucherRow


class RecapitulativeStatementVoucher(RecordedVoucherRow, Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		art: DF.Literal["L", "D", "S"]
		customer: DF.Link | None
		destination: DF.Data | None
		kennzahl: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		party: DF.Data | None
		vat_id: DF.Data | None
		voucher_no: DF.DynamicLink | None
		voucher_type: DF.Link | None
	# end: auto-generated types

	pass
