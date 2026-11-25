"""USt-IdNr.-Bestätigung: the record of one query to confirm a USt-IdNr. at the BZSt or at VIES.

Only the server writes it, with what was asked and what came back, and the answer as it came as a private file:
the record the BZSt returns is the proof of the query (UStAE 18e.1 Abs. 2 Satz 5), and „Das BZSt versendet keine
schriftliche Bestätigungsmitteilung.“ (BZSt, "Fragen und Antworten" zur USt-IdNr.). So nobody changes or deletes
a record or its answer once it is stored; steuerbote.steuerbote.record_files keeps the File of the answer as it
was stored. A confirmation of steuerbote.vatid can take two queries, and store() keeps each, the
later one pointing to the earlier, with the Zusammenfassende Meldung or the Umsatzsteuer-Voranmeldung it came from;
latest() gives the newest record of each number of a company, which the lines of a Zusammenfassende Meldung show
and the hints of a Voranmeldung read.
"""

from collections.abc import Iterable
from datetime import datetime
from types import MappingProxyType

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import convert_utc_to_system_timezone

from steuerbote.steuerbote import guards
from steuerbote.steuerbote.doctype.vat_id_confirmation import records
from steuerbote.vatid.result import Confirmation

DOCTYPE = "VAT ID Confirmation"
LATEST_FIELDS = (
	"name",
	"requested",
	"requested_at",
	"service",
	"result",
	"status_code",
	"consultation_id",
	"valid_from",
	"valid_until",
)
# The field of a record that names the document whose USt-IdNrn. its confirmation asked about.
SOURCE_FIELDS: MappingProxyType[str, str] = MappingProxyType(
	{"Recapitulative Statement": "recapitulative_statement", "VAT Return": "vat_return"}
)


class VATIDConfirmation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		answered_at: DF.Datetime | None
		city_match: DF.Literal["", "A", "B", "C", "D"]
		company: DF.Link | None
		consultation_id: DF.SmallText | None
		details_city: DF.SmallText | None
		details_name: DF.SmallText | None
		details_postcode: DF.SmallText | None
		details_street: DF.SmallText | None
		fallback_reason: DF.SmallText | None
		http_status: DF.Int
		message: DF.SmallText | None
		name_match: DF.Literal["", "A", "B", "C", "D"]
		outcome: DF.Literal["valid", "invalid", "unknown"]
		postcode_match: DF.Literal["", "A", "B", "C", "D"]
		previous: DF.Link | None
		qualified: DF.Check
		recapitulative_statement: DF.Link | None
		requested: DF.Data
		requested_at: DF.Datetime | None
		requester: DF.Data
		response_file: DF.Attach | None
		result: DF.Literal["valid", "invalid", "unknown"]
		service: DF.Literal["bzst", "vies"]
		service_date: DF.Date | None
		service_time: DF.Datetime | None
		status_code: DF.SmallText | None
		street_match: DF.Literal["", "A", "B", "C", "D"]
		unavailable: DF.Check
		user: DF.Link | None
		valid_from: DF.Date | None
		valid_until: DF.Date | None
		vat_return: DF.Link | None
	# end: auto-generated types

	def validate(self) -> None:
		if not self.is_new():
			frappe.throw(
				_("A VAT ID Confirmation keeps the answer of a query as it came and cannot be changed.")
			)

	def on_trash(self) -> None:
		frappe.throw(
			_("{0} is the proof of a query to confirm a USt-IdNr. and cannot be deleted.").format(self.name)
		)


def store(confirmation: Confirmation, company: str, source: tuple[str, str] | None = None) -> str:
	"""Record each query of the confirmation, the first first, with its answer as a private file; ``source`` is the
	DocType and the name of the document whose USt-IdNrn. the confirmation asked about. Returns the name of the
	record of the last query."""
	origin = {SOURCE_FIELDS[source[0]]: source[1]} if source else {}
	previous = None
	for query, values in zip(confirmation.queries(), records.records(confirmation), strict=True):
		record = guards.insert_record(
			frappe.get_doc(
				{
					"doctype": DOCTYPE,
					**values,
					**{name: _site_time(values[name]) for name in records.TIME_FIELDS},
					"company": company,
					**origin,
					"user": frappe.session.user,
					"previous": previous,
				}
			)
		)
		if query.response_text:
			file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": records.response_file_name(record.name, query),
					"attached_to_doctype": DOCTYPE,
					"attached_to_name": record.name,
					"attached_to_field": "response_file",
					"is_private": 1,
					"content": query.response_text.encode("utf-8"),
				}
			).insert(ignore_permissions=True)
			frappe.db.set_value(DOCTYPE, record.name, "response_file", file.file_url, update_modified=False)
		previous = record.name
	return previous


def latest(company: str, vat_ids: Iterable[str]) -> dict[str, frappe._dict]:
	"""The newest record of each USt-IdNr. that the company asked about, by the number: queries run one after
	the other and each is stored when it is answered."""
	numbers = sorted({vat_id for vat_id in vat_ids if vat_id})
	if not numbers:
		return {}
	found: dict[str, frappe._dict] = {}
	for record in frappe.get_all(
		DOCTYPE,
		filters={"company": company, "requested": ["in", numbers]},
		fields=list(LATEST_FIELDS),
		order_by="creation desc",
	):
		found.setdefault(record.requested, record)
	return found


def _site_time(moment: datetime | None) -> datetime | None:
	"""A moment with its zone as the Datetime fields of the site keep it: in the time zone of the system."""
	return None if moment is None else convert_utc_to_system_timezone(moment).replace(tzinfo=None)
