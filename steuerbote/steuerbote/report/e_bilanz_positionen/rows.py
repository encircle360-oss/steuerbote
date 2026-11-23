"""The rows of the report „E-Bilanz Positionen“: the positions of an E-Bilanz as a tree, each with the accounts behind
it, and the comparison of its Umsatzerlöse with the Voranmeldungen of the year.

report_rows() takes the tables of the E-Bilanz as Berechnen wrote them: each position under the position above it in
the presentation of the HGB-Taxonomie (parent_concept), and under each position the Kontensalden of the accounts that
go to it, in the direction of the position (steuerbote/ebilanz/kontennachweis.py), so that a position opens to the
accounts it consists of. A position reported as NIL has neither amount nor accounts and is left out.

revenue() sets the Umsatzerlöse of the GuV in the Gesamtkostenverfahren, „Umsatzerlöse (GKV)“
[is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales], against the Kennzahlen of the Voranmeldungen
filed for the year that hold sales without the tax, as filed after the corrections of the company: Kz 81
„Steuerpflichtige Umsätze zum Steuersatz von 19 %“, Kz 86 „... von 7 %“, Kz 41 „Innergemeinschaftliche Lieferungen
(§ 4 Nummer 1 Buchstabe b UStG) an Abnehmer mit Umsatzsteuer-Identifikationsnummer“ and Kz 45 „Übrige nicht steuerbare
Umsätze (Leistungsort nicht im Inland)“ (Vordruck USt 1 A 2026, BMF letter of 29 December 2025, GZ III C 3 - S
7344/00039/007/036; steuerbote/ustva/kennzahlen.py). A Voranmeldung reports each of them in whole euros, with the cents
cut off (steuerbote/ustva/rounding.py), so up to one euro per filed amount is no difference. Beyond that the report gives a hint: the Umsatzerlöse also hold sales of other Kennzahlen, such as
steuerfreie Ausfuhren (Kz 43) or sonstige Leistungen in the EU (Kz 21), and the Voranmeldungen take the sales of their
periods as the books stood then; whether the difference is explained, the company decides.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from steuerbote.jahresmeldung.overrides import to_amount
from steuerbote.ustjahr.soll import Filed

REVENUE = "is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales"
KENNZAHLEN = ("81", "86", "41", "45")
ONE_EURO = Decimal("1.00")
DIFFERENT = (
	"The Umsatzerlöse of the E-Bilanz are {0}, the Kz 81, 86, 41 and 45 of the {1} Voranmeldungen filed for the year "
	"{2}: a difference of {3}. Other Kennzahlen such as Kz 43 or Kz 21 and postings after a Voranmeldung explain such a "
	"difference; check it."
)
NOT_FILED = "No Voranmeldung of the year is filed, so the Umsatzerlöse of {0} are compared with none."
MESSAGES = (DIFFERENT, NOT_FILED)

type Record = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Revenue:
	"""The Umsatzerlöse of the E-Bilanz and the sum of Kz 81, 86, 41 and 45 of the filed Voranmeldungen of the year,
	with the number of those Voranmeldungen and of the amounts they filed of these Kennzahlen."""

	ebilanz: Decimal
	voranmeldungen: Decimal
	filed: int
	amounts: int

	@property
	def difference(self) -> Decimal:
		return self.ebilanz - self.voranmeldungen

	@property
	def explained_by_rounding(self) -> bool:
		"""Whether the difference is no more than the cents each filed amount cuts off."""
		return abs(self.difference) <= ONE_EURO * self.amounts


def report_rows(positions: Iterable[Record], accounts: Iterable[Record]) -> list[dict[str, Any]]:
	"""The positions with an amount as a tree, each with the accounts behind it as its children."""
	shown = [row for row in positions if not row.get("nil")]
	keys = {str(row.get("concept")) for row in shown}
	sums = {str(row.get("parent_concept") or "") for row in shown}
	by_position: dict[str, list[Record]] = {}
	for account in accounts:
		by_position.setdefault(str(account.get("position") or ""), []).append(account)
	indents: dict[str, int] = {}
	rows = []
	for row in shown:
		concept = str(row.get("concept"))
		parent = str(row.get("parent_concept") or "")
		parent = parent if parent in keys else None
		indent = indents.get(parent, -1) + 1 if parent else 0
		indents[concept] = indent
		rows.append(
			{
				"key": concept,
				"parent_key": parent,
				"indent": indent,
				"label": row.get("label") or "",
				"component": row.get("component") or "",
				"mark": row.get("mark") or "",
				"ledger_amount": to_amount(row.get("ledger_amount")),
				"reported": to_amount(row.get("reported")),
				"account": None,
				"account_number": None,
				"bold": int(concept in sums),
			}
		)
		for account in by_position.get(concept, ()):
			rows.append(
				{
					"key": f"{concept}:{account.get('account_number')}",
					"parent_key": concept,
					"indent": indent + 1,
					"label": account.get("account_label") or "",
					"component": row.get("component") or "",
					"mark": "",
					"ledger_amount": to_amount(account.get("amount")),
					"reported": to_amount(account.get("amount")),
					"account": account.get("account"),
					"account_number": account.get("account_number"),
					"bold": 0,
				}
			)
	return rows


def revenue(positions: Iterable[Record], filed: Iterable[Filed]) -> Revenue | None:
	"""The Umsatzerlöse of the E-Bilanz against the Voranmeldungen filed for the year; None for an E-Bilanz without a
	GuV, such as an Eröffnungsbilanz."""
	row = next((row for row in positions if row.get("concept") == REVENUE), None)
	if row is None:
		return None
	filed = tuple(filed)
	values = [
		entry.lines[kennzahl].final for entry in filed for kennzahl in KENNZAHLEN if kennzahl in entry.lines
	]
	return Revenue(to_amount(row.get("reported")), sum(values, Decimal(0)), len(filed), len(values))


def revenue_note(found: Revenue | None) -> tuple[str, tuple[object, ...]] | None:
	"""The hint of the report, as a template and its values: none where the Umsatzerlöse and the Voranmeldungen agree
	but for the cents they cut off, or where the E-Bilanz has no GuV."""
	if found is None:
		return None
	if not found.filed:
		return NOT_FILED, (found.ebilanz,)
	if found.explained_by_rounding:
		return None
	return DIFFERENT, (found.ebilanz, found.filed, found.voranmeldungen, found.difference)
