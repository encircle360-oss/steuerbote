from frappe.model.document import Document


class AnnualVATReturnReconciliation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		annual: DF.Currency
		annual_only: DF.Currency
		corrections: DF.Currency
		filed: DF.Currency
		filed_ledger: DF.Currency
		kennzahl: DF.Data | None
		label: DF.SmallText | None
		late: DF.Currency
		ledger_now: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		rest: DF.Currency
		rounding: DF.Currency
		soll: DF.Currency
		sondervorauszahlung: DF.Currency
		unfiled: DF.Currency
	# end: auto-generated types

	pass
