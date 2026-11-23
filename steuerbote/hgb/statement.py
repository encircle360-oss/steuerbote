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

Ergebnisverwendung. „Die Bilanz darf auch unter Berücksichtigung der vollständigen oder teilweisen Verwendung des
Jahresergebnisses aufgestellt werden. Wird die Bilanz unter Berücksichtigung der teilweisen Verwendung des
Jahresergebnisses aufgestellt, so tritt an die Stelle der Posten „Jahresüberschuß/Jahresfehlbetrag“ und
„Gewinnvortrag/Verlustvortrag“ der Posten „Bilanzgewinn/Bilanzverlust“; ein vorhandener Gewinn- oder
Verlustvortrag ist in den Posten „Bilanzgewinn/Bilanzverlust“ einzubeziehen und in der Bilanz gesondert
anzugeben.“ (§ 268 Abs. 1 Satz 1 and 2 HGB) ProfitPresentation chooses: before the appropriation the balance sheet
shows „IV.“ and „V.“, after part of it the Bilanzgewinn adds both to the balances of the appropriation, which the
mapping places on the Bilanzgewinn, and notes the Gewinnvortrag; a balance on the Bilanzgewinn before the
appropriation is an error. An UG draws its balance sheet up after part of the appropriation: „In der Bilanz des
nach den §§ 242, 264 des Handelsgesetzbuchs aufzustellenden Jahresabschlusses ist eine gesetzliche Rücklage zu
bilden, in die ein Viertel des um einen Verlustvortrag aus dem Vorjahr geminderten Jahresüberschusses einzustellen
ist.“ (§ 5a Abs. 3 Satz 1 GmbHG, ug_reserve_minimum())

Previous year. „In der Bilanz sowie in der Gewinn- und Verlustrechnung ist zu jedem Posten der entsprechende
Betrag des vorhergehenden Geschäftsjahrs anzugeben.“ (§ 265 Abs. 2 Satz 1 HGB) The previous year goes through the
same steps in the form of the current class, from its books or, in the first year with Steuerbote, from the
figures of the last festgestellter Jahresabschluss entered at the positions (entered()); its findings say
„Vorjahr“. „Ein Posten der Bilanz oder der Gewinn- und Verlustrechnung, der keinen Betrag ausweist, braucht nicht
aufgeführt zu werden, es sei denn, daß im vorhergehenden Geschäftsjahr unter diesem Posten ein Betrag ausgewiesen
wurde.“ (§ 265 Abs. 8 HGB) A line without an amount in either year is therefore not ``shown``, except the
Eigenkapital and the Gezeichnetes Kapital, which § 42 Abs. 1 GmbHG wants in every balance sheet of a GmbH, and the
results of the income statement.

Each line names the sources of the balances that landed on it, as the drill-down of the Annual Accounts shows
them. The schemes and their sources are steuerbote.hgb.schemes.
"""

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
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
from steuerbote.ustva.rounding import ceil_cents

ZERO = Decimal("0")
NO_PARENTS: Mapping[str, str] = MappingProxyType({})
NET_INCOME = "bs.eqLiab.equity.netIncome"
PROFIT_CARRIED_FORWARD = "bs.eqLiab.equity.retainedEarnings"
EQUITY = "bs.eqLiab.equity"
DEFICIT = "bs.ass.deficitNotCoveredByCapital"
DEFICIT_IN_EQUITY = "bs.eqLiab.equity.deficitNotCoveredByCapital"
BILANZGEWINN = "bs.eqLiab.equity.profitLoss"
_UG_RESERVE_SHARE = Decimal("4")
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


def entered(
	position: Position,
	amount: Decimal,
	*,
	shareholder: bool = False,
	remaining_term: RemainingTerm | None = None,
	source: str = "Vorjahr",
) -> Balance:
	"""The balance of an amount entered at a position in its direction, such as a figure of the last festgestellter
	Jahresabschluss for the first previous year."""
	return Balance(position.concept, _signed(amount, position.direction), shareholder, remaining_term, source)


class ProfitPresentation(Enum):
	BEFORE_APPROPRIATION = "vor Verwendung des Jahresergebnisses"
	AFTER_PARTIAL_APPROPRIATION = "nach teilweiser Verwendung des Jahresergebnisses"


def ug_reserve_minimum(net_income: Decimal, carried_forward: Decimal) -> Decimal:
	"""What an UG puts into its gesetzliche Rücklage at least (§ 5a Abs. 3 Satz 1 GmbHG): a quarter of the
	Jahresüberschuss less the Verlustvortrag, both as the lines show them, rounded up to the cent; nothing from a
	Jahresfehlbetrag or a Jahresüberschuss the Verlustvortrag uses up."""
	base = net_income + min(carried_forward, ZERO)
	return ceil_cents(max(base, ZERO) / _UG_RESERVE_SHARE)


class Severity(Enum):
	ERROR = "Fehler"
	HINT = "Hinweis"


class Code(StrEnum):
	UNPLACED = "JA-OHNE-POSTEN"
	COMPUTED = "JA-RECHENPOSTEN"
	NOT_BALANCED = "JA-BILANZ-UNGLEICH"
	UNITEMIZED = "JA-OHNE-UNTERPOSTEN"
	REMAINING_TERM_UNKNOWN = "JA-RESTLAUFZEIT-FEHLT"
	APPROPRIATION = "JA-BILANZGEWINN"


@dataclass(frozen=True, slots=True)
class Finding:
	"""What holds the Jahresabschluss back (an error) or what someone should look at (a hint), as one German
	sentence with its source; ``concept`` and ``amount`` name what it is about. ``code`` is a Code of this module
	or a code of steuerbote.hgb.notes and steuerbote.hgb.disclosure."""

	code: str
	severity: Severity
	text: str
	reference: str
	concept: str = ""
	amount: Decimal | None = None
	prior_year: bool = False

	@property
	def blocking(self) -> bool:
		return self.severity is Severity.ERROR


@dataclass(frozen=True, slots=True)
class VermerkLine:
	"""A Vermerk of a line with its amount and the amount of the previous year, None without one."""

	vermerk: Vermerk
	amount: Decimal
	prior: Decimal | None = None

	@property
	def shown(self) -> bool:
		"""§ 265 Abs. 8 HGB: a Vermerk without an amount in either year need not be noted."""
		return bool(self.amount) or bool(self.prior)


@dataclass(frozen=True, slots=True)
class Line:
	"""A line of the balance sheet or the income statement: its position, its name, its amount in the direction of
	the position and that of the previous year (None without one), its Vermerke and the sources of its balances.
	``shown`` is False for a line § 265 Abs. 8 HGB leaves out."""

	position: Position
	label: str
	amount: Decimal
	prior: Decimal | None = None
	vermerke: tuple[VermerkLine, ...] = ()
	sources: tuple[str, ...] = ()
	shown: bool = True


def _line(lines: Iterable[Line], concept: str) -> Line:
	for line in lines:
		if line.position.concept == concept:
			return line
	raise KeyError(f"no line shows the position {concept}")


@dataclass(frozen=True, slots=True)
class IncomeStatement:
	"""The income statement: its lines, the Jahresüberschuss/Jahresfehlbetrag and the Umsatzerlöse, each also of the
	previous year."""

	scheme: IncomeStatementScheme
	lines: tuple[Line, ...]
	net_income: Decimal
	sales: Decimal
	prior_net_income: Decimal | None = None
	prior_sales: Decimal | None = None

	def line(self, concept: str) -> Line:
		return _line(self.lines, concept)


@dataclass(frozen=True, slots=True)
class BalanceSheet:
	"""The balance sheet of a size class: the lines of each side, their totals, the Eigenkapital and the
	Bilanzsumme of § 267 Abs. 4a HGB, the totals and the Bilanzsumme also of the previous year."""

	scheme: BalanceSheetScheme
	size_class: SizeClass
	aktiva: tuple[Line, ...]
	passiva: tuple[Line, ...]
	aktiva_total: Decimal
	passiva_total: Decimal
	equity: Decimal
	deficit: Decimal
	bilanzsumme: Decimal
	prior_aktiva_total: Decimal | None = None
	prior_passiva_total: Decimal | None = None
	prior_bilanzsumme: Decimal | None = None

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
		self.placed: defaultdict[str, list[_Placed]] = defaultdict(list)
		self._amounts: dict[str, Decimal] = {}

	def add(self, placed: _Placed) -> None:
		position, balance = placed.position, placed.balance
		self.placed[position.concept].append(placed)
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

	def vermerk(self, concept: str, vermerk: Vermerk) -> Decimal:
		if vermerk.kind is VermerkKind.PROFIT_CARRIED_FORWARD:
			return self.amount(PROFIT_CARRIED_FORWARD)
		return self.noted[(concept, vermerk.kind)]

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

	def _up_from(self, position: Position) -> Iterator[Position]:
		current: Position | None = position
		while current is not None:
			yield current
			current = self.scheme.parent(current.concept)

	def _within(self, position: Position, scope: str) -> bool:
		return any(holder.concept == scope for holder in self._up_from(position))


class _Books:
	"""One fiscal year of the books in both schemes, with the findings of placing its balances."""

	def __init__(
		self,
		balance_scheme: BalanceSheetScheme,
		income_scheme: IncomeStatementScheme,
		balances: Iterable[Balance],
		parents: Mapping[str, str],
		net_income: Decimal | None = None,
	) -> None:
		self.findings: list[Finding] = []
		self.income = _Year(income_scheme)
		placed_balance: list[_Placed] = []
		with_income = False
		for balance in balances:
			for scheme in (balance_scheme, income_scheme):
				found = _place(balance, scheme, parents)
				if found is None:
					continue
				if found.position.computed:
					self.findings.append(_computed(balance, found.position))
				elif scheme is income_scheme:
					self.income.add(found)
					with_income = True
				else:
					placed_balance.append(found)
				break
			else:
				self.findings.append(_unplaced(balance))
		self.net_income = self.income.amount(income_scheme.net_income.concept)
		if net_income is not None and not with_income:
			self.net_income = net_income
		self.sales = self.income.amount(income_scheme.sales.concept)
		self.sheet = _Year(balance_scheme, {NET_INCOME: self.net_income})
		for placed in placed_balance:
			self.sheet.add(placed)
		_offset_deficit(self.sheet)
		self.aktiva_total = self.sheet.amount(balance_scheme.aktiva.concept)
		self.passiva_total = self.sheet.amount(balance_scheme.passiva.concept)
		self.bilanzsumme = self.aktiva_total - self.sheet.amount(DEFICIT)
		if self.aktiva_total != self.passiva_total:
			self.findings.append(_not_balanced(self.aktiva_total - self.passiva_total))


def build(
	year: int,
	size_class: SizeClass,
	balances: Iterable[Balance],
	*,
	parents: Mapping[str, str] = NO_PARENTS,
	prior: Iterable[Balance] | None = None,
	prior_net_income: Decimal | None = None,
	method: Method = Method.GKV,
	presentation: ProfitPresentation = ProfitPresentation.BEFORE_APPROPRIATION,
) -> AnnualStatement:
	"""The balance sheet and the income statement of ``size_class`` for the fiscal year that ends in ``year``.

	``balances`` holds the balances of the books, of the balance sheet and of the income statement alike, as the
	Balance Sheet Mapping delivers them; ``parents`` the hierarchy of their concepts. ``prior`` holds those of the
	previous year in the same form: from its books, or for the first year entered by hand from the last
	festgestellter Jahresabschluss at the positions of the class (entered()); ``prior_net_income`` gives the
	Jahresüberschuss/Jahresfehlbetrag of such a previous year without its income statement. ``presentation``
	chooses whether the balance sheet is drawn up before or after part of the result is appropriated.
	"""
	balance_scheme = balance_sheet_scheme(year)
	income_scheme = income_statement_scheme(year, method)
	current = _Books(balance_scheme, income_scheme, balances, parents)
	previous = (
		None if prior is None else _Books(balance_scheme, income_scheme, prior, parents, prior_net_income)
	)
	income_statement = IncomeStatement(
		income_scheme,
		tuple(
			_line_of(position, position.vermerke, current.income, previous and previous.income)
			for position in income_scheme.positions()
		),
		current.net_income,
		current.sales,
		None if previous is None else previous.net_income,
		None if previous is None else previous.sales,
	)
	balance_sheet = BalanceSheet(
		balance_scheme,
		size_class,
		_lines(current, previous, balance_scheme, balance_scheme.aktiva, size_class, presentation),
		_lines(current, previous, balance_scheme, balance_scheme.passiva, size_class, presentation),
		current.aktiva_total,
		current.passiva_total,
		current.sheet.amount(EQUITY),
		current.sheet.amount(DEFICIT),
		current.bilanzsumme,
		None if previous is None else previous.aktiva_total,
		None if previous is None else previous.passiva_total,
		None if previous is None else previous.bilanzsumme,
	)
	findings = list(_year_findings(current, balance_sheet, size_class, method, presentation))
	if previous is not None:
		findings.extend(
			replace(finding, text=f"Vorjahr: {finding.text}", prior_year=True)
			for finding in _year_findings(previous, balance_sheet, size_class, method, presentation)
		)
	return AnnualStatement(balance_sheet, income_statement, tuple(findings))


_PARAGRAPHS = MappingProxyType({Method.GKV: 2, Method.UKV: 3})
_ALWAYS_SHOWN = frozenset({EQUITY, "bs.eqLiab.equity.subscribed"})
_REPLACED_BY_BILANZGEWINN = frozenset({PROFIT_CARRIED_FORWARD, NET_INCOME})


def _year_findings(
	books: _Books,
	balance_sheet: BalanceSheet,
	size_class: SizeClass,
	method: Method,
	presentation: ProfitPresentation,
) -> Iterator[Finding]:
	yield from books.findings
	if presentation is ProfitPresentation.BEFORE_APPROPRIATION:
		for placed in books.sheet.placed[BILANZGEWINN]:
			if placed.balance.amount:
				yield _appropriated(placed.balance)
	yield from _unitemized(
		books.sheet, balance_sheet.scheme.visible(size_class), LEVELS[size_class].reference
	)
	yield from _unitemized(
		books.income, tuple(books.income.scheme.positions()), f"§ 275 Abs. {_PARAGRAPHS[method]} HGB"
	)
	yield from _without_term(books.sheet, balance_sheet)


def _offset_deficit(sheet: _Year) -> None:
	"""§ 268 Abs. 3 HGB: a negative Eigenkapital shows as a Fehlbetrag on the Aktiva and is offset within it."""
	equity = sheet.amount(EQUITY)
	if equity < 0:
		sheet.fix(DEFICIT, -equity)
		sheet.fix(DEFICIT_IN_EQUITY, -equity)


def _line_of(
	position: Position, vermerke: tuple[Vermerk, ...], current: _Year, previous: _Year | None
) -> Line:
	concept = position.concept
	amount = current.amount(concept)
	prior = None if previous is None else previous.amount(concept)
	return Line(
		position,
		position.label,
		amount,
		prior,
		tuple(
			VermerkLine(
				vermerk,
				current.vermerk(concept, vermerk),
				None if previous is None else previous.vermerk(concept, vermerk),
			)
			for vermerk in vermerke
		),
		tuple(current.sources[concept]),
		bool(position.terms) or concept in _ALWAYS_SHOWN or bool(amount) or bool(prior),
	)


def _lines(
	current: _Books,
	previous: _Books | None,
	scheme: BalanceSheetScheme,
	side: Position,
	size_class: SizeClass,
	presentation: ProfitPresentation,
) -> tuple[Line, ...]:
	"""The lines of one side of the balance sheet: the positions ``size_class`` shows, in their order."""
	after = presentation is ProfitPresentation.AFTER_PARTIAL_APPROPRIATION
	hidden = _REPLACED_BY_BILANZGEWINN if after else frozenset({BILANZGEWINN})
	lines: list[Line] = []
	for position in side.walk():
		if position is side or position.concept in hidden or not scheme.shows(position.concept, size_class):
			continue
		line = _line_of(
			position,
			scheme.vermerke(position.concept, size_class),
			current.sheet,
			None if previous is None else previous.sheet,
		)
		if position.concept == BILANZGEWINN:
			amount = _bilanzgewinn(current.sheet)
			prior = None if previous is None else _bilanzgewinn(previous.sheet)
			line = replace(line, amount=amount, prior=prior, shown=bool(amount) or bool(prior))
		if any(
			noted.vermerk.kind is VermerkKind.UNCALLED_CAPITAL and noted.amount for noted in line.vermerke
		):
			line = replace(line, label=CALLED_CAPITAL)
		lines.append(line)
	return tuple(lines)


def _bilanzgewinn(sheet: _Year) -> Decimal:
	"""The Bilanzgewinn/Bilanzverlust: the Gewinnvortrag, the Jahresüberschuss and what was appropriated."""
	return sheet.amount(PROFIT_CARRIED_FORWARD) + sheet.amount(NET_INCOME) + sheet.amount(BILANZGEWINN)


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


def _appropriated(balance: Balance) -> Finding:
	return Finding(
		Code.APPROPRIATION,
		Severity.ERROR,
		f"Der Saldo von {_named(balance)} steht auf dem Bilanzgewinn, die Bilanz ist aber vor Verwendung des "
		"Jahresergebnisses aufgestellt; sie braucht die Darstellung nach teilweiser Verwendung.",
		"§ 268 Abs. 1 Satz 2 HGB",
		balance.concept,
		balance.amount,
	)
