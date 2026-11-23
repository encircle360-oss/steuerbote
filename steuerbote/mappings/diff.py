"""What tells a mapping from its defaults or from a file: the three-way comparison behind Vorgaben aktualisieren and
Zuordnung importieren.

A mapping is a sequence of items, each a place of the mapping under a key: (kind, key) with its fields as text, such
as ("account", "8400") with the Kennzahl and side of its rule, or ("check", "Umsatzsteuer 19 %") with the accounts of
a Verprobung. Which kinds and fields a mapping has, its converter decides (steuerbote/mapping_sync.py for the VAT
Return Mapping); this module only compares them, so that any mapping of Steuerbote can use it.

compare() sets the items of the mapping (current) against those it may take over (proposed), item by item. An item
that reads the same on both sides is unchanged. Every other item is a Difference: it would be added, removed or
changed, field by field. The third side is the base, the items as the mapping last took them over from the defaults.
An item whose current fields are those of the base was left as the defaults gave it, so only the defaults moved: its
difference comes from the defaults, and Vorgaben aktualisieren proposes to take it. An item that differs from the
base was added, changed or removed by the user: its difference is the user's own, and taking it over would undo what
the user did. Without a base, the origin is unknown. apply() takes over the chosen differences and keeps everything
else.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Collection
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from enum import Enum

Key = tuple[str, str]
Fields = ReadOnlyMapping[str, str | None]
Items = ReadOnlyMapping[Key, Fields]


class Change(Enum):
	"""What taking over a difference does to the mapping."""

	ADDED = "added"
	REMOVED = "removed"
	CHANGED = "changed"


class Origin(Enum):
	"""Where a difference comes from."""

	DEFAULTS = "defaults"
	OWN = "own"
	UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Difference:
	"""An item that the mapping and the proposed items hold differently; ``fields`` names those that differ."""

	key: Key
	change: Change
	origin: Origin
	current: Fields | None
	proposed: Fields | None
	fields: tuple[str, ...]

	@property
	def proposes(self) -> bool:
		"""Whether taking it over follows the defaults without undoing anything the user did."""
		return self.origin is Origin.DEFAULTS


@dataclass(frozen=True, slots=True)
class Comparison:
	differences: tuple[Difference, ...]
	unchanged: tuple[Key, ...]


def compare(current: Items, proposed: Items, base: Items | None) -> Comparison:
	"""The differences between the items of a mapping and the items proposed, in the order of the mapping and then of
	the proposal; ``base`` is what the mapping took over from the defaults, None when nobody knows."""
	differences = []
	unchanged = []
	for key in (*current, *(key for key in proposed if key not in current)):
		mine, theirs = current.get(key), proposed.get(key)
		if mine == theirs:
			unchanged.append(key)
			continue
		differences.append(
			Difference(
				key=key,
				change=Change.ADDED if mine is None else Change.REMOVED if theirs is None else Change.CHANGED,
				origin=_origin(mine, base, key),
				current=mine,
				proposed=theirs,
				fields=_differing(mine, theirs),
			)
		)
	return Comparison(tuple(differences), tuple(unchanged))


def apply(current: Items, proposed: Items, chosen: Collection[Key]) -> dict[Key, Fields]:
	"""The items of the mapping with the chosen keys taken from the proposal: changed, removed or added at the end in
	the order of the proposal. Every other item stays as it is."""
	result: dict[Key, Fields] = {}
	for key, fields in current.items():
		if key not in chosen:
			result[key] = fields
		elif key in proposed:
			result[key] = proposed[key]
	for key, fields in proposed.items():
		if key in chosen and key not in current:
			result[key] = fields
	return result


def _origin(mine: Fields | None, base: Items | None, key: Key) -> Origin:
	if base is None:
		return Origin.UNKNOWN
	return Origin.DEFAULTS if mine == base.get(key) else Origin.OWN


def _differing(mine: Fields | None, theirs: Fields | None) -> tuple[str, ...]:
	"""The fields whose texts differ, in the order of the proposal and then of the mapping; all of a side that is
	missing."""
	names = (*(theirs or {}), *(name for name in mine or {} if name not in (theirs or {})))
	return tuple(name for name in names if (mine or {}).get(name) != (theirs or {}).get(name))
