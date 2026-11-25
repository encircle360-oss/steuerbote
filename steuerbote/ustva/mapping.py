"""Which ledger accounts feed which Kennzahl.

A Mapping belongs to one chart of accounts (SKR03, SKR04 or a company's own numbering) and one
year of the form, and is plain data. An AccountRule says which Kennzahl an account feeds and on which
side the account carries its balance. A base whose tax the form reports in its own Kennzahl (for
example 46 and 47) gets that tax in one of two ways: every rule of the base carries a tax rate, so the
tax is derived from the base accounts and the tax accounts are only checked, or no rule does and a tax
account is mapped to the tax Kennzahl directly. A rule may report its balance to a second,
informational Kennzahl as well, one that does not change the amount owed, such as Kz 50. A watched
account belongs, or may belong, to the Voranmeldung without a Kennzahl yet: at the blocking level a
balance on it holds the return, at the hint level it only adds a hint. A Verprobung of a purchase whose tax the
company owes itself may name the Kennzahl that takes the base of a voucher booking its tax on none of its base
accounts (``derived_base``, see calculation.py), and another one for a voucher of a supplier established in another
member state (``derived_base_eu``, see residence.py). The defaults for the DATEV charts live in defaults.py; a company
adjusts them in its settings. ``for_year`` re-validates the same
rules against another year's form.
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum

from steuerbote.ustva.kennzahlen import BALANCE_KENNZAHL, LATEST_YEAR, Effect, Kennzahl, catalogue_for
from steuerbote.ustva.rounding import HUNDRED, ZERO, require_decimal


class MappingError(ValueError):
	pass


class Side(Enum):
	"""On which side an account carries its balance."""

	CREDIT = "credit"
	DEBIT = "debit"


def is_account_number(value: object) -> bool:
	"""Account numbers are compared as written, so one with surrounding blanks would never match."""
	return isinstance(value, str) and bool(value) and value == value.strip()


def _accounts(value: Iterable[str], what: str) -> tuple[str, ...]:
	if isinstance(value, str):
		raise MappingError(f"{what} must be a sequence of account numbers, not a string")
	accounts = tuple(value)
	for account in accounts:
		if not is_account_number(account):
			raise MappingError(f"{what}: {account!r} is not an account number")
	return accounts


@dataclass(frozen=True, slots=True)
class AccountRule:
	"""An account feeding a Kennzahl; ``tax_rate`` is a percentage as the form prints it, such as 19.

	``also_kennzahl`` reports the balance on ``also_side`` to a second, informational Kennzahl. For a
	receivable that became uncollectible, the Anleitung to line 51 (USt 1 E 2026) says „tragen Sie die
	Minderung der Bemessungsgrundlage bitte zusätzlich in Zeile 51 ein“: a bad-debt account feeds Kz 81
	on the credit side and Kz 50 on the debit side.
	"""

	account_number: str
	kennzahl: str
	side: Side
	tax_rate: Decimal | None = None
	also_kennzahl: str | None = None
	also_side: Side | None = None

	def __post_init__(self) -> None:
		if not is_account_number(self.account_number):
			raise MappingError(f"{self.account_number!r} is not an account number")
		object.__setattr__(self, "side", Side(self.side))
		if self.tax_rate is not None and not _is_percentage(require_decimal(self.tax_rate)):
			raise MappingError(
				f"account {self.account_number}: tax rate {self.tax_rate} is not a percentage "
				"above 0 and below 100"
			)
		if (self.also_kennzahl is None) != (self.also_side is None):
			raise MappingError(f"account {self.account_number}: also_kennzahl and also_side go together")
		if self.also_side is not None:
			object.__setattr__(self, "also_side", Side(self.also_side))


def _is_percentage(rate: Decimal) -> bool:
	return rate.is_finite() and ZERO < rate < HUNDRED


class WatchLevel(Enum):
	"""What a balance on a watched account does to the return."""

	BLOCKING = "blocking"
	HINT = "hint"


@dataclass(frozen=True, slots=True)
class WatchedAccount:
	"""An account of the Voranmeldung whose Kennzahl is not decided.

	At the blocking level a balance on it holds the return until the account is mapped. At the hint level
	a balance only adds a hint to the return: for an account whose balance belongs in the Voranmeldung in
	some cases only, which the company settles with its Steuerberatung.
	"""

	account_number: str
	level: WatchLevel = WatchLevel.BLOCKING

	def __post_init__(self) -> None:
		if not is_account_number(self.account_number):
			raise MappingError(f"watched: {self.account_number!r} is not an account number")
		object.__setattr__(self, "level", WatchLevel(self.level))


def _watched(value: Iterable[str | WatchedAccount]) -> tuple[WatchedAccount, ...]:
	"""Watched accounts as given; a bare account number is watched at the blocking level."""
	if isinstance(value, str):
		raise MappingError("watched must be a sequence of account numbers, not a string")
	return tuple(item if isinstance(item, WatchedAccount) else WatchedAccount(item) for item in value)


# The bases of sections C and D of form USt 1 A 2026 (lines 24 to 32) that carry a tax: the innergemeinschaftliche
# Erwerbe (Kz 89, 93, 95 and 94) and the Leistungen whose recipient owes the tax (§ 13b Absatz 5 UStG; Kz 46, 73 and
# 84). The company owes this tax on a purchase and deducts it again as Vorsteuer (§ 15 Absatz 1 Satz 1 Nummer 3 and 4
# UStG), so its books carry the base on whatever account the purchase goes to, an expense, an asset or goods, and the
# tax on the tax accounts of the Verprobung. Kz 90 and 91 carry no tax to derive a base from, and turnover always has a
# revenue account of its own.
DERIVED_BASE_KENNZAHLEN = frozenset({"89", "93", "95", "94", "46", "73", "84"})
# Sections C and D of the form: the purchases whose tax the company owes.
PURCHASE_LINES = range(24, 33)
# Section C of the form: the innergemeinschaftliche Erwerbe (lines 24 to 29).
ACQUISITION_LINES = range(24, 30)


@dataclass(frozen=True, slots=True)
class TaxCheck:
	"""Verprobung: the tax booked on tax_accounts against the tax that belongs to base_accounts.

	``derived_base`` names the Kennzahl that takes the base of a voucher which books tax on the tax accounts but
	nothing on the base accounts, one of DERIVED_BASE_KENNZAHLEN; None leaves such a voucher a deviation.
	``derived_base_eu`` names the Kennzahl that takes that base instead when the voucher is a sonstige Leistung of
	§ 3a Absatz 2 UStG of a business established in another member state (§ 13b Absatz 1 UStG, residence.py); it
	needs a ``derived_base`` for every other voucher.
	"""

	label: str
	base_accounts: tuple[str, ...]
	tax_accounts: tuple[str, ...]
	side: Side = Side.CREDIT
	derived_base: str | None = None
	derived_base_eu: str | None = None

	def __post_init__(self) -> None:
		object.__setattr__(self, "base_accounts", _accounts(self.base_accounts, f"check {self.label!r}"))
		object.__setattr__(self, "tax_accounts", _accounts(self.tax_accounts, f"check {self.label!r}"))
		object.__setattr__(self, "side", Side(self.side))
		for name in ("derived_base", "derived_base_eu"):
			value = getattr(self, name)
			if value is not None and not (isinstance(value, str) and value):
				raise MappingError(f"check {self.label!r}: {name} must be a Kennzahl or None, not {value!r}")
		if self.derived_base_eu is not None and self.derived_base is None:
			raise MappingError(
				f"check {self.label!r}: derived_base_eu needs a derived_base for the vouchers of other suppliers"
			)


@dataclass(frozen=True, slots=True)
class Mapping:
	chart: str
	rules: tuple[AccountRule, ...]
	checks: tuple[TaxCheck, ...] = ()
	watched: tuple[WatchedAccount, ...] = ()
	year: int = LATEST_YEAR

	def __post_init__(self) -> None:
		object.__setattr__(self, "rules", tuple(self.rules))
		object.__setattr__(self, "checks", tuple(self.checks))
		object.__setattr__(self, "watched", _watched(self.watched))
		self.validate()

	@property
	def catalogue(self) -> ReadOnlyMapping[str, Kennzahl]:
		return catalogue_for(self.year)

	def for_year(self, year: int) -> Mapping:
		"""The same rules, validated against the form of another year."""
		return replace(self, year=year)

	def validate(self) -> None:
		self._validate_year()
		catalogue_for(self.year)
		self._validate_rules()
		self._validate_reported_taxes()
		self._validate_checks()
		self._validate_watched()

	def watched_at(self, level: WatchLevel) -> tuple[str, ...]:
		"""The numbers of the accounts watched at ``level``, in the order of the mapping."""
		return tuple(watched.account_number for watched in self.watched if watched.level is level)

	def has_place(self, account_number: str) -> bool:
		"""Whether a rule maps the account, a Verprobung checks it as a tax account or the mapping watches it.

		An account without any of these places enters no Kennzahl and holds nothing: its balance drops out of
		the Voranmeldung unseen (calculation.py).
		"""
		return (
			self.rule_for(account_number) is not None
			or any(account_number in check.tax_accounts for check in self.checks)
			or any(watched.account_number == account_number for watched in self.watched)
		)

	def rule_for(self, account_number: str) -> AccountRule | None:
		for rule in self.rules:
			if rule.account_number == account_number:
				return rule
		return None

	def rate_for(self, rule: AccountRule) -> Decimal:
		"""The rate that turns a base account's balance into tax."""
		if rule.tax_rate is not None:
			return rule.tax_rate
		kennzahl = self.catalogue[rule.kennzahl]
		if kennzahl.rate is None:
			raise MappingError(
				f"account {rule.account_number}: Kennzahl {kennzahl.number} carries no tax rate"
			)
		return kennzahl.rate

	def derived_rate(self, check: TaxCheck) -> Decimal:
		"""The rate of the base a check derives: the one rate of its base accounts."""
		rates = {self.rate_for(self._rule_of(account)) for account in self._deriving(check).base_accounts}
		return rates.pop()

	def base_side(self, check: TaxCheck) -> Side:
		"""The side the base accounts of a check that derives a base carry their balance on."""
		return self._rule_of(self._deriving(check).base_accounts[0]).side

	def is_purchase(self, check: TaxCheck) -> bool:
		"""Whether every base account of the check feeds a purchase whose tax the company owes (sections C and D)."""
		return self._in_lines(check, PURCHASE_LINES)

	def is_acquisition(self, check: TaxCheck) -> bool:
		"""Whether every base account of the check feeds an innergemeinschaftlicher Erwerb (section C)."""
		return self._in_lines(check, ACQUISITION_LINES)

	def _in_lines(self, check: TaxCheck, lines: range) -> bool:
		catalogue = self.catalogue
		return all(
			catalogue[self._rule_of(account).kennzahl].line in lines for account in check.base_accounts
		)

	def _deriving(self, check: TaxCheck) -> TaxCheck:
		if check.derived_base is None:
			raise MappingError(f"check {check.label!r} derives no base")
		return check

	def _rule_of(self, account_number: str) -> AccountRule:
		"""The rule of a base account of a check, which _validate_checks requires before it asks for one."""
		return next(rule for rule in self.rules if rule.account_number == account_number)

	def _validate_derived_base(self, check: TaxCheck, where: str, number: str) -> None:
		"""The base a check derives needs one rate and one side, those of its base accounts, and a Kennzahl that takes
		it: a purchase of DERIVED_BASE_KENNZAHLEN, at its statutory rate if it has one, whose tax is derived rather
		than mapped from an account, which would report the tax a second time. The base accounts themselves must be
		purchases too, so that a Verprobung of turnover never derives one."""
		catalogue = self.catalogue
		if number not in DERIVED_BASE_KENNZAHLEN or number not in catalogue:
			raise MappingError(f"{where}: Kennzahl {number} takes no base derived from the tax of a voucher")
		rules = [self._rule_of(account) for account in check.base_accounts]
		for rule in rules:
			if catalogue[rule.kennzahl].line not in PURCHASE_LINES:
				raise MappingError(
					f"{where}: base account {rule.account_number} feeds Kennzahl {rule.kennzahl}, which is no "
					"purchase whose tax the company owes"
				)
		rates = {self.rate_for(rule) for rule in rules}
		if len(rates) > 1:
			raise MappingError(f"{where}: its base accounts carry two rates, so no base can be derived")
		if len({rule.side for rule in rules}) > 1:
			raise MappingError(f"{where}: its base accounts carry their balance on two sides")
		kennzahl = catalogue[number]
		(rate,) = rates
		if kennzahl.rate is not None and kennzahl.rate != rate:
			raise MappingError(
				f"{where}: Kennzahl {number} carries {kennzahl.rate} %, the base accounts of the check {rate} %"
			)
		mapped = [rule.account_number for rule in self.rules if rule.kennzahl == kennzahl.tax_kennzahl]
		if mapped:
			raise MappingError(
				f"{where}: Kennzahl {kennzahl.tax_kennzahl} is mapped from account {mapped[0]}, so Kennzahl "
				f"{number} takes no derived base"
			)

	def _validate_year(self) -> None:
		"""2026.0 and Decimal("2026") would find the 2026 catalogue by hash, and True is an int to Python."""
		if isinstance(self.year, bool) or not isinstance(self.year, int):
			raise TypeError(f"year must be an int, not {type(self.year).__name__}")

	def _validate_rules(self) -> None:
		seen: set[str] = set()
		for rule in self.rules:
			where = f"account {rule.account_number}"
			kennzahl = self._amount_kennzahl(rule.kennzahl, where)
			if rule.account_number in seen:
				raise MappingError(f"{where} is mapped twice")
			seen.add(rule.account_number)
			if rule.tax_rate is not None and kennzahl.tax_kennzahl is None:
				raise MappingError(f"{where}: Kennzahl {kennzahl.number} takes no tax rate")
			if rule.also_kennzahl is not None:
				self._validate_also_kennzahl(rule, where)

	def _validate_also_kennzahl(self, rule: AccountRule, where: str) -> None:
		"""The second Kennzahl only informs, so it must not change the amount owed nor need a tax.

		Its own Kennzahl again would count the balance twice, and a base with a tax Kennzahl of its own
		would appear without its tax.
		"""
		also = self._amount_kennzahl(rule.also_kennzahl, where)
		if also.number == rule.kennzahl:
			raise MappingError(f"{where}: also_kennzahl {also.number} is the rule's own Kennzahl")
		if also.effect is not Effect.NONE:
			raise MappingError(
				f"{where}: Kennzahl {also.number} changes the amount owed and cannot be an also_kennzahl"
			)
		if also.tax_kennzahl is not None:
			raise MappingError(
				f"{where}: Kennzahl {also.number} has a tax Kennzahl of its own and cannot be an "
				"also_kennzahl"
			)

	def _validate_reported_taxes(self) -> None:
		"""A base with a tax Kennzahl of its own feeds it from rates on all its rules or from a tax account.

		The form does not compute the tax of these bases, so a base whose tax comes from nowhere would
		leave the tax out of the filing, rates on only some of its rules would leave out the tax of the
		others, and a tax account mapped next to rated rules would report the same tax twice.
		"""
		catalogue = self.catalogue
		bases = dict.fromkeys(r.kennzahl for r in self.rules if catalogue[r.kennzahl].tax_kennzahl)
		for base in bases:
			tax = catalogue[base].tax_kennzahl
			rated = [r.account_number for r in self.rules if r.kennzahl == base and r.tax_rate is not None]
			unrated = [r.account_number for r in self.rules if r.kennzahl == base and r.tax_rate is None]
			mapped = [r.account_number for r in self.rules if r.kennzahl == tax]
			if rated and unrated:
				raise MappingError(
					f"Kennzahl {base}: mix of rated and unrated rules (without rate: {', '.join(unrated)})"
				)
			if rated and mapped:
				raise MappingError(
					f"Kennzahl {tax} is derived from account {rated[0]} and mapped from account {mapped[0]}"
				)
			if not rated and not mapped:
				raise MappingError(
					f"Kennzahl {tax} is fed by nothing: give the rules of Kennzahl {base} a tax rate "
					f"or map a tax account to {tax}"
				)

	def _validate_checks(self) -> None:
		"""A check's tax accounts are checked, never mapped, and every account is checked once.

		The bases of a check always carry a rate, so the form or the rule already derives the tax those
		accounts hold; mapping them as well would report that tax a second time. A base account listed
		twice would count its tax twice against the booked tax.
		"""
		seen_base_accounts: set[str] = set()
		seen_tax_accounts: set[str] = set()
		for check in self.checks:
			where = f"check {check.label!r}"
			if not check.label:
				raise MappingError("a tax check needs a label")
			if not check.base_accounts or not check.tax_accounts:
				raise MappingError(f"{where} needs base accounts and tax accounts")
			for account in check.base_accounts:
				if account in seen_base_accounts:
					raise MappingError(f"base account {account} is checked twice")
				seen_base_accounts.add(account)
				rule = self.rule_for(account)
				if rule is None:
					raise MappingError(f"{where}: account {account} is not mapped")
				self.rate_for(rule)
			for account in check.tax_accounts:
				if account in seen_tax_accounts:
					raise MappingError(f"tax account {account} is checked twice")
				seen_tax_accounts.add(account)
				rule = self.rule_for(account)
				if rule is not None:
					raise MappingError(
						f"{where}: tax account {account} is also mapped to Kennzahl {rule.kennzahl}"
					)
			for number in dict.fromkeys((check.derived_base, check.derived_base_eu)):
				if number is not None:
					self._validate_derived_base(check, where, number)

	def _validate_watched(self) -> None:
		"""An account watched twice would have two levels, or count its balance twice."""
		checked = {account for check in self.checks for account in check.tax_accounts}
		seen: set[str] = set()
		for watched in self.watched:
			account = watched.account_number
			if account in seen:
				raise MappingError(f"account {account} is watched twice")
			seen.add(account)
			if self.rule_for(account) is not None or account in checked:
				raise MappingError(f"account {account} is watched but also mapped or checked")

	def _amount_kennzahl(self, number: str, where: str) -> Kennzahl:
		kennzahl = self._kennzahl(number, where)
		if not kennzahl.holds_amount:
			raise MappingError(f"{where}: Kennzahl {kennzahl.number} holds no amount")
		if kennzahl.number == BALANCE_KENNZAHL:
			raise MappingError(f"{where}: Kennzahl {BALANCE_KENNZAHL} is computed, not mapped")
		return kennzahl

	def _kennzahl(self, number: str, where: str) -> Kennzahl:
		try:
			return self.catalogue[number]
		except KeyError:
			raise MappingError(f"{where}: unknown Kennzahl {number}") from None
