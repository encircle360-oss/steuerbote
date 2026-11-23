"""The Veranlagungszeiträume for which Steuerbote computes the Körperschaftsteuer, with the rates and limits of each.

The Körperschaftsteuer is a Jahressteuer whose bases are determined for a calendar year, the Veranlagungszeitraum
(VZ, § 7 Absatz 3 KStG); a company that keeps HGB books determines its profit by its Wirtschaftsjahr, which with a
calendar-year Wirtschaftsjahr is the VZ itself (§ 7 Absatz 4 KStG). YEARS holds every VZ Steuerbote computes, each
with the statutes its figures come from (``Year.sources``), read on gesetze-im-internet.de on 23 November 2026:
the KStG „zuletzt geändert durch Art. 30 G v. 4.2.2026 I Nr. 33“, the EStG as of Art. 1 G v. 15.10.2026 I Nr. 307
and the SolZG 1995.

Two figures change with the VZ by statute, so a new VZ takes them from the schedule here: the rate of § 23 Absatz 1
KStG, 15 % up to 2027, then one point less each year down to 10 % from 2032 (Gesetz für ein steuerliches
Investitionssofortprogramm, BGBl. 2025 I Nr. 161), and the share of § 10d Absatz 2 Satz 1 EStG beyond 1 Million
Euro, 70 % up to 2027 and 60 % from 2028 (Wachstumschancengesetz, BGBl. 2024 I Nr. 108, Art. 2 Nr. 4, Art. 6 Nr. 1
with § 52 Absatz 18b EStG and Art. 35 Absatz 4 and 9).

The forms come from the Jahresdokumentation of the Datenart KSt (E30) of the ERiC documentation. ERiC 44.3.6.0 knows
the VZ 2015 to 2025 only (plugins checkKSt_2015 to checkKSt_2025), so the forms of 2026 are those of
Jahresdokumentation_E30_2025.ods (Versionslabel 7.0) until ELSTER publishes the one of 2026: 2026 is
``provisional`` and its ``documentation_year`` is 2025. The tables keyed by the VZ besides YEARS are the form
catalogue (kst/form.py), the schema of the XML writer (elster/kst_xml.py) and the defaults of the Income Tax Mapping
(kst/defaults.py).

The year check reads, for a year, the Jahresdokumentation and the schema that ``jahresdokumentation`` and
``schema`` name, below Datenarten/ElsterErklaerung/KSt of the documentation. The modules of the core say which
rules of the Jahresdokumentation they compute, and with which factors, as RuleExpectation: ``expected_rules`` of
kst/chain.py, kst/losses.py and kst/einlagekonto.py. The year check finds each rule by its Fehlercode in the sheet
„<form> - Regeln“ and names the terms its Prüfbedingung lacks (``RuleExpectation.missing_terms``); a provisional
year is compared with the newest Jahresdokumentation there is.

The module imports nothing of Steuerbote but the error of an unknown year, so that every part can name its VZ.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from steuerbote.ustva.years import UnknownYearError

HUNDRED = Decimal("100")
# § 23 Absatz 1 KStG: „Die Körperschaftsteuer beträgt für 1. Veranlagungszeiträume bis 2027 15 Prozent, 2. den
# Veranlagungszeitraum 2028 14 Prozent, 3. den Veranlagungszeitraum 2029 13 Prozent, 4. den Veranlagungszeitraum 2030
# 12 Prozent, 5. den Veranlagungszeitraum 2031 11 Prozent und 6. Veranlagungszeiträume ab 2032 10 Prozent des zu
# versteuernden Einkommens.“ Each step is the first VZ of a rate.
_RATE_STEPS = ((2028, Decimal("14")), (2029, Decimal("13")), (2030, Decimal("12")), (2031, Decimal("11")))
_RATE_UNTIL_2027 = Decimal("15")
_RATE_FROM_2032 = Decimal("10")
# § 10d Absatz 2 Satz 1 EStG: 70 Prozent „erstmals für den Veranlagungszeitraum 2024“ (Art. 2 Nr. 4
# Wachstumschancengesetz, § 52 Absatz 18b Satz 3 EStG); 60 Prozent by Art. 6 Nr. 1, in force on 1 January 2028
# (Art. 35 Absatz 9), „erstmals für den Veranlagungszeitraum 2028“ (the sentence Art. 6 Nr. 2 adds to § 52 Absatz 18b).
_LOSS_SHARE_UNTIL_2027 = Decimal("70")
_LOSS_SHARE_FROM_2028 = Decimal("60")
# § 37 Absatz 1 Satz 1 EStG with § 31 Absatz 1 KStG: „am 10. März, 10. Juni, 10. September und 10. Dezember“.
_PREPAYMENT_DAYS = ((3, 10), (6, 10), (9, 10), (12, 10))


@dataclass(frozen=True, slots=True)
class Year:
	"""A Veranlagungszeitraum with the rates and limits of the Körperschaftsteuer. Percentages are given as the
	statute writes them: 15 for 15 %, 5.5 for 5,5 %."""

	year: int
	rate: Decimal
	"""§ 23 Absatz 1 KStG, in percent of the zu versteuerndes Einkommen."""
	solz_rate: Decimal
	"""§ 4 Satz 1 SolZG, in percent of the festgesetzte Körperschaftsteuer. The Freigrenze of § 3 Absatz 3 SolZG
	applies to „einkommensteuerpflichtige Personen“ only, so a Körperschaft has none."""
	loss_carry_back: Decimal
	"""§ 10d Absatz 1 Satz 1 EStG: the Verlustrücktrag reaches „bis zu einem Betrag von 1 000 000 Euro“."""
	loss_unlimited: Decimal
	"""§ 10d Absatz 2 Satz 1 EStG: the Verlustvortrag is deducted „bis zu einem Gesamtbetrag der Einkünfte von 1
	Million Euro unbeschränkt“."""
	loss_share: Decimal
	"""§ 10d Absatz 2 Satz 1 EStG: beyond that, „bis zu 70 Prozent des 1 Million Euro übersteigenden Gesamtbetrags der
	Einkünfte“."""
	donation_income_percent: Decimal
	"""§ 9 Absatz 1 Nummer 2 Satz 1 Buchstabe a KStG: Zuwendungen up to „20 Prozent des Einkommens“."""
	donation_turnover_per_mille: Decimal
	"""Buchstabe b: or up to „4 Promille der Summe der gesamten Umsätze und der im Kalenderjahr aufgewendeten Löhne
	und Gehälter“."""
	p8b_percent: Decimal
	"""§ 8b Absatz 3 Satz 1 and Absatz 5 Satz 1 KStG: 5 Prozent of an exempt gain or dividend „gelten als
	Ausgaben, die nicht als Betriebsausgaben abgezogen werden dürfen“."""
	p8b_minimum_holding: Decimal
	"""§ 8b Absatz 4 Satz 1 KStG: dividends are taxed if the holding at the start of the calendar year was „weniger
	als 10 Prozent des Grund- oder Stammkapitals“."""
	gift_limit: Decimal
	"""§ 4 Absatz 5 Satz 1 Nummer 1 Satz 2 EStG: gifts to one recipient in a year above 50 Euro are not
	deductible."""
	entertainment_deductible_percent: Decimal
	"""§ 4 Absatz 5 Satz 1 Nummer 2 Satz 1 EStG: entertainment is deductible up to „70 Prozent der Aufwendungen“."""
	supervisory_board_percent: Decimal
	"""§ 10 Nummer 4 KStG: „die Hälfte der Vergütungen jeder Art“ to the members of the Aufsichtsrat is not
	deductible."""
	iab_percent: Decimal
	"""§ 7g Absatz 1 Satz 1 EStG: an Investitionsabzugsbetrag of „bis zu 50 Prozent der voraussichtlichen
	Anschaffungs- oder Herstellungskosten“."""
	iab_profit_limit: Decimal
	"""§ 7g Absatz 1 Satz 2 Nummer 1 Buchstabe b EStG: only if the profit „200 000 Euro nicht überschreitet“."""
	iab_total_limit: Decimal
	"""§ 7g Absatz 1 Satz 4 EStG: the deductions of four Wirtschaftsjahre „darf je Betrieb 200 000 Euro nicht
	übersteigen“."""
	interest_barrier: Decimal
	"""§ 4h Absatz 2 Satz 1 Buchstabe a EStG: the Zinsschranke does not apply if „die Nettozinsaufwendungen des
	Betriebs weniger als drei Millionen Euro betragen“."""
	documentation_year: int
	"""The year of the Jahresdokumentation E30 whose forms and rules the VZ takes."""
	provisional: bool
	"""True while the VZ takes the forms of an earlier Jahresdokumentation."""
	sources: tuple[str, ...]

	@property
	def prepayment_dates(self) -> tuple[date, ...]:
		"""The four Vorauszahlungen of the VZ (§ 37 Absatz 1 Satz 1 EStG); those on the Solidaritätszuschlag fall on the
		same days (§ 1 Absatz 4 Satz 1 SolZG)."""
		return tuple(date(self.year, month, day) for month, day in _PREPAYMENT_DAYS)

	@property
	def datenart_version(self) -> str:
		return datenart_version(self.year)

	@property
	def plugin(self) -> str:
		return plugin(self.year)

	@property
	def jahresdokumentation(self) -> str:
		"""The Jahresdokumentation the forms of the VZ come from, that of the VZ itself unless it is provisional."""
		return jahresdokumentation(self.documentation_year)

	@property
	def schema(self) -> str:
		return schema(self.documentation_year)


def statutory_rate(year: int) -> Decimal:
	"""The rate of § 23 Absatz 1 KStG for a VZ."""
	if year <= 2027:
		return _RATE_UNTIL_2027
	return next((rate for first, rate in _RATE_STEPS if first == year), _RATE_FROM_2032)


def statutory_loss_share(year: int) -> Decimal:
	"""The share of § 10d Absatz 2 Satz 1 EStG beyond 1 Million Euro for a VZ."""
	return _LOSS_SHARE_UNTIL_2027 if year <= 2027 else _LOSS_SHARE_FROM_2028


_SOURCES_2026 = (
	"§ 23 Absatz 1 KStG (zuletzt geändert durch Art. 30 G v. 4.2.2026 I Nr. 33); the rates from 2028 by the Gesetz für "
	"ein steuerliches Investitionssofortprogramm, BGBl. 2025 I Nr. 161",
	"§ 3 Absatz 1 Nummer 1 and Absatz 3, § 4 SolZG 1995",
	"§ 10d Absatz 1 und 2 EStG (Stand Art. 1 G v. 15.10.2026 I Nr. 307); 70 Prozent by Art. 2 Nr. 4, 60 Prozent from "
	"VZ 2028 by Art. 6 Nr. 1 Wachstumschancengesetz, BGBl. 2024 I Nr. 108",
	"§ 9 Absatz 1 Nummer 2 KStG",
	"§ 8b Absatz 3 bis 5 KStG",
	"§ 4 Absatz 5 Satz 1 Nummer 1 und 2 EStG; 50 Euro by Art. 2 Nr. 1 Wachstumschancengesetz",
	"§ 10 Nummer 4 KStG",
	"§ 7g Absatz 1 EStG",
	"§ 4h Absatz 2 Satz 1 Buchstabe a EStG",
	"§ 37 Absatz 1 Satz 1 EStG with § 31 Absatz 1 KStG and § 1 Absatz 4 SolZG",
	"forms: Jahresdokumentation_E30_2025.ods (Versionslabel 7.0) of the ERiC documentation 44.3.6.0, provisionally "
	"for 2026",
)

YEARS: MappingProxyType[int, Year] = MappingProxyType(
	{
		2026: Year(
			year=2026,
			rate=statutory_rate(2026),
			solz_rate=Decimal("5.5"),
			loss_carry_back=Decimal("1000000"),
			loss_unlimited=Decimal("1000000"),
			loss_share=statutory_loss_share(2026),
			donation_income_percent=Decimal("20"),
			donation_turnover_per_mille=Decimal("4"),
			p8b_percent=Decimal("5"),
			p8b_minimum_holding=Decimal("10"),
			gift_limit=Decimal("50"),
			entertainment_deductible_percent=Decimal("70"),
			supervisory_board_percent=Decimal("50"),
			iab_percent=Decimal("50"),
			iab_profit_limit=Decimal("200000"),
			iab_total_limit=Decimal("200000"),
			interest_barrier=Decimal("3000000"),
			documentation_year=2025,
			provisional=True,
			sources=_SOURCES_2026,
		),
	}
)
LATEST_YEAR = max(YEARS)


def year_of(year: int) -> Year:
	"""The entry of the VZ; 2026.0 and True would find 2026 by hash, so only an int is a year."""
	if isinstance(year, bool) or not isinstance(year, int):
		raise TypeError(f"year must be an int, not {type(year).__name__}")
	try:
		return YEARS[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in YEARS)
		raise UnknownYearError(f"Steuerbote has no data for {year}; known years: {known}") from None


def datenart_version(year: int) -> str:
	"""The datenartVersion of the Körperschaftsteuererklärung of a VZ, such as KSt_30_2026."""
	return f"KSt_30_{year}"


def plugin(year: int) -> str:
	"""The plugin of ERiC that checks the Datenart of a VZ, such as checkKSt_2026."""
	return f"checkKSt_{year}"


def jahresdokumentation(year: int) -> str:
	"""The file of the Jahresdokumentation E30 of a year, below Datenarten/ElsterErklaerung/KSt/Jahresdokumentation."""
	return f"Jahresdokumentation_E30_{year}.ods"


def schema(year: int) -> str:
	"""The schema E30 of a year, below Datenarten/ElsterErklaerung/KSt/Schema/<year>."""
	return f"E30-{year}.xsd"


def namespace(year: int) -> str:
	"""The targetNamespace of the schema E30 of a year."""
	return f"http://finkonsens.de/elster/elstererklaerung/kst/e30/v{year}"


def factor(percent: Decimal) -> str:
	"""A percentage as the Prüfbedingungen of the Jahresdokumentation multiply with it: 15 as 0.15, 70 as 0.7."""
	return format((percent / HUNDRED).normalize(), "f")


@dataclass(frozen=True, slots=True)
class RuleExpectation:
	"""A rule of the Jahresdokumentation that the core computes, and what its Prüfbedingung has to say for that.

	``code`` is the Fehlercode and ``form`` the form whose sheet „<form> - Regeln“ holds the rule. ``terms`` are
	parts of the Prüfbedingung written without blanks, such as Abrunden([E8007504]*0.15) for the rate of the
	Körperschaftsteuer or -[E8003301] for a field the formula subtracts; the factors come from the year data.
	"""

	code: str
	form: str
	terms: tuple[str, ...]

	def __post_init__(self) -> None:
		for term in self.terms:
			if "".join(term.split()) != term:
				raise ValueError(f"rule {self.code}: a term is written without blanks, not {term!r}")

	@property
	def sheet(self) -> str:
		return f"{self.form} - Regeln"

	def missing_terms(self, condition: str) -> tuple[str, ...]:
		"""The terms that the Prüfbedingung lacks, blanks and line breaks aside. A term with a leading plus, the sign of
		a field in a sum, is also found where it opens the sum, after „{“ or „!=“."""
		written = "".join(condition.split())
		return tuple(term for term in self.terms if not _found(term, written))


def _found(term: str, written: str) -> bool:
	if term in written:
		return True
	if term.startswith("+"):
		return f"{{{term[1:]}" in written or f"!={term[1:]}" in written
	return False
