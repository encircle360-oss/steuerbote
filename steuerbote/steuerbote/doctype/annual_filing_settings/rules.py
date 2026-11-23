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

Messages are English templates with positional placeholders. SettingsError keeps the template and its values
apart, so that the Frappe layer translates the template before formatting it. This module is pure Python and never
imports Frappe.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from steuerbote.elster.charset import CharsetError, describe, transliterate


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


MESSAGES = (
	NOT_A_LEGAL_FORM,
	TEXT_TOO_LONG,
	TEXT_CHARACTERS,
	NOT_A_HOUSE_NUMBER,
	HOUSE_NUMBER_WITHOUT_STREET,
	SUFFIX_WITHOUT_HOUSE_NUMBER,
	NOT_A_POSTAL_CODE,
	STREET_LINE_TOO_LONG,
)
