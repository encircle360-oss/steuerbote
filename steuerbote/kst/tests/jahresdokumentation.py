"""The Jahresdokumentationen E30 and E20 and their schemas in the ERiC documentation, read for the tests of the
catalogues, the writers and the simulation of Körperschaftsteuer and Gewerbesteuer.

Like the other files of the ERiC documentation, they carry no licence that allows passing them on, so the tests read
them from the unzipped documentation that STEUERBOTE_ERIC_DOC_DIR names (steuerbote/elster/tests/eric_schema.py),
below Datenarten/ElsterErklaerung/KSt and Datenarten/ElsterErklaerung/GewSt of its directory Dokumentation, with the
reader of the annual filings (steuerbote/jahresmeldung/documentation.py). Without such a directory the tests are
skipped with a message, as the tests of form USt 2 A are.

The documentation of ERiC 44.3.6.0 ends with the VZ 2025. Nutzdaten of a provisional VZ, written in the namespace and
version of their own year, are checked against the schema of the documentation year after in_documentation_year()
has rewritten both, which only the tests do.
"""

from functools import cache
from pathlib import Path
from types import MappingProxyType
from unittest import SkipTest

from lxml import etree

from steuerbote.elster.tests import eric_schema
from steuerbote.eric.datenart import Datenart
from steuerbote.jahresmeldung import documentation
from steuerbote.jahresmeldung.documentation import Jahresdokumentation, Schema
from steuerbote.ustva.documentation import Row, tables

KST = ("KSt", "E30")
GEWST = ("GewSt", "E20")


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
	return _read(datenart, year).sheet(name)


@cache
def _read(datenart: tuple[str, str], year: int) -> Jahresdokumentation:
	"""The Jahresdokumentation of the year, from one reading of the spreadsheet."""
	return documentation.read(jahresdokumentation(datenart, year))


def lines(datenart: tuple[str, str], year: int, name: str) -> list[str]:
	"""The first cell of each row of a sheet without a head row, such as „Allg. Information“."""
	if name == documentation.INFORMATION:
		return list(_read(datenart, year).information)
	return [row[0] for row in tables(jahresdokumentation(datenart, year), name)[name] if row and row[0]]


@cache
def leaves(datenart: tuple[str, str], year: int, form: str) -> tuple[tuple[str, str], ...]:
	"""The context and name of each leaf of a Vordruck in the schema, in the order of its sequences."""
	return tuple((leaf.context, leaf.name) for leaf in _schema(datenart, year).vordrucke[form])


@cache
def occurrences(datenart: tuple[str, str], year: int) -> dict[str, str]:
	"""The maxOccurs of each Vordruck and context of the schema that repeats, by its path below the root."""
	return dict(_schema(datenart, year).repeats)


@cache
def form_order(datenart: tuple[str, str], year: int) -> tuple[str, ...]:
	"""The Vordrucke in the order of the sequence of the root."""
	return tuple(_schema(datenart, year).vordrucke)


@cache
def _schema(datenart: tuple[str, str], year: int) -> Schema:
	return documentation.read_schema(schema(datenart, year), datenart[1])
