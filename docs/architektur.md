# Architektur

Steuerbote besteht aus zwei Schichten. Der Rechenkern unter `steuerbote/ustva` kennt die Kennzahlen des Vordrucks, rundet, ordnet Konten zu, rechnet und prüft, alles in reinem Python ohne Frappe. Die Frappe-Schicht liest das Hauptbuch und die Einstellungen aus ERPNext, übergibt sie dem Kern und hält das Ergebnis in DocTypes, einem Bericht, einem Arbeitsbereich und einem Druckformat fest. Über die ERiC-Anbindung unter `steuerbote/eric` übermittelt sie die Meldung, den Vordruck der Dauerfristverlängerung und die Zusammenfassende Meldung an ELSTER. Ebenso rechnen eigene Kerne die Zusammenfassende Meldung (`steuerbote/zm`, siehe [Zusammenfassende Meldung](zm.md)), die Bestätigung ausländischer USt-IdNrn. (`steuerbote/vatid`, siehe [Prüfung ausländischer USt-IdNrn.](ust-idnr-pruefung.md)) und die Dauerfristverlängerung (`steuerbote/dauerfrist`). Diese Seite beschreibt die Frappe-Schicht. Die fachlichen Regeln des Kerns stehen in [Kennzahlen und Kontenzuordnung](ustva-kennzahlen.md), Aufbau, Tests und Stil in [Entwicklung](entwicklung.md).

## Der Kern rechnet, die Frappe-Schicht liest und speichert

Jeder Betrag einer Meldung kommt aus dem Kern: Kennzahlen, Rundung, die Summen des Vordrucks, Kz 83, Verprobung, Zeiträume und Fristen. Die Frappe-Schicht wandelt nur Daten um. Was sich dabei ohne Datenbank prüfen lässt, steht in eigenen Modulen ohne Frappe-Import mit Unit-Tests, damit die Controller der DocTypes dünn bleiben.

| Modul | Aufgabe |
|---|---|
| `steuerbote/ledger.py` | liest das Hauptbuch eines Zeitraums als Buchungszeilen des Kerns und die Namen und Bezeichnungen von Konten, mit Frappe |
| `steuerbote/invoices.py` | liest die eingereichten Rechnungen eines Zeitraums als Rechnungszeilen für die Hinweise, mit Frappe |
| `steuerbote/ustva/plausibility.py` | stellt die Kennzahlen einer Meldung neben Vorperiode und Vorjahr und leitet die Hinweise aus Rechnungen, Hauptbuch und Vergleich ab, im Kern ohne Frappe |
| `steuerbote/mapping_sync.py` | macht aus den Zeilen der Kontenzuordnung die `Mapping` des Kerns und kürzt die Vorgaben auf die Konten eines Unternehmens |
| `steuerbote/elster/` | bildet aus Steuernummer und Bundesland die 13-stellige Steuernummer im ELSTER-Format, schreibt die Meldung als XML für Mein ELSTER und ERiC (`ustva_xml.py`, siehe [Abgabe über Mein ELSTER](abgabe-mein-elster.md)) den Vordruck USt 1 H als XML für ERiC (`ust1h_xml.py`, siehe [XML für ERiC](dauerfristverlaengerung.md#xml-für-eric)) und die Zusammenfassende Meldung als XML für ERiC (`zm_xml.py`, siehe [ZM über ERiC](zm.md#zm-über-eric)) |
| `vat_return_settings/rules.py` | Voranmeldungszeitraum je Monat, Dauerfristverlängerung und Sondervorauszahlung je Jahr, Abgaberhythmus der Zusammenfassenden Meldung und eigene USt-IdNr. |
| `vat_return/bridge.py` | überträgt das Ergebnis des Kerns in die Tabellen der Meldung, auch Vorperiodenvergleich und Hinweise, bildet die Summen über die gemeldeten Beträge und übergibt die Meldung und den Datenlieferanten an das XML |
| `report/ustva_kennzahlen/attribution.py` | findet die Belege, aus denen jede Kennzahl besteht |
| `report/ustva_kennzahlen/comparison.py` | stellt jede Kennzahl und Summe des Berichts neben Vorperiode und Vorjahr und wählt die Abweichungen aus |
| `steuerbote/holiday_list.py` | liest die Feiertage der Fristen von Zusammenfassender Meldung und Dauerfristverlängerung aus der Standard-Feiertagsliste des Unternehmens, ohne die wöchentlich freien Tage (`deadline_holidays` in `ustva/period.py`), mit Frappe |
| `steuerbote/zm_sources.py` | liest für die Zusammenfassende Meldung die Beiträge der Belege zu Kz 41, 42 und 21, die Kunden der Belege, Kz 41 und 42 je Monat für die Schwelle, die abgegebenen Voranmeldungen und Name und Anschrift eines Kunden, mit Frappe |
| `recapitulative_statement/bridge.py` | überträgt Zeilen, Belege, Befunde, Abgleich und Vorperiodenvergleich des Kerns in die Tabellen der Zusammenfassenden Meldung, liest Korrekturen und Bestätigungen aus ihnen zurück und gibt `zm_xml` die Meldung (`zm`) und den Unternehmer aus den Einstellungen (`unternehmer`) |
| `vat_id_confirmation/records.py` | macht aus jeder Abfrage einer Bestätigung die Felder einer USt-IdNr.-Bestätigung und das Ergebnis der Prüfung bis zu ihr |
| `steuerbote/dauerfrist_sources.py` | liest für die Dauerfristverlängerung die abgegebenen Voranmeldungen eines Jahres mit Kz 83 und Kz 39 und das Gründungsdatum des Unternehmens, mit Frappe |
| `vat_return_extension/bridge.py` | wählt die abgegebenen Voranmeldungen des Vorjahres, deren Kz 83 und Kz 39 die Grundlage bilden, nennt die Voranmeldungszeiträume, die ihr fehlen, gibt Grundlage, Grundlage von Hand und Monate der Tätigkeit an den Kern und bildet den Vordruck USt 1 H aus den Feldern des Belegs |
| `elster_transmission/transmission.py` | Prüfen, Testsenden und Senden eines Belegs über ERiC: `Transmittable`, von dem Voranmeldung, Dauerfristverlängerung und Zusammenfassende Meldung erben, den Hintergrundjob `run_transmission`, `stash_certificate`, den Kopf der Lieferung mit den Angaben der Datenart des Belegs, die Verknüpfungen eines Belegs zu seinen ELSTER-Übermittlungen und seinen letzten abgeschlossenen Lauf (`latest_run`), siehe [Übermittlung an ELSTER](#übermittlung-an-elster) |
| `elster_transmission/messages.py` | zählt die Fehler und Hinweise einer ELSTER-Übermittlung und gibt die ersten jeder Art an das Formular ihres Belegs |
| `steuerbote/steuerbote/record_files.py` | hält die Dateien einer ELSTER-Übermittlung und die Antwort einer USt-IdNr.-Bestätigung, wie sie abgelegt wurden: `doc_events` für File, die gegen die gespeicherte Datei prüfen und Lösen, Umhängen, Veröffentlichen, Umbenennen und Löschen ablehnen, solange es den Beleg gibt, siehe [Wo XML und Protokoll liegen](uebermittlung.md#wo-xml-und-protokoll-liegen) |
| `public/js/elster_transmission.js` | Schaltflächen, Dialog für Zertifikat und Passwort, Hinweise der Übermittlung und die Fehler und Hinweise des letzten Laufs, die die Formulare von Voranmeldung, Dauerfristverlängerung und Zusammenfassender Meldung mit `{% include %}` einbinden |
| `steuerbote/steuerbote/deadlines.py` | liest Einstellungen, Belege, Feiertage und Hauptbuch jedes Unternehmens für die Fristen, die der Kern unter `steuerbote/deadlines` bildet, für den Bericht „Offene Fristen“ und die tägliche Erinnerung mit ihren Fristerinnerungen, mit Frappe, siehe [Fristen](fristen.md) |

So läuft „Berechnen“ an einer Meldung:

1. Die Meldung bestimmt aus Jahr, Abgaberhythmus und Nummer ihren Zeitraum und prüft ihn gegen die Einstellungen des Unternehmens. Diese liefern auch die Dauerfristverlängerung für die Fälligkeit und, im letzten Zeitraum des Jahres, die Sondervorauszahlung für Kz 39.
2. `ledger.load_lines` liest die Buchungen (GL Entry) des Zeitraums.
3. Die Kontenzuordnung des Unternehmens wird über `mapping_sync.rows_to_mapping` zur `Mapping` des Kerns, geprüft gegen den Vordruck des Jahres der Meldung.
4. `calculate()` rechnet Kennzahlen, Summen, Kz 83 und Verprobung.
5. `bridge.py` schreibt das Ergebnis in die Tabellen der Meldung. Bei jedem Speichern rechnet der Kern Summen und Kz 83 aus den gemeldeten Beträgen neu, damit Korrekturen mit Begründung darin eingehen.
6. `build_comparison` rechnet Vorperiode und Vorjahr aus dem Hauptbuch, `build_hints` liest die Rechnungen des Zeitraums und nimmt aus dem Ergebnis des Kerns die Salden der beobachteten Konten der Stufe „Hinweis“; beide füllen die Tabellen „Vorperiodenvergleich“ und „Hinweise“, siehe [Vorperiodenvergleich und Hinweise](#vorperiodenvergleich-und-hinweise).

## DocTypes

DocTypes heißen nach der Konvention von Frappe englisch. Die Oberfläche zeigt die deutschen Bezeichnungen aus `steuerbote/translations/de.csv`.

### Einstellungen Umsatzsteuer-Voranmeldung (`VAT Return Settings`)

Ein Dokument je Unternehmen, sein Name ist das Unternehmen. Anlegen und ändern dürfen es Accounts Manager und System Manager, Accounts User lesen es nur: Steuernummer, Voranmeldungszeiträume, Sondervorauszahlung und Toleranz entscheiden, was an welches Finanzamt geht, und Steuerbote liest sie bei jedem Vorgang neu, siehe [Übermittlung an ELSTER](uebermittlung.md#die-vorgänge).

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company` | Unternehmen | Pflicht |
| `chart` | Kontenrahmen | SKR03, SKR04 oder Eigener Kontenrahmen |
| `taxation_type` | Besteuerung | nur Soll; die Ist-Versteuerung wird noch nicht unterstützt |
| `tolerance` | Toleranz je Beleg | wie weit die gebuchte Steuer eines Belegs in der Verprobung abweichen darf, Vorgabe 0,01 EUR |
| `comparison_threshold_percent`, `comparison_threshold_amount` | Schwelle Vorperiodenvergleich (%), Schwelle Vorperiodenvergleich (EUR) | ab wann eine Kennzahl gegenüber der Vorperiode auffällig ist, Vorgabe 50 % und 100 EUR; gelten für die Meldung und den Bericht „UStVA Kennzahlen“ |
| `state` | Bundesland | Pflicht |
| `tax_number` | Steuernummer | Pflicht, wie vom Finanzamt vergeben; das Format wird gegen das Bundesland geprüft |
| `elster_tax_number` | Steuernummer im ELSTER-Format | 13 Stellen, berechnet |
| `tax_office` | Finanzamt | |
| `wid_nr` | Wirtschafts-Identifikationsnummer | freiwillig, „DE“ und neun Ziffern ohne die fünfstellige Ergänzung |
| `ust_idnr` | USt-IdNr. | die eigene deutsche USt-IdNr., „DE“ und neun Ziffern, mit der Steuerbote die USt-IdNrn. der Kunden bestätigen lässt; leer übernimmt das Speichern das Feld „Steuernummer“ (`tax_id`) des Unternehmens, wenn es eine deutsche USt-IdNr. ist |
| `teilnehmernummer` | Teilnehmernummer beim BZSt | für die Zusammenfassende Meldung über ERiC, nur wenn das BZSt dem Unternehmen einmal eine vergeben hat: sieben oder acht Ziffern ab 0300000 (Regel 170015024 der Jahresdokumentation ZMDO, geprüft mit `zm_xml.teilnehmernummer`); leer schreibt die Meldung 1111111, siehe [Was die Nutzdaten enthalten](zm.md#was-die-nutzdaten-enthalten) |
| `filer_name`, `street`, `postal_code`, `city`, `phone`, `email` | Name, Straße und Hausnummer, Postleitzahl, Ort, Telefon, E-Mail | Datenlieferant der Datei für ELSTER und mit der USt-IdNr. der Unternehmer der Zusammenfassenden Meldung für ERiC (`unternehmer` in `recapitulative_statement/bridge.py`), Längen wie im Schema (45, 30, 12, 30, 20 und 70 Zeichen); Name, Straße, Postleitzahl und Ort braucht die Datei. Ein leeres Feld füllt das Speichern (`set_datenlieferant`) mit `bridge.datenlieferant_defaults` aus dem Unternehmen: Name, Telefon und E-Mail des Unternehmens, Straße (`address_line1`), Postleitzahl und Ort seiner Adresse, die `get_default_address` von Frappe wählt, Telefon und E-Mail ersatzweise aus ihr; einen Wert, den ELSTER nicht nimmt, übernimmt es nicht |
| `period_rules` | Voranmeldungszeiträume | Pflicht; Tabelle „Regel zum Voranmeldungszeitraum“ mit Jahr, Voranmeldungszeitraum (monatlich, vierteljährlich oder keine) und „Gültig ab Monat“ (1, 4, 7 oder 10) |
| `prepayments` | Dauerfristverlängerung und Sondervorauszahlung | Tabelle „Dauerfristverlängerung je Jahr“ mit Jahr, Dauerfristverlängerung und Sondervorauszahlung |
| `zm_rules` | Abgaberhythmus der Zusammenfassenden Meldung | Tabelle „Regel zur Zusammenfassenden Meldung“ mit Jahr, Gültig ab Monat, Abgaberhythmus (monatlich, vierteljährlich oder jährlich), Sonstige Leistungen monatlich und Grund; geprüft von `steuerbote/zm/rhythm.py` |

### Kontenzuordnung Umsatzsteuer (`VAT Return Mapping`)

Ein Dokument je Unternehmen, sein Name ist das Unternehmen.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company` | Unternehmen | Pflicht |
| `chart` | Kontenrahmen | bestimmt die Vorgabe für „Vorgaben laden“ |
| `rules` | Zuordnungen | Tabelle „Regel der Kontenzuordnung Umsatzsteuer“: Konto, Kontonummer (aus dem Konto), Kennzahl, Seite (Haben oder Soll), Steuersatz (%; leer oder 0 heißt kein Satz, die Tabelle zeigt ihn dann leer), Zusätzliche Kennzahl und Seite der zusätzlichen Kennzahl |
| `checks` | Verprobungen | Tabelle „Verprobung der Kontenzuordnung Umsatzsteuer“: Bezeichnung, Grundlagenkonten und Steuerkonten (Kontonummern, durch Kommas getrennt), Seite |
| `watched` | Beobachtete Konten | Tabelle „Beobachtetes Konto der Kontenzuordnung Umsatzsteuer“: Konto, Kontonummer und Stufe: „Sperrt“ (Vorgabe) hält die Meldung bei einem Saldo an, „Hinweis“ ergibt dann nur einen Hinweis |

### Umsatzsteuer-Voranmeldung (`VAT Return`)

Einreichbar, Nummernkreis `UStVA-.{year}.-.#####`: Das Jahr im Namen ist das Jahr der Meldung (Feld `year`), nicht das Jahr, in dem sie angelegt wird, siehe [Nummern nach dem Jahr des Belegs](#nummern-nach-dem-jahr-des-belegs).

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
| `ready` | Bereit zur Abgabe | alle Verprobungen gehen auf und kein beobachtetes Konto der Stufe „Sperrt“ hat einen Saldo |
| `checks` | Verprobung | Tabelle „Verprobung der Umsatzsteuer-Voranmeldung“: Verprobung, Berechnete Steuer, Gebuchte Steuer, Unterschied, Abweichende Belege und Verprobung aufgegangen |
| `deviations` | Abweichende Belege | Tabelle „Abweichender Beleg der Verprobung“: Verprobung, Belegtyp, Belegnr., Berechnete Steuer, Gebuchte Steuer und Unterschied |
| `unmapped` | Beobachtete Konten mit Saldo | Tabelle „Beobachtetes Konto mit Saldo“: Kontonummer, Konto, Soll und Haben der Konten der Stufe „Sperrt“; den Saldo eines Kontos der Stufe „Hinweis“ nennt ein Hinweis |
| `accounts_without_number` | Konten ohne Kontonummer | Zahl der Konten, die in keine Kennzahl eingehen können |
| `hints` | Hinweise | Tabelle „Hinweis zur Umsatzsteuer-Voranmeldung“: Art (Hinweis oder Warnung), Code, Nachricht, Belegtyp, Belegnr. und Partei; füllt „Berechnen“, hält die Meldung nie an |
| `comparison` | Vorperiodenvergleich | Tabelle „Vorperiodenvergleich der Umsatzsteuer-Voranmeldung“: Kennzahl, Beschreibung, Dieser Zeitraum, Vorperiode, Vorjahr, Differenz zur Vorperiode, Differenz (%) und Auffällig; füllt „Berechnen“ |
| `attachments` | Belege beigefügt oder gesondert eingereicht (Kz 22) | Kennzeichen des Vordrucks |
| `regelbesteuerung_from` | Datum des Wechsels zur Regelbesteuerung (Kz 70) | Zeile 12 des Vordrucks, nur in den Fällen der Anleitung zu Zeile 12 (USt 1 E 2026): der Tag des Umsatzes, mit dem der Gesamtumsatz 100.000 Euro überschritten hat, im Jahr der Gründung 25.000 Euro, oder der 1. Januar nach dem Verzicht auf die Kleinunternehmer-Regelung (§ 19 Absatz 3 UStG). Das Speichern lehnt ein Datum außerhalb des Jahres der Meldung ab (Regel 11085153 der Jahresdokumentation UStVA 2026). Kz 70 trägt keinen Betrag und ändert keine Summe. |
| `offset_requested` | Verrechnung erwünscht oder Erstattungsbetrag abgetreten (Kz 29) | Kennzeichen des Vordrucks |
| `no_sepa_mandate` | SEPA-Lastschriftmandat ausnahmsweise nicht verwenden (Kz 26) | Kennzeichen des Vordrucks |
| `supplementary_code` | Ergänzende Angaben zur Steueranmeldung (Kz 500) | Schlüssel 1 bis 4 |
| `kz500_begruendung` | Begründung zu Kz 500 | Pflicht mit Kz 500 und nur mit ihr, höchstens 180 Zeichen in einer Zeile |
| `remarks` | Anmerkungen | Pflicht, wenn eine Meldung abgegeben wird, die nicht bereit ist |
| `transmission_in_progress` | Übermittlung läuft | gesetzt, solange Prüfen, Testsenden oder Senden läuft; so lange lässt sich die Meldung nicht ändern |

An der Meldung stehen unter „Verknüpfungen“ ihre ELSTER-Übermittlungen. Über dem Formular nennt sie die Fehler und Hinweise ihres letzten abgeschlossenen Prüfens, Testsendens oder Sendens, siehe [Übermittlung an ELSTER](#übermittlung-an-elster).

### ERiC-Einstellungen (`ERiC Settings`)

Ein Dokument für die ganze Installation (Single), nur für den System Manager. Hersteller-ID und Laufzeitumgebung gehören zur Software, nicht zu einem Unternehmen.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `simulation` | Simulationsmodus | berechnet: aktiv, solange keine Laufzeitumgebung installiert oder keine Hersteller-ID eingetragen ist |
| `hersteller_id` | Hersteller-ID | fünf Ziffern nach der Regel von Kz 09, nicht 74931 |
| `produkt_name`, `produkt_version` | Produktname, Produktversion | für den NutzdatenHeader; der Name hat höchstens 50 Zeichen und enthält nicht „ELSTER“, die Version ist die von Steuerbote |
| `datenlieferant` | Datenlieferant | für den Kopf der Lieferung, höchstens 256 Zeichen |
| `archive_path`, `archive_sha256` | ERiC-Archiv, SHA-256 des Archivs | nur zur Anzeige: absoluter Pfad des Archivs auf dem Server und seine Prüfsumme, wie `steuerbote_eric_archive` und `steuerbote_eric_archive_sha256` der `common_site_config.json` sie nennen; die Installation liest sie dort selbst (`transmission_adapter.configured_archive`) |
| `installed_version`, `lib_dir`, `log_dir`, `last_check` | Installierte Version, Verzeichnis der Bibliotheken, Verzeichnis der Logdateien, Letzte Prüfung | setzt die Installation |
| `privacy_notice_confirmed`, `privacy_notice_confirmed_by`, `privacy_notice_confirmed_on` | Datenschutzhinweise gelesen und bestätigt, Bestätigt von, Bestätigt am | die Bestätigung nach § 5 Abs. 1 und 2 des ERiC-Lizenzvertrags; wer sie gibt und wann, setzt das Speichern. Ohne sie läuft kein Vorgang mit ERiC, die Simulation hängt nicht davon ab. |
| `minimum_list_version`, `minimum_list_modified`, `minimum_eric_version`, `versions_checked_on`, `versions_check_failed`, dazu verborgen `minimum_versions` und `version_notices` | Version der Mindestversionsliste, Mindestversionsliste geändert am, Mindestversion von ERiC, Versionen zuletzt geprüft, Versionsprüfung fehlgeschlagen | setzt nur die wöchentliche Prüfung `check_versions`, ein Speichern behält sie: die Mindestversionsliste von ELSTER mit ihrer Version, dem Stand laut Server und den Mindestversionen von Linux Intel, die Mindestversion von `libericapi.so`, wann geprüft wurde und ob es fehlschlug, und die Befunde, von denen die System Manager schon wissen, siehe [ERiC](eric.md#betrieb-und-updates) |
| `proxy_url`, `proxy_user`, `proxy_password` | Proxy-URL, Benutzer des Proxys, Passwort des Proxys | der Proxy, über den ERiC die Server von ELSTER erreicht, geprüft von `steuerbote/eric/proxy.py`; das Passwort ist ein Passwortfeld. Ohne URL entfallen Benutzer und Passwort. `transmission_adapter.run` gibt den Proxy jedem Lauf mit Laufzeit mit, siehe [ERiC](eric.md#proxy). |

„Laufzeitumgebung prüfen“ (`check_runtime`, nur für den System Manager) zeigt die Prüfungen von `steuerbote.eric.runtime.status` über `transmission_adapter.runtime_status`: Plattform, eingerichtete Laufzeitumgebung, ihre Bibliotheken, das Plugin des laufenden Jahres, das Plugin `checkZMDO` der Zusammenfassenden Meldung und die Hersteller-ID, siehe [ERiC](eric.md#statusprüfung). Danach folgen die von `steuerbote.eric.releases`: der Abgleich mit der Mindestversionsliste, die die wöchentliche Prüfung geladen hat, und das Plugin des kommenden Jahres. Die Prüfung ändert nichts.

### ELSTER-Übermittlung (`ELSTER Transmission`)

Ein Dokument je Lauf von Prüfen, Testsenden oder Senden und je Vermerk einer Abgabe außerhalb von Steuerbote, für eine Umsatzsteuer-Voranmeldung, eine Dauerfristverlängerung oder eine Zusammenfassende Meldung, Nummernkreis `ELSTER-{YYYY}-{#####}`. Nur der Server schreibt es; nach der Aufzeichnung bleibt es, wie es ist.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `document_type`, `document`, `company` | Dokumententyp, Dokument, Unternehmen | der Beleg als Dynamic Link, `VAT Return`, `VAT Return Extension` oder `Recapitulative Statement` (`DOCUMENT_TYPES`), und sein Unternehmen |
| `operation` | Vorgang | `validate`, `test_send`, `send` oder `extern` |
| `status` | Status | Läuft, Erfolgreich, Fehlgeschlagen oder Unbekannt |
| `outcome` | Ergebnis laut ERiC | `valid`, `invalid`, `accepted`, `rejected`, `failed` oder `unknown` aus `steuerbote.eric.result.Outcome` |
| `simulated` | Simuliert | der Lauf ging an die Simulation |
| `started_at`, `finished_at`, `user` | Gestartet am, Beendet am, Benutzer | |
| `transferticket`, `testmerker`, `eric_version` | Transferticket, Testmerker, ERiC-Version | aus dem Ergebnis |
| `filed_via`, `filed_on` | Abgegeben über, Abgegeben am | bei einem Vermerk: `mein_elster` oder `other_way` und der Tag der Abgabe |
| `remarks` | Anmerkungen | der Vermerk einer Abgabe außerhalb von Steuerbote |
| `messages` | Nachrichten | Tabelle „Meldung der ELSTER-Übermittlung“: Art (Fehler oder Hinweis), Code, Nachricht und Feld |
| `xml`, `protocol_pdf`, `response_xml` | Nutzdaten (XML), Protokoll (PDF), Antwort des ELSTER-Servers (XML) | private Dateien der Übermittlung |

Bis Version 0.2 nannte eine ELSTER-Übermittlung ihre Meldung im Feld `vat_return`, einem Link auf die Umsatzsteuer-Voranmeldung. Der Patch `steuerbote/patches/link_transmissions_to_their_document.py` läuft bei `bench migrate` nach dem Abgleich der DocTypes (`post_model_sync`): Frappe behält die Spalte eines Felds, das den DocType verlässt, also trägt er deren Wert als `document` mit dem `document_type` `VAT Return` ein und lässt Übermittlungen, die ihr Dokument schon nennen, wie sie sind. Die alte Spalte entfernt `bench trim-tables`. Die Verknüpfungen eines Belegs zu seinen Übermittlungen stehen nicht in der DocType-Datei, deren Tabelle `links` keinen Dynamic Link kennt, sondern in `<doctype>_dashboard.py` mit `dynamic_links` (`transmission.dashboard`).

### Zusammenfassende Meldung (`Recapitulative Statement`)

Einreichbar, Nummernkreis `ZM-.{year}.-.#####` mit dem Jahr der Meldung, siehe [Nummern nach dem Jahr des Belegs](#nummern-nach-dem-jahr-des-belegs). Wie die Meldung arbeitet, steht in [Die Zusammenfassende Meldung](#die-zusammenfassende-meldung) und in [Zusammenfassende Meldung](zm.md#die-zusammenfassende-meldung-in-erpnext).

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company`, `year` | Unternehmen, Jahr | Pflicht |
| `period_kind`, `period_index` | Art des Meldezeitraums, Nummer des Zeitraums | Kalendermonat, zwei Monate eines Quartals, Kalendervierteljahr oder Kalenderjahr (`zm.period.Kind`); Monat 1 bis 12 oder Quartal 1 bis 4 |
| `meldeart`, `corrects` | Meldeart, Berichtigt | Erstmeldung oder Berichtigung, gesetzt von „Berichtigung anlegen“ mit der Meldung, die sie berichtigt |
| `anzeige`, `widerruf` | Anzeige der monatlichen Abgabe, Widerruf der Anzeige | Kennzeichen im Formular von Mein ELSTER, geprüft mit `check_notices()` |
| `period_label`, `quart`, `from_date`, `to_date`, `deadline` | Meldezeitraum, Zeitraumcode, Von-Datum, Bis-Datum, Fälligkeitsdatum | berechnet, etwa „März 2026“ und 23; fällig am 25. Tag nach Ablauf, sonst am nächsten Werktag nach der Feiertagsliste des Unternehmens |
| `goods_from`, `goods_to`, `services_from`, `services_to` | Lieferungen von, Lieferungen bis, Sonstige Leistungen von, Sonstige Leistungen bis | berechnet: erster und letzter Tag der Monate, deren Lieferungen und deren sonstige Leistungen die Meldung meldet (`coverage()`); eine abgegebene Meldung behält sie |
| `status` | Status | Entwurf, Berechnet, Bereit, Abgegeben oder Ersetzt; setzt nur Steuerbote, an einer eingereichten Meldung nur die Abgabe einer Berichtigung, die sie auf „Ersetzt“ setzt |
| `confirmation_in_progress` | Prüfung läuft | gesetzt, solange „USt-IdNrn. prüfen“ läuft; so lange lässt sich die Meldung nicht ändern und nicht übermitteln |
| `transmission_in_progress` | Übermittlung läuft | gesetzt, solange Prüfen, Testsenden oder Senden läuft; so lange lässt sich die Meldung nicht ändern, und ihre USt-IdNrn. werden nicht geprüft |
| `lines` | Meldezeilen | Tabelle „Zeile der Zusammenfassenden Meldung“: USt-IdNr., Art der Leistung, Kunde, Betrag laut Hauptbuch, Korrigierter Betrag mit Begründung, Gemeldeter Betrag, Hält die Meldung an, Von Hand (eine eigene Zeile ohne Beleg, siehe [Zeilen von Hand](zm.md#zeilen-von-hand)), Bisher gemeldet, In der Datei und die letzte Prüfung der Nummer (Geprüft am, Dienst, Ergebnis der Prüfung, Code, Nummer der Abfrage, USt-IdNr.-Bestätigung) |
| `total_l`, `total_d`, `total_s` | Summe L, Summe D, Summe S | Summen der Meldezeilen je Art |
| `ready` | Bereit zur Abgabe | keine Zeile gesperrt, keine Schwelle überschritten und jeder Beleg im Hauptbuch wiedergefunden |
| `hints` | Befunde | Tabelle „Befund der Zusammenfassenden Meldung“: Art (Fehler oder Hinweis), Code, Nachricht, Belegtyp, Belegnr. und Partei |
| `reconciliation` | Abgleich mit der Voranmeldung | Tabelle „Abgleich der Zusammenfassenden Meldung“ je Art: Kennzahl, Betrag laut Hauptbuch, Betrag in den Meldezeilen, Unterschied, Gemeldeter Betrag, Laut abgegebenen Voranmeldungen, Abweichende Belege, Abgeglichen und Zeilen von Hand, der Teil des gemeldeten Betrags ohne Beleg im Hauptbuch |
| `comparison` | Vorperiodenvergleich | Tabelle „Vorperiodenvergleich der Zusammenfassenden Meldung“: USt-IdNr., Art der Leistung, Dieser Zeitraum, Vorperiode, Differenz zur Vorperiode, Differenz (%) und Auffällig |
| `vouchers` | Belege der Meldezeilen | Tabelle „Beleg der Zusammenfassenden Meldung“: Belegtyp, Belegnr., Kunde, Partei, USt-IdNr., Kennzahl, Art der Leistung, Betrag laut Hauptbuch und Bestimmungsland |
| `filed_via`, `filed_on`, `transferticket`, `filed_by`, `filing_note` | Abgegeben über, Abgegeben am, Transferticket, Vermerkt von, Wie und wann abgegeben | die Abgabe: über ERiC (`eric`) nach einem Senden, das ELSTER angenommen hat, mit dem Tag der Antwort, dem Transferticket und dem, der gesendet hat, oder vermerkt als in Mein ELSTER (`mein_elster`) oder auf anderem Weg (`other_way`) abgegeben |
| `remarks` | Anmerkungen | Pflicht, wenn eine Meldung abgegeben wird, die nicht bereit ist |

An der Meldung stehen unter „Verknüpfungen“ ihre USt-IdNr.-Bestätigungen und ihre ELSTER-Übermittlungen. Über dem Formular nennt sie die Fehler und Hinweise ihres letzten abgeschlossenen Prüfens, Testsendens oder Sendens, siehe [Übermittlung an ELSTER](#übermittlung-an-elster).

### Dauerfristverlängerung (`VAT Return Extension`)

Einreichbar, Nummernkreis `DFV-.{year}.-.#####` mit dem Jahr des Vordrucks (siehe [Nummern nach dem Jahr des Belegs](#nummern-nach-dem-jahr-des-belegs)), ein Vordruck USt 1 H je Unternehmen und Jahr: im Jahr des Antrags der Antrag auf Dauerfristverlängerung, bei monatlicher Abgabe mit der Anmeldung der Sondervorauszahlung, in jedem weiteren Jahr die Anmeldung allein. „Berechnen“ liest mit `dauerfrist_sources.py` die abgegebenen Voranmeldungen des Vorjahres und das Gründungsdatum, der Kern unter `steuerbote/dauerfrist` rechnet Grundlage, Sondervorauszahlung (Kz 38), Fälligkeit und den Zeitraum der Anrechnung über Kz 39, und `vat_return_extension/bridge.py` überträgt die Werte. Eine Grundlage von Hand mit Begründung ersetzt die aus den Voranmeldungen. Prüfen, Testsenden und Senden laufen wie an der Voranmeldung, siehe [Übermittlung an ELSTER](#übermittlung-an-elster), mit `transmission_in_progress` als Sperre; ohne Hersteller-ID trägt man den Vordruck in Mein ELSTER von Hand ein. Ein Senden, das ELSTER angenommen hat, „In Mein ELSTER eingetragen“ und „Als außerhalb abgegeben vermerken“ reichen den Beleg ein und setzen in den Einstellungen die Dauerfristverlängerung des Jahres, bei der Anmeldung dazu Kz 38 als Sondervorauszahlung, die die letzte Voranmeldung des Jahres in Kz 39 abzieht. Eine abgegebene Anmeldung wird storniert und mit „Ändern“ als berichtigte Anmeldung (Kz 10) neu angelegt. Felder, Status und Fristen stehen in [Der Beleg in ERPNext](dauerfristverlaengerung.md#der-beleg-in-erpnext).

### USt-IdNr.-Bestätigung (`VAT ID Confirmation`)

Ein Dokument je Abfrage beim BZSt oder bei VIES, Nummernkreis `USTID-{YYYY}-{#####}`. Nur der Server legt es an, über den Beleg ändert oder löscht es niemand, auch nicht seine Antwort, die als private Datei daran hängt, und „Transaktionen löschen“ am Unternehmen lässt es aus wie die Meldungen (`company_data_to_be_ignored` in `hooks.py`). Es hält angefragte und anfragende USt-IdNr., Unternehmen, Dienst, Ergebnis der Abfrage und der Prüfung, Code, Nachricht, Nummer der Abfrage, Name und Anschrift einer qualifizierten Abfrage mit den Vergleichsergebnissen, Zeitpunkte, Gültigkeit, HTTP-Status, die vorherige Abfrage und die Meldung, aus der die Prüfung kam. Die Felder stehen in [Prüfung ausländischer USt-IdNrn.](ust-idnr-pruefung.md#in-erpnext).

### Nummern nach dem Jahr des Belegs

Umsatzsteuer-Voranmeldung, Zusammenfassende Meldung und Dauerfristverlängerung tragen im Namen das Jahr, für das sie gelten: Ihr Nummernkreis nimmt mit `{year}` das Feld `year` des Belegs, das Frappe beim Anlegen einsetzt (`parse_naming_series` in `frappe/model/naming.py` liest einen Teil in geschweiften Klammern aus dem Feld des Belegs). Mit `.YYYY.` stünde dort das Jahr der Anlage: Der Vordruck USt 1 H für 2027 entsteht im November 2026, die Voranmeldung für Dezember im Januar darauf. Den Zähler hält Frappe je Präfix in der Tabelle der Nummernkreise, etwa für `UStVA-2026-`; Belege, die früher mit dem Jahr der Anlage benannt wurden, behalten ihre Namen, und die Zählung eines Präfixes geht hinter ihnen weiter, so dass kein Name doppelt entsteht.

### Feld an der Journalbuchung

Steuerbote ergänzt die Journalbuchung (Journal Entry) um das Feld „Nicht in der Umsatzsteuer-Voranmeldung“ (`steuerbote_exclude_from_vat_return`). Es kommt als Fixture der App und lässt eine Buchung aus der Meldung heraus, etwa die Verrechnung der Steuerkonten mit dem Finanzamt. Der Haken wird gesetzt, bevor die Journalbuchung gebucht wird: Danach lässt er sich nicht mehr ändern, denn er bestimmt, was ein schon abgegebener Zeitraum meldet. Soll eine gebuchte Buchung anders zählen, wird sie storniert und mit „Ändern“ neu gebucht; für einen abgegebenen Zeitraum geht die Änderung als berichtigte Anmeldung (Kz 10) an das Finanzamt.

## Die Abfrage des Hauptbuchs

`ledger.load_lines(company, from_date, to_date)` liest die Buchungen (GL Entry) des Unternehmens im Zeitraum, beide Tage eingeschlossen, zusammen mit der Kontonummer des Kontos. Nicht in die Meldung gehen:

- Buchungen, die ERPNext als storniert kennzeichnet (`is_cancelled`), siehe unten,
- Eröffnungsbuchungen,
- Periodenabschlussbuchungen (Period Closing Voucher),
- Journalbuchungen mit dem Haken „Nicht in der Umsatzsteuer-Voranmeldung“,
- Konten ohne Kontonummer. Keine Regel kann sie zuordnen; die Meldung zählt sie unter „Konten ohne Kontonummer“.

Soll und Haben werden je Kontonummer und Beleg summiert und als `Decimal` in Cent übergeben. Ein Beleg heißt beim Kern „Belegtyp:Belegnummer“, weil zwei Belegtypen dieselbe Nummer tragen können. Die Abfrage läuft über den Query Builder von Frappe mit Parametern, ohne zusammengesetztes SQL.

**Stornierte Belege.** Ohne „Unveränderliches Hauptbuch aktivieren“ (`enable_immutable_ledger`) in den Buchhaltungseinstellungen kennzeichnet ERPNext beim Stornieren die Buchungen eines Belegs und ihre Gegenbuchungen als storniert, und die Abfrage lässt beide aus, auch in einem Zeitraum, der schon gemeldet ist. Mit der Einstellung bucht ERPNext die Gegenbuchungen am Tag der Stornierung und kennzeichnet nichts, die Abfrage liest also beide: Im selben Zeitraum heben sie sich auf, eine Stornierung in einem späteren Zeitraum mindert diesen Zeitraum.

## Einstellungen je Unternehmen und Zeitraum

- **Voranmeldungszeitraum.** Jede Regel gilt ab einem Jahr und Monat bis zur nächsten Regel, auch über Jahresgrenzen. Ein Wechsel beginnt mit einem Kalendervierteljahr, also im Monat 1, 4, 7 oder 10. „Keine“ heißt: Für diese Monate ist keine Voranmeldung abzugeben. Vor der ersten Regel gibt es keinen Zeitraum, denn ihn legt das Finanzamt fest; Steuerbote rät ihn nicht.
- **Dauerfristverlängerung und Sondervorauszahlung je Jahr.** Mit Dauerfristverlängerung verschiebt sich jede Fälligkeit des Jahres um einen Monat (§ 46 UStDV). Eine Sondervorauszahlung gibt es nur zusammen mit ihr (§ 47 Absatz 1 UStDV) und sie wird in Kz 39 der letzten Voranmeldung des Jahres abgezogen (§ 48 Absatz 4 UStDV).
- **Die Meldung wählt ihren Zeitraum.** Abgaberhythmus und Nummer des Zeitraums stehen in der Meldung. Beim Speichern prüft sie, dass die Einstellungen für den ersten Monat des Zeitraums denselben Rhythmus vorschreiben, und setzt Voranmeldungszeitraum, Zeitraumcode, Von-Datum, Bis-Datum und Fälligkeit: der 10. Tag nach Ablauf des Zeitraums, mit Dauerfristverlängerung einen Monat später, an einem Wochenende der nächste Werktag. Feiertage der Länder berücksichtigt die Fälligkeit noch nicht.
- Ohne Einstellungen lässt sich keine Meldung anlegen, ohne Kontenzuordnung keine berechnen.

## Kontenzuordnung je Unternehmen

- **Vorgaben laden.** Die Schaltfläche füllt die Tabellen aus der Vorgabe für SKR03 oder SKR04, gekürzt auf die Konten des Unternehmens mit Kontonummer, die Buchungen aufnehmen. Regeln und beobachtete Konten bleiben, wenn es ihr Konto gibt. Ein beobachtetes Konto behält die Stufe, die seine Zeile vorher hatte; eines, das neu dazukommt, bekommt die Stufe der Vorgabe. Eine Verprobung behält ihre vorhandenen Grundlagen und Steuerkonten und entfällt, wenn auf einer Seite keines bleibt. Ein Hinweis nennt die Konten der Vorgabe, die dem Unternehmen fehlen. Für einen eigenen Kontenrahmen gibt es keine Vorgabe.
- **Prüfung beim Speichern.** Jedes Konto gehört zum Unternehmen und ist keine Kontengruppe. Der Kern prüft die Zuordnung gegen den neuesten Vordruck: jedes Konto nur einmal, nur Kennzahlen mit Betrag, ein Steuersatz nur dort, wo der Vordruck eine eigene Steuer-Kennzahl hat, Verprobungen und beobachtete Konten ohne Widerspruch, jedes beobachtete Konto nur einmal.
- „Berechnen“ prüft dieselbe Zuordnung noch einmal gegen den Vordruck des Jahres der Meldung.

## Lebenslauf einer Meldung

| Status | Bedeutung |
|---|---|
| Entwurf | angelegt und noch nicht berechnet, oder Unternehmen, Jahr, Abgaberhythmus oder Nummer des Zeitraums haben sich geändert; das verwirft eine Berechnung |
| Berechnet | berechnet, aber nicht bereit: Eine Verprobung weicht ab oder ein beobachtetes Konto der Stufe „Sperrt“ hat einen Saldo |
| Bereit | berechnet, alle Verprobungen gehen auf und kein beobachtetes Konto der Stufe „Sperrt“ hat einen Saldo |
| Abgegeben | eingereicht; das setzt eine Berechnung voraus und, wenn die Meldung nicht bereit ist, eine Begründung in den Anmerkungen |
| Ersetzt | für denselben Zeitraum ist später eine berichtigte Anmeldung abgegeben worden |

- Den Status setzt nur Steuerbote. An einer eingereichten Meldung ändert ihn niemand von Hand: Er entscheidet, ob ein Zeitraum abgegeben ist und welche Meldung in die Grundlage der Sondervorauszahlung eingeht (`dauerfrist_sources.py`). Auf „Ersetzt“ setzt ihn die Abgabe einer berichtigten Anmeldung, zurück auf „Abgegeben“ ihr Stornieren.
- „Berechnen“ geht, solange die Meldung nicht eingereicht ist, und lässt Korrekturen mit Begründung stehen.
- Frappe hält beim Speichern über die API kein schreibgeschütztes Feld fest. Deshalb nimmt das Speichern nur, was das Formular ändern lässt: Korrekturen mit Begründung, eigene Zeilen mit einer Korrektur, die weiteren Angaben und die Anmerkungen. Kennzahlen und Beträge der Zeilen, die „Berechnen“ gefunden hat, Verprobung, beobachtete Konten, Hinweise, Vorperiodenvergleich, „Bereit zur Abgabe“ und Status bleiben, wie „Berechnen“ sie gespeichert hat (`_keep_the_calculation`, `bridge.restored`); eine Zeile, die „Berechnen“ gefunden hat, lässt sich nicht entfernen. Eine neue Meldung beginnt immer als Entwurf ohne Berechnung (`before_insert`). Die Dauerfristverlängerung hält es mit ihrer Grundlage, ihrem Status und ihrer Abgabe ebenso, die Zusammenfassende Meldung mit ihren Belegen, Befunden, Abgleich, Vorperiodenvergleich, Status und Abgabe, siehe [Die Zusammenfassende Meldung](#die-zusammenfassende-meldung).
- Bevor eine Meldung übermittelt, als Datei für Mein ELSTER geschrieben oder eingereicht wird, rechnet Steuerbote ihre gemeldeten Beträge, die Summen und Kz 83 aus den gespeicherten Zeilen nach (`bridge.amounts_kept`), an der Dauerfristverlängerung Grundlage und Kz 38, an der Zusammenfassenden Meldung Meldezeilen und Summen aus den gespeicherten Belegen und Korrekturen. Weichen sie von dem ab, was gespeichert ist, etwa weil jemand sie an Steuerbote vorbei geändert hat oder „Buchen“ andere Korrekturen mitschickt, lehnt Steuerbote ab, bis die Meldung neu geladen oder neu berechnet ist.
- Ein Entwurf, dessen eigenes Senden ELSTER angenommen hat oder dessen Ergebnis unbekannt ist, liegt dem Finanzamt oder dem BZSt vor, wie er gesendet wurde, oder kann ihm so vorliegen. Deshalb ändern sich an ihm nur noch die Anmerkungen: Jedes andere Speichern lehnt Steuerbote ab, auch „Buchen“, das andere Werte mitschickt (`refuse_changes_after_sending` in `elster_transmission/transmission.py`, Feld für Feld und Zeile für Zeile mit dem gespeicherten Beleg verglichen), ebenso „Berechnen“ und Verwerfen (`refuse_if_sent`, `before_discard`). Nach einem angenommenen Senden reicht „Buchen“ ihn ein, nach einem unbekannten Ergebnis der Vermerk der Abgabe, der dabei nur deren Felder setzt. Das gilt für alle drei Belege; eine Änderung geht danach als neuer Beleg, der den gesendeten berichtigt.
- Ein Zeitraum wird je Unternehmen einmal abgegeben. Jede weitere Meldung für einen abgegebenen Zeitraum muss eine berichtigte Anmeldung (Kz 10) sein. Wird sie abgegeben, stehen die früheren Meldungen des Zeitraums auf „Ersetzt“; wird sie storniert, steht die zuletzt ersetzte wieder auf „Abgegeben“.
- Als abgegeben zählt ein Zeitraum, sobald eine seiner Meldungen eingereicht ist oder eine seiner Meldungen über Steuerbote gesendet wurde, mit Annahme durch ELSTER oder unbekanntem Ergebnis, auch wenn sie danach storniert wurde. Diese Regel prüfen Senden, die Datei für Mein ELSTER und die Vermerke einer Abgabe (`_refuse_second_filing`); das Speichern lehnt eine zweite Meldung ohne Kz 10 ab, sobald eine Meldung des Zeitraums eingereicht ist (`_refuse_second_return`).
- „Abgegeben“ heißt: Die Meldung ist in ERPNext eingereicht und festgeschrieben. Das geschieht nach einem Senden, das ELSTER angenommen hat, mit „In Mein ELSTER abgegeben“ nach einer Abgabe über die [Datei für Mein ELSTER](abgabe-mein-elster.md) oder von Hand dort, oder mit „Als außerhalb abgegeben vermerken“ für jeden anderen Weg. „Buchen“ allein lehnt `before_submit` ab, außer für eine Meldung, die ELSTER angenommen hat, deren Buchen danach aber scheiterte; das Formular zeigt die Schaltfläche nur dann.
- Eine Meldung, die ELSTER angenommen hat oder die als abgegeben vermerkt ist, lässt sich nicht stornieren (`before_cancel`). Stornieren lässt sich nur eine Meldung, die eine frühere Version von Steuerbote mit „Buchen“ allein eingereicht hat, ohne ELSTER-Übermittlung.
- „XML für Mein ELSTER“ erzeugt die Datei aus der gespeicherten Meldung, wenn sie abgegeben werden könnte oder abgegeben ist, und hängt sie privat an die Meldung.

## Vorperiodenvergleich und Hinweise

„Berechnen“ füllt an der Meldung zwei Tabellen, die beim Prüfen helfen und nichts ändern: Kein Betrag, keine Summe und nicht, ob die Meldung bereit ist, hängt von ihnen ab. Bereit ist eine Meldung weiter genau dann, wenn alle Verprobungen aufgehen und kein beobachtetes Konto der Stufe „Sperrt“ einen Saldo hat; ein Saldo auf einem Konto der Stufe „Hinweis“ ändert daran nichts. Beide Tabellen zeigen den Stand der letzten Berechnung, eine Korrektur danach erst nach dem nächsten „Berechnen“. Ihre Abschnitte erscheinen im Formular nur mit Zeilen.

**Vorperiodenvergleich.** Je Kennzahl stehen der gemeldete Betrag (nach Korrekturen), der Betrag der Vorperiode und der des Vorjahres, die Differenz zur Vorperiode und ihr Anteil am Betrag der Vorperiode. Vorperiode ist der vorige Zeitraum im selben Abgaberhythmus, Vorjahr derselbe Zeitraum ein Jahr früher, wie im Bericht „UStVA Kennzahlen“. Beide rechnet `build_comparison` in `vat_return.py` aus dem Hauptbuch, mit derselben Abfrage und der Kontenzuordnung auf dem Vordruck ihres Jahres, im letzten Zeitraum eines Jahres mit Kz 39. Frühere Meldungen liest es nicht: Das Hauptbuch ist die einzige Quelle der Kennzahlen, und der Vergleich geht auch, bevor es eine frühere Meldung gibt. Kennt Steuerbote die Kennzahlen eines Jahres nicht, heute 2025, oder passt die Kontenzuordnung nicht zu seinem Vordruck, bleiben die Werte dieses Zeitraums im Formular leer, und ein Hinweis nennt den Grund. Ein solcher Zeitraum kostet keine Abfrage; mit beiden Vergleichszeiträumen fragt „Berechnen“ das Hauptbuch höchstens dreimal ab.

Auffällig ist eine Kennzahl, wenn ihre Änderung gegenüber der Vorperiode beide Schwellen der Einstellungen übersteigt: „Schwelle Vorperiodenvergleich (%)“ als Anteil am Betrag der Vorperiode und „Schwelle Vorperiodenvergleich (EUR)“ als Betrag, ohne Eintrag 50 % und 100 EUR. Gleichstand mit einer Schwelle ist nicht auffällig, eine Änderung gegenüber 0 übersteigt jede Prozentschwelle. Es ist dieselbe Regel wie bei „Nur Abweichungen“ im Bericht (`Thresholds.exceeded` in `report/ustva_kennzahlen/comparison.py`).

**Hinweise.** Jeder Hinweis ist ein Satz mit den Beträgen im Zahlenformat der Site und, wo es sie gibt, mit Beleg und Partei. Eine Warnung betrifft eine Rechnung, die wahrscheinlich falsch ist, ein Hinweis einen Unterschied, den jemand erklären sollte; Warnungen stehen oben. Die Rechnungen liest `steuerbote/invoices.py`: die eingereichten Ausgangsrechnungen des Zeitraums je Erlöskonto und die Eingangsrechnungen je Aufwandskonto der Kz 46 und 84, ohne Eröffnungsrechnungen, Gutschriften mit negativen Beträgen. Netto ist der Nettobetrag der Artikel in Firmenwährung, die Steuer die, die ERPNext je Artikel und Steuerzeile berechnet hat (Item Wise Tax Detail), das Land das der Anschrift auf der Rechnung und die USt-IdNr. die des Kunden oder Lieferanten. Welche Kennzahl eine Rechnungszeile betrifft, sagt die Kontenzuordnung. Hat ein Konto, das die Kontenzuordnung auf der Stufe „Hinweis“ beobachtet, im Zeitraum einen Saldo, nennt ein Hinweis seine Kontonummer, seine Bezeichnung (das Feld „Kontoname“, gelesen von `ledger.account_labels`), Soll, Haben und Saldo; Soll und Haben rechnet der Kern (`hinted` in `calculate()`).

| Code | Art | Bedeutung |
|---|---|---|
| `EU-OHNE-USTID` | Warnung | Eine Rechnung geht in Kz 41 oder 21 ein, aber der Kunde hat keine USt-IdNr. Kz 41 setzt nach § 6a Absatz 1 Satz 1 Nummer 4 UStG die USt-IdNr. eines anderen Mitgliedstaats voraus, für Kz 21 nennt die Zusammenfassende Meldung sie (§ 18a Absatz 7 Satz 1 Nummer 3 UStG). Ob die Nummer gültig ist, prüft Steuerbote nicht. |
| `EU-VORLAGE-ADRESSE` | Warnung | Eine Rechnung geht in Kz 41 oder 21 ein, aber die Anschrift auf der Rechnung liegt in Deutschland, außerhalb der EU oder fehlt. Beide Kennzahlen setzen einen Kunden im übrigen Gemeinschaftsgebiet voraus (§ 6a Absatz 1 und § 18b Satz 1 Nummer 2 UStG): in einem der anderen 26 Mitgliedstaaten oder in Monaco, das nach § 1 Absatz 2a UStG als Gebiet Frankreichs gilt. |
| `NULLSATZ-OHNE-GRUND` | Warnung | Eine Rechnung bucht auf ein Konto der Kz 81 oder 86, aber ohne Steuer. |
| `STEUER-ABWEICHUNG` | Warnung | Die Steuer einer Rechnung auf einem Konto der Kz 81 oder 86 weicht um mehr als 1 Cent von 19 % oder 7 % des Nettobetrags auf diesem Konto ab. |
| `ABGLEICH-RECHNUNGEN` | Hinweis | Für Kz 81, 86, 41, 21, 45, 46 oder 84 weicht die Summe der Rechnungen um mehr als 1 EUR vom Betrag laut Hauptbuch ab, etwa wegen einer Journalbuchung auf einem Erlöskonto. |
| `KONTO-BEOBACHTET` | Hinweis | Ein Konto, das die Kontenzuordnung auf der Stufe „Hinweis“ beobachtet, hat im Zeitraum einen Saldo. Er geht in keine Kennzahl ein; ob er in die Voranmeldung gehört, klärt das Unternehmen, siehe [Beobachtete Konten mit Hinweis](ustva-kennzahlen.md#beobachtete-konten-mit-hinweis). |
| `ABWEICHUNG-VORPERIODE` | Hinweis | Eine Kennzahl ist im Vorperiodenvergleich auffällig. |
| `KEIN-KATALOG` | Hinweis | Steuerbote kennt die Kennzahlen des Jahres eines Vergleichszeitraums nicht, seine Werte bleiben leer. |
| `ZUORDNUNG-JAHRGANG` | Hinweis | Die Kontenzuordnung passt nicht zum Vordruck des Jahres eines Vergleichszeitraums, seine Werte bleiben leer. |

## Übermittlung an ELSTER

Prüfen, Testsenden und Senden laufen in einem Hintergrundjob, ERiC selbst in einem kurzlebigen Prozess des Jobs, für die Umsatzsteuer-Voranmeldung, die Dauerfristverlängerung und die Zusammenfassende Meldung auf demselben Weg: Alle drei Controller erben von `Transmittable` in `elster_transmission/transmission.py` und liefern nur, was ihr Beleg anders macht, `datenart()`, `nutzdaten(hersteller_id)`, `check_transmittable()` und `check_can_be_sent()`. `datenart()` nennt die Datenart aus `steuerbote/eric/datenart.py`, an Voranmeldung und Dauerfristverlängerung die UStVA ihres Jahres, an der Zusammenfassenden Meldung ZMDO, siehe [ERiC](eric.md#datenarten). Was Anwender dabei sehen, beschreibt [Übermittlung an ELSTER](uebermittlung.md), die Anbindung von ERiC [ERiC](eric.md).

1. `transmit` am Beleg sperrt seine Zeile, liest ihn neu und prüft: Entwurf, berechnet (`check_transmittable`, an der Dauerfristverlängerung dazu Vordruck und Schema des Jahres, an der Zusammenfassenden Meldung keine laufende Prüfung der USt-IdNrn.), kein laufender Vorgang, außerhalb der Simulation bestätigte Datenschutzhinweise. Für Senden prüft es dazu, dass kein Simulationsmodus aktiv ist, und `check_can_be_sent`, dass der Beleg abgegeben werden könnte wie beim Buchen, der Zeitraum, das Jahr oder der Meldezeitraum nicht schon abgegeben ist und der Beleg weder übermittelt ist noch mit unbekanntem Ergebnis gesendet wurde; an der Zusammenfassenden Meldung dazu, dass das Hauptbuch ihrer Monate bucht, wie „Berechnen“ es gelesen hat.
2. Sie legt die ELSTER-Übermittlung mit dem Status „Läuft“ an, setzt `transmission_in_progress` und stellt `run_transmission` mit dem Namen dieser Übermittlung in die Queue `long`, nach dem Commit, mit einer Job-ID je Übermittlung. Ein Job, dessen Übermittlung nicht mehr läuft, tut nichts. Ist der Job eines laufenden Vorgangs verschwunden, zeigt `onload` das dem Formular an, und es ruft `release_stale_transmission`: Die Übermittlung wird geschlossen, ein Prüfen als fehlgeschlagen, ein Testsenden oder Senden mit unbekanntem Ergebnis, und die Sperre fällt. Dasselbe geschieht beim nächsten Start eines Vorgangs.
3. Zertifikat und Passwort gehen vorher an `stash_certificate`, das sie über `steuerbote.eric.secrets` mit dem Schlüssel der Site verschlüsselt höchstens 15 Minuten im Zwischenspeicher ablegt, gebunden an den Benutzer und den Beleg, und dem Formular ein Token gibt. `transmit` gibt sie für diesen Benutzer und Beleg an die neue Übermittlung weiter (`hand_over`); der Job bekommt nur Beleg, Vorgang und Übermittlung und holt sie unter deren Namen einmal ab (`take`).
4. Der Job schreibt die Nutzdaten mit `nutzdaten` des Belegs, an der Meldung mit `ustva_xml.to_nutzdaten` aus demselben Baum wie die Datei für Mein ELSTER, an der Dauerfristverlängerung mit `ust1h_xml.to_nutzdaten`, beide mit der Hersteller-ID in Kz 09, an der Zusammenfassenden Meldung mit `zm_xml.to_nutzdaten` aus den gespeicherten Meldezeilen und dem Unternehmer der Einstellungen, ohne Hersteller-ID, und den Kopf der Lieferung als `EnvelopeHeader` mit der datenartVersion der Datenart, `UStVA_<Jahr>` oder `ZMDO`. Hersteller-ID, Produktdaten und Datenlieferant kommen aus den ERiC-Einstellungen, der Empfänger aus der Datenart: für die UStVA das Finanzamt aus den ersten vier Stellen der Steuernummer im ELSTER-Format, für ZMDO `BF` mit `id="L"`.
5. Außerhalb der Simulation sucht `runtime.detect` die Laufzeit für die Datenart des Belegs, mit einem Verzeichnis für `eric.log` je Übermittlung: die neueste freigegebene Version mit ihrem Plugin, `checkUStVA_<Jahr>` oder `checkZMDO`, für Prüfen und Testsenden ersatzweise eine Beta, für Senden nie. `service.run` ruft damit den Worker auf, ohne Laufzeit die Simulation.
6. Das Ergebnis geht in die ELSTER-Übermittlung: Status, Ergebnis laut ERiC, Transferticket, Nachrichten und Dateien. Nur ein Senden, das ELSTER angenommen hat, bucht den Beleg, mit `flags.filing_transmission`; Dauerfristverlängerung und Zusammenfassende Meldung halten dabei ERiC, den Tag der Antwort und das Transferticket als ihre Abgabe fest, die Zusammenfassende Meldung auch, wer gesendet hat; eine Berichtigung der Zusammenfassenden Meldung setzt die früheren Meldungen ihres Meldezeitraums auf „Ersetzt“. Scheitert das Buchen, steht der Grund mit dem Transferticket in der Übermittlung, und der Beleg bleibt ein Entwurf, der sich nicht noch einmal senden und bis auf die Anmerkungen nicht mehr ändern lässt, siehe [Lebenslauf einer Meldung](#lebenslauf-einer-meldung).
7. Zum Schluss gibt der Job die Sperre frei und meldet das Ergebnis dem Benutzer.

| Ergebnis laut ERiC | Status |
|---|---|
| Gültig, Angenommen | Erfolgreich |
| Ungültig, Abgelehnt, fehlgeschlagen | Fehlgeschlagen |
| Unbekannt | Unbekannt; die Meldung lässt sich nicht noch einmal senden und bis auf die Anmerkungen nicht ändern, bis jemand in Mein ELSTER nachgesehen und ein System Manager die Übermittlung gelöscht oder die Abgabe vermerkt hat |

`vat_return/transmission_adapter.py` enthält die Aufrufe, die ein eingerichtetes ERiC brauchen: Worker, Laufzeit der Datenart, Statusprüfung und Installation, mit den Pfaden und dem Benutzer der Site. Die Tests ersetzen nur diese Aufrufe (`FakeEric` in `steuerbote/tests/transmitting.py`) und lassen XML, Kopf, Ablage von Zertifikat und Passwort und Simulation wirklich laufen. Mit der Stub-Bibliothek der ERiC-Tests richtet ein Test eine Laufzeit aus einem Archiv ein und sendet durch den Worker.

Das Ereignis `steuerbote_elster_transmission` nennt `document_type` und `document` des Laufs; jedes Formular reagiert nur auf die Läufe seines DocTypes. Alle drei Formulare binden dieselben Schaltflächen und denselben Dialog aus `public/js/elster_transmission.js` ein und geben ihm nur die Texte, die ihren Beleg nennen, die Zusammenfassende Meldung auch die Beschriftung von „Senden“ und die Hinweise zur Simulation, die das BZSt nennen.

Über dem Formular nennen alle drei Belege die Fehler und Hinweise ihres letzten abgeschlossenen Prüfens, Testsendens oder Sendens, denn ein Prüfen mit Hinweisen ist erfolgreich (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.1.2.4.1): `onload` gibt dem Formular `latest_run` von `Transmittable`, `elster_transmission/messages.py` zählt die Nachrichten des Laufs je Art und gibt die ersten drei jeder Art weiter, und `show_latest_run` in `public/js/elster_transmission.js` zeigt sie mit dem Link auf die ELSTER-Übermittlung, die alle hält. Ein Vorgang, der noch läuft, zählt erst, wenn er beendet ist.

## Die Zusammenfassende Meldung

Die Meldung folgt dem Muster der Voranmeldung: Der Kern unter `steuerbote/zm` rechnet, `steuerbote/zm_sources.py` liest, `recapitulative_statement/bridge.py` überträgt, und der Controller bewegt nur Daten.

So läuft „Berechnen“:

1. Die Meldung bestimmt aus Jahr, Art und Nummer ihren Meldezeitraum (`ReportingPeriod`) und prüft ihn gegen den Abgaberhythmus der Einstellungen (`coverage()`), der auch die Monate der Lieferungen und der sonstigen Leistungen nennt.
2. `zm_sources.shares` liest mit `ledger.load_lines` nur die Konten, denen die Kontenzuordnung Kz 41, 42 oder 21 gibt, und teilt die Buchungen mit `attribution.contributions()` je Beleg auf; `zm_sources.parties` liest Kunde, USt-IdNr. und Bestimmungsland je Belegtyp mit einer Abfrage, siehe [Zusammenfassende Meldung](zm.md#berechnen).
3. Die letzte USt-IdNr.-Bestätigung jeder Nummer gibt ihr Ergebnis; eine Nummer ohne Bestätigung gilt als nicht bestätigt.
4. `lines.build()` bildet die Meldezeilen mit ihren Befunden und den Korrekturen der Zeilen, `threshold_findings()` prüft die Schwelle an Kz 41 und 42 je Monat, `reconcile()` gleicht mit dem Hauptbuch und den abgegebenen Voranmeldungen ab, `compare()` stellt die Zeilen der früheren Meldezeiträume daneben, die `earlier()` wählt: für die Lieferungen den vorigen, für die sonstigen Leistungen den letzten, der welche meldet.
5. `bridge.py` schreibt alles in die Tabellen. Bei jedem Speichern baut die Meldung die Zeilen aus den gespeicherten Belegen, den Korrekturen der Zeilen und der letzten USt-IdNr.-Bestätigung jeder Nummer neu, damit eine Korrektur mit Begründung ihre Sperre sofort aufhebt. Frappe hält beim Speichern über die API kein schreibgeschütztes Feld fest; deshalb nimmt das Speichern aus den gesendeten Zeilen nur Korrekturen und eigene Zeilen. Belege, Abgleich, Vorperiodenvergleich, die Befunde von Schwelle, Abgleich und Vorperiodenvergleich und der Status bleiben, wie „Berechnen“ sie gespeichert hat (`_keep_the_calculation`), die Abgabe, wie Senden oder ihr Vermerk sie gesetzt hat (`_keep_the_filing`). Eine neue Meldung beginnt immer als Entwurf ohne Abgabe und übernimmt aus ihren Zeilen nur USt-IdNr., Art und Korrektur mit Begründung (`before_insert`).

„USt-IdNrn. prüfen“ läuft als Hintergrundjob (`run_confirmation`) in der Queue `long`, mit einer Job-ID je Meldung und `confirmation_in_progress` als Sperre: je Nummer ein `vatid.confirm()` mit eigenem `UrllibFetch`, eine Abfrage nach der anderen, jede Bestätigung sofort festgeschrieben. Ist der Job verschwunden, gibt `release_stale_confirmation` die Sperre frei. „CSV für Mein ELSTER“ (`make_csv_file`) schreibt die Datei mit `csv_file()` aus der gespeicherten Meldung, nicht aber für einen Entwurf, dessen eigenes Senden ELSTER angenommen hat oder dessen Ergebnis unbekannt ist (`_refuse_sent_statement`). Vorher lesen sie und der Vermerk der Abgabe an einer Meldung im Entwurf das Hauptbuch der Monate neu (`zm_sources.shares`, `zm_sources.parties`) und lehnen ab, wenn `ledger_changes()` einen Beleg findet, der seit dem Berechnen mit anderem Betrag oder unter anderer USt-IdNr. bucht oder nur auf einer Seite steht. An einer abgegebenen Meldung fragt das Formular `ledger_changes_since_filing`, das ihre Belege ebenso gegen das Hauptbuch der Monate stellt, die sie behalten hat, und zeigt das Ergebnis als Hinweis; „Berichtigung anlegen“ nennt dieselben Belege, siehe [Stornierte Rechnungen](zm.md#stornierte-rechnungen). „In Mein ELSTER abgegeben“ und „Als außerhalb abgegeben vermerken“ (`mark_filed_outside`) reichen die Meldung ein und legen eine ELSTER-Übermittlung mit dem Vorgang „Außerhalb abgegeben“ an; „Buchen“ allein lehnt `before_submit` ab, außer für eine Meldung, die ELSTER angenommen hat, und `before_cancel` lehnt jedes Stornieren ab. „Berichtigung anlegen“ (`make_correction`) legt eine Meldung mit der Meldeart Berichtigung an, deren Datei `correct()` gegen alle Abgaben des Meldezeitraums bildet; wird sie abgegeben, stehen die früheren auf „Ersetzt“.

„Prüfen“, „Testsenden“ und „Senden“ laufen wie an der Voranmeldung, siehe [Übermittlung an ELSTER](#übermittlung-an-elster), mit diesen Teilen der Meldung:

1. `nutzdaten` bildet mit `bridge.zm` die `Zm` aus Meldezeitraum, den gespeicherten Meldezeilen, Anzeige und Widerruf, an einer Berichtigung mit den Zeilen, die die bisherigen Abgaben des Meldezeitraums halten (`as_filed`), und mit `bridge.unternehmer` den `Unternehmer` aus den Einstellungen und dem Staatenschlüssel des Landes des Unternehmens. `zm_xml.to_nutzdaten` schreibt beide mit dem Tag des Laufs; was es ablehnt, steht übersetzt als Nachricht in der ELSTER-Übermittlung, und nichts geht an ELSTER.
2. `check_transmittable` verlangt eine berechnete Meldung im Entwurf, keine laufende Prüfung der USt-IdNrn. und Meldezeilen und Summen, die aus den gespeicherten Belegen und Korrekturen neu gebaut so herauskommen, wie sie gespeichert sind (`_require_amounts_as_stored`, `bridge.amounts_kept`); dasselbe prüfen die CSV-Datei und das Einreichen. „USt-IdNrn. prüfen“ lehnt umgekehrt ab, solange `transmission_in_progress` gesetzt ist.
3. `check_can_be_sent` verlangt wie der Vermerk der Abgabe „Bereit“ oder Anmerkungen (`_check_ready_to_file`) und das Hauptbuch der Monate, wie „Berechnen“ es gelesen hat (`_require_unchanged_ledger`), und lehnt ab, wenn die Meldung schon gesendet ist oder mit unbekanntem Ergebnis gesendet wurde. Ein Meldezeitraum gilt als abgegeben, sobald eine seiner Meldungen eingereicht ist oder über Steuerbote gesendet wurde, mit Annahme oder unbekanntem Ergebnis (`filings`); jede andere Meldung des Meldezeitraums geht dann nur als Berichtigung (`_refuse_second_filing`), für Senden, CSV-Datei und Vermerk gleich.
4. Nach einem Senden, das ELSTER angenommen hat, reicht der Job die Meldung ein: `before_submit` nimmt mit `accepted_send` Tag der Antwort, Transferticket und Benutzer aus der ELSTER-Übermittlung, `on_submit` setzt bei einer Berichtigung die früheren Meldungen auf „Ersetzt“. Scheitert das Einreichen, ändert sich an der Meldung bis auf die Anmerkungen nichts mehr, wie an jedem Beleg nach einem eigenen Senden (`refuse_changes_after_sending`, siehe [Lebenslauf einer Meldung](#lebenslauf-einer-meldung)): Speichern mit anderen Werten, „Berechnen“, „USt-IdNrn. prüfen“, die CSV-Datei und Verwerfen lehnt Steuerbote ab, und „Buchen“ reicht sie ein, wie sie gesendet wurde.

## Was wo berechnet wird

| Was | Wo |
|---|---|
| Kennzahlen, Rundung, Summen der Zeilen 37, 45 und 48, Kz 83, Verprobung | `calculate()` im Kern |
| gemeldete Beträge nach Korrekturen und die Summen darüber | Kern: `bridge.filing` gibt die gemeldeten Beträge noch einmal in `calculate()` |
| Voranmeldungszeitraum, Zeitraumcode, Fälligkeit | `Period` im Kern, Rhythmus aus `vat_return_settings/rules.py` |
| Kz 39 | `bridge.sondervorauszahlung_values` aus den Einstellungen |
| Steuernummer im ELSTER-Format | `steuerbote/elster` |
| XML für Mein ELSTER und ERiC, mit Kz 83 aus den geschriebenen Werten nachgerechnet | `steuerbote/elster/ustva_xml.py` |
| XML des Vordrucks USt 1 H für ERiC, im Kontext, den der Abgaberhythmus wählt | `steuerbote/elster/ust1h_xml.py` mit `Ust1H` aus `steuerbote/dauerfrist/form.py` |
| XML der Zusammenfassenden Meldung für ERiC, mit dem Unternehmer aus den Einstellungen | `steuerbote/elster/zm_xml.py` mit `bridge.zm` und `bridge.unternehmer` der Meldung |
| Kopf der Lieferung, Hersteller-ID, Empfänger und Testmerker | `envelope_header` in `elster_transmission/transmission.py` mit der Datenart des Belegs aus `steuerbote/eric/datenart.py`, geprüft von `steuerbote/eric/header.py` |
| Laufzeit der Datenart, Ergebnis eines Laufs | `steuerbote/eric/runtime.py`, `steuerbote/eric/service.py` mit Worker oder Simulation |
| Belege hinter jeder Kennzahl | `attribution.py` mit den Regeln von `calculate()` |
| Vorperiode und Vorjahr im Bericht | `calculate()` für die Vergleichszeiträume, `comparison.py` |
| Vorperiodenvergleich und Hinweise der Meldung | `calculate()` für die Vergleichszeiträume, `steuerbote/ustva/plausibility.py` mit der Regel aus `comparison.py`, Rechnungszeilen aus `steuerbote/invoices.py` |
| Druckformat | rechnet keine Kennzahl, nur was der Vordruck selbst bildet: die Zeilen 45 und 48 aus den gespeicherten Summen und die Steuer der Zeilen 13, 14, 25 und 26 aus der Bemessungsgrundlage in vollen Euro |
| Meldezeitraum, Code `quart`, Fälligkeit und Abgaberhythmus der Zusammenfassenden Meldung | `steuerbote/zm/period.py` und `steuerbote/zm/rhythm.py`, Feiertage aus der Feiertagsliste des Unternehmens ohne die wöchentlich freien Tage (`steuerbote/holiday_list.py`) |
| Meldezeilen, Rundung auf ganze Euro, Sperren, Abgleich, Vorperiodenvergleich, Berichtigung und CSV-Datei der Zusammenfassenden Meldung | `steuerbote/zm` |
| Bestätigung der USt-IdNrn. und ihr Ergebnis | `steuerbote/vatid`, `vat_id_confirmation/records.py` |
| Grundlage, Sondervorauszahlung (Kz 38), Fristen und Zeitraum der Anrechnung der Dauerfristverlängerung, Vordruck USt 1 H mit Feldern und Regeln des Jahres | `steuerbote/dauerfrist`, Feiertage aus `steuerbote/holiday_list.py` |

## Bericht „UStVA Kennzahlen“

Der Bericht zeigt für einen Zeitraum, aus welchen Buchungen jede Kennzahl besteht, und stellt jede Kennzahl neben Vorperiode und Vorjahr. Filter sind Unternehmen, Jahr, Abgaberhythmus und Nummer des Zeitraums, dazu „Nur Abweichungen“.

- Er liest dasselbe wie „Berechnen“: die Abfrage des Hauptbuchs mit denselben Ausschlüssen, die Kontenzuordnung und die Einstellungen des Unternehmens, im letzten Zeitraum des Jahres also auch Kz 39.
- Je Kennzahl steht eine Zeile in der Reihenfolge des Vordrucks mit Kennzahl, Zeile im Vordruck, Bezeichnung, Betrag laut Hauptbuch und Betrag laut Vordruck. Darunter folgt eine Ebene tiefer je Beleg eine Zeile mit Buchungsdatum, Belegtyp, Belegnr., Drucken, Partei, Konto, Soll, Haben und dem Betrag, den der Beleg beiträgt. Die Summen der Zeilen 37, 45 und 48 und Kz 83 stehen an ihrer Stelle im Vordruck.
- Die Belegnr. öffnet den Beleg, „Drucken“ seine Druckansicht (`/printview`) in einem neuen Tab. Partei ist bei einer Ausgangsrechnung der Kunde, bei einer Eingangsrechnung der Lieferant, mit dem Namen aus der Rechnung; bei anderen Belegen, etwa Journalbuchungen, bleibt sie leer. Die Parteien liest der Bericht mit einer Abfrage je Belegtyp.
- Ein stornierter Beleg erscheint nur mit „Unveränderliches Hauptbuch aktivieren“, siehe [Die Abfrage des Hauptbuchs](#die-abfrage-des-hauptbuchs). Seine Zeile zeigt unter „Drucken“ „Storniert“ statt des Links, denn Frappe druckt stornierte Belege nur, wenn die Druckeinstellungen es erlauben; die Belegnr. öffnet ihn weiter. Die Beträge bleiben, wie sie im Hauptbuch stehen: 0, wenn Beleg und Stornierung im selben Zeitraum liegen. Welche Belege storniert sind, liest der Bericht mit einer Abfrage je Belegtyp.
- Ein Konto mit Regel trägt je Beleg seinen Saldo auf der Seite der Regel bei, mit zusätzlicher Kennzahl auch dort. Eine abgeleitete Steuer, etwa Kz 47 zu Kz 46, entsteht je Beleg aus der Summe seiner Bemessungsgrundlagen zu einem Steuersatz und wird einmal gerundet, wie in `calculate()`. Ihre Belegzeile zeigt die Buchungen der Grundlagenkonten und die Steuer als Betrag.
- Die Belege einer Kennzahl ergeben genau ihren Betrag laut Hauptbuch. Heben sich die Belege einer Kennzahl auf, steht sie mit 0 im Bericht.
- **Vorperiodenvergleich.** Jede Kennzahl und jede Summe zeigt den Betrag laut Vordruck der Vorperiode, also des vorigen Zeitraums im selben Abgaberhythmus (für Januar der Dezember des Vorjahres, für das erste Quartal das vierte), und des Vorjahres, also desselben Zeitraums ein Jahr früher, dazu die Differenz zur Vorperiode: Betrag laut Vordruck abzüglich Vorperiode. Beide Zeiträume rechnet der Bericht wie seinen eigenen aus dem Hauptbuch, mit der Kontenzuordnung des Unternehmens auf dem Vordruck ihres Jahres und im letzten Zeitraum eines Jahres mit Kz 39. Frühere Meldungen liest er nicht, so vergleicht er auch Zeiträume, für die es noch keine Meldung gibt. Eine Kennzahl, die nur in Vorperiode oder Vorjahr einen Betrag hat, steht mit 0 im Bericht.
- Kennt Steuerbote die Kennzahlen eines Vergleichsjahres nicht, etwa 2025, oder passt die Kontenzuordnung nicht zu dessen Vordruck, bleibt die Spalte leer, ohne Vorperiode auch die Differenz. Eine Zeile am Anfang des Berichts nennt den Grund, etwa „Kein Vergleich mit Dezember 2025: Steuerbote kennt die Kennzahlen für 2025 noch nicht.“
- **Nur Abweichungen** zeigt nur die Kennzahlen und Summen, deren Differenz zur Vorperiode beide Schwellen überschreitet, den Betrag in Euro und den Anteil am Betrag der Vorperiode, jeweils mit ihren Belegen. Die Schwellen kommen aus den Einstellungen des Unternehmens, „Schwelle Vorperiodenvergleich (%)“ und „Schwelle Vorperiodenvergleich (EUR)“; ohne Eintrag gelten 50 % und 100 EUR. Eine Änderung gegenüber 0 überschreitet jede Prozentschwelle. Ohne Vorperiode blendet der Filter nichts aus.
- Der Bericht zeigt das Hauptbuch, keine Meldung: Korrekturen einer Meldung erscheinen darin nicht.
- Frappe schreibt eine Textspalte eines Berichts als HTML in die Seite. Nur „Drucken“ enthält HTML mit Absicht; Kennzahl, Bezeichnung und Partei maskiert der Formatierer des Berichts (`ustva_kennzahlen.js`), bevor Frappe sie zeigt, so dass etwa der Name eines Kunden nie als Code läuft. Der Export nach CSV oder Excel nimmt die Werte, wie sie sind.

## Arbeitsbereich „Steuern“ und Seitenleiste

Der Arbeitsbereich führt zu „Neue Voranmeldung“, zur Liste „Voranmeldungen“, zum Bericht „UStVA Kennzahlen“ („Kennzahlen (Bericht)“) und zu den Dauerfristverlängerungen („Dauerfristanträge“), im Abschnitt „Zusammenfassende Meldung“ zu „Neue ZM“, „Zusammenf. Meldungen“ und „USt-IdNr.-Prüfungen“, und zu „Einstellungen“ und „Kontenzuordnung“. Die Zahlenkarte „Offene Voranmeldungen“ zählt die Meldungen aller Unternehmen, die noch nicht eingereicht sind. Sichtbar ist der Arbeitsbereich für die Rollen Accounts Manager, Accounts User und System Manager.

Die Seitenleiste des Moduls bringt Steuerbote selbst mit (`sidebar/steuerbote`). Ohne sie bildet Frappe die Einträge aus den Namen der DocTypes, und die Seitenleiste schneidet Namen wie „Einstellungen Umsatzsteuer-Voranmeldung“ ab. Sie führt zum Arbeitsbereich „Steuern“, zu „Voranmeldungen“, „Dauerfristanträge“, „Zusammenf. Meldungen“, „USt-IdNr.-Prüfungen“, „Kontenzuordnung“, „Einstellungen“, „ERiC-Einstellungen“ und „ELSTER-Übermittlung“ und unter „Berichte“ zu „UStVA Kennzahlen“. Ein neuer DocType mit eigener Liste gehört auch in die Seitenleiste; `test_standard_records.py` prüft das, ebenso, dass keine Bezeichnung länger als 20 Zeichen ist.

## Platz im Desk

Links im Desk steht eine Leiste mit den Bereichen der App, in der man gerade arbeitet, bei ERPNext etwa Rechnungswesen, Vertrieb und Einkauf. Welche Bereiche dort stehen, legt jede App in ihrem Dock fest. Ein Modul, das kein Dock nennt, steht in keiner Leiste und ist nur über die Suche und seine Adressen zu erreichen.

- **Leiste von ERPNext.** Steuerbote bringt ein Dock mit (`steuerbote/dock/steuerbote/steuerbote.json`) und hängt es über `mount_on` in die Leiste von ERPNext ein. Dort steht „Steuern“ hinter den Bereichen von ERPNext und öffnet die Seitenleiste des Moduls mit dem Arbeitsbereich „Steuern“ als erstem Eintrag; die Leiste von ERPNext bleibt dabei stehen. Frappe zeigt den Eintrag nur, wenn der Benutzer in der Seitenleiste etwas öffnen darf. Das Symbol des Eintrags liegt in `steuerbote/public/icons/module-icons.svg`, `app_include_icons` in `hooks.py` lädt es.
- **Angeordnete Leiste.** Hat jemand die Leiste von ERPNext für alle oder für sich gespeichert, nimmt Frappe Einträge, die eine App später mitbringt, nicht von selbst auf. „Steuern“ steht dann im Benutzermenü unter „Dock verwalten“ zur Auswahl.
- **App-Übersicht.** `add_to_apps_screen` in `hooks.py` meldet Steuerbote mit Logo und dem Arbeitsbereich `/desk/steuern` an. Den Eintrag sehen Benutzer mit einer der Rollen des Arbeitsbereichs: Accounts Manager, Accounts User oder System Manager (`steuerbote/permissions.py`). Eine App, die sich in die Leiste einer anderen App einhängt, zeigt Frappe nicht als Kachel in der App-Übersicht. Der Eintrag macht Steuerbote aber als Standard-App wählbar, und Frappe zählt ihn mit, wenn es nach der Anmeldung die Startseite wählt: Wer außer Steuerbote nur ERPNext sieht, landet in der App-Übersicht statt auf der Startseite von ERPNext. Eine Standard-App in den Systemeinstellungen oder am Benutzer legt die Startseite fest.
- **Logo.** `steuerbote/public/images/steuerbote-logo.svg`, von Hand als SVG gezeichnet, und daraus gerendert `steuerbote-logo.png` mit 512 × 512 Pixeln. Steuerbote setzt kein `app_logo_url`: Daraus nimmt Frappe das Logo der Anmeldeseite, bei genau zwei Einträgen das der App neben Frappe, und ein weiterer Eintrag würde es auf jeder Site ändern.
- **Arbeitsbereich „Accounting“ von ERPNext.** Dort fügt Steuerbote keine Verknüpfung ein. Den Arbeitsbereich liefert ERPNext als Standard aus, und `bench migrate` spielt ihn neu ein, sobald ERPNext eine neuere Fassung mitbringt. Eine Anpassung der Site übersteht das, friert aber den Inhalt des Arbeitsbereichs ein, sodass spätere Änderungen von ERPNext dort nicht mehr ankommen.

## Standard-Druckformate

Jeder Beleg, der an eine Behörde geht, druckt ohne weitere Wahl mit seinem Druckformat: die Umsatzsteuer-Voranmeldung mit „Umsatzsteuer-Voranmeldung“, die Zusammenfassende Meldung mit „Zusammenfassende Meldung“ und die Dauerfristverlängerung mit „Dauerfristverlängerung“. Ein Standard-DocType nimmt sein Standard-Druckformat nur aus einem Property Setter (`default_print_format`): Frappe 16 lehnt das Feld in der Definition eines Standard-DocTypes ab („Standard DocType cannot have default print format, use Customize Form“, `DocType.validate`), und die Schaltfläche „Set as Default“ eines Druckformats legt den Property Setter an (`make_default` in `print_format.py`). Steuerbote bringt die drei Property Setter als Fixture mit (`steuerbote/fixtures/property_setter.json`, `fixtures` in `hooks.py`). Frappe spielt die Fixtures einer App bei ihrer Installation und bei jedem `bench migrate` neu ein; ein anderes Standard-Druckformat, das eine Site für diese Belege wählt, setzt das nächste `bench migrate` deshalb zurück.

## Druckformat „Umsatzsteuer-Voranmeldung“

Das Druckformat gibt eine Meldung in Reihenfolge und Wortlaut des Vordrucks USt 1 A 2026 aus, auf A4, schwarz und grau, ohne Logo und ohne Briefkopf.

- **Kopf:** Unternehmen, Steuernummer, Steuernummer im ELSTER-Format und Finanzamt aus den Einstellungen, Voranmeldungszeitraum, Fälligkeit, Name und Status der Meldung, in zwei Spalten: links die Bezeichnung, rechts der Wert.
- **Vordruck:** die Zeilen 10 und 11 (Kz 10 und 22), dann die Abschnitte A bis J und die ergänzenden Angaben zur Steueranmeldung (Kz 500 mit Begründung). Jede Zeile zeigt Zeile, Bezeichnung, Kennzahl und Bemessungsgrundlage in vollen Euro sowie Kennzahl und Steuer in Euro und Cent. Ein Abschnitt ohne Werte sagt „Keine Eintragungen“. Die Zeilen 37, 45 und 48 und Kz 83 stehen immer da.
- **Darunter:** die Korrekturen gegenüber dem Hauptbuch mit Begründung und die Anmerkungen, wenn es sie gibt.
- **Fußzeile:** „Zum Abgleich mit der Steuerberatung oder zum Übertragen in Mein ELSTER.“ und der Hinweis, dass der Ausdruck keine Abgabe ist.

Das Druckformat liest nur die Meldung und die Einstellungen ihres Unternehmens. Die Zeilen der Kennzahlen tragen Kennzahl, Zeile, Bezeichnung und Art des Betrags aus dem Katalog des Jahres der Meldung, die Meldung schreibt sie bei jedem Speichern neu. Abschnitte und Steuersätze des Ausdrucks gehören zum Vordruck 2026. Ein neuer Jahrgang braucht deshalb auch hier eine Prüfung Zeile für Zeile, wie der Katalog.

Alle Klassen des Druckformats beginnen mit `sb-`. Das Druck-Stylesheet von Frappe gestaltet allgemeine Klassen wie `label` selbst, als Inline-Element in 75 % der Schriftgröße; eigene Klassen halten diese Regeln vom Ausdruck fern.

## Druckformat „Zusammenfassende Meldung“

Das Druckformat gibt eine Zusammenfassende Meldung im Stil der Voranmeldung aus, auf A4, schwarz und grau, ohne Logo und ohne Briefkopf: im Kopf Unternehmen, eigene USt-IdNr., Meldezeitraum, Fälligkeit, Meldeart, Name und Status der Meldung und, wenn vermerkt, den Tag der Abgabe; dann die Zeilen der Datei je USt-IdNr. und Art mit dem Kunden, bei einer Berichtigung mit „Bisher gemeldet“, die Summen je Art, die Korrekturen mit Begründung und die Anmerkungen. Es rechnet nichts: Die Zeilen sind die mit „In der Datei“, die Summen addieren ihre gemeldeten Beträge. Auch hier beginnen alle Klassen mit `sb-`.

## Druckformat „Dauerfristverlängerung“

Das Druckformat gibt einen Vordruck USt 1 H im Stil der Voranmeldung aus, auf A4, schwarz und grau: Kopf mit Unternehmen, Steuernummer und Finanzamt, bei der Anmeldung der Sondervorauszahlung die abgegebenen Voranmeldungen des Vorjahres mit Kz 83 und Kz 39, dann der Vordruck in Reihenfolge und Wortlaut von 2026, die Grundlage von Hand, die offenen Punkte, die Anmerkungen und die Abgabe. Es rechnet nichts und dient als Vorlage für den Eintrag in Mein ELSTER, siehe [Dauerfristverlängerung](dauerfristverlaengerung.md#der-beleg-in-erpnext).

## Für die Steuerberatung zu klären

Steuerbote ersetzt keine Steuerberatung. Diese Punkte entscheidet die Steuerberatung für jedes Unternehmen, bevor die erste Meldung abgegeben wird:

1. **Einordnung von Handelsergebnissen.** Ob Erträge und Aufwendungen aus dem Handel, etwa mit Wertpapieren, Devisen oder Derivaten, in der Voranmeldung erscheinen, als nicht steuerbar, steuerfrei ohne Vorsteuerabzug (Kz 48) oder steuerpflichtig, und auf welche Konten sie dafür gebucht werden. Konten ohne Regel gehen in keine Kennzahl ein. Ergebniskonten wie 2654 „Erträge aus anderen Wertpapieren und Ausleihungen des Umlaufvermögens“ oder 2166 „Aufwendungen aus Bewertung Finanzmittelfonds“ halten je Geschäft nur Gewinn oder Verlust. Eine Bemessungsgrundlage für Kz 48 liefern sie nicht, denn der Umsatz „wird … nach dem Entgelt bemessen“ (§ 10 Abs. 1 Satz 1 UStG): Gehört der Handel in die Voranmeldung, braucht Kz 48 die Entgelte selbst, auf einem Konto mit Regel wie 8100 (SKR04: 4100) oder als Korrektur mit Begründung. Bis die Steuerberatung entschieden hat, kann das Unternehmen solche Konten auf der Stufe „Hinweis“ beobachten (siehe [Beobachtete Konten mit Hinweis](ustva-kennzahlen.md#beobachtete-konten-mit-hinweis)).
2. **Vorsteueraufteilung nach § 15 Absatz 4 UStG.** Hat ein Unternehmen auch Umsätze, die den Vorsteuerabzug ausschließen, ist die Vorsteuer aufzuteilen. Steuerbote meldet die Vorsteuer so, wie sie gebucht ist, und teilt nichts auf. Aufteilung und Buchung des nicht abziehbaren Teils sind abzustimmen. Aufzuteilen ist auch, was das Unternehmen zugleich für nichtunternehmerische Tätigkeiten bezieht, etwa für eine Vermögensverwaltung: Sonstige Leistungen sind „entsprechend der beabsichtigten Verwendung aufzuteilen“ (UStAE 15.2c Abs. 2 Satz 1 Nr. 1), und eine Leistung allein für nichtunternehmerische Tätigkeiten gehört gar nicht zum Unternehmen (UStAE 15.2c Abs. 1 Satz 2).
3. **Freigabe der Kontenzuordnung.** Die Vorgaben für SKR03 und SKR04 sind von keiner Steuerberatung bestätigt. Die Kontenzuordnung jedes Unternehmens, mit Verprobungen und beobachteten Konten, gibt die Steuerberatung frei.
4. **Voranmeldungszeitraum.** Ob monatlich, vierteljährlich oder keine Voranmeldung abzugeben ist, legt das Finanzamt fest (§ 18 Absatz 2 UStG), ebenso Dauerfristverlängerung und Sondervorauszahlung. Die Einträge in den Einstellungen sind je Jahr mit den Bescheiden abzugleichen.
