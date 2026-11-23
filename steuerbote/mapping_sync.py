"""The rows of the DocType VAT Return Mapping and the core Mapping, converted without Frappe.

The DocType keeps a company's Kontenzuordnung as table rows: rules (account, Kennzahl, side, rate and an
additional Kennzahl), checks (account numbers as text) and watched accounts with their level. The core works
with Mapping, AccountRule, TaxCheck and WatchedAccount. rows_to_mapping turns the rows into a Mapping, and
defaults_for_accounts turns the default mapping of a chart into rows for the accounts a company has. Both
take and return plain dicts with the DocType's field names, so the controller stays thin and this module is
tested without a bench.

For Vorgaben aktualisieren and the file of a mapping, the rows are also items of steuerbote.mappings.diff: one per
account with its place in the mapping, its rule or its watched entry, and one per Verprobung by its label. Each field
is a text in one canonical form: a rate as its digits without trailing zeros, the accounts of a Verprobung sorted,
so that the same mapping always gives the same items, however Frappe stored its rows. items_of_rows and
rows_of_items turn rows into items and back, default_items gives the defaults of a chart for a company as items, and
body_of_items and items_of_body turn items into the plain data of the stored defaults and of the file and back, and
file_body and items_of_file_body make the body of the file of a mapping, its rows with the defaults it took over.

The annual return reads the same rows and two things more (steuerbote/ustjahr/split.py): the annual field and the
paragraph a rule names for its line, and the rows of the accounts only the annual return reads, „Zuordnung nur für
die Umsatzsteuererklärung“. choices_of_rows and annual_rules_of_rows turn them into the Choice and AnnualRule of the
core, and annual_split gives the line of every account with the defaults of the chart by role
(steuerbote/ustjahr/defaults.py), which is what the annual return calls. As items, an annual field is one of its own
kind beside the rule of its account, and so is a row for the annual return only beside a watched entry of the same
account; both come after the other items. The body holds them in parts of their own, annual_fields and annual_rules,
and only when there are any, so that a mapping without them keeps the body, the stored defaults and the file it had,
and the body of a file of an earlier version reads as before. annual_rows_for_accounts and annual_default_items give
the rows for the annual return of the defaults of a chart for the accounts a company has. check_annual_rows is what
saving a mapping checks of them.

A row holds what Frappe stores: an empty Float field is 0, an empty Data or Select field is "" or None,
and a rule's account number is the one fetched from its account. The DocType's own validate runs before
Frappe checks the mandatory fields, so a row can still lack a value here.
"""

import json
import re
from collections.abc import Iterable, Set
from collections.abc import Mapping as ReadOnlyMapping
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, NamedTuple

from steuerbote.mappings.transfer import canonical_json
from steuerbote.ustjahr.defaults import CHARTS as ANNUAL_CHARTS
from steuerbote.ustjahr.defaults import annual_rules, role_defaults
from steuerbote.ustjahr.form import catalogue_for as annual_catalogue_for
from steuerbote.ustjahr.split import ANNUAL_MAPPED, AnnualRule, Choice, Split, SplitError, split
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
Key = tuple[str, str]
Fields = dict[str, str | None]

# The format of the file of a VAT Return Mapping (steuerbote.mappings.transfer).
FILE_FORMAT = "steuerbote/vat-return-mapping"
# The kinds of items of a VAT Return Mapping, and the places an account takes in it.
ACCOUNT = "account"
CHECK = "check"
RULE = "rule"
WATCHED = "watched"
# The annual field and paragraph a rule names for the annual return, and an account only the annual return reads.
ANNUAL_FIELD = "annual_field"
ANNUAL_RULE = "annual_rule"
RULE_FIELDS = ("kennzahl", "side", "tax_rate", "also_kennzahl", "also_side")
CHECK_FIELDS = ("base_accounts", "tax_accounts", "side")
CHOICE_FIELDS = ("annual_field", "paragraph")
ANNUAL_RULE_FIELDS = ("annual_field", "side", "paragraph")
BODY_PARTS = {
	"rules": ("account_number", *RULE_FIELDS),
	"checks": ("label", *CHECK_FIELDS),
	"watched": ("account_number", "level"),
}
ANNUAL_BODY_PARTS = {
	"annual_fields": ("account_number", *CHOICE_FIELDS),
	"annual_rules": ("account_number", *ANNUAL_RULE_FIELDS),
}

# The DocType asks for account numbers separated by commas; blanks and line breaks separate them as well,
# since a number never contains either.
_ACCOUNT_SEPARATORS = re.compile(r"[\s,]+")


class MappingRows(NamedTuple):
	"""The rows of the three tables of a mapping, by account number."""

	rule_rows: list[dict[str, Any]]
	check_rows: list[dict[str, Any]]
	watched_rows: list[dict[str, Any]]


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


def items_of_rows(
	rule_rows: Iterable[Row],
	check_rows: Iterable[Row],
	watched_rows: Iterable[Row],
	annual_rows: Iterable[Row] = (),
) -> dict[Key, Fields]:
	"""The items of the rows: the accounts of the rules, then the watched accounts, then the Verprobungen, then the
	annual fields of the rules and the rows for the annual return only, each in the order of its table. Raises
	MappingError for a row the core cannot read and for an account or a label that two rows name, since an item has
	one place."""
	items: dict[Key, Fields] = {}
	rule_rows = tuple(rule_rows)
	for row in rule_rows:
		rule = _rule(row)
		_put(items, (ACCOUNT, rule.account_number), _rule_fields(rule), "account {0} is mapped twice")
	for row in watched_rows:
		watched = _watched(row)
		key = (ACCOUNT, watched.account_number)
		twice = items.get(key, {}).get("place") == WATCHED
		_put(
			items,
			key,
			{"place": WATCHED, "level": watched.level.value},
			"account {0} is watched twice" if twice else "account {0} is watched but also mapped or checked",
		)
	for row in check_rows:
		check = _check(row)
		_put(items, (CHECK, check.label), _check_fields(check), "two tax checks have the label {0!r}")
	for choice in choices_of_rows(rule_rows):
		items[(ANNUAL_FIELD, choice.account_number)] = {
			"annual_field": choice.field,
			"paragraph": choice.paragraph,
		}
	for annual in annual_rules_of_rows(annual_rows):
		_put(
			items,
			(ANNUAL_RULE, annual.account_number),
			{"annual_field": annual.field, "side": annual.side.value, "paragraph": annual.paragraph},
			"account {0} has two rows for the annual return only",
		)
	return items


def items_of_mapping(mapping: Mapping) -> dict[Key, Fields]:
	"""The items of a core Mapping, as its rows would give them."""
	return items_of_rows(
		[_rule_row(rule) for rule in mapping.rules],
		[
			{
				"label": check.label,
				"base_accounts": ", ".join(check.base_accounts),
				"tax_accounts": ", ".join(check.tax_accounts),
				"side": check.side.value,
			}
			for check in mapping.checks
		],
		[
			{"account_number": watched.account_number, "level": watched.level.value}
			for watched in mapping.watched
		],
	)


def default_items(chart: str, year: int, existing_numbers: Set[str]) -> dict[Key, Fields]:
	"""What Vorgaben laden takes over from the defaults of a chart for a company with these accounts, as items: the
	levels are those of the defaults, not those a company gave its watched accounts."""
	defaults = defaults_for_accounts(chart, year, existing_numbers)
	return items_of_rows(defaults.rule_rows, defaults.check_rows, defaults.watched_rows)


def choices_of_rows(rule_rows: Iterable[Row]) -> tuple[Choice, ...]:
	"""What the rule rows say for the annual return: each that names an annual field or a paragraph, as a Choice."""
	choices = []
	for row in rule_rows:
		field, paragraph = _text(row.get("annual_field")) or None, _one_line(row.get("paragraph"))
		if field is not None or paragraph is not None:
			choices.append(Choice(_account_number(row, "rule"), field, paragraph))
	return tuple(choices)


def annual_rules_of_rows(annual_rows: Iterable[Row]) -> tuple[AnnualRule, ...]:
	"""The rows of the accounts only the annual return reads, as AnnualRule; raises MappingError for a row without
	account or field or with a side that is neither credit nor debit."""
	rules = []
	for row in annual_rows:
		number = _account_number(row, "row for the annual return only")
		where = f"account {number}"
		field = _text(row.get("annual_field"))
		if not field:
			raise MappingError(f"{where}: no annual field")
		rules.append(
			AnnualRule(number, field, _side(row.get("side"), where), _one_line(row.get("paragraph")))
		)
	return tuple(rules)


def annual_split(
	chart: str,
	rule_rows: Iterable[Row],
	check_rows: Iterable[Row],
	watched_rows: Iterable[Row],
	annual_rows: Iterable[Row],
	year: int,
) -> Split:
	"""The line of the annual return of ``year`` for each account of the rows, with the defaults of the chart by role.

	Raises MappingError for rows the core of the Voranmeldung refuses, SplitError for an annual field or a row for the
	annual return that does not fit, and UnknownYearError for a year without its form.
	"""
	rule_rows = tuple(rule_rows)
	mapping = rows_to_mapping(chart, rule_rows, check_rows, watched_rows, year)
	roles = role_defaults(chart, year) if chart in ANNUAL_CHARTS else None
	return split(mapping, choices_of_rows(rule_rows), roles, annual_rules_of_rows(annual_rows))


def check_annual_rows(
	chart: str,
	rule_rows: Iterable[Row],
	check_rows: Iterable[Row],
	watched_rows: Iterable[Row],
	annual_rows: Iterable[Row],
	year: int,
) -> None:
	"""Refuse an annual field, a paragraph or a row for the annual return only that does not fit form USt 2 A of
	``year``: SplitError, or MappingError for a row the core cannot read.

	The Voranmeldung needs no line of the annual return, so an account whose Kennzahl splits into lines without a
	default, such as Kz 64, and that has neither an annual field nor a role naming one of them, is left to the annual
	return, which asks for its line; for this check it takes the first of them. An account of a Kennzahl without any
	line, Kz 39, whose Sondervorauszahlung the annual return takes into its Vorauszahlungssoll, is left out unless its
	rule names an annual field or a paragraph, and is never one for the annual return only. Rules that the form of the
	Voranmeldung of ``year`` does not take leave the check to the Voranmeldung, which checks them against the form of
	its own year first: a later year may know a Kennzahl that the latest form of the annual return does not.
	"""
	rule_rows = tuple(rule_rows)
	choices, annual = choices_of_rows(rule_rows), annual_rules_of_rows(annual_rows)
	try:
		mapping = rows_to_mapping(chart, rule_rows, check_rows, watched_rows, year)
	except MappingError:
		return
	catalogue = annual_catalogue_for(year)
	roles = dict(role_defaults(chart, year)) if chart in ANNUAL_CHARTS else {}
	chosen = {choice.account_number for choice in choices}
	rules = []
	for rule in mapping.rules:
		lines = catalogue.children(rule.kennzahl)
		if not lines and rule.account_number not in chosen:
			continue
		rules.append(rule)
		elements = {line.element for line in lines}
		if (
			lines
			and catalogue.default_child(rule.kennzahl) is None
			and roles.get(rule.account_number) not in elements
		):
			roles[rule.account_number] = lines[0].element
	for annual_rule in annual:
		mapped = mapping.rule_for(annual_rule.account_number)
		if mapped is not None and mapped not in rules:
			raise SplitError(ANNUAL_MAPPED, annual_rule.account_number, mapped.kennzahl)
	checked = Mapping(chart, tuple(rules), mapping.checks, mapping.watched, year)
	split(checked, choices, roles, annual)


def annual_rows_for_accounts(chart: str, year: int, existing_numbers: Set[str]) -> list[dict[str, Any]]:
	"""The rows for the annual return only of the defaults of ``chart`` whose account the company has; none for a
	chart of its own."""
	if chart not in ANNUAL_CHARTS:
		return []
	return [
		{
			"account_number": rule.account_number,
			"annual_field": rule.field,
			"side": rule.side.value,
			"paragraph": rule.paragraph,
		}
		for rule in annual_rules(chart, year)
		if rule.account_number in existing_numbers
	]


def annual_default_items(chart: str, year: int, existing_numbers: Set[str]) -> dict[Key, Fields]:
	"""What Vorgaben laden takes over for the annual return from the defaults of a chart, as items."""
	return items_of_rows((), (), (), annual_rows_for_accounts(chart, year, existing_numbers))


def rows_of_items(items: ReadOnlyMapping[Key, ReadOnlyMapping[str, str | None]]) -> MappingRows:
	"""The rows of the items by account number, each table in the order of the items; a rule row carries the annual
	field and paragraph of its account, if the items name one. Raises MappingError for an annual field whose account
	has no rule, since the rule row holds it."""
	parts = _parts_of_items(items)
	rules = {row["account_number"]: row for row in parts["rules"]}
	for choice in parts["annual_fields"]:
		number = choice["account_number"]
		if number not in rules:
			raise MappingError(f"account {number} has an annual field but no rule")
		rules[number] = {**rules[number], **{name: choice[name] for name in CHOICE_FIELDS}}
	return MappingRows(list(rules.values()), parts["checks"], parts["watched"])


def annual_rows_of_items(
	items: ReadOnlyMapping[Key, ReadOnlyMapping[str, str | None]],
) -> list[dict[str, Any]]:
	"""The rows for the annual return only, in the order of the items."""
	return _parts_of_items(items)["annual_rules"]


def body_of_items(items: ReadOnlyMapping[Key, ReadOnlyMapping[str, str | None]]) -> dict[str, list[dict]]:
	"""The items as plain data, the form the stored defaults and the file of a mapping hold them in: rules, checks
	and watched accounts with their fields as texts, the accounts of a check as a list, and the annual fields and the
	rows for the annual return only where there are any."""
	parts = _parts_of_items(items)
	body = {
		"rules": [{**row, "tax_rate": _rate_text(row["tax_rate"])} for row in parts["rules"]],
		"checks": [
			{**row, **{part: list(_account_numbers(row[part])) for part in ("base_accounts", "tax_accounts")}}
			for row in parts["checks"]
		],
		"watched": parts["watched"],
	}
	return body | {part: parts[part] for part in ANNUAL_BODY_PARTS if parts[part]}


def items_of_body(body: Any) -> dict[Key, Fields]:
	"""The items of plain data as body_of_items writes it; raises MappingError for data of another shape."""
	if not isinstance(body, dict) or not set(BODY_PARTS) <= set(body) <= {*BODY_PARTS, *ANNUAL_BODY_PARTS}:
		raise MappingError(
			f"a mapping holds {', '.join(BODY_PARTS)} and may hold {', '.join(ANNUAL_BODY_PARTS)}"
		)
	for part, fields in {**BODY_PARTS, **ANNUAL_BODY_PARTS}.items():
		rows = body.get(part, [])
		if not isinstance(rows, list):
			raise MappingError(f"{part} must be a list")
		for row in rows:
			if not isinstance(row, dict) or set(row) != set(fields):
				raise MappingError(f"each of the {part} holds {', '.join(fields)}")
			for name, value in row.items():
				if not _plain(
					value, list_of_numbers=part == "checks" and name in ("base_accounts", "tax_accounts")
				):
					raise MappingError(f"{part}: {name} cannot be {value!r}")
	rules = {row["account_number"]: row for row in body["rules"]}
	for choice in body.get("annual_fields", []):
		if choice["account_number"] not in rules:
			raise MappingError(f"account {choice['account_number']} has an annual field but no rule")
		rules[choice["account_number"]] = {**rules[choice["account_number"]], **choice}
	return items_of_rows(
		[rules.get(row["account_number"], row) for row in body["rules"]],
		[
			{**row, **{part: ", ".join(row[part]) for part in ("base_accounts", "tax_accounts")}}
			for row in body["checks"]
		],
		body["watched"],
		body.get("annual_rules", []),
	)


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


def _parts_of_items(items: ReadOnlyMapping[Key, ReadOnlyMapping[str, str | None]]) -> dict[str, list[dict]]:
	"""The rows of each kind of item, rules without their annual fields, in the order of the items."""
	parts: dict[str, list[dict]] = {
		"rules": [],
		"checks": [],
		"watched": [],
		"annual_fields": [],
		"annual_rules": [],
	}
	for (kind, key), fields in items.items():
		if kind == CHECK:
			parts["checks"].append({"label": key, **{name: fields[name] for name in CHECK_FIELDS}})
		elif kind == ANNUAL_FIELD:
			parts["annual_fields"].append(
				{"account_number": key, **{name: fields[name] for name in CHOICE_FIELDS}}
			)
		elif kind == ANNUAL_RULE:
			parts["annual_rules"].append(
				{"account_number": key, **{name: fields[name] for name in ANNUAL_RULE_FIELDS}}
			)
		elif fields["place"] == WATCHED:
			parts["watched"].append({"account_number": key, "level": fields["level"]})
		else:
			rate = fields["tax_rate"]
			parts["rules"].append(
				{
					"account_number": key,
					**{name: fields[name] for name in RULE_FIELDS},
					"tax_rate": Decimal(rate) if rate else None,
				}
			)
	return parts


def _put(items: dict[Key, Fields], key: Key, fields: Fields, refusal: str) -> None:
	if key in items:
		raise MappingError(refusal.format(key[1]))
	items[key] = fields


def _plain(value: Any, list_of_numbers: bool) -> bool:
	if list_of_numbers:
		return isinstance(value, list) and all(isinstance(number, str) for number in value)
	return value is None or isinstance(value, str)


def _rule_fields(rule: AccountRule) -> Fields:
	return {
		"place": RULE,
		"kennzahl": rule.kennzahl,
		"side": rule.side.value,
		"tax_rate": _rate_text(rule.tax_rate),
		"also_kennzahl": rule.also_kennzahl,
		"also_side": rule.also_side.value if rule.also_side else None,
	}


def _check_fields(check: TaxCheck) -> Fields:
	return {
		"base_accounts": ", ".join(sorted(check.base_accounts)),
		"tax_accounts": ", ".join(sorted(check.tax_accounts)),
		"side": check.side.value,
	}


def _rate_text(rate: Decimal | None) -> str | None:
	"""A rate as its digits, 19 for 19.0 and 5.5 for 5.50, so that a rate reads the same however it was stored."""
	return None if rate is None else format(rate.normalize(), "f")


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


def _one_line(value: Any) -> str | None:
	"""A text on one line without blanks at either end, as the core takes a paragraph; None for an empty one."""
	return " ".join(_text(value).split()) or None


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
