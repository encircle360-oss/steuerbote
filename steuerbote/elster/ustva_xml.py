"""The Umsatzsteuer-Voranmeldung as ELSTER XML: the element Anmeldungssteuern of the schema of its year.

Sources are the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/), cited as
HB for ERiC-Entwicklerhandbuch.pdf and JD for Jahresdokumentation_UStVA_2026.ods with its rules by
Fehlercode, and the ELSTER help "Benutzeranleitung zum Hochladen von Formulardaten"
(https://www.elster.de/eportal/helpGlobal?themaGlobal=ustva_upload, retrieved 18 November 2026). The schema of
2027 comes provisionally from the documentation of Beta ERiC 45.1.5.0
(https://download.elster.de/download/eric/eric_45/): UStVA-2027.xsd orders the elements as UStVA-2026.xsd does and
gives Kz 09 five digits alone, which is what the writer writes there in every year.

One tree serves both ways of filing:

- Mein ELSTER imports a file of the Nutzdaten alone: „dass nur der Inhalt der Nutzdaten (vollständiger Pfad
  gemäß Schnittstellenbeschreibung, z. B.: "/Elster/DatenTeil/Nutzdatenblock/Nutzdaten/Anmeldungssteuern")
  hochgeladen werden kann“, and „Der zu verwendende Zeichensatz der XML-Datei lautet ISO-8859-15.“ (help).
  ``to_import_file`` writes it with the declaration of the help's example.
- ERiC takes the same tree as the Nutzdaten of a DatenTeil, in UTF-8 (HB 5.3.2), with the Hersteller-ID in
  Kz 09, which ERiC requires (JD 110085045). ``to_nutzdaten`` writes it; steuerbote/eric/header.py puts it
  into the DatenTeil, and EricCreateTH adds the TransferHeader. The whole envelope of envelope.py serves
  the schema tests only.

Kz 09 stays out of the import file. Mein ELSTER does not import it (the help lists
Umsatzsteuervoranmeldung/Kz09 among the elements it leaves out), the import goes through the form and not
through ERiC, and Steuerbote has no Hersteller-ID of its own yet. The value 74931 of the documentation's
examples „dient in der Dokumentation nur noch zu Illustrationszwecken“ (HB 6.5.3) and is never written.

The rules (JD, sheet "Allg. Information" for the formats):

- The elements follow the xs:sequence of the schema, not the numbers: Kz 90 follows Kz 93.
- A base is written in whole euros, a tax with exactly two decimals and a point; there is no plus sign, no
  leading zero and no negative zero. Kz 37 and Kz 39 (Formatkennzeichen %) and Kz 50 (U) take no sign.
- A Kennzahl of zero is left out: written without Kz 10, an explicit zero draws a hint („ist die Erklärung
  eines Nullwertes nicht erforderlich“, 110085186 to 110085217). Kz 83 is always written (110085064).
- A corrected return writes zero for each Kennzahl that the returns it replaces reported and it no longer
  does. This is an inference, not a documented rule: the hints fire only under FeldNichtAngegeben(Kz10), so
  a zero in a corrected return draws none, and the Anleitung to the form says nothing about zeros. The first
  real import into Mein ELSTER has to show whether the zeros are needed.
- A base and its tax in a Kennzahl of its own go together (110085065 to 110085072), so the other one is
  written as zero if need be.
- Kz 83 is recomputed from the values as written and has to match: no rule of ERiC checks it, and Mein
  ELSTER copies it „in das Feld für die manuelle Eingabe“ (help). A return with the tax as booked of the bases at a
  statutory rate (StatutoryTax of steuerbote/ustva/calculation.py) gives that tax with its amounts (``taxes``), and
  the check takes it instead of the tax of the base in full euros; nothing else of the file changes.
- Kz 29 needs a surplus in Kz 83 or Kz 10 (11085149); Kz 500 and its Begründung go together (11085137);
  the date in Kz 70 lies in the year of the period (11085153).
- Texts use the ELSTER character set (charset.py) and have no blank at either end (JD "Formale Fehler").
"""

import re
from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import NamedTuple

from lxml import etree

from steuerbote.elster.charset import CharsetError, describe, transliterate
from steuerbote.ustva import Kennzahl, Kind, Mapping, Period, StatutoryTax, calculate, catalogue_for
from steuerbote.ustva.kennzahlen import BALANCE_KENNZAHL
from steuerbote.ustva.rounding import ZERO, require_decimal, to_cents, to_full_euros

IMPORT_DECLARATION = b'<?xml version="1.0" encoding="ISO-8859-15" standalone="no"?>\n'
IMPORT_ENCODING = "iso-8859-15"
YES = "1"
BASE_DIGITS = 13
TAX_INTEGER_DIGITS = 11
SUPPLEMENTARY_CODES = ("1", "2", "3", "4")
BEGRUENDUNG_LENGTH = 180
EXAMPLE_HERSTELLER_ID = "74931"
STEUERNUMMER_PATTERN = re.compile("[0-9]{4}0[0-9]{8}")
WID_NR_PATTERN = re.compile("DE[0-9]{9}")
HERSTELLER_ID_PATTERN = re.compile("[0-9]{5}")

NO_SCHEMA = "Steuerbote cannot write the ELSTER XML for {0} yet."
UNKNOWN_KENNZAHL = "Kennzahl {0} is not on the form of {1}."
NO_AMOUNT = "Kennzahl {0} takes no amount."
TOO_MANY_DIGITS = "Kennzahl {0} has more digits than ELSTER takes: {1}."
NEGATIVE = "Kennzahl {0} takes no negative amount: {1}."
BALANCE_MISSING = "Kennzahl 83 is missing."
BALANCE_MISMATCH = "Kennzahl 83 is {0}, but the Kennzahlen written give {1}."
OFFSET_WITHOUT_REFUND = (
	"Kennzahl 29 is for a refund: Kennzahl 83 has to show a surplus, unless the return is a corrected return "
	"(Kz 10)."
)
UNKNOWN_CODE = "Kennzahl 500 takes 1, 2, 3 or 4, not {0}."
CODE_WITHOUT_BEGRUENDUNG = "Kennzahl 500 needs a Begründung."
BEGRUENDUNG_WITHOUT_CODE = "A Begründung is only filed with Kennzahl 500."
SWITCH_IN_ANOTHER_YEAR = "The date in Kennzahl 70 has to lie in {0}, not in {1}."
NOT_A_STEUERNUMMER = "{0} is not a Steuernummer in the 13-digit ELSTER format."
NOT_A_WID_NR = (
	"{0} is not a Wirtschafts-Identifikationsnummer: ELSTER takes DE and nine digits, without the "
	"five-digit suffix."
)
NOT_A_HERSTELLER_ID = "{0} is not a Hersteller-ID of five digits."
ILLUSTRATION_HERSTELLER_ID = "74931 only illustrates the ERiC documentation and is no Hersteller-ID."
TEXT_MISSING = "{label} is missing."
TEXT_TOO_LONG = "{label} has {0} characters, ELSTER takes at most {1}."
TEXT_CHARACTERS = "{label} contains characters ELSTER does not take: {0}."
MESSAGES = (
	NO_SCHEMA,
	UNKNOWN_KENNZAHL,
	NO_AMOUNT,
	TOO_MANY_DIGITS,
	NEGATIVE,
	BALANCE_MISSING,
	BALANCE_MISMATCH,
	OFFSET_WITHOUT_REFUND,
	UNKNOWN_CODE,
	CODE_WITHOUT_BEGRUENDUNG,
	BEGRUENDUNG_WITHOUT_CODE,
	SWITCH_IN_ANOTHER_YEAR,
	NOT_A_STEUERNUMMER,
	NOT_A_WID_NR,
	NOT_A_HERSTELLER_ID,
	ILLUSTRATION_HERSTELLER_ID,
	TEXT_MISSING,
	TEXT_TOO_LONG,
	TEXT_CHARACTERS,
)

NAME_LABEL = "The name of the Datenlieferant"
STREET_LABEL = "The street of the Datenlieferant"
POSTAL_CODE_LABEL = "The postal code of the Datenlieferant"
TOWN_LABEL = "The town of the Datenlieferant"
PHONE_LABEL = "The phone number of the Datenlieferant"
EMAIL_LABEL = "The email address of the Datenlieferant"
BEGRUENDUNG_LABEL = "The Begründung of Kennzahl 500"
LABELS = (
	NAME_LABEL,
	STREET_LABEL,
	POSTAL_CODE_LABEL,
	TOWN_LABEL,
	PHONE_LABEL,
	EMAIL_LABEL,
	BEGRUENDUNG_LABEL,
)


class XmlError(ValueError):
	"""The return cannot be written as ELSTER takes it.

	``template``, ``values`` and the ``label`` of the text concerned make the message, so that a caller can
	translate template and label before formatting them.
	"""

	def __init__(self, template: str, *values: object, label: str = "") -> None:
		super().__init__(template.format(*values, label=label))
		self.template = template
		self.values = values
		self.label = label


@dataclass(frozen=True, slots=True)
class Schema:
	"""What the XML schema of a year adds to the Kennzahlen of its form.

	``order`` lists the Kennzahlen as the xs:sequence of the element Umsatzsteuervoranmeldung does, which is
	not their numeric order; ``unsigned`` holds those whose type takes no sign.
	"""

	year: int
	namespace: str
	order: tuple[str, ...]
	unsigned: frozenset[str]

	@property
	def elements(self) -> tuple[str, ...]:
		"""Every child of Umsatzsteuervoranmeldung, in the order of the schema."""
		kennzahlen = tuple(f"Kz{number}" for number in self.order)
		return ("Jahr", "Zeitraum", "Steuernummer", "WIdNr", "Kz09", *kennzahlen, "Kz500_Begruendung")


# UStVA-2026.xsd and UStVA-2027.xsd, type Umsatzsteuervoranmeldung_m472961002_CType; JD of both years:
# Formatkennzeichen % for Kz 37 and Kz 39, U for Kz 50.
_ORDER_2026 = (
	*("10", "21", "22", "26", "29", "35", "36", "37", "39", "41", "42", "43", "44", "45", "46"),
	*("47", "48", "49", "50", "59", "60", "61", "62", "63", "64", "65", "66", "67", "69", "70"),
	*("73", "74", "76", "77", "80", "81", "83", "84", "85", "86", "87", "89", "91", "93", "90"),
	*("94", "95", "96", "98", "500"),
)
_UNSIGNED_2026 = frozenset({"37", "39", "50"})
SCHEMAS: MappingProxyType[int, Schema] = MappingProxyType(
	{
		2026: Schema(
			year=2026,
			namespace="http://finkonsens.de/elster/elsteranmeldung/ustva/v2026",
			order=_ORDER_2026,
			unsigned=_UNSIGNED_2026,
		),
		2027: Schema(
			year=2027,
			namespace="http://finkonsens.de/elster/elsteranmeldung/ustva/v2027",
			order=_ORDER_2026,
			unsigned=_UNSIGNED_2026,
		),
	}
)


def schema_for(year: int) -> Schema:
	try:
		return SCHEMAS[year]
	except KeyError:
		raise XmlError(NO_SCHEMA, year) from None


class TextField(NamedTuple):
	element: str
	label: str
	length: int
	required: bool


# The DatenLieferant of UStVA-2026.xsd; ERiC requires name, street, postal code and town (JD 110085075
# to 110085078). The street takes the house number too.
DATENLIEFERANT: MappingProxyType[str, TextField] = MappingProxyType(
	{
		"name": TextField("Name", NAME_LABEL, 45, required=True),
		"street": TextField("Strasse", STREET_LABEL, 30, required=True),
		"postal_code": TextField("PLZ", POSTAL_CODE_LABEL, 12, required=True),
		"city": TextField("Ort", TOWN_LABEL, 30, required=True),
		"phone": TextField("Telefon", PHONE_LABEL, 20, required=False),
		"email": TextField("Email", EMAIL_LABEL, 70, required=False),
	}
)


def elster_text(value: str | None, label: str, length: int) -> str | None:
	"""A text as ELSTER takes it: transliterated, on one line, without blanks at either end; None if empty."""
	if value is None:
		return None
	try:
		text = " ".join(transliterate(value).split())
	except CharsetError as error:
		described = ", ".join(describe(character) for character in error.characters)
		raise XmlError(TEXT_CHARACTERS, described, label=label) from None
	if len(text) > length:
		raise XmlError(TEXT_TOO_LONG, len(text), length, label=label)
	return text or None


def required_text(value: str | None, label: str, length: int) -> str:
	"""A text as ELSTER takes it that must not be empty."""
	text = elster_text(value, label, length)
	if text is None:
		raise XmlError(TEXT_MISSING, label=label)
	return text


def normalized_wid_nr(value: str | None) -> str | None:
	"""The Wirtschafts-Identifikationsnummer as the schema takes it, DE and nine digits, or None.

	A W-IdNr. carries a five-digit suffix such as -00001; the Voranmeldung takes the number without it
	(pattern DE[0-9]{9} in UStVA-2026.xsd). Blanks are dropped and the letters capitalised.
	"""
	compact = "".join((value or "").split()).upper()
	if not compact:
		return None
	if not WID_NR_PATTERN.fullmatch(compact):
		raise XmlError(NOT_A_WID_NR, value)
	return compact


def require_hersteller_id(value: str) -> str:
	"""The Hersteller-ID of five digits that the Bayerisches Landesamt für Steuern assigns.

	HerstellerIDSType in headerbasis_datentypen.xsd of the ElsterBasisSchema.
	"""
	if not isinstance(value, str) or not HERSTELLER_ID_PATTERN.fullmatch(value):
		raise XmlError(NOT_A_HERSTELLER_ID, value)
	if value == EXAMPLE_HERSTELLER_ID:
		raise XmlError(ILLUSTRATION_HERSTELLER_ID)
	return value


@dataclass(frozen=True, slots=True)
class Filer:
	"""The company that files, as ELSTER names it.

	``steuernummer`` is the 13-digit number for ELSTER (steuernummer.py), ``wid_nr`` the
	Wirtschafts-Identifikationsnummer if the company has one. The other fields are the Datenlieferant. Texts
	are kept as ELSTER takes them: transliterated, on one line and trimmed; one longer than the schema
	allows is refused.
	"""

	steuernummer: str
	name: str
	street: str
	postal_code: str
	city: str
	phone: str | None = None
	email: str | None = None
	wid_nr: str | None = None

	def __post_init__(self) -> None:
		if not isinstance(self.steuernummer, str) or not STEUERNUMMER_PATTERN.fullmatch(self.steuernummer):
			raise XmlError(NOT_A_STEUERNUMMER, self.steuernummer)
		object.__setattr__(self, "wid_nr", normalized_wid_nr(self.wid_nr))
		for attribute, field in DATENLIEFERANT.items():
			clean = required_text if field.required else elster_text
			object.__setattr__(self, attribute, clean(getattr(self, attribute), field.label, field.length))


@dataclass(frozen=True, slots=True)
class Voranmeldung:
	"""One Umsatzsteuer-Voranmeldung as filed.

	``amounts`` holds the Kennzahlen with an amount as the core reports them, Kz 83 included. The yes fields
	(Kz 10, 22, 26, 29), Kz 500 with its Begründung and the date of Kz 70 have fields of their own.
	``reported_before`` names the Kennzahlen that the returns a corrected return replaces reported; it
	writes each of them, as zero if it has no amount for it. Those zeros are inferred from the hints on zero
	values, not prescribed; see the rules in the docstring of the module. ``taxes`` holds the tax as booked of the
	bases at a statutory rate that Kz 83 holds, by Kennzahl; none when Kz 83 holds the tax of the form.
	"""

	period: Period
	amounts: ReadOnlyMapping[str, Decimal]
	corrected: bool = False
	attachments: bool = False
	no_sepa_mandate: bool = False
	offset_requested: bool = False
	supplementary_code: str | None = None
	begruendung: str | None = None
	regelbesteuerung_from: date | None = None
	reported_before: frozenset[str] = frozenset()
	taxes: ReadOnlyMapping[str, Decimal] = MappingProxyType({})

	def __post_init__(self) -> None:
		object.__setattr__(self, "amounts", MappingProxyType(dict(self.amounts)))
		object.__setattr__(self, "taxes", MappingProxyType(dict(self.taxes)))
		object.__setattr__(self, "reported_before", frozenset(self.reported_before))
		if self.reported_before and not self.corrected:
			raise ValueError("only a corrected return (Kz 10) writes the Kennzahlen reported before")


def pairs(catalogue: ReadOnlyMapping[str, Kennzahl]) -> dict[str, str]:
	"""Each base whose tax the form reports in a Kennzahl of its own, with that Kennzahl."""
	return {number: kennzahl.tax_kennzahl for number, kennzahl in catalogue.items() if kennzahl.tax_kennzahl}


def import_file_name(voranmeldung: Voranmeldung) -> str:
	"""UStVA_<Jahr>_<Zeitraum>.xml, with _berichtigt for a corrected return; ELSTER prescribes no name."""
	period = voranmeldung.period
	return f"UStVA_{period.year}_{period.code}{'_berichtigt' if voranmeldung.corrected else ''}.xml"


def to_import_file(filer: Filer, voranmeldung: Voranmeldung, created: date) -> bytes:
	"""The file to import into the form of Mein ELSTER, in ISO-8859-15, created on ``created``."""
	return IMPORT_DECLARATION + serialized(build(filer, voranmeldung, created)).encode(IMPORT_ENCODING)


def to_nutzdaten(filer: Filer, voranmeldung: Voranmeldung, created: date, hersteller_id: str) -> str:
	"""The Nutzdaten for ERiC: the tree of the import file with the Hersteller-ID in Kz 09, as text."""
	return serialized(build(filer, voranmeldung, created, hersteller_id))


def build(
	filer: Filer, voranmeldung: Voranmeldung, created: date, hersteller_id: str | None = None
) -> etree._Element:
	"""The element Anmeldungssteuern; with a Hersteller-ID it carries Kz 09 for ERiC."""
	schema = schema_for(voranmeldung.period.year)
	texts = {
		"Jahr": str(schema.year),
		"Zeitraum": voranmeldung.period.code,
		"Steuernummer": filer.steuernummer,
		"WIdNr": filer.wid_nr,
		"Kz09": None if hersteller_id is None else require_hersteller_id(hersteller_id),
		**_kennzahlen(schema, voranmeldung),
	}
	root, steuerfall = anmeldungssteuern(filer, schema, created)
	context(steuerfall, schema, "Umsatzsteuervoranmeldung", texts, schema.elements)
	return root


def anmeldungssteuern(filer: Filer, schema: Schema, created: date) -> tuple[etree._Element, etree._Element]:
	"""The element Anmeldungssteuern of the schema with Erstellungsdatum and DatenLieferant, and its Steuerfall.

	The Steuerfall takes the one context of the filing: the Umsatzsteuervoranmeldung here, or one of the two of
	form USt 1 H (ust1h_xml.py), since a filing holds exactly one of the three (JD 110085099).
	"""
	root = etree.Element(_tag(schema, "Anmeldungssteuern"), nsmap={None: schema.namespace})
	root.set("version", str(schema.year))
	_append(root, schema, "Erstellungsdatum", created.strftime("%Y%m%d"))
	datenlieferant = _append(root, schema, "DatenLieferant")
	for attribute, field in DATENLIEFERANT.items():
		if getattr(filer, attribute) is not None:
			_append(datenlieferant, schema, field.element, getattr(filer, attribute))
	return root, _append(root, schema, "Steuerfall")


def context(
	steuerfall: etree._Element,
	schema: Schema,
	name: str,
	texts: ReadOnlyMapping[str, str | None],
	elements: Iterable[str],
) -> etree._Element:
	"""The context ``name`` in the Steuerfall, with each of ``elements`` in that order that has a text."""
	child = _append(steuerfall, schema, name)
	for element in elements:
		if texts.get(element) is not None:
			_append(child, schema, element, texts[element])
	return child


def _kennzahlen(schema: Schema, voranmeldung: Voranmeldung) -> dict[str, str]:
	catalogue = catalogue_for(schema.year)
	amounts = {
		number: _rounded(schema, _holding_amount(catalogue, number, schema.year), amount)
		for number, amount in voranmeldung.amounts.items()
	}
	if BALANCE_KENNZAHL not in amounts:
		raise XmlError(BALANCE_MISSING)
	written = {number for number, amount in amounts.items() if amount} | {BALANCE_KENNZAHL}
	written |= {
		_holding_amount(catalogue, number, schema.year).number for number in voranmeldung.reported_before
	}
	for base, tax in pairs(catalogue).items():
		if written & {base, tax}:
			written |= {base, tax}
	values = {
		number: amounts[number] if number in amounts else _rounded(schema, catalogue[number], ZERO)
		for number in written
	}
	_check_balance(schema.year, values, voranmeldung.taxes)
	return {
		**{f"Kz{number}": format(value, "f") for number, value in values.items()},
		**_further_details(schema, voranmeldung, values[BALANCE_KENNZAHL]),
	}


def _holding_amount(catalogue: ReadOnlyMapping[str, Kennzahl], number: str, year: int) -> Kennzahl:
	kennzahl = catalogue.get(number)
	if kennzahl is None:
		raise XmlError(UNKNOWN_KENNZAHL, number, year)
	if not kennzahl.holds_amount:
		raise XmlError(NO_AMOUNT, number)
	return kennzahl


def _rounded(schema: Schema, kennzahl: Kennzahl, amount: Decimal) -> Decimal:
	"""The amount as written: a base in whole euros, a tax in cents, within the digits of the schema."""
	if not require_decimal(amount).is_finite():
		raise ValueError(f"Kennzahl {kennzahl.number}: {amount} is not an amount")
	is_base = kennzahl.kind is Kind.BASE
	value = to_full_euros(amount) if is_base else to_cents(amount)
	if value < ZERO and kennzahl.number in schema.unsigned:
		raise XmlError(NEGATIVE, kennzahl.number, format(value, "f"))
	integer_digits = len(format(abs(value), "f").partition(".")[0])
	if integer_digits > (BASE_DIGITS if is_base else TAX_INTEGER_DIGITS):
		raise XmlError(TOO_MANY_DIGITS, kennzahl.number, format(value, "f"))
	return value


def _check_balance(year: int, values: dict[str, Decimal], taxes: ReadOnlyMapping[str, Decimal]) -> None:
	"""Kz 83 as the form computes it from the values written, with the taxes it derives from the bases or, for a base
	with a tax as booked, that tax."""
	written = {number: value for number, value in values.items() if number != BALANCE_KENNZAHL}
	statutory_tax = StatutoryTax.AS_BOOKED if taxes else StatutoryTax.FROM_BASE
	form = calculate(
		(),
		Mapping(chart="", rules=(), year=year),
		extra_values=written,
		statutory_tax=statutory_tax,
		taxes=taxes,
	)
	if form.kz83 != values[BALANCE_KENNZAHL]:
		raise XmlError(BALANCE_MISMATCH, format(values[BALANCE_KENNZAHL], "f"), format(form.kz83, "f"))


def _further_details(schema: Schema, voranmeldung: Voranmeldung, balance: Decimal) -> dict[str, str]:
	texts = {}
	if voranmeldung.corrected:
		texts["Kz10"] = YES
	if voranmeldung.attachments:
		texts["Kz22"] = YES
	if voranmeldung.no_sepa_mandate:
		texts["Kz26"] = YES
	if voranmeldung.offset_requested:
		if balance >= ZERO and not voranmeldung.corrected:
			raise XmlError(OFFSET_WITHOUT_REFUND)
		texts["Kz29"] = YES
	return {
		**texts,
		**regelbesteuerung_details(voranmeldung.regelbesteuerung_from, schema.year),
		**supplementary_details(voranmeldung.supplementary_code, voranmeldung.begruendung),
	}


def regelbesteuerung_details(day: date | None, year: int) -> dict[str, str]:
	"""Kz 70, the date of the switch from the Kleinunternehmer-Regelung, as TT.MM.JJJJ in the year of the
	period (JD 11085153), or nothing without a date."""
	if day is None:
		return {}
	if day.year != year:
		raise XmlError(SWITCH_IN_ANOTHER_YEAR, year, day.year)
	return {"Kz70": day.strftime("%d.%m.%Y")}


def supplementary_details(code: str | None, begruendung: str | None) -> dict[str, str]:
	"""Kz 500 and its Begründung as written, which go together (JD 11085137), or nothing without a code."""
	text = elster_text(begruendung, BEGRUENDUNG_LABEL, BEGRUENDUNG_LENGTH)
	if not code:
		if text is not None:
			raise XmlError(BEGRUENDUNG_WITHOUT_CODE)
		return {}
	if code not in SUPPLEMENTARY_CODES:
		raise XmlError(UNKNOWN_CODE, code)
	if text is None:
		raise XmlError(CODE_WITHOUT_BEGRUENDUNG)
	return {"Kz500": code, "Kz500_Begruendung": text}


def _tag(schema: Schema, name: str) -> str:
	return f"{{{schema.namespace}}}{name}"


def _append(parent: etree._Element, schema: Schema, name: str, text: str | None = None) -> etree._Element:
	child = etree.SubElement(parent, _tag(schema, name))
	child.text = text
	return child


def serialized(root: etree._Element) -> str:
	"""The tree as text, indented with tabs, without a declaration."""
	etree.indent(root, space="\t")
	return etree.tostring(root, encoding="unicode") + "\n"
