"""The print of the E-Bilanz: Bilanz in Kontoform, GuV, Betriebsvermögensvergleich, Anlagenspiegel, Kontennachweis and
Überleitungsrechnung, each with the labels of the HGB-Taxonomie, from the tables of the document.

print_sections() takes the rows of the document as Berechnen wrote them and a save kept them: the positions with the
amounts they report, the Kontensalden, the rows of the Anlagenspiegel and the entries of the Überleitung. It gives:

- the Bilanzierungsstandard and the Status des Berichts in words, the latter as the GCD of the taxonomy labels it
  (steuerbote/jahresmeldung/corrections.py);

- the Bilanz in Kontoform, the positions of Aktiva (under „Bilanzsumme, Summe Aktiva“, bs.ass) on the left and of the
  Passiva (bs.eqLiab) on the right, each with its level in the presentation of the taxonomy, a position above others
  as a sum, and for a Handelsbilanz the amount of the Steuerbilanz beside it;
- the GuV and the Betriebsvermögensvergleich in the order of their presentation;
- the Anlagenspiegel with a row per position, value type and asset category in two parts, the Anschaffungs- und
  Herstellungskosten and the Abschreibungen with the Buchwert, each with the columns of the value development of the
  taxonomy (the Abschreibungen of the period as one column of their kinds, which the XBRL file reports one by one),
  and a row with the sums per value type;
- the Kontennachweis, the accounts of each position with their sum;
- the Überleitungsrechnung of a Handelsbilanz.

A position reported as NIL, a Mussfeld the books do not fill, is not printed: it has no amount to show. The amounts are
in euros and cents as the E-Bilanz reports them. The print format „E-Bilanz“ shows the sections; it computes nothing
but these sums of the rows.
"""

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any

from steuerbote.jahresmeldung.corrections import LABELS as REVISION_STATUSES
from steuerbote.jahresmeldung.overrides import to_amount
from steuerbote.steuerbote.doctype.annual_vat_return import layout as annual_vat_return

ASSETS = "bs.ass"
EQUITY_AND_LIABILITIES = "bs.eqLiab"
VALUE_TYPES = {"StB": "Steuerbilanzwert", "HB": "Handelsbilanzwert", "Überleitung": "Überleitungswert"}
STANDARDS = {
	"HAOE": "Einheitsbilanz (HAOE)",
	"HGBM": "Handelsbilanz mit Überleitungsrechnung (HGBM)",
	"AO": "Steuerbilanz (AO)",
}
"""The Bilanzierungsstandards as the head of the print names them (Technischer Leitfaden zur HGB-Taxonomie 6.9,
B.13)."""
DEPRECIATION_OF_THE_PERIOD = (
	"depreciation_regular",
	"depreciation_extraordinary",
	"depreciation_special",
	"depreciation_7g",
	"depreciation_6b",
	"depreciation_other",
)
COST_COLUMNS = (
	("cost_begin", "Anfang"),
	("additions", "Zugänge"),
	("disposals", "Abgänge"),
	("transfers", "Umbuchungen"),
	("cost_end", "Ende"),
)
DEPRECIATION_COLUMNS = (
	("depreciation_begin", "Anfang"),
	("depreciation_period", "des Jahres"),
	("depreciation_additions", "Zugänge"),
	("depreciation_disposals", "Abgänge"),
	("depreciation_transfers", "Umbuchungen"),
	("depreciation_end", "Ende"),
	("writeups", "Zuschreibungen"),
	("book_value_end", "Buchwert Ende"),
)
"""The columns of the two parts of the Anlagenspiegel as the print shows them, after the value development of the
taxonomy (Technischer Leitfaden zur HGB-Taxonomie 6.9, B.14.12.1) and § 284 Abs. 3 HGB: the Zugänge and Abgänge of
the Abschreibungen are those without effect on the result, „Kumulierte Abschreibungen, erfolgsneutrale Zugänge“ and
„... Abgänge“ of the taxonomy."""
ANLAGENSPIEGEL_COLUMNS = (*COST_COLUMNS, *DEPRECIATION_COLUMNS)

type Record = Mapping[str, Any]


def print_sections(
	positions: Iterable[Record],
	accounts: Iterable[Record] = (),
	fixed_assets: Iterable[Record] = (),
	transfers: Iterable[Record] = (),
	*,
	handelsbilanz: bool = False,
	accounting_standard: str = "",
	revision_status: str = "",
) -> dict[str, Any]:
	"""The sections of the print of an E-Bilanz from the rows of its tables."""
	shown = [row for row in positions if not row.get("nil")]
	parents = {str(row.get("parent_concept") or "") for row in shown}
	components: dict[str, list[dict[str, Any]]] = {"B": [], "GuV": [], "BVV": []}
	for row in shown:
		component = str(row.get("component") or "")
		if component in components:
			components[component].append(_position(row, parents, handelsbilanz))
	balance_sheet = components["B"]
	return {
		"standard": STANDARDS.get(accounting_standard, accounting_standard),
		"revision_status": REVISION_STATUSES.get(revision_status, revision_status),
		"handelsbilanz": handelsbilanz,
		"aktiva": _under(balance_sheet, ASSETS),
		"passiva": _under(balance_sheet, EQUITY_AND_LIABILITIES),
		"guv": components["GuV"],
		"bvv": components["BVV"],
		"anlagenspiegel": _anlagenspiegel(fixed_assets),
		"kontennachweis": _kontennachweis(accounts),
		"ueberleitung": [_transfer(row) for row in transfers],
	}


def german(amount: Decimal) -> str:
	"""An amount in euros and cents as the print shows it, as 1.234,56."""
	return annual_vat_return.german(amount, 2)


def _position(row: Record, parents: set[str], handelsbilanz: bool) -> dict[str, Any]:
	concept = str(row.get("concept") or "")
	return {
		"concept": concept,
		"label": row.get("label") or concept,
		"level": int(row.get("depth") or 0),
		"sum": concept in parents,
		"amount": german(to_amount(row.get("reported"))),
		"tax": german(to_amount(row.get("tax_amount"))) if handelsbilanz else "",
	}


def _under(rows: list[dict[str, Any]], top: str) -> list[dict[str, Any]]:
	"""The positions of one side of the Bilanz: the total and every position whose name lies under it."""
	return [row for row in rows if row["concept"] == top or row["concept"].startswith(f"{top}.")]


def _anlagenspiegel(rows: Iterable[Record]) -> dict[str, Any]:
	lines = []
	totals: dict[str, dict[str, Decimal]] = {}
	for row in rows:
		values = {
			name: to_amount(row.get(name))
			for name, _ in ANLAGENSPIEGEL_COLUMNS
			if name != "depreciation_period"
		}
		values["depreciation_period"] = sum(
			(to_amount(row.get(name)) for name in DEPRECIATION_OF_THE_PERIOD), Decimal(0)
		)
		kind = str(row.get("value_type") or "StB")
		total = totals.setdefault(kind, dict.fromkeys(values, Decimal(0)))
		for name, value in values.items():
			total[name] += value
		lines.append(
			{
				"label": row.get("position_label") or row.get("position") or "",
				"value_type": VALUE_TYPES.get(kind, kind),
				"source": row.get("asset_category") or ("Zeile von Hand" if row.get("manual") else ""),
				"reason": row.get("reason") or "",
				**_parts(values),
			}
		)
	return {
		"cost_columns": [label for _, label in COST_COLUMNS],
		"depreciation_columns": [label for _, label in DEPRECIATION_COLUMNS],
		"rows": lines,
		"totals": [
			{"value_type": VALUE_TYPES.get(kind, kind), **_parts(values)} for kind, values in totals.items()
		],
	}


def _parts(values: Mapping[str, Decimal]) -> dict[str, list[str]]:
	return {
		"cost": [german(values[name]) for name, _ in COST_COLUMNS],
		"depreciation": [german(values[name]) for name, _ in DEPRECIATION_COLUMNS],
	}


def _kontennachweis(rows: Iterable[Record]) -> list[dict[str, Any]]:
	"""The accounts of each position in the order of the Kontensalden, each position with the sum of its accounts."""
	groups: dict[str, dict[str, Any]] = {}
	for row in rows:
		position = str(row.get("position") or "")
		group = groups.setdefault(
			position,
			{
				"concept": position,
				"label": row.get("position_label") or position,
				"accounts": [],
				"sum": Decimal(0),
			},
		)
		amount = to_amount(row.get("amount"))
		group["accounts"].append(
			{
				"number": row.get("account_number") or "",
				"label": row.get("account_label") or "",
				"amount": german(amount),
			}
		)
		group["sum"] += amount
	return [{**group, "sum": german(group["sum"])} for group in groups.values()]


def _transfer(row: Record) -> dict[str, Any]:
	return {
		"kind": row.get("kind") or "",
		"label": row.get("position_label") or row.get("position") or "",
		"concept": row.get("position") or "",
		"current": german(to_amount(row.get("current"))),
		"previous": german(to_amount(row.get("previous"))),
		"reason": row.get("reason") or "",
	}
