# ERiC

ERiC (ELSTER Rich Client) ist die C-Bibliothek der Steuerverwaltung, die ELSTER-Daten prüft, verschlüsselt, signiert und an die Annahmeserver übermittelt. Steuerbote bindet ERiC ab Version 44 über `ctypes` an und ruft es für „Prüfen“, „Testsenden“ und „Senden“ der Umsatzsteuer-Voranmeldung, der Dauerfristverlängerung (Vordruck USt 1 H) und der Zusammenfassenden Meldung auf. Die ersten beiden gehören zur Datenart UStVA: Das Entwicklerhandbuch führt die „Umsatzsteuer-Dauerfristverlängerung (UStDV)“ und die „Umsatzsteuer-Dauerfristverlängerung mit Sondervorauszahlung (UStSV)“ in Tabelle 2-13 unter der UStVA, und die `Datenartversionmatrix.ods` gibt `UStVA_<Jahr>` mit dem Plugin `checkUStVA_<Jahr>` „Mit UStDV und UStSV“. Die Zusammenfassende Meldung ist die Datenart ZMDO des Verfahrens ElsterExtern (Kap. 8.15, Tabelle 8-28), siehe [Datenarten](#datenarten). Diese Seite beschreibt Lizenz, Einrichtung, Datenarten, Versionen, Simulation, Vorgänge, Sicherheit und Grenzen.

Quelle ist die ERiC-Dokumentation 44.3.6.0: Entwicklerhandbuch (zitiert mit Kapitel oder Tabelle), API-Referenz, Releasenotes, Tutorial und der Softwarehersteller-Lizenzvertrag (`lizenz.pdf`, zitiert mit Paragraf). Das Dokumentationspaket ist öffentlich: [ERiC-44.3.6.0-Dokumentation.zip](https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Dokumentation.zip).

## Lizenz und Voraussetzungen

- **Weitergabe nur im eigenen Produkt.** Der Lizenzvertrag erlaubt dem Softwarehersteller, ERiC in eigene Software zu integrieren und mit ihr als einheitliches Produkt zu verbreiten (§ 4 Abs. 1). Das Nutzungsrecht an Dritte zu übertragen oder darüber hinaus Unterlizenzen zu erteilen, ist nicht gestattet (§ 4 Abs. 3).
- **Steuerbote liefert ERiC nicht mit.** Das Repository, die Pakete und die CI enthalten keine Datei von ERiC, und Steuerbote lädt ERiC nicht selbst herunter. Jeder Betreiber lädt ERiC selbst aus dem ELSTER-Entwicklerbereich, nach der Anmeldung und der Annahme des Lizenzvertrags (Tutorial, Kap. 2.5). Die Zugangsdaten kommen einige Tage nach der Registrierung als Softwarehersteller per E-Mail (Tutorial, Kap. 2.2).
- **Eigene Hersteller-ID, auch zum Testen.** ERiC und ELSTER verarbeiten Daten nur mit der eigenen Hersteller-ID, für Echtfälle wie für Testfälle (Kap. 6.5.3). Die frühere Test-Hersteller-ID 74931 dient nur noch der Illustration; seit ERiC 39.4 weist ERiC sie mit dem Fehler 610301202 zurück (Kap. 10.1.1), auch beim bloßen Prüfen. Ohne eigene Hersteller-ID arbeitet Steuerbote deshalb nur in der Simulation. Die Hersteller-ID ist produktbezogen (Kap. 6.5.3).
- **Pflichten gegenüber den Anwendern.** Vor der ersten Nutzung sind die Datenschutzhinweise der Finanzverwaltung zur Kenntnis zu bringen und zu bestätigen (§ 5 Abs. 1 und 2), und die Anwender sind darauf hinzuweisen, dass ERiC Protokolldateien anlegt (§ 15, Kap. 4.1.3). Der Produktname darf „ELSTER“ nicht enthalten (§ 12); Steuerbote prüft das am Produktnamen im NutzdatenHeader. Zu verwenden ist mindestens die Mindestversion (§ 5 Abs. 6).
- **Plattform.** Linux x86_64 mit glibc 2.28 oder neuer und `libgcc_s` (Kap. 2.4.4.5), mindestens 5 GiB freier Speicher für die Programmkomponenten (Tabelle 2-1).

## Einrichtung durch den Betreiber

1. Im ELSTER-Entwicklerbereich anmelden, den Lizenzvertrag annehmen und das Softwarepaket für Linux laden, `ERiC-<version>-Linux-x86_64.jar`. Die JAR-Datei ist ein ZIP-Archiv (Kap. 3.1, 4.3.3).
2. Die Signatur prüfen. Die Softwarepakete werden „jeweils als signierte JAR-Datei ausgeliefert“, und das Entwicklerhandbuch nennt zur Prüfung `jarsigner -verify -certs -verbose ERiC-<version>-<os>.jar` aus dem JDK, das auch das Zertifikat der Signatur zeigt (Kap. 3.1). Welches Zertifikat die Signatur tragen muss, nennt es nicht, und das Dokumentationspaket enthält keine Zertifikatsdatei. Steuerbote prüft die Signatur deshalb nicht selbst; das tut der Betreiber, und Steuerbote prüft danach die SHA-256-Summe, die er festhält.
3. Die SHA-256-Summe des Archivs bilden, etwa mit `sha256sum`, und Pfad und Summe auf dem Server in die `common_site_config.json` der Bench eintragen:

   ```sh
   bench set-config -g steuerbote_eric_archive /srv/eric/ERiC-44.3.6.0-Linux-x86_64.jar
   bench set-config -g steuerbote_eric_archive_sha256 <SHA-256-Summe>
   ```

   Nur dort zählen sie: Eine Laufzeit dient allen Sites der Bench, und die Probe beim Einrichten lädt die Bibliothek des Archivs als Benutzer der Bench. Was in der `site_config.json` einer Site steht, nimmt Steuerbote nicht, und die ERiC-Einstellungen zeigen Pfad und Summe nur an, sodass auch ein System Manager kein anderes Archiv wählen kann.
4. In den ERiC-Einstellungen „Laufzeitumgebung installieren“ wählen. Der Hintergrundjob liest Pfad und Summe selbst aus der `common_site_config.json`. Steuerbote
   - prüft die SHA-256-Summe, bevor es etwas entpackt, und nimmt nur Archive bis 1 GiB;
   - entpackt nur die Dateien unter `ERiC-<version>/Linux-x86_64/lib/`, die Basisbibliotheken und darunter die Plugins (Kap. 3.1.4, Tabellen 3-2 und 3-3), und verlangt `libericapi.so` und das Plugin `libcommonData.so`, das ERiC immer braucht (Kap. 3.1.6.1);
   - weist Pfade außerhalb dieses Verzeichnisses, Links, doppelte Einträge und Bibliotheken zweier Pakete zurück;
   - lädt die Bibliothek zur Probe einmal im Worker-Prozess (`EricInitialisiere`, `EricVersion`, `EricBeende`);
   - legt die Version erst danach als Ganzes unter `<Laufzeitverzeichnis>/<version>/` ab, mit dem Manifest `steuerbote-runtime.json`: SHA-256 des Archivs und jeder Datei, die Jahre der UStVA-Plugins, ob die Version eine Beta ist, Zeitpunkt und Benutzer der Einrichtung.
5. Jede Version liegt in einem eigenen Verzeichnis, denn Basisbibliotheken verschiedener Pakete passen nur garantiert zusammen, wenn sie aus demselben Paket stammen (Kap. 3.1.6.2). Dasselbe Archiv noch einmal einzurichten ändert nichts, solange die Dateien der Version ihrem Manifest entsprechen, und nennt sonst die Abweichung; ein anderes Archiv mit derselben Version wird abgewiesen.
6. Das Laufzeitverzeichnis liegt außerhalb jeder Site, unter `sites/eric/` der Bench oder dort, wo `steuerbote_eric_root` in der `common_site_config.json` es hinlegt. So wird ERiC weder ausgeliefert noch mit den Sicherungen einer Site gesichert. Steuerbote übergibt den Pfad der Bibliotheken nie an `ldconfig` und setzt kein `LD_LIBRARY_PATH` (Kap. 4.3.3, 4.2.2).

Vor jedem Prüfen, Testsenden und Senden vergleicht Steuerbote die Laufzeit, die es gewählt hat, mit ihrem Manifest (`runtime.detect`, `runtime.verify`): Jede Datei unter `lib/` muss die SHA-256-Summe des Manifests haben, keine darf fehlen, keine fremde dazukommen, und ein Link, auf eine Bibliothek oder ein Verzeichnis von Plugins, ist immer fremd. Weicht etwas ab, lädt Steuerbote ERiC nicht, der Vorgang endet als fehlgeschlagen und nennt die Abweichung, und der Worker erhält weder Zertifikat noch PIN. Dann das Verzeichnis der Version entfernen und sie neu einrichten.

Das Archiv nennt seine Version im Stammverzeichnis `ERiC-<version>/`; fehlt es, gilt die Version aus dem Dateinamen `ERiC-<version>-Linux-x86_64.jar`. Diesen Aufbau beschreibt das Entwicklerhandbuch für das entpackte Paket (Kap. 3.1.4 und Kap. 4.3 mit dem Include-Pfad `ERiC-<version>\Windows-x86\include`). Ein echtes Paket für Linux hat Steuerbote bisher nicht entpackt.

### Statusprüfung

`steuerbote.eric.runtime.status` liefert die Prüfungen für die Statusseite: Plattform (Linux x86_64, glibc ab 2.28), eingerichtete Laufzeit, Bibliotheken unverändert gegenüber dem Manifest, Plugin des Jahres (`plugin`), Plugin `checkZMDO` der Zusammenfassenden Meldung (`zmdo`) und eigene Hersteller-ID. Ein Plugin gilt als vorhanden, wenn eine freigegebene Laufzeit es hat; hat es nur eine Beta, nennt die Prüfung sie und dass mit ihr nur Prüfen und Testsenden gehen. In den ERiC-Einstellungen zeigt „Laufzeitumgebung prüfen“ diese Prüfungen für das laufende Jahr, siehe [Übermittlung an ELSTER](uebermittlung.md#laufzeitumgebung-prüfen). Dass die Datenschutzhinweise bestätigt sind, halten die ERiC-Einstellungen fest und geben es mit der Laufzeit weiter (`RuntimeInfo.confirmed_privacy_notice`); ohne diese Bestätigung weist `steuerbote.eric.service.run` jeden Lauf mit ERiC ab, nur die Simulation antwortet. Die Betriebsart ist ausdrücklich: Die Simulation antwortet nur, wenn die Frappe-Schicht keine Laufzeit übergibt. Ein Fehler von ERiC führt nie in die Simulation.

## Datenarten

Was ERiC und der Kopf einer Lieferung außer den Nutzdaten brauchen, hängt an ihrer Datenart: „Mit dem Verfahren, der Datenart und gegebenenfalls dem unterstützten Jahr (AZ) werden aus der Datenartversionmatrix der Parameter datenartVersion für EricBearbeiteVorgang() und das Plugin bestimmt, das zu installieren ist.“ (Kap. 8.1) [`steuerbote/eric/datenart.py`](../steuerbote/eric/datenart.py) beschreibt jede Datenart an einer Stelle (`Datenart`), und alles, was eine Lieferung baut oder prüft, nimmt die Werte von dort: der DatenTeil mit dem NutzdatenHeader (`header.datenteil`, `header.problems`), der Worker für `EricCreateTH` und `EricBearbeiteVorgang`, die Auswahl der Laufzeit und die Statusprüfung (`runtime.detect`, `runtime.status`), die Simulation und der Umschlag der Schematests (`steuerbote/elster/envelope.py`). Der Kopf der Lieferung nennt die Datenart mit seiner datenartVersion; jeder Beleg nennt seine mit `datenart()`.

| Angabe | Voranmeldung und Vordruck USt 1 H | Zusammenfassende Meldung | Grundlage |
|---|---|---|---|
| Verfahren, DatenArt | `ElsterAnmeldung`, `UStVA` | `ElsterExtern`, `ZMDO` | Tabelle 8-8, Tabelle 8-28 |
| Vorgang | `send-Auth`, kein `send-NoSig` | `send-Auth`, kein `send-NoSig` | Tabelle 8-8, Tabelle 8-28 |
| datenartVersion | `UStVA_<Jahr>` | `ZMDO`, ohne Jahr | `Datenartversionmatrix.ods`; Tabelle 2-13: Anmeldungszeitraum „Unabhängig“ bei ZMDO |
| Plugin | `checkUStVA_<Jahr>` | `checkZMDO` | `Datenartversionmatrix.ods`, unter Linux `lib<Plugin>.so` (Kap. 3.1.6.1) |
| Empfänger im NutzdatenHeader | `<Empfaenger id="F">` mit der Bundesfinanzamtsnummer aus der Steuernummer | `<Empfaenger id="L">BF</Empfaenger>` | Tabelle 8-8, Tabelle 8-28, `EmpfaengerIDSType` und `BundeslandSType` in `headerbasis_datentypen.xsd` |
| Schema der Nutzdaten | `Datenarten/ElsterAnmeldung/UStVA/Schema/<Jahr>/UStVA-<Jahr>.xsd`, Wurzel `Anmeldungssteuern` mit der Version `<Jahr>` | `Datenarten/ElsterExtern/ZMDO/Schema/5/zm_000005.xsd`, Wurzel `zm` mit der Version `000005` im Namensraum von ElsterXML 11 | die Schemas der Dokumentation |

Die Namen der UStVA bildet die Jahrestabelle `steuerbote/ustva/years.py` aus dem Jahr. Die Tests vergleichen die Beschreibungen mit den Beispielen, Schemas, der Datenartversionmatrix und der Jahresdokumentation ZMDO der ERiC-Dokumentation (`steuerbote/eric/tests/test_datenart.py`) und den DatenTeil jeder Datenart im ganzen Umschlag mit dessen Schema (`test_header.py`).

## Versionen und Jahreswechsel

- Mitte November erscheint das Hauptrelease mit dem neuen Jahr, zuerst als Beta, mit der keine Echtfälle gesendet werden können (Kap. 2.3, 5.4.3); ERiC weist sie mit dem Fehler 610001020 ab. Das Hauptrelease hat eine ungerade Hauptversion, die Beta ist seine erste Auslieferung `<major>.1` (Kap. 3.1.1 und die Grafik zum Releasezyklus), etwa ERiC 45.1 mit `UStVA_2027` (Releasenotes 45.1.5.0, Kap. 3). Anfang Mai folgt ein technisches Release mit gerader Hauptversion.
- Im April steigt die Mindestversion; ältere Releases weisen die Annahmeserver dann ab (Kap. 5.4.2, § 5 Abs. 6 des Lizenzvertrags).
- Die datenartVersion `UStVA_<Jahr>` braucht das Plugin `checkUStVA_<Jahr>`, unter Linux `libcheckUStVA_<Jahr>.so` (`Datenartversionmatrix.ods`, Kap. 3.1.6.1). ERiC 44 kennt die Jahre 2016 bis 2026 (Tabelle 2-13). Beide Namen bildet die Jahrestabelle [`steuerbote/ustva/years.py`](../steuerbote/ustva/years.py) aus dem Jahr (`datenart_version`, `plugin`, `plugin_library`), und die Einrichtung liest mit `plugin_year` die Jahre der Plugins eines Archivs ins Manifest. Ein neues Jahr braucht dafür keinen Eintrag, solange die Datenartversionmatrix die Plugins so benennt; die Jahresprüfung vergleicht das jedes Jahr, siehe [Entwicklung, Jahreswechsel](entwicklung.md#jahreswechsel). Die Zusammenfassende Meldung hat ein Plugin für alle Jahre, `checkZMDO`; ob eine Laufzeit es hat, liest Steuerbote aus den Dateien ihres Manifests, für jede schon eingerichtete Version.
- Steuerbote nimmt für das Jahr einer Voranmeldung die neueste eingerichtete Laufzeit mit diesem Plugin, die keine Beta ist, für eine Zusammenfassende Meldung ebenso die neueste mit `checkZMDO`. Kennt nur eine Beta das Jahr, prüft und testsendet Steuerbote mit ihr, denn eine Beta weist nur Echtfälle ab (Kap. 5.4.3); Senden braucht immer eine freigegebene Laufzeit. Fehlt das Plugin, nennt die Statusprüfung das Jahr.
- Für den Betrieb heißt das: im November die neue Version einrichten und mit ihr testen, die freigegebene Folgeversion einrichten, sobald sie erscheint, und vor April prüfen, ob die eingerichtete Version die Mindestversion erreicht.
- Die Dokumentation des Hauptrelease enthält schon mit der Beta Jahresdokumentation und Schema des neuen Jahres, die Dokumentation 45.1.5.0 etwa `Jahresdokumentation_UStVA_2027.ods` und `UStVA-2027.xsd`. Mit ihr beginnt der Jahreswechsel im Code; ein Plugin für ein Jahr, dessen Daten Steuerbote noch nicht hat, bleibt ungenutzt, denn Berechnen und XML brauchen erst Katalog, Schema und Vordruck des Jahres.

## Simulation

Ohne Laufzeit antwortet die Simulation (`steuerbote.eric.fake.Simulation`) auf dieselben Vorgänge, ohne etwas zu übermitteln. So lässt sich der ganze Ablauf vom Knopf bis zum Übermittlungsprotokoll nutzen und testen, bevor es eine Hersteller-ID gibt.

- Sie prüft den Kopf der Lieferung, für die UStVA, dass die Nutzdaten XML ohne DTD sind und die Wurzel `Anmeldungssteuern` im Namensraum des Jahres haben, und von den Regeln der Jahresdokumentation UStVA 2026, die das Schema nicht abbildet, die zum Aufbau: genau einer der Kontexte `Umsatzsteuervoranmeldung`, `Dauerfristverlaengerung` und `Umsatzsteuersondervorauszahlung` im Steuerfall (110085099, `SIM-006`), die Pflichtfelder des Kontexts (`SIM-004`), in der Voranmeldung Kz 83 (110085064), im Vordruck USt 1 H Jahr, Steuernummer und Kz 09 (110085048, 110085044, 110085045) und in der Anmeldung der Sondervorauszahlung Kz 38 (110085143), und dass das Jahr des Kontexts das Jahr der Datenart ist (110085047, 110085130, 110085131, `SIM-007`).
- Nennt die Umgebungsvariable `STEUERBOTE_ERIC_DOC_DIR` die entpackte ERiC-Dokumentation oder ihr Verzeichnis `Dokumentation`, prüft sie die Nutzdaten zusätzlich gegen das Schema ihrer Datenart, `UStVA-<Jahr>.xsd` oder `zm_000005.xsd`. Die Schemata gehören nicht in das Repository, weil ihre Weitergabe nicht geregelt ist. Ohne sie sagt ein Hinweis, dass nur der Aufbau geprüft wurde.
- Testsenden und Senden liefern ein Transferticket `SIM-` mit den ersten 28 Hexadezimalziffern der SHA-256-Summe der Nutzdaten. Diese Form hat kein Transferticket von ERiC. Dazu kommt eine einseitige PDF-Datei mit dem Satz, dass die Übermittlung nur simuliert und nichts an ELSTER übermittelt wurde, mit Zeitraum und Kz 83 der Voranmeldung oder dem Vordruck mit seinem Jahr und Kz 38.
- Die Nutzdaten der Zusammenfassenden Meldung prüft sie nach den Regeln der Jahresdokumentation ZMDO, die ihren Aufbau betreffen: die Wurzel `zm` in der Version `000005` (`SIM-003`), die Pflichtfelder von Unternehmer, Meldezeilen und Meldezeitraum und jeder Meldezeile (`SIM-004`, etwa 170015001 oder 170045002), keine USt-IdNr. und Art zweimal (`SIM-008`, 170045003 bis 170045005) und höchstens 5.000 Meldezeilen (`SIM-009`), mit der Dokumentation auch gegen `zm_000005.xsd`, das sie in den Namensraum von ElsterXML 11 nimmt. Ihr Platzhalter-PDF nennt Meldezeitraum, Meldeart und Zahl der Meldezeilen, siehe [Zusammenfassende Meldung](zm.md#simulation).
- Jedes Ergebnis ist als simuliert gekennzeichnet und trägt den Hinweis `SIM-000`. Ein simuliertes Ergebnis ist nie eine Abgabe.

## Vorgänge

| Vorgang | Aufruf von `EricBearbeiteVorgang` | Braucht | Liefert |
|---|---|---|---|
| Prüfen | Hinweisprüfung, Validierung und Vorschaudruck (EBV-9, Tabelle 6-2), ohne Verschlüsselungsparameter | Laufzeit, auch eine Beta, eigene Hersteller-ID, bestätigte Datenschutzhinweise | Fehler, Hinweise, Vorschau-PDF ohne Sendedatum und Transferticket (Kap. 5.1.5.6) |
| Testsenden | Validierung, Versand mit `send-Auth` und Druck (EBV-6), mit Testmerker 700000004 | dazu Zertifikat und PIN; ELSTER-Testzertifikate nur hier (Kap. 4.3.5.1) | Transferticket, PDF mit „*** Testfall ***“ (Kap. 5.1.5.7); der Annahmeserver löscht den Fall sofort nach Eingang (Tabelle 6-7) |
| Senden | wie Testsenden, ohne Testmerker | Laufzeit, die keine Beta ist, Organisationszertifikat | Transferticket und Übertragungsprotokoll (Kap. 5.1.4.4) |

Die Datenart UStVA kennt nur `send-Auth` (Tabelle 8-8), ebenso ZMDO (Tabelle 8-28), jedes Senden braucht also ein Zertifikat, für die Voranmeldung, den Vordruck USt 1 H und die Zusammenfassende Meldung; „Daten werden signiert versendet.“ (Tabelle 5-2). Den Testmerker 700000004 nimmt auch ZMDO, wie das Beispiel `ZMDO_5_send-Auth.xml` zeigt (Kap. 6.5.5, Tabelle 6-7). Ein Aufruf läuft so ab (Kap. 6.2.4): `EricInitialisiere` mit dem Plugin- und dem Protokollverzeichnis, Einstellungen (Verbindungsaufbau 30 Sekunden, Antwort 60 Sekunden statt unbegrenzt, je 100 statt 20 Fehler und Hinweise, Tabelle 4-1), Zertifikat aus dem Speicher öffnen (`EricZertifikatOeffnenAusBytes`), `EricCreateTH` schreibt den TransferHeader um den DatenTeil, wie das Handbuch empfiehlt (Kap. 5.1), `EricBearbeiteVorgang`, `EricGetErrormessagesFromXMLAnswer` liest Transferticket und Rückmeldungen der Serverantwort, Zertifikat schließen, `EricBeende`. ERiC 44 spricht nur noch mit einem Annahmeserver und nennt das Transferticket nur in dessen Antwort (Releasenotes 44.3.6.0, Kap. 5.2.7).

### Ergebnisse

| Ergebnis | Bedeutung |
|---|---|
| gültig | Geprüft ohne Fehler, Hinweise sind möglich. Nichts wurde gesendet. |
| ungültig | Die Plausibilitätsprüfung hat Fehler gefunden (610001002). Nichts wurde gesendet. |
| angenommen | Der Annahmeserver hat die Daten angenommen; das Transferticket steht in seiner Antwort. |
| abgewiesen | Der Annahmeserver meldet einen Fehler im TransferHeader (610101210) oder in einem NutzdatenHeader (610101292), etwa bei einer veralteten ERiC-Version. |
| fehlgeschlagen | Nichts wurde gesendet. Der Vorgang endete, bevor ERiC die Daten bearbeitete (Einrichtung, Kopf der Lieferung, Form der PIN, Öffnen des Zertifikats), oder ERiC brach ohne Serverantwort mit einem Code ab, der nur vor der Übermittlung entsteht. |
| unbekannt | Jeder andere Code von ERiC beim Senden, etwa Zeitüberschreitung (610101283), keine Antwort (610101279), Fehler beim Datenaustausch (610101271) oder ein Fehler beim Druck nach der Übermittlung (610501001 bis 610501015), dazu der Abbruch des Worker-Prozesses und jede Ausnahme, nachdem er gestartet ist, etwa die Zeitüberschreitung des Hintergrundjobs. Liefert ERiC eine Serverantwort, stehen sie und ihr Transferticket im Ergebnis. Ob die Daten angekommen sind, ist offen. Nicht erneut senden, bevor das geklärt ist. |

Welche Codes vor der Übermittlung entstehen, folgt aus der Reihenfolge, in der `EricBearbeiteVorgang` arbeitet: Einlesen, Validieren, Vorbereiten mit Signatur und Verschlüsselung, Senden, Drucken (Abbildung 6-6). ERiC validiert vor jedem Senden (Kap. 6.2.1) und prüft die Größe der Daten vor der Übermittlung (Kap. 5.1.3.3); gedruckt wird erst, wenn der Annahmeserver OK gemeldet hat (Kap. 5 mit Abbildung 5-1). `BEFORE_TRANSFER` in `steuerbote/eric/worker.py` nennt deshalb nur Codes zu Aufruf und Parametern, zu Hersteller-ID, Testmerker, Beta und Plugin, zum Einlesen, Validieren und zur Größe der Daten, zu Zertifikat, PIN, Signatur und Verschlüsselung (das Zertifikat dient bei der UStVA nur der Signatur, Kap. 5.2) und zu einer Verbindung, die nicht zustande kam. Nach anderen Fehlern sind die Puffer undefiniert (API-Referenz, `EricBearbeiteVorgang`). Eine Serverantwort liest Steuerbote trotzdem, wann immer ERiC eine liefert, denn auch nach einer Zeitüberschreitung kann sie das Transferticket enthalten (Kap. 6.2.5.2); mit einer Serverantwort ist auch ein Code aus `BEFORE_TRANSFER` ein unbekanntes Ergebnis.

Die Meldungen tragen den Code von ERiC, den Fehler- oder Hinweiscode der Regel oder den Code des Servers. Eigene Codes von Steuerbote beginnen mit `SB-`: `SB-HEADER` (Kopf der Lieferung), `SB-PIN`, `SB-ERIC` (ERiC lässt sich nicht laden oder antwortet unlesbar), `SB-TICKET`, `SB-WORKER` und `SB-UNKNOWN`. Die Simulation verwendet `SIM-000` bis `SIM-009`.

## Proxy

Erreicht der Server ELSTER nur über einen Proxy, nennen ihn die ERiC-Einstellungen im Abschnitt „Proxy“: die Proxy-URL und, wenn der Proxy eine Anmeldung verlangt, Benutzer und Passwort in eigenen Feldern. Das Passwort ist ein Passwortfeld von Frappe und liegt verschlüsselt in der Site.

| Proxy-URL | `http.proxy_host` | `http.proxy_port` |
|---|---|---|
| `http://proxy.example.com:3128` | `proxy.example.com` | `3128` |
| `socks4://proxy.example.com:1080` | `socks4://proxy.example.com` | `1080` |
| `socks5://[2001:db8::1]:1080` | `socks5://[2001:db8::1]` | `1080` |

- **Einstellungen von ERiC.** ERiC nimmt einen Proxy als API-Einstellungen von `EricEinstellungSetzen` (Kap. 4.1.2.2, Tabelle 4-2): `http.proxy_host`, „IP-Adresse oder Hostname des Proxys“, `http.proxy_port` und, mit Benutzer und Passwort, `http.proxy_username` und `http.proxy_password`. Der Worker setzt sie nach `EricInitialisiere` und vor dem Zertifikat, wie es der Ablauf eines Aufrufs vorsieht: „Falls ein Proxy verwendet wird, müssen die Proxy-Parameter mit EricEinstellungSetzen() gesetzt werden“ (Kap. 6.2.4). Sie gelten nur für die Instanz von ERiC, an der sie gesetzt wurden (Kap. 5.3.14), also für einen Lauf.
- **Port ist Pflicht.** „Proxy-Port muss angegeben werden, falls http.proxy_host gesetzt wurde, andernfalls schlägt der Versand mit dem Rückgabecode ERIC_TRANSFER_ERR_PROXYPORT_INVALID fehl.“ (Tabelle 4-2) Eine URL ohne Port lehnt das Speichern ab.
- **SOCKS ohne Anmeldung.** „Das SOCKS4- und SOCKS5-Protokoll ohne Authentifizierung wird unterstützt. Der Protokollname ist dem Hostname voranzustellen“ (Tabelle 4-2). Steuerbote nimmt deshalb `http://`, `socks4://` und `socks5://`, einen SOCKS-Proxy nur ohne Benutzer und Passwort, Benutzer und Passwort nur zusammen und nie in der URL.
- **Authentifizierungsschema.** `http.proxy_auth` behält den Voreinstellungswert Any. Erwartet ein Proxy ein bestimmtes Schema, zeigt `eric.log` den Fehler 407 des Proxys (Kap. 4.1.2.2); ein Feld dafür hat Steuerbote noch nicht.
- **Weg des Passworts.** Das Passwort des Proxys geht wie Zertifikat und PIN nur über die Standardeingabe an den Worker, in der versiegelten Anfrage (`Sealed`), und erscheint weder in Ausgaben noch in Tracebacks; `Proxy` zeigt es nicht in seiner Darstellung.
- **Simulation.** Die Simulation erreicht keinen Server und lässt den Proxy beiseite.

`steuerbote/eric/proxy.py` prüft die URL und bildet die Einstellungen, `transmission_adapter.settings_proxy` liest den Proxy der ERiC-Einstellungen für jeden Lauf mit Laufzeit.

## Sicherheit

- **Zertifikat und PIN nur je Vorgang.** Beide werden für einen Vorgang eingegeben, nie gespeichert und nie protokolliert. Für den Weg in den Hintergrundjob legt `steuerbote.eric.secrets` sie mit dem Schlüssel der Site verschlüsselt (Fernet) unter einem zufälligen Token für höchstens 15 Minuten im Redis-Cache ab. Der Job erhält nur das Token und holt beide genau einmal ab (`GETDEL`). Jobargumente selbst blieben tagelang in Redis und erschienen in der Liste der RQ-Jobs.
- **Ein Prozess je Vorgang.** ERiC läuft in einem kurzlebigen Worker-Prozess (`python -m steuerbote.eric.worker`) ohne Frappe und mit `LANG` und `PATH` als einziger Umgebung. Ein Absturz in ERiC beendet nur diesen Prozess, und nur ein Prozess lässt sich bei einer Zeitüberschreitung beenden: Threads in ERiC dürfen nicht abgebrochen werden (Kap. 5.3.14). Nach 120 Sekunden ohne Antwort beendet Steuerbote den Prozess samt Prozessgruppe, ebenso bei jeder Ausnahme im Hintergrundjob, während der Prozess läuft.
- **Nichts Geheimes in Ausgaben.** Zertifikat und PIN erreichen den Worker nur über die Standardeingabe. Bevor er sie liest, macht er sich nicht dumpbar (`prctl(PR_SET_DUMPABLE, 0)`) und setzt die Größe von Core-Dateien auf 0. Seine Ausgaben nennen weder Zertifikat noch PIN, bei Fehlern nur das Feld oder die Art des Fehlers. Die Kopien von PIN und Zertifikat für ERiC werden überschrieben, sobald ERiC sie nicht mehr braucht. Das Zertifikat liegt nie als Datei auf der Platte; ERiC öffnet es aus dem Speicher (API-Referenz, `EricZertifikatOeffnenAusBytes`).
- **Nichts Geheimes in Tracebacks.** Im Entwicklermodus schreibt Frappe die lokalen Variablen jedes Rahmens in das Fehlerprotokoll und verbirgt nur Werte, deren Variable oder Schlüssel password, secret, token oder key im Namen trägt. Jede Variable mit Zertifikat oder PIN trägt deshalb secret oder password im Namen. Die Anfrage an den Worker und der Klartext für den Redis-Cache sind `Sealed` (`steuerbote/eric/sealed.py`) und erscheinen in jedem Rahmen als Platzhalter, auch in denen der Standardbibliothek wie `subprocess.Popen.communicate`.
- **PIN.** Die PIN einer Zertifikatsdatei hat 6 bis 128 ASCII-Zeichen vom Leerzeichen bis zur Tilde (Tabelle 5-3); Steuerbote weist andere vor dem Aufruf ab. Fehlversuche sperren eine Zertifikatsdatei nicht (Tabelle 5-4).
- **Protokoll `eric.log`.** ERiC schreibt sein Protokoll in das Verzeichnis, das der Aufruf nennt, rollierend in bis zu vier Dateien zu je 10 MiB (Kap. 4.1.3.3). Für den ELSTER-Support ist die Datei vollständig weiterzugeben (Kap. 4.1.3.4), an die Finanzverwaltung nur mit ausdrücklicher Erlaubnis der Anwender (§ 15).

## Aufbewahrung

Steuerbote löscht nichts, was ein Lauf hinterlässt. Was bleibt, wo es liegt und wer es löscht:

- **ELSTER-Übermittlung und ihre Dateien.** Nutzdaten, Protokoll und Antwort des ELSTER-Servers hängen als private Dateien an der Übermittlung, unter `sites/<site>/private/files` und in jeder Sicherung mit Dateien, siehe [Übermittlung an ELSTER](uebermittlung.md#wo-xml-und-protokoll-liegen). Eine Übermittlung, die eine Abgabe festhält, lässt sich nicht löschen: Sie gehört mit dem Übermittlungsprotokoll zu den Unterlagen, die das Unternehmen nach § 147 AO aufbewahrt; wie lange, klärt es mit der Steuerberatung. Jede andere Übermittlung darf der System Manager löschen.
- **`eric.log`.** Das Protokoll von ERiC liegt je Übermittlung unter `sites/<site>/logs/eric/<Übermittlung>`, außerhalb der Datenbank, mit höchstens 40 MiB je Verzeichnis. Es dient der Fehlersuche mit dem ELSTER-Support. Steuerbote löscht es nicht, auch nicht mit seiner Übermittlung, und eine Sicherung mit `bench backup --with-files` enthält es nicht. Der Betreiber legt fest, wie lange er die Verzeichnisse braucht, und löscht ältere selbst, etwa mit einem Cron-Job.
- **Fehlerprotokoll.** Unerwartete Fehler eines Laufs schreibt Steuerbote mit dem Traceback in das Fehlerprotokoll (Error Log) von Frappe. Zertifikat und PIN stehen nie darin, siehe [Sicherheit](#sicherheit), im Entwicklermodus aber womöglich Steuerdaten aus den lokalen Variablen. Frappe löscht die Einträge jeden Tag, sobald sie älter sind als die Tage, die die Protokolleinstellungen (Log Settings) unter „Zu löschende Protokolle“ für das Fehlerprotokoll nennen; ohne eigenen Eintrag sind es in Frappe 16 14 Tage (`default_log_clearing_doctypes` in `frappe/hooks.py`). Wer Einträge länger braucht oder kürzer halten will, stellt die Zahl dort ein.

## Grenzen

- Nur Linux x86_64, nur die Datenarten UStVA mit Voranmeldung und Vordruck USt 1 H und ZMDO mit der Zusammenfassenden Meldung, ein Nutzdatenblock je Lieferung.
- Ein Proxy nur mit dem Authentifizierungsschema, das ERiC von sich aus wählt (`http.proxy_auth` = Any, Tabelle 4-2), siehe [Proxy](#proxy).
- Kein gespeichertes Zertifikat; es wird für jeden Vorgang neu eingegeben.
- Die Tests laufen gegen eine Stub-Bibliothek, die die dokumentierten Signaturen nachbildet. Wie sich das echte ERiC verhält, zeigt erst ein Lauf mit Hersteller-ID und ELSTER-Testzertifikat.
- Die Simulation prüft weit weniger als ERiC, das alle Plausibilitätsregeln des Jahres anwendet.
- Ob Betreiber eine eigene Hersteller-ID brauchen oder die von Steuerbote nutzen dürfen, ist noch zu klären.

## Aufbau im Code

| Modul | Inhalt |
|---|---|
| `result.py` | `Operation`, `Outcome`, `Message`, `TransmissionResult`, Exitcodes des Workers |
| `datenart.py` | `Datenart`: Verfahren, DatenArt, Vorgang, datenartVersion, Plugin, Empfänger und Schema der UStVA eines Jahres (`ustva`) und der ZMDO (`ZMDO`), siehe [Datenarten](#datenarten) |
| `header.py` | `EnvelopeHeader`, der DatenTeil für `EricCreateTH` mit dem Empfänger der Datenart, Prüfung des Kopfs |
| `api.py` | ctypes-Anbindung von ERiC 44, Druckparameter Version 4, Verschlüsselungsparameter Version 3 |
| `runtime.py` | Einrichtung aus dem Archiv, Auswahl der Laufzeit nach dem Plugin der Datenart, Statusprüfung |
| `worker.py` | der Worker-Prozess, der ERiC einmal aufruft |
| `proxy.py` | `Proxy`, die Proxy-URL der ERiC-Einstellungen geprüft und als Einstellungen von ERiC |
| `fake.py` | die Simulation, mit den Prüfungen des Aufbaus je Datenart |
| `service.py` | `run` und `library_versions` für die Frappe-Schicht |
| `sealed.py` | `Sealed`, Bytes mit Zertifikat oder PIN, die sich in Tracebacks als Platzhalter zeigen |
| `secrets.py` | Übergabe von Zertifikat und PIN an den Hintergrundjob, das einzige Modul mit Frappe |

Der Worker liest ein JSON-Objekt von der Standardeingabe und schreibt eines auf die Standardausgabe. Exitcode 0 heißt, die Antwort steht auf der Standardausgabe, gleich mit welchem Ergebnis; 2 heißt, die Anfrage war nicht verständlich und nichts wurde geladen; 1 steht für einen unerwarteten Fehler, dessen Art auf der Standardfehlerausgabe steht.

Die Tests der Anbindung, des Workers und des Dienstes laufen gegen `steuerbote/eric/tests/stub/ericapi_stub.c`. Der Stub ist aus der API-Referenz geschrieben, kennt die datenartVersionen `UStVA_<Jahr>` und `ZMDO`, solange ihr Plugin im Plugin-Verzeichnis liegt, prüft Versionen und Felder der Parameterstrukturen, die erlaubten Kombinationen der Bearbeitungsflags, Zertifikats-Handle und PIN, zeichnet auf, was er erhalten hat, und antwortet mit festen Puffern; Marker in den Nutzdaten lösen Fehlercodes, eine Wartezeit oder einen Absturz aus, etwa `STUB-TIMEOUT`, `STUB-ABORT`, `STUB-PRINT-ERROR` (Fehler beim Druck nach angenommener Übermittlung) und `STUB-TIMEOUT-ANSWER` (Zeitüberschreitung mit Serverantwort und Transferticket). Die Tests bauen ihn beim ersten Gebrauch mit `cc`; ohne Compiler werden sie mit einem Hinweis übersprungen. Die CI baut ihn vorab mit allen Warnungen als Fehler und gibt den Pfad in `STEUERBOTE_ERIC_STUB` weiter, dort schlägt ein fehlender Compiler also fehl. `tests/test_secrets.py` braucht Redis und eine Site und läuft nur mit `bench run-tests`; dort prüft es auch, was `frappe.get_traceback(with_context=True)` von Zertifikat und PIN zeigt. Ohne Frappe bildet `tests/tracebacks.py` diese Ausgabe für die Tests des Dienstes nach.
