"""The header of an ELSTER delivery and the DatenTeil that EricCreateTH completes.

An ELSTER delivery is an <Elster> element with a TransferHeader and a DatenTeil; the DatenTeil holds
one Nutzdatenblock with its NutzdatenHeader and the Nutzdaten (ERiC-Entwicklerhandbuch 44.3.6.0,
Kap. 5.1). The handbook recommends creating the TransferHeader with EricCreateTH (Kap. 5.1, p. 83 and
the sequence in Kap. 6.2.4), which takes the DatenTeil, so steuerbote writes only the DatenTeil and
leaves the TransferHeader to ERiC. EricCreateTH answers a namespace on <DatenTeil> with a parse error
and puts the ELSTER namespace on <Elster> itself (API-Referenz, EricCreateTH).

The limits of the header fields come from the ElsterBasisSchema of the documentation package:
HerstellerIDSType and NutzdatenBlockTicketSType in headerbasis_datentypen.xsd, the Hersteller element
in ndh000011.xsd and the 256 characters of DatenLieferantExternSType. The datenartVersion names the Datenart
of the delivery (steuerbote.eric.datenart), and the Datenart where the NutzdatenHeader sends it: the UStVA to
the Finanzamt in <Empfaenger id="F"> (Entwicklerhandbuch, Tabelle 8-8), ZMDO to <Empfaenger id="L">BF</Empfaenger>
(Tabelle 8-28).

ndh000011.xsd lets the NutzdatenHeader name a DatenLieferant after the Hersteller, of at most 256 characters
(DatenLieferantInternSType). The E-Bilanz needs it: „Damit beim PDF-Druck des Übertragungsprotokolls der Name des
Erstellers, seine Adresse und weitere Angaben korrekt gedruckt werden, muss im <NutzdatenHeader>-Block der Inhalt
des Elements <DatenLieferant> das folgende Format erfüllen und darf die max. Länge von 256 Zeichen nicht
überschreiten. [...] Name des Erstellers; Strasse; Hausnummer; Hausnummerzusatz; Adresszusatz; PLZ; Ort; Land;
Telefon; E-Mail-Adresse“ (Entwicklerhandbuch, Kap. 9.7.1). nutzdaten_datenlieferant writes the ten parts as the
example there does, separated by a semicolon and a blank; the blanks are printed as they are.
"""

import re
from dataclasses import dataclass
from xml.sax.saxutils import escape

from steuerbote.eric.datenart import Datenart, of_version
from steuerbote.eric.result import ERROR, TESTMERKER, Message, Operation

ILLUSTRATION_HERSTELLER_ID = "74931"
"""The former test Hersteller-ID: ERiC rejects it with 610301202 (Entwicklerhandbuch, Kap. 6.5.3, 10.1.1)."""

HEADER_CODE = "SB-HEADER"
NUTZDATEN_DATENLIEFERANT_FIELD = "NutzdatenHeader/DatenLieferant"
DATENLIEFERANT_LENGTH = 256
DATENLIEFERANT_PARTS = 10
"""Name des Erstellers, Strasse, Hausnummer, Hausnummerzusatz, Adresszusatz, PLZ, Ort, Land, Telefon and
E-Mail-Adresse (Entwicklerhandbuch, Kap. 9.7.1)."""
DATENLIEFERANT_SEPARATOR = "; "

_DECLARATION = re.compile(r"<\?xml[^>]*\?>")


@dataclass(frozen=True, slots=True)
class EnvelopeHeader:
	"""What ERiC needs about a delivery besides the Nutzdaten."""

	hersteller_id: str
	datenlieferant: str
	produkt_name: str
	produkt_version: str
	empfaenger: str
	"""The recipient in <Empfaenger> of the NutzdatenHeader: the Bundesfinanzamtsnummer of four digits for a
	Datenart that goes to the Finanzamt, such as the UStVA, else the recipient of the Datenart, BF for ZMDO."""
	datenart_version: str
	"""Such as UStVA_2026 or ZMDO (Datenartversionmatrix.ods), which names the Datenart of the delivery."""
	testmerker: str | None
	nutzdaten_ticket: str
	nutzdaten_datenlieferant: str | None = None
	"""The DatenLieferant of the NutzdatenHeader, which the E-Bilanz needs in the ten parts of
	nutzdaten_datenlieferant; None writes none."""


def datenteil(nutzdaten_xml: str, header: EnvelopeHeader) -> str:
	"""The DatenTeil with the NutzdatenHeader and the Nutzdaten, as EricCreateTH takes it.

	The Nutzdaten keep their own namespace; their XML declaration and byte order mark are dropped,
	because the whole delivery is one UTF-8 document.
	"""
	nutzdaten = without_declaration(nutzdaten_xml)
	kind = of_version(header.datenart_version)
	datenlieferant = (
		""
		if header.nutzdaten_datenlieferant is None
		else f"<DatenLieferant>{escape(header.nutzdaten_datenlieferant)}</DatenLieferant>"
	)
	return (
		"<DatenTeil><Nutzdatenblock>"
		'<NutzdatenHeader version="11">'
		f"<NutzdatenTicket>{escape(header.nutzdaten_ticket)}</NutzdatenTicket>"
		f'<Empfaenger id="{kind.recipient_id}">{escape(header.empfaenger)}</Empfaenger>'
		f"<Hersteller><ProduktName>{escape(header.produkt_name)}</ProduktName>"
		f"<ProduktVersion>{escape(header.produkt_version)}</ProduktVersion></Hersteller>"
		f"{datenlieferant}"
		"</NutzdatenHeader>"
		f"<Nutzdaten>{nutzdaten}</Nutzdaten>"
		"</Nutzdatenblock></DatenTeil>"
	)


def nutzdaten_datenlieferant(
	*,
	name: str,
	street: str = "",
	house_number: str = "",
	house_number_suffix: str = "",
	address_supplement: str = "",
	postal_code: str = "",
	city: str = "",
	country: str = "",
	phone: str = "",
	email: str = "",
) -> str:
	"""The DatenLieferant of the NutzdatenHeader of an E-Bilanz: its ten parts in their order, each without blanks at
	either end; a part that is missing keeps its place. The whole ends without a blank, which ERiC 44.3.6.0 refuses
	(„nachfolgendesBlank“, validation of Bilanz_6.9), so missing last parts end in a bare semicolon. problems refuses
	parts that do not come out as ten."""
	parts = (
		name,
		street,
		house_number,
		house_number_suffix,
		address_supplement,
		postal_code,
		city,
		country,
		phone,
		email,
	)
	return DATENLIEFERANT_SEPARATOR.join(part.strip() for part in parts).rstrip()


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
	kind = _datenart(header.datenart_version)
	if kind is not None:
		recipient = _recipient_problem(kind, header.empfaenger)
		if recipient:
			refuse("Empfaenger", recipient)
		datenlieferant = _datenlieferant_problem(kind, header.nutzdaten_datenlieferant)
		if datenlieferant:
			refuse(NUTZDATEN_DATENLIEFERANT_FIELD, datenlieferant)
	if not 1 <= len(header.nutzdaten_ticket) <= 32:
		refuse("NutzdatenTicket", "Das NutzdatenTicket hat 1 bis 32 Zeichen.")
	if not 1 <= len(header.produkt_name) <= 50 or "elster" in header.produkt_name.casefold():
		refuse("ProduktName", "Der Produktname hat 1 bis 50 Zeichen und enthält nicht „ELSTER“.")
	if not 1 <= len(header.produkt_version) <= 50:
		refuse("ProduktVersion", "Die Produktversion hat 1 bis 50 Zeichen.")
	if not header.datenlieferant.strip() or len(header.datenlieferant) > 256:
		refuse("DatenLieferant", "Der Datenlieferant ist angegeben und hat höchstens 256 Zeichen.")
	if kind is None:
		refuse("datenartVersion", f"Die datenartVersion {header.datenart_version!r} ist unbekannt.")
	return tuple(found)


def _datenart(datenart_version: str) -> Datenart | None:
	try:
		return of_version(datenart_version)
	except ValueError:
		return None


def _datenlieferant_problem(kind: Datenart, datenlieferant: str | None) -> str | None:
	if datenlieferant is not None and len(datenlieferant) > DATENLIEFERANT_LENGTH:
		return "Der Datenlieferant im NutzdatenHeader hat höchstens 256 Zeichen."
	if datenlieferant and datenlieferant != datenlieferant.rstrip():
		return "Der Datenlieferant im NutzdatenHeader endet nicht mit einem Leerzeichen."
	if not kind.nutzdaten_datenlieferant:
		return None
	parts = (datenlieferant or "").split(";")
	if len(parts) != DATENLIEFERANT_PARTS or not parts[0].strip():
		return (
			f"Die Datenart {kind.name} braucht im NutzdatenHeader den Datenlieferanten aus zehn Teilen, durch "
			"Semikolon getrennt: Name des Erstellers; Straße; Hausnummer; Hausnummerzusatz; Adresszusatz; PLZ; Ort; "
			"Land; Telefon; E-Mail-Adresse, mindestens mit dem Namen und ohne Semikolon in einer Angabe "
			"(ERiC-Entwicklerhandbuch, Kap. 9.7.1)."
		)
	return None


def _recipient_problem(kind: Datenart, empfaenger: str) -> str | None:
	if kind.recipient is None:
		return (
			None
			if re.fullmatch(r"\d{4}", empfaenger)
			else "Die Bundesfinanzamtsnummer besteht aus vier Ziffern."
		)
	if empfaenger != kind.recipient:
		return f"Die Datenart {kind.name} geht an den Empfänger {kind.recipient}, nicht an {empfaenger!r}."
	return None
