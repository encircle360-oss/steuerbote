"""The instance of a report: the XBRL document of the facts of steuerbote/xbrl/facts.py for one view of the taxonomy.

The E-Bilanz takes the instance as the Nutzdaten of its ElsterXML (instance()), the Offenlegung as a file of its own
(write()). Both are written the same way, for the taxonomies of the generation 6 with their tuples; the taxonomy 7.0
needs a writer of its own (steuerbote/xbrl/facts.py).

Document. The root xbrli:xbrl declares the namespaces of XBRL 2.1, of XBRL Dimensions and of ISO 4217, and of the
modules of the view under the prefixes their schemas declare, de-gcd and de-gaap-ci; values and members name concepts
by those prefixes. It holds the entry points of the view, the contexts, the units and the facts, in this order (XBRL
2.1, Kap. 4). The entry points are the GCD and the GAAP entry point of the view, „immer genau eines zusammen mit dem
Einstiegsschema für die GCD“ (Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025, B.3), by their absolute
URLs (A.6). A document is UTF-8 with its declaration, „<?xml version=“1.0“ encoding=“utf-8“?>“ (Einheitliche
Elster-Datenschnittstelle XML, Stand 2026-02-12, Kap. 2.1), indented by tabs as the other documents of Steuerbote.
There is nothing but the standard taxonomy, no extension, linkbase or footnote of its own (Leitfaden B.10) and no
Inline XBRL.

Contexts. One context for each period and scenario the items refer to, and no other: „Jeder der im eingereichten
Datensatz spezifizierten Kontexte muss von mindestens einem Fakt referenziert werden.“ (Leitfaden B.14.7) Each names
the company as the report does, the one entity of the document. The instant of the Bilanzstichtag is I-AKTJAHR and
the fiscal year D-AKTJAHR, as in the examples of the ERiC documentation 44.3.6.0, and the previous year I-VORJAHR and
D-VORJAHR. The members of a table stand in the scenario, „Alle Dimensionen der HGB-Taxonomie sind
Szenario-Dimensionen“ (Leitfaden A.14.2.1), as explicit members in the order of the names of the dimensions; such a
context follows the one of its period without a scenario, numbered in the order of its members, D-AKTJAHR-1 and so
on. Outside the tables a context has no scenario, „Zusätzliche Angaben zur Definition von Kontexten („scenario“ und
„segment“) sind grundsätzlich unzulässig, allenfalls im Bereich der Tabellenbereiche“ (B.14.7), and the previous year
never has one: „Vorjahreskontexte dürfen nicht dimensional sein.“ (ERiC E-Bilanz-Dokumentation für HGB-Taxonomie 6.9,
ERiC 44.3.6.0, Kap. 3.2) An item of a table names a usable member of each of the dimensions of its table, since the
taxonomy gives no dimension a default member.

Units and numbers. An amount refers to the unit EUR, iso4217:EUR, „nur Euro als Währungsangabe“ (Leitfaden B.7), and
carries the decimals of the report: „Die monetären Wertangaben müssen auf zwei Nachkommastellen genau angegeben sein“
(B.7), decimals="2" (ERiC E-Bilanz-Dokumentation, Kap. 3.8). It is written with exactly as many places, and one
more exact than that is refused, since Steuerbote rounds where its rules say so and never while it writes. Another
number refers to the unit PURE, xbrli:pure, with the decimals of its item, as „<de-gcd:...shareholder.currentnumber
decimals="0" contextRef="D-AKTJAHR" unitRef="PURE">“ of the ERiC examples; the HGB-Taxonomie 6.9 has no item of the
type xbrli:sharesItemType, which would need the unit xbrli:shares. Only the units in use are written.

NIL. An item without a value is written xsi:nil="true", „leer“ (Leitfaden B.14.2.3), a number with its unit and
without decimals: „If a numeric fact has a nil value ... the precision and decimals attributes MUST NOT appear“ (XBRL
2.1, Kap. 4.6.3). A tuple without content is NIL.

Tuples. A tuple holds what the content of its complex type takes: each part as often as it may, those of a sequence
in its order, whatever order the report gives them in, and the values of a choice as empty elements (Leitfaden A.8,
B.14.1). A part of a tuple is reported inside it only: „Bei E-Bilanz wird diese Möglichkeit jedoch durch eine
zusätzliche Prüfung gezielt unterbunden“ (ERiC E-Bilanz-Dokumentation, Kap. 3.10).

Duplicates. No position twice in one context, no tuple twice with the same content, at the top or within a tuple:
„darf der an die Finanzverwaltung einzureichende Datensatz derartige Duplikate sowohl im GCD- als auch im GAAP-Bereich
nicht enthalten“ (Leitfaden B.14.13).

Characters. A text holds only the characters of ELSTER, „eine Teilmenge von ISO-8859-15“ (Einheitliche
Elster-Datenschnittstelle XML, Kap. 2.2; steuerbote/elster/charset.py), and line feeds and carriage returns: the
list of the ERiC E-Bilanz-Dokumentation, Kap. 3.16, „U+000A, U+000D, U+0020 bis einschließlich U+007E ...“. Its
„U+00A3F“ and „U+00B1B“ stand for U+00AF and U+00BB, which the pattern of the Datenschnittstelle lists. Texts from the
books are made to fit with steuerbote.elster.charset.transliterate() before they become facts.

Determinism. The same report gives the same bytes: the namespaces, contexts and units in a fixed order, the facts in
the order of the report and the parts of a tuple in the order of its content.

What cannot be written so raises a WriterError naming the position. This module is pure Python with lxml and never
imports Frappe.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from lxml import etree

from steuerbote.elster.charset import ALLOWED, describe
from steuerbote.xbrl.facts import Fact, Item, Period, Report, Tuple
from steuerbote.xbrl.taxonomy import Concept, Kind, PeriodType, Taxonomy
from steuerbote.xbrl.versions import BASE_URL

XBRLI = "http://www.xbrl.org/2003/instance"
LINK = "http://www.xbrl.org/2003/linkbase"
XLINK = "http://www.w3.org/1999/xlink"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
ISO4217 = "http://www.xbrl.org/2003/iso4217"
NAMESPACES = {"xbrli": XBRLI, "link": LINK, "xlink": XLINK, "xsi": XSI, "xbrldi": XBRLDI, "iso4217": ISO4217}
DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>\n'
EUR = "EUR"
PURE = "PURE"
MEASURES = {EUR: "iso4217:EUR", PURE: "xbrli:pure"}
"""Each unit with its measure, in the order of the document."""
CONTEXT_IDS = {
	Period.STICHTAG: "I-AKTJAHR",
	Period.WIRTSCHAFTSJAHR: "D-AKTJAHR",
	Period.VORJAHR_STICHTAG: "I-VORJAHR",
	Period.VORJAHR: "D-VORJAHR",
}
CHARACTERS = ALLOWED | {"\n", "\r"}
"""The characters of a text (ERiC E-Bilanz-Dokumentation, Kap. 3.16)."""
BOOLEAN = "xbrli:booleanItemType"
DATE = "xbrli:dateItemType"
QNAME = "xbrli:QNameItemType"
INTEGER_TYPES = frozenset(
	{
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
"""The numeric item types of XBRL 2.1 whose values are whole numbers."""

type _Context = tuple[Period, tuple[tuple[str, str], ...]]


class WriterError(ValueError):
	"""The report cannot be written as an instance of the view."""


def entry_points(taxonomy: Taxonomy) -> tuple[str, ...]:
	"""The URLs a report of the view references, the GCD first (Leitfaden A.6, B.3)."""
	return tuple(BASE_URL + path for path in taxonomy.entry_points)


def write(report: Report, taxonomy: Taxonomy) -> bytes:
	"""The instance as a document of its own."""
	root = instance(report, taxonomy)
	etree.indent(root, space="\t")
	return DECLARATION + etree.tostring(root, encoding="unicode").encode("utf-8") + b"\n"


def instance(report: Report, taxonomy: Taxonomy) -> etree._Element:
	"""The xbrli:xbrl element of the report, after every fact is checked against the view."""
	return _Writer(report, taxonomy).instance()


class _Writer:
	def __init__(self, report: Report, taxonomy: Taxonomy) -> None:
		self.report = report
		self.taxonomy = taxonomy
		self.units: set[str] = set()

	def instance(self) -> etree._Element:
		report = self.report
		expected = entry_points(self.taxonomy)
		if report.schema_refs != expected:
			raise WriterError(
				f"a report of the view {self.taxonomy.view} references the entry points {', '.join(expected)}"
			)
		if report.monetary_decimals < 0:
			raise WriterError("a report gives its amounts to the euro at least, with 0 or more decimals")
		self._check_facts(report.facts, "the report", top=True)
		contexts = sorted(report.contexts(), key=_context_order)
		ids = _context_ids(contexts)
		nsmap = NAMESPACES | {
			prefix: self.taxonomy.namespaces[prefix] for prefix in sorted(self.taxonomy.namespaces)
		}
		root = etree.Element(_xbrli("xbrl"), nsmap=nsmap)
		for url in report.schema_refs:
			etree.SubElement(
				root, f"{{{LINK}}}schemaRef", {f"{{{XLINK}}}type": "simple", f"{{{XLINK}}}href": url}
			)
		for context in contexts:
			self._context(root, ids[context], *context)
		for unit, measure in MEASURES.items():
			if unit in self.units:
				etree.SubElement(
					etree.SubElement(root, _xbrli("unit"), {"id": unit}), _xbrli("measure")
				).text = measure
		for fact in report.facts:
			self._fact(root, fact, ids)
		return root

	def _concept(self, name: str) -> Concept:
		concept = self.taxonomy.concepts.get(name)
		if concept is None:
			raise WriterError(
				f"the view {self.taxonomy.view} of the HGB-Taxonomie {self.taxonomy.version} has no concept {name}"
			)
		return concept

	def _check_facts(self, facts: Iterable[Fact], where: str, *, top: bool = False) -> None:
		facts = tuple(facts)
		counts = Counter(_key(fact) for fact in facts)
		repeated = tuple(dict.fromkeys(fact.concept for fact in facts if counts[_key(fact)] > 1))
		if repeated:
			raise WriterError(f"{where} holds {', '.join(repeated)} twice (Leitfaden B.14.13)")
		for fact in facts:
			if top and self.taxonomy.tuples_of(fact.concept):
				raise WriterError(
					f"{fact.concept} is a part of {', '.join(self.taxonomy.tuples_of(fact.concept))} and is reported "
					"inside it only (ERiC E-Bilanz-Dokumentation, Kap. 3.10)"
				)
			if isinstance(fact, Item):
				self._check_item(fact)
			else:
				self._check_tuple(fact)

	def _check_item(self, item: Item) -> None:
		concept = self._concept(item.concept)
		if concept.kind is not Kind.ITEM or concept.abstract:
			raise WriterError(f"{item.concept} is no position that holds a value")
		if item.period.instant != (concept.period_type is PeriodType.INSTANT):
			raise WriterError(
				f"{item.concept} is a position of the period type {concept.period_type}, not of the period "
				f"{item.period.value} (Leitfaden B.8)"
			)
		if item.period.prior and item.dimensions:
			raise WriterError(
				f"{item.concept} refers to the previous year, whose contexts have no dimensions (ERiC "
				"E-Bilanz-Dokumentation, Kap. 3.2)"
			)
		self._check_dimensions(item)
		if concept.numeric:
			self.units.add(EUR if concept.monetary else PURE)
		if item.value is not None:
			self._check_value(item, concept)

	def _check_dimensions(self, item: Item) -> None:
		tables = self.taxonomy.tables_of(item.concept)
		if not tables:
			if item.dimensions:
				raise WriterError(
					f"{item.concept} is in no table, so its context has no scenario (Leitfaden B.14.7)"
				)
			return
		members = dict(item.dimensions)
		for table in tables:
			if len(members) == len(table.dimensions) and all(
				members.get(dimension.name) in dimension.members for dimension in table.dimensions
			):
				return
		expected = "; ".join(
			f"{table.hypercube}: {', '.join(dimension.name for dimension in table.dimensions)}"
			for table in tables
		)
		raise WriterError(f"{item.concept} names a usable member of each dimension of its table ({expected})")

	def _check_value(self, item: Item, concept: Concept) -> None:
		value = item.value
		if concept.monetary:
			if not isinstance(value, Decimal):
				raise WriterError(f"the amount of {item.concept} is a Decimal, not {value!r}")
			_require_exact(item.concept, "amount", value, self.report.monetary_decimals)
		elif concept.numeric:
			whole = concept.item_type in INTEGER_TYPES
			if isinstance(value, bool) or not isinstance(value, int if whole else Decimal | int):
				raise WriterError(f"{item.concept} takes a {'whole ' if whole else ''}number, not {value!r}")
			if item.decimals is None:
				raise WriterError(f"the number of {item.concept} names its decimals")
			_require_exact(item.concept, "number", Decimal(value), item.decimals)
		elif concept.item_type == BOOLEAN:
			if not isinstance(value, bool):
				raise WriterError(f"{item.concept} takes true or false, not {value!r}")
		elif concept.item_type == DATE:
			if not isinstance(value, date) or isinstance(value, datetime):
				raise WriterError(f"{item.concept} takes a date, not {value!r}")
		elif not isinstance(value, str):
			raise WriterError(f"{item.concept} takes a text, not {value!r}")
		else:
			if concept.item_type == QNAME and value.partition(":")[0] not in self.taxonomy.namespaces:
				raise WriterError(
					f"{item.concept} names a position with the prefix of its module, such as de-gaap-ci:bs.ass, "
					f"not {value}"
				)
			refused = tuple(dict.fromkeys(character for character in value if character not in CHARACTERS))
			if refused:
				raise WriterError(
					f"{item.concept} holds characters ELSTER does not take: "
					f"{', '.join(describe(character) for character in refused)}"
				)

	def _check_tuple(self, fact: Tuple) -> None:
		concept = self._concept(fact.concept)
		if concept.kind is not Kind.TUPLE:
			raise WriterError(f"{fact.concept} is no tuple")
		if fact.nil:
			return
		content = concept.content
		counts = Counter(self._particle(fact, concept, child) for child in fact.children)
		if content.group == "choice":
			low = content.min_occurs * min(particle.min_occurs for particle in content.particles)
			highs = [particle.max_occurs for particle in content.particles]
			high = None if content.max_occurs is None or None in highs else content.max_occurs * max(highs)
			allowed = low <= len(fact.children) and (high is None or len(fact.children) <= high)
		else:
			allowed = all(
				particle.min_occurs <= counts[index]
				and (particle.max_occurs is None or counts[index] <= particle.max_occurs)
				for index, particle in enumerate(content.particles)
			)
		if not allowed:
			raise WriterError(
				f"the tuple {fact.concept} holds a part more often or more rarely than its content allows"
			)
		self._check_facts(fact.children, f"the tuple {fact.concept}")

	def _particle(self, fact: Tuple, concept: Concept, child: Fact) -> int:
		"""The place of a part in the content of its tuple."""
		for index, particle in enumerate(concept.content.particles):
			if child.concept == particle.concept or child.concept in self.taxonomy.substitutes(
				particle.concept
			):
				return index
		raise WriterError(f"the tuple {fact.concept} takes no {child.concept}")

	def _context(
		self, root: etree._Element, id: str, period: Period, dimensions: tuple[tuple[str, str], ...]
	) -> None:
		context = etree.SubElement(root, _xbrli("context"), {"id": id})
		entity = etree.SubElement(context, _xbrli("entity"))
		identifier = etree.SubElement(entity, _xbrli("identifier"), {"scheme": self.report.entity.scheme})
		identifier.text = self.report.entity.identifier
		element = etree.SubElement(context, _xbrli("period"))
		start, end = self.report.periods.dates(period)
		if start is None:
			etree.SubElement(element, _xbrli("instant")).text = end.isoformat()
		else:
			etree.SubElement(element, _xbrli("startDate")).text = start.isoformat()
			etree.SubElement(element, _xbrli("endDate")).text = end.isoformat()
		if dimensions:
			scenario = etree.SubElement(context, _xbrli("scenario"))
			for dimension, member in dimensions:
				etree.SubElement(
					scenario, f"{{{XBRLDI}}}explicitMember", {"dimension": dimension}
				).text = member

	def _fact(self, parent: etree._Element, fact: Fact, ids: Mapping[_Context, str]) -> None:
		concept = self.taxonomy.concepts[fact.concept]
		tag = f"{{{concept.namespace}}}{concept.local_name}"
		if isinstance(fact, Tuple):
			element = etree.SubElement(parent, tag)
			if fact.nil:
				element.set(f"{{{XSI}}}nil", "true")
			for child in sorted(fact.children, key=lambda child: self._particle(fact, concept, child)):
				self._fact(element, child, ids)
			return
		element = etree.SubElement(parent, tag, {"contextRef": ids[(fact.period, fact.dimensions)]})
		if concept.numeric:
			element.set("unitRef", EUR if concept.monetary else PURE)
		if fact.value is None:
			element.set(f"{{{XSI}}}nil", "true")
			return
		if concept.numeric:
			decimals = self.report.monetary_decimals if concept.monetary else fact.decimals
			element.set("decimals", str(decimals))
			element.text = _number(fact.value, decimals)
		else:
			element.text = _text(fact.value) or None


def _xbrli(name: str) -> str:
	return f"{{{XBRLI}}}{name}"


def _key(fact: Fact) -> object:
	return (fact.concept, fact.period, fact.dimensions) if isinstance(fact, Item) else fact


def _context_order(context: _Context) -> tuple:
	period, dimensions = context
	return list(Period).index(period), bool(dimensions), dimensions


def _context_ids(contexts: Iterable[_Context]) -> dict[_Context, str]:
	ids: dict[_Context, str] = {}
	numbers: Counter[Period] = Counter()
	for period, dimensions in contexts:
		base = CONTEXT_IDS[period]
		if dimensions:
			numbers[period] += 1
			ids[(period, dimensions)] = f"{base}-{numbers[period]}"
		else:
			ids[(period, dimensions)] = base
	return ids


def _require_exact(concept: str, kind: str, value: Decimal, decimals: int) -> None:
	try:
		exact = value.is_finite() and value == value.quantize(Decimal(1).scaleb(-decimals))
	except InvalidOperation:
		exact = False
	if not exact:
		raise WriterError(
			f"{concept} has the {kind} {value}, which is no finite number to {decimals} decimals"
		)


def _number(value: object, decimals: int) -> str:
	number = Decimal(value)
	return format(abs(number) if number == 0 else number, f".{max(decimals, 0)}f")


def _text(value: str | bool | date) -> str:
	if isinstance(value, bool):
		return "true" if value else "false"
	if isinstance(value, date):
		return value.isoformat()
	return value
