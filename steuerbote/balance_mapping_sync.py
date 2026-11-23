"""The rows of the DocType Balance Sheet Mapping and the core Mapping of steuerbote.xbrl.mapping, converted without
Frappe.

The DocType keeps the Bilanzzuordnung of a company as table rows: rules (account, position, position for the
opposite balance, Abschlusszweck, shareholder flag and remaining term), watched accounts with their level, and
accounts outside the Bilanz and the GuV with their reason. rows_to_mapping turns the rows into a Mapping,
rows_of_mapping the other way, and defaults_rows gives the rows of the defaults of a chart
(steuerbote/ebilanz/defaults.py) for the accounts a company has. All take and return plain dicts with the field names
of the DocType, so the controller stays thin and this module is tested without a bench, as steuerbote/mapping_sync.py
does for the VAT Return Mapping.

For Vorgaben aktualisieren and the file of a mapping, the rows are also items of steuerbote.mappings.diff: one per
account, ("account", number), with its place, rule, watched or excluded, and the fields of that place as texts; the
shareholder flag is "1" or None. An account has one place, so a change of its place is one difference.
items_of_rows and rows_of_items turn rows into items and back, default_items gives the defaults of a chart for a
company as items, and body_of_items and items_of_body turn items into the plain data of the stored defaults and of the
file and back, with the flag as true or false; file_body and items_of_file_body make the body of the file, the rows
with the defaults the mapping took over.

A row holds what Frappe stores: an empty Check field is 0, an empty Data or Select field is "" or None, and an
account number is the one fetched from its account. The validate of the DocType runs before Frappe checks the
mandatory fields, so a row can still lack a value here.

The balances placed on their positions (steuerbote.xbrl.mapping.place) feed both documents:

- the Jahresabschluss (steuerbote/hgb/statement.py) takes statement_balances(): a Balance per account with the
  position its rule gives it, debit minus credit, the shareholder flag and the remaining term of the rule, and the
  account as its source. A „davon“ position goes as it is, which the statement notes as its Vermerk where one names
  it; the Restlaufzeiten and the shareholders come from the flags.
- the E-Bilanz takes position_values(), the value of each position its accounts count in, in the direction of the
  position (Technischer Leitfaden zur HGB-Taxonomie 6.9, A.13), davon_values() for the „davon“ positions, and
  kontennachweis(), one AccountLine per account with a balance: „der dem Konto zugeordneten Position (technisch:
  QName), der Kontonummer ..., der Kontobezeichnung ... und dem Kontosaldo zum Ende-Stichtag“ (Leitfaden A.12), on the
  position its value counts in, so that „Die Summe der Werte zum Element „Kontosaldo“ ... dem Wert der
  Taxonomieposition entsprechen“ (Technischer Leitfaden 6.10, B.12.1) and no Kontensaldo names a position no
  calculation holds. An account without a label is described by its name, since the elements „dürfen nicht leer
  übermittelt werden“ (Leitfaden 6.9, B.12).
"""

import json
from collections.abc import Iterable, Set
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any, NamedTuple

from steuerbote.ebilanz.defaults import defaults_for
from steuerbote.hgb.statement import Balance
from steuerbote.mappings.transfer import canonical_json
from steuerbote.ustva.mapping import WatchLevel
from steuerbote.xbrl.mapping import Excluded, Mapping, MappingError, Placement, Purpose, Rule, Watched
from steuerbote.xbrl.taxonomy import GAAP_PREFIX, Taxonomy
from steuerbote.xbrl.taxonomy import Balance as Side
from steuerbote.xbrl.versions import LATEST

Row = ReadOnlyMapping[str, Any]
Key = tuple[str, str]
Fields = dict[str, str | None]

FILE_FORMAT = "steuerbote/balance-sheet-mapping"
"""The kind of the file of a Balance Sheet Mapping (steuerbote.mappings.transfer)."""
ACCOUNT = "account"
RULE = "rule"
WATCHED = "watched"
EXCLUDED = "excluded"
RULE_FIELDS = ("concept", "opposite_concept", "purpose", "shareholder", "remaining_term")
BODY_PARTS = MappingProxyType(
	{
		"rules": ("account_number", *RULE_FIELDS),
		"watched": ("account_number", "level"),
		"excluded": ("account_number", "reason"),
	}
)

NO_ACCOUNT = "Row {0} of the Balance Sheet Mapping names no account."
NO_ACCOUNT_NUMBER = "Account {0} has no account number, by which the Balance Sheet Mapping names it."
NOT_JSON = "The stored defaults of the Balance Sheet Mapping are no JSON."
NOT_A_BODY = (
	"A Balance Sheet Mapping holds rules, watched accounts and accounts outside the Bilanz and the GuV."
)
BAD_ROWS = "Each row of the {0} holds {1}, as texts, the shareholder flag as true or false."
NOT_A_FILE_BODY = "The body of the file holds the mapping and the defaults it took over."
MESSAGES = (NO_ACCOUNT, NO_ACCOUNT_NUMBER, NOT_JSON, NOT_A_BODY, BAD_ROWS, NOT_A_FILE_BODY)


class MappingRows(NamedTuple):
	"""The rows of the three tables of a mapping, by account number."""

	rule_rows: list[dict[str, Any]]
	watched_rows: list[dict[str, Any]]
	excluded_rows: list[dict[str, Any]]


def rows_to_mapping(
	chart: str,
	rule_rows: Iterable[Row],
	watched_rows: Iterable[Row],
	excluded_rows: Iterable[Row],
	taxonomy_version: str,
) -> Mapping:
	"""The core Mapping of the rows; raises MappingError."""
	return Mapping(
		chart,
		tuple(_rule(row) for row in rule_rows),
		tuple(_watched(row) for row in watched_rows),
		tuple(_excluded(row) for row in excluded_rows),
		taxonomy_version,
	)


def rows_of_mapping(mapping: Mapping) -> MappingRows:
	"""The rows of a core Mapping, each table in the order of the mapping."""
	return MappingRows(
		[_rule_row(rule) for rule in mapping.rules],
		[
			{"account_number": watched.account_number, "level": watched.level.value}
			for watched in mapping.watched
		],
		[
			{"account_number": excluded.account_number, "reason": excluded.reason}
			for excluded in mapping.excluded
		],
	)


def defaults_rows(
	chart: str,
	taxonomy_version: str,
	existing_numbers: Set[str],
	levels: ReadOnlyMapping[str, str | None] = MappingProxyType({}),
) -> MappingRows:
	"""The rows the defaults of a chart give a company with these accounts; a watched account keeps the level the
	company gave it in ``levels``, by account number, and takes the one of the defaults otherwise."""
	defaults = defaults_for(chart, taxonomy_version)
	kept = {number: level for number, level in levels.items() if level}
	return rows_of_mapping(defaults.for_accounts(existing_numbers, kept))


def without_defaults(chart: str, taxonomy_version: str, existing_numbers: Set[str]) -> tuple[str, ...]:
	"""The accounts of a company that the defaults of the chart leave without a place, sorted."""
	return defaults_for(chart, taxonomy_version).uncovered(existing_numbers)


def items_of_mapping(mapping: Mapping) -> dict[Key, Fields]:
	"""The items of a core Mapping: the rules, then the watched accounts, then those outside the Bilanz and the GuV,
	each in the order of the mapping."""
	items: dict[Key, Fields] = {}
	for rule in mapping.rules:
		items[(ACCOUNT, rule.account_number)] = {
			"place": RULE,
			"concept": rule.concept,
			"opposite_concept": rule.opposite,
			"purpose": rule.purpose.value,
			"shareholder": "1" if rule.shareholder else None,
			"remaining_term": rule.term_value,
		}
	for watched in mapping.watched:
		items[(ACCOUNT, watched.account_number)] = {"place": WATCHED, "level": watched.level.value}
	for excluded in mapping.excluded:
		items[(ACCOUNT, excluded.account_number)] = {"place": EXCLUDED, "reason": excluded.reason}
	return items


def items_of_rows(
	rule_rows: Iterable[Row], watched_rows: Iterable[Row], excluded_rows: Iterable[Row]
) -> dict[Key, Fields]:
	"""The items of the rows, read as the core reads them; raises MappingError for a row the core cannot read and
	for an account in two rows. Items compare places, not the chart and the version of the taxonomy a mapping names."""
	return items_of_mapping(rows_to_mapping("", rule_rows, watched_rows, excluded_rows, LATEST.version))


def default_items(chart: str, taxonomy_version: str, existing_numbers: Set[str]) -> dict[Key, Fields]:
	"""What Vorgaben laden takes over from the defaults of a chart for a company with these accounts, as items: the
	levels are those of the defaults, not those a company gave its watched accounts."""
	return items_of_mapping(defaults_for(chart, taxonomy_version).for_accounts(existing_numbers))


def rows_of_items(items: ReadOnlyMapping[Key, ReadOnlyMapping[str, str | None]]) -> MappingRows:
	"""The rows of the items by account number, each table in the order of the items."""
	rows = MappingRows([], [], [])
	for (_kind, number), fields in items.items():
		if fields["place"] == RULE:
			rows.rule_rows.append(
				{
					"account_number": number,
					**{name: fields[name] for name in RULE_FIELDS},
					"shareholder": 1 if fields["shareholder"] else 0,
				}
			)
		elif fields["place"] == WATCHED:
			rows.watched_rows.append({"account_number": number, "level": fields["level"]})
		else:
			rows.excluded_rows.append({"account_number": number, "reason": fields["reason"]})
	return rows


def body_of_items(items: ReadOnlyMapping[Key, ReadOnlyMapping[str, str | None]]) -> dict[str, list[dict]]:
	"""The items as plain data, the form the stored defaults and the file of a mapping hold them in."""
	rows = rows_of_items(items)
	return {
		"rules": [{**row, "shareholder": bool(row["shareholder"])} for row in rows.rule_rows],
		"watched": rows.watched_rows,
		"excluded": rows.excluded_rows,
	}


def items_of_body(body: Any) -> dict[Key, Fields]:
	"""The items of plain data as body_of_items writes it; raises MappingError for data of another shape."""
	if not isinstance(body, dict) or set(body) != set(BODY_PARTS):
		raise MappingError(NOT_A_BODY)
	for part, fields in BODY_PARTS.items():
		rows = body[part]
		if not isinstance(rows, list) or not all(_plain_row(row, fields) for row in rows):
			raise MappingError(BAD_ROWS, part, ", ".join(fields))
	return items_of_rows(body["rules"], body["watched"], body["excluded"])


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
		raise MappingError(NOT_A_FILE_BODY)
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
		raise MappingError(NOT_JSON) from None
	return items_of_body(body)


@dataclass(frozen=True, slots=True)
class AccountLine:
	"""A Kontensaldo of the E-Bilanz: the position the value of the account counts in, without the prefix of the GAAP
	module, the account number, its description and its balance in the direction of the position."""

	position: str
	account_number: str
	description: str
	amount: Decimal

	@property
	def position_name(self) -> str:
		"""The QName of the position, as detailedInformation.accountbalances.positionName holds it."""
		return f"{GAAP_PREFIX}:{self.position}"


def statement_balances(placement: Placement) -> tuple[Balance, ...]:
	"""The placed balances as the Balance rows of the Jahresabschluss, in the order of the books."""
	return tuple(
		Balance(
			item.concept, item.amount, item.rule.shareholder, item.rule.remaining_term, item.balance.account
		)
		for item in placement.placed
	)


def position_values(placement: Placement) -> dict[str, Decimal]:
	"""The value of each position the placed balances count in, in the order the books first name them."""
	values: dict[str, Decimal] = {}
	for item in placement.placed:
		values[item.position] = values.get(item.position, Decimal(0)) + item.value
	return values


def davon_values(placement: Placement, taxonomy: Taxonomy) -> dict[str, Decimal]:
	"""The value of each „davon“ position the balances go to, in its own direction."""
	values: dict[str, Decimal] = {}
	for item in placement.placed:
		if item.concept != item.position:
			side = taxonomy.concept(item.concept).balance
			value = item.amount if side is Side.DEBIT else -item.amount
			values[item.concept] = values.get(item.concept, Decimal(0)) + value
	return values


def kontennachweis(placement: Placement) -> tuple[AccountLine, ...]:
	"""One Kontensaldo per placed account, by position and account number."""
	lines = (
		AccountLine(
			item.position,
			item.balance.number,
			item.balance.label or item.balance.account,
			item.value,
		)
		for item in placement.placed
	)
	return tuple(sorted(lines, key=lambda line: (line.position, line.account_number)))


def _plain_row(row: Any, fields: tuple[str, ...]) -> bool:
	if not isinstance(row, dict) or set(row) != set(fields):
		return False
	return all(
		isinstance(value, bool) if name == "shareholder" else value is None or isinstance(value, str)
		for name, value in row.items()
	)


def _rule(row: Row) -> Rule:
	return Rule(
		_account_number(row),
		row.get("concept"),
		row.get("opposite_concept") or None,
		row.get("purpose") or Purpose.BOTH,
		bool(row.get("shareholder")),
		row.get("remaining_term") or None,
	)


def _watched(row: Row) -> Watched:
	return Watched(_account_number(row), row.get("level") or WatchLevel.BLOCKING)


def _excluded(row: Row) -> Excluded:
	return Excluded(_account_number(row), row.get("reason"))


def _rule_row(rule: Rule) -> dict[str, Any]:
	return {
		"account_number": rule.account_number,
		"concept": rule.concept,
		"opposite_concept": rule.opposite,
		"purpose": rule.purpose.value,
		"shareholder": int(rule.shareholder),
		"remaining_term": rule.term_value,
	}


def _account_number(row: Row) -> str:
	"""The account number as fetched, compared as written like every account number of the core."""
	if number := row.get("account_number"):
		return number
	if account := row.get("account"):
		raise MappingError(NO_ACCOUNT_NUMBER, account)
	raise MappingError(NO_ACCOUNT, row.get("idx") or "?")
