"""The lines of a Zusammenfassende Meldung beside those of the previous Meldezeitraum: hints, nothing more.

The previous Meldezeitraum is the one of the same kind before (ReportingPeriod.previous()). Its lines come from
the ledger in the same way as those of the ZM itself, not from an earlier ZM, just as the Vorperiodenvergleich of
the Voranmeldung reads the ledger and not earlier returns. Each line that either period reports is set against
the other; a line whose change the caller's rule finds auffällig gets a hint. The Frappe layer passes the rule of the report „UStVA Kennzahlen“,
Thresholds.exceeded of steuerbote.steuerbote.report.ustva_kennzahlen.comparison, with the thresholds of the VAT
Return Settings. A hint never holds the ZM back.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import HUNDRED, ZERO, to_cents
from steuerbote.zm.findings import Code, Finding
from steuerbote.zm.lines import Art, Statement, line_order
from steuerbote.zm.period import ReportingPeriod


@dataclass(frozen=True, slots=True)
class ComparisonRow:
	"""A line as this and the previous Meldezeitraum report it, 0 where a period does not."""

	vat_id: str
	art: Art
	current: Decimal
	previous: Decimal
	flagged: bool

	@property
	def difference(self) -> Decimal:
		return self.current - self.previous

	@property
	def difference_percent(self) -> Decimal | None:
		"""The difference in percent of the previous amount, rounded to hundredths; None without one."""
		return to_cents(self.difference * HUNDRED / abs(self.previous)) if self.previous else None


def compare(
	current: Statement, previous: Statement, deviates: Callable[[Decimal, Decimal], bool]
) -> tuple[ComparisonRow, ...]:
	"""A row per Meldezeile of either statement, ordered as the statements order their lines."""
	now = {line.key: line.amount for line in current.meldezeilen}
	before = {line.key: line.amount for line in previous.meldezeilen}
	rows = []
	for key in sorted(now.keys() | before.keys(), key=line_order):
		amount, earlier = now.get(key, ZERO), before.get(key, ZERO)
		rows.append(ComparisonRow(*key, amount, earlier, deviates(amount, earlier)))
	return tuple(rows)


def comparison_hints(
	rows: tuple[ComparisonRow, ...], previous_period: ReportingPeriod, figures: Figures
) -> tuple[Finding, ...]:
	return tuple(_hint(row, previous_period, figures) for row in rows if row.flagged)


def _hint(row: ComparisonRow, previous_period: ReportingPeriod, figures: Figures) -> Finding:
	direction = "über" if row.difference > ZERO else "unter"
	share = "" if row.difference_percent is None else f" um {figures.percent(abs(row.difference_percent))}"
	earlier = f"der Vorperiode {previous_period.label} ({figures.money(row.previous)})"
	text = f"Die Zeile {row.vat_id} ({row.art.value}) liegt mit {figures.money(row.current)}{share} {direction} {earlier}."
	return Finding(Code.PREVIOUS_PERIOD, text)
