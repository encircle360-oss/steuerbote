"""The data of the annual filings and of the Voranmeldung against the ERiC documentation, which says what a
Jahreswechsel changes: ``python -m steuerbote.jahresmeldung.yearcheck <dir> [<Datenart> ...] [<year> ...]``.

<dir> is the directory the documentation package was unzipped into, or its directory Dokumentation, as for
STEUERBOTE_ERIC_DOC_DIR in docs/entwicklung.md. MODULES holds the year check of each Datenart: the Voranmeldung
(UStVA), the Erklärungen USt, KSt and GewSt, and the E-Bilanz (Bilanz). The command runs the Datenarten it is given,
every one without, for the years it is given, else for every year of their year tables; a version of the
HGB-Taxonomie such as 6.10 is a key of the Bilanz alone. Each check prints a line for each fact on which Steuerbote
and the documentation disagree, left what Steuerbote says, right the file and what it says, as
steuerbote/ustva/yearcheck.py does, with the Datenart and the year or version in front. Run for the years of its
tables, a check also names the years and versions the documentation holds beyond them. The command ends with 0 when
it prints nothing, with 1 when it prints a line and with 2 when the documentation lacks a file it reads.

A year a table lacks is a year in the making: its first line names those tables, and the data of the latest year take
its place, so that the lines that follow are what the new year changes. A provisional year, such as KSt and GewSt
2026, whose forms are those of the Jahresdokumentation 2025 (steuerbote/kst/years.py), is compared with the newest
Jahresdokumentation the documentation holds up to its year; a line says so where that is not the one the year takes.

What each check compares, JD standing for the Jahresdokumentation of the year:

- UStVA: what steuerbote/ustva/yearcheck.py compares.
- USt: the catalogue of the XML (SCHEMAS of steuerbote/elster/ust2a_xml.py, a FormCatalogue) with the JD E50 and
  E50-<Jahr>.xsd (form_catalogue_differences); the rules of form USt 2 A (CATALOGUES of steuerbote/ustjahr/form.py)
  with the sheet „USt2A - Regeln“; each rule Steuerbote checks itself (LOCAL_RULES of steuerbote/ustjahr/rules.py)
  with its Prüfbedingung, and every rule of USt2A either checked or left to ERiC (LEFT_TO_ERIC); the texts of the
  Vorsatz (TEXTS of steuerbote/elster/vorsatz.py) with the sheet „Vorsatz - Felder“; the datenartVersion and the
  plugin of the year with Datenartversionmatrix.ods.
- KSt and GewSt: each rule of the JD E30 or E20 that the core computes (expected_rules of the modules in
  ``expecting``) by its Fehlercode and the terms of its Prüfbedingung (steuerbote.kst.years.RuleExpectation); the
  catalogue of the Vordrucke (CATALOGUES of steuerbote/kst/form.py and steuerbote/gewst/form.py) as for USt; what the
  writer takes from the schema besides it (SCHEMAS of steuerbote/elster/kst_xml.py and gewst_xml.py): the contexts
  that repeat with their maxOccurs and the Vordrucke that begin with the Indexfeld; the categories of the Rechtsformen
  Steuerbote files (RECHTSFORMEN) with their enumeration in the sheet „Benutzerdefinierte Typen“; the Vorsatz and the
  plugin.
- Bilanz: each version of TAXONOMIES (steuerbote/xbrl/versions.py) with its Jahresdokumentation_Bilanz_Taxonomie, the
  rules a module of the E-Bilanz computes of it (BILANZ_EXPECTING, functions of the version) and its row in the
  matrix; a year by the versions of its fiscal year, that of BILANZ_TAXONOMIES of steuerbote/eric/releases.py or else
  those the BMF letters allow for it (versions.allowed_for).

A module plugs in where its data are: a new table of a year joins the tables of its check, a new module of the core
that computes rules of the JD the ``expecting`` of its IncomeTax, and a module that computes rules of the E-Bilanz
BILANZ_EXPECTING.
"""

import argparse
import re
import sys
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import TextIO

from steuerbote.elster import gewst_xml, kst_xml, ust2a_xml, vorsatz
from steuerbote.elster.erklaerung import Field, FormCatalogue
from steuerbote.eric import releases
from steuerbote.eric.datenart import Datenart, bilanz, gewst, kst, ust, ustva
from steuerbote.eric.simulation import bilanz as bilanz_simulation
from steuerbote.gewst import chain as gewst_chain
from steuerbote.gewst import form as gewst_form
from steuerbote.gewst import years as gewst_years
from steuerbote.jahresmeldung import documentation
from steuerbote.jahresmeldung.documentation import (
	HINT,
	YEAR_PLACEHOLDER,
	YES,
	Jahresdokumentation,
	Schema,
	datenart_versions,
	jahresdokumentation_name,
	jahresdokumentation_path,
	matrix_rows,
	read,
	read_schema,
	schema_path,
	taxonomies,
)
from steuerbote.kst import chain as kst_chain
from steuerbote.kst import einlagekonto, losses
from steuerbote.kst import form as kst_form
from steuerbote.kst import years as kst_years
from steuerbote.kst.years import RuleExpectation
from steuerbote.ustjahr import defaults as ustjahr_defaults
from steuerbote.ustjahr import form as ustjahr_form
from steuerbote.ustjahr import rules as ustjahr_rules
from steuerbote.ustjahr import years as ustjahr_years
from steuerbote.ustva import documentation as ustva_documentation
from steuerbote.ustva import yearcheck as ustva_yearcheck
from steuerbote.ustva import years as ustva_years
from steuerbote.ustva.documentation import MATRIX, DocumentationError, Row
from steuerbote.ustva.yearcheck import Difference
from steuerbote.xbrl import versions

USTVA, UST, KST, GEWST, BILANZ = "UStVA", "USt", "KSt", "GewSt", "Bilanz"
MAIN_FORM = "USt2A"
VORSATZ = "Vorsatz"
NO = "Nein"
ERROR = "Fehler"
MITWIRKUNG = "Mitwirk/"
# Jahresdokumentation_E50_2026.ods puts the Mitwirkung einer Steuerberatung in line 23 and its statement E3002602 in
# line 123; form USt 2 A prints them after line 126 (steuerbote/ustjahr/form.py).
MITWIRKUNG_LINE = "23"
MITWIRKUNG_LINES = MappingProxyType({"E3002602": "123"})
YEAR = "<Jahr>"
TAXONOMY_ROW = "HGB-Taxonomie "

_YEAR_ARGUMENT = re.compile(r"\d{4}")
_TAXONOMY_ARGUMENT = re.compile(r"\d+\.\d+")
_FROM_YEAR = re.compile(r"<Jahr>: ab (?P<year>\d{4})")
_LISTED_YEARS = re.compile(r"<Jahr>: (?P<years>\d{4}(?:, \d{4})*)")
_FIELD_LIST = re.compile(r"\(((?:e\d{7},)+e\d{7})\)")
_CONJUNCTION = re.compile(r"[()]|und")
_RECHTSFORM = re.compile(r"- (?P<code>\d+) \[[^\]]*\] (?P<categories>.*)")
_CATEGORY = re.compile(r"(\w+): (\w+)")
TYPES = "Benutzerdefinierte Typen"


@dataclass(frozen=True, slots=True)
class Table:
	"""A table keyed by the year or the version, by its name and file, as the line of a year in the making names it."""

	name: str
	file: str
	keys: Collection[int | str]


@dataclass(frozen=True, slots=True)
class Module:
	"""The year check of a Datenart.

	``keys`` are the years or versions of its year table, which the command checks when it is given none; ``check``
	gives the lines of one of them, or of a year, against the directory Dokumentation and raises DocumentationError
	when the documentation lacks a file it reads; ``beyond`` gives the lines for what the documentation holds beyond
	the year table.
	"""

	name: str
	keys: Callable[[], tuple[int | str, ...]]
	check: Callable[[Path, int | str], Iterator[str]]
	beyond: Callable[[Path], Iterator[str]]


@dataclass(frozen=True, slots=True)
class IncomeTax:
	"""The year check of an Erklärung whose year may take the forms of an earlier Jahresdokumentation: KSt and GewSt.

	``years`` is the year table, whose entries name their ``documentation_year``, whether they are ``provisional``, and
	their ``jahresdokumentation`` (steuerbote/kst/years.py, steuerbote/gewst/years.py); ``expecting`` are the modules
	of the core with ``expected_rules(year)``; ``tables`` the tables keyed by the year, YEARS first; ``catalogues`` the
	catalogues of the Vordrucke by year, ``xml_schemas`` what the writer takes from the schema besides them, and
	``rechtsformen`` the categories of the Rechtsformen Steuerbote files, with the type of the sheet „Benutzerdefinierte
	Typen“ that enumerates them (``rechtsform_type``, its name and version).
	"""

	name: str
	years: Mapping[int, kst_years.Year | gewst_years.Year]
	datenart: Callable[[int], Datenart]
	expecting: tuple[ModuleType, ...]
	tables: tuple[Table, ...]
	catalogues: Mapping[int, FormCatalogue]
	xml_schemas: Mapping[int, kst_xml.Schema]
	rechtsformen: Mapping[int, Mapping[str, Mapping[str, str]]]
	rechtsform_type: tuple[str, str]

	def check(self, root: Path, year: int | str) -> Iterator[str]:
		"""The lines of the year: the rules the core computes, the catalogue of the XML, the Vorsatz and the plugin,
		against the Jahresdokumentation of the year, or the newest up to it for a provisional year."""
		year = int(year)
		subject = f"{self.name} {year}"
		data, kind = latest(self.years, year), self.datenart(year)
		documentation_year = data.documentation_year
		differences: list[Difference] = []
		if data.provisional or year not in self.years:
			folder = jahresdokumentation_path(root, kind).parent
			documented = [found for found in documentation.years(root, kind) if found <= year]
			if not documented:
				raise DocumentationError(f"{folder} holds no Jahresdokumentation up to {year}")
			documentation_year = documented[-1]
			if documentation_year != data.documentation_year:
				newest = jahresdokumentation_name(self.datenart(documentation_year))
				differences.append(
					Difference(
						f"{subject}, Jahresdokumentation",
						f"{data.jahresdokumentation}, provisionally",
						str(folder.relative_to(root)),
						f"{newest}, the newest up to {year}",
					)
				)
		jd = read(jahresdokumentation_path(root, self.datenart(documentation_year)))
		lacking = missing(year, self.tables)
		if lacking:
			yield making(subject, lacking)
		for module in self.expecting:
			for expectation in module.expected_rules(data.year):
				differences.extend(expectation_differences(subject, expectation, jd, _file_of(module)))
		xsd = read_schema(schema_path(root, self.datenart(documentation_year)), kind.root)
		catalogue = latest(self.catalogues, year)
		differences.extend(
			form_catalogue_differences(subject, catalogue, jd, xsd, documentation_year == year)
		)
		differences.extend(
			xml_schema_differences(subject, latest(self.xml_schemas, year), catalogue, jd, xsd)
		)
		rechtsformen = latest(self.rechtsformen, year)
		differences.extend(rechtsform_differences(subject, rechtsformen, self.rechtsform_type, jd))
		differences.extend(vorsatz_differences(subject, jd))
		differences.extend(plugin_differences(subject, kind, datenart_versions(root)))
		yield from (str(difference) for difference in differences)

	def beyond(self, root: Path) -> Iterator[str]:
		"""The years the documentation holds a Jahresdokumentation of beyond YEARS."""
		return _beyond_years(self.name, root, self.datenart, self.tables[0])

	@property
	def module(self) -> Module:
		return Module(self.name, lambda: tuple(self.years), self.check, self.beyond)


def missing(key: int | str, tables: Iterable[Table]) -> tuple[str, ...]:
	"""The tables that hold nothing for the year or version, by name and file."""
	return tuple(f"{table.name} of {table.file}" for table in tables if key not in table.keys)


def making(subject: str, lacking: Sequence[str]) -> str:
	"""The first line of a year in the making, which names the tables it is missing in."""
	return f"{subject} is missing in {', '.join(lacking)}; the latest data take its place:"


def latest[T](table: Mapping[int, T], year: int) -> T:
	"""The entry of the year, or that of the latest year for a year in the making."""
	return table[year] if year in table else table[max(table)]


def conjuncts(text: str) -> set[str]:
	"""The parts of a condition that „Und“ joins outside brackets, without blanks, in lower case and with each list of
	fields sorted: the JD writes „Und“ and „und“, spaces at will and the fields of a list in any order."""
	text = _FIELD_LIST.sub(_sorted_fields, re.sub(r"\s+", "", text).lower())
	parts, depth, start = [], 0, 0
	for match in _CONJUNCTION.finditer(text):
		if match[0] == "(":
			depth += 1
		elif match[0] == ")":
			depth -= 1
		elif depth == 0:
			parts.append(text[start : match.start()])
			start = match.end()
	parts.append(text[start:])
	return set(parts)


def form_catalogue_differences(
	subject: str,
	catalogue: FormCatalogue,
	jd: Jahresdokumentation,
	xsd: Schema,
	own_year: bool = True,
	expected_line: Callable[[Field], str] | None = None,
) -> Iterator[Difference]:
	"""The form catalogue of an Erklärung against the Jahresdokumentation and the schema it comes from.

	It compares the source, which names the file and its Versionslabel, with them; the Vordrucke with those of „Allg.
	Information“, a Pflichtvordruck the catalogue lacks included, and with those of the schema, their order and their
	maxOccurs; per Vordruck with fields, the fields with the filed fields of the JD and the leaves of the schema, each
	in its order and without the Indexfeld, which numbers a Vordruck and is none of its fields; per field its context,
	Formatkennzeichen, Vordruckzeile (``expected_line`` gives the line of the JD where the form prints another),
	Kennzahl with or without its Sachbereich, Pflichtfeld, max. Zeilen, Beschreibung (with or without the year for
	„$VZ$“), the Max. Länge of a text, the pattern and the values of a list; and the rules of the catalogue by
	Fehlercode. Namespace and version count only where the JD is that of the year of the catalogue (``own_year``),
	which the one of a provisional year is not.
	"""
	described = f"Versionslabel {jd.versionslabel or 'none'}"
	label = re.compile(rf"{re.escape(described)}(?![\d.])")
	if jd.file not in catalogue.source or not label.search(catalogue.source):
		yield Difference(f"{subject}, source", catalogue.source, jd.file, described)
	kind = catalogue.datenart
	if own_year:
		for where, ours, file, theirs in (
			("namespace", kind.namespace, jd.file, jd.namespace),
			("namespace", kind.namespace, xsd.file, xsd.namespace),
			("version", kind.root_version, xsd.file, xsd.version),
		):
			if ours != theirs:
				yield Difference(f"{subject}, {where}", ours, file, theirs or "none")
	yield from _forms(subject, catalogue, jd)
	yield from _schema_forms(subject, catalogue, xsd)
	for form in dict.fromkeys(field_.form for field_ in catalogue.fields):
		fields = [field_ for field_ in catalogue.fields if field_.form == form]
		if form not in jd.vordrucke:
			yield Difference(f"{subject}, {form}", "its fields", jd.file, f"no Vordruck {form}")
		else:
			yield from _fields(subject, form, fields, jd, xsd, expected_line or _line, str(kind.year))
	yield from _rules(subject, catalogue, jd)


def expectation_differences(
	subject: str, expectation: RuleExpectation, jd: Jahresdokumentation, file: str
) -> Iterator[Difference]:
	"""A rule the core computes against the rule of its Fehlercode in its Vordruck: one difference if it is missing or
	there twice, else one for each term its Prüfbedingung lacks."""
	where = f"{subject}, rule {expectation.code} of {expectation.form}"
	vordruck = jd.vordrucke.get(expectation.form)
	if vordruck is None:
		yield Difference(where, f"computed in {file}", jd.file, f"no Vordruck {expectation.form}")
		return
	rules = vordruck.rules_of(expectation.code)
	if len(rules) != 1:
		yield Difference(where, f"computed in {file}", jd.file, f"{len(rules) or 'no'} such rules")
		return
	for term in expectation.missing_terms(rules[0].get("Prüfbedingung", "")):
		yield Difference(where, term, jd.file, "not in its Prüfbedingung")


def vorsatz_differences(subject: str, jd: Jahresdokumentation) -> Iterator[Difference]:
	"""The texts of the Vorsatz, their length and whether a rule requires them, against „Vorsatz - Felder“."""
	if VORSATZ not in jd.vordrucke:
		yield Difference(f"{subject}, {VORSATZ}", "its texts", jd.file, f"no Vordruck {VORSATZ}")
		return
	rows = {row.get("Name", ""): row for row in jd.vordruck(VORSATZ).fields}
	for name, (length, required) in vorsatz.TEXTS.items():
		where, row = f"{subject}, {VORSATZ}, {name}", rows.get(name)
		ours = f"Max. Länge {length}, Pflichtfeld {YES if required else NO}"
		if row is None:
			yield Difference(where, ours, jd.file, "no such field")
		else:
			theirs = (
				f"Max. Länge {row.get('Max. Länge') or 'none'}, Pflichtfeld {row.get('Pflichtfeld') or NO}"
			)
			if ours != theirs:
				yield Difference(where, ours, jd.file, theirs)


def plugin_differences(subject: str, kind: Datenart, rows: Sequence[Row]) -> Iterator[Difference]:
	"""The datenartVersion and the plugin of the Datenart against its row of the Datenartversionmatrix, and the year
	or taxonomy that row names."""
	where, ours = f"{subject}, plugin", f"{kind.version}, {kind.plugin}"
	found = matrix_rows(rows, kind)
	if not found:
		yield Difference(where, ours, MATRIX, f"no row of {kind.version}")
		return
	row = found[0]
	year = "" if kind.year is None else str(kind.year)
	plugin = row.get("Plugin-Bibliothek", "").replace(YEAR, year)
	if plugin != kind.plugin:
		yield Difference(where, ours, MATRIX, f"Plugin-Bibliothek {plugin or 'none'}")
	named = row.get("Jahr / Version", "")
	if not _names(named, kind):
		yield Difference(where, f"for {kind.taxonomy or year}", MATRIX, f"Jahr / Version {named or 'none'}")


def check_ustva(root: Path, year: int | str) -> Iterator[str]:
	"""What steuerbote/ustva/yearcheck.py finds for the year."""
	year = int(year)
	year_documentation = ustva_documentation.read(root, year)
	lacking = ustva_yearcheck.missing(year)
	if lacking:
		yield making(f"{USTVA} {year}", lacking)
	for difference in ustva_yearcheck.differences(year_documentation, ustva_yearcheck.data_for(year)):
		yield f"{USTVA} {year}, {difference}"


def check_ust(root: Path, year: int | str) -> Iterator[str]:
	"""The Umsatzsteuererklärung of the year against the JD E50, its schema and the matrix."""
	year = int(year)
	subject = f"{UST} {year}"
	kind = ust(year)
	jd = read(jahresdokumentation_path(root, kind))
	xsd = read_schema(schema_path(root, kind), kind.root)
	lacking = missing(year, UST_TABLES)
	if lacking:
		yield making(subject, lacking)
	catalogue = latest(ust2a_xml.SCHEMAS, year)
	differences = [
		*form_catalogue_differences(subject, catalogue, jd, xsd, expected_line=ust_line),
		*_ust_rules(subject, latest(ustjahr_form.CATALOGUES, year), jd),
		*_local_rules(
			subject, latest(ustjahr_rules.LOCAL_RULES, year), latest(ustjahr_rules.LEFT_TO_ERIC, year), jd
		),
		*vorsatz_differences(subject, jd),
		*plugin_differences(subject, kind, datenart_versions(root)),
	]
	yield from (str(difference) for difference in differences)


def check_bilanz(root: Path, key: int | str) -> Iterator[str]:
	"""A version of the HGB-Taxonomie, or the versions of the fiscal year of a year, against the documentation."""
	if isinstance(key, int):
		yield from _bilanz_year(root, key)
		return
	subject = f"{BILANZ} {key}"
	kind = bilanz(key)
	jd = read(jahresdokumentation_path(root, kind))
	lacking = missing(key, BILANZ_TABLES)
	if lacking:
		yield making(subject, lacking)
	data = key if key in versions.TAXONOMIES else versions.LATEST.version
	differences = [
		difference
		for expecting in BILANZ_EXPECTING
		for expectation in expecting(data)
		for difference in expectation_differences(subject, expectation, jd, _file_of(expecting))
	]
	differences.extend(plugin_differences(subject, kind, datenart_versions(root)))
	yield from (str(difference) for difference in differences)


def beyond_bilanz(root: Path) -> Iterator[str]:
	"""The versions of the HGB-Taxonomie that the documentation holds beyond TAXONOMIES, by their Jahresdokumentation
	or their row in the matrix."""
	newest = _version(versions.LATEST.version)
	documented = {
		version: jahresdokumentation_name(bilanz(version))
		for version in taxonomies(root, bilanz(versions.LATEST.version))
	}
	for named in _bilanz_rows(datenart_versions(root)):
		documented.setdefault(named, MATRIX)
	table = BILANZ_TABLES[0]
	for version in sorted((found for found in documented if _version(found) > newest), key=_version):
		yield str(
			Difference(
				f"{BILANZ} {version}",
				f"not in {table.name} of {table.file}",
				documented[version],
				"documented",
			)
		)


def main(
	argv: Sequence[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None
) -> int:
	"""The command; stdout and stderr are those of the process unless a test passes its own."""
	stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
	parser = argparse.ArgumentParser(
		prog="python -m steuerbote.jahresmeldung.yearcheck",
		description="Compare the data of the annual filings and of the UStVA with the ERiC documentation.",
	)
	parser.add_argument(
		"documentation", type=Path, help="the unzipped ERiC documentation or its Dokumentation"
	)
	parser.add_argument(
		"selection",
		nargs="*",
		metavar="Datenart, year or taxonomy",
		help=f"{', '.join(module.name for module in MODULES)}, years such as 2026 and versions of the HGB-Taxonomie "
		"such as 6.9; by default every Datenart and every year of its tables",
	)
	arguments = parser.parse_args(argv)
	try:
		selected = selection(arguments.selection)
	except ValueError as error:
		parser.error(str(error))
	try:
		root = documentation.find(arguments.documentation)
	except DocumentationError as error:
		stderr.write(f"{error}\n")
		return 2
	lines: list[str] = []
	errors: list[str] = []
	for module, keys in selected:
		for key in keys or module.keys():
			_collect(module.check(root, key), lines, errors)
		if not keys:
			_collect(module.beyond(root), lines, errors)
	stdout.writelines(f"{line}\n" for line in lines)
	stderr.writelines(f"{error}\n" for error in errors)
	if errors:
		return 2
	return 1 if lines else 0


def selection(arguments: Sequence[str]) -> list[tuple[Module, tuple[int | str, ...]]]:
	"""The modules the arguments name, each with the years and versions it checks, none for those of its tables.

	Without a name, years go to every module, and versions of the HGB-Taxonomie alone to the Bilanz."""
	names = {module.name.lower(): module for module in MODULES}
	modules: list[Module] = []
	years: list[int] = []
	taxonomies_: list[str] = []
	for argument in arguments:
		if argument.lower() in names:
			modules.append(names[argument.lower()])
		elif _YEAR_ARGUMENT.fullmatch(argument):
			years.append(int(argument))
		elif _TAXONOMY_ARGUMENT.fullmatch(argument):
			taxonomies_.append(argument)
		else:
			known = ", ".join(module.name for module in MODULES)
			raise ValueError(
				f"{argument} is no Datenart ({known}), no year and no version of the HGB-Taxonomie"
			)
	if taxonomies_ and modules and all(module.name != BILANZ for module in modules):
		raise ValueError(f"{taxonomies_[0]} is a version of the HGB-Taxonomie, which only {BILANZ} takes")
	if not modules:
		modules = [module for module in MODULES if module.name == BILANZ or years or not taxonomies_]
	return [
		(module, (*years, *(taxonomies_ if module.name == BILANZ else ())))
		for module in dict.fromkeys(modules)
	]


def _collect(lines_of: Iterator[str], lines: list[str], errors: list[str]) -> None:
	"""The lines of a check, up to the error of the documentation that ends it."""
	try:
		for line in lines_of:
			lines.append(line)
	except DocumentationError as error:
		errors.append(str(error))


def _bilanz_year(root: Path, year: int) -> Iterator[str]:
	subject = f"{BILANZ} {year}"
	lacking = missing(year, BILANZ_YEAR_TABLES)
	if lacking:
		yield making(subject, lacking)
	if year in releases.BILANZ_TAXONOMIES:
		chosen: tuple[str, ...] = (releases.BILANZ_TAXONOMIES[year],)
	else:
		chosen = tuple(entry.version for entry in versions.allowed_for(date(year, 1, 1), date(year, 12, 31)))
	if not chosen:
		table = BILANZ_TABLES[0]
		named = max(_bilanz_rows(datenart_versions(root)), key=_version, default="none")
		ours = f"no HGB-Taxonomie of {table.name} of {table.file} for the fiscal year"
		yield str(Difference(subject, ours, MATRIX, f"the newest is {named}"))
	for version in chosen:
		yield from check_bilanz(root, version)


def _bilanz_rows(rows: Iterable[Row]) -> list[str]:
	"""The versions of the HGB-Taxonomie that the rows of the Datenart Bilanz in the matrix name."""
	return [
		named.removeprefix(TAXONOMY_ROW)
		for row in rows
		if row.get("Datenart(en)") == BILANZ
		and (named := row.get("Jahr / Version", "")).startswith(TAXONOMY_ROW)
	]


def _beyond_years(name: str, root: Path, datenart: Callable[[int], Datenart], table: Table) -> Iterator[str]:
	"""The years whose Jahresdokumentation the documentation holds beyond the year table."""
	newest = max(int(key) for key in table.keys)
	for year in documentation.years(root, datenart(newest)):
		if year > newest:
			file = jahresdokumentation_name(datenart(year))
			yield str(
				Difference(f"{name} {year}", f"not in {table.name} of {table.file}", file, "documented")
			)


def _forms(subject: str, catalogue: FormCatalogue, jd: Jahresdokumentation) -> Iterator[Difference]:
	listed = {form.name: form for form in jd.forms}
	ours = {form.name: form for form in catalogue.forms}
	for name, form in ours.items():
		where, theirs = f"{subject}, Vordruck {name}", listed.get(name)
		if theirs is None:
			yield Difference(where, _described(form.count, form.mandatory), jd.file, "not listed")
		elif theirs != form:
			yield Difference(
				where,
				_described(form.count, form.mandatory),
				jd.file,
				_described(theirs.count, theirs.mandatory),
			)
	for name, form in listed.items():
		if form.mandatory and name not in ours:
			yield Difference(
				f"{subject}, Vordruck {name}", "not in the catalogue", jd.file, "Pflichtvordruck"
			)


def _schema_forms(subject: str, catalogue: FormCatalogue, xsd: Schema) -> Iterator[Difference]:
	"""The Vordrucke of the catalogue against the elements of the root of the schema: each there, in the order of the
	schema, with the maxOccurs of its „max. lfd. Nr. Vordruck“."""
	present = [form for form in catalogue.forms if form.name in xsd.vordrucke]
	for form in catalogue.forms:
		if form.name not in xsd.vordrucke:
			where = f"{subject}, Vordruck {form.name}"
			yield Difference(where, "in the catalogue", xsd.file, f"no element {form.name}")
	names = {form.name for form in present}
	documented = [name for name in xsd.vordrucke if name in names]
	for form, name in zip(present, documented, strict=True):
		if form.name != name:
			ours, theirs = f"{form.name} before {name}", f"{name} before {form.name}"
			yield Difference(f"{subject}, order of the Vordrucke", ours, xsd.file, theirs)
			break
	for form in present:
		most = xsd.repeats.get(form.name, "1")
		if str(form.count) != most:
			where = f"{subject}, Vordruck {form.name}"
			yield Difference(where, f"max. lfd. Nr. {form.count}", xsd.file, f"maxOccurs {most}")


def xml_schema_differences(
	subject: str, schema: kst_xml.Schema, catalogue: FormCatalogue, jd: Jahresdokumentation, xsd: Schema
) -> Iterator[Difference]:
	"""What the writer of an Erklärung takes from its schema besides the catalogue (steuerbote/elster/kst_xml.py): the
	contexts of the Vordrucke of the catalogue that repeat, with their maxOccurs, and the Vordrucke that begin with the
	Indexfeld."""
	forms = {form.name for form in catalogue.forms}
	documented = {
		path: most for path, most in xsd.repeats.items() if "/" in path and path.split("/")[0] in forms
	}
	ours = {path: str(most) for path, most in schema.repeats.items()}
	for path in dict.fromkeys((*ours, *documented)):
		if ours.get(path) != documented.get(path):
			where = f"{subject}, context {path}"
			yield Difference(where, _repeated(ours.get(path)), xsd.file, _repeated(documented.get(path)))
	indexed = {form for form in forms if form in jd.vordrucke and jd.vordruck(form).index_fields}
	if set(schema.indexed) != indexed:
		ours_indexed, documented_indexed = ", ".join(sorted(schema.indexed)), ", ".join(sorted(indexed))
		yield Difference(
			f"{subject}, Indexfeld", ours_indexed or "none", jd.file, documented_indexed or "none"
		)


def rechtsform_differences(
	subject: str,
	rechtsformen: Mapping[str, Mapping[str, str]],
	kind: tuple[str, str],
	jd: Jahresdokumentation,
) -> Iterator[Difference]:
	"""The categories of each Rechtsform Steuerbote files against the enumeration of its type in the sheet
	„Benutzerdefinierte Typen“, such as „- 350 [Gesellschaft mit beschränkter Haftung] RF_Gruppe: 1 NurG: 1“."""
	name, version = kind
	where = f"{subject}, {name}"
	rows = [row for row in jd.sheets.get(TYPES, ()) if (row.get("Name"), row.get("Version")) == kind]
	if len(rows) != 1:
		yield Difference(
			where, "the categories of the Rechtsformen", jd.file, f"no type {name} of version {version}"
		)
		return
	documented = {
		match["code"]: dict(_CATEGORY.findall(match["categories"]))
		for line in rows[0].get("Format", "").split("\n")
		if (match := _RECHTSFORM.match(line.strip()))
	}
	for code, categories in rechtsformen.items():
		theirs = documented.get(code)
		if theirs != dict(categories):
			described = "no such Rechtsform" if theirs is None else _categories(theirs)
			yield Difference(f"{where}, {code}", _categories(categories), jd.file, described)


def _categories(categories: Mapping[str, str]) -> str:
	return ", ".join(f"{key} {value}" for key, value in sorted(categories.items()))


def _repeated(most: str | None) -> str:
	return "does not repeat" if most is None else f"repeats up to {most}"


def _kennzahlen(row: Row) -> tuple[str, str]:
	"""The Kennzahl of a row of „<Vordruck> - Kennzahlen“ without and with its Sachbereich, such as 110 and 13.110."""
	kennzahl, sachbereich = row.get("Kennzahl", ""), row.get("Sachbereich", "")
	return kennzahl, f"{sachbereich}.{kennzahl}" if sachbereich else kennzahl


def _described(count: int, mandatory: bool) -> str:
	return f"max. lfd. Nr. {count}{', Pflichtvordruck' if mandatory else ''}"


def _fields(
	subject: str,
	form: str,
	fields: Sequence[Field],
	jd: Jahresdokumentation,
	xsd: Schema,
	expected_line: Callable[[Field], str],
	year: str,
) -> Iterator[Difference]:
	vordruck = jd.vordruck(form)
	index = set(vordruck.index_fields)
	rows = {name: row for row in vordruck.filed_fields if (name := row.get("Name", "")) not in index}
	yield from _order(f"{subject}, {form}", [field_.feldkennung for field_ in fields], list(rows), jd.file)
	leaves = [leaf for leaf in xsd.vordrucke.get(form, ()) if leaf.name not in index]
	if form in xsd.vordrucke:
		places = [_place(leaf.context, leaf.name) for leaf in leaves]
		ours = [_place(field_.context, field_.feldkennung) for field_ in fields]
		yield from _order(f"{subject}, {form}", ours, places, xsd.file)
	kennzahlen = {row.get("Feldname", ""): _kennzahlen(row) for row in vordruck.kennzahlen}
	types = {leaf.name: leaf.type for leaf in leaves}
	for field_ in fields:
		where = f"{subject}, field {field_.feldkennung}"
		row = rows.get(field_.feldkennung)
		if row is not None:
			yield from _field(where, field_, row, jd.file, expected_line, year)
			ours = field_.kennzahl or ""
			documented = kennzahlen.get(_place(field_.context, field_.feldkennung), ("", ""))
			if ours not in documented:
				theirs = documented["." in ours]
				yield Difference(where, f"Kennzahl {ours or 'none'}", jd.file, f"Kennzahl {theirs or 'none'}")
		values = xsd.enumerations.get(types.get(field_.feldkennung, ""), ())
		if form in xsd.vordrucke and field_.options and field_.options != values:
			ours = f"values {', '.join(field_.options)}"
			yield Difference(where, ours, xsd.file, f"values {', '.join(values) or 'none'}")


def _field(
	where: str, field_: Field, row: Row, source: str, expected_line: Callable[[Field], str], year: str
) -> Iterator[Difference]:
	"""The columns of one field of „<Vordruck> - Felder“ against the field of the catalogue."""
	written = " ".join(row.get("Beschreibung", "").split())
	label = written.replace(YEAR_PLACEHOLDER, year)
	columns = [
		("Kontext", field_.context, row.get("Kontext", "")),
		("Formatkennzeichen", field_.format, row.get("Formatkennzeichen", "")),
		("Vordruckzeile", expected_line(field_), row.get("Vordruckzeile", "")),
		("Pflichtfeld", YES if field_.required else NO, row.get("Pflichtfeld", "") or NO),
		("max. Zeilen", str(field_.rows), row.get("max. Zeilen", "")),
		("Beschreibung", field_.label, written if field_.label == written else label),
	]
	if field_.format == "C":
		columns.append(("Max. Länge", str(field_.length), row.get("Max. Länge", "")))
	if field_.pattern is not None:
		columns.append(
			("Format als regulärer Ausdruck", field_.pattern, row.get("Format als regulärer Ausdruck", ""))
		)
	for column, ours, theirs in columns:
		if ours != theirs:
			yield Difference(where, f"{column} {ours or 'none'}", source, f"{column} {theirs or 'none'}")


def _rules(subject: str, catalogue: FormCatalogue, jd: Jahresdokumentation) -> Iterator[Difference]:
	"""The rules a form catalogue names, by Fehlercode, against their name and Regelart in the JD."""
	documented = {rule.get("Fehlercode", ""): rule for _, rule in jd.rules}
	for rule in catalogue.rules:
		row = documented.get(rule.code)
		ours = f"{rule.name}, {HINT if rule.hint else ERROR}"
		theirs = "no such rule" if row is None else f"{row.get('Name', '')}, {row.get('Regelart', '')}"
		if ours != theirs:
			yield Difference(f"{subject}, rule {rule.code}", ours, jd.file, theirs)


def _ust_rules(
	subject: str, catalogue: ustjahr_form.Catalogue, jd: Jahresdokumentation
) -> Iterator[Difference]:
	"""The rules of form USt 2 A, with their name, context and Regelart, against „USt2A - Regeln“, by Fehlercode."""
	documented = {
		row.get(
			"Fehlercode", ""
		): f"{row.get('Name', '')} in {row.get('Kontext') or MAIN_FORM}, {row.get('Regelart', '')}"
		for row in jd.vordruck(MAIN_FORM).rules
	}
	ours = {
		rule.code: f"{rule.name} in {rule.context or MAIN_FORM}, {rule.severity.value}"
		for rule in catalogue.rules
	}
	for code in dict.fromkeys((*ours, *documented)):
		if ours.get(code) != documented.get(code):
			yield Difference(
				f"{subject}, rule {code}",
				ours.get(code, "no such rule"),
				jd.file,
				documented.get(code, "no such rule"),
			)


def _local_rules(
	subject: str, local: Sequence[ustjahr_rules.Check], left: Mapping[str, str], jd: Jahresdokumentation
) -> Iterator[Difference]:
	"""Each rule Steuerbote checks with the Prüfbedingung of the JD, and every rule of USt2A checked or left to ERiC."""
	documented = {row.get("Fehlercode", ""): row for row in jd.vordruck(MAIN_FORM).rules}
	checked = {rule.code: rule.condition for rule in local}
	for code, condition in checked.items():
		where, row = f"{subject}, rule {code}", documented.get(code)
		if row is None:
			yield Difference(where, "checked by steuerbote/ustjahr/rules.py", jd.file, "no such rule")
		elif conjuncts(condition) != conjuncts(row.get("Prüfbedingung", "")):
			theirs = " ".join(row.get("Prüfbedingung", "").split())
			yield Difference(where, f"checked as {' '.join(condition.split())}", jd.file, theirs)
	for code in left:
		if code not in documented:
			yield Difference(f"{subject}, rule {code}", "left to ERiC", jd.file, "no such rule")
	for code, row in documented.items():
		if code not in checked and code not in left:
			ours = "neither checked by steuerbote/ustjahr/rules.py nor left to ERiC"
			yield Difference(
				f"{subject}, rule {code}", ours, jd.file, f"{row.get('Regelart', '')} {row.get('Name', '')}"
			)


def ust_line(field_: Field) -> str:
	"""The Vordruckzeile the JD E50 gives a field of USt2A: its line, but for the Mitwirkung einer Steuerberatung."""
	if field_.context.startswith(MITWIRKUNG):
		return MITWIRKUNG_LINES.get(field_.feldkennung, MITWIRKUNG_LINE)
	return _line(field_)


def _line(field_: Field) -> str:
	return "" if field_.line is None else str(field_.line)


def _place(context: str, name: str) -> str:
	return f"{context}/{name}" if context else name


def _order(subject: str, ours: Sequence[str], documented: Sequence[str], source: str) -> Iterator[Difference]:
	"""The fields only one side has, then the first two that both have in another order."""
	for name in ours:
		if name not in documented:
			yield Difference(f"{subject}, {name}", "a field", source, "no such field")
	for name in documented:
		if name not in ours:
			yield Difference(f"{subject}, {name}", "no such field", source, "a field")
	common = [name for name in ours if name in documented]
	documented_common = [name for name in documented if name in ours]
	for name, other in zip(common, documented_common, strict=True):
		if name != other:
			yield Difference(f"{subject}, order", f"{name} before {other}", source, f"{other} before {name}")
			return


def _names(named: str, kind: Datenart) -> bool:
	"""Whether the Jahr / Version of a row of the matrix covers the year or the taxonomy of the Datenart."""
	if kind.taxonomy is not None:
		return named == f"{TAXONOMY_ROW}{kind.taxonomy}"
	if (first := _FROM_YEAR.fullmatch(named)) is not None:
		return kind.year is not None and kind.year >= int(first["year"])
	if (listed := _LISTED_YEARS.fullmatch(named)) is not None:
		return str(kind.year) in listed["years"].split(", ")
	return False


def _version(text: str) -> tuple[int, ...]:
	return tuple(int(part) for part in text.split(".") if part.isdigit())


def _sorted_fields(match: re.Match[str]) -> str:
	return f"({','.join(sorted(match[1].split(',')))})"


def _file_of(source: ModuleType | Callable[..., object]) -> str:
	name = source.__name__ if isinstance(source, ModuleType) else source.__module__
	return f"{name.replace('.', '/')}.py"


UST_TABLES = (
	Table("YEARS", "steuerbote/ustjahr/years.py", ustjahr_years.YEARS),
	Table("CATALOGUES", "steuerbote/ustjahr/form.py", ustjahr_form.CATALOGUES),
	Table("LOCAL_RULES", "steuerbote/ustjahr/rules.py", ustjahr_rules.LOCAL_RULES),
	Table("LEFT_TO_ERIC", "steuerbote/ustjahr/rules.py", ustjahr_rules.LEFT_TO_ERIC),
	Table("ROLE_FIELDS", "steuerbote/ustjahr/defaults.py", ustjahr_defaults.ROLE_FIELDS),
	Table("ANNUAL_ACCOUNTS", "steuerbote/ustjahr/defaults.py", ustjahr_defaults.ANNUAL_ACCOUNTS),
	Table("REVISIONS", "steuerbote/ustjahr/defaults.py", ustjahr_defaults.REVISIONS),
	Table("SCHEMAS", "steuerbote/elster/ust2a_xml.py", ust2a_xml.SCHEMAS),
)
USTVA_YEARS = Table("YEARS", "steuerbote/ustva/years.py", ustva_years.YEARS)
BILANZ_TABLES = (Table("TAXONOMIES", "steuerbote/xbrl/versions.py", versions.TAXONOMIES),)
BILANZ_YEAR_TABLES = (Table("BILANZ_TAXONOMIES", "steuerbote/eric/releases.py", releases.BILANZ_TAXONOMIES),)
BILANZ_EXPECTING: tuple[Callable[[str], tuple[RuleExpectation, ...]], ...] = (
	bilanz_simulation.expected_rules,
)
"""The functions of the modules of the E-Bilanz that name the rules of a taxonomy they compute, by its version."""
KST_CHECK = IncomeTax(
	KST,
	kst_years.YEARS,
	kst,
	(kst_chain, losses, einlagekonto),
	(
		Table("YEARS", "steuerbote/kst/years.py", kst_years.YEARS),
		Table("CATALOGUES", "steuerbote/kst/form.py", kst_form.CATALOGUES),
		Table("RECHTSFORMEN", "steuerbote/kst/form.py", kst_form.RECHTSFORMEN),
		Table("SCHEMAS", "steuerbote/elster/kst_xml.py", kst_xml.SCHEMAS),
	),
	kst_form.CATALOGUES,
	kst_xml.SCHEMAS,
	kst_form.RECHTSFORMEN,
	("RECHTSFORM_KOERPERSCHAFTEN_V3", "3"),
)
GEWST_CHECK = IncomeTax(
	GEWST,
	gewst_years.YEARS,
	gewst,
	(gewst_chain,),
	(
		Table("YEARS", "steuerbote/gewst/years.py", gewst_years.YEARS),
		Table("CATALOGUES", "steuerbote/gewst/form.py", gewst_form.CATALOGUES),
		Table("RECHTSFORMEN", "steuerbote/gewst/form.py", gewst_form.RECHTSFORMEN),
		Table("SCHEMAS", "steuerbote/elster/gewst_xml.py", gewst_xml.SCHEMAS),
	),
	gewst_form.CATALOGUES,
	gewst_xml.SCHEMAS,
	gewst_form.RECHTSFORMEN,
	("RECHTSFORM_GEWERBESTEUER_V2", "2"),
)
MODULES = (
	Module(
		USTVA,
		lambda: tuple(ustva_years.YEARS),
		check_ustva,
		lambda root: _beyond_years(USTVA, root, ustva, USTVA_YEARS),
	),
	Module(
		UST,
		lambda: tuple(ustjahr_years.YEARS),
		check_ust,
		lambda root: _beyond_years(UST, root, ust, UST_TABLES[0]),
	),
	KST_CHECK.module,
	GEWST_CHECK.module,
	Module(BILANZ, lambda: tuple(versions.TAXONOMIES), check_bilanz, beyond_bilanz),
)


if __name__ == "__main__":
	sys.exit(main())
