"""The Elster envelope around the Nutzdaten, for the tests against the schema.

The envelope follows elster11_UStVA_2026_extern.xsd with the ElsterBasisSchema of the ERiC documentation
44.3.6.0 (HB for ERiC-Entwicklerhandbuch.pdf, DS for Einheitliche_Datenschnittstelle_XML_11.pdf). It is
written in UTF-8 (HB 5.3.2) and declares the namespace of ElsterXML 11 on the root alone; the Nutzdaten
declare their own (DS 2.3).

The TransferHeader names the Verfahren ElsterAnmeldung, the Datenart UStVA and the Vorgang send-Auth, the
only one the UStVA allows (HB table 8-8). A test case carries the Testmerker 700000004, which the ELSTER
server deletes „sofort nach Eingang“ (HB table 6-7); a real case carries none (HB 6.5.5). TransferTicket,
EingangsDatum, RC, SigUser and the Empfaenger of the TransferHeader are left to ERiC and the server. The
NutzdatenHeader sends to the Bundesfinanzamtsnummer, „die ersten 4 Stellen der 13-stelligen Steuernummer“
(ERiC-API-Referenz), and names the product, which must not carry the name ELSTER (ERiC licence, § 12).

This envelope is not what ERiC receives. The transmission writes only the DatenTeil with the
NutzdatenHeader and the Nutzdaten (steuerbote/eric/header.py), and EricCreateTH builds the TransferHeader,
as HB recommends: it takes „ein komplettes Elster-XML oder nur der Datenteil“ (ERiC-API-Referenz) and sets
the fields of the header itself. The whole envelope here lets the tests check the Nutzdaten against
elster11_UStVA_2026_extern.xsd as one delivery.
"""

from datetime import date

from lxml import etree

from steuerbote import __version__
from steuerbote.elster.ustva_xml import (
	Filer,
	Voranmeldung,
	build,
	elster_text,
	require_hersteller_id,
	required_text,
)

NAMESPACE = "http://www.elster.de/elsterxml/schema/v11"
DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>\n'
HEADER_VERSION = "11"
VERFAHREN = "ElsterAnmeldung"
DATENART = "UStVA"
VORGANG = "send-Auth"
TESTMERKER = "700000004"
VERSCHLUESSELUNG = "CMSEncryptedData"
KOMPRESSION = "GZIP"
PRODUCT_NAME = "Steuerbote"
COUNTRY = "Deutschland"
TRANSFER_DATENLIEFERANT_LENGTH = 256
NUTZDATEN_TICKET_LENGTH = 32
PRODUCT_TEXT_LENGTH = 50

CONTACT_LABEL = "The contact person of the Datenlieferant"
TRANSFER_DATENLIEFERANT_LABEL = "The DatenLieferant of the TransferHeader"
NUTZDATEN_TICKET_LABEL = "The NutzdatenTicket"
PRODUCT_VERSION_LABEL = "The ProduktVersion"


def to_envelope(
	filer: Filer,
	voranmeldung: Voranmeldung,
	created: date,
	*,
	hersteller_id: str,
	testmerker: bool,
	contact: str | None = None,
	produkt_version: str = __version__,
	nutzdaten_ticket: str = "1",
) -> bytes:
	"""The whole ElsterXML document of one Voranmeldung, in UTF-8.

	``nutzdaten_ticket`` tells the Nutzdatenblöcke of one delivery apart; with a single one, the schema
	suggests 1 (NutzdatenBlockTicketSType).
	"""
	hersteller_id = require_hersteller_id(hersteller_id)
	root = etree.Element(_tag("Elster"), nsmap={None: NAMESPACE})
	header = _append(root, "TransferHeader", version=HEADER_VERSION)
	_append(header, "Verfahren", VERFAHREN)
	_append(header, "DatenArt", DATENART)
	_append(header, "Vorgang", VORGANG)
	if testmerker:
		_append(header, "Testmerker", TESTMERKER)
	_append(header, "HerstellerID", hersteller_id)
	_append(header, "DatenLieferant", transfer_datenlieferant(filer, contact))
	datei = _append(header, "Datei")
	_append(datei, "Verschluesselung", VERSCHLUESSELUNG)
	_append(datei, "Kompression", KOMPRESSION)
	block = _append(_append(root, "DatenTeil"), "Nutzdatenblock")
	nutzdaten_header = _append(block, "NutzdatenHeader", version=HEADER_VERSION)
	ticket = required_text(nutzdaten_ticket, NUTZDATEN_TICKET_LABEL, NUTZDATEN_TICKET_LENGTH)
	_append(nutzdaten_header, "NutzdatenTicket", ticket)
	_append(nutzdaten_header, "Empfaenger", filer.steuernummer[:4], id="F")
	hersteller = _append(nutzdaten_header, "Hersteller")
	_append(hersteller, "ProduktName", PRODUCT_NAME)
	version = required_text(produkt_version, PRODUCT_VERSION_LABEL, PRODUCT_TEXT_LENGTH)
	_append(hersteller, "ProduktVersion", version)
	_append(block, "Nutzdaten").append(build(filer, voranmeldung, created, hersteller_id))
	etree.indent(root, space="\t")
	return DECLARATION + etree.tostring(root, encoding="unicode").encode("utf-8") + b"\n"


def transfer_datenlieferant(filer: Filer, contact: str | None = None) -> str:
	"""The DatenLieferant of the TransferHeader: free text of at most 256 characters.

	Built as DatenLieferantExternSType in headerbasis_datentypen.xsd describes it: „Lieferant (Firma);
	Ansprechpartner; Telefon; E-Mail Adresse; Ort; PLZ; Straße; Land;“. A part that is missing keeps its place.
	"""
	parts = (
		filer.name,
		elster_text(contact, CONTACT_LABEL, TRANSFER_DATENLIEFERANT_LENGTH) or "",
		filer.phone or "",
		filer.email or "",
		filer.city,
		filer.postal_code,
		filer.street,
		COUNTRY,
	)
	return required_text("; ".join(parts), TRANSFER_DATENLIEFERANT_LABEL, TRANSFER_DATENLIEFERANT_LENGTH)


def _tag(name: str) -> str:
	return f"{{{NAMESPACE}}}{name}"


def _append(parent: etree._Element, name: str, text: str | None = None, **attributes: str) -> etree._Element:
	child = etree.SubElement(parent, _tag(name), attributes)
	child.text = text
	return child
