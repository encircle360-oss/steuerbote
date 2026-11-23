"""The E-Bilanz as ELSTER XML: the Nutzdaten of the Datenart Bilanz around the XBRL instance of steuerbote/ebilanz.

Sources are the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/): the schema
Datenarten/ElsterBilanz/Bilanz/Schema/ebilanz_000002.xsd, the ERiC-Entwicklerhandbuch (HB) and the Technischer
Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025 („Leitfaden“).

The Nutzdaten are the element EBilanz of ebilanz_000002.xsd in the version 2, „Derzeit ist Version 2 dieser
Schnittstelle im Einsatz“ (E-Bilanz_Taxonomie_6_9.pdf, Kap. 2), holding the stichtag „im Format YYYYMMTT“ and the
XBRL instance, xbrli:xbrl. The stichtag is the Bilanzstichtag of the GCD: „Das unter „Bilanzstichtag“
[genInfo.report.period.balSheetClosingDate] angegebene Datum muss mit dem Eintrag im Element „stichtag“ unter
„Nutzdaten/E-Bilanz“ übereinstimmen.“ (Leitfaden B.2.2; rule 170205022). The Datenart is Bilanz_<version> of the
taxonomy (steuerbote.eric.datenart.bilanz), which ERiC checks with its plugin and no schema of the Nutzdaten (HB
Tabelle 9-20). The delivery goes to the Finanzamt of the Steuernummer, „die aus der Steuernummer des Unternehmens
abgeleitete Bundesfinanzamtsnummer [muss] mit der Bundesfinanzamtsnummer im ELSTER-Header übereinstimmen“ (Leitfaden
B.2.1 a; rules 170205001 and 170205002), and its NutzdatenHeader names the DatenLieferant in the ten parts of
steuerbote.eric.header.nutzdaten_datenlieferant() (HB Kap. 9.7.1).

Size. „Bilanz_6.9 ... max. unkomprimierte Größe 100 MiB“ of the Eingangsdatensatz (HB Kap. 5.3.8.1, Tabelle 5-7),
which the headers fill besides the Nutzdaten: the Nutzdaten take at most that less 64 KiB, far more than the
TransferHeader and the NutzdatenHeader take, and a larger E-Bilanz is refused with an XmlError.

envelope() writes the whole ElsterXML document for the tests against ebilanz_000002.xsd and for „XML exportieren“;
the transmission sends to_nutzdaten() in the DatenTeil of steuerbote/eric/header.py, whose TransferHeader EricCreateTH
writes. This module is pure Python with lxml and never imports Frappe.
"""

from lxml import etree

from steuerbote import __version__
from steuerbote.ebilanz.instance import EBilanz
from steuerbote.elster.envelope import envelope_for
from steuerbote.elster.ustva_xml import XmlError, serialized
from steuerbote.eric.datenart import EBILANZ_NAMESPACE, Datenart
from steuerbote.xbrl.versions import version_of

MAX_EINGANGSDATENSATZ = 100 * 1024 * 1024
"""100 MiB of 1.048.576 bytes each (HB Kap. 5.3.8.1, footnote 37)."""
HEADER_RESERVE = 64 * 1024
MAX_NUTZDATEN_BYTES = MAX_EINGANGSDATENSATZ - HEADER_RESERVE

TOO_LARGE = "The E-Bilanz has {0} bytes; ERiC takes at most {1} bytes of Nutzdaten."
MESSAGES = (TOO_LARGE,)


def datenart(ebilanz: EBilanz) -> Datenart:
	"""The Datenart of the taxonomy of the E-Bilanz, such as Bilanz_6.9."""
	return version_of(ebilanz.structure.taxonomy.version).datenart


def nutzdaten(ebilanz: EBilanz) -> etree._Element:
	"""The element EBilanz of ebilanz_000002.xsd: the Bilanzstichtag and the instance of the E-Bilanz."""
	kind = datenart(ebilanz)
	root = etree.Element(
		f"{{{EBILANZ_NAMESPACE}}}{kind.root}", nsmap={"ebilanz": EBILANZ_NAMESPACE}, version=kind.root_version
	)
	closing = ebilanz.structure.case.periods.balance_sheet_date
	etree.SubElement(root, f"{{{EBILANZ_NAMESPACE}}}stichtag").text = f"{closing:%Y%m%d}"
	root.append(ebilanz.instance())
	return root


def to_nutzdaten(ebilanz: EBilanz) -> str:
	"""The Nutzdaten as text, as the DatenTeil of the transmission takes them; refused above the size ERiC takes."""
	return _within_the_size(serialized(nutzdaten(ebilanz)))


def envelope(
	ebilanz: EBilanz,
	*,
	hersteller_id: str,
	testmerker: bool,
	datenlieferant: str,
	nutzdaten_datenlieferant: str,
	produkt_version: str = __version__,
	nutzdaten_ticket: str = "1",
) -> bytes:
	"""The whole ElsterXML document of the E-Bilanz, in UTF-8: ``datenlieferant`` is that of the TransferHeader,
	``nutzdaten_datenlieferant`` the ten parts of the NutzdatenHeader."""
	root = nutzdaten(ebilanz)
	_within_the_size(serialized(root))
	return envelope_for(
		root,
		datenart(ebilanz),
		empfaenger=ebilanz.master.finanzamt,
		hersteller_id=hersteller_id,
		testmerker=testmerker,
		datenlieferant=datenlieferant,
		nutzdaten_datenlieferant=nutzdaten_datenlieferant,
		produkt_version=produkt_version,
		nutzdaten_ticket=nutzdaten_ticket,
	)


def _within_the_size(text: str) -> str:
	size = len(text.encode("utf-8"))
	if size > MAX_NUTZDATEN_BYTES:
		raise XmlError(TOO_LARGE, size, MAX_NUTZDATEN_BYTES)
	return text
