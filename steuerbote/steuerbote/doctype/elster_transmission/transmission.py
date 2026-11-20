"""Prüfen, Testsenden and Senden of a filing through ERiC, each run recorded as an ELSTER Transmission.

Two documents go to ELSTER this way, both of the Datenart UStVA: the VAT Return (Umsatzsteuer-Voranmeldung) and
the VAT Return Extension (form USt 1 H, Dauerfristverlängerung). Both inherit Transmittable, so that every run
goes the same way. transmit checks the document and puts the run into a background job, run_transmission, which
writes the Nutzdaten of the document, hands them to steuerbote.eric, through the worker of an installed runtime
or the simulation, and records the result. While it runs, the document is locked and cannot change, so that the
job files exactly what it sent. Only a Senden that ELSTER accepted files the document: the job submits it with
flags.filing_transmission set. A run whose job is gone is closed by the form or by the next run, a check as
failed, a test send or send as unknown, since it may have reached ELSTER. Certificate and password never become
arguments of the job: stash_certificate keeps them encrypted for a few minutes, and the job takes them back once
by their token.

A document that transmits has the fields company, year and transmission_in_progress and provides
nutzdaten(hersteller_id), the Nutzdaten for ERiC; check_transmittable(), which refuses a document that cannot go
yet; and check_can_be_sent(), the guards of Senden, which files the document once.
"""

import base64
import binascii
import contextlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, escape_html, now_datetime, strip_html
from frappe.utils.background_jobs import is_job_enqueued

import steuerbote
from steuerbote.eric import secrets
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import TESTMERKER, Operation, Outcome
from steuerbote.eric.service import PIN
from steuerbote.steuerbote.doctype.elster_transmission import messages
from steuerbote.steuerbote.doctype.elster_transmission.elster_transmission import (
	DOCUMENT_TYPES,
	EXTERN,
	FAILED,
	RUNNING,
	SEND,
	SUCCEEDED,
	TEST_SEND,
	UNKNOWN,
	VALIDATE,
)
from steuerbote.steuerbote.doctype.eric_settings.eric_settings import eric_log_root
from steuerbote.steuerbote.doctype.vat_return import transmission_adapter

TRANSMISSION = "ELSTER Transmission"
ERIC_SETTINGS = "ERiC Settings"
SETTINGS_DOCTYPE = "VAT Return Settings"
OPERATIONS = (VALIDATE, TEST_SEND, SEND)
LOCK_FIELD = "transmission_in_progress"
TRANSMISSION_JOB = "steuerbote.steuerbote.doctype.elster_transmission.transmission.run_transmission"
TRANSMISSION_EVENT = "steuerbote_elster_transmission"
# The worker of steuerbote.eric is ended after two minutes; the job keeps time to record the result.
TRANSMISSION_TIMEOUT = 300
# One case per delivery, so its NutzdatenTicket is 1 (ERiC-Entwicklerhandbuch 44.3.6.0, p. 95).
NUTZDATEN_TICKET = "1"
# Kz 09 and the header of the simulation: five digits as ELSTER wants them, and no Hersteller-ID anyone has.
SIMULATION_HERSTELLER_ID = "00000"
DEFAULT_PRODUKT_NAME = "steuerbote"
# The .pfx file of an ELSTER certificate has a few kilobytes.
MAX_CERTIFICATE_BYTES = 64 * 1024


class Transmittable:
	"""A document that goes to ELSTER through ERiC, mixed into its controller before Document."""

	def elster_state(self) -> dict[str, bool]:
		"""For the banner and the buttons of the form: whether ERiC runs as a simulation, whether the lock of a
		transmission is stale and whether ELSTER accepted the document while its submission failed."""
		simulation = frappe.get_cached_doc(ERIC_SETTINGS).simulation
		draft = self.docstatus == 0 and not self.is_new()
		return {
			"simulation": bool(cint(simulation)),
			"stale": draft and self._has_stale_transmission(),
			"sent": draft and self.was_accepted(),
		}

	@frappe.whitelist(methods=["POST"])
	def transmit(self, operation: str, token: str | None = None) -> str:
		"""Prüfen, Testsenden or Senden: check that the document can go, then run it in a background job.

		Certificate and password reach the job only as ``token`` from stash_certificate(), never as arguments
		of the job. Returns the name of the ELSTER Transmission that records the run.
		"""
		if operation not in OPERATIONS:
			frappe.throw(_("Steuerbote knows no ELSTER procedure {0}.").format(escape_html(str(operation))))
		self.check_permission("submit" if operation == SEND else "write")
		self.lock_for_transmission()
		self.check_transmittable()
		self._close_stale_transmission()
		settings = frappe.get_single(ERIC_SETTINGS)
		simulation = bool(cint(settings.simulation))
		if not simulation:
			require_privacy_notice(settings)
		if operation == SEND:
			if simulation:
				frappe.throw(
					_(
						"Senden needs an installed ERiC runtime and a Hersteller-ID. In the simulation, only Prüfen and Testsenden are possible."
					)
				)
			self.check_can_be_sent()
		if operation != VALIDATE and not simulation and not token:
			frappe.throw(_("Choose the certificate file and enter its password."))
		transmission = self.new_transmission(operation, simulated=simulation)
		self.db_set(LOCK_FIELD, 1)
		frappe.enqueue(
			TRANSMISSION_JOB,
			queue="long",
			timeout=TRANSMISSION_TIMEOUT,
			job_id=transmission_job_id(transmission.name),
			enqueue_after_commit=True,
			name=self.name,
			operation=operation,
			token=token,
			transmission=transmission.name,
		)
		return transmission.name

	@frappe.whitelist(methods=["POST"])
	def release_stale_transmission(self) -> None:
		"""Close the run whose background job is gone, a worker that stopped for instance, and lift its lock,
		so that the document can be used again; the form calls this when it finds such a lock."""
		self.check_permission("write")
		self.lock_for_transmission()
		self._close_stale_transmission()

	def lock_for_transmission(self) -> None:
		"""Hold the row of the document until the request ends and read it fresh: two requests cannot start a
		transmission together, and every check sees what the job will send."""
		frappe.db.get_value(self.doctype, self.name, "name", for_update=True)
		self.reload()

	def refuse_changes_while_transmitting(self) -> None:
		"""The job files exactly what it sent, so the document stays as it is while a transmission runs. The
		flag in the database counts: the form may hold a copy from before the transmission started."""
		if self.is_new() or self.flags.filing_transmission:
			return
		if cint(frappe.db.get_value(self.doctype, self.name, LOCK_FIELD)):
			frappe.throw(
				_("A transmission of {0} is running. Wait for its result before changing it.").format(
					self.name
				)
			)

	def _close_stale_transmission(self) -> None:
		"""Refuse a second run while one is queued or running; close the record of a run whose job is gone
		and lift the lock."""
		if not cint(self.get(LOCK_FIELD)):
			return
		running = self._running_transmissions()
		if any(is_job_enqueued(transmission_job_id(name)) for name in running):
			frappe.throw(_("A transmission of {0} is running. Wait for its result.").format(self.name))
		for name in running:
			close_stale_transmission(frappe.get_doc(TRANSMISSION, name))
		self.db_set(LOCK_FIELD, 0)

	def _has_stale_transmission(self) -> bool:
		if not cint(self.get(LOCK_FIELD)):
			return False
		return not any(is_job_enqueued(transmission_job_id(name)) for name in self._running_transmissions())

	def _running_transmissions(self) -> list[str]:
		return frappe.get_all(
			TRANSMISSION,
			filters={"document_type": self.doctype, "document": self.name, "status": RUNNING},
			pluck="name",
		)

	def filings(self) -> list[dict]:
		"""The records that file this document, see filings()."""
		return filings(self.doctype, [self.name])

	def was_accepted(self) -> bool:
		"""Whether ELSTER accepted a real Senden of the document."""
		return self.accepted_send() is not None

	def accepted_send(self) -> dict | None:
		"""The record of a real Senden of the document that ELSTER accepted, if there is one."""
		return next(
			(row for row in self.filings() if row.operation == SEND and row.status == SUCCEEDED), None
		)

	def latest_run(self) -> dict | None:
		"""For the form: the latest Prüfen, Testsenden or Senden of the document that has finished, with how many
		errors and hints ERiC or the simulation gave and the first of each (messages.summary)."""
		if self.is_new():
			return None
		latest = frappe.get_all(
			TRANSMISSION,
			filters={
				"document_type": self.doctype,
				"document": self.name,
				"operation": ["in", OPERATIONS],
				"status": ["!=", RUNNING],
			},
			order_by="creation desc",
			limit=1,
			pluck="name",
		)
		if not latest:
			return None
		transmission = frappe.get_doc(TRANSMISSION, latest[0])
		return {
			"name": transmission.name,
			"operation": transmission.operation,
			"status": transmission.status,
			"simulated": cint(transmission.simulated),
			**messages.summary(transmission.messages),
		}

	def new_transmission(
		self,
		operation: str,
		*,
		simulated: bool,
		status: str = RUNNING,
		remarks: str | None = None,
		filed_via: str | None = None,
		transferticket: str | None = None,
		filed_on=None,
	) -> Document:
		now = now_datetime()
		return frappe.get_doc(
			{
				"doctype": TRANSMISSION,
				"document_type": self.doctype,
				"document": self.name,
				"company": self.company,
				"operation": operation,
				"status": status,
				"simulated": int(simulated),
				"user": frappe.session.user,
				"started_at": now,
				"finished_at": None if status == RUNNING else now,
				"remarks": remarks,
				"filed_via": filed_via,
				"transferticket": transferticket,
				"filed_on": filed_on,
			}
		).insert(ignore_permissions=True)


def dashboard(doctype: str) -> dict:
	"""The connections of a document of ``doctype`` to its ELSTER Transmissions, which name it by
	document_type and document."""
	return {
		"fieldname": "document",
		"dynamic_links": {"document": [doctype, "document_type"]},
		"transactions": [{"label": _("ELSTER"), "items": [TRANSMISSION]}],
	}


def filings(doctype: str, names: list[str]) -> list[dict]:
	"""The records of the given documents that file them, or may have: a real Senden that ELSTER accepted or
	whose outcome is unknown, and a filing outside Steuerbote; the latest first. A cancelled document counts
	as well, since cancelling it in ERPNext takes nothing back from the Finanzamt."""
	if not names:
		return []
	return frappe.get_all(
		TRANSMISSION,
		filters={
			"document_type": doctype,
			"document": ["in", names],
			"operation": ["in", (SEND, EXTERN)],
			"status": ["in", (SUCCEEDED, UNKNOWN)],
			"simulated": 0,
		},
		fields=["name", "document", "operation", "status", "transferticket", "finished_at"],
		order_by="creation desc",
	)


def transmission_job_id(transmission: str) -> str:
	return f"steuerbote:elster:{transmission}"


def close_stale_transmission(transmission: Document) -> None:
	"""Close a run whose job is gone. A check never left the server, a test send or a send may have
	reached ELSTER, so its outcome is unknown."""
	transferred = transmission.operation in (TEST_SEND, SEND) and not cint(transmission.simulated)
	outcome = Outcome.UNKNOWN if transferred else Outcome.FAILED
	transmission.update(
		{
			"status": UNKNOWN if transferred else FAILED,
			"outcome": outcome.value,
			"finished_at": now_datetime(),
		}
	)
	note = (
		_(
			"The transmission did not finish and its result is unknown. Before sending again, check in Mein ELSTER whether {0} arrived."
		).format(transmission.document)
		if transferred
		else _(
			"The run did not finish because its background job is gone. Nothing reached ELSTER; start it again."
		)
	)
	transmission.append("messages", {"severity": "error", "text": note})
	record(transmission)


def require_privacy_notice(settings: Document) -> None:
	"""ERiC licence, § 5 Abs. 1 and 2: the end user acknowledges the Datenschutzhinweise of the tax
	administration before using the software."""
	if not cint(settings.privacy_notice_confirmed):
		frappe.throw(
			_(
				"Before ERiC is used, the Datenschutzhinweise of the tax administration have to be read and confirmed in the ERiC Settings."
			)
		)


def record(transmission: Document) -> None:
	"""Save an ELSTER Transmission, which only the server may change."""
	transmission.flags.recording = True
	transmission.save(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def stash_certificate(certificate_secret: str, certificate_password: str) -> str:
	"""Keep the certificate (.pfx, base64) and its password for the next transmission in the one-shot store
	of steuerbote.eric.secrets; returns the token that transmit() takes in their place.

	Parameters and locals carry "secret" or "password" in their names, which Frappe masks in its logs and
	tracebacks.
	"""
	if not any(frappe.has_permission(doctype, "write") for doctype in DOCUMENT_TYPES):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	try:
		decoded_secret = base64.b64decode(certificate_secret or "", validate=True)
	except binascii.Error, ValueError:
		decoded_secret = b""
	if not decoded_secret or len(decoded_secret) > MAX_CERTIFICATE_BYTES:
		frappe.throw(_("The certificate file could not be read. Choose the .pfx file of the ELSTER account."))
	if not PIN.fullmatch(certificate_password or ""):
		frappe.throw(
			_(
				"The certificate password has 6 to 128 characters: letters, digits, spaces and punctuation, without umlauts."
			)
		)
	return secrets.stash(decoded_secret, certificate_password)


def run_transmission(name: str, operation: str, transmission: str, token: str | None = None) -> None:
	"""Background job of Transmittable.transmit: one run through ERiC or its simulation.

	Whatever happens ends in the ELSTER Transmission, the lock of the document is released and the user who
	started the run gets a realtime notice. Only a Senden that ELSTER accepted changes the document: the job
	submits it, which files it. A run whose record was closed meanwhile as stale does nothing, since the lock
	of the document may belong to another run by now, and drops its certificate from the store.
	"""
	transmission = frappe.get_doc(TRANSMISSION, transmission)
	if transmission.status != RUNNING:
		_discard_certificate(token)
		return
	doctype = transmission.document_type
	result = None
	frappe.db.savepoint("elster_transmission")
	try:
		result, nutzdaten = _call_eric(
			frappe.get_doc(doctype, name), Operation(operation), token, transmission
		)
		_record_result(transmission, result, nutzdaten)
		if _files_the_document(result):
			_file_sent_document(doctype, name, transmission)
	except Exception as error:
		frappe.db.rollback(save_point="elster_transmission")
		_record_failure(transmission, _failure_text(error), result)
	finally:
		frappe.db.set_value(doctype, name, LOCK_FIELD, 0)
	frappe.publish_realtime(
		TRANSMISSION_EVENT,
		{
			"document_type": doctype,
			"document": name,
			"transmission": transmission.name,
			"operation": transmission.operation,
			"status": transmission.status,
			"simulated": cint(transmission.simulated),
		},
		user=transmission.user,
		after_commit=True,
	)


def _call_eric(doc: Document, operation: Operation, token: str | None, transmission: Document):
	settings = frappe.get_single(ERIC_SETTINGS)
	simulation = bool(cint(settings.simulation))
	if not simulation:
		require_privacy_notice(settings)
	certificate_secret, certificate_password = _take_certificate(token)
	header = envelope_header(doc, settings, operation, simulation)
	nutzdaten = doc.nutzdaten(header.hersteller_id)
	runtime_info = (
		None if simulation else _installed_runtime(doc, operation, header.hersteller_id, transmission)
	)
	result = transmission_adapter.run(
		operation, nutzdaten, header, runtime_info, certificate_secret, certificate_password
	)
	return result, nutzdaten


def envelope_header(
	doc: Document, settings: Document, operation: Operation, simulation: bool
) -> EnvelopeHeader:
	"""The header of the delivery. Its Hersteller-ID is the one of the ERiC Settings, which the runtime and
	Kz 09 of the Nutzdaten carry as well; only the simulation runs without one.

	Voranmeldung and form USt 1 H are both the datenartVersion UStVA_<Jahr>, which the Datenartversionmatrix of
	the ERiC documentation 44.3.6.0 gives „Mit UStDV und UStSV“, with the plugin checkUStVA_<Jahr>.
	"""
	hersteller_id = settings.hersteller_id or (SIMULATION_HERSTELLER_ID if simulation else "")
	datenlieferant = settings.datenlieferant or (doc.company if simulation else "")
	if not hersteller_id:
		frappe.throw(_("Enter the Hersteller-ID in the ERiC Settings."))
	if not datenlieferant:
		frappe.throw(_("Enter the Datenlieferant in the ERiC Settings."))
	return EnvelopeHeader(
		hersteller_id=hersteller_id,
		datenlieferant=datenlieferant,
		produkt_name=settings.produkt_name or DEFAULT_PRODUKT_NAME,
		produkt_version=steuerbote.__version__,
		empfaenger_finanzamt=finanzamt_of(doc.company),
		datenart_version=f"UStVA_{cint(doc.year)}",
		testmerker=TESTMERKER if operation is Operation.TEST_SEND else None,
		nutzdaten_ticket=NUTZDATEN_TICKET,
	)


def finanzamt_of(company: str) -> str:
	"""The Bundesfinanzamtsnummer: "die ersten 4 Stellen der 13-stelligen Steuernummer" (ERiC-API-Referenz)."""
	elster_tax_number = frappe.db.get_value(SETTINGS_DOCTYPE, company, "elster_tax_number")
	if not elster_tax_number:
		frappe.throw(_("The VAT Return Settings of {0} have no ELSTER Steuernummer.").format(company))
	return elster_tax_number[:4]


def _take_certificate(token: str | None) -> tuple[bytes | None, str | None]:
	if not token:
		return None, None
	try:
		return secrets.take(token)
	except secrets.SecretsExpired:
		frappe.throw(
			_(
				"The certificate and its password are no longer available. Start the transmission again and enter them anew."
			)
		)


def _discard_certificate(token: str | None) -> None:
	if token:
		with contextlib.suppress(secrets.SecretsExpired):
			secrets.take(token)


def _installed_runtime(doc: Document, operation: Operation, hersteller_id: str, transmission: Document):
	"""The runtime for the year of the document; ERiC writes its eric.log beside the site, one per run."""
	log_dir = eric_log_root() / transmission.name
	runtime_info = transmission_adapter.detect_runtime(cint(doc.year), operation, hersteller_id, log_dir)
	if runtime_info is None:
		frappe.throw(
			_(
				"No installed ERiC runtime serves {0}. Install the runtime for this year in the ERiC Settings; a beta serves Testsenden only."
			).format(cint(doc.year))
		)
	return runtime_info


def _status(result) -> str:
	if result.ok:
		return SUCCEEDED
	return UNKNOWN if result.outcome is Outcome.UNKNOWN else FAILED


def _files_the_document(result) -> bool:
	return result.operation is Operation.SEND and result.outcome is Outcome.ACCEPTED and not result.simulated


def _record_result(transmission: Document, result, nutzdaten: str) -> None:
	transmission.reload()
	transmission.update(
		{
			"status": _status(result),
			"outcome": result.outcome.value,
			"simulated": int(result.simulated),
			"eric_version": result.eric_version,
			"transferticket": result.transferticket,
			"testmerker": result.testmerker,
			"finished_at": now_datetime(),
		}
	)
	transmission.set("messages", _message_rows(result))
	response = result.server_response_xml
	files = {
		"xml": ("nutzdaten.xml", nutzdaten.encode()),
		"protocol_pdf": ("protokoll.pdf", result.protocol_pdf),
		"response_xml": ("serverantwort.xml", response.encode() if response else None),
	}
	for fieldname, (suffix, content) in files.items():
		transmission.set(fieldname, _attach_to_transmission(transmission, fieldname, suffix, content))
	record(transmission)


def _message_rows(result) -> list[dict]:
	return [
		{"severity": message.severity, "code": message.code, "text": message.text, "field": message.field}
		for message in result.messages
	]


def _attach_to_transmission(
	transmission: Document, fieldname: str, suffix: str, content: bytes | None
) -> str | None:
	"""A private File on the ELSTER Transmission; returns its address for the field.

	A file that cannot be stored is named in the messages instead: the record of the run, its Transferticket
	above all, matters more than any one of its files.
	"""
	if not content:
		return None
	file_name = f"{transmission.document}-{transmission.operation}-{suffix}"
	frappe.db.savepoint("elster_file")
	try:
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"attached_to_doctype": TRANSMISSION,
				"attached_to_name": transmission.name,
				"attached_to_field": fieldname,
				"is_private": 1,
				"content": content,
			}
		).insert(ignore_permissions=True)
	except Exception as error:
		frappe.db.rollback(save_point="elster_file")
		transmission.append(
			"messages",
			{
				"severity": "error",
				"text": _("The file {0} of the transmission could not be stored: {1}").format(
					file_name, _failure_text(error)
				),
			},
		)
		return None
	return file.file_url


def _file_sent_document(doctype: str, name: str, transmission: Document) -> None:
	"""Submit the document the Finanzamt has now. If that fails, the record says so: sending it again would
	file it twice."""
	frappe.db.savepoint("elster_filing")
	try:
		doc = frappe.get_doc(doctype, name)
		doc.flags.filing_transmission = transmission.name
		doc.submit()
	except Exception as error:
		frappe.db.rollback(save_point="elster_filing")
		transmission.reload()
		transmission.append(
			"messages", {"severity": "error", "text": _not_filed_text(transmission, _failure_text(error))}
		)
		record(transmission)


def _record_failure(transmission: Document, text: str, result) -> None:
	"""Record a run that broke off; with the result of ERiC, what ERiC answered is kept, the Transferticket
	of a Senden above all."""
	transmission.reload()
	outcome = result.outcome if result else Outcome.FAILED
	transmission.update(
		{
			"status": _status(result) if result else FAILED,
			"outcome": outcome.value,
			"finished_at": now_datetime(),
		}
	)
	if result:
		transmission.update(
			{
				"simulated": int(result.simulated),
				"eric_version": result.eric_version,
				"transferticket": result.transferticket,
				"testmerker": result.testmerker,
			}
		)
		transmission.set("messages", _message_rows(result))
		if _files_the_document(result):
			text = _not_filed_text(transmission, text)
	transmission.append("messages", {"severity": "error", "text": text})
	record(transmission)


def _not_filed_text(transmission: Document, reason: str) -> str:
	return _(
		"Transmitted with Transferticket {0}, but {1} could not be submitted: {2} Do not send it again; submit it once the cause is resolved."
	).format(transmission.transferticket, transmission.document, reason)


def _failure_text(error: Exception) -> str:
	"""What the user reads about a failure: the message of an expected error, else a pointer to the Error Log."""
	if isinstance(error, frappe.ValidationError | ValueError):
		return strip_html(str(error)).strip()
	frappe.log_error(title=_("ELSTER transmission failed"))
	return _("An unexpected error stopped the transmission. The Error Log has the details.")
