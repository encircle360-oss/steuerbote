# E-Bilanz

Eine GmbH oder UG übermittelt den Inhalt ihrer Bilanz und ihrer Gewinn- und Verlustrechnung nach amtlich vorgeschriebenem Datensatz an das Finanzamt (§ 5b Abs. 1 Satz 1 EStG), im Jahr ihrer Gründung auch den der Eröffnungsbilanz (§ 5b Abs. 1 Satz 4 EStG). Der Datensatz ist die [HGB-Taxonomie](taxonomie.md). Steuerbote berechnet die E-Bilanz als Beleg „E-Bilanz“ (`Electronic Balance Sheet`) aus dem Hauptbuch, den Anlagen, der Bilanzzuordnung und den Einstellungen Jahresmeldungen, prüft sie mit den Regeln der Taxonomie, druckt sie mit Bilanz, GuV, Betriebsvermögensvergleich, Anlagenspiegel, Kontennachweis und Überleitungsrechnung und gibt sie über ERiC ab. Bis Steuerbote eine Hersteller-ID hat, läuft die Übermittlung als Simulation; Mein ELSTER nimmt keine E-Bilanz an, die Datei von „XBRL exportieren“ geht dann an die Steuerberatung, und „Als außerhalb abgegeben vermerken“ hält die Abgabe fest. Diese Seite ersetzt keine Steuerberatung.

Der Beleg lebt auf der Grundlage der Jahresmeldungen: Status, Berechnen, Korrekturen und Zeilen von Hand, Befunde, Abgabe, Berichtigung und Übermittlung sind die aller Jahresmeldungen und stehen in [Jahresmeldungen](jahresmeldungen.md). Den Kern unter `steuerbote/ebilanz`, der die Positionen, Summen, Überleitung, Anlagenspiegel und Instanz rechnet, nennt die [Architektur](architektur.md#e-bilanz), die Datenart und die Simulation [ERiC](eric.md#erklärungen-und-e-bilanz).

## Umfang

- **Unternehmen:** eine GmbH oder UG (haftungsbeschränkt), wie die Einstellungen Jahresmeldungen sie nennen, mit einer Bilanzzuordnung, für SKR03 und SKR04 aus den Vorgaben, für einen eigenen Kontenrahmen von Hand.
- **Bilanzart:** der Jahresabschluss eines Wirtschaftsjahres und die Eröffnungsbilanz des Gründungsjahres.
- **Bilanzierungsstandard:** die Einheitsbilanz (HAOE), die Handelsbilanz mit Überleitungsrechnung (HGBM) oder die Steuerbilanz (AO), Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025 („Leitfaden“), B.13.
- **Taxonomie:** 6.9, für die Wirtschaftsjahre 2025 bis 2027, siehe [Versionen](taxonomie.md#versionen).
- **Wirtschaftsjahr:** das Geschäftsjahr von ERPNext, das im Jahr endet. Wie ERPNext nimmt der Beleg ein Geschäftsjahr, das das Unternehmen nennt, vor einem für alle Unternehmen, so dass ein kurzes erstes Wirtschaftsjahr neben dem Kalenderjahr der übrigen Unternehmen seine E-Bilanz hat; genau eines muss es geben.
- **Nicht darin:** Vorjahreswerte, denn eine Steuerbilanz meldet keine; Ergänzungs- und Sonderbilanzen und die Kapitalkontenentwicklung von Personengesellschaften; die GuV im Umsatzkostenverfahren; die Handelsbilanz aus dem Beleg „Jahresabschluss“, siehe [Grenzen](#grenzen).

## Der Beleg

Je Unternehmen, Jahr und Bilanzart ein Beleg, benannt nach dem Jahr, für das er gilt (`EB-2026-00001`). Jeder weitere Beleg desselben Schlüssels ist eine Berichtigung, siehe [Berichtigung](#berichtigung).

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company`, `year` | Unternehmen, Jahr | Pflicht; das Jahr ist das, in dem das Wirtschaftsjahr endet |
| `statement_type` | Bilanzart | Jahresabschluss (Vorgabe) oder Eröffnungsbilanz; die Eröffnungsbilanz zeigt die Bilanz am ersten Tag des Wirtschaftsjahres, ohne GuV und Betriebsvermögensvergleich |
| `fiscal_year`, `from_date`, `to_date`, `status`, `ready`, `deadline`, `is_correction`, `corrects`, `transmission_in_progress`, `findings`, `filed_via`, `filed_on`, `transferticket`, `filed_by`, `filing_note`, `remarks` | | die Felder jedes Belegs einer Jahresmeldung, siehe [Felder jedes Belegs](jahresmeldungen.md#felder-jedes-belegs) |
| `revision_status` | Status des Berichts | setzt Steuerbote für die erste E-Bilanz auf E (erstmalig); eine Berichtigung nennt B (berichtigt), G (geändert), BG (berichtigt und geändert), sK (sonstige Korrektur) oder I (identischer Abschluss mit differenzierteren Informationen), siehe [Berichtigung](#berichtigung) |
| `stichtag` | Bilanzstichtag | setzt jedes Speichern: das Ende des Wirtschaftsjahres, bei einer Eröffnungsbilanz sein erster Tag |
| `accounting_standard` | Bilanzierungsstandard | HAOE (Vorgabe), HGBM oder AO; das Formular einer neuen E-Bilanz übernimmt den der Einstellungen Jahresmeldungen |
| `taxonomy_version` | HGB-Taxonomie | die Version, deren Positionen die E-Bilanz meldet: die gewählte, solange das Wirtschaftsjahr sie nehmen darf, sonst die, die es grundsätzlich nimmt, 6.9 für 2026 und 6.10 von 2027 an; die Bilanzzuordnung nennt dieselbe |
| `first_fiscal_year` | Gründungsjahr | setzt „Berechnen“: Das Gründungsdatum des Unternehmens liegt im Wirtschaftsjahr. Vor ihm gab es kein Betriebsvermögen und kein Anlagevermögen |
| `annual_accounts` | Jahresabschluss | setzen eine neue E-Bilanz und jedes „Berechnen“: der Jahresabschluss des Unternehmens und Jahres, der festgestellte oder sonst sein Entwurf, mit dem „Berechnen“ die Handelsbilanz vergleicht, siehe [Vergleich mit dem Jahresabschluss](#vergleich-mit-dem-jahresabschluss); eine Eröffnungsbilanz nennt keinen |
| `commercial_finance_book` | Finanzbuch der Handelsbilanz | das Finanzbuch der Handelsbilanz und der Einheitsbilanz; leer die Buchungen ohne Finanzbuch. Eine neue E-Bilanz übernimmt das der Einstellungen Jahresmeldungen |
| `tax_finance_book` | Finanzbuch der Steuerbilanz | das Finanzbuch der Steuerbilanz: bei AO die Bücher der E-Bilanz, bei HGBM die Quelle der Überleitungsrechnung; ebenso aus den Einstellungen |
| `positions` | Positionen | Tabelle „Position der E-Bilanz“, siehe [Positionen](#positionen-korrekturen-und-zeilen-von-hand) |
| `total_assets`, `total_equity_and_liabilities` | Summe Aktiva, Summe Passiva | setzt „Berechnen“, wie alle Felder des Abschnitts „Summen“ |
| `net_income` | Jahresüberschuss/Jahresfehlbetrag | der der GuV, bei HGBM der Handelsbilanz |
| `tax_net_income` | Jahresüberschuss/Jahresfehlbetrag der Steuerbilanz | nach der Überleitungsrechnung; von ihm geht die Körperschaftsteuererklärung aus |
| `tax_equity` | Betriebsvermögen der Steuerbilanz | das Eigenkapital abzüglich des „nicht durch Eigenkapital gedeckten Fehlbetrags“ am Bilanzstichtag (Regel 170405114) |
| `bvv_previous_equity` | Betriebsvermögen zum Ende des vorangegangenen Wirtschaftsjahres | setzt „Berechnen“, siehe [Betriebsvermögensvergleich](#betriebsvermögensvergleich) |
| `bvv_previous_equity_override`, `bvv_previous_equity_reason` | Betriebsvermögen des Vorjahres laut Unternehmen, Begründung des Betriebsvermögens des Vorjahres | ein anderer Betrag, etwa der eines Bescheids; nur mit Begründung |
| `bvv_founding_contribution` | Einlagen bei der Gründung | setzt „Berechnen“: im Gründungsjahr das Eigenkapital der Eröffnungsbilanz |
| `bvv_contributions`, `bvv_withdrawals`, `bvv_capital_adjustments` | Weitere Einlagen, Entnahmen und Ausschüttungen, Kapitalanpassung | was der Betriebsvermögensvergleich über die Bücher hinaus nimmt |
| `fixed_assets` | Anlagenspiegel | Tabelle „Zeile des Anlagenspiegels der E-Bilanz“, siehe [Anlagenspiegel](#anlagenspiegel) |
| `transfers` | Überleitungsrechnung | Tabelle „Eintrag der Überleitungsrechnung“, nur bei HGBM, siehe [Überleitungsrechnung](#überleitungsrechnung) |
| `accounts` | Kontensalden | Tabelle „Kontensaldo der E-Bilanz“, die „Berechnen“ füllt: der Kontennachweis mit der Position (`position`), der Bezeichnung der Position (`position_label`), dem Konto (`account`), der Kontonummer (`account_number`), der Kontobezeichnung (`account_label`) und dem Kontosaldo in der Richtung der Position (`amount`) |

Rechte wie bei der Voranmeldung: System Manager und Accounts Manager legen an, berechnen, ändern und geben ab; ein Accounts User legt an, berechnet und ändert, gibt aber nicht ab. Die Liste steht als „E-Bilanzen“ in der Seitenleiste in der Gruppe „Jahresmeldungen“ und im gleichnamigen Abschnitt des Arbeitsbereichs „Steuern“, dort neben „Neue E-Bilanz“; der Bericht „E-Bilanz Positionen“ steht in der Gruppe „Berichte“.

## Berechnen

„Berechnen“ liest die Quellen des Wirtschaftsjahres (`steuerbote/ebilanz_sources.py`) und rechnet mit dem Kern (`compute` in `electronic_balance_sheet.py`, über `electronic_balance_sheet/bridge.py`):

1. **Fall:** die Rechtsform der Einstellungen Jahresmeldungen, das Wirtschaftsjahr, die Bilanzart und der Bilanzierungsstandard (`bridge.case_of`). Auf der steuerlichen Ansicht der eingerichteten Taxonomie gibt `steuerbote.ebilanz.positions.structure()` daraus die Positionen, die die E-Bilanz meldet. Ohne eingerichtete Taxonomie rechnet „Berechnen“ nicht.
2. **Bücher:** die Salden des Hauptbuchs aus `steuerbote/balances.py`, für einen Jahresabschluss die Konten der Bilanz bis zum Bilanzstichtag und die der GuV des Wirtschaftsjahres ohne seinen Periodenabschlussbeleg, für eine Eröffnungsbilanz die Bilanz am ersten Tag. Gelesen wird das Finanzbuch der Bilanz: bei HAOE und HGBM das der Handelsbilanz, bei AO das der Steuerbilanz (Leitfaden B.13), mit seinen Buchungen und denen ohne Finanzbuch.
3. **Bilanzzuordnung:** setzt jeden Saldo auf seine Position, mit dem Abschlusszweck der Bilanzart, und gibt die „davon“-Positionen als Zeilen von Hand (`steuerbote/balance_mapping_sync.py`); was sie nicht unterbringt, nennt sie in den Befunden.
4. **Anlagenspiegel:** aus dem Bericht „Asset Depreciations and Balances“ von ERPNext, siehe [Anlagenspiegel](#anlagenspiegel).
5. **Überleitungsrechnung:** bei HGBM aus dem Finanzbuch der Steuerbilanz und von Hand, siehe [Überleitungsrechnung](#überleitungsrechnung).
6. **Betriebsvermögensvergleich und GCD:** das Betriebsvermögen des Vorjahres und die Angaben des Belegs, siehe [Betriebsvermögensvergleich](#betriebsvermögensvergleich), und die Stammdaten der GCD aus den Einstellungen Jahresmeldungen: Name, Anschrift mit Hausnummer, die Steuernummer für Körperschaftsteuer und E-Bilanz im ELSTER-Format, der Gegenstand des Unternehmens, der Status des Berichts und das vorangegangene Geschäftsjahr, im Gründungsjahr keines (Leitfaden B.18).
7. **Kern:** `steuerbote.ebilanz.instance.build()` rechnet Positionen und Summen, Überleitung, Betriebsvermögensvergleich, Anlagenspiegel und Kontensalden und schreibt die Instanz. `bridge.py` bringt das Ergebnis in die Tabellen und Felder des Belegs.
8. **Jahresabschluss:** die Handelsbilanz neben der des Jahresabschlusses des Jahres, siehe [Vergleich mit dem Jahresabschluss](#vergleich-mit-dem-jahresabschluss).

Eine Änderung an dem, was „Berechnen“ liest, an einer berechneten E-Bilanz, also am Bilanzierungsstandard, an der Taxonomie, an einem Finanzbuch, an den Angaben des Betriebsvermögensvergleichs, an einer Spalte oder Zeile von Hand des Anlagenspiegels oder an einem Eintrag von Hand der Überleitung, setzt sie auf „Berechnet“ mit dem Befund `SB-NEU-BERECHNEN`. Abgeben lässt sie sich erst nach einem neuen „Berechnen“, denn Summen, Steuerbilanz und Betriebsvermögensvergleich folgen über die Taxonomie aus diesen Angaben.

## Positionen, Korrekturen und Zeilen von Hand

Die Tabelle „Positionen“ hält jede Position von Bilanz, GuV und Betriebsvermögensvergleich, die die E-Bilanz meldet, in der Reihenfolge ihrer Darstellung in der Taxonomie: die Positionen mit Betrag, die Oberpositionen, jedes Mussfeld und Summenmussfeld, das die Bücher nicht füllen, als NIL, und bei HGBM die Positionen, die nur die Steuerbilanz hat. Ihre Spalten: „Position“ (`concept`, der Name ohne das Präfix `de-gaap-ci:`), die Bezeichnung der Taxonomie (`label`), der „Berichtsbestandteil“ (`component`, B, GuV oder BVV), das „Kennzeichen der Taxonomie“ (`mark`: Muss, Summenmuss, Auffang, rechnerisch notwendig oder davon), die Ebene in der Darstellung (`depth`), die „Übergeordnete Position“ (`parent_concept`), „Teil von“ (`davon_of`) bei einer „davon“-Position, „NIL“ (`nil`), „Betrag laut Hauptbuch“ (`ledger_amount`), „Berechneter Betrag“ (`computed`), „Betrag der Steuerbilanz“ (`tax_amount`) nach der Überleitung, „Korrigierter Betrag“ (`correction`) mit „Begründung der Korrektur“ (`correction_reason`), „Berechnet bei der Korrektur“ (`correction_basis`, der Betrag, den „Berechnen“ ergab, als die Korrektur eingetragen wurde; siehe [Jahresmeldungen](jahresmeldungen.md)), „Gemeldeter Betrag“ (`reported`) und „Zeile von Hand“ (`manual`).

- **Korrektur:** meldet einen anderen Betrag einer Position, unter der keine Positionen stehen, und braucht eine Begründung, wie an jeder Jahresmeldung; eine Summe ergibt sich aus den Positionen darunter, korrigiert wird eine von ihnen (`EB-KORREKTUR-SUMME`). Auch eine Korrektur auf 0 zählt.
- **Zeile von Hand:** eine neue Zeile mit dem Namen einer Position, die die Bücher nicht füllen, und ihrem Betrag als Korrektur mit Begründung. Das Speichern nimmt das Präfix `de-gaap-ci:` weg, setzt Bezeichnung und Berichtsbestandteil aus der Taxonomie und lehnt eine Position ab, die „Berechnen“ schon meldet: deren Zeile wird korrigiert.
- **Die Summen** rechnet der Kern aus den gemeldeten Beträgen nach dem Rechennetz der Taxonomie, der Jahresüberschuss der Bilanz kommt aus der GuV.

## Anlagenspiegel

„Für Wirtschaftsjahre, die nach dem 31. Dezember 2016 beginnen, ist der „Anlagenspiegel (brutto)“ [table.nt.ass.gross] zu übermitteln.“ (Leitfaden B.14.12.1). Die Tabelle „Anlagenspiegel“ hält eine Zeile je Anlagenkategorie und Wertart, die „Berechnen“ aus dem Bericht „Asset Depreciations and Balances“ von ERPNext füllt, auf der Position, in die die Bilanzzuordnung das Anlagenkonto der Kategorie setzt:

- **Je Anlage, je Kategorie.** Der Bericht summiert je Anlage Anschaffungs- und Herstellungskosten zum Anfang der Periode, Zugänge, Abgänge durch Verkauf, Verschrottung und Aktivierung, die Anpassungen auf dem Anlagenkonto, die kumulierten Abschreibungen zum Anfang, die Abschreibungen der Periode abzüglich ihrer Stornos und die Abschreibungen auf die Abgänge. In einem Finanzbuch hält er nur die Anlagen mit einem Abschreibungsplan in diesem Buch; jede andere Anlage nimmt der Beleg aus dem Bericht ohne Finanzbuch, denn ERPNext zählt die Buchungen ohne Finanzbuch in jedem Buch.
- **Wertart.** Bei HAOE und AO Steuerbilanzwerte; bei HGBM Handelsbilanzwerte und, mit einem Finanzbuch der Steuerbilanz, Überleitungswerte, je Anlage das, was sie in der Steuerbilanz mehr hat, je Kategorie summiert. Ein Grundstück ohne Abschreibung hat in beiden Büchern dieselben Werte und keinen Überleitungswert. Die Steuerbilanzwerte einer Handelsbilanz leitet der Kern ab (Leitfaden B.14.12.1 c bis g).
- **Spalten von Hand.** Was das Anlagenmodul nicht nach Kategorie bucht, trägt das Unternehmen mit Begründung (`reason`) in die Zeile ein: Umbuchungen (`transfers`), Zuschreibungen (`writeups`), außerplanmäßige Abschreibungen (`depreciation_extraordinary`), Sonderabschreibungen (`depreciation_special`), den Herabsetzungsbetrag nach § 7g Abs. 2 EStG (`depreciation_7g`), den Abzugsbetrag nach § 6b EStG (`depreciation_6b`), „AfA nicht zuordenbar“ (`depreciation_other`) und die erfolgsneutralen Zugänge und Umbuchungen der kumulierten Abschreibungen (`depreciation_additions`, `depreciation_transfers`). „Berechnen“ behält sie für die Kategorie und Wertart.
- **Anpassungen in ERPNext.** Eine Anpassung des Vermögenswerts (Asset Value Adjustment) und jede andere Buchung auf dem Anlagenkonto außer Zugang und Abgang steht in „Anpassungen in ERPNext“ (`erp_adjustment`). Der Anlagenspiegel kennt keine solche Spalte: Die Spalten von Hand müssen sie genau aufnehmen, als Zuschreibung, außerplanmäßige Abschreibung, Sonderabschreibung oder Umbuchung, sonst hält `SB-ANLAGE-ANPASSUNG` die E-Bilanz an.
- **Zeile von Hand.** Eine neue Zeile nennt ihre Position (`position`) und Wertart (`value_type`), gibt jede Spalte an und braucht eine Begründung, etwa für ein Grundstück, das nicht als Anlage geführt ist.

Die Spalten der Zeile: Position, „Bezeichnung der Position“ (`position_label`), „Wertart“ (`value_type`, StB, HB oder Überleitung, Leitfaden A.14.2.2), die Anlagenkategorie (`asset_category`), „Zeile von Hand“ (`manual`), „Anschaffungs- und Herstellungskosten zum Anfang der Periode“ (`cost_begin`), „Anschaffungs- und Herstellungskosten, Zugänge“ (`additions`), „Anschaffungs- und Herstellungskosten, Abgänge“ (`disposals`), „Anschaffungs- und Herstellungskosten, Umbuchungen“, „Zuschreibungen“, „Kumulierte Abschreibungen zum Anfang der Periode“ (`depreciation_begin`), „Planmäßige Abschreibung“ (`depreciation_regular`), „Außerplanmäßige Abschreibung“, „Sonderabschreibung“, „Herabsetzungsbetrag nach § 7g Abs. 2 EStG“, „Abzugsbetrag nach § 6b EStG“, „AfA nicht zuordenbar“, „Kumulierte Abschreibungen, erfolgsneutrale Zugänge“, „Kumulierte Abschreibungen, erfolgsneutrale Abgänge“ (`depreciation_disposals`), „Kumulierte Abschreibungen, Umbuchungen“ und, berechnet, „Anschaffungs- und Herstellungskosten zum Ende der Periode“ (`cost_end`), „Kumulierte Abschreibungen zum Ende der Periode“ (`depreciation_end`) und „Buchwert zum Ende der Periode“ (`book_value_end`). Der Buchwert jeder Zeile muss der Wert ihrer Position in der Bilanz sein (Leitfaden B.14.12.1 e bis g); das prüft der Kern.

Die Abschreibungen der Bücher prüft der Beleg dazu: Planen die aktiven Abschreibungspläne der Anlagen in den Finanzbüchern der E-Bilanz bis zum Bilanzstichtag eine Abschreibung, die keine Journalbuchung gebucht hat, hält `SB-AFA-OFFEN` an (§ 253 Abs. 3 Satz 1 HGB, § 7 Abs. 1 EStG). Eine abgeschriebene Anlage braucht in jedem Finanzbuch der E-Bilanz einen aktiven Plan oder einen ohne Finanzbuch (`SB-ANLAGE-PLAN`), aber nicht beides, denn das Buch zählte dann beide Abschreibungen (`SB-ANLAGE-DOPPELT`): Weichen die Abschreibungen der Bücher ab, gehört jeder Plan in sein Finanzbuch.

## Überleitungsrechnung

„Enthält die Bilanz Ansätze oder Beträge, die den steuerlichen Vorschriften nicht entsprechen, so sind diese Ansätze oder Beträge durch Zusätze oder Anmerkungen den steuerlichen Vorschriften anzupassen“ (§ 5b Abs. 1 Satz 2 EStG). Bei HGBM hält die Tabelle „Überleitungsrechnung“ diese Anpassungen, je Position in ihrer Richtung, mit „Art der Überleitung“ (`kind`: Wertänderung, Umgliederung oder Umgliederung und Wertänderung, Leitfaden A.11), Position (`position`), „Bezeichnung der Position“ (`position_label`), „Änderung des laufenden Wirtschaftsjahres“ (`current`), „Änderung früherer Wirtschaftsjahre“ (`previous`), Begründung (`reason`) und „Aus dem Finanzbuch“ (`derived`).

- **Aus dem Finanzbuch der Steuerbilanz:** Für einen Jahresabschluss vergleicht „Berechnen“ die Salden der Positionen im Finanzbuch der Steuerbilanz mit denen der Handelsbilanz und schreibt je Position von Bilanz und GuV, deren Salden abweichen, eine Wertänderung, bei einer Position der Bilanz geteilt in die Abweichung zu Beginn des Wirtschaftsjahres, die der früheren Wirtschaftsjahre, und die Änderung im laufenden (Leitfaden A.11, B.15.1). Das Eigenkapital lässt es aus: Seine Abweichung ist der steuerliche Ausgleichsposten, den der Kern aus den übrigen Einträgen ableitet. Diese Einträge ändert ein Speichern nicht.
- **Von Hand:** ohne Finanzbuch der Steuerbilanz oder für eine Abweichung, die es nicht kennt, eine Zeile mit Art, Position, Beträgen und Begründung (`EB-UEBERLEITUNG-BEGRUENDUNG`).
- **Steuerbilanz:** Der Kern gibt der Handelsbilanz die Steuerbilanz, die ERiC prüft, mit dem steuerlichen Ausgleichsposten und dem Jahresüberschuss der Steuerbilanz (`tax_net_income`); jede Position hält ihren „Betrag der Steuerbilanz“ (`tax_amount`), und das Druckformat „E-Bilanz“ zeigt ihn neben dem Betrag der Handelsbilanz.

## Betriebsvermögensvergleich

Der steuerliche Betriebsvermögensvergleich eines Jahresabschlusses (Leitfaden B.14.3.2.12) stellt das Betriebsvermögen am Bilanzstichtag neben das zum Ende des vorangegangenen Wirtschaftsjahres, mit den Einlagen, Entnahmen und Ausschüttungen und einer Kapitalanpassung; sein Ergebnis ist der Jahresüberschuss der Steuerbilanz. Das Betriebsvermögen des Vorjahres (`bvv_previous_equity`) setzt „Berechnen“:

1. im Gründungsjahr 0, und das Eigenkapital der Bücher am ersten Tag sind die „Einlagen bei der Gründung“;
2. sonst das „Betriebsvermögen der Steuerbilanz“ der abgegebenen E-Bilanz des Vorjahres, die keine Berichtigung ersetzt hat;
3. ohne sie das Eigenkapital der Bücher zu Beginn des Wirtschaftsjahres, bei HGBM mit dem steuerlichen Ausgleichsposten des letzten Bilanzstichtags.

Ein anderer Betrag, etwa der eines Bescheids, geht mit Begründung in „Betriebsvermögen des Vorjahres laut Unternehmen“; ohne Begründung nimmt „Berechnen“ den berechneten. Weitere Einlagen, Entnahmen und Ausschüttungen und die Kapitalanpassung gibt das Unternehmen an; ein Betrag von 0 geht als NIL.

## Befunde und „Bereit“

„Bereit“ heißt, wie an jeder Jahresmeldung: kein Fehler der Befunde. An der E-Bilanz verlangt das:

- die Taxonomie der E-Bilanz eingerichtet und unverändert;
- die Bilanzzuordnung auf derselben Version der Taxonomie;
- kein Saldo ohne Platz in der Bilanzzuordnung und kein Fehler der Prüfungen des Kerns: Mussfelder, Summen, Oberpositionen, Anlagenspiegel, Überleitung, Kontensalden und Instanz;
- jede Anpassung in ERPNext auf einem Anlagenkonto in einer Spalte des Anlagenspiegels;
- die Abschreibungen bis zum Bilanzstichtag gebucht, mit einem Abschreibungsplan je Anlage und Finanzbuch;
- eine vollständige GCD: Name, Anschrift und die Steuernummer im ELSTER-Format;
- ist der Jahresabschluss des Jahres festgestellt, dieselbe Handelsbilanz wie er.

Ein fehlender Periodenabschlussbeleg ist nur ein Hinweis: Die E-Bilanz nimmt den Jahresüberschuss aus der GuV und braucht ihn nicht.

| Code | Art | Woher |
|---|---|---|
| `SB-TAXONOMIE` | Fehler | die eingerichtete Taxonomie weicht von ihrem Manifest ab, siehe [Einrichten](taxonomie.md#einrichten) |
| `SB-ANLAGE-POSITION` | Fehler | das Anlagenkonto einer Anlagenkategorie geht in keine Position des Anlagevermögens |
| `SB-ANLAGE-ANPASSUNG` | Fehler | die Spalten von Hand einer Zeile nehmen die Anpassungen in ERPNext nicht genau auf |
| `SB-AFA-OFFEN` | Fehler | eine Abschreibung, die der Plan bis zum Bilanzstichtag vorsieht, ist nicht gebucht |
| `SB-ANLAGE-PLAN` | Fehler | eine abgeschriebene Anlage hat keinen aktiven Abschreibungsplan in einem Finanzbuch der E-Bilanz und keinen ohne Finanzbuch |
| `SB-ANLAGE-DOPPELT` | Fehler | eine Anlage hat einen Plan in einem Finanzbuch der E-Bilanz und einen ohne Finanzbuch |
| `SB-BV-VORJAHR` | Hinweis | Steuerbote hält keine abgegebene E-Bilanz des Vorjahres, und das Betriebsvermögen des Vorjahres kommt aus den Buchungen zu Beginn des Wirtschaftsjahres, etwa im ersten Jahr nach einem [Start im laufenden Betrieb](einrichtung.md#start-mit-steuerbote-im-laufenden-betrieb); abzugleichen mit der E-Bilanz des Vorjahres und bei einer Abweichung unter „Betriebsvermögen des Vorjahres laut Unternehmen“ einzutragen |
| `SB-PERIODENABSCHLUSS` | Hinweis | für das Geschäftsjahr ist kein Periodenabschlussbeleg gebucht |
| `SB-NEU-BERECHNEN` | Fehler | seit dem Berechnen hat sich etwas geändert, das „Berechnen“ liest |
| `SB-KORREKTUR-UEBERHOLT` | Fehler | eine Korrektur wurde gegen einen anderen Betrag eingetragen, als „Berechnen“ jetzt für ihre Zeile ergibt, siehe [Jahresmeldungen](jahresmeldungen.md) |
| `SB-JA-ABWEICHUNG` | Fehler, Hinweis | ein Posten der Handelsbilanz liegt einen Euro oder mehr neben dem des Jahresabschlusses: ein Fehler, wenn der Jahresabschluss festgestellt ist, sonst ein Hinweis |
| `SB-JA-FEHLT` | Hinweis | der Jahresabschluss des Jahres ist nicht berechnet, verglichen ist nichts |
| `SB-ZUORDNUNG-VERSION` | Fehler | die Bilanzzuordnung nennt eine andere Version der Taxonomie als die E-Bilanz, an der Stelle von `BILANZ-TAXONOMIE`: Eine ältere Zuordnung kommt mit „Auf neue Taxonomie heben“ auf die Version der E-Bilanz; eine gehobene lässt sich nicht zurücknehmen, dann nimmt die E-Bilanz ihre Version, wo das Wirtschaftsjahr sie nehmen darf, siehe [Versionen](taxonomie.md#versionen). Bis dahin setzt „Berechnen“ die Bücher auf die Positionen der Version der E-Bilanz |
| `BILANZ-OHNE-PLATZ`, `BILANZ-OHNE-KONTONUMMER`, `BILANZ-BEOBACHTET`, `BILANZ-POSITION`, `BILANZ-NICHT-GUELTIG`, `BILANZ-ABSCHLUSSKONTO`, `BILANZ-TAXONOMIE` | Fehler | die Bilanzzuordnung: ein Saldo ohne Platz oder ohne Kontonummer, ein beobachtetes Konto, eine Position, die es nicht gibt oder die im Wirtschaftsjahr nicht gilt, das Ergebnis früherer Jahre ohne Abschlusskonto, eine andere Taxonomie |
| `BILANZ-AUSSERHALB`, `BILANZ-ABSCHLUSSZWECK`, `BILANZ-AUFFANGPOSITION`, `BILANZ-ERGEBNISVORTRAG` | Hinweis | ein Saldo außerhalb von Bilanz und GuV oder nur für eine andere Bilanz, eine Auffangposition, das Ergebnis früherer Jahre auf dem Abschlusskonto |
| `EB-NICHT-ZUGEORDNET`, `EB-POSITION`, `EB-BERECHNET`, `EB-DAVON` | Fehler | eine Position, die die E-Bilanz nicht nimmt: kein Platz, für die Finanzverwaltung nicht zulässig, eine Position des Betriebsvermögensvergleichs oder eine „davon“-Position |
| `EB-SUMME`, `EB-KORREKTUR-SUMME` | Fehler | eine Summe stimmt nicht, oder eine Korrektur trifft eine Summe |
| `EB-ANLAGENSPIEGEL-ZEILE`, `EB-ANLAGENSPIEGEL-WERT`, `EB-ANLAGENSPIEGEL-BEGRUENDUNG`, `EB-ANLAGENSPIEGEL-ANFANG`, `EB-ANLAGENSPIEGEL-STEUERLICH` | Fehler | eine Zeile des Anlagenspiegels: keine Position des Anlagevermögens, eine Wertart, die der Bilanzierungsstandard nicht nimmt, Beträge von Hand ohne Begründung, Werte vor dem ersten Wirtschaftsjahr, eine steuerlich nicht zulässige Position |
| `EB-UEBERLEITUNG-BERECHNET`, `EB-UEBERLEITUNG-SUMME`, `EB-UEBERLEITUNG-VORPERIODE`, `EB-UEBERLEITUNG-BEGRUENDUNG`, `EB-UEBERLEITUNG-STEUERLICH` | Fehler | ein Eintrag der Überleitung, den Steuerbote selbst ableitet, auf einer Summe, mit Vorperiode auf einem Posten der GuV oder ohne Begründung, oder eine steuerlich nicht zulässige Position, die nicht auf null geht |
| `EB-UMGLIEDERUNG` | Hinweis | die Umgliederungen ändern Eigenkapital oder Ergebnis |
| `EB-KONTENSALDEN`, `EB-KONTENSALDEN-FEHLEN`, `EB-KONTENSALDEN-SUMME` | Fehler, Hinweis | ohne Kontensalden; ab der Taxonomie 6.10 braucht jede Position einen Kontensaldo, der ihren Betrag ergibt |
| `EB-KONTENSALDEN-OHNE-KONTO` | Hinweis | ab der Taxonomie 6.10 eine Position von Hand ohne Konto der Bücher, die die E-Bilanz als Kontensaldo ohne Konteninformationen meldet; `EB-KONTENSALDEN-SUMME` ist dort ein Fehler |
| `EB-STEUERNUMMER`, `EB-FINANZAMT`, `EB-KENNUNG`, `EB-GCD-ZEICHEN`, `EB-TAXONOMIE` | Fehler | die GCD: die Steuernummer, das Finanzamt, die Kennung einer Eröffnungsbilanz ohne Steuernummer, Zeichen, die ELSTER nicht nimmt, eine unbekannte Taxonomie |
| `EB-INSTANZ` | Fehler | die XBRL-Instanz lässt sich nicht schreiben |
| Regelnummer der Taxonomie, etwa `170185136` | Fehler | eine Regel oder ein struktureller Fehler der Jahresdokumentation der Taxonomie, die der Kern selbst prüft |

## Abgabe

- **Fälligkeit:** Die E-Bilanz hat keine eigene Frist und geht mit der Körperschaftsteuererklärung des Jahres, in dem das Wirtschaftsjahr endet (FAQ zur E-Bilanz, Version 2026-01, Tz. 5), die Eröffnungsbilanz mit ihr; für 2026 ist das der 02.08.2027, mit Steuerberatung der 29.02.2028, siehe [Fristen](fristen.md#jahresmeldungen).
- **Über ERiC:** Prüfen, Testsenden und Senden in der Datenart der Taxonomie, `Bilanz_6.9` (`datenart.bilanz`), mit den Nutzdaten aus `steuerbote/elster/ebilanz_xml.py`; Prüfen ohne Vorschau (EBV-8), denn ERiC druckt die E-Bilanz nicht. Die Nutzdaten kommen aus dem Beleg, wie er gespeichert ist: Gibt die E-Bilanz aus seinen Tabellen einen anderen Betrag als den gespeicherten, etwa nach einer Änderung der Taxonomie, lehnt der Beleg ab, bis „Berechnen“ ihn neu rechnet. Ohne Hersteller-ID läuft das als Simulation, die Aufbau, Mussfelder und Summen mit der eingerichteten Taxonomie prüft.
- **XBRL exportieren:** an einer berechneten E-Bilanz, die abgegeben werden könnte, und an einer abgegebenen gibt „XBRL exportieren“ die Instanz als Datei, privat am Beleg, für die Steuerberatung, die sie mit ihrer Software übermittelt. Eine abgegebene E-Bilanz gibt die Datei, wie sie abgegeben ist.
- **In Mein ELSTER:** Mein ELSTER nimmt keine E-Bilanz an; das ist „nicht möglich und auch nicht geplant“ (FAQ zur E-Bilanz, Version 2026-01, Tz. 9).
- **Auf anderem Weg,** etwa durch die Steuerberatung: „Als außerhalb abgegeben vermerken“ mit „Wie und wann abgegeben“, etwa „am 15. Mai 2027 durch die Steuerberatung, das Übertragungsprotokoll liegt in den Unterlagen“.

### Berichtigung

Eine geänderte Bilanz „ist als eigener, neuer Datensatz einzureichen“, und die GCD sagt, dass es eine geänderte ist (FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d). „Berichtigung anlegen“ an einer abgegebenen E-Bilanz legt eine neue, vollständige E-Bilanz desselben Unternehmens, Jahres und derselben Bilanzart an, mit den Korrekturen, Zeilen von Hand, den Spalten und Zeilen von Hand des Anlagenspiegels, den Einträgen von Hand der Überleitung und den Angaben der abgegebenen, und berechnet sie sofort. Sie nennt ihren Status des Berichts; „K“, die Korrektur durch die Finanzverwaltung, gibt es für eine Abgabe nicht. Welcher Status gilt, entscheidet die Steuerberatung. Abgegeben, setzt eine Berichtigung die frühere auf „Ersetzt“. Eine abgegebene E-Bilanz wird nie storniert.

## Druckformat „E-Bilanz“

Das Druckformat „E-Bilanz“ gibt die E-Bilanz mit den Bezeichnungen der Taxonomie aus, auf A4, schwarz und grau, für die Steuerberatung:

- **Kopf:** der Kopf der Jahresmeldungen mit Bilanzstichtag, Bilanzierungsstandard, HGB-Taxonomie und Status des Berichts.
- **Bilanz in Kontoform:** links die Aktiva, rechts die Passiva, jede Position auf ihrer Ebene, eine Position über anderen als Summe; bei HGBM neben dem Betrag der Handelsbilanz der der Steuerbilanz.
- **GuV und Betriebsvermögensvergleich** in der Reihenfolge ihrer Darstellung.
- **Anlagenspiegel (brutto)** in zwei Teilen, Anschaffungs- und Herstellungskosten sowie Abschreibungen und Buchwert, je Zeile mit Kategorie oder „Zeile von Hand“ und Begründung und mit der Summe je Wertart; die Abschreibungen des Jahres als Summe ihrer Arten, die die XBRL-Datei einzeln meldet.
- **Kontennachweis:** je Position ihre Konten mit Nummer, Bezeichnung und Saldo und deren Summe.
- **Überleitungsrechnung** bei HGBM.
- **Darunter:** die Korrekturen und Zeilen von Hand, die Befunde, die Anmerkungen und der Hinweis, dass der Ausdruck keine Abgabe ist.

Ein Mussfeld, das als NIL geht, hat keinen Betrag und steht nicht im Ausdruck. Die Abschnitte gibt `e_bilanz_print()` des Belegs mit `print_sections()` aus `electronic_balance_sheet/layout.py`; das Druckformat rechnet nichts. Es ist das Standard-Druckformat des Belegs, über den Property Setter in `steuerbote/fixtures/property_setter.json`.

## Bericht „E-Bilanz Positionen“

Der Bericht zeigt für ein Unternehmen, ein Jahr und eine Bilanzart die Positionen der E-Bilanz als Baum, jede Position unter der übergeordneten, und darunter die Konten, aus denen sie besteht, mit ihren Salden. Er liest die abgegebene E-Bilanz, die keine Berichtigung ersetzt hat, sonst den neuesten Entwurf, so wie „Berechnen“ ihn geschrieben hat (`report/e_bilanz_positionen/rows.py`, ohne Frappe).

Darüber stellt er die Umsatzerlöse der E-Bilanz, „Umsatzerlöse (GKV)“, neben die Kz 81, 86, 41 und 45 der für das Jahr abgegebenen Voranmeldungen, so wie sie nach den Korrekturen abgegeben sind. Eine Voranmeldung meldet volle Euro, bis zu einem Euro je Betrag ist also keine Abweichung. Darüber hinaus gibt der Bericht einen Hinweis: Andere Kennzahlen wie Kz 43 oder Kz 21 und Buchungen nach einer Voranmeldung erklären eine Abweichung; ob sie erklärt ist, entscheidet das Unternehmen. Ohne abgegebene Voranmeldung sagt er das.

Rollen wie bei dem Beleg: Accounts Manager, Accounts User und System Manager. Bezeichnungen zeigt der Bericht als Text, nie als HTML.

## Vergleich mit dem Jahresabschluss

Die Bilanz der E-Bilanz ist die des Jahresabschlusses: „Wird der Gewinn nach § 4 Absatz 1, § 5 oder § 5a ermittelt, so ist der Inhalt der Bilanz, der Gewinn- und Verlustrechnung [...] nach amtlich vorgeschriebenem Datensatz durch Datenfernübertragung zu übermitteln“ (§ 5b Abs. 1 Satz 1 EStG), und „Enthält die Bilanz Ansätze oder Beträge, die den steuerlichen Vorschriften nicht entsprechen, so sind diese Ansätze oder Beträge durch Zusätze oder Anmerkungen den steuerlichen Vorschriften anzupassen“ (§ 5b Abs. 1 Satz 2 EStG): Das ist die Überleitungsrechnung. Beide Belege lesen dieselben Bücher über dieselbe Bilanzzuordnung, der Jahresabschluss in der handelsrechtlichen Ansicht mit den Posten des § 266 HGB seiner Größenklasse, die E-Bilanz in der steuerlichen mit ihren tieferen Positionen. Eine neue E-Bilanz nennt im Feld „Jahresabschluss“ den Jahresabschluss ihres Unternehmens und Jahres, den festgestellten oder, solange keiner festgestellt ist, seinen Entwurf, und jedes „Berechnen“ nennt ihn neu. „Berechnen“ vergleicht dann mit dem, was der Jahresabschluss offenlegt, in vollen Euro (`electronic_balance_sheet/comparison.py`):

- **HGBM:** jeden Posten seiner Bilanz, Summe Aktiva, Summe Passiva und den Jahresüberschuss/Jahresfehlbetrag mit den Beträgen der Handelsbilanz der E-Bilanz vor der Überleitung, wo die E-Bilanz die Position führt;
- **HAOE:** Summe Aktiva und Jahresüberschuss/Jahresfehlbetrag als Plausibilität, denn eine Einheitsbilanz kann schon an das Steuerrecht angepasst sein (Leitfaden B.13);
- **AO:** nichts, denn eine Steuerbilanz ist keine Handelsbilanz.

Weniger als ein Euro ist Rundung. Liegt ein Posten einen Euro oder mehr daneben, nennt `SB-JA-ABWEICHUNG` ihn mit beiden Beträgen und dem Unterschied: als Fehler, der die E-Bilanz von „Bereit“ abhält, wenn der Jahresabschluss festgestellt ist (§ 42a Abs. 2 Satz 1 GmbHG), sonst als Hinweis, denn er kann sich noch ändern. Der übliche Grund ist eine Buchung nach der Feststellung; dann wird der Jahresabschluss storniert, berichtigt und neu festgestellt, siehe [Feststellung](jahresabschluss.md#feststellung). Ist der Jahresabschluss nicht berechnet, sagt `SB-JA-FEHLT`, dass nichts verglichen ist. Ohne Jahresabschluss in Steuerbote, etwa wenn die Steuerberatung ihn aufstellt, vergleicht „Berechnen“ nichts, und das Feld bleibt leer.

Wird der Jahresabschluss storniert, nachdem „Berechnen“ die E-Bilanz mit ihm verglichen hat, lässt sie sich erst nach einem neuen „Berechnen“ abgeben, das sie mit seiner Berichtigung vergleicht. Eine abgegebene E-Bilanz hält das Stornieren nicht auf: Sie nennt weiter den Jahresabschluss, mit dem sie verglichen ist, und ihre Berichtigung nennt den neuen. Der Jahresabschluss zeigt die E-Bilanzen, die ihn nennen, unter seinen Verbindungen. Wo der Vergleich in der Arbeit eines Jahres steht, sagt [Zusammenspiel der Jahresmeldungen](jahresmeldungen.md#zusammenspiel-der-jahresmeldungen).

## Für die Körperschaftsteuererklärung

Die Körperschaftsteuererklärung nennt die E-Bilanz ihres Jahres im Feld „E-Bilanz“ und nimmt aus ihr Anlage GK Zeile 11, siehe [Aus der E-Bilanz](ertragsteuern.md#aus-der-e-bilanz): den Jahresüberschuss der GuV, bei HGBM der Handelsbilanz (`net_income`), und den Unterschied zum Jahresüberschuss der Steuerbilanz nach der Überleitungsrechnung (`tax_net_income`). „Berechnen“ an der Körperschaftsteuererklärung nimmt die E-Bilanz des Jahresabschlusses, die berechnet, bereit oder abgegeben und nicht ersetzt ist; wer nach der E-Bilanz noch bucht, etwa die vorgeschlagenen Rückstellungen, berechnet sie neu, bevor die Erklärung ihren Jahresüberschuss nimmt. Für KSt 1 F Zeilen 17 und 18 des Folgejahres nimmt die Körperschaftsteuererklärung von der abgegebenen E-Bilanz, die keine Berichtigung ersetzt hat, das Betriebsvermögen der Steuerbilanz (`tax_equity`) und den Betrag der Steuerbilanz des gezeichneten Kapitals (`bs.eqLiab.equity.subscribed`).

## Grenzen

- Die Handelsbilanz kommt aus dem Hauptbuch, nicht aus dem Beleg „Jahresabschluss“ (`Annual Accounts`); „Berechnen“ vergleicht sie mit ihm, siehe [Vergleich mit dem Jahresabschluss](#vergleich-mit-dem-jahresabschluss).
- Keine Vorjahreswerte, keine Ergänzungs- und Sonderbilanzen, keine Kapitalkontenentwicklung, keine GuV im Umsatzkostenverfahren.
- Ein Wirtschaftsjahr je Jahr und Bilanzart; zwei Geschäftsjahre, die im selben Jahr enden und dasselbe Unternehmen nennen, lehnt der Beleg ab.
- Der Anlagenspiegel liest je Anlage und Kategorie, was das Anlagenmodul bucht; Umbuchungen, Zuschreibungen und die übrigen Arten der Abschreibung kommen von Hand.
- Die Überleitung aus dem Finanzbuch der Steuerbilanz kennt nur Wertänderungen; eine Umgliederung kommt von Hand.
- Der Bericht ERPNext „Asset Depreciations and Balances“ zählt in jedem Buch auch die Buchungen eines Standardfinanzbuchs des Unternehmens; ein Standardfinanzbuch, das nicht das der E-Bilanz ist, lässt Anlagenspiegel und Bilanz auseinanderlaufen, und der Kern hält die E-Bilanz an.
- Mein ELSTER nimmt keine E-Bilanz an; ohne Hersteller-ID geht sie nur über die Steuerberatung.

## Quellen

- EStG § 5b, § 7 Abs. 1; HGB §§ 253 Abs. 3, 284 Abs. 3, gelesen am 23.11.2026 auf gesetze-im-internet.de; EStG § 5 Abs. 1 Satz 1, GmbHG § 42a Abs. 2 Satz 1 und EStDV § 60 Abs. 2 Satz 1, gelesen am 24.11.2026 ebenda.
- BMF-Schreiben vom 10.06.2025, IV C 6 - S 2133-b/00064/002/006, BStBl I S. 1450; Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025, A.11, A.14.2.2, B.13, B.14.3.2.12, B.14.12.1, B.15.1, B.18; FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d, 5 und 9; alle auf <https://www.esteuer.de/>.
- HGB-Taxonomie 6.9: die steuerliche Ansicht `de-gaap-ci-2025-04-01-shell-fiscal.xsd`, die Regeln und strukturellen Fehler ihrer Jahresdokumentation in der ERiC-Dokumentation 44.3.6.0.
- ERPNext 16: Bericht „Asset Depreciations and Balances“, Asset Depreciation Schedule, Asset Value Adjustment, Finance Book, Period Closing Voucher.
