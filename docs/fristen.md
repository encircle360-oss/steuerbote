# Fristen

Steuerbote kennt die Fristen der Umsatzsteuer-Voranmeldung, der Zusammenfassenden Meldung und der Sondervorauszahlung. Der Bericht „Offene Fristen“ zeigt sie für ein Unternehmen oder für alle, eine E-Mail erinnert jeden Tag an die, die nicht abgegeben sind. Welche Fristen es gibt und wann sie fällig sind, rechnet der Kern unter `steuerbote/deadlines` aus den Einstellungen Umsatzsteuer-Voranmeldung, mit den Regeln der Kerne der Voranmeldung, der Zusammenfassenden Meldung und der Dauerfristverlängerung. Er ist reines Python ohne Frappe-Import und hat vollständige Testabdeckung. Die Seite ersetzt keine Steuerberatung.

## Welche Fristen

| Art | Je | Fällig | Quelle |
|---|---|---|---|
| Umsatzsteuer-Voranmeldung | Voranmeldungszeitraum der Einstellungen, monatlich oder vierteljährlich | am 10. Tag nach Ablauf des Zeitraums, mit Dauerfristverlängerung seines Jahres einen Monat später | § 18 Abs. 1 Satz 1 UStG; Anleitung USt 1 E 2026, Zeilen 53 bis 54; § 46 UStDV; `Period.deadline` in `ustva/period.py` |
| Zusammenfassende Meldung | Meldezeitraum des Abgaberhythmus der Einstellungen | am 25. Tag nach Ablauf des Meldezeitraums, ohne Dauerfristverlängerung | § 18a Abs. 1 UStG; BZSt „Fristen“ (ZM); `ReportingPeriod.deadline` in `zm/period.py` |
| Sondervorauszahlung | Jahr mit Dauerfristverlängerung, dessen erster Voranmeldungszeitraum ein Monat ist | mit der ersten Voranmeldung des Jahres ohne die Verlängerung, also am 10. Februar | § 47 Abs. 1 und § 48 Abs. 1 und 2 UStDV; Anleitung USt 5 E 2026, Zeilen 8 bis 9; `antrag_deadline` und `sondervorauszahlung_deadline` in `dauerfrist/period.py` |

- **Voranmeldung.** Eine Frist gibt es für jeden Voranmeldungszeitraum, den die Regeln der Einstellungen vorsehen (`rhythm_for` in `vat_return_settings/rules.py`). Monate mit „Keine“ und Monate vor der ersten Regel haben keine: Den Zeitraum legt das Finanzamt fest, Steuerbote rät ihn nicht.
- **Zusammenfassende Meldung.** Die Meldezeiträume ergeben sich aus dem Abgaberhythmus der Einstellungen wie beim Beleg (`goods_period` und `coverage` in `zm/rhythm.py`), auch die zwei Monate eines Quartals nach einem Wechsel zur monatlichen Abgabe und das Kalenderjahr, siehe [Zusammenfassende Meldung](zm.md#meldezeiträume-und-fristen). Ohne Abgaberhythmus gibt es keine Frist.
- **Sondervorauszahlung.** Ein Unternehmen, das monatlich abgibt, zahlt sie in jedem Jahr mit Dauerfristverlängerung „bis zum gesetzlichen Zeitpunkt der Übermittlung der ersten Voranmeldung“ (§ 48 Abs. 2 Satz 1 UStDV), im Jahr des Antrags mit dem Antrag (§ 48 Abs. 1 UStDV). Beginnen die Voranmeldungen eines Jahres später, etwa im April, ist sie mit der Voranmeldung für April fällig. Wer vierteljährlich abgibt, zahlt keine (§ 47 Abs. 1 UStDV) und hat hier keine Frist. Siehe [Dauerfristverlängerung](dauerfristverlaengerung.md#fristen).
- **Wochenende und Feiertage.** „Fällt das Ende einer Frist auf einen Sonntag, einen gesetzlichen Feiertag oder einen Sonnabend, so endet die Frist mit dem Ablauf des nächstfolgenden Werktags.“ (§ 108 Abs. 3 AO; für die ZM über § 18a Abs. 11 UStG) Die Feiertage kommen für alle drei Arten aus der Standard-Feiertagsliste des Unternehmens, ohne die wöchentlich freien Tage (`steuerbote/holiday_list.py`). Das Feld „Fälligkeitsdatum“ der Voranmeldung selbst berücksichtigt die Feiertage noch nicht; fällt der 10. auf einen Feiertag der Liste, nennt der Bericht den nächsten Werktag.

Beispiele aus den Tests:

| Frist | Fällig |
|---|---|
| Voranmeldung Oktober 2026 | Dienstag, 10. November 2026 |
| Voranmeldung Dezember 2026, der 10. Januar ist ein Sonntag | Montag, 11. Januar 2027 |
| Voranmeldung November 2026 mit Dauerfristverlängerung | Montag, 11. Januar 2027 |
| Voranmeldung III. Kalendervierteljahr 2026, der 10. Oktober ist ein Samstag | Montag, 12. Oktober 2026 |
| ZM I. Kalendervierteljahr 2026, der 25. April ist ein Samstag | Montag, 27. April 2026 |
| ZM November 2026 mit beiden Weihnachtsfeiertagen in der Liste | Montag, 28. Dezember 2026 |
| Sondervorauszahlung 2027 | Mittwoch, 10. Februar 2027 |
| Sondervorauszahlung 2026, die Voranmeldungen beginnen im April | Montag, 11. Mai 2026 |

**Nicht in der Übersicht** sind der einmalige Antrag auf Dauerfristverlängerung bei vierteljährlicher Abgabe, denn die Einstellungen halten nicht fest, in welchem Jahr er gestellt wurde, und die Umsatzsteuererklärung für das Jahr, die Steuerbote noch nicht kennt. Die Einstellungen kennen die Dauerfristverlängerung nur für ein ganzes Jahr, siehe [Annahmen und offene Punkte](dauerfristverlaengerung.md#annahmen-und-offene-punkte).

## Abgegeben, offen oder fehlt

Jede Frist hat einen Status. Er kommt aus den Belegen des Unternehmens für ihren Zeitraum:

| Status | Bedeutung |
|---|---|
| Abgegeben | ein Beleg des Zeitraums trägt den Vermerk der Abgabe |
| Offen | es gibt einen Beleg, aber keiner ist abgegeben |
| Fehlt | es gibt keinen Beleg |

Als abgegeben zählt:

- **Voranmeldung:** eine Meldung des Zeitraums ist eingereicht, also „Abgegeben“ oder „Ersetzt“, oder wurde über Steuerbote gesendet, mit Annahme durch ELSTER oder unbekanntem Ergebnis, auch wenn sie danach storniert wurde. Das ist dieselbe Regel wie im [Lebenslauf einer Meldung](architektur.md#lebenslauf-einer-meldung) (`filings` in `vat_return.py`).
- **Zusammenfassende Meldung:** eine Meldung des Meldezeitraums ist mit „In Mein ELSTER abgegeben“ oder „Als außerhalb abgegeben vermerken“ eingereicht, auch eine Berichtigung.
- **Sondervorauszahlung:** eine Dauerfristverlängerung des Unternehmens für das Jahr ist eingereicht. Eine Anmeldung, die für ihre Berichtigung storniert wurde, bleibt abgegeben, denn das Finanzamt hat sie.

Gibt es mehrere Belege, zeigt die Frist den zuletzt angelegten abgegebenen, sonst den zuletzt angelegten.

**Keine Nullmeldung.** Eine Zusammenfassende Meldung ist nur für einen Meldezeitraum abzugeben, in dem etwas zu melden ist (§ 18a Abs. 1 UStG); „Sog. „Nullmeldungen“ sind nicht abzugeben“ (BZSt, Anleitung zur ZM, III.1). Ohne Beleg nimmt Steuerbote eine ZM deshalb nur an, wenn im Meldezeitraum ein Beleg auf ein Konto der Kz 41 oder 42 bucht, in den Monaten seiner Lieferungen, oder auf ein Konto der Kz 21, in den Monaten seiner sonstigen Leistungen. Das Hauptbuch liest es wie „Berechnen“ (`zm_sources.shares`) mit der Kontenzuordnung des Unternehmens. Passt keine Kontenzuordnung zum Jahr, zählt jeder Meldezeitraum. Hebt sich ein Beleg mit einer Gutschrift auf, nimmt Steuerbote die ZM trotzdem an; die Meldung hätte dann keine Zeile.

## Welche Fristen erscheinen

Der Bericht und die Erinnerung nennen dieselben Fristen, der Bericht bis zu seiner Vorschau, die Erinnerung bis zu ihrem Vorlauf:

- jede Frist, die von heute an bis zum letzten Tag der Vorschau oder des Vorlaufs fällig ist, mit jedem Status;
- jede Frist, die überschritten und nicht abgegeben ist, bis sie abgegeben ist: mit Beleg immer, ohne Beleg, wenn sie am Tag oder nach dem Tag fällig war, an dem die Einstellungen des Unternehmens angelegt wurden. Ob eine Frist davor außerhalb von Steuerbote eingehalten wurde, kann Steuerbote nicht wissen. Eine abgegebene Frist, die vorbei ist, erscheint nicht mehr.

Fristen am selben Tag stehen in der Reihenfolge Voranmeldung, Zusammenfassende Meldung, Sondervorauszahlung.

## Der Bericht „Offene Fristen“

Der Bericht steht im Arbeitsbereich „Steuern“ im Abschnitt „Fristen“ und in der Seitenleiste unter „Berichte“, für die Rollen Accounts Manager, Accounts User und System Manager.

| Filter | Inhalt |
|---|---|
| Unternehmen | ein Unternehmen; leer alle Unternehmen mit Einstellungen, die der Benutzer lesen darf |
| Vorschau (Tage) | wie viele Tage ab heute der Bericht vorausschaut, Vorgabe 60 |

| Spalte | Inhalt |
|---|---|
| Unternehmen | das Unternehmen |
| Art | Umsatzsteuer-Voranmeldung, Zusammenfassende Meldung oder Sondervorauszahlung |
| Zeitraum | der Voranmeldungszeitraum, der Meldezeitraum oder das Jahr der Sondervorauszahlung |
| Fällig am | der Tag der Frist |
| Tage | die Tage bis dahin, negativ für eine überschrittene Frist |
| Status | Abgegeben, Offen oder Fehlt |
| Beleg | der Beleg; fehlt er, legt „Erstellen“ einen neuen mit Unternehmen und Zeitraum an |

Die Zeilen stehen nach dem Tag der Frist geordnet. Der Bericht rechnet nichts selbst: Er liest mit `steuerbote/steuerbote/deadlines.py` Einstellungen, Belege, Feiertage und Hauptbuch, und der Kern bildet die Fristen.

## Die Erinnerung

Jeden Tag läuft der Job `send_reminders` (`scheduler_events` in `hooks.py`, „daily“). Für jedes Unternehmen, dessen Einstellungen Empfänger nennen, schickt er den Empfängern eine E-Mail mit den Fristen, die nicht abgegeben sind und innerhalb des Vorlaufs fällig werden oder überschritten sind, wie unter [Welche Fristen erscheinen](#welche-fristen-erscheinen). Die E-Mail ist deutsch: „Steuerbote: offene Fristen für …“, darin eine Tabelle wie der Bericht mit Art, Zeitraum, Fällig am, Tage, Status und einem Link auf den Beleg oder auf einen neuen Beleg des Zeitraums, darunter ein Link auf den Bericht. Sie geht über die E-Mail-Warteschlange von Frappe und braucht ein ausgehendes E-Mail-Konto.

- **Jeden Tag, bis abgegeben ist.** Eine Frist steht vom ersten Tag des Vorlaufs an jeden Tag in der E-Mail, auch nach ihrem Ablauf, bis ihr Beleg abgegeben ist. Ist an einem Tag nichts offen, geht keine E-Mail.
- **Nie zweimal am selben Tag.** Jede Frist der E-Mail hält eine „Fristerinnerung“ (`Deadline Reminder`) fest. Läuft der Job an einem Tag noch einmal, schickt er nur Fristen, an die an diesem Tag noch nicht erinnert wurde, etwa nach einem längeren Vorlauf, und sonst nichts.
- **Ohne Empfänger** geht nichts hinaus, und es gibt keinen Fehler.
- **Ungültige Einträge.** Eine Zeile, die keine E-Mail-Adresse ist, bekommt keine E-Mail; das Fehlerprotokoll (Error Log) nennt sie.
- **Fehler bei einem Unternehmen.** Scheitert die Erinnerung eines Unternehmens, etwa an seinen Einstellungen, nimmt Steuerbote ihre Änderungen zurück, schreibt den Fehler in das Fehlerprotokoll und macht mit den anderen Unternehmen weiter.

### Fristerinnerung (`Deadline Reminder`)

Ein Dokument je Frist und Tag einer Erinnerung. Nur der Server legt es an, niemand ändert es; ein System Manager darf es löschen, dann kann an die Frist am selben Tag noch einmal erinnert werden. Sein Name ist aus Unternehmen, Art, Zeitraum, Fälligkeit und Tag gebildet, deshalb lässt sich dieselbe Erinnerung nicht zweimal anlegen. Die Liste steht in der Seitenleiste als „Fristerinnerungen“.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company` | Unternehmen | |
| `kind` | Art | Umsatzsteuer-Voranmeldung, Zusammenfassende Meldung oder Sondervorauszahlung |
| `period_label` | Zeitraum | wie im Bericht |
| `due_date` | Fällig am | der Tag der Frist zur Zeit der Erinnerung |
| `sent_on` | Gesendet am | der Tag der Erinnerung |

## Einstellungen

Im Abschnitt „Fristen“ der Einstellungen Umsatzsteuer-Voranmeldung:

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `deadline_recipients` | Empfänger der Erinnerung | E-Mail-Adressen, eine je Zeile; leer geht keine Erinnerung hinaus |
| `reminder_days` | Vorlauf (Tage) | ab wie vielen Tagen vor der Fälligkeit die Erinnerung eine Frist nennt, Vorgabe 7 |

Die Fristen selbst kommen aus den Regeln der Einstellungen: Voranmeldungszeiträume, Dauerfristverlängerung je Jahr und Abgaberhythmus der Zusammenfassenden Meldung, siehe [Einstellungen je Unternehmen und Zeitraum](architektur.md#einstellungen-je-unternehmen-und-zeitraum).

## Aufbau

| Modul | Aufgabe |
|---|---|
| `steuerbote/deadlines/obligations.py` | welche Meldungen die Regeln für welchen Zeitraum verlangen und wann sie fällig sind, im Kern ohne Frappe |
| `steuerbote/deadlines/overview.py` | Status aus den Belegen, die Fristen bis zur Vorschau und die überschrittenen (`upcoming`), im Kern ohne Frappe |
| `steuerbote/steuerbote/deadlines.py` | liest Einstellungen, Belege, Feiertage und Hauptbuch, schickt die Erinnerung und legt die Fristerinnerungen an, mit Frappe |
| `steuerbote/steuerbote/report/offene_fristen/` | Bericht „Offene Fristen“ |
| `steuerbote/steuerbote/doctype/deadline_reminder/` | Fristerinnerung |

## Quellen

- **§ 18 Abs. 1 UStG:** <https://www.gesetze-im-internet.de/ustg_1980/__18.html>
- **§ 18a UStG:** <https://www.gesetze-im-internet.de/ustg_1980/__18a.html>
- **§§ 46 bis 48 UStDV:** <https://www.gesetze-im-internet.de/ustdv_1980/__46.html>, <https://www.gesetze-im-internet.de/ustdv_1980/__47.html>, <https://www.gesetze-im-internet.de/ustdv_1980/__48.html>
- **§ 108 AO:** <https://www.gesetze-im-internet.de/ao_1977/__108.html>
- **BMF-Schreiben vom 29. Dezember 2025**, GZ III C 3 - S 7344/00039/007/036, mit den Anleitungen USt 1 E 2026 und USt 5 E 2026, siehe [Dauerfristverlängerung](dauerfristverlaengerung.md#quellen)
- **BZSt „Fristen“ (ZM):** <https://www.bzst.de/DE/Unternehmen/Umsatzsteuer/ZusammenfassendeMeldung/Fristen/fristen_node.html>
- **BZSt „Anleitung zur Zusammenfassenden Meldung“** (USt ZM 1/2021), Textziffer III.1: <https://www.bzst.de/SharedDocs/Downloads/DE/ZM/zm_ausfuellanleitung.pdf?__blob=publicationFile&v=14>
