# Jahresabschluss

Eine GmbH oder UG stellt für jedes Geschäftsjahr einen Jahresabschluss auf, Bilanz und Gewinn- und Verlustrechnung (§ 242 Abs. 3, § 264 Abs. 1 Satz 1 HGB), die Gesellschafter stellen ihn fest (§ 42a Abs. 2 Satz 1 GmbHG), und die Geschäftsführer übermitteln ihn an das Unternehmensregister (§ 325 Abs. 1 Satz 1 HGB). Steuerbote berechnet ihn als Beleg „Jahresabschluss“ (`Annual Accounts`) aus dem Hauptbuch über die Bilanzzuordnung, entscheidet die Größenklasse, stellt die Angaben ihres Katalogs zusammen, hält die Feststellung und die Ergebnisverwendung fest, zeigt in einer Vorschau, was die Offenlegung sichtbar macht, schreibt die XBRL-Datei für das Unternehmensregister und hält fest, was das Register nach dem Upload antwortet. Diese Seite ersetzt keine Steuerberatung.

Der Beleg lebt auf der Grundlage der Jahresmeldungen mit dem Lebenslauf `ACCOUNTS`: Status, Berechnen, Korrekturen, Befunde, Feststellung und Änderung stehen in [Jahresmeldungen](jahresmeldungen.md). Die XBRL-Datei und das Hochladen auf der Publikations-Plattform beschreibt [Offenlegung des Jahresabschlusses](offenlegung.md), die Fristen der Feststellung und der Offenlegung [Fristen](fristen.md#jahresmeldungen), die Bilanzzuordnung [Architektur](architektur.md#bilanzzuordnung-balance-sheet-mapping).

## Umfang

- **Unternehmen:** eine GmbH oder UG (haftungsbeschränkt) mit den Einstellungen Jahresmeldungen und einer Bilanzzuordnung. Für eine Kleinstkapitalgesellschaft (§ 267a HGB) und eine kleine Gesellschaft (§ 267 Abs. 1 HGB) bereitet Steuerbote alles vor, was die Offenlegung braucht; für eine mittelgroße oder große Gesellschaft berechnet und druckt der Beleg Bilanz und Gewinn- und Verlustrechnung, Anhang und Offenlegung übernimmt die Steuerberatung oder der Abschlussprüfer.
- **Geschäftsjahre:** das Geschäftsjahr von ERPNext, das im Jahr des Belegs endet, für die Offenlegung eines der HGB-Taxonomie 6.9, siehe [Umfang der Offenlegung](offenlegung.md#umfang). Steuerbote kennt Schwellen der Größenklassen und Gliederungen heute für 2026 (`schemes.years()`); einen Jahresabschluss für ein anderes Jahr lehnt schon das Anlegen ab, mit der Meldung „Steuerbote hat noch keinen Jahresabschluss für …“.
- **Gliederung:** die Bilanz nach § 266 HGB in der Kontoform der Größenklasse und die Gewinn- und Verlustrechnung nach dem Gesamtkostenverfahren (§ 275 Abs. 2 HGB), denn das Hauptbuch kennt die Art eines Aufwands, nicht seine Funktion (`steuerbote/hgb/schemes.py`).
- **Nicht darin:** Lagebericht, Konzernabschluss, Umsatzkostenverfahren, Tabellen der Haftungsverhältnisse und der Vorschüsse und Kredite an Organmitglieder (sie stehen im Text und Betrag ihrer Angabe), die Steuerbilanz und die Übermittlung selbst, siehe [Grenzen](#grenzen).

## Ablauf

1. **Einrichten:** die Einstellungen Jahresmeldungen mit Rechtsform, Sitz, Registergericht und Registernummer, Geschäftsführern, Abschlusskonto und Größenmerkmalen, die Bilanzzuordnung („Steuerbote einrichten“ legt sie an, siehe [Einrichtung](einrichtung.md#die-schritte)) und die HGB-Taxonomie 6.9 („Taxonomie einrichten“ in den ERiC-Einstellungen).
2. **Anlegen und Berechnen:** ein Beleg je Unternehmen und Jahr, benannt nach dem Jahr (`JA-2026-00001`); „Berechnen“ liest die Bücher und füllt Größenklasse, Posten, Angaben und Unterzeichner.
3. **Prüfen und ergänzen:** die Angaben beantworten, Posten mit Begründung korrigieren, wo die Bücher kein Vorjahr haben das Vorjahr von Hand eintragen, wo nötig Größenklasse oder Arbeitnehmer von Hand mit Begründung; jede Änderung verlangt ein neues „Berechnen“.
4. **Feststellen:** den Tag der Feststellung und die Daten der Unterschriften eintragen, „Berechnen“, dann „Buchen“: Das ist die Feststellung, siehe [Feststellung](#feststellung).
5. **Ergebnisverwendung buchen**, wo die Gesellschafter in die Rücklagen einstellen oder ausschütten.
6. **Offenlegen:** „Vorschau der Offenlegung“ und „XBRL für das Unternehmensregister“, das Hochladen auf der Publikations-Plattform nach [Offenlegung des Jahresabschlusses](offenlegung.md#hochladen-auf-der-publikations-plattform), dann „Übermittlung festhalten“ und, sobald das Register eingestellt hat, „Einstellung festhalten“.

## Der Beleg

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company`, `year` | Unternehmen, Jahr | Pflicht; das Jahr ist das, in dem das Geschäftsjahr endet |
| `fiscal_year`, `from_date`, `to_date`, `status`, `ready`, `deadline`, `is_correction`, `corrects`, `findings`, `filed_via`, `filed_on`, `transferticket`, `filed_by`, `filing_note`, `remarks` | | die Felder jedes Belegs einer Jahresmeldung, siehe [Felder jedes Belegs](jahresmeldungen.md#felder-jedes-belegs); `deadline` ist der letzte Tag der Feststellung, „Übermittlung festhalten“ setzt `filed_via` auf `upload` und `filed_on` auf den Tag des Uploads, und eine Berichtigung gibt es nicht |
| `disclosure_deadline` | Offenlegung fällig am | der letzte Tag der Übermittlung an das Unternehmensregister (§ 325 Abs. 1a Satz 1 HGB), wie „Offene Fristen“ ihn führt |
| `bilanzsumme`, `umsatzerloese` | Bilanzsumme, Umsatzerlöse | setzt „Berechnen“ aus der Bilanz und der Gewinn- und Verlustrechnung in der Form einer kleinen Gesellschaft; die Bilanzsumme ohne einen nicht durch Eigenkapital gedeckten Fehlbetrag (§ 267 Abs. 4a HGB) |
| `employees_counted`, `headcount_detail` | Gezählte Arbeitnehmer, Arbeitnehmer je Quartalsende | der Durchschnitt der Mitarbeiter an den vier Quartalsenden und die Zahl je Quartalsende, siehe [Arbeitnehmer](#arbeitnehmer) |
| `employees_override`, `employees_override_reason` | Arbeitnehmer von Hand, Begründung der Arbeitnehmer von Hand | zählen, sobald die Begründung steht, auch null |
| `employees` | Arbeitnehmer | die Zahl, mit der Größenklasse und Angabe rechnen: von Hand oder gezählt |
| `prior_bilanzsumme`, `prior_umsatzerloese`, `prior_employees`, `prior_criteria_source`, `prior_size_class` | Bilanzsumme des Vorjahres, Umsatzerlöse des Vorjahres, Arbeitnehmer des Vorjahres, Merkmale des Vorjahres aus, Größenklasse des Vorjahres | die Merkmale des vorigen Abschlussstichtags und woher sie stammen, siehe [Größenklasse](#größenklasse) |
| `size_class_computed`, `size_basis` | Entschiedene Größenklasse, Grundlage der Größenklasse | was § 267 HGB aus beiden Abschlussstichtagen entscheidet, und auf welcher Grundlage |
| `size_class_override`, `size_class_override_reason` | Größenklasse von Hand, Begründung der Größenklasse von Hand | gilt mit ihrer Begründung statt der entschiedenen |
| `size_class` | Angewandte Größenklasse | die Klasse, nach der der Beleg gliedert und offenlegt |
| `presentation` | Ausweis des Ergebnisses | vor Verwendung des Jahresergebnisses oder nach teilweiser Verwendung (§ 268 Abs. 1 HGB); leer setzt das Speichern ihn nach der Rechtsform, eine UG nach teilweiser Verwendung, denn sie bildet ihre gesetzliche Rücklage in der Bilanz des Jahres (§ 5a Abs. 3 Satz 1 GmbHG) |
| `net_income`, `carried_forward`, `equity` | Jahresergebnis, Gewinnvortrag/Verlustvortrag, Eigenkapital | aus der Bilanz und der Gewinn- und Verlustrechnung mit den Korrekturen; der Gewinnvortrag nach teilweiser Verwendung aus dem Vermerk beim Bilanzgewinn |
| `has_prior`, `prior_from_date`, `prior_to_date` | Mit Vorjahr, Vorjahr vom, Vorjahr bis | ob der Abschluss ein Vorjahr hat, und sein Geschäftsjahr |
| `statement_data` | Grundlagen des Abschlusses | verborgen: die Salden mit den Korrekturen, das Vorjahr und der Teil der Taxonomie, aus denen die Bilanz entsteht, damit die XBRL-Datei eines festgestellten Abschlusses dessen Beträge trägt, was die Bücher später auch sagen |
| `lines` | Posten von Bilanz und GuV | Tabelle „Posten des Jahresabschlusses“, siehe [Posten](#posten) |
| `prior_entries`, `prior_net_income`, `prior_source` | Vorjahr von Hand, Jahresergebnis des Vorjahres, Quelle des Vorjahres von Hand | nur wo die Bücher kein Vorjahr haben: die Beträge des letzten festgestellten Jahresabschlusses auf ihren Posten, sein Jahresergebnis und woher sie stammen, siehe [Vorjahr](#vorjahr) |
| `firma`, `sitz`, `register_court`, `register_number`, `legal_form` | Firma, Sitz, Registergericht, Registernummer, Rechtsform | setzt „Berechnen“ aus dem Unternehmen und den Einstellungen Jahresmeldungen: die Angaben nach § 264 Abs. 1a Satz 1 HGB, die Registernummer mit ihrer Registerart, etwa „HRB 12345“ |
| `in_liquidation` | In Liquidation | befindet sich die Gesellschaft in Liquidation oder Abwicklung, sagt der Jahresabschluss es (§ 264 Abs. 1a Satz 2 HGB) |
| `notes` | Angaben | Tabelle „Angabe des Jahresabschlusses“, siehe [Angaben](#angaben) |
| `adopted_on`, `resolution_file` | Festgestellt am, Gesellschafterbeschluss | der Tag, an dem die Gesellschafter den Jahresabschluss festgestellt haben, und der Beschluss als Datei; ein neuer Beleg, auch ein geänderter, beginnt ohne beide |
| `signatories` | Unterzeichner | Tabelle „Unterzeichner des Jahresabschlusses“, siehe [Unterzeichner](#unterzeichner) |
| `ug_reserve_minimum` | Mindestbetrag der gesetzlichen Rücklage | für eine UG ein Viertel des um einen Verlustvortrag geminderten Jahresüberschusses (§ 5a Abs. 3 Satz 1 GmbHG) |
| `appropriation_reserve`, `appropriation_dividend`, `appropriation_carried` | In die Rücklagen, Ausschüttung, Vortrag auf neue Rechnung | die Ergebnisverwendung, siehe [Ergebnisverwendung](#ergebnisverwendung) |
| `appropriation_entry` | Buchungssatz der Ergebnisverwendung | der Entwurf, den „Ergebnisverwendung buchen“ anlegt |
| `disclosure_mode` | Art der Offenlegung | Hinterlegung oder Veröffentlichung; leer nimmt eine Kleinstkapitalgesellschaft die Vorgabe der Einstellungen, jede andere Klasse veröffentlicht (§ 326 Abs. 2 HGB) |
| `preview_file`, `xbrl_file` | Vorschau der Offenlegung, XBRL für das Unternehmensregister | die privaten Dateien der beiden Schritte |
| `channel`, `transmitted_on`, `transmitted_by`, `order_number`, `confirmation_file`, `kleinst_notice`, `published_on`, `receipt_file`, `fees` | Kanal, Übermittelt am, Übermittelt von, Auftragsnummer, Auftragsbestätigung, Haken der Hinterlegung gesetzt, Eingestellt am, Beleg, Gebühren | was „Übermittlung festhalten“ und „Einstellung festhalten“ eintragen, siehe [Übermittlung und Einstellung](#übermittlung-und-einstellung); ein Speichern ändert nichts daran |

### Posten

Die Tabelle „Posten des Jahresabschlusses“ (`Annual Accounts Line`) hält je Posten der Bilanz und der Gewinn- und Verlustrechnung eine Zeile, die Vermerke („davon“) unter ihrem Posten und die Summe jeder Seite der Bilanz:

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `statement` | Teil des Abschlusses | Aktiva, Passiva oder GuV |
| `marker`, `label`, `level`, `parent_concept` | Gliederungszeichen, Bezeichnung des Postens, Gliederungsebene, Übergeordneter Posten | wie das Gliederungsschema der Größenklasse den Posten nennt |
| `concept` | Position der Taxonomie | die Position der HGB-Taxonomie oder ihres Vermerks, ohne das Präfix `de-gaap-ci:` |
| `amount`, `prior` | Betrag, Vorjahr | was „Berechnen“ aus den Büchern ermittelt und der Betrag des Vorjahres (§ 265 Abs. 2 Satz 1 HGB) |
| `correction`, `correction_reason` | Korrigierter Betrag, Begründung der Korrektur | eine Korrektur mit ihrer Begründung, nur an einer Zeile, die Salden selbst aufnimmt, siehe [Korrekturen](#korrekturen) |
| `reported` | Betrag im Abschluss | was die Zeile ausweist: die Korrektur, sonst der Betrag |
| `shown` | Im Abschluss gezeigt | ob der Posten in einem der beiden Jahre einen Betrag hat (§ 265 Abs. 8 HGB) |
| `takes_correction` | Korrigierbar | ob die Zeile eine Korrektur nimmt |
| `sources` | Konten der Salden | die Konten, deren Salden in den Posten eingehen |
| `manual` | Zeile von Hand | gibt es im Jahresabschluss nicht: Jeder Posten der Klasse hat seine Zeile |

### Angaben

Die Tabelle „Angabe des Jahresabschlusses“ (`Annual Accounts Note`) hält den Katalog der Größenklasse aus `steuerbote/hgb/notes.py`: eine Kleinstkapitalgesellschaft macht ihre Angaben unter der Bilanz (§ 264 Abs. 1 Satz 5 HGB), eine kleine Gesellschaft in ihrem Anhang.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `code`, `label`, `reference`, `requirement`, `published` | Code, Angabe, Quelle, Anforderung, Offengelegt | setzt „Berechnen“ aus dem Katalog: die Vorschrift, ob die Angabe Pflicht ist oder nur, wenn sie zutrifft, und ob sie offengelegt wird; der Anhang einer kleinen Gesellschaft lässt die Angaben zur Gewinn- und Verlustrechnung weg (§ 326 Abs. 1 Satz 2 HGB) |
| `answer` | Trifft zu | ja, nein oder entfällt; die Arbeitnehmer (`ARBEITNEHMER`) beginnen mit „ja“, ihre Zahl ist die des Belegs (§ 285 Nr. 7 HGB) |
| `text`, `amount` | Text, Betrag | was die Angabe sagt; ein Betrag von null ist kein Betrag |

Ein Speichern nimmt aus der Tabelle nur die Antworten, Texte und Beträge; „Berechnen“ behält sie je Code. Ein Eigenkapital von null verlangt die Angabe `EIGENKAPITAL-NULL`, die unter der Bilanz erklärt, warum das Stammkapital aufgezehrt ist (Bundesamt für Justiz, FAQ zu Inhalts- und Formverstößen).

### Unterzeichner

„Der Jahresabschluß ist vom Kaufmann unter Angabe des Datums zu unterzeichnen.“ (§ 245 Satz 1 HGB) Bei einer GmbH unterzeichnet jeder Geschäftsführer. Die Tabelle „Unterzeichner des Jahresabschlusses“ (`Annual Accounts Signatory`) beginnt „Berechnen“ mit den Geschäftsführern der Einstellungen Jahresmeldungen, die unterzeichnen und am Tag der Feststellung im Amt sind, mit dem Sitz als Ort:

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `signatory_name`, `function` | Name, Funktion | wer unterzeichnet, etwa „Geschäftsführerin“ |
| `place`, `signed_on` | Ort, Datum der Unterschrift | wo und wann; das Druckformat schreibt jede Unterschrift als „Musterstadt, 12. Mai 2027: gez. Erika Beispiel, Geschäftsführerin“ |

### Vorjahr

Haben die Bücher kein Vorjahr, etwa weil die Gesellschaft erst mit dem Geschäftsjahr in ERPNext bucht, nimmt Steuerbote kein Vorjahr aus ihnen. Als Vorjahr der Bücher gilt nur eines mit einer Buchung, die keine Eröffnungsbuchung ist: Eröffnungsbuchungen am letzten Tag des Vorjahres hielten dessen Bilanz ohne Gewinn- und Verlustrechnung. Ebenso wenig gilt es, wenn die Einstellungen Umsatzsteuer-Voranmeldung den Start der Bücher („Bücher in ERPNext ab“) nach dem ersten Tag des Vorjahres nennen (`steuerbote/balances.py`, siehe [Start mit Steuerbote im laufenden Betrieb](einrichtung.md#start-mit-steuerbote-im-laufenden-betrieb)). Dann nimmt die Tabelle „Vorjahresbetrag von Hand“ (`Annual Accounts Prior Entry`) die Beträge des letzten festgestellten Jahresabschlusses auf:

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `concept` | Position der Taxonomie | ein Posten des Gliederungsschemas, etwa `bs.ass.currAss.cashEquiv` oder `bs.eqLiab.equity.subscribed`; einen Posten, den das Schema rechnet, lehnt das Speichern ab |
| `label` | Beschreibung | setzt das Speichern aus dem Schema |
| `amount` | Betrag | der Betrag des Vorjahres |
| `shareholder`, `remaining_term` | Gegenüber Gesellschaftern, Restlaufzeit | was die Vermerke des Postens brauchen |

Das Vorjahr von Hand braucht seine Quelle (`prior_source`) und tritt an die Stelle der Bücher des Vorjahres; das Jahresergebnis des Vorjahres steht ohne dessen Gewinn- und Verlustrechnung in `prior_net_income`. Fehlt ein Vorjahr und ist die Gesellschaft nicht im Geschäftsjahr gegründet, hält der Befund `JA-VORJAHR-FEHLT` den Beleg an (§ 265 Abs. 2 Satz 1 HGB).

## Berechnen

„Berechnen“ liest mit `steuerbote/annual_accounts_sources.py` die Bücher des Geschäftsjahres und des Vorjahres im Finanzbuch der Handelsbilanz, mit dem Abschlusskonto, auf das das Ergebnis früherer Jahre geht, wo kein Periodenabschlussbeleg es abgeschlossen hat (`balances.fiscal_year_books`). Die Bilanzzuordnung verteilt die Salden auf die Positionen der Handelsbilanz, geprüft gegen die steuerliche Ansicht der eingerichteten Taxonomie (`Balance Sheet Mapping.place`), und die Rechnung der handelsrechtlichen Ansicht gibt die Hierarchie, entlang der `steuerbote/hgb/statement.py` die Salden zu den Posten der Größenklasse aufsummiert. Die Befunde der Zuordnung (`BILANZ-…`) stehen in der Tabelle „Befunde“, die des Vorjahres mit „Vorjahr:“ davor.

### Größenklasse

Eine Gesellschaft ist klein oder eine Kleinstkapitalgesellschaft, wenn sie an zwei aufeinanderfolgenden Abschlussstichtagen zwei der drei Merkmale nicht überschreitet: Bilanzsumme, Umsatzerlöse und Arbeitnehmer im Jahresdurchschnitt (§ 267 Abs. 1 und 4, § 267a Abs. 1 HGB). „Berechnen“ liest die Merkmale des Geschäftsjahres aus der Bilanz und der Gewinn- und Verlustrechnung in der Form einer kleinen Gesellschaft, die die Umsatzerlöse zeigt, und die des vorigen Abschlussstichtags aus den Größenmerkmalen der Einstellungen Jahresmeldungen, wo sie alle drei halten, sonst aus dem Vorjahr. `steuerbote/hgb/size.py` entscheidet die Klasse; im ersten Geschäftsjahr nach einer Neugründung genügt der erste Abschlussstichtag (§ 267 Abs. 4 Satz 2 HGB), und eine Gesellschaft nach § 267a Abs. 3 HGB ist keine Kleinstkapitalgesellschaft. Weichen die Merkmale beider Stichtage voneinander ab, braucht die Entscheidung die Größenklasse des Vorjahres aus den Größenmerkmalen; fehlt sie, gilt keine Klasse (`JA-GROESSENKLASSE`), bis die Einstellungen sie nennen oder die Größenklasse von Hand mit Begründung eingetragen ist. Mit der angewandten Klasse baut „Berechnen“ Bilanz und Gewinn- und Verlustrechnung noch einmal.

### Arbeitnehmer

`steuerbote/headcount.py` zählt an den vier Quartalsenden des Geschäftsjahres, 31. März, 30. Juni, 30. September und 31. Dezember, die Mitarbeiter (Employee) des Unternehmens vom Tag des Eintritts bis zum Tag des Austritts, und teilt die Summe durch vier (§ 267 Abs. 5 HGB). Die Arten der Beschäftigung, die die Einstellungen Jahresmeldungen auslassen, etwa Apprentice, zählen nicht mit, denn das Gesetz zählt „ohne die zu ihrer Berufsausbildung Beschäftigten“; ohne HRMS haben die Mitarbeiter keine Art der Beschäftigung, und jeder zählt (`JA-ARBEITNEHMER-ART`). Wer darüber hinaus zählt, etwa eine Teilzeitkraft oder ein Geschäftsführer, ist nicht geprüft; dafür sind die Arbeitnehmer von Hand mit ihrer Begründung da (`JA-ARBEITNEHMER-HAND`).

### Korrekturen

Eine Korrektur weist an einer Zeile einen anderen Betrag aus und braucht eine Begründung. Sie nimmt nur eine Zeile, die Salden selbst aufnimmt: keine Summe, kein Ergebnis, kein Posten, unter dem die Klasse Posten zeigt, und kein Vermerk; jede andere lehnt das Speichern ab. „Berechnen“ nimmt den Unterschied zum Betrag der Bücher als Saldo des Postens in die Bilanz, so dass Summen, Jahresergebnis und der Vergleich von Aktiva und Passiva ihr folgen; eine Korrektur, die die angewandte Klasse auf keiner eigenen Zeile hat, hält der Befund `JA-KORREKTUR` an.

## Befunde

Neben den Befunden der Bilanzzuordnung (`BILANZ-…`) schreibt „Berechnen“ die des Jahresabschlusses; ein Fehler hält den Beleg an, ein Hinweis nicht:

| Code | Art | Bedeutung |
|---|---|---|
| `JA-GROESSENKLASSE` | Fehler | keine Größenklasse entschieden, siehe [Größenklasse](#größenklasse) |
| `JA-GROESSENKLASSE-HAND` | Hinweis | die Größenklasse von Hand ersetzt die entschiedene |
| `JA-KLASSE` | Hinweis | eine Gesellschaft nach § 267a Abs. 3 HGB stellt den Abschluss einer kleinen auf, oder Steuerbote bereitet für eine mittelgroße oder große Gesellschaft Anhang und Offenlegung nicht vor |
| `JA-ARBEITNEHMER-HAND` | Hinweis | die Arbeitnehmer von Hand ersetzen die gezählten |
| `JA-ARBEITNEHMER-ART` | Hinweis | die Einstellungen lassen Arten der Beschäftigung aus, die Mitarbeiter haben aber keine |
| `JA-VORJAHR-FEHLT` | Fehler | kein Vorjahr in den Büchern und keines von Hand |
| `JA-GROESSE-EINSTELLUNGEN` | Hinweis | die Größenmerkmale der Einstellungen nennen für den Abschlussstichtag nicht die angewandte Klasse; die Frist der Feststellung rechnet nach ihnen |
| `JA-UG-RUECKLAGE` | Fehler | eine UG stellt weniger als ein Viertel ihres Jahresüberschusses in die gesetzliche Rücklage ein (§ 5a Abs. 3 Satz 1 GmbHG) |
| `JA-HINTERLEGUNG` | Hinweis | eine Kleinstkapitalgesellschaft veröffentlicht, was sie hinterlegen könnte |
| `JA-KORREKTUR` | Fehler | eine Korrektur einer Zeile, die die Klasse nicht zeigt |
| `JA-OHNE-POSTEN` | Fehler | ein Saldo findet keinen Posten des Schemas |
| `JA-RECHENPOSTEN` | Fehler | ein Saldo liegt auf einem Posten, den das Schema rechnet |
| `JA-BILANZ-UNGLEICH` | Fehler | Aktiva und Passiva weichen voneinander ab (§ 242 Abs. 1, § 266 Abs. 1 HGB) |
| `JA-OHNE-UNTERPOSTEN` | Fehler | ein Saldo liegt auf einem Posten, den die Klasse in Unterposten zeigt |
| `JA-RESTLAUFZEIT-FEHLT` | Fehler | Forderungen oder Verbindlichkeiten eines Postens fehlt die Restlaufzeit, die seine Vermerke brauchen (§ 268 Abs. 4 und 5 HGB); ein Befund je Posten nennt alle Konten und sagt, wo die Restlaufzeit einzutragen ist. Steuern, Sozialversicherung und Löhne tragen sie nach den Vorgaben ab Stand 2026.2 schon, siehe [Restlaufzeit kraft Gesetzes](ebilanz-zuordnung.md#restlaufzeit-kraft-gesetzes) |
| `JA-BILANZGEWINN` | Fehler | ein Saldo steht auf dem Bilanzgewinn, die Bilanz ist aber vor Verwendung des Jahresergebnisses aufgestellt; sie braucht den Ausweis nach teilweiser Verwendung (§ 268 Abs. 1 Satz 2 HGB) |
| `JA-ANGABE-OFFEN` | Fehler | eine Angabe des Katalogs ist nicht beantwortet |
| `JA-ANGABE-PFLICHT` | Fehler | eine Pflichtangabe ist nicht mit „ja“ beantwortet |
| `JA-ANGABE-LEER` | Fehler | eine Angabe mit „ja“ hat weder Text noch Betrag |
| `JA-ANGABE-UNBEKANNT` | Fehler | eine Antwort gehört zu keiner Angabe des Katalogs |
| `JA-ANGABE-DOPPELT` | Fehler | eine Angabe ist mehrfach beantwortet |
| `JA-REGISTERANGABEN` | Fehler | Firma, Sitz, Registergericht oder Registernummer fehlen (§ 264 Abs. 1a HGB) |
| `JA-NICHT-FESTGESTELLT` | Fehler | der Tag der Feststellung fehlt |
| `JA-FESTSTELLUNG-DATUM` | Fehler | der Tag der Feststellung liegt im Geschäftsjahr |
| `JA-UNTERSCHRIFT-FEHLT` | Fehler | ein Geschäftsführer, der am Tag der Feststellung im Amt ist, hat nicht unterzeichnet |
| `JA-UNTERSCHRIFT-OHNE-DATUM` | Fehler | einer Unterschrift fehlt das Datum |
| `JA-UNTERSCHRIFT-DATUM` | Fehler | eine Unterschrift liegt im Geschäftsjahr |
| `SB-NEU-BERECHNEN` | Fehler | seit „Berechnen“ hat sich eine Eingabe geändert: eine Korrektur, eine Angabe, ein Unterzeichner, das Vorjahr von Hand, Größenklasse oder Arbeitnehmer von Hand, die Ergebnisverwendung, die Offenlegung oder der Tag der Feststellung |

Was die XBRL-Datei anhält (`JA-XBRL-…` und `XBRL-…`), steht in [Befunde der Offenlegung](offenlegung.md#befunde).

## Feststellung

„Buchen“ ist die Feststellung. Wie jede Jahresmeldung braucht sie „Bereit zur Abgabe“ oder jeden Fehler der Befunde mit einer Begründung bestätigt, die sagt, warum der Abschluss dennoch richtig ist (siehe [Bestätigte Fehler](jahresmeldungen.md#bestätigte-fehler)); unabhängig von jeder Bestätigung hält sie an (`check_filing`, `bridge.filing_problems`):

- eine Eingabe, die sich seit „Berechnen“ geändert hat,
- keine Größenklasse,
- Aktiva und Passiva, die voneinander abweichen (§ 242 Abs. 1, § 266 Abs. 1 Satz 1 HGB),
- ein Jahresergebnis der Bilanz, das nicht das der Gewinn- und Verlustrechnung ist (§ 266 Abs. 3 A. V., § 275 HGB),
- fehlende Angaben nach § 264 Abs. 1a HGB,
- eine Angabe des Katalogs ohne Antwort und ein Eigenkapital von null ohne seine Erklärung,
- kein Tag der Feststellung, einer im Geschäftsjahr oder einer in der Zukunft (§ 42a Abs. 2 Satz 1 GmbHG).

Die Feststellung friert die Beträge ein und trägt ihren Tag in die Angaben je Jahr der Einstellungen Jahresmeldungen ein (`record_adoption`); das Stornieren nimmt ihn wieder heraus. Ändert sich ein festgestellter Jahresabschluss, wird er storniert und berichtigt: Die Berichtigung beginnt ohne den Tag der Feststellung und ohne die Daten der Unterschriften, wird wieder festgestellt und offengelegt (§ 325 Abs. 1b Satz 1 HGB), und ihre Feststellung setzt den stornierten auf „Ersetzt“. Die XBRL-Datei einer Berichtigung, deren stornierter Beleg schon übermittelt war, meldet einen geänderten Bericht.

## Ergebnisverwendung

Mit der Feststellung beschließen die Gesellschafter über die Verwendung des Ergebnisses (§ 42a Abs. 2 Satz 1, § 29 GmbHG): was in die Rücklagen geht, bei einer UG in die gesetzliche Rücklage, und was ausgeschüttet wird; der Rest ist der Vortrag auf neue Rechnung. Das Speichern lehnt negative Beträge ab und mehr, als der Bilanzgewinn aus Jahresergebnis und Gewinnvortrag hält.

„Ergebnisverwendung buchen“ legt nach der Feststellung eine Journalbuchung im Entwurf zum Tag der Feststellung an und bucht nichts: Das Abschlusskonto der Einstellungen, das das Ergebnis hält, gibt ab, was in die Rücklagen und an die Gesellschafter geht. Die Konten sind die der DATEV-Kontenrahmen 2026:

| Konto | SKR03 | SKR04 |
|---|---|---|
| Gesetzliche Rücklage (UG) | 0846 | 2930 |
| Andere Gewinnrücklagen | 0855 | 2960 |
| Verbindlichkeiten gegenüber Gesellschaftern für offene Ausschüttungen | 0755 | 3519 |

Nach teilweiser Verwendung des Ergebnisses hält die Bilanz die Rücklage des Jahres schon (§ 268 Abs. 1 Satz 2 HGB); dann bucht der Entwurf nur die Ausschüttung. Einen zweiten Entwurf lehnt Steuerbote ab, solange der erste nicht gebucht oder gelöscht ist; ein eigener Kontenrahmen bekommt keinen.

## Offenlegung

- **Vorschau der Offenlegung** druckt mit dem Druckformat „Jahresabschluss“ in eine private PDF-Datei am Beleg, was das Unternehmensregister bekommt und wer es sieht: eine Kleinstkapitalgesellschaft ihre Bilanz mit den Angaben unter der Bilanz, hinterlegt nur auf Antrag einsehbar (§ 326 Abs. 2, § 9 Abs. 6 Satz 3 HGB), eine kleine Gesellschaft ihre Bilanz und ihren Anhang ohne die Angaben zur Gewinn- und Verlustrechnung (§ 326 Abs. 1 HGB), dazu den Tag der Feststellung, die Unterschriften mit „gez.“ und das Hochladen. Die Gewinn- und Verlustrechnung zeigt sie nicht. Die PDF-Datei schreibt der PDF-Generator der Druckeinstellungen; PlutoPrint braucht keinen Browser.
- **XBRL für das Unternehmensregister** schreibt die Datei der Offenlegung (`steuerbote/hgb/instance.py`, `xbrl_export.py`) aus den Grundlagen des Abschlusses mit der eingerichteten HGB-Taxonomie in der Ansicht der Klasse und hängt sie privat an den Beleg (`Offenlegung-JA-2026-00001.xbrl`); ein Entwurf schreibt sie nur, solange er festgestellt werden könnte. Was sie anhält, ersetzt in der Tabelle „Befunde“ die Befunde der Datei davor.
- **Hochladen** auf der Publikations-Plattform, die Testplattform zuerst, Schritt für Schritt wie in [Offenlegung des Jahresabschlusses](offenlegung.md#hochladen-auf-der-publikations-plattform); das Druckformat zeigt die Schritte, Gebühren und Felder des Webformulars ebenfalls. Die Felder des Webformulars sind nicht geprüft.

### Übermittlung und Einstellung

„Übermittlung festhalten“ nimmt nach dem Upload Tag, Person, Auftragsnummer, Weg, Auftragsbestätigung und Gebühren und für eine Hinterlegung den Haken des Auftrags, der die Mitteilung nach § 326 Abs. 2 Satz 2 HGB ist. Es verlangt einen festgestellten Jahresabschluss, einen Tag nach der Feststellung und nicht in der Zukunft, eine Unterschrift mit Datum, die Person (§ 3a Abs. 1 URV) und die Auftragsnummer, setzt den Beleg auf „Übermittelt“ und vermerkt die Abgabe über den Upload: Der Tag der Übermittlung wahrt die Frist der Offenlegung (§ 325 Abs. 4 Satz 2 HGB). „Einstellung festhalten“ nimmt den Tag der Einstellung, den PDF-Beleg und die Gebühren und setzt den Beleg auf „Eingestellt“. Beide Dateien sind privat am Beleg angehängt; eine andere lehnt Steuerbote ab.

## Druckformat „Jahresabschluss“

Das Druckformat druckt die Bilanz in Kontoform (§ 266 Abs. 1 Satz 1 HGB), Aktiva links und Passiva rechts, jeden Posten mit einem Betrag in einem der beiden Jahre (§ 265 Abs. 8 HGB) mit dem Betrag des Vorjahres, die Gewinn- und Verlustrechnung nach dem Gesamtkostenverfahren, die Angaben nach § 264 Abs. 1a HGB mit den Angaben unter der Bilanz oder dem Anhang, den Tag der Feststellung und jede Unterschrift mit Ort, Datum und „gez.“, die Ergebnisverwendung, das Hochladen zum Unternehmensregister, die Korrekturen, die Befunde und die Anmerkungen. Es rechnet nichts. Die Vorschau der Offenlegung ist dasselbe Druckformat mit dem Teil `templates/includes/annual_accounts/offenlegung.html`.

## Für die E-Bilanz

Die E-Bilanz des Jahres nennt den Jahresabschluss im Feld „Jahresabschluss“, den festgestellten oder sonst seinen Entwurf, und „Berechnen“ an der E-Bilanz vergleicht ihre Handelsbilanz mit dem, was er offenlegt, in vollen Euro: bei HGBM jeden Posten der Bilanz, Summe Aktiva, Summe Passiva und den Jahresüberschuss/Jahresfehlbetrag, bei HAOE Summe Aktiva und Jahresüberschuss/Jahresfehlbetrag, siehe [Vergleich mit dem Jahresabschluss](ebilanz.md#vergleich-mit-dem-jahresabschluss). Weicht ein festgestellter Jahresabschluss ab, hält das die E-Bilanz von „Bereit“ ab; der übliche Grund ist eine Buchung nach der Feststellung, nach der er storniert, berichtigt und neu festgestellt wird. Der Jahresabschluss zeigt die E-Bilanzen, die ihn nennen, unter seinen Verbindungen. Stornieren lässt er sich auch, wenn eine abgegebene E-Bilanz ihn nennt: Sie bleibt, wie sie abgegeben ist, und ihre Berichtigung nennt die Berichtigung des Jahresabschlusses.

## Für die Umsatzsteuererklärung

Die Umsatzerlöse des festgestellten Jahresabschlusses (`umsatzerloese`) stellt „Berechnen“ an der Umsatzsteuererklärung des Jahres neben die Bemessungsgrundlagen ihrer Lieferungen und sonstigen Leistungen; eine Differenz über die Rundung und die Toleranz hinaus ist der Hinweis `SB-UMSATZERLOESE`, siehe [Abgleich mit den Umsatzerlösen](umsatzsteuererklaerung.md#abgleich-mit-den-umsatzerlösen). Ein Entwurf zählt dafür nicht; ohne festgestellten Jahresabschluss nimmt die Umsatzsteuererklärung die Umsatzerlöse der abgegebenen E-Bilanz. Warum der Jahresabschluss nach den Rückstellungen und vor der E-Bilanz festgestellt wird, sagt [Zusammenspiel der Jahresmeldungen](jahresmeldungen.md#zusammenspiel-der-jahresmeldungen).

## Grenzen

- **Haftungsverhältnisse und Organkredite:** keine eigenen Tabellen; Text und Betrag der Angabe tragen sie, die XBRL-Datei schreibt sie so.
- **Größenmerkmale:** „Berechnen“ schreibt die Merkmale und die Klasse nicht in die Einstellungen Jahresmeldungen; der Hinweis `JA-GROESSE-EINSTELLUNGEN` sagt, wann sie dort fehlen.
- **Gesetzliche Rücklage der UG:** ob die Rücklage im Abschluss des Jahres oder erst mit der Ergebnisverwendung entsteht, prüft die Steuerberatung.
- **Status des Berichts:** dass eine Berichtigung nach dem Upload als „geändert“ gemeldet wird, ist nicht mit dem Unternehmensregister geprüft.
- **E-Bilanz:** Der Jahresabschluss rechnet keine Steuerbilanz und prüft nichts gegen die E-Bilanz; den Vergleich macht „Berechnen“ an der E-Bilanz, siehe [Für die E-Bilanz](#für-die-e-bilanz).
- **Dateien:** Steuerbote schützt die Dateien am Beleg nicht gegen Löschen.

## Quellen

- HGB §§ 9, 242, 245, 264, 265, 266, 267, 267a, 268, 275, 285, 325, 326, 328; GmbHG §§ 5a, 29, 42a; URV § 3a, gelesen am 23.11.2026 auf gesetze-im-internet.de.
- Bundesamt für Justiz, FAQ zu Inhalts- und Formverstößen bei der Offenlegung.
- DATEV-Kontenrahmen SKR 03 und SKR 04, „Gültig für 2026“.
- HGB-Taxonomie 6.9 vom 1. April 2025 (esteuer.de).
