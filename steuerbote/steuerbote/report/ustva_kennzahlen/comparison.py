"""The Vorperiodenvergleich of the report UStVA Kennzahlen. Pure Python, no Frappe.

The report sets every Kennzahl and every sum of the form beside the amount the same line reported in the
previous Voranmeldungszeitraum of the same rhythm and in the same period one year earlier. The report
computes both from the general ledger with calculate() and the company's mapping on the form of their own
year, not from earlier VAT Returns: the ledger is the source of every Kennzahl, and the comparison works
before any return of those periods exists. All amounts are reported amounts, as the form rounds them.

compared_rows() adds the amounts of the compared periods and the difference to the previous period to the
rows of report_rows().
"""

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from steuerbote.steuerbote.report.ustva_kennzahlen.attribution import COLUMNS, SUM_LINES
from steuerbote.ustva import Period, UstvaResult
from steuerbote.ustva.rounding import ZERO


def year_before(period: Period) -> Period:
	"""The same period one year earlier."""
	return Period(period.year - 1, period.rhythm, period.index)


def compared_kennzahlen(*results: UstvaResult | None) -> frozenset[str]:
	"""The Kennzahlen with an amount in any of the compared periods, so that a Kennzahl that fell to zero
	still has its row."""
	return frozenset(number for result in results if result is not None for number in result.values)


def compared_rows(
	rows: Iterable[dict[str, Any]], previous: UstvaResult | None, previous_year: UstvaResult | None
) -> list[dict[str, Any]]:
	"""The rows with the amounts of the previous period and of the previous year and the difference to the
	previous period, on the rows of the Kennzahlen and the sums. A period that could not be computed, such
	as one of a year without catalogue, leaves its column empty, and with the previous period the
	difference."""
	before = _reported(previous)
	year_ago = _reported(previous_year)
	return [_compared(row, before, year_ago) for row in rows]


def _reported(result: UstvaResult | None) -> dict[str | int, Decimal] | None:
	"""The reported amounts of a period by Kennzahl, and the sums of the form by their line."""
	if result is None:
		return None
	return {
		**{number: value.reported for number, value in result.values.items()},
		**{line: getattr(result, total) for line, _label, total in SUM_LINES},
	}


def _compared(
	row: dict[str, Any],
	before: dict[str | int, Decimal] | None,
	year_ago: dict[str | int, Decimal] | None,
) -> dict[str, Any]:
	key = _key(row)
	if key is None:
		return row
	previous = None if before is None else before.get(key, ZERO)
	return {
		**row,
		"previous_period": previous,
		"previous_year": None if year_ago is None else year_ago.get(key, ZERO),
		"difference": None if previous is None else row["reported"] - previous,
	}


def _key(row: dict[str, Any]) -> str | int | None:
	"""A Kennzahl row by its Kennzahl, a sum by its line; vouchers and notes are not compared."""
	if row["indent"]:
		return None
	return row["kennzahl"] or row["line"]


def note_row(text: str) -> dict[str, Any]:
	"""A row of its own that tells the reader something about the report, such as a comparison it lacks."""
	return {**dict.fromkeys(COLUMNS), "label": text, "indent": 0, "parent_kennzahl": None, "bold": 0}
