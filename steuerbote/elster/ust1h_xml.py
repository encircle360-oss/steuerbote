"""Form USt 1 H as ELSTER XML for ERiC: the Antrag auf Dauerfristverlängerung and the Anmeldung der
Sondervorauszahlung in the element Anmeldungssteuern of the schema of its year.

Sources are the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/): HB for
ERiC-Entwicklerhandbuch.pdf, JD for Jahresdokumentation_UStVA_2026.ods with its sheets and its rules by
Fehlercode, the schema UStVA-2026.xsd and Datenartversionmatrix.ods; and the ELSTER help "Benutzeranleitung zum
Hochladen von Formulardaten" (https://www.elster.de/eportal/helpGlobal?themaGlobal=ustva_upload).

Form USt 1 H belongs to the Datenart UStVA: HB table 2-13 lists the "Umsatzsteuer-Dauerfristverlängerung
(UStDV)" and the "Umsatzsteuer-Dauerfristverlängerung mit Sondervorauszahlung (UStSV)" under it, and the
Datenartversionmatrix gives UStVA_<Jahr> with the plugin checkUStVA_<Jahr> „Mit UStDV und UStSV“. So the form
goes in the schema and namespace of the Voranmeldung, as one of its two contexts in the Steuerfall, and a filing
holds exactly one of the three contexts (JD 110085099):

- Dauerfristverlaengerung, the Antrag of a company that files quarterly. „Soll eine Dauerfristverlängerung ohne
  Sondervorauszahlung abgegeben werden, ist nur Kz 09 zu füllen.“ (HB 8.5.1)
- Umsatzsteuersondervorauszahlung of a company that files monthly: „Die Umsatzsteuer Sondervorauszahlung wird auf
  dem gleichen Formular wie die Dauerfristverlängerung angemeldet.“ (HB 8.5.1)

Neither context has a field for the Antrag. The sheet "Anmeldungssteuern - Felder" gives the context
Umsatzsteuersondervorauszahlung Jahr, Steuernummer, WIdNr, Kz09, Kz10, Kz26, Kz29, Kz38, Kz500 and
Kz500_Begruendung, and the sheet "Anmeldungssteuern - Texte" prints section I "Antrag auf Dauerfristverlängerung"
with its sentence „Ich beantrage die Fristen für die Übermittlung der Umsatzsteuer-Voranmeldung und für die
Entrichtung der Umsatzsteuer-Vorauszahlungen um einen Monat zu verlängern.“ (B 1110010) above Kz 09 of both
contexts, line 6. The context is the Antrag, for a monthly filer together with the Anmeldung, which § 48 Absatz 1
Satz 4 UStDV puts into the Antrag; in a later year the section is „gegenstandslos, wenn Dauerfristverlängerung
bereits gewährt worden ist“ (JD, B 1110 EZ 1), and the same context files the Anmeldung alone.

Only ERiC takes the form. Mein ELSTER uploads form data „für alle angebotenen Jahresversionen der
Umsatzsteuer-Voranmeldung (UStVA) und der Mitteilung nach § 146a Abs. 4 AO“ (help) and not for form USt 1 H, so
there is no file for Mein ELSTER. ``to_nutzdaten`` writes the Nutzdaten in UTF-8 (HB 5.3.2), with the
Erstellungsdatum and the DatenLieferant of the Voranmeldung (ustva_xml.py), for steuerbote/eric/header.py to put
into the DatenTeil.

The rules (JD, sheet "Anmeldungssteuern - Regeln"):

- One context per file (110085099), without Unternehmer, Berater or Mandant, so that Kz 09 holds the Hersteller-ID
  alone (110085046); from 2027 its format takes nothing else (Jahresdokumentation_UStVA_2027.ods of the beta ERiC
  45.1.5.0, which drops that rule).
- Jahr is the year of the schema (110085130, 110085131) and required (110085048); the Steuernummer of the filer is
  required (110085044), the Wirtschafts-Identifikationsnummer is written when the filer has one (11085154).
- Kz 09 carries the Hersteller-ID in both contexts (110085045), checked as for the Voranmeldung.
- Kz 38 is required in the Anmeldung, 0 if need be (110085143), in whole euros without sign (Formatkennzeichen U);
  Kz 29 goes only with Kz 10 (11085150); Kz 500 and its Begründung go together (11085137). dauerfrist.form.Ust1H
  keeps these, and the Begründung takes the character set of ELSTER here, as in the Voranmeldung (charset.py).
"""

from datetime import date

from lxml import etree

from steuerbote.dauerfrist import Ust1H, layout_for
from steuerbote.elster.ustva_xml import (
	Filer,
	anmeldungssteuern,
	context,
	require_hersteller_id,
	schema_for,
	serialized,
	supplementary_details,
)


def to_nutzdaten(filer: Filer, ust1h: Ust1H, created: date, hersteller_id: str) -> str:
	"""The Nutzdaten for ERiC: form USt 1 H with the Hersteller-ID in Kz 09, created on ``created``, as text."""
	return serialized(build(filer, ust1h, created, hersteller_id))


def build(filer: Filer, ust1h: Ust1H, created: date, hersteller_id: str) -> etree._Element:
	"""The element Anmeldungssteuern of the year of the form, with its one context."""
	schema = schema_for(ust1h.year)
	texts = {
		**ust1h.texts(),
		"Jahr": str(schema.year),
		"Steuernummer": filer.steuernummer,
		"WIdNr": filer.wid_nr,
		"Kz09": require_hersteller_id(hersteller_id),
		**supplementary_details(ust1h.supplementary_code, ust1h.begruendung),
	}
	root, steuerfall = anmeldungssteuern(filer, schema, created)
	context(steuerfall, schema, ust1h.context.value, texts, layout_for(ust1h.year).elements(ust1h.context))
	return root
