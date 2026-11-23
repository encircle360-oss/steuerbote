from frappe.model.document import Document


class AnnualAccountsPriorEntry(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		concept: DF.Data
		label: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		remaining_term: DF.Literal[
			"", "bis zu einem Jahr", "mehr als ein Jahr bis zu fünf Jahren", "mehr als fünf Jahre"
		]
		shareholder: DF.Check
	# end: auto-generated types

	pass
