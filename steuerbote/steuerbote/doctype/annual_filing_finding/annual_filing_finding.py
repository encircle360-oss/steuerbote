from frappe.model.document import Document


class AnnualFilingFinding(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		acknowledgeable: DF.Check
		acknowledged: DF.Check
		acknowledged_by: DF.Link | None
		acknowledged_on: DF.Datetime | None
		acknowledgement_reason: DF.SmallText | None
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
