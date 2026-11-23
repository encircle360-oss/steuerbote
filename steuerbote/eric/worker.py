"""The worker that calls ERiC once, in a process of its own: python -m steuerbote.eric.worker <pid of the parent>.

ERiC runs in a short-lived process because a crash in the native library then ends only that process,
because a thread inside ERiC must not be stopped (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.3.14), so only
ending the process enforces a timeout, and because ERiC keeps its state per process between
EricInitialisiere and EricBeende (Kap. 4.1.1). This is the only module that loads the library, and it
never imports Frappe.

The worker reads one JSON object from standard input and writes one to standard output:

	{"command": "process", "operation": "validate" | "test_send" | "send",
	 "nutzdaten": "<Anmeldungssteuern …>" | "<zm …>", "header": {…}, "runtime": {…},
	 "certificate_secret": "<PKCS#12 in base64>" | null,
	 "certificate_password": "…" | null, "proxy": {"host": …, "port": …, "username": …, "password": …} | null,
	 "work_dir": "/absolute/directory"}
		answers with a TransmissionResult as JSON; a proxy goes into the settings of ERiC before anything is
		sent (steuerbote.eric.proxy); ERiC writes its files into work_dir, which the parent makes private and
		removes once the worker has ended, since a killed worker removes nothing
	{"command": "version", "runtime": {…}}
		answers {"libraries": {name: product version}} or {"error": "…"}

Exit codes: 0 when the answer is on standard output, whatever the outcome; 2 when the request was not
understood, before anything was loaded, or the pid of the parent is missing; 1 for an unexpected error and
for a parent that has gone before the worker hardened itself. A process killed by a signal, a crash inside
ERiC, ends with the negative signal number in the parent.

Certificate and password, and the password of a proxy, arrive on standard input only and are never written
anywhere: not into the answer, and not to standard error, which names the field of a request it did not understand or the type
of an unexpected error, never a value. Before reading the request the worker makes itself undumpable,
so neither a core file nor a debugger of the same user can read what it holds, and has the kernel send it
SIGKILL when its parent ends (prctl(2), PR_SET_PDEATHSIG, Linux only, as ERiC is here), so that a background
job killed with SIGKILL takes its worker along. The signal follows the thread that started the worker, the
thread of the job that waits for it; a parent that ended before the signal was set is no longer the parent of
the worker, which then ends at once.

Prüfen is EBV-9 of the handbook (Tabelle 6-2): Hinweisprüfung, validation and a preview PDF, without
encryption parameters. Testsenden and Senden are EBV-6 with send-Auth, the only way to send a UStVA
(Tabelle 8-8) and a ZMDO (Tabelle 8-28): validation, sending and the Übertragungsprotokoll, signed with the
certificate („Daten werden signiert versendet.“, Tabelle 5-2). The Verfahren, the Datenart and the Vorgang of
the TransferHeader and the datenartVersion are those of the Datenart the header names (steuerbote.eric.datenart).
ERiC 44 talks to one server and gives the Transferticket in its answer only (ERiC-Releasenotes 44.3.6.0,
Kap. 5.2.7), read with EricGetErrormessagesFromXMLAnswer (Kap. 6.2.4).

EricBearbeiteVorgang reads, validates, prepares with signature and encryption, sends and prints, in this
order (Abbildung 6-6); it validates whenever it sends (Kap. 6.2.1), and it prints only after the server
answered OK (Kap. 5 with Abbildung 5-1). So a send has failed, with nothing sent, only for a code of
BEFORE_TRANSFER, and is invalid for 610001002. Every other code leaves the outcome of a send unknown,
the errors of printing among them, and nothing is sent again automatically. A server answer is read
whenever ERiC returns one, for its Transferticket and messages; after a timeout it may still hold the
Transferticket (Kap. 6.2.5.2). The buffers after other errors are undefined (API-Referenz,
EricBearbeiteVorgang), so an answer that cannot be read is kept as it is, and any answer turns even a
code of BEFORE_TRANSFER into an unknown outcome.
"""

import base64
import binascii
import ctypes
import json
import os
import resource
import signal
import sys
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
	TRANSFER_ERR_XML_NHEADER,
	TRANSFER_ERR_XML_THEADER,
	VALIDIERE,
	EricError,
	EricLibrary,
	ProcessResult,
)
from steuerbote.eric.datenart import of_version
from steuerbote.eric.header import EnvelopeHeader, datenteil, problems
from steuerbote.eric.proxy import Proxy
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

PR_SET_PDEATHSIG = 1
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
BEFORE_TRANSFER = frozenset(
	{
		# The call: its parameters and flags, and ERiC not ready for it (API-Referenz, EricBearbeiteVorgang;
		# Kap. 6.2.1 for the encryption parameters).
		610001081,  # GLOBAL_NICHT_INITIALISIERT
		610001231,  # GLOBAL_MEHRFACHAUFRUFE_NICHT_UNTERSTUETZT
		610001526,  # GLOBAL_NULL_PARAMETER
		610001222,  # GLOBAL_UNGUELTIGER_PARAMETER
		610001226,  # GLOBAL_UNGUELTIGE_PARAMETER_VERSION
		610001218,  # GLOBAL_UNGUELTIGE_FLAG_KOMBINATION
		610001209,  # GLOBAL_SEND_FLAG_MEHR_ALS_EINES
		610001206,  # GLOBAL_VERSCHLUESSELUNGS_PARAMETER_NICHT_ANGEGEBEN
		610001027,  # GLOBAL_VERSCHLUESSELUNGS_PARAMETER_NICHT_ERLAUBT
		610001225,  # GLOBAL_VERSAND_ART_NICHT_UNTERSTUETZT
		610301300,  # IO_UEBERGABEPARAMETER_FEHLERHAFT
		610301400,  # IO_UNGUELTIGE_UTF8_SEQUENZ
		610301401,  # IO_UNGUELTIGE_ZEICHEN_IN_PARAMETER
		# What may be sent at all: Hersteller-ID, Testmerker, a beta (Kap. 5.4.3, 6.5.3, 10.1.1) and the
		# plugin of the datenartVersion.
		610001016,  # GLOBAL_HERSTELLER_ID_NICHT_ERLAUBT
		610001019,  # GLOBAL_ECHTFALL_NICHT_ERLAUBT
		610001020,  # GLOBAL_NO_VERSAND_IN_BETA_VERSION
		610001025,  # GLOBAL_TESTMERKER_UNGUELTIG
		610001042,  # GLOBAL_DATENARTVERSION_UNBEKANNT
		610001044,  # GLOBAL_DATENARTVERSION_XML_INKONSISTENT
		610301202,  # IO_TESTHERSTELLERID_GESPERRT
		# Reading and validating the data, and their size, checked first and once more before the transfer
		# (Abbildung 6-6; Kap. 5.1.3.3).
		GLOBAL_PRUEF_FEHLER,
		610001026,  # GLOBAL_DATENSATZ_ZU_GROSS
		610301006,  # IO_PARSE_FEHLER
		610301014,  # IO_STEUERZEICHEN_IM_NDS
		610301104,  # IO_FALSCHES_VERFAHREN
		610301105,  # IO_READER_MEHRFACHE_STEUERFAELLE
		610301106,  # IO_READER_UNERWARTETE_ELEMENTE
		610301107,  # IO_READER_FORMALE_FEHLER
		610301108,  # IO_READER_FALSCHES_ENCODING
		610301109,  # IO_READER_MEHRFACHE_NUTZDATEN_ELEMENTE
		610301110,  # IO_READER_MEHRFACHE_NUTZDATENBLOCK_ELEMENTE
		610301111,  # IO_UNBEKANNTE_DATENART
		610301114,  # IO_READER_UNTERSACHBEREICH_UNGUELTIG
		610301115,  # IO_READER_ZU_VIELE_NUTZDATENBLOCK_ELEMENTE
		610301150,  # IO_READER_STEUERZEICHEN_IM_TRANSFERHEADER
		610301151,  # IO_READER_STEUERZEICHEN_IM_NUTZDATENHEADER
		610301152,  # IO_READER_STEUERZEICHEN_IN_DEN_NUTZDATEN
		610301200,  # IO_READER_SCHEMA_VALIDIERUNGSFEHLER
		610301201,  # IO_READER_UNBEKANNTE_XML_ENTITY
		610301252,  # IO_DATENTEILNOTFOUND
		610301253,  # IO_DATENTEILENDNOTFOUND
		# Certificate, PIN, signature and encryption, which prepare the data before they are sent; send-Auth
		# uses the certificate only to sign (Abbildung 6-6; Kap. 5.1.3.3, 5.2; Tabelle 5-2).
		610001028,  # GLOBAL_NUR_PORTALZERTIFIKAT_ERLAUBT
		610201101,  # CRYPT_E_INVALID_HANDLE
		610201106,  # CRYPT_E_PIN_WRONG
		610201107,  # CRYPT_E_PIN_LOCKED
		610201111,  # CRYPT_E_P12_READ
		610201112,  # CRYPT_E_P12_DECODE
		610201113,  # CRYPT_E_P12_SIG_KEY
		610201118,  # CRYPT_E_XML_SIG_ADD
		610201120,  # CRYPT_E_XML_SIG_SIGN
		610201124,  # CRYPT_E_ENCRYPT
		610201201,  # CRYPT_SIGNATUR
		610201203,  # CRYPT_NICHT_UNTERSTUETZTES_PSE_FORMAT
		610201205,  # CRYPT_PIN_BENOETIGT
		610201213,  # CRYPT_CORRUPTED
		610201221,  # CRYPT_E_P12_NO_SIG_CERT
		# No connection: the transfer never began (Kap. 4.1.2.2 for the proxy).
		610101276,  # TRANSFER_ERR_PROXYCONNECT
		610101278,  # TRANSFER_ERR_CONNECTSERVER
		610101280,  # TRANSFER_ERR_PROXYAUTH
		610101282,  # TRANSFER_ERR_SEND_INIT
		610101284,  # TRANSFER_ERR_PROXYPORT_INVALID
	}
)
"""The return codes of a send after which nothing reached ELSTER; any other code leaves the outcome unknown."""

ERIC_CODE = "SB-ERIC"
TICKET_CODE = "SB-TICKET"
OPTIONAL_HEADER_FIELDS = frozenset({"testmerker", "nutzdaten_datenlieferant"})
"""The fields of EnvelopeHeader that are text or null; every other one is text."""


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
	proxy: Proxy | None = None
	work_dir: Path | None = None


def main() -> int:
	arguments = sys.argv[1:]
	if len(arguments) != 1 or not arguments[0].isdigit():
		sys.stderr.write("steuerbote.eric.worker: invalid request: parent\n")
		return EXIT_INVALID_REQUEST
	if not harden(int(arguments[0])):
		sys.stderr.write("steuerbote.eric.worker: parent gone\n")
		return EXIT_FAILURE
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


def harden(parent: int) -> bool:
	"""No core file and no ptrace by the same user while the worker holds certificate and PIN, and SIGKILL once
	the parent ends; False when the parent had ended already."""
	prctl(PR_SET_DUMPABLE, 0)
	_, hard = resource.getrlimit(resource.RLIMIT_CORE)
	resource.setrlimit(resource.RLIMIT_CORE, (0, hard))
	prctl(PR_SET_PDEATHSIG, signal.SIGKILL)
	return os.getppid() == parent


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
	certificate = request.get("certificate_secret")
	password = request.get("certificate_password")
	if operation.sends and not isinstance(certificate, str):
		raise RequestError("certificate_secret")
	if operation.sends and not isinstance(password, str):
		raise RequestError("certificate_password")
	try:
		container = None if certificate is None else base64.b64decode(certificate, validate=True)
	except binascii.Error, TypeError:
		raise RequestError("certificate_secret") from None
	try:
		proxy = None if request.get("proxy") is None else Proxy.from_dict(request.get("proxy"))
	except ValueError:
		raise RequestError("proxy") from None
	work_dir = request.get("work_dir")
	if not isinstance(work_dir, str) or not os.path.isabs(work_dir):
		raise RequestError("work_dir")
	return Request(command, runtime, operation, nutzdaten, header, container, password, proxy, Path(work_dir))


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
		try:
			for name, value in (*SETTINGS, *(request.proxy.settings() if request.proxy else ())):
				library.set_setting(name, value)
			if operation.sends:
				certificate = library.open_certificate_from_bytes(
					request.certificate, request.password.encode()
				)
			kind = of_version(header.datenart_version)
			xml = library.create_transfer_header(
				datenteil(request.nutzdaten, header),
				verfahren=kind.verfahren,
				datenart=kind.name,
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
				pdf_path=request.work_dir / "protocol.pdf",
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


def outcome(operation: Operation, code: int, *, server_answered: bool) -> Outcome:
	"""What a return code of EricBearbeiteVorgang means for the operation, given whether a server answer came."""
	if not operation.sends:
		if code in (ERIC_OK, GLOBAL_HINWEISE):
			return Outcome.VALID
		return Outcome.INVALID if code == GLOBAL_PRUEF_FEHLER else Outcome.FAILED
	if code == ERIC_OK:
		return Outcome.ACCEPTED
	if code in (TRANSFER_ERR_XML_THEADER, TRANSFER_ERR_XML_NHEADER):
		return Outcome.REJECTED
	if code in BEFORE_TRANSFER and not server_answered:
		return Outcome.INVALID if code == GLOBAL_PRUEF_FEHLER else Outcome.FAILED
	return Outcome.UNKNOWN


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

	def result(meaning: Outcome, ticket: str | None = None) -> TransmissionResult:
		return TransmissionResult(
			operation,
			meaning.ok,
			False,
			version,
			ticket,
			testmerker,
			tuple(messages),
			protocol_pdf=pdf if meaning.ok else None,
			server_response_xml=server_xml,
			outcome=meaning,
		)

	meaning = outcome(operation, code, server_answered=server_xml is not None)
	ticket = None
	if operation.sends and server_xml is not None:
		ticket = _server_messages(library, server_xml, messages, rejected=meaning is Outcome.REJECTED)
	if meaning is Outcome.ACCEPTED and ticket is None:
		messages.append(
			Message(
				TICKET_CODE,
				"ELSTER hat die Daten angenommen, die Antwort nennt aber kein lesbares Transferticket. "
				"Die Antwort des Servers liegt bei.",
				HINT,
			)
		)
	if meaning is Outcome.UNKNOWN:
		messages.append(UNKNOWN_MESSAGE)
	return result(meaning, ticket)


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
	library: EricLibrary, server_xml: str, messages: list[Message], *, rejected: bool
) -> str | None:
	"""Add the codes of the server answer to messages; the Transferticket, if the answer names one.

	The return code of the TransferHeader is 0 when the server accepted the delivery. Its text is kept as
	a hint, except in a rejection, where code 0 means that only a NutzdatenHeader failed.
	"""
	try:
		answer = library.server_answer(server_xml)
	except EricError:
		return None
	if answer.code != "0":
		messages.append(Message(answer.code, answer.text, ERROR, "TransferHeader"))
	elif not rejected:
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
		if not isinstance(value, str) and not (field.name in OPTIONAL_HEADER_FIELDS and value is None):
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
