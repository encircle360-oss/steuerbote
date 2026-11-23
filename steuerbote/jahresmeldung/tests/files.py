"""Jahresdokumentationen, schemas and a Datenartversionmatrix written for the tests, in the form of the ERiC
documentation 44.3.6.0, so that the tests of the reader and of the year check need no ERiC documentation.

A Documented holds what a Jahresdokumentation says, sheet by sheet, so that a test can change one fact and write it;
the tests against the documentation itself read it from STEUERBOTE_ERIC_DOC_DIR (steuerbote/elster/tests/eric_schema.py).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from steuerbote.jahresmeldung.documentation import INFORMATION, TEXTS
from steuerbote.ustva.documentation import MATRIX, VERSIONS
from steuerbote.ustva.tests.eric_documentation import spreadsheet

XS = "http://www.w3.org/2001/XMLSchema"
HEADS = {
	"Kontexte": ("Kontext", "max. Wiederholbarkeit", "Annotationen", "Änderungsinformation"),
	"Felder": (
		"Kontext",
		"Name",
		"Beschreibung",
		"max. Zeilen",
		"Format als regulärer Ausdruck",
		"Formatkennzeichen",
		"Min. Länge",
		"Max. Länge",
		"Pflichtfeld",
		"Vordruckzeile",
		"Internes ERiC Feld",
		"Änderungsinformation",
	),
	"Regeln": ("Kontext", "Name", "Fehlercode", "Prüfbedingung", "Regelart", "Änderungsinformation"),
	"Kennzahlen": ("Feldname", "Kennzahl", "Änderungsinformation"),
}
VERSION_HEADS = (
	"Verfahren",
	"Datenart(en)",
	"Jahr / Version",
	"datenartVersion-Parameter",
	"Plugin-Bibliothek",
)

type Rows = list[dict[str, str]]


@dataclass
class Documented:
	"""What a Jahresdokumentation says: the lines of „Allg. Information“, the sheets of each Vordruck by their kind,
	the rows of „Texte“ as they are, and other sheets with a head row by their name."""

	information: list[str] = field(default_factory=list)
	vordrucke: dict[str, dict[str, Rows]] = field(default_factory=dict)
	texts: dict[str, list[list[str]]] = field(default_factory=dict)
	others: dict[str, Rows] = field(default_factory=dict)

	def rows(self, vordruck: str, kind: str) -> Rows:
		return self.vordrucke.setdefault(vordruck, {}).setdefault(kind, [])

	def row(self, vordruck: str, kind: str, **cells: str) -> dict[str, str]:
		"""The one row of a sheet whose cells have the values, such as Name="E3000601"."""
		(found,) = (
			row
			for row in self.rows(vordruck, kind)
			if all(row.get(column) == value for column, value in cells.items())
		)
		return found


def write(path: Path, documented: Documented) -> Path:
	"""The Jahresdokumentation as an OpenDocument spreadsheet, each sheet of a Vordruck with the heads of its kind."""
	sheets: dict[str, Sequence[Sequence[str]]] = {INFORMATION: [[line] for line in documented.information]}
	for vordruck, kinds in documented.vordrucke.items():
		for kind, rows in kinds.items():
			sheets[f"{vordruck} - {kind}"] = _headed(HEADS[kind], rows)
	for vordruck, rows in documented.texts.items():
		sheets[f"{vordruck} - {TEXTS}"] = rows
	for name, rows in documented.others.items():
		heads = tuple(dict.fromkeys(column for row in rows for column in row))
		sheets[name] = _headed(heads, rows)
	return spreadsheet(path, sheets)


def write_matrix(documentation: Path, rows: Sequence[Sequence[str]]) -> Path:
	"""Datenartversionmatrix.ods with the sheet „Datenartversionen“."""
	return spreadsheet(
		documentation / MATRIX, {VERSIONS: [list(VERSION_HEADS), *(list(row) for row in rows)]}
	)


def write_schema(
	path: Path,
	root: str,
	namespace: str,
	version: str | None,
	vordrucke: Mapping[str, Sequence[tuple[str, str, str]]],
	enumerations: Mapping[str, Sequence[str]] = {},
	complex_enumerations: Mapping[str, Sequence[str]] = {},
) -> Path:
	"""A schema whose root holds the Vordrucke in their order, each with its leaves as (context, name, type): every
	context a complex type with a sequence, every type of a leaf with values a simple type that enumerates them, or a
	complex type of simple content as the schemas of the Erklärungen write their lists."""
	schema = ElementTree.Element(f"{{{XS}}}schema", {"targetNamespace": namespace})
	ElementTree.SubElement(schema, f"{{{XS}}}element", {"name": root, "type": f"{root}_CType"})
	root_type = _complex_type(schema, f"{root}_CType", [(name, f"{name}_CType") for name in vordrucke])
	if version is not None:
		ElementTree.SubElement(root_type, f"{{{XS}}}attribute", {"name": "version", "fixed": version})
	for name, leaves in vordrucke.items():
		_contexts(schema, f"{name}_CType", leaves, "")
	for type_name, values in enumerations.items():
		simple = ElementTree.SubElement(schema, f"{{{XS}}}simpleType", {"name": type_name})
		_enumeration(simple, values)
	for type_name, values in complex_enumerations.items():
		complex_type = ElementTree.SubElement(schema, f"{{{XS}}}complexType", {"name": type_name})
		_enumeration(ElementTree.SubElement(complex_type, f"{{{XS}}}simpleContent"), values)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(ElementTree.tostring(schema, encoding="utf-8", xml_declaration=True))
	return path


def _enumeration(parent: ElementTree.Element, values: Sequence[str]) -> None:
	restriction = ElementTree.SubElement(parent, f"{{{XS}}}restriction", {"base": "StringBaseCType"})
	for value in values:
		ElementTree.SubElement(restriction, f"{{{XS}}}enumeration", {"value": value})


def _headed(heads: Sequence[str], rows: Rows) -> list[list[str]]:
	return [list(heads), *([row.get(head, "") for head in heads] for row in rows)]


def _contexts(
	schema: ElementTree.Element, type_name: str, leaves: Sequence[tuple[str, str, str]], context: str
) -> None:
	"""The complex type of a context with its fields and the contexts right below it, in the order of the leaves."""
	elements: list[tuple[str, str]] = []
	below: dict[str, list[tuple[str, str, str]]] = {}
	prefix = f"{context}/" if context else ""
	for leaf_context, name, leaf_type in leaves:
		if leaf_context == context:
			elements.append((name, leaf_type))
			continue
		child = leaf_context.removeprefix(prefix).split("/")[0]
		if child not in below:
			elements.append((child, f"{type_name}_{child}"))
		below.setdefault(child, []).append((leaf_context, name, leaf_type))
	_complex_type(schema, type_name, elements)
	for child, child_leaves in below.items():
		_contexts(schema, f"{type_name}_{child}", child_leaves, f"{prefix}{child}")


def _complex_type(
	schema: ElementTree.Element, name: str, elements: Sequence[tuple[str, str]]
) -> ElementTree.Element:
	complex_type = ElementTree.SubElement(schema, f"{{{XS}}}complexType", {"name": name})
	sequence = ElementTree.SubElement(complex_type, f"{{{XS}}}sequence")
	for element, type_name in elements:
		ElementTree.SubElement(sequence, f"{{{XS}}}element", {"name": element, "type": type_name})
	return complex_type
