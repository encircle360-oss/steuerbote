"""An XBRL instance read into the facts of steuerbote/xbrl/facts.py, for the tests against the examples of the ERiC
documentation.

The periods come from the GCD of the instance: the fiscal year from genInfo.report.period.fiscalYearBegin and
fiscalYearEnd, the Bilanzstichtag from balSheetClosingDate and the previous year from fiscalPreviousYearBegin and
fiscalPreviousYearEnd, as the examples write them. A context refers to the instant or the fiscal year it names, of the
report or of its previous year. The facts model has no typed dimensions, which the examples of partnerships use for
their Kapitalkontenentwicklung, so the facts of a context with a typed member are left out. A position name of the
Kontensalden without a prefix names a position of the GAAP module: „Ist diese Angabe nicht vorhanden, so wird als
Namensraum der Ziel-Namensraum des gewählten Einstiegsschemas ... angenommen.“ (ERiC E-Bilanz-Dokumentation für
HGB-Taxonomie 6.9, ERiC 44.3.6.0, Kap. 3.12)
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from lxml import etree

from steuerbote.xbrl.facts import Entity, Fact, Item, Period, Periods, Report, Tuple
from steuerbote.xbrl.taxonomy import GAAP_PREFIX, Kind, Taxonomy

XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"
LINK = "{http://www.xbrl.org/2003/linkbase}"
XLINK = "{http://www.w3.org/1999/xlink}"
NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
PERIOD = "de-gcd:genInfo.report.period."
INTEGER_TYPES = frozenset(
	{"xbrli:integerItemType", "xbrli:nonNegativeIntegerItemType", "xbrli:positiveIntegerItemType"}
)


def read(path: Path, taxonomy: Taxonomy) -> Report:
	"""The report of the instance in the file of path, inside an ElsterXML envelope or on its own."""
	root = etree.parse(str(path)).getroot()
	instance = root if root.tag == f"{XBRLI}xbrl" else root.find(f".//{XBRLI}xbrl")
	return _Reader(instance, taxonomy).report()


class _Reader:
	def __init__(self, instance: etree._Element, taxonomy: Taxonomy) -> None:
		self.instance = instance
		self.taxonomy = taxonomy
		self.prefixes = {namespace: prefix for prefix, namespace in taxonomy.namespaces.items()}
		self.contexts = {context.get("id"): context for context in instance.iter(f"{XBRLI}context")}

	def report(self) -> Report:
		dates = {
			etree.QName(element).localname: date.fromisoformat(element.text.strip())
			for element in self.instance
			if isinstance(element.tag, str)
			and self._name(element).startswith(PERIOD)
			and element.get(NIL) != "true"
		}
		self.periods = Periods(
			dates["genInfo.report.period.fiscalYearBegin"],
			dates["genInfo.report.period.fiscalYearEnd"],
			dates.get("genInfo.report.period.balSheetClosingDate"),
			dates.get("genInfo.report.period.fiscalPreviousYearBegin"),
			dates.get("genInfo.report.period.fiscalPreviousYearEnd"),
		)
		identifier = next(iter(self.contexts.values())).find(f"{XBRLI}entity/{XBRLI}identifier")
		facts = [
			fact
			for element in self.instance
			if isinstance(element.tag, str) and not element.tag.startswith((XBRLI, LINK))
			if (fact := self._fact(element)) is not None
		]
		return Report(
			Entity(identifier.get("scheme"), identifier.text.strip()),
			self.periods,
			tuple(reference.get(f"{XLINK}href") for reference in self.instance.iter(f"{LINK}schemaRef")),
			tuple(facts),
		)

	def _name(self, element: etree._Element) -> str:
		qname = etree.QName(element)
		return f"{self.prefixes.get(qname.namespace, qname.namespace)}:{qname.localname}"

	def _fact(self, element: etree._Element) -> Fact | None:
		name = self._name(element)
		concept = self.taxonomy.concept(name)
		if concept.kind is Kind.TUPLE:
			children = tuple(
				fact
				for child in element
				if isinstance(child.tag, str)
				if (fact := self._fact(child)) is not None
			)
			if element.get(NIL) == "true":
				return Tuple(name, nil=True)
			return Tuple(name, children) if children or not len(element) else None
		context = self.contexts[element.get("contextRef")]
		if next(context.iter(f"{XBRLDI}typedMember"), None) is not None:
			return None
		dimensions = tuple(
			(member.get("dimension"), member.text.strip())
			for member in context.iter(f"{XBRLDI}explicitMember")
		)
		decimals = element.get("decimals")
		value = None if element.get(NIL) == "true" else self._value(element, concept.item_type)
		return Item(
			name,
			self._period(context),
			value,
			dimensions,
			None if concept.monetary or decimals is None or value is None else int(decimals),
		)

	def _value(self, element: etree._Element, item_type: str | None):
		text = (element.text or "").strip()
		if item_type == "xbrli:monetaryItemType":
			return Decimal(text)
		if item_type in INTEGER_TYPES:
			return int(text)
		if item_type in ("xbrli:decimalItemType", "xbrli:pureItemType"):
			return Decimal(text)
		if item_type == "xbrli:booleanItemType":
			return text == "true"
		if item_type == "xbrli:dateItemType":
			return date.fromisoformat(text)
		if item_type == "xbrli:QNameItemType":
			prefix, _, local = text.rpartition(":")
			if not prefix:
				return f"{GAAP_PREFIX}:{local}"
			return f"{self.prefixes[element.nsmap[prefix]]}:{local}"
		return element.text or ""

	def _period(self, context: etree._Element) -> Period:
		period = context.find(f"{XBRLI}period")
		instant = period.findtext(f"{XBRLI}instant")
		if instant is not None:
			day = date.fromisoformat(instant.strip())
			return Period.STICHTAG if day == self.periods.balance_sheet_date else Period.VORJAHR_STICHTAG
		end = date.fromisoformat(period.findtext(f"{XBRLI}endDate").strip())
		return Period.WIRTSCHAFTSJAHR if end == self.periods.fiscal_year_end else Period.VORJAHR
