"""The Jahresdokumentationen E30 and E20 and their schemas in the ERiC documentation, read for the tests of the
catalogues, the writers and the simulation of Körperschaftsteuer and Gewerbesteuer.

Like the other files of the ERiC documentation, they carry no licence that allows passing them on, so the tests read
them from the unzipped documentation that STEUERBOTE_ERIC_DOC_DIR names (steuerbote/elster/tests/eric_schema.py),
below Datenarten/ElsterErklaerung/KSt and Datenarten/ElsterErklaerung/GewSt of its directory Dokumentation. Without
such a directory the tests are skipped with a message, as the tests of form USt 2 A are.

The documentation of ERiC 44.3.6.0 ends with the VZ 2025. Nutzdaten of a provisional VZ, written in the namespace and
version of their own year, are checked against the schema of the documentation year after in_documentation_year()
has rewritten both, which only the tests do.
"""

from functools import cache
from pathlib import Path
from types import MappingProxyType
from unittest import SkipTest
from xml.etree import ElementTree

from lxml import etree

from steuerbote.elster.tests import eric_schema
from steuerbote.eric.datenart import Datenart
from steuerbote.ustva import documentation
from steuerbote.ustva.documentation import Row

KST = ("KSt", "E30")
GEWST = ("GewSt", "E20")
_XS = "{http://www.w3.org/2001/XMLSchema}"


def directory(datenart: str) -> Path:
	"""Datenarten/ElsterErklaerung/<datenart> of the documentation; skips the test without it."""
	found = eric_schema.erklaerung_directory(datenart)
	if not found.is_dir():
		raise SkipTest(
			f"{found} is missing: the {datenart} is not checked against the ERiC documentation. Unzip "
			f"*/Datenarten/ElsterErklaerung/{datenart}/* of {eric_schema.DOWNLOAD} as well."
		)
	return found


def jahresdokumentation(datenart: tuple[str, str], year: int) -> Path:
	name, root = datenart
	return directory(name) / "Jahresdokumentation" / f"Jahresdokumentation_{root}_{year}.ods"


def schema(datenart: tuple[str, str], year: int) -> Path:
	name, root = datenart
	return directory(name) / "Schema" / str(year) / f"{root}-{year}.xsd"


def example(datenart: tuple[str, str], file: str) -> Path:
	return directory(datenart[0]) / "Beispiele" / file


@cache
def nutzdaten_schema(datenart: tuple[str, str], year: int) -> etree.XMLSchema:
	"""<root>-<year>.xsd, the schema of the Nutzdaten."""
	return etree.XMLSchema(etree.parse(str(schema(datenart, year))))


def in_documentation_year(nutzdaten: etree._Element, kind: Datenart, documented: Datenart) -> etree._Element:
	"""A copy of Nutzdaten of the Datenart in the namespace and the version of the documented Datenart of the same
	Erklärung: its root and every element below it."""
	text = etree.tostring(nutzdaten, encoding="unicode").replace(kind.namespace, documented.namespace)
	rewritten = etree.fromstring(text)
	if rewritten.get("version") != kind.root_version:
		raise ValueError(f"the Nutzdaten are not those of {kind.version}")
	rewritten.set("version", documented.root_version)
	return rewritten


FORMS = MappingProxyType(
	{KST: ("KSt1", "GK", "ZVE", "Z", "Verluste", "WA", "KSt1F"), GEWST: ("GewSt1A", "BEG")}
)
"""The Vordrucke of Steuerbote's scope, whose sheets the tests read."""


def sheet(datenart: tuple[str, str], year: int, name: str) -> tuple[Row, ...]:
	"""The current rows of a sheet of the Jahresdokumentation of the year."""
	return _sheets(datenart, year)[name]


@cache
def _sheets(datenart: tuple[str, str], year: int) -> dict[str, tuple[Row, ...]]:
	"""The sheets the tests read, from one reading of the spreadsheet."""
	names = [f"{form} - {kind}" for form in FORMS[datenart] for kind in ("Felder", "Kennzahlen", "Regeln")]
	if datenart == GEWST:
		names.remove("BEG - Kennzahlen")
	return documentation.sheets(jahresdokumentation(datenart, year), *names, "Benutzerdefinierte Typen")


def lines(datenart: tuple[str, str], year: int, name: str) -> list[str]:
	"""The first cell of each row of a sheet without a head row, such as „Allg. Information“."""
	return eric_schema.lines(jahresdokumentation(datenart, year), name)


@cache
def leaves(datenart: tuple[str, str], year: int, form: str) -> tuple[tuple[str, str], ...]:
	"""The context and name of each leaf of a Vordruck in the schema, in the order of its sequences."""
	types, forms = _schema(datenart, year)
	found: list[tuple[str, str]] = []
	_walk(types, forms[form][0], (), found)
	return tuple(found)


@cache
def occurrences(datenart: tuple[str, str], year: int) -> dict[str, str]:
	"""The maxOccurs of each Vordruck and context of the schema that repeats, by its path below the root."""
	types, forms = _schema(datenart, year)
	found: dict[str, str] = {}
	for form, (type_name, most) in forms.items():
		if most != "1":
			found[form] = most
		_repeats(types, type_name, form, found)
	return found


@cache
def form_order(datenart: tuple[str, str], year: int) -> tuple[str, ...]:
	"""The Vordrucke in the order of the sequence of the root."""
	return tuple(_schema(datenart, year)[1])


@cache
def _schema(
	datenart: tuple[str, str], year: int
) -> tuple[dict[str, ElementTree.Element], dict[str, tuple[str, str]]]:
	root = ElementTree.parse(schema(datenart, year)).getroot()
	types = {name: node for node in root.iter(f"{_XS}complexType") if (name := node.get("name"))}
	(top,) = (element for element in root.iterfind(f"{_XS}element") if element.get("name") == datenart[1])
	sequence = types[top.get("type", "")].find(f"{_XS}sequence")
	assert sequence is not None
	forms = {
		element.get("name", ""): (element.get("type", ""), element.get("maxOccurs", "1"))
		for element in sequence.iterfind(f"{_XS}element")
	}
	return types, forms


def _sequence(types: dict[str, ElementTree.Element], type_name: str) -> ElementTree.Element | None:
	complex_type = types.get(type_name)
	return None if complex_type is None else complex_type.find(f"{_XS}sequence")


def _walk(
	types: dict[str, ElementTree.Element], type_name: str, path: tuple[str, ...], found: list[tuple[str, str]]
) -> None:
	sequence = _sequence(types, type_name)
	for element in () if sequence is None else sequence.iterfind(f"{_XS}element"):
		name, child = element.get("name", ""), element.get("type", "")
		if _sequence(types, child) is not None:
			_walk(types, child, (*path, name), found)
		else:
			found.append(("/".join(path), name))


def _repeats(types: dict[str, ElementTree.Element], type_name: str, path: str, found: dict[str, str]) -> None:
	sequence = _sequence(types, type_name)
	for element in () if sequence is None else sequence.iterfind(f"{_XS}element"):
		child = element.get("type", "")
		if _sequence(types, child) is None:
			continue
		here = f"{path}/{element.get('name', '')}"
		if element.get("maxOccurs", "1") != "1":
			found[here] = element.get("maxOccurs", "1")
		_repeats(types, child, here, found)
