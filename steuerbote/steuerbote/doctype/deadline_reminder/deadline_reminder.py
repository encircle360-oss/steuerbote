"""Fristerinnerung: the record that the reminder of one deadline went out on one day.

steuerbote.steuerbote.deadlines writes one for each deadline its e-mail names. The name of a record comes from the
company, the deadline and the day, so a second record of the same deadline for the same day cannot be inserted,
and nobody changes a record once it is written.
"""

import hashlib
from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

DOCTYPE = "Deadline Reminder"
NAME_LENGTH = 20


class DeadlineReminder(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		company: DF.Link
		due_date: DF.Date
		kind: DF.Literal["Umsatzsteuer-Voranmeldung", "Zusammenfassende Meldung", "Sondervorauszahlung"]
		period_label: DF.Data
		sent_on: DF.Date
	# end: auto-generated types

	def autoname(self) -> None:
		self.name = reminder_name(self.company, self.kind, self.period_label, self.due_date, self.sent_on)

	def validate(self) -> None:
		if not self.is_new():
			frappe.throw(_("A Deadline Reminder records a reminder that was sent and cannot be changed."))


def reminder_name(
	company: str, kind: str, period_label: str, due_date: date | str, sent_on: date | str
) -> str:
	"""The name of the record of one deadline reminded on one day."""
	key = "\n".join((company, kind, period_label, str(getdate(due_date)), str(getdate(sent_on))))
	return hashlib.sha256(key.encode("utf-8")).hexdigest()[:NAME_LENGTH]
