"""Corrections and lines by hand of an annual document, and the amounts its lines report.

An annual document reports lines: the fields of an Erklärung, the positions of the E-Bilanz, the lines of the
Jahresabschluss. Berechnen computes each line it can from the sources. The company may file another amount for a
line once it says why, a correction, and add a line by hand where Berechnen computes nothing, with its amount and its
reason. „Eine Abweichung muss erklärt sein“ (docs/roadmap.md, Grundsätze): the Voranmeldung takes an override once it
has a reason, and an override without a reason is refused rather than ignored, since its author expects it to count
(steuerbote/steuerbote/doctype/vat_return/bridge.py). A correction to zero is filed too.

Columns names the columns of the line table of a module: the key of a line, such as a Feldkennung or a concept of the
taxonomy; the amounts Berechnen computes, the first of them what the line files without a correction; what Berechnen
writes to describe the line; the correction with its reason; the reported amount; and the mark of a line by hand,
whose correction is its amount. Rows are mappings, such as the dicts of the child rows of Frappe.

- recalculated: Berechnen writes the lines it computed and keeps the corrections and the lines by hand. A correction of
  a line Berechnen no longer computes stays, with its amounts at zero, so that nothing the company filed by hand drops
  out unnoticed.
- restored: Frappe keeps no read-only field from a save through its API, so a save takes what the company enters on a
  line and keeps what Berechnen computed. A new line is a line by hand, and a line Berechnen computed cannot be
  removed.
- reported: what a line files.
- kept: whether the amounts stored for the lines are those the lines give, before a filing.
- changed: whether a save changed what Berechnen checked.
- manual_lines: the lines by hand, for a module whose computation takes them in, such as an amount by hand that
  goes into the sum of a field before it is rounded.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from steuerbote.ustva.rounding import ZERO, require_decimal, to_cents

type Row = Mapping[str, Any]


class Problem(Enum):
	NO_KEY = "no_key"
	DUPLICATE = "duplicate"
	MISSING_REASON = "missing_reason"
	REMOVED = "removed"


class OverrideError(ValueError):
	"""A line that cannot be filed as it is."""

	def __init__(self, problem: Problem, key: str) -> None:
		super().__init__(f"line {key!r}: {problem.value}")
		self.problem = problem
		self.key = key


@dataclass(frozen=True, slots=True)
class Columns:
	"""The columns of the line table of a module."""

	key: str = "key"
	amounts: tuple[str, ...] = ("computed",)
	"""The amounts Berechnen computes; the first is what the line files without a correction."""
	described: tuple[str, ...] = ()
	"""What Berechnen writes to describe the line, such as its label or its Zeile."""
	correction: str = "correction"
	reason: str = "correction_reason"
	reported: str = "reported"
	manual: str = "manual"

	def __post_init__(self) -> None:
		if not self.amounts:
			raise ValueError("a line table needs the column of the amount Berechnen computes")

	@property
	def amount(self) -> str:
		return self.amounts[0]

	@property
	def filled(self) -> tuple[str, ...]:
		"""What Berechnen writes on a line, and a save keeps."""
		return (self.key, *self.amounts, *self.described)


@dataclass(frozen=True, slots=True)
class Correction:
	"""An amount a line files instead of the computed one, with the reason why."""

	amount: Decimal
	reason: str

	def __post_init__(self) -> None:
		require_decimal(self.amount)
		if not isinstance(self.reason, str) or not self.reason.strip():
			raise OverrideError(Problem.MISSING_REASON, "")


@dataclass(frozen=True, slots=True)
class ManualLine:
	"""A line by hand: its key, its amount and its reason."""

	key: str
	amount: Decimal
	reason: str


def to_amount(value: object) -> Decimal:
	"""The value of a currency field in cents; Frappe hands out floats, strings or nothing."""
	return to_cents(Decimal(str(value or ZERO)))


def correction_of(row: Row, columns: Columns) -> Correction | None:
	"""The correction of a line, once it has a reason; an amount without a reason is refused."""
	reason = str(row.get(columns.reason) or "").strip()
	amount = to_amount(row.get(columns.correction))
	if not reason:
		if amount:
			raise OverrideError(Problem.MISSING_REASON, _key(row, columns))
		return None
	return Correction(amount, reason)


def reported(row: Row, columns: Columns) -> Decimal:
	"""What a line files: its correction once it has a reason, else the amount Berechnen computed. A line by hand files
	its correction, which it needs."""
	correction = correction_of(row, columns)
	if _manual(row, columns) and correction is None:
		raise OverrideError(Problem.MISSING_REASON, _key(row, columns))
	return correction.amount if correction else to_amount(row.get(columns.amount))


def manual_lines(rows: Iterable[Row], columns: Columns) -> tuple[ManualLine, ...]:
	"""The lines by hand, in their order, each with its key, amount and reason."""
	lines = []
	for row in rows:
		if _manual(row, columns):
			key = _required_key(row, columns)
			amount = reported(row, columns)
			lines.append(ManualLine(key, amount, str(row.get(columns.reason)).strip()))
	return tuple(lines)


def recalculated(computed: Iterable[Row], rows: Iterable[Row], columns: Columns) -> list[dict[str, Any]]:
	"""The lines after Berechnen: those it computed, each with the correction the document holds for its key, then the
	corrections of lines it no longer computes and the lines by hand, as the document holds them."""
	rows = list(rows)
	corrections = {
		_key(row, columns): correction
		for row in rows
		if not _manual(row, columns) and (correction := correction_of(row, columns))
	}
	lines = []
	for row in computed:
		key = _required_key(row, columns)
		correction = corrections.pop(key, None)
		line = {
			**_without_name(row),
			columns.correction: correction.amount if correction else ZERO,
			columns.reason: correction.reason if correction else "",
			columns.manual: 0,
		}
		lines.append(line)
	_refuse_duplicates(lines, columns)
	for row in rows:
		manual = _manual(row, columns)
		if manual or _key(row, columns) in corrections:
			lines.append(
				{**_without_name(row), **dict.fromkeys(columns.amounts, ZERO), columns.manual: int(manual)}
			)
	return [_with_reported(line, columns) for line in lines]


def restored(stored: Iterable[Row], sent: Iterable[Row], columns: Columns) -> list[dict[str, Any]]:
	"""The lines a save sends, each with what Berechnen stored for it: a line of a stored name keeps its key, amounts,
	description and mark, and takes the correction; a line by hand takes its key as well, and a new line is one."""
	by_name = {row.get("name"): row for row in stored if row.get("name")}
	lines = []
	for row in sent:
		before = by_name.pop(row.get("name"), None) if row.get("name") else None
		if before is None:
			line = {**row, "name": None, **dict.fromkeys(columns.amounts, ZERO), columns.manual: 1}
		elif _manual(before, columns):
			line = {**row, **dict.fromkeys(columns.amounts, ZERO), columns.manual: 1}
		else:
			line = {**row, **{column: before.get(column) for column in columns.filled}, columns.manual: 0}
		lines.append(line)
	removed = next((row for row in by_name.values() if not _manual(row, columns)), None)
	if removed is not None:
		raise OverrideError(Problem.REMOVED, _key(removed, columns))
	_refuse_duplicates(lines, columns)
	return [_with_reported(line, columns) for line in lines]


def kept(rows: Iterable[Row], stored: Iterable[Row], columns: Columns) -> bool:
	"""Whether ``stored`` holds, for the same lines, the amount each of ``rows`` reports."""
	try:
		computed = {row.get("name"): reported(row, columns) for row in rows}
	except OverrideError:
		return False
	return computed == {row.get("name"): to_amount(row.get(columns.reported)) for row in stored}


def changed(before: Iterable[Row], rows: Iterable[Row], columns: Columns) -> bool:
	"""Whether the lines report other amounts than ``before``: a correction, or a line by hand more, less or other."""
	return _filed(before, columns) != _filed(rows, columns)


def _filed(rows: Iterable[Row], columns: Columns) -> list[tuple[str, int, Decimal]]:
	return sorted((_key(row, columns), int(_manual(row, columns)), reported(row, columns)) for row in rows)


def _with_reported(line: dict[str, Any], columns: Columns) -> dict[str, Any]:
	return {**line, columns.reported: reported(line, columns)}


def _refuse_duplicates(lines: Iterable[Row], columns: Columns) -> None:
	seen = set()
	for line in lines:
		if _manual(line, columns):
			continue
		key = _required_key(line, columns)
		if key in seen:
			raise OverrideError(Problem.DUPLICATE, key)
		seen.add(key)


def _without_name(row: Row) -> dict[str, Any]:
	return {column: value for column, value in row.items() if column != "name"}


def _manual(row: Row, columns: Columns) -> bool:
	return bool(row.get(columns.manual))


def _key(row: Row, columns: Columns) -> str:
	return str(row.get(columns.key) or "").strip()


def _required_key(row: Row, columns: Columns) -> str:
	key = _key(row, columns)
	if not key:
		raise OverrideError(Problem.NO_KEY, key)
	return key
