"""The header of an ELSTER delivery and the DatenTeil that EricCreateTH completes.

An ELSTER delivery is an <Elster> element with a TransferHeader and a DatenTeil; the DatenTeil holds
one Nutzdatenblock with its NutzdatenHeader and the Nutzdaten (ERiC-Entwicklerhandbuch 44.3.6.0,
Kap. 5.1). The handbook recommends creating the TransferHeader with EricCreateTH (Kap. 5.1, p. 83 and
the sequence in Kap. 6.2.4), which takes the DatenTeil, so steuerbote writes only the DatenTeil and
leaves the TransferHeader to ERiC. EricCreateTH answers a namespace on <DatenTeil> with a parse error
and puts the ELSTER namespace on <Elster> itself (API-Referenz, EricCreateTH).

The limits of the header fields come from the ElsterBasisSchema of the documentation package:
HerstellerIDSType and NutzdatenBlockTicketSType in headerbasis_datentypen.xsd, the Hersteller element
in ndh000011.xsd and the 256 characters of DatenLieferantExternSType. For UStVA the NutzdatenHeader
names the Finanzamt in <Empfaenger id="F"> and the data are sent with send-Auth only (Entwicklerhandbuch,
Tabelle 8-8).
"""

import re
from dataclasses import dataclass
from xml.sax.saxutils import escape

from steuerbote.eric.result import ERROR, TESTMERKER, Message, Operation

ILLUSTRATION_HERSTELLER_ID = "74931"
"""The former test Hersteller-ID: ERiC rejects it with 610301202 (Entwicklerhandbuch, Kap. 6.5.3, 10.1.1)."""

HEADER_CODE = "SB-HEADER"

_DATENART_VERSION = re.compile(r"UStVA_(?P<year>\d{4})")
_DECLARATION = re.compile(r"<\?xml[^>]*\?>")


@dataclass(frozen=True, slots=True)
class EnvelopeHeader:
	"""What ERiC needs about a delivery besides the Nutzdaten."""

	hersteller_id: str
	datenlieferant: str
	produkt_name: str
	produkt_version: str
	empfaenger_finanzamt: str
	"""Bundesfinanzamtsnummer, four digits."""
	datenart_version: str
	"""Such as UStVA_2026 (Datenartversionmatrix.ods)."""
	testmerker: str | None
	nutzdaten_ticket: str


@dataclass(frozen=True, slots=True)
class Datenart:
	verfahren: str
	datenart: str
	vorgang: str
	year: int

	@property
	def plugin_library(self) -> str:
		"""The plugin file ERiC loads for the year, checkUStVA_<Jahr> in the Datenartversionmatrix."""
		return f"libcheckUStVA_{self.year}.so"


def datenart(datenart_version: str) -> Datenart:
	"""Verfahren, Datenart and Vorgang of a datenartVersion; steuerbote knows the UStVA only."""
	match = _DATENART_VERSION.fullmatch(datenart_version)
	if match is None:
		raise ValueError(f"unknown datenartVersion {datenart_version!r}, expected UStVA_<year>")
	return Datenart("ElsterAnmeldung", "UStVA", "send-Auth", int(match["year"]))


def datenteil(nutzdaten_xml: str, header: EnvelopeHeader) -> str:
	"""The DatenTeil with the NutzdatenHeader and the Nutzdaten, as EricCreateTH takes it.

	The Nutzdaten keep their own namespace; their XML declaration and byte order mark are dropped,
	because the whole delivery is one UTF-8 document.
	"""
	nutzdaten = without_declaration(nutzdaten_xml)
	return (
		"<DatenTeil><Nutzdatenblock>"
		'<NutzdatenHeader version="11">'
		f"<NutzdatenTicket>{escape(header.nutzdaten_ticket)}</NutzdatenTicket>"
		f'<Empfaenger id="F">{escape(header.empfaenger_finanzamt)}</Empfaenger>'
		f"<Hersteller><ProduktName>{escape(header.produkt_name)}</ProduktName>"
		f"<ProduktVersion>{escape(header.produkt_version)}</ProduktVersion></Hersteller>"
		"</NutzdatenHeader>"
		f"<Nutzdaten>{nutzdaten}</Nutzdaten>"
		"</Nutzdatenblock></DatenTeil>"
	)


def without_declaration(xml: str) -> str:
	"""The XML without a leading byte order mark, XML declaration and white space."""
	text = xml.lstrip("\ufeff").lstrip()
	declaration = _DECLARATION.match(text)
	return text[declaration.end() :].lstrip() if declaration else text


def problems(
	header: EnvelopeHeader, operation: Operation, *, own_hersteller_id: str | None = None
) -> tuple[Message, ...]:
	"""What is wrong with the header for the operation, before ERiC or the simulation sees it.

	ERiC needs the own Hersteller-ID for test and real cases alike (Entwicklerhandbuch, Kap. 6.5.3), so
	with own_hersteller_id, the one set up for ERiC, the header must name it. The simulation runs without.
	"""
	found = []

	def refuse(field: str, text: str) -> None:
		found.append(Message(HEADER_CODE, text, ERROR, field))

	expected_testmerker = TESTMERKER if operation is Operation.TEST_SEND else None
	if operation is not Operation.VALIDATE and header.testmerker != expected_testmerker:
		if expected_testmerker:
			refuse("Testmerker", f"Ein Testsenden braucht den Testmerker {TESTMERKER}.")
		else:
			refuse("Testmerker", "Ein echtes Senden darf keinen Testmerker tragen.")
	if own_hersteller_id == ILLUSTRATION_HERSTELLER_ID:
		refuse(
			"HerstellerID",
			f"Die Hersteller-ID {ILLUSTRATION_HERSTELLER_ID} dient nur der Illustration und ist gesperrt. "
			"Nötig ist die eigene Hersteller-ID, auch für Testfälle.",
		)
	elif own_hersteller_id is not None and not re.fullmatch(r"\d{5}", own_hersteller_id):
		refuse("HerstellerID", "ERiC braucht die eigene Hersteller-ID aus fünf Ziffern, auch zum Prüfen.")
	elif own_hersteller_id is not None and header.hersteller_id != own_hersteller_id:
		refuse(
			"HerstellerID",
			f"Die Daten nennen die Hersteller-ID {header.hersteller_id}, eingerichtet ist {own_hersteller_id}.",
		)
	if not re.fullmatch(r"\d{4}", header.empfaenger_finanzamt):
		refuse("Empfaenger", "Die Bundesfinanzamtsnummer besteht aus vier Ziffern.")
	if not 1 <= len(header.nutzdaten_ticket) <= 32:
		refuse("NutzdatenTicket", "Das NutzdatenTicket hat 1 bis 32 Zeichen.")
	if not 1 <= len(header.produkt_name) <= 50 or "elster" in header.produkt_name.casefold():
		refuse("ProduktName", "Der Produktname hat 1 bis 50 Zeichen und enthält nicht „ELSTER“.")
	if not 1 <= len(header.produkt_version) <= 50:
		refuse("ProduktVersion", "Die Produktversion hat 1 bis 50 Zeichen.")
	if not header.datenlieferant.strip() or len(header.datenlieferant) > 256:
		refuse("DatenLieferant", "Der Datenlieferant ist angegeben und hat höchstens 256 Zeichen.")
	if not _DATENART_VERSION.fullmatch(header.datenart_version):
		refuse("datenartVersion", f"Die datenartVersion {header.datenart_version!r} ist unbekannt.")
	return tuple(found)
