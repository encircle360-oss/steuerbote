"""The Einlagen of a Wirtschaftsjahr as the books show them, for the steuerlicher Betriebsvermögensvergleich.

„Gewinn ist der Unterschiedsbetrag zwischen dem Betriebsvermögen am Schluss des Wirtschaftsjahres und dem
Betriebsvermögen am Schluss des vorangegangenen Wirtschaftsjahres, vermehrt um den Wert der Entnahmen und vermindert um
den Wert der Einlagen.“ „Einlagen sind alle Wirtschaftsgüter (Bareinzahlungen und sonstige Wirtschaftsgüter), die der
Steuerpflichtige dem Betrieb im Laufe des Wirtschaftsjahres zugeführt hat“ (§ 4 Abs. 1 Satz 1 und 8 EStG), for a
corporation through § 8 Abs. 1 KStG. No year is excepted: in the founding year the Betriebsvermögen at the start is
zero, and the Stammkapital paid in is an Einlage like a later capital increase or a payment into the Kapitalrücklage
(§ 272 Abs. 1 and Abs. 2 Nr. 1 and 4 HGB). The taxonomy reports them under „Einlagen / Kapitalzuführungen im laufenden
Wirtschaftsjahr“ of the Betriebsvermögensvergleich (BVV.contribution, HGB-Taxonomie 6.9).

What the books show of them: the capital an entry of the year credits to the gezeichnetes Kapital, to the Stammkapital
not called in or to the Kapitalrücklage, as the Bilanzzuordnung places the accounts, as far as the entry brings it in
from outside the Eigenkapital. Per voucher that is the smaller of the net credit on these accounts and the net credit on
the whole Eigenkapital, never below zero: a Kapitalerhöhung aus Gesellschaftsmitteln, a release of the Kapitalrücklage
or the Stammkapital subscribed but not called in moves nothing in, a payment of capital not called in does, and a
called-in claim on the shareholder is a Wirtschaftsgut of the company when it arises (§ 272 Abs. 1 Satz 2 und 3 HGB).
What the books cannot show, such as a verdeckte Einlage booked as income (§ 8 Abs. 3 Satz 3 KStG) or a Sacheinlage at
another value than the Teilwert (§ 6 Abs. 1 Nr. 5 EStG), the company adds by hand.

This module is pure Python and never imports Frappe.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from steuerbote.ustva.rounding import ZERO, to_cents

EQUITY = "bs.eqLiab.equity."
CAPITAL = ("bs.eqLiab.equity.subscribed.", "bs.eqLiab.equity.capRes")
"""The positions of the capital paid in: gezeichnetes Kapital, the Stammkapital not called in and the
Kapitalrücklage."""


@dataclass(frozen=True, slots=True)
class Line:
	"""What a voucher of the year books on an account, by its number."""

	voucher: str
	account: str
	debit: Decimal
	credit: Decimal


def booked_contributions(lines: Iterable[Line], concepts: Mapping[str, str | None]) -> Decimal:
	"""The Einlagen the vouchers book, with the position of each account (``concepts``, with or without the prefix of
	the GAAP module; an account without one counts outside the Eigenkapital)."""
	equity: dict[str, Decimal] = defaultdict(lambda: ZERO)
	capital: dict[str, Decimal] = defaultdict(lambda: ZERO)
	for line in lines:
		concept = _plain(concepts.get(line.account))
		movement = line.credit - line.debit
		if concept.startswith(EQUITY):
			equity[line.voucher] += movement
			if concept.startswith(CAPITAL):
				capital[line.voucher] += movement
	return to_cents(sum((max(ZERO, min(capital[voucher], equity[voucher])) for voucher in capital), ZERO))


def _plain(concept: str | None) -> str:
	return (concept or "").rpartition(":")[2]
