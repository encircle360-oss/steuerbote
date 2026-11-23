"""The balance sheet of § 266 HGB and the income statement of § 275 HGB, each position with its concept of the HGB
taxonomy.

The balance sheet holds every position of § 266 Abs. 2 and 3 HGB in its order, with the letters, roman and
arabic numerals of the law, and three kinds of positions the law adds elsewhere:

- the separate items „Ausleihungen, Forderungen und Verbindlichkeiten gegenüber Gesellschaftern“ of a GmbH, which
  „sind in der Regel als solche jeweils gesondert auszuweisen“ (§ 42 Abs. 3 GmbHG), after the last arabic item of
  their group and without a numeral of their own;
- the „Bilanzgewinn/Bilanzverlust“, which takes the place of „Jahresüberschuß/Jahresfehlbetrag“ and
  „Gewinnvortrag/Verlustvortrag“ when the balance sheet is drawn up after part of the result has been
  appropriated (§ 268 Abs. 1 Satz 2 HGB);
- the „Nicht durch Eigenkapital gedeckter Fehlbetrag“ at the end of the Aktiva (§ 268 Abs. 3 HGB), and the same
  amount within the Eigenkapital, which it brings to zero.

Each position names its concept of the HGB taxonomy 6.9 (de-gaap-ci-2025-04-01 of the package
german-gaap-taxonomy-v6.9-2025-04-01-xbrl.zip, read on 23 November 2026), without the prefix de-gaap-ci_, as the
Balance Sheet Mapping names them. The concept of a position is an ancestor of the concepts of the positions under
it, so the balances of the books add up to a position through the calculation linkbase of the taxonomy
(steuerbote.hgb.statement). The statement computes the totals, the Jahresüberschuss/Jahresfehlbetrag from the
income statement and the Fehlbetrag; no balance lands on them (``computed``).

How much of the balance sheet a class shows is § 266 Abs. 1 HGB (LEVELS): „Kleinstkapitalgesellschaften (§ 267a)
brauchen nur eine verkürzte Bilanz aufzustellen, in die nur die in den Absätzen 2 und 3 mit Buchstaben
bezeichneten Posten gesondert und in der vorgeschriebenen Reihenfolge aufgenommen werden“ (Satz 4), klein the
positions „mit Buchstaben und römischen Zahlen“ (Satz 3), mittelgroß and groß every position (Satz 2). The
Fehlbetrag stands with the letters, the Bilanzgewinn and the Fehlbetrag within the Eigenkapital with the roman
numerals, the separate items of § 42 Abs. 3 GmbHG with the arabic ones.

A fiscal year names its schemes by the year it ends in, as steuerbote.hgb.size names its thresholds: both tables
hold the same years. Text of § 266 HGB and § 42 GmbHG as read on gesetze-im-internet.de on 23 November 2026.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from steuerbote.hgb.size import SizeClass, UnknownYearError


class SchemeError(LookupError):
	"""The scheme has no such position."""


class Direction(Enum):
	"""The side of the books on which a position is positive: assets and expenses debit, the rest credit."""

	DEBIT = "Soll"
	CREDIT = "Haben"


class Level(Enum):
	TOTAL = "Summe"
	LETTER = "Buchstabe"
	ROMAN = "römische Zahl"
	ARABIC = "arabische Zahl"
	LOWER = "Kleinbuchstabe"


@dataclass(frozen=True, slots=True)
class Position:
	"""A position of a scheme: its marker as printed (such as „A.“, „II.“, „3.“ or none), the wording of the law,
	its concept and level, the side it is positive on and its source."""

	marker: str
	label: str
	concept: str
	level: Level
	direction: Direction
	reference: str
	children: tuple[Position, ...] = ()
	computed: bool = False

	def walk(self) -> Iterator[Position]:
		"""This position and every position under it, in the order of the scheme."""
		yield self
		for child in self.children:
			yield from child.walk()


@dataclass(frozen=True, slots=True)
class Form:
	"""The levels of the balance sheet a class shows, with the sentence of § 266 Abs. 1 HGB that sets them."""

	levels: frozenset[Level]
	reference: str


_EVERY_LEVEL = frozenset({Level.LETTER, Level.ROMAN, Level.ARABIC})
LEVELS: MappingProxyType[SizeClass, Form] = MappingProxyType(
	{
		SizeClass.KLEINST: Form(frozenset({Level.LETTER}), "§ 266 Abs. 1 Satz 4 HGB"),
		SizeClass.KLEIN: Form(frozenset({Level.LETTER, Level.ROMAN}), "§ 266 Abs. 1 Satz 3 HGB"),
		SizeClass.MITTELGROSS: Form(_EVERY_LEVEL, "§ 266 Abs. 1 Satz 2 HGB"),
		SizeClass.GROSS: Form(_EVERY_LEVEL, "§ 266 Abs. 1 Satz 2 HGB"),
	}
)


@dataclass(frozen=True, slots=True)
class BalanceSheetScheme:
	year: int
	taxonomy: str
	aktiva: Position
	passiva: Position
	_index: Mapping[str, Position] = field(init=False, repr=False, compare=False)
	_parents: Mapping[str, Position] = field(init=False, repr=False, compare=False)

	def __post_init__(self) -> None:
		index: dict[str, Position] = {}
		parents: dict[str, Position] = {}
		for root in (self.aktiva, self.passiva):
			for position in root.walk():
				index[position.concept] = position
				parents.update((child.concept, position) for child in position.children)
		object.__setattr__(self, "_index", MappingProxyType(index))
		object.__setattr__(self, "_parents", MappingProxyType(parents))

	def positions(self) -> Iterator[Position]:
		"""Every position of the Aktiva, then of the Passiva, each side from its total down."""
		yield from self.aktiva.walk()
		yield from self.passiva.walk()

	def has(self, concept: str) -> bool:
		return concept in self._index

	def position(self, concept: str) -> Position:
		try:
			return self._index[concept]
		except KeyError:
			raise SchemeError(f"the balance sheet of {self.year} has no position {concept}") from None

	def parent(self, concept: str) -> Position | None:
		"""The position the one of ``concept`` lies under, None for the total of a side."""
		self.position(concept)
		return self._parents.get(concept)

	def shows(self, concept: str, size_class: SizeClass) -> bool:
		"""Whether the balance sheet of ``size_class`` shows the position as a line of its own."""
		return self.position(concept).level in LEVELS[size_class].levels

	def visible(self, size_class: SizeClass) -> tuple[Position, ...]:
		"""The positions the balance sheet of ``size_class`` shows, in their order, without the totals."""
		return tuple(position for position in self.positions() if position.level in LEVELS[size_class].levels)


_ROMAN = frozenset({"I", "II", "III", "IV", "V"})


def _item(
	paragraph: int,
	path: str,
	label: str,
	concept: str,
	direction: Direction,
	*children: Position,
	**flags: bool,
) -> Position:
	"""A position of § 266 Abs. 2 or 3 HGB; ``path`` such as „A.I.3“ or „C.8“ gives its marker, level and
	reference."""
	parts = path.split(".")
	last = parts[-1]
	level = Level.ARABIC if last.isdigit() else Level.ROMAN if last in _ROMAN else Level.LETTER
	return Position(
		f"{last}.",
		label,
		concept,
		level,
		direction,
		f"§ 266 Abs. {paragraph} {' '.join(f'{part}.' for part in parts)} HGB",
		children,
		**flags,
	)


def _asset(path: str, label: str, concept: str, *children: Position) -> Position:
	return _item(2, path, label, concept, Direction.DEBIT, *children)


def _claim(path: str, label: str, concept: str, *children: Position, computed: bool = False) -> Position:
	"""A position of the Passiva: Eigenkapital, Rückstellungen, Verbindlichkeiten and the rest."""
	return _item(3, path, label, concept, Direction.CREDIT, *children, computed=computed)


def _shareholder_item(label: str, concept: str, direction: Direction) -> Position:
	return Position("", label, concept, Level.ARABIC, direction, "§ 42 Abs. 3 GmbHG")


_AKTIVA_2026 = Position(
	"",
	"Summe Aktiva",
	"bs.ass",
	Level.TOTAL,
	Direction.DEBIT,
	"§ 266 Abs. 2 HGB",
	(
		_asset(
			"A",
			"Anlagevermögen",
			"bs.ass.fixAss",
			_asset(
				"A.I",
				"Immaterielle Vermögensgegenstände",
				"bs.ass.fixAss.intan",
				_asset(
					"A.I.1",
					"Selbst geschaffene gewerbliche Schutzrechte und ähnliche Rechte und Werte",
					"bs.ass.fixAss.intan.selfmade",
				),
				_asset(
					"A.I.2",
					"entgeltlich erworbene Konzessionen, gewerbliche Schutzrechte und ähnliche Rechte und Werte sowie "
					"Lizenzen an solchen Rechten und Werten",
					"bs.ass.fixAss.intan.concessionBrands",
				),
				_asset("A.I.3", "Geschäfts- oder Firmenwert", "bs.ass.fixAss.intan.goodwill"),
				_asset("A.I.4", "geleistete Anzahlungen", "bs.ass.fixAss.intan.advPaym"),
			),
			_asset(
				"A.II",
				"Sachanlagen",
				"bs.ass.fixAss.tan",
				_asset(
					"A.II.1",
					"Grundstücke, grundstücksgleiche Rechte und Bauten einschließlich der Bauten auf fremden "
					"Grundstücken",
					"bs.ass.fixAss.tan.landBuildings",
				),
				_asset("A.II.2", "technische Anlagen und Maschinen", "bs.ass.fixAss.tan.machinery"),
				_asset(
					"A.II.3",
					"andere Anlagen, Betriebs- und Geschäftsausstattung",
					"bs.ass.fixAss.tan.otherEquipm",
				),
				_asset(
					"A.II.4", "geleistete Anzahlungen und Anlagen im Bau", "bs.ass.fixAss.tan.inConstrAdvPaym"
				),
			),
			_asset(
				"A.III",
				"Finanzanlagen",
				"bs.ass.fixAss.fin",
				_asset("A.III.1", "Anteile an verbundenen Unternehmen", "bs.ass.fixAss.fin.sharesInAffil"),
				_asset("A.III.2", "Ausleihungen an verbundene Unternehmen", "bs.ass.fixAss.fin.loansToAffil"),
				_asset("A.III.3", "Beteiligungen", "bs.ass.fixAss.fin.particip"),
				_asset(
					"A.III.4",
					"Ausleihungen an Unternehmen, mit denen ein Beteiligungsverhältnis besteht",
					"bs.ass.fixAss.fin.loansToParticip",
				),
				_asset("A.III.5", "Wertpapiere des Anlagevermögens", "bs.ass.fixAss.fin.securities"),
				_asset("A.III.6", "sonstige Ausleihungen", "bs.ass.fixAss.fin.otherLoans"),
				_shareholder_item(
					"Ausleihungen an Gesellschafter", "bs.ass.fixAss.fin.loansToSharehold", Direction.DEBIT
				),
			),
		),
		_asset(
			"B",
			"Umlaufvermögen",
			"bs.ass.currAss",
			_asset(
				"B.I",
				"Vorräte",
				"bs.ass.currAss.inventory",
				_asset("B.I.1", "Roh-, Hilfs- und Betriebsstoffe", "bs.ass.currAss.inventory.material"),
				_asset(
					"B.I.2",
					"unfertige Erzeugnisse, unfertige Leistungen",
					"bs.ass.currAss.inventory.inProgress",
				),
				_asset("B.I.3", "fertige Erzeugnisse und Waren", "bs.ass.currAss.inventory.finishedAndMerch"),
				_asset("B.I.4", "geleistete Anzahlungen", "bs.ass.currAss.inventory.advPaymPaid"),
			),
			_asset(
				"B.II",
				"Forderungen und sonstige Vermögensgegenstände",
				"bs.ass.currAss.receiv",
				_asset("B.II.1", "Forderungen aus Lieferungen und Leistungen", "bs.ass.currAss.receiv.trade"),
				_asset("B.II.2", "Forderungen gegen verbundene Unternehmen", "bs.ass.currAss.receiv.affil"),
				_asset(
					"B.II.3",
					"Forderungen gegen Unternehmen, mit denen ein Beteiligungsverhältnis besteht",
					"bs.ass.currAss.receiv.particip",
				),
				_asset("B.II.4", "sonstige Vermögensgegenstände", "bs.ass.currAss.receiv.other"),
				_shareholder_item(
					"Forderungen gegen Gesellschafter", "bs.ass.currAss.receiv.shareholders", Direction.DEBIT
				),
			),
			_asset(
				"B.III",
				"Wertpapiere",
				"bs.ass.currAss.securities",
				_asset("B.III.1", "Anteile an verbundenen Unternehmen", "bs.ass.currAss.securities.affil"),
				_asset("B.III.2", "sonstige Wertpapiere", "bs.ass.currAss.securities.other"),
			),
			_asset(
				"B.IV",
				"Kassenbestand, Bundesbankguthaben, Guthaben bei Kreditinstituten und Schecks",
				"bs.ass.currAss.cashEquiv",
			),
		),
		_asset("C", "Rechnungsabgrenzungsposten", "bs.ass.prepaidExp"),
		_asset("D", "Aktive latente Steuern", "bs.ass.defTax"),
		_asset(
			"E", "Aktiver Unterschiedsbetrag aus der Vermögensverrechnung", "bs.ass.SurplusFromOffsetting"
		),
		Position(
			"",
			"Nicht durch Eigenkapital gedeckter Fehlbetrag",
			"bs.ass.deficitNotCoveredByCapital",
			Level.LETTER,
			Direction.DEBIT,
			"§ 268 Abs. 3 HGB",
			computed=True,
		),
	),
	computed=True,
)

_PASSIVA_2026 = Position(
	"",
	"Summe Passiva",
	"bs.eqLiab",
	Level.TOTAL,
	Direction.CREDIT,
	"§ 266 Abs. 3 HGB",
	(
		_claim(
			"A",
			"Eigenkapital",
			"bs.eqLiab.equity",
			_claim("A.I", "Gezeichnetes Kapital", "bs.eqLiab.equity.subscribed"),
			_claim("A.II", "Kapitalrücklage", "bs.eqLiab.equity.capRes"),
			_claim(
				"A.III",
				"Gewinnrücklagen",
				"bs.eqLiab.equity.revenueRes",
				_claim("A.III.1", "gesetzliche Rücklage", "bs.eqLiab.equity.revenueRes.legal"),
				_claim(
					"A.III.2",
					"Rücklage für Anteile an einem herrschenden oder mehrheitlich beteiligten Unternehmen",
					"bs.eqLiab.equity.revenueRes.sharesParentComp",
				),
				_claim("A.III.3", "satzungsmäßige Rücklagen", "bs.eqLiab.equity.revenueRes.statutory"),
				_claim("A.III.4", "andere Gewinnrücklagen", "bs.eqLiab.equity.revenueRes.other"),
			),
			_claim("A.IV", "Gewinnvortrag/Verlustvortrag", "bs.eqLiab.equity.retainedEarnings"),
			_claim("A.V", "Jahresüberschuss/Jahresfehlbetrag", "bs.eqLiab.equity.netIncome", computed=True),
			Position(
				"IV.",
				"Bilanzgewinn/Bilanzverlust",
				"bs.eqLiab.equity.profitLoss",
				Level.ROMAN,
				Direction.CREDIT,
				"§ 268 Abs. 1 Satz 2 HGB",
			),
			Position(
				"",
				"Nicht durch Eigenkapital gedeckter Fehlbetrag",
				"bs.eqLiab.equity.deficitNotCoveredByCapital",
				Level.ROMAN,
				Direction.CREDIT,
				"§ 268 Abs. 3 HGB",
				computed=True,
			),
		),
		_claim(
			"B",
			"Rückstellungen",
			"bs.eqLiab.accruals",
			_claim(
				"B.1",
				"Rückstellungen für Pensionen und ähnliche Verpflichtungen",
				"bs.eqLiab.accruals.pensions",
			),
			_claim("B.2", "Steuerrückstellungen", "bs.eqLiab.accruals.tax"),
			_claim("B.3", "sonstige Rückstellungen", "bs.eqLiab.accruals.other"),
		),
		_claim(
			"C",
			"Verbindlichkeiten",
			"bs.eqLiab.liab",
			_claim("C.1", "Anleihen", "bs.eqLiab.liab.securities"),
			_claim("C.2", "Verbindlichkeiten gegenüber Kreditinstituten", "bs.eqLiab.liab.bank"),
			_claim("C.3", "erhaltene Anzahlungen auf Bestellungen", "bs.eqLiab.liab.advPaym"),
			_claim("C.4", "Verbindlichkeiten aus Lieferungen und Leistungen", "bs.eqLiab.liab.trade"),
			_claim(
				"C.5",
				"Verbindlichkeiten aus der Annahme gezogener Wechsel und der Ausstellung eigener Wechsel",
				"bs.eqLiab.liab.notes",
			),
			_claim("C.6", "Verbindlichkeiten gegenüber verbundenen Unternehmen", "bs.eqLiab.liab.assocComp"),
			_claim(
				"C.7",
				"Verbindlichkeiten gegenüber Unternehmen, mit denen ein Beteiligungsverhältnis besteht",
				"bs.eqLiab.liab.particip",
			),
			_claim("C.8", "sonstige Verbindlichkeiten", "bs.eqLiab.liab.other"),
			_shareholder_item(
				"Verbindlichkeiten gegenüber Gesellschaftern", "bs.eqLiab.liab.shareholders", Direction.CREDIT
			),
		),
		_claim("D", "Rechnungsabgrenzungsposten", "bs.eqLiab.defIncome"),
		_claim("E", "Passive latente Steuern", "bs.eqLiab.defTax"),
	),
	computed=True,
)


BALANCE_SHEETS: MappingProxyType[int, BalanceSheetScheme] = MappingProxyType(
	{2026: BalanceSheetScheme(2026, "6.9", _AKTIVA_2026, _PASSIVA_2026)}
)


def balance_sheet_scheme(year: int) -> BalanceSheetScheme:
	"""The balance sheet of the fiscal year that ends in ``year``."""
	return _entry(BALANCE_SHEETS, year, "balance sheet")


def _entry[T](table: Mapping[int, T], year: int, what: str) -> T:
	if isinstance(year, bool) or not isinstance(year, int):
		raise TypeError(f"year must be an int, not {type(year).__name__}")
	try:
		return table[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in table)
		raise UnknownYearError(f"Steuerbote has no {what} for {year}; known years: {known}") from None
