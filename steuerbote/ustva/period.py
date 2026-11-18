"""Voranmeldungszeiträume and their deadlines.

A company files monthly or quarterly (§ 18 Absatz 2 UStG); the form USt 1 A 2026 offers the twelve
months and the four Kalendervierteljahre. The Vorauszahlung is due on the 10th day after the end of
the period (Anleitung to the form, lines 53 to 54: "Die Vorauszahlung ist am 10. Tag nach Ablauf des
Voranmeldungszeitraums fällig"); with Dauerfristverlängerung (§§ 46 to 48 UStDV) the deadline moves by
one month. A deadline on a Saturday, Sunday or public holiday moves to the next working day
(§ 108 Absatz 3 AO); public holidays differ by state, so the caller passes them in.

The two-digit period codes are those of the ELSTER interface for the Datenart UStVA: 01 to 12 for
the months, 41 to 44 for the quarters. They are re-checked against the ERiC schema when the XML is built.
"""

import calendar
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

MONTH_NAMES = (
	"Januar",
	"Februar",
	"März",
	"April",
	"Mai",
	"Juni",
	"Juli",
	"August",
	"September",
	"Oktober",
	"November",
	"Dezember",
)
QUARTER_NAMES = ("I.", "II.", "III.", "IV.")
QUARTER_CODE_OFFSET = 40
DUE_DAY = 10
SATURDAY = 5


class Rhythm(Enum):
	MONTHLY = "monthly"
	QUARTERLY = "quarterly"


@dataclass(frozen=True, slots=True)
class Period:
	year: int
	rhythm: Rhythm
	index: int

	def __post_init__(self) -> None:
		object.__setattr__(self, "rhythm", Rhythm(self.rhythm))
		last = 12 if self.rhythm is Rhythm.MONTHLY else 4
		if not _is_int(self.index) or not 1 <= self.index <= last:
			raise ValueError(
				f"{self.rhythm.value} period index must be between 1 and {last}, not {self.index!r}"
			)
		if not _is_int(self.year) or not 1 <= self.year <= 9999:
			raise ValueError(f"year must be a four-digit year, not {self.year!r}")

	@classmethod
	def month(cls, year: int, month: int) -> Period:
		return cls(year, Rhythm.MONTHLY, month)

	@classmethod
	def quarter(cls, year: int, quarter: int) -> Period:
		return cls(year, Rhythm.QUARTERLY, quarter)

	@classmethod
	def containing(cls, day: date, rhythm: Rhythm) -> Period:
		if Rhythm(rhythm) is Rhythm.MONTHLY:
			return cls.month(day.year, day.month)
		return cls.quarter(day.year, (day.month - 1) // 3 + 1)

	@property
	def first_month(self) -> int:
		return self.index if self.rhythm is Rhythm.MONTHLY else (self.index - 1) * 3 + 1

	@property
	def last_month(self) -> int:
		return self.index if self.rhythm is Rhythm.MONTHLY else self.index * 3

	@property
	def start(self) -> date:
		return date(self.year, self.first_month, 1)

	@property
	def end(self) -> date:
		return date(self.year, self.last_month, calendar.monthrange(self.year, self.last_month)[1])

	@property
	def code(self) -> str:
		"""The ELSTER period code: 01 to 12 for months, 41 to 44 for quarters."""
		number = self.index if self.rhythm is Rhythm.MONTHLY else QUARTER_CODE_OFFSET + self.index
		return f"{number:02d}"

	@property
	def label(self) -> str:
		if self.rhythm is Rhythm.MONTHLY:
			return f"{MONTH_NAMES[self.index - 1]} {self.year}"
		return f"{QUARTER_NAMES[self.index - 1]} Kalendervierteljahr {self.year}"

	def contains(self, day: date) -> bool:
		return self.start <= day <= self.end

	def deadline(self, dauerfristverlaengerung: bool = False, holidays: Collection[date] = ()) -> date:
		"""The day the Voranmeldung is due and the Vorauszahlung has to be paid."""
		months_after_end = 2 if dauerfristverlaengerung else 1
		due = _add_months(self.end, months_after_end).replace(day=DUE_DAY)
		while due.weekday() >= SATURDAY or due in holidays:
			due += timedelta(days=1)
		return due

	def previous(self) -> Period:
		if self.index > 1:
			return Period(self.year, self.rhythm, self.index - 1)
		last = 12 if self.rhythm is Rhythm.MONTHLY else 4
		return Period(self.year - 1, self.rhythm, last)

	def next(self) -> Period:
		last = 12 if self.rhythm is Rhythm.MONTHLY else 4
		if self.index < last:
			return Period(self.year, self.rhythm, self.index + 1)
		return Period(self.year + 1, self.rhythm, 1)


def _is_int(value: object) -> bool:
	"""True is an int to Python, but neither a year nor a month."""
	return isinstance(value, int) and not isinstance(value, bool)


def _add_months(day: date, months: int) -> date:
	month_index = day.month - 1 + months
	year = day.year + month_index // 12
	month = month_index % 12 + 1
	return date(year, month, 1)
