"""The categories of the Income Tax Mapping: what the balance of an account means for the Körperschaftsteuer and the
Gewerbesteuer.

Every account of the profit and loss account counts in the Jahresüberschuss (Anlage GK line 11). A category says
what the computation corrects about an account outside the books, or what the Gewerbesteuer adds back or cuts. The
categories by group:

- taxes on income, which § 10 Nummer 2 KStG and § 4 Absatz 5b EStG do not let reduce the income: ``kst``, ``solz``,
  ``kapest``, ``gewst`` and ``foreign_tax`` (Anlage GK lines 81 to 84 and 87);
- non-deductible expenses: ``ancillary`` (Nebenleistungen to these taxes, line 88), ``supervisory_board`` (the
  non-deductible half of the fees, booked on an account of its own as DATEV SKR03 2385 does, line 89),
  ``gifts_nondeductible``, ``entertainment_nondeductible`` and ``other_nondeductible`` (line 90), and
  ``entertainment_deductible``, the deductible 70 % of entertainment, which only gives a hint when nothing is booked
  as non-deductible;
- ``donations`` (line 92, deducted within the limits in Anlage ZVE line 34), ``tax_free`` (line 102) and
  ``investment_grant`` (line 96);
- § 8b KStG: ``dividends``, ``share_gain``, ``share_loss``, ``share_writedown``, ``share_writeup`` and
  ``share_sale_costs`` (lines 151 to 201);
- Termingeschäfte of § 15 Absatz 4 Satz 3 EStG: ``derivatives_gain`` and ``derivatives_loss`` (lines 51 and 52);
  ``funds`` for investment funds (InvStG, lines 219 to 237); the Investitionsabzugsbetrag of § 7g EStG:
  ``iab_deduction`` (line 67) and ``iab_addback`` (lines 70 to 72);
- Gewerbesteuer only: the financing parts of § 8 Nummer 1 GewStG, ``interest``, ``annuities``, ``silent_partner``,
  ``rent_movable``, ``rent_movable_ev``, ``rent_immovable`` and ``licences`` (GewSt 1 A lines 50 to 57), and
  ``property_tax_own``, the Grundsteuer of § 9 Nummer 1 Satz 1 GewStG (line 87);
- ``trading_unclassified``, the accounts that hold the results of trading in financial instruments.

A trading account, such as SKR03 2654 „Erträge aus anderen Wertpapieren und Ausleihungen des Umlaufvermögens“ or
2166 „Aufwendungen aus Bewertung Finanzmittelfonds“ (SKR04 7115 and 6883), holds the gain or loss of each trade. What
that result is for the tax depends on the instrument: a share (§ 8b Absatz 2 and 3 KStG), a Termingeschäft (§ 15
Absatz 4 Satz 3 EStG), an investment fund (InvStG) or anything else, which is fully taxable. The class decides
between exemption, the separate loss pool and full taxation, which moves the zu versteuerndes Einkommen and the
Gewerbeertrag a lot, and the facts differ per company; so the Steuerberatung sets the TradingClass of each trading
account, the defaults set none, and a trading account without a class holds the filing back. A class splits the
account voucher by voucher: a voucher whose balance on the account is on the credit side is a gain, one on the debit
side a loss (TRADING_CATEGORIES).

Foreign taxes (Anlage AESt) and investment funds (InvStG) are later modules; until they exist a balance on one of
their categories holds the filing back (LATER).

A Mapping belongs to one company and holds one AccountRule per account. A watched account may belong to the
Körperschaftsteuer or the Gewerbesteuer without a category yet, such as an account DATEV marks for its tax programs
(Programmverbindung K or G) that the defaults leave open: at the blocking level a balance on it holds the filing back,
at the hint level it only gives a hint, as for the watched accounts of the Umsatzsteuer-Voranmeldung
(steuerbote.ustva.mapping).

classify() sums the ledger lines of the Wirtschaftsjahr per category, in the direction of the category, and keeps
the postings behind each amount as a Contribution per account and voucher, so that a report can show the entries
behind each line of the declaration. The lines are those of steuerbote.ustva (LedgerLine): one posting on one account
in cents, with the key "<voucher type>:<voucher name>" of its voucher; lines without a voucher count as one. An
account without rule counts in no category, only in the Jahresüberschuss. The Classification also lists what holds
the filing back: the trading accounts without class that have a balance (``unclassified``), the later categories
with a balance (``later``) and the watched accounts with a balance by level (``watched``, ``hinted``).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, StrEnum
from types import MappingProxyType

from steuerbote.ustva.calculation import AccountBalance, LedgerLine
from steuerbote.ustva.mapping import MappingError, WatchedAccount, WatchLevel, is_account_number
from steuerbote.ustva.rounding import ZERO


class Category(StrEnum):
	KST = "kst"
	SOLZ = "solz"
	KAPEST = "kapest"
	GEWST = "gewst"
	FOREIGN_TAX = "foreign_tax"
	ANCILLARY = "ancillary"
	SUPERVISORY_BOARD = "supervisory_board"
	GIFTS_NONDEDUCTIBLE = "gifts_nondeductible"
	ENTERTAINMENT_NONDEDUCTIBLE = "entertainment_nondeductible"
	ENTERTAINMENT_DEDUCTIBLE = "entertainment_deductible"
	OTHER_NONDEDUCTIBLE = "other_nondeductible"
	DONATIONS = "donations"
	TAX_FREE = "tax_free"
	INVESTMENT_GRANT = "investment_grant"
	DIVIDENDS = "dividends"
	SHARE_GAIN = "share_gain"
	SHARE_LOSS = "share_loss"
	SHARE_WRITEDOWN = "share_writedown"
	SHARE_WRITEUP = "share_writeup"
	SHARE_SALE_COSTS = "share_sale_costs"
	DERIVATIVES_GAIN = "derivatives_gain"
	DERIVATIVES_LOSS = "derivatives_loss"
	FUNDS = "funds"
	IAB_DEDUCTION = "iab_deduction"
	IAB_ADDBACK = "iab_addback"
	INTEREST = "interest"
	ANNUITIES = "annuities"
	SILENT_PARTNER = "silent_partner"
	RENT_MOVABLE = "rent_movable"
	RENT_MOVABLE_EV = "rent_movable_ev"
	RENT_IMMOVABLE = "rent_immovable"
	LICENCES = "licences"
	PROPERTY_TAX_OWN = "property_tax_own"
	TRADING_UNCLASSIFIED = "trading_unclassified"


class Nature(Enum):
	"""On which side a category counts its amount: an expense on the debit side, an income on the credit side."""

	EXPENSE = "expense"
	INCOME = "income"


@dataclass(frozen=True, slots=True)
class CategoryInfo:
	"""``label`` names the category in German, as findings and reports show it; ``later`` marks a category Steuerbote
	does not compute yet, ``hint_only`` one that only gives a hint."""

	label: str
	nature: Nature
	law: str
	later: bool = False
	hint_only: bool = False


_EXPENSE, _INCOME = Nature.EXPENSE, Nature.INCOME

CATEGORIES: MappingProxyType[Category, CategoryInfo] = MappingProxyType(
	{
		Category.KST: CategoryInfo("Körperschaftsteuer", _EXPENSE, "§ 10 Nummer 2 KStG"),
		Category.SOLZ: CategoryInfo("Solidaritätszuschlag", _EXPENSE, "§ 10 Nummer 2 KStG"),
		Category.KAPEST: CategoryInfo("Kapitalertragsteuer", _EXPENSE, "§ 10 Nummer 2 KStG"),
		Category.GEWST: CategoryInfo("Gewerbesteuer", _EXPENSE, "§ 4 Absatz 5b EStG"),
		Category.FOREIGN_TAX: CategoryInfo(
			"Ausländische Steuern", _EXPENSE, "§ 10 Nummer 2, § 26 KStG", later=True
		),
		Category.ANCILLARY: CategoryInfo(
			"Nebenleistungen zu den Steuern", _EXPENSE, "§ 10 Nummer 2 zweiter Halbsatz KStG"
		),
		Category.SUPERVISORY_BOARD: CategoryInfo(
			"Nicht abziehbare Hälfte der Aufsichtsratsvergütungen", _EXPENSE, "§ 10 Nummer 4 KStG"
		),
		Category.GIFTS_NONDEDUCTIBLE: CategoryInfo(
			"Nicht abzugsfähige Geschenke", _EXPENSE, "§ 4 Absatz 5 Satz 1 Nummer 1 EStG"
		),
		Category.ENTERTAINMENT_NONDEDUCTIBLE: CategoryInfo(
			"Nicht abzugsfähige Bewirtungskosten", _EXPENSE, "§ 4 Absatz 5 Satz 1 Nummer 2 EStG"
		),
		Category.ENTERTAINMENT_DEDUCTIBLE: CategoryInfo(
			"Abzugsfähige Bewirtungskosten", _EXPENSE, "§ 4 Absatz 5 Satz 1 Nummer 2 EStG", hint_only=True
		),
		Category.OTHER_NONDEDUCTIBLE: CategoryInfo(
			"Sonstige nicht abziehbare Aufwendungen",
			_EXPENSE,
			"§ 4 Absatz 5 EStG, § 10 Nummer 3 KStG, § 160 AO",
		),
		Category.DONATIONS: CategoryInfo(
			"Zuwendungen", _EXPENSE, "§ 9 Absatz 1 Nummer 2 KStG, § 9 Nummer 5 GewStG"
		),
		Category.TAX_FREE: CategoryInfo("Steuerfreie Einnahmen", _INCOME, "§ 3 und § 3c Absatz 1 EStG"),
		Category.INVESTMENT_GRANT: CategoryInfo("Investitionszulage", _INCOME, "§ 13 Satz 1 InvZulG 2010"),
		Category.DIVIDENDS: CategoryInfo(
			"Bezüge aus Anteilen",
			_INCOME,
			"§ 8b Absatz 1, 4 und 5 KStG; § 8 Nummer 5, § 9 Nummer 2a und 7 GewStG",
		),
		Category.SHARE_GAIN: CategoryInfo(
			"Gewinne aus der Veräußerung von Anteilen",
			_INCOME,
			"§ 8b Absatz 2 Satz 1 und Absatz 3 Satz 1 KStG",
		),
		Category.SHARE_LOSS: CategoryInfo(
			"Verluste aus der Veräußerung von Anteilen", _EXPENSE, "§ 8b Absatz 3 Satz 3 KStG"
		),
		Category.SHARE_WRITEDOWN: CategoryInfo(
			"Teilwertabschreibungen auf Anteile", _EXPENSE, "§ 8b Absatz 3 Satz 3 KStG"
		),
		Category.SHARE_WRITEUP: CategoryInfo(
			"Wertaufholungen bei Anteilen", _INCOME, "§ 8b Absatz 2 Satz 3 und Absatz 3 Satz 1 KStG"
		),
		Category.SHARE_SALE_COSTS: CategoryInfo(
			"Veräußerungskosten von Anteilen", _EXPENSE, "§ 8b Absatz 2 Satz 2 KStG"
		),
		Category.DERIVATIVES_GAIN: CategoryInfo(
			"Gewinne aus Termingeschäften", _INCOME, "§ 15 Absatz 4 Satz 3 EStG"
		),
		Category.DERIVATIVES_LOSS: CategoryInfo(
			"Verluste aus Termingeschäften", _EXPENSE, "§ 15 Absatz 4 Satz 3 EStG"
		),
		Category.FUNDS: CategoryInfo("Erträge aus Investmentfonds", _INCOME, "§ 20 InvStG", later=True),
		Category.IAB_DEDUCTION: CategoryInfo("Investitionsabzugsbetrag", _EXPENSE, "§ 7g Absatz 1 EStG"),
		Category.IAB_ADDBACK: CategoryInfo(
			"Hinzurechnung von Investitionsabzugsbeträgen", _INCOME, "§ 7g Absatz 2 Satz 1 EStG"
		),
		Category.INTEREST: CategoryInfo("Entgelte für Schulden", _EXPENSE, "§ 8 Nummer 1 Buchstabe a GewStG"),
		Category.ANNUITIES: CategoryInfo(
			"Renten und dauernde Lasten", _EXPENSE, "§ 8 Nummer 1 Buchstabe b GewStG"
		),
		Category.SILENT_PARTNER: CategoryInfo(
			"Gewinnanteile stiller Gesellschafter", _EXPENSE, "§ 8 Nummer 1 Buchstabe c GewStG"
		),
		Category.RENT_MOVABLE: CategoryInfo(
			"Mieten und Leasingraten für bewegliche Wirtschaftsgüter",
			_EXPENSE,
			"§ 8 Nummer 1 Buchstabe d Satz 1 GewStG",
		),
		Category.RENT_MOVABLE_EV: CategoryInfo(
			"Mieten und Leasingraten für Elektrofahrzeuge und Fahrräder",
			_EXPENSE,
			"§ 8 Nummer 1 Buchstabe d Satz 2 GewStG",
		),
		Category.RENT_IMMOVABLE: CategoryInfo(
			"Mieten und Pachten für unbewegliche Wirtschaftsgüter",
			_EXPENSE,
			"§ 8 Nummer 1 Buchstabe e GewStG",
		),
		Category.LICENCES: CategoryInfo(
			"Aufwendungen für die Überlassung von Rechten", _EXPENSE, "§ 8 Nummer 1 Buchstabe f GewStG"
		),
		Category.PROPERTY_TAX_OWN: CategoryInfo(
			"Grundsteuer für eigenen Grundbesitz", _EXPENSE, "§ 9 Nummer 1 Satz 1 GewStG"
		),
		Category.TRADING_UNCLASSIFIED: CategoryInfo(
			"Handelsergebnis ohne Klasse", _INCOME, "§ 8b KStG, § 15 Absatz 4 Satz 3 EStG, § 20 InvStG"
		),
	}
)
LATER = frozenset(category for category, info in CATEGORIES.items() if info.later)


class TradingClass(StrEnum):
	"""What the results on a trading account are: shares, Termingeschäfte, investment funds, or fully taxable."""

	SHARES = "shares"
	DERIVATIVES = "derivatives"
	FUNDS = "funds"
	TAXABLE = "taxable"


# The categories of a gain and of a loss on a trading account of each class; a fully taxable result stays in the
# Jahresüberschuss and needs none.
TRADING_CATEGORIES: MappingProxyType[TradingClass, tuple[Category, Category] | None] = MappingProxyType(
	{
		TradingClass.SHARES: (Category.SHARE_GAIN, Category.SHARE_LOSS),
		TradingClass.DERIVATIVES: (Category.DERIVATIVES_GAIN, Category.DERIVATIVES_LOSS),
		TradingClass.FUNDS: (Category.FUNDS, Category.FUNDS),
		TradingClass.TAXABLE: None,
	}
)


@dataclass(frozen=True, slots=True)
class AccountRule:
	"""An account in a category; a trading account (``trading_unclassified``) may carry its TradingClass."""

	account_number: str
	category: Category
	trading_class: TradingClass | None = None

	def __post_init__(self) -> None:
		if not is_account_number(self.account_number):
			raise MappingError(f"{self.account_number!r} is not an account number")
		object.__setattr__(self, "category", Category(self.category))
		if self.trading_class is None:
			return
		if self.category is not Category.TRADING_UNCLASSIFIED:
			raise MappingError(
				f"account {self.account_number}: a trading class needs the category {Category.TRADING_UNCLASSIFIED}"
			)
		object.__setattr__(self, "trading_class", TradingClass(self.trading_class))


@dataclass(frozen=True, slots=True)
class Mapping:
	"""The Income Tax Mapping of a company: one rule per account, and the accounts it watches."""

	chart: str
	rules: tuple[AccountRule, ...]
	watched: tuple[WatchedAccount, ...] = ()
	_by_account: MappingProxyType[str, AccountRule] = field(init=False, repr=False, compare=False)

	def __post_init__(self) -> None:
		rules = _sequence(self.rules, "rules must be a sequence of AccountRule")
		watched = tuple(
			item if isinstance(item, WatchedAccount) else WatchedAccount(item)
			for item in _sequence(self.watched, "watched must be a sequence of account numbers")
		)
		mapped: dict[str, AccountRule] = {}
		for rule in rules:
			if rule.account_number in mapped:
				raise MappingError(f"account {rule.account_number} has more than one rule")
			mapped[rule.account_number] = rule
		seen: set[str] = set()
		for item in watched:
			if item.account_number in mapped:
				raise MappingError(f"account {item.account_number} is mapped and watched")
			if item.account_number in seen:
				raise MappingError(f"account {item.account_number} is watched twice")
			seen.add(item.account_number)
		object.__setattr__(self, "rules", rules)
		object.__setattr__(self, "watched", watched)
		object.__setattr__(self, "_by_account", MappingProxyType(mapped))

	def rule_for(self, account_number: str) -> AccountRule | None:
		return self._by_account.get(account_number)

	def watched_at(self, level: WatchLevel) -> frozenset[str]:
		return frozenset(item.account_number for item in self.watched if item.level is level)


@dataclass(frozen=True, slots=True)
class Contribution:
	"""What the postings of one voucher on one account add to a category."""

	category: Category
	account_number: str
	voucher: str | None
	debit: Decimal
	credit: Decimal

	@property
	def amount(self) -> Decimal:
		"""Debit less credit for an expense, credit less debit for an income."""
		if CATEGORIES[self.category].nature is Nature.EXPENSE:
			return self.debit - self.credit
		return self.credit - self.debit


@dataclass(frozen=True, slots=True)
class CategoryAmount:
	category: Category
	contributions: tuple[Contribution, ...]

	@property
	def amount(self) -> Decimal:
		return sum((contribution.amount for contribution in self.contributions), ZERO)


@dataclass(frozen=True, slots=True)
class Classification:
	"""The amounts of the categories that have postings, and what holds the filing back."""

	amounts: MappingProxyType[Category, CategoryAmount]
	unclassified: tuple[AccountBalance, ...]
	watched: tuple[AccountBalance, ...]
	hinted: tuple[AccountBalance, ...]

	def amount(self, *categories: Category) -> Decimal:
		"""The sum of the categories, 0 for one without postings."""
		return sum((self.amounts[c].amount for c in categories if c in self.amounts), ZERO)

	def contributions(self, *categories: Category) -> tuple[Contribution, ...]:
		return tuple(
			contribution
			for category in categories
			if category in self.amounts
			for contribution in self.amounts[category].contributions
		)

	@property
	def later(self) -> tuple[Category, ...]:
		"""The categories Steuerbote does not compute yet that have a balance."""
		return tuple(category for category in self.amounts if category in LATER and self.amount(category))


def classify(lines: Iterable[LedgerLine], mapping: Mapping) -> Classification:
	"""The ledger lines of the Wirtschaftsjahr by category; see the module docstring."""
	totals: dict[str, dict[str | None, list[Decimal]]] = {}
	for line in lines:
		total = totals.setdefault(line.account_number, {}).setdefault(line.voucher, [ZERO, ZERO])
		total[0] += line.debit
		total[1] += line.credit
	contributions: dict[Category, list[Contribution]] = {}
	balances: dict[str, list[Decimal]] = {}
	for account, vouchers in totals.items():
		rule = mapping.rule_for(account)
		balance = balances.setdefault(account, [ZERO, ZERO])
		for voucher, (debit, credit) in vouchers.items():
			balance[0] += debit
			balance[1] += credit
			category = None if rule is None else _category(rule, debit, credit)
			if category is not None:
				contribution = Contribution(category, account, voucher, debit, credit)
				contributions.setdefault(category, []).append(contribution)
	ordered = sorted(contributions, key=list(Category).index)
	return Classification(
		amounts=MappingProxyType({c: CategoryAmount(c, tuple(contributions[c])) for c in ordered}),
		unclassified=_with_balance(balances, _unclassified(mapping)),
		watched=_with_balance(balances, mapping.watched_at(WatchLevel.BLOCKING)),
		hinted=_with_balance(balances, mapping.watched_at(WatchLevel.HINT)),
	)


def _category(rule: AccountRule, debit: Decimal, credit: Decimal) -> Category | None:
	"""The category the postings of a voucher on the account of the rule count in, if any."""
	if rule.category is not Category.TRADING_UNCLASSIFIED or rule.trading_class is None:
		return rule.category
	split = TRADING_CATEGORIES[rule.trading_class]
	if split is None or credit == debit:
		return None
	gain, loss = split
	return gain if credit > debit else loss


def _unclassified(mapping: Mapping) -> frozenset[str]:
	return frozenset(
		rule.account_number
		for rule in mapping.rules
		if rule.category is Category.TRADING_UNCLASSIFIED and rule.trading_class is None
	)


def _with_balance(balances: dict[str, list[Decimal]], accounts: frozenset[str]) -> tuple[AccountBalance, ...]:
	return tuple(
		AccountBalance(account, debit, credit)
		for account, (debit, credit) in sorted(balances.items())
		if account in accounts and debit != credit
	)


def _sequence(value: Iterable, message: str) -> tuple:
	if isinstance(value, str):
		raise MappingError(message)
	return tuple(value)
