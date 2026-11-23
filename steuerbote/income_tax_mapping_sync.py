"""The rows of the DocType Income Tax Mapping and the core Mapping of the Körperschaftsteuer, converted without Frappe.

The DocType keeps the Kontenzuordnung Ertragsteuern of a company as table rows: rules (account, category and, for a
trading account, its class) and watched accounts with their level. The core works with Mapping, AccountRule and
WatchedAccount of steuerbote.kst.categories. rows_to_mapping turns the rows into a Mapping, and defaults_for_accounts
turns the defaults of a chart (steuerbote.kst.defaults) into rows for the accounts a company has, with the DATEV
accounts of the defaults it lacks. Both take and return plain dicts with the field names of the DocType, so the
controller stays thin and this module is tested without a bench.

For Vorgaben aktualisieren and the file of a mapping, the rows are also items of steuerbote.mappings.diff, one per
account: ("account", number) with its place, rule or watched, and the category and the trading class of a rule or the
level of a watched account, each as its text. items_of_rows and rows_of_items turn rows into items and back,
default_items gives the defaults of a chart for a company as items, body_of_items and items_of_body turn items into
the plain data of the stored defaults and of the file and back, and file_body and items_of_file_body make the body of
the file of a mapping (steuerbote.mappings.transfer, format FILE_FORMAT), its rows with the defaults it took over.

A row holds what Frappe stores: an empty Select field is "" or None, and the account number of a row is the one
fetched from its account. The validate of the DocType runs before Frappe checks the mandatory fields, so a row can
still lack a value here.
"""

import json
from collections.abc import Iterable, Set
from collections.abc import Mapping as ReadOnlyMapping
from types import MappingProxyType
from typing import Any, NamedTuple

from steuerbote.kst.categories import AccountRule, Category, Mapping, TradingClass
from steuerbote.kst.defaults import default_accounts
from steuerbote.mappings.transfer import canonical_json
from steuerbote.ustva.mapping import MappingError, WatchedAccount, WatchLevel

Row = ReadOnlyMapping[str, Any]
Key = tuple[str, str]
Fields = dict[str, str | None]

# The format of the file of an Income Tax Mapping (steuerbote.mappings.transfer).
FILE_FORMAT = "steuerbote/income-tax-mapping"
# The kind of the items of an Income Tax Mapping, and the places an account takes in it.
ACCOUNT = "account"
RULE = "rule"
WATCHED = "watched"
RULE_FIELDS = ("category", "trading_class")
BODY_PARTS = {"rules": ("account_number", *RULE_FIELDS), "watched": ("account_number", "level")}


class MappingRows(NamedTuple):
	"""The rows of the two tables of a mapping, by account number."""

	rule_rows: list[dict[str, Any]]
	watched_rows: list[dict[str, Any]]


class MissingAccount(NamedTuple):
	"""An account of the defaults that the company does not have, with its DATEV label."""

	account_number: str
	label: str


class DefaultRows(NamedTuple):
	"""The rows of the default mapping for the accounts of a company, and the accounts of the defaults it lacks."""

	rule_rows: list[dict[str, Any]]
	watched_rows: list[dict[str, Any]]
	missing: list[MissingAccount]


def rows_to_mapping(chart: str, rule_rows: Iterable[Row], watched_rows: Iterable[Row]) -> Mapping:
	"""The core Mapping of the rows; raises MappingError."""
	return Mapping(
		chart=chart,
		rules=tuple(_rule(row) for row in rule_rows),
		watched=tuple(_watched(row) for row in watched_rows),
	)


def defaults_for_accounts(
	chart: str,
	existing_numbers: Set[str],
	levels: ReadOnlyMapping[str, str | None] = MappingProxyType({}),
) -> DefaultRows:
	"""The default mapping of ``chart`` reduced to the account numbers a company has, as rows.

	A rule or a watched account stays when its account exists. A watched account keeps the level the company gave it,
	``levels`` by account number, and takes the level of the defaults otherwise. ``missing`` lists, sorted by number,
	the accounts of the defaults that do not exist with their DATEV labels; it informs and changes nothing.
	"""
	rule_rows, watched_rows, missing = [], [], []
	for account in default_accounts(chart):
		if account.number not in existing_numbers:
			missing.append(MissingAccount(account.number, account.label))
		elif account.category is not None:
			rule_rows.append(_rule_row(AccountRule(account.number, account.category)))
		else:
			level = levels.get(account.number) or account.level.value
			watched_rows.append({"account_number": account.number, "level": level})
	return DefaultRows(rule_rows, watched_rows, sorted(missing))


def items_of_rows(rule_rows: Iterable[Row], watched_rows: Iterable[Row]) -> dict[Key, Fields]:
	"""The items of the rows: the accounts of the rules, then the watched accounts, each in the order of its table.
	Raises MappingError for a row the core cannot read and for an account that two rows name, since an item has one
	place."""
	items: dict[Key, Fields] = {}
	for row in rule_rows:
		rule = _rule(row)
		_put(items, (ACCOUNT, rule.account_number), _rule_fields(rule), "account {0} has more than one rule")
	for row in watched_rows:
		watched = _watched(row)
		key = (ACCOUNT, watched.account_number)
		twice = items.get(key, {}).get("place") == WATCHED
		_put(
			items,
			key,
			{"place": WATCHED, "level": watched.level.value},
			"account {0} is watched twice" if twice else "account {0} is mapped and watched",
		)
	return items


def items_of_mapping(mapping: Mapping) -> dict[Key, Fields]:
	"""The items of a core Mapping, as its rows would give them."""
	return items_of_rows(
		[_rule_row(rule) for rule in mapping.rules],
		[
			{"account_number": watched.account_number, "level": watched.level.value}
			for watched in mapping.watched
		],
	)


def default_items(chart: str, existing_numbers: Set[str]) -> dict[Key, Fields]:
	"""What Vorgaben laden takes over from the defaults of a chart for a company with these accounts, as items: the
	levels are those of the defaults, not those a company gave its watched accounts."""
	defaults = defaults_for_accounts(chart, existing_numbers)
	return items_of_rows(defaults.rule_rows, defaults.watched_rows)


def rows_of_items(items: ReadOnlyMapping[Key, ReadOnlyMapping[str, str | None]]) -> MappingRows:
	"""The rows of the items by account number, each table in the order of the items."""
	rules, watched = [], []
	for (_kind, number), fields in items.items():
		if fields["place"] == WATCHED:
			watched.append({"account_number": number, "level": fields["level"]})
		else:
			rules.append({"account_number": number, **{name: fields[name] for name in RULE_FIELDS}})
	return MappingRows(rules, watched)


def body_of_items(items: ReadOnlyMapping[Key, ReadOnlyMapping[str, str | None]]) -> dict[str, list[dict]]:
	"""The items as plain data, the form the stored defaults and the file of a mapping hold them in: rules and
	watched accounts with their fields as texts."""
	rows = rows_of_items(items)
	return {"rules": rows.rule_rows, "watched": rows.watched_rows}


def items_of_body(body: Any) -> dict[Key, Fields]:
	"""The items of plain data as body_of_items writes it; raises MappingError for data of another shape."""
	if not isinstance(body, dict) or set(body) != set(BODY_PARTS):
		raise MappingError(f"a mapping holds {', '.join(BODY_PARTS)}")
	for part, fields in BODY_PARTS.items():
		rows = body[part]
		if not isinstance(rows, list):
			raise MappingError(f"{part} must be a list")
		for row in rows:
			if not isinstance(row, dict) or set(row) != set(fields):
				raise MappingError(f"each of the {part} holds {', '.join(fields)}")
			for name, value in row.items():
				if value is not None and not isinstance(value, str):
					raise MappingError(f"{part}: {name} cannot be {value!r}")
	return items_of_rows(body["rules"], body["watched"])


def file_body(
	items: ReadOnlyMapping[Key, ReadOnlyMapping[str, str | None]],
	defaults: ReadOnlyMapping[Key, ReadOnlyMapping[str, str | None]] | None,
) -> dict[str, Any]:
	"""The body of the file of a mapping (steuerbote.mappings.transfer): its rows, and the rows of the defaults it took
	over, None for a mapping that knows none."""
	return {
		"mapping": body_of_items(items),
		"defaults": None if defaults is None else body_of_items(defaults),
	}


def items_of_file_body(body: Any) -> tuple[dict[Key, Fields], dict[Key, Fields] | None]:
	"""The items of the mapping and of its defaults that file_body wrote; raises MappingError for another shape."""
	if not isinstance(body, dict) or set(body) != {"mapping", "defaults"}:
		raise MappingError("the body of the file holds mapping and defaults")
	defaults = body["defaults"]
	return items_of_body(body["mapping"]), None if defaults is None else items_of_body(defaults)


def dump_items(items: ReadOnlyMapping[Key, ReadOnlyMapping[str, str | None]]) -> str:
	"""The items as the canonical JSON of their body: keys sorted, no blanks, UTF-8 as it is."""
	return canonical_json(body_of_items(items))


def load_items(text: str) -> dict[Key, Fields]:
	"""The items of the JSON dump_items wrote; raises MappingError for another text."""
	try:
		body = json.loads(text)
	except ValueError:
		raise MappingError("the stored defaults are no JSON") from None
	return items_of_body(body)


def _put(items: dict[Key, Fields], key: Key, fields: Fields, refusal: str) -> None:
	if key in items:
		raise MappingError(refusal.format(key[1]))
	items[key] = fields


def _rule_row(rule: AccountRule) -> dict[str, Any]:
	return {
		"account_number": rule.account_number,
		"category": rule.category.value,
		"trading_class": rule.trading_class.value if rule.trading_class else None,
	}


def _rule_fields(rule: AccountRule) -> Fields:
	row = _rule_row(rule)
	return {"place": RULE, **{name: row[name] for name in RULE_FIELDS}}


def _rule(row: Row) -> AccountRule:
	number = _account_number(row, "rule")
	where = f"account {number}"
	category = row.get("category")
	if not category:
		raise MappingError(f"{where}: no category")
	trading_class = row.get("trading_class")
	return AccountRule(
		account_number=number,
		category=_member(Category, category, where, "category"),
		trading_class=_member(TradingClass, trading_class, where, "trading class") if trading_class else None,
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


def _member[T: (Category, TradingClass)](kind: type[T], value: Any, where: str, what: str) -> T:
	"""The member of the enumeration that a Select field holds."""
	try:
		return kind(value)
	except ValueError:
		raise MappingError(
			f"{where}: {what} must be one of {', '.join(member.value for member in kind)}, not {value!r}"
		) from None


def _account_number(row: Row, kind: str) -> str:
	"""The account number as fetched, compared as written like every account number of the core."""
	if number := row.get("account_number"):
		return number
	if account := row.get("account"):
		raise MappingError(f"account {account} has no account number")
	in_row = f" in row {idx}" if (idx := row.get("idx")) else ""
	raise MappingError(f"{kind}{in_row} has no account")
