from frappe.model.document import Document


class VATReturnComparison(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		current: DF.Currency
		difference: DF.Currency
		difference_percent: DF.Percent
		flagged: DF.Check
		kennzahl: DF.Data | None
		label: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		previous_period: DF.Currency
		previous_period_known: DF.Check
		previous_year: DF.Currency
		previous_year_known: DF.Check
	# end: auto-generated types

	pass
