from frappe.model.document import Document


class AnnualFilingFinding(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		blocking: DF.Check
		code: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		reference: DF.Data | None
		severity: DF.Literal["Fehler", "Hinweis"]
		text: DF.SmallText | None
	# end: auto-generated types

	pass
