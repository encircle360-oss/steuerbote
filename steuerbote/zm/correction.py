"""The berichtigte Zusammenfassende Meldung: which lines it holds, and which Meldezeitraum it corrects.

„Erkennt der Unternehmer nachträglich, dass eine von ihm abgegebene Zusammenfassende Meldung unrichtig oder
unvollständig ist, so ist er verpflichtet, die ursprüngliche Zusammenfassende Meldung innerhalb eines Monats zu
berichtigen“ (§ 18a Absatz 10 UStG). The BZSt describes the form („Berichtigung einer ZM“): „Für jeden zu
berichtigenden Meldezeitraum ist eine gesonderte berichtigte ZM elektronisch zu übermitteln. Korrekt gemeldete
Angaben sind in der berichtigten ZM nicht zu wiederholen.“ A missing line is added, a wrong sum is replaced by
the right one, „nicht nur der zu viel oder zu wenig gemeldete Differenzbetrag“ (Anleitung zur ZM, IV.12.2),
and a line under a wrong USt-IdNr., Art or Meldezeitraum is cancelled with „0“ in the Meldezeitraum it was filed
for, the right line being reported where it belongs (IV.12 and IV.12.3; BZSt cases 1 to 5).

So a correction compares what the BZSt holds for the Meldezeitraum, after the original ZM and any earlier
correction, with the lines computed now: a line that is new or changed carries its new sum, a line that is gone
carries 0, and an unchanged line is left out. A discount, a Skonto or a receivable written off is no correction:
„Der geänderte Umsatz ist in dem Monat zu erklären, in dem die Änderung eingetreten ist“ (BZSt, Rabatte); the
ledger books it then, and the ZM of that period reports it.
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from decimal import Decimal

from steuerbote.ustva.rounding import ZERO
from steuerbote.zm.errors import ZmError
from steuerbote.zm.lines import Art, Meldezeile
from steuerbote.zm.period import ReportingPeriod

LINE_TWICE = "The line {0} {1} appears twice in one Zusammenfassende Meldung."


@dataclass(frozen=True, slots=True)
class Correction:
	"""A berichtigte ZM for ``period``: the Meldezeilen that change what was filed for it, cancelled lines first."""

	period: ReportingPeriod
	lines: tuple[Meldezeile, ...]


def as_filed(*filings: Iterable[Meldezeile]) -> dict[tuple[str, Art], Decimal]:
	"""What the BZSt holds for a Meldezeitraum: the sum of each line after the original ZM and its corrections,
	given in the order they were filed, each line of a later one replacing the sum of its key."""
	held: dict[tuple[str, Art], Decimal] = {}
	for filing in filings:
		held.update(_by_key(filing))
	return held


def correct(
	period: ReportingPeriod, filed: ReadOnlyMapping[tuple[str, Art], Decimal], current: Iterable[Meldezeile]
) -> Correction:
	"""The correction of ``period`` from what was filed for it (as_filed()) and the Meldezeilen computed now."""
	now = _by_key(current)
	cancelled = [Meldezeile(*key, ZERO) for key, amount in filed.items() if amount and key not in now]
	changed = [Meldezeile(*key, amount) for key, amount in now.items() if filed.get(key) != amount]
	return Correction(period, (*cancelled, *changed))


def _by_key(lines: Iterable[Meldezeile]) -> dict[tuple[str, Art], Decimal]:
	found: dict[tuple[str, Art], Decimal] = {}
	for line in lines:
		if line.key in found:
			raise ZmError(LINE_TWICE, *line.key)
		found[line.key] = line.amount
	return found
