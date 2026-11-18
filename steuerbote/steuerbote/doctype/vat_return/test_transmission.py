"""Prüfen, Testsenden, Senden and „Als außerhalb abgegeben vermerken“ on the VAT Return.

The XML of steuerbote.elster, the header, the store of certificate and password and the simulation run for
real. FakeEric replaces the two calls of transmission_adapter that need an installed ERiC, the worker and
the runtime directory, with results of steuerbote.eric.result. With the stub of the ERiC library, which the
CI builds, a runtime installs from an archive and the worker sends through it.
"""

import base64
import hashlib
import shutil
import tempfile
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

import steuerbote
from steuerbote.eric import secrets
from steuerbote.eric.fake import placeholder_pdf
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import (
	ERROR,
	TESTMERKER,
	UNKNOWN_MESSAGE,
	Message,
	Operation,
	Outcome,
	TransmissionResult,
)
from steuerbote.eric.runtime import RuntimeInfo
from steuerbote.eric.tests import stub
from steuerbote.steuerbote.doctype.eric_settings.eric_settings import eric_log_root, run_installation
from steuerbote.steuerbote.doctype.vat_return import transmission_adapter
from steuerbote.steuerbote.doctype.vat_return.vat_return import (
	VATReturn,
	run_transmission,
	stash_certificate,
)
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)

COMPANY = "Steuerbote Test Uebermittlung GmbH"
# Files through the ERiC stub, with periods of its own.
STUB_COMPANY = "Steuerbote Test ERiC-Stub GmbH"
DATENLIEFERANT_ADDRESS = {
	"filer_name": COMPANY,
	"street": "Hauptstraße 1",
	"postal_code": "80331",
	"city": "München",
}
ACCOUNTS_USER = "steuerbote-uebermittlung@example.com"
JOB = "steuerbote.steuerbote.doctype.vat_return.vat_return.run_transmission"
JOB_ARGUMENTS = ("name", "operation", "token")
TRANSMISSION = "ELSTER Transmission"
DATENLIEFERANT = "Steuerbote Test Uebermittlung GmbH; Erika Beispiel; 089 1234567; erika@example.org"
# Invented for the tests, like every certificate and password here.
CERTIFICATE = b"0\x82\x01\x00 invented PKCS #12 \x00\x01\x02"
PIN = "Geheim-PIN-2026"
TICKET = "et0123456789abcdef"
STUB_TICKET = "et0stub0accepted0000000000000001"
STUB_LIB = "ERiC-44.3.6.0/Linux-x86_64/lib"
PROTOCOL = placeholder_pdf("Übertragungsprotokoll", ["Erfunden für die Tests"])

ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"8338": ("Erlöse Drittland nicht steuerbar", "Income"),
	"3123": ("Sonstige Leistungen EU 19 %", "Expense"),
	"1787": ("Umsatzsteuer nach § 13b UStG 19 %", "Liability"),
	"1577": ("Vorsteuer nach § 13b UStG 19 %", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1200": ("Bank", "Asset"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}

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

	def detect_runtime(self, year, operation, hersteller_id, log_dir):
		self.detections.append((year, operation, hersteller_id, log_dir))
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


def make_user(email: str, role: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Steuerbote",
				"send_welcome_email": 0,
				"roles": [{"role": role}],
			}
		).insert(ignore_permissions=True)
	return email


class TestTransmission(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STUEB")
		a = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)], **DATENLIEFERANT_ADDRESS)
		make_mapping(COMPANY)
		march = "2026-03-10"
		post_journal_entry(COMPANY, march, [(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)])
		post_journal_entry(COMPANY, march, [(a["1400"], 2000, 0), (a["8336"], 0, 2000)])
		post_journal_entry(COMPANY, march, [(a["1400"], 500, 0), (a["8338"], 0, 500)])
		post_journal_entry(
			COMPANY, march, [(a["3123"], 300, 0), (a["1577"], 57, 0), (a["1787"], 0, 57), (a["1200"], 0, 300)]
		)
		post_journal_entry(COMPANY, march, [(a["1576"], 95, 0), (a["1200"], 0, 95)])
		make_company(STUB_COMPANY, "STUES")
		make_settings(
			STUB_COMPANY, [(2026, "monthly", 1)], **{**DATENLIEFERANT_ADDRESS, "filer_name": STUB_COMPANY}
		)
		make_mapping(STUB_COMPANY)
		make_user(ACCOUNTS_USER, "Accounts User")

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
				**values,
			}
		)
		settings.save()

	def use_runtime(self):
		self.eric_settings(
			hersteller_id="12345",
			datenlieferant=DATENLIEFERANT,
			installed_version=RUNTIME.version,
			lib_dir=str(RUNTIME.lib_dir),
			log_dir=str(RUNTIME.log_dir),
		)

	def new_return(self, period: int, company: str = COMPANY, **fields):
		return frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": company,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": period,
				**fields,
			}
		).insert()

	def calculated(self, period: int, **fields):
		doc = self.new_return(period, **fields)
		doc.calculate()
		doc.reload()
		return doc

	def stash(self) -> str:
		return stash_certificate(base64.b64encode(CERTIFICATE).decode(), PIN)

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

	def test_pruefen_in_the_simulation_records_the_result_and_leaves_the_return_as_it_is(self):
		doc = self.calculated(3)
		transmission, publish, run = self.transmitted(doc, "validate")
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (0, "Bereit", 0))
		self.assertEqual(
			(
				transmission.vat_return,
				transmission.company,
				transmission.operation,
				transmission.status,
				transmission.outcome,
				transmission.simulated,
				transmission.eric_version,
				transmission.transferticket,
				transmission.testmerker,
				transmission.user,
			),
			(
				doc.name,
				COMPANY,
				"validate",
				"Erfolgreich",
				"valid",
				1,
				"simulation",
				None,
				None,
				"Administrator",
			),
		)
		self.assertIn("SIM-000", self.codes(transmission))
		self.assertLessEqual(transmission.started_at, transmission.finished_at)
		operation, nutzdaten, header, runtime_info, certificate, password = run.call_args.args
		self.assertEqual(
			(operation, runtime_info, certificate, password), (Operation.VALIDATE, None, None, None)
		)
		self.assertEqual(
			header,
			EnvelopeHeader(
				hersteller_id="00000",
				datenlieferant=COMPANY,
				produkt_name="steuerbote",
				produkt_version=steuerbote.__version__,
				empfaenger_finanzamt="9123",
				datenart_version="UStVA_2026",
				testmerker=None,
				nutzdaten_ticket="1",
			),
		)
		for element in (
			"<Zeitraum>03</Zeitraum>",
			"<Steuernummer>9123045678901</Steuernummer>",
			"<Kz09>00000</Kz09>",
			"<Kz81>1000</Kz81>",
			"<Kz67>57.00</Kz67>",
			"<Kz83>95.00</Kz83>",
		):
			with self.subTest(element=element):
				self.assertIn(element, nutzdaten)
		xml = self.attachment(transmission, "xml")
		self.assertEqual((xml.file_url, xml.is_private), (transmission.xml, 1))
		self.assertEqual(xml.get_content(), nutzdaten)
		self.assertFalse(transmission.protocol_pdf or transmission.response_xml)
		self.assertEqual(
			publish.call_args.args,
			(
				"steuerbote_elster_transmission",
				{
					"vat_return": doc.name,
					"transmission": transmission.name,
					"operation": "validate",
					"status": "Erfolgreich",
					"simulated": 1,
				},
			),
		)
		self.assertEqual(publish.call_args.kwargs, {"user": "Administrator", "after_commit": True})

	def test_testsenden_in_the_simulation_needs_no_certificate_and_keeps_the_return_a_draft(self):
		doc = self.calculated(1)
		transmission, _, _ = self.transmitted(doc, "test_send")
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.simulated, transmission.testmerker),
			("Erfolgreich", "accepted", 1, "700000004"),
		)
		self.assertTrue(transmission.transferticket.startswith("SIM-"))
		protocol = self.attachment(transmission, "protocol_pdf")
		self.assertTrue(protocol.get_content().startswith(b"%PDF"))
		self.assertEqual((doc.docstatus, doc.status), (0, "Bereit"))

	def test_senden_is_not_offered_in_the_simulation(self):
		doc = self.calculated(2)
		with patch("frappe.enqueue") as enqueue, self.assertRaisesRegex(frappe.ValidationError, "simulation"):
			doc.transmit("send")
		enqueue.assert_not_called()
		self.assertFalse(frappe.db.exists(TRANSMISSION, {"vat_return": doc.name}))

	def test_an_unknown_operation_is_refused(self):
		doc = self.calculated(2)
		with patch("frappe.enqueue") as enqueue, self.assertRaises(frappe.ValidationError):
			doc.transmit("delete")
		enqueue.assert_not_called()

	def test_senden_needs_the_permission_to_submit(self):
		self.use_runtime()
		doc = self.calculated(2)
		with self.set_user(ACCOUNTS_USER), patch("frappe.enqueue") as enqueue:
			with self.assertRaises(frappe.PermissionError):
				doc.transmit("send", "token")
			doc.transmit("validate")
		self.assertEqual(enqueue.call_count, 1)

	def test_senden_files_the_return_and_keeps_the_transferticket(self):
		self.use_runtime()
		doc = self.calculated(4)
		fake = FakeEric()
		token = self.stash()
		transmission, _, _ = self.transmitted(doc, "send", fake, token)
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (1, "Abgegeben", 0))
		self.assertEqual(
			(
				transmission.status,
				transmission.outcome,
				transmission.simulated,
				transmission.transferticket,
				transmission.testmerker,
				transmission.eric_version,
			),
			("Erfolgreich", "accepted", 0, TICKET, None, "44.3.6.0"),
		)
		log_dir = eric_log_root() / transmission.name
		self.assertEqual(fake.detections, [(2026, Operation.SEND, "12345", log_dir)])
		(run,) = fake.runs
		self.assertEqual((run["certificate"], run["password"]), (CERTIFICATE, PIN))
		self.assertEqual(run["runtime"], replace(RUNTIME, hersteller_id="12345", log_dir=log_dir))
		self.assertEqual(
			(run["header"].hersteller_id, run["header"].datenlieferant, run["header"].testmerker),
			("12345", DATENLIEFERANT, None),
		)
		self.assertIn("<Kz09>12345</Kz09>", run["nutzdaten"])
		self.assertEqual(self.attachment(transmission, "protocol_pdf").get_content(), PROTOCOL)
		with self.assertRaises(secrets.SecretsExpired):
			secrets.take(token)

	def test_the_certificate_and_its_password_reach_the_job_only_as_a_token(self):
		self.use_runtime()
		doc = self.calculated(10)
		fake = FakeEric()
		token = self.stash()
		name, enqueue = self.transmit(doc, "test_send", token)
		(call,) = enqueue.call_args_list
		self.assertEqual(call.args, (JOB,))
		self.assertEqual(
			call.kwargs,
			{
				"name": doc.name,
				"operation": "test_send",
				"token": token,
				"queue": "long",
				"timeout": 300,
				"job_id": f"steuerbote:elster:{doc.name}",
				"deduplicate": True,
				"enqueue_after_commit": True,
			},
		)
		self.run_job(enqueue, fake)
		transmission = frappe.get_doc(TRANSMISSION, name)
		self.assertEqual((transmission.testmerker, transmission.simulated), ("700000004", 0))
		self.assertEqual(fake.runs[0]["header"].testmerker, "700000004")
		self.assertEqual(fake.detections[0][1], Operation.TEST_SEND)
		recorded = frappe.as_json(transmission.as_dict())
		self.assertNotIn(PIN, recorded)
		self.assertNotIn(base64.b64encode(CERTIFICATE).decode(), recorded)

	def test_testsenden_needs_the_certificate_outside_the_simulation(self):
		self.use_runtime()
		doc = self.calculated(12)
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "certificate"),
		):
			doc.transmit("test_send")
		enqueue.assert_not_called()

	def test_a_certificate_that_is_gone_ends_in_a_failed_transmission(self):
		self.use_runtime()
		doc = self.calculated(10)
		fake = FakeEric()
		transmission, publish, _ = self.transmitted(doc, "test_send", fake, "expired")
		self.assertEqual(
			(transmission.status, transmission.outcome, doc.transmission_in_progress),
			("Fehlgeschlagen", "failed", 0),
		)
		self.assertIn("certificate", transmission.messages[-1].text)
		self.assertEqual(fake.runs, [])
		self.assertEqual(publish.call_args.args[1]["status"], "Fehlgeschlagen")

	def test_data_the_xml_does_not_take_end_in_a_failed_transmission(self):
		doc = self.calculated(1)
		street = frappe.db.get_value("VAT Return Settings", COMPANY, "street")
		frappe.db.set_value("VAT Return Settings", COMPANY, "street", None)
		self.addCleanup(frappe.db.set_value, "VAT Return Settings", COMPANY, "street", street)
		transmission, _, run = self.transmitted(doc, "validate")
		self.assertEqual((transmission.status, doc.transmission_in_progress), ("Fehlgeschlagen", 0))
		self.assertIn("street of the Datenlieferant", transmission.messages[-1].text)
		run.assert_not_called()
		self.assertEqual((doc.docstatus, doc.status), (0, "Bereit"))

	def test_a_rejected_send_keeps_the_return_a_draft_with_the_messages(self):
		self.use_runtime()
		doc = self.calculated(5)
		error = Message("610101210", "Die Steuernummer ist ungültig.", ERROR, "Steuernummer")
		fake = FakeEric(outcome=Outcome.REJECTED, messages=(error,))
		transmission, _, _ = self.transmitted(doc, "send", fake, self.stash())
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (0, "Bereit", 0))
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.transferticket),
			("Fehlgeschlagen", "rejected", None),
		)
		self.assertEqual(
			[(row.code, row.severity, row.text, row.field) for row in transmission.messages],
			[("610101210", "error", "Die Steuernummer ist ungültig.", "Steuernummer")],
		)

	def test_a_send_that_may_have_reached_elster_blocks_sending_until_it_is_cleared(self):
		self.use_runtime()
		doc = self.calculated(12)
		lost = Message("SB-WORKER", "ERiC hat nach 120 Sekunden nicht geantwortet.", ERROR)
		fake = FakeEric(outcome=Outcome.UNKNOWN, messages=(lost, UNKNOWN_MESSAGE))
		transmission, publish, _ = self.transmitted(doc, "send", fake, self.stash())
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.transferticket),
			("Unbekannt", "unknown", None),
		)
		self.assertEqual(self.codes(transmission), ["SB-WORKER", "SB-UNKNOWN"])
		self.assertEqual((doc.docstatus, publish.call_args.args[1]["status"]), (0, "Unbekannt"))
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(
				frappe.ValidationError, f"Whether {transmission.name} reached ELSTER"
			):
				doc.transmit("send", self.stash())
			with self.assertRaisesRegex(frappe.ValidationError, "transmitted already"):
				self.calculated(12).transmit("send", self.stash())
		enqueue.assert_not_called()
		frappe.delete_doc(TRANSMISSION, transmission.name)
		_, enqueue = self.transmit(doc, "send", self.stash())
		self.assertEqual(enqueue.call_args.kwargs["operation"], "send")

	def test_a_sent_return_that_could_not_be_submitted_is_never_sent_again(self):
		self.use_runtime()
		doc = self.calculated(6)
		fake = FakeEric()
		with patch.object(VATReturn, "before_submit", side_effect=frappe.ValidationError("Kaputt")):
			transmission, _, _ = self.transmitted(doc, "send", fake, self.stash())
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (0, "Bereit", 0))
		self.assertEqual((transmission.status, transmission.transferticket), ("Erfolgreich", TICKET))
		self.assertEqual(transmission.messages[-1].severity, "error")
		self.assertIn(TICKET, transmission.messages[-1].text)
		self.assertIn("Kaputt", transmission.messages[-1].text)
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(frappe.ValidationError, "transmitted already"):
				doc.transmit("send", self.stash())
			with self.assertRaisesRegex(frappe.ValidationError, "transmitted already"):
				self.calculated(6).transmit("send", self.stash())
		enqueue.assert_not_called()

	def test_a_corrected_return_replaces_the_return_sent_before(self):
		self.use_runtime()
		first = self.calculated(7)
		fake = FakeEric()
		self.transmitted(first, "send", fake, self.stash())
		correction = self.calculated(7, is_correction=1)
		self.transmitted(correction, "send", fake, self.stash())
		first.reload()
		self.assertEqual((first.status, correction.docstatus, correction.status), ("Ersetzt", 1, "Abgegeben"))
		self.assertIn("<Kz10>1</Kz10>", fake.runs[1]["nutzdaten"])

	def test_one_transmission_at_a_time(self):
		doc = self.calculated(8)
		name, _ = self.transmit(doc, "validate")
		self.assertEqual(frappe.db.get_value("VAT Return", doc.name, "transmission_in_progress"), 1)
		self.assertEqual(frappe.db.get_value(TRANSMISSION, name, "status"), "Läuft")
		with (
			patch("steuerbote.steuerbote.doctype.vat_return.vat_return.is_job_enqueued", return_value=True),
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "running"),
		):
			doc.transmit("validate")
		enqueue.assert_not_called()
		doc.reload()
		doc.remarks = "Geändert während der Übermittlung"
		with self.assertRaisesRegex(frappe.ValidationError, "running"):
			doc.save()
		doc.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "running"):
			doc.calculate()

	def test_a_check_whose_job_is_gone_is_closed_as_failed(self):
		doc = self.calculated(8)
		first, _ = self.transmit(doc, "validate")
		with patch("steuerbote.steuerbote.doctype.vat_return.vat_return.is_job_enqueued", return_value=False):
			second, enqueue = self.transmit(doc, "validate")
		enqueue.assert_called_once()
		stale = frappe.get_doc(TRANSMISSION, first)
		self.assertEqual((stale.status, stale.outcome), ("Fehlgeschlagen", "failed"))
		self.assertTrue(stale.finished_at)
		self.assertIn("Mein ELSTER", stale.messages[-1].text)
		self.assertEqual(frappe.db.get_value(TRANSMISSION, second, "status"), "Läuft")

	def test_a_send_whose_job_is_gone_has_an_unknown_outcome_and_is_not_repeated(self):
		self.use_runtime()
		doc = self.calculated(11)
		first, _ = self.transmit(doc, "send", self.stash())
		with (
			patch("steuerbote.steuerbote.doctype.vat_return.vat_return.is_job_enqueued", return_value=False),
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, f"Whether {first} reached ELSTER"),
		):
			doc.transmit("send", self.stash())
		enqueue.assert_not_called()
		self.assertEqual(
			frappe.db.get_value(TRANSMISSION, first, ["status", "outcome"]), ("Unbekannt", "unknown")
		)

	def test_only_a_calculated_draft_is_transmitted(self):
		draft = self.new_return(11)
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(frappe.ValidationError, "Calculate"):
				draft.transmit("validate")
			filed = self.calculated(11)
			filed.submit()
			with self.assertRaisesRegex(frappe.ValidationError, "draft"):
				filed.transmit("validate")
		enqueue.assert_not_called()

	def test_marking_as_filed_outside_records_the_note_and_files_the_return(self):
		doc = self.calculated(9)
		note = "Am 9. Oktober 2026 in Mein ELSTER übermittelt"
		name = doc.mark_filed_outside(note)
		doc.reload()
		self.assertEqual((doc.docstatus, doc.status), (1, "Abgegeben"))
		transmission = frappe.get_doc(TRANSMISSION, name)
		self.assertEqual(
			(
				transmission.vat_return,
				transmission.operation,
				transmission.status,
				transmission.simulated,
				transmission.remarks,
				transmission.user,
			),
			(doc.name, "extern", "Erfolgreich", 0, note, "Administrator"),
		)
		with self.assertRaisesRegex(frappe.ValidationError, "draft"):
			doc.mark_filed_outside(note)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc(TRANSMISSION, name)

	def test_marking_as_filed_outside_needs_a_note_and_a_calculation(self):
		doc = self.new_return(12)
		with self.assertRaisesRegex(frappe.ValidationError, "how and when"):
			doc.mark_filed_outside("  ")
		with self.assertRaisesRegex(frappe.ValidationError, "Calculate"):
			doc.mark_filed_outside("In Mein ELSTER übermittelt")
		self.assertFalse(frappe.db.exists(TRANSMISSION, {"vat_return": doc.name}))
		self.assertEqual(frappe.db.get_value("VAT Return", doc.name, "docstatus"), 0)

	def test_a_transmission_stays_as_it_was_recorded(self):
		doc = self.calculated(1)
		transmission, _, _ = self.transmitted(doc, "validate")
		transmission.transferticket = "et-geaendert"
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be changed"):
			transmission.save()
		with self.assertRaises(frappe.LinkExistsError):
			frappe.delete_doc("VAT Return", doc.name)
		frappe.delete_doc(TRANSMISSION, transmission.name)
		self.assertFalse(frappe.db.exists(TRANSMISSION, transmission.name))

	def test_stashing_keeps_certificate_and_password_behind_a_token(self):
		encoded = base64.b64encode(CERTIFICATE).decode()
		token = stash_certificate(encoded, PIN)
		self.assertEqual(secrets.take(token), (CERTIFICATE, PIN))
		with self.assertRaises(secrets.SecretsExpired):
			secrets.take(token)
		for certificate, password, message in (
			("", PIN, "certificate file"),
			("kein base64!", PIN, "certificate file"),
			(encoded, "kurz", "6 to 128"),
			(encoded, "x" * 129, "6 to 128"),
			(encoded, "Passwört-2026", "6 to 128"),
		):
			with (
				self.subTest(certificate=certificate[:8], password=len(password)),
				self.assertRaisesRegex(frappe.ValidationError, message) as raised,
			):
				stash_certificate(certificate, password)
			self.assertNotIn(password, str(raised.exception))

	def test_the_form_learns_whether_eric_is_simulated(self):
		doc = self.new_return(3)
		doc.run_method("onload")
		self.assertEqual(doc.get_onload("elster"), {"simulation": True})
		self.use_runtime()
		doc.run_method("onload")
		self.assertEqual(doc.get_onload("elster"), {"simulation": False})

	def test_through_the_eric_stub_a_runtime_installs_and_testsenden_and_senden_go_out(self):
		library = stub.library()
		directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-"))
		self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
		archive = directory / "ERiC-44.3.6.0-Linux-x86_64.jar"
		with zipfile.ZipFile(archive, "w") as jar:
			jar.write(library, f"{STUB_LIB}/libericapi.so")
			jar.writestr(f"{STUB_LIB}/plugins2/libcommonData.so", b"")
			jar.writestr(f"{STUB_LIB}/plugins2/libcheckUStVA_2026.so", b"")
		checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
		root = directory / "eric"
		with patch.object(transmission_adapter, "runtime_root", return_value=root):
			with patch("frappe.publish_realtime"):
				run_installation(archive_path=str(archive), sha256=checksum)
			settings = frappe.get_single("ERiC Settings")
			self.assertEqual(
				(settings.installed_version, settings.lib_dir), ("44.3.6.0", str(root / "44.3.6.0" / "lib"))
			)
			settings.update({"hersteller_id": "12345", "datenlieferant": DATENLIEFERANT})
			settings.save()
			doc = self.new_return(1, company=STUB_COMPANY)
			doc.calculate()
			doc.reload()
			test, _, _ = self.transmitted(doc, "test_send", token=self.stash())
			self.assertEqual(
				(test.status, test.outcome, test.simulated, test.transferticket, test.testmerker),
				("Erfolgreich", "accepted", 0, STUB_TICKET, "700000004"),
			)
			self.assertEqual(test.eric_version, "44.3.6.0")
			self.assertTrue((eric_log_root() / test.name).is_dir())
			self.assertEqual((doc.docstatus, doc.status), (0, "Bereit"))
			sent, _, _ = self.transmitted(doc, "send", token=self.stash())
		self.assertEqual(
			(sent.status, sent.outcome, sent.transferticket), ("Erfolgreich", "accepted", STUB_TICKET)
		)
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (1, "Abgegeben", 0))
