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
not exceed it. Text of §§ 267, 267a HGB and Art. 93 HGBEG as read on gesetze-im-internet.de on 23 November 2026.

This module imports nothing of Steuerbote, so that every part of the Jahresabschluss can name its class with it.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from functools import total_ordering
from types import MappingProxyType

_REQUIRED_CRITERIA_ABOVE = 2


class UnknownYearError(ValueError):
	"""Steuerbote has no thresholds for the fiscal year: its entry in YEARS comes first."""


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
