# Offenlegung des Jahresabschlusses

Die Geschäftsführer einer GmbH oder UG übermitteln den festgestellten Jahresabschluss „an die das Unternehmensregister führende Stelle“ (§ 325 Abs. 1 Satz 1 HGB), „spätestens ein Jahr nach dem Abschlussstichtag des Geschäftsjahrs“ (§ 325 Abs. 1a Satz 1 HGB). Für eine Kleinstkapitalgesellschaft und eine kleine Gesellschaft schreibt Steuerbote dafür die XBRL-Datei und führt Schritt für Schritt durch das Hochladen auf der Publikations-Plattform. Übermitteln kann Steuerbote nicht: Die Massenschnittstelle des Registers für Jahresabschlüsse gibt es nur auf Anfrage, und jede Person, die übermittelt, identifiziert sich vorher selbst (§ 3a Abs. 1 URV).

Die Datei baut `steuerbote/hgb/instance.py` aus dem Jahresabschluss (`steuerbote/hgb/statement.py`), den Angaben (`steuerbote/hgb/notes.py`), dem, was die Größenklasse offenlegt (`steuerbote/hgb/disclosure.py`), und den Stammdaten der GCD. Die Schritte des Hochladens mit Identifizierung, Gebühren und dem, was danach festzuhalten ist, hält `steuerbote/hgb/upload.py` als Daten mit ihren Quellen. Zeigen soll beides der Beleg Jahresabschluss (`Annual Accounts`), der auch festhält, was das Register antwortet; er ist in Arbeit. Fristen und Feststellung stehen in [Fristen](fristen.md#jahresmeldungen), die Änderung eines Auftrags in [Jahresmeldungen](jahresmeldungen.md#offenlegung).

## Umfang

- **Unternehmen:** eine GmbH oder UG (haftungsbeschränkt), Kleinstkapitalgesellschaft (§ 267a HGB) oder kleine Gesellschaft (§ 267 Abs. 1 HGB). Für eine mittelgroße oder große Gesellschaft nennt Steuerbote nur, was sie offenlegt, und schreibt keine Datei.
- **Geschäftsjahre:** die der HGB-Taxonomie 6.9, die nach dem 31. Dezember 2025 beginnen und vor dem 31. Dezember 2027 enden (`steuerbote/xbrl/versions.py`); das Unternehmensregister nimmt 6.9 seit dem 15. Oktober 2025. Für ein späteres Geschäftsjahr braucht Steuerbote die nächste Taxonomie.
- **Nicht darin:** die Gewinn- und Verlustrechnung, die beide Klassen nicht offenlegen (§ 326 Abs. 1 Satz 1 und Abs. 2 Satz 1 HGB), Lagebericht und Bestätigungsvermerk, die sie nicht haben (§ 264 Abs. 1 Satz 4, § 316 Abs. 1 Satz 1 HGB), der Konzernabschluss und die Übermittlung selbst.

## Was sichtbar wird

| Größenklasse | Weg | Übermittelt | Wer es sieht | Quelle |
|---|---|---|---|---|
| Kleinstkapitalgesellschaft | Hinterlegung, die Vorgabe | die Bilanz mit den Angaben unter der Bilanz | wer sie beantragt, „nur auf Antrag durch Übermittlung einer Kopie“ | § 326 Abs. 2, § 9 Abs. 6 Satz 3 HGB |
| Kleinstkapitalgesellschaft | Veröffentlichung | die Bilanz mit den Angaben unter der Bilanz | jeder im Unternehmensregister | § 326 Abs. 2 HGB |
| kleine Gesellschaft | Offenlegung | die Bilanz und den Anhang ohne die Angaben, die die Gewinn- und Verlustrechnung betreffen | jeder im Unternehmensregister | § 326 Abs. 1 HGB |

Den Weg einer Kleinstkapitalgesellschaft wählt das Feld „Offenlegung als Kleinstkapitalgesellschaft“ der Einstellungen Jahresmeldungen. Das Unternehmensregister zeigt „lediglich die Positionen, zu denen Werte berichtet werden, sowie deren übergeordnete Positionen“ (Arbeitshilfe des Unternehmensregisters), deshalb enthält die Datei nur, was die Klasse offenlegt, und nichts darunter.

## Die XBRL-Datei

Die Datei ist eine Instanz nach XBRL 2.1 auf der HGB-Taxonomie 6.9 im Profil `DISCLOSURE` von `steuerbote/xbrl/profiles.py`, eine Datei je Auftrag:

- **Einstiegsschemata:** die GCD `de-gcd-2025-04-01-shell.xsd` mit „Einzelabschluss MicroBilG“ `de-gaap-ci-2025-04-01-shell-microbilg.xsd` für eine Kleinstkapitalgesellschaft und „Einzelabschluss“ `de-gaap-ci-2025-04-01-shell.xsd` für eine kleine Gesellschaft („Arbeitshilfe für die Einreichung von Jahresabschlüssen/Finanzberichten im XBRL-Format“ des Unternehmensregisters, Stand September 2025).
- **Unternehmen:** jeder Kontext nennt die Gesellschaft mit Registergericht und Registernummer, etwa „Amtsgericht Musterstadt HRB 12345“, im Schema `http://www.handelsregister.de`, denn das Register führt die Gesellschaften danach (§ 3 Abs. 2 URV).
- **Kontexte:** der Abschlussstichtag `I-AKTJAHR`, der des Vorjahres `I-VORJAHR` und das Geschäftsjahr `D-AKTJAHR`, wie der Writer von `steuerbote/xbrl/writer.py` sie schreibt.
- **Beträge:** volle Euro mit `decimals="0"`, aus dem Jahresabschluss in vollen Euro (`in_full_euros()` in `steuerbote/hgb/statement.py`).
- **Gleicher Jahresabschluss, gleiche Datei:** dieselben Eingaben geben dieselben Bytes. Das Erstellungsdatum steht nur darin, wenn die Stammdaten es nennen.

Vor dem Schreiben prüft das Profil die Datei: nur Positionen, die in einer Handelsbilanz zulässig sind (`notPermittedFor` „handelsrechtlich“), nur was die Klasse offenlegt, jeden Posten zu beiden Abschlussstichtagen (§ 265 Abs. 2 Satz 1 HGB), die Rechnung der Taxonomie, die Oberpositionen jeder berichteten Position und die Kontexte. Jeder Fehler dieser Prüfungen und jeder Befund des Jahresabschlusses, der ein Fehler ist, hält die Datei an; ein Hinweis hält nichts an.

### Bilanz

- **Gliederung:** eine Kleinstkapitalgesellschaft „nur die in den Absätzen 2 und 3 mit Buchstaben bezeichneten Posten“, eine kleine Gesellschaft die „mit Buchstaben und römischen Zahlen“ (§ 266 Abs. 1 Satz 4 und 3 HGB), dazu die Summen beider Seiten.
- **Vorjahr:** jeder Posten mit dem Betrag des Vorjahres (§ 265 Abs. 2 Satz 1 HGB). Ein Posten ohne Betrag in beiden Jahren fehlt (§ 265 Abs. 8 HGB), außer ein Posten darunter hat einen: dann steht er, auch mit null, denn „Ist eine Unterposition werthaltig angegeben, so sind auch ihre Oberpositionen werthaltig zu berichten“ (Technischer Leitfaden zur HGB-Taxonomie 6.9, B.14.10).
- **Vermerke:** die „davon“-Positionen der Taxonomie unter einem Posten, den die Klasse zeigt, zu beiden Abschlussstichtagen. Eine Kleinstkapitalgesellschaft vermerkt Restlaufzeiten und Gesellschafter ihrer Forderungen bei „B. Umlaufvermögen“ und ihre Ausleihungen an Gesellschafter bei „A. Anlagevermögen“; die Taxonomie hat diese Vermerke nur unter „B. II.“ und „A. III.“, die eine Kleinstkapitalgesellschaft nicht zeigt. Sie stehen deshalb als Text unter der Bilanz, etwa „B. Umlaufvermögen, davon Forderungen gegen Gesellschafter: 2.500 € (Vorjahr: 1.500 €)“.
- **Gezeichnetes Kapital:** die nicht eingeforderten ausstehenden Einlagen und die eigenen Anteile sind „offen abzusetzen“ (§ 272 Abs. 1 Satz 2 und Abs. 1a Satz 1 HGB). Die Datei nennt dafür den Nennbetrag (`bs.eqLiab.equity.subscribed.corp`) und die Abzüge als positive Beträge (`unpaidCap`, `ownSharesdeducted`), die die Rechnung der Taxonomie abzieht; der Posten behält, was bleibt.
- **Ergebnis:** der Jahresüberschuss oder -fehlbetrag mit Gewinn- oder Verlustvortrag, nach teilweiser Verwendung der Bilanzgewinn mit dem Vortrag als „davon“ (§ 268 Abs. 1 Satz 2 HGB), und ein nicht durch Eigenkapital gedeckter Fehlbetrag auf der Aktivseite und im Eigenkapital (§ 268 Abs. 3 HGB).

### Angaben

Eine Kleinstkapitalgesellschaft macht ihre Angaben „unter der Bilanz“ (§ 264 Abs. 1 Satz 5 HGB), in der Rolle `notesBelowBalanceSheet`; eine kleine Gesellschaft legt ihren Anhang offen (§ 326 Abs. 1 Satz 1 HGB), in der Rolle `notes`. Firma, Sitz, Registergericht und Registernummer und gegebenenfalls die Liquidation (§ 264 Abs. 1a HGB) stehen in beiden Klassen unter der Bilanz, als `notesBelowBalanceSheet.geninfo.company`, `.location`, `.court`, `.number` und `.liquidationOrWindingUp`.

Eine Angabe, die mit „ja“ beantwortet ist, steht mit ihrem Text an der Position der Tabellen und mit dem Betrag ihrer Antwort, wo die Taxonomie für ihn eine Position hat, sonst hinter dem Text. Teilen sich zwei Angaben eine Position, folgen ihre Texte einander in der Reihenfolge des Katalogs von `steuerbote/hgb/notes.py`. Was die Gewinn- und Verlustrechnung betrifft, steht nicht im offengelegten Anhang (§ 326 Abs. 1 Satz 2 HGB), etwa außerplanmäßige Abschreibungen und außergewöhnliche Erträge und Aufwendungen.

**Unter der Bilanz der Kleinstkapitalgesellschaft**

| Angabe | Position | Betrag |
|---|---|---|
| `HAFTUNGSVERHAELTNISSE` | `ntmi.other` | `bs.contingLiab` |
| `ORGANKREDITE` | `nt.relationships.creditsToMembers` | |
| `ZUSAETZLICHE-ANGABEN` | `ntmi.other` | |
| `EIGENKAPITAL-NULL` | `ntmi.other` | |

**Im Anhang der kleinen Gesellschaft**

| Angabe | Position | Betrag |
|---|---|---|
| `ZUSAETZLICHE-ANGABEN` | `nt.additionalNotes.additDisclosuresIfFinStatmntDoesNotPresentTrueAndFairView` | |
| `DARSTELLUNGSSTETIGKEIT` | `nt.genInfo.changeInPresentation` | |
| `VORJAHRESBETRAEGE` | `nt.genInfo.lackOfComparabilityToPriorStatements` | |
| `MITZUGEHOERIGKEIT` | `nt.genInfo.asetsOrLiabilitiesUnderServeralHeadings` | |
| `HAFTUNGSVERHAELTNISSE` | `nt.otherInfo.contingLiab` | `bs.contingLiab` |
| `BEWERTUNGSMETHODEN` | `nt.genInfo.measurement` | |
| `METHODENABWEICHUNGEN` | `nt.genInfo.changeInMeasuremt` | |
| `FREMDKAPITALZINSEN` | `nt.genInfo.interestInManufCost` | |
| `VERBINDLICHKEITEN` | `nt.bsInfo.totalAmountLiabOver5Years` | |
| `FINANZIELLE-VERPFLICHTUNGEN` | `nt.otherInfo.contingLiab` | |
| `ARBEITNEHMER` | | `nt.employeesAveragePeriod` |
| `ORGANKREDITE` | `nt.relationships.creditsToMembers` | |
| `FIRMENWERT` | `nt.isInfo.reasonsGoodwillAmortisationsLonger5Years` | |
| `MUTTERUNTERNEHMEN` | `nt.assocComp.parentsNameSmall` | |
| `ZEITWERT` | `nt.genInfo` | |
| `BEWERTUNGSEINHEITEN` | `nt.genInfo.DisclosuresMasurementUnits` | |
| `VERRECHNUNG` | `nt.genInfo.DisclosuresOffsetAssets` | |

- **Haftungsverhältnisse:** Art für Art in vollen Euro zum Abschlussstichtag unter `bs.contingLiab`, was die Altersversorgung und verbundene oder assoziierte Unternehmen betrifft „jeweils gesondert“, und die gewährten Pfandrechte und sonstigen Sicherheiten im Text (§ 268 Abs. 7 HGB). Die Beträge der Arten ergeben zusammen den Betrag der Antwort.
- **Vorschüsse und Kredite:** je Personengruppe als Text mit Betrag, Zinssätzen, wesentlichen Bedingungen, den im Geschäftsjahr zurückgezahlten oder erlassenen Beträgen und den zu ihren Gunsten eingegangenen Haftungsverhältnissen (§ 285 Nr. 9 Buchst. c HGB).
- **Arbeitnehmer:** die durchschnittliche Zahl als Zahl mit ihren Nachkommastellen (§ 285 Nr. 7 HGB).
- **Unterschriften:** „Der Jahresabschluß ist vom Kaufmann unter Angabe des Datums zu unterzeichnen.“ (§ 245 Satz 1 HGB) Die kleine Gesellschaft nennt jeden Geschäftsführer als „Unterschrift der Geschäftsleitung“ (`nt.directorsSign`) mit Funktion, Ort und Tag einmal, wenn alle sie teilen, sonst bei jeder Person. Die Kleinstkapitalgesellschaft hat keinen Anhang; ihre Unterschriften schließen den Text unter der Bilanz, etwa „Musterstadt, 12. Mai 2027: gez. Erika Beispiel, Geschäftsführerin“.
- **Zeichen:** Texte behalten die Zeichen von ELSTER; die üblichen typografischen ersetzt Steuerbote Zeile für Zeile, ein anderes Zeichen nennt ein Befund, der die Datei anhält, bis der Text geändert ist.

### Stammdaten (GCD)

Die GCD ist „ein Modul mit allgemeinen Informationen über das Dokument, den Bericht und das berichtende Unternehmen“ (Arbeitshilfe des Unternehmensregisters). Welche ihrer Felder das Register braucht, ist ungeprüft; seine Informationen für Softwareanbieter stehen erst nach einer Freischaltung bereit. Die Datei enthält deshalb jedes Feld von `de-gcd-2025-04-01`, das ein festgestellter Jahresabschluss einer kleinen GmbH füllt, in dieser Reihenfolge:

| Feld | Wert | Quelle |
|---|---|---|
| `genInfo.doc.id.generationDate` | der Tag, an dem die Datei geschrieben wird, wenn die Stammdaten ihn nennen | |
| `genInfo.report.id.reportType` | `JA` „Art des Berichts, Jahresabschluss“ | § 325 Abs. 1 Satz 1 HGB |
| `genInfo.report.id.reportStatus.reportStatus.dateofapproval` | der Tag der Feststellung | § 328 Abs. 1a Satz 1 HGB |
| `genInfo.report.id.reportStatus` | `E` „endgültig“ | § 325 Abs. 1 Satz 1 Nr. 1 HGB |
| `genInfo.report.id.revisionStatus` | `E` „erstmalig“, für einen geänderten Jahresabschluss der Status der Stammdaten | § 325 Abs. 1b Satz 1 HGB |
| `genInfo.report.id.reportElement` | `B` „Bilanz“ und `H` „Angaben unterhalb der Bilanz“, für eine kleine Gesellschaft dazu `SA` „andere Anhangangaben“ | § 326 Abs. 1 Satz 1 und Abs. 2 Satz 1 HGB |
| `genInfo.report.id.reportElement.allocation.genInfo` | `toBalance` „Angaben unter der Bilanz“ | § 264 Abs. 1a HGB |
| `genInfo.report.id.reportElement.allocation.notesMicroBilG` | `toBalance`, nur für eine Kleinstkapitalgesellschaft | § 264 Abs. 1 Satz 5 HGB |
| `genInfo.report.id.reportElement.allocation.contingencies` | `toBalance` für eine Kleinstkapitalgesellschaft, `inNotes` für eine kleine Gesellschaft, wenn Haftungsverhältnisse angegeben sind | § 268 Abs. 7 HGB |
| `genInfo.report.id.statementType` | `E` „Jahresabschluss“ | |
| `genInfo.report.id.incomeStatementendswithBalProfit` | ob die Bilanz einen Bilanzgewinn ausweist | § 268 Abs. 1 Satz 2 HGB |
| `genInfo.report.id.accountingStandard` | `HGBM` „deutsches Handelsrecht“ | |
| `genInfo.report.id.specialAccountingStandard` | `K` „Kerntaxonomie“ | |
| `genInfo.report.id.incomeStatementFormat` | `GKV` oder `UKV`, das Verfahren der nicht offengelegten Gewinn- und Verlustrechnung | § 275 Abs. 1 HGB |
| `genInfo.report.id.consolidationRange` | `EA` „nicht konsolidiert/ Einzelabschluss“ | |
| `genInfo.report.period.fiscalYearBegin` | Beginn des Geschäftsjahres | |
| `genInfo.report.period.fiscalYearEnd` | Ende des Geschäftsjahres | |
| `genInfo.report.period.balSheetClosingDate` | Abschlussstichtag | |
| `genInfo.report.period.fiscalPreviousYearBegin` | Beginn des Vorjahres, wenn es eines gibt | § 265 Abs. 2 HGB |
| `genInfo.report.period.fiscalPreviousYearEnd` | Ende des Vorjahres, ebenso | § 265 Abs. 2 HGB |
| `genInfo.report.period.balSheetClosingDatePreviousYear` | Abschlussstichtag des Vorjahres, ebenso | § 265 Abs. 2 HGB |
| `genInfo.report.audit.noAudit` | `noAuditRequi` „keine Abschlussprüfung durchgeführt, keine Prüfungspflicht“ | § 316 Abs. 1 Satz 1 HGB |
| `genInfo.company.id.name` | die Firma | § 264 Abs. 1a Satz 1 HGB |
| `genInfo.company.id.legalStatus` | `GMBH` „Gesellschaft mit beschränkter Haftung“, auch für eine UG: die Taxonomie dokumentiert `legalStatus.UG` als „Nicht vorgesehen für Bundesanzeiger, Erfassung unter "Gesellschaft mit beschränkter Haftung"“ | Taxonomie 6.9 |
| `genInfo.company.id.FoundationDate` | der Tag der Gründung, wenn die Stammdaten ihn nennen | |
| `genInfo.company.id.Incorporation.Type` | `HR` „Handelsregister“ | § 264 Abs. 1a Satz 1 HGB |
| `genInfo.company.id.Incorporation.court` | das Registergericht | § 264 Abs. 1a Satz 1 HGB |
| `genInfo.company.id.sizeClass` | `KstK` „Kleinstkapitalgesellschaft“ oder `KK` „kleine Kapitalgesellschaft“ | §§ 267, 267a HGB |
| `genInfo.company.id.reportedSizeClassBs` | `Kst` oder `K`, die Gliederung der Bilanz | § 266 Abs. 1 Satz 3 und 4 HGB |
| `genInfo.company.id.location` | der Sitz | § 264 Abs. 1a Satz 1 HGB |
| `genInfo.company.id.location.street` | Straße der Anschrift, wenn die Stammdaten sie nennen | |
| `genInfo.company.id.location.houseNo` | Hausnummer, ebenso | |
| `genInfo.company.id.location.zipCode` | Postleitzahl, ebenso | |
| `genInfo.company.id.location.city` | Ort, ebenso | |
| `genInfo.company.id.location.country` | Land, ebenso | |
| `genInfo.company.id.idNo` | die Registernummer als `type.companyId.HRN` „Handelsregisternummer“ | § 264 Abs. 1a Satz 1 HGB |
| `genInfo.company.id.CompanyStatus` | `L` „in Liquidation“, nur für eine Gesellschaft in Liquidation | § 264 Abs. 1a Satz 2 HGB |
| `genInfo.company.disclosureCriterion.scope.CapitalMarketOrientationHGBs264d` | `false`: „Eine Kapitalgesellschaft im Sinn des § 264d gilt stets als große.“ | § 267 Abs. 3 Satz 2 HGB |

Nicht darin sind die Personen, die die Datei erstellt haben (`genInfo.doc.author`), und die Gesellschafter: Beides gehört nicht zum Jahresabschluss, und das Register veröffentlicht, was es erhält.

### Befunde

Was den Jahresabschluss anhält, hält die Datei an: die Fehler der Bilanz beider Jahre, offene oder unvollständige Angaben, fehlende Angaben nach § 264 Abs. 1a HGB, eine Feststellung im Geschäftsjahr. Dazu kommen die Befunde der Datei selbst, alle Fehler:

| Code | Bedeutung |
|---|---|
| `JA-XBRL-ZEICHEN` | ein Text hat Zeichen, die ELSTER nicht nimmt |
| `JA-XBRL-ARBEITNEHMER` | die Angabe der Arbeitnehmer hat keine Zahl |
| `JA-XBRL-EINTRAEGE` | zu Haftungsverhältnissen oder Vorschüssen sind Einträge erfasst, die Angabe ist aber nicht mit „ja“ beantwortet |
| `JA-XBRL-BETRAG` | der Betrag einer Angabe ist nicht die Summe ihrer Einträge |

## Hochladen auf der Publikations-Plattform

Die Schritte gibt `upload.steps()`; die Testplattform entfällt nach dem ersten echten Upload, die Hinterlegung für eine Gesellschaft, die veröffentlicht.

1. **Testplattform:** Vor dem ersten echten Upload die XBRL-Datei auf der Testplattform des Bundesanzeiger Verlags hochladen. Sie prüft „die Kompatibilität Ihrer XBRL-Dateien unabhängig von der regulären Auftragsübermittlung“; den Zugang gibt es auf Anfrage an testplattform@rt.bundesanzeiger.de.
2. **Registrieren:** einmal auf www.publikations-plattform.de, für die Gesellschaft selbst oder als Einsender für Dritte, etwa die Steuerberatung. Für Übermittlungen an das Unternehmensregister nennt die Registrierung Firma, Registergericht, Registerart und Registernummer (§ 3 Abs. 2 URV).
3. **Identifizieren:** vor der ersten Übermittlung einmal je Person, die hochlädt, elektronisch (§ 3a Abs. 1 URV), nach einer Namensänderung neu. Ohne Identifizierung lässt sich kein Jahresabschluss übermitteln.
4. **Auftrag anlegen:** angemeldet unter „Auftragsübermittlung“ ein Auftrag an das Unternehmensregister für den Jahresabschluss des Geschäftsjahres.
5. **Hinterlegung wählen:** nur für eine Kleinstkapitalgesellschaft, die hinterlegt, den Haken setzen, dass sie die Voraussetzungen erfüllt. Der Haken ist die Mitteilung nach § 326 Abs. 2 Satz 2 HGB; ohne ihn ist der Auftrag keine Hinterlegung.
6. **XBRL-Datei hochladen:** die Datei von Steuerbote auf der Upload-Seite des Auftrags, „nur eine Datei pro Auftrag“. XML ist das Format der Übermittlung (§ 11 Abs. 2 Satz 1 Nr. 4 URV); für Word, RTF, Excel oder PDF fiele neben der Gebühr ein Konvertierungsentgelt an.
7. **Auftragsbestätigung ablegen:** Der Auftrag steht unter „Meine Daten“, „Aufträge & Abrufe“; über „Ansehen“ lässt sich die Auftragsbestätigung ausdrucken. Der Tag der Übermittlung wahrt die Frist (§ 325 Abs. 4 Satz 2 HGB).
8. **Beleg ablegen:** Nach der Einstellung in das Unternehmensregister steht dort ein PDF-Beleg bereit.

### Identifizierung und Gebühren

Die Identifizierung kostet einmal je Person (Nr. 1441 KV JVKostG):

| Weg | Gebühr | Quelle |
|---|---|---|
| Online-Ausweisfunktion des Personalausweises, der eID-Karte oder des Aufenthaltstitels, oder ein elektronisches Identifizierungsmittel eines anderen Mitgliedstaats | 12,00 € | Nr. 1441 Buchst. a KV JVKostG; § 3a Abs. 1 Satz 3 Nr. 1 und 2 URV |
| Videoidentifizierung der registerführenden Stelle, automatisch oder begleitet | 22,00 € | Nr. 1441 Buchst. b KV JVKostG; § 3a Abs. 1 Satz 3 Nr. 3 URV |
| Identifizierung über die Steuerberaterplattform | 7,60 € | Nr. 1441 Buchst. c KV JVKostG; § 3a Abs. 4 URV |

Das Register berechnet für die Einstellung des Jahresabschlusses einer Kleinstkapitalgesellschaft 18,50 € (Nr. 1420 KV JVKostG) und einer kleinen Gesellschaft 25,00 € (Nr. 1421 KV JVKostG), dazu 3,00 € im Jahr für eine Gesellschaft mit den Erleichterungen des § 326 HGB (Nr. 1410 KV JVKostG). Unterlagen, die vor der Einstellung geändert übermittelt werden, kosten die Hälfte mehr, eine Rücknahme die Hälfte (Vorbemerkung 1.4.2 Abs. 2 und 3 KV JVKostG). `upload.costs()` gibt die Gebühren eines Jahresabschlusses, auf Wunsch mit der Identifizierung.

### Was danach festzuhalten ist

Der Jahresabschluss hält fest, was der Upload ergibt (`upload.RECORDS`): Übermittelt am, Übermittelt von, Auftragsnummer, Auftragsbestätigung, Eingestellt am, Beleg und Gebühren. Die Auftragsnummer nennt eine Berichtigung oder Ergänzung mit dem Tag der Veröffentlichung oder Hinterlegung.

## Ungeprüft

- Welche Felder der GCD das Unternehmensregister braucht: Die Datei füllt jedes, das die Taxonomie für einen festgestellten Jahresabschluss einer kleinen GmbH vorsieht.
- Ob das Register die Beträge in vollen Euro erwartet; die Datei schreibt `decimals="0"`.
- Welche Kennung des Unternehmens das Register im Kontext erwartet; die Datei nennt Registergericht und Registernummer im Schema `http://www.handelsregister.de`.
- Die Vermerke einer Kleinstkapitalgesellschaft, die die Taxonomie nur unter Posten hat, die sie nicht zeigt, stehen als Text unter der Bilanz.
- Die Beträge der Haftungsverhältnisse des Vorjahres schreibt die Datei nicht: Ob § 265 Abs. 2 HGB sie verlangt, ist ungeprüft.
- Die Positionen der Angaben im Anhang folgen den Bezeichnungen der Taxonomie 6.9 und warten wie der Katalog auf die Durchsicht einer Steuerberatung; für die Angaben zum beizulegenden Zeitwert (§ 285 Nr. 20 HGB) hat die Taxonomie keine eigene Position, sie stehen unter der Überschrift `nt.genInfo`.
- Die Prüfungen des Registers über XBRL 2.1, XBRL Dimensions 1.0 und die Rechnung der Taxonomie hinaus; deshalb vor dem ersten echten Upload die Testplattform.
- Die Felder des Webformulars für kleine Gesellschaften: Das Formular braucht eine Anmeldung, `upload.web_form()` nennt die Felder, wie Steuerbote sie erwartet.
- Ob das Register auf die Gebühren Umsatzsteuer berechnet.

## Prüfung der Datei

Die Tests unter `steuerbote/hgb/tests` schreiben die Dateien zweier erfundener Gesellschaften, einer Kleinstkapitalgesellschaft und einer kleinen GmbH, und vergleichen sie in kanonischer Form mit den Dateien unter `steuerbote/hgb/tests/fixtures`. Sie laufen gegen einen Auszug der Taxonomie 6.9 (`steuerbote/hgb/tests/taxonomy.py`) und, mit `STEUERBOTE_TAXONOMY_6_9`, gegen das Paket selbst: Jedes Konzept und jede Beziehung des Auszugs steht so im Paket, jede Position einer Angabe gibt es in beiden Ansichten, und die Dateien sind gegen das Paket dieselben. Der XBRL-Job der CI lässt Arelle die Dateien dieser Gesellschaften und ihrer Abwandlungen gegen das Paket prüfen (`steuerbote/xbrl/tests/arelle_validation.py`), nach XBRL 2.1, XBRL Dimensions 1.0 und der Rechnung der Taxonomie.

## Quellen

- HGB §§ 9, 245, 264, 265, 266, 267, 267a, 268, 272, 275, 284, 285, 288, 316, 325, 326, 328; URV §§ 3, 3a, 11; JVKostG, Anlage 1 (Kostenverzeichnis), Hauptabschnitt 4 mit Vorbemerkung 1.4.2 und Nr. 1410, 1420, 1421 und 1441, gelesen am 23.11.2026 auf gesetze-im-internet.de.
- Unternehmensregister, „Arbeitshilfe für die Einreichung von Jahresabschlüssen/Finanzberichten im XBRL-Format“, Stand September 2025.
- Publikations-Plattform, gelesen am 23.11.2026: „So geht's: Jahresabschluss Veröffentlichung“, „So geht's: Jahresabschluss Hinterlegung“, „So geht's: Registrieren / Identifizieren“, „Fragen und Antworten: Aufträge an das Unternehmensregister“ und „Übermittlung von Jahresabschlüssen“, „Arbeitshilfen: XBRL-Programm“ (<https://www.publikations-plattform.de>).
- HGB-Taxonomie 6.9 vom 1. April 2025 (esteuer.de), Module `de-gcd-2025-04-01` und `de-gaap-ci-2025-04-01` mit ihren Bezeichnungen; Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025.
- Einheitliche Elster-Datenschnittstelle XML, Kap. 2.2, und ERiC E-Bilanz-Dokumentation für HGB-Taxonomie 6.9, Kap. 3.16: die Zeichen der Texte.
