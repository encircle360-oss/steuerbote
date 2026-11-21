import base64
import ctypes
import io
import json
import resource
import runpy
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
from unittest import TestCase, mock

from steuerbote.elster.tests import zm_examples
from steuerbote.eric import worker
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.proxy import Proxy
from steuerbote.eric.result import ERROR, HINT, TESTMERKER, Operation, Outcome, TransmissionResult
from steuerbote.eric.runtime import RuntimeInfo
from steuerbote.eric.tests import stub

NUTZDATEN = (
	'<Anmeldungssteuern xmlns="http://finkonsens.de/elster/elsteranmeldung/ustva/v2026" version="2026">'
	"<Steuerfall><Umsatzsteuervoranmeldung><Jahr>2026</Jahr><Zeitraum>10</Zeitraum>"
	"<Kz83>95.00</Kz83>{marker}</Umsatzsteuervoranmeldung></Steuerfall></Anmeldungssteuern>"
)
HEADER = EnvelopeHeader(
	hersteller_id="12345",
	datenlieferant="Beispiel GmbH & Co. KG; Erika Beispiel",
	produkt_name="Steuerbote",
	produkt_version="0.1.0",
	empfaenger="9198",
	datenart_version="UStVA_2026",
	testmerker=None,
	nutzdaten_ticket="1",
)
# The Zusammenfassende Meldung goes to the Länderkürzel BF in the datenartVersion ZMDO (steuerbote.eric.datenart).
ZM_HEADER = replace(HEADER, empfaenger="BF", datenart_version="ZMDO")
CONTAINER = b"\x30\x82\x01\x00fake\x00pkcs12\x00container"
PIN = "Geheim-PIN-4711"
# The password of the proxy, invented.
PROXY_GEHEIM = "Proxy-Geheim-4711"
PROXY = Proxy("proxy.example.com", 3128, "steuerbote", PROXY_GEHEIM)
APP_ROOT = Path(worker.__file__).resolve().parents[2]


def nutzdaten(marker: str = "") -> str:
	return NUTZDATEN.format(marker=f"<!-- {marker} -->" if marker else "")


class WorkerTestCase(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-worker-"))
		cls.addClassCleanup(shutil.rmtree, cls.directory)
		cls.lib_dir = stub.install(cls.directory)
		cls.runtime = RuntimeInfo(
			"44.3.6.0", cls.lib_dir, cls.lib_dir, cls.directory / "log" / "run-1", "12345"
		)
		cls.stub = stub.Controls(cls.lib_dir)

	def setUp(self):
		self.stub.reset()

	def request(self, operation: Operation, marker: str = "", **changes) -> dict:
		header = HEADER if operation is not Operation.TEST_SEND else replace(HEADER, testmerker=TESTMERKER)
		request = {
			"command": "process",
			"operation": operation.value,
			"nutzdaten": nutzdaten(marker),
			"header": asdict(header),
			"runtime": self.runtime.to_dict(),
			"certificate_secret": (
				None if operation is Operation.VALIDATE else base64.b64encode(CONTAINER).decode()
			),
			"certificate_password": None if operation is Operation.VALIDATE else PIN,
		}
		return request | changes

	def serve(self, request: object) -> tuple[int, bytes, str]:
		stdin = io.BytesIO(request if isinstance(request, bytes) else json.dumps(request).encode())
		stdout, stderr = io.BytesIO(), io.StringIO()
		code = worker.serve(stdin, stdout, stderr)
		return code, stdout.getvalue(), stderr.getvalue()

	def run_operation(self, operation: Operation, marker: str = "", **changes) -> TransmissionResult:
		code, stdout, stderr = self.serve(self.request(operation, marker, **changes))
		self.assertEqual((code, stderr), (0, ""))
		self.assertEqual(self.stub.open_certificates, 0)
		self.assertFalse(self.stub.initialised)
		return TransmissionResult.from_dict(json.loads(stdout))

	def messages(self, result: TransmissionResult) -> list[tuple[str, str, str | None]]:
		return [(message.code, message.severity, message.field) for message in result.messages]


class ValidateTest(WorkerTestCase):
	def test_validates_with_hints_and_a_preview(self):
		result = self.run_operation(Operation.VALIDATE)
		self.assertIs(result.outcome, Outcome.VALID)
		self.assertFalse(result.simulated)
		self.assertEqual(result.eric_version, "44.3.6.0")
		self.assertIsNone(result.transferticket)
		self.assertIsNone(result.server_response_xml)
		self.assertEqual(len(result.protocol_pdf), self.stub.pdf_size)
		self.assertEqual(self.stub.recorded("flags"), "162")
		self.assertEqual(self.stub.recorded("vorschau"), "1")
		self.assertEqual(self.stub.recorded("crypto_version"), "-1")
		self.assertIsNone(self.stub.recorded("container_size"))

	def test_sets_the_timeouts_and_the_number_of_messages(self):
		self.run_operation(Operation.VALIDATE)
		for name, value in (
			("transfer.connect_timeout", "30"),
			("transfer.response_timeout", "60"),
			("validieren.fehler_max", "100"),
			("validieren.hinweise_max", "100"),
		):
			with self.subTest(setting=name):
				self.assertEqual(self.stub.recorded(f"setting:{name}"), value)

	def test_sets_no_proxy_without_one(self):
		self.run_operation(Operation.VALIDATE)
		for name in ("http.proxy_host", "http.proxy_port", "http.proxy_username", "http.proxy_password"):
			with self.subTest(setting=name):
				self.assertIsNone(self.stub.recorded(f"setting:{name}"))

	def test_lets_eric_write_the_transfer_header_around_the_datenteil(self):
		self.run_operation(Operation.VALIDATE)
		self.assertEqual(self.stub.recorded("th_verfahren"), "ElsterAnmeldung")
		self.assertEqual(self.stub.recorded("th_datenart"), "UStVA")
		self.assertEqual(self.stub.recorded("th_vorgang"), "send-Auth")
		self.assertEqual(self.stub.recorded("th_testmerker"), "<NULL>")
		self.assertEqual(self.stub.recorded("th_hersteller_id"), "12345")
		self.assertEqual(self.stub.recorded("th_datenlieferant"), HEADER.datenlieferant)
		self.assertIn(f"<Nutzdaten>{nutzdaten()}</Nutzdaten>", self.stub.recorded("datenpuffer"))
		self.assertIn('<Empfaenger id="F">9198</Empfaenger>', self.stub.recorded("datenpuffer"))
		self.assertEqual(self.stub.recorded("datenart_version"), "UStVA_2026")

	def test_initialises_with_the_runtime_and_its_log_directory(self):
		self.run_operation(Operation.VALIDATE)
		self.assertEqual(self.stub.recorded("plugin_path"), str(self.lib_dir))
		self.assertEqual(self.stub.recorded("log_path"), str(self.runtime.log_dir))
		self.assertTrue((self.runtime.log_dir / "eric.log").is_file())
		self.assertEqual(self.runtime.log_dir.stat().st_mode & 0o777, 0o700)

	def test_hints_keep_the_data_valid(self):
		result = self.run_operation(Operation.VALIDATE, "STUB-HINWEIS")
		self.assertIs(result.outcome, Outcome.VALID)
		self.assertEqual(self.messages(result), [("610001003", HINT, None), ("11085155", HINT, "Kz26")])
		self.assertEqual(result.messages[1].text, "Bitte prüfen Sie die Kennzahl 26.")
		self.assertIsNotNone(result.protocol_pdf)

	def test_rule_errors_make_the_data_invalid(self):
		result = self.run_operation(Operation.VALIDATE, "STUB-PRUEF-FEHLER")
		self.assertIs(result.outcome, Outcome.INVALID)
		self.assertEqual(
			self.messages(result),
			[
				("610001002", ERROR, None),
				("110085064", ERROR, "Kz83"),
				("stubRegelOhneId", ERROR, None),
				("11085155", HINT, "Kz26"),
			],
		)
		self.assertEqual(result.messages[1].text, "Die Kennzahl 83 muss angegeben werden.")

	def test_an_unreadable_return_buffer_still_fails_with_the_code(self):
		result = self.run_operation(Operation.VALIDATE, "STUB-BROKEN-RETURN")
		self.assertIs(result.outcome, Outcome.INVALID)
		self.assertEqual(self.messages(result), [("610001002", ERROR, None), ("SB-ERIC", ERROR, None)])

	def test_other_codes_fail_with_their_text(self):
		result = self.run_operation(Operation.VALIDATE, "STUB-SCHEMA")
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.messages(result), [("610301200", ERROR, None)])
		self.assertEqual(result.messages[0].text, "Es traten Fehler beim Validieren des XML auf.")

	def test_an_error_while_printing_the_preview_fails_the_check(self):
		result = self.run_operation(Operation.VALIDATE, "STUB-PRINT-ERROR")
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.messages(result), [("610501010", ERROR, None)])
		self.assertIsNone(result.protocol_pdf)


class SendTest(WorkerTestCase):
	def test_a_test_send_is_accepted_with_the_ticket_of_the_server(self):
		result = self.run_operation(Operation.TEST_SEND)
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertEqual(result.transferticket, "et0stub0accepted0000000000000001")
		self.assertEqual(result.testmerker, TESTMERKER)
		self.assertIn("<TransferTicket>", result.server_response_xml)
		self.assertEqual(len(result.protocol_pdf), self.stub.pdf_size)
		self.assertEqual(self.messages(result), [("0", HINT, "TransferHeader")])
		self.assertEqual(result.messages[0].text, "Daten wurden erfolgreich angenommen.")
		self.assertEqual(self.stub.recorded("th_testmerker"), TESTMERKER)
		self.assertEqual(self.stub.recorded("flags"), "38")
		self.assertEqual(self.stub.recorded("vorschau"), "0")

	def test_opens_the_certificate_from_memory_and_signs_with_the_pin(self):
		self.run_operation(Operation.SEND)
		self.assertEqual(self.stub.recorded("container_size"), str(len(CONTAINER)))
		self.assertEqual(self.stub.recorded("container_sum"), str(sum(CONTAINER)))
		self.assertEqual(self.stub.recorded("open_password"), PIN)
		self.assertEqual(self.stub.recorded("pin"), PIN)
		self.assertEqual(self.stub.recorded("crypto_version"), "3")
		self.assertEqual(self.stub.recorded("closed_handle"), "4711")

	def test_a_real_send_has_no_testmerker(self):
		result = self.run_operation(Operation.SEND)
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertIsNone(result.testmerker)
		self.assertEqual(self.stub.recorded("th_testmerker"), "<NULL>")

	def test_rule_errors_stop_a_send_before_it_leaves(self):
		result = self.run_operation(Operation.SEND, "STUB-PRUEF-FEHLER")
		self.assertIs(result.outcome, Outcome.INVALID)
		self.assertIsNone(result.transferticket)
		self.assertIsNone(result.protocol_pdf)

	def test_a_rejection_in_the_transfer_header(self):
		result = self.run_operation(Operation.SEND, "STUB-THEADER")
		self.assertIs(result.outcome, Outcome.REJECTED)
		self.assertEqual(result.transferticket, "et0stub0rejected0000000000000002")
		self.assertEqual(
			self.messages(result), [("610101210", ERROR, None), ("301100005", ERROR, "TransferHeader")]
		)
		self.assertEqual(result.messages[1].text, "Stub: Die Daten wurden nicht angenommen.")

	def test_a_rejection_in_the_nutzdaten_header(self):
		result = self.run_operation(Operation.SEND, "STUB-NHEADER")
		self.assertIs(result.outcome, Outcome.REJECTED)
		self.assertEqual(
			self.messages(result), [("610101292", ERROR, None), ("200100007", ERROR, "NutzdatenHeader")]
		)
		self.assertEqual(result.messages[1].text, "Stub: Die Steuernummer ist dem Finanzamt nicht bekannt.")

	def test_an_answer_that_never_came_leaves_the_outcome_unknown(self):
		for marker, code in (("STUB-TIMEOUT", "610101283"), ("STUB-NORESPONSE", "610101279")):
			with self.subTest(marker=marker):
				result = self.run_operation(Operation.SEND, marker)
				self.assertIs(result.outcome, Outcome.UNKNOWN)
				self.assertIsNone(result.transferticket)
				self.assertEqual(self.messages(result), [(code, ERROR, None), ("SB-UNKNOWN", ERROR, None)])
				self.assertIn("Nicht erneut senden", result.messages[1].text)

	def test_a_timeout_keeps_the_ticket_the_answer_of_the_server_still_holds(self):
		result = self.run_operation(Operation.SEND, "STUB-TIMEOUT-ANSWER")
		self.assertIs(result.outcome, Outcome.UNKNOWN)
		self.assertEqual(result.transferticket, "et0stub0timedout0000000000000004")
		self.assertIn("<TransferTicket>et0stub0timedout", result.server_response_xml)
		self.assertEqual(
			self.messages(result),
			[("610101283", ERROR, None), ("301100006", ERROR, "TransferHeader"), ("SB-UNKNOWN", ERROR, None)],
		)
		self.assertEqual(result.messages[1].text, "Stub: Zeitüberschreitung beim Speichern der Daten.")

	def test_an_error_after_the_transfer_leaves_the_outcome_unknown_with_the_ticket(self):
		result = self.run_operation(Operation.TEST_SEND, "STUB-PRINT-ERROR")
		self.assertIs(result.outcome, Outcome.UNKNOWN)
		self.assertEqual(result.transferticket, "et0stub0accepted0000000000000001")
		self.assertEqual(result.testmerker, TESTMERKER)
		self.assertIn("<TransferTicket>", result.server_response_xml)
		self.assertIsNone(result.protocol_pdf)
		self.assertEqual(
			self.messages(result),
			[("610501010", ERROR, None), ("0", HINT, "TransferHeader"), ("SB-UNKNOWN", ERROR, None)],
		)
		self.assertEqual(
			result.messages[0].text, "Während der Ausgabe der Inhalte ist ein Fehler aufgetreten."
		)

	def test_no_connection_means_nothing_was_sent(self):
		result = self.run_operation(Operation.SEND, "STUB-CONNECT")
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.messages(result), [("610101278", ERROR, None)])
		self.assertIsNone(result.server_response_xml)

	def test_an_accepted_send_without_a_ticket_says_so(self):
		result = self.run_operation(Operation.SEND, "STUB-NO-TICKET")
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertIsNone(result.transferticket)
		self.assertIn(("SB-TICKET", HINT, None), self.messages(result))

	def test_an_unreadable_server_answer_keeps_the_acceptance(self):
		result = self.run_operation(Operation.SEND, "STUB-UNREADABLE-ANSWER")
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertIsNone(result.transferticket)
		self.assertEqual(result.server_response_xml, "Stub: keine XML-Antwort")
		self.assertEqual(self.messages(result), [("SB-TICKET", HINT, None)])

	def test_a_wrong_pin_fails_before_anything_is_sent(self):
		result = self.run_operation(Operation.SEND, certificate_password=stub.WRONG_PIN)
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.messages(result), [("610201106", ERROR, None)])
		self.assertIsNone(self.stub.recorded("datenpuffer"))

	def test_never_writes_certificate_or_password(self):
		code, stdout, stderr = self.serve(self.request(Operation.SEND, proxy=PROXY.to_dict()))
		self.assertEqual(code, 0)
		for secret in (PIN.encode(), base64.b64encode(CONTAINER), b"pkcs12", PROXY_GEHEIM.encode()):
			self.assertNotIn(secret, stdout)
			self.assertNotIn(secret.decode(), stderr)

	def test_sends_through_the_proxy_of_the_request(self):
		"""Kap. 6.2.4, step 2: „Falls ein Proxy verwendet wird, müssen die Proxy-Parameter mit
		EricEinstellungSetzen() gesetzt werden“, with the names of Tabelle 4-2."""
		result = self.run_operation(Operation.TEST_SEND, proxy=PROXY.to_dict())
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		for name, value in (
			("http.proxy_host", "proxy.example.com"),
			("http.proxy_port", "3128"),
			("http.proxy_username", "steuerbote"),
			("http.proxy_password", PROXY_GEHEIM),
		):
			with self.subTest(setting=name):
				self.assertEqual(self.stub.recorded(f"setting:{name}"), value)

	def test_a_socks_proxy_names_its_protocol_and_no_user(self):
		self.run_operation(Operation.SEND, proxy=Proxy("socks5://10.0.0.1", 1080).to_dict())
		self.assertEqual(self.stub.recorded("setting:http.proxy_host"), "socks5://10.0.0.1")
		self.assertEqual(self.stub.recorded("setting:http.proxy_port"), "1080")
		self.assertIsNone(self.stub.recorded("setting:http.proxy_username"))


class ZmdoTest(WorkerTestCase):
	"""The Zusammenfassende Meldung takes the calls of the UStVA with the parameters of its Datenart ZMDO: Verfahren
	ElsterExtern, send-Auth and the recipient BF (ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 8-28), the
	datenartVersion ZMDO with the plugin checkZMDO (Datenartversionmatrix.ods)."""

	def run_zm(self, operation: Operation) -> TransmissionResult:
		header = (
			ZM_HEADER if operation is not Operation.TEST_SEND else replace(ZM_HEADER, testmerker=TESTMERKER)
		)
		return self.run_operation(operation, header=asdict(header), nutzdaten=zm_examples.nutzdaten())

	def test_lets_eric_write_the_transfer_header_of_zmdo_around_the_datenteil(self):
		for operation in Operation:
			with self.subTest(operation=operation):
				self.stub.reset()
				result = self.run_zm(operation)
				self.assertTrue(result.ok)
				self.assertEqual(
					[self.stub.recorded(f"th_{name}") for name in ("verfahren", "datenart", "vorgang")],
					["ElsterExtern", "ZMDO", "send-Auth"],
				)
				self.assertEqual(self.stub.recorded("datenart_version"), "ZMDO")
				delivered = self.stub.recorded("datenpuffer")
				self.assertIn('<Empfaenger id="L">BF</Empfaenger>', delivered)
				self.assertIn(f"<Nutzdaten>{zm_examples.nutzdaten()}</Nutzdaten>", delivered)

	def test_a_send_of_the_zm_is_accepted_with_the_ticket_of_the_server(self):
		result = self.run_zm(Operation.SEND)
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertTrue(result.transferticket)
		self.assertEqual(self.stub.recorded("th_testmerker"), "<NULL>")

	def test_without_the_plugin_check_zmdo_eric_knows_no_zmdo(self):
		plugin = self.lib_dir / "plugins2" / "libcheckZMDO.so"
		plugin.unlink()
		self.addCleanup(plugin.write_bytes, b"")
		result = self.run_zm(Operation.VALIDATE)
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(result.messages[0].code, "610001042")


class FailureTest(WorkerTestCase):
	def test_a_missing_library_fails_before_anything_is_sent(self):
		runtime = replace(self.runtime, lib_dir=self.directory / "nowhere")
		result = self.run_operation(Operation.SEND, runtime=runtime.to_dict())
		self.assertIs(result.outcome, Outcome.FAILED)
		(message,) = result.messages
		self.assertEqual(message.code, "SB-ERIC")
		self.assertIn("libericapi.so", message.text)

	def test_an_initialisation_eric_refuses(self):
		ctypes.CDLL(str(self.lib_dir / "libericapi.so")).EricInitialisiere(None, None)
		code, stdout, _ = self.serve(self.request(Operation.VALIDATE))
		self.assertEqual(code, 0)
		result = TransmissionResult.from_dict(json.loads(stdout))
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.messages(result), [("610001082", ERROR, None)])
		self.assertIsNone(self.stub.recorded("th_input"))

	def test_an_error_while_preparing_sends_nothing(self):
		self.stub.fail_buffer()
		result = self.run_operation(Operation.SEND)
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.messages(result), [("610001013", ERROR, None)])
		self.assertIsNone(self.stub.recorded("datenpuffer"))

	def test_a_buffer_eric_cannot_create_for_the_send_sends_nothing(self):
		self.stub.fail_buffer(after=1)
		result = self.run_operation(Operation.SEND)
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.messages(result), [("610001013", ERROR, None)])
		self.assertIsNotNone(self.stub.recorded("th_input"))
		self.assertIsNone(self.stub.recorded("datenpuffer"))

	def test_a_header_out_of_shape_never_reaches_eric(self):
		header = asdict(replace(HEADER, hersteller_id="74931"))
		result = self.run_operation(Operation.SEND, header=header)
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.messages(result), [("SB-HEADER", ERROR, "HerstellerID")])
		self.assertIsNone(self.stub.recorded("plugin_path"))

	def test_the_hersteller_id_must_be_the_one_of_the_runtime(self):
		runtime = replace(self.runtime, hersteller_id="54321")
		result = self.run_operation(Operation.VALIDATE, runtime=runtime.to_dict())
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.messages(result), [("SB-HEADER", ERROR, "HerstellerID")])

	def test_a_log_directory_that_cannot_be_created_sends_nothing(self):
		blocker = self.directory / "file"
		blocker.write_text("")
		runtime = replace(self.runtime, log_dir=blocker / "log")
		result = self.run_operation(Operation.SEND, runtime=runtime.to_dict())
		self.assertIs(result.outcome, Outcome.FAILED)
		(message,) = result.messages
		self.assertEqual(message.code, "SB-ERIC")
		self.assertIn(str(blocker / "log"), message.text)
		self.assertIsNone(self.stub.recorded("plugin_path"))


class ProtocolTest(WorkerTestCase):
	def test_refuses_requests_it_does_not_understand_without_echoing_them(self):
		valid = self.request(Operation.SEND)
		broken = {
			"no json": b"{" + PIN.encode(),
			"no object": [],
			"unknown command": valid | {"command": "print"},
			"unknown operation": valid | {"operation": "file"},
			"nutzdaten": valid | {"nutzdaten": 83},
			"header": valid | {"header": ["12345"]},
			"header fields": valid | {"header": {"hersteller_id": "12345"}},
			"header field": valid | {"header": asdict(HEADER) | {"testmerker": 700000004}},
			"runtime": valid | {"runtime": {"version": "44.3.6.0"}},
			"certificate": valid | {"certificate_secret": "kein base64!"},
			"no certificate": valid | {"certificate_secret": None},
			"no password": valid | {"certificate_password": None},
			"password": valid | {"certificate_password": 4711},
			"proxy": valid | {"proxy": ["proxy.example.com", 3128]},
			"proxy port": valid | {"proxy": PROXY.to_dict() | {"port": "3128"}},
		}
		for case, request in broken.items():
			with self.subTest(case):
				code, stdout, stderr = self.serve(request)
				self.assertEqual(code, worker.EXIT_INVALID_REQUEST)
				self.assertEqual(stdout, b"")
				self.assertTrue(stderr.startswith("steuerbote.eric.worker: invalid request:"))
				self.assertNotIn(PIN, stderr)

	def test_names_only_the_type_of_an_unexpected_error(self):
		with mock.patch.object(worker, "process", side_effect=ValueError(PIN)):
			code, stdout, stderr = self.serve(self.request(Operation.SEND))
		self.assertEqual((code, stdout), (worker.EXIT_FAILURE, b""))
		self.assertEqual(stderr, "steuerbote.eric.worker: unexpected ValueError\n")

	def test_reports_the_versions_of_the_libraries(self):
		code, stdout, _ = self.serve({"command": "version", "runtime": self.runtime.to_dict()})
		self.assertEqual(code, 0)
		self.assertEqual(
			json.loads(stdout),
			{"libraries": {"libericapi.so": "44, 3, 6, 0", "libcheckUStVA_2026.so": "44, 3, 6, 0"}},
		)
		self.assertFalse(self.stub.initialised)

	def test_reports_why_the_versions_are_missing(self):
		runtime = replace(self.runtime, lib_dir=self.directory / "nowhere")
		code, stdout, _ = self.serve({"command": "version", "runtime": runtime.to_dict()})
		self.assertEqual(code, 0)
		self.assertIn("libericapi.so", json.loads(stdout)["error"])
		library = ctypes.CDLL(str(self.lib_dir / "libericapi.so"))
		library.EricInitialisiere(None, None)
		code, stdout, _ = self.serve({"command": "version", "runtime": self.runtime.to_dict()})
		self.assertIn("610001082", json.loads(stdout)["error"])


class OutcomeTest(TestCase):
	"""What a return code of EricBearbeiteVorgang means for a check and for a send."""

	def test_a_send_fails_only_for_a_code_before_the_transfer(self):
		for operation in (Operation.SEND, Operation.TEST_SEND):
			for code in worker.BEFORE_TRANSFER:
				with self.subTest(operation=operation, code=code):
					self.assertIs(
						worker.outcome(operation, code, server_answered=False),
						Outcome.INVALID if code == 610001002 else Outcome.FAILED,
					)

	def test_every_other_code_leaves_a_send_unknown(self):
		after_or_anywhere = {
			610501001: "PRINT_INTERNER_FEHLER",
			610501004: "PRINT_UNGUELTIGER_DATEI_PFAD",
			610501010: "PRINT_ABBRUCH_GENERIERUNG",
			610501015: "PRINT_PDFCALLBACK",
			610101200: "TRANSFER_COM_ERROR",
			610101271: "TRANSFER_ERR_SEND",
			610101274: "TRANSFER_ERR_NOTENCRYPTED",
			610101279: "TRANSFER_ERR_NORESPONSE",
			610101283: "TRANSFER_ERR_TIMEOUT",
			610101291: "TRANSFER_ERR_OTHER",
			610001001: "GLOBAL_UNKNOWN",
			610001003: "GLOBAL_HINWEISE",
			610001013: "GLOBAL_NICHT_GENUEGEND_ARBEITSSPEICHER",
			610001032: "GLOBAL_INTERNER_FEHLER",
			610001045: "GLOBAL_COMMONDATA_NICHT_VERFUEGBAR",
			610001228: "GLOBAL_PLUGININITIALISIERUNG",
			610201125: "CRYPT_E_DECRYPT",
			610201200: "CRYPT_ZERTIFIKAT",
			610301001: "IO_FEHLER",
			1: "a code ERiC does not know",
		}
		for code, name in after_or_anywhere.items():
			with self.subTest(code=code, name=name):
				self.assertIs(worker.outcome(Operation.SEND, code, server_answered=False), Outcome.UNKNOWN)

	def test_an_answer_of_the_server_makes_even_a_code_before_the_transfer_unknown(self):
		for code in (610001002, 610101278, 610201106, 610301200):
			with self.subTest(code=code):
				self.assertIs(worker.outcome(Operation.SEND, code, server_answered=True), Outcome.UNKNOWN)

	def test_the_server_accepts_or_rejects(self):
		for answered in (False, True):
			self.assertIs(worker.outcome(Operation.SEND, 0, server_answered=answered), Outcome.ACCEPTED)
			for code in (610101210, 610101292):
				self.assertIs(
					worker.outcome(Operation.SEND, code, server_answered=answered), Outcome.REJECTED
				)

	def test_a_check_is_valid_invalid_or_failed(self):
		for code, expected in (
			(0, Outcome.VALID),
			(610001003, Outcome.VALID),
			(610001002, Outcome.INVALID),
			(610301200, Outcome.FAILED),
			(610501010, Outcome.FAILED),
			(610101283, Outcome.FAILED),
		):
			with self.subTest(code=code):
				self.assertIs(worker.outcome(Operation.VALIDATE, code, server_answered=False), expected)

	def test_no_code_of_printing_or_of_the_answer_counts_as_before_the_transfer(self):
		for code in worker.BEFORE_TRANSFER:
			with self.subTest(code=code):
				self.assertRegex(str(code), r"^610[0-3]\d{5}$")
		self.assertTrue(
			worker.BEFORE_TRANSFER.isdisjoint(
				{0, 610101210, 610101271, 610101274, 610101279, 610101283, 610101292}
			)
		)


class HardeningTest(TestCase):
	def setUp(self):
		limits = resource.getrlimit(resource.RLIMIT_CORE)
		self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
		self.addCleanup(worker.prctl, worker.PR_SET_DUMPABLE, 1)

	def test_makes_the_process_undumpable_without_core_files(self):
		worker.harden()
		self.assertEqual(worker.prctl(worker.PR_GET_DUMPABLE, 0), 0)
		self.assertEqual(resource.getrlimit(resource.RLIMIT_CORE)[0], 0)

	def test_a_refused_prctl_is_an_error(self):
		with self.assertRaises(OSError):
			worker.prctl(-1, 0)

	def test_runs_as_a_script_that_hardens_itself_first(self):
		request = json.dumps({"command": "version", "runtime": {}}).encode()
		stdin = io.TextIOWrapper(io.BytesIO(request))
		stdout = io.TextIOWrapper(io.BytesIO())
		with (
			mock.patch.object(sys, "stdin", stdin),
			mock.patch.object(sys, "stdout", stdout),
			mock.patch.object(sys, "stderr", io.StringIO()) as stderr,
			self.assertRaises(SystemExit) as exited,
		):
			runpy.run_path(worker.__file__, run_name="__main__")
		self.assertEqual(exited.exception.code, worker.EXIT_INVALID_REQUEST)
		self.assertEqual(stderr.getvalue(), "steuerbote.eric.worker: invalid request: runtime\n")
		self.assertEqual(worker.prctl(worker.PR_GET_DUMPABLE, 0), 0)


class SubprocessTest(WorkerTestCase):
	def test_answers_as_a_process_of_its_own(self):
		completed = subprocess.run(
			[sys.executable, "-E", "-s", "-m", "steuerbote.eric.worker"],
			input=json.dumps(self.request(Operation.VALIDATE)).encode(),
			capture_output=True,
			cwd=APP_ROOT,
			timeout=60,
			check=False,
		)
		self.assertEqual((completed.returncode, completed.stderr), (0, b""))
		result = TransmissionResult.from_dict(json.loads(completed.stdout))
		self.assertIs(result.outcome, Outcome.VALID)
		self.assertIsNotNone(result.protocol_pdf)
