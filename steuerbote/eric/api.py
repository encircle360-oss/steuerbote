"""ctypes binding of the ERiC single-threading API, version 44 and later.

Signatures, structures, flags and codes follow the ERiC API-Referenz 44.3.6.0 (ericapi.h, eric_types.h,
ericdef.h, eric_fehlercodes.h). Since ERiC 44.1, EricBearbeiteVorgang takes seven parameters without a
transfer handle (ERiC-Releasenotes 44.3.6.0, Kap. 5.2.6), and the print parameters are version 4, the
encryption parameters version 3. On Linux the calling convention is cdecl.

The library is loaded with RTLD_GLOBAL (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 4.2.2), never through
ldconfig or LD_LIBRARY_PATH (Kap. 4.3.3). Data for ERiC are UTF-8 without a byte order mark (Kap. 5.3.2),
paths are passed in the encoding of the file system (Kap. 5.3.3). A return buffer is read as a pointer
with its length, since its content may hold NUL bytes, and is always freed (API-Referenz,
EricRueckgabepufferHandle). The PIN and the PKCS#12 container are copied into buffers of their own,
which are wiped when ERiC no longer needs them: the PIN after each call, the container once the
certificate is closed. EricCreateTH is used as the handbook recommends (Kap. 5.1).

Only the worker process loads the library: one ERiC per process, initialised once and finished once.
"""

import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from ctypes import (
	CDLL,
	CFUNCTYPE,
	POINTER,
	RTLD_GLOBAL,
	Array,
	Structure,
	byref,
	c_char_p,
	c_int,
	c_uint8,
	c_uint32,
	c_void_p,
	cast,
	create_string_buffer,
	memset,
	sizeof,
	string_at,
)
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

LIBRARY = "libericapi.so"

VALIDIERE = 1 << 1
SENDE = 1 << 2
DRUCKE = 1 << 5
PRUEFE_HINWEISE = 1 << 7

PRINT_PARAMETERS_VERSION = 4
ENCRYPTION_PARAMETERS_VERSION = 3

ERIC_OK = 0
GLOBAL_PRUEF_FEHLER = 610001002
GLOBAL_HINWEISE = 610001003
GLOBAL_NICHT_GENUEGEND_ARBEITSSPEICHER = 610001013
TRANSFER_ERR_XML_THEADER = 610101210
TRANSFER_ERR_SEND = 610101271
TRANSFER_ERR_NORESPONSE = 610101279
TRANSFER_ERR_TIMEOUT = 610101283
TRANSFER_ERR_XML_NHEADER = 610101292

PdfCallback = CFUNCTYPE(c_int, c_char_p, POINTER(c_uint8), c_uint32, c_void_p)
"""EricPdfCallback: name of the PDF, its bytes, their number and the user data of the print parameters."""


class PrintParameters(Structure):
	"""eric_druck_parameter_t, version 4."""

	_fields_ = (
		("version", c_uint32),
		("vorschau", c_uint32),
		("duplexDruck", c_uint32),
		("pdfName", c_char_p),
		("fussText", c_char_p),
		("pdfCallback", PdfCallback),
		("pdfCallbackBenutzerdaten", c_void_p),
	)


class EncryptionParameters(Structure):
	"""eric_verschluesselungs_parameter_t, version 3."""

	_fields_ = (
		("version", c_uint32),
		("zertifikatHandle", c_uint32),
		("pin", c_char_p),
	)


_BUFFER = c_void_p
PROTOTYPES = MappingProxyType(
	{
		"EricInitialisiere": (c_int, (c_char_p, c_char_p)),
		"EricBeende": (c_int, ()),
		"EricEinstellungSetzen": (c_int, (c_char_p, c_char_p)),
		"EricRueckgabepufferErzeugen": (_BUFFER, ()),
		"EricRueckgabepufferInhalt": (c_void_p, (_BUFFER,)),
		"EricRueckgabepufferLaenge": (c_uint32, (_BUFFER,)),
		"EricRueckgabepufferFreigeben": (c_int, (_BUFFER,)),
		"EricHoleFehlerText": (c_int, (c_int, _BUFFER)),
		"EricVersion": (c_int, (_BUFFER,)),
		"EricCreateTH": (c_int, (c_char_p,) * 9 + (_BUFFER,)),
		"EricZertifikatOeffnenAusBytes": (c_int, (POINTER(c_uint32), c_void_p, c_uint32, c_void_p)),
		"EricCloseHandleToCertificate": (c_int, (c_uint32,)),
		"EricBearbeiteVorgang": (
			c_int,
			(
				c_char_p,
				c_char_p,
				c_uint32,
				POINTER(PrintParameters),
				POINTER(EncryptionParameters),
				_BUFFER,
				_BUFFER,
			),
		),
		"EricGetErrormessagesFromXMLAnswer": (c_int, (c_char_p, _BUFFER, _BUFFER, _BUFFER, _BUFFER)),
		"EricCheckXML": (c_int, (c_char_p, c_char_p, _BUFFER)),
	}
)
"""Return and argument types of each function steuerbote calls, as ericapi.h declares them."""


class EricError(Exception):
	"""A call of ERiC returned a code other than ERIC_OK."""

	def __init__(self, code: int, text: str):
		super().__init__(f"{code}: {text}")
		self.code = code
		self.text = text


@dataclass(frozen=True, slots=True)
class Pdf:
	name: str
	"""The Nutzdatenticket of the Nutzdatenblock the PDF shows, or "Uebertragungsprotokoll"."""
	data: bytes


@dataclass(frozen=True, slots=True)
class ProcessResult:
	"""What EricBearbeiteVorgang returned: its code, both buffers and the PDFs of the callback."""

	code: int
	return_xml: str
	server_response_xml: str
	pdfs: tuple[Pdf, ...]


@dataclass(frozen=True, slots=True)
class ServerAnswer:
	"""What EricGetErrormessagesFromXMLAnswer read from the answer of the ELSTER server."""

	transferticket: str
	code: str
	"""Return code of the TransferHeader."""
	text: str
	nutzdaten_errors_xml: str
	"""Codes and texts of the NutzdatenHeaders (EricGetErrormessagesFromXMLAnswer.xsd)."""


class EricLibrary:
	def __init__(self, path: Path):
		self._containers: dict[int, Array] = {}
		self._library = CDLL(os.fsdecode(path), mode=RTLD_GLOBAL)
		for name, (restype, argtypes) in PROTOTYPES.items():
			function = getattr(self._library, name)
			function.restype = restype
			function.argtypes = argtypes

	def initialise(self, plugin_dir: Path, log_dir: Path) -> None:
		"""EricInitialisiere: plugins are searched below plugin_dir, eric.log is written to log_dir."""
		self._check(self._library.EricInitialisiere(os.fsencode(plugin_dir), os.fsencode(log_dir)))

	def finish(self) -> None:
		self._check(self._library.EricBeende())

	def set_setting(self, name: str, value: str) -> None:
		self._check(self._library.EricEinstellungSetzen(name.encode(), value.encode()))

	def error_text(self, code: int) -> str:
		with self._buffer() as buffer:
			if self._library.EricHoleFehlerText(code, buffer) != ERIC_OK:
				return f"ERiC hat keinen Text zum Fehlercode {code}."
			return self._text(buffer)

	def version(self) -> str:
		"""The EricVersion XML: product and file version of each library."""
		with self._buffer() as buffer:
			self._check(self._library.EricVersion(buffer))
			return self._text(buffer)

	def create_transfer_header(
		self,
		xml: str,
		*,
		verfahren: str,
		datenart: str,
		vorgang: str,
		testmerker: str | None,
		hersteller_id: str,
		datenlieferant: str,
	) -> str:
		"""EricCreateTH: the complete Elster XML for a DatenTeil, testmerker None for a real case."""
		with self._buffer() as buffer:
			self._check(
				self._library.EricCreateTH(
					xml.encode(),
					verfahren.encode(),
					datenart.encode(),
					vorgang.encode(),
					None if testmerker is None else testmerker.encode(),
					hersteller_id.encode(),
					datenlieferant.encode(),
					None,
					None,
					buffer,
				)
			)
			return self._text(buffer)

	def open_certificate_from_bytes(self, container: bytes, pin: bytes) -> int:
		"""EricZertifikatOeffnenAusBytes: the handle of a PKCS#12 container held in memory.

		The copy of the container stays as it is until close_certificate, because the API reference does
		not say whether ERiC reads it again after opening; the copy of the PIN is wiped at once.
		"""
		container_buffer = create_string_buffer(container, len(container))
		pin_buffer = create_string_buffer(pin)
		handle = c_uint32()
		try:
			code = self._library.EricZertifikatOeffnenAusBytes(
				byref(handle), container_buffer, len(container), pin_buffer
			)
		finally:
			_wipe(pin_buffer)
		if code != ERIC_OK:
			_wipe(container_buffer)
			raise EricError(code, self.error_text(code))
		self._containers[handle.value] = container_buffer
		return handle.value

	def close_certificate(self, handle: int) -> None:
		"""EricCloseHandleToCertificate, then the copy of the container is wiped."""
		code = self._library.EricCloseHandleToCertificate(handle)
		container = self._containers.pop(handle, None)
		if container is not None:
			_wipe(container)
		self._check(code)

	def process(
		self,
		xml: str,
		datenart_version: str,
		flags: int,
		*,
		preview: bool = False,
		pdf_path: Path | None = None,
		certificate: int | None = None,
		pin: bytes = b"",
	) -> ProcessResult:
		"""EricBearbeiteVorgang. Print parameters go along with DRUCKE, encryption parameters with a certificate.

		PDFs come through the callback. pdf_path is passed as well, because the handbook calls pdfName
		mandatory for a printout (Kap. 5.1.5.4), while the API reference says a callback replaces the file.
		"""
		pdfs = []

		def collect(name: bytes | None, data, size: int, _user_data) -> int:
			pdfs.append(Pdf((name or b"").decode(errors="replace"), string_at(data, size)))
			return 0

		callback = PdfCallback(collect)
		print_parameters = None
		if flags & DRUCKE:
			print_parameters = PrintParameters(
				version=PRINT_PARAMETERS_VERSION,
				vorschau=int(preview),
				duplexDruck=0,
				pdfName=None if pdf_path is None else os.fsencode(pdf_path),
				fussText=None,
				pdfCallback=callback,
				pdfCallbackBenutzerdaten=None,
			)
		pin_buffer = create_string_buffer(pin)
		encryption = None
		if certificate is not None:
			encryption = EncryptionParameters(
				version=ENCRYPTION_PARAMETERS_VERSION,
				zertifikatHandle=certificate,
				pin=cast(pin_buffer, c_char_p),
			)
		try:
			with self._buffer() as answer, self._buffer() as server:
				code = self._library.EricBearbeiteVorgang(
					xml.encode(),
					datenart_version.encode(),
					flags,
					None if print_parameters is None else byref(print_parameters),
					None if encryption is None else byref(encryption),
					answer,
					server,
				)
				return ProcessResult(code, self._text(answer), self._text(server), tuple(pdfs))
		finally:
			_wipe(pin_buffer)

	def server_answer(self, xml: str) -> ServerAnswer:
		"""EricGetErrormessagesFromXMLAnswer on the unchanged answer of the ELSTER server."""
		with ExitStack() as stack:
			ticket, code, text, errors = (stack.enter_context(self._buffer()) for _ in range(4))
			self._check(
				self._library.EricGetErrormessagesFromXMLAnswer(xml.encode(), ticket, code, text, errors)
			)
			return ServerAnswer(self._text(ticket), self._text(code), self._text(text), self._text(errors))

	def check_xml(self, xml: str, datenart_version: str) -> None:
		"""EricCheckXML: validates against the schema of the datenartVersion, raising EricError if invalid."""
		with self._buffer() as buffer:
			code = self._library.EricCheckXML(xml.encode(), datenart_version.encode(), buffer)
			if code != ERIC_OK:
				raise EricError(code, self._text(buffer) or self.error_text(code))

	@contextmanager
	def _buffer(self) -> Iterator[int]:
		handle = self._library.EricRueckgabepufferErzeugen()
		if not handle:
			raise EricError(
				GLOBAL_NICHT_GENUEGEND_ARBEITSSPEICHER, "ERiC konnte keinen Rückgabepuffer anlegen."
			)
		try:
			yield handle
		finally:
			self._library.EricRueckgabepufferFreigeben(handle)

	def _text(self, buffer: int) -> str:
		content = self._library.EricRueckgabepufferInhalt(buffer)
		return string_at(content, self._library.EricRueckgabepufferLaenge(buffer)).decode(errors="replace")

	def _check(self, code: int) -> None:
		if code != ERIC_OK:
			raise EricError(code, self.error_text(code))


def _wipe(buffer: Array) -> None:
	memset(buffer, 0, sizeof(buffer))
