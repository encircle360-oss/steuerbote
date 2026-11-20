"""Run an operation with ERiC or, without a runtime, with the simulation.

This is what the Frappe layer calls from its background job. With a runtime, the call goes to the
worker in a process of its own, python -m steuerbote.eric.worker, and the process is ended when it does
not answer in time: a thread inside ERiC must not be stopped (ERiC-Entwicklerhandbuch 44.3.6.0,
Kap. 5.3.14), a process can. Without a runtime, the simulation answers in this process.

The worker starts with the interpreter of this process, without the PYTHON* environment variables and
the user's site packages (-E -s), in a new process group, with LANG=C.UTF-8 and a fixed PATH as its whole
environment. Its working directory is the directory that holds the package steuerbote, so it imports
the same code as this process, whether steuerbote is installed or checked out; -I would drop that
directory from the module path.

ERiC runs only for a runtime that confirms the privacy notices of the tax administration
(Lizenzvertrag, § 5 Abs. 1 und 2); the simulation needs no confirmation.

Certificate and PIN, and the password of a proxy, go to the worker on standard input and nowhere else. The
request that carries them is Sealed, and each variable that holds one of them has secret or password in its name, so a traceback
with the local variables of its frames, as Frappe writes it in developer mode, shows neither. Once the
worker has started, a send that does not come back, because of the timeout, a crash, an answer that is
no result or an exception in this process such as the timeout of the background job, has an unknown
outcome and must not be repeated blindly; a check that does not come back simply failed.
"""

import base64
import json
import os
import re
import signal
import subprocess
import sys
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path

from steuerbote.eric.fake import Simulation
from steuerbote.eric.header import EnvelopeHeader, problems
from steuerbote.eric.proxy import Proxy
from steuerbote.eric.result import (
	ERROR,
	EXIT_INVALID_REQUEST,
	EXIT_OK,
	TESTMERKER,
	UNKNOWN_MESSAGE,
	Message,
	Operation,
	Outcome,
	TransmissionResult,
)
from steuerbote.eric.runtime import RuntimeInfo
from steuerbote.eric.sealed import Sealed

WORKER_MODULE = "steuerbote.eric.worker"
APP_ROOT = Path(__file__).resolve().parents[2]
WORKER_ENVIRONMENT = {"LANG": "C.UTF-8", "PATH": "/usr/bin:/bin"}
STDERR_LIMIT = 2048
WORKER_CODE = "SB-WORKER"
PIN = re.compile(r"[\x20-\x7e]{6,128}")
"""The PIN of a Zertifikatsdatei: 6 to 128 ASCII characters from space to tilde (Entwicklerhandbuch, Tabelle 5-3)."""
PRIVACY_NOTICE_MISSING = (
	"ERiC läuft erst, wenn die Datenschutzhinweise der Finanzverwaltung zur Kenntnis genommen und bestätigt "
	"sind (ERiC-Lizenzvertrag, § 5 Abs. 1 und 2). Die ERiC-Einstellungen halten diese Bestätigung noch "
	"nicht fest."
)

_SIGNALS = {number.value: number.name for number in signal.Signals}


class WorkerError(RuntimeError):
	"""The worker gave no answer: timeout, crash, unexpected error or an answer that is no JSON."""


class PrivacyNoticeNotConfirmed(RuntimeError):
	"""ERiC was to run for a runtime that does not confirm the privacy notices; nothing was started."""


@dataclass(frozen=True, slots=True)
class WorkerOutput:
	returncode: int
	stdout: bytes
	stderr: str
	timeout_seconds: int | None = None
	"""Set when the worker was ended after this many seconds without an answer."""


def run(
	operation: Operation,
	nutzdaten_xml: str,
	header: EnvelopeHeader,
	runtime: RuntimeInfo | None,
	certificate_secret: bytes | None,
	certificate_password: str | None,
	timeout_seconds: int = 120,
	*,
	proxy: Proxy | None = None,
) -> TransmissionResult:
	"""Dispatch to the ERiC worker when a runtime is configured, else to the simulation.

	With a runtime, PrivacyNoticeNotConfirmed unless the runtime confirms the privacy notices, and SEND
	and TEST_SEND need the PKCS#12 container certificate_secret and its certificate_password; the
	simulation accepts them being None. ERiC reaches the ELSTER servers through ``proxy`` if one is given;
	the simulation reaches no server and leaves it aside. Never logs the password or the certificate.
	"""
	if runtime is None:
		return Simulation().run(operation, nutzdaten_xml, header)
	if not runtime.confirmed_privacy_notice:
		raise PrivacyNoticeNotConfirmed(PRIVACY_NOTICE_MISSING)
	if operation.sends and (certificate_secret is None or certificate_password is None):
		raise ValueError("sending with ERiC needs the certificate and its password")
	testmerker = TESTMERKER if operation is Operation.TEST_SEND else None
	refused = problems(header, operation, own_hersteller_id=runtime.hersteller_id)
	if operation.sends and not PIN.fullmatch(certificate_password):
		refused = (
			Message(
				"SB-PIN",
				"Die PIN einer Zertifikatsdatei hat 6 bis 128 Zeichen aus dem ASCII-Zeichensatz, "
				"vom Leerzeichen bis zur Tilde.",
				ERROR,
			),
			*refused,
		)
	if refused:
		return TransmissionResult(
			operation, False, False, runtime.version, None, testmerker, refused, outcome=Outcome.FAILED
		)
	request_secret = _process_request(
		operation, nutzdaten_xml, header, runtime, certificate_secret, certificate_password, proxy
	)
	worker = start_worker()
	try:
		return interpret(wait_for(worker, request_secret, timeout_seconds), operation, runtime.version)
	except Exception as error:
		return lost(operation, runtime.version, error)


def library_versions(runtime: RuntimeInfo, timeout_seconds: int = 60) -> dict[str, str]:
	"""The product versions of the libraries of the runtime, read by the worker; a smoke test of a runtime."""
	data = answer(call_worker({"command": "version", "runtime": runtime.to_dict()}, timeout_seconds))
	libraries = data.get("libraries") if isinstance(data, Mapping) else None
	if not isinstance(libraries, Mapping):
		raise WorkerError(str(data.get("error") if isinstance(data, Mapping) else data))
	return dict(libraries)


def call_worker(request: Mapping[str, object], timeout_seconds: int) -> WorkerOutput:
	"""Run the worker on the request and end its process group after timeout_seconds without an answer."""
	return wait_for(start_worker(), Sealed(json.dumps(request).encode()), timeout_seconds)


def start_worker() -> subprocess.Popen:
	"""The worker process, waiting for its request on standard input."""
	return subprocess.Popen(  # noqa: S603 - the interpreter of this process with a fixed module
		[sys.executable, "-E", "-s", "-m", WORKER_MODULE],
		stdin=subprocess.PIPE,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		cwd=APP_ROOT,
		env=WORKER_ENVIRONMENT,
		process_group=0,
	)


def wait_for(worker: subprocess.Popen, request_secret: Sealed, timeout_seconds: int) -> WorkerOutput:
	"""Hand the request to the worker and wait for its answer.

	The process group of the worker is ended after timeout_seconds without an answer and before any
	exception leaves, so that no worker outlives the call.
	"""
	try:
		stdout, stderr = worker.communicate(request_secret, timeout=timeout_seconds)
	except subprocess.TimeoutExpired:
		_end(worker)
		stdout, stderr = worker.communicate()
		return WorkerOutput(worker.returncode, stdout, stderr.decode(errors="replace"), timeout_seconds)
	except BaseException:
		_end(worker)
		worker.wait()
		for stream in (worker.stdin, worker.stdout, worker.stderr):
			stream.close()
		raise
	return WorkerOutput(worker.returncode, stdout, stderr.decode(errors="replace"))


def answer(output: WorkerOutput) -> object:
	"""The JSON answer of the worker; WorkerError when there is none."""
	tail = output.stderr[-STDERR_LIMIT:].strip()
	said = f" Ausgabe: {tail}" if tail else ""
	if output.timeout_seconds is not None:
		raise WorkerError(
			f"ERiC hat nach {output.timeout_seconds} Sekunden nicht geantwortet, der Prozess wurde beendet.{said}"
		)
	if output.returncode < 0:
		name = _SIGNALS.get(-output.returncode, str(-output.returncode))
		raise WorkerError(f"Der ERiC-Prozess ist mit dem Signal {name} abgebrochen.{said}")
	if output.returncode == EXIT_INVALID_REQUEST:
		raise WorkerError(f"Der ERiC-Prozess hat die Anfrage nicht verstanden.{said}")
	if output.returncode != EXIT_OK:
		raise WorkerError(f"Der ERiC-Prozess ist mit dem Code {output.returncode} beendet worden.{said}")
	try:
		return json.loads(output.stdout)
	except ValueError as error:
		raise WorkerError("Die Antwort des ERiC-Prozesses ist kein JSON.") from error


def interpret(output: WorkerOutput, operation: Operation, version: str) -> TransmissionResult:
	"""The result the worker answered, or what its missing answer means for the operation."""
	try:
		return TransmissionResult.from_dict(answer(output))
	except WorkerError as error:
		problem = str(error)
	except ValueError:
		problem = "Die Antwort des ERiC-Prozesses ist kein Ergebnis."
	understood = output.timeout_seconds is not None or output.returncode != EXIT_INVALID_REQUEST
	return _no_result(operation, version, Message(WORKER_CODE, problem, ERROR), maybe_sent=understood)


def lost(operation: Operation, version: str, error: Exception) -> TransmissionResult:
	"""The result after an exception that ended the worker while it ran: unknown for a send."""
	message = Message(
		WORKER_CODE,
		f"Der Lauf von ERiC wurde durch {type(error).__name__} unterbrochen, der ERiC-Prozess wurde beendet.",
		ERROR,
	)
	return _no_result(operation, version, message, maybe_sent=True)


def _no_result(
	operation: Operation, version: str, message: Message, *, maybe_sent: bool
) -> TransmissionResult:
	testmerker = TESTMERKER if operation is Operation.TEST_SEND else None
	if not (operation.sends and maybe_sent):
		return TransmissionResult(
			operation, False, False, version, None, testmerker, (message,), outcome=Outcome.FAILED
		)
	return TransmissionResult(
		operation,
		False,
		False,
		version,
		None,
		testmerker,
		(message, UNKNOWN_MESSAGE),
		outcome=Outcome.UNKNOWN,
	)


def _process_request(
	operation: Operation,
	nutzdaten_xml: str,
	header: EnvelopeHeader,
	runtime: RuntimeInfo,
	certificate_secret: bytes | None,
	certificate_password: str | None,
	proxy: Proxy | None = None,
) -> Sealed:
	"""The request of the worker for the operation, as Sealed JSON: the dictionary never outlives this call."""
	return Sealed(
		json.dumps(
			{
				"command": "process",
				"operation": operation.value,
				"nutzdaten": nutzdaten_xml,
				"header": asdict(header),
				"runtime": runtime.to_dict(),
				"certificate_secret": (
					None if certificate_secret is None else base64.b64encode(certificate_secret).decode()
				),
				"certificate_password": certificate_password,
				"proxy": None if proxy is None else proxy.to_dict(),
			}
		).encode()
	)


def _end(worker: subprocess.Popen) -> None:
	with suppress(ProcessLookupError):
		os.killpg(worker.pid, signal.SIGKILL)
