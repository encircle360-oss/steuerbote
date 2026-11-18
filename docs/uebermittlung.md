# Übermittlung an ELSTER

Steuerbote übermittelt die Umsatzsteuer-Voranmeldung über ERiC, die Schnittstelle der Finanzverwaltung. Am Beleg „Umsatzsteuer-Voranmeldung“ gibt es dafür die Gruppe „ELSTER“ mit drei Vorgängen, „Prüfen“, „Testsenden“ und „Senden“, und dem Vermerk „Als außerhalb abgegeben vermerken“ für Meldungen, die auf anderem Weg zum Finanzamt gehen. Jeder Vorgang läuft im Hintergrund und hinterlässt eine ELSTER-Übermittlung mit Ergebnis, Meldungen und Dateien.

Ohne eigene Hersteller-ID und ohne installierte ERiC-Laufzeitumgebung läuft Steuerbote im [Simulationsmodus](#simulationsmodus). Dann geht nichts an das Finanzamt.

## Die Vorgänge

| Vorgang | Was passiert | Was es braucht | Folge für die Meldung |
|---|---|---|---|
| Prüfen | ERiC prüft die Meldung nach den Prüfregeln von ELSTER und liefert Fehler, Hinweise und ein Vorschau-PDF. Nichts geht an das Finanzamt. | berechnete Meldung im Entwurf | keine |
| Testsenden | Die Meldung geht als Testfall mit dem Testmerker 700000004 an den ELSTER-Server. Der löscht sie beim Eingang, ohne sie weiterzuleiten. | berechnete Meldung im Entwurf, Zertifikatsdatei (.pfx) und Zertifikats-Passwort | keine, sie bleibt ein Entwurf |
| Senden | Die Meldung geht an das Finanzamt. ELSTER antwortet mit Transferticket und Übermittlungsprotokoll. | Meldung „Bereit“ oder mit Begründung in den Anmerkungen, Zertifikatsdatei und Zertifikats-Passwort, Berechtigung zum Buchen, ERiC-Laufzeitumgebung und Hersteller-ID | wird gebucht, Status „Abgegeben“ |
| Als außerhalb abgegeben vermerken | Kein ERiC. Steuerbote vermerkt, dass die Meldung auf anderem Weg abgegeben wurde. | Meldung wie zum Buchen, ein Vermerk, wie und wann sie abgegeben wurde | wird gebucht, Status „Abgegeben“ |

Dabei gilt:

- **Erst speichern und berechnen.** Die Schaltflächen erscheinen an einer gespeicherten Meldung im Entwurf mit dem Status „Berechnet“ oder „Bereit“. Ungespeicherte Änderungen weist Steuerbote ab, weil der Hintergrundjob nur die gespeicherte Meldung kennt.
- **Eine Übermittlung zur Zeit.** Während ein Vorgang läuft, steht an der Meldung „Übermittlung läuft“. Bis zu seinem Ende lässt sie sich nicht berechnen, speichern oder buchen, damit genau das gebucht wird, was übermittelt wurde. Ist der Vorgang beendet, erscheint ein Hinweis, und das Formular lädt neu.
- **Berechtigungen.** Prüfen und Testsenden darf, wer die Meldung bearbeiten darf (Accounts User, Accounts Manager, System Manager). Senden und den Vermerk darf nur, wer buchen darf (Accounts Manager, System Manager).
- **Senden nur einmal.** Wurde eine Meldung schon mit Transferticket übermittelt, lehnt Steuerbote ein zweites Senden ab. Für einen Zeitraum, für den eine andere Meldung schon übermittelt ist, geht Senden nur mit einer berichtigten Anmeldung (Kz 10).

## Zertifikat und Passwort

Testsenden und Senden brauchen die Zertifikatsdatei (.pfx) des ELSTER-Kontos der Firma und ihr Passwort. Beides wird für jeden Vorgang neu eingegeben.

- Der Browser liest die Zertifikatsdatei. Sie wird nicht als Anhang hochgeladen.
- Zertifikat und Passwort gehen einmal an den Server. Dort liegen sie verschlüsselt und höchstens 15 Minuten, bis der Hintergrundjob sie einmal abholt. Weder an der Meldung noch an der ELSTER-Übermittlung, im Hintergrundjob oder in einem Protokoll wird eines von beiden gespeichert.
- Das Passwort hat 6 bis 128 Zeichen: Buchstaben, Ziffern, Leerzeichen und Satzzeichen, ohne Umlaute (ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 5-3).
- Testzertifikate von ELSTER taugen nur für Testsenden.

## Simulationsmodus

Solange in den ERiC-Einstellungen keine Laufzeitumgebung installiert oder keine Hersteller-ID eingetragen ist, ist der Simulationsmodus aktiv. Die Meldung zeigt dann einen orangefarbenen Hinweis mit Verweis auf die ERiC-Einstellungen, und die Schaltflächen heißen „Prüfen (Simulation)“ und „Testsenden (Simulation)“.

- Nichts geht an ELSTER oder an das Finanzamt.
- Prüfen prüft den Aufbau der Daten, nicht die Prüfregeln von ELSTER.
- Testsenden braucht weder Zertifikat noch Passwort. Das Ergebnis trägt ein Transferticket, das mit „SIM-“ beginnt und nie einem echten gleicht, und ein Platzhalter-PDF statt des Übermittlungsprotokolls. Anstelle einer Hersteller-ID steht 00000.
- Senden gibt es nicht, und die Meldung bleibt, wie sie ist. Abgeben lässt sie sich von Hand oder per XML-Import in Mein ELSTER und danach mit „Als außerhalb abgegeben vermerken“ festhalten.
- In der Liste der ELSTER-Übermittlungen steht bei jedem simulierten Lauf „Simuliert“.

## ERiC-Einstellungen

Die ERiC-Einstellungen gelten für die ganze Installation, nicht je Firma, denn die Hersteller-ID gehört zur Software. Bearbeiten darf sie nur der System Manager.

| Feld | Inhalt |
|---|---|
| Simulationsmodus | berechnet: aktiv, solange keine Laufzeitumgebung installiert oder keine Hersteller-ID eingetragen ist |
| Hersteller-ID | fünf Ziffern, im ELSTER-Entwicklerbereich an den Hersteller der Software vergeben. Die Hersteller-ID 74931 der ERiC-Dokumentation lehnt Steuerbote ab, weil sie nur der Veranschaulichung dient. |
| Produktname | Vorgabe „steuerbote“, höchstens 50 Zeichen. Der Name darf das Wort ELSTER nicht enthalten (§ 12 der ERiC-Nutzungsbedingungen). |
| Produktversion | Version von Steuerbote, wird gesetzt |
| Datenlieferant | wer die Daten liefert, höchstens 256 Zeichen: Firma; Ansprechpartner; Telefon; E-Mail; Ort; PLZ; Straße; Land. Zeilenumbrüche werden zu Semikolons. |
| ERiC-Archiv | absoluter Pfad des Archivs für Linux x86_64 auf dem Server oder seine Adresse auf `https://download.elster.de/` |
| SHA-256 des Archivs | die Prüfsumme, die der ELSTER-Entwicklerbereich für das Archiv angibt, 64 hexadezimale Stellen |
| Installierte Version, Verzeichnis der Bibliotheken, Verzeichnis der Logdateien, Letzte Prüfung | setzt die Installation |

### Laufzeitumgebung installieren

Steuerbote enthält kein ERiC. ERiC dürfen nur Lizenznehmer der Finanzverwaltung nutzen, und zwar in ihrem eigenen Produkt. Jeder Betreiber lädt sein ERiC deshalb selbst:

1. Im ELSTER-Entwicklerbereich anmelden, die Nutzungsbedingungen annehmen und das ERiC-Archiv für Linux x86_64 herunterladen oder seine Adresse kopieren.
2. In den ERiC-Einstellungen Pfad oder Adresse des Archivs und seine SHA-256 eintragen und speichern.
3. „Laufzeitumgebung installieren“ wählen. Die Installation läuft im Hintergrund. Ist sie fertig, erscheinen ein Hinweis und die installierte Version. Schlägt sie fehl, nennt der Hinweis die Ursache, Einzelheiten stehen im Fehlerprotokoll.

Die Laufzeitumgebungen liegen außerhalb jeder Site im Verzeichnis `sites/eric` der Bench, das `steuerbote_eric_root` in `common_site_config.json` ändern kann. Sie werden weder ausgeliefert noch mit einer Site gesichert.

## Ablauf eines Vorgangs

1. Bei Testsenden und Senden fragt ein Dialog nach Zertifikatsdatei und Zertifikats-Passwort, im Simulationsmodus nur nach einer Bestätigung.
2. Steuerbote prüft die Meldung: Entwurf, berechnet, kein anderer Vorgang läuft. Für Senden zusätzlich: kein Simulationsmodus, Meldung „Bereit“ oder mit Begründung, noch nicht übermittelt.
3. Steuerbote legt eine ELSTER-Übermittlung mit dem Status „Läuft“ an, sperrt die Meldung und stellt den Hintergrundjob ein.
4. Der Hintergrundjob baut die Nutzdaten, ruft ERiC oder die Simulation auf, hält Ergebnis, Meldungen und Dateien in der ELSTER-Übermittlung fest, gibt die Meldung wieder frei und benachrichtigt den Benutzer, der den Vorgang gestartet hat.
5. Nach einem erfolgreichen Senden bucht der Hintergrundjob die Meldung, ihr Status wird „Abgegeben“.

Zwei Sonderfälle:

- **Übermittelt, aber nicht gebucht.** Scheitert das Buchen nach einem erfolgreichen Senden, hält die ELSTER-Übermittlung Transferticket und Grund fest, und die Meldung bleibt ein Entwurf. Dann nicht erneut senden, denn das Finanzamt hat die Meldung schon. Steuerbote lehnt ein zweites Senden ohnehin ab. Nach Behebung der Ursache die Meldung mit „Buchen“ einreichen.
- **Abgebrochener Vorgang.** Bricht ein Hintergrundjob ab, etwa durch einen Neustart des Servers, bleibt seine ELSTER-Übermittlung auf „Läuft“. Beim nächsten Start eines Vorgangs schließt Steuerbote sie als „Fehlgeschlagen“ mit dem Vermerk, dass das Ergebnis unbekannt ist. Vor einem erneuten Senden in Mein ELSTER nachsehen, ob die Meldung angekommen ist. Ist sie angekommen, die Meldung mit „Als außerhalb abgegeben vermerken“ und dem Transferticket aus Mein ELSTER festhalten.

## ELSTER-Übermittlung

Jeder Vorgang und jeder Vermerk ist eine ELSTER-Übermittlung. Die Liste steht unter „ELSTER-Übermittlung“, die Übermittlungen einer Meldung stehen an der Meldung unter „Verknüpfungen“.

| Feld | Inhalt |
|---|---|
| Umsatzsteuer-Voranmeldung, Unternehmen | die Meldung und ihr Unternehmen |
| Vorgang | Prüfen, Testsenden, Senden oder Außerhalb abgegeben |
| Status | Läuft, Erfolgreich oder Fehlgeschlagen |
| Simuliert | der Lauf ging an die Simulation, nicht an ERiC |
| Gestartet am, Beendet am, Benutzer | wann und von wem |
| Transferticket | die Nummer, unter der ELSTER die Meldung angenommen hat |
| Testmerker | 700000004 bei Testsenden |
| ERiC-Version | die Version der Laufzeitumgebung oder „simulation“ |
| Anmerkungen | der Vermerk bei „Als außerhalb abgegeben vermerken“ |
| Nachrichten | Fehler und Hinweise von ERiC oder Steuerbote mit Code, Nachricht und Feld |
| Nutzdaten (XML), Protokoll (PDF), Antwort des ELSTER-Servers (XML) | die Dateien des Laufs, siehe unten |

Eine ELSTER-Übermittlung schreibt nur der Server, danach lässt sie sich nicht mehr ändern. Eine Übermittlung, die eine Abgabe festhält (ein erfolgreiches Senden außerhalb der Simulation oder ein Vermerk), lässt sich nicht löschen. Andere darf nur der System Manager löschen. Eine Meldung mit ELSTER-Übermittlungen lässt sich nicht löschen.

## Wo XML und Protokoll liegen

Jeder Lauf legt seine Dateien als private Dateien an seiner ELSTER-Übermittlung ab:

- **Nutzdaten (XML):** die geprüften oder übermittelten Daten der Meldung in UTF-8, wie ERiC sie erhält.
- **Protokoll (PDF):** bei Prüfen die Vorschau, bei Senden das Übermittlungsprotokoll mit Transferticket, in der Simulation ein Platzhalter.
- **Antwort des ELSTER-Servers (XML):** die Antwort von ELSTER, wenn es eine gibt.

Private Dateien liegen im Verzeichnis `sites/<site>/private/files` und öffnen sich nur für Benutzer, die die ELSTER-Übermittlung lesen dürfen. Eine Sicherung mit Dateien (`bench backup --with-files`) enthält sie. Die Nutzdaten enthalten die Steuerdaten der Meldung, Sicherungen sind entsprechend zu schützen. Zertifikat und Passwort sind nie darunter.

## Berichtigte Anmeldung (Kz 10)

Eine abgegebene Meldung lässt sich nicht mehr ändern oder erneut senden. Stornieren nimmt sie beim Finanzamt nicht zurück. Eine Korrektur geht so:

1. Eine neue Umsatzsteuer-Voranmeldung für dasselbe Unternehmen und denselben Zeitraum anlegen und „Berichtigte Anmeldung (Kz 10)“ setzen.
2. Berechnen, prüfen und senden, oder außerhalb abgeben und vermerken.
3. Ist die berichtigte Anmeldung abgegeben, steht die frühere Meldung des Zeitraums auf „Ersetzt“.

Ohne Kz 10 lehnt Steuerbote eine zweite Meldung für einen abgegebenen Zeitraum ab und ebenso das Senden einer Meldung für einen Zeitraum, der schon übermittelt ist.

## Als außerhalb abgegeben vermerken

Der Vermerk ist für Meldungen, die nicht über Steuerbote zum Finanzamt gehen: von Hand oder per XML-Import in Mein ELSTER oder über die Steuerberatung. Im Simulationsmodus ist er der Weg, eine abgegebene Meldung festzuhalten.

1. In der Gruppe „ELSTER“ „Als außerhalb abgegeben vermerken“ wählen.
2. Unter „Wie und wann abgegeben“ den Weg und das Datum eintragen, am besten mit dem Transferticket aus Mein ELSTER.
3. Steuerbote bucht die Meldung, ihr Status wird „Abgegeben“, und legt eine ELSTER-Übermittlung mit dem Vorgang „Außerhalb abgegeben“ und dem Vermerk in den Anmerkungen an.

Es gelten dieselben Regeln wie beim Buchen: Die Meldung muss berechnet sein, und ist sie nicht bereit, braucht sie vorher eine Begründung in ihren Anmerkungen.

Wie die Arbeitspakete der Übermittlung zusammenhängen, steht in der [Roadmap](roadmap.md).
