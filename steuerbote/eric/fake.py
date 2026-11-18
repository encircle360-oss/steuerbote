"""The simulation of ERiC: the same operations and results, and nothing leaves the server.

Without an ERiC runtime steuerbote answers with this simulation, so the whole way from the button to the
record of the Übermittlung can be used and tested before a Hersteller-ID exists. It checks what can be
checked without ERiC: the header of the delivery, that the Nutzdaten are XML without a DTD, with the root
Anmeldungssteuern in the namespace of the year and the Kennzahl 83, which the Jahresdokumentation
UStVA 2026 makes mandatory (rule 110085064), and, with the ERiC documentation at hand, the Nutzdaten
against UStVA-<Jahr>.xsd of Datenarten/ElsterAnmeldung/UStVA/Schema/<Jahr>/. The variable
STEUERBOTE_ERIC_DOC_DIR names the unzipped documentation package or its directory Dokumentation.

A test send or send that passes answers with a Transferticket "SIM-" and the first 28 hexadecimal digits
of the SHA-256 of the Nutzdaten, a form no Transferticket of ERiC has, and with a one-page PDF saying that
nothing was transmitted. Every result is marked as simulated and carries the hint SIM-000.

This module is pure Python and never imports Frappe; lxml is imported only for the schema check.
"""

import hashlib
import os
from collections.abc import Sequence
from pathlib import Path
from xml.etree import ElementTree

from steuerbote.eric.header import EnvelopeHeader, datenart, problems, without_declaration
from steuerbote.eric.result import ERROR, HINT, TESTMERKER, Message, Operation, Outcome, TransmissionResult

DOCUMENTATION_VARIABLE = "STEUERBOTE_ERIC_DOC_DIR"
SIMULATED_VERSION = "simulation"
TICKET_PREFIX = "SIM-"
NAMESPACE = "http://finkonsens.de/elster/elsteranmeldung/ustva/v{year}"
SCHEMA = "Datenarten/ElsterAnmeldung/UStVA/Schema/{year}/UStVA-{year}.xsd"
PDF_TITLE = "Simulation, keine Übermittlung"

SIMULATION_NOTICE = Message(
	"SIM-000", "Simulationsmodus: ERiC ist nicht eingerichtet, es wird nichts an ELSTER übermittelt.", HINT
)
STRUCTURE_ONLY = "Die Simulation prüft nur Aufbau, Wurzelelement und Kennzahl 83, nicht das XSD des Jahres {year}: {reason}"


class Simulation:
	def __init__(self, documentation: Path | None = None):
		"""documentation: the unzipped ERiC documentation; by default the directory STEUERBOTE_ERIC_DOC_DIR names."""
		configured = os.environ.get(DOCUMENTATION_VARIABLE)
		self._documentation = documentation or (Path(configured) if configured else None)

	def run(self, operation: Operation, nutzdaten_xml: str, header: EnvelopeHeader) -> TransmissionResult:
		testmerker = TESTMERKER if operation is Operation.TEST_SEND else None
		messages = [SIMULATION_NOTICE]
		errors = list(problems(header, operation))
		if not errors:
			year = datenart(header.datenart_version).year
			root, structure = _structure(nutzdaten_xml, year)
			errors.extend(structure)
			if root is not None and not structure:
				schema_errors, unchecked = self._schema_errors(without_declaration(nutzdaten_xml), year)
				errors.extend(schema_errors)
				if unchecked:
					messages.append(
						Message("SIM-001", STRUCTURE_ONLY.format(year=year, reason=unchecked), HINT)
					)
		if errors:
			return TransmissionResult(
				operation,
				False,
				True,
				SIMULATED_VERSION,
				None,
				testmerker,
				(SIMULATION_NOTICE, *errors),
				outcome=Outcome.INVALID,
			)
		if operation is Operation.VALIDATE:
			return TransmissionResult(operation, True, True, SIMULATED_VERSION, None, None, tuple(messages))
		digest = hashlib.sha256(nutzdaten_xml.encode()).hexdigest()
		ticket = TICKET_PREFIX + digest[:28]
		pdf = placeholder_pdf(PDF_TITLE, _protocol_lines(operation, header, root, year, ticket, digest))
		return TransmissionResult(
			operation, True, True, SIMULATED_VERSION, ticket, testmerker, tuple(messages), protocol_pdf=pdf
		)

	def _schema_errors(self, nutzdaten: str, year: int) -> tuple[list[Message], str | None]:
		"""The errors against the XSD of the year, and why the check did not run, if it did not."""
		schema_path = self._schema(year)
		if schema_path is None:
			return [], f"Die ERiC-Dokumentation mit UStVA-{year}.xsd fehlt ({DOCUMENTATION_VARIABLE})."
		try:
			from lxml import etree
		except ImportError:
			return [], "lxml ist nicht installiert."
		schema = etree.XMLSchema(etree.parse(str(schema_path)))
		parser = etree.XMLParser(resolve_entities=False, no_network=True)
		document = etree.fromstring(nutzdaten.encode(), parser)
		if schema.validate(document):
			return [], None
		return [
			Message("SIM-005", f"{schema_path.name}, Zeile {error.line}: {error.message}", ERROR)
			for error in schema.error_log
		], None

	def _schema(self, year: int) -> Path | None:
		if self._documentation is None:
			return None
		for directory in (self._documentation, *sorted(self._documentation.glob("ERiC-*/Dokumentation"))):
			path = directory / SCHEMA.format(year=year)
			if path.is_file():
				return path
		return None


def placeholder_pdf(title: str, lines: Sequence[str]) -> bytes:
	"""A one-page A4 PDF: the title in bold Helvetica, then the lines.

	The text is encoded in WinAnsiEncoding, one of the encodings every PDF reader knows for the standard
	fonts (PDF 1.4, Anhang D); characters outside it become question marks.
	"""
	text = [
		*("BT", "/F2 16 Tf", "56 780 Td", f"({_pdf_string(title)}) Tj", "ET"),
		*("BT", "/F1 11 Tf", "16 TL", "56 758 Td", *(f"({_pdf_string(line)}) '" for line in lines), "ET"),
	]
	content = "\n".join(text).encode("cp1252", errors="replace")
	objects = (
		b"<< /Type /Catalog /Pages 2 0 R >>",
		b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
		b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
		b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
		b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
		b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
		b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
	)
	pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
	offsets = []
	for number, body in enumerate(objects, 1):
		offsets.append(len(pdf))
		pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
	xref = len(pdf)
	pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
	pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
	pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
	return bytes(pdf)


def _structure(nutzdaten_xml: str, year: int) -> tuple[ElementTree.Element | None, list[Message]]:
	text = without_declaration(nutzdaten_xml)
	if "<!DOCTYPE" in text:
		return None, [Message("SIM-002", "Die Nutzdaten dürfen keine DTD enthalten.", ERROR)]
	try:
		root = ElementTree.fromstring(text)  # noqa: S314 - refused above if it carries a DTD
	except ElementTree.ParseError as error:
		return None, [Message("SIM-002", f"Die Nutzdaten sind kein wohlgeformtes XML: {error}.", ERROR)]
	namespace = NAMESPACE.format(year=year)
	if root.tag != f"{{{namespace}}}Anmeldungssteuern":
		return root, [
			Message(
				"SIM-003",
				f"Die Nutzdaten beginnen nicht mit Anmeldungssteuern im Namensraum {namespace}.",
				ERROR,
				"Anmeldungssteuern",
			)
		]
	if root.find(f".//{{{namespace}}}Kz83") is None:
		return root, [
			Message(
				"SIM-004",
				"Die Kennzahl 83, der verbleibende Betrag der Anmeldung, ist ein Pflichtfeld (Regel 110085064).",
				ERROR,
				"Kz83",
			)
		]
	return root, []


def _protocol_lines(
	operation: Operation,
	header: EnvelopeHeader,
	root: ElementTree.Element,
	year: int,
	ticket: str,
	digest: str,
) -> list[str]:
	namespace = NAMESPACE.format(year=year)

	def value(name: str) -> str:
		return root.findtext(f".//{{{namespace}}}{name}", default="").strip()

	return [
		"Diese Übermittlung wurde nur simuliert. Es wurde nichts an ELSTER übermittelt.",
		"",
		f"Vorgang: {'Testsenden' if operation is Operation.TEST_SEND else 'Senden'}",
		f"Datenart: {header.datenart_version}",
		f"Zeitraum: {value('Zeitraum')}/{value('Jahr')}",
		f"Kennzahl 83: {value('Kz83')}",
		f"Transferticket (simuliert): {ticket}",
		f"SHA-256 der Nutzdaten: {digest}",
		f"{header.produkt_name} {header.produkt_version}",
	]


def _pdf_string(text: str) -> str:
	return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
