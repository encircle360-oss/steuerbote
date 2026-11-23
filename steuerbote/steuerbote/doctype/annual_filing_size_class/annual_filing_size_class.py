from frappe.model.document import Document


class AnnualFilingSizeClass(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		balance_sheet_total: DF.Currency
		employees: DF.Float
		fiscal_year_end: DF.Date
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		reason: DF.SmallText | None
		revenue: DF.Currency
		size_class: DF.Literal["Kleinst", "Klein", "Mittelgroß", "Groß"]
		source: DF.Data
	# end: auto-generated types

	pass
