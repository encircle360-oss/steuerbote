"""Pure Python between the VAT Return Extension document and the core in steuerbote.dauerfrist.

Nothing here imports Frappe. The module picks the filed VAT Returns of the previous year whose Kz 83 and Kz 39
make the base of the Sondervorauszahlung, with the Voranmeldungen filed before Steuerbote for the periods no VAT
Return covers (steuerbote/setup/start.py), names the Voranmeldungszeiträume the base lacks, hands base and
Kz 38 to the core and builds form USt 1 H from the values of the document, so that the controller only moves
data and every rule is tested without a bench.
"""

from collections.abc import Iterable, Sequence
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from steuerbote import dauerfrist
from steuerbote.dauerfrist import Context, Ust1H
from steuerbote.setup import start
from steuerbote.steuerbote.doctype.vat_return.bridge import Row, to_amount
from steuerbote.steuerbote.doctype.vat_return_settings import rules
from steuerbote.ustva import Period
from steuerbote.ustva.rounding import ZERO

MONTHS_PER_YEAR = 12


@dataclass(frozen=True, slots=True)
class FiledReturn:
	"""A VAT Return as filed: its Voranmeldungszeitraum, its name, its Kz 83 and the Sondervorauszahlung its
	Kz 39 credited. ``prior`` marks a Voranmeldung filed before Steuerbote, whose name is that of its record."""

	period: Period
	name: str
	kz83: Decimal
	kz39: Decimal = ZERO
	prior: bool = False


def latest_per_period(returns: Iterable[FiledReturn]) -> tuple[FiledReturn, ...]:
	"""The filing of each Voranmeldungszeitraum that counts, in the order of the year.

	``returns`` lists the latest filing first. A corrected return (Kz 10) replaces the returns of its period
	before it, so the latest filing of a period is the one the Finanzamt has.
	"""
	latest: dict[Period, FiledReturn] = {}
	for filed in returns:
		latest.setdefault(filed.period, filed)
	return tuple(sorted(latest.values(), key=lambda filed: filed.period.start))


def with_prior(returns: Iterable[FiledReturn], prior: Iterable[start.PriorFiling]) -> tuple[FiledReturn, ...]:
	"""The filed VAT Returns, the latest of each period first as latest_per_period() takes them, and the latest
	Voranmeldung filed before Steuerbote of each period whose months no VAT Return covers, in the order of the year:
	they count as filed, as their records hold them."""
	own = latest_per_period(returns)
	months = {
		(filed.period.year, month)
		for filed in own
		for month in range(filed.period.first_month, filed.period.last_month + 1)
	}
	outside = [
		FiledReturn(filed.period, filed.name, filed.kz83, filed.kz39, prior=True)
		for filed in start.latest(prior)
		if not months.intersection(filed.months)
	]
	return tuple(sorted((*own, *outside), key=lambda filed: filed.period.start))


def base_rows(returns: Iterable[FiledReturn]) -> list[dict[str, Any]]:
	"""The rows of the table of the base: one per filed return, linked to its VAT Return or, filed before Steuerbote,
	to its record."""
	return [
		{
			"period_label": filed.period.label,
			"period_code": filed.period.code,
			"vat_return": None if filed.prior else filed.name,
			"prior_filing": filed.name if filed.prior else None,
			"kz83": filed.kz83,
			"kz39": filed.kz39,
		}
		for filed in returns
	]


def base_amounts(rows: Iterable[Row]) -> tuple[list[Decimal], Decimal]:
	"""Kz 83 of each row of the table of the base, and the Sondervorauszahlung their Kz 39 credited."""
	rows = list(rows)
	kz83 = [to_amount(row.get("kz83")) for row in rows]
	kz39 = sum((to_amount(row.get("kz39")) for row in rows), ZERO)
	return kz83, kz39


def gaps(
	period_rules: Iterable[rules.PeriodRule], year: int, returns: Iterable[FiledReturn], first_month: int = 1
) -> tuple[Period, ...]:
	"""The Voranmeldungszeiträume of ``year`` whose Kz 83 the base lacks, from ``first_month`` on.

	A month a filed return covers lacks nothing. Any other month lacks the Voranmeldungszeitraum the settings
	set for it, unless they exempt it from the Voranmeldungen; a month they set none for lacks itself, since its
	Voranmeldung may have been filed outside Steuerbote. ``first_month`` is the month a company began in, whose
	Voranmeldungszeitraum counts whole.
	"""
	period_rules = tuple(period_rules)
	filed = tuple(returns)
	missing: list[Period] = []
	for month in range(first_month, MONTHS_PER_YEAR + 1):
		start = date(year, month, 1)
		if any(filed_return.period.contains(start) for filed_return in filed):
			continue
		try:
			period = Period.containing(start, rules.rhythm_for(period_rules, year, month))
		except rules.NoVoranmeldungError:
			continue
		except rules.SettingsError as error:
			if error.template != rules.NO_RULE_YET:
				raise
			period = Period.month(year, month)
		if period not in missing:
			missing.append(period)
	return tuple(missing)


class BaseProblem(Enum):
	NO_RETURNS = "no_returns"
	EXPECTED_NEEDED = "expected_needed"
	MISSING_REASON = "missing_reason"
	BEGAN_LATER = "began_later"


class BaseError(ValueError):
	"""The base of the Sondervorauszahlung cannot be computed as the document stands."""

	def __init__(self, problem: BaseProblem) -> None:
		super().__init__(problem.value)
		self.problem = problem


@dataclass(frozen=True, slots=True)
class Override:
	"""A base the user enters instead of the one from the Voranmeldungen, with the reason why."""

	amount: Decimal
	reason: str


def override_of(amount: object, reason: object) -> Override | None:
	"""The base by hand, which takes effect once it has a reason, so that 0 can be entered too.

	An amount without a reason is refused rather than ignored, since its author expects it to count.
	"""
	text = str(reason or "").strip()
	value = to_amount(amount)
	if text:
		return Override(value, text)
	if value:
		raise BaseError(BaseProblem.MISSING_REASON)
	return None


@dataclass(frozen=True, slots=True)
class Activity:
	"""The months of activity that count for the Sondervorauszahlung of a year, and whether the company began
	in that year itself."""

	months: int
	this_year: bool


def activity(year: int, began: date | None) -> Activity:
	"""What the start of the company means for the Sondervorauszahlung of ``year``.

	A company that began in the previous year converts the Vorauszahlungen of its months into an annual sum
	(§ 47 Absatz 2 UStDV); one that began in ``year`` pays the average Vorauszahlung of a month it expects
	(§ 47 Absatz 3 UStDV). Any other company was active all of the previous year.
	"""
	if began is None or began.year < year - 1:
		return Activity(MONTHS_PER_YEAR, this_year=False)
	if began.year > year:
		raise BaseError(BaseProblem.BEGAN_LATER)
	if began.year == year:
		return Activity(dauerfrist.months_of_activity(year, began), this_year=True)
	return Activity(dauerfrist.months_of_activity(year - 1, began), this_year=False)


@dataclass(frozen=True, slots=True)
class Sondervorauszahlung:
	"""Zeilen 8 and 9 of form USt 1 H as the document files them.

	``kz83`` and ``kz39`` are the sums over the filed returns, ``computed_base`` is Zeile 8 from them, None
	without returns and for a company that began in the year, and ``base`` is the base Kz 38 follows from,
	the computed one or the one by hand.
	"""

	kz83: Decimal
	kz39: Decimal
	computed_base: Decimal | None
	base: Decimal
	kz38: Decimal


def sondervorauszahlung(
	kz83: Sequence[Decimal], kz39: Decimal, active: Activity, override: Override | None
) -> Sondervorauszahlung:
	"""Base and Kz 38 through the core, from the filed returns or from the base by hand.

	For a company that began in the year, the base by hand holds the Vorauszahlungen it expects for the year,
	and Kz 38 is their average over its months of activity.
	"""
	total = sum(kz83, ZERO)
	if active.this_year:
		if override is None:
			raise BaseError(BaseProblem.EXPECTED_NEEDED)
		kz38 = dauerfrist.expected_sondervorauszahlung(override.amount, active.months)
		return Sondervorauszahlung(total, kz39, None, override.amount, kz38)
	computed = dauerfrist.previous_year_base(kz83, kz39, active.months) if kz83 else None
	if override is not None:
		base = override.amount
	elif computed is None:
		raise BaseError(BaseProblem.NO_RETURNS)
	else:
		base = computed
	return Sondervorauszahlung(total, kz39, computed, base, dauerfrist.sondervorauszahlung(base))


def amounts_kept(computed: ReadOnlyMapping[str, object], stored: Row) -> bool:
	"""Whether ``stored`` holds each of the values of base and Kz 38 that ``computed`` gives.

	A filing carries Kz 38 as the form holds it, which every save sets from the table of the base and the base by
	hand. Computed again before a filing, it differs when it was changed past the save, or when the base by hand
	changed while the form was filed.
	"""
	return all(to_amount(stored.get(field)) == to_amount(value) for field, value in computed.items())


def form(doc: Row) -> Ust1H:
	"""Form USt 1 H as the document fills it, checked by the core.

	Kz 38 belongs to the Anmeldung der Sondervorauszahlung alone; the yes fields go as the document holds them,
	so that the core refuses one the Antrag alone does not carry.
	"""
	context = Context(doc.get("context"))
	return Ust1H(
		year=int(doc.get("year") or 0),
		context=context,
		sondervorauszahlung=to_amount(doc.get("sondervorauszahlung"))
		if context.with_sondervorauszahlung
		else None,
		corrected=_checked(doc.get("is_correction")),
		no_sepa_mandate=_checked(doc.get("no_sepa_mandate")),
		offset_requested=_checked(doc.get("offset_requested")),
		supplementary_code=doc.get("supplementary_code") or None,
		begruendung=doc.get("kz500_begruendung") or None,
	)


def _checked(value: object) -> bool:
	"""The value of a check field; Frappe hands out 0 and 1, or nothing."""
	return bool(int(value or 0))
