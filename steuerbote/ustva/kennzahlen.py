"""Kennzahlen (Kz) of form USt 1 A, Umsatzsteuer-Voranmeldung, one catalogue per year.

The BMF publishes the form for the coming year every December; ELSTER accepts a filing only in the
Datenart of the period's year and keeps the current year and the three years before it open. The
catalogue is therefore chosen by the year of the period, so earlier periods and corrections keep
their own Kennzahlen and a new year's catalogue can be added whenever it is published.

2026: BMF letter of 29 December 2025 (GZ III C 3 - S 7344/00039/007/036), Vordruckmuster USt 1 A 2026
and its Anleitung. Line numbers (Zeile) and labels follow that form. Lines 37, 45 and 48 are sums the
form computes itself and have no Kennzahl. Every Kennzahl that changes the amount owed lies in one of
these sums or is the Sondervorauszahlung in Kennzahl 39; a catalogue that breaks this is refused when
it is built.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType


class Kind(Enum):
	"""What a Kennzahl holds, and therefore how it is rounded (see rounding.py)."""

	BASE = "base"
	TAX = "tax"
	FLAG = "flag"
	DATE = "date"
	CODE = "code"


class Effect(Enum):
	"""How a Kennzahl enters the Vorauszahlung/Überschuss in line 48 of the form."""

	NONE = "none"
	INCREASES = "increases"
	REDUCES = "reduces"


@dataclass(frozen=True, slots=True)
class Kennzahl:
	number: str
	line: int
	label: str
	kind: Kind
	effect: Effect = Effect.NONE
	rate: Decimal | None = None
	tax_kennzahl: str | None = None

	def __post_init__(self) -> None:
		if self.rate is not None and self.kind is not Kind.BASE:
			raise ValueError(f"Kennzahl {self.number}: only a base carries a rate")
		if self.tax_kennzahl is not None and self.kind is not Kind.BASE:
			raise ValueError(f"Kennzahl {self.number}: only a base points to a tax Kennzahl")
		if self.rate is not None and self.tax_kennzahl is not None:
			raise ValueError(f"Kennzahl {self.number}: a base derives its tax or reports it, not both")
		if self.kind is Kind.BASE and self.effect is not Effect.NONE and self.rate is None:
			raise ValueError(f"Kennzahl {self.number}: a base without rate cannot change the amount owed")
		if self.kind not in (Kind.BASE, Kind.TAX) and self.effect is not Effect.NONE:
			raise ValueError(f"Kennzahl {self.number}: only amounts change the amount owed")

	@property
	def derives_tax(self) -> bool:
		"""True when the form computes the tax from this base itself (lines 13, 14, 25 and 26)."""
		return self.rate is not None

	@property
	def holds_amount(self) -> bool:
		return self.kind in (Kind.BASE, Kind.TAX)


RATE_19 = Decimal("19")
RATE_7 = Decimal("7")

_FORM_2026 = (
	Kennzahl("10", 10, "Berichtigte Anmeldung", Kind.FLAG),
	Kennzahl(
		"22",
		11,
		"Belege (z. B. Verträge, Rechnungen) sind beigefügt bzw. werden gesondert eingereicht",
		Kind.FLAG,
	),
	Kennzahl(
		"70",
		12,
		"Wechsel von der Kleinunternehmer-Regelung (§ 19 UStG) zur Regelbesteuerung: Datum des Wechsels",
		Kind.DATE,
	),
	# A. Steuerpflichtige Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben
	Kennzahl(
		"81", 13, "Steuerpflichtige Umsätze zum Steuersatz von 19 %", Kind.BASE, Effect.INCREASES, RATE_19
	),
	Kennzahl(
		"86", 14, "Steuerpflichtige Umsätze zum Steuersatz von 7 %", Kind.BASE, Effect.INCREASES, RATE_7
	),
	Kennzahl("87", 15, "Steuerpflichtige Umsätze zum Steuersatz von 0 %", Kind.BASE),
	Kennzahl("35", 16, "Steuerpflichtige Umsätze zu anderen Steuersätzen", Kind.BASE, tax_kennzahl="36"),
	Kennzahl(
		"36", 16, "Steuer auf steuerpflichtige Umsätze zu anderen Steuersätzen", Kind.TAX, Effect.INCREASES
	),
	Kennzahl(
		"77",
		17,
		"Lieferungen land- und forstwirtschaftlicher Betriebe nach § 24 UStG an Abnehmer mit "
		"Umsatzsteuer-Identifikationsnummer",
		Kind.BASE,
	),
	Kennzahl(
		"76",
		18,
		"Umsätze, für die eine Steuer nach § 24 UStG zu entrichten ist (Sägewerkserzeugnisse, Getränke und "
		"alkoholische Flüssigkeiten, z. B. Wein)",
		Kind.BASE,
		tax_kennzahl="80",
	),
	Kennzahl(
		"80",
		18,
		"Steuer auf Umsätze, für die eine Steuer nach § 24 UStG zu entrichten ist",
		Kind.TAX,
		Effect.INCREASES,
	),
	# B. Steuerfreie Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben
	Kennzahl(
		"41",
		19,
		"Innergemeinschaftliche Lieferungen (§ 4 Nummer 1 Buchstabe b UStG) an Abnehmer mit "
		"Umsatzsteuer-Identifikationsnummer",
		Kind.BASE,
	),
	Kennzahl(
		"44",
		20,
		"Innergemeinschaftliche Lieferungen neuer Fahrzeuge an Abnehmer ohne Umsatzsteuer-Identifikationsnummer",
		Kind.BASE,
	),
	Kennzahl(
		"49",
		21,
		"Innergemeinschaftliche Lieferungen neuer Fahrzeuge außerhalb eines Unternehmens (§ 2a UStG)",
		Kind.BASE,
	),
	Kennzahl(
		"43",
		22,
		"Weitere steuerfreie Umsätze mit Vorsteuerabzug (z. B. Ausfuhrlieferungen, Umsätze nach § 4 Nummer 2 "
		"bis 7 UStG, Umsätze nach Verordnungen der EU)",
		Kind.BASE,
	),
	Kennzahl(
		"48",
		23,
		"Steuerfreie Umsätze ohne Vorsteuerabzug (z. B. Umsätze nach § 4 Nummer 8 bis 29 oder § 19 Absatz 1 UStG)",
		Kind.BASE,
	),
	# C. Innergemeinschaftliche Erwerbe
	Kennzahl(
		"91",
		24,
		"Steuerfreie innergemeinschaftliche Erwerbe von bestimmten Gegenständen und Anlagegold "
		"(§§ 4b und 25c UStG)",
		Kind.BASE,
	),
	Kennzahl(
		"89",
		25,
		"Steuerpflichtige innergemeinschaftliche Erwerbe zum Steuersatz von 19 %",
		Kind.BASE,
		Effect.INCREASES,
		RATE_19,
	),
	Kennzahl(
		"93",
		26,
		"Steuerpflichtige innergemeinschaftliche Erwerbe zum Steuersatz von 7 %",
		Kind.BASE,
		Effect.INCREASES,
		RATE_7,
	),
	Kennzahl("90", 27, "Steuerpflichtige innergemeinschaftliche Erwerbe zum Steuersatz von 0 %", Kind.BASE),
	Kennzahl(
		"95",
		28,
		"Steuerpflichtige innergemeinschaftliche Erwerbe zu anderen Steuersätzen",
		Kind.BASE,
		tax_kennzahl="98",
	),
	Kennzahl(
		"98",
		28,
		"Steuer auf steuerpflichtige innergemeinschaftliche Erwerbe zu anderen Steuersätzen",
		Kind.TAX,
		Effect.INCREASES,
	),
	Kennzahl(
		"94",
		29,
		"Steuerpflichtige innergemeinschaftliche Erwerbe neuer Fahrzeuge (§ 1b Absatz 2 und 3 UStG) von "
		"Lieferern ohne Umsatzsteuer-Identifikationsnummer zum allgemeinen Steuersatz",
		Kind.BASE,
		tax_kennzahl="96",
	),
	Kennzahl(
		"96",
		29,
		"Steuer auf innergemeinschaftliche Erwerbe neuer Fahrzeuge von Lieferern ohne "
		"Umsatzsteuer-Identifikationsnummer",
		Kind.TAX,
		Effect.INCREASES,
	),
	# D. Leistungsempfänger als Steuerschuldner (§ 13b UStG)
	Kennzahl(
		"46",
		30,
		"Sonstige Leistungen nach § 3a Absatz 2 UStG eines im übrigen Gemeinschaftsgebiet ansässigen "
		"Unternehmers (§ 13b Absatz 1 UStG)",
		Kind.BASE,
		tax_kennzahl="47",
	),
	Kennzahl(
		"47",
		30,
		"Steuer auf sonstige Leistungen nach § 3a Absatz 2 UStG eines im übrigen Gemeinschaftsgebiet "
		"ansässigen Unternehmers",
		Kind.TAX,
		Effect.INCREASES,
	),
	Kennzahl(
		"73",
		31,
		"Umsätze, die unter das GrEStG fallen (§ 13b Absatz 2 Nummer 3 UStG)",
		Kind.BASE,
		tax_kennzahl="74",
	),
	Kennzahl("74", 31, "Steuer auf Umsätze, die unter das GrEStG fallen", Kind.TAX, Effect.INCREASES),
	Kennzahl(
		"84",
		32,
		"Andere Leistungen (§ 13b Absatz 2 Nummer 1, 2, 4 bis 12 UStG)",
		Kind.BASE,
		tax_kennzahl="85",
	),
	Kennzahl(
		"85",
		32,
		"Steuer auf andere Leistungen (§ 13b Absatz 2 Nummer 1, 2, 4 bis 12 UStG)",
		Kind.TAX,
		Effect.INCREASES,
	),
	# E. Ergänzende Angaben zu Umsätzen
	Kennzahl(
		"42",
		33,
		"Lieferungen des ersten Abnehmers bei innergemeinschaftlichen Dreiecksgeschäften (§ 25b UStG)",
		Kind.BASE,
	),
	Kennzahl(
		"60",
		34,
		"Steuerpflichtige Umsätze des leistenden Unternehmers, für die der Leistungsempfänger die Steuer "
		"nach § 13b Absatz 5 UStG schuldet",
		Kind.BASE,
	),
	Kennzahl("21", 35, "Nicht steuerbare sonstige Leistungen gemäß § 18b Satz 1 Nummer 2 UStG", Kind.BASE),
	Kennzahl("45", 36, "Übrige nicht steuerbare Umsätze (Leistungsort nicht im Inland)", Kind.BASE),
	# F. Abziehbare Vorsteuerbeträge und Berichtigung des Vorsteuerabzugs
	Kennzahl(
		"66",
		38,
		"Vorsteuerbeträge aus Rechnungen von anderen Unternehmern (§ 15 Absatz 1 Satz 1 Nummer 1 UStG), aus "
		"Leistungen im Sinne des § 27 Absatz 40a UStG und aus innergemeinschaftlichen Dreiecksgeschäften "
		"(§ 25b Absatz 5 UStG)",
		Kind.TAX,
		Effect.REDUCES,
	),
	Kennzahl(
		"61",
		39,
		"Vorsteuerbeträge aus dem innergemeinschaftlichen Erwerb von Gegenständen "
		"(§ 15 Absatz 1 Satz 1 Nummer 3 UStG)",
		Kind.TAX,
		Effect.REDUCES,
	),
	Kennzahl(
		"62",
		40,
		"Entstandene Einfuhrumsatzsteuer (§ 15 Absatz 1 Satz 1 Nummer 2 UStG)",
		Kind.TAX,
		Effect.REDUCES,
	),
	Kennzahl(
		"67",
		41,
		"Vorsteuerbeträge aus Leistungen im Sinne des § 13b UStG (§ 15 Absatz 1 Satz 1 Nummer 4 UStG)",
		Kind.TAX,
		Effect.REDUCES,
	),
	Kennzahl(
		"63",
		42,
		"Vorsteuerbeträge, die nach allgemeinen Durchschnittssätzen berechnet sind (§ 23a UStG)",
		Kind.TAX,
		Effect.REDUCES,
	),
	Kennzahl(
		"59",
		43,
		"Vorsteuerabzug für innergemeinschaftliche Lieferungen neuer Fahrzeuge außerhalb eines Unternehmens "
		"(§ 2a UStG) sowie von Kleinunternehmern im Sinne des § 19 Absatz 1 UStG (§ 15 Absatz 4a UStG)",
		Kind.TAX,
		Effect.REDUCES,
	),
	Kennzahl("64", 44, "Berichtigung des Vorsteuerabzugs (§ 15a UStG)", Kind.TAX, Effect.REDUCES),
	# G. Andere Steuerbeträge
	Kennzahl(
		"65",
		46,
		"Steuer infolge des Wechsels der Besteuerungsform sowie Nachsteuer auf versteuerte Anzahlungen und "
		"ähnlichem wegen Steuersatzänderung",
		Kind.TAX,
		Effect.INCREASES,
	),
	Kennzahl(
		"69",
		47,
		"In Rechnungen unrichtig oder unberechtigt ausgewiesene Steuerbeträge (§ 14c UStG) sowie "
		"Steuerbeträge, die nach § 6a Absatz 4 Satz 2, § 17 Absatz 1 Satz 7, § 25b Absatz 2 UStG oder von "
		"einem Auslagerer oder Lagerhalter nach § 27 Absatz 40a UStG geschuldet werden",
		Kind.TAX,
		Effect.INCREASES,
	),
	# H. Vorauszahlung/Überschuss
	Kennzahl(
		"39",
		49,
		"Abzug der festgesetzten Sondervorauszahlung für Dauerfristverlängerung (in der Regel nur in der "
		"letzten Voranmeldung des Besteuerungszeitraums auszufüllen)",
		Kind.TAX,
		Effect.REDUCES,
	),
	Kennzahl(
		"83",
		50,
		"Verbleibende Umsatzsteuer-Vorauszahlung / Verbleibender Überschuss (bitte in jedem Fall ausfüllen)",
		Kind.TAX,
	),
	# I. Ergänzende Angaben zu Minderungen nach § 17 Absatz 1 Sätze 1 und 2 i. V. m. Absatz 2 Nummer 1 Satz 1 UStG
	Kennzahl("50", 51, "Minderung der Bemessungsgrundlage (in den Zeilen 13 bis 18 enthalten)", Kind.BASE),
	Kennzahl(
		"37",
		52,
		"Minderung der abziehbaren Vorsteuerbeträge (in der Zeile 38 aus Rechnungen von anderen Unternehmern "
		"sowie in den Zeilen 42 und 43 enthalten)",
		Kind.TAX,
	),
	# J. Sonstige Angaben
	Kennzahl(
		"29",
		53,
		"Verrechnung des Erstattungsbetrags erwünscht / Erstattungsbetrag ist abgetreten",
		Kind.FLAG,
	),
	Kennzahl(
		"26",
		54,
		"Das SEPA-Lastschriftmandat soll ausnahmsweise für diesen Voranmeldungszeitraum nicht verwendet werden",
		Kind.FLAG,
	),
	Kennzahl("500", 55, "Ergänzende Angaben zur Steueranmeldung (1 bis 4)", Kind.CODE),
)


class UnknownYearError(ValueError):
	"""No catalogue for the year of the period; the app needs the form of that year first."""


BALANCE_KENNZAHL = "83"
SONDERVORAUSZAHLUNG_KENNZAHL = "39"

# The sums the form computes itself, by the lines they cover.
OUTPUT_TAX_LINES = range(13, 33)
INPUT_TAX_LINES = range(38, 45)
OTHER_TAX_LINES = range(46, 48)


def _enters_a_sum(kennzahl: Kennzahl) -> bool:
	return (
		kennzahl.number == SONDERVORAUSZAHLUNG_KENNZAHL
		or (kennzahl.effect is Effect.INCREASES and kennzahl.line in OUTPUT_TAX_LINES)
		or (kennzahl.effect is Effect.REDUCES and kennzahl.line in INPUT_TAX_LINES)
		or (kennzahl.effect is Effect.INCREASES and kennzahl.line in OTHER_TAX_LINES)
	)


def _index(form: tuple[Kennzahl, ...]) -> MappingProxyType[str, Kennzahl]:
	"""Index a form by Kennzahl, refusing a form whose amounts would not all reach Kennzahl 83.

	A Kennzahl with an effect outside the sums of its effect would silently drop out of the amount
	owed, for example after a line moved in a new year's form.
	"""
	index: dict[str, Kennzahl] = {}
	for kennzahl in form:
		if kennzahl.number in index:
			raise ValueError(f"Kennzahl {kennzahl.number} is listed twice")
		if kennzahl.effect is not Effect.NONE and not _enters_a_sum(kennzahl):
			raise ValueError(
				f"Kennzahl {kennzahl.number} on line {kennzahl.line} changes the amount owed "
				"but is in none of the form's sums"
			)
		index[kennzahl.number] = kennzahl
	return MappingProxyType(index)


CATALOGUES: MappingProxyType[int, MappingProxyType[str, Kennzahl]] = MappingProxyType(
	{2026: _index(_FORM_2026)}
)
LATEST_YEAR = max(CATALOGUES)


def catalogue_for(year: int) -> MappingProxyType[str, Kennzahl]:
	"""The Kennzahlen of the form for the given year."""
	try:
		return CATALOGUES[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in sorted(CATALOGUES))
		raise UnknownYearError(f"no Kennzahlen catalogue for {year}; known years: {known}") from None


KENNZAHLEN = catalogue_for(LATEST_YEAR)
