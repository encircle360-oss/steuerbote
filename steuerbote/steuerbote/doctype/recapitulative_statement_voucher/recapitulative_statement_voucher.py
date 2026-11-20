from frappe.model.document import Document


class CancelledVoucherRow:
	"""A row that names a voucher of the ledger, which may be cancelled: with „Unveränderliches Hauptbuch
	aktivieren“ ERPNext books its reversal in the month of the cancellation, and the ZM of that month reports it
	(Anleitung zur ZM, IV.10). Frappe refuses a link to a cancelled document in a submittable one, so such a row
	checks only that the documents it names exist."""

	def get_invalid_links(self, is_submittable: bool = False) -> tuple[list, list]:
		invalid_links, _cancelled_links = super().get_invalid_links(is_submittable)
		return invalid_links, []


class RecapitulativeStatementVoucher(CancelledVoucherRow, Document):
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
