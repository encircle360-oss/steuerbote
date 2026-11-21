# Übermittlung an ELSTER

Steuerbote übermittelt die Umsatzsteuer-Voranmeldung, die Dauerfristverlängerung (Vordruck USt 1 H) und die Zusammenfassende Meldung über ERiC, die Schnittstelle der Finanzverwaltung. An allen drei Belegen gibt es dafür die Gruppe „ELSTER“ mit drei Vorgängen, „Prüfen“, „Testsenden“ und „Senden“, und den Vermerken „In Mein ELSTER abgegeben“ (an der Dauerfristverlängerung „In Mein ELSTER eingetragen“) und „Als außerhalb abgegeben vermerken“ für Meldungen, die auf anderem Weg zum Finanzamt oder zum BZSt gehen. Jeder Vorgang läuft im Hintergrund und hinterlässt eine ELSTER-Übermittlung mit Ergebnis, Meldungen und Dateien. Wie ERiC selbst eingebunden ist, beschreibt [ERiC](eric.md).

Diese Seite beschreibt die Vorgänge an der Voranmeldung. An der Dauerfristverlängerung und an der Zusammenfassenden Meldung laufen sie genauso, mit demselben Dialog, derselben Sperre, denselben Ergebnissen und derselben ELSTER-Übermittlung; was dort anders ist, steht unter [Dauerfristverlängerung](#dauerfristverlängerung) und [Zusammenfassende Meldung](#zusammenfassende-meldung).

Ohne eigene Hersteller-ID oder ohne installierte ERiC-Laufzeitumgebung läuft Steuerbote im [Simulationsmodus](#simulationsmodus). Dann geht nichts an das Finanzamt.

## Die Vorgänge

| Vorgang | Was passiert | Was es braucht | Folge für die Meldung |
|---|---|---|---|
| Prüfen | ERiC prüft die Meldung nach den Prüfregeln von ELSTER und liefert Fehler, Hinweise und ein Vorschau-PDF. Nichts geht an das Finanzamt. | berechnete Meldung im Entwurf | keine |
| Testsenden | Die Meldung geht als Testfall mit dem Testmerker 700000004 an den ELSTER-Server. Der löscht sie beim Eingang, ohne sie weiterzuleiten. | berechnete Meldung im Entwurf, Zertifikatsdatei (.pfx) und Zertifikats-Passwort | keine, sie bleibt ein Entwurf |
| Senden | Die Meldung geht an das Finanzamt. ELSTER antwortet mit Transferticket und Übermittlungsprotokoll. | Meldung „Bereit“ oder mit Begründung in den Anmerkungen, Zertifikatsdatei und Zertifikats-Passwort, Berechtigung zum Buchen, ERiC-Laufzeitumgebung, Hersteller-ID und bestätigte Datenschutzhinweise | wird gebucht, Status „Abgegeben“ |
| In Mein ELSTER abgegeben | Kein ERiC. Steuerbote vermerkt, dass die Meldung in Mein ELSTER abgegeben wurde, etwa mit der [Datei für Mein ELSTER](abgabe-mein-elster.md). | Meldung wie zum Senden; Transferticket, Tag der Abgabe und Anmerkungen nach Wunsch | wird gebucht, Status „Abgegeben“ |
| Als außerhalb abgegeben vermerken | Kein ERiC. Steuerbote vermerkt, dass die Meldung auf anderem Weg abgegeben wurde, etwa durch die Steuerberatung. | Meldung wie zum Senden, ein Vermerk, wie und wann sie abgegeben wurde; Transferticket und Tag der Abgabe nach Wunsch | wird gebucht, Status „Abgegeben“ |

Dabei gilt:

- **Erst speichern und berechnen.** Die Schaltflächen erscheinen an einer gespeicherten Meldung im Entwurf mit dem Status „Berechnet“ oder „Bereit“. Ungespeicherte Änderungen weist Steuerbote ab, weil der Hintergrundjob nur die gespeicherte Meldung kennt.
- **Buchen allein gibt nichts ab.** Eine Meldung im Entwurf hat keine Schaltfläche „Buchen“ und nicht den Hinweis von Frappe, sie zu buchen: Abgegeben wird sie durch Senden oder durch einen der beiden Vermerke, die sie buchen. Ist sie „Bereit“, steht über dem Formular „Bereit zur Abgabe: XML für Mein ELSTER erzeugen oder über ELSTER übermitteln.“ Die einzige Ausnahme ist eine Meldung, die ELSTER angenommen hat, die sich danach aber nicht buchen ließ, siehe [Sonderfälle](#ablauf-eines-vorgangs).
- **Datenlieferant und Steuernummer.** Jeder Vorgang schreibt die Meldung in denselben Aufbau wie die [Datei für Mein ELSTER](abgabe-mein-elster.md), dazu die Hersteller-ID in Kz 09. Die Einstellungen Umsatzsteuer-Voranmeldung des Unternehmens brauchen deshalb Straße, Postleitzahl und Ort des Datenlieferanten. Das Finanzamt, an das die Meldung geht, sind die ersten vier Stellen der Steuernummer im ELSTER-Format. Steuernummer und Datenlieferant liest der Hintergrundjob erst beim Lauf aus den Einstellungen, nicht aus der Meldung: Übermittelt wird mit der Steuernummer, die die Einstellungen in diesem Augenblick halten, und die ELSTER-Übermittlung hält sie in ihren Nutzdaten fest. Ändern dürfen die Einstellungen deshalb nur Accounts Manager und System Manager; Accounts User lesen sie. Wer die Rollen anders vergibt, gibt mit dem Schreibrecht an den Einstellungen auch die Wahl der Steuernummer und des Finanzamts weiter.
- **Fehler und Hinweise des letzten Laufs.** Nach jedem Prüfen, Testsenden oder Senden steht über dem Formular der Meldung, wie viele Fehler und Hinweise ERiC oder die Simulation gemeldet hat, mit den ersten drei jeder Art und dem Link auf die ELSTER-Übermittlung, die alle hält; die ELSTER-Übermittlung zählt sie über ihren Nachrichten ebenso. Hinweise halten eine Meldung nicht an: „Grundsätzlich ist aber ein Datensatz, für den Hinweise aber keine Fehler gemeldet werden, valide und könnte versendet oder gedruckt werden.“ (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.1.2.4.1) Ein Prüfen mit Hinweisen ist deshalb erfolgreich, und erst die Hinweise zeigen, was ELSTER anmerkt, etwa eine fehlende Wirtschafts-Identifikationsnummer (11085154).
- **Laufzeitumgebung des Jahres.** Außerhalb der Simulation nimmt Steuerbote die neueste installierte Laufzeitumgebung mit dem Plugin für das Jahr der Meldung, die keine Beta ist. Hat keine freigegebene Laufzeitumgebung das Plugin, nehmen Prüfen und Testsenden eine Beta; Senden geht mit einer Beta nie.
- **Eine Übermittlung zur Zeit.** Während ein Vorgang läuft, steht an der Meldung „Übermittlung läuft“. Bis zu seinem Ende lässt sie sich nicht berechnen, speichern oder buchen, damit genau das gebucht wird, was übermittelt wurde. Ist der Vorgang beendet, erscheint ein Hinweis, und das Formular lädt neu.
- **Berechtigungen.** Prüfen und Testsenden darf, wer die Meldung bearbeiten darf (Accounts User, Accounts Manager, System Manager). Senden und die Vermerke darf nur, wer buchen darf (Accounts Manager, System Manager).
- **Ein Zeitraum wird einmal abgegeben.** Ein Zeitraum gilt als abgegeben, sobald eine seiner Meldungen gebucht ist oder eine seiner Meldungen über Steuerbote gesendet wurde, mit Annahme durch ELSTER oder unbekanntem Ergebnis, auch wenn sie später storniert wurde. Danach lehnt Steuerbote für jede andere Meldung des Zeitraums Senden, die Vermerke und die Datei für Mein ELSTER ab, außer für eine berichtigte Anmeldung (Kz 10). Eine Meldung, die schon mit Transferticket übermittelt ist oder deren Senden ein unbekanntes Ergebnis hat, lässt sich nicht noch einmal senden, und Steuerbote schreibt für sie keine Datei für Mein ELSTER mehr, mit der sie ein zweites Mal abgegeben würde.
- **Keine Stornierung einer abgegebenen Meldung.** Eine Meldung, die ELSTER angenommen hat oder die als abgegeben vermerkt ist, lässt sich nicht stornieren, denn das nähme beim Finanzamt nichts zurück. Eine Änderung geht als [berichtigte Anmeldung](#berichtigte-anmeldung-kz-10).

## Dauerfristverlängerung

Der Beleg „Dauerfristverlängerung“ übermittelt den Vordruck USt 1 H eines Unternehmens für ein Jahr, siehe [Dauerfristverlängerung](dauerfristverlaengerung.md#der-beleg-in-erpnext). Er gehört zur Datenart UStVA, also gelten Laufzeitumgebung, Plugin und Kopf der Lieferung der Voranmeldung (`UStVA_<Jahr>`, ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 2-13). Anders als an der Voranmeldung:

- **Die Nutzdaten** sind der Kontext des Vordrucks, `Umsatzsteuersondervorauszahlung` bei monatlicher oder `Dauerfristverlaengerung` bei vierteljährlicher Abgabe, mit der Hersteller-ID in Kz 09, siehe [XML für ERiC](dauerfristverlaengerung.md#xml-für-eric). Eine Datei für Mein ELSTER gibt es nicht.
- **Ein Jahr wird einmal abgegeben.** Ist für das Unternehmen und Jahr schon ein Vordruck abgegeben oder über Steuerbote gesendet, mit Annahme durch ELSTER oder unbekanntem Ergebnis, auch wenn er später storniert wurde, gehen Senden und Vermerk nur für eine berichtigte Anmeldung der Sondervorauszahlung (Kz 10). Den Antrag allein kann man nicht berichtigen.
- **Ein Jahr ohne Vordruck oder Schema** in Steuerbote lässt sich nicht übermitteln, nur von Hand in Mein ELSTER abgeben.
- **Nach einem angenommenen Senden** ist der Beleg abgegeben über ERiC, am Tag der Antwort, mit dem Transferticket, und seine Sondervorauszahlung steht in den Einstellungen des Unternehmens.
- **Berichtigen** heißt eine abgegebene Anmeldung der Sondervorauszahlung stornieren und mit „Ändern“ als berichtigte Anmeldung (Kz 10) neu anlegen; das Stornieren nimmt beim Finanzamt nichts zurück.
- **Die Vermerke** legen ebenfalls eine ELSTER-Übermittlung mit dem Vorgang „Außerhalb abgegeben“ an.

## Zusammenfassende Meldung

Der Beleg „Zusammenfassende Meldung“ übermittelt die ZM eines Unternehmens für einen Meldezeitraum an das BZSt, siehe [Zusammenfassende Meldung](zm.md#zm-über-eric). Sie ist eine eigene Datenart, ZMDO des Verfahrens ElsterExtern, mit dem Vorgang `send-Auth` (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 8.15, Tabelle 8-28), beschrieben in [`steuerbote/eric/datenart.py`](../steuerbote/eric/datenart.py). Anders als an der Voranmeldung:

- **Das BZSt ist der Empfänger.** Der Kopf der Lieferung nennt `<Empfaenger id="L">BF</Empfaenger>` statt des Finanzamts, die Steuernummer braucht die ZM nicht. Die datenartVersion ist `ZMDO` ohne Jahr, und die Laufzeitumgebung ist die neueste freigegebene mit dem Plugin `checkZMDO`; hat nur eine Beta das Plugin, prüft und testsendet Steuerbote mit ihr, Senden geht mit einer Beta nie.
- **Die Nutzdaten** sind das Element `zm` mit den Meldezeilen der Meldung, bei einer Berichtigung nur mit den Zeilen, die die bisherigen Abgaben ändern. Den Unternehmer nehmen sie aus den Einstellungen: USt-IdNr., Teilnehmernummer beim BZSt, Name und Anschrift des Datenlieferanten, siehe [Der Unternehmer aus den Einstellungen](zm.md#der-unternehmer-aus-den-einstellungen). Eine Hersteller-ID steht nur im Kopf der Lieferung. Die Simulation prüft den Aufbau nach den Regeln der Jahresdokumentation ZMDO, siehe [Simulation](zm.md#simulation).
- **Senden braucht das Hauptbuch, wie „Berechnen“ es gelesen hat.** Hat sich seit dem Berechnen ein Beleg der Monate geändert, lehnt Steuerbote das Senden ab und nennt ihn, wie bei der CSV-Datei für Mein ELSTER. Prüfen und Testsenden gehen trotzdem.
- **Ein Meldezeitraum wird einmal abgegeben.** Ist eine Meldung des Meldezeitraums eingereicht oder über Steuerbote gesendet, mit Annahme durch ELSTER oder unbekanntem Ergebnis, gehen Senden, Vermerk und CSV-Datei jeder anderen Meldung des Meldezeitraums nur als Berichtigung, die „Berichtigung anlegen“ an der abgegebenen Meldung anlegt.
- **Eine Übermittlung zur Zeit, und keine Prüfung der USt-IdNrn. daneben.** Während ein Vorgang läuft, lassen sich die USt-IdNrn. nicht prüfen, und während sie geprüft werden, startet kein Vorgang.
- **Nach einem angenommenen Senden** ist die Meldung abgegeben über ERiC, am Tag der Antwort, mit dem Transferticket, und vermerkt von dem, der gesendet hat. Eine Berichtigung setzt die frühere Meldung des Meldezeitraums auf „Ersetzt“. Scheitert das Einreichen, ändern sich an der Meldung nur noch die Anmerkungen, wie an jedem Beleg unter [Sonderfälle](#ablauf-eines-vorgangs): Berechnen, USt-IdNrn. prüfen, die CSV-Datei, Verwerfen und jedes andere Speichern lehnt Steuerbote ab, und „Buchen“ reicht sie ein, wie sie gesendet wurde.
- **Ohne Hersteller-ID** bleibt die [CSV-Datei für Mein ELSTER](zm.md#csv-datei-für-mein-elster) der Weg zum BZSt. Die Vermerke legen wie an der Voranmeldung eine ELSTER-Übermittlung mit dem Vorgang „Außerhalb abgegeben“ an.

## Zertifikat und Passwort

Testsenden und Senden brauchen die Zertifikatsdatei (.pfx) des ELSTER-Kontos der Firma und ihr Passwort. Beides wird für jeden Vorgang neu eingegeben.

- Der Browser liest die Zertifikatsdatei. Sie wird nicht als Anhang hochgeladen.
- Zertifikat und Passwort gehen einmal an den Server. Dort liegen sie mit dem Schlüssel der Site verschlüsselt und höchstens 15 Minuten im Zwischenspeicher, bis der Hintergrundjob sie einmal abholt; ein zweites Abholen gibt es nicht. Weder an der Meldung noch an der ELSTER-Übermittlung, im Hintergrundjob oder in einem Protokoll wird eines von beiden gespeichert, auch nicht im Recorder von Frappe oder in einem Fehlerbericht. Lassen sie sich nicht ablegen, sagt das eine Meldung, die keines von beiden nennt, siehe [ERiC](eric.md#sicherheit).
- Zertifikat und Passwort gelten nur für den Benutzer, der sie eingegeben hat, und für die Meldung, an der er sie eingegeben hat. Startet ein anderer Benutzer oder für eine andere Meldung mit ihnen einen Vorgang, lehnt Steuerbote ab und verlangt sie neu; der Hintergrundjob erhält nie etwas, womit sich Zertifikat und Passwort abholen ließen, außer dem Namen seiner ELSTER-Übermittlung.
- Die Zertifikatsdatei darf höchstens 32 KiB groß sein, und jeder Benutzer kann Zertifikat und Passwort höchstens zehnmal in einer Viertelstunde an den Server geben.
- Das Passwort hat 6 bis 128 Zeichen: Buchstaben, Ziffern, Leerzeichen und Satzzeichen, ohne Umlaute (ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 5-3).
- Testzertifikate von ELSTER taugen nur für Testsenden.

## Simulationsmodus

Solange in den ERiC-Einstellungen keine Laufzeitumgebung installiert oder keine Hersteller-ID eingetragen ist, ist der Simulationsmodus aktiv. Die Meldung zeigt dann einen orangefarbenen Hinweis mit Verweis auf die ERiC-Einstellungen, und die Schaltflächen heißen „Prüfen (Simulation)“ und „Testsenden (Simulation)“. Die Bestätigung der Datenschutzhinweise braucht die Simulation nicht.

- Nichts geht an ELSTER oder an das Finanzamt.
- Prüfen prüft den Aufbau der Daten, mit der ERiC-Dokumentation auch gegen das Schema des Jahres, aber nicht die Prüfregeln von ELSTER, siehe [ERiC](eric.md#simulation). Ein simuliertes Prüfen liefert kein PDF.
- Testsenden braucht weder Zertifikat noch Passwort. Das Ergebnis trägt ein Transferticket, das mit „SIM-“ beginnt und nie einem echten gleicht, und ein Platzhalter-PDF statt des Übermittlungsprotokolls. Ist keine Hersteller-ID eingetragen, steht 00000 an ihrer Stelle, im Kopf der Lieferung wie in Kz 09.
- Senden gibt es nicht, und die Meldung bleibt, wie sie ist. Abgeben lässt sie sich von Hand oder per XML-Import in Mein ELSTER und danach mit „In Mein ELSTER abgegeben“ festhalten.
- In der Liste der ELSTER-Übermittlungen trägt jeder simulierte Lauf zusätzlich zu seinem Status die Markierung „Simuliert“.

## ERiC-Einstellungen

Die ERiC-Einstellungen gelten für die ganze Installation, nicht je Firma, denn die Hersteller-ID gehört zur Software. Bearbeiten darf sie nur der System Manager.

| Feld | Inhalt |
|---|---|
| Simulationsmodus | berechnet: aktiv, solange keine Laufzeitumgebung installiert oder keine Hersteller-ID eingetragen ist |
| Datenschutzhinweise gelesen und bestätigt | Vor der Nutzung von ERiC sind die Datenschutzhinweise der Finanzverwaltung zur Kenntnis zu nehmen und zu bestätigen (§ 5 Abs. 1 und 2 des ERiC-Lizenzvertrags). Ihr Text liegt dem ERiC-Download aus dem ELSTER-Entwicklerbereich bei. Ohne die Bestätigung lehnt Steuerbote jeden Vorgang mit ERiC ab; die Simulation läuft trotzdem. |
| Bestätigt von, Bestätigt am | wer die Datenschutzhinweise bestätigt hat und wann, gesetzt beim Speichern; gelöscht, wenn die Bestätigung zurückgenommen wird |
| Hersteller-ID | fünf Ziffern, im ELSTER-Entwicklerbereich an den Hersteller der Software vergeben. Dieselbe Hersteller-ID steht im Kopf jeder Lieferung, in Kz 09 der Nutzdaten und in der Laufzeitumgebung. Die Hersteller-ID 74931 der ERiC-Dokumentation lehnt Steuerbote ab, weil sie nur der Veranschaulichung dient. |
| Produktname | Vorgabe „steuerbote“, höchstens 50 Zeichen. Der Name darf das Wort ELSTER nicht enthalten (§ 12 der ERiC-Nutzungsbedingungen). |
| Produktversion | Version von Steuerbote, wird gesetzt |
| Datenlieferant | wer die Daten liefert, für den Kopf der Lieferung, höchstens 256 Zeichen: Firma; Ansprechpartner; Telefon; E-Mail; Ort; PLZ; Straße; Land. Zeilenumbrüche werden zu Semikolons. |
| ERiC-Archiv | nur zur Anzeige: der absolute Pfad des Archivs für Linux x86_64 auf dem Server, den der Betreiber als `steuerbote_eric_archive` in die `common_site_config.json` der Bench einträgt |
| SHA-256 des Archivs | nur zur Anzeige: die Prüfsumme des Archivs, 64 hexadezimale Stellen, aus `steuerbote_eric_archive_sha256` derselben Datei |
| Installierte Version, Verzeichnis der Bibliotheken, Letzte Prüfung | setzt die Installation |
| Verzeichnis der Logdateien | wo ERiC seine Protokolldatei `eric.log` ablegt, je ELSTER-Übermittlung ein Verzeichnis unter `sites/<site>/logs/eric/` |
| Proxy-URL | nur wenn der Server ELSTER über einen Proxy erreicht: `http://`, `socks4://` oder `socks5://` mit Host und Port, etwa `http://proxy.example.com:3128`; leer heißt ohne Proxy. Die Simulation erreicht keinen Server und braucht keinen. |
| Benutzer des Proxys, Passwort des Proxys | nur zusammen und nur für einen Proxy über `http://`; das Passwort liegt verschlüsselt in der Site und geht für jeden Lauf an ERiC, siehe [ERiC](eric.md#proxy) |

### Laufzeitumgebung installieren

Steuerbote enthält kein ERiC und lädt es auch nicht herunter. ERiC dürfen nur Lizenznehmer der Finanzverwaltung nutzen, und zwar in ihrem eigenen Produkt. Jeder Betreiber holt sein ERiC deshalb selbst:

1. Im ELSTER-Entwicklerbereich anmelden, die Nutzungsbedingungen annehmen, das ERiC-Archiv für Linux x86_64 herunterladen und auf den Server legen.
2. Auf dem Server die Signatur des Archivs mit `jarsigner` prüfen, seine SHA-256 bilden und beides in die `common_site_config.json` der Bench eintragen, mit `bench set-config -g steuerbote_eric_archive <Pfad>` und `bench set-config -g steuerbote_eric_archive_sha256 <SHA-256>`, siehe [ERiC](eric.md#einrichtung-durch-den-betreiber). Das ist Sache des Betreibers des Servers: Die ERiC-Einstellungen zeigen Pfad und SHA-256 nur an, und die `site_config.json` einer Site zählt nicht, denn eine Laufzeitumgebung dient allen Sites der Bench, und ihre Probe lädt die Bibliothek des Archivs als Benutzer der Bench.
3. In den ERiC-Einstellungen die Datenschutzhinweise lesen und bestätigen und speichern.
4. „Laufzeitumgebung installieren“ wählen. Die Installation läuft im Hintergrund und liest Pfad und SHA-256 selbst aus der `common_site_config.json`: Sie prüft die SHA-256, entpackt die Bibliotheken für Linux x86_64, lädt sie einmal zur Probe und legt die Version erst danach ab. Ist sie fertig, erscheinen ein Hinweis und die installierte Version. Schlägt sie fehl, nennt der Hinweis die Ursache, Einzelheiten zu unerwarteten Fehlern stehen im Fehlerprotokoll.

Die Laufzeitumgebungen liegen außerhalb jeder Site im Verzeichnis `sites/eric` der Bench, das `steuerbote_eric_root` in `common_site_config.json` ändern kann. Sie werden weder ausgeliefert noch mit einer Site gesichert. Vor jedem Vorgang mit ERiC prüft Steuerbote die Bibliotheken der Laufzeitumgebung gegen ihr Manifest; ist eine verändert, fehlt eine oder liegt eine fremde Datei oder ein Link darunter, lehnt es den Vorgang ab und nennt die Abweichung. Wie Versionen und Jahreswechsel zusammenhängen, steht in [ERiC](eric.md#versionen-und-jahreswechsel).

### Laufzeitumgebung prüfen

„Laufzeitumgebung prüfen“ zeigt dem System Manager die Statusprüfungen von ERiC: Plattform, eingerichtete Laufzeitumgebung, ob ihre Bibliotheken unverändert sind, ob eine freigegebene Laufzeitumgebung das Plugin des laufenden Jahres für die Voranmeldung und das Plugin `checkZMDO` für die Zusammenfassende Meldung hat, und die Hersteller-ID, siehe [ERiC](eric.md#statusprüfung). Die Prüfung ändert nichts.

## Ablauf eines Vorgangs

1. Bei Testsenden und Senden fragt ein Dialog nach Zertifikatsdatei und Zertifikats-Passwort, im Simulationsmodus nur nach einer Bestätigung.
2. Steuerbote prüft die Meldung: Entwurf, berechnet, ihre Beträge stimmen mit den gespeicherten Kennzahlen überein (an der Dauerfristverlängerung Grundlage und Kz 38 mit dem gespeicherten Vordruck, an der Zusammenfassenden Meldung Meldezeilen und Summen mit ihren gespeicherten Belegen und Korrekturen), kein anderer Vorgang läuft, außerhalb der Simulation bestätigte Datenschutzhinweise. Für Senden zusätzlich: kein Simulationsmodus, Meldung „Bereit“ oder mit Begründung, der Zeitraum ist nicht schon abgegeben, und die Meldung ist weder übermittelt noch mit unbekanntem Ergebnis gesendet.
3. Steuerbote legt eine ELSTER-Übermittlung mit dem Status „Läuft“ an, sperrt die Meldung und stellt einen Hintergrundjob für genau diese Übermittlung ein.
4. Der Hintergrundjob holt Zertifikat und Passwort ab, schreibt die Nutzdaten, ruft ERiC in einem eigenen, kurzlebigen Prozess oder die Simulation auf, hält Ergebnis, Meldungen und Dateien in der ELSTER-Übermittlung fest, gibt die Meldung wieder frei und benachrichtigt den Benutzer, der den Vorgang gestartet hat.
5. Nach einem Senden, das ELSTER angenommen hat, bucht der Hintergrundjob die Meldung, ihr Status wird „Abgegeben“.

Drei Sonderfälle:

- **Ergebnis unbekannt.** Kommt nach einem Senden keine Antwort zurück, etwa weil ERiC nicht rechtzeitig antwortet oder sein Prozess abbricht, kann die Meldung trotzdem angekommen sein. Die ELSTER-Übermittlung steht dann auf „Unbekannt“, und Steuerbote lehnt jedes weitere Senden der Meldung ab, ebenso das Senden einer anderen Meldung des Zeitraums ohne Kz 10. In Mein ELSTER nachsehen, ob die Meldung eingegangen ist. Ist sie eingegangen, die Meldung mit „In Mein ELSTER abgegeben“ und dem Transferticket aus Mein ELSTER festhalten. Ist sie nicht eingegangen, löscht ein System Manager die ELSTER-Übermittlung, danach lässt sich die Meldung erneut senden und wieder ändern. Bis dahin ändern sich an ihr nur die Anmerkungen, denn das Finanzamt kann sie haben, wie sie gesendet wurde: Speichern mit anderen Werten, Berechnen, Verwerfen und die Datei für Mein ELSTER lehnt Steuerbote ab.
- **Übermittelt, aber nicht gebucht.** Scheitert das Buchen nach einem erfolgreichen Senden, hält die ELSTER-Übermittlung Transferticket und Grund fest, und die Meldung bleibt ein Entwurf. Das Formular sagt das und bietet „Buchen“ an. Dann nicht erneut senden, denn das Finanzamt hat die Meldung schon; Steuerbote lehnt ein zweites Senden und die Vermerke ohnehin ab. Nach Behebung der Ursache die Meldung mit „Buchen“ einreichen. Bis dahin ändern sich an ihr nur die Anmerkungen: Speichern mit anderen Werten, Berechnen, Verwerfen und die Datei für Mein ELSTER lehnt Steuerbote ab, und auch „Buchen“ nur mit den Werten, mit denen sie gesendet wurde. Eine Änderung geht danach als berichtigte Anmeldung (Kz 10), an der Zusammenfassenden Meldung als Berichtigung.
- **Abgebrochener Hintergrundjob.** Bricht ein Hintergrundjob ab, etwa durch einen Neustart des Servers, bleibt seine ELSTER-Übermittlung auf „Läuft“ und die Meldung gesperrt. Beim nächsten Öffnen der Meldung löst das Formular die Sperre selbst und schließt die Übermittlung: ein Prüfen als „Fehlgeschlagen“, ein Testsenden oder Senden als „Unbekannt“, mit den Folgen des ersten Sonderfalls. Danach sind die Schaltflächen wieder da. Ein abgebrochener Job, der später doch noch anläuft, tut nichts mehr.

## ELSTER-Übermittlung

Jeder Vorgang und jeder Vermerk ist eine ELSTER-Übermittlung. Die Liste steht unter „ELSTER-Übermittlung“, die Übermittlungen eines Belegs stehen am Beleg unter „Verknüpfungen“. Eine ELSTER-Übermittlung nennt ihren Beleg mit Dokumententyp und Dokument. Übermittlungen aus Versionen bis 0.2, die nur eine Umsatzsteuer-Voranmeldung nennen konnten, ordnet `bench migrate` einmal ihrer Voranmeldung zu.

| Feld | Inhalt |
|---|---|
| Dokumententyp, Dokument, Unternehmen | der Beleg, eine Umsatzsteuer-Voranmeldung, eine Dauerfristverlängerung oder eine Zusammenfassende Meldung, und sein Unternehmen |
| Vorgang | Prüfen, Testsenden, Senden oder Außerhalb abgegeben |
| Status | Läuft, Erfolgreich, Fehlgeschlagen oder Unbekannt |
| Ergebnis laut ERiC | Gültig oder Ungültig nach Prüfen, Angenommen oder Abgelehnt nach einem Senden, Fehlgeschlagen, wenn nichts gesendet wurde, Unbekannt, wenn offen ist, ob ein Senden angekommen ist |
| Simuliert | der Lauf ging an die Simulation, nicht an ERiC |
| Gestartet am, Beendet am, Benutzer | wann und von wem |
| Transferticket | die Nummer, unter der ELSTER die Meldung angenommen hat |
| Testmerker | 700000004 bei Testsenden |
| ERiC-Version | die Version der Laufzeitumgebung oder „simulation“ |
| Abgegeben über, Abgegeben am | bei einem Vermerk: Mein ELSTER oder auf anderem Weg, und der Tag der Abgabe |
| Anmerkungen | der Vermerk einer Abgabe außerhalb von Steuerbote |
| Nachrichten | Fehler und Hinweise von ERiC, von der Simulation oder von Steuerbote mit Code, Nachricht und Feld; über dem Formular steht, wie viele Fehler und Hinweise es sind |
| Nutzdaten (XML), Protokoll (PDF), Antwort des ELSTER-Servers (XML) | die Dateien des Laufs, siehe unten |

Eine ELSTER-Übermittlung schreibt nur der Server, danach lässt sie sich nicht mehr ändern. Eine Übermittlung, die eine Abgabe festhält (ein erfolgreiches Senden außerhalb der Simulation oder ein Vermerk), lässt sich nicht löschen. Andere darf nur der System Manager löschen. Eine Meldung mit ELSTER-Übermittlungen lässt sich nicht löschen. „Transaktionen löschen“ am Unternehmen in ERPNext lässt Meldungen und Übermittlungen aus, solange niemand sie von Hand in die Liste der zu löschenden DocTypes einträgt, siehe [Prüfung ausländischer USt-IdNrn.](ust-idnr-pruefung.md#in-erpnext).

## Wo XML und Protokoll liegen

Jeder Lauf legt seine Dateien als private Dateien an seiner ELSTER-Übermittlung ab:

- **Nutzdaten (XML):** die geprüften oder übermittelten Daten der Meldung oder des Vordrucks in UTF-8, wie ERiC sie erhält.
- **Protokoll (PDF):** bei Prüfen mit ERiC die Vorschau, bei Senden das Übermittlungsprotokoll mit Transferticket, beim simulierten Testsenden ein Platzhalter. Ein simuliertes Prüfen legt kein PDF ab.
- **Antwort des ELSTER-Servers (XML):** die Antwort von ELSTER, wenn es eine gibt.

Lässt sich eine Datei nicht speichern, nennt eine Nachricht der ELSTER-Übermittlung sie und den Grund; Ergebnis und Transferticket bleiben trotzdem festgehalten.

Die Dateien bleiben, wie der Lauf sie abgelegt hat. Sie gehören dem Benutzer, der den Vorgang gestartet hat, und Frappe ließe den Eigentümer einer Datei sie ändern und löschen. Steuerbote lehnt deshalb für jede Datei einer ELSTER-Übermittlung ab, sie von der Übermittlung zu lösen oder an einen anderen Beleg oder ein anderes Feld zu hängen, sie öffentlich zu machen, sie auf eine andere Datei zu richten, sie umzubenennen und sie zu löschen, solange es die Übermittlung gibt, für jeden Benutzer (`steuerbote/steuerbote/record_files.py`, eingehängt als `doc_events` für File). Geprüft wird gegen die gespeicherte Datei, nicht gegen das, was eine Anfrage schickt. Löscht ein System Manager eine Übermittlung, die keine Abgabe festhält, gehen ihre Dateien mit ihr. Eine eigene Datei mit demselben Inhalt teilt sich mit der Datei der Übermittlung die Datei auf dem Server, deshalb lässt auch sie sich nicht öffentlich machen. Eingriffe direkt in der Datenbank oder im Dateisystem verhindert das nicht.

Private Dateien liegen im Verzeichnis `sites/<site>/private/files` und öffnen sich nur für Benutzer, die die ELSTER-Übermittlung lesen dürfen. Eine Sicherung mit Dateien (`bench backup --with-files`) enthält sie. Die Nutzdaten enthalten die Steuerdaten der Meldung, Sicherungen sind entsprechend zu schützen. Zertifikat und Passwort sind nie darunter. Die Protokolldatei `eric.log` von ERiC liegt je ELSTER-Übermittlung unter `sites/<site>/logs/eric/<Übermittlung>`; der ELSTER-Support fragt bei Fehlern nach ihr.

## Berichtigte Anmeldung (Kz 10)

Eine abgegebene Meldung lässt sich nicht mehr ändern, erneut senden oder stornieren; eine Stornierung nähme sie beim Finanzamt ohnehin nicht zurück. Eine Korrektur geht so:

1. Eine neue Umsatzsteuer-Voranmeldung für dasselbe Unternehmen und denselben Zeitraum anlegen und „Berichtigte Anmeldung (Kz 10)“ setzen.
2. Berechnen, prüfen und senden, oder außerhalb abgeben und vermerken.
3. Ist die berichtigte Anmeldung abgegeben, steht die frühere Meldung des Zeitraums auf „Ersetzt“.

Ohne Kz 10 lehnt Steuerbote eine zweite Meldung für einen abgegebenen Zeitraum ab, ebenso das Senden, die Vermerke und die Datei für Mein ELSTER für eine Meldung eines Zeitraums, der schon abgegeben ist.

## Als außerhalb abgegeben vermerken

Die Vermerke sind für Meldungen, die nicht über Steuerbote zum Finanzamt gehen. Im Simulationsmodus sind sie der Weg, eine abgegebene Meldung festzuhalten.

- **In Mein ELSTER abgegeben:** nach dem Import der [Datei für Mein ELSTER](abgabe-mein-elster.md) und dem Absenden dort, oder nach einer Eingabe von Hand in Mein ELSTER. Transferticket, Tag der Abgabe und Anmerkungen sind freiwillig; das Transferticket steht im Protokoll von Mein ELSTER.
- **Als außerhalb abgegeben vermerken:** für jeden anderen Weg, etwa über die Steuerberatung. Unter „Wie und wann abgegeben“ steht der Weg; Transferticket und Tag der Abgabe sind freiwillig.

Steuerbote prüft ein Transferticket gegen die Form, die ELSTER vorgibt (32 Zeichen, `TransferTicketSType` im ELSTER-Basisschema), und weist einen Tag der Abgabe in der Zukunft ab. Dann bucht Steuerbote die Meldung, ihr Status wird „Abgegeben“, und legt eine ELSTER-Übermittlung mit dem Vorgang „Außerhalb abgegeben“ an, mit Weg, Tag, Transferticket und Anmerkungen.

Es gelten dieselben Regeln wie beim Senden: Die Meldung muss berechnet sein, ist sie nicht bereit, braucht sie vorher eine Begründung in ihren Anmerkungen, und für einen schon abgegebenen Zeitraum geht nur eine berichtigte Anmeldung. Eine Meldung, die ELSTER angenommen hat, wird nicht vermerkt, sondern gebucht.

Wie die Arbeitspakete der Übermittlung zusammenhängen, steht in der [Roadmap](roadmap.md).
