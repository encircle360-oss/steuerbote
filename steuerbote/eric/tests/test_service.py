import hashlib
import shutil
import tempfile
import time
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase

from steuerbote.eric import service
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import ERROR, TESTMERKER, Operation, Outcome
from steuerbote.eric.runtime import RuntimeInfo, install_from_archive
from steuerbote.eric.service import WorkerError, WorkerOutput, library_versions, run
from steuerbote.eric.tests import stub

NUTZDATEN = (
	'<Anmeldungssteuern xmlns="http://finkonsens.de/elster/elsteranmeldung/ustva/v2026" version="2026">'
	"<Steuerfall><Umsatzsteuervoranmeldung><Jahr>2026</Jahr><Zeitraum>10</Zeitraum>"
	"<Kz83>95.00</Kz83>{marker}</Umsatzsteuervoranmeldung></Steuerfall></Anmeldungssteuern>"
)
HEADER = EnvelopeHeader(
	hersteller_id="12345",
	datenlieferant="Beispiel GmbH",
	produkt_name="Steuerbote",
	produkt_version="0.1.0",
	empfaenger_finanzamt="9198",
	datenart_version="UStVA_2026",
	testmerker=None,
	nutzdaten_ticket="1",
)
TEST_HEADER = replace(HEADER, testmerker=TESTMERKER)
CONTAINER = b"\x30\x82\x01\x00fake\x00pkcs12"
PIN = "123456"


def nutzdaten(marker: str = "") -> str:
	return NUTZDATEN.format(marker=f"<!-- {marker} -->" if marker else "")


class ServiceTestCase(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-service-"))
		cls.addClassCleanup(shutil.rmtree, cls.directory)
		cls.lib_dir = stub.install(cls.directory)
		cls.runtime = RuntimeInfo("44.3.6.0", cls.lib_dir, cls.lib_dir, cls.directory / "log", "12345")

	def codes(self, result) -> list[str]:
		return [message.code for message in result.messages]


class SimulationDispatchTest(ServiceTestCase):
	def test_without_a_runtime_the_simulation_answers(self):
		result = run(Operation.VALIDATE, nutzdaten(), HEADER, None, None, None)
		self.assertTrue(result.simulated)
		self.assertIs(result.outcome, Outcome.VALID)

	def test_the_simulation_needs_neither_certificate_nor_pin(self):
		result = run(Operation.TEST_SEND, nutzdaten(), TEST_HEADER, None, None, None)
		self.assertTrue(result.simulated)
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertTrue(result.transferticket.startswith("SIM-"))


class WorkerDispatchTest(ServiceTestCase):
	def test_with_a_runtime_the_worker_validates(self):
		result = run(Operation.VALIDATE, nutzdaten(), HEADER, self.runtime, None, None)
		self.assertFalse(result.simulated)
		self.assertIs(result.outcome, Outcome.VALID)
		self.assertEqual(result.eric_version, "44.3.6.0")
		self.assertIsNotNone(result.protocol_pdf)

	def test_with_a_runtime_the_worker_sends(self):
		result = run(Operation.TEST_SEND, nutzdaten(), TEST_HEADER, self.runtime, CONTAINER, PIN)
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertEqual(result.transferticket, "et0stub0accepted0000000000000001")
		self.assertEqual(result.testmerker, TESTMERKER)

	def test_sending_with_eric_needs_certificate_and_pin(self):
		for certificate, pin in ((None, PIN), (CONTAINER, None)):
			with self.subTest(certificate=certificate, pin=pin), self.assertRaises(ValueError):
				run(Operation.SEND, nutzdaten(), HEADER, self.runtime, certificate, pin)

	def test_refuses_a_pin_eric_would_never_accept(self):
		for pin in ("12345", "x" * 129, "123456ä", "123\t456"):
			with self.subTest(pin=pin):
				result = run(Operation.SEND, nutzdaten(), HEADER, self.runtime, CONTAINER, pin)
				self.assertIs(result.outcome, Outcome.FAILED)
				self.assertEqual(self.codes(result), ["SB-PIN"])
				self.assertNotIn(pin, result.messages[0].text)

	def test_refuses_a_header_without_the_own_hersteller_id(self):
		result = run(
			Operation.VALIDATE, nutzdaten(), replace(HEADER, hersteller_id="74931"), self.runtime, None, None
		)
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.codes(result), ["SB-HEADER"])


class LostWorkerTest(ServiceTestCase):
	def test_a_send_that_takes_too_long_is_ended_and_its_outcome_unknown(self):
		started = time.monotonic()
		result = run(
			Operation.SEND, nutzdaten("STUB-SLEEP"), HEADER, self.runtime, CONTAINER, PIN, timeout_seconds=3
		)
		self.assertLess(time.monotonic() - started, 20)
		self.assertIs(result.outcome, Outcome.UNKNOWN)
		self.assertEqual(self.codes(result), ["SB-WORKER", "SB-UNKNOWN"])
		self.assertIn("3 Sekunden", result.messages[0].text)

	def test_a_check_that_takes_too_long_fails(self):
		result = run(
			Operation.VALIDATE, nutzdaten("STUB-SLEEP"), HEADER, self.runtime, None, None, timeout_seconds=3
		)
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.codes(result), ["SB-WORKER"])

	def test_a_crash_during_a_send_leaves_the_outcome_unknown(self):
		result = run(Operation.TEST_SEND, nutzdaten("STUB-ABORT"), TEST_HEADER, self.runtime, CONTAINER, PIN)
		self.assertIs(result.outcome, Outcome.UNKNOWN)
		self.assertEqual(result.testmerker, TESTMERKER)
		self.assertEqual(self.codes(result), ["SB-WORKER", "SB-UNKNOWN"])
		self.assertIn("SIGABRT", result.messages[0].text)

	def test_a_crash_during_a_check_fails(self):
		result = run(Operation.VALIDATE, nutzdaten("STUB-ABORT"), HEADER, self.runtime, None, None)
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertIn("SIGABRT", result.messages[0].text)


class OutputTest(TestCase):
	def interpret(self, output: WorkerOutput, operation: Operation = Operation.SEND):
		return service.interpret(output, operation, "44.3.6.0")

	def test_a_request_the_worker_did_not_understand_sent_nothing(self):
		result = self.interpret(WorkerOutput(2, b"", "steuerbote.eric.worker: invalid request: header\n"))
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertIn("header", result.messages[0].text)

	def test_an_unexpected_error_during_a_send_leaves_the_outcome_unknown(self):
		result = self.interpret(WorkerOutput(1, b"", "steuerbote.eric.worker: unexpected KeyError\n"))
		self.assertIs(result.outcome, Outcome.UNKNOWN)
		self.assertIn("KeyError", result.messages[0].text)
		self.assertEqual(result.messages[0].severity, ERROR)

	def test_an_answer_that_is_no_result_counts_as_lost(self):
		for stdout in (b"", b"{", b"[]", b'{"ok": true}'):
			with self.subTest(stdout=stdout):
				self.assertIs(self.interpret(WorkerOutput(0, stdout, "")).outcome, Outcome.UNKNOWN)
				self.assertIs(
					self.interpret(WorkerOutput(0, stdout, ""), Operation.VALIDATE).outcome, Outcome.FAILED
				)

	def test_keeps_only_the_end_of_a_long_error_output(self):
		result = self.interpret(WorkerOutput(1, b"", "x" * 5000 + "Ende"))
		self.assertTrue(result.messages[0].text.endswith("Ende"))
		self.assertLess(len(result.messages[0].text), service.STDERR_LIMIT + 200)


class VersionTest(ServiceTestCase):
	def test_reads_the_versions_of_the_libraries(self):
		self.assertEqual(
			library_versions(self.runtime),
			{"libericapi.so": "44, 3, 6, 0", "libcheckUStVA_2026.so": "44, 3, 6, 0"},
		)

	def test_a_runtime_that_does_not_load_is_an_error(self):
		with self.assertRaises(WorkerError) as raised:
			library_versions(replace(self.runtime, lib_dir=self.directory / "nowhere"))
		self.assertIn("libericapi.so", str(raised.exception))

	def test_a_worker_that_does_not_answer_is_an_error(self):
		with self.assertRaises(WorkerError) as raised:
			library_versions(replace(self.runtime, version=""), timeout_seconds=0)
		self.assertIn("0 Sekunden", str(raised.exception))

	def test_probes_an_installation_with_the_worker(self):
		archive = self.directory / "ERiC-44.3.6.0-Linux-x86_64.jar"
		lib = "ERiC-44.3.6.0/Linux-x86_64/lib"
		with zipfile.ZipFile(archive, "w") as jar:
			jar.write(stub.library(), f"{lib}/libericapi.so")
			jar.writestr(f"{lib}/plugins2/libcommonData.so", b"")
			jar.writestr(f"{lib}/plugins2/libcheckUStVA_2026.so", b"")
		checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
		info = install_from_archive(archive, checksum, self.directory / "eric", probe=library_versions)
		self.assertTrue((info.lib_dir / "libericapi.so").is_file())
