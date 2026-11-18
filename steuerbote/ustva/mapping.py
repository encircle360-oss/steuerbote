"""Which ledger accounts feed which Kennzahl.

A Mapping belongs to one chart of accounts (SKR03, SKR04 or a company's own numbering) and one
year of the form, and is plain data. An AccountRule says which Kennzahl an account feeds and on which
side the account carries its balance. A base whose tax the form reports in its own Kennzahl (for
example 46 and 47) gets that tax in one of two ways: every rule of the base carries a tax rate, so the
tax is derived from the base accounts and the tax accounts are only checked, or no rule does and a tax
account is mapped to the tax Kennzahl directly. A rule may report its balance to a second,
informational Kennzahl as well, one that does not change the amount owed, such as Kz 50. The defaults
for the DATEV charts live in defaults.py; a company adjusts them in its settings. ``for_year``
re-validates the same rules against another year's form.
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


@dataclass(frozen=True, slots=True)
class TaxCheck:
	"""Verprobung: the tax booked on tax_accounts against the tax that belongs to base_accounts."""

	label: str
	base_accounts: tuple[str, ...]
	tax_accounts: tuple[str, ...]
	side: Side = Side.CREDIT

	def __post_init__(self) -> None:
		object.__setattr__(self, "base_accounts", _accounts(self.base_accounts, f"check {self.label!r}"))
		object.__setattr__(self, "tax_accounts", _accounts(self.tax_accounts, f"check {self.label!r}"))
		object.__setattr__(self, "side", Side(self.side))


@dataclass(frozen=True, slots=True)
class Mapping:
	chart: str
	rules: tuple[AccountRule, ...]
	checks: tuple[TaxCheck, ...] = ()
	watched: tuple[str, ...] = ()
	year: int = LATEST_YEAR

	def __post_init__(self) -> None:
		object.__setattr__(self, "rules", tuple(self.rules))
		object.__setattr__(self, "checks", tuple(self.checks))
		object.__setattr__(self, "watched", _accounts(self.watched, "watched"))
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

	def _validate_watched(self) -> None:
		checked = {account for check in self.checks for account in check.tax_accounts}
		for account in self.watched:
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
