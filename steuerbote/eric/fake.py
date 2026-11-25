"""The simulation of ERiC: the same operations and results, and nothing leaves the server.

Without an ERiC runtime steuerbote answers with this simulation, so the whole way from the button to the
record of the Übermittlung can be used and tested before a Hersteller-ID exists. It checks what can be
checked without ERiC: the header of the delivery, that the Nutzdaten are XML without a DTD and begin with the
element of their Datenart in its namespace (steuerbote.eric.datenart), the rules of the Jahresdokumentation of the
Datenart on their structure, and, with the ERiC documentation at hand, the Nutzdaten against the schema of the
Datenart. The variable STEUERBOTE_ERIC_DOC_DIR names the unzipped documentation package or its directory
Dokumentation.

The Datenart UStVA holds form USt 1 H next to the Voranmeldung (ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 2-13),
and the schema leaves the rules that tie its elements together to ERiC. Of these the simulation checks those
on the structure, from the sheet "Anmeldungssteuern - Regeln" of the Jahresdokumentationen UStVA 2026 and, from
the beta ERiC 45.1.5.0, 2027, which keeps them: the Steuerfall holds exactly one of the three contexts (110085099),
each context the fields it requires (CONTEXTS), and a context's Jahr is the year of the Datenart (110085047,
110085130, 110085131). Of the Hinweise it gives those of HINTS, from 2027 the one on a delivery of a new vehicle
in Kz 44 (11085156), and leaves the others to ERiC. Its schema is UStVA-<Jahr>.xsd in the namespace of the year.

The Zusammenfassende Meldung is the Datenart ZMDO. Of the rules of Jahresdokumentation_ZMDO_2.ods, sheet "ZMDO -
Regeln", the simulation checks those on the structure: the fields the Unternehmer, its Meldezeilen and their
Meldezeitraum require (ZM_REQUIRED), at least one Meldezeile (170045002), each with its Art, USt-IdNr. and sum
(ZM_LINE), no USt-IdNr. and Art twice (170045003 to 170045005, ZM_TWICE), and at most ZM_MAX_LINES Meldezeilen,
the "max. Zeilen" of the fields of a Meldezeile on the sheet "ZMDO - Felder". The element zm comes in the version
000005 of zm_000005.xsd, a schema without a namespace that the simulation includes into the namespace of
ElsterXML 11, as elster11_Zm_000005_extern.xsd does.

The Erklärungen, USt, KSt and GewSt, and the E-Bilanz, Datenart Bilanz, have their checks in
steuerbote.eric.simulation: the structure of their Nutzdaten, the Pflichtvordrucke and the Vorsatz of an Erklärung,
the frame of the E-Bilanz, and the rules their modules add. ERiC checks no schema of the Nutzdaten of the Bilanz
(ERiC-Entwicklerhandbuch, Tabelle 9-20), and neither does the simulation.

A test send or send that passes answers with a Transferticket "SIM-" and the first 28 hexadecimal digits
of the SHA-256 of the Nutzdaten, a form no Transferticket of ERiC has, and with a one-page PDF saying that
nothing was transmitted and naming the document ERiC prints in its place, the Übertragungsprotokoll or the
Freizeichnungsdokument of an Erklärung (steuerbote.eric.datenart). Every result is marked as simulated and carries
the hint SIM-000.

This module is pure Python and never imports Frappe; lxml is imported only for the schema check.
"""

import hashlib
import os
from collections.abc import Sequence
from pathlib import Path
from types import MappingProxyType
from typing import NamedTuple
from xml.etree import ElementTree

from steuerbote.eric.datenart import Datenart, of_version
from steuerbote.eric.header import EnvelopeHeader, problems, without_declaration
from steuerbote.eric.result import (
	ERROR,
	HINT,
	SCHEMA_NOT_CHECKED,
	TESTMERKER,
	Message,
	Operation,
	Outcome,
	TransmissionResult,
)
from steuerbote.eric.runtime import Check
from steuerbote.eric.simulation import Checks, Structure, bilanz, gewst, kst, ust
from steuerbote.vatid.ustid import has_german_check_digit

DOCUMENTATION_VARIABLE = "STEUERBOTE_ERIC_DOC_DIR"
SIMULATED_VERSION = "simulation"
TICKET_PREFIX = "SIM-"
PDF_TITLE = "Simulation, keine Übermittlung"

SIMULATION_NOTICE = Message(
	"SIM-000", "Simulationsmodus: ERiC ist nicht eingerichtet, es wird nichts an ELSTER übermittelt.", HINT
)
STRUCTURE_ONLY = (
	"Die Simulation prüft nur Aufbau, Kontext und Pflichtfelder, nicht das XSD des Jahres {year}: {reason}"
)
ZM_STRUCTURE_ONLY = "Die Simulation prüft nur Aufbau und Pflichtfelder, nicht gegen {schema}: {reason}"
NO_SCHEMA_CHECK = (
	"ERiC prüft die Nutzdaten der Datenart {name} nicht gegen ein Schema (ERiC-Entwicklerhandbuch, Tabelle 9-20); "
	"sie prüft erst das Plugin von ERiC."
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


class Hint(NamedTuple):
	"""A rule of kind Hinweis on a field of a context, from the first year whose Jahresdokumentation has it, with the
	Fehlercode of its rule and what the message says."""

	context: str
	element: str
	code: str
	text: str
	first_year: int


HINTS = (
	Hint(
		"Umsatzsteuervoranmeldung",
		"Kz44",
		"11085156",
		"Kennzahl 44 enthält Lieferungen neuer Fahrzeuge an Abnehmer ohne USt-IdNr.: Jede ist auch dem "
		"Bundeszentralamt für Steuern zu melden (§ 18c UStG, § 1 Absatz 1 FzgLiefgMeldV).",
		2027,
	),
)


class ZmField(NamedTuple):
	"""A field the rules of ZMDO require, by its path below the element zm or a Meldezeile, an attribute after
	@, with the Fehlercode of its rule and what the message says."""

	path: str
	code: str
	text: str

	@property
	def name(self) -> str:
		return self.path.replace("@", "/").rpartition("/")[2]


ZM_REQUIRED = (
	ZmField("unternehmer/knri", "170015001", "Die USt-IdNr. des Unternehmers ist ein Pflichtfeld"),
	ZmField(
		"unternehmer/zulassNr/zulnr1",
		"170015021",
		"Der Paginierbuchstabe der Teilnehmernummer ist ein Pflichtfeld",
	),
	ZmField(
		"unternehmer/zulassNr/zulnr2", "170015023", "Der zweite Teil der Teilnehmernummer ist ein Pflichtfeld"
	),
	ZmField("unternehmer/anschrift/name", "170025001", "Der Name des Unternehmens ist ein Pflichtfeld"),
	ZmField("unternehmer/anschrift/strasse", "170025002", "Die Straße des Unternehmens ist ein Pflichtfeld"),
	ZmField("unternehmer/anschrift/ort", "170025003", "Der Ort des Unternehmens ist ein Pflichtfeld"),
	ZmField("unternehmer/anschrift/staat", "170025004", "Der Staat des Unternehmens ist ein Pflichtfeld"),
	ZmField("unternehmer/zm-zeilen@waehrung", "170015004", "Die Währung ist ein Pflichtfeld"),
	ZmField("unternehmer/zm-zeilen@meldeart", "170015005", "Die Meldeart ist ein Pflichtfeld"),
	ZmField(
		"unternehmer/zm-zeilen/anzeige",
		"170015006",
		"Die Angabe zur Anzeige der monatlichen Abgabe ist ein Pflichtfeld",
	),
	ZmField(
		"unternehmer/zm-zeilen/widerruf",
		"170015009",
		"Die Angabe zum Widerruf der Anzeige ist ein Pflichtfeld",
	),
	ZmField("unternehmer/zm-zeilen/mzr/quart", "170015014", "Der Meldezeitraum ist ein Pflichtfeld"),
	ZmField("unternehmer/zm-zeilen/mzr/jahr", "170015018", "Das Jahr des Meldezeitraums ist ein Pflichtfeld"),
)
ZM_LINES = "unternehmer/zm-zeilen/zeile"
ZM_NO_LINE = ZmField(
	"zeile",
	"170045002",
	"Die Zusammenfassende Meldung braucht eine Meldezeile, Nullmeldungen sind nicht zulässig",
)
ZM_LINE = (
	ZmField("@umsatzart", "170045011", "Die Art der Leistung ist in jeder Meldezeile ein Pflichtfeld"),
	ZmField("knre", "170045008", "Die USt-IdNr. des Erwerbers ist in jeder Meldezeile ein Pflichtfeld"),
	ZmField("betrag", "170045007", "Die Summe ist in jeder Meldezeile ein Pflichtfeld"),
)
ZM_TWICE: MappingProxyType[str, str] = MappingProxyType(
	{"D": "170045003", "L": "170045004", "S": "170045005"}
)
"""The rule that refuses a second Meldezeile of the same USt-IdNr., by Art."""
ZM_MAX_LINES = 5000
MELDEARTEN: MappingProxyType[str, str] = MappingProxyType({"10": "Erstmeldung", "11": "Berichtigung"})
"""The attribute meldeart of zm-zeilen: 10 „Erstmeldung“, 11 „berichtigte Anmeldung“ (meldeart_Type of the XSD)."""


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
			kind = of_version(header.datenart_version)
			checks = CHECKS[kind.name]
			found, structure = _structure(nutzdaten_xml, kind, checks)
			errors.extend(structure)
			if not structure:
				errors.extend(
					found_error for rule in checks.rules if (found_error := rule(found, kind, header))
				)
				schema_errors, unchecked = (
					self._schema_errors(without_declaration(nutzdaten_xml), kind)
					if checks.schema
					else ([], NO_SCHEMA_CHECK.format(name=kind.name))
				)
				errors.extend(schema_errors)
				if unchecked:
					messages.append(Message(SCHEMA_NOT_CHECKED, checks.structure_only(kind, unchecked), HINT))
				messages.extend(checks.hints(found, kind))
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
		filing = checks.filing(found, kind)
		pdf = placeholder_pdf(PDF_TITLE, _protocol_lines(operation, header, kind, filing, ticket, digest))
		return TransmissionResult(
			operation, True, True, SIMULATED_VERSION, ticket, testmerker, tuple(messages), protocol_pdf=pdf
		)

	def _schema_errors(self, nutzdaten: str, kind: Datenart) -> tuple[list[Message], str | None]:
		"""The errors against the XSD of the Datenart, and why the check did not run, if it did not."""
		schema_path = self._schema(kind)
		if schema_path is None:
			return [], f"Die Prüfung gegen das Schema wurde übersprungen, {self._missing(kind)}"
		try:
			from lxml import etree
		except ImportError:
			return [], "lxml ist nicht installiert."
		schema = etree.XMLSchema(_in_its_namespace(etree, schema_path, kind))
		parser = etree.XMLParser(resolve_entities=False, no_network=True)
		document = etree.fromstring(nutzdaten.encode(), parser)
		if schema.validate(document):
			return [], None
		return [
			Message("SIM-005", f"{schema_path.name}, Zeile {error.line}: {error.message}", ERROR)
			for error in schema.error_log
		], None

	def schema_check(self, kind: Datenart) -> Check:
		"""For „Laufzeitumgebung prüfen“: whether Prüfen in the simulation checks the Nutzdaten of the Datenart against
		its schema, and from where, or why not."""
		schema_path = self._schema(kind)
		if schema_path is None:
			return Check("schema", False, f"Die Simulation prüft ohne Schema, {self._missing(kind)}")
		return Check(
			"schema",
			True,
			f"Die Simulation prüft „Prüfen“ gegen {schema_path.name} aus {schema_path.parents[len(Path(kind.schema).parts) - 1]}.",
		)

	def _missing(self, kind: Datenart) -> str:
		name = Path(kind.schema).name
		if self._documentation is None:
			return (
				f"weil die Umgebungsvariable {DOCUMENTATION_VARIABLE} nicht gesetzt ist; sie nennt die entpackte "
				f"ERiC-Dokumentation mit {name}."
			)
		return f"weil {DOCUMENTATION_VARIABLE} auf {self._documentation} zeigt und dort {name} fehlt."

	def _schema(self, kind: Datenart) -> Path | None:
		if self._documentation is None:
			return None
		for directory in (self._documentation, *sorted(self._documentation.glob("ERiC-*/Dokumentation"))):
			path = directory / kind.schema
			if path.is_file():
				return path
		return None


def _in_its_namespace(etree, schema_path: Path, kind: Datenart):
	"""The XSD as lxml takes it. A schema without a target namespace, zm_000005.xsd, is included into the
	namespace of its Datenart, as elster11_Zm_000005_extern.xsd includes it into the one of ElsterXML 11."""
	document = etree.parse(str(schema_path))
	if document.getroot().get("targetNamespace"):
		return document
	wrapper = (
		f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="{kind.namespace}" '
		f'targetNamespace="{kind.namespace}" elementFormDefault="qualified">'
		f'<xs:include schemaLocation="{schema_path.resolve().as_uri()}"/></xs:schema>'
	)
	return etree.fromstring(wrapper.encode())


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


def _structure(
	nutzdaten_xml: str, kind: Datenart, checks: Checks
) -> tuple[ElementTree.Element | None, list[Message]]:
	"""What the protocol reads of the Nutzdaten, or the errors of their structure."""
	text = without_declaration(nutzdaten_xml)
	if "<!DOCTYPE" in text:
		return None, [Message("SIM-002", "Die Nutzdaten dürfen keine DTD enthalten.", ERROR)]
	try:
		root = ElementTree.fromstring(text)  # noqa: S314 - refused above if it carries a DTD
	except ElementTree.ParseError as error:
		return None, [Message("SIM-002", f"Die Nutzdaten sind kein wohlgeformtes XML: {error}.", ERROR)]
	found, error = checks.structure(root, kind)
	return (None, [error]) if error else (found, [])


def _anmeldungssteuern(root: ElementTree.Element, kind: Datenart) -> Structure:
	"""The one context of the Steuerfall of the UStVA, or the error of its structure."""
	namespace = kind.namespace
	if root.tag != f"{{{namespace}}}{kind.root}":
		return None, Message(
			"SIM-003",
			f"Die Nutzdaten beginnen nicht mit {kind.root} im Namensraum {namespace}.",
			ERROR,
			kind.root,
		)
	contexts = [
		child
		for steuerfall in root.iterfind(f"{{{namespace}}}Steuerfall")
		for child in steuerfall
		if _local_name(child) in CONTEXTS
	]
	if len(contexts) != 1:
		return None, Message("SIM-006", ONE_CONTEXT, ERROR, "Steuerfall")
	(context,) = contexts
	rules = CONTEXTS[_local_name(context)]
	for field in rules.required:
		if context.find(f"{{{namespace}}}{field.element}") is None:
			return None, Message("SIM-004", f"{field.text} (Regel {field.code}).", ERROR, field.element)
	jahr = context.findtext(f"{{{namespace}}}Jahr")
	if jahr is not None and jahr.strip() != str(kind.year):
		wrong_year = (
			f"Das Jahr {jahr.strip()} ist nicht das Jahr der Datenart, {kind.year} (Regel {rules.year_rule})."
		)
		return None, Message("SIM-007", wrong_year, ERROR, "Jahr")
	return context, None


def _ustva_filing(context: ElementTree.Element, kind: Datenart) -> list[str]:
	def value(name: str) -> str:
		return context.findtext(f"{{{kind.namespace}}}{name}", default="").strip()

	form = CONTEXTS[_local_name(context)].form
	if form is None:
		return [f"Zeitraum: {value('Zeitraum')}/{value('Jahr')}", f"Kennzahl 83: {value('Kz83')}"]
	kz38 = [f"Kennzahl 38: {value('Kz38')}"] if context.find(f"{{{kind.namespace}}}Kz38") is not None else []
	return [f"Vordruck: {form} {value('Jahr')}", *kz38]


def _ustva_hints(context: ElementTree.Element, kind: Datenart) -> tuple[Message, ...]:
	"""The Hinweise of the year of the Datenart that the fields of the context set off."""
	name = _local_name(context)
	return tuple(
		Message(hint.code, hint.text, HINT, hint.element)
		for hint in HINTS
		if hint.context == name
		and kind.year >= hint.first_year
		and context.find(f"{{{kind.namespace}}}{hint.element}") is not None
	)


def _wid_nr_check_digit(
	context: ElementTree.Element, kind: Datenart, header: EnvelopeHeader
) -> Message | None:
	"""ERiC refuses a W-IdNr. whose check digit is wrong (ungueltigeWirtschaftsIdentifikationsnummer, validation of a
	Voranmeldung 2026 with ERiC 44.3.6.0)."""
	wid_nr = context.findtext(f"{{{kind.namespace}}}WIdNr", default="").strip()
	if not wid_nr or has_german_check_digit(wid_nr):
		return None
	return Message(
		"ungueltigeWirtschaftsIdentifikationsnummer",
		f"Die W-IdNr. {wid_nr} ist ungültig: Ihre Prüfziffer, die letzte der neun Ziffern, stimmt nicht.",
		ERROR,
		"WIdNr",
	)


def _own_vat_id_check_digit(
	root: ElementTree.Element, kind: Datenart, header: EnvelopeHeader
) -> Message | None:
	"""ERiC refuses an own USt-IdNr. whose check digit is wrong (ungueltigeUStIDNr, validation of a Zusammenfassende
	Meldung with ERiC 44.3.6.0)."""
	vat_id = _zm_value(root, "unternehmer/knri", kind)
	if has_german_check_digit(vat_id):
		return None
	return Message(
		"ungueltigeUStIDNr",
		f"Die USt-IdNr. {vat_id} des Unternehmers ist ungültig: Ihre Prüfziffer, die letzte Ziffer, stimmt nicht.",
		ERROR,
		"knri",
	)


def _ustva_structure_only(kind: Datenart, reason: str) -> str:
	return STRUCTURE_ONLY.format(year=kind.year, reason=reason)


def _zm(root: ElementTree.Element, kind: Datenart) -> Structure:
	"""The element zm of the Zusammenfassende Meldung, or the error of its structure."""
	if root.tag != f"{{{kind.namespace}}}{kind.root}" or root.get("version") != kind.root_version:
		begins = f"Die Nutzdaten beginnen nicht mit {kind.root} in der Version {kind.root_version}"
		return None, Message("SIM-003", f"{begins} im Namensraum {kind.namespace}.", ERROR, kind.root)
	for field in ZM_REQUIRED:
		if not _zm_value(root, field.path, kind):
			return None, _missing(field)
	lines = root.findall(_zm_path(ZM_LINES, kind))
	if not lines:
		return None, _missing(ZM_NO_LINE)
	if len(lines) > ZM_MAX_LINES:
		too_many = (
			f"Die Nutzdaten haben {len(lines)} Meldezeilen, ZMDO nimmt höchstens {ZM_MAX_LINES} (max. Zeilen der "
			"Meldezeile in der Jahresdokumentation ZMDO)."
		)
		return None, Message("SIM-009", too_many, ERROR, "zeile")
	seen = set()
	for line in lines:
		for field in ZM_LINE:
			if not _zm_value(line, field.path, kind):
				return None, _missing(field)
		vat_id, art = _zm_value(line, "knre", kind), _zm_value(line, "@umsatzart", kind)
		if (vat_id, art) in seen and art in ZM_TWICE:
			twice = (
				f"Die Meldezeile {vat_id} {art} steht mehr als einmal in den Nutzdaten; ihre Beträge gehören in "
				f"eine Zeile (Regel {ZM_TWICE[art]})."
			)
			return None, Message("SIM-008", twice, ERROR, "zeile")
		seen.add((vat_id, art))
	return root, None


def _zm_filing(root: ElementTree.Element, kind: Datenart) -> list[str]:
	meldeart = _zm_value(root, "unternehmer/zm-zeilen@meldeart", kind)
	quart = _zm_value(root, "unternehmer/zm-zeilen/mzr/quart", kind)
	jahr = _zm_value(root, "unternehmer/zm-zeilen/mzr/jahr", kind)
	return [
		f"Meldezeitraum: {quart}/{jahr}",
		f"Meldeart: {meldeart} ({MELDEARTEN.get(meldeart, 'unbekannt')})",
		f"Meldezeilen: {len(root.findall(_zm_path(ZM_LINES, kind)))}",
	]


def _zm_structure_only(kind: Datenart, reason: str) -> str:
	return ZM_STRUCTURE_ONLY.format(schema=Path(kind.schema).name, reason=reason)


CHECKS: MappingProxyType[str, Checks] = MappingProxyType(
	{
		"UStVA": Checks(
			_anmeldungssteuern,
			_ustva_filing,
			_ustva_structure_only,
			rules=(_wid_nr_check_digit,),
			hints=_ustva_hints,
		),
		"ZMDO": Checks(_zm, _zm_filing, _zm_structure_only, rules=(_own_vat_id_check_digit,)),
		"USt": ust.CHECKS,
		"KSt": kst.CHECKS,
		"GewSt": gewst.CHECKS,
		"Bilanz": bilanz.CHECKS,
	}
)
"""The checks of each Datenart of steuerbote.eric.datenart, by its name."""


def _zm_path(path: str, kind: Datenart) -> str:
	return "/".join(f"{{{kind.namespace}}}{part}" for part in path.split("/")) if path else "."


def _zm_value(element: ElementTree.Element, path: str, kind: Datenart) -> str:
	"""The text of the element at the path below ``element``, or of its attribute after @; empty without one."""
	where, _, attribute = path.partition("@")
	found = element.find(_zm_path(where, kind))
	if found is None:
		return ""
	value = found.get(attribute) if attribute else found.text
	return (value or "").strip()


def _missing(field: ZmField) -> Message:
	return Message("SIM-004", f"{field.text} (Regel {field.code}).", ERROR, field.name)


def _local_name(element: ElementTree.Element) -> str:
	return element.tag.rpartition("}")[2]


def _protocol_lines(
	operation: Operation,
	header: EnvelopeHeader,
	kind: Datenart,
	filing: list[str],
	ticket: str,
	digest: str,
) -> list[str]:
	return [
		"Diese Übermittlung wurde nur simuliert. Es wurde nichts an ELSTER übermittelt.",
		f"Nach einem echten Senden erstellt ERiC an seiner Stelle das {kind.printout}.",
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
