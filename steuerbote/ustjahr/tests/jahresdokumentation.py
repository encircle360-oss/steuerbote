"""Jahresdokumentation_E50_<Jahr>.ods and E50-<Jahr>.xsd of the ERiC documentation, read for the tests of the catalogue.

Like the other files of the ERiC documentation, they carry no licence that allows passing them on, so the tests read
them from the unzipped documentation that STEUERBOTE_ERIC_DOC_DIR names (steuerbote/elster/tests/eric_schema.py), in
Datenarten/ElsterErklaerung/USt below its directory Dokumentation. Without that directory the tests are skipped with a
message, in a CI too, until the CI unzips it along with the files of the UStVA.
"""

from functools import cache
from pathlib import Path
from unittest import SkipTest
from xml.etree import ElementTree

from steuerbote.elster.tests import eric_schema
from steuerbote.ustva import documentation
from steuerbote.ustva.documentation import Row

FIELDS = "USt2A - Felder"
KENNZAHLEN = "USt2A - Kennzahlen"
RULES = "USt2A - Regeln"
INTERNAL = "Ja"
_XS = "{http://www.w3.org/2001/XMLSchema}"


def ust() -> Path:
	"""Datenarten/ElsterErklaerung/USt of the documentation; skips the test without it."""
	directory = eric_schema.documentation() / "Datenarten" / "ElsterErklaerung" / "USt"
	if not directory.is_dir():
		raise SkipTest(
			f"{directory} is missing: the catalogue of form USt 2 A is not checked against the ERiC documentation. "
			f"Unzip */Datenarten/ElsterErklaerung/USt/* of {eric_schema.DOWNLOAD} as well."
		)
	return directory


def jahresdokumentation(year: int) -> Path:
	return ust() / "Jahresdokumentation" / f"Jahresdokumentation_E50_{year}.ods"


def schema(year: int) -> Path:
	return ust() / "Schema" / str(year) / f"E50-{year}.xsd"


@cache
def sheet(year: int, name: str) -> tuple[Row, ...]:
	"""The current rows of a sheet of the Jahresdokumentation of the year."""
	return documentation.sheets(jahresdokumentation(year), name)[name]


def fields(year: int) -> tuple[Row, ...]:
	"""The fields of USt2A that a filing holds: those of the sheet "USt2A - Felder" but ERiC's internal ones."""
	return tuple(row for row in sheet(year, FIELDS) if row["Internes ERiC Feld"] != INTERNAL)


@cache
def leaves(year: int) -> tuple[tuple[str, str], ...]:
	"""The context and name of each leaf of USt2A in the schema, in the order of its sequences."""
	root = ElementTree.parse(schema(year)).getroot()
	types = {name: node for node in root.iter(f"{_XS}complexType") if (name := node.get("name"))}
	(e50,) = (
		element.get("type", "") for element in root.iterfind(f"{_XS}element") if element.get("name") == "E50"
	)
	(ust2a,) = (
		element.get("type", "")
		for element in types[e50].iter(f"{_XS}element")
		if element.get("name") == "USt2A"
	)
	found: list[tuple[str, str]] = []
	_walk(types, ust2a, (), found)
	return tuple(found)


def _walk(
	types: dict[str, ElementTree.Element], type_name: str, path: tuple[str, ...], found: list[tuple[str, str]]
) -> None:
	sequence = types[type_name].find(f"{_XS}sequence") if type_name in types else None
	for element in () if sequence is None else sequence.iterfind(f"{_XS}element"):
		name, child = element.get("name", ""), element.get("type", "")
		child_type = types.get(child)
		if child_type is not None and child_type.find(f"{_XS}sequence") is not None:
			_walk(types, child, (*path, name), found)
		else:
			found.append(("/".join(path), name))
