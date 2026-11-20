"""The lines of a Zusammenfassende Meldung beside those of an earlier Meldezeitraum: hints, nothing more.

The Lieferungen (Art L and D) compare with the previous Meldezeitraum of the same kind (ReportingPeriod.previous()).
The sonstige Leistungen (Art S) compare with the last earlier Meldezeitraum of the same kind that reports
sonstige Leistungen, and only where the ZM reports them itself: a monthly ZM without „sonstige Leistungen
monatlich“ reports them only „in der Zusammenfassenden Meldung für den letzten Monat des Kalendervierteljahres“
(§ 18a Absatz 2 Satz 2 UStG), so the ZM for June, which holds those of April to June, compares them with the ZM
for March, and the ZM for July holds and compares none. The earlier lines come from the ledger in the same way as
those of the ZM itself, not from an earlier ZM, just as the Vorperiodenvergleich of the Voranmeldung reads the
ledger and not earlier returns. Each line that either period reports is set against the other; a line whose
change the caller's rule finds auffällig gets a hint. The Frappe layer passes the rule of the report „UStVA
Kennzahlen“, Thresholds.exceeded of steuerbote.steuerbote.report.ustva_kennzahlen.comparison, with the thresholds
of the VAT Return Settings. A hint never holds the ZM back.
"""

from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from decimal import Decimal

from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import HUNDRED, ZERO, to_cents
from steuerbote.zm.findings import Code, Finding
from steuerbote.zm.lines import ART_ORDER, Art, Statement, line_order
from steuerbote.zm.period import ReportingPeriod
from steuerbote.zm.rhythm import Coverage, Rule, coverage_or_months


@dataclass(frozen=True, slots=True)
class ComparisonRow:
	"""A line as this and the earlier Meldezeitraum report it, 0 where a period does not."""

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


@dataclass(frozen=True, slots=True)
class Earlier:
	"""The earlier Meldezeiträume the lines of a ZM are set against, with the months whose lines they hold:
	``goods`` for the Lieferungen, ``services`` for the sonstige Leistungen, None where the ZM reports none."""

	goods: Coverage
	services: Coverage | None

	@property
	def arts(self) -> tuple[Art, ...]:
		"""The Arts that have an earlier Meldezeitraum to compare with."""
		return ART_ORDER if self.services else (Art.L, Art.D)

	def period(self, art: Art) -> ReportingPeriod:
		"""The Meldezeitraum the lines of ``art`` are set against; for Art S without one, that of the Lieferungen."""
		return self.services.period if art is Art.S and self.services else self.goods.period


def earlier(rules: Iterable[Rule], current: Coverage) -> Earlier:
	"""The Meldezeiträume the ZM of ``current`` is set against, with the months the rules give them; a
	Meldezeitraum the rules give no ZM for, such as one before their first rule, counts with all its months."""
	rules = tuple(rules)
	goods = coverage_or_months(rules, current.period.previous())
	if not current.services:
		return Earlier(goods, None)
	services = goods
	while not services.services:
		services = coverage_or_months(rules, services.period.previous())
	return Earlier(goods, services)


def compare(
	current: Statement,
	previous: Statement,
	deviates: Callable[[Decimal, Decimal], bool],
	arts: Collection[Art] = ART_ORDER,
) -> tuple[ComparisonRow, ...]:
	"""A row per Meldezeile of the Arts in ``arts`` of either statement, ordered as the statements order their
	lines."""
	now = {line.key: line.amount for line in current.meldezeilen if line.art in arts}
	before = {line.key: line.amount for line in previous.meldezeilen if line.art in arts}
	rows = []
	for key in sorted(now.keys() | before.keys(), key=line_order):
		amount, earlier_amount = now.get(key, ZERO), before.get(key, ZERO)
		rows.append(ComparisonRow(*key, amount, earlier_amount, deviates(amount, earlier_amount)))
	return tuple(rows)


def comparison_hints(
	rows: tuple[ComparisonRow, ...], before: Earlier, figures: Figures
) -> tuple[Finding, ...]:
	return tuple(_hint(row, before.period(row.art), figures) for row in rows if row.flagged)


def _hint(row: ComparisonRow, previous_period: ReportingPeriod, figures: Figures) -> Finding:
	direction = "über" if row.difference > ZERO else "unter"
	share = "" if row.difference_percent is None else f" um {figures.percent(abs(row.difference_percent))}"
	earlier_text = f"der Vorperiode {previous_period.label} ({figures.money(row.previous)})"
	text = f"Die Zeile {row.vat_id} ({row.art.value}) liegt mit {figures.money(row.current)}{share} {direction} {earlier_text}."
	return Finding(Code.PREVIOUS_PERIOD, text)
