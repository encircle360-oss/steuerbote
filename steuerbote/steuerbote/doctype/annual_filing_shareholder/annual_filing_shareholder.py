from frappe.model.document import Document


class AnnualFilingShareholder(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		foreign_id: DF.Data | None
		from_date: DF.Date
		idnr: DF.Data | None
		kind: DF.Literal["Natural Person", "Corporation", "Business Partnership"]
		nominal_amount: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		percent: DF.Percent
		postal_code_and_town: DF.Data
		shareholder_name: DF.Data
		street: DF.Data
		tax_number: DF.Data | None
		tax_number_state: DF.Literal[
			"",
			"Baden-Württemberg",
			"Bayern",
			"Berlin",
			"Brandenburg",
			"Bremen",
			"Hamburg",
			"Hessen",
			"Mecklenburg-Vorpommern",
			"Niedersachsen",
			"Nordrhein-Westfalen",
			"Rheinland-Pfalz",
			"Saarland",
			"Sachsen",
			"Sachsen-Anhalt",
			"Schleswig-Holstein",
			"Thüringen",
		]
		to_date: DF.Date | None
		wid_nr: DF.Data | None
	# end: auto-generated types

	pass
