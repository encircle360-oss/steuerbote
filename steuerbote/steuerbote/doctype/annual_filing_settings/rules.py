"""Rules of the Annual Filing Settings: what the year-end filings of a company read beyond its ledger.

The Umsatzsteuererklärung, the Körperschaft- and the Gewerbesteuererklärung, the E-Bilanz and the
Jahresabschluss share one document per company. This module checks its rows before they are stored and gives
them to the filings as values. The forms set the lengths and patterns: the fields of the Jahresdokumentation
E50 2026 (USt 2 A and Vorsatz), E30 2025 (KSt), E20 2025 (GewSt 1 A) and E21 2025 (GewSt 1 D) of the ERiC
documentation 44.3.6.0. The Körperschaft- and Gewerbesteuererklärung of 2026 keep the fields of 2025 until ERiC
ships the year.

Legal form. Steuerbote files for a GmbH and for a UG (haftungsbeschränkt), the GmbH founded below the
Mindeststammkapital (§ 5a Abs. 1 GmbHG). KSt 1 line 9 (E8001105) and GewSt 1 A line 14 (E4000501) take the
keys „350 [Gesellschaft mit beschränkter Haftung]“ and „370 [Unternehmergesellschaft (haftungsbeschränkt)]“
(types RECHTSFORM_KOERPERSCHAFTEN_V3 and RECHTSFORM_GEWERBESTEUER_V2, sheet „Benutzerdefinierte Typen“). The GCD
of taxonomy 6.9 names them genInfo.company.id.legalStatus.legalStatus.GMBH and .UG; the documentation label of
.UG says „Nicht vorgesehen für Bundesanzeiger, Erfassung unter "Gesellschaft mit beschränkter Haftung"“, so the
disclosure files a UG as a GmbH (de-gcd-2025-04-01-label-de.xml).

Texts. Every text of the Erklärungen keeps to the character set of ELSTER, as steuerbote.elster.charset describes
it, and to the length of its field: the Gegenstand des Unternehmens at most 25 characters (GewSt 1 A line 4,
E4000201), the Ort der Geschäftsleitung and the Ort des Sitzes at most 24 (KSt 1 lines 6 and 7, E8000501 and
E8000601), the Steuerberatung at most 55 per line and 60 for the Mandantennummer (USt 2 A „Mitwirk“, E3002501 to
E3002509; KSt 1 lines 100 to 102, E8019910 to E8019918).

Address. USt 2 A lines 8 to 13 and the GCD take the house number apart from the street: digits only, at most four
(E3001203, pattern ^(?=.{1,4}$)[0-9]+), a suffix of at most six characters (E3001204), an Adressergänzung of at
most 25 (E3001205), a German postal code of five digits not beginning with 00 (type Postleitzahl_DE) or another of
at most twelve (E3001208). The Vorsatz of every Erklärung names the Absender with street and house number on one
line of at most 30 characters (AbsStr) and the town in at most 29 (AbsOrt, sheet „Vorsatz - Felder“).
split_street() splits the street of the VAT Return Settings, which holds both, at its last digits after a blank.

Years. A Steuerberatung that prepares the Erklärungen of a year moves their deadline to the last day of February
of the second year after it (§ 149 Abs. 3 Nr. 2 to 4 AO) and sets USt 2 A line 127 (E3002602) and KSt 1 line 100
(E8001901). Only for such Erklärungen may the Finanzamt ask early (§ 149 Abs. 4 Satz 1 AO): „vor dem letzten Tag
des Monats Februar des zweiten auf den Besteuerungszeitraum folgenden Kalenderjahres“, and never earlier than the
deadline of Absatz 2 („keine kürzere als die in Absatz 2 bestimmte Frist“, Satz 6), seven months after the year.
A Kleinunternehmer files no Umsatzsteuererklärung: § 19 Abs. 1 Satz 2 UStG leaves out
„die Erklärungspflichten (§ 18 Absatz 1 bis 4)“. A subsidiary exempt under § 264 Abs. 3 HGB states why.

Shareholders. KSt 1 lines 21 to 23b name each Anteilseigner with name, street and town (rule 8912022) and each
holding period with the amount in euros, the share in percent and its first day (rule 8912153); the share takes
at most four decimals and 100 (E8122105). The nominal amount is a sum of Geschäftsanteile, each in full euros
(§ 5 Abs. 2 Satz 1 GmbHG). „Die Höhe der Beteiligungen aller Anteilseigner darf nicht mehr als 100 % und nicht weniger
als 99 % betragen“ (rule 8931029, sheet „KSt1 - Regeln“): the settings hold that on every day a shareholder holds
shares. A shareholder may give a Steuernummer (13 digits for ELSTER, type Steuernummer), an
Identifikationsnummer of eleven digits (type IDNr), which only natural persons have (§ 139b Abs. 1 AO), and a
Wirtschafts-Identifikationsnummer of DE and nine digits (type W_IdNr; § 139c Abs. 1 Satz 2 AO). A company may
process an Identifikationsnummer only for its transmissions to the Finanzbehörden (§ 139b Abs. 2 Satz 2 Nr. 1 AO),
so these numbers never appear in a message.

Managing directors. Every Geschäftsführer signs the Jahresabschluss with the date (§ 245 HGB); whether one is a
shareholder decides the Gesellschafter-Geschäftsführer positions of the E-Bilanz.

Gewerbesteuer. The Amtlicher Gemeindeschlüssel has the Länderschlüssel 01 to 16 and six more digits (GewSt 1 D,
E4101103 of Jahresdokumentation E21 2025), the Hebenummer of the Gemeinde at most 28 characters (GewSt 1 A line 33,
E4001803). The Hebesatz is the Gemeinde's, set for one or more calendar years (§ 16 Abs. 2 GewStG), and at least
200 %: „Er beträgt 200 Prozent, wenn die Gemeinde nicht einen höheren Hebesatz bestimmt hat“ (§ 16 Abs. 4 Satz 2
GewStG up to the Erhebungszeitraum 2026). Art. 8 Nr. 1 of the Neuntes Gesetz zur Änderung von Vorschriften im
Steuerberatungsrecht sowie im Steuerrecht of 29 June 2026 (BGBl. 2026 I Nr. 197) replaces 200 by 280, first for the
Erhebungszeitraum 2027 (§ 36 Abs. 5b GewStG).

Holdings. § 8b Abs. 4 Satz 1 KStG reads the share „zu Beginn des Kalenderjahres“, § 9 Nr. 2a and 7 GewStG the share
„zu Beginn des Erhebungszeitraums“, so a holding has a row per year.

Vorauszahlungen. The Körperschaftsteuer is paid ahead on 10 March, June, September and December (§ 31 Abs. 1 KStG,
§ 37 Abs. 1 EStG), the Solidaritätszuschlag with it (§ 3 Abs. 1 Nr. 2 SolZG), the Gewerbesteuer to the Gemeinde on
15 February, May, August and November (§ 19 Abs. 1 GewStG). Each row is an amount in cents of a notice.

Carry-forwards. The amounts the Finanzamt last stated: the Verlustvortrag (§ 10d Abs. 4 EStG), the losses from
Termingeschäfte (§ 15 Abs. 4 Satz 3 to 5 EStG), the Zuwendungsvortrag of the Körperschaftsteuer (§ 9 Abs. 1 Nr. 2
KStG) and of the Gewerbesteuer (§ 9 Nr. 5 GewStG), the Fehlbetrag (§ 10a GewStG), the steuerliches Einlagekonto
(§ 27 Abs. 2 KStG) and the Sonderausweis (§ 28 Abs. 1 Satz 3 KStG).

Size. § 267 Abs. 4 HGB decides the size class on two consecutive Abschlussstichtage, so the settings keep the
criteria of § 267 and § 267a HGB per fiscal year and the class applied, with its source.

Messages are English templates with positional placeholders. SettingsError keeps the template and its values
apart, so that the Frappe layer translates the template before formatting it. This module is pure Python and never
imports Frappe.
"""

import re
from collections.abc import Callable, Hashable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from steuerbote.elster.charset import CharsetError, describe, transliterate
from steuerbote.elster.steuernummer import SCHEMES, STATE_CODES, SteuernummerError, to_elster
from steuerbote.ustva.period import day_label
from steuerbote.ustva.rounding import CENT, EURO, HUNDRED, ZERO, require_decimal


class SettingsError(ValueError):
	"""A rule of the settings is broken; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


# Legal form

NOT_A_LEGAL_FORM = "{0} is not a legal form Steuerbote files for: GmbH or UG."


class LegalForm(StrEnum):
	GMBH = "GmbH"
	UG = "UG"


RECHTSFORM: MappingProxyType[LegalForm, str] = MappingProxyType({LegalForm.GMBH: "350", LegalForm.UG: "370"})
LEGAL_STATUS: MappingProxyType[LegalForm, str] = MappingProxyType(
	{LegalForm.GMBH: "GMBH", LegalForm.UG: "UG"}
)


def legal_form(value: object) -> LegalForm:
	try:
		return LegalForm(value)
	except ValueError:
		raise SettingsError(NOT_A_LEGAL_FORM, value) from None


def rechtsform(value: object) -> str:
	"""The key of the Rechtsform in KSt 1 line 9 and GewSt 1 A line 14."""
	return RECHTSFORM[legal_form(value)]


def legal_status(value: object, *, disclosure: bool = False) -> str:
	"""The legalStatus of the GCD: GMBH or UG in the E-Bilanz; the disclosure files a UG as GMBH."""
	form = legal_form(value)
	return LEGAL_STATUS[LegalForm.GMBH if disclosure else form]


# Texts

TEXT_TOO_LONG = "{0} has {1} characters; ELSTER takes at most {2}."
TEXT_CHARACTERS = "{0} contains characters ELSTER does not take: {1}."

STREET_LINE_LENGTH = 30
# The texts of the settings that go into the forms, with the length their fields take (see above).
TEXT_LENGTHS: MappingProxyType[str, int] = MappingProxyType(
	{
		"business_purpose": 25,
		"management_seat": 24,
		"registered_seat": 24,
		"street": STREET_LINE_LENGTH,
		"house_number_suffix": 6,
		"address_supplement": 25,
		"postal_code": 12,
		"city": 29,
		"advisor_name": 55,
		"advisor_first_name": 55,
		"advisor_street": 55,
		"advisor_town": 55,
		"advisor_phone": 55,
		"advisor_details": 55,
		"advisor_client_number": 60,
		"advisor_clerk": 55,
	}
)
# The texts of the tables that go into the forms: KSt 1 lines 22b to 22e (E8122113, E8122101 to E8122103) and
# GewSt 1 A lines 32 and 33 (E4001111, E4001803).
ROW_TEXT_LENGTHS: MappingProxyType[str, MappingProxyType[str, int]] = MappingProxyType(
	{
		"shareholders": MappingProxyType(
			{"shareholder_name": 999, "street": 999, "postal_code_and_town": 999, "foreign_id": 999}
		),
		"establishments": MappingProxyType({"municipality": 999, "hebenummer": 28}),
	}
)


def elster_text(value: str | None, label: str, length: int) -> str | None:
	"""A text as the forms take it: in the character set of ELSTER, on one line, at most ``length`` characters.

	The typographic characters that ``transliterate`` replaces count as their replacements, and ``label`` names the
	field in the message. None and blanks give None.
	"""
	if value is None:
		return None
	try:
		text = " ".join(transliterate(value).split())
	except CharsetError as error:
		described = ", ".join(describe(character) for character in error.characters)
		raise SettingsError(TEXT_CHARACTERS, label, described) from None
	if len(text) > length:
		raise SettingsError(TEXT_TOO_LONG, label, len(text), length)
	return text or None


# Address

NOT_A_HOUSE_NUMBER = (
	"{0} is not a house number: digits only, at most four. Letters and ranges go into the suffix."
)
HOUSE_NUMBER_WITHOUT_STREET = "A house number needs its street."
SUFFIX_WITHOUT_HOUSE_NUMBER = "A house number suffix needs its house number."
NOT_A_POSTAL_CODE = "{0} is not a German postal code: five digits, not beginning with 00."
STREET_LINE_TOO_LONG = (
	"Street, house number and suffix make {0} characters; the Vorsatz of an Erklärung takes at most {1}."
)

GERMANY = "Germany"
HOUSE_NUMBER = re.compile("[0-9]{1,4}")
GERMAN_POSTAL_CODE = re.compile("0[1-9][0-9]{3}|[1-9][0-9]{4}")
# The street takes as much as it can, so that the house number is the last group of up to four digits after a blank;
# what follows it, beginning with no digit, is the suffix.
_LAST_HOUSE_NUMBER = re.compile(r"(?P<street>.*\S) (?P<number>[0-9]{1,4})(?P<suffix>(?:[^0-9].*)?)")


@dataclass(frozen=True, slots=True)
class StreetSplit:
	"""A street with its house number in digits and the suffix apart, as the Erklärungen take them."""

	street: str
	house_number: str | None = None
	house_number_suffix: str | None = None


def split_street(text: str | None) -> StreetSplit | None:
	"""Split a street with its house number, such as „Musterstraße 12a“, at its last digits after a blank.

	A street without such digits stays whole, and None or blanks give None. The result is a proposal: an
	address such as „Hauptstraße 5 / 2. OG“ splits at the 2, so the user checks it before it is stored.
	"""
	street = " ".join((text or "").split())
	if not street:
		return None
	match = _LAST_HOUSE_NUMBER.fullmatch(street)
	if match is None:
		return StreetSplit(street)
	return StreetSplit(match["street"].rstrip(" ,"), match["number"], match["suffix"].strip() or None)


def german_postal_code(value: str) -> str:
	if not GERMAN_POSTAL_CODE.fullmatch(value):
		raise SettingsError(NOT_A_POSTAL_CODE, value)
	return value


@dataclass(frozen=True, slots=True)
class Address:
	"""The address of the company as the Erklärungen, the E-Bilanz and the Jahresabschluss write it."""

	street: str | None = None
	house_number: str | None = None
	house_number_suffix: str | None = None
	supplement: str | None = None
	postal_code: str | None = None
	city: str | None = None
	country: str = GERMANY

	def __post_init__(self) -> None:
		if self.house_number is not None and not HOUSE_NUMBER.fullmatch(self.house_number):
			raise SettingsError(NOT_A_HOUSE_NUMBER, self.house_number)
		if self.house_number and not self.street:
			raise SettingsError(HOUSE_NUMBER_WITHOUT_STREET)
		if self.house_number_suffix and not self.house_number:
			raise SettingsError(SUFFIX_WITHOUT_HOUSE_NUMBER)
		if self.postal_code is not None and self.in_germany:
			german_postal_code(self.postal_code)
		line = self.street_line
		if line is not None and len(line) > STREET_LINE_LENGTH:
			raise SettingsError(STREET_LINE_TOO_LONG, len(line), STREET_LINE_LENGTH)

	@property
	def in_germany(self) -> bool:
		return self.country == GERMANY

	@property
	def street_line(self) -> str | None:
		"""Street, house number and suffix on one line, as the Absender of the Vorsatz names them."""
		if not self.street:
			return None
		number = (self.house_number or "") + (self.house_number_suffix or "")
		return f"{self.street} {number}" if number else self.street


# Periods


@dataclass(frozen=True, slots=True)
class Period:
	"""The days from ``first`` through ``last``; without a last day the period lasts."""

	first: date
	last: date | None = None

	def covers(self, day: date) -> bool:
		return self.first <= day and (self.last is None or day <= self.last)

	def overlaps(self, other: Period) -> bool:
		return (other.last is None or self.first <= other.last) and (
			self.last is None or other.first <= self.last
		)


def _period(first: date, last: date | None, template: str, row: int) -> Period:
	"""The period of a row, refused with ``template`` when it ends before it starts."""
	if last is not None and last < first:
		raise SettingsError(template, row, day_label(last), day_label(first))
	return Period(first, last)


# Years

NOT_A_YEAR = "{0} is not a four-digit year."
YEAR_TWICE = "The year {0} is entered twice."
EARLY_REQUEST_WITHOUT_ADVISOR = (
	"The Finanzamt can ask for the {0} of {1} early only when a Steuerberatung prepares it (§ 149 Abs. 4 AO)."
)
EARLY_REQUEST_OUTSIDE = "The Finanzamt can ask for the {0} of {1} for a day from {2} on and before {3} (§ 149 Abs. 4 AO), not for {4}."
EARLY_REQUEST_KLEINUNTERNEHMER = (
	"A Kleinunternehmer files no Umsatzsteuererklärung for {0} (§ 19 Abs. 1 Satz 2 UStG), so the Finanzamt "
	"cannot ask for it early."
)
EXEMPTION_WITHOUT_REASON = "The exemption of {0} under § 264 Abs. 3 HGB needs its reason."

UMSATZSTEUERERKLAERUNG = "Umsatzsteuererklärung"
KOERPERSCHAFTSTEUERERKLAERUNG = "Körperschaftsteuererklärung"
GEWERBESTEUERERKLAERUNG = "Gewerbesteuererklärung"


def early_request_window(year: int) -> tuple[date, date]:
	"""The days § 149 Abs. 4 AO lets the Finanzamt set for an Erklärung of ``year``: from the deadline of Absatz 2,
	seven months after the year, up to the last day of February of the second year after it, which is not one."""
	_require_year(year)
	return date(year + 1, 7, 31), date(year + 2, 3, 1) - timedelta(days=1)


@dataclass(frozen=True, slots=True)
class YearSettings:
	"""What the settings say of one year: the VZ, the EZ or the year the fiscal year ends in.

	The early requests are the days the Finanzamt set under § 149 Abs. 4 AO; ``adopted_on`` is the day the
	shareholders adopted the Jahresabschluss of the fiscal year (§ 42a Abs. 2 GmbHG).
	"""

	year: int
	advisor_prepares: bool = False
	kleinunternehmer: bool = False
	early_request_ust: date | None = None
	early_request_kst: date | None = None
	early_request_gewst: date | None = None
	adopted_on: date | None = None
	exempt_264_3: bool = False
	exempt_264_3_reason: str | None = None

	def __post_init__(self) -> None:
		_require_year(self.year)
		if self.early_request_ust and self.kleinunternehmer:
			raise SettingsError(EARLY_REQUEST_KLEINUNTERNEHMER, self.year)
		first, last = early_request_window(self.year)
		for erklaerung, requested in self.early_requests.items():
			if requested is None:
				continue
			if not self.advisor_prepares:
				raise SettingsError(EARLY_REQUEST_WITHOUT_ADVISOR, erklaerung, self.year)
			if not first <= requested < last:
				raise SettingsError(
					EARLY_REQUEST_OUTSIDE,
					erklaerung,
					self.year,
					day_label(first),
					day_label(last),
					day_label(requested),
				)
		if self.exempt_264_3 and not (self.exempt_264_3_reason or "").strip():
			raise SettingsError(EXEMPTION_WITHOUT_REASON, self.year)

	@property
	def early_requests(self) -> dict[str, date | None]:
		return {
			UMSATZSTEUERERKLAERUNG: self.early_request_ust,
			KOERPERSCHAFTSTEUERERKLAERUNG: self.early_request_kst,
			GEWERBESTEUERERKLAERUNG: self.early_request_gewst,
		}


def check_years(years: Iterable[YearSettings]) -> None:
	duplicate = _first_duplicate(year.year for year in years)
	if duplicate is not None:
		raise SettingsError(YEAR_TWICE, duplicate)


def year_settings(years: Iterable[YearSettings], year: int) -> YearSettings | None:
	return next((settings for settings in years if settings.year == year), None)


# Shareholders

NOT_A_SHAREHOLDER_KIND = (
	"{0} is not a kind of shareholder: Natural Person, Corporation or Business Partnership."
)
SHAREHOLDER_ENDS_BEFORE_START = "Row {0} of the shareholders ends on {1}, before its start on {2}."
NOT_A_SHARE = (
	"Row {0} of the shareholders: the share in percent lies above 0 and at most at 100, with at most four "
	"decimals, not {1}."
)
NOT_A_NOMINAL_AMOUNT = (
	"Row {0} of the shareholders: the nominal amount is the sum of Geschäftsanteile, in full euros above 0 (§ 5 "
	"Abs. 2 GmbHG), not {1}."
)
IDNR_OF_A_NATURAL_PERSON = (
	"Row {0} of the shareholders: only a natural person has an Identifikationsnummer (§ 139b Abs. 1 AO)."
)
NOT_AN_IDNR = "Row {0} of the shareholders: an Identifikationsnummer has eleven digits."
NOT_A_WID_NR = (
	"Row {0} of the shareholders: a Wirtschafts-Identifikationsnummer is DE and nine digits, without the "
	"five-digit suffix."
)
NOT_A_STATE = "{0} is not a Bundesland."
NOT_A_STEUERNUMMER = "Row {0} of the shareholders: the Steuernummer does not have the format {1} of {2}."
NOT_AN_ELSTER_STEUERNUMMER = (
	"Row {0} of the shareholders: without its Bundesland the Steuernummer is the 13-digit form for ELSTER."
)
SHAREHOLDER_TWICE = "Rows {0} and {1} of the shareholders name {2} for the same days."
SHARES_NOT_COMPLETE = "On {0} the shares of the shareholders add up to {1} %; ELSTER takes 99 to 100 % (rule 8931029 of the KSt 1)."

SHARE_TOTAL_RANGE = (Decimal(99), HUNDRED)
SHARE_PLACES = Decimal("0.0001")
IDNR = re.compile("[0-9]{11}")
WID_NR = re.compile("DE[0-9]{9}")
ELSTER_STEUERNUMMER = re.compile("[0-9]{4}0[0-9]{8}")


class ShareholderKind(StrEnum):
	NATURAL_PERSON = "Natural Person"
	CORPORATION = "Corporation"
	PARTNERSHIP = "Business Partnership"


def normalized_idnr(value: str | None, row: int) -> str | None:
	"""The Identifikationsnummer of a shareholder without blanks, or None."""
	compact = "".join((value or "").split())
	if not compact:
		return None
	if not IDNR.fullmatch(compact):
		raise SettingsError(NOT_AN_IDNR, row)
	return compact


def normalized_wid_nr(value: str | None, row: int) -> str | None:
	"""The Wirtschafts-Identifikationsnummer of a shareholder without blanks and in capitals, or None."""
	compact = "".join((value or "").split()).upper()
	if not compact:
		return None
	if not WID_NR.fullmatch(compact):
		raise SettingsError(NOT_A_WID_NR, row)
	return compact


def elster_tax_number(value: str | None, state: str | None, row: int) -> str | None:
	"""The 13-digit Steuernummer of a shareholder for ELSTER: from the number as the Finanzamt of ``state`` issued
	it, or, without a state, the 13-digit form itself. None without a number."""
	number = (value or "").strip()
	if not number:
		return None
	if state:
		code = STATE_CODES.get(state)
		if code is None:
			raise SettingsError(NOT_A_STATE, state)
		try:
			return to_elster(code, number)
		except SteuernummerError:
			raise SettingsError(NOT_A_STEUERNUMMER, row, SCHEMES[code].standard, state) from None
	compact = "".join(number.split())
	if not ELSTER_STEUERNUMMER.fullmatch(compact):
		raise SettingsError(NOT_AN_ELSTER_STEUERNUMMER, row)
	return compact


@dataclass(frozen=True, slots=True)
class Shareholder:
	"""A shareholder for one holding period, as KSt 1 lines 21 to 23b name it.

	``tax_number`` is the 13-digit form for ELSTER. ``tax_number``, ``idnr``, ``wid_nr`` and ``foreign_id`` are
	for the KSt 1 only (§ 139b Abs. 2 AO) and stay out of messages and logs.
	"""

	row: int
	name: str
	kind: ShareholderKind
	nominal_amount: Decimal
	percent: Decimal
	from_date: date
	to_date: date | None = None
	tax_number: str | None = None
	idnr: str | None = None
	wid_nr: str | None = None
	foreign_id: str | None = None
	street: str | None = None
	postal_code_and_town: str | None = None

	def __post_init__(self) -> None:
		object.__setattr__(self, "kind", _member(ShareholderKind, self.kind, NOT_A_SHAREHOLDER_KIND))
		percent = require_decimal(self.percent)
		if (
			not percent.is_finite()
			or not ZERO < percent <= HUNDRED
			or percent != percent.quantize(SHARE_PLACES)
		):
			raise SettingsError(NOT_A_SHARE, self.row, _number(percent))
		amount = require_decimal(self.nominal_amount)
		if not amount.is_finite() or amount <= ZERO or amount != amount.quantize(EURO):
			raise SettingsError(NOT_A_NOMINAL_AMOUNT, self.row, _number(amount))
		if self.idnr and self.kind is not ShareholderKind.NATURAL_PERSON:
			raise SettingsError(IDNR_OF_A_NATURAL_PERSON, self.row)
		_period(self.from_date, self.to_date, SHAREHOLDER_ENDS_BEFORE_START, self.row)

	@property
	def period(self) -> Period:
		return Period(self.from_date, self.to_date)


def share_total(shareholders: Iterable[Shareholder], day: date) -> Decimal:
	"""The shares in percent the shareholders hold on a day."""
	return sum((shareholder.percent for shareholder in shareholders if shareholder.period.covers(day)), ZERO)


def shareholders_on(shareholders: Iterable[Shareholder], day: date) -> list[Shareholder]:
	return [shareholder for shareholder in shareholders if shareholder.period.covers(day)]


def check_shareholders(shareholders: Sequence[Shareholder]) -> None:
	"""A shareholder holds one share at a time, and on every day someone holds shares they add up to 99 to 100 %.

	The total changes only on the first day of a row and on the day after its last, so those days are checked.
	"""
	twice = _first_overlap(shareholders, lambda shareholder: _person(shareholder.name))
	if twice is not None:
		first, second = twice
		raise SettingsError(SHAREHOLDER_TWICE, first.row, second.row, first.name)
	low, high = SHARE_TOTAL_RANGE
	for day in _change_days(shareholder.period for shareholder in shareholders):
		if shareholders_on(shareholders, day):
			total = share_total(shareholders, day)
			if not low <= total <= high:
				raise SettingsError(SHARES_NOT_COMPLETE, day_label(day), _number(total))


# Managing directors

DIRECTOR_ENDS_BEFORE_START = "Row {0} of the managing directors ends on {1}, before its start on {2}."
DIRECTOR_TWICE = "Rows {0} and {1} of the managing directors name {2} for the same days."


@dataclass(frozen=True, slots=True)
class Director:
	"""A Geschäftsführer for the days of the office."""

	row: int
	name: str
	from_date: date
	to_date: date | None = None
	role: str | None = None
	is_shareholder: bool = False
	signs: bool = True

	def __post_init__(self) -> None:
		_period(self.from_date, self.to_date, DIRECTOR_ENDS_BEFORE_START, self.row)

	@property
	def period(self) -> Period:
		return Period(self.from_date, self.to_date)


def directors_on(directors: Iterable[Director], day: date) -> list[Director]:
	return [director for director in directors if director.period.covers(day)]


def check_directors(directors: Sequence[Director]) -> None:
	twice = _first_overlap(directors, lambda director: _person(director.name))
	if twice is not None:
		first, second = twice
		raise SettingsError(DIRECTOR_TWICE, first.row, second.row, first.name)


# Gewerbesteuer

NOT_AN_AGS = "{0} is not an Amtlicher Gemeindeschlüssel: the Länderschlüssel 01 to 16 and six more digits."
ESTABLISHMENT_ENDS_BEFORE_START = "Row {0} of the Betriebsstätten ends on {1}, before its start on {2}."
ESTABLISHMENT_TWICE = (
	"Rows {0} and {1} of the Betriebsstätten name the same Betriebsstätte in {2} for the same days."
)
HEBESATZ_BELOW_MINIMUM = (
	"The Hebesatz of {0} for {1} is {2} %; § 16 Abs. 4 Satz 2 GewStG sets at least {3} % for that year."
)
HEBESATZ_WITHOUT_SOURCE = (
	"The Hebesatz of {0} for {1} needs its source, such as the Haushaltssatzung of the Gemeinde."
)
HEBESATZ_TWICE = "The Hebesatz of {0} for {1} is entered twice."

AGS = re.compile("(0[1-9]|1[0-6])[0-9]{6}")
MINIMUM_HEBESATZ = Decimal(200)
MINIMUM_HEBESATZ_FROM_2027 = Decimal(280)


def normalized_ags(value: str | None) -> str:
	"""The Amtlicher Gemeindeschlüssel of eight digits, without blanks."""
	compact = "".join((value or "").split())
	if not AGS.fullmatch(compact):
		raise SettingsError(NOT_AN_AGS, value)
	return compact


def minimum_hebesatz(year: int) -> Decimal:
	"""The Hebesatz in percent that § 16 Abs. 4 Satz 2 GewStG sets when the Gemeinde sets no higher one."""
	_require_year(year)
	return MINIMUM_HEBESATZ_FROM_2027 if year >= 2027 else MINIMUM_HEBESATZ


@dataclass(frozen=True, slots=True)
class Establishment:
	"""A Betriebsstätte of the company in a Gemeinde for the days it existed."""

	row: int
	municipality: str
	postal_code: str
	ags: str
	from_date: date
	to_date: date | None = None
	hebenummer: str | None = None

	def __post_init__(self) -> None:
		object.__setattr__(self, "ags", normalized_ags(self.ags))
		german_postal_code(self.postal_code)
		_period(self.from_date, self.to_date, ESTABLISHMENT_ENDS_BEFORE_START, self.row)

	@property
	def period(self) -> Period:
		return Period(self.from_date, self.to_date)


def establishments_in(
	establishments: Iterable[Establishment], first: date, last: date
) -> list[Establishment]:
	"""The Betriebsstätten that existed on a day of the period, such as an Erhebungszeitraum."""
	period = Period(first, last)
	return [establishment for establishment in establishments if establishment.period.overlaps(period)]


def check_establishments(establishments: Sequence[Establishment]) -> None:
	twice = _first_overlap(
		establishments,
		lambda establishment: (
			establishment.ags,
			establishment.postal_code,
			_person(establishment.municipality),
		),
	)
	if twice is not None:
		first, second = twice
		raise SettingsError(ESTABLISHMENT_TWICE, first.row, second.row, first.municipality)


@dataclass(frozen=True, slots=True)
class TradeTaxRate:
	"""The Hebesatz in percent of a Gemeinde for one Erhebungszeitraum, with where it is set."""

	ags: str
	year: int
	hebesatz: Decimal
	source: str
	source_date: date | None = None

	def __post_init__(self) -> None:
		object.__setattr__(self, "ags", normalized_ags(self.ags))
		minimum = minimum_hebesatz(self.year)
		hebesatz = require_decimal(self.hebesatz)
		if not hebesatz.is_finite() or hebesatz < minimum:
			raise SettingsError(
				HEBESATZ_BELOW_MINIMUM, self.ags, self.year, _number(hebesatz), _number(minimum)
			)
		if not (self.source or "").strip():
			raise SettingsError(HEBESATZ_WITHOUT_SOURCE, self.ags, self.year)


def check_trade_tax_rates(rates: Iterable[TradeTaxRate]) -> None:
	duplicate = _first_duplicate((rate.ags, rate.year) for rate in rates)
	if duplicate is not None:
		raise SettingsError(HEBESATZ_TWICE, *duplicate)


def hebesatz_of(rates: Iterable[TradeTaxRate], ags: str, year: int) -> TradeTaxRate | None:
	return next((rate for rate in rates if rate.ags == ags and rate.year == year), None)


# Holdings

NOT_A_HOLDING_SHARE = "The holding in {0}: a share in percent lies from 0 to 100, not {1}."
HOLDING_SOLD_BEFORE_BOUGHT = "The holding in {0} is sold on {1}, before it was bought on {2}."
HOLDING_TWICE = "The holding in {0} for {1} is entered twice."


@dataclass(frozen=True, slots=True)
class Holding:
	"""A holding of the company in another company for one year, with the shares that § 8b Abs. 4 KStG and § 9
	Nr. 2a and 7 GewStG read."""

	name: str
	year: int
	percent_on_1_january: Decimal | None = None
	percent_at_start_of_ez: Decimal | None = None
	bought_on: date | None = None
	sold_on: date | None = None
	identifier: str | None = None
	country: str | None = None

	def __post_init__(self) -> None:
		_require_year(self.year)
		for percent in (self.percent_on_1_january, self.percent_at_start_of_ez):
			if percent is not None and (
				not require_decimal(percent).is_finite() or not ZERO <= percent <= HUNDRED
			):
				raise SettingsError(NOT_A_HOLDING_SHARE, self.name, _number(percent))
		if self.bought_on and self.sold_on and self.sold_on < self.bought_on:
			raise SettingsError(
				HOLDING_SOLD_BEFORE_BOUGHT, self.name, day_label(self.sold_on), day_label(self.bought_on)
			)


def check_holdings(holdings: Iterable[Holding]) -> None:
	seen = set()
	for holding in holdings:
		key = (_person(holding.name), holding.year)
		if key in seen:
			raise SettingsError(HOLDING_TWICE, holding.name, holding.year)
		seen.add(key)


def holdings_of(holdings: Iterable[Holding], year: int) -> list[Holding]:
	return [holding for holding in holdings if holding.year == year]


# Vorauszahlungen

NOT_A_TAX = "{0} is not a tax of the Vorauszahlungen: KSt, SolZ or GewSt."
PREPAYMENT_NOT_IN_CENTS = (
	"The Vorauszahlung {0} of {1} due on {2} is an amount in cents of at least 0, not {3}."
)
AGS_ONLY_FOR_GEWERBESTEUER = (
	"The Vorauszahlung {0} of {1} due on {2} goes to the Finanzamt, not to a Gemeinde: leave its Amtlicher "
	"Gemeindeschlüssel empty."
)
PREPAYMENT_TWICE = "The Vorauszahlung {0} of {1} due on {2} is entered twice."


class Tax(StrEnum):
	KST = "KSt"
	SOLZ = "SolZ"
	GEWST = "GewSt"


@dataclass(frozen=True, slots=True)
class Prepayment:
	"""A Vorauszahlung as a notice sets it."""

	tax: Tax
	year: int
	due_date: date
	amount: Decimal
	notice_date: date | None = None
	ags: str | None = None

	def __post_init__(self) -> None:
		object.__setattr__(self, "tax", _member(Tax, self.tax, NOT_A_TAX))
		_require_year(self.year)
		if not _in_cents(self.amount):
			raise SettingsError(
				PREPAYMENT_NOT_IN_CENTS, self.tax, self.year, day_label(self.due_date), _number(self.amount)
			)
		if self.ags:
			if self.tax is not Tax.GEWST:
				raise SettingsError(AGS_ONLY_FOR_GEWERBESTEUER, self.tax, self.year, day_label(self.due_date))
			object.__setattr__(self, "ags", normalized_ags(self.ags))


def check_prepayments(prepayments: Iterable[Prepayment]) -> None:
	duplicate = _first_duplicate(
		(prepayment.tax, prepayment.year, prepayment.due_date) for prepayment in prepayments
	)
	if duplicate is not None:
		tax, year, due_date = duplicate
		raise SettingsError(PREPAYMENT_TWICE, tax, year, day_label(due_date))


def prepayments_of(prepayments: Iterable[Prepayment], tax: Tax, year: int) -> list[Prepayment]:
	return [prepayment for prepayment in prepayments if prepayment.tax is tax and prepayment.year == year]


# Carry-forwards

NOT_A_CARRY_FORWARD = "{0} is not a kind of carry-forward."
CARRY_FORWARD_NOT_IN_CENTS = "{0} as of {1} is an amount in cents of at least 0, not {2}."
CARRY_FORWARD_TWICE = "{0} as of {1} is entered twice."


class CarryForwardKind(StrEnum):
	LOSS = "Loss Carried Forward (§ 10d EStG)"
	TERMINGESCHAEFTE = "Loss from Termingeschäfte (§ 15 Abs. 4 EStG)"
	DONATIONS_KST = "Donations Carried Forward (KSt)"
	FEHLBETRAG = "Fehlbetrag (§ 10a GewStG)"
	DONATIONS_GEWST = "Donations Carried Forward (GewSt)"
	EINLAGEKONTO = "Einlagekonto (§ 27 KStG)"
	SONDERAUSWEIS = "Sonderausweis (§ 28 KStG)"


@dataclass(frozen=True, slots=True)
class CarryForward:
	"""An amount the Finanzamt stated as of a day, and whether someone checked it against the notice."""

	kind: CarryForwardKind
	as_of: date
	amount: Decimal
	notice_date: date | None = None
	confirmed: bool = False

	def __post_init__(self) -> None:
		object.__setattr__(self, "kind", _member(CarryForwardKind, self.kind, NOT_A_CARRY_FORWARD))
		if not _in_cents(self.amount):
			raise SettingsError(
				CARRY_FORWARD_NOT_IN_CENTS, self.kind, day_label(self.as_of), _number(self.amount)
			)


def check_carry_forwards(carry_forwards: Iterable[CarryForward]) -> None:
	duplicate = _first_duplicate(
		(carry_forward.kind, carry_forward.as_of) for carry_forward in carry_forwards
	)
	if duplicate is not None:
		kind, as_of = duplicate
		raise SettingsError(CARRY_FORWARD_TWICE, kind, day_label(as_of))


def latest_carry_forward(
	carry_forwards: Iterable[CarryForward], kind: CarryForwardKind, day: date
) -> CarryForward | None:
	"""The latest amount of a kind stated as of ``day`` or before."""
	stated = [
		carry_forward
		for carry_forward in carry_forwards
		if carry_forward.kind is kind and carry_forward.as_of <= day
	]
	return max(stated, key=lambda carry_forward: carry_forward.as_of, default=None)


# Size

NOT_A_SIZE_CLASS = "{0} is not a size class: Kleinst, Klein, Mittelgroß or Groß."
SIZE_CRITERION_NEGATIVE = "The size of the fiscal year ending on {0}: the {1} cannot be negative."
SIZE_WITHOUT_SOURCE = "The size of the fiscal year ending on {0} needs its source."
SIZE_TWICE = "The size of the fiscal year ending on {0} is entered twice."

BALANCE_SHEET_TOTAL = "Bilanzsumme"
REVENUE = "Umsatzerlöse"
EMPLOYEES = "Arbeitnehmer"


class SizeClass(StrEnum):
	KLEINST = "Kleinst"
	KLEIN = "Klein"
	MITTELGROSS = "Mittelgroß"
	GROSS = "Groß"


@dataclass(frozen=True, slots=True)
class SizeRecord:
	"""The criteria of § 267 and § 267a HGB on one Abschlussstichtag and the size class applied for that year."""

	fiscal_year_end: date
	size_class: SizeClass
	source: str
	balance_sheet_total: Decimal | None = None
	revenue: Decimal | None = None
	employees: Decimal | None = None
	reason: str | None = None

	def __post_init__(self) -> None:
		object.__setattr__(self, "size_class", _member(SizeClass, self.size_class, NOT_A_SIZE_CLASS))
		for criterion, value in (
			(BALANCE_SHEET_TOTAL, self.balance_sheet_total),
			(REVENUE, self.revenue),
			(EMPLOYEES, self.employees),
		):
			if value is not None and (not require_decimal(value).is_finite() or value < ZERO):
				raise SettingsError(SIZE_CRITERION_NEGATIVE, day_label(self.fiscal_year_end), criterion)
		if not (self.source or "").strip():
			raise SettingsError(SIZE_WITHOUT_SOURCE, day_label(self.fiscal_year_end))


def check_size_history(history: Iterable[SizeRecord]) -> None:
	duplicate = _first_duplicate(record.fiscal_year_end for record in history)
	if duplicate is not None:
		raise SettingsError(SIZE_TWICE, day_label(duplicate))


def size_class_on(history: Iterable[SizeRecord], fiscal_year_end: date) -> SizeClass | None:
	"""The size class the settings applied to the fiscal year ending on that day, if they hold it."""
	return next((record.size_class for record in history if record.fiscal_year_end == fiscal_year_end), None)


# Employment Types

EMPLOYMENT_TYPE_TWICE = "The Employment Type {0} is listed twice."


def check_employment_types(names: Iterable[str]) -> None:
	duplicate = _first_duplicate(names)
	if duplicate is not None:
		raise SettingsError(EMPLOYMENT_TYPE_TWICE, duplicate)


MESSAGES = (
	NOT_A_LEGAL_FORM,
	TEXT_TOO_LONG,
	TEXT_CHARACTERS,
	NOT_A_HOUSE_NUMBER,
	HOUSE_NUMBER_WITHOUT_STREET,
	SUFFIX_WITHOUT_HOUSE_NUMBER,
	NOT_A_POSTAL_CODE,
	STREET_LINE_TOO_LONG,
	NOT_A_YEAR,
	YEAR_TWICE,
	EARLY_REQUEST_WITHOUT_ADVISOR,
	EARLY_REQUEST_OUTSIDE,
	EARLY_REQUEST_KLEINUNTERNEHMER,
	EXEMPTION_WITHOUT_REASON,
	NOT_A_SHAREHOLDER_KIND,
	SHAREHOLDER_ENDS_BEFORE_START,
	NOT_A_SHARE,
	NOT_A_NOMINAL_AMOUNT,
	IDNR_OF_A_NATURAL_PERSON,
	NOT_AN_IDNR,
	NOT_A_WID_NR,
	NOT_A_STATE,
	NOT_A_STEUERNUMMER,
	NOT_AN_ELSTER_STEUERNUMMER,
	SHAREHOLDER_TWICE,
	SHARES_NOT_COMPLETE,
	DIRECTOR_ENDS_BEFORE_START,
	DIRECTOR_TWICE,
	NOT_AN_AGS,
	ESTABLISHMENT_ENDS_BEFORE_START,
	ESTABLISHMENT_TWICE,
	HEBESATZ_BELOW_MINIMUM,
	HEBESATZ_WITHOUT_SOURCE,
	HEBESATZ_TWICE,
	NOT_A_HOLDING_SHARE,
	HOLDING_SOLD_BEFORE_BOUGHT,
	HOLDING_TWICE,
	NOT_A_TAX,
	PREPAYMENT_NOT_IN_CENTS,
	AGS_ONLY_FOR_GEWERBESTEUER,
	PREPAYMENT_TWICE,
	NOT_A_CARRY_FORWARD,
	CARRY_FORWARD_NOT_IN_CENTS,
	CARRY_FORWARD_TWICE,
	NOT_A_SIZE_CLASS,
	SIZE_CRITERION_NEGATIVE,
	SIZE_WITHOUT_SOURCE,
	SIZE_TWICE,
	EMPLOYMENT_TYPE_TWICE,
)


def _member[E: StrEnum](enum: type[E], value: object, template: str) -> E:
	try:
		return enum(value)
	except ValueError:
		raise SettingsError(template, value) from None


def _number(value: Decimal) -> str:
	"""A number as a message shows it, without trailing zeros: 400 for 400.0, 33.3333 for 33.33330."""
	return f"{value.normalize():f}"


def _in_cents(amount: object) -> bool:
	value = require_decimal(amount)
	return value.is_finite() and value >= ZERO and value == value.quantize(CENT)


def _require_year(year: object) -> None:
	if not _is_int(year) or not 1000 <= year <= 9999:
		raise SettingsError(NOT_A_YEAR, year)


def _is_int(value: object) -> bool:
	"""True is an int to Python, but no year."""
	return isinstance(value, int) and not isinstance(value, bool)


def _person(name: str) -> str:
	"""A name as the same person or place, whatever its case and blanks."""
	return " ".join(name.split()).casefold()


def _change_days(periods: Iterable[Period]) -> list[date]:
	"""The days on which who holds what can change: the first day of each period and the day after its last."""
	days = set()
	for period in periods:
		days.add(period.first)
		if period.last is not None:
			days.add(period.last + timedelta(days=1))
	return sorted(days)


class _Lasting(Protocol):
	@property
	def period(self) -> Period: ...


def _first_overlap[T: _Lasting](rows: Sequence[T], key: Callable[[T], Hashable]) -> tuple[T, T] | None:
	"""The first two rows with the same key whose periods share a day."""
	for index, row in enumerate(rows):
		for other in rows[index + 1 :]:
			if key(row) == key(other) and row.period.overlaps(other.period):
				return row, other
	return None


def _first_duplicate[T](keys: Iterable[T]) -> T | None:
	seen: set[T] = set()
	for key in keys:
		if key in seen:
			return key
		seen.add(key)
	return None
