from frappe.model.document import Document


class TradeTaxReturnMunicipality(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		ags: DF.Data | None
		balance: DF.Currency
		gewst: DF.Currency
		hebenummer: DF.Data | None
		hebesatz: DF.Percent
		hebesatz_source: DF.SmallText | None
		messbetrag: DF.Currency
		municipality: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		postal_code: DF.Data | None
		prepayments: DF.Currency
	# end: auto-generated types

	pass
