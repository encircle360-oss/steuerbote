# Vorgaben der Bilanzzuordnung

Die Bilanzzuordnung sagt für jedes Konto eines Unternehmens, in welche Position der HGB-Taxonomie sein Saldo geht; E-Bilanz und Jahresabschluss lesen dieselbe Zuordnung, siehe [Bilanzzuordnung](architektur.md#bilanzzuordnung-balance-sheet-mapping). Für die DATEV-Kontenrahmen SKR03 und SKR04 bringt Steuerbote Vorgaben mit (`steuerbote/ebilanz/defaults.py`): „Steuerbote einrichten“ und „Vorgaben laden“ legen damit die Zuordnung eines Unternehmens an, „Vorgaben aktualisieren“ bringt spätere Stände in eine bestehende Zuordnung. Diese Seite beschreibt, wie die Vorgaben entstanden sind, nach welchen Regeln sie zuordnen, welche Entscheidungen auffallen und was die Steuerberatung prüfen sollte. Die Vorgaben sind von keiner Steuerberatung bestätigt, und diese Seite ersetzt keine Steuerberatung.

## Umfang

- **Kontenrahmen:** SKR03 und SKR04 in der Ausgabe „Gültig für 2026“, jedes Konto und jeder Kontenbereich, den DATEV beschriftet, auch die der Klasse 9, dazu jedes Konto der Vorlagen von ERPNext 16, das die DATEV-Ausgabe nicht hat. Ein Konto, das DATEV nicht beschriftet, bekommt keine Vorgabe, auch wenn es zwischen zwei beschrifteten liegt: Was ein Unternehmen dort anlegt, ordnet es selbst zu, „Konten prüfen“ nennt es.
- **Taxonomie:** HGB-Taxonomie 6.9, steuerliche Ansicht, für eine GmbH oder UG mit Gesamtkostenverfahren; für 6.10 dieselben Vorgaben bis auf die sonstigen Steuern, siehe [Taxonomie 6.10](#taxonomie-610).
- **Stand:** „SKR03 Taxonomie 6.9 2026.2“ und „SKR04 Taxonomie 6.9 2026.2“. Revision 0 war die leere Tabelle vor den ersten Vorgaben, Revision 1 der Stand vor den [Verrechnungsgruppen](#verrechnungsgruppen) und den Restlaufzeiten kraft Gesetzes.

| Kontenrahmen | Einträge mit Position | beobachtet | außerhalb von Bilanz und GuV |
|---|---|---|---|
| SKR03 | 1127 | 240 | 170 |
| SKR04 | 1203 | 311 | 178 |

Ein Eintrag ist ein Konto oder ein Kontenbereich, wie der Kontenrahmen ihn druckt, etwa SKR04 1210-1214 „Forderungen aus Lieferungen und Leistungen ohne Kontokorrent“; jedes Konto des Unternehmens darin bekommt den Platz des Eintrags mit seiner eigenen Nummer. Von den Einträgen mit Position gehen 91 (SKR03) und 112 (SKR04) auf eine Auffangposition, 182 und 190 haben eine Position bei Gegensaldo, 49 und 51 gehören zur Verrechnungsgruppe „Umsatzsteuer“, 161 und 171 haben eine Restlaufzeit und 23 und 24 die Angabe „Gegenüber Gesellschaftern“; 35 und 39 gelten nur für die Handelsbilanz, 30 und 33 nur für die Steuerbilanz.

## Wie die Vorgaben entstanden sind

- **Quellen.** Die Bezeichnung jedes Kontos und die Spalten Bilanzposten (Fußnote 2) und Abschlusszweck (Fußnote 4) der DATEV-Kontenrahmen; die Bezeichnungen, die definitionGuidance und die steuerlichen Merkmale der Positionen der HGB-Taxonomie 6.9 (Mussfeld, Rechtsform, `notPermittedFor`); der Technische Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025 („Leitfaden“); und die Vorlagen `de_kontenplan_SKR03.json` und `de_kontenplan_SKR04.json` von ERPNext 16 mit ihren Kontotypen. Die Zuordnungstabellen, die DATEV selbst für die E-Bilanz pflegt, sind keine Quelle: Jede Zuordnung folgt aus der Bezeichnung des Kontos und der der Position.
- **Paare.** Ein Konto des SKR03 und sein Gegenstück im SKR04 mit derselben Bezeichnung stehen in einer Zeile und haben denselben Platz, etwa SKR03 1200 und SKR04 1800 „Bank“. Wo die beiden Kontenrahmen sich unterscheiden, hat jedes Konto seine eigene Zeile, etwa SKR03 1702, das die Vorlage von ERPNext anders nutzt als DATEV.
- **Begründung.** Wo die Bezeichnung des Kontos und die der Position die Wahl nicht allein tragen, nennt die Gruppe einen Grund (`Reason`), und `REASONS` gibt ihn mit seiner Quelle: dem Abschnitt des Leitfadens, der definitionGuidance der Position, dem Gesetz oder der Spalte des Kontenrahmens. Jede Auffangposition, jede Position bei Gegensaldo, jedes beobachtete Konto und jeder abweichende Abschlusszweck hat einen.
- **Prüfung.** `steuerbote/ebilanz/tests/test_defaults.py` prüft die Vorgaben gegen die Nummern der Kontenrahmen und der Vorlagen (`steuerbote/ebilanz/tests/datev_charts.py`) und gegen das Paket der Taxonomie: dass jedes beschriftete Konto und jedes Konto der Vorlagen genau einen Platz hat; dass jede Position die Prüfungen der Bilanzzuordnung besteht, auch mit dem Teil, den der Kontotyp der Vorlage dem Konto gibt; dass jede Position die tiefste ist, die die E-Bilanz einer GmbH verlangt; dass Abschlusszweck, Gegensaldo, Restlaufzeit und die Angabe „Gegenüber Gesellschaftern“ den Spalten und Bezeichnungen von DATEV folgen; und dass eine erfundene GmbH mit SKR04 und dieselbe mit SKR03 durch Verteilen und Berechnen eine E-Bilanz ohne Befund ergeben, in der Aktiva und Passiva übereinstimmen.

## Faustregeln

1. **Tiefste Position.** Ein Konto geht in die tiefste Position, die seine Bezeichnung nennt und die die E-Bilanz einer GmbH verlangt: ein Mussfeld oder Summenmussfeld, oder eine Position „Rechnerisch notwendig, soweit vorhanden“ neben Mussfeldern (Leitfaden A.10.1, A.10.3). SKR04 0135 „EDV-Software“ geht in „Konzessionen, gewerbliche Schutzrechte und ähnliche Rechte und Werte sowie Lizenzen an solchen Rechten und Werten“, SKR04 4400 „Erlöse 19 % USt“ in die Umsatzerlöse zum Regelsteuersatz.
2. **Auffangposition, wo das Konto mischt.** Hält ein Konto, was die Taxonomie in Mussfelder teilt, geht es in die Auffangposition „nicht zuordenbar“ oder „ohne Zuordnung“ (Leitfaden A.10.4): SKR04 0200 „Grundstücke, grundstücksgleiche Rechte und Bauten“, 4000-4099 „Umsatzerlöse (Zur freien Verfügung)“ ohne Umsatzsteuertatbestand, 6000 „Löhne und Gehälter“ neben den Vergütungen an Gesellschafter-Geschäftsführer. Verteilen gibt für einen Saldo darauf den Hinweis „BILANZ-AUFFANGPOSITION“: Gibt die Buchführung eine genauere Position her, gehört der Saldo dorthin.
3. **Gegensaldo, wo DATEV zwei Seiten nennt.** Gibt der Bilanzposten des Kontos zwei Seiten an, „… oder …“, hat die Zuordnung eine Position bei Gegensaldo: Ein überzogenes Bankkonto geht in die Verbindlichkeiten gegenüber Kreditinstituten (Leitfaden A.13), eine Umsatzsteuer im Soll in die sonstigen Vermögensgegenstände. Wo DATEV eine Seite nennt, wie bei den Restlaufzeiten von mehr als einem Jahr, bleibt der Saldo auf seiner Position und mindert sie. Die Gegenkonten einer Aufteilung nach Restlaufzeiten bleiben auf der Position der aufgeteilten Konten, damit beide sich aufheben.
4. **Abschlusszweck wie DATEV.** Ein Konto, das DATEV mit HB kennzeichnet, gilt nur für die Handelsbilanz, eines mit SB nur für die Steuerbilanz (Fußnote 4); in der Einheitsbilanz gehen beide nicht ein. Wo der Inhalt eines Kontos nur in einer der beiden Bilanzen vorkommt, sagen die Vorgaben das auch dort, wo DATEV das Konto für beide kennzeichnet: Die latenten Steuern (§ 274 HGB), die Rückstellungen der Steuerstundung nach der Bundessteuerberaterkammer und die Aufwandsrückstellungen (§ 249 Abs. 2 HGB a. F.) gelten nur für die Handelsbilanz, die Auflösung steuerfreier Rücklagen und die Übertragung einer § 6b-Rücklage auf Finanzanlagen nur für die Steuerbilanz. Einem Kennzeichen von DATEV widersprechen die Vorgaben nie.
5. **Gesellschafter.** Jede Position der Ausleihungen, Forderungen und Verbindlichkeiten gegenüber Gesellschaftern hat die Angabe „Gegenüber Gesellschaftern“ für den Vermerk nach § 42 Abs. 3 GmbHG. Jeder Gesellschafter einer GmbH oder UG ist GmbH-Gesellschafter, auch die „sonstigen Gesellschafter“ des Kontenrahmens; ein stiller Gesellschafter ist keiner.
6. **Restlaufzeit aus der Bezeichnung oder dem Gesetz.** Eine Restlaufzeit hat ein Konto, wenn seine Bezeichnung sie nennt, oder „bis 1 Jahr“, wenn das Gesetz die Forderung oder Schuld binnen eines Jahres fällig macht, siehe [Restlaufzeit kraft Gesetzes](#restlaufzeit-kraft-gesetzes). Sonst nennt die Bezeichnung sie: „bis 1 Jahr“, „1 bis 5 Jahre“, „größer 5 Jahre“ und „größer 1 Jahr“, das als „1 bis 5 Jahre“ gilt, denn mehr verlangt der Vermerk der Forderungen nicht (§ 268 Abs. 4 Satz 1 HGB). Die Basiskonten, etwa SKR04 1200 „Forderungen aus Lieferungen und Leistungen“ oder 3300 „Verbindlichkeiten aus Lieferungen und Leistungen“, haben keine; die Offenlegung meldet für einen Saldo darauf „JA-RESTLAUFZEIT-FEHLT“, wo ein Vermerk sie braucht.
7. **Beobachtet, wo eine GmbH das Konto nicht hat.** Konten der Personengesellschaften, Einzelunternehmen und Genossenschaften, etwa das häusliche Arbeitszimmer oder die Geschäftsguthaben der Mitglieder, der Sonder- und Ergänzungsbilanzen, der Einnahmenüberschussrechnung und der atypisch stillen Gesellschaft beobachten die Vorgaben auf der Stufe „Sperrt“, ebenso die der Ergebnisverwendung, die die E-Bilanz von Steuerbote nicht kennt, die Bereiche „(zur freien Verfügung)“ und den steuerlichen Ausgleichsposten, den die Überleitungsrechnung gibt. Ein Saldo darauf hält E-Bilanz und Jahresabschluss an, bis das Konto eine Position hat.
8. **Außerhalb von Bilanz und GuV.** Die statistischen Konten und die Vortragskonten der Klasse 9, die Interimskonten, die zum Bilanzstichtag ausgeglichen sind, und die kalkulatorischen Kosten liegen außerhalb, mit dem Grund aus `Outside`. Ein Saldo darauf gibt einen Hinweis. Geldtransit und das Verrechnungskonto der Ist-Versteuerung können dagegen zum Bilanzstichtag einen Saldo haben; sie gehen wie ihr Bilanzposten bei DATEV in die sonstigen Vermögensgegenstände oder die sonstigen Verbindlichkeiten.
9. **Konten der Vorlagen von ERPNext.** Die Vorlagen von ERPNext bringen Konten früherer DATEV-Ausgaben mit; sie haben ihre eigene Zeile mit der Bezeichnung der Vorlage. Wo die Vorlage einem Konto eine Aufgabe gibt, die DATEV ihm nicht gibt, folgt die Vorgabe der Aufgabe: SKR04 70001 „Wareneingangs-Verrechnungskonto“ und SKR03 1702 sind die Konten der gelieferten, noch nicht berechneten Ware, die Herstellungs-, Verwaltungs- und Vertriebskosten (SKR03 4996-4999, SKR04 6990-6999) sind Materialaufwand.

## Verrechnungsgruppen

„Posten der Aktivseite dürfen nicht mit Posten der Passivseite […] verrechnet werden“ (§ 246 Abs. 2 Satz 1 HGB). Das Verbot trifft Vermögensgegenstände und Schulden, die je für sich bestehen. Forderungen und Verbindlichkeiten gleicher Art gegenüber demselben Gläubiger, die gegeneinander aufgerechnet werden können (§ 387 BGB, für Ansprüche aus dem Steuerschuldverhältnis § 226 Abs. 1 AO), sind dagegen eine einzige Abrechnungsposition; die Kommentierung zu § 246 HGB lässt ihre Verrechnung zu. Für die Umsatzsteuer kommt hinzu, dass die Vorsteuer gar keine eigene Forderung ist: Sie wird von der Steuer desselben Voranmeldungszeitraums abgesetzt (§ 16 Abs. 2 Satz 1 UStG), und was aus früheren Zeiträumen und Jahren offen ist, verrechnet das Finanzamt untereinander. Die üblichen Zuordnungen der Standardkontenrahmen führen die Umsatzsteuerkonten deshalb als Wechselkonten: Der Saldo der ganzen Gruppe entscheidet, ob sie unter den sonstigen Vermögensgegenständen oder den sonstigen Verbindlichkeiten steht.

Die Bilanzzuordnung kennt dafür die **Verrechnungsgruppe** einer Zuordnung (Spalte „Verrechnungsgruppe“ der Zeile). Konten derselben Gruppe gehen alle auf die Seite, die ihr gemeinsamer Saldo zeigt: auf ihre Position oder alle auf die Position bei Gegensaldo, die eine Zuordnung einer Gruppe deshalb haben muss. In der E-Bilanz steht jedes Konto mit seinem Saldo im Kontennachweis dieser Position, ein Konto der anderen Seite mit umgekehrtem Vorzeichen (Leitfaden A.13); im Jahresabschluss und in der Bilanzsumme, die die Größenklasse mitbestimmt (§ 267 Abs. 4a HGB), zählt nur der verrechnete Betrag. Eine verrechnete Gruppe gibt den Hinweis `BILANZ-VERRECHNUNG` mit ihren Konten, dem Betrag und der Seite. Alle anderen Konten behalten ihr eigenes Vorzeichen.

Die Vorgaben bilden eine Gruppe „Umsatzsteuer“ aus den Umsatzsteuerkonten gegenüber dem Finanzamt:

| SKR03 | SKR04 | Inhalt |
|---|---|---|
| 1528, 1529, 1556-1559 | 1376, 1377, 1396-1399 | Berichtigungen der Vorsteuer nach § 15a UStG |
| 1560-1578, 1573, 1584, 1585, 1588 | 1400-1419, 1431-1433, 1436 | abziehbare und aufzuteilende Vorsteuer, Einfuhrumsatzsteuer |
| 1545, 1546, 1539 | 1420-1425 | Forderungen aus Vorauszahlungen und Umsatzsteuerforderungen des laufenden Jahres, des Vorjahres und früherer Jahre |
| 1769-1779, 1782-1791, 1794, 1783 | 3800-3809, 3819, 3832-3845, 3851, 3852 | Umsatzsteuer, Nachsteuer, unrichtig ausgewiesene Steuer, Umsatzsteuer laufendes Jahr, Vorjahr und frühere Jahre |
| 1780, 1781, 1797, 1725 | 3820, 3830, 3860, 3865 | Vorauszahlungen, Sondervorauszahlung, Verbindlichkeiten aus Vorauszahlungen, Steuer in der Folgeperiode fällig |

Nicht in der Gruppe: die Vorsteuer, die erst in einer Folgeperiode abziehbar ist (SKR03 1548, SKR04 1434), und die noch nicht fällige Umsatzsteuer (SKR03 1760-1766, SKR04 3810-3816), weil gegen sie noch nicht aufgerechnet werden kann; die aufgeschobene Einfuhrumsatzsteuer (SKR04 3850), die dem Hauptzollamt geschuldet ist; und die Steuer anderer Mitgliedstaaten. Lohnsteuer, Körperschaft- und Gewerbesteuer verrechnet die Vorgabe nicht mit, obwohl § 226 AO auch das zuließe: Die übliche Darstellung trennt sie, und ob ein Unternehmen sie verrechnet, entscheidet es mit der Steuerberatung, indem es den Zeilen dieselbe Verrechnungsgruppe gibt.

Eine Bank mit Guthaben und eine mit Überziehung, Forderungen an Kunden mit Habensaldo und Konten der Gesellschafter mit beiden Vorzeichen bleiben getrennt: Dort fehlt die Aufrechnungslage gegenüber demselben Gläubiger, oder die Bücher zeigen sie nicht. Ein Konto mit Gegensaldo geht wie bisher für sich auf die Gegenseite (Leitfaden A.13).

## Restlaufzeit kraft Gesetzes

Die Vermerke nach § 268 Abs. 4 Satz 1 und Abs. 5 Satz 1 HGB brauchen die Restlaufzeit jeder Forderung und Verbindlichkeit. Wo die Bezeichnung des Kontos keine nennt, das Gesetz die Forderung oder Schuld aber binnen eines Jahres fällig macht, geben die Vorgaben „bis 1 Jahr“ (`Due` und `DUE_SOURCES` in `steuerbote/ebilanz/defaults.py`):

| Konten | SKR03 | SKR04 | Fälligkeit |
|---|---|---|---|
| Umsatzsteuer und Vorsteuer, die ganze Verrechnungsgruppe und die Vorsteuer der Folgeperiode | wie oben, 1548 | wie oben, 1434 | Vorauszahlung am 10. Tag nach dem Voranmeldungszeitraum (§ 18 Abs. 1 Satz 4 UStG), Abschlusszahlung einen Monat nach der Erklärung (§ 18 Abs. 4 Satz 1 UStG), Erstattung mit der Festsetzung (§ 168 Satz 2, § 220 Abs. 2 AO) |
| Lohn- und Kirchensteuer, Bauabzug | 1741, 1749 | 3730, 3726 | 10. Tag nach dem Anmeldungszeitraum (§ 41a Abs. 1 Satz 1 EStG), 10. Tag nach dem Monat der Zahlung (§ 48a Abs. 1 Satz 1 EStG) |
| Sozialversicherung | 1742, 1759 | 3740, 3759 | drittletzter Bankarbeitstag des Monats (§ 23 Abs. 1 Satz 2 SGB IV) |
| Lohn und Gehalt | 1740, 1755 | 3720, 3790 | nach der Leistung der Dienste (§ 614 BGB) |

Forderungen und Verbindlichkeiten aus Lieferungen und Leistungen bekommen keine Vorgabe: Ihr Zahlungsziel legt der Vertrag fest. Für einen Saldo ohne Restlaufzeit nennt der Jahresabschluss je Vermerk einen Befund `JA-RESTLAUFZEIT-FEHLT` mit allen betroffenen Konten und sagt, wo die Restlaufzeit einzutragen ist.

## Auffällige Entscheidungen

| SKR03 | SKR04 | Vorgabe | Warum |
|---|---|---|---|
| 0050 | 0200 | `bs.ass.fixAss.tan.landBuildings.misc` | Grundstücke, grundstücksgleiche Rechte und Bauten in einem Konto teilt die Taxonomie in Mussfelder; die Auffangposition nimmt es. |
| 0080 | 0230 | `bs.ass.fixAss.tan.landBuildings.buildingsOnOwnLand.buildings` | Den Grund und Boden bebauter Grundstücke hält DATEV auf eigenen Konten; das Konto der Bauten hält den Gebäudeanteil. |
| 0410, 0420, 0430 | 0635, 0640, 0650 | `bs.ass.fixAss.tan.otherEquipm.office` | Geschäfts-, Laden- und Büroeinrichtung sind Geschäftsausstattung. |
| 0450 | 0680 | `bs.ass.fixAss.tan.landBuildings.buildingsOnNonOwnedLand` | „Hier sind auch die Mietereinbauten, sofern es sich um keine technischen Anlagen und Maschinen handelt, einzutragen“ (definitionGuidance der Bauten auf fremden Grundstücken), obwohl DATEV sie unter Betriebs- und Geschäftsausstattung führt. |
| 0501, 0509 | 0803, 0805 | `bs.ass.fixAss.fin.sharesInAffil.partnerships.commPart.other` | Anteile an einer gewerblich tätigen oder geprägten Personengesellschaft sind Anteile an einer Mitunternehmerschaft (§ 15 EStG); die Aufteilung gilt nur steuerlich. |
| 1200 | 1800 | `bs.ass.currAss.cashEquiv.bank` | mit Gegensaldo `bs.eqLiab.liab.bank.other`: ein überzogenes Konto geht in die Verbindlichkeiten gegenüber Kreditinstituten (Leitfaden A.13). |
| 1400 | 1200 | `bs.ass.currAss.receiv.trade.other` | mit Gegensaldo in die übrigen sonstigen Verbindlichkeiten, wie der Bilanzposten von DATEV; ohne Restlaufzeit. |
| 1499 | 1259 | `bs.ass.currAss.receiv.trade.other` | Das Gegenkonto der Aufteilung nach Restlaufzeiten bleibt bei den aufgeteilten Forderungen, ohne Gegensaldo. |
| 1576 | 1406 | `bs.ass.currAss.receiv.other.vat` | Vorsteuer ist eine Forderung gegen das Finanzamt, im Haben eine Verbindlichkeit aus Steuern (Gegensaldo); als Teil der Verrechnungsgruppe „Umsatzsteuer“ entscheidet der Saldo der Gruppe die Seite. |
| 1776 | 3806 | `bs.eqLiab.liab.other.theroffTax` | Umsatzsteuer ist eine Verbindlichkeit aus Steuern, im Soll eine sonstige Forderung (Gegensaldo); als Teil der Verrechnungsgruppe „Umsatzsteuer“ entscheidet der Saldo der Gruppe die Seite. |
| 1507, 1508 | 1330, 1331, 1335 | `bs.ass.currAss.receiv.shareholders.gmbh` | Jeder Gesellschafter einer GmbH oder UG ist GmbH-Gesellschafter, auch die „sonstigen“ des Kontenrahmens. |
| 0951, 1357 | 3009, 1381 | `bs.eqLiab.accruals.pensions.other` | Pensionsrückstellungen zur Saldierung mit Vermögensgegenständen (§ 246 Abs. 2 Satz 2 HGB) teilen die Position mit diesen; welche Art von Zusage sie halten, sagt das Konto nicht, daher die Auffangposition. Übersteigen die Vermögensgegenstände, braucht die Zeile eine Änderung. |
| 0962 | 3050 | `bs.eqLiab.accruals.tax.defTax` | Die Rückstellung der Steuerstundung nach der Bundessteuerberaterkammer ist eine für passive latente Steuern (§ 249 Abs. 1 HGB): nur Handelsbilanz. |
| – | 3098 | `bs.eqLiab.accruals.other` | Aufwandsrückstellungen nach § 249 Abs. 2 HGB a. F. kennt nur die Handelsbilanz. |
| 1702 | 70001 | `bs.eqLiab.liab.trade.genOther` | Die Vorlagen von ERPNext buchen darauf die gelieferte, noch nicht berechnete Ware; SKR03 1702 ohne die Restlaufzeit der DATEV-Bezeichnung. |
| 0820-0829 | – | `bs.eqLiab.equity.subscribed.unpaidCap` | Die nicht eingeforderten ausstehenden Einlagen setzt die Taxonomie vom gezeichneten Kapital ab (§ 272 Abs. 1 Satz 2 HGB). |
| 8400 | 4400 | `is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.generalRateVAT` | Erlöse 19 % USt gehen in die Umsatzerlöse zum Regelsteuersatz. |
| 8340 | 4340 | `is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.otherRateVAT` | 16 % sind kein Steuersatz von heute; die definitionGuidance der sonstigen Umsatzsteuersätze nennt die früherer Jahre. |
| 8000-8099 | 4000-4099 | `is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.unknownVAT` | Ohne Umsatzsteuertatbestand nimmt die Auffangposition „ohne Zuordnung nach Umsatzsteuertatbeständen“ die Erlöse. |
| 4100 | 6000 | `is.netIncome.regular.operatingTC.staff.salaries.nonAllocable` | Löhne und Gehälter jeder Art in einem Konto; die Vergütungen an Gesellschafter-Geschäftsführer sind ein Mussfeld. |
| 4124 | 6024 | `is.netIncome.regular.operatingTC.staff.salaries.managerPartner` | Geschäftsführergehälter der GmbH-Gesellschafter sind Vergütungen an Gesellschafter-Geschäftsführer. |
| 4127 | 6027 | `is.netIncome.regular.operatingTC.staff.salaries.misc` | Die Geschäftsführer, die keine Gesellschafter sind, gehören zu den übrigen Löhnen und Gehältern (definitionGuidance). |
| 4653 | 6643 | `is.netIncome.regular.operatingTC.otherCost.otherOrdinary` | Aufmerksamkeiten wie Kaffee, Tee und Gebäck sind keine Bewirtung (R 4.10 Abs. 5 EStR). |
| 4957 | 6827 | `is.netIncome.regular.operatingTC.otherCost.legalConsulting` | Abschluss- und Prüfungskosten sind Honorare der Steuerberatung und der Wirtschaftsprüfung. |
| 4550 | 6550 | `is.netIncome.regular.operatingTC.otherCost.leaseFix.other` | Eine Garage ist ein unbewegliches Wirtschaftsgut; DATEV gibt das Konto der Gewerbesteuer als Miete dafür weiter. |
| 4996, 4997, 4998, 4999 | 6990, 6992, 6994, 6999 | `is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.misc` | ERPNext bucht auf Herstellungskosten, Verwaltungs- und Vertriebskosten den Wareneinsatz und die bewerteten Kosten, DATEV nutzt sie mit ihrem Gegenkonto statistisch; so oder so gehören sie zum Materialaufwand, in seine Auffangposition. |
| 2250, 2255, 2260, 2265 | 7645, 7649, 7646, 7648 | `is.netIncome.tax.deferred` | Latente Steuern, auch die der Steuerstundung nach der Bundessteuerberaterkammer, kennt nur die Handelsbilanz (§ 274 HGB, § 249 Abs. 1 HGB): Abschlusszweck Handelsbilanz. |
| 2740 | 4935 | `is.netIncome.regular.operatingTC.otherOpRevenue.releasePreTaxRes.other` | Steuerfreie Rücklagen bildet seit dem BilMoG nur die Steuerbilanz; ihre Auflösung gilt nur für sie. |
| 2109 | 7309 | `is.netIncome.regular.fin.netInterest.expenses.regularInterest.misc` | Zinsen an verbundene Unternehmen gehen an die Mutter, an Schwestern oder an Töchter; das Mussfeld der Zinsen an Gesellschafter mit mehr als 25 % und ihnen nahestehende Personen trennt das Konto nicht ab. |
| 3089 | 5189 | `is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.generalRateVAT` | Der letzte Abnehmer eines innergemeinschaftlichen Dreiecksgeschäfts erwirbt nicht innergemeinschaftlich, er schuldet die Steuer einer Lieferung im Inland (§ 25b Abs. 2 UStG). |
| 4228 | 6318 | `is.netIncome.regular.operatingTC.otherCost.misc` | Miet- und Pachtnebenkosten sind keine Miete; Heizung, Wasser und Reinigung haben eigene Positionen. |
| 4400-4499 | 7800-7899 | beobachtet | „(zur freien Verfügung)“: Die Bedeutung der Konten legt das Unternehmen fest. |
| 2860 | 7700 | beobachtet | Ergebnisverwendung nach dem Jahresüberschuss, die die E-Bilanz von Steuerbote nicht zeigt. |
| 1360, 1390 | 1460, 1490 | `bs.ass.currAss.receiv.other.other` | Geldtransit und das Verrechnungskonto der Ist-Versteuerung können zum Bilanzstichtag einen Saldo haben; mit Gegensaldo in die sonstigen Verbindlichkeiten, wie der Bilanzposten von DATEV. |
| 0059 | 0229 | beobachtet | Das häusliche Arbeitszimmer hat nur eine natürliche Person (§ 4 Abs. 5 Satz 1 Nr. 6b EStG). |
| 0810, 0811, 0812 | 2901, 2902, 2903 | beobachtet | Geschäftsguthaben der Mitglieder hat nur eine Genossenschaft (§ 337 Abs. 1 HGB). |
| 9000 | 9000 | außerhalb | Vortragskonto der Eröffnungsbuchungen. |

## Prüfliste für die Steuerberatung

Steuerbote ersetzt keine Steuerberatung. Vor der ersten E-Bilanz und dem ersten Jahresabschluss, die abgegeben werden, prüft die Steuerberatung die Bilanzzuordnung des Unternehmens, besonders diese Punkte:

1. **Freigabe.** Die Vorgaben für SKR03 und SKR04 sind von keiner Steuerberatung bestätigt. Die Bilanzzuordnung jedes Unternehmens gibt die Steuerberatung frei, mit den Konten, die das Unternehmen selbst angelegt hat und die „Konten prüfen“ nennt.
2. **Restlaufzeiten.** Die Steuern, Abgaben der Sozialversicherung und Löhne, die das Gesetz binnen eines Jahres fällig macht, tragen „bis 1 Jahr“; eine gestundete Steuer oder eine Ratenvereinbarung braucht eine andere Restlaufzeit. Die übrigen Basiskonten der Forderungen und Verbindlichkeiten haben keine Restlaufzeit: Für die Vermerke nach § 268 Abs. 4 und 5 HGB nennt die Zuordnung sie, oder das Unternehmen bucht auf die Konten mit Restlaufzeit. „Größer 1 Jahr“ gilt als „1 bis 5 Jahre“; ob eine Forderung länger als fünf Jahre läuft, sagt das Konto nicht.
3. **Auffangpositionen.** Wo die Buchführung genauer trennt als das Konto, etwa Grundstücke mit und ohne Bauten oder Erlöse nach Steuersatz, gehört der Saldo auf ein genaueres Konto oder die Zeile auf eine genauere Position (Leitfaden A.10.4).
4. **Personengesellschaften.** Anteile und Ergebnisse von Personengesellschaften ordnen die Vorgaben einer Mitunternehmerschaft zu; eine vermögensverwaltende Personengesellschaft braucht die Position für ihre Anteile. Diese Positionen sind handelsrechtlich nicht zulässig und können „in einer Handelsbilanz nicht auftreten“ (Leitfaden A.9.2): Eine Handelsbilanz mit Überleitungsrechnung braucht für die Konten eine handelsrechtliche Position und die Überleitung. Die Konten der atypisch stillen Gesellschaft sind beobachtet.
5. **Gesellschafter.** Ob die „sonstigen Gesellschafter“ die der GmbH sind, ob ein Darlehensgeber stiller Gesellschafter ist, und die Bezüge und Tantiemen der Gesellschafter-Geschäftsführung.
6. **Vermögensverrechnung.** Pensionsrückstellungen und vergleichbare Verpflichtungen mit ihren Vermögensgegenständen (§ 246 Abs. 2 Satz 2 HGB) teilen eine Position; übersteigen die Vermögensgegenstände, gehört der Unterschied in den aktiven Unterschiedsbetrag aus der Vermögensverrechnung.
7. **Abschlusszweck.** Latente Steuern, die Steuerstundung nach der Bundessteuerberaterkammer, Aufwandsrückstellungen, Bilanzierungshilfen, selbst geschaffene immaterielle Vermögensgegenstände und andere Konten nur für die Handelsbilanz gehen in keine Einheitsbilanz, ebenso die Konten nur für die Steuerbilanz wie die Auflösung steuerfreier Rücklagen; mit einer Handelsbilanz und Überleitungsrechnung nimmt die Überleitung sie auf.
8. **Konten der Vorlagen von ERPNext.** Wo die Vorlage ein Konto anders nutzt als DATEV: SKR03 1702 als Konto der gelieferten, noch nicht berechneten Ware (ohne Restlaufzeit), SKR04 4910 „Erträge aus Zuschreibungen des Sachanlagevermögens“ und 6910 „Abschreibungen auf Umlaufvermögen außer Vorräte und Wertpapiere (übliche Höhe)“ als Konten der Rundungsdifferenzen, die die Vorgaben nach ihrer DATEV-Bezeichnung zuordnen, und die Herstellungs-, Verwaltungs- und Vertriebskosten als Materialaufwand.
9. **Beobachtete Konten.** Ein Saldo auf einem beobachteten Konto, etwa der Ergebnisverwendung oder eines Bereichs „(zur freien Verfügung)“, hält E-Bilanz und Jahresabschluss an, bis die Zeile eine Position hat. Das trifft die UG, die die gesetzliche Rücklage in der Bilanz bildet (§ 5a Abs. 3 GmbHG), und die GmbH mit einer Vorabausschüttung, solange die E-Bilanz keine Ergebnisverwendung kennt.
10. **Verrechnung.** Ob die Konten der Verrechnungsgruppe „Umsatzsteuer“ verrechnet ausgewiesen werden und ob weitere Steuern gegenüber demselben Finanzamt dazugehören, bestätigt die Steuerberatung (§ 246 Abs. 2 Satz 1 HGB, § 387 BGB, § 226 AO); der Hinweis `BILANZ-VERRECHNUNG` nennt die Konten.

## Eine Zeile ändern

Was für ein Unternehmen anders gelten soll, ändert es in seiner Bilanzzuordnung: Position, Position bei Gegensaldo, Abschlusszweck, „Gegenüber Gesellschaftern“ und Restlaufzeit einer Zuordnung, die Stufe eines beobachteten Kontos, oder ein Konto aus „Beobachtete Konten“ in die Zuordnungen. Speichern prüft die Zeile im Kern und, mit eingerichteter Taxonomie, gegen deren Positionen, siehe [Bilanzzuordnung](architektur.md#bilanzzuordnung-balance-sheet-mapping). Die geänderte Zeile ist eine eigene Änderung: „Vorgaben aktualisieren“ schlägt nicht vor, sie zurückzunehmen. Ein Konto, das das Unternehmen selbst anlegt, bekommt keine Vorgabe; „Konten prüfen“ nennt es, bis es einen Platz hat.

Was für alle Unternehmen anders gelten soll, gehört in die Vorgaben selbst: die Gruppe in `GROUPS` von `steuerbote/ebilanz/defaults.py` mit ihrem Grund, die Revision in `REVISIONS` um eins höher, die SHA-256-Summe des neuen Stands in `DIGESTS` von `test_defaults.py` und diese Seite.

## Neue Revisionen der Vorgaben

Jeder Stand der Vorgaben hat einen Namen aus Kontenrahmen, Version der Taxonomie, Ausgabe des DATEV-Kontenrahmens und Revision, und jeder Name steht für denselben Inhalt; eine Bilanzzuordnung hält den Stand, den sie übernommen hat, mit seinen Zeilen fest. Eine neue Revision erreicht eine bestehende Zuordnung über „Vorgaben aktualisieren“: Der Dialog stellt jede Zeile der Zuordnung neben die Vorgabe von heute und die übernommene Vorgabe und hakt die Änderungen der Vorgaben an, eigene Änderungen nicht, siehe [Vorgaben aktualisieren](einrichtung.md#vorgaben-aktualisieren).

- **Von Revision 0.** Eine Zuordnung, die vor diesen Vorgaben angelegt wurde, hat die leere Tabelle der Revision 0 übernommen. „Vorgaben aktualisieren“ schlägt ihr jede Zeile des Stands 2026.1 als Änderung der Vorgaben vor, angehakt; eine Zeile, die das Unternehmen inzwischen selbst angelegt hat, bleibt eine eigene Änderung. Hat sie noch keine Zeilen, bekommt sie die Vorgaben von heute beim nächsten „Steuerbote einrichten“ wie eine neue Zuordnung, und bis dahin nennt ihr Formular sie über den Feldern.
- **Neue Ausgabe der Kontenrahmen.** Eine neue Ausgabe der DATEV-Kontenrahmen beginnt wieder bei Revision 1, etwa „SKR04 Taxonomie 6.9 2027.1“.
- **Neue Version der Taxonomie.** Eine neue Version der HGB-Taxonomie bekommt eigene Gruppen und einen eigenen Stand, denn ihre Positionen können anders heißen; eine Zuordnung wechselt mit ihrer Version.

## Grenzen

- Nur SKR03 und SKR04 der Ausgabe 2026 und die Vorlagen von ERPNext 16; ein eigener Kontenrahmen hat keine Vorgaben.
- Nur die GmbH und die UG mit Gesamtkostenverfahren; Positionen anderer Rechtsformen und des Umsatzkostenverfahrens nennen die Vorgaben nicht.
- Keine Ergebnisverwendung: Ihre Konten sind beobachtet.
- Restlaufzeiten nur aus der Bezeichnung des Kontos und, mit „bis 1 Jahr“, aus der gesetzlichen Fälligkeit der Steuern, der Sozialversicherung und der Löhne.
- Eine Verrechnungsgruppe nur für die Umsatzsteuer gegenüber dem Finanzamt.
- Ein Konto ohne Beschriftung durch DATEV bekommt keine Vorgabe, auch in einem Bereich zwischen zwei beschrifteten Konten.

## Taxonomie 6.10

Die Vorgaben für die HGB-Taxonomie 6.10 sind die von 6.9, durch die Änderungen der Taxonomie gehoben (`steuerbote/xbrl/changes.py`): 6.10 benennt keine Position der Vorgaben um und entfernt keine. Anders ist nur die Gruppe der sonstigen Steuern, denn 6.10 macht „sonstige Steuern“ zum Summenmussfeld über dem neuen Mussfeld „sonstige Steuern, Grundsteuer“, und ein Saldo auf der Summe neben einem auf der Grundsteuer ergäbe nicht ihre Summe:

| SKR03 | SKR04 | 6.9 | 6.10 |
|---|---|---|---|
| 2375 | 7680 | `is.netIncome.otherTaxes` | `is.netIncome.otherTaxes.GrSt` |
| 4340, 4350, 4355, 4510, 2285, 2287 | 7650, 7675, 7678, 7685, 7690, 7692 | `is.netIncome.otherTaxes` | `is.netIncome.otherTaxes.other` |
| 2289 | 7694 | `is.netIncome.otherTaxes` | `is.netIncome.otherTaxes.releaseTaxProvision` |

Stand: „SKR03 Taxonomie 6.10 2026.1“ und „SKR04 Taxonomie 6.10 2026.1“. Eine Bilanzzuordnung, die „Auf neue Taxonomie heben“ von 6.9 auf 6.10 hebt, behält die übernommenen Vorgaben von 6.9; „Vorgaben aktualisieren“ schlägt ihr diese Zeilen dann als Änderungen der Vorgaben vor.

Für die Steuerberatung zu prüfen:

1. **Grundsteuer.** Die Konten der Grundsteuer gehen in das neue Mussfeld; Grundsteuer, die ein Unternehmen auf einem anderen Konto bucht, gehört ebenfalls dorthin.
2. **Steuern früherer Jahre.** Nachzahlungen und Erstattungen sonstiger Steuern für Vorjahre gehen in „übrige sonstige Steuern“, weil ihre eigenen Positionen „Steuernachzahlungen für Vorjahre“ und „Steuererstattungen für Vorjahre“ steuerlich nicht zulässig sind. Handelsrechtlich gibt es sie; die Vorgaben trennen den Abschlusszweck dafür nicht.

## Quellen

- DATEV-Kontenrahmen nach dem Bilanzrichtlinie-Umsetzungsgesetz, Standardkontenrahmen SKR 03 (Art.-Nr. 11174) und SKR 04 (Art.-Nr. 11175), „Gültig für 2026“: die Bezeichnungen der Konten und Bereiche, Bilanzposten (Fußnote 2), Abschlusszweck (Fußnote 4).
- HGB-Taxonomie 6.9 von esteuer.de (`steuerbote/xbrl/versions.py`): Bezeichnungen, definitionGuidance und steuerliche Merkmale der Positionen.
- Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025: A.10.1 bis A.10.4 (Mussfelder, Summenmussfelder, Auffangpositionen), A.11 (Überleitungsrechnung), A.13 (Kontensalden und Gegensaldo), B.4.2 (Rechtsform), B.9.1.2 (Bilanzgewinn).
- HGB §§ 246 Abs. 2, 266, 267 Abs. 4a, 268 Abs. 4 und 5, 272, 274, 275, 337 Abs. 1; GmbHG § 42 Abs. 3; EStG §§ 4 Abs. 5, 5 Abs. 1a, 15, 37b, 41a, 48a; KStG § 10 Nr. 4; UStG §§ 3a, 4, 15, 16 Abs. 2, 18, 24, 25, 25b; AO §§ 168, 220, 226; BGB §§ 387, 614; SGB IV § 23; EStR R 4.10; LStR R 19.6.
- ERPNext 16 (`version-16`): die Vorlagen `erpnext/accounts/doctype/account/chart_of_accounts/verified/de_kontenplan_SKR03.json` und `de_kontenplan_SKR04.json` mit Kontotypen und Stammtypen.
