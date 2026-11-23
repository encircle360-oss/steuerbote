"""The simulation of the Körperschaftsteuererklärung, Datenart KSt (Jahresdokumentation_E30_<Jahr>.ods): the
structure of an Erklärung with the main form KSt1, and the rules of the year in RULES.

Sources are Jahresdokumentation_E30_2025.ods of the ERiC documentation 44.3.6.0, cited as JD, the provisional data of
VZ 2026 (steuerbote.kst.form), and the „ERiC Zusatzinformation zur Plausibilitätsprüfung“ of that documentation,
Kap. 4, cited as ZI, which describes the language of the Prüfbedingungen.

RULES checks the rules of the catalogue of the VZ (steuerbote.kst.form.CATALOGUES): the Vordrucke and fields a GmbH
has to file, and the sums and roundings of Steuerbote's computation. CONDITIONS reads the Prüfbedingung of each in
Python, and reads the Nutzdaten as ZI does:
- a field is given when it holds a value, a context or a Vordruck when one of its fields does (ZI Tabellen 4-6 to
  4-8); the Indexfeld WJ is no field;
- in a sum a field that is not given counts as zero, the „Summe aller Werte der angegebenen Felder“ (ZI Kap. 4.3.2),
  and a field of a repeated context counts with every instance; the long sums, such as GK_INCOME, hold the fields
  of their Prüfbedingung with its signs;
- Abrunden and Aufrunden go to the next smaller and the next greater whole number (ZI Tabelle 4-12), through
  steuerbote.ustva.rounding;
- a rule of a Vordruck that may stand twice, Anlage GK and KSt 1 F, holds for each of them („Prüfung für mehrere
  Vordrucke: Alle“), and [E8109901 Fuer "WJ1"] is the field of the Anlage GK of the first Wirtschaftsjahr;
- [E8001105->RF_Gruppe] is a category of the Rechtsform of KSt 1 line 9 (steuerbote.kst.form.RECHTSFORMEN, the GmbH and
  the UG); another Rechtsform has none, so a rule that asks for a category does not apply to it.
A rule that fails gives an error with its Fehlercode, as ERiC reports it, whose text names the rule, the
Jahresdokumentation and the field or Vordruck it is about, such as „Die Regel 8906061 (Regel_160151_GK_Zinsschranke) der
Jahresdokumentation E30 2025 schlägt an: E8109901 im Vordruck GK, Zeile 300.“ The texts of the JD, its Prüfbedingungen
and its Fehler- and Hinweistexte, are not in the repository, since the JD carries no licence that allows passing it on,
as for USt2A (steuerbote.eric.simulation.ust): the test against the JD holds the SHA-256 of each Prüfbedingung read and
the terms of each long sum. A rule that would compute with a text that is no number gives nothing: the schema refuses
the text. The Hinweis 8912019 on the Solidaritätszuschlag of Anlage WA is left out, since the simulation takes every
message of a rule for an error (steuerbote.eric.fake), and the computation writes the Solidaritätszuschlag of the
Steuerbescheinigungen as they are.

The rules apply to a VZ Steuerbote has Vordrucke for. Another VZ, such as 2025 of the examples of the documentation,
is checked for its structure only.

Vordruck, Erklaerung, Condition and rules() also read the Gewerbesteuererklärung (steuerbote.eric.simulation.gewst).
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import TYPE_CHECKING
from xml.etree import ElementTree

from steuerbote.eric.datenart import Datenart
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import ERROR, Message
from steuerbote.eric.simulation import Rule, erklaerung
from steuerbote.ustva.rounding import ZERO, ceil_euro, floor_euro

if TYPE_CHECKING:
	# steuerbote.elster imports lxml, which the simulation runs without (steuerbote.eric.fake).
	from steuerbote.elster.erklaerung import FormCatalogue

TITLE = "Körperschaftsteuererklärung"
MAIN_FORM = "KSt1"
INDEX = "WJ"
YES, NO = "1", "2"
"""Wahr and Falsch of a JaNeinFeld, Formatkennzeichen Y."""

type Categories = Mapping[str, Mapping[str, str]]
"""The categories of the Rechtsformen of a year by their key, such as {"350": {"RF_Gruppe": "1"}}."""
type Terms = tuple[tuple[int, str], ...]
"""The fields of a sum with their signs, such as ((1, "E8002001"), (-1, "E8002204"))."""


class NotANumber(ValueError):
	"""A field a rule computes with holds no number."""


def number(text: str) -> Decimal:
	"""The value of a number in the Nutzdaten, with its decimal comma."""
	try:
		value = Decimal(text.replace(",", "."))
	except InvalidOperation:
		raise NotANumber(text) from None
	if not value.is_finite():
		raise NotANumber(text)
	return value


def sum_of(text: str) -> Terms:
	"""The terms of a sum written as its fields, each with a leading „-“ where the sum subtracts it, such as
	„E8002001 E8002004 -E8002204“."""
	return tuple((-1, term[1:]) if term.startswith("-") else (1, term) for term in text.split())


def fields(sum_terms: Terms) -> tuple[str, ...]:
	return tuple(field for _, field in sum_terms)


def _local(element: ElementTree.Element) -> str:
	return element.tag.rpartition("}")[2]


class Vordruck:
	"""A Vordruck of the Nutzdaten as the rules read it: the texts of its fields by Feldkennung, those of a repeated
	context once per instance, the fields of each instance of a context, the contexts that hold a value, and its
	Indexfeld."""

	def __init__(self, element: ElementTree.Element) -> None:
		self.name = _local(element)
		self.wj: str | None = None
		self.texts: defaultdict[str, list[str]] = defaultdict(list)
		self.contexts: set[str] = set()
		self.instances: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
		self._read(element, self.name)

	def _read(self, element: ElementTree.Element, path: str) -> bool:
		found = False
		here: dict[str, str] = {}
		for child in element:
			name = _local(child)
			text = (child.text or "").strip()
			if len(child):
				found = self._read(child, f"{path}/{name}") or found
			elif path == self.name and name == INDEX:
				self.wj = text
			elif text:
				self.texts[name].append(text)
				here[name] = text
				found = True
		self.instances[path].append(here)
		if found:
			self.contexts.add(path)
		return found

	@property
	def filled(self) -> bool:
		"""Whether one of its fields holds a value."""
		return self.name in self.contexts

	def any_of(self, *names: str) -> bool:
		"""FeldAngegeben, MindestensEinFeldAngegeben."""
		return any(name in self.texts for name in names)

	def all_of(self, *names: str) -> bool:
		"""AlleFelderAngegeben."""
		return all(name in self.texts for name in names)

	def text(self, name: str) -> str:
		return self.texts[name][0] if name in self.texts else ""

	def value(self, name: str) -> Decimal:
		"""The number of the field, the sum of its instances, zero where it is not given."""
		return sum((number(text) for text in self.texts.get(name, ())), ZERO)

	def total(self, sum_terms: Terms) -> Decimal:
		return sum((sign * self.value(field) for sign, field in sum_terms), ZERO)

	def context(self, path: str) -> bool:
		"""KontextAngegeben, by the path of the context below the root, such as Verluste/Anfang."""
		return path in self.contexts


class Erklaerung:
	"""The Vordrucke of Nutzdaten as the rules read them, with the categories of the Rechtsformen of their year."""

	def __init__(self, root: ElementTree.Element, categories: Categories) -> None:
		self.vordrucke = tuple(Vordruck(child) for child in root if _local(child) != "Vorsatz")
		self.categories = categories

	def each(self, form: str) -> tuple[Vordruck, ...]:
		"""The Vordrucke of the form that hold a value."""
		return tuple(vordruck for vordruck in self.vordrucke if vordruck.name == form and vordruck.filled)

	def has(self, form: str) -> bool:
		"""KontextAngegeben(/<form>), MindestensEinKontextAngegeben(/<form>*)."""
		return bool(self.each(form))

	def one(self, form: str, wj: str | None = None) -> Vordruck:
		"""The first Vordruck of the form, of the Wirtschaftsjahr if one is named; an empty one without it."""
		found = (vordruck for vordruck in self.each(form) if wj is None or vordruck.wj == wj)
		return next(found, Vordruck(ElementTree.Element(form)))

	def any_of(self, *names: str) -> bool:
		return any(vordruck.any_of(*names) for vordruck in self.vordrucke)

	def all_of(self, *names: str) -> bool:
		return all(self.any_of(name) for name in names)

	def text(self, name: str) -> str:
		return next((vordruck.text(name) for vordruck in self.vordrucke if vordruck.any_of(name)), "")

	def value(self, name: str) -> Decimal:
		return next((vordruck.value(name) for vordruck in self.vordrucke if vordruck.any_of(name)), ZERO)

	def category(self, field: str, name: str) -> str:
		"""[<field>->name]: the category of the value of a Rechtsform field, empty for a value without one."""
		return self.categories.get(self.text(field), MappingProxyType({})).get(name, "")


@dataclass(frozen=True, slots=True)
class Condition:
	"""The reading of a Prüfbedingung: the Fehlercode of its rule, the field or Vordruck its message names, and whether
	the rule fails for the Nutzdaten."""

	code: str
	field: str
	fails: Callable[[Erklaerung], bool]


@dataclass(frozen=True, slots=True)
class Documented:
	"""What the rules of a year read beside the Nutzdaten: the catalogue of its Vordrucke with the name of each rule and
	the line of each field, the categories of its Rechtsformen, and the Jahresdokumentation they come from."""

	catalogue: FormCatalogue
	categories: Categories
	documentation: str
	"""Such as „Jahresdokumentation E30 2025“."""

	def place(self, name: str) -> str:
		"""A Vordruck or a field as a message names it, such as „Vordruck GK“ or „E8109901 im Vordruck GK, Zeile 300“."""
		if name in {form.name for form in self.catalogue.forms}:
			return f"Vordruck {name}"
		field = self.catalogue.field(name)
		where = f"{field.feldkennung} im Vordruck {field.form}"
		return where if field.line is None else f"{where}, Zeile {field.line}"

	def failure(self, condition: Condition) -> str:
		"""The text of the error of a rule that fails (module docstring)."""
		name = next(rule.name for rule in self.catalogue.rules if rule.code == condition.code)
		return f"Die Regel {condition.code} ({name}) der {self.documentation} schlägt an: {self.place(condition.field)}."


type Year = Callable[[int], Documented | None]
"""What the rules of a year read; None for a year without Vordrucke."""


@dataclass(frozen=True, slots=True)
class SimulatedRule:
	"""A rule of RULES: the Condition of a rule of the JD on Nutzdaten of a year Steuerbote has Vordrucke for."""

	condition: Condition
	year: Year

	def __call__(self, root: ElementTree.Element, kind: Datenart, header: EnvelopeHeader) -> Message | None:
		documented = self.year(kind.year)
		if documented is None:
			return None
		try:
			failed = self.condition.fails(Erklaerung(root, documented.categories))
		except NotANumber:
			return None
		if not failed:
			return None
		return Message(self.condition.code, documented.failure(self.condition), ERROR, self.condition.field)


def rules(conditions: Iterable[Condition], year: Year) -> tuple[Rule, ...]:
	return tuple(SimulatedRule(condition, year) for condition in conditions)


def _year(year: int) -> Documented | None:
	# steuerbote.kst.form imports steuerbote.eric, whose package imports this module through steuerbote.eric.fake.
	from steuerbote.kst import form, years

	if year not in form.CATALOGUES:
		return None
	catalogue = form.CATALOGUES[year]
	documentation = f"Jahresdokumentation {catalogue.datenart.root} {years.YEARS[year].documentation_year}"
	return Documented(catalogue, form.RECHTSFORMEN[year], documentation)


RECHTSFORM = "E8001105"
KAPITALGESELLSCHAFT = ("1", "2")
"""RF_Gruppe 1 and 2: the Körperschaften of § 1 Absatz 1 Nummer 1 and 2 KStG."""
FIVE_PERCENT = Decimal("0.05")
"""§ 8b Absatz 3 and 5 KStG, as rules 8956020 and 8956042 write it."""
CORPORATE_TAX_RATE = Decimal("0.15")
"""Rule 8900331: „Die Körperschaftsteuer von 15 %“."""
MILLION = Decimal("1000000")
SEVENTY_PERCENT = Decimal("0.7")
"""§ 10d Absatz 2 Satz 1 EStG, as rules 8900184 and 8900170 write it."""

GK_INCOME = sum_of(
	"E8002001 E8002004 E8002006 -E8002204 E8002207 E8002215 E8002211 E8002216 -E8002303 E8002002 "
	"-E8001801 -E8001809 -E8001802 -E8001903 E8001803 E8001804 -E8001805 E8001806 E8001807 -E8001808 "
	"E8003002 E8003001 E8003101 E8003201 E8002110 -E8002111 E8002102 -E8002103 E8002104 -E8002105 "
	"E8002106 -E8002107 E8002108 -E8002109 E8004004 -E8004005 E8002601 -E8002602 E8002603 E8002604 "
	"E8002605 E8002701 E8002709 -E8002702 E8002902 E8002801 E8100201 E8100301 E8100501 E8100601 E8100702 "
	"E8100803 E8100804 E8100801 E8100901 E8101001 E8101101 E8101201 E8101301 E8101302 E8101401 -E8003301 "
	"-E8003401 -E8003402 -E8003601 E8003702 -E8009702 -E8003701 E8007025 E8007017 E8007019 E8004002 "
	"-E8007302 E8007408 -E8181001 E8181101 E8183001 -E8004437 E8004441 E8562101 E8562201 -E8562515 "
	"E8562516 E8011302 E8011602 E8011902 E8012202 E8012502 E8012802 E8012901 -E8016107 E8016108 -E8016109 "
	"-E8016201 E8016302 -E8016303 -E8160501 E8160601 E8160701 E8160903 -E8160902 -E8160909 E8160910 "
	"E8160911 -E8160904 E8162001 -E8162101 E8162201 E8162202 E8162204 E8017601 -E8017602 -E8017603 "
	"E8017604 E8004903 E8004905 -E8004902 -E8004906"
)
"""Anlage GK line 300 (E8109901) as rule 8906062 sums it."""
P8B_CORRECTION = sum_of(
	"E8560801 E8561410 E8561301 E8561411 E8561412 E8561601 E8561701 E8561801 -E8560401 -E8561212 "
	"-E8561220 -E8561237 -E8561501 -E8561901 -E8562001"
)
"""Anlage GK line 201 (E8562101) as rule 8956047 sums it."""
SUM_OF_INCOME = sum_of(
	"E8022101 E8022102 E8022103 E8004904 E8005002 E8022403 E8020503 -E8020603 -E8020702 E8020703 E8023202 "
	"E8023303 E8023701 E8023702 E8024101 E8021202 E8021201 E8024201 -E8024301 E8024401 -E8024404 "
	"-E8024405 E8024406 E8024601 -E8024604 -E8024605 E8024606 E8043701 E8043702 -E8004201 -E8004202 "
	"E8004301 -E8004401 -E8005301 -E8022801 -E8022901 E8023001 E8023101 E8023105 -E8023107"
)
"""Anlage ZVE line 32 (E8005401), the Summe der Einkünfte, as rule 8900207 sums it."""
TOTAL_INCOME = sum_of(
	"E8005401 -E8025101 -E8005601 E8005701 E8005702 E8006301 E8006401 E8006402 E8003302 E8003303 E8006501 "
	"E8006601 E8006608 E8006609"
)
"""Anlage ZVE line 53 (E8006901), the Gesamtbetrag der Einkünfte, as rule 8900413 sums it."""
ZVE = sum_of(
	"E8005401 -E8025101 -E8005601 E8005701 E8005702 E8006301 E8006401 E8006402 E8003302 E8003303 E8006501 "
	"E8006601 E8006608 E8006609 E8006801 -E8007001 -E8007002 -E8007101 -E8007103 -E8007102 -E8007104 "
	"-E8026301 E8025903 -E8006803 -E8007401"
)
"""Anlage ZVE line 70 (E8007501), the zu versteuerndes Einkommen, as rule 8900431 sums it."""
LOSS_BEFORE_DEDUCTION = sum_of(
	"E8007801 E8007803 -E8007804 E8007805 -E8007902 -E8007905 -E8007908 E8008001 -E8001902 -E8001904 "
	"-E8008102"
)
"""Anlage Verluste line 21, the first amount whose least with line 24 and 1 Million Euro rule 8900184 takes for line
25 (E8008601)."""
LOSS_INCOME = sum_of("E8008501 -E8008502")
"""Anlage Verluste line 22 less line 23, the line 24 of rule 8900184."""
LOSS_BEFORE_LIMITED = sum_of(
	"E8007801 E8007803 -E8007804 E8007805 -E8007902 -E8007905 -E8007908 E8008001 -E8001902 -E8001904 "
	"-E8008102 -E8008602"
)
"""Anlage Verluste line 21 less line 25 (E8008602), the Verlustvortrag rule 8900170 leaves for line 27 (E8008801)."""
LOSS_INCOME_LIMITED = sum_of("E8008501 -E8008502 -E8008601")
"""Anlage Verluste line 22 less lines 23 and 25 (E8008601), of which rule 8900170 takes 70 % for line 27."""
LOSS_REMAINING = sum_of(
	"E8007801 E8007803 -E8007804 E8007805 -E8007902 -E8007905 -E8007908 E8008001 -E8001902 -E8001904 "
	"-E8008102 -E8008602 -E8008801"
)
"""Anlage Verluste line 28 (E8009201), the verbleibender Verlustvortrag, as rule 8900347 sums it."""
EINLAGEKONTO_CLOSING = sum_of(
	"E8240102 E8240103 -E8241715 -E8241716 -E8242201 -E8242202 -E8242204 -E8242205 E8240602 E8241202 "
	"E8243006 -E8241305 E8241407 -E8241410 E8241416 E8241501 E8241502 E8241601 E8241602 E8241603 E8244103 "
	"E8246102 E8246103 E8242301 E8242702 -E8242901 E8243001 -E8243502 E8243603 -E8243902 -E8244108 "
	"E8244502 -E8244702 -E8245202 -E8245403 E8245409 E8241901 -E8245501"
)
"""KSt 1 F line 152 (E8245601), the Endbestände, as rule 8924445 sums them."""
EINLAGEKONTO_OPENING = sum_of("E8240102 E8240103 -E8241715 -E8241716")
"""KSt 1 F line 46 (E8241717), the Zwischensumme, as rule 8920012 sums it."""
LOSS_CONTEXTS = (
	"Verluste/Anfang",
	"Verluste/Negativ",
	"Verluste/Positiv/Vorspalte",
	"Verluste/Positiv/Hauptspalte",
)


def _kapitalgesellschaft(e: Erklaerung) -> bool:
	return e.category(RECHTSFORM, "RF_Gruppe") in KAPITALGESELLSCHAFT


def _each_gk(e: Erklaerung, fails: Callable[[Vordruck], bool]) -> bool:
	return any(fails(gk) for gk in e.each("GK"))


def _each_kst1f(e: Erklaerung, fails: Callable[[Vordruck], bool]) -> bool:
	return any(fails(kst1f) for kst1f in e.each("KSt1F"))


def _total_without_single_values(total: str, single: str) -> Callable[[Erklaerung], bool]:
	"""A total of Anlage GK given without the single values of its holdings."""
	return lambda e: _each_gk(e, lambda gk: gk.any_of(total) and not gk.any_of(single))


def _total_of_single_values(
	total: str, single: str, rounded: Callable[[Decimal], Decimal] = lambda amount: amount
) -> Callable[[Erklaerung], bool]:
	"""A total of Anlage GK that is not the sum of the single values of its holdings, rounded."""
	return lambda e: _each_gk(
		e, lambda gk: gk.all_of(total, single) and gk.value(total) != rounded(gk.value(single))
	)


def _excess(kst1f: Vordruck) -> Decimal:
	"""KSt 1 F line 47 less line 48: the Leistungen beyond the ausschüttbarer Gewinn."""
	return kst1f.value("E8240302") - kst1f.value("E8240401")


def _set_off(kst1f: Vordruck) -> bool:
	"""Whether the Einlagekonto is set off against the Leistungen: lines 46 to 54 are needed (8920012, 8920013)."""
	return kst1f.total(EINLAGEKONTO_OPENING) > ZERO and (
		_excess(kst1f) > ZERO or kst1f.any_of("E8240303", "E8242205")
	)


CONDITIONS: tuple[Condition, ...] = (
	Condition(
		"8906010",
		"GK",
		lambda e: (
			not e.has("GK")
			and e.category(RECHTSFORM, "NurG") == "1"
			and not e.all_of("E8000603", "E8000702")
			and not e.any_of("E8000803", "E8001506", "E8025903", "E8001702")
		),
	),
	Condition("8900744", "ZVE", lambda e: not e.has("ZVE") and not e.any_of("E8001506")),
	Condition("8912208", "WA", lambda e: e.category(RECHTSFORM, "RF_Gruppe") == "1" and not e.has("WA")),
	Condition(
		"8912209",
		"E8122801",
		lambda e: e.has("WA") and e.category(RECHTSFORM, "RF_Gruppe") == "1" and not e.any_of("E8122801"),
	),
	Condition(
		"8931022",
		"KSt1F",
		lambda e: (
			not e.has("KSt1F")
			and _kapitalgesellschaft(e)
			and not e.any_of("E8001702")
			and (e.any_of("E8000803") or not e.all_of("E8000603", "E8000702"))
		),
	),
	Condition(
		"8900709", "E8000016", lambda e: not e.any_of("E8000016") and (e.has("KSt1F") or e.has("KSt1Fa"))
	),
	Condition(
		"8912151",
		"E8122101",
		lambda e: not e.any_of("E8122101") and e.has("KSt1") and _kapitalgesellschaft(e),
	),
	Condition(
		"8912163",
		"E8122601",
		lambda e: e.has("KSt1") and not e.any_of("E8122601", "E8001506") and _kapitalgesellschaft(e),
	),
	Condition("8900368", "E8001007", lambda e: not e.any_of("E8001007", "E8001505")),
	Condition("8900070", "E8002001", lambda e: _each_gk(e, lambda gk: not gk.any_of("E8002001", "E8002004"))),
	Condition("8906061", "E8109901", lambda e: _each_gk(e, lambda gk: not gk.any_of("E8109901"))),
	Condition("8900548", "E8004904", lambda e: not e.any_of("E8004904") and e.has("GK")),
	Condition(
		"8900100",
		"E8005401",
		lambda e: not e.any_of("E8005401") and e.has("ZVE") and not e.any_of("E8025903", "E8007704"),
	),
	Condition(
		"8900818",
		"E8006901",
		lambda e: (
			not e.any_of("E8006901")
			and e.has("ZVE")
			and not e.any_of("E8025903", "E8007704")
			and not e.has("OHK")
		),
	),
	Condition("8900836", "E8007501", lambda e: not e.any_of("E8007501", "E8007704") and e.has("ZVE")),
	Condition("8918391", "E8009201", lambda e: e.has("Verluste") and not e.any_of("E8009201")),
	Condition(
		"8920227",
		"E8245601",
		lambda e: _each_kst1f(
			e, lambda kst1f: not kst1f.any_of("E8245601") and kst1f.any_of("E8240102", "E8240103")
		),
	),
	Condition(
		"8924512",
		"E8240103",
		lambda e: _each_kst1f(
			e, lambda kst1f: not kst1f.any_of("E8240102", "E8240104", "E8240103", "E8240201")
		),
	),
	Condition("8956060", "E8560404", _total_without_single_values("E8560401", "E8560404")),
	Condition("8956070", "E8561211", _total_without_single_values("E8561212", "E8561211")),
	Condition("8956072", "E8561403", _total_without_single_values("E8561410", "E8561403")),
	Condition("8905507", "E8561210", _total_without_single_values("E8561220", "E8561210")),
	Condition("8905516", "E8561408", _total_without_single_values("E8561411", "E8561408")),
	Condition(
		"8906062",
		"E8109901",
		lambda e: _each_gk(
			e,
			lambda gk: (
				gk.any_of("E8109901")
				and gk.any_of("E8002001", "E8002004")
				and gk.value("E8109901") != gk.total(GK_INCOME)
			),
		),
	),
	Condition(
		"8956047",
		"E8562101",
		lambda e: (
			not e.any_of("E8160202")
			and _each_gk(
				e,
				lambda gk: (
					gk.any_of("E8562101")
					and gk.any_of(*fields(P8B_CORRECTION))
					and gk.value("E8562101") != gk.total(P8B_CORRECTION)
				),
			)
		),
	),
	Condition(
		"8956020",
		"E8560801",
		lambda e: (
			not e.any_of("E8160202")
			and _each_gk(
				e,
				lambda gk: (
					gk.all_of("E8560801", "E8560401")
					and gk.value("E8560801") != floor_euro(gk.value("E8560401") * FIVE_PERCENT)
				),
			)
		),
	),
	Condition(
		"8956042",
		"E8561301",
		lambda e: (
			not e.any_of("E8160202")
			and _each_gk(
				e,
				lambda gk: (
					gk.any_of("E8561301")
					and gk.any_of("E8561212", "E8561220", "E8561237")
					and gk.value("E8561301")
					!= floor_euro(
						(gk.value("E8561212") + gk.value("E8561220") + gk.value("E8561237")) * FIVE_PERCENT
					)
				),
			)
		),
	),
	Condition("8956007", "E8560401", _total_of_single_values("E8560401", "E8560404", ceil_euro)),
	Condition("8956040", "E8561212", _total_of_single_values("E8561212", "E8561211", ceil_euro)),
	Condition("8956044", "E8561410", _total_of_single_values("E8561410", "E8561403", floor_euro)),
	Condition("8905506", "E8561220", _total_of_single_values("E8561220", "E8561210", ceil_euro)),
	Condition("8905515", "E8561411", _total_of_single_values("E8561411", "E8561408")),
	Condition(
		"8900549",
		"E8004904",
		lambda e: (
			e.any_of("E8004904")
			and len(e.each("GK")) == 1
			and e.value("E8004904") != e.one("GK", "WJ1").value("E8109901")
		),
	),
	Condition(
		"8900207",
		"E8005401",
		lambda e: (
			e.any_of("E8005401")
			and not e.any_of("E8001506", "E8025903")
			and e.value("E8005401") != e.one("ZVE").total(SUM_OF_INCOME)
		),
	),
	Condition(
		"8900413",
		"E8006901",
		lambda e: (
			e.any_of("E8006901")
			and not e.any_of("E8001506", "E8025903")
			and not e.has("OHK")
			and e.value("E8006901") != e.one("ZVE").total(TOTAL_INCOME)
		),
	),
	Condition(
		"8900431",
		"E8007501",
		lambda e: (
			e.any_of("E8007501")
			and e.has("ZVE")
			and not e.any_of("E8025402")
			and e.value("E8007501") != e.one("ZVE").total(ZVE)
		),
	),
	Condition(
		"8900330",
		"E8007501",
		lambda e: (
			e.any_of("E8007504", "E8007603")
			and e.value("E8007501") != e.value("E8007504") + e.value("E8007603")
		),
	),
	Condition(
		"8900361",
		"E8007502",
		lambda e: e.any_of("E8007504", "E8007502") and not e.all_of("E8007504", "E8007502"),
	),
	Condition(
		"8900331",
		"E8007502",
		lambda e: (
			e.all_of("E8007502", "E8007504")
			and e.value("E8007504") > ZERO
			and e.value("E8007502") != floor_euro(e.value("E8007504") * CORPORATE_TAX_RATE)
		),
	),
	Condition(
		"8900570",
		"E8007502",
		lambda e: (
			e.all_of("E8007502", "E8007504") and e.value("E8007504") <= ZERO and e.value("E8007502") != ZERO
		),
	),
	Condition(
		"8900184",
		"E8008601",
		lambda e: (
			e.any_of("E8008601")
			and e.any_of("E8008501", "E8008502")
			and e.value("E8008601")
			!= min(
				e.one("Verluste").total(LOSS_BEFORE_DEDUCTION), e.one("Verluste").total(LOSS_INCOME), MILLION
			)
		),
	),
	Condition(
		"8900170",
		"E8008801",
		lambda e: (
			e.all_of("E8008801", "E8008701")
			and e.value("E8008801")
			!= min(
				e.one("Verluste").total(LOSS_BEFORE_LIMITED),
				ceil_euro(e.one("Verluste").total(LOSS_INCOME_LIMITED) * SEVENTY_PERCENT),
			)
		),
	),
	Condition(
		"8900347",
		"E8009201",
		lambda e: (
			e.any_of("E8009201")
			and any(e.one("Verluste").context(path) for path in LOSS_CONTEXTS)
			and e.value("E8009201") != e.one("Verluste").total(LOSS_REMAINING)
		),
	),
	Condition(
		"8920021",
		"E8201301",
		lambda e: _each_kst1f(
			e,
			lambda kst1f: (
				kst1f.any_of("E8201301")
				and kst1f.any_of("E8201001", "E8201101", "E8201201")
				and kst1f.value("E8201301")
				!= max(kst1f.value("E8201001") - kst1f.value("E8201101") - kst1f.value("E8201201"), ZERO)
			),
		),
	),
	Condition(
		"8924445",
		"E8245601",
		lambda e: _each_kst1f(
			e,
			lambda kst1f: (
				kst1f.any_of("E8245601")
				and kst1f.any_of("E8240102", "E8240103")
				and kst1f.value("E8245601") != kst1f.total(EINLAGEKONTO_CLOSING)
			),
		),
	),
	Condition(
		"8920011",
		"E8201001",
		lambda e: _each_kst1f(
			e,
			lambda kst1f: (
				kst1f.any_of("E8200502")
				and kst1f.value("E8240102") + kst1f.value("E8240103") > ZERO
				and not kst1f.all_of("E8201001", "E8201101", "E8201201", "E8201301")
			),
		),
	),
	Condition(
		"8920012",
		"E8241717",
		lambda e: _each_kst1f(
			e,
			lambda kst1f: (
				kst1f.any_of("E8241717")
				and kst1f.any_of(*fields(EINLAGEKONTO_OPENING))
				and _set_off(kst1f)
				and kst1f.value("E8241717") != kst1f.total(EINLAGEKONTO_OPENING)
			),
		),
	),
	Condition(
		"8920013",
		"E8241717",
		lambda e: _each_kst1f(
			e,
			lambda kst1f: (
				not kst1f.any_of("E8241717")
				and kst1f.any_of(*fields(EINLAGEKONTO_OPENING))
				and _set_off(kst1f)
			),
		),
	),
	Condition(
		"8920019",
		"E8241717",
		lambda e: _each_kst1f(
			e,
			lambda kst1f: (
				kst1f.any_of("E8241717")
				and (
					kst1f.total(EINLAGEKONTO_OPENING) <= ZERO
					or (kst1f.any_of("E8240302") and _excess(kst1f) <= ZERO)
					or not kst1f.any_of("E8240302", "E8240401", "E8240303", "E8242205")
				)
			),
		),
	),
	Condition(
		"8924077",
		"E8240302",
		lambda e: _each_kst1f(
			e,
			lambda kst1f: (
				kst1f.all_of("E8240302", "E8200502")
				and not kst1f.any_of("E8240303", "E8242205")
				and kst1f.value("E8240302") != kst1f.value("E8200502")
			),
		),
	),
	Condition(
		"8924079",
		"E8240401",
		lambda e: _each_kst1f(
			e,
			lambda kst1f: (
				kst1f.all_of("E8240401", "E8201301", "E8240302")
				and kst1f.value("E8240401") != kst1f.value("E8201301")
			),
		),
	),
	Condition(
		"8924401",
		"E8240501",
		lambda e: _each_kst1f(
			e,
			lambda kst1f: (
				kst1f.any_of("E8240501")
				and kst1f.any_of("E8240302", "E8240401")
				and kst1f.value("E8240501") != _excess(kst1f)
			),
		),
	),
	Condition(
		"8920076",
		"E8242201",
		lambda e: _each_kst1f(
			e,
			lambda kst1f: (
				kst1f.all_of("E8242201", "E8240501")
				and not kst1f.any_of("E8122011")
				and kst1f.value("E8242201")
				!= max(min(kst1f.value("E8241717"), kst1f.value("E8240501"), kst1f.value("E8122003")), ZERO)
			),
		),
	),
)
"""The reading of each Prüfbedingung, in the order of the catalogue."""

RULES: tuple[Rule, ...] = rules(CONDITIONS, _year)
"""The rules of the sheets „<Vordruck> - Regeln“ that the simulation checks beyond the structure."""

CHECKS = erklaerung.checks(TITLE, MAIN_FORM, RULES)
