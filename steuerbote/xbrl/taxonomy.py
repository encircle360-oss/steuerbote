"""The HGB-Taxonomie as Steuerbote reads it: concepts, tuples, labels, fiscal references and the networks of the views.

Steuerbote never ships the taxonomy (steuerbote/xbrl/versions.py). The operator puts the package of esteuer.de on the
server, and load() reads it from its unpacked directory for one view: the files its entry points reach, „discoverable
taxonomy set“ in the words of XBRL 2.1, Kap. 3.2. Every view starts from the GCD and exactly one entry point of the GAAP
module (Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025, B.3):

- FISCAL, de-gaap-ci-2025-04-01-shell-fiscal.xsd, „GAAP steuerlicher Einzelabschluss“, for the E-Bilanz;
- COMMERCIAL, de-gaap-ci-2025-04-01-shell.xsd, „GAAP Einzelabschluss“, for the Offenlegung of a small company;
- COMMERCIAL_MICROBILG, de-gaap-ci-2025-04-01-shell-microbilg.xsd, „GAAP Einzelabschluss MicroBilG“, for a
  Kleinstkapitalgesellschaft (Leitfaden A.5; „Arbeitshilfe für die Einreichung von Jahresabschlüssen/Finanzberichten
  im XBRL-Format“ of the Unternehmensregister, Stand September 2025).

Files reach others by xs:import and xs:include, by link:linkbaseRef, and by the locators and role references of a
linkbase. A reference is a path relative to its file or an absolute URL under http://www.xbrl.de/taxonomies/, which
names the same file of the package (Leitfaden A.6). The schemas of XBRL 2.1 and XBRL Dimensions 1.0 at www.xbrl.org are
no part of the package; a validator has them itself. A reference that leaves the package, a missing file and a file
that is no XML stop the loader with a TaxonomyError.

Concepts. A concept is a global element of a schema with an id: its name with the prefix its schema declares for its
namespace (de-gcd, de-gaap-ci), its type, period type and balance, whether it is abstract or nillable, and its
substitution group (XBRL 2.1, Kap. 5.1.1). The group makes it an item or a tuple, or, through XBRL Dimensions, a
hypercube or a dimension; an element in the group of another element, such as a value of a choice in the group of its
abstract head, takes the kind of that element. A tuple has the content of its complex type: a sequence of its parts or
a choice, each part with its minOccurs and maxOccurs. „Positionen mit Auswahlwerten“ are tuples whose choice takes the
substitutes of a head, „Positionen zur Einfachauswahl“ once and „Positionen zur Mehrfachauswahl“ more often (Leitfaden
A.8, B.14.1).

Relationships. Arcs relate concepts in presentation, calculation and definition links, and concepts to their labels and
references, each within the role of its extended link. Equivalent relationships, the same arc between the same ends in
the same role with the same attributes but use and priority, collapse to the one of the highest priority, and if that
one is prohibited the relationship is gone (XBRL 2.1, Kap. 3.5.3.9.7.4 and 3.5.3.9.7.5). That is how
de-gaap-ci-2025-04-01-label-fiscal-de.xml, which only the fiscal view reads, puts labels of the tax administration in
place of those of the commercial view: „bei den Bezeichnern (Standard- und Terse-Label) mehr Abweichungen“ (Leitfaden
A.3).

Labels are the German ones of four roles: the label and the terse label, the terse label of at most 60 characters of the
fiscal view, and the guidance of the tax administration, „Erläuterungen der Finanzverwaltung“ in the linkbases
...label-guidance-de.xml (Leitfaden B.6).

Fiscal references. The references of the role mandatoryDisclosureRef carry the properties of Leitfaden A.9 in the
namespace hgbref: the legal forms a position is for (legalFormEU, legalFormKSt, legalFormPG), the format of the GuV
(typeOperatingResult GKV, UKV or „neutral“, „für beide Varianten gültige Positionen“), the fiscal requirement
(„Mussfeld“, „Summenmussfeld“, „Rechnerisch notwendig, soweit vorhanden“), its validity (fiscalValidSince,
fiscalValidThrough), the purposes it is not permitted for (notPermittedFor „steuerlich“, „handelsrechtlich“ and
„Einreichung an Finanzverwaltung“) and onlyPermittedForSoBil_ErgBil. The references of the commercial view add
ValidSince and ValidThrough (A.9.2). A position of no legal form is for every legal form (B.4.2), and one of no
format for both (A.9.1). Several dates of one kind give the narrowest validity; two fiscal requirements of one concept
stop the loader.

This module is pure Python with lxml and never imports Frappe.
"""

import posixpath
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from lxml import etree

from steuerbote.xbrl.versions import BASE_URL, Version

XS = "http://www.w3.org/2001/XMLSchema"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
LINK = "http://www.xbrl.org/2003/linkbase"
XLINK = "http://www.w3.org/1999/xlink"
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDT = "http://xbrl.org/2005/xbrldt"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
HGBREF = "http://www.xbrl.de/taxonomies/de-ref-2010-02-19"
WELL_KNOWN = MappingProxyType({XBRLI: "xbrli", XBRLDT: "xbrldt", XS: "xs", LINK: "link", XLINK: "xlink"})
"""The prefixes of the namespaces of XBRL itself, the same in every schema that names them."""
GAAP_PREFIX = "de-gaap-ci"
"""The module a name without a prefix belongs to: the Bilanzzuordnung names the positions of the GAAP module so."""

PARENT_CHILD = "http://www.xbrl.org/2003/arcrole/parent-child"
SUMMATION_ITEM = "http://www.xbrl.org/2003/arcrole/summation-item"
CONCEPT_LABEL = "http://www.xbrl.org/2003/arcrole/concept-label"
CONCEPT_REFERENCE = "http://www.xbrl.org/2003/arcrole/concept-reference"
ALL = "http://xbrl.org/int/dim/arcrole/all"
HYPERCUBE_DIMENSION = "http://xbrl.org/int/dim/arcrole/hypercube-dimension"
DIMENSION_DOMAIN = "http://xbrl.org/int/dim/arcrole/dimension-domain"
DOMAIN_MEMBER = "http://xbrl.org/int/dim/arcrole/domain-member"

LABEL = "http://www.xbrl.org/2003/role/label"
TERSE_LABEL = "http://www.xbrl.org/2003/role/terseLabel"
TERSE60_LABEL = "http://www.xbrl.de/roles/labels/terse60Label"
GUIDANCE = "http://www.xbrl.org/2003/role/definitionGuidance"
DOCUMENTATION = "http://www.xbrl.org/2003/role/documentation"
LABEL_ROLES = (LABEL, TERSE_LABEL, TERSE60_LABEL, GUIDANCE)
LANGUAGE = "de"

NOT_PERMITTED_SUBMISSION = "Einreichung an Finanzverwaltung"
"""„Die mit „Einreichung an Finanzverwaltung“ gekennzeichneten Positionen dürfen für die Übermittlung von E-Bilanzen an
die Finanzverwaltung nicht verwendet werden.“ (Leitfaden A.9.3)"""
NOT_PERMITTED_FISCAL = "steuerlich"
"""„Die mit „steuerlich“ unzulässig gekennzeichneten Positionen dürfen nur in der Handelsbilanz vorkommen“ (A.9.3)."""
NOT_PERMITTED_COMMERCIAL = "handelsrechtlich"
NEUTRAL = "neutral"

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, remove_comments=True)
_LINKS = MappingProxyType(
	{
		f"{{{LINK}}}presentationLink": f"{{{LINK}}}presentationArc",
		f"{{{LINK}}}calculationLink": f"{{{LINK}}}calculationArc",
		f"{{{LINK}}}definitionLink": f"{{{LINK}}}definitionArc",
		f"{{{LINK}}}labelLink": f"{{{LINK}}}labelArc",
		f"{{{LINK}}}referenceLink": f"{{{LINK}}}referenceArc",
	}
)
_EXEMPT = frozenset({"use", "priority"})
"""The attributes of an arc that do not tell two relationships apart (XBRL 2.1, Kap. 3.5.3.9.7.4), besides xlink."""


class TaxonomyError(Exception):
	"""The package is not the HGB-Taxonomie Steuerbote reads, or the case names something it does not hold."""


class View(StrEnum):
	"""The entry points of a document: the GCD and one of the GAAP module (Leitfaden B.3)."""

	FISCAL = "fiscal"
	COMMERCIAL = "commercial"
	COMMERCIAL_MICROBILG = "commercial-microbilg"

	def entry_points(self, version: Version) -> tuple[str, str]:
		gaap = {
			View.FISCAL: version.fiscal_shell,
			View.COMMERCIAL: version.commercial_shell,
			View.COMMERCIAL_MICROBILG: version.microbilg_shell,
		}[self]
		return version.gcd_shell, gaap


class Kind(StrEnum):
	ITEM = "item"
	TUPLE = "tuple"
	HYPERCUBE = "hypercube"
	DIMENSION = "dimension"


_KIND_OF_GROUP = MappingProxyType(
	{
		"xbrli:item": Kind.ITEM,
		"xbrli:tuple": Kind.TUPLE,
		"xbrldt:hypercubeItem": Kind.HYPERCUBE,
		"xbrldt:dimensionItem": Kind.DIMENSION,
	}
)


class PeriodType(StrEnum):
	INSTANT = "instant"
	DURATION = "duration"


class Balance(StrEnum):
	DEBIT = "debit"
	CREDIT = "credit"


class Requirement(StrEnum):
	"""The fiscal requirement of a position, „fiscalRequirement“ (Leitfaden A.9.3, A.10)."""

	MUSSFELD = "Mussfeld"
	MUSSFELD_KONTENNACHWEIS = "Mussfeld, Kontennachweis erwünscht"
	SUMMENMUSSFELD = "Summenmussfeld"
	RECHNERISCH_NOTWENDIG = "Rechnerisch notwendig, soweit vorhanden"

	@property
	def mandatory(self) -> bool:
		"""Whether the position is reported, with NIL if the books cannot fill it: every Mussfeld, and „Summenmussfelder
		sind stets zu übermitteln“ (A.9.3). The taxonomy 6.9 no longer marks „Mussfeld, Kontennachweis erwünscht“
		(A.10.2); older versions did, as a Mussfeld."""
		return self is not Requirement.RECHNERISCH_NOTWENDIG


class LegalForm(StrEnum):
	"""The kinds of legal form the references name (legalFormEU, legalFormKSt, legalFormPG; Leitfaden A.9.1, B.4.1)."""

	EU = "EU"
	KST = "KSt"
	PG = "PG"


class IncomeStatementFormat(StrEnum):
	"""Gesamtkostenverfahren or Umsatzkostenverfahren (Leitfaden A.9.1, B.14.3.1.15)."""

	GKV = "GKV"
	UKV = "UKV"


MONETARY = "xbrli:monetaryItemType"
NUMERIC_TYPES = frozenset(
	{
		MONETARY,
		"xbrli:decimalItemType",
		"xbrli:pureItemType",
		"xbrli:sharesItemType",
		"xbrli:integerItemType",
		"xbrli:longItemType",
		"xbrli:intItemType",
		"xbrli:shortItemType",
		"xbrli:byteItemType",
		"xbrli:nonNegativeIntegerItemType",
		"xbrli:positiveIntegerItemType",
		"xbrli:nonPositiveIntegerItemType",
		"xbrli:negativeIntegerItemType",
		"xbrli:unsignedLongItemType",
		"xbrli:unsignedIntItemType",
		"xbrli:unsignedShortItemType",
		"xbrli:unsignedByteItemType",
	}
)
"""The numeric item types of XBRL 2.1 (Kap. 5.1.1.3) that take decimals; float, double and fraction the taxonomy never
uses."""


@dataclass(frozen=True, slots=True)
class Particle:
	"""A part of the content of a tuple: a concept with how often it may come, None for „unbounded“."""

	concept: str
	min_occurs: int = 1
	max_occurs: int | None = 1


@dataclass(frozen=True, slots=True)
class Content:
	"""The content of a tuple: a sequence or a choice of particles, which itself may come min_occurs to max_occurs
	times."""

	group: str
	min_occurs: int
	max_occurs: int | None
	particles: tuple[Particle, ...]


@dataclass(frozen=True, slots=True)
class Fiscal:
	"""The fiscal properties of a position (Leitfaden A.9.1, A.9.3)."""

	requirement: Requirement | None = None
	legal_forms: frozenset[LegalForm] = frozenset()
	"""The legal forms whose reference says true; none for a position of no legal form."""
	operating_results: frozenset[str] = frozenset()
	"""GKV, UKV or neutral; none for a position of no format."""
	not_permitted_for: frozenset[str] = frozenset()
	required_since: date | None = None
	"""fiscalValidSince: a Mussfeld only for fiscal years beginning on or after this day."""
	required_through: date | None = None
	"""fiscalValidThrough: a Mussfeld only up to a closing date on this day."""
	special_balance_only: bool = False
	"""onlyPermittedForSoBil_ErgBil: valued only in a Sonder- or Ergänzungsbilanz."""


@dataclass(frozen=True, slots=True)
class Concept:
	"""An element of the taxonomy that a fact can report, or a hypercube or dimension of a table."""

	name: str
	"""The name with the prefix of its module, such as de-gaap-ci:bs.ass."""
	namespace: str
	kind: Kind
	substitution_group: str
	item_type: str | None = None
	"""The type of an item, such as xbrli:monetaryItemType; None for a tuple."""
	period_type: PeriodType | None = None
	balance: Balance | None = None
	abstract: bool = False
	nillable: bool = False
	content: Content | None = None
	"""The content of a tuple."""
	fiscal: Fiscal = Fiscal()
	valid_since: date | None = None
	"""ValidSince: reported only for fiscal years beginning on or after this day (Leitfaden A.9.2, B.14.4.1)."""
	valid_through: date | None = None
	"""ValidThrough: reported only up to a closing date on this day."""

	@property
	def local_name(self) -> str:
		return self.name.partition(":")[2]

	@property
	def prefix(self) -> str:
		return self.name.partition(":")[0]

	@property
	def monetary(self) -> bool:
		return self.item_type == MONETARY

	@property
	def numeric(self) -> bool:
		return self.item_type in NUMERIC_TYPES

	def applies_to(self, legal_form: LegalForm) -> bool:
		"""Whether a company of the legal form may report the position: „nur Positionen mit der Auszeichnung
		„legalFormKSt“ = „true“ und Positionen, die keiner Rechtsform zugeordnet sind“ (Leitfaden B.4.2)."""
		return not self.fiscal.legal_forms or legal_form in self.fiscal.legal_forms

	def suits(self, income_statement_format: IncomeStatementFormat) -> bool:
		"""Whether the position belongs to a GuV of the format: „Wenn das GuV-Format „Gesamtkostenverfahren“ ...
		ausgewählt wurde, dann dürfen Positionen mit der Auszeichnung typeOperatingResult = UKV nicht übermittelt
		werden.“ (Leitfaden B.14.3.1.15)"""
		results = self.fiscal.operating_results
		return not results or NEUTRAL in results or income_statement_format.value in results

	def valid_for(self, fiscal_year_begin: date, closing_date: date) -> bool:
		"""Whether the position may be reported for the fiscal year (Leitfaden B.14.4.1)."""
		return not (self.valid_since is not None and fiscal_year_begin < self.valid_since) and not (
			self.valid_through is not None and closing_date > self.valid_through
		)

	def required_for(self, fiscal_year_begin: date, closing_date: date) -> bool:
		"""Whether the position is a Mussfeld or Summenmussfeld of the fiscal year (Leitfaden B.14.4.1 and B.14.4.2);
		whether the legal form, the format and the components of the case take it is the caller's to ask."""
		fiscal = self.fiscal
		return (
			fiscal.requirement is not None
			and fiscal.requirement.mandatory
			and self.valid_for(fiscal_year_begin, closing_date)
			and not (fiscal.required_since is not None and fiscal_year_begin < fiscal.required_since)
			and not (fiscal.required_through is not None and closing_date > fiscal.required_through)
		)

	def permitted_for(self, purpose: str) -> bool:
		"""Whether notPermittedFor leaves the position to the purpose, such as NOT_PERMITTED_SUBMISSION."""
		return purpose not in self.fiscal.not_permitted_for


@dataclass(frozen=True, slots=True)
class Arc:
	"""A relationship of a presentation or calculation network: parent, child, order, and the weight of a calculation."""

	parent: str
	child: str
	order: Decimal = Decimal(1)
	weight: Decimal | None = None
	preferred_label: str | None = None


@dataclass(frozen=True)
class Network:
	"""The arcs of one role and arcrole, in the order of the files, with their children ordered by „order“."""

	role: str
	arcs: tuple[Arc, ...]
	_children: Mapping[str, tuple[Arc, ...]] = field(init=False, repr=False, compare=False)
	_parents: Mapping[str, tuple[Arc, ...]] = field(init=False, repr=False, compare=False)
	_concepts: frozenset[str] = field(init=False, repr=False, compare=False)

	def __post_init__(self) -> None:
		children: dict[str, list[Arc]] = {}
		parents: dict[str, list[Arc]] = {}
		for arc in self.arcs:
			children.setdefault(arc.parent, []).append(arc)
			parents.setdefault(arc.child, []).append(arc)
		object.__setattr__(
			self,
			"_children",
			MappingProxyType(
				{name: tuple(sorted(arcs, key=lambda arc: arc.order)) for name, arcs in children.items()}
			),
		)
		object.__setattr__(
			self, "_parents", MappingProxyType({name: tuple(arcs) for name, arcs in parents.items()})
		)
		object.__setattr__(self, "_concepts", frozenset(children) | frozenset(parents))

	def __contains__(self, name: object) -> bool:
		return name in self._concepts

	def children(self, name: str) -> tuple[Arc, ...]:
		return self._children.get(name, ())

	def parents(self, name: str) -> tuple[Arc, ...]:
		return self._parents.get(name, ())

	def parent(self, name: str) -> str | None:
		"""The parent of a concept, None for a root; a concept under two parents has none to name."""
		parents = {arc.parent for arc in self.parents(name)}
		if len(parents) > 1:
			raise TaxonomyError(
				f"{name} has the parents {', '.join(sorted(parents))} in the role {self.role}"
			)
		return next(iter(parents), None)

	def ancestors(self, name: str) -> tuple[str, ...]:
		"""The parent, its parent and so on, nearest first."""
		found: list[str] = []
		current = self.parent(name)
		while current is not None and current not in found:
			found.append(current)
			current = self.parent(current)
		return tuple(found)

	def descendants(self, name: str) -> tuple[str, ...]:
		"""Every concept below one, depth first in the order of the network."""
		return tuple(concept for concept, _ in self._walk_from(name, 0, set()))[1:]

	def roots(self) -> tuple[str, ...]:
		"""The concepts without a parent, in the order the network names them."""
		return tuple(dict.fromkeys(arc.parent for arc in self.arcs if arc.parent not in self._parents))

	def walk(self) -> Iterator[tuple[str, int]]:
		"""Every concept with its depth, depth first from the roots in the order of the network."""
		seen: set[str] = set()
		for root in self.roots():
			yield from self._walk_from(root, 0, seen)

	def _walk_from(self, name: str, depth: int, seen: set[str]) -> Iterator[tuple[str, int]]:
		if name in seen:
			return
		seen.add(name)
		yield name, depth
		for arc in self.children(name):
			yield from self._walk_from(arc.child, depth + 1, seen)


@dataclass(frozen=True, slots=True)
class DefinitionArc:
	"""A relationship of a definition link, with the attributes XBRL Dimensions 1.0 gives it."""

	arcrole: str
	source: str
	target: str
	order: Decimal = Decimal(1)
	context_element: str | None = None
	closed: bool | None = None
	usable: bool = True
	target_role: str | None = None


@dataclass(frozen=True)
class Taxonomy:
	"""One view of one version of the taxonomy."""

	version: str
	view: View
	entry_points: tuple[str, ...]
	namespaces: Mapping[str, str]
	"""The prefix of each module and its namespace."""
	concepts: Mapping[str, Concept]
	roles: Mapping[str, str]
	"""The roles the schemas define, with their definitions."""
	labels: Mapping[str, Mapping[str, str]]
	"""The German labels of each concept by their role."""
	presentation: Mapping[str, Network]
	calculation: Mapping[str, Network]
	definition: Mapping[str, tuple[DefinitionArc, ...]]
	_substitutes: Mapping[str, tuple[str, ...]] = field(init=False, repr=False, compare=False)
	_tuples: Mapping[str, tuple[str, ...]] = field(init=False, repr=False, compare=False)
	_presented: frozenset[str] = field(init=False, repr=False, compare=False)

	def __post_init__(self) -> None:
		substitutes: dict[str, list[str]] = {}
		for concept in self.concepts.values():
			if concept.substitution_group in self.concepts:
				substitutes.setdefault(concept.substitution_group, []).append(concept.name)
		object.__setattr__(
			self,
			"_substitutes",
			MappingProxyType({head: tuple(names) for head, names in substitutes.items()}),
		)
		tuples: dict[str, list[str]] = {}
		for concept in self.concepts.values():
			for part in self._parts_of(concept):
				tuples.setdefault(part, []).append(concept.name)
		object.__setattr__(
			self, "_tuples", MappingProxyType({part: tuple(of) for part, of in tuples.items()})
		)
		object.__setattr__(
			self,
			"_presented",
			frozenset(name for network in self.presentation.values() for name in network._concepts),
		)

	def has(self, name: str) -> bool:
		return self._qualified(name) in self.concepts

	def concept(self, name: str) -> Concept:
		"""The concept of a name with its prefix, or of the GAAP module without one."""
		try:
			return self.concepts[self._qualified(name)]
		except KeyError:
			raise TaxonomyError(f"the HGB-Taxonomie {self.version} has no concept {name}") from None

	def label(self, name: str, role: str = LABEL) -> str:
		"""The German label of a concept in a role, else its standard label, else its name."""
		labels = self.labels.get(self._qualified(name), {})
		return labels.get(role) or labels.get(LABEL) or self._qualified(name).partition(":")[2]

	def presented(self, name: str) -> bool:
		"""Whether a presentation network of the view holds the concept, which makes it transmittable (Leitfaden
		B.11)."""
		return self._qualified(name) in self._presented

	def substitutes(self, head: str) -> tuple[str, ...]:
		"""The concepts in the substitution group of a head, in the order of their schema."""
		return self._substitutes.get(self._qualified(head), ())

	def parts(self, name: str) -> tuple[str, ...]:
		"""The concepts a tuple takes: each particle, an abstract head by its substitutes (XML Schema, „substitution
		group“)."""
		return self._parts_of(self.concept(name))

	def tuples_of(self, name: str) -> tuple[str, ...]:
		"""The tuples a concept is a part of; none for one reported on its own."""
		return self._tuples.get(self._qualified(name), ())

	def _parts_of(self, concept: Concept) -> tuple[str, ...]:
		if concept.content is None:
			return ()
		parts: list[str] = []
		for particle in concept.content.particles:
			target = self.concepts.get(particle.concept)
			if target is not None and not target.abstract:
				parts.append(particle.concept)
			parts.extend(self._substitutes.get(particle.concept, ()))
		return tuple(parts)

	@staticmethod
	def _qualified(name: str) -> str:
		return name if ":" in name else f"{GAAP_PREFIX}:{name}"


def load(directory: Path, version: Version, view: View) -> Taxonomy:
	"""The view of the taxonomy in the unpacked package of directory."""
	package = _Package(directory)
	documents = package.discover(view.entry_points(version))
	schemas = [document.schema for document in documents if document.schema is not None]
	prefixes = _prefixes(schemas)
	linkbases = _linkbases(documents, prefixes)
	concepts = _concepts(schemas, prefixes, _references(linkbases))
	roles = {role: definition for schema in schemas for role, definition in schema.roles.items()}
	return Taxonomy(
		version=version.version,
		view=view,
		entry_points=view.entry_points(version),
		namespaces=MappingProxyType(
			dict(sorted({(concept.prefix, concept.namespace) for concept in concepts.values()}))
		),
		concepts=MappingProxyType(concepts),
		roles=MappingProxyType(dict(sorted(roles.items()))),
		labels=MappingProxyType(_labels(linkbases)),
		presentation=MappingProxyType(_networks(linkbases, f"{{{LINK}}}presentationArc", PARENT_CHILD)),
		calculation=MappingProxyType(_networks(linkbases, f"{{{LINK}}}calculationArc", SUMMATION_ITEM)),
		definition=MappingProxyType(_definitions(linkbases)),
	)


type _Name = tuple[str, str]
"""A QName as namespace and local name, before the taxonomy gives the namespace its prefix."""


@dataclass
class _Element:
	"""A global element of a schema as written, before its substitution group is followed."""

	name: str
	id: str
	substitution_group: _Name | None
	item_type: _Name | None
	period_type: PeriodType | None
	balance: Balance | None
	abstract: bool
	nillable: bool
	content: tuple[str, int, int | None, tuple[tuple[_Name, int, int | None], ...]] | None


@dataclass
class _Schema:
	path: PurePosixPath
	target: str
	prefix: str | None
	elements: list[_Element]
	roles: dict[str, str]


@dataclass
class _Document:
	path: PurePosixPath
	root: etree._Element
	references: list[PurePosixPath]
	schema: _Schema | None = None


class _Package:
	"""The unpacked package, read file by file as the entry points reach them."""

	def __init__(self, directory: Path):
		self.directory = directory

	def discover(self, entry_points: Iterable[str]) -> list[_Document]:
		"""The documents the entry points reach, in the order they are found."""
		found: list[_Document] = []
		queue = [PurePosixPath(entry_point) for entry_point in entry_points]
		seen: set[PurePosixPath] = set()
		while queue:
			path = queue.pop(0)
			if path in seen:
				continue
			seen.add(path)
			document = self.document(path)
			found.append(document)
			queue.extend(document.references)
		return found

	def document(self, path: PurePosixPath) -> _Document:
		file = self.directory.joinpath(*path.parts)
		try:
			root = etree.parse(str(file), _PARSER).getroot()
		except OSError:
			raise TaxonomyError(f"the package holds no file {path}") from None
		except etree.XMLSyntaxError as error:
			raise TaxonomyError(f"{path} is no XML: {error}") from None
		references = [reference for href in _hrefs(root) if (reference := _resolve(path, href)) is not None]
		document = _Document(path, root, references)
		if root.tag == f"{{{XS}}}schema":
			document.schema = _read_schema(path, root)
		return document


def _hrefs(root: etree._Element) -> list[str]:
	"""Where a schema or linkbase points: imports and includes, linkbase references, locators and role references."""
	hrefs = [
		location
		for element in root.iter(f"{{{XS}}}import", f"{{{XS}}}include")
		if (location := element.get("schemaLocation"))
	]
	hrefs.extend(
		href
		for element in root.iter(
			f"{{{LINK}}}linkbaseRef", f"{{{LINK}}}loc", f"{{{LINK}}}roleRef", f"{{{LINK}}}arcroleRef"
		)
		if (href := element.get(f"{{{XLINK}}}href"))
	)
	return hrefs


def _resolve(base: PurePosixPath, href: str) -> PurePosixPath | None:
	"""The path in the package an href of the file base names, None for a document outside the taxonomy, such as the
	schemas of XBRL 2.1 at www.xbrl.org."""
	location = href.partition("#")[0]
	if not location:
		return None
	if location.startswith(BASE_URL):
		joined = location.removeprefix(BASE_URL)
	elif "://" in location:
		return None
	else:
		joined = posixpath.join(str(base.parent), location)
	normal = posixpath.normpath(joined)
	if normal == ".." or normal.startswith(("../", "/")):
		raise TaxonomyError(f"{base} refers to {href} outside the package")
	return PurePosixPath(normal)


def _read_schema(path: PurePosixPath, root: etree._Element) -> _Schema:
	target = root.get("targetNamespace", "")
	prefix = next(
		(prefix for prefix, namespace in root.nsmap.items() if namespace == target and prefix), None
	)
	elements = [
		_read_element(path, element)
		for element in root.iterchildren(f"{{{XS}}}element")
		if element.get("id") and element.get("name")
	]
	roles = {
		role_type.get("roleURI", ""): (role_type.findtext(f"{{{LINK}}}definition") or "").strip()
		for role_type in root.iter(f"{{{LINK}}}roleType")
	}
	return _Schema(path, target, prefix, elements, roles)


def _read_element(path: PurePosixPath, element: etree._Element) -> _Element:
	period = element.get(f"{{{XBRLI}}}periodType")
	balance = element.get(f"{{{XBRLI}}}balance")
	group = element.get("substitutionGroup")
	item_type = element.get("type")
	return _Element(
		name=element.get("name", ""),
		id=element.get("id", ""),
		substitution_group=_qname(group, element, path) if group else None,
		item_type=_qname(item_type, element, path) if item_type else None,
		period_type=PeriodType(period) if period else None,
		balance=Balance(balance) if balance else None,
		abstract=element.get("abstract") == "true",
		nillable=element.get("nillable") == "true",
		content=_content(element, path),
	)


def _content(
	element: etree._Element, path: PurePosixPath
) -> tuple[str, int, int | None, tuple[tuple[_Name, int, int | None], ...]] | None:
	complex_type = element.find(f"{{{XS}}}complexType")
	group = None if complex_type is None else complex_type.find(f"{{{XS}}}sequence")
	if complex_type is not None and group is None:
		group = complex_type.find(f"{{{XS}}}choice")
	if group is None:
		return None
	particles = tuple(
		(_qname(part.get("ref", ""), part, path), *_occurs(part))
		for part in group.iterchildren(f"{{{XS}}}element")
	)
	return (etree.QName(group).localname, *_occurs(group), particles)


def _occurs(element: etree._Element) -> tuple[int, int | None]:
	maximum = element.get("maxOccurs", "1")
	return int(element.get("minOccurs", "1")), None if maximum == "unbounded" else int(maximum)


def _qname(value: str, element: etree._Element, path: PurePosixPath) -> _Name:
	prefix, _, local = value.rpartition(":")
	namespace = element.nsmap.get(prefix or None)
	if namespace is None:
		raise TaxonomyError(f"{path} names {value} with a prefix it does not declare")
	return namespace, local


def _prefixes(schemas: Iterable[_Schema]) -> dict[str, str]:
	"""The prefix of each namespace: the one the schemas declaring concepts of it use, which must agree."""
	prefixes = dict(WELL_KNOWN)
	for schema in schemas:
		if not schema.elements or schema.target in WELL_KNOWN:
			continue
		if schema.prefix is None:
			raise TaxonomyError(f"{schema.path} declares no prefix for its namespace {schema.target}")
		known = prefixes.setdefault(schema.target, schema.prefix)
		if known != schema.prefix:
			raise TaxonomyError(
				f"{schema.path} names its namespace {schema.target} with the prefix {schema.prefix}, other schemas "
				f"with {known}"
			)
	return prefixes


def _qualifier(prefixes: Mapping[str, str]):
	def qualified(name: _Name) -> str:
		namespace, local = name
		return f"{prefixes[namespace]}:{local}" if namespace in prefixes else f"{{{namespace}}}{local}"

	return qualified


def _concepts(
	schemas: Iterable[_Schema], prefixes: Mapping[str, str], references: Mapping[str, Mapping[str, set[str]]]
) -> dict[str, Concept]:
	declared: dict[str, tuple[_Schema, _Element]] = {}
	for schema in schemas:
		for element in schema.elements:
			declared[f"{prefixes[schema.target]}:{element.name}"] = (schema, element)
	qualified = _qualifier(prefixes)
	kinds: dict[str, Kind | None] = {}
	for name in declared:
		_kind(name, declared, kinds, [], qualified)
	concepts = {}
	for name, (schema, element) in declared.items():
		kind = kinds[name]
		if kind is None:
			continue
		content = None
		if element.content is not None:
			group, minimum, maximum, particles = element.content
			content = Content(
				group,
				minimum,
				maximum,
				tuple(Particle(qualified(part), low, high) for part, low, high in particles),
			)
		parts = references.get(name, {})
		concepts[name] = Concept(
			name=name,
			namespace=schema.target,
			kind=kind,
			substitution_group=qualified(element.substitution_group) if element.substitution_group else "",
			item_type=None
			if kind is Kind.TUPLE or element.item_type is None
			else qualified(element.item_type),
			period_type=element.period_type,
			balance=element.balance,
			abstract=element.abstract,
			nillable=element.nillable,
			content=content,
			fiscal=_fiscal(name, parts),
			valid_since=_latest(name, parts.get("ValidSince")),
			valid_through=_earliest(name, parts.get("ValidThrough")),
		)
	return concepts


def _kind(
	name: str,
	declared: Mapping[str, tuple[_Schema, _Element]],
	kinds: dict[str, Kind | None],
	chain: list[str],
	qualified,
) -> Kind | None:
	"""The kind of a concept: that of its substitution group, followed through the elements of the taxonomy; None for
	an element that is no concept, such as a part of a reference."""
	if name in kinds:
		return kinds[name]
	if name in chain:
		raise TaxonomyError(f"the substitution groups of {name} form a cycle: {' > '.join([*chain, name])}")
	group = declared[name][1].substitution_group
	if group is None:
		kind = None
	elif (group_name := qualified(group)) in _KIND_OF_GROUP:
		kind = _KIND_OF_GROUP[group_name]
	elif group_name in declared:
		kind = _kind(group_name, declared, kinds, [*chain, name], qualified)
	elif group[0] in WELL_KNOWN:
		kind = None
	else:
		raise TaxonomyError(
			f"{name} is in the substitution group {group_name}, which the taxonomy does not declare"
		)
	kinds[name] = kind
	return kind


def _fiscal(name: str, parts: Mapping[str, set[str]]) -> Fiscal:
	requirements = parts.get("fiscalRequirement", set())
	if len(requirements) > 1:
		raise TaxonomyError(f"{name} has the fiscalRequirement {' and '.join(sorted(requirements))}")
	try:
		requirement = Requirement(next(iter(requirements))) if requirements else None
	except ValueError:
		raise TaxonomyError(f"{name} has the unknown fiscalRequirement {next(iter(requirements))}") from None
	return Fiscal(
		requirement=requirement,
		legal_forms=frozenset(
			form for form in LegalForm if "true" in parts.get(f"legalForm{form.value}", set())
		),
		operating_results=frozenset(parts.get("typeOperatingResult", set())),
		not_permitted_for=frozenset(parts.get("notPermittedFor", set())),
		required_since=_latest(name, parts.get("fiscalValidSince")),
		required_through=_earliest(name, parts.get("fiscalValidThrough")),
		special_balance_only="true" in parts.get("onlyPermittedForSoBil_ErgBil", set()),
	)


def _dates(name: str, values: set[str] | None) -> list[date]:
	try:
		return [date.fromisoformat(value) for value in values or ()]
	except ValueError as error:
		raise TaxonomyError(f"{name} has a reference with a date that is none: {error}") from None


def _latest(name: str, values: set[str] | None) -> date | None:
	return max(_dates(name, values), default=None)


def _earliest(name: str, values: set[str] | None) -> date | None:
	return min(_dates(name, values), default=None)


@dataclass(frozen=True, slots=True)
class _Relation:
	"""A relationship before the prohibitions and overrides of its equivalent relationships are applied."""

	arc: str
	"""The tag of the arc, such as {http://www.xbrl.org/2003/linkbase}presentationArc."""
	role: str
	arcrole: str
	source: str
	target: str
	"""A concept, or for a label or reference the key of its resource."""
	attributes: tuple[tuple[str, str], ...]
	prohibited: bool
	priority: int


@dataclass
class _Linkbases:
	"""The relationships of the linkbases of a view by the tag of their arc, and the resources of labels and
	references by their key: their file and id."""

	relations: dict[str, list[_Relation]]
	resources: dict[str, etree._Element]

	def of(self, arc: str, arcrole: str) -> Iterator[_Relation]:
		return (relation for relation in self.relations.get(arc, ()) if relation.arcrole == arcrole)


def _linkbases(documents: Iterable[_Document], prefixes: Mapping[str, str]) -> _Linkbases:
	"""The relationships of the linkbases, prohibited ones taken out (XBRL 2.1, Kap. 3.5.3.9.7.5)."""
	documents = list(documents)
	targets: dict[tuple[PurePosixPath, str], str] = {}
	for document in documents:
		if document.schema is not None:
			prefix = prefixes.get(document.schema.target)
			for element in document.schema.elements:
				targets[(document.path, element.id)] = f"{prefix}:{element.name}"
	resources: dict[str, etree._Element] = {}
	links: list[tuple[_Document, etree._Element, dict[int, str]]] = []
	for document in documents:
		if document.schema is not None:
			continue
		for number, link in enumerate(document.root.iterchildren(*_LINKS)):
			keys: dict[int, str] = {}
			for index, element in enumerate(link):
				if element.get(f"{{{XLINK}}}type") != "resource":
					continue
				identifier = element.get("id")
				keys[index] = f"{document.path}#{identifier or f'{number}.{index}'}"
				resources[keys[index]] = element
				if identifier:
					targets[(document.path, identifier)] = keys[index]
			links.append((document, link, keys))
	winners: dict[tuple, _Relation] = {}
	for document, link, keys in links:
		for relation in _link_relations(document, link, keys, targets):
			key = (
				relation.arc,
				relation.role,
				relation.arcrole,
				relation.source,
				relation.target,
				relation.attributes,
			)
			known = winners.get(key)
			if known is None or (relation.priority, relation.prohibited) >= (
				known.priority,
				known.prohibited,
			):
				winners[key] = relation
	relations: dict[str, list[_Relation]] = {}
	for relation in winners.values():
		if not relation.prohibited:
			relations.setdefault(relation.arc, []).append(relation)
	return _Linkbases(relations, resources)


def _link_relations(
	document: _Document,
	link: etree._Element,
	keys: Mapping[int, str],
	targets: Mapping[tuple[PurePosixPath, str], str],
) -> Iterator[_Relation]:
	role = link.get(f"{{{XLINK}}}role", "")
	ends: dict[str, list[str]] = {}
	for index, element in enumerate(link):
		label = element.get(f"{{{XLINK}}}label", "")
		if element.get(f"{{{XLINK}}}type") == "locator":
			href = element.get(f"{{{XLINK}}}href", "")
			target = targets.get((_resolve(document.path, href) or document.path, href.partition("#")[2]))
			if target is None:
				raise TaxonomyError(f"{document.path} locates {href}, which the package does not hold")
			ends.setdefault(label, []).append(target)
		elif index in keys:
			ends.setdefault(label, []).append(keys[index])
	arc_tag = _LINKS[link.tag]
	for arc in link.iterchildren(arc_tag):
		source, target = arc.get(f"{{{XLINK}}}from", ""), arc.get(f"{{{XLINK}}}to", "")
		for label in (source, target):
			if label not in ends:
				raise TaxonomyError(f"an arc of {document.path} names {label}, which its link does not hold")
		attributes = {
			name: _normal(name, value)
			for name, value in arc.attrib.items()
			if not name.startswith(f"{{{XLINK}}}") and name not in _EXEMPT
		}
		attributes.setdefault("order", "1")
		for start in ends[source]:
			for end in ends[target]:
				yield _Relation(
					arc=arc_tag,
					role=role,
					arcrole=arc.get(f"{{{XLINK}}}arcrole", ""),
					source=start,
					target=end,
					attributes=tuple(sorted(attributes.items())),
					prohibited=arc.get("use") == "prohibited",
					priority=int(arc.get("priority", "0")),
				)


def _normal(name: str, value: str) -> str:
	"""The value of an attribute as relationships compare it: order and weight as decimals."""
	if name in ("order", "weight"):
		try:
			return str(Decimal(value).normalize())
		except InvalidOperation:
			raise TaxonomyError(f"the {name} {value} of an arc is no number") from None
	return value


def _attribute(relation: _Relation, name: str) -> str | None:
	return next((value for key, value in relation.attributes if key == name), None)


def _labels(linkbases: _Linkbases) -> dict[str, Mapping[str, str]]:
	labels: dict[str, dict[str, str]] = {}
	for relation in linkbases.of(f"{{{LINK}}}labelArc", CONCEPT_LABEL):
		element = linkbases.resources[relation.target]
		role = element.get(f"{{{XLINK}}}role", LABEL)
		if role in LABEL_ROLES and element.get(XML_LANG, "").partition("-")[0] == LANGUAGE:
			labels.setdefault(relation.source, {}).setdefault(role, "".join(element.itertext()).strip())
	return {name: MappingProxyType(roles) for name, roles in sorted(labels.items())}


def _references(linkbases: _Linkbases) -> dict[str, dict[str, set[str]]]:
	"""The parts of the references in the namespace hgbref of each concept, merged over all its references."""
	parts: dict[str, dict[str, set[str]]] = {}
	for relation in linkbases.of(f"{{{LINK}}}referenceArc", CONCEPT_REFERENCE):
		for part in linkbases.resources[relation.target].iterchildren(f"{{{HGBREF}}}*"):
			parts.setdefault(relation.source, {}).setdefault(etree.QName(part).localname, set()).add(
				(part.text or "").strip()
			)
	return parts


def _networks(linkbases: _Linkbases, arc: str, arcrole: str) -> dict[str, Network]:
	arcs: dict[str, list[Arc]] = {}
	for relation in linkbases.of(arc, arcrole):
		weight = _attribute(relation, "weight")
		arcs.setdefault(relation.role, []).append(
			Arc(
				parent=relation.source,
				child=relation.target,
				order=Decimal(_attribute(relation, "order") or "1"),
				weight=None if weight is None else Decimal(weight),
				preferred_label=_attribute(relation, "preferredLabel"),
			)
		)
	return {role: Network(role, tuple(role_arcs)) for role, role_arcs in sorted(arcs.items())}


def _definitions(linkbases: _Linkbases) -> dict[str, tuple[DefinitionArc, ...]]:
	arcs: dict[str, list[DefinitionArc]] = {}
	for relation in linkbases.relations.get(f"{{{LINK}}}definitionArc", ()):
		closed = _attribute(relation, f"{{{XBRLDT}}}closed")
		arcs.setdefault(relation.role, []).append(
			DefinitionArc(
				arcrole=relation.arcrole,
				source=relation.source,
				target=relation.target,
				order=Decimal(_attribute(relation, "order") or "1"),
				context_element=_attribute(relation, f"{{{XBRLDT}}}contextElement"),
				closed=None if closed is None else closed == "true",
				usable=_attribute(relation, f"{{{XBRLDT}}}usable") != "false",
				target_role=_attribute(relation, f"{{{XBRLDT}}}targetRole"),
			)
		)
	return {role: tuple(role_arcs) for role, role_arcs in sorted(arcs.items())}
