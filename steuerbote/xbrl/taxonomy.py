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

A concept is a global element of a schema with an id: its name with the prefix its schema declares for its
namespace (de-gcd, de-gaap-ci), its type, period type and balance, whether it is abstract or nillable, and its
substitution group (XBRL 2.1, Kap. 5.1.1). The group makes it an item or a tuple, or, through XBRL Dimensions, a
hypercube or a dimension; an element in the group of another element, such as a value of a choice in the group of its
abstract head, takes the kind of that element. A tuple has the content of its complex type: a sequence of its parts or
a choice, each part with its minOccurs and maxOccurs. „Positionen mit Auswahlwerten“ are tuples whose choice takes the
substitutes of a head, „Positionen zur Einfachauswahl“ once and „Positionen zur Mehrfachauswahl“ more often (Leitfaden
A.8, B.14.1).

This module is pure Python with lxml and never imports Frappe.
"""

import posixpath
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
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
WELL_KNOWN = MappingProxyType({XBRLI: "xbrli", XBRLDT: "xbrldt", XS: "xs", LINK: "link", XLINK: "xlink"})
"""The prefixes of the namespaces of XBRL itself, the same in every schema that names them."""
GAAP_PREFIX = "de-gaap-ci"
"""The module a name without a prefix belongs to: the Bilanzzuordnung names the positions of the GAAP module so."""

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, remove_comments=True)


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
	_substitutes: Mapping[str, tuple[str, ...]] = field(init=False, repr=False, compare=False)
	_tuples: Mapping[str, tuple[str, ...]] = field(init=False, repr=False, compare=False)

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

	def has(self, name: str) -> bool:
		return self._qualified(name) in self.concepts

	def concept(self, name: str) -> Concept:
		"""The concept of a name with its prefix, or of the GAAP module without one."""
		try:
			return self.concepts[self._qualified(name)]
		except KeyError:
			raise TaxonomyError(f"the HGB-Taxonomie {self.version} has no concept {name}") from None

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
	concepts = _concepts(schemas, prefixes)
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
	)


type _Name = tuple[str, str]
"""A QName as namespace and local name, before the taxonomy gives the namespace its prefix."""


@dataclass
class _Element:
	"""A global element of a schema as written, before its substitution group is followed."""

	name: str
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
	"""The unpacked package: its files by their path, each parsed once."""

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


def _concepts(schemas: Iterable[_Schema], prefixes: Mapping[str, str]) -> dict[str, Concept]:
	declared: dict[str, tuple[_Schema, _Element]] = {}
	for schema in schemas:
		for element in schema.elements:
			declared[f"{prefixes[schema.target]}:{element.name}"] = (schema, element)

	def qualified(name: _Name) -> str:
		namespace, local = name
		return f"{prefixes[namespace]}:{local}" if namespace in prefixes else f"{{{namespace}}}{local}"

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
