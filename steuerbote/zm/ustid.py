"""USt-IdNrn. in the Zusammenfassende Meldung: how Steuerbote writes them and which it refuses.

The ELSTER help „Import von Meldelisten zur Zusammenfassenden Meldung“ (Datensatztabelle Meldezeilen) describes
the field as AN(7,14): „Die Umsatzsteuer-Identifikationsnummer muss mit dem Länderkennzeichen, bestehend aus
zwei Großbuchstaben A bis Z, beginnen. [...] Die folgenden Zeichen können Buchstaben, Ziffern oder die Zeichen +
und * sein. Nicht erlaubt sind Leerzeichen, Sonderzeichen und Umlaute. Die Angabe zur
Umsatzsteuer-Identifikationsnummer muss mindestens 7 Zeichen enthalten.“ The ERiC data type ZMDO has the same
field (Jahresdokumentation ZMDO 2, sheet „ZMDO - Felder“, knre_UstIdNr_Erwerber, 7 to 14 characters).

normalize() keeps the letters, digits, + and * of a value as ERPNext holds it, so that "ATU 123 456 78" becomes
"ATU12345678", writes letters in upper case and takes the result if it has that form and starts with a country
code of the help page's „Liste der Länderkennzeichen“: the 26 other member states, Greece as EL, and XI for
Northern Ireland. It refuses
- DE: „Es dürfen keine inländischen UstId-Nummern angegeben werden“ (ZMDO rule 170045014);
- GB: „Das Länderkennzeichen "GB" ist nur für die Meldezeiträume bis zum Ablauf des Übergangszeitraumes am
  31.12.2020 ein zulässiges Länderkennzeichen“ (BZSt, Fragen und Antworten zur ZM, Brexit; ZMDO rule 170045017);
- XI for sonstige Leistungen: „Nordirische UStIDs (Präfix XI) dürfen nicht für sonstige Leistungen verwendet
  werden“ (ZMDO rule 170045021). Article 8 of the Protocol on Ireland/Northern Ireland to the withdrawal
  agreement (OJ C 384 I of 12 November 2019) applies the provisions of Union law on VAT „concerning goods“ in
  respect of Northern Ireland, so services to Northern Ireland are services to a third country (BZSt, Fragen und
  Antworten zur ZM, Brexit).

Whether a number has been issued is a question for the confirmation of § 18e UStG, not for this module.
"""

import re
from enum import Enum

from steuerbote.ustva.plausibility import EU_MEMBER_STATES, GERMANY, member_state

UNITED_KINGDOM = "GB"
NORTHERN_IRELAND = "XI"
# The one member state whose country code in USt-IdNrn. differs from its ISO code.
VAT_PREFIXES_BY_ISO = {"GR": "EL"}
OTHER_MEMBER_STATES: tuple[str, ...] = tuple(
	VAT_PREFIXES_BY_ISO.get(state.code, state.code) for state in EU_MEMBER_STATES if state.code != GERMANY
)
_KEPT = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+*")
_FORM = re.compile(r"[A-Z]{2}[A-Z0-9+*]{5,12}")


class Refusal(Enum):
	"""Why the ZM cannot take a value as a USt-IdNr."""

	FORMAT = "format"
	DOMESTIC = "domestic"
	UNITED_KINGDOM = "united_kingdom"
	UNKNOWN_COUNTRY = "unknown_country"
	NORTHERN_IRELAND_SERVICES = "northern_ireland_services"


def clean(value: str | None) -> str:
	"""The letters, digits, + and * of a value, letters in upper case."""
	return "".join(character for character in value or "" if character in _KEPT).upper()


def refusal(value: str | None, services: bool = False) -> Refusal | None:
	"""Why the ZM cannot take the value, or None if it can; ``services`` for a line of Art S."""
	cleaned = clean(value)
	if not _FORM.fullmatch(cleaned):
		return Refusal.FORMAT
	prefix = cleaned[:2]
	if prefix == GERMANY:
		return Refusal.DOMESTIC
	if prefix == UNITED_KINGDOM:
		return Refusal.UNITED_KINGDOM
	if prefix == NORTHERN_IRELAND:
		return Refusal.NORTHERN_IRELAND_SERVICES if services else None
	if prefix not in OTHER_MEMBER_STATES:
		return Refusal.UNKNOWN_COUNTRY
	return None


def normalize(value: str | None, services: bool = False) -> str | None:
	"""The USt-IdNr. as the ZM writes it, or None if the ZM cannot take the value."""
	return None if refusal(value, services) else clean(value)


def country_prefix(country: str | None) -> str | None:
	"""The country code that a USt-IdNr. issued in ``country`` starts with, or None outside the other member
	states. ``country`` is an ISO code, the name of a Country in ERPNext, or a country code of USt-IdNrn. such as
	EL or XI; Monaco counts as France (§ 1 Absatz 2a UStG)."""
	code = (country or "").strip().upper()
	if code == NORTHERN_IRELAND or code in OTHER_MEMBER_STATES:
		return code
	state = member_state(country)
	if state is None:
		return None
	prefix = VAT_PREFIXES_BY_ISO.get(state.code, state.code)
	return prefix if prefix in OTHER_MEMBER_STATES else None
