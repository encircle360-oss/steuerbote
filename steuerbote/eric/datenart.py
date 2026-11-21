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

This module is pure Python and never imports Frappe.
"""

import re
from dataclasses import dataclass

from steuerbote.ustva import years

ELSTER_XML = "http://www.elster.de/elsterxml/schema/v11"
SEND_AUTH = "send-Auth"
FINANZAMT = "F"
LAENDERKUERZEL = "L"

_USTVA_VERSION = re.compile(r"UStVA_(?P<year>\d{4})")


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
	"""The Datenart of a datenartVersion; steuerbote knows UStVA_<Jahr> and ZMDO."""
	if datenart_version == ZMDO.version:
		return ZMDO
	match = _USTVA_VERSION.fullmatch(datenart_version)
	if match is None:
		raise ValueError(f"unknown datenartVersion {datenart_version!r}, expected UStVA_<year> or ZMDO")
	return ustva(int(match["year"]))
