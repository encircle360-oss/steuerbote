# Dauerfristverlängerung und Sondervorauszahlung

Mit der Dauerfristverlängerung gibt ein Unternehmen jede Umsatzsteuer-Voranmeldung einen Monat später ab und zahlt die Vorauszahlung einen Monat später. Wer monatlich abgibt, bekommt sie nur gegen eine Sondervorauszahlung, die jedes Jahr fällig wird und in der letzten Voranmeldung des Jahres über Kz 39 angerechnet wird. Diese Seite beschreibt die Regeln mit ihren Quellen und was der Rechenkern unter `steuerbote/dauerfrist` daraus macht. Sie ersetzt keine Steuerberatung.

## Quellen

- **§ 18 Abs. 1 und 6 UStG:** <https://www.gesetze-im-internet.de/ustg_1980/__18.html>. Absatz 6 erlaubt die Verordnung: „Zur Vermeidung von Härten kann das Bundesministerium der Finanzen mit Zustimmung des Bundesrates durch Rechtsverordnung die Fristen für die Voranmeldungen und Vorauszahlungen um einen Monat verlängern und das Verfahren näher bestimmen. Dabei kann angeordnet werden, dass der Unternehmer eine Sondervorauszahlung auf die Steuer für das Kalenderjahr zu entrichten hat.“
- **§§ 46 bis 48 UStDV:** <https://www.gesetze-im-internet.de/ustdv_1980/__46.html>, <https://www.gesetze-im-internet.de/ustdv_1980/__47.html>, <https://www.gesetze-im-internet.de/ustdv_1980/__48.html>
- **§ 108 Abs. 3 AO:** <https://www.gesetze-im-internet.de/ao_1977/__108.html>
- **BMF-Schreiben vom 29. Dezember 2025**, GZ III C 3 - S 7344/00039/007/036, mit den Vordrucken USt 1 H 2026 (Antrag auf Dauerfristverlängerung, Anmeldung der Sondervorauszahlung), USt 1 E 2026 (Anleitung zur Umsatzsteuer-Voranmeldung) und USt 5 E 2026 (Anleitung zum Antrag auf Dauerfristverlängerung/zur Anmeldung der Sondervorauszahlung): <https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/2025-12-29-vordruckmuster-USt-voranmeldung-2026.pdf?__blob=publicationFile>, SHA-256 `82e7d63a0faec542bb184acb438eaf4ce90a2d7db067bb47f92ae13b4b17613d`. Ohne `?__blob=publicationFile` liefert die Adresse eine HTML-Seite statt des PDF.
- **ERiC-Dokumentation 44.3.6.0:** <https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Dokumentation.zip>, darin `UStVA-2026.xsd`, die Jahresdokumentation `Jahresdokumentation_UStVA_2026.ods` (Blätter „Anmeldungssteuern - Felder“, „Anmeldungssteuern - Regeln“ und „Allg. Information“), die Beispiele `UStVA_Df_2026.xml` und `UStVA_SoVZ_2026.xml` und das ERiC-Entwicklerhandbuch, Kap. 8.5.1.
- **ELSTER-Hilfe „Benutzeranleitung zum Hochladen von Formulardaten“:** <https://www.elster.de/eportal/helpGlobal?themaGlobal=ustva_upload>

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

ELSTER kennt den Vordruck USt 1 H als zwei Kontexte der Datenart UStVA, neben der Umsatzsteuer-Voranmeldung. Eine Datei enthält genau einen der drei (110085099). Für den Antrag ohne Sondervorauszahlung sagt das ERiC-Entwicklerhandbuch: „Soll eine Dauerfristverlängerung ohne Sondervorauszahlung abgegeben werden, ist nur Kz 09 zu füllen. Eine Berichtigung dieser Fallkonstellation ist nicht möglich.“ Das Schema für 2026 nimmt dort zusätzlich Kz 500 mit Begründung an. [`form.py`](../steuerbote/dauerfrist/form.py) hält Felder und Regeln je Jahr als Daten (`LAYOUTS`), bisher für 2026, und `Ust1H` einen Vordruck, wie er abgegeben wird. Die Tests vergleichen die Daten mit Schema, Jahresdokumentation und Beispielen der ERiC-Dokumentation. Die Jahresdokumentation 2025 hatte statt Kz 500 noch Kz 23; ein neues Jahr bekommt deshalb ein eigenes Layout.

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

Die Nummern in Klammern sind die Fehlercodes der Regeln aus der Jahresdokumentation. `Ust1H` prüft, was der Vordruck selbst enthält: Kz 38 im Kontext der Sondervorauszahlung (110085143), Kz 29 nur mit Kz 10 (11085150), Kz 500 nur mit Begründung und umgekehrt (11085137), die Formate der Felder und dass der Antrag allein weder Kz 10, 26, 29 noch 38 trägt. `Ust1H.hints` nennt die Hinweise zu Kz 26 und Kz 500. Steuernummer, Wirtschafts-Identifikationsnummer und Kz 09 kommen vom Unternehmen und aus den ERiC-Einstellungen; sie prüft der Schreiber des XML, wenn es ihn gibt, wie heute bei der Voranmeldung, ebenso, dass Kz 09 nur die Hersteller-ID enthält (110085046).

## Was Steuerbote heute rechnet und was später kommt

**Heute** gibt es den Rechenkern unter `steuerbote/dauerfrist`, reines Python ohne Frappe mit vollständiger Testabdeckung: Grundlage und Sondervorauszahlung, Fristen, den Zeitraum der Anrechnung und das Modell des Vordrucks. Die Frappe-Schicht nutzt ihn noch nicht. Die Sondervorauszahlung steht weiter von Hand in den Einstellungen („Dauerfristverlängerung je Jahr“), und daraus kommt Kz 39.

**Später** kommen:

- **ein Beleg für den Vordruck USt 1 H** in der Frappe-Schicht, der Kz 38 aus den abgegebenen Voranmeldungen des Vorjahres berechnet (Kz 83 und Kz 39 jeder zuletzt abgegebenen Meldung je Zeitraum) und mit der Abgabe die Sondervorauszahlung seines Jahres in die Einstellungen schreibt. Dann kommt Kz 39 aus dem abgegebenen Vordruck statt aus einer eigenen Eingabe.
- **das XML über ERiC**, sobald die ERiC-Dokumentation das Schema für 2027 enthält und Steuerbote eine Hersteller-ID hat: ERiC verlangt Kz 09 in beiden Kontexten (110085045). Die ERiC-Dokumentation 44.3.6.0 kennt bisher nur 2026, die Sondervorauszahlung 2027 ist am 10. Februar 2027 fällig.

**Bis dahin von Hand in Mein ELSTER.** Eine Datei zum Hochladen gibt es für den Vordruck nicht. Die ELSTER-Hilfe sagt: „Die Funktion zum Hochladen von Formulardaten (XML-Datei) steht Ihnen für alle angebotenen Jahresversionen der Umsatzsteuer-Voranmeldung (UStVA) und der Mitteilung nach § 146a Abs. 4 AO zur Verfügung.“ Den Antrag auf Dauerfristverlängerung nennt sie nicht. Den Betrag aus Kz 38 tippst du deshalb in Mein ELSTER in das Formular für den Antrag auf Dauerfristverlängerung und die Anmeldung der Sondervorauszahlung und trägst ihn danach in die Einstellungen ein.

## Annahmen und offene Punkte

1. **Volle Euro in Kz 38.** Steuerbote lässt die Cent des Elftels weg. Verordnung, Anleitung und Jahresdokumentation sagen nur, dass Kz 38 volle Euro sind. Zu bestätigen bei der ELSTER-Hotline.
2. **Monate beim Beginn im laufenden Jahr.** Für das Vorjahr zählt § 47 Abs. 2 UStDV einen angefangenen Monat voll. Für das Jahr des Beginns sagen weder § 47 Abs. 3 UStDV noch die Anleitung, wie die Monate zählen; Steuerbote zählt ebenso.
3. **Feiertage.** Wie bei der Voranmeldung kennt Steuerbote die Feiertage der Bundesländer noch nicht; der Aufrufer übergibt sie.
