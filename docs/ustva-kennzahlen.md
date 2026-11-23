# Umsatzsteuer-Voranmeldung: Kennzahlen und Kontenzuordnung

Diese Seite ist die fachliche Grundlage des Rechenkerns unter `steuerbote/ustva`: Quelle, Rundung, alle Kennzahlen des Katalogs, die Kontenzuordnung mit den Vorgaben für SKR03 und SKR04 sowie Zeiträume und Fristen. Sie ersetzt keine Steuerberatung. Lass die Einrichtung deiner Firma von deiner Steuerberatung bestätigen.

## Quelle

BMF-Schreiben vom 29. Dezember 2025, GZ III C 3 - S 7344/00039/007/036: „Umsatzsteuer; Muster der Vordrucke im Umsatzsteuer-Voranmeldungs- und -Vorauszahlungsverfahren für das Kalenderjahr 2026“

<https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/2025-12-29-vordruckmuster-USt-voranmeldung-2026.pdf>

Das Schreiben führt für die Voranmeldungszeiträume ab Januar 2026 vier Vordruckmuster ein:

| Vordruck | Inhalt | Verwendung in Steuerbote |
|---|---|---|
| USt 1 A | Umsatzsteuer-Voranmeldung 2026 | Zeilen, Kennzahlen und Bezeichnungen des Katalogs |
| USt 1 E | Anleitung zur Umsatzsteuer-Voranmeldung 2026 | Rundung, Fälligkeit |
| USt 1 H | Antrag auf Dauerfristverlängerung und Anmeldung der Sondervorauszahlung 2026 | Stufe 2 der [Roadmap](roadmap.md) |
| USt 5 E | Anleitung zum Antrag auf Dauerfristverlängerung/zur Anmeldung der Sondervorauszahlung 2026 | Stufe 2 der Roadmap |

[`kennzahlen.py`](../steuerbote/ustva/kennzahlen.py) führt einen Katalog je Jahr des Vordrucks (`CATALOGUES`), bisher für 2026, für die Jahre der Jahrestabelle `YEARS` in [`years.py`](../steuerbote/ustva/years.py). Der Katalog 2026 folgt dem Vordruck USt 1 A 2026 Zeile für Zeile. [`test_kennzahlen.py`](../steuerbote/ustva/tests/test_kennzahlen.py) hält jede Kennzahl mit Zeile, Art, Wirkung, Steuersatz und Steuer-Kennzahl so fest, wie sie auf dem Vordruck steht, und prüft den Katalog dagegen. `catalogue_for(year)` wählt den Katalog nach dem Jahr des Zeitraums, `KENNZAHLEN` ist der neueste (`LATEST_YEAR`). Für ein Jahr ohne Katalog gibt es einen `UnknownYearError`.

Vordruck und Anleitung ändern sich jedes Jahr. Deshalb kommt zu jedem Jahreswechsel ein Katalog für das neue Jahr dazu, Zeile für Zeile gegen das neue BMF-Schreiben geprüft, siehe [Jahreswechsel](#jahreswechsel). Der erste Katalog ist der für 2026; Kataloge für frühere Jahre sind nicht geplant, siehe [Roadmap](roadmap.md#grundsätze).

Die Kontenbezeichnungen auf dieser Seite stammen aus den DATEV-Kontenrahmen nach dem Bilanzrichtlinie-Umsetzungsgesetz, gültig für 2026:

- Standardkontenrahmen SKR 03 (Prozessgliederungsprinzip), Art.-Nr. 11174: <https://www.datev.de/content/dam/markenassets/themen-und-produktgruppen/zielgruppen/mandant/unternehmer/branche/bau/11174%20SKR03%20BilrUg.pdf>
- Standardkontenrahmen SKR 04 (Abschlussgliederungsprinzip), Art.-Nr. 11175: <https://www.datev.de/content/dam/markenassets/themen-und-produktgruppen/zielgruppen/mandant/unternehmer/branche/bau/11175%20SKR04%20BilrUg.pdf>

## Rundung

Die Anleitung zur Umsatzsteuer-Voranmeldung 2026 sagt:

> „Tragen Sie bei den Bemessungsgrundlagen bitte nur Beträge in vollen Euro ein; bei den Umsatzsteuer- und Vorsteuerbeträgen ist dagegen stets auch die Eintragung von Centbeträgen erforderlich.“

Zu den Zeilen 13 bis 16 ergänzt sie, dass Bemessungsgrundlagen „in vollen Euro (ohne Centbeträge) anzugeben“ sind. Negative Beträge erhalten ein Minuszeichen.

Steuerbote setzt das in [`rounding.py`](../steuerbote/ustva/rounding.py) so um:

| Betrag | Regel | Funktion | Beispiele aus den Tests |
|---|---|---|---|
| Bemessungsgrundlage | volle Euro: Die Cent fallen weg, Richtung null, auch bei negativen Beträgen | `to_full_euros` | 1.000,99 → 1.000; -1.000,99 → -1.000; -0,40 → 0 |
| Steuerbetrag | auf Cent kaufmännisch gerundet, ein halber Cent rundet weg von null | `to_cents` | 0,005 → 0,01; 0,004 → 0,00; -0,005 → -0,01 |
| Steuer aus einer Bemessungsgrundlage | Bemessungsgrundlage × Steuersatz, dann auf Cent gerundet | `tax_from_base` | 999 × 7 % → 69,93; 0,50 × 19 % → 0,10 |

Ein Ergebnis von null wird nie als „-0“ gemeldet. Außerdem gilt:

- **Alles ist `Decimal`.** Ein `float` führt zu einem `TypeError`, weil binäre Gleitkommazahlen Cent nicht genau darstellen. Gerundet wird nur in `rounding.py`.
- **Buchungen kommen in Cent.** Jeder Betrag einer Buchungszeile (`LedgerLine`) und jeder Wert in `extra_values` muss endlich sein und in ganzen Cent vorliegen, sonst folgt ein `ValueError`.
- **Kz 83 rechnet mit den gemeldeten Werten.** Für die Zeilen 13, 14, 25 und 26 (Kz 81, 86, 89 und 93) hat der Vordruck keine eigene Steuer-Kennzahl, die Steuer ergibt sich aus Bemessungsgrundlage und Steuersatz. Steuerbote berechnet sie aus der gemeldeten Bemessungsgrundlage in vollen Euro. Alle anderen Beträge gehen mit ihrem gemeldeten Wert in Cent ein.
- **Die Verprobung rechnet mit dem genauen Wert.** Sie vergleicht die gebuchte Steuer mit der Steuer auf die genaue Bemessungsgrundlage. Beispiel aus den Tests: 1.000,99 EUR auf 8400 und 190,19 EUR auf 1776 ergeben Kz 81 = 1.000 und Kz 83 = 190,00. Die Verprobung rechnet 1.000,99 × 19 % = 190,19 und geht ohne Differenz auf.
- **Toleranz.** Die Bücher runden die Steuer je Beleg, nicht je Monat. Deshalb rechnet Steuerbote die abgeleitete Steuer (Kz 47, 85, 96) und jede Verprobung je Beleg (`voucher` der Buchungszeile): Die Steuer eines Belegs wird aus seinen Grundlagen berechnet und auf Cent gerundet, die Kennzahl ist die Summe dieser Beträge. Je Beleg darf die gebuchte Steuer um höchstens `tolerance` (Vorgabe 0,01 EUR) von der berechneten abweichen, sonst steht der Beleg als `Deviation` in der Verprobung. Buchungszeilen ohne Beleg bilden eine Gruppe; dort gilt die Toleranz je Buchung auf den Grundlagenkonten.

## Kennzahlen des Vordrucks USt 1 A 2026

Der Katalog für 2026 enthält 50 Kennzahlen. Zu den Spalten:

- **Art:** Bemessungsgrundlage (gemeldet in vollen Euro), Steuer (gemeldet in Cent), Kennzeichen, Datum oder Schlüssel. Kennzeichen, Datum und Schlüssel tragen keinen Betrag. Sie lassen sich keinem Konto zuordnen und nicht über `extra_values` setzen; gesetzt werden sie in eigenen Feldern der Meldung: Kz 10, 22, 26 und 29 als Kennzeichen, Kz 70 als Datum und Kz 500 mit Begründung, siehe [Architektur](architektur.md#umsatzsteuer-voranmeldung-vat-return).
- **Wirkung:** wie der Betrag in die verbleibende Vorauszahlung (Kz 83) eingeht: erhöht, mindert oder keine. Bei Kz 81, 86, 89 und 93 erhöht die Steuer, die aus der Bemessungsgrundlage folgt.
- **Steuersatz/Steuer-Kz:** der Satz, mit dem der Vordruck die Steuer selbst berechnet, oder die Kennzahl, in der die Steuer zu dieser Bemessungsgrundlage eigens steht.

| Zeile | Kz | Bezeichnung (kurz) | Art | Wirkung | Steuersatz/Steuer-Kz |
|---|---|---|---|---|---|
| | | **Vor Abschnitt A** | | | |
| 10 | 10 | Berichtigte Anmeldung | Kennzeichen | keine | |
| 11 | 22 | Belege sind beigefügt bzw. werden gesondert eingereicht | Kennzeichen | keine | |
| 12 | 70 | Wechsel von der Kleinunternehmer-Regelung (§ 19 UStG) zur Regelbesteuerung: Datum des Wechsels | Datum | keine | |
| | | **A. Steuerpflichtige Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben** | | | |
| 13 | 81 | Steuerpflichtige Umsätze zu 19 % | Bemessungsgrundlage | erhöht | 19 % |
| 14 | 86 | Steuerpflichtige Umsätze zu 7 % | Bemessungsgrundlage | erhöht | 7 % |
| 15 | 87 | Steuerpflichtige Umsätze zu 0 % | Bemessungsgrundlage | keine | |
| 16 | 35 | Steuerpflichtige Umsätze zu anderen Steuersätzen | Bemessungsgrundlage | keine | Kz 36 |
| 16 | 36 | Steuer auf Umsätze zu anderen Steuersätzen | Steuer | erhöht | |
| 17 | 77 | Lieferungen land- und forstwirtschaftlicher Betriebe nach § 24 UStG an Abnehmer mit USt-IdNr. | Bemessungsgrundlage | keine | |
| 18 | 76 | Umsätze, für die eine Steuer nach § 24 UStG zu entrichten ist | Bemessungsgrundlage | keine | Kz 80 |
| 18 | 80 | Steuer auf Umsätze nach § 24 UStG | Steuer | erhöht | |
| | | **B. Steuerfreie Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben** | | | |
| 19 | 41 | Innergemeinschaftliche Lieferungen (§ 4 Nr. 1 Buchst. b UStG) an Abnehmer mit USt-IdNr. | Bemessungsgrundlage | keine | |
| 20 | 44 | Innergemeinschaftliche Lieferungen neuer Fahrzeuge an Abnehmer ohne USt-IdNr. | Bemessungsgrundlage | keine | |
| 21 | 49 | Innergemeinschaftliche Lieferungen neuer Fahrzeuge außerhalb eines Unternehmens (§ 2a UStG) | Bemessungsgrundlage | keine | |
| 22 | 43 | Weitere steuerfreie Umsätze mit Vorsteuerabzug, z. B. Ausfuhrlieferungen | Bemessungsgrundlage | keine | |
| 23 | 48 | Steuerfreie Umsätze ohne Vorsteuerabzug | Bemessungsgrundlage | keine | |
| | | **C. Innergemeinschaftliche Erwerbe** | | | |
| 24 | 91 | Steuerfreie innergemeinschaftliche Erwerbe (§§ 4b und 25c UStG) | Bemessungsgrundlage | keine | |
| 25 | 89 | Steuerpflichtige innergemeinschaftliche Erwerbe zu 19 % | Bemessungsgrundlage | erhöht | 19 % |
| 26 | 93 | Steuerpflichtige innergemeinschaftliche Erwerbe zu 7 % | Bemessungsgrundlage | erhöht | 7 % |
| 27 | 90 | Steuerpflichtige innergemeinschaftliche Erwerbe zu 0 % | Bemessungsgrundlage | keine | |
| 28 | 95 | Steuerpflichtige innergemeinschaftliche Erwerbe zu anderen Steuersätzen | Bemessungsgrundlage | keine | Kz 98 |
| 28 | 98 | Steuer auf innergemeinschaftliche Erwerbe zu anderen Steuersätzen | Steuer | erhöht | |
| 29 | 94 | Innergemeinschaftliche Erwerbe neuer Fahrzeuge (§ 1b Abs. 2 und 3 UStG) von Lieferern ohne USt-IdNr. | Bemessungsgrundlage | keine | Kz 96 |
| 29 | 96 | Steuer auf innergemeinschaftliche Erwerbe neuer Fahrzeuge | Steuer | erhöht | |
| | | **D. Leistungsempfänger als Steuerschuldner (§ 13b UStG)** | | | |
| 30 | 46 | Sonstige Leistungen nach § 3a Abs. 2 UStG eines im übrigen Gemeinschaftsgebiet ansässigen Unternehmers (§ 13b Abs. 1 UStG) | Bemessungsgrundlage | keine | Kz 47 |
| 30 | 47 | Steuer auf diese sonstigen Leistungen | Steuer | erhöht | |
| 31 | 73 | Umsätze, die unter das GrEStG fallen (§ 13b Abs. 2 Nr. 3 UStG) | Bemessungsgrundlage | keine | Kz 74 |
| 31 | 74 | Steuer auf Umsätze, die unter das GrEStG fallen | Steuer | erhöht | |
| 32 | 84 | Andere Leistungen (§ 13b Abs. 2 Nr. 1, 2, 4 bis 12 UStG) | Bemessungsgrundlage | keine | Kz 85 |
| 32 | 85 | Steuer auf andere Leistungen nach § 13b UStG | Steuer | erhöht | |
| | | **E. Ergänzende Angaben zu Umsätzen** | | | |
| 33 | 42 | Lieferungen des ersten Abnehmers bei innergemeinschaftlichen Dreiecksgeschäften (§ 25b UStG) | Bemessungsgrundlage | keine | |
| 34 | 60 | Steuerpflichtige Umsätze, für die der Leistungsempfänger die Steuer nach § 13b Abs. 5 UStG schuldet | Bemessungsgrundlage | keine | |
| 35 | 21 | Nicht steuerbare sonstige Leistungen gemäß § 18b Satz 1 Nr. 2 UStG | Bemessungsgrundlage | keine | |
| 36 | 45 | Übrige nicht steuerbare Umsätze (Leistungsort nicht im Inland) | Bemessungsgrundlage | keine | |
| 37 | | *Umsatzsteuer: Summe der Zeilen 13 bis 18 und 25 bis 32* | Summe | | |
| | | **F. Abziehbare Vorsteuerbeträge und Berichtigung des Vorsteuerabzugs** | | | |
| 38 | 66 | Vorsteuer aus Rechnungen anderer Unternehmer (§ 15 Abs. 1 Satz 1 Nr. 1 UStG), aus Leistungen im Sinne des § 27 Abs. 40a UStG und aus Dreiecksgeschäften (§ 25b Abs. 5 UStG) | Steuer | mindert | |
| 39 | 61 | Vorsteuer aus dem innergemeinschaftlichen Erwerb von Gegenständen (§ 15 Abs. 1 Satz 1 Nr. 3 UStG) | Steuer | mindert | |
| 40 | 62 | Entstandene Einfuhrumsatzsteuer (§ 15 Abs. 1 Satz 1 Nr. 2 UStG) | Steuer | mindert | |
| 41 | 67 | Vorsteuer aus Leistungen im Sinne des § 13b UStG (§ 15 Abs. 1 Satz 1 Nr. 4 UStG) | Steuer | mindert | |
| 42 | 63 | Vorsteuer nach allgemeinen Durchschnittssätzen (§ 23a UStG) | Steuer | mindert | |
| 43 | 59 | Vorsteuerabzug für innergemeinschaftliche Lieferungen neuer Fahrzeuge außerhalb eines Unternehmens (§ 2a UStG) und von Kleinunternehmern (§ 15 Abs. 4a UStG) | Steuer | mindert | |
| 44 | 64 | Berichtigung des Vorsteuerabzugs (§ 15a UStG) | Steuer | mindert | |
| 45 | | *Verbleibender Betrag: Zeile 37 abzüglich der Zeilen 38 bis 44* | Summe | | |
| | | **G. Andere Steuerbeträge** | | | |
| 46 | 65 | Steuer infolge des Wechsels der Besteuerungsform sowie Nachsteuer auf versteuerte Anzahlungen u. Ä. wegen Steuersatzänderung | Steuer | erhöht | |
| 47 | 69 | In Rechnungen unrichtig oder unberechtigt ausgewiesene Steuer (§ 14c UStG) und weitere geschuldete Steuerbeträge | Steuer | erhöht | |
| | | **H. Vorauszahlung/Überschuss** | | | |
| 48 | | *Umsatzsteuer-Vorauszahlung/Überschuss: Summe der Zeilen 45 bis 47* | Summe | | |
| 49 | 39 | Abzug der festgesetzten Sondervorauszahlung für Dauerfristverlängerung | Steuer | mindert | |
| 50 | 83 | Verbleibende Umsatzsteuer-Vorauszahlung / verbleibender Überschuss | Steuer | keine (Ergebnis) | |
| | | **I. Ergänzende Angaben zu Minderungen nach § 17 Abs. 1 Sätze 1 und 2 i. V. m. Abs. 2 Nr. 1 Satz 1 UStG** | | | |
| 51 | 50 | Minderung der Bemessungsgrundlage (in den Zeilen 13 bis 18 enthalten) | Bemessungsgrundlage | keine | |
| 52 | 37 | Minderung der abziehbaren Vorsteuerbeträge (in Zeile 38 und in den Zeilen 42 und 43 enthalten) | Steuer | keine | |
| | | **J. Sonstige Angaben** | | | |
| 53 | 29 | Verrechnung des Erstattungsbetrags erwünscht / Erstattungsbetrag ist abgetreten | Kennzeichen | keine | |
| 54 | 26 | SEPA-Lastschriftmandat soll ausnahmsweise nicht verwendet werden | Kennzeichen | keine | |
| | | **Ergänzende Angaben zur Steueranmeldung** | | | |
| 55 | 500 | Ergänzende Angaben zur Steueranmeldung | Schlüssel | keine | |

Hinweise:

- Die Zeilen 37, 45 und 48 sind Summen, die der Vordruck selbst bildet. Sie tragen keine Kennzahl. Steuerbote liefert sie als `output_tax` (Zeile 37), `remaining_tax` (Zeile 45) und `prepayment` (Zeile 48). Zeilennummer und Kennzahl sind verschiedene Zahlen: Kz 37 steht in Zeile 52, Kz 45 in Zeile 36, Kz 48 in Zeile 23.
- Ein negativer Wert in Kz 83 ist ein Überschuss. Der Vordruck verlangt dafür ein Minuszeichen.
- Negative Werte sind überall möglich. Zu Zeile 44 schreibt die Anleitung: „Handelt es sich bei den Berichtigungsbeträgen um zurückzuzahlende Vorsteuerbeträge, tragen Sie bitte vor dem Betrag ein Minuszeichen ein.“ Ein negativer Betrag in Kz 64 mindert die Summe der Vorsteuer und erhöht damit Kz 83.
- Die Zeilen 1 bis 9 (Steuernummer, Wirtschafts-Identifikationsnummer, Finanzamt, Unternehmer, Voranmeldungszeitraum) sind Kopfdaten und keine Kennzahlen.
- Kz 500 nimmt einen der Schlüssel 1 bis 4 auf, die der Vordruck in Zeile 55 erklärt.

## Kontenzuordnung

### Modell

Die Zuordnung steht in [`mapping.py`](../steuerbote/ustva/mapping.py) und ist reine Datenhaltung:

- **`AccountRule`** ordnet ein Konto über seine Kontonummer einer Kennzahl zu und legt die Seite fest, auf der das Konto seinen Saldo trägt: Haben (`Side.CREDIT`) für Erlöse und andere Steuerbeträge, Soll (`Side.DEBIT`) für Erwerbe, bezogene Leistungen und Vorsteuer. Der Betrag ist der Saldo des Zeitraums auf dieser Seite. Eine Gutschrift auf einem Erlöskonto mindert also die Bemessungsgrundlage und kann sie negativ machen. Hat die Kennzahl eine eigene Steuer-Kennzahl (etwa Kz 46 mit Kz 47), kann die Regel einen Steuersatz tragen (`tax_rate`). Dann leitet Steuerbote die Steuer aus dem Grundlagenkonto ab: Saldo × Satz geht in die Steuer-Kennzahl.
- **`TaxCheck`** ist eine Verprobung mit einer Bezeichnung (`label`): Die Steuer, die zu den Grundlagenkonten gehört (`base_accounts`), wird mit der Steuer auf den Steuerkonten verglichen (`tax_accounts`, Seite standardmäßig Haben). Der Satz eines Grundlagenkontos ist der Satz seiner Regel oder, wenn sie keinen trägt, der Satz der Kennzahl im Vordruck.
- **`Mapping`** gehört zu genau einem Kontenrahmen und einem Jahr des Vordrucks (`year`, ohne Angabe das neueste) und enthält Regeln, Verprobungen und beobachtete Konten (`watched`). Beobachtet werden Konten, die zur Voranmeldung gehören oder gehören können, für die es aber noch keine Zuordnung gibt. Jedes beobachtete Konto (`WatchedAccount`) hat eine Stufe (`WatchLevel`): „Sperrt“ (`BLOCKING`) hält die Meldung an, sobald das Konto einen Saldo hat, „Hinweis“ (`HINT`) gibt dann nur einen Hinweis. Eine bloße Kontonummer wird auf der Stufe „Sperrt“ beobachtet, `watched_at(level)` nennt die Konten einer Stufe. `has_place(number)` sagt, ob ein Konto einen Platz hat: eine Regel, als Steuerkonto eine Verprobung oder einen Eintrag unter den beobachteten Konten. `for_year(year)` prüft dieselben Regeln gegen den Vordruck eines anderen Jahres, `default_mapping(chart, year)` liefert die Vorgabe eines Kontenrahmens für das Jahr des Zeitraums.

Eine Zuordnung prüft sich beim Anlegen selbst. Einen `MappingError` gibt es bei:

- einer Kontonummer, die kein nicht leerer Text ohne Leerzeichen am Rand ist, in Regeln, Verprobungen und beobachteten Konten,
- einer unbekannten Kennzahl, einer Kennzahl ohne Betrag (Kennzeichen, Datum, Schlüssel) oder Kz 83, die nur berechnet wird,
- einem doppelt zugeordneten Konto,
- einem Steuersatz an einer Regel, deren Kennzahl keine eigene Steuer-Kennzahl hat, etwa Kz 81 oder 66, oder einem Satz, der nicht endlich oder nicht zwischen 0 und 100 liegt,
- einer Bemessungsgrundlage mit eigener Steuer-Kennzahl (etwa Kz 46), deren Regeln teils mit, teils ohne Steuersatz sind, oder deren Steuer-Kennzahl nichts zufließt, weil weder die Regeln einen Satz tragen noch ein Steuerkonto der Steuer-Kennzahl zugeordnet ist,
- einer Verprobung ohne Bezeichnung, ohne Grundlagen- oder Steuerkonten, mit einem Grundlagenkonto ohne Regel oder ohne Steuersatz, mit einem Steuerkonto, das schon eine andere Verprobung prüft, oder mit einem Steuerkonto, das zugleich einer Kennzahl zugeordnet ist,
- einem beobachteten Konto, das zugleich zugeordnet oder verprobt ist oder zweimal beobachtet wird, auch auf zwei Stufen.

Ein Jahr, das keine ganze Zahl ist, ergibt einen `TypeError`. Für ein Jahr ohne Katalog gibt es stattdessen einen `UnknownYearError`.

Jede Firma soll die Vorgabe ihres Kontenrahmens in ihren Einstellungen anpassen können (geplant, Paket 1 der [Roadmap](roadmap.md)). Die Zuordnung arbeitet nur mit Kontonummern. Jeder andere Kontenrahmen, auch ein eigener, funktioniert deshalb, solange seine Konten Nummern tragen und eine Zuordnung dafür angelegt ist. Eine eigene Zuordnung darf die Steuer eines Paars wie Kz 46 und 47 auch direkt einem Steuerkonto zuordnen, statt sie abzuleiten.

### So rechnet `calculate()`

[`calculation.py`](../steuerbote/ustva/calculation.py) bekommt die Buchungszeilen eines Zeitraums, eine Zeile je Buchung und Konto, in Firmenwährung und in Cent, dazu eine Zuordnung. Was nicht zum Umsatz des Zeitraums gehört, lässt der Aufrufer weg: Buchungen, die ERPNext als storniert kennzeichnet, Eröffnungs- und Abschlussbuchungen und die Buchungen, mit denen die Steuerkonten gegenüber dem Finanzamt ausgeglichen werden. Mit „Unveränderliches Hauptbuch aktivieren“ in den Buchhaltungseinstellungen kennzeichnet ERPNext keine Buchung als storniert; dann gehen ein stornierter Beleg und seine Gegenbuchungen ein, siehe [Die Abfrage des Hauptbuchs](architektur.md#die-abfrage-des-hauptbuchs).

1. Soll, Haben und die Zahl der Buchungen werden je Konto summiert, dazu je Konto und Beleg, soweit die Zeilen einen Beleg nennen.
2. Jedes zugeordnete Konto gibt seinen Saldo auf seiner Seite an seine Kennzahl. Trägt die Regel einen Steuersatz, geht zusätzlich die Steuer an die Steuer-Kennzahl: je Beleg Saldo × Satz, auf Cent gerundet, über alle Belege summiert. Konten ohne Regel, etwa Bankkonten, gehen nicht ein.
3. Beträge ohne Konto kommen über `extra_values` dazu, etwa die Sondervorauszahlung in Kz 39. Unbekannte Kennzahlen, Kennzahlen ohne Betrag und Kz 83 werden abgelehnt.
4. Kennzahlen mit dem Betrag null entfallen. Jede andere hat ihren genauen Betrag (`amount`) und den gemeldeten Wert (`reported`) nach den Rundungsregeln.
5. Die Summen folgen dem Vordruck: Zeile 37 (`output_tax`), Zeilen 38 bis 44 (`input_tax`), Zeile 45 (`remaining_tax`), Zeilen 46 und 47 (`other_tax`), Zeile 48 (`prepayment`) und Kz 39 (`sondervorauszahlung`). Kz 83 ist Zeile 48 abzüglich Kz 39, auf Cent gerundet, und immer dabei.
6. Jede Verprobung ergibt ein `CheckResult` mit berechneter und gebuchter Steuer, Zahl der Buchungen, Toleranz, Differenz (gebucht minus berechnet) und der Liste der abweichenden Belege (`deviations`, je Beleg berechnete und gebuchte Steuer). `passed` ist wahr, wenn kein Beleg abweicht.
7. `unmapped` nennt die beobachteten Konten der Stufe „Sperrt“ mit Saldo, `hinted` die der Stufe „Hinweis“ mit Saldo, jeweils mit Soll und Haben des Zeitraums (`AccountBalance`). Keines davon geht in eine Kennzahl ein. `ready` ist erst wahr, wenn kein Konto der Stufe „Sperrt“ einen Saldo hat und alle Verprobungen aufgehen; ein Saldo auf der Stufe „Hinweis“ ändert daran nichts und ergibt an der Meldung den Hinweis `KONTO-BEOBACHTET` (siehe [Vorperiodenvergleich und Hinweise](architektur.md#vorperiodenvergleich-und-hinweise)).

Konten ohne Regel, die auch nicht beobachtet werden, fehlen in der Meldung, ohne dass ein Fehler entsteht. Für die Konten der Steuervorlagen einer Firma gibt es deshalb die [Prüfung der Steuervorlagen](#prüfung-der-steuervorlagen).

### Vorgaben

[`defaults.py`](../steuerbote/ustva/defaults.py) bringt Vorgaben für SKR03 und SKR04 mit. Sie decken drei Nummernkreise ab: die DATEV-Kontenrahmen in der Ausgabe für 2026, die Kontonummern der Vorlagen für SKR03 und SKR04, die ERPNext selbst mitbringt (`de_kontenplan_SKR03.json` und `de_kontenplan_SKR04.json`, Version 16), und Kontonummern aus verbreiteten SKR03-Varianten, die in der DATEV-Ausgabe 2026 nicht mehr stehen oder dort kein „U“ tragen (ältere DATEV-Ausgaben und Vorlagen von ERP-Systemen). Eine Firma, die mit einer solchen Vorlage angelegt ist, bucht auf deren Nummern, und einige davon führt der Kontenrahmen 2026 nicht mehr oder hält sie frei. Jedes Konto, das der Kontenrahmen an die Umsatzsteuer weitergibt, jedes Umsatzsteuerkonto einer Vorlage von ERPNext und jede dieser SKR03-Nummern hat darin genau einen Platz:

- **Zugeordnet:** Das Konto geht in die Kennzahl, die sich aus seiner Bezeichnung eindeutig ergibt. Dazu gehören auch die Vorsteuerkonten und die Konten für Kz 63, 65 und 69. Ein Forderungsverlust mindert die Bemessungsgrundlage und meldet die Minderung zusätzlich in Kz 50; die Tabellen zeigen das als „81, zusätzlich Kz 50“, und in Kz 50 geht der Saldo im Soll.
- **Verprobt:** Das Umsatzsteuerkonto zu einer Bemessungsgrundlage wird nie zugeordnet. Die Steuer folgt aus dem Grundlagenkonto, mit dem Satz der Kennzahl oder, bei § 13b UStG und bei neuen Fahrzeugen, mit dem Satz, den das Konto laut Bezeichnung trägt. Das gebuchte Steuerkonto wird dagegen verprobt.
- **Beobachtet:** Das Konto gehört zur Voranmeldung, seine Kennzahl ist aber noch nicht entschieden. Hat es im Zeitraum einen Saldo, ist die Meldung nicht bereit. Konten, deren Saldo nur in manchen Fällen in die Voranmeldung gehört, beobachten die Vorgaben auf der Stufe „Hinweis“: Ein Saldo darauf ergibt einen Hinweis, und die Meldung bleibt bereit (siehe [Beobachtete Konten mit Hinweis](#beobachtete-konten-mit-hinweis)).
- **Bewusst ohne Kennzahl:** Die Voranmeldung hat für das Konto keine Kennzahl, etwa für Zahlungen an das Finanzamt, für Umsatzsteuer aus dem OSS-Verfahren oder für einen Einkauf im Inland, von dem nur die Vorsteuer gemeldet wird. Diese Konten stehen in `SKR03_IGNORED` und `SKR04_IGNORED` und gehören nicht zur Zuordnung.

Ein Kontenbereich wie 8400 bis 8409 fasst Konten gleichen Zwecks zusammen. Die Kontenrahmen drucken ihn als „-09“ unter seinem ersten Konto und sagen: „Kontenbereiche werden nur weitergegeben, wenn sie im Standardkontenrahmen ausgewiesen sind (z. B. AM 8400-09)“. Jedes Konto eines Bereichs hat den Platz seines ersten Kontos. `SKR03_RANGES` und `SKR04_RANGES` führen die Bereiche, die Tabellen zeigen sie als „8400 bis 8409“. Bezeichnungen mit dem Zusatz „(ERPNext)“ stammen aus der Vorlage von ERPNext, solche mit dem Zusatz „(SKR03-Variante)“ aus einer verbreiteten SKR03-Variante, weil der Kontenrahmen 2026 die Nummer nicht oder ohne Bezeichnung führt.

[`test_completeness.py`](../steuerbote/ustva/tests/test_completeness.py) setzt das durch: Jedes Konto, das in der Spalte „Programmverbindung“ ein „U“ trägt (Weitergabe an das Programm Umsatzsteuererklärung), jedes Steuerkonto mit der Funktion S oder F in den Bereichen der Vor- und Umsatzsteuer (SKR03 15xx und 17xx, SKR04 14xx und 38xx), jedes Konto ihrer Kontenbereiche, jedes Umsatzsteuerkonto der Vorlagen von ERPNext und jede Nummer aus den SKR03-Varianten hat genau einen dieser Plätze, die Nummern der Varianten genau den, den ihre Bezeichnung ergibt. Die Kontonummern stehen in [`datev_2026.py`](../steuerbote/ustva/tests/fixtures/datev_2026.py), [`erpnext_v16.py`](../steuerbote/ustva/tests/fixtures/erpnext_v16.py) mit den Stichwörtern, nach denen die Konten der Vorlagen ausgewählt sind, und [`skr03_legacy_numbers.py`](../steuerbote/ustva/tests/fixtures/skr03_legacy_numbers.py). Wenige Konten aus keiner dieser Quellen haben trotzdem einen Platz: etwa 8320 bis 8329 für Lieferungen, die im anderen EU-Land steuerpflichtig sind, und 8331 für elektronische Dienstleistungen, beide in Kz 45; 3551 und 1390 (SKR04: 5551), die der Kontenrahmen 2026 ohne „U“ führt, bewusst ohne Kennzahl; und die sonstigen betrieblichen Erträge auf der Stufe „Hinweis“ (siehe [Beobachtete Konten mit Hinweis](#beobachtete-konten-mit-hinweis)). Der Test führt sie mit Grund auf. Kennzeichnet eine neue Ausgabe des Kontenrahmens ein weiteres Konto mit „U“, schlägt der Test fehl, bis das Konto seinen Platz hat.

An echten Buchungen geprüft sind die Konten des Testfalls `VerifiedMonthTest` (siehe [Beispiel](#beispiel)). Alle anderen Zuordnungen folgen den Bezeichnungen. Die Vorgabe SKR04 bildet SKR03 Rolle für Rolle nach: gleiche Kennzahl, gleiche Seite, gleicher Steuersatz, gleiche Verprobungen. Zu 8630 hat SKR04 kein Konto, zu 3852 aus der Vorlage von ERPNext hat SKR03 keines, siehe [Vorgabe SKR04](#vorgabe-skr04). [`test_defaults.py`](../steuerbote/ustva/tests/test_defaults.py) hält jede Regel, jede Verprobung und die Listen der beobachteten und der bewusst nicht zugeordneten Konten beider Vorgaben fest und prüft die Spiegelung. [`test_docs.py`](../steuerbote/ustva/tests/test_docs.py) prüft, dass die Tabellen auf dieser Seite genau den Code zeigen.

### Vorgabe SKR03

| Konto | Bezeichnung laut Kontenrahmen 2026 | Kz | Seite |
|---|---|---|---|
| 8400 bis 8409 | Erlöse 19 % USt | 81 | Haben |
| 8410 bis 8419 | Erlöse 19 % USt | 81 | Haben |
| 8449 | Erlöse aus im Inland steuerpflichtigen elektronischen Dienstleistungen 19 % USt | 81 | Haben |
| 2752 | Erlöse aus Vermietung und Verpachtung 19 % USt | 81 | Haben |
| 8519 | Provisionsumsätze 19 % USt | 81 | Haben |
| 8640 bis 8644 | Sonstige Erträge betrieblich und regelmäßig 19 % USt | 81 | Haben |
| 8801 bis 8806 | Erlöse aus Verkäufen Sachanlagevermögen 19 % USt (bei Buchverlust) | 81 | Haben |
| 8820 bis 8825 | Erlöse aus Verkäufen Sachanlagevermögen 19 % USt (bei Buchgewinn) | 81 | Haben |
| 8850 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens 19 % USt für § 4 Abs. 3 Satz 4 EStG | 81 | Haben |
| 8595 | Sachbezüge 19 % USt (Waren) | 81 | Haben |
| 8611 | Verrechnete sonstige Sachbezüge aus Fahrzeug-Gestellung 19 % USt | 81 | Haben |
| 8613 | Verrechnete sonstige Sachbezüge 19 % USt | 81 | Haben |
| 8910 bis 8913 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 19 % USt | 81 | Haben |
| 8920 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt | 81 | Haben |
| 8921 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Fahrzeug-Nutzung) | 81 | Haben |
| 8922 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Telefon-Nutzung) | 81 | Haben |
| 8925 bis 8927 | Unentgeltliche Erbringung einer sonstigen Leistung 19 % USt | 81 | Haben |
| 8935 bis 8937 | Unentgeltliche Zuwendung von Gegenständen 19 % USt | 81 | Haben |
| 8940 bis 8943 | Unentgeltliche Zuwendung von Waren 19 % USt | 81 | Haben |
| 8720 bis 8721 | Erlösschmälerungen 19 % USt | 81 | Haben |
| 8760 bis 8761 | Gewährte Boni 19 % USt | 81 | Haben |
| 8790 bis 8791 | Gewährte Rabatte 19 % USt | 81 | Haben |
| 8736 | Gewährte Skonti 19 % USt | 81 | Haben |
| 2406 | Forderungsverluste 19 % USt (übliche Höhe) | 81, zusätzlich Kz 50 | Haben |
| 2436 | Forderungsverluste 19 % USt (soweit unüblich hoch) | 81, zusätzlich Kz 50 | Haben |
| 1718 | Erhaltene, versteuerte Anzahlungen 19 % USt (Verbindlichkeiten) | 81 | Haben |
| 8196 | Erlöse aus Geldspielautomaten 19 % USt (SKR03-Variante) | 81 | Haben |
| 8579 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten 19 % USt (SKR03-Variante) | 81 | Haben |
| 8315 bis 8319 | Erlöse aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 8726 | Erlösschmälerungen aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 2408 | Forderungsverluste aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt (übliche Höhe) | 81, zusätzlich Kz 50 | Haben |
| 8748 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 8300 bis 8309 | Erlöse 7 % USt | 86 | Haben |
| 8334 | Erlöse 7 % USt | 86 | Haben |
| 8630 bis 8634 | Sonstige Erträge betrieblich und regelmäßig 7 % USt | 86 | Haben |
| 8591 | Sachbezüge 7 % USt (Waren) | 86 | Haben |
| 8915 bis 8916 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | Haben |
| 8917 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | Haben |
| 8930 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | Haben |
| 8931 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | Haben |
| 8932 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | Haben |
| 8933 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | Haben |
| 8945 bis 8946 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | Haben |
| 8947 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | Haben |
| 8710 bis 8711 | Erlösschmälerungen 7 % USt | 86 | Haben |
| 8750 bis 8751 | Gewährte Boni 7 % USt | 86 | Haben |
| 8780 bis 8781 | Gewährte Rabatte 7 % USt | 86 | Haben |
| 8731 | Gewährte Skonti 7 % USt | 86 | Haben |
| 2401 | Forderungsverluste 7 % USt (übliche Höhe) | 86, zusätzlich Kz 50 | Haben |
| 2431 | Forderungsverluste 7 % USt (soweit unüblich hoch) | 86, zusätzlich Kz 50 | Haben |
| 1711 | Erhaltene, versteuerte Anzahlungen 7 % USt (Verbindlichkeiten) | 86 | Haben |
| 8516 | Provisionsumsätze 7 % USt (SKR03-Variante) | 86 | Haben |
| 8576 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten 7 % USt (SKR03-Variante) | 86 | Haben |
| 8310 bis 8314 | Erlöse aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 8725 | Erlösschmälerungen aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 2403 | Forderungsverluste aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt (übliche Höhe) | 86, zusätzlich Kz 50 | Haben |
| 8746 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 8290 | Erlöse 0 % USt | 87 | Haben |
| 8719 | Erlösschmälerungen 0 % USt | 87 | Haben |
| 8734 | Gewährte Skonti 0 % USt | 87 | Haben |
| 1714 | Erhaltene, versteuerte Anzahlungen 0 % USt (Verbindlichkeiten) | 87 | Haben |
| 8100 bis 8104 | Steuerfreie Umsätze § 4 Nr. 8 ff. UStG | 48 | Haben |
| 8105 | Steuerfreie Umsätze nach § 4 Nr. 12 UStG (Vermietung und Verpachtung) | 48 | Haben |
| 8160 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend, § 4 UStG | 48 | Haben |
| 8165 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend | 48 | Haben |
| 8192 | Steuerfreie Erlöse Kleinunternehmer nach § 19 Abs. 1 UStG | 48 | Haben |
| 2751 | Erlöse aus Vermietung und Verpachtung, umsatzsteuerfrei § 4 Nr. 12 UStG | 48 | Haben |
| 8514 | Provisionsumsätze, steuerfrei § 4 Nr. 8 ff. UStG | 48 | Haben |
| 8851 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG | 48 | Haben |
| 8701 | Erlösschmälerungen für steuerfreie Umsätze nach § 4 Nr. 8 ff. UStG | 48 | Haben |
| 8703 | Erlösschmälerungen für sonstige steuerfreie Umsätze ohne Vorsteuerabzug | 48 | Haben |
| 8707 | Erlösschmälerungen für steuerfreie Umsätze nach § 19 Abs. 1 UStG | 48 | Haben |
| 8609 | Sonstige Erträge betrieblich und regelmäßig, steuerfrei § 4 Nr. 8 ff. UStG | 48 | Haben |
| 8852 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG und § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG | 48 | Haben |
| 8195 | Erlöse als Kleinunternehmer nach § 19 Abs. 1 UStG (SKR03-Variante) | 48 | Haben |
| 8574 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten, steuerfrei § 4 Nr. 8 ff. UStG (SKR03-Variante) | 48 | Haben |
| 8120 | Steuerfreie Umsätze nach § 4 Nr. 1a UStG | 43 | Haben |
| 8140 | Steuerfreie Umsätze Offshore usw. | 43 | Haben |
| 8150 | Sonstige steuerfreie Umsätze (z. B. § 4 Nr. 2 bis 7 UStG) | 43 | Haben |
| 8807 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchverlust) | 43 | Haben |
| 8827 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchgewinn) | 43 | Haben |
| 8515 | Provisionsumsätze, steuerfrei § 4 Nr. 5 UStG | 43 | Haben |
| 8625 bis 8629 | Sonstige betriebliche Erträge, steuerfrei z. B. § 4 Nr. 2 bis 7 UStG | 43 | Haben |
| 8702 | Erlösschmälerungen für steuerfreie Umsätze nach § 4 Nr. 2 bis 7 UStG | 43 | Haben |
| 8704 | Erlösschmälerungen für sonstige steuerfreie Umsätze mit Vorsteuerabzug | 43 | Haben |
| 8705 | Erlösschmälerungen aus steuerfreien Umsätzen § 4 Nr. 1a UStG | 43 | Haben |
| 8194 | Umsatzerlöse aus Reiseleistungen § 25 Abs. 2 UStG, steuerfrei | 43 | Haben |
| 8575 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten, steuerfrei § 4 Nr. 5 UStG (SKR03-Variante) | 43 | Haben |
| 8125 | Steuerfreie innergemeinschaftliche Lieferungen nach § 4 Nr. 1b UStG | 41 | Haben |
| 8808 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1b UStG (bei Buchverlust) | 41 | Haben |
| 8828 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1b UStG (bei Buchgewinn) | 41 | Haben |
| 8724 | Erlösschmälerungen aus steuerfreien innergemeinschaftlichen Lieferungen | 41 | Haben |
| 2402 | Forderungsverluste aus steuerfreien EU-Lieferungen (übliche Höhe) | 41 | Haben |
| 8743 | Gewährte Skonti aus steuerfreien innergemeinschaftlichen Lieferungen § 4 Nr. 1b UStG | 41 | Haben |
| 8135 | Steuerfreie innergemeinschaftliche Lieferungen von Neufahrzeugen an Abnehmer ohne USt-Id-Nr. | 44 | Haben |
| 8130 | Lieferungen des ersten Abnehmers bei innergemeinschaftlichen Dreiecksgeschäften § 25b Abs. 2 UStG | 42 | Haben |
| 8706 | Erlösschmälerungen für steuerfreie innergemeinschaftliche Dreiecksgeschäfte nach § 25b Abs. 2 und 4 UStG | 42 | Haben |
| 8338 | Erlöse aus im Drittland steuerbaren Leistungen, im Inland nicht steuerbare Umsätze | 45 | Haben |
| 8320 bis 8329 | Erlöse aus im anderen EU-Land steuerpflichtigen Lieferungen, im Inland nicht steuerbar | 45 | Haben |
| 8339 | Erlöse aus im anderen EU-Land steuerbaren Leistungen, im Inland nicht steuerbare Umsätze | 45 | Haben |
| 8331 | Erlöse aus im anderen EU-Land steuerpflichtigen elektronischen Dienstleistungen | 45 | Haben |
| 8727 | Erlösschmälerungen aus im anderen EU-Land steuerpflichtigen Lieferungen | 45 | Haben |
| 8336 | Erlöse aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen, für die der Leistungsempfänger die Umsatzsteuer schuldet | 21 | Haben |
| 8742 | Gewährte Skonti aus Erlösen aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen, für die der Leistungsempfänger die Umsatzsteuer schuldet | 21 | Haben |
| 8337 | Erlöse aus Leistungen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 8335 | Erlöse aus Lieferungen von Mobilfunkgeräten, Tablet-Computern, Spielekonsolen und integrierten Schaltkreisen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 8741 | Gewährte Skonti aus Leistungen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 8738 | Gewährte Skonti aus Lieferungen von Mobilfunkgeräten etc., für die der Leistungsempfänger die Umsatzsteuer nach § 13b Abs. 2 Nr. 10 UStG schuldet | 60 | Haben |
| 3425 bis 3429 | Innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3725 | Nachlässe aus innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3718 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3062 bis 3063 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3741 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3748 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3420 bis 3424 | Innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3724 | Nachlässe aus innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3717 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3060 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3743 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3746 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3435 | Innergemeinschaftlicher Erwerb ohne Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3430 | Innergemeinschaftlicher Erwerb ohne Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3066 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb ohne Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 3067 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb ohne Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 3440 | Innergemeinschaftlicher Erwerb von Neufahrzeugen von Lieferanten ohne USt-Id-Nr. 19 % Vorsteuer und 19 % Umsatzsteuer | 94, Steuer 19 % in Kz 96 | Soll |
| 3550 | Steuerfreier innergemeinschaftlicher Erwerb | 91 | Soll |
| 3123 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 46, Steuer 19 % in Kz 47 | Soll |
| 3143 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 46, Steuer 19 % in Kz 47 | Soll |
| 3113 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 46, Steuer 7 % in Kz 47 | Soll |
| 3133 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 46, Steuer 7 % in Kz 47 | Soll |
| 3125 bis 3126 | Leistungen eines im Ausland ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 3145 bis 3146 | Leistungen eines im Ausland ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 3120 bis 3121 | Bauleistungen eines im Inland ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 3140 bis 3141 | Bauleistungen eines im Inland ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 3115 | Leistungen eines im Ausland ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 3135 | Leistungen eines im Ausland ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 3110 | Bauleistungen eines im Inland ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 3130 | Bauleistungen eines im Inland ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 1570 | Abziehbare Vorsteuer | 66 | Soll |
| 1576 | Abziehbare Vorsteuer 19 % | 66 | Soll |
| 1571 | Abziehbare Vorsteuer 7 % | 66 | Soll |
| 1573 | Vorsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 66 | Soll |
| 1585 | Abziehbare Vorsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager | 66 | Soll |
| 1574 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb 19 % | 61 | Soll |
| 1572 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb | 61 | Soll |
| 1584 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen von Lieferanten ohne USt-Id-Nr. | 61 | Soll |
| 1588 | Entstandene Einfuhrumsatzsteuer | 62 | Soll |
| 1577 | Abziehbare Vorsteuer nach § 13b UStG 19 % | 67 | Soll |
| 1578 | Abziehbare Vorsteuer nach § 13b UStG | 67 | Soll |
| 1587 | Vorsteuer nach allgemeinen Durchschnittssätzen UStVA Kz. 63 (SKR03-Variante) | 63 | Soll |
| 1528 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 2 UStG | 64 | Soll |
| 1529 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 2 UStG | 64 | Soll |
| 1556 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | Soll |
| 1557 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | Soll |
| 1558 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | Soll |
| 1559 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | Soll |
| 1782 | Nachsteuer, UStVA Kz. 65 | 65 | Haben |
| 1783 | In Rechnung unrichtig oder unberechtigt ausgewiesene Steuerbeträge, UStVA Kz. 69 | 69 | Haben |
| 1794 | Umsatzsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 69 | Haben |

### Vorgabe SKR04

| Konto | Bezeichnung laut Kontenrahmen 2026 | Kz | Seite |
|---|---|---|---|
| 4400 bis 4409 | Erlöse 19 % USt | 81 | Haben |
| 4410 bis 4419 | Erlöse 19 % USt | 81 | Haben |
| 4449 | Erlöse aus im Inland steuerpflichtigen elektronischen Dienstleistungen 19 % USt | 81 | Haben |
| 4862 | Erlöse aus Vermietung und Verpachtung 19 % USt | 81 | Haben |
| 4569 | Provisionsumsätze 19 % USt | 81 | Haben |
| 4836 | Sonstige Erträge betrieblich und regelmäßig 19 % USt | 81 | Haben |
| 6885 | Erlöse aus Verkäufen Sachanlagevermögen 19 % USt (bei Buchverlust) | 81 | Haben |
| 4845 | Erlöse aus Verkäufen Sachanlagevermögen 19 % USt (bei Buchgewinn) | 81 | Haben |
| 4865 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens 19 % USt für § 4 Abs. 3 Satz 4 EStG | 81 | Haben |
| 4945 | Sachbezüge 19 % USt (Waren) | 81 | Haben |
| 4947 | Verrechnete sonstige Sachbezüge aus Fahrzeug-Gestellung 19 % USt | 81 | Haben |
| 4948 | Verrechnete sonstige Sachbezüge 19 % USt | 81 | Haben |
| 4620 bis 4626 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 19 % USt | 81 | Haben |
| 4640 bis 4644 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt | 81 | Haben |
| 4645 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Fahrzeug-Nutzung) | 81 | Haben |
| 4646 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Telefon-Nutzung) | 81 | Haben |
| 4660 bis 4666 | Unentgeltliche Erbringung einer sonstigen Leistung 19 % USt | 81 | Haben |
| 4686 bis 4687 | Unentgeltliche Zuwendung von Gegenständen 19 % USt | 81 | Haben |
| 4680 bis 4684 | Unentgeltliche Zuwendung von Waren 19 % USt | 81 | Haben |
| 4720 bis 4721 | Erlösschmälerungen 19 % USt | 81 | Haben |
| 4760 bis 4761 | Gewährte Boni 19 % USt | 81 | Haben |
| 4790 bis 4791 | Gewährte Rabatte 19 % USt | 81 | Haben |
| 4736 | Gewährte Skonti 19 % USt | 81 | Haben |
| 6936 | Forderungsverluste 19 % USt (übliche Höhe) | 81, zusätzlich Kz 50 | Haben |
| 6286 | Forderungsverluste 19 % USt (soweit unüblich hoch) | 81, zusätzlich Kz 50 | Haben |
| 3272 | Erhaltene, versteuerte Anzahlungen 19 % USt (Verbindlichkeiten) | 81 | Haben |
| 4186 | Erlöse aus Geldspielautomaten 19 % USt (ERPNext) | 81 | Haben |
| 4579 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten 19% USt (ERPNext) | 81 | Haben |
| 4315 bis 4319 | Erlöse aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 4726 | Erlösschmälerungen aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 6938 | Forderungsverluste aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt (übliche Höhe) | 81, zusätzlich Kz 50 | Haben |
| 4748 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt | 81 | Haben |
| 4300 bis 4309 | Erlöse 7 % USt | 86 | Haben |
| 4334 | Erlöse 7 % USt | 86 | Haben |
| 4941 | Sachbezüge 7 % USt (Waren) | 86 | Haben |
| 4610 bis 4615 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | Haben |
| 4616 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt | 86 | Haben |
| 4630 bis 4635 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | Haben |
| 4636 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt | 86 | Haben |
| 4650 bis 4655 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | Haben |
| 4656 | Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt | 86 | Haben |
| 4670 bis 4675 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | Haben |
| 4676 | Unentgeltliche Zuwendung von Waren 7 % USt | 86 | Haben |
| 4710 bis 4711 | Erlösschmälerungen 7 % USt | 86 | Haben |
| 4750 bis 4751 | Gewährte Boni 7 % USt | 86 | Haben |
| 4780 bis 4781 | Gewährte Rabatte 7 % USt | 86 | Haben |
| 4731 | Gewährte Skonti 7 % USt | 86 | Haben |
| 6931 | Forderungsverluste 7 % USt (übliche Höhe) | 86, zusätzlich Kz 50 | Haben |
| 6281 | Forderungsverluste 7 % USt (soweit unüblich hoch) | 86, zusätzlich Kz 50 | Haben |
| 3260 | Erhaltene, versteuerte Anzahlungen 7 % USt (Verbindlichkeiten) | 86 | Haben |
| 4566 | Provisionsumsätze 7% USt (ERPNext) | 86 | Haben |
| 4576 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten 7% USt (ERPNext) | 86 | Haben |
| 4310 bis 4314 | Erlöse aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 4725 | Erlösschmälerungen aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 6933 | Forderungsverluste aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt (übliche Höhe) | 86, zusätzlich Kz 50 | Haben |
| 4746 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt | 86 | Haben |
| 4290 | Erlöse 0 % USt | 87 | Haben |
| 4719 | Erlösschmälerungen 0 % USt | 87 | Haben |
| 4734 | Gewährte Skonti 0 % USt | 87 | Haben |
| 3264 | Erhaltene, versteuerte Anzahlungen 0 % USt (Verbindlichkeiten) | 87 | Haben |
| 4100 bis 4104 | Steuerfreie Umsätze § 4 Nr. 8 ff. UStG | 48 | Haben |
| 4105 | Steuerfreie Umsätze nach § 4 Nr. 12 UStG (Vermietung und Verpachtung) | 48 | Haben |
| 4160 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend, § 4 UStG | 48 | Haben |
| 4165 | Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend | 48 | Haben |
| 4184 | Steuerfreie Erlöse Kleinunternehmer nach § 19 Abs. 1 UStG | 48 | Haben |
| 4861 | Erlöse aus Vermietung und Verpachtung, umsatzsteuerfrei § 4 Nr. 12 UStG | 48 | Haben |
| 4564 | Provisionsumsätze, steuerfrei § 4 Nr. 8 ff. UStG | 48 | Haben |
| 4866 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG | 48 | Haben |
| 4701 | Erlösschmälerungen für steuerfreie Umsätze nach § 4 Nr. 8 ff. UStG | 48 | Haben |
| 4703 | Erlösschmälerungen für sonstige steuerfreie Umsätze ohne Vorsteuerabzug | 48 | Haben |
| 4707 | Erlösschmälerungen für steuerfreie Umsätze nach § 19 Abs. 1 UStG | 48 | Haben |
| 4841 | Sonstige Erträge betrieblich und regelmäßig, steuerfrei § 4 Nr. 8 ff. UStG | 48 | Haben |
| 4867 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG, § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG | 48 | Haben |
| 4185 | Erlöse aus Kleinunternehmer i. S. d. § 19 Abs. 1 UStG (ERPNext) | 48 | Haben |
| 4574 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten, steuerfrei § 4 Nr. 8ff UStG (ERPNext) | 48 | Haben |
| 4120 | Steuerfreie Umsätze nach § 4 Nr. 1a UStG | 43 | Haben |
| 4140 | Steuerfreie Umsätze Offshore etc. | 43 | Haben |
| 4150 | Sonstige steuerfreie Umsätze (z. B. § 4 Nr. 2 bis 7 UStG) | 43 | Haben |
| 6884 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchverlust) | 43 | Haben |
| 4844 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchgewinn) | 43 | Haben |
| 4565 | Provisionsumsätze, steuerfrei § 4 Nr. 5 UStG | 43 | Haben |
| 4842 | Sonstige betriebliche Erträge, steuerfrei z. B. § 4 Nr. 2 bis 7 UStG | 43 | Haben |
| 4702 | Erlösschmälerungen für steuerfreie Umsätze nach § 4 Nr. 2 bis 7 UStG | 43 | Haben |
| 4704 | Erlösschmälerungen für sonstige steuerfreie Umsätze mit Vorsteuerabzug | 43 | Haben |
| 4705 | Erlösschmälerungen aus steuerfreien Umsätzen § 4 Nr. 1a UStG | 43 | Haben |
| 4139 | Umsatzerlöse aus Reiseleistungen § 25 Abs. 2 UStG, steuerfrei | 43 | Haben |
| 4575 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten, steuerfrei § 4 Nr. 5 UStG (ERPNext) | 43 | Haben |
| 4125 | Steuerfreie innergemeinschaftliche Lieferungen nach § 4 Nr. 1b UStG | 41 | Haben |
| 6888 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1b UStG (bei Buchverlust) | 41 | Haben |
| 4848 | Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1b UStG (bei Buchgewinn) | 41 | Haben |
| 4724 | Erlösschmälerungen aus steuerfreien innergemeinschaftlichen Lieferungen | 41 | Haben |
| 6932 | Forderungsverluste aus steuerfreien EU-Lieferungen (übliche Höhe) | 41 | Haben |
| 4743 | Gewährte Skonti aus steuerfreien innergemeinschaftlichen Lieferungen § 4 Nr. 1b UStG | 41 | Haben |
| 4135 | Steuerfreie innergemeinschaftliche Lieferungen von Neufahrzeugen an Abnehmer ohne Umsatzsteuer-Identifikationsnummer | 44 | Haben |
| 4130 | Lieferungen des ersten Abnehmers bei innergemeinschaftlichen Dreiecksgeschäften § 25b Abs. 2 UStG | 42 | Haben |
| 4706 | Erlösschmälerungen für steuerfreie innergemeinschaftliche Dreiecksgeschäfte nach § 25b Abs. 2 und 4 UStG | 42 | Haben |
| 4338 | Erlöse aus im Drittland steuerbaren Leistungen, im Inland nicht steuerbare Umsätze | 45 | Haben |
| 4320 bis 4329 | Erlöse aus im anderen EU-Land steuerpflichtigen Lieferungen, im Inland nicht steuerbar | 45 | Haben |
| 4339 | Erlöse aus im anderen EU-Land steuerbaren Leistungen, im Inland nicht steuerbare Umsätze | 45 | Haben |
| 4331 | Erlöse aus im anderen EU-Land steuerpflichtigen elektronischen Dienstleistungen | 45 | Haben |
| 4727 | Erlösschmälerungen aus im anderen EU-Land steuerpflichtigen Lieferungen | 45 | Haben |
| 4336 | Erlöse aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen, für die der Leistungsempfänger die Umsatzsteuer schuldet | 21 | Haben |
| 4742 | Gewährte Skonti aus Erlösen aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen, für die der Leistungsempfänger die Umsatzsteuer schuldet | 21 | Haben |
| 4337 | Erlöse aus Leistungen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 4335 | Erlöse aus Lieferungen von Mobilfunkgeräten, Tablet-Computern, Spielekonsolen und integrierten Schaltkreisen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 4741 | Gewährte Skonti aus Leistungen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet | 60 | Haben |
| 4738 | Gewährte Skonti aus Lieferungen von Mobilfunkgeräten etc., für die der Leistungsempfänger die Umsatzsteuer nach § 13b Abs. 2 Nr. 10 UStG schuldet | 60 | Haben |
| 5425 bis 5429 | Innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5725 | Nachlässe aus innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5718 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5162 bis 5163 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5741 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5748 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5420 bis 5424 | Innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5724 | Nachlässe aus innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5717 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5160 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5743 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5746 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5435 | Innergemeinschaftlicher Erwerb ohne Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5430 | Innergemeinschaftlicher Erwerb ohne Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5166 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb ohne Vorsteuer und 7 % Umsatzsteuer | 93 | Soll |
| 5167 | Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb ohne Vorsteuer und 19 % Umsatzsteuer | 89 | Soll |
| 5440 | Innergemeinschaftlicher Erwerb von Neufahrzeugen von Lieferanten ohne Umsatzsteuer-Identifikationsnummer 19 % Vorsteuer und 19 % Umsatzsteuer | 94, Steuer 19 % in Kz 96 | Soll |
| 5550 | Steuerfreier innergemeinschaftlicher Erwerb | 91 | Soll |
| 5923 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 46, Steuer 19 % in Kz 47 | Soll |
| 5943 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 46, Steuer 19 % in Kz 47 | Soll |
| 5913 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 46, Steuer 7 % in Kz 47 | Soll |
| 5933 | Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 46, Steuer 7 % in Kz 47 | Soll |
| 5925 bis 5926 | Leistungen eines im Ausland ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 5945 bis 5946 | Leistungen eines im Ausland ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 5920 bis 5921 | Bauleistungen eines im Inland ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 5940 bis 5941 | Bauleistungen eines im Inland ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer | 84, Steuer 19 % in Kz 85 | Soll |
| 5915 | Leistungen eines im Ausland ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 5935 | Leistungen eines im Ausland ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 5910 | Bauleistungen eines im Inland ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 5930 | Bauleistungen eines im Inland ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer | 84, Steuer 7 % in Kz 85 | Soll |
| 1400 | Abziehbare Vorsteuer | 66 | Soll |
| 1406 | Abziehbare Vorsteuer 19 % | 66 | Soll |
| 1401 | Abziehbare Vorsteuer 7 % | 66 | Soll |
| 1436 | Vorsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 66 | Soll |
| 1431 | Abziehbare Vorsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager | 66 | Soll |
| 1404 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb 19 % | 61 | Soll |
| 1402 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb | 61 | Soll |
| 1432 | Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen von Lieferanten ohne USt-Identifikationsnummer | 61 | Soll |
| 1433 | Entstandene Einfuhrumsatzsteuer | 62 | Soll |
| 1407 | Abziehbare Vorsteuer nach § 13b UStG 19 % | 67 | Soll |
| 1408 | Abziehbare Vorsteuer nach § 13b UStG | 67 | Soll |
| 1484 | Vorsteuer nach allgemeinen Durchschnittssätzen UStVA Kz. 63 (ERPNext) | 63 | Soll |
| 1376 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 2 UStG | 64 | Soll |
| 1377 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 2 UStG | 64 | Soll |
| 1396 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | Soll |
| 1397 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter | 64 | Soll |
| 1398 | Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | Soll |
| 1399 | Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter | 64 | Soll |
| 3832 | Nachsteuer, UStVA Kz. 65 | 65 | Haben |
| 3851 | In Rechnung unrichtig oder unberechtigt ausgewiesene Steuerbeträge, UStVA Kz. 69 | 69 | Haben |
| 3819 | Umsatzsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts | 69 | Haben |
| 3852 | In Rechnung unrichtig oder unberechtigtausgewiesene Steuerbeträge, UStVA Kz. 69 (ERPNext) | 69 | Haben |

Zu 8630 (Sonstige Erträge betrieblich und regelmäßig 7 % USt) hat SKR04 kein Konto. 4835 heißt dort „Sonstige Erträge betrieblich und regelmäßig“, trägt kein „U“, nimmt Erträge ohne Umsatzsteuer auf und ist das Gegenstück zu SKR03 8605. Es hat deshalb in den Vorgaben keinen Platz. Die Konten 1484, 3852, 4185, 4186, 4566, 4574, 4575, 4576 und 4579 stammen aus der Vorlage von ERPNext. In SKR03 entsprechen ihnen 1587, 8195, 8196, 8516, 8574, 8575, 8576 und 8579 aus verbreiteten SKR03-Varianten; nur 3852 hat in SKR03 kein Gegenstück.

### Verprobungen

Beide Vorgaben verproben die gebuchte Umsatzsteuer auf der Haben-Seite der Steuerkonten:

| Verprobung | Grundlagen SKR03 | Grundlagen SKR04 | Steuerkonto SKR03 / SKR04 | Bezeichnung des Steuerkontos |
|---|---|---|---|---|
| Umsatzsteuer 19 % | 8400 bis 8409, 8410 bis 8419, 8449, 2752, 8519, 8640 bis 8644, 8801 bis 8806, 8820 bis 8825, 8850, 8595, 8611, 8613, 8910 bis 8913, 8920, 8921, 8922, 8925 bis 8927, 8935 bis 8937, 8940 bis 8943, 8720 bis 8721, 8760 bis 8761, 8790 bis 8791, 8736, 2406, 2436, 1718, 8196, 8579 | 4400 bis 4409, 4410 bis 4419, 4449, 4862, 4569, 4836, 6885, 4845, 4865, 4945, 4947, 4948, 4620 bis 4626, 4640 bis 4644, 4645, 4646, 4660 bis 4666, 4686 bis 4687, 4680 bis 4684, 4720 bis 4721, 4760 bis 4761, 4790 bis 4791, 4736, 6936, 6286, 3272, 4186, 4579 | 1776 / 3806 | Umsatzsteuer 19 % |
| Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 19 % | 8315 bis 8319, 8726, 2408, 8748 | 4315 bis 4319, 4726, 6938, 4748 | 1778 / 3808 | Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 19 % |
| Umsatzsteuer 7 % | 8300 bis 8309, 8334, 8630 bis 8634, 8591, 8915 bis 8916, 8917, 8930, 8931, 8932, 8933, 8945 bis 8946, 8947, 8710 bis 8711, 8750 bis 8751, 8780 bis 8781, 8731, 2401, 2431, 1711, 8516, 8576 | 4300 bis 4309, 4334, 4941, 4610 bis 4615, 4616, 4630 bis 4635, 4636, 4650 bis 4655, 4656, 4670 bis 4675, 4676, 4710 bis 4711, 4750 bis 4751, 4780 bis 4781, 4731, 6931, 6281, 3260, 4566, 4576 | 1771 / 3801 | Umsatzsteuer 7 % |
| Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 7 % | 8310 bis 8314, 8725, 2403, 8746 | 4310 bis 4314, 4725, 6933, 4746 | 1777 / 3807 | Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen |
| Umsatzsteuer aus innergemeinschaftlichem Erwerb 19 % | 3425 bis 3429, 3725, 3718, 3062 bis 3063, 3741, 3748 | 5425 bis 5429, 5725, 5718, 5162 bis 5163, 5741, 5748 | 1774 / 3804 | Umsatzsteuer aus innergemeinschaftlichem Erwerb 19 % |
| Umsatzsteuer aus innergemeinschaftlichem Erwerb 7 % | 3420 bis 3424, 3724, 3717, 3060, 3743, 3746 | 5420 bis 5424, 5724, 5717, 5160, 5743, 5746 | 1772 / 3802 | Umsatzsteuer aus innergemeinschaftlichem Erwerb |
| Umsatzsteuer aus innergemeinschaftlichem Erwerb ohne Vorsteuerabzug | 3430, 3435, 3066, 3067 | 5430, 5435, 5166, 5167 | 1779 / 3809 | Umsatzsteuer aus innergemeinschaftlichem Erwerb ohne Vorsteuerabzug |
| Umsatzsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen | 3440 | 5440 | 1784 / 3834 | Umsatzsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen von Lieferanten ohne Umsatzsteuer-Identifikationsnummer |
| Umsatzsteuer nach § 13b UStG 19 % | 3123, 3143, 3125 bis 3126, 3145 bis 3146, 3120 bis 3121, 3140 bis 3141 | 5923, 5943, 5925 bis 5926, 5945 bis 5946, 5920 bis 5921, 5940 bis 5941 | 1787 / 3837 | Umsatzsteuer nach § 13b UStG 19 % |
| Umsatzsteuer nach § 13b UStG 7 % | 3113, 3133, 3115, 3135, 3110, 3130 | 5913, 5933, 5915, 5935, 5910, 5930 | 1785 / 3835 | Umsatzsteuer nach § 13b UStG |

In SKR04 fehlt in der Verprobung „Umsatzsteuer 7 %“ das Gegenstück zu 8630. Die Erwerbe ohne Vorsteuerabzug, auch 3066 und 3067 (SKR04: 5166 und 5167), verprobt 1779 (SKR04: 3809), das Konto für deren Umsatzsteuer.

Die Steuer zu Kz 47, 85 und 96 kommt in den Vorgaben deshalb immer aus den Grundlagenkonten, nicht aus dem gebuchten Betrag auf 1787, 1785 oder 1784 (SKR04: 3837, 3835 oder 3834). Weicht die Buchung um mehr als die Toleranz ab, geht die Verprobung nicht auf, und die Meldung ist nicht bereit.

### Beobachtete Konten

Diese Konten gehören zur Voranmeldung, sind in den Vorgaben aber noch keiner Kennzahl zugeordnet. Die Vorgaben beobachten sie auf der Stufe „Sperrt“: Hat eines davon im Zeitraum einen Saldo, steht es in `unmapped`, und die Meldung ist nicht bereit, bis die Firma eine Zuordnung ergänzt hat. Auf 1548 und 1725 (SKR04: 1434 und 3865) ist ein Saldo eine Frage des Zeitpunkts: Vorsteuer, die erst in einem späteren Zeitraum abziehbar ist, und Umsatzsteuer, die erst später fällig wird. Die Firma klärt sie, bevor sie meldet.

| SKR03 | Bezeichnung laut Kontenrahmen 2026 |
|---|---|
| 1548 | Vorsteuer in Folgeperiode/im Folgejahr abziehbar |
| 1725 | Umsatzsteuer in Folgeperiode fällig (§§ 13 Abs. 1 Nr. 6 und 13b Abs. 2 UStG) |
| 1560 | Aufzuteilende Vorsteuer |
| 1561 | Aufzuteilende Vorsteuer 7 % |
| 1562 | Aufzuteilende Vorsteuer aus innergemeinschaftlichem Erwerb |
| 1563 | Aufzuteilende Vorsteuer aus innergemeinschaftlichem Erwerb 19 % |
| 1566 | Aufzuteilende Vorsteuer 19 % |
| 1567 | Aufzuteilende Vorsteuer nach §§ 13a und 13b UStG |
| 1569 | Aufzuteilende Vorsteuer nach §§ 13a und 13b UStG 19 % |
| 1712 | Erhaltene, versteuerte Anzahlungen 5 % USt (Verbindlichkeiten) |
| 1717 | Erhaltene, versteuerte Anzahlungen 16 % USt (Verbindlichkeiten) |
| 1760 | Umsatzsteuer nicht fällig |
| 1761 | Umsatzsteuer nicht fällig 7 % |
| 1762 | Umsatzsteuer nicht fällig aus im Inland steuerpflichtigen EU-Lieferungen |
| 1764 | Umsatzsteuer nicht fällig aus im Inland steuerpflichtigen EU-Lieferungen 19 % |
| 1766 | Umsatzsteuer nicht fällig 19 % |
| 1769 | Umsatzsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager |
| 1770 | Umsatzsteuer |
| 3075 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer |
| 3076 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer |
| 3151 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird 19 % Vorsteuer und 19 % Umsatzsteuer |
| 3154 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird ohne Vorsteuer, mit 19 % Umsatzsteuer |
| 3560 | Waren aus einem Umsatzsteuerlager, § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer |
| 3565 | Waren aus einem Umsatzsteuerlager, § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer |
| 8110 | Sonstige steuerfreie Umsätze Inland |
| 8190 | Erlöse, die mit den Durchschnittssätzen des § 24 UStG versteuert werden |
| 8198 | Umsatzerlöse nach § 25 UStG 19 % USt |
| 8199 | Umsatzerlöse nach § 25a UStG 19 % USt |
| 8189 | Umsatzerlöse nach § 25 UStG ohne USt |
| 8197 | Umsatzerlöse nach § 25a UStG ohne USt |
| 8200 | Erlöse |
| 8340 bis 8349 | Erlöse 16 % USt |
| 8649 | Sonstige Erträge betrieblich und regelmäßig 16 % USt |
| 8708 | Erlösschmälerungen für Umsätze nach § 25 UStG 19 % USt |
| 8709 | Erlösschmälerungen für Umsätze nach § 25a UStG 19 % USt |
| 1716 | Erhaltene Anzahlungen 15% MwSt. (SKR03-Variante) |
| 2400 | Forderungsverluste (übliche Höhe) |
| 2430 | Forderungsverluste (soweit unüblich hoch) |
| 3150 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird |
| 3153 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird ohne Vorsteuer aber mit Umsatzsteuer |
| 3160 | Leistungen nach § 13b UStG mit Vorsteuerabzug |
| 3165 | Leistungen nach § 13b UStG ohne Vorsteuerabzug |
| 3744 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb |
| 3745 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb |
| 8191 | Umsatzerlöse nach §§ 25 und 25a UStG 19 % USt |
| 8193 | Umsatzerlöse nach §§ 25 und 25a UStG ohne USt |
| 8499 | Nebenerlöse (Bezug zu Materialaufwand) |
| 8510 | Provisionsumsätze |
| 8520 | Erlöse Abfallverwertung |
| 8540 | Erlöse Leergut |
| 8570 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten |
| 8590 | Verrechnete sonstige Sachbezüge (keine Waren) |
| 8600 | Sonstige Erlöse betrieblich und regelmäßig (SKR03-Variante) |
| 8607 | Andere Nebenerlöse |
| 8610 | Verrechnete sonstige Sachbezüge |
| 8614 | Verrechnete sonstige Sachbezüge ohne Umsatzsteuer |
| 8700 | Erlösschmälerungen |
| 8730 | Gewährte Skonti |
| 8745 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen |
| 8769 | Gewährte Boni |
| 8770 | Gewährte Rabatte |
| 8800 | Erlöse aus Verkäufen Sachanlagevermögen (bei Buchverlust) |
| 8817 | Erlöse aus Verkäufen immaterieller Vermögensgegenstände (bei Buchverlust) |
| 8818 | Erlöse aus Verkäufen Finanzanlagen (bei Buchverlust) |
| 8819 | Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (bei Buchverlust) |
| 8829 | Erlöse aus Verkäufen Sachanlagevermögen (bei Buchgewinn) |
| 8837 | Erlöse aus Verkäufen immaterieller Vermögensgegenstände (bei Buchgewinn) |
| 8838 | Erlöse aus Verkäufen Finanzanlagen (bei Buchgewinn) |
| 8839 | Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG (bei Buchgewinn) |
| 8853 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens nach § 4 Abs 3 Satz 4 EStG |
| 8900 | Unentgeltliche Wertabgaben |
| 8955 | Umsatzsteuervergütungen nach § 24 UStG |

| SKR04 | Bezeichnung laut Kontenrahmen 2026 |
|---|---|
| 1434 | Vorsteuer in Folgeperiode/im Folgejahr abziehbar |
| 3865 | Umsatzsteuer in Folgeperiode fällig (§§ 13 Abs. 1 Nr. 6 und 13b Abs. 2 UStG) |
| 1410 | Aufzuteilende Vorsteuer |
| 1411 | Aufzuteilende Vorsteuer 7 % |
| 1412 | Aufzuteilende Vorsteuer aus innergemeinschaftlichem Erwerb |
| 1413 | Aufzuteilende Vorsteuer aus innergemeinschaftlichem Erwerb 19 % |
| 1416 | Aufzuteilende Vorsteuer 19 % |
| 1417 | Aufzuteilende Vorsteuer nach §§ 13a und 13b UStG |
| 1419 | Aufzuteilende Vorsteuer nach §§ 13a und 13b UStG 19 % |
| 3261 | Erhaltene, versteuerte Anzahlungen 5 % USt (Verbindlichkeiten) |
| 3270 | Erhaltene, versteuerte Anzahlungen 16 % USt (Verbindlichkeiten) |
| 3800 | Umsatzsteuer |
| 3810 | Umsatzsteuer nicht fällig |
| 3811 | Umsatzsteuer nicht fällig 7 % |
| 3812 | Umsatzsteuer nicht fällig aus im Inland steuerpflichtigen EU-Lieferungen |
| 3814 | Umsatzsteuer nicht fällig aus im Inland steuerpflichtigen EU-Lieferungen 19 % |
| 3816 | Umsatzsteuer nicht fällig 19 % |
| 3839 | Umsatzsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager |
| 5175 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer |
| 5176 | Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer |
| 5951 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird 19 % Vorsteuer und 19 % Umsatzsteuer |
| 5954 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird ohne Vorsteuer, mit 19 % Umsatzsteuer |
| 5560 | Waren aus einem Umsatzsteuerlager, § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer |
| 5565 | Waren aus einem Umsatzsteuerlager, § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer |
| 4110 | Sonstige steuerfreie Umsätze Inland |
| 4180 | Erlöse, die mit den Durchschnittssätzen des § 24 UStG versteuert werden |
| 4133 | Umsatzerlöse nach § 25 UStG 19 % USt |
| 4134 | Umsatzerlöse nach § 25a UStG 19 % USt |
| 4131 | Umsatzerlöse nach § 25 UStG ohne USt |
| 4132 | Umsatzerlöse nach § 25a UStG ohne USt |
| 4200 | Erlöse |
| 4340 bis 4349 | Erlöse 16 % USt |
| 4834 | Sonstige Erträge betrieblich und regelmäßig 16 % USt |
| 4708 | Erlösschmälerungen für Umsätze nach § 25 UStG 19 % USt |
| 4709 | Erlösschmälerungen für Umsätze nach § 25a UStG 19 % USt |
| 5744 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb |
| 4499 | Nebenerlöse (Bezug zu Materialaufwand) |
| 4869 | Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens nach § 4 Abs. 3 Satz 4 EStG |
| 4560 | Provisionsumsätze |
| 4570 | Sonstige Erträge aus Provisionen, Lizenzen und Patenten |
| 4949 | Verrechnete sonstige Sachbezüge ohne Umsatzsteuer |
| 3271 | Erhaltene, versteuerte Anz. 15 % USt (Verb.) (ERPNext) |
| 4136 | Umsatzerlöse nach §§ 25 und 25a UStG 19 % USt |
| 4138 | Umsatzerlöse nach §§ 25 und 25a UStG ohne USt |
| 4330 | Erlöse aus im Inland steuerpfl. EU-Lieferungen 16 % USt (ERPNext) |
| 4510 | Erlöse Abfallverwertung |
| 4520 | Erlöse Leergut |
| 4600 | Unentgeltliche Wertabgaben |
| 4695 | Umsatzsteuervergütungen nach § 24 UStG |
| 4700 | Erlösschmälerungen |
| 4723 | Erlösschmälerungen 16 % USt (ERPNext) |
| 4729 | Erlösschmälerungen aus im Inland steuerpfl. EU-Lieferungen 16 % USt (ERPNext) |
| 4730 | Gewährte Skonti |
| 4745 | Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen |
| 4769 | Gewährte Boni |
| 4770 | Gewährte Rabatte |
| 4833 | Andere Nebenerlöse |
| 4849 | Erlöse aus Verkäufen Sachanlagevermögen (bei Buchgewinn) |
| 4850 | Erlöse aus Verkäufen immaterieller Vermögensgegenstände (bei Buchgewinn) |
| 4851 | Erlöse aus Verkäufen Finanzanlagen (bei Buchgewinn) |
| 4852 | Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG (bei Buchgewinn) |
| 4940 | Verrechnete sonstige Sachbezüge (keine Waren) |
| 4946 | Verrechnete sonstige Sachbezüge |
| 5726 | Nachlässe aus innergem. Erwerb 16 % Vorsteuer und 16 % Umsatzsteuer (ERPNext) |
| 5727 | Nachlässe aus innergem. Erwerb 15 % Vorsteuer und 15 % Umsatzsteuer (ERPNext) |
| 5745 | Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb |
| 5950 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird |
| 5953 | Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird ohne Vorsteuer aber mit Umsatzsteuer |
| 5960 | Leistungen nach § 13b UStG mit Vorsteuerabzug |
| 5965 | Leistungen nach § 13b UStG ohne Vorsteuerabzug |
| 6280 | Forderungsverluste (soweit unüblich hoch) |
| 6285 | Forderungsverluste 16% USt (soweit unüblich hoch) (ERPNext) |
| 6287 | Forderungsverluste 15% USt (soweit unüblich hoch) (ERPNext) |
| 6889 | Erlöse aus Verkäufen Sachanlagevermögen (bei Buchverlust) |
| 6890 | Erlöse aus Verkäufen immaterieller Vermögensgegenstände (bei Buchverlust) |
| 6891 | Erlöse aus Verkäufen Finanzanlagen (bei Buchverlust) |
| 6892 | Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (bei Buchverlust) |
| 6930 | Forderungsverluste (übliche Höhe) |
| 6934 | Forderungsverluste aus im Inland steuerpfl. EU-Lieferungen 16 % USt (übliche Höhe) (ERPNext) |
| 6935 | Forderungsverluste 16% USt (übliche Höhe) (ERPNext) |
| 6937 | Forderungsverluste 15% USt (übliche Höhe) (ERPNext) |
| 6939 | Forderungsverluste aus im Inland steuerpfl. EU-Lieferungen 15% USt (übliche Höhe) (ERPNext) |

Die beiden Listen entsprechen sich Konto für Konto, mit zwei Ausnahmen: Nur in SKR03 steht 8600 aus einer verbreiteten SKR03-Variante. Nur in SKR04 stehen 4330, 4723, 4729, 5726, 5727, 6285, 6287, 6934, 6935, 6937 und 6939, Konten zu 15 und 16 % aus der Vorlage von ERPNext ohne Gegenstück in SKR03. 5744, 4499 und 4869 beobachtet SKR04 als Gegenstücke von 3744, 8499 und 8853, obwohl der Kontenrahmen sie ohne „U“ führt.

### Beobachtete Konten mit Hinweis

Diese Konten beobachten die Vorgaben auf der Stufe „Hinweis“: Ihr Saldo kann in die Voranmeldung gehören, meist gehört er nicht hinein. Hat eines davon im Zeitraum einen Saldo, steht es mit Soll und Haben in `hinted`, und die Meldung bekommt den Hinweis `KONTO-BEOBACHTET` mit Kontonummer, Bezeichnung, Soll, Haben und Saldo. Bereit bleibt sie trotzdem.

8603, 8605 und 8606 (SKR04: 4830, 4835 und 4832) sind sonstige betriebliche Erträge ohne „U“. Über der Kontenklasse druckt der Kontenrahmen 2026 für sie die Zusatzfunktion „Umsatzsteuer“: „M 8194-8603“ und „M 8605-8613“, in SKR04 „M 4830-4837“, erläutert unter „Zusatzfunktionen (über einer Kontenklasse)“ als „M Zusatzfunktion ‚Umsatzsteuer‘“. Auf diesen Konten lässt sich also mit Umsatzsteuer buchen, ohne dass der Kontenrahmen sie an die Umsatzsteuererklärung weitergibt. Steuerpflichtiges, das mit seiner Steuer darauf gebucht ist, zeigt die Verprobung, denn die Steuer steht dann ohne Grundlage auf 1776 oder 1771 (SKR04: 3806 oder 3801). Steuerfreies, etwa ein Umsatz nach § 4 Nr. 8 UStG für Kz 48, zeigt sie nicht; dafür steht der Hinweis.

| SKR03 | Bezeichnung laut Kontenrahmen 2026 |
|---|---|
| 8603 | Sonstige betriebliche Erträge |
| 8605 | Sonstige Erträge betrieblich und regelmäßig |
| 8606 | Sonstige betriebliche Erträge von verbundenen Unternehmen |

| SKR04 | Bezeichnung laut Kontenrahmen 2026 |
|---|---|
| 4830 | Sonstige betriebliche Erträge |
| 4835 | Sonstige Erträge betrieblich und regelmäßig |
| 4832 | Sonstige betriebliche Erträge von verbundenen Unternehmen |

In ihrer Kontenzuordnung setzt jede Firma jedes beobachtete Konto auf eine der beiden Stufen und kann weitere Konten beobachten. Die Stufe „Hinweis“ passt zu Konten, deren Einordnung die Steuerberatung noch klärt, etwa Erträge und Aufwendungen aus dem Handel mit Wertpapieren oder Devisen, Zinsen und Gebühren (siehe [Für die Steuerberatung zu klären](architektur.md#für-die-steuerberatung-zu-klären)). In den Vorgaben stehen solche Konten nicht: Der Kontenrahmen 2026 kennzeichnet etwa 2650, 2654, 2166 und 4970 weder mit „U“ noch mit der Zusatzfunktion „Umsatzsteuer“, und ob ihr Saldo in eine Kennzahl gehört, hängt von der Tätigkeit der Firma ab.

### Bewusst ohne Kennzahl

Diese Konten gibt der Kontenrahmen, eine Vorlage von ERPNext oder eine verbreitete SKR03-Variante an die Umsatzsteuer weiter, die Voranmeldung hat für sie aber keine Kennzahl. Die Vorgaben ordnen sie deshalb nicht zu und beobachten sie nicht. Sie stehen in `SKR03_IGNORED` und `SKR04_IGNORED`, damit `test_completeness.py` sie als entschieden kennt. Dazu gehören die Konten des OSS-Verfahrens, 1728, 1729, 1767, 1768 und 1798 (SKR04: 3798, 3817, 3818 und 3831): Ihre Umsatzsteuer erklärt die Firma dem Bundeszentralamt für Steuern, sie bekommt deshalb nie eine Kennzahl der Voranmeldung. Konten, auf denen ein Saldo nur eine Frage des Zeitpunkts ist, bleiben dagegen beobachtet (siehe [Beobachtete Konten](#beobachtete-konten)).

| SKR03 | Bezeichnung laut Kontenrahmen 2026 | Grund |
|---|---|---|
| 1543 | Forderungen an das Finanzamt aus abgeführtem Bauabzugsbetrag | Bauabzugsbetrag nach § 48 EStG, keine Umsatzsteuer |
| 1593 | Verrechnungskonto erhaltene Anzahlungen bei Buchung über Debitorenkonto | Verrechnungskonto. Die versteuerten Anzahlungen stehen auf 1711 bis 1718. |
| 1390 | Verrechnungskonto Ist-Versteuerung | Verrechnungskonto für die Ist-Versteuerung, im Kontenrahmen mit der Funktion F wie 1490 in SKR04 |
| 1728 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen elektronischen Dienstleistungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 1767 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen Lieferungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 1768 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen/Werklieferungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 1798 | Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen, nur OSS | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 1780 | Umsatzsteuer-Vorauszahlungen | Zahlung an das Finanzamt |
| 1781 | Umsatzsteuer-Vorauszahlungen 1/11 | Zahlung der Sondervorauszahlung an das Finanzamt. Die Sondervorauszahlung geht über `extra_values` in Kz 39 ein. |
| 3089 | Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 1794 in Kz 69, die Vorsteuer über 1573 in Kz 66. |
| 3552 | Erwerb 1. Abnehmer innerhalb eines Dreiecksgeschäftes | Dreiecksgeschäft, erster Abnehmer: Sein Erwerb gilt als besteuert (§ 25b Abs. 3 UStG) und wird nicht gemeldet. |
| 3553 | Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 1794 in Kz 69, die Vorsteuer über 1573 in Kz 66. |
| 3792 | Erhaltene Skonti aus Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 1794 in Kz 69, die Vorsteuer über 1573 in Kz 66. |
| 3793 | Erhaltene Skonti aus Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 1794 in Kz 69, die Vorsteuer über 1573 in Kz 66. |
| 0985 | Als Aufwand berücksichtigte Umsatzsteuer auf Anzahlungen | Umsatzsteuer auf Anzahlungen, in der Bilanz abgegrenzt |
| 1545 | Forderungen aus Umsatzsteuer-Vorauszahlungen | Verrechnung mit dem Finanzamt |
| 1789 | Umsatzsteuer laufendes Jahr | Verrechnung mit dem Finanzamt |
| 1790 | Umsatzsteuerverbindlichkeiten Vorjahr | Verrechnung mit dem Finanzamt |
| 1791 | Umsatzsteuerverbindlichkeiten frühere Jahre | Verrechnung mit dem Finanzamt |
| 1797 | Verbindlichkeiten aus Umsatzsteuer-Vorauszahlungen | Verrechnung mit dem Finanzamt |
| 1788 | Einfuhrumsatzsteuer aufgeschoben bis (SKR03-Variante) | Schuld an den Zoll für die aufgeschobene Einfuhrumsatzsteuer. Der Abzug läuft über 1588 in Kz 62. |
| 1729 | Steuerzahlungen aus im anderen EU-Land steuerpflichtigen Leistungen | OSS, nicht Teil der Voranmeldung |
| 4902 | Interimskonto für Aufwendungen in einem anderen Land, bei denen eine Vorsteuervergütung möglich ist | Vorsteuervergütung anderer Länder |
| 8604 | Erstattete Vorsteuer anderer Länder | Vorsteuervergütung anderer Länder |
| 1371 | Verrechnungskonto Gewinnermittlung § 4 Abs. 3 EStG, nicht ergebniswirksam | EÜR-Konto |
| 1372 | Wirtschaftsgüter des Umlaufvermögens nach § 4 Abs. 3 Satz 4 EStG | EÜR-Konto |
| 1445 | Forderungen aus Lieferungen und Leistungen zum allgemeinen Umsatzsteuersatz oder eines Kleinunternehmers (EÜR) | EÜR-Konto |
| 1446 | Forderungen aus Lieferungen und Leistungen zum ermäßigten Umsatzsteuersatz (EÜR) | EÜR-Konto |
| 1447 | Forderungen aus steuerfreien oder nicht steuerbaren Lieferungen und Leistungen (EÜR) | EÜR-Konto |
| 1448 | Forderungen aus Lieferungen und Leistungen nach Durchschnittssätzen nach § 24 UStG (EÜR) | EÜR-Konto |
| 1450 | Forderungen nach § 11 Abs. 1 Satz 2 EStG für § 4 Abs. 3 EStG | EÜR-Konto |
| 1580 | Gegenkonto Vorsteuer § 4 Abs. 3 EStG | EÜR-Konto |
| 1581 | Auflösung Vorsteuer aus Vorjahr § 4 Abs. 3 EStG | EÜR-Konto |
| 1582 | Vorsteuer aus Investitionen § 4 Abs. 3 EStG | EÜR-Konto |
| 1583 | Gegenkonto für Vorsteuer nach Durchschnittssätzen für § 4 Abs. 3 EStG (SKR03-Variante) | EÜR-Konto |
| 1605 | Verbindlichkeiten aus Lieferungen und Leistungen zum allgemeinen Umsatzsteuersatz (EÜR) | EÜR-Konto |
| 1606 | Verbindlichkeiten aus Lieferungen und Leistungen zum ermäßigten Umsatzsteuersatz (EÜR) | EÜR-Konto |
| 1607 | Verbindlichkeiten aus Lieferungen und Leistungen ohne Vorsteuerabzug (EÜR) | EÜR-Konto |
| 1624 | Verbindlichkeiten aus Lieferungen und Leistungen für Investitionen für § 4 Abs. 3 EStG | EÜR-Konto |
| 1704 | Sonstige Verbindlichkeiten nach § 11 Abs. 2 Satz 2 EStG für § 4 Abs. 3 EStG | EÜR-Konto |
| 1756 | Lohn- und Gehaltsverrechnung nach § 11 Abs. 2 Satz 2 EStG für § 4 Abs. 3 EStG | EÜR-Konto |
| 1795 | Verbindlichkeiten im Rahmen der sozialen Sicherheit für § 4 Abs. 3 EStG | EÜR-Konto |
| 8589 | Gegenkonto 8580-8582 bei Aufteilung der Erlöse nach Steuersätzen (EÜR) | EÜR-Konto |
| 2170 | Nicht abziehbare Vorsteuer | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 2171 | Nicht abziehbare Vorsteuer 7 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 2176 | Nicht abziehbare Vorsteuer 19 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 3600 bis 3609 | Nicht abziehbare Vorsteuer | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 3610 bis 3619 | Nicht abziehbare Vorsteuer 7 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 3660 bis 3669 | Nicht abziehbare Vorsteuer 19 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 4300 | Nicht abziehbare Vorsteuer | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 4301 | Nicht abziehbare Vorsteuer 7 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 4306 | Nicht abziehbare Vorsteuer 19 % | nicht abziehbare Vorsteuer, kein Vorsteuerabzug |
| 3109 | Fremdleistungen ohne Vorsteuer | Inlandseinkauf ohne Vorsteuer, keine Kennzahl |
| 3349 | Wareneingang ohne Vorsteuerabzug | Inlandseinkauf ohne Vorsteuer, keine Kennzahl |
| 1511 | Geleistete Anzahlungen, 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 1518 | Geleistete Anzahlungen, 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3010 bis 3019 | Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3030 bis 3039 | Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3070 | Einkauf Roh-, Hilfs- und Betriebsstoffe 5,5 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3071 | Einkauf Roh-, Hilfs- und Betriebsstoffe 7,8 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3091 | Energiestoffe (Fertigung) 7 % VSt | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3092 | Energiestoffe (Fertigung) 19 % VSt | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3106 | Fremdleistungen 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3108 | Fremdleistungen 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3300 bis 3309 | Wareneingang 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3400 bis 3409 | Wareneingang 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3505 bis 3509 | Wareneingang 5,5 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3540 bis 3549 | Wareneingang zum Durchschnittssatz nach § 24 UStG 7,8 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3710 bis 3711 | Nachlässe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3714 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3715 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3720 bis 3721 | Nachlässe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3730 | Erhaltene Skonti | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3731 | Erhaltene Skonti 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3733 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3734 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3736 | Erhaltene Skonti 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3738 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3750 bis 3751 | Erhaltene Boni 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3753 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3754 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3755 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3760 bis 3761 | Erhaltene Boni 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3769 | Erhaltene Boni | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3770 | Erhaltene Rabatte | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3780 bis 3781 | Erhaltene Rabatte 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3783 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3784 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3785 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3788 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 10,7 % Vorsteuer (SKR03-Variante) | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3790 bis 3791 | Erhaltene Rabatte 19 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3794 | Erhaltene Skonti 5,5 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3796 | Erhaltene Skonti 10,7 % Vorsteuer (SKR03-Variante) | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3798 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 5,5 % Vorsteuer | Inlandseinkauf: Die Bemessungsgrundlage hat keine Kennzahl, die Vorsteuer läuft über 1576, 1571 oder 1570. |
| 3551 | Wareneingang im Drittland steuerbar | Wareneingang im Drittland steuerbar, nichts zu melden: Die Lieferung ist im Inland nicht steuerbar (§ 1 Abs. 1 Nr. 1 UStG), die Einfuhrumsatzsteuer einer Einfuhr geht über 1588 in Kz 62. |
| 3557 | Wareneingang, steuerpflichtig im Drittland (7%) (SKR03-Variante) | wie 3551; der Kontenrahmen 2026 hält 3554 bis 3557 frei |
| 3558 | Wareneingang im anderen EU-Land steuerbar | Wareneingang im anderen EU-Land steuerbar, nichts zu melden |
| 3559 | Steuerfreie Einfuhren | steuerfreie Einfuhr, nichts zu melden |
| 8905 | Entnahme von Gegenständen ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8906 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8918 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt (Telefon-Nutzung) | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8919 | Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8924 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt (Fahrzeug-Nutzung) | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8929 | Unentgeltliche Erbringung einer sonstigen Leistung ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8939 | Unentgeltliche Zuwendung von Gegenständen ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8949 | Unentgeltliche Zuwendung von Waren ohne USt | Wertabgabe ohne Umsatzsteuer, nicht steuerbar (§ 3 Abs. 1b Satz 2 UStG) |
| 8950 | Nicht steuerbare Umsätze (Innenumsätze) | Innenumsätze, nicht steuerbar |
| 1710 | Erhaltene Anzahlungen auf Bestellungen (Verbindlichkeiten) | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1719 | Erhaltene Anzahlungen - Restlaufzeit bis 1 Jahr | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1720 | - Restlaufzeit 1 bis 5 Jahre | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1721 | - Restlaufzeit größer 5 Jahre | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1722 | Erhaltene Anzahlungen auf Bestellungen (von Vorräten offen abgesetzt) | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1793 | Verrechnungskonto geleistete Anzahlungen bei Buchung über Kreditorenkonto | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 1711, 1714 und 1718. |
| 1800 | Privatentnahmen allgemein | Privat- oder Kapitalkonto, nur Einzelunternehmen |
| 1880 | Unentgeltliche Wertabgaben | Privat- oder Kapitalkonto, nur Einzelunternehmen |
| 1869 | Grundstücksaufwand (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen) 10)22) | Privat- oder Kapitalkonto, nur Einzelunternehmen |
| 1879 | Grundstücksertrag (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen) 10)22) | Privat- oder Kapitalkonto, nur Einzelunternehmen |
| 1900 | Auszahlungen allgemein (Teilhafter), Fremdkapital | Konto eines Teilhafters |
| 1980 | Unentgeltliche Wertabgaben (Teilhafter), Fremdkapital | Konto eines Teilhafters |
| 8650 | Erlöse Zinsen und Diskontspesen | von DATEV nicht als umsatzsteuerrelevant gekennzeichnet, Zinserlöse laufen über 2650 |
| 8660 | Erlöse Zinsen und Diskontspesen aus verbundenen Unternehmen | von DATEV nicht als umsatzsteuerrelevant gekennzeichnet, Zinserlöse laufen über 2650 |

| SKR04 | Bezeichnung laut Kontenrahmen 2026 | Grund |
|---|---|---|
| 1456 | Forderungen an das Finanzamt aus abgeführtem Bauabzugsbetrag | Bauabzugsbetrag nach § 48 EStG, keine Umsatzsteuer |
| 1495 | Verrechnungskonto erhaltene Anzahlungen bei Buchung über Debitorenkonto | Verrechnungskonto. Die versteuerten Anzahlungen stehen auf 3260 bis 3272. |
| 3798 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen elektronischen Dienstleistungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 3817 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen Lieferungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 3818 | Umsatzsteuer aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen/Werklieferungen | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 3831 | Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen, nur OSS | OSS-Verfahren: Diese Umsatzsteuer wird dem Bundeszentralamt für Steuern erklärt, nicht in der Voranmeldung. |
| 3820 | Umsatzsteuer-Vorauszahlungen | Zahlung an das Finanzamt |
| 3830 | Umsatzsteuer-Vorauszahlungen 1/11 | Zahlung der Sondervorauszahlung an das Finanzamt. Die Sondervorauszahlung geht über `extra_values` in Kz 39 ein. |
| 5189 | Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 3819 in Kz 69, die Vorsteuer über 1436 in Kz 66. |
| 5552 | Erwerb 1. Abnehmer innerhalb eines Dreiecksgeschäftes | Dreiecksgeschäft, erster Abnehmer: Sein Erwerb gilt als besteuert (§ 25b Abs. 3 UStG) und wird nicht gemeldet. |
| 5553 | Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 3819 in Kz 69, die Vorsteuer über 1436 in Kz 66. |
| 5792 | Erhaltene Skonti aus Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 3819 in Kz 69, die Vorsteuer über 1436 in Kz 66. |
| 5793 | Erhaltene Skonti aus Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer | Dreiecksgeschäft, letzter Abnehmer: Die Bemessungsgrundlage wird nicht gemeldet. Die Steuer geht über 3819 in Kz 69, die Vorsteuer über 1436 in Kz 66. |
| 5909 | Fremdleistungen ohne Vorsteuer | Inlandseinkauf ohne Vorsteuer, keine Kennzahl |
| 1427 | Forderungen aus entrichteten Verbrauchsteuern | Verbrauchsteuer, keine Umsatzsteuer |
| 1460 | Geldtransit | Geldtransit, keine Umsatzsteuer |
| 1486 | Verrechnungskonto für Gewinnermittlung § 4 Abs. 3 EStG, nicht ergebniswirksam | Verrechnungskonto für die Gewinnermittlung nach § 4 Abs. 3 EStG |
| 1490 | Verrechnungskonto Ist-Versteuerung | Verrechnungskonto für die Ist-Versteuerung |
| 1491 | Neutralisierung ertragswirksamer Sachverhalte für § 4 Abs. 3 EStG | Neutralisierung für die Gewinnermittlung nach § 4 Abs. 3 EStG |
| 1420 | Forderungen aus Umsatzsteuer-Vorauszahlungen | Forderung an das Finanzamt |
| 1421 | Umsatzsteuerforderungen laufendes Jahr (ERPNext) | Forderung an das Finanzamt |
| 1422 | Umsatzsteuerforderungen Vorjahr | Forderung an das Finanzamt |
| 1425 | Umsatzsteuerforderungen frühere Jahre | Forderung an das Finanzamt |
| 1930 | Als Aufwand berücksichtigte Umsatzsteuer auf Anzahlungen | Umsatzsteuer auf Anzahlungen, in der Bilanz abgegrenzt |
| 3850 | Einfuhrumsatzsteuer aufgeschoben bis (ERPNext) | Schuld an den Zoll für die aufgeschobene Einfuhrumsatzsteuer. Der Abzug läuft über 1433 in Kz 62. |
| 4605 | Entnahme von Gegenständen ohne USt | ohne Umsatzsteuer, nichts zu melden |
| 4637 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt | ohne Umsatzsteuer, nichts zu melden |
| 4638 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt (Telefon-Nutzung) | ohne Umsatzsteuer, nichts zu melden |
| 4639 | Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt (Fahrzeug-Nutzung) | ohne Umsatzsteuer, nichts zu melden |
| 4659 | Unentgeltliche Erbringung einer sonstigen Leistung ohne USt | ohne Umsatzsteuer, nichts zu melden |
| 4679 | Unentgeltliche Zuwendung von Waren ohne USt | ohne Umsatzsteuer, nichts zu melden |
| 4689 | Unentgeltliche Zuwendung von Gegenständen ohne USt | ohne Umsatzsteuer, nichts zu melden |
| 4690 | Nicht steuerbare Umsätze (Innenumsätze) | Innenumsätze werden nicht gemeldet (Anleitung zu Zeile 36) |
| 4838 | Erstattete Vorsteuer anderer Länder | Vorsteuer anderer Staaten, nicht Teil der Voranmeldung |
| 6302 | Interimskonto für Aufwendungen in einem anderen Land, bei denen eine Vorsteuervergütung möglich ist | Vorsteuer anderer Staaten, nicht Teil der Voranmeldung |
| 1181 | Geleistete Anzahlungen 7 % Vorsteuer | Geleistete Anzahlung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 1184 | Geleistete Anzahlungen, 16 % Vorsteuer | Geleistete Anzahlung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 1185 | Geleistete Anz., 15 % Vorsteuer (ERPNext) | Geleistete Anzahlung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 1186 | Geleistete Anzahlungen 19 % Vorsteuer | Geleistete Anzahlung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5110 bis 5119 | Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5130 bis 5139 | Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5170 | Einkauf Roh-, Hilfs- und Betriebsstoffe 5,5 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5171 | Einkauf Roh-, Hilfs- und Betriebsstoffe 7,8 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5191 | Energiestoffe (Fertigung) 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5192 | Energiestoffe (Fertigung) 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5300 bis 5309 | Wareneingang 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5400 bis 5409 | Wareneingang 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5505 bis 5509 | Wareneingang 5,5 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5540 bis 5549 | Wareneingang zum Durchschnittssatz nach § 24 UStG 7,8 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5710 bis 5711 | Nachlässe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5714 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5715 | Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5720 bis 5721 | Nachlässe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5722 | Nachlässe 16 % Vorsteuer (ERPNext) | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5723 | Nachlässe 15 % Vorsteuer (ERPNext) | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5730 | Erhaltene Skonti | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5731 | Erhaltene Skonti 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5733 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5734 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5736 | Erhaltene Skonti 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5738 | Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5750 bis 5751 | Erhaltene Boni 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5753 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5754 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5755 | Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5760 bis 5761 | Erhaltene Boni 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5769 | Erhaltene Boni | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5770 | Erhaltene Rabatte | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5780 bis 5781 | Erhaltene Rabatte 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5783 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5784 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5785 | Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5790 bis 5791 | Erhaltene Rabatte 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5906 | Fremdleistungen 19 % Vorsteuer | Einkauf im Inland oder seine Minderung: Gemeldet wird nur die Vorsteuer, über deren Konten (Kz 66). |
| 5551 | Wareneingang im Drittland steuerbar | im Drittland steuerbar, nichts zu melden: Die Lieferung ist im Inland nicht steuerbar (§ 1 Abs. 1 Nr. 1 UStG), die Einfuhrumsatzsteuer einer Einfuhr geht über 1433 in Kz 62. |
| 5558 | Wareneingang im anderen EU-Land steuerbar | im anderen EU-Land steuerbar, nichts zu melden |
| 5559 | Steuerfreie Einfuhren | steuerfreie Einfuhr, nichts zu melden |
| 5600 bis 5609 | Nicht abziehbare Vorsteuer | nicht abziehbare Vorsteuer, ein Aufwand |
| 5610 bis 5619 | Nicht abziehbare Vorsteuer 7 % | nicht abziehbare Vorsteuer, ein Aufwand |
| 5660 bis 5669 | Nicht abziehbare Vorsteuer 19 % | nicht abziehbare Vorsteuer, ein Aufwand |
| 6871 | Nicht abziehbare Vorsteuer 19 % | nicht abziehbare Vorsteuer, ein Aufwand |
| 1190 | Erhaltene Anzahlungen auf Bestellungen (von Vorräten offen abgesetzt) | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |
| 3250 | Erhaltene Anzahlungen auf Bestellungen (Verbindlichkeiten) | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |
| 3280 | Erhaltene Anzahlungen – Restlaufzeit bis 1 Jahr | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |
| 3284 | – Restlaufzeit 1 bis 5 Jahre | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |
| 3285 | – Restlaufzeit größer 5 Jahre | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |
| 3695 | Verrechnungskonto geleistete Anzahlungen bei Buchung über Kreditorenkonto | Anzahlung ohne Automatikfunktion. Die versteuerten Anzahlungen laufen über 3260, 3264 und 3272. |

Nur in SKR04 stehen 1427, das dort ein „U“ trägt, und die Verrechnungskonten 1460 und 1491, die SKR04 mit der Funktion F im Bereich 14xx führt. In SKR03 trägt das Gegenstück 1547 kein „U“, und 1360 und 1391 liegen im Bereich 13xx, außerhalb der Bereiche der Vor- und Umsatzsteuer. Dort liegt auch 1390, das Gegenstück von 1490; es steht trotzdem in beiden Vorgaben, denn SKR03 führt es ebenso mit der Funktion F („F 1390 Verrechnungskonto Ist-Versteuerung“). Das Gegenstück von 1486 ist 1371, das SKR03 bei den EÜR-Konten führt. Die übrigen Konten nur einer Vorgabe stammen aus den Vorlagen von ERPNext oder aus verbreiteten SKR03-Varianten. 3798 und 4300 bis 4306 haben in den beiden Vorgaben verschiedene Bedeutungen: In SKR03 sind es Konten älterer Ausgaben für Skonti und nicht abziehbare Vorsteuer, in SKR04 das Konto des OSS-Verfahrens und die Erlöse zu 7 %.

### Beispiel

Der Testfall `VerifiedMonthTest` in [`test_calculation.py`](../steuerbote/ustva/tests/test_calculation.py) hält das an echten Buchungen geprüfte Verhalten fest (SKR03):

| Konto | Soll | Haben | Geht ein in |
|---|---|---|---|
| 8400 | | 1.000,00 | Kz 81, Grundlage der Verprobung „Umsatzsteuer 19 %“ |
| 1776 | | 190,00 | Steuerkonto der Verprobung „Umsatzsteuer 19 %“ |
| 8336 | | 2.000,00 | Kz 21 |
| 8338 | | 500,00 | Kz 45 |
| 3123 | 300,00 | | Kz 46, daraus Kz 47 mit 19 % |
| 1787 | | 57,00 | Steuerkonto der Verprobung „Umsatzsteuer nach § 13b UStG 19 %“ |
| 1577 | 57,00 | | Kz 67 |
| 1576 | 95,00 | | Kz 66 |

Ergebnis: Kz 81 = 1.000, Kz 21 = 2.000, Kz 45 = 500, Kz 46 = 300, Kz 47 = 57,00, Kz 66 = 95,00 und Kz 67 = 57,00. Zeile 37 ergibt 247,00 (190,00 aus Kz 81 und 57,00 aus Kz 47), die Zeilen 38 bis 44 ergeben 152,00, Zeile 45 und Zeile 48 je 95,00 und Kz 83 = 95,00. Beide Verprobungen mit Buchungen gehen auf den Cent auf, kein beobachtetes Konto hat einen Saldo, die Meldung ist bereit.

### Noch nicht zugeordnet

Diesen Kennzahlen ordnen die Vorgaben bewusst kein Konto zu:

| Kennzahlen | Fälle |
|---|---|
| 35/36 | Umsätze zu anderen Steuersätzen |
| 77, 76/80 | Land- und Forstwirtschaft nach § 24 UStG |
| 49 | innergemeinschaftliche Lieferungen neuer Fahrzeuge außerhalb eines Unternehmens (§ 2a UStG) |
| 90, 95/98 | innergemeinschaftliche Erwerbe zu 0 % und zu anderen Steuersätzen |
| 73/74 | Umsätze, die unter das GrEStG fallen |
| 59 | Vorsteuerabzug nach § 15 Abs. 4a UStG |
| 37 | Minderung der abziehbaren Vorsteuer nach § 17 UStG |
| 39 | Sondervorauszahlung: kommt nicht von einem Konto, sondern über `extra_values` |

Kz 63 (Vorsteuer nach allgemeinen Durchschnittssätzen, § 23a UStG) geht auf 1587 aus verbreiteten SKR03-Varianten und 1484 aus der Vorlage von ERPNext. Kz 50 bekommen die Forderungsverluste zusätzlich zu ihrer Bemessungsgrundlage, denn die Anleitung zu Zeile 51 sagt: „Erfolgt die Änderung nach § 17 Absatz 2 Nummer 1 Satz 1 UStG, weil das vereinbarte Entgelt für einen steuerpflichtigen Umsatz uneinbringlich geworden ist, tragen Sie die Minderung der Bemessungsgrundlage bitte zusätzlich in Zeile 51 ein.“ Kennzeichen, Datum und Schlüssel (Kz 10, 22, 70, 29, 26 und 500) nehmen kein Konto auf, Kz 83 wird berechnet.

Wer einen dieser Fälle hat, klärt Konto und Kennzahl mit der Steuerberatung und ergänzt die Zuordnung der eigenen Firma (Einstellungen geplant, Paket 1 der Roadmap). In die Vorgaben kommt eine Kennzahl erst, wenn Konto und Kennzahl bestätigt sind und eine Quelle dafür vorliegt, nach dem Ablauf in [CONTRIBUTING.md](../CONTRIBUTING.md).

### Prüfung der Steuervorlagen

ERPNext bucht die Steuer einer Rechnung auf die Konten ihrer Steuervorlagen: die Konten der Zeilen einer Vorlage für Verkaufs- oder Einkaufssteuern und die Konten der Steuersätze einer Artikelsteuervorlage. Die Voranmeldung enthält „die Steuer für den Voranmeldungszeitraum“ (§ 18 Absatz 1 Satz 1 UStG), ein Konto ohne Platz in der Zuordnung aber geht in keine Kennzahl ein. [`tax_templates.py`](../steuerbote/ustva/tax_templates.py) nennt deshalb jedes Konto der Steuervorlagen einer Firma, das weder zugeordnet noch verprobt noch beobachtet ist:

- **Bewusst ohne Kennzahl** bleiben außen vor: die Konten von `SKR03_IGNORED` und `SKR04_IGNORED` samt ihrer Kontenbereiche, wenn die Kontenzuordnung diesen Kontenrahmen nennt (`deliberately_without_kennzahl` in `defaults.py`). Dazu gehört die Umsatzsteuer des OSS-Verfahrens, die die Firma in der Steuererklärung des besonderen Besteuerungsverfahrens erklärt (§ 18j Absatz 4 UStG), nicht in der Voranmeldung.
- **Ohne Kontonummer** hat ein Konto nie einen Platz, denn die Zuordnung arbeitet mit Kontonummern.
- **Je Konto** sagt der Hinweis `STEUERVORLAGE-OHNE-KENNZAHL` an der Meldung, aus welchen Vorlagen das Konto kommt und ob es im Zeitraum einen Saldo hat, mit Soll und Haben. Er hält die Meldung nicht an.

In der Kontenzuordnung nennt „Steuervorlagen prüfen“ dieselben Konten und nimmt sie auf Wunsch in einem Schritt als beobachtete Konten der Stufe „Sperrt“ auf. Ein Saldo auf einem von ihnen hält die Meldung dann an, bis das Konto eine Zuordnung hat. Wie die Frappe-Schicht die Vorlagen liest, steht in [Architektur](architektur.md#prüfung-der-steuervorlagen).

## Ist-Versteuerung

Steuerbote rechnet die Voranmeldung nach vereinbarten Entgelten (§ 16 Abs. 1 Satz 1 UStG, Soll-Versteuerung); in den Einstellungen kennt „Besteuerung“ (`taxation_type`) nur „Soll“. Dieser Abschnitt schätzt ein, was die Berechnung nach vereinnahmten Entgelten (Ist-Versteuerung) ändert, wie eine Buchhaltung sie buchen müsste, was ERPNext 16 dafür mitbringt und was Steuerbote bräuchte. Umgesetzt ist davon nichts. Die Quellen stehen am Ende des Abschnitts als [I1] bis [I12], alle am 20. November 2026 gelesen; was sie nicht belegen, steht unter [Offen zur Ist-Versteuerung](#offen-zur-ist-versteuerung).

**Heute ist Steuerbote für Ist-Versteuerer nicht geeignet.** Bucht ein Unternehmen die Steuer seiner Rechnungen auf die nicht fälligen Konten, wie es die Ist-Versteuerung verlangt, hält die Meldung an, denn die Vorgaben beobachten diese Konten (siehe [Beobachtete Konten](#beobachtete-konten)). Bucht es sie gleich auf die fälligen Konten, meldet Steuerbote die Umsätze im Zeitraum der Rechnung statt der Zahlung, ohne es zu bemerken.

### Was § 20 UStG ändert

- **Wer.** Das Finanzamt kann auf Antrag gestatten, die Steuer „nicht nach den vereinbarten Entgelten (§ 16 Abs. 1 Satz 1), sondern nach den vereinnahmten Entgelten“ zu berechnen: wenn der Gesamtumsatz im vorangegangenen Kalenderjahr „nicht mehr als 800 000 Euro betragen hat“, wenn der Unternehmer nach § 148 AO von der Buchführungspflicht befreit ist, soweit er Umsätze aus einem freien Beruf im Sinne des § 18 Abs. 1 Nr. 1 EStG ausführt, oder wenn er eine juristische Person des öffentlichen Rechts ist, soweit sie weder freiwillig noch gesetzlich verpflichtet Bücher führt (§ 20 Satz 1 UStG [I1]). Die Gestattung „erstreckt sich wegen des Prinzips der Abschnittsbesteuerung stets auf das volle Kalenderjahr“; für freie Berufe wird sie nicht erteilt, „wenn der Unternehmer für die in der Vorschrift genannten Umsätze Bücher führt“ (UStAE 20.1 Abs. 1 Satz 4 und 7 [I5]).
- **Wann die Steuer entsteht.** Statt „mit Ablauf des Voranmeldungszeitraums, in dem die Leistungen ausgeführt worden sind“, entsteht sie „mit Ablauf des Voranmeldungszeitraums, in dem die Entgelte vereinnahmt worden sind“ (§ 13 Abs. 1 Nr. 1 Buchst. a und b UStG [I2]). „Als Zeitpunkt der Vereinnahmung gilt bei Überweisungen auf ein Bankkonto grundsätzlich der Zeitpunkt der Gutschrift.“ (UStAE 13.6 Abs. 1 Satz 3 [I5]) Eine Rechnung vom 20. November, deren Betrag am 8. Januar gutgeschrieben wird, gehört damit in die Voranmeldung für Januar, nicht für November. Bei einer Teilzahlung zählt der vereinnahmte Teil; DATEV rechnet die Steuer dafür aus dem Zahlbetrag [I9].
- **In der Voranmeldung.** Zu den Zeilen 13 bis 16 (Kz 81, 86, 87 und 35/36) sagt die Anleitung: „Bitte tragen Sie hier die Bemessungsgrundlagen Ihrer Umsätze und die erhaltenen Anzahlungen ein, für die die Umsatzsteuer entstanden ist.“ [I6] Bei Ist-Versteuerung sind das die Entgelte, die im Zeitraum vereinnahmt wurden; eine eigene Regel dafür hat die Anleitung nicht. Ihr einziger Satz zur Ist-Versteuerung betrifft die Steuersätze von 2020: Bei Ist-Versteuerung gehören „im aktuellen Voranmeldungszeitraum vereinnahmte Beträge für nach dem 30. Juni 2020 und vor dem 1. Januar 2021 ausgeführte Umsätze“ in Zeile 16 [I6], also in Kz 35/36, der die Vorgaben kein Konto zuordnen. DATEV schreibt: „Bei der Ist-Versteuerung erfolgt der Ausweis von steuerpflichtigen und steuerfreien inländischen Umsätzen in der Umsatzsteuer-Voranmeldung (UStVA) erst bei der Zahlungseingangsbuchung (Geldfluss).“ [I9]
- **Was nicht von der Zahlung abhängt.** Eigene Zeitpunkte behalten:
  - unentgeltliche Wertabgaben nach § 3 Abs. 1b und 9a UStG: „mit Ablauf des Voranmeldungszeitraums, in dem diese Leistungen ausgeführt worden sind“ (§ 13 Abs. 1 Nr. 2 UStG [I2]), ebenso Leistungen an das Personal ohne besonderes Entgelt (UStAE 13.6 Abs. 2 [I5]);
  - der innergemeinschaftliche Erwerb (Kz 89 und 93): „mit Ausstellung der Rechnung, spätestens jedoch mit Ablauf des dem Erwerb folgenden Kalendermonats“ (§ 13 Abs. 1 Nr. 6 UStG [I2]);
  - die Steuer des Leistungsempfängers (Kz 46/47 und 84/85): nach § 13b Abs. 1 und 2 UStG [I3];
  - innergemeinschaftliche Lieferungen (Kz 41), sonstige Leistungen nach § 3a Abs. 2 UStG (Kz 21) und Lieferungen im Dreiecksgeschäft (Kz 42): Die Angaben zu innergemeinschaftlichen Lieferungen sind „in dem Voranmeldungszeitraum zu machen, in dem die Rechnung für diesen Umsatz ausgestellt wird“, spätestens in dem, in dem der Monat nach der Ausführung endet, die zu sonstigen Leistungen und Dreiecksgeschäften in dem, „in dem diese Umsätze ausgeführt worden sind“ (§ 18b Satz 2 und 3 UStG [I3]); die Zusammenfassende Meldung folgt ohnehin § 18a Abs. 8 UStG;
  - der eigene Vorsteuerabzug: Seine Voraussetzungen „müssen insgesamt erfüllt werden. Das gilt auch für Leistungsempfänger, die die Steuer für ihre Umsätze nach vereinnahmten Entgelten berechnen (§ 20 UStG).“ (UStAE 15.2 Abs. 2 Satz 2 und 3 [I5])

  DATEV fasst es so: „Alle anderen Steuersachverhalte werden unabhängig vom Zuflussprinzip (Ist-Versteuerung) gebucht.“ [I9]
- **Wechsel.** „Wechselt der Unternehmer die Art der Steuerberechnung, so dürfen Umsätze nicht doppelt erfasst werden oder unversteuert bleiben.“ (§ 20 Satz 3 UStG [I1]) „Im Falle eines bereits sollversteuerten Umsatzes bleibt der Zeitpunkt des Entstehens der Steuer auch dann unverändert, wenn der Unternehmer zur Istversteuerung wechselt und das Entgelt noch nicht vereinnahmt hat.“ Umgekehrt gilt die Ist-Versteuerung für Umsätze aus Jahren mit Gestattung weiter, auch nach einem Wechsel zur Soll-Versteuerung (UStAE 13.6 Abs. 3 [I5]).
- **Ab 2028 auch beim Leistungsempfänger.** Das Jahressteuergesetz 2024 ändert zum 1. Januar 2028 zwei Vorschriften [I7]: Die Rechnung eines Ist-Versteuerers trägt die Angabe „Versteuerung nach vereinnahmten Entgelten“ (§ 14 Abs. 4 Satz 1 Nr. 6a UStG neu), und ihr Empfänger zieht die Vorsteuer daraus nur ab, „soweit eine Zahlung auf eine ausgeführte Leistung geleistet worden ist“ (§ 15 Abs. 1 Satz 1 Nr. 1 Satz 2 Buchst. b UStG neu), erstmals für Rechnungen, „die nach dem 31. Dezember 2027 ausgestellt werden“ (§ 27 Abs. 41 UStG neu). Das trifft jedes Unternehmen, das Steuerbote nutzt, auch bei Soll-Versteuerung: Kz 66 hängt für solche Rechnungen dann an der Zahlung. Am 20. November 2026 enthält § 15 UStG diese Bedingung noch nicht [I4].

### Buchung der Ist-Versteuerung

DATEV bucht die Ist-Versteuerung über eigene Konten [I9, I10]: „Bei der Rechnungsausgangsbuchung (Umsatzerlös) wird die Umsatzsteuer von steuerpflichtigen inländischen Umsätzen errechnet und automatisch auf Umsatzsteuer nicht fällig gebucht.“ „Bei der Zahlungseingangsbuchung (Geldfluss) erfolgt automatisch eine abgeleitete Umbuchung von „Umsatzsteuer nicht fällig“ auf „Umsatzsteuer fällig“. Bemessungsgrundlage und Umsatzsteuer (bei steuerfreien Umsätzen nur die Bemessungsgrundlage) werden in der UStVA ausgewiesen.“ [I9] Die Konten dafür, geprüft an den Kontenrahmen 2026 [I8]:

| Zweck | SKR03 | SKR04 | Bezeichnung laut Kontenrahmen 2026 |
|---|---|---|---|
| Steuer der Rechnung, 19 % | 1766 | 3816 | Umsatzsteuer nicht fällig 19 % |
| Steuer der Rechnung, 7 % | 1761 | 3811 | Umsatzsteuer nicht fällig 7 % |
| Steuer bei Zahlung, 19 % | 1776 | 3806 | Umsatzsteuer 19 % |
| Steuer bei Zahlung, 7 % | 1771 | 3801 | Umsatzsteuer 7 % |
| Umstellung von Soll auf Ist | 1390 | 1490 | Verrechnungskonto Ist-Versteuerung |

Umgebucht wird von 1766 und 1761 auf 1776 und 1771, in SKR04 von 3816 und 3811 auf 3806 und 3801 [I10]. Dazu führen die Kontenrahmen 1760 „Umsatzsteuer nicht fällig“ und für im Inland steuerpflichtige EU-Lieferungen 1762 und 1764 (SKR04 3810, 3812 und 3814); für 1762 und 1764 nennen die gelesenen DATEV-Dokumente kein Gegenkonto. Das Verrechnungskonto dient „zur Erfassung von Vorgängen im Zusammenhang mit der Umstellung von der Soll- auf die Ist-Versteuerung“ und wird „insbesondere genutzt, um Forderungsausfälle abzubilden, bei denen die Umsatzsteuer bereits im Rahmen der Soll-Versteuerung berücksichtigt wurde“ [I10].

Ein Beispiel in SKR03: eine Rechnung über 1.000 € zuzüglich 19 % vom 20. November, bezahlt am 8. Januar.

| Tag | Soll | Haben | Betrag | Voranmeldung |
|---|---|---|---|---|
| 20. November | Forderung | 8400 | 1.000,00 | noch nicht |
| 20. November | Forderung | 1766 | 190,00 | noch nicht |
| 8. Januar | Bank | Forderung | 1.190,00 | |
| 8. Januar | 1766 | 1776 | 190,00 | Januar: Kz 81 mit 1.000 |

Zahlt der Kunde am 8. Januar nur 595 €, werden 95 € umgebucht (595 × 19/119), und Kz 81 erhält 500 €.

**In ERPNext** bucht eine Vorlage für Verkaufssteuern und -abgaben (Sales Taxes and Charges Template) mit dem nicht fälligen Konto statt 1776 die Steuer jeder Ausgangsrechnung so, wie DATEV es tut, denn ERPNext bucht die Steuer einer Rechnung auf das Konto ihrer Steuerzeile [I11]. Dabei ist zu beachten: Die Vorlage SKR03 von ERPNext enthält keine nicht fälligen Konten, die Vorlage SKR04 enthält 3810, 3811, 3812, 3814 und 3816 ohne Kontoart, und als Konto einer Steuerzeile bietet ERPNext nur Konten der Arten Tax, Chargeable und Expense Account an [I11]; die Konten sind also anzulegen oder als Tax zu kennzeichnen. Die Umbuchung bei Zahlung macht ERPNext nicht, siehe unten; ohne sie bleibt eine Journalbuchung je Zahlung von Hand. Für ein Skonto bucht ERPNext mit der Einstellung „Book tax loss on early payment discount“ (`book_tax_discount_loss`) den Steueranteil auf das Steuerkonto der Rechnung [I11], bei Ist-Versteuerung also auf das nicht fällige Konto.

### Was ERPNext 16 mitbringt

Keine Ist-Versteuerung. Geprüft im Quelltext von ERPNext 16.60.0 und des Frappe Framework 16.60.0 und in der App erpnext_germany (Zweig version-16) [I11]:

- Eine Ausgangsrechnung bucht ihre Steuer beim Buchen auf das Konto ihrer Steuerzeile (`sales_invoice.py`, Zeile 2009). Der Abgleich von Zahlungen mit Rechnungen (`reconcile_against_document` in `erpnext/accounts/utils.py`) bucht keine Steuer um. Die Buchhaltungseinstellungen haben kein Feld, das die Steuer an die Zahlung bindet; ihre Steuerfelder betreffen Steuerkategorie und Steuervorlagen, Rundung, Druck und den Steueranteil am Skonto.
- Die Zahlung (Payment Entry) hat eine Tabelle „Advance Taxes and Charges“. Ihre Beträge rechnet ERPNext aus dem Zahlbetrag (`current_tax_amount = (tax_rate / 100.0) * self.paid_amount_after_tax`, Zeile 2056), nicht aus den bezahlten Rechnungen; keine Zeile verweist auf eine Rechnung, und nichts bucht sie später zurück. Zwei Zeilen mit festem Betrag, „Deduct“ auf dem nicht fälligen und „Add“ auf dem fälligen Konto, ergäben nach dem Code (`add_tax_gl_entries`, ab Zeile 1818) die Umbuchung, wenn jemand den Betrag je Zahlung von Hand einträgt.
- Über den Hook `regional_overrides` lässt sich ERPNext je Land erweitern, etwa um `add_regional_gl_entries` der Zahlung (Zeile 3855, aufgerufen in Zeile 1504). Für Deutschland trägt ERPNext keinen ein, erpnext_germany auch nicht. Über diesen Hook könnte eine App die Umbuchung in die Buchungen der Zahlung selbst schreiben.
- Bei ERPNext sind die Issues #42843 „Incorrect Taxes on Advance Payment“ und #34467 „Invoice on Account/Advance Invoice“ offen; der Pull Request #54921 „feat(PE): carry advance tax through invoice consumption“ wurde am 31. Oktober 2026 ohne Merge geschlossen, und #56063 bringt Berichte zur Gewinnermittlung nach Zahlungen, keine Umsatzsteuer [I12].

### Was Steuerbote bräuchte

1. **Besteuerung je Jahr.** „Ist“ als zweite Möglichkeit in den Einstellungen, je Unternehmen und Kalenderjahr, weil die Gestattung immer für ein ganzes Jahr gilt [I5].
2. **Vorgaben je Besteuerungsart.** Die nicht fälligen Konten 1760, 1761, 1762, 1764 und 1766 (SKR04 3810, 3811, 3812, 3814 und 3816) bleiben bei Soll beobachtet. Bei Ist tragen sie planmäßig die Steuer der offenen Rechnungen: Sie gehen in keine Kennzahl ein und halten die Meldung nicht an.
3. **Kz 81 und 86 aus den fälligen Konten.** Bei Ist buchen die Erlöskonten (8400 und die übrigen Grundlagen von Kz 81 und 86) mit der Rechnung und dürfen deshalb nicht mehr in Kz 81 und 86 eingehen. An ihre Stelle tritt die Steuer, die im Zeitraum fällig wird: Kz 81 ist der Saldo im Haben von 1776 (SKR04 3806) im Zeitraum geteilt durch 19 %, Kz 86 der von 1771 (3801) geteilt durch 7 %. Das erfasst die Umbuchungen bei Zahlung ebenso wie Umsätze, deren Steuer gleich auf das fällige Konto gebucht wird, etwa unentgeltliche Wertabgaben. Der Kern bräuchte dafür eine Regel, die die Grundlage aus einem Steuerkonto ableitet, das Gegenstück zum Steuersatz einer Regel heute (`AccountRule.tax_rate`). Weil die Steuer jeder Zahlung auf Cent gerundet ist, weicht die abgeleitete Grundlage je Zahlung um wenige Cent von der vereinnahmten ab. Genau wäre die Grundlage aus den Zahlungen selbst, Zahlbetrag abzüglich Steueranteil je bezahlter Rechnung; die bezahlten Rechnungen einer Zahlung liest die Frappe-Schicht schon heute für die Zusammenfassende Meldung (`zm_sources.py`). Steuerfreie inländische Umsätze haben kein fälliges Konto; sind sie bei Ist erst mit der Zahlung zu melden, wie DATEV es tut [I9], geht es für sie nur über die Zahlungen.
4. **Verprobung bei Ist.** Heute vergleicht sie je Beleg die gebuchte Steuer mit der Steuer auf die Grundlagen. Bei Ist wäre je Zahlung zu prüfen, ob die Umbuchung dem Steueranteil des Zahlbetrags entspricht, und am Ende des Zeitraums, ob der Saldo der nicht fälligen Konten zum Steueranteil der offenen Posten passt.
5. **Die Umbuchung.** Entweder bucht sie die Buchhaltung von Hand und Steuerbote prüft sie, oder Steuerbote bucht sie selbst, etwa über `add_regional_gl_entries` in der Zahlung. Steuerbote würde damit zum ersten Mal selbst buchen, und Zahlungen, die erst später über den Zahlungsabgleich oder als Journalbuchung einer Rechnung zugeordnet werden, bräuchten einen eigenen Weg.
6. **Wechsel.** Rechnungen, die vor dem Wechsel zu Ist schon nach Soll gemeldet sind, dürfen bei Zahlung nicht noch einmal in Kz 81 eingehen, und umgekehrt [I5]; DATEV unterbindet dafür die erneute Umbuchung und bucht Forderungsausfälle solcher Rechnungen über das Verrechnungskonto [I10]. In den Vorgaben stehen 1390 (SKR03) und 1490 (SKR04) heute als bewusst ohne Kennzahl.
7. **Tests.** Wie bei der Soll-Versteuerung ein an echten Buchungen geprüfter Monat (siehe [Beispiel](#beispiel)) und Frappe-Tests für Teilzahlung, Skonto, Gutschrift, Erstattung und Stornierung mit unveränderlichem Hauptbuch.

### Empfehlung für die Roadmap

1. **Nicht in Stufe 2.** „Besteuerung“ bleibt bei „Soll“, bis die Ist-Versteuerung vollständig ist; Ist-Versteuerer können Steuerbote bis dahin nicht einsetzen.
2. **Ein eigenes Paket „Ist-Versteuerung“ nach der echten Übermittlung**, sobald ein Unternehmen mit Ist-Versteuerung Steuerbote einsetzen will, in dieser Reihenfolge: die Buchungsweise wie bei DATEV mit einer Steuerberatung festlegen; im Kern die Besteuerung je Jahr, Vorgaben je Besteuerungsart und die Grundlage aus den fälligen Konten oder aus den Zahlungen; der Abgleich der nicht fälligen Konten mit den offenen Posten; die Umbuchung zuerst von Hand mit Prüfung durch Steuerbote, eine automatische Umbuchung erst nach Erprobung des Hooks; zuletzt der Wechsel zwischen Soll und Ist.
3. **Unabhängig davon bis Ende 2027** die Vorsteuer aus Rechnungen Ist-versteuernder Lieferanten: Für ihre Rechnungen ab 2028 hängt Kz 66 an der Zahlung [I7]. Das betrifft jedes Unternehmen und gehört in die Vorbereitung des Jahreswechsels 2028.

### Offen zur Ist-Versteuerung

- Ob das Finanzamt Kz 81 und 86 aus der gerundeten Steuer der Zahlungen gelten lässt oder die vereinnahmten Entgelte auf den Cent verlangt, sagt keine der Quellen; das klärt die Steuerberatung.
- Steuerfreie inländische Umsätze (etwa Kz 43 und 48) meldet DATEV bei Ist-Versteuerung erst mit der Zahlung [I9]; eine Vorschrift oder Verwaltungsanweisung dazu steht in den gelesenen Quellen nicht.
- Für 1762 und 1764 (SKR04 3812 und 3814) nennen die gelesenen DATEV-Dokumente kein Gegenkonto der Umbuchung.
- Die Umbuchung über zwei Zeilen „Advance Taxes and Charges“ und über `add_regional_gl_entries` ist nur aus dem Quelltext gelesen, nicht an einer Site erprobt.
- Gesetze, die nach Mitte Oktober 2026 verkündet wurden, sind nicht darauf geprüft, ob sie die Änderungen des Jahressteuergesetzes 2024 zum 1. Januar 2028 verschieben oder ändern.

### Quellen zur Ist-Versteuerung

- **[I1]** § 20 UStG „Berechnung der Steuer nach vereinnahmten Entgelten“: <https://www.gesetze-im-internet.de/ustg_1980/__20.html>
- **[I2]** § 13 UStG „Entstehung der Steuer“: <https://www.gesetze-im-internet.de/ustg_1980/__13.html>
- **[I3]** § 13b UStG „Leistungsempfänger als Steuerschuldner“: <https://www.gesetze-im-internet.de/ustg_1980/__13b.html>; § 18b UStG: <https://www.gesetze-im-internet.de/ustg_1980/__18b.html>
- **[I4]** § 15 UStG „Vorsteuerabzug“: <https://www.gesetze-im-internet.de/ustg_1980/__15.html>
- **[I5]** Umsatzsteuer-Anwendungserlass, Stand 13. November 2026, Abschnitte 13.6, 15.2 Abs. 2 und 20.1: <https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/Umsatzsteuer-Anwendungserlass/Umsatzsteuer-Anwendungserlass-aktuell.pdf?__blob=publicationFile&v=61> (SHA-256 `406cda32cf956d29f2ffde5079c8a7f963a763aa47615c6652148856a23e4c2e`)
- **[I6]** Anleitung zur Umsatzsteuer-Voranmeldung 2026 (USt 1 E), Zeilen 13 bis 16, im BMF-Schreiben vom 29. Dezember 2025, siehe [Quelle](#quelle) (SHA-256 `82e7d63a0faec542bb184acb438eaf4ce90a2d7db067bb47f92ae13b4b17613d`)
- **[I7]** Jahressteuergesetz 2024 vom 2. Dezember 2024, BGBl. 2024 I Nr. 387, Artikel 27 und Artikel 56 Absatz 12 („Die Artikel 27 und 30 treten am 1. Januar 2028 in Kraft.“): <https://www.recht.bund.de/bgbl/1/2024/387/regelungstext.pdf?__blob=publicationFile&v=1> (SHA-256 `5ed5fd277dac16360d53acc403d3a2cb0b2bf798b2e511c5c2917a8a869c8f4c`)
- **[I8]** DATEV-Kontenrahmen SKR 03 (Art.-Nr. 11174) und SKR 04 (Art.-Nr. 11175), „Gültig für 2026“, siehe [Quelle](#quelle): SKR03 1390 (Funktion F), 1760, 1761, 1762, 1764, 1766, 1771 und 1776 (Funktion S); SKR04 1490 (F), 3801, 3806, 3810, 3811, 3812, 3814 und 3816 (S)
- **[I9]** DATEV Dok.-Nr. 1080673 „Besondere Regeln und Vereinfachungen für die Buchung der Ist-Versteuerung“, zuletzt aktualisiert am 26. September 2026: <https://wissensplattform.apps.datev.de/help/document/1080673>
- **[I10]** DATEV Dok.-Nr. 1034841 „Umstellung von Soll-Versteuerung auf Ist-Versteuerung in den DATEV-Rechnungswesen-Programmen“, Stand 4. Juni 2026: <https://apps.datev.de/help-center/documents/1034841>; DATEV Dok.-Nr. 5360294 „Verrechnungskonto Ist-Versteuerung - Kontenerläuterung“ vom 1. Juni 2026: <https://apps.datev.de/knowledge/professional/documents/5360294>
- **[I11]** ERPNext 16.60.0, <https://github.com/frappe/erpnext/tree/v16.60.0>: `erpnext/accounts/doctype/sales_invoice/sales_invoice.py` (Zeile 2009), `erpnext/accounts/doctype/accounts_settings/accounts_settings.json`, `erpnext/accounts/doctype/payment_entry/payment_entry.json` (Tabelle `taxes`, Zeilen 607 bis 610), `erpnext/accounts/doctype/payment_entry/payment_entry.py` (`add_tax_gl_entries` ab Zeile 1818, Zeile 2056, `split_early_payment_discount_loss` ab Zeile 3659, `add_regional_gl_entries` in den Zeilen 1504 und 3855), `erpnext/accounts/utils.py` (`reconcile_against_document` ab Zeile 510), `erpnext/__init__.py` und `erpnext/hooks.py` (`regional_overrides`, Zeilen 684 bis 697), `erpnext/public/js/controllers/accounts.js` (Zeilen 25 bis 37) und die Vorlagen `de_kontenplan_SKR03.json` und `de_kontenplan_SKR04.json` (dort Zeilen 766 und 1456 bis 1472) unter `erpnext/accounts/doctype/account/chart_of_accounts/verified/`; Frappe Framework 16.60.0; erpnext_germany, Zweig version-16: <https://github.com/alyf-de/erpnext_germany/tree/version-16>
- **[I12]** frappe/erpnext, Issues <https://github.com/frappe/erpnext/issues/42843> und <https://github.com/frappe/erpnext/issues/34467>, Pull Requests <https://github.com/frappe/erpnext/pull/54921> und <https://github.com/frappe/erpnext/pull/56063>

## Zeiträume und Fristen

[`period.py`](../steuerbote/ustva/period.py) beschreibt Voranmeldungszeiträume und ihre Fristen:

- **Zeitraum:** Eine Firma gibt monatlich oder vierteljährlich ab (§ 18 Absatz 2 UStG). Der Vordruck bietet die zwölf Monate und die vier Kalendervierteljahre, und so heißen die Zeiträume auch in Steuerbote, etwa „März 2026“ oder „III. Kalendervierteljahr 2026“.
- **Frist:** Die Anleitung sagt zu den Zeilen 53 und 54: „Die Vorauszahlung ist am 10. Tag nach Ablauf des Voranmeldungszeitraums fällig“. Mit Dauerfristverlängerung (§§ 46 bis 48 UStDV) verschiebt sich die Frist um einen Monat.
- **Wochenende und Feiertage:** Fällt die Frist auf einen Samstag, Sonntag oder Feiertag, gilt der nächste Werktag (§ 108 Absatz 3 AO). Feiertage unterscheiden sich je Bundesland, deshalb übergibt sie der Aufrufer.
- **Zeitraumcode:** `Period.code` liefert den zweistelligen Code der ELSTER-Schnittstelle für die Umsatzsteuer-Voranmeldung: 01 bis 12 für die Monate, 41 bis 44 für die Quartale. Die Tests des XML prüfen jeden Code gegen das Schema des Jahres aus der ERiC-Dokumentation, siehe [Abgabe über Mein ELSTER](abgabe-mein-elster.md).

Beispiele aus den Tests: Januar 2026 ist am 10. Februar 2026 fällig, mit Dauerfristverlängerung am 10. März 2026. Das I. Kalendervierteljahr 2026 ist am 10. April 2026 fällig. Für September 2026 gilt der 12. Oktober 2026, weil der 10. Oktober ein Samstag ist. Dezember 2026 ist am 11. Januar 2027 fällig, weil der 10. Januar ein Sonntag ist.

## Jahreswechsel

Den ganzen Ablauf mit Jahrestabelle, Schema, Vordruck USt 1 H, Plugin und Release beschreibt [Entwicklung, Jahreswechsel](entwicklung.md#jahreswechsel). Hier stehen die Prüfungen am Vordruck USt 1 A und an den Vorgaben. Zu jedem neuen Jahr:

1. Das BMF-Schreiben „Muster der Vordrucke im Umsatzsteuer-Voranmeldungs- und -Vorauszahlungsverfahren“ für das neue Kalenderjahr lesen. Es nennt die Änderungen in einem eigenen Abschnitt, und die Anleitung markiert wesentliche Änderungen mit „Neu!“. Datum, Geschäftszeichen und Adresse kommen in `YEARS` von [`years.py`](../steuerbote/ustva/years.py).
2. Den neuen Vordruck USt 1 A Zeile für Zeile mit dem Katalog des Vorjahres vergleichen: Zeile, Kennzahl, Bezeichnung, Art, Wirkung, Steuersatz und Steuer-Kennzahl, neue, entfallene und verschobene Kennzahlen. Die Jahresprüfung `python -m steuerbote.ustva.yearcheck` vergleicht Kennzahlen, Zeile, Art und die Paare aus Bemessungsgrundlage und Steuer mit der Jahresdokumentation von ERiC; Bezeichnung, Wirkung und Steuersatz stehen nur im Vordruck. Dazu prüfen, ob die Zeilen der Summen noch stimmen (`OUTPUT_TAX_LINES`, `INPUT_TAX_LINES`, `OTHER_TAX_LINES`); sie gelten bisher für alle Jahrgänge. Liegt eine Kennzahl mit Wirkung im neuen Vordruck außerhalb dieser Zeilen, weist `_index` den Katalog ab; dann werden die Zeilen der Summen ein Teil des Jahrgangs, in `kennzahlen.py` und in `calculation.py`, das sie liest.
3. Den Rundungssatz und die Fälligkeit in der Anleitung mit `rounding.py` und `period.py` vergleichen.
4. Zuerst die Tests schreiben: eine Tabelle des neuen Vordrucks in `test_kennzahlen.py` nach dem Muster von `FORM_UST_1_A_2026`. Dann den neuen Katalog als weiteren Jahrgang in `CATALOGUES` anlegen, mit Datum und Geschäftszeichen des neuen Schreibens im Docstring von `kennzahlen.py`. Der Katalog des Vorjahres bleibt.
5. Die neuen Ausgaben der DATEV-Kontenrahmen SKR 03 und SKR 04 („Gültig für“ das neue Jahr) gegen `defaults.py` prüfen: Nummern und Bezeichnungen aller Konten aus Regeln, Verprobungen, beobachteten und bewusst ausgenommenen Konten, die Liste der mit „U“ gekennzeichneten Konten in `tests/fixtures/datev_2026.py` als neue Ausgabe daneben anlegen (der Vollständigkeitstest `test_completeness.py` prüft die Vorgaben dagegen), und ob die Vorgaben gegen den neuen Katalog gültig sind (`default_mapping(chart, year)`). Auch hier zuerst `test_defaults.py`. Die Vorgaben werden gegen den neuesten Katalog gebaut: Nimmt eine ihrer Regeln eine Kennzahl, die der neue Vordruck nicht mehr hat, scheitert schon der Import von `defaults.py`, und die Vorgaben brauchen einen Stand je Jahr.
6. Diese Seite aktualisieren: Quelle, Kennzahlen, Vorgaben, Verprobungen, beobachtete und bewusst ausgenommene Konten. Die Tabellen entstehen aus dem Code; [`test_docs.py`](../steuerbote/ustva/tests/test_docs.py) gleicht sie mit `defaults.py` ab und muss ohne Abweichung durchlaufen.
7. Das XML-Schema des Jahres aus der ERiC-Dokumentation prüfen: `python -m steuerbote.ustva.yearcheck <Verzeichnis> <Jahr>` vergleicht Katalog, Schema des XML und Vordruck USt 1 H mit Jahresdokumentation und Schema des Jahres und muss ohne Ausgabe enden, siehe [Jahresprüfung](entwicklung.md#jahresprüfung).

Warum ein Katalog je Jahr: ELSTER nimmt eine Meldung nur in der Datenart des Jahres ihres Zeitraums an und hält das laufende Jahr und die drei Jahre davor offen. Steuerbote wählt den Katalog deshalb nach dem Jahr des Zeitraums. So behalten frühere Zeiträume und berichtigte Anmeldungen ihre Kennzahlen, und der Katalog für ein neues Jahr kann dazukommen, sobald das BMF den Vordruck veröffentlicht.
