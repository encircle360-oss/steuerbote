"""Which Meldezeitraum a company files its Zusammenfassende Meldung for, month by month.

§ 18a Absatz 1 UStG makes the Kalendermonat the Meldezeitraum of the innergemeinschaftliche Warenlieferungen and
the Lieferungen im Sinne des § 25b Absatz 2 (Art L and D). The company may file per Kalendervierteljahr „Soweit
die Summe der Bemessungsgrundlagen [...] weder für das laufende Kalendervierteljahr noch für eines der vier
vorangegangenen Kalendervierteljahre jeweils mehr als 50 000 Euro beträgt“ (Satz 2). When the sum exceeds
50,000 euros in the course of a quarter, the ZM is due „bis zum 25. Tag nach Ablauf des Kalendermonats, in dem
dieser Betrag überschritten wird, [...] für diesen Kalendermonat und die bereits abgelaufenen Kalendermonate
dieses Kalendervierteljahres“ (Satz 3), and monthly from then on (BZSt, „Fristen“ of the ZM). A company exempt
from the Voranmeldungen with little EU trade may file per Kalenderjahr (Absatz 9).

The sonstige Leistungen (Art S) are due per Kalendervierteljahr (Absatz 2 Satz 1). A company that files monthly
reports them „in der Zusammenfassenden Meldung für den letzten Monat des Kalendervierteljahres“ (Absatz 2 Satz 2)
or, after an Anzeige, „in die Meldung für den jeweiligen Meldezeitraum“ (Absatz 3).

The company records its rhythm as rules: from a year and month on, monthly, quarterly or yearly, and for monthly
whether the sonstige Leistungen go into each month. A rule holds until the next one starts. A quarter starts in
month 1, 4, 7 or 10 and a year in January; a monthly rule may start in any month, and one that starts in the
middle of a quarter after a quarterly rule makes its first ZM cover the quarter up to its month, as Satz 3 wants.
The rules come from the company, which knows its Anzeigen; the ledger can only show that a quarterly or yearly
rule breaks the threshold, which threshold_findings() reports.
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from itertools import pairwise

from steuerbote.ustva.calculation import require_cents
from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import ZERO
from steuerbote.zm.errors import ZmError
from steuerbote.zm.findings import Code, Finding
from steuerbote.zm.period import QUARTER_START_MONTHS, Kind, ReportingPeriod, quarter_start

THRESHOLD = Decimal("50000")
PREVIOUS_QUARTERS = 4

NOT_A_YEAR = "{0} is not a four-digit year."
NOT_A_MONTH = "{0} is not a month."
NOT_A_RHYTHM = "{0} is not a rhythm of the Zusammenfassende Meldung: choose monthly, quarterly or yearly."
NOT_A_QUARTER_START = "A quarterly Zusammenfassende Meldung starts with a quarter, in month 1, 4, 7 or 10, not in month {1} of {0}."
NOT_A_YEAR_START = "A yearly Zusammenfassende Meldung starts in January, not in month {1} of {0}."
SERVICES_MONTHLY_ONLY = (
	"Sonstige Leistungen go into each Zusammenfassende Meldung only when it is filed monthly, "
	"not from month {1} of {0}."
)
DUPLICATE_RULE = "The rhythm of the Zusammenfassende Meldung from month {1} of {0} is entered twice."
YEAR_NOT_WHOLE = "A yearly Zusammenfassende Meldung covers the calendar year {0}, so no rule can start in month {2} of {1}."
NO_RULE = "No rhythm of the Zusammenfassende Meldung is set for month {1} of {0}."
NO_REPORTING_PERIOD = "The rules of the company give no Zusammenfassende Meldung for {0}."
ANZEIGE_AND_WIDERRUF = "A Zusammenfassende Meldung cannot carry both the Anzeige and its Widerruf."
ANZEIGE_ONLY_MONTHLY = (
	"The Anzeige of § 18a Absatz 1 UStG comes only with a monthly Zusammenfassende Meldung, not with {0}."
)
WIDERRUF_ONLY_QUARTERLY = (
	"The Widerruf of the Anzeige comes only with the Zusammenfassende Meldung of a quarter or of the third month of "
	"a quarter, not with {0}."
)


class Rhythm(Enum):
	MONTHLY = "monthly"
	QUARTERLY = "quarterly"
	YEARLY = "yearly"


@dataclass(frozen=True, slots=True)
class Rule:
	"""From ``month`` of ``year`` on, the company files its ZM in ``rhythm``; with ``services_monthly`` a monthly
	ZM reports the sonstige Leistungen of its own month (§ 18a Absatz 3 UStG)."""

	year: int
	month: int
	rhythm: Rhythm
	services_monthly: bool = False

	def __post_init__(self) -> None:
		if not _is_int(self.year) or not 1000 <= self.year <= 9999:
			raise ZmError(NOT_A_YEAR, self.year)
		_require_month(self.month)
		try:
			object.__setattr__(self, "rhythm", Rhythm(self.rhythm))
		except ValueError:
			raise ZmError(NOT_A_RHYTHM, self.rhythm) from None
		if not isinstance(self.services_monthly, bool):
			raise TypeError(f"services_monthly must be a bool, not {type(self.services_monthly).__name__}")
		if self.rhythm is Rhythm.QUARTERLY and self.month not in QUARTER_START_MONTHS:
			raise ZmError(NOT_A_QUARTER_START, self.year, self.month)
		if self.rhythm is Rhythm.YEARLY and self.month != 1:
			raise ZmError(NOT_A_YEAR_START, self.year, self.month)
		if self.services_monthly and self.rhythm is not Rhythm.MONTHLY:
			raise ZmError(SERVICES_MONTHLY_ONLY, self.year, self.month)

	@property
	def start(self) -> tuple[int, int]:
		return (self.year, self.month)


@dataclass(frozen=True, slots=True)
class Coverage:
	"""The months of ``period.year`` whose lines a ZM reports: Art L and D of ``goods``, Art S of ``services``."""

	period: ReportingPeriod
	goods: tuple[int, ...]
	services: tuple[int, ...]

	@property
	def goods_span(self) -> tuple[date, date]:
		return _span(self.period.year, self.goods)

	@property
	def services_span(self) -> tuple[date, date] | None:
		return _span(self.period.year, self.services) if self.services else None


def check_rules(rules: Iterable[Rule]) -> None:
	"""Refuse two rules with the same start, and a rule that starts within the year of a yearly rule."""
	ordered = sorted(rules, key=lambda rule: rule.start)
	for before, after in pairwise(ordered):
		if before.start == after.start:
			raise ZmError(DUPLICATE_RULE, *after.start)
		if before.rhythm is Rhythm.YEARLY and after.year == before.year:
			raise ZmError(YEAR_NOT_WHOLE, before.year, *after.start)


def rule_for(rules: Iterable[Rule], year: int, month: int) -> Rule:
	"""The rule of a month: the latest that starts in or before it."""
	rule = _rule_or_none(rules, year, month)
	if rule is None:
		raise ZmError(NO_RULE, year, month)
	return rule


def goods_period(rules: Iterable[Rule], year: int, month: int) -> ReportingPeriod:
	"""The Meldezeitraum of the Lieferungen (Art L and D) of a month."""
	rules = tuple(rules)
	rule = rule_for(rules, year, month)
	if rule.rhythm is Rhythm.YEARLY:
		return ReportingPeriod.calendar_year(year)
	first = quarter_start(month)
	switch = _switch_to_monthly(rules, year, first)
	if rule.rhythm is Rhythm.QUARTERLY:
		return ReportingPeriod(year, first, switch or first + 2)
	if month == switch:
		return ReportingPeriod(year, first, month)
	return ReportingPeriod.month(year, month)


def services_period(rules: Iterable[Rule], year: int, month: int) -> ReportingPeriod:
	"""The Meldezeitraum of the sonstige Leistungen (Art S) of a month.

	Whether they go into each monthly ZM is decided by the rule of the last month of the quarter, so that all
	sonstige Leistungen of a quarter follow the same rule.
	"""
	rules = tuple(rules)
	last = quarter_start(month) + 2
	closing = rule_for(rules, year, last)
	if closing.rhythm is Rhythm.MONTHLY and closing.services_monthly:
		return goods_period(rules, year, month)
	return goods_period(rules, year, last)


def coverage(rules: Iterable[Rule], period: ReportingPeriod) -> Coverage:
	"""The months whose lines the ZM for ``period`` reports, or ZmError if the rules give no ZM for it."""
	rules = tuple(rules)
	check_rules(rules)
	candidates = [
		month
		for month in range(quarter_start(period.first_month), period.last_month + 1)
		if _rule_or_none(rules, period.year, month) is not None
	]
	goods = tuple(month for month in candidates if goods_period(rules, period.year, month) == period)
	if not goods:
		raise ZmError(NO_REPORTING_PERIOD, period.label)
	services = tuple(month for month in candidates if services_period(rules, period.year, month) == period)
	return Coverage(period, goods, services)


def check_notices(period: ReportingPeriod, anzeige: bool, widerruf: bool) -> None:
	"""Refuse an Anzeige or a Widerruf after § 18a Absatz 1 UStG that the ZM for ``period`` cannot carry.

	ZMDO takes the Anzeige only in a monthly ZM (rule 170015008), the Widerruf only in the ZM of a quarter or of
	the third month of a quarter (170015012), and not both at once (170015013).
	"""
	if anzeige and widerruf:
		raise ZmError(ANZEIGE_AND_WIDERRUF)
	if anzeige and period.kind is not Kind.MONTH:
		raise ZmError(ANZEIGE_ONLY_MONTHLY, period.label)
	closes_quarter = period.kind is Kind.QUARTER or (period.kind is Kind.MONTH and period.last_month % 3 == 0)
	if widerruf and not closes_quarter:
		raise ZmError(WIDERRUF_ONLY_QUARTERLY, period.label)


def exceeded_in(deliveries: ReadOnlyMapping[tuple[int, int], Decimal], year: int, quarter: int) -> int | None:
	"""The month in which the Lieferungen of a quarter, added up month by month, first exceed 50,000 euros.

	``deliveries`` holds the exact amounts of Kz 41 and 42 together by year and month, as the ledger gives them.
	„mehr als 50 000 Euro“: 50,000 euros are not more.
	"""
	total = ZERO
	for month in _months(year, quarter):
		total += _delivered(deliveries, year, month)
		if total > THRESHOLD:
			return month
	return None


def threshold_window(period: ReportingPeriod) -> tuple[date, date]:
	"""The first and last day of the months whose Lieferungen threshold_findings() reads for ``period``."""
	year, quarter = _quarter_before(period.year, (period.first_month - 1) // 3 + 1, PREVIOUS_QUARTERS)
	return date(year, (quarter - 1) * 3 + 1, 1), period.end


def threshold_findings(
	rules: Iterable[Rule],
	period: ReportingPeriod,
	deliveries: ReadOnlyMapping[tuple[int, int], Decimal],
	figures: Figures,
) -> tuple[Finding, ...]:
	"""Errors where the rules give a quarterly or yearly ZM although the Lieferungen exceed 50,000 euros.

	A quarterly rule breaks the threshold when its quarter exceeds it before its last month, since the first
	monthly ZM is then due for fewer months; an excess in the last month gives the same months and deadline as the
	quarter. A yearly rule breaks it with any excess, since § 18a Absatz 1 Satz 2 and 3 UStG then wants the ZM
	monthly from the month of the excess on; the narrower limits of the yearly ZM itself, such as the 15,000 euros
	a year of Absatz 9 Nummer 2, are not checked here. Either breaks it when one of the four previous quarters
	exceeded it (Absatz 1 Satz 2). One finding per quarter, in their order.
	"""
	rules = tuple(rules)
	found: dict[tuple[int, int], Finding] = {}
	for year, quarter in _quarters_not_filed_monthly(rules, period):
		crossing = exceeded_in(deliveries, year, quarter)
		if crossing is not None:
			rhythm = rule_for(rules, year, crossing).rhythm
			if rhythm is Rhythm.YEARLY or (rhythm is Rhythm.QUARTERLY and crossing < quarter * 3):
				found[(year, quarter)] = _crossing(year, quarter, crossing, deliveries, figures)
		for back in range(1, PREVIOUS_QUARTERS + 1):
			earlier = _quarter_before(year, quarter, back)
			total = sum((_delivered(deliveries, earlier[0], month) for month in _months(*earlier)), ZERO)
			if total > THRESHOLD and earlier not in found:
				found[earlier] = _excess(earlier, total, figures)
	return tuple(found[key] for key in sorted(found))


def _crossing(
	year: int,
	quarter: int,
	crossing: int,
	deliveries: ReadOnlyMapping[tuple[int, int], Decimal],
	figures: Figures,
) -> Finding:
	first = (quarter - 1) * 3 + 1
	total = sum((_delivered(deliveries, year, month) for month in range(first, crossing + 1)), ZERO)
	month = ReportingPeriod.month(year, crossing).label
	text = (
		f"Im {ReportingPeriod.quarter(year, quarter).label} ergeben Kz 41 und 42 bis {month} zusammen "
		f"{figures.money(total)}, mehr als {figures.money(THRESHOLD)}. Ab {month} ist die ZM deshalb monatlich "
		f"abzugeben, die erste für den Meldezeitraum {ReportingPeriod(year, first, crossing).label} "
		"(§ 18a Absatz 1 Satz 3 UStG)."
	)
	return Finding(Code.THRESHOLD, text)


def _excess(quarter: tuple[int, int], total: Decimal, figures: Figures) -> Finding:
	until = ReportingPeriod.quarter(*_quarter_before(*quarter, -PREVIOUS_QUARTERS)).label
	text = (
		f"Im {ReportingPeriod.quarter(*quarter).label} ergeben Kz 41 und 42 zusammen {figures.money(total)}, mehr "
		f"als {figures.money(THRESHOLD)}. Bis einschließlich {until} ist die ZM deshalb monatlich abzugeben "
		"(§ 18a Absatz 1 Satz 2 UStG)."
	)
	return Finding(Code.THRESHOLD, text)


def _quarters_not_filed_monthly(rules: tuple[Rule, ...], period: ReportingPeriod) -> list[tuple[int, int]]:
	quarters = {
		(period.year, (month - 1) // 3 + 1)
		for month in coverage(rules, period).goods
		if rule_for(rules, period.year, month).rhythm is not Rhythm.MONTHLY
	}
	return sorted(quarters)


def _switch_to_monthly(rules: tuple[Rule, ...], year: int, first: int) -> int | None:
	"""The month in which a monthly rule cuts the quarter starting in ``first`` short after a quarterly rule.

	Only a monthly rule can start in the middle of a quarter, so the first rule there is one.
	"""
	opening = _rule_or_none(rules, year, first)
	if opening is None or opening.rhythm is not Rhythm.QUARTERLY:
		return None
	later = [rule.month for rule in rules if rule.year == year and first < rule.month <= first + 2]
	return min(later, default=None)


def _rule_or_none(rules: Iterable[Rule], year: int, month: int) -> Rule | None:
	_require_month(month)
	started = [rule for rule in rules if rule.start <= (year, month)]
	return max(started, key=lambda rule: rule.start) if started else None


def _quarter_before(year: int, quarter: int, back: int) -> tuple[int, int]:
	"""The quarter ``back`` quarters before, or after for a negative ``back``."""
	index = year * 4 + quarter - 1 - back
	return index // 4, index % 4 + 1


def _delivered(deliveries: ReadOnlyMapping[tuple[int, int], Decimal], year: int, month: int) -> Decimal:
	return require_cents(deliveries.get((year, month), ZERO))


def _months(year: int, quarter: int) -> range:
	first = (quarter - 1) * 3 + 1
	return range(first, first + 3)


def _span(year: int, months: tuple[int, ...]) -> tuple[date, date]:
	return ReportingPeriod.month(year, months[0]).start, ReportingPeriod.month(year, months[-1]).end


def _require_month(month: object) -> None:
	if not _is_int(month) or not 1 <= month <= 12:
		raise ZmError(NOT_A_MONTH, month)


def _is_int(value: object) -> bool:
	"""True is an int to Python, but neither a year nor a month."""
	return isinstance(value, int) and not isinstance(value, bool)
