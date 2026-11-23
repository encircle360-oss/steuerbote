"""The Erhebungszeiträume for which Steuerbote computes the Gewerbesteuer, with the figures of each.

The Steuermessbetrag is assessed for the Erhebungszeitraum (EZ), the calendar year (§ 14 Satz 2 GewStG); the
Gewerbeertrag of a company with a calendar-year Wirtschaftsjahr is that of the EZ. YEARS holds every EZ Steuerbote
computes, each with the statutes its figures come from (``Year.sources``), the GewStG as read on
gesetze-im-internet.de on 23 November 2026 (Stand: Art. 8 G v. 29.6.2026 I Nr. 197).

Two figures change with the EZ by statute, so a new EZ takes them from the schedule here:
- the minimum Hebesatz of § 16 Absatz 4 Satz 2 GewStG, 200 Prozent, and 280 Prozent „erstmals für den
  Erhebungszeitraum 2027“ (§ 36 Absatz 5b GewStG, both by Art. 8 of the Gesetz vom 29. Juni 2026, BGBl. 2026 I
  Nr. 197);
- the half of the fifth of § 8 Nummer 1 Buchstabe d Satz 2 GewStG for the rent of electric vehicles and bicycles,
  „letztmals für den Erhebungszeitraum 2030“ (§ 36 Absatz 4 Satz 3 GewStG); from 2031 their rent counts with the
  fifth of Satz 1.

Since EZ 2025 the Kürzung of § 9 Nummer 1 Satz 1 GewStG is „die im Erhebungszeitraum als Betriebsausgabe erfasste
Grundsteuer für zum Betriebsvermögen des Unternehmers gehörenden Grundbesitz“ (Jahressteuergesetz 2024, BGBl. 2024
I Nr. 387; § 36 Absatz 4b GewStG); the Einheitswert is gone, and the Jahresdokumentation E20 2025 took its lines
from the form.

The forms come from the Jahresdokumentation of the Datenart GewSt (E20). ERiC 44.3.6.0 knows the EZ 2015 to 2025
only (plugins checkGewSt_2015 to checkGewSt_2025), so the forms of 2026 are those of
Jahresdokumentation_E20_2025.ods (Versionslabel 11.0) until ELSTER publishes the one of 2026: 2026 is
``provisional`` and its ``documentation_year`` is 2025. The other tables keyed by the EZ are the form catalogue
(gewst/form.py) and the schema of the XML writer (elster/gewst_xml.py). The year check reads the files that
``jahresdokumentation`` and ``schema`` name, below Datenarten/ElsterErklaerung/GewSt of the documentation, and the
rules gewst/chain.py computes are its ``expected_rules`` (steuerbote.kst.years.RuleExpectation).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from steuerbote.ustva.years import UnknownYearError

_MINIMUM_HEBESATZ_UNTIL_2026 = Decimal("200")
_MINIMUM_HEBESATZ_FROM_2027 = Decimal("280")
_EV_RENT_PERCENT_UNTIL_2030 = Decimal("10")
_MOVABLE_RENT_PERCENT = Decimal("20")
# § 19 Absatz 1 Satz 1 GewStG: „am 15. Februar, 15. Mai, 15. August und 15. November“.
_PREPAYMENT_DAYS = ((2, 15), (5, 15), (8, 15), (11, 15))


@dataclass(frozen=True, slots=True)
class Year:
	"""An Erhebungszeitraum with the figures of the Gewerbesteuer. Percentages are given as the statute writes them:
	3.5 for 3,5 %, 25 for one quarter."""

	year: int
	messzahl: Decimal
	"""§ 11 Absatz 2 GewStG: „Die Steuermesszahl für den Gewerbeertrag beträgt 3,5 Prozent.“ A Kapitalgesellschaft
	has no Freibetrag (§ 11 Absatz 1 Satz 3 Nummer 1 and 2)."""
	financing_allowance: Decimal
	"""§ 8 Nummer 1 GewStG: the sum of the financing parts is added back „soweit die Summe den Betrag von 200 000
	Euro übersteigt“."""
	financing_percent: Decimal
	"""§ 8 Nummer 1 GewStG: „Ein Viertel der Summe“."""
	movable_rent_percent: Decimal
	"""§ 8 Nummer 1 Buchstabe d Satz 1: „einem Fünftel der Miet- und Pachtzinsen (einschließlich Leasingraten) für
	die Benutzung von beweglichen Wirtschaftsgütern des Anlagevermögens“."""
	movable_rent_ev_percent: Decimal
	"""§ 8 Nummer 1 Buchstabe d Satz 2: for electric vehicles, plug-in hybrids within its limits and bicycles „nur zur
	Hälfte“, for contracts concluded after 31 December 2019 (§ 36 Absatz 4 Satz 1)."""
	immovable_rent_percent: Decimal
	"""§ 8 Nummer 1 Buchstabe e: „der Hälfte der Miet- und Pachtzinsen ... für die Benutzung der unbeweglichen
	Wirtschaftsgüter des Anlagevermögens“."""
	licence_percent: Decimal
	"""§ 8 Nummer 1 Buchstabe f: „einem Viertel der Aufwendungen für die zeitlich befristete Überlassung von
	Rechten“."""
	participation_minimum: Decimal
	"""§ 9 Nummer 2a and 7 GewStG: dividends are cut „wenn die Beteiligung zu Beginn des Erhebungszeitraums mindestens
	15 Prozent“ of the capital is; below, § 8 Nummer 5 adds back the dividends § 8b Absatz 1 KStG exempts."""
	donation_profit_percent: Decimal
	"""§ 9 Nummer 5 Satz 1 GewStG: Zuwendungen up to „20 Prozent des um die Hinzurechnungen nach § 8 Nummer 9
	erhöhten Gewinns aus Gewerbebetrieb (§ 7)“."""
	donation_turnover_per_mille: Decimal
	"""§ 9 Nummer 5 Satz 1 GewStG: or up to „4 Promille der Summe der gesamten Umsätze und der im Wirtschaftsjahr
	aufgewendeten Löhne und Gehälter“."""
	loss_unlimited: Decimal
	"""§ 10a Satz 1 GewStG: Fehlbeträge reduce the Gewerbeertrag „bis zu einem Betrag in Höhe von 1 Million Euro“."""
	loss_share: Decimal
	"""§ 10a Satz 2 GewStG: beyond that „bis zu 60 Prozent“."""
	minimum_hebesatz: Decimal
	"""§ 16 Absatz 4 Satz 2 GewStG, in percent."""
	prepayment_minimum: Decimal
	"""§ 19 Absatz 5 Satz 2 GewStG: a Vorauszahlung „wird nur festgesetzt, wenn sie mindestens 50 Euro beträgt“."""
	documentation_year: int
	"""The year of the Jahresdokumentation E20 whose forms and rules the EZ takes."""
	provisional: bool
	"""True while the EZ takes the forms of an earlier Jahresdokumentation."""
	sources: tuple[str, ...]

	@property
	def prepayment_dates(self) -> tuple[date, ...]:
		"""The four Vorauszahlungen of the EZ (§ 19 Absatz 1 Satz 1 GewStG)."""
		return tuple(date(self.year, month, day) for month, day in _PREPAYMENT_DAYS)

	@property
	def datenart_version(self) -> str:
		return datenart_version(self.year)

	@property
	def plugin(self) -> str:
		return plugin(self.year)

	@property
	def jahresdokumentation(self) -> str:
		"""The Jahresdokumentation the forms of the EZ come from, that of the EZ itself unless it is provisional."""
		return jahresdokumentation(self.documentation_year)

	@property
	def schema(self) -> str:
		return schema(self.documentation_year)


def statutory_minimum_hebesatz(year: int) -> Decimal:
	"""The Hebesatz of § 16 Absatz 4 Satz 2 GewStG for an EZ, which a Gemeinde may not undercut."""
	return _MINIMUM_HEBESATZ_UNTIL_2026 if year <= 2026 else _MINIMUM_HEBESATZ_FROM_2027


def statutory_ev_rent_percent(year: int) -> Decimal:
	"""The part of the rent of electric vehicles and bicycles that § 8 Nummer 1 Buchstabe d counts in an EZ."""
	return _EV_RENT_PERCENT_UNTIL_2030 if year <= 2030 else _MOVABLE_RENT_PERCENT


_SOURCES_2026 = (
	"§ 8 Nummer 1 GewStG (Stand: Art. 8 G v. 29.6.2026 I Nr. 197); Buchstabe d Satz 2 by § 36 Absatz 4 Satz 3 GewStG "
	"until EZ 2030",
	"§ 8 Nummer 5 GewStG",
	"§ 9 Nummer 1 Satz 1 GewStG, the booked Grundsteuer from EZ 2025 by § 36 Absatz 4b GewStG",
	"§ 9 Nummer 2a und 7 GewStG",
	"§ 9 Nummer 5 GewStG",
	"§ 10a GewStG",
	"§ 11 GewStG; R 14.1 Satz 3 GewStR 2009",
	"§ 16 Absatz 4 Satz 2 GewStG; 280 Prozent from EZ 2027 by § 36 Absatz 5b GewStG",
	"§ 19 Absatz 1 und 5 GewStG",
	"forms: Jahresdokumentation_E20_2025.ods (Versionslabel 11.0) of the ERiC documentation 44.3.6.0, provisionally "
	"for 2026",
)

YEARS: MappingProxyType[int, Year] = MappingProxyType(
	{
		2026: Year(
			year=2026,
			messzahl=Decimal("3.5"),
			financing_allowance=Decimal("200000"),
			financing_percent=Decimal("25"),
			movable_rent_percent=_MOVABLE_RENT_PERCENT,
			movable_rent_ev_percent=statutory_ev_rent_percent(2026),
			immovable_rent_percent=Decimal("50"),
			licence_percent=Decimal("25"),
			participation_minimum=Decimal("15"),
			donation_profit_percent=Decimal("20"),
			donation_turnover_per_mille=Decimal("4"),
			loss_unlimited=Decimal("1000000"),
			loss_share=Decimal("60"),
			minimum_hebesatz=statutory_minimum_hebesatz(2026),
			prepayment_minimum=Decimal("50"),
			documentation_year=2025,
			provisional=True,
			sources=_SOURCES_2026,
		),
	}
)
LATEST_YEAR = max(YEARS)


def year_of(year: int) -> Year:
	"""The entry of the EZ; 2026.0 and True would find 2026 by hash, so only an int is a year."""
	if isinstance(year, bool) or not isinstance(year, int):
		raise TypeError(f"year must be an int, not {type(year).__name__}")
	try:
		return YEARS[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in YEARS)
		raise UnknownYearError(f"Steuerbote has no data for {year}; known years: {known}") from None


def datenart_version(year: int) -> str:
	"""The datenartVersion of the Gewerbesteuererklärung of an EZ, such as GewSt_2026."""
	return f"GewSt_{year}"


def plugin(year: int) -> str:
	"""The plugin of ERiC that checks the Datenart of an EZ, such as checkGewSt_2026."""
	return f"checkGewSt_{year}"


def jahresdokumentation(year: int) -> str:
	"""The file of the Jahresdokumentation E20 of a year, below Datenarten/ElsterErklaerung/GewSt/Jahresdokumentation."""
	return f"Jahresdokumentation_E20_{year}.ods"


def schema(year: int) -> str:
	"""The schema E20 of a year, below Datenarten/ElsterErklaerung/GewSt/Schema/<year>."""
	return f"E20-{year}.xsd"


def namespace(year: int) -> str:
	"""The targetNamespace of the schema E20 of a year."""
	return f"http://finkonsens.de/elster/elstererklaerung/gewst/e20/v{year}"
