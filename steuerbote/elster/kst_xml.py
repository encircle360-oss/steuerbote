"""The Körperschaftsteuererklärung as ELSTER XML: the Nutzdaten E30 of a VZ, which ERiC takes for the Datenart
KSt_30_<Jahr>.

Sources are the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/): the schema
E30-2025.xsd and Jahresdokumentation_E30_2025.ods, cited as JD, with the „ERiC Zusatzinformation zur
Plausibilitätsprüfung“ (Datenarten/Zusatzinformationen_zur_Plausibilitaetspruefung.pdf), cited as ZI.

The Nutzdaten are the element E30 in the namespace and the version of the Datenart of the VZ
(steuerbote.eric.datenart.kst), and in it, in the order of the xs:sequence of E30:
- the Vordrucke of steuerbote.kst.form, each as many times as its „max. lfd. Nr. Vordruck“ allows: Anlage GK and
  KSt 1 F once per Wirtschaftsjahr, WJ1 before WJ2, the first child of each the Indexfeld WJ (JD, column Indexfeld);
- in each Vordruck its fields in the order of their sequences, each context once, a context that repeats once per
  instance (SCHEMAS: its maxOccurs in the schema, its „max. Wiederholbarkeit“ in the JD sheet „<Vordruck> -
  Kontexte“), the instances in the order of their numbers;
- the Vorsatz with the Unterfallart 30 as the last element (steuerbote.elster.vorsatz).

Each value goes through Field.text of the catalogue (steuerbote.elster.erklaerung), with its Formatkennzeichen and its
pattern. A value None is left out, so is a yes field that says no, and a Vordruck left without a field, since ERiC
counts a Vordruck or context as given by its fields (ZI Tabelle 4-8, „KontextAngegeben“). The writer adds nothing:
what the Vordrucke hold is the caller's, steuerbote.kst.form.vordrucke() for the lines the computation gives. It
refuses what the schema would refuse, with a ValueError: a field the catalogue lacks or that belongs to another
Vordruck, a field twice, the instances of a context that repeats missing, too many or given for one that does not
repeat, more Vordrucke than the JD allows, a missing or a second Indexfeld, and a declaration without its
Pflichtvordruck KSt1.

SCHEMAS holds per VZ what the writer takes from the schema besides the catalogue: the contexts that repeat, with
their maxOccurs, the Vordrucke with the Indexfeld, and the year of the schema the tests check the Nutzdaten against,
which is the documentation year of a provisional VZ: 2026 is written as E30 version 2026 in the namespace of 2026, and tested against E30-2025.xsd
after a rewrite of namespace and version in the test. build() writes the Nutzdaten of any Erklärung from its
catalogue and schema; steuerbote.elster.gewst_xml writes the E20 with it.

This module is pure Python and never imports Frappe.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from lxml import etree

from steuerbote.elster.erklaerung import Field, FormCatalogue
from steuerbote.elster.ustva_xml import serialized
from steuerbote.elster.vorsatz import Vorsatz, append_to
from steuerbote.kst.form import INDEXED, WJ, Entry, Vordruck, catalogue_for
from steuerbote.ustva.years import UnknownYearError

INDEX = "WJ"


@dataclass(frozen=True, slots=True)
class Schema:
	"""What the schema of a year adds to its catalogue: ``repeats`` holds each context that repeats, by its path below
	the root such as KSt1/AE/Einzel, with its maxOccurs; ``documentation_year`` is the year of the schema the Nutzdaten
	are tested against; ``indexed`` names the Vordrucke that begin with the Indexfeld WJ."""

	year: int
	repeats: Mapping[str, int]
	documentation_year: int
	indexed: frozenset[str] = frozenset()

	def __post_init__(self) -> None:
		object.__setattr__(self, "repeats", MappingProxyType(dict(self.repeats)))
		object.__setattr__(self, "indexed", frozenset(self.indexed))


SCHEMAS: MappingProxyType[int, Schema] = MappingProxyType(
	{
		2026: Schema(
			2026,
			{
				"KSt1/AE/Einzel": 99,
				"KSt1/AE/Einzel/Besitzdauer": 3,
				"GK/Bilanz/PG/Einzel": 99,
				"GK/ABil/AtypG/Einzel": 99,
				"GK/ABil/TypG/Einzel": 99,
				"GK/ABil/VGA/Einzel": 99,
				"GK/ABil/Genuss/Einzel": 99,
				"GK/ABil/Weiteres2/Sonstige/Einzel": 99,
				"GK/UmwStG/Verschmelzung_UN/Einzel": 99,
				"GK/UmwStG/Anderes_Jahr/Einzel": 99,
				"GK/UmwStG/Lfd_Jahr/Einzel": 99,
				"GK/Ausland/DBA/Einzel": 99,
				"GK/Ausland/Berichtigung/Einzel": 99,
				"GK/Beteiligung/Verkauf/Anderes_Jahr/Einzel": 99,
				"GK/Beteiligung/Verkauf/Lfd_Jahr/Einzel": 99,
				"GK/Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Einzel": 99,
				"GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel": 99,
				"GK/Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel": 99,
				"GK/Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Einzel": 99,
				"GK/Org_AP/Einzel": 99,
				"GK/Ni_ORG/Einzel": 99,
				"ZVE/SdE/LuF/PG/Einzel": 99,
				"ZVE/SdE/Selbstandig/Einzel_Betrieb": 99,
				"ZVE/SdE/Selbstandig/Beteiligung_PG/Einzel_PG": 99,
				"ZVE/SdE/P50a/P50aNR1/Einzel": 99,
				"ZVE/SdE/P50a/P50aNR2/Einzel": 99,
				"Z/Ermittlung/Zuwendung/Einzel": 99,
				"Z/Ermittlung/Zuwendung/Einzel_2": 99,
				"WA/AE/Einzel": 99,
				"WA/Aufsichtsrat/Empfanger": 99,
				"WA/Vergutung/Empfanger": 99,
				"WA/FZul/Einzel": 99,
				"KSt1F/Leistungen/Einzel": 99,
				"KSt1F/Einlagen/Einlage": 99,
			},
			2025,
			INDEXED,
		)
	}
)


def schema_for(year: int) -> Schema:
	try:
		return SCHEMAS[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in SCHEMAS)
		raise UnknownYearError(f"no schema E30 for {year}; known years: {known}") from None


def nutzdaten(year: int, vordrucke: Iterable[Vordruck], vorsatz: Vorsatz) -> etree._Element:
	"""The element E30 of the VZ with the Vordrucke and the Vorsatz."""
	return build(catalogue_for(year), schema_for(year), vordrucke, vorsatz)


def to_nutzdaten(year: int, vordrucke: Iterable[Vordruck], vorsatz: Vorsatz) -> str:
	"""The Nutzdaten E30 as text, without a declaration, as the DatenTeil of steuerbote.eric.header takes them."""
	return serialized(nutzdaten(year, vordrucke, vorsatz))


def build(
	catalogue: FormCatalogue, schema: Schema, vordrucke: Iterable[Vordruck], vorsatz: Vorsatz
) -> etree._Element:
	"""The Nutzdaten of the Erklärung of the catalogue: its Vordrucke in the order of the catalogue, then the
	Vorsatz; see the module docstring."""
	kind = catalogue.datenart
	forms = {
		form.name: (number, form) for number, form in enumerate(catalogue.forms) if form.name != "Vorsatz"
	}
	given = tuple(vordrucke)
	for vordruck in given:
		if vordruck.form not in forms:
			raise ValueError(f"{catalogue.source} has no Vordruck {vordruck.form}")
	layout = _Layout(catalogue, schema)
	root = etree.Element(f"{{{kind.namespace}}}{kind.root}", nsmap={None: kind.namespace})
	root.set("version", kind.root_version)
	written: Counter[str] = Counter()
	indexes: set[tuple[str, str | None]] = set()
	for vordruck in sorted(given, key=lambda item: (forms[item.form][0], item.wj or "")):
		_check_index(vordruck, schema.indexed, indexes)
		element = layout.vordruck(kind.namespace, vordruck)
		if element is None:
			continue
		written[vordruck.form] += 1
		most = forms[vordruck.form][1].count
		if written[vordruck.form] > most:
			raise ValueError(f"{catalogue.source} takes at most {most} Vordrucke {vordruck.form}")
		root.append(element)
	for form in catalogue.mandatory_forms:
		if form != "Vorsatz" and not written[form]:
			raise ValueError(f"the Erklärung needs its Pflichtvordruck {form}")
	append_to(root, kind, vorsatz)
	return root


def _check_index(vordruck: Vordruck, indexed: frozenset[str], seen: set[tuple[str, str | None]]) -> None:
	if vordruck.form in indexed and vordruck.wj not in WJ:
		raise ValueError(f"the Vordruck {vordruck.form} needs its Indexfeld {INDEX}, one of {', '.join(WJ)}")
	if vordruck.form not in indexed and vordruck.wj is not None:
		raise ValueError(f"the Vordruck {vordruck.form} has no Indexfeld {INDEX}")
	if vordruck.wj is not None:
		if (vordruck.form, vordruck.wj) in seen:
			raise ValueError(f"the Vordruck {vordruck.form} stands twice for {vordruck.wj}")
		seen.add((vordruck.form, vordruck.wj))


class _Layout:
	"""Where each field of a catalogue goes: the rank of each field and context in the order of the schema, and the
	contexts that repeat."""

	def __init__(self, catalogue: FormCatalogue, schema: Schema) -> None:
		self.source = catalogue.source
		self.repeats = schema.repeats
		self.fields = {field.feldkennung: field for field in catalogue.fields}
		self.ranks: dict[str, int] = {}
		for rank, field in enumerate(catalogue.fields):
			self.ranks[field.feldkennung] = rank
			for path in _prefixes(field):
				self.ranks.setdefault(path, rank)

	def vordruck(self, namespace: str, vordruck: Vordruck) -> etree._Element | None:
		"""The element of the Vordruck, None when no entry gives a value."""
		placed: list[tuple[tuple[tuple[int, int], ...], Field, Entry, str]] = []
		seen: set[tuple[str, tuple[int, ...]]] = set()
		for entry in vordruck.entries:
			field = self._field(vordruck.form, entry)
			if (entry.feldkennung, entry.rows) in seen:
				raise ValueError(
					f"{vordruck.form}: the field {entry.feldkennung} stands twice in {entry.rows}"
				)
			seen.add((entry.feldkennung, entry.rows))
			text = field.text(entry.value)
			if text is not None:
				placed.append((self._key(field, entry), field, entry, text))
		if not placed:
			return None
		element = etree.Element(f"{{{namespace}}}{vordruck.form}")
		if vordruck.wj is not None:
			etree.SubElement(element, f"{{{namespace}}}{INDEX}").text = vordruck.wj
		contexts: dict[tuple[tuple[str, int], ...], etree._Element] = {}
		for _key, field, entry, text in sorted(placed, key=lambda item: item[0]):
			parent = element
			rows = iter(entry.rows)
			path: tuple[tuple[str, int], ...] = ()
			for prefix, name in zip(_prefixes(field), _names(field), strict=True):
				path = (*path, (name, next(rows) if prefix in self.repeats else 0))
				if path not in contexts:
					contexts[path] = etree.SubElement(parent, f"{{{namespace}}}{name}")
				parent = contexts[path]
			etree.SubElement(parent, f"{{{namespace}}}{field.feldkennung}").text = text
		return element

	def _field(self, form: str, entry: Entry) -> Field:
		field = self.fields.get(entry.feldkennung)
		if field is None:
			raise ValueError(f"{self.source} has no field {entry.feldkennung}")
		if field.form != form:
			raise ValueError(f"the field {entry.feldkennung} belongs to {field.form}, not to {form}")
		repeated = [prefix for prefix in _prefixes(field) if prefix in self.repeats]
		if len(entry.rows) != len(repeated):
			raise ValueError(
				f"{entry.feldkennung} lies in {len(repeated)} contexts that repeat, so it needs as many instances, "
				f"not {entry.rows}"
			)
		for prefix, row in zip(repeated, entry.rows, strict=True):
			if row >= self.repeats[prefix]:
				raise ValueError(f"{prefix} repeats at most {self.repeats[prefix]} times, not {row + 1}")
		return field

	def _key(self, field: Field, entry: Entry) -> tuple[tuple[int, int], ...]:
		rows = iter(entry.rows)
		steps = tuple(
			(self.ranks[prefix], next(rows) if prefix in self.repeats else 0) for prefix in _prefixes(field)
		)
		return (*steps, (self.ranks[field.feldkennung], 0))


def _prefixes(field: Field) -> tuple[str, ...]:
	"""The paths of the contexts of a field below the root, from the outermost: GK/Bilanz, GK/Bilanz/PG, ..."""
	names = _names(field)
	return tuple("/".join((field.form, *names[: length + 1])) for length in range(len(names)))


def _names(field: Field) -> tuple[str, ...]:
	return tuple(part for part in field.context.split("/") if part)
