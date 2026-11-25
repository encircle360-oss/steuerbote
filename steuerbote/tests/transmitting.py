"""Stand-ins and steps for the tests that transmit a document through ERiC or its simulation.

FakeEric replaces the two calls of transmission_adapter that need an installed ERiC, the worker and the runtime
directory, with results of steuerbote.eric.result; the XML of steuerbote.elster, the header, the store of
certificate and password and the simulation run for real. Transmitting gives an IntegrationTestCase the steps of
a run: ERiC Settings that simulate unless use_runtime() sets up a runtime, the stash of certificate and password,
transmit with the job it enqueues and the ELSTER Transmission the job leaves.
"""

import base64
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import frappe

from steuerbote.eric import secrets
from steuerbote.eric.fake import placeholder_pdf
from steuerbote.eric.result import TESTMERKER, Message, Operation, Outcome, TransmissionResult
from steuerbote.eric.runtime import RuntimeInfo
from steuerbote.steuerbote.doctype.elster_transmission.transmission import run_transmission, stash_certificate
from steuerbote.steuerbote.doctype.vat_return import transmission_adapter

TRANSMISSION = "ELSTER Transmission"
JOB = "steuerbote.steuerbote.doctype.elster_transmission.transmission.run_transmission"
JOB_ARGUMENTS = ("name", "operation", "transmission")
IS_JOB_ENQUEUED = "steuerbote.steuerbote.doctype.elster_transmission.transmission.is_job_enqueued"
DATENLIEFERANT = "Steuerbote Test Uebermittlung GmbH; Erika Beispiel; 089 1234567; erika@example.org"
# Invented for the tests, like every certificate and password here.
CERTIFICATE = b"0\x82\x01\x00 invented PKCS #12 \x00\x01\x02"
PIN = "Geheim-PIN-2026"
TICKET = "et0123456789abcdef"
PROTOCOL = placeholder_pdf("Übertragungsprotokoll", ["Erfunden für die Tests"])

RUNTIME = RuntimeInfo(
	"44.3.6.0",
	Path("/srv/eric/44.3.6.0/lib"),
	Path("/srv/eric/44.3.6.0/lib"),
	Path("/srv/eric/log"),
	"",
)


class FakeEric:
	"""Stands in for the worker and the runtime directory of steuerbote.eric and keeps what it was given."""

	def __init__(
		self,
		*,
		outcome: Outcome | None = None,
		messages: tuple[Message, ...] = (),
		error: Exception | None = None,
	):
		self.outcome = outcome
		self.messages = messages
		self.error = error
		self.runs: list[dict] = []
		self.detections: list[tuple] = []

	def patch(self):
		return patch.multiple(transmission_adapter, run=self.run, detect_runtime=self.detect_runtime)

	def detect_runtime(self, datenart, operation, hersteller_id, log_dir):
		self.detections.append((datenart, operation, hersteller_id, log_dir))
		return replace(RUNTIME, hersteller_id=hersteller_id, log_dir=log_dir)

	def run(self, operation, nutzdaten_xml, header, runtime_info, certificate_secret, certificate_password):
		self.runs.append(
			{
				"operation": operation,
				"nutzdaten": nutzdaten_xml,
				"header": header,
				"runtime": runtime_info,
				"certificate": certificate_secret,
				"password": certificate_password,
			}
		)
		if self.error:
			raise self.error
		outcome = self.outcome or (Outcome.ACCEPTED if operation.sends else Outcome.VALID)
		return TransmissionResult(
			operation,
			outcome.ok,
			runtime_info is None,
			RUNTIME.version,
			TICKET if outcome is Outcome.ACCEPTED else None,
			TESTMERKER if operation is Operation.TEST_SEND else None,
			self.messages,
			PROTOCOL,
			"<Elster/>" if operation.sends else None,
			outcome,
		)


class Transmitting:
	"""The steps of a test that transmits, mixed into an IntegrationTestCase before it."""

	def setUp(self):
		super().setUp()
		self.eric_settings()

	def eric_settings(self, **values):
		"""Without values the ERiC Settings simulate; use_runtime() configures a runtime."""
		settings = frappe.get_single("ERiC Settings")
		settings.update(
			{
				"hersteller_id": "",
				"datenlieferant": "",
				"produkt_name": "steuerbote",
				"installed_version": "",
				"lib_dir": "",
				"log_dir": "",
				"privacy_notice_confirmed": 0,
				**values,
			}
		)
		settings.save()

	def use_runtime(self, **values):
		"""ERiC Settings with a runtime; transmit, which refuses a run without one at the button, finds the runtime
		of the bench or, where the bench has none, the stand-in RUNTIME, which a FakeEric then serves."""
		self.eric_settings(
			**{
				"hersteller_id": "12345",
				"datenlieferant": DATENLIEFERANT,
				"installed_version": RUNTIME.version,
				"lib_dir": str(RUNTIME.lib_dir),
				"log_dir": str(RUNTIME.log_dir),
				"privacy_notice_confirmed": 1,
				**values,
			}
		)
		detect = transmission_adapter.detect_runtime

		def found(datenart, operation, hersteller_id, log_dir):
			return detect(datenart, operation, hersteller_id, log_dir) or replace(
				RUNTIME, hersteller_id=hersteller_id, log_dir=log_dir
			)

		patcher = patch.object(transmission_adapter, "detect_runtime", side_effect=found)
		patcher.start()
		self.addCleanup(patcher.stop)

	def stash(self, doc) -> str:
		"""Certificate and password, entered by the current user for the document."""
		return stash_certificate(doc.doctype, doc.name, base64.b64encode(CERTIFICATE).decode(), PIN)

	def handed_over(self, transmission: str, doc) -> tuple[bytes, str]:
		"""What the job of the transmission would take, taken by the test instead."""
		return secrets.take(transmission, user=frappe.session.user, document=(doc.doctype, doc.name))

	def transmit(self, doc, operation: str, token: str | None = None):
		with patch("frappe.enqueue") as enqueue:
			name = doc.transmit(operation, token)
		return name, enqueue

	def run_job(self, enqueue, fake: FakeEric | None = None):
		"""Run the job enqueued; without a fake through the real service, whose run is recorded."""
		(call,) = enqueue.call_args_list
		calls = (
			fake.patch()
			if fake
			else patch.object(transmission_adapter, "run", wraps=transmission_adapter.run)
		)
		with calls as run, patch("frappe.publish_realtime") as publish:
			run_transmission(**{key: call.kwargs[key] for key in JOB_ARGUMENTS})
		return publish, run

	def transmitted(self, doc, operation: str, fake: FakeEric | None = None, token: str | None = None):
		name, enqueue = self.transmit(doc, operation, token)
		publish, run = self.run_job(enqueue, fake)
		doc.reload()
		return frappe.get_doc(TRANSMISSION, name), publish, run

	def attachment(self, transmission, fieldname: str):
		name = frappe.db.get_value(
			"File",
			{
				"attached_to_doctype": TRANSMISSION,
				"attached_to_name": transmission.name,
				"attached_to_field": fieldname,
			},
		)
		return frappe.get_doc("File", name)

	def codes(self, transmission) -> list[str]:
		return [row.code for row in transmission.messages]
