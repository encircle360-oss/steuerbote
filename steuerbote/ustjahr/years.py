"""The years Steuerbote files the Umsatzsteuererklärung for, and what each of them needs.

ELSTER takes the Umsatzsteuererklärung only in the Datenart of its year: Verfahren ElsterErklaerung, Datenart
USt, datenartVersion USt_<Jahr>, which ERiC checks with the plugin checkUSt_<Jahr> (Datenartversionmatrix.ods of
the ERiC documentation 44.3.6.0: „USt, <Jahr>: ab 2015, USt_<Jahr>, checkUSt_<Jahr>, neue Nutzdatenstruktur ab
2021“). A year is a set of data, each part in a table of its own that is keyed by the year:

- the fields, Kennzahlen and rules of form USt 2 A from Jahresdokumentation_E50_<Jahr>.ods, with the BMF letter
  of the forms of the year: CATALOGUES in steuerbote/ustjahr/form.py;
- the rules of that Jahresdokumentation that Steuerbote checks without ERiC: LOCAL_RULES in
  steuerbote/ustjahr/rules.py;
- the defaults of the charts SKR03 and SKR04 for the lines of the form: ROLE_FIELDS, ANNUAL_ACCOUNTS and their
  REVISIONS in steuerbote/ustjahr/defaults.py;
- the patterns and lists of the fields of that Jahresdokumentation, which the XML of the return keeps: SCHEMAS in
  steuerbote/elster/ust2a_xml.py.

YEARS names the years with the BMF letter of their forms. The letter for the annual return is not the letter of
the Voranmeldung, although the BMF signed both on the same day, so this table does not share the entries of
steuerbote/ustva/years.py. The annual return also keeps a clock of its own: in 2027 the Voranmeldungen are those of
2027, while the annual return filed then is that of 2026. Every table above holds exactly the years of YEARS
(steuerbote/ustjahr/tests/test_years.py).

The deadline of the return follows the Abgabenordnung, the same for every year: filing_deadline().
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, timedelta
from types import MappingProxyType

from steuerbote.ustva.period import next_working_day
from steuerbote.ustva.years import MONTHS, UnknownYearError

JULY = 7
MARCH = 3
LAST_OF_JULY = 31


@dataclass(frozen=True, slots=True)
class Year:
	"""A year Steuerbote files, with the BMF letter that publishes its forms USt 2 A, Anlage UN, Anlage FV, USt 2 E
	and USt 6 E."""

	year: int
	letter_date: date
	reference: str
	"""The Geschäftszeichen (GZ) of the letter."""
	url: str

	@property
	def letter(self) -> str:
		"""The letter as the docstrings of the data of the year cite it."""
		day = self.letter_date
		return f"BMF letter of {day.day} {MONTHS[day.month - 1]} {day.year} (GZ {self.reference})"

	@property
	def datenart_version(self) -> str:
		return datenart_version(self.year)

	@property
	def plugin(self) -> str:
		return plugin(self.year)

	@property
	def plugin_library(self) -> str:
		return plugin_library(self.year)


YEARS: MappingProxyType[int, Year] = MappingProxyType(
	{
		2026: Year(
			2026,
			date(2025, 12, 29),
			"III C 3 - S 7344/00040/008/034",
			"https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/"
			"2025-12-29-muster-USt-erklaerung-2026.pdf",
		),
	}
)
LATEST_YEAR = max(YEARS)


def year_of(year: int) -> Year:
	"""The entry of the year; 2026.0 and True would find 2026 by hash, so only an int is a year."""
	_require_year(year)
	try:
		return YEARS[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in YEARS)
		raise UnknownYearError(
			f"Steuerbote has no data for the Umsatzsteuererklärung {year}; known years: {known}"
		) from None


def datenart_version(year: int) -> str:
	"""The datenartVersion of the Umsatzsteuererklärung of the year, such as USt_2026."""
	return f"USt_{year}"


def plugin(year: int) -> str:
	"""The plugin of ERiC that checks the Datenart of the year, such as checkUSt_2026."""
	return f"checkUSt_{year}"


def plugin_library(year: int) -> str:
	"""The file of the plugin under Linux, lib<plugin>.so."""
	return f"lib{plugin(year)}.so"


def filing_deadline(
	year: int, advisor: bool = False, requested: date | None = None, holidays: Collection[date] = ()
) -> date:
	"""The day the Umsatzsteuererklärung of ``year`` is due.

	Without a Steuerberatung „spätestens sieben Monate nach Ablauf des Kalenderjahres“ (§ 149 Absatz 2 Satz 1 AO),
	as the Anleitung prints it for 2026: „Abgabefrist: bis 31. Juli 2027“ (USt 2 E 2026). Prepared by a
	Steuerberatung (``advisor``), „bis zum letzten Tag des Monats Februar ... des zweiten auf den
	Besteuerungszeitraum folgenden Kalenderjahres“ (§ 149 Absatz 3 Nummer 4 AO). A day the Finanzamt orders
	(``requested``, § 149 Absatz 4 AO) replaces both. A deadline on a Saturday, a Sunday or one of the
	``holidays`` moves to the next working day: § 108 Absatz 3 AO, which applies to „die Erklärungsfrist (§ 149
	AO)“ (AEAO zu § 108).
	"""
	_require_year(year)
	if requested is not None:
		due = requested
	elif advisor:
		due = date(year + 2, MARCH, 1) - timedelta(days=1)
	else:
		due = date(year + 1, JULY, LAST_OF_JULY)
	return next_working_day(due, holidays)


def _require_year(year: object) -> None:
	if isinstance(year, bool) or not isinstance(year, int):
		raise TypeError(f"year must be an int, not {type(year).__name__}")
