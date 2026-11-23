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
or „sonstige Aktiva“ under the total of the Aktiva, is an error: the balance sheet would leave it out.

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

Each line names the sources of the balances that landed on it, as the drill-down of the Annual Accounts shows
them. The schemes and their sources are steuerbote.hgb.schemes.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, StrEnum
from types import MappingProxyType

from steuerbote.hgb.schemes import (
	BalanceSheetScheme,
	Direction,
	IncomeStatementScheme,
	Method,
	Position,
	balance_sheet_scheme,
	income_statement_scheme,
)
from steuerbote.hgb.size import SizeClass

ZERO = Decimal("0")
NO_PARENTS: Mapping[str, str] = MappingProxyType({})
NET_INCOME = "bs.eqLiab.equity.netIncome"
EQUITY = "bs.eqLiab.equity"
DEFICIT = "bs.ass.deficitNotCoveredByCapital"
_SCHEMES_REFERENCE = "§§ 266, 275 HGB"


class RemainingTerm(Enum):
	UP_TO_ONE_YEAR = "bis zu einem Jahr"
	ONE_TO_FIVE_YEARS = "mehr als ein Jahr bis zu fünf Jahren"
	OVER_FIVE_YEARS = "mehr als fünf Jahre"


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
class Line:
	"""A line of the balance sheet or the income statement: its position and its amount in the direction of it."""

	position: Position
	amount: Decimal
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
	balance: Balance
	position: Position


class _Year:
	"""The amounts one fiscal year gives the positions of one scheme."""

	def __init__(
		self, scheme: BalanceSheetScheme | IncomeStatementScheme, fixed: Mapping[str, Decimal] | None = None
	) -> None:
		self.scheme = scheme
		self.fixed = dict(fixed or {})
		self.own: defaultdict[str, Decimal] = defaultdict(Decimal)
		self.sources: defaultdict[str, list[str]] = defaultdict(list)
		self._amounts: dict[str, Decimal] = {}

	def add(self, placed: _Placed) -> None:
		position = placed.position
		self.own[position.concept] += _signed(placed.balance.amount, position.direction)
		if placed.balance.source:
			self.sources[position.concept].append(placed.balance.source)

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

	def line(self, position: Position) -> Line:
		return Line(position, self.amount(position.concept), tuple(self.sources[position.concept]))


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
			position = _place(balance.concept, scheme, parents)
			if position is not None:
				if position.computed:
					findings.append(_computed(balance, position))
				else:
					placed.append(_Placed(balance, position))
				break
		else:
			findings.append(_unplaced(balance))
	income = _Year(income_scheme)
	for placed in placed_income:
		income.add(placed)
	net_income = income.amount(income_scheme.net_income.concept)
	income_statement = IncomeStatement(
		income_scheme,
		tuple(income.line(position) for position in income_scheme.positions()),
		net_income,
		income.amount(income_scheme.sales.concept),
	)
	sheet = _Year(balance_scheme, {NET_INCOME: net_income})
	for placed in placed_balance:
		sheet.add(placed)
	aktiva_total = sheet.amount(balance_scheme.aktiva.concept)
	balance_sheet = BalanceSheet(
		balance_scheme,
		size_class,
		_lines(sheet, balance_scheme, balance_scheme.aktiva, size_class),
		_lines(sheet, balance_scheme, balance_scheme.passiva, size_class),
		aktiva_total,
		sheet.amount(balance_scheme.passiva.concept),
		sheet.amount(EQUITY),
		aktiva_total - sheet.amount(DEFICIT),
	)
	if balance_sheet.difference:
		findings.append(_not_balanced(balance_sheet.difference))
	return AnnualStatement(balance_sheet, income_statement, tuple(findings))


def _lines(
	sheet: _Year, scheme: BalanceSheetScheme, side: Position, size_class: SizeClass
) -> tuple[Line, ...]:
	"""The lines of one side of the balance sheet: the positions ``size_class`` shows, in their order."""
	return tuple(
		sheet.line(position)
		for position in side.walk()
		if position is not side and scheme.shows(position.concept, size_class)
	)


def _place(
	concept: str, scheme: BalanceSheetScheme | IncomeStatementScheme, parents: Mapping[str, str]
) -> Position | None:
	"""The nearest position at or above ``concept``, or the position of a Vermerk that names it as a member."""
	chain: list[str] = []
	current: str | None = concept
	while current is not None and current not in chain:
		if scheme.has(current):
			return scheme.position(current)
		chain.append(current)
		current = parents.get(current)
	for position in scheme.positions():
		for vermerk in position.vermerke:
			if any(member in chain for member in vermerk.members):
				return scheme.position(vermerk.scope)
	return None


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
