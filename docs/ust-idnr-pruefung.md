# Prüfung ausländischer USt-IdNrn.

Steuerbote lässt sich die USt-IdNr. eines Kunden aus einem anderen Mitgliedstaat im Bestätigungsverfahren nach § 18e UStG bestätigen. Diese Seite beschreibt den Kern unter `steuerbote/vatid`: reines Python ohne Frappe-Import, die Abfrage beim Bundeszentralamt für Steuern (BZSt), das Ausweichen auf VIES, die Bedeutung jeder Antwort und den Datensatz, der als Nachweis bleibt. In ERPNext prüft die Zusammenfassende Meldung damit die USt-IdNrn. ihrer Zeilen und hält jede Abfrage als USt-IdNr.-Bestätigung fest, siehe [In ERPNext](#in-erpnext). Die Seite ersetzt keine Steuerberatung.

Die Quellen stehen am [Ende der Seite](#quellen), alle am 20. November 2026 gelesen.

## Das Bestätigungsverfahren

- **Was bestätigt wird.** „Das Bundeszentralamt für Steuern bestätigt auf Anfrage dem Unternehmer im Sinne des § 2 die Gültigkeit einer Umsatzsteuer-Identifikationsnummer sowie den Namen und die Anschrift der Person, der die Umsatzsteuer-Identifikationsnummer von einem anderen Mitgliedstaat erteilt wurde“ (§ 18e Nr. 1 UStG). Eine deutsche USt-IdNr. bestätigt das BZSt auf diesem Weg nicht.
- **Wer fragt.** „Anfragen zur Bestätigung einer ausländischen USt-IdNr. kann jeder Inhaber einer deutschen USt-IdNr. stellen.“ (UStAE 18e.1 Abs. 1). „Bei der Abfrage muss immer die eigene deutsche USt-IdNr. angegeben werden.“ (BZSt, FAQ). Steuerbote fragt deshalb immer mit der USt-IdNr. des Unternehmens, für das es prüft.
- **Woher die Antwort kommt.** „In Deutschland werden keine Daten zu USt-IdNrn. anderer EU-Mitgliedstaaten gespeichert. Das BZSt leitet Bestätigungsanfragen direkt und automatisiert an die Behörden der jeweiligen EU-Mitgliedstaaten weiter.“ (BZSt, Bestätigung ausländischer USt-IdNrn).
- **Für welchen Zeitpunkt.** Eine Bestätigung gilt für den Zeitpunkt der Anfrage: „Bestätigungen für zurückliegende Zeitpunkte oder Zeiträume sind nicht möglich.“ (BZSt, FAQ). War die Unrichtigkeit einer USt-IdNr. erkennbar und wurde sie nicht erkannt, „z. B. weil das Bestätigungsverfahren nicht oder zu einem späteren Zeitpunkt als dem des Umsatzes durchgeführt wird“, genügt das nicht der Sorgfaltspflicht eines ordentlichen Kaufmanns (UStAE 6a.8 Abs. 6 Satz 1). Eine Prüfung erst mit der Zusammenfassenden Meldung kommt also spät.
- **Wann.** Das BZSt bestätigt „rund um die Uhr“; „Im Zeitraum von 23:00 Uhr bis 05:00 Uhr können Wartungsarbeiten durchgeführt werden“. Derzeit dauern Antworten länger als üblich, und das BZSt bittet: „Bitte sehen Sie von einem unmittelbaren Wiederholen der Anfrage ab.“ (BZSt, Bestätigung ausländischer USt-IdNrn). „Es werden nur Einzelabfragen verarbeitet. Diese werden nacheinander abgearbeitet.“ (ebenda, REST-API). Steuerbote wiederholt deshalb keine Abfrage von selbst und stellt je Aufruf eine Abfrage nach der anderen.
- **Kosten.** „Nein, vom BZSt werden keine Gebühren erhoben.“ (BZSt, FAQ).

## Einfache und qualifizierte Abfrage

Die einfache Abfrage prüft die Gültigkeit der Nummer (UStAE 18e.1 Abs. 3), die qualifizierte zusätzlich „der Name und die Anschrift des Inhabers der ausländischen USt-IdNr.“ (UStAE 18e.1 Abs. 4). „Eine einfache Bestätigung muss zwingend vor einer qualifizierten Bestätigung durchgeführt werden.“ (BZSt, FAQ). Steuerbote stellt deshalb immer zuerst die einfache Abfrage und die qualifizierte nur, wenn der Aufrufer Name und Ort übergibt und das BZSt die Nummer als gültig bestätigt hat. Für eine Nummer, die nicht gültig ist, gibt es nichts zu vergleichen: Die Vergleichsergebnisse kommen nur „im Fall der Gültigkeit“ (OpenAPI-Dokument, Beschreibung von `/v1/abfrage`).

Die Schnittstelle ist die REST-API des BZSt: ein POST an `https://api.evatr.vies.bzst.de/app/v1/abfrage` mit dem JSON-Objekt `Bestaetigungsabfrage` in UTF-8 („Zur reibungslosen Verarbeitung der Daten ist ausschließlich das Zeichenkodierungsformat UTF-8 zu verwenden.“, BZSt, FAQ).

| Feld | Inhalt | Abfrage |
|---|---|---|
| `anfragendeUstid` | die eigene deutsche USt-IdNr. | beide, Pflicht |
| `angefragteUstid` | die USt-IdNr. des Kunden | beide, Pflicht |
| `firmenname` | Name des Kunden mit Rechtsform | qualifiziert, Pflicht |
| `ort` | Ort | qualifiziert, Pflicht |
| `plz` | Postleitzahl | qualifiziert, wenn bekannt |
| `strasse` | Straße und Hausnummer | qualifiziert, wenn bekannt |

Die qualifizierte Abfrage läuft, „wenn zu den Feldern anfragendeUstid und angefragteUstid im Request Body auch mindestens firmenname und ort besetzt sind. Die zusätzlichen Felder strasse und plz sind optional.“ (OpenAPI-Dokument). Die Antwort `Bestaetigungsantwort` hat immer `anfrageZeitpunkt` und `status`, dazu `id` („Technische ID zur Bestaetigungsanfrage“), bei einer ungültigen Nummer gegebenenfalls `gueltigAb` und `gueltigBis` und nach einer qualifizierten Abfrage je Angabe ein Vergleichsergebnis, `ergFirmenname`, `ergStrasse`, `ergPlz` und `ergOrt`:

| Buchstabe | Bedeutung laut OpenAPI-Dokument | VIES |
|---|---|---|
| A | Die Angaben stimmen mit den registrierten Daten überein. | 1 (VALID) |
| B | Die Angaben stimmen mit den registrierten Daten nicht überein. | 2 (INVALID) |
| C | Die Angaben wurden nicht angefragt. | – |
| D | Die Angaben wurden vom EU-Mitgliedsstaat nicht mitgeteilt. | 3 (NOT_PROCESSED) |

„Es gibt bei den Firmendaten eine Fehlertoleranz. Genauere Angaben zu diesen Toleranzen erteilt das Bundeszentralamt für Steuern nicht.“ (BZSt, FAQ). Die Antworten von VIES liest Steuerbote in dieselben Buchstaben, wie die letzte Spalte zeigt; „nicht bearbeitet“ steht dabei für „nicht mitgeteilt“.

Wofür die qualifizierte Bestätigung zählt, zeigt UStAE 3a.2 Abs. 9: Verwendet der Empfänger einer sonstigen Leistung eine USt-IdNr., kann der leistende Unternehmer regelmäßig davon ausgehen, dass der Empfänger Unternehmer ist und die Leistung für sein Unternehmen bezieht (Satz 4). „Voraussetzung ist, dass der leistende Unternehmer nach § 18e UStG von der Möglichkeit Gebrauch gemacht hat, sich die Gültigkeit einer USt-IdNr. eines anderen EU-Mitgliedstaates sowie den Namen und die Anschrift der Person, der diese Nummer erteilt wurde, durch das BZSt bestätigen zu lassen“ (Satz 5).

## Der Datensatz ist der Nachweis

„Bei der Durchführung gleichzeitiger Anfragen zu mehreren USt-IdNrn. über die vom BZSt zu diesem Zweck angebotene Schnittstelle kann die vom BZSt übermittelte elektronische Antwort in Form eines Datensatzes unmittelbar in das System des Unternehmens eingebunden und ausgewertet werden. In diesen Fällen ist der Nachweis einer durchgeführten qualifizierten Anfrage einer USt-IdNr. über den vom BZSt empfangenen Datensatz zu führen.“ (UStAE 18e.1 Abs. 2 Satz 4 und 5). Dasselbe sagt das BZSt zur REST-API (Bestätigung ausländischer USt-IdNrn, „Infos zur REST-API“), und: „Das BZSt versendet keine schriftliche Bestätigungsmitteilung.“ (BZSt, FAQ).

Eine gedruckte Bestätigung gibt es über die Schnittstelle nicht. Zur XML-RPC-Schnittstelle schreibt das BZSt: „Zum 01.01.2021 wurde der UStAE zu § 18e.1 geändert. … Die bisherige Druckfunktion steht deshalb nicht mehr zur Verfügung.“ Diese Schnittstelle ist seit dem 30. November 2025 obsolet; an ihre Stelle tritt die REST-API (BZSt, Bestätigung ausländischer USt-IdNrn, „XML-RPC-Schnittstelle (ab 30.11.2025 obsolet)“).

Deshalb hält Steuerbote jede Antwort fest, wie sie kam: `Confirmation.response_text` ist der empfangene Datensatz. Die Antwort wiederholt weder die Nummern noch Name und Anschrift, etwa `{"id":"…","anfrageZeitpunkt":"2026-11-20T15:35:59.960171228+01:00","status":"evatr-0004"}`; darum steht die Anfrage mit im Datensatz (`steuerbote/vatid/result.py`):

| Feld | Inhalt |
|---|---|
| `requested`, `requester` | angefragte und anfragende USt-IdNr., normalisiert |
| `details` | Name, Ort, Postleitzahl und Straße der qualifizierten Abfrage; leer bei der einfachen |
| `service` | `bzst` oder `vies` |
| `outcome` | `valid`, `invalid` oder `unknown`, siehe [Statusmeldungen des BZSt](#statusmeldungen-des-bzst) |
| `status`, `message` | Status des BZSt mit dem Text seines Katalogs, Fehler oder Ergebnis von VIES, oder ein Code von Steuerbote |
| `consultation_id` | `id` des BZSt oder `requestIdentifier` von VIES |
| `requested_at`, `answered_at` | Zeitpunkt der Anfrage und der Antwort nach der Uhr, die der Aufrufer übergibt, mit Zeitzone |
| `service_time`, `service_date` | `anfrageZeitpunkt` des BZSt und sein Tag, bei VIES nur der Tag (`requestDate`) |
| `valid_from`, `valid_until` | `gueltigAb` und `gueltigBis` des BZSt |
| `name_match`, `street_match`, `postcode_match`, `city_match` | Vergleichsergebnisse A bis D |
| `http_status`, `response_text` | HTTP-Status und Antwort, wie sie kam; leer, wenn keine kam |
| `unavailable` | der Dienst konnte die Anfrage nicht bearbeiten |
| `fallback_reason` | warum VIES an Stelle des BZSt geantwortet hat |
| `previous` | die Abfrage davor in derselben Prüfung |

Eine Prüfung kann zwei Abfragen haben: die einfache und die qualifizierte, oder die beim BZSt und die bei VIES. Jede ist ein eigener Datensatz; `Confirmation.queries()` gibt sie in ihrer Reihenfolge zurück. Ein Ergebnis „gültig“ oder „ungültig“ gibt es nur mit der Antwort, aus der es stammt.

## Ausweichen auf VIES

VIES ist der Dienst der Europäischen Kommission, über den Unternehmen die Gültigkeit einer USt-IdNr. „in accordance to article 31 of Council Regulation (EC) No. 904/2010“ bestätigt bekommen (WSDL von VIES, Dokumentation). Steuerbote fragt VIES nur, wenn das BZSt die einfache Abfrage nicht beantworten konnte:

| Antwort des BZSt auf die einfache Abfrage | VIES |
|---|---|
| keine: Zeitüberschreitung, keine Verbindung, Fehler beim Verbindungsaufbau (`SB-NO-ANSWER`) | ja |
| HTTP 500 oder höher ohne lesbaren Datensatz (`SB-UNREADABLE`) | ja |
| ein Status, den der Katalog mit HTTP 500 oder 503 führt, oder ein unbekannter Status mit HTTP 500 oder höher | ja |
| gültig oder ungültig | nein |
| jeder andere Status, etwa eine falsche eigene USt-IdNr. | nein |
| eine unlesbare Antwort mit HTTP unter 500 | nein |

Eine Antwort des BZSt ersetzt Steuerbote nie durch eine von VIES. Scheitert erst die qualifizierte Abfrage, nachdem das BZSt die Nummer bestätigt hat, fragt Steuerbote VIES ebenfalls nicht: Die Gültigkeit hat das BZSt dann beantwortet, und die qualifizierte Abfrage lässt sich später wiederholen. Mit Name und Anschrift fragt Steuerbote auch VIES qualifiziert, in einer einzigen Abfrage.

Die Abfrage ist `checkVatApprox` über SOAP 1.1 an `https://ec.europa.eu/taxation_customs/vies/services/checkVatService`, mit `countryCode` und `vatNumber` der Nummer, `traderName`, `traderStreet`, `traderPostcode` und `traderCity` für die qualifizierte Abfrage und `requesterCountryCode` und `requesterVatNumber` der eigenen deutschen USt-IdNr. Die Antwort nennt `valid`, `requestDate`, je angefragter Angabe einen Vergleich (`traderNameMatch` usw.) und den `requestIdentifier`, den Steuerbote als Nummer der Abfrage hält (WSDL von VIES, `checkVatApprox` und `checkVatApproxResponse`).

Grenzen:

- Die Antwort von VIES „does not in itself give a right to exempt intra-Community supplies from Value Added Tax“, und ihre Daten sind „obtained from Member States' databases over which the Commission services have no control“ (WSDL von VIES, Dokumentation).
- UStAE 18e.1 Abs. 2 nennt als Nachweis den vom BZSt empfangenen Datensatz, UStAE 3a.2 Abs. 9 Satz 5 die Bestätigung durch das BZSt. Ob ein Finanzamt die Antwort von VIES gelten lässt, sagt keine dieser Quellen; das klärt die Steuerberatung. Bis dahin empfiehlt es sich, die Prüfung beim BZSt nachzuholen, sobald es wieder antwortet.

### Fehler von VIES

Einen Fehler meldet VIES als SOAP-Fault mit einem dieser Werte in `faultstring` (WSDL von VIES, Dokumentation):

| `faultstring` | Bedeutung laut WSDL | Ergebnis |
|---|---|---|
| `INVALID_INPUT` | Das Länderkennzeichen ist ungültig oder die USt-IdNr. leer. | ungültig |
| `GLOBAL_MAX_CONCURRENT_REQ` | Die Höchstzahl gleichzeitiger Anfragen ist erreicht. | unbekannt |
| `MS_MAX_CONCURRENT_REQ` | Die Höchstzahl gleichzeitiger Anfragen an diesen Mitgliedstaat ist erreicht. | unbekannt |
| `SERVICE_UNAVAILABLE` | Im Netz oder in der Anwendung ist ein Fehler aufgetreten. | unbekannt |
| `MS_UNAVAILABLE` | Der Dienst des Mitgliedstaats antwortet nicht oder ist nicht verfügbar. | unbekannt |
| `TIMEOUT` | In der vorgesehenen Zeit kam keine Antwort. | unbekannt |

Außer bei `INVALID_INPUT` rät die WSDL, es später noch einmal zu versuchen; Steuerbote kennzeichnet diese Fehler als `unavailable`. Ein `faultstring`, den die WSDL nicht nennt, lässt das Ergebnis unbekannt und steht mit seinem Wert im Datensatz.

## Statusmeldungen des BZSt

Das BZSt veröffentlicht seine Statusmeldungen unter <https://api.evatr.vies.bzst.de/v1/info/statusmeldungen>, am 20. November 2026 sind es 26. `steuerbote/vatid/bzst.py` führt jede mit Kategorie, HTTP-Code, Feld und Text des Katalogs, wortgleich; `test_bzst.py` vergleicht das mit einer Kopie des Katalogs in `tests/fixtures/statusmeldungen.json`. Das Ergebnis steht im Text der Meldung: gültig, wo sie sagt, die Nummer „ist zum Anfragezeitpunkt gültig“; ungültig, wo die Nummer nicht vergeben, noch nicht oder nicht mehr gültig ist, ihr Länderkennzeichen nicht gültig ist oder sie syntaktisch falsch ist; unbekannt bei allen anderen, denn sie sagen nichts über die Nummer. „VIES ja“ heißt: Der Katalog führt den Status mit HTTP 500 oder 503, das BZSt konnte die Anfrage nicht bearbeiten.

| Status | HTTP | Meldung | Ergebnis | VIES |
|---|---|---|---|---|
| `evatr-0000` | 200 | Die angefragte USt-IdNr. ist zum Anfragezeitpunkt gültig. | gültig | nein |
| `evatr-0001` | – | Bitte bestätigen Sie den Datenschutzhinweis. | unbekannt | nein |
| `evatr-0002` | 400 | Mindestens eins der Pflichtfelder ist nicht besetzt. | unbekannt | nein |
| `evatr-0003` | 400 | Die angefragte USt-IdNr. ist zum Anfragezeitpunkt gültig. Mindestens eines der Pflichtfelder für eine qualifizierte Bestätigungsanfrage ist nicht besetzt. | gültig | nein |
| `evatr-0004` | 400 | Die anfragende DE USt-IdNr. ist syntaktisch falsch. Sie passt nicht in das deutsche Erzeugungsschema. | unbekannt | nein |
| `evatr-0005` | 400 | Die angegebene angefragte USt-IdNr. ist syntaktisch falsch. | ungültig | nein |
| `evatr-0006` | 403 | Die anfragende DE USt-IdNr. ist nicht berechtigt eine DE USt-IdNr. anzufragen. | unbekannt | nein |
| `evatr-0007` | 403 | Fehlerhafter Aufruf. | unbekannt | nein |
| `evatr-0008` | 403 | Die maximale Anzahl von qualifizierten Bestätigungsabfragen für diese Session wurde erreicht. Bitte starten Sie erneut mit einer einfachen Bestätigungsabfrage. | unbekannt | nein |
| `evatr-0011` | 503 | Eine Bearbeitung Ihrer Anfrage ist zurzeit nicht möglich. Bitte versuchen Sie es später noch einmal. | unbekannt | ja |
| `evatr-0012` | 400 | Die angefragte USt-IdNr. ist syntaktisch falsch. Sie passt nicht in das Erzeugungsschema. | ungültig | nein |
| `evatr-0013` | 503 | Eine Bearbeitung Ihrer Anfrage ist zurzeit nicht möglich. Bitte versuchen Sie es später noch einmal. | unbekannt | ja |
| `evatr-1001` | 503 | Eine Bearbeitung Ihrer Anfrage ist zurzeit nicht möglich. Bitte versuchen Sie es später noch einmal. | unbekannt | ja |
| `evatr-1002` | 500 | Eine Bearbeitung Ihrer Anfrage ist zurzeit nicht möglich. Bitte versuchen Sie es später noch einmal. | unbekannt | ja |
| `evatr-1003` | 500 | Eine Bearbeitung Ihrer Anfrage ist zurzeit nicht möglich. Bitte versuchen Sie es später noch einmal. | unbekannt | ja |
| `evatr-1004` | 500 | Eine Bearbeitung Ihrer Anfrage ist zurzeit nicht möglich. Bitte versuchen Sie es später noch einmal. | unbekannt | ja |
| `evatr-2001` | 404 | Die angefragte USt-IdNr. ist zum Anfragezeitpunkt nicht vergeben. | ungültig | nein |
| `evatr-2002` | 200 | Die angefragte USt-IdNr. ist zum Anfragezeitpunkt nicht gültig. Sie ist erst gültig ab dem Datum im Feld gueltigAb. | ungültig | nein |
| `evatr-2003` | 400 | Das angegebene Länderkennzeichen der angefragten USt-IdNr. ist nicht gültig. | ungültig | nein |
| `evatr-2004` | 500 | Eine Bearbeitung Ihrer Anfrage ist zurzeit nicht möglich. Bitte versuchen Sie es später noch einmal. | unbekannt | ja |
| `evatr-2005` | 404 | Die angegebene eigene DE USt-IdNr. ist zum Anfragezeitpunkt nicht gültig. | unbekannt | nein |
| `evatr-2006` | 200 | Die angefragte USt-IdNr. ist zum Anfragezeitpunkt nicht gültig. Sie war gültig im Zeitraum, der durch die Werte in den Feldern gueltigAb und gueltigBis beschrieben ist. | ungültig | nein |
| `evatr-2007` | 500 | Bei der Verarbeitung der Daten aus dem angefragten EU-Mitgliedstaat ist ein Fehler aufgetreten. Ihre Anfrage kann deshalb nicht bearbeitet werden. | unbekannt | ja |
| `evatr-2008` | 200 | Die angefragte USt-IdNr. ist zum Anfragezeitpunkt gültig. Für die qualifizierte Bestätigungsanfrage liegt einer Besonderheit vor. Für Rückfragen wenden Sie sich an das BZSt. | gültig | nein |
| `evatr-2011` | 500 | Eine Bearbeitung Ihrer Anfrage ist zurzeit nicht möglich. Bitte versuchen Sie es später noch einmal. | unbekannt | ja |
| `evatr-3011` | 500 | Eine Bearbeitung Ihrer Anfrage ist zurzeit nicht möglich. Bitte versuchen Sie es später noch einmal. | unbekannt | ja |

Dazu kommen zwei Codes von Steuerbote, beide mit unbekanntem Ergebnis: `SB-NO-ANSWER`, wenn keine Antwort kam, und `SB-UNREADABLE`, wenn die Antwort kein lesbarer Datensatz ist, etwa kein JSON, ohne `status` oder `anfrageZeitpunkt`, oder mit einem Datum oder Vergleichsergebnis, das Steuerbote nicht lesen kann. Ein Status, der nicht im Katalog steht, bleibt mit seinem Code im Datensatz, das Ergebnis ist unbekannt.

Zu einzelnen Status:

- **`evatr-0003`** bestätigt die Nummer als gültig, obwohl ein Pflichtfeld der qualifizierten Abfrage fehlt. Steuerbote stellt die qualifizierte Abfrage nur mit Name und Ort; der Status sollte also nicht vorkommen.
- **`evatr-0004`** bekam eine Probe am 20. November 2026 mit der Beispielnummer `DE123456789` des OpenAPI-Dokuments als anfragender Nummer und einer erfundenen angefragten Nummer, mit HTTP 400. Die Probe zeigt auch, dass das BZSt den Datensatz mit `id`, `anfrageZeitpunkt` und `status` auch zu HTTP 400 sendet. Mit den Werten, die das OpenAPI-Dokument für Testaufrufe nennt, also `DE123456789` als anfragender und `ATU12345678` als angefragter Nummer, für die qualifizierte Abfrage dazu „Musterhaus GmbH & Co KG“, „Musterstrasse 22“, „12345“ und „musterort“, antwortete die API am selben Tag mit HTTP 200 und `evatr-0000`, die qualifizierte Abfrage dazu mit A für Name, Straße, Postleitzahl und Ort; `confirm()` las beide Antworten. Ein Testaufruf ist also mit genau diesen Werten möglich, mit einer anderen angefragten Nummer nicht.
- **`evatr-0006`** kann nicht vorkommen, denn Steuerbote fragt keine deutschen Nummern an.
- **`evatr-0008`** begrenzt die qualifizierten Abfragen „für diese Session“. Wie das BZSt eine Session erkennt, ist nicht beschrieben, siehe [Offene Fragen](#offene-fragen).
- **HTTP-Codes.** Katalog und OpenAPI-Dokument weichen voneinander ab: bei `evatr-0008` (403 im Katalog, 400 im OpenAPI-Dokument) und bei `evatr-1002` bis `evatr-1004` (500 im Katalog, 503 im OpenAPI-Dokument); `evatr-0001`, `evatr-0003`, `evatr-0013` und `evatr-2007` nennt nur der Katalog. Steuerbote richtet sich nach dem Status im Datensatz und seinem Eintrag im Katalog, nicht nach dem HTTP-Code der Antwort.

## Aufbau einer USt-IdNr.

`steuerbote/vatid/ustid.py` prüft eine Nummer, bevor jemand gefragt wird:

- **Plausibel** ist eine Nummer aus 7 bis 14 Zeichen: zwei Großbuchstaben als Länderkennzeichen, danach Buchstaben, Ziffern und die Zeichen + und *. So prüft ERiC die USt-IdNr. einer Zeile der Zusammenfassenden Meldung (Jahresdokumentation ZMDO 2, Feld `knre_UstIdNr_Erwerber`: Muster `[A-Z]{2}[a-zA-Z0-9\+\*]*`, Länge 7 bis 14), und Steuerbote bestätigt die Nummer in der Form, in der es sie meldet. `normalize` behält nur diese Zeichen und schreibt Buchstaben groß, aus „atu 123 456 78“ wird `ATU12345678`.
- **Länderkennzeichen** sind die der Liste des BZSt ohne DE (<https://api.evatr.vies.bzst.de/v1/info/eu_mitgliedstaaten>): die übrigen 26 Mitgliedstaaten, Griechenland mit EL, dazu XI für Nordirland. „Ab dem 01.01.2021 können USt-IdNrn. mit dem Länderkennzeichen "XI" im Bestätigungsverfahren nach § 18e UStG geprüft werden.“ (BZSt, FAQ).
- **Abgewiesen** werden DE, weil § 18e Nr. 1 UStG nur Nummern eines anderen Mitgliedstaats nennt, GB, denn „Nach dem 31.12.2020 können USt-IdNrn. mit dem Länderkennzeichen "GB" nicht mehr im Bestätigungsverfahren nach § 18e UStG geprüft werden“ (BZSt, FAQ), und GR mit dem Hinweis auf EL. `problem()` nennt den Grund als Satz, `is_plausible()` sagt nur ja oder nein.
- **Die anfragende Nummer** ist DE mit neun Ziffern (`is_german()`). Ob ihre Prüfziffer stimmt, prüft das BZSt (`evatr-0004`).

Wie jeder Mitgliedstaat seine Nummern aufbaut, beschreibt das Merkblatt „Aufbau der Umsatzsteuer-Identifikationsnummer (USt-IdNr.) in den EU-Mitgliedstaaten“ des BZSt. Dorthin führt UStAE 18e.2: „Informationen zum Aufbau der USt-IdNrn. in den EU-Mitgliedstaaten sind unter der Internet-Adresse www.bzst.de abrufbar.“ Wo das Merkblatt für eine Stelle keinen Buchstaben nennt, ist sie eine Ziffer.

| Kennzeichen | Mitgliedstaat | Stellen nach dem Kennzeichen laut BZSt |
|---|---|---|
| AT | Österreich | neun, die erste Stelle muss der Buchstabe „U“ sein |
| BE | Belgien | zehn, nur Ziffern; alte neunstellige USt-IdNrn. werden durch Voranstellen der Ziffer 0 ergänzt |
| BG | Bulgarien | neun oder zehn, nur Ziffern |
| CY | Zypern | neun, die letzte Stelle muss ein Buchstabe sein |
| CZ | Tschechien | acht, neun oder zehn, nur Ziffern |
| DK | Dänemark | acht, nur Ziffern |
| EE | Estland | neun, nur Ziffern |
| EL | Griechenland | neun, nur Ziffern |
| ES | Spanien | neun, die erste und die letzte Stelle bzw. die erste oder die letzte Stelle kann ein Buchstabe sein |
| FI | Finnland | acht, nur Ziffern |
| FR | Frankreich | elf, nur Ziffern bzw. die erste und/oder die zweite Stelle kann ein Buchstabe sein |
| HR | Kroatien | elf, nur Ziffern |
| HU | Ungarn | acht, nur Ziffern |
| IE | Irland | acht, die zweite Stelle kann und die letzte Stelle muss ein Buchstabe sein, oder neun Stellen (ab 01.01.2013): 1. bis 7. Stelle Ziffern, 8. Stelle Buchstaben von A bis W, 9. Stelle Buchstaben von A bis I |
| IT | Italien | elf, nur Ziffern |
| LT | Litauen | neun oder zwölf, nur Ziffern |
| LU | Luxemburg | acht, nur Ziffern |
| LV | Lettland | elf, nur Ziffern |
| MT | Malta | acht, nur Ziffern |
| NL | Niederlande | zwölf, Ziffern, Buchstaben und die Zeichen „+“ und „*“ in zufälliger Reihenfolge |
| PL | Polen | zehn, nur Ziffern |
| PT | Portugal | neun, nur Ziffern |
| RO | Rumänien | maximal zehn, nur Ziffern, Ziffernfolge nicht mit 0 beginnend |
| SE | Schweden | zwölf, nur Ziffern, die beiden letzten Stellen bestehen immer aus der Ziffernkombination „01“ |
| SI | Slowenien | acht, nur Ziffern |
| SK | Slowakei | zehn, nur Ziffern |
| XI | Nordirland | neun oder zwölf, nur Ziffern; für Verwaltungen und Gesundheitswesen fünf, die ersten zwei Stellen GD oder HA |

Eine plausible Nummer, die nicht so aufgebaut ist, bekommt nur einen Hinweis (`structure_hint()`) und wird trotzdem angefragt. ERiC meldet eine solche Nummer in der Zusammenfassenden Meldung ebenfalls nur als Hinweis (Regel 17004518, „Unschlüssige Umsatzsteuer-Identifikationsnummer“), und das BZSt prüft den Aufbau selbst und antwortet mit `evatr-0005` oder `evatr-0012`. Diese Antwort ist ein Nachweis wie jede andere; eine Sperre in Steuerbote ließe keinen zurück.

Rumänien ist ein Sonderfall: Das Merkblatt nennt höchstens zehn Ziffern, die nicht mit 0 beginnen, während ERiC für die Zusammenfassende Meldung verlangt, eine rumänische USt-IdNr. „mit 2- bis 4-stelligem Ziffernteil“ „durch Angabe führender Nullen auf 5 Stellen“ aufzufüllen (Jahresdokumentation ZMDO 2, Fehlertext zu `knre_UstIdNr_Erwerber`). Eine so aufgefüllte Nummer ist plausibel und bekommt den Hinweis des Merkblatts. Ob das BZSt sie bestätigt, ist offen.

In der Zusammenfassenden Meldung gilt XI nur für Waren. Für Lieferungen gelten nach Artikel 8 des Protokolls zu Irland/Nordirland die Vorschriften für den innergemeinschaftlichen Handel, aber „Für den Dienstleistungsverkehr mit Nordirland gelten die für das Drittlandsgebiet geltenden Vorschriften zur Umsatzsteuer.“ (BZSt, FAQ). Das prüft die Zusammenfassende Meldung, nicht die Bestätigung.

## Was die Frappe-Schicht übergibt und speichert

`steuerbote.vatid.confirm(requested, requester, details, fetch, clock)` gibt eine `Confirmation` zurück, die der letzten Abfrage. Die Frappe-Schicht übergibt:

- `requested`: die USt-IdNr. des Kunden, in jeder Schreibweise, die `normalize` liest. Vorher zeigt `problem()` den Grund, wenn sie nicht plausibel ist, denn `confirm` weist eine solche Nummer mit `ValueError` ab, bevor es etwas sendet; `structure_hint()` liefert den Hinweis zum Aufbau.
- `requester`: die eigene deutsche USt-IdNr. des Unternehmens aus seinen Einstellungen.
- `details`: `Details(name, city, postcode, street)` für die qualifizierte Abfrage, sonst `None`. Name und Ort sind Pflicht.
- `fetch`: der Transport. `UrllibFetch(timeout_seconds=…, opener=…)` nimmt nur HTTPS, die Zertifikate des Systems und die Proxys der Umgebung; ein eigener `opener` mit `urllib.request.ProxyHandler` setzt einen Proxy. Ein eigener Transport gibt jede HTTP-Antwort zurück, auch mit Status 4xx und 5xx, und wirft `OSError` nur, wenn keine Antwort kam. Je Prüfung ein eigener `UrllibFetch`, denn er hält die Cookies der Dienste.
- `clock`: eine Uhr mit Zeitzone, etwa `lambda: datetime.now(UTC)`.

Die Frappe-Schicht speichert jeden Datensatz aus `queries()` als eigene, nicht änderbare Bestätigung, die Antwort (`response_text`) als private Datei, und zeigt an einer Zeile der Zusammenfassenden Meldung die letzte Prüfung mit Tag, Dienst, Ergebnis, Status und Nummer der Abfrage, siehe [In ERPNext](#in-erpnext). Prüfungen laufen nacheinander, nicht gleichzeitig, und ohne automatische Wiederholung; nach `unavailable` fragt jemand später erneut, nach einer Antwort von VIES auch beim BZSt.

## In ERPNext

„USt-IdNrn. prüfen“ an einer berechneten Zusammenfassenden Meldung im Entwurf fragt nach jeder USt-IdNr., die eine ihrer Zeilen meldet, jede Nummer einmal. Die Prüfung läuft als Hintergrundjob in der Queue `long`. Solange sie läuft, lässt sich die Meldung nicht ändern; ist ihr Job verschwunden, gibt das Formular die Sperre frei. Je Nummer:

1. Anfragende Nummer ist die USt-IdNr. aus den Einstellungen des Unternehmens; ohne sie beginnt keine Prüfung.
2. Name und Ort für die qualifizierte Abfrage kommen aus dem Kunden der Belege der Zeile: sein Name und die Hauptadresse am Kunden, ohne sie seine bevorzugte Rechnungsadresse oder die zuletzt geänderte seiner Adressen, je mit Postleitzahl und erster Adresszeile. Ohne Ort fragt Steuerbote nur einfach.
3. `confirm()` fragt mit einem eigenen `UrllibFetch`, der bis zu 60 Sekunden auf jede Antwort wartet, eine Abfrage nach der anderen und keine zweimal.
4. Jede Abfrage wird als USt-IdNr.-Bestätigung gespeichert und sofort festgeschrieben: Der Datensatz ist der Nachweis einer Abfrage, die der Dienst erhalten hat, und was danach scheitert, nimmt ihn nicht zurück.

Am Ende zeigt jede Zeile die letzte Prüfung ihrer Nummer: Tag, Dienst, Ergebnis, Code und Nummer der Abfrage, mit einem Link auf die Bestätigung. Wer die Prüfung gestartet hat, bekommt eine Nachricht. „Berechnen“ liest die letzte Bestätigung jeder Nummer des Unternehmens ebenso, auch eine aus einer früheren Meldung. Prüfungen der App erpnext_germany (VAT ID Check) zählen nicht, denn sie fragen immer mit dem Standardunternehmen (Entscheidung des Maintainers).

**Was die Meldung daraus macht.** Mit „gültig“ ist die Nummer bestätigt. „Ungültig“ sperrt die Zeile (`ZM-USTID-UNGUELTIG`), „unbekannt“ und eine Nummer ohne Bestätigung sperren sie ebenso (`ZM-USTID-UNBESTAETIGT`). Eine Antwort gilt für den Zeitpunkt der Abfrage: Meldet das BZSt eine Nummer als dann nicht gültig, aber gültig durch alle Monate der Meldung, mit `gueltigAb` und `gueltigBis` (`evatr-2006`) oder ab `gueltigAb` (`evatr-2002`), zählt sie für diese Meldung als bestätigt. Die Befunde nennen den Tag der Abfrage, auf der sie beruhen, etwa „Die USt-IdNr. FR12345678901 ist laut Bestätigungsabfrage vom 20. November 2026 ungültig.“; jede Zeile zeigt ihn ohnehin unter „Geprüft am“. Eine Korrektur der Zeile mit Begründung hebt die Sperre auf (Entscheidung des Maintainers). Das Ergebnis einer Prüfung ist das ihrer letzten Abfrage, die eines hat: Scheitert die qualifizierte Abfrage, nachdem das BZSt die Nummer bestätigt hat, bleibt sie bestätigt; antwortet VIES, weil das BZSt nicht konnte, zählt die Antwort von VIES.

**Die USt-IdNr.-Bestätigung** (`VAT ID Confirmation`) speichert je Abfrage:

| Feld | Inhalt |
|---|---|
| Angefragte USt-IdNr., Anfragende USt-IdNr., Unternehmen | was gefragt wurde und für wen |
| Dienst | BZSt oder VIES |
| Ergebnis der Abfrage, Ergebnis der Prüfung | was der Dienst auf diese Abfrage geantwortet hat, und was die Prüfung bis zu ihr über die Nummer sagt |
| Code, Nachricht, Nummer der Abfrage | Status mit dem Text des Katalogs, `id` des BZSt oder `requestIdentifier` von VIES |
| Qualifizierte Abfrage, Firmenname, Straße und Hausnummer, Postleitzahl, Ort, Ergebnis Name, Ergebnis Straße, Ergebnis Postleitzahl, Ergebnis Ort | Name und Anschrift der qualifizierten Abfrage und ihre Vergleichsergebnisse A bis D |
| Angefragt am, Beantwortet am, Zeitpunkt laut Dienst, Tag laut Dienst | nach der Uhr des Servers in der Zeitzone der Site, und `anfrageZeitpunkt` des Dienstes |
| Gültig ab, Gültig bis | `gueltigAb` und `gueltigBis` des BZSt |
| HTTP-Status, Dienst nicht verfügbar, Warum VIES geantwortet hat, Vorherige Abfrage | wie der Dienst geantwortet hat und welche Abfrage dieser in derselben Prüfung voranging |
| Zusammenfassende Meldung, Benutzer | woher die Prüfung kam und wer sie gestartet hat |
| Antwort (Nachweis) | die Antwort, wie sie kam, als private Datei: JSON vom BZSt, SOAP von VIES |

Nur der Server legt eine Bestätigung an. Über den Beleg ändert oder löscht sie niemand, auch kein System Manager, und ihre Antwort ebenso wenig: Steuerbote lehnt jede Änderung und jedes Löschen der Bestätigung und ihrer Datei ab (`keep_answer`, eingehängt als `doc_events` für File). „Transaktionen löschen“ am Unternehmen in ERPNext löscht dagegen mit `frappe.db.delete` direkt in der Datenbank, an diesen Prüfungen vorbei, und zwar die Belege jedes DocTypes mit einem Link auf das Unternehmen, der nicht unter „Ausgeschlossene DocTypes“ des Datensatzes zur Transaktionslöschung steht. Steuerbote nennt die USt-IdNr.-Bestätigung, die Zusammenfassende Meldung, die Dauerfristverlängerung, die Umsatzsteuer-Voranmeldung und die ELSTER-Übermittlung deshalb im Hook `company_data_to_be_ignored`, aus dem ERPNext diese Liste vorbelegt, und sie kommen nicht in die Liste „Zu löschende DocTypes“ (ERPNext 16.60.0, siehe Quellen). Wer sie dort von Hand einträgt oder aus den ausgeschlossenen herausnimmt, löscht sie trotzdem; das verhindert Steuerbote nicht, so wenig wie einen Eingriff direkt in die Datenbank. Lesen dürfen sie die Rollen Accounts User, Accounts Manager und System Manager.

## Datenschutz

- **Was das System verlässt.** An das BZSt (`api.evatr.vies.bzst.de`) gehen die eigene USt-IdNr. und die des Kunden, bei der qualifizierten Abfrage dazu Name, Ort, Postleitzahl und Straße des Kunden. Das BZSt leitet die Anfrage an die Behörde des Mitgliedstaats weiter, der die Nummer erteilt hat (BZSt, Bestätigung ausländischer USt-IdNrn). Nur wenn das BZSt nicht antworten kann, gehen dieselben Angaben an VIES der Europäischen Kommission (`ec.europa.eu`).
- **Wie.** Nur über HTTPS: „Der Zugriff ist ausschließlich über eine TLS-verschlüsselte HTTPS-Verbindung möglich.“ (BZSt, FAQ). `UrllibFetch` weist jede andere Adresse ab.
- **Personenbezug.** Ist der Kunde eine natürliche Person, etwa ein Einzelunternehmen, sind Name und Anschrift personenbezogene Daten (Art. 4 Nr. 1 DSGVO). Die Verarbeitung bei VIES beschreibt der Data Protection Notice, auf den die WSDL verweist; das BZSt verweist auf seine [Datenschutzerklärung](https://www.bzst.de/DE/Service/Datenschutz/datenschutz_node.html).
- **Was bleibt.** Steuerbote hält jede Antwort, wie sie kam. Bei VIES kann sie Name und Anschrift enthalten, wie der Mitgliedstaat sie registriert hat (`traderName`, `traderAddress`). Cookies der Dienste hält `UrllibFetch` nur im Speicher, je Instanz.

## Offene Fragen

1. **Anmeldung an der REST-API.** Das OpenAPI-Dokument beschreibt kein Verfahren zur Anmeldung, und beide Proben kamen ohne Zugangsdaten aus. Für die XML-RPC-Schnittstelle schrieb das BZSt: „die Nutzung der Schnittstelle ist durch keine Registrierung reglementiert“ (BZSt, FAQ). Für die REST-API sagt es das nicht.
2. **Grenzen für Abfragen.** Eine Höchstzahl je Zeit nennt das BZSt nicht, nur Einzelabfragen nacheinander, kein unmittelbares Wiederholen und `evatr-0008` für die qualifizierten Abfragen einer Session.
3. **Session.** Wie das BZSt eine Session erkennt und ob die qualifizierte Abfrage zur Session der einfachen gehören muss, ist nicht beschrieben. Die erste Probe bekam ein Cookie `AL_BALANCE-S`; `UrllibFetch` hält Cookies je Instanz, damit beide Abfragen einer Prüfung dieselbe Session haben, falls es darauf ankommt.
4. **Format von `gueltigAb` und `gueltigBis`.** Das OpenAPI-Dokument sagt nur „string“. Steuerbote liest ISO 8601 wie bei `anfrageZeitpunkt`; ein anderes Format macht die Antwort unlesbar, mit unbekanntem Ergebnis, und der Datensatz bleibt erhalten.
5. **Rumänische Nummern mit zwei bis vier Ziffern.** Ob das BZSt die für die Zusammenfassende Meldung aufgefüllte Form bestätigt, siehe [Aufbau einer USt-IdNr.](#aufbau-einer-ust-idnr).
6. **VIES als Nachweis.** Für die Steuerberatung, siehe [Ausweichen auf VIES](#ausweichen-auf-vies).

## Quellen

Alle am 20. November 2026 gelesen.

- § 18e UStG „Bestätigungsverfahren“: <https://www.gesetze-im-internet.de/ustg_1980/__18e.html>
- Umsatzsteuer-Anwendungserlass, Stand 13. November 2026, Abschnitte 3a.2 Abs. 9, 6a.8 Abs. 6, 18e.1 und 18e.2: <https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/Umsatzsteuer-Anwendungserlass/Umsatzsteuer-Anwendungserlass-aktuell.pdf?__blob=publicationFile&v=61> (SHA-256 `406cda32cf956d29f2ffde5079c8a7f963a763aa47615c6652148856a23e4c2e`)
- BZSt, „Bestätigung ausländischer USt-IdNrn“, Abschnitte „Abfragemöglichkeiten“, „Hinweis zum Bestätigungsverfahren“, „Infos zur REST-API“ und „XML-RPC-Schnittstelle (ab 30.11.2025 obsolet)“: <https://www.bzst.de/DE/Unternehmen/Identifikationsnummern/Umsatzsteuer-Identifikationsnummer/AuslaendischeUSt-IdNr/auslaendische_ust_idnr_node.html>
- BZSt, „Fragen und Antworten“ zur USt-IdNr. (zitiert als BZSt, FAQ), Abschnitte „Bestätigungsverfahren“, „Bestätigung ausländischer USt-IdNr.“, Nordirland und Großbritannien sowie „Bestätigung via Schnittstelle“: <https://www.bzst.de/DE/Unternehmen/Identifikationsnummern/Umsatzsteuer-Identifikationsnummer/FAQ/faq_ust_node.html>
- BZSt, Merkblatt „Aufbau der Umsatzsteuer-Identifikationsnummer (USt-IdNr.) in den EU-Mitgliedstaaten“: <https://www.bzst.de/SharedDocs/Downloads/DE/Merkblaetter/ust_idnr_aufbau.pdf?__blob=publicationFile&v=8> (SHA-256 `9f77010c20056dbb4049b836d1b640c65975c9e89c330077fbfbb64ce604fb57`)
- OpenAPI 3.0.1 „eVATR API“, Version v:1.2.3.19.886, Server `/app`, `POST /v1/abfrage`, Schemas `Bestaetigungsabfrage` und `Bestaetigungsantwort`: <https://api.evatr.vies.bzst.de/api-docs>
- Statusmeldungen der eVatR-API: <https://api.evatr.vies.bzst.de/v1/info/statusmeldungen>, Kopie in `steuerbote/vatid/tests/fixtures/statusmeldungen.json`
- Liste der Mitgliedstaaten der eVatR-API: <https://api.evatr.vies.bzst.de/v1/info/eu_mitgliedstaaten>, Kopie in `steuerbote/vatid/tests/fixtures/eu_mitgliedstaaten.json`
- WSDL von VIES, Dokumentation (Zweck, Haftung, Fehlerwerte), `checkVatApprox` und `checkVatApproxResponse`, Adresse des Dienstes: <https://ec.europa.eu/taxation_customs/vies/checkVatService.wsdl>
- ERiC-Dokumentation 44.3.6.0, `Datenarten/ElsterExtern/ZMDO/Jahresdokumentation/Jahresdokumentation_ZMDO_2.ods`, Blatt „ZMDO - Felder“ (Feld `knre_UstIdNr_Erwerber`) und Blatt „ZMDO - Regeln“ (Regel 17004518): <https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Dokumentation.zip>
- ERPNext 16.60.0, `erpnext/setup/doctype/transaction_deletion_record/transaction_deletion_record.py`: `get_doctypes_to_be_ignored()` mit dem Hook `company_data_to_be_ignored`, `generate_to_delete_list()`, die die ausgeschlossenen DocTypes auslässt, und `delete_docs_linked_with_specified_company()` mit `frappe.db.delete`: <https://github.com/frappe/erpnext/blob/v16.60.0/erpnext/setup/doctype/transaction_deletion_record/transaction_deletion_record.py>
- Probe der eVatR-API am 20. November 2026, 15:35 Uhr: `POST /app/v1/abfrage` mit `{"anfragendeUstid":"DE123456789","angefragteUstid":"ATU00000000"}`, Antwort HTTP 400 mit `id`, `anfrageZeitpunkt` und `status` `evatr-0004`.
- Probe der eVatR-API am 20. November 2026, 19:13 Uhr, mit `confirm()` und den Testwerten des OpenAPI-Dokuments (Beschreibung von `/v1/abfrage`): einfache und qualifizierte Abfrage je mit HTTP 200 und `status` `evatr-0000`, die qualifizierte mit `ergFirmenname`, `ergStrasse`, `ergPlz` und `ergOrt` A.
