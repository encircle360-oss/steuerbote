"""The years Steuerbote files, and what each of them needs.

ELSTER takes a Voranmeldung, and form USt 1 H with it, only in the Datenart of its year: datenartVersion
UStVA_<Jahr>, which ERiC checks with the plugin checkUStVA_<Jahr>, „Mit UStDV und UStSV“, so with both contexts
of form USt 1 H (Datenartversionmatrix.ods of the ERiC documentation 44.3.6.0; ERiC-Entwicklerhandbuch,
Kap. 3.1.6.1, for the plugins). A year is therefore a set of data, each part in a table of its own that is keyed
by the year and taken from a source of its own:

- the Kennzahlen of form USt 1 A from the BMF letter with the Vordruckmuster of the year: CATALOGUES in
  steuerbote/ustva/kennzahlen.py;
- the schema of Anmeldungssteuern, UStVA-<Jahr>.xsd of the ERiC documentation, with its namespace, the order of
  its elements and the Kennzahlen without sign: SCHEMAS in steuerbote/elster/ustva_xml.py;
- the fields and rules of form USt 1 H from Jahresdokumentation_UStVA_<Jahr>.ods: LAYOUTS in
  steuerbote/dauerfrist/form.py;
- the plugin of ERiC, which the Datenartversionmatrix names after the year: ``Year.plugin``.

YEARS names the years Steuerbote files, each with the BMF letter of its forms. Every table holds exactly these
years (steuerbote/ustva/tests/test_years.py), and ``python -m steuerbote.ustva.yearcheck`` compares the data of a
year with the ERiC documentation; docs/entwicklung.md, section Jahreswechsel, describes how a year is added.

The beta of the main release of ERiC brings the Jahresdokumentation and the schema of the coming year in mid
November, the BMF letter with its forms follows in December (ERiC-Entwicklerhandbuch, Kap. 2.3; the letter for 2026
is of 29 December 2025). A year added in between is ``provisional``: its data come from the documentation of the beta,
its lines and labels from the form of the year before, and the documents of the year say so until both are
published and the year is made final.

The Zusammenfassende Meldung is no part of a year. Its Datenart ZMDO has one datenartVersion and one plugin for
every year, ZMDO and checkZMDO without year or version (Datenartversionmatrix.ods), and its schema has a version
of its own, 000005 since 15 October 2020 (zm_000005.xsd in Datenarten/ElsterExtern/ZMDO/Schema/5). The year of
the Meldezeitraum is a field of the data, jahr next to quart (Jahresdokumentation_ZMDO_2.ods, sheet "ZMDO -
Felder"), so a new year changes none of it; steuerbote/elster/zm_xml.py names all three, and the year check
compares them with the Datenartversionmatrix of each year.

The module imports nothing of Steuerbote, so that every part can name its year with it.
"""

import re
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

MONTHS = (
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
)
_PLUGIN_LIBRARY = re.compile(r"libcheckUStVA_(?P<year>\d{4})\.so")


class UnknownYearError(ValueError):
	"""Steuerbote has no data for the year: it needs the forms and the ERiC documentation of that year first."""


@dataclass(frozen=True, slots=True)
class Year:
	"""A year Steuerbote files, with the BMF letter that publishes its forms USt 1 A, USt 1 E, USt 1 H and USt 5 E.

	A ``provisional`` year has no letter yet: its data come from the Jahresdokumentation and the schema of the year in
	the ``documentation`` of a beta of ERiC, its lines, labels and print layout from the form of ``form_year``.
	"""

	year: int
	letter_date: date | None
	reference: str | None
	"""The Geschäftszeichen (GZ) of the letter."""
	url: str | None
	provisional: bool = False
	documentation: str | None = None
	"""The release of ERiC whose documentation the data of a provisional year come from, such as Beta ERiC 45.1.5.0."""
	form_year: int | None = None
	"""The year of the form whose lines, labels and print layout the year takes, the year itself unless given."""

	def __post_init__(self) -> None:
		if not self.provisional and None in (self.letter_date, self.reference, self.url):
			raise ValueError(f"{self.year}: a final year names the BMF letter of its forms")
		if self.provisional and not self.documentation:
			raise ValueError(f"{self.year}: a provisional year names the documentation it comes from")
		if self.form_year is None:
			object.__setattr__(self, "form_year", self.year)

	@property
	def letter(self) -> str | None:
		"""The letter as the docstrings of the data of the year cite it, None before the BMF publishes it."""
		day = self.letter_date
		if day is None:
			return None
		return f"BMF letter of {day.day} {MONTHS[day.month - 1]} {day.year} (GZ {self.reference})"

	@property
	def source(self) -> str:
		"""What the docstrings of the data of the year cite: the letter of a final year, the Jahresdokumentation of the
		documentation of a provisional one."""
		letter = self.letter
		if self.provisional or letter is None:
			return f"Jahresdokumentation_UStVA_{self.year}.ods of the documentation of {self.documentation}"
		return letter

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
			"III C 3 - S 7344/00039/007/036",
			"https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/"
			"2025-12-29-vordruckmuster-USt-voranmeldung-2026.pdf",
		),
	}
)
LATEST_YEAR = max(YEARS)


def year_of(year: int) -> Year:
	"""The entry of the year; 2026.0 and True would find 2026 by hash, so only an int is a year."""
	if isinstance(year, bool) or not isinstance(year, int):
		raise TypeError(f"year must be an int, not {type(year).__name__}")
	try:
		return YEARS[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in YEARS)
		raise UnknownYearError(f"Steuerbote has no data for {year}; known years: {known}") from None


def datenart_version(year: int) -> str:
	"""The datenartVersion of the Voranmeldung and of form USt 1 H of the year, such as UStVA_2026."""
	return f"UStVA_{year}"


def plugin(year: int) -> str:
	"""The plugin of ERiC that checks the Datenart of the year, such as checkUStVA_2026."""
	return f"checkUStVA_{year}"


def plugin_library(year: int) -> str:
	"""The file of the plugin under Linux, lib<plugin>.so."""
	return f"lib{plugin(year)}.so"


def plugin_year(file_name: str) -> int | None:
	"""The year whose plugin the library file is, or None for any other file."""
	match = _PLUGIN_LIBRARY.fullmatch(file_name)
	return int(match["year"]) if match else None
