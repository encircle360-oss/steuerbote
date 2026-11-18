# ERiC

ERiC (ELSTER Rich Client) ist die C-Bibliothek der Steuerverwaltung, die ELSTER-Daten prüft, verschlüsselt, signiert und an die Annahmeserver übermittelt. Steuerbote bindet ERiC ab Version 44 über `ctypes` an und ruft es für „Prüfen“, „Testsenden“ und „Senden“ der Umsatzsteuer-Voranmeldung auf. Diese Seite beschreibt Lizenz, Einrichtung, Versionen, Simulation, Vorgänge, Sicherheit und Grenzen.

Quelle ist die ERiC-Dokumentation 44.3.6.0: Entwicklerhandbuch (zitiert mit Kapitel oder Tabelle), API-Referenz, Releasenotes, Tutorial und der Softwarehersteller-Lizenzvertrag (`lizenz.pdf`, zitiert mit Paragraf). Das Dokumentationspaket ist öffentlich: [ERiC-44.3.6.0-Dokumentation.zip](https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Dokumentation.zip).

## Lizenz und Voraussetzungen

- **Weitergabe nur im eigenen Produkt.** Der Lizenzvertrag erlaubt dem Softwarehersteller, ERiC in eigene Software zu integrieren und mit ihr als einheitliches Produkt zu verbreiten (§ 4 Abs. 1). Das Nutzungsrecht an Dritte zu übertragen oder darüber hinaus Unterlizenzen zu erteilen, ist nicht gestattet (§ 4 Abs. 3).
- **Steuerbote liefert ERiC nicht mit.** Das Repository, die Pakete und die CI enthalten keine Datei von ERiC, und Steuerbote lädt ERiC nicht selbst herunter. Jeder Betreiber lädt ERiC selbst aus dem ELSTER-Entwicklerbereich, nach der Anmeldung und der Annahme des Lizenzvertrags (Tutorial, Kap. 2.5). Die Zugangsdaten kommen einige Tage nach der Registrierung als Softwarehersteller per E-Mail (Tutorial, Kap. 2.2).
- **Eigene Hersteller-ID, auch zum Testen.** ERiC und ELSTER verarbeiten Daten nur mit der eigenen Hersteller-ID, für Echtfälle wie für Testfälle (Kap. 6.5.3). Die frühere Test-Hersteller-ID 74931 dient nur noch der Illustration; seit ERiC 39.4 weist ERiC sie mit dem Fehler 610301202 zurück (Kap. 10.1.1), auch beim bloßen Prüfen. Ohne eigene Hersteller-ID arbeitet Steuerbote deshalb nur in der Simulation. Die Hersteller-ID ist produktbezogen (Kap. 6.5.3).
- **Pflichten gegenüber den Anwendern.** Vor der ersten Nutzung sind die Datenschutzhinweise der Finanzverwaltung zur Kenntnis zu bringen und zu bestätigen (§ 5 Abs. 1 und 2), und die Anwender sind darauf hinzuweisen, dass ERiC Protokolldateien anlegt (§ 15, Kap. 4.1.3). Der Produktname darf „ELSTER“ nicht enthalten (§ 12); Steuerbote prüft das am Produktnamen im NutzdatenHeader. Zu verwenden ist mindestens die Mindestversion (§ 5 Abs. 6).
- **Plattform.** Linux x86_64 mit glibc 2.28 oder neuer und `libgcc_s` (Kap. 2.4.4.5), mindestens 5 GiB freier Speicher für die Programmkomponenten (Tabelle 2-1).

## Einrichtung durch den Betreiber

1. Im ELSTER-Entwicklerbereich anmelden, den Lizenzvertrag annehmen und das Softwarepaket für Linux laden, `ERiC-<version>-Linux-x86_64.jar`. Die JAR-Datei ist ein ZIP-Archiv (Kap. 3.1, 4.3.3).
2. Die SHA-256-Summe des Archivs bilden, etwa mit `sha256sum`, und Pfad und Summe in den ERiC-Einstellungen eintragen.
3. Einrichten lassen. Steuerbote
   - prüft die SHA-256-Summe, bevor es etwas entpackt, und nimmt nur Archive bis 1 GiB;
   - entpackt nur die Dateien unter `ERiC-<version>/Linux-x86_64/lib/`, die Basisbibliotheken und darunter die Plugins (Kap. 3.1.4, Tabellen 3-2 und 3-3), und verlangt `libericapi.so` und das Plugin `libcommonData.so`, das ERiC immer braucht (Kap. 3.1.6.1);
   - weist Pfade außerhalb dieses Verzeichnisses, Links, doppelte Einträge und Bibliotheken zweier Pakete zurück;
   - lädt die Bibliothek zur Probe einmal im Worker-Prozess (`EricInitialisiere`, `EricVersion`, `EricBeende`);
   - legt die Version erst danach als Ganzes unter `<Laufzeitverzeichnis>/<version>/` ab, mit dem Manifest `steuerbote-runtime.json`: SHA-256 des Archivs und jeder Datei, die Jahre der UStVA-Plugins, ob die Version eine Beta ist, Zeitpunkt und Benutzer der Einrichtung.
4. Jede Version liegt in einem eigenen Verzeichnis, denn Basisbibliotheken verschiedener Pakete passen nur garantiert zusammen, wenn sie aus demselben Paket stammen (Kap. 3.1.6.2). Dasselbe Archiv noch einmal einzurichten ändert nichts; ein anderes Archiv mit derselben Version wird abgewiesen.
5. Das Laufzeitverzeichnis liegt außerhalb jeder Site, etwa unter `sites/eric/` der Bench. So wird ERiC weder ausgeliefert noch mit den Sicherungen einer Site gesichert. Steuerbote übergibt den Pfad der Bibliotheken nie an `ldconfig` und setzt kein `LD_LIBRARY_PATH` (Kap. 4.3.3, 4.2.2).

Das Archiv nennt seine Version im Stammverzeichnis `ERiC-<version>/`; fehlt es, gilt die Version aus dem Dateinamen `ERiC-<version>-Linux-x86_64.jar`. Diesen Aufbau beschreibt das Entwicklerhandbuch für das entpackte Paket (Kap. 3.1.4 und Kap. 4.3 mit dem Include-Pfad `ERiC-<version>\Windows-x86\include`). Ein echtes Paket für Linux hat Steuerbote bisher nicht entpackt.

### Statusprüfung

`steuerbote.eric.runtime.status` liefert die Prüfungen für die Statusseite: Plattform (Linux x86_64, glibc ab 2.28), eingerichtete Laufzeit, Bibliotheken unverändert gegenüber dem Manifest, Plugin des Jahres und eigene Hersteller-ID. Die Bestätigung der Datenschutzhinweise prüft die Frappe-Schicht. Die Betriebsart ist ausdrücklich: Die Simulation antwortet nur, wenn die Frappe-Schicht keine Laufzeit übergibt. Ein Fehler von ERiC führt nie in die Simulation.

## Versionen und Jahreswechsel

- Mitte November erscheint das Hauptrelease mit dem neuen Jahr, zuerst als Beta, mit der keine Echtfälle gesendet werden können (Kap. 2.3, 5.4.3); ERiC weist sie mit dem Fehler 610001020 ab. Das Hauptrelease hat eine ungerade Hauptversion, die Beta ist seine erste Auslieferung `<major>.1` (Kap. 3.1.1 und die Grafik zum Releasezyklus), etwa ERiC 45.1 mit `UStVA_2027` (Releasenotes 45.1.5.0, Kap. 3). Anfang Mai folgt ein technisches Release mit gerader Hauptversion.
- Im April steigt die Mindestversion; ältere Releases weisen die Annahmeserver dann ab (Kap. 5.4.2, § 5 Abs. 6 des Lizenzvertrags).
- Die datenartVersion `UStVA_<Jahr>` braucht das Plugin `checkUStVA_<Jahr>`, unter Linux `libcheckUStVA_<Jahr>.so` (`Datenartversionmatrix.ods`, Kap. 3.1.6.1). ERiC 44 kennt die Jahre 2016 bis 2026 (Tabelle 2-13).
- Steuerbote nimmt für das Jahr einer Voranmeldung die neueste eingerichtete Laufzeit mit diesem Plugin, die keine Beta ist. Eine Beta kommt nur für das Testsenden in Frage. Fehlt das Plugin, nennt die Statusprüfung das Jahr.
- Für den Betrieb heißt das: im November die neue Version einrichten und mit ihr testen, die freigegebene Folgeversion einrichten, sobald sie erscheint, und vor April prüfen, ob die eingerichtete Version die Mindestversion erreicht.

## Simulation

Ohne Laufzeit antwortet die Simulation (`steuerbote.eric.fake.Simulation`) auf dieselben Vorgänge, ohne etwas zu übermitteln. So lässt sich der ganze Ablauf vom Knopf bis zum Übermittlungsprotokoll nutzen und testen, bevor es eine Hersteller-ID gibt.

- Sie prüft den Kopf der Lieferung, dass die Nutzdaten XML ohne DTD sind, die Wurzel `Anmeldungssteuern` im Namensraum des Jahres und die Kennzahl 83, die die Jahresdokumentation UStVA 2026 als Pflichtfeld führt (Regel 110085064).
- Nennt die Umgebungsvariable `STEUERBOTE_ERIC_DOC_DIR` die entpackte ERiC-Dokumentation oder ihr Verzeichnis `Dokumentation`, prüft sie die Nutzdaten zusätzlich gegen `UStVA-<Jahr>.xsd`. Die Schemata gehören nicht in das Repository, weil ihre Weitergabe nicht geregelt ist. Ohne sie sagt ein Hinweis, dass nur der Aufbau geprüft wurde.
- Testsenden und Senden liefern ein Transferticket `SIM-` mit den ersten 28 Hexadezimalziffern der SHA-256-Summe der Nutzdaten. Diese Form hat kein Transferticket von ERiC. Dazu kommt eine einseitige PDF-Datei mit dem Satz, dass die Übermittlung nur simuliert und nichts an ELSTER übermittelt wurde.
- Jedes Ergebnis ist als simuliert gekennzeichnet und trägt den Hinweis `SIM-000`. Ein simuliertes Ergebnis ist nie eine Abgabe.

## Vorgänge

| Vorgang | Aufruf von `EricBearbeiteVorgang` | Braucht | Liefert |
|---|---|---|---|
| Prüfen | Hinweisprüfung, Validierung und Vorschaudruck (EBV-9, Tabelle 6-2), ohne Verschlüsselungsparameter | Laufzeit, eigene Hersteller-ID | Fehler, Hinweise, Vorschau-PDF ohne Sendedatum und Transferticket (Kap. 5.1.5.6) |
| Testsenden | Validierung, Versand mit `send-Auth` und Druck (EBV-6), mit Testmerker 700000004 | dazu Zertifikat und PIN; ELSTER-Testzertifikate nur hier (Kap. 4.3.5.1) | Transferticket, PDF mit „*** Testfall ***“ (Kap. 5.1.5.7); der Annahmeserver löscht den Fall sofort nach Eingang (Tabelle 6-7) |
| Senden | wie Testsenden, ohne Testmerker | Laufzeit, die keine Beta ist, Organisationszertifikat | Transferticket und Übertragungsprotokoll (Kap. 5.1.4.4) |

Die Umsatzsteuer-Voranmeldung kennt nur `send-Auth` (Tabelle 8-8), jedes Senden braucht also ein Zertifikat. Ein Aufruf läuft so ab (Kap. 6.2.4): `EricInitialisiere` mit dem Plugin- und dem Protokollverzeichnis, Einstellungen (Verbindungsaufbau 30 Sekunden, Antwort 60 Sekunden statt unbegrenzt, je 100 statt 20 Fehler und Hinweise, Tabelle 4-1), Zertifikat aus dem Speicher öffnen (`EricZertifikatOeffnenAusBytes`), `EricCreateTH` schreibt den TransferHeader um den DatenTeil, wie das Handbuch empfiehlt (Kap. 5.1), `EricBearbeiteVorgang`, `EricGetErrormessagesFromXMLAnswer` liest Transferticket und Rückmeldungen der Serverantwort, Zertifikat schließen, `EricBeende`. ERiC 44 spricht nur noch mit einem Annahmeserver und nennt das Transferticket nur in dessen Antwort (Releasenotes 44.3.6.0, Kap. 5.2.7).

### Ergebnisse

| Ergebnis | Bedeutung |
|---|---|
| gültig | Geprüft ohne Fehler, Hinweise sind möglich. Nichts wurde gesendet. |
| ungültig | Die Plausibilitätsprüfung hat Fehler gefunden (610001002). Nichts wurde gesendet. |
| angenommen | Der Annahmeserver hat die Daten angenommen; das Transferticket steht in seiner Antwort. |
| abgewiesen | Der Annahmeserver meldet einen Fehler im TransferHeader (610101210) oder in einem NutzdatenHeader (610101292), etwa bei einer veralteten ERiC-Version. |
| fehlgeschlagen | Nichts wurde gesendet: Einrichtung, Hersteller-ID, Zertifikat, PIN oder Verbindungsaufbau. |
| unbekannt | Ein Senden ohne Antwort: Zeitüberschreitung (610101283), keine Antwort (610101279), Fehler beim Datenaustausch (610101271) oder Abbruch des Worker-Prozesses. Ob die Daten angekommen sind, ist offen. Nicht erneut senden, bevor das geklärt ist. |

Die Meldungen tragen den Code von ERiC, den Fehler- oder Hinweiscode der Regel oder den Code des Servers. Eigene Codes von Steuerbote beginnen mit `SB-`: `SB-HEADER` (Kopf der Lieferung), `SB-PIN`, `SB-ERIC` (ERiC lässt sich nicht laden oder antwortet unlesbar), `SB-TICKET`, `SB-WORKER` und `SB-UNKNOWN`. Die Simulation verwendet `SIM-000` bis `SIM-005`.

## Sicherheit

- **Zertifikat und PIN nur je Vorgang.** Beide werden für einen Vorgang eingegeben, nie gespeichert und nie protokolliert. Für den Weg in den Hintergrundjob legt `steuerbote.eric.secrets` sie mit dem Schlüssel der Site verschlüsselt (Fernet) unter einem zufälligen Token für höchstens 15 Minuten im Redis-Cache ab. Der Job erhält nur das Token und holt beide genau einmal ab (`GETDEL`). Jobargumente selbst blieben tagelang in Redis und erschienen in der Liste der RQ-Jobs.
- **Ein Prozess je Vorgang.** ERiC läuft in einem kurzlebigen Worker-Prozess (`python -m steuerbote.eric.worker`) ohne Frappe und mit `LANG` und `PATH` als einziger Umgebung. Ein Absturz in ERiC beendet nur diesen Prozess, und nur ein Prozess lässt sich bei einer Zeitüberschreitung beenden: Threads in ERiC dürfen nicht abgebrochen werden (Kap. 5.3.14). Nach 120 Sekunden ohne Antwort beendet Steuerbote den Prozess samt Prozessgruppe.
- **Nichts Geheimes in Ausgaben.** Zertifikat und PIN erreichen den Worker nur über die Standardeingabe. Bevor er sie liest, macht er sich nicht dumpbar (`prctl(PR_SET_DUMPABLE, 0)`) und setzt die Größe von Core-Dateien auf 0. Seine Ausgaben nennen weder Zertifikat noch PIN, bei Fehlern nur das Feld oder die Art des Fehlers. Die Kopien von PIN und Zertifikat für ERiC werden überschrieben, sobald ERiC sie nicht mehr braucht. Das Zertifikat liegt nie als Datei auf der Platte; ERiC öffnet es aus dem Speicher (API-Referenz, `EricZertifikatOeffnenAusBytes`).
- **PIN.** Die PIN einer Zertifikatsdatei hat 6 bis 128 ASCII-Zeichen vom Leerzeichen bis zur Tilde (Tabelle 5-3); Steuerbote weist andere vor dem Aufruf ab. Fehlversuche sperren eine Zertifikatsdatei nicht (Tabelle 5-4).
- **Protokoll `eric.log`.** ERiC schreibt sein Protokoll in das Verzeichnis, das der Aufruf nennt, rollierend in bis zu vier Dateien zu je 10 MiB (Kap. 4.1.3.3). Für den ELSTER-Support ist die Datei vollständig weiterzugeben (Kap. 4.1.3.4), an die Finanzverwaltung nur mit ausdrücklicher Erlaubnis der Anwender (§ 15).

## Grenzen

- Nur Linux x86_64, nur die Datenart UStVA, ein Nutzdatenblock je Lieferung.
- Kein Proxy: Die Einstellungen `http.proxy_*` (Kap. 4.1.2.2) setzt Steuerbote noch nicht.
- Kein gespeichertes Zertifikat; es wird für jeden Vorgang neu eingegeben.
- Die Tests laufen gegen eine Stub-Bibliothek, die die dokumentierten Signaturen nachbildet. Wie sich das echte ERiC verhält, zeigt erst ein Lauf mit Hersteller-ID und ELSTER-Testzertifikat.
- Die Simulation prüft weit weniger als ERiC, das alle Plausibilitätsregeln des Jahres anwendet.
- Ob Betreiber eine eigene Hersteller-ID brauchen oder die von Steuerbote nutzen dürfen, ist noch zu klären.

## Aufbau im Code

| Modul | Inhalt |
|---|---|
| `result.py` | `Operation`, `Outcome`, `Message`, `TransmissionResult`, Exitcodes des Workers |
| `header.py` | `EnvelopeHeader`, der DatenTeil für `EricCreateTH`, Prüfung des Kopfs |
| `api.py` | ctypes-Anbindung von ERiC 44, Druckparameter Version 4, Verschlüsselungsparameter Version 3 |
| `runtime.py` | Einrichtung aus dem Archiv, Auswahl der Laufzeit je Jahr, Statusprüfung |
| `worker.py` | der Worker-Prozess, der ERiC einmal aufruft |
| `fake.py` | die Simulation |
| `service.py` | `run` und `library_versions` für die Frappe-Schicht |
| `secrets.py` | Übergabe von Zertifikat und PIN an den Hintergrundjob, das einzige Modul mit Frappe |

Der Worker liest ein JSON-Objekt von der Standardeingabe und schreibt eines auf die Standardausgabe. Exitcode 0 heißt, die Antwort steht auf der Standardausgabe, gleich mit welchem Ergebnis; 2 heißt, die Anfrage war nicht verständlich und nichts wurde geladen; 1 steht für einen unerwarteten Fehler, dessen Art auf der Standardfehlerausgabe steht.

Die Tests der Anbindung, des Workers und des Dienstes laufen gegen `steuerbote/eric/tests/stub/ericapi_stub.c`. Der Stub ist aus der API-Referenz geschrieben, prüft Versionen und Felder der Parameterstrukturen, die erlaubten Kombinationen der Bearbeitungsflags, Zertifikats-Handle und PIN, zeichnet auf, was er erhalten hat, und antwortet mit festen Puffern; Marker in den Nutzdaten wie `STUB-TIMEOUT` oder `STUB-ABORT` lösen Fehlercodes, eine Wartezeit oder einen Absturz aus. Die Tests bauen ihn beim ersten Gebrauch mit `cc`; ohne Compiler werden sie mit einem Hinweis übersprungen. Die CI baut ihn vorab mit allen Warnungen als Fehler und gibt den Pfad in `STEUERBOTE_ERIC_STUB` weiter, dort schlägt ein fehlender Compiler also fehl. `tests/test_secrets.py` braucht Redis und eine Site und läuft nur mit `bench run-tests`.
