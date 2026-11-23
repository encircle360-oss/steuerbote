"""The size classes of a GmbH or UG (§§ 267, 267a HGB), which decide the form of its Jahresabschluss and what of
it the company discloses.

A class applies to a company that does not exceed at least two of its three thresholds: „Kleine
Kapitalgesellschaften sind solche, die mindestens zwei der drei nachstehenden Merkmale nicht überschreiten“
(§ 267 Abs. 1 HGB); mittelgroß is a company above the thresholds of klein and within at least two of its own
(Abs. 2), groß one above those (Abs. 3). „Kleinstkapitalgesellschaften sind kleine Kapitalgesellschaften, die
mindestens zwei der drei nachstehenden Merkmale nicht überschreiten“ (§ 267a Abs. 1 HGB), and „Die in diesem
Gesetz für kleine Kapitalgesellschaften (§ 267 Absatz 1) vorgesehenen besonderen Regelungen gelten für
Kleinstkapitalgesellschaften entsprechend, soweit nichts anderes geregelt ist.“ (Abs. 2)

The thresholds are those of the Zweites Gesetz zur Änderung des DWD-Gesetzes sowie zur Änderung
handelsrechtlicher Vorschriften of 11 April 2024 (BGBl. 2024 I Nr. 120), in force since 17 April 2024. Art. 93
Abs. 1 HGBEG applies them „erstmals auf Jahres- und Konzernabschlüsse [...] für das nach dem 31. Dezember 2023
beginnende Geschäftsjahr“; Abs. 2 allowed them a year earlier, „jedoch nur insgesamt“. Every fiscal year
Steuerbote prepares begins in 2026 or later, so YEARS holds them under each year from 2026 on; a new year adds its
entry, as the other cores add the data of a year.

The criteria are the Bilanzsumme, the Umsatzerlöse „in den zwölf Monaten vor dem Abschlussstichtag“ and the
Arbeitnehmer „im Jahresdurchschnitt“ (§ 267 Abs. 1 and 2, § 267a Abs. 1 HGB). A criterion at its threshold does
not exceed it.

„Die Rechtsfolgen der Merkmale nach den Absätzen 1 bis 3 Satz 1 treten nur ein, wenn sie an den
Abschlußstichtagen von zwei aufeinanderfolgenden Geschäftsjahren über- oder unterschritten werden.“ (§ 267 Abs. 4
Satz 1 HGB, for Kleinst by § 267a Abs. 1 Satz 2) decide() applies this to each of the three boundaries between the
classes: a boundary the criteria cross on one Abschlussstichtag only keeps the side the class of the previous year
stood on. A company that grows from klein over two years into mittelgroß and then groß is therefore mittelgroß in
the second year. Both Abschlussstichtage are measured against the thresholds of the fiscal year decided.
„Im Falle der Umwandlung oder Neugründung treten die Rechtsfolgen schon ein, wenn die Voraussetzungen des
Absatzes 1, 2 oder 3 am ersten Abschlußstichtag nach der Umwandlung oder Neugründung vorliegen. Satz 2 findet im
Falle des Formwechsels keine Anwendung, sofern der formwechselnde Rechtsträger eine Kapitalgesellschaft oder eine
Personenhandelsgesellschaft im Sinne des § 264a Absatz 1 ist.“ (§ 267 Abs. 4 Satz 2 and 3 HGB)

„Keine Kleinstkapitalgesellschaften sind“ the Investmentgesellschaften, the Unternehmensbeteiligungsgesellschaften
and a pure holding (§ 267a Abs. 3 HGB, KLEINST_EXCLUSIONS). Such a company keeps the reliefs of klein, so decide()
gives it klein where its criteria point to Kleinst; the Annual Filing Settings record it with ``holding_267a_3``.

„Als durchschnittliche Zahl der Arbeitnehmer gilt der vierte Teil der Summe aus den Zahlen der jeweils am
31. März, 30. Juni, 30. September und 31. Dezember beschäftigten Arbeitnehmer einschließlich der im Ausland
beschäftigten Arbeitnehmer, jedoch ohne die zu ihrer Berufsausbildung Beschäftigten.“ (§ 267 Abs. 5 HGB)
average_employees() takes the four headcounts, which the Annual Accounts read from the employees of the company
without the Employment Types the Annual Filing Settings leave out. HEADCOUNT_CONVENTIONS names who counts: the law
settles staff abroad and apprentices; whether a part-timer counts as one head and a Geschäftsführer not at all
stays unverified, as does which months the Umsatzerlöse of a short fiscal year cover, so the class of a year can be
overridden with a Begründung. For a short first fiscal year the law names no other days, and a day before the
founding counts nobody.

Text of §§ 267, 267a HGB and Art. 93 HGBEG as read on gesetze-im-internet.de on 23 November 2026.

This module imports nothing of Steuerbote, so that every part of the Jahresabschluss can name its class with it.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from functools import total_ordering
from types import MappingProxyType

_REQUIRED_CRITERIA_ABOVE = 2
_QUARTER_ENDS = ((3, 31), (6, 30), (9, 30), (12, 31))
_HEADCOUNT_DAYS = len(_QUARTER_ENDS)


class UnknownYearError(ValueError):
	"""Steuerbote has no thresholds for the fiscal year: its entry in YEARS comes first."""


class SizeError(ValueError):
	"""The input cannot be measured against the thresholds, such as a headcount on the wrong days."""


@total_ordering
class SizeClass(Enum):
	"""The size classes from the smallest to the largest; they compare by that order."""

	KLEINST = "Kleinstkapitalgesellschaft"
	KLEIN = "kleine Kapitalgesellschaft"
	MITTELGROSS = "mittelgroße Kapitalgesellschaft"
	GROSS = "große Kapitalgesellschaft"

	@property
	def rank(self) -> int:
		return _ORDER.index(self)

	@property
	def reference(self) -> str:
		return _REFERENCES[self]

	@property
	def gcd(self) -> str:
		"""The value of genInfo.company.id.sizeClass in the GCD module of the HGB taxonomy 6.9
		(de-gcd-2025-04-01.xsd: KstK, KK, MK and GK)."""
		return _GCD[self]

	@property
	def is_small(self) -> bool:
		"""Kleinst or klein: a Kleinstkapitalgesellschaft is a small one with the reliefs of klein as well."""
		return self.rank <= _ORDER.index(SizeClass.KLEIN)

	def __lt__(self, other: object) -> bool:
		if not isinstance(other, SizeClass):
			return NotImplemented
		return self.rank < other.rank


_ORDER = tuple(SizeClass)
_REFERENCES = MappingProxyType(
	{
		SizeClass.KLEINST: "§ 267a Abs. 1 HGB",
		SizeClass.KLEIN: "§ 267 Abs. 1 HGB",
		SizeClass.MITTELGROSS: "§ 267 Abs. 2 HGB",
		SizeClass.GROSS: "§ 267 Abs. 3 HGB",
	}
)
_GCD = MappingProxyType(
	{SizeClass.KLEINST: "KstK", SizeClass.KLEIN: "KK", SizeClass.MITTELGROSS: "MK", SizeClass.GROSS: "GK"}
)


@dataclass(frozen=True, slots=True)
class Thresholds:
	"""The three thresholds of one class: Bilanzsumme and Umsatzerlöse in euros, Arbeitnehmer as an average."""

	bilanzsumme: Decimal
	umsatzerloese: Decimal
	arbeitnehmer: int


@dataclass(frozen=True, slots=True)
class YearThresholds:
	"""The thresholds a fiscal year is measured against, with their source; each is the upper end of its class."""

	year: int
	kleinst: Thresholds
	klein: Thresholds
	mittelgross: Thresholds
	source: str

	def boundaries(self) -> tuple[tuple[SizeClass, Thresholds], ...]:
		"""Each class below groß with its thresholds; a company above them belongs to a larger class."""
		return (
			(SizeClass.KLEINST, self.kleinst),
			(SizeClass.KLEIN, self.klein),
			(SizeClass.MITTELGROSS, self.mittelgross),
		)


_SOURCE_2024 = (
	"§ 267 Abs. 1 and 2, § 267a Abs. 1 HGB as amended by the Zweites Gesetz zur Änderung des DWD-Gesetzes sowie "
	"zur Änderung handelsrechtlicher Vorschriften of 11 April 2024 (BGBl. 2024 I Nr. 120); first applied to "
	"„das nach dem 31. Dezember 2023 beginnende Geschäftsjahr“ (Art. 93 Abs. 1 HGBEG)"
)
_THRESHOLDS_2024 = (
	Thresholds(Decimal("450000"), Decimal("900000"), 10),
	Thresholds(Decimal("7500000"), Decimal("15000000"), 50),
	Thresholds(Decimal("25000000"), Decimal("50000000"), 250),
)

YEARS: MappingProxyType[int, YearThresholds] = MappingProxyType(
	{2026: YearThresholds(2026, *_THRESHOLDS_2024, source=_SOURCE_2024)}
)


def thresholds_for(year: int) -> YearThresholds:
	"""The thresholds of the fiscal year that ends in ``year``; 2026.0 and True would find 2026 by hash."""
	if isinstance(year, bool) or not isinstance(year, int):
		raise TypeError(f"year must be an int, not {type(year).__name__}")
	try:
		return YEARS[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in YEARS)
		raise UnknownYearError(
			f"Steuerbote has no size thresholds for {year}; known years: {known}"
		) from None


@dataclass(frozen=True, slots=True)
class Criteria:
	"""The three criteria of one Abschlussstichtag; each is a Decimal, the Arbeitnehmer an average."""

	closing_date: date
	bilanzsumme: Decimal
	umsatzerloese: Decimal
	arbeitnehmer: Decimal

	def __post_init__(self) -> None:
		for name in ("bilanzsumme", "umsatzerloese", "arbeitnehmer"):
			value = getattr(self, name)
			if not isinstance(value, Decimal):
				raise TypeError(f"{name} must be Decimal, not {type(value).__name__}")
			if value < 0:
				raise ValueError(f"{name} cannot be negative: {value}")


def exceeds(criteria: Criteria, thresholds: Thresholds) -> bool:
	"""Whether at least two of the three criteria are above their thresholds."""
	above = (
		criteria.bilanzsumme > thresholds.bilanzsumme,
		criteria.umsatzerloese > thresholds.umsatzerloese,
		criteria.arbeitnehmer > thresholds.arbeitnehmer,
	)
	return sum(above) >= _REQUIRED_CRITERIA_ABOVE


def indicated_class(criteria: Criteria, thresholds: YearThresholds) -> SizeClass:
	"""The class the criteria of one Abschlussstichtag point to, before § 267 Abs. 4 HGB asks for a second one."""
	for size, limits in thresholds.boundaries():
		if not exceeds(criteria, limits):
			return size
	return SizeClass.GROSS


class Origin(Enum):
	"""What the fiscal year is the first after; only a Neugründung and an Umwandlung let its closing date decide."""

	NEUGRUENDUNG = "Neugründung"
	UMWANDLUNG = "Umwandlung"
	FORMWECHSEL = (
		"Formwechsel einer Kapitalgesellschaft oder einer Personenhandelsgesellschaft "
		"im Sinne des § 264a Absatz 1"
	)


class Basis(Enum):
	"""Why a class applies to a fiscal year."""

	CONFIRMED = "an zwei aufeinanderfolgenden Abschlussstichtagen"
	CARRIED = "Größenklasse des Vorjahres"
	FOUNDING = "erster Abschlussstichtag nach Neugründung oder Umwandlung"


@dataclass(frozen=True, slots=True)
class SizeDecision:
	"""The class of a fiscal year: the class each Abschlussstichtag points to and the one that applies.

	``applied`` is None while the class of the previous year is needed and unknown; the Annual Accounts then ask
	for it or for an override with a Begründung.
	"""

	year: int
	indicated: SizeClass
	previous_indicated: SizeClass | None
	applied: SizeClass | None
	basis: Basis | None
	kleinst_excluded: bool = False
	"""True when § 267a Abs. 3 HGB turned Kleinst into klein."""

	@property
	def decided(self) -> bool:
		return self.applied is not None


def decide(
	current: Criteria,
	previous: Criteria | None = None,
	previous_class: SizeClass | None = None,
	*,
	first_after: Origin | None = None,
	excluded_from_kleinst: bool = False,
) -> SizeDecision:
	"""The class of the fiscal year ending on ``current.closing_date`` (§ 267 Abs. 4 HGB).

	``previous`` holds the criteria of the Abschlussstichtag before, ``previous_class`` the class that applied in
	that fiscal year, as the size history of the Annual Filing Settings records it. ``first_after`` names what the
	fiscal year is the first after: the founding year of the company is the first after its Neugründung.
	``excluded_from_kleinst`` marks a company of § 267a Abs. 3 HGB.
	"""
	if previous is not None and previous.closing_date >= current.closing_date:
		raise SizeError(
			f"the previous Abschlussstichtag {previous.closing_date.isoformat()} must lie before "
			f"{current.closing_date.isoformat()}"
		)
	year = current.closing_date.year
	thresholds = thresholds_for(year)
	indicated = indicated_class(current, thresholds)
	previous_indicated = None if previous is None else indicated_class(previous, thresholds)
	applied, basis = _applied(indicated, current, previous, previous_class, first_after, thresholds)
	if excluded_from_kleinst and applied is SizeClass.KLEINST:
		return SizeDecision(
			year, indicated, previous_indicated, SizeClass.KLEIN, basis, kleinst_excluded=True
		)
	return SizeDecision(year, indicated, previous_indicated, applied, basis)


def _applied(
	indicated: SizeClass,
	current: Criteria,
	previous: Criteria | None,
	previous_class: SizeClass | None,
	first_after: Origin | None,
	thresholds: YearThresholds,
) -> tuple[SizeClass | None, Basis | None]:
	if first_after in (Origin.NEUGRUENDUNG, Origin.UMWANDLUNG):
		return indicated, Basis.FOUNDING
	if previous is None:
		return (indicated, Basis.CARRIED) if previous_class is indicated else (None, None)
	if indicated_class(previous, thresholds) is indicated:
		return indicated, Basis.CONFIRMED
	if previous_class is None:
		return None, None
	return _carried(current, previous, previous_class, thresholds), Basis.CARRIED


def _carried(
	current: Criteria, previous: Criteria, previous_class: SizeClass, thresholds: YearThresholds
) -> SizeClass:
	"""The class whose boundaries keep the side of previous_class unless both closing dates crossed them.

	Thresholds rise from class to class, so a company above one boundary is above every lower one on the same
	closing date, and the boundaries above the result never outnumber those below it.
	"""
	above = 0
	for size, limits in thresholds.boundaries():
		now, before = exceeds(current, limits), exceeds(previous, limits)
		above += now if now == before else previous_class > size
	return _ORDER[above]


def headcount_dates(closing_date: date) -> tuple[date, ...]:
	"""The days of § 267 Abs. 5 HGB for the year that ends on ``closing_date``: the last four quarter ends up to it,
	31 March, 30 June, 30 September and 31 December of a calendar year."""
	candidates = [
		date(year, month, day)
		for year in (closing_date.year - 1, closing_date.year)
		for month, day in _QUARTER_ENDS
	]
	return tuple(day for day in candidates if day <= closing_date)[-_HEADCOUNT_DAYS:]


def average_employees(headcounts: Mapping[date, int], closing_date: date) -> Decimal:
	"""The average number of Arbeitnehmer of § 267 Abs. 5 HGB: a quarter of the four headcounts, kept exactly."""
	days = headcount_dates(closing_date)
	if set(headcounts) != set(days):
		expected = ", ".join(day.isoformat() for day in days)
		raise SizeError(f"the average of § 267 Abs. 5 HGB needs the headcounts of {expected}")
	for day in days:
		count = headcounts[day]
		if isinstance(count, bool) or not isinstance(count, int):
			raise TypeError(f"the headcount of {day.isoformat()} must be an int, not {type(count).__name__}")
		if count < 0:
			raise ValueError(f"the headcount of {day.isoformat()} cannot be negative: {count}")
	return Decimal(sum(headcounts[day] for day in days)) / _HEADCOUNT_DAYS


class Counting(Enum):
	COUNTED = "zählt"
	NOT_COUNTED = "zählt nicht"
	UNVERIFIED = "ungeprüft"


@dataclass(frozen=True, slots=True)
class HeadcountConvention:
	"""Who counts as an Arbeitnehmer of § 267 Abs. 5 HGB; ``reference`` is empty while no primary source settles
	it."""

	who: str
	counting: Counting
	reference: str


HEADCOUNT_CONVENTIONS: tuple[HeadcountConvention, ...] = (
	HeadcountConvention("im Ausland beschäftigte Arbeitnehmer", Counting.COUNTED, "§ 267 Abs. 5 HGB"),
	HeadcountConvention("zu ihrer Berufsausbildung Beschäftigte", Counting.NOT_COUNTED, "§ 267 Abs. 5 HGB"),
	HeadcountConvention("Teilzeitbeschäftigte, je Kopf gezählt", Counting.UNVERIFIED, ""),
	HeadcountConvention("Geschäftsführer", Counting.UNVERIFIED, ""),
)


@dataclass(frozen=True, slots=True)
class KleinstExclusion:
	who: str
	reference: str


KLEINST_EXCLUSIONS: tuple[KleinstExclusion, ...] = (
	KleinstExclusion("Investmentgesellschaften im Sinne des § 1 Absatz 11 KAGB", "§ 267a Abs. 3 Nr. 1 HGB"),
	KleinstExclusion(
		"Unternehmensbeteiligungsgesellschaften im Sinne des § 1a Absatz 1 UBGG", "§ 267a Abs. 3 Nr. 2 HGB"
	),
	KleinstExclusion(
		"Unternehmen, deren einziger Zweck darin besteht, Beteiligungen an anderen Unternehmen zu erwerben sowie die "
		"Verwaltung und Verwertung dieser Beteiligungen wahrzunehmen, ohne dass sie unmittelbar oder mittelbar in "
		"die Verwaltung dieser Unternehmen eingreifen",
		"§ 267a Abs. 3 Nr. 3 HGB",
	),
)
