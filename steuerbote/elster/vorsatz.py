"""The Vorsatz of an Erklärung: the part of the E50, E30 and E20 that names the case for ELSTER.

Sources are the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/), cited as HB for
ERiC-Entwicklerhandbuch.pdf, JD for the sheets „Vorsatz - Felder“ and „Vorsatz - Regeln“ of
Jahresdokumentation_E50_2026.ods, Jahresdokumentation_E30_2025.ods and Jahresdokumentation_E20_2025.ods, which
describe the same Vorsatz, and FP for Datenarten/ElsterErklaerung/Formale_Plausipruefungen.ods. The schemas give it
the same elements in the same order, as the last element of the Nutzdaten (the types Vorsatz_*_CType of
E50-2026.xsd, E30-2025.xsd and E20-2025.xsd).

What steuerbote writes, each field with the rule of the JD that requires it:

- Unterfallart: 50, 30 or 20, that of the Datenart (HB Tabelle 2-12; 10425).
- Vorgang 01, „Veranlagung“: the only value the USt takes and the first of KSt and GewSt (10427).
- StNr: the Steuernummer in the 13-digit ELSTER format, ([0-9]{4})0[0-9]{8}, which OrdNrArt S requires (10433).
- Zeitraum: the year of the Erklärung, which has to be the one of its Datenart (109000004, 109000005).
- AbsName, AbsStr, AbsPlz and AbsOrt, the sender, of at most 45, 30, 5 and 29 characters; the Postleitzahl has five
  German digits and is optional (10100, 10110, 10130).
- Copyright, the „Copyrightvermerk des Herstellers der Steuersoftware“ of at most 50 characters (10435), „Copyright
  des Herstellers (Herstellername, Firmensitz)“ (FP 6, 10411).
- OrdNrArt S for the Steuernummer: steuerbote files no Neuaufnahme, O, which E30 and E20 do not take at all (10423).
- Rueckuebermittlung/Bescheid: 1 if the Bescheiddaten are to be provided for electronic retrieval, else 2 (10438).

ERiC sets the fields the JD marks „Internes ERiC Feld“ itself: Ordnungsbegriff, TeleNummer and the
Bundesfinanzamtsnummer (10436). ID and IDEhefrau are for the Einkommensteuer only (10079, 10080), and the key and
the address of the notice of the Bescheiddaten serve a send-NoSig (FP 10153), which steuerbote never sends.

Texts are written in the character set Standard_E_V2 (JD, sheet „Allg. Information“) through charset.py, on one line
and without blanks at either end (ustva_xml.elster_text).
"""

import re
from dataclasses import dataclass
from types import MappingProxyType

from lxml import etree

from steuerbote.elster.ustva_xml import (
	NOT_A_STEUERNUMMER,
	STEUERNUMMER_PATTERN,
	TEXT_CHARACTERS,
	TEXT_MISSING,
	TEXT_TOO_LONG,
	XmlError,
	required_text,
)
from steuerbote.eric.datenart import Datenart

VERANLAGUNG = "01"
STEUERNUMMER = "S"
BESCHEIDDATEN = "1"
NO_BESCHEIDDATEN = "2"
POSTLEITZAHL_PATTERN = re.compile("0[1-9][0-9]{3}|[1-9][0-9]{4}")
"""Postleitzahl_DE of the JD: five digits that do not begin with 00."""

NOT_A_POSTLEITZAHL = "{0} is not a German Postleitzahl of five digits."
MESSAGES = (NOT_A_POSTLEITZAHL, NOT_A_STEUERNUMMER, TEXT_MISSING, TEXT_TOO_LONG, TEXT_CHARACTERS)

NAME_LABEL = "The name of the sender of the Erklärung"
STREET_LABEL = "The street of the sender of the Erklärung"
CITY_LABEL = "The town of the sender of the Erklärung"
COPYRIGHT_LABEL = "The copyright notice of the manufacturer of the software"
LABELS = (NAME_LABEL, STREET_LABEL, CITY_LABEL, COPYRIGHT_LABEL)

TEXTS: MappingProxyType[str, tuple[int, bool]] = MappingProxyType(
	{"AbsName": (45, True), "AbsStr": (30, True), "AbsOrt": (29, True), "Copyright": (50, True)}
)
"""The texts of the Vorsatz with their greatest length and whether a rule requires them (JD)."""
_TEXT_FIELDS = (
	("name", "AbsName", NAME_LABEL),
	("street", "AbsStr", STREET_LABEL),
	("city", "AbsOrt", CITY_LABEL),
	("copyright", "Copyright", COPYRIGHT_LABEL),
)


@dataclass(frozen=True, slots=True)
class Vorsatz:
	"""What the Vorsatz says of the company that files.

	``steuernummer`` is the 13-digit number for ELSTER (steuernummer.py). Texts are kept as ELSTER takes them:
	transliterated, on one line and trimmed; one longer than the JD allows is refused.
	"""

	steuernummer: str
	name: str
	street: str
	"""Street and house number, as the AbsStr of the examples holds both."""
	city: str
	copyright: str
	"""The copyright notice of the manufacturer of the software, from the ERiC Settings."""
	postal_code: str | None = None
	bescheiddaten: bool = False
	"""Whether the Bescheiddaten are to be provided for electronic retrieval (Bescheid 1)."""

	def __post_init__(self) -> None:
		if not isinstance(self.steuernummer, str) or not STEUERNUMMER_PATTERN.fullmatch(self.steuernummer):
			raise XmlError(NOT_A_STEUERNUMMER, self.steuernummer)
		for attribute, element, label in _TEXT_FIELDS:
			length, _ = TEXTS[element]
			object.__setattr__(self, attribute, required_text(getattr(self, attribute), label, length))
		object.__setattr__(self, "postal_code", _postleitzahl(self.postal_code))


def copyright_text(value: str | None) -> str:
	"""The copyright notice as the Vorsatz writes it, which the ERiC Settings keep."""
	length, _ = TEXTS["Copyright"]
	return required_text(value, COPYRIGHT_LABEL, length)


def append_to(parent: etree._Element, kind: Datenart, vorsatz: Vorsatz) -> etree._Element:
	"""Append the Vorsatz to the root of the Nutzdaten of the Erklärung of the Datenart, as its last element."""
	if kind.unterfallart is None:
		raise ValueError(f"the Datenart {kind.name} has no Vorsatz")
	element = _append(parent, kind, "Vorsatz")
	for name, text in (
		("Unterfallart", kind.unterfallart),
		("Vorgang", VERANLAGUNG),
		("StNr", vorsatz.steuernummer),
		("Zeitraum", str(kind.year)),
		("AbsName", vorsatz.name),
		("AbsStr", vorsatz.street),
		("AbsPlz", vorsatz.postal_code),
		("AbsOrt", vorsatz.city),
		("Copyright", vorsatz.copyright),
		("OrdNrArt", STEUERNUMMER),
	):
		if text is not None:
			_append(element, kind, name, text)
	bescheid = BESCHEIDDATEN if vorsatz.bescheiddaten else NO_BESCHEIDDATEN
	_append(_append(element, kind, "Rueckuebermittlung"), kind, "Bescheid", bescheid)
	return element


def _postleitzahl(value: str | None) -> str | None:
	text = (value or "").strip()
	if not text:
		return None
	if not POSTLEITZAHL_PATTERN.fullmatch(text):
		raise XmlError(NOT_A_POSTLEITZAHL, value)
	return text


def _append(parent: etree._Element, kind: Datenart, name: str, text: str | None = None) -> etree._Element:
	child = etree.SubElement(parent, f"{{{kind.namespace}}}{name}")
	child.text = text
	return child
