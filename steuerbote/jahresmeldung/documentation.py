"""The Jahresdokumentationen of the ERiC documentation as data, which the catalogues of the annual filings and the year
check compare with.

ERiC describes each Datenart of a year, or of a version of the HGB-Taxonomie, in a Jahresdokumentation, an
OpenDocument spreadsheet in Datenarten/<Verfahren>/<Datenart>/Jahresdokumentation below the directory Dokumentation of
the documentation package (ERiC documentation 44.3.6.0, https://download.elster.de/download/eric/eric_44/):

- Jahresdokumentation_E50_<Jahr>.ods, _E30_ and _E20_ for the Erklärungen USt, KSt and GewSt of the Verfahren
  ElsterErklaerung, named after the root of their Nutzdaten, with the schema <root>-<Jahr>.xsd in Schema/<Jahr>;
- Jahresdokumentation_UStVA_<Jahr>.ods for the Voranmeldung of the Verfahren ElsterAnmeldung;
- Jahresdokumentation_Bilanz_Taxonomie_<major>_<minor>.ods for the E-Bilanz of the Verfahren ElsterBilanz.

Each has, per Vordruck, the sheets „<Vordruck> - Kontexte“, „- Felder“, „- Regeln“, „- Kennzahlen“ and „- Texte“,
some of them without one or the other. The Vordrucke of an Erklärung are its forms, such as USt2A, GK or the Vorsatz;
the E-Bilanz has the two Vordrucke Kontext and Header, whose rules are the list of rules ERiC checks a balance sheet
with, and the sheet „Strukturelle Fehler“ with the errors of the XBRL instance itself. „Allg. Information“ names the
Versionslabel of the documentation („Dokumentation erzeugt für VZ 2026 ERiC 44.3 (Versionslabel 9.0)“), the namespace
of the Nutzdaten („Für Nutzdaten muss der Namensraum '…' angegeben werden.“) and each Vordruck with its „max. lfd. Nr.
Vordruck“ and whether it is a Pflichtvordruck. „Allg. Information“ and the sheets „<Vordruck> - Texte“ have no head
row: a row of „Texte“ is the Zeile of the form, the text in the column of its depth, the key of the field („FK“ and
its Feldkennung) or of the block („B“ and a number), and the context and the path of either. Every other sheet has a
head row, and only its current rows count, as steuerbote/ustva/documentation.py reads them.

The files carry no licence that allows passing them on, so the repository holds none of them: read() takes a file of
the unzipped documentation, which find() locates as STEUERBOTE_ERIC_DOC_DIR names it (docs/entwicklung.md). The
spreadsheets are read with tables() and records() of steuerbote/ustva/documentation.py, the schemas with ElementTree;
both from the standard library.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from xml.etree import ElementTree

from steuerbote.elster.erklaerung import Form
from steuerbote.eric.datenart import Datenart
from steuerbote.ustva import documentation as ustva_documentation
from steuerbote.ustva.documentation import MATRIX, VERSIONS, DocumentationError, Row, records, sheets, tables

DATENARTEN = PurePosixPath("Datenarten")
JAHRESDOKUMENTATION = "Jahresdokumentation"
INFORMATION = "Allg. Information"
CONTEXTS = "Kontexte"
FIELDS = "Felder"
RULES = "Regeln"
KENNZAHLEN = "Kennzahlen"
TEXTS = "Texte"
KINDS = (CONTEXTS, FIELDS, RULES, KENNZAHLEN, TEXTS)
"""The sheets of a Vordruck, „<Vordruck> - <kind>“."""
STRUCTURAL_ERRORS = "Strukturelle Fehler"
INTERNAL = "Internes ERiC Feld"
YES = "Ja"
HINT = "Hinweis"
YEAR_PLACEHOLDER = "$VZ$"
"""The year of the Erklärung in the texts of a Jahresdokumentation, such as „Vorauszahlungssoll $VZ$“."""

_SEPARATOR = " - "
_VERSIONSLABEL = re.compile(r"Versionslabel (?P<label>\d+(?:\.\d+)*)")
_NAMESPACE = re.compile(r"Für Nutzdaten muss der Namensraum '(?P<namespace>[^']+)' angegeben werden\.")
_LISTED = re.compile(
	r"(?P<name>\S+) - max\. lfd\. Nr\. Vordruck: (?P<count>\d+)(?P<mandatory> - Pflichtvordruck)?"
)
_KEY = re.compile(r"(?:FK|B) \S.*")
_TAXONOMY_FILE = re.compile(r"Jahresdokumentation_Bilanz_Taxonomie_(?P<major>\d+)_(?P<minor>\d+)\.ods")
_XS = "{http://www.w3.org/2001/XMLSchema}"


@dataclass(frozen=True, slots=True)
class Text:
	"""A row of the sheet „<Vordruck> - Texte“: a text of the printed form, in the order of the form.

	``line`` is the Zeile of the form, empty for a heading; ``depth`` how far the text is indented, 0 for the title of
	the Vordruck; ``key`` is „FK“ and the Feldkennung for the text of a field, „B“ and a number for that of a block, with
	„EZ“ and a number for a further text of it; ``context`` and ``path`` place the field or block in the Nutzdaten,
	empty where the sheet names neither.
	"""

	line: str
	depth: int
	text: str
	key: str
	context: str = ""
	path: str = ""

	@property
	def feldkennung(self) -> str | None:
		"""The Feldkennung of the text of a field, None for a block."""
		kind, _, name = self.key.partition(" ")
		return name if kind == "FK" else None


@dataclass(frozen=True, slots=True)
class Vordruck:
	"""The sheets of a Vordruck: its contexts, fields, rules, Kennzahlen and texts, each in the order of its sheet."""

	name: str
	contexts: tuple[Row, ...] = ()
	fields: tuple[Row, ...] = ()
	rules: tuple[Row, ...] = ()
	kennzahlen: tuple[Row, ...] = ()
	texts: tuple[Text, ...] = ()

	@property
	def filed_fields(self) -> tuple[Row, ...]:
		"""The fields a filing holds: all but those marked „Internes ERiC Feld“, which ERiC fills itself."""
		return tuple(row for row in self.fields if row.get(INTERNAL) != YES)

	def rules_of(self, code: str) -> tuple[Row, ...]:
		"""The rules of the Fehlercode: one, unless the Vordruck has none or the documentation names it twice."""
		return tuple(row for row in self.rules if row.get("Fehlercode") == code)


@dataclass(frozen=True, slots=True)
class Jahresdokumentation:
	"""A Jahresdokumentation: the lines of „Allg. Information“, the Vordrucke in the order of the file and every sheet
	with a head row by its name, among them the sheets of the Vordrucke."""

	file: str
	information: tuple[str, ...]
	vordrucke: Mapping[str, Vordruck]
	sheets: Mapping[str, tuple[Row, ...]]

	@property
	def versionslabel(self) -> str | None:
		"""The Versionslabel of the documentation, such as 9.0, which tells two documentations of a year apart."""
		return next(
			(match["label"] for line in self.information if (match := _VERSIONSLABEL.search(line))), None
		)

	@property
	def namespace(self) -> str | None:
		"""The namespace the Nutzdaten have to name; an earlier one, marked „(alt)“, does not count."""
		return next(
			(match["namespace"] for line in self.information if (match := _NAMESPACE.fullmatch(line))), None
		)

	@property
	def forms(self) -> tuple[Form, ...]:
		"""The Vordrucke as „Allg. Information“ lists them, each with its count and whether it is a Pflichtvordruck."""
		return tuple(
			Form(match["name"], int(match["count"]), match["mandatory"] is not None)
			for line in self.information
			if (match := _LISTED.fullmatch(line))
		)

	@property
	def rules(self) -> tuple[tuple[str, Row], ...]:
		"""Every rule of the documentation with the name of its Vordruck, in the order of the file."""
		return tuple((vordruck.name, rule) for vordruck in self.vordrucke.values() for rule in vordruck.rules)

	@property
	def structural_errors(self) -> tuple[Row, ...]:
		"""The rows of „Strukturelle Fehler“, the errors ERiC reports of an XBRL instance itself, none for an
		Erklärung."""
		return self.sheets.get(STRUCTURAL_ERRORS, ())

	def vordruck(self, name: str) -> Vordruck:
		try:
			return self.vordrucke[name]
		except KeyError:
			raise DocumentationError(f"{self.file} has no Vordruck {name}") from None

	def sheet(self, name: str) -> tuple[Row, ...]:
		"""The current rows of a sheet with a head row."""
		try:
			return self.sheets[name]
		except KeyError:
			raise DocumentationError(f"{self.file} has no sheet {name}") from None


@dataclass(frozen=True, slots=True)
class Leaf:
	"""A field in a schema: the elements between its Vordruck and it, joined by „/“, its name and its type."""

	context: str
	name: str
	type: str


@dataclass(frozen=True, slots=True)
class Schema:
	"""What <root>-<Jahr>.xsd says: its namespace, the fixed version of the root, the leaves of each Vordruck in the
	order of its sequences, and the values of each type that enumerates them."""

	file: str
	namespace: str | None
	version: str | None
	vordrucke: Mapping[str, tuple[Leaf, ...]]
	enumerations: Mapping[str, tuple[str, ...]]


def find(directory: Path) -> Path:
	"""The directory Dokumentation: the directory itself, or the one ERiC-<version>/Dokumentation below it."""
	return ustva_documentation.find(directory, DATENARTEN)


def directory(documentation: Path, kind: Datenart) -> Path:
	"""The directory of the Datenart below the directory Dokumentation, such as Datenarten/ElsterErklaerung/USt."""
	return documentation / DATENARTEN / kind.verfahren / kind.name


def jahresdokumentation_name(kind: Datenart) -> str:
	"""The file of the Jahresdokumentation of the Datenart, by its taxonomy or its year."""
	if kind.taxonomy is not None:
		return f"Jahresdokumentation_Bilanz_Taxonomie_{kind.taxonomy.replace('.', '_')}.ods"
	if kind.year is None:
		raise ValueError(f"the Datenart {kind.name} has a Jahresdokumentation of no year")
	return f"Jahresdokumentation_{_stem(kind)}_{kind.year}.ods"


def jahresdokumentation_path(documentation: Path, kind: Datenart) -> Path:
	return directory(documentation, kind) / JAHRESDOKUMENTATION / jahresdokumentation_name(kind)


def schema_path(documentation: Path, kind: Datenart) -> Path:
	return documentation / kind.schema


def years(documentation: Path, kind: Datenart) -> tuple[int, ...]:
	"""The years of the Datenart whose Jahresdokumentation the documentation holds, whatever the year of ``kind``."""
	pattern = re.compile(rf"Jahresdokumentation_{re.escape(_stem(kind))}_(?P<year>\d{{4}})\.ods")
	return tuple(sorted(int(match["year"]) for match in _matches(documentation, kind, pattern)))


def taxonomies(documentation: Path, kind: Datenart) -> tuple[str, ...]:
	"""The versions of the HGB-Taxonomie whose Jahresdokumentation of the Datenart Bilanz the documentation holds."""
	found = sorted(
		(int(match["major"]), int(match["minor"])) for match in _matches(documentation, kind, _TAXONOMY_FILE)
	)
	return tuple(f"{major}.{minor}" for major, minor in found)


def read(path: Path) -> Jahresdokumentation:
	"""The Jahresdokumentation in the file, refused when it is no spreadsheet or has no „Allg. Information“."""
	found = tables(path)
	if INFORMATION not in found:
		raise DocumentationError(f"{path.name} has no sheet {INFORMATION}")
	information = tuple(row[0] for row in found[INFORMATION] if row and row[0])
	headed = {
		name: records(rows) for name, rows in found.items() if name != INFORMATION and not _is_texts(name)
	}
	parts: dict[str, dict[str, tuple[Row, ...]]] = {}
	texts: dict[str, tuple[Text, ...]] = {}
	for name, rows in found.items():
		vordruck, separator, kind = name.rpartition(_SEPARATOR)
		if separator and kind == TEXTS:
			texts[vordruck] = _texts(path.name, name, rows)
		if separator and kind in KINDS:
			parts.setdefault(vordruck, {})[kind] = headed.get(name, ())
	vordrucke = {
		name: Vordruck(
			name,
			contexts=sheet.get(CONTEXTS, ()),
			fields=sheet.get(FIELDS, ()),
			rules=sheet.get(RULES, ()),
			kennzahlen=sheet.get(KENNZAHLEN, ()),
			texts=texts.get(name, ()),
		)
		for name, sheet in parts.items()
	}
	return Jahresdokumentation(path.name, information, MappingProxyType(vordrucke), MappingProxyType(headed))


def read_schema(path: Path, root: str) -> Schema:
	"""The schema of the Nutzdaten that begin with the element ``root``, such as E50: the Vordrucke in its sequence."""
	try:
		top = ElementTree.parse(path).getroot()  # noqa: S314 - the ERiC documentation, no data of a user
	except (OSError, ElementTree.ParseError) as error:
		raise DocumentationError(f"{path} cannot be read as a schema: {error}") from None
	types = {name: node for node in top.iter(f"{_XS}complexType") if (name := node.get("name"))}
	elements = {element.get("name"): element.get("type", "") for element in top.iterfind(f"{_XS}element")}
	root_type = types.get(elements.get(root, ""))
	version = None if root_type is None else root_type.find(f"{_XS}attribute[@name='version']")
	vordrucke = {name: tuple(_leaves(types, type_name, ())) for name, type_name in _sequence(root_type)}
	enumerations = {
		name: values
		for node in (*top.iter(f"{_XS}complexType"), *top.iter(f"{_XS}simpleType"))
		if (name := node.get("name"))
		and (values := tuple(item.get("value", "") for item in node.iter(f"{_XS}enumeration")))
	}
	return Schema(
		path.name,
		top.get("targetNamespace"),
		None if version is None else version.get("fixed"),
		MappingProxyType(vordrucke),
		MappingProxyType(enumerations),
	)


def datenart_versions(documentation: Path) -> tuple[Row, ...]:
	"""The rows of the sheet „Datenartversionen“ of Datenartversionmatrix.ods."""
	return sheets(documentation / MATRIX, VERSIONS)[VERSIONS]


def matrix_rows(rows: Sequence[Row], kind: Datenart) -> tuple[Row, ...]:
	"""The rows of the matrix that name the datenartVersion of the Datenart, with <Jahr> as its year."""
	year = "" if kind.year is None else str(kind.year)
	return tuple(
		row
		for row in rows
		if row.get("Verfahren") == kind.verfahren
		and row.get("Datenart(en)") == kind.name
		and row.get("datenartVersion-Parameter", "").replace("<Jahr>", year) == kind.version
	)


def _stem(kind: Datenart) -> str:
	"""An Erklärung names its Jahresdokumentation after the root of its Nutzdaten, the UStVA after itself."""
	return kind.root if kind.unterfallart is not None else kind.name


def _matches(documentation: Path, kind: Datenart, pattern: re.Pattern[str]) -> list[re.Match[str]]:
	folder = directory(documentation, kind) / JAHRESDOKUMENTATION
	files = sorted(folder.iterdir()) if folder.is_dir() else []
	return [match for file in files if (match := pattern.fullmatch(file.name))]


def _is_texts(name: str) -> bool:
	return name.endswith(f"{_SEPARATOR}{TEXTS}")


def _texts(file: str, sheet: str, rows: Sequence[Sequence[str]]) -> tuple[Text, ...]:
	"""The rows of a sheet „Texte“; the key is the last cell that names a field or a block, the cells before it from
	the second on are the columns of the depths."""
	texts = []
	for number, row in enumerate(rows, 1):
		if not row:
			continue
		keys = [index for index, cell in enumerate(row) if index and _KEY.fullmatch(cell)]
		if not keys:
			raise DocumentationError(f"{file}, sheet {sheet}, row {number} names no field FK and no block B")
		key = keys[-1]
		columns = row[1:key]
		depth = next((index for index, text in enumerate(columns) if text), 0)
		context, path = (*row[key + 1 : key + 3], "", "")[:2]
		texts.append(Text(row[0], depth, columns[depth] if columns else "", row[key], context, path))
	return tuple(texts)


def _sequence(complex_type: ElementTree.Element | None) -> list[tuple[str, str]]:
	"""The name and type of each element of the xs:sequence of a complex type, none without one."""
	if complex_type is None:
		return []
	return [
		(element.get("name", ""), element.get("type", ""))
		for element in complex_type.iterfind(f"{_XS}sequence/{_XS}element")
	]


def _leaves(types: Mapping[str, ElementTree.Element], type_name: str, path: tuple[str, ...]) -> list[Leaf]:
	"""The leaves below a complex type: an element whose type has a sequence of its own is a context, any other a
	field."""
	found = []
	for name, child in _sequence(types.get(type_name)):
		child_type = types.get(child)
		if child_type is not None and child_type.find(f"{_XS}sequence") is not None:
			found.extend(_leaves(types, child, (*path, name)))
		else:
			found.append(Leaf("/".join(path), name, child))
	return found
