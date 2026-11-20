# Zusammenfassende Meldung

Diese Seite ist die fachliche Grundlage des Kerns unter `steuerbote/zm`: Meldezeiträume und Fristen, Abgaberhythmus, Meldezeilen aus dem Hauptbuch, USt-IdNrn., Sperren und Übersteuern, Abgleich mit der Voranmeldung, Berichtigung und die CSV-Datei für Mein ELSTER. Der Kern ist reines Python ohne Frappe-Import. Wie der Beleg „Zusammenfassende Meldung“ in ERPNext mit ihm arbeitet, steht unter [Die Zusammenfassende Meldung in ERPNext](#die-zusammenfassende-meldung-in-erpnext); die Übermittlung über ERiC folgt mit der Hersteller-ID, siehe [Roadmap](roadmap.md). Die Seite ersetzt keine Steuerberatung. Die Quellen stehen am Ende als [Q1] bis [Q16], alle am 20. November 2026 gelesen.

## Was die ZM ist

Wer innergemeinschaftliche Warenlieferungen, Lieferungen im Sinne des § 25b Absatz 2 UStG (Dreiecksgeschäfte) oder sonstige Leistungen nach § 3a Absatz 2 UStG an Unternehmer in anderen Mitgliedstaaten ausführt, meldet sie dem Bundeszentralamt für Steuern (BZSt): je Erwerber dessen USt-IdNr. und „die Summe der Bemessungsgrundlagen“ (§ 18a Absatz 7 UStG [Q1]). Die ZM unterscheidet drei Arten, im Datensatz „Art der Leistung“ [Q11, Q13]:

| Art | Umsatz | Kennzahl der Voranmeldung |
|---|---|---|
| L | innergemeinschaftliche Lieferung (§ 18a Absatz 6 Nummer 1 und 2 UStG), auch das Verbringen nach § 6a Absatz 2 UStG | Kz 41, Zeile 19 |
| D | Lieferung des ersten Abnehmers im innergemeinschaftlichen Dreiecksgeschäft (§ 25b Absatz 2 UStG) | Kz 42, Zeile 33 |
| S | sonstige Leistung nach § 3a Absatz 2 UStG, für die der Leistungsempfänger die Steuer in seinem Mitgliedstaat schuldet | Kz 21, Zeile 35 |

Dieselben Umsätze stehen in der Voranmeldung (§ 18b UStG [Q2], Vordruck USt 1 A 2026 [Q4]); zu den Zeilen 19 und 35 sagt die Anleitung: „übermitteln Sie bitte Zusammenfassende Meldungen an das Bundeszentralamt für Steuern“. `lines.py` ordnet die Kennzahlen so den Arten zu (`KENNZAHL_ART`).

Die ZM entscheidet über die Steuerbefreiung: Die innergemeinschaftliche Lieferung ist nicht steuerfrei, „wenn der Unternehmer seiner Pflicht zur Abgabe der Zusammenfassenden Meldung (§ 18a) nicht nachgekommen ist oder soweit er diese im Hinblick auf die jeweilige Lieferung unrichtig oder unvollständig abgegeben hat“ (§ 4 Nummer 1 Buchstabe b UStG [Q3]).

## Meldezeiträume und Fristen

[`period.py`](../steuerbote/zm/period.py) beschreibt die Meldezeiträume (`ReportingPeriod`), ihre Codes und Fristen.

| Meldezeitraum | Wann | Code `quart` |
|---|---|---|
| Kalendermonat | Grundfall für L und D (§ 18a Absatz 1 Satz 1 UStG) | 21 bis 32 |
| Kalendervierteljahr | L und D bleiben im laufenden und in den vier vorangegangenen Quartalen bei höchstens 50.000 € (Absatz 1 Satz 2); S grundsätzlich (Absatz 2 Satz 1) | 1 bis 4 |
| erste zwei Monate eines Quartals | die Schwelle wird im zweiten Monat überschritten (Absatz 1 Satz 3) | 11 bis 14 |
| Kalenderjahr | von den Voranmeldungen befreit und wenig EU-Umsatz (Absatz 9) | 5 |

Die Codes sind die des Feldes `quart` der ERiC-Datenart ZMDO [Q11]: 21 bis 32 für Januar bis Dezember, 11 bis 14 für Januar und Februar, April und Mai, Juli und August, Oktober und November, 1 bis 4 für die Quartale und 5 für das Jahr. Wird die Schwelle im dritten Monat eines Quartals überschritten, umfasst die erste monatliche ZM das ganze Quartal und trägt dessen Code.

**Frist.** Die ZM ist „bis zum 25. Tag nach Ablauf“ des Meldezeitraums zu übermitteln (§ 18a Absatz 1 Satz 1 UStG, BZSt „Fristen“ [Q6]). „Die Regelungen über die Dauerfristverlängerung für die Abgabe der Umsatzsteuer-Voranmeldungen gelten nicht für die ZM“ [Q6], `deadline()` kennt deshalb keine. Für die ZM gelten die Vorschriften der Abgabenordnung für Steuererklärungen (§ 18a Absatz 11 UStG), also auch § 108 Absatz 3 AO [Q5]: Fällt die Frist auf einen Samstag, Sonntag oder gesetzlichen Feiertag, endet sie am nächsten Werktag. Diese Regel teilt sich `deadline()` mit der Voranmeldung (`next_working_day` in `ustva/period.py`). Feiertage unterscheiden sich je Bundesland, deshalb übergibt sie der Aufrufer.

Beispiele aus den Tests: Januar 2026 ist am 25. Februar 2026 fällig. April und Mai 2026 sind am 25. Juni 2026 fällig, wie im Beispiel des BZSt [Q6]. Das I. Kalendervierteljahr 2026 ist am 27. April 2026 fällig, weil der 25. April ein Samstag ist. April 2026 ist am 25. Mai 2026 fällig; übergibt der Aufrufer den Pfingstmontag als Feiertag, am 26. Mai. November 2026 ist mit den Weihnachtsfeiertagen am 28. Dezember 2026 fällig. Das IV. Kalendervierteljahr 2026 ist am 25. Januar 2027 fällig.

## Abgaberhythmus

[`rhythm.py`](../steuerbote/zm/rhythm.py) leitet aus Regeln des Unternehmens ab, für welchen Meldezeitraum es die Zeilen eines Monats meldet. Eine Regel (`Rule`) gilt ab Jahr und Monat bis zur nächsten Regel: monatlich, vierteljährlich oder jährlich, bei monatlich wahlweise mit „sonstige Leistungen monatlich“. Vor der ersten Regel gibt es keinen Meldezeitraum; Steuerbote rät ihn nicht.

- **Vierteljährlich** beginnt mit einem Quartal, also im Monat 1, 4, 7 oder 10.
- **Jährlich** beginnt im Januar und gilt für ganze Kalenderjahre (§ 18a Absatz 9 UStG: „bis zum 25. Tag nach Ablauf jedes Kalenderjahres“). Ob die Voraussetzungen erfüllt sind, also Befreiung von den Voranmeldungen, höchstens 200.000 € Umsatz und höchstens 15.000 € innergemeinschaftliche Umsätze, prüft Steuerbote nicht; das Hauptbuch zeigt nur die Schwelle unten.
- **Monatlich** kann in jedem Monat beginnen. Beginnt eine monatliche Regel mitten in einem Quartal nach einer vierteljährlichen, umfasst ihre erste ZM das Quartal bis zu ihrem Monat. Das ist der Fall des § 18a Absatz 1 Satz 3 UStG: Übersteigen L und D im Laufe eines Quartals 50.000 €, ist die ZM „bis zum 25. Tag nach Ablauf des Kalendermonats, in dem dieser Betrag überschritten wird, [...] für diesen Kalendermonat und die bereits abgelaufenen Kalendermonate dieses Kalendervierteljahres“ zu übermitteln. Beispiel des BZSt [Q6]: vierteljährlich bisher, im Mai 57.000 €, also eine ZM für April und Mai bis zum 25. Juni und ab Juni monatlich. Die Anleitung zur ZM erlaubt stattdessen auch je eine ZM für jeden abgelaufenen Monat [Q10, III.1]; Steuerbote bildet die gemeinsame.
- **Sonstige Leistungen** (S) sind vierteljährlich zu melden (§ 18a Absatz 2 Satz 1 UStG). Wer monatlich abgibt, meldet sie „in der Zusammenfassenden Meldung für den letzten Monat des Kalendervierteljahres“ (Absatz 2 Satz 2) oder nach einer Anzeige an das BZSt in der ZM des jeweiligen Monats (Absatz 3). Welche Variante gilt, bestimmt die Regel des letzten Monats im Quartal, damit alle sonstigen Leistungen eines Quartals derselben Regel folgen.

`coverage()` nennt für einen Meldezeitraum die Monate, deren Lieferungen (L und D) und deren sonstige Leistungen (S) er meldet, und lehnt einen Meldezeitraum ab, den die Regeln nicht ergeben. Die monatliche ZM für Juni enthält so die Lieferungen des Juni und, ohne „sonstige Leistungen monatlich“, die sonstigen Leistungen von April bis Juni.

**Schwelle.** `threshold_findings()` prüft die Regeln gegen das Hauptbuch: Kz 41 und Kz 42 zusammen, je Monat und genau in Cent, für den Meldezeitraum und die vier Quartale davor (`threshold_window()`). „Mehr als 50 000 Euro“ heißt: 50.000,00 € sind nicht mehr. Ein Fehler (`ZM-SCHWELLE`) entsteht,

- bei einer vierteljährlichen Regel, wenn das Quartal die Schwelle vor seinem letzten Monat überschreitet; im letzten Monat ergibt die erste monatliche ZM dieselben Monate und dieselbe Frist wie das Quartal;
- bei einer jährlichen Regel, sobald ein Quartal die Schwelle überschreitet, denn dann ist die ZM nach § 18a Absatz 1 Satz 2 und 3 UStG ab dem Monat der Überschreitung monatlich abzugeben; die engeren Grenzen der jährlichen ZM selbst, etwa 15.000 € im Jahr nach Absatz 9 Nummer 2, prüft Steuerbote nicht, siehe oben;
- bei beiden, wenn eines der vier vorangegangenen Quartale mehr als 50.000 € hatte (§ 18a Absatz 1 Satz 2 UStG).

Ein Hinweis des BZSt: „Der Wechsel zur monatlichen Abgabe erfolgt automatisch. Das Unternehmen hat auf seine Abgabepflichten zu achten; es erfolgt keine Mitteilung des BZSt über die Änderung des Meldezeitraums.“ [Q9]

**Anzeige und Widerruf.** Wer monatlich abgibt, obwohl er vierteljährlich dürfte, zeigt das in der ersten monatlichen ZM an (§ 18a Absatz 1 Satz 4 UStG; Anleitung zur ZM, III.1 und IV.4 [Q10]); der Widerruf steht in einer ZM für ein Quartal oder für den dritten Monat eines Quartals (ZMDO-Regeln 170015008, 170015012 und 170015013 [Q11]). `check_notices()` lehnt ab, was diese Regeln nicht zulassen. Beides sind Felder im Kopf des Formulars, nicht in der CSV-Datei; sie werden in Mein ELSTER gesetzt.

## Meldezeilen aus dem Hauptbuch

[`lines.py`](../steuerbote/zm/lines.py) bildet die Meldezeilen (`build()`) aus dem, was jeder Beleg zu Kz 41, 42 und 21 beiträgt (`VoucherAmount`): Belegschlüssel `Belegtyp:Belegnr.`, Kennzahl, genauer Betrag in Cent, Kunde, dessen USt-IdNr. und bei Dreiecksgeschäften das Land, in dem die Lieferung endet.

**Warum das Hauptbuch und nicht die Rechnungen.** § 18a Absatz 7 Satz 2 UStG wendet § 17 UStG auf die ZM an. Skonti, Rabatte, Boni und uneinbringlich gewordene Forderungen ändern die Zeile des Meldezeitraums, „in dem die Änderung eingetreten ist“, verrechnet mit den Lieferungen dieses Zeitraums [Q8, Rabatte; Q10, IV.10]. Beispiel des BZSt: 80.000 € Lieferungen und 5.000 € Preisnachlass auf eine frühere Lieferung ergeben 75.000 €. Rechnungen allein enthalten solche Änderungen nicht, wenn sie als Zahlung oder Journalbuchung gebucht sind. Steuerbote nimmt deshalb die Belege hinter den Kennzahlen aus dem Hauptbuch, wie für die Voranmeldung; das hat der Maintainer so entschieden. Ergibt die Verrechnung einen negativen Betrag, steht er mit Minuszeichen in der Zeile [Q10, IV.10].

- **Eine Zeile je USt-IdNr. und Art.** Die Bemessungsgrundlagen eines Erwerbers „sind summiert für die jeweilige Umsatzart [...] in je einer Zeile gesondert einzutragen“, höchstens drei Zeilen je Erwerber [Q10, IV.8 und IV.11]; ZMDO lehnt eine zweite Zeile ab, „die bis auf den Betrag identisch“ ist (170045003 bis 170045005). Schreibweisen derselben Nummer („ATU 123 456 78“, „atu12345678“) ergeben eine Zeile.
- **Reihenfolge:** nach USt-IdNr., je Nummer L, D, S wie die Kennzahlen im Vordruck.
- **Keine Nullzeilen.** „Sog. „Nullmeldungen“ sind nicht abzugeben“ [Q10, III.1]; ZMDO verlangt mindestens eine Zeile und lehnt eine erste ZM ab, deren einzige Zeile 0 € meldet (170045002, 170045001). Eine Zeile, die 0 € meldet, entfällt.
- **Zeitliche Zuordnung:** Die Frappe-Schicht wählt die Belege nach Buchungsdatum aus (Entscheidung des Maintainers), für die Monate, die `coverage()` nennt. § 18a Absatz 8 UStG verlangt für L den Meldezeitraum, in dem die Rechnung ausgestellt wird, spätestens den, in dem der Monat nach der Lieferung endet, für S und D den Meldezeitraum der Ausführung.

## Rundung

Die ZM meldet ganze Euro: Feld `betrag` in ZMDO als „GeldBetragOhneCent“ [Q11], in der CSV-Datei „eine ganze Zahl“ [Q13]. Wie die Cent wegfallen, sagt keine der Quellen. Steuerbote schneidet die Cent je Zeile ab, Richtung null, wie bei den Bemessungsgrundlagen der Voranmeldung (`to_full_euros` in `ustva/rounding.py`): 1.000,99 € werden 1.000 €, -1.000,99 € werden -1.000 €. Das ist eine Annahme und eine Entscheidung des Maintainers, keine belegte Regel.

## USt-IdNr.

[`ustid.py`](../steuerbote/zm/ustid.py) legt fest, welche USt-IdNr. die ZM nimmt. Form und Länderkennzeichen sind die Regel der Bestätigung nach § 18e UStG in [`vatid/ustid.py`](../steuerbote/vatid/ustid.py), damit Steuerbote genau die Nummer bestätigen lässt, die die ZM meldet. Die ZM ergänzt nur, dass XI nicht für sonstige Leistungen gilt; für die Bestätigung gilt XI ohne Einschränkung.

- **Form:** Länderkennzeichen aus zwei Großbuchstaben, danach Buchstaben, Ziffern, + und *, „mindestens 7 Zeichen“, höchstens 14 (AN 7,14) [Q13]; ZMDO-Feld `knre_UstIdNr_Erwerber` ebenso [Q11]. `normalize()` behält von einem Wert aus ERPNext Buchstaben, Ziffern, + und *, schreibt Buchstaben groß und nimmt das Ergebnis, wenn es diese Form hat.
- **Länderkennzeichen:** die 26 anderen Mitgliedstaaten nach der Liste der Hilfe [Q13]: AT, BE, BG, CY, CZ, DK, EE, EL, ES, FI, FR, HR, HU, IE, IT, LT, LU, LV, MT, NL, PL, PT, RO, SE, SI, SK. Griechenland heißt EL, nicht GR.
- **XI** (Nordirland) gilt nur für Lieferungen (L und D): „Nordirische UStIDs (Präfix XI) dürfen nicht für sonstige Leistungen verwendet werden“ (ZMDO-Regel 170045021 [Q11]). Grund ist Artikel 8 des Protokolls zu Irland/Nordirland zum Austrittsabkommen: „The provisions of Union law listed in Annex 3 to this Protocol concerning goods shall apply to and in the United Kingdom in respect of Northern Ireland.“ [Q12] Für Waren gelten in Nordirland also die Regeln des innergemeinschaftlichen Handels, Dienstleistungen nach Nordirland sind Drittlandsumsätze und gehören nicht in die ZM [Q9, Fragen zum Brexit].
- **Abgelehnt:** DE, „Es dürfen keine inländischen UstId-Nummern angegeben werden“ (170045014); GB, „nur für die Meldezeiträume bis zum Ablauf des Übergangszeitraumes am 31.12.2020“ [Q9] (170045017).
- **Rumänische Nummern** mit zwei bis vier Ziffern sind mit führenden Nullen auf fünf Ziffern aufzufüllen, so der Fehlertext des ZMDO-Feldes [Q11]. Steuerbote ergänzt nichts: Die Nummer gehört so in den Kunden.
- **Gültigkeit:** Ob eine Nummer erteilt ist, klärt die Bestätigung nach § 18e UStG, siehe [Prüfung ausländischer USt-IdNrn.](ust-idnr-pruefung.md). Ihr Ergebnis (bestätigt, ungültig, nicht bestätigt) ist eine Eingabe von `build()`; eine Nummer ohne Ergebnis lässt `build()` durch. Der Beleg in ERPNext übergibt für jede Nummer ein Ergebnis, eine nie bestätigte Nummer als nicht bestätigt, siehe [Berechnen](#berechnen).

## Sperren und Übersteuern

Jeder Befund ist ein Satz mit Beleg und Kunde, wo es sie gibt (`findings.py`). Fehler halten die ZM von „Bereit“ ab, Hinweise ändern nichts.

| Code | Wirkung | Bedeutung | Grundlage |
|---|---|---|---|
| `ZM-OHNE-KUNDE` | Fehler | Ein Beleg geht in Kz 41, 42 oder 21 ein, nennt aber keinen Kunden. | § 18a Absatz 7 UStG |
| `ZM-OHNE-USTID` | Fehler | Der Beleg nennt keine USt-IdNr. des Kunden, etwa weil die Rechnung ohne sie ausgestellt wurde, auch wenn der Kunde inzwischen eine hat. | § 18a Absatz 7 UStG |
| `ZM-USTID-FORMAT` | Fehler | Die USt-IdNr. hat nicht die Form der ZM, ist deutsch, britisch, ohne gültiges Länderkennzeichen oder XI bei einer sonstigen Leistung. | [Q13], [Q11], [Q9] |
| `ZM-USTID-UNGUELTIG` | Fehler | Die Bestätigung hat die Nummer als ungültig gemeldet. | § 6a Absatz 1 Satz 1 Nummer 4 UStG [Q3]; Entscheidung des Maintainers [Q16] |
| `ZM-USTID-UNBESTAETIGT` | Fehler | Die Nummer ist nicht bestätigt. | Entscheidung des Maintainers [Q16] |
| `ZM-DREIECK-LAND` | Fehler | Bei einem Dreiecksgeschäft stammt die USt-IdNr. nicht aus dem Land, in dem die Lieferung endet, oder der Beleg nennt kein Land. | § 18a Absatz 7 Satz 1 Nummer 4 Buchstabe a UStG |
| `ZM-SCHWELLE` | Fehler | Die Regeln geben eine vierteljährliche oder jährliche ZM, obwohl L und D mehr als 50.000 € im Quartal ergeben. | § 18a Absatz 1 UStG |
| `ZM-ABGLEICH-HAUPTBUCH` | Fehler | Ein Beleg steht mit anderem Betrag im Hauptbuch als in den Zeilen. | siehe Abgleich |
| `ZM-ABGLEICH-VORANMELDUNG` | Hinweis | Die Meldezeilen weichen weiter von den abgegebenen Voranmeldungen ab, als die Rundung erklärt. | siehe Abgleich |
| `ZM-ABWEICHUNG-VORPERIODE` | Hinweis | Eine Zeile ist im Vorperiodenvergleich auffällig. | siehe Vorperiodenvergleich |

**Übersteuern je Zeile.** Eine Korrektur (`Override`) mit Betrag in ganzen Euro und Begründung ersetzt den Betrag einer Zeile und hebt ihre Sperren auf, etwa wenn eine Nummer am Liefertag bestätigt war und der Nachweis vorliegt. Eine Zeile ohne USt-IdNr., die die ZM nimmt, kann nicht gemeldet werden; ihre Korrektur kann sie nur mit 0 herausnehmen. Eine Korrektur für eine Zeile ohne Belege ist eine Zeile für sich. So entsteht etwa die Zeile für ein Verbringen (§ 6a Absatz 2 UStG), das unter der eigenen USt-IdNr. des Unternehmens im anderen Mitgliedstaat zu melden ist (§ 18a Absatz 7 Satz 1 Nummer 2 UStG): die Zeile mit der eigenen ausländischen Nummer und dem Betrag, dazu die Korrektur 0 für die Zeile des Belegs ohne Kunden. `ZM-SCHWELLE` und `ZM-ABGLEICH-HAUPTBUCH` lassen sich nicht übersteuern; dort sind die Regeln oder die Daten zu berichtigen.

## Abgleich mit der Voranmeldung

ZM und Voranmeldung melden dieselben Umsätze, mit denselben Zeiträumen (§ 18a Absatz 8, § 18b Satz 2 und 3 UStG) und § 17 UStG für beide (§ 18a Absatz 7 Satz 2, § 18b Satz 4 UStG). Das BZSt gleicht ab: „Nach Eingang der ZM beim BZSt erfolgt ein Abgleich der gemeldeten innergemeinschaftlichen Umsatzarten mit den Angaben in den Umsatzsteuer-Voranmeldungen und -Jahreserklärungen.“ [Q8] [`reconciliation.py`](../steuerbote/zm/reconciliation.py) prüft deshalb ΣL = Kz 41, ΣD = Kz 42 und ΣS = Kz 21 über dieselben Monate, die Lieferungsmonate für Kz 41 und 42, die Leistungsmonate für Kz 21:

1. **Hauptbuch, Beleg für Beleg.** Die genauen Beträge der Belege in den Zeilen gegen das, was das Hauptbuch jeder Kennzahl gibt; die Beiträge (`Contribution`) des Berichts „UStVA Kennzahlen“ passen dafür unverändert. Fehlt ein Beleg auf einer Seite oder hat er einen anderen Betrag, nennt ein Fehler den Beleg (`ZM-ABGLEICH-HAUPTBUCH`).
2. **Abgegebene Voranmeldungen.** Die Meldezeilen je Art gegen die Kennzahl der für diese Monate abgegebenen Voranmeldungen. Jede Zeile und jede Voranmeldung schneidet weniger als einen Euro ab. Weichen beide um so viele Euro ab, wie es Zeilen dieser Art und Voranmeldungen gibt, oder um mehr, ist das keine Rundung, sondern etwa eine Korrektur; das gibt einen Hinweis (`ZM-ABGLEICH-VORANMELDUNG`).

## Vorperiodenvergleich

[`comparison.py`](../steuerbote/zm/comparison.py) stellt jede Meldezeile neben die des vorigen Meldezeitraums derselben Art (`ReportingPeriod.previous()`). Dessen Zeilen kommen ebenso aus dem Hauptbuch, nicht aus einer früheren ZM. Auffällig ist eine Zeile nach derselben Regel wie im Bericht „UStVA Kennzahlen“ (`Thresholds.exceeded`) mit den Schwellen der Einstellungen, ohne Eintrag 50 % und 100 €. Eine auffällige Zeile ergibt einen Hinweis, etwa „Die Zeile ATU12345678 (L) liegt mit 12.000,00 € um 140,0 % über der Vorperiode März 2026 (5.000,00 €).“

## Berichtigung

Wer eine abgegebene ZM als unrichtig oder unvollständig erkennt, muss sie „innerhalb eines Monats“ berichtigen (§ 18a Absatz 10 UStG). Das BZSt beschreibt die Form [Q8]: „Für jeden zu berichtigenden Meldezeitraum ist eine gesonderte berichtigte ZM elektronisch zu übermitteln. Korrekt gemeldete Angaben sind in der berichtigten ZM nicht zu wiederholen.“ Eine Summe wird durch die richtige ersetzt, „nicht nur der zu viel oder zu wenig gemeldete Differenzbetrag“ [Q10, IV.12.2]; eine falsche Zeile wird im ursprünglichen Meldezeitraum mit 0 storniert [Q10, IV.12].

[`correction.py`](../steuerbote/zm/correction.py) vergleicht dazu, was das BZSt für den Meldezeitraum hält (`as_filed()`: die ursprüngliche ZM und jede frühere Berichtigung, eine spätere Zeile ersetzt die frühere), mit den Zeilen von heute (`correct()`): Eine neue oder geänderte Zeile trägt ihre neue Summe, eine weggefallene 0, eine unveränderte entfällt. Stornierte Zeilen stehen zuerst. Die Tests rechnen die fünf Fälle des BZSt nach, alle mit dem spanischen Unternehmer P:

| Fall des BZSt | Gemeldet | Richtig | Berichtigung |
|---|---|---|---|
| 1. unvollständige ZM | ohne P | P, L, 5.000 | P, L, 5.000 |
| 2. falscher Meldezeitraum | Februar: P, L, 13.000 | März: P, L, 13.000 | Februar: P, L, 0; März: P, L, 13.000 |
| 3. falsche USt-IdNr. | ES111111113, L, 21.000 | ES111111112, L, 21.000 | ES111111113, L, 0 und ES111111112, L, 21.000 |
| 4. falsche Summe | P, L, 30.000 | P, L, 20.000 | P, L, 20.000 |
| 5. falsche Art | P, S, 20.000 | P, L, 20.000 | P, S, 0 und P, L, 20.000 |

Eine Berichtigung bezieht sich immer auf den Meldezeitraum der ZM, die sie berichtigt. Ein Rabatt, ein Skonto oder ein Forderungsausfall ist dagegen keine Berichtigung: „Der geänderte Umsatz ist in dem Monat zu erklären, in dem die Änderung eingetreten ist.“ [Q8] Das Hauptbuch bucht ihn dann, und die ZM dieses Zeitraums meldet ihn.

## CSV-Datei für Mein ELSTER

Ohne Hersteller-ID geht die ZM nicht über ERiC. Das Formular „Zusammenfassende Meldung“ in Mein ELSTER und im BZSt-Online-Portal übernimmt die Meldezeilen aber aus einer CSV-Datei [Q7]. [`csv_file.py`](../steuerbote/zm/csv_file.py) schreibt sie nach der Hilfe „Import von Meldelisten zur Zusammenfassenden Meldung“ [Q13] und der allgemeinen Anleitung für CSV-Dateien [Q14]; ein Test vergleicht die Datei Byte für Byte mit dem Beispiel der Hilfe.

| Regel | Grundlage |
|---|---|
| Zeile 1 `#v3.0`: die neueste CSV-Version mit dem Präfix `#v` | Versionstabelle [Q13]; „1. Zeile: Neueste CSV-Version der Importfunktion mit dem Präfix #v“ [Q14] |
| Zeile 2 `#ve3.2.1`: die Excel-Version derselben Tabelle | Beispiel [Q13]; die allgemeine Anleitung [Q14] erwähnt die Zeile nicht, siehe offene Punkte |
| Zeile 3 die Spaltenköpfe `Umsatzsteuer-Identifikationsnummer (USt-IdNr.),Summe (Euro),Art der Leistung` | Datensatztabelle Meldezeilen und Beispiel [Q13] |
| je Meldezeile USt-IdNr., Summe und Art, durch Komma getrennt; „Dateiweit darf nur ein Trennzeichen verwendet werden.“ | [Q13], [Q14] |
| Summe als ganze Zahl, höchstens 11 Ziffern, mit Minuszeichen 12 | Datensatztabelle Meldezeilen [Q13] |
| UTF-8 ohne Byte Order Mark: „Sie können sowohl "UTF-8" als auch "UTF-8 mit BOM" als Encoding verwenden.“ | [Q15] |
| Zeilen durch Zeilenvorschub getrennt, nach der letzten Zeile nichts; „Leere Zeilen sind nicht erlaubt.“ | Beispiel [Q13], [Q14] |
| höchstens 1.500 Meldezeilen, sonst ein Fehler mit der Zahl der Zeilen | „Es können maximal 1500 Datenzeilen in einer CSV-Datei importiert werden.“ [Q13]; das Formular nimmt höchstens 1.500 Meldezeilen [Q7] |
| mindestens eine Zeile, keine Zeile doppelt, 0 nur in einer Berichtigung | ZMDO 170045001 bis 170045005 [Q11], [Q8] |

Eine Berichtigung schreibt nur ihre geänderten Zeilen (`csv_file(correction.lines, correction=True)`).

**Mehr als 1.500 Zeilen** nimmt das Formular nicht. Das BZSt nennt dafür die Massendatenschnittstelle ELMA5 im BZSt-Online-Portal [Q9]; die Übermittlung über ERiC (ZMDO) nimmt bis zu 5.000 Zeilen [Q11] und folgt mit der Hersteller-ID.

**Import in Mein ELSTER**, soweit die Hilfe ihn beschreibt:

1. Das Formular „Zusammenfassende Meldung“ öffnen, das das BZSt verlinkt: <https://www.elster.de/eportal/formulare-leistungen/alleformulare/zmdo> [Q7].
2. Den Kopf ausfüllen: eigene USt-IdNr., Meldezeitraum, „Berichtigte Meldung“ und, wenn sie zutreffen, Anzeige oder Widerruf nach § 18a Absatz 1 UStG [Q10, IV.1 bis IV.5]. Für eine Berichtigung fragt das Formular unter „Berichtigte Meldung“, „ob bereits eine Zusammenfassende Meldung abgegeben wurde, deren Inhalt zu berichtigen ist“ [Q8].
3. Im aufklappbaren Bereich „Import von Daten (CSV-Format)“ die Datei importieren [Q14].
4. Scheitert der Import, bietet das Formular eine kommentierte CSV-Datei an, mit den Fehlern in der letzten Spalte; nach der Korrektur den Import wiederholen [Q14].
5. Nach dem Import prüfen, „dass die Anzahl der Datensätze in der CSV-Datei mit der Anzahl der importierten Datensätze übereinstimmt“ [Q14].
6. Die ZM in Mein ELSTER absenden.

## Die Zusammenfassende Meldung in ERPNext

Der Beleg „Zusammenfassende Meldung“ (`Recapitulative Statement`) bringt den Kern in ERPNext. Er rechnet nichts selbst: Jede Zeile, jeder Betrag und jede Regel kommt aus `steuerbote/zm`, die Frappe-Schicht liest die Daten und hält das Ergebnis fest. Wie die Teile zusammenspielen, beschreibt [Architektur](architektur.md#die-zusammenfassende-meldung).

### Einstellungen

In den Einstellungen Umsatzsteuer-Voranmeldung des Unternehmens stehen dazu:

| Feld | Inhalt |
|---|---|
| USt-IdNr. | die eigene deutsche USt-IdNr., DE und neun Ziffern; mit ihr fragt Steuerbote das BZSt nach den USt-IdNrn. der Kunden. Bleibt das Feld leer, übernimmt Steuerbote beim Speichern das Feld „Steuernummer“ (`tax_id`) des Unternehmens, wenn es eine deutsche USt-IdNr. enthält. |
| Abgaberhythmus der Zusammenfassenden Meldung | Tabelle „Regel zur Zusammenfassenden Meldung“ mit Jahr, Gültig ab Monat, Abgaberhythmus (monatlich, vierteljährlich oder jährlich), Sonstige Leistungen monatlich und Grund. Jede Regel gilt bis zur nächsten, wie unter [Abgaberhythmus](#abgaberhythmus) beschrieben; der Kern prüft die Regeln beim Speichern. |

Ohne Abgaberhythmus lässt sich keine Zusammenfassende Meldung anlegen, ohne Kontenzuordnung keine berechnen.

### Der Beleg

Eine Meldung gilt einem Unternehmen und einem Meldezeitraum: Jahr, Art des Meldezeitraums (Kalendermonat, zwei Monate eines Quartals, Kalendervierteljahr oder Kalenderjahr) und Nummer (Monat 1 bis 12 oder Quartal 1 bis 4, beim Kalenderjahr keine). Beim Speichern prüft sie, dass der Abgaberhythmus diesen Meldezeitraum ergibt, und setzt Meldezeitraum, Code `quart`, Von- und Bis-Datum, Fälligkeit und die Monate, deren Lieferungen und deren sonstige Leistungen sie meldet (`coverage()`, Felder „Lieferungen von“ bis „Sonstige Leistungen bis“). Eine abgegebene Meldung behält diese Monate, auch wenn sich der Abgaberhythmus später ändert. Fällig ist sie am 25. Tag nach Ablauf des Meldezeitraums; fällt er auf ein Wochenende oder einen Tag der Standard-Feiertagsliste des Unternehmens, am nächsten Werktag (Entscheidung des Maintainers [Q16]). Tage, die die Liste als wöchentlich frei markiert, verschieben keine Frist: Samstag und Sonntag kennt der Kern selbst, und ein anderer freier Wochentag ist kein gesetzlicher Feiertag (§ 108 Absatz 3 AO [Q5]). Dieselbe Regel gilt für die Dauerfristverlängerung (`steuerbote/holiday_list.py`). Die Liste sollte deshalb nur gesetzliche Feiertage enthalten, sonst verschiebt sich die Frist zu weit. „Anzeige der monatlichen Abgabe“ und „Widerruf der Anzeige“ sind Felder im Kopf des Formulars in Mein ELSTER; Steuerbote prüft sie mit `check_notices()` und hält fest, was dort anzukreuzen ist.

| Status | Bedeutung |
|---|---|
| Entwurf | angelegt und noch nicht berechnet, oder Unternehmen, Jahr oder Meldezeitraum haben sich geändert; das verwirft die Berechnung |
| Berechnet | berechnet, aber ein Fehler der Befunde hält die Meldung an |
| Bereit | berechnet, kein Fehler hält die Meldung an |
| Abgegeben | als abgegeben vermerkt und damit eingereicht |
| Ersetzt | für denselben Meldezeitraum ist später eine Berichtigung abgegeben worden |

### Berechnen

„Berechnen“ nimmt die Monate, die der Abgaberhythmus dem Meldezeitraum gibt (`coverage()`), und liest:

1. **Belege:** die Buchungen (GL Entry) auf den Konten, denen die Kontenzuordnung Kz 41, 42 oder 21 gibt, mit den Ausschlüssen der Voranmeldung (`steuerbote/ledger.py`), je Beleg aufgeteilt wie im Bericht „UStVA Kennzahlen“: Kz 41 und 42 aus den Lieferungsmonaten, Kz 21 aus den Leistungsmonaten, jeweils nach Buchungsdatum. Ein Dreiecksgeschäft ist ein Beleg auf einem Konto der Kz 42.
2. **Kunden:** Eine Ausgangsrechnung nennt ihren Kunden und hält dessen USt-IdNr. (`tax_id`) fest, wie sie beim Anlegen war; das Bestimmungsland eines Dreiecksgeschäfts ist das Land der Lieferanschrift der Rechnung, ohne sie das der Rechnungsanschrift. Eine Zahlung, etwa mit Skonto, nennt ihren Kunden; USt-IdNr. und Land kommen aus der ersten bezahlten Rechnung, die sie hat, sonst die USt-IdNr. aus dem Kunden. Eine Journalbuchung zählt mit dem einzigen Kunden, den ihre Zeilen nennen; USt-IdNr. und Land kommen wie bei einer Zahlung aus der ersten Ausgangsrechnung, auf die sich ihre Zeilen beziehen (Referenztyp „Sales Invoice“), etwa bei einer Gutschrift als Journalbuchung auf ein Konto der Kz 42, sonst die USt-IdNr. aus dem Kunden. Andere Belege nennen keinen Kunden, und der Kern meldet das je Beleg (`ZM-OHNE-KUNDE`).
3. **Bestätigungen:** je USt-IdNr. das Ergebnis der letzten USt-IdNr.-Bestätigung des Unternehmens. Eine Nummer, die nie bestätigt wurde oder deren Prüfung keine Antwort bekam, gilt als nicht bestätigt und hält die Meldung an (`ZM-USTID-UNBESTAETIGT`).
4. **Schwelle:** Kz 41 und 42 je Monat für die vier Quartale vor dem Meldezeitraum und den Meldezeitraum selbst (`threshold_window()`), mit einer Abfrage je Monat und der Kontenzuordnung auch für Monate des Vorjahres.
5. **Abgegebene Voranmeldungen:** Kz 41, 42 und 21 der abgegebenen, nicht ersetzten Voranmeldungen, deren Zeiträume zusammen genau die Monate der Meldung ergeben. Fehlt ein Monat, unterbleibt dieser Abgleich.
6. **Vorperiode:** die Zeilen des vorigen Meldezeitraums derselben Art, ebenso aus dem Hauptbuch.

Daraus füllt der Kern die Tabellen der Meldung: Meldezeilen (`build()`), Belege der Meldezeilen, Abgleich mit der Voranmeldung (`reconcile()`), Vorperiodenvergleich (`compare()`) und Befunde. Die Summen L, D und S sind die Summen der Meldezeilen. Bereit ist eine Meldung, wenn keine Zeile gesperrt ist (`Statement.ready`) und weder `ZM-SCHWELLE` noch `ZM-ABGLEICH-HAUPTBUCH` vorliegt.

### Korrekturen und eigene Zeilen

Eine Zeile bekommt einen korrigierten Betrag in ganzen Euro mit Begründung. Die Korrektur ersetzt den gemeldeten Betrag und hebt die Sperre der Zeile auf, sobald die Meldung gespeichert ist; einen Betrag ohne Begründung lehnt Steuerbote ab. Ebenso bleibt eine eigene Zeile ohne Belege mit USt-IdNr., Art, Betrag und Begründung, etwa ein Verbringen unter der eigenen USt-IdNr. im anderen Mitgliedstaat. „Berechnen“ übernimmt Korrekturen und eigene Zeilen.

### USt-IdNrn. prüfen

Die Schaltfläche fragt das BZSt im Hintergrund nach jeder USt-IdNr., die die Meldung meldet, eine nach der anderen und ohne Wiederholung, für die qualifizierte Abfrage mit Name und Ort des Kunden, wo sie bekannt sind. Jede Abfrage bleibt als USt-IdNr.-Bestätigung erhalten, und jede Zeile zeigt die letzte Prüfung ihrer Nummer. Einzelheiten stehen in [Prüfung ausländischer USt-IdNrn.](ust-idnr-pruefung.md#in-erpnext).

### CSV für Mein ELSTER und Abgabe

„CSV für Mein ELSTER“ schreibt die Zeilen der gespeicherten Meldung mit `csv_file()` und hängt die Datei privat an die Meldung, etwa `ZM-2026-03.csv`, für eine Berichtigung `ZM-2026-03-berichtigt.csv`. Die Datei gibt es für eine Meldung, die bereit ist oder deren Anmerkungen begründen, warum sie trotzdem abgegeben wird, und für jede abgegebene Meldung. So geht sie an das BZSt:

1. In Steuerbote „Berechnen“ und „USt-IdNrn. prüfen“, bis die Meldung „Bereit“ ist oder die Anmerkungen begründen, warum sie trotzdem abgegeben wird.
2. „CSV für Mein ELSTER“ und die Datei speichern.
3. In Mein ELSTER das Formular „Zusammenfassende Meldung“ öffnen und den Kopf ausfüllen, wie unter [Import in Mein ELSTER](#csv-datei-für-mein-elster) beschrieben: eigene USt-IdNr., Meldezeitraum, bei einer Berichtigung „Berichtigte Meldung“ und, wenn die Meldung sie trägt, Anzeige oder Widerruf.
4. Unter „Import von Daten (CSV-Format)“ die Datei importieren und prüfen, dass das Formular so viele Zeilen zeigt wie die Datei.
5. Die ZM in Mein ELSTER absenden.
6. In Steuerbote „In Mein ELSTER abgegeben“ mit dem Tag der Abgabe und, wenn vorhanden, dem Transferticket des Protokolls vermerken. Für jeden anderen Weg, etwa das BZSt-Online-Portal oder die Steuerberatung, „Als außerhalb abgegeben vermerken“ mit einer Notiz, wie und wann.

Erst der Vermerk reicht die Meldung ein; „Buchen“ allein lehnt Steuerbote ab. Ein Meldezeitraum wird je Unternehmen einmal abgegeben, und ebenso die Lieferungen und die sonstigen Leistungen jedes Monats: Gibt ein geänderter Abgaberhythmus einen Monat einem zweiten Meldezeitraum, etwa den Januar nach einer vierteljährlichen Abgabe einer monatlichen ZM, lehnt Steuerbote die zweite Meldung ab. Eine abgegebene Meldung lässt sich nicht stornieren: Eine Änderung geht als Berichtigung an das BZSt.

### Berichtigung anlegen

Die Schaltfläche an der zuletzt abgegebenen Meldung legt eine Meldung desselben Meldezeitraums mit der Meldeart „Berichtigung“ an, übernimmt Korrekturen und eigene Zeilen und berechnet sie. Sie vergleicht die Zeilen von heute mit dem, was das BZSt nach den bisherigen Abgaben des Meldezeitraums hält (`as_filed()`, `correct()`): Jede Zeile zeigt „Bisher gemeldet“ und ob sie in der Datei steht. Die Datei meldet nur die geänderten Zeilen mit ihrer neuen Summe und storniert eine weggefallene Zeile mit 0. Ändert sich nichts, lässt sich die Berichtigung nicht abgeben. Wird sie abgegeben, steht die frühere Meldung auf „Ersetzt“. Wurde nach dem Anlegen einer Berichtigung eine andere Abgabe des Meldezeitraums vermerkt, ist die Berichtigung neu anzulegen.

### Druckformat

Das Druckformat „Zusammenfassende Meldung“ zeigt Unternehmen, eigene USt-IdNr., Meldezeitraum, Fälligkeit, Meldeart und Status, dann die Zeilen der Datei je USt-IdNr. und Art mit dem Kunden und die Summen je Art, bei einer Berichtigung mit „Bisher gemeldet“, dazu die Korrekturen mit Begründung und die Anmerkungen. Der Ausdruck ist keine Abgabe.

## Offene Punkte

- **ZMDO über ERiC** mit Anzeige und Widerruf, sobald es die Hersteller-ID gibt.
- **Feiertage:** Die Fälligkeit folgt der Standard-Feiertagsliste des Unternehmens. Welche Feiertage für eine Frist beim BZSt gelten, sagt keine der Quellen.
- **Rundung:** Das Abschneiden der Cent ist eine Annahme; eine Bestätigung des BZSt oder der ELSTER-Hotline steht aus.
- **Zeile `#ve3.2.1`:** Das Beispiel der Hilfe hat sie, die allgemeine Anleitung nennt nur die Zeile `#v`. Ob der Import sie verlangt, ist nicht belegt; Steuerbote schreibt sie wie das Beispiel. Bringt die Versionstabelle eine neue Version, ändern sich `VERSION` und `EXCEL_VERSION`.
- **Zeilenende:** Die Hilfe schreibt keines vor. Steuerbote folgt dem Beispiel: Zeilenvorschub, keiner nach der letzten Zeile.
- **Verbringen** (§ 6a Absatz 2 UStG) braucht eine Zeile von Hand, siehe Übersteuern.
- **Konsignationslager** (§ 6b UStG): Die Angaben lassen sich derzeit nicht im Verfahren der ZM übermitteln; das BZSt hält dafür ein eigenes Formular bereit [Q7, Q9]. Steuerbote meldet sie nicht.
- **Nordirland als Bestimmungsland:** ERPNext kennt Nordirland nicht als Land. Ein Dreiecksgeschäft mit einer XI-Nummer bekommt `ZM-DREIECK-LAND`, wenn die Frappe-Schicht nicht „XI“ als Land übergibt.
- **Dreiecksgeschäfte** kennt ERPNext nicht eigens; Steuerbote findet sie über die Konten der Kz 42 aus der Kontenzuordnung. Ein Dreiecksgeschäft auf einem anderen Konto erkennt Steuerbote nicht.
- **Prüfungen von ERiC**, die erst die Übermittlung betreffen, prüft der Kern nicht: kein Meldezeitraum in der Zukunft (170015020), eine ZM für zwei Monate erst ab dem zweiten Monat (170015019), höchstens zehn Jahre zurück (170015016).

## Quellen

- **[Q1]** § 18a UStG „Zusammenfassende Meldung“: <https://www.gesetze-im-internet.de/ustg_1980/__18a.html>
- **[Q2]** § 18b UStG „Gesonderte Erklärung innergemeinschaftlicher Lieferungen und bestimmter sonstiger Leistungen im Besteuerungsverfahren“: <https://www.gesetze-im-internet.de/ustg_1980/__18b.html>
- **[Q3]** § 4 Nummer 1 Buchstabe b UStG: <https://www.gesetze-im-internet.de/ustg_1980/__4.html>; § 6a UStG „Innergemeinschaftliche Lieferung“: <https://www.gesetze-im-internet.de/ustg_1980/__6a.html>
- **[Q4]** BMF-Schreiben vom 29. Dezember 2025, GZ III C 3 - S 7344/00039/007/036, Vordruck USt 1 A 2026 und Anleitung USt 1 E 2026, Zeilen 19, 33 und 35, siehe [Kennzahlen und Kontenzuordnung](ustva-kennzahlen.md#quelle)
- **[Q5]** § 108 AO „Fristen und Termine“: <https://www.gesetze-im-internet.de/ao_1977/__108.html>
- **[Q6]** BZSt „Fristen“ (ZM): <https://www.bzst.de/DE/Unternehmen/Umsatzsteuer/ZusammenfassendeMeldung/Fristen/fristen_node.html>
- **[Q7]** BZSt „Elektronische Abgabe und Datenübermittlung“ (ZM): <https://www.bzst.de/DE/Unternehmen/Umsatzsteuer/ZusammenfassendeMeldung/ElektronischeAbgabe/elektronischeabgabe_zm_node.html>
- **[Q8]** BZSt „Berichtigung einer ZM“, Abschnitte „Fristen“, „Berichtigungs-Form“, Fälle 1 bis 5 und „Rabatte, Stornierungen“: <https://www.bzst.de/DE/Unternehmen/Umsatzsteuer/ZusammenfassendeMeldung/BerichtigungZM/berichtigung_node.html>
- **[Q9]** BZSt „Fragen und Antworten“ (ZM), darunter die Fragen zu Meldezeiträumen, ELMA5, Konsignationslager und Brexit: <https://www.bzst.de/DE/Unternehmen/Umsatzsteuer/ZusammenfassendeMeldung/FAQ/faq_zm.html>
- **[Q10]** BZSt „Anleitung zur Zusammenfassenden Meldung“ (USt ZM 1/2021), Textziffern III.1 und IV.1 bis IV.12: <https://www.bzst.de/SharedDocs/Downloads/DE/ZM/zm_ausfuellanleitung.pdf?__blob=publicationFile&v=14>
- **[Q11]** ERiC-Dokumentation 44.3.6.0, wie in der CI gepinnt: `Datenarten/ElsterExtern/ZMDO/Jahresdokumentation/Jahresdokumentation_ZMDO_2.ods`, Blätter „ZMDO - Felder“ (`quart`, `knre_UstIdNr_Erwerber`, `betrag`) und „ZMDO - Regeln“, sowie `Schema/5/zm_000005.xsd`: <https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Dokumentation.zip>
- **[Q12]** Abkommen über den Austritt des Vereinigten Königreichs aus der EU und der EAG, Protokoll zu Irland/Nordirland, Artikel 8 „VAT and excise“, englische Fassung im ABl. C 384 I vom 12. November 2019, S. 1: <https://www.legislation.gov.uk/eut/withdrawal-agreement/pdfs/eut_withdrawal-agreement_adopted_en.pdf>
- **[Q13]** ELSTER-Hilfe „Import von Meldelisten zur Zusammenfassenden Meldung“, Abschnitte „Versionstabelle“, „Datensatztabelle Meldezeilen (Satzart 1)“, „Beispielhafte CSV-Datei“ und „Liste der Länderkennzeichen“: <https://www.elster.de/eportal/helpGlobal?themaGlobal=zmdo_import_eop>
- **[Q14]** ELSTER-Hilfe „Allgemeine Anleitung zur Erstellung von CSV-Dateien für die Importfunktion“, Abschnitte „Aufbau einer CSV-Datei“, „Vorgaben für gültige CSV-Dateien“ und „Import der CSV-Datei“: <https://www.elster.de/eportal/helpGlobal?themaGlobal=allgemeine_csv-anleitung>
- **[Q15]** ELSTER-Hilfe „Hilfe zur UTF-8-Umstellung der Importfunktion“: <https://www.elster.de/eportal/helpGlobal?themaGlobal=help_utf-8_import>
- **[Q16]** Entscheidungen des Maintainers vom 20. November 2026: Zeilen aus dem Hauptbuch je Beleg, Abschneiden auf ganze Euro, ungültige USt-IdNr. sperrt „Bereit“ und lässt sich je Zeile mit Begründung übersteuern, XI nur für Lieferungen, Buchungsdatum für die Zuordnung zum Zeitraum; in ERPNext der Abgaberhythmus aus den Einstellungen mit Prüfung der Schwelle, die Feiertage aus der Standard-Feiertagsliste des Unternehmens und die Bestätigung beim BZSt mit VIES als Ausweichdienst, ohne die Prüfungen der App erpnext_germany.
