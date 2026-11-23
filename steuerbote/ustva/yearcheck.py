"""The data of a year against the ERiC documentation: ``python -m steuerbote.ustva.yearcheck <dir> [<year> ...]``.

<dir> is the directory the documentation package was unzipped into, or its directory Dokumentation, as for
STEUERBOTE_ERIC_DOC_DIR in docs/entwicklung.md; without a year the command checks every year of YEARS. For each year
it reads Jahresdokumentation_UStVA_<Jahr>.ods, cited as JD, UStVA-<Jahr>.xsd and Datenartversionmatrix.ods
(documentation.py) and prints a line for each fact on which they and the data of the year disagree. It ends with 0 when it prints nothing, with 1
when it prints a line and with 2 when the documentation of a year is missing.

It compares
- the catalogue of kennzahlen.py with the fields of the context Umsatzsteuervoranmeldung (JD sheet "Anmeldungssteuern
  - Felder"): which Kennzahlen there are, their kind by Formatkennzeichen (legend in the JD sheet "Allg.
  Information") and their line by Vordruckzeile; with the rules of that context (sheet "Anmeldungssteuern -
  Regeln"): the pairs of a base and its tax that FelderNichtGemeinsamAngegeben files together, and Kz 83 as the one
  Kennzahl a rule makes mandatory; and with the elements of the context in the schema and the kind of their types;
- the schema of the XML writer (SCHEMAS of steuerbote/elster/ustva_xml.py) with the schema: namespace, version and
  the order of the elements, and its Kennzahlen without sign with the types of the schema and the Formatkennzeichen;
- the layout of form USt 1 H (LAYOUTS of steuerbote/dauerfrist/form.py) with the fields and rules of its two
  contexts and with their elements in the schema;
- the datenartVersion and the plugin of the year (steuerbote/ustva/years.py) with the row of the Datenart UStVA in
  Datenartversionmatrix.ods, and those of ZMDO (steuerbote/eric/datenart.py) with its row, which names no year.

A year that a table lacks is a year in the making: the command names those tables and compares the part of the
latest year in its place, so that its lines are what the new year changes. A provisional year comes from the
documentation of a later release of ERiC than the one the CI pins, such as 2027 from Beta ERiC 45.1.5.0 against
44.3.6.0: without years the command passes over it where the documentation holds no Jahresdokumentation of it
(passes_over), and named it ends the check as any year without its documentation does.
"""

import argparse
import re
import sys
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TextIO

from steuerbote.dauerfrist.form import LAYOUTS, Context, Layout
from steuerbote.elster.ustva_xml import SCHEMAS, Schema
from steuerbote.eric.datenart import ZMDO
from steuerbote.ustva import documentation
from steuerbote.ustva.documentation import DocumentationError, Row, YearDocumentation
from steuerbote.ustva.kennzahlen import BALANCE_KENNZAHL, CATALOGUES, Kennzahl, Kind
from steuerbote.ustva.years import YEARS, datenart_version, plugin

UMSATZSTEUERVORANMELDUNG = "Umsatzsteuervoranmeldung"
STEUERFALL = "Steuerfall"
# Kz 09 is the Hersteller-ID, no line of form USt 1 A; the XML writer adds it (JD: „Fünfstellige HerstellerID“).
NOT_ON_THE_FORM = frozenset({"09"})
# The Formatkennzeichen of the JD that the writer takes, by the kind it writes; U and % are those „Ohne Vorzeichen“.
KINDS_BY_FORMAT: MappingProxyType[str, Kind] = MappingProxyType(
	{
		"N": Kind.BASE,
		"U": Kind.BASE,
		"P": Kind.TAX,
		"%": Kind.TAX,
		"J": Kind.FLAG,
		"D": Kind.DATE,
		"H": Kind.CODE,
	}
)
UNSIGNED_FORMATS = frozenset({"U", "%"})
# The schema names its simple types after what they hold, NichtNeg for those without sign (UStVA-2026.xsd).
KINDS_BY_TYPE = (
	("Ganzzahl", Kind.BASE),
	("Dezimalzahl", Kind.TAX),
	("Ja1", Kind.FLAG),
	("DatumTTpMMpJJJJ", Kind.DATE),
	("Enum_", Kind.CODE),
)
UNSIGNED_TYPE = "NichtNeg"
ERROR = "Fehler"
USTVA = ("ElsterAnmeldung", "UStVA")
YEAR_PLACEHOLDER = "<Jahr>"

_KENNZAHL = re.compile(r"Kz(?P<number>\d+)")
_TOGETHER = re.compile(r"FelderNichtGemeinsamAngegeben\(\s*Kz(\d+)\s*,\s*Kz(\d+)\s*\)")
_MANDATORY = re.compile(r"FeldNichtAngegeben\(\s*Kz(\d+)\s*\) und KontextAngegeben\(RegelKontext\)", re.I)
_FIRST_YEAR = re.compile(r"<Jahr>: ab (?P<year>\d{4})")


@dataclass(frozen=True, slots=True)
class Difference:
	"""A fact on which the data of a year and a file of the ERiC documentation disagree."""

	subject: str
	ours: str
	source: str
	documented: str

	def __str__(self) -> str:
		return f"{self.subject}: {self.ours}; {self.source}: {self.documented}"


@dataclass(frozen=True, slots=True)
class Data:
	"""The parts of a year that the check compares; the catalogue does not know its year, so it comes along."""

	catalogue_year: int
	catalogue: Mapping[str, Kennzahl]
	schema: Schema
	layout: Layout


def missing(year: int) -> tuple[str, ...]:
	"""The tables of a year that hold no data for the year, by name and file."""
	tables: tuple[tuple[str, str, Mapping[int, object]], ...] = (
		("YEARS", "steuerbote/ustva/years.py", YEARS),
		("CATALOGUES", "steuerbote/ustva/kennzahlen.py", CATALOGUES),
		("SCHEMAS", "steuerbote/elster/ustva_xml.py", SCHEMAS),
		("LAYOUTS", "steuerbote/dauerfrist/form.py", LAYOUTS),
	)
	return tuple(f"{name} of {path}" for name, path, table in tables if year not in table)


def data_for(year: int) -> Data:
	"""The parts of the year; a part the year does not have yet is that of the latest year that has one."""
	catalogue_year = year if year in CATALOGUES else max(CATALOGUES)
	return Data(
		catalogue_year,
		CATALOGUES[catalogue_year],
		SCHEMAS[year if year in SCHEMAS else max(SCHEMAS)],
		LAYOUTS[year if year in LAYOUTS else max(LAYOUTS)],
	)


def differences(year_documentation: YearDocumentation, data: Data) -> tuple[Difference, ...]:
	"""Every fact on which the data and the documentation of the year disagree."""
	return (
		*_catalogue(year_documentation, data.catalogue_year, data.catalogue),
		*_schema(year_documentation, data.schema),
		*_layout(year_documentation, data.layout),
		*_datenart_versions(year_documentation),
	)


def passes_over(documentation_directory: Path, year: int) -> bool:
	"""Whether a run without years leaves the year out: a provisional year whose Jahresdokumentation the directory
	Dokumentation does not hold, since its release came before the one the year comes from."""
	entry = YEARS.get(year)
	jahresdokumentation = documentation.jahresdokumentation_path(documentation_directory, year)
	return entry is not None and entry.provisional and not jahresdokumentation.is_file()


def check(directory: Path, year: int) -> tuple[Difference, ...]:
	"""The differences between the data of the year and its documentation in the directory."""
	return differences(documentation.read(documentation.find(directory), year), data_for(year))


def main(
	argv: Sequence[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None
) -> int:
	"""The command; stdout and stderr are those of the process unless a test passes its own."""
	stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
	parser = argparse.ArgumentParser(
		prog="python -m steuerbote.ustva.yearcheck",
		description="Compare the data of a year with its Jahresdokumentation and schema in the ERiC documentation.",
	)
	parser.add_argument(
		"documentation", type=Path, help="the unzipped ERiC documentation or its Dokumentation"
	)
	parser.add_argument("years", type=int, nargs="*", help="the years to check, by default those of YEARS")
	arguments = parser.parse_args(argv)
	lines: list[str] = []
	try:
		root = documentation.find(arguments.documentation)
		for year in arguments.years or [year for year in YEARS if not passes_over(root, year)]:
			year_documentation = documentation.read(root, year)
			lacking = missing(year)
			if lacking:
				lines.append(f"{year} is missing in {', '.join(lacking)}; the latest data take its place:")
			lines.extend(str(difference) for difference in differences(year_documentation, data_for(year)))
	except DocumentationError as error:
		stdout.writelines(f"{line}\n" for line in lines)
		stderr.write(f"{error}\n")
		return 2
	stdout.writelines(f"{line}\n" for line in lines)
	return 1 if lines else 0


def _catalogue(doc: YearDocumentation, year: int, catalogue: Mapping[str, Kennzahl]) -> Iterator[Difference]:
	subject, source = f"catalogue {year}", doc.jahresdokumentation
	rows = {
		number: row
		for row in _of(doc.fields, UMSATZSTEUERVORANMELDUNG)
		if (number := _number(row["Name"])) is not None and number not in NOT_ON_THE_FORM
	}
	for number in _numerically(catalogue, rows):
		where, kennzahl, row = f"{subject}, Kz {number}", catalogue.get(number), rows.get(number)
		if kennzahl is None:
			yield Difference(where, "not in the catalogue", source, f"Vordruckzeile {row['Vordruckzeile']}")
		elif row is None:
			yield Difference(where, f"line {kennzahl.line}", source, f"no field Kz{number}")
		else:
			if KINDS_BY_FORMAT.get(row["Formatkennzeichen"]) is not kennzahl.kind:
				format_ = row["Formatkennzeichen"] or "none"
				yield Difference(where, f"kind {kennzahl.kind.value}", source, f"Formatkennzeichen {format_}")
			if row["Vordruckzeile"] != str(kennzahl.line):
				line = row["Vordruckzeile"] or "none"
				yield Difference(where, f"line {kennzahl.line}", source, f"Vordruckzeile {line}")
	yield from _catalogue_rules(doc, subject, catalogue)
	yield from _catalogue_types(doc, subject, catalogue)


def _catalogue_rules(
	doc: YearDocumentation, subject: str, catalogue: Mapping[str, Kennzahl]
) -> Iterator[Difference]:
	source = doc.jahresdokumentation
	together: dict[frozenset[str], str] = {}
	mandatory: dict[str, str] = {}
	for row in _of(doc.rules, UMSATZSTEUERVORANMELDUNG):
		condition = " ".join(row["Prüfbedingung"].split())
		for pair in _TOGETHER.findall(condition):
			together[frozenset(pair)] = _rule(row)
		match = _MANDATORY.fullmatch(condition)
		if match and row["Regelart"] == ERROR and match[1] not in NOT_ON_THE_FORM:
			mandatory[match[1]] = _rule(row)
	pairs = {frozenset((number, k.tax_kennzahl)) for number, k in catalogue.items() if k.tax_kennzahl}
	for pair in sorted(pairs | together.keys(), key=lambda pair: sorted(int(number) for number in pair)):
		where = f"{subject}, Kz {' and Kz '.join(sorted(pair, key=int))}"
		if pair not in together:
			yield Difference(where, "a base and its tax", source, "no rule files them together")
		elif pair not in pairs:
			yield Difference(where, "no base and its tax", source, f"filed together, {together[pair]}")
	for number in _numerically(mandatory, (BALANCE_KENNZAHL,)):
		where = f"{subject}, Kz {number}"
		if number not in mandatory:
			yield Difference(where, "always written", source, "no rule makes it mandatory")
		elif number != BALANCE_KENNZAHL:
			yield Difference(where, "written with an amount only", source, f"mandatory, {mandatory[number]}")


def _catalogue_types(
	doc: YearDocumentation, subject: str, catalogue: Mapping[str, Kennzahl]
) -> Iterator[Difference]:
	elements = doc.xsd.contexts.get(UMSATZSTEUERVORANMELDUNG)
	if elements is None:
		yield Difference(subject, "its Kennzahlen", doc.schema, f"no element {UMSATZSTEUERVORANMELDUNG}")
		return
	types = {
		number: type_name
		for name, type_name in elements
		if (number := _number(name)) is not None and number not in NOT_ON_THE_FORM
	}
	for number in _numerically(catalogue, types):
		where, kennzahl, type_name = f"{subject}, Kz {number}", catalogue.get(number), types.get(number)
		if kennzahl is None:
			yield Difference(where, "not in the catalogue", doc.schema, f"element of type {type_name}")
		elif type_name is None:
			yield Difference(where, f"line {kennzahl.line}", doc.schema, f"no element Kz{number}")
		elif _kind_of_type(type_name) is not kennzahl.kind:
			yield Difference(where, f"kind {kennzahl.kind.value}", doc.schema, f"type {type_name}")


def _schema(doc: YearDocumentation, schema: Schema) -> Iterator[Difference]:
	subject = f"schema {schema.year}"
	if schema.namespace != doc.xsd.namespace:
		yield Difference(f"{subject}, namespace", schema.namespace, doc.schema, doc.xsd.namespace or "none")
	if str(schema.year) != doc.xsd.version:
		yield Difference(f"{subject}, version", str(schema.year), doc.schema, doc.xsd.version or "none")
	yield from _elements(
		doc, f"{subject}, {UMSATZSTEUERVORANMELDUNG}", schema.elements, UMSATZSTEUERVORANMELDUNG
	)
	types = {
		number: type_name
		for name, type_name in doc.xsd.contexts.get(UMSATZSTEUERVORANMELDUNG, ())
		if (number := _number(name)) is not None
	}
	formats = {
		number: row["Formatkennzeichen"]
		for row in _of(doc.fields, UMSATZSTEUERVORANMELDUNG)
		if (number := _number(row["Name"])) is not None
	}
	for number in schema.order:
		where, unsigned = f"{subject}, Kz {number}", number in schema.unsigned
		ours = "without sign" if unsigned else "with sign"
		if number in types and (UNSIGNED_TYPE in types[number]) != unsigned:
			yield Difference(where, ours, doc.schema, f"type {types[number]}")
		if number in formats and (formats[number] in UNSIGNED_FORMATS) != unsigned:
			format_ = formats[number] or "none"
			yield Difference(where, ours, doc.jahresdokumentation, f"Formatkennzeichen {format_}")


def _layout(doc: YearDocumentation, layout: Layout) -> Iterator[Difference]:
	source = doc.jahresdokumentation
	for context in Context:
		subject = f"layout {layout.year}, {context.value}"
		rows = {row["Name"]: row for row in _of(doc.fields, context.value)}
		if rows:
			yield from _order(subject, layout.elements(context), list(rows), source)
		else:
			yield Difference(subject, "its fields", source, "no field of the context")
		for field in layout.fields[context]:
			row = rows.get(field.element)
			if row is None:
				continue
			for column, ours in (
				("Format als regulärer Ausdruck", field.regex),
				("Formatkennzeichen", field.format.value),
				("Min. Länge", _cell(field.min_length)),
				("Max. Länge", _cell(field.max_length)),
				("Vordruckzeile", _cell(field.line)),
			):
				if row[column] != ours:
					where, theirs = f"{subject}, {field.element}", row[column] or "none"
					yield Difference(where, f"{column} {ours or 'none'}", source, f"{column} {theirs}")
		yield from _elements(doc, subject, layout.elements(context), context.value)
	yield from _layout_rules(doc, layout)


def _layout_rules(doc: YearDocumentation, layout: Layout) -> Iterator[Difference]:
	"""The rules of the two contexts, and those of the whole Steuerfall that name one of them."""
	contexts = {_kontext(context.value) for context in Context}
	documented = {
		(row["Kontext"], row["Name"]): f"{row['Fehlercode']}, {row['Regelart']}"
		for row in doc.rules
		if row["Kontext"] in contexts
		or (
			row["Kontext"] == STEUERFALL and any(context.value in row["Prüfbedingung"] for context in Context)
		)
	}
	ours = {
		(STEUERFALL if rule.context is None else _kontext(rule.context.value), rule.name): (
			f"{rule.code}, {rule.severity.value}"
		)
		for rule in layout.rules
	}
	for key in sorted(ours.keys() | documented.keys()):
		ours_text, documented_text = ours.get(key, "no such rule"), documented.get(key, "no such rule")
		if ours_text != documented_text:
			where = f"layout {layout.year}, rule {key[1]} of {key[0]}"
			yield Difference(where, ours_text, doc.jahresdokumentation, documented_text)


def _datenart_versions(doc: YearDocumentation) -> Iterator[Difference]:
	"""The datenartVersion and plugin of the year, and those of ZMDO, which are the same for every year."""
	rows = {(row["Verfahren"], row["Datenart(en)"]): row for row in doc.datenart_versions}
	subject, source, year = f"plugin {doc.year}", doc.matrix, doc.year
	ustva = rows.get(USTVA)
	if ustva is None:
		yield Difference(subject, plugin(year), source, "no row of the Datenart UStVA")
	else:
		for column, ours in (
			("datenartVersion-Parameter", datenart_version(year)),
			("Plugin-Bibliothek", plugin(year)),
		):
			documented = ustva[column].replace(YEAR_PLACEHOLDER, str(year))
			if documented != ours:
				yield Difference(subject, ours, source, f"{column} {documented or 'none'}")
		first = _FIRST_YEAR.fullmatch(ustva["Jahr / Version"])
		if first is None or year < int(first["year"]):
			years = ustva["Jahr / Version"] or "none"
			yield Difference(subject, f"the year {year}", source, f"Jahr / Version {years}")
	zmdo = rows.get((ZMDO.verfahren, ZMDO.name))
	ours = f"no year, {ZMDO.version}, {ZMDO.plugin}"
	if zmdo is None:
		yield Difference("ZMDO", ours, source, "no row of the Datenart ZMDO")
	else:
		documented = ", ".join(
			(
				zmdo["Jahr / Version"] or "no year",
				zmdo["datenartVersion-Parameter"],
				zmdo["Plugin-Bibliothek"],
			)
		)
		if documented != ours:
			yield Difference("ZMDO", ours, source, documented)


def _elements(
	doc: YearDocumentation, subject: str, ours: Sequence[str], context: str
) -> Iterator[Difference]:
	"""The elements of a context against those of the context in the schema."""
	elements = doc.xsd.contexts.get(context)
	if elements is None:
		yield Difference(subject, "its elements", doc.schema, f"no element {context}")
	else:
		yield from _order(subject, ours, [name for name, _ in elements], doc.schema)


def _order(subject: str, ours: Sequence[str], documented: Sequence[str], source: str) -> Iterator[Difference]:
	"""The elements only one side has, then the first two that both have in another order."""
	for element in ours:
		if element not in documented:
			yield Difference(f"{subject}, {element}", "an element", source, "no such element")
	for element in documented:
		if element not in ours:
			yield Difference(f"{subject}, {element}", "no such element", source, "an element")
	common = [element for element in ours if element in documented]
	documented_common = [element for element in documented if element in ours]
	for element, other in zip(common, documented_common, strict=True):
		if element != other:
			yield Difference(
				f"{subject}, order", f"{element} before {other}", source, f"{other} before {element}"
			)
			return


def _of(rows: Iterable[Row], context: str) -> Iterator[Row]:
	kontext = _kontext(context)
	return (row for row in rows if row["Kontext"] == kontext)


def _kontext(context: str) -> str:
	return f"{STEUERFALL}/{context}"


def _number(name: str) -> str | None:
	match = _KENNZAHL.fullmatch(name)
	return match["number"] if match else None


def _kind_of_type(type_name: str) -> Kind | None:
	return next((kind for prefix, kind in KINDS_BY_TYPE if type_name.startswith(prefix)), None)


def _numerically(*groups: Iterable[str]) -> list[str]:
	return sorted({number for group in groups for number in group}, key=int)


def _rule(row: Row) -> str:
	return f"rule {row['Fehlercode']} {row['Name']}"


def _cell(value: int | None) -> str:
	return "" if value is None else str(value)


if __name__ == "__main__":
	sys.exit(main())
