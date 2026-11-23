from frappe.model.document import Document


class AnnualFilingCarryForward(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		as_of: DF.Date
		confirmed: DF.Check
		kind: DF.Literal[
			"Loss Carried Forward (§ 10d EStG)",
			"Loss from Termingeschäfte (§ 15 Abs. 4 EStG)",
			"Donations Carried Forward (KSt)",
			"Fehlbetrag (§ 10a GewStG)",
			"Donations Carried Forward (GewSt)",
			"Einlagekonto (§ 27 KStG)",
			"Sonderausweis (§ 28 KStG)",
		]
		notice_date: DF.Date | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
	# end: auto-generated types

	pass
