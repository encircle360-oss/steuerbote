"""The worker that calls ERiC once, in a process of its own: python -m steuerbote.eric.worker.

ERiC runs in a short-lived process because a crash in the native library then ends only that process,
because a thread inside ERiC must not be stopped (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.3.14), so only
ending the process enforces a timeout, and because ERiC keeps its state per process between
EricInitialisiere and EricBeende (Kap. 4.1.1). This is the only module that loads the library, and it
never imports Frappe.

The worker reads one JSON object from standard input and writes one to standard output:

	{"command": "process", "operation": "validate" | "test_send" | "send", "nutzdaten": "<Anmeldungssteuern …>",
	 "header": {…}, "runtime": {…}, "certificate": "<PKCS#12 in base64>" | null,
	 "certificate_password": "…" | null}
		answers with a TransmissionResult as JSON
	{"command": "version", "runtime": {…}}
		answers {"libraries": {name: product version}} or {"error": "…"}

Exit codes: 0 when the answer is on standard output, whatever the outcome; 2 when the request was not
understood, before anything was loaded; 1 for an unexpected error. A process killed by a signal, a
crash inside ERiC, ends with the negative signal number in the parent.

Certificate and password arrive on standard input only and are never written anywhere: not into the
answer, and not to standard error, which names the field of a request it did not understand or the type
of an unexpected error, never a value. Before reading the request the worker makes itself undumpable,
so neither a core file nor a debugger of the same user can read what it holds.

Prüfen is EBV-9 of the handbook (Tabelle 6-2): Hinweisprüfung, validation and a preview PDF, without
encryption parameters. Testsenden and Senden are EBV-6 with send-Auth, the only way to send a UStVA
(Tabelle 8-8): validation, sending and the Übertragungsprotokoll, signed with the certificate. ERiC 44
talks to one server and gives the Transferticket in its answer only (ERiC-Releasenotes 44.3.6.0,
Kap. 5.2.7), read with EricGetErrormessagesFromXMLAnswer (Kap. 6.2.4). Without an answer after sending,
whether the data arrived is unknown, and nothing is sent again automatically.
"""

import base64
import binascii
import ctypes
import json
import resource
import sys
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, fields
from pathlib import Path
from typing import BinaryIO, TextIO
from xml.etree import ElementTree

from steuerbote.eric.api import (
	DRUCKE,
	ERIC_OK,
	GLOBAL_HINWEISE,
	GLOBAL_PRUEF_FEHLER,
	LIBRARY,
	PRUEFE_HINWEISE,
	SENDE,
	TRANSFER_ERR_NORESPONSE,
	TRANSFER_ERR_SEND,
	TRANSFER_ERR_TIMEOUT,
	TRANSFER_ERR_XML_NHEADER,
	TRANSFER_ERR_XML_THEADER,
	VALIDIERE,
	EricError,
	EricLibrary,
	ProcessResult,
)
from steuerbote.eric.header import EnvelopeHeader, datenart, datenteil, problems
from steuerbote.eric.result import (
	ERROR,
	EXIT_FAILURE,
	EXIT_INVALID_REQUEST,
	EXIT_OK,
	HINT,
	TESTMERKER,
	UNKNOWN_MESSAGE,
	Message,
	Operation,
	Outcome,
	TransmissionResult,
)
from steuerbote.eric.runtime import RuntimeInfo

PR_GET_DUMPABLE = 3
PR_SET_DUMPABLE = 4

SETTINGS = (
	("transfer.connect_timeout", "30"),
	("transfer.response_timeout", "60"),
	("validieren.fehler_max", "100"),
	("validieren.hinweise_max", "100"),
)
"""Timeouts in seconds, by default 30 and unlimited, and the messages per call, by default 20 (Tabelle 4-1)."""

VALIDATE_FLAGS = PRUEFE_HINWEISE | VALIDIERE | DRUCKE
SEND_FLAGS = VALIDIERE | SENDE | DRUCKE
UNKNOWN_AFTER_SENDING = frozenset({TRANSFER_ERR_SEND, TRANSFER_ERR_NORESPONSE, TRANSFER_ERR_TIMEOUT})
"""Codes after which ERiC cannot say whether the server received the data (Entwicklerhandbuch, Kap. 6.2.5)."""

ERIC_CODE = "SB-ERIC"
TICKET_CODE = "SB-TICKET"


class RequestError(ValueError):
	"""The request is not understood; the message names the field, never its value."""


@dataclass(frozen=True, slots=True)
class Request:
	command: str
	runtime: RuntimeInfo
	operation: Operation | None = None
	nutzdaten: str = ""
	header: EnvelopeHeader | None = None
	certificate: bytes | None = None
	password: str | None = None


def main() -> int:
	harden()
	return serve(sys.stdin.buffer, sys.stdout.buffer, sys.stderr)


def serve(stdin: BinaryIO, stdout: BinaryIO, stderr: TextIO) -> int:
	"""Answer one request; the exit code of the worker."""
	try:
		request = parse_request(stdin.read())
	except RequestError as error:
		stderr.write(f"steuerbote.eric.worker: invalid request: {error}\n")
		return EXIT_INVALID_REQUEST
	try:
		answer = process(request).to_dict() if request.command == "process" else versions(request.runtime)
	except Exception as error:
		stderr.write(f"steuerbote.eric.worker: unexpected {type(error).__name__}\n")
		return EXIT_FAILURE
	stdout.write(json.dumps(answer).encode())
	stdout.flush()
	return EXIT_OK


def harden() -> None:
	"""No core file and no ptrace by the same user while the worker holds certificate and PIN."""
	prctl(PR_SET_DUMPABLE, 0)
	_, hard = resource.getrlimit(resource.RLIMIT_CORE)
	resource.setrlimit(resource.RLIMIT_CORE, (0, hard))


def prctl(option: int, value: int) -> int:
	"""prctl(2) with one argument, raising OSError on failure."""
	function = ctypes.CDLL(None, use_errno=True).prctl
	function.argtypes = (ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong)
	result = function(option, value, 0, 0, 0)
	if result < 0:
		raise OSError(ctypes.get_errno(), f"prctl({option}) failed")
	return result


def parse_request(data: bytes) -> Request:
	try:
		request = json.loads(data)
	except UnicodeDecodeError, json.JSONDecodeError:
		raise RequestError("not JSON") from None
	if not isinstance(request, Mapping):
		raise RequestError("not a JSON object")
	try:
		runtime = RuntimeInfo.from_dict(request.get("runtime"))
	except ValueError:
		raise RequestError("runtime") from None
	command = request.get("command")
	if command == "version":
		return Request(command, runtime)
	if command != "process":
		raise RequestError("command")
	try:
		operation = Operation(request.get("operation"))
	except ValueError:
		raise RequestError("operation") from None
	nutzdaten = request.get("nutzdaten")
	if not isinstance(nutzdaten, str):
		raise RequestError("nutzdaten")
	header = _header(request.get("header"))
	certificate = request.get("certificate")
	password = request.get("certificate_password")
	if operation.sends and not isinstance(certificate, str):
		raise RequestError("certificate")
	if operation.sends and not isinstance(password, str):
		raise RequestError("certificate_password")
	try:
		container = None if certificate is None else base64.b64decode(certificate, validate=True)
	except binascii.Error, TypeError:
		raise RequestError("certificate") from None
	return Request(command, runtime, operation, nutzdaten, header, container, password)


def process(request: Request) -> TransmissionResult:
	"""Check, test send or send once with ERiC."""
	operation, runtime, header = request.operation, request.runtime, request.header
	testmerker = TESTMERKER if operation is Operation.TEST_SEND else None

	def failed(*messages: Message) -> TransmissionResult:
		return TransmissionResult(
			operation, False, False, runtime.version, None, testmerker, messages, outcome=Outcome.FAILED
		)

	header_problems = problems(header, operation, own_hersteller_id=runtime.hersteller_id)
	if header_problems:
		return failed(*header_problems)
	try:
		library = EricLibrary(runtime.lib_dir / LIBRARY)
	except OSError as error:
		return failed(Message(ERIC_CODE, f"ERiC lässt sich nicht laden: {error}", ERROR))
	try:
		runtime.log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
	except OSError as error:
		return failed(Message(ERIC_CODE, f"Das Protokollverzeichnis von ERiC fehlt: {error}", ERROR))
	try:
		library.initialise(runtime.plugin_dir, runtime.log_dir)
	except EricError as error:
		return failed(_error_message(error))
	certificate = None
	try:
		with tempfile.TemporaryDirectory(prefix="steuerbote-eric-") as work:
			try:
				for name, value in SETTINGS:
					library.set_setting(name, value)
				if operation.sends:
					certificate = library.open_certificate_from_bytes(
						request.certificate, request.password.encode()
					)
				kind = datenart(header.datenart_version)
				xml = library.create_transfer_header(
					datenteil(request.nutzdaten, header),
					verfahren=kind.verfahren,
					datenart=kind.datenart,
					vorgang=kind.vorgang,
					testmerker=header.testmerker,
					hersteller_id=header.hersteller_id,
					datenlieferant=header.datenlieferant,
				)
				# process raises only before it calls ERiC, when it gets no return buffer.
				answer = library.process(
					xml,
					header.datenart_version,
					SEND_FLAGS if operation.sends else VALIDATE_FLAGS,
					preview=not operation.sends,
					pdf_path=Path(work) / "protocol.pdf",
					certificate=certificate,
					pin=(request.password or "").encode(),
				)
			except EricError as error:
				return failed(_error_message(error))
			return _result(library, operation, runtime.version, testmerker, answer)
	finally:
		if certificate is not None:
			with suppress(EricError):
				library.close_certificate(certificate)
		with suppress(EricError):
			library.finish()


def versions(runtime: RuntimeInfo) -> dict[str, object]:
	"""The product versions of the libraries ERiC loads, as EricVersion lists them."""
	try:
		library = EricLibrary(runtime.lib_dir / LIBRARY)
		library.initialise(runtime.plugin_dir, runtime.log_dir)
	except (OSError, EricError) as error:
		return {"error": str(error)}
	try:
		root = ElementTree.fromstring(library.version())  # noqa: S314 - the answer of ERiC itself
	finally:
		library.finish()
	return {
		"libraries": {
			_text(library_element, "Name"): _text(library_element, "Produktversion")
			for library_element in root
			if _local(library_element.tag) == "Bibliothek"
		}
	}


def _result(
	library: EricLibrary, operation: Operation, version: str, testmerker: str | None, answer: ProcessResult
) -> TransmissionResult:
	code = answer.code
	messages = []
	if code != ERIC_OK:
		messages.append(
			Message(str(code), library.error_text(code), HINT if code == GLOBAL_HINWEISE else ERROR)
		)
	messages.extend(_rule_messages(answer.return_xml))
	pdf = answer.pdfs[0].data if answer.pdfs else None
	server_xml = answer.server_response_xml or None

	def result(outcome: Outcome, ticket: str | None = None) -> TransmissionResult:
		return TransmissionResult(
			operation,
			outcome.ok,
			False,
			version,
			ticket,
			testmerker,
			tuple(messages),
			protocol_pdf=pdf if outcome.ok else None,
			server_response_xml=server_xml,
			outcome=outcome,
		)

	if not operation.sends:
		if code in (ERIC_OK, GLOBAL_HINWEISE):
			return result(Outcome.VALID)
		return result(Outcome.INVALID if code == GLOBAL_PRUEF_FEHLER else Outcome.FAILED)
	if code == ERIC_OK:
		ticket = _server_messages(library, answer.server_response_xml, messages, accepted=True)
		if ticket is None:
			messages.append(
				Message(
					TICKET_CODE,
					"ELSTER hat die Daten angenommen, die Antwort nennt aber kein lesbares Transferticket. "
					"Die Antwort des Servers liegt bei.",
					HINT,
				)
			)
		return result(Outcome.ACCEPTED, ticket)
	if code in (TRANSFER_ERR_XML_THEADER, TRANSFER_ERR_XML_NHEADER):
		ticket = _server_messages(library, answer.server_response_xml, messages, accepted=False)
		return result(Outcome.REJECTED, ticket)
	if code in UNKNOWN_AFTER_SENDING:
		messages.append(UNKNOWN_MESSAGE)
		return result(Outcome.UNKNOWN)
	return result(Outcome.INVALID if code == GLOBAL_PRUEF_FEHLER else Outcome.FAILED)


def _rule_messages(return_xml: str) -> list[Message]:
	"""The FehlerRegelpruefung and Hinweis elements of the return buffer (EricBearbeiteVorgang.xsd)."""
	if not return_xml:
		return []
	try:
		root = ElementTree.fromstring(return_xml)  # noqa: S314 - the return buffer of ERiC itself
	except ElementTree.ParseError:
		return [Message(ERIC_CODE, "Den Rückgabepuffer von ERiC konnte steuerbote nicht lesen.", ERROR)]
	found = []
	for element in root:
		kind = _local(element.tag)
		if kind not in ("FehlerRegelpruefung", "Hinweis"):
			continue
		identifier = "FachlicheFehlerId" if kind == "FehlerRegelpruefung" else "FachlicheHinweisId"
		found.append(
			Message(
				_text(element, identifier) or _text(element, "RegelName"),
				_text(element, "Text"),
				ERROR if kind == "FehlerRegelpruefung" else HINT,
				_text(element, "Feldidentifikator") or None,
			)
		)
	return found


def _server_messages(
	library: EricLibrary, server_xml: str, messages: list[Message], *, accepted: bool
) -> str | None:
	"""Add the codes of the server answer to messages; the Transferticket, if the answer names one.

	The return code of the TransferHeader is 0 when the server accepted the delivery; its text is kept as
	a hint for an accepted delivery and left out when only a NutzdatenHeader failed.
	"""
	try:
		answer = library.server_answer(server_xml)
	except EricError:
		return None
	if answer.code != "0":
		messages.append(Message(answer.code, answer.text, ERROR, "TransferHeader"))
	elif accepted:
		messages.append(Message(answer.code, answer.text, HINT, "TransferHeader"))
	with suppress(ElementTree.ParseError):
		for error in ElementTree.fromstring(answer.nutzdaten_errors_xml):  # noqa: S314 - written by ERiC
			messages.append(Message(_text(error, "Code"), _text(error, "Meldung"), ERROR, "NutzdatenHeader"))
	return answer.transferticket or None


def _error_message(error: EricError) -> Message:
	return Message(str(error.code), error.text, ERROR)


def _header(data: object) -> EnvelopeHeader:
	if not isinstance(data, Mapping):
		raise RequestError("header")
	values = {}
	for field in fields(EnvelopeHeader):
		value = data.get(field.name)
		if not isinstance(value, str) and not (field.name == "testmerker" and value is None):
			raise RequestError(f"header.{field.name}")
		values[field.name] = value
	return EnvelopeHeader(**values)


def _local(tag: str) -> str:
	return tag.rpartition("}")[2]


def _text(element: ElementTree.Element, name: str) -> str:
	child = next((child for child in element if _local(child.tag) == name), None)
	return "" if child is None or child.text is None else child.text.strip()


if __name__ == "__main__":
	sys.exit(main())
