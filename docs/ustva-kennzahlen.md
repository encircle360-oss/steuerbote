# Umsatzsteuer-Voranmeldung: Kennzahlen und Kontenzuordnung

Diese Seite ist die fachliche Grundlage des Rechenkerns unter `steuerbote/ustva`: Quelle, Rundung, alle Kennzahlen des Katalogs, die Kontenzuordnung mit den Vorgaben für SKR03 und SKR04, ihre Zeilen für die [Umsatzsteuererklärung](#kontenzuordnung-der-umsatzsteuererklärung) sowie Zeiträume und Fristen. Sie ersetzt keine Steuerberatung. Lass die Einrichtung deiner Firma von deiner Steuerberatung bestätigen.

## Quelle

BMF-Schreiben vom 29. Dezember 2025, GZ III C 3 - S 7344/00039/007/036: „Umsatzsteuer; Muster der Vordrucke im Umsatzsteuer-Voranmeldungs- und -Vorauszahlungsverfahren für das Kalenderjahr 2026“

<https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/2025-12-29-vordruckmuster-USt-voranmeldung-2026.pdf>

Das Schreiben führt für die Voranmeldungszeiträume ab Januar 2026 vier Vordruckmuster ein:

| Vordruck | Inhalt | Verwendung in Steuerbote |
|---|---|---|
| USt 1 A | Umsatzsteuer-Voranmeldung 2026 | Zeilen, Kennzahlen und Bezeichnungen des Katalogs |
| USt 1 E | Anleitung zur Umsatzsteuer-Voranmeldung 2026 | Rundung, Fälligkeit |
| USt 1 H | Antrag auf Dauerfristverlängerung und Anmeldung der Sondervorauszahlung 2026 | Zeilen und Bezeichnungen des Vordrucks, siehe [Dauerfristverlängerung](dauerfristverlaengerung.md) |
| USt 5 E | Anleitung zum Antrag auf Dauerfristverlängerung/zur Anmeldung der Sondervorauszahlung 2026 | Sondervorauszahlung und Fristen, siehe [Dauerfristverlängerung](dauerfristverlaengerung.md) |

Für 2027 gibt es noch kein solches Schreiben; Steuerbote kennt 2027 vorläufig aus der Dokumentation der Beta ERiC 45.1.5.0, siehe [Jahrgang 2027, vorläufig](#jahrgang-2027-vorläufig).

[`kennzahlen.py`](../steuerbote/ustva/kennzahlen.py) führt einen Katalog je Jahr des Vordrucks (`CATALOGUES`), für 2026 und vorläufig für 2027, für die Jahre der Jahrestabelle `YEARS` in [`years.py`](../steuerbote/ustva/years.py). Der Katalog 2026 folgt dem Vordruck USt 1 A 2026 Zeile für Zeile. [`test_kennzahlen.py`](../steuerbote/ustva/tests/test_kennzahlen.py) hält jede Kennzahl mit Zeile, Art, Wirkung, Steuersatz und Steuer-Kennzahl so fest, wie sie auf dem Vordruck steht, und prüft den Katalog dagegen. `catalogue_for(year)` wählt den Katalog nach dem Jahr des Zeitraums, `KENNZAHLEN` ist der neueste (`LATEST_YEAR`). Für ein Jahr ohne Katalog gibt es einen `UnknownYearError`.

Vordruck und Anleitung ändern sich jedes Jahr. Deshalb kommt zu jedem Jahreswechsel ein Katalog für das neue Jahr dazu, Zeile für Zeile gegen das neue BMF-Schreiben geprüft, siehe [Jahreswechsel](#jahreswechsel). Der erste Katalog ist der für 2026; Kataloge für frühere Jahre sind nicht geplant, siehe [Roadmap](roadmap.md#grundsätze).

Die Kontenbezeichnungen auf dieser Seite stammen aus den DATEV-Kontenrahmen nach dem Bilanzrichtlinie-Umsetzungsgesetz, gültig für 2026:

- Standardkontenrahmen SKR 03 (Prozessgliederungsprinzip), Art.-Nr. 11174: <https://www.datev.de/content/dam/markenassets/themen-und-produktgruppen/zielgruppen/mandant/unternehmer/branche/bau/11174%20SKR03%20BilrUg.pdf>
- Standardkontenrahmen SKR 04 (Abschlussgliederungsprinzip), Art.-Nr. 11175: <https://www.datev.de/content/dam/markenassets/themen-und-produktgruppen/zielgruppen/mandant/unternehmer/branche/bau/11175%20SKR04%20BilrUg.pdf>

## Rundung

Die Anleitung zur Umsatzsteuer-Voranmeldung 2026 sagt:

> „Tragen Sie bei den Bemessungsgrundlagen bitte nur Beträge in vollen Euro ein; bei den Umsatzsteuer- und Vorsteuerbeträgen ist dagegen stets auch die Eintragung von Centbeträgen erforderlich.“

Zu den Zeilen 13 bis 16 ergänzt sie, dass Bemessungsgrundlagen „in vollen Euro (ohne Centbeträge) anzugeben“ sind. Negative Beträge erhalten ein Minuszeichen.

Steuerbote setzt das in [`rounding.py`](../steuerbote/ustva/rounding.py) so um:

| Betrag | Regel | Funktion | Beispiele aus den Tests |
|---|---|---|---|
| Bemessungsgrundlage | volle Euro: Die Cent fallen weg, Richtung null, auch bei negativen Beträgen | `to_full_euros` | 1.000,99 → 1.000; -1.000,99 → -1.000; -0,40 → 0 |
| Steuerbetrag | auf Cent kaufmännisch gerundet, ein halber Cent rundet weg von null | `to_cents` | 0,005 → 0,01; 0,004 → 0,00; -0,005 → -0,01 |
| Steuer aus einer Bemessungsgrundlage | Bemessungsgrundlage × Steuersatz, dann auf Cent gerundet | `tax_from_base` | 999 × 7 % → 69,93; 0,50 × 19 % → 0,10 |
| Gebuchte Steuer eines Belegs über seine Bemessungsgrundlagen | jede Bemessungsgrundlage ihre Steuer auf Cent, der Rest zur betragsmäßig größten | `apportion_cents` | 22,54 über 3,507 und 19,019 → 3,51 und 19,03 |

Ein Ergebnis von null wird nie als „-0“ gemeldet. Außerdem gilt:

- **Alles ist `Decimal`.** Ein `float` führt zu einem `TypeError`, weil binäre Gleitkommazahlen Cent nicht genau darstellen. Gerundet wird nur in `rounding.py`.
- **Buchungen kommen in Cent.** Jeder Betrag einer Buchungszeile (`LedgerLine`) und jeder Wert in `extra_values` muss endlich sein und in ganzen Cent vorliegen, sonst folgt ein `ValueError`.
- **Kz 83 rechnet mit den gemeldeten Werten.** Für die Zeilen 13, 14, 25 und 26 (Kz 81, 86, 89 und 93) hat der Vordruck keine eigene Steuer-Kennzahl, die Steuer ergibt sich aus Bemessungsgrundlage und Steuersatz. Steuerbote berechnet sie mit der Vorgabe aus der gemeldeten Bemessungsgrundlage in vollen Euro, wahlweise nimmt es die gebuchte Steuer der Belege, siehe [Steuer zu Umsätzen mit festem Steuersatz](#steuer-zu-umsätzen-mit-festem-steuersatz). Alle anderen Beträge gehen mit ihrem gemeldeten Wert in Cent ein.
- **Eine abgeleitete Bemessungsgrundlage zählt genau.** Ergibt sich die Bemessungsgrundlage eines Belegs ohne Grundlagenkonto aus seinen Buchungszeilen, geht ihr genauer Betrag in die Kennzahl ein; nur wenn die Zeilen sie nicht eindeutig zeigen, rechnet Steuerbote sie aus der Steuer zurück: Steuer ÷ Satz, auf Cent kaufmännisch gerundet (`base_from_tax`), Beispiel aus den Tests: 11,98 EUR zu 19 % → 63,05 EUR. Die Steuer dieses Betrags ist wieder die gebuchte Steuer. Auf volle Euro gerundet wird erst die Summe des Zeitraums, wie bei jeder anderen Bemessungsgrundlage, siehe [Bemessungsgrundlage ohne Grundlagenkonto](#bemessungsgrundlage-ohne-grundlagenkonto).
- **Die Verprobung rechnet mit dem genauen Wert.** Sie vergleicht die gebuchte Steuer mit der Steuer auf die genaue Bemessungsgrundlage. Beispiel aus den Tests: 1.000,99 EUR auf 8400 und 190,19 EUR auf 1776 ergeben Kz 81 = 1.000 und Kz 83 = 190,00. Die Verprobung rechnet 1.000,99 × 19 % = 190,19 und geht ohne Differenz auf.
- **Toleranz.** Die Bücher runden die Steuer je Beleg, nicht je Monat. Deshalb rechnet Steuerbote die abgeleitete Steuer (Kz 47, 85, 96) und jede Verprobung je Beleg (`voucher` der Buchungszeile): Die Steuer eines Belegs wird aus seinen Grundlagen berechnet und auf Cent gerundet, die Kennzahl ist die Summe dieser Beträge. Je Beleg darf die gebuchte Steuer um höchstens `tolerance` (Vorgabe 0,01 EUR) von der berechneten abweichen, sonst steht der Beleg als `Deviation` in der Verprobung. Buchungszeilen ohne Beleg bilden eine Gruppe; dort gilt die Toleranz je Buchung auf den Grundlagenkonten.

## Kennzahlen des Vordrucks USt 1 A 2026

Der Katalog für 2026 enthält 50 Kennzahlen. Zu den Spalten:

- **Art:** Bemessungsgrundlage (gemeldet in vollen Euro), Steuer (gemeldet in Cent), Kennzeichen, Datum oder Schlüssel. Kennzeichen, Datum und Schlüssel tragen keinen Betrag. Sie lassen sich keinem Konto zuordnen und nicht über `extra_values` setzen; gesetzt werden sie in eigenen Feldern der Meldung: Kz 10, 22, 26 und 29 als Kennzeichen, Kz 70 als Datum und Kz 500 mit Begründung, siehe [Architektur](architektur.md#umsatzsteuer-voranmeldung-vat-return).
- **Wirkung:** wie der Betrag in die verbleibende Vorauszahlung (Kz 83) eingeht: erhöht, mindert oder keine. Bei Kz 81, 86, 89 und 93 erhöht die Steuer, die aus der Bemessungsgrundlage folgt.
- **Steuersatz/Steuer-Kz:** der Satz, mit dem der Vordruck die Steuer selbst berechnet, oder die Kennzahl, in der die Steuer zu dieser Bemessungsgrundlage eigens steht.

| Zeile | Kz | Bezeichnung (kurz) | Art | Wirkung | Steuersatz/Steuer-Kz |
|---|---|---|---|---|---|
| | | **Vor Abschnitt A** | | | |
| 10 | 10 | Berichtigte Anmeldung | Kennzeichen | keine | |
| 11 | 22 | Belege sind beigefügt bzw. werden gesondert eingereicht | Kennzeichen | keine | |
| 12 | 70 | Wechsel von der Kleinunternehmer-Regelung (§ 19 UStG) zur Regelbesteuerung: Datum des Wechsels | Datum | keine | |
| | | **A. Steuerpflichtige Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben** | | | |
| 13 | 81 | Steuerpflichtige Umsätze zu 19 % | Bemessungsgrundlage | erhöht | 19 % |
| 14 | 86 | Steuerpflichtige Umsätze zu 7 % | Bemessungsgrundlage | erhöht | 7 % |
| 15 | 87 | Steuerpflichtige Umsätze zu 0 % | Bemessungsgrundlage | keine | |
| 16 | 35 | Steuerpflichtige Umsätze zu anderen Steuersätzen | Bemessungsgrundlage | keine | Kz 36 |
| 16 | 36 | Steuer auf Umsätze zu anderen Steuersätzen | Steuer | erhöht | |
| 17 | 77 | Lieferungen land- und forstwirtschaftlicher Betriebe nach § 24 UStG an Abnehmer mit USt-IdNr. | Bemessungsgrundlage | keine | |
| 18 | 76 | Umsätze, für die eine Steuer nach § 24 UStG zu entrichten ist | Bemessungsgrundlage | keine | Kz 80 |
| 18 | 80 | Steuer auf Umsätze nach § 24 UStG | Steuer | erhöht | |
| | | **B. Steuerfreie Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben** | | | |
| 19 | 41 | Innergemeinschaftliche Lieferungen (§ 4 Nr. 1 Buchst. b UStG) an Abnehmer mit USt-IdNr. | Bemessungsgrundlage | keine | |
| 20 | 44 | Innergemeinschaftliche Lieferungen neuer Fahrzeuge an Abnehmer ohne USt-IdNr. | Bemessungsgrundlage | keine | |
| 21 | 49 | Innergemeinschaftliche Lieferungen neuer Fahrzeuge außerhalb eines Unternehmens (§ 2a UStG) | Bemessungsgrundlage | keine | |
| 22 | 43 | Weitere steuerfreie Umsätze mit Vorsteuerabzug, z. B. Ausfuhrlieferungen | Bemessungsgrundlage | keine | |
| 23 | 48 | Steuerfreie Umsätze ohne Vorsteuerabzug | Bemessungsgrundlage | keine | |
| | | **C. Innergemeinschaftliche Erwerbe** | | | |
| 24 | 91 | Steuerfreie innergemeinschaftliche Erwerbe (§§ 4b und 25c UStG) | Bemessungsgrundlage | keine | |
| 25 | 89 | Steuerpflichtige innergemeinschaftliche Erwerbe zu 19 % | Bemessungsgrundlage | erhöht | 19 % |
| 26 | 93 | Steuerpflichtige innergemeinschaftliche Erwerbe zu 7 % | Bemessungsgrundlage | erhöht | 7 % |
| 27 | 90 | Steuerpflichtige innergemeinschaftliche Erwerbe zu 0 % | Bemessungsgrundlage | keine | |
| 28 | 95 | Steuerpflichtige innergemeinschaftliche Erwerbe zu anderen Steuersätzen | Bemessungsgrundlage | keine | Kz 98 |
| 28 | 98 | Steuer auf innergemeinschaftliche Erwerbe zu anderen Steuersätzen | Steuer | erhöht | |
| 29 | 94 | Innergemeinschaftliche Erwerbe neuer Fahrzeuge (§ 1b Abs. 2 und 3 UStG) von Lieferern ohne USt-IdNr. | Bemessungsgrundlage | keine | Kz 96 |
| 29 | 96 | Steuer auf innergemeinschaftliche Erwerbe neuer Fahrzeuge | Steuer | erhöht | |
| | | **D. Leistungsempfänger als Steuerschuldner (§ 13b UStG)** | | | |
| 30 | 46 | Sonstige Leistungen nach § 3a Abs. 2 UStG eines im übrigen Gemeinschaftsgebiet ansässigen Unternehmers (§ 13b Abs. 1 UStG) | Bemessungsgrundlage | keine | Kz 47 |
| 30 | 47 | Steuer auf diese sonstigen Leistungen | Steuer | erhöht | |
| 31 | 73 | Umsätze, die unter das GrEStG fallen (§ 13b Abs. 2 Nr. 3 UStG) | Bemessungsgrundlage | keine | Kz 74 |
| 31 | 74 | Steuer auf Umsätze, die unter das GrEStG fallen | Steuer | erhöht | |
| 32 | 84 | Andere Leistungen (§ 13b Abs. 2 Nr. 1, 2, 4 bis 12 UStG) | Bemessungsgrundlage | keine | Kz 85 |
| 32 | 85 | Steuer auf andere Leistungen nach § 13b UStG | Steuer | erhöht | |
| | | **E. Ergänzende Angaben zu Umsätzen** | | | |
| 33 | 42 | Lieferungen des ersten Abnehmers bei innergemeinschaftlichen Dreiecksgeschäften (§ 25b UStG) | Bemessungsgrundlage | keine | |
| 34 | 60 | Steuerpflichtige Umsätze, für die der Leistungsempfänger die Steuer nach § 13b Abs. 5 UStG schuldet | Bemessungsgrundlage | keine | |
| 35 | 21 | Nicht steuerbare sonstige Leistungen gemäß § 18b Satz 1 Nr. 2 UStG | Bemessungsgrundlage | keine | |
| 36 | 45 | Übrige nicht steuerbare Umsätze (Leistungsort nicht im Inland) | Bemessungsgrundlage | keine | |
| 37 | | *Umsatzsteuer: Summe der Zeilen 13 bis 18 und 25 bis 32* | Summe | | |
| | | **F. Abziehbare Vorsteuerbeträge und Berichtigung des Vorsteuerabzugs** | | | |
| 38 | 66 | Vorsteuer aus Rechnungen anderer Unternehmer (§ 15 Abs. 1 Satz 1 Nr. 1 UStG), aus Leistungen im Sinne des § 27 Abs. 40a UStG und aus Dreiecksgeschäften (§ 25b Abs. 5 UStG) | Steuer | mindert | |
| 39 | 61 | Vorsteuer aus dem innergemeinschaftlichen Erwerb von Gegenständen (§ 15 Abs. 1 Satz 1 Nr. 3 UStG) | Steuer | mindert | |
| 40 | 62 | Entstandene Einfuhrumsatzsteuer (§ 15 Abs. 1 Satz 1 Nr. 2 UStG) | Steuer | mindert | |
| 41 | 67 | Vorsteuer aus Leistungen im Sinne des § 13b UStG (§ 15 Abs. 1 Satz 1 Nr. 4 UStG) | Steuer | mindert | |
| 42 | 63 | Vorsteuer nach allgemeinen Durchschnittssätzen (§ 23a UStG) | Steuer | mindert | |
| 43 | 59 | Vorsteuerabzug für innergemeinschaftliche Lieferungen neuer Fahrzeuge außerhalb eines Unternehmens (§ 2a UStG) und von Kleinunternehmern (§ 15 Abs. 4a UStG) | Steuer | mindert | |
| 44 | 64 | Berichtigung des Vorsteuerabzugs (§ 15a UStG) | Steuer | mindert | |
| 45 | | *Verbleibender Betrag: Zeile 37 abzüglich der Zeilen 38 bis 44* | Summe | | |
| | | **G. Andere Steuerbeträge** | | | |
| 46 | 65 | Steuer infolge des Wechsels der Besteuerungsform sowie Nachsteuer auf versteuerte Anzahlungen u. Ä. wegen Steuersatzänderung | Steuer | erhöht | |
| 47 | 69 | In Rechnungen unrichtig oder unberechtigt ausgewiesene Steuer (§ 14c UStG) und weitere geschuldete Steuerbeträge | Steuer | erhöht | |
| | | **H. Vorauszahlung/Überschuss** | | | |
| 48 | | *Umsatzsteuer-Vorauszahlung/Überschuss: Summe der Zeilen 45 bis 47* | Summe | | |
| 49 | 39 | Abzug der festgesetzten Sondervorauszahlung für Dauerfristverlängerung | Steuer | mindert | |
| 50 | 83 | Verbleibende Umsatzsteuer-Vorauszahlung / verbleibender Überschuss | Steuer | keine (Ergebnis) | |
| | | **I. Ergänzende Angaben zu Minderungen nach § 17 Abs. 1 Sätze 1 und 2 i. V. m. Abs. 2 Nr. 1 Satz 1 UStG** | | | |
| 51 | 50 | Minderung der Bemessungsgrundlage (in den Zeilen 13 bis 18 enthalten) | Bemessungsgrundlage | keine | |
| 52 | 37 | Minderung der abziehbaren Vorsteuerbeträge (in Zeile 38 und in den Zeilen 42 und 43 enthalten) | Steuer | keine | |
| | | **J. Sonstige Angaben** | | | |
| 53 | 29 | Verrechnung des Erstattungsbetrags erwünscht / Erstattungsbetrag ist abgetreten | Kennzeichen | keine | |
| 54 | 26 | SEPA-Lastschriftmandat soll ausnahmsweise nicht verwendet werden | Kennzeichen | keine | |
| | | **Ergänzende Angaben zur Steueranmeldung** | | | |
| 55 | 500 | Ergänzende Angaben zur Steueranmeldung | Schlüssel | keine | |

Hinweise:

- Die Zeilen 37, 45 und 48 sind Summen, die der Vordruck selbst bildet. Sie tragen keine Kennzahl. Steuerbote liefert sie als `output_tax` (Zeile 37), `remaining_tax` (Zeile 45) und `prepayment` (Zeile 48). Zeilennummer und Kennzahl sind verschiedene Zahlen: Kz 37 steht in Zeile 52, Kz 45 in Zeile 36, Kz 48 in Zeile 23.
- Ein negativer Wert in Kz 83 ist ein Überschuss. Der Vordruck verlangt dafür ein Minuszeichen.
- Negative Werte sind überall möglich. Zu Zeile 44 schreibt die Anleitung: „Handelt es sich bei den Berichtigungsbeträgen um zurückzuzahlende Vorsteuerbeträge, tragen Sie bitte vor dem Betrag ein Minuszeichen ein.“ Ein negativer Betrag in Kz 64 mindert die Summe der Vorsteuer und erhöht damit Kz 83.
- Die Zeilen 1 bis 9 (Steuernummer, Wirtschafts-Identifikationsnummer, Finanzamt, Unternehmer, Voranmeldungszeitraum) sind Kopfdaten und keine Kennzahlen.
- Kz 500 nimmt einen der Schlüssel 1 bis 4 auf, die der Vordruck in Zeile 55 erklärt.

## Jahrgang 2027, vorläufig

Am 23. November 2026 hatte das BMF kein Schreiben mit den Vordruckmustern 2027 veröffentlicht, sein neuestes BMF-Schreiben war vom 13. November 2026, und ERiC 45 gab es nur als Beta. Steuerbote kennt 2027 deshalb vorläufig (`provisional` in `YEARS`): Kennzahlen, Formatkennzeichen und Regeln kommen aus `Jahresdokumentation_UStVA_2027.ods` (Versionslabel 4.0) und `UStVA-2027.xsd` der ERiC-Dokumentation 45.1.5.0 (Beta), Zeilen und Bezeichnungen aus dem Vordruck USt 1 A 2026 (`form_year` 2026). Die Jahresdokumentationen 2026 aus ERiC 44.3.6.0 und 2027 aus der Beta, Blatt für Blatt verglichen:

| Teil | 2026 | 2027 | In Steuerbote |
|---|---|---|---|
| Kennzahlen des Kontexts `Umsatzsteuervoranmeldung` | 50 | dieselben 50, mit derselben Vordruckzeile, demselben Formatkennzeichen und derselben Beschreibung | der Katalog 2027 ist der von 2026 |
| Kz 09, Hersteller-ID, in allen drei Kontexten | fünf Ziffern, auch mit fünf weiteren, durch `*` getrennten Angaben, höchstens 95 Zeichen | genau fünf Ziffern | der Schreiber schreibt in jedem Jahr nur die Hersteller-ID |
| Regel 110085046 (`UStVA_Laenge_Kz09`, `Df_Kz09_Laenge`, `Svz_Kz09_Laenge`) | Kz 09 trägt nur die Hersteller-ID, sobald Unternehmer, Berater oder Mandant angegeben sind | entfällt, das Format von Kz 09 sagt es schon | das Layout USt 1 H 2027 hat die beiden Regeln nicht mehr |
| Regel 11085156 (`UStVA_Kz44_BZSt_Hinweis`), Hinweis | – | neu: Lieferungen neuer Fahrzeuge in Kz 44 sind auch dem BZSt zu melden (§ 18c UStG, § 1 Abs. 1 FzgLiefgMeldV) | die Simulation gibt den Hinweis ab 2027, siehe [ERiC](eric.md#simulation) |
| Regel 110085049 (`Kz500_Hinweis`), Hinweis | in allen drei Kontexten | anderer Hinweistext | nichts: Steuerbote führt die Regel, nicht ihren Text |
| Schema | Namensraum `…/ustva/v2026`, Version 2026 | `…/ustva/v2027`, Version 2027, Elemente in der Reihenfolge von 2026 | `SCHEMAS` in `elster/ustva_xml.py` |
| datenartVersion und Plugin | `UStVA_2026`, `checkUStVA_2026` | `UStVA_2027`, `checkUStVA_2027` | aus dem Jahr gebildet; `libcheckUStVA_2027.so` kommt mit ERiC 45 |

In Zahlen: keine neue, keine entfallene und keine geänderte Kennzahl; ein geändertes Feld, Kz 09, in jedem der drei Kontexte; von den 109 Regeln 2026 entfallen drei (110085046) und kommt eine dazu (11085156), drei behalten Code und Art bei neuem Text (110085049); 107 Regeln 2027. Rundung, Zeiträume und Fristen bleiben, siehe [Zeiträume und Fristen](#zeiträume-und-fristen).

Solange 2027 vorläufig ist, steht an jeder Voranmeldung 2027 „Vorläufige Vordrucke“, sie wird mit „Berechnen“ nicht „Bereit“ und geht nur mit Anmerkungen ab, die sagen, warum trotzdem, wie die Erklärungen der Ertragsteuern mit ihren vorläufigen Vordrucken (siehe [Ertragsteuern](ertragsteuern.md#vorläufige-vordrucke-2026)). Ihr Ausdruck behält den Aufbau des Vordrucks 2026 und trägt unter dem Titel „vorläufig (Beta ERiC 45.1.5.0, Vordruck 2026)“.

Das Vorläufige heben zwei Veröffentlichungen auf: eine freigegebene Version von ERiC 45 mit `libcheckUStVA_2027.so` und ihrer Dokumentation, gegen die die Jahresprüfung 2027 noch einmal läuft; und das BMF-Schreiben mit den Vordruckmustern USt 1 A und USt 1 H 2027, gegen das Katalog, Bezeichnungen, Vordruck USt 1 H und die Druckformate Zeile für Zeile geprüft werden. Dann bekommt `YEARS` Datum, Geschäftszeichen und Adresse des Schreibens, und `provisional` fällt weg; ab dem nächsten „Berechnen“ kann eine Voranmeldung 2027 „Bereit“ werden. Die Vorgaben für SKR03 und SKR04 bleiben bis dahin auf den DATEV-Ausgaben 2026, siehe [Jahreswechsel](#jahreswechsel), Schritt 5.

## Kontenzuordnung

### Modell

Die Zuordnung steht in [`mapping.py`](../steuerbote/ustva/mapping.py) und ist reine Datenhaltung:

- **`AccountRule`** ordnet ein Konto über seine Kontonummer einer Kennzahl zu und legt die Seite fest, auf der das Konto seinen Saldo trägt: Haben (`Side.CREDIT`) für Erlöse und andere Steuerbeträge, Soll (`Side.DEBIT`) für Erwerbe, bezogene Leistungen und Vorsteuer. Der Betrag ist der Saldo des Zeitraums auf dieser Seite. Eine Gutschrift auf einem Erlöskonto mindert also die Bemessungsgrundlage und kann sie negativ machen. Hat die Kennzahl eine eigene Steuer-Kennzahl (etwa Kz 46 mit Kz 47), kann die Regel einen Steuersatz tragen (`tax_rate`). Dann leitet Steuerbote die Steuer aus dem Grundlagenkonto ab: Saldo × Satz geht in die Steuer-Kennzahl.
- **`TaxCheck`** ist eine Verprobung mit einer Bezeichnung (`label`): Die Steuer, die zu den Grundlagenkonten gehört (`base_accounts`), wird mit der Steuer auf den Steuerkonten verglichen (`tax_accounts`, Seite standardmäßig Haben). Der Satz eines Grundlagenkontos ist der Satz seiner Regel oder, wenn sie keinen trägt, der Satz der Kennzahl im Vordruck. Eine Verprobung eines Erwerbs oder einer Leistung, deren Steuer das Unternehmen selbst schuldet, kann eine Kennzahl für die Bemessungsgrundlage ohne Grundlagenkonto nennen (`derived_base`): Bucht ein Beleg Steuer auf ihre Steuerkonten, aber nichts auf ihre Grundlagenkonten, geht seine Bemessungsgrundlage in diese Kennzahl, siehe [Bemessungsgrundlage ohne Grundlagenkonto](#bemessungsgrundlage-ohne-grundlagenkonto). `derived_rate(check)` und `base_side(check)` nennen Satz und Seite dieser Grundlage, die ihrer Grundlagenkonten.
- **`Mapping`** gehört zu genau einem Kontenrahmen und einem Jahr des Vordrucks (`year`, ohne Angabe das neueste) und enthält Regeln, Verprobungen und beobachtete Konten (`watched`). Beobachtet werden Konten, die zur Voranmeldung gehören oder gehören können, für die es aber noch keine Zuordnung gibt. Jedes beobachtete Konto (`WatchedAccount`) hat eine Stufe (`WatchLevel`): „Sperrt“ (`BLOCKING`) hält die Meldung an, sobald das Konto einen Saldo hat, „Hinweis“ (`HINT`) gibt dann nur einen Hinweis. Eine bloße Kontonummer wird auf der Stufe „Sperrt“ beobachtet, `watched_at(level)` nennt die Konten einer Stufe. `has_place(number)` sagt, ob ein Konto einen Platz hat: eine Regel, als Steuerkonto eine Verprobung oder einen Eintrag unter den beobachteten Konten. `for_year(year)` prüft dieselben Regeln gegen den Vordruck eines anderen Jahres, `default_mapping(chart, year)` liefert die Vorgabe eines Kontenrahmens für das Jahr des Zeitraums.

Eine Zuordnung prüft sich beim Anlegen selbst. Einen `MappingError` gibt es bei:

- einer Kontonummer, die kein nicht leerer Text ohne Leerzeichen am Rand ist, in Regeln, Verprobungen und beobachteten Konten,
- einer unbekannten Kennzahl, einer Kennzahl ohne Betrag (Kennzeichen, Datum, Schlüssel) oder Kz 83, die nur berechnet wird,
- einem doppelt zugeordneten Konto,
- einem Steuersatz an einer Regel, deren Kennzahl keine eigene Steuer-Kennzahl hat, etwa Kz 81 oder 66, oder einem Satz, der nicht endlich oder nicht zwischen 0 und 100 liegt,
- einer Bemessungsgrundlage mit eigener Steuer-Kennzahl (etwa Kz 46), deren Regeln teils mit, teils ohne Steuersatz sind, oder deren Steuer-Kennzahl nichts zufließt, weil weder die Regeln einen Satz tragen noch ein Steuerkonto der Steuer-Kennzahl zugeordnet ist,
- einer Verprobung ohne Bezeichnung, ohne Grundlagen- oder Steuerkonten, mit einem Grundlagenkonto ohne Regel oder ohne Steuersatz, mit einem Steuerkonto, das schon eine andere Verprobung prüft, oder mit einem Steuerkonto, das zugleich einer Kennzahl zugeordnet ist,
- einer Kennzahl für die Bemessungsgrundlage ohne Grundlagenkonto, die keine von Kz 89, 93, 95, 94, 46, 73 und 84 ist (`DERIVED_BASE_KENNZAHLEN`), deren Verprobung ein Grundlagenkonto außerhalb der Abschnitte C und D des Vordrucks (Zeilen 24 bis 32) hat, deren Grundlagenkonten zwei Sätze oder zwei Seiten tragen, deren gesetzlicher Satz nicht der Satz der Grundlagenkonten ist oder deren Steuer-Kennzahl schon ein Steuerkonto zugeordnet ist,
- einem beobachteten Konto, das zugleich zugeordnet oder verprobt ist oder zweimal beobachtet wird, auch auf zwei Stufen.

Ein Jahr, das keine ganze Zahl ist, ergibt einen `TypeError`. Für ein Jahr ohne Katalog gibt es stattdessen einen `UnknownYearError`.

Jede Firma passt die Vorgabe ihres Kontenrahmens in ihrer Kontenzuordnung an; „Vorgaben aktualisieren“ übernimmt später nur die Änderungen der Vorgaben und lässt ihre eigenen stehen, siehe [Einrichtung](einrichtung.md#vorgaben-aktualisieren). Die Zuordnung arbeitet nur mit Kontonummern. Jeder andere Kontenrahmen, auch ein eigener, funktioniert deshalb, solange seine Konten Nummern tragen und eine Zuordnung dafür angelegt ist. Eine eigene Zuordnung darf die Steuer eines Paars wie Kz 46 und 47 auch direkt einem Steuerkonto zuordnen, statt sie abzuleiten.

### So rechnet `calculate()`

[`calculation.py`](../steuerbote/ustva/calculation.py) bekommt die Buchungszeilen eines Zeitraums, eine Zeile je Buchung und Konto, in Firmenwährung und in Cent, dazu eine Zuordnung. Was nicht zum Umsatz des Zeitraums gehört, lässt der Aufrufer weg: Buchungen, die ERPNext als storniert kennzeichnet, Eröffnungs- und Abschlussbuchungen und die Buchungen, mit denen die Steuerkonten gegenüber dem Finanzamt ausgeglichen werden. Einen stornierten Beleg liest die Voranmeldung mit seiner Gegenbuchung am Datum des Belegs, mit und ohne „Unveränderliches Hauptbuch aktivieren“ in den Buchhaltungseinstellungen, siehe [Stornierte Belege](#stornierte-belege).

1. Soll, Haben und die Zahl der Buchungen werden je Konto summiert, dazu je Konto und Beleg, soweit die Zeilen einen Beleg nennen.
2. Jedes zugeordnete Konto gibt seinen Saldo auf seiner Seite an seine Kennzahl. Trägt die Regel einen Steuersatz, geht zusätzlich die Steuer an die Steuer-Kennzahl: je Beleg Saldo × Satz, auf Cent gerundet, über alle Belege summiert. Konten ohne Regel, etwa Bankkonten, gehen nicht ein.
3. Bucht ein Beleg Steuer auf die Steuerkonten einer Verprobung mit `derived_base`, aber nichts auf ihre Grundlagenkonten, geht seine Bemessungsgrundlage in diese Kennzahl, ihre Steuer wie in Schritt 2 je Beleg in die Steuer-Kennzahl, siehe [Bemessungsgrundlage ohne Grundlagenkonto](#bemessungsgrundlage-ohne-grundlagenkonto).
4. Beträge ohne Konto kommen über `extra_values` dazu, etwa die Sondervorauszahlung in Kz 39. Unbekannte Kennzahlen, Kennzahlen ohne Betrag und Kz 83 werden abgelehnt.
5. Kennzahlen mit dem Betrag null entfallen. Jede andere hat ihren genauen Betrag (`amount`) und den gemeldeten Wert (`reported`) nach den Rundungsregeln.
6. Die Summen folgen dem Vordruck: Zeile 37 (`output_tax`), Zeilen 38 bis 44 (`input_tax`), Zeile 45 (`remaining_tax`), Zeilen 46 und 47 (`other_tax`), Zeile 48 (`prepayment`) und Kz 39 (`sondervorauszahlung`). Kz 83 ist Zeile 48 abzüglich Kz 39, auf Cent gerundet, und immer dabei.
7. Jede Verprobung ergibt ein `CheckResult` mit berechneter und gebuchter Steuer, Zahl der Buchungen, Toleranz, Differenz (gebucht minus berechnet), der Liste der abweichenden Belege (`deviations`, je Beleg berechnete und gebuchte Steuer) und den abgeleiteten Bemessungsgrundlagen (`derived`, zusammen `derived_base`), deren Steuer als berechnete Steuer zählt. `passed` ist wahr, wenn kein Beleg abweicht.
8. `unmapped` nennt die beobachteten Konten der Stufe „Sperrt“ mit Saldo, `hinted` die der Stufe „Hinweis“ mit Saldo, jeweils mit Soll und Haben des Zeitraums (`AccountBalance`). Keines davon geht in eine Kennzahl ein. `ready` ist erst wahr, wenn kein Konto der Stufe „Sperrt“ einen Saldo hat und alle Verprobungen aufgehen; ein Saldo auf der Stufe „Hinweis“ ändert daran nichts und ergibt an der Meldung den Hinweis `KONTO-BEOBACHTET` (siehe [Vorperiodenvergleich und Hinweise](architektur.md#vorperiodenvergleich-und-hinweise)).

Konten ohne Regel, die auch nicht beobachtet werden, fehlen in der Meldung, ohne dass ein Fehler entsteht. Für die Konten der Steuervorlagen einer Firma gibt es deshalb die [Prüfung der Steuervorlagen](#prüfung-der-steuervorlagen).

### Vorgaben

[`defaults.py`](../steuerbote/ustva/defaults.py) bringt Vorgaben für SKR03 und SKR04 mit. Sie decken drei Nummernkreise ab: die DATEV-Kontenrahmen in der Ausgabe für 2026, die Kontonummern der Vorlagen für SKR03 und SKR04, die ERPNext selbst mitbringt (`de_kontenplan_SKR03.json` und `de_kontenplan_SKR04.json`, Version 16), und Kontonummern aus verbreiteten SKR03-Varianten, die in der DATEV-Ausgabe 2026 nicht mehr stehen oder dort kein „U“ tragen (ältere DATEV-Ausgaben und Vorlagen von ERP-Systemen). Eine Firma, die mit einer solchen Vorlage angelegt ist, bucht auf deren Nummern, und einige davon führt der Kontenrahmen 2026 nicht mehr oder hält sie frei. Jedes Konto, das der Kontenrahmen an die Umsatzsteuer weitergibt, jedes Umsatzsteuerkonto einer Vorlage von ERPNext und jede dieser SKR03-Nummern hat darin genau einen Platz:

- **Zugeordnet:** Das Konto geht in die Kennzahl, die sich aus seiner Bezeichnung eindeutig ergibt. Dazu gehören auch die Vorsteuerkonten und die Konten für Kz 63, 65 und 69. Ein Forderungsverlust mindert die Bemessungsgrundlage und meldet die Minderung zusätzlich in Kz 50; die Tabellen zeigen das als „81, zusätzlich Kz 50“, und in Kz 50 geht der Saldo im Soll.
- **Verprobt:** Das Umsatzsteuerkonto zu einer Bemessungsgrundlage wird nie zugeordnet. Die Steuer folgt aus dem Grundlagenkonto, mit dem Satz der Kennzahl oder, bei § 13b UStG und bei neuen Fahrzeugen, mit dem Satz, den das Konto laut Bezeichnung trägt. Das gebuchte Steuerkonto wird dagegen verprobt.
- **Beobachtet:** Das Konto gehört zur Voranmeldung, seine Kennzahl ist aber noch nicht entschieden. Hat es im Zeitraum einen Saldo, ist die Meldung nicht bereit. Konten, deren Saldo nur in manchen Fällen in die Voranmeldung gehört, beobachten die Vorgaben auf der Stufe „Hinweis“: Ein Saldo darauf ergibt einen Hinweis, und die Meldung bleibt bereit (siehe [Beobachtete Konten mit Hinweis](#beobachtete-konten-mit-hinweis)).
- **Bewusst ohne Kennzahl:** Die Voranmeldung hat für das Konto keine Kennzahl, etwa für Zahlungen an das Finanzamt, für Umsatzsteuer aus dem OSS-Verfahren oder für einen Einkauf im Inland, von dem nur die Vorsteuer gemeldet wird. Diese Konten stehen in `SKR03_IGNORED` und `SKR04_IGNORED` und gehören nicht zur Zuordnung.

Ein Kontenbereich wie 8400 bis 8409 fasst Konten gleichen Zwecks zusammen. Die Kontenrahmen drucken ihn als „-09“ unter seinem ersten Konto und sagen: „Kontenbereiche werden nur weitergegeben, wenn sie im Standardkontenrahmen ausgewiesen sind (z. B. AM 8400-09)“. Jedes Konto eines Bereichs hat den Platz seines ersten Kontos. `SKR03_RANGES` und `SKR04_RANGES` führen die Bereiche, die Tabellen zeigen sie als „8400 bis 8409“. Bezeichnungen mit dem Zusatz „(ERPNext)“ stammen aus der Vorlage von ERPNext, solche mit dem Zusatz „(SKR03-Variante)“ aus einer verbreiteten SKR03-Variante, weil der Kontenrahmen 2026 die Nummer nicht oder ohne Bezeichnung führt.

[`test_completeness.py`](../steuerbote/ustva/tests/test_completeness.py) setzt das durch: Jedes Konto, das in der Spalte „Programmverbindung“ ein „U“ trägt (Weitergabe an das Programm Umsatzsteuererklärung), jedes Steuerkonto mit der Funktion S oder F in den Bereichen der Vor- und Umsatzsteuer (SKR03 15xx und 17xx, SKR04 14xx und 38xx), jedes Konto ihrer Kontenbereiche, jedes Umsatzsteuerkonto der Vorlagen von ERPNext und jede Nummer aus den SKR03-Varianten hat genau einen dieser Plätze, die Nummern der Varianten genau den, den ihre Bezeichnung ergibt. Die Kontonummern stehen in [`datev_2026.py`](../steuerbote/ustva/tests/fixtures/datev_2026.py), [`erpnext_v16.py`](../steuerbote/ustva/tests/fixtures/erpnext_v16.py) mit den Stichwörtern, nach denen die Konten der Vorlagen ausgewählt sind, und [`skr03_legacy_numbers.py`](../steuerbote/ustva/tests/fixtures/skr03_legacy_numbers.py). Wenige Konten aus keiner dieser Quellen haben trotzdem einen Platz: etwa 8320 bis 8329 für Lieferungen, die im anderen EU-Land steuerpflichtig sind, und 8331 für elektronische Dienstleistungen, beide in Kz 45; 3551 und 1390 (SKR04: 5551), die der Kontenrahmen 2026 ohne „U“ führt, bewusst ohne Kennzahl; und die sonstigen betrieblichen Erträge auf der Stufe „Hinweis“ (siehe [Beobachtete Konten mit Hinweis](#beobachtete-konten-mit-hinweis)). Der Test führt sie mit Grund auf. Kennzeichnet eine neue Ausgabe des Kontenrahmens ein weiteres Konto mit „U“, schlägt der Test fehl, bis das Konto seinen Platz hat.

An echten Buchungen geprüft sind die Konten des Testfalls `VerifiedMonthTest` (siehe [Beispiel](#beispiel)). Alle anderen Zuordnungen folgen den Bezeichnungen. Die Vorgabe SKR04 bildet SKR03 Rolle für Rolle nach: gleiche Kennzahl, gleiche Seite, gleicher Steuersatz, gleiche Verprobungen. Zu 8630 hat SKR04 kein Konto, zu 3852 aus der Vorlage von ERPNext hat SKR03 keines, siehe [Vorgabe SKR04](#vorgabe-skr04). [`test_defaults.py`](../steuerbote/ustva/tests/test_defaults.py) hält jede Regel, jede Verprobung und die Listen der beobachteten und der bewusst nicht zugeordneten Konten beider Vorgaben fest und prüft die Spiegelung. [`test_docs.py`](../steuerbote/ustva/tests/test_docs.py) prüft, dass die Tabellen auf dieser Seite genau den Code zeigen.

Die Vorgaben haben einen Stand aus Kontenrahmen, Ausgabe des DATEV-Kontenrahmens und Revision, heute „SKR03 2026.3“ und „SKR04 2026.3“ (`DATEV_EDITION`, `REVISION` und `defaults_version` in `defaults.py`). Jede Änderung der Vorgaben erhöht `REVISION`; `DefaultsVersionTest` in `test_defaults.py` hält die SHA-256-Summe des Inhalts jedes Stands fest und schlägt fehl, bis die Revision steigt und die Summe des neuen Stands eingetragen ist. „Vorgaben laden“ merkt sich an der Kontenzuordnung den Stand und die Zeilen, die er gab; „Vorgaben aktualisieren“ unterscheidet damit Änderungen der Vorgaben von eigenen, siehe [Einrichtung](einrichtung.md#vorgaben-aktualisieren). Revision 2 gibt den Verprobungen der Erwerbe und des § 13b UStG die Kennzahl für die Bemessungsgrundlage ohne Grundlagenkonto; einer Kontenzuordnung mit Revision 1 schlägt „Vorgaben aktualisieren“ diese Änderung je Verprobung vor. Revision 3 gibt den Verprobungen des § 13b UStG Kz 46 für die Belege eines Lieferanten mit Sitz im übrigen Gemeinschaftsgebiet (`DERIVED_EU`), siehe [Kz 46 oder Kz 84: der Sitz des Leistenden](#kz-46-oder-kz-84-der-sitz-des-leistenden); auch diese Änderung schlägt „Vorgaben aktualisieren“ je Verprobung angehakt vor.

### Vorgabe SKR03

| Konto | Bezeichnung laut Kontenrahmen 2026 | Kz | Seite |
|---|---|---|---|
| 8400 bis 8409 | Erlöse 19 % USt | 81 | Haben |
| 8410 bis 8419 | Erlöse 19 % USt | 81 | Haben |
| 8449 | Erlöse aus im Inland steuerpflichtigen elektronischen Dienstleistungen 19 % USt | 81 | Haben |
| 2752 | Erlöse aus Vermietung und Verpachtung 19 % USt | 81 | Haben |
| 8519 | Provisionsumsätze 19 % USt | 81 | Haben |
| 8640 bis 8644 | Sonstige Erträge betrieblich und regelmäßig 19 % USt | 81 | Haben |
| 8801 bis 8806 | Erlöse aus Verkäufen Sachanlagevermögen 19 % USt (bei Buchverlust) | 81 | Haben |
| 8820 bis 8825 | Erlöse aus Verkäufen Sachanlagevermögen 19 % USt (bei Buchgewinn) | 81 | Haben |
| 8850 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens 19 % USt für § 4 Abs. 3 Satz 4 EStG | 81 | Haben |
| 8595 | Sachbezüge 19 % USt (Waren) | 81 | Haben |
| 8611 | Verrechnete sonstige Sachbezüge aus Fahrzeug-Gestellung 19 % USt | 81 | Haben |
| 8613 | Verrechnete sonstige Sachbezüge 19 % USt | 81 | Haben |
| 8910 bis 8913 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 19 % USt | 81 | Haben |
| 8920 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt | 81 | Haben |
| 8921 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Fahrzeug-Nutzung) | 81 | Haben |
| 8922 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Telefon-Nutzung) | 81 | Haben |
| 8925 bis 8927 | Unentgeltliche Erbringung einer sonstigen Leistung 19 % USt | 81 | Haben |
| 8935 bis 8937 | Unentgeltliche Zuwendung von Gegenständen 19 % USt | 81 | Haben |
| 8940 bis 8943 | Unentgeltliche Zuwendung von Waren 19 % USt | 81 | Haben |
| 8720 bis 8721 | Erlösschmälerungen 19 % USt | 81 | Haben |
| 8760 bis 8761 | Gewährte Boni 19 % USt | 81 | Haben |
| 8790 bis 8791 | Gewährte Rabatte 19 % USt | 81 | Haben |
| 8736 | Gewährte Skonti 19 % USt | 81 | Haben |
| 2406 | Forderungsverluste 19 % USt (übliche Höhe) | 81, zusätzlich Kz 50 | Haben |
| 2436 | Forderungsverluste 19 % USt (soweit unüblich hoch) | 81, zusätzlich Kz 50 | Haben |
| 1718 | Erhaltene, versteuerte Anzahlungen 19 % USt (Verbindlichkeiten) | 81 | Haben |
| 8196 | Erlöse aus Geldspielautomaten 19 % USt (SKR03-Variante) | 81 | Haben |
| 8579 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten 19 % USt (SKR03-Variante) | 81 | Haben |
| 8315 bis 8319 | Erlöse aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 8726 | Erlösschmälerungen aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 2408 | Forderungsverluste aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt (übliche Höhe) | 81, zusätzlich Kz 50 | Haben |
| 8748 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 8300 bis 8309 | Erlöse 7 % USt | 86 | Haben |
| 8334 | Erlöse 7 % USt | 86 | Haben |
| 8630 bis 8634 | Sonstige Erträge betrieblich und regelmäßig 7 % USt | 86 | Haben |
| 8591 | Sachbezüge 7 % USt (Waren) | 86 | Haben |
| 8915 bis 8916 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | Haben |
| 8917 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | Haben |
| 8930 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | Haben |
| 8931 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | Haben |
| 8932 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | Haben |
| 8933 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | Haben |
| 8945 bis 8946 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | Haben |
| 8947 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | Haben |
| 8710 bis 8711 | Erlösschmälerungen 7 % USt | 86 | Haben |
| 8750 bis 8751 | Gewährte Boni 7 % USt | 86 | Haben |
| 8780 bis 8781 | Gewährte Rabatte 7 % USt | 86 | Haben |
| 8731 | Gewährte Skonti 7 % USt | 86 | Haben |
| 2401 | Forderungsverluste 7 % USt (übliche Höhe) | 86, zusätzlich Kz 50 | Haben |
| 2431 | Forderungsverluste 7 % USt (soweit unüblich hoch) | 86, zusätzlich Kz 50 | Haben |
| 1711 | Erhaltene, versteuerte Anzahlungen 7 % USt (Verbindlichkeiten) | 86 | Haben |
| 8516 | Provisionsumsätze 7 % USt (SKR03-Variante) | 86 | Haben |
| 8576 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten 7 % USt (SKR03-Variante) | 86 | Haben |
| 8310 bis 8314 | Erlöse aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 8725 | Erlösschmälerungen aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 2403 | Forderungsverluste aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt (übliche Höhe) | 86, zusätzlich Kz 50 | Haben |
| 8746 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 8290 | Erlöse 0 % USt | 87 | Haben |
| 8719 | Erlösschmälerungen 0 % USt | 87 | Haben |
| 8734 | Gewährte Skonti 0 % USt | 87 | Haben |
| 1714 | Erhaltene, versteuerte Anzahlungen 0 % USt (Verbindlichkeiten) | 87 | Haben |
| 8100 bis 8104 | Steuerfreie Umsätze § 4 Nr. 8 ff. UStG | 48 | Haben |
| 8105 | Steuerfreie Umsätze nach § 4 Nr. 12 UStG (Vermietung und Verpachtung) | 48 | Haben |
| 8160 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend, § 4 UStG | 48 | Haben |
| 8165 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend | 48 | Haben |
| 8192 | Steuerfreie Erlöse Kleinunternehmer nach § 19 Abs. 1 UStG | 48 | Haben |
| 2751 | Erlöse aus Vermietung und Verpachtung, umsatzsteuerfrei § 4 Nr. 12 UStG | 48 | Haben |
| 8514 | Provisionsumsätze, steuerfrei § 4 Nr. 8 ff. UStG | 48 | Haben |
| 8851 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG | 48 | Haben |
| 8701 | Erlösschmälerungen für steuerfreie Umsätze nach § 4 Nr. 8 ff. UStG | 48 | Haben |
| 8703 | Erlösschmälerungen für sonstige steuerfreie Umsätze ohne Vorsteuerabzug | 48 | Haben |
| 8707 | Erlösschmälerungen für steuerfreie Umsätze nach § 19 Abs. 1 UStG | 48 | Haben |
| 8609 | Sonstige Erträge betrieblich und regelmäßig, steuerfrei § 4 Nr. 8 ff. UStG | 48 | Haben |
| 8852 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG und § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG | 48 | Haben |
| 8195 | Erlöse als Kleinunternehmer nach § 19 Abs. 1 UStG (SKR03-Variante) | 48 | Haben |
| 8574 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten, steuerfrei § 4 Nr. 8 ff. UStG (SKR03-Variante) | 48 | Haben |
| 8120 | Steuerfreie Umsätze nach § 4 Nr. 1a UStG | 43 | Haben |
| 8140 | Steuerfreie Umsätze Offshore usw. | 43 | Haben |
| 8150 | Sonstige steuerfreie Umsätze (z. B. § 4 Nr. 2 bis 7 UStG) | 43 | Haben |
| 8807 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchverlust) | 43 | Haben |
| 8827 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchgewinn) | 43 | Haben |
| 8515 | Provisionsumsätze, steuerfrei § 4 Nr. 5 UStG | 43 | Haben |
| 8625 bis 8629 | Sonstige betriebliche Erträge, steuerfrei z. B. § 4 Nr. 2 bis 7 UStG | 43 | Haben |
| 8702 | Erlösschmälerungen für steuerfreie Umsätze nach § 4 Nr. 2 bis 7 UStG | 43 | Haben |
| 8704 | Erlösschmälerungen für sonstige steuerfreie Umsätze mit Vorsteuerabzug | 43 | Haben |
| 8705 | Erlösschmälerungen aus steuerfreien Umsätzen § 4 Nr. 1a UStG | 43 | Haben |
| 8194 | Umsatzerlöse aus Reiseleistungen § 25 Abs. 2 UStG, steuerfrei | 43 | Haben |
| 8575 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten, steuerfrei § 4 Nr. 5 UStG (SKR03-Variante) | 43 | Haben |
| 8125 | Steuerfreie innergemeinschaftliche Lieferungen nach § 4 Nr. 1b UStG | 41 | Haben |
| 8808 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1b UStG (bei Buchverlust) | 41 | Haben |
| 8828 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1b UStG (bei Buchgewinn) | 41 | Haben |
| 8724 | Erlösschmälerungen aus steuerfreien innergemeinschaftlichen Lieferungen | 41 | Haben |
| 2402 | Forderungsverluste aus steuerfreien EU-Lieferungen (übliche Höhe) | 41 | Haben |
| 8743 | Gewährte Skonti aus steuerfreien innergemeinschaftlichen Lieferungen § 4 Nr. 1b UStG | 41 | Haben |
| 8135 | Steuerfreie innergemeinschaftliche Lieferungen von Neufahrzeugen an Abnehmer ohne USt-Id-Nr. | 44 | Haben |
| 8130 | Lieferungen des ersten Abnehmers bei innergemeinschaftlichen Dreiecksgeschäften § 25b Abs. 2 UStG | 42 | Haben |
| 8706 | Erlösschmälerungen für steuerfreie innergemeinschaftliche Dreiecksgeschäfte nach § 25b Abs. 2 und 4 UStG | 42 | Haben |
| 8338 | Erlöse aus im Drittland steuerbaren Leistungen, im Inland nicht steuerbare Umsätze | 45 | Haben |
| 8320 bis 8329 | Erlöse aus im anderen EU-Land steuerpflichtigen Lieferungen, im Inland nicht steuerbar | 45 | Haben |
| 8339 | Erlöse aus im anderen EU-Land steuerbaren Leistungen, im Inland nicht steuerbare Umsätze | 45 | Haben |
| 8331 | Erlöse aus im anderen EU-Land steuerpflichtigen elektronischen Dienstleistungen | 45 | Haben |
| 8727 | Erlösschmälerungen aus im anderen EU-Land steuerpflichtigen Lieferungen | 45 | Haben |
| 8336 | Erlöse aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen, für die der Leistungsempfänger die Umsatzsteuer schuldet | 21 | Haben |
| 8742 | Gewährte Skonti aus Erlösen aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen, für die der Leistungsempfänger die Umsatzsteuer schuldet | 21 | Haben |
| 8337 | Erlöse aus Leistungen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 8335 | Erlöse aus Lieferungen von Mobilfunkgeräten, Tablet-Computern, Spielekonsolen und integrierten Schaltkreisen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 8741 | Gewährte Skonti aus Leistungen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 8738 | Gewährte Skonti aus Lieferungen von Mobilfunkgeräten etc., für die der Leistungsempfänger die Umsatzsteuer nach § 13b Abs. 2 Nr. 10 UStG schuldet | 60 | Haben |
| 3425 bis 3429 | Innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3725 | Nachlässe aus innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3718 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3062 bis 3063 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3741 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3748 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3420 bis 3424 | Innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3724 | Nachlässe aus innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3717 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3060 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3743 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3746 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3435 | Innergemeinschaftlicher Erwerb ohne Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3430 | Innergemeinschaftlicher Erwerb ohne Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3066 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb ohne Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3067 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb ohne Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3440 | Innergemeinschaftlicher Erwerb von Neufahrzeugen von Lieferanten ohne USt-Id-Nr. 19 % Vorsteuer und 19 % Umsatzsteuer | 94, Steuer 19 % in Kz 96 | Soll |
| 3550 | Steuerfreier innergemeinschaftlicher Erwerb | 91 | Soll |
| 3123 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 46, Steuer 19 % in Kz 47 | Soll |
| 3143 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 46, Steuer 19 % in Kz 47 | Soll |
| 3113 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 46, Steuer 7 % in Kz 47 | Soll |
| 3133 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 46, Steuer 7 % in Kz 47 | Soll |
| 3125 bis 3126 | Leistungen eines im Ausland ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 3145 bis 3146 | Leistungen eines im Ausland ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 3120 bis 3121 | Bauleistungen eines im Inland ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 3140 bis 3141 | Bauleistungen eines im Inland ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 3115 | Leistungen eines im Ausland ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 3135 | Leistungen eines im Ausland ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 3110 | Bauleistungen eines im Inland ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 3130 | Bauleistungen eines im Inland ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 1570 | Abziehbare Vorsteuer | 66 | Soll |
| 1576 | Abziehbare Vorsteuer 19 % | 66 | Soll |
| 1571 | Abziehbare Vorsteuer 7 % | 66 | Soll |
| 1573 | Vorsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 66 | Soll |
| 1585 | Abziehbare Vorsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager | 66 | Soll |
| 1574 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb 19 % | 61 | Soll |
| 1572 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb | 61 | Soll |
| 1584 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen von Lieferanten ohne USt-Id-Nr. | 61 | Soll |
| 1588 | Entstandene Einfuhrumsatzsteuer | 62 | Soll |
| 1577 | Abziehbare Vorsteuer nach § 13b UStG 19 % | 67 | Soll |
| 1578 | Abziehbare Vorsteuer nach § 13b UStG | 67 | Soll |
| 1587 | Vorsteuer nach allgemeinen Durchschnittssätzen UStVA Kz. 63 (SKR03-Variante) | 63 | Soll |
| 1528 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 2 UStG | 64 | Soll |
| 1529 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 2 UStG | 64 | Soll |
| 1556 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | Soll |
| 1557 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | Soll |
| 1558 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | Soll |
| 1559 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | Soll |
| 1782 | Nachsteuer, UStVA Kz. 65 | 65 | Haben |
| 1783 | In Rechnung unrichtig oder unberechtigt ausgewiesene Steuerbeträge, UStVA Kz. 69 | 69 | Haben |
| 1794 | Umsatzsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 69 | Haben |

### Vorgabe SKR04

| Konto | Bezeichnung laut Kontenrahmen 2026 | Kz | Seite |
|---|---|---|---|
| 4400 bis 4409 | Erlöse 19 % USt | 81 | Haben |
| 4410 bis 4419 | Erlöse 19 % USt | 81 | Haben |
| 4449 | Erlöse aus im Inland steuerpflichtigen elektronischen Dienstleistungen 19 % USt | 81 | Haben |
| 4862 | Erlöse aus Vermietung und Verpachtung 19 % USt | 81 | Haben |
| 4569 | Provisionsumsätze 19 % USt | 81 | Haben |
| 4836 | Sonstige Erträge betrieblich und regelmäßig 19 % USt | 81 | Haben |
| 6885 | Erlöse aus Verkäufen Sachanlagevermögen 19 % USt (bei Buchverlust) | 81 | Haben |
| 4845 | Erlöse aus Verkäufen Sachanlagevermögen 19 % USt (bei Buchgewinn) | 81 | Haben |
| 4865 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens 19 % USt für § 4 Abs. 3 Satz 4 EStG | 81 | Haben |
| 4945 | Sachbezüge 19 % USt (Waren) | 81 | Haben |
| 4947 | Verrechnete sonstige Sachbezüge aus Fahrzeug-Gestellung 19 % USt | 81 | Haben |
| 4948 | Verrechnete sonstige Sachbezüge 19 % USt | 81 | Haben |
| 4620 bis 4626 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 19 % USt | 81 | Haben |
| 4640 bis 4644 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt | 81 | Haben |
| 4645 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Fahrzeug-Nutzung) | 81 | Haben |
| 4646 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Telefon-Nutzung) | 81 | Haben |
| 4660 bis 4666 | Unentgeltliche Erbringung einer sonstigen Leistung 19 % USt | 81 | Haben |
| 4686 bis 4687 | Unentgeltliche Zuwendung von Gegenständen 19 % USt | 81 | Haben |
| 4680 bis 4684 | Unentgeltliche Zuwendung von Waren 19 % USt | 81 | Haben |
| 4720 bis 4721 | Erlösschmälerungen 19 % USt | 81 | Haben |
| 4760 bis 4761 | Gewährte Boni 19 % USt | 81 | Haben |
| 4790 bis 4791 | Gewährte Rabatte 19 % USt | 81 | Haben |
| 4736 | Gewährte Skonti 19 % USt | 81 | Haben |
| 6936 | Forderungsverluste 19 % USt (übliche Höhe) | 81, zusätzlich Kz 50 | Haben |
| 6286 | Forderungsverluste 19 % USt (soweit unüblich hoch) | 81, zusätzlich Kz 50 | Haben |
| 3272 | Erhaltene, versteuerte Anzahlungen 19 % USt (Verbindlichkeiten) | 81 | Haben |
| 4186 | Erlöse aus Geldspielautomaten 19 % USt (ERPNext) | 81 | Haben |
| 4579 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten 19% USt (ERPNext) | 81 | Haben |
| 4315 bis 4319 | Erlöse aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 4726 | Erlösschmälerungen aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 6938 | Forderungsverluste aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt (übliche Höhe) | 81, zusätzlich Kz 50 | Haben |
| 4748 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 4300 bis 4309 | Erlöse 7 % USt | 86 | Haben |
| 4334 | Erlöse 7 % USt | 86 | Haben |
| 4941 | Sachbezüge 7 % USt (Waren) | 86 | Haben |
| 4610 bis 4615 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | Haben |
| 4616 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | Haben |
| 4630 bis 4635 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | Haben |
| 4636 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | Haben |
| 4650 bis 4655 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | Haben |
| 4656 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | Haben |
| 4670 bis 4675 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | Haben |
| 4676 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | Haben |
| 4710 bis 4711 | Erlösschmälerungen 7 % USt | 86 | Haben |
| 4750 bis 4751 | Gewährte Boni 7 % USt | 86 | Haben |
| 4780 bis 4781 | Gewährte Rabatte 7 % USt | 86 | Haben |
| 4731 | Gewährte Skonti 7 % USt | 86 | Haben |
| 6931 | Forderungsverluste 7 % USt (übliche Höhe) | 86, zusätzlich Kz 50 | Haben |
| 6281 | Forderungsverluste 7 % USt (soweit unüblich hoch) | 86, zusätzlich Kz 50 | Haben |
| 3260 | Erhaltene, versteuerte Anzahlungen 7 % USt (Verbindlichkeiten) | 86 | Haben |
| 4566 | Provisionsumsätze 7% USt (ERPNext) | 86 | Haben |
| 4576 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten 7% USt (ERPNext) | 86 | Haben |
| 4310 bis 4314 | Erlöse aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 4725 | Erlösschmälerungen aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 6933 | Forderungsverluste aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt (übliche Höhe) | 86, zusätzlich Kz 50 | Haben |
| 4746 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 4290 | Erlöse 0 % USt | 87 | Haben |
| 4719 | Erlösschmälerungen 0 % USt | 87 | Haben |
| 4734 | Gewährte Skonti 0 % USt | 87 | Haben |
| 3264 | Erhaltene, versteuerte Anzahlungen 0 % USt (Verbindlichkeiten) | 87 | Haben |
| 4100 bis 4104 | Steuerfreie Umsätze § 4 Nr. 8 ff. UStG | 48 | Haben |
| 4105 | Steuerfreie Umsätze nach § 4 Nr. 12 UStG (Vermietung und Verpachtung) | 48 | Haben |
| 4160 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend, § 4 UStG | 48 | Haben |
| 4165 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend | 48 | Haben |
| 4184 | Steuerfreie Erlöse Kleinunternehmer nach § 19 Abs. 1 UStG | 48 | Haben |
| 4861 | Erlöse aus Vermietung und Verpachtung, umsatzsteuerfrei § 4 Nr. 12 UStG | 48 | Haben |
| 4564 | Provisionsumsätze, steuerfrei § 4 Nr. 8 ff. UStG | 48 | Haben |
| 4866 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG | 48 | Haben |
| 4701 | Erlösschmälerungen für steuerfreie Umsätze nach § 4 Nr. 8 ff. UStG | 48 | Haben |
| 4703 | Erlösschmälerungen für sonstige steuerfreie Umsätze ohne Vorsteuerabzug | 48 | Haben |
| 4707 | Erlösschmälerungen für steuerfreie Umsätze nach § 19 Abs. 1 UStG | 48 | Haben |
| 4841 | Sonstige Erträge betrieblich und regelmäßig, steuerfrei § 4 Nr. 8 ff. UStG | 48 | Haben |
| 4867 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG, § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG | 48 | Haben |
| 4185 | Erlöse aus Kleinunternehmer i. S. d. § 19 Abs. 1 UStG (ERPNext) | 48 | Haben |
| 4574 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten, steuerfrei § 4 Nr. 8ff UStG (ERPNext) | 48 | Haben |
| 4120 | Steuerfreie Umsätze nach § 4 Nr. 1a UStG | 43 | Haben |
| 4140 | Steuerfreie Umsätze Offshore etc. | 43 | Haben |
| 4150 | Sonstige steuerfreie Umsätze (z. B. § 4 Nr. 2 bis 7 UStG) | 43 | Haben |
| 6884 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchverlust) | 43 | Haben |
| 4844 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchgewinn) | 43 | Haben |
| 4565 | Provisionsumsätze, steuerfrei § 4 Nr. 5 UStG | 43 | Haben |
| 4842 | Sonstige betriebliche Erträge, steuerfrei z. B. § 4 Nr. 2 bis 7 UStG | 43 | Haben |
| 4702 | Erlösschmälerungen für steuerfreie Umsätze nach § 4 Nr. 2 bis 7 UStG | 43 | Haben |
| 4704 | Erlösschmälerungen für sonstige steuerfreie Umsätze mit Vorsteuerabzug | 43 | Haben |
| 4705 | Erlösschmälerungen aus steuerfreien Umsätzen § 4 Nr. 1a UStG | 43 | Haben |
| 4139 | Umsatzerlöse aus Reiseleistungen § 25 Abs. 2 UStG, steuerfrei | 43 | Haben |
| 4575 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten, steuerfrei § 4 Nr. 5 UStG (ERPNext) | 43 | Haben |
| 4125 | Steuerfreie innergemeinschaftliche Lieferungen nach § 4 Nr. 1b UStG | 41 | Haben |
| 6888 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1b UStG (bei Buchverlust) | 41 | Haben |
| 4848 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1b UStG (bei Buchgewinn) | 41 | Haben |
| 4724 | Erlösschmälerungen aus steuerfreien innergemeinschaftlichen Lieferungen | 41 | Haben |
| 6932 | Forderungsverluste aus steuerfreien EU-Lieferungen (übliche Höhe) | 41 | Haben |
| 4743 | Gewährte Skonti aus steuerfreien innergemeinschaftlichen Lieferungen § 4 Nr. 1b UStG | 41 | Haben |
| 4135 | Steuerfreie innergemeinschaftliche Lieferungen von Neufahrzeugen an Abnehmer ohne Umsatzsteuer-Identifikationsnummer | 44 | Haben |
| 4130 | Lieferungen des ersten Abnehmers bei innergemeinschaftlichen Dreiecksgeschäften § 25b Abs. 2 UStG | 42 | Haben |
| 4706 | Erlösschmälerungen für steuerfreie innergemeinschaftliche Dreiecksgeschäfte nach § 25b Abs. 2 und 4 UStG | 42 | Haben |
| 4338 | Erlöse aus im Drittland steuerbaren Leistungen, im Inland nicht steuerbare Umsätze | 45 | Haben |
| 4320 bis 4329 | Erlöse aus im anderen EU-Land steuerpflichtigen Lieferungen, im Inland nicht steuerbar | 45 | Haben |
| 4339 | Erlöse aus im anderen EU-Land steuerbaren Leistungen, im Inland nicht steuerbare Umsätze | 45 | Haben |
| 4331 | Erlöse aus im anderen EU-Land steuerpflichtigen elektronischen Dienstleistungen | 45 | Haben |
| 4727 | Erlösschmälerungen aus im anderen EU-Land steuerpflichtigen Lieferungen | 45 | Haben |
| 4336 | Erlöse aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen, für die der Leistungsempfänger die Umsatzsteuer schuldet | 21 | Haben |
| 4742 | Gewährte Skonti aus Erlösen aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen, für die der Leistungsempfänger die Umsatzsteuer schuldet | 21 | Haben |
| 4337 | Erlöse aus Leistungen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 4335 | Erlöse aus Lieferungen von Mobilfunkgeräten, Tablet-Computern, Spielekonsolen und integrierten Schaltkreisen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 4741 | Gewährte Skonti aus Leistungen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 4738 | Gewährte Skonti aus Lieferungen von Mobilfunkgeräten etc., für die der Leistungsempfänger die Umsatzsteuer nach § 13b Abs. 2 Nr. 10 UStG schuldet | 60 | Haben |
| 5425 bis 5429 | Innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5725 | Nachlässe aus innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5718 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5162 bis 5163 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5741 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5748 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5420 bis 5424 | Innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5724 | Nachlässe aus innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5717 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5160 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5743 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5746 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5435 | Innergemeinschaftlicher Erwerb ohne Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5430 | Innergemeinschaftlicher Erwerb ohne Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5166 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb ohne Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5167 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb ohne Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5440 | Innergemeinschaftlicher Erwerb von Neufahrzeugen von Lieferanten ohne Umsatzsteuer-Identifikationsnummer 19 % Vorsteuer und 19 % Umsatzsteuer | 94, Steuer 19 % in Kz 96 | Soll |
| 5550 | Steuerfreier innergemeinschaftlicher Erwerb | 91 | Soll |
| 5923 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 46, Steuer 19 % in Kz 47 | Soll |
| 5943 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 46, Steuer 19 % in Kz 47 | Soll |
| 5913 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 46, Steuer 7 % in Kz 47 | Soll |
| 5933 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 46, Steuer 7 % in Kz 47 | Soll |
| 5925 bis 5926 | Leistungen eines im Ausland ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 5945 bis 5946 | Leistungen eines im Ausland ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 5920 bis 5921 | Bauleistungen eines im Inland ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 5940 bis 5941 | Bauleistungen eines im Inland ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 5915 | Leistungen eines im Ausland ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 5935 | Leistungen eines im Ausland ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 5910 | Bauleistungen eines im Inland ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 5930 | Bauleistungen eines im Inland ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 1400 | Abziehbare Vorsteuer | 66 | Soll |
| 1406 | Abziehbare Vorsteuer 19 % | 66 | Soll |
| 1401 | Abziehbare Vorsteuer 7 % | 66 | Soll |
| 1436 | Vorsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 66 | Soll |
| 1431 | Abziehbare Vorsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager | 66 | Soll |
| 1404 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb 19 % | 61 | Soll |
| 1402 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb | 61 | Soll |
| 1432 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen von Lieferanten ohne USt-Identifikationsnummer | 61 | Soll |
| 1433 | Entstandene Einfuhrumsatzsteuer | 62 | Soll |
| 1407 | Abziehbare Vorsteuer nach § 13b UStG 19 % | 67 | Soll |
| 1408 | Abziehbare Vorsteuer nach § 13b UStG | 67 | Soll |
| 1484 | Vorsteuer nach allgemeinen Durchschnittssätzen UStVA Kz. 63 (ERPNext) | 63 | Soll |
| 1376 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 2 UStG | 64 | Soll |
| 1377 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 2 UStG | 64 | Soll |
| 1396 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | Soll |
| 1397 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | Soll |
| 1398 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | Soll |
| 1399 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | Soll |
| 3832 | Nachsteuer, UStVA Kz. 65 | 65 | Haben |
| 3851 | In Rechnung unrichtig oder unberechtigt ausgewiesene Steuerbeträge, UStVA Kz. 69 | 69 | Haben |
| 3819 | Umsatzsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 69 | Haben |
| 3852 | In Rechnung unrichtig oder unberechtigtausgewiesene Steuerbeträge, UStVA Kz. 69 (ERPNext) | 69 | Haben |

Zu 8630 (Sonstige Erträge betrieblich und regelmäßig 7 % USt) hat SKR04 kein Konto. 4835 heißt dort „Sonstige Erträge betrieblich und regelmäßig“, trägt kein „U“, nimmt Erträge ohne Umsatzsteuer auf und ist das Gegenstück zu SKR03 8605. Es hat deshalb in den Vorgaben keinen Platz. Die Konten 1484, 3852, 4185, 4186, 4566, 4574, 4575, 4576 und 4579 stammen aus der Vorlage von ERPNext. In SKR03 entsprechen ihnen 1587, 8195, 8196, 8516, 8574, 8575, 8576 und 8579 aus verbreiteten SKR03-Varianten; nur 3852 hat in SKR03 kein Gegenstück.

### Verprobungen

Beide Vorgaben verproben die gebuchte Umsatzsteuer auf der Haben-Seite der Steuerkonten:

| Verprobung | Grundlagen SKR03 | Grundlagen SKR04 | Steuerkonto SKR03 / SKR04 | Grundlage ohne Grundlagenkonto | bei Sitz im übrigen Gemeinschaftsgebiet | Bezeichnung des Steuerkontos |
|---|---|---|---|---|---|---|
| Umsatzsteuer 19 % | 8400 bis 8409, 8410 bis 8419, 8449, 2752, 8519, 8640 bis 8644, 8801 bis 8806, 8820 bis 8825, 8850, 8595, 8611, 8613, 8910 bis 8913, 8920, 8921, 8922, 8925 bis 8927, 8935 bis 8937, 8940 bis 8943, 8720 bis 8721, 8760 bis 8761, 8790 bis 8791, 8736, 2406, 2436, 1718, 8196, 8579 | 4400 bis 4409, 4410 bis 4419, 4449, 4862, 4569, 4836, 6885, 4845, 4865, 4945, 4947, 4948, 4620 bis 4626, 4640 bis 4644, 4645, 4646, 4660 bis 4666, 4686 bis 4687, 4680 bis 4684, 4720 bis 4721, 4760 bis 4761, 4790 bis 4791, 4736, 6936, 6286, 3272, 4186, 4579 | 1776 / 3806 | — | — | Umsatzsteuer 19 % |
| Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 19 % | 8315 bis 8319, 8726, 2408, 8748 | 4315 bis 4319, 4726, 6938, 4748 | 1778 / 3808 | — | — | Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 19 % |
| Umsatzsteuer 7 % | 8300 bis 8309, 8334, 8630 bis 8634, 8591, 8915 bis 8916, 8917, 8930, 8931, 8932, 8933, 8945 bis 8946, 8947, 8710 bis 8711, 8750 bis 8751, 8780 bis 8781, 8731, 2401, 2431, 1711, 8516, 8576 | 4300 bis 4309, 4334, 4941, 4610 bis 4615, 4616, 4630 bis 4635, 4636, 4650 bis 4655, 4656, 4670 bis 4675, 4676, 4710 bis 4711, 4750 bis 4751, 4780 bis 4781, 4731, 6931, 6281, 3260, 4566, 4576 | 1771 / 3801 | — | — | Umsatzsteuer 7 % |
| Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 7 % | 8310 bis 8314, 8725, 2403, 8746 | 4310 bis 4314, 4725, 6933, 4746 | 1777 / 3807 | — | — | Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen |
| Umsatzsteuer aus innergemeinschaftlichem Erwerb 19 % | 3425 bis 3429, 3725, 3718, 3062 bis 3063, 3741, 3748 | 5425 bis 5429, 5725, 5718, 5162 bis 5163, 5741, 5748 | 1774 / 3804 | Kz 89 | — | Umsatzsteuer aus innergemeinschaftlichem Erwerb 19 % |
| Umsatzsteuer aus innergemeinschaftlichem Erwerb 7 % | 3420 bis 3424, 3724, 3717, 3060, 3743, 3746 | 5420 bis 5424, 5724, 5717, 5160, 5743, 5746 | 1772 / 3802 | Kz 93 | — | Umsatzsteuer aus innergemeinschaftlichem Erwerb |
| Umsatzsteuer aus innergemeinschaftlichem Erwerb ohne Vorsteuerabzug | 3430, 3435, 3066, 3067 | 5430, 5435, 5166, 5167 | 1779 / 3809 | — | — | Umsatzsteuer aus innergemeinschaftlichem Erwerb ohne Vorsteuerabzug |
| Umsatzsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen | 3440 | 5440 | 1784 / 3834 | Kz 94 | — | Umsatzsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen von Lieferanten ohne Umsatzsteuer-Identifikationsnummer |
| Umsatzsteuer nach § 13b UStG 19 % | 3123, 3143, 3125 bis 3126, 3145 bis 3146, 3120 bis 3121, 3140 bis 3141 | 5923, 5943, 5925 bis 5926, 5945 bis 5946, 5920 bis 5921, 5940 bis 5941 | 1787 / 3837 | Kz 84 | Kz 46 | Umsatzsteuer nach § 13b UStG 19 % |
| Umsatzsteuer nach § 13b UStG 7 % | 3113, 3133, 3115, 3135, 3110, 3130 | 5913, 5933, 5915, 5935, 5910, 5930 | 1785 / 3835 | Kz 84 | Kz 46 | Umsatzsteuer nach § 13b UStG |

Die Spalte „bei Sitz im übrigen Gemeinschaftsgebiet“ nennt die Kennzahl, die die Bemessungsgrundlage eines solchen Belegs statt der vorigen Spalte nimmt, wenn sein Lieferant im übrigen Gemeinschaftsgebiet ansässig ist, siehe [Kz 46 oder Kz 84: der Sitz des Leistenden](#kz-46-oder-kz-84-der-sitz-des-leistenden).

In SKR04 fehlt in der Verprobung „Umsatzsteuer 7 %“ das Gegenstück zu 8630. Die Erwerbe ohne Vorsteuerabzug, auch 3066 und 3067 (SKR04: 5166 und 5167), verprobt 1779 (SKR04: 3809), das Konto für deren Umsatzsteuer.

Die Steuer zu Kz 47, 85 und 96 kommt in den Vorgaben deshalb aus den Grundlagenkonten, nicht aus dem gebuchten Betrag auf 1787, 1785 oder 1784 (SKR04: 3837, 3835 oder 3834). Weicht die Buchung um mehr als die Toleranz ab, geht die Verprobung nicht auf, und die Meldung ist nicht bereit. Bucht ein Beleg Steuer auf diese Konten ohne Grundlagenkonto, nimmt Steuerbote die Bemessungsgrundlage aus dem Beleg, siehe den nächsten Abschnitt; die Spalte „Grundlage ohne Grundlagenkonto“ nennt ihre Kennzahl.

### Vorsteuer und der Satz des Wareneingangskontos

Die Vorsteuer (Kz 66) hat keine Verprobung: Ihre Grundlage, der Aufwand oder Wareneingang, steht auf Konten ohne Kennzahl, und ein Aufwandskonto sagt meist keinen Steuersatz. Abziehbar ist aber nur „die gesetzlich geschuldete Steuer für Lieferungen und sonstige Leistungen, die von einem anderen Unternehmer für sein Unternehmen ausgeführt worden sind“ (§ 15 Abs. 1 Satz 1 Nr. 1 Satz 1 UStG); eine zu hoch ausgewiesene Steuer schuldet der Aussteller (§ 14c Abs. 1 UStG), abziehen darf sie der Empfänger nicht. Einige Konten nennen den Satz ihrer Vorsteuer, und ERPNext setzt in einer Eingangsrechnung die Artikelsteuervorlage einer Position beim Speichern auf die Vorgabe des Artikels zurück, so dass 19 % Vorsteuer auf einem Wareneingang zu 7 % im Alltag vorkommt.

Für diese Konten vergleicht [`input_tax.py`](../steuerbote/ustva/input_tax.py) je Beleg die gebuchte Vorsteuer auf den Konten der Kz 66 mit dem Satz des Kontos auf seiner Grundlage, je Satz auf Cent gerundet wie die Steuerzeile eines Belegs, mit der Toleranz je Beleg der Einstellungen wie die Verprobung der Umsatzsteuer. Weicht sie ab, gibt „Berechnen“ die Warnung `VORSTEUER-ABWEICHUNG` mit Beleg, Konten, Grundlage, gebuchter und erwarteter Vorsteuer. Die Warnung hält die Meldung nicht an, denn ob die Rechnung die Steuer so ausweist, sieht Steuerbote nicht; die Kennzahl bleibt, wie gebucht. Steuerbote beurteilt keinen Beleg, der zugleich auf ein anderes Aufwands- oder Bestandskonto ohne Satz bucht, denn seine Vorsteuer kann zu dieser Zeile gehören, und keine Buchungszeilen ohne Beleg. Ein Kontenrahmen ohne Vorgaben hat keine solchen Konten.

| Satz der Vorsteuer | SKR03 | SKR04 |
|---|---|---|
| 7 % | 3010 bis 3019 „Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer“, 3091 „Energiestoffe (Fertigung) 7 % VSt“, 3300 bis 3309 und 3347 „Wareneingang 7 % Vorsteuer“ | 5110 bis 5119, 5191, 5300 bis 5309, 5347 |
| 19 % | 3030 bis 3039 „Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer“, 3092 „Energiestoffe (Fertigung) 19 % VSt“, 3400 bis 3409 und 3418 „Wareneingang 19 % Vorsteuer“ | 5130 bis 5139, 5192, 5400 bis 5409, 5418 |

Quelle der Konten und ihrer Bezeichnungen sind die DATEV-Kontenrahmen SKR 03 und SKR 04, „Gültig für 2026“ (`purchase_rates` in `defaults.py`).

### Bemessungsgrundlage ohne Grundlagenkonto

Viele Bücher haben für einen innergemeinschaftlichen Erwerb oder eine Leistung nach § 13b UStG kein eigenes Grundlagenkonto. Der Nettobetrag steht auf dem Konto, auf das der Einkauf ohnehin gehört, etwa einem Aufwands-, Anlage- oder Wareneingangskonto, und die Steuer bucht ein DATEV-Steuerschlüssel oder die Steuervorlage der Eingangsrechnung auf die Steuerkonten der Verprobung: Umsatzsteuer und Vorsteuer nach § 13b UStG (SKR03: 1787 und 1577) oder aus dem innergemeinschaftlichen Erwerb (1774 und 1574). Die Vorsteuer findet die Voranmeldung auf ihren Konten (Kz 67, 61). Ohne Grundlagenkonto aber blieben Bemessungsgrundlage und Umsatzsteuer leer, Kz 83 um diese Umsatzsteuer zu niedrig, und die Verprobung ginge für jeden solchen Beleg nicht auf.

Eine Verprobung mit einer Kennzahl für die Bemessungsgrundlage ohne Grundlagenkonto (`derived_base`, in der Kontenzuordnung die Spalte „Kz der Grundlage ohne Grundlagenkonto“) leitet sie deshalb Beleg für Beleg ab (`derive_bases` in [`calculation.py`](../steuerbote/ustva/calculation.py)):

1. **Welche Belege.** Jeder Beleg, der auf den Steuerkonten der Verprobung einen Saldo hat und auf keinem ihrer Grundlagenkonten bucht. Ein Beleg mit einer Buchung auf einem Grundlagenkonto zeigt seine Bemessungsgrundlage selbst; seine Verprobung bleibt, wie sie war, und eine Steuer, die nicht passt, bleibt eine Abweichung. So zählt keine Bemessungsgrundlage doppelt, auch wenn ein Unternehmen Grundlagenkonten und Steuerschlüssel nebeneinander nutzt.
2. **Aus den Buchungszeilen.** In Frage kommen die Konten des Belegs ohne Platz in der Kontenzuordnung: kein zugeordnetes Konto wie eine Vorsteuer, kein Steuerkonto einer Verprobung, kein beobachtetes Konto. Steuerbote sucht die Konten, deren Saldo auf der Seite der Grundlagenkonten mal Satz die gebuchte Steuer ergibt, am genauesten zuerst und höchstens 1 Cent daneben (`DERIVATION_TOLERANCE`, für Steuer, die je Artikel gerundet ist). So bleibt eine Zeile anderen Zwecks im selben Beleg draußen, etwa eine Bankgebühr: Mit ihr passt die Steuer nicht mehr. Bank-, Kreditoren- und Debitorenzeilen tragen das umgekehrte Vorzeichen und passen nie allein.
3. **Aus der Steuer.** Passen mehrere Zusammenstellungen gleich gut mit verschiedenen Summen, passt keine, hat der Beleg mehr als zwölf solche Konten (`MOST_LINES`) oder nennen die Zeilen keinen Beleg, zeigen die Zeilen die Bemessungsgrundlage nicht. Dann rechnet Steuerbote sie aus der Steuer zurück, siehe [Rundung](#rundung), und die Meldung bekommt für den Beleg den Hinweis `GRUNDLAGE-AUS-STEUER`.
4. **Wohin.** Die Bemessungsgrundlage geht in die Kennzahl der Verprobung, zum Satz ihrer Grundlagenkonten. Hat die Kennzahl eine eigene Steuer-Kennzahl (Kz 85 zu Kz 84, Kz 47 zu Kz 46), entsteht die Steuer je Beleg wie bei einem Grundlagenkonto mit Satz; bei Kz 89 und 93 berechnet der Vordruck sie aus der gemeldeten Bemessungsgrundlage. Die Verprobung zählt die Steuer der abgeleiteten Bemessungsgrundlage als berechnete Steuer und geht für diese Belege auf.

Gutschriften und Stornos gehen mit ihrem Vorzeichen ein: Eine Gutschrift mindert Bemessungsgrundlage und Steuer und kann sie negativ machen, ein Storno mit Neubuchung im selben Beleg ergibt keine Steuer und leitet nichts ab. Ein Beleg mit Steuer zweier Verprobungen, etwa eines Erwerbs und einer Leistung nach § 13b UStG, findet für jede ihre eigenen Zeilen.

Die Vorgaben nennen die Kennzahl für die Verprobungen der Erwerbe (Kz 89, 93 und 94, jeweils die Kennzahl ihres Satzes) und des § 13b UStG (Kz 84, und Kz 46 für einen Lieferanten mit Sitz im übrigen Gemeinschaftsgebiet). Kz 84 nimmt die Leistungen nach § 13b Absatz 2 Nummer 1, 2 und 4 bis 12 UStG auf, darunter nach Nummer 1 jede Werklieferung und sonstige Leistung eines im Ausland ansässigen Unternehmers, die nicht unter Absatz 1 fällt. Kz 46 nimmt nur die sonstigen Leistungen nach § 3a Absatz 2 UStG eines im übrigen Gemeinschaftsgebiet ansässigen Unternehmers auf (§ 13b Absatz 1 UStG). Das Hauptbuch zeigt das nicht, der Lieferant des Belegs schon: Wie Steuerbote zwischen beiden entscheidet, steht im nächsten Abschnitt. Die Verprobung „Umsatzsteuer aus innergemeinschaftlichem Erwerb ohne Vorsteuerabzug“ leitet nichts ab, denn ihr Steuerkonto nimmt 7 und 19 % auf, und ohne Grundlagenkonto bleibt der Satz offen; die Verprobungen der Umsätze leiten nichts ab, denn Umsätze haben immer ein eigenes Erlöskonto, und eine Umsatzsteuer ohne Erlöskonto soll die Verprobung zeigen. Eine leere Spalte lässt einen Beleg ohne Grundlagenkonto wie bisher als Abweichung stehen.

Was die Meldung zeigt: die Kennzahlen mit der abgeleiteten Bemessungsgrundlage, in der Tabelle „Verprobung“ je Verprobung die Spalte „Grundlage ohne Grundlagenkonto“ mit der Summe der abgeleiteten Bemessungsgrundlagen, im Bericht „UStVA Kennzahlen“ je Beleg die Konten, aus denen die Bemessungsgrundlage kommt, oder das Steuerkonto, wenn sie aus der Steuer stammt, und für jeden Beleg, dessen Bemessungsgrundlage aus der Steuer stammt, den Hinweis `GRUNDLAGE-AUS-STEUER`. Der Abgleich der Rechnungen mit dem Hauptbuch (`ABGLEICH-RECHNUNGEN`) zählt die abgeleiteten Bemessungsgrundlagen nicht, denn sie stehen auf keinem Konto der Kennzahl, das eine Rechnung nennen könnte; der Abgleich mit den Registern vergleicht weiter Konto für Konto. Die Umsatzsteuererklärung leitet über das Jahr genauso ab und gibt die Bemessungsgrundlage und ihre Steuer an die Vorgabezeile ihrer Kennzahl.

### Kz 46 oder Kz 84: der Sitz des Leistenden

Abschnitt D des Vordrucks hat drei Zeilen für die Leistungen, deren Steuer das Unternehmen als Leistungsempfänger schuldet (§ 13b Absatz 5 UStG). Die Steuer ist in allen dreien dieselbe, die Zeile nicht: Das Finanzamt gleicht Kz 46 mit den Zusammenfassenden Meldungen der Leistenden ab.

**Die Zeilen.** Die Anleitung zur Umsatzsteuer-Voranmeldung 2026 sagt zu den Zeilen 30 bis 32: „Vorbehaltlich der Ausnahmeregelungen des § 13b Absatz 6 UStG tragen Sie bitte folgende im Inland steuerpflichtige Umsätze ein, für die Sie die Steuer als Leistungsempfänger schulden“:

| Zeile | Kennzahl | Was hineingehört | Gesetz |
|---|---|---|---|
| 30 | Kz 46, Steuer Kz 47 | „sonstige Leistungen nach § 3a Absatz 2 UStG eines im übrigen Gemeinschaftsgebiet ansässigen Unternehmers“ | § 13b Absatz 1 UStG: „Für nach § 3a Absatz 2 im Inland steuerpflichtige sonstige Leistungen eines im übrigen Gemeinschaftsgebiet ansässigen Unternehmers entsteht die Steuer mit Ablauf des Voranmeldungszeitraums, in dem die Leistungen ausgeführt worden sind.“ |
| 31 | Kz 73, Steuer Kz 74 | „unter das Grunderwerbsteuergesetz fallende Umsätze, insbesondere Lieferungen von Grundstücken, für die der leistende Unternehmer nach § 9 Absatz 3 UStG zur Steuerpflicht optiert hat“ | § 13b Absatz 2 Nummer 3 UStG |
| 32 | Kz 84, Steuer Kz 85 | „Werklieferungen und die nicht in Zeile 30 einzutragenden sonstigen Leistungen eines im Ausland ansässigen Unternehmers“, dazu die Fälle im Inland: Lieferungen sicherungsübereigneter Gegenstände, Bauleistungen, Gas, Elektrizität, Wärme und Kälte, Emissionszertifikate, die Gegenstände der Anlage 3 (Altmetalle und Schrott), die Reinigung von Gebäuden, Gold, Mobilfunkgeräte, Tablet-Computer, Spielekonsolen und integrierte Schaltkreise, die Metalle der Anlage 4 und Telekommunikationsleistungen an Wiederverkäufer | § 13b Absatz 2 Nummer 1, 2 und 4 bis 12 UStG |

**Nicht jede Leistung aus dem übrigen Gemeinschaftsgebiet gehört in Kz 46.** Zeile 30 nimmt nur sonstige Leistungen, deren Ort sich nach § 3a Absatz 2 UStG richtet, dem Ort, „von dem aus der Empfänger sein Unternehmen betreibt“. Eine Werklieferung und jede sonstige Leistung mit einem anderen Ort gehören auch von einem Unternehmer aus dem übrigen Gemeinschaftsgebiet in Zeile 32 (§ 13b Absatz 2 Nummer 1 UStG: „nicht unter Absatz 1 fallende sonstige Leistungen eines im Ausland ansässigen Unternehmers“), wenn ihr Ort im Inland liegt. Das sind vor allem die Ausnahmen, die § 3a Absatz 2 UStG selbst nennt („vorbehaltlich der Absätze 3 bis 8 und der §§ 3b und 3e“): die sonstige Leistung im Zusammenhang mit einem Grundstück, etwa Bau-, Architekten- und Maklerleistungen oder ein Hotelzimmer (§ 3a Absatz 3 Nummer 1 UStG), die kurzfristige Vermietung eines Beförderungsmittels (§ 3a Absatz 3 Nummer 2 UStG), die Restaurationsleistung (§ 3a Absatz 3 Nummer 3a Buchstabe a UStG), die Eintrittsberechtigung zu Veranstaltungen (§ 3a Absatz 3 Nummer 5 UStG) und die Personenbeförderung (§ 3b UStG). Steuerfreie Leistungen gehören in keine der Zeilen.

**Fälle im Inland.** Bauleistungen, die Reinigung von Gebäuden, Schrott und die anderen Fälle des § 13b Absatz 2 Nummer 2 und 4 bis 12 UStG gehören in Zeile 32, gleich wo der Leistende ansässig ist: Ein Bauunternehmer aus Deutschland, Polen oder der Schweiz kommt in Kz 84. Grundstücksumsätze nach dem Grunderwerbsteuergesetz gehören in Zeile 31. Für die Fälle im Inland hat SKR03 eigene Grundlagenkonten (3120, 3140 und die Konten des Schrotts), die Vorgaben ordnen sie Kz 84 zu.

**Wer im übrigen Gemeinschaftsgebiet ansässig ist.** „Ein im übrigen Gemeinschaftsgebiet ansässiger Unternehmer ist ein Unternehmer, der in den Gebieten der übrigen Mitgliedstaaten der Europäischen Union, die nach dem Gemeinschaftsrecht als Inland dieser Mitgliedstaaten gelten, einen Wohnsitz, seinen gewöhnlichen Aufenthalt, seinen Sitz, seine Geschäftsleitung oder eine Betriebsstätte hat“; „Maßgebend ist der Zeitpunkt, in dem die Leistung ausgeführt wird“ (§ 13b Absatz 7 Satz 2 und 4 UStG). Das übrige Gemeinschaftsgebiet sind „die Gebiete der übrigen Mitgliedstaaten der Europäischen Union, die nach dem Gemeinschaftsrecht als Inland dieser Mitgliedstaaten gelten“, und „Das Fürstentum Monaco gilt als Gebiet der Französischen Republik“ (§ 1 Absatz 2a UStG). Nicht dazu gehören Gebiete eines Mitgliedstaats außerhalb des Gebiets der Mehrwertsteuer, etwa die Kanarischen Inseln, die Ålandinseln, der Berg Athos, die französischen Gebiete nach Artikel 349 und 355 Absatz 1 AEUV, Ceuta, Melilla und Livigno (Artikel 6 der Richtlinie 2006/112/EG).

**Die Mitgliedstaaten eines Tages.** Welche Staaten am Tag einer Leistung Mitgliedstaaten sind, führt `MEMBERSHIPS` in [`residence.py`](../steuerbote/ustva/residence.py) mit dem Tag des Beitritts: die Gründerstaaten seit 1958, Dänemark und Irland seit 1973, Griechenland seit 1981, Spanien und Portugal seit 1986, Österreich, Finnland und Schweden seit 1995, die zehn Staaten der Erweiterung am 1. Mai 2004, Bulgarien und Rumänien seit 2007 und Kroatien seit dem 1. Juli 2013 (Jahre laut <https://european-union.europa.eu/principles-countries-history/eu-countries_en>). Das Vereinigte Königreich, mit der Insel Man (§ 1 Absatz 2a Satz 2 UStG), gilt bis zum 31. Dezember 2020: Das Austrittsabkommen hat einen Übergangszeitraum, „der am Tag des Inkrafttretens dieses Abkommens beginnt und am 31. Dezember 2020 endet“ (Artikel 126), und in ihm „gilt das Unionsrecht während des Übergangszeitraums für das Vereinigte Königreich sowie im Vereinigten Königreich“ (Artikel 127 Absatz 1; ABl. L 29 vom 31. Januar 2020). Nordirland zählt seitdem nur für Waren zur Union: „Für den Dienstleistungsverkehr mit Nordirland gelten die für das Drittlandsgebiet geltenden Vorschriften zur Umsatzsteuer.“ (BZSt, „Fragen und Antworten“ zur USt-IdNr., siehe [Aufbau einer USt-IdNr.](ust-idnr-pruefung.md#aufbau-einer-ust-idnr)). Für § 13b Absatz 1 UStG, der nur sonstige Leistungen kennt, ist ein Unternehmer aus Nordirland deshalb im Drittlandsgebiet ansässig, und seine Leistung gehört in Kz 84. Eine Liste der Mitgliedstaaten vor 2026 braucht Steuerbote heute nur für Belege, die es nachträglich rechnet; die Daten stehen trotzdem vollständig da, damit ein Tag immer dieselbe Antwort gibt.

**Die Zusammenfassende Meldung des Leistenden.** Kz 46 ist das Gegenstück zur Zusammenfassenden Meldung des Leistenden. Jeder Unternehmer der Union meldet dort „die Steuerpflichtigen sowie die nicht steuerpflichtigen juristischen Personen mit Mehrwertsteuer-Identifikationsnummer, für die er Dienstleistungen erbracht hat, die keine Dienstleistungen sind, die in dem Mitgliedstaat, in dem der Umsatz steuerbar ist, von der Mehrwertsteuer befreit sind, und für die der Dienstleistungsempfänger gemäß Artikel 196 der Steuerschuldner ist“ (Artikel 262 Absatz 1 Buchstabe c der Richtlinie 2006/112/EG), und Artikel 196 ist die Steuerschuld des Empfängers für eine „Dienstleistung nach Artikel 44“, die Grundregel, die § 3a Absatz 2 UStG umsetzt. Was der tschechische oder irische Leistende unter der USt-IdNr. des Unternehmens meldet, sollte also in dessen Kz 46 stehen; die deutsche Seite dazu ist § 18a Absatz 7 Satz 1 Nummer 3 UStG, siehe [Zusammenfassende Meldung](zm.md). Eine Leistung in Kz 84 meldet der Leistende dort nicht.

**Was die USt-IdNr. auf der Rechnung zeigt.** Sie zeigt, wo ein Unternehmer registriert ist, nicht, wo er ansässig ist: Ein Unternehmen aus dem Drittlandsgebiet kann die USt-IdNr. eines Mitgliedstaats haben, in dem es registriert ist, und eine Rechnung unter dieser Nummer stellen. Eine Nummer aus „EU“ und neun Ziffern ist die Identifikationsnummer der Sonderregelung für nicht in der Gemeinschaft ansässige Steuerpflichtige (Artikel 362 der Richtlinie 2006/112/EG, „nicht in der Gemeinschaft ansässigen Steuerpflichtigen“), also gerade kein Zeichen für einen Sitz in der Union. Ein Unternehmen aus dem Drittlandsgebiet kann außerdem dieselbe Leistung einmal mit deutscher Umsatzsteuer abrechnen, wenn keine USt-IdNr. des Empfängers vorlag, und einmal ohne Steuer; dann trägt nur der zweite Beleg Steuer nach § 13b UStG.

**Wie Steuerbote entscheidet.** Bucht ein Beleg die Steuer einer Verprobung des § 13b UStG ohne Grundlagenkonto (siehe [Bemessungsgrundlage ohne Grundlagenkonto](#bemessungsgrundlage-ohne-grundlagenkonto)), entscheidet `place()` in [`residence.py`](../steuerbote/ustva/residence.py) zwischen der Kennzahl der Spalte „Kz der Grundlage ohne Grundlagenkonto“ (`derived_base`, Vorgabe Kz 84) und der Spalte „Kz bei Sitz im übrigen Gemeinschaftsgebiet“ (`derived_base_eu`, Vorgabe Kz 46). Was die Frappe-Schicht über den Beleg weiß, liest [`suppliers.py`](../steuerbote/suppliers.py) (`Voucher`, `Supplier`); der Kern entscheidet in dieser Reihenfolge:

1. **Einordnung des Belegs.** Eine Zeile der Tabelle „Einordnungen nach § 13b UStG“ der Kontenzuordnung für diese Eingangsrechnung oder Journalbuchung.
2. **Einordnung des Lieferanten.** Eine Zeile derselben Tabelle für den Lieferanten des Belegs; hat der Beleg mehrere Lieferanten, nur wenn alle dieselbe haben.
3. **Einordnung der Steuervorlage.** Eine Zeile für die Vorlage für Einkaufssteuern, die die Eingangsrechnung trägt (`taxes_and_charges`). Wer seine Vorlagen nach Kz 46 und 84 trennt, ordnet sie einmal ein.
4. **Land des Lieferanten.** Das Feld „Land“ des Lieferanten, ohne Land das Land seiner Hauptanschrift. Ein Lieferant im übrigen Gemeinschaftsgebiet am Buchungsdatum des Belegs gibt Kz 46, einer im Inland oder im Drittlandsgebiet Kz 84. Lieferanten eines Belegs mit verschiedenem Sitz entscheiden nichts.
5. **Sonst** bleibt die Einordnung offen, und der Beleg nimmt Kz 84, die Kennzahl der Verprobung.

Die Einordnung durch einen Menschen geht vor, weil nur er die Ausnahmen kennt: die Werklieferung, die Grundstücksleistung, das Hotelzimmer eines Lieferanten aus dem übrigen Gemeinschaftsgebiet, oder die Leistung, die ein Unternehmen aus dem Drittlandsgebiet unter demselben Lieferanten abrechnet wie seine Tochter in einem Mitgliedstaat. Die USt-IdNr. entscheidet nie, sie prüft nur das Land. Wer ein Konto für die Grundlage hat, bucht weiter darauf: Ein Beleg mit einer Buchung auf einem Grundlagenkonto der Verprobung behält dessen Kennzahl, gleich wo sein Lieferant ansässig ist, und nichts zählt doppelt.

**Hinweise statt stiller Wahl.** Jeder Widerspruch und jede offene Einordnung steht als Hinweis an der Meldung, mit Beleg und Lieferant; keiner hält die Meldung an:

| Code | Art | Wann |
|---|---|---|
| `SITZ-OFFEN` | Hinweis | Ein Beleg des § 13b UStG ohne Grundlagenkonto nennt keinen Lieferanten, sein Lieferant hat weder Land noch Anschrift mit Land, oder seine Lieferanten sind an verschiedenen Orten ansässig; er geht in Kz 84. Ein Lieferant ohne Land, dessen USt-IdNr. mit dem Kennzeichen eines Mitgliedstaats beginnt, bekommt dasselbe: Die Nummer allein entscheidet nicht. |
| `SITZ-WIDERSPRUCH` | Hinweis | Das Land des Lieferanten entscheidet, aber seine Anschrift liegt anderswo, oder seine USt-IdNr. beginnt mit dem Kennzeichen eines anderen Orts (XI gilt als Drittlandsgebiet, EU als kein Ort); oder eine Steuervorlage ist als andere Leistung eingeordnet, der Lieferant aber im übrigen Gemeinschaftsgebiet ansässig. |
| `KZ46-OHNE-EU-SITZ` | Warnung | Beleg, Lieferant oder Steuervorlage sind als sonstige Leistung aus dem übrigen Gemeinschaftsgebiet eingeordnet, der Lieferant ist laut Stammdaten aber im Inland oder im Drittlandsgebiet ansässig; oder ein Beleg bucht auf ein Grundlagenkonto von Kz 46 (SKR03 3123, 3143, 3113, 3133), sein Lieferant ist aber nicht im übrigen Gemeinschaftsgebiet ansässig oder als andere Leistung eingeordnet. |
| `ERWERB-AUS-DRITTLAND` | Warnung | Ein Beleg bucht Umsatzsteuer aus innergemeinschaftlichem Erwerb, mit oder ohne Grundlagenkonto, und sein Lieferant ist laut Stammdaten im Drittlandsgebiet ansässig. Ein innergemeinschaftlicher Erwerb setzt voraus, dass der Gegenstand „aus dem Gebiet eines Mitgliedstaates in das Gebiet eines anderen Mitgliedstaates“ gelangt (§ 1a Absatz 1 Nummer 1 UStG); der Sitz des Lieferanten entscheidet das nicht, deshalb nur eine Warnung zum Prüfen. |

Eine Einordnung ohne Lieferant und ein Lieferant ohne Land brauchen keinen weiteren Hinweis, wenn eine Einordnung vorliegt. Ein Beleg mit Grundlagenkonto von Kz 84 und einem Lieferanten aus dem übrigen Gemeinschaftsgebiet bekommt keinen Hinweis: Das Grundlagenkonto ist die Entscheidung des Unternehmens, und Bauleistungen auf denselben Konten stammen oft aus dem übrigen Gemeinschaftsgebiet.

**Überall gleich.** Die Kennzahl jedes Belegs ist in der Meldung, ihrer Verprobung (die Steuer der abgeleiteten Bemessungsgrundlage zählt als berechnete Steuer, gleich in welcher Kennzahl), dem Vorperiodenvergleich, dem Bericht „UStVA Kennzahlen“ und der Umsatzsteuererklärung dieselbe, denn alle rechnen mit `calculate()` und denselben Angaben aus `suppliers.py`. Der Abgleich der Rechnungen mit dem Hauptbuch zieht die abgeleiteten Bemessungsgrundlagen je Kennzahl ab, ob Kz 46 oder Kz 84. Die Summe von Kz 46 und 84 und die von Kz 47 und 85 sind dieselben wie ohne Unterscheidung; nur ihre Aufteilung ändert sich.

**Zu bestätigen durch die Steuerberatung.** Steuerbote ordnet einen Beleg nach dem Sitz des Lieferanten ein und nimmt an, dass jede sonstige Leistung eines Lieferanten aus dem übrigen Gemeinschaftsgebiet, die als Leistung nach § 13b UStG gebucht ist, eine Leistung nach § 3a Absatz 2 UStG ist. Ob das für die Bezüge des Unternehmens stimmt, welche Ausnahmen es hat, und wie ein Lieferant mit Sitz im Drittlandsgebiet und Betriebsstätte in einem Mitgliedstaat einzuordnen ist (§ 13b Absatz 7 Satz 2 UStG nennt die Betriebsstätte, die Frage, ob sie an der Leistung beteiligt ist, beantwortet das Gesetz für den Fall des Satzes 3 nur für eine Betriebsstätte im Inland), klärt die Steuerberatung, siehe [Prüfliste](pruefliste-steuerberatung.md). Das Buchungsdatum steht für den Tag der Leistung; zwischen beiden änderte sich die Liste der Mitgliedstaaten zuletzt zum 1. Januar 2021.

Quellen: §§ 1, 1a, 3a, 3b, 13b und 18a UStG (<https://www.gesetze-im-internet.de/ustg_1980/>, am 25. November 2026 gelesen); die Anleitung USt 1 E 2026 aus dem BMF-Schreiben unter [Quelle](#quelle), Erläuterungen zu den Zeilen 30 bis 32; Richtlinie 2006/112/EG, konsolidierte Fassung vom 1. Januar 2025, Artikel 6, 196, 262 und 362 (<https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:02006L0112-20250101>); Abkommen über den Austritt des Vereinigten Königreichs, Artikel 126 und 127 (<https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:12020W/TXT>).

### Abgleich mit den Registern

Die Verprobung prüft jeden Beleg in sich. Der Abgleich mit den Registern stellt dazu die Summen der Berichte Sales Register und Purchase Register von ERPNext neben die Beträge, die die Meldung aus dem Hauptbuch nimmt ([`registers.py`](../steuerbote/ustva/registers.py)). Welche Kennzahlen ein Bericht abgleicht, folgt den Abschnitten des Vordrucks USt 1 A 2026:

| Bericht | Abschnitte des Vordrucks | Kennzahlen |
|---|---|---|
| Sales Register (Ausgangsrechnungen) | A. Steuerpflichtige Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben (Zeilen 13 bis 18); B. Steuerfreie Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben (Zeilen 19 bis 23); E. Ergänzende Angaben zu Umsätzen (Zeilen 33 bis 36) | 81, 86, 87, 35/36, 77, 76/80; 41, 44, 49, 43, 48; 42, 60, 21, 45 |
| Purchase Register (Eingangsrechnungen) | C. Innergemeinschaftliche Erwerbe (Zeilen 24 bis 29); D. Leistungsempfänger als Steuerschuldner (§ 13b UStG, Zeilen 30 bis 32); aus F. die Vorsteuer aus Rechnungen, aus innergemeinschaftlichen Erwerben, die Einfuhrumsatzsteuer und die Vorsteuer aus Leistungen nach § 13b UStG (Zeilen 38 bis 41) | 91, 89, 93, 90, 95/98, 94/96; 46/47, 73/74, 84/85; 66, 61, 62, 67 |
| keiner | Kz 63, 59 und 64, die das Unternehmen selbst berechnet (Durchschnittssätze nach § 23a UStG, Vorsteuerabzug nach § 15 Abs. 4a UStG, Berichtigung nach § 15a UStG); G. Andere Steuerbeträge (Kz 65 und 69, aus Verkäufen wie aus Einkäufen); Kz 39, 50 und 37 | — |

Je Bericht gelten diese Gruppen:

- **Bemessungsgrundlagen:** je Kennzahl die Summe der Konten ihrer Regeln im Bericht gegen den genauen Betrag der Kennzahl laut Hauptbuch, vor dem Runden auf volle Euro. Die Konten stehen im Bericht mit dem Nettobetrag der Artikel, die Ausgangsrechnung im Haben, die Eingangsrechnung im Soll. Inländische Umsätze zu 19 und 7 % sind Kz 81 und 86, die Leistungen nach § 13b UStG Kz 46, 73 und 84, die innergemeinschaftlichen Lieferungen und sonstigen Leistungen Kz 41, 44, 49 und 21, die innergemeinschaftlichen Erwerbe Kz 89, 93 und die übrigen des Abschnitts C. Eine zusätzliche Kennzahl wie Kz 50 bleibt außen vor, sie wiederholt einen Betrag aus den Zeilen 13 bis 18.
- **Steuer:** je Steuerkonto, das eine Verprobung prüft oder eine Regel einer Steuer-Kennzahl zuordnet, die Steuer im Bericht gegen den Saldo des Kontos laut Hauptbuch. Das Steuerkonto einer Verprobung gehört zum Bericht ihrer Grundlagen: die Umsatzsteuer 19 % und 7 % (1776 und 1771, SKR04: 3806 und 3801) zum Sales Register, die Umsatzsteuer aus innergemeinschaftlichen Erwerben und nach § 13b UStG (etwa 1774 und 1787, SKR04: 3804 und 3837) zum Purchase Register. Die Vorsteuer (Kz 66, 61, 62 und 67) gehört zum Purchase Register. Die Steuer, die der Vordruck aus Kz 81, 86, 89 und 93 selbst berechnet, vergleicht der Abgleich nicht, denn der Vordruck rundet die Bemessungsgrundlage vorher auf volle Euro; die gebuchte Steuer der Verprobungskonten vergleicht er.

Die Differenz ist der Betrag laut Hauptbuch abzüglich des Betrags laut Bericht, auf Cent gerundet. Steuer, die eine Eingangsrechnung abzieht, etwa die Umsatzsteuer nach § 13b UStG, zeigt der Purchase Register negativ; auf der Haben-Seite des Steuerkontos wird sie positiv. Was nicht verglichen werden kann, steht mit seinem Betrag in einer eigenen Zeile, ohne Differenz: Eröffnungsrechnungen, die Konten von „Bewusst ohne Kennzahl“, Konten ohne Platz in der Kontenzuordnung, beobachtete Konten, Konten von Kennzahlen, die der Bericht nicht abgleicht, und Konten ohne Kontonummer. Bucht ein Bericht im Zeitraum auf kein Konto, gleicht er nichts ab, und eine Zeile sagt das. Eine Differenz braucht vor der Abgabe eine Erklärung in ihrer Zeile oder in den Anmerkungen, siehe [Architektur](architektur.md#abgleich-mit-sales-register-und-purchase-register).

### Beobachtete Konten

Diese Konten gehören zur Voranmeldung, sind in den Vorgaben aber noch keiner Kennzahl zugeordnet. Die Vorgaben beobachten sie auf der Stufe „Sperrt“: Hat eines davon im Zeitraum einen Saldo, steht es in `unmapped`, und die Meldung ist nicht bereit, bis die Firma eine Zuordnung ergänzt hat. Auf 1548 und 1725 (SKR04: 1434 und 3865) ist ein Saldo eine Frage des Zeitpunkts: Vorsteuer, die erst in einem späteren Zeitraum abziehbar ist, und Umsatzsteuer, die erst später fällig wird. Die Firma klärt sie, bevor sie meldet.

| SKR03 | Bezeichnung laut Kontenrahmen 2026 |
|---|---|
| 1548 | Vorsteuer in Folgeperiode/im Folgejahr abziehbar |
| 1725 | Umsatzsteuer in Folgeperiode fällig (§§ 13 Abs. 1 Nr. 6 und 13b Abs. 2 UStG) |
| 1560 | Aufzuteilende Vorsteuer |
| 1561 | Aufzuteilende Vorsteuer 7 % |
| 1562 | Aufzuteilende Vorsteuer aus innergemeinschaftlichem Erwerb |
| 1563 | Aufzuteilende Vorsteuer aus innergemeinschaftlichem Erwerb 19 % |
| 1566 | Aufzuteilende Vorsteuer 19 % |
| 1567 | Aufzuteilende Vorsteuer nach §§ 13a und 13b UStG |
| 1569 | Aufzuteilende Vorsteuer nach §§ 13a und 13b UStG 19 % |
| 1712 | Erhaltene, versteuerte Anzahlungen 5 % USt (Verbindlichkeiten) |
| 1717 | Erhaltene, versteuerte Anzahlungen 16 % USt (Verbindlichkeiten) |
| 1760 | Umsatzsteuer nicht fällig |
| 1761 | Umsatzsteuer nicht fällig 7 % |
| 1762 | Umsatzsteuer nicht fällig aus im Inland steuerpflichtigen EU-Lieferungen |
| 1764 | Umsatzsteuer nicht fällig aus im Inland steuerpflichtigen EU-Lieferungen 19 % |
| 1766 | Umsatzsteuer nicht fällig 19 % |
| 1769 | Umsatzsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager |
| 1770 | Umsatzsteuer |
| 3075 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer |
| 3076 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer |
| 3151 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird 19 % Vorsteuer und 19 % Umsatzsteuer |
| 3154 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird ohne Vorsteuer, mit 19 % Umsatzsteuer |
| 3560 | Waren aus einem Umsatzsteuerlager, § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer |
| 3565 | Waren aus einem Umsatzsteuerlager, § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer |
| 8110 | Sonstige steuerfreie Umsätze Inland |
| 8190 | Erlöse, die mit den Durchschnittssätzen des § 24 UStG versteuert werden |
| 8198 | Umsatzerlöse nach § 25 UStG 19 % USt |
| 8199 | Umsatzerlöse nach § 25a UStG 19 % USt |
| 8189 | Umsatzerlöse nach § 25 UStG ohne USt |
| 8197 | Umsatzerlöse nach § 25a UStG ohne USt |
| 8200 | Erlöse |
| 8340 bis 8349 | Erlöse 16 % USt |
| 8649 | Sonstige Erträge betrieblich und regelmäßig 16 % USt |
| 8708 | Erlösschmälerungen für Umsätze nach § 25 UStG 19 % USt |
| 8709 | Erlösschmälerungen für Umsätze nach § 25a UStG 19 % USt |
| 1716 | Erhaltene Anzahlungen 15% MwSt. (SKR03-Variante) |
| 2400 | Forderungsverluste (übliche Höhe) |
| 2430 | Forderungsverluste (soweit unüblich hoch) |
| 3150 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird |
| 3153 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird ohne Vorsteuer aber mit Umsatzsteuer |
| 3160 | Leistungen nach § 13b UStG mit Vorsteuerabzug |
| 3165 | Leistungen nach § 13b UStG ohne Vorsteuerabzug |
| 3744 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb |
| 3745 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb |
| 8191 | Umsatzerlöse nach §§ 25 und 25a UStG 19 % USt |
| 8193 | Umsatzerlöse nach §§ 25 und 25a UStG ohne USt |
| 8499 | Nebenerlöse (Bezug zu Materialaufwand) |
| 8510 | Provisionsumsätze |
| 8520 | Erlöse Abfallverwertung |
| 8540 | Erlöse Leergut |
| 8570 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten |
| 8590 | Verrechnete sonstige Sachbezüge (keine Waren) |
| 8600 | Sonstige Erlöse betrieblich und regelmäßig (SKR03-Variante) |
| 8607 | Andere Nebenerlöse |
| 8610 | Verrechnete sonstige Sachbezüge |
| 8614 | Verrechnete sonstige Sachbezüge ohne Umsatzsteuer |
| 8700 | Erlösschmälerungen |
| 8730 | Gewährte Skonti |
| 8745 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen |
| 8769 | Gewährte Boni |
| 8770 | Gewährte Rabatte |
| 8800 | Erlöse aus Verkäufen Sachanlagevermögen (bei Buchverlust) |
| 8817 | Erlöse aus Verkäufen immaterieller Vermögensgegenstände (bei Buchverlust) |
| 8818 | Erlöse aus Verkäufen Finanzanlagen (bei Buchverlust) |
| 8819 | Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (bei Buchverlust) |
| 8829 | Erlöse aus Verkäufen Sachanlagevermögen (bei Buchgewinn) |
| 8837 | Erlöse aus Verkäufen immaterieller Vermögensgegenstände (bei Buchgewinn) |
| 8838 | Erlöse aus Verkäufen Finanzanlagen (bei Buchgewinn) |
| 8839 | Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG (bei Buchgewinn) |
| 8853 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens nach § 4 Abs 3 Satz 4 EStG |
| 8900 | Unentgeltliche Wertabgaben |
| 8955 | Umsatzsteuervergütungen nach § 24 UStG |

| SKR04 | Bezeichnung laut Kontenrahmen 2026 |
|---|---|
| 1434 | Vorsteuer in Folgeperiode/im Folgejahr abziehbar |
| 3865 | Umsatzsteuer in Folgeperiode fällig (§§ 13 Abs. 1 Nr. 6 und 13b Abs. 2 UStG) |
| 1410 | Aufzuteilende Vorsteuer |
| 1411 | Aufzuteilende Vorsteuer 7 % |
| 1412 | Aufzuteilende Vorsteuer aus innergemeinschaftlichem Erwerb |
| 1413 | Aufzuteilende Vorsteuer aus innergemeinschaftlichem Erwerb 19 % |
| 1416 | Aufzuteilende Vorsteuer 19 % |
| 1417 | Aufzuteilende Vorsteuer nach §§ 13a und 13b UStG |
| 1419 | Aufzuteilende Vorsteuer nach §§ 13a und 13b UStG 19 % |
| 3261 | Erhaltene, versteuerte Anzahlungen 5 % USt (Verbindlichkeiten) |
| 3270 | Erhaltene, versteuerte Anzahlungen 16 % USt (Verbindlichkeiten) |
| 3800 | Umsatzsteuer |
| 3810 | Umsatzsteuer nicht fällig |
| 3811 | Umsatzsteuer nicht fällig 7 % |
| 3812 | Umsatzsteuer nicht fällig aus im Inland steuerpflichtigen EU-Lieferungen |
| 3814 | Umsatzsteuer nicht fällig aus im Inland steuerpflichtigen EU-Lieferungen 19 % |
| 3816 | Umsatzsteuer nicht fällig 19 % |
| 3839 | Umsatzsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager |
| 5175 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer |
| 5176 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer |
| 5951 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird 19 % Vorsteuer und 19 % Umsatzsteuer |
| 5954 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird ohne Vorsteuer, mit 19 % Umsatzsteuer |
| 5560 | Waren aus einem Umsatzsteuerlager, § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer |
| 5565 | Waren aus einem Umsatzsteuerlager, § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer |
| 4110 | Sonstige steuerfreie Umsätze Inland |
| 4180 | Erlöse, die mit den Durchschnittssätzen des § 24 UStG versteuert werden |
| 4133 | Umsatzerlöse nach § 25 UStG 19 % USt |
| 4134 | Umsatzerlöse nach § 25a UStG 19 % USt |
| 4131 | Umsatzerlöse nach § 25 UStG ohne USt |
| 4132 | Umsatzerlöse nach § 25a UStG ohne USt |
| 4200 | Erlöse |
| 4340 bis 4349 | Erlöse 16 % USt |
| 4834 | Sonstige Erträge betrieblich und regelmäßig 16 % USt |
| 4708 | Erlösschmälerungen für Umsätze nach § 25 UStG 19 % USt |
| 4709 | Erlösschmälerungen für Umsätze nach § 25a UStG 19 % USt |
| 5744 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb |
| 4499 | Nebenerlöse (Bezug zu Materialaufwand) |
| 4869 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens nach § 4 Abs. 3 Satz 4 EStG |
| 4560 | Provisionsumsätze |
| 4570 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten |
| 4949 | Verrechnete sonstige Sachbezüge ohne Umsatzsteuer |
| 3271 | Erhaltene, versteuerte Anz. 15 % USt (Verb.) (ERPNext) |
| 4136 | Umsatzerlöse nach §§ 25 und 25a UStG 19 % USt |
| 4138 | Umsatzerlöse nach §§ 25 und 25a UStG ohne USt |
| 4330 | Erlöse aus im Inland steuerpfl. EU-Lieferungen 16 % USt (ERPNext) |
| 4510 | Erlöse Abfallverwertung |
| 4520 | Erlöse Leergut |
| 4600 | Unentgeltliche Wertabgaben |
| 4695 | Umsatzsteuervergütungen nach § 24 UStG |
| 4700 | Erlösschmälerungen |
| 4723 | Erlösschmälerungen 16 % USt (ERPNext) |
| 4729 | Erlösschmälerungen aus im Inland steuerpfl. EU-Lieferungen 16 % USt (ERPNext) |
| 4730 | Gewährte Skonti |
| 4745 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen |
| 4769 | Gewährte Boni |
| 4770 | Gewährte Rabatte |
| 4833 | Andere Nebenerlöse |
| 4849 | Erlöse aus Verkäufen Sachanlagevermögen (bei Buchgewinn) |
| 4850 | Erlöse aus Verkäufen immaterieller Vermögensgegenstände (bei Buchgewinn) |
| 4851 | Erlöse aus Verkäufen Finanzanlagen (bei Buchgewinn) |
| 4852 | Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG (bei Buchgewinn) |
| 4940 | Verrechnete sonstige Sachbezüge (keine Waren) |
| 4946 | Verrechnete sonstige Sachbezüge |
| 5726 | Nachlässe aus innergem. Erwerb 16 % Vorsteuer und 16 % Umsatzsteuer (ERPNext) |
| 5727 | Nachlässe aus innergem. Erwerb 15 % Vorsteuer und 15 % Umsatzsteuer (ERPNext) |
| 5745 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb |
| 5950 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird |
| 5953 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird ohne Vorsteuer aber mit Umsatzsteuer |
| 5960 | Leistungen nach § 13b UStG mit Vorsteuerabzug |
| 5965 | Leistungen nach § 13b UStG ohne Vorsteuerabzug |
| 6280 | Forderungsverluste (soweit unüblich hoch) |
| 6285 | Forderungsverluste 16% USt (soweit unüblich hoch) (ERPNext) |
| 6287 | Forderungsverluste 15% USt (soweit unüblich hoch) (ERPNext) |
| 6889 | Erlöse aus Verkäufen Sachanlagevermögen (bei Buchverlust) |
| 6890 | Erlöse aus Verkäufen immaterieller Vermögensgegenstände (bei Buchverlust) |
| 6891 | Erlöse aus Verkäufen Finanzanlagen (bei Buchverlust) |
| 6892 | Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (bei Buchverlust) |
| 6930 | Forderungsverluste (übliche Höhe) |
| 6934 | Forderungsverluste aus im Inland steuerpfl. EU-Lieferungen 16 % USt (übliche Höhe) (ERPNext) |
| 6935 | Forderungsverluste 16% USt (übliche Höhe) (ERPNext) |
| 6937 | Forderungsverluste 15% USt (übliche Höhe) (ERPNext) |
| 6939 | Forderungsverluste aus im Inland steuerpfl. EU-Lieferungen 15% USt (übliche Höhe) (ERPNext) |

Die beiden Listen entsprechen sich Konto für Konto, mit zwei Ausnahmen: Nur in SKR03 steht 8600 aus einer verbreiteten SKR03-Variante. Nur in SKR04 stehen 4330, 4723, 4729, 5726, 5727, 6285, 6287, 6934, 6935, 6937 und 6939, Konten zu 15 und 16 % aus der Vorlage von ERPNext ohne Gegenstück in SKR03. 5744, 4499 und 4869 beobachtet SKR04 als Gegenstücke von 3744, 8499 und 8853, obwohl der Kontenrahmen sie ohne „U“ führt.

### Übergang eines Saldos in eine spätere Voranmeldung

Die beobachteten Konten 1548 „Vorsteuer in Folgeperiode/im Folgejahr abziehbar“ und 1725 „Umsatzsteuer nicht fällig“ (SKR04: 1434 und 3865, `TIMING_ACCOUNTS` in [`defaults.py`](../steuerbote/ustva/defaults.py)) tragen einen Betrag in eine spätere Voranmeldung: Vorsteuer ist erst abziehbar, wenn Leistung und Rechnung vorliegen (§ 15 Abs. 1 Satz 1 Nr. 1 UStG; „Fallen Empfang der Leistung und Empfang der Rechnung zeitlich auseinander, ist der Vorsteuerabzug für den Besteuerungszeitraum zulässig, in dem erstmalig beide Voraussetzungen erfüllt sind“, UStAE 15.2 Abs. 2 Satz 6). Den Saldo, den ein solches Konto in einen Zeitraum mitbringt, löst dieser Zeitraum auf, etwa im Januar auf 1576, und der Betrag geht über das Gegenkonto in dessen Kennzahl.

Eine solche Auflösung hält die Voranmeldung nicht an ([`carried.py`](../steuerbote/ustva/carried.py)): Bewegt sich ein Konto dieser Liste, das auf der Stufe „Sperrt“ beobachtet ist, im Zeitraum gegen den Saldo, den es aus der Zeit davor trägt, und um nicht mehr als diesen, steht es nicht unter „Nicht zugeordnet“, sondern als Hinweis `KONTO-BEOBACHTET` mit dem aufgelösten und dem mitgebrachten Betrag. Den mitgebrachten Saldo liest Steuerbote aus allen Buchungen bis zum Ende des Zeitraums, die Eröffnungsbuchungen und die Journalbuchungen mit „Nicht in der Umsatzsteuer-Voranmeldung“ eingeschlossen, abzüglich der Bewegung des Zeitraums (`closing_balances` in `steuerbote/ledger.py`). Ein neuer Saldo, eine Bewegung in die Richtung des Saldos oder mehr als der mitgebrachte Betrag sperren weiter, ebenso jedes andere beobachtete Konto. Das gilt jedes Jahr für den Übergang vom Dezember in den Januar und ebenso für den Saldo der Eröffnungsbuchungen eines Unternehmens, das im laufenden Betrieb mit Steuerbote beginnt (siehe [Einrichtung](einrichtung.md#start-mit-steuerbote-im-laufenden-betrieb)); über das Jahr gerechnet ebenso in der Umsatzsteuererklärung (`SB-KONTO-AUFGELOEST`). Der Bericht „UStVA Kennzahlen“ folgt derselben Regel (`released` in `vat_return.py`): Er nennt am Anfang jedes Konto, das die Voranmeldung des Zeitraums sperrt, und jede Auflösung mit demselben Hinweis wie die Voranmeldung (`blocked_notes` in `steuerbote/steuerbote/report/ustva_kennzahlen/comparison.py`).

### Beobachtete Konten mit Hinweis

Diese Konten beobachten die Vorgaben auf der Stufe „Hinweis“: Ihr Saldo kann in die Voranmeldung gehören, meist gehört er nicht hinein. Hat eines davon im Zeitraum einen Saldo, steht es mit Soll und Haben in `hinted`, und die Meldung bekommt den Hinweis `KONTO-BEOBACHTET` mit Kontonummer, Bezeichnung, Soll, Haben und Saldo. Bereit bleibt sie trotzdem.

8603, 8605 und 8606 (SKR04: 4830, 4835 und 4832) sind sonstige betriebliche Erträge ohne „U“. Über der Kontenklasse druckt der Kontenrahmen 2026 für sie die Zusatzfunktion „Umsatzsteuer“: „M 8194-8603“ und „M 8605-8613“, in SKR04 „M 4830-4837“, erläutert unter „Zusatzfunktionen (über einer Kontenklasse)“ als „M Zusatzfunktion ‚Umsatzsteuer‘“. Auf diesen Konten lässt sich also mit Umsatzsteuer buchen, ohne dass der Kontenrahmen sie an die Umsatzsteuererklärung weitergibt. Steuerpflichtiges, das mit seiner Steuer darauf gebucht ist, zeigt die Verprobung, denn die Steuer steht dann ohne Grundlage auf 1776 oder 1771 (SKR04: 3806 oder 3801). Steuerfreies, etwa ein Umsatz nach § 4 Nr. 8 UStG für Kz 48, zeigt sie nicht; dafür steht der Hinweis.

| SKR03 | Bezeichnung laut Kontenrahmen 2026 |
|---|---|
| 8603 | Sonstige betriebliche Erträge |
| 8605 | Sonstige Erträge betrieblich und regelmäßig |
| 8606 | Sonstige betriebliche Erträge von verbundenen Unternehmen |

| SKR04 | Bezeichnung laut Kontenrahmen 2026 |
|---|---|
| 4830 | Sonstige betriebliche Erträge |
| 4835 | Sonstige Erträge betrieblich und regelmäßig |
| 4832 | Sonstige betriebliche Erträge von verbundenen Unternehmen |

In ihrer Kontenzuordnung setzt jede Firma jedes beobachtete Konto auf eine der beiden Stufen und kann weitere Konten beobachten. Die Stufe „Hinweis“ passt zu Konten, deren Einordnung die Steuerberatung noch klärt, etwa Erträge und Aufwendungen aus dem Handel mit Wertpapieren oder Devisen, Zinsen und Gebühren (siehe [Für die Steuerberatung zu klären](architektur.md#für-die-steuerberatung-zu-klären)). In den Vorgaben stehen solche Konten nicht: Der Kontenrahmen 2026 kennzeichnet etwa 2650, 2654, 2166 und 4970 weder mit „U“ noch mit der Zusatzfunktion „Umsatzsteuer“, und ob ihr Saldo in eine Kennzahl gehört, hängt von der Tätigkeit der Firma ab.

### Bewusst ohne Kennzahl

Diese Konten gibt der Kontenrahmen, eine Vorlage von ERPNext oder eine verbreitete SKR03-Variante an die Umsatzsteuer weiter, die Voranmeldung hat für sie aber keine Kennzahl. Die Vorgaben ordnen sie deshalb nicht zu und beobachten sie nicht. Sie stehen in `SKR03_IGNORED` und `SKR04_IGNORED`, damit `test_completeness.py` sie als entschieden kennt. Dazu gehören die Konten des OSS-Verfahrens, 1728, 1729, 1767, 1768 und 1798 (SKR04: 3798, 3817, 3818 und 3831): Ihre Umsatzsteuer erklärt die Firma dem Bundeszentralamt für Steuern, sie bekommt deshalb nie eine Kennzahl der Voranmeldung. Konten, auf denen ein Saldo nur eine Frage des Zeitpunkts ist, bleiben dagegen beobachtet (siehe [Beobachtete Konten](#beobachtete-konten)).

| SKR03 | Bezeichnung laut Kontenrahmen 2026 | Grund |
|---|---|---|
| 1543 | Forderungen an das Finanzamt aus abgeführtem Bauabzugsbetrag | Bauabzugsbetrag nach § 48 EStG, keine Umsatzsteuer |
| 1593 | Verrechnungskonto erhaltene Anzahlungen bei Buchung über Debitorenkonto | Verrechnungskonto. Die versteuerten Anzahlungen stehen auf 1711 bis 1718. |
| 1390 | Verrechnungskonto Ist-Versteuerung | Verrechnungskonto für die Ist-Versteuerung, im Kontenrahmen mit der Funktion F wie 1490 in SKR04 |
| 1728 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen elektronischen Dienstleistungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 1767 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen Lieferungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 1768 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen/Werklieferungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 1798 | Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen, nur OSS | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 1780 | Umsatzsteuer-Vorauszahlungen | Zahlung an das Finanzamt |
| 1781 | Umsatzsteuer-Vorauszahlungen 1/11 | Zahlung der Sondervorauszahlung an das Finanzamt. Die Sondervorauszahlung geht über `extra_values` in Kz 39 ein. |
| 3089 | Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 1794 in Kz 69, die Vorsteuer über 1573 in Kz 66. |
| 3552 | Erwerb 1. Abnehmer innerhalb eines Dreiecksgeschäftes | Dreiecksgeschäft, erster Abnehmer: Sein Erwerb gilt als besteuert (§ 25b Abs. 3 UStG) und wird nicht gemeldet. |
| 3553 | Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 1794 in Kz 69, die Vorsteuer über 1573 in Kz 66. |
| 3792 | Erhaltene Skonti aus Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 1794 in Kz 69, die Vorsteuer über 1573 in Kz 66. |
| 3793 | Erhaltene Skonti aus Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 1794 in Kz 69, die Vorsteuer über 1573 in Kz 66. |
| 0985 | Als Aufwand berücksichtigte Umsatzsteuer auf Anzahlungen | Umsatzsteuer auf Anzahlungen, in der Bilanz abgegrenzt |
| 1545 | Forderungen aus Umsatzsteuer-Vorauszahlungen | Verrechnung mit dem Finanzamt |
| 1789 | Umsatzsteuer laufendes Jahr | Verrechnung mit dem Finanzamt |
| 1790 | Umsatzsteuerverbindlichkeiten Vorjahr | Verrechnung mit dem Finanzamt |
| 1791 | Umsatzsteuerverbindlichkeiten frühere Jahre | Verrechnung mit dem Finanzamt |
| 1797 | Verbindlichkeiten aus Umsatzsteuer-Vorauszahlungen | Verrechnung mit dem Finanzamt |
| 1788 | Einfuhrumsatzsteuer aufgeschoben bis (SKR03-Variante) | Schuld an den Zoll für die aufgeschobene Einfuhrumsatzsteuer. Der Abzug läuft über 1588 in Kz 62. |
| 1729 | Steuerzahlungen aus im anderen EU-Land steuerpflichtigen Leistungen | OSS, nicht Teil der Voranmeldung |
| 4902 | Interimskonto für Aufwendungen in einem anderen Land, bei denen eine Vorsteuervergütung möglich ist | Vorsteuervergütung anderer Länder |
| 8604 | Erstattete Vorsteuer anderer Länder | Vorsteuervergütung anderer Länder |
| 1371 | Verrechnungskonto Gewinnermittlung § 4 Abs. 3 EStG, nicht ergebniswirksam | EÜR-Konto |
| 1372 | Wirtschaftsgüter des Umlaufvermögens nach § 4 Abs. 3 Satz 4 EStG | EÜR-Konto |
| 1445 | Forderungen aus Lieferungen und Leistungen zum allgemeinen Umsatzsteuersatz oder eines Kleinunternehmers (EÜR) | EÜR-Konto |
| 1446 | Forderungen aus Lieferungen und Leistungen zum ermäßigten Umsatzsteuersatz (EÜR) | EÜR-Konto |
| 1447 | Forderungen aus steuerfreien oder nicht steuerbaren Lieferungen und Leistungen (EÜR) | EÜR-Konto |
| 1448 | Forderungen aus Lieferungen und Leistungen nach Durchschnittssätzen nach § 24 UStG (EÜR) | EÜR-Konto |
| 1450 | Forderungen nach § 11 Abs. 1 Satz 2 EStG für § 4 Abs. 3 EStG | EÜR-Konto |
| 1580 | Gegenkonto Vorsteuer § 4 Abs. 3 EStG | EÜR-Konto |
| 1581 | Auflösung Vorsteuer aus Vorjahr § 4 Abs. 3 EStG | EÜR-Konto |
| 1582 | Vorsteuer aus Investitionen § 4 Abs. 3 EStG | EÜR-Konto |
| 1583 | Gegenkonto für Vorsteuer nach Durchschnittssätzen für § 4 Abs. 3 EStG (SKR03-Variante) | EÜR-Konto |
| 1605 | Verbindlichkeiten aus Lieferungen und Leistungen zum allgemeinen Umsatzsteuersatz (EÜR) | EÜR-Konto |
| 1606 | Verbindlichkeiten aus Lieferungen und Leistungen zum ermäßigten Umsatzsteuersatz (EÜR) | EÜR-Konto |
| 1607 | Verbindlichkeiten aus Lieferungen und Leistungen ohne Vorsteuerabzug (EÜR) | EÜR-Konto |
| 1624 | Verbindlichkeiten aus Lieferungen und Leistungen für Investitionen für § 4 Abs. 3 EStG | EÜR-Konto |
| 1704 | Sonstige Verbindlichkeiten nach § 11 Abs. 2 Satz 2 EStG für § 4 Abs. 3 EStG | EÜR-Konto |
| 1756 | Lohn- und Gehaltsverrechnung nach § 11 Abs. 2 Satz 2 EStG für § 4 Abs. 3 EStG | EÜR-Konto |
| 1795 | Verbindlichkeiten im Rahmen der sozialen Sicherheit für § 4 Abs. 3 EStG | EÜR-Konto |
| 8589 | Gegenkonto 8580-8582 bei Aufteilung der Erlöse nach Steuersätzen (EÜR) | EÜR-Konto |
| 2170 | Nicht abziehbare Vorsteuer | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 2171 | Nicht abziehbare Vorsteuer 7 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 2176 | Nicht abziehbare Vorsteuer 19 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 3600 bis 3609 | Nicht abziehbare Vorsteuer | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 3610 bis 3619 | Nicht abziehbare Vorsteuer 7 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 3660 bis 3669 | Nicht abziehbare Vorsteuer 19 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 4300 | Nicht abziehbare Vorsteuer | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 4301 | Nicht abziehbare Vorsteuer 7 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 4306 | Nicht abziehbare Vorsteuer 19 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 3109 | Fremdleistungen ohne Vorsteuer | Inlandseinkauf ohne Vorsteuer, keine Kennzahl |
| 3349 | Wareneingang ohne Vorsteuerabzug | Inlandseinkauf ohne Vorsteuer, keine Kennzahl |
| 1511 | Geleistete Anzahlungen, 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 1518 | Geleistete Anzahlungen, 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3010 bis 3019 | Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3030 bis 3039 | Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3070 | Einkauf Roh-, Hilfs- und Betriebsstoffe 5,5 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3071 | Einkauf Roh-, Hilfs- und Betriebsstoffe 7,8 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3091 | Energiestoffe (Fertigung) 7 % VSt | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3092 | Energiestoffe (Fertigung) 19 % VSt | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3106 | Fremdleistungen 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3108 | Fremdleistungen 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3300 bis 3309 | Wareneingang 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3400 bis 3409 | Wareneingang 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3505 bis 3509 | Wareneingang 5,5 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3540 bis 3549 | Wareneingang zum Durchschnittssatz nach § 24 UStG 7,8 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3710 bis 3711 | Nachlässe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3714 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3715 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3720 bis 3721 | Nachlässe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3730 | Erhaltene Skonti | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3731 | Erhaltene Skonti 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3733 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3734 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3736 | Erhaltene Skonti 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3738 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3750 bis 3751 | Erhaltene Boni 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3753 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3754 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3755 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3760 bis 3761 | Erhaltene Boni 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3769 | Erhaltene Boni | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3770 | Erhaltene Rabatte | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3780 bis 3781 | Erhaltene Rabatte 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3783 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3784 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3785 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3788 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 10,7 % Vorsteuer (SKR03-Variante) | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3790 bis 3791 | Erhaltene Rabatte 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3794 | Erhaltene Skonti 5,5 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3796 | Erhaltene Skonti 10,7 % Vorsteuer (SKR03-Variante) | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3798 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 5,5 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3551 | Wareneingang im Drittland steuerbar | Wareneingang im Drittland steuerbar, nichts zu melden: Die Lieferung ist im Inland nicht steuerbar (§ 1 Abs. 1 Nr. 1 UStG), die Einfuhrumsatzsteuer einer Einfuhr geht über 1588 in Kz 62. |
| 3557 | Wareneingang, steuerpflichtig im Drittland (7%) (SKR03-Variante) | wie 3551; der Kontenrahmen 2026 hält 3554 bis 3557 frei |
| 3558 | Wareneingang im anderen EU-Land steuerbar | Wareneingang im anderen EU-Land steuerbar, nichts zu melden |
| 3559 | Steuerfreie Einfuhren | steuerfreie Einfuhr, nichts zu melden |
| 8905 | Entnahme von Gegenständen ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8906 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8918 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt (Telefon-Nutzung) | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8919 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8924 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt (Fahrzeug-Nutzung) | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8929 | Unentgeltliche Erbringung einer sonstigen Leistung ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8939 | Unentgeltliche Zuwendung von Gegenständen ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8949 | Unentgeltliche Zuwendung von Waren ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8950 | Nicht steuerbare Umsätze (Innenumsätze) | Innenumsätze, nicht steuerbar |
| 1710 | Erhaltene Anzahlungen auf Bestellungen (Verbindlichkeiten) | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1719 | Erhaltene Anzahlungen - Restlaufzeit bis 1 Jahr | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1720 | - Restlaufzeit 1 bis 5 Jahre | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1721 | - Restlaufzeit größer 5 Jahre | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1722 | Erhaltene Anzahlungen auf Bestellungen (von Vorräten offen abgesetzt) | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1793 | Verrechnungskonto geleistete Anzahlungen bei Buchung über Kreditorenkonto | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1800 | Privatentnahmen allgemein | Privat- oder Kapitalkonto, nur Einzelunternehmen |
| 1880 | Unentgeltliche Wertabgaben | Privat- oder Kapitalkonto, nur Einzelunternehmen |
| 1869 | Grundstücksaufwand (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen) 10)22) | Privat- oder Kapitalkonto, nur Einzelunternehmen |
| 1879 | Grundstücksertrag (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen) 10)22) | Privat- oder Kapitalkonto, nur Einzelunternehmen |
| 1900 | Auszahlungen allgemein (Teilhafter), Fremdkapital | Konto eines Teilhafters |
| 1980 | Unentgeltliche Wertabgaben (Teilhafter), Fremdkapital | Konto eines Teilhafters |
| 8650 | Erlöse Zinsen und Diskontspesen | von DATEV nicht als umsatzsteuerrelevant gekennzeichnet, Zinserlöse laufen über 2650 |
| 8660 | Erlöse Zinsen und Diskontspesen aus verbundenen Unternehmen | von DATEV nicht als umsatzsteuerrelevant gekennzeichnet, Zinserlöse laufen über 2650 |

| SKR04 | Bezeichnung laut Kontenrahmen 2026 | Grund |
|---|---|---|
| 1456 | Forderungen an das Finanzamt aus abgeführtem Bauabzugsbetrag | Bauabzugsbetrag nach § 48 EStG, keine Umsatzsteuer |
| 1495 | Verrechnungskonto erhaltene Anzahlungen bei Buchung über Debitorenkonto | Verrechnungskonto. Die versteuerten Anzahlungen stehen auf 3260 bis 3272. |
| 3798 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen elektronischen Dienstleistungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 3817 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen Lieferungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 3818 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen/Werklieferungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 3831 | Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen, nur OSS | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 3820 | Umsatzsteuer-Vorauszahlungen | Zahlung an das Finanzamt |
| 3830 | Umsatzsteuer-Vorauszahlungen 1/11 | Zahlung der Sondervorauszahlung an das Finanzamt. Die Sondervorauszahlung geht über `extra_values` in Kz 39 ein. |
| 5189 | Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 3819 in Kz 69, die Vorsteuer über 1436 in Kz 66. |
| 5552 | Erwerb 1. Abnehmer innerhalb eines Dreiecksgeschäftes | Dreiecksgeschäft, erster Abnehmer: Sein Erwerb gilt als besteuert (§ 25b Abs. 3 UStG) und wird nicht gemeldet. |
| 5553 | Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 3819 in Kz 69, die Vorsteuer über 1436 in Kz 66. |
| 5792 | Erhaltene Skonti aus Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 3819 in Kz 69, die Vorsteuer über 1436 in Kz 66. |
| 5793 | Erhaltene Skonti aus Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 3819 in Kz 69, die Vorsteuer über 1436 in Kz 66. |
| 5909 | Fremdleistungen ohne Vorsteuer | Inlandseinkauf ohne Vorsteuer, keine Kennzahl |
| 1427 | Forderungen aus entrichteten Verbrauchsteuern | Verbrauchsteuer, keine Umsatzsteuer |
| 1460 | Geldtransit | Geldtransit, keine Umsatzsteuer |
| 1486 | Verrechnungskonto für Gewinnermittlung § 4 Abs. 3 EStG, nicht ergebniswirksam | Verrechnungskonto für die Gewinnermittlung nach § 4 Abs. 3 EStG |
| 1490 | Verrechnungskonto Ist-Versteuerung | Verrechnungskonto für die Ist-Versteuerung |
| 1491 | Neutralisierung ertragswirksamer Sachverhalte für § 4 Abs. 3 EStG | Neutralisierung für die Gewinnermittlung nach § 4 Abs. 3 EStG |
| 1420 | Forderungen aus Umsatzsteuer-Vorauszahlungen | Forderung an das Finanzamt |
| 1421 | Umsatzsteuerforderungen laufendes Jahr (ERPNext) | Forderung an das Finanzamt |
| 1422 | Umsatzsteuerforderungen Vorjahr | Forderung an das Finanzamt |
| 1425 | Umsatzsteuerforderungen frühere Jahre | Forderung an das Finanzamt |
| 1930 | Als Aufwand berücksichtigte Umsatzsteuer auf Anzahlungen | Umsatzsteuer auf Anzahlungen, in der Bilanz abgegrenzt |
| 3850 | Einfuhrumsatzsteuer aufgeschoben bis (ERPNext) | Schuld an den Zoll für die aufgeschobene Einfuhrumsatzsteuer. Der Abzug läuft über 1433 in Kz 62. |
| 4605 | Entnahme von Gegenständen ohne USt | ohne Umsatzsteuer, nichts zu melden |
| 4637 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt | ohne Umsatzsteuer, nichts zu melden |
| 4638 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt (Telefon-Nutzung) | ohne Umsatzsteuer, nichts zu melden |
| 4639 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt (Fahrzeug-Nutzung) | ohne Umsatzsteuer, nichts zu melden |
| 4659 | Unentgeltliche Erbringung einer sonstigen Leistung ohne USt | ohne Umsatzsteuer, nichts zu melden |
| 4679 | Unentgeltliche Zuwendung von Waren ohne USt | ohne Umsatzsteuer, nichts zu melden |
| 4689 | Unentgeltliche Zuwendung von Gegenständen ohne USt | ohne Umsatzsteuer, nichts zu melden |
| 4690 | Nicht steuerbare Umsätze (Innenumsätze) | Innenumsätze werden nicht gemeldet (Anleitung zu Zeile 36) |
| 4838 | Erstattete Vorsteuer anderer Länder | Vorsteuer anderer Staaten, nicht Teil der Voranmeldung |
| 6302 | Interimskonto für Aufwendungen in einem anderen Land, bei denen eine Vorsteuervergütung möglich ist | Vorsteuer anderer Staaten, nicht Teil der Voranmeldung |
| 1181 | Geleistete Anzahlungen 7 % Vorsteuer | Geleistete Anzahlung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 1184 | Geleistete Anzahlungen, 16 % Vorsteuer | Geleistete Anzahlung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 1185 | Geleistete Anz., 15 % Vorsteuer (ERPNext) | Geleistete Anzahlung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 1186 | Geleistete Anzahlungen 19 % Vorsteuer | Geleistete Anzahlung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5110 bis 5119 | Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5130 bis 5139 | Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5170 | Einkauf Roh-, Hilfs- und Betriebsstoffe 5,5 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5171 | Einkauf Roh-, Hilfs- und Betriebsstoffe 7,8 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5191 | Energiestoffe (Fertigung) 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5192 | Energiestoffe (Fertigung) 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5300 bis 5309 | Wareneingang 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5400 bis 5409 | Wareneingang 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5505 bis 5509 | Wareneingang 5,5 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5540 bis 5549 | Wareneingang zum Durchschnittssatz nach § 24 UStG 7,8 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5710 bis 5711 | Nachlässe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5714 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5715 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5720 bis 5721 | Nachlässe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5722 | Nachlässe 16 % Vorsteuer (ERPNext) | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5723 | Nachlässe 15 % Vorsteuer (ERPNext) | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5730 | Erhaltene Skonti | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5731 | Erhaltene Skonti 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5733 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5734 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5736 | Erhaltene Skonti 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5738 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5750 bis 5751 | Erhaltene Boni 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5753 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5754 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5755 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5760 bis 5761 | Erhaltene Boni 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5769 | Erhaltene Boni | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5770 | Erhaltene Rabatte | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5780 bis 5781 | Erhaltene Rabatte 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5783 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5784 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5785 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5790 bis 5791 | Erhaltene Rabatte 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5906 | Fremdleistungen 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5551 | Wareneingang im Drittland steuerbar | im Drittland steuerbar, nichts zu melden: Die Lieferung ist im Inland nicht steuerbar (§ 1 Abs. 1 Nr. 1 UStG), die Einfuhrumsatzsteuer einer Einfuhr geht über 1433 in Kz 62. |
| 5558 | Wareneingang im anderen EU-Land steuerbar | im anderen EU-Land steuerbar, nichts zu melden |
| 5559 | Steuerfreie Einfuhren | steuerfreie Einfuhr, nichts zu melden |
| 5600 bis 5609 | Nicht abziehbare Vorsteuer | nicht abziehbare Vorsteuer, ein Aufwand |
| 5610 bis 5619 | Nicht abziehbare Vorsteuer 7 % | nicht abziehbare Vorsteuer, ein Aufwand |
| 5660 bis 5669 | Nicht abziehbare Vorsteuer 19 % | nicht abziehbare Vorsteuer, ein Aufwand |
| 6871 | Nicht abziehbare Vorsteuer 19 % | nicht abziehbare Vorsteuer, ein Aufwand |
| 1190 | Erhaltene Anzahlungen auf Bestellungen (von Vorräten offen abgesetzt) | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |
| 3250 | Erhaltene Anzahlungen auf Bestellungen (Verbindlichkeiten) | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |
| 3280 | Erhaltene Anzahlungen – Restlaufzeit bis 1 Jahr | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |
| 3284 | – Restlaufzeit 1 bis 5 Jahre | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |
| 3285 | – Restlaufzeit größer 5 Jahre | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |
| 3695 | Verrechnungskonto geleistete Anzahlungen bei Buchung über Kreditorenkonto | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |

Nur in SKR04 stehen 1427, das dort ein „U“ trägt, und die Verrechnungskonten 1460 und 1491, die SKR04 mit der Funktion F im Bereich 14xx führt. In SKR03 trägt das Gegenstück 1547 kein „U“, und 1360 und 1391 liegen im Bereich 13xx, außerhalb der Bereiche der Vor- und Umsatzsteuer. Dort liegt auch 1390, das Gegenstück von 1490; es steht trotzdem in beiden Vorgaben, denn SKR03 führt es ebenso mit der Funktion F („F 1390 Verrechnungskonto Ist-Versteuerung“). Das Gegenstück von 1486 ist 1371, das SKR03 bei den EÜR-Konten führt. Die übrigen Konten nur einer Vorgabe stammen aus den Vorlagen von ERPNext oder aus verbreiteten SKR03-Varianten. 3798 und 4300 bis 4306 haben in den beiden Vorgaben verschiedene Bedeutungen: In SKR03 sind es Konten älterer Ausgaben für Skonti und nicht abziehbare Vorsteuer, in SKR04 das Konto des OSS-Verfahrens und die Erlöse zu 7 %.

### Beispiel

Der Testfall `VerifiedMonthTest` in [`test_calculation.py`](../steuerbote/ustva/tests/test_calculation.py) hält das an echten Buchungen geprüfte Verhalten fest (SKR03):

| Konto | Soll | Haben | Geht ein in |
|---|---|---|---|
| 8400 | | 1.000,00 | Kz 81, Grundlage der Verprobung „Umsatzsteuer 19 %“ |
| 1776 | | 190,00 | Steuerkonto der Verprobung „Umsatzsteuer 19 %“ |
| 8336 | | 2.000,00 | Kz 21 |
| 8338 | | 500,00 | Kz 45 |
| 3123 | 300,00 | | Kz 46, daraus Kz 47 mit 19 % |
| 1787 | | 57,00 | Steuerkonto der Verprobung „Umsatzsteuer nach § 13b UStG 19 %“ |
| 1577 | 57,00 | | Kz 67 |
| 1576 | 95,00 | | Kz 66 |

Ergebnis: Kz 81 = 1.000, Kz 21 = 2.000, Kz 45 = 500, Kz 46 = 300, Kz 47 = 57,00, Kz 66 = 95,00 und Kz 67 = 57,00. Zeile 37 ergibt 247,00 (190,00 aus Kz 81 und 57,00 aus Kz 47), die Zeilen 38 bis 44 ergeben 152,00, Zeile 45 und Zeile 48 je 95,00 und Kz 83 = 95,00. Beide Verprobungen mit Buchungen gehen auf den Cent auf, kein beobachtetes Konto hat einen Saldo, die Meldung ist bereit.

### Noch nicht zugeordnet

Diesen Kennzahlen ordnen die Vorgaben bewusst kein Konto zu:

| Kennzahlen | Fälle |
|---|---|
| 35/36 | Umsätze zu anderen Steuersätzen |
| 77, 76/80 | Land- und Forstwirtschaft nach § 24 UStG |
| 49 | innergemeinschaftliche Lieferungen neuer Fahrzeuge außerhalb eines Unternehmens (§ 2a UStG) |
| 90, 95/98 | innergemeinschaftliche Erwerbe zu 0 % und zu anderen Steuersätzen |
| 73/74 | Umsätze, die unter das GrEStG fallen |
| 59 | Vorsteuerabzug nach § 15 Abs. 4a UStG |
| 37 | Minderung der abziehbaren Vorsteuer nach § 17 UStG |
| 39 | Sondervorauszahlung: kommt nicht von einem Konto, sondern über `extra_values` |

Kz 63 (Vorsteuer nach allgemeinen Durchschnittssätzen, § 23a UStG) geht auf 1587 aus verbreiteten SKR03-Varianten und 1484 aus der Vorlage von ERPNext. Kz 50 bekommen die Forderungsverluste zusätzlich zu ihrer Bemessungsgrundlage, denn die Anleitung zu Zeile 51 sagt: „Erfolgt die Änderung nach § 17 Absatz 2 Nummer 1 Satz 1 UStG, weil das vereinbarte Entgelt für einen steuerpflichtigen Umsatz uneinbringlich geworden ist, tragen Sie die Minderung der Bemessungsgrundlage bitte zusätzlich in Zeile 51 ein.“ Kennzeichen, Datum und Schlüssel (Kz 10, 22, 70, 29, 26 und 500) nehmen kein Konto auf, Kz 83 wird berechnet.

Wer einen dieser Fälle hat, klärt Konto und Kennzahl mit der Steuerberatung und ergänzt die Kontenzuordnung Umsatzsteuer des eigenen Unternehmens, siehe [Einrichtung](einrichtung.md). In die Vorgaben kommt eine Kennzahl erst, wenn Konto und Kennzahl bestätigt sind und eine Quelle dafür vorliegt, nach dem Ablauf in [CONTRIBUTING.md](../CONTRIBUTING.md).

### Prüfung der Steuervorlagen

ERPNext bucht die Steuer einer Rechnung auf die Konten ihrer Steuervorlagen: die Konten der Zeilen einer Vorlage für Verkaufs- oder Einkaufssteuern und die Konten der Steuersätze einer Artikelsteuervorlage. Die Voranmeldung enthält „die Steuer für den Voranmeldungszeitraum“ (§ 18 Absatz 1 Satz 1 UStG), ein Konto ohne Platz in der Zuordnung aber geht in keine Kennzahl ein. [`tax_templates.py`](../steuerbote/ustva/tax_templates.py) nennt deshalb jedes Konto der Steuervorlagen einer Firma, das weder zugeordnet noch verprobt noch beobachtet ist:

- **Bewusst ohne Kennzahl** bleiben außen vor: die Konten von `SKR03_IGNORED` und `SKR04_IGNORED` samt ihrer Kontenbereiche, wenn die Kontenzuordnung diesen Kontenrahmen nennt (`deliberately_without_kennzahl` in `defaults.py`). Dazu gehört die Umsatzsteuer des OSS-Verfahrens, die die Firma in der Steuererklärung des besonderen Besteuerungsverfahrens erklärt (§ 18j Absatz 4 UStG), nicht in der Voranmeldung.
- **Ohne Kontonummer** hat ein Konto nie einen Platz, denn die Zuordnung arbeitet mit Kontonummern.
- **Je Konto** sagt der Hinweis `STEUERVORLAGE-OHNE-KENNZAHL` an der Meldung, aus welchen Vorlagen das Konto kommt und ob es im Zeitraum einen Saldo hat, mit Soll und Haben. Er hält die Meldung nicht an.

In der Kontenzuordnung nennt „Steuervorlagen prüfen“ dieselben Konten und nimmt sie auf Wunsch in einem Schritt als beobachtete Konten der Stufe „Sperrt“ auf. Ein Saldo auf einem von ihnen hält die Meldung dann an, bis das Konto eine Zuordnung hat. Wie die Frappe-Schicht die Vorlagen liest, steht in [Architektur](architektur.md#prüfung-der-steuervorlagen).

## Kontenzuordnung der Umsatzsteuererklärung

Die Umsatzsteuererklärung (Vordruck USt 2 A 2026) liest dieselbe Kontenzuordnung wie die Voranmeldung. Sie ist aber keine Summe der Voranmeldungen: Zehn Kennzahlen der Voranmeldung verteilen sich in der Erklärung auf mehrere Zeilen, und einige Beträge kennt nur die Erklärung. Dafür trägt die Kontenzuordnung drei Angaben, die die Voranmeldung nicht liest. Quellen sind das BMF-Schreiben vom 29. Dezember 2025, GZ III C 3 - S 7344/00040/008/034, „Muster der Umsatzsteuererklärung 2026“, mit dem Vordruck USt 2 A und seiner Anleitung USt 2 E 2026 (<https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/2025-12-29-muster-USt-erklaerung-2026.pdf>), und die `Jahresdokumentation_E50_2026.ods` (Versionslabel 9.0) der ERiC-Dokumentation 44.3.6.0. Den Katalog der Felder hält [`ustjahr/form.py`](../steuerbote/ustjahr/form.py).

### Felder der Umsatzsteuererklärung

- **Feld der Umsatzsteuererklärung** (`annual_field`) an einer Zuordnung: die Feldkennung der Zeile, in die der Saldo des Kontos im Jahr geht, etwa E3003405 für Kz 178 in Zeile 25. Leer nimmt das Konto die Vorgabe seiner Rolle im Kontenrahmen oder die Vorgabezeile seiner Kennzahl.
- **Paragraf der Steuerbefreiung** (`paragraph`) an einer Zuordnung: Die Zeilen 46, 52 und 54 drucken „Umsätze nach § … UStG“, „nach § 4 Nummer … UStG“ und „nach § … UStG“. Ein Betrag in einer dieser Zeilen braucht den Paragrafen, den die Zuordnung seines Kontos nennt, etwa „4 Nummer 14“, sonst meldet die Erklärung `PARAGRAF-FEHLT`. Vorgaben gibt es dafür nicht.
- **Zuordnungen nur für die Umsatzsteuererklärung** (Tabelle `annual_rules`, „Zuordnung nur für die Umsatzsteuererklärung“): Konto, Feld der Umsatzsteuererklärung, Seite und Paragraf eines Kontos, dessen Saldo keine Kennzahl der Voranmeldung aufnimmt, etwa der Erwerb des ersten Abnehmers in einem innergemeinschaftlichen Dreiecksgeschäft für Kz 789 in Zeile 55, neu 2026. Ein beobachtetes Konto darf hier stehen. Ein Konto, das die Zuordnung einer Kennzahl zuordnet oder als Steuerkonto einer Verprobung führt, darf es nicht, sonst zählte sein Saldo doppelt.

Jedes Konto bekommt seine Zeile so ([`split.py`](../steuerbote/ustjahr/split.py)):

1. das Feld der Umsatzsteuererklärung seiner Zuordnung;
2. die Vorgabe seiner Rolle im Kontenrahmen, siehe [Vorgaben der Umsatzsteuererklärung](#vorgaben-der-umsatzsteuererklärung);
3. die Vorgabezeile seiner Kennzahl oder ihre einzige Zeile, etwa Zeile 24 für Kz 81, Zeile 46 für Kz 43, Zeile 52 für Kz 48, Zeile 85 für Kz 66 und Zeile 119 für Kz 69. Kz 65 geht in Zeile 40 (Kz 319), mit dem Hinweis `NACHSTEUER-ZEILE`.

Die Zeile muss die Beträge der Kennzahl der Zuordnung nehmen. Ein Feld, das das nicht tut, lehnt die Kontenzuordnung ab; eine solche Rollenvorgabe bleibt unbeachtet, denn dann hat die Firma das Konto einer anderen Kennzahl zugeordnet, als seine Rolle nahelegt. So ergeben die Zeilen einer Kennzahl zusammen ihren Jahresbetrag, und der Abgleich mit den Voranmeldungen geht Kennzahl für Kennzahl auf. Kz 64, die Berichtigung des Vorsteuerabzugs nach § 15a UStG, hat keine Vorgabezeile: Die Art des Wirtschaftsguts entscheidet zwischen den Zeilen 105, 106 und 107, ihr Konto braucht deshalb eine Rolle oder ein Feld.

Beim Speichern prüft die Kontenzuordnung jedes Feld, jeden Paragrafen und jede Zuordnung nur für die Umsatzsteuererklärung gegen den neuesten Vordruck USt 2 A (`check_annual_rows` in [`mapping_sync.py`](../steuerbote/mapping_sync.py)) und lehnt ab, was nicht passt, mit dem Grund. Die Zeile eines Kontos von Kz 64 ohne Feld und Rolle verlangt erst die Umsatzsteuererklärung, denn die Voranmeldung braucht sie nicht. `to_split(year)` gibt der Erklärung eines Jahres die Zeile jedes Kontos.

„Vorgaben laden“ füllt die Zuordnungen nur für die Umsatzsteuererklärung aus den Vorgaben des Kontenrahmens für die Konten, die das Unternehmen hat, und behält Feld und Paragraf einer Zuordnung, deren Konto seine Kennzahl behält. „Vorgaben aktualisieren“ und die Datei der Zuordnung führen Feld und Paragraf eines Kontos und jede Zuordnung nur für die Umsatzsteuererklärung als eigene Zeilen, siehe [Einrichtung](einrichtung.md#vorgaben-aktualisieren). Eine Zuordnung, die ihre Vorgaben vor diesen Zeilen übernommen hat, bekommt die Zuordnungen nur für die Umsatzsteuererklärung dort als Änderungen der Vorgaben vorgeschlagen.

### Vorgaben der Umsatzsteuererklärung

[`ustjahr/defaults.py`](../steuerbote/ustjahr/defaults.py) bringt für SKR03 und SKR04 je Jahr des Vordrucks zwei Tabellen mit: die Zeile je Rolle (`ROLE_FIELDS`), nur wo sie nicht die Vorgabezeile ihrer Kennzahl ist, und die Konten nur für die Umsatzsteuererklärung (`ANNUAL_ACCOUNTS`). Die Rollen sind die der [Vorgaben](#vorgaben) der Voranmeldung, jedes Konto eines Kontenbereichs nimmt die Vorgabe seines ersten Kontos. Ein eigener Kontenrahmen bekommt keine Vorgaben: Seine Zuordnungen nennen ihre Felder selbst.

Die Zeilen der Rollen folgen der Anleitung USt 2 E 2026:

- **Unentgeltliche Wertabgaben** sind „in der Regel den entgeltlichen Lieferungen“ und „in der Regel den entgeltlichen sonstigen Leistungen gleichgestellt“ (Zeilen 24 bis 33): Entnahme und unentgeltliche Zuwendung von Gegenständen sind Lieferungen nach § 3 Absatz 1b UStG (Zeilen 25 und 28), die Verwendung von Gegenständen und die unentgeltliche Erbringung einer sonstigen Leistung sonstige Leistungen nach § 3 Absatz 9a UStG (Zeilen 26 und 29). Sachbezüge bleiben in den Zeilen 24 und 27, denn ob ein Sachbezug unentgeltlich ist, hängt vom Fall ab; das ist nicht geprüft.
- **Steuerfreie Umsätze mit Vorsteuerabzug:** „Bitte tragen Sie in Zeile 45 steuerfreie Ausfuhrlieferungen ein (§ 4 Nummer 1 Buchstabe a, § 6 UStG)“, die Umsätze im Sinne des Offshore-Steuerabkommens gehören in Zeile 47 und die Reiseleistungen nach § 25 Absatz 2 UStG in Zeile 49 (Zeile 45, Zeilen 46 bis 50). Die Konten nach § 4 Nummer 1 Buchstabe a UStG nehmen auch Lohnveredelungen nach § 7 UStG auf, die in Zeile 46 gehören: Ein Konto, das sie hält, braucht das Feld dieser Zeile.
- **Steuerfreie Umsätze ohne Vorsteuerabzug:** Zeile 51 nimmt die „Vermietung und Verpachtung von Grundstücken“ nach § 4 Nummer 12 UStG, Zeile 53 die Umsätze eines Kleinunternehmers nach § 19 Absatz 1 UStG und Zeile 54 die Umsätze, „die zum Gesamtumsatz nach § 19 Absatz 2 UStG gehören“, wie die Konten „zum Gesamtumsatz gehörend“ sie führen (Zeilen 51 bis 54). Jeder andere steuerfreie Umsatz ohne Vorsteuerabzug geht in Zeile 52, die Vorgabezeile von Kz 48.
- **Vorsteuer:** Zeile 88 nimmt die Vorsteuer aus der Steuer, die der Unternehmer als Auslagerer aus einem Umsatzsteuerlager schuldet, Zeile 92 die aus innergemeinschaftlichen Dreiecksgeschäften (Zeilen 85 bis 93).
- **Berichtigung des Vorsteuerabzugs nach § 15a UStG** nach der Art des Wirtschaftsguts: Zeile 105 für Grundstücke mit einem Berichtigungszeitraum von zehn Jahren, Zeile 106 für übrige Wirtschaftsgüter und sonstige Leistungen, Zeile 107 für solche, die nur einmalig zur Ausführung von Umsätzen verwendet werden, je mit der Spalte „nachträglich abziehbar“ und der Spalte „zurückzuzahlen“ (Zeilen 95 bis 108). DATEV führt sie als § 15a Absatz 1 UStG für unbewegliche und bewegliche Wirtschaftsgüter und § 15a Absatz 2 UStG.
- **Steuern aus Kz 69:** die Steuer, „die der letzte Abnehmer nach § 25b Absatz 2 UStG für die Lieferung des ersten Abnehmers schuldet“, zu 19 % in Zeile 66 (Zeilen 65 bis 70), und die Steuer des Auslagerers in Zeile 63. Das Konto der Auslagerung, SKR03 1769 und SKR04 3839, beobachten die Vorgaben der Voranmeldung, denn seine Kennzahl ist dort nicht entschieden; sobald die Firma es Kz 69 zuordnet, nimmt es Zeile 63.

Die steuerpflichtigen Umsätze nach §§ 25 und 25a UStG (SKR03 8198 und 8199, SKR04 4133 und 4134) bleiben außen vor: Die Zeilen 37 und 38 übermittelt Steuerbote nicht.

Die Vorgaben haben einen Stand aus Kontenrahmen, „USt“ für die Umsatzsteuererklärung, Jahr des Vordrucks und Revision, heute „SKR03 USt 2026.1“ und „SKR04 USt 2026.1“ (`defaults_version` in `ustjahr/defaults.py`). Jede Änderung der Vorgaben eines Jahres erhöht seine Revision in `REVISIONS`; `DefaultsVersionTest` in [`ustjahr/tests/test_defaults.py`](../steuerbote/ustjahr/tests/test_defaults.py) hält die SHA-256-Summe des Inhalts jedes Stands fest. In der Kontenzuordnung stehen die Zeilen dieser Vorgaben bei den übernommenen Vorgaben (`defaults_rows`), so findet „Vorgaben aktualisieren“ auch ihre Änderungen; das Feld „Stand der Vorgaben“ nennt den Stand der Vorgaben der Voranmeldung. [`ustjahr/tests/test_defaults.py`](../steuerbote/ustjahr/tests/test_defaults.py) hält jede Rolle und jedes Konto beider Kontenrahmen fest und prüft die Spiegelung, [`ustjahr/tests/test_docs.py`](../steuerbote/ustjahr/tests/test_docs.py), dass die Tabellen dieses Abschnitts genau den Code zeigen.

### Vorgabe der Zeilen

Die Spalte Kz nennt die Kennzahl der Voranmeldung, der die Vorgaben das Konto zuordnen; „beobachtet“ heißt, dass die Vorgaben der Voranmeldung das Konto beobachten. Feld und Zeile sind die des Vordrucks USt 2 A 2026, mit der Kennzahl, die der Vordruck druckt.

| SKR03 | Bezeichnung laut Kontenrahmen 2026 | Kz | Feld | Zeile |
|---|---|---|---|---|
| 8910 bis 8913 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 19 % USt | 81 | E3003405 (Kz 178) | 25 |
| 8935 bis 8937 | Unentgeltliche Zuwendung von Gegenständen 19 % USt | 81 | E3003405 (Kz 178) | 25 |
| 8940 bis 8943 | Unentgeltliche Zuwendung von Waren 19 % USt | 81 | E3003405 (Kz 178) | 25 |
| 8920 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt | 81 | E3003505 (Kz 179) | 26 |
| 8921 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Fahrzeug-Nutzung) | 81 | E3003505 (Kz 179) | 26 |
| 8922 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Telefon-Nutzung) | 81 | E3003505 (Kz 179) | 26 |
| 8925 bis 8927 | Unentgeltliche Erbringung einer sonstigen Leistung 19 % USt | 81 | E3003505 (Kz 179) | 26 |
| 8915 bis 8916 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | E3003703 (Kz 195) | 28 |
| 8917 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | E3003703 (Kz 195) | 28 |
| 8945 bis 8946 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | E3003703 (Kz 195) | 28 |
| 8947 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | E3003703 (Kz 195) | 28 |
| 8930 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | E3003803 (Kz 196) | 29 |
| 8931 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | E3003803 (Kz 196) | 29 |
| 8932 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | E3003803 (Kz 196) | 29 |
| 8933 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | E3003803 (Kz 196) | 29 |
| 8120 | Steuerfreie Umsätze nach § 4 Nr. 1a UStG | 43 | E3103801 (Kz 752) | 45 |
| 8807 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchverlust) | 43 | E3103801 (Kz 752) | 45 |
| 8827 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchgewinn) | 43 | E3103801 (Kz 752) | 45 |
| 8705 | Erlösschmälerungen aus steuerfreien Umsätzen § 4 Nr. 1a UStG | 43 | E3103801 (Kz 752) | 45 |
| 8140 | Steuerfreie Umsätze Offshore usw. | 43 | E3104001 | 47 |
| 8194 | Umsatzerlöse aus Reiseleistungen § 25 Abs. 2 UStG, steuerfrei | 43 | E3104101 | 49 |
| 8105 | Steuerfreie Umsätze nach § 4 Nr. 12 UStG (Vermietung und Verpachtung) | 48 | E3104401 (Kz 286) | 51 |
| 2751 | Erlöse aus Vermietung und Verpachtung, umsatzsteuerfrei § 4 Nr. 12 UStG | 48 | E3104401 (Kz 286) | 51 |
| 8192 | Steuerfreie Erlöse Kleinunternehmer nach § 19 Abs. 1 UStG | 48 | E3104701 (Kz 236) | 53 |
| 8195 | Erlöse als Kleinunternehmer nach § 19 Abs. 1 UStG (SKR03-Variante) | 48 | E3104701 (Kz 236) | 53 |
| 8707 | Erlösschmälerungen für steuerfreie Umsätze nach § 19 Abs. 1 UStG | 48 | E3104701 (Kz 236) | 53 |
| 8160 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend, § 4 UStG | 48 | E3104902 (Kz 240) | 54 |
| 8165 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend | 48 | E3104902 (Kz 240) | 54 |
| 1585 | Abziehbare Vorsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager | 66 | E3006503 (Kz 466) | 88 |
| 1573 | Vorsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 66 | E3006801 (Kz 760) | 92 |
| 1558 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | E3008701 | 105 |
| 1559 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | E3008702 | 105 |
| 1556 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | E3008801 | 106 |
| 1557 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | E3008802 | 106 |
| 1528 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 2 UStG | 64 | E3008803 | 107 |
| 1529 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 2 UStG | 64 | E3008804 | 107 |
| 1794 | Umsatzsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 69 | E3101702 | 66 |
| 1769 | Umsatzsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager | beobachtet | E3102805 (Kz 853) | 63 |

| SKR04 | Bezeichnung laut Kontenrahmen 2026 | Kz | Feld | Zeile |
|---|---|---|---|---|
| 4620 bis 4626 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 19 % USt | 81 | E3003405 (Kz 178) | 25 |
| 4686 bis 4687 | Unentgeltliche Zuwendung von Gegenständen 19 % USt | 81 | E3003405 (Kz 178) | 25 |
| 4680 bis 4684 | Unentgeltliche Zuwendung von Waren 19 % USt | 81 | E3003405 (Kz 178) | 25 |
| 4640 bis 4644 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt | 81 | E3003505 (Kz 179) | 26 |
| 4645 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Fahrzeug-Nutzung) | 81 | E3003505 (Kz 179) | 26 |
| 4646 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Telefon-Nutzung) | 81 | E3003505 (Kz 179) | 26 |
| 4660 bis 4666 | Unentgeltliche Erbringung einer sonstigen Leistung 19 % USt | 81 | E3003505 (Kz 179) | 26 |
| 4610 bis 4615 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | E3003703 (Kz 195) | 28 |
| 4616 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | E3003703 (Kz 195) | 28 |
| 4670 bis 4675 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | E3003703 (Kz 195) | 28 |
| 4676 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | E3003703 (Kz 195) | 28 |
| 4630 bis 4635 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | E3003803 (Kz 196) | 29 |
| 4636 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | E3003803 (Kz 196) | 29 |
| 4650 bis 4655 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | E3003803 (Kz 196) | 29 |
| 4656 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | E3003803 (Kz 196) | 29 |
| 4120 | Steuerfreie Umsätze nach § 4 Nr. 1a UStG | 43 | E3103801 (Kz 752) | 45 |
| 6884 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchverlust) | 43 | E3103801 (Kz 752) | 45 |
| 4844 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchgewinn) | 43 | E3103801 (Kz 752) | 45 |
| 4705 | Erlösschmälerungen aus steuerfreien Umsätzen § 4 Nr. 1a UStG | 43 | E3103801 (Kz 752) | 45 |
| 4140 | Steuerfreie Umsätze Offshore etc. | 43 | E3104001 | 47 |
| 4139 | Umsatzerlöse aus Reiseleistungen § 25 Abs. 2 UStG, steuerfrei | 43 | E3104101 | 49 |
| 4105 | Steuerfreie Umsätze nach § 4 Nr. 12 UStG (Vermietung und Verpachtung) | 48 | E3104401 (Kz 286) | 51 |
| 4861 | Erlöse aus Vermietung und Verpachtung, umsatzsteuerfrei § 4 Nr. 12 UStG | 48 | E3104401 (Kz 286) | 51 |
| 4184 | Steuerfreie Erlöse Kleinunternehmer nach § 19 Abs. 1 UStG | 48 | E3104701 (Kz 236) | 53 |
| 4185 | Erlöse aus Kleinunternehmer i. S. d. § 19 Abs. 1 UStG (ERPNext) | 48 | E3104701 (Kz 236) | 53 |
| 4707 | Erlösschmälerungen für steuerfreie Umsätze nach § 19 Abs. 1 UStG | 48 | E3104701 (Kz 236) | 53 |
| 4160 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend, § 4 UStG | 48 | E3104902 (Kz 240) | 54 |
| 4165 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend | 48 | E3104902 (Kz 240) | 54 |
| 1431 | Abziehbare Vorsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager | 66 | E3006503 (Kz 466) | 88 |
| 1436 | Vorsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 66 | E3006801 (Kz 760) | 92 |
| 1398 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | E3008701 | 105 |
| 1399 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | E3008702 | 105 |
| 1396 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | E3008801 | 106 |
| 1397 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | E3008802 | 106 |
| 1376 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 2 UStG | 64 | E3008803 | 107 |
| 1377 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 2 UStG | 64 | E3008804 | 107 |
| 3819 | Umsatzsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 69 | E3101702 | 66 |
| 3839 | Umsatzsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager | beobachtet | E3102805 (Kz 853) | 63 |

### Konten nur für die Umsatzsteuererklärung

Diese Konten haben in der Voranmeldung keinen Platz oder werden dort beobachtet, siehe [Beobachtete Konten](#beobachtete-konten) und [Bewusst ohne Kennzahl](#bewusst-ohne-kennzahl). Die Erklärung liest ihren Saldo des Jahres auf der Seite der Tabelle:

- **Zeile 55 (Kz 789):** „Bitte füllen Sie die Zeile 55 bei innergemeinschaftlichen Dreiecksgeschäften aus, wenn Sie der erste Abnehmer sind und Ihr Erwerb als besteuert gilt (§ 25b Absatz 3 UStG)“ (USt 2 E, Zeile 55). ERiC nimmt Kz 789 nur zusammen mit Kz 742, den Lieferungen des ersten Abnehmers (Regel 30013), und Kz 742 darf nicht kleiner sein als Kz 789 (Regel 30014).
- **Zeile 66 (Kz 751):** „Die Bemessungsgrundlage und die Steuer, die der letzte Abnehmer nach § 25b Absatz 2 UStG für die Lieferung des ersten Abnehmers schuldet, tragen Sie bitte in den Zeilen 66, 67 und 69 ein“ (USt 2 E, Zeilen 65 bis 70): der Erwerb als letzter Abnehmer zu 19 % und seine Skonti, die die Bemessungsgrundlage mindern. DATEV führt SKR04 5792 ohne „U“, anders als SKR03 3792; beide gehen gleich ein.
- **Zeile 63 (Kz 852):** „Tragen Sie bitte in Zeile 63 die Lieferungen ein, die den Auslagerungen von Gegenständen aus einem Umsatzsteuerlager vorangegangen sind“ (USt 2 E, Zeile 63): die Einkäufe aus einem Umsatzsteuerlager zu 7 und 19 %.

Die Steuer zu den Zeilen 63 und 66 kommt über Kz 69 aus den Rollen ihrer Steuerkonten, siehe [Vorgabe der Zeilen](#vorgabe-der-zeilen).

| SKR03 | Bezeichnung laut Kontenrahmen 2026 | Feld | Zeile | Seite |
|---|---|---|---|---|
| 3552 | Erwerb 1. Abnehmer innerhalb eines Dreiecksgeschäftes | E3100801 (Kz 789) | 55 | Soll |
| 3089 | Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | E3101701 (Kz 751) | 66 | Soll |
| 3553 | Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | E3101701 (Kz 751) | 66 | Soll |
| 3792 | Erhaltene Skonti aus Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | E3101701 (Kz 751) | 66 | Soll |
| 3793 | Erhaltene Skonti aus Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | E3101701 (Kz 751) | 66 | Soll |
| 3075 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer | E3102804 (Kz 852) | 63 | Soll |
| 3076 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer | E3102804 (Kz 852) | 63 | Soll |
| 3560 | Waren aus einem Umsatzsteuerlager, § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer | E3102804 (Kz 852) | 63 | Soll |
| 3565 | Waren aus einem Umsatzsteuerlager, § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer | E3102804 (Kz 852) | 63 | Soll |

| SKR04 | Bezeichnung laut Kontenrahmen 2026 | Feld | Zeile | Seite |
|---|---|---|---|---|
| 5552 | Erwerb 1. Abnehmer innerhalb eines Dreiecksgeschäftes | E3100801 (Kz 789) | 55 | Soll |
| 5189 | Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | E3101701 (Kz 751) | 66 | Soll |
| 5553 | Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | E3101701 (Kz 751) | 66 | Soll |
| 5792 | Erhaltene Skonti aus Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | E3101701 (Kz 751) | 66 | Soll |
| 5793 | Erhaltene Skonti aus Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | E3101701 (Kz 751) | 66 | Soll |
| 5175 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer | E3102804 (Kz 852) | 63 | Soll |
| 5176 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer | E3102804 (Kz 852) | 63 | Soll |
| 5560 | Waren aus einem Umsatzsteuerlager, § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer | E3102804 (Kz 852) | 63 | Soll |
| 5565 | Waren aus einem Umsatzsteuerlager, § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer | E3102804 (Kz 852) | 63 | Soll |

## Steuer zu Umsätzen mit festem Steuersatz

Für die Umsätze und Erwerbe zu 19 % und 7 % (Kz 81, 86, 89 und 93) übermittelt die Voranmeldung nur die Bemessungsgrundlage, in vollen Euro (Schematyp ganze Zahl); eine Kennzahl für ihre Steuer gibt es nicht. Kz 83 wird mit Cent übermittelt, und die Jahresdokumentation UStVA 2026 der ERiC-Dokumentation enthält keine Regel, die Kz 83 aus den Bemessungsgrundlagen nachrechnet. Die Schnittstelle des Finanzamts nimmt deshalb beide Wege an, die Steuer dieser Zeilen zu bestimmen. Welchen Steuerbote geht, entscheidet je Unternehmen die Einstellung „Steuer zu Umsätzen mit festem Steuersatz“ (`statutory_tax`) in den Einstellungen Umsatzsteuer-Voranmeldung; die Regeln stehen im Kern unter `StatutoryTax` in [`calculation.py`](../steuerbote/ustva/calculation.py).

| Wert | Steuer der Kz 81, 86, 89 und 93 | Kz 83 |
|---|---|---|
| **aus der Bemessungsgrundlage in vollen Euro (wie im amtlichen Formular)**, Vorgabe | Steuersatz × gemeldete Bemessungsgrundlage, wie der Vordruck neben den Zeilen 13, 14, 25 und 26 rechnet | um die Steuer auf die weggelassenen Cent der Bemessungsgrundlagen niedriger als der Saldo der Steuerkonten |
| **wie gebucht (Summe der Steuer aus den Belegen)** | die Steuer, die die Belege der Verprobung der Bemessungsgrundlage auf deren Steuerkonten buchen, mit Cent | gleich dem Saldo der Steuerkonten; nach der Zahlung bleibt nichts auf ihnen stehen |

Andere Buchhaltungsprogramme gehen den zweiten Weg. Beispiel aus den Tests: drei Rechnungen über je 33,33 EUR mit je 6,33 EUR Umsatzsteuer. Kz 81 ist in beiden Fällen 99; aus der Bemessungsgrundlage ist die Steuer 18,81 EUR, wie gebucht 18,99 EUR, und Kz 83 entsprechend. Die Bemessungsgrundlagen bleiben in beiden Fällen dieselben, ebenso die Verprobung und jede Steuer mit eigener Kennzahl (Kz 36, 47, 74, 80, 85, 96, 98): Die Aufteilung zwischen Kz 46 und 84 ändert sich nicht.

**Wie gebucht, im Einzelnen** (`booked_taxes()`):

- Je Beleg und Verprobung zählt die Steuer auf ihren Steuerkonten. Zeigt ein Beleg Bemessungsgrundlagen zweier Kennzahlen mit festem Steuersatz, etwa die Erwerbe ohne Vorsteuerabzug zu 7 und 19 % auf einem Steuerkonto, teilt `apportion_cents` seine gebuchte Steuer nach der genauen Steuer jeder Bemessungsgrundlage.
- Zeigt ein Beleg in derselben Verprobung auch eine Bemessungsgrundlage mit eigener Steuer-Kennzahl (etwa Kz 35 mit Kz 36 in einer eigenen Zuordnung), behält diese ihre je Beleg abgeleitete Steuer; der Rest der gebuchten Steuer gehört den Kennzahlen mit festem Steuersatz.
- Eine Bemessungsgrundlage unter einem Euro meldet 0, ihre gebuchte Steuer zählt trotzdem: 0,80 EUR mit 0,15 EUR Steuer ergeben Kz 81 = 0 und Kz 83 = 0,15. Steuer, die ein Beleg ohne jede Bemessungsgrundlage bucht, geht an die erste Kennzahl mit festem Steuersatz ihrer Verprobung; die Verprobung zeigt den Beleg weiter als Abweichung.
- Eine [Bemessungsgrundlage ohne Grundlagenkonto](#bemessungsgrundlage-ohne-grundlagenkonto) eines Erwerbs nimmt die Steuer, aus der sie abgeleitet ist. Kz 89 und Kz 61 sind dann gleich, Kz 83 bleibt bei 0,00.
- Buchungszeilen ohne Beleg gelten wie bei der Verprobung als ein Beleg. Gutschriften und Stornos gehen mit ihrem Vorzeichen ein.
- Eine Bemessungsgrundlage mit festem Steuersatz ohne Verprobung, was nur eine eigene Zuordnung haben kann, nimmt die Steuer ihres Satzes je Beleg auf Cent.

**Wo es wirkt.** Die Steuer geht in Zeile 37 und Kz 83 der Meldung ein, in die Spalte „Steuer“ der Kennzahlen (`tax` der Tabelle), in den Ausdruck neben den Zeilen 13, 14, 25 und 26, in die Datei für Mein ELSTER und die Übermittlung (dort ändert sich nur Kz 83), in die Summenzeilen des Berichts „UStVA Kennzahlen“ und in den Vorperiodenvergleich. „Berechnen“ hält an der Meldung fest, mit welcher Einstellung gerechnet wurde; jedes weitere Speichern und die Übermittlung rechnen mit dieser, bis „Berechnen“ erneut läuft. Eine Korrektur einer Bemessungsgrundlage mit festem Steuersatz nimmt die Steuer aus der korrigierten Bemessungsgrundlage, denn hinter dem korrigierten Betrag steht keine Buchung. Meldungen, die vor dieser Einstellung berechnet wurden, rechnen weiter aus der Bemessungsgrundlage.

**Was gleich bleibt.** Die Zuordnung zum Voranmeldungszeitraum gilt für die Steuer wie für ihre Bemessungsgrundlage, denn beide sind Buchungen desselben Belegs, siehe [Zuordnung zum Voranmeldungszeitraum](#zuordnung-zum-voranmeldungszeitraum). Die Hinweise zu einzelnen Rechnungen (etwa `STEUER-ABWEICHUNG`) prüfen die Belege selbst und hängen nicht von der Einstellung ab. Der Vergleich „Seit der Abgabe geändert“ vergleicht die Beträge der Kennzahlen und lässt Kz 83 weiter aus; eine Buchung nur auf ein Steuerkonto nach der Abgabe nennt die Tabelle als nachträgliche Buchung. Die Sondervorauszahlung der [Dauerfristverlängerung](dauerfristverlaengerung.md) nimmt Kz 83 der abgegebenen Meldungen und folgt damit der Einstellung, mit der sie abgegeben wurden; die Voranmeldungen vor Steuerbote tragen ihr Kz 83, wie es eingegeben wurde. Die Steuer des Vorjahres, nach der die Einrichtung den Voranmeldungszeitraum vorschlägt, rechnet mit der Einstellung, wenn es schon Einstellungen gibt.

**Umsatzsteuererklärung.** Wie gebucht nimmt auch die [Umsatzsteuererklärung](umsatzsteuererklaerung.md) für die Zeilen der Kz 81, 86, 89 und 93 die gebuchte Steuer, so dass die Voranmeldungen eines Jahres und die Erklärung ohne Centdifferenz aufgehen, siehe dort.

## Zuordnung zum Voranmeldungszeitraum

Steuerbote rechnet die Voranmeldung aus dem Hauptbuch. Welcher Voranmeldungszeitraum eine Buchung meldet, entscheidet die Einstellung „Zuordnung zum Voranmeldungszeitraum“ (`period_basis`), was mit einer Buchung für einen schon abgegebenen Zeitraum geschieht, die Einstellung „Belege für abgegebene Zeiträume“ (`late_documents`), beide in den Einstellungen Umsatzsteuer-Voranmeldung. Die Regeln stehen im Kern unter [`assignment.py`](../steuerbote/ustva/assignment.py), gelesen wird über [`vat_periods.py`](../steuerbote/vat_periods.py), siehe [Architektur](architektur.md#zuordnung-zum-voranmeldungszeitraum). Die Quellen stehen am Ende des Abschnitts als [Z1] bis [Z9], alle am 25. November 2026 gelesen; was eine Steuerberatung bestätigen sollte, steht unter [Offen zur Zuordnung](#offen-zur-zuordnung) und in der [Prüfliste](pruefliste-steuerberatung.md#zuordnung-zum-voranmeldungszeitraum).

### Was das Gesetz sagt

Bei der Soll-Versteuerung entsteht die Steuer „mit Ablauf des Voranmeldungszeitraums, in dem die Leistungen ausgeführt worden sind“ (§ 13 Abs. 1 Nr. 1 Buchst. a Satz 1 UStG [Z1]), gleich, wann die Rechnung geschrieben wird: „Der Zeitpunkt der Leistung ist entscheidend, für welchen Voranmeldungszeitraum ein Umsatz zu berücksichtigen ist“ (UStAE 13.1 Abs. 1 Satz 6 [Z7]). Eine Leistung im Juli, die am 1. August oder am 20. September berechnet wird, gehört in den Juli.

| Vorgang | Zeitraum nach dem Gesetz | Quelle | Steuerbote nach Leistungsdatum |
|---|---|---|---|
| Eigene Lieferung oder sonstige Leistung | Ablauf des Zeitraums der Ausführung. Eine Lieferung ist ausgeführt, wenn der Kunde die Verfügungsmacht erlangt oder die Beförderung beginnt, eine sonstige Leistung mit ihrer Vollendung, eine Dauerleistung mit ihrem Ende, außer die Beteiligten haben Teilleistungen vereinbart | § 13 Abs. 1 Nr. 1 Buchst. a Sätze 1 bis 3 UStG [Z1]; UStAE 13.1 Abs. 2 und 3, 13.4 [Z7] | Ausgangsrechnung im Zeitraum ihres Leistungsdatums, siehe [Rangfolge](#rangfolge-der-daten) |
| Anzahlung vor der Leistung | Ablauf des Zeitraums, in dem sie vereinnahmt wird | § 13 Abs. 1 Nr. 1 Buchst. a Satz 4 UStG [Z1]; UStAE 13.5 [Z7] | Zahlung (Payment Entry) mit ihrer Steuer nach Buchungsdatum |
| Unentgeltliche Wertabgabe | Ablauf des Zeitraums der Ausführung | § 13 Abs. 1 Nr. 2 UStG [Z1] | Journalbuchung nach Buchungsdatum |
| Gutschrift, Preisnachlass, Rückgabe, Forderungsausfall | „Die Berichtigungen … sind für den Besteuerungszeitraum vorzunehmen, in dem die Änderung der Bemessungsgrundlage eingetreten ist“ | § 17 Abs. 1 Satz 8 und Abs. 2 UStG [Z3] | Gutschrift (`is_return`) und Belastungsanzeige (`is_debit_note`) nach Buchungsdatum, auch mit Leistungszeitraum |
| Ist-Versteuerung | Ablauf des Zeitraums der Vereinnahmung | § 13 Abs. 1 Nr. 1 Buchst. b, § 20 UStG [Z1] | nicht unterstützt, siehe [Ist-Versteuerung](#ist-versteuerung) |
| Vorsteuer | der Zeitraum, in dem Leistung und Rechnung erstmals beide vorliegen; bei einer Anzahlung Rechnung und Zahlung | § 15 Abs. 1 Satz 1 Nr. 1 UStG [Z4]; UStAE 15.2 Abs. 2 Sätze 5 und 6 [Z7] | Eingangsrechnung nach Buchungsdatum: Sie wird gebucht, wenn die Rechnung da ist, nie vor ihrem Datum |
| Steuer nach § 13b Abs. 1 UStG: sonstige Leistung eines im übrigen Gemeinschaftsgebiet ansässigen Unternehmers (Kz 46/47) | Ablauf des Zeitraums der Ausführung | § 13b Abs. 1 und 4 UStG [Z5]; UStAE 13b.12 Abs. 1 Nr. 1 [Z7] | Eingangsrechnung nach Buchungsdatum, siehe [Offen zur Zuordnung](#offen-zur-zuordnung) |
| Steuer nach § 13b Abs. 2 UStG, etwa Werklieferungen ausländischer Unternehmer oder Bauleistungen (Kz 84/85) | mit Ausstellung der Rechnung, spätestens mit Ablauf des Monats nach der Ausführung | § 13b Abs. 2 UStG [Z5]; UStAE 13b.12 Abs. 1 Nr. 2 [Z7] | Eingangsrechnung nach Buchungsdatum |
| Innergemeinschaftlicher Erwerb (Kz 89, 93) | mit Ausstellung der Rechnung, spätestens mit Ablauf des Monats nach dem Erwerb; die Vorsteuer daraus im selben Zeitraum | § 13 Abs. 1 Nr. 6, § 15 Abs. 1 Satz 1 Nr. 3 UStG [Z1] [Z4] | Eingangsrechnung nach Buchungsdatum |
| Innergemeinschaftliche Lieferung (Kz 41) | Zeitraum, „in dem die Rechnung für diesen Umsatz ausgestellt wird, spätestens jedoch“ der, in dem der Monat nach der Lieferung endet; die Rechnung ist bis zum 15. dieses Monats auszustellen | § 18b Satz 2, § 14a Abs. 3 Satz 1 UStG [Z2] [Z6] | Ausgangsrechnung nach Buchungsdatum, dem Tag der Rechnung |
| Sonstige Leistung nach § 3a Abs. 2 UStG im übrigen Gemeinschaftsgebiet (Kz 21), Lieferung des ersten Abnehmers im Dreiecksgeschäft (Kz 42) | Zeitraum der Ausführung | § 18b Satz 3 UStG [Z2] | Ausgangsrechnung nach Buchungsdatum, wie die Zusammenfassende Meldung, siehe unten |
| Zusammenfassende Meldung | Lieferungen (L): Meldezeitraum der Rechnung, spätestens der des Monats nach der Lieferung; sonstige Leistungen (S) und Dreiecksgeschäfte (D): Meldezeitraum der Ausführung | § 18a Abs. 8 UStG [Z2] | unverändert nach Buchungsdatum (Entscheidung des Maintainers), siehe [Zusammenfassende Meldung](zm.md#meldezeilen-aus-dem-hauptbuch) |

**Kz 41, 42 und 21 bleiben beim Buchungsdatum.** Für Kz 41 ist das der Tag der Rechnung und damit, was § 18b Satz 2 UStG verlangt, solange die Rechnung rechtzeitig ausgestellt wird. Kz 21 und 42 gehören nach § 18b Satz 3 UStG in den Zeitraum der Ausführung. Die Zusammenfassende Meldung wählt ihre Belege aber nach Buchungsdatum, und ihr [Abgleich](zm.md#abgleich-mit-der-voranmeldung) setzt sie gegen Kz 41, 42 und 21 der abgegebenen Voranmeldungen. Deshalb behalten die Konten dieser drei Kennzahlen in der Kontenzuordnung (`invoice_date_accounts`) unter beiden Einstellungen das Buchungsdatum: Voranmeldung und Zusammenfassende Meldung melden dieselben Belege in denselben Zeiträumen. Beide auf die Ausführung umzustellen ist ein eigener Schritt, der die Zusammenfassende Meldung mitnimmt.

**Eingangsseite.** Eingangsrechnungen tragen in ERPNext kein Leistungsdatum, das Steuerbote liest; sie zählen nach Buchungsdatum. Für die Vorsteuer ist das die gesetzliche Regel, solange die Rechnung gebucht wird, wenn sie vorliegt. Bei § 13b Abs. 1 UStG entsteht die Steuer dagegen schon im Zeitraum der Ausführung, bei § 13b Abs. 2 UStG und beim innergemeinschaftlichen Erwerb spätestens mit Ablauf des Folgemonats. Kommt die Rechnung später, gehört die Buchung in den früheren Zeitraum. Weil Steuer und Vorsteuer daraus im selben Zeitraum stehen (§ 15 Abs. 1 Satz 1 Nr. 3 und 4 UStG [Z4]), ändert das bei vollem Vorsteuerabzug die Zahllast nicht, wohl aber die Kennzahlen des Zeitraums.

### Die Einstellung „Zuordnung zum Voranmeldungszeitraum“

| Wert | Bedeutung |
|---|---|
| nach Leistungsdatum (gesetzlicher Regelfall), Vorgabe | Eine Ausgangsrechnung zählt im Zeitraum ihres Leistungsdatums, jede andere Buchung an ihrem Buchungsdatum |
| nach Buchungsdatum | Jede Buchung zählt an ihrem Buchungsdatum, wie Steuerbote bis Version 0.13 gerechnet hat. Das passt zu Büchern, deren Buchungsdatum schon den Zeitraum trägt, etwa übernommenen Journalbuchungen aus einer Buchhaltung, die nach Buchungsperioden bucht |

Mehr Werte gibt es nicht. Ein Wert „nach Rechnungsdatum“ fiele mit „nach Buchungsdatum“ zusammen, denn das Buchungsdatum einer Ausgangsrechnung ist ihr Datum. Die Ist-Versteuerung ist keine Frage der Zuordnung, sondern der Bemessungsgrundlage, und bleibt ein eigenes Paket.

#### Rangfolge der Daten

Das Leistungsdatum einer Ausgangsrechnung (`service_date` in `assignment.py`, gelesen von `steuerbote/ledger.py`) ist, in dieser Reihenfolge:

1. das Bis-Datum (`to_date`) des Leistungszeitraums der Rechnung. ERPNext füllt Von- und Bis-Datum bei Rechnungen aus einem Abonnement; die App für E-Rechnungen schreibt den Zeitraum in die E-Rechnung und nimmt das Bis-Datum als Lieferdatum. Eine Leistung über mehrere Monate ist mit ihrem Ende ausgeführt, sie zählt also im Zeitraum, in dem der Leistungszeitraum endet. Sind Teilleistungen vereinbart, etwa ein monatliches Entgelt, bekommt jede ihre eigene Rechnung mit ihrem eigenen Zeitraum; im Formular der Ausgangsrechnung stehen die beiden Felder als „Von-Datum“ und „Bis-Datum“ im Reiter „Weitere Informationen“ unter „Abonnement“, einem Abschnitt, den ERPNext eingeklappt zeigt;
2. ohne Bis-Datum das Von-Datum;
3. ohne beide das Buchungsdatum des letzten eingereichten Lieferscheins, den eine Position der Rechnung nennt, der Tag der Lieferung;
4. sonst das Buchungsdatum.

Kein Leistungsdatum haben Gutschriften und Belastungsanzeigen (§ 17 UStG), Zahlungen, Journalbuchungen, Lohnbuchungen und Eingangsrechnungen; Rechnungen der Kasse (POS) tragen keinen Leistungszeitraum und zählen am Tag ihrer Buchung. Das Leistungsdatum gilt für alle Buchungen der Rechnung, Erlös, Umsatzsteuer und Forderung, so dass die Verprobung je Beleg aufgeht; ausgenommen sind die Konten der Kz 41, 42 und 21. Die Termine der Rechnungsabgrenzung an den Positionen (`service_start_date`, `service_end_date`) liest Steuerbote nicht: Sie verteilen Erlöse über Monate, die Steuer der Rechnung bleibt an ihr.

Eine [Bemessungsgrundlage ohne Grundlagenkonto](#bemessungsgrundlage-ohne-grundlagenkonto) leitet der Kern je Beleg aus den Buchungszeilen ab, die der Zeitraum meldet. Alle Buchungen eines Belegs mit demselben Buchungsdatum bekommen denselben Zeitraum; die abgeleitete Grundlage folgt deshalb unter beiden Einstellungen und auch als nachträgliche Buchung dem Zeitraum ihrer Steuer, in Voranmeldung, Verprobung, Bericht „UStVA Kennzahlen“ und Umsatzsteuererklärung.

Liegt das Leistungsdatum nach der Rechnung, zählt sie im späteren Zeitraum der Leistung. Wird eine solche Rechnung vor der Leistung bezahlt, entsteht die Steuer nach § 13 Abs. 1 Nr. 1 Buchst. a Satz 4 UStG schon mit der Zahlung; das erkennt Steuerbote nicht, siehe [Offen zur Zuordnung](#offen-zur-zuordnung).

Eine stornierte Ausgangsrechnung zählt mit ihrer Gegenbuchung im Zeitraum ihres Leistungsdatums und gleicht sich dort aus, mit und ohne „Unveränderliches Hauptbuch aktivieren“, siehe [Stornierte Belege](#stornierte-belege).

### Belege für abgegebene Zeiträume

Ein Zeitraum gilt als abgegeben, sobald eine seiner Meldungen gesendet oder als abgegeben vermerkt ist, wie es [Übermittlung](uebermittlung.md) beschreibt. Als Zeitpunkt zählt, wann Steuerbote die Abgabe festgehalten hat (`finished_at` der ELSTER-Übermittlung); bei einem Vermerk ist das nie vor der Abgabe. Eine Buchung ist nachträglich, wenn ihr Eintrag im Hauptbuch (`creation` des GL Entry) später liegt als die Abgabe ihres Zeitraums. Das gilt für jede Buchung, auch eine rückdatierte Journalbuchung, und unter beiden Werten der Zuordnung.

Eine Buchung für einen abgegebenen Zeitraum macht dessen Anmeldung unvollständig. § 153 Abs. 1 Satz 1 Nr. 1 AO [Z8] verlangt dann, „dies unverzüglich anzuzeigen und die erforderliche Richtigstellung vorzunehmen“; bei der Voranmeldung geschieht das mit einer berichtigten Anmeldung (Kz 10). Viele Buchhaltungen melden einen solchen Beleg stattdessen im Zeitraum, den sie gerade bearbeiten. Die Einstellung „Belege für abgegebene Zeiträume“ bietet beides:

| Wert | Was mit der nachträglichen Buchung geschieht |
|---|---|
| Berichtigung des abgegebenen Zeitraums, Vorgabe | Sie bleibt in ihrem Zeitraum. Die Meldung, die gerade vorbereitet wird, nennt sie, und der abgegebene Zeitraum braucht eine berichtigte Anmeldung. Eine Berichtigung, die nach der Buchung abgegeben wird, enthält sie; danach gilt sie nicht mehr als nachträglich. |
| im laufenden Zeitraum melden | Sie geht in den ersten Zeitraum desselben Jahres nach ihrem, der bei ihrer Buchung noch nicht abgegeben war, also den, der gerade vorbereitet wurde, und zählt dort ab seinem ersten Tag. Es entscheidet die erste Abgabe des Zeitraums: Eine spätere Berichtigung holt die Buchung nicht zurück. Gibt es im Jahr keinen offenen Zeitraum mehr, bleibt sie in ihrem Zeitraum und braucht dessen Berichtigung, denn Besteuerungszeitraum ist das Kalenderjahr (§ 16 Abs. 1 Satz 2 UStG), und die Umsatzsteuererklärung des Jahres hält sie. |

**Zeiträume vor dem Start der Bücher.** Beginnen die Bücher eines Unternehmens in ERPNext erst im Lauf seines Lebens („Bücher in ERPNext ab“, siehe [Start mit Steuerbote im laufenden Betrieb](einrichtung.md#start-mit-steuerbote-im-laufenden-betrieb)), sind die Zeiträume davor außerhalb von Steuerbote aus anderen Büchern abgegeben und als „Voranmeldung vor Steuerbote“ erfasst. Keine Buchung in ERPNext steckt in diesen Meldungen. Jeder Zeitraum vor dem Start gilt deshalb als abgegeben, bevor irgendetwas in ERPNext gebucht wurde, gleich an welchem Tag er abgegeben ist; seine Einteilung nimmt Steuerbote aus den Voranmeldungen vor Steuerbote, sonst aus den Regeln der Einstellungen, sonst als Monat. Eine Buchung, die nach ihrem Leistungs- oder Buchungsdatum in einen solchen Zeitraum gehört, etwa eine Ausgangsrechnung im Juli für eine Leistung im Juni bei einem Start am 1. Juli, ist also immer nachträglich: Mit „Berichtigung des abgegebenen Zeitraums“ bleibt sie in ihrem Zeitraum, und die Meldung, die gerade vorbereitet wird, sagt, dass die Berichtigung abgibt, wer den Zeitraum abgegeben hat, denn für einen Zeitraum vor dem Start legt Steuerbote keine Meldung an; mit „im laufenden Zeitraum melden“ geht sie in den ersten Zeitraum, der bei ihrer Buchung offen war, frühestens den ersten Zeitraum der Bücher. In keinem Fall landet sie unbemerkt in einem Zeitraum vor dem Start oder fällt heraus.

**Kein Beleg doppelt, keiner verloren.** Wohin eine Buchung gehört, folgt allein aus ihr, den Zeiträumen und deren Abgaben; jede Buchung landet in genau einem Zeitraum. Die Tests prüfen das für jede Kombination der beiden Einstellungen an denselben Buchungen (`LinesTest` in `steuerbote/ustva/tests/test_assignment.py`). Mit „im laufenden Zeitraum melden“ rechnet eine Berichtigung des abgegebenen Zeitraums die verschobene Buchung nicht mit, und der Zeitraum, der sie meldet, zählt sie einmal. Wer eine der beiden Einstellungen ändert, ändert, wohin frühere Buchungen gehören: Die abgegebenen Zeiträume, deren Beträge sich dadurch ändern, zeigt Steuerbote an, wie im nächsten Absatz. Die Einstellungen sollten deshalb nur zum Jahreswechsel und mit der Steuerberatung geändert werden.

**Wo Steuerbote es zeigt.** „Berechnen“ füllt an der Meldung die Tabelle „Nach der Abgabe geändert“ und hält in „Zuordnung zum Voranmeldungszeitraum“ und „Belege für abgegebene Zeiträume“ fest, nach welchen Einstellungen gerechnet wurde. Die Tabelle nennt

- jede nachträgliche Buchung eines abgegebenen Zeitraums desselben Jahres oder des Vorjahres, die diese Meldung meldet („Gehört zu Juli 2026 und wurde nach der Abgabe von Juli 2026 gebucht: in diesem Zeitraum gemeldet.“) oder die eine Berichtigung ihres Zeitraums braucht,
- jede Stornierung nach der Abgabe des Zeitraums ihres Belegs, mit der Art „Nach der Abgabe storniert“, siehe [Stornierte Belege](#stornierte-belege), und
- jede Kennzahl eines abgegebenen Zeitraums vor dieser Meldung, deren Betrag laut Hauptbuch heute von dem abweicht, den die abgegebene Meldung genommen hat („Kz 81: abgegeben 1.000,00 €, jetzt 1.500,00 €.“). Kz 83 und Kz 39 folgen aus den anderen und aus den Einstellungen und werden nicht verglichen. Dieser Vergleich findet auch, was keine nachträgliche Buchung erklärt, etwa einen gelöschten Beleg oder eine geänderte Kontenzuordnung.

Die abgegebene Meldung selbst nennt beim Öffnen über dem Formular, was sich in ihrem Zeitraum seit der Abgabe geändert hat und wo eine nachträgliche Buchung gemeldet ist. „Berichtigung anlegen“ an ihr legt die berichtigte Anmeldung (Kz 10) des Zeitraums als Entwurf an oder öffnet den Entwurf, den es schon gibt.

### Stornierte Belege

Wer einen Beleg in ERPNext storniert, sagt: Diese Buchung war falsch. Die Lieferung, die Rechnung oder die Zahlung, die sie gebucht hat, gab es so nicht, und für die Umsatzsteuer hat es den Beleg in seinem Zeitraum nie gegeben. Die Steuer eines Zeitraums ist die Steuer seiner Umsätze (§ 13 Abs. 1 Nr. 1 Buchst. a, § 16 Abs. 1 und § 18 Abs. 1 UStG [Z1]), abziehbar ist nur die gesetzlich geschuldete Steuer für eine an das Unternehmen ausgeführte Leistung (§ 15 Abs. 1 Satz 1 Nr. 1 UStG [Z4]). Eine abgegebene Anmeldung, die den Beleg enthält, ist deshalb unrichtig und wird berichtigt (§ 153 Abs. 1 Satz 1 Nr. 1 AO [Z8]).

ERPNext bucht beim Stornieren zu jeder Buchung des Belegs eine Gegenbuchung mit der Bemerkung „On cancellation of“ und dem Beleg. Ohne „Unveränderliches Hauptbuch aktivieren“ in den Buchhaltungseinstellungen trägt sie das Datum des Belegs, und ERPNext kennzeichnet beide als storniert (`is_cancelled`); mit der Einstellung trägt die Gegenbuchung den Tag der Stornierung, und nichts ist gekennzeichnet. Steuerbote liest in beiden Fällen dasselbe (`load_bookings` in `steuerbote/ledger.py`): die Buchungen des Belegs, wie sie gebucht wurden, und jede Gegenbuchung als Stornierung am Buchungsdatum des Belegs, eingetragen zur Zeit der Stornierung (`Booking.cancellation` in [`assignment.py`](../steuerbote/ustva/assignment.py)). Eine Ausgangsrechnung mit Leistungsdatum storniert sich nach Leistungsdatum. Damit gilt die Regel für [Belege für abgegebene Zeiträume](#belege-für-abgegebene-zeiträume):

| Stornierung | Berichtigung des abgegebenen Zeitraums (Vorgabe) | im laufenden Zeitraum melden |
|---|---|---|
| bevor der Zeitraum des Belegs abgegeben ist, nach Leistungsdatum oder Buchungsdatum | Beleg und Stornierung heben sich in seinem Zeitraum auf, keine Meldung enthält ihn, auch nicht die des Tags der Stornierung (`settled` in `assignment.py`). | wie links |
| nachdem der Zeitraum des Belegs abgegeben ist, nach Leistungsdatum oder Buchungsdatum | Die Stornierung bleibt im Zeitraum des Belegs, der abgegebene Zeitraum braucht eine berichtigte Anmeldung (Kz 10); die Meldung, die gerade vorbereitet wird, und die abgegebene nennen den Beleg mit „Nach der Abgabe storniert“. | Die Stornierung geht mit umgekehrtem Vorzeichen in den Zeitraum, der bei der Stornierung offen war, und die Tabelle „Nach der Abgabe geändert“ dieser Meldung nennt sie. |

Die beiden Spalten unterscheiden sich nur nach der Abgabe, und die Einstellung „Zuordnung zum Voranmeldungszeitraum“ entscheidet nur, welcher Zeitraum der des Belegs ist. Eine Stornierung, die ERPNext vor das Datum des Belegs bucht, etwa eines vordatierten Belegs, ändert den Zeitraum ihres Tags nicht. Ein gelöschter Beleg, dessen Buchungen ERPNext nur ohne unveränderliches Hauptbuch und mit `delete_linked_ledger_entries` der Buchhaltungseinstellungen mitlöscht, fehlt im Hauptbuch; der Vergleich der Kennzahlen eines abgegebenen Zeitraums zeigt ihn.

**Keine Stornierung ist eine spätere Änderung.** Ändert sich die Bemessungsgrundlage eines Umsatzes, den es gab, etwa durch Rückgabe, Preisnachlass, Skonto oder Forderungsausfall, wird sie berichtigt „für den Besteuerungszeitraum …, in dem die Änderung der Bemessungsgrundlage eingetreten ist“ (§ 17 Abs. 1 Satz 8 und Abs. 2 UStG [Z3]); beim Empfänger ebenso die Vorsteuer (§ 17 Abs. 1 Satz 2 UStG). Dafür bucht man eine Gutschrift (Rechnungskorrektur) oder bei einer Eingangsrechnung eine Rücksendung mit eigenem Datum, nicht die Stornierung der ursprünglichen Rechnung; die Gutschrift zählt an ihrem Buchungsdatum, siehe [Was das Gesetz sagt](#was-das-gesetz-sagt). Eine Stornierung mit „Ändern“ legt einen neuen Beleg an, der an seinem eigenen Datum zählt.

### Was sich für ein Unternehmen ändert

Mit der Vorgabe „nach Leistungsdatum“ ändert sich nur etwas für Ausgangsrechnungen mit Leistungszeitraum oder Lieferschein in einem anderen Zeitraum als ihr Buchungsdatum: Sie zählen im Zeitraum der Leistung. Journalbuchungen, Zahlungen, Eingangsrechnungen und Rechnungen ohne diese Daten zählen wie bisher. Die [Umsatzsteuererklärung](umsatzsteuererklaerung.md#berechnen), der Bericht „UStVA Kennzahlen“, der Vorperiodenvergleich und der Vorschlag des Voranmeldungszeitraums in der [Einrichtung](einrichtung.md#voranmeldungszeitraum) rechnen nach derselben Zuordnung; ein Jahr ist die Summe seiner Zeiträume. Der [Abgleich mit den Registern](#abgleich-mit-den-registern) vergleicht weiter die Berichte Sales Register und Purchase Register mit dem Hauptbuch nach Buchungsdatum, denn auch die Berichte wählen ihre Rechnungen nach Buchungsdatum. Die Hinweise zu den Rechnungen lesen die Ausgangsrechnungen, deren Buchungen die Meldung meldet. Bestehende Einstellungen bekommen beim Update beide Vorgaben (`steuerbote/patches/set_the_assignment_to_the_voranmeldungszeitraum.py`); eine schon abgegebene Meldung, deren Zeitraum nach der neuen Zuordnung andere Beträge hat, nennt das wie oben.

### Offen zur Zuordnung

- **Tag der Ausführung.** Ob das Bis-Datum des Leistungszeitraums, ersatzweise Von-Datum oder Lieferschein, den Tag der Ausführung im Sinne von UStAE 13.1 Abs. 2 und 3 trifft, hängt vom Vertrag ab, etwa von vereinbarten Teilleistungen. Das bestätigt die Steuerberatung.
- **Nachträgliche Belege im laufenden Zeitraum.** Die Gesetze und Verwaltungsanweisungen, die Steuerbote liest, sehen dafür keine Erleichterung vor; § 153 AO verlangt die Berichtigung. Ob die Praxis, die die Einstellung „im laufenden Zeitraum melden“ abbildet, für das Unternehmen vertretbar ist, entscheidet die Steuerberatung.
- **Kz 21 und 42** zählen nach Buchungsdatum, wie die Zusammenfassende Meldung, obwohl § 18b Satz 3 UStG den Zeitraum der Ausführung nennt.
- **§ 13b und innergemeinschaftlicher Erwerb.** Steuerbote nimmt das Buchungsdatum der Eingangsrechnung, auch wo das Gesetz den Zeitraum der Ausführung (§ 13b Abs. 1 UStG) oder spätestens den Folgemonat verlangt.
- **Anzahlungen über eine Ausgangsrechnung.** Eine Rechnung mit Leistungszeitraum nach ihrem Datum, die vor der Leistung bezahlt wird, meldet Steuerbote im Zeitraum der Leistung statt der Zahlung.
- **Rechnungskorrektur.** Eine Gutschrift, die eine falsch ausgestellte Rechnung berichtigt, ohne dass sich das Entgelt ändert, zählt nach ihrem Buchungsdatum wie eine Änderung der Bemessungsgrundlage. Ob sie in den Zeitraum der ursprünglichen Leistung gehört, klärt die Steuerberatung.
- **Stornierung oder Änderung.** Ob eine Stornierung einen Fehler berichtigt (Zeitraum des Belegs) oder eine spätere Änderung der Bemessungsgrundlage ist (§ 17 UStG, Zeitraum der Änderung), sieht Steuerbote dem Beleg nicht an; es behandelt jede Stornierung als Berichtigung. Eine spätere Änderung bucht das Unternehmen als Gutschrift.
- **Zeitpunkt der Abgabe.** Bei einem Vermerk zählt der Zeitpunkt, zu dem er in Steuerbote erfasst wurde, nicht der Tag der Abgabe in Mein ELSTER; eine Buchung zwischen beiden zählt als nicht nachträglich und erscheint dann als Abweichung der Kennzahlen.

### Quellen zur Zuordnung

- **[Z1]** § 13 UStG „Entstehung der Steuer“: <https://www.gesetze-im-internet.de/ustg_1980/__13.html>
- **[Z2]** § 18a UStG „Zusammenfassende Meldung“ und § 18b UStG „Gesonderte Erklärung innergemeinschaftlicher Lieferungen und bestimmter sonstiger Leistungen im Besteuerungsverfahren“: <https://www.gesetze-im-internet.de/ustg_1980/__18a.html>, <https://www.gesetze-im-internet.de/ustg_1980/__18b.html>
- **[Z3]** § 17 UStG „Änderung der Bemessungsgrundlage“: <https://www.gesetze-im-internet.de/ustg_1980/__17.html>
- **[Z4]** § 15 UStG „Vorsteuerabzug“: <https://www.gesetze-im-internet.de/ustg_1980/__15.html>
- **[Z5]** § 13b UStG „Leistungsempfänger als Steuerschuldner“: <https://www.gesetze-im-internet.de/ustg_1980/__13b.html>
- **[Z6]** § 14a UStG „Zusätzliche Pflichten bei der Ausstellung von Rechnungen in besonderen Fällen“: <https://www.gesetze-im-internet.de/ustg_1980/__14a.html>
- **[Z7]** Umsatzsteuer-Anwendungserlass, Stand 13. November 2026, Abschnitte 13.1, 13.4, 13.5, 13b.12 und 15.2, wie unter [I5](#quellen-zur-ist-versteuerung)
- **[Z8]** § 153 AO „Berichtigung von Erklärungen“: <https://www.gesetze-im-internet.de/ao_1977/__153.html>
- **[Z9]** ERPNext 16.60.0, <https://github.com/frappe/erpnext/tree/v16.60.0>: `erpnext/accounts/doctype/sales_invoice/sales_invoice.json` (Felder `from_date`, `to_date`, `is_return`, `is_debit_note`, `is_pos`, `is_consolidated`) und `erpnext/accounts/doctype/sales_invoice_item/sales_invoice_item.json` (`delivery_note`, `service_start_date`, `service_end_date`)

## Ist-Versteuerung

Steuerbote rechnet die Voranmeldung nach vereinbarten Entgelten (§ 16 Abs. 1 Satz 1 UStG, Soll-Versteuerung); in den Einstellungen kennt „Besteuerung“ (`taxation_type`) nur „Soll“. Dieser Abschnitt schätzt ein, was die Berechnung nach vereinnahmten Entgelten (Ist-Versteuerung) ändert, wie eine Buchhaltung sie buchen müsste, was ERPNext 16 dafür mitbringt und was Steuerbote bräuchte. Umgesetzt ist davon nichts. Die Quellen stehen am Ende des Abschnitts als [I1] bis [I12], alle am 20. November 2026 gelesen; was sie nicht belegen, steht unter [Offen zur Ist-Versteuerung](#offen-zur-ist-versteuerung).

**Heute ist Steuerbote für Ist-Versteuerer nicht geeignet.** Bucht ein Unternehmen die Steuer seiner Rechnungen auf die nicht fälligen Konten, wie es die Ist-Versteuerung verlangt, hält die Meldung an, denn die Vorgaben beobachten diese Konten (siehe [Beobachtete Konten](#beobachtete-konten)). Bucht es sie gleich auf die fälligen Konten, meldet Steuerbote die Umsätze im Zeitraum der Rechnung statt der Zahlung, ohne es zu bemerken.

### Was § 20 UStG ändert

- **Wer.** Das Finanzamt kann auf Antrag gestatten, die Steuer „nicht nach den vereinbarten Entgelten (§ 16 Abs. 1 Satz 1), sondern nach den vereinnahmten Entgelten“ zu berechnen: wenn der Gesamtumsatz im vorangegangenen Kalenderjahr „nicht mehr als 800 000 Euro betragen hat“, wenn der Unternehmer nach § 148 AO von der Buchführungspflicht befreit ist, soweit er Umsätze aus einem freien Beruf im Sinne des § 18 Abs. 1 Nr. 1 EStG ausführt, oder wenn er eine juristische Person des öffentlichen Rechts ist, soweit sie weder freiwillig noch gesetzlich verpflichtet Bücher führt (§ 20 Satz 1 UStG [I1]). Die Gestattung „erstreckt sich wegen des Prinzips der Abschnittsbesteuerung stets auf das volle Kalenderjahr“; für freie Berufe wird sie nicht erteilt, „wenn der Unternehmer für die in der Vorschrift genannten Umsätze Bücher führt“ (UStAE 20.1 Abs. 1 Satz 4 und 7 [I5]).
- **Wann die Steuer entsteht.** Statt „mit Ablauf des Voranmeldungszeitraums, in dem die Leistungen ausgeführt worden sind“, entsteht sie „mit Ablauf des Voranmeldungszeitraums, in dem die Entgelte vereinnahmt worden sind“ (§ 13 Abs. 1 Nr. 1 Buchst. a und b UStG [I2]). „Als Zeitpunkt der Vereinnahmung gilt bei Überweisungen auf ein Bankkonto grundsätzlich der Zeitpunkt der Gutschrift.“ (UStAE 13.6 Abs. 1 Satz 3 [I5]) Eine Rechnung vom 20. November, deren Betrag am 8. Januar gutgeschrieben wird, gehört damit in die Voranmeldung für Januar, nicht für November. Bei einer Teilzahlung zählt der vereinnahmte Teil; DATEV rechnet die Steuer dafür aus dem Zahlbetrag [I9].
- **In der Voranmeldung.** Zu den Zeilen 13 bis 16 (Kz 81, 86, 87 und 35/36) sagt die Anleitung: „Bitte tragen Sie hier die Bemessungsgrundlagen Ihrer Umsätze und die erhaltenen Anzahlungen ein, für die die Umsatzsteuer entstanden ist.“ [I6] Bei Ist-Versteuerung sind das die Entgelte, die im Zeitraum vereinnahmt wurden; eine eigene Regel dafür hat die Anleitung nicht. Ihr einziger Satz zur Ist-Versteuerung betrifft die Steuersätze von 2020: Bei Ist-Versteuerung gehören „im aktuellen Voranmeldungszeitraum vereinnahmte Beträge für nach dem 30. Juni 2020 und vor dem 1. Januar 2021 ausgeführte Umsätze“ in Zeile 16 [I6], also in Kz 35/36, der die Vorgaben kein Konto zuordnen. DATEV schreibt: „Bei der Ist-Versteuerung erfolgt der Ausweis von steuerpflichtigen und steuerfreien inländischen Umsätzen in der Umsatzsteuer-Voranmeldung (UStVA) erst bei der Zahlungseingangsbuchung (Geldfluss).“ [I9]
- **Was nicht von der Zahlung abhängt.** Eigene Zeitpunkte behalten:
  - unentgeltliche Wertabgaben nach § 3 Abs. 1b und 9a UStG: „mit Ablauf des Voranmeldungszeitraums, in dem diese Leistungen ausgeführt worden sind“ (§ 13 Abs. 1 Nr. 2 UStG [I2]), ebenso Leistungen an das Personal ohne besonderes Entgelt (UStAE 13.6 Abs. 2 [I5]);
  - der innergemeinschaftliche Erwerb (Kz 89 und 93): „mit Ausstellung der Rechnung, spätestens jedoch mit Ablauf des dem Erwerb folgenden Kalendermonats“ (§ 13 Abs. 1 Nr. 6 UStG [I2]);
  - die Steuer des Leistungsempfängers (Kz 46/47 und 84/85): nach § 13b Abs. 1 und 2 UStG [I3];
  - innergemeinschaftliche Lieferungen (Kz 41), sonstige Leistungen nach § 3a Abs. 2 UStG (Kz 21) und Lieferungen im Dreiecksgeschäft (Kz 42): Die Angaben zu innergemeinschaftlichen Lieferungen sind „in dem Voranmeldungszeitraum zu machen, in dem die Rechnung für diesen Umsatz ausgestellt wird“, spätestens in dem, in dem der Monat nach der Ausführung endet, die zu sonstigen Leistungen und Dreiecksgeschäften in dem, „in dem diese Umsätze ausgeführt worden sind“ (§ 18b Satz 2 und 3 UStG [I3]); die Zusammenfassende Meldung folgt ohnehin § 18a Abs. 8 UStG;
  - der eigene Vorsteuerabzug: Seine Voraussetzungen „müssen insgesamt erfüllt werden. Das gilt auch für Leistungsempfänger, die die Steuer für ihre Umsätze nach vereinnahmten Entgelten berechnen (§ 20 UStG).“ (UStAE 15.2 Abs. 2 Satz 2 und 3 [I5])

  DATEV fasst es so: „Alle anderen Steuersachverhalte werden unabhängig vom Zuflussprinzip (Ist-Versteuerung) gebucht.“ [I9]
- **Wechsel.** „Wechselt der Unternehmer die Art der Steuerberechnung, so dürfen Umsätze nicht doppelt erfasst werden oder unversteuert bleiben.“ (§ 20 Satz 3 UStG [I1]) „Im Falle eines bereits sollversteuerten Umsatzes bleibt der Zeitpunkt des Entstehens der Steuer auch dann unverändert, wenn der Unternehmer zur Istversteuerung wechselt und das Entgelt noch nicht vereinnahmt hat.“ Umgekehrt gilt die Ist-Versteuerung für Umsätze aus Jahren mit Gestattung weiter, auch nach einem Wechsel zur Soll-Versteuerung (UStAE 13.6 Abs. 3 [I5]).
- **Ab 2028 auch beim Leistungsempfänger.** Das Jahressteuergesetz 2024 ändert zum 1. Januar 2028 zwei Vorschriften [I7]: Die Rechnung eines Ist-Versteuerers trägt die Angabe „Versteuerung nach vereinnahmten Entgelten“ (§ 14 Abs. 4 Satz 1 Nr. 6a UStG neu), und ihr Empfänger zieht die Vorsteuer daraus nur ab, „soweit eine Zahlung auf eine ausgeführte Leistung geleistet worden ist“ (§ 15 Abs. 1 Satz 1 Nr. 1 Satz 2 Buchst. b UStG neu), erstmals für Rechnungen, „die nach dem 31. Dezember 2027 ausgestellt werden“ (§ 27 Abs. 41 UStG neu). Das trifft jedes Unternehmen, das Steuerbote nutzt, auch bei Soll-Versteuerung: Kz 66 hängt für solche Rechnungen dann an der Zahlung. Am 20. November 2026 enthält § 15 UStG diese Bedingung noch nicht [I4].

### Buchung der Ist-Versteuerung

DATEV bucht die Ist-Versteuerung über eigene Konten [I9, I10]: „Bei der Rechnungsausgangsbuchung (Umsatzerlös) wird die Umsatzsteuer von steuerpflichtigen inländischen Umsätzen errechnet und automatisch auf Umsatzsteuer nicht fällig gebucht.“ „Bei der Zahlungseingangsbuchung (Geldfluss) erfolgt automatisch eine abgeleitete Umbuchung von „Umsatzsteuer nicht fällig“ auf „Umsatzsteuer fällig“. Bemessungsgrundlage und Umsatzsteuer (bei steuerfreien Umsätzen nur die Bemessungsgrundlage) werden in der UStVA ausgewiesen.“ [I9] Die Konten dafür, geprüft an den Kontenrahmen 2026 [I8]:

| Zweck | SKR03 | SKR04 | Bezeichnung laut Kontenrahmen 2026 |
|---|---|---|---|
| Steuer der Rechnung, 19 % | 1766 | 3816 | Umsatzsteuer nicht fällig 19 % |
| Steuer der Rechnung, 7 % | 1761 | 3811 | Umsatzsteuer nicht fällig 7 % |
| Steuer bei Zahlung, 19 % | 1776 | 3806 | Umsatzsteuer 19 % |
| Steuer bei Zahlung, 7 % | 1771 | 3801 | Umsatzsteuer 7 % |
| Umstellung von Soll auf Ist | 1390 | 1490 | Verrechnungskonto Ist-Versteuerung |

Umgebucht wird von 1766 und 1761 auf 1776 und 1771, in SKR04 von 3816 und 3811 auf 3806 und 3801 [I10]. Dazu führen die Kontenrahmen 1760 „Umsatzsteuer nicht fällig“ und für im Inland steuerpflichtige EU-Lieferungen 1762 und 1764 (SKR04 3810, 3812 und 3814); für 1762 und 1764 nennen die gelesenen DATEV-Dokumente kein Gegenkonto. Das Verrechnungskonto dient „zur Erfassung von Vorgängen im Zusammenhang mit der Umstellung von der Soll- auf die Ist-Versteuerung“ und wird „insbesondere genutzt, um Forderungsausfälle abzubilden, bei denen die Umsatzsteuer bereits im Rahmen der Soll-Versteuerung berücksichtigt wurde“ [I10].

Ein Beispiel in SKR03: eine Rechnung über 1.000 € zuzüglich 19 % vom 20. November, bezahlt am 8. Januar.

| Tag | Soll | Haben | Betrag | Voranmeldung |
|---|---|---|---|---|
| 20. November | Forderung | 8400 | 1.000,00 | noch nicht |
| 20. November | Forderung | 1766 | 190,00 | noch nicht |
| 8. Januar | Bank | Forderung | 1.190,00 | |
| 8. Januar | 1766 | 1776 | 190,00 | Januar: Kz 81 mit 1.000 |

Zahlt der Kunde am 8. Januar nur 595 €, werden 95 € umgebucht (595 × 19/119), und Kz 81 erhält 500 €.

**In ERPNext** bucht eine Vorlage für Verkaufssteuern und -abgaben (Sales Taxes and Charges Template) mit dem nicht fälligen Konto statt 1776 die Steuer jeder Ausgangsrechnung so, wie DATEV es tut, denn ERPNext bucht die Steuer einer Rechnung auf das Konto ihrer Steuerzeile [I11]. Dabei ist zu beachten: Die Vorlage SKR03 von ERPNext enthält keine nicht fälligen Konten, die Vorlage SKR04 enthält 3810, 3811, 3812, 3814 und 3816 ohne Kontoart, und als Konto einer Steuerzeile bietet ERPNext nur Konten der Arten Tax, Chargeable und Expense Account an [I11]; die Konten sind also anzulegen oder als Tax zu kennzeichnen. Die Umbuchung bei Zahlung macht ERPNext nicht, siehe unten; ohne sie bleibt eine Journalbuchung je Zahlung von Hand. Für ein Skonto bucht ERPNext mit der Einstellung „Book tax loss on early payment discount“ (`book_tax_discount_loss`) den Steueranteil auf das Steuerkonto der Rechnung [I11], bei Ist-Versteuerung also auf das nicht fällige Konto.

### Was ERPNext 16 mitbringt

Keine Ist-Versteuerung. Geprüft im Quelltext von ERPNext 16.60.0 und des Frappe Framework 16.60.0 und in der App erpnext_germany (Zweig version-16) [I11]:

- Eine Ausgangsrechnung bucht ihre Steuer beim Buchen auf das Konto ihrer Steuerzeile (`sales_invoice.py`, Zeile 2009). Der Abgleich von Zahlungen mit Rechnungen (`reconcile_against_document` in `erpnext/accounts/utils.py`) bucht keine Steuer um. Die Buchhaltungseinstellungen haben kein Feld, das die Steuer an die Zahlung bindet; ihre Steuerfelder betreffen Steuerkategorie und Steuervorlagen, Rundung, Druck und den Steueranteil am Skonto.
- Die Zahlung (Payment Entry) hat eine Tabelle „Advance Taxes and Charges“. Ihre Beträge rechnet ERPNext aus dem Zahlbetrag (`current_tax_amount = (tax_rate / 100.0) * self.paid_amount_after_tax`, Zeile 2056), nicht aus den bezahlten Rechnungen; keine Zeile verweist auf eine Rechnung, und nichts bucht sie später zurück. Zwei Zeilen mit festem Betrag, „Deduct“ auf dem nicht fälligen und „Add“ auf dem fälligen Konto, ergäben nach dem Code (`add_tax_gl_entries`, ab Zeile 1818) die Umbuchung, wenn jemand den Betrag je Zahlung von Hand einträgt.
- Über den Hook `regional_overrides` lässt sich ERPNext je Land erweitern, etwa um `add_regional_gl_entries` der Zahlung (Zeile 3855, aufgerufen in Zeile 1504). Für Deutschland trägt ERPNext keinen ein, erpnext_germany auch nicht. Über diesen Hook könnte eine App die Umbuchung in die Buchungen der Zahlung selbst schreiben.
- Bei ERPNext sind die Issues #42843 „Incorrect Taxes on Advance Payment“ und #34467 „Invoice on Account/Advance Invoice“ offen; der Pull Request #54921 „feat(PE): carry advance tax through invoice consumption“ wurde am 31. Oktober 2026 ohne Merge geschlossen, und #56063 bringt Berichte zur Gewinnermittlung nach Zahlungen, keine Umsatzsteuer [I12].

### Was Steuerbote bräuchte

1. **Besteuerung je Jahr.** „Ist“ als zweite Möglichkeit in den Einstellungen, je Unternehmen und Kalenderjahr, weil die Gestattung immer für ein ganzes Jahr gilt [I5].
2. **Vorgaben je Besteuerungsart.** Die nicht fälligen Konten 1760, 1761, 1762, 1764 und 1766 (SKR04 3810, 3811, 3812, 3814 und 3816) bleiben bei Soll beobachtet. Bei Ist tragen sie planmäßig die Steuer der offenen Rechnungen: Sie gehen in keine Kennzahl ein und halten die Meldung nicht an.
3. **Kz 81 und 86 aus den fälligen Konten.** Bei Ist buchen die Erlöskonten (8400 und die übrigen Grundlagen von Kz 81 und 86) mit der Rechnung und dürfen deshalb nicht mehr in Kz 81 und 86 eingehen. An ihre Stelle tritt die Steuer, die im Zeitraum fällig wird: Kz 81 ist der Saldo im Haben von 1776 (SKR04 3806) im Zeitraum geteilt durch 19 %, Kz 86 der von 1771 (3801) geteilt durch 7 %. Das erfasst die Umbuchungen bei Zahlung ebenso wie Umsätze, deren Steuer gleich auf das fällige Konto gebucht wird, etwa unentgeltliche Wertabgaben. Der Kern bräuchte dafür eine Regel, die die Grundlage aus einem Steuerkonto ableitet, das Gegenstück zum Steuersatz einer Regel heute (`AccountRule.tax_rate`). Weil die Steuer jeder Zahlung auf Cent gerundet ist, weicht die abgeleitete Grundlage je Zahlung um wenige Cent von der vereinnahmten ab. Genau wäre die Grundlage aus den Zahlungen selbst, Zahlbetrag abzüglich Steueranteil je bezahlter Rechnung; die bezahlten Rechnungen einer Zahlung liest die Frappe-Schicht schon heute für die Zusammenfassende Meldung (`zm_sources.py`). Steuerfreie inländische Umsätze haben kein fälliges Konto; sind sie bei Ist erst mit der Zahlung zu melden, wie DATEV es tut [I9], geht es für sie nur über die Zahlungen.
4. **Verprobung bei Ist.** Heute vergleicht sie je Beleg die gebuchte Steuer mit der Steuer auf die Grundlagen. Bei Ist wäre je Zahlung zu prüfen, ob die Umbuchung dem Steueranteil des Zahlbetrags entspricht, und am Ende des Zeitraums, ob der Saldo der nicht fälligen Konten zum Steueranteil der offenen Posten passt.
5. **Die Umbuchung.** Entweder bucht sie die Buchhaltung von Hand und Steuerbote prüft sie, oder Steuerbote bucht sie selbst, etwa über `add_regional_gl_entries` in der Zahlung. Steuerbote würde damit zum ersten Mal selbst buchen, und Zahlungen, die erst später über den Zahlungsabgleich oder als Journalbuchung einer Rechnung zugeordnet werden, bräuchten einen eigenen Weg.
6. **Wechsel.** Rechnungen, die vor dem Wechsel zu Ist schon nach Soll gemeldet sind, dürfen bei Zahlung nicht noch einmal in Kz 81 eingehen, und umgekehrt [I5]; DATEV unterbindet dafür die erneute Umbuchung und bucht Forderungsausfälle solcher Rechnungen über das Verrechnungskonto [I10]. In den Vorgaben stehen 1390 (SKR03) und 1490 (SKR04) heute als bewusst ohne Kennzahl.
7. **Tests.** Wie bei der Soll-Versteuerung ein an echten Buchungen geprüfter Monat (siehe [Beispiel](#beispiel)) und Frappe-Tests für Teilzahlung, Skonto, Gutschrift, Erstattung und Stornierung mit unveränderlichem Hauptbuch.

### Empfehlung für die Roadmap

1. **Nicht in Stufe 2.** „Besteuerung“ bleibt bei „Soll“, bis die Ist-Versteuerung vollständig ist; Ist-Versteuerer können Steuerbote bis dahin nicht einsetzen.
2. **Ein eigenes Paket „Ist-Versteuerung“ nach der echten Übermittlung**, sobald ein Unternehmen mit Ist-Versteuerung Steuerbote einsetzen will, in dieser Reihenfolge: die Buchungsweise wie bei DATEV mit einer Steuerberatung festlegen; im Kern die Besteuerung je Jahr, Vorgaben je Besteuerungsart und die Grundlage aus den fälligen Konten oder aus den Zahlungen; der Abgleich der nicht fälligen Konten mit den offenen Posten; die Umbuchung zuerst von Hand mit Prüfung durch Steuerbote, eine automatische Umbuchung erst nach Erprobung des Hooks; zuletzt der Wechsel zwischen Soll und Ist.
3. **Unabhängig davon bis Ende 2027** die Vorsteuer aus Rechnungen Ist-versteuernder Lieferanten: Für ihre Rechnungen ab 2028 hängt Kz 66 an der Zahlung [I7]. Das betrifft jedes Unternehmen und gehört in die Vorbereitung des Jahreswechsels 2028.

### Offen zur Ist-Versteuerung

- Ob das Finanzamt Kz 81 und 86 aus der gerundeten Steuer der Zahlungen gelten lässt oder die vereinnahmten Entgelte auf den Cent verlangt, sagt keine der Quellen; das klärt die Steuerberatung.
- Steuerfreie inländische Umsätze (etwa Kz 43 und 48) meldet DATEV bei Ist-Versteuerung erst mit der Zahlung [I9]; eine Vorschrift oder Verwaltungsanweisung dazu steht in den gelesenen Quellen nicht.
- Für 1762 und 1764 (SKR04 3812 und 3814) nennen die gelesenen DATEV-Dokumente kein Gegenkonto der Umbuchung.
- Die Umbuchung über zwei Zeilen „Advance Taxes and Charges“ und über `add_regional_gl_entries` ist nur aus dem Quelltext gelesen, nicht an einer Site erprobt.
- Gesetze, die nach Mitte Oktober 2026 verkündet wurden, sind nicht darauf geprüft, ob sie die Änderungen des Jahressteuergesetzes 2024 zum 1. Januar 2028 verschieben oder ändern.

### Quellen zur Ist-Versteuerung

- **[I1]** § 20 UStG „Berechnung der Steuer nach vereinnahmten Entgelten“: <https://www.gesetze-im-internet.de/ustg_1980/__20.html>
- **[I2]** § 13 UStG „Entstehung der Steuer“: <https://www.gesetze-im-internet.de/ustg_1980/__13.html>
- **[I3]** § 13b UStG „Leistungsempfänger als Steuerschuldner“: <https://www.gesetze-im-internet.de/ustg_1980/__13b.html>; § 18b UStG: <https://www.gesetze-im-internet.de/ustg_1980/__18b.html>
- **[I4]** § 15 UStG „Vorsteuerabzug“: <https://www.gesetze-im-internet.de/ustg_1980/__15.html>
- **[I5]** Umsatzsteuer-Anwendungserlass, Stand 13. November 2026, Abschnitte 13.6, 15.2 Abs. 2 und 20.1: <https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/Umsatzsteuer-Anwendungserlass/Umsatzsteuer-Anwendungserlass-aktuell.pdf?__blob=publicationFile&v=61> (SHA-256 `406cda32cf956d29f2ffde5079c8a7f963a763aa47615c6652148856a23e4c2e`)
- **[I6]** Anleitung zur Umsatzsteuer-Voranmeldung 2026 (USt 1 E), Zeilen 13 bis 16, im BMF-Schreiben vom 29. Dezember 2025, siehe [Quelle](#quelle) (SHA-256 `82e7d63a0faec542bb184acb438eaf4ce90a2d7db067bb47f92ae13b4b17613d`)
- **[I7]** Jahressteuergesetz 2024 vom 2. Dezember 2024, BGBl. 2024 I Nr. 387, Artikel 27 und Artikel 56 Absatz 12 („Die Artikel 27 und 30 treten am 1. Januar 2028 in Kraft.“): <https://www.recht.bund.de/bgbl/1/2024/387/regelungstext.pdf?__blob=publicationFile&v=1> (SHA-256 `5ed5fd277dac16360d53acc403d3a2cb0b2bf798b2e511c5c2917a8a869c8f4c`)
- **[I8]** DATEV-Kontenrahmen SKR 03 (Art.-Nr. 11174) und SKR 04 (Art.-Nr. 11175), „Gültig für 2026“, siehe [Quelle](#quelle): SKR03 1390 (Funktion F), 1760, 1761, 1762, 1764, 1766, 1771 und 1776 (Funktion S); SKR04 1490 (F), 3801, 3806, 3810, 3811, 3812, 3814 und 3816 (S)
- **[I9]** DATEV Dok.-Nr. 1080673 „Besondere Regeln und Vereinfachungen für die Buchung der Ist-Versteuerung“, zuletzt aktualisiert am 26. September 2026: <https://wissensplattform.apps.datev.de/help/document/1080673>
- **[I10]** DATEV Dok.-Nr. 1034841 „Umstellung von Soll-Versteuerung auf Ist-Versteuerung in den DATEV-Rechnungswesen-Programmen“, Stand 4. Juni 2026: <https://apps.datev.de/help-center/documents/1034841>; DATEV Dok.-Nr. 5360294 „Verrechnungskonto Ist-Versteuerung - Kontenerläuterung“ vom 1. Juni 2026: <https://apps.datev.de/knowledge/professional/documents/5360294>
- **[I11]** ERPNext 16.60.0, <https://github.com/frappe/erpnext/tree/v16.60.0>: `erpnext/accounts/doctype/sales_invoice/sales_invoice.py` (Zeile 2009), `erpnext/accounts/doctype/accounts_settings/accounts_settings.json`, `erpnext/accounts/doctype/payment_entry/payment_entry.json` (Tabelle `taxes`, Zeilen 607 bis 610), `erpnext/accounts/doctype/payment_entry/payment_entry.py` (`add_tax_gl_entries` ab Zeile 1818, Zeile 2056, `split_early_payment_discount_loss` ab Zeile 3659, `add_regional_gl_entries` in den Zeilen 1504 und 3855), `erpnext/accounts/utils.py` (`reconcile_against_document` ab Zeile 510), `erpnext/__init__.py` und `erpnext/hooks.py` (`regional_overrides`, Zeilen 684 bis 697), `erpnext/public/js/controllers/accounts.js` (Zeilen 25 bis 37) und die Vorlagen `de_kontenplan_SKR03.json` und `de_kontenplan_SKR04.json` (dort Zeilen 766 und 1456 bis 1472) unter `erpnext/accounts/doctype/account/chart_of_accounts/verified/`; Frappe Framework 16.60.0; erpnext_germany, Zweig version-16: <https://github.com/alyf-de/erpnext_germany/tree/version-16>
- **[I12]** frappe/erpnext, Issues <https://github.com/frappe/erpnext/issues/42843> und <https://github.com/frappe/erpnext/issues/34467>, Pull Requests <https://github.com/frappe/erpnext/pull/54921> und <https://github.com/frappe/erpnext/pull/56063>

## Zeiträume und Fristen

[`period.py`](../steuerbote/ustva/period.py) beschreibt Voranmeldungszeiträume und ihre Fristen:

- **Zeitraum:** Eine Firma gibt monatlich oder vierteljährlich ab (§ 18 Absatz 2 UStG). Der Vordruck bietet die zwölf Monate und die vier Kalendervierteljahre, und so heißen die Zeiträume auch in Steuerbote, etwa „März 2026“ oder „III. Kalendervierteljahr 2026“.
- **Frist:** Die Anleitung sagt zu den Zeilen 53 und 54: „Die Vorauszahlung ist am 10. Tag nach Ablauf des Voranmeldungszeitraums fällig“. Mit Dauerfristverlängerung (§§ 46 bis 48 UStDV) verschiebt sich die Frist um einen Monat.
- **Wochenende und Feiertage:** Fällt die Frist auf einen Samstag, Sonntag oder Feiertag, gilt der nächste Werktag (§ 108 Absatz 3 AO). Feiertage unterscheiden sich je Bundesland, deshalb übergibt sie der Aufrufer.
- **Zeitraumcode:** `Period.code` liefert den zweistelligen Code der ELSTER-Schnittstelle für die Umsatzsteuer-Voranmeldung: 01 bis 12 für die Monate, 41 bis 44 für die Quartale. Die Tests des XML prüfen jeden Code gegen das Schema des Jahres aus der ERiC-Dokumentation, siehe [Abgabe über Mein ELSTER](abgabe-mein-elster.md).

Beispiele aus den Tests: Januar 2026 ist am 10. Februar 2026 fällig, mit Dauerfristverlängerung am 10. März 2026. Das I. Kalendervierteljahr 2026 ist am 10. April 2026 fällig. Für September 2026 gilt der 12. Oktober 2026, weil der 10. Oktober ein Samstag ist. Dezember 2026 ist am 11. Januar 2027 fällig, weil der 10. Januar ein Sonntag ist.

**Ein Zeitraum, der noch läuft.** Die Steuer entsteht mit Ablauf des Voranmeldungszeitraums (§ 13 Abs. 1 Nr. 1 Buchst. a Satz 1 UStG), und die Voranmeldung wird bis zum 10. Tag nach seinem Ablauf übermittelt (§ 18 Abs. 1 Satz 1 UStG). Eine Meldung lässt sich vorher anlegen und berechnen, damit die Buchhaltung den Monat prüfen kann; solange der letzte Tag ihres Zeitraums nicht vorbei ist, gibt „Berechnen“ die Warnung `ZEITRAUM-NICHT-ABGELAUFEN`, und die Meldung wird nicht bereit ([`obligations.py`](../steuerbote/ustva/obligations.py)). Nach dem Ende des Zeitraums rechnet man sie erneut; abgegeben wird sie vorher nur mit Anmerkungen, die sagen, warum. Auch ERiC weist auf einen Zeitraum hin, der noch nicht beendet ist oder in der Zukunft liegt.

**Zusammenfassende Meldung.** Meldet die Voranmeldung Umsätze in Kz 41, 42 oder 21, ist für sie eine Zusammenfassende Meldung abzugeben (§ 18a Abs. 1 und 2 UStG). Nennen die Einstellungen für einen Monat des Zeitraums keinen Rhythmus der Zusammenfassenden Meldung, gibt „Berechnen“ die Warnung `ZM-OHNE-RHYTHMUS`; ohne Rhythmus kennt Steuerbote weder die Meldung noch ihre Frist, siehe [Einrichtung](einrichtung.md).

**Vor dem Start der Bücher.** Nennen die Einstellungen in „Bücher in ERPNext ab“ den ersten Tag der Bücher in ERPNext, lehnt das Speichern eine Voranmeldung für einen Zeitraum ab, der davor beginnt: Sie wurde außerhalb von Steuerbote abgegeben und wird als Voranmeldung vor Steuerbote eingetragen. Der Vorperiodenvergleich mit einem solchen Zeitraum bleibt leer, mit dem Hinweis `VOR-START`; der Bericht „UStVA Kennzahlen“ sagt dasselbe in seiner Notiz. Siehe [Start mit Steuerbote im laufenden Betrieb](einrichtung.md#start-mit-steuerbote-im-laufenden-betrieb).

Für 2027 gilt dasselbe: Januar 2027 ist am Mittwoch, 10. Februar 2027 fällig, mit Dauerfristverlängerung am 10. März 2027. Das I. Kalendervierteljahr 2027 ist am Montag, 12. April 2027 fällig, Juni am Montag, 12. Juli 2027, September am Montag, 11. Oktober 2027, weil der 10. ein Samstag oder Sonntag ist; ein Feiertag am 11. Oktober schöbe die Frist auf den 12. Oktober. Dezember 2027 und das IV. Kalendervierteljahr 2027 sind am Montag, 10. Januar 2028 fällig, Dezember mit Dauerfristverlängerung am Donnerstag, 10. Februar 2028.

## Jahreswechsel

Den ganzen Ablauf mit Jahrestabelle, Schema, Vordruck USt 1 H, Plugin und Release beschreibt [Entwicklung, Jahreswechsel](entwicklung.md#jahreswechsel). Hier stehen die Prüfungen am Vordruck USt 1 A und an den Vorgaben. Zu jedem neuen Jahr:

1. Das BMF-Schreiben „Muster der Vordrucke im Umsatzsteuer-Voranmeldungs- und -Vorauszahlungsverfahren“ für das neue Kalenderjahr lesen. Es nennt die Änderungen in einem eigenen Abschnitt, und die Anleitung markiert wesentliche Änderungen mit „Neu!“. Datum, Geschäftszeichen und Adresse kommen in `YEARS` von [`years.py`](../steuerbote/ustva/years.py).
2. Den neuen Vordruck USt 1 A Zeile für Zeile mit dem Katalog des Vorjahres vergleichen: Zeile, Kennzahl, Bezeichnung, Art, Wirkung, Steuersatz und Steuer-Kennzahl, neue, entfallene und verschobene Kennzahlen. Die Jahresprüfung `python -m steuerbote.ustva.yearcheck` vergleicht Kennzahlen, Zeile, Art und die Paare aus Bemessungsgrundlage und Steuer mit der Jahresdokumentation von ERiC; Bezeichnung, Wirkung und Steuersatz stehen nur im Vordruck. Dazu prüfen, ob die Zeilen der Summen noch stimmen (`OUTPUT_TAX_LINES`, `INPUT_TAX_LINES`, `OTHER_TAX_LINES`); sie gelten bisher für alle Jahrgänge. Liegt eine Kennzahl mit Wirkung im neuen Vordruck außerhalb dieser Zeilen, weist `_index` den Katalog ab; dann werden die Zeilen der Summen ein Teil des Jahrgangs, in `kennzahlen.py` und in `calculation.py`, das sie liest.
3. Den Rundungssatz und die Fälligkeit in der Anleitung mit `rounding.py` und `period.py` vergleichen.
4. Zuerst die Tests schreiben: eine Tabelle des neuen Vordrucks in `test_kennzahlen.py` nach dem Muster von `FORM_UST_1_A_2026`. Dann den neuen Katalog als weiteren Jahrgang in `CATALOGUES` anlegen, mit Datum und Geschäftszeichen des neuen Schreibens im Docstring von `kennzahlen.py`. Der Katalog des Vorjahres bleibt.
5. Die neuen Ausgaben der DATEV-Kontenrahmen SKR 03 und SKR 04 („Gültig für“ das neue Jahr) gegen `defaults.py` prüfen: Nummern und Bezeichnungen aller Konten aus Regeln, Verprobungen, beobachteten und bewusst ausgenommenen Konten, die Liste der mit „U“ gekennzeichneten Konten in `tests/fixtures/datev_2026.py` als neue Ausgabe daneben anlegen (der Vollständigkeitstest `test_completeness.py` prüft die Vorgaben dagegen), und ob die Vorgaben gegen den neuen Katalog gültig sind (`default_mapping(chart, year)`). Auch hier zuerst `test_defaults.py`. Ändern sich die Vorgaben, kommt die neue Ausgabe in `DATEV_EDITION`, `REVISION` beginnt wieder bei 1, und `DIGESTS` in `test_defaults.py` bekommt die Summen der neuen Stände. Die Vorgaben werden gegen den neuesten Katalog gebaut: Nimmt eine ihrer Regeln eine Kennzahl, die der neue Vordruck nicht mehr hat, scheitert schon der Import von `defaults.py`, und die Vorgaben brauchen einen Stand je Jahr.
6. Diese Seite aktualisieren: Quelle, Kennzahlen, Vorgaben, Verprobungen, beobachtete und bewusst ausgenommene Konten. Die Tabellen entstehen aus dem Code; [`test_docs.py`](../steuerbote/ustva/tests/test_docs.py) gleicht sie mit `defaults.py` ab und muss ohne Abweichung durchlaufen.
7. Das XML-Schema des Jahres aus der ERiC-Dokumentation prüfen: `python -m steuerbote.ustva.yearcheck <Verzeichnis> <Jahr>` vergleicht Katalog, Schema des XML und Vordruck USt 1 H mit Jahresdokumentation und Schema des Jahres und muss ohne Ausgabe enden, siehe [Jahresprüfung](entwicklung.md#jahresprüfung).
8. Die Umsatzsteuererklärung hat eine eigene Uhr: Ihr Vordruck für ein Jahr erscheint erst nach dessen Voranmeldungen. Mit ihm die [Vorgaben der Umsatzsteuererklärung](#vorgaben-der-umsatzsteuererklärung) gegen die Anleitung USt 2 E des Jahres prüfen und als Jahrgang in `ROLE_FIELDS`, `ANNUAL_ACCOUNTS` und `REVISIONS` von [`ustjahr/defaults.py`](../steuerbote/ustjahr/defaults.py) anlegen, die Summen der neuen Stände in `DIGESTS` von `ustjahr/tests/test_defaults.py`, und die Muster und Listen der Felder aus der Jahresdokumentation E50 des Jahres in `SCHEMAS` von [`elster/ust2a_xml.py`](../steuerbote/elster/ust2a_xml.py). [`ustjahr/tests/test_years.py`](../steuerbote/ustjahr/tests/test_years.py) schlägt fehl, bis jede Tabelle das Jahr hat; die Tests von `ust2a_xml.py` vergleichen jedes Muster mit der Jahresdokumentation.

Warum ein Katalog je Jahr: ELSTER nimmt eine Meldung nur in der Datenart des Jahres ihres Zeitraums an und hält das laufende Jahr und die drei Jahre davor offen. Steuerbote wählt den Katalog deshalb nach dem Jahr des Zeitraums. So behalten frühere Zeiträume und berichtigte Anmeldungen ihre Kennzahlen, und der Katalog für ein neues Jahr kann dazukommen, sobald das BMF den Vordruck veröffentlicht.

Ein Jahr kann vor seinem BMF-Schreiben dazukommen, aus der Dokumentation der Beta, so 2027 (siehe [Jahrgang 2027, vorläufig](#jahrgang-2027-vorläufig)): dann trägt `YEARS` statt des Schreibens `provisional`, die Dokumentation (`documentation`) und das Jahr des Vordrucks, dessen Zeilen und Bezeichnungen es behält (`form_year`), und die Docstrings von `kennzahlen.py` und `form.py` zitieren die Jahresdokumentation statt des Schreibens. Mit dem Schreiben holt der Jahrgang die Schritte 1 bis 6 nach, mit der freigegebenen Version von ERiC Schritt 7; dann fällt `provisional` weg.
