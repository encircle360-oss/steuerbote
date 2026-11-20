"""The simulation of ERiC: the same operations and results, and nothing leaves the server.

Without an ERiC runtime steuerbote answers with this simulation, so the whole way from the button to the
record of the Übermittlung can be used and tested before a Hersteller-ID exists. It checks what can be
checked without ERiC: the header of the delivery, that the Nutzdaten are XML without a DTD, with the root
Anmeldungssteuern in the namespace of the year, and, with the ERiC documentation at hand, the Nutzdaten against
UStVA-<Jahr>.xsd of Datenarten/ElsterAnmeldung/UStVA/Schema/<Jahr>/. The variable STEUERBOTE_ERIC_DOC_DIR names
the unzipped documentation package or its directory Dokumentation.

The Datenart UStVA holds form USt 1 H next to the Voranmeldung (ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 2-13),
and the schema leaves the rules that tie its elements together to ERiC. Of these the simulation checks those
on the structure, from the sheet "Anmeldungssteuern - Regeln" of the Jahresdokumentation UStVA 2026: the
Steuerfall holds exactly one of the three contexts (110085099), each context the fields it requires (CONTEXTS),
and a context's Jahr is the year of the Datenart (110085047, 110085130, 110085131).

A test send or send that passes answers with a Transferticket "SIM-" and the first 28 hexadecimal digits
of the SHA-256 of the Nutzdaten, a form no Transferticket of ERiC has, and with a one-page PDF saying that
nothing was transmitted. Every result is marked as simulated and carries the hint SIM-000.

This module is pure Python and never imports Frappe; lxml is imported only for the schema check.
"""

import hashlib
import os
from collections.abc import Sequence
from pathlib import Path
from types import MappingProxyType
from typing import NamedTuple
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
STRUCTURE_ONLY = (
	"Die Simulation prüft nur Aufbau, Kontext und Pflichtfelder, nicht das XSD des Jahres {year}: {reason}"
)


class Required(NamedTuple):
	"""A field a context requires, with the Fehlercode of its rule and what the message says."""

	element: str
	code: str
	text: str


class Context(NamedTuple):
	"""What the simulation checks of a context of the Steuerfall and how its protocol names it.

	``year_rule`` is the Fehlercode of the rule that the Jahr is the year of the Datenart, ``form`` the name of
	form USt 1 H for a context of it, None for the Voranmeldung.
	"""

	required: tuple[Required, ...]
	year_rule: str
	form: str | None = None


_JAHR = Required("Jahr", "110085048", "Das Jahr ist ein Pflichtfeld")
_STEUERNUMMER = Required("Steuernummer", "110085044", "Die Steuernummer ist ein Pflichtfeld")
_HERSTELLER_ID = Required("Kz09", "110085045", "Die Kennzahl 09, die Hersteller-ID, ist ein Pflichtfeld")
CONTEXTS: MappingProxyType[str, Context] = MappingProxyType(
	{
		"Umsatzsteuervoranmeldung": Context(
			(
				Required(
					"Kz83",
					"110085064",
					"Die Kennzahl 83, der verbleibende Betrag der Anmeldung, ist ein Pflichtfeld",
				),
			),
			"110085047",
		),
		"Dauerfristverlaengerung": Context(
			(_JAHR, _STEUERNUMMER, _HERSTELLER_ID), "110085130", "Antrag auf Dauerfristverlängerung"
		),
		"Umsatzsteuersondervorauszahlung": Context(
			(
				_JAHR,
				_STEUERNUMMER,
				_HERSTELLER_ID,
				Required(
					"Kz38",
					"110085143",
					"Die Kennzahl 38, die Sondervorauszahlung, ist ein Pflichtfeld, gegebenenfalls 0",
				),
			),
			"110085131",
			"Anmeldung der Sondervorauszahlung",
		),
	}
)
ONE_CONTEXT = (
	"Der Steuerfall enthält genau einen der Kontexte Umsatzsteuervoranmeldung, Dauerfristverlaengerung und "
	"Umsatzsteuersondervorauszahlung (Regel 110085099)."
)


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
			context, structure = _structure(nutzdaten_xml, year)
			errors.extend(structure)
			if not structure:
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
		pdf = placeholder_pdf(PDF_TITLE, _protocol_lines(operation, header, context, year, ticket, digest))
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
	"""The one context of the Nutzdaten, or the errors of their structure."""
	text = without_declaration(nutzdaten_xml)
	if "<!DOCTYPE" in text:
		return None, [Message("SIM-002", "Die Nutzdaten dürfen keine DTD enthalten.", ERROR)]
	try:
		root = ElementTree.fromstring(text)  # noqa: S314 - refused above if it carries a DTD
	except ElementTree.ParseError as error:
		return None, [Message("SIM-002", f"Die Nutzdaten sind kein wohlgeformtes XML: {error}.", ERROR)]
	namespace = NAMESPACE.format(year=year)
	if root.tag != f"{{{namespace}}}Anmeldungssteuern":
		return None, [
			Message(
				"SIM-003",
				f"Die Nutzdaten beginnen nicht mit Anmeldungssteuern im Namensraum {namespace}.",
				ERROR,
				"Anmeldungssteuern",
			)
		]
	contexts = [
		child
		for steuerfall in root.iterfind(f"{{{namespace}}}Steuerfall")
		for child in steuerfall
		if _local_name(child) in CONTEXTS
	]
	if len(contexts) != 1:
		return None, [Message("SIM-006", ONE_CONTEXT, ERROR, "Steuerfall")]
	(context,) = contexts
	rules = CONTEXTS[_local_name(context)]
	for field in rules.required:
		if context.find(f"{{{namespace}}}{field.element}") is None:
			return None, [Message("SIM-004", f"{field.text} (Regel {field.code}).", ERROR, field.element)]
	jahr = context.findtext(f"{{{namespace}}}Jahr")
	if jahr is not None and jahr.strip() != str(year):
		wrong_year = (
			f"Das Jahr {jahr.strip()} ist nicht das Jahr der Datenart, {year} (Regel {rules.year_rule})."
		)
		return None, [Message("SIM-007", wrong_year, ERROR, "Jahr")]
	return context, []


def _local_name(element: ElementTree.Element) -> str:
	return element.tag.rpartition("}")[2]


def _protocol_lines(
	operation: Operation,
	header: EnvelopeHeader,
	context: ElementTree.Element,
	year: int,
	ticket: str,
	digest: str,
) -> list[str]:
	namespace = NAMESPACE.format(year=year)

	def value(name: str) -> str:
		return context.findtext(f"{{{namespace}}}{name}", default="").strip()

	form = CONTEXTS[_local_name(context)].form
	if form is None:
		filing = [f"Zeitraum: {value('Zeitraum')}/{value('Jahr')}", f"Kennzahl 83: {value('Kz83')}"]
	else:
		kz38 = [f"Kennzahl 38: {value('Kz38')}"] if context.find(f"{{{namespace}}}Kz38") is not None else []
		filing = [f"Vordruck: {form} {value('Jahr')}", *kz38]
	return [
		"Diese Übermittlung wurde nur simuliert. Es wurde nichts an ELSTER übermittelt.",
		"",
		f"Vorgang: {'Testsenden' if operation is Operation.TEST_SEND else 'Senden'}",
		f"Datenart: {header.datenart_version}",
		*filing,
		f"Transferticket (simuliert): {ticket}",
		f"SHA-256 der Nutzdaten: {digest}",
		f"{header.produkt_name} {header.produkt_version}",
	]


def _pdf_string(text: str) -> str:
	return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
