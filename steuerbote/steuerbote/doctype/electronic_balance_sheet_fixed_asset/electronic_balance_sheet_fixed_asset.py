from frappe.model.document import Document


class ElectronicBalanceSheetFixedAsset(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		additions: DF.Currency
		asset_category: DF.Link | None
		book_value_end: DF.Currency
		cost_begin: DF.Currency
		cost_end: DF.Currency
		depreciation_6b: DF.Currency
		depreciation_7g: DF.Currency
		depreciation_additions: DF.Currency
		depreciation_begin: DF.Currency
		depreciation_disposals: DF.Currency
		depreciation_end: DF.Currency
		depreciation_extraordinary: DF.Currency
		depreciation_other: DF.Currency
		depreciation_regular: DF.Currency
		depreciation_special: DF.Currency
		depreciation_transfers: DF.Currency
		disposals: DF.Currency
		erp_adjustment: DF.Currency
		manual: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		position: DF.Data | None
		position_label: DF.SmallText | None
		reason: DF.SmallText | None
		transfers: DF.Currency
		value_type: DF.Literal["StB", "HB", "Überleitung"]
		writeups: DF.Currency
	# end: auto-generated types

	pass
