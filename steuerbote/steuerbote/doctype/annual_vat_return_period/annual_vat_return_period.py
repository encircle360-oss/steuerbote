from frappe.model.document import Document


class AnnualVATReturnPeriod(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		cause: DF.Literal[
			"",
			"No Difference",
			"Late Postings",
			"Corrections without Posting",
			"Late Postings and Corrections",
			"Not Filed",
		]
		corrections: DF.Currency
		difference: DF.Currency
		due: DF.Check
		kz39: DF.Currency
		kz83: DF.Currency
		kz83_now: DF.Currency
		late: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		period_code: DF.Data | None
		period_label: DF.Data | None
		vat_return: DF.Link | None
		waiver_reason: DF.SmallText | None
	# end: auto-generated types

	pass
