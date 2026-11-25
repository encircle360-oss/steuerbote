"""The Vordrucke of the Gewerbesteuererklärung as ELSTER takes them, per EZ, and the fields of the lines that
steuerbote.gewst.chain computes.

Source is the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/), cited as JD for
Jahresdokumentation_E20_2025.ods (Versionslabel 11.0) with its sheets „Allg. Information“, „<Vordruck> - Felder“,
„<Vordruck> - Kennzahlen“, „<Vordruck> - Regeln“ and „Benutzerdefinierte Typen“, and the schema E20-2025.xsd. ERiC
44.3.6.0 knows the EZ 2015 to 2025 only, so EZ 2026 takes the Vordrucke of 2025 until ELSTER publishes the
Jahresdokumentation 2026 (steuerbote.gewst.years: ``provisional``, ``documentation_year`` 2025).

Vordrucke. A GmbH or UG files GewSt1A, the Pflichtvordruck, and an Anlage BEG for each holding whose dividends § 8
Nummer 5 GewStG adds back or § 9 Nummer 2a or 7 GewStG cuts, up to 99, with the Vorsatz (FORMS, with the „max. lfd. Nr.
Vordruck“ of the sheet „Allg. Information“). The other Vordrucke of E20, EMU and OHG for partnerships and Organschaft
and BEKGW for the notice of the Gemeinde, are outside Steuerbote's scope.

Fields. The tables hold the current fields of the sheets „GewSt1A - Felder“ and „BEG - Felder“ in the order of the JD,
which is the order of the schema, in the layout of steuerbote.kst.form: Kontext, Name, Vordruckzeile,
Formatkennzeichen, Max. Länge of a text, Pflichtfeld, Kennzahl, Format als regulärer Ausdruck and Beschreibung, with
„-“ for an empty cell. The Beschreibung of each field is also its Drucktext, the text of the printed form.

Rules. The catalogue holds the rules of the JD that Steuerbote checks itself before ERiC
(steuerbote.eric.simulation.gewst): a Gewinn or Gewerbeertrag, the Betriebsstätte of lines 26 to 32, the Zuwendungen
of line 92d with the receipts of lines 92a to 92c, and the lines 15 to 19 of Anlage BEG. Their Fehler- /Hinweistext is
empty, as in steuerbote.kst.form. They ask for the Rechtsformgruppe of the Rechtsform of line 14 (E4000501), the
enumeration RECHTSFORM_GEWERBESTEUER_V2 of the sheet „Benutzerdefinierte Typen“: KOE for the GmbH (350) and the UG
(370), which RECHTSFORMEN holds.

Lines. Each step of steuerbote.gewst.chain names its line and Feldkennung (STEP_FIELDS). vordrucke() turns a
GewstResult into GewSt1A with the declared amounts of its steps, a zero left out but for the Gewinn of line 39, which
a declaration always holds (40000), and into an Anlage BEG for each holding of GewstResult.beg: the name of line 2, the
dividends of line 6 (40921, 40933), the paragraph of line 7 for a holding of at least 15 %, the costs of lines 8 and 9
with it, and the amounts of lines 12 and 14 to 19 that are not zero, line 12 also beside line 14 (40969). What the
computation does not know comes from the company: GewSt1A lines 1 to 33 with the Betriebsstätte, line 94 and the
receipts of lines 92a to 92c, the carry-forwards of lines 148 to 150, and lines 1 and 3 to 5a of Anlage BEG;
Vordruck.extended() adds them.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Mapping
from decimal import Decimal
from types import MappingProxyType

from steuerbote.elster.erklaerung import Form, FormCatalogue, Rule
from steuerbote.eric.datenart import gewst
from steuerbote.gewst.chain import STEPS, BegLine, GewstResult
from steuerbote.kst.form import Entry, Vordruck, checked, entries, table_fields
from steuerbote.ustva.rounding import ZERO, half_up_euro
from steuerbote.ustva.years import UnknownYearError

# The JD, sheet „GewSt1A - Felder“.
_GEWST1A_2025 = r"""
Allgemein	E4000101	3	C	103	Ja	-	.{1,103}	Unternehmen/Firma
Allgemein	E4000201	4	C	25	Ja	-	.{1,25}	Gegenstand des Unternehmens
Allgemein	E4000502	5	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
Rechtsform	E4001203	10	J	-	-	-	1	Der Gewerbebetrieb wird als Einzelunternehmen betrieben.
Rechtsform	E4001902	11	J	-	-	-	1	Das Unternehmen wurde im Kalenderjahr $VZ$ überwiegend oder ausschließlich als Hausgewerbe betrieben (§ 11 Absatz 3 GewStG).
Rechtsform	E4001201	12	J	-	-	-	1	Das Unternehmen wurde im Kalenderjahr $VZ$ als Reisegewerbebetrieb nach § 35a Absatz 1 GewStG betrieben.
Rechtsform	E4001204	13	J	-	-	-	1	Der Mittelpunkt der gewerblichen Tätigkeit des Reisegewerbebetriebs (zum Beispiel Wohnsitzgemeinde des Reisegewerbetreibenden) wurde im Kalenderjahr $VZ$ verlegt.
Rechtsform	E4000501	14	H	-	-	-	\Q350\E|\Q370\E|\Q310\E|\Q360\E|\Q320\E|\Q910\E|\Q460\E|\Q450\E|\Q490\E|\Q930\E|\Q510\E|\Q511\E|\Q520\E|\Q623\E|\Q540\E|\Q590\E|\Q940\E|\Q621\E|\Q650\E|\Q624\E|\Q950\E|\Q810\E|\Q811\E|\Q838\E|\Q831\E|\Q833\E|\Q820\E|\Q840\E|\Q850\E|\Q834\E|\Q960\E|\Q611\E|\Q391\E|\Q221\E|\Q837\E|\Q200\E|\Q210\E|\Q220\E|\Q230\E|\Q240\E|\Q250\E|\Q260\E|\Q270\E|\Q271\E|\Q280\E|\Q290\E|\Q291\E|\Q292\E|\Q293\E|\Q295\E|\Q920\E	Nur bei Personengesellschaften und Körperschaften: Rechtsform des Unternehmens
Rechtsform	E4001405	14a	J	-	-	-	1	Es handelt sich um eine optierende Gesellschaft nach § 1a KStG. Das Unternehmen ist im Weiteren wie eine Körperschaft in Form einer Kapitalgesellschaft zu behandeln.
Rechtsform	E4000602	16	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Das Einzelunternehmen / die Personengesellschaft ist durch einen unterjährigen Rechtsformwechsel im Kalenderjahr $VZ$ aus einer Personengesellschaft / einem Einzelunternehmen hervorgegangen am
Rechtsform	E4001603	17	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer des anderen Steuerschuldners im Falle des Rechtsformwechsels im Sinne der Zeile 16
Rechtsform	E4001705	17a	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer des anderen Steuerschuldners im Falle des Rechtsformwechsels im Sinne der Zeile 16
Rechtsform	E4000905	18	J	-	-	30.55	1	Es handelt sich um ein Unternehmen im Sinne des § 7 Satz 5 GewStG in Verbindung mit § 8 Absatz 9 KStG (auch soweit Organgesellschaft).
Erg_Ang	E4003204	21	H	-	-	86.500	\Q1\E|\Q2\E|\Q3\E|\Q4\E	In dieser Steuererklärung
Erg_Ang	E4003205	21	C	999	-	-	.{1,999}	Ergänzende Angaben zur Steuererklärung
St_Gest	E4003208	22	C	17	-	20.809	(AT|BE|BG|CY|CZ|DE|DK|EE|ES|FI|FR|GB|GR|HR|HU|IE|IT|LT|LU|LV|MT|NL|PL|PT|RO|SE|SI|SK)A(((2000|((19|20)(0[48]|[2468][048]|[13579][26])))0229)|(((19|20)[0-9]{2})02(0[1-9]|1[0-9]|2[0-8]))|(((19|20)[0-9]{2})(0[13578]|10|12)(0[1-9]|[12][0-9]|3[01]))|(((19|20)[0-9]{2})(0[469]|11)(0[1-9]|[12][0-9]|30)))([A-Z]|[0-9]){6}	Registriernummer
St_Gest	E4003209	23	C	17	-	20.819	(AT|BE|BG|CY|CZ|DE|DK|EE|ES|FI|FR|GB|GR|HR|HU|IE|IT|LT|LU|LV|MT|NL|PL|PT|RO|SE|SI|SK)D(((2000|((19|20)(0[48]|[2468][048]|[13579][26])))0229)|(((19|20)[0-9]{2})02(0[1-9]|1[0-9]|2[0-8]))|(((19|20)[0-9]{2})(0[13578]|10|12)(0[1-9]|[12][0-9]|3[01]))|(((19|20)[0-9]{2})(0[469]|11)(0[1-9]|[12][0-9]|30)))([A-Z]|[0-9]){6}	Offenlegungsnummer
St_Gest	E4003210	24	J	-	-	20.829	1	Es liegen noch keine Registriernummer und Offenlegungsnummer vor.
St_Gest	E4003211	25	C	999	-	-	.{1,999}	Bezeichnung der Steuergestaltungen, soweit noch keine Registrier- und Offenlegungsnummer vorliegen
Ang_Gew_Betr/Betr_St	E4001506	26	Y	-	-	-	1|2	Betriebsstätten bestanden im Kalenderjahr $VZ$ in mehreren Gemeinden.
Ang_Gew_Betr/Betr_St	E4001507	27	Y	-	-	-	1|2	Betriebsstätte(n) erstreckte(n) sich im Kalenderjahr $VZ$ über mehrere Gemeinden.
Ang_Gew_Betr/Betr_St	E4001102	28	Y	-	-	-	1|2	Die einzige Betriebsstätte wurde im Laufe des Kalenderjahrs $VZ$ in eine andere Gemeinde verlegt
Ang_Gew_Betr/Betr_St	E4001103	29	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Wenn ja: Die Betriebsstätte wurde verlegt am
Ang_Gew_Betr/Betr_St	E4001104	30	C	999	-	-	.{1,999}	Ort der einzigen Betriebsstätte (bisher)
Ang_Gew_Betr/Betr_St	E4001105	30	C	999	-	-	.{1,999}	Ort der einzigen Betriebsstätte (neu)
Ang_Gew_Betr/Betr_St	E4001110	31	C	5	-	-	^(?=.{5,5}$)([0]{1}[1-9]{1}[0-9]{3})|([1-9]{1}[0-9]{4})	Wenn nein: Postleitzahl der einzigen Betriebsstätte
Ang_Gew_Betr/Betr_St	E4001111	32	C	999	-	-	.{1,999}	Ort der einzigen Betriebsstätte
Ang_Gew_Betr/Heb_Nr	E4001803	33	C	28	-	-	.{1,28}	Hebenummer (Steuernummer) der Gemeinde
Ang_Gew_Betr/Betr_Eroeff	E4002103	34	D	-	-	30.70	\d\d\.\d\d\.\d\d\d\d	Die werbende Tätigkeit wurde begonnen am
Ang_Gew_Betr/Betr_Eroeff	E4002205	35	T	-	-	30.71	\d\d\.\d\d\.	Die werbende Tätigkeit wurde in $VZ$ beendet am
Ang_Gew_Betr/OG	E4001401	36	J	-	-	-	1	Das Unternehmen ist Organträger.
Ang_Gew_Betr/OG	E4001501	37	J	-	-	-	1	Das Unternehmen ist Organgesellschaft.
Gewinn	E4001703	39	N	-	-	21.10	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Gewinn aus Gewerbebetrieb vor Anwendung des § 7 Satz 4 GewStG (ohne Beträge laut Zeilen 46 und 100 bis 102)
Gewinn	E4003408	40	N	-	-	21.18	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nur bei Personengesellschaften: Steuerfreie Einnahmen nach § 3 Nummer 40 EStG und § 8b KStG vermindert um nichtabziehbare Beträge nach § 3c Absatz 2 EStG und § 8b KStG (§ 7 Satz 4 GewStG)
Gewinn	E4003409	41	N	-	-	21.23	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nur bei Personengesellschaften: Nach §§ 20, 42 und 43 InvStG steuerfreie Erträge vermindert um Beträge nach §§ 21 und 44 InvStG (Randziffer 20.20 des BMF-Schreibens vom 21.05.2019, BStBl I 2019, 527)
Gewinn	E4003504	42	C	2	-	21.51	[1-9]|[1-2][0-9]|[3][0-2]	Der Gewerbebetrieb ist nach folgender Nummer des § 3 GewStG vollständig oder partiell von der Gewerbesteuer befreit:
Gewinn	E4003603	43	N	-	-	21.52	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Von der Gewerbesteuer befreiter Gewinn aus Gewerbebetrieb laut Zeile 39
Gewinn	E4003604	44	N	-	-	21.55	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Von der Gewerbesteuer nach § 13 GewStDV befreiter Anteil am Gewinn aus Gewerbebetrieb laut Zeile 39
Gewinn	E4003704	45	M	-	-	21.21	^(?=.{1,13}$)(?=.*[1-9].*)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Korrektur des Gewinns aus Gewerbebetrieb aufgrund der Erstattung von Aufwendungen, die in einem vorangegangenen Erhebungszeitraum der Hinzurechnung unterlegen haben (Eintrag mit negativem Vorzeichen)
Gewinn	E4003903	46	N	-	-	21.29	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Gewinn des wirtschaftlichen Geschäftsbetriebs nach § 15 Absatz 4 InvStG
Gewinn	E4004003	47	G	-	-	21.20	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Nur bei Personengesellschaften: Abzug von Kapitalertragsteuer gemäß Antrag nach § 36a Absatz 1 Satz 3 EStG: Abzuziehende nicht anrechenbare Kapitalertragsteuer nach § 36a Absatz 1 Satz 3 EStG
Gewinn	E4004004	48	N	-	-	21.53	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Anwendung des § 20 Absatz 5 InvStG: Gesamtbetrag der bei der Ermittlung des Gewinns aus Gewerbebetrieb vorgenommenen Teilfreistellungen aus unmittelbaren Beteiligungen nach §§ 20 und 21 InvStG
Gewinn	E4004006	48a	N	-	-	21.56	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Anwendung des § 45 Absatz 2 InvStG: Korrekturbetrag nach § 45 Absatz 2 InvStG
Gewinn	E4004005	49	U	-	-	21.54	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Anwendung des § 45 Absatz 1 InvStG: Korrekturbetrag nach § 45 Absatz 1 Satz 1 InvStG
Hinz/P_8_Nr_1_Wj1	E4003202	50	U	-	-	21.31	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Entgelte für Schulden (§ 8 Nummer 1 Buchstabe a GewStG)
Hinz/P_8_Nr_1_Wj1	E4003302	51	U	-	-	21.32	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Renten und dauernde Lasten (§ 8 Nummer 1 Buchstabe b GewStG)
Hinz/P_8_Nr_1_Wj1	E4003407	52	N	-	-	21.33	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Gewinnanteile der stillen Gesellschafter (§ 8 Nummer 1 Buchstabe c GewStG)
Hinz/P_8_Nr_1_Wj1	E4003502	53	U	-	-	21.34	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Miet- und Pachtzinsen (einschließlich Leasingraten) für die Benutzung fremder beweglicher Betriebsanlagegüter (§ 8 Nummer 1 Buchstabe d Satz 1 GewStG) (ohne Beträge laut Zeile 54)
Hinz/P_8_Nr_1_Wj1	E4004402	54	U	-	-	21.38	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Miet- und Pachtzinsen (einschließlich Leasingraten) für Elektrofahrzeuge, begünstigte Hybridelektrofahrzeuge und Fahrräder im Sinne des § 8 Nummer 1 Buchstabe d Satz 2 GewStG aus Verträgen, die nach dem 31.12.2019 abgeschlossen worden sind
Hinz/P_8_Nr_1_Wj1	E4003602	55	U	-	-	21.35	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Miet- und Pachtzinsen (einschließlich Leasingraten) für die Benutzung fremder unbeweglicher Betriebsanlagegüter (§ 8 Nummer 1 Buchstabe e GewStG)
Hinz/P_8_Nr_1_Wj1	E4003703	56	U	-	-	21.36	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Aufwendungen für die zeitlich befristete Überlassung von Rechten, insbesondere Konzessionen und Lizenzen (§ 8 Nummer 1 Buchstabe f GewStG)
Hinz/P_8_Nr_1_Wj1	E4004103	57	U	-	-	21.37	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Im Betrag laut Zeile 56 enthaltene Vergütungen im Sinne des § 50a Absatz 1 Nummer 3 EStG an beschränkt steuerpflichtige Zahlungsempfänger
Hinz/P_8_Nr_1_Wj2	E4003802	58	U	-	-	21.41	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Entgelte für Schulden (§ 8 Nummer 1 Buchstabe a GewStG)
Hinz/P_8_Nr_1_Wj2	E4003902	59	U	-	-	21.42	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Renten und dauernde Lasten (§ 8 Nummer 1 Buchstabe b GewStG)
Hinz/P_8_Nr_1_Wj2	E4004002	60	N	-	-	21.43	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Gewinnanteile der stillen Gesellschafter (§ 8 Nummer 1 Buchstabe c GewStG)
Hinz/P_8_Nr_1_Wj2	E4004102	61	U	-	-	21.44	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Miet- und Pachtzinsen (einschließlich Leasingraten) für die Benutzung fremder beweglicher Betriebsanlagegüter (§ 8 Nummer 1 Buchstabe d Satz 1 GewStG) (ohne Beträge laut Zeile 62)
Hinz/P_8_Nr_1_Wj2	E4005103	62	U	-	-	21.48	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Miet- und Pachtzinsen (einschließlich Leasingraten) für Elektrofahrzeuge, begünstigte Hybridelektrofahrzeuge und Fahrräder im Sinne des § 8 Nummer 1 Buchstabe d Satz 2 GewStG aus Verträgen, die nach dem 31.12.2019 abgeschlossen worden sind
Hinz/P_8_Nr_1_Wj2	E4004203	63	U	-	-	21.45	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Miet- und Pachtzinsen (einschließlich Leasingraten) für die Benutzung fremder unbeweglicher Betriebsanlagegüter (§ 8 Nummer 1 Buchstabe e GewStG)
Hinz/P_8_Nr_1_Wj2	E4004303	64	U	-	-	21.46	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Aufwendungen für die zeitlich befristete Überlassung von Rechten, insbesondere Konzessionen und Lizenzen (§ 8 Nummer 1 Buchstabe f GewStG)
Hinz/P_8_Nr_1_Wj2	E4004702	65	U	-	-	21.47	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Im Betrag laut Zeile 64 enthaltene Vergütungen im Sinne des § 50a Absatz 1 Nummer 3 EStG an beschränkt steuerpflichtige Zahlungsempfänger
Hinz/P_8_Nr_4	E4002101	66	N	-	-	21.14	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nur bei einer Kommanditgesellschaft auf Aktien: Gewinnanteile der in § 8 Nummer 4 GewStG bezeichneten Art an persönlich haftende Gesellschafter
Hinz/P_8_Nr_8/Einz	E4002320	67	C	999	-	-	.{1,999}	Name der Personengesellschaft
Hinz/P_8_Nr_8/Einz	E4002321	67a	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der Personengesellschaft
Hinz/P_8_Nr_8/Einz	E4002323	67b	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer der Personengesellschaft
Hinz/P_8_Nr_8/Einz	E4002322	67c	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Anteil am Verlust der in- oder ausländischen Personengesellschaft
Hinz/P_8_Nr_8/Sum	E4002301	67d	U	-	-	21.16	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Summe der Anteile am Verlust von in- und/oder ausländischen Personengesellschaften (§ 8 Nummer 8 GewStG; Betrag ohne Minuszeichen eintragen)
Hinz/P_8_9_12	E4002501	68	U	-	-	21.19	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausschüttungs- und abführungsbedingte Gewinnminderungen bei Beteiligungsbesitz (§ 8 Nummer 10 GewStG); auch soweit die Gewinnminderung Folge einer Auskehrung von Liquidationsraten ist
Hinz/P_8_9_12	E4002601	69	U	-	-	21.22	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausländische Steuern, soweit sie auf Gewinne oder Gewinnanteile entfallen, die nach § 9 GewStG gekürzt werden oder sonst nicht im Gewerbeertrag enthalten sind (§ 8 Nummer 12 GewStG)
Gew_Ant_Koe	E4006104	70	C	10	-	-	^(?=.{8,10}$)(?!0\d)\d{1,3}(,\d{6,6})$	Nur bei Mitunternehmerschaften: Anteil der an der Mitunternehmerschaft unmittelbar oder mittelbar über andere Mitunternehmerschaften beteiligten Körperschaften in Höhe von (Prozent)
Gew_Ant_Koe	E4006201	71	C	10	-	-	^(?=.{8,10}$)(?!0\d)\d{1,3}(,\d{6,6})$	Nur bei Organgesellschaften: Anteil der an der Organgesellschaft unmittelbar oder mittelbar über Mitunternehmerschaften beteiligten Körperschaften in Höhe von (Prozent)
Gew_Ant_Koe	E4006301	72	C	10	-	-	^(?=.{8,10}$)(?!0\d)\d{1,3}(,\d{6,6})$	Bei Mitunternehmerschaften und Organgesellschaften: Anteil der an der Mitunternehmerschaft oder der Organgesellschaft unmittelbar oder mittelbar über andere Mitunternehmerschaften beteiligten natürlichen Personen (100 % abzüglich Prozentsatz laut Zeile 70 oder 71)
Gew_Ant_Koe	E4006401	73	U	-	-	21.63	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Organgesellschaften: Steuerfreie Bezüge nach § 8b Absatz 1 und 4 KStG oder nach DBA (Summe der Beträge laut Zeile 13 aller Anlagen BEG)
Gew_Ant_Koe	E4006501	75	U	-	-	21.64	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bezüge nach § 3 Nummer 40 EStG gekürzt um Betriebsausgaben nach § 3c Absatz 2 EStG vor Anwendung des Teileinkünfteverfahrens (Summe der positiven Beträge laut Zeile 22 aller Anlagen BEG)
Gew_Ant_Koe	E4006502	76	M	-	-	21.68	^(?=.{1,13}$)(?=.*[1-9].*)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Bezüge nach § 3 Nummer 40 EStG gekürzt um Betriebsausgaben nach § 3c Absatz 2 EStG vor Anwendung des Teileinkünfteverfahrens (Summe der negativen Beträge laut Zeile 22 aller Anlagen BEG)
Gew_Ant_Koe	E4006601	77	U	-	-	21.26	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Hinzurechnungsbetrag nach § 8 Nummer 5 GewStG, soweit auf Körperschaften entfallend (Summe der Beträge laut Zeile 15 aller Anlagen BEG)
Gew_Ant_Koe	E4006602	78	N	-	-	21.69	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hinzurechnungsbetrag nach § 8 Nummer 5 GewStG, soweit auf natürliche Personen entfallend (Summe der Beträge laut Zeile 23 aller Anlagen BEG)
Gew_Ant_Koe	E4006701	79	U	-	-	21.65	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Kürzung des Hinzurechnungsbetrages nach § 8 Nummer 1 GewStG aufgrund des § 9 Nummer 2a Satz 3 zweiter Halbsatz GewStG, § 9 Nummer 7 Satz 2 beziehungsweise § 9 Nummer 8 Satz 2 GewStG (Summe der Beträge laut Zeile 20 aller Anlagen BEG)
Gew_Ant_Koe	E4006702	80	U	-	-	21.66	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Kürzung des Hinzurechnungsbetrages nach § 8 Nummer 1 GewStG aufgrund des § 9 Nummer 2a Satz 3 zweiter Halbsatz GewStG, § 9 Nummer 7 Satz 2 beziehungsweise § 9 Nummer 8 Satz 2 GewStG (Summe der Beträge laut Zeile 28 aller Anlagen BEG)
Gew_Ant_Koe	E4006801	81	U	-	-	20.026	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Kürzung nach § 9 Nummer 2a, 7 und 8 GewStG (Betrag laut Zeile 19 aller Anlagen BEG)
Gew_Ant_Koe	E4006802	82	U	-	-	20.002	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Kürzung nach § 9 Nummer 2a, 7 und 8 GewStG vor Anwendung des Teileinkünfteverfahrens (Betrag laut Zeile 27 aller Anlagen BEG)
Kuerz/Ehw	E4008701	87	N	-	-	20.113	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Als Betriebsausgabe erfasste Grundsteuer
Kuerz/Weit_Kuerz	E4002901	88	N	-	-	20.030	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Erweiterte Kürzung bei einem Grundstücksunternehmen im Sinne des § 9 Nummer 1 Satz 2 folgende GewStG (Die Voraussetzungen des § 9 Nummer 1 Satz 2 bis 6 GewStG sind anhand geeigneter Aufzeichnungen nachzuweisen.)
Kuerz/Gew_PersG/Einz	E4003020	89	C	999	-	-	.{1,999}	Name der Personengesellschaft
Kuerz/Gew_PersG/Einz	E4003021	89a	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der Personengesellschaft
Kuerz/Gew_PersG/Einz	E4003023	89b	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer der Personengesellschaft
Kuerz/Gew_PersG/Einz	E4003022	89c	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Anteil am Gewinn der in- oder ausländischen Personengesellschaft
Kuerz/Gew_PersG/Sum	E4003001	89d	U	-	-	20.031	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Summe der Anteile am Gewinn von in- und/oder ausländischen Personengesellschaften (§ 9 Nummer 2 GewStG)
Kuerz/Weit_Ang	E4003201	90	U	-	-	20.053	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Die nach § 8 Nummer 4 GewStG dem Gewinn aus Gewerbebetrieb der Kommanditgesellschaft auf Aktien hinzugerechneten Gewinnanteile eines persönlich haftenden Gesellschafters (§ 9 Nummer 2b GewStG)
Kuerz/Weit_Ang	E4003301	91	N	-	-	20.033	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Teil des Gewerbeertrages, der auf Betriebsstätten im Ausland entfällt, ohne Einkünfte im Sinne des § 7 Satz 7 und 8 GewStG (§ 9 Nummer 3 GewStG); negative Beträge mit Minuszeichen eintragen
Kuerz/Zuw/Stb_Zweck/Einz	E4009220	92a	C	999	-	-	.{1,999}	Name des Empfängers
Kuerz/Zuw/Stb_Zweck/Einz	E4009221	92b	R	-	-	-	^(?=.{4,15}$)(?=.*[1-9].*)(?!0\d)\d{1,12}(,\d{2,2})$	Betrag laut Bestätigung
Kuerz/Zuw/Stb_Zweck/Einz	E4009222	92c	H	-	-	-	\Q1\E|\Q2\E	Der Empfänger liegt im
Kuerz/Zuw/Stb_Zweck/Sum	E4003403	92d	G	-	-	20.071	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Zuwendungen im Kalenderjahr $VZ$ beziehungsweise im abweichenden Wirtschaftsjahr $VZ-1$/$VZ$ zur Förderung steuerbegünstigter Zwecke im Sinne der §§ 52 bis 54 AO (§ 9 Nummer 5 Satz 1 GewStG)
Kuerz/Zuw/HB	E4004001	94	U	-	-	20.057	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Summe der gesamten Umsätze und der im Wirtschaftsjahr aufgewendeten Löhne und Gehälter
Kuerz/Zuw/Vortrag	E4006101	95	U	-	-	20.084	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bei dem übernehmenden Unternehmen im Jahr der Vermögensübernahme: Auf das übernehmende Unternehmen im laufenden Erhebungszeitraum übergegangener Zuwendungsvortrag nach § 9 Nummer 5 Satz 13 GewStG in Verbindung mit § 12 Absatz 3 UmwStG (gegebenenfalls in Verbindung mit § 15 Absatz 1, § 16, § 18 UmwStG)
Kuerz/Zuw/Vortrag	E4009501	95a	U	-	-	20.114	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bei dem übernehmenden Unternehmen im Jahr der Vermögensübernahme: Auf das übernehmende Unternehmen zum Ende des Erhebungszeitraums übergegangener Zuwendungsvortrag nach § 9 Nummer 5 Satz 13 GewStG in Verbindung mit § 12 Absatz 3 UmwStG (gegebenenfalls in Verbindung mit § 15 Absatz 1, § 16, § 18 UmwStG)
Kuerz/Zuw/Vortrag	E4006103	95b	U	-	-	20.089	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Im Falle einer Abspaltung oder Teilübertragung: Verringerung des verbleibenden Zuwendungsvortrags (§ 9 Nummer 5 Satz 13 GewStG) bei der übertragenden Körperschaft (§ 12 Absatz 3 in Verbindung mit § 15 Absatz 1, § 16, § 18 UmwStG)
Kuerz/Zuw/Vortrag	E4009404	95c	U	-	-	20.083	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des verbleibenden Zuwendungsvortrags des laufenden Erhebungszeitraums durch Abspaltung oder Teilübertragung bei der übertragenden Körperschaft zum Ende des Erhebungszeitraums (§ 12 Absatz 3 in Verbindung mit § 15 Absatz 1, § 16, § 18 UmwStG)
Kuerz/Zuw/Stift/Spenden/Einz	E4009620	96a	C	999	-	-	.{1,999}	Name des Empfängers
Kuerz/Zuw/Stift/Spenden/Einz	E4009621	96b	R	-	-	-	^(?=.{4,15}$)(?=.*[1-9].*)(?!0\d)\d{1,12}(,\d{2,2})$	Betrag laut Bestätigung
Kuerz/Zuw/Stift/Spenden/Einz	E4009622	96c	H	-	-	-	\Q1\E|\Q2\E	Der Empfänger liegt im
Kuerz/Zuw/Stift/Spenden/Sum	E4003404	96d	G	-	-	-	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Spenden im Kalenderjahr $VZ$ beziehungsweise im abweichenden Wirtschaftsjahr $VZ-1$/$VZ$ in den Vermögensstock einer Stiftung, für die der besondere Abzug nach § 9 Nummer 5 Satz 9 bis 11 GewStG beantragt wird
Kuerz/Zuw/Stift/Abzug	E4003406	98	U	-	-	20.072	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Betrag der Vermögensstockspenden, die im Erhebungszeitraum $VZ$ abgezogen werden sollen
Kuerz/Zuw/Stift/Vortrag	E4003405	98a	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zum Ende des vorangegangenen Erhebungszeitraums gesondert festgestellter verbleibender Vortrag von Vermögensstockspenden nach § 9 Nummer 5 Satz 9 folgende GewStG
Kuerz/Zuw/Stift/Vortrag	E4003505	99	U	-	-	20.108	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zum Ende des Erhebungszeitraums verbleibender Betrag der Vermögensstockspenden, der aufgrund des Ablaufs des zehnjährigen Abzugszeitraums im Folgejahr nicht mehr beansprucht werden kann
Kuerzung_AStG/Einz	E4009910	99a	C	999	-	-	.{1,999}	Bezeichnung der Zwischengesellschaft
Kuerzung_AStG/Einz	E4009911	99b	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Kürzungsbetrag nach § 11 Absatz 5 AStG
Kuerzung_AStG/Sum	E4009902	99c	U	-	-	20.109	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Summe der Kürzungsbeträge nach § 11 Absatz 5 AStG
Gew_Ertr/P_5a_EStG	E4004202	100	U	-	-	20.023	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nach § 5a Absatz 1 EStG ermittelter Gewinn
Gew_Ertr/P_5a_EStG	E4001704	101	N	-	-	21.27	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hinzuzurechnender Unterschiedsbetrag nach § 5a Absatz 4 EStG und sonstige Hinzurechnungen im Sinne des § 5a Absatz 5 EStG
Gew_Ertr/P_5a_EStG	E4003503	102	N	-	-	21.28	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hinzuzurechnende Vergütungen im Sinne des § 5a Absatz 4a Satz 3 EStG (gegebenenfalls gekürzt um damit im Zusammenhang stehende Aufwendungen)
Gew_Ertr/Oer_Rundfunk	E4004811	103	U	-	-	20.025	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nach § 8 Absatz 1 Satz 3 KStG ermitteltes Einkommen aus dem Geschäft der Veranstaltung von Werbesendungen (§ 7 Satz 3 GewStG)
Gew_Ertr/Spartentr	E4007601	104	U	-	-	20.061	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Maßgebender verbleibender Gewerbeertrag in den Fällen des § 7 Satz 5 GewStG in Verbindung mit § 8 Absatz 9 KStG (Betrag laut Zeile 71 aller Anlagen ÖHG)
Weit_Ang/Gew_Ertr_OG/Einz	E4004320	105	C	999	-	-	.{1,999}	Name der Organgesellschaft
Weit_Ang/Gew_Ertr_OG/Einz	E4004321	106	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der Organgesellschaft
Weit_Ang/Gew_Ertr_OG/Einz	E4004323	106a	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer der Organgesellschaft
Weit_Ang/Gew_Ertr_OG/Einz	E4004322	107	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Gewerbeertrag der Organgesellschaft
Weit_Ang/Gew_Ertr_OG/Einz	E4004922	107a	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Korrekturbetrag nach § 3 Nummer 40 Buchstabe a, § 3c EStG und § 8b Absatz 2 und 3 KStG, § 12 Absatz 2 UmwStG in Verbindung mit § 15 Satz 1 Nummer 2 und Satz 2 KStG und § 34c Absatz 3 EStG
Weit_Ang/Gew_Ertr_OG/Einz	E4004925	107b	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Korrekturbetrag nach §§ 20 und 21 InvStG
Weit_Ang/Gew_Ertr_OG/Einz	E4004926	107c	G	-	-	-	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Nur bei Körperschaften: Korrekturbetrag nach § 45 Absatz 1 InvStG
Weit_Ang/Gew_Ertr_OG/Sum	E4004301	108	N	-	-	20.060	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Summe der Gewerbeerträge der Organgesellschaften
Weit_Ang/Gew_Ertr_OG/Sum	E4004913	109	N	-	-	20.079	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Summe der Korrekturbeträge aufgrund der Anwendung des § 3 Nummer 40 Buchstabe a, § 3c EStG, § 8b Absatz 2 und 3 KStG, § 12 Absatz 2 UmwStG in Verbindung mit § 15 Satz 1 Nummer 2 und Satz 2 KStG und der Anwendung von § 34c Absatz 3 EStG (negative Beträge mit Minuszeichen eintragen)
Weit_Ang/Gew_Ertr_OG/Sum	E4004914	110	N	-	-	20.101	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Summe der Korrekturbeträge aufgrund der Anwendung der §§ 20 und 21 InvStG in Verbindung mit § 15 Satz 1 Nummer 2a und Satz 2 KStG gegebenenfalls in Verbindung mit § 43 Absatz 3 und § 45 Absatz 2 InvStG (negative Beträge mit Minuszeichen eintragen)
Weit_Ang/Gew_Ertr_OG/Sum	E4004915	111	G	-	-	20.102	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Nur bei Körperschaften: Summe der Korrekturbeträge aufgrund der Anwendung des § 45 Absatz 1 InvStG
Weit_Ang/Ang_OG	E4006003	112	N	-	-	20.028	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Wenn der Organträger eine natürliche Person ist: Zu berücksichtigender Korrekturbetrag zum Gewerbeertrag aufgrund der Anwendung des § 3 Nummer 40 Buchstabe a, § 3c EStG und § 12 Absatz 2 UmwStG in Verbindung mit § 15 Satz 1 Nummer 2 und Satz 2 KStG sowie § 34c Absatz 3 EStG
Weit_Ang/Ang_OG	E4006004	113	N	-	-	20.029	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Wenn der Organträger eine Körperschaft ist: Zu berücksichtigender Korrekturbetrag zum Gewerbeertrag aufgrund der Anwendung des § 8b Absatz 2 und 3 KStG und § 12 Absatz 2 UmwStG in Verbindung mit § 15 Satz 1 Nummer 2 und Satz 2 KStG sowie § 34c Absatz 3 EStG
Weit_Ang/Ang_OG	E4006005	114	N	-	-	20.027	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Wenn der Organträger eine Personengesellschaft ist: Zu berücksichtigender Korrekturbetrag zum Gewerbeertrag aufgrund der Anwendung des § 3 Nummer 40 Buchstabe a, § 3c EStG, § 8b Absatz 2 und 3 KStG, § 12 Absatz 2 UmwStG in Verbindung mit § 15 Satz 1 Nummer 2 und Satz 2 KStG sowie § 34c Absatz 3 EStG
Weit_Ang/Ang_OG	E4006006	115	N	-	-	20.103	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Wenn der Organträger eine natürliche Person ist: Zu berücksichtigender Korrekturbetrag zum Gewerbeertrag aufgrund der Anwendung des § 15 Satz 1 Nummer 2a und Satz 2 KStG, insbesondere in den Fällen der §§ 20, 21 InvStG und § 43 Absatz 3 in Verbindung mit § 45 Absatz 2 InvStG
Weit_Ang/Ang_OG	E4006007	116	N	-	-	20.104	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Wenn der Organträger eine Körperschaft ist: Zu berücksichtigender Korrekturbetrag zum Gewerbeertrag aufgrund der Anwendung des § 15 Satz 1 Nummer 2a und Satz 2 KStG, insbesondere in den Fällen der §§ 20, 21 InvStG und § 43 Absatz 3 in Verbindung mit § 45 Absatz 2 InvStG
Weit_Ang/Ang_OG	E4006008	117	N	-	-	20.105	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Wenn der Organträger eine Personengesellschaft ist: Zu berücksichtigender Korrekturbetrag zum Gewerbeertrag aufgrund der Anwendung des § 15 Satz 1 Nummer 2a und Satz 2 KStG, insbesondere in den Fällen der §§ 20, 21 InvStG und § 43 Absatz 3 in Verbindung mit § 45 Absatz 2 InvStG
Weit_Ang/Ang_OG	E4006009	118	U	-	-	20.106	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Wenn der Organträger eine Körperschaft ist: Zu berücksichtigender Korrekturbetrag aufgrund der Anwendung des § 45 Absatz 1 InvStG
P2_Abs4_UmwStG	E4008301	120	U	-	-	20.021	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Beim übernehmenden Rechtsträger: Positiver Gewerbeertrag des übertragenden oder einbringenden Rechtsträgers im Rückwirkungszeitraum
P2_Abs4_UmwStG	E4008401	121	U	-	-	20.022	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Organträgern: Beim Organträger des übernehmenden Rechtsträgers: Positiver Gewerbeertrag des auf die Organgesellschaft(en) übertragenden oder einbringenden Rechtsträgers im Rückwirkungszeitraum
P2_Abs5_UmwStG	E4009002	122	U	-	-	20.024	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Negative Einkünfte des übernehmenden Rechtsträgers nach § 2 Absatz 5 UmwStG
Beschraenk_lfd_Verlust/Mind_lfd_Verl	E4009001	123	U	-	-	20.107	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Körperschaften und Personengesellschaften, soweit an diesen eine Körperschaft unmittelbar oder mittelbar über eine oder mehrere Personengesellschaft(en) beteiligt ist: Höhe der gesamten zum Zeitpunkt des schädlichen Beteiligungserwerbs im Sinne von § 10a Satz 10 GewStG in Verbindung mit § 8c KStG im Inland vorhandenen gewerbesteuerpflichtigen stillen Reserven des Betriebsvermögens bei Anwendung der Stille-Reserven-Klausel (vergleiche Gleich lautende Erlasse der obersten Finanzbehörden der Länder vom 29.11.2017, BStBl I 2017, 1643)
Beschraenk_lfd_Verlust/Mind_lfd_Verl	E4009701	124	U	-	-	20.049	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Körperschaften: Nach § 10a Satz 10 GewStG in Verbindung mit § 8c KStG nicht ausgleichsfähiger Gewerbeverlust des laufenden Erhebungszeitraums (gegebenenfalls in Verbindung mit § 2 Absatz 4 Satz 1 und 2, § 20 Absatz 6 Satz 4 UmwStG)
Beschraenk_lfd_Verlust/Mind_lfd_Verl	E4004801	125	U	-	-	20.078	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Körperschaften: Bei der übertragenden Körperschaft im Falle der Abspaltung wegfallender Gewerbeverlust des laufenden Erhebungszeitraums (§ 18 Absatz 1 beziehungsweise § 19 Absatz 1 in Verbindung mit § 15 Absatz 1 Satz 1, § 15 Absatz 3 und § 16 Satz 1 UmwStG)
Beschraenk_lfd_Verlust/Mind_lfd_Verl	E4009901	126	U	-	-	20.013	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei einer Personengesellschaft, soweit an dieser eine Körperschaft unmittelbar oder mittelbar über eine oder mehrere Personengesellschaft(en) beteiligt ist: Nach § 10a Satz 10 GewStG in Verbindung mit § 8c KStG nicht ausgleichsfähiger Gewerbeverlust des laufenden Erhebungszeitraums
Ffg_Verlust	E4009403	127	J	-	-	20.038	1	Nur bei Körperschaften: § 8d KStG ist auf die Gewerbesteuerfehlbeträge entsprechend anzuwenden (§ 10a Satz 11 und 12 GewStG).
Ffg_Verlust	E4009503	128	Y	-	-	20.035	1|2	Nur bei Körperschaften: Wenn zum Schluss des vorangegangenen Erhebungszeitraums ein fortführungsgebundener Gewerbeverlust festgestellt wurde: Im Erhebungszeitraum sind Ereignisse im Sinne des § 8d Absatz 2 KStG eingetreten.
Verlust	E4004501	129	U	-	-	20.045	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Personengesellschaften: Von einem Einzelunternehmen im Falle des Rechtsformwechsels übernommener Gewerbeverlust aus der Zeit vor dem Rechtsformwechsel, soweit nach § 10a GewStG vortragsfähig
Verlust	E4004601	130	U	-	-	20.048	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Übernommener Gewerbeverlust im laufenden Erhebungszeitraum im Falle der - Einbringung des Betriebs einer Kapitalgesellschaft oder Personengesellschaft in eine Personengesellschaft oder - Verschmelzung von Personengesellschaften (R 10a.3 Absatz 3 Satz 9 Nummer 5 Satz 1 und 2 GewStR 2009) oder - Anwachsung oder der Verschmelzung einer Personengesellschaft auf einen Gesellschafter (R 10a.3 Absatz 3 Satz 9 Nummer 4 GewStR 2009)
Verlust	E4013001	130a	U	-	-	20.110	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Übernommener Gewerbeverlust zum Ende des Erhebungszeitraums im Falle der - Einbringung des Betriebs einer Kapitalgesellschaft oder Personengesellschaft in eine Personengesellschaft oder - Verschmelzung von Personengesellschaften (R 10a.3 Absatz 3 Satz 9 Nummer 5 Satz 1 und 2 GewStR 2009) oder - Anwachsung oder der Verschmelzung einer Personengesellschaft auf einen Gesellschafter (R 10a.3 Absatz 3 Satz 9 Nummer 4 GewStR 2009)
Verlust	E4009201	131	U	-	-	20.018	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Organgesellschaften: Im Falle der Anwachsung einer Personengesellschaft auf eine Organgesellschaft im laufenden Erhebungszeitraum: Im Betrag laut Zeile 130 enthaltener Verlust, der vor dem rechtswirksamen Abschluss des Gewinnabführungsvertrages bei der Personengesellschaft entstanden ist (R 10a.4 Satz 2 GewStR 2009)
Verlust	E4013101	131a	U	-	-	20.111	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Organgesellschaften: Im Falle der Anwachsung einer Personengesellschaft auf eine Organgesellschaft zum Ende des Erhebungszeitraums: Im Betrag laut Zeile 130a enthaltener Verlust, der vor dem rechtswirksamen Abschluss des Gewinnabführungsvertrages bei der Personengesellschaft entstanden ist (R 10a.4 Satz 2 GewStR 2009)
Verlust	E4009101	132	U	-	-	20.020	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Betrieben gewerblicher Art: Übernommener vortragsfähiger Gewerbeverlust (§ 10a Satz 9 GewStG in Verbindung mit § 8 Absatz 8 KStG)
Verlust	E4004701	133	U	-	-	20.047	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Körperschaften: Bei der übertragenden Körperschaft im Falle der Abspaltung wegfallender Gewerbeverlust aus vorangegangenen Erhebungszeiträumen (§ 18 Absatz 1 in Verbindung mit § 16 und § 15 Absatz 3 beziehungsweise § 19 Absatz 2 in Verbindung mit § 15 Absatz 3 UmwStG)
Verlust	E4009605	134	U	-	-	20.044	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Körperschaften: Nach § 10a Satz 10 GewStG in Verbindung mit § 8c KStG nicht abziehbarer Gewerbeverlust aus vorangegangenen Erhebungszeiträumen (gegebenenfalls in Verbindung mit § 2 Absatz 4 Satz 1 und 2, § 20 Absatz 6 Satz 4 UmwStG) (laut gesonderter Ermittlung)
Verlust	E4010201	135	N	-	-	20.052	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nur bei Körperschaften: Erhalt des vortragsfähigen fortführungsgebundenen Gewerbeverlustes nach § 10a Satz 11 GewStG in Verbindung mit § 8d Absatz 2 Satz 1 zweiter Halbsatz KStG durch entsprechende Anwendung des § 8c Absatz 1 Satz 5 bis 8 KStG bezogen auf die zum Schluss des vorangegangenen Erhebungszeitraums vorhandenen stillen Reserven
Verlust	E4009802	136	U	-	-	20.012	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei einer Personengesellschaft, soweit an dieser eine Körperschaft unmittelbar oder mittelbar über eine oder mehrere Personengesellschaften beteiligt ist: Nach § 10a Satz 10 GewStG in Verbindung mit § 8c KStG nicht abziehbarer Gewerbeverlust aus vorangegangenen Erhebungszeiträumen (laut gesonderter Ermittlung)
Verlust	E4005001	137	U	-	-	20.043	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Personengesellschaften: Wegfallende vortragsfähige Gewerbeverluste und Gewerbeverluste des laufenden Erhebungszeitraums von Mitunternehmern, die im laufenden Erhebungszeitraum ausgeschieden sind
Verlust	E4010405	138	U	-	-	20.055	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Personengesellschaften: Nach § 10a Satz 1 GewStG in Verbindung mit § 10a Satz 4 und 5 GewStG zu berücksichtigender Verlustabzug (höchstens 1 Million €) für Mitunternehmer, denen ein Anteil am vortragsfähigen Gewerbeverlust zum Schluss des vorangegangenen Erhebungszeitraums zuzurechnen ist
Verlust	E4010402	139	U	-	-	20.081	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Personengesellschaften: Nach § 10a Satz 2 GewStG in Verbindung mit § 10a Satz 4 und 5 GewStG zu berücksichtigender Verlustabzug (60 % des 1 Million € übersteigenden Gewerbeertrages) für Mitunternehmer, denen ein Anteil am vortragsfähigen Gewerbeverlust zum Schluss des vorangegangenen Erhebungszeitraums zuzurechnen ist
Verlust	E4010403	140	U	-	-	20.016	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Personengesellschaften oder Einzelunternehmen: Aufgrund der Veräußerung oder Aufgabe von Teilbetrieben wegfallender vortragsfähiger Gewerbeverlust und Gewerbeverlust des laufenden Erhebungszeitraums
Verlust	E4001202	142a	G	-	-	-	^(?=.{1,15}$)(?=.*[1-9].*)(?!0\d)\d{1,15}$	Nur bei Personengesellschaften: Anzahl der übermittelten Anlagen EMU
P_35_EStG	E4006002	143	N	-	-	20.082	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nur bei Personengesellschaften oder Einzelunternehmen: Veräußerungs- oder Aufgabegewinn nach § 18 Absatz 3 UmwStG
San	E4010901	144	U	-	-	20.001	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nach Anwendung des § 3a Absatz 3 Satz 2 Nummer 1 EStG verbleibender geminderter Sanierungsertrag im Sinne des § 3a Absatz 3 Satz 1 EStG (§ 7b Absatz 2 Satz 1, gegebenenfalls in Verbindung mit Satz 2 und 3 beziehungsweise Absatz 3 GewStG) vor Anwendung des § 7b Absatz 2 Satz 1 Nummer 1 bis 3 GewStG
Rfw_PersG_EU	E4011002	145	U	-	-	20.007	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Einheitlich ermittelter Gewerbesteuermessbetrag des Gewerbebetriebs für den gesamten Erhebungszeitraum
Rfw_PersG_EU	E4011001	146	N	-	-	20.008	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Für den Steuerschuldner (Einzelunternehmen) ermittelter Gewerbeertrag einschließlich Hinzurechnungen und Kürzungen
Rfw_PersG_EU	E4011101	147	N	-	-	20.009	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Für den Steuerschuldner (Personengesellschaft) ermittelter Gewerbeertrag einschließlich Hinzurechnungen und Kürzungen
Einbringung_P24	E4014701	147a	N	-	-	21.39	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Ermittelter Gewerbeertrag für den gesamten Erhebungszeitraum nach Anwendung des § 10a GewStG
Einbringung_P24	E4014702	147b	U	-	-	21.40	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Vortragsfähiger Gewerbeverlust zum Schluss des laufenden Erhebungszeitraums
Einbringung_P24	E4014703	147c	U	-	-	21.57	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Übergehender Gewerbeverlust wegen Einbringung nach § 24 UmwStG
VJ1_EZ	E4014801	148	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zum Schluss des vorangegangenen Erhebungszeitraums gesondert festgestellter vortragsfähiger Gewerbeverlust
VJ1_EZ	E4014901	149	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur bei Körperschaften: Zum Schluss des vorangegangenen Erhebungszeitraums gesondert festgestellter fortführungsgebundener vortragsfähiger Gewerbeverlust
VJ1_EZ	E4015001	150	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zum Schluss des vorangegangenen Erhebungszeitraums gesondert festgestellter verbleibender Zuwendungsvortrag
Steuerberater	E4001617	-	C	60	-	-	.{1,60}	(Feld wird nicht gedruckt) Ihr Zeichen/gegebenenfalls Zuordnungskriterium für Bescheiddatenübermittlung
Steuerberater/Mitwirkung	E4002002	200	J	-	-	-	1	Die Steuererklärung wurde unter Mitwirkung einer selbständig und eigenverantwortlich tätigen und zur Hilfeleistung in Steuersachen nach §§ 3 und 4 StBerG befugten Person oder Vereinigung angefertigt.
Steuerberater/Mitwirkung	E4001614	200a	C	55	-	-	.{1,55}	Telefonische Rückfragen unter Telefonnummer
Steuerberater/Mitwirkung/Anfertigung	E4001610	201	C	55	-	-	.{1,55}	Name
Steuerberater/Mitwirkung/Anfertigung	E4001611	202	C	55	-	-	.{1,55}	Vorname
Steuerberater/Mitwirkung/Anfertigung	E4001612	203	C	55	-	-	.{1,55}	Straße, Hausnummer
Steuerberater/Mitwirkung/Anfertigung	E4001613	204	C	55	-	-	.{1,55}	Postleitzahl, Ort
Steuerberater/Mitwirkung/Anfertigung	E4001615	206	C	55	-	-	.{1,55}	zusätzliche Angaben
Steuerberater/Mitwirkung/Anfertigung	E4001616	207	C	60	-	-	.{1,60}	Mandantennummer
Steuerberater/Mitwirkung/Anfertigung	E4001618	208	C	55	-	-	.{1,55}	Bearbeiterkennzeichen
"""

# The JD, sheet „BEG - Felder“.
_BEG_2025 = r"""
Allg	E4050101	1	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer (soweit im Inland steuerlich erfasst)
Allg	E4050506	1a	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
Allg	E4050504	1b	C	12	-	-	^(?=.{12,12}$)[A-Z]{2}[A-Z0-9]{9}[0-9]{1}	ISIN (soweit vorhanden)
Allg	E4050201	2	C	25	Ja	-	.{1,25}	Bezeichnung der Körperschaft
Allg/Adr	E4050301	3	C	25	-	-	.{1,25}	Straße
Allg/Adr	E4050401	4	C	4	-	-	^(?=.{1,4}$)[0-9]+	Hausnummer
Allg/Adr	E4050402	4	C	6	-	-	.{1,6}	Hausnummerzusatz
Allg/Adr	E4050403	4	C	25	-	-	.{1,25}	Adressergänzung
Allg/Adr	E4050501	5	C	5	-	-	^(?=.{5,5}$)([0]{1}[1-9]{1}[0-9]{3})|([1-9]{1}[0-9]{4})	Postleitzahl
Allg/Adr	E4050505	5	C	12	-	-	.{1,12}	Postleitzahl (Ausland)
Allg/Adr	E4050502	5	C	20	-	-	.{1,20}	Ort
Allg/Adr	E4050503	5a	C	50	-	-	.{1,50}	Ansässigkeitsstaat
Ausschuett	E4050601	6	U	-	Ja	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Gesamtbetrag der im Wirtschaftsjahr erhaltenen Bezüge im Sinne des § 20 Absatz 1 Nummer 1, 2, 9 und 10 Buchstabe a EStG aus dieser Beteiligung
Ausschuett	E4050701	7	H	-	-	-	\Q1\E|\Q2\E|\Q3\E	Die Beteiligung erfüllt die Voraussetzungen des
Ausschuett	E4050801	8	G	-	-	-	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Mit den Bezügen laut Zeile 6 in unmittelbarem Zusammenhang stehende Aufwendungen im Sinne des § 8 Nummer 1 GewStG
Ausschuett	E4050901	9	G	-	-	-	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Mit den Bezügen laut Zeile 6 in unmittelbarem Zusammenhang stehende andere Aufwendungen
Ausschuett	E4051001	10	C	10	-	-	^(?=.{8,10}$)(?!0\d)\d{1,3}(,\d{6,6})$	Nur wenn die Beteiligung im Sonderbetriebsvermögen gehalten wird: Bezogen auf die im Sonderbetriebsvermögen gehaltene Beteiligung sind Körperschaften unmittelbar oder mittelbar über eine Personengesellschaft beteiligt in Höhe von (Prozent)
Ausschuett	E4051101	11	C	10	-	-	^(?=.{8,10}$)(?!0\d)\d{1,3}(,\d{6,6})$	Nur wenn die Beteiligung im Sonderbetriebsvermögen gehalten wird: Bezogen auf die im Sonderbetriebsvermögen gehaltene Beteiligung sind natürliche Personen unmittelbar oder mittelbar über eine Personengesellschaft beteiligt in Höhe von (100 % abzüglich Prozentsatz laut Zeile 10)
Ang_Bet_Koe	E4051201	12	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bezüge laut Zeile 6, die die Voraussetzungen der Steuerbefreiung nach § 8b Absatz 1 und 4 KStG oder nach DBA erfüllen
Ang_Bet_Koe	E4051301	13	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur für Organgesellschaften: Steuerfreie Bezüge nach § 8b Absatz 1 und 4 KStG oder nach DBA (Betrag laut Zeile 12 multipliziert mit dem Prozentsatz laut Zeile 71 des Vordrucks GewSt 1 A)
Ang_Bet_Koe	E4051401	14	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bezüge laut Zeile 6, die die Voraussetzungen der Steuerbefreiung nach § 8b Absatz 1 und 4 KStG oder nach DBA nicht erfüllen (Betrag laut Zeile 6 abzüglich Betrag laut Zeile 12)
Ang_Bet_Koe	E4051501	15	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Hinzurechnungsbetrag nach § 8 Nummer 5 GewStG (wenn in Zeile 7 keine Eintragung gemacht wurde: 95 % des Betrages laut Zeile 12; bei Mitunternehmerschaften und Organgesellschaften: zusätzlich multipliziert mit dem Prozentsatz laut Zeile 70 oder 71 des Vordrucks GewSt 1 A, bei Eintragung in Zeile 10: stattdessen zusätzlich multipliziert mit dem Prozentsatz laut Zeile 10)
Ang_Bet_Koe	E4051601	16	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausgangsbetrag für eine Kürzung nach § 9 Nummer 2a, 7 oder 8 GewStG (Betrag laut Zeile 14; nur ausfüllen, wenn in Zeile 7 und Zeile 14 eine Eintragung gemacht wurde)
Ang_Bet_Koe	E4051701	17	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mit den Beträgen laut Zeile 16 in unmittelbarem Zusammenhang stehende Aufwendungen im Sinne des § 8 Nummer 1 GewStG (Betrag laut Zeile 8, höchstens Betrag laut Zeile 16)
Ang_Bet_Koe	E4051801	18	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mit den Beträgen laut Zeile 16 in unmittelbarem Zusammenhang stehende andere Aufwendungen (Betrag laut Zeile 9, höchstens Betrag laut Zeile 16 abzüglich Betrag laut Zeile 17)
Ang_Bet_Koe	E4051901	19	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Kürzung nach § 9 Nummer 2a, 7 und 8 GewStG (Betrag laut Zeile 16 abzüglich Summe der Beträge laut Zeilen 17 und 18; bei Mitunternehmerschaften und Organgesellschaften: multipliziert mit dem Prozentsatz laut Zeile 70 oder 71 des Vordrucks GewSt 1 A, bei Eintragung in Zeile 10: stattdessen multipliziert mit dem Prozentsatz laut Zeile 10)
Ang_Bet_Koe	E4052001	20	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Kürzung des Hinzurechnungsbetrages nach § 8 Nummer 1 GewStG aufgrund des § 9 Nummer 2a Satz 3 zweiter Halbsatz GewStG, § 9 Nummer 7 Satz 2 beziehungsweise § 9 Nummer 8 Satz 2 GewStG (Betrag laut Zeile 17; bei Mitunternehmerschaften und Organgesellschaften: multipliziert mit dem Prozentsatz laut Zeile 70 oder 71 des Vordrucks GewSt 1 A, bei Eintragung in Zeile 10: stattdessen multipliziert mit dem Prozentsatz laut Zeile 10)
Ang_Bet_nat_P	E4052101	21	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bezüge laut Zeile 6, die die Voraussetzungen der Steuerbefreiung nach § 3 Nummer 40 EStG erfüllen
Ang_Bet_nat_P	E4052201	22	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Bezüge nach § 3 Nummer 40 EStG gekürzt um Betriebsausgaben nach § 3c Absatz 2 EStG vor Anwendung des Teileinkünfteverfahrens (Betrag laut Zeile 21 abzüglich der Summe der Beträge laut Zeilen 8 und 9 multipliziert mit dem Prozentsatz laut Zeile 72 des Vordrucks GewSt 1 A, bei Eintragung in Zeile 11: stattdessen multipliziert mit dem Prozentsatz laut Zeile 11)
Ang_Bet_nat_P	E4052301	23	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hinzurechnungsbetrag nach § 8 Nummer 5 GewStG (wenn in Zeile 7 keine Eintragung gemacht wurde: 40 % des Betrages laut Zeile 21; abzüglich 40 % der Beträge laut Zeilen 8 und 9, bei Mitunternehmerschaften und Organgesellschaften: zusätzlich multipliziert mit dem Prozentsatz laut Zeile 72 des Vordrucks GewSt 1 A, bei Eintragung in Zeile 11: stattdessen zusätzlich multipliziert mit dem Prozentsatz laut Zeile 11)
Ang_Bet_nat_P	E4052401	24	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausgangsbetrag für eine Kürzung nach § 9 Nummer 2a, 7 oder 8 GewStG (Betrag laut Zeile 6; nur ausfüllen, wenn in Zeile 7 der Wert 1 [= § 9 Nummer 2a GewStG], 2 [= § 9 Nummer 7 GewStG] oder 3 [= § 9 Nummer 8 GewStG] eingetragen ist)
Ang_Bet_nat_P	E4052501	25	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mit den Beträgen laut Zeile 24 in unmittelbarem Zusammenhang stehende Aufwendungen im Sinne des § 8 Nummer 1 GewStG (Betrag laut Zeile 8, höchstens Betrag laut Zeile 24)
Ang_Bet_nat_P	E4052601	26	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mit den Beträgen laut Zeile 24 in unmittelbarem Zusammenhang stehende andere Aufwendungen (Betrag laut Zeile 9, höchstens Betrag laut Zeile 24 abzüglich Betrag laut Zeile 25)
Ang_Bet_nat_P	E4052701	27	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Kürzung nach § 9 Nummer 2a, 7 und 8 GewStG vor Anwendung des Teileinkünfteverfahrens (Betrag laut Zeile 24 abzüglich Summe der Beträge laut Zeilen 25 und 26; bei Mitunternehmerschaften und Organgesellschaften: multipliziert mit dem Prozentsatz laut Zeile 72 des Vordrucks GewSt 1 A, bei Eintragung in Zeile 11: stattdessen multipliziert mit dem Prozentsatz laut Zeile 11)
Ang_Bet_nat_P	E4052801	28	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Kürzung des Hinzurechnungsbetrages nach § 8 Nummer 1 GewStG aufgrund des § 9 Nummer 2a Satz 3 zweiter Halbsatz GewStG, § 9 Nummer 7 Satz 2 beziehungsweise § 9 Nummer 8 Satz 2 GewStG (Betrag laut Zeile 25; bei Mitunternehmerschaften und Organgesellschaften: multipliziert mit dem Prozentsatz laut Zeile 72 des Vordrucks GewSt 1 A, bei Eintragung in Zeile 11: stattdessen multipliziert mit dem Prozentsatz laut Zeile 11)
"""

# The rules of the JD that Steuerbote checks (steuerbote.eric.simulation.gewst), from the sheets „<Vordruck> -
# Regeln“, without their Fehler- /Hinweistext (module docstring).
_RULES_2025 = (
	Rule(
		"40000",
		"GewSt_40000",
		"",
		(
			"/GewSt1A/Einbringung_P24/E4014701",
			"/GewSt1A/Einbringung_P24/E4014702",
			"/GewSt1A/Einbringung_P24/E4014703",
			"/GewSt1A/Gew_Ertr/Oer_Rundfunk/E4004811",
			"/GewSt1A/Gew_Ertr/P_5a_EStG/E4004202",
			"/GewSt1A/Gewinn/E4001703",
			"/GewSt1A/Gewinn/E4003903",
		),
	),
	Rule(
		"40038",
		"GewSt_2021_40038",
		"",
		("/GewSt1A/Ang_Gew_Betr/Betr_St/E4001506", "/GewSt1A/Rechtsform/E4001201"),
	),
	Rule(
		"40047",
		"GewSt_2021_40047",
		"",
		(
			"/GewSt1A/Ang_Gew_Betr/Betr_St/E4001102",
			"/GewSt1A/Ang_Gew_Betr/Betr_St/E4001506",
			"/GewSt1A/Rechtsform/E4001201",
		),
	),
	Rule(
		"40029",
		"GewSt_2021_40029",
		"",
		(
			"/GewSt1A/Ang_Gew_Betr/Betr_St/E4001102",
			"/GewSt1A/Ang_Gew_Betr/Betr_St/E4001110",
			"/GewSt1A/Ang_Gew_Betr/Betr_St/E4001111",
		),
	),
	Rule(
		"40051",
		"GewSt_2025_40051",
		"",
		("/GewSt1A/Kuerz/Zuw/Stb_Zweck/Einz/E4009221", "/GewSt1A/Kuerz/Zuw/Stb_Zweck/Sum/E4003403"),
	),
	Rule(
		"40052",
		"GewSt_2025_40052",
		"",
		("/GewSt1A/Kuerz/Zuw/Stb_Zweck/Einz/E4009221", "/GewSt1A/Kuerz/Zuw/Stb_Zweck/Sum/E4003403"),
	),
	Rule(
		"40053",
		"GewSt_2025_40053",
		"",
		("/GewSt1A/Kuerz/Zuw/Stb_Zweck/Einz/E4009221", "/GewSt1A/Kuerz/Zuw/Stb_Zweck/Sum/E4003403"),
	),
	Rule(
		"40054",
		"GewSt_2025_40054",
		"",
		(
			"/GewSt1A/Kuerz/Zuw/Stb_Zweck/Einz/E4009220",
			"/GewSt1A/Kuerz/Zuw/Stb_Zweck/Einz/E4009221",
			"/GewSt1A/Kuerz/Zuw/Stb_Zweck/Einz/E4009222",
		),
	),
	Rule(
		"40954",
		"BEG_40954",
		"",
		(
			"/BEG/Ang_Bet_Koe/E4051201",
			"/BEG/Ang_Bet_Koe/E4051501",
			"/BEG/Ausschuett/E4050701",
			"/BEG/Ausschuett/E4051001",
			"/GewSt1A/Ang_Gew_Betr/OG/E4001501",
			"/GewSt1A/Gew_Ant_Koe/E4006104",
			"/GewSt1A/Gew_Ant_Koe/E4006201",
			"/GewSt1A/Rechtsform/E4000501",
			"/GewSt1A/Rechtsform/E4001405",
		),
	),
	Rule(
		"40958",
		"BEG_40958",
		"",
		(
			"/BEG/Ang_Bet_Koe/E4051601",
			"/BEG/Ang_Bet_Koe/E4051701",
			"/BEG/Ausschuett/E4050801",
			"/BEG/Ausschuett/E4051001",
			"/GewSt1A/Ang_Gew_Betr/OG/E4001501",
			"/GewSt1A/Gew_Ant_Koe/E4006104",
			"/GewSt1A/Gew_Ant_Koe/E4006201",
			"/GewSt1A/Rechtsform/E4000501",
			"/GewSt1A/Rechtsform/E4001405",
		),
	),
	Rule(
		"40959",
		"BEG_40959",
		"",
		(
			"/BEG/Ang_Bet_Koe/E4051601",
			"/BEG/Ang_Bet_Koe/E4051701",
			"/BEG/Ang_Bet_Koe/E4051801",
			"/BEG/Ausschuett/E4050901",
			"/BEG/Ausschuett/E4051001",
			"/GewSt1A/Ang_Gew_Betr/OG/E4001501",
			"/GewSt1A/Gew_Ant_Koe/E4006104",
			"/GewSt1A/Gew_Ant_Koe/E4006201",
			"/GewSt1A/Rechtsform/E4000501",
			"/GewSt1A/Rechtsform/E4001405",
		),
	),
	Rule(
		"40965",
		"BEG_40965",
		"",
		(
			"/BEG/Ang_Bet_Koe/E4051601",
			"/BEG/Ang_Bet_Koe/E4051701",
			"/BEG/Ang_Bet_Koe/E4051801",
			"/BEG/Ang_Bet_Koe/E4051901",
			"/BEG/Ausschuett/E4051001",
			"/GewSt1A/Ang_Gew_Betr/OG/E4001501",
			"/GewSt1A/Gew_Ant_Koe/E4006104",
			"/GewSt1A/Gew_Ant_Koe/E4006201",
			"/GewSt1A/Rechtsform/E4000501",
			"/GewSt1A/Rechtsform/E4001405",
		),
	),
)

FORMS = (Form("GewSt1A", mandatory=True), Form("BEG", count=99), Form("Vorsatz", mandatory=True))
"""The Vordrucke of a GmbH or UG in the order of E20-2025.xsd, with the „max. lfd. Nr. Vordruck“ and the
Pflichtvordrucke of the JD, sheet „Allg. Information“."""

CATALOGUES: MappingProxyType[int, FormCatalogue] = MappingProxyType(
	{
		2026: checked(
			FormCatalogue(
				datenart=gewst(2026),
				source="Jahresdokumentation_E20_2025.ods, Versionslabel 11.0, provisionally for 2026",
				forms=FORMS,
				fields=(*table_fields("GewSt1A", _GEWST1A_2025), *table_fields("BEG", _BEG_2025)),
				rules=_RULES_2025,
			),
			STEPS,
		)
	}
)

RECHTSFORMEN: MappingProxyType[int, MappingProxyType[str, MappingProxyType[str, str]]] = MappingProxyType(
	{
		2026: MappingProxyType(
			{
				"350": MappingProxyType({"Rechtsformgruppe": "KOE"}),
				"370": MappingProxyType({"Rechtsformgruppe": "KOE"}),
			}
		)
	}
)
"""The categories of the Rechtsformen Steuerbote files, by EZ: RECHTSFORM_GEWERBESTEUER_V2 of the JD 2025, sheet
„Benutzerdefinierte Typen“."""

STEP_FIELDS: MappingProxyType[str, str] = MappingProxyType(
	{step.key: step.field for step in STEPS if step.field is not None}
)
"""The Feldkennung of each step of steuerbote.gewst.chain that has one."""

PROFIT = "E4001703"
BEG_NAME = "E4050201"
BEG_DIVIDENDS = "E4050601"
BEG_PARAGRAPH = "E4050701"
BEG_FINANCING_COSTS = "E4050801"
BEG_OTHER_COSTS = "E4050901"
BEG_EXEMPT = "E4051201"
BEG_NOT_EXEMPT = "E4051401"
BEG_CUT_BASE = "E4051601"
BEG_WITH_CUT_BASE = MappingProxyType(
	{"E4051701": BEG_FINANCING_COSTS, "E4051801": BEG_OTHER_COSTS, "E4051901": None}
)
"""Lines 17, 18 and 19 of Anlage BEG, which go beside line 16, each with the line it needs filed as well."""
LICENCES = "E4003703"
LICENCES_NONRESIDENTS = "E4004103"
# Anlage BEG lines 15 to 19, by the attribute of BegLine that holds each.
BEG_LINES = (
	("addback", "E4051501"),
	("cut_base", "E4051601"),
	("financing_costs", "E4051701"),
	("other_costs", "E4051801"),
	("cut", "E4051901"),
)


def catalogue_for(year: int) -> FormCatalogue:
	"""The catalogue of the EZ; UnknownYearError for an EZ Steuerbote has none for."""
	try:
		return CATALOGUES[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in CATALOGUES)
		raise UnknownYearError(
			f"no Vordrucke of the Gewerbesteuer for {year}; known years: {known}"
		) from None


def vordrucke(result: GewstResult) -> tuple[Vordruck, ...]:
	"""GewSt1A with the amounts of a computed EZ and an Anlage BEG for each holding; see the module docstring."""
	amounts: dict[str, object] = {}
	for step in STEPS:
		declared = result.lines[step.key].declared
		if step.field is not None and (declared or step.field == PROFIT):
			amounts[step.field] = declared
	if LICENCES in amounts:
		amounts[LICENCES_NONRESIDENTS] = ZERO
	return (
		Vordruck("GewSt1A", entries(amounts)),
		*(Vordruck("BEG", tuple(_beg(line))) for line in result.beg),
	)


def beg_lines(amounts: Mapping[str, Decimal], written: set[str]) -> list[Entry]:
	"""Lines 15 to 19 of Anlage BEG by their Feldkennung, after the lines ``written`` above them, which it extends.

	A line that is not zero goes, and so does one a rule of the Jahresdokumentation GewSt 2025 wants beside another,
	at zero as well: line 16 beside lines 7 and 14 (rules 40946, 40956), lines 17 and 18 beside line 16 where lines 8
	and 9 are filed, and line 19 beside line 16 (rules 40947 to 40949); validation with ERiC 44.3.6.0."""
	found = []
	for _, feldkennung in BEG_LINES:
		amount = amounts.get(feldkennung, ZERO)
		if feldkennung == BEG_CUT_BASE:
			required = {BEG_PARAGRAPH, BEG_NOT_EXEMPT} <= written
		else:
			source = BEG_WITH_CUT_BASE.get(feldkennung, "")
			required = source != "" and BEG_CUT_BASE in written and (source is None or source in written)
		if amount or required:
			found.append(Entry(feldkennung, amount))
			written.add(feldkennung)
	return found


def _beg(line: BegLine) -> Iterable[Entry]:
	holding = line.holding.result
	found = [Entry(BEG_NAME, holding.holding.name), Entry(BEG_DIVIDENDS, line.dividends)]
	if line.paragraph is not None:
		found.append(Entry(BEG_PARAGRAPH, str(line.paragraph)))
		for feldkennung, costs in (
			(BEG_FINANCING_COSTS, holding.financing_costs),
			(BEG_OTHER_COSTS, holding.other_costs),
		):
			if half_up_euro(costs):
				found.append(Entry(feldkennung, half_up_euro(costs)))
	if line.exempt or line.not_exempt:
		found += [Entry(BEG_EXEMPT, line.exempt), Entry(BEG_NOT_EXEMPT, line.not_exempt)]
	amounts = {feldkennung: getattr(line, attribute) for attribute, feldkennung in BEG_LINES}
	return (*found, *beg_lines(amounts, {entry.feldkennung for entry in found}))
