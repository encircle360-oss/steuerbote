"""The balance sheet and the income statement of a size class from the balances of the books.

Input. The Balance Sheet Mapping (steuerbote/xbrl/mapping.py and steuerbote/balances.py) delivers the books as
Balance rows: a concept of the HGB taxonomy, the balance as debit minus credit in euros and cents, and the flags
of its rule, whether the balance is owed to or by shareholders and its remaining term. Balance sheet accounts are
summed up to the Abschlussstichtag with the opening entries, P&L accounts within the fiscal year, and the Period
Closing Voucher of the fiscal year is left out. ``parents`` names for each concept the concept it adds up to, as
the calculation linkbase of the taxonomy has it (steuerbote/xbrl/taxonomy.py). Until both exist, any caller can
pass the rows and the hierarchy as plain values; the core needs nothing else.

Placement. A balance lands on the nearest position of the scheme at or above its concept. A „davon“ concept the
calculation linkbase leaves out, such as „Anleihen, davon konvertibel“, lands on the position of its Vermerk. A
balance without a position above it, and one on a position the statement computes, such as the Jahresüberschuss
or „sonstige Aktiva“ under the total of the Aktiva, is an error: the balance sheet would leave it out. So is a
balance a class shows only in a total while it shows the positions under it, such as one on „A. Eigenkapital“
itself in the balance sheet of klein, which shows „I.“ to „V.“: the positions would not add up to the total.

Signs. A line is positive on the side of its position: assets and expenses debit, equity, liabilities and income
credit (steuerbote.hgb.schemes.Direction). A balance on the other side counts negative, as a Verlustvortrag does
under „Gewinnvortrag/Verlustvortrag“. A position adds up the positions under it, and a result of the income
statement adds up the items above it, each with its sign.

Results. The income statement computes the Jahresüberschuss/Jahresfehlbetrag, and the balance sheet takes it as
„V. Jahresüberschuß/Jahresfehlbetrag“ (§ 266 Abs. 3 A. V. HGB): before the Period Closing Voucher no account of the
balance sheet holds the result of the year, so it comes from the income statement alone. Both sides of the
balance sheet then add up to the same total, or the books are not complete: the balance sheet of § 242 Abs. 1 HGB
sets the Vermögen against the Schulden and the Eigenkapital in Kontoform (§ 266 Abs. 1 Satz 1 HGB). The
Bilanzsumme of the size criteria „setzt sich aus den Posten zusammen, die in den Buchstaben A bis E des § 266
Absatz 2 aufgeführt sind“ (§ 267 Abs. 4a HGB), and the Umsatzerlöse are the first item of the income statement,
as § 277 Abs. 1 HGB defines them.

Fehlbetrag. „Ist das Eigenkapital durch Verluste aufgebraucht und ergibt sich ein Überschuß der Passivposten über
die Aktivposten, so ist dieser Betrag am Schluß der Bilanz auf der Aktivseite gesondert unter der Bezeichnung
„Nicht durch Eigenkapital gedeckter Fehlbetrag“ auszuweisen.“ (§ 268 Abs. 3 HGB) The same amount within the
Eigenkapital brings it to zero, so both sides rise by it; the Bilanzsumme of the size criteria leaves it out
(§ 267 Abs. 4a Satz 2 HGB). An Eigenkapital of zero is what the Bundesamt für Justiz asks a Kleinst to explain
(steuerbote.hgb.notes).

Vermerke. A Vermerk takes the balances under the position of its ``scope`` that its kind selects: the remaining
term of the rule for § 268 Abs. 4 and 5 HGB, the shareholder flag of the rule or a „davon“ concept for § 42
Abs. 3 GmbHG, a „davon“ concept for the rest (steuerbote.hgb.schemes). A balance without a remaining term where
the balance sheet of the class notes one is an error, since the Vermerk would be wrong. Where uncalled
contributions are offset, the position takes the name the law gives it: „der verbleibende Betrag ist als Posten
„Eingefordertes Kapital“ in der Hauptspalte der Passivseite auszuweisen“ (§ 272 Abs. 1 Satz 2 HGB).

Each line names the sources of the balances that landed on it, as the drill-down of the Annual Accounts shows
them. The schemes and their sources are steuerbote.hgb.schemes.
"""

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, StrEnum
from types import MappingProxyType

from steuerbote.hgb.schemes import (
	LEVELS,
	BalanceSheetScheme,
	Direction,
	IncomeStatementScheme,
	Method,
	Position,
	Vermerk,
	VermerkKind,
	balance_sheet_scheme,
	income_statement_scheme,
)
from steuerbote.hgb.size import SizeClass

ZERO = Decimal("0")
NO_PARENTS: Mapping[str, str] = MappingProxyType({})
NET_INCOME = "bs.eqLiab.equity.netIncome"
PROFIT_CARRIED_FORWARD = "bs.eqLiab.equity.retainedEarnings"
EQUITY = "bs.eqLiab.equity"
DEFICIT = "bs.ass.deficitNotCoveredByCapital"
DEFICIT_IN_EQUITY = "bs.eqLiab.equity.deficitNotCoveredByCapital"
CALLED_CAPITAL = "Eingefordertes Kapital"
_SCHEMES_REFERENCE = "§§ 266, 275 HGB"


class RemainingTerm(Enum):
	UP_TO_ONE_YEAR = "bis zu einem Jahr"
	ONE_TO_FIVE_YEARS = "mehr als ein Jahr bis zu fünf Jahren"
	OVER_FIVE_YEARS = "mehr als fünf Jahre"


_OVER_ONE_YEAR = frozenset({RemainingTerm.ONE_TO_FIVE_YEARS, RemainingTerm.OVER_FIVE_YEARS})
_REMAINING_TERM_KINDS = frozenset(
	{
		VermerkKind.RECEIVABLES_OVER_ONE_YEAR,
		VermerkKind.LIABILITIES_UP_TO_ONE_YEAR,
		VermerkKind.LIABILITIES_OVER_ONE_YEAR,
	}
)


@dataclass(frozen=True, slots=True)
class Balance:
	"""One balance of the books: a concept, debit minus credit, and the flags of its rule in the mapping."""

	concept: str
	amount: Decimal
	shareholder: bool = False
	remaining_term: RemainingTerm | None = None
	source: str = ""

	def __post_init__(self) -> None:
		if not isinstance(self.amount, Decimal):
			raise TypeError(f"amount must be Decimal, not {type(self.amount).__name__}")


class Severity(Enum):
	ERROR = "Fehler"
	HINT = "Hinweis"


class Code(StrEnum):
	UNPLACED = "JA-OHNE-POSTEN"
	COMPUTED = "JA-RECHENPOSTEN"
	NOT_BALANCED = "JA-BILANZ-UNGLEICH"
	UNITEMIZED = "JA-OHNE-UNTERPOSTEN"
	REMAINING_TERM_UNKNOWN = "JA-RESTLAUFZEIT-FEHLT"


@dataclass(frozen=True, slots=True)
class Finding:
	"""What holds the Jahresabschluss back (an error) or what someone should look at (a hint), as one German
	sentence with its source; ``concept`` and ``amount`` name the balance it is about."""

	code: Code
	severity: Severity
	text: str
	reference: str
	concept: str = ""
	amount: Decimal | None = None

	@property
	def blocking(self) -> bool:
		return self.severity is Severity.ERROR


@dataclass(frozen=True, slots=True)
class VermerkLine:
	vermerk: Vermerk
	amount: Decimal


@dataclass(frozen=True, slots=True)
class Line:
	"""A line of the balance sheet or the income statement: its position, its name, its amount in the direction of
	the position, its Vermerke and the sources of its balances."""

	position: Position
	label: str
	amount: Decimal
	vermerke: tuple[VermerkLine, ...] = ()
	sources: tuple[str, ...] = ()


def _line(lines: Iterable[Line], concept: str) -> Line:
	for line in lines:
		if line.position.concept == concept:
			return line
	raise KeyError(f"no line shows the position {concept}")


@dataclass(frozen=True, slots=True)
class IncomeStatement:
	"""The income statement: its lines, the Jahresüberschuss/Jahresfehlbetrag and the Umsatzerlöse."""

	scheme: IncomeStatementScheme
	lines: tuple[Line, ...]
	net_income: Decimal
	sales: Decimal

	def line(self, concept: str) -> Line:
		return _line(self.lines, concept)


@dataclass(frozen=True, slots=True)
class BalanceSheet:
	"""The balance sheet of a size class: the lines of each side, their totals, the Eigenkapital and the
	Bilanzsumme of § 267 Abs. 4a HGB."""

	scheme: BalanceSheetScheme
	size_class: SizeClass
	aktiva: tuple[Line, ...]
	passiva: tuple[Line, ...]
	aktiva_total: Decimal
	passiva_total: Decimal
	equity: Decimal
	deficit: Decimal
	bilanzsumme: Decimal

	@property
	def difference(self) -> Decimal:
		"""Aktiva less Passiva; anything but zero means the books are not complete."""
		return self.aktiva_total - self.passiva_total

	def line(self, concept: str) -> Line:
		return _line(self.aktiva + self.passiva, concept)


@dataclass(frozen=True, slots=True)
class AnnualStatement:
	"""The balance sheet and the income statement of one fiscal year, with what the books leave open."""

	balance_sheet: BalanceSheet
	income_statement: IncomeStatement
	findings: tuple[Finding, ...]


@dataclass(frozen=True, slots=True)
class _Placed:
	"""A balance on its position; ``chain`` holds its concept and those above it up to the position."""

	balance: Balance
	position: Position
	chain: tuple[str, ...]


class _Year:
	"""The amounts one fiscal year gives the positions and Vermerke of one scheme."""

	def __init__(
		self, scheme: BalanceSheetScheme | IncomeStatementScheme, fixed: Mapping[str, Decimal] | None = None
	) -> None:
		self.scheme = scheme
		self.fixed = dict(fixed or {})
		self.own: defaultdict[str, Decimal] = defaultdict(Decimal)
		self.sources: defaultdict[str, list[str]] = defaultdict(list)
		self.noted: defaultdict[tuple[str, VermerkKind], Decimal] = defaultdict(Decimal)
		self.without_term: defaultdict[tuple[str, VermerkKind], list[_Placed]] = defaultdict(list)
		self._amounts: dict[str, Decimal] = {}

	def add(self, placed: _Placed) -> None:
		position, balance = placed.position, placed.balance
		self.own[position.concept] += _signed(balance.amount, position.direction)
		if balance.source:
			self.sources[position.concept].append(balance.source)
		for holder in self._up_from(position):
			for vermerk in holder.vermerke:
				if not self._within(position, vermerk.scope):
					continue
				key = (holder.concept, vermerk.kind)
				if _selects(vermerk, placed):
					self.noted[key] += _signed(balance.amount, holder.direction)
				elif (
					vermerk.kind in _REMAINING_TERM_KINDS
					and balance.remaining_term is None
					and balance.amount
				):
					self.without_term[key].append(placed)

	def fix(self, concept: str, amount: Decimal) -> None:
		"""Set the amount of a computed position, which every amount computed before may have to take in."""
		self.fixed[concept] = amount
		self._amounts.clear()

	def amount(self, concept: str) -> Decimal:
		if concept not in self._amounts:
			self._amounts[concept] = self._compute(self.scheme.position(concept))
		return self._amounts[concept]

	def _compute(self, position: Position) -> Decimal:
		if position.concept in self.fixed:
			return self.fixed[position.concept]
		if position.terms:
			return sum(
				(self.amount(term) * _sign(self.scheme.position(term), position) for term in position.terms),
				ZERO,
			)
		children = sum(
			(self.amount(child.concept) * _sign(child, position) for child in position.children), ZERO
		)
		return self.own[position.concept] + children

	def line(self, position: Position, vermerke: tuple[Vermerk, ...]) -> Line:
		return Line(
			position,
			position.label,
			self.amount(position.concept),
			tuple(VermerkLine(vermerk, self.noted[(position.concept, vermerk.kind)]) for vermerk in vermerke),
			tuple(self.sources[position.concept]),
		)

	def _up_from(self, position: Position) -> Iterator[Position]:
		current: Position | None = position
		while current is not None:
			yield current
			current = self.scheme.parent(current.concept)

	def _within(self, position: Position, scope: str) -> bool:
		return any(holder.concept == scope for holder in self._up_from(position))


def build(
	year: int,
	size_class: SizeClass,
	balances: Iterable[Balance],
	*,
	parents: Mapping[str, str] = NO_PARENTS,
	method: Method = Method.GKV,
) -> AnnualStatement:
	"""The balance sheet and the income statement of ``size_class`` for the fiscal year that ends in ``year``.

	``balances`` holds the balances of the books, of the balance sheet and of the income statement alike, as the
	Balance Sheet Mapping delivers them; ``parents`` the hierarchy of their concepts.
	"""
	balance_scheme = balance_sheet_scheme(year)
	income_scheme = income_statement_scheme(year, method)
	findings: list[Finding] = []
	placed_balance: list[_Placed] = []
	placed_income: list[_Placed] = []
	for balance in balances:
		for scheme, placed in ((balance_scheme, placed_balance), (income_scheme, placed_income)):
			found = _place(balance, scheme, parents)
			if found is not None:
				if found.position.computed:
					findings.append(_computed(balance, found.position))
				else:
					placed.append(found)
				break
		else:
			findings.append(_unplaced(balance))
	income = _Year(income_scheme)
	for placed in placed_income:
		income.add(placed)
	net_income = income.amount(income_scheme.net_income.concept)
	income_lines = tuple(income.line(position, position.vermerke) for position in income_scheme.positions())
	income_statement = IncomeStatement(
		income_scheme, income_lines, net_income, income.amount(income_scheme.sales.concept)
	)
	sheet = _Year(balance_scheme, {NET_INCOME: net_income})
	for placed in placed_balance:
		sheet.add(placed)
	_offset_deficit(sheet)
	aktiva_total = sheet.amount(balance_scheme.aktiva.concept)
	deficit = sheet.amount(DEFICIT)
	balance_sheet = BalanceSheet(
		balance_scheme,
		size_class,
		_lines(sheet, balance_scheme, balance_scheme.aktiva, size_class),
		_lines(sheet, balance_scheme, balance_scheme.passiva, size_class),
		aktiva_total,
		sheet.amount(balance_scheme.passiva.concept),
		sheet.amount(EQUITY),
		deficit,
		aktiva_total - deficit,
	)
	if balance_sheet.difference:
		findings.append(_not_balanced(balance_sheet.difference))
	findings.extend(_unitemized(sheet, balance_scheme.visible(size_class), LEVELS[size_class].reference))
	findings.extend(
		_unitemized(income, tuple(income_scheme.positions()), f"§ 275 Abs. {_PARAGRAPHS[method]} HGB")
	)
	findings.extend(_without_term(sheet, balance_sheet))
	return AnnualStatement(balance_sheet, income_statement, tuple(findings))


_PARAGRAPHS = MappingProxyType({Method.GKV: 2, Method.UKV: 3})


def _offset_deficit(sheet: _Year) -> None:
	"""§ 268 Abs. 3 HGB: a negative Eigenkapital shows as a Fehlbetrag on the Aktiva and is offset within it."""
	equity = sheet.amount(EQUITY)
	if equity < 0:
		sheet.fix(DEFICIT, -equity)
		sheet.fix(DEFICIT_IN_EQUITY, -equity)


def _lines(
	sheet: _Year, scheme: BalanceSheetScheme, side: Position, size_class: SizeClass
) -> tuple[Line, ...]:
	"""The lines of one side of the balance sheet: the positions ``size_class`` shows, in their order."""
	lines: list[Line] = []
	for position in side.walk():
		if position is side or not scheme.shows(position.concept, size_class):
			continue
		line = sheet.line(position, scheme.vermerke(position.concept, size_class))
		vermerke = tuple(
			VermerkLine(noted.vermerk, sheet.amount(PROFIT_CARRIED_FORWARD))
			if noted.vermerk.kind is VermerkKind.PROFIT_CARRIED_FORWARD
			else noted
			for noted in line.vermerke
		)
		uncalled = any(
			noted.vermerk.kind is VermerkKind.UNCALLED_CAPITAL and noted.amount for noted in vermerke
		)
		lines.append(
			Line(position, CALLED_CAPITAL if uncalled else line.label, line.amount, vermerke, line.sources)
		)
	return tuple(lines)


def _place(
	balance: Balance, scheme: BalanceSheetScheme | IncomeStatementScheme, parents: Mapping[str, str]
) -> _Placed | None:
	"""The balance on the nearest position at or above its concept, or on the position of a Vermerk that names
	one of those concepts as a member."""
	chain: list[str] = []
	current: str | None = balance.concept
	while current is not None and current not in chain:
		chain.append(current)
		if scheme.has(current):
			return _Placed(balance, scheme.position(current), tuple(chain))
		current = parents.get(current)
	for position in scheme.positions():
		for vermerk in position.vermerke:
			if any(member in chain for member in vermerk.members):
				return _Placed(balance, scheme.position(vermerk.scope), tuple(chain))
	return None


def _selects(vermerk: Vermerk, placed: _Placed) -> bool:
	balance = placed.balance
	match vermerk.kind:
		case VermerkKind.RECEIVABLES_OVER_ONE_YEAR | VermerkKind.LIABILITIES_OVER_ONE_YEAR:
			return balance.remaining_term in _OVER_ONE_YEAR
		case VermerkKind.LIABILITIES_UP_TO_ONE_YEAR:
			return balance.remaining_term is RemainingTerm.UP_TO_ONE_YEAR
		case VermerkKind.SHAREHOLDERS:
			return balance.shareholder or _member(vermerk, placed)
		case _:
			return _member(vermerk, placed)


def _member(vermerk: Vermerk, placed: _Placed) -> bool:
	return any(concept in vermerk.members for concept in placed.chain)


def _signed(amount: Decimal, direction: Direction) -> Decimal:
	return amount if direction is Direction.DEBIT else -amount


def _sign(term: Position, result: Position) -> int:
	return 1 if term.direction is result.direction else -1


def _named(balance: Balance) -> str:
	return f"„{balance.source}“ ({balance.concept})" if balance.source else balance.concept


def _unplaced(balance: Balance) -> Finding:
	return Finding(
		Code.UNPLACED,
		Severity.ERROR,
		f"Der Saldo von {_named(balance)} gehört zu keinem Posten der Bilanz oder der Gewinn- und "
		"Verlustrechnung; die Zuordnung braucht einen Posten darunter.",
		_SCHEMES_REFERENCE,
		balance.concept,
		balance.amount,
	)


def _computed(balance: Balance, position: Position) -> Finding:
	return Finding(
		Code.COMPUTED,
		Severity.ERROR,
		f"Der Saldo von {_named(balance)} landet auf „{position.label}“, den Steuerbote aus anderen Posten "
		"errechnet; die Zuordnung braucht einen Posten darunter.",
		_SCHEMES_REFERENCE,
		balance.concept,
		balance.amount,
	)


def _not_balanced(difference: Decimal) -> Finding:
	return Finding(
		Code.NOT_BALANCED,
		Severity.ERROR,
		"Aktiva und Passiva der Bilanz weichen voneinander ab; ein Konto mit Saldo fehlt in der Zuordnung, oder die "
		"Salden enthalten die Abschlussbuchung des Geschäftsjahres.",
		"§ 242 Abs. 1, § 266 Abs. 1 Satz 1 HGB",
		amount=difference,
	)


def _unitemized(year: _Year, shown: tuple[Position, ...], reference: str) -> Iterator[Finding]:
	"""A balance on a position whose positions underneath are shown as well: the total would not add up."""
	concepts = {position.concept for position in shown}
	for position in shown:
		own = year.own[position.concept]
		if own and any(child.concept in concepts for child in position.children):
			sources = ", ".join(f"„{source}“" for source in year.sources[position.concept])
			named = f"{sources} ({position.concept})" if sources else position.concept
			yield Finding(
				Code.UNITEMIZED,
				Severity.ERROR,
				f"Der Saldo von {named} steht bei „{position.label}“, aber in keinem der Posten darunter; die "
				"Zuordnung braucht einen dieser Posten.",
				reference,
				position.concept,
				own,
			)


def _without_term(sheet: _Year, balance_sheet: BalanceSheet) -> Iterator[Finding]:
	"""Each balance whose remaining term a Vermerk the balance sheet notes would need, once."""
	seen: dict[int, None] = {}
	for line in balance_sheet.aktiva + balance_sheet.passiva:
		for noted in line.vermerke:
			for placed in sheet.without_term[(line.position.concept, noted.vermerk.kind)]:
				if id(placed) in seen:
					continue
				seen[id(placed)] = None
				yield Finding(
					Code.REMAINING_TERM_UNKNOWN,
					Severity.ERROR,
					f"Für {_named(placed.balance)} fehlt die Restlaufzeit, die der Vermerk „{noted.vermerk.label}“ "
					f"bei „{line.label}“ braucht; die Zuordnung nennt sie.",
					noted.vermerk.reference,
					placed.balance.concept,
					placed.balance.amount,
				)
