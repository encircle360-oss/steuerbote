# Körperschaftsteuer- und Gewerbesteuererklärung

Eine GmbH oder UG erklärt für jedes Jahr ihre Steuern vom Einkommen und Ertrag: die Körperschaftsteuer mit der Erklärung zur gesonderten Feststellung des steuerlichen Einlagekontos (KSt 1 mit den Anlagen GK, ZVE, Z, Verluste und WA und KSt 1 F; § 31 Abs. 1 und 1a, § 27 Abs. 2 Satz 4 KStG) und die Gewerbesteuer mit der Erklärung zur Festsetzung des Steuermessbetrags (GewSt 1 A mit einer Anlage BEG je Beteiligung; § 14a Satz 1 GewStG), beide nach amtlich vorgeschriebenem Datensatz. Steuerbote berechnet sie als Belege „Körperschaftsteuererklärung“ (`Corporate Income Tax Return`) und „Gewerbesteuererklärung“ (`Trade Tax Return`) aus der Gewinn- und Verlustrechnung des Wirtschaftsjahres, der Kontenzuordnung Ertragsteuern und den Einstellungen Jahresmeldungen, prüft sie mit den Regeln der Jahresdokumentationen, die Steuerbote selbst prüft, schlägt die Rückstellungen der drei Steuern als Journalbuchung im Entwurf vor und druckt beide in der Reihenfolge und mit den Zeilen der Vordrucke. Über ERiC gehen sie, sobald ERiC die Plugins des Jahres mitbringt und Steuerbote eine Hersteller-ID hat; bis dahin läuft die Übermittlung als Simulation, und die Erklärungen werden in Mein ELSTER nach den Druckformaten eingegeben. Diese Seite ersetzt keine Steuerberatung.

Beide Belege leben auf der Grundlage der Jahresmeldungen: Status, Berechnen, Korrekturen und Zeilen von Hand, Befunde, Abgabe, Berichtigung und Übermittlung sind die aller Jahresmeldungen und stehen in [Jahresmeldungen](jahresmeldungen.md). Die Rechenkerne unter `steuerbote/kst` und `steuerbote/gewst` beschreibt [Rechenkern der Ertragsteuern](architektur.md#rechenkern-der-ertragsteuern), die Datenarten, das XML und die Simulation [ERiC](eric.md#erklärungen-und-e-bilanz). Es gibt eine Rechnung, nicht zwei: Die Gewerbesteuererklärung baut auf der Körperschaftsteuererklärung desselben Unternehmens und Jahres auf, und ihr Gewinn aus Gewerbebetrieb folgt aus deren Summe der Einkünfte, Anlage ZVE Zeile 32 ohne die Wirkung von § 15 Abs. 4 EStG, also mit zurückgenommenen Anlage GK Zeilen 51 und 52 (R 7.1 Abs. 4 GewStR).

## Umfang

- **Unternehmen:** eine GmbH oder UG (haftungsbeschränkt) mit Geschäftsleitung oder Sitz im Inland (§ 1 Abs. 1 KStG), mit dem Kontenrahmen SKR03 oder SKR04 und den Vorgaben der Kontenzuordnung Ertragsteuern. Ein eigener Kontenrahmen geht mit einer eigenen Zuordnung, aber ohne den Vergleich mit den Vorgaben, ohne den Vergleich der Vorauszahlungen mit dem Hauptbuch und ohne „Rückstellungen vorschlagen“.
- **Jahre:** 2026, vorläufig mit den Vordrucken der Jahresdokumentationen E30 und E20 2025 (`steuerbote/kst/years.py`, `steuerbote/gewst/years.py`), siehe [Vorläufige Vordrucke 2026](#vorläufige-vordrucke-2026). Ein Jahr ohne Vordrucke lehnt der Beleg beim Speichern ab.
- **Wirtschaftsjahr:** das Geschäftsjahr von ERPNext, das im Jahr endet (§ 7 Abs. 4 KStG), eines je Jahr.
- **Gewerbesteuer:** eine Betriebsstätte in einer Gemeinde.
- **Nicht darin:** Organschaft, ausländische Steuern (Anlage AESt), Investmentfonds, die Zerlegung (GewSt 1 D), die Zinsschranke über einen Hinweis hinaus und die E-Bilanz selbst, siehe [Grenzen](#grenzen).

## Die Belege

Je Unternehmen und Jahr ein Beleg jeder Erklärung, benannt nach dem Jahr, für das er gilt (`KSt-2026-00001`, `GewSt-2026-00001`). Jeder weitere Beleg des Jahres ist eine Berichtigung, siehe [Berichtigung](#berichtigung).

### Körperschaftsteuererklärung

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company`, `year` | Unternehmen, Jahr | Pflicht; das Jahr ist der Veranlagungszeitraum, das Kalenderjahr, in dem das Wirtschaftsjahr endet, und wählt die Vordrucke |
| `fiscal_year`, `from_date`, `to_date`, `status`, `ready`, `deadline`, `is_correction`, `corrects`, `transmission_in_progress`, `findings`, `filed_via`, `filed_on`, `transferticket`, `filed_by`, `filing_note`, `remarks` | | die Felder jedes Belegs einer Jahresmeldung, siehe [Felder jedes Belegs](jahresmeldungen.md#felder-jedes-belegs) |
| `provisional` | Vorläufige Vordrucke | setzt jedes Speichern: Die Vordrucke des Jahres sind die der Jahresdokumentation eines früheren Jahres, siehe [Vorläufige Vordrucke 2026](#vorläufige-vordrucke-2026) |
| `vorgang` | Vorgang | immer 01, Veranlagung, wie der Vorsatz ihn schreibt |
| `electronic_balance_sheet` | E-Bilanz | die E-Bilanz des Jahres, deren Jahresüberschuss Anlage GK Zeile 11 nimmt, bei einer Handelsbilanz mit Überleitungsrechnung mit der Überleitung zur Steuerbilanz, siehe [Aus der E-Bilanz](#aus-der-e-bilanz). „Berechnen“ nimmt die genannte, solange sie berechnet oder abgegeben und nicht ersetzt ist, sonst die neueste solche des Unternehmens und Jahres, und nennt sie hier; ein neuer Beleg nennt sie beim Anlegen. Eine E-Bilanz eines anderen Unternehmens oder Jahres, eine Eröffnungsbilanz und eine stornierte lehnt das Speichern ab |
| `net_income` | Jahresüberschuss (GK Zeile 11) | setzt „Berechnen“, wie alle Felder des Abschnitts „Berechnung“: der Jahresüberschuss der E-Bilanz oder, ohne sie, der Bücher, mit der Überleitung zur Steuerbilanz |
| `business_income` | Einkünfte aus Gewerbebetrieb (GK Zeile 300) | |
| `sum_of_income` | Summe der Einkünfte (ZVE Zeile 32) | |
| `total_income` | Gesamtbetrag der Einkünfte (ZVE Zeile 53) | |
| `zve` | Zu versteuerndes Einkommen (ZVE Zeile 70) | |
| `kst` | Körperschaftsteuer (ZVE Zeile 71) | 15 % des zu versteuernden Einkommens, auf volle Euro nach unten (§ 23 Abs. 1 und § 31 Abs. 1 KStG; Regel 8900331) |
| `solz` | Solidaritätszuschlag | 5,5 % der Körperschaftsteuer ohne Bruchteile eines Cents (§§ 3, 4 SolZG) |
| `capital_gains_tax_credit`, `solz_credit` | Anrechenbare Kapitalertragsteuer (WA Zeile 2), Anrechenbarer Solidaritätszuschlag (WA Zeile 3) | die Summen der Steuerbescheinigungen |
| `kst_prepayments`, `solz_prepayments` | Vorauszahlungen Körperschaftsteuer, Vorauszahlungen Solidaritätszuschlag | die Vorauszahlungen der Bescheide des Jahres aus den Einstellungen Jahresmeldungen |
| `kst_balance`, `solz_balance` | Abschlusszahlung oder Erstattung Körperschaftsteuer, Abschlusszahlung oder Erstattung Solidaritätszuschlag | die Steuer abzüglich der anrechenbaren Steuern und der Vorauszahlungen, negativ eine Erstattung |
| `einlagekonto` | Steuerliches Einlagekonto zum Schluss des Jahres (KSt 1 F Zeile 152) | der Bestand nach § 27 KStG |
| `provisions_entry` | Buchungsentwurf der Rückstellungen | die Journalbuchung, die „Rückstellungen vorschlagen“ zuletzt im Entwurf angelegt hat, siehe [Rückstellungen vorschlagen](#rückstellungen-vorschlagen) |
| `lines` | Zeilen der Erklärung | Tabelle „Zeile der Körperschaftsteuererklärung“, siehe [Zeilen](#zeilen-korrekturen-und-zeilen-von-hand) |
| `supplement_key`, `supplement_text` | Ergänzende Angaben zur Steuererklärung (KSt 1 Zeile 13), Ergänzende Angaben | der qualifizierte Freitext nach § 150 Abs. 7 Satz 1 AO: Schlüssel 1 bis 4 und Text, das eine nur mit dem anderen (Regel 8900735) |
| `shareholder_contracts` | Verträge mit Anteilseignern geschlossen oder geändert (WA Zeile 15) | Vorgabe nein |
| `carry_back_chosen`, `loss_carry_back` | Verlustrücktrag gewählt (Verluste Zeile 20), Verlustrücktrag | bei einem Verlust des Jahres der Betrag, der in vorangegangene Veranlagungszeiträume zurückgetragen wird, 0 für den Verzicht (§ 10d Abs. 1 EStG) |
| `turnover_and_wages_given` | Umsätze, Löhne und Gehälter angegeben (Anlage Z Zeile 10) | wenn die Zuwendungen 20 % der Summe der Einkünfte übersteigen (§ 9 Abs. 1 Nr. 2 Satz 1 KStG): Mit dem Haken zählt der Betrag des folgenden Felds, auch 0; ohne ihn gilt er als nicht angegeben |
| `turnover_and_wages` | Umsätze, Löhne und Gehälter (Anlage Z Zeile 10) | die Umsätze und die Löhne und Gehälter des Kalenderjahres |
| `holding_results`, `credits`, `donations` | § 8b-Ergebnisse, Steuerbescheinigungen, Zuwendungsbestätigungen | Tabellen, siehe [Tabellen der Körperschaftsteuererklärung](#tabellen-der-körperschaftsteuererklärung) |
| `distributions`, `contributions` | Leistungen, Einlagen | die Tabellen von KSt 1 F, ebenda |
| `previous_equity` | Eigenkapital zum Schluss des vorangegangenen Wirtschaftsjahres (KSt 1 F Zeile 17) | aus der Steuerbilanz des Vorjahres, von Hand, solange für das Vorjahr keine E-Bilanz abgegeben ist; mit einer nimmt KSt 1 F deren Beträge, siehe [Aus der E-Bilanz](#aus-der-e-bilanz) |
| `previous_nominal_capital` | Nennkapital zum Schluss des vorangegangenen Wirtschaftsjahres (KSt 1 F Zeile 18) | mit dem Eigenkapital nötig für Leistungen, solange das Einlagekonto einen Bestand hat (§ 27 Abs. 1 Satz 5 KStG); beide 0 gelten als nicht angegeben |

### Gewerbesteuererklärung

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company`, `year` | Unternehmen, Jahr | Pflicht; das Jahr ist der Erhebungszeitraum |
| `corporate_income_tax_return` | Körperschaftsteuererklärung | die Körperschaftsteuererklärung des Unternehmens und Jahres, auf der die Erklärung aufbaut. Ein Speichern ohne sie nennt den Entwurf des Jahres oder, ohne Entwurf, die zuletzt abgegebene, die keine Berichtigung ersetzt hat; eine stornierte oder eine eines anderen Unternehmens oder Jahres lehnt es ab |
| `fiscal_year`, `from_date`, `to_date`, `status`, `ready`, `deadline`, `is_correction`, `corrects`, `transmission_in_progress`, `findings`, `filed_via`, `filed_on`, `transferticket`, `filed_by`, `filing_note`, `remarks`, `provisional`, `vorgang` | | wie an der Körperschaftsteuererklärung |
| `profit` | Gewinn aus Gewerbebetrieb (Zeile 39) | setzt „Berechnen“, wie alle Felder des Abschnitts „Berechnung“ |
| `financing_addback` | Hinzurechnung nach § 8 Nr. 1 GewStG | in Cent, nur für die Rückstellung: Die Erklärung gibt die Teile in voller Höhe an, die Hinzurechnung rechnet das Finanzamt |
| `gewerbeertrag` | Gewerbeertrag, auf volle 100 Euro abgerundet | § 11 Abs. 1 Satz 3 GewStG |
| `messbetrag` | Steuermessbetrag | 3,5 % des Gewerbeertrags, auf volle Euro nach unten (§ 11 Abs. 2 GewStG, R 14.1 GewStR) |
| `hebesatz`, `gewst` | Hebesatz, Gewerbesteuer | der Hebesatz der Gemeinde der Betriebsstätte aus den Einstellungen Jahresmeldungen und die Steuer darauf (§ 16 GewStG) |
| `prepayments`, `balance` | Vorauszahlungen Gewerbesteuer, Abschlusszahlung oder Erstattung Gewerbesteuer | die Vorauszahlungen der Bescheide des Jahres (§ 19 GewStG) und die Gewerbesteuer abzüglich ihrer |
| `lines` | Zeilen der Erklärung | Tabelle „Zeile der Gewerbesteuererklärung“: die Beträge der GewSt 1 A, ohne Korrekturen und ohne Zeilen von Hand |
| `municipalities` | Gemeinde | Tabelle „Gemeinde der Gewerbesteuererklärung“, siehe [Tabellen der Gewerbesteuererklärung](#tabellen-der-gewerbesteuererklärung) |
| `holdings` | Anlagen BEG | Tabelle „Anlage BEG“, ebenda |
| `donations` | Zuwendungsbestätigungen | die Zuwendungsbestätigungen der Körperschaftsteuererklärung, GewSt 1 A Zeilen 92a bis 92c |
| `supplement_key`, `supplement_text` | Ergänzende Angaben zur Steuererklärung (GewSt 1 A Zeile 21), Ergänzende Angaben | wie KSt 1 Zeile 13, das eine nur mit dem anderen (Regel 40128) |

Rechte wie bei der Voranmeldung: System Manager und Accounts Manager legen an, berechnen, ändern und geben ab; ein Accounts User legt an, berechnet und ändert, gibt aber nicht ab. Die Listen stehen als „KSt-Erklärungen“ und „GewSt-Erklärungen“ in der Seitenleiste in der Gruppe „Jahresmeldungen“ und im gleichnamigen Abschnitt des Arbeitsbereichs „Steuern“, dort neben „Neue KSt-Erklärung“ und „Neue GewSt-Erklärung“; der Bericht „Ertragsteuer-Kontennachweis“ steht in der Gruppe „Berichte“ als „KSt/GewSt-Nachweis“.

## Berechnen

„Berechnen“ an der Körperschaftsteuererklärung liest die Quellen des Wirtschaftsjahres (`steuerbote/income_tax_sources.py`) und rechnet mit dem Kern (`compute` in `corporate_income_tax_return.py`, über `corporate_income_tax_return/bridge.py`):

1. **Hauptbuch:** die Buchungen (GL Entry) der Konten der Kontoarten Ertrag und Aufwand vom ersten bis zum letzten Tag des Wirtschaftsjahres, je Konto und Beleg summiert. Stornierte Buchungen, Eröffnungsbuchungen und der Periodenabschlussbeleg bleiben draußen; Journalbuchungen mit dem Kennzeichen „Nicht in der Umsatzsteuer-Voranmeldung“ zählen mit, denn das Kennzeichen gilt der Umsatzsteuer. Von den Finanzbüchern zählen die Buchungen ohne Finanzbuch und die des Finanzbuchs der Handelsbilanz der Einstellungen Jahresmeldungen. Ihr Saldo, Haben abzüglich Soll, ist der Jahresüberschuss der Anlage GK Zeile 11, solange die Erklärung keine E-Bilanz nennt, siehe [Aus der E-Bilanz](#aus-der-e-bilanz); ein Konto ohne Nummer zählt darin mit, aber keine Zuordnung kann es einordnen.
2. **Kontenzuordnung Ertragsteuern:** gibt den Konten mit Nummer ihre Kategorie und den Handelskonten ihre Klasse, ein Konto ohne Zuordnung zählt nur im Jahresüberschuss; `classify()` summiert die Buchungen je Kategorie, und daraus kommen die Zeilen der Bücher, etwa die Körperschaftsteuer in Anlage GK Zeile 81 oder die Bezüge aus Anteilen in Zeile 156. Ohne Kontenzuordnung des Unternehmens rechnet „Berechnen“ nicht.
3. **Einstellungen Jahresmeldungen:** Rechtsform, Orte von Geschäftsleitung und Sitz, Anteilseigner, Beteiligungen, die Vorauszahlungen der Bescheide, die festgestellten Vorträge zum Schluss des vorangegangenen Wirtschaftsjahres, die nur bestätigt und in vollen Euro zählen, das Kennzeichen nach § 8b Abs. 7 KStG, der Tag der Prüfung durch die Steuerberatung und, in einem Jahr mit Mitwirkung einer Steuerberatung, die Steuerberatung; dazu die W-IdNr. aus den Einstellungen Umsatzsteuer-Voranmeldung und Name und Gründungsdatum des Unternehmens.
4. **Beleg:** die Zeilen von Hand und Korrekturen, die Tabellen und die Angaben, siehe unten. Den Verlustrücktrag nimmt der Kern nur, wenn der Gesamtbetrag der Einkünfte negativ ist; „Berechnen“ rechnet deshalb zuerst ohne ihn.
5. **Kern:** `steuerbote.kst.chain.compute()` rechnet die Anlagen GK, ZVE, Z, Verluste und WA bis zur Abschlusszahlung, `steuerbote.kst.einlagekonto.roll_forward()` das Einlagekonto, aus dem `kst1f()` KSt 1 F bildet.
6. **Regeln:** Auf die Vordrucke, wie die Erklärung sie abgibt, mit den Korrekturen und den Angaben aus Tabellen und Einstellungen, laufen die Regeln der Jahresdokumentation E30, die Steuerbote selbst prüft (`check_reported`, die Regeln von `steuerbote/eric/simulation/kst.py`).

„Berechnen“ an der Gewerbesteuererklärung rechnet die Körperschaftsteuer der Erklärung, die sie nennt, noch einmal, mit deren Zeilen und Tabellen, wie sie gespeichert sind, auf dem Hauptbuch von heute; die Körperschaftsteuererklärung muss dafür nicht berechnet sein. Auf ihr Ergebnis rechnet `steuerbote.gewst.chain.compute()` die Gewerbesteuer mit dem Hebesatz der Gemeinde der einen Betriebsstätte, dem vortragsfähigen Fehlbetrag (§ 10a GewStG) und dem Zuwendungsvortrag der Gewerbesteuer der Einstellungen, die ebenso nur bestätigt und in vollen Euro zählen, und den Vorauszahlungen der Bescheide. Auf GewSt 1 A und die Anlagen BEG laufen die Regeln der Jahresdokumentation E20, die Steuerbote selbst prüft (`steuerbote/eric/simulation/gewst.py`).

Die beiden `bridge.py` bringen die Ergebnisse in die Zeilen und Tabellen der Belege, ohne Frappe und mit eigenen Tests.

### Vorauszahlungen

Beide Erklärungen rechnen mit den Vorauszahlungen der Bescheide, wie die Einstellungen Jahresmeldungen sie je Steuer, Jahr und Fälligkeit halten (§ 37 EStG mit § 31 Abs. 1 KStG, § 19 GewStG), nicht mit dem Hauptbuch. Sie vergleichen sie mit den Vorauszahlungen, die im Wirtschaftsjahr gebucht sind, die Körperschaftsteuererklärung die der Körperschaftsteuer und des Solidaritätszuschlags, die Gewerbesteuererklärung die der Gewerbesteuer: Soll abzüglich Haben auf dem Aufwandskonto der Steuer, SKR03 2200 Körperschaftsteuer, 2208 Solidaritätszuschlag und 4320 Gewerbesteuer, SKR04 7600, 7608 und 7610, in allen Belegen, die weder die Rückstellung noch den Erstattungsanspruch der Steuer berühren. Ein Beleg, der sie berührt, etwa die Journalbuchung von „Rückstellungen vorschlagen“, bucht eine Rückstellung und keine Vorauszahlung. Weicht beides ab, gibt die Erklärung einen Hinweis (`KST-VORAUSZAHLUNGEN`, `GEWST-VORAUSZAHLUNGEN`); er hält sie nicht an. Bei einem eigenen Kontenrahmen kennt Steuerbote die Konten der Steuern nicht und vergleicht nichts.

## Zeilen, Korrekturen und Zeilen von Hand

Die Tabelle „Zeilen der Erklärung“ der Körperschaftsteuererklärung hält jeden Betrag der Vordrucke Anlage GK, Anlage ZVE, Anlage Z, Anlage Verluste, Anlage WA und KSt 1 F, der nicht zu einem Kontext gehört, der sich wiederholt, in der Reihenfolge der Vordrucke. Ihre Spalten: „Vordruck“ (`form`), „Zeile im Vordruck“ (`line`), „Feldkennung“ (`feldkennung`), die Beschreibung des Felds in der Jahresdokumentation (`label`), „Betrag laut Hauptbuch“ (`ledger_amount`, nur für eine Zeile der Bücher, auf den Cent), „Betrag laut Vordruck“ (`form_amount`), „Korrigierter Betrag“ (`correction`) mit „Begründung der Korrektur“ (`correction_reason`), „Gemeldeter Betrag“ (`reported`) und „Zeile von Hand“ (`manual`). Was sich wiederholt, etwa jede Veräußerung von Anteilen oder jede Zuwendungsbestätigung, kommt aus den Tabellen des Belegs, KSt 1 aus den Einstellungen.

- **Korrektur:** meldet einen anderen Betrag und braucht eine Begründung, wie an jeder Jahresmeldung. „Berechnen“ gibt sie dem Kern als Zeile von Hand des Unterschieds zu den Büchern, damit die Summen der Vordrucke sie mitnehmen. Eine Korrektur nimmt nur eine Zeile der Bücher oder eine, die die Rechnung der Hand überlässt; jede andere Zeile folgt aus ihnen, aus den Tabellen oder aus den Einstellungen, und das Speichern lehnt eine Korrektur dort ab. Das sind die Zeilen der Anlage GK:

  | Zeile | Feldkennung | Zeile | Feldkennung |
  |---|---|---|---|
  | 11 Jahresüberschuss | `E8002001` | 84 Gewerbesteuer | `E8100702` |
  | 67 Investitionsabzugsbeträge des Wirtschaftsjahres | `E8002602` | 87 Ausländische Steuern vom Einkommen | `E8101001` |
  | 70 bis 72 Hinzurechnung von Investitionsabzugsbeträgen | `E8002603`, `E8002604`, `E8002605` | 88 Nebenleistungen zu den Steuern | `E8101101` |
  | 75 Verdeckte Gewinnausschüttungen | `E8002701` | 89 Hälfte der Vergütungen an den Aufsichtsrat | `E8101201` |
  | 75c Ausschüttungen auf Genussrechte | `E8002709` | 90 Sonstige nichtabziehbare Aufwendungen | `E8101301` |
  | 81 Körperschaftsteuer | `E8100301` | 92 Spenden und Mitgliedsbeiträge | `E8101401` |
  | 82 Solidaritätszuschlag | `E8100501` | 96 Investitionszulage | `E8003601` |
  | 83 Kapitalertragsteuer | `E8100601` | 102 Sonstige steuerfreie Einnahmen | `E8003701` |

  Die Einlagen der Zeilen 78, 93 und 94 kommen aus der Tabelle „Einlagen“, nicht aus einer Korrektur.
- **Zeile von Hand:** eine neue Zeile mit der Feldkennung einer dieser Zeilen und ihrem Betrag als Korrektur mit Begründung. Das Speichern schreibt die Feldkennung groß, nimmt Vordruck, Zeile und Beschreibung ihres Felds dazu und lehnt eine andere Feldkennung ab; „Berechnen“ nimmt den Betrag in die Zeile seines Felds auf, etwa eine verdeckte Gewinnausschüttung auf `E8002701` (§ 8 Abs. 3 Satz 2 KStG).
- **Volle Euro:** Ein Feld, das volle Euro meldet, nimmt keine Korrektur mit Cent.
- **Die Überleitung zur Steuerbilanz** kommt aus der E-Bilanz, siehe [Aus der E-Bilanz](#aus-der-e-bilanz); ohne E-Bilanz kommt sie von Hand: je Schritt eine Zeile von Hand auf `E8002001` mit ihrer Begründung, etwa für eine Rückstellung für drohende Verluste, die die Steuerbilanz nicht kennt (§ 5 Abs. 4a EStG). Halten die Einstellungen eine Handelsbilanz mit Überleitungsrechnung (Bilanzierungsstandard HGBM), hält eine Erklärung ohne Zeile von Hand oder Korrektur auf `E8002001` an (`KST-UEBERLEITUNG-FEHLT`, § 60 Abs. 2 Satz 1 EStDV). Bei einer Einheitsbilanz (HAOE, die Vorgabe) und einer Steuerbilanz (AO) ist der Jahresüberschuss des Hauptbuchs der steuerliche.

Die Gewerbesteuererklärung nimmt keine Korrektur und keine Zeile von Hand, das Speichern lehnt beide ab: Zeile 39 folgt aus der Körperschaftsteuererklärung, die übrigen Zeilen kommen aus der Kontenzuordnung Ertragsteuern. Eine Korrektur gehört deshalb an die Körperschaftsteuererklärung oder in die Zuordnung. Ihre Tabelle „Zeilen der Erklärung“ hat dieselben Spalten ohne Korrektur und Begründung; sie hält die Beträge der GewSt 1 A, dazu Zeile 94 mit den Umsätzen, Löhnen und Gehältern, wo die Körperschaftsteuererklärung sie angibt, auch mit 0, und die Zeilen 148 und 150 mit den Vorträgen zum Schluss des vorangegangenen Erhebungszeitraums.

### Was das Speichern prüft

Das Speichern der Körperschaftsteuererklärung nimmt die Korrekturen und Zeilen von Hand, die Tabellen und die Angaben und prüft die Zeilen der Tabellen, bevor „Berechnen“ sie liest, wo eine Regel der Jahresdokumentation dahintersteht, mit ihrer Nummer:

- **§ 8b-Ergebnisse:** eine Art, die es gibt. Eine Veräußerung braucht ihren Zeitpunkt, Veräußerungspreis, Veräußerungskosten und Buchwert sind nicht negativ, und ihr Betrag ist der Preis abzüglich der Kosten und des Buchwerts, den das Speichern setzt: über 0 ein Gewinn, unter 0 ein Verlust, 0 lehnt es ab. Jede andere Zeile hat einen Betrag über 0, eine Teilwertabschreibung in vollen Euro; Aufwendungen sind nicht negativ.
- **Leistungen:** eine Art, die es gibt, ein Bruttobetrag über 0 in vollen Euro und eine bescheinigte Minderung des Einlagekontos in vollen Euro, nicht über dem Bruttobetrag. Der Tag des Abflusses ist Pflicht und liegt im Wirtschaftsjahr (Regel 8920296); eine offene Gewinnausschüttung braucht den Tag des Gewinnverteilungsbeschlusses (Regel 8920247), und der Abfluss liegt nicht vor ihm (Regel 8920298).
- **Einlagen:** eine Behandlung und eine Art, die es gibt, ein Betrag über 0 in vollen Euro, eine Sacheinlage mit ihrer Bezeichnung und der Tag der Einlage im Wirtschaftsjahr (Regel 8920293).
- **Steuerbescheinigungen und Zuwendungsbestätigungen:** anrechenbare Steuern nicht unter 0, ein Betrag laut Bestätigung über 0.
- **Angaben:** Verlustrücktrag, Umsätze, Löhne und Gehälter, Eigenkapital und Nennkapital in vollen Euro und, außer dem Eigenkapital, nicht unter 0; der Schlüssel der ergänzenden Angaben nur mit ihrem Text und der Text nur mit seinem Schlüssel, an beiden Erklärungen.

Die Anteile und die Steuerbefreiung der § 8b-Ergebnisse setzt das Speichern aus den Beteiligungen der Einstellungen. Ändert ein Speichern eine Tabelle oder eine Angabe eines berechneten Belegs, steht er auf „Berechnet“ mit dem Befund `SB-NEU-BERECHNEN`, bis „Berechnen“ ihn wieder prüft; an der Gewerbesteuererklärung ebenso, wenn sie eine andere Körperschaftsteuererklärung nennt oder sich ihre ergänzenden Angaben ändern.

## Tabellen der Körperschaftsteuererklärung

**§ 8b-Ergebnisse** (`holding_results`, Tabelle „Beteiligungsergebnis“): je Zeile die „Art des Ergebnisses“ (`kind`), die „Beteiligung“ (`holding_name`), der Betrag (`amount`) und bei Bezügen die Aufwendungen, die mit ihnen in unmittelbarem Zusammenhang stehen, „Aufwendungen nach § 8 Nr. 1 GewStG (BEG Zeile 8)“ (`financing_costs`) und „Übrige Aufwendungen (BEG Zeile 9)“ (`other_costs`). Eine Veräußerung nennt dazu den „Zeitpunkt der Veräußerung“ (`result_date`), den „Veräußerungspreis“ (`sale_price`), die „Veräußerungskosten“ (`sale_costs`) und den „Buchwert“ (`book_value`) der Anteile; ihren Betrag setzt das Speichern (§ 8b Abs. 2 Satz 2 KStG). Aus der Beteiligung der Einstellungen, die eine Zeile mit Bezügen mit ihrem Namen nennt, setzt das Speichern die „Beteiligung am 1. Januar“ (`percent_on_1_january`, § 8b Abs. 4 KStG), die „Beteiligung zu Beginn des Erhebungszeitraums“ (`percent_at_start_of_ez`, § 9 Nr. 2a und 7 GewStG) und die „Steuerbefreiung“ (`exemption`).

| Art | Was | Vordrucke |
|---|---|---|
| Bezüge | die Bezüge einer Beteiligung der Einstellungen, brutto vor Kapitalertragsteuer; die Steuerbefreiung ist „§ 8b Abs. 1 KStG“ ab 10 % am 1. Januar, sonst „Streubesitz“, mit dem Kennzeichen der Einstellungen „§ 8b Abs. 7 KStG“ | Anlage GK Zeilen 152 bis 155 für die befreiten, Anlage BEG |
| Veräußerung | eine Veräußerung von Anteilen mit Zeitpunkt, Preis, Kosten, Buchwert und dem Gewinn oder Verlust daraus, die Anlage GK zusammen angibt (Regel 8956041) | Anlage GK Zeilen 162 bis 165 mit 166 für einen Gewinn oder 166a für einen Verlust |
| Wertaufholung | eine Zuschreibung auf Anteile | Anlage GK Zeilen 167b und 167c |
| Teilwertabschreibung | eine Abschreibung oder andere Gewinnminderung auf Anteile, in vollen Euro | Anlage GK Zeilen 185 und 186 |

Die Summen der Anlage GK, die Zeilen 166b, 166c, 176 und 188, kommen aus den Büchern, ihre Einzelangaben aus dieser Tabelle (Regeln 8956070, 8956072, 8905507 und 8905516): Gewinne der Bücher brauchen eine Veräußerung mit Gewinn, Verluste eine mit Verlust. Eine Summe der Bücher ohne Einzelangabe hält die Erklärung an (`KST-8B-EINZELANGABEN`), ebenso Bezüge einer Beteiligung, die die Einstellungen für das Jahr nicht nennen (`KST-BETEILIGUNG-UNBEKANNT`), denn ohne ihre Beteiligung am 1. Januar ist offen, ob § 8b Abs. 4 KStG sie befreit.

**Steuerbescheinigungen** (`credits`, Tabelle „Anrechenbare Steuer“): je Steuerbescheinigung der „Aussteller der Steuerbescheinigung“ (`issuer`), das „Datum der Steuerbescheinigung“ (`certificate_date`), die einbehaltene „Kapitalertragsteuer“ (`capital_gains_tax`) und der „Solidaritätszuschlag“ darauf (`solz`). Ihre Summen sind Anlage WA Zeilen 2 und 3 (§ 36 Abs. 2 Nr. 2 EStG). Weicht die Kapitalertragsteuer von der als Aufwand gebuchten ab, die Anlage GK Zeile 83 wieder hinzurechnet, gibt die Erklärung den Hinweis `KST-KAPEST`.

**Zuwendungsbestätigungen** (`donations`, Tabelle „Zuwendungsbestätigung“): je Bestätigung der Empfänger (`recipient`), der „Betrag laut Bestätigung“ (`amount`) und „Empfänger im EU- oder EWR-Ausland“ (`abroad`). Sie sind Anlage Z Zeile 5 und GewSt 1 A Zeilen 92a bis 92c; Anlage Z Zeile 9 nennt die Summe der Bestätigungen von Empfängern im Ausland, auf volle Euro abgerundet (Regeln 8901015 und 8901017). Ihre Summe sind die Zuwendungen, die § 9 Abs. 1 Nr. 2 KStG in seinen Grenzen abzieht. Ohne Bestätigungen nimmt Anlage Z die Zuwendungen der Bücher ohne die Konten, die keine solchen sind: die steuerlich nicht abziehbaren und die an politische Parteien (SKR03 2380 und 2384, SKR04 6390 und 6394). Haben die Bücher solche und die Tabelle keine Zeile, hält die Erklärung an (`KST-ZUWENDUNGEN-BESTAETIGUNG`, § 50 Abs. 1 EStDV); weichen beide ab, gibt sie den Hinweis `KST-ZUWENDUNGEN-ABWEICHUNG`.

**Leistungen** (`distributions`, Tabelle „Ausschüttung“): je Leistung des Wirtschaftsjahres die „Art der Leistung“ (`kind`), der „Tag des Gewinnverteilungsbeschlusses“ (`resolution_date`), der „Tag des Abflusses“ (`outflow_date`), der „Bruttobetrag“ (`amount`) und die „Bescheinigte Minderung des Einlagekontos“ (`certified_reduction`), KSt 1 F Zeilen 3 bis 7 und 13. Jede Leistung gibt ihre bescheinigte Minderung an, auch 0 (Regel 8912016), und KSt 1 F Zeile 12 deren Summe, auch 0 (Regel 8920254).

| Art | Schlüssel in KSt 1 F Zeile 3 |
|---|---|
| Offene Gewinnausschüttung | 1 |
| Verdeckte Gewinnausschüttung | 2 |
| Abschlagszahlung auf das Liquidationsergebnis | 3 |

Die Schlüssel 4 und 5, Leistungen nach § 20 Abs. 1 Nr. 9 und 10 Buchst. a EStG und Entnahmen einer optierenden Gesellschaft, gibt es bei einer GmbH oder UG nicht (Regeln 8920316 und 8920051).

**Einlagen** (`contributions`, Tabelle „Einlage“): je Einlage der Anteilseigner (`shareholder`), der „Tag der Einlage“ (`contribution_date`), die „Behandlung“ (`treatment`), die „Art der Einlage“ (`kind`, Bareinlage oder Sacheinlage, KSt 1 F Zeile 205), bei einer Sacheinlage die „Bezeichnung der Sacheinlage“ (`description`) und der Betrag (`amount`).

| Behandlung | Anlage GK | KSt 1 F |
|---|---|---|
| Gewinnwirksam gebucht und geleistet | Zeile 93 | Zeile 91 und Zeilen 200 bis 206 |
| Gewinnwirksam gebucht, nicht geleistet | Zeile 94 | – |
| Nicht gewinnwirksam gebucht | Zeile 78 | Zeile 92 und Zeilen 200 bis 206 |
| Andere Einlage | – | Zeile 95 und Zeilen 200 bis 206, etwa eine Zahlung in die Kapitalrücklage |

Eine Einlage, die bis zum Schluss des Wirtschaftsjahres nicht geleistet ist, geht nicht in das Einlagekonto, denn § 27 Abs. 1 Satz 1 KStG zählt die „geleisteten Einlagen“. Das Einlagekonto beginnt mit dem bestätigten Vortrag der Einstellungen und dem Sonderausweis nach § 28 KStG; KSt 1 F geht mit jeder Erklärung, auch von 0 auf 0 (Regeln 8931022 und 8900709).

## Tabellen der Gewerbesteuererklärung

Die Tabellen der Gewerbesteuererklärung setzt „Berechnen“; ein Speichern ändert sie nicht.

**Gemeinde** (`municipalities`, Tabelle „Gemeinde der Gewerbesteuererklärung“): die „Gemeinde“ der einen Betriebsstätte im Erhebungszeitraum (`municipality`) mit „Postleitzahl“ (`postal_code`), „Amtlicher Gemeindeschlüssel“ (`ags`) und „Hebenummer“ (`hebenummer`) aus den Einstellungen, ihr „Hebesatz“ (`hebesatz`) mit der „Quelle des Hebesatzes“ (`hebesatz_source`), der „Steuermessbetrag“ (`messbetrag`), die „Gewerbesteuer“ (`gewst`), die „Vorauszahlungen“ (`prepayments`) und die „Abschlusszahlung oder Erstattung“ (`balance`), die alle auf sie fallen (§ 4 Abs. 1 GewStG). GewSt 1 A Zeilen 26 bis 33 nennen die eine Betriebsstätte, die im Jahr nicht verlegt wurde, mit Postleitzahl, Ort und Hebenummer.

**Anlagen BEG** (`holdings`, Tabelle „Anlage BEG“): je Beteiligung, deren Bezüge die Gewerbesteuer hinzurechnet oder kürzt, eine Anlage BEG mit der „Beteiligung“ (`holding_name`), der „Kürzung (BEG Zeile 7)“ (`paragraph`, „§ 9 Nr. 2a GewStG“ oder „§ 9 Nr. 7 GewStG“ ab 15 % zu Beginn des Erhebungszeitraums), den „Bezüge (BEG Zeile 6)“ (`dividends`), den „Aufwendungen nach § 8 Nr. 1 GewStG (BEG Zeile 8)“ (`financing_costs`) und den „Übrige Aufwendungen (BEG Zeile 9)“ (`other_costs`), den „Steuerfreie Bezüge (BEG Zeile 12)“ (`exempt`) und den „Übrige Bezüge (BEG Zeile 14)“ (`not_exempt`), der „Hinzurechnung nach § 8 Nr. 5 GewStG (BEG Zeile 15)“ (`addback`) und den Zeilen der Kürzung, „Bemessungsgrundlage der Kürzung (BEG Zeile 16)“ (`cut_base`), „Aufwendungen nach § 8 Nr. 1 GewStG (BEG Zeile 17)“ (`cut_financing_costs`), „Übrige Aufwendungen (BEG Zeile 18)“ (`cut_other_costs`) und „Kürzung (BEG Zeile 19)“ (`cut`). Streubesitz unter 10 %, den die Gewerbesteuer weder hinzurechnet noch kürzt, hat keine Anlage BEG.

## Befunde und „Bereit“

„Bereit“ heißt, wie an jeder Jahresmeldung: kein Fehler der Befunde. An der Körperschaftsteuererklärung verlangt das:

- kein Saldo auf einem Konto, dem die Vorgaben seines Kontenrahmens einen Platz in der Kontenzuordnung geben und die Zuordnung des Unternehmens nicht (die Konten mit den DATEV-Kennzeichen K und G), kein Saldo auf einem beobachteten Konto der Stufe „Sperrt“, kein Handelskonto ohne Klasse und kein Erfolgskonto ohne Nummer;
- vollständige Einstellungen Jahresmeldungen: Rechtsform, Ort der Geschäftsleitung und Ort des Sitzes, Anteilseigner, die an jedem Tag des Wirtschaftsjahres zusammen 99 bis 100 % halten (Regel 8931029 der KSt 1), mit höchstens drei Besitzzeiten je Anteilseigner im Wirtschaftsjahr;
- die Prüfung durch die Steuerberatung, deren Tag „KSt und GewSt geprüft am“ in den Einstellungen festhält, siehe [Prüfliste für die Steuerberatung](#prüfliste-für-die-steuerberatung);
- bestätigte Vorträge in vollen Euro;
- die Überleitung zur Steuerbilanz, wo die E-Bilanz oder, ohne sie, die Einstellungen eine Handelsbilanz mit Überleitungsrechnung halten, und neben der E-Bilanz keine Überleitung von Hand;
- eine E-Bilanz, deren Jahresüberschuss der der Bücher ist, die die Erklärung liest;
- die Regeln der Jahresdokumentation, die Steuerbote selbst prüft, ohne Fehler;
- Vordrucke, die nicht vorläufig sind, siehe [Vorläufige Vordrucke 2026](#vorläufige-vordrucke-2026);
- keine Salden auf ausländischen Steuern, etwa SKR03 2218 und 2219 (SKR04 7638 und 7639), und keine Ergebnisse aus Investmentfonds, bis eigene Module Anlage AESt und das Investmentsteuergesetz rechnen.

An der Gewerbesteuererklärung dazu: genau eine Betriebsstätte im Erhebungszeitraum, ein Hebesatz der Gemeinde für das Jahr mit seiner Quelle, Gegenstand des Unternehmens und Rechtsform. Jeden Fehler der Körperschaftsteuer, auf der sie aufbaut, übernimmt sie, die fehlende Prüfung durch die Steuerberatung eingeschlossen, außer dem der vorläufigen Vordrucke, den sie für sich selbst nennt.

| Code | Art | Woher |
|---|---|---|
| `KST-VORLAEUFIG`, `GEWST-VORLAEUFIG` | Fehler | die Vordrucke des Jahres sind vorläufig die der Jahresdokumentation 2025 |
| `KST-EINSTELLUNGEN-FEHLEN` | Fehler | das Unternehmen hat keine Einstellungen Jahresmeldungen |
| `KST-PRUEFUNG-FEHLT` | Fehler | die Einstellungen nennen keinen Tag, an dem eine Steuerberatung die Klassen der Handelskonten, den Status nach § 8b Abs. 7 KStG und die Prüfliste bestätigt hat |
| `KST-ANGABEN-FEHLEN` | Fehler | den Einstellungen fehlen Rechtsform, Ort der Geschäftsleitung oder Ort des Sitzes (KSt 1 Zeilen 6, 7 und 9) |
| `GEWST-ANGABEN-FEHLEN` | Fehler | den Einstellungen fehlen Gegenstand des Unternehmens oder Rechtsform (GewSt 1 A Zeilen 4 und 14) |
| `KST-ANTEILSEIGNER` | Fehler | an einem Tag des Wirtschaftsjahres halten die Anteilseigner der Einstellungen nicht 99 bis 100 % |
| `KST-BESITZDAUER` | Fehler | ein Anteilseigner hat mehr als drei Besitzzeiten im Wirtschaftsjahr; KSt 1 Zeilen 23 bis 23b nehmen drei |
| `KST-VORTRAG-UNBESTAETIGT`, `GEWST-VORTRAG-UNBESTAETIGT` | Fehler | ein Vortrag der Einstellungen ist nicht gegen seinen Bescheid bestätigt |
| `KST-VORTRAG-CENT`, `GEWST-VORTRAG-CENT` | Fehler | ein Vortrag hat Cent; die Erklärung nimmt ihn kaufmännisch auf volle Euro gerundet und nennt beide Beträge |
| `KST-UEBERLEITUNG-FEHLT` | Fehler | Handelsbilanz mit Überleitungsrechnung ohne Überleitung: eine E-Bilanz ohne Eintrag der Überleitung oder, ohne E-Bilanz, keine Zeile von Hand und keine Korrektur auf `E8002001` |
| `KST-UEBERLEITUNG-DOPPELT` | Fehler | Zeilen von Hand oder Korrekturen auf `E8002001` neben der Überleitung der E-Bilanz |
| `KST-EBILANZ-ABWEICHUNG` | Fehler, Hinweis | der Jahresüberschuss der E-Bilanz weicht um einen Euro oder mehr von dem der Bücher ab; ein Hinweis, wo die E-Bilanz ein anderes Finanzbuch liest als die Erklärung |
| `KST-EIGENKAPITAL-QUELLE` | Hinweis | woher KSt 1 F Zeilen 17 und 18 kommen: aus der abgegebenen E-Bilanz des Vorjahres oder von Hand |
| `KST-KONTO-OHNE-ZUORDNUNG` | Fehler | ein Konto mit Saldo, dem die Vorgaben einen Platz geben und die Zuordnung nicht |
| `KST-KONTO-OHNE-NUMMER` | Fehler | ein Erfolgskonto ohne Kontonummer mit Saldo |
| `KST-KONTO-OHNE-KATEGORIE` | Fehler | ein beobachtetes Konto der Stufe „Sperrt“ hat einen Saldo |
| `KST-KONTO-BEOBACHTET` | Hinweis | ein beobachtetes Konto der Stufe „Hinweis“ hat einen Saldo |
| `KST-HANDEL-OHNE-KLASSE` | Fehler | ein Handelskonto mit Saldo hat keine Klasse |
| `KST-AUSLAENDISCHE-STEUERN`, `KST-INVESTMENTFONDS` | Fehler | Salden auf ausländischen Steuern oder aus Investmentfonds |
| `KST-ZUWENDUNGEN-BESTAETIGUNG` | Fehler | abziehbare Zuwendungen in den Büchern ohne Zuwendungsbestätigung |
| `KST-ZUWENDUNGEN-ABWEICHUNG` | Hinweis | die Bestätigungen weichen von den Zuwendungen der Bücher ab |
| `KST-UMSATZ-FEHLT` | Fehler | die Zuwendungen übersteigen 20 % der Summe der Einkünfte, und Anlage Z Zeile 10 fehlt |
| `KST-8B-EINZELANGABEN` | Fehler | eine Summe der Anlage GK Zeilen 166b, 166c, 176 oder 188 ohne Einzelangabe in den § 8b-Ergebnissen |
| `KST-BETEILIGUNG-UNBEKANNT` | Fehler | Bezüge einer Beteiligung, die die Einstellungen für das Jahr nicht nennen |
| `KST-STREUBESITZ` | Hinweis | Bezüge der Bücher, die keiner Zeile „Bezüge“ der § 8b-Ergebnisse gehören, bleiben als Streubesitz steuerpflichtig |
| `KST-BEZUEGE-UEBER-HAUPTBUCH` | Fehler | die § 8b-Ergebnisse nennen mehr Bezüge, als die Bücher haben |
| `KST-8B-ABSATZ-7` | Hinweis | nach den Einstellungen gilt § 8b Abs. 7 KStG (KSt 1 Zeile 16) |
| `KST-VERLUSTRUECKTRAG-FEHLT` | Fehler | ein negativer Gesamtbetrag der Einkünfte ohne Entscheidung über den Verlustrücktrag (Regel 8900343) |
| `KST-VERLUSTRUECKTRAG-ZU-HOCH` | Fehler | der Verlustrücktrag ist höher als der Verlust oder der Höchstbetrag (Regel 8900124) |
| `KST-VERLUSTRUECKTRAG-OHNE-VERLUST` | Fehler | ein Verlustrücktrag ohne Verlust; die Erklärung lässt ihn weg |
| `KST-KAPEST` | Hinweis | die Kapitalertragsteuer der Steuerbescheinigungen weicht von der gebuchten ab |
| `KST-SOLZ-KAPEST` | Hinweis | der Solidaritätszuschlag der Steuerbescheinigungen weicht um mehr als 5 Cent von 5,5 % der Kapitalertragsteuer ab (Regel 8912019) |
| `KST-WA-VERTRAEGE` | Hinweis | Anlage WA Zeile 15 sagt ja; die Einzelangaben der Zeile 16 gibt Steuerbote nicht ab |
| `KST-VORAUSZAHLUNGEN`, `GEWST-VORAUSZAHLUNGEN` | Hinweis | die Vorauszahlungen der Einstellungen weichen von den gebuchten ab |
| `KST-BEWIRTUNG` | Hinweis | abzugsfähige Bewirtungskosten ohne nicht abzugsfähige |
| `KST-ZINSSCHRANKE` | Hinweis | die Zinsaufwendungen erreichen die Grenze der Zinsschranke, die Steuerbote nicht rechnet |
| `KST-IAB-HOECHSTBETRAG` | Fehler | die Investitionsabzugsbeträge übersteigen den Höchstbetrag (§ 7g Abs. 1 Satz 4 EStG) |
| `KST-IAB-GEWINNGRENZE` | Hinweis | der Gewinn ohne die Investitionsabzugsbeträge übersteigt die Gewinngrenze (§ 7g Abs. 1 Satz 2 Nr. 1 Buchst. b EStG) |
| `KST-EINLAGEKONTO-EIGENKAPITAL` | Fehler | Leistungen bei einem Bestand des Einlagekontos ohne Eigenkapital und Nennkapital des Vorjahres (Regel 8920011) |
| `KST-EINLAGEKONTO-MEHRERE-LEISTUNGEN` | Fehler | mehrere Leistungen mit bescheinigter Minderung des Einlagekontos, deren Abzug Steuerbote nicht rechnet |
| `GEWST-BETRIEBSSTAETTE` | Fehler | keine oder mehr als eine Betriebsstätte im Erhebungszeitraum |
| `GEWST-HEBESATZ-FEHLT` | Fehler | für die Gemeinde fehlt der Hebesatz des Jahres mit seiner Quelle |
| `GEWST-HEBESATZ-UNTER-MINDESTSATZ` | Fehler | der Hebesatz liegt unter dem Mindesthebesatz von § 16 Abs. 4 Satz 2 GewStG |
| `GEWST-BEG-FINANZIERUNGSANTEILE` | Hinweis | Aufwendungen nach § 8 Nr. 1 GewStG mindern die Kürzung einer Beteiligung; die Hinzurechnung der Anlage BEG Zeile 20 rechnet Steuerbote nicht |
| `KST-NUTZDATEN`, `GEWST-NUTZDATEN` | Fehler | die Vordrucke lassen sich nicht so schreiben, wie ELSTER sie nimmt |
| `SB-NEU-BERECHNEN` | Fehler | seit dem Berechnen hat sich etwas geändert, das „Berechnen“ liest |
| Fehlercode der Jahresdokumentation, etwa `8906062` oder `40000` | Fehler | eine der Regeln, die Steuerbote selbst prüft |

## Vorläufige Vordrucke 2026

ELSTER hat die Jahresdokumentationen E30 und E20 für 2026 noch nicht veröffentlicht: ERiC 44.3.6.0 kennt Körperschaft- und Gewerbesteuer bis 2025, und die ELSTER-Hilfe beschreibt beide Erklärungen bis 2025. Steuerbote nimmt für 2026 deshalb die Vordrucke, Felder, Regeln und Schemas von 2025 mit den Steuersätzen und Grenzen von 2026. Ob ERiC und die Formulare von Mein ELSTER eine Erklärung 2026 so nehmen, wie Steuerbote sie schreibt, ist damit nicht bekannt: Vordrucke, Zeilen, Felder und Regeln können sich ändern.

Entschieden ist deshalb: Solange die Vordrucke eines Jahres vorläufig sind, steht jede Erklärung des Jahres mit dem Fehler `KST-VORLAEUFIG` oder `GEWST-VORLAEUFIG` in den Befunden. „Bereit“ erreicht eine Erklärung 2026 damit nicht, bis ein Release von Steuerbote die Jahresdokumentationen 2026 übernimmt; dann entfällt der Befund mit dem nächsten „Berechnen“. Abgeben lässt sie sich vorher, wie jeder Beleg, der nicht bereit ist, nur mit Anmerkungen, die sagen, warum trotzdem, etwa weil die Steuerberatung den Ausdruck mit den Formularen von Mein ELSTER 2026 abgeglichen hat. Das Feld „Vorläufige Vordrucke“ zeigt den Stand, und beide Druckformate tragen unter dem Titel „vorläufig (Jahresdokumentation 2025)“.

## Rückstellungen vorschlagen

„Rückstellungen vorschlagen“ an einer berechneten oder abgegebenen Körperschaftsteuererklärung legt eine Journalbuchung im Entwurf an: für Körperschaftsteuer, Solidaritätszuschlag und Gewerbesteuer des Jahres je den Betrag, der nach Anrechnung und Vorauszahlungen bleibt (`steuerbote/kst/provisions.py`), zum letzten Tag des Wirtschaftsjahres, mit der Standardkostenstelle des Unternehmens. Für einen Betrag, den die Steuer schuldet, verlangt § 249 Abs. 1 Satz 1 HGB eine Rückstellung; ein negativer Betrag ist ein Erstattungsanspruch. Steuerbote bucht nichts: Das Unternehmen prüft die Journalbuchung und bucht sie selbst. Das Formular öffnet sie, und das Feld „Buchungsentwurf der Rückstellungen“ nennt sie.

| Steuer | SKR03: Aufwand, Rückstellung, Erstattungsanspruch | SKR04: Aufwand, Rückstellung, Erstattungsanspruch |
|---|---|---|
| Körperschaftsteuer | 2200, 0963 „Körperschaftsteuerrückstellung“, 1549 „Körperschaftsteuerrückforderung“ | 7600, 3040, 1450 |
| Solidaritätszuschlag | 2208, 0963, 1549 | 7608, 3040, 1450 |
| Gewerbesteuer | 4320, 0956 „Gewerbesteuerrückstellung nach § 4 Abs. 5b EStG“, 1540 „Forderungen aus Gewerbesteuerüberzahlungen“ | 7610, 3035, 1435 |

- **Je Steuer eine Soll- und eine Habenzeile:** eine Rückstellung im Soll auf dem Aufwand und im Haben auf der Rückstellung, ein Erstattungsanspruch im Soll auf dem Erstattungsanspruch und im Haben auf dem Aufwand, mit dem Vermerk „Rückstellung Körperschaftsteuer 2026“ oder „Erstattungsanspruch Körperschaftsteuer 2026“. Der Solidaritätszuschlag geht in die Rückstellung der Körperschaftsteuer, denn die DATEV-Kontenrahmen haben für ihn keine eigene.
- **Die Gewerbesteuer** rechnet „Rückstellungen vorschlagen“ wie die Gewerbesteuererklärung, auf der Körperschaftsteuer des Belegs; ohne Hebesatz der Gemeinde für das Jahr lässt es sie mit einem Hinweis weg.
- **Kein zweiter Vorschlag:** Steht die Journalbuchung des letzten Vorschlags noch im Entwurf, lehnt es einen neuen ab, bis sie gebucht oder gelöscht ist. Halten die Bücher des Wirtschaftsjahres schon Rückstellungen oder Erstattungsansprüche der Steuern, also Buchungen auf dem Aufwand einer Steuer in einem Beleg, der ihre Rückstellung oder ihren Erstattungsanspruch berührt, lehnt es den Vorschlag ab, denn er gälte dem ganzen Betrag des Jahres. Hat keine Steuer einen Betrag, legt es keine Journalbuchung an.
- **Konten:** Fehlt dem Unternehmen eines der Konten, nennt es die Nummern; ein eigener Kontenrahmen hat keine Vorgaben für sie.
- **Das zu versteuernde Einkommen bleibt:** Anlage GK Zeilen 81 bis 84 rechnen jede Steuer vom Einkommen wieder hinzu (§ 10 Nr. 2 KStG, § 4 Abs. 5b EStG). Nach dem Buchen ist der Jahresüberschuss um die Rückstellungen kleiner, Zeilen 81, 82 und 84 sind um sie größer, und „Berechnen“ ergibt dasselbe zu versteuernde Einkommen.

Im erfundenen Beispiel „Muster IT GmbH“ der Tests, einer GmbH mit SKR03, ergibt „Berechnen“ ein zu versteuerndes Einkommen von 111.200 €, Körperschaftsteuer 16.680,00 € und Solidaritätszuschlag 917,40 €, nach Vorauszahlungen und Kapitalertragsteuer zu zahlen 1.680,00 € und 92,40 €, und einen Gewerbeertrag von 107.600 € mit einem Messbetrag von 3.766 € und, bei einem Hebesatz von 400 %, 15.064,00 € Gewerbesteuer, nach den Vorauszahlungen 64,00 € zu zahlen. Der Vorschlag bucht 2200 an 0963 1.680,00 €, 2208 an 0963 92,40 € und 4320 an 0956 64,00 €; nach dem Buchen bleibt das zu versteuernde Einkommen 111.200 €.

## Aus der E-Bilanz

Die Körperschaftsteuererklärung nimmt Anlage GK Zeile 11 aus der E-Bilanz des Jahres und KSt 1 F Zeilen 17 und 18 aus der E-Bilanz des Vorjahres (Vertrag der Stufe 3, Abschnitt 3.3: „GK 11 from the E-Bilanz (is.netIncome ± Überleitung)“). Was sie von beiden liest, geben `income_tax_sources.ebilanz()` und `income_tax_sources.prior_ebilanz()` der Brücke als `EBilanz` und `PriorEBilanz`.

- **Welche E-Bilanz.** Das Feld „E-Bilanz“ nennt sie, und die Auswahl bietet nur E-Bilanzen des Jahresabschlusses desselben Unternehmens und Jahres, die nicht storniert sind. „Berechnen“ nimmt die genannte, solange sie berechnet, bereit oder abgegeben und nicht ersetzt ist, sonst die neueste solche (`ebilanz_sources.ebilanz_for_income_tax`), und schreibt sie ins Feld. Gibt es keine, bleibt das Feld leer, und Zeile 11 ist der Jahresüberschuss der Bücher wie ohne E-Bilanz. Eine Änderung des Felds stellt eine berechnete Erklärung auf „Berechnet“ mit `SB-NEU-BERECHNEN`, und eine Berichtigung beginnt mit der E-Bilanz der abgegebenen Erklärung, deren Berichtigung „Berechnen“ dann an ihre Stelle setzt. Die Gewerbesteuererklärung rechnet die Körperschaftsteuer mit der E-Bilanz, die die Körperschaftsteuererklärung nennt; ihre Zahlen übernimmt sie wie bisher.
- **Zeile 11.** „Jahresüberschuss/-fehlbetrag laut Handels- oder Steuerbilanz“, „bei Handelsbilanz: nach Berücksichtigung der Überleitungsrechnung nach § 5b Absatz 1 Satz 2 EStG beziehungsweise § 60 Absatz 2 EStDV“ (Jahresdokumentation E30 2025, `E8002001`): Zeile 11 nimmt den Jahresüberschuss der GuV der E-Bilanz, bei einer Handelsbilanz mit Überleitungsrechnung (HGBM) den der Handelsbilanz, und den Unterschied zum Jahresüberschuss ihrer Steuerbilanz nach der Überleitung als Zeile von Hand des Schritts mit der Begründung „Überleitungsrechnung der E-Bilanz …“ (`bridge.ueberleitung_lines`). Den Jahresüberschuss der Steuerbilanz rechnet der Kern der E-Bilanz aus den Einträgen der Überleitungsrechnung, mit dem steuerlichen Ausgleichsposten und dem Sammelposten der GuV. In der Zeile `E8002001` zeigt „Betrag laut Hauptbuch“ dann den Jahresüberschuss der Handelsbilanz, „Betrag laut Vordruck“ den nach der Überleitung. Eine Einheitsbilanz (HAOE) und eine Steuerbilanz (AO) haben keine Überleitung.
- **Abgleich mit den Büchern.** Die übrigen Zeilen der Anlage GK kommen aus den Büchern, etwa die Steuern der Zeilen 81 bis 84. Weicht der Jahresüberschuss der E-Bilanz um einen Euro oder mehr von dem der Gewinn- und Verlustrechnung ab, die die Erklärung liest, hält `KST-EBILANZ-ABWEICHUNG` sie an: Dann ist gebucht worden, seit die E-Bilanz berechnet ist, etwa die Rückstellungen, oder eine Korrektur der E-Bilanz ändert eine Position der GuV. Liest die E-Bilanz ein anderes Finanzbuch als die Erklärung, etwa eine Steuerbilanz (AO) das der Steuerbilanz, ist der Unterschied nur ein Hinweis. Unter einem Euro bleibt er die Rundung der Zeile, die volle Euro meldet.
- **Die Überleitung einmal.** Neben der E-Bilanz nimmt Zeile 11 keine Zeile von Hand und keine Korrektur, denn sie zählten die Überleitung ein zweites Mal (`KST-UEBERLEITUNG-DOPPELT`); jeder Schritt der Überleitung gehört in die Überleitungsrechnung der E-Bilanz. Ob eine Überleitung nötig ist, sagt dann der Bilanzierungsstandard der E-Bilanz, nicht der der Einstellungen: Eine Handelsbilanz ohne Eintrag der Überleitung hält die Erklärung an (`KST-UEBERLEITUNG-FEHLT`, § 60 Abs. 2 Satz 1 EStDV).
- **KSt 1 F Zeilen 17 und 18.** Das „Eigenkapital laut Steuerbilanz“ und das „Nennkapital“ zum Schluss des vorangegangenen Wirtschaftsjahres, aus denen das steuerliche Einlagekonto den ausschüttbaren Gewinn rechnet (§ 27 Abs. 1 Satz 5 KStG), kommen aus der E-Bilanz des Vorjahres, die abgegeben ist und die keine Berichtigung ersetzt hat: ihr Betriebsvermögen der Steuerbilanz (`ebilanz_sources.filed_tax_equity`) und ihr gezeichnetes Kapital der Steuerbilanz, die Position `bs.eqLiab.equity.subscribed` (`ebilanz_sources.subscribed_capital`), beide kaufmännisch auf die vollen Euro gerundet, die die Zeilen melden. Ohne eine solche E-Bilanz gelten die Beträge von Hand wie bisher. Der Hinweis `KST-EIGENKAPITAL-QUELLE` sagt, woher die Zeilen kommen, und nennt Beträge von Hand, die neben der E-Bilanz nicht zählen.
- **Rückstellungen und E-Bilanz.** Nach dem Buchen der vorgeschlagenen Rückstellungen erst die E-Bilanz neu berechnen, dann die Körperschaftsteuererklärung: Zeile 11 ist um die Rückstellungen kleiner, die Zeilen 81, 82 und 84 sind um sie größer, und das zu versteuernde Einkommen, die Körperschaftsteuer und der Solidaritätszuschlag bleiben. Wer die Erklärung vor der E-Bilanz neu berechnet, sieht `KST-EBILANZ-ABWEICHUNG`.

## Abgabe

- **Fälligkeit:** der Tag, den „Offene Fristen“ für die Erklärung des Jahres nennt (`annual_deadline`, siehe [Fristen](fristen.md#jahresmeldungen)): sieben Monate nach Ablauf des Jahres, mit Steuerberatung der letzte Tag im Februar des zweiten Folgejahres, bei einer Vorabanforderung der früheste Tag der Vorabanforderungen des Jahres, verschoben auf den nächsten Werktag (§ 149 Abs. 2 bis 4 und § 108 Abs. 3 AO). Für 2026 ist das der 02.08.2027, mit Steuerberatung der 29.02.2028.
- **Über ERiC:** Prüfen, Testsenden und Senden in der Datenart KSt oder GewSt des Jahres (`datenart.kst`, `datenart.gewst`) mit den Nutzdaten E30 aus `steuerbote/elster/kst_xml.py` und E20 aus `steuerbote/elster/gewst_xml.py`, mit dem Vorsatz, Vorgang 01 und ohne Bereitstellung der Bescheiddaten (Bescheid 2). Ohne Hersteller-ID läuft das als Simulation: Sie prüft Aufbau und Regeln; ein Schema für 2026 hat sie nicht und sagt das in einem Hinweis. Senden geht erst mit einer Laufzeitumgebung, die das Plugin des Jahres mitbringt (`checkKSt_2026`, `checkGewSt_2026`; ERiC 44.3.6.0 kennt beide Datenarten bis 2025), und der Hersteller-ID.
- **In Mein ELSTER:** Mein ELSTER importiert keine Körperschaftsteuererklärung und keine Gewerbesteuererklärung, es nimmt hochgeladene Formulardaten nur für die Voranmeldung und die Mitteilung nach § 146a Abs. 4 AO. Die Erklärungen werden dort nach den Druckformaten eingegeben und mit „In Mein ELSTER abgegeben“ vermerkt; die Formulare sagen das im Hinweis der Simulation und an einer bereiten Erklärung.
- **Auf anderem Weg,** etwa durch die Steuerberatung: „Als außerhalb abgegeben vermerken“ mit „Wie und wann abgegeben“.

### Berichtigung

Kein Feld kennzeichnet eine Berichtigung der Körperschaft- oder Gewerbesteuererklärung; sie ist eine neue, vollständige Erklärung, die der qualifizierte Freitext in KSt 1 Zeile 13 oder GewSt 1 A Zeile 21 erklären kann, siehe [Berichtigung](jahresmeldungen.md#berichtigung). „Berichtigung anlegen“ an einer abgegebenen Körperschaftsteuererklärung legt sie mit den Korrekturen, Zeilen von Hand, Angaben und Tabellen der abgegebenen an und berechnet sie sofort; an einer abgegebenen Gewerbesteuererklärung mit den ergänzenden Angaben und dem Entwurf der Körperschaftsteuererklärung des Jahres oder, ohne Entwurf, der zuletzt abgegebenen, die keine Berichtigung ersetzt hat. Abgegeben, setzt eine Berichtigung die frühere auf „Ersetzt“. Eine abgegebene Erklärung wird nie storniert.

## Druckformate

Die Druckformate „Körperschaftsteuererklärung“ und „Gewerbesteuererklärung“ geben jede Erklärung in Reihenfolge und Wortlaut ihrer Vordrucke aus, auf A4, schwarz und grau, als Vorlage für Mein ELSTER oder die Steuerberatung:

- **Kopf:** der Kopf der Jahresmeldungen mit Finanzamt und Vorgang „01 Veranlagung“, an der Gewerbesteuererklärung dazu die Körperschaftsteuererklärung, auf der sie aufbaut. Unter dem Titel steht „vorläufig (Jahresdokumentation 2025)“, solange die Vordrucke vorläufig sind, und an einer Berichtigung „Berichtigung, eine neue und vollständige Erklärung“.
- **Vordrucke:** je Vordruck, den die Erklärung abgibt, ein Abschnitt in der Reihenfolge der Jahresdokumentation: KSt 1, Anlage GK, Anlage ZVE, Anlage Z, Anlage Verluste, Anlage WA und KSt 1 F; GewSt 1 A und je Beteiligung eine Anlage BEG. Jede Zeile zeigt Zeile, Bezeichnung, Nr. und Wert. Die Bezeichnung ist die Beschreibung des Felds in der Jahresdokumentation, die sie auch als Drucktext führt, mit dem Jahr der Erklärung, wo die Jahresdokumentation einen Platzhalter für das Jahr hat; Nr. zählt, was sich wiederholt, etwa „1.2“ für die zweite Besitzzeit des ersten Anteilseigners. Volle Euro stehen als 1.234, Beträge mit Cent als 1.234,56, andere Zahlen wie Prozentsätze mit ihren Nachkommastellen, Ja-Nein-Felder als „Ja“ oder „Nein“, Tage als TT.MM.JJJJ, ein Tag ohne Jahr als TT.MM., und der Wert eines Listenfelds als sein Schlüssel; ein Feld, das nur ein Ja kennt, steht bei nein nicht da. Die Abschnitte gibt `income_tax_print()` des Belegs mit `print_sections()` aus `corporate_income_tax_return/layout.py`, aus denselben Vordrucken, die in die Nutzdaten gehen.
- **Ohne die Nummern der Anteilseigner:** Steuernummer, Identifikationsnummer, W-IdNr. und ausländisches Identifikationsmerkmal der Anteilseigner gehen an ELSTER und in keinen Ausdruck, denn eine andere Stelle als die Finanzbehörde darf die Identifikationsnummer nur verarbeiten, soweit eine Übermittlung an sie es verlangt (§ 139b Abs. 2 Satz 2 Nr. 1 AO).
- **Darunter:** die Berechnung mit den Feldern des Belegs, an der Gewerbesteuererklärung mit der Gemeinde, dem Amtlichen Gemeindeschlüssel und der Quelle des Hebesatzes, an der Körperschaftsteuererklärung die Korrekturen und Zeilen von Hand, dann die Befunde, die Anmerkungen und der Hinweis, dass der Ausdruck keine Abgabe ist.

Das Druckformat rechnet nichts. Es ist das Standard-Druckformat seines Belegs, über den Property Setter in `steuerbote/fixtures/property_setter.json`.

## Bericht „Ertragsteuer-Kontennachweis“

Der Bericht zeigt für ein Unternehmen und ein Jahr, aus welchen Buchungen jede Zeile der beiden Erklärungen besteht. Er liest dasselbe wie „Berechnen“: die Gewinn- und Verlustrechnung des Wirtschaftsjahres, das im Jahr endet, und die Kontenzuordnung Ertragsteuern (`report/ertragsteuer_kontennachweis/attribution.py`, ohne Frappe).

- **Anlage GK Zeile 11** mit jedem Erfolgskonto, seinem Soll, seinem Haben und seinem Saldo, Haben abzüglich Soll, und darunter zusammen den „Konten ohne Kontonummer“.
- **Jede Zeile, deren Betrag aus Kategorien der Zuordnung kommt,** einmal je Satz von Kategorien, etwa Anlage GK Zeile 81 oder GewSt 1 A Zeile 50, mit Vordruck, Zeile und Feldkennung, dem Betrag der Bücher in der Richtung ihrer Kategorien (ein Aufwand Soll abzüglich Haben, ein Ertrag Haben abzüglich Soll), darunter jedes Konto und darunter jeder Beleg mit Buchungsdatum, Belegtyp und Belegnr.
- **Der Betrag ist der der Bücher,** vor der Rechnung: Anlage GK Zeile 156 zeigt alle Bezüge der Kategorie, von denen § 8b KStG einen Teil befreit, und Korrekturen und Zeilen von Hand erscheinen nicht.
- Rollen wie bei den Belegen: Accounts Manager, Accounts User und System Manager. Bezeichnungen und Feldkennungen zeigt der Bericht als Text, nie als HTML.

## Prüfliste für die Steuerberatung

Steuerbote ersetzt keine Steuerberatung. Vor der ersten Erklärung, die abgegeben wird, prüft die Steuerberatung für das Unternehmen diese Punkte; den Tag hält „KSt und GewSt geprüft am“ in den Einstellungen Jahresmeldungen fest, mit einem Vermerk. Bis der Tag dort steht, hält jede Körperschaft- und Gewerbesteuererklärung an (`KST-PRUEFUNG-FEHLT`).

1. **Handelskonten.** Die Klasse jedes Kontos mit Handelsergebnissen: Anteile (§ 8b KStG), Termingeschäfte (§ 15 Abs. 4 Satz 3 EStG), Investmentfonds oder voll steuerpflichtig. Dass jeder CFD ein Termingeschäft ist, ist ungeprüft. Dazu die Verrechnung von Gewinnen und Verlusten aus Termingeschäften innerhalb des Jahres.
2. **§ 8b KStG.** Ob § 8b Abs. 7 KStG gilt (KSt 1 Zeile 16); Wertpapierleihe und Kompensationszahlungen (§ 8b Abs. 10 KStG); ausländische Quellensteuer (§ 26 KStG, Anlage AESt).
3. **Verdeckte Gewinnausschüttungen.** Bezüge und Tantieme der Gesellschafter-Geschäftsführung (etwa SKR03 4126, SKR04 6026), Darlehen von Gesellschaftern und ihre Zinsen (2114 und 2117, SKR04 7316 und 7317), Vergütungen an Gesellschafter für überlassene Wirtschaftsgüter (4222 und 4958, SKR04 6313 und 6833) und die private Nutzung von Fahrzeugen.
4. **Überleitung.** Von der Handels- zur Steuerbilanz, die dauernde Wertminderung einer Teilwertabschreibung (§ 6 Abs. 1 Nr. 2 Satz 2 EStG) und offene Positionen zum Schluss des Wirtschaftsjahres, etwa eine Rückstellung für drohende Verluste, die die Steuerbilanz nicht kennt (§ 5 Abs. 4a EStG), und Bewertungseinheiten (§ 5 Abs. 1a EStG).
5. **Grundlagen.** Die Kontenzuordnung Ertragsteuern, die Eröffnungswerte in den Einstellungen (Einlagekonto, Sonderausweis, Verlustvortrag, Fehlbetrag und Zuwendungsvorträge), die Betriebsstätten, auch ob ein Arbeitszimmer in der Wohnung der Geschäftsführung eine Betriebsstätte der GmbH ist (§ 12 AO), und der Hebesatz mit seiner Quelle.
6. **Die ersten Erklärungen,** bevor sie abgegeben werden: der Ausdruck neben dem, was die Steuerberatung selbst rechnet.

## Grenzen

- Die Vordrucke 2026 sind vorläufig die von 2025, siehe [Vorläufige Vordrucke 2026](#vorläufige-vordrucke-2026).
- Eine Betriebsstätte in einer Gemeinde; keine Zerlegung (GewSt 1 D). Keine oder mehrere Betriebsstätten halten die Gewerbesteuererklärung an.
- Keine Organschaft, keine Anlage AESt und kein Investmentsteuergesetz: Salden auf ausländischen Steuern (SKR03 2218 und 2219, SKR04 7638 und 7639) und aus Investmentfonds halten die Erklärung an.
- Ein Wirtschaftsjahr je Jahr: Anlage GK und KSt 1 F für ein zweites Wirtschaftsjahr, etwa bei der Umstellung des Wirtschaftsjahres, gibt Steuerbote nicht ab.
- Anlage GK Zeile 11 kommt aus der E-Bilanz des Jahres, ohne sie aus dem Hauptbuch mit der Überleitung von Hand; KSt 1 F Zeilen 17 und 18 kommen aus der abgegebenen E-Bilanz des Vorjahres, ohne sie von Hand. Das Finanzbuch der Steuerbilanz liest die Erklärung nur über die E-Bilanz.
- Von Anlage WA gibt Steuerbote die Zeilen 2, 3 und 15 ab; die Einzelangaben der Zeile 16 nicht.
- Je Anteilseigner höchstens drei Besitzzeiten im Wirtschaftsjahr, wie das Schema sie zulässt; mehr halten die Erklärung an (`KST-BESITZDAUER`).
- Leistungen nur der Arten 1 bis 3 von KSt 1 F Zeile 3, wie eine GmbH oder UG sie erbringt.
- Der Verlustrücktrag geht in die Erklärung des Jahres; die Erklärung des Vorjahres berichtigt Steuerbote nicht.
- Die Gewerbesteuererklärung nimmt keine Korrektur: Was an ihr anders sein soll, gehört an die Körperschaftsteuererklärung oder in die Kontenzuordnung.
- Die Hinzurechnung der Anlage BEG Zeile 20 und die Zinsschranke rechnet Steuerbote nicht.
- Erklärte Beträge in vollen Euro rundet der Kern kaufmännisch, wo die Jahresdokumentation keine Richtung nennt; ob ELSTER das so erwartet, ist nicht bestätigt.
- Mein ELSTER nimmt keine Datei der Erklärungen; sie werden dort nach dem Druckformat eingegeben.

## Quellen

- KStG §§ 1, 7, 8, 8b, 9, 10, 23, 27, 28, 31; EStG §§ 4 Abs. 5b, 5 Abs. 1a und 4a, 6 Abs. 1 Nr. 2, 7g, 10d, 15 Abs. 4, 36 Abs. 2, 37; EStDV §§ 50, 60 Abs. 2; SolZG §§ 3, 4; GewStG §§ 4, 7, 8, 9, 10a, 11, 14a, 16, 19, 28 bis 31; AO §§ 10, 11, 12, 108, 139b, 146a Abs. 4, 149, 150 Abs. 7; HGB § 249, gelesen am 23.11.2026 auf gesetze-im-internet.de; R 7.1 Abs. 4 und R 14.1 GewStR 2009 (Amtliches Gewerbesteuer-Handbuch 2024).
- ERiC-Dokumentation 44.3.6.0: Jahresdokumentation E30 2025 (Versionslabel 7.0), Blätter „Allg. Information“, „KSt1 - Felder“, „GK - Felder“, „ZVE - Felder“, „Z - Felder“, „Verluste - Felder“, „WA - Felder“, „KSt1F - Felder“ und die Regeln dieser Vordrucke; Jahresdokumentation E20 2025 (Versionslabel 11.0), Blätter „GewSt1A - Felder“, „BEG - Felder“ und ihre Regeln; die Schemas `E30-2025.xsd` und `E20-2025.xsd`; Entwicklerhandbuch Tabelle 2-12 (die Datenarten und Jahre, die ERiC kennt).
- ELSTER-Hilfe „Formulare“ (KSt und GewSt bis 2025) und „Benutzeranleitung zum Hochladen von Formulardaten“, Abschnitt „Allgemeines“ (<https://www.elster.de/eportal/helpGlobal?themaGlobal=ustva_upload>).
- DATEV-Kontenrahmen 2026, SKR 03 (Art.-Nr. 11174) und SKR 04 (Art.-Nr. 11175): die Konten der Steuern vom Einkommen, ihrer Rückstellungen und Erstattungsansprüche.
