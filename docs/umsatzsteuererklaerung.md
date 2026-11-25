# Umsatzsteuererklärung

Die Umsatzsteuererklärung ist die Steueranmeldung des Unternehmens für das Kalenderjahr: „Der Unternehmer hat […] für das Kalenderjahr oder für den kürzeren Besteuerungszeitraum eine Steuererklärung nach amtlich vorgeschriebenem Datensatz über die amtlich bestimmte Schnittstelle zu übermitteln, in der er die zu entrichtende Steuer oder den Überschuss, der sich zu seinen Gunsten ergibt, […] selbst zu berechnen hat“ (§ 18 Abs. 3 Satz 1 UStG). Steuerbote berechnet sie als Beleg „Umsatzsteuererklärung“ (`Annual VAT Return`) aus dem Hauptbuch des Jahres, gleicht sie mit den abgegebenen Voranmeldungen ab, prüft sie mit den Regeln der Jahresdokumentation und druckt sie im Wortlaut des Vordrucks USt 2 A. Über ERiC geht sie, sobald Steuerbote eine Hersteller-ID hat; bis dahin läuft die Übermittlung als Simulation, und die Erklärung wird in Mein ELSTER nach dem Druckformat eingegeben. Diese Seite ersetzt keine Steuerberatung.

Der Beleg lebt auf der Grundlage der Jahresmeldungen: Status, Berechnen, Korrekturen und Zeilen von Hand, Befunde, Abgabe, Berichtigung und Übermittlung sind die aller Jahresmeldungen und stehen in [Jahresmeldungen](jahresmeldungen.md). Den Rechenkern unter `steuerbote/ustjahr` (Katalog, Aufteilung, Berechnung, Vorauszahlungssoll, Abgleich, Regeln) beschreiben seine Docstrings, die Kontenzuordnung mit den Feldern der Erklärung [Kontenzuordnung der Umsatzsteuererklärung](ustva-kennzahlen.md#kontenzuordnung-der-umsatzsteuererklärung), das XML und die Simulation [ERiC](eric.md).

## Umfang

- **Unternehmen:** eine GmbH oder UG mit Sitz im Inland und einer Steuernummer, Kontenrahmen SKR03 oder SKR04 mit den Vorgaben der Kontenzuordnung, Geschäftsjahr gleich Kalenderjahr.
- **Jahre:** 2026, der erste Jahrgang mit Vordruck, Jahresdokumentation und Schema (`steuerbote/ustjahr/years.py`). Ein Jahr ohne Vordruck lehnt der Beleg beim Speichern ab.
- **Besteuerung:** nach vereinbarten Entgelten; die Erklärung gibt Kz 133 immer mit 1 an.
- **Nicht darin:** Anlage UN und Anlage FV, die Umsätze nach §§ 25 und 25a UStG (Zeilen 37 und 38) und die Aufgabe des Unternehmens im Lauf des Jahres. Ein Kleinunternehmer gibt keine Erklärung ab (§ 19 Abs. 1 Satz 2 UStG), außer das Finanzamt fordert sie an (§ 149 Abs. 1 Satz 2 AO); ein Jahr, das die Einstellungen Jahresmeldungen als Jahr eines Kleinunternehmers kennzeichnen, hat deshalb kein Fälligkeitsdatum und einen Hinweis.

## Der Beleg

Ein Beleg je Unternehmen und Jahr, benannt nach dem Jahr, für das er gilt (`UStE-2026-00001`). Jeder weitere Beleg des Jahres ist eine Berichtigung mit Kz 110, siehe [Berichtigung](#berichtigung).

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company`, `year` | Unternehmen, Jahr | Pflicht; das Jahr ist das Kalenderjahr, der Besteuerungszeitraum, und wählt den Vordruck |
| `fiscal_year`, `from_date`, `to_date`, `status`, `ready`, `deadline`, `is_correction`, `corrects`, `transmission_in_progress`, `findings`, `filed_via`, `filed_on`, `transferticket`, `filed_by`, `filing_note`, `remarks` | | die Felder jedes Belegs einer Jahresmeldung, siehe [Felder jedes Belegs](jahresmeldungen.md#felder-jedes-belegs) |
| `lines` | Zeilen der Erklärung | Tabelle „Zeile der Umsatzsteuererklärung“ (`Annual VAT Return Line`): Feldkennung, Bezeichnung, Kennzahl, Zeile im Vordruck, Formatkennzeichen, Kennzahl der Voranmeldung, Paragraf der Steuerbefreiung, Betrag laut Hauptbuch, Betrag laut Vordruck, Korrigierter Betrag mit Begründung, Gemeldeter Betrag und Zeile von Hand |
| `soll_voranmeldungen`, `soll_credited` | Kz 83 der Voranmeldungen, Kz 39 der Voranmeldungen | die Summen der jeweils letzten abgegebenen Voranmeldung jedes Zeitraums |
| `sondervorauszahlung` | Sondervorauszahlung laut Einstellungen | aus den Einstellungen Umsatzsteuer-Voranmeldung, in einem Jahr mit Dauerfristverlängerung |
| `soll_computed` | Vorauszahlungssoll berechnet | Kz 83 der Voranmeldungen und die Sondervorauszahlung, bei einer Berichtigung die Kz 816 der berichtigten Erklärung |
| `soll_override`, `soll_override_reason` | Vorauszahlungssoll laut Finanzamt, Begründung des Vorauszahlungssolls | nur, wenn das Finanzamt ein anderes Soll festgesetzt hat; der Betrag zählt mit Begründung, auch 0, und ohne Begründung lehnt das Speichern ihn ab |
| `vorauszahlungssoll` | Vorauszahlungssoll (Zeile 125) | was Zeile 125 meldet: das Soll laut Finanzamt oder das berechnete |
| `kz816`, `kz820` | Verbleibende Umsatzsteuer oder verbleibender Überschuss (Kz 816), Abschlusszahlung oder Erstattungsanspruch (Kz 820) | aus den gemeldeten Zeilen |
| `payment_due` | Abschlusszahlung fällig am | setzt die Abgabe, siehe [Abschlusszahlung](#abschlusszahlung) |
| `line_41` bis `line_122` | Zeile 41 bis Zeile 122 | die Summen des Vordrucks: Zeilen 41, 50, 62, 64, 70, 74, 93, 108 (zwei Spalten), 109 bis 118 und 122 |
| `kz129` | Verrechnung des Erstattungsbetrages erwünscht oder Erstattungsbetrag abgetreten (Kz 129) | Zeile 22 |
| `kz136` | Datum des Wechsels von der Kleinunternehmer-Regelung (Kz 136) | Zeile 18, der Tag, den Kz 70 der Voranmeldung des Zeitraums nennt (USt 1 E 2026, Zeile 12); nennt eine abgegebene Voranmeldung einen anderen, gibt „Berechnen“ den Hinweis `SB-KZ136` |
| `kz500`, `kz500_text` | Ergänzende Angaben zur Steuererklärung (Kz 500), Ergänzende Angaben | Zeile 23, der Schlüssel 1 bis 4 mit seinem Text |
| `bescheid` | Bescheiddaten zum Abruf bereitstellen | der Vorsatz fragt mit Bescheid 1 nach den Bescheiddaten zum elektronischen Abruf, sonst mit 2; Vorgabe nein |
| `kz370`, `properties` | Grundstücke im Jahr erstmals verwendet (Kz 370), Grundstücke (Zeile 95) | Zeile 95 mit der Tabelle „Grundstück nach § 15a UStG“ (`Annual VAT Return Property`): Lage, Zeitpunkt der erstmaligen tatsächlichen Verwendung, Art und Umfang der Verwendung im Erstjahr, insgesamt angefallene und in den Vorjahren bereits abgezogene Vorsteuer, höchstens 99 |
| `kz371`, `kz372`, `kz369` | Geänderte Verhältnisse … | die Fragen der Zeilen 96 bis 98 |
| `change_by_sale`, `change_by_withdrawal`, `change_of_taxation`, `change_of_small_business`, `change_of_use`, `change_of_letting`, `change_of_own_use`, `change_for_other_reasons`, `change_reason` | Geändert durch … | die Gründe der Zeilen 99 bis 104 mit der Begründung |
| `periods` | Voranmeldungszeiträume | Tabelle „Abgleich je Voranmeldungszeitraum“ (`Annual VAT Return Period`), siehe [Abgleich](#abgleich-mit-den-voranmeldungen) |
| `reconciliation` | Je Kennzahl | Tabelle „Abgleich je Kennzahl“ (`Annual VAT Return Reconciliation`) |
| `checks`, `deviations`, `unmapped` | Verprobung, Abweichende Belege, Beobachtete Konten mit Saldo | die Tabellen der Voranmeldung, für das ganze Jahr |

Rechte wie bei der Voranmeldung: System Manager und Accounts Manager legen an, berechnen, ändern und geben ab; ein Accounts User legt an, berechnet und ändert, gibt aber nicht ab. Die Liste steht als „USt-Erklärungen“ in der Seitenleiste in der Gruppe „Jahresmeldungen“ und im gleichnamigen Abschnitt des Arbeitsbereichs „Steuern“, dort neben „Neue USt-Erklärung“.

## Berechnen

„Berechnen“ liest die Quellen des Jahres (`steuerbote/ustjahr_sources.py`) und rechnet mit dem Kern (`compute` in `annual_vat_return.py`):

1. **Hauptbuch:** die Buchungen des Kalenderjahres, wie die Voranmeldung sie liest und ihren Zeiträumen zuordnet (`vat_periods.VatLedger`, siehe [Zuordnung zum Voranmeldungszeitraum](ustva-kennzahlen.md#zuordnung-zum-voranmeldungszeitraum)), und die der Zeiträume des Jahres. Eine Buchung wechselt nie das Jahr, auch nicht mit „im laufenden Zeitraum melden“; das Jahr ist deshalb unter beiden Einstellungen die Summe seiner Zeiträume, und eine Ausgangsrechnung zählt in dem Jahr ihrer Leistung.
2. **Zeilen:** Die Kontenzuordnung Umsatzsteuer gibt jedem Konto seine Zeile der Erklärung (`to_split`). `calculation.calculate()` rechnet daraus die Felder des Vordrucks, mit den Zeilen von Hand. Bemessungsgrundlagen sind die vollen Euro des genauen Jahresbetrags, die Steuer einer Steuerzeile der Satz auf die genaue Jahresgrundlage, kaufmännisch gerundet; dass die Finanzverwaltung so rechnet, ist ungeprüft (Option B, siehe `steuerbote/ustjahr/calculation.py`). Steht in den Einstellungen Umsatzsteuer-Voranmeldung „Steuer zu Umsätzen mit festem Steuersatz“ auf „wie gebucht“, nimmt die Steuerzeile einer Bemessungsgrundlage der Kz 81, 86, 89 und 93 stattdessen die Steuer, die ihre Belege buchen, wie die Voranmeldungen (siehe [Steuer zu Umsätzen mit festem Steuersatz](ustva-kennzahlen.md#steuer-zu-umsätzen-mit-festem-steuersatz)): jeder Teil eines Belegs in der Zeile seines Grundlagenkontos, ein Teil ohne Grundlagenkonto in der Vorgabezeile seiner Kennzahl, dazu der Satz auf die Konten nur für die Erklärung und die Zeilen von Hand. Weil die gebuchte Steuer eines Belegs in seiner Voranmeldung und im Jahr dieselbe ist, gehen die Voranmeldungen und die Erklärung ohne Centdifferenz auf; nur Buchungszeilen ohne Beleg gelten je Zeitraum und im Jahr als ein Beleg und können um Cent abweichen. ERiC nimmt eine Steuer an, die höchstens einen Euro neben dem Satz auf die übermittelte Bemessungsgrundlage in vollen Euro liegt (Regeln 30639 bis 30644 und die verwandten, siehe `steuerbote/ustjahr/calculation.py`). Liegt die gebuchte Steuer weiter daneben, nimmt die Zeile die Steuer der genauen Jahresgrundlage, und der Hinweis `STEUER-WIE-GEBUCHT` nennt den Abstand. Die genauen Beträge der Steuerzeile bleiben in beiden Fällen der Satz auf die genaue Bemessungsgrundlage, so dass der Abgleich mit den Voranmeldungen den Unterschied wie bisher als Rundung ausweist. Eine Bemessungsgrundlage ohne Grundlagenkonto, etwa eines Einkaufs mit Steuer nach § 13b UStG auf einem Aufwandskonto, leitet der Lauf über das Jahr ab wie jede Voranmeldung und gibt sie mit ihrer Steuer an die Vorgabezeile ihrer Kennzahl, siehe [Bemessungsgrundlage ohne Grundlagenkonto](ustva-kennzahlen.md#bemessungsgrundlage-ohne-grundlagenkonto); eine Leistung nach § 13b UStG geht dabei wie in der Voranmeldung nach dem Lieferanten ihres Belegs an die Zeile von Kz 46 oder Kz 84, siehe [Kz 46 oder Kz 84](ustva-kennzahlen.md#kz-46-oder-kz-84-der-sitz-des-leistenden).
3. **Vorauszahlungssoll:** `soll.vorauszahlungssoll()` aus den abgegebenen Voranmeldungen, der Sondervorauszahlung und den Begründungen für Zeiträume ohne Voranmeldung, siehe unten.
4. **Abgleich:** `reconciliation.reconcile()` stellt die Erklärung den abgegebenen Voranmeldungen und einem Lauf der Voranmeldung auf dem heutigen Hauptbuch je Zeitraum gegenüber; `reconciliation.journal_entries()` nennt Journalbuchungen auf Steuerkonten.
5. **Regeln:** Auf die Werte, wie die Erklärung sie abgibt, mit den Korrekturen, laufen die eigenen Prüfungen von Steuerbote und die Regeln der Jahresdokumentation, die Steuerbote selbst prüft (`rules.check()`).
6. **Umsatzerlöse:** Dieselben Werte stellt „Berechnen“ neben die Umsatzerlöse des festgestellten Jahresabschlusses oder der abgegebenen E-Bilanz des Jahres, siehe [Abgleich mit den Umsatzerlösen](#abgleich-mit-den-umsatzerlösen).

`annual_vat_return/bridge.py` bringt die Ergebnisse in die Zeilen und Tabellen des Belegs, ohne Frappe und mit eigenen Tests.

### Zeilen, Korrekturen und Zeilen von Hand

Jedes Feld mit einem Betrag hat eine Zeile. Eine **Korrektur** meldet einen anderen Betrag und braucht eine Begründung, wie an jeder Jahresmeldung. Eine **Zeile von Hand** nennt ihr Feld mit der Feldkennung oder der Kennzahl, etwa 320 für E3006201, und gibt ihren Betrag als Korrektur mit Begründung an; das Speichern schreibt die Feldkennung und die Beschreibung des Felds dazu und lehnt ein Feld ab, das kein Konto speisen kann, etwa eine Summe. „Berechnen“ nimmt den Betrag in die Zeile seines Felds auf, vor dem Runden, etwa eine Berichtigung nach § 15a UStG bis 6.000 Euro, die erst in der Erklärung erfolgt (§ 44 Abs. 3 Satz 1 UStDV). Eine Zeile von Hand der Zeilen 46, 52 und 54 nennt ihren Paragrafen selbst; die berechneten Zeilen nehmen ihn aus den Zuordnungen der Konten.

### Was das Speichern nimmt

Das Speichern nimmt die Korrekturen und Zeilen von Hand, das Vorauszahlungssoll laut Finanzamt mit Begründung, die Begründungen der Zeiträume, die Angaben der Erklärung und die Grundstücke; die Summen, Kz 816, Zeile 125 und Kz 820 setzt es aus den gemeldeten Zeilen (`set_amounts`). Ändert ein Speichern etwas davon an einem berechneten Beleg, steht er auf „Berechnet“ mit dem Befund `SB-NEU-BERECHNEN`, bis „Berechnen“ ihn wieder prüft. Von der Tabelle „Voranmeldungszeiträume“ nimmt das Speichern nur die Begründungen; Zeilen von Hand nimmt sie nicht.

## Vorauszahlungssoll und Abschlusszahlung

Zeile 125, „Vorauszahlungssoll 2026 (einschließlich Sondervorauszahlung)“, ist Pflicht (Regel 30915). Die Anleitung sagt: „Vorauszahlungssoll ist die Summe der angemeldeten bzw. festgesetzten Umsatzsteuer-Vorauszahlungen/Überschüsse aus dem Voranmeldungsverfahren einschließlich der Sondervorauszahlung für die Dauerfristverlängerung.“ (USt 2 E 2026, Zeilen 124 bis 126)

- **Die abgegebenen Voranmeldungen:** je Voranmeldungszeitraum die letzte, die gebucht ist und den Status „Abgegeben“ hat; eine berichtigte Anmeldung (Kz 10) ersetzt die früheren ihres Zeitraums. Ihre Kz 83 und Kz 39 ergeben die Felder „Kz 83 der Voranmeldungen“ und „Kz 39 der Voranmeldungen“.
- **Die Sondervorauszahlung** des Jahres aus den Einstellungen Umsatzsteuer-Voranmeldung, wenn das Jahr eine Dauerfristverlängerung hat. Die letzte Voranmeldung des Jahres zieht sie in Kz 39 ab (§ 48 Abs. 4 UStDV); weicht Kz 39 davon ab, gibt der Kern den Hinweis `SONDERVORAUSZAHLUNG-KZ39`.
- **Zeiträume ohne Voranmeldung:** Jeder Zeitraum, für den die Einstellungen eine Voranmeldung verlangen und der nicht abgegeben ist, hält die Erklärung an (`ZEITRAUM-FEHLT`), außer seine Zeile in „Voranmeldungszeiträume“ begründet, warum die Erklärung ohne sie abgegeben wird, etwa weil sie außerhalb von Steuerbote abgegeben wurde; ihr Betrag kommt dann mit dem Vorauszahlungssoll laut Finanzamt. Ein Monat, den die Einstellungen von der Voranmeldung befreien (§ 18 Abs. 2 Satz 3 UStG) oder der vor ihrer ersten Regel oder vor der Gründung liegt, verlangt keine.
- **Das Finanzamt** setzt ein anderes Soll fest, in einem Bescheid oder einer Schätzung: Das Vorauszahlungssoll laut Finanzamt mit Begründung ersetzt das berechnete, mit dem Hinweis `SOLL-UEBERSCHRIEBEN`.
- **Eine Berichtigung** nimmt die Kz 816 der Erklärung, die sie berichtigt: „In den Fällen, in denen bereits eine Festsetzung der Umsatzsteuer für den Besteuerungszeitraum erfolgt ist, tragen Sie bitte die bisher festgesetzte Umsatzsteuer als Vorauszahlungssoll ein.“ (USt 2 E 2026) Die abgegebene Erklärung steht einer Festsetzung unter Vorbehalt der Nachprüfung gleich (§ 168 Satz 1 AO); weicht das Finanzamt ab, gilt sein Betrag als Vorauszahlungssoll laut Finanzamt.
- **Zahlungen:** Ob gezahlt wurde, spielt für das Soll keine Rolle. Der Hinweis `ZAHLUNGEN` nennt, was das Hauptbuch im Jahr auf den Konten der Zahlungen an das Finanzamt zeigt, wenn es vom Soll abweicht: SKR03 1780 „Umsatzsteuer-Vorauszahlungen“ und 1781 „Umsatzsteuer-Vorauszahlungen 1/11“, SKR04 3820 und 3830, Soll abzüglich Haben, alle Belege des Jahres außer Eröffnungsbuchungen, Periodenabschlussbelegen und stornierten. Die Zahlung für den letzten Zeitraum des Jahres im Januar oder Februar des Folgejahres fehlt darin, die für den letzten Zeitraum des Vorjahres zählt mit; der Hinweis ist deshalb ein Anlass zum Nachsehen.

### Abschlusszahlung

Kz 820 ist Kz 816 abzüglich des Vorauszahlungssolls (Regel 30638): positiv „Noch an die Finanzkasse zu entrichten – Abschlusszahlung“, negativ der Erstattungsanspruch. Die Abschlusszahlung ist „einen Monat nach dem Eingang der Steueranmeldung fällig“ (§ 18 Abs. 4 Satz 1 UStG). Die Abgabe setzt den Tag (`soll.payment_due`): einen Monat nach dem Tag der Abgabe, nach § 188 Abs. 2 und 3 BGB, und am nächsten Werktag, wenn er auf ein Wochenende oder einen Feiertag der Feiertagsliste des Unternehmens fällt (§ 108 Abs. 3 AO). Ein Erstattungsanspruch hat keinen.

## Abgleich mit den Voranmeldungen

**Je Voranmeldungszeitraum** (Tabelle „Voranmeldungszeiträume“): jeder Zeitraum des Jahres, wie die Einstellungen ihn setzen, ein Monat ohne Voranmeldung als eigener Zeitraum, dazu jeder abgegebene Zeitraum, den die Einstellungen nicht mehr setzen. Je Zeitraum: Voranmeldungszeitraum, ob eine Voranmeldung fällig ist, die abgegebene Umsatzsteuer-Voranmeldung, Kz 83 und Kz 39 wie abgegeben, Kz 83 laut Hauptbuch heute, der Unterschied mit seinen Teilen spätere Buchungen und Korrekturen ohne Buchung, die Ursache und die Begründung ohne Voranmeldung.

| Ursache | Bedeutung |
|---|---|
| Kein Unterschied | das heutige Hauptbuch ergibt, was abgegeben ist |
| Spätere Buchungen | Buchungen mit Datum im Zeitraum nach seiner Abgabe, etwa Abschlussbuchungen; der Hinweis `BUCHUNG-NACH-ABGABE` nennt sie |
| Korrekturen ohne Buchung | die Voranmeldung hat Korrekturen gemeldet, die das Hauptbuch nicht hat |
| Spätere Buchungen und Korrekturen | beides |
| Nicht abgegeben | keine abgegebene Voranmeldung |

**Je Kennzahl** (Tabelle „Je Kennzahl“): jede Kennzahl der Voranmeldung mit einem Betrag, wie abgegeben, wie das Hauptbuch sie bei der Abgabe hatte und heute hat und wie die Erklärung sie meldet. Der Unterschied der Erklärung zu den Voranmeldungen zerfällt in spätere Buchungen, Korrekturen ohne Buchung, nicht abgegebene Zeiträume, Rundung, Beträge nur der Erklärung (Konten nur für die Umsatzsteuererklärung, Zeilen von Hand, Korrekturen) und einen unerklärten Rest. Die letzte Zeile stellt Kz 820 den Kz 83 der Zeiträume gegenüber, mit zwei Teilen dazu: Kz 39 gegen die Sondervorauszahlung und ein abweichendes Vorauszahlungssoll. Der Rest ist null, wenn Jahr und Zeiträume dasselbe Hauptbuch lesen; sonst hält er die Erklärung an (`ABGLEICH-REST`).

Ob eine Buchung nach der Abgabe eine berichtigte Voranmeldung verlangt (§ 153 Abs. 1 AO), entscheidet das Unternehmen mit seiner Steuerberatung; ob die Jahreserklärung allein eine Voranmeldung berichtigen darf, ist ungeprüft.

## Abgleich mit den Umsatzerlösen

Umsatzerlöse und Umsätze zählen dieselben Verkäufe ohne Umsatzsteuer: Als Umsatzerlöse sind „die Erlöse aus dem Verkauf und der Vermietung oder Verpachtung von Produkten sowie aus der Erbringung von Dienstleistungen der Kapitalgesellschaft nach Abzug von Erlösschmälerungen und der Umsatzsteuer“ auszuweisen (§ 277 Abs. 1 HGB), und „Der Umsatz wird bei Lieferungen und sonstigen Leistungen [...] nach dem Entgelt bemessen“ (§ 10 Abs. 1 Satz 1 UStG). „Berechnen“ stellt deshalb die Bemessungsgrundlagen der Lieferungen und sonstigen Leistungen, wie die Erklärung sie mit den Korrekturen abgibt, neben die Umsatzerlöse des Jahres (`annual_vat_return/revenue.py`):

- **Umsatzerlöse:** die des festgestellten Jahresabschlusses des Jahres, des gebuchten, der nicht ersetzt ist (siehe [Jahresabschluss](jahresabschluss.md#für-die-umsatzsteuererklärung)), sonst „Umsatzerlöse (GKV)“ der für das Jahr abgegebenen E-Bilanz (siehe [E-Bilanz](ebilanz.md)); ohne beide vergleicht „Berechnen“ nichts.
- **Umsätze der Erklärung:** die Zeilen, die die Kennzahlen der Voranmeldung mit den Bemessungsgrundlagen von Lieferungen und sonstigen Leistungen nehmen (Kz 81, 86, 87, 35, 77, 76, 41, 44, 49, 43, 48, 42, 60, 21 und 45): die steuerpflichtigen Umsätze der Zeilen 24, 27, 30 und 33 bis 35, die steuerfreien der Zeilen 42 bis 49 und 51 bis 54, die Lieferungen des ersten Abnehmers in Zeile 65 und die Umsätze der Zeilen 76, 78, 80 und 81, deren Steuer ein anderer schuldet oder die im Inland nicht steuerbar sind. Die unentgeltlichen Wertabgaben der Zeilen 25, 26, 28, 29, 31 und 32 bleiben draußen: Sie bringen keine Erlöse, und die DATEV-Kontenrahmen führen ihre Konten unter den sonstigen betrieblichen Erträgen.
- **Toleranz:** Jede Zeile meldet volle Euro ohne Cent, bis zu einem Euro je Zeile ist also Rundung; darüber hinaus gilt die Schwelle in Euro des Vorperiodenvergleichs der Einstellungen Umsatzsteuer-Voranmeldung (`comparison_threshold_amount`, Vorgabe 100 €).

Liegt die Differenz darüber, nennt der Hinweis `SB-UMSATZERLOESE` die Umsatzerlöse mit ihrem Beleg, die Summe und die Zeilen der Erklärung und die Differenz. Er hält die Erklärung nie an: Der Verkauf von Anlagevermögen ist eine Lieferung, aber kein Umsatzerlös, eine Anzahlung wird mit ihrer Vereinnahmung versteuert (§ 13 Abs. 1 Nr. 1 Buchstabe a Satz 4 UStG), und ein Erlös, den keine Zeile der Erklärung nimmt, ist kein Umsatz der Erklärung; ob die Differenz erklärt ist, entscheidet das Unternehmen. Die Umsatzerlöse der E-Bilanz neben den Kz 81, 86, 41 und 45 der Voranmeldungen zeigt der Bericht „E-Bilanz Positionen“, siehe [E-Bilanz](ebilanz.md#bericht-e-bilanz-positionen). Wie die Jahresmeldungen eines Jahres aufeinander aufbauen, beschreibt [Zusammenspiel der Jahresmeldungen](jahresmeldungen.md#zusammenspiel-der-jahresmeldungen).

## Befunde und „Bereit“

„Bereit“ heißt: kein Fehler der Befunde, und die Prüfungen des Kerns gehen auf. Das verlangt:

- die Verprobung geht über das Jahr auf, und kein beobachtetes Konto der Stufe „Sperrt“ hat einen Saldo, den keine Zeile liest (`AnnualResult.ready`);
- jeder fällige Zeitraum ist abgegeben oder begründet (`Soll.ready`);
- der Abgleich lässt keinen Rest (`Reconciliation.ready`);
- keine Regel der Jahresdokumentation, die Steuerbote prüft, und keine eigene Prüfung findet einen Fehler, die Paragrafen der Zeilen 46, 52 und 54 eingeschlossen.

| Code | Art | Woher |
|---|---|---|
| `SB-VERPROBUNG` | Fehler | eine Verprobung geht über das Jahr nicht auf; die Tabellen „Verprobung“ und „Abweichende Belege“ nennen die Belege |
| `SB-KONTO-SPERRT` | Fehler | ein Konto der Stufe „Sperrt“ hat im Jahr einen Saldo, den keine Zeile der Erklärung liest |
| `SB-KONTO-AUFGELOEST` | Hinweis | ein Konto, das einen Betrag in eine spätere Voranmeldung trägt, löst über das Jahr den Saldo auf, den es ins Jahr mitbrachte, etwa aus den Eröffnungsbuchungen; das sperrt nicht, siehe [Übergang eines Saldos](ustva-kennzahlen.md#übergang-eines-saldos-in-eine-spätere-voranmeldung) |
| `SB-ZAHLUNG-VOR-START` | Hinweis | ein Beleg des Jahres auf den Konten der Vorauszahlungen zahlt genau Kz 83 einer Voranmeldung vor Steuerbote des Vorjahres, etwa die Zahlung für Dezember im Februar nach einem Start am 1. Januar: Er ist keine Vorauszahlung des Jahres, und der Abgleich der Zahlungen mit dem Vorauszahlungssoll lässt ihn aus (`prior_payments` in `steuerbote/setup/start.py`); sauber ist die Buchung auf „Umsatzsteuer Vorjahr“ |
| `SB-VOR-START` | Fehler | die Bücher in ERPNext beginnen nach dem 1. Januar des Jahres („Bücher in ERPNext ab“), das Hauptbuch hält das Jahr nicht ganz, siehe [Start mit Steuerbote im laufenden Betrieb](einrichtung.md#start-mit-steuerbote-im-laufenden-betrieb) |
| `SB-KONTO-HINWEIS` | Hinweis | ein Konto der Stufe „Hinweis“ hat im Jahr einen Saldo, den keine Zeile liest |
| `SB-KLEINUNTERNEHMER` | Hinweis | die Einstellungen Jahresmeldungen kennzeichnen das Jahr als Jahr eines Kleinunternehmers |
| `SB-KZ136` | Hinweis | eine abgegebene Voranmeldung datiert den Wechsel zur Regelbesteuerung in Kz 70 auf einen anderen Tag als Kz 136 der Erklärung |
| `SB-UMSATZERLOESE` | Hinweis | die Bemessungsgrundlagen der Lieferungen und sonstigen Leistungen liegen über Rundung und Toleranz hinaus neben den Umsatzerlösen des festgestellten Jahresabschlusses oder der abgegebenen E-Bilanz, siehe [Abgleich mit den Umsatzerlösen](#abgleich-mit-den-umsatzerlösen) |
| `SB-NEU-BERECHNEN` | Fehler | seit dem Berechnen hat sich etwas geändert, das „Berechnen“ liest |
| `ZEITRAUM-FEHLT` | Fehler | ein fälliger Zeitraum ohne abgegebene Voranmeldung und ohne Begründung |
| `SONDERVORAUSZAHLUNG-KZ39` | Hinweis | Kz 39 der Voranmeldungen weicht von der Sondervorauszahlung der Einstellungen ab |
| `SOLL-UEBERSCHRIEBEN` | Hinweis | das Vorauszahlungssoll laut Finanzamt ersetzt das berechnete |
| `ZAHLUNGEN` | Hinweis | die Zahlungen im Hauptbuch weichen vom Soll ab |
| `BUCHUNG-NACH-ABGABE` | Hinweis | ein abgegebener Zeitraum hat seit der Abgabe Buchungen bekommen |
| `ABGLEICH-REST` | Fehler | ein unerklärter Rest im Abgleich |
| `VORSTEUER-RECHNUNG` | Hinweis | Steuerbote nimmt die Vorsteuer nach dem Buchungsdatum der Rechnung, der Abzug setzt den Besitz der Rechnung voraus (§ 15 Abs. 1 Satz 1 Nr. 1 Satz 2 UStG) |
| `JOURNALBUCHUNG-STEUERKONTO` | Hinweis | eine Journalbuchung des Jahres bewegt ein Steuerkonto ohne das Kennzeichen „Nicht in der Umsatzsteuer-Voranmeldung“ |
| `NACHSTEUER-ZEILE` | Hinweis | ein Konto von Kz 65 ohne Feld der Erklärung geht in Kz 319 |
| `STEUER-WIE-GEBUCHT` | Hinweis | die gebuchte Steuer einer Steuerzeile liegt mehr als einen Euro neben dem Satz auf die übermittelte Bemessungsgrundlage; die Zeile nimmt die Steuer der genauen Jahresgrundlage |
| `VOLLE-EURO`, `VORZEICHEN`, `STELLEN`, `LAENGE`, `PARAGRAF-FEHLT` | Fehler | die eigenen Prüfungen von `rules.check()`: Cent in vollen Euro, ein Minus ohne Vorzeichen, zu viele Stellen, ein zu langer Text, ein Betrag der Zeilen 46, 52 oder 54 ohne Paragrafen |
| Fehlercode der Jahresdokumentation, etwa `30639` | Fehler oder Hinweis | eine der Regeln, die Steuerbote selbst prüft, mit der Regelart der Jahresdokumentation |

## Angaben der Erklärung

Was die Erklärung über die Beträge hinaus meldet, nimmt sie aus den Einstellungen und dem Beleg, jedes Mal, wenn sie geprüft, gedruckt oder übermittelt wird:

| Zeilen | Angabe | Quelle |
|---|---|---|
| 3 | Kz 110 Berichtigte Steuererklärung | eine Berichtigung |
| 4 | Wirtschafts-Identifikationsnummer | Einstellungen Umsatzsteuer-Voranmeldung |
| 5 | Name des Unternehmers | Name des Unternehmens |
| 7 | Art des Unternehmens | Gegenstand des Unternehmens der Einstellungen Jahresmeldungen |
| 8 bis 11 | Straße, Hausnummer, Zusatz, Adressergänzung, Postleitzahl, Ort | Anschrift der Einstellungen Jahresmeldungen; eine Anschrift im Ausland meldet keine Postleitzahl |
| 14, 15 | Telefon, E-Mail-Adresse | Datenlieferant der Einstellungen Umsatzsteuer-Voranmeldung |
| 18 | Kz 136 | das Feld des Belegs |
| 19 | Dauer der Unternehmereigenschaft | vom Gründungsdatum des Unternehmens bis zum 31. Dezember, wenn es im Jahr gegründet wurde (§ 16 Abs. 3 UStG) |
| 21 | Kz 133 | immer 1, vereinbarte Entgelte (§ 16 Abs. 1 Satz 1 UStG) |
| 22, 23 | Kz 129, Kz 500 mit Text | die Felder des Belegs |
| 95 bis 104 | Kz 370 mit den Grundstücken, Kz 371, 372, 369 und die Gründe | die Felder des Belegs |
| 127 bis 129 | Mitwirkung einer Steuerberatung | in einem Jahr, das die Einstellungen Jahresmeldungen mit Mitwirkung einer Steuerberatung kennzeichnen: die Erklärung der Zeile 127 und die Steuerberatung der Einstellungen |

## Abgabe

- **Fälligkeit:** der Tag, den „Offene Fristen“ für die Umsatzsteuererklärung des Jahres nennt (`annual_deadline`, siehe [Fristen](fristen.md#jahresmeldungen)): sieben Monate nach Ablauf des Jahres, mit Steuerberatung der letzte Tag im Februar des zweiten Folgejahres, bei einer Vorabanforderung der früheste Tag der Vorabanforderungen des Jahres, verschoben auf den nächsten Werktag (§ 149 Abs. 2 bis 4 und § 108 Abs. 3 AO). Für 2026 ist das der 02.08.2027, mit Steuerberatung der 29.02.2028. Steuerberatung und Vorabanforderung stehen je Jahr in den Einstellungen Jahresmeldungen. Ohne Einstellungen Jahresmeldungen hat die Erklärung kein Fälligkeitsdatum, und „Offene Fristen“ nennt sie nicht.
- **Über ERiC:** Prüfen, Testsenden und Senden in der Datenart USt des Jahres (`datenart.ust`) mit den Nutzdaten E50 aus `steuerbote/elster/ust2a_xml.py`, dem Vorsatz und dem Copyrightvermerk der ERiC-Einstellungen. Ohne Hersteller-ID läuft das als Simulation, die die Regeln von USt2A prüft; Senden geht erst mit einer installierten Laufzeitumgebung und der Hersteller-ID. Nach einem angenommenen Senden druckt ERiC ein Freizeichnungsdokument.
- **In Mein ELSTER:** Mein ELSTER importiert keine Umsatzsteuererklärung, es nimmt hochgeladene Formulardaten nur für die Voranmeldung und die Mitteilung nach § 146a Abs. 4 AO. Die Erklärung wird dort nach dem Druckformat „Umsatzsteuererklärung“ eingegeben und mit „In Mein ELSTER abgegeben“ vermerkt; das Formular sagt das im Hinweis der Simulation und an einer bereiten Erklärung.
- **Auf anderem Weg,** etwa durch die Steuerberatung: „Als außerhalb abgegeben vermerken“ mit „Wie und wann abgegeben“.

### Berichtigung

„Berichtigung anlegen“ an einer abgegebenen Erklärung legt eine neue, vollständige Erklärung desselben Jahres mit Kz 110 an (Regel 30002), mit den Korrekturen, Zeilen von Hand, Angaben, Grundstücken und Begründungen der Zeiträume der abgegebenen, und berechnet sie sofort. Ihr Vorauszahlungssoll ist die Kz 816 der abgegebenen Erklärung. Abgegeben, setzt sie die frühere auf „Ersetzt“. Eine abgegebene Erklärung wird nie storniert.

## Druckformat

Das Druckformat „Umsatzsteuererklärung“ gibt die Erklärung in Reihenfolge und Wortlaut des Vordrucks USt 2 A 2026 aus, auf A4, schwarz und grau: den Kopf der Jahresmeldungen mit Finanzamt und dem Tag der Abschlusszahlung, dann die Abschnitte A bis K mit ihren Zwischenüberschriften, die ergänzenden Angaben der Zeile 23 und die Mitwirkung der Zeilen 127 bis 129. Jede Zeile zeigt Zeile, Bezeichnung, Kennzahl und Betrag, die Bemessungsgrundlage in vollen Euro links, die Steuer in Euro und Cent rechts, in den Zeilen 105 bis 108 links den nachträglich abziehbaren und rechts den zurückzuzahlenden Betrag. Ein Abschnitt ohne Werte sagt „Keine Eintragungen“. Darunter stehen das Vorauszahlungssoll, der Abgleich je Voranmeldungszeitraum und je Kennzahl, die Korrekturen und Zeilen von Hand, die Befunde, die Anmerkungen und der Hinweis, dass der Ausdruck keine Abgabe ist. Das Druckformat rechnet nichts: Die Abschnitte gibt `annual_vat_print()` aus `annual_vat_return/layout.py`, das je Jahr den Aufbau des Vordrucks hält.

## Grenzen

- Die Steuer der Steuerzeilen aus der genauen Jahresgrundlage (Option B), Kz 177 = 0 bei einer Erklärung ohne Beträge und ob die Jahreserklärung allein eine Voranmeldung berichtigen darf, sind ungeprüft, siehe `steuerbote/ustjahr`.
- Die Vorsteuer zählt nach dem Buchungsdatum der Rechnung, nicht nach ihrem Eingang.
- Der Hinweis auf die Zahlungen liest das Kalenderjahr; Zahlungen, die einem anderen Jahr gelten, ordnet er nicht zu.
- Die Angaben der Erklärung kommen beim Prüfen, Drucken und Übermitteln aus den Einstellungen, wie sie dann sind; die ELSTER-Übermittlung hält die Nutzdaten jedes Laufs fest.
- Mehrere Betriebsstätten, Anlage UN und Anlage FV, §§ 25 und 25a UStG, die Ist-Versteuerung und die Aufgabe des Unternehmens im Jahr kennt Steuerbote nicht.
- Prüfen und Testsenden mit ERiC folgen mit der Hersteller-ID; bis dahin prüft die Simulation.

## Quellen

- UStG §§ 15 Abs. 1, 15a, 16 Abs. 1 und 3, 18 Abs. 1 bis 4, 19 Abs. 1; UStDV §§ 44 Abs. 3, 48 Abs. 4; AO §§ 108, 149, 153, 168; BGB § 188, gelesen am 23.11.2026 auf gesetze-im-internet.de; UStG § 10 Abs. 1 Satz 1 und § 13 Abs. 1 Nr. 1 Buchstabe a Satz 4, HGB § 277 Abs. 1, gelesen am 24.11.2026 ebenda.
- BMF-Schreiben vom 29. Dezember 2025, III C 3 - S 7344/00040/008/034: Vordruckmuster USt 2 A und Anleitung USt 2 E 2026, mit den Abschnitten A bis K, den Zeilen 124 bis 126 und der Abgabefrist.
- ERiC-Dokumentation 44.3.6.0: Jahresdokumentation E50 2026 (Versionslabel 9.0), Blätter „USt2A - Felder“, „USt2A - Kontexte“ und „USt2A - Regeln“; Entwicklerhandbuch Kap. 5.1.4.3 (Freizeichnungsdokument).
- ELSTER-Hilfe „Benutzeranleitung zum Hochladen von Formulardaten“, Abschnitt „Allgemeines“ (<https://www.elster.de/eportal/helpGlobal?themaGlobal=ustva_upload>).
- DATEV-Kontenrahmen 2026, SKR 03 und SKR 04: die Konten der Umsatzsteuer-Vorauszahlungen.
