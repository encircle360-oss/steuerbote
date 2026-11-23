"""The facts of an XBRL report, independent of the XML that writes them.

A report names its company (Entity), the periods of its fiscal year (Periods) and the entry points it references,
and holds facts: items, each a value of a concept for a period, and tuples, which group items and tuples. The E-Bilanz
and the Offenlegung build their reports from these alone; steuerbote/xbrl/writer.py writes them for the taxonomies of
the generation 6, which has tuples. The taxonomy 7.0 drops them, so it needs only a writer of its own: its preview on
esteuer.de (Previewfassung_Modernisierung_Taxonomie.zip, June 2026) declares no tuple in de-gcd-2026-05-22.xsd or
de-gaap-ci-2026-05-22.xsd.

Periods. „Stichtagsbezogene Positionen müssen im Datensatz stichtagsbezogenen Kontexten zugordnet sein ...
Entsprechend müssen periodenbezogene Positionen periodenbezogenen Kontexten zugeordnet sein“ (Technischer Leitfaden zur
HGB-Taxonomie 6.9, Stand 10.06.2025, B.8): an item refers to the Bilanzstichtag (STICHTAG) or to the fiscal year
(WIRTSCHAFTSJAHR), and where a Handelsbilanz shows the previous year to its Bilanzstichtag or its fiscal year
(VORJAHR_STICHTAG, VORJAHR; B.8.3). The Bilanzstichtag is the end of the fiscal year unless the report says otherwise,
as an Eröffnungsbilanz does: the example SteuerbilanzAutoverkaeufer-Eroeffnung_PersG.xml of the ERiC documentation
44.3.6.0 has the stichtag 20250101 in a fiscal year from 01.01.2025 to 31.12.2025.

Entity. The E-Bilanz names the company by its Steuernummer in the 13-digit format of ELSTER in the scheme
http://www.rzf-nrw.de/Steuernummer, as every context of the examples of the ERiC documentation does („Die entity-Einträge
in den Kontexten sind daraufhin zu prüfen, ob sie im gesamten Datensatz mit nur einem einheitlichen Wert belegt
sind“, Leitfaden B.14.7). Which identifier the Unternehmensregister expects is unverified; the report takes any scheme.

Items. The value of an item is a Decimal for an amount, never a float (AGENTS.md), an int or a Decimal for another
number, a bool, a date, or a text, which also writes a QName such as de-gaap-ci:bs.ass. None is NIL: „Nicht aus der
Buchführung mit Werten zu belegende Mussfelder ... müssen im Datensatz „leer“ (technisch mit „NIL“) übermittelt werden“
(B.14.2.3). An item of a table names a member for each of its dimensions, which are scenario dimensions (A.14.2.1);
decimals are given for a number that is no amount, and the report gives those of its amounts, two by default: „Die
monetären Wertangaben müssen auf zwei Nachkommastellen genau angegeben sein“ (B.7).

Tuples. „Eine Position mit Auswahlwerten ist eine Datenstruktur (technisch: Tupel), welche die Auswahlwerte als in der
Datenstruktur geschachtelte Felder enthält“ (A.8); its values are empty strings, and NIL where a Mussfeld is not
reported (B.14.1): choice(). A tuple without content is NIL, a tuple with content is not.

Concepts are named with the prefix of their module, such as de-gaap-ci:bs.ass. This module is pure Python and never
imports Frappe.
"""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

STEUERNUMMER = "http://www.rzf-nrw.de/Steuernummer"
"""The scheme of the entity of the E-Bilanz, with the Steuernummer in the 13-digit format of ELSTER."""
_ST13 = re.compile(r"[0-9]{13}")

type Value = Decimal | int | bool | date | str | None


class Period(StrEnum):
	"""What an item refers to: a day or the fiscal year, of the report or of its previous year (Leitfaden B.8)."""

	STICHTAG = "stichtag"
	WIRTSCHAFTSJAHR = "wirtschaftsjahr"
	VORJAHR_STICHTAG = "vorjahr-stichtag"
	VORJAHR = "vorjahr"

	@property
	def instant(self) -> bool:
		return self in (Period.STICHTAG, Period.VORJAHR_STICHTAG)

	@property
	def prior(self) -> bool:
		return self in (Period.VORJAHR_STICHTAG, Period.VORJAHR)


@dataclass(frozen=True, slots=True)
class Periods:
	"""The fiscal year of a report and its Bilanzstichtag, and the previous fiscal year where the report shows it."""

	fiscal_year_begin: date
	fiscal_year_end: date
	balance_sheet_date: date | None = None
	"""The Bilanzstichtag, by default the end of the fiscal year."""
	prior_fiscal_year_begin: date | None = None
	prior_fiscal_year_end: date | None = None

	def __post_init__(self) -> None:
		if self.fiscal_year_end < self.fiscal_year_begin:
			raise ValueError("a fiscal year ends after it begins")
		if self.balance_sheet_date is None:
			object.__setattr__(self, "balance_sheet_date", self.fiscal_year_end)
		begin, end = self.prior_fiscal_year_begin, self.prior_fiscal_year_end
		if (begin is None) != (end is None):
			raise ValueError("the previous fiscal year needs both its first and its last day")
		if begin is None or end is None:
			return
		if end < begin:
			raise ValueError("the previous fiscal year ends after it begins")
		if end >= self.fiscal_year_begin:
			raise ValueError("the previous fiscal year ends before the fiscal year begins")

	@property
	def prior_balance_sheet_date(self) -> date | None:
		"""The Bilanzstichtag of the previous year, the end of its fiscal year."""
		return self.prior_fiscal_year_end

	def dates(self, period: Period) -> tuple[date | None, date]:
		"""The first and the last day of a period, None as the first of an instant."""
		match period:
			case Period.STICHTAG:
				return None, self.balance_sheet_date or self.fiscal_year_end
			case Period.WIRTSCHAFTSJAHR:
				return self.fiscal_year_begin, self.fiscal_year_end
		if self.prior_fiscal_year_begin is None or self.prior_fiscal_year_end is None:
			raise ValueError(f"the report has no Vorjahr for the period {period.value}")
		if period is Period.VORJAHR_STICHTAG:
			return None, self.prior_fiscal_year_end
		return self.prior_fiscal_year_begin, self.prior_fiscal_year_end


@dataclass(frozen=True, slots=True)
class Entity:
	"""The company a report is about, as the identifier of every context names it."""

	scheme: str
	identifier: str

	def __post_init__(self) -> None:
		if not self.scheme.strip() or not self.identifier.strip():
			raise ValueError("an entity has a scheme and an identifier")

	@classmethod
	def steuernummer(cls, st13: str) -> Entity:
		"""The company of an E-Bilanz by its Steuernummer in the 13-digit format of ELSTER."""
		if not _ST13.fullmatch(st13):
			raise ValueError(f"{st13} is no Steuernummer of 13 digits in the format of ELSTER")
		return cls(STEUERNUMMER, st13)


@dataclass(frozen=True, slots=True)
class Item:
	"""A value of a concept for a period, None for NIL, with a member for each dimension of a table."""

	concept: str
	period: Period
	value: Value = None
	dimensions: tuple[tuple[str, str], ...] = ()
	"""Each dimension with its member, in the order of the names of the dimensions."""
	decimals: int | None = None
	"""How many decimals a number that is no amount is exact to; amounts take those of the report."""

	def __post_init__(self) -> None:
		_require_prefix(self.concept)
		if isinstance(self.value, float) or not isinstance(
			self.value, Decimal | int | date | str | type(None)
		):
			raise TypeError(f"{self.concept} takes no {type(self.value).__name__} as value")
		if self.decimals is not None and (
			isinstance(self.decimals, bool) or not isinstance(self.decimals, int)
		):
			raise TypeError(f"the decimals of {self.concept} are a whole number")
		dimensions = tuple(sorted(self.dimensions))
		for dimension, member in dimensions:
			_require_prefix(dimension)
			_require_prefix(member)
		names = [dimension for dimension, _ in dimensions]
		repeated = sorted({name for name in names if names.count(name) > 1})
		if repeated:
			raise ValueError(f"{self.concept} names more than one member of {', '.join(repeated)}")
		object.__setattr__(self, "dimensions", dimensions)

	@property
	def nil(self) -> bool:
		return self.value is None

	def dimension(self, name: str) -> str | None:
		"""The member of a dimension, None for a dimension the item does not name."""
		return next((member for dimension, member in self.dimensions if dimension == name), None)


@dataclass(frozen=True, slots=True)
class Tuple:
	"""Items and tuples that belong together, or NIL without any."""

	concept: str
	children: tuple[Item | Tuple, ...] = ()
	nil: bool = False

	def __post_init__(self) -> None:
		_require_prefix(self.concept)
		object.__setattr__(self, "children", tuple(self.children))
		if any(not isinstance(child, Item | Tuple) for child in self.children):
			raise TypeError(f"the tuple {self.concept} holds items and tuples only")
		if self.nil and self.children:
			raise ValueError(f"the tuple {self.concept} is NIL, so it holds nothing")


type Fact = Item | Tuple


@dataclass(frozen=True, slots=True)
class Report:
	"""What an instance holds: the company, the periods, the entry points it references and the facts."""

	entity: Entity
	periods: Periods
	schema_refs: tuple[str, ...]
	"""The absolute URLs of the entry points (Leitfaden A.6)."""
	facts: tuple[Fact, ...]
	monetary_decimals: int = 2

	def __post_init__(self) -> None:
		object.__setattr__(self, "schema_refs", tuple(self.schema_refs))
		object.__setattr__(self, "facts", tuple(self.facts))
		if not self.schema_refs:
			raise ValueError("a report references at least one entry point")
		if any(not isinstance(fact, Item | Tuple) for fact in self.facts):
			raise TypeError("a report holds items and tuples only")

	def items(self) -> Iterator[tuple[Item, tuple[Tuple, ...]]]:
		"""Every item with the tuples around it, outermost first."""
		return _items(self.facts, ())

	def tuples(self) -> Iterator[tuple[Tuple, tuple[Tuple, ...]]]:
		"""Every tuple with the tuples around it, outermost first."""
		return _tuples(self.facts, ())

	def contexts(self) -> set[tuple[Period, tuple[tuple[str, str], ...]]]:
		"""The period and dimensions of every item, which the instance writes as its contexts."""
		return {(item.period, item.dimensions) for item, _ in self.items()}


def amount(concept: str, period: Period, value: Decimal, dimensions: Iterable[tuple[str, str]] = ()) -> Item:
	"""An item with an amount in euros and cents."""
	if not isinstance(value, Decimal):
		raise TypeError(f"the amount of {concept} is a Decimal, not {type(value).__name__}")
	return Item(concept, period, value, tuple(dimensions))


def nil(concept: str, period: Period, dimensions: Iterable[tuple[str, str]] = ()) -> Item:
	"""An item that is NIL."""
	return Item(concept, period, None, tuple(dimensions))


def choice(
	concept: str, *values: str, unreported: Iterable[str] = (), period: Period = Period.WIRTSCHAFTSJAHR
) -> Tuple:
	"""A position with Auswahlwerten: each value as an empty string, each unreported Mussfeld among them as NIL
	(Leitfaden B.14.1, A.10.1)."""
	return Tuple(
		concept,
		(
			*(Item(value, period, "") for value in values),
			*(Item(value, period, None) for value in unreported),
		),
	)


def _require_prefix(name: object) -> None:
	if not isinstance(name, str) or ":" not in name:
		raise ValueError(f"{name} is no name with the prefix of its module, such as de-gaap-ci:bs.ass")


def _items(facts: Iterable[Fact], around: tuple[Tuple, ...]) -> Iterator[tuple[Item, tuple[Tuple, ...]]]:
	for fact in facts:
		if isinstance(fact, Item):
			yield fact, around
		else:
			yield from _items(fact.children, (*around, fact))


def _tuples(facts: Iterable[Fact], around: tuple[Tuple, ...]) -> Iterator[tuple[Tuple, tuple[Tuple, ...]]]:
	for fact in facts:
		if isinstance(fact, Tuple):
			yield fact, around
			yield from _tuples(fact.children, (*around, fact))
