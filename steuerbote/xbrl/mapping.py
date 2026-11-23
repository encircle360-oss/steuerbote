"""The Bilanzzuordnung of a company: which position of the HGB-Taxonomie each account of its books goes to.

The E-Bilanz (§ 5b EStG) and the Offenlegung of the Jahresabschluss (§§ 325, 326 HGB) read the same books through
the same mapping: the E-Bilanz reports the positions themselves, the Offenlegung sums them up to the scheme of § 266
HGB along the hierarchy of the taxonomy (steuerbote/hgb/statement.py). A Mapping belongs to one company, one chart of
accounts (SKR03, SKR04 or one of its own) and one version of the taxonomy whose positions it names, and is plain
data. Every account has one place in it:

- A Rule: the account goes to a position, named without the prefix of the GAAP module, as steuerbote/hgb and
  Taxonomy.parents() name them. A balance on the other side of the position goes to the position for the opposite
  balance, if the rule names one: a bank account „würde bei einem Saldo im „Soll“ auf der Aktivseite ... zugeordnet
  werden. Ist der Saldo jedoch im „Haben“ (d.h. das Konto wurde „überzogen“) so erfolgt der Ausweis auf der
  Passivseite unter den Verbindlichkeiten in der Position „Verbindlichkeiten gegenüber Kreditinstituten““
  (Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025, A.13).
- Each rule carries its Abschlusszweck, as the DATEV charts mark accounts „ausschließlich für die Handelsbilanz“ (HB)
  or „ausschließlich für die Steuerbilanz“ (SB) (DATEV SKR 03, Art.-Nr. 11174, and SKR 04, Art.-Nr. 11175, „Gültig
  für 2026“, Fußnote 4): a rule for both counts in every balance sheet, one for the Handelsbilanz or the Steuerbilanz
  only in that one (Rule.counts_for).
- Each rule carries the flags the Offenlegung notes below the positions: whether the balance is owed to or by the
  shareholders, „Ausleihungen, Forderungen und Verbindlichkeiten gegenüber Gesellschaftern sind in der Regel als
  solche jeweils gesondert auszuweisen oder im Anhang anzugeben“ (§ 42 Abs. 3 GmbHG), and its remaining term, „Der
  Betrag der Forderungen mit einer Restlaufzeit von mehr als einem Jahr ist bei jedem gesondert ausgewiesenen Posten
  zu vermerken“ and likewise the Verbindlichkeiten „mit einer Restlaufzeit bis zu einem Jahr“ and „von mehr als einem
  Jahr“ (§ 268 Abs. 4 Satz 1, Abs. 5 Satz 1 HGB). The terms are those of steuerbote.hgb.statement.RemainingTerm; the
  E-Bilanz reports no Restlaufzeiten.
- A Watched account: an account whose position is not decided. A balance on it holds the E-Bilanz and the
  Jahresabschluss back; at the level hint it only adds a hint, as in the VAT Return Mapping since v0.4.0
  (steuerbote/ustva/mapping.py).
- An Excluded account: an account outside the Bilanz and the GuV, with the reason, such as the Vortrags- and
  statistical accounts of class 9 of the DATEV charts.

An account in two places is refused, so that a balance never counts twice. Account numbers are compared as written,
like every account number of Steuerbote.

Errors are MappingError with an English template and its values, which the Frappe layer translates; MESSAGES lists
the templates. This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from steuerbote.hgb.statement import RemainingTerm
from steuerbote.ustva.mapping import WatchLevel, is_account_number
from steuerbote.xbrl.taxonomy import GAAP_PREFIX
from steuerbote.xbrl.versions import LATEST, TAXONOMIES

NOT_AN_ACCOUNT_NUMBER = "{0} is no account number: it is a text without blanks at either end."
NO_POSITION = "Account {0} has no position."
SAME_OPPOSITE = "Account {0}: the position for the opposite balance is its position itself."
NO_PURPOSE = "Account {0}: {1} is no Abschlusszweck; it is both, commercial or tax."
NO_REMAINING_TERM = "Account {0}: {1} is no remaining term."
NO_FLAG = "Account {0}: whether the balance is owed to or by the shareholders is yes or no, not {1}."
NO_LEVEL = "Account {0}: the level of a watched account is blocking or hint, not {1}."
NO_REASON = "Account {0} lies outside the Bilanz and the GuV, but the mapping does not say why."
TWICE = "Account {0} has more than one row in the Balance Sheet Mapping."
UNKNOWN_VERSION = "Steuerbote knows no HGB-Taxonomie {0}."
MESSAGES = (
	NOT_AN_ACCOUNT_NUMBER,
	NO_POSITION,
	SAME_OPPOSITE,
	NO_PURPOSE,
	NO_REMAINING_TERM,
	NO_FLAG,
	NO_LEVEL,
	NO_REASON,
	TWICE,
	UNKNOWN_VERSION,
)

REMAINING_TERMS: MappingProxyType[str, RemainingTerm] = MappingProxyType(
	{
		"up to one year": RemainingTerm.UP_TO_ONE_YEAR,
		"one to five years": RemainingTerm.ONE_TO_FIVE_YEARS,
		"over five years": RemainingTerm.OVER_FIVE_YEARS,
	}
)
"""The remaining terms by the values a row of the mapping holds them under."""
_TERM_VALUES = MappingProxyType({term: value for value, term in REMAINING_TERMS.items()})


class MappingError(ValueError):
	"""Rows the mapping cannot hold; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


class Purpose(StrEnum):
	"""The Abschlusszweck of a rule: which balance sheets the account is booked for (DATEV, Fußnote 4)."""

	BOTH = "both"
	COMMERCIAL = "commercial"
	"""HB: the Handelsbilanz only."""
	TAX = "tax"
	"""SB: the Steuerbilanz only."""


@dataclass(frozen=True, slots=True)
class Rule:
	"""An account that goes to a position, with the position for a balance on the other side, its Abschlusszweck
	and the flags of the Offenlegung."""

	account_number: str
	concept: str
	opposite: str | None = None
	purpose: Purpose = Purpose.BOTH
	shareholder: bool = False
	remaining_term: RemainingTerm | None = None

	def __post_init__(self) -> None:
		number = _require_number(self.account_number)
		concept = _concept_name(self.concept)
		if not concept:
			raise MappingError(NO_POSITION, number)
		opposite = _concept_name(self.opposite) or None
		if opposite == concept:
			raise MappingError(SAME_OPPOSITE, number)
		object.__setattr__(self, "concept", concept)
		object.__setattr__(self, "opposite", opposite)
		try:
			object.__setattr__(self, "purpose", Purpose(self.purpose))
		except ValueError:
			raise MappingError(NO_PURPOSE, number, self.purpose) from None
		if not isinstance(self.shareholder, bool):
			raise MappingError(NO_FLAG, number, self.shareholder)
		term = self.remaining_term
		if term is not None and not isinstance(term, RemainingTerm):
			if term not in REMAINING_TERMS:
				raise MappingError(NO_REMAINING_TERM, number, term)
			object.__setattr__(self, "remaining_term", REMAINING_TERMS[term])

	@property
	def term_value(self) -> str | None:
		"""The remaining term as a row of the mapping holds it."""
		return None if self.remaining_term is None else _TERM_VALUES[self.remaining_term]

	def counts_for(self, purpose: Purpose) -> bool:
		"""Whether the balance counts in a balance sheet of the purpose: a rule for both in every one, a rule for the
		Handelsbilanz or the Steuerbilanz in that one alone. The Einheitsbilanz, „deutsches Handelsrecht (sog.
		Einheitsbilanz)“, which the tax administration treats as a Steuerbilanz (Leitfaden B.13), is a balance sheet for
		both, so only the rules for both count in it."""
		return self.purpose is Purpose.BOTH or self.purpose is purpose


@dataclass(frozen=True, slots=True)
class Watched:
	"""An account whose position is not decided: a balance on it holds the documents back, or at the level hint only
	adds a hint."""

	account_number: str
	level: WatchLevel = WatchLevel.BLOCKING

	def __post_init__(self) -> None:
		number = _require_number(self.account_number)
		try:
			object.__setattr__(self, "level", WatchLevel(self.level))
		except ValueError:
			raise MappingError(NO_LEVEL, number, self.level) from None


@dataclass(frozen=True, slots=True)
class Excluded:
	"""An account outside the Bilanz and the GuV, with the reason on one line."""

	account_number: str
	reason: str

	def __post_init__(self) -> None:
		number = _require_number(self.account_number)
		reason = " ".join(str(self.reason or "").split())
		if not reason:
			raise MappingError(NO_REASON, number)
		object.__setattr__(self, "reason", reason)


type Place = Rule | Watched | Excluded


@dataclass(frozen=True, slots=True)
class Mapping:
	"""The Bilanzzuordnung of a company: its chart, the version of the taxonomy its positions belong to, and the place
	of each account."""

	chart: str
	rules: tuple[Rule, ...] = ()
	watched: tuple[Watched, ...] = ()
	excluded: tuple[Excluded, ...] = ()
	taxonomy_version: str = LATEST.version
	_by_number: MappingProxyType[str, Place] = field(init=False, repr=False, compare=False)

	def __post_init__(self) -> None:
		if self.taxonomy_version not in TAXONOMIES:
			raise MappingError(UNKNOWN_VERSION, self.taxonomy_version)
		object.__setattr__(self, "rules", tuple(self.rules))
		object.__setattr__(self, "watched", tuple(self.watched))
		object.__setattr__(self, "excluded", tuple(self.excluded))
		places: dict[str, Place] = {}
		for place in self._places():
			if place.account_number in places:
				raise MappingError(TWICE, place.account_number)
			places[place.account_number] = place
		object.__setattr__(self, "_by_number", MappingProxyType(places))

	def _places(self) -> Iterable[Place]:
		yield from self.rules
		yield from self.watched
		yield from self.excluded

	@property
	def numbers(self) -> frozenset[str]:
		"""Every account the mapping gives a place."""
		return frozenset(self._by_number)

	def place_of(self, account_number: str) -> Place | None:
		"""The rule, the watched entry or the exclusion of an account; None for an account without a place."""
		return self._by_number.get(account_number)


def _require_number(value: object) -> str:
	if not is_account_number(value):
		raise MappingError(NOT_AN_ACCOUNT_NUMBER, value)
	return value


def _concept_name(value: object) -> str:
	"""A position without blanks and without the prefix of the GAAP module."""
	return str(value or "").strip().removeprefix(f"{GAAP_PREFIX}:")
