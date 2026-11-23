from frappe.model.document import Document


class TradeTaxReturnHolding(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		addback: DF.Currency
		cut: DF.Currency
		cut_base: DF.Currency
		cut_financing_costs: DF.Currency
		cut_other_costs: DF.Currency
		dividends: DF.Currency
		exempt: DF.Currency
		financing_costs: DF.Currency
		holding_name: DF.Data | None
		not_exempt: DF.Currency
		other_costs: DF.Currency
		paragraph: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
	# end: auto-generated types

	pass
