"""ELSTER-Übermittlung: the record of one Prüfen, Testsenden or Senden of a VAT Return, or of its filing
outside Steuerbote.

Only the server writes it. VATReturn.transmit creates it while the run waits for its background job, the job
completes it with the outcome of steuerbote.eric, and afterwards it stays as it is. A record of a filing, a
successful real Senden or a filing outside Steuerbote, cannot be deleted, since the Finanzamt has that
return. A real Senden with an unknown outcome may have reached ELSTER: it blocks sending the return again
until someone has checked in Mein ELSTER and a System Manager has deleted it.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

VALIDATE = "validate"
TEST_SEND = "test_send"
SEND = "send"
EXTERN = "extern"

SUCCEEDED = "Erfolgreich"
FAILED = "Fehlgeschlagen"
UNKNOWN = "Unbekannt"
RUNNING = "Läuft"


class ELSTERTransmission(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from steuerbote.steuerbote.doctype.elster_transmission_message.elster_transmission_message import (
			ELSTERTransmissionMessage,
		)

		company: DF.Link | None
		eric_version: DF.Data | None
		finished_at: DF.Datetime | None
		messages: DF.Table[ELSTERTransmissionMessage]
		operation: DF.Literal["validate", "test_send", "send", "extern"]
		outcome: DF.Literal["", "valid", "invalid", "accepted", "rejected", "failed", "unknown"]
		protocol_pdf: DF.Attach | None
		remarks: DF.SmallText | None
		response_xml: DF.Attach | None
		simulated: DF.Check
		started_at: DF.Datetime | None
		status: DF.Literal["Erfolgreich", "Fehlgeschlagen", "Unbekannt", "Läuft"]
		testmerker: DF.Data | None
		transferticket: DF.Data | None
		user: DF.Link | None
		vat_return: DF.Link
		xml: DF.Attach | None
	# end: auto-generated types

	def validate(self) -> None:
		if not self.is_new() and not self.flags.recording:
			frappe.throw(_("An ELSTER Transmission cannot be changed after it was recorded."))

	def on_trash(self) -> None:
		if self.records_a_filing():
			frappe.throw(
				_("{0} records a return the Finanzamt has, so it cannot be deleted.").format(self.name)
			)

	def records_a_filing(self) -> bool:
		if self.status != SUCCEEDED:
			return False
		return self.operation == EXTERN or (self.operation == SEND and not cint(self.simulated))
