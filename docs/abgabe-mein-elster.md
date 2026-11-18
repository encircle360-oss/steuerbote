# Abgabe über Mein ELSTER

Ohne eigene Hersteller-ID geht eine Umsatzsteuer-Voranmeldung nicht über ERiC an das Finanzamt. Steuerbote schreibt sie deshalb als XML-Datei, die du in Mein ELSTER in das Formular der Umsatzsteuer-Voranmeldung importierst. Der Import füllt nur das Formular. Prüfen und absenden tust du selbst in Mein ELSTER.

## Voraussetzungen

- **Einstellungen Umsatzsteuer-Voranmeldung** des Unternehmens mit Bundesland und Steuernummer. Daraus bildet Steuerbote die 13-stellige Steuernummer für ELSTER.
- **Datenlieferant** in denselben Einstellungen: Straße und Hausnummer, Postleitzahl und Ort sind Pflicht für die Datei. Der Name ist es auch, bleibt das Feld leer, steht der Name des Unternehmens darin. Telefon und E-Mail sind freiwillig. Beim Speichern prüfen die Einstellungen Länge und Zeichen, siehe [Zeichensatz](#zeichensatz).
- **Wirtschafts-Identifikationsnummer** in den Einstellungen, wenn das Unternehmen eine hat: „DE“ und neun Ziffern, ohne die fünfstellige Ergänzung wie „-00001“. Fehlt sie, gibt ERiC nur einen Hinweis (11085154).
- **Eine berechnete Meldung**, die abgegeben werden könnte: Status „Bereit“, oder „Berechnet“ mit einer Begründung in den Bemerkungen. Für eine schon abgegebene Meldung lässt sich die Datei ebenfalls erzeugen, für eine ersetzte oder stornierte nicht.
- **Ein Zugang zu Mein ELSTER**, mit dem das Unternehmen seine Voranmeldungen abgibt.

## Datei erzeugen

1. Die Umsatzsteuer-Voranmeldung öffnen und „Berechnen“.
2. Kennzahlen prüfen, Korrekturen mit Begründung eintragen und die Kennzeichen setzen (Kz 10, 22, 26 und 29). Wer Kz 500 wählt, trägt die Begründung zu Kz 500 ein: Pflicht, höchstens 180 Zeichen in einer Zeile.
3. Speichern.
4. „XML für Mein ELSTER“ klicken. Steuerbote baut die Datei aus der gespeicherten Meldung, hängt sie privat an die Meldung und öffnet sie zum Herunterladen.

Die Datei heißt `UStVA_<Jahr>_<Zeitraum>.xml`, etwa `UStVA_2026_10.xml` für Oktober 2026 oder `UStVA_2026_41.xml` für das I. Kalendervierteljahr 2026, eine berichtigte Anmeldung `UStVA_2026_10_berichtigt.xml`. ELSTER schreibt keinen Namen vor. Liegt auf dem Server schon eine Datei dieses Namens mit anderem Inhalt, hängt Frappe sechs Zeichen an den Namen. Jeder Klick baut die Datei aus den aktuellen Werten; dieselbe Datei hängt nur einmal an der Meldung. Als Erstellungsdatum trägt sie den Tag, an dem sie entsteht.

## In Mein ELSTER importieren

1. In Mein ELSTER mit dem Zugang des Unternehmens anmelden.
2. „Formulare und Leistungen“ › „Umsatzsteuer-Voranmeldung“ des Jahres der Meldung › „Datenübernahme“ › „XML-Import“ wählen und die Datei hochladen. Die Bezeichnungen in Mein ELSTER können abweichen, die ELSTER-Hilfe beschreibt den Weg unter „Benutzeranleitung zum Hochladen von Formulardaten“.
3. Das Formular prüfen: Zeitraum, Steuernummer, jede Kennzahl und die Kennzeichen. Mein ELSTER übernimmt alles unter `/Anmeldungssteuern/Steuerfall` bis auf Kz 09 und einige Namensfelder von Berater, Unternehmer und Mandant.
4. Kz 83 vergleichen: „Beim Hochladen von Formulardaten wird der Wert aus "kz83" in das Feld für die manuelle Eingabe im Formular zur Umsatzsteuer-Voranmeldung übernommen.“ Der Betrag, den das Formular selbst rechnet, muss mit Kz 83 der Meldung übereinstimmen. Steuerbote hat Kz 83 vor dem Schreiben nachgerechnet, siehe [Prüfungen](#prüfungen-bevor-die-datei-entsteht).
5. In Mein ELSTER absenden.
6. In Steuerbote die Meldung einreichen. Damit steht sie auf „Abgegeben“, und eine weitere Meldung für denselben Zeitraum muss eine berichtigte Anmeldung sein.

## Welche Jahre

Die ELSTER-Hilfe sagt: „Die Funktion zum Hochladen von Formulardaten (XML-Datei) steht Ihnen für alle angebotenen Jahresversionen der Umsatzsteuer-Voranmeldung (UStVA) und der Mitteilung nach § 146a Abs. 4 AO zur Verfügung. In der Regel sind das die Formulare für die Veranlagungszeiträume des laufenden und der drei vergangenen Kalenderjahre.“ Jedes Jahr hat ein eigenes Schema mit eigenem Namensraum. Steuerbote kennt Kennzahlen und Schema bisher nur für 2026 und lehnt die Datei für andere Jahre ab. Ein neuer Jahrgang kommt mit seinem Katalog der Kennzahlen und seinem Schema dazu.

## Was die Datei enthält

- **Nur die Nutzdaten:** das Element `Anmeldungssteuern` im Namensraum `http://finkonsens.de/elster/elsteranmeldung/ustva/v2026` mit `version="2026"`. Die Hilfe nennt die Besonderheit, „dass nur der Inhalt der Nutzdaten (vollständiger Pfad gemäß Schnittstellenbeschreibung, z. B.: "/Elster/DatenTeil/Nutzdatenblock/Nutzdaten/Anmeldungssteuern") hochgeladen werden kann“.
- **Zeichensatz ISO-8859-15:** „Der zu verwendende Zeichensatz der XML-Datei lautet ISO-8859-15.“ Die erste Zeile lautet wie im Beispiel der Hilfe `<?xml version="1.0" encoding="ISO-8859-15" standalone="no"?>`.
- **Erstellungsdatum und Datenlieferant** mit Name, Straße, Postleitzahl, Ort, Telefon und E-Mail. Mein ELSTER übernimmt sie nicht. ERiC verlangt sie (110085074 bis 110085078), und für ERiC schreibt Steuerbote denselben Baum.
- **Die Voranmeldung** unter `Steuerfall/Umsatzsteuervoranmeldung`: Jahr, Zeitraum, Steuernummer, Wirtschafts-Identifikationsnummer, wenn eingetragen, die Kennzahlen mit Betrag, die Kennzeichen und Kz 500 mit Begründung.

Nicht in der Datei:

- **Kein Umschlag:** kein `Elster`, kein `TransferHeader`, kein `NutzdatenHeader`. Den Umschlag braucht nur die Übermittlung über ERiC.
- **Kein Testmerker:** Jede Datei ist ein Echtfall. Testlieferungen gibt es nur über ERiC.
- **Keine Hersteller-ID, kein Kz 09:** Mein ELSTER übernimmt Kz 09 nicht, und der Import läuft ohne ERiC. Die Hersteller-ID 74931 aus den Beispielen der ERiC-Dokumentation „dient in der Dokumentation nur noch zu Illustrationszwecken“ (ERiC-Entwicklerhandbuch 6.5.3) und steht nie in einer Datei.
- **Keine Angaben zu Unternehmer, Berater oder Mandant.**

## Prüfungen, bevor die Datei entsteht

Steuerbote schreibt die Datei nur, wenn sie diese Regeln erfüllt. Die Fehlercodes stammen aus der Jahresdokumentation UStVA 2026 der ERiC-Dokumentation, die Formate aus ihrem Blatt „Allg. Information“ und dem Schema `UStVA-2026.xsd`.

| Regel | Grundlage |
|---|---|
| Die Elemente stehen in der Reihenfolge des Schemas, nicht nach Nummern: Kz 90 folgt auf Kz 93. | `xs:sequence` in `UStVA-2026.xsd` |
| Bemessungsgrundlagen in vollen Euro, höchstens 13 Stellen; Steuern mit genau zwei Nachkommastellen und Punkt, höchstens 11 Stellen vor dem Komma. Kein Pluszeichen, keine führende Null, kein „-0“. | Formatkennzeichen N und P |
| Kz 37 und Kz 39 (Formatkennzeichen %) und Kz 50 (U) nehmen kein Vorzeichen. Ein negativer Betrag dort wird abgelehnt. | Formatkennzeichen % und U |
| Kennzahlen mit 0 entfallen, Kz 83 steht immer in der Datei, auch als 0.00. | Hinweise 110085186 bis 110085217, Pflichtfeld 110085064 |
| Bemessungsgrundlage und Steuer stehen gemeinsam: Kz 35 und 36, 46 und 47, 73 und 74, 76 und 80, 84 und 85, 94 und 96, 95 und 98. Eine Grundlage, die auf 0 Euro fällt, steht als 0 neben ihrer Steuer. | 110085065 bis 110085072 |
| Kz 83 wird aus den geschriebenen Werten nachgerechnet: die Steuer der Zeilen 13 bis 32 samt der Steuer, die das Formular aus Kz 81, 86, 89 und 93 selbst berechnet, abzüglich der Zeilen 38 bis 44, zuzüglich der Zeilen 46 und 47, abzüglich Kz 39. Weicht Kz 83 der Meldung davon ab, entsteht keine Datei. ERiC prüft Kz 83 nicht. | keine Regel in ERiC |
| Kz 29 nur mit einem Überschuss in Kz 83 oder in einer berichtigten Anmeldung. | 11085149 |
| Kz 500 (1 bis 4) nur mit Begründung und die Begründung nur mit Kz 500, höchstens 180 Zeichen in einer Zeile. Die Meldung prüft das schon beim Speichern. | 11085137 |
| Das Datum in Kz 70 liegt im Jahr des Zeitraums. Die Meldung hat für Kz 70 noch kein Feld. | 11085153 |
| Steuernummer mit 13 Ziffern, die fünfte ist 0; Wirtschafts-Identifikationsnummer „DE“ und neun Ziffern. | 110085044, Schema |
| Datenlieferant: Name bis 45 Zeichen, Straße und Hausnummer bis 30, Postleitzahl bis 12, Ort bis 30, Telefon bis 20, E-Mail bis 70. Name, Straße, Postleitzahl und Ort sind Pflicht. | 110085075 bis 110085078, Schema |
| Texte nur aus dem Zeichensatz, ohne Leerzeichen am Anfang oder Ende. | Blätter „Zeichensatz“ und „Formale Fehler“ |

Hinweise, die ERiC nur meldet, ohne die Abgabe anzuhalten, prüft Steuerbote nicht, etwa einen Zeitraum in der Zukunft (11085134) oder eine unwahrscheinliche Steuer zu einer Bemessungsgrundlage (11085142 bis 11085148).

## Zeichensatz

ELSTER nimmt in jedem Text nur den Zeichensatz Standard_E_V2: die druckbaren Zeichen von ISO-8859-15 ohne geschütztes Leerzeichen, ©, weiches Trennzeichen, ¶ und ·. Zeilenumbrüche sind in keinem Feld der Voranmeldung erlaubt. Ein Zeichen außerhalb des Satzes fällt durch das Schema, auch als Zeichenreferenz wie `&#8222;`.

Texte aus ERPNext tragen oft typografische Zeichen. Steuerbote ersetzt die häufigen:

| Zeichen | wird zu |
|---|---|
| „ “ ” ‟ ″ | `"` |
| ‚ ‘ ’ ‛ ′ ‹ › | `'` |
| Bindestriche, Gedankenstriche und das Minuszeichen (U+2010 bis U+2015, U+2212) | `-` |
| … | `...` |
| geschützte und schmale Leerzeichen, Tabulator, Zeilenumbruch | Leerzeichen |
| weiches Trennzeichen, Zeichen ohne Breite | entfällt |

Danach werden mehrere Leerzeichen zu einem, und Leerzeichen am Anfang und Ende entfallen. Jedes andere Zeichen außerhalb des Satzes lehnt Steuerbote ab und nennt es mit seinem Codepunkt, etwa ł (U+0142). Wie ein Name ohne dieses Zeichen geschrieben wird, entscheidest du, nicht Steuerbote.

## Berichtigte Anmeldung

Eine berichtigte Anmeldung trägt Kz 10 = 1, und ihre Datei heißt `UStVA_<Jahr>_<Zeitraum>_berichtigt.xml`. Jede Kennzahl, die eine früher abgegebene Meldung desselben Zeitraums hatte und die berichtigte nicht mehr hat, schreibt die Datei ausdrücklich mit 0. Ohne Kz 10 meldet ERiC für einen solchen Nullwert einen Hinweis: „Da es sich nicht um eine Berichtigung der Anmeldung handelt, ist die Erklärung eines Nullwertes nicht erforderlich.“ In einer Berichtigung ist der Nullwert also vorgesehen. Ob Mein ELSTER ihn braucht, ist noch offen.

## Kennzahlen und Elemente

Die Kinder von `Umsatzsteuervoranmeldung` in der Reihenfolge von `UStVA-2026.xsd`, mit der Zeile im Vordruck USt 1 A 2026. „Euro“ heißt volle Euro ohne Cent, „Euro und Cent“ genau zwei Nachkommastellen. Was nicht ohne Vorzeichen ist, darf negativ sein.

| Nr. | Element | Zeile | Format | Hinweis |
|---|---|---|---|---|
| 1 | `Jahr` | | Jahr des Zeitraums | Pflicht (110085048), gleich dem Jahr des Namensraums (110085047) |
| 2 | `Zeitraum` | | 01 bis 12, 41 bis 44 | Pflicht (110085037), Zeitraumcode aus `period.py` |
| 3 | `Steuernummer` | | 13 Ziffern, fünfte 0 | Pflicht (110085044) |
| 4 | `WIdNr` | 1 | DE und 9 Ziffern | freiwillig, ohne Eintrag Hinweis 11085154 |
| 5 | `Kz09` | | 5 Ziffern | Hersteller-ID, nur für ERiC (110085045), nie in der Importdatei |
| 6 | `Kz10` | 10 | 1 | berichtigte Anmeldung |
| 7 | `Kz21` | 35 | Euro | |
| 8 | `Kz22` | 11 | 1 | Belege beigefügt |
| 9 | `Kz26` | 54 | 1 | SEPA-Lastschriftmandat nicht verwenden, Hinweis 11085155 |
| 10 | `Kz29` | 53 | 1 | nur mit Überschuss in Kz 83 oder Kz 10 (11085149) |
| 11 | `Kz35` | 16 | Euro | mit Kz 36 (110085065) |
| 12 | `Kz36` | 16 | Euro und Cent | mit Kz 35 (110085065) |
| 13 | `Kz37` | 52 | Euro und Cent, ohne Vorzeichen | |
| 14 | `Kz39` | 49 | Euro und Cent, ohne Vorzeichen | Sondervorauszahlung |
| 15 | `Kz41` | 19 | Euro | |
| 16 | `Kz42` | 33 | Euro | |
| 17 | `Kz43` | 22 | Euro | |
| 18 | `Kz44` | 20 | Euro | |
| 19 | `Kz45` | 36 | Euro | |
| 20 | `Kz46` | 30 | Euro | mit Kz 47 (110085066) |
| 21 | `Kz47` | 30 | Euro und Cent | mit Kz 46 (110085066) |
| 22 | `Kz48` | 23 | Euro | |
| 23 | `Kz49` | 21 | Euro | |
| 24 | `Kz50` | 51 | Euro, ohne Vorzeichen | |
| 25 | `Kz59` | 43 | Euro und Cent | |
| 26 | `Kz60` | 34 | Euro | |
| 27 | `Kz61` | 39 | Euro und Cent | ohne Kz 89, 93 oder 95 Hinweis 11085152 |
| 28 | `Kz62` | 40 | Euro und Cent | |
| 29 | `Kz63` | 42 | Euro und Cent | |
| 30 | `Kz64` | 44 | Euro und Cent | |
| 31 | `Kz65` | 46 | Euro und Cent | |
| 32 | `Kz66` | 38 | Euro und Cent | |
| 33 | `Kz67` | 41 | Euro und Cent | |
| 34 | `Kz69` | 47 | Euro und Cent | |
| 35 | `Kz70` | 12 | TT.MM.JJJJ | im Jahr des Zeitraums (11085153) |
| 36 | `Kz73` | 31 | Euro | mit Kz 74 (110085068) |
| 37 | `Kz74` | 31 | Euro und Cent | mit Kz 73 (110085068) |
| 38 | `Kz76` | 18 | Euro | mit Kz 80 (110085069) |
| 39 | `Kz77` | 17 | Euro | |
| 40 | `Kz80` | 18 | Euro und Cent | mit Kz 76 (110085069) |
| 41 | `Kz81` | 13 | Euro | Steuer berechnet das Formular |
| 42 | `Kz83` | 50 | Euro und Cent | immer (110085064), von Steuerbote nachgerechnet |
| 43 | `Kz84` | 32 | Euro | mit Kz 85 (110085072) |
| 44 | `Kz85` | 32 | Euro und Cent | mit Kz 84 (110085072) |
| 45 | `Kz86` | 14 | Euro | Steuer berechnet das Formular |
| 46 | `Kz87` | 15 | Euro | |
| 47 | `Kz89` | 25 | Euro | Steuer berechnet das Formular |
| 48 | `Kz91` | 24 | Euro | |
| 49 | `Kz93` | 26 | Euro | Steuer berechnet das Formular |
| 50 | `Kz90` | 27 | Euro | folgt auf Kz 93 |
| 51 | `Kz94` | 29 | Euro | mit Kz 96 (110085071) |
| 52 | `Kz95` | 28 | Euro | mit Kz 98 (110085070) |
| 53 | `Kz96` | 29 | Euro und Cent | mit Kz 94 (110085071) |
| 54 | `Kz98` | 28 | Euro und Cent | mit Kz 95 (110085070) |
| 55 | `Kz500` | 55 | 1 bis 4 | nur mit Begründung (11085137) |
| 56 | `Kz500_Begruendung` | 55 | Text bis 180 Zeichen, eine Zeile | nur mit Kz 500 (11085137) |

## Offene Punkte

Diese Punkte klärt erst ein echter Import in Mein ELSTER:

- **Import ohne Kz 09.** Die Hilfe sagt, dass Mein ELSTER Kz 09 nicht übernimmt, aber nicht, ob es eine Datei ohne Kz 09 annimmt.
- **Kz 83 im Feld für die manuelle Eingabe.** Wie das Formular einen Wert behandelt, der von seiner eigenen Rechnung abweicht, ist nicht beschrieben. Steuerbote schreibt deshalb nur ein Kz 83, das zu den Kennzahlen passt.
- **Nullwerte in einer berichtigten Anmeldung,** siehe oben.
- **Die Menüpunkte in Mein ELSTER** sind nur hinter der Anmeldung zu sehen und hier nicht bestätigt.

Außerdem: Die Schemas der ERiC-Dokumentation tragen keine Lizenz, die eine Weitergabe erlaubt. Sie liegen deshalb nicht im Repository; die Tests laden die Dokumentation von ELSTER, siehe [Entwicklung](entwicklung.md#schematests).

## Quellen

- ELSTER-Hilfe „Benutzeranleitung zum Hochladen von Formulardaten“, https://www.elster.de/eportal/helpGlobal?themaGlobal=ustva_upload, abgerufen am 18. November 2026.
- ERiC-Dokumentation 44.3.6.0, https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Dokumentation.zip (SHA-256 `bad21c27ecce56d04fc04bccfd2dfa17b9ff2455aa878758100fc73a28492ad5`): Schema `Datenarten/ElsterAnmeldung/UStVA/Schema/2026/UStVA-2026.xsd`, Jahresdokumentation `Jahresdokumentation_UStVA_2026.ods` mit Formaten, Zeichensatz und Regeln nach Fehlercode, Beispiel `Beispiele/UStVA_2026.xml` und `ERiC-Entwicklerhandbuch.pdf`.
- Die Umsetzung steht in `steuerbote/elster/ustva_xml.py` und `steuerbote/elster/charset.py`, die Kennzahlen des Vordrucks in [Kennzahlen und Kontenzuordnung](ustva-kennzahlen.md).
