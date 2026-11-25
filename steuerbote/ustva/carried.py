"""The balance a watched timing account carries into a period, and the period that releases it.

Two watched accounts of each chart hold amounts on their way into a later Voranmeldung (TIMING_ACCOUNTS of
steuerbote/ustva/defaults.py): „Vorsteuer in Folgeperiode/im Folgejahr abziehbar“ the input tax of an invoice that
is deductible only once the supply is made or the invoice is there (§ 15 Absatz 1 Satz 1 Nummer 1 UStG, UStAE 15.2
Absatz 2 Satz 6), and „Umsatzsteuer nicht fällig“ the output tax that arises in a later period. A balance on such an
account goes into no Kennzahl, so a movement on it blocks the Voranmeldung until someone looked at it.

A period that moves the balance the account carries into it, out of it, is the bridge itself: the amount goes into the
Kennzahl of the account it moves to, and the release blocks nothing. That happens every January to the amounts of a
December, and to the opening balances of a company that starts with Steuerbote in the middle of its life, whose
earlier books never were in Steuerbote (steuerbote/setup/start.py). releases() finds such periods: on a timing account
that blocks, the movement of the period runs against the balance carried in and is not larger. Any other movement, a
new balance or more than was carried, still blocks.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Collection, Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from decimal import Decimal

from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.plausibility import Code, Figures, Hint
from steuerbote.ustva.rounding import ZERO


@dataclass(frozen=True, slots=True)
class Release:
	"""A timing account that releases in the period what it carried in: ``carried`` is the balance carried in and
	``released`` the movement of the period, both debit less credit, of opposite signs."""

	account_number: str
	carried: Decimal
	released: Decimal


def movements(lines: Iterable[LedgerLine]) -> dict[str, Decimal]:
	"""Debit less credit of each account over the lines."""
	found: dict[str, Decimal] = {}
	for entry in lines:
		found[entry.account_number] = found.get(entry.account_number, ZERO) + entry.debit - entry.credit
	return found


def carried_balances(
	closing: ReadOnlyMapping[str, Decimal], lines: Iterable[LedgerLine]
) -> dict[str, Decimal]:
	"""The balance each account of ``closing`` carries into the period: its balance at the end of the period, from
	every entry up to then, the opening entries and the entries left out of the Voranmeldung among them, less the
	movement of the lines of the period."""
	moved = movements(lines)
	return {account: balance - moved.get(account, ZERO) for account, balance in closing.items()}


def releases(
	blocked: Iterable[str],
	lines: Iterable[LedgerLine],
	carried: ReadOnlyMapping[str, Decimal],
	timing: Collection[str],
) -> tuple[Release, ...]:
	"""The blocked timing accounts whose movement in the period releases part or all of the balance they carried in."""
	moved = movements(lines)
	found = []
	for account in blocked:
		before = carried.get(account, ZERO)
		movement = moved.get(account, ZERO)
		against = before and movement and (movement > ZERO) != (before > ZERO)
		if account in timing and against and abs(movement) <= abs(before):
			found.append(Release(account, before, movement))
	return tuple(found)


def still_blocked(blocked: Iterable[str], found: Iterable[Release]) -> tuple[str, ...]:
	"""The blocked accounts without those that release what they carried in."""
	released = {release.account_number for release in found}
	return tuple(account for account in blocked if account not in released)


def release_hints(found: Iterable[Release], names: ReadOnlyMapping[str, str], figures: Figures) -> list[Hint]:
	"""A hint per release: the account, what it releases and the balance it carried in."""
	hints = []
	for release in found:
		name = names.get(release.account_number)
		account = f"Konto {release.account_number} {name}" if name else f"Konto {release.account_number}"
		side = "Soll" if release.carried > ZERO else "Haben"
		text = (
			f"{account} löst {figures.money(abs(release.released))} des Saldos auf, den es aus der Zeit davor trägt "
			f"({figures.money(abs(release.carried))} im {side}). Ein solcher Übergang in eine spätere Voranmeldung "
			"hält sie nicht an; die Steuer steht in der Kennzahl des Gegenkontos."
		)
		hints.append(Hint(Code.WATCHED_ACCOUNT, text))
	return hints
