"""Meldezeiträume of the Zusammenfassende Meldung, their ELSTER codes and their deadlines.

§ 18a UStG knows four Meldezeiträume: the Kalendermonat (Absatz 1 Satz 1), the Kalendervierteljahr (Absatz 1
Satz 2 and Absatz 2), the Kalenderjahr for companies exempt from the Voranmeldungen (Absatz 9), and, when the
deliveries of a quarter exceed 50,000 euros, the month of the excess together with „die bereits abgelaufenen
Kalendermonate dieses Kalendervierteljahres“ (Absatz 1 Satz 3). The ERiC data type ZMDO codes the Meldezeitraum
in its field quart (Jahresdokumentation ZMDO 2, sheet „ZMDO - Felder“): 21 to 32 for the months, 11 to 14 for
January and February, April and May, July and August, October and November, 1 to 4 for the quarters and 5 for
the year. Excess in the third month of a quarter makes the first monthly ZM cover the whole quarter, which
carries the code of the quarter.

The ZM is due „bis zum 25. Tag nach Ablauf“ of its Meldezeitraum (§ 18a Absatz 1 Satz 1 UStG), and „Die
Regelungen über die Dauerfristverlängerung für die Abgabe der Umsatzsteuer-Voranmeldungen gelten nicht für die
ZM“ (BZSt, „Fristen“ of the ZM). § 18a Absatz 11 UStG applies the rules of the Abgabenordnung for tax returns
to the ZM, so a deadline on a Saturday, Sunday or public holiday moves to the next working day
(§ 108 Absatz 3 AO). Public holidays differ by state, so the caller passes them in.
"""

import calendar
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from steuerbote.ustva.period import MONTH_NAMES, QUARTER_NAMES, next_working_day

DUE_DAYS_AFTER_END = 25
QUARTER_START_MONTHS = (1, 4, 7, 10)
MONTH_CODE_OFFSET = 20
TWO_MONTHS_CODE_OFFSET = 10
YEAR_CODE = 5


class Kind(Enum):
	MONTH = "month"
	TWO_MONTHS = "two_months"
	QUARTER = "quarter"
	YEAR = "year"


@dataclass(frozen=True, slots=True)
class ReportingPeriod:
	"""The Meldezeitraum of a ZM: the months ``first_month`` to ``last_month`` of ``year``."""

	year: int
	first_month: int
	last_month: int

	def __post_init__(self) -> None:
		if not _is_int(self.year) or not 1 <= self.year <= 9999:
			raise ValueError(f"year must be a four-digit year, not {self.year!r}")
		_kind(self.first_month, self.last_month)

	@classmethod
	def month(cls, year: int, month: int) -> ReportingPeriod:
		return cls(year, month, month)

	@classmethod
	def two_months(cls, year: int, quarter: int) -> ReportingPeriod:
		"""The first two months of a quarter."""
		first = _first_month_of(quarter)
		return cls(year, first, first + 1)

	@classmethod
	def quarter(cls, year: int, quarter: int) -> ReportingPeriod:
		first = _first_month_of(quarter)
		return cls(year, first, first + 2)

	@classmethod
	def calendar_year(cls, year: int) -> ReportingPeriod:
		return cls(year, 1, 12)

	@classmethod
	def from_quart(cls, year: int, quart: int) -> ReportingPeriod:
		"""The Meldezeitraum of a quart code of ZMDO."""
		if not _is_int(quart):
			raise ValueError(f"{quart!r} is not a quart of the ZM")
		if MONTH_CODE_OFFSET < quart <= MONTH_CODE_OFFSET + 12:
			return cls.month(year, quart - MONTH_CODE_OFFSET)
		if TWO_MONTHS_CODE_OFFSET < quart <= TWO_MONTHS_CODE_OFFSET + 4:
			return cls.two_months(year, quart - TWO_MONTHS_CODE_OFFSET)
		if 1 <= quart <= 4:
			return cls.quarter(year, quart)
		if quart == YEAR_CODE:
			return cls.calendar_year(year)
		raise ValueError(f"{quart!r} is not a quart of the ZM")

	@property
	def kind(self) -> Kind:
		return _kind(self.first_month, self.last_month)

	@property
	def quart(self) -> int:
		"""The code of the Meldezeitraum in the field quart of ZMDO."""
		quarter = (self.first_month - 1) // 3 + 1
		match self.kind:
			case Kind.MONTH:
				return MONTH_CODE_OFFSET + self.first_month
			case Kind.TWO_MONTHS:
				return TWO_MONTHS_CODE_OFFSET + quarter
			case Kind.QUARTER:
				return quarter
		return YEAR_CODE

	@property
	def months(self) -> tuple[int, ...]:
		return tuple(range(self.first_month, self.last_month + 1))

	@property
	def start(self) -> date:
		return date(self.year, self.first_month, 1)

	@property
	def end(self) -> date:
		return date(self.year, self.last_month, calendar.monthrange(self.year, self.last_month)[1])

	@property
	def label(self) -> str:
		match self.kind:
			case Kind.MONTH:
				return f"{MONTH_NAMES[self.first_month - 1]} {self.year}"
			case Kind.TWO_MONTHS:
				first, second = MONTH_NAMES[self.first_month - 1], MONTH_NAMES[self.last_month - 1]
				return f"{first} und {second} {self.year}"
			case Kind.QUARTER:
				return f"{QUARTER_NAMES[(self.first_month - 1) // 3]} Kalendervierteljahr {self.year}"
		return f"Kalenderjahr {self.year}"

	def contains(self, day: date) -> bool:
		return self.start <= day <= self.end

	def deadline(self, holidays: Collection[date] = ()) -> date:
		"""The day the ZM is due: the 25th day after the end of the period, or the next working day."""
		return next_working_day(self.end + timedelta(days=DUE_DAYS_AFTER_END), holidays)

	def previous(self) -> ReportingPeriod:
		"""The Meldezeitraum of the same kind before this one."""
		if self.kind is Kind.YEAR:
			return ReportingPeriod.calendar_year(self.year - 1)
		step = 1 if self.kind is Kind.MONTH else 3
		if self.first_month > step:
			return ReportingPeriod(self.year, self.first_month - step, self.last_month - step)
		return ReportingPeriod(self.year - 1, self.first_month - step + 12, self.last_month - step + 12)


def quarter_start(month: int) -> int:
	"""The first month of the quarter of a month."""
	return (month - 1) // 3 * 3 + 1


def _first_month_of(quarter: int) -> int:
	"""A quarter outside 1 to 4 gives a month that no Meldezeitraum starts with, so the period refuses it."""
	return (quarter - 1) * 3 + 1 if _is_int(quarter) else 0


def _kind(first: int, last: int) -> Kind:
	if _is_int(first) and _is_int(last):
		if first == last and 1 <= first <= 12:
			return Kind.MONTH
		if first in QUARTER_START_MONTHS and last == first + 1:
			return Kind.TWO_MONTHS
		if first in QUARTER_START_MONTHS and last == first + 2:
			return Kind.QUARTER
		if (first, last) == (1, 12):
			return Kind.YEAR
	raise ValueError(f"months {first!r} to {last!r} are no Meldezeitraum")


def _is_int(value: object) -> bool:
	"""True is an int to Python, but neither a year nor a month."""
	return isinstance(value, int) and not isinstance(value, bool)
