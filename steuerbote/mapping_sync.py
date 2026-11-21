"""The rows of the DocType VAT Return Mapping and the core Mapping, converted without Frappe.

The DocType keeps a company's Kontenzuordnung as table rows: rules (account, Kennzahl, side, rate and an
additional Kennzahl), checks (account numbers as text) and watched accounts with their level. The core works
with Mapping, AccountRule, TaxCheck and WatchedAccount. rows_to_mapping turns the rows into a Mapping, and
defaults_for_accounts turns the default mapping of a chart into rows for the accounts a company has. Both
take and return plain dicts with the DocType's field names, so the controller stays thin and this module is
tested without a bench.

A row holds what Frappe stores: an empty Float field is 0, an empty Data or Select field is "" or None,
and a rule's account number is the one fetched from its account. The DocType's own validate runs before
Frappe checks the mandatory fields, so a row can still lack a value here.
"""

import re
from collections.abc import Iterable, Set
from collections.abc import Mapping as ReadOnlyMapping
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, NamedTuple

from steuerbote.ustva import (
	AccountRule,
	Mapping,
	MappingError,
	Side,
	TaxCheck,
	WatchedAccount,
	WatchLevel,
	default_mapping,
)

Row = ReadOnlyMapping[str, Any]

# The DocType asks for account numbers separated by commas; blanks and line breaks separate them as well,
# since a number never contains either.
_ACCOUNT_SEPARATORS = re.compile(r"[\s,]+")


class DefaultRows(NamedTuple):
	"""The rows of a default mapping for a company's accounts, and the default accounts it lacks."""

	rule_rows: list[dict[str, Any]]
	check_rows: list[dict[str, Any]]
	watched_rows: list[dict[str, Any]]
	missing: list[str]


def rows_to_mapping(
	chart: str,
	rule_rows: Iterable[Row],
	check_rows: Iterable[Row],
	watched_rows: Iterable[Row],
	year: int,
) -> Mapping:
	"""The core Mapping of the rows, validated against the form of ``year``; raises MappingError."""
	return Mapping(
		chart=chart,
		rules=tuple(_rule(row) for row in rule_rows),
		checks=tuple(_check(row) for row in check_rows),
		watched=tuple(_watched(row) for row in watched_rows),
		year=year,
	)


def defaults_for_accounts(
	chart: str,
	year: int,
	existing_numbers: Set[str],
	levels: ReadOnlyMapping[str, str | None] = MappingProxyType({}),
) -> DefaultRows:
	"""The default mapping of ``chart`` reduced to the account numbers a company has, as rows.

	A rule or a watched account stays when its account exists. A watched account keeps the level the
	company gave it, ``levels`` by account number, and takes the level of the defaults otherwise. A check
	keeps the base and tax accounts that exist and is dropped when no base or no tax account remains, since
	it would compare nothing. ``missing`` lists, sorted, the accounts of the defaults that do not exist; it
	informs and changes nothing.
	"""
	mapping = default_mapping(chart, year)
	return DefaultRows(
		rule_rows=[_rule_row(rule) for rule in mapping.rules if rule.account_number in existing_numbers],
		check_rows=[
			row for check in mapping.checks if (row := _check_row(check, existing_numbers)) is not None
		],
		watched_rows=[
			{
				"account_number": watched.account_number,
				"level": levels.get(watched.account_number) or watched.level.value,
			}
			for watched in mapping.watched
			if watched.account_number in existing_numbers
		],
		missing=sorted(_accounts_of(mapping).difference(existing_numbers)),
	)


def _rule(row: Row) -> AccountRule:
	number = _account_number(row, "rule")
	where = f"account {number}"
	kennzahl = _text(row.get("kennzahl"))
	if not kennzahl:
		raise MappingError(f"{where}: no Kennzahl")
	also_side = row.get("also_side")
	return AccountRule(
		account_number=number,
		kennzahl=kennzahl,
		side=_side(row.get("side"), where),
		tax_rate=_tax_rate(row.get("tax_rate"), where),
		also_kennzahl=_text(row.get("also_kennzahl")) or None,
		also_side=_side(also_side, where) if also_side else None,
	)


def _watched(row: Row) -> WatchedAccount:
	number = _account_number(row, "watched account")
	return WatchedAccount(number, _level(row.get("level"), f"account {number}"))


def _level(value: Any, where: str) -> WatchLevel:
	"""An empty level blocks, like the default of the DocType."""
	if not value:
		return WatchLevel.BLOCKING
	try:
		return WatchLevel(value)
	except ValueError:
		raise MappingError(f"{where}: level must be blocking or hint, not {value!r}") from None


def _check(row: Row) -> TaxCheck:
	label = _text(row.get("label"))
	return TaxCheck(
		label=label,
		base_accounts=_account_numbers(row.get("base_accounts")),
		tax_accounts=_account_numbers(row.get("tax_accounts")),
		side=_side(row.get("side") or Side.CREDIT, f"check {label!r}"),
	)


def _account_number(row: Row, kind: str) -> str:
	"""The account number as fetched, compared as written like every account number of the core."""
	if number := row.get("account_number"):
		return number
	if account := row.get("account"):
		raise MappingError(f"account {account} has no account number")
	in_row = f" in row {idx}" if (idx := row.get("idx")) else ""
	raise MappingError(f"{kind}{in_row} has no account")


def _account_numbers(text: Any) -> tuple[str, ...]:
	return tuple(number for number in _ACCOUNT_SEPARATORS.split(_text(text)) if number)


def _side(value: Any, where: str) -> Side:
	try:
		return Side(value)
	except ValueError:
		raise MappingError(f"{where}: side must be credit or debit, not {value!r}") from None


def _tax_rate(value: Any, where: str) -> Decimal | None:
	"""An empty Float field holds 0, and the core takes no rate of 0 %, so 0 means no rate."""
	if value is None or value == "":
		return None
	try:
		rate = Decimal(str(value))
	except InvalidOperation:
		raise MappingError(f"{where}: tax rate {value!r} is not a number") from None
	return None if rate.is_zero() else rate


def _text(value: Any) -> str:
	return "" if value is None else str(value).strip()


def _rule_row(rule: AccountRule) -> dict[str, Any]:
	return {
		"account_number": rule.account_number,
		"kennzahl": rule.kennzahl,
		"side": rule.side.value,
		"tax_rate": rule.tax_rate,
		"also_kennzahl": rule.also_kennzahl,
		"also_side": rule.also_side.value if rule.also_side else None,
	}


def _check_row(check: TaxCheck, existing_numbers: Set[str]) -> dict[str, Any] | None:
	base_accounts = [number for number in check.base_accounts if number in existing_numbers]
	tax_accounts = [number for number in check.tax_accounts if number in existing_numbers]
	if not base_accounts or not tax_accounts:
		return None
	return {
		"label": check.label,
		"base_accounts": ", ".join(base_accounts),
		"tax_accounts": ", ".join(tax_accounts),
		"side": check.side.value,
	}


def _accounts_of(mapping: Mapping) -> set[str]:
	"""Every account of a mapping; the base accounts of its checks are always among its rules."""
	return {
		*(rule.account_number for rule in mapping.rules),
		*(number for check in mapping.checks for number in check.tax_accounts),
		*(watched.account_number for watched in mapping.watched),
	}
