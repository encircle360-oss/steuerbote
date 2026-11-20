"""USt-IdNrn. in the Zusammenfassende Meldung: how Steuerbote writes them and which it refuses.

The form of a USt-IdNr. and its country codes are the rule of the confirmation, steuerbote.vatid.ustid, so that
the number the confirmation of § 18e UStG asks about is the number the ZM reports. That rule is the field of the
ELSTER help „Import von Meldelisten zur Zusammenfassenden Meldung“ (Datensatztabelle Meldezeilen, AN 7 to 14) and
of the ERiC data type ZMDO (Jahresdokumentation ZMDO 2, sheet „ZMDO - Felder“, knre_UstIdNr_Erwerber): the
country code of two capital letters, then letters, digits, + and *, 7 to 14 characters in all, written in
capitals without blanks, dots or dashes, with the country codes of the 26 other member states, Greece as EL,
and XI for Northern Ireland. DE is refused, „Es dürfen keine inländischen UstId-Nummern angegeben werden“ (ZMDO
rule 170045014), and so is GB, „nur für die Meldezeiträume bis zum Ablauf des Übergangszeitraumes am
31.12.2020“ (BZSt, Fragen und Antworten zur ZM, Brexit; ZMDO rule 170045017).

The ZM adds one rule of its own: XI only for goods. „Nordirische UStIDs (Präfix XI) dürfen nicht für sonstige
Leistungen verwendet werden“ (ZMDO rule 170045021). Article 8 of the Protocol on Ireland/Northern Ireland to
the withdrawal agreement (OJ C 384 I of 12 November 2019) applies the provisions of Union law on VAT „concerning
goods“ in respect of Northern Ireland, so services to Northern Ireland are services to a third country (BZSt,
Fragen und Antworten zur ZM, Brexit). refusal() names the reason, so that a line can say why the ZM cannot
take its number.

Whether a number has been issued is a question for the confirmation of § 18e UStG, not for this module.
"""

from enum import Enum
from types import MappingProxyType

from steuerbote.ustva.plausibility import member_state
from steuerbote.vatid import ustid as confirmation

GERMANY = "DE"
UNITED_KINGDOM = "GB"
NORTHERN_IRELAND = "XI"
# The one member state whose country code in USt-IdNrn. differs from its ISO code.
VAT_PREFIXES_BY_ISO = {"GR": "EL"}
OTHER_MEMBER_STATES: tuple[str, ...] = tuple(
	code for code in confirmation.MEMBER_STATES if code != NORTHERN_IRELAND
)


class Refusal(Enum):
	"""Why the ZM cannot take a value as a USt-IdNr."""

	FORMAT = "format"
	DOMESTIC = "domestic"
	UNITED_KINGDOM = "united_kingdom"
	UNKNOWN_COUNTRY = "unknown_country"
	NORTHERN_IRELAND_SERVICES = "northern_ireland_services"


# The country codes the confirmation refuses although they look right, and how the ZM names the reason; GR is
# no country code of a USt-IdNr. at all.
_REFUSED_COUNTRIES = MappingProxyType({GERMANY: Refusal.DOMESTIC, UNITED_KINGDOM: Refusal.UNITED_KINGDOM})


def clean(value: str | None) -> str:
	"""The letters, digits, + and * of a value, letters in upper case."""
	return confirmation.normalize(value or "")


def refusal(value: str | None, services: bool = False) -> Refusal | None:
	"""Why the ZM cannot take the value, or None if it can; ``services`` for a line of Art S."""
	number = clean(value)
	if not (
		confirmation.COUNTRY_CODE.fullmatch(number[:2])
		and confirmation.MIN_LENGTH <= len(number) <= confirmation.MAX_LENGTH
	):
		return Refusal.FORMAT
	if not confirmation.is_plausible(number):
		return _REFUSED_COUNTRIES.get(number[:2], Refusal.UNKNOWN_COUNTRY)
	if services and number[:2] == NORTHERN_IRELAND:
		return Refusal.NORTHERN_IRELAND_SERVICES
	return None


def normalize(value: str | None, services: bool = False) -> str | None:
	"""The USt-IdNr. as the ZM writes it, or None if the ZM cannot take the value."""
	return None if refusal(value, services) else clean(value)


def country_prefix(country: str | None) -> str | None:
	"""The country code that a USt-IdNr. issued in ``country`` starts with, or None outside the other member
	states. ``country`` is an ISO code, the name of a Country in ERPNext, or a country code of USt-IdNrn. such as
	EL or XI; Monaco counts as France (§ 1 Absatz 2a UStG)."""
	code = (country or "").strip().upper()
	if code in confirmation.MEMBER_STATES:
		return code
	state = member_state(country)
	if state is None:
		return None
	prefix = VAT_PREFIXES_BY_ISO.get(state.code, state.code)
	return prefix if prefix in OTHER_MEMBER_STATES else None
