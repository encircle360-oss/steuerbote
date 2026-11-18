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

from steuerbote.eric import worker
from steuerbote.eric.header import EnvelopeHeader
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
	empfaenger_finanzamt="9198",
	datenart_version="UStVA_2026",
	testmerker=None,
	nutzdaten_ticket="1",
)
CONTAINER = b"\x30\x82\x01\x00fake\x00pkcs12\x00container"
PIN = "Geheim-PIN-4711"
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
			"certificate": None if operation is Operation.VALIDATE else base64.b64encode(CONTAINER).decode(),
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

	def test_no_connection_means_nothing_was_sent(self):
		result = self.run_operation(Operation.SEND, "STUB-CONNECT")
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.messages(result), [("610101278", ERROR, None)])

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
		code, stdout, stderr = self.serve(self.request(Operation.SEND))
		self.assertEqual(code, 0)
		for secret in (PIN.encode(), base64.b64encode(CONTAINER), b"pkcs12"):
			self.assertNotIn(secret, stdout)
			self.assertNotIn(secret.decode(), stderr)


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
		self.stub.fail_next_buffer()
		result = self.run_operation(Operation.SEND)
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.messages(result), [("610001013", ERROR, None)])
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
			"certificate": valid | {"certificate": "kein base64!"},
			"no certificate": valid | {"certificate": None},
			"no password": valid | {"certificate_password": None},
			"password": valid | {"certificate_password": 4711},
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
