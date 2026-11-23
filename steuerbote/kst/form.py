"""The Vordrucke of the Körperschaftsteuererklärung as ELSTER takes them, per VZ, and the fields of the lines that
steuerbote.kst.chain computes.

Source is the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/), cited as JD for
Jahresdokumentation_E30_2025.ods (Versionslabel 7.0) with its sheets „Allg. Information“, „<Vordruck> - Felder“,
„<Vordruck> - Kennzahlen“, „<Vordruck> - Regeln“ and „Benutzerdefinierte Typen“, and the schema E30-2025.xsd. ERiC
44.3.6.0 knows the VZ 2015 to 2025 only, so VZ 2026 takes the Vordrucke of 2025 until ELSTER publishes the
Jahresdokumentation 2026 (steuerbote.kst.years: ``provisional``, ``documentation_year`` 2025).

Vordrucke. A GmbH or UG of Steuerbote's scope files KSt1, GK, ZVE, Z, Verluste, WA and KSt1F with the Vorsatz, in the
order of the schema (FORMS). Each Form has the „max. lfd. Nr. Vordruck“ of the sheet „Allg. Information“, two of
Anlage GK and KSt 1 F for a VZ with two Wirtschaftsjahre, and its Pflichtvordruck mark: KSt1 and the Vorsatz. Which of
the others a GmbH has to file, the rules say: Anlage GK (8906010), Anlage ZVE (8900744), Anlage WA (8912208) and KSt 1 F
(8931022) always, Anlage Verluste and Anlage Z with a carry-forward or an amount of the year.

Fields. Each table below holds the current fields of one sheet „<Vordruck> - Felder“ in the order of the JD, which is
the order of the leaves of the Vordruck in the schema, one field per line with nine columns separated by tabs:
Kontext, Name (the Feldkennung), Vordruckzeile, Formatkennzeichen, Max. Länge of a text, Pflichtfeld, Kennzahl
(Sachbereich and Kennzahl of the sheet „<Vordruck> - Kennzahlen“, such as 13.110), Format als regulärer Ausdruck and
Beschreibung, with „-“ for an empty cell and the paragraphs of a Beschreibung joined by a blank. The Beschreibung of
each field is also its Drucktext, the text of the printed form. A Listenfeld (H) takes the values its pattern quotes. Anlage GK and KSt 1 F begin with the Indexfeld WJ, the Wirtschaftsjahr WJ1 or
WJ2, which is no field of a Vordruck but its index: steuerbote.elster.kst_xml writes it.

Rules. The catalogue holds the rules of the JD that Steuerbote checks itself before ERiC
(steuerbote.eric.simulation.kst), with their Fehlercode, name, the fields they check and whether they are a Hinweis:
the Vordrucke and fields a GmbH has to file, and the sums and roundings the computation makes. Their Fehler-
/Hinweistext is empty: it stays in the JD, which carries no licence that allows passing it on, as for USt 2 A
(steuerbote.eric.simulation.ust).

Rechtsform. Rules ask for categories of the Rechtsform of KSt 1 line 9 (E8001105), the enumeration
RECHTSFORM_KOERPERSCHAFTEN_V3 of the sheet „Benutzerdefinierte Typen“: RF_Gruppe 1 for the Kapitalgesellschaften, NurG
1 for those with Einkünfte aus Gewerbebetrieb only. RECHTSFORMEN holds them for the two Rechtsformen Steuerbote files,
350 for the GmbH and 370 for the UG (haftungsbeschränkt).

Lines. Each step of steuerbote.kst.chain names its form, line and Feldkennung (STEP_FIELDS). vordrucke() turns a
KstResult into the Vordrucke GK, ZVE, WA, Verluste and Z with the amounts the computation gives, as the rules take them:
- the declared amount of each step with a field, a zero left out but for the amounts the rules require: Anlage GK
  lines 11 and 300 (8900070, 8906061) and Anlage ZVE lines 2, 32, 53 and 70 (8900548, 8900100, 8900818, 8900836);
- Anlage ZVE line 71 with its Vorspalte, the zu versteuerndes Einkommen taxed at the rate of § 23 Absatz 1 KStG
  (E8007504), which goes with the tax (8900361) and makes line 70 (8900330), for a positive zu versteuerndes
  Einkommen; otherwise neither, since the tax is then 0 (8900570);
- the Einzelangaben of lines 151 to 155 for each holding whose dividends § 8b Absatz 1 KStG exempts: name, share at
  the start of the calendar year, kind (1 for a direct holding, 2 for an acquisition of § 8b Absatz 4 Satz 6 KStG) and
  dividends (8956008), which line 156 sums (8956007, 8956060);
- Anlage Verluste with a Verlustvortrag or a loss: line 11, the loss of line 19 with the Verlustrücktrag of line 20,
  or the positive Gesamtbetrag der Einkünfte of line 22 with lines 21 and 25 in both columns, lines 26 and 27 where the
  minimum taxation leaves something, and line 28 (8900184, 8900170, 8900347, 8918391, 8918404, 8918405, 8918406,
  8900134, 8900344, 8992218);
- Anlage Z with a Zuwendungsvortrag or Zuwendungen: lines 1 and 5 to 8 and, once known, line 10 (8900204, 8901000,
  8900351, 8901004).
kst1f() turns the steuerliches Einlagekonto of steuerbote.kst.einlagekonto into KSt 1 F, with the lines that module
names: 42 always (8924512) and 152 (8920227, 8924445), 43 and the Sonderausweis of line 152 where there is one, 11 and
12 with the Leistungen, 17 to 20 once the equity of the previous year is known (8920011, 8920021), 46 to 50 where the
Leistungen exceed the ausschüttbarer Gewinn (8920012, 8920013, 8920019, 8924077, 8924079, 8924401, 8920076), and the
Einlagen of lines 91, 92 and 95.
What the computation does not know comes from the company and its records: KSt 1, the Einzelangaben of the sales,
write-ups and write-downs of lines 161 to 187 (8956070, 8956072, 8905507, 8905516), the receipts of Anlage Z line 5
(8901013) and Anlage WA line 15; Vordruck.extended() adds them to a Vordruck.

This module is pure Python and never imports Frappe.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from steuerbote.elster.erklaerung import Field, Form, FormCatalogue, Rule
from steuerbote.eric.datenart import kst
from steuerbote.kst.chain import STEPS, KstResult, Step
from steuerbote.kst.einlagekonto import Einlagekonto
from steuerbote.kst.holdings import Exemption
from steuerbote.kst.losses import Donations, LossDeduction
from steuerbote.ustva.rounding import ZERO
from steuerbote.ustva.years import UnknownYearError

EMPTY = "-"
_QUOTED = re.compile(r"\\Q(.*?)\\E")

# The JD, sheet „KSt1 - Felder“.
_KST1_2025 = r"""
-	E8000015	-	X	-	-	-	X	Erklärung zur gesonderten und einheitlichen Feststellung des dem Organträger zuzurechnenden Einkommens der Organgesellschaft und damit zusammenhängender anderer Besteuerungsgrundlagen (§ 14 Absatz 5 KStG)
-	E8000016	-	X	-	-	-	X	Erklärung zur gesonderten Feststellung des steuerlichen Einlagekontos (§ 27 Absatz 2 KStG) und des durch Umwandlung von Rücklagen entstandenen Nennkapitals (§ 28 Absatz 1 Satz 3 KStG)
-	E8000012	-	X	-	-	-	X	Belege werden nachgereicht
Allgemein	E8000101	1	C	103	Ja	-	.{1,103}	Bezeichnung der Körperschaft, Personenvereinigung oder Vermögensmasse
Allgemein	E8000102	1a	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
Steuerpflicht	E8000501	6	C	24	Ja	-	.{1,24}	Ort der Geschäftsleitung nach § 10 AO
Steuerpflicht	E8000603	6	H	-	-	-	\QAfghanistan\E|\QÄgypten\E|\QAlbanien\E|\QAlgerien\E|\QAndorra\E|\QAngola\E|\QAntigua und Barbuda\E|\QÄquatorialguinea\E|\QArgentinien\E|\QArmenien\E|\QAserbaidschan\E|\QÄthiopien\E|\QAustralien\E|\QBahamas\E|\QBahrain\E|\QBangladesch\E|\QBarbados\E|\QBelgien\E|\QBelize\E|\QBenin\E|\QBhutan\E|\QBolivien\E|\QBosnien und Herzegowina\E|\QBotsuana\E|\QBrasilien\E|\QBrunei Darussalam\E|\QBulgarien\E|\QBurkina Faso\E|\QBurundi\E|\QChile\E|\QChina\E|\QCookinseln\E|\QCosta Rica\E|\QCote d'Ivoire\E|\QDänemark\E|\QDominica\E|\QDominikanische Republik\E|\QDschibuti\E|\QEcuador\E|\QEl Salvador\E|\QEritrea\E|\QEstland\E|\QEswatini\E|\QFidschi\E|\QFinnland\E|\QFrankreich\E|\QGabun\E|\QGambia\E|\QGeorgien\E|\QGhana\E|\QGrenada\E|\QGriechenland\E|\QGuatemala\E|\QGuinea\E|\QGuinea-Bissau\E|\QGuyana\E|\QHaiti\E|\QHonduras\E|\QIndien\E|\QIndonesien\E|\QIrak\E|\QIran\E|\QIrland\E|\QIsland\E|\QIsrael\E|\QItalien\E|\QJamaika\E|\QJapan\E|\QJemen\E|\QJordanien\E|\QKambodscha\E|\QKamerun\E|\QKanada\E|\QKap Verde\E|\QKasachstan\E|\QKatar\E|\QKenia\E|\QKirgisistan\E|\QKiribati\E|\QKolumbien\E|\QKomoren\E|\QKongo\E|\QKongo, Demokratische Republik\E|\QKorea, Demokratische Volksrepublik\E|\QKorea, Republik\E|\QKosovo\E|\QKroatien\E|\QKuba\E|\QKuwait\E|\QLaos\E|\QLesotho\E|\QLettland\E|\QLibanon\E|\QLiberia\E|\QLibyen\E|\QLiechtenstein\E|\QLitauen\E|\QLuxemburg\E|\QMadagaskar\E|\QMalawi\E|\QMalaysia\E|\QMalediven\E|\QMali\E|\QMalta\E|\QMarokko\E|\QMarshallinseln\E|\QMauretanien\E|\QMauritius\E|\QMexiko\E|\QFöderierte Staaten von Mikronesien\E|\QMoldau\E|\QMonaco\E|\QMongolei\E|\QMontenegro\E|\QMosambik\E|\QMyanmar\E|\QNamibia\E|\QNauru\E|\QNepal\E|\QNeuseeland\E|\QNicaragua\E|\QNiederlande\E|\QNiger\E|\QNigeria\E|\QNiue\E|\QNordmazedonien\E|\QNorwegen\E|\QOman\E|\QÖsterreich\E|\QPakistan\E|\QPalau\E|\QPanama\E|\QPapua-Neuguinea\E|\QParaguay\E|\QPeru\E|\QPhilippinen\E|\QPolen\E|\QPortugal\E|\QRuanda\E|\QRumänien\E|\QRussische Föderation\E|\QSalomonen\E|\QSambia\E|\QSamoa\E|\QSan Marino\E|\QSao Tome und Principe\E|\QSaudi-Arabien\E|\QSchweden\E|\QSchweiz\E|\QSenegal\E|\QSerbien\E|\QSeychellen\E|\QSierra Leone\E|\QSimbabwe\E|\QSingapur\E|\QSlowakei\E|\QSlowenien\E|\QSomalia\E|\QSpanien\E|\QSri Lanka\E|\QSt. Kitts und Nevis\E|\QSt. Lucia\E|\QSt. Vincent und die Grenadinen\E|\QSüdafrika\E|\QSudan\E|\QSüdsudan\E|\QSurinam\E|\QSyrien\E|\QTadschikistan\E|\QTansania\E|\QThailand\E|\QTimor-Leste\E|\QTogo\E|\QTonga\E|\QTrinidad und Tobago\E|\QTschad\E|\QTschechische Republik\E|\QTunesien\E|\QTürkei\E|\QTurkmenistan\E|\QTuvalu\E|\QUganda\E|\QUkraine\E|\QUngarn\E|\QUruguay\E|\QUSA\E|\QUsbekistan\E|\QVanuatu\E|\QVatikanstadt\E|\QVenezuela\E|\QVereinigte Arabische Emirate\E|\QVereinigtes Königreich\E|\QVietnam\E|\QWeißrussland\E|\QZentralafrikanische Republik\E|\QZypern\E|\Q* nicht in Liste / Unterlagen werden eingereicht *\E	Staat (nur angeben, wenn im Ausland)
Steuerpflicht	E8000601	7	C	24	Ja	-	.{1,24}	Ort des Sitzes nach § 11 AO
Steuerpflicht	E8000702	7	H	-	-	-	\QAfghanistan\E|\QÄgypten\E|\QAlbanien\E|\QAlgerien\E|\QAndorra\E|\QAngola\E|\QAntigua und Barbuda\E|\QÄquatorialguinea\E|\QArgentinien\E|\QArmenien\E|\QAserbaidschan\E|\QÄthiopien\E|\QAustralien\E|\QBahamas\E|\QBahrain\E|\QBangladesch\E|\QBarbados\E|\QBelgien\E|\QBelize\E|\QBenin\E|\QBhutan\E|\QBolivien\E|\QBosnien und Herzegowina\E|\QBotsuana\E|\QBrasilien\E|\QBrunei Darussalam\E|\QBulgarien\E|\QBurkina Faso\E|\QBurundi\E|\QChile\E|\QChina\E|\QCookinseln\E|\QCosta Rica\E|\QCote d'Ivoire\E|\QDänemark\E|\QDominica\E|\QDominikanische Republik\E|\QDschibuti\E|\QEcuador\E|\QEl Salvador\E|\QEritrea\E|\QEstland\E|\QEswatini\E|\QFidschi\E|\QFinnland\E|\QFrankreich\E|\QGabun\E|\QGambia\E|\QGeorgien\E|\QGhana\E|\QGrenada\E|\QGriechenland\E|\QGuatemala\E|\QGuinea\E|\QGuinea-Bissau\E|\QGuyana\E|\QHaiti\E|\QHonduras\E|\QIndien\E|\QIndonesien\E|\QIrak\E|\QIran\E|\QIrland\E|\QIsland\E|\QIsrael\E|\QItalien\E|\QJamaika\E|\QJapan\E|\QJemen\E|\QJordanien\E|\QKambodscha\E|\QKamerun\E|\QKanada\E|\QKap Verde\E|\QKasachstan\E|\QKatar\E|\QKenia\E|\QKirgisistan\E|\QKiribati\E|\QKolumbien\E|\QKomoren\E|\QKongo\E|\QKongo, Demokratische Republik\E|\QKorea, Demokratische Volksrepublik\E|\QKorea, Republik\E|\QKosovo\E|\QKroatien\E|\QKuba\E|\QKuwait\E|\QLaos\E|\QLesotho\E|\QLettland\E|\QLibanon\E|\QLiberia\E|\QLibyen\E|\QLiechtenstein\E|\QLitauen\E|\QLuxemburg\E|\QMadagaskar\E|\QMalawi\E|\QMalaysia\E|\QMalediven\E|\QMali\E|\QMalta\E|\QMarokko\E|\QMarshallinseln\E|\QMauretanien\E|\QMauritius\E|\QMexiko\E|\QFöderierte Staaten von Mikronesien\E|\QMoldau\E|\QMonaco\E|\QMongolei\E|\QMontenegro\E|\QMosambik\E|\QMyanmar\E|\QNamibia\E|\QNauru\E|\QNepal\E|\QNeuseeland\E|\QNicaragua\E|\QNiederlande\E|\QNiger\E|\QNigeria\E|\QNiue\E|\QNordmazedonien\E|\QNorwegen\E|\QOman\E|\QÖsterreich\E|\QPakistan\E|\QPalau\E|\QPanama\E|\QPapua-Neuguinea\E|\QParaguay\E|\QPeru\E|\QPhilippinen\E|\QPolen\E|\QPortugal\E|\QRuanda\E|\QRumänien\E|\QRussische Föderation\E|\QSalomonen\E|\QSambia\E|\QSamoa\E|\QSan Marino\E|\QSao Tome und Principe\E|\QSaudi-Arabien\E|\QSchweden\E|\QSchweiz\E|\QSenegal\E|\QSerbien\E|\QSeychellen\E|\QSierra Leone\E|\QSimbabwe\E|\QSingapur\E|\QSlowakei\E|\QSlowenien\E|\QSomalia\E|\QSpanien\E|\QSri Lanka\E|\QSt. Kitts und Nevis\E|\QSt. Lucia\E|\QSt. Vincent und die Grenadinen\E|\QSüdafrika\E|\QSudan\E|\QSüdsudan\E|\QSurinam\E|\QSyrien\E|\QTadschikistan\E|\QTansania\E|\QThailand\E|\QTimor-Leste\E|\QTogo\E|\QTonga\E|\QTrinidad und Tobago\E|\QTschad\E|\QTschechische Republik\E|\QTunesien\E|\QTürkei\E|\QTurkmenistan\E|\QTuvalu\E|\QUganda\E|\QUkraine\E|\QUngarn\E|\QUruguay\E|\QUSA\E|\QUsbekistan\E|\QVanuatu\E|\QVatikanstadt\E|\QVenezuela\E|\QVereinigte Arabische Emirate\E|\QVereinigtes Königreich\E|\QVietnam\E|\QWeißrussland\E|\QZentralafrikanische Republik\E|\QZypern\E|\Q* nicht in Liste / Unterlagen werden eingereicht *\E	Staat (nur angeben, wenn im Ausland)
Steuerpflicht	E8000803	8	H	-	-	11.18	\Q1\E|\Q2\E	Wegen der Verlegung des Ortes des Sitzes und/oder der Geschäftsleitung vom Ausland ins Inland oder vom Inland ins Ausland besteht im laufenden Veranlagungszeitraum sowohl beschränkte als auch unbeschränkte Steuerpflicht:
Steuerpflicht/Rechtsform	E8001105	9	H	-	Ja	-	\Q350\E|\Q370\E|\Q310\E|\Q360\E|\Q320\E|\Q910\E|\Q210\E|\Q220\E|\Q230\E|\Q240\E|\Q250\E|\Q260\E|\Q271\E|\Q280\E|\Q293\E|\Q920\E|\Q460\E|\Q450\E|\Q490\E|\Q930\E|\Q510\E|\Q511\E|\Q520\E|\Q623\E|\Q540\E|\Q590\E|\Q940\E|\Q621\E|\Q650\E|\Q624\E|\Q950\E|\Q611\E|\Q391\E|\Q221\E|\Q810\E|\Q811\E|\Q838\E|\Q831\E|\Q833\E|\Q820\E|\Q840\E|\Q850\E|\Q834\E|\Q960\E	Rechtsform
Steuerbefreiung/Bezeichnung	E8001505	10	H	-	-	11.15	\Q3\E|\Q5\E|\Q7\E|\Q9\E|\Q10\E|\Q14\E|\Q16\E|\Q18\E|\Q19\E|\Q21\E|\Q22\E	Die Körperschaft ist nach der folgenden Nummer des § 5 Absatz 1 KStG von der Körperschaftsteuer befreit:
Steuerbefreiung/Umfang	E8001506	11	J	-	-	-	1	Die Körperschaft ist vollumfänglich von der Körperschaftsteuer befreit.
Qualifiz	E8001305	13	H	-	-	86.500	\Q1\E|\Q2\E|\Q3\E|\Q4\E	In dieser Steuererklärung
Qualifiz	E8001304	13	C	999	-	-	.{1,999}	Ergänzende Angaben zur Steuererklärung
Wirtschaftsjahr	E8002606	14	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Erstes Wirtschaftsjahr vom
Wirtschaftsjahr	E8002607	14	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Erstes Wirtschaftsjahr bis
Wirtschaftsjahr	E8002608	14	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Gegebenenfalls zweites Wirtschaftsjahr vom
Wirtschaftsjahr	E8002609	14	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Gegebenenfalls zweites Wirtschaftsjahr bis
Wirtschaftsjahr	E8000703	14a	J	-	-	-	1	Die Körperschaft wurde im Veranlagungszeitraum neu gegründet.
Wirtschaftsjahr	E8001508	15	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Die Körperschaft wurde aufgelöst und befindet sich in Abwicklung (Liquidation). Als Wirtschaftsjahr wurde der Besteuerungszeitraum nach § 11 KStG angegeben. Datum der Auflösung:
Weiteres	E8001008	16	J	-	-	11.69	1	Das Unternehmen hält Anteile, auf die § 8b Absatz 7 KStG anzuwenden ist.
Weiteres	E8001007	17	Y	-	-	11.68	1|2	Es handelt sich um ein Unternehmen, auf das § 8 Absatz 9 KStG anzuwenden ist, oder um eine Organgesellschaft, auf deren Organträger § 8 Absatz 9 KStG anzuwenden ist (wenn ja: zusätzlich Anlage(n) ÖHK übermitteln).
Weiteres	E8001702	17a	H	-	-	11.66	\Q1\E|\Q2\E	Bei Investmentfonds: Art des Investmentfonds:
BgA	E8001718	17b	J	-	-	11.67	1	Nur bei Stiftungen des öffentlichen Rechts: Die Trägerkörperschaft dient ausschließlich und unmittelbar gemeinnützigen oder mildtätigen Zwecken. Eine Bescheinigung nach § 44a Absatz 7 Satz 1 Nummer 2 in Verbindung mit Satz 2 EStG wurde ausgestellt (NV-Art 36).
BgA	E8001202	18	H	-	-	11.61	\Q1\E|\Q2\E|\Q3\E	Organisationsform des Betriebs gewerblicher Art:
AE/Einzel	E8122111	21a	Y	-	-	-	1|2	Die Angaben haben sich bei diesem Anteilseigner gegenüber dem Vorjahr geändert.
AE/Einzel	E8122109	22	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer
AE/Einzel	E8122110	22a	I	-	-	-	[0-9]{11}	Identifikationsnummer
AE/Einzel	E8122112	22a	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
AE/Einzel	E8122113	22b	C	999	-	-	.{1,999}	Ausländisches Identifikationsmerkmal
AE/Einzel	E8122101	22c	C	999	-	-	.{1,999}	Name (bei natürlichen Personen Vor- und Nachname)
AE/Einzel	E8122102	22d	C	999	-	-	.{1,999}	Straße und Hausnummer
AE/Einzel	E8122103	22e	C	999	-	-	.{1,999}	Postleitzahl und Wohnort
AE/Einzel/Besitzdauer	E8122104	23	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Höhe der Beteiligung in EUR
AE/Einzel/Besitzdauer	E8122105	23a	F	-	-	-	^(?=.{1,8}$)(?!0\d)\d{1,3}(,\d{1,4})?$	Höhe der Beteiligung (in Prozent)
AE/Einzel/Besitzdauer	E8122106	23b	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Besitzdauer von
AE/Einzel/Besitzdauer	E8122107	23b	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Besitzdauer bis
AE/Gesamt	E8002005	26	J	-	-	19.217	1	Eine Aufstellung über die erstmalige oder geänderte von der Höhe der Beteiligung abweichende Verteilung der Stimmrechte wird gesondert übermittelt (einschließlich Erläuterung zur abweichenden Verteilung).
AE/Gesamt	E8122601	27	Y	-	-	19.210	1|2	Die oben genannten Angaben zu den Anteilseignern haben sich gegenüber dem Vorjahr geändert.
Steuerberater	E8019917	-	C	60	-	-	.{1,60}	(Feld wird nicht gedruckt) Ihr Zeichen/gegebenenfalls Zuordnungskriterium für Bescheiddatenübermittlung
Steuerberater/Mitwirkung	E8001901	100	J	-	-	-	1	Die Steuererklärung wurde unter Mitwirkung einer selbständig und eigenverantwortlich tätigen und zur Hilfeleistung in Steuersachen nach §§ 3 und 4 StBerG befugten Person oder Vereinigung angefertigt.
Steuerberater/Mitwirkung	E8019914	100a	C	55	-	-	.{1,55}	Telefonische Rückfragen unter Telefonnummer
Steuerberater/Mitwirkung/Anfertigung	E8019910	101	C	55	-	-	.{1,55}	Name
Steuerberater/Mitwirkung/Anfertigung	E8019911	101	C	55	-	-	.{1,55}	Vorname
Steuerberater/Mitwirkung/Anfertigung	E8019912	101	C	55	-	-	.{1,55}	Straße, Hausnummer
Steuerberater/Mitwirkung/Anfertigung	E8019913	101	C	55	-	-	.{1,55}	Postleitzahl, Ort
Steuerberater/Mitwirkung/Anfertigung	E8019915	102	C	55	-	-	.{1,55}	zusätzliche Angaben
Steuerberater/Mitwirkung/Anfertigung	E8019916	102	C	60	-	-	.{1,60}	Mandantennummer
Steuerberater/Mitwirkung/Anfertigung	E8019918	102	C	55	-	-	.{1,55}	Bearbeiterkennzeichen
"""

# The JD, sheet „GK - Felder“.
_GK_2025 = r"""
Allgemein	E8000110	1	C	999	-	-	.{1,999}	Bei mehreren Betrieben: Bezeichnung des Betriebs
Allgemein	E8000201	2	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Wirtschaftsjahr vom
Allgemein	E8000202	2	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Wirtschaftsjahr bis
Bilanz	E8002001	11	N	-	-	13.110	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Jahresüberschuss/-fehlbetrag laut Handels- oder Steuerbilanz (bei Handelsbilanz: nach Berücksichtigung der Überleitungsrechnung nach § 5b Absatz 1 Satz 2 EStG beziehungsweise § 60 Absatz 2 EStDV zur Anpassung an die steuerlich maßgeblichen Wertansätze)
Bilanz	E8002004	12	N	-	-	13.213	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Bei Gewinnermittlung nach § 4 Absatz 3 EStG: Summe der Betriebseinnahmen (Betrag laut Zeile 23 der Anlage EÜR) abzüglich Summe der Betriebsausgaben (Betrag laut Zeile 75 der Anlage EÜR)
Bilanz	E8002006	13	N	-	-	13.262	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hinzurechnungen und Abrechnungen bei Wechsel der Gewinnermittlungsart: Übergangsgewinn/-verlust laut gesonderter Ermittlung
Bilanz/PG/Einzel	E8002212	14	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der Personengesellschaft
Bilanz/PG/Einzel	E8002217	14	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
Bilanz/PG/Einzel	E8002205	15	C	999	-	-	.{1,999}	Name der Personengesellschaft
Bilanz/PG/Einzel	E8002206	16	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Im bilanziellen Ergebnis enthaltener Gewinn/Verlust aus dieser Personengesellschaft
Bilanz/PG/Einzel	E8002209	17	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Nicht bei Organgesellschaften: Steuerpflichtige Einkünfte aus der Beteiligung an der Mitunternehmerschaft laut gesonderter und einheitlicher Feststellung nach Anwendung aller außerbilanziellen Korrekturen (zum Beispiel § 8b KStG) sowie von Verlustverrechnungsbeschränkungen, die auf Ebene der Mitunternehmerschaft anzuwenden sind (zum Beispiel § 15a EStG)
Bilanz/PG/Einzel	E8002213	18	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Nur bei Organgesellschaften: Einkünfte aus der Beteiligung an der Mitunternehmerschaft laut gesonderter und einheitlicher Feststellung vor Anwendung der aufgrund § 15 Satz 1 Nummer 2 und 2a und § 15 Satz 2 KStG nicht vorzunehmenden außerbilanziellen Korrekturen
Bilanz/PG/Einzel	E8002210	19	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Nicht bei Organgesellschaften: Steuerpflichtige Einkünfte aus der Beteiligung an dieser Personengesellschaft aus vermögensverwaltenden Tätigkeiten (Überleitung nach Maßgabe des BMF-Schreibens vom 29.04.1994, BStBl I 1994, 282) nach Anwendung aller außerbilanziellen Korrekturen (zum Beispiel § 8b KStG) sowie von Verlustverrechnungsbeschränkungen, die auf Ebene der Personengesellschaft anzuwenden sind
Bilanz/PG/Einzel	E8002214	20	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Nur bei Organgesellschaften: Einkünfte aus der Beteiligung an dieser Personengesellschaft aus vermögensverwaltenden Tätigkeiten (Überleitung nach Maßgabe des BMF-Schreibens vom 29.04.1994, BStBl I 1994, 282) vor Anwendung der aufgrund § 15 Satz 1 Nummer 2 und 2a und § 15 Satz 2 KStG nicht vorzunehmenden außerbilanziellen Korrekturen
Bilanz/PG/Gesamt	E8002204	21	N	-	-	13.279	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab / Dazu: Im Betrag laut Zeile 11 enthaltener Gewinn/Verlust aus der Beteiligung an Personengesellschaften
Bilanz/PG/Gesamt	E8002207	22	N	-	-	13.179	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nicht bei Organgesellschaften: Dazu / Davon ab: Steuerpflichtige Einkünfte aus der Beteiligung an Mitunternehmerschaften laut gesonderter und einheitlicher Feststellung nach Anwendung aller außerbilanziellen Korrekturen (zum Beispiel § 8b KStG) sowie von Verlustverrechnungsbeschränkungen, die auf Ebene der Mitunternehmerschaft anzuwenden sind (zum Beispiel § 15a EStG)
Bilanz/PG/Gesamt	E8002215	23	N	-	-	17.262	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nur bei Organgesellschaften: Dazu / Davon ab: Einkünfte aus der Beteiligung an Mitunternehmerschaften laut gesonderter und einheitlicher Feststellung vor Anwendung der aufgrund § 15 Satz 1 Nummer 2 und 2a und § 15 Satz 2 KStG nicht vorzunehmenden außerbilanziellen Korrekturen
Bilanz/PG/Gesamt	E8002211	24	N	-	-	13.280	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nicht bei Organgesellschaften: Dazu / Davon ab: Steuerpflichtige Einkünfte aus der Beteiligung an vermögensverwaltenden Personengesellschaften (Überleitung nach Maßgabe des BMF-Schreibens vom 29.04.1994, BStBl I 1994, 282) nach Anwendung aller außerbilanziellen Korrekturen (zum Beispiel § 8b KStG) sowie von Verlustverrechnungsbeschränkungen, die auf Ebene der Personengesellschaft anzuwenden sind
Bilanz/PG/Gesamt	E8002216	25	N	-	-	17.263	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nur bei Organgesellschaften: Dazu / Davon ab: Einkünfte aus der Beteiligungen an vermögensverwaltenden Personengesellschaften (Überleitung nach Maßgabe des BMF-Schreibens vom 29.04.1994, BStBl I 1994, 282) vor Anwendung der aufgrund § 15 Satz 1 Nummer 2 und 2a und § 15 Satz 2 KStG nicht vorzunehmenden außerbilanziellen Korrekturen
Bilanz/Tonnage	E8002303	26	N	-	-	13.281	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab / Dazu: Im Betrag laut Zeile 11 enthaltener (tatsächlicher) Gewinn/Verlust aus dem Betrieb von Handelsschiffen im internationalen Verkehr, der nach § 5a EStG pauschal zu ermitteln ist
Bilanz/Tonnage	E8002002	27	N	-	-	13.181	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Pauschaler Gewinn/Verlust aus dem Betrieb von Handelsschiffen und Hinzurechnungen bei gesonderter Gewinnermittlung nach § 5a EStG
Bilanz/Altmaterial	E8001801	28	U	-	-	13.290	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Einnahmen aus der Verwertung von Altpapier, das unentgeltlich außerhalb einer ständig dafür vorgehaltenen Verkaufsstelle erworben wurde (ohne Umsatzsteuer)
Bilanz/Altmaterial	E8001809	29	U	-	-	13.296	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bei Gewinnermittlung nach § 4 Absatz 3 EStG: Davon ab: Vereinnahmte Umsatzsteuer auf Einnahmen aus der Verwertung von Altpapier, das unentgeltlich außerhalb einer ständig dafür vorgehaltenen Verkaufsstelle erworben wurde
Bilanz/Altmaterial	E8001802	30	U	-	-	13.291	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Einnahmen aus der Verwertung von Altmaterial (außer Altpapier), das unentgeltlich außerhalb einer ständig dafür vorgehaltenen Verkaufsstelle erworben wurde (ohne Umsatzsteuer)
Bilanz/Altmaterial	E8001903	31	U	-	-	13.298	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bei Gewinnermittlung nach § 4 Absatz 3 EStG: Davon ab: Vereinnahmte Umsatzsteuer auf Einnahmen aus der Verwertung von Altmaterial (außer Altpapier), das unentgeltlich außerhalb einer ständig dafür vorgehaltenen Verkaufsstelle erworben wurde
Bilanz/Altmaterial	E8001803	32	U	-	-	13.292	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Mit den Einnahmen laut Zeilen 28 und 30 in Zusammenhang stehende tatsächliche Aufwendungen (bei Gewinnermittlung nach § 4 Absatz 3 EStG: einschließlich Umsatzsteuer)
Bilanz/Altmaterial	E8001804	33	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Anzusetzender branchenüblicher Reingewinn aus der Verwertung von Altmaterial nach § 64 Absatz 5 AO (5 % des Betrages laut Zeile 28 zuzüglich 20 % des Betrages laut Zeile 30)
Bilanz/Altmaterial	E8001805	34	U	-	-	13.293	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Einnahmen aus Tätigkeiten nach § 64 Absatz 6 AO (ohne Umsatzsteuer)
Bilanz/Altmaterial	E8001808	35	U	-	-	13.295	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bei Gewinnermittlung nach § 4 Absatz 3 EStG: Davon ab: Vereinnahmte Umsatzsteuer auf Einnahmen aus Tätigkeiten nach § 64 Absatz 6 AO
Bilanz/Altmaterial	E8001806	36	U	-	-	13.294	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Mit den Einnahmen laut Zeile 34 in Zusammenhang stehende tatsächliche Aufwendungen (bei Gewinnermittlung nach § 4 Absatz 3 EStG: einschließlich Umsatzsteuer)
Bilanz/Altmaterial	E8001807	37	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Pauschalierter Gewinn nach § 64 Absatz 6 AO (15 % des Betrages laut Zeile 34)
ABil	E8003002	37a	U	-	-	13.233	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Aufwendungen nach § 8 Steueroasen-Abwehrgesetz aus Geschäftsvorgängen in oder mit Bezug zu einem nicht kooperativen Steuerhoheitsgebiet
ABil	E8003001	38	N	-	-	13.241	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Betrag nach § 4e Absatz 3 EStG
ABil	E8003101	39	N	-	-	13.242	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Betrag nach § 4f EStG
ABil	E8003201	40	U	-	-	13.248	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nichtabziehbare Aufwendungen bei Besteuerungsinkongruenzen nach § 4k EStG
ABil/Weiteres0	E8002110	47	U	-	-	13.328	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nicht ausgleichsfähige Verluste nach § 15b EStG gegebenenfalls in Verbindung mit § 2 Absatz 4 Satz 1 und 2 UmwStG und § 20 Absatz 6 Satz 4 UmwStG (ohne Beträge aus Beteiligungen an Personengesellschaften)
ABil/Weiteres0	E8002111	48	U	-	-	13.329	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verlustverrechnung nach § 15b EStG, gegebenenfalls unter Berücksichtigung von § 2 Absatz 4 Satz 3 und 4 UmwStG (ohne Beträge aus Beteiligungen an Personengesellschaften)
ABil/Tierzucht	E8002102	49	U	-	-	13.320	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nicht ausgleichsfähige Verluste aus gewerblicher Tierzucht/-haltung nach § 15 Absatz 4 Satz 1 EStG gegebenenfalls in Verbindung mit § 2 Absatz 4 Satz 1 und 2 UmwStG und § 20 Absatz 6 Satz 4 UmwStG
ABil/Tierzucht	E8002103	50	U	-	-	13.321	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verrechnung von Gewinnen aus gewerblicher Tierzucht/-haltung des laufenden Jahres mit dem Verlustvortrag und dem Verlustrücktrag aus dem folgenden Veranlagungszeitraum nach § 15 Absatz 4 Satz 2 EStG, gegebenenfalls unter Berücksichtigung von § 2 Absatz 4 Satz 3 und 4 UmwStG
ABil/Termin	E8002104	51	U	-	-	13.322	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nicht ausgleichsfähige Verluste aus Termingeschäften nach § 15 Absatz 4 Satz 3 EStG gegebenenfalls in Verbindung mit § 2 Absatz 4 Satz 1 und 2 UmwStG und § 20 Absatz 6 Satz 4 UmwStG
ABil/Termin	E8002105	52	U	-	-	13.323	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verrechnung von Gewinnen aus Termingeschäften des laufenden Jahres mit dem Verlustvortrag und dem Verlustrücktrag aus dem folgenden Veranlagungszeitraum nach § 15 Absatz 4 Satz 3 in Verbindung mit Satz 2 EStG, gegebenenfalls unter Berücksichtigung von § 2 Absatz 4 Satz 3 und 4 UmwStG
ABil/AtypG/Einzel	E8002112	53	C	999	-	-	.{1,999}	Name der Körperschaft, an der die atypisch stille Beteiligung besteht
ABil/AtypG/Einzel	E8002113	54	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer
ABil/AtypG/Einzel	E8002120	54	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
ABil/AtypG/Einzel	E8002114	55	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Nicht ausgleichsfähiger laufender Verlust
ABil/AtypG/Einzel	E8002115	56	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Verlustverrechnung
ABil/AtypG/Gesamt	E8002106	57	U	-	-	13.324	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nicht ausgleichsfähige Verluste als atypisch stiller Gesellschafter nach § 15 Absatz 4 Satz 6 bis 8 EStG gegebenenfalls in Verbindung mit § 2 Absatz 4 Satz 1 und 2 UmwStG und § 20 Absatz 6 Satz 4 UmwStG
ABil/AtypG/Gesamt	E8002107	58	U	-	-	13.325	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verrechnung von Gewinnen als atypisch stiller Gesellschafter mit dem Verlustvortrag und dem Verlustrücktrag aus dem folgenden Veranlagungszeitraum nach § 15 Absatz 4 Satz 6 bis 8 EStG, gegebenenfalls unter Berücksichtigung von § 2 Absatz 4 Satz 3 und 4 UmwStG
ABil/TypG/Einzel	E8002116	59	C	999	-	-	.{1,999}	Name des Unternehmens, an dem die typisch stille Gesellschaft besteht
ABil/TypG/Einzel	E8002117	60	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer
ABil/TypG/Einzel	E8002121	60	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
ABil/TypG/Einzel	E8002118	61	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Nicht ausgleichsfähiger laufender Verlust
ABil/TypG/Einzel	E8002119	62	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Verlustverrechnung
ABil/TypG/Gesamt	E8002108	63	U	-	-	13.326	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nicht ausgleichsfähige Verluste als typisch stiller Gesellschafter nach § 20 Absatz 1 Nummer 4 Satz 2 EStG in Verbindung mit § 15 Absatz 4 Satz 6 und 8 und § 15a EStG und gegebenenfalls § 2 Absatz 4 Satz 1 und 2 UmwStG und § 20 Absatz 6 Satz 4 UmwStG
ABil/TypG/Gesamt	E8002109	64	U	-	-	13.327	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verrechnung von Gewinnen als typisch stiller Gesellschafter nach § 20 Absatz 1 Nummer 4 Satz 1 EStG mit dem Verlustvortrag und dem Verlustrücktrag aus dem folgenden Veranlagungszeitraum nach § 20 Absatz 1 Nummer 4 Satz 2 EStG in Verbindung mit § 15 Absatz 4 Satz 6 bis 8 EStG oder mit dem Verlustvortrag nach § 15a EStG und gegebenenfalls unter Berücksichtigung von § 2 Absatz 4 Satz 3 und 4 UmwStG
ABil/REIT	E8004004	65	U	-	-	13.318	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nicht ausgleichsfähige Verluste aus Anteilen an REIT-Körperschaften nach § 19 Absatz 4 REITG gegebenenfalls in Verbindung mit § 2 Absatz 4 Satz 1 und 2 UmwStG und § 20 Absatz 6 Satz 4 UmwStG (vorbehaltlich des § 19a Absatz 1 Satz 2 REITG)
ABil/REIT	E8004005	66	U	-	-	13.319	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verrechnung von Gewinnen aus Anteilen an REIT-Körperschaften des laufenden Jahres nach § 19 Absatz 4 REITG gegebenenfalls unter Berücksichtigung von § 2 Absatz 4 Satz 3 und 4 UmwStG
ABil/SiebenG	E8002602	67	U	-	-	13.239	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Investitionsabzugsbeträge des laufenden Wirtschaftsjahres nach § 7g Absatz 1 EStG
ABil/SiebenG	E8002603	70	U	-	-	13.245	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Im Wirtschaftsjahr der Anschaffung/Herstellung: Investitionsabzugsbeträge nach § 7g Absatz 2 Satz 1 EStG aus $VZ-3$
ABil/SiebenG	E8002604	71	U	-	-	13.246	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Im Wirtschaftsjahr der Anschaffung/Herstellung: Investitionsabzugsbeträge nach § 7g Absatz 2 Satz 1 EStG aus $VZ-2$
ABil/SiebenG	E8002605	72	U	-	-	13.247	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Im Wirtschaftsjahr der Anschaffung/Herstellung: Investitionsabzugsbeträge nach § 7g Absatz 2 Satz 1 EStG aus $VZ-1$
ABil/VGA/Einzel	E8002704	73	C	999	-	-	.{1,999}	Bezeichnung
ABil/VGA/Einzel	E8002710	73a	C	999	-	-	.{1,999}	Name des Anteilseigners, dem die verdeckte Gewinnausschüttung zuzurechnen ist
ABil/VGA/Einzel	E8002711	73b	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer (soweit im Inland steuerlich erfasst)
ABil/VGA/Einzel	E8002712	73c	I	-	-	-	[0-9]{11}	Identifikationsnummer
ABil/VGA/Einzel	E8002713	73d	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
ABil/VGA/Einzel	E8002716	73e	C	999	-	-	.{1,999}	Ausländisches Identifikationsmerkmal
ABil/VGA/Einzel	E8002714	73f	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Zeitpunkt des Zuflusses
ABil/VGA/Einzel	E8002715	73g	Z	-	-	-	\d\d\.\d\d\.\d\d\d\d-\d\d\.\d\d\.\d\d\d\d	Zeitraum des Zuflusses
ABil/VGA/Einzel	E8002705	74	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Betrag
ABil/VGA/Gesamt	E8002701	75	U	-	-	13.116	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nicht bei Organgesellschaften: Dazu: Verdeckte Gewinnausschüttungen nach § 8 Absatz 3 Satz 2 KStG
ABil/Genuss/Einzel	E8002707	75a	C	999	-	-	.{1,999}	Bezeichnung
ABil/Genuss/Einzel	E8002708	75b	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Betrag
ABil/Genuss/Gesamt	E8002709	75c	U	-	-	13.218	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Ausschüttungen jeder Art auf Genussrechte, mit denen das Recht auf Beteiligung am Gewinn und am Liquidationserlös der Kapitalgesellschaft verbunden ist, nach § 8 Absatz 3 Satz 2 zweite Alternative KStG
ABil/Weiteres2	E8002702	76	G	-	-	13.166	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Davon ab: Gewinnerhöhungen im Zusammenhang mit versteuerten verdeckten Gewinnausschüttungen (gemäß BMF-Schreiben vom 28.05.2002, BStBl I 2002, 603)
ABil/Weiteres2	E8002902	77	U	-	-	13.216	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nichtabziehbare genossenschaftliche Rückvergütungen - verdeckte Gewinnausschüttungen nach R 22 Absatz 13 KStR 2022 (Betrag laut Zeile 18 der Anlage GR)
ABil/Weiteres2	E8002801	78	G	-	-	13.226	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Dazu: Nicht erfolgswirksam gebuchte Einlagen nach § 8 Absatz 3 Satz 4 KStG
ABil/Weiteres2	E8002601	79	U	-	-	13.139	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Gewinnzuschlag nach § 6b Absatz 7 EStG gegebenenfalls in Verbindung mit § 6c EStG
ABil/Weiteres2	E8100201	80	U	-	-	14.12	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Aufwendungen für satzungsmäßige Zwecke (§ 10 Nummer 1 KStG)
ABil/Weiteres2	E8100301	81	N	-	-	14.15	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Körperschaftsteuer
ABil/Weiteres2	E8100501	82	N	-	-	14.30	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Solidaritätszuschlag
ABil/Weiteres2	E8100601	83	U	-	-	14.17	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Kapitalertragsteuer auf vereinnahmte Kapitalerträge
ABil/Weiteres2	E8100702	84	N	-	-	14.43	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Gewerbesteuer ab Erhebungszeitraum 2008
ABil/Weiteres2	E8100803	84b	N	-	-	14.46	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Mindeststeuer (MinStG)
ABil/Weiteres2	E8100804	84c	N	-	-	14.47	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Nach § 3 Absatz 6 Satz 3 MinStG nicht abziehbare Aufwendungen beziehungsweise nicht steuerpflichtige Erträge für Ausgleichsansprüche
ABil/Weiteres2	E8100801	85	N	-	-	14.21	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Sonstige Personensteuern (zum Beispiel Vermögensteuer, Erbschaft- und Schenkungsteuer)
ABil/Weiteres2	E8100901	86	N	-	-	14.25	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Nach § 10 Nummer 2 KStG nichtabziehbarer Teil der Umsatzsteuer und Vorsteuerbeträge
ABil/Weiteres2	E8101001	87	N	-	-	14.26	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Ausländische Personensteuern und ausländische Steuern vom Einkommen nach § 10 Nummer 2 KStG
ABil/Weiteres2	E8101101	88	N	-	-	14.31	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Nebenleistungen zu den Steuern laut Zeilen 81 bis 87 (zum Beispiel Säumnis- und Verspätungszuschläge, Zwangsgelder, Zinsen nach §§ 234 bis 237 AO, Nachzahlungszinsen nach § 233a AO, Zuschläge nach § 162 Absatz 4 AO, Gebühren nach §§ 89 und 89a AO)
ABil/Weiteres2	E8101201	89	N	-	-	14.32	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Die Hälfte der Vergütungen aller Art, die an Mitglieder des Aufsichtsrats, Verwaltungsrats oder andere mit der Überwachung der Geschäftsführung beauftragte Personen gewährt werden (einschließlich des von der Körperschaft getragenen Steuerabzugs nach § 50a Absatz 1 Nummer 4 EStG und des Solidaritätszuschlags; § 10 Nummer 4 KStG) – Zeilen 20 bis 20h und 30 bis 37 der Anlage WA sind zusätzlich auszufüllen -
ABil/Weiteres2	E8101301	90	N	-	-	14.33	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Sonstige nichtabziehbare Aufwendungen; insbesondere nach § 4 Absatz 5 Satz 1 Nummer 1 bis 4, 7, 8, 8a, 10 und Absatz 6 bis 8 EStG, §§ 4c und 4d EStG, § 160 Absatz 1 AO, § 10 Nummer 3 KStG
ABil/Weiteres2	E8101302	91	U	-	-	14.45	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nichtabziehbare Beitragsrückerstattungen nach § 21 KStG
ABil/Weiteres2	E8101401	92	U	-	-	14.35	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Sämtliche Spenden und nicht als Betriebsausgaben abziehbare Beiträge
ABil/Weiteres2	E8003301	93	N	-	-	13.140	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Einlagen der Gesellschafter (§ 8 Absatz 3 Satz 3 KStG), die erfolgswirksam gebucht und bis zum Ende des Wirtschaftsjahres geleistet wurden (einschließlich eines Erhöhungsbetrages nach § 23 Absatz 2 und 3 UmwStG)
ABil/Weiteres2	E8003401	94	N	-	-	13.148	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Einlagen der Gesellschafter (§ 8 Absatz 3 Satz 3 KStG), die erfolgswirksam gebucht, aber nicht bis zum Ende des Wirtschaftsjahres geleistet wurden
ABil/Weiteres2	E8003402	95	G	-	-	13.220	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Davon ab: Gewinnerhöhung aus der Begründung des Besteuerungsrechts der Bundesrepublik Deutschland hinsichtlich des Gewinns aus der Veräußerung eines Wirtschaftsgutes (§ 4 Absatz 1 Satz 8 zweiter Halbsatz EStG)
ABil/Weiteres2	E8003601	96	N	-	-	13.131	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Investitionszulage (zurückgeforderte Investitionszulage mit negativem Vorzeichen eintragen)
ABil/Weiteres2	E8003702	97	G	-	-	13.221	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Dazu: Einkommenserhöhung aus der Steuerentstrickung nach § 12 Absatz 1 Satz 1 und 2 KStG, § 16 Absatz 3a EStG (soweit im Betrag laut Zeilen 11 und 12 nicht erfasst)
ABil/Weiteres2	E8009702	97a	N	-	-	13.200	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab / Dazu: Nach § 3 Nummer 72 EStG steuerfreie Einnahmen und Entnahmen aus dem Betrieb von Photovoltaikanlagen, vermindert um damit im Zusammenhang stehende Betriebsausgaben nach § 3c Absatz 1 EStG
ABil/Weiteres2/Sonstige/Einzel	E8003604	98	C	999	-	-	.{1,999}	Steuerbefreiung nach §
ABil/Weiteres2/Sonstige/Einzel	E8003605	99	C	999	-	-	.{1,999}	Art der sonstigen steuerfreien Einnahmen
ABil/Weiteres2/Sonstige/Einzel	E8003606	100	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Betrag der Einnahmen
ABil/Weiteres2/Sonstige/Einzel	E8003607	101	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Betrag der Ausgaben
ABil/Weiteres2/Sonstige/Gesamt	E8003701	102	N	-	-	13.130	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Sonstige steuerfreie Einnahmen, vermindert um damit im Zusammenhang stehende nicht abzugsfähige Betriebsausgaben nach § 3c Absatz 1 EStG
UmwStG/Verschmelzung_UN/Einzel	E8007020	103	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer des übertragenden Rechtsträgers
UmwStG/Verschmelzung_UN/Einzel	E8007026	103	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer des übertragenden Rechtsträgers
UmwStG/Verschmelzung_UN/Einzel	E8007010	104	C	999	-	-	.{1,999}	Name des übertragenden Rechtsträgers
UmwStG/Verschmelzung_UN/Einzel	E8007021	105	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Wert mit dem das übernommene Betriebsvermögen in der Steuerbilanz angesetzt wurde
UmwStG/Verschmelzung_UN/Einzel	E8007022	106	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Buchwert der Anteile am übertragenden Rechtsträger
UmwStG/Verschmelzung_UN/Einzel	E8007024	107	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Kosten für den Vermögensübergang
UmwStG/Verschmelzung_UN/Einzel	E8007011	108	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Übernahmegewinn/-verlust nach § 12 Absatz 2 UmwStG
UmwStG/Verschmelzung_UN/Einzel	E8007012	109	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Übernahmegewinn nach § 12 Absatz 2 Satz 2 UmwStG
UmwStG/Verschmelzung_UN/Einzel	E8007013	110	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Übernahmegewinn nach § 12 Absatz 2 Satz 1 UmwStG (Positiver Betrag laut Zeile 108 abzüglich Betrag laut Zeile 109)
UmwStG/Verschmelzung_UN/Einzel	E8007014	111	M	-	-	-	^(?=.{1,13}$)(?=.*[1-9].*)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Übernahmeverlust nach § 12 Absatz 2 Satz 1 UmwStG (Negativer Betrag laut Zeile 108)
UmwStG/Verschmelzung_UN/Einzel	E8007023	112	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Betrag des in der Steuerbilanz erfolgsneutral angesetzten übernommenen Vermögens
UmwStG/Verschmelzung_UN/Vor	E8007016	116	U	-	-	13.204	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Übernahmegewinn nach § 12 Absatz 2 Satz 2 UmwStG in Verbindung mit § 8b Absatz 2 KStG (Vorspalte: Summe der Beträge aller Zeilen 109; nicht bei Organgesellschaften: Übertrag in Hauptspalte in Höhe von 95 % mit umgekehrtem Vorzeichen)
UmwStG/Verschmelzung_UN/Vor	E8007018	117	N	-	-	13.205	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Übernahmegewinne/-verluste nach § 12 Absatz 2 Satz 1 UmwStG (Summe der Beträge aller Zeilen 110 und 111; nicht bei Organgesellschaften: Übertrag in die Hauptspalte mit umgekehrtem Vorzeichen)
UmwStG/Verschmelzung_UN/Haupt	E8007025	115	N	-	-	13.203	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Betrag des in der Steuerbilanz erfolgsneutral angesetzten übernommenen Vermögens (Summe der Beträge aller Zeilen 112)
UmwStG/Verschmelzung_UN/Haupt	E8007017	116	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Übernahmegewinn nach § 12 Absatz 2 Satz 2 UmwStG in Verbindung mit § 8b Absatz 2 KStG (Vorspalte: Summe der Beträge aller Zeilen 109; nicht bei Organgesellschaften: Übertrag in Hauptspalte in Höhe von 95 % mit umgekehrtem Vorzeichen)
UmwStG/Verschmelzung_UN/Haupt	E8007019	117	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Übernahmegewinne/-verluste nach § 12 Absatz 2 Satz 1 UmwStG (Summe der Beträge aller Zeilen 110 und 111; nicht bei Organgesellschaften: Übertrag in die Hauptspalte mit umgekehrtem Vorzeichen)
UmwStG/EGI	E8004002	118	G	-	-	13.225	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Dazu: Im laufenden Wirtschaftsjahr zu versteuernder "Einbringungsgewinn I" nach § 22 Absatz 1 UmwStG
UmwStG/Anderes_Jahr/Einzel	E8007303	119	C	999	-	-	.{1,999}	Bezeichnung des Anteils
UmwStG/Anderes_Jahr/Einzel	E8007304	120	G	-	-	-	^(?=.{4,4}$)(?=.*[1-9].*)(?!0\d)\d{1,15}$	Jahr der Entstehung der Aufwendungen/Erträge
UmwStG/Anderes_Jahr/Einzel	E8007305	121	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Betrag
UmwStG/Anderes_Jahr/Gesamt	E8007302	122	N	-	-	13.237	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab / Dazu: In einem anderen Wirtschaftsjahr entstandene Aufwendungen beziehungsweise Erträge, die im Zusammenhang mit dem im laufenden Wirtschaftsjahr nach § 12 Absatz 2 Satz 1 UmwStG zu berücksichtigenden Übernahmegewinn/-verlust und/oder zu versteuernden "Einbringungsgewinn I" nach § 22 Absatz 1 UmwStG stehen
UmwStG/Lfd_Jahr/Einzel	E8007405	123	C	999	-	-	.{1,999}	Bezeichnung des Anteils
UmwStG/Lfd_Jahr/Einzel	E8007406	124	O	-	-	-	^(?=.{1,4}$)[0-9]+	Jahr des steuerlichen Übertragungsstichtags des Umwandlungsvorgangs
UmwStG/Lfd_Jahr/Einzel	E8007407	125	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Betrag
UmwStG/Lfd_Jahr/Gesamt	E8007408	126	N	-	-	13.238	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Im laufenden Wirtschaftsjahr entstandene Aufwendungen beziehungsweise Erträge, die im Zusammenhang mit dem in einem anderen Wirtschaftsjahr nach § 12 Absatz 2 Satz 1 UmwStG zu berücksichtigenden Übernahmegewinn/-verlust und/oder zu versteuernden "Einbringungsgewinn I" nach § 22 Absatz 1 UmwStG stehen
Ausland/DBA/Einzel	E8180501	127	C	50	-	-	.{1,50}	Name des Staates
Ausland/DBA/Einzel	E8180502	128	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Nettobetrag der ausländischen Einkünfte
Ausland/DBA/Einzel	E8180503	129	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Auf die ausländischen Einkünfte entfallende ausländische Steuer
Ausland/DBA/Einzel	E8180504	130	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Bruttobetrag der ausländischen Einkünfte
Ausland/DBA/Gesamt	E8181001	131	N	-	-	16.111	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Ausländische Einkünfte, die aufgrund von DBA steuerfrei sind (ohne Bezüge nach § 20 Absatz 1 Nummer 1, 2, 9 und 10 Buchstabe a EStG aus der Beteiligung an einer ausländischen Körperschaft)
Ausland/DBA/Gesamt	E8181101	132	U	-	-	16.112	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Mit den ausländischen Einkünften laut Zeile 131 im Zusammenhang stehende nichtabziehbare inländische Betriebsausgaben
Ausland/Berichtigung/Einzel	E8183012	140	C	999	-	-	.{1,999}	Beschreibung und Art der Geschäftsbeziehung
Ausland/Berichtigung/Einzel	E8183013	141	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Betrag
Ausland/Berichtigung/Gesamt	E8183001	142	N	-	-	16.175	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Berichtigungsbetrag nach § 1 AStG laut gesonderter Ermittlung
Beteiligung/Verkauf/Anderes_Jahr/Einzel	E8004438	143	C	999	-	-	.{1,999}	Bezeichnung des Anteils
Beteiligung/Verkauf/Anderes_Jahr/Einzel	E8004439	144	G	-	-	-	^(?=.{4,4}$)(?=.*[1-9].*)(?!0\d)\d{1,15}$	Jahr der Entstehung der Aufwendungen/Erträge
Beteiligung/Verkauf/Anderes_Jahr/Einzel	E8004440	145	S	-	-	-	^(?=-?.{4,15}$)(?=.*[1-9].*)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Betrag
Beteiligung/Verkauf/Anderes_Jahr/Gesamt	E8004437	146	N	-	-	13.283	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab / Dazu: In einem anderen Wirtschaftsjahr entstandene Aufwendungen beziehungsweise Erträge, die im Zusammenhang mit der nach § 8b Absatz 2 und 3 KStG steuerfreien Veräußerung von Anteilen an anderen Körperschaften im laufenden Wirtschaftsjahr stehen
Beteiligung/Verkauf/Lfd_Jahr/Einzel	E8004442	147	C	999	-	-	.{1,999}	Bezeichnung des Anteils
Beteiligung/Verkauf/Lfd_Jahr/Einzel	E8004443	148	G	-	-	-	^(?=.{4,4}$)(?=.*[1-9].*)(?!0\d)\d{1,15}$	Jahr, in dem das Wirtschaftsjahr der Veräußerung endet
Beteiligung/Verkauf/Lfd_Jahr/Einzel	E8004444	149	S	-	-	-	^(?=-?.{4,15}$)(?=.*[1-9].*)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Betrag
Beteiligung/Verkauf/Lfd_Jahr/Gesamt	E8004441	150	N	-	-	13.284	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Im laufenden Wirtschaftsjahr entstandene Aufwendungen beziehungsweise Erträge, die im Zusammenhang mit der nach § 8b Absatz 2 und 3 KStG steuerfreien Veräußerung von Anteilen an anderen Körperschaften in einem anderen Wirtschaftsjahr stehen
Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Einzel	E8560405	151	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der ausschüttenden Körperschaft
Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Einzel	E8560408	151	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Einzel	E8560403	152	C	999	-	-	.{1,999}	Name der ausschüttenden Körperschaft
Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Einzel	E8560406	153	%	-	-	-	^(?=.{4,6}$)(?!0\d)\d{1,3}(,\d{2,2})$	Höhe der Beteiligung zum Beginn des Kalenderjahres
Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Einzel	E8560407	154	H	-	-	-	\Q1\E|\Q2\E|\Q3\E|\Q4\E|\Q5\E	Art der Beteiligung (1 = Unmittelbare Beteiligung, 2 = Begünstigter unterjähriger Erwerb nach § 8b Absatz 4 Satz 6 KStG, 3 = Begünstigte kreditwirtschaftliche Verbundgruppe nach § 8b Absatz 4 Satz 8 KStG, 4 = Nicht nach § 8b KStG aber nach DBA steuerbefreit (Schachtelbeteiligung), 5 = Unmittelbare Beteiligung, die durch Zusammenfassung mit mittelbaren Beteiligungen über Personengesellschaften die Voraussetzungen des § 8b Absatz 4 KStG erfüllt)
Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Einzel	E8560404	155	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Bezüge nach § 20 Absatz 1 Nummer 1, 2, 9 und 10 Buchstabe a EStG, die nach § 8b Absatz 1 und 4 KStG oder aufgrund eines DBA steuerfrei sind
Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Gesamt	E8560401	156	U	-	-	13.310	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bezüge nach § 20 Absatz 1 Nummer 1, 2, 9 und 10 Buchstabe a EStG, die nach § 8b Absatz 1 und 4 KStG oder aufgrund eines DBA steuerfrei sind
Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Gesamt	E8560801	160	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nichtabziehbare Ausgaben nach § 8b Absatz 5 Satz 1 KStG (5 % des Betrags laut Zeile 156)
Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel	E8560802	161	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der Körperschaft
Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel	E8560803	161	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel	E8561202	162	C	999	-	-	.{1,999}	Name der Beteiligung
Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel	E8561213	162a	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Zeitpunkt der Veräußerung
Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel	E8561204	163	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Veräußerungspreis oder an dessen Stelle tretender Wert
Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel	E8561205	164	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Veräußerungskosten
Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel	E8561206	165	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Buchwert des Anteils
Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel	E8561211	166	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Gewinn nach § 8b Absatz 2 Satz 1 und Satz 6 KStG
Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel	E8561403	166a	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Verlust nach § 8b Absatz 3 Satz 3 KStG
Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Gesamt	E8561212	166b	U	-	-	13.340	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Gewinne aus der Veräußerung von Anteilen an Körperschaften, die nach § 8b Absatz 2 Satz 1 und Satz 6 KStG steuerfrei sind (gegebenenfalls in Verbindung mit § 15 Absatz 1a EStG)
Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Gesamt	E8561410	166c	U	-	-	13.343	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verluste aus der Veräußerung von Beteiligungen an Körperschaften, die nach § 8b Absatz 3 Satz 3 KStG nicht abziehbar sind
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561238	167a	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der Körperschaft
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561241	167a	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561239	167b	C	999	-	-	.{1,999}	Name der Körperschaft
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561210	167c	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Gewinne aus dem Ansatz des in § 6 Absatz 1 Nummer 2 Satz 3 EStG bezeichneten Wertes, die nach § 8b Absatz 2 Satz 3 KStG steuerfrei sind (Wertaufholung)
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561230	168	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Buchwert der Beteiligung vor Berücksichtigung der Rückzahlung von Nennkapital, Einlagenrückgewähr und Mehr- und Minderabführungen
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561231	169	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Davon ab: Einlagenrückgewähr laut Bescheinigung
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561232	170	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Davon ab: Rückzahlung von Nennkapital
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561233	171	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Davon ab: Mehrabführungen, die ihre Ursache in organschaftlicher Zeit haben
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561234	172	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Davon ab: Mehrabführungen, die ihre Ursache in vororganschaftlicher Zeit haben und für die die Verwendung des steuerlichen Einlagekontos bescheinigt wurde
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561235	173	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Dazu: Minderabführungen
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561240	173a	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Verbleibender Buchwert
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel	E8561236	174	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Gewinne aus der Auflösung oder der Herabsetzung des Nennkapitals oder aus einer Einlagenrückgewähr, die nach § 8b Absatz 2 Satz 3 KStG steuerfrei sind
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Gesamt	E8561220	176	U	-	-	13.341	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Gewinne aus dem Ansatz des in § 6 Absatz 1 Nummer 2 Satz 3 EStG bezeichneten Wertes, die nach § 8b Absatz 2 Satz 3 KStG steuerfrei sind (Wertaufholung)
Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Gesamt	E8561237	177	U	-	-	13.342	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Gewinne aus der Auflösung oder der Herabsetzung des Nennkapitals oder aus einer Einlagenrückgewähr, die nach § 8b Absatz 2 Satz 3 KStG steuerfrei sind
Beteiligung/Tabelle/P8b_Vergleichbar/NichtAbziehbare	E8561301	181	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nichtabziehbare Ausgaben nach § 8b Absatz 3 Satz 1 KStG (5 % der Summe der Beträge laut Zeile 166b, Zeile 176 und Zeile 177)
Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Einzel	E8561404	184	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der Körperschaft
Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Einzel	E8561413	184	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Einzel	E8561402	185	C	999	-	-	.{1,999}	Name der Beteiligung
Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Einzel	E8561408	186	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Sonstige Gewinnminderungen (zum Beispiel Teilwertabschreibungen) aus der Beteiligung an einer Körperschaft, die nach § 8b Absatz 3 Satz 3 KStG nicht abziehbar sind
Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Einzel	E8561409	187	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Gewinnminderungen im Zusammenhang mit Darlehensforderungen (zum Beispiel Teilwertabschreibungen), die nach § 8b Absatz 3 Satz 4 KStG nicht abziehbar sind
Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Gesamt	E8561411	188	U	-	-	13.344	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Sonstige Gewinnminderungen (zum Beispiel Teilwertabschreibungen) aus Beteiligungen an Körperschaften, die nach § 8b Absatz 3 Satz 3 KStG nicht abziehbar sind
Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Gesamt	E8561412	189	U	-	-	13.345	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Gewinnminderungen im Zusammenhang mit Darlehensforderungen (zum Beispiel Teilwertabschreibungen), die nach § 8b Absatz 3 Satz 4 folgende KStG nicht abziehbar sind
Beteiligung/Tabelle/P8b_Vergleichbar/Darlehen	E8561501	190	U	-	-	13.288	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Gewinne nach § 8b Absatz 3 Satz 9 KStG
Beteiligung/Tabelle/P8b_Vergleichbar/LV_KV	E8561601	191	N	-	-	13.168	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Einkommensminderungen beziehungsweise -erhöhungen nach § 8b Absatz 8 Satz 4 und 5 KStG
Beteiligung/Tabelle/P8b_Vergleichbar/Sonstige	E8561701	192	G	-	-	13.227	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Nach § 8b Absatz 10 Satz 1 KStG nichtabziehbare Aufwendungen, soweit sie sich auf die überlassenen Anteile beziehen
Beteiligung/Tabelle/P8b_Vergleichbar/Sonstige	E8561801	193	G	-	-	13.228	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Fiktive Einnahmen und/oder Bezüge nach § 8b Absatz 10 Satz 2 KStG
Beteiligung/Tabelle/P8b_Vergleichbar/Sonstige	E8561901	194	G	-	-	13.229	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Beträge im Sinne der Zeile 193, soweit es sich dabei um Bezüge nach § 8b Absatz 1 KStG, auf die § 8b Absatz 4 KStG nicht anzuwenden ist, und/oder um Gewinne nach § 8b Absatz 2 KStG handelt
Beteiligung/Tabelle/P8b_Vergleichbar/Sonstige	E8562001	195	G	-	-	13.230	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	5 % des Betrages laut Zeile 156 und/oder der Beträge laut Zeilen 166b, 176 und 177, soweit es sich hierbei um Bezüge aus entliehenen Anteilen nach § 8b Absatz 10 KStG handelt
Beteiligung/Korrektur	E8562101	201	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nicht bei Organgesellschaften: Summe der Beträge laut Zeilen 160, 166c, 181, 188, 189, 191, 192 und 193 abzüglich der Summe der Beträge laut Zeilen 156, 166b, 176, 177, 190, 194 und 195
Beteiligung/Korrektur	E8562201	202	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nur bei Organgesellschaften: Summe der Beträge laut Zeilen 191, 192 und 193
Org_AP/Einzel	E8562501	203	C	50	-	-	.{1,50}	Name der Beteiligung an der (gegebenenfalls ehemaligen) Organgesellschaft
Org_AP/Einzel	E8562502	204	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der (gegebenenfalls ehemaligen) Organgesellschaft
Org_AP/Einzel	E8562521	204	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer der (gegebenenfalls ehemaligen) Organgesellschaft
Org_AP/Einzel	E8562503	206	Y	-	-	-	1|2	Die Voraussetzungen für die Anwendung des § 8b Absatz 7 oder 8 KStG liegen vor.
Org_AP/Einzel	E8562520	212a	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Rücklage nach § 34 Absatz 6e Satz 15 KStG zum Beginn des Wirtschaftsjahres
Org_AP/Einzel	E8562510	213	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Auflösung der Rücklage nach § 34 Absatz 6e Satz 17 KStG
Org_AP/Einzel	E8562519	213a	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Auflösung der Rücklage bei vollständiger oder anteiliger Veräußerung und gleichgestellten Vorgängen nach § 34 Absatz 6e Satz 18 und Satz 19 KStG
Org_AP/Einzel	E8562511	214	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Rücklage nach § 34 Absatz 6e Satz 15 KStG zum Ende des Wirtschaftsjahres
Org_AP/Gesamt/Vorspalte	E8562513	217	U	-	-	13.304	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Auflösung der Rücklage nach § 34 Absatz 6e Satz 17 bis 19 KStG im laufenden Wirtschaftsjahr (Summe der Beträge aller Zeilen 213 und 213a bei denen § 8b Absatz 7 oder 8 KStG nicht anwendbar sind; Übertrag in Hauptspalte (nicht bei Organgesellschaften))
Org_AP/Gesamt/Hauptspalte	E8562515	217	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Auflösung der Rücklage nach § 34 Absatz 6e Satz 17 bis 19 KStG im laufenden Wirtschaftsjahr (Summe der Beträge aller Zeilen 213 und 213a bei denen § 8b Absatz 7 oder 8 KStG nicht anwendbar sind; Übertrag in Hauptspalte (nicht bei Organgesellschaften))
Org_AP/Gesamt/Hauptspalte	E8562516	218	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nichtabziehbare Ausgaben nach § 8b Absatz 3 Satz 1 in Verbindung mit § 34 Absatz 6e Satz 14 und 20 KStG (5 % des Betrages laut Zeile 217 Hauptspalte)
Invest/Aktie/Vorspalte	E8011102	219	N	-	-	13.350	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Investmenterträge nach § 20 Absatz 1 Nummer 3 EStG aus Aktienfonds nach § 2 Absatz 6 InvStG und Erträge aus dem Ansatz des Teilwerts (vor Teilfreistellung; ohne Beträge laut Zeile 222)
Invest/Aktie/Vorspalte	E8011201	220	U	-	-	13.360	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mit den Erträgen laut Zeile 219 in Zusammenhang stehende Betriebsvermögensminderungen, Betriebsausgaben, Teilwertabschreibungen oder Veräußerungskosten
Invest/Aktie/Vorspalte	E8011301	221	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nach § 20 Absatz 1 InvStG freizustellender Betrag für Aktienfonds (Vorspalte: Betrag laut Zeile 219 abzüglich Betrag laut Zeile 220; Hauptspalte (nicht bei Organgesellschaften): 80 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Aktie/Hauptspalte	E8011302	221	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nach § 20 Absatz 1 InvStG freizustellender Betrag für Aktienfonds (Vorspalte: Betrag laut Zeile 219 abzüglich Betrag laut Zeile 220; Hauptspalte (nicht bei Organgesellschaften): 80 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Aktie/Vorspalte_2	E8011401	222	N	-	-	13.351	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Investmenterträge nach § 20 Absatz 1 Nummer 3 EStG aus Aktienfonds nach § 2 Absatz 6 InvStG, die den Kapitalanlagen eines Lebens- oder Krankenversicherungsunternehmens beziehungsweise einem Pensionsfonds zuzurechnen sind oder wenn die Voraussetzungen des § 20 Absatz 1 Satz 4 Nummer 2 InvStG erfüllt sind und Erträge aus dem Ansatz des Teilwerts (vor Teilfreistellung)
Invest/Aktie/Vorspalte_2	E8011501	223	U	-	-	13.361	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mit den Erträgen laut Zeile 222 in Zusammenhang stehende Betriebsvermögensminderungen, Betriebsausgaben, Teilwertabschreibungen oder Veräußerungskosten
Invest/Aktie/Vorspalte_2	E8011601	224	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	In den Fällen des § 20 Absatz 1 Satz 4 und 5 InvStG nach § 20 Absatz 1 InvStG freizustellender Betrag für Aktienfonds (Vorspalte: Betrag laut Zeile 222 abzüglich Betrag laut Zeile 223; Hauptspalte: 30 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Aktie/Hauptspalte_2	E8011602	224	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	In den Fällen des § 20 Absatz 1 Satz 4 und 5 InvStG nach § 20 Absatz 1 InvStG freizustellender Betrag für Aktienfonds (Vorspalte: Betrag laut Zeile 222 abzüglich Betrag laut Zeile 223; Hauptspalte: 30 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Misch/Vorspalte	E8011701	225	N	-	-	13.352	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Investmenterträge nach § 20 Absatz 1 Nummer 3 EStG aus Mischfonds nach § 2 Absatz 7 InvStG und Erträge aus dem Ansatz des Teilwerts (vor Teilfreistellung; ohne Beträge laut Zeile 228)
Invest/Misch/Vorspalte	E8011801	226	U	-	-	13.362	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mit den Erträgen laut Zeile 225 in Zusammenhang stehende Betriebsvermögensminderungen, Betriebsausgaben, Teilwertabschreibungen oder Veräußerungskosten
Invest/Misch/Vorspalte	E8011901	227	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nach § 20 Absatz 2 in Verbindung mit Absatz 1 InvStG freizustellender Betrag für Mischfonds (Vorspalte: Betrag laut Zeile 225 abzüglich Betrag laut Zeile 226; Hauptspalte (nicht bei Organgesellschaften): 40 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Misch/Hauptspalte	E8011902	227	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nach § 20 Absatz 2 in Verbindung mit Absatz 1 InvStG freizustellender Betrag für Mischfonds (Vorspalte: Betrag laut Zeile 225 abzüglich Betrag laut Zeile 226; Hauptspalte (nicht bei Organgesellschaften): 40 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Misch/Vorspalte_2	E8012001	228	N	-	-	13.353	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Investmenterträge nach § 20 Absatz 1 Nummer 3 EStG aus Mischfonds nach § 2 Absatz 7 InvStG, die den Kapitalanlagen eines Lebens- oder Krankenversicherungsunternehmens beziehungsweise einem Pensionsfonds zuzurechnen sind oder wenn die Voraussetzungen des § 20 Absatz 1 Satz 4 Nummer 2 InvStG erfüllt sind und Erträge aus dem Ansatz des Teilwerts (vor Teilfreistellung)
Invest/Misch/Vorspalte_2	E8012101	229	U	-	-	13.363	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mit den Erträgen laut Zeile 228 in Zusammenhang stehende Betriebsvermögensminderungen, Betriebsausgaben, Teilwertabschreibungen oder Veräußerungskosten
Invest/Misch/Vorspalte_2	E8012201	230	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	In den Fällen des § 20 Absatz 1 Satz 4 und 5 InvStG nach § 20 Absatz 2 in Verbindung mit Absatz 1 InvStG freizustellender Betrag für Mischfonds (Vorspalte: Betrag laut Zeile 228 abzüglich Betrag laut Zeile 229; Hauptspalte: 15 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Misch/Hauptspalte_2	E8012202	230	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	In den Fällen des § 20 Absatz 1 Satz 4 und 5 InvStG nach § 20 Absatz 2 in Verbindung mit Absatz 1 InvStG freizustellender Betrag für Mischfonds (Vorspalte: Betrag laut Zeile 228 abzüglich Betrag laut Zeile 229; Hauptspalte: 15 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Immo_P2Abs9/Vorspalte	E8012301	231	N	-	-	13.354	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Investmenterträge nach § 20 Absatz 1 Nummer 3 EStG aus Immobilienfonds nach § 2 Absatz 9 Satz 1 InvStG und Erträge aus dem Ansatz des Teilwerts (vor Teilfreistellung)
Invest/Immo_P2Abs9/Vorspalte	E8012401	232	U	-	-	13.364	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mit den Erträgen laut Zeile 231 in Zusammenhang stehende Betriebsvermögensminderungen, Betriebsausgaben, Teilwertabschreibungen oder Veräußerungskosten
Invest/Immo_P2Abs9/Vorspalte	E8012501	233	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nach § 20 Absatz 3 Satz 1 InvStG freizustellender Betrag für Immobilienfonds (Vorspalte: Betrag laut Zeile 231 abzüglich Betrag laut Zeile 232; Hauptspalte (nicht bei Organgesellschaften): 60 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Immo_P2Abs9/Hauptspalte	E8012502	233	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nach § 20 Absatz 3 Satz 1 InvStG freizustellender Betrag für Immobilienfonds (Vorspalte: Betrag laut Zeile 231 abzüglich Betrag laut Zeile 232; Hauptspalte (nicht bei Organgesellschaften): 60 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Immo_Ausland/Vorspalte	E8012601	234	N	-	-	13.355	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Investmenterträge nach § 20 Absatz 1 Nummer 3 EStG aus Auslands-Immobilienfonds nach § 2 Absatz 9 Satz 2 InvStG und Erträge aus dem Ansatz des Teilwerts (vor Teilfreistellung)
Invest/Immo_Ausland/Vorspalte	E8012701	235	U	-	-	13.365	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mit den Erträgen laut Zeile 234 in Zusammenhang stehende Betriebsvermögensminderungen, Betriebsausgaben, Teilwertabschreibungen oder Veräußerungskosten
Invest/Immo_Ausland/Vorspalte	E8012801	236	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nach § 20 Absatz 3 Satz 2 InvStG freizustellender Betrag für Auslands-Immobilienfonds nach § 2 Absatz 9 Satz 2 InvStG (Vorspalte: Betrag laut Zeile 234 abzüglich Betrag laut Zeile 235; Hauptspalte (nicht bei Organgesellschaften): 80 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Immo_Ausland/Hauptspalte	E8012802	236	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nach § 20 Absatz 3 Satz 2 InvStG freizustellender Betrag für Auslands-Immobilienfonds nach § 2 Absatz 9 Satz 2 InvStG (Vorspalte: Betrag laut Zeile 234 abzüglich Betrag laut Zeile 235; Hauptspalte (nicht bei Organgesellschaften): 80 % des Wertes der Vorspalte mit umgekehrtem Vorzeichen)
Invest/Unterschiedsbetrag	E8012901	237	N	-	-	13.392	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Unterschiedsbeträge nach § 5 Absatz 1 Satz 1 Nummer 5 Satz 5 beziehungsweise § 13 Absatz 4a Satz 2 InvStG 2004
Spezial_Invest/Vorspalte	E8016106	237a	U	-	-	13.396	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Im Betrag laut Zeile 11 enthaltene laufende Erträge als Anleger an einem Spezial-Investmentfonds (Nicht bei Organgesellschaften: Übertrag in die Hauptspalte)
Spezial_Invest/Hauptspalte	E8016107	237a	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Im Betrag laut Zeile 11 enthaltene laufende Erträge als Anleger an einem Spezial-Investmentfonds (Nicht bei Organgesellschaften: Übertrag in die Hauptspalte)
Spezial_Invest/Hauptspalte	E8016108	237b	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nicht bei Organgesellschaften: Dazu: Steuerpflichtige laufende Spezial-Investmenterträge nach § 20 Absatz 1 Nummer 3a EStG in Verbindung mit § 34 Absatz 1 Nummer 1 und 2 InvStG (Summe der Beträge laut Zeile 64 aller Anlagen SPIF, soweit die Anteile dem Gewerbebetrieb zuzuordnen sind)
Spezial_Invest/Hauptspalte	E8016109	237c	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Nicht bei Organgesellschaften: Davon ab / Dazu: Außerbilanzieller Korrekturbetrag bei Veräußerung von Anteilen an Spezial-Investmentfonds (Summe der Beträge laut Zeile 104 aller Anlagen SPIF, soweit die Anteile dem Gewerbebetrieb zuzuordnen sind)
Spezial_Invest/TW	E8016201	266	N	-	-	13.390	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab / Dazu: Positiver/negativer Anleger-Abkommensgewinn nach § 49 Absatz 1 Satz 1 Nummer 2 in Verbindung mit § 49 Absatz 1 Satz 2 InvStG
Spezial_Invest/TW/Vorspalte_2	E8016301	267	N	-	-	13.391	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Positiver/negativer Anleger-Teilfreistellungsgewinn nach § 49 Absatz 1 Satz 1 Nummer 3 in Verbindung mit § 49 Absatz 1 Satz 2 InvStG für Anleger, die dem KStG unterliegen (nicht bei Organgesellschaften: Übertrag in die Hauptspalte mit umgekehrtem Vorzeichen)
Spezial_Invest/TW/Hauptspalte_2	E8016302	267	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Positiver/negativer Anleger-Teilfreistellungsgewinn nach § 49 Absatz 1 Satz 1 Nummer 3 in Verbindung mit § 49 Absatz 1 Satz 2 InvStG für Anleger, die dem KStG unterliegen (nicht bei Organgesellschaften: Übertrag in die Hauptspalte mit umgekehrtem Vorzeichen)
Spezial_Invest/TW/Hauptspalte_2	E8016303	268	N	-	-	13.393	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab / Dazu: Positiver/negativer Anleger-Teilfreistellungsgewinn nach § 49 Absatz 1 Satz 1 Nummer 3 in Verbindung mit § 49 Absatz 1 Satz 2 InvStG in den Fällen des § 20 Absatz 1 Satz 4 und 5 InvStG
Organschaft/Neutral_OT	E8160501	270	U	-	-	17.110	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Erträge aus der Gewinnabführung der Organgesellschaft(en)
Organschaft/Neutral_OT	E8160601	271	U	-	-	17.111	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Aufwendungen des Organträgers aus der Verlustübernahme von Organgesellschaft(en)
Organschaft/Neutral_OT	E8160701	272	U	-	-	17.116	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Ausgleichszahlungen des Organträgers an außenstehende Anteilseigner der Organgesellschaft(en) (§ 4 Absatz 5 Satz 1 Nummer 9 EStG)
Organschaft/Neutral_OT	E8160903	275	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Mehrabführungen, die ihre Ursache in vororganschaftlicher Zeit haben (§ 14 Absatz 3 Satz 1 KStG) (Summe der Beträge laut Zeile 25c aller Anlagen OT, bei denen das Ende des Wirtschaftsjahres laut Anlage OT in dem Wirtschaftsjahr liegt, für das die Anlage GK ausgefüllt wird – gegebenenfalls multipliziert mit der Summe der Beträge laut Zeilen 8 und 9 dividiert durch die Summe der Beträge laut Zeilen 8 bis 10 der jeweiligen Anlage OT)
Organschaft/Neutral_OT	E8160902	276	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Minderabführungen, die ihre Ursache in vororganschaftlicher Zeit haben (§ 14 Absatz 3 Satz 2 KStG) (Summe der Beträge laut Zeile 25d aller Anlagen OT, bei denen das Ende des Wirtschaftsjahres laut Anlage OT in dem Wirtschaftsjahr liegt, für das die Anlage GK ausgefüllt wird – gegebenenfalls multipliziert mit der Summe der Beträge laut Zeilen 8 und 9 dividiert durch die Summe der Beträge laut Zeilen 8 bis 10 der jeweiligen Anlage OT)
Organschaft/Neutral_OT	E8160909	277	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Minderabführungen, die ihre Ursache in organschaftlicher Zeit haben (§ 14 Absatz 4 Satz 1 KStG) (Summe der Beträge laut Zeile 25b aller Anlagen OT, bei denen das Ende des Wirtschaftsjahres laut Anlage OT in dem Wirtschaftsjahr liegt, für das die Anlage GK ausgefüllt wird – gegebenenfalls multipliziert mit der Summe der Beträge laut Zeilen 8 und 9 dividiert durch die Summe der Beträge laut Zeilen 8 bis 10 der jeweiligen Anlage OT)
Organschaft/Neutral_OT	E8160910	278	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Mehrabführungen, die ihre Ursache in organschaftlicher Zeit haben (§ 14 Absatz 4 Satz 2 KStG) (Summe der Beträge laut Zeile 25a aller Anlagen OT, bei denen das Ende des Wirtschaftsjahres laut Anlage OT in dem Wirtschaftsjahr liegt, für das die Anlage GK ausgefüllt wird – gegebenenfalls multipliziert mit der Summe der Beträge laut Zeilen 8 und 9 dividiert durch die Summe der Beträge laut Zeilen 8 bis 10 der jeweiligen Anlage OT)
Organschaft/Neutral_OT	E8160911	279	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Saldo der Mehr- und Minderabführungen, die im laufenden Wirtschaftsjahr bilanziell berücksichtigt wurden, aus Feststellungen für den vorangegangenen Veranlagungszeitraum
Organschaft/Neutral_OT	E8160904	280	U	-	-	17.150	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verdeckte Gewinnausschüttungen der Organgesellschaft(en)
Organschaft/Neutral_OG	E8162001	281	U	-	-	17.112	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Von der Organgesellschaft an den Organträger abzuführender Gewinn
Organschaft/Neutral_OG	E8162101	282	U	-	-	17.113	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Vom Organträger an die Organgesellschaft zum Ausgleich eines sonst entstehenden Jahresfehlbetrages zu leistender Betrag
Organschaft/Neutral_OG	E8162201	283	U	-	-	17.234	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Von der Organgesellschaft geleistete Ausgleichszahlungen an außenstehende Anteilseigner (§ 4 Absatz 5 Satz 1 Nummer 9 EStG)
Organschaft/Neutral_OG	E8162202	284	U	-	-	17.152	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: An den Organträger geleistete verdeckte Gewinnausschüttungen (R 14.6 Absatz 4 Satz 1 KStR 2022)
Organschaft/Neutral_OG	E8162204	285	U	-	-	17.224	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Von der Organgesellschaft geleistete verdeckte Gewinnausschüttungen an außenstehende Anteilseigner (R 14.6 Absatz 4 Satz 4 KStR 2022)
Ni_ORG/Einzel	E8017605	286	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der Organgesellschaft
Ni_ORG/Einzel	E8017611	286	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
Ni_ORG/Einzel	E8017606	287	C	999	-	-	.{1,999}	Name der Organgesellschaft
Ni_ORG/Einzel	E8017607	288	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Mehrabführungen, die ihre Ursache in vororganschaftlicher Zeit haben (§ 14 Absatz 3 Satz 1 KStG)
Ni_ORG/Einzel	E8017608	289	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Minderabführungen, die ihre Ursache in vororganschaftlicher Zeit haben (§ 14 Absatz 3 Satz 2 KStG)
Ni_ORG/Einzel	E8017609	290	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Minderabführungen, die ihre Ursache in organschaftlicher Zeit haben (§ 14 Absatz 4 Satz 1 KStG)
Ni_ORG/Einzel	E8017610	291	%	-	-	-	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Mehrabführungen, die ihre Ursache in organschaftlicher Zeit haben (§ 14 Absatz 4 Satz 2 KStG)
Ni_ORG/Gesamt	E8017601	292	U	-	-	13.336	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Mehrabführungen, die ihre Ursache in vororganschaftlicher Zeit haben (§ 14 Absatz 3 Satz 1 KStG)
Ni_ORG/Gesamt	E8017602	293	U	-	-	13.337	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Minderabführungen, die ihre Ursache in vororganschaftlicher Zeit haben (§ 14 Absatz 3 Satz 2 KStG)
Ni_ORG/Gesamt	E8017603	294	U	-	-	13.339	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Minderabführungen, die ihre Ursache in organschaftlicher Zeit haben (§ 14 Absatz 4 Satz 1 KStG)
Ni_ORG/Gesamt	E8017604	295	U	-	-	13.338	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Mehrabführungen, die ihre Ursache in organschaftlicher Zeit haben (§ 14 Absatz 4 Satz 2 KStG)
Zinsschranke	E8004907	295a	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
Zinsschranke	E8004903	296	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Zinsaufwendungen nach § 4h Absatz 3 Satz 2 EStG des laufenden Wirtschaftsjahres (Betrag laut Zeile 11 der zugehörigen Anlage Zinsschranke)
Zinsschranke	E8004905	297	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Zinsaufwendungen nach § 4h Absatz 3 Satz 2 EStG des laufenden Wirtschaftsjahres der Organgesellschaft(en) (Betrag laut Zeile 12 der zugehörigen Anlage Zinsschranke)
Zinsschranke	E8004902	298	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Nach Anwendung des § 4h EStG in Verbindung mit § 8 Absatz 1, § 8a KStG als Betriebsausgaben abziehbare Zinsaufwendungen (Betrag laut Zeile 24 der zugehörigen Anlage Zinsschranke)
Einkunfte	E8004906	299	U	-	-	13.317	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verrechnung mit verrechenbaren Verlusten nach § 15a EStG, die aufgrund einer Anwachsung bei der Körperschaft zu berücksichtigen sind
Einkunfte	E8109901	300	N	-	Ja	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Einkünfte aus Gewerbebetrieb (Übertrag nach Zeile 2, 3 oder 4 der Anlage ZVE)
"""  # noqa: RUF001

# The JD, sheet „ZVE - Felder“.
_ZVE_2025 = r"""
SdE/LuF	E8022101	1	N	-	-	20.10	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Gewinn aus eigenen Betrieben (einschließlich Veräußerungsgewinn; laut gesonderter Ermittlung): Auf das Kalenderjahr $VZ$ entfallender Gewinn aus dem Wirtschaftsjahr $VZ-1$/$VZ$ ($VZ$)
SdE/LuF	E8022102	1a	N	-	-	20.12	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Gewinn aus eigenen Betrieben (einschließlich Veräußerungsgewinn; laut gesonderter Ermittlung): Auf das Kalenderjahr $VZ$ entfallender Gewinn aus dem Wirtschaftsjahr $VZ$/$VZ+1$
SdE/LuF/PG/Einzel	E8022104	1b	C	999	-	-	.{1,999}	Name der Gesellschaft
SdE/LuF/PG/Einzel	E8022106	1b	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer
SdE/LuF/PG/Einzel	E8022108	1b	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
SdE/LuF/PG/Einzel	E8022107	1b	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Einkünfte aus Land- und Forstwirtschaft laut gesonderter (und gegebenenfalls einheitlicher) Feststellung
SdE/LuF/PG/Gesamt	E8022103	1b	N	-	-	20.38	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Einkünfte aus Land- und Forstwirtschaft aus Beteiligungen an Personengesellschaften
SdE/Gewerbe/Laufend	E8004904	2	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Einkünfte aus Gewerbebetrieb laut Zeile 300 der Anlage GK; bei zusätzlichem Rumpfwirtschaftsjahr: Einkünfte aus Gewerbebetrieb des zweiten im Veranlagungszeitraum endenden Wirtschaftsjahres; bei mehreren Betrieben: Einkünfte aus Gewerbebetrieb der ersten Anlage GK
SdE/Gewerbe/Laufend	E8005002	3	N	-	-	13.211	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Bei zusätzlichem Rumpfwirtschaftsjahr: Einkünfte aus Gewerbebetrieb des ersten im Veranlagungszeitraum endenden Wirtschaftsjahres (laut Zeile 300 der Anlage GK für das erste Wirtschaftsjahr)
SdE/Gewerbe/Laufend	E8022403	4	N	-	-	13.151	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Bei mehreren Betrieben: Dazu / Davon ab: Einkünfte aus Gewerbebetrieb laut Zeile 300 der übrigen Anlagen GK
SdE/Gewerbe/VG	E8020503	5	N	-	-	13.251	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Veräußerungspreis aller im laufenden Veranlagungszeitraum veräußerten/aufgegebenen Betriebe
SdE/Gewerbe/VG	E8020603	6	U	-	-	13.252	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Veräußerungskosten
SdE/Gewerbe/VG	E8020702	7	N	-	-	13.253	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Wert des Betriebsvermögens
SdE/Gewerbe/VG	E8020703	7a	N	-	-	13.249	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Einkünfte aus Gewerbebetrieb nach § 17 EStG
SdE/Selbstandig/Einzel_Betrieb	E8023201	9	C	999	-	-	.{1,999}	Art der Tätigkeit
SdE/Selbstandig/Einzel_Betrieb	E8020902	9	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Einkünfte
SdE/Selbstandig/Gesamt_Betrieb	E8023202	9	N	-	-	13.160	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Einkünfte (einschließlich Veräußerungsgewinn) aus selbständiger Arbeit aus eigenen Betrieben (laut gesonderter Ermittlung)
SdE/Selbstandig/Beteiligung_PG/Einzel_PG	E8023301	10	C	999	-	-	.{1,999}	Name der Gesellschaft
SdE/Selbstandig/Beteiligung_PG/Einzel_PG	E8023305	10	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer
SdE/Selbstandig/Beteiligung_PG/Einzel_PG	E8023306	10	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
SdE/Selbstandig/Beteiligung_PG/Einzel_PG	E8023302	10	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Einkünfte aus selbständiger Arbeit laut gesonderter (und gegebenenfalls einheitlicher) Feststellung
SdE/Selbstandig/Beteiligung_PG/Gesamt_PG	E8023303	10	N	-	-	13.161	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Einkünfte aus selbständiger Arbeit aus Beteiligungen an Personengesellschaften
SdE/KapV	E8023701	11	N	-	-	26.40	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Einkünfte aus Kapitalvermögen ohne Beträge laut Zeile 11a (unter Berücksichtigung des § 20 Absatz 6 und 9 EStG; laut gesonderter Ermittlung)
SdE/KapV	E8023702	11a	N	-	-	26.41	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Einkünfte aus Kapitalvermögen, bei denen § 8 Absatz 10 Satz 2 KStG in Verbindung mit § 32d Absatz 2 Nummer 1 oder 3 EStG erfüllt ist
SdE/VuV	E8024101	12	N	-	-	25.120	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Einkünfte aus Vermietung und Verpachtung (laut gesonderter Ermittlung)
SdE/Invest_Steuerabzug	E8021202	12a	N	-	-	13.330	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Inländische Immobilienerträge nach § 6 Absatz 4 InvStG sowie sonstige inländische Einkünfte nach § 6 Absatz 5 InvStG, die keinem Steuerabzug unterliegen
SdE/SPIF	E8021201	12b	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Steuerpflichtige laufende Spezial-Investmenterträge nach § 20 Absatz 1 Nummer 3a EStG in Verbindung mit § 34 Absatz 1 Nummer 1 und 2 InvStG (Summe der Beträge laut Zeile 64 aller Anlagen SPIF, bei denen die Anteile keinem inländischen Betrieb zuzuordnen sind)
SdE/Sonstige/Bezuge	E8024201	13	N	-	-	26.58	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Einnahmen
SdE/Sonstige/Bezuge	E8024301	14	U	-	-	26.60	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Werbungskosten
SdE/Sonstige/Verausserung	E8024401	15	N	-	-	26.62	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Einkünfte aus privaten Veräußerungsgeschäften vor Berücksichtigung der Freigrenze nach § 23 Absatz 3 Satz 5 EStG
SdE/Sonstige/Verausserung	E8024404	15a	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Freigrenze nach § 23 Absatz 3 Satz 5 EStG (nur wenn Betrag laut Zeile 15 größer als 0 €, aber kleiner als 1.000 €: Betrag laut Zeile 15)
SdE/Sonstige/Verausserung	E8024405	15b	U	-	-	26.63	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verrechnung mit einem vortragsfähigen Verlust oder Berücksichtigung eines Verlustrücktrags
SdE/Sonstige/Verausserung	E8024406	15c	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Negativer Betrag laut Zeile 15 (mit umgekehrtem Vorzeichen eintragen)
SdE/Sonstige/Leistung	E8024601	16	N	-	-	26.64	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Einkünfte aus Leistungen nach § 22 Nummer 3 EStG vor Berücksichtigung der Freigrenze nach § 22 Nummer 3 Satz 2 EStG
SdE/Sonstige/Leistung	E8024604	16a	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Freigrenze nach § 22 Nummer 3 Satz 2 EStG (nur wenn Betrag laut Zeile 16 größer als 0 €, aber kleiner als 256 €: Betrag laut Zeile 16)
SdE/Sonstige/Leistung	E8024605	16b	U	-	-	26.65	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verrechnung mit einem vortragsfähigen Verlust oder Berücksichtigung eines Verlustrücktrags
SdE/Sonstige/Leistung	E8024606	16c	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Negativer Betrag laut Zeile 16 (mit umgekehrtem Vorzeichen eintragen)
SdE/P50a/P50aNR1/Einzel	E8043710	17	C	999	-	-	.{1,999}	Bezeichnung
SdE/P50a/P50aNR1/Einzel	E8043711	17	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Betrag
SdE/P50a/P50aNR1/Gesamt	E8043701	17	N	-	-	13.260	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Einkünfte, die dem Steuerabzug nach § 50a Absatz 1 Nummer 1 EStG unterlegen haben (laut gesonderter Einzelaufstellung)
SdE/P50a/P50aNR2/Einzel	E8043720	18	C	999	-	-	.{1,999}	Bezeichnung
SdE/P50a/P50aNR2/Einzel	E8043721	18	P	-	-	-	^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$	Betrag
SdE/P50a/P50aNR2/Gesamt	E8043702	18	N	-	-	13.261	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Einkünfte, die dem Steuerabzug nach § 50a Absatz 1 Nummer 2 EStG unterlegen haben (laut gesonderter Einzelaufstellung)
SdE/Abzug	E8004201	20	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nicht bei Organgesellschaften: Davon ab: Abzuziehende ausländische Steuern nach § 26 Absatz 1 Satz 1 Nummer 1 KStG in Verbindung mit § 34c Absatz 2 EStG (Summe der Beträge laut Zeile 42 aller Anlagen AESt zuzüglich Summe der Beträge laut Zeile 69 aller Anlagen SPIF zuzüglich Summe der Beträge laut Zeile 21 aller Anlagen SPIFA)
SdE/Abzug	E8004202	21	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nicht bei Organgesellschaften: Davon ab: Abzuziehende ausländische Steuern nach § 26 Absatz 1 Satz 1 Nummer 1 KStG in Verbindung mit § 34c Absatz 3 EStG (Summe aus 20 % des Betrages laut Zeile 11, 70 % des Betrages laut Zeile 14, 60 % des Betrages laut Zeile 17, 85 % des Betrages laut Zeile 20, 40 % des Betrages laut Zeile 23 und 20 % des Betrages laut Zeile 26 aller Anlagen AESt zuzüglich Summe der Beträge laut Zeilen 5a und 30 aller Anlagen AESt)
SdE/Negativ	E8004301	26	U	-	-	16.127	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nicht zu berücksichtigende negative Einkünfte / Gewinnminderungen nach § 2a Absatz 1 EStG (Summe der Beträge laut Zeilen 9 und 10 aller Anlagen AEV)
SdE/Negativ	E8004401	27	U	-	-	16.128	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verlustabzug nach § 2a Absatz 1 Satz 3 EStG (Summe der Beträge laut Zeile 15 aller Anlagen AEV)
SdE/KapESt	E8005301	28	U	-	-	15.62	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Abzuziehende Kapitalertragsteuer nach § 36a Absatz 1 Satz 3 EStG
SdE/Invest_Steuerbefreiung	E8022801	28a	N	-	-	15.63	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab / Dazu: Nach § 8 Absatz 1 und 2 sowie § 10 InvStG steuerfreie Einkünfte, die keinem Steuerabzug unterliegen
SdE/San_Ertrag	E8022901	29	U	-	-	15.71	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Betriebsvermögensmehrungen oder Betriebseinnahmen aus einem Schuldenerlass zum Zwecke einer unternehmensbezogenen Sanierung nach § 3a Absatz 2 EStG (Sanierungsertrag) (Übertrag nach Zeile 1 der Anlage SAN)
SdE/San_Ertrag	E8023001	30	U	-	-	15.72	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Mit dem steuerfreien Sanierungsertrag in unmittelbarem wirtschaftlichen Zusammenhang stehende Betriebsvermögensminderungen oder Betriebsausgaben nach § 3c Absatz 4 EStG des Sanierungsjahres (Übertrag nach Zeile 2 der Anlage SAN)
SdE/San_Ertrag	E8023101	31	U	-	-	15.73	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Mit einem in einem anderen Veranlagungszeitraum steuerfreien Sanierungsertrag nach § 3a Absatz 1 EStG in unmittelbarem wirtschaftlichen Zusammenhang stehende Betriebsvermögensminderungen oder Betriebsausgaben nach § 3c Absatz 4 EStG des laufenden Veranlagungszeitraums
SdE/AStG_ZwiG	E8023105	31a	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Summe der Hinzurechnungsbeträge nach § 10 AStG, die der Körperschaft als Feststellungsbeteiligte der Feststellung nach § 18 AStG zuzurechnen sind (Summe der Beträge laut Zeile 11 abzüglich Summe der Beträge laut Zeile 13 aller Anlagen ZwiG, auf denen keine Eintragungen in Zeile 6 vorgenommen wurden)
SdE/AStG_ZwiG	E8023107	31b	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nicht bei Organgesellschaften: Davon ab: Summe der Kürzungsbeträge nach § 11 Absatz 2 AStG (Summe der Beträge laut Zeile 33 gekürzt um die Summe der Beträge laut Zeilen 34 und 35 aller Anlagen ZwiG, auf denen keine Eintragungen in Zeile 6 vorgenommen wurden)
SdE/SdE	E8005401	32	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Summe der Einkünfte
GdE/LuF	E8025101	33	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Freibetrag für Land- und Forstwirtschaft (§ 13 Absatz 3 EStG)
GdE/Zuwendung	E8005601	34	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Abziehbare Zuwendungen nach § 9 Absatz 1 Nummer 2 KStG zur Förderung steuerbegünstigter Zwecke (Betrag laut Zeile 7 der Anlage Z)
GdE/Hinzurechnung	E8005701	35	N	-	-	16.121	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu: Hinzurechnungsbetrag
GdE/P2Abs5UmwStG	E8005703	35a	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
GdE/P2Abs5UmwStG	E8005702	35b	U	-	-	15.59	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Negative Einkünfte des übernehmenden Rechtsträgers nach § 2 Absatz 5 UmwStG
GdE/P8cKStG_Lfd	E8006304	36	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
GdE/P8cKStG_Lfd	E8006301	37	U	-	-	15.51	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Nach § 8c KStG nicht berücksichtigungsfähiger Verlust des laufenden Veranlagungszeitraums (gegebenenfalls in Verbindung mit § 2 Absatz 4 Satz 1 und 2, § 20 Absatz 6 Satz 4 UmwStG) (ohne Vorzeichen eintragen; laut gesonderter Ermittlung)
GdE/Einkommen_OT	E8006401	38	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Dazu / Davon ab: Korrigierte zuzurechnende Einkommen der Organgesellschaften (Summe der Beträge aus Zeile 25 aller Anlagen OT)
GdE/Abspaltung	E8023203	39	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
GdE/Abspaltung	E8006402	40	U	-	-	15.52	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Im Falle einer Abspaltung bei der übertragenden Körperschaft: wegfallender Verlust aus dem laufenden Veranlagungszeitraum nach § 15 Absatz 3, § 16 UmwStG (ohne Vorzeichen eintragen)
GdE/San_Lfd	E8003302	41	U	-	-	15.78	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Minderung des laufenden Verlustes des Sanierungsjahres des zu sanierenden Unternehmens nach § 3a Absatz 3 Satz 2 Nummer 8 EStG (Betrag laut Zeile 17 der Anlage SAN)
GdE/San_Lfd	E8003303	42	U	-	-	15.79	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Minderung des ausgleichsfähigen Verlustes aus allen anderen Einkunftsarten des Veranlagungszeitraums, in dem das Sanierungsjahr endet nach § 3a Absatz 3 Satz 2 Nummer 9 EStG (Betrag laut Zeile 19 der Anlage SAN)
GdE/Einkommen_OG	E8023401	43	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme (Bei einer Organgesellschaft: Einkommen der Organgesellschaft vor Zurechnung an den Organträger)
GdE/Einkommen_OG	E8006601	44	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab / Dazu: Dem Organträger zuzurechnendes Einkommen (Betrag laut Zeile 31 der Anlage OG; einzutragen mit umgekehrtem Vorzeichen)
GdE/Einkommen_OG	E8006501	45	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Vom Organträger zu leistende Ausgleichszahlungen nach § 16 Satz 2 KStG (Betrag laut Zeile 28 der Anlage OG)
GdE/P2Abs4	E8006602	46	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
GdE/P2Abs4/Vorspalte	E8006603	47	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Betrag laut Zeile 46
GdE/P2Abs4/Vorspalte	E8006604	48	U	-	-	15.53	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Im Betrag laut Zeile 47 enthaltene positive Einkünfte des übertragenden oder einbringenden Rechtsträgers im Rückwirkungszeitraum aus eigenen Übernahmen
GdE/P2Abs4/Vorspalte	E8006605	49	U	-	-	15.54	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Im Betrag laut Zeile 47 enthaltene positive Einkünfte des übertragenden oder einbringenden Rechtsträgers im Rückwirkungszeitraum laut gesonderter und einheitlicher Feststellung einer Personengesellschaft
GdE/P2Abs4/Vorspalte	E8006606	50	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Im Betrag laut Zeile 47 enthaltene positive Einkünfte des übertragenden oder einbringenden Rechtsträgers im Rückwirkungszeitraum laut gesonderter und einheitlicher Feststellung(en) nach § 14 Absatz 5 KStG (Summe der Beträge laut Zeile 27 aller Anlagen OT)
GdE/P2Abs4/Vorspalte	E8006607	51	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme: Wenn negativ: Nach § 2 Absatz 4 Satz 3 und 4 UmwStG nicht ausgleichsfähiger Verlust des übernehmenden Rechtsträgers (Übertrag eines negativen Betrages in die Hauptspalte mit umgekehrtem Vorzeichen)
GdE/P2Abs4/Hauptspalte	E8006608	51	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zwischensumme: Wenn negativ: Nach § 2 Absatz 4 Satz 3 und 4 UmwStG nicht ausgleichsfähiger Verlust des übernehmenden Rechtsträgers (Übertrag eines negativen Betrages in die Hauptspalte mit umgekehrtem Vorzeichen)
GdE/P2Abs4_OHK	E8006609	52	U	-	-	15.74	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nicht bei Organgesellschaften: Dazu: Nach § 2 Absatz 4 Satz 3 und 4 UmwStG nicht ausgleichsfähiger Verlust des übernehmenden Rechtsträgers (Betrag laut Zeile 208 Hauptspalte aller Anlagen ÖHK)
GdE/GdE	E8006901	53	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Gesamtbetrag der Einkünfte
GdE/GdE	E8006801	54	U	-	-	15.75	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bei Gesellschaften, die unter § 8 Absatz 7 Satz 1 Nummer 2 Satz 2 KStG fallen, und bei Gesellschaften und Betrieben gewerblicher Art, die Organträger solcher Gesellschaften sind; nicht bei Organgesellschaften: Dazu: Summe der negativen Gesamtbeträge der Einkünfte aus den einzelnen Sparten nach § 8 Absatz 9 Satz 1 Nummer 1 bis 3 KStG (Betrag laut Zeile 210 aller Anlagen ÖHK)
GdE/GdE	E8006902	55	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Maßgeblicher Gesamtbetrag der Einkünfte in den Fällen des § 8 Absatz 9 KStG
ZVE/Verlustabzug	E8007001	56	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Verlustabzug aufgrund der Verrechnung mit dem Verlustvortrag (nicht in den Fällen des § 8 Absatz 9 KStG); (Summe der Beträge laut Zeilen 25 und 27 der Anlage Verluste oder des Betrages laut Zeile 5 der Anlage Invest-Verluste)
ZVE/Verlustabzug	E8007002	57	N	-	-	15.76	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Verlustabzug aufgrund der Verrechnung mit dem Verlustvortrag (in den Fällen des § 8 Absatz 9 KStG); (Betrag laut Zeile 233 aller Anlagen ÖHK)
ZVE/Verlustabzug	E8007101	58	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Verlustabzug aufgrund eines Verlustrücktrags aus dem folgenden Veranlagungszeitraum, gegebenenfalls unter Berücksichtigung des § 2 Absatz 4 Satz 3 UmwStG und des § 3a Absatz 3 Satz 2 Nummer 12 Satz 2 EStG (nicht in den Fällen des § 8 Absatz 9 KStG)
ZVE/Verlustabzug	E8007103	58a	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Verlustabzug aufgrund eines Verlustrücktrags aus dem zweiten folgenden Veranlagungszeitraum, gegebenenfalls unter Berücksichtigung des § 2 Absatz 4 Satz 3 UmwStG und des § 3a Absatz 3 Satz 2 Nummer 12 Satz 2 EStG (nicht in den Fällen des § 8 Absatz 9 KStG)
ZVE/Verlustabzug	E8007102	59	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Verlustabzug aufgrund eines Verlustrücktrags aus dem folgenden Veranlagungszeitraum, gegebenenfalls unter Berücksichtigung des § 2 Absatz 4 Satz 3 UmwStG und des § 3a Absatz 3 Satz 2 Nummer 12 Satz 2 EStG (in den Fällen des § 8 Absatz 9 KStG)
ZVE/Verlustabzug	E8007104	59a	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: Verlustabzug aufgrund eines Verlustrücktrags aus dem zweiten folgenden Veranlagungszeitraum, gegebenenfalls unter Berücksichtigung des § 2 Absatz 4 Satz 3 UmwStG und des § 3a Absatz 3 Satz 2 Nummer 12 Satz 2 EStG (in den Fällen des § 8 Absatz 9 KStG)
ZVE/P10g	E8026301	60	G	-	-	15.43	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Davon ab: Abzugsbetrag nach § 10g EStG (Abzug höchstens bis auf 0 €)
ZVE/Kassen	E8025301	61	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ZVE/Kassen	E8025402	62	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon steuerpflichtiges Einkommen in Höhe der Überdotierung (Betrag laut Zeile 61 multipliziert mit dem Wert laut Zeile 45 der Anlage Kassen, dividiert durch den Wert laut Zeile 43 der Anlage Kassen beziehungsweise Betrag laut Zeile 61 multipliziert mit dem Wert laut Zeile 62 der Anlage Kassen, dividiert durch Wert laut Zeile 60 der Anlage Kassen)
ZVE/Kassen/UKasse/Vorspalte	E8025502	63	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Höhe der im Wirtschaftsjahr getätigten Versorgungsleistungen
ZVE/Kassen/UKasse/Vorspalte	E8025602	64	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Festgestellter Betrag nach § 6 Absatz 5a Satz 6 Nummer 2 KStG zum Ende des vorangegangenen Veranlagungszeitraums
ZVE/Kassen/UKasse/Vorspalte	E8025702	65	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Betrag nach § 6 Absatz 5a Satz 4 und 5 KStG (wenn Betrag laut Zeile 62 positiv: niedrigerer Betrag aus den Zeilen 62, 63 oder 64)
ZVE/Kassen/UKasse/Hauptspalte	E8025703	65	U	-	-	15.58	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Betrag nach § 6 Absatz 5a Satz 4 und 5 KStG (wenn Betrag laut Zeile 62 positiv: niedrigerer Betrag aus den Zeilen 62, 63 oder 64)
ZVE/Kassen/UKasse/Feststellung	E8025802	66	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Festzustellender Betrag nach § 6 Absatz 5a Satz 6 Nummer 2 KStG zum Ende des laufenden Veranlagungszeitraums (Betrag laut Zeile 64 abzüglich Betrag laut Zeile 65)
ZVE/Rundfunk	E8025903	67	U	-	-	15.55	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Einkommen nach § 8 Absatz 1 Satz 3 KStG
ZVE/Einkommen	E8007301	68	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Einkommen
ZVE/Einkommen	E8006802	68a	G	-	-	15.28	2	Nur bei Genossenschaften und steuerpflichtigen Vereinen, die ausschließlich Einkünfte aus Land- und Forstwirtschaft erzielen: Die Voraussetzungen für einen Freibetrag nach § 25 KStG liegen vor
ZVE/Einkommen	E8006803	68b	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Freibetrag nach § 25 KStG
ZVE/Einkommen	E8007401	69	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Freibetrag nach § 24 KStG für bestimmte Körperschaften (Betrag laut Zeile 68, höchstens 5.000 €)
ZVE/ZVE	E8007501	70	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zu versteuerndes Einkommen
Steuerberechnung/Regel	E8007504	71	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Von dem zu versteuernden Einkommen (Betrag laut Zeile 70) unterliegen dem Regelsteuersatz von 15 %
Steuerberechnung/Regel	E8007502	71	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Körperschaftsteuer (15 % des Betrages laut Vorspalte)
Steuerberechnung/Besonders	E8007601	72	%	-	-	15.81	^(?=.{4,5}$)(?!0\d)\d{1,15}(,\d{2,2})$	Besonderer Steuersatz in Höhe von
Steuerberechnung/Besonders	E8007602	72	C	999	-	-	.{1,999}	Besonderer Steuersatz nach §
Steuerberechnung/Besonders	E8007603	72a	N	-	-	15.82	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Von dem zu versteuernden Einkommen (Betrag laut Zeile 70) unterliegen dem besonderen Steuersatz laut Zeile 72
Steuerberechnung/Besonders	E8007604	72a	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Körperschaftsteuer (Prozentsatz laut Zeile 72 multipliziert mit dem Betrag laut Vorspalte)
Steuerberechnung/Besonders	E8007606	73	U	-	-	15.85	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Betrag der aufgelösten Rücklage nach § 3 Absatz 4 Satz 2 Forstschäden-Ausgleichsgesetz
Steuerberechnung/Besonders	E8007607	73	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Körperschaftsteuer (10 % des Betrages laut Vorspalte)
Ber	E8007704	74	N	-	-	15.80	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Mittel, die für die unmittelbare oder mittelbare Unterstützung oder Förderung politischer Parteien verwendet wurden
Ber	E8007705	75	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Körperschaftsteuer (50 % des Betrages aus Zeile 74)
Invest	E8007605	76	N	-	-	15.83	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Inländische Beteiligungseinnahmen und sonstige inländische Einkünfte, für die ein Steuerabzug nachzuholen ist (§ 6 Absatz 3 und 5 in Verbindung mit § 7 InvStG) (laut gesonderter Ermittlung)
Invest	E8007701	77	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Körperschaftsteuer auf den Betrag laut Zeile 76 (Steuersatz nach § 7 Absatz 1 InvStG)
"""

# The JD, sheet „Z - Felder“.
_Z_2025 = r"""
Ermittlung	E8009401	1	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Zuwendungsvortrag zum Schluss des vorangegangenen Veranlagungszeitraums
Ermittlung	E8010001	2	U	-	-	15.66	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Im Falle einer Abspaltung oder Teilübertragung im laufenden Veranlagungszeitraum: Verringerung des verbleibenden Zuwendungsvortrags bei der übertragenden Körperschaft (§ 12 Absatz 3 UmwStG in Verbindung mit § 15 Absatz 1, § 16 UmwStG)
Ermittlung	E8009501	3	U	-	-	15.46	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Bei der übernehmenden Körperschaft im Jahr der Vermögensübernahme: Auf die übernehmende Körperschaft im laufenden Veranlagungszeitraum übergegangener Zuwendungsvortrag nach § 9 Absatz 1 Nummer 2 Satz 9 KStG in Verbindung mit § 12 Absatz 3 UmwStG (gegebenenfalls in Verbindung mit § 15 Absatz 1 UmwStG)
Ermittlung/Zuwendung/Einzel	E8009506	4	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der Personengesellschaft
Ermittlung/Zuwendung/Einzel	E8009509	4	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer der Personengesellschaft
Ermittlung/Zuwendung/Einzel	E8009507	4	C	999	-	-	.{1,999}	Name der Personengesellschaft
Ermittlung/Zuwendung/Einzel	E8009508	4	R	-	-	-	^(?=.{4,15}$)(?=.*[1-9].*)(?!0\d)\d{1,12}(,\d{2,2})$	Betrag
Ermittlung/Zuwendung/Gesamt	E8009502	4	U	-	-	15.48	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Im Kalenderjahr $VZ$ beziehungsweise im Wirtschaftsjahr $VZ-1$/$VZ$ geleistete Zuwendungen (Spenden und Mitgliedsbeiträge) für steuerbegünstigte Zwecke nach §§ 52 bis 54 AO aus Beteiligung an einer Personengesellschaft (laut gesonderter und einheitlicher Feststellung)
Ermittlung/Zuwendung/Einzel_2	E8005603	5	C	999	-	-	.{1,999}	Name des Empfängers
Ermittlung/Zuwendung/Einzel_2	E8005604	5	R	-	-	-	^(?=.{4,15}$)(?=.*[1-9].*)(?!0\d)\d{1,12}(,\d{2,2})$	Betrag laut Bestätigung
Ermittlung/Zuwendung/Einzel_2	E8005605	5	H	-	-	-	\Q1\E|\Q2\E	Der Empfänger liegt im
Ermittlung/Zuwendung/Gesamt_2	E8005602	5	U	-	-	15.40	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Im Kalenderjahr $VZ$ beziehungsweise im Wirtschaftsjahr $VZ-1$/$VZ$ geleistete Zuwendungen (Spenden und Mitgliedsbeiträge) für steuerbegünstigte Zwecke nach §§ 52 bis 54 AO laut Zuwendungsbestätigungen
Ermittlung/Fortfuhrung	E8009701	6	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zwischensumme
Ermittlung/Fortfuhrung	E8006101	7	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Unter Beachtung der Höchstbeträge abziehbare Zuwendungen (Übertrag nach Zeile 34 der Anlage ZVE)
Ermittlung/Fortfuhrung	E8006102	7a	U	-	-	15.65	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Minderung des verbleibenden Zuwendungsvortrags durch Abspaltung oder Teilübertragung zum Ende des Veranlagungszeitraums (§ 12 Absatz 3 UmwStG in Verbindung mit § 15 Absatz 1, § 16 UmwStG)
Ermittlung/Fortfuhrung	E8006103	7b	U	-	-	15.64	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Bei der übernehmenden Körperschaft im Jahr der Vermögensübernahme: Auf die übernehmende Körperschaft zum Ende des Veranlagungszeitraums übergegangener Zuwendungsvortrag nach § 9 Absatz 1 Nummer 2 Satz 9 KStG in Verbindung mit § 12 Absatz 3 UmwStG (gegebenenfalls in Verbindung mit § 15 Absatz 1 UmwStG)
Ermittlung/Fortfuhrung	E8010101	8	N	-	Ja	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibender Zuwendungsvortrag zum Schluss des Veranlagungszeitraums
Ermittlung/Fortfuhrung	E8009601	9	U	-	-	15.42	^(?=.{1,12}$)(?!0\d)\d{1,12}$	In Zeile 5 enthaltene Zuwendungen an Empfänger im EU-/EWR-Ausland
Ermittlung/Hochstbetrag	E8006001	10	U	-	-	15.18	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Summe der gesamten Umsätze sowie der im Kalenderjahr $VZ$ aufgewendeten Löhne und Gehälter
Ermittlung/Hochstbetrag	E8001101	11	U	-	-	15.84	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Summe der gesamten Umsätze sowie der im Kalenderjahr $VZ$ aufgewendeten Löhne und Gehälter aus Beteiligung an einer Personengesellschaft
"""

# The JD, sheet „Verluste - Felder“.
_VERLUSTE_2025 = r"""
Anfang	E8007801	11	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Verlustvortrag zum Schluss des vorangegangenen Veranlagungszeitraums
Anfang	E8007804	13	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Untergang des fortführungsgebundenen Verlustvortrags aufgrund eines schädlichen Ereignisses nach § 8d Absatz 2 KStG (Betrag laut Zeile 29)
Anfang	E8007805	14	U	-	-	37.39	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Erhalt des fortführungsgebundenen Verlustvortrags nach § 8d Absatz 2 Satz 1 zweiter Halbsatz KStG durch entsprechende Anwendung des § 8c Absatz 1 Satz 5 bis 8 KStG bezogen auf die zum Schluss des vorangegangenen Veranlagungszeitraums vorhandenen stillen Reserven (höchstens Betrag laut Zeile 13; laut gesonderter Ermittlung)
Anfang	E8007803	14a	U	-	-	37.25	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nur für Betriebe gewerblicher Art: Dazu: Zu übernehmender verbleibender Verlustvortrag (§ 8 Absatz 8 KStG)
Anfang	E8007902	15	U	-	-	37.36	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Nicht zu berücksichtigender Verlustvortrag nach § 8c KStG (gegebenenfalls in Verbindung mit § 2 Absatz 4 Satz 1, § 20 Absatz 6 Satz 4 UmwStG; laut gesonderter Ermittlung)
Anfang	E8007905	16	U	-	-	37.21	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verringerung des Verlustvortrags durch Abspaltung (§ 15 Absatz 3, § 16 UmwStG)
Anfang	E8007907	17	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zwischensumme
Anfang	E8007908	18	U	-	-	37.54	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Minderung des Verlustvortrags nach § 3a Absatz 3 Satz 2 Nummer 10 EStG (Betrag laut Zeile 21 der Anlage SAN)
Negativ	E8008001	19	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Berücksichtigungsfähiger Verlust des laufenden Veranlagungszeitraums (negativer Betrag laut Zeile 53 der Anlage ZVE oder wenn Betrag laut Zeile 51 Vorspalte der Anlage ZVE negativ: Betrag laut Zeile 51 Vorspalte der Anlage ZVE)
Negativ	E8001902	19a	U	-	-	37.55	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Minderung der negativen Einkünfte nach § 3a Absatz 3 Satz 2 Nummer 12 EStG aufgrund eines Sanierungsertrags in $VZ-1$
Negativ	E8001904	19b	U	-	-	37.56	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Minderung der negativen Einkünfte nach § 3a Absatz 3 Satz 2 Nummer 12 EStG aufgrund eines Sanierungsertrags in $VZ-2$
Negativ	E8008102	20	U	-	-	37.28	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verlustrücktrag auf das Einkommen $VZ-1$ und $VZ-2$ (höchstens 1 Million €; bei Verzicht auf den Verlustrücktrag: Eintrag mit 0)
Negativ	E8008401	21	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zwischensumme
Positiv/Vorspalte	E8008501	22	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Positiver Gesamtbetrag der Einkünfte (positiver Betrag laut Zeile 53 der Anlage ZVE)
Positiv/Vorspalte	E8008502	23	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Im Falle von Umwandlungen mit steuerlicher Rückwirkung beim übernehmenden Rechtsträger: Davon ab: Im Betrag laut Zeile 22 enthaltene positive Einkünfte des übertragenden oder einbringenden Rechtsträgers im Rückwirkungszeitraum (vergleiche § 2 Absatz 4 Satz 3 und 4 UmwStG) - Summe der Beträge laut Zeilen 48 bis 50 Vorspalte der Anlage ZVE
Positiv/Vorspalte	E8008503	24	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zwischensumme
Positiv/Vorspalte	E8008601	25	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Niedrigerer Betrag aus Zeile 21 und 24, höchstens 1 Million € (Übertrag des Betrages laut Hauptspalte nach Zeile 56 der Anlage ZVE)
Positiv/Vorspalte	E8008701	26	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zwischensumme
Positiv/Hauptspalte	E8008602	25	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Niedrigerer Betrag aus Zeile 21 und 24, höchstens 1 Million € (Übertrag des Betrages laut Hauptspalte nach Zeile 56 der Anlage ZVE)
Positiv/Hauptspalte	E8008702	26	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zwischensumme
Positiv/Hauptspalte	E8008801	27	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Betrag laut Zeile 26 Hauptspalte, höchstens 70 % des Betrages laut Zeile 26 Vorspalte (Übertrag des Betrages laut Hauptspalte nach Zeile 56 der Anlage ZVE)
Ende	E8009201	28	U	-	Ja	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Verlustvortrag zum Schluss des Veranlagungszeitraums
Ffg_Verlust	E8009303	29	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender fortführungsgebundener Verlustvortrag zum Schluss des vorangegangenen Veranlagungszeitraums
Ffg_Verlust	E8009304	30	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Untergang des fortführungsgebundenen Verlustvortrags aufgrund eines schädlichen Ereignisses nach § 8d Absatz 2 KStG (Betrag laut Zeile 29)
Ffg_Verlust	E8009305	31	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Wegfall der Fortführungsgebundenheit bei Vorliegen eines schädlichen Beteiligungserwerbs nach § 8c KStG (Betrag laut Zeile 29)
Ffg_Verlust	E8009306	32	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Im wegfallenden Verlustvortrag enthaltener fortführungsgebundener Verlustvortrag (im Betrag laut Zeile 16 enthalten, höchstens Betrag laut Zeile 29 abzüglich Summe der Beträge laut Zeilen 30 und 31)
Ffg_Verlust	E8009308	34	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Verrechnung mit dem fortführungsgebundenen Verlust (Summe der Beträge laut Zeilen 18, 25 und 27, höchstens Betrag laut Zeile 29 abzüglich Summe der Beträge laut Zeilen 30 bis 32)
Ffg_Verlust	E8009310	36	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Wenn im Veranlagungszeitraum ein schädlicher Beteiligungserwerb nach § 8c KStG erfolgte und die Voraussetzungen zur Anwendung des § 8d KStG erfüllt sind: Dazu: Zugang zum fortführungsgebundenen Verlustvortrag (Betrag laut Zeile 28 abzüglich Betrag laut Zeile 29 zuzüglich Summe der Beträge laut Zeilen 30 bis 34)
Ffg_Verlust	E8009311	37	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Im Betrag laut Zeile 28 enthaltener zum Schluss des Veranlagungszeitraums verbleibender fortführungsgebundener Verlustvortrag
Beitritt	E8007802	38	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Von den Beträgen laut Zeile 11 beziehungsweise 14a entfällt auf den in 1990 entstandenen Verlust aus dem Beitrittsgebiet nach § 57 Absatz 4 EStG
Beitritt	E8003904	39	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Untergang des fortführungsgebundenen Verlustvortrags aufgrund eines schädlichen Ereignisses nach § 8d Absatz 2 KStG (Betrag laut Zeile 38)
Beitritt	E8004003	40	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Dazu: Erhalt des fortführungsgebundenen Verlustvortrags nach § 8d Absatz 2 Satz 1 zweiter Halbsatz KStG durch entsprechende Anwendung des § 8c Absatz 1 Satz 5 bis 8 KStG bezogen auf die zum Schluss des vorangegangenen Veranlagungszeitraums vorhandenen stillen Reserven (Betrag laut Zeile 14 höchstens Betrag laut Zeile 38)
Beitritt	E8007906	41	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Davon ab: In den Beträgen laut Zeilen 15, 16 und 18 enthaltener, in 1990 entstandener Verlust aus dem Beitrittsgebiet nach § 57 Absatz 4 EStG
Beitritt	E8009302	42	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Davon ab: Summe der Beträge laut Zeilen 25 und 27, höchstens Betrag laut Zeile 38 abzüglich der Beträge laut Zeilen 39 und 41 zuzüglich Betrag laut Zeile 40
Beitritt	E8009301	43	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zum Schluss des Veranlagungszeitraums verbleibender Verlust aus dem Beitrittsgebiet nach § 57 Absatz 4 EStG
"""

# The JD, sheet „WA - Felder“.
_WA_2025 = r"""
KapESt	E8120401	2	%	-	-	19.131	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Kapitalertragsteuer laut gesondert übermittelten Steuerbescheinigungen (ohne Beträge laut Zeile 6)
KapESt	E8120601	3	%	-	-	19.133	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Solidaritätszuschlag zur Kapitalertragsteuer laut Zeile 2
KapESt	E8120402	4	%	-	-	19.231	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Kapitalertragsteuer laut gesonderter und einheitlicher Feststellung aus Beteiligungen an Personengesellschaften (ohne Beträge laut Zeile 6)
KapESt	E8120502	5	%	-	-	19.233	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Solidaritätszuschlag zur Kapitalertragsteuer laut Zeile 4 (laut gesonderter und einheitlicher Feststellung aus Beteiligungen an Personengesellschaften)
KapESt	E8120602	6	%	-	-	19.261	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Kapitalertragsteuer, für die die Voraussetzungen des § 36a Absatz 1 Satz 1 EStG nicht erfüllt sind und die Anrechnung auf zwei Fünftel beschränkt ist (laut gesondert übermittelten Steuerbescheinigungen und laut gesonderter und einheitlicher Feststellung aus Beteiligungen an Personengesellschaften; die Kapitalertragsteuer ist in voller Höhe einzutragen; die Beschränkung der Anrechnung erfolgt von Amts wegen)
KapESt	E8120702	7	%	-	-	19.263	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Solidaritätszuschlag zur Kapitalertragsteuer laut Zeile 6
Steuerabzugsbetrag	E8120701	8	%	-	-	19.134	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Anrechenbarer Steuerabzugsbetrag nach § 50a Absatz 1 Nummer 1 und 2 EStG sowie nach § 50a Absatz 7 EStG (laut gesondert übermitteltem Nachweis) (nur bei beschränkt steuerpflichtigen Vergütungsgläubigern ausfüllen; wenn während des Kalenderjahres sowohl unbeschränkte als auch beschränkte Steuerpflicht bestanden hat: für die Zeit der beschränkten Steuerpflicht einbehaltener Steuerabzugsbetrag)
Steuerabzugsbetrag	E8120901	9	%	-	-	19.234	^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$	Solidaritätszuschlag zum Abzugsbetrag laut Zeile 8
P50dAbs10	E8180403	10	N	-	-	16.239	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Inländische Einkünfte nach § 50d Absatz 10 EStG
P50dAbs10	E8180404	11	N	-	-	16.249	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Darauf entfallende festgesetzte, gezahlte, um einen entstandenen Ermäßigungsanspruch gekürzte, anteilige ausländische Steuer (laut Nachweis), die der deutschen Einkommensteuer beziehungsweise Körperschaftsteuer entspricht und auf die die deutsche Steuer nicht angerechnet wurde (§ 50d Absatz 10 Satz 5 EStG)
Erwerb_P8c	E8122710	11a	Y	-	-	19.264	1|2	Die Voraussetzungen des § 8c Absatz 1 Satz 1 KStG wurden in diesem Veranlagungszeitraum erfüllt, weil innerhalb der letzten fünf Jahre mittelbar oder unmittelbar mehr als 50 % des gezeichneten Kapitals, der Mitgliedschaftsrechte, der Beteiligungsrechte oder der Stimmrechte an der Körperschaft an einen Erwerber oder diesem nahe stehende Personen übertragen wurden oder ein vergleichbarer Sachverhalt vorliegt.
Erwerb_P8c	E8122711	11b	J	-	-	19.265	1	Die Anwendung des § 8c KStG ist ausgeschlossen, weil ein Erwerb seitens einer natürlichen Person durch Erbfall einschließlich der in vollem Umfang unentgeltlichen Erbauseinandersetzung und der in vollem Umfang unentgeltlichen vorweggenommenen Erbfolge zwischen Angehörigen nach § 15 AO vorliegt; vergleiche Randnummer 4 des BMF-Schreibens vom 28.11.2017, BStBl I 2017, 1645.
Erwerb_P8c/Konzern	E8122712	11c	H	-	-	19.266	\Q1\E|\Q2\E|\Q3\E	Die Voraussetzungen der Konzernklausel nach § 8c Absatz 1 Satz 4 KStG sind erfüllt.
Erwerb_P8c/Stille_Res	E8122713	11d	J	-	-	19.267	1	Bei der Ermittlung der nichtabziehbaren nicht genutzten Verluste nach § 8c Absatz 1 Satz 1 KStG wurde die Stille-Reserven-Klausel berücksichtigt, vergleiche § 8c Absatz 1 Satz 5 folgende KStG.
Erwerb_P8c/Stille_Res	E8122714	11e	U	-	-	19.268	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Höhe der gesamten zum Zeitpunkt des schädlichen Beteiligungserwerbs vorhandenen im Inland steuerpflichtigen stillen Reserven des Betriebsvermögens der Körperschaft bei Anwendung der Stille-Reserven-Klausel; vergleiche Randnummer 50 folgende des BMF-Schreibens vom 28.11.2017, BStBl I 2017, 1645 (laut gesonderter Ermittlung)
Erwerb_P8c/Sanierung	E8122715	11f	J	-	-	19.269	1	Es liegt ein Beteiligungserwerb zum Zweck der Sanierung des Geschäftsbetriebs der Körperschaft nach § 8c Absatz 1a KStG vor.
Erwerb_P8c/Sanierung	E8122716	11g	Y	-	-	19.270	1|2	Erforderliche Angaben zu § 8c Absatz 1a KStG, wenn innerhalb der letzten fünf vorangegangenen Veranlagungszeiträume die Sanierungsklausel angewendet wurde: Die Voraussetzungen für die Anwendung der Sanierungsklausel liegen weiterhin vor.
Ffg_Verlust	E8122701	12	J	-	-	19.237	1	Der Antrag nach § 8d KStG wird gestellt. Die gesetzlichen Voraussetzungen hierfür liegen vollumfänglich vor; insbesondere wurde seit dem Beginn des dritten Veranlagungszeitraums, der dem schädlichen Beteiligungserwerb vorausgeht, ausschließlich derselbe Geschäftsbetrieb unterhalten und zusätzlich hat in diesem Zeitraum bis zum Schluss des Veranlagungszeitraums $VZ$ kein Ereignis nach § 8d Absatz 2 KStG stattgefunden.
Ffg_Verlust/Vorjahr	E8122702	13	Y	-	-	19.238	1|2	Im Veranlagungszeitraum sind Ereignisse nach § 8d Absatz 2 KStG eingetreten. Die festgestellten fortführungsgebundenen Verlustvorträge gehen unter.
Ffg_Verlust/Vorjahr	E8122703	14	Y	-	-	19.239	1|2	Es liegen stille Reserven zum Schluss des vorangegangenen Veranlagungszeitraums (§ 8d Absatz 2 Satz 1 zweiter Halbsatz KStG) vor.
AE	E8122801	15	Y	-	-	19.211	1|2	Sind vertragliche Vereinbarungen (Anstellungsverträge, Mietverträge, Darlehensverträge, Pensionszusagen) mit Anteilseignern und/oder diesen nahe stehenden Personen im Veranlagungszeitraum abgeschlossen beziehungsweise geändert worden? Entsprechende Verträge sind dem Finanzamt vorzulegen.
AE/Einzel	E8123003	16	C	999	-	-	.{1,999}	Vertragsart
AE/Einzel	E8123004	16	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Datum der letzten Vertragsänderung oder des Vertragsabschlusses
AE/Einzel	E8123005	16	C	999	-	-	.{1,999}	Name des Vertragspartners
AE/Einzel	E8123006	16	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Höhe der Vergütung
Aufsichtsrat/Empfanger	E8123301	20	C	999	-	-	.{1,999}	Vor- und Nachname
Aufsichtsrat/Empfanger	E8123302	20a	C	999	-	-	.{1,999}	Straße und Hausnummer
Aufsichtsrat/Empfanger	E8123303	20b	C	999	-	-	.{1,999}	Postleitzahl und Wohnort
Aufsichtsrat/Empfanger	E8123309	20d	I	-	-	-	[0-9]{11}	Identifikationsnummer
Aufsichtsrat/Empfanger	E8123305	20e	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer
Aufsichtsrat/Empfanger	E8123311	20f	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
Aufsichtsrat/Empfanger	E8123306	20g	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Im Kalenderjahr geleistete Vergütungen
Aufsichtsrat/Empfanger	E8123307	20h	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Darin enthaltene Umsatzsteuer
Multinationale	E8123805	27	H	-	-	19.212	\Q1\E|\Q2\E|\Q3\E|\Q4\E	Die Körperschaft
Multinationale	E8123806	28	C	999	-	19.214	.{1,999}	Bezeichnung des Unternehmens, das den länderbezogenen Bericht des Konzerns übermitteln wird:
Multinationale	E8123807	29	H	-	-	19.215	\QAF\E|\QEG\E|\QAX\E|\QAL\E|\QDZ\E|\QVI\E|\QUM\E|\QAS\E|\QAD\E|\QAO\E|\QAI\E|\QAQ\E|\QAG\E|\QGQ\E|\QAR\E|\QAM\E|\QAW\E|\QAZ\E|\QET\E|\QAU\E|\QBS\E|\QBH\E|\QBD\E|\QBB\E|\QBY\E|\QBE\E|\QBZ\E|\QBJ\E|\QBM\E|\QBT\E|\QBO\E|\QBQ\E|\QBA\E|\QBW\E|\QBV\E|\QBR\E|\QVG\E|\QIO\E|\QBN\E|\QBG\E|\QBF\E|\QBI\E|\QCL\E|\QCN\E|\QCK\E|\QCR\E|\QCI\E|\QCW\E|\QDK\E|\QDE\E|\QDM\E|\QDO\E|\QDJ\E|\QEC\E|\QSV\E|\QER\E|\QEE\E|\QFK\E|\QFO\E|\QFJ\E|\QFI\E|\QFR\E|\QTF\E|\QGF\E|\QPF\E|\QGA\E|\QGM\E|\QGE\E|\QGH\E|\QGI\E|\QGD\E|\QGR\E|\QGL\E|\QGP\E|\QGU\E|\QGT\E|\QGG\E|\QGN\E|\QGW\E|\QGY\E|\QHT\E|\QHM\E|\QVA\E|\QHN\E|\QHK\E|\QIN\E|\QID\E|\QIM\E|\QIQ\E|\QIR\E|\QIE\E|\QIS\E|\QIL\E|\QIT\E|\QJM\E|\QJP\E|\QYE\E|\QJE\E|\QJO\E|\QKY\E|\QKH\E|\QCM\E|\QCA\E|\QCV\E|\QKZ\E|\QQA\E|\QKE\E|\QKG\E|\QKI\E|\QCC\E|\QCO\E|\QKM\E|\QCD\E|\QCG\E|\QSZ\E|\QKP\E|\QKR\E|\QKO\E|\QHR\E|\QCU\E|\QKW\E|\QLA\E|\QLS\E|\QLV\E|\QLB\E|\QLR\E|\QLY\E|\QLI\E|\QLT\E|\QLU\E|\QMO\E|\QMG\E|\QMW\E|\QMY\E|\QMV\E|\QML\E|\QMT\E|\QMP\E|\QMA\E|\QMH\E|\QMQ\E|\QMR\E|\QMU\E|\QYT\E|\QMX\E|\QFM\E|\QMD\E|\QMC\E|\QMN\E|\QME\E|\QMS\E|\QMZ\E|\QMM\E|\QNA\E|\QNR\E|\QNP\E|\QNC\E|\QNZ\E|\QNI\E|\QNL\E|\QNE\E|\QNG\E|\QNU\E|\QMK\E|\QNF\E|\QNO\E|\QOM\E|\QAT\E|\QPK\E|\QPS\E|\QPW\E|\QPA\E|\QPG\E|\QPY\E|\QPE\E|\QPH\E|\QPN\E|\QPL\E|\QPT\E|\QPR\E|\QRE\E|\QRW\E|\QRO\E|\QRU\E|\QSB\E|\QZM\E|\QWS\E|\QSM\E|\QST\E|\QSA\E|\QSE\E|\QCH\E|\QSN\E|\QRS\E|\QSC\E|\QSL\E|\QZW\E|\QSG\E|\QSX\E|\QSK\E|\QSI\E|\QSO\E|\QES\E|\QLK\E|\QBL\E|\QSH\E|\QKN\E|\QLC\E|\QMF\E|\QPM\E|\QVC\E|\QZA\E|\QSD\E|\QGS\E|\QSS\E|\QSR\E|\QSJ\E|\QSY\E|\QTJ\E|\QTW\E|\QTZ\E|\QTH\E|\QTL\E|\QTG\E|\QTK\E|\QTO\E|\QTT\E|\QTD\E|\QCZ\E|\QTN\E|\QTR\E|\QTM\E|\QTC\E|\QTV\E|\QUG\E|\QUA\E|\QHU\E|\QUY\E|\QUZ\E|\QVU\E|\QVE\E|\QAE\E|\QGB\E|\QUS\E|\QVN\E|\QWF\E|\QCX\E|\QEH\E|\QCF\E|\QCY\E	Länderschlüssel der Finanzbehörde, an die der länderbezogene Bericht des Konzerns übermittelt wird:
Vergutung/Empfanger	E8123901	30	C	999	-	-	.{1,999}	Vor- und Nachname
Vergutung/Empfanger	E8123902	30a	C	999	-	-	.{1,999}	Straße und Hausnummer
Vergutung/Empfanger	E8123903	30b	C	999	-	-	.{1,999}	Postleitzahl und Ort
Vergutung/Empfanger	E8123907	30c	C	40	-	-	.{1,40}	Weitere Adressangaben
Vergutung/Empfanger	E8123908	30d	C	50	-	-	.{1,50}	Staat
Vergutung/Empfanger	E8123310	30e	C	999	-	-	.{1,999}	Ausländisches Identifikationsmerkmal
Vergutung/Empfanger	E8123904	30f	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Geleistete Vergütung
Vergutung/Empfanger	E8123905	30g	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Einbehaltener und abgeführter Steuerabzug
Vergutung/Empfanger	E8123906	30h	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Einbehaltener und abgeführter Solidaritätszuschlag auf den Steuerabzug
Vergutung/Empfanger	E8123909	31	H	-	-	-	\Q1\E|\Q2\E|\Q3\E	Der Steuerabzug wurde aus folgenden Gründen nicht oder nicht in voller Höhe vorgenommen, da auf die Vergütung folgende Befreiungsvorschrift anzuwenden ist:
Vergutung/Empfanger	E8123910	32	C	999	-	-	.{1,999}	Bezeichnung der Verwertungsgesellschaft nach § 73f EStDV, an die die Vergütung geleistet wurde
Vergutung/Empfanger/P50c	E8124401	35	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	In den Fällen des § 50c EStG: auf Grund der Bescheinigung des Bundeszentralamts für Steuern vom
Vergutung/Empfanger/P50c	E8124402	35a	C	999	-	-	.{1,999}	Aktenzeichen der Bescheinigung des Bundeszentralamts für Steuern für den Steuerabzug
Vergutung/Anmeldung	E8124504	37	A	-	-	-	91160[0-9]{8}	Steuernummer beim Bundeszentralamt für Steuern
Bauleistung	E8124002	40a	J	-	-	19.243	1	Es liegt anrechenbare Bauabzugsteuer vor.
FZul	E8124101	41	J	-	-	19.241	1	Für die Körperschaft wurde ein Antrag auf Festsetzung einer Forschungszulage gestellt. Es wird beantragt, die Festsetzung der Körperschaftsteuer bis zur Festsetzung der Forschungszulage zurückzustellen.
FZul	E8124204	42	J	-	-	19.242	1	Für die nachfolgend aufgeführten Personengesellschaften besteht ein Anspruch auf Festsetzung oder Feststellung einer Forschungszulage. Es wird beantragt, die Festsetzung der Körperschaftsteuer bis zur gesonderten und einheitlichen Feststellung nach § 10 Absatz 2 Satz 2 FZulG zurückzustellen.
FZul/Einzel	E8124304	43	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer der Personengesellschaft
FZul/Einzel	E8124305	43	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer der Personengesellschaft
FZul/Einzel	E8124403	44	C	999	-	-	.{1,999}	Name der Personengesellschaft
"""

# The JD, sheet „KSt1F - Felder“.
_KST1F_2025 = r"""
Allgemein	E8200905	1	D	-	-	48.230	\d\d\.\d\d\.\d\d\d\d	Datum des Eintritts in die unbeschränkte Steuerpflicht im laufenden Wirtschaftsjahr
Allgemein	E8200101	2	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Wirtschaftsjahr vom
Allgemein	E8200102	2	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Wirtschaftsjahr bis
Leistungen/Einzel	E8122020	3	H	-	-	-	\Q1\E|\Q2\E|\Q3\E|\Q4\E|\Q5\E	Art der Leistung
Leistungen/Einzel	E8122021	4	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Datum des Gewinnverteilungsbeschlusses
Leistungen/Einzel	E8122022	4	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Datum des Abflusses
Leistungen/Einzel	E8122023	5	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bruttobetrag der Leistung
Leistungen/Einzel	E8122024	6	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bescheinigte Minderung des Einlagekontos
Leistungen/Gesamt	E8121406	7	U	-	-	19.250	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Summe der im Wirtschaftsjahr erbrachten Gewinnausschüttungen und sonstigen Leistungen (zum Beispiel Gewinnausschüttungen, die auf einem den gesellschaftsrechtlichen Vorschriften entsprechenden Gewinnverteilungsbeschluss beruhen; verdeckte Gewinnausschüttungen; Abschlagszahlungen auf das Liquidationsergebnis, soweit diese nicht als Nennkapitalrückzahlung nach § 28 Absatz 2 KStG zu beurteilen sind; Leistungen nach § 20 Absatz 1 Nummer 9 und 10 Buchstabe a EStG; bei Organgesellschaften: einschließlich geleisteter Ausgleichszahlungen und verdeckter Gewinnausschüttungen an außenstehende Anteilseigner; ohne Betrag laut Zeile 8)
Leistungen/Gesamt	E8121502	8	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mehrabführungen, die ihre Ursache in vororganschaftlicher Zeit haben (§ 14 Absatz 3 Satz 1 KStG, Betrag laut Zeile 22)
Leistungen/Gesamt	E8121503	9	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mehrabführungen, die ihre Ursache in vororganschaftlicher Zeit haben und bei der Körperschaft zu berücksichtigen sind, obwohl sie nicht Organträger der Organgesellschaft ist (vermittelnde Körperschaft) (Betrag laut Zeile 292 der Anlage GK)
Leistungen/Gesamt	E8200401	10	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bescheinigte Minderung des steuerlichen Einlagekontos zu den Zeilen 8 und 9
Leistungen/Gesamt	E8200502	11	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Im Wirtschaftsjahr erbrachte Leistungen ohne Leistungen aus der Rückzahlung von Nennkapital nach § 28 Absatz 2 KStG (Summe der Beträge laut Zeilen 7 bis 9) (Übertrag nach Zeile 47)
Leistungen/Gesamt	E8122003	12	U	-	-	19.185	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Summe der bescheinigten Minderung des steuerlichen Einlagekontos zu den in Zeilen 7, 8 und 9 enthaltenen Beträgen
Leistungen/Gesamt	E8122011	13	J	-	-	19.285	1	Bei mehr als einer Gewinnausschüttung/Leistung: Es wurde mindestens eine Bescheinigung über die Minderung des steuerlichen Einlagekontos ausgestellt
Leistungen/Gesamt	E8200701	14	U	-	-	19.284	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Im Falle einer Liquidation: Bescheinigte Minderung(en) des steuerlichen Einlagekontos für die Schlussauskehrung, soweit nicht Nennkapital ausgekehrt wird
Leistungen/Gesamt	E8122013	15	J	-	-	19.286	1	Kapitalertragsteuer wurde durch die Körperschaft nicht angemeldet, weil die Voraussetzungen des § 43 Absatz 1 Satz 1 Nummer 1a EStG (Sammelverwahrung oder Sonderverwahrung) vorliegen und damit die auszahlende Stelle die Kapitalertragsteuer anzumelden hat
Leistungen/Gesamt	E8240904	16	J	-	-	19.282	1	Eine der Leistungen laut Zeile 7 oder die Auszahlung des Nennkapitals aufgrund einer Kapitalherabsetzung laut Zeile 76 ist nicht dem Beteiligungsverhältnis entsprechend (disquotal) erfolgt (BMF-Schreiben vom 04.09.2024, BStBl I 2024, 1246)
Gewinn	E8201001	17	N	-	-	48.116	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Eigenkapital laut Steuerbilanz
Gewinn	E8201101	18	U	-	-	48.114	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nennkapital
Gewinn	E8201201	19	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Positiver Bestand des steuerlichen Einlagekontos
Gewinn	E8201301	20	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausschüttbarer Gewinn (§ 27 Absatz 1 Satz 5 KStG; wenn negativ, dann "0" eintragen)
MMA	E8205301	21	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Jahresüberschuss/-fehlbetrag laut Handels- oder Steuerbilanz (Betrag laut Zeile 11 der Anlage GK)
MMA	E8162901	22	U	-	-	17.173	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mehrabführungen, die ihre Ursache in vororganschaftlicher Zeit haben nach § 14 Absatz 3 Satz 1 KStG
MMA	E8163001	23	U	-	-	17.183	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Minderabführungen, die ihre Ursache in vororganschaftlicher Zeit haben nach § 14 Absatz 3 Satz 2 KStG
MMA	E8205601	24	U	-	-	48.272	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verrechenbare Verluste nach § 15a EStG, durch die keine Mehrabführung entsteht
MMA	E8205701	25	U	-	-	48.273	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verrechnung mit verrechenbaren Verlusten nach § 15a EStG, durch die keine Mehrabführung entstanden ist
MMA	E8205801	26	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Einlagen der Gesellschafter (§ 8 Absatz 3 Satz 3 KStG), die erfolgswirksam gebucht und bis zum Ende des Wirtschaftsjahres geleistet wurden (Betrag laut Zeile 93 der Anlage GK)
MMA	E8205802	27	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Einlagen der Gesellschafter (§ 8 Absatz 3 Satz 3 KStG), die erfolgswirksam gebucht aber nicht bis zum Ende des Wirtschaftsjahres geleistet wurden (Betrag laut Zeile 94 der Anlage GK)
MMA	E8241711	29	N	-	-	48.122	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Sonstige Korrekturen (laut gesonderter Erläuterung)
MMA	E8205902	30	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
MMA	E8162105	31	U	-	-	17.273	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mehrabführungen, die ihre Ursache in organschaftlicher Zeit haben nach § 14 Absatz 4 Satz 2 KStG
MMA	E8162106	32	U	-	-	17.274	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Minderabführungen, die ihre Ursache in organschaftlicher Zeit haben nach § 14 Absatz 4 Satz 1 KStG
ELK/Tabelle/Anfang	E8240102	40	U	-	-	48.217	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bei Eintritt in die unbeschränkte Steuerpflicht: Zum Zeitpunkt des Eintritts in die unbeschränkte Steuerpflicht vorhandener Bestand der nicht in das Nennkapital geleisteten Einlagen (§ 27 Absatz 2 Satz 3 KStG)
ELK/Tabelle/Anfang	E8240104	41	U	-	-	48.235	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bei Eintritt in die unbeschränkte Steuerpflicht: Zum Zeitpunkt des Eintritts in die unbeschränkte Steuerpflicht vorhandener Bestand des Sonderausweises nach § 28 Absatz 1 Satz 3 KStG
ELK/Tabelle/Anfang	E8240103	42	N	-	-	48.117	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Bestand nach § 27 Absatz 2 Satz 1 KStG zum Schluss des vorangegangenen Wirtschaftsjahres
ELK/Tabelle/Anfang	E8240201	43	N	-	-	48.135	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Bestand nach § 28 Absatz 1 Satz 3 KStG zum Schluss des vorangegangenen Wirtschaftsjahres
ELK/Tabelle/Org_Mehr	E8241715	44	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mehrabführungen, die ihre Ursache in organschaftlicher Zeit haben nach § 14 Absatz 4 Satz 2 KStG (Betrag laut Zeile 31)
ELK/Tabelle/Org_Mehr	E8241716	45	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Mehrabführungen, die ihre Ursache in organschaftlicher Zeit haben und bei der Körperschaft zu berücksichtigen sind, obwohl sie nicht Organträger der Organgesellschaft ist (vermittelnde Körperschaft) (Betrag laut Zeile 295 der Anlage GK)
ELK/Tabelle/Verrechnung	E8241717	46	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/Verrechnung/Kein_EeA	E8240302	47	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Im Wirtschaftsjahr erbrachte Leistungen ohne Leistungen aus der Rückzahlung von Nennkapital nach § 28 Absatz 2 KStG (Betrag laut Zeile 11)
ELK/Tabelle/Verrechnung/Kein_EeA	E8240401	48	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausschüttbarer Gewinn (§ 27 Absatz 1 Satz 5 KStG) - Betrag laut Zeile 20
ELK/Tabelle/Verrechnung/Kein_EeA	E8240501	49	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Summe
ELK/Tabelle/Verrechnung/Kein_EeA	E8242201	50	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Abzug vom steuerlichen Einlagekonto, wenn nur eine Leistung vorliegt oder keine Minderung des steuerlichen Einlagekontos bescheinigt wurde: Betrag laut Zeile 12, höchstens der kleinste der positiven Beträge laut Zeilen 46 und 49
ELK/Tabelle/Verrechnung/Kein_EeA	E8242202	51	U	-	-	48.285	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Abzug vom steuerlichen Einlagekonto, wenn mehrere Leistungen erbracht wurden und die Minderung des steuerlichen Einlagekontos bescheinigt wurde
ELK/Tabelle/Verrechnung/Nur_EeA	E8240303	52	U	-	-	48.250	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Im Wirtschaftsjahr geleisteter Teil des Kaufpreises, der über den Nennbetrag der erworbenen Anteile hinausgeht
ELK/Tabelle/Verrechnung/Nur_EeA	E8242204	53	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Abzug vom steuerlichen Einlagekonto: Betrag laut Zeile 52 abzüglich Betrag laut Zeile 20, wenn Differenz positiv; höchstens positiver Betrag laut Zeile 46
ELK/Tabelle/Verrechnung/EeA_Leistungen	E8242205	54	U	-	-	48.258	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Abzug vom steuerlichen Einlagekonto
ELK/Tabelle/Verrechnung/Abspaltung	E8240602	55	N	-	-	48.225	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Leistungen, die das steuerliche Einlagekonto erst nach dem steuerlichen Übertragungsstichtag mindern (gegebenenfalls anteiliger Betrag der Beträge laut Zeilen 50, 51 oder 54)
ELK/Tabelle/Herabsetzung	E8240801	56	U	-	-	48.134	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Betrag der Herabsetzung des Nennkapitals (ohne fiktive Herabsetzung bei Auflösung der Körperschaft nach § 28 Absatz 2 KStG)
ELK/Tabelle/Herabsetzung	E8241101	57	U	-	-	48.137	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausstehende Einlagen in das Nennkapital (nur, soweit die Einzahlungsverpflichtung des Anteilseigners entfällt)
ELK/Tabelle/Herabsetzung	E8241003	58	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 41 beziehungsweise Zeile 43 oder dem Betrag laut Zeile 56 abzüglich Betrag laut Zeile 57
ELK/Tabelle/Herabsetzung	E8241002	58	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 41 beziehungsweise Zeile 43 oder dem Betrag laut Zeile 56 abzüglich Betrag laut Zeile 57
ELK/Tabelle/Herabsetzung	E8241201	59	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/Herabsetzung	E8241202	59	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/Herabsetzung	E8242903	60	U	-	-	48.121	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Vom Betrag der Herabsetzung des Nennkapitals laut Zeile 56 sind zur Auszahlung vorgesehen
ELK/Tabelle/Auflosung	E8241206	70	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/Auflosung	E8242602	71	U	-	-	48.284	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Betrag des Nennkapitals zum Zeitpunkt der Auflösung der Körperschaft im Wirtschaftsjahr (zum Beispiel: Liquidationsbeschluss) nach § 28 Absatz 2 KStG
ELK/Tabelle/Auflosung	E8243002	72	U	-	-	48.287	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausstehende Einlagen in das Nennkapital
ELK/Tabelle/Auflosung	E8243003	73	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 70 oder dem Betrag laut Zeile 71 abzüglich Betrag laut Zeile 72
ELK/Tabelle/Auflosung	E8243004	73	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 70 oder dem Betrag laut Zeile 71 abzüglich Betrag laut Zeile 72
ELK/Tabelle/Auflosung	E8243005	74	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/Auflosung	E8243006	74	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/Ruckzahlung	E8243007	75	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/Ruckzahlung	E8240901	76	U	-	-	48.139	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Betrag der Rückzahlung des Nennkapitals, soweit hierauf § 28 Absatz 2 Satz 2 folgende KStG anzuwenden ist; bei Liquidation: ohne Beträge der Schlussauskehrung
ELK/Tabelle/Ruckzahlung	E8241205	77	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Betrag laut Zeile 76 soweit der Sonderausweis im Jahr der Kapitalherabsetzung oder der Auflösung der Körperschaft gemindert wurde = Bezüge des Anteilseigners nach § 20 Absatz 1 Nummer 2 EStG
ELK/Tabelle/Ruckzahlung	E8241419	78	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/Ruckzahlung	E8241304	79	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Abzug vom steuerlichen Einlagekonto (höchstens in Höhe des positiven Betrages laut Zeile 75)
ELK/Tabelle/Ruckzahlung	E8241305	79	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Abzug vom steuerlichen Einlagekonto (höchstens in Höhe des positiven Betrages laut Zeile 75)
ELK/Tabelle/Ruckzahlung	E8241303	80	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Übersteigender Betrag = Bezüge des Anteilseigners nach § 20 Absatz 1 Nummer 2 EStG
ELK/Tabelle/Erwerb_EigAnt	E8241403	80a	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/Erwerb_EigAnt/Uber	E8241404	81	U	-	-	48.251	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nennbetrag der erworbenen eigenen Anteile
ELK/Tabelle/Erwerb_EigAnt/Uber	E8241405	82	U	-	-	48.252	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausstehende Einlagen in das Nennkapital (nur, soweit die Einzahlungsverpflichtung entfällt)
ELK/Tabelle/Erwerb_EigAnt/Uber	E8241406	83	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/Erwerb_EigAnt/Uber	E8241407	83	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/Erwerb_EigAnt/Uber	E8241408	84	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/Erwerb_EigAnt/Uber	E8241409	85	U	-	-	48.253	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Im Wirtschaftsjahr geleisteter Kaufpreis der erworbenen eigenen Anteile (nur soweit auf die Rückzahlung des Nennkapitals entfallend; Betrag im Sinne der Zeile 83)
ELK/Tabelle/Erwerb_EigAnt/Uber	E8241410	86	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Abzug des Kaufpreises der erworbenen eigenen Anteile laut Zeile 85 vom steuerlichen Einlagekonto (höchstens in Höhe des positiven Betrages laut Zeile 84)
ELK/Tabelle/Erwerb_EigAnt/Unter	E8241411	87	U	-	-	48.254	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Differenzbetrag zwischen Nennbetrag und Kaufpreis
ELK/Tabelle/Erwerb_EigAnt/Unter	E8241414	88	U	-	-	48.255	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausstehende Einlagen in das Nennkapital (nur, soweit die Einzahlungsverpflichtung entfällt)
ELK/Tabelle/Erwerb_EigAnt/Unter	E8241412	89	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 80a oder dem Betrag laut Zeile 87 abzüglich Betrag laut Zeile 88
ELK/Tabelle/Erwerb_EigAnt/Unter	E8241413	89	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 80a oder dem Betrag laut Zeile 87 abzüglich Betrag laut Zeile 88
ELK/Tabelle/Erwerb_EigAnt/Unter	E8241415	90	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/Erwerb_EigAnt/Unter	E8241416	90	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/Einlagen	E8241501	91	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Einlagen, die in diesem Wirtschaftsjahr einkommenswirksam berücksichtigt worden sind, einschließlich entsprechender Erhöhungsbeträge nach § 23 Absatz 2 und 3 UmwStG (Betrag laut Zeile 93 der Anlage GK)
ELK/Tabelle/Einlagen	E8241502	92	G	-	-	-	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Nicht erfolgswirksam gebuchte Einlagen nach § 8 Absatz 3 Satz 4 KStG (Betrag laut Zeile 78 der Anlage GK)
ELK/Tabelle/Einlagen	E8241602	93	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Minderabführungen, die ihre Ursache in vororganschaftlicher Zeit haben (§ 14 Absatz 3 Satz 2 KStG; Betrag laut Zeile 23)
ELK/Tabelle/Einlagen	E8241603	94	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Minderabführungen, die ihre Ursache in vororganschaftlicher Zeit haben und bei der Körperschaft zu berücksichtigen sind, obwohl sie nicht Organträger der Organgesellschaft ist (vermittelnde Körperschaft) (Betrag laut Zeile 293 der Anlage GK)
ELK/Tabelle/Einlagen	E8241601	95	N	-	-	48.119	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Sonstige im Wirtschaftsjahr geleistete Einlagen (zum Beispiel Zugänge bei Einbringung nach §§ 20 oder 21 UmwStG in eine bestehende Körperschaft, Agio, Einlagen, die in einem früheren Wirtschaftsjahr einkommensmindernd berücksichtigt worden sind, Erhöhungsbeträge nach § 23 Absatz 2 und 3 UmwStG); ohne Beträge im Sinne der Zeilen 91 bis 93
ELK/Tabelle/Weiterverausserung	E8244103	96	U	-	-	48.256	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Differenzbetrag zwischen Nennbetrag und Veräußerungspreis
ELK/Tabelle/Org_Minder	E8246102	97	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Minderabführungen, die ihre Ursache in organschaftlicher Zeit haben nach § 14 Absatz 4 Satz 1 KStG (Betrag laut Zeile 32)
ELK/Tabelle/Org_Minder	E8246103	98	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Minderabführungen, die ihre Ursache in organschaftlicher Zeit haben und bei der Körperschaft zu berücksichtigen sind, obwohl sie nicht Organträger der Organgesellschaft ist (vermittelnde Körperschaft) (Betrag laut Zeile 294 der Anlage GK)
ELK/Tabelle/UN_UmwStG	E8242002	99	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/UN_UmwStG/Bet_UN	E8242301	100	N	-	-	48.111	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Steuerliches Einlagekonto des übertragenden Rechtsträgers, gegebenenfalls gekürzt im Verhältnis der unmittelbaren oder mittelbaren Beteiligung des übernehmenden Rechtsträgers an dem übertragenden Rechtsträger (§ 29 Absatz 2 Satz 2, § 29 Absatz 6 KStG)
ELK/Tabelle/UN_UmwStG/Bet_UT	E8242401	101	G	-	-	48.179	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Fiktive Herabsetzung des Nennkapitals (§ 29 Absatz 1 KStG): Betrag des Nennkapitals des übernehmenden Rechtsträgers am steuerlichen Übertragungsstichtag
ELK/Tabelle/UN_UmwStG/Bet_UT	E8242601	102	U	-	-	48.181	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausstehende Einlagen in das Nennkapital
ELK/Tabelle/UN_UmwStG/Bet_UT	E8242501	103	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 99 oder dem Betrag laut Zeile 101 abzüglich Betrag laut Zeile 102
ELK/Tabelle/UN_UmwStG/Bet_UT	E8242502	103	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 99 oder dem Betrag laut Zeile 101 abzüglich Betrag laut Zeile 102
ELK/Tabelle/UN_UmwStG/Bet_UT	E8242701	104	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/UN_UmwStG/Bet_UT	E8242702	104	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/UN_UmwStG/Bet_UT	E8242801	105	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/UN_UmwStG/Bet_UT	E8242901	106	N	-	-	48.112	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Minderung des steuerlichen Einlagekontos des übernehmenden Rechtsträgers im Verhältnis der Beteiligung des übertragenden Rechtsträgers am übernehmenden Rechtsträger (§ 29 Absatz 2 Satz 3 KStG)
ELK/Tabelle/UN_UmwStG/Bet_UT	E8243001	107	N	-	-	48.182	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hinzurechnung des steuerlichen Einlagekontos des übertragenden Rechtsträgers
ELK/Tabelle/UN_UmwStG/Bet_UT	E8243101	108	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/UN_UmwStG/Anpassung	E8243201	109	N	-	-	48.131	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Bei Beteiligung des übertragenden Rechtsträgers am übernehmenden Rechtsträger: Betrag des Nennkapitals; in allen anderen Fällen: Betrag der Erhöhung des Nennkapitals (nicht enthalten sein dürfen Beträge, die auf baren Zuzahlungen beziehungsweise Sacheinlagen beruhen)
ELK/Tabelle/UN_UmwStG/Anpassung	E8243301	110	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausstehende Einlagen in das Nennkapital (Betrag laut Zeile 102)
ELK/Tabelle/UN_UmwStG/Anpassung	E8243401	111	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/UN_UmwStG/Anpassung	E8243501	112	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hierfür Minderung eines positiven Bestandes des steuerlichen Einlagekontos bis zu dessen Verbrauch
ELK/Tabelle/UN_UmwStG/Anpassung	E8243502	112	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hierfür Minderung eines positiven Bestandes des steuerlichen Einlagekontos bis zu dessen Verbrauch
ELK/Tabelle/UN_UmwStG/Anpassung	E8243601	113	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibender Betrag: Nennkapitalerhöhung aus sonstigen Rücklagen
ELK/Tabelle/UN_UmwStG/Anpassung	E8243602	113	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibender Betrag: Nennkapitalerhöhung aus sonstigen Rücklagen
ELK/Tabelle/UN_UmwStG/Anpassung	E8243603	114	N	-	-	48.241	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Bei mehreren Übernahmen: Beträge im Sinne der Zeilen 112 und 113 laut gesonderter Ermittlung jeweils für jede Übernahme entsprechend der Zeilen 100 bis 111
ELK/Tabelle/UN_UmwStG/Anpassung	E8243604	114	N	-	-	48.242	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Bei mehreren Übernahmen: Beträge im Sinne der Zeilen 112 und 113 laut gesonderter Ermittlung jeweils für jede Übernahme entsprechend der Zeilen 100 bis 111
ELK/Tabelle/Erhohung_NK	E8243701	115	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/Erhohung_NK	E8243801	116	U	-	-	48.115	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Betrag der Erhöhung des Nennkapitals
ELK/Tabelle/Erhohung_NK	E8243802	117	U	-	-	48.215	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bei Abbruch der Liquidation (Fortsetzungsbeschluss): Betrag des Nennkapitals gekürzt um ausstehende Einlagen
ELK/Tabelle/Erhohung_NK	E8243901	118	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hierfür Minderung eines positiven Bestandes des steuerlichen Einlagekontos bis zu dessen Verbrauch
ELK/Tabelle/Erhohung_NK	E8243902	118	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hierfür Minderung eines positiven Bestandes des steuerlichen Einlagekontos bis zu dessen Verbrauch
ELK/Tabelle/Erhohung_NK	E8244001	119	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibender Betrag: Nennkapitalerhöhung aus sonstigen Rücklagen
ELK/Tabelle/Erhohung_NK	E8244002	119	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibender Betrag: Nennkapitalerhöhung aus sonstigen Rücklagen
ELK/Tabelle/EigAnt_Verkauf	E8244104	120	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/EigAnt_Verkauf	E8244106	121	U	-	-	48.257	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Bei Weiterveräußerung: Differenzbetrag zwischen Nennbetrag und Veräußerungspreis; Bei Einziehung ohne Kapitalherabsetzung: Nennbetrag der eingezogenen eigenen Anteile
ELK/Tabelle/EigAnt_Verkauf	E8244107	122	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Hierfür Minderung eines positiven Bestandes des steuerlichen Einlagekontos bis zu dessen Verbrauch
ELK/Tabelle/EigAnt_Verkauf	E8244108	122	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Hierfür Minderung eines positiven Bestandes des steuerlichen Einlagekontos bis zu dessen Verbrauch
ELK/Tabelle/EigAnt_Verkauf	E8244109	123	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Nennkapitalerhöhung aus sonstigen Rücklagen
ELK/Tabelle/EigAnt_Verkauf	E8244110	123	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Nennkapitalerhöhung aus sonstigen Rücklagen
ELK/Tabelle/UT	E8244112	124	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/UT/Abspaltung_P29Abs1	E8244201	125	G	-	-	48.136	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Betrag des Nennkapitals am steuerlichen Übertragungsstichtag
ELK/Tabelle/UT/Abspaltung_P29Abs1	E8244401	126	U	-	-	48.132	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausstehende Einlagen in das Nennkapital
ELK/Tabelle/UT/Abspaltung_P29Abs1	E8244301	127	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 124 oder dem Betrag laut Zeile 125 abzüglich Betrag laut Zeile 126
ELK/Tabelle/UT/Abspaltung_P29Abs1	E8244302	127	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 124 oder dem Betrag laut Zeile 125 abzüglich Betrag laut Zeile 126
ELK/Tabelle/UT/Abspaltung_P29Abs1	E8244501	128	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/UT/Abspaltung_P29Abs1	E8244502	128	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/UT/Abspaltung_P29Abs1	E8244601	129	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/UT/Abspaltung_P29Abs3	E8244602	130	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Betrag laut Zeile 129 Spalte 3
ELK/Tabelle/UT/Abspaltung_P29Abs3	E8244603	131	N	-	-	48.226	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Korrektur um in den Zeilen 56 bis 119 enthaltene Zu- und Abgänge aufgrund von Sachverhalten, die nach dem steuerlichen Übertragungsstichtag verwirklicht wurden (laut gesonderter Ermittlung)
ELK/Tabelle/UT/Abspaltung_P29Abs3	E8244604	132	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/UT/Abspaltung_P29Abs3	E8244703	133	U	-	-	48.341	^(?=.{1,15}$)(?!0\d)\d{1,15}$	Der für die Abspaltung maßgebende Zähler nach § 29 Absatz 3 KStG
ELK/Tabelle/UT/Abspaltung_P29Abs3	E8244704	134	G	-	-	48.342	^(?=.{1,15}$)(?=.*[1-9].*)(?!0\d)\d{1,15}$	Der für die Abspaltung maßgebende Nenner nach § 29 Absatz 3 KStG
ELK/Tabelle/UT/Abspaltung_P29Abs3	E8244702	135	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verringerung des steuerlichen Einlagekontos nach § 29 Absatz 3 KStG (Betrag laut Zeile 132 multipliziert mit dem Betrag laut Zeile 133 dividiert durch den Betrag laut Zeile 134)
ELK/Tabelle/UT/Abspaltung_P29Abs3	E8244801	136	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/UT/Abspaltung_P29Abs4	E8244901	137	G	-	-	48.118	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Höhe des Nennkapitals nach der Übertragung
ELK/Tabelle/UT/Abspaltung_P29Abs4	E8245001	138	U	-	-	48.180	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausstehende Einlagen in das Nennkapital
ELK/Tabelle/UT/Abspaltung_P29Abs4	E8245101	139	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/UT/Abspaltung_P29Abs4	E8245201	140	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hierfür Minderung eines positiven Bestandes des steuerlichen Einlagekontos bis zu dessen Verbrauch
ELK/Tabelle/UT/Abspaltung_P29Abs4	E8245202	140	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Hierfür Minderung eines positiven Bestandes des steuerlichen Einlagekontos bis zu dessen Verbrauch
ELK/Tabelle/UT/Abspaltung_P29Abs4	E8245301	141	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibender Betrag: Nennkapitalerhöhung aus sonstigen Rücklagen
ELK/Tabelle/UT/Abspaltung_P29Abs4	E8245302	141	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibender Betrag: Nennkapitalerhöhung aus sonstigen Rücklagen
ELK/Tabelle/UT/Abspaltung_P29Abs4	E8245303	142	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/UT/Abspaltung_P29Abs4	E8245304	142	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/UT/Abspaltung_P29Abs4	E8245403	143	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verringerung des steuerlichen Einlagekontos im Falle von Leistungen, die nicht bis zum steuerlichen Übertragungsstichtag erfolgt sind beziehungsweise als erfolgt gelten: - Betrag laut Zeile 55 höchstens Summe der Beträge laut Zeile 131 Vorspalte und Zeile 142 Spalte 3, wenn Summe positiv oder - insoweit nach § 27 Absatz 5 KStG zu berücksichtigender Betrag
ELK/Tabelle/Verschmelzung	E8245404	144	U	-	-	48.236	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Fiktive Herabsetzung des Nennkapitals (§ 29 Absatz 1 KStG): Betrag des Nennkapitals am steuerlichen Übertragungsstichtag
ELK/Tabelle/Verschmelzung	E8245407	145	U	-	-	48.232	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Ausstehende Einlagen in das Nennkapital
ELK/Tabelle/Verschmelzung	E8245405	146	G	-	-	-	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 142, Spalte 4 oder dem Betrag laut Zeile 144 abzüglich Betrag laut Zeile 145
ELK/Tabelle/Verschmelzung	E8245406	146	G	-	-	-	^(?=.{1,12}$)(?=.*[1-9].*)(?!0\d)\d{1,12}$	Verringerung des Sonderausweises bis zu dessen Verbrauch; niedrigerer Betrag laut Zeile 142, Spalte 4 oder dem Betrag laut Zeile 144 abzüglich Betrag laut Zeile 145
ELK/Tabelle/Verschmelzung	E8245408	147	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/Verschmelzung	E8245409	147	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag: Gutschrift beim steuerlichen Einlagekonto
ELK/Tabelle/Verschmelzung	E8245401	148	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/P35	E8241901	149	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zugang nach § 35 KStG aufgrund eines Verlustabzugs
ELK/Tabelle/AusgleichSoAu	E8245410	150	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/AusgleichSoAu	E8245411	150	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zwischensumme
ELK/Tabelle/AusgleichSoAu	E8245501	151	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Abzug des Betrages laut Zeile 150 Spalte 4 - maximal in Höhe des positiven Betrages laut Zeile 150 Spalte 3 - jeweils in Spalten 3 und 4
ELK/Tabelle/AusgleichSoAu	E8245502	151	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Abzug des Betrages laut Zeile 150 Spalte 4 - maximal in Höhe des positiven Betrages laut Zeile 150 Spalte 3 - jeweils in Spalten 3 und 4
ELK/Tabelle/Ende	E8245601	152	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Endbestände zum Schluss des Wirtschaftsjahres
ELK/Tabelle/Ende	E8245602	152	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Endbestände zum Schluss des Wirtschaftsjahres
ELK/Tabelle/Liquidation	E8211901	160	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Vom Betrag laut Zeile 152 Spalte 3 sind aus einer erfolgten Nennkapitalherabsetzung oder Auflösung der Körperschaft noch zur Auszahlung vorgesehen
ELK/Tabelle/Liquidation	E8212001	161	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Verbleibendes Einlagekonto
ELK/Tabelle/Liquidation	E8245901	162	U	-	-	48.183	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Auszukehrendes Eigenkapital laut Liquidationsschlussbilanz (Schlussauskehrung)
ELK/Tabelle/Liquidation	E8241212	163	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Teil der Schlussauskehrung, in deren Höhe der Sonderausweis bei Auflösung der Körperschaft und gegebenenfalls einer Nennkapitalherabsetzung gemindert wurde = Bezüge des Anteilseigners nach § 20 Absatz 1 Nummer 2 EStG
ELK/Tabelle/Liquidation	E8212201	164	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Positiver Bestand des steuerlichen Einlagekontos oder nach § 27 Absatz 5 KStG zu berücksichtigender Betrag (niedrigerer Betrag der Zeilen 14, 161 und 162 abzüglich Zeile 163; wenn in Zeile 14 kein Betrag eingetragen, hier "0" eintragen)
ELK/Tabelle/Liquidation	E8212301	165	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Nennkapitalrückzahlung (Betrag laut Zeile 160, höchstens Betrag laut Zeile 162 abzüglich Summe der Beträge laut Zeilen 163 und 164)
ELK/Tabelle/Liquidation	E8212401	166	U	-	-	-	^(?=.{1,12}$)(?!0\d)\d{1,12}$	Verbleibender Betrag = Bezüge des Anteilseigners nach § 20 Absatz 1 Nummer 2 EStG
Zusatz_Abspaltung	E8246803	167	N	-	-	48.355	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zum steuerlichen Übertragungsstichtag ausgewiesenes Eigenkapital laut steuerlicher Schlussbilanz des übertragenden Rechtsträgers für das auf Personengesellschaften übergehende Vermögen
Zusatz_Abspaltung	E8246903	169	N	-	-	48.356	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Steuerliches Einlagekonto zum Übertragungsstichtag, soweit das Vermögen auf eine Personengesellschaft übergeht
Zusatz_Abspaltung	E8247101	172	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Bezüge des Anteilseigners nach § 20 Absatz 1 Nummer 1 EStG
Zusatz_Formwechsel	E8247103	173	N	-	-	48.357	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Zum steuerlichen Übertragungsstichtag ausgewiesenes Eigenkapital laut steuerlicher Schlussbilanz des übertragenden Rechtsträgers
Zusatz_Formwechsel	E8246902	174	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Steuerliches Einlagekonto zum Übertragungsstichtag (Betrag laut Zeile 148 Spalte 3)
Zusatz_Formwechsel	E8247102	178	N	-	-	-	^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$	Bezüge des Anteilseigners nach § 20 Absatz 1 Nummer 1 EStG
Einlagen/Einlage	E8241510	200	C	999	-	-	.{1,999}	Name des leistenden Anteilseigners
Einlagen/Einlage	E8241511	201	A	-	-	-	([0-9]{4})0[0-9]{8}	Steuernummer
Einlagen/Einlage	E8241512	202	I	-	-	-	[0-9]{11}	Identifikationsnummer
Einlagen/Einlage	E8241513	203	C	11	-	-	DE[0-9]{9}	Wirtschafts-Identifikationsnummer
Einlagen/Einlage	E8241514	204	D	-	-	-	\d\d\.\d\d\.\d\d\d\d	Zeitpunkt der Leistung der Einlage
Einlagen/Einlage	E8241515	205	H	-	-	-	\Q1\E|\Q2\E	Art der Einlage
Einlagen/Einlage	E8241516	206	C	999	-	-	.{1,999}	Bei Sacheinlagen: Bezeichnung der Einlage
"""

# The rules of the JD that Steuerbote checks (steuerbote.eric.simulation.kst), from the sheets „<Vordruck> - Regeln“,
# without their Fehler- /Hinweistext (module docstring).
_RULES_2025 = (
	Rule(
		"8906010",
		"Regel_160100_GK_allg",
		"",
		(
			"/KSt1/Steuerbefreiung/Umfang/E8001506",
			"/KSt1/Steuerpflicht/E8000603",
			"/KSt1/Steuerpflicht/E8000702",
			"/KSt1/Steuerpflicht/E8000803",
			"/KSt1/Steuerpflicht/Rechtsform/E8001105",
			"/KSt1/Weiteres/E8001702",
			"/ZVE/ZVE/Rundfunk/E8025903",
		),
	),
	Rule(
		"8900744",
		"Regel_170034_ZVE_allgAngaben",
		"",
		("/KSt1/Steuerbefreiung/Umfang/E8001506", "/ZVE/SdE/Gewerbe/Laufend/E8004904"),
	),
	Rule(
		"8912208",
		"Regel_170308_WA_Anteilseigner",
		"",
		("/KSt1/Steuerpflicht/Rechtsform/E8001105",),
	),
	Rule(
		"8912209",
		"Regel_170309_WA_Anteilseigner",
		"",
		("/KSt1/Steuerpflicht/Rechtsform/E8001105", "/WA/AE/E8122801"),
	),
	Rule(
		"8931022",
		"KSt1_19_002",
		"",
		(
			"/KSt1/Steuerpflicht/E8000603",
			"/KSt1/Steuerpflicht/E8000702",
			"/KSt1/Steuerpflicht/E8000803",
			"/KSt1/Steuerpflicht/Rechtsform/E8001105",
			"/KSt1/Weiteres/E8001702",
		),
	),
	Rule(
		"8900709",
		"Regel_170009_KSt1_allgAngaben",
		"",
		("/KSt1/E8000016",),
	),
	Rule(
		"8912151",
		"Regel_121204_WA_Anteilseigner",
		"",
		("/KSt1/AE/Einzel/E8122101", "/KSt1/Steuerpflicht/Rechtsform/E8001105"),
	),
	Rule(
		"8912163",
		"Regel_121216_WA_Anteilseigner_30",
		"",
		(
			"/KSt1/AE/Gesamt/E8122601",
			"/KSt1/Steuerbefreiung/Umfang/E8001506",
			"/KSt1/Steuerpflicht/Rechtsform/E8001105",
		),
	),
	Rule(
		"8900368",
		"Regel_130002_1A_allgAngaben",
		"",
		("/KSt1/Steuerbefreiung/Bezeichnung/E8001505", "/KSt1/Weiteres/E8001007"),
	),
	Rule(
		"8900070",
		"Regel_07114_1A_Einnahmen",
		"",
		("/GK/Bilanz/E8002001", "/GK/Bilanz/E8002004"),
	),
	Rule(
		"8906061",
		"Regel_160151_GK_Zinsschranke",
		"",
		("/GK/Einkunfte/E8109901",),
	),
	Rule(
		"8900548",
		"Regel_160004_1A_Gewerbe",
		"",
		("/ZVE/SdE/Gewerbe/Laufend/E8004904",),
	),
	Rule(
		"8900100",
		"Regel_080114_1A_Summen",
		"",
		("/ZVE/Ber/E8007704", "/ZVE/SdE/SdE/E8005401", "/ZVE/ZVE/Rundfunk/E8025903"),
	),
	Rule(
		"8900818",
		"Regel_170108_ZVE_GdE",
		"",
		("/ZVE/Ber/E8007704", "/ZVE/GdE/GdE/E8006901", "/ZVE/ZVE/Rundfunk/E8025903"),
	),
	Rule(
		"8900836",
		"Regel_170126_ZVE_zvE",
		"",
		("/ZVE/Ber/E8007704", "/ZVE/ZVE/ZVE/E8007501"),
	),
	Rule(
		"8918391",
		"Regel_160231_Vl_Endbest",
		"",
		("/Verluste/Ende/E8009201",),
	),
	Rule(
		"8920227",
		"Regel_171052_KSt1F",
		"",
		(
			"/KSt1F/ELK/Tabelle/Anfang/E8240102",
			"/KSt1F/ELK/Tabelle/Anfang/E8240103",
			"/KSt1F/ELK/Tabelle/Ende/E8245601",
		),
	),
	Rule(
		"8924512",
		"Regel_156007_1F_Anfangsbestaende",
		"",
		(
			"/KSt1F/ELK/Tabelle/Anfang/E8240102",
			"/KSt1F/ELK/Tabelle/Anfang/E8240103",
			"/KSt1F/ELK/Tabelle/Anfang/E8240104",
			"/KSt1F/ELK/Tabelle/Anfang/E8240201",
		),
	),
	Rule(
		"8956060",
		"Regel_145660_B_Bezuege",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Einzel/E8560404",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Gesamt/E8560401",
		),
	),
	Rule(
		"8956070",
		"Regel_145670_B_Bezuege",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel/E8561211",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Gesamt/E8561212",
		),
	),
	Rule(
		"8956072",
		"Regel_145672_B_Bezuege",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel/E8561403",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Gesamt/E8561410",
		),
	),
	Rule(
		"8905507",
		"GK_22_007",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel/E8561210",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Gesamt/E8561220",
		),
	),
	Rule(
		"8905516",
		"GK_22_016",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Einzel/E8561408",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Gesamt/E8561411",
		),
	),
	Rule(
		"8906062",
		"Regel_160152_GK_Zinsschranke",
		"",
		(
			"/GK/ABil/AtypG/Gesamt/E8002106",
			"/GK/ABil/AtypG/Gesamt/E8002107",
			"/GK/ABil/E8003001",
			"/GK/ABil/E8003002",
			"/GK/ABil/E8003101",
			"/GK/ABil/E8003201",
			"/GK/ABil/Genuss/Gesamt/E8002709",
			"/GK/ABil/REIT/E8004004",
			"/GK/ABil/REIT/E8004005",
			"/GK/ABil/SiebenG/E8002602",
			"/GK/ABil/SiebenG/E8002603",
			"/GK/ABil/SiebenG/E8002604",
			"/GK/ABil/SiebenG/E8002605",
			"/GK/ABil/Termin/E8002104",
			"/GK/ABil/Termin/E8002105",
			"/GK/ABil/Tierzucht/E8002102",
			"/GK/ABil/Tierzucht/E8002103",
			"/GK/ABil/TypG/Gesamt/E8002108",
			"/GK/ABil/TypG/Gesamt/E8002109",
			"/GK/ABil/VGA/Gesamt/E8002701",
			"/GK/ABil/Weiteres0/E8002110",
			"/GK/ABil/Weiteres0/E8002111",
			"/GK/ABil/Weiteres2/E8002601",
			"/GK/ABil/Weiteres2/E8002702",
			"/GK/ABil/Weiteres2/E8002801",
			"/GK/ABil/Weiteres2/E8002902",
			"/GK/ABil/Weiteres2/E8003301",
			"/GK/ABil/Weiteres2/E8003401",
			"/GK/ABil/Weiteres2/E8003402",
			"/GK/ABil/Weiteres2/E8003601",
			"/GK/ABil/Weiteres2/E8003702",
			"/GK/ABil/Weiteres2/E8009702",
			"/GK/ABil/Weiteres2/E8100201",
			"/GK/ABil/Weiteres2/E8100301",
			"/GK/ABil/Weiteres2/E8100501",
			"/GK/ABil/Weiteres2/E8100601",
			"/GK/ABil/Weiteres2/E8100702",
			"/GK/ABil/Weiteres2/E8100801",
			"/GK/ABil/Weiteres2/E8100803",
			"/GK/ABil/Weiteres2/E8100804",
			"/GK/ABil/Weiteres2/E8100901",
			"/GK/ABil/Weiteres2/E8101001",
			"/GK/ABil/Weiteres2/E8101101",
			"/GK/ABil/Weiteres2/E8101201",
			"/GK/ABil/Weiteres2/E8101301",
			"/GK/ABil/Weiteres2/E8101302",
			"/GK/ABil/Weiteres2/E8101401",
			"/GK/ABil/Weiteres2/Sonstige/Gesamt/E8003701",
			"/GK/Ausland/Berichtigung/Gesamt/E8183001",
			"/GK/Ausland/DBA/Gesamt/E8181001",
			"/GK/Ausland/DBA/Gesamt/E8181101",
			"/GK/Beteiligung/Korrektur/E8562101",
			"/GK/Beteiligung/Korrektur/E8562201",
			"/GK/Beteiligung/Verkauf/Anderes_Jahr/Gesamt/E8004437",
			"/GK/Beteiligung/Verkauf/Lfd_Jahr/Gesamt/E8004441",
			"/GK/Bilanz/Altmaterial/E8001801",
			"/GK/Bilanz/Altmaterial/E8001802",
			"/GK/Bilanz/Altmaterial/E8001803",
			"/GK/Bilanz/Altmaterial/E8001804",
			"/GK/Bilanz/Altmaterial/E8001805",
			"/GK/Bilanz/Altmaterial/E8001806",
			"/GK/Bilanz/Altmaterial/E8001807",
			"/GK/Bilanz/Altmaterial/E8001808",
			"/GK/Bilanz/Altmaterial/E8001809",
			"/GK/Bilanz/Altmaterial/E8001903",
			"/GK/Bilanz/E8002001",
			"/GK/Bilanz/E8002004",
			"/GK/Bilanz/E8002006",
			"/GK/Bilanz/PG/Gesamt/E8002204",
			"/GK/Bilanz/PG/Gesamt/E8002207",
			"/GK/Bilanz/PG/Gesamt/E8002211",
			"/GK/Bilanz/PG/Gesamt/E8002215",
			"/GK/Bilanz/PG/Gesamt/E8002216",
			"/GK/Bilanz/Tonnage/E8002002",
			"/GK/Bilanz/Tonnage/E8002303",
			"/GK/Einkunfte/E8004906",
			"/GK/Einkunfte/E8109901",
			"/GK/Invest/Aktie/Hauptspalte/E8011302",
			"/GK/Invest/Aktie/Hauptspalte_2/E8011602",
			"/GK/Invest/Immo_Ausland/Hauptspalte/E8012802",
			"/GK/Invest/Immo_P2Abs9/Hauptspalte/E8012502",
			"/GK/Invest/Misch/Hauptspalte/E8011902",
			"/GK/Invest/Misch/Hauptspalte_2/E8012202",
			"/GK/Invest/Unterschiedsbetrag/E8012901",
			"/GK/Ni_ORG/Gesamt/E8017601",
			"/GK/Ni_ORG/Gesamt/E8017602",
			"/GK/Ni_ORG/Gesamt/E8017603",
			"/GK/Ni_ORG/Gesamt/E8017604",
			"/GK/Org_AP/Gesamt/Hauptspalte/E8562515",
			"/GK/Org_AP/Gesamt/Hauptspalte/E8562516",
			"/GK/Organschaft/Neutral_OG/E8162001",
			"/GK/Organschaft/Neutral_OG/E8162101",
			"/GK/Organschaft/Neutral_OG/E8162201",
			"/GK/Organschaft/Neutral_OG/E8162202",
			"/GK/Organschaft/Neutral_OG/E8162204",
			"/GK/Organschaft/Neutral_OT/E8160501",
			"/GK/Organschaft/Neutral_OT/E8160601",
			"/GK/Organschaft/Neutral_OT/E8160701",
			"/GK/Organschaft/Neutral_OT/E8160902",
			"/GK/Organschaft/Neutral_OT/E8160903",
			"/GK/Organschaft/Neutral_OT/E8160904",
			"/GK/Organschaft/Neutral_OT/E8160909",
			"/GK/Organschaft/Neutral_OT/E8160910",
			"/GK/Organschaft/Neutral_OT/E8160911",
			"/GK/Spezial_Invest/Hauptspalte/E8016107",
			"/GK/Spezial_Invest/Hauptspalte/E8016108",
			"/GK/Spezial_Invest/Hauptspalte/E8016109",
			"/GK/Spezial_Invest/TW/E8016201",
			"/GK/Spezial_Invest/TW/Hauptspalte_2/E8016302",
			"/GK/Spezial_Invest/TW/Hauptspalte_2/E8016303",
			"/GK/UmwStG/Anderes_Jahr/Gesamt/E8007302",
			"/GK/UmwStG/EGI/E8004002",
			"/GK/UmwStG/Lfd_Jahr/Gesamt/E8007408",
			"/GK/UmwStG/Verschmelzung_UN/Haupt/E8007017",
			"/GK/UmwStG/Verschmelzung_UN/Haupt/E8007019",
			"/GK/UmwStG/Verschmelzung_UN/Haupt/E8007025",
			"/GK/Zinsschranke/E8004902",
			"/GK/Zinsschranke/E8004903",
			"/GK/Zinsschranke/E8004905",
		),
	),
	Rule(
		"8956047",
		"Regel_145647_B_Sachverhalte",
		"",
		(
			"/GK/Beteiligung/Korrektur/E8562101",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Gesamt/E8561220",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Gesamt/E8561237",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Darlehen/E8561501",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/LV_KV/E8561601",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Gesamt/E8561411",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Gesamt/E8561412",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/NichtAbziehbare/E8561301",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Sonstige/E8561701",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Sonstige/E8561801",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Sonstige/E8561901",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Sonstige/E8562001",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Gesamt/E8560401",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Gesamt/E8560801",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Gesamt/E8561212",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Gesamt/E8561410",
			"/OG/Allgemein/OT/E8160202",
		),
	),
	Rule(
		"8956020",
		"Regel_145620_B_Bezuege",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Gesamt/E8560401",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Gesamt/E8560801",
			"/OG/Allgemein/OT/E8160202",
		),
	),
	Rule(
		"8956042",
		"Regel_145642_B_Sachverhalte",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Gesamt/E8561220",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Gesamt/E8561237",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/NichtAbziehbare/E8561301",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Gesamt/E8561212",
			"/OG/Allgemein/OT/E8160202",
		),
	),
	Rule(
		"8956007",
		"Regel_145607_B_Bezuege",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Einzel/E8560404",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Gesamt/E8560401",
		),
	),
	Rule(
		"8956040",
		"Regel_145640_B_Sachverhalte",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel/E8561211",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Gesamt/E8561212",
		),
	),
	Rule(
		"8956044",
		"Regel_145644_B_Sachverhalte",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Einzel/E8561403",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Verausserung/Gesamt/E8561410",
		),
	),
	Rule(
		"8905506",
		"GK_22_006",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Einzel/E8561210",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Aufholung/Gesamt/E8561220",
		),
	),
	Rule(
		"8905515",
		"GK_22_015",
		"",
		(
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Einzel/E8561408",
			"/GK/Beteiligung/Tabelle/P8b_Vergleichbar/Minderung/Gesamt/E8561411",
		),
	),
	Rule(
		"8900549",
		"Regel_160005_1A_Gewerbe",
		"",
		("/GK/Einkunfte/E8109901", "/GK/WJ", "/ZVE/SdE/Gewerbe/Laufend/E8004904"),
	),
	Rule(
		"8900207",
		"Regel_080151_1A_SdE",
		"",
		(
			"/KSt1/Steuerbefreiung/Umfang/E8001506",
			"/ZVE/SdE/AStG_ZwiG/E8023105",
			"/ZVE/SdE/AStG_ZwiG/E8023107",
			"/ZVE/SdE/Abzug/E8004201",
			"/ZVE/SdE/Abzug/E8004202",
			"/ZVE/SdE/Gewerbe/Laufend/E8004904",
			"/ZVE/SdE/Gewerbe/Laufend/E8005002",
			"/ZVE/SdE/Gewerbe/Laufend/E8022403",
			"/ZVE/SdE/Gewerbe/VG/E8020503",
			"/ZVE/SdE/Gewerbe/VG/E8020603",
			"/ZVE/SdE/Gewerbe/VG/E8020702",
			"/ZVE/SdE/Gewerbe/VG/E8020703",
			"/ZVE/SdE/Invest_Steuerabzug/E8021202",
			"/ZVE/SdE/Invest_Steuerbefreiung/E8022801",
			"/ZVE/SdE/KapESt/E8005301",
			"/ZVE/SdE/KapV/E8023701",
			"/ZVE/SdE/KapV/E8023702",
			"/ZVE/SdE/LuF/E8022101",
			"/ZVE/SdE/LuF/E8022102",
			"/ZVE/SdE/LuF/PG/Gesamt/E8022103",
			"/ZVE/SdE/Negativ/E8004301",
			"/ZVE/SdE/Negativ/E8004401",
			"/ZVE/SdE/P50a/P50aNR1/Gesamt/E8043701",
			"/ZVE/SdE/P50a/P50aNR2/Gesamt/E8043702",
			"/ZVE/SdE/SPIF/E8021201",
			"/ZVE/SdE/San_Ertrag/E8022901",
			"/ZVE/SdE/San_Ertrag/E8023001",
			"/ZVE/SdE/San_Ertrag/E8023101",
			"/ZVE/SdE/SdE/E8005401",
			"/ZVE/SdE/Selbstandig/Beteiligung_PG/Gesamt_PG/E8023303",
			"/ZVE/SdE/Selbstandig/Gesamt_Betrieb/E8023202",
			"/ZVE/SdE/Sonstige/Bezuge/E8024201",
			"/ZVE/SdE/Sonstige/Bezuge/E8024301",
			"/ZVE/SdE/Sonstige/Leistung/E8024601",
			"/ZVE/SdE/Sonstige/Leistung/E8024604",
			"/ZVE/SdE/Sonstige/Leistung/E8024605",
			"/ZVE/SdE/Sonstige/Leistung/E8024606",
			"/ZVE/SdE/Sonstige/Verausserung/E8024401",
			"/ZVE/SdE/Sonstige/Verausserung/E8024404",
			"/ZVE/SdE/Sonstige/Verausserung/E8024405",
			"/ZVE/SdE/Sonstige/Verausserung/E8024406",
			"/ZVE/SdE/VuV/E8024101",
			"/ZVE/ZVE/Rundfunk/E8025903",
		),
	),
	Rule(
		"8900413",
		"Regel_090125_1A_GdE",
		"",
		(
			"/KSt1/Steuerbefreiung/Umfang/E8001506",
			"/ZVE/GdE/Abspaltung/E8006402",
			"/ZVE/GdE/Einkommen_OG/E8006501",
			"/ZVE/GdE/Einkommen_OG/E8006601",
			"/ZVE/GdE/Einkommen_OT/E8006401",
			"/ZVE/GdE/GdE/E8006901",
			"/ZVE/GdE/Hinzurechnung/E8005701",
			"/ZVE/GdE/LuF/E8025101",
			"/ZVE/GdE/P2Abs4/Hauptspalte/E8006608",
			"/ZVE/GdE/P2Abs4_OHK/E8006609",
			"/ZVE/GdE/P2Abs5UmwStG/E8005702",
			"/ZVE/GdE/P8cKStG_Lfd/E8006301",
			"/ZVE/GdE/San_Lfd/E8003302",
			"/ZVE/GdE/San_Lfd/E8003303",
			"/ZVE/GdE/Zuwendung/E8005601",
			"/ZVE/SdE/SdE/E8005401",
			"/ZVE/ZVE/Rundfunk/E8025903",
		),
	),
	Rule(
		"8900431",
		"Regel_080143_1A_zvE",
		"",
		(
			"/ZVE/GdE/Abspaltung/E8006402",
			"/ZVE/GdE/Einkommen_OG/E8006501",
			"/ZVE/GdE/Einkommen_OG/E8006601",
			"/ZVE/GdE/Einkommen_OT/E8006401",
			"/ZVE/GdE/GdE/E8006801",
			"/ZVE/GdE/Hinzurechnung/E8005701",
			"/ZVE/GdE/LuF/E8025101",
			"/ZVE/GdE/P2Abs4/Hauptspalte/E8006608",
			"/ZVE/GdE/P2Abs4_OHK/E8006609",
			"/ZVE/GdE/P2Abs5UmwStG/E8005702",
			"/ZVE/GdE/P8cKStG_Lfd/E8006301",
			"/ZVE/GdE/San_Lfd/E8003302",
			"/ZVE/GdE/San_Lfd/E8003303",
			"/ZVE/GdE/Zuwendung/E8005601",
			"/ZVE/SdE/SdE/E8005401",
			"/ZVE/ZVE/Einkommen/E8006803",
			"/ZVE/ZVE/Einkommen/E8007401",
			"/ZVE/ZVE/Kassen/E8025402",
			"/ZVE/ZVE/P10g/E8026301",
			"/ZVE/ZVE/Rundfunk/E8025903",
			"/ZVE/ZVE/Verlustabzug/E8007001",
			"/ZVE/ZVE/Verlustabzug/E8007002",
			"/ZVE/ZVE/Verlustabzug/E8007101",
			"/ZVE/ZVE/Verlustabzug/E8007102",
			"/ZVE/ZVE/Verlustabzug/E8007103",
			"/ZVE/ZVE/Verlustabzug/E8007104",
			"/ZVE/ZVE/ZVE/E8007501",
		),
	),
	Rule(
		"8900330",
		"Regel_120030_1A_KSt",
		"",
		(
			"/ZVE/Steuerberechnung/Besonders/E8007603",
			"/ZVE/Steuerberechnung/Regel/E8007504",
			"/ZVE/ZVE/ZVE/E8007501",
		),
	),
	Rule(
		"8900361",
		"Regel_120061_1A_Einkommen",
		"",
		("/ZVE/Steuerberechnung/Regel/E8007502", "/ZVE/Steuerberechnung/Regel/E8007504"),
	),
	Rule(
		"8900331",
		"Regel_120031_1A_KSt",
		"",
		("/ZVE/Steuerberechnung/Regel/E8007502", "/ZVE/Steuerberechnung/Regel/E8007504"),
	),
	Rule(
		"8900570",
		"Regel_160026_1A_KSt",
		"",
		("/ZVE/Steuerberechnung/Regel/E8007502", "/ZVE/Steuerberechnung/Regel/E8007504"),
	),
	Rule(
		"8900184",
		"Regel_110017_1A_Verluste",
		"",
		(
			"/Verluste/Anfang/E8007801",
			"/Verluste/Anfang/E8007803",
			"/Verluste/Anfang/E8007804",
			"/Verluste/Anfang/E8007805",
			"/Verluste/Anfang/E8007902",
			"/Verluste/Anfang/E8007905",
			"/Verluste/Anfang/E8007908",
			"/Verluste/Negativ/E8001902",
			"/Verluste/Negativ/E8001904",
			"/Verluste/Negativ/E8008001",
			"/Verluste/Negativ/E8008102",
			"/Verluste/Positiv/Vorspalte/E8008501",
			"/Verluste/Positiv/Vorspalte/E8008502",
			"/Verluste/Positiv/Vorspalte/E8008601",
		),
	),
	Rule(
		"8900170",
		"Regel_090123_1A_Verluste",
		"",
		(
			"/Verluste/Anfang/E8007801",
			"/Verluste/Anfang/E8007803",
			"/Verluste/Anfang/E8007804",
			"/Verluste/Anfang/E8007805",
			"/Verluste/Anfang/E8007902",
			"/Verluste/Anfang/E8007905",
			"/Verluste/Anfang/E8007908",
			"/Verluste/Negativ/E8001902",
			"/Verluste/Negativ/E8001904",
			"/Verluste/Negativ/E8008001",
			"/Verluste/Negativ/E8008102",
			"/Verluste/Positiv/Hauptspalte/E8008602",
			"/Verluste/Positiv/Hauptspalte/E8008801",
			"/Verluste/Positiv/Vorspalte/E8008501",
			"/Verluste/Positiv/Vorspalte/E8008502",
			"/Verluste/Positiv/Vorspalte/E8008601",
			"/Verluste/Positiv/Vorspalte/E8008701",
		),
	),
	Rule(
		"8900347",
		"Regel_120047_1A_Verluste",
		"",
		(
			"/Verluste/Anfang/E8007801",
			"/Verluste/Anfang/E8007803",
			"/Verluste/Anfang/E8007804",
			"/Verluste/Anfang/E8007805",
			"/Verluste/Anfang/E8007902",
			"/Verluste/Anfang/E8007905",
			"/Verluste/Anfang/E8007907",
			"/Verluste/Anfang/E8007908",
			"/Verluste/Ende/E8009201",
			"/Verluste/Negativ/E8001902",
			"/Verluste/Negativ/E8001904",
			"/Verluste/Negativ/E8008001",
			"/Verluste/Negativ/E8008102",
			"/Verluste/Negativ/E8008401",
			"/Verluste/Positiv/Hauptspalte/E8008602",
			"/Verluste/Positiv/Hauptspalte/E8008702",
			"/Verluste/Positiv/Hauptspalte/E8008801",
			"/Verluste/Positiv/Vorspalte/E8008501",
			"/Verluste/Positiv/Vorspalte/E8008502",
			"/Verluste/Positiv/Vorspalte/E8008503",
			"/Verluste/Positiv/Vorspalte/E8008601",
			"/Verluste/Positiv/Vorspalte/E8008701",
		),
	),
	Rule(
		"8920021",
		"Regel_082003_1F_ausschuettbarerGew",
		"",
		(
			"/KSt1F/Gewinn/E8201001",
			"/KSt1F/Gewinn/E8201101",
			"/KSt1F/Gewinn/E8201201",
			"/KSt1F/Gewinn/E8201301",
		),
	),
	Rule(
		"8924445",
		"Regel_120045_1F27_28_Endbestaende",
		"",
		(
			"/KSt1F/ELK/Tabelle/Anfang/E8240102",
			"/KSt1F/ELK/Tabelle/Anfang/E8240103",
			"/KSt1F/ELK/Tabelle/Auflosung/E8243006",
			"/KSt1F/ELK/Tabelle/AusgleichSoAu/E8245501",
			"/KSt1F/ELK/Tabelle/EigAnt_Verkauf/E8244108",
			"/KSt1F/ELK/Tabelle/Einlagen/E8241501",
			"/KSt1F/ELK/Tabelle/Einlagen/E8241502",
			"/KSt1F/ELK/Tabelle/Einlagen/E8241601",
			"/KSt1F/ELK/Tabelle/Einlagen/E8241602",
			"/KSt1F/ELK/Tabelle/Einlagen/E8241603",
			"/KSt1F/ELK/Tabelle/Ende/E8245601",
			"/KSt1F/ELK/Tabelle/Erhohung_NK/E8243902",
			"/KSt1F/ELK/Tabelle/Erwerb_EigAnt/Uber/E8241407",
			"/KSt1F/ELK/Tabelle/Erwerb_EigAnt/Uber/E8241410",
			"/KSt1F/ELK/Tabelle/Erwerb_EigAnt/Unter/E8241416",
			"/KSt1F/ELK/Tabelle/Herabsetzung/E8241202",
			"/KSt1F/ELK/Tabelle/Org_Mehr/E8241715",
			"/KSt1F/ELK/Tabelle/Org_Mehr/E8241716",
			"/KSt1F/ELK/Tabelle/Org_Minder/E8246102",
			"/KSt1F/ELK/Tabelle/Org_Minder/E8246103",
			"/KSt1F/ELK/Tabelle/P35/E8241901",
			"/KSt1F/ELK/Tabelle/Ruckzahlung/E8241305",
			"/KSt1F/ELK/Tabelle/UN_UmwStG/Anpassung/E8243502",
			"/KSt1F/ELK/Tabelle/UN_UmwStG/Anpassung/E8243603",
			"/KSt1F/ELK/Tabelle/UN_UmwStG/Bet_UN/E8242301",
			"/KSt1F/ELK/Tabelle/UN_UmwStG/Bet_UT/E8242702",
			"/KSt1F/ELK/Tabelle/UN_UmwStG/Bet_UT/E8242901",
			"/KSt1F/ELK/Tabelle/UN_UmwStG/Bet_UT/E8243001",
			"/KSt1F/ELK/Tabelle/UT/Abspaltung_P29Abs1/E8244502",
			"/KSt1F/ELK/Tabelle/UT/Abspaltung_P29Abs3/E8244702",
			"/KSt1F/ELK/Tabelle/UT/Abspaltung_P29Abs4/E8245202",
			"/KSt1F/ELK/Tabelle/UT/Abspaltung_P29Abs4/E8245403",
			"/KSt1F/ELK/Tabelle/Verrechnung/Abspaltung/E8240602",
			"/KSt1F/ELK/Tabelle/Verrechnung/EeA_Leistungen/E8242205",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8242201",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8242202",
			"/KSt1F/ELK/Tabelle/Verrechnung/Nur_EeA/E8242204",
			"/KSt1F/ELK/Tabelle/Verschmelzung/E8245409",
			"/KSt1F/ELK/Tabelle/Weiterverausserung/E8244103",
		),
	),
	Rule(
		"8920011",
		"Regel_082002_1F_ausschuettbarerGew",
		"",
		(
			"/KSt1F/ELK/Tabelle/Anfang/E8240102",
			"/KSt1F/ELK/Tabelle/Anfang/E8240103",
			"/KSt1F/Gewinn/E8201001",
			"/KSt1F/Gewinn/E8201101",
			"/KSt1F/Gewinn/E8201201",
			"/KSt1F/Gewinn/E8201301",
			"/KSt1F/Leistungen/Gesamt/E8200502",
		),
	),
	Rule(
		"8920012",
		"KSt1F_22_040",
		"",
		(
			"/KSt1F/ELK/Tabelle/Anfang/E8240102",
			"/KSt1F/ELK/Tabelle/Anfang/E8240103",
			"/KSt1F/ELK/Tabelle/Org_Mehr/E8241715",
			"/KSt1F/ELK/Tabelle/Org_Mehr/E8241716",
			"/KSt1F/ELK/Tabelle/Verrechnung/E8241717",
			"/KSt1F/ELK/Tabelle/Verrechnung/EeA_Leistungen/E8242205",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240302",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240401",
			"/KSt1F/ELK/Tabelle/Verrechnung/Nur_EeA/E8240303",
		),
	),
	Rule(
		"8920013",
		"KSt1F_22_041",
		"",
		(
			"/KSt1F/ELK/Tabelle/Anfang/E8240102",
			"/KSt1F/ELK/Tabelle/Anfang/E8240103",
			"/KSt1F/ELK/Tabelle/Org_Mehr/E8241715",
			"/KSt1F/ELK/Tabelle/Org_Mehr/E8241716",
			"/KSt1F/ELK/Tabelle/Verrechnung/E8241717",
			"/KSt1F/ELK/Tabelle/Verrechnung/EeA_Leistungen/E8242205",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240302",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240401",
			"/KSt1F/ELK/Tabelle/Verrechnung/Nur_EeA/E8240303",
		),
	),
	Rule(
		"8920019",
		"KSt1F_22_042",
		"",
		(
			"/KSt1F/ELK/Tabelle/Anfang/E8240102",
			"/KSt1F/ELK/Tabelle/Anfang/E8240103",
			"/KSt1F/ELK/Tabelle/Org_Mehr/E8241715",
			"/KSt1F/ELK/Tabelle/Org_Mehr/E8241716",
			"/KSt1F/ELK/Tabelle/Verrechnung/E8241717",
			"/KSt1F/ELK/Tabelle/Verrechnung/EeA_Leistungen/E8242205",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240302",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240401",
			"/KSt1F/ELK/Tabelle/Verrechnung/Nur_EeA/E8240303",
		),
	),
	Rule(
		"8924077",
		"Regel_092401_1F27_28_Verrechnung",
		"",
		(
			"/KSt1F/ELK/Tabelle/Verrechnung/EeA_Leistungen/E8242205",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240302",
			"/KSt1F/ELK/Tabelle/Verrechnung/Nur_EeA/E8240303",
			"/KSt1F/Leistungen/Gesamt/E8200502",
		),
	),
	Rule(
		"8924079",
		"Regel_092403_1F27_28_Verrechnung",
		"",
		(
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240302",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240401",
			"/KSt1F/Gewinn/E8201301",
		),
	),
	Rule(
		"8924401",
		"Regel_120001_1F27_28_Verrechnung",
		"",
		(
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240302",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240401",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240501",
		),
	),
	Rule(
		"8920076",
		"KSt1F_22_020",
		"",
		(
			"/KSt1F/ELK/Tabelle/Verrechnung/E8241717",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8240501",
			"/KSt1F/ELK/Tabelle/Verrechnung/Kein_EeA/E8242201",
			"/KSt1F/Leistungen/Gesamt/E8122003",
			"/KSt1F/Leistungen/Gesamt/E8122011",
		),
	),
	Rule(
		"8912019",
		"Regel_111201_WA_AnrechBetr",
		"",
		("/WA/KapESt/E8120401", "/WA/KapESt/E8120601"),
		hint=True,
	),
)


@dataclass(frozen=True, slots=True)
class Entry:
	"""The value of a field of a Vordruck. ``rows`` numbers the instance of each repeated context on the path of the
	field, from the outermost and counted from 0, such as the Anteilseigner of KSt 1 lines 21 to 27."""

	feldkennung: str
	value: object
	rows: tuple[int, ...] = ()

	def __post_init__(self) -> None:
		object.__setattr__(self, "rows", tuple(self.rows))
		if any(isinstance(row, bool) or not isinstance(row, int) or row < 0 for row in self.rows):
			raise ValueError(f"{self.feldkennung}: the instances of a context count from 0, not {self.rows}")


@dataclass(frozen=True, slots=True)
class Vordruck:
	"""A Vordruck of the Erklärung with its entries; ``wj`` is the Indexfeld WJ of a Vordruck that has one, WJ1 or
	WJ2."""

	form: str
	entries: tuple[Entry, ...] = ()
	wj: str | None = None

	def __post_init__(self) -> None:
		object.__setattr__(self, "entries", tuple(self.entries))

	def extended(self, *entries: Entry) -> Vordruck:
		"""The Vordruck with the entries added."""
		return Vordruck(self.form, (*self.entries, *entries), self.wj)

	def value(self, feldkennung: str, rows: tuple[int, ...] = ()) -> object:
		"""The value of the field in the instances ``rows``, None without one."""
		return next(
			(entry.value for entry in self.entries if (entry.feldkennung, entry.rows) == (feldkennung, rows)),
			None,
		)


def entries(values: dict[str, object]) -> tuple[Entry, ...]:
	"""Entries of fields outside a repeated context, from their values by Feldkennung."""
	return tuple(Entry(feldkennung, value) for feldkennung, value in values.items())


def table_fields(form: str, table: str) -> tuple[Field, ...]:
	"""The fields of a table of the module docstring's layout, one per line."""
	return tuple(_field(form, line) for line in table.strip("\n").split("\n"))


def _field(form: str, line: str) -> Field:
	context, feldkennung, zeile, formatkennzeichen, length, required, kennzahl, pattern, label = line.split(
		"\t"
	)
	return Field(
		form=form,
		context=_cell(context) or "",
		feldkennung=feldkennung,
		label=label,
		format=formatkennzeichen,
		line=_cell(zeile),
		kennzahl=_cell(kennzahl),
		length=None if length == EMPTY else int(length),
		required=required == "Ja",
		pattern=pattern,
		options=tuple(_QUOTED.findall(pattern)) if formatkennzeichen == "H" else (),
	)


def _cell(text: str) -> str | None:
	return None if text == EMPTY else text


def checked(catalogue: FormCatalogue, steps: Iterable[Step] = STEPS) -> FormCatalogue:
	"""The catalogue, refused if a step names a field it lacks or holds on another form or line, so that a new year
	cannot drop a field the computation fills; the steps are those of steuerbote.kst.chain unless given."""
	for step in steps:
		if step.field is None:
			continue
		try:
			field = catalogue.field(step.field)
		except KeyError:
			raise ValueError(f"{catalogue.source}: no field {step.field} of the step {step.key}") from None
		if (field.form, field.line) != (step.form, step.line):
			raise ValueError(
				f"{catalogue.source}: the step {step.key} is {step.form} line {step.line}, its field "
				f"{step.field} {field.form} line {field.line}"
			)
	return catalogue


FORMS = (
	Form("KSt1", mandatory=True),
	Form("GK", count=2),
	Form("ZVE"),
	Form("Z"),
	Form("Verluste"),
	Form("WA"),
	Form("KSt1F", count=2),
	Form("Vorsatz", mandatory=True),
)
"""The Vordrucke of a GmbH or UG in the order of E30-2025.xsd, with the „max. lfd. Nr. Vordruck“ and the
Pflichtvordrucke of the JD, sheet „Allg. Information“."""
INDEXED = frozenset({"GK", "KSt1F"})
"""The Vordrucke whose first element is the Indexfeld WJ (JD, column Indexfeld)."""
WJ = ("WJ1", "WJ2")
"""The values of the Indexfeld, INDEXFELD_WJ of the JD."""

CATALOGUES: MappingProxyType[int, FormCatalogue] = MappingProxyType(
	{
		2026: checked(
			FormCatalogue(
				datenart=kst(2026),
				source="Jahresdokumentation_E30_2025.ods, Versionslabel 7.0, provisionally for 2026",
				forms=FORMS,
				fields=(
					*table_fields("KSt1", _KST1_2025),
					*table_fields("GK", _GK_2025),
					*table_fields("ZVE", _ZVE_2025),
					*table_fields("Z", _Z_2025),
					*table_fields("Verluste", _VERLUSTE_2025),
					*table_fields("WA", _WA_2025),
					*table_fields("KSt1F", _KST1F_2025),
				),
				rules=_RULES_2025,
			)
		)
	}
)

RECHTSFORMEN: MappingProxyType[int, MappingProxyType[str, MappingProxyType[str, str]]] = MappingProxyType(
	{
		2026: MappingProxyType(
			{
				"350": MappingProxyType({"RF_Gruppe": "1", "NurG": "1"}),
				"370": MappingProxyType({"RF_Gruppe": "1", "NurG": "1"}),
			}
		)
	}
)
"""The categories of the Rechtsformen Steuerbote files, by VZ: RECHTSFORMEN_KOERPERSCHAFTEN_V3 of the JD 2025, sheet
„Benutzerdefinierte Typen“."""

STEP_FIELDS: MappingProxyType[str, str] = MappingProxyType(
	{step.key: step.field for step in STEPS if step.field is not None}
)
"""The Feldkennung of each step of steuerbote.kst.chain that has one."""

GK_INCOME = "E8109901"
REGULAR_RATE_BASE = "E8007504"
CORPORATE_TAX = "E8007502"
NET_INCOME = "E8002001"
# The amounts a filed Anlage GK or ZVE always holds, if need be with zero (8900070, 8906061, 8900548, 8900100,
# 8900818, 8900836).
ALWAYS = frozenset({NET_INCOME, GK_INCOME, "E8004904", "E8005401", "E8006901", "E8007501"})
# Anlage GK lines 151 to 155 for each holding with exempt dividends, in the context
# Beteiligung/Tabelle/P8b_Vergleichbar/Unmittelbar/Einzel: name, share at the start of the year, kind, dividends.
HOLDING_NAME, HOLDING_SHARE, HOLDING_KIND, HOLDING_DIVIDENDS = "E8560403", "E8560406", "E8560407", "E8560404"
DIRECT, ACQUIRED = "1", "2"


def catalogue_for(year: int) -> FormCatalogue:
	"""The catalogue of the VZ; UnknownYearError for a VZ Steuerbote has none for."""
	try:
		return CATALOGUES[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in CATALOGUES)
		raise UnknownYearError(
			f"no Vordrucke of the Körperschaftsteuer for {year}; known years: {known}"
		) from None


def step_field(year: int, key: str) -> Field:
	"""The field of a step of steuerbote.kst.chain in the catalogue of the VZ; KeyError for a step without one."""
	return catalogue_for(year).field(STEP_FIELDS[key])


def vordrucke(result: KstResult) -> tuple[Vordruck, ...]:
	"""The Vordrucke GK, ZVE and WA with the amounts of a computed VZ, with Anlage Verluste and Anlage Z where the VZ
	needs them; see the module docstring."""
	amounts: dict[str, dict[str, object]] = {"GK": {}, "ZVE": {}, "WA": {}}
	for step in STEPS:
		declared = result.lines[step.key].declared
		if step.field is not None and (declared or step.field in ALWAYS):
			amounts[step.form][step.field] = declared
	zve = amounts["ZVE"]
	zve.pop(CORPORATE_TAX, None)
	if result.zve > ZERO:
		zve[REGULAR_RATE_BASE] = result.zve
		zve[CORPORATE_TAX] = result.kst
	found = [
		Vordruck("GK", (*entries(amounts["GK"]), *_holdings(result)), WJ[0]),
		Vordruck("ZVE", entries(zve)),
		Vordruck("WA", entries(amounts["WA"])),
	]
	if result.losses.required:
		found.append(Vordruck("Verluste", entries(_losses(result.losses))))
	if result.donations.required:
		found.append(Vordruck("Z", entries(_donations(result.donations))))
	return tuple(found)


def _holdings(result: KstResult) -> Iterable[Entry]:
	exempt = [
		holding
		for holding in result.p8b.holdings
		if holding.exemption is Exemption.EXEMPT and holding.result.dividends
	]
	for row, holding in enumerate(exempt):
		yield Entry(HOLDING_NAME, holding.result.holding.name, (row,))
		yield Entry(HOLDING_SHARE, holding.result.holding.share_at_year_start, (row,))
		yield Entry(HOLDING_KIND, ACQUIRED if holding.acquisition_counts else DIRECT, (row,))
		yield Entry(HOLDING_DIVIDENDS, holding.result.dividends, (row,))


def _losses(losses: LossDeduction) -> dict[str, object]:
	lines: dict[str, object] = {}
	if losses.carry_forward:
		lines["E8007801"] = losses.carry_forward
	if losses.loss:
		lines["E8008001"] = losses.loss
		if losses.carry_back is not None:
			lines["E8008102"] = losses.carry_back
	else:
		lines["E8008401"] = losses.subtotal
		lines["E8008501"] = losses.total_income
		lines["E8008601"] = lines["E8008602"] = losses.unlimited
		if losses.limited:
			lines["E8008701"] = losses.rest
			lines["E8008702"] = losses.carry_forward - losses.unlimited
			lines["E8008801"] = losses.limited
	lines["E8009201"] = losses.remaining
	return lines


def _donations(donations: Donations) -> dict[str, object]:
	lines: dict[str, object] = {}
	if donations.carry_forward:
		lines["E8009401"] = donations.carry_forward
	if donations.donations.declared:
		lines["E8005602"] = donations.donations.declared
	lines["E8009701"] = donations.available
	lines["E8006101"] = donations.deductible
	lines["E8010101"] = donations.remaining
	if donations.turnover_and_wages is not None:
		lines["E8006001"] = donations.turnover_and_wages
	return lines


# KSt 1 F lines 42, 43, 11, 12, 17 to 20, 46 to 50, 91, 92, 95 and 152 (steuerbote.kst.einlagekonto).
OPENING, OPENING_SONDERAUSWEIS = "E8240103", "E8240201"
DISTRIBUTIONS, CERTIFIED_REDUCTION = "E8200502", "E8122003"
PREVIOUS_EQUITY, PREVIOUS_NOMINAL_CAPITAL, POSITIVE_OPENING, DISTRIBUTABLE = (
	"E8201001",
	"E8201101",
	"E8201201",
	"E8201301",
)
SUBTOTAL, SET_OFF_DISTRIBUTIONS, SET_OFF_DISTRIBUTABLE, EXCESS, REDUCTION = (
	"E8241717",
	"E8240302",
	"E8240401",
	"E8240501",
	"E8242201",
)
CONTRIBUTIONS_BOOKED, CONTRIBUTIONS_NOT_BOOKED, OTHER_CONTRIBUTIONS = "E8241501", "E8241502", "E8241601"
CLOSING, CLOSING_SONDERAUSWEIS = "E8245601", "E8245602"


def kst1f(
	account: Einlagekonto,
	*,
	wj: str = WJ[0],
	previous_equity: Decimal | None = None,
	previous_nominal_capital: Decimal | None = None,
	contributions_booked: Decimal = ZERO,
	contributions_not_booked: Decimal = ZERO,
	other_contributions: Decimal = ZERO,
) -> Vordruck:
	"""KSt 1 F of the Wirtschaftsjahr ``wj`` from the Einlagekonto that steuerbote.kst.einlagekonto.roll_forward()
	gives, with the equity of the previous year and the Einlagen it was given; see the module docstring."""
	if contributions_booked + contributions_not_booked + other_contributions != account.contributions:
		raise ValueError(
			f"the Einlagen of lines 91, 92 and 95 add up to "
			f"{contributions_booked + contributions_not_booked + other_contributions}, the Einlagekonto took "
			f"{account.contributions}"
		)
	lines: dict[str, object] = {OPENING: account.opening}
	if account.sonderausweis:
		lines[OPENING_SONDERAUSWEIS] = account.sonderausweis
	if account.distributions:
		lines[DISTRIBUTIONS] = account.distributions
	if account.certified_reduction:
		lines[CERTIFIED_REDUCTION] = account.certified_reduction
	if account.distributable is not None:
		lines.update(_distributable(account, previous_equity, previous_nominal_capital))
	if account.subtotal is not None:
		lines[SUBTOTAL] = account.subtotal
	if account.distributions and account.excess is not None:
		lines[SET_OFF_DISTRIBUTIONS] = account.distributions
		lines[SET_OFF_DISTRIBUTABLE] = account.distributable
		lines[EXCESS] = account.excess
	if account.subtotal is not None:
		lines[REDUCTION] = account.reduction
	for field, amount in (
		(CONTRIBUTIONS_BOOKED, contributions_booked),
		(CONTRIBUTIONS_NOT_BOOKED, contributions_not_booked),
		(OTHER_CONTRIBUTIONS, other_contributions),
	):
		if amount:
			lines[field] = amount
	lines[CLOSING] = account.closing
	if account.closing_sonderausweis:
		lines[CLOSING_SONDERAUSWEIS] = account.closing_sonderausweis
	return Vordruck("KSt1F", entries(lines), wj)


def _distributable(
	account: Einlagekonto, equity: Decimal | None, nominal_capital: Decimal | None
) -> dict[str, object]:
	"""Lines 17 to 20, from the equity the ausschüttbarer Gewinn of the Einlagekonto was computed with."""
	if equity is None or nominal_capital is None:
		raise ValueError(
			"lines 17 and 18 of KSt 1 F need the Eigenkapital and the Nennkapital of the previous year"
		)
	if max(equity - nominal_capital - account.positive_opening, ZERO) != account.distributable:
		raise ValueError(
			f"the Eigenkapital {equity} and the Nennkapital {nominal_capital} do not give the ausschüttbarer Gewinn "
			f"{account.distributable} of the Einlagekonto"
		)
	return {
		PREVIOUS_EQUITY: equity,
		PREVIOUS_NOMINAL_CAPITAL: nominal_capital,
		POSITIVE_OPENING: account.positive_opening,
		DISTRIBUTABLE: account.distributable,
	}
