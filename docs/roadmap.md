# Roadmap

Steuerbote entsteht in drei Stufen: zuerst die Umsatzsteuer-Voranmeldung samt Übermittlung über ERiC, dann Dauerfristverlängerung und Zusammenfassende Meldung, zuletzt die Jahresmeldungen. Diese Seite beschreibt Pakete und Reihenfolge, keine Termine.

## Stand

- **Rechenkern der Umsatzsteuer-Voranmeldung** unter `steuerbote/ustva`: Katalog der Kennzahlen des Vordrucks USt 1 A je Jahrgang (bisher 2026), Rundung nach der Anleitung, Kontenzuordnung mit Vorgaben für SKR03 und SKR04, in denen jedes von DATEV für die Umsatzsteuer gekennzeichnete Konto samt Kontenbereichen und die Kontonummern der ERPNext-Vorlagen zugeordnet, verprobt, beobachtet oder mit Grund bewusst ohne Kennzahl ist, Berechnung aus Hauptbuchzeilen mit den Summen des Vordrucks bis Kz 83, Verprobung je Beleg und beobachteten Konten, dazu Voranmeldungszeiträume mit ihren Fristen. Reines Python ohne Frappe-Import, 100 % Testabdeckung. Die fachlichen Regeln stehen in [Kennzahlen und Kontenzuordnung](ustva-kennzahlen.md).
- **App-Gerüst:** Frappe-App mit dem Modul „Steuerbote“. Sie installiert sich auf einer Site mit ERPNext 16.
- **Frappe-Schicht der Umsatzsteuer-Voranmeldung:** Einstellungen je Firma mit Voranmeldungszeitraum je Jahr ab einem Monat, Dauerfristverlängerung und Sondervorauszahlung je Jahr und Steuernummer im ELSTER-Format; Kontenzuordnung je Firma mit „Vorgaben laden“ aus SKR03 oder SKR04; einreichbare Umsatzsteuer-Voranmeldung, die „Berechnen“ aus dem Hauptbuch füllt, mit Korrekturen samt Begründung und berichtigter Anmeldung (Kz 10); Bericht „UStVA Kennzahlen“ mit den Belegen hinter jeder Kennzahl; Arbeitsbereich „Steuern“ und Druckformat nach dem Vordruck. Wie das zusammenspielt, steht in [Architektur](architektur.md).
- **CI:** Tests für Kern und Frappe-Site, Linters und Sicherheitsprüfungen, siehe [Entwicklung](entwicklung.md#ci).
- **XML für Mein ELSTER:** Die Meldung erzeugt ihre Voranmeldung als XML-Datei nach dem Schema des Jahres, die Mein ELSTER importiert, siehe [Abgabe über Mein ELSTER](abgabe-mein-elster.md).
- **ERiC-Anbindung und Übermittlung:** `steuerbote/eric` bindet ERiC ab Version 44 an, mit Laufzeitumgebungen aus dem Archiv des Betreibers, einem kurzlebigen Worker-Prozess je Aufruf und einer Simulation. Am Beleg laufen Prüfen, Testsenden und Senden als Hintergrundjob, jeder Lauf mit einer ELSTER-Übermittlung; dazu kommen die ERiC-Einstellungen und „Als außerhalb abgegeben vermerken“, siehe [Übermittlung an ELSTER](uebermittlung.md) und [ERiC](eric.md). Ohne eigene Hersteller-ID läuft die Übermittlung als Simulation.
- **Noch nicht vorhanden:** die Hersteller-ID und damit Prüfen und Senden mit echtem ERiC. Bis dahin geht eine Voranmeldung von Hand oder per XML-Import in Mein ELSTER an das Finanzamt. Steuerbote ist noch nicht einsatzfähig.

## Arbeitspakete Stufe 1: Umsatzsteuer-Voranmeldung

Ziel der Stufe: Jede Voranmeldung, monatlich oder vierteljährlich, wird aus dem Hauptbuch berechnet und von ERiC geprüft. Sie liegt als PDF und als XML für Mein ELSTER vor und geht mit Zertifikat direkt an ELSTER. Das Übermittlungsprotokoll bleibt am Beleg.

Die Pakete folgen ihrer Nummerierung. 0a läuft parallel zu allen anderen.

| Nr. | Paket | Inhalt | Ergebnis/Abnahme |
|---|---|---|---|
| 0a | Hersteller-ID | Registrierung im ELSTER-Entwicklerbereich, Antrag auf eine Hersteller-ID für Steuerbote. | Die Hersteller-ID ist erteilt. Ohne sie gibt es keine Übermittlung über ERiC. |
| 0b | Gerüst (erledigt) | Frappe-App, Lizenz AGPL-3.0-or-later, CI mit Frappe-Testsite, Regeln für Beiträge. | Die App installiert sich auf einer Site mit ERPNext 16. Die CI prüft Kern, Frappe-Site, Stil und Sicherheit. |
| 1 | Zuordnung und Einstellungen (erledigt) | Vorhanden: „VAT Return Mapping“ je Firma mit Regeln, Verprobungen und beobachteten Konten und „Vorgaben laden“ aus SKR03 oder SKR04, „VAT Return Settings“ je Firma mit Voranmeldungszeitraum je Jahr ab einem Monat, Dauerfristverlängerung und Sondervorauszahlung je Jahr, Soll-Versteuerung und Steuernummer im ELSTER-Format. | Jede Firma hat Einstellungen und eine Zuordnung, ohne sie entsteht keine Meldung. Offen ist die Prüfung der Steuervorlagen, siehe Offene Punkte. |
| 2 | Rechenkern (erledigt) | Reines Python-Modul `steuerbote/ustva`: Katalog je Jahrgang, Kennzahlen aus Hauptbuchzeilen, Rundung nach der Anleitung, Summen wie im Vordruck bis Kz 83, Kz 39, negative Werte, Verprobung, beobachtete Konten, Voranmeldungszeiträume und Fristen. | `calculate()` liefert Kennzahlen, Summen, Verprobungen und die beobachteten Konten mit Saldo, `Period` Zeitraum, Frist und ELSTER-Code. 100 % Testabdeckung; die Kernfälle der Vorgabe SKR03 (ein Monat mit acht Konten) sind an echten Buchungen geprüft, alle übrigen Zuordnungen an den Kontenbezeichnungen und der Anleitung zum Vordruck. |
| 3 | Meldung und Bericht (erledigt) | Vorhanden: einreichbarer DocType „VAT Return“, den „Berechnen“ aus dem Hauptbuch ohne Stornos, Eröffnungs- und Abschlussbuchungen und ohne markierte Journalbuchungen füllt, mit Korrekturen samt Begründung und den Status Entwurf, Berechnet, Bereit, Abgegeben und Ersetzt, dazu der Bericht „UStVA Kennzahlen“ mit den Belegen hinter jeder Kennzahl. | Eine Meldung je Firma und Zeitraum, eine zweite nur als berichtigte Anmeldung (Kz 10). Jede Kennzahl führt zu ihren Buchungen. |
| 4 | Druckformat (erledigt) | Vorhanden: Druckformat „Umsatzsteuer-Voranmeldung“ in Reihenfolge und Wortlaut des Vordrucks USt 1 A 2026 mit Summen, Kennzeichen und Korrekturen, auf A4 in Schwarz und Grau, für die Steuerberatung oder zum Abtippen in Mein ELSTER. | Abgabe ohne Hersteller-ID von Hand in Mein ELSTER. |
| 5 | ERiC-Laufzeitumgebung | Vorhanden in `steuerbote/eric`: Der Betreiber lädt ERiC für Linux x86_64 nach Annahme des Lizenzvertrags selbst aus dem ELSTER-Entwicklerbereich (Login nötig) und nennt Archiv und SHA-256-Summe. Steuerbote prüft die Summe vor dem Entpacken, übernimmt nur die Bibliotheken für Linux x86_64, lädt sie zur Probe und hält jede Version mit Manifest in einem eigenen Verzeichnis. Statusprüfungen für Plattform, Bibliotheken, Plugin des Jahres und Hersteller-ID; ERiC-Einstellungen mit Installation im Hintergrund. Offen: die Statusseite in Frappe und die Bestätigung der Datenschutzhinweise. | ERiC ist eingerichtet, ohne Teil von Steuerbote zu sein. Die Datenschutzhinweise der Finanzverwaltung sind vor dem ersten Aufruf bestätigt. Siehe [ERiC](eric.md). |
| 6 | ERiC-Anbindung | Vorhanden in `steuerbote/eric`: Anbindung von ERiC ab Version 44 über `ctypes` (`EricBearbeiteVorgang` mit sieben Parametern, Druckparameter Version 4, Verschlüsselungsparameter Version 3, `EricCreateTH`, Zertifikat aus dem Speicher) für Prüfen, Testsenden und Senden. Jeder Aufruf läuft in einem kurzlebigen Worker-Prozess, nie im Prozess der Anwendung; ohne Laufzeit antwortet eine Simulation. Getestet gegen eine Stub-Bibliothek. Der Hintergrundjob der Übermittlung ruft sie auf. Offen: ein Lauf mit echtem ERiC nach Erteilung der Hersteller-ID. | Fehler und Hinweise von ERiC sind ausgewertet, das PDF-Protokoll liegt als Nachweis am Beleg. |
| 7 | XML und Validierung (teilweise erledigt: XML für Mein ELSTER; ERiC-Validierung folgt) | Vorhanden: XML nach dem ERiC-Schema des Jahres (Wurzel `<Anmeldungssteuern>`) mit den Zeitraumcodes aus `period.py`, für Mein ELSTER als Datei in ISO-8859-15, für ERiC derselbe Baum in UTF-8 mit der Hersteller-ID in Kz 09; Kz 83 nachgerechnet, Zeichensatz von ELSTER; Tests gegen die XSD aus der ERiC-Dokumentation, die die CI mit Prüfsumme lädt; Schaltfläche „XML für Mein ELSTER“ an der Meldung. Offen: ERiC prüft jede Datei, siehe Pakete 5 und 6. | Mit Hersteller-ID prüft ERiC jede Datei, bevor sie angeboten wird. Ohne Hersteller-ID: Abgabe per XML-Import in Mein ELSTER. |
| 8 | Übermittlung, teilweise erledigt (Simulation; echte Übermittlung nach Hersteller-ID) | Vorhanden: „Prüfen“, „Testsenden“ mit Testmerker und „Senden“ am Beleg als Hintergrundjob, Zertifikatsdatei (.pfx) und Zertifikats-Passwort je Lauf eingegeben und nie gespeichert; ELSTER-Übermittlung mit Transferticket, Meldungen, Nutzdaten, Protokoll und Antwort des Servers; Sperre während der Übermittlung; „Als außerhalb abgegeben vermerken“ für Abgaben außerhalb von Steuerbote; ERiC-Einstellungen mit Simulationsmodus; ein Senden mit unbekanntem Ergebnis sperrt jedes weitere Senden der Meldung. Offen: die echte Übermittlung nach Erteilung der Hersteller-ID (Paket 0a). Siehe [Übermittlung an ELSTER](uebermittlung.md). | Eine Testsendung läuft durch: Der ELSTER-Server nimmt sie an und leitet sie nicht weiter. Danach echte Übermittlung mit Übermittlungsprotokoll als PDF am Beleg. |
| 9 | Betrieb | Erinnerung an die Frist aus `Period.deadline` (10. Tag nach Ablauf des Zeitraums, mit Dauerfristverlängerung einen Monat später; die Feiertage des Bundeslands übergibt der Aufrufer), Rollen und Berechtigungen, Dokumentation, Hinweis auf neue ERiC-Versionen. | Erste Veröffentlichung. |

## Oberfläche in ERPNext

So sieht die Voranmeldung für Anwender aus, wenn die Pakete 1, 3, 4 und 8 fertig sind:

- **Workspace „Steuern“** je Firma: offene Zeiträume mit Fälligkeit, zuletzt übermittelte Meldungen, Einstieg in Einstellungen und Zuordnung.
- **Beleg „Umsatzsteuer-Voranmeldung“** je Firma und Zeitraum (Monat oder Quartal): Kennzahlen aus dem Hauptbuch berechnet, Verprobung je Steuerkonto, Hinweise auf Entwürfe, nicht gebuchte Belege und beobachtete Konten, manuelles Überschreiben einzelner Kennzahlen mit Begründung, Entwurf speichern, Ausdruck nach dem Vordruck.
- **Übermittlung am Beleg:** „Prüfen“, „Testsenden“ (ELSTER-Testmerker) und „Senden“, jeweils mit Zertifikat und PIN pro Vorgang, danach Übermittlungsprotokoll als PDF und Verlauf am Beleg. Ohne Hersteller-ID: Vorschau und Berechnung vollständig, Abgabe über die XML-Datei für Mein ELSTER.
- **Einstellungen je Firma:** Voranmeldungszeitraum je Jahr mit „gilt ab“, Dauerfristverlängerung mit Sondervorauszahlung (Kz 38, Abzug über Kz 39 in der Voranmeldung für Dezember) und der Antrag USt 1 H über ERiC, Steuernummer, Finanzamt, Zertifikat.

## Stufe 2: Dauerfristverlängerung und Zusammenfassende Meldung

Quelle für die Dauerfristverlängerung ist dasselbe BMF-Schreiben wie für die Voranmeldung, mit Vordruck USt 1 H und Anleitung USt 5 E.

| Paket | Inhalt | Ergebnis/Abnahme |
|---|---|---|
| Dauerfristverlängerung | Antrag auf Dauerfristverlängerung und Anmeldung der Sondervorauszahlung (Vordruck USt 1 H) als XML über ERiC. Bei monatlicher Abgabe beträgt die Sondervorauszahlung ein Elftel der Vorauszahlungen des Vorjahres zuzüglich der dort berücksichtigten Sondervorauszahlung (Kz 38). | Die Sondervorauszahlung ist gebucht und wird grundsätzlich in der Voranmeldung für Dezember über Kz 39 abgezogen. Der Rechenkern nimmt Kz 39 schon heute an. |
| Zusammenfassende Meldung | Zusammenfassende Meldung aus ERPNext als Datei für die Abgabe beim Bundeszentralamt für Steuern (BZSt). | Die Datei lässt sich beim BZSt hochladen. |

## Stufe 3: Jahresmeldungen

Jede Jahresmeldung wird ein eigenes Modul mit eigener Planung:

- **E-Bilanz:** Zuordnung jedes Kontos zur XBRL-Taxonomie.
- **Umsatzsteuererklärung** für das Kalenderjahr.
- **Körperschaftsteuer und Gewerbesteuer:** Berechnung und Erklärungen.
- **Hinterlegung oder Offenlegung** des Jahresabschlusses.

## Offene Punkte

- **Prüfung der Steuervorlagen.** Ein Konto aus den Steuervorlagen einer Firma, das keine Kennzahl hat, meldet Steuerbote noch nicht. Bis dahin halten nur beobachtete Konten mit Saldo eine Meldung an.
- **Bestätigung der Kontenzuordnung.** Die Vorgaben für SKR03 und SKR04 sind noch nicht von einer Steuerberatung bestätigt. Lass deine Einrichtung in jedem Fall von deiner Steuerberatung bestätigen.
- **Markenprüfung.** Recherche zum Namen „Steuerbote“ beim Deutschen Patent- und Markenamt vor der ersten öffentlichen Veröffentlichung.
- **ELSTER-Konto mit Zertifikatsdatei.** Für die Übermittlung über ERiC braucht die Firma ein ELSTER-Konto mit Anmeldung per Zertifikatsdatei (.pfx). ELSTER Secure funktioniert mit ERiC nicht.
- **Hersteller-ID.** Registrierung im ELSTER-Entwicklerbereich und Antrag auf die Hersteller-ID, siehe Paket 0a. Abgeben lässt sich auch ohne sie: von Hand oder per XML-Import in Mein ELSTER.

Offene Punkte zu einzelnen Kennzahlen und Konten stehen in [Kennzahlen und Kontenzuordnung](ustva-kennzahlen.md).

## Grundsätze

- **Alles je Firma.** Jede Buchung in ERPNext trägt ihre Firma. Zuordnung, Zeitraum, Steuernummer, Zertifikat und jede Meldung gehören zu genau einer Firma; mehrere Firmen in einer Site stören sich nicht, auch mit unterschiedlichen Voranmeldungszeiträumen.
- **Kennzahlen je Jahrgang.** Der Katalog wird nach dem Jahr des Zeitraums gewählt. Vorjahre und Berichtigungen behalten ihre Kennzahlen, ein neuer Jahrgang kommt als eigener Katalog dazu, sobald das BMF-Schreiben vorliegt. ELSTER nimmt das laufende Jahr und drei Vorjahre an.
- **Nur die aktuelle Hauptversion.** Frappe und ERPNext werden nur in der aktuellen Hauptversion unterstützt, derzeit 16. Keine Rückportierungen, keine Kompatibilitätsschichten.
- **Test zuerst.** Jede Kennzahl, Rundungsregel, Prüfung und jeder XML-Pfad bekommt einen Test, bevor es den Code gibt: Unit-Tests für den Kern, Integrationstests auf einer Frappe-Testsite. Keine Änderung an einer Zuordnung ohne Testfall. Geplant: ERiC prüft jede erzeugte XML-Datei in der CI.
- **Quellen im Code.** Jede fachliche Regel nennt ihre Primärquelle: Gesetz, BMF-Schreiben, Anleitung zum Vordruck, ELSTER- oder ERiC-Dokumentation.
- **ERiC von Anfang an.** ERiC gehört zur ersten Stufe, nicht zu einer späteren. So prüft die Bibliothek der Finanzverwaltung die Zahlen, bevor jemand sie abgibt.
- **Hauptbuch statt Rechnungen, mit Verprobung.** Steuerbote rechnet aus den Buchungen (GL Entry), nicht aus Rechnungen. So zählen Journalbuchungen, Korrekturen und importierte Buchungsstapel mit, und die Summen- und Saldenliste passt zur Meldung. Der Preis: Die Konten müssen sauber bebucht sein, und Steuerbote muss prüfen statt raten. Deshalb vergleicht die Verprobung die gebuchte Steuer mit der Steuer, die zu den Bemessungsgrundlagen gehört, und ein Saldo auf einem beobachteten Konto ohne Zuordnung hält die Meldung an. Geplant sind dazu: Steuerbuchungen bis zum Beleg verfolgen und die Summen mit den Berichten Sales Register und Purchase Register abgleichen. Eine Abweichung muss erklärt sein, bevor die Meldung abgegeben wird.
