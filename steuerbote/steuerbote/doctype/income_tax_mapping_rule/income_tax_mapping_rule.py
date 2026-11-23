from frappe.model.document import Document


class IncomeTaxMappingRule(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		account: DF.Link
		account_number: DF.Data | None
		category: DF.Literal[
			"",
			"kst",
			"solz",
			"kapest",
			"gewst",
			"foreign_tax",
			"ancillary",
			"supervisory_board",
			"gifts_nondeductible",
			"entertainment_nondeductible",
			"entertainment_deductible",
			"other_nondeductible",
			"donations",
			"tax_free",
			"investment_grant",
			"dividends",
			"share_gain",
			"share_loss",
			"share_writedown",
			"share_writeup",
			"share_sale_costs",
			"derivatives_gain",
			"derivatives_loss",
			"funds",
			"iab_deduction",
			"iab_addback",
			"interest",
			"annuities",
			"silent_partner",
			"rent_movable",
			"rent_movable_ev",
			"rent_immovable",
			"licences",
			"property_tax_own",
			"trading_unclassified",
		]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		trading_class: DF.Literal["", "shares", "derivatives", "funds", "taxable"]
	# end: auto-generated types

	pass
