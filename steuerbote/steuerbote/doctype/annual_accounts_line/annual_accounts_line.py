from frappe.model.document import Document


class AnnualAccountsLine(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		concept: DF.Data
		correction: DF.Currency
		correction_reason: DF.SmallText | None
		label: DF.SmallText | None
		level: DF.Literal[
			"Summe", "Buchstabe", "römische Zahl", "arabische Zahl", "Kleinbuchstabe", "Vermerk"
		]
		manual: DF.Check
		marker: DF.Data | None
		parent: DF.Data
		parent_concept: DF.Data | None
		parentfield: DF.Data
		parenttype: DF.Data
		prior: DF.Currency
		reported: DF.Currency
		shown: DF.Check
		sources: DF.SmallText | None
		statement: DF.Literal["Aktiva", "Passiva", "GuV"]
		takes_correction: DF.Check
	# end: auto-generated types

	pass
