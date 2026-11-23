"""The Datenarten steuerbote sends through ERiC, each described in this one place.

Sources are the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/), cited as HB for
ERiC-Entwicklerhandbuch.pdf and DVM for Datenartversionmatrix.ods. Besides its Nutzdaten a delivery needs, by its
Datenart:

- the Verfahren, the DatenArt and the Vorgang that EricCreateTH writes into the TransferHeader (HB Kap. 5.1), as the
  table of the properties of each Datenart gives them;
- the datenartVersion that EricBearbeiteVorgang takes and the plugin ERiC checks it with: „Mit dem Verfahren, der
  Datenart und gegebenenfalls dem unterstützten Jahr (AZ) werden aus der Datenartversionmatrix der Parameter
  datenartVersion für EricBearbeiteVorgang() und das Plugin bestimmt, das zu installieren ist.“ (HB Kap. 8.1), the
  plugin under Linux as lib<plugin>.so (HB Kap. 3.1.6.1);
- the recipient in <Empfaenger> of the NutzdatenHeader, with the attribute id F for a Bundesfinanzamtsnummer or L
  for a Länderkürzel (EmpfaengerIDSType in ElsterBasisSchema/Schema/headerbasis_datentypen.xsd);
- the schema of the Nutzdaten below the directory Dokumentation, with the element and the version they begin with.

The Umsatzsteuer-Voranmeldung and form USt 1 H, which HB Tabelle 2-13 holds under the UStVA, are the Datenart UStVA
of the Verfahren ElsterAnmeldung, sent with send-Auth only, „send-NoSig [...] Nein“, to the Finanzamt in
<Empfaenger id="F"> (HB Tabelle 8-8), whose Bundesfinanzamtsnummer the transmission takes from the Steuernummer.
ELSTER takes them only in the datenartVersion of their year, UStVA_<Jahr> with the plugin checkUStVA_<Jahr> (DVM), as
steuerbote/ustva/years.py names both, and their schema and namespace carry the year as well
(Datenarten/ElsterAnmeldung/UStVA/Schema/<Jahr>/UStVA-<Jahr>.xsd).

The Zusammenfassende Meldung is the Datenart ZMDO of the Verfahren ElsterExtern, sent with send-Auth, „send-NoSig
[...] Nein“ (HB Tabelle 8-28), to <Empfaenger id="L">BF</Empfaenger> (HB Tabelle 8-28; Jahresdokumentation_ZMDO_2.ods,
EmpfaengerTyp L and EmpfaengerName BF for the NutzdatenHeader version 11), BF being the „Bundesamt für Finanzen“ of
BundeslandSType in headerbasis_datentypen.xsd, today the BZSt. Its AZ is „Unabhängig“ (HB Tabelle 2-13): one
datenartVersion and one plugin for every year, ZMDO and checkZMDO (DVM, row ElsterExtern/ZMDO without Jahr /
Version), and the year of the Meldezeitraum is a field of the Nutzdaten. They are the element zm of zm_000005.xsd
with the version 000005 („Konstanter Wert“), a schema without a namespace that elster11_Zm_000005_extern.xsd
includes into the one of ElsterXML 11 (Datenarten/ElsterExtern/ZMDO/Schema/5).

The Umsatzsteuererklärung, the Körperschaftsteuererklärung and the Gewerbesteuererklärung are the Datenarten USt,
KSt and GewSt of the Verfahren ElsterErklaerung, sent with send-Auth only, send-NoSig „Nur bis einschließlich VZ
2016 möglich“ or „Nein“, to the Finanzamt in <Empfaenger id="F"> (HB Tabellen 7-13, 7-15 and 7-9). Their
datenartVersion and plugin carry the year (VZ or EZ): USt_<Jahr> with checkUSt_<Jahr>, KSt_30_<Jahr> with
checkKSt_<Jahr> for the Unterfallart 30, GewSt_<Jahr> with checkGewSt_<Jahr> (DVM). Their Nutzdaten are the
element E50, E30 or E20 in the version of the year, in the namespace the Jahresdokumentation of the year names
(sheet „Allg. Information“), with the Vorsatz of the Unterfallart 50, 30 or 20 (HB Tabelle 2-12; sheet „Vorsatz -
Felder“), which steuerbote/elster/vorsatz.py writes. After an authenticated send ERiC prints a
Freizeichnungsdokument for them, not an Übertragungsprotokoll: „Für Erklärungssteuern wird bei authentifizierter
Übermittlung ein sogenanntes Freizeichnungsdokument erstellt“ (HB Kap. 5.1.4.3) and „Für Erklärungssteuern wird
kein Übertragungsprotokoll erstellt“ (HB Kap. 5.1.4.4). The UStVA and ZMDO, which are no Erklärungssteuern, keep
their Übertragungsprotokoll.

The E-Bilanz is the Datenart Bilanz of the Verfahren ElsterBilanz, sent with send-Auth only to the Finanzamt in
<Empfaenger id="F"> (HB Tabelle 9-20). Its datenartVersion and plugin carry the HGB-Taxonomie, not a year: Bilanz_6.9
with checkBilanz_6_9 for „HGB-Taxonomie 6.9“ (DVM). Its Nutzdaten are the element EBilanz of ebilanz_000002.xsd with
the stichtag and the XBRL instance, in the version 2: „Derzeit ist Version 2 dieser Schnittstelle im Einsatz“
(E-Bilanz_Taxonomie_6_9.pdf, Kap. 2). ERiC checks no schema of them, „Nutzdatenschemavalidierung: Nein“ (HB Tabelle
9-20), prints no copy of the data but only an Übertragungsprotokoll, and refuses the Hinweisprüfung without
Validiere (HB Kap. 9.7.1). So Prüfen is EBV-8, Hinweisprüfung and Validiere without a preview (HB Tabelle 6-2), and
the NutzdatenHeader names the DatenLieferant in the ten parts the Übertragungsprotokoll prints (HB Kap. 9.7.1).

This module is pure Python and never imports Frappe.
"""

import re
from dataclasses import dataclass

from steuerbote.ustva import years

ELSTER_XML = "http://www.elster.de/elsterxml/schema/v11"
SEND_AUTH = "send-Auth"
FINANZAMT = "F"
LAENDERKUERZEL = "L"
ELSTER_ERKLAERUNG = "ElsterErklaerung"
ELSTER_BILANZ = "ElsterBilanz"
EBILANZ_NAMESPACE = "http://rzf.fin-nrw.de/RMS/EBilanz/2016/XMLSchema"
UEBERTRAGUNGSPROTOKOLL = "Übertragungsprotokoll"
FREIZEICHNUNGSDOKUMENT = "Freizeichnungsdokument"

_USTVA_VERSION = re.compile(r"UStVA_(?P<year>\d{4})")
_ERKLAERUNG_VERSION = re.compile(r"(?P<prefix>USt|KSt_30|GewSt)_(?P<year>\d{4})")
_BILANZ_VERSION = re.compile(r"Bilanz_(?P<taxonomy>.*)")
_TAXONOMY = re.compile(r"(?P<major>\d+)\.(?P<minor>\d+)")


@dataclass(frozen=True, slots=True)
class Datenart:
	"""What ERiC and the envelope of a delivery need to know about its Datenart."""

	name: str
	"""The DatenArt of the TransferHeader, such as UStVA."""
	version: str
	"""The datenartVersion of EricBearbeiteVorgang, such as UStVA_2026 (Datenartversionmatrix.ods)."""
	verfahren: str
	"""The Verfahren of the TransferHeader, such as ElsterAnmeldung."""
	vorgang: str
	"""The Vorgang of the TransferHeader."""
	recipient_id: str
	"""The attribute id of <Empfaenger> in the NutzdatenHeader: F for a Bundesfinanzamtsnummer, L for a
	Länderkürzel."""
	recipient: str | None
	"""The recipient every delivery of the Datenart goes to, None where it goes to the Finanzamt of the filer."""
	plugin: str
	"""The plugin of ERiC that checks the datenartVersion, such as checkUStVA_2026."""
	schema: str
	"""The XSD of the Nutzdaten, below the directory Dokumentation of the ERiC documentation."""
	namespace: str
	"""The namespace of the Nutzdaten."""
	root: str
	"""The element the Nutzdaten begin with."""
	root_version: str
	"""The attribute version of that element, which its schema fixes."""
	year: int | None
	"""The year of a Datenart that ELSTER takes per year, None for one without a year."""
	printout: str = UEBERTRAGUNGSPROTOKOLL
	"""What ERiC prints after an accepted send-Auth: the Übertragungsprotokoll, or the Freizeichnungsdokument of an
	Erklärung (HB Kap. 5.1.4.3 and 5.1.4.4)."""
	preview_on_check: bool = True
	"""Whether Prüfen prints a preview with the Hinweisprüfung and the validation (EBV-9 of HB Tabelle 6-2), or runs
	them without one (EBV-8)."""
	nutzdaten_datenlieferant: bool = False
	"""Whether the NutzdatenHeader names the DatenLieferant, which steuerbote.eric.header checks for its ten parts."""
	unterfallart: str | None = None
	"""The Unterfallart of the Vorsatz of an Erklärung (HB Tabelle 2-12), None for a Datenart without a Vorsatz."""
	taxonomy: str | None = None
	"""The HGB-Taxonomie of the E-Bilanz, such as 6.9, None for any other Datenart."""

	@property
	def plugin_library(self) -> str:
		"""The file of the plugin under Linux."""
		return f"lib{self.plugin}.so"


def ustva(year: int) -> Datenart:
	"""The Datenart UStVA of the year: the Voranmeldung and form USt 1 H."""
	return Datenart(
		name="UStVA",
		version=years.datenart_version(year),
		verfahren="ElsterAnmeldung",
		vorgang=SEND_AUTH,
		recipient_id=FINANZAMT,
		recipient=None,
		plugin=years.plugin(year),
		schema=f"Datenarten/ElsterAnmeldung/UStVA/Schema/{year}/UStVA-{year}.xsd",
		namespace=f"http://finkonsens.de/elster/elsteranmeldung/ustva/v{year}",
		root="Anmeldungssteuern",
		root_version=str(year),
		year=year,
	)


def ust(year: int) -> Datenart:
	"""The Datenart USt of the year: the Umsatzsteuererklärung, Unterfallart 50."""
	return _erklaerung("USt", "USt", "E50", "50", year)


def kst(year: int) -> Datenart:
	"""The Datenart KSt of the year in the datenartVersion of the Unterfallart 30: the Körperschaftsteuererklärung."""
	return _erklaerung("KSt", "KSt_30", "E30", "30", year)


def gewst(year: int) -> Datenart:
	"""The Datenart GewSt of the year: the Gewerbesteuererklärung, Unterfallart 20."""
	return _erklaerung("GewSt", "GewSt", "E20", "20", year)


def _erklaerung(name: str, prefix: str, root: str, unterfallart: str, year: int) -> Datenart:
	"""An Erklärung of the year, whose plugin is check<name>_<Jahr> also where the datenartVersion names the
	Unterfallart (DVM: KSt_30_<Jahr> with checkKSt_<Jahr>)."""
	return Datenart(
		name=name,
		version=f"{prefix}_{year}",
		verfahren=ELSTER_ERKLAERUNG,
		vorgang=SEND_AUTH,
		recipient_id=FINANZAMT,
		recipient=None,
		plugin=f"check{name}_{year}",
		schema=f"Datenarten/{ELSTER_ERKLAERUNG}/{name}/Schema/{year}/{root}-{year}.xsd",
		namespace=f"http://finkonsens.de/elster/elstererklaerung/{name.lower()}/{root.lower()}/v{year}",
		root=root,
		root_version=str(year),
		year=year,
		printout=FREIZEICHNUNGSDOKUMENT,
		unterfallart=unterfallart,
	)


_ERKLAERUNGEN = {"USt": ust, "KSt_30": kst, "GewSt": gewst}


def bilanz(taxonomy: str) -> Datenart:
	"""The Datenart Bilanz of the HGB-Taxonomie, such as 6.9: the E-Bilanz."""
	match = _TAXONOMY.fullmatch(taxonomy)
	if match is None:
		raise ValueError(f"{taxonomy!r} is no HGB-Taxonomie <major>.<minor>")
	return Datenart(
		name="Bilanz",
		version=f"Bilanz_{taxonomy}",
		verfahren=ELSTER_BILANZ,
		vorgang=SEND_AUTH,
		recipient_id=FINANZAMT,
		recipient=None,
		plugin=f"checkBilanz_{match['major']}_{match['minor']}",
		schema=f"Datenarten/{ELSTER_BILANZ}/Bilanz/Schema/ebilanz_000002.xsd",
		namespace=EBILANZ_NAMESPACE,
		root="EBilanz",
		root_version="2",
		year=None,
		preview_on_check=False,
		nutzdaten_datenlieferant=True,
		taxonomy=taxonomy,
	)


ZMDO = Datenart(
	name="ZMDO",
	version="ZMDO",
	verfahren="ElsterExtern",
	vorgang=SEND_AUTH,
	recipient_id=LAENDERKUERZEL,
	recipient="BF",
	plugin="checkZMDO",
	schema="Datenarten/ElsterExtern/ZMDO/Schema/5/zm_000005.xsd",
	namespace=ELSTER_XML,
	root="zm",
	root_version="000005",
	year=None,
)
"""The Zusammenfassende Meldung."""


def of_version(datenart_version: str) -> Datenart:
	"""The Datenart of a datenartVersion; steuerbote knows UStVA_<Jahr>, ZMDO, USt_<Jahr>, KSt_30_<Jahr>,
	GewSt_<Jahr> and Bilanz_<Taxonomie>."""
	if datenart_version == ZMDO.version:
		return ZMDO
	if match := _USTVA_VERSION.fullmatch(datenart_version):
		return ustva(int(match["year"]))
	if match := _ERKLAERUNG_VERSION.fullmatch(datenart_version):
		return _ERKLAERUNGEN[match["prefix"]](int(match["year"]))
	if match := _BILANZ_VERSION.fullmatch(datenart_version):
		return bilanz(match["taxonomy"])
	raise ValueError(
		f"unknown datenartVersion {datenart_version!r}, expected UStVA_<year>, ZMDO, USt_<year>, KSt_30_<year>, "
		"GewSt_<year> or Bilanz_<taxonomy>"
	)
