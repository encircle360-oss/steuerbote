"""Prüfen, Testsenden, Senden and „Als außerhalb abgegeben vermerken“ on the VAT Return.

FakeEric replaces the functions of transmission_adapter: the ERiC library layer, the XML builder and the
store for certificate and password. Its results have the fields of steuerbote.eric.result.
"""

import base64
import io
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from pypdf import PdfWriter

import steuerbote
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
ACCOUNTS_USER = "steuerbote-uebermittlung@example.com"
JOB = "steuerbote.steuerbote.doctype.vat_return.vat_return.run_transmission"
JOB_ARGUMENTS = ("name", "operation", "token")
TRANSMISSION = "ELSTER Transmission"
DATENLIEFERANT = "Steuerbote Test Uebermittlung GmbH; Erika Beispiel; 089 1234567; erika@example.org"
NUTZDATEN = (
	'<Anmeldungssteuern xmlns="http://finkonsens.de/elster/elsteranmeldung/ustva/v2026" version="2026"/>'
)
# Invented for the tests, like every certificate and password here.
CERTIFICATE = b"0\x82\x01\x00 invented PKCS #12 \x00\x01\x02"
PIN = "Geheim-PIN-2026"
TICKET = "et0123456789abcdef"

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


def money(value) -> Decimal:
	return Decimal(str(value)).quantize(Decimal("0.01"))


def blank_pdf() -> bytes:
	writer = PdfWriter()
	writer.add_blank_page(width=595, height=842)
	buffer = io.BytesIO()
	writer.write(buffer)
	return buffer.getvalue()


PROTOCOL = blank_pdf()


class Operation(Enum):
	VALIDATE = "validate"
	TEST_SEND = "test_send"
	SEND = "send"


@dataclass(frozen=True, slots=True)
class Message:
	code: str
	text: str
	severity: str
	field: str | None = None


@dataclass(frozen=True, slots=True)
class TransmissionResult:
	operation: Operation
	ok: bool
	simulated: bool
	eric_version: str
	transferticket: str | None
	testmerker: str | None
	messages: tuple[Message, ...] = ()
	protocol_pdf: bytes | None = None
	server_response_xml: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimeInfo:
	version: str
	lib_dir: Path
	plugin_dir: Path
	log_dir: Path
	hersteller_id: str


RUNTIME = RuntimeInfo(
	"44.3.6.0",
	Path("/srv/eric/44.3.6.0/lib"),
	Path("/srv/eric/44.3.6.0/lib/plugins"),
	Path("/srv/eric/logs"),
	"",
)


class FakeEric:
	"""Stands in for transmission_adapter and keeps what it was given."""

	def __init__(
		self, *, ok: bool = True, messages: tuple[Message, ...] = (), error: Exception | None = None
	):
		self.ok = ok
		self.messages = messages
		self.error = error
		self.secrets: dict[str, tuple[bytes, str]] = {}
		self.built: list[tuple[str, str, dict[str, Decimal]]] = []
		self.runs: list[dict] = []

	def patch(self):
		return patch.multiple(
			transmission_adapter,
			build_nutzdaten=self.build_nutzdaten,
			run=self.run,
			stash=self.stash,
			take=self.take,
			detect_runtime=self.detect_runtime,
		)

	def build_nutzdaten(self, vat_return, hersteller_id):
		amounts = {row.kennzahl: money(row.final) for row in vat_return.kennzahlen}
		self.built.append((vat_return.name, hersteller_id, amounts))
		return NUTZDATEN

	def stash(self, certificate_secret, certificate_password):
		token = f"token-{len(self.secrets) + 1}"
		self.secrets[token] = (certificate_secret, certificate_password)
		return token

	def take(self, token):
		return self.secrets.pop(token)

	def detect_runtime(self, hersteller_id):
		return replace(RUNTIME, hersteller_id=hersteller_id)

	def run(self, operation, nutzdaten_xml, header, runtime, certificate_secret, certificate_password):
		self.runs.append(
			{
				"operation": operation,
				"nutzdaten": nutzdaten_xml,
				"header": header,
				"runtime": runtime,
				"certificate": certificate_secret,
				"password": certificate_password,
			}
		)
		if self.error:
			raise self.error
		simulated = runtime is None
		sending = operation != Operation.VALIDATE.value
		return TransmissionResult(
			operation=Operation(operation),
			ok=self.ok,
			simulated=simulated,
			eric_version="simulation" if simulated else RUNTIME.version,
			transferticket=(("SIM-" if simulated else "") + TICKET) if sending and self.ok else None,
			testmerker=header["testmerker"],
			messages=self.messages,
			protocol_pdf=PROTOCOL,
			server_response_xml="<Elster/>" if sending else None,
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
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)
		march = "2026-03-10"
		post_journal_entry(COMPANY, march, [(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)])
		post_journal_entry(COMPANY, march, [(a["1400"], 2000, 0), (a["8336"], 0, 2000)])
		post_journal_entry(COMPANY, march, [(a["1400"], 500, 0), (a["8338"], 0, 500)])
		post_journal_entry(
			COMPANY, march, [(a["3123"], 300, 0), (a["1577"], 57, 0), (a["1787"], 0, 57), (a["1200"], 0, 300)]
		)
		post_journal_entry(COMPANY, march, [(a["1576"], 95, 0), (a["1200"], 0, 95)])
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

	def new_return(self, period: int, **fields):
		return frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
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

	def stash(self, fake: FakeEric) -> str:
		with fake.patch():
			return stash_certificate(base64.b64encode(CERTIFICATE).decode(), PIN)

	def transmit(self, doc, operation: str, token: str | None = None):
		with patch("frappe.enqueue") as enqueue:
			name = doc.transmit(operation, token)
		return name, enqueue

	def run_job(self, enqueue, fake: FakeEric):
		(call,) = enqueue.call_args_list
		with fake.patch(), patch("frappe.publish_realtime") as publish:
			run_transmission(**{key: call.kwargs[key] for key in JOB_ARGUMENTS})
		return publish

	def transmitted(self, doc, operation: str, fake: FakeEric, token: str | None = None):
		name, enqueue = self.transmit(doc, operation, token)
		publish = self.run_job(enqueue, fake)
		doc.reload()
		return frappe.get_doc(TRANSMISSION, name), publish

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

	def test_pruefen_in_the_simulation_records_the_result_and_leaves_the_return_as_it_is(self):
		doc = self.calculated(3)
		hint = Message("SIM-000", "Simulation, keine Übermittlung", "hint")
		fake = FakeEric(messages=(hint,))
		transmission, publish = self.transmitted(doc, "validate", fake)
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (0, "Bereit", 0))
		self.assertEqual(
			(
				transmission.vat_return,
				transmission.company,
				transmission.operation,
				transmission.status,
				transmission.simulated,
				transmission.eric_version,
				transmission.transferticket,
				transmission.testmerker,
				transmission.user,
			),
			(doc.name, COMPANY, "validate", "Erfolgreich", 1, "simulation", None, None, "Administrator"),
		)
		self.assertEqual(
			[(row.code, row.severity, row.text, row.field) for row in transmission.messages],
			[("SIM-000", "hint", "Simulation, keine Übermittlung", None)],
		)
		self.assertLessEqual(transmission.started_at, transmission.finished_at)
		self.assertEqual(
			fake.built,
			[
				(
					doc.name,
					"00000",
					{
						"81": money(1000),
						"46": money(300),
						"47": money(57),
						"21": money(2000),
						"45": money(500),
						"66": money(95),
						"67": money(57),
						"83": money(95),
					},
				)
			],
		)
		(run,) = fake.runs
		self.assertEqual(
			(run["operation"], run["nutzdaten"], run["runtime"], run["certificate"], run["password"]),
			("validate", NUTZDATEN, None, None, None),
		)
		self.assertEqual(
			run["header"],
			{
				"hersteller_id": "00000",
				"datenlieferant": COMPANY,
				"produkt_name": "steuerbote",
				"produkt_version": steuerbote.__version__,
				"empfaenger_finanzamt": "9123",
				"datenart_version": "UStVA_2026",
				"testmerker": None,
				"nutzdaten_ticket": "1",
			},
		)
		xml = self.attachment(transmission, "xml")
		self.assertEqual((xml.file_url, xml.is_private), (transmission.xml, 1))
		self.assertEqual(xml.get_content(), NUTZDATEN)
		protocol = self.attachment(transmission, "protocol_pdf")
		self.assertEqual((protocol.file_url, protocol.is_private), (transmission.protocol_pdf, 1))
		self.assertEqual(protocol.get_content(), PROTOCOL)
		self.assertFalse(transmission.response_xml)
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
		transmission, _ = self.transmitted(doc, "test_send", FakeEric())
		self.assertEqual(
			(
				transmission.status,
				transmission.simulated,
				transmission.testmerker,
				transmission.transferticket,
			),
			("Erfolgreich", 1, "700000004", f"SIM-{TICKET}"),
		)
		self.assertEqual((doc.docstatus, doc.status), (0, "Bereit"))
		self.assertEqual(self.attachment(transmission, "response_xml").get_content(), "<Elster/>")

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
				doc.transmit("send", "token-1")
			doc.transmit("validate")
		self.assertEqual(enqueue.call_count, 1)

	def test_senden_files_the_return_and_keeps_the_transferticket(self):
		self.use_runtime()
		doc = self.calculated(4)
		fake = FakeEric()
		transmission, _ = self.transmitted(doc, "send", fake, self.stash(fake))
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (1, "Abgegeben", 0))
		self.assertEqual(
			(
				transmission.status,
				transmission.simulated,
				transmission.transferticket,
				transmission.testmerker,
				transmission.eric_version,
			),
			("Erfolgreich", 0, TICKET, None, "44.3.6.0"),
		)
		(run,) = fake.runs
		self.assertEqual((run["certificate"], run["password"]), (CERTIFICATE, PIN))
		self.assertEqual(run["runtime"], replace(RUNTIME, hersteller_id="12345"))
		self.assertEqual(
			(run["header"]["hersteller_id"], run["header"]["datenlieferant"], run["header"]["testmerker"]),
			("12345", DATENLIEFERANT, None),
		)
		self.assertEqual(fake.built[0][1], "12345")
		self.assertEqual(fake.secrets, {})

	def test_the_certificate_and_its_password_reach_the_job_only_as_a_token(self):
		self.use_runtime()
		doc = self.calculated(10)
		fake = FakeEric()
		token = self.stash(fake)
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
		self.assertEqual(fake.runs[0]["header"]["testmerker"], "700000004")
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
		transmission, publish = self.transmitted(doc, "test_send", fake, "token-expired")
		self.assertEqual((transmission.status, doc.transmission_in_progress), ("Fehlgeschlagen", 0))
		self.assertIn("certificate", transmission.messages[-1].text)
		self.assertEqual(fake.runs, [])
		self.assertEqual(publish.call_args.args[1]["status"], "Fehlgeschlagen")

	def test_a_missing_library_ends_in_a_failed_transmission_that_names_it(self):
		doc = self.calculated(1)
		fake = FakeEric(error=transmission_adapter.TransmissionUnavailable("steuerbote.eric.service"))
		transmission, _ = self.transmitted(doc, "validate", fake)
		self.assertEqual((transmission.status, doc.transmission_in_progress), ("Fehlgeschlagen", 0))
		self.assertIn("steuerbote.eric.service", transmission.messages[-1].text)
		self.assertEqual((doc.docstatus, doc.status), (0, "Bereit"))

	def test_a_rejected_send_keeps_the_return_a_draft_with_the_messages(self):
		self.use_runtime()
		doc = self.calculated(5)
		error = Message("610101210", "Die Steuernummer ist ungültig.", "error", "Steuernummer")
		fake = FakeEric(ok=False, messages=(error,))
		transmission, _ = self.transmitted(doc, "send", fake, self.stash(fake))
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (0, "Bereit", 0))
		self.assertEqual((transmission.status, transmission.transferticket), ("Fehlgeschlagen", None))
		self.assertEqual(
			[(row.code, row.severity, row.text, row.field) for row in transmission.messages],
			[("610101210", "error", "Die Steuernummer ist ungültig.", "Steuernummer")],
		)

	def test_a_sent_return_that_could_not_be_submitted_is_never_sent_again(self):
		self.use_runtime()
		doc = self.calculated(6)
		fake = FakeEric()
		with patch.object(VATReturn, "before_submit", side_effect=frappe.ValidationError("Kaputt")):
			transmission, _ = self.transmitted(doc, "send", fake, self.stash(fake))
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (0, "Bereit", 0))
		self.assertEqual((transmission.status, transmission.transferticket), ("Erfolgreich", TICKET))
		self.assertEqual(transmission.messages[-1].severity, "error")
		self.assertIn(TICKET, transmission.messages[-1].text)
		self.assertIn("Kaputt", transmission.messages[-1].text)
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(frappe.ValidationError, "transmitted already"):
				doc.transmit("send", self.stash(fake))
			with self.assertRaisesRegex(frappe.ValidationError, "transmitted already"):
				self.calculated(6).transmit("send", self.stash(fake))
		enqueue.assert_not_called()

	def test_a_corrected_return_replaces_the_return_sent_before(self):
		self.use_runtime()
		first = self.calculated(7)
		fake = FakeEric()
		self.transmitted(first, "send", fake, self.stash(fake))
		correction = self.calculated(7, is_correction=1)
		self.transmitted(correction, "send", fake, self.stash(fake))
		first.reload()
		self.assertEqual((first.status, correction.docstatus, correction.status), ("Ersetzt", 1, "Abgegeben"))

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

	def test_a_transmission_whose_job_is_gone_is_closed_with_an_unknown_result(self):
		doc = self.calculated(8)
		first, _ = self.transmit(doc, "validate")
		with patch("steuerbote.steuerbote.doctype.vat_return.vat_return.is_job_enqueued", return_value=False):
			second, enqueue = self.transmit(doc, "validate")
		enqueue.assert_called_once()
		stale = frappe.get_doc(TRANSMISSION, first)
		self.assertEqual(stale.status, "Fehlgeschlagen")
		self.assertTrue(stale.finished_at)
		self.assertIn("Mein ELSTER", stale.messages[-1].text)
		self.assertEqual(frappe.db.get_value(TRANSMISSION, second, "status"), "Läuft")

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
		transmission, _ = self.transmitted(doc, "validate", FakeEric())
		transmission.transferticket = "et-geaendert"
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be changed"):
			transmission.save()
		with self.assertRaises(frappe.LinkExistsError):
			frappe.delete_doc("VAT Return", doc.name)
		frappe.delete_doc(TRANSMISSION, transmission.name)
		self.assertFalse(frappe.db.exists(TRANSMISSION, transmission.name))

	def test_stashing_keeps_certificate_and_password_behind_a_token(self):
		fake = FakeEric()
		encoded = base64.b64encode(CERTIFICATE).decode()
		with fake.patch():
			token = stash_certificate(encoded, PIN)
			self.assertEqual(fake.secrets[token], (CERTIFICATE, PIN))
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
		self.assertEqual(len(fake.secrets), 1)

	def test_the_form_learns_whether_eric_is_simulated(self):
		doc = self.new_return(3)
		doc.run_method("onload")
		self.assertEqual(doc.get_onload("elster"), {"simulation": True})
		self.use_runtime()
		doc.run_method("onload")
		self.assertEqual(doc.get_onload("elster"), {"simulation": False})
