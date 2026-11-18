# Architektur

Steuerbote besteht aus zwei Schichten. Der Rechenkern unter `steuerbote/ustva` kennt die Kennzahlen des Vordrucks, rundet, ordnet Konten zu, rechnet und prüft, alles in reinem Python ohne Frappe. Die Frappe-Schicht liest das Hauptbuch und die Einstellungen aus ERPNext, übergibt sie dem Kern und hält das Ergebnis in DocTypes, einem Bericht, einem Arbeitsbereich und einem Druckformat fest. Über die ERiC-Anbindung unter `steuerbote/eric` übermittelt sie die Meldung an ELSTER. Diese Seite beschreibt die Frappe-Schicht. Die fachlichen Regeln des Kerns stehen in [Kennzahlen und Kontenzuordnung](ustva-kennzahlen.md), Aufbau, Tests und Stil in [Entwicklung](entwicklung.md).

## Der Kern rechnet, die Frappe-Schicht liest und speichert

Jeder Betrag einer Meldung kommt aus dem Kern: Kennzahlen, Rundung, die Summen des Vordrucks, Kz 83, Verprobung, Zeiträume und Fristen. Die Frappe-Schicht wandelt nur Daten um. Was sich dabei ohne Datenbank prüfen lässt, steht in eigenen Modulen ohne Frappe-Import mit Unit-Tests, damit die Controller der DocTypes dünn bleiben.

| Modul | Aufgabe |
|---|---|
| `steuerbote/ledger.py` | liest das Hauptbuch eines Zeitraums als Buchungszeilen des Kerns, als einziges dieser Module mit Frappe |
| `steuerbote/mapping_sync.py` | macht aus den Zeilen der Kontenzuordnung die `Mapping` des Kerns und kürzt die Vorgaben auf die Konten eines Unternehmens |
| `steuerbote/elster/` | bildet aus Steuernummer und Bundesland die 13-stellige Steuernummer im ELSTER-Format und schreibt die Meldung als XML für Mein ELSTER und ERiC, siehe [Abgabe über Mein ELSTER](abgabe-mein-elster.md) |
| `vat_return_settings/rules.py` | Voranmeldungszeitraum je Monat, Dauerfristverlängerung und Sondervorauszahlung je Jahr |
| `vat_return/bridge.py` | überträgt das Ergebnis des Kerns in die Tabellen der Meldung, bildet die Summen über die gemeldeten Beträge und übergibt die Meldung und den Datenlieferanten an das XML |
| `report/ustva_kennzahlen/attribution.py` | findet die Belege, aus denen jede Kennzahl besteht |

So läuft „Berechnen“ an einer Meldung:

1. Die Meldung bestimmt aus Jahr, Abgaberhythmus und Nummer ihren Zeitraum und prüft ihn gegen die Einstellungen des Unternehmens. Diese liefern auch die Dauerfristverlängerung für die Fälligkeit und, im letzten Zeitraum des Jahres, die Sondervorauszahlung für Kz 39.
2. `ledger.load_lines` liest die Buchungen (GL Entry) des Zeitraums.
3. Die Kontenzuordnung des Unternehmens wird über `mapping_sync.rows_to_mapping` zur `Mapping` des Kerns, geprüft gegen den Vordruck des Jahres der Meldung.
4. `calculate()` rechnet Kennzahlen, Summen, Kz 83 und Verprobung.
5. `bridge.py` schreibt das Ergebnis in die Tabellen der Meldung. Bei jedem Speichern rechnet der Kern Summen und Kz 83 aus den gemeldeten Beträgen neu, damit Korrekturen mit Begründung darin eingehen.

## DocTypes

DocTypes heißen nach der Konvention von Frappe englisch. Die Oberfläche zeigt die deutschen Bezeichnungen aus `steuerbote/translations/de.csv`.

### Einstellungen Umsatzsteuer-Voranmeldung (`VAT Return Settings`)

Ein Dokument je Unternehmen, sein Name ist das Unternehmen.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company` | Unternehmen | Pflicht |
| `chart` | Kontenrahmen | SKR03, SKR04 oder Eigener Kontenrahmen |
| `taxation_type` | Besteuerung | nur Soll; die Ist-Versteuerung wird noch nicht unterstützt |
| `tolerance` | Toleranz je Beleg | wie weit die gebuchte Steuer eines Belegs in der Verprobung abweichen darf, Vorgabe 0,01 EUR |
| `state` | Bundesland | Pflicht |
| `tax_number` | Steuernummer | Pflicht, wie vom Finanzamt vergeben; das Format wird gegen das Bundesland geprüft |
| `elster_tax_number` | Steuernummer im ELSTER-Format | 13 Stellen, berechnet |
| `tax_office` | Finanzamt | |
| `wid_nr` | Wirtschafts-Identifikationsnummer | freiwillig, „DE“ und neun Ziffern ohne die fünfstellige Ergänzung |
| `filer_name`, `street`, `postal_code`, `city`, `phone`, `email` | Name, Straße und Hausnummer, Postleitzahl, Ort, Telefon, E-Mail | Datenlieferant der Datei für ELSTER, Längen wie im Schema (45, 30, 12, 30, 20 und 70 Zeichen); Straße, Postleitzahl und Ort braucht die Datei, ein leerer Name steht für das Unternehmen |
| `period_rules` | Voranmeldungszeiträume | Pflicht; Tabelle „Regel zum Voranmeldungszeitraum“ mit Jahr, Voranmeldungszeitraum (monatlich, vierteljährlich oder keine) und „Gültig ab Monat“ (1, 4, 7 oder 10) |
| `prepayments` | Dauerfristverlängerung und Sondervorauszahlung | Tabelle „Dauerfristverlängerung je Jahr“ mit Jahr, Dauerfristverlängerung und Sondervorauszahlung |

### Kontenzuordnung Umsatzsteuer (`VAT Return Mapping`)

Ein Dokument je Unternehmen, sein Name ist das Unternehmen.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company` | Unternehmen | Pflicht |
| `chart` | Kontenrahmen | bestimmt die Vorgabe für „Vorgaben laden“ |
| `rules` | Zuordnungen | Tabelle „Regel der Kontenzuordnung Umsatzsteuer“: Konto, Kontonummer (aus dem Konto), Kennzahl, Seite (Haben oder Soll), Steuersatz (%), Zusätzliche Kennzahl und Seite der zusätzlichen Kennzahl |
| `checks` | Verprobungen | Tabelle „Verprobung der Kontenzuordnung Umsatzsteuer“: Bezeichnung, Grundlagenkonten und Steuerkonten (Kontonummern, durch Kommas getrennt), Seite |
| `watched` | Beobachtete Konten | Tabelle „Beobachtetes Konto der Kontenzuordnung Umsatzsteuer“: Konto und Kontonummer |

### Umsatzsteuer-Voranmeldung (`VAT Return`)

Einreichbar, Nummernkreis `UStVA-.YYYY.-.#####`.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company` | Unternehmen | Pflicht |
| `year` | Jahr | Pflicht; wählt den Katalog der Kennzahlen |
| `rhythm` | Abgaberhythmus | Pflicht, monatlich oder vierteljährlich |
| `period_index` | Nummer des Zeitraums | Pflicht, Monat 1 bis 12 oder Quartal 1 bis 4 |
| `is_correction` | Berichtigte Anmeldung (Kz 10) | |
| `period_label`, `period_code` | Voranmeldungszeitraum, Zeitraumcode | berechnet, etwa „März 2026“ und „03“, Quartale 41 bis 44 |
| `from_date`, `to_date`, `deadline` | Von-Datum, Bis-Datum, Fälligkeitsdatum | berechnet |
| `status` | Status | Entwurf, Berechnet, Bereit, Abgegeben oder Ersetzt |
| `kennzahlen` | Kennzahlen | Tabelle „Kennzahl der Umsatzsteuer-Voranmeldung“: Kennzahl, Zeile im Vordruck, Beschreibung, Art des Betrags, Betrag laut Hauptbuch, Betrag laut Vordruck, Korrigierter Betrag, Begründung der Korrektur und Gemeldeter Betrag |
| `output_tax`, `input_tax`, `other_tax` | Umsatzsteuer (Zeile 37), Vorsteuer (Zeilen 38 bis 44), Andere Steuerbeträge (Zeilen 46 und 47) | Summen über die gemeldeten Beträge |
| `sondervorauszahlung`, `kz83` | Sondervorauszahlung (Kz 39), Verbleibende Vorauszahlung oder verbleibender Überschuss (Kz 83) | |
| `ready` | Bereit zur Abgabe | alle Verprobungen gehen auf und kein beobachtetes Konto hat einen Saldo |
| `checks` | Verprobung | Tabelle „Verprobung der Umsatzsteuer-Voranmeldung“: Verprobung, Berechnete Steuer, Gebuchte Steuer, Unterschied, Abweichende Belege und Verprobung aufgegangen |
| `deviations` | Abweichende Belege | Tabelle „Abweichender Beleg der Verprobung“: Verprobung, Belegtyp, Belegnr., Berechnete Steuer, Gebuchte Steuer und Unterschied |
| `unmapped` | Beobachtete Konten mit Saldo | Tabelle „Beobachtetes Konto mit Saldo“: Kontonummer, Konto, Soll und Haben |
| `accounts_without_number` | Konten ohne Kontonummer | Zahl der Konten, die in keine Kennzahl eingehen können |
| `attachments` | Belege beigefügt oder gesondert eingereicht (Kz 22) | Kennzeichen des Vordrucks |
| `offset_requested` | Verrechnung erwünscht oder Erstattungsbetrag abgetreten (Kz 29) | Kennzeichen des Vordrucks |
| `no_sepa_mandate` | SEPA-Lastschriftmandat ausnahmsweise nicht verwenden (Kz 26) | Kennzeichen des Vordrucks |
| `supplementary_code` | Ergänzende Angaben zur Steueranmeldung (Kz 500) | Schlüssel 1 bis 4 |
| `kz500_begruendung` | Begründung zu Kz 500 | Pflicht mit Kz 500 und nur mit ihr, höchstens 180 Zeichen in einer Zeile |
| `remarks` | Anmerkungen | Pflicht, wenn eine Meldung abgegeben wird, die nicht bereit ist |
| `transmission_in_progress` | Übermittlung läuft | gesetzt, solange Prüfen, Testsenden oder Senden läuft; so lange lässt sich die Meldung nicht ändern |

An der Meldung stehen unter „Verknüpfungen“ ihre ELSTER-Übermittlungen.

### ERiC-Einstellungen (`ERiC Settings`)

Ein Dokument für die ganze Installation (Single), nur für den System Manager. Hersteller-ID und Laufzeitumgebung gehören zur Software, nicht zu einem Unternehmen.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `simulation` | Simulationsmodus | berechnet: aktiv, solange keine Laufzeitumgebung installiert oder keine Hersteller-ID eingetragen ist |
| `hersteller_id` | Hersteller-ID | fünf Ziffern nach der Regel von Kz 09, nicht 74931 |
| `produkt_name`, `produkt_version` | Produktname, Produktversion | für den NutzdatenHeader; der Name hat höchstens 50 Zeichen und enthält nicht „ELSTER“, die Version ist die von Steuerbote |
| `datenlieferant` | Datenlieferant | für den Kopf der Lieferung, höchstens 256 Zeichen |
| `archive_path`, `archive_sha256` | ERiC-Archiv, SHA-256 des Archivs | absoluter Pfad des Archivs auf dem Server und seine Prüfsumme |
| `installed_version`, `lib_dir`, `log_dir`, `last_check` | Installierte Version, Verzeichnis der Bibliotheken, Verzeichnis der Logdateien, Letzte Prüfung | setzt die Installation |

### ELSTER-Übermittlung (`ELSTER Transmission`)

Ein Dokument je Lauf von Prüfen, Testsenden oder Senden und je Vermerk einer Abgabe außerhalb von Steuerbote, Nummernkreis `ELSTER-{YYYY}-{#####}`. Nur der Server schreibt es; nach der Aufzeichnung bleibt es, wie es ist.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `vat_return`, `company` | Umsatzsteuer-Voranmeldung, Unternehmen | die Meldung und ihr Unternehmen |
| `operation` | Vorgang | `validate`, `test_send`, `send` oder `extern` |
| `status` | Status | Läuft, Erfolgreich, Fehlgeschlagen oder Unbekannt |
| `outcome` | Ergebnis laut ERiC | `valid`, `invalid`, `accepted`, `rejected`, `failed` oder `unknown` aus `steuerbote.eric.result.Outcome` |
| `simulated` | Simuliert | der Lauf ging an die Simulation |
| `started_at`, `finished_at`, `user` | Gestartet am, Beendet am, Benutzer | |
| `transferticket`, `testmerker`, `eric_version` | Transferticket, Testmerker, ERiC-Version | aus dem Ergebnis |
| `remarks` | Anmerkungen | der Vermerk einer Abgabe außerhalb von Steuerbote |
| `messages` | Nachrichten | Tabelle „Meldung der ELSTER-Übermittlung“: Art (Fehler oder Hinweis), Code, Nachricht und Feld |
| `xml`, `protocol_pdf`, `response_xml` | Nutzdaten (XML), Protokoll (PDF), Antwort des ELSTER-Servers (XML) | private Dateien der Übermittlung |

### Feld an der Journalbuchung

Steuerbote ergänzt die Journalbuchung (Journal Entry) um das Feld „Nicht in der Umsatzsteuer-Voranmeldung“ (`steuerbote_exclude_from_vat_return`). Es kommt als Fixture der App und lässt eine Buchung aus der Meldung heraus, etwa die Verrechnung der Steuerkonten mit dem Finanzamt.

## Die Abfrage des Hauptbuchs

`ledger.load_lines(company, from_date, to_date)` liest die Buchungen (GL Entry) des Unternehmens im Zeitraum, beide Tage eingeschlossen, zusammen mit der Kontonummer des Kontos. Nicht in die Meldung gehen:

- stornierte Buchungen und ihre Gegenbuchungen,
- Eröffnungsbuchungen,
- Periodenabschlussbuchungen (Period Closing Voucher),
- Journalbuchungen mit dem Haken „Nicht in der Umsatzsteuer-Voranmeldung“,
- Konten ohne Kontonummer. Keine Regel kann sie zuordnen; die Meldung zählt sie unter „Konten ohne Kontonummer“.

Soll und Haben werden je Kontonummer und Beleg summiert und als `Decimal` in Cent übergeben. Ein Beleg heißt beim Kern „Belegtyp:Belegnummer“, weil zwei Belegtypen dieselbe Nummer tragen können. Die Abfrage läuft über den Query Builder von Frappe mit Parametern, ohne zusammengesetztes SQL.

## Einstellungen je Unternehmen und Zeitraum

- **Voranmeldungszeitraum.** Jede Regel gilt ab einem Jahr und Monat bis zur nächsten Regel, auch über Jahresgrenzen. Ein Wechsel beginnt mit einem Kalendervierteljahr, also im Monat 1, 4, 7 oder 10. „Keine“ heißt: Für diese Monate ist keine Voranmeldung abzugeben. Vor der ersten Regel gibt es keinen Zeitraum, denn ihn legt das Finanzamt fest; Steuerbote rät ihn nicht.
- **Dauerfristverlängerung und Sondervorauszahlung je Jahr.** Mit Dauerfristverlängerung verschiebt sich jede Fälligkeit des Jahres um einen Monat (§ 46 UStDV). Eine Sondervorauszahlung gibt es nur zusammen mit ihr (§ 47 Absatz 1 UStDV) und sie wird in Kz 39 der letzten Voranmeldung des Jahres abgezogen (§ 48 Absatz 4 UStDV).
- **Die Meldung wählt ihren Zeitraum.** Abgaberhythmus und Nummer des Zeitraums stehen in der Meldung. Beim Speichern prüft sie, dass die Einstellungen für den ersten Monat des Zeitraums denselben Rhythmus vorschreiben, und setzt Voranmeldungszeitraum, Zeitraumcode, Von-Datum, Bis-Datum und Fälligkeit: der 10. Tag nach Ablauf des Zeitraums, mit Dauerfristverlängerung einen Monat später, an einem Wochenende der nächste Werktag. Feiertage der Länder berücksichtigt die Fälligkeit noch nicht.
- Ohne Einstellungen lässt sich keine Meldung anlegen, ohne Kontenzuordnung keine berechnen.

## Kontenzuordnung je Unternehmen

- **Vorgaben laden.** Die Schaltfläche füllt die Tabellen aus der Vorgabe für SKR03 oder SKR04, gekürzt auf die Konten des Unternehmens mit Kontonummer, die Buchungen aufnehmen. Regeln und beobachtete Konten bleiben, wenn es ihr Konto gibt. Eine Verprobung behält ihre vorhandenen Grundlagen und Steuerkonten und entfällt, wenn auf einer Seite keines bleibt. Ein Hinweis nennt die Konten der Vorgabe, die dem Unternehmen fehlen. Für einen eigenen Kontenrahmen gibt es keine Vorgabe.
- **Prüfung beim Speichern.** Jedes Konto gehört zum Unternehmen und ist keine Kontengruppe. Der Kern prüft die Zuordnung gegen den neuesten Vordruck: jedes Konto nur einmal, nur Kennzahlen mit Betrag, ein Steuersatz nur dort, wo der Vordruck eine eigene Steuer-Kennzahl hat, Verprobungen und beobachtete Konten ohne Widerspruch.
- „Berechnen“ prüft dieselbe Zuordnung noch einmal gegen den Vordruck des Jahres der Meldung.

## Lebenslauf einer Meldung

| Status | Bedeutung |
|---|---|
| Entwurf | angelegt und noch nicht berechnet, oder Unternehmen, Jahr, Abgaberhythmus oder Nummer des Zeitraums haben sich geändert; das verwirft eine Berechnung |
| Berechnet | berechnet, aber nicht bereit: Eine Verprobung weicht ab oder ein beobachtetes Konto hat einen Saldo |
| Bereit | berechnet, alle Verprobungen gehen auf und kein beobachtetes Konto hat einen Saldo |
| Abgegeben | eingereicht; das setzt eine Berechnung voraus und, wenn die Meldung nicht bereit ist, eine Begründung in den Anmerkungen |
| Ersetzt | für denselben Zeitraum ist später eine berichtigte Anmeldung abgegeben worden |

- „Berechnen“ geht, solange die Meldung nicht eingereicht ist, und lässt Korrekturen mit Begründung stehen.
- Ein Zeitraum wird je Unternehmen einmal abgegeben. Jede weitere Meldung für einen abgegebenen Zeitraum muss eine berichtigte Anmeldung (Kz 10) sein. Wird sie abgegeben, stehen die früheren Meldungen des Zeitraums auf „Ersetzt“; wird sie storniert, steht die zuletzt ersetzte wieder auf „Abgegeben“.
- „Abgegeben“ heißt: Die Meldung ist in ERPNext eingereicht und festgeschrieben. Das geschieht nach einem Senden, das ELSTER angenommen hat, mit „Als außerhalb abgegeben vermerken“ nach einer Abgabe von Hand oder als XML-Datei über Mein ELSTER, siehe [Abgabe über Mein ELSTER](abgabe-mein-elster.md), oder mit „Buchen“.
- „XML für Mein ELSTER“ erzeugt die Datei aus der gespeicherten Meldung, wenn sie abgegeben werden könnte oder abgegeben ist, und hängt sie privat an die Meldung.

## Übermittlung an ELSTER

Prüfen, Testsenden und Senden laufen in einem Hintergrundjob, ERiC selbst in einem kurzlebigen Prozess des Jobs. Was Anwender dabei sehen, beschreibt [Übermittlung an ELSTER](uebermittlung.md), die Anbindung von ERiC [ERiC](eric.md).

1. `transmit` an der Meldung sperrt ihre Zeile, liest sie neu und prüft: Entwurf, berechnet, kein laufender Vorgang. Für Senden prüft sie dazu, dass kein Simulationsmodus aktiv ist, die Meldung abgegeben werden könnte wie beim Buchen und weder sie noch eine andere Meldung des Zeitraums ohne Kz 10 übermittelt ist oder mit unbekanntem Ergebnis gesendet wurde.
2. Sie legt die ELSTER-Übermittlung mit dem Status „Läuft“ an, setzt `transmission_in_progress` und stellt `run_transmission` in die Queue `long`, nach dem Commit, mit einer Job-ID je Meldung und ohne doppelte Jobs. Ein Lauf, dessen Job verschwunden ist, wird beim nächsten Start geschlossen.
3. Zertifikat und Passwort gehen vorher an `stash_certificate`, das sie über `steuerbote.eric.secrets` mit dem Schlüssel der Site verschlüsselt höchstens 15 Minuten im Zwischenspeicher ablegt. Der Job bekommt nur den Token und holt sie einmal ab.
4. Der Job schreibt die Nutzdaten mit `ustva_xml.to_nutzdaten`, aus demselben Baum wie die Datei für Mein ELSTER und mit der Hersteller-ID in Kz 09, und den Kopf der Lieferung als `EnvelopeHeader`. Hersteller-ID, Produktdaten und Datenlieferant kommen aus den ERiC-Einstellungen, das Finanzamt aus den ersten vier Stellen der Steuernummer im ELSTER-Format.
5. Außerhalb der Simulation sucht `runtime.detect` die Laufzeit für das Jahr der Meldung, eine Beta nur zum Testsenden, mit einem Verzeichnis für `eric.log` je Übermittlung. `service.run` ruft damit den Worker auf, ohne Laufzeit die Simulation.
6. Das Ergebnis geht in die ELSTER-Übermittlung: Status, Ergebnis laut ERiC, Transferticket, Nachrichten und Dateien. Nur ein Senden, das ELSTER angenommen hat, bucht die Meldung. Scheitert das Buchen, steht der Grund mit dem Transferticket in der Übermittlung, und die Meldung bleibt ein Entwurf, der sich nicht noch einmal senden lässt.
7. Zum Schluss gibt der Job die Sperre frei und meldet das Ergebnis dem Benutzer.

| Ergebnis laut ERiC | Status |
|---|---|
| Gültig, Angenommen | Erfolgreich |
| Ungültig, Abgelehnt, fehlgeschlagen | Fehlgeschlagen |
| Unbekannt | Unbekannt; die Meldung lässt sich nicht noch einmal senden, bis jemand in Mein ELSTER nachgesehen und ein System Manager die Übermittlung gelöscht hat |

`vat_return/transmission_adapter.py` enthält die Aufrufe, die ein eingerichtetes ERiC brauchen: Worker, Laufzeit des Jahres und Installation, mit den Pfaden und dem Benutzer der Site. Die Tests ersetzen nur diese Aufrufe und lassen XML, Kopf, Ablage von Zertifikat und Passwort und Simulation wirklich laufen. Mit der Stub-Bibliothek der ERiC-Tests richtet ein Test eine Laufzeit aus einem Archiv ein und sendet durch den Worker.

## Was wo berechnet wird

| Was | Wo |
|---|---|
| Kennzahlen, Rundung, Summen der Zeilen 37, 45 und 48, Kz 83, Verprobung | `calculate()` im Kern |
| gemeldete Beträge nach Korrekturen und die Summen darüber | Kern: `bridge.filing` gibt die gemeldeten Beträge noch einmal in `calculate()` |
| Voranmeldungszeitraum, Zeitraumcode, Fälligkeit | `Period` im Kern, Rhythmus aus `vat_return_settings/rules.py` |
| Kz 39 | `bridge.sondervorauszahlung_values` aus den Einstellungen |
| Steuernummer im ELSTER-Format | `steuerbote/elster` |
| XML für Mein ELSTER und ERiC, mit Kz 83 aus den geschriebenen Werten nachgerechnet | `steuerbote/elster/ustva_xml.py` |
| Kopf der Lieferung, Hersteller-ID, Finanzamt und Testmerker | `envelope_header` in `vat_return.py`, geprüft von `steuerbote/eric/header.py` |
| Laufzeit des Jahres, Ergebnis eines Laufs | `steuerbote/eric/runtime.py`, `steuerbote/eric/service.py` mit Worker oder Simulation |
| Belege hinter jeder Kennzahl | `attribution.py` mit den Regeln von `calculate()` |
| Druckformat | rechnet keine Kennzahl, nur was der Vordruck selbst bildet: die Zeilen 45 und 48 aus den gespeicherten Summen und die Steuer der Zeilen 13, 14, 25 und 26 aus der Bemessungsgrundlage in vollen Euro |

## Bericht „UStVA Kennzahlen“

Der Bericht zeigt für einen Zeitraum, aus welchen Buchungen jede Kennzahl besteht. Filter sind Unternehmen, Jahr, Abgaberhythmus und Nummer des Zeitraums.

- Er liest dasselbe wie „Berechnen“: die Abfrage des Hauptbuchs mit denselben Ausschlüssen, die Kontenzuordnung und die Einstellungen des Unternehmens, im letzten Zeitraum des Jahres also auch Kz 39.
- Je Kennzahl steht eine Zeile in der Reihenfolge des Vordrucks mit Kennzahl, Zeile im Vordruck, Bezeichnung, Betrag laut Hauptbuch und Betrag laut Vordruck. Darunter folgt eine Ebene tiefer je Beleg eine Zeile mit Buchungsdatum, Belegtyp, Belegnr., Konto, Soll, Haben und dem Betrag, den der Beleg beiträgt. Die Summen der Zeilen 37, 45 und 48 und Kz 83 stehen an ihrer Stelle im Vordruck.
- Ein Konto mit Regel trägt je Beleg seinen Saldo auf der Seite der Regel bei, mit zusätzlicher Kennzahl auch dort. Eine abgeleitete Steuer, etwa Kz 47 zu Kz 46, entsteht je Beleg aus der Summe seiner Bemessungsgrundlagen zu einem Steuersatz und wird einmal gerundet, wie in `calculate()`. Ihre Belegzeile zeigt die Buchungen der Grundlagenkonten und die Steuer als Betrag.
- Die Belege einer Kennzahl ergeben genau ihren Betrag laut Hauptbuch. Heben sich die Belege einer Kennzahl auf, steht sie mit 0 im Bericht.
- Der Bericht zeigt das Hauptbuch, keine Meldung: Korrekturen einer Meldung erscheinen darin nicht.

## Arbeitsbereich „Steuern“

Der Arbeitsbereich führt zu „Neue Umsatzsteuer-Voranmeldung“, zur Liste der Umsatzsteuer-Voranmeldungen, zum Bericht „UStVA Kennzahlen“ und zu den Einstellungen und der Kontenzuordnung. Die Zahlenkarte „Offene Voranmeldungen“ zählt die Meldungen aller Unternehmen, die noch nicht eingereicht sind. Sichtbar ist der Arbeitsbereich für die Rollen Accounts Manager, Accounts User und System Manager.

## Druckformat „Umsatzsteuer-Voranmeldung“

Das Druckformat gibt eine Meldung in Reihenfolge und Wortlaut des Vordrucks USt 1 A 2026 aus, auf A4, schwarz und grau, ohne Logo und ohne Briefkopf.

- **Kopf:** Unternehmen, Steuernummer, Steuernummer im ELSTER-Format und Finanzamt aus den Einstellungen, Voranmeldungszeitraum, Fälligkeit, Name und Status der Meldung.
- **Vordruck:** die Zeilen 10 und 11 (Kz 10 und 22), dann die Abschnitte A bis J und die ergänzenden Angaben zur Steueranmeldung (Kz 500 mit Begründung). Jede Zeile zeigt Zeile, Bezeichnung, Kennzahl und Bemessungsgrundlage in vollen Euro sowie Kennzahl und Steuer in Euro und Cent. Ein Abschnitt ohne Werte sagt „Keine Eintragungen“. Die Zeilen 37, 45 und 48 und Kz 83 stehen immer da.
- **Darunter:** die Korrekturen gegenüber dem Hauptbuch mit Begründung und die Anmerkungen, wenn es sie gibt.
- **Fußzeile:** „Zum Abgleich mit der Steuerberatung oder zum Übertragen in Mein ELSTER.“ und der Hinweis, dass der Ausdruck keine Abgabe ist.

Das Druckformat liest nur die Meldung und die Einstellungen ihres Unternehmens. Die Zeilen der Kennzahlen tragen Kennzahl, Zeile, Bezeichnung und Art des Betrags aus dem Katalog des Jahres der Meldung, die Meldung schreibt sie bei jedem Speichern neu. Abschnitte und Steuersätze des Ausdrucks gehören zum Vordruck 2026. Ein neuer Jahrgang braucht deshalb auch hier eine Prüfung Zeile für Zeile, wie der Katalog.

## Für die Steuerberatung zu klären

Steuerbote ersetzt keine Steuerberatung. Diese Punkte entscheidet die Steuerberatung für jedes Unternehmen, bevor die erste Meldung abgegeben wird:

1. **Einordnung von Handelsergebnissen.** Ob Erträge und Aufwendungen aus dem Handel, etwa mit Wertpapieren, Devisen oder Derivaten, in der Voranmeldung erscheinen, als nicht steuerbar, steuerfrei ohne Vorsteuerabzug (Kz 48) oder steuerpflichtig, und auf welche Konten sie dafür gebucht werden. Konten ohne Regel gehen in keine Kennzahl ein.
2. **Vorsteueraufteilung nach § 15 Absatz 4 UStG.** Hat ein Unternehmen auch Umsätze, die den Vorsteuerabzug ausschließen, ist die Vorsteuer aufzuteilen. Steuerbote meldet die Vorsteuer so, wie sie gebucht ist, und teilt nichts auf. Aufteilung und Buchung des nicht abziehbaren Teils sind abzustimmen.
3. **Freigabe der Kontenzuordnung.** Die Vorgaben für SKR03 und SKR04 sind von keiner Steuerberatung bestätigt. Die Kontenzuordnung jedes Unternehmens, mit Verprobungen und beobachteten Konten, gibt die Steuerberatung frei.
4. **Voranmeldungszeitraum.** Ob monatlich, vierteljährlich oder keine Voranmeldung abzugeben ist, legt das Finanzamt fest (§ 18 Absatz 2 UStG), ebenso Dauerfristverlängerung und Sondervorauszahlung. Die Einträge in den Einstellungen sind je Jahr mit den Bescheiden abzugleichen.
