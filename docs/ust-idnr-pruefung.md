# Prüfung ausländischer USt-IdNrn.

Steuerbote lässt sich die USt-IdNr. eines Geschäftspartners aus einem anderen Mitgliedstaat im Bestätigungsverfahren nach § 18e UStG bestätigen. Diese Seite beschreibt den Kern unter `steuerbote/vatid`: reines Python ohne Frappe-Import, die Abfrage beim Bundeszentralamt für Steuern (BZSt), das Ausweichen auf VIES, die Bedeutung jeder Antwort, den Datensatz, der als Nachweis bleibt, und die Regeln, wann ein Partner bestätigt wird und was eine Ausgangsrechnung braucht. In ERPNext lässt Steuerbote die Nummer eines Kunden oder Lieferanten bestätigen, wenn er angelegt oder geändert wird, auf Knopfdruck und jeden Morgen, wenn die Bestätigung fällig ist, prüft beim Buchen einer Ausgangsrechnung hinter Kz 41, 42 oder 21, ob eine aktuelle Bestätigung vorliegt, und führt eine Arbeitsliste der Partner ohne aktuelle Bestätigung, siehe [In ERPNext](#in-erpnext); Zusammenfassende Meldung und Voranmeldung lesen dieselben Bestätigungen, siehe [In der Umsatzsteuer-Voranmeldung](#in-der-umsatzsteuer-voranmeldung). Die Seite ersetzt keine Steuerberatung und keine Rechtsberatung.

Die Quellen stehen am [Ende der Seite](#quellen), gelesen am 20. November 2026, die für die Voranmeldung am 23. November 2026 und die für die Partner, die Ausgangsrechnung und den Datenschutz am 25. November 2026.

## Das Bestätigungsverfahren

- **Was bestätigt wird.** „Das Bundeszentralamt für Steuern bestätigt auf Anfrage dem Unternehmer im Sinne des § 2 die Gültigkeit einer Umsatzsteuer-Identifikationsnummer sowie den Namen und die Anschrift der Person, der die Umsatzsteuer-Identifikationsnummer von einem anderen Mitgliedstaat erteilt wurde“ (§ 18e Nr. 1 UStG). Eine deutsche USt-IdNr. bestätigt das BZSt auf diesem Weg nicht.
- **Wer fragt.** „Anfragen zur Bestätigung einer ausländischen USt-IdNr. kann jeder Inhaber einer deutschen USt-IdNr. stellen.“ (UStAE 18e.1 Abs. 1). „Bei der Abfrage muss immer die eigene deutsche USt-IdNr. angegeben werden.“ (BZSt, FAQ). Steuerbote fragt deshalb immer mit der USt-IdNr. des Unternehmens, für das es prüft.
- **Woher die Antwort kommt.** „In Deutschland werden keine Daten zu USt-IdNrn. anderer EU-Mitgliedstaaten gespeichert. Das BZSt leitet Bestätigungsanfragen direkt und automatisiert an die Behörden der jeweiligen EU-Mitgliedstaaten weiter.“ (BZSt, Bestätigung ausländischer USt-IdNrn).
- **Für welchen Zeitpunkt.** Eine Bestätigung gilt für den Zeitpunkt der Anfrage: „Bestätigungen für zurückliegende Zeitpunkte oder Zeiträume sind nicht möglich.“ (BZSt, FAQ). War die Unrichtigkeit einer USt-IdNr. erkennbar und wurde sie nicht erkannt, „z. B. weil das Bestätigungsverfahren nicht oder zu einem späteren Zeitpunkt als dem des Umsatzes durchgeführt wird“, genügt das nicht der Sorgfaltspflicht eines ordentlichen Kaufmanns (UStAE 6a.8 Abs. 6 Satz 1). Eine Prüfung erst mit der Zusammenfassenden Meldung kommt also spät; deshalb bestätigt Steuerbote die Nummer schon am Partner und prüft die Ausgangsrechnung beim Buchen.
- **Wann.** Das BZSt bestätigt „rund um die Uhr“; „Im Zeitraum von 23:00 Uhr bis 05:00 Uhr können Wartungsarbeiten durchgeführt werden“. Derzeit dauern Antworten länger als üblich, und das BZSt bittet: „Bitte sehen Sie von einem unmittelbaren Wiederholen der Anfrage ab.“ (BZSt, Bestätigung ausländischer USt-IdNrn). „Es werden nur Einzelabfragen verarbeitet. Diese werden nacheinander abgearbeitet.“ (ebenda, REST-API). Steuerbote stellt deshalb eine Abfrage nach der anderen, wiederholt keine Abfrage sofort und erneuert eine Bestätigung höchstens einmal am Tag, nur zwischen 5 und 23 Uhr, siehe [Die tägliche Erneuerung](#die-tägliche-erneuerung).
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
- **Die anfragende Nummer** ist DE mit neun Ziffern (`is_german()`). Ihre Prüfziffer prüfen schon die Einstellungen beim Speichern (`has_german_check_digit()`, siehe [Architektur](architektur.md)), und das BZSt prüft sie noch einmal (`evatr-0004`). Der Testwert DE123456789 des OpenAPI-Dokuments des BZSt hat nach dem Verfahren unten eine falsche Prüfziffer; die Tests nehmen DE123456788.
- **Eine deutsche Nummer eines Partners** ist DE mit neun Ziffern, deren erste nicht 0 ist und deren letzte die Prüfziffer ist (`german_problem()`, `german_check_digit()`), siehe [Deutsche USt-IdNrn.](#deutsche-ust-idnrn).

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

Eine plausible Nummer, die nicht so aufgebaut ist, bekommt in der Zusammenfassenden Meldung und bei „USt-IdNrn. prüfen“ nur einen Hinweis (`structure_hint()`) und wird trotzdem angefragt. Am Kunden und Lieferanten ist sie dagegen „Fehlerhaft“ und wird nicht gesendet, bis eine Antwort eines Dienstes sie gültig fand: Dann zählt die Antwort, denn das Merkblatt kann strenger sein als der Mitgliedstaat (`kind()` und `standing()` in `steuerbote/vatid/partners.py`). ERiC meldet eine solche Nummer in der Zusammenfassenden Meldung ebenfalls nur als Hinweis (Regel 17004518, „Unschlüssige Umsatzsteuer-Identifikationsnummer“), und das BZSt prüft den Aufbau selbst und antwortet mit `evatr-0005` oder `evatr-0012`. Diese Antwort ist ein Nachweis wie jede andere; eine Sperre in Steuerbote ließe keinen zurück.

Rumänien ist ein Sonderfall: Das Merkblatt nennt höchstens zehn Ziffern, die nicht mit 0 beginnen, während ERiC für die Zusammenfassende Meldung verlangt, eine rumänische USt-IdNr. „mit 2- bis 4-stelligem Ziffernteil“ „durch Angabe führender Nullen auf 5 Stellen“ aufzufüllen (Jahresdokumentation ZMDO 2, Fehlertext zu `knre_UstIdNr_Erwerber`). Eine so aufgefüllte Nummer ist plausibel und bekommt den Hinweis des Merkblatts. Ob das BZSt sie bestätigt, ist offen.

In der Zusammenfassenden Meldung gilt XI nur für Waren. Für Lieferungen gelten nach Artikel 8 des Protokolls zu Irland/Nordirland die Vorschriften für den innergemeinschaftlichen Handel, aber „Für den Dienstleistungsverkehr mit Nordirland gelten die für das Drittlandsgebiet geltenden Vorschriften zur Umsatzsteuer.“ (BZSt, FAQ). Das prüft die Zusammenfassende Meldung, nicht die Bestätigung.

## Was die Frappe-Schicht übergibt und speichert

`steuerbote.vatid.confirm(requested, requester, details, fetch, clock)` gibt eine `Confirmation` zurück, die der letzten Abfrage. Die Frappe-Schicht übergibt:

- `requested`: die USt-IdNr. des Kunden, in jeder Schreibweise, die `normalize` liest. Vorher zeigt `problem()` den Grund, wenn sie nicht plausibel ist, denn `confirm` weist eine solche Nummer mit `ValueError` ab, bevor es etwas sendet; `structure_hint()` liefert den Hinweis zum Aufbau.
- `requester`: die eigene deutsche USt-IdNr. des Unternehmens aus seinen Einstellungen.
- `details`: `Details(name, city, postcode, street)` für die qualifizierte Abfrage, sonst `None`. Name und Ort sind Pflicht.
- `fetch`: der Transport. `UrllibFetch(timeout_seconds=…, opener=…)` nimmt nur HTTPS, die Zertifikate des Systems und die Proxys der Umgebung und folgt keiner Weiterleitung: Eine Antwort mit Status 3xx kommt zurück, wie sie ist, denn sonst stammte der Nachweis womöglich von einem anderen Server oder käme über HTTP. Ein eigener `opener` mit `urllib.request.ProxyHandler` setzt einen Proxy. Ein eigener Transport gibt jede HTTP-Antwort zurück, auch mit Status 4xx und 5xx, und wirft `OSError` nur, wenn keine Antwort kam. Je Prüfung ein eigener `UrllibFetch`, denn er hält die Cookies der Dienste.
- `clock`: eine Uhr mit Zeitzone, etwa `lambda: datetime.now(UTC)`.

Die Frappe-Schicht speichert jeden Datensatz aus `queries()` als eigene, nicht änderbare Bestätigung, die Antwort (`response_text`) als private Datei, und zeigt an einer Zeile der Zusammenfassenden Meldung die letzte Prüfung mit Tag, Dienst, Ergebnis, Status und Nummer der Abfrage, siehe [In ERPNext](#in-erpnext). Prüfungen laufen nacheinander, nicht gleichzeitig, und ohne sofortige Wiederholung; nach `unavailable` fragt die tägliche Erneuerung am nächsten Tag erneut, nach einer Antwort von VIES auch beim BZSt, denn erst dessen qualifizierte Bestätigung zählt für eine sonstige Leistung.

## In ERPNext

Steuerbote lässt die USt-IdNr. eines Geschäftspartners zu der Zeit bestätigen, zu der das Gesetz sie verlangt, also vor dem Umsatz: auf Knopfdruck am Kunden, am Lieferanten und an einer Ausgangsrechnung im Entwurf, wie bisher mit „USt-IdNrn. prüfen“ an Zusammenfassender Meldung und Voranmeldung und, wenn das Unternehmen die [automatische Prüfung](#die-automatische-prüfung) einschaltet, auch von selbst, wenn ein Kunde oder Lieferant angelegt wird oder sich seine USt-IdNr., sein Name oder seine Adresse ändert, und jeden Morgen für jeden Partner, dessen Bestätigung fällig ist. Beim Buchen einer Ausgangsrechnung hinter Kz 41, 42 oder 21 prüft es, ob eine aktuelle Bestätigung vorliegt; diese Prüfung sendet selbst nichts. Jede Abfrage bleibt als [USt-IdNr.-Bestätigung](#die-ust-idnr-bestätigung) erhalten; sie ist der einzige Nachweis, den Steuerbote führt. Die Regeln stehen im Kern `steuerbote/vatid/partners.py` (reines Python, voll getestet), die Frappe-Schicht in `steuerbote/steuerbote/partner_vat_ids.py`.

### Die Nummern eines Partners

ERPNext kennt je Kunde, Lieferant und Unternehmen ein Feld für eine Steuernummer, `tax_id`. Alle Apps, die es lesen, Steuerbote eingeschlossen, nehmen es als USt-IdNr.; die deutsche Übersetzung von ERPNext nennt es aber „Steuernummer“, so dass dort leicht die Steuernummer des Finanzamts landet. „Steuerbote einrichten“ bietet an, das Feld „USt-IdNr.“ zu nennen, siehe [Einrichtung](einrichtung.md#die-schritte). Für die übrigen Nummern legt Steuerbote eigene Felder an Kunde und Lieferant an:

| Feld | Inhalt |
|---|---|
| USt-IdNr. (`tax_id`, von ERPNext) | die USt-IdNr. eines Mitgliedstaats mit Länderkennzeichen, in jeder Schreibweise, die `normalize` liest; Steuerbote ändert das Feld nicht |
| Steuernummer (`steuernummer`) | die Steuernummer, die ein deutsches Finanzamt dem Partner erteilt hat, etwa für eine Gutschrift, in der der Partner der leistende Unternehmer ist (§ 14 Abs. 2 Satz 2 und Abs. 4 Satz 1 Nr. 2 UStG), oder für einen Partner ohne USt-IdNr.; Steuerbote sendet sie nirgendwohin |
| Ausländische Steuernummer (`foreign_tax_id`) | eine Nummer von außerhalb der EU, etwa eine Schweizer UID; weder das BZSt noch VIES bestätigen sie, Steuerbote sendet sie nirgendwohin |
| Stand der USt-IdNr. (`vat_id_status`), USt-IdNr. geprüft am, Letzte USt-IdNr.-Bestätigung | setzt Steuerbote, schreibgeschützt; der Stand steht auch als Filter in der Liste |

Der Stand folgt der Nummer und der neuesten Bestätigung dieser Nummer, gleich für welches Unternehmen:

| Stand | Bedeutung |
|---|---|
| (leer) | keine USt-IdNr. |
| Nicht geprüft | eine USt-IdNr. eines anderen Mitgliedstaats, noch ohne Abfrage |
| Gültig, Ungültig, Keine Antwort | das Ergebnis der neuesten Bestätigung |
| Gültig (einfach) | eine deutsche USt-IdNr., die VIES gültig fand: gültig laut VIES, ohne Namensabgleich, nicht die Bestätigung nach § 18e UStG |
| Deutsche USt-IdNr., nicht geprüft | eine deutsche USt-IdNr. mit richtiger Prüfziffer, noch ohne Abfrage bei VIES, siehe [Deutsche USt-IdNrn.](#deutsche-ust-idnrn) |
| Nicht bestätigbar | ein Länderkennzeichen, das das BZSt nicht bestätigt: GB, GR oder ein Land außerhalb der EU; eine solche Nummer gehört meist in „Ausländische Steuernummer“ |
| Fehlerhaft | ohne Länderkennzeichen, mit einer Länge außerhalb von 7 bis 14 Zeichen, nicht so aufgebaut, wie das Merkblatt des BZSt es für den Mitgliedstaat beschreibt, oder eine deutsche Nummer, die nicht aus DE und neun Ziffern besteht, mit 0 beginnt oder deren Prüfziffer nicht stimmt. Beim Speichern sagt eine Meldung, was nicht stimmt |

Über dem Formular des Partners steht je Unternehmen, das ihn bestätigt, wo seine Bestätigung steht, wie in der [Arbeitsliste](#arbeitsliste), mit dem Tag der letzten Antwort, ob eine Bestätigung in der Warteschlange wartet (solange sie wartet oder läuft, fragt das Formular alle vier Sekunden nach und lädt sich neu, sobald sie fertig ist, auch ohne die Echtzeitverbindung) und für welche Unternehmen die automatische Prüfung ausgeschaltet ist; dort bleibt ein Partner „Nicht geprüft“, bis jemand die Schaltfläche drückt. Unter „Verknüpfungen“ stehen in der Gruppe „Steuer“ alle seine USt-IdNr.-Bestätigungen.

### Wann Steuerbote fragt

| Auslöser | Wann | Für welche Unternehmen |
|---|---|---|
| Partner angelegt oder geändert | ein neuer Kunde oder Lieferant mit USt-IdNr., eine andere USt-IdNr., ein anderer Name, eine andere Hauptadresse, eine neue oder geänderte Adresse (Straße, Postleitzahl, Ort, Land, deaktiviert) | die Unternehmen des Partners, die „Bei Änderung eines Partners bestätigen“ eingeschaltet haben (Vorgabe aus), für Lieferanten nur mit „Lieferanten bestätigen“ |
| „USt-IdNr. bestätigen“ am Kunden oder Lieferanten | auf Knopfdruck, nach einem Dialog, der nennt, was gesendet wird | die Unternehmen des Partners, auch für Lieferanten und unabhängig von den beiden Einstellungen |
| „USt-IdNr. des Kunden bestätigen“ an einer gespeicherten Ausgangsrechnung im Entwurf | auf Knopfdruck, nach demselben Dialog; die Bestätigung nennt die Rechnung | nur das Unternehmen der Rechnung |
| Tägliche Erneuerung | jeden Morgen, siehe [Die tägliche Erneuerung](#die-tägliche-erneuerung) | die Unternehmen, die „Bestätigungen täglich erneuern“ eingeschaltet haben (Vorgabe aus) |
| „USt-IdNrn. prüfen“ | an einer berechneten Zusammenfassenden Meldung oder Voranmeldung im Entwurf, siehe [Zusammenfassende Meldung und Voranmeldung](#zusammenfassende-meldung-und-voranmeldung) | das Unternehmen der Meldung |

Für alle Auslöser gilt:

- **Unternehmen des Partners** sind die Unternehmen, für die am Partner eigene Konten eingetragen sind (Tabelle „Default Accounts“ am Kunden, „Per-Company Accounts“ am Lieferanten, DocType Party Account; ERPNext füllt sie nur, wenn jemand für ein Unternehmen ein abweichendes Debitoren- oder Kreditorenkonto einträgt), und die Unternehmen seiner gebuchten Ausgangsrechnungen, bei einem Lieferanten seiner gebuchten Eingangsrechnungen. Hat ein Partner weder das eine noch das andere, etwa ein neuer Kunde, gilt das Standardunternehmen der Site (Global Defaults, „Standardunternehmen“). Ein neuer Kunde eines anderen Unternehmens wird deshalb erst für dieses bestätigt, wenn er dort eine gebuchte Rechnung oder ein eigenes Konto hat, oder über die Schaltfläche an seiner Rechnung im Entwurf. Ein Unternehmen fragt nur, wenn seine Einstellungen seine eigene USt-IdNr. enthalten: „Anfragen zur Bestätigung einer ausländischen USt-IdNr. kann jeder Inhaber einer deutschen USt-IdNr. stellen.“ (UStAE 18e.1 Abs. 1). Ohne sie fragt Steuerbote für das Unternehmen nichts.
- **Nur eine Nummer, die ein Dienst prüft**, verlässt die Site: eine plausible USt-IdNr. eines anderen Mitgliedstaats mit dem Aufbau des Merkblatts geht an das BZSt (siehe [Aufbau einer USt-IdNr.](#aufbau-einer-ust-idnr)), eine deutsche USt-IdNr. mit richtiger Prüfziffer an VIES, wenn das Unternehmen „Deutsche USt-IdNrn. prüfen“ eingeschaltet hat (siehe [Deutsche USt-IdNrn.](#deutsche-ust-idnrn)). Eine fehlerhafte und eine nicht bestätigbare Nummer bekommen nur ihren Stand.
- **Im Hintergrund.** Jeder Auslöser legt einen Job in die Queue `long`, je Partner höchstens einen; ein zweiter Auslöser, solange er wartet, geht in ihm auf. Das Speichern des Partners oder der Adresse wartet nicht auf die Antwort, die Minuten dauern kann. Je Unternehmen eine Bestätigung, eine Abfrage nach der anderen, jede sofort festgeschrieben. Am Ende setzt der Job den Stand des Partners, und wer ihn ausgelöst hat, bekommt eine Nachricht.
- **Qualifiziert, wo Name und Ort bekannt sind:** der Name des Partners (Kunden- oder Lieferantenname) und die Adresse in seinem Feld für die Hauptadresse (`customer_primary_address`, `supplier_primary_address`), wenn sie aktiv ist; sonst von seinen aktiven verknüpften Adressen die als bevorzugte Rechnungsadresse markierte, dann die zuletzt geänderte; je mit Ort, Postleitzahl und erster Adresszeile. Ohne Name oder Ort fragt Steuerbote einfach.
- **Keine Frage zweimal am Tag.** Hat dasselbe Unternehmen am selben Tag schon eine Antwort zu der Nummer, fragt Steuerbote nicht noch einmal (`covered_today`): Eine Antwort „gültig“ beantwortet die einfache Frage und, wenn sie qualifiziert war, die qualifizierte mit demselben Namen und derselben Anschrift; eine Antwort „ungültig“ beantwortet jede Frage. Eine Abfrage ohne Antwort beantwortet nichts; auf Knopfdruck oder nach einer Änderung fragt Steuerbote dann am selben Tag noch einmal, die tägliche Erneuerung nicht.
- **Wer fragen darf, und immer echt:** Eine Bestätigung schickt Daten an das BZSt oder an VIES. Auslösen darf sie deshalb nur, wer Daten von der Site senden darf, wie bei „USt-IdNrn. prüfen“, Testsenden und Senden (siehe [Schutz der Belege und Rechte](architektur.md#schutz-der-belege-und-rechte)): an einer Ausgangsrechnung, wer sie buchen darf; an einem Kunden oder Lieferanten, wer ihn ändern und eine Umsatzsteuer-Voranmeldung buchen darf (Accounts Manager, System Manager). Speichert jemand ohne dieses Recht einen Partner, fragt Steuerbote nicht; ist die tägliche Erneuerung eingeschaltet, holt sie die Bestätigung nach. Diese Regel steht an einer Stelle (`may_ask` in `partner_vat_ids.py`), durch die jeder Auslöser geht. Der Simulationsmodus von ERiC gilt für die Bestätigung nicht, denn eine simulierte Antwort wäre kein Nachweis: Steuerbote fragt immer echt, und jeder Dialog sagt das. Zu Testsystemen siehe [Testsysteme](#testsysteme).

### Die automatische Prüfung

„Bei Änderung eines Partners bestätigen“ und „Bestätigungen täglich erneuern“ sind ausgeschaltet, für neue Installationen wie nach einem Update: Steuerbote sendet keine Daten von Partnern, nur weil die App installiert oder aktualisiert wurde. Bis ein Unternehmen sie einschaltet, fragt Steuerbote nur auf Knopfdruck, und ein Partner bleibt „Nicht geprüft“, bis jemand die Schaltfläche am Partner oder an einer Rechnung drückt; das Formular des Partners und die Arbeitsliste sagen, dass die automatische Prüfung aus ist. Der Schritt „Automatische USt-IdNr.-Prüfung“ von „Steuerbote einrichten“ erklärt, was sie tut und was an wen geht, und schaltet beide für das Unternehmen mit einer Aktion ein, die nur ein System Manager ausführt; ebenso lassen sie sich in den Einstellungen schalten. „Lieferanten bestätigen“ ist eingeschaltet und wirkt, sobald die automatische Prüfung läuft. Die Prüfung der Ausgangsrechnung beim Buchen gilt unabhängig davon, denn sie sendet nichts.

### Die tägliche Erneuerung

Ein Job des Schedulers (`scheduler_events`, Cron `30 6 * * *` in der Zeitzone der Site) erneuert jeden Morgen die Bestätigungen, die fällig sind. Die Regeln (`is_due`, `renewal_order` und `renew` in `steuerbote/vatid/partners.py`):

1. **Welche Partner:** je Unternehmen mit eigener USt-IdNr. und „Bestätigungen täglich erneuern“ die aktiven Kunden und, mit „Lieferanten bestätigen“, die aktiven Lieferanten, mit denen es zu tun hat (siehe oben), je Nummer einmal, auch wenn mehrere Partner sie tragen.
2. **Fällig** ist eine USt-IdNr., die das BZSt bestätigt, nach der das Unternehmen heute noch nicht gefragt hat, und die noch keine Antwort hat, deren letzte Antwort, ob gültig oder ungültig, so alt ist wie „Höchstalter der USt-IdNr.-Bestätigung (Tage)“ oder älter, oder die nur einfach bestätigt ist, obwohl Name und Ort inzwischen bekannt sind. Nach einer ungültigen Nummer fragt Steuerbote also nicht häufiger als nach einer gültigen.
3. **Reihenfolge:** die Nummern ohne Antwort zuerst, dann die älteste Antwort zuerst.
4. **Eine nach der anderen**, mit zwei Sekunden Pause dazwischen, höchstens 25 Nummern am Tag über alle Unternehmen; der Rest folgt an den nächsten Tagen.
5. **Nur zu den Zeiten der Dienste:** vor jeder Abfrage zwischen 5 und 23 Uhr deutscher Zeit, sonst endet der Lauf.
6. **Halt beim ersten Ausfall:** Konnte das BZSt die einfache Abfrage einer Nummer nicht beantworten, bleibt diese Bestätigung erhalten, auch mit einer Antwort von VIES, und der Lauf endet; er setzt am nächsten Tag fort. Keine Nummer wird am selben Tag wiederholt.
7. **Kein Abbruch an einer Nummer:** Eine fehlerhafte oder nicht bestätigbare Nummer bekommt ihren Stand, ohne dass gefragt wird. Scheitert eine Bestätigung an etwas anderem, etwa weil der Partner inzwischen gelöscht ist, steht der Fehler im Fehlerprotokoll und der Lauf geht weiter.
8. **Aus, bis ein Unternehmen seine USt-IdNr. hat:** Ohne eigene USt-IdNr. in den Einstellungen erneuert Steuerbote für ein Unternehmen nichts.

Damit hält sich die Erneuerung an die Bedingungen beider Dienste. Das BZSt: „Es werden nur Einzelabfragen verarbeitet. Diese werden nacheinander abgearbeitet.“, „Bitte sehen Sie von einem unmittelbaren Wiederholen der Anfrage ab.“, bei einer Zeitüberschreitung möge man es „zu einer anderen Tageszeit“ versuchen, und „Im Zeitraum von 23:00 Uhr bis 05:00 Uhr können Wartungsarbeiten durchgeführt werden“ (BZSt, Bestätigung ausländischer USt-IdNrn); die REST-API richtet sich „insbesondere an Unternehmen mit vielen Bestätigungsanfragen“ (ebenda). VIES, das nur antwortet, wenn das BZSt es nicht kann, nennt als Missbrauch „Multiple validation of the same VAT number per day except for availability tests“ und „High traffic of invalid VAT numbers“ und sperrt dann die IP-Adresse des Absenders (VIES, FAQ).

### Die Ausgangsrechnung

Beim Buchen einer Ausgangsrechnung (`before_submit`) prüft Steuerbote die USt-IdNr. des Kunden, wenn die Rechnung in Kz 41, 42 oder 21 eingeht. Gutschriften (Rückgaben) und Eröffnungsrechnungen prüft es nicht.

**Woher die Kennzahl kommt.** Die Buchungen gibt es beim Buchen noch nicht. Steuerbote nimmt deshalb die Erlöskonten der Artikel der Rechnung und die Zuordnungen der Kontenzuordnung Umsatzsteuer ihres Unternehmens, mit „Kennzahl“ und „Auch Kennzahl“: dieselben Regeln, nach denen die Voranmeldung die Buchungen dieser Konten später in Kz 41, 42 oder 21 meldet. Steuervorlage und Steuerkategorie liest Steuerbote dafür nicht, denn die Voranmeldung liest sie auch nicht; eine Vorlage, die zu einem anderen Konto passt, als gebucht wird, änderte an der Meldung nichts. Eine Rechnung ohne ein solches Konto braucht keine Bestätigung, ebenso eine Rechnung eines Unternehmens ohne Kontenzuordnung oder ohne eigene USt-IdNr.

**Welche Nummer.** Die USt-IdNr. an der Rechnung (`tax_id`, die ERPNext vom Kunden holt), ohne sie die des Kunden.

**Was aktuell heißt.** Die letzte Antwort des Unternehmens zu der Nummer, gleich wodurch ausgelöst, ist gültig und höchstens so viele Tage alt, wie die Einstellungen zulassen, gezählt bis zum Buchungsdatum der Rechnung; eine Antwort nach dem Buchungsdatum zählt als null Tage alt, belegt dann aber nicht mehr die Zeit des Umsatzes (UStAE 6a.8 Abs. 6 Satz 1).

- **Lieferungen (Kz 41, 42):** eine gültige Bestätigung, höchstens „Höchstalter für Lieferungen (Tage)“ alt, Vorgabe 0: eine Bestätigung vom Tag der Rechnung. Die Gültigkeit zur Zeit der Lieferung ist Voraussetzung der Steuerbefreiung (§ 6a Abs. 1 Satz 1 Nr. 4 UStG, UStAE 6a.1 Abs. 12 Satz 3), und eine spätere Bestätigung genügt der Sorgfalt nicht (UStAE 6a.8 Abs. 6 Satz 1).
- **Sonstige Leistungen (Kz 21):** eine gültige qualifizierte Bestätigung des BZSt, höchstens „Höchstalter der USt-IdNr.-Bestätigung (Tage)“ alt, Vorgabe 90 (UStAE 3a.2 Abs. 9 Satz 5). Die Nummer soll vor der Leistung verwendet und im Auftrag festgehalten sein; bei einem neuen Kunden genügt seine Erklärung in den Stammdaten, die Nummer für alle künftigen Aufträge zu verwenden (UStAE 3a.2 Abs. 10).
- **Beides an einer Rechnung:** erst die Regel der Lieferungen, dann die qualifizierte Bestätigung.

Was fehlen kann: keine USt-IdNr., eine deutsche, eine nicht bestätigbare oder fehlerhafte, keine Bestätigung, keine Antwort, eine ungültige, eine zu alte oder, für Kz 21, eine ohne Name und Anschrift. Die Meldung nennt Nummer, Kunde, Kennzahlen und gegebenenfalls Tag und Alter der Antwort.

**Sperren, Warnen, Aus.** „Rechnungen über Lieferungen (Kz 41, 42)“ steht auf Sperren, „Rechnungen über sonstige Leistungen (Kz 21)“ auf Warnen, auch wenn die automatische Prüfung aus ist. Fehlt die USt-IdNr., ist sie deutsch, nicht bestätigbar, fehlerhaft oder ungültig, nennt die Meldung denselben Satz zu den Folgen wie die Voranmeldung und die Zusammenfassende Meldung (`steuerbote/vatid/exemption.py`), etwa für Kz 41 den Verlust der Steuerfreiheit nach § 6a Abs. 1 Satz 1 Nr. 4 UStG. Sperren lehnt das Buchen ab und sagt, was als Nächstes zu tun ist:

- **Fehlt die Bestätigung, ist sie zu alt, nicht qualifiziert, ohne Antwort oder fand sie die Nummer ungültig:** „USt-IdNr. des Kunden bestätigen“ an der Rechnung oder „USt-IdNr. bestätigen“ am Kunden drücken, die Nachricht abwarten, dass die Bestätigung abgeschlossen ist, und erneut buchen. Eine Bestätigung vom selben Tag genügt dann ohne weiteren Schritt: Das Alter zählt in Kalendertagen vom Tag der Abfrage bis zum Buchungsdatum der Rechnung, beide in der Zeitzone der Site (die Bestätigung hält ihren Zeitpunkt in dieser Zeitzone fest). Liegt eine Bestätigung vom Tag des Umsatzes außerhalb von Steuerbote vor, gibt eine schriftliche Begründung im Feld „Begründung der Freigabe der USt-IdNr.“ die Nummer für diese Rechnung frei, wie eine Freigabe die Zeile der Zusammenfassenden Meldung freigibt; Steuerbote bucht die Rechnung dann, nennt den Befund, und die Begründung bleibt an der Rechnung.
- **Fehlt die USt-IdNr. oder ist sie deutsch, nicht bestätigbar oder fehlerhaft:** Keine Begründung gibt sie frei, wie an der Zusammenfassenden Meldung. Die USt-IdNr. ist am Kunden und an der Rechnung zu berichtigen, oder die Rechnung gehört auf ein Erlöskonto, das die Kontenzuordnung nicht Kz 41, 42 oder 21 zuordnet.

Warnen bucht und nennt den Befund. Aus prüft nicht.

**Was die Rechnung behält.** Im Feld „USt-IdNr.-Bestätigung“ die Bestätigung, gegen die Steuerbote sie geprüft hat: die der letzten Antwort, ohne sie die der letzten Abfrage. Kein Feld der Rechnung ändert sich nach dem Buchen.

Beim Buchen fragt Steuerbote nie selbst das BZSt: Eine Antwort kann Minuten dauern. „USt-IdNr. des Kunden bestätigen“ an der Rechnung im Entwurf fragt im Hintergrund; danach lässt sie sich buchen.

### Zusammenfassende Meldung und Voranmeldung

„USt-IdNrn. prüfen“ an einer berechneten Zusammenfassenden Meldung oder Voranmeldung im Entwurf fragt nach jeder USt-IdNr., die eine Zeile meldet oder die ein Kunde hinter Kz 41, 42 oder 21 des Zeitraums hat, jede Nummer einmal, als Hintergrundjob in der Queue `long`; Einzelheiten unter [In der Umsatzsteuer-Voranmeldung](#in-der-umsatzsteuer-voranmeldung) und [Zusammenfassende Meldung](zm.md#berechnen). Seit Steuerbote die Partner selbst bestätigen lässt, gilt dabei:

1. Eine Nummer, die das Unternehmen heute schon beantwortet bekommen hat, gleich durch welchen Auslöser, fragt Steuerbote nicht noch einmal, nach der Regel [Keine Frage zweimal am Tag](#wann-steuerbote-fragt). Sind alle Nummern so beantwortet, bietet das Formular die Schaltfläche nicht an.
2. Der Dialog nennt, was gesendet wird: die eigene USt-IdNr. des Unternehmens, jede USt-IdNr., nach der gefragt wird, und, wo bekannt, Name, Straße, Postleitzahl und Ort jedes Kunden, an das BZSt, nur ersatzweise an VIES.
3. Jede Bestätigung nennt den Kunden des ersten Belegs der Nummer und als Auslöser die Meldung; der Stand des Kunden folgt ihr.
4. Wie bisher lesen „Berechnen“ und die Hinweise die letzte Bestätigung jeder Nummer des Unternehmens, gleich wodurch sie ausgelöst wurde, also auch die der Partner und der täglichen Erneuerung.
5. Starten darf sie nur, wer die Meldung buchen darf (Accounts Manager, System Manager), und sie fragt immer echt, auch wenn ERiC als Simulation läuft; der Dialog sagt das.
6. Anfragende Nummer ist die USt-IdNr. aus den Einstellungen des Unternehmens; ohne sie beginnt keine Prüfung. Name und Ort für die qualifizierte Abfrage kommen aus dem Kunden des ersten Belegs der Nummer wie oben. `confirm()` fragt mit einem eigenen `UrllibFetch`, der bis zu 60 Sekunden auf jede Antwort wartet.

Am Ende zeigt jede Zeile der Zusammenfassenden Meldung die letzte Prüfung ihrer Nummer: Tag, Dienst, Ergebnis, Code und Nummer der Abfrage, mit einem Link auf die Bestätigung. Prüfungen der App erpnext_germany (VAT ID Check) zählen nicht, siehe [Zusammenarbeit mit erpnext_germany](#zusammenarbeit-mit-erpnext_germany).

**Was die Meldung daraus macht.** Mit „gültig“ ist die Nummer bestätigt. „Ungültig“ sperrt die Zeile (`ZM-USTID-UNGUELTIG`), „unbekannt“ und eine Nummer ohne Bestätigung sperren sie ebenso (`ZM-USTID-UNBESTAETIGT`). Eine Antwort gilt für den Zeitpunkt der Abfrage: Meldet das BZSt eine Nummer als dann nicht gültig, aber gültig durch alle Monate der Meldung, mit `gueltigAb` und `gueltigBis` (`evatr-2006`) oder ab `gueltigAb` (`evatr-2002`), zählt sie für diese Meldung als bestätigt. Die Befunde nennen den Tag der Abfrage, auf der sie beruhen, etwa „Die USt-IdNr. FR12345678901 ist laut Bestätigungsabfrage vom 20. November 2026 ungültig.“; jede Zeile zeigt ihn ohnehin unter „Geprüft am“. Eine Freigabe der USt-IdNr. mit Begründung („Begründung der Freigabe der USt-IdNr.“) hebt die Sperre auf, ohne den Betrag zu ändern, etwa wenn eine Bestätigung vom Tag der Lieferung außerhalb von Steuerbote vorliegt; eine Korrektur des Betrags mit Begründung hebt sie ebenso auf (Entscheidung des Maintainers). Eine bestätigte Nummer, deren letzte Bestätigung mehr Tage vor dem Ende der Monate der Meldung liegt, als die Einstellungen zulassen („Höchstalter der USt-IdNr.-Bestätigung“, wie an der Voranmeldung), bekommt den Hinweis `ZM-USTID-VERALTET`. Eine Zeile ohne Bestätigung zeigt in „Ergebnis der Prüfung“ „Nicht bestätigt“. Prüfungen der App erpnext_germany (VAT ID Check) zählen hier nicht: Wer dort „gültig“ sieht, lässt die Nummer mit „USt-IdNrn. prüfen“ bestätigen. Das Ergebnis einer Prüfung ist das ihrer letzten Abfrage, die eines hat: Scheitert die qualifizierte Abfrage, nachdem das BZSt die Nummer bestätigt hat, bleibt sie bestätigt; antwortet VIES, weil das BZSt nicht konnte, zählt die Antwort von VIES.

### Arbeitsliste

Der Bericht „Partner ohne aktuelle USt-IdNr-Bestätigung“ (in der Seitenleiste „Offene USt-IdNrn.“, im Arbeitsbereich „Steuern“ unter „Zusammenfassende Meldung“) listet je Unternehmen jeden Kunden und Lieferanten, mit dem es zu tun hat und dessen USt-IdNr. keine aktuelle Bestätigung hat; ein Filter wählt Kunden oder Lieferanten. Partner ohne USt-IdNr. stehen nicht darauf, Partner mit deutscher USt-IdNr. nur, wenn das Unternehmen deutsche USt-IdNrn. prüft. Der Name des Berichts schreibt „USt-IdNr“ ohne Punkt, weil Frappe aus dem Namen eines Berichts den Pfad seines Python-Moduls bildet.

| Stand | Bedeutung |
|---|---|
| Fehlt | noch keine Bestätigung |
| Deutsche USt-IdNr., nicht geprüft | eine deutsche USt-IdNr., noch ohne Abfrage bei VIES |
| Abgelaufen | die letzte Antwort ist gültig, aber älter als „Höchstalter der USt-IdNr.-Bestätigung (Tage)“ |
| Ungültig | die letzte Antwort fand die Nummer ungültig |
| Keine Antwort | Abfragen gab es, beantwortet wurde keine |
| Nicht bestätigbar, Fehlerhaft | wie am Stand des Partners, mit dem Grund |
| Adresse fehlt | gültig, aber nur einfach bestätigt, weil dem Partner Name oder Ort fehlt |
| Nicht qualifiziert | gültig, aber nur einfach bestätigt, obwohl Name und Ort inzwischen bekannt sind; die tägliche Erneuerung fragt qualifiziert nach |
| Angaben weichen ab | gültig und qualifiziert, aber der Mitgliedstaat hat einen anderen Namen oder eine andere Anschrift registriert (Ergebnis B) |

Jede Zeile nennt dazu den Tag und das Alter der letzten Antwort, ihr Ergebnis und die Bestätigung. Ein Unternehmen ohne eigene USt-IdNr. bekommt eine leere Liste und den Hinweis, dass Steuerbote für es nichts bestätigt.

### Einstellungen

In den Einstellungen Umsatzsteuer-Voranmeldung jedes Unternehmens, Abschnitt „USt-IdNr.-Prüfung“; das Höchstalter steht wie bisher unter „Steuernummer und Finanzamt“. Keine Quelle nennt eine Zahl von Tagen. Die Vorgaben folgen der Ausarbeitung für die Einführung; **die Höchstalter sind mit der Steuerberatung abzustimmen**, siehe [Prüfliste](pruefliste-steuerberatung.md#ust-idnrn-der-geschäftspartner).

| Einstellung | Vorgabe | Wirkung |
|---|---|---|
| USt-IdNr. (`ust_idnr`) | die Steuernummer des Unternehmens, wenn sie eine deutsche USt-IdNr. ist | anfragende Nummer; ohne sie fragt Steuerbote für das Unternehmen nichts |
| Höchstalter der USt-IdNr.-Bestätigung (Tage) (`max_confirmation_age`) | 90 | Hinweise der Voranmeldung, Rechnungen hinter Kz 21 und Takt der täglichen Erneuerung; 90 Tage sind etwa ein Kalendervierteljahr, der Voranmeldungszeitraum des § 18 Abs. 2 Satz 1 UStG |
| Bei Änderung eines Partners bestätigen (`vat_id_check_on_change`) | aus | Bestätigung, wenn ein Partner angelegt wird oder sich USt-IdNr., Name oder Adresse ändern |
| Bestätigungen täglich erneuern (`vat_id_renewal`) | aus | [Die tägliche Erneuerung](#die-tägliche-erneuerung) |
| Deutsche USt-IdNrn. prüfen (`vat_id_check_german`) | an | deutsche USt-IdNrn. bei VIES einfach prüfen lassen, siehe [Deutsche USt-IdNrn.](#deutsche-ust-idnrn); wirkt mit der automatischen Prüfung und auf die Schaltflächen |
| Lieferanten bestätigen (`vat_id_check_suppliers`) | an | wirkt erst, wenn die automatische Prüfung eingeschaltet ist: auch Lieferanten aus anderen Mitgliedstaaten; das Gesetz verlangt die Bestätigung nur für Kunden, für Lieferanten ist sie eine Prüfung der Stammdaten (ein Vorsteuerabzug nach § 15 Abs. 1 Satz 1 Nr. 3 und 4 UStG setzt die USt-IdNr. des Lieferanten nicht voraus) |
| Rechnungen über Lieferungen (Kz 41, 42) (`vat_id_invoice_goods`) | Sperren | Sperren, Warnen oder Aus beim Buchen |
| Höchstalter für Lieferungen (Tage) (`vat_id_goods_max_age`) | 0 | eine Bestätigung vom Tag der Rechnung |
| Rechnungen über sonstige Leistungen (Kz 21) (`vat_id_invoice_services`) | Warnen | Sperren, Warnen oder Aus beim Buchen |

### Deutsche USt-IdNrn.

Viele Partner eines deutschen Unternehmens haben eine deutsche USt-IdNr. Eine falsche oder erfundene Nummer in den Stammdaten fällt sonst niemandem auf, und die E-Rechnung trägt sie als USt-IdNr. des Käufers (BT-48, „Buyer VAT identifier“, EN 16931, siehe Quellen). Steuerbote prüft deutsche Nummern deshalb in zwei Stufen.

**Ohne Abfrage: Aufbau und Prüfziffer.** Eine deutsche USt-IdNr. ist DE mit neun Ziffern; die erste ist nicht 0, die neunte ist die Prüfziffer der ersten acht. Das Verfahren: P = 10; für jede der ersten acht Ziffern M = (Ziffer + P) modulo 10, 10 wo das 0 ergibt, und P = 2 · M modulo 11; R = 11 − P, und die Prüfziffer ist 0, wo R 10 ist, sonst R (`german_check_digit()` in `steuerbote/vatid/ustid.py`); das ist das hybride Prüfziffernsystem ISO/IEC 7064 MOD 11,10. ERiC hält die neunte Ziffer ebenso für eine Prüfziffer („Die letzte der neun Ziffern ist eine Prüfziffer.“, ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 6.3.5), und das Verfahren gibt dieselbe Antwort wie die Prüfung `EricPruefeWIdNr` von ERiC; dieselbe Funktion prüft die eigene USt-IdNr. und die W-IdNr. in den Einstellungen. Die Regel, dass die erste Ziffer nicht 0 ist, gilt nur für die Nummer eines Partners, denn ERiC nimmt eine W-IdNr. wie DE000000003. Das BZSt und das BMF veröffentlichen das Verfahren nicht selbst; das österreichische BMF veröffentlicht es in seinen Konstruktionsregeln der UID, mit dem Hinweis: „Folgende Konstruktionsregeln wurden vom jeweiligen Mitgliedstaat aufgrund bilateraler Vereinbarungen zur Veröffentlichung freigegeben.“, und dem Beispiel 111111125 (siehe Quellen). Das BZSt nennt eine Nummer, die nicht in das Schema passt, „syntaktisch falsch“ (`evatr-0004`, `evatr-0012`). Eine Nummer, deren Prüfziffer nicht stimmt, ist am Partner sofort „Fehlerhaft“, beim Speichern sagt eine Meldung, welche letzte Ziffer das Verfahren ergäbe, und Steuerbote sendet sie nirgendwohin. Die Prüfung läuft immer, ohne Einstellung. Der Testwert DE123456789 des OpenAPI-Dokuments des BZSt besteht sie nicht.

**Mit Abfrage: VIES, einfach.** Das BZSt bestätigt keine deutsche USt-IdNr.: § 18e Nr. 1 UStG nennt nur Nummern, die „von einem anderen Mitgliedstaat erteilt“ wurden, das BZSt antwortet auf die Frage, ob ein deutsches Unternehmen deutsche USt-IdNrn. abfragen kann: „Nein, grundsätzlich können nur USt-IdNr. von Unternehmen in anderen EU-Mitgliedsstaaten abgefragt werden.“ (BZSt, FAQ), und seine Schnittstelle meldet „Die anfragende DE USt-IdNr. ist nicht berechtigt eine DE USt-IdNr. anzufragen.“ (`evatr-0006`). VIES prüft Nummern aller Mitgliedstaaten, auch deutsche. Hat das Unternehmen „Deutsche USt-IdNrn. prüfen“ eingeschaltet (Vorgabe an), fragt Steuerbote VIES nach einer deutschen Nummer mit richtiger Prüfziffer, wenn die automatische Prüfung eingeschaltet ist, und auf Knopfdruck am Partner: `checkVatApprox` mit der Nummer und der eigenen USt-IdNr. als Anfragender, ohne Name und Anschrift (`vies.query`, `service.confirm`). Es gelten dieselben Regeln wie für alle Abfragen: eine nach der anderen, keine Nummer zweimal am Tag, Halt beim ersten Ausfall, dasselbe Höchstalter. Die Antwort bleibt als USt-IdNr.-Bestätigung mit Dienst VIES und der Antwort als Datei.

**Was die Antwort belegt, und was nicht.** Gültig heißt „gültig laut VIES, ohne Namensabgleich“; der Partner zeigt „Gültig (einfach)“. Die Antwort sagt, dass die Nummer zur Zeit der Abfrage erteilt und gültig war; mit der eigenen USt-IdNr. als Anfragender trägt sie nach der Hilfe von VIES eine Nummer der Abfrage, mit der sich belegen lässt, „that you have checked a given VAT number at a given time, and obtained a given validation reply“ (VIES, FAQ). Sie sagt nichts darüber, wem die Nummer gehört: Steuerbote fragt nicht nach Name und Anschrift. Sie ist nicht die Bestätigung nach § 18e UStG, die es für deutsche Nummern nicht gibt, und nicht der Nachweis, den UStAE 18e.1 Abs. 2 meint. Die Prüfung der Ausgangsrechnung ändert sich nicht: Ein deutscher Kunde steht nicht hinter Kz 41, 42 oder 21.

**Warum es sich trotzdem lohnt.** Der Empfänger einer Rechnung hat ihre Angaben „auf ihre Vollständigkeit und Richtigkeit zu überprüfen“, wobei „der Grundsatz der Verhältnismäßigkeit zu wahren“ ist; die Richtigkeit der inländischen USt-IdNr. zu prüfen, ist ihm nach UStAE 15.2a Abs. 6 „regelmäßig nicht möglich“, und eine nicht erkennbar falsche Nummer kostet den Vorsteuerabzug nicht. VIES macht diese Prüfung möglich. § 25f UStG versagt Vorsteuerabzug und Steuerbefreiung, wenn der Unternehmer wusste oder hätte wissen müssen, dass er in eine Steuerhinterziehung einbezogen ist; nach UStAE 25f.1 Abs. 4 darf darauf vertrauen, wer „alle Maßnahmen getroffen hat, die vernünftigerweise von ihm verlangt werden können“. Die Prüfung der USt-IdNr. nennt UStAE 25f.1 dabei nicht ausdrücklich; sie ist eine der Maßnahmen, die ein Unternehmen ohne Aufwand ergreifen und dokumentieren kann, und sie findet falsche Stammdaten, bevor sie auf Rechnungen und E-Rechnungen stehen.

**Offen.** Ob VIES einem deutschen Anfragenden zu einer deutschen Nummer eine Nummer der Abfrage gibt, und ob es Name und Anschrift einer deutschen Nummer anzeigt, sagen die Unterlagen von VIES nicht; eine Antwort mit einem Fehler wie `INVALID_REQUESTER_INFO` bleibt als Bestätigung mit unbekanntem Ergebnis erhalten. VIES nennt als Zweck die Prüfung im innergemeinschaftlichen Handel (Haftungsausschluss nach Art. 31 der Verordnung (EU) Nr. 904/2010); ob die Prüfung deutscher Partner darunter fällt, klärt das Unternehmen mit seiner Steuerberatung, siehe [Prüfliste](pruefliste-steuerberatung.md#ust-idnrn-der-geschäftspartner).

### Zusammenarbeit mit erpnext_germany

Steuerbote braucht die App erpnext_germany nicht und liest nichts von ihr. Ist sie installiert, prüft ihr Job `erpnext_germany.tasks.all` (Version 16.2.2, `tasks.py`) bei jedem Lauf des Schedulers, also alle paar Minuten, bis zu vier Kunden und vier Lieferanten, die aktiv sind, eine USt-IdNr. haben und in den letzten drei Monaten keine abgeschlossene Prüfung, bei VIES, immer mit der USt-IdNr. des Standardunternehmens als Anfragender, und hält die Ergebnisse im DocType „VAT ID Check“ fest. Steuerbote liest diese Ergebnisse nicht als Nachweis, denn sie fragen nicht beim BZSt und nicht mit der USt-IdNr. des Unternehmens, für das der Umsatz gilt (Entscheidung des Maintainers). „Steuerbote einrichten“ erklärt das im Schritt „USt-IdNr.-Prüfung von erpnext_germany“ und bietet an, den Job anzuhalten: Die Aktion setzt „Angehalten“ (`stopped`) an seinem Scheduled Job Type; `bench migrate` aktualisiert bei einem Update nur Häufigkeit und Cron eines bestehenden Jobs und lässt dieses Feld stehen. Die Datensätze „VAT ID Check“ bleiben, wie sie sind, und die App bleibt für ihre übrigen Funktionen installiert. Wer den Job weiterlaufen lässt, hat zwei Listen mit verschiedener Bedeutung; der Nachweis nach UStAE 18e.1 Abs. 2 ist nur die USt-IdNr.-Bestätigung.

### Nach einem Update

`bench migrate` bringt die neuen Felder der Partner, der Ausgangsrechnung, der USt-IdNr.-Bestätigung und der Einstellungen mit ihren Vorgaben, und jeder Partner mit USt-IdNr. bekommt einmal seinen Stand, ohne dass gefragt wird (`fill_statuses`, `after_migrate`). Danach gilt die Prüfung der Ausgangsrechnung für jedes Unternehmen mit eigener USt-IdNr. und Kontenzuordnung: Sperren für Rechnungen über Lieferungen ohne Bestätigung vom Tag, Warnen für sonstige Leistungen. Von selbst gesendet wird nichts, bis ein Unternehmen die automatische Prüfung einschaltet. Nicht von selbst geschehen auch die neue Beschriftung von `tax_id` und das Anhalten des Jobs von erpnext_germany; alle drei bietet „Steuerbote einrichten“ an. Bestehende USt-IdNr.-Bestätigungen bleiben unverändert und nennen keinen Partner; sie zählen weiter für ihre Nummer und ihr Unternehmen.

Vor dem Update oder gleich danach:

1. Die Einstellungen der USt-IdNr.-Prüfung mit der Steuerberatung abstimmen und, wo nötig, ändern.
2. An Kunden und Lieferanten aus anderen Mitgliedstaaten eine Hauptadresse mit Ort pflegen, damit Steuerbote qualifiziert fragt.
3. Steuernummern deutscher Partner und Nummern von außerhalb der EU aus `tax_id` in „Steuernummer“ und „Ausländische Steuernummer“ umtragen; die Arbeitsliste zeigt sie als nicht bestätigbar oder fehlerhaft.
4. „Steuerbote einrichten“ ausführen und die drei neuen Schritte entscheiden, darunter, ob die automatische Prüfung eingeschaltet wird; die erste Erneuerung danach arbeitet die Partner ohne Bestätigung ab, 25 am Tag.
5. Datenschutzhinweise und Verarbeitungsverzeichnis ergänzen, siehe [Datenschutz](#datenschutz).

### Testsysteme

Auf einem Testsystem bleibt die automatische Prüfung aus, wie es die Vorgabe ist. Solange irgendeine automatische Prüfung von USt-IdNrn. läuft, die von Steuerbote oder der Job einer anderen App wie erpnext_germany, steht an keinem aktiven Kunden oder Lieferanten eine erfundene USt-IdNr.: Sie ginge mit der echten USt-IdNr. des Unternehmens als Anfragender an das BZSt oder an VIES. Für Tests mit erfundenen Nummern dient ein Unternehmen ohne eigene USt-IdNr. in den Einstellungen oder ein Partner, der danach deaktiviert wird. Auf einem Testsystem mit einer Kopie der echten Stammdaten lässt sich die Prüfung dagegen gezielt testen, auch für deutsche Nummern: Dort sind die Nummern echt, und die Antworten zeigen, welche Stammdaten falsch sind; jede Abfrage geht dann wirklich an das BZSt oder an VIES.

### Die USt-IdNr.-Bestätigung

Die USt-IdNr.-Bestätigung (`VAT ID Confirmation`) speichert je Abfrage:

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
| Zusammenfassende Meldung, Umsatzsteuer-Voranmeldung, Ausgangsrechnung, Benutzer | woher die Prüfung kam und wer sie gestartet hat |
| Partnertyp, Partner, Ausgelöst durch | der Kunde oder Lieferant, nach dessen Nummer gefragt wurde, und was die Prüfung ausgelöst hat: Manuell, Partner geändert, Rechnung, Erneuerung, Voranmeldung oder Zusammenfassende Meldung; leer bei Bestätigungen von vor dieser Version |
| Antwort (Nachweis) | die Antwort, wie sie kam, als private Datei: JSON vom BZSt, SOAP von VIES |

Name und Anschrift, Code und Nummer der Abfrage stehen in Feldern ohne die Grenze von 140 Zeichen, die ein Datenfeld von Frappe hat, an der Bestätigung wie an den Zeilen der Zusammenfassenden Meldung, die Code und Nummer zeigen: Eine Adresszeile in ERPNext hält 240 Zeichen, und ein Dienst kann längere Werte senden. Gekürzt wird nichts, denn ein zu langer Wert ließe sonst das Speichern scheitern, und mit ihm ginge der Nachweis aller Abfragen der Nummer verloren.

Nur Steuerbote legt eine Bestätigung an, keine Anfrage und kein Benutzer, auch nicht der Administrator über die REST-API oder einen Import, siehe [Schutz der Belege und Rechte](architektur.md#schutz-der-belege-und-rechte). Über den Beleg ändert oder löscht sie niemand, auch kein System Manager, und ihre Antwort ebenso wenig: Steuerbote lehnt jede Änderung und jedes Löschen der Bestätigung ab, und für die Datei ihrer Antwort, sie von der Bestätigung zu lösen oder an einen anderen Beleg oder ein anderes Feld zu hängen, sie öffentlich zu machen, sie auf eine andere Datei zu richten, sie umzubenennen und sie zu löschen (`steuerbote/steuerbote/record_files.py`, eingehängt als `doc_events` für File). Das gilt auch für den Benutzer, dessen Abfrage die Datei abgelegt hat und dem sie deshalb gehört, und geprüft wird gegen die gespeicherte Datei, nicht gegen das, was eine Anfrage schickt, sodass sich die Antwort auch nicht erst lösen und dann löschen oder veröffentlichen lässt. Eine eigene Datei mit demselben Inhalt teilt sich mit der Antwort die Datei auf dem Server und lässt sich deshalb ebenso wenig öffentlich machen. „Transaktionen löschen“ am Unternehmen in ERPNext löscht dagegen mit `frappe.db.delete` direkt in der Datenbank, an diesen Prüfungen vorbei, und zwar die Belege jedes DocTypes mit einem Link auf das Unternehmen, der nicht unter „Ausgeschlossene DocTypes“ des Datensatzes zur Transaktionslöschung steht. Steuerbote nennt die USt-IdNr.-Bestätigung, die Zusammenfassende Meldung, die Dauerfristverlängerung, die Umsatzsteuer-Voranmeldung und die ELSTER-Übermittlung deshalb im Hook `company_data_to_be_ignored`, aus dem ERPNext diese Liste vorbelegt, und sie kommen nicht in die Liste „Zu löschende DocTypes“ (ERPNext 16.60.0, siehe Quellen). Wer sie dort von Hand einträgt oder aus den ausgeschlossenen herausnimmt, löscht sie trotzdem; das verhindert Steuerbote nicht, so wenig wie einen Eingriff direkt in die Datenbank. Lesen dürfen sie die Rollen Accounts User, Accounts Manager und System Manager.

## In der Umsatzsteuer-Voranmeldung

Kz 41 setzt voraus, dass der Abnehmer „eine ihm von einem anderen Mitgliedstaat erteilte gültige Umsatzsteuer-Identifikationsnummer verwendet“ (§ 6a Abs. 1 Satz 1 Nr. 4 UStG), und zwar zur Zeit der Lieferung: „Die USt-IdNr. muss vielmehr im Zeitpunkt der Lieferung gültig sein.“ (UStAE 6a.1 Abs. 12 Satz 3). Für die Umsätze hinter Kz 42 und Kz 21 nennt die Zusammenfassende Meldung die USt-IdNr. jedes letzten Abnehmers und jedes Leistungsempfängers (§ 18a Abs. 7 Satz 1 Nr. 4 und 3 UStG). Stimmt die Nummer nicht, bleibt eine Lieferung nur steuerfrei, wenn der Unternehmer „die Unrichtigkeit dieser Angaben auch bei Beachtung der Sorgfalt eines ordentlichen Kaufmanns nicht erkennen konnte“ (§ 6a Abs. 4 Satz 1 UStG). Dazu gehört die Bestätigung zur rechten Zeit: Wird das Bestätigungsverfahren „nicht oder zu einem späteren Zeitpunkt als dem des Umsatzes durchgeführt“, genügt das der Sorgfaltspflicht nicht (UStAE 6a.8 Abs. 6 Satz 1), und selbst „die alleinige Durchführung eines qualifizierten Bestätigungsverfahrens nach § 18e UStG“ reicht nicht, wenn ein Vertreter die Ware abholt (UStAE 6a.8 Abs. 7 Satz 3). Für sonstige Leistungen gilt die Vermutung, ein Empfänger mit USt-IdNr. sei Unternehmer, nur mit der qualifizierten Bestätigung, siehe [Einfache und qualifizierte Abfrage](#einfache-und-qualifizierte-abfrage) (UStAE 3a.2 Abs. 9 Satz 5). Das BZSt beschreibt das Verfahren als Prüfung, „ob zum Zeitpunkt der Leistungserbringung die Lieferung oder sonstige Leistung an ein in einem anderen EU-Mitgliedsstaat registriertes Unternehmen erbracht wird“ (BZSt, Bestätigung ausländischer USt-IdNrn).

Deshalb lässt auch die Voranmeldung ihre Nummern bestätigen, und „Berechnen“ sagt, welche Nummer keine, eine zu alte oder eine Bestätigung hat, die sie ungültig fand.

**USt-IdNrn. prüfen.** An einer berechneten Voranmeldung im Entwurf steht die Schaltfläche neben „Berechnen“ und fragt mit demselben Dialog wie an der Zusammenfassenden Meldung nach der USt-IdNr. jedes Kunden hinter Kz 41, 42 und 21 des Zeitraums, jede Nummer einmal. Die Belege und ihre Kunden liest Steuerbote aus dem Hauptbuch des Voranmeldungszeitraums, wie die Zusammenfassende Meldung sie liest (`zm_sources.span_shares`, `zm_sources.parties`): eine Ausgangsrechnung mit der USt-IdNr., mit der sie erstellt wurde, eine Zahlung oder eine Journalbuchung mit der der Rechnung, auf die sie sich bezieht. Name und Ort für die qualifizierte Abfrage kommen wie dort aus dem Kunden. Eine Nummer, die das BZSt gar nicht bestätigen kann, etwa eine deutsche, fragt Steuerbote nicht an (`problem()`, siehe [Aufbau einer USt-IdNr.](#aufbau-einer-ust-idnr)). Der Ablauf gehört beiden Belegen gemeinsam (`steuerbote/steuerbote/doctype/vat_id_confirmation/confirming.py` und `public/js/vat_id_confirmation.js`): ein Hintergrundjob in der Queue `long` mit einer Job-ID je Beleg und keine zweite Prüfung, solange eine läuft, eine Abfrage nach der anderen, jede als USt-IdNr.-Bestätigung sofort festgeschrieben, die den Beleg nennt. Solange die Prüfung läuft, lässt sich die Voranmeldung weder ändern noch berechnen noch übermitteln, und während einer Übermittlung beginnt keine Prüfung; ist der Job verschwunden, gibt das Formular die Sperre frei. Nach einem eigenen Senden, das ELSTER angenommen hat oder dessen Ergebnis unbekannt ist, prüft die Voranmeldung nicht mehr. Am Ende gibt der Job die Hinweise zu den USt-IdNrn. neu, die übrigen Hinweise bleiben, wie „Berechnen“ sie fand, und wer die Prüfung gestartet hat, bekommt eine Nachricht.

**Die Hinweise.** „Berechnen“ liest je Nummer die letzte USt-IdNr.-Bestätigung des Unternehmens, gleich ob sie aus einer Zusammenfassenden Meldung oder aus einer Voranmeldung kam, und gibt je Nummer höchstens einen Hinweis (`vat_id_hints` in `steuerbote/ustva/plausibility.py`):

| Code | Art | Wann |
|---|---|---|
| `USTIDNR-UNGEPRUEFT` | Hinweis | Die Nummer hat keine Bestätigung, oder die letzte Abfrage ergab kein Ergebnis; dann nennt der Hinweis ihren Tag. Er verweist auf „USt-IdNrn. prüfen“. |
| `USTIDNR-VERALTET` | Hinweis | Die letzte Bestätigung liegt mehr Tage vor dem Ende des Voranmeldungszeitraums, als die Einstellungen zulassen. |
| `USTIDNR-UNGUELTIG` | Fehler | Die letzte Bestätigung fand die Nummer ungültig, oder das BZSt kann sie gar nicht bestätigen; der Hinweis nennt den Tag der Abfrage oder den Grund. War die Nummer laut Antwort durch den ganzen Zeitraum gültig (`evatr-2006` mit `gueltigAb` und `gueltigBis`, `evatr-2002` mit `gueltigAb`), zählt sie wie an der Zusammenfassenden Meldung als bestätigt. |

Eine Nummer, die zuletzt gültig und frisch bestätigt wurde, bekommt keinen Hinweis. Jeder Hinweis nennt die Nummer, den Kunden und die Kennzahlen, etwa: „Die USt-IdNr. ATU12345678 des Kunden Alpen Handel GmbH (Kz 41) ist zuletzt am 1. Juli 2026 bestätigt worden, 122 Tage vor dem Ende des Voranmeldungszeitraums Oktober 2026; die Einstellungen lassen höchstens 90 Tage zu. „USt-IdNrn. prüfen“ fragt erneut.“ Eine ungültige Nummer und eine, die das BZSt gar nicht bestätigen kann, halten die Voranmeldung als Fehler an, ebenso ein Kunde ohne USt-IdNr. (`EU-OHNE-USTID`): Ohne gültige USt-IdNr. des Abnehmers ist eine innergemeinschaftliche Lieferung nicht steuerfrei (§ 6a Abs. 1 Satz 1 Nr. 4 UStG), und ohne richtige Zeile in der ZM entfällt die Steuerfreiheit ebenso (§ 4 Nr. 1 Buchst. b UStG). Steuerbote kann eine Rechnung nicht selbst neu besteuern: Die Voranmeldung bleibt „Berechnet“, bis die Rechnung berichtigt ist oder die Bemerkungen begründen, warum sie trotzdem so abgegeben wird; die Bemerkungen stehen im Ausdruck. Die Zusammenfassende Meldung hält denselben Beleg mit demselben Satz an (`steuerbote/vatid/exemption.py`), siehe [Zusammenfassende Meldung](zm.md#sperren-und-übersteuern). Eine nicht bestätigte oder zu alte Bestätigung bleibt an der Voranmeldung ein Hinweis, denn sie belegt die Sorgfalt, ändert aber die Kennzahl nicht; an der Zusammenfassenden Meldung, die die Nummer meldet, hält eine nicht bestätigte Nummer an. Einen Kunden ohne USt-IdNr. nennt der Hinweis `EU-OHNE-USTID` an seiner Rechnung, siehe [Architektur](architektur.md#vorperiodenvergleich-und-hinweise).

**Wie alt eine Bestätigung sein darf.** Eine Frist in Tagen nennt keine der Quellen: Das BZSt bestätigt für den Zeitpunkt der Anfrage, „Bestätigungen für zurückliegende Zeitpunkte oder Zeiträume sind nicht möglich“ (BZSt, FAQ), und die Sorgfalt verlangt die Bestätigung spätestens zum Umsatz (UStAE 6a.8 Abs. 6 Satz 1). Steuerbote zählt deshalb die Tage von der letzten Bestätigung bis zum Ende des Voranmeldungszeitraums und vergleicht sie mit „Höchstalter der USt-IdNr.-Bestätigung (Tage)“ in den Einstellungen (`max_confirmation_age`). Die Vorgabe sind 90 Tage, etwa ein Kalendervierteljahr, der Voranmeldungszeitraum, den § 18 Abs. 2 Satz 1 UStG vorsieht: Wer jede Nummer einmal im Vierteljahr bestätigen lässt, bekommt keinen Hinweis. 0 lässt nur Bestätigungen vom letzten Tag des Zeitraums oder später gelten. Eine Bestätigung nach dem Ende des Zeitraums zählt als frisch, denn sie ist die neueste Antwort über die Nummer; dass sie den Zeitpunkt des Umsatzes nicht mehr belegt (UStAE 6a.8 Abs. 6 Satz 1), prüft Steuerbote nicht. Wie oft das Unternehmen bestätigen lässt, legt es mit seiner Steuerberatung fest.

**Grenzen.**

- Die Hinweise lesen nur die letzte Bestätigung einer Nummer. Ob es zur Zeit jedes Umsatzes eine gab, prüft die Ausgangsrechnung beim Buchen, siehe [Die Ausgangsrechnung](#die-ausgangsrechnung); eine Zahlung oder Journalbuchung prüft Steuerbote nicht.
- Ob die letzte Bestätigung einfach oder qualifiziert war und ob Name und Anschrift übereinstimmten, sagen die Hinweise nicht; das steht in der USt-IdNr.-Bestätigung und in der [Arbeitsliste](#arbeitsliste).
- Eine Prüfung erst mit der Voranmeldung kommt wie die mit der Zusammenfassenden Meldung spät, siehe [Das Bestätigungsverfahren](#das-bestätigungsverfahren); sie ergänzt die Bestätigung am Partner, sie ersetzt sie nicht.

## Datenschutz

Dieser Abschnitt ist eine Orientierung für den Betreiber, keine Rechtsberatung. Was das Unternehmen in seine Datenschutzhinweise und sein Verzeichnis der Verarbeitungstätigkeiten schreibt, entscheidet es mit seiner Datenschutzberatung.

**Was die Site verlässt, an wen.** Jede Bestätigung einer Nummer eines anderen Mitgliedstaats geht an das BZSt (`api.evatr.vies.bzst.de`), nur wenn das BZSt die einfache Abfrage nicht beantworten kann, an VIES der Europäischen Kommission (`ec.europa.eu`). Die Prüfung einer deutschen Nummer geht an VIES allein, mit der eigenen USt-IdNr. des Unternehmens und der Nummer des Partners, ohne Name und Anschrift. Das BZSt leitet die Anfrage an die Behörde des Mitgliedstaats weiter, der die Nummer erteilt hat (BZSt, Bestätigung ausländischer USt-IdNrn).

| Auslöser | Was gesendet wird |
|---|---|
| jede Bestätigung | die eigene USt-IdNr. des Unternehmens und die USt-IdNr. des Partners |
| qualifizierte Abfrage, wenn Name und Ort des Partners bekannt sind | dazu Name, Ort, Postleitzahl und Straße des Partners |
| Partner angelegt oder geändert, Schaltfläche am Partner oder an der Ausgangsrechnung, tägliche Erneuerung, „USt-IdNrn. prüfen“ | dasselbe; welcher Auslöser es war, steht in der Bestätigung |

Nie gesendet werden eine fehlerhafte oder nicht bestätigbare Nummer, eine deutsche Nummer, wo das Unternehmen deutsche Nummern nicht prüft, die Steuernummer und die ausländische Steuernummer eines Partners, und kein Partner, dessen Unternehmen keine eigene USt-IdNr. hat. Jeder Dialog vor einer Bestätigung auf Knopfdruck nennt, was gesendet wird.

**Wie.** Nur über HTTPS: „Der Zugriff ist ausschließlich über eine TLS-verschlüsselte HTTPS-Verbindung möglich.“ (BZSt, FAQ). `UrllibFetch` weist jede andere Adresse ab und folgt keiner Weiterleitung, auch nicht zu einem anderen Server oder zu HTTP.

**Personenbezug.** Ist der Partner eine natürliche Person, etwa ein Einzelunternehmen oder eine Personengesellschaft natürlicher Personen, sind USt-IdNr., Name und Anschrift personenbezogene Daten (Art. 4 Nr. 1 DSGVO).

**Wer auf der anderen Seite verarbeitet.** Das BZSt verarbeitet die Anfragen nach § 18e UStG; nach seinem Datenschutz-Produktsteckbrief zum Bestätigungsverfahren speichert es Anfragen und Antworten 20 Jahre und kann sie an die Finanzbehörden der Länder und anderer Mitgliedstaaten weitergeben (BZSt, Produktsteckbrief). Bei VIES sind die Steuerverwaltungen der Mitgliedstaaten gemeinsam Verantwortliche; die Kommission betreibt das System als Auftragsverarbeiter und hält die Daten nicht vor (VIES, Datenschutzerklärung). Beide handeln in eigener gesetzlicher Zuständigkeit; einen Vertrag über eine Auftragsverarbeitung (Art. 28 DSGVO) braucht das Unternehmen mit ihnen nach dieser Einschätzung nicht.

**Rechtsgrundlage, nach Einschätzung.** Für Kunden aus anderen Mitgliedstaaten Art. 6 Abs. 1 Buchst. c DSGVO mit § 4 Nr. 1 Buchst. b, § 6a und § 18a UStG, § 17d UStDV und § 147 AO: Die Bestätigung ist Teil der Sorgfalt und des Nachweises, die das Gesetz für die steuerfreie Lieferung und den Ort der sonstigen Leistung verlangt (siehe [Die Ausgangsrechnung](#die-ausgangsrechnung)). Für Lieferanten, für deutsche Nummern und für die regelmäßige Erneuerung Art. 6 Abs. 1 Buchst. f DSGVO: das berechtigte Interesse an der richtigen umsatzsteuerlichen Behandlung und am Erkennen falscher Rechnungen. Wer das für Lieferanten oder deutsche Nummern nicht will, schaltet „Lieferanten bestätigen“ oder „Deutsche USt-IdNrn. prüfen“ aus. Die Aufbewahrung der Bestätigungen stützt sich auf Art. 6 Abs. 1 Buchst. c DSGVO mit § 147 AO.

**Was der Betreiber festhalten sollte.**

1. **Datenschutzhinweise für Geschäftspartner** (Art. 13 DSGVO bei der Erhebung, Art. 14 DSGVO für das Ergebnis, das von einer Behörde kommt): Zweck (Bestätigung der USt-IdNr. nach § 18e UStG, Prüfung deutscher USt-IdNrn. bei VIES), Daten (USt-IdNr., Name, Anschrift, Ergebnis, Zeitpunkt, Nummer der Abfrage, Vergleichsergebnisse), Empfänger (BZSt; über das BZSt oder VIES die Steuerverwaltung des Mitgliedstaats der Nummer; die Kommission als Betreiberin von VIES), Rechtsgrundlagen wie oben, Speicherdauer.
2. **Eintrag im Verzeichnis der Verarbeitungstätigkeiten** (Art. 30 DSGVO), etwa „Bestätigung der USt-IdNrn. von Geschäftspartnern“: dieselben Angaben, die Kategorien der Betroffenen (Kunden und Lieferanten, die natürliche Personen sind), die Löschfrist und die technischen und organisatorischen Maßnahmen: Übertragung nur über TLS, Bestätigungen und Antworten lesen nur die Rollen Accounts User, Accounts Manager und System Manager, Antworten als private Dateien.
3. **Datensparsamkeit:** Gesendet wird nur, was die Bestätigung braucht; für deutsche Nummern nur die beiden Nummern, ohne Name und Anschrift. Ob Lieferanten und deutsche Nummern geprüft werden, ist eine Entscheidung des Unternehmens.

**Was bleibt.** Steuerbote hält jede Antwort, wie sie kam. Bei VIES kann sie Name und Anschrift enthalten, wie der Mitgliedstaat sie registriert hat (`traderName`, `traderAddress`). Cookies der Dienste hält `UrllibFetch` nur im Speicher, je Instanz.

**Aufbewahrung.** Jede Abfrage bleibt als USt-IdNr.-Bestätigung in der Datenbank der Site, mit angefragter und anfragender USt-IdNr., dem Partner, bei der qualifizierten Abfrage mit Name und Anschrift des Partners, und ihre Antwort als private Datei unter `sites/<site>/private/files`; beide stehen in jeder Sicherung mit Dateien. Sie sind der Nachweis der Abfrage (UStAE 18e.1 Abs. 2 Satz 5) und gehören zu den Unterlagen, die das Unternehmen nach § 147 AO aufbewahrt; wie lange, klärt es mit der Steuerberatung. Steuerbote löscht keine Bestätigung und lässt sie über den Beleg nicht löschen, auch nicht nach Ablauf der Frist, siehe [Die USt-IdNr.-Bestätigung](#die-ust-idnr-bestätigung): Eine Löschung nach der Frist ist Sache des Betreibers und geht heute nur an Steuerbote vorbei in der Datenbank. Scheitert eine Abfrage, schreibt Steuerbote den Fehler mit dem Traceback in das Fehlerprotokoll (Error Log) von Frappe, im Entwicklermodus womöglich mit USt-IdNrn., Namen und Anschriften aus den lokalen Variablen. Frappe löscht diese Einträge jeden Tag, sobald sie älter sind als die Tage, die die Protokolleinstellungen (Log Settings) unter „Zu löschende Protokolle“ für das Fehlerprotokoll nennen; ohne eigenen Eintrag sind es in Frappe 16 14 Tage (`default_log_clearing_doctypes` in `frappe/hooks.py`).

## Offene Fragen

1. **Anmeldung an der REST-API.** Das OpenAPI-Dokument beschreibt kein Verfahren zur Anmeldung, und beide Proben kamen ohne Zugangsdaten aus. Für die XML-RPC-Schnittstelle schrieb das BZSt: „die Nutzung der Schnittstelle ist durch keine Registrierung reglementiert“ (BZSt, FAQ). Für die REST-API sagt es das nicht.
2. **Grenzen für Abfragen.** Eine Höchstzahl je Zeit nennt das BZSt nicht, nur Einzelabfragen nacheinander, kein unmittelbares Wiederholen und `evatr-0008` für die qualifizierten Abfragen einer Session.
3. **Session.** Wie das BZSt eine Session erkennt und ob die qualifizierte Abfrage zur Session der einfachen gehören muss, ist nicht beschrieben. Die erste Probe bekam ein Cookie `AL_BALANCE-S`; `UrllibFetch` hält Cookies je Instanz, damit beide Abfragen einer Prüfung dieselbe Session haben, falls es darauf ankommt.
4. **Format von `gueltigAb` und `gueltigBis`.** Das OpenAPI-Dokument sagt nur „string“. Steuerbote liest ISO 8601 wie bei `anfrageZeitpunkt`; ein anderes Format macht die Antwort unlesbar, mit unbekanntem Ergebnis, und der Datensatz bleibt erhalten.
5. **Rumänische Nummern mit zwei bis vier Ziffern.** Ob das BZSt die für die Zusammenfassende Meldung aufgefüllte Form bestätigt, siehe [Aufbau einer USt-IdNr.](#aufbau-einer-ust-idnr).
6. **VIES als Nachweis.** Für die Steuerberatung, siehe [Ausweichen auf VIES](#ausweichen-auf-vies).
7. **Höchstalter einer Bestätigung.** Keine Quelle nennt eine Zahl von Tagen. Die Vorgaben, null Tage für Lieferungen und 90 für sonstige Leistungen und die Erneuerung, sind mit der Steuerberatung abzustimmen, siehe [Einstellungen](#einstellungen).
8. **Lieferanten.** Ob das Unternehmen die USt-IdNrn. seiner Lieferanten bestätigen lässt, verlangt kein Gesetz; Steuerbote tut es nach der Vorgabe, siehe [Datenschutz](#datenschutz).
9. **Deutsche Nummern bei VIES.** Ob VIES einem deutschen Anfragenden zu einer deutschen Nummer antwortet, mit Nummer der Abfrage, und ob die Prüfung deutscher Partner unter den Zweck von VIES fällt, siehe [Deutsche USt-IdNrn.](#deutsche-ust-idnrn).

## Quellen

Am 20. November 2026 gelesen, wo nichts anderes steht.

- § 18e UStG „Bestätigungsverfahren“: <https://www.gesetze-im-internet.de/ustg_1980/__18e.html>
- § 6a UStG „Innergemeinschaftliche Lieferung“, Abs. 1 Satz 1 Nr. 4 und Abs. 4, am 23. November 2026 gelesen: <https://www.gesetze-im-internet.de/ustg_1980/__6a.html>
- § 18 UStG, Abs. 2 Satz 1 („Voranmeldungszeitraum ist das Kalendervierteljahr.“), am 23. November 2026 gelesen: <https://www.gesetze-im-internet.de/ustg_1980/__18.html>
- § 18a UStG, Abs. 7 Satz 1 Nr. 1, 3 und 4, am 23. November 2026 gelesen: <https://www.gesetze-im-internet.de/ustg_1980/__18a.html>
- Umsatzsteuer-Anwendungserlass, Stand 13. November 2026, Abschnitte 3a.2 Abs. 9, 6a.1 Abs. 12, 6a.8 Abs. 6 und 7, 18e.1 und 18e.2: <https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/Umsatzsteuer-Anwendungserlass/Umsatzsteuer-Anwendungserlass-aktuell.pdf?__blob=publicationFile&v=61> (SHA-256 `406cda32cf956d29f2ffde5079c8a7f963a763aa47615c6652148856a23e4c2e`, am 23. November 2026 wieder geladen, dieselbe Datei)
- BZSt, „Bestätigung ausländischer USt-IdNrn“, Einleitung (am 23. November 2026 wieder gelesen, unverändert) und Abschnitte „Abfragemöglichkeiten“, „Hinweis zum Bestätigungsverfahren“, „Infos zur REST-API“ und „XML-RPC-Schnittstelle (ab 30.11.2025 obsolet)“: <https://www.bzst.de/DE/Unternehmen/Identifikationsnummern/Umsatzsteuer-Identifikationsnummer/AuslaendischeUSt-IdNr/auslaendische_ust_idnr_node.html>
- BZSt, „Fragen und Antworten“ zur USt-IdNr. (zitiert als BZSt, FAQ), Abschnitte „Bestätigungsverfahren“ mit den Fragen nach dem Unterschied der einfachen und der qualifizierten Bestätigung und nach zurückliegenden Zeitpunkten, „Bestätigung ausländischer USt-IdNr.“, Nordirland und Großbritannien sowie „Bestätigung via Schnittstelle“, am 23. November 2026 wieder gelesen, unverändert: <https://www.bzst.de/DE/Unternehmen/Identifikationsnummern/Umsatzsteuer-Identifikationsnummer/FAQ/faq_ust_node.html>
- BZSt, Merkblatt „Aufbau der Umsatzsteuer-Identifikationsnummer (USt-IdNr.) in den EU-Mitgliedstaaten“: <https://www.bzst.de/SharedDocs/Downloads/DE/Merkblaetter/ust_idnr_aufbau.pdf?__blob=publicationFile&v=8> (SHA-256 `9f77010c20056dbb4049b836d1b640c65975c9e89c330077fbfbb64ce604fb57`)
- OpenAPI 3.0.1 „eVATR API“, Version v:1.2.3.19.886, Server `/app`, `POST /v1/abfrage`, Schemas `Bestaetigungsabfrage` und `Bestaetigungsantwort`: <https://api.evatr.vies.bzst.de/api-docs>
- Statusmeldungen der eVatR-API: <https://api.evatr.vies.bzst.de/v1/info/statusmeldungen>, Kopie in `steuerbote/vatid/tests/fixtures/statusmeldungen.json`
- Liste der Mitgliedstaaten der eVatR-API: <https://api.evatr.vies.bzst.de/v1/info/eu_mitgliedstaaten>, Kopie in `steuerbote/vatid/tests/fixtures/eu_mitgliedstaaten.json`
- WSDL von VIES, Dokumentation (Zweck, Haftung, Fehlerwerte), `checkVatApprox` und `checkVatApproxResponse`, Adresse des Dienstes: <https://ec.europa.eu/taxation_customs/vies/checkVatService.wsdl>
- ERiC-Dokumentation 44.3.6.0, `Datenarten/ElsterExtern/ZMDO/Jahresdokumentation/Jahresdokumentation_ZMDO_2.ods`, Blatt „ZMDO - Felder“ (Feld `knre_UstIdNr_Erwerber`) und Blatt „ZMDO - Regeln“ (Regel 17004518): <https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Dokumentation.zip>
- ERPNext 16.60.0, `erpnext/setup/doctype/transaction_deletion_record/transaction_deletion_record.py`: `get_doctypes_to_be_ignored()` mit dem Hook `company_data_to_be_ignored`, `generate_to_delete_list()`, die die ausgeschlossenen DocTypes auslässt, und `delete_docs_linked_with_specified_company()` mit `frappe.db.delete`: <https://github.com/frappe/erpnext/blob/v16.60.0/erpnext/setup/doctype/transaction_deletion_record/transaction_deletion_record.py>
- Umsatzsteuer-Anwendungserlass, Abschnitt 3a.2 Abs. 10, am 25. November 2026 gelesen, Stand 31. Dezember 2025: <https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/Umsatzsteuer-Anwendungserlass/Umsatzsteuer-Anwendungserlass-31-12-2025.pdf>
- § 14 UStG „Ausstellung von Rechnungen“, Abs. 2 Satz 2 und Abs. 4 Satz 1 Nr. 2, und § 15 Abs. 1 Satz 1 Nr. 3 und 4 UStG, am 25. November 2026 gelesen: <https://www.gesetze-im-internet.de/ustg_1980/__14.html>, <https://www.gesetze-im-internet.de/ustg_1980/__15.html>
- VIES, Hilfe, FAQ und Haftungsausschluss (zitiert als VIES, FAQ), mit den Fällen, die die Kommission als Missbrauch ansieht, am 25. November 2026 gelesen: <https://ec.europa.eu/taxation_customs/vies/>
- VIES, Datenschutzerklärung (Privacy Statement), am 25. November 2026 gelesen: <https://taxation-customs.ec.europa.eu/document/download/a6cea373-9e05-45b8-9edb-e122ef35423a_en>
- BZSt, Datenschutz-Produktsteckbrief „Umsatzsteuer-Kontrollverfahren; Teilbereich Bestätigung“ (zitiert als BZSt, Produktsteckbrief), am 25. November 2026 gelesen: <https://www.bzst.de/SharedDocs/Downloads/DE/Informationen_zum_Datenschutz/USt_Kontrollverfahren_Teilbereich_Bestaetigung.pdf?__blob=publicationFile&v=3>
- Verordnung (EU) 2016/679 (DSGVO), Art. 4 Nr. 1, Art. 6 Abs. 1 Buchst. c und f, Art. 13, 14, 28 und 30; § 147 AO; § 17d UStDV
- Frappe 16.60.2, `frappe/core/doctype/scheduled_job_type/scheduled_job_type.py`: `insert_single_event` aktualisiert bei `bench migrate` nur Häufigkeit und Cron eines bestehenden Jobs
- Österreichisches BMF, „Information über die Konstruktionsregeln der Umsatzsteuer-Identifikationsnummern (UID)“, Stand November 2020, Abschnitt Deutschland mit Verfahren und Beispiel 111111125, am 25. November 2026 gelesen: <https://bmf.gv.at/dam/jcr:d6794f8f-d321-43df-9840-1a841f9bf5dc/BMF_UID_Konstruktionsregeln_Stand_November%202020.pdf>
- BZSt, FAQ, Frage „Kann ich als deutsches Unternehmen auch deutsche USt-IdNrn. im Bestätigungsverfahren abfragen?“, am 25. November 2026 gelesen (Adresse wie oben)
- § 25f UStG, Abs. 1, am 25. November 2026 gelesen: <https://www.gesetze-im-internet.de/ustg_1980/__25f.html>
- Umsatzsteuer-Anwendungserlass, Abschnitte 15.2a Abs. 6 und 25f.1 Abs. 4 und 5, im Umsatzsteuer-Handbuch 2024 des BMF, am 25. November 2026 gelesen: <https://usth.bundesfinanzministerium.de/usth/2024/A-Umsatzsteuergesetz/IV-Steuer-und-Vorsteuer/Paragraf-15/inhalt.html>, <https://usth.bundesfinanzministerium.de/usth/2024/A-Umsatzsteuergesetz/VI-Sonderregelungen/Paragraf-25f/inhalt.html>
- EN 16931 in der Syntax von Peppol BIS Billing 3.0, BT-48 „Buyer VAT identifier“, am 25. November 2026 gelesen: <https://docs.peppol.eu/poacc/billing/3.0/syntax/ubl-invoice/cac-AccountingCustomerParty/cac-Party/cac-PartyTaxScheme/cbc-CompanyID>
- Probe der eVatR-API am 20. November 2026, 15:35 Uhr: `POST /app/v1/abfrage` mit `{"anfragendeUstid":"DE123456789","angefragteUstid":"ATU00000000"}`, Antwort HTTP 400 mit `id`, `anfrageZeitpunkt` und `status` `evatr-0004`.
- Probe der eVatR-API am 20. November 2026, 19:13 Uhr, mit `confirm()` und den Testwerten des OpenAPI-Dokuments (Beschreibung von `/v1/abfrage`): einfache und qualifizierte Abfrage je mit HTTP 200 und `status` `evatr-0000`, die qualifizierte mit `ergFirmenname`, `ergStrasse`, `ergPlz` und `ergOrt` A.
