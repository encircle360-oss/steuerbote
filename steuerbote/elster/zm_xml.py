"""The Zusammenfassende Meldung as ELSTER XML for ERiC: the Nutzdaten of the Datenart ZMDO.

Sources are the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/), cited as HB for
ERiC-Entwicklerhandbuch.pdf, JD for Datenarten/ElsterExtern/ZMDO/Jahresdokumentation/Jahresdokumentation_ZMDO_2.ods
with its rules by Fehlercode, and XSD for Datenarten/ElsterExtern/ZMDO/Schema/5/zm_000005.xsd, which
elster11_Zm_000005_extern.xsd includes into the namespace of ElsterXML 11. Beispiele/ZMDO_5_send-Auth.xml shows
the whole delivery.

ZMDO is the Datenart of the Verfahren ElsterExtern for the ZM (HB Kap. 8.15, Tabelle 8-28). Its Nutzdaten are
the element zm in the namespace http://www.elster.de/elsterxml/schema/v11 (JD, sheet „XML-Schema Namensräume“)
with the version 000005, „Konstanter Wert“ (XSD). ERiC takes them as the Nutzdaten of a DatenTeil, in UTF-8
without a byte order mark (HB 5.3.2). Unlike the Voranmeldung with its Kz 09 they carry no Hersteller-ID: only
the TransferHeader names it, which EricCreateTH writes. Mein ELSTER imports no XML for the ZM; its form takes
the CSV file of steuerbote.zm.csv_file.

What the transmission needs besides the Nutzdaten, the Verfahren ElsterExtern, the Datenart ZMDO, the Vorgang
send-Auth, the datenartVersion ZMDO with the plugin checkZMDO and the recipient BF of the NutzdatenHeader, describes
steuerbote.eric.datenart.ZMDO, the one place for the parameters of every Datenart.

The rules:

- unternehmer: the filer's German USt-IdNr. in knri, DE and nine digits (XSD knri_Type; 170015001, 170015002);
  the Teilnehmernummer zulassNr with zulnr1 N, „Für ERiC ist hier der konstante Wert „N“ zu verwenden“ (JD;
  170015022), and zulnr2 1111111, since „das BZSt keine neuen Teilnehmernummern vergibt“, or the company's own
  Teilnehmernummer of seven or eight digits from 0300000 (JD; 170015024); the address with name, street, town
  and country (170025001 to 170025004), a German postal code of five digits from 01001 to 99999 (170025005,
  170025006) and a foreign one of letters, digits and blanks, a phone number of digits, blanks and ( ) / + -
  (XSD, JD), and the country from the list of the JD, but not GB (170045020).
- zm-zeilen: waehrung 1 for the euro, the only value the JD takes; meldeart 10 for an Erstmeldung and 11 for a
  Berichtigung; anzeige and widerruf, both always written (170015006, 170015009), as steuerbote.zm.rhythm
  check_notices() allows them (170015008, 170015012, 170015013); the Meldezeitraum in mzr with quart and jahr.
- zeile: at least one (170045002), at most 5,000 (JD, max. Zeilen), each USt-IdNr. and Art once (170045003 to
  170045005); the sum in whole euros with a minus sign where it is negative and at most 11 digits (XSD
  betrag_Type, JD Formatkennzeichen N). A Meldezeile holds only USt-IdNrn. the ZM takes (steuerbote.zm.ustid):
  none of Germany (170045014) or Great Britain (170045017), and XI only for L and D (170045021). XI counts from
  2021 on (170045022). The Applikationsbedingungen_ZMDO_2.pdf describe a formal check of XI numbers,
  „validiereNordirischeUstidAppBed“, without its format, and the JD uses none of them („Verwendete
  Applikationsbedingungen: keine“), so an XI number gets no check of its structure here, like any other number.
- An Erstmeldung reports every line of the statement, a Berichtigung only what changes what the BZSt holds:
  „Korrekt gemeldete Angaben sind in der berichtigten ZM nicht zu wiederholen.“ (BZSt, „Berichtigung einer ZM“),
  a changed line with its new sum (Anleitung zur ZM, IV.12.2) and a line that is gone with 0 (IV.12), as
  steuerbote.zm.correction.correct() finds them. No line of the statement reports 0: „Nullmeldungen sind nicht
  abzugeben“ (170045001; Anleitung zur ZM, III.1).
- Against the day of the transmission, „Heute“ of the rules, which is the day the Nutzdaten are written: the
  Meldezeitraum has begun (170015020), a ZM for two months goes from the first day of the second month on
  (170015019), and ERiC takes ten years back (170015016).
- Texts use the character set Standard_E_V2 (JD, sheet „Allg. Information“), whose sheet „Zeichensatz“ lists the
  same characters as that of the Voranmeldung (charset.py), on one line and without blanks at either end (JD,
  sheet „Formale Fehler“).
"""

import re
from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from lxml import etree

from steuerbote.elster import ustva_xml
from steuerbote.elster.ustva_xml import TextField, XmlError, elster_text, required_text
from steuerbote.vatid import ustid as vat_ids
from steuerbote.zm.correction import correct
from steuerbote.zm.errors import ZmError
from steuerbote.zm.lines import Art, Meldezeile
from steuerbote.zm.period import Kind, ReportingPeriod
from steuerbote.zm.rhythm import check_notices

NAMESPACE = "http://www.elster.de/elsterxml/schema/v11"
VERSION = "000005"
EURO = "1"
ZULNR1 = "N"
ZULNR2 = "1111111"
TEILNEHMERNUMMER_MIN = 300000
MAX_LINES = 5000
AMOUNT_DIGITS = 11
NORTHERN_IRELAND = "XI"
NORTHERN_IRELAND_FROM = 2021
YEARS_BACK = 10
GERMANY = "DE"
UNITED_KINGDOM = "GB"

TEILNEHMERNUMMER = re.compile("[0-9]{7,8}")
GERMAN_POSTAL_CODE = re.compile("0100[1-9]|010[1-9][0-9]|01[1-9][0-9]{2}|0[2-9][0-9]{3}|[1-9][0-9]{4}")
POSTAL_CODE = re.compile("[A-Za-z0-9 ]+")
PHONE = re.compile(r"[0-9 +\-/()]+")

# ISO_3166_1_2stellig, version 6, the Benutzerdefinierte Typdefinition of the field staat (JD, sheets „ZMDO -
# Felder“ and „Benutzerdefinierte Typen“): the codes of ISO 3166-1 with XL for Melilla, XI for Northern Ireland
# and XU for the United Kingdom without Northern Ireland.
_COUNTRY_CODES = (
	"AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV "
	"BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES "
	"ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE "
	"IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KO KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV "
	"LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR "
	"NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL "
	"SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC "
	"VE VG VI VN VU WF WS XI XL XU YE YT ZA ZM ZW"
)
COUNTRIES = frozenset(_COUNTRY_CODES.split())

NOT_A_GERMAN_VAT_ID = "{0} is not a German USt-IdNr.: the Zusammenfassende Meldung takes DE and nine digits."
NOT_A_TEILNEHMERNUMMER = "{0} is not a Teilnehmernummer of the BZSt: seven or eight digits from 0300000 on."
NOT_A_GERMAN_POSTAL_CODE = "{0} is not a German postal code: ELSTER takes five digits from 01001 to 99999."
NOT_A_POSTAL_CODE = "The postal code {0} may hold letters without umlauts, digits and blanks only."
NOT_A_PHONE = "The phone number {0} may hold digits, blanks and the characters ( ) / + - only."
UNKNOWN_COUNTRY = "{0} is not a country code that ELSTER takes for the address."
UNITED_KINGDOM_ADDRESS = (
	"ELSTER no longer takes GB for the address: Northern Ireland is XI, the rest of the United Kingdom XU."
)
NO_LINES = "The Zusammenfassende Meldung for {0} reports no Meldezeile; Nullmeldungen are not filed."
NOTHING_TO_CORRECT = "The Berichtigung for {0} changes nothing that was filed."
TOO_MANY_LINES = "The Zusammenfassende Meldung has {0} Meldezeilen; ERiC takes at most {1}."
LINE_TWICE = "The Meldezeile {0} {1} appears twice; its amounts belong in one line."
ZERO_LINE = "The Meldezeile {0} {1} reports 0 euros; a Berichtigung writes the 0 for a filed line itself."
TOO_MANY_DIGITS = "The sum {2} of the Meldezeile {0} {1} has more than 11 digits."
NORTHERN_IRELAND_TOO_EARLY = (
	"The Meldezeile {0} {1}: ELSTER takes USt-IdNrn. of Northern Ireland from 2021 on, not in {2}."
)
NOT_BEGUN = "ERiC takes the Zusammenfassende Meldung for {0} once its Meldezeitraum has begun."
TWO_MONTHS_TOO_EARLY = (
	"ERiC takes the Zusammenfassende Meldung for {0} from the first day of its second month on."
)
TOO_OLD = "ERiC takes Zusammenfassende Meldungen for {1} and later years, not for {0}."
MESSAGES = (
	NOT_A_GERMAN_VAT_ID,
	NOT_A_TEILNEHMERNUMMER,
	NOT_A_GERMAN_POSTAL_CODE,
	NOT_A_POSTAL_CODE,
	NOT_A_PHONE,
	UNKNOWN_COUNTRY,
	UNITED_KINGDOM_ADDRESS,
	NO_LINES,
	NOTHING_TO_CORRECT,
	TOO_MANY_LINES,
	LINE_TWICE,
	ZERO_LINE,
	TOO_MANY_DIGITS,
	NORTHERN_IRELAND_TOO_EARLY,
	NOT_BEGUN,
	TWO_MONTHS_TOO_EARLY,
	TOO_OLD,
)
"""The templates of this module. The writer raises those of check_notices() in steuerbote.zm.rhythm, of a
Meldezeile that correct() cannot build (steuerbote.zm.lines) and of the texts in ustva_xml.MESSAGES as well."""

NAME_LABEL = "The name of the Unternehmer"
ADDRESS_SUFFIX_LABEL = "The address suffix of the Unternehmer"
STREET_LABEL = "The street of the Unternehmer"
HOUSE_NUMBER_LABEL = "The house number of the Unternehmer"
HOUSE_NUMBER_SUFFIX_LABEL = "The house number suffix of the Unternehmer"
POSTAL_CODE_LABEL = "The postal code of the Unternehmer"
TOWN_LABEL = "The town of the Unternehmer"
COUNTRY_LABEL = "The country of the Unternehmer"
PHONE_LABEL = "The phone number of the Unternehmer"
LABELS = (
	NAME_LABEL,
	ADDRESS_SUFFIX_LABEL,
	STREET_LABEL,
	HOUSE_NUMBER_LABEL,
	HOUSE_NUMBER_SUFFIX_LABEL,
	POSTAL_CODE_LABEL,
	TOWN_LABEL,
	COUNTRY_LABEL,
	PHONE_LABEL,
)

# The children of anschrift_Type in the order of the schema, by the field of Unternehmer that holds each, with
# its maximum length and whether the JD requires it (170025001 to 170025004); a German address also requires
# the postal code (170025005).
ANSCHRIFT: MappingProxyType[str, TextField] = MappingProxyType(
	{
		"name": TextField("name", NAME_LABEL, 100, required=True),
		"address_suffix": TextField("adresszusatz", ADDRESS_SUFFIX_LABEL, 40, required=False),
		"street": TextField("strasse", STREET_LABEL, 30, required=True),
		"house_number": TextField("hausnr", HOUSE_NUMBER_LABEL, 10, required=False),
		"house_number_suffix": TextField("hausnrzusatz", HOUSE_NUMBER_SUFFIX_LABEL, 10, required=False),
		"postal_code": TextField("plz", POSTAL_CODE_LABEL, 12, required=False),
		"city": TextField("ort", TOWN_LABEL, 30, required=True),
		"country": TextField("staat", COUNTRY_LABEL, 2, required=True),
		"phone": TextField("telefon", PHONE_LABEL, 20, required=False),
	}
)


class Meldeart(Enum):
	"""The attribute meldeart of zm-zeilen: 10 „Erstmeldung“, 11 „berichtigte Anmeldung“ (XSD meldeart_Type)."""

	ERSTMELDUNG = "10"
	BERICHTIGUNG = "11"


@dataclass(frozen=True, slots=True)
class Unternehmer:
	"""The company that files the ZM, the element unternehmer of the schema.

	``ust_idnr`` is its German USt-IdNr. in capitals without blanks; the other fields but ``teilnehmernummer`` are
	its address, ``country`` the code of the state it lies in. ``teilnehmernummer`` is the number the BZSt once
	assigned for the electronic ZM, if the company has one. Texts are kept as ELSTER takes them: transliterated,
	on one line and trimmed; one longer than the schema allows is refused.
	"""

	ust_idnr: str
	name: str
	street: str
	postal_code: str | None
	city: str
	house_number: str | None = None
	house_number_suffix: str | None = None
	address_suffix: str | None = None
	country: str = GERMANY
	phone: str | None = None
	teilnehmernummer: str | None = None

	def __post_init__(self) -> None:
		object.__setattr__(self, "ust_idnr", _german_vat_id(self.ust_idnr))
		for attribute, text_field in ANSCHRIFT.items():
			if attribute != "country":
				clean = required_text if text_field.required else elster_text
				value = clean(getattr(self, attribute), text_field.label, text_field.length)
				object.__setattr__(self, attribute, value)
		object.__setattr__(self, "country", _country(self.country))
		if self.country == GERMANY:
			if self.postal_code is None:
				raise XmlError(ustva_xml.TEXT_MISSING, label=POSTAL_CODE_LABEL)
			if not GERMAN_POSTAL_CODE.fullmatch(self.postal_code):
				raise XmlError(NOT_A_GERMAN_POSTAL_CODE, self.postal_code)
		elif self.postal_code is not None and not POSTAL_CODE.fullmatch(self.postal_code):
			raise XmlError(NOT_A_POSTAL_CODE, self.postal_code)
		if self.phone is not None and not PHONE.fullmatch(self.phone):
			raise XmlError(NOT_A_PHONE, self.phone)
		object.__setattr__(self, "teilnehmernummer", _teilnehmernummer(self.teilnehmernummer))


@dataclass(frozen=True, slots=True)
class Zm:
	"""One Zusammenfassende Meldung of ``period`` for ERiC.

	``lines`` are the Meldezeilen of the Meldezeitraum as they stand now, as steuerbote.zm.lines.Statement gives
	them. An Erstmeldung reports them all. A Berichtigung is a Zm with ``filed``, what the BZSt holds for the
	Meldezeitraum after the earlier filings (steuerbote.zm.correction.as_filed()); it reports only the lines that
	change that, a line that is gone with 0 and before the others. ``reported`` holds the lines the Nutzdaten
	write. ``anzeige`` and ``widerruf`` are the Anzeige of § 18a Absatz 1 UStG and its Widerruf.
	"""

	period: ReportingPeriod
	lines: tuple[Meldezeile, ...]
	filed: ReadOnlyMapping[tuple[str, Art], Decimal] | None = None
	anzeige: bool = False
	widerruf: bool = False
	reported: tuple[Meldezeile, ...] = field(init=False)

	def __post_init__(self) -> None:
		object.__setattr__(self, "lines", tuple(self.lines))
		if self.filed is not None:
			object.__setattr__(self, "filed", MappingProxyType(dict(self.filed)))
		for flag in (self.anzeige, self.widerruf):
			if not isinstance(flag, bool):
				raise TypeError(f"anzeige and widerruf are bools, not {type(flag).__name__}")
		_check_lines(self.lines)
		try:
			check_notices(self.period, self.anzeige, self.widerruf)
			reported = (
				self.lines if self.filed is None else correct(self.period, self.filed, self.lines).lines
			)
		except ZmError as error:
			raise XmlError(error.template, *error.values) from None
		if not reported:
			raise XmlError(NO_LINES if self.filed is None else NOTHING_TO_CORRECT, self.period.label)
		if len(reported) > MAX_LINES:
			raise XmlError(TOO_MANY_LINES, len(reported), MAX_LINES)
		for line in reported:
			if len(str(abs(int(line.amount)))) > AMOUNT_DIGITS:
				raise XmlError(TOO_MANY_DIGITS, line.vat_id, line.art.value, int(line.amount))
			if line.vat_id.startswith(NORTHERN_IRELAND) and self.period.year < NORTHERN_IRELAND_FROM:
				raise XmlError(NORTHERN_IRELAND_TOO_EARLY, line.vat_id, line.art.value, self.period.year)
		object.__setattr__(self, "reported", reported)

	@property
	def meldeart(self) -> Meldeart:
		return Meldeart.ERSTMELDUNG if self.filed is None else Meldeart.BERICHTIGUNG


def to_nutzdaten(filer: Unternehmer, zm: Zm, created: date) -> str:
	"""The Nutzdaten for ERiC, as text without an XML declaration.

	``created`` is the day the Nutzdaten are written for the transmission, which the rules on the Meldezeitraum
	compare it with.
	"""
	return _serialized(build(filer, zm, created))


def build(filer: Unternehmer, zm: Zm, created: date) -> etree._Element:
	"""The element zm."""
	_check_day(zm.period, created)
	root = etree.Element(_tag("zm"), nsmap={None: NAMESPACE})
	root.set("version", VERSION)
	unternehmer = _append(root, "unternehmer")
	_append(unternehmer, "knri", filer.ust_idnr)
	zulassung = _append(unternehmer, "zulassNr")
	_append(zulassung, "zulnr1", ZULNR1)
	_append(zulassung, "zulnr2", filer.teilnehmernummer or ZULNR2)
	anschrift = _append(unternehmer, "anschrift")
	for attribute, text_field in ANSCHRIFT.items():
		if getattr(filer, attribute) is not None:
			_append(anschrift, text_field.element, getattr(filer, attribute))
	zeilen = _append(unternehmer, "zm-zeilen")
	zeilen.set("waehrung", EURO)
	zeilen.set("meldeart", zm.meldeart.value)
	_append(zeilen, "anzeige", _boolean(zm.anzeige))
	_append(zeilen, "widerruf", _boolean(zm.widerruf))
	meldezeitraum = _append(zeilen, "mzr")
	_append(meldezeitraum, "quart", str(zm.period.quart))
	_append(meldezeitraum, "jahr", str(zm.period.year))
	for line in zm.reported:
		zeile = _append(zeilen, "zeile")
		zeile.set("umsatzart", line.art.value)
		_append(zeile, "knre", line.vat_id)
		_append(zeile, "betrag", str(int(line.amount)))
	return root


def _check_lines(lines: Iterable[Meldezeile]) -> None:
	seen: set[tuple[str, Art]] = set()
	for line in lines:
		if line.key in seen:
			raise XmlError(LINE_TWICE, line.vat_id, line.art.value)
		seen.add(line.key)
		if not line.amount:
			raise XmlError(ZERO_LINE, line.vat_id, line.art.value)


def _check_day(period: ReportingPeriod, created: date) -> None:
	if period.year < created.year - YEARS_BACK:
		raise XmlError(TOO_OLD, period.label, created.year - YEARS_BACK)
	if created < period.start:
		raise XmlError(NOT_BEGUN, period.label)
	if period.kind is Kind.TWO_MONTHS and created < date(period.year, period.first_month + 1, 1):
		raise XmlError(TWO_MONTHS_TOO_EARLY, period.label)


def _german_vat_id(value: object) -> str:
	number = vat_ids.normalize(value) if isinstance(value, str) else ""
	if not vat_ids.GERMAN.fullmatch(number):
		raise XmlError(NOT_A_GERMAN_VAT_ID, value)
	return number


def _country(value: object) -> str:
	code = value.strip().upper() if isinstance(value, str) else value
	if code is None or code == "":
		raise XmlError(ustva_xml.TEXT_MISSING, label=COUNTRY_LABEL)
	if code == UNITED_KINGDOM:
		raise XmlError(UNITED_KINGDOM_ADDRESS)
	if code not in COUNTRIES:
		raise XmlError(UNKNOWN_COUNTRY, value)
	return code


def _teilnehmernummer(value: str | None) -> str | None:
	number = "".join((value or "").split())
	if not number:
		return None
	if not TEILNEHMERNUMMER.fullmatch(number) or int(number) < TEILNEHMERNUMMER_MIN:
		raise XmlError(NOT_A_TEILNEHMERNUMMER, value)
	return number


def _boolean(value: bool) -> str:
	return "true" if value else "false"


def _tag(name: str) -> str:
	return f"{{{NAMESPACE}}}{name}"


def _append(parent: etree._Element, name: str, text: str | None = None) -> etree._Element:
	child = etree.SubElement(parent, _tag(name))
	child.text = text
	return child


def _serialized(root: etree._Element) -> str:
	etree.indent(root, space="\t")
	return etree.tostring(root, encoding="unicode") + "\n"
