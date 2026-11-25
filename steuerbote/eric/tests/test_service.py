import base64
import ctypes
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, mock

from steuerbote.eric import runtime, service
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.proxy import Proxy
from steuerbote.eric.result import ERROR, TESTMERKER, Operation, Outcome
from steuerbote.eric.runtime import RuntimeInfo, install_from_archive, installations
from steuerbote.eric.service import (
	PrivacyNoticeNotConfirmed,
	WorkerError,
	WorkerOutput,
	library_versions,
	run,
	steuernummer_valid,
)
from steuerbote.eric.tests import stub
from steuerbote.eric.tests.tracebacks import frame_variables, interrupted_after

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
	empfaenger="9198",
	datenart_version="UStVA_2026",
	testmerker=None,
	nutzdaten_ticket="1",
)
TEST_HEADER = replace(HEADER, testmerker=TESTMERKER)
CONTAINER = b"\x30\x82\x01\x00fake\x00pkcs12"
PIN = "Geheim-PIN-4711"
SECRETS = (PIN, base64.b64encode(CONTAINER).decode(), "pkcs12")
# The password of the proxy, invented.
PROXY_GEHEIM = "Proxy-Geheim-4711"
PROXY = Proxy("proxy.example.com", 3128, "steuerbote", PROXY_GEHEIM)
PR_SET_CHILD_SUBREAPER = 36
# A background job that starts the worker on a send that sleeps in ERiC and then waits, as long as it is let live.
JOB = """
import json, sys, time
from pathlib import Path
from steuerbote.eric import service
from steuerbote.eric.result import Operation
from steuerbote.eric.runtime import RuntimeInfo
from steuerbote.eric.tests.test_service import CONTAINER, HEADER, PIN, nutzdaten

runtime = RuntimeInfo.from_dict(json.loads(sys.argv[1]))
request = service._process_request(
	Operation.SEND, nutzdaten("STUB-SLEEP"), HEADER, runtime, CONTAINER, PIN, work_dir=Path(sys.argv[2])
)
worker = service.start_worker()
worker.stdin.write(request)
worker.stdin.close()
print(worker.pid, flush=True)
time.sleep(60)
"""


class JobTimeout(Exception):
	"""Stands in for the exception a background job gets when it runs too long."""


class Interrupted(BaseException):
	"""An exception that no handler of steuerbote catches."""


def nutzdaten(marker: str = "") -> str:
	return NUTZDATEN.format(marker=f"<!-- {marker} -->" if marker else "")


class ServiceTestCase(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-service-"))
		cls.addClassCleanup(shutil.rmtree, cls.directory)
		cls.lib_dir = stub.install(cls.directory)
		cls.runtime = RuntimeInfo(
			"44.3.6.0",
			cls.lib_dir,
			cls.lib_dir,
			cls.directory / "log",
			"12345",
			confirmed_privacy_notice=True,
		)

	def codes(self, result) -> list[str]:
		return [message.code for message in result.messages]

	def started_workers(self) -> list[subprocess.Popen]:
		"""The worker processes the service starts during the test."""
		workers = []
		start = service.start_worker

		def recorded() -> subprocess.Popen:
			workers.append(start())
			return workers[-1]

		self.enterContext(mock.patch.object(service, "start_worker", side_effect=recorded))
		return workers


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

	def test_the_simulation_reaches_no_server_and_leaves_the_proxy_aside(self):
		workers = self.started_workers()
		result = run(Operation.TEST_SEND, nutzdaten(), TEST_HEADER, None, None, None, proxy=PROXY)
		self.assertTrue(result.simulated)
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertEqual(workers, [])


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

	def test_the_worker_sends_through_the_proxy(self):
		result = run(Operation.TEST_SEND, nutzdaten(), TEST_HEADER, self.runtime, CONTAINER, PIN, proxy=PROXY)
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertNotIn(PROXY_GEHEIM, json.dumps(result.to_dict()))

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


class SteuernummerTest(ServiceTestCase):
	"""The check of a Steuernummer with ERiC for the settings; None where it cannot say."""

	def test_checks_with_the_runtime(self):
		self.assertIs(steuernummer_valid(self.runtime, "9198011310010"), True)
		self.assertIs(steuernummer_valid(self.runtime, "9198011310019"), False)

	def test_cannot_say_without_a_runtime_or_the_confirmed_privacy_notice(self):
		workers = self.started_workers()
		self.assertIsNone(steuernummer_valid(None, "9198011310019"))
		self.assertIsNone(
			steuernummer_valid(replace(self.runtime, confirmed_privacy_notice=False), "9198011310019")
		)
		self.assertEqual(workers, [])

	def test_cannot_say_when_the_worker_fails(self):
		self.assertIsNone(
			steuernummer_valid(replace(self.runtime, lib_dir=self.directory / "nowhere"), "9198011310019")
		)
		self.assertIsNone(steuernummer_valid(self.runtime, ""))
		with mock.patch.object(service, "call_worker", side_effect=service.WorkerError("timeout")):
			self.assertIsNone(steuernummer_valid(self.runtime, "9198011310019"))


class PrivacyNoticeTest(ServiceTestCase):
	def test_eric_runs_only_after_the_privacy_notices_are_confirmed(self):
		unconfirmed = replace(self.runtime, confirmed_privacy_notice=False)
		workers = self.started_workers()
		for operation, header, certificate, pin in (
			(Operation.VALIDATE, HEADER, None, None),
			(Operation.TEST_SEND, TEST_HEADER, CONTAINER, PIN),
			(Operation.SEND, HEADER, CONTAINER, PIN),
		):
			with self.subTest(operation=operation), self.assertRaises(PrivacyNoticeNotConfirmed) as raised:
				run(operation, nutzdaten(), header, unconfirmed, certificate, pin)
			self.assertIn("Datenschutzhinweise der Finanzverwaltung", str(raised.exception))
		self.assertEqual(workers, [])


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

	def test_an_exception_while_a_send_runs_ends_the_worker_and_leaves_the_outcome_unknown(self):
		workers = self.started_workers()
		with interrupted_after(1, JobTimeout(PIN)):
			result = run(
				Operation.SEND,
				nutzdaten("STUB-SLEEP"),
				HEADER,
				self.runtime,
				CONTAINER,
				PIN,
				timeout_seconds=60,
			)
		self.assertIs(result.outcome, Outcome.UNKNOWN)
		self.assertEqual(self.codes(result), ["SB-WORKER", "SB-UNKNOWN"])
		self.assertIn("JobTimeout", result.messages[0].text)
		self.assertNotIn(PIN, result.messages[0].text)
		(worker,) = workers
		self.assertEqual(worker.returncode, -signal.SIGKILL)

	def test_an_exception_while_a_check_runs_fails_it(self):
		with interrupted_after(1, JobTimeout()):
			result = run(
				Operation.VALIDATE,
				nutzdaten("STUB-SLEEP"),
				HEADER,
				self.runtime,
				None,
				None,
				timeout_seconds=60,
			)
		self.assertIs(result.outcome, Outcome.FAILED)
		self.assertEqual(self.codes(result), ["SB-WORKER"])

	def test_an_exception_no_handler_catches_still_ends_the_worker(self):
		workers = self.started_workers()
		with self.assertRaises(Interrupted), interrupted_after(1, Interrupted()):
			run(
				Operation.SEND,
				nutzdaten("STUB-SLEEP"),
				HEADER,
				self.runtime,
				CONTAINER,
				PIN,
				timeout_seconds=60,
			)
		(worker,) = workers
		self.assertEqual(worker.returncode, -signal.SIGKILL)
		self.assertTrue(worker.stdout.closed and worker.stderr.closed)

	def test_a_worker_that_does_not_start_sent_nothing_and_the_error_stays(self):
		with (
			mock.patch.object(service, "start_worker", side_effect=OSError("kein Prozess")),
			self.assertRaises(OSError),
		):
			run(Operation.SEND, nutzdaten(), HEADER, self.runtime, CONTAINER, PIN)


class WorkDirectoryTest(ServiceTestCase):
	"""ERiC writes its protocol into a directory only the user of the bench can read, which the service makes for
	each run and removes once the worker has ended, whether it answered, was ended after its timeout or by an
	exception: a worker that is killed cannot remove anything itself."""

	def setUp(self):
		self.temporary = Path(tempfile.mkdtemp(prefix="steuerbote-eric-tmp-"))
		self.addCleanup(shutil.rmtree, self.temporary, ignore_errors=True)
		self.enterContext(mock.patch.object(tempfile, "tempdir", str(self.temporary)))
		self.seen: list[tuple[Path, int]] = []
		start = service.start_worker

		def started() -> subprocess.Popen:
			for path in self.temporary.iterdir():
				self.seen.append((path, stat.S_IMODE(path.stat().st_mode)))
			return start()

		self.enterContext(mock.patch.object(service, "start_worker", side_effect=started))

	def assertRemovedAfterwards(self) -> None:
		((path, mode),) = self.seen
		self.assertTrue(path.name.startswith("steuerbote-eric-"))
		self.assertEqual(mode, 0o700)
		self.assertEqual(list(self.temporary.iterdir()), [])

	def test_a_run_that_answers(self):
		self.assertIs(
			run(Operation.VALIDATE, nutzdaten(), HEADER, self.runtime, None, None).outcome, Outcome.VALID
		)
		self.assertRemovedAfterwards()

	def test_a_run_whose_worker_is_ended_after_its_timeout(self):
		result = run(
			Operation.SEND, nutzdaten("STUB-SLEEP"), HEADER, self.runtime, CONTAINER, PIN, timeout_seconds=1
		)
		self.assertIs(result.outcome, Outcome.UNKNOWN)
		self.assertRemovedAfterwards()

	def test_a_run_that_an_exception_interrupts(self):
		with self.assertRaises(Interrupted), interrupted_after(1, Interrupted()):
			run(
				Operation.SEND,
				nutzdaten("STUB-SLEEP"),
				HEADER,
				self.runtime,
				CONTAINER,
				PIN,
				timeout_seconds=60,
			)
		self.assertRemovedAfterwards()

	def test_the_worker_writes_into_that_directory(self):
		request = json.loads(
			service._process_request(
				Operation.SEND, nutzdaten(), HEADER, self.runtime, CONTAINER, PIN, work_dir=self.temporary
			)
		)
		self.assertEqual(request["work_dir"], str(self.temporary))


class OrphanTest(ServiceTestCase):
	"""A background job ended with SIGKILL, by the operating system or a supervisor, takes its worker along
	(PR_SET_PDEATHSIG), so no worker keeps running with certificate and PIN after the run is gone."""

	def subreaper(self) -> None:
		"""Orphans of this test become children of this process, which so learns how they ended."""
		prctl = ctypes.CDLL(None, use_errno=True).prctl
		prctl.argtypes = (ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong)
		self.assertEqual(prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0), 0)
		self.addCleanup(prctl, PR_SET_CHILD_SUBREAPER, 0, 0, 0, 0)

	def ended(self, pid: int, seconds: float) -> int | None:
		"""The wait status of the child, once it has ended within the seconds; None while it runs."""
		deadline = time.monotonic() + seconds
		while True:
			ended, status = os.waitpid(pid, os.WNOHANG)
			if ended:
				self.reaped.add(pid)
				return status
			if time.monotonic() >= deadline:
				return None
			time.sleep(0.05)

	def end(self, pid: int) -> None:
		"""Kill and reap a child the test has not reaped."""
		if pid not in self.reaped:
			os.kill(pid, signal.SIGKILL)
			os.waitpid(pid, 0)

	def test_a_worker_ends_with_the_job_that_started_it(self):
		self.reaped: set[int] = set()
		self.subreaper()
		log_dir = Path(tempfile.mkdtemp(prefix="steuerbote-eric-orphan-"))
		self.addCleanup(shutil.rmtree, log_dir, ignore_errors=True)
		runtime = replace(self.runtime, log_dir=log_dir)
		job = subprocess.Popen(  # noqa: S603 - this interpreter with the job above
			[sys.executable, "-c", JOB, json.dumps(runtime.to_dict()), str(log_dir)],
			stdout=subprocess.PIPE,
			cwd=service.APP_ROOT,
		)
		self.addCleanup(job.wait)
		self.addCleanup(job.kill)
		worker = int(job.stdout.readline())
		self.addCleanup(self.end, worker)
		deadline = time.monotonic() + 30
		while not (log_dir / "eric.log").exists() and time.monotonic() < deadline:
			time.sleep(0.05)
		self.assertTrue((log_dir / "eric.log").exists(), "the worker never reached ERiC")
		job.kill()
		job.wait()
		status = self.ended(worker, 10)
		self.assertIsNotNone(status, "the worker outlived the job that started it")
		self.assertEqual(os.WTERMSIG(status), signal.SIGKILL)


class TracebackTest(ServiceTestCase):
	"""What a traceback with the local variables of its frames, as Frappe writes it in developer mode, shows."""

	def raised(self, call: Callable[[], object]) -> BaseException:
		try:
			call()
		except (OSError, Interrupted) as error:
			return error
		self.fail("the call raised nothing")

	def assertShowsNoSecret(self, error: BaseException) -> str:
		variables = frame_variables(error)
		for secret in SECRETS:
			self.assertNotIn(secret, variables)
		return variables

	def test_an_error_before_the_worker_starts(self):
		with mock.patch.object(service, "start_worker", side_effect=OSError("kein Prozess")):
			error = self.raised(
				lambda: run(Operation.SEND, nutzdaten(), HEADER, self.runtime, CONTAINER, PIN, proxy=PROXY)
			)
		variables = self.assertShowsNoSecret(error)
		self.assertIn("certificate_secret = ********", variables)
		self.assertIn("request_secret = ********", variables)
		self.assertIn("proxy = Proxy(host='proxy.example.com', port=3128, username='steuerbote')", variables)
		self.assertNotIn(PROXY_GEHEIM, variables)

	def test_an_exception_while_the_worker_runs(self):
		with interrupted_after(1, Interrupted()):
			error = self.raised(
				lambda: run(
					Operation.SEND,
					nutzdaten("STUB-SLEEP"),
					HEADER,
					self.runtime,
					CONTAINER,
					PIN,
					timeout_seconds=60,
				)
			)
		variables = self.assertShowsNoSecret(error)
		self.assertIn("in _communicate", variables)
		self.assertIn("input = <sealed>", variables)

	def test_the_request_of_a_run_is_sealed(self):
		request = service._process_request(Operation.SEND, nutzdaten(), HEADER, self.runtime, CONTAINER, PIN)
		self.assertEqual((repr(request), str(request)), ("<sealed>", "<sealed>"))
		data = json.loads(request)
		self.assertEqual(
			(base64.b64decode(data["certificate_secret"]), data["certificate_password"]), (CONTAINER, PIN)
		)
		self.assertTrue(data["runtime"]["confirmed_privacy_notice"])
		self.assertIsNone(data["proxy"])

	def test_the_proxy_with_its_password_goes_into_the_sealed_request(self):
		request = service._process_request(
			Operation.SEND, nutzdaten(), HEADER, self.runtime, CONTAINER, PIN, PROXY
		)
		self.assertEqual(repr(request), "<sealed>")
		self.assertEqual(json.loads(request)["proxy"], PROXY.to_dict())

	def test_hides_what_frappe_hides(self):
		def fail(certificate_password: str, request: dict, container: bytes) -> None:
			raise OSError("kaputt")

		error = self.raised(
			lambda: fail(PIN, {"certificate_secret": "geheim", "nutzdaten": "<Kz83/>"}, b"offen")
		)
		variables = frame_variables(error)
		self.assertIn("certificate_password = ********", variables)
		self.assertIn("{certificate_secret: ********, nutzdaten: <Kz83/>}", variables)
		self.assertIn("container = b'offen'", variables)


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

	def test_needs_no_confirmation_of_the_privacy_notices(self):
		self.assertIn(
			"libericapi.so", library_versions(replace(self.runtime, confirmed_privacy_notice=False))
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
		# The stub loads wherever the tests run, ERiC and so its installation only on Linux x86_64 with glibc.
		with mock.patch.object(runtime, "_platform", return_value=("linux", "x86_64", "glibc 2.41")):
			info = install_from_archive(archive, checksum, self.directory / "eric", probe=library_versions)
		self.assertTrue((info.lib_dir / "libericapi.so").is_file())
		(installation,) = installations(self.directory / "eric")
		self.assertEqual(
			dict(installation.library_versions),
			{"libericapi.so": "44, 3, 6, 0", "libcheckUStVA_2026.so": "44, 3, 6, 0"},
		)
