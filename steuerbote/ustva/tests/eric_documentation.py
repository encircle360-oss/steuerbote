"""A Jahresdokumentation and a schema written from the data of a year, for the tests that need no ERiC documentation.

They hold what the year check reads, in the form of the ERiC documentation 44.3.6.0, and say what the data say,
so that a test can change one fact and see the check name it. The tests against the documentation itself read it
from STEUERBOTE_ERIC_DOC_DIR, see steuerbote/elster/tests/eric_schema.py.
"""

import re
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from steuerbote.dauerfrist.form import Context
from steuerbote.ustva.documentation import FIELDS, MATRIX, RULES, USTVA, VERSIONS
from steuerbote.ustva.kennzahlen import BALANCE_KENNZAHL, Kind
from steuerbote.ustva.yearcheck import Data

OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
XS = "http://www.w3.org/2001/XMLSchema"
FIELD_HEADS = (
	"Kontext",
	"Name",
	"Beschreibung",
	"Format als regulärer Ausdruck",
	"Formatkennzeichen",
	"Min. Länge",
	"Max. Länge",
	"Vordruckzeile",
	"Änderungsinformation",
)
RULE_HEADS = ("Kontext", "Name", "Fehlercode", "Prüfbedingung", "Regelart", "Änderungsinformation")
VERSION_HEADS = (
	"Verfahren",
	"Datenart(en)",
	"Jahr / Version",
	"datenartVersion-Parameter",
	"Plugin-Bibliothek",
)
# The rows of Datenartversionmatrix.ods of the ERiC documentation 44.3.6.0 for the UStVA and the ZMDO, and one more.
DATENART_VERSIONS = (
	("ElsterAnmeldung", "LStA", "<Jahr>: ab 2016", "LStA_<Jahr>", "checkLStA_<Jahr>"),
	("ElsterAnmeldung", "UStVA", "<Jahr>: ab 2016", "UStVA_<Jahr>", "checkUStVA_<Jahr>"),
	("ElsterExtern", "ZMDO", "", "ZMDO", "checkZMDO"),
)
USTVA_CONTEXT = "Umsatzsteuervoranmeldung"
FORMATS = {
	Kind.BASE: ("N", "U"),
	Kind.TAX: ("P", "%"),
	Kind.FLAG: ("J",),
	Kind.DATE: ("D",),
	Kind.CODE: ("H",),
}
TYPES = {
	Kind.BASE: "Ganzzahl{0}OhneFuehrNull_SType",
	Kind.TAX: "Dezimalzahl{0}OhneFuehrNull_SType",
	Kind.FLAG: "Ja1BaseSType",
	Kind.DATE: "DatumTTpMMpJJJJBekanntBaseSType",
	Kind.CODE: "Enum_Kz500_SType",
}
# Elements of Umsatzsteuervoranmeldung that are no Kennzahl, with their Formatkennzeichen.
OTHER_FIELDS = {
	"Jahr": "C",
	"Zeitraum": "H",
	"Steuernummer": "A",
	"WIdNr": "C",
	"Kz09": "C",
	"Kz500_Begruendung": "C",
}


@dataclass
class Documented:
	"""What a documentation of a year says: the rows of its two sheets and the elements of its schema."""

	year: int
	fields: list[dict[str, str]]
	rules: list[dict[str, str]]
	namespace: str
	version: str
	contexts: dict[str, list[tuple[str, str]]]
	datenart_versions: list[dict[str, str]]

	def field(self, context: str, name: str) -> dict[str, str]:
		(row,) = (
			row for row in self.fields if row["Kontext"] == f"Steuerfall/{context}" and row["Name"] == name
		)
		return row

	def rule(self, name: str, kontext: str = f"Steuerfall/{USTVA_CONTEXT}") -> dict[str, str]:
		(row,) = (row for row in self.rules if row["Kontext"] == kontext and row["Name"] == name)
		return row

	def datenart(self, datenart: str) -> dict[str, str]:
		(row,) = (row for row in self.datenart_versions if row["Datenart(en)"] == datenart)
		return row


def documented(data: Data, year: int | None = None) -> Documented:
	"""What a documentation of the year says that agrees with the data, the year of the schema by default."""
	schema, catalogue = data.schema, data.catalogue
	fields = [_ustva_field(name, schema.order, schema.unsigned, catalogue) for name in schema.elements]
	elements = [(name, _type(name, schema.unsigned, catalogue)) for name in schema.elements]
	contexts: dict[str, list[tuple[str, str]]] = {USTVA_CONTEXT: elements}
	for context in Context:
		contexts[context.value] = [(element, "String_SType") for element in data.layout.elements(context)]
		for field in data.layout.fields[context]:
			fields.append(
				{
					"Kontext": f"Steuerfall/{context.value}",
					"Name": field.element,
					"Beschreibung": field.label,
					"Format als regulärer Ausdruck": field.regex,
					"Formatkennzeichen": field.format.value,
					"Min. Länge": _cell(field.min_length),
					"Max. Länge": _cell(field.max_length),
					"Vordruckzeile": _cell(field.line),
					"Änderungsinformation": "KEIN_DELTA",
				}
			)
	return Documented(
		year or schema.year,
		fields,
		[*_catalogue_rules(catalogue), *_layout_rules(data)],
		schema.namespace,
		str(year or schema.year),
		contexts,
		[dict(zip(VERSION_HEADS, row, strict=True)) for row in DATENART_VERSIONS],
	)


def write(directory: Path, documented: Documented) -> Path:
	"""The directory Dokumentation with the Jahresdokumentation and the schema of the year and the
	Datenartversionmatrix, where the zip of the ERiC documentation unpacks it."""
	documentation = directory / "ERiC-44.3.6.0" / "Dokumentation"
	year = documented.year
	ods = documentation / USTVA / "Jahresdokumentation" / f"Jahresdokumentation_UStVA_{year}.ods"
	xsd = documentation / USTVA / "Schema" / str(year) / f"UStVA-{year}.xsd"
	spreadsheet(
		ods,
		{
			"Allg. Information": [["Deltadokumentation für Datenart UStVA (UStVA) für Anwendung eric"]],
			FIELDS: [
				list(FIELD_HEADS),
				*([row.get(head, "") for head in FIELD_HEADS] for row in documented.fields),
			],
			RULES: [
				list(RULE_HEADS),
				*([row.get(head, "") for head in RULE_HEADS] for row in documented.rules),
			],
		},
	)
	xsd.parent.mkdir(parents=True, exist_ok=True)
	xsd.write_bytes(schema(documented))
	versions = [[row.get(head, "") for head in VERSION_HEADS] for row in documented.datenart_versions]
	spreadsheet(documentation / MATRIX, {VERSIONS: [list(VERSION_HEADS), *versions]})
	return documentation


def spreadsheet(path: Path, sheets: Mapping[str, Sequence[Sequence[str]]]) -> Path:
	"""An OpenDocument spreadsheet whose sheets hold the rows of text, each row ending as LibreOffice ends it."""
	root = ElementTree.Element(f"{{{OFFICE}}}document-content", {f"{{{OFFICE}}}version": "1.2"})
	body = ElementTree.SubElement(
		ElementTree.SubElement(root, f"{{{OFFICE}}}body"), f"{{{OFFICE}}}spreadsheet"
	)
	for name, rows in sheets.items():
		table = ElementTree.SubElement(body, f"{{{TABLE}}}table", {f"{{{TABLE}}}name": name})
		for values in rows:
			row = ElementTree.SubElement(table, f"{{{TABLE}}}table-row")
			for value in values:
				_text_cell(row, value)
			ElementTree.SubElement(
				row, f"{{{TABLE}}}table-cell", {f"{{{TABLE}}}number-columns-repeated": "1024"}
			)
	path.parent.mkdir(parents=True, exist_ok=True)
	with zipfile.ZipFile(path, "w") as archive:
		archive.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
		archive.writestr("content.xml", ElementTree.tostring(root, encoding="utf-8", xml_declaration=True))
	return path


def schema(documented: Documented) -> bytes:
	"""UStVA-<Jahr>.xsd with the root, the Steuerfall and the elements of each context, as the check reads them."""
	attributes = {"targetNamespace": documented.namespace, "elementFormDefault": "qualified"}
	root = ElementTree.Element(f"{{{XS}}}schema", attributes)
	ElementTree.SubElement(
		root, f"{{{XS}}}element", {"name": "Anmeldungssteuern", "type": "Anmeldungssteuern_CType"}
	)
	anmeldung = _complex_type(
		root,
		"Anmeldungssteuern_CType",
		[("Erstellungsdatum", "DatumJJJJMMTTBekanntBaseSType"), ("Steuerfall", "Steuerfall_CType")],
	)
	ElementTree.SubElement(
		anmeldung, f"{{{XS}}}attribute", {"name": "version", "fixed": documented.version, "use": "required"}
	)
	_complex_type(
		root, "Steuerfall_CType", [(context, f"{context}_CType") for context in documented.contexts]
	)
	for context, elements in documented.contexts.items():
		_complex_type(root, f"{context}_CType", elements)
	return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def _ustva_field(
	name: str, order: Sequence[str], unsigned: frozenset[str], catalogue: Mapping
) -> dict[str, str]:
	number = name.removeprefix("Kz")
	row = {"Kontext": f"Steuerfall/{USTVA_CONTEXT}", "Name": name, "Änderungsinformation": "KEIN_DELTA"}
	if name in OTHER_FIELDS:
		return {**row, "Formatkennzeichen": OTHER_FIELDS[name]}
	kennzahl = catalogue[number]
	formats = FORMATS[kennzahl.kind]
	signless = number in unsigned and len(formats) > 1
	return {**row, "Formatkennzeichen": formats[signless], "Vordruckzeile": str(kennzahl.line)}


def _type(name: str, unsigned: frozenset[str], catalogue: Mapping) -> str:
	number = name.removeprefix("Kz")
	if name in OTHER_FIELDS or number not in catalogue:
		return "String_SType"
	return TYPES[catalogue[number].kind].format("NichtNeg" if number in unsigned else "")


def _catalogue_rules(catalogue: Mapping) -> list[dict[str, str]]:
	kontext = f"Steuerfall/{USTVA_CONTEXT}"
	pairs = [
		{
			"Kontext": kontext,
			"Name": f"UStVA_Kz{number}_{kennzahl.tax_kennzahl}_Gemeinsam",
			"Fehlercode": "110085065",
			"Prüfbedingung": f"FelderNichtGemeinsamAngegeben(Kz{number},  Kz{kennzahl.tax_kennzahl}) und\n"
			"KontextAngegeben(RegelKontext)",
			"Regelart": "Fehler",
		}
		for number, kennzahl in catalogue.items()
		if kennzahl.tax_kennzahl
	]
	mandatory = [
		{
			"Kontext": kontext,
			"Name": f"UStVA_Kz{number}_Pflichtfeld",
			"Fehlercode": "110085064",
			"Prüfbedingung": f"FeldNichtAngegeben(Kz{number}) und KontextAngegeben(RegelKontext)",
			"Regelart": "Fehler",
		}
		for number in ("09", BALANCE_KENNZAHL)
	]
	others = [
		{
			"Kontext": kontext,
			"Name": "UStVA_Kz41_Nullwertangabe_Hinweis",
			"Fehlercode": "110085186",
			"Prüfbedingung": "FeldNichtAngegeben(Kz10) und FeldAngegeben(Kz41) und [Kz41] == 0",
			"Regelart": "Hinweis",
		},
		{
			"Kontext": kontext,
			"Name": "UStVA_Kz10_Pflichtfeld",
			"Fehlercode": "110085999",
			"Prüfbedingung": "FeldNichtAngegeben(Kz10) und KontextAngegeben(RegelKontext)",
			"Regelart": "Hinweis",
		},
		{
			"Kontext": kontext,
			"Name": "UStVA_Kz21_22_Gemeinsam",
			"Fehlercode": "110085067",
			"Prüfbedingung": "FelderNichtGemeinsamAngegeben(Kz21, Kz22)",
			"Regelart": "Fehler",
			"Änderungsinformation": "GELOESCHT",
		},
		{
			"Kontext": "Steuerfall",
			"Name": "UStVA_Laenge_Kz09",
			"Fehlercode": "110085046",
			"Prüfbedingung": "(Laenge(Umsatzsteuervoranmeldung/Kz09) != 5) und KontextAngegeben(Umsatzsteuervoranmeldung)",
			"Regelart": "Fehler",
		},
	]
	return [*pairs, *mandatory, *others]


def _layout_rules(data: Data) -> list[dict[str, str]]:
	return [
		{
			"Kontext": "Steuerfall" if rule.context is None else f"Steuerfall/{rule.context.value}",
			"Name": rule.name,
			"Fehlercode": rule.code,
			"Prüfbedingung": "AnzahlAngegebenerKontexte(Umsatzsteuervoranmeldung, Dauerfristverlaengerung) != 1"
			if rule.context is None
			else "KontextAngegeben(RegelKontext)",
			"Regelart": rule.severity.value,
		}
		for rule in data.layout.rules
	]


def _complex_type(
	root: ElementTree.Element, name: str, elements: Sequence[tuple[str, str]]
) -> ElementTree.Element:
	complex_type = ElementTree.SubElement(root, f"{{{XS}}}complexType", {"name": name})
	sequence = ElementTree.SubElement(complex_type, f"{{{XS}}}sequence")
	for element, type_name in elements:
		ElementTree.SubElement(
			sequence, f"{{{XS}}}element", {"name": element, "type": type_name, "minOccurs": "0"}
		)
	return complex_type


def _text_cell(row: ElementTree.Element, value: str) -> None:
	"""A cell as LibreOffice writes it: a paragraph per line, the second and further blanks of a run as text:s."""
	cell = ElementTree.SubElement(row, f"{{{TABLE}}}table-cell")
	for line in value.split("\n") if value else ():
		paragraph = ElementTree.SubElement(cell, f"{{{TEXT}}}p")
		first, *rest = re.split(r"( {2,})", line)
		paragraph.text, last = first, None
		for blanks, after in zip(rest[::2], rest[1::2], strict=True):
			if last is None:
				paragraph.text += " "
			else:
				last.tail = (last.tail or "") + " "
			attributes = {} if len(blanks) == 2 else {f"{{{TEXT}}}c": str(len(blanks) - 1)}
			last = ElementTree.SubElement(paragraph, f"{{{TEXT}}}s", attributes)
			last.tail = after


def _cell(value: int | None) -> str:
	return "" if value is None else str(value)
