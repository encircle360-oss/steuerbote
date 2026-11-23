"""Jahresdokumentation, schema and Datenartversionmatrix of a year in the unzipped ERiC documentation, for the year check.

The documentation package is public (https://download.elster.de/download/eric/), but its files carry no licence
that allows passing them on, so the repository holds none of them and the check reads them from the directory the
package was unzipped into. For the Datenart UStVA the package holds, for each year it knows,
Datenarten/ElsterAnmeldung/UStVA/Jahresdokumentation/Jahresdokumentation_UStVA_<Jahr>.ods and
Datenarten/ElsterAnmeldung/UStVA/Schema/<Jahr>/UStVA-<Jahr>.xsd below its directory Dokumentation, and there
Datenartversionmatrix.ods with the datenartVersion and the plugin of each Datenart (ERiC documentation 44.3.6.0).

The Jahresdokumentation and the Datenartversionmatrix are OpenDocument spreadsheets: zips whose content.xml holds
one table:table per sheet. The sheets of the Jahresdokumentation keep the versions of a field or rule that the year
dropped or replaced, marked in the column Änderungsinformation (legend in the sheet "Allg. Information"); only the
current rows count. The standard library reads both the spreadsheets and the schema. tables() gives the rows of a sheet
as they are, for the sheets without a head row such as "Allg. Information", and records() makes rows by their heads
of them, as sheets() does; steuerbote/jahresmeldung/documentation.py reads the Jahresdokumentationen of the annual
filings with both.
"""

import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from xml.etree import ElementTree

USTVA = PurePosixPath("Datenarten/ElsterAnmeldung/UStVA")
FIELDS = "Anmeldungssteuern - Felder"
RULES = "Anmeldungssteuern - Regeln"
MATRIX = "Datenartversionmatrix.ods"
VERSIONS = "Datenartversionen"
# The columns the year check reads, by sheet.
COLUMNS = MappingProxyType(
	{
		FIELDS: (
			"Kontext",
			"Name",
			"Format als regulärer Ausdruck",
			"Formatkennzeichen",
			"Min. Länge",
			"Max. Länge",
			"Vordruckzeile",
		),
		RULES: ("Kontext", "Name", "Fehlercode", "Prüfbedingung", "Regelart"),
		VERSIONS: (
			"Verfahren",
			"Datenart(en)",
			"Jahr / Version",
			"datenartVersion-Parameter",
			"Plugin-Bibliothek",
		),
	}
)
CHANGE = "Änderungsinformation"
OUTDATED = frozenset({"GELOESCHT", "GEAENDERT_ALTE_VERSION"})
# More columns than any sheet has; empty cells at the end of a row repeat up to the last column of the sheet.
MAX_COLUMNS = 64

_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
_CELLS = (f"{_TABLE}table-cell", f"{_TABLE}covered-table-cell")
_XS = "{http://www.w3.org/2001/XMLSchema}"
_ROOT = "Anmeldungssteuern"
_CASES = "Steuerfall"

Row = Mapping[str, str]
Elements = tuple[tuple[str, str], ...]


class DocumentationError(Exception):
	"""The directory holds no ERiC documentation, or not the files of a year."""


@dataclass(frozen=True, slots=True)
class Xsd:
	"""What UStVA-<Jahr>.xsd says: its namespace, the version of Anmeldungssteuern and the contexts of a Steuerfall.

	``contexts`` holds, for each context of the Steuerfall such as Umsatzsteuervoranmeldung, the name and type of its
	elements in the order of their xs:sequence.
	"""

	namespace: str | None
	version: str | None
	contexts: Mapping[str, Elements]


@dataclass(frozen=True, slots=True)
class YearDocumentation:
	"""What the documentation says of one year: the current rows of the two sheets of its Jahresdokumentation, its
	schema and the rows of the Datenartversionmatrix, each with the name of its file."""

	year: int
	jahresdokumentation: str
	fields: tuple[Row, ...]
	rules: tuple[Row, ...]
	schema: str
	xsd: Xsd
	matrix: str
	datenart_versions: tuple[Row, ...]


def find(directory: Path, marker: PurePosixPath = USTVA) -> Path:
	"""The directory Dokumentation: the directory itself, or the one ERiC-<version>/Dokumentation below it, whichever
	holds the directory ``marker``, by default that of the UStVA."""
	candidates = (directory, *sorted(directory.glob("ERiC-*/Dokumentation")))
	found = [candidate for candidate in candidates if (candidate / marker).is_dir()]
	if not found:
		raise DocumentationError(f"{directory} holds no ERiC documentation with {marker}")
	if len(found) > 1:
		names = ", ".join(str(candidate) for candidate in found)
		raise DocumentationError(
			f"{directory} holds the documentation of several ERiC versions, name one of {names}"
		)
	return found[0]


def jahresdokumentation_path(documentation: Path, year: int) -> Path:
	return documentation / USTVA / "Jahresdokumentation" / f"Jahresdokumentation_UStVA_{year}.ods"


def schema_path(documentation: Path, year: int) -> Path:
	return documentation / USTVA / "Schema" / str(year) / f"UStVA-{year}.xsd"


def read(documentation: Path, year: int) -> YearDocumentation:
	"""The Jahresdokumentation, the schema and the Datenartversionmatrix of the year in the directory Dokumentation."""
	jahresdokumentation = jahresdokumentation_path(documentation, year)
	schema = schema_path(documentation, year)
	found = {
		**_with_columns(jahresdokumentation, sheets(jahresdokumentation, FIELDS, RULES)),
		**_with_columns(documentation / MATRIX, sheets(documentation / MATRIX, VERSIONS)),
	}
	return YearDocumentation(
		year,
		jahresdokumentation.name,
		found[FIELDS],
		found[RULES],
		schema.name,
		read_xsd(schema),
		MATRIX,
		found[VERSIONS],
	)


def sheets(path: Path, *names: str) -> dict[str, tuple[Row, ...]]:
	"""The current rows of the named sheets of a spreadsheet, each row by the heads in the first row of its sheet."""
	return {name: records(rows) for name, rows in tables(path, *names).items()}


def tables(path: Path, *names: str) -> dict[str, tuple[tuple[str, ...], ...]]:
	"""The rows of the named sheets of a spreadsheet as they are, every sheet in the order of the file without names.

	A row is the texts of its cells without the empty ones at its end, so an empty row is empty; the rows of every
	version stay, and the first row is a row like the others.
	"""
	try:
		with zipfile.ZipFile(path) as archive:
			content = archive.read("content.xml")
		root = ElementTree.fromstring(content)  # noqa: S314 - the ERiC documentation, no data of a user
	except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as error:
		raise DocumentationError(f"{path} cannot be read as a spreadsheet: {error}") from None
	found = {
		name: tuple(tuple(_cells(row)) for row in table.iter(f"{_TABLE}table-row"))
		for table in root.iter(f"{_TABLE}table")
		if (name := table.get(f"{_TABLE}name", "")) in names or not names
	}
	missing = [name for name in names if name not in found]
	if missing:
		raise DocumentationError(f"{path.name} has no sheet {', '.join(missing)}")
	return found


def records(rows: Sequence[Sequence[str]]) -> tuple[Row, ...]:
	"""The current rows of a sheet that tables() read, each by the heads in its first row; an empty row and the
	versions of a field or rule that the year dropped or replaced are left out."""
	if not rows:
		return ()
	head, *body = rows
	padded = (dict(zip(head, (*row, *[""] * (len(head) - len(row))), strict=False)) for row in body if row)
	return tuple(MappingProxyType(record) for record in padded if record.get(CHANGE) not in OUTDATED)


def _with_columns(path: Path, found: dict[str, tuple[Row, ...]]) -> dict[str, tuple[Row, ...]]:
	"""The sheets, refused when their rows lack a column the check reads, which a renamed head would do."""
	for name, rows in found.items():
		lacking = [column for column in COLUMNS[name] if rows and column not in rows[0]]
		if lacking:
			raise DocumentationError(f"{path.name}, sheet {name}, has no column {', '.join(lacking)}")
	return found


def read_xsd(path: Path) -> Xsd:
	try:
		root = ElementTree.parse(path).getroot()  # noqa: S314 - the ERiC documentation, no data of a user
	except (OSError, ElementTree.ParseError) as error:
		raise DocumentationError(f"{path} cannot be read as a schema: {error}") from None
	types = {
		name: complex_type
		for complex_type in root.iter(f"{_XS}complexType")
		if (name := complex_type.get("name")) is not None
	}
	tops = {element.get("name"): element.get("type", "") for element in root.iterfind(f"{_XS}element")}
	root_type = tops.get(_ROOT, "")
	anmeldung = types.get(root_type)
	version = None if anmeldung is None else anmeldung.find(f"{_XS}attribute[@name='version']")
	cases = dict(_sequence(types, root_type)).get(_CASES, "")
	return Xsd(
		root.get("targetNamespace"),
		None if version is None else version.get("fixed"),
		MappingProxyType({name: _sequence(types, type_name) for name, type_name in _sequence(types, cases)}),
	)


def _sequence(types: Mapping[str, ElementTree.Element], type_name: str) -> Elements:
	"""The name and type of each element in the xs:sequence of the named complex type, none for another type."""
	complex_type = types.get(type_name)
	if complex_type is None:
		return ()
	return tuple(
		(element.get("name", ""), element.get("type", ""))
		for element in complex_type.iterfind(f"{_XS}sequence/{_XS}element")
	)


def _cells(row: ElementTree.Element) -> list[str]:
	cells: list[str] = []
	for cell in row:
		if cell.tag in _CELLS:
			text = "\n".join(_text(paragraph) for paragraph in cell.iterfind(f"{_TEXT}p"))
			repeat = int(cell.get(f"{_TABLE}number-columns-repeated", "1"))
			cells.extend([text] * min(repeat, MAX_COLUMNS))
	while cells and not cells[-1]:
		cells.pop()
	return cells


def _text(element: ElementTree.Element) -> str:
	"""The text of a paragraph, in which OpenDocument writes a run of blanks as text:s with their number."""
	parts = [element.text or ""]
	for child in element:
		if child.tag == f"{_TEXT}s":
			parts.append(" " * int(child.get(f"{_TEXT}c", "1")))
		elif child.tag == f"{_TEXT}tab":
			parts.append("\t")
		elif child.tag == f"{_TEXT}line-break":
			parts.append("\n")
		else:
			parts.append(_text(child))
		parts.append(child.tail or "")
	return "".join(parts)
