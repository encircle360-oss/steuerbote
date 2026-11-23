"""The accounts the tax templates of a company name, against the Kontenzuordnung.

ERPNext books the tax of an invoice on the accounts of its tax templates. The Voranmeldung carries „die Steuer für
den Voranmeldungszeitraum“ (§ 18 Absatz 1 Satz 1 UStG), but an account that the mapping neither maps, nor checks as
a tax account of a Verprobung, nor watches enters no Kennzahl and holds nothing (Mapping.has_place): what a template
books there drops out of the return unseen. The defaults leave some accounts without Kennzahl on purpose, such as the
Umsatzsteuer of the OSS procedure, which the company declares in the Steuererklärung of the besonderes
Besteuerungsverfahren instead (§ 18j Absatz 4 UStG); defaults.deliberately_without_kennzahl lists them, and they are
not reported. An account without number has no place at all, since the mapping works with account numbers.

Berechnen gives a hint for each account without place, naming its templates and its balance in the period. A hint
never holds the return.
"""

from collections.abc import Collection, Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from decimal import Decimal

from steuerbote.ustva.calculation import AccountBalance, LedgerLine
from steuerbote.ustva.mapping import Mapping, is_account_number
from steuerbote.ustva.plausibility import Code, Figures, Hint
from steuerbote.ustva.rounding import ZERO


@dataclass(frozen=True, slots=True)
class TemplateAccount:
	"""An account that tax templates of a company name, and those templates.

	``account`` is the name of the account in ERPNext and ``account_name`` the name the texts give it;
	``account_number`` is None for an account without number, which no rule can map.
	"""

	account: str
	account_number: str | None
	account_name: str
	templates: tuple[str, ...]

	def __post_init__(self) -> None:
		if not self.account:
			raise ValueError("a template account names no account")
		if self.account_number is not None and not is_account_number(self.account_number):
			raise ValueError(f"{self.account_number!r} is not an account number")
		object.__setattr__(self, "templates", tuple(self.templates))
		if not self.templates:
			raise ValueError(f"{self.account} is named by no template")


def without_place(
	accounts: Iterable[TemplateAccount],
	mapping: Mapping,
	deliberately_without_kennzahl: Collection[str] = frozenset(),
) -> tuple[TemplateAccount, ...]:
	"""The accounts that have no place in the mapping, in the order given.

	An account the defaults leave without Kennzahl on purpose, one of ``deliberately_without_kennzahl``, is left
	out; an account without number never has a place.
	"""
	return tuple(
		account
		for account in accounts
		if account.account_number is None
		or not (
			mapping.has_place(account.account_number)
			or account.account_number in deliberately_without_kennzahl
		)
	)


def balances(lines: Iterable[LedgerLine], account_numbers: Collection[str]) -> dict[str, AccountBalance]:
	"""The debits and credits of the period on the accounts asked for, by account number.

	An account without a posting in the lines has no entry.
	"""
	debits: dict[str, Decimal] = {}
	credits: dict[str, Decimal] = {}
	for line in lines:
		if line.account_number in account_numbers:
			debits[line.account_number] = debits.get(line.account_number, ZERO) + line.debit
			credits[line.account_number] = credits.get(line.account_number, ZERO) + line.credit
	return {number: AccountBalance(number, debits[number], credits[number]) for number in debits}


def hints(
	unplaced: Iterable[TemplateAccount], balances: ReadOnlyMapping[str, AccountBalance], figures: Figures
) -> list[Hint]:
	"""A hint per account without place, in the order given: the account, its templates and its balance.

	``balances`` holds the debits and credits of the period by account number; an account it lacks has no
	balance. An account without number gets a hint of its own, since no rule can map it.
	"""
	return [_hint(account, balances, figures) for account in unplaced]


def _hint(account: TemplateAccount, balances: ReadOnlyMapping[str, AccountBalance], figures: Figures) -> Hint:
	templates = _templates(account.templates)
	if account.account_number is None:
		text = (
			f"Konto {account.account_name} aus {templates} hat keine Kontonummer, deshalb kann keine Regel der "
			"Kontenzuordnung es zuordnen."
		)
		return Hint(Code.TAX_TEMPLATE_WITHOUT_PLACE, text)
	subject = (
		f"Konto {account.account_number} {account.account_name} aus {templates} hat keinen Platz in der "
		"Kontenzuordnung"
	)
	balance = balances.get(account.account_number)
	if balance is None or not balance.balance:
		return Hint(Code.TAX_TEMPLATE_WITHOUT_PLACE, f"{subject}; im Zeitraum hat es keinen Saldo.")
	side = "Soll" if balance.balance > ZERO else "Haben"
	totals = f"Soll {figures.money(balance.debit)}, Haben {figures.money(balance.credit)}"
	text = (
		f"{subject} und im Zeitraum einen Saldo von {figures.money(abs(balance.balance))} im {side} ({totals}), "
		"der in keine Kennzahl eingeht."
	)
	return Hint(Code.TAX_TEMPLATE_WITHOUT_PLACE, text)


def _templates(names: tuple[str, ...]) -> str:
	quoted = [f"„{name}“" for name in names]
	if len(quoted) == 1:
		return f"der Steuervorlage {quoted[0]}"
	return f"den Steuervorlagen {', '.join(quoted[:-1])} und {quoted[-1]}"
