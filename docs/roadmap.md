# Roadmap

Steuerbote entsteht in drei Stufen: zuerst die Umsatzsteuer-Voranmeldung samt Übermittlung über ERiC, dann Dauerfristverlängerung und Zusammenfassende Meldung, zuletzt die Jahresmeldungen. Diese Seite beschreibt Pakete und Reihenfolge, keine Termine.

## Stand

- **Rechenkern der Umsatzsteuer-Voranmeldung** unter `steuerbote/ustva`: Katalog der Kennzahlen des Vordrucks USt 1 A je Jahrgang (bisher 2026), Rundung nach der Anleitung, Kontenzuordnung mit Vorgaben für SKR03 und SKR04, in denen jedes von DATEV für die Umsatzsteuer gekennzeichnete Konto samt Kontenbereichen und die Kontonummern der ERPNext-Vorlagen zugeordnet, verprobt, beobachtet oder mit Grund bewusst ohne Kennzahl ist, Berechnung aus Hauptbuchzeilen mit den Summen des Vordrucks bis Kz 83, Verprobung je Beleg und beobachteten Konten, dazu Voranmeldungszeiträume mit ihren Fristen. Reines Python ohne Frappe-Import, 100 % Testabdeckung. Die fachlichen Regeln stehen in [Kennzahlen und Kontenzuordnung](ustva-kennzahlen.md).
- **App-Gerüst:** Frappe-App mit dem Modul „Steuerbote“. Sie installiert sich auf einer Site mit ERPNext 16.
- **CI:** Tests für Kern und Frappe-Site, Linters und Sicherheitsprüfungen, siehe [Entwicklung](entwicklung.md#ci).
- **Noch nicht vorhanden:** DocTypes, Einstellungen, Oberfläche, Berichte, Druckformat, XML und die Anbindung an ERiC. Steuerbote ist noch nicht einsatzfähig.

## Arbeitspakete Stufe 1: Umsatzsteuer-Voranmeldung

Ziel der Stufe: Jede Voranmeldung, monatlich oder vierteljährlich, wird aus dem Hauptbuch berechnet und von ERiC geprüft. Sie liegt als PDF und als XML für Mein ELSTER vor und geht mit Zertifikat direkt an ELSTER. Das Übermittlungsprotokoll bleibt am Beleg.

Die Pakete folgen ihrer Nummerierung. 0a läuft parallel zu allen anderen.

| Nr. | Paket | Inhalt | Ergebnis/Abnahme |
|---|---|---|---|
| 0a | Hersteller-ID | Registrierung im ELSTER-Entwicklerbereich, Antrag auf eine Hersteller-ID für Steuerbote. | Die Hersteller-ID ist erteilt. Ohne sie gibt es keine Übermittlung über ERiC. |
| 0b | Gerüst (erledigt) | Frappe-App, Lizenz AGPL-3.0-or-later, CI mit Frappe-Testsite, Regeln für Beiträge. | Die App installiert sich auf einer Site mit ERPNext 16. Die CI prüft Kern, Frappe-Site, Stil und Sicherheit. |
| 1 | Zuordnung und Einstellungen | DocType „VAT Return Mapping“ je Firma und Kontenrahmen mit Regeln, Verprobungen und beobachteten Konten, vorbelegt aus SKR03 oder SKR04. DocType „VAT Return Settings“ je Firma: Zeitraum (Monat oder Quartal), Dauerfristverlängerung, Soll-Versteuerung (Ist-Versteuerung später), Steuernummer im 13-stelligen ELSTER-Format aus Steuernummer und Bundesland. | Jede Firma hat eine Zuordnung. Ein Konto aus ihren Steuervorlagen ohne Kennzahl wird gemeldet. |
| 2 | Rechenkern (erledigt) | Reines Python-Modul `steuerbote/ustva`: Katalog je Jahrgang, Kennzahlen aus Hauptbuchzeilen, Rundung nach der Anleitung, Summen wie im Vordruck bis Kz 83, Kz 39, negative Werte, Verprobung, beobachtete Konten, Voranmeldungszeiträume und Fristen. | `calculate()` liefert Kennzahlen, Summen, Verprobungen und die beobachteten Konten mit Saldo, `Period` Zeitraum, Frist und ELSTER-Code. 100 % Testabdeckung; die Kernfälle der Vorgabe SKR03 (ein Monat mit acht Konten) sind an echten Buchungen geprüft, alle übrigen Zuordnungen an den Kontenbezeichnungen und der Anleitung zum Vordruck. |
| 3 | Meldung und Bericht | Einreichbarer DocType „VAT Return“ mit Kennzahlen, Korrekturen mit Begründung und Status (Entwurf, abgegeben, berichtigt). „Berechnen“ liest die Buchungen (GL Entry) des Zeitraums, ohne Stornos, Eröffnungs- und Abschlussbuchungen und ohne die Verrechnung der Steuerkonten mit dem Finanzamt. Bericht „UStVA Kennzahlen“ mit Drill-down zu den Buchungen hinter jeder Kennzahl. | Eine Meldung je Firma und Zeitraum, eine zweite nur als berichtigte Anmeldung (Kz 10). Jede Kennzahl führt zu ihren Buchungen. |
| 4 | Druckformat | PDF in Reihenfolge und Wortlaut des Vordrucks USt 1 A, für die Steuerberatung oder zum Abtippen in Mein ELSTER. | Abgabe ohne Hersteller-ID von Hand in Mein ELSTER. |
| 5 | ERiC-Laufzeitumgebung | Installer lädt ERiC für Linux x86_64 nach Annahme der Nutzungsbedingungen aus dem ELSTER-Entwicklerbereich (Login nötig), prüft die SHA-256-Summe und hält jede Version in einem eigenen Verzeichnis. Statusseite für Bibliothek, Version, Hersteller-ID und Zertifikat. | ERiC ist eingerichtet, ohne Teil von Steuerbote zu sein. Die Datenschutzhinweise der Finanzverwaltung sind vor dem ersten Aufruf bestätigt. |
| 6 | ERiC-Anbindung | Anbindung von `EricBearbeiteVorgang` über `ctypes` für Prüfen, Testsenden und Senden. Jeder Aufruf läuft in einem kurzlebigen Unterprozess aus einem Hintergrundjob, nie im Prozess der Anwendung. | Fehler und Hinweise von ERiC sind ausgewertet, das PDF-Protokoll liegt als Nachweis am Beleg. |
| 7 | XML und Validierung | XML nach dem ERiC-Schema des Jahres (Wurzel `<Anmeldungssteuern>`, ISO-8859-15), mit den Zeitraumcodes aus `period.py`, die dabei gegen das Schema geprüft werden. Dieselbe Datei dient dem Import in Mein ELSTER. Tests gegen das XSD aus der ERiC-Dokumentation. | Mit Hersteller-ID prüft ERiC jede Datei, bevor sie angeboten wird. Ohne Hersteller-ID: Abgabe per XML-Import in Mein ELSTER. |
| 8 | Übermittlung | „Prüfen“, „Testsenden“ mit Testmerker und „Senden“ mit Organisationszertifikat (.pfx) und PIN, beide je Lauf eingegeben und nie gespeichert. Übermittlungsakte mit Transferticket, Protokoll und allen Dateien, Sperre während der Übermittlung, „Als abgegeben vermerken“ für Abgaben außerhalb von Steuerbote. | Eine Testsendung läuft durch: Der ELSTER-Server nimmt sie an und leitet sie nicht weiter. Danach echte Übermittlung mit Übermittlungsprotokoll als PDF am Beleg. |
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
