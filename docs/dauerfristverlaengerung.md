# Dauerfristverlängerung und Sondervorauszahlung

Mit der Dauerfristverlängerung gibt ein Unternehmen jede Umsatzsteuer-Voranmeldung einen Monat später ab und zahlt die Vorauszahlung einen Monat später. Wer monatlich abgibt, bekommt sie nur gegen eine Sondervorauszahlung, die jedes Jahr fällig wird und in der letzten Voranmeldung des Jahres über Kz 39 angerechnet wird. Diese Seite beschreibt die Regeln mit ihren Quellen, was der Rechenkern unter `steuerbote/dauerfrist` daraus macht, wie Steuerbote den Vordruck USt 1 H als XML schreibt und über ERiC übermittelt und wie der Beleg „Dauerfristverlängerung“ in ERPNext damit arbeitet. Sie ersetzt keine Steuerberatung.

## Quellen

- **§ 18 Abs. 1 und 6 UStG:** <https://www.gesetze-im-internet.de/ustg_1980/__18.html>. Absatz 6 erlaubt die Verordnung: „Zur Vermeidung von Härten kann das Bundesministerium der Finanzen mit Zustimmung des Bundesrates durch Rechtsverordnung die Fristen für die Voranmeldungen und Vorauszahlungen um einen Monat verlängern und das Verfahren näher bestimmen. Dabei kann angeordnet werden, dass der Unternehmer eine Sondervorauszahlung auf die Steuer für das Kalenderjahr zu entrichten hat.“
- **§§ 46 bis 48 UStDV:** <https://www.gesetze-im-internet.de/ustdv_1980/__46.html>, <https://www.gesetze-im-internet.de/ustdv_1980/__47.html>, <https://www.gesetze-im-internet.de/ustdv_1980/__48.html>
- **§ 108 Abs. 3 AO:** <https://www.gesetze-im-internet.de/ao_1977/__108.html>
- **BMF-Schreiben vom 29. Dezember 2025**, GZ III C 3 - S 7344/00039/007/036, mit den Vordrucken USt 1 H 2026 (Antrag auf Dauerfristverlängerung, Anmeldung der Sondervorauszahlung), USt 1 E 2026 (Anleitung zur Umsatzsteuer-Voranmeldung) und USt 5 E 2026 (Anleitung zum Antrag auf Dauerfristverlängerung/zur Anmeldung der Sondervorauszahlung): <https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/2025-12-29-vordruckmuster-USt-voranmeldung-2026.pdf?__blob=publicationFile>, SHA-256 `82e7d63a0faec542bb184acb438eaf4ce90a2d7db067bb47f92ae13b4b17613d`. Ohne `?__blob=publicationFile` liefert die Adresse eine HTML-Seite statt des PDF.
- **ERiC-Dokumentation 44.3.6.0:** <https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Dokumentation.zip>, darin `UStVA-2026.xsd`, die Jahresdokumentation `Jahresdokumentation_UStVA_2026.ods` (Blätter „Anmeldungssteuern - Felder“, „Anmeldungssteuern - Regeln“, „Anmeldungssteuern - Texte“ und „Allg. Information“), die Beispiele `UStVA_Df_2026.xml` und `UStVA_SoVZ_2026.xml`, `Datenartversionmatrix.ods` und das ERiC-Entwicklerhandbuch, Tabelle 2-13 und Kap. 5.3.2 und 8.5.1.
- **ERiC-Dokumentation 45.1.5.0 (Beta):** <https://download.elster.de/download/eric/eric_45/ERiC-45.1.5.0-Dokumentation.zip>, darin `UStVA-2027.xsd` und die Beispiele `UStVA_Df_2027.xml` und `UStVA_SoVZ_2027.xml`.
- **ELSTER-Hilfe „Benutzeranleitung zum Hochladen von Formulardaten“:** <https://www.elster.de/eportal/helpGlobal?themaGlobal=ustva_upload>
- **ELSTER-Hilfe „Anleitung zur Umsatzsteuer-Dauerfristverlängerung 2026“**, die Hilfe zum Formular in Mein ELSTER: <https://www.elster.de/eportal/helpGlobal?themaGlobal=help_ustdv_2026>
- **ELSTER-Hilfe zu Formularen:** <https://www.elster.de/eportal/helpGlobal?themaGlobal=formulare_eop>. Sie führt das Formular unter „Umsatzsteuer“ als „Dauerfristverlängerung / Sondervorauszahlung“.
- **ERPNext 16**, die DocTypes Company (Felder `date_of_establishment`, „Gründungsdatum“, und `default_holiday_list`, „Standard Feiertagsliste“) und Holiday List mit der Tabelle Holiday (`holiday_date` und `weekly_off`, „Wöchentlich frei“): <https://github.com/frappe/erpnext/tree/version-16/erpnext/setup/doctype>

Gelesen am 20. November 2026.

## Was die Dauerfristverlängerung ist

„Das Finanzamt hat dem Unternehmer auf Antrag die Fristen für die Übermittlung der Voranmeldungen und für die Entrichtung der Vorauszahlungen (§ 18 Abs. 1, 2 und 2a des Gesetzes) um einen Monat zu verlängern. Das Finanzamt hat den Antrag abzulehnen oder eine bereits gewährte Fristverlängerung zu widerrufen, wenn der Steueranspruch gefährdet erscheint.“ (§ 46 UStDV)

Einen Bescheid gibt es nicht. Die Anleitung USt 5 E sagt: „Sie können die Fristverlängerung in Anspruch nehmen, wenn das Finanzamt Ihren Antrag nicht ablehnt; ein Bewilligungsbescheid wird nicht erteilt. Die Fristverlängerung gilt solange, bis Sie gegenüber dem Finanzamt erklären, dass Sie die Fristverlängerung nicht mehr in Anspruch nehmen wollen oder das Finanzamt die Fristverlängerung widerruft (§ 46 UStDV).“

Mit Dauerfristverlängerung ist die Voranmeldung für Januar am 10. März fällig statt am 10. Februar. Diese Frist rechnet schon heute `Period.deadline` im Kern der Voranmeldung, je Jahr nach den Einstellungen des Unternehmens, siehe [Zeiträume und Fristen](ustva-kennzahlen.md#zeiträume-und-fristen).

## Wer was abgibt

Die Sondervorauszahlung ist die Auflage für Unternehmen, die monatlich abgeben: „Die Fristverlängerung ist bei einem Unternehmer, der die Voranmeldungen monatlich zu übermitteln hat, unter der Auflage zu gewähren, dass dieser eine Sondervorauszahlung auf die Steuer eines jeden Kalenderjahres entrichtet.“ (§ 47 Abs. 1 Satz 1 UStDV) Der Vordruck USt 1 H sagt Unternehmen, die vierteljährlich abgeben: „Der Antrag auf Dauerfristverlängerung ist nicht zu stellen, wenn Dauerfristverlängerung bereits gewährt worden ist. Er ist nicht jährlich zu wiederholen. Eine Sondervorauszahlung ist nicht zu berechnen und anzumelden.“

| Voranmeldungszeitraum | Im Jahr des Antrags | In jedem weiteren Jahr | Kontext in ELSTER |
|---|---|---|---|
| vierteljährlich | Antrag ohne Sondervorauszahlung | nichts | `Dauerfristverlaengerung` |
| monatlich | Antrag mit der Anmeldung der Sondervorauszahlung: „In dem Antrag hat der Unternehmer, der die Voranmeldungen monatlich zu übermitteln hat, die Sondervorauszahlung (§ 47) selbst zu berechnen und anzumelden.“ (§ 48 Abs. 1 Satz 4 UStDV) | Anmeldung der Sondervorauszahlung (§ 48 Abs. 2 UStDV) | `Umsatzsteuersondervorauszahlung` |

`obligation(year, rhythm, first_period, holidays)` in [`period.py`](../steuerbote/dauerfrist/period.py) sagt, was ein Unternehmen für ein Jahr abgibt und bis wann: `first_period` ist beim Antrag der erste Voranmeldungszeitraum, für den die Verlängerung gelten soll; ohne ihn gilt sie schon aus einem früheren Jahr fort. Für ein vierteljährlich abgebendes Unternehmen ist dann nichts abzugeben (`None`).

## Sondervorauszahlung

[`calculation.py`](../steuerbote/dauerfrist/calculation.py) rechnet die Zeilen 8 und 9 des Vordrucks USt 1 H.

**Ein Elftel des Vorjahres.** „Die Sondervorauszahlung beträgt ein Elftel der Summe der Vorauszahlungen für das vorangegangene Kalenderjahr.“ (§ 47 Abs. 1 Satz 2 UStDV) Die Anleitung USt 5 E zählt die Vorauszahlungen „ohne Berücksichtigung der Sondervorauszahlung“, und Zeile 8 des Vordrucks heißt „Summe der verbleibenden Umsatzsteuer-Vorauszahlungen zuzüglich der zu berücksichtigenden Sondervorauszahlung für das Kalenderjahr 2025“. Grundlage ist also Kz 83 aller Voranmeldungen des Vorjahres, wie sie abgegeben sind, je Zeitraum die zuletzt abgegebene, dazu die Sondervorauszahlung, die Kz 39 darin angerechnet hat. Das rechnet `previous_year_base(kz83, kz39, months_active)`, die Sondervorauszahlung daraus `sondervorauszahlung(base)`.

Das Beispiel der Anleitung USt 5 E, als Test in [`test_calculation.py`](../steuerbote/dauerfrist/tests/test_calculation.py):

| | Betrag |
|---|---|
| Kz 83 der Voranmeldungen 2025 zusammen | 39.000 € |
| Kz 39 der Voranmeldung für Dezember 2025 | 5.000 € |
| Zeile 8: Summe | 44.000 € |
| Zeile 9, Kz 38: ein Elftel, Sondervorauszahlung 2026 | 4.000 € |

**Überschuss.** „Ergibt sich bei der Berechnung der Sondervorauszahlung in Zeile 8 ein Überschuss zu Ihren Gunsten, ist die Sondervorauszahlung in Zeile 9 mit 0 € einzutragen.“ (USt 5 E) Steuerbote setzt Kz 38 auf 0, wenn Zeile 8 nicht positiv ist.

**Tätigkeit nur in einem Teil des Vorjahres.** „Hat der Unternehmer seine gewerbliche oder berufliche Tätigkeit nur in einem Teil des vorangegangenen Kalenderjahres ausgeübt, so ist die Summe der Vorauszahlungen dieses Zeitraums in eine Jahressumme umzurechnen. Angefangene Kalendermonate sind hierbei als volle Kalendermonate zu behandeln.“ (§ 47 Abs. 2 UStDV) `previous_year_base` rechnet die Summe mit `months_active` auf zwölf Monate hoch, `months_of_activity(year, began)` zählt die Monate ab dem Beginn der Tätigkeit, den angefangenen voll. Beispiel: Beginn am 15. Mai, das sind acht Monate; 20.000 € Vorauszahlungen werden zu 30.000 €, die Sondervorauszahlung ist 2.727 €.

**Beginn im laufenden Jahr.** „Hat der Unternehmer seine gewerbliche oder berufliche Tätigkeit im laufenden Kalenderjahr begonnen, so ist die Sondervorauszahlung auf der Grundlage der zu erwartenden Vorauszahlungen dieses Kalenderjahres zu berechnen.“ (§ 47 Abs. 3 UStDV) Die Anleitung USt 5 E ergänzt: „Die Sondervorauszahlung soll der durchschnittlichen Vorauszahlung eines Kalendermonats entsprechen. Fügen Sie bitte in diesem Fall ein gesondertes Blatt mit kurzer Erläuterung der Berechnung bei.“ `expected_sondervorauszahlung(expected, months_active)` teilt die erwarteten Vorauszahlungen durch die Monate der Tätigkeit im Jahr. Beispiel: Beginn am 15. März 2027, erwartet sind 15.000 € bis Dezember, das sind zehn Monate und 1.500 €.

**Volle Euro.** Kz 38 ist nach der Jahresdokumentation ein „GeldBetragOhneCent ohne Vorzeichen“ mit höchstens 13 Stellen, Formatkennzeichen U („Zahl ohne Nachkommastellen bzw. GeldbetragOhneCent, Ohne Vorzeichen, Null erlaubt“), Vordruckzeile 9. Für Zeile 8 gibt es kein Feld, ELSTER bekommt sie nicht. Wie aus dem Elftel volle Euro werden, sagen weder Verordnung noch Anleitung noch Jahresdokumentation. Steuerbote lässt die Cent weg, wie bei einer Bemessungsgrundlage, mit `to_full_euros` aus [`rounding.py`](../steuerbote/ustva/rounding.py). Das ist eine Annahme, siehe [Annahmen](#annahmen-und-offene-punkte). Zeile 8 behält ihre Cent und nach dem Hochrechnen ihren Bruchteil, so fallen die Cent nur einmal weg: Aus 43.999,99 € wird 3.999 €, kaufmännisch gerundet wären es 4.000 €.

## Fristen

[`period.py`](../steuerbote/dauerfrist/period.py) rechnet die Fristen mit `Period.deadline` aus dem Kern der Voranmeldung.

- **Antrag:** „Der Unternehmer hat die Fristverlängerung für die Übermittlung der Voranmeldungen bis zu dem Zeitpunkt zu beantragen, an dem die Voranmeldung, für die die Fristverlängerung erstmals gelten soll, nach § 18 Abs. 1, 2 und 2a des Gesetzes zu übermitteln ist.“ (§ 48 Abs. 1 Satz 1 UStDV) Das ist der 10. Tag nach Ablauf dieses Zeitraums (§ 18 Abs. 1 Satz 1 UStG), ohne die Verlängerung, die erst beantragt wird: `antrag_deadline(first_period, holidays)`.
- **Sondervorauszahlung im Jahr des Antrags:** mit dem Antrag. „Gleichzeitig hat er die angemeldete Sondervorauszahlung zu entrichten.“ (§ 48 Abs. 1 Satz 5 UStDV)
- **Sondervorauszahlung in jedem weiteren Jahr:** „Während der Geltungsdauer der Fristverlängerung hat der Unternehmer, der die Voranmeldungen monatlich zu übermitteln hat, die Sondervorauszahlung für das jeweilige Kalenderjahr bis zum gesetzlichen Zeitpunkt der Übermittlung der ersten Voranmeldung zu berechnen, anzumelden und zu entrichten.“ (§ 48 Abs. 2 Satz 1 UStDV) Die Anleitung USt 5 E sagt „jährlich bis zum 10. Februar“: `sondervorauszahlung_deadline(year, holidays)`.
- **Wochenende und Feiertage:** „Fällt das Ende einer Frist auf einen Sonntag, einen gesetzlichen Feiertag oder einen Sonnabend, so endet die Frist mit dem Ablauf des nächstfolgenden Werktags.“ (§ 108 Abs. 3 AO) Die Feiertage übergibt der Aufrufer, wie bei der Voranmeldung, denn sie unterscheiden sich je Bundesland.

| Fall | Frist |
|---|---|
| Sondervorauszahlung 2027 | Mittwoch, 10. Februar 2027 |
| Sondervorauszahlung 2029, der 10. Februar ist ein Samstag | Montag, 12. Februar 2029 |
| Sondervorauszahlung 2030, der 10. Februar ist ein Sonntag | Montag, 11. Februar 2030 |
| Antrag ab dem I. Kalendervierteljahr 2027, der 10. April ist ein Samstag | Montag, 12. April 2027 |
| Antrag mit Sondervorauszahlung ab Juli 2027 | Dienstag, 10. August 2027 |
| Antrag ab April 2029, der 10. Mai ist Christi Himmelfahrt | Freitag, 11. Mai 2029 |

Mit Dauerfristverlängerung ist die Voranmeldung für Dezember am selben Tag fällig wie die Sondervorauszahlung des nächsten Jahres, etwa am 10. Februar 2027. Die Grundlage der Sondervorauszahlung braucht Kz 83 dieser Voranmeldung.

## Anrechnung über Kz 39

„Die festgesetzte Sondervorauszahlung ist bei der Festsetzung der Vorauszahlung für den letzten Voranmeldungszeitraum des Besteuerungszeitraums zu berücksichtigen, für den die Fristverlängerung gilt. Ein danach verbleibender Erstattungsanspruch ist mit Ansprüchen aus dem Steuerschuldverhältnis aufzurechnen (§ 226 der Abgabenordnung), im Übrigen zu erstatten.“ (§ 48 Abs. 4 UStDV)

Die Anleitung zur Voranmeldung sagt zu Zeile 49: „Die festgesetzte Sondervorauszahlung ziehen Sie bitte grundsätzlich in der Voranmeldung für Dezember ab. Wenn Sie im Laufe des Kalenderjahres Ihre gewerbliche oder berufliche Tätigkeit eingestellt oder auf die Dauerfristverlängerung verzichtet haben, tragen Sie die Sondervorauszahlung bitte im letzten Voranmeldungszeitraum des Besteuerungszeitraums ein, für den die Fristverlängerung gilt.“

Heute setzt `bridge.sondervorauszahlung_values` Kz 39 in der letzten Voranmeldung des Jahres ein, im Dezember oder im IV. Kalendervierteljahr, mit der Sondervorauszahlung aus den Einstellungen. `crediting_period(year, rhythm, last_month)` nennt denselben Zeitraum, ein Test prüft beides gegeneinander. Mit `last_month` nennt es einen früheren, wenn die Verlängerung im Lauf des Jahres endet; ein solches Ende halten die Einstellungen noch nicht fest. Das Finanzamt kann die Sondervorauszahlung auch selbst festsetzen, „wenn sie vom Unternehmer nicht oder nicht richtig berechnet wurde oder wenn die Anmeldung zu einem offensichtlich unzutreffenden Ergebnis führt“ (§ 48 Abs. 3 UStDV). In Kz 39 gehört dann der festgesetzte Betrag.

## Vordruck USt 1 H in ELSTER

ELSTER kennt den Vordruck USt 1 H als zwei Kontexte der Datenart UStVA, neben der Umsatzsteuer-Voranmeldung. Das ERiC-Entwicklerhandbuch führt in Tabelle 2-13 unter den Anmeldungssteuern die „Umsatzsteuer-Dauerfristverlängerung (UStDV)“ und die „Umsatzsteuer-Dauerfristverlängerung mit Sondervorauszahlung (UStSV)“, beide mit dem Verweis auf die UStVA, und die `Datenartversionmatrix.ods` nennt für `UStVA_<Jahr>` mit dem Plugin `checkUStVA_<Jahr>` „Mit UStDV und UStSV“. Eine Datei enthält genau einen der drei Kontexte (110085099). Für den Antrag ohne Sondervorauszahlung sagt das ERiC-Entwicklerhandbuch: „Soll eine Dauerfristverlängerung ohne Sondervorauszahlung abgegeben werden, ist nur Kz 09 zu füllen. Eine Berichtigung dieser Fallkonstellation ist nicht möglich.“ Das Schema für 2026 nimmt dort zusätzlich Kz 500 mit Begründung an. [`form.py`](../steuerbote/dauerfrist/form.py) hält Felder und Regeln je Jahr als Daten (`LAYOUTS`), bisher für 2026, und `Ust1H` einen Vordruck, wie er abgegeben wird. Die Tests vergleichen die Daten mit Schema, Jahresdokumentation und Beispielen der ERiC-Dokumentation. Die Jahresdokumentation 2025 hatte statt Kz 500 noch Kz 23; ein neues Jahr bekommt deshalb ein eigenes Layout.

| Element | Zeile | `Dauerfristverlaengerung` | `Umsatzsteuersondervorauszahlung` | Inhalt |
|---|---|---|---|---|
| `Jahr` | | ja | ja | Jahr, für das der Vordruck gilt, gleich dem Jahr des Schemas (110085130, 110085131) |
| `Steuernummer` | | ja | ja | 13-stellige Steuernummer im ELSTER-Format, Pflicht (110085044) |
| `WIdNr` | 2 | ja | ja | Wirtschafts-Identifikationsnummer; fehlt sie, gibt ERiC einen Hinweis (11085154) |
| `Kz09` | 6 | ja | ja | Hersteller-ID, Pflicht (110085045) |
| `Kz10` | 7 | | ja | berichtigte Anmeldung, „1“ |
| `Kz26` | 11 | | ja | SEPA-Lastschriftmandat ausnahmsweise nicht verwenden, „1“, mit einem Hinweis (11085155) |
| `Kz29` | 10 | | ja | Verrechnung erwünscht oder Erstattungsbetrag abgetreten, „1“, nur mit Kz 10 (11085150) |
| `Kz38` | 9 | | ja | Sondervorauszahlung in vollen Euro ohne Vorzeichen, höchstens 13 Stellen, Pflicht, auch 0 (110085143) |
| `Kz500` | 12 | ja | ja | ergänzende Angaben, Schlüssel 1 bis 4, nur mit Begründung (11085137), mit einem Hinweis (110085049) |
| `Kz500_Begruendung` | 12 | ja | ja | Begründung zu Kz 500, eine Zeile, höchstens 180 Zeichen |

Die Nummern in Klammern sind die Fehlercodes der Regeln aus der Jahresdokumentation. `Ust1H` prüft, was der Vordruck selbst enthält: Kz 38 im Kontext der Sondervorauszahlung (110085143), Kz 29 nur mit Kz 10 (11085150), Kz 500 nur mit Begründung und umgekehrt (11085137), die Formate der Felder und dass der Antrag allein weder Kz 10, 26, 29 noch 38 trägt. `Ust1H.hints` nennt die Hinweise zu Kz 26 und Kz 500. Steuernummer, Wirtschafts-Identifikationsnummer und Kz 09 kommen vom Unternehmen und aus den ERiC-Einstellungen; sie prüft der Schreiber des XML, siehe [XML für ERiC](#xml-für-eric).

**Kein Feld für den Antrag.** Der Antrag auf Dauerfristverlängerung hat in keinem der beiden Kontexte ein eigenes Feld. Das Blatt „Anmeldungssteuern - Felder“ führt für `Steuerfall/Umsatzsteuersondervorauszahlung` nur die Felder der Tabelle oben, und das Blatt „Anmeldungssteuern - Texte“ druckt Abschnitt I „Antrag auf Dauerfristverlängerung“ mit dem Satz „Ich beantrage die Fristen für die Übermittlung der Umsatzsteuer-Voranmeldung und für die Entrichtung der Umsatzsteuer-Vorauszahlungen um einen Monat zu verlängern.“ (B 1110010) über Kz 09 beider Kontexte, Zeile 6. Der Kontext ist also der Antrag: bei vierteljährlicher Abgabe allein, bei monatlicher Abgabe zusammen mit der Anmeldung der Sondervorauszahlung, die § 48 Abs. 1 Satz 4 UStDV in den Antrag legt („Die Umsatzsteuer Sondervorauszahlung wird auf dem gleichen Formular wie die Dauerfristverlängerung angemeldet.“, ERiC-Entwicklerhandbuch, Kap. 8.5.1). In einem späteren Jahr ist Abschnitt I „gegenstandslos, wenn Dauerfristverlängerung bereits gewährt worden ist“ (B 1110 EZ 1), und derselbe Kontext meldet die Sondervorauszahlung allein an. Das XML ist deshalb im Jahr des Antrags und in jedem weiteren Jahr dasselbe; der Haken „Antrag auf Dauerfristverlängerung“ am Beleg wirkt nur auf Fälligkeit und Druckformat.

## XML für ERiC

`steuerbote/elster/ust1h_xml.py` schreibt den Vordruck mit `to_nutzdaten(filer, ust1h, created, hersteller_id)` als Nutzdaten für ERiC: das Element `Anmeldungssteuern` im Schema und Namensraum des Jahres des Vordrucks, mit demselben Erstellungsdatum und Datenlieferanten wie die Voranmeldung, in UTF-8 (ERiC-Entwicklerhandbuch, Kap. 5.3.2). Den Kontext wählt der Vordruck selbst: Wer monatlich abgibt, schickt `Umsatzsteuersondervorauszahlung`, wer vierteljährlich abgibt, `Dauerfristverlaengerung` (`Context.for_rhythm`, siehe [Wer was abgibt](#wer-was-abgibt)). Das Jahr ist ein Parameter; der Schreiber braucht für ein Jahr das Layout des Vordrucks in `form.py` und das Schema in `ustva_xml.py`.

| Regel | Grundlage |
|---|---|
| Genau ein Kontext im Steuerfall, ohne Unternehmer, Berater oder Mandant; Kz 09 enthält nur die Hersteller-ID. | 110085099, 110085046 |
| Die Elemente stehen in der Reihenfolge der `xs:sequence` des Kontexts. | `UStVA-2026.xsd`, Typen `Dauerfristverlaengerung_m472961002_CType` und `Umsatzsteuersondervorauszahlung_m472961002_CType` |
| `Jahr` ist das Jahr des Schemas und damit des Vordrucks, Pflicht. | 110085130, 110085131, 110085048 |
| Steuernummer mit 13 Ziffern, die fünfte ist 0, Pflicht; die Wirtschafts-Identifikationsnummer, wenn das Unternehmen eine hat. | 110085044, 11085154, Schema |
| Kz 09 trägt die Hersteller-ID aus fünf Ziffern, wie bei der Voranmeldung; 74931 lehnt Steuerbote ab, weil sie nur der Veranschaulichung dient. | 110085045, `HerstellerIDSType`, ERiC-Entwicklerhandbuch, Kap. 6.5.3 |
| Kz 38 nur in der Anmeldung der Sondervorauszahlung und dort immer, auch als 0, in vollen Euro ohne Vorzeichen, höchstens 13 Stellen. | 110085143, Formatkennzeichen U |
| Kz 29 nur mit Kz 10. | 11085150 |
| Kz 500 nur mit Begründung und umgekehrt; die Begründung in einer Zeile mit höchstens 180 Zeichen im Zeichensatz von ELSTER, wie bei der Voranmeldung. | 11085137, Blatt „Zeichensatz“, siehe [Zeichensatz](abgabe-mein-elster.md#zeichensatz) |

Eine Datei zum Hochladen in Mein ELSTER gibt es für den Vordruck nicht: Die ELSTER-Hilfe bietet das Hochladen „für alle angebotenen Jahresversionen der Umsatzsteuer-Voranmeldung (UStVA) und der Mitteilung nach § 146a Abs. 4 AO“ an, den Antrag auf Dauerfristverlängerung nennt sie nicht. Der Schreiber hat deshalb nur `to_nutzdaten`.

Die Tests prüfen die Nutzdaten beider Kontexte gegen `UStVA-2026.xsd` und den Umschlag gegen `elster11_UStVA_2026_extern.xsd`, Byte für Byte gegen eigene Beispieldateien und gegen die Beispiele `UStVA_Df_2026.xml` und `UStVA_SoVZ_2026.xml` der ERiC-Dokumentation: Ohne Kommentare, ohne den Unternehmer, den Steuerbote nicht schreibt, und mit einer eigenen Hersteller-ID statt 74931 sind sie in Canonical XML 2.0 dasselbe Dokument wie das, was Steuerbote mit ihren Daten schreibt. Das Schema bildet die Regel 110085099 nicht ab: Eine Datei mit zwei Kontexten besteht es, deshalb hält sich der Schreiber selbst daran, und die Simulation prüft es, siehe [ERiC](eric.md#simulation). Das Schema 2027 der ERiC-Dokumentation 45.1.5.0 (Beta) hat dieselben Elemente in beiden Kontexten, nur im Namensraum `…/ustva/v2027`.

## Was Steuerbote heute rechnet und übermittelt

**Heute** gibt es den Rechenkern unter `steuerbote/dauerfrist`, reines Python ohne Frappe mit vollständiger Testabdeckung: Grundlage und Sondervorauszahlung, Fristen, den Zeitraum der Anrechnung und das Modell des Vordrucks. Auf ihm baut der Beleg „Dauerfristverlängerung“ in ERPNext auf, siehe [Der Beleg in ERPNext](#der-beleg-in-erpnext). Er berechnet Kz 38 aus den abgegebenen Voranmeldungen des Vorjahres, schreibt den Vordruck als XML und übermittelt ihn über ERiC wie die Voranmeldung, siehe [Übermittlung an ELSTER](uebermittlung.md). Mit der Abgabe schreibt er die Sondervorauszahlung in die Einstellungen, aus denen die letzte Voranmeldung des Jahres sie in Kz 39 abzieht.

**Was von Hand bleibt.** Mit Hersteller-ID und eingerichteter ERiC-Laufzeitumgebung nichts: Prüfen, Testsenden und Senden laufen am Beleg, das Übermittlungsprotokoll liegt an der ELSTER-Übermittlung. Ohne Hersteller-ID arbeitet ERiC nicht, auch nicht zum Prüfen (ERiC-Entwicklerhandbuch, Kap. 6.5.3); dann laufen Prüfen und Testsenden als Simulation, und abgegeben wird der Vordruck in Mein ELSTER von Hand, denn eine Datei zum Hochladen gibt es für ihn nicht, siehe [In Mein ELSTER eintragen](#in-mein-elster-eintragen).

**Für ein neues Jahr** braucht der Kern das Layout des Vordrucks (`form.py`) und der Schreiber das Schema des Jahres (`ustva_xml.py`). Die ERiC-Dokumentation 44.3.6.0 kennt 2026; die Sondervorauszahlung 2027 ist am 10. Februar 2027 fällig, ihr Schema steht in der ERiC-Dokumentation 45.1.5.0 (Beta). Ein Beleg eines Jahres ohne Layout oder Schema lässt sich berechnen und von Hand abgeben, aber nicht übermitteln.

## Der Beleg in ERPNext

Der DocType `VAT Return Extension` heißt in der Oberfläche „Dauerfristverlängerung“, ist einreichbar und hat den Nummernkreis `DFV-.{year}.-.#####`: Das Jahr im Namen ist das Jahr, für das der Vordruck gilt, etwa DFV-2027-00001 für einen Vordruck für 2027, der im November 2026 entsteht. Er hält einen Vordruck USt 1 H eines Unternehmens für ein Jahr; je Unternehmen und Jahr gibt es einen, stornierte zählen nicht mit. Der Controller `vat_return_extension.py` bewegt nur Daten: Beträge, Fristen und die Regeln des Vordrucks kommen aus dem Kern. Was zwischen Beleg und Kern umgerechnet wird, steht ohne Frappe-Import in `vat_return_extension/bridge.py`, was der Beleg aus ERPNext liest, in `steuerbote/dauerfrist_sources.py`.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company`, `year` | Unternehmen, Jahr | Pflicht |
| `antrag` | Antrag auf Dauerfristverlängerung | im Jahr des Antrags; ohne ihn gilt die Verlängerung aus einem früheren Jahr fort |
| `first_month` | Verlängert ab Monat | mit dem Antrag Pflicht: der Monat, dessen Voranmeldung als erste verlängert wird, 1 bis 12; bei vierteljährlicher Abgabe der erste Monat des Quartals |
| `is_correction` | Berichtigte Anmeldung (Kz 10) | nur bei der Anmeldung der Sondervorauszahlung |
| `context` | Art des Vordrucks | berechnet: Anmeldung der Sondervorauszahlung (`Umsatzsteuersondervorauszahlung`) oder Antrag auf Dauerfristverlängerung (`Dauerfristverlaengerung`) |
| `rhythm`, `first_period_label` | Abgaberhythmus, Verlängert ab | berechnet; der erste verlängerte Voranmeldungszeitraum nur mit Antrag |
| `deadline` | Fälligkeitsdatum | berechnet, siehe unten |
| `crediting_period_label` | Angerechnet in Kz 39 von | berechnet: die letzte Voranmeldung des Jahres im Abgaberhythmus des Dezembers (`crediting_period`) |
| `status` | Status | Entwurf, Berechnet, Bereit oder Abgegeben |
| `transmission_in_progress` | Übermittlung läuft | gesetzt, solange Prüfen, Testsenden oder Senden läuft; so lange lässt sich der Beleg nicht ändern |
| `base_rows` | Abgegebene Voranmeldungen des Vorjahres | Tabelle „Grundlage der Sondervorauszahlung“: Voranmeldungszeitraum, Zeitraumcode, Umsatzsteuer-Voranmeldung, Kz 83 und Kz 39 |
| `missing_periods` | Fehlt in der Grundlage | Voranmeldungszeiträume des Vorjahres ohne abgegebene Voranmeldung |
| `kz83`, `kz39` | Summe der Kz 83, Angerechnete Sondervorauszahlung (Kz 39) | Summen über die Tabelle |
| `established_on`, `months_active` | Gründungsdatum, Monate der Tätigkeit | aus dem Gründungsdatum des Unternehmens, gelesen von Berechnen |
| `computed_base` | Grundlage aus den Voranmeldungen | Zeile 8 aus Kz 83 und Kz 39 (`previous_year_base`) |
| `base_override`, `base_override_reason` | Grundlage von Hand, Begründung der Grundlage von Hand | siehe unten |
| `base` | Grundlage (Zeile 8) | die Grundlage, aus der Kz 38 folgt |
| `sondervorauszahlung` | Sondervorauszahlung (Kz 38) | `sondervorauszahlung` oder, nach einem Beginn im Jahr des Belegs, `expected_sondervorauszahlung` |
| `offset_requested`, `no_sepa_mandate` | Verrechnung erwünscht oder Erstattungsbetrag abgetreten (Kz 29), SEPA-Lastschriftmandat ausnahmsweise nicht verwenden (Kz 26) | nur bei der Anmeldung der Sondervorauszahlung |
| `supplementary_code`, `kz500_begruendung` | Ergänzende Angaben zur Steueranmeldung (Kz 500), Begründung zu Kz 500 | in beiden Vordrucken |
| `findings` | Offene Punkte | was dem Status „Bereit“ entgegensteht |
| `remarks` | Anmerkungen | Pflicht, wenn ein Beleg abgegeben wird, der nicht bereit ist |
| `filed_via`, `filed_on`, `transferticket`, `filing_note` | Abgegeben über, Abgegeben am, Transferticket, Wie und wann abgegeben | setzt die Abgabe: ERiC (`eric`) mit dem Tag der Antwort und dem Transferticket nach einem Senden, das ELSTER angenommen hat, sonst der Vermerk mit Mein ELSTER (`mein_elster`) oder einem anderen Weg (`other_way`) |

**Welcher Vordruck.** Beim Speichern liest der Beleg aus den Einstellungen den Voranmeldungszeitraum des ersten Monats, den er abdeckt: mit Antrag den Monat in „Verlängert ab Monat“, sonst den Januar. Wer dann monatlich abgibt, meldet die Sondervorauszahlung an, wer vierteljährlich abgibt, beantragt nur die Dauerfristverlängerung (`Context.for_rhythm`). Ein vierteljährlich abgebendes Unternehmen, dessen Verlängerung fortgilt, gibt nichts ab (`obligation` ergibt `None`), und das Speichern lehnt einen solchen Beleg ab. Kz 10, 26 und 29 trägt nur die Anmeldung der Sondervorauszahlung, beim Antrag allein setzt das Speichern sie zurück.

**Berechnen** liest die Voranmeldungen des Vorjahres und das Gründungsdatum des Unternehmens:

1. Als abgegeben zählt eine Voranmeldung, die eingereicht ist und den Status „Abgegeben“ hat. Eine durch eine berichtigte Anmeldung ersetzte steht auf „Ersetzt“ und fällt heraus, je Voranmeldungszeitraum zählt die zuletzt abgegebene. Aus ihr übernimmt der Beleg Kz 83 und Kz 39, wie die Meldung sie hält: Kz 83 ist der Betrag, den ihre Datei für Mein ELSTER schreibt.
2. Hat das Unternehmen im Vorjahr begonnen, rechnet `previous_year_base` die Summe über dessen Monate der Tätigkeit auf ein Jahr hoch (§ 47 Abs. 2 UStDV). Hat es im Jahr des Belegs begonnen, gibt es kein Vorjahr: Dann gehören die erwarteten Vorauszahlungen des Jahres in die Grundlage von Hand, und Kz 38 ist ihr Durchschnitt über die Monate der Tätigkeit (§ 47 Abs. 3 UStDV, `expected_sondervorauszahlung`).
3. Für jeden Monat des Vorjahres ab dem Beginn der Tätigkeit prüft der Beleg, ob eine abgegebene Voranmeldung ihn abdeckt. Fehlt sie, nennt „Fehlt in der Grundlage“ den Voranmeldungszeitraum, den die Einstellungen für den Monat vorsehen, oder den Monat selbst, wenn die Einstellungen für ihn keinen Voranmeldungszeitraum kennen, etwa weil seine Voranmeldung außerhalb von Steuerbote abgegeben wurde. Ein Monat, für den die Einstellungen keine Voranmeldung vorsehen, fehlt nicht. Mit Dauerfristverlängerung ist die Voranmeldung für Dezember am selben Tag fällig wie die Sondervorauszahlung, siehe [Fristen](#fristen); ist sie noch nicht abgegeben, steht sie hier.
4. Grundlage und Kz 38 rechnet der Kern, Kz 38 in vollen Euro wie unter [Sondervorauszahlung](#sondervorauszahlung) beschrieben.

Ohne abgegebene Voranmeldung des Vorjahres und ohne Grundlage von Hand lehnt Berechnen ab und sagt, was fehlt.

**Grundlage von Hand.** Sie ersetzt die Grundlage aus den Voranmeldungen, sobald eine Begründung dasteht, auch mit 0 €; einen Betrag ohne Begründung lehnt das Speichern ab. Sie ist für das, was die Buchhaltung nicht wissen kann: Voranmeldungen des Vorjahres, die außerhalb von Steuerbote abgegeben wurden, oder die erwarteten Vorauszahlungen nach einem Beginn im laufenden Jahr. Kz 38 folgt ihr bei jedem Speichern. Mit ihr sind fehlende Voranmeldungen kein offener Punkt mehr; die Tabelle und „Fehlt in der Grundlage“ zeigen sie weiter.

**Was das Speichern nimmt.** Frappe hält beim Speichern über die API kein schreibgeschütztes Feld fest. Das Speichern nimmt deshalb nur, was das Formular ändern lässt: Antrag und ersten verlängerten Monat, Kz 10, die Grundlage von Hand mit Begründung, die weiteren Angaben und die Anmerkungen. Die Tabelle der Grundlage, „Fehlt in der Grundlage“, das Gründungsdatum, der Status und die Abgabe bleiben, wie „Berechnen“ und die Abgabe sie gespeichert haben; Grundlage und Kz 38 rechnet das Speichern daraus neu. Bevor der Beleg übermittelt oder eingereicht wird, rechnet Steuerbote Grundlage und Kz 38 noch einmal nach und lehnt ab, wenn sie nicht zum gespeicherten Vordruck passen.

| Status | Bedeutung |
|---|---|
| Entwurf | angelegt und noch nicht berechnet, oder Unternehmen, Jahr, Antrag oder erster verlängerter Monat haben sich geändert; das verwirft eine Berechnung |
| Berechnet | berechnet, aber mit offenen Punkten |
| Bereit | berechnet und ohne offene Punkte |
| Abgegeben | nach einem Senden, das ELSTER angenommen hat, oder mit einem Vermerk der Abgabe eingereicht |

**Offene Punkte** sind fehlende Voranmeldungen des Vorjahres ohne Grundlage von Hand und ein Jahr, dessen Vordruck Steuerbote noch nicht kennt. `layout_for` kennt bisher nur 2026, ein Beleg für 2027 bleibt deshalb „Berechnet“, bis der Kern den Vordruck 2027 kennt. Die Regeln des Vordrucks prüft `Ust1H` bei jedem Speichern: Kz 29 nur mit Kz 10, Kz 500 nur mit Begründung und umgekehrt, die Schlüssel 1 bis 4 und höchstens 180 Zeichen in einer Zeile. Ein Verstoß verhindert das Speichern. Für ein Jahr ohne Vordruck im Kern prüft Steuerbote diese Regeln nicht.

**Fristen.** Die Fälligkeit rechnet `obligation` wie unter [Fristen](#fristen): mit Antrag der Tag, an dem die erste verlängerte Voranmeldung ohne die Verlängerung fällig ist, sonst der 10. Februar. Die Feiertage nimmt der Beleg aus der Standard-Feiertagsliste des Unternehmens, und zwar die Tage, die dort nicht als wöchentlich frei markiert sind; Samstag und Sonntag kennt der Kern selbst.

**Übermitteln.** Unter „ELSTER“ stehen „Prüfen“, „Testsenden“ und „Senden“, sobald der Beleg berechnet ist, mit demselben Dialog für Zertifikatsdatei und Passwort wie an der Voranmeldung. Jeder Vorgang läuft als Hintergrundjob, sperrt den Beleg, bis er endet, und hinterlässt eine ELSTER-Übermittlung mit Nutzdaten, Meldungen und Protokoll; im Simulationsmodus prüft und testsendet die Simulation, Senden gibt es dort nicht. Es gelten die Regeln der Voranmeldung, siehe [Übermittlung an ELSTER](uebermittlung.md):

- Senden nur, wenn der Beleg bereit ist oder seine Anmerkungen begründen, warum er trotzdem abgegeben wird.
- Ein Jahr wird einmal abgegeben: Ist für das Unternehmen und Jahr schon ein Vordruck abgegeben oder über Steuerbote gesendet, mit Annahme durch ELSTER oder unbekanntem Ergebnis, auch wenn er später storniert wurde, geht jeder weitere nur als berichtigte Anmeldung der Sondervorauszahlung (Kz 10). Den Antrag allein kann man nicht berichtigen.
- Ein Senden mit unbekanntem Ergebnis sperrt jedes weitere Senden, bis in Mein ELSTER geklärt ist, ob der Vordruck angekommen ist, und ein System Manager die ELSTER-Übermittlung gelöscht hat. Bis dahin ändern sich am Beleg nur die Anmerkungen, denn das Finanzamt kann ihn haben, wie er gesendet wurde; ist er angekommen, reicht „In Mein ELSTER eingetragen“ ihn ein.
- Ein Jahr, dessen Vordruck oder Schema Steuerbote nicht kennt, lässt sich nicht übermitteln.

Nach einem Senden, das ELSTER angenommen hat, reicht der Hintergrundjob den Beleg ein: Abgegeben über ERiC, am Tag der Antwort, mit dem Transferticket. Scheitert das Einreichen, steht das mit dem Transferticket in der ELSTER-Übermittlung; der Beleg bleibt ein Entwurf, lässt sich nicht noch einmal senden, und „Buchen“ reicht ihn ein, sobald die Ursache behoben ist. Bis dahin ändern sich an ihm nur die Anmerkungen: Speichern mit anderen Werten, Berechnen und Verwerfen lehnt Steuerbote ab, ebenso „Buchen“ mit anderen Werten, denn das Finanzamt hat den Vordruck, wie er gesendet wurde.

**Abgabe vermerken.** Unter „ELSTER“ stehen außerdem „In Mein ELSTER eingetragen“ und „Als außerhalb abgegeben vermerken“ für einen Vordruck, der nicht über Steuerbote zum Finanzamt geht. Beide fragen nach dem Tag der Abgabe und nach dem Transferticket aus dem Protokoll von ELSTER, das freiwillig ist; „Als außerhalb abgegeben vermerken“ verlangt dazu, wie und wann abgegeben wurde. Ein Beleg, der nicht bereit ist, wird nur mit Anmerkungen abgegeben, und der Tag der Abgabe liegt nicht in der Zukunft. Der Vermerk reicht den Beleg ein und legt eine ELSTER-Übermittlung mit dem Vorgang „Außerhalb abgegeben“ an. Einen Vordruck, den ELSTER angenommen hat, vermerkt Steuerbote nicht, und für ein schon abgegebenes Jahr gilt dieselbe Regel wie beim Senden. „Buchen“ allein gibt nichts ab: Das Formular bietet es nur nach einem angenommenen Senden an, dessen Einreichen scheiterte, und das Einreichen lehnt es sonst ab.

Unter „Verknüpfungen“ stehen die ELSTER-Übermittlungen des Belegs.

**Was in die Einstellungen kommt.** Mit dem Einreichen schreibt der Beleg in den Einstellungen Umsatzsteuer-Voranmeldung die Zeile seines Jahres in „Dauerfristverlängerung je Jahr“. Er setzt den Haken „Dauerfristverlängerung“ und bei der Anmeldung der Sondervorauszahlung den Betrag aus Kz 38 als Sondervorauszahlung; fehlt die Zeile, legt er sie an. Die letzte Voranmeldung des Jahres zieht die Sondervorauszahlung dann in Kz 39 ab, wie es `bridge.sondervorauszahlung_values` schon tut, im Dezember oder im IV. Kalendervierteljahr. Der Antrag allein setzt nur den Haken. Die Einstellungen halten die Verlängerung je Jahr fest: Jedes weitere Jahr, in dem sie fortgilt, braucht eine eigene Zeile.

**Berichtigen.** Eine abgegebene Anmeldung der Sondervorauszahlung lässt sich stornieren und mit „Ändern“ als berichtigte Anmeldung (Kz 10) neu anlegen; ohne Kz 10 lehnt das Speichern die Änderung ab. Ebenso lehnt es jeden anderen Vordruck desselben Jahres ohne Kz 10 ab, sobald für das Jahr einer abgegeben wurde, auch wenn er storniert ist und der neue nicht aus ihm geändert, sondern neu angelegt wird. Die Änderung beginnt als Entwurf ohne Berechnung und ohne Vermerk. Stornieren nimmt beim Finanzamt nichts zurück: Die Einstellungen behalten den Betrag, bis die Berichtigung vermerkt ist. Eine Voranmeldung, die die alte Sondervorauszahlung schon abgezogen hat, ändert Steuerbote nicht. Den Antrag auf Dauerfristverlängerung allein lässt Steuerbote nicht stornieren, denn er lässt sich nicht berichtigen: „Eine Berichtigung dieser Fallkonstellation ist nicht möglich.“ (ERiC-Entwicklerhandbuch, Kap. 8.5.1)

**Druckformat „Dauerfristverlängerung“.** A4, schwarz und grau, im Stil des Druckformats der Voranmeldung. Der Kopf nennt Unternehmen, Steuernummer, Steuernummer im ELSTER-Format und Finanzamt, mit Antrag den ersten verlängerten Voranmeldungszeitraum, die Fälligkeit, die Voranmeldung, die die Sondervorauszahlung anrechnet, und Name und Status des Belegs. Bei der Anmeldung der Sondervorauszahlung folgt die Tabelle der abgegebenen Voranmeldungen des Vorjahres mit Kz 83, Kz 39 und ihrer Summe, dazu die fehlenden Voranmeldungszeiträume und die Monate der Tätigkeit. Darunter steht der Vordruck USt 1 H in Reihenfolge und Wortlaut von 2026: Abschnitt I mit dem Antrag, Abschnitt II mit den Zeilen 7 bis 9, Abschnitt III mit den Zeilen 10 und 11 und Zeile 12 mit Kz 500. Danach kommen die Grundlage von Hand mit Begründung, die offenen Punkte, die Anmerkungen und die Abgabe, über ERiC, Mein ELSTER oder einen anderen Weg. Die Fußzeile sagt, dass der Ausdruck keine Abgabe ist.

## In Mein ELSTER eintragen

Ohne Hersteller-ID, oder für ein Jahr, dessen Vordruck Steuerbote noch nicht übermittelt, trägt man den Vordruck in Mein ELSTER von Hand ein. Mein ELSTER führt ihn unter „Umsatzsteuer“ als „Dauerfristverlängerung / Sondervorauszahlung“, je Jahr ein eigenes Formular (ELSTER-Hilfe zu Formularen). Die Schritte folgen dem Vordruck USt 1 H 2026, der Anleitung USt 5 E 2026 und der ELSTER-Hilfe zum Formular. Die ELSTER-Hilfe nennt die Summe der Vorauszahlungen Zeile 7, der Vordruck Zeile 8; die Zeilen hier sind die des Vordrucks.

1. **Berechnen.** Ist der Beleg nicht bereit, in den Anmerkungen festhalten, warum er trotzdem so abgegeben wird. Der Ausdruck „Dauerfristverlängerung“ dient als Vorlage.
2. **Kopf.** In Mein ELSTER das Formular für das Jahr des Belegs öffnen. Zeile 1 nennt die Steuernummer, Zeile 2 die Wirtschafts-Identifikationsnummer, die nur eingetragen wird, „wenn diese Ihnen bereits bekannt ist“ (USt 5 E), Zeile 3 das Finanzamt und die Zeilen 4 bis 6 das Unternehmen.
3. **Abschnitt I, Antrag auf Dauerfristverlängerung,** nur im Jahr des Antrags: „Dieser Abschnitt ist gegenstandslos, wenn Dauerfristverlängerung bereits gewährt worden ist.“ Wer vierteljährlich abgibt, füllt nur ihn aus: „Eine Sondervorauszahlung ist nicht zu berechnen und anzumelden.“ (USt 1 H)
4. **Abschnitt II, nur bei monatlicher Abgabe.** Zeile 7 „Berichtigte Anmeldung“ (Kz 10) nur bei einer Berichtigung. In Zeile 8, die „Summe der verbleibenden Umsatzsteuer-Vorauszahlungen zuzüglich der zu berücksichtigenden Sondervorauszahlung“ des Vorjahres, gehört „Grundlage (Zeile 8)“ des Belegs, in Zeile 9, „Davon 1/11 = Sondervorauszahlung“ (Kz 38), „Sondervorauszahlung (Kz 38)“ in vollen Euro. „Ergibt sich bei der Berechnung der Sondervorauszahlung in Zeile 8 ein Überschuss zu Ihren Gunsten, ist die Sondervorauszahlung in Zeile 9 mit 0 € einzutragen.“ (USt 5 E)
5. **Abschnitt III, Sonstige Angaben.** Zeile 10, Kz 29: „Verrechnung des Erstattungsbetrags erwünscht / Erstattungsbetrag ist abgetreten“; die Verrechnungswünsche gehen nach der ELSTER-Hilfe mit dem Formular „Sonstige Nachricht an das Finanzamt“ an das Finanzamt. Zeile 11, Kz 26, wenn das SEPA-Lastschriftmandat für die Sondervorauszahlung dieses Jahres ausnahmsweise nicht verwendet werden soll: „Ein ggf. verbleibender Restbetrag ist gesondert zu entrichten.“ (USt 1 H) In Mein ELSTER sind beides Häkchen.
6. **Zeile 12, Kz 500,** nur für einen der dort genannten Sachverhalte, mit der Begründung aus dem Beleg. In Mein ELSTER gehören dazu ein Häkchen und ein Freitextfeld; reicht der Platz nicht, nennt die ELSTER-Hilfe eine „Sonstige Nachricht an das Finanzamt“ mit dem Betreff „Ergänzende Angaben zur Steueranmeldung“.
7. **Beginn im laufenden Jahr.** Die Anleitung USt 5 E bittet um „ein gesondertes Blatt mit kurzer Erläuterung der Berechnung“, die ELSTER-Hilfe dafür um eine „Sonstige Nachricht an das Finanzamt“.
8. **Absenden** und das Transferticket aus dem Protokoll notieren. Danach am Beleg „In Mein ELSTER eingetragen“ mit dem Tag der Abgabe vermerken. Die Sondervorauszahlung ist bis zur Fälligkeit des Belegs zu entrichten, im Jahr des Antrags „gleichzeitig“ mit ihm (§ 48 Abs. 1 Satz 5 und Abs. 2 UStDV).

## Annahmen und offene Punkte

1. **Volle Euro in Kz 38.** Steuerbote lässt die Cent des Elftels weg. Verordnung, Anleitung und Jahresdokumentation sagen nur, dass Kz 38 volle Euro sind. Zu bestätigen bei der ELSTER-Hotline.
2. **Monate beim Beginn im laufenden Jahr.** Für das Vorjahr zählt § 47 Abs. 2 UStDV einen angefangenen Monat voll. Für das Jahr des Beginns sagen weder § 47 Abs. 3 UStDV noch die Anleitung, wie die Monate zählen; Steuerbote zählt ebenso.
3. **Feiertage.** Steuerbote kennt die Feiertage der Bundesländer nicht. Der Beleg nimmt die Tage der Standard-Feiertagsliste des Unternehmens, die nicht als wöchentlich frei markiert sind. Stehen dort Tage, die keine gesetzlichen Feiertage sind, etwa Betriebsferien, verschiebt er die Frist zu Unrecht; die Liste ist deshalb mit den gesetzlichen Feiertagen abzugleichen. Die Fälligkeit der Voranmeldung berücksichtigt noch keine Feiertage.
4. **Vordruck 2027.** Der Kern kennt den Vordruck USt 1 H bisher nur für 2026. Ein Beleg für 2027 bleibt „Berechnet“, lässt sich nicht übermitteln und wird mit Anmerkungen von Hand abgegeben, bis Layout und Schema 2027 in Steuerbote stehen; seine Angaben zu Kz 10, 26, 29 und 500 prüft Steuerbote bis dahin nicht.
5. **Verlängerung je Jahr.** Die Einstellungen kennen die Dauerfristverlängerung nur für ein ganzes Jahr. Wer sie ab einem späteren Monat beantragt, bekommt mit dem Vermerk der Abgabe auch für die Voranmeldungen der Monate davor die verlängerte Frist angezeigt.
6. **Beginn der Tätigkeit.** § 47 UStDV stellt auf die Tätigkeit ab, Steuerbote auf das Gründungsdatum des Unternehmens. Begann die Tätigkeit an einem anderen Tag, gehört die Grundlage von Hand mit Begründung in den Beleg.
7. **Antrag ohne eigenes Feld.** Dass der Kontext `Umsatzsteuersondervorauszahlung` im Jahr des Antrags zugleich den Antrag auf Dauerfristverlängerung stellt, folgert Steuerbote aus Jahresdokumentation, Entwicklerhandbuch und § 48 Abs. 1 Satz 4 UStDV, siehe [Kein Feld für den Antrag](#vordruck-ust-1-h-in-elster). Eine Quelle, die es ausdrücklich sagt, fehlt; zu bestätigen bei der ersten echten Übermittlung oder bei der ELSTER-Hotline.
8. **Echte Übermittlung.** Gegen das Schema und die Beispiele der ERiC-Dokumentation ist das XML geprüft, gegen ERiC selbst noch nicht: Das zeigt erst ein Lauf mit Hersteller-ID und ELSTER-Testzertifikat.
