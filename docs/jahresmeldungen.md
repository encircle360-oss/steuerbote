# Jahresmeldungen

Umsatzsteuererklärung, E-Bilanz, Körperschaftsteuererklärung, Gewerbesteuererklärung und Jahresabschluss sind die Jahresmeldungen von Steuerbote. Sie leben auf derselben Grundlage: einem Kern ohne Frappe unter `steuerbote/jahresmeldung` mit Status, Korrekturen, Befunden und Berichtigungen und einer Frappe-Schicht, `AnnualFiling` in `steuerbote/steuerbote/annual_filing.py`, die der Controller jedes Belegs vor `Transmittable` und `Document` einbindet. Sie verallgemeinert, was für Umsatzsteuer-Voranmeldung und Zusammenfassende Meldung gilt (siehe [Lebenslauf einer Meldung](architektur.md#lebenslauf-einer-meldung)).

Diese Seite beschreibt, was für alle Jahresmeldungen gilt: Status, Felder, Berechnen, Korrekturen und Zeilen von Hand, Befunde, Abgabe, Berichtigung je Datenart, Übermittlung an ELSTER, Druck und Formular, und die Schnittstelle, auf die die Module bauen. Die Belege selbst bringen die Module der Jahresmeldungen mit, alle fünf: die Umsatzsteuererklärung (`Annual VAT Return`, siehe [Umsatzsteuererklärung](umsatzsteuererklaerung.md)), die Körperschaftsteuererklärung (`Corporate Income Tax Return`), die Gewerbesteuererklärung (`Trade Tax Return`, siehe [Körperschaftsteuer- und Gewerbesteuererklärung](ertragsteuern.md)), die E-Bilanz (`Electronic Balance Sheet`, siehe [E-Bilanz](ebilanz.md)) und der Jahresabschluss (`Annual Accounts`, siehe [Jahresabschluss](jahresabschluss.md)). Die Frappe-Tests der Grundlage selbst laufen an zwei eigenen Test-DocTypes, siehe [Der Kern](#der-kern).

Die offenen fachlichen Punkte aller Jahresmeldungen, die eine Steuerberatung vor der ersten Abgabe bestätigen oder entscheiden sollte, sammelt die [Prüfliste für die Steuerberatung](pruefliste-steuerberatung.md).

## Status

| Status | Erklärungen und E-Bilanz | Jahresabschluss | Bedeutung |
|---|---|---|---|
| Entwurf | ja | ja | angelegt und noch nicht berechnet |
| Berechnet | ja | ja | berechnet, aber nicht bereit: Ein Fehler der Befunde hält den Beleg an, eine Prüfung des Moduls geht nicht auf, oder eine Korrektur oder Zeile von Hand hat sich seit dem Berechnen geändert. Der Jahresabschluss bleibt nach dem Berechnen immer hier; ob ein Fehler ihn anhält, sagt „Bereit zur Abgabe“ |
| Bereit | ja | nein | berechnet, kein Fehler der Befunde, und die Prüfungen des Moduls gehen auf |
| Abgegeben | ja | nein | gebucht nach einem Senden, das ELSTER angenommen hat, oder mit dem Vermerk der Abgabe in Mein ELSTER oder auf anderem Weg |
| Ersetzt | ja | ja | eine spätere Abgabe desselben Schlüssels ersetzt den Beleg: eine abgegebene Berichtigung, beim Jahresabschluss die festgestellte Berichtigung eines stornierten |
| Festgestellt | nein | ja | gebucht; „Buchen“ ist die Feststellung des Jahresabschlusses, über die die Gesellschafter beschließen (§ 42a Abs. 2 Satz 1 GmbHG) |
| Übermittelt | nein | ja | an das Unternehmensregister übermittelt |
| Eingestellt | nein | ja | vom Unternehmensregister eingestellt |

- **Den Status setzt nur Steuerbote**, mit den Schritten des Lebenslaufs aus `steuerbote/jahresmeldung/lifecycle.py`: `FILING` für Erklärungen und E-Bilanz, `ACCOUNTS` für den Jahresabschluss. Ein Speichern behält ihn, wie er gespeichert ist.
- **Berechnen** geht aus „Entwurf“, „Berechnet“ und „Bereit“ nach „Bereit“, wenn weder ein Fehler der Befunde noch eine Prüfung des Moduls den Beleg anhält, sonst nach „Berechnet“. Der Jahresabschluss kennt kein „Bereit“.
- **Ein Speichern, das ändert, was eine Zeile meldet**, eine Korrektur oder eine Zeile von Hand, stellt einen berechneten Beleg auf „Berechnet“, mit dem Befund `SB-NEU-BERECHNEN`, bis „Berechnen“ ihn wieder prüft. Eine neue Begründung für denselben Betrag ändert nichts.
- **Der Schlüssel bleibt, wie der Beleg angelegt wurde.** Der Schlüssel ist das Unternehmen und das Jahr, mit dem, was ein Modul dazunimmt, etwa die Bilanzart der E-Bilanz (`KEY_FIELDS`). Seine Felder sind in der DocType-Datei `set_only_once`, im Formular eines gespeicherten Belegs also schreibgeschützt, und `steuerbote.steuerbote.guards.Filing`, von dem `AnnualFiling` erbt, lehnt jedes Speichern ab, das einen von ihnen ändert, auch über die API, bevor der Controller den Beleg prüft. Für ein anderes Unternehmen oder Jahr legt man einen neuen Beleg an und löscht den Entwurf. Umbenennen und Zusammenführen lehnt Steuerbote ebenso ab, denn ELSTER-Übermittlungen und Berichtigungen nennen den Beleg beim Namen, siehe [Architektur](architektur.md#schutz-der-belege-und-rechte).
- **Nach der Feststellung** geht der Jahresabschluss über `move_on` weiter: mit `Event.TRANSMIT` auf „Übermittelt“, mit `Event.PUBLISH` danach auf „Eingestellt“. Jeden anderen Schritt lehnt Steuerbote ab, ebenso jeden an einem Beleg, der nicht gebucht ist.

## Felder jedes Belegs

Jeder Beleg einer Jahresmeldung hat diese Felder mit diesen Feldnamen, Typen und Bezeichnungen (`lifecycle.standard_fields`). Schreibgeschützt sind alle außer Unternehmen, Jahr und Anmerkungen; Unternehmen und Jahr werden einmal gesetzt, beim Anlegen (`set_only_once`). `lifecycle.field_problems(definition, lifecycle, transmits=…)` vergleicht die Definition eines DocTypes mit ihnen; der Test jedes Moduls ruft sie für seine DocType-Datei auf.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company`, `year` | Unternehmen, Jahr | Pflicht. Das Jahr ist der Veranlagungszeitraum (VZ) von Umsatzsteuer und Körperschaftsteuer, der Erhebungszeitraum (EZ) der Gewerbesteuer und bei E-Bilanz und Jahresabschluss das Jahr, in dem das Wirtschaftsjahr endet |
| `fiscal_year`, `from_date`, `to_date` | Geschäftsjahr, Von-Datum, Bis-Datum | setzt jedes Speichern: das Geschäftsjahr, das im Jahr endet, eines des Unternehmens vor einem ohne Unternehmen, das allen dient, wie ERPNext sie ordnet (Fiscal Year Company, `_get_fiscal_years`), damit ein kurzes erstes Wirtschaftsjahr neben dem Kalenderjahr der übrigen Unternehmen steht. Es muss genau eines geben |
| `status` | Status | setzt nur Steuerbote, siehe [Status](#status) |
| `ready`, `remarks` | Bereit zur Abgabe, Anmerkungen | „Bereit zur Abgabe“ setzt „Berechnen“. Die Anmerkungen sind eine Notiz zum Beleg und geben nichts frei: Warum ein Beleg, der nicht bereit ist, trotzdem abgegeben wird, steht an jedem Fehler der Befunde, siehe [Bestätigte Fehler](#bestätigte-fehler); nach einem Senden ändern sich nur noch die Anmerkungen |
| `deadline` | Fälligkeitsdatum | was `compute_deadline` des Moduls nennt, gesetzt mit dem Geschäftsjahr |
| `is_correction`, `corrects` | Berichtigung, Berichtigt | setzt „Berichtigung anlegen“ beim Anlegen; jedes spätere Speichern behält sie |
| `transmission_in_progress` | Übermittlung läuft | nur an Belegen, die über ERiC gehen: die Sperre während eines Vorgangs |
| `filed_via`, `filed_on`, `transferticket`, `filed_by`, `filing_note` | Abgegeben über, Abgegeben am, Transferticket, Vermerkt von, Wie und wann abgegeben | die Abgabe, siehe [Abgabe](#abgabe); nur das Senden, die Vermerke und `move_on` setzen sie |
| `findings` | Befunde | Tabelle „Befund einer Jahresmeldung“ (`Annual Filing Finding`) mit Art, Sperrt, Code, Nachricht und Referenz, siehe [Befunde](#befunde-und-bereit-zur-abgabe) |

## Berechnen

„Berechnen“ (`calculate`) geht nur an einem Entwurf, nicht während einer Übermittlung und nicht nach einem eigenen Senden, das ELSTER angenommen hat oder dessen Ergebnis unbekannt ist.

1. `set_period` setzt Geschäftsjahr, Von-Datum, Bis-Datum und Fälligkeitsdatum.
2. `compute()` des Moduls liest die Quellen und rechnet mit dem Kern des Moduls. Es gibt eine `Calculation` zurück: `lines`, die Zeilen, die es berechnet hat, mit den Spalten von `LINE_COLUMNS`; `tables`, die Zeilen weiterer Tabellen; `values`, die Werte seiner Felder; `findings`, die Befunde aus den Quellen; und `passed`, ob die weiteren Prüfungen des Moduls aufgehen.
3. Die Zeilen des Belegs werden zu den berechneten Zeilen, mit den Korrekturen und Zeilen von Hand, die der Beleg hatte (`overrides.recalculated`). Tabellen und Werte schreibt die Grundlage, wie das Modul sie liefert.
4. `check_reported(lines)` des Moduls prüft die Zeilen, wie sie gemeldet werden, also mit den Korrekturen.
5. Die Befunde aus beiden kommen in die Tabelle „Befunde“, die Fehler zuerst. „Bereit zur Abgabe“ heißt: kein Fehler und `passed` (`findings.ready`). Daraus folgt der Status.
6. Der Beleg wird einmal gespeichert.

Was „Berechnen“ geschrieben hat, behält jedes spätere Speichern: Frappe hält beim Speichern über die API kein schreibgeschütztes Feld fest, deshalb nimmt das Speichern nur, was das Unternehmen eingibt, die Korrekturen und Zeilen von Hand mit ihren Begründungen, die Anmerkungen und die Felder des Moduls, die keine Berechnung sind. Status, „Bereit zur Abgabe“, die Felder aus `CALCULATED_FIELDS`, die Tabellen aus `CALCULATED_TABLES` und die Befunde bleiben, wie „Berechnen“ sie gespeichert hat. Ein neuer Beleg beginnt immer als Entwurf ohne Berechnung und ohne Abgabe, auch als Kopie (`before_insert`); Korrekturen und Zeilen von Hand nimmt er mit.

## Korrekturen und Zeilen von Hand

Ein Beleg meldet Zeilen: die Felder einer Erklärung, die Positionen der E-Bilanz, die Zeilen des Jahresabschlusses. „Eine Abweichung muss erklärt sein“ ([Roadmap](roadmap.md), Grundsätze), deshalb gilt an jeder Zeile (`steuerbote/jahresmeldung/overrides.py`):

- **Korrektur:** ein anderer Betrag als der berechnete, mit Begründung. Ohne Begründung lehnt Steuerbote den Betrag ab, statt ihn zu übergehen, denn wer ihn einträgt, erwartet, dass er zählt. Auch eine Korrektur auf 0 zählt.
- **Zeile von Hand:** eine Zeile, die „Berechnen“ nicht kennt, mit Betrag und Begründung. Eine neue Zeile ist immer eine Zeile von Hand.
- **Gemeldet** wird die Korrektur, wenn sie eine Begründung hat, sonst der berechnete Betrag (`overrides.reported`).
- **Berechnen behält beide.** Eine Korrektur einer Zeile, die „Berechnen“ nicht mehr findet, bleibt mit dem berechneten Betrag 0 stehen, damit nichts, was das Unternehmen von Hand eingetragen hat, unbemerkt wegfällt.
- **Speichern nimmt nur Korrektur und Begründung** einer berechneten Zeile (`overrides.restored`); Schlüssel, Beträge und Beschreibung bleiben, wie „Berechnen“ sie geschrieben hat, und eine berechnete Zeile lässt sich nicht entfernen.
- **Vor jeder Abgabe nachgerechnet:** Bevor ein Beleg übermittelt, als Datei geschrieben oder gebucht wird, rechnet Steuerbote die gemeldeten Beträge aus den gespeicherten Zeilen nach (`require_amounts_as_stored`, `overrides.kept`) und lässt das Modul seine Summen prüfen (`amounts_kept`). Weichen sie von dem ab, was gespeichert ist, etwa weil jemand sie an Steuerbote vorbei geändert hat, lehnt Steuerbote ab, bis der Beleg neu geladen oder neu berechnet ist.
- **Für den Kern des Moduls:** `manual_lines()` gibt die Zeilen von Hand mit Schlüssel, Betrag und Begründung, für ein Modul, dessen Rechnung sie einbezieht, etwa einen Betrag, der vor dem Runden in die Summe eines Felds eingeht.

## Befunde und „Bereit zur Abgabe“

Ein Befund (`Finding` in `steuerbote/jahresmeldung/findings.py`) hat einen Code, eine Art, eine Nachricht und eine Referenz. Die Art ist Fehler oder Hinweis, wie die Jahresdokumentationen der ERiC-Dokumentation 44.3.6.0 jede Regel mit ihrer „Regelart“ kennzeichnen. Ein Fehler hält den Beleg vor „Bereit“ an, ein Hinweis nicht, denn „Grundsätzlich ist aber ein Datensatz, für den Hinweise aber keine Fehler gemeldet werden, valide und könnte versendet oder gedruckt werden.“ (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.1.2.4.1)

- **Code:** der Fehlercode einer Regel der Jahresdokumentation, etwa 30639, oder ein Code von Steuerbote, der mit `SB-` beginnt. **Referenz:** worum es geht, ein Feld, eine Position, ein Konto, ein Beleg oder ein Zeitraum. Beide haben höchstens 140 Zeichen, wie ein Datenfeld von Frappe.
- **Die Tabelle „Befunde“** listet die Fehler zuerst, dann die Hinweise, jeden einmal, in der Reihenfolge, in der sie gefunden wurden (`findings.rows`). Nur Steuerbote schreibt sie; ein Speichern behält sie.
- **Bereit oder bestätigt:** Ein berechneter Beleg, der nicht bereit ist, wird erst abgegeben, wenn jeder seiner Fehler mit Begründung bestätigt ist und keiner zu denen gehört, die sich nie bestätigen lassen (`lifecycle.fit_for_filing`). Über dem Formular steht, wie viele Fehler ihn anhalten, dass alle bestätigt sind, oder dass er bereit ist. Die Anmerkungen geben nichts frei.

### Bestätigte Fehler

Manche Fehler sagen nur, dass etwas nicht sicher ist: vorläufige Vordrucke, ein Konto ohne entschiedenen Platz, eine Prüfung, die noch nicht vermerkt ist. Das Unternehmen kann trotzdem abgeben, wenn es sagt, warum, und zwar an jedem einzelnen Fehler: „Fehler bestätigen“ zeigt die bestätigbaren Fehler mit einem Feld „Begründung der Abgabe trotz Fehler“ (`acknowledge_finding`). Die Zeile hält „Bestätigt“, die Begründung, wer bestätigt hat und wann, die Chronik des Belegs einen Eintrag; eine leere Begründung nimmt die Bestätigung zurück. „Berechnen“ behält die Bestätigung eines Befunds, der gleich bleibt (Code, Referenz und Nachricht); ändert sich etwa sein Betrag, fragt der Befund neu. Bestätigt wird nur an einem berechneten Entwurf.

Nie bestätigt werden Fehler, die die Datei schon im Aufbau falsch machen; die Spalte „Bestätigbar“ zeigt es, und der Kern nennt den Grund mit Quelle (`steuerbote/jahresmeldung/acknowledgements.py`, `NEVER` und `SOURCES`):

| Grund | Codes |
|---|---|
| Fehler einer Regel der Jahresdokumentation, die ERiC und ELSTER zurückweisen (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.1.2.4.1) | jeder numerische Fehlercode, etwa 170205010 „Summe Aktiva ungleich Summe Passiva“ |
| Aktiva und Passiva weichen ab (§ 242 Abs. 1, § 266 Abs. 1 HGB) | `JA-BILANZ-UNGLEICH` |
| ein anderes Jahresergebnis als das der GuV oder der E-Bilanz, die die Erklärung liest | `JA-BILANZGEWINN`, `KST-EBILANZ-ABWEICHUNG` |
| ein Saldo ohne Platz, die Bilanz unvollständig (§ 246 Abs. 1 Satz 1 HGB) | `BILANZ-OHNE-PLATZ`, `BILANZ-OHNE-KONTONUMMER`, `BILANZ-BEOBACHTET`, `BILANZ-POSITION`, `BILANZ-NICHT-GUELTIG`, `BILANZ-ABSCHLUSSKONTO`, `EB-NICHT-ZUGEORDNET`, `JA-OHNE-POSTEN`, `JA-RECHENPOSTEN`, `JA-OHNE-UNTERPOSTEN` |
| Summen, Mussfelder und Positionen, die die HGB-Taxonomie verlangt (§ 5b Abs. 1 Satz 1 EStG, Leitfaden A.10, B.10) | `EB-SUMME`, `EB-KORREKTUR-SUMME`, `EB-BERECHNET`, `EB-UEBERLEITUNG-SUMME`, `XBRL-RECHNUNG`, `XBRL-MUSSFELD`, `XBRL-SUMMENMUSSFELD`, `XBRL-UNZULAESSIG`, `XBRL-NICHT-UEBERMITTELBAR`, `XBRL-RECHTSFORM`, `XBRL-SONDERBILANZ`, `XBRL-KONTEXT`, `XBRL-BERICHTSBESTANDTEIL`, `XBRL-OBERPOSITION`, `XBRL-GUV-FORMAT` |
| eine Zuordnung einer anderen Version der Taxonomie | `BILANZ-TAXONOMIE`, `SB-ZUORDNUNG-VERSION` |
| eine Berechnung, die älter ist als ihre Eingaben | `SB-NEU-BERECHNEN` |
| Nutzdaten, die ihr Schema nicht bestehen (§ 150 Abs. 6 AO) | `KST-NUTZDATEN`, `GEWST-NUTZDATEN` |

Alle anderen Fehler von Steuerbote lassen sich bestätigen. Der Jahresabschluss prüft vor der Feststellung zusätzlich, was `check_filing()` verlangt (siehe [Feststellung](jahresabschluss.md#feststellung)).

Das Modell ist für alle Meldungen gedacht: Eine Tabelle von Befunden mit den Spalten `acknowledgeable`, `acknowledged`, `acknowledgement_reason`, `acknowledged_by` und `acknowledged_on` und die Funktionen `acknowledge`, `carried`, `open_errors` und `never` des Kerns genügen; Voranmeldung und Zusammenfassende Meldung können es übernehmen, indem sie ihre Hinweistabellen um diese Spalten ergänzen und ihre Codes, die die Datei im Aufbau falsch machen, in `NEVER` eintragen.

## Abgabe

| Abgegeben über | Bezeichnung | Wann |
|---|---|---|
| `eric` | ERiC | ein Senden über ERiC, das ELSTER angenommen hat. Der Hintergrundjob bucht den Beleg mit dem Tag der Antwort, dem Transferticket und dem Benutzer, der gesendet hat |
| `mein_elster` | Mein ELSTER | „In Mein ELSTER abgegeben“: Die Erklärung wurde in Mein ELSTER eingegeben, mit dem Druckformat als Vorlage, denn Mein ELSTER importiert keine Jahresmeldung. Transferticket, Tag der Abgabe und Anmerkungen nach Wunsch |
| `other_way` | Auf anderem Weg | „Als außerhalb abgegeben vermerken“, etwa durch die Steuerberatung; „Wie und wann abgegeben“ ist Pflicht, Transferticket und Tag nach Wunsch |
| `upload` | Upload ins Unternehmensregister | die Übermittlung des Jahresabschlusses an das Unternehmensregister, festgehalten mit `move_on` |

- **Buchen allein gibt nichts ab.** Eine Erklärung oder E-Bilanz bucht nur ein Senden, das ELSTER angenommen hat, oder einer der beiden Vermerke (`mark_filed_outside`), der dazu eine ELSTER-Übermittlung mit dem Vorgang „Außerhalb abgegeben“ anlegt (`before_submit`). Das Formular zeigt an ihrem Entwurf deshalb kein „Buchen“, außer nach einem angenommenen Senden, dessen Buchen scheiterte. Der Jahresabschluss wird von Hand gebucht; das ist seine Feststellung.
- **Vor jeder Abgabe** muss der Beleg berechnet sein, bereit oder mit jedem Fehler bestätigt, mit den Beträgen, wie sie gespeichert sind, und die Prüfungen von `check_filing()` des Moduls bestehen (`check_fit_for_filing`); die E-Bilanz braucht dazu ihren Status des Berichts.
- **Die Vermerke** prüfen das Transferticket gegen die Form, die ELSTER vorgibt (32 Zeichen, `TransferTicketSType`), weisen einen Tag der Abgabe in der Zukunft ab und gehen nicht für einen Beleg, den ELSTER angenommen hat: Der wird gebucht.
- **Ein Schlüssel wird einmal abgegeben.** Er hat einen Entwurf zur Zeit. Sobald ein Beleg des Schlüssels gebucht ist oder über Steuerbote gesendet wurde, mit Annahme durch ELSTER oder unbekanntem Ergebnis, auch wenn er danach storniert wurde, ist jeder weitere eine Berichtigung (`refuse_second_filing`). Das prüfen Speichern, Senden, die Vermerke und die Datei eines Moduls.
- **Nichts Abgegebenes wird storniert** (`before_cancel`), denn das nähme beim Finanzamt nichts zurück; eine Änderung geht als [Berichtigung](#berichtigung). Nur der Jahresabschluss wird storniert und berichtigt (in Frappe „Stornieren“ und „Berichtigen“), wenn er sich ändert; die festgestellte Berichtigung setzt den stornierten auf „Ersetzt“. „Berichtigung anlegen“ und eine eigene Berichtigung gibt es für ihn nicht.
- **Nach einem Senden**, das ELSTER angenommen hat oder dessen Ergebnis unbekannt ist, ändern sich an einem Entwurf nur noch die Anmerkungen (`refuse_changes_after_sending`); nach einem unbekannten Ergebnis hält ein Vermerk die Abgabe fest, nachdem jemand in Mein ELSTER nachgesehen hat, siehe [Übermittlung an ELSTER](uebermittlung.md#ablauf-eines-vorgangs).
- **Übermittlung und Einstellung des Jahresabschlusses:** `move_on(Event.TRANSMIT, filed_via="upload", filed_on=…, note=…)` stellt ihn auf „Übermittelt“ und hält den Upload ins Unternehmensregister mit Tag, Vermerk und Benutzer fest, `move_on(Event.PUBLISH)` danach auf „Eingestellt“. Ein gebuchter Beleg behält seine Felder, deshalb speichert `move_on` Status und Abgabe direkt.

## Berichtigung

Eine Berichtigung ist ein neuer, vollständiger Beleg desselben Schlüssels, der einen abgegebenen berichtigt. „Berichtigung anlegen“ (`make_correction`) an einem abgegebenen Beleg legt sie an, mit den Korrekturen und Zeilen von Hand des abgegebenen und dem, was `correction_values()` des Moduls dazugibt, und berechnet sie sofort; solange ein Entwurf des Schlüssels besteht, geht das nicht. Wird die Berichtigung abgegeben, stehen die früheren Abgaben des Schlüssels auf „Ersetzt“. Wie jede Datenart eine Berichtigung kennzeichnet, steht in `steuerbote/jahresmeldung/corrections.py`; `berichtigung()` gibt sie für den Beleg.

| Datenart | Wie | Felder | Geprüft | Quelle |
|---|---|---|---|---|
| `USt` (E50) | Kz 110 „Berichtigte Steuererklärung“ in Zeile 3, ein Ja-Feld mit dem Wert 1 (`corrections.marker`): „Bitte die Zeile 3 nur angeben, wenn Sie eine bereits übermittelte Erklärung berichtigen wollen.“ Eine zweite Erklärung des Jahres geht nur mit ihr (Regel 30002). Das Vorauszahlungssoll einer berichtigten Erklärung ist die Kz 816 der Erklärung, die sie berichtigt, oder der Betrag des Finanzamts als Korrektur mit Begründung | `E3000601` | ja | Jahresdokumentation E50 2026, Blätter „USt2A - Felder“ und „USt2A - Regeln“ |
| `KSt` (E30) | Kein Feld kennzeichnet eine Berichtigung, sie ist eine neue, vollständige Erklärung. Erklären kann sie der qualifizierte Freitext nach § 150 Abs. 7 Satz 1 AO, „Angaben, die nach seiner Auffassung Anlass für eine Bearbeitung durch Amtsträger sind“, in KSt 1 Zeile 13: Schlüssel 1 bis 4 und Text, beide oder keines (Regel 8900735). Ob ELSTER den Text bei einer Berichtigung erwartet, ist nicht bestätigt; das klärt die ELSTER-Hotline | `E8001305`, `E8001304` | nein | § 150 Abs. 7 Satz 1 AO; Jahresdokumentation E30 2025, Blätter „KSt1 - Felder“ und „KSt1 - Regeln“ |
| `GewSt` (E20) | wie die Körperschaftsteuererklärung, mit dem Freitext in GewSt 1 A Zeile 21 (Regel 40128) | `E4003204`, `E4003205` | nein | § 150 Abs. 7 Satz 1 AO; Jahresdokumentation E20 2025, Blätter „GewSt1A - Felder“ und „GewSt1A - Regeln“ |
| `Bilanz` | der Status des Berichts in der GCD, im Feld `revision_status` des Belegs, siehe unten | `genInfo.report.id.revisionStatus` | ja | FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d; `de-gcd-2025-04-01.xsd`, `-label-de.xml` und `-reference-fiscal.xml` der Taxonomie 6.9 |
| `Offenlegung` | keine Berichtigung am Beleg: Ein Jahresabschluss, der sich ändert, wird storniert und berichtigt, und die Änderung wird offengelegt, siehe unten | – | ja | § 325 Abs. 1b Satz 1 HGB; JVKostG, Anlage 1, Vorbemerkung 1.4.2; Allgemeine Nutzungsbedingungen für das Unternehmensregister, §§ 13 und 14 |

### Status des Berichts der E-Bilanz

Eine geänderte Bilanz „ist als eigener, neuer Datensatz einzureichen“, und in der GCD ist anzugeben, dass es sich um eine geänderte Bilanz handelt (FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d). Die erste Abgabe eines Schlüssels ist erstmalig; das setzt Steuerbote selbst. Eine Berichtigung nennt ihren Status, spätestens wenn sie abgegeben wird (`corrections.revision_status`). Korrekturen einer Bilanz sind nur unter den Voraussetzungen von § 4 Abs. 2 EStG zulässig; welchen dieser Status sie trägt, entscheidet die Steuerberatung.

| Wert | Status des Berichts | Wann |
|---|---|---|
| `E` | erstmalig | die erste Abgabe des Schlüssels |
| `B` | berichtigt | eine Korrektur der Bilanz nach § 4 Abs. 2 EStG |
| `G` | geändert | ebenso |
| `BG` | berichtigt und geändert | ebenso |
| `sK` | sonstige Korrektur | Korrekturen nur außerhalb von Bilanz und GuV, etwa der steuerlichen Gewinnermittlung in Fällen des § 7g Abs. 3 Satz 1 EStG |
| `I` | identischer Abschluss mit differenzierteren Informationen | es werden nur bisher nicht übermittelte Informationen nachgereicht, etwa Kontensalden |
| `K` | Korrektur durch Finanzverwaltung | nie: Die Taxonomie lässt den Wert für die „Einreichung an Finanzverwaltung“ nicht zu (`notPermittedFor`), und Steuerbote lehnt ihn ab |

### Offenlegung

„Wird der Jahresabschluss [...] geändert, so ist auch die Änderung nach Absatz 1 Satz 1 offenzulegen.“ (§ 325 Abs. 1b Satz 1 HGB) Ein festgestellter Jahresabschluss, der sich ändert, wird deshalb storniert und berichtigt; die Berichtigung wird wieder festgestellt und übermittelt. Wie sich ein Auftrag an das Unternehmensregister selbst ändert, hängt an seiner Einstellung (`corrections.register_changes`, `corrections.fee_factor`):

- **Vor der Einstellung** lassen sich die Unterlagen ergänzt oder geändert übermitteln; dann „erhöhen sich die Gebühren dieses Abschnitts um 50 Prozent“. Wer verlangt, sie nicht einzustellen, zahlt die Hälfte, und nichts, wenn er es am Kalendertag der Übermittlung verlangt (JVKostG, Anlage 1, Vorbemerkung 1.4.2 Abs. 2 Satz 2 und Abs. 3).
- **Nach der Einstellung** lassen sich Aufträge „grundsätzlich weder widerrufen noch auf andere Weise ganz oder teilweise rückgängig“ machen, und „Eine Korrektur kann bei selbstverursachten Fehlern nur eigenständig durch Übermittlung eines separaten Berichtigungsauftrags erfolgen“ (Allgemeine Nutzungsbedingungen für das Unternehmensregister, § 13 Abs. 3), mit den Gebühren eines eigenen Auftrags.

## Übermittlung an ELSTER

Umsatzsteuererklärung, E-Bilanz, Körperschaftsteuererklärung und Gewerbesteuererklärung gehen wie die Voranmeldung über ERiC an das Finanzamt: Ihre Controller erben `Transmittable`, und Prüfen, Testsenden und Senden laufen mit derselben Sperre, denselben Ergebnissen, derselben Simulation und derselben ELSTER-Übermittlung, siehe [Übermittlung an ELSTER](uebermittlung.md). Die ELSTER-Übermittlung nennt ihre DocTypes in `DOCUMENT_TYPES`: `Annual VAT Return`, `Electronic Balance Sheet`, `Corporate Income Tax Return` und `Trade Tax Return`. Der Jahresabschluss geht nicht an das Finanzamt.

- **Datenart.** `datenart()` des Moduls nennt die Datenart, `datenart.ust(Jahr)`, `kst(Jahr)`, `gewst(Jahr)` oder `bilanz(Taxonomie)`, siehe [ERiC](eric.md#erklärungen-und-e-bilanz). `nutzdaten(hersteller_id)` behält seine Signatur; die Erklärungen und die E-Bilanz schreiben die Hersteller-ID nicht in die Nutzdaten und übergehen das Argument.
- **Steuernummer und Finanzamt.** `elster_tax_number()` gibt die 13-stellige Steuernummer, unter der der Beleg geht: für Körperschaftsteuer, Gewerbesteuer und E-Bilanz die Steuernummer der Einstellungen Jahresmeldungen (`elster_income_tax_number`), wenn das Finanzamt dafür eine eigene vergeben hat, sonst die der Einstellungen Umsatzsteuer-Voranmeldung. Das Finanzamt im Kopf der Lieferung sind ihre ersten vier Stellen. `tax_numbers()` gibt dazu die Steuernummer, wie das Finanzamt sie vergeben hat, für den Druck.
- **Vorsatz einer Erklärung.** `vorsatz()` bildet ihn aus der Steuernummer, dem Namen des Unternehmens, Straße, Postleitzahl und Ort der Einstellungen Jahresmeldungen und dem Copyrightvermerk der ERiC-Einstellungen; `bescheiddaten()` des Moduls entscheidet über die Bereitstellung der Bescheiddaten (`Rueckuebermittlung/Bescheid` 1 statt 2). Ohne Einstellungen Jahresmeldungen geht keine Erklärung über ERiC, außerhalb der Simulation auch nicht ohne Copyrightvermerk; `check_transmittable()` bildet den Vorsatz vor jedem Vorgang einmal zur Probe.
- **DatenLieferant der E-Bilanz.** `nutzdaten_datenlieferant()` gibt den DatenLieferant des NutzdatenHeaders in seinen zehn Teilen (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 9.7.1): Name des Unternehmens, Straße, Hausnummer, Hausnummerzusatz, Adressergänzung, Postleitzahl, Ort und Land der Einstellungen Jahresmeldungen, das Land einer Anschrift in Deutschland als „Deutschland“, wie das Beispiel des Handbuchs es schreibt, und Telefon und E-Mail des Datenlieferanten der Einstellungen Umsatzsteuer-Voranmeldung. Ein Semikolon in einem Teil lehnt Steuerbote ab, denn es trennt die Teile.
- **Was ERiC nach dem Senden druckt.** Für eine Erklärung erstellt ERiC kein Übertragungsprotokoll, sondern ein Freizeichnungsdokument, für die E-Bilanz nur ein Übertragungsprotokoll (Kap. 5.1.4.3, 5.1.4.4 und 9.7.1). `printout()` nennt es, das Formular erfährt es aus `elster_state`, und der Dialog für Zertifikat und Passwort sagt, was die ELSTER-Übermittlung danach hält. Sie hält es im Feld „Protokoll oder Freizeichnungsdokument (PDF)“, als Datei, deren Name auf `freizeichnungsdokument.pdf` oder `protokoll.pdf` endet. Das Prüfen der E-Bilanz druckt nichts (EBV-8).
- **Senden** prüft dazu, dass der Beleg abgegeben werden könnte, weder übermittelt ist noch mit unbekanntem Ergebnis gesendet wurde und sein Schlüssel nicht abgegeben ist (`check_can_be_sent`); ein Beleg, den ELSTER hat oder haben kann, wird auch nicht als Datei für einen anderen Weg geschrieben (`refuse_sent_document`).
- **Ohne Hersteller-ID** läuft alles in der Simulation. Die Erklärungen gibt man dann in Mein ELSTER ein, mit dem Druckformat als Vorlage; für die E-Bilanz gibt es diesen Weg nicht („nicht möglich und auch nicht geplant“, FAQ zur E-Bilanz, Tz. 9), ihr Modul nennt deshalb nur „Als außerhalb abgegeben vermerken“ in `FILED_OUTSIDE`.

## Druckformate

Jeder Beleg druckt mit einem Standard-Druckformat seines Moduls, auf A4, schwarz und grau, ohne Logo und ohne Briefkopf. Die Teile, die alle gleich haben, liegen in `steuerbote/templates/includes/annual_filing/`, und jedes Druckformat bindet sie mit `{% include %}` ein:

| Teil | Inhalt |
|---|---|
| `style.html` | A4 hochkant, Schrift und Tabellen, alle Klassen mit `sb-`, denn das Druck-Stylesheet von Frappe gestaltet allgemeine Klassen wie `label` selbst. Das Druckformat bindet es zuerst ein und legt seinen Inhalt in `<div class="sb-annual">` |
| `head.html` | der Kopf in zwei Spalten: Unternehmen, Steuernummer, Steuernummer im ELSTER-Format, Jahr, Geschäftsjahr, Fällig am, die Zeilen des Moduls aus `head_rows`, Beleg mit Status, Berichtigung zu und Abgegeben am mit dem Weg |
| `corrections.html` | „Korrekturen und Zeilen von Hand“: Zeile, Bezeichnung, berechnet, gemeldet und Begründung |
| `findings.html` | „Befunde“: jeder Fehler mit Art, Code, Nachricht, Referenz und, wo bestätigt, der Begründung (`errors`); die Hinweise nach Art mit ihrer Zahl und dem ersten (`hint_kinds`); alle Hinweise als Anhang nur, wenn der Druck `all_hints=1` verlangt (`hints`), über „Drucken mit allen Hinweisen“ am Formular |
| `remarks.html` | die Anmerkungen |
| `footer.html` | „Zum Abgleich mit der Steuerberatung oder zum Übertragen in Mein ELSTER.“ und der Hinweis, dass der Ausdruck keine Abgabe ist; ohne den Weg über Mein ELSTER, wie bei der E-Bilanz, nur „Zum Abgleich mit der Steuerberatung.“; beim Jahresabschluss der Hinweis, dass der Ausdruck keine Offenlegung ist |

Die Teile lesen, was `annual_print()` des Belegs gibt: `accounts` (ein Jahresabschluss), `mein_elster` (der Beleg geht auch über Mein ELSTER), `tax_number` und `elster_tax_number`, `findings` und `corrections`, die Zeilen mit Korrektur oder von Hand mit `key`, `label`, `manual`, `computed`, `reported` und `reason`. Ein Druckformat setzt `annual` einmal am Anfang, damit kein Teil es neu bildet, und `head_rows` für die Zeilen seines Kopfs, eine Liste von Bezeichnung und Wert:

```jinja
{% set annual = doc.annual_print() %}
{% include "steuerbote/templates/includes/annual_filing/style.html" %}
<div class="sb-annual">
  <h1>Umsatzsteuererklärung {{ doc.year }}</h1>
  {% set head_rows = [("Finanzamt", finanzamt)] %}
  {% include "steuerbote/templates/includes/annual_filing/head.html" %}
  … der Vordruck des Moduls …
  {% include "steuerbote/templates/includes/annual_filing/corrections.html" %}
  {% include "steuerbote/templates/includes/annual_filing/findings.html" %}
  {% include "steuerbote/templates/includes/annual_filing/remarks.html" %}
  {% include "steuerbote/templates/includes/annual_filing/footer.html" %}
</div>
```

## Formular

`steuerbote/public/js/annual_filing.js` gibt den Formularen, was alle gleich haben. Ein Formular, das über ERiC geht, bindet zuerst `steuerbote/public/js/elster_transmission.js` ein, dann diese Datei, jedes mit `{% include %}`, und ruft `annual_filing_setup(frm)` in `setup` und `annual_filing_refresh(frm, texts)` in `refresh`. Was die Grundlage dem Formular sagt, steht in `annual_state()`, das `onload` mitgibt: welche Status berechnet und welche abgegeben heißen, welche Vermerke es gibt, ob der Beleg von Hand gebucht wird und ob sich eine Berichtigung anlegen lässt.

- „Berechnen“ an einem Entwurf, solange keine Übermittlung läuft und kein Senden ihn sperrt; „Berichtigung anlegen“ an einem abgegebenen Beleg, nicht am Jahresabschluss.
- Unter „ELSTER“ an einem berechneten Entwurf Prüfen, Testsenden und Senden und die Vermerke „In Mein ELSTER abgegeben“ und „Als außerhalb abgegeben vermerken“, soweit `FILED_OUTSIDE` sie nennt. Kein „Buchen“ für einen Entwurf, der über ERiC geht, und nicht der Hinweis von Frappe, ihn zu buchen.
- Über dem Formular: ob der Beleg bereit ist oder wie viele Fehler ihn anhalten, wann und wie er abgegeben wurde, die Hinweise der Übermittlung und die Fehler und Hinweise des letzten Laufs.

Die Texte, die den Beleg nennen, gibt das Formular in `texts` mit: für `elster_transmission.js` `unsaved`, `send`, `test_send`, `sent`, `running` und nach Bedarf `simulation` (eine Funktion des Links auf die ERiC-Einstellungen), `send_label` und `simulated_test_send`; für `annual_filing.js` nach Bedarf `berichtigung` (die Rückfrage vor „Berichtigung anlegen“), `ready` (der Hinweis an einem bereiten Beleg) und `filed_outside_example` (ein Beispiel für „Wie und wann abgegeben“).

## Zusammenspiel der Jahresmeldungen

Die Jahresmeldungen eines Jahres bauen aufeinander auf: Die E-Bilanz übermittelt den Inhalt der Bilanz und der Gewinn- und Verlustrechnung (§ 5b Abs. 1 Satz 1 EStG), also die des festgestellten Jahresabschlusses, und aus ihr kommt der Jahresüberschuss der Körperschaftsteuererklärung, auf der die Gewerbesteuererklärung aufbaut. Woraus ein Beleg nimmt, steht an verschiedenen Stellen:

- **Im Feld:** Die Körperschaftsteuererklärung nennt ihre E-Bilanz (`electronic_balance_sheet`) und die E-Bilanz ihren Jahresabschluss (`annual_accounts`); ein neuer Beleg und „Berechnen“ setzen beide. Die Gewerbesteuererklärung nennt ihre Körperschaftsteuererklärung (`corporate_income_tax_return`); dieses Feld setzt das Speichern, wo es leer ist.
- **In der Tabelle „Voranmeldungszeiträume“:** Die Umsatzsteuererklärung nennt je Zeitraum die abgegebene Umsatzsteuer-Voranmeldung, wie „Berechnen“ sie einträgt.
- **Nur im Hinweis:** Die abgegebene E-Bilanz des Vorjahres hinter KSt 1 F Zeilen 17 und 18 nennt `KST-EIGENKAPITAL-QUELLE`; den Jahresabschluss oder die E-Bilanz hinter den Umsatzerlösen nennt `SB-UMSATZERLOESE`, und diesen Hinweis gibt es nur, wo die Umsätze der Umsatzsteuererklärung nicht zu den Umsatzerlösen passen.
- **Nirgends:** Die E-Bilanz übernimmt das Betriebsvermögen der abgegebenen E-Bilanz des Vorjahres in `bvv_previous_equity`, ohne diese zu nennen.

Je Beleg, was er woraus nimmt, mit dem Feld oder Befund dazu; wo zwei Belege dasselbe zeigen, vergleicht „Berechnen“ sie:

| Beleg | nimmt | aus | Feld, Befund |
|---|---|---|---|
| E-Bilanz | die Handelsbilanz zum Vergleich | dem Jahresabschluss des Jahres, dem festgestellten oder sonst seinem Entwurf | `annual_accounts`; `SB-JA-ABWEICHUNG`, `SB-JA-FEHLT`, siehe [Vergleich mit dem Jahresabschluss](ebilanz.md#vergleich-mit-dem-jahresabschluss) |
| E-Bilanz | das Betriebsvermögen zum Ende des Vorjahres | der abgegebenen E-Bilanz des Vorjahres | `bvv_previous_equity`, siehe [Betriebsvermögensvergleich](ebilanz.md#betriebsvermögensvergleich) |
| Körperschaftsteuererklärung | Anlage GK Zeile 11, bei einer Handelsbilanz mit Überleitungsrechnung mit der Überleitung | der E-Bilanz des Jahresabschlusses des Jahres | `electronic_balance_sheet`; `KST-EBILANZ-ABWEICHUNG`, `KST-UEBERLEITUNG-DOPPELT`, siehe [Aus der E-Bilanz](ertragsteuern.md#aus-der-e-bilanz) |
| Körperschaftsteuererklärung | KSt 1 F Zeilen 17 und 18 | der abgegebenen E-Bilanz des Vorjahres | `KST-EIGENKAPITAL-QUELLE` |
| Gewerbesteuererklärung | die Körperschaftsteuer, auf der sie rechnet | der Körperschaftsteuererklärung des Jahres | `corporate_income_tax_return`, siehe [Körperschaftsteuer- und Gewerbesteuererklärung](ertragsteuern.md) |
| Umsatzsteuererklärung | die Umsatzerlöse zum Abgleich | dem festgestellten Jahresabschluss, sonst der abgegebenen E-Bilanz | `SB-UMSATZERLOESE`, siehe [Abgleich mit den Umsatzerlösen](umsatzsteuererklaerung.md#abgleich-mit-den-umsatzerlösen) |
| Umsatzsteuererklärung | Kennzahlen und Vorauszahlungssoll | den abgegebenen Voranmeldungen | siehe [Abgleich mit den Voranmeldungen](umsatzsteuererklaerung.md#abgleich-mit-den-voranmeldungen) |

Ein Unterschied hält nur dort an, wo dieselbe Zahl zweimal verschieden abgegeben würde: die E-Bilanz neben einem festgestellten Jahresabschluss, der anders ist, und die Körperschaftsteuererklärung neben einer E-Bilanz, die nicht mehr die Bücher zeigt. Die Umsatzerlöse neben den Umsätzen der Umsatzsteuererklärung sind nur ein Hinweis, denn beide zählen nicht genau dasselbe.

Daraus folgt die Reihenfolge der Arbeit eines Jahres:

1. **Bücher:** alle Buchungen des Geschäftsjahres, die Abschreibungen bis zum Bilanzstichtag eingeschlossen.
2. **Rückstellungen:** die Körperschaftsteuererklärung berechnen, solange es keine E-Bilanz gibt aus den Büchern, und „Rückstellungen vorschlagen“; die Journalbuchung prüfen und buchen. Die Rückstellungen gehören in den Jahresabschluss.
3. **Jahresabschluss:** berechnen, die Angaben beantworten und feststellen. Wer danach noch bucht, ändert die Bücher, nicht ihn: Er wird storniert, berichtigt und neu festgestellt.
4. **E-Bilanz:** berechnen; sie nennt den Jahresabschluss und vergleicht ihre Handelsbilanz mit ihm.
5. **Körperschaftsteuererklärung:** neu berechnen; sie nennt die E-Bilanz und nimmt aus ihr Zeile 11. Das zu versteuernde Einkommen bleibt das aus Schritt 2, denn die Zeilen 81 bis 84 rechnen die Steuern wieder hinzu, bis auf die Rundung der Zeilen (siehe [Grenzen](ertragsteuern.md#grenzen)).
6. **Gewerbesteuererklärung:** auf der Körperschaftsteuererklärung berechnen.
7. **Umsatzsteuererklärung:** berechnen; sie stellt ihre Umsätze neben die Umsatzerlöse des Jahresabschlusses.
8. **Abgabe:** die Erklärungen und die E-Bilanz über ERiC oder mit dem Vermerk ihrer Abgabe, den Jahresabschluss beim Unternehmensregister. „Offene Fristen“ zeigt für jede Jahresmeldung des Jahres, was abgegeben und was offen ist, siehe [Fristen](fristen.md#jahresmeldungen).

Die Frappe-Tests gehen diese Reihenfolge an einer erfundenen GmbH mit SKR04 durch (`steuerbote/tests/test_annual_year.py` auf `steuerbote/tests/annual_integration.py`), dazu das Jahr, dessen Jahresabschluss vor den Rückstellungen festgestellt ist.

## Für die Module

Im Desk steht jeder Beleg mit seiner Liste in der Gruppe „Jahresmeldungen“ der Seitenleiste, neben den Einstellungen Jahresmeldungen und den Zuordnungen, die Berichte der Module in der Gruppe „Berichte“; der Arbeitsbereich „Steuern“ führt in seinem Abschnitt „Jahresmeldungen“ zur Liste jedes Belegs und zu einem neuen Beleg jeder Erklärung und der E-Bilanz, siehe [Architektur](architektur.md#arbeitsbereich-steuern-und-seitenleiste). Ein neues Modul gibt seinem Beleg eine Zeile in der Gruppe, ohne Symbol, mit seiner Bezeichnung in `de.csv`, und seine Liste im Abschnitt; `steuerbote/tests/test_menu.py` verlangt beides.

Ein Modul baut seinen Controller so:

```python
from frappe.model.document import Document

from steuerbote.steuerbote.annual_filing import AnnualFiling, Calculation
from steuerbote.steuerbote.doctype.elster_transmission.transmission import Transmittable


class AnnualVATReturn(AnnualFiling, Transmittable, Document):
	LINES = "lines"

	def compute(self) -> Calculation: ...
	def datenart(self): ...
	def nutzdaten(self, hersteller_id: str) -> str: ...
```

Der Jahresabschluss geht nicht an ELSTER: `class AnnualAccounts(AnnualFiling, Document)` mit `LIFECYCLE = ACCOUNTS`. Wie jeder buchbare DocType hat sein DocType das Feld `amended_from`, das Frappe für „Berichtigen“ anlegt; die Berichtigung eines stornierten Jahresabschlusses nennt ihn dort und ersetzt ihn, wenn sie festgestellt wird. Überschreibt ein Modul einen Hook von Frappe, den die Grundlage hat (`onload`, `before_insert`, `validate`, `before_submit`, `on_submit`, `before_cancel`), ruft es den der Grundlage mit `super()` auf. `transmits` sagt, ob der Beleg über ERiC geht.

### Was das Modul angibt

| Attribut | Vorgabe | Inhalt |
|---|---|---|
| `LIFECYCLE` | `FILING` | der Lebenslauf: `FILING` für Erklärungen und E-Bilanz, `ACCOUNTS` für den Jahresabschluss |
| `KEY_FIELDS` | `("company", "year")` | der Schlüssel: je Schlüssel ein Entwurf und eine Abgabe, sonst Berichtigungen. Die E-Bilanz nimmt die Bilanzart dazu |
| `LINES` | `None` | die Tabelle der Zeilen, die „Berechnen“ füllt und an der Korrekturen und Zeilen von Hand stehen |
| `LINE_COLUMNS` | `overrides.Columns()` | ihre Spalten: Schlüssel, berechnete Beträge (der erste ist der gemeldete ohne Korrektur), Beschreibung, Korrektur, Begründung, gemeldeter Betrag und Zeile von Hand |
| `CALCULATED_TABLES` | `()` | weitere Tabellen, die „Berechnen“ füllt und ein Speichern behält |
| `CALCULATED_FIELDS` | `()` | Felder, die „Berechnen“ setzt und ein Speichern behält |
| `FILED_OUTSIDE` | `("mein_elster", "other_way")` | die Vermerke einer Abgabe außerhalb von ERiC; die E-Bilanz nennt nur `other_way` |

| Hook | Pflicht | Inhalt |
|---|---|---|
| `compute()` | ja | „Berechnen“: liest die Quellen, rechnet mit dem Kern und gibt eine `Calculation` mit `lines`, `tables`, `values`, `findings` und `passed` |
| `check_reported(lines)` | nein | die Befunde zu den Zeilen, wie sie gemeldet werden, nach Korrekturen und Zeilen von Hand |
| `compute_deadline()` | nein | das Fälligkeitsdatum aus den Fristen der Jahresmeldungen: `annual_deadline(company, kind, year)` in `steuerbote/steuerbote/deadlines.py` gibt mit dem Kern `steuerbote/deadlines/annual.py` denselben Tag wie „Offene Fristen“, siehe [Fristen](fristen.md#belege-der-jahresmeldungen); ohne es bleibt das Feld leer |
| `set_amounts()` | nein | setzt bei jedem Speichern die Felder, die das Modul aus den gemeldeten Zeilen bildet, etwa seine Summen |
| `amounts_kept(stored)` | nein | ob der gespeicherte Beleg diese Felder so hält, wie die Zeilen sie ergeben |
| `check_filing()` | nein | lehnt eine Abgabe ab, die das Modul über „Bereit oder bestätigt“ hinaus nicht zulässt |
| `correction_values()` | nein | die Werte, mit denen eine Berichtigung über Schlüssel und Zeilen hinaus beginnt |
| `bescheiddaten()` | nein | ob der Vorsatz einer Erklärung die Bescheiddaten zum Abruf anfordert |
| `datenart()`, `nutzdaten(hersteller_id)` | ja, wenn über ERiC | aus `Transmittable`: die Datenart und die Nutzdaten |

### Was die Grundlage gibt

| Methode | Inhalt |
|---|---|
| `calculate()` | „Berechnen“, nur POST |
| `acknowledge_finding(finding, reason)` | „Fehler bestätigen“, nur POST: bestätigt einen Fehler der Befunde mit Begründung, eine leere Begründung nimmt die Bestätigung zurück |
| `make_correction()` | „Berichtigung anlegen“, nur POST; gibt den Namen der Berichtigung |
| `add_finding(finding)` | fügt den Befunden, die „Berechnen“ gespeichert hat, einen hinzu, etwa den, der nach „Berechnen“ fragt, und behält die Bestätigungen der anderen |
| `mark_filed_outside(filed_via, note, transferticket, filed_on)` | „In Mein ELSTER abgegeben“ und „Als außerhalb abgegeben vermerken“, nur POST; gibt den Namen der ELSTER-Übermittlung |
| `move_on(event, filed_via=…, filed_on=…, note=…)` | der nächste Schritt eines gebuchten Belegs, Übermittlung und Einstellung des Jahresabschlusses; gibt den neuen Status |
| `set_period()` | Geschäftsjahr, Von-Datum, Bis-Datum und Fälligkeitsdatum |
| `check_fit_for_filing()` | „Bereit oder bestätigt“, Status des Berichts und `check_filing()` |
| `require_amounts_as_stored(stored)` | die Beträge, wie die gespeicherten Zeilen sie ergeben |
| `require_fit_for_export()` | vor einer Datei eines Moduls, etwa dem XBRL der E-Bilanz: ein abgegebener Beleg schreibt sie, wie er abgegeben ist, ein Entwurf nur, solange er abgegeben werden könnte und weder gesendet noch abgegeben ist; ein stornierter nie |
| `refuse_second_filing()`, `refuse_sent_document()` | ein Schlüssel wird einmal abgegeben; was ELSTER hat oder haben kann, geht nicht noch einmal |
| `manual_lines()` | die Zeilen von Hand |
| `berichtigung()` | wie die Datenart des Belegs eine Berichtigung kennzeichnet |
| `annual_print()`, `tax_numbers()` | was die Teile der Druckformate lesen, und die Steuernummer in beiden Formen |
| `annual_state()` | was das Formular wissen muss |
| `elster_tax_number()`, `nutzdaten_datenlieferant()`, `vorsatz()`, `check_transmittable()`, `check_can_be_sent()` | für `Transmittable`, siehe [Übermittlung an ELSTER](#übermittlung-an-elster) |

### Der Kern

| Modul | Inhalt |
|---|---|
| `jahresmeldung/lifecycle.py` | `Status`, `Event`, `Lifecycle` mit `FILING` und `ACCOUNTS`, „Bereit oder bestätigt“ (`fit_for_filing`), ein Entwurf und eine Abgabe je Schlüssel (`refuse_second_draft`, `refuse_second_filing`, `check_correction`), die Wege der Abgabe (`FILED_VIA`) und die Felder jedes Belegs (`standard_fields`, `field_problems`) |
| `jahresmeldung/overrides.py` | `Columns`, `Correction`, `ManualLine`; die Zeilen nach „Berechnen“ (`recalculated`) und nach einem Speichern (`restored`), der gemeldete Betrag (`reported`), ob die gespeicherten Beträge stimmen (`kept`), ob ein Speichern etwas geändert hat (`changed`), die Zeilen von Hand (`manual_lines`) |
| `jahresmeldung/findings.py` | `Finding`, `Severity`, `ready`, die Zeilen der Tabelle „Befunde“ (`rows`, `of_rows`) |
| `jahresmeldung/acknowledgements.py` | die Bestätigung eines Fehlers (`acknowledge`), die Fehler, die nie bestätigt werden, mit Grund und Quelle (`NEVER`, `Ground`, `SOURCES`, `ground_of`), die offenen Fehler (`open_errors`, `never`) und die Bestätigungen, die „Berechnen“ behält (`carried`) |
| `jahresmeldung/corrections.py` | die Berichtigung je Datenart (`BERICHTIGUNGEN`, `berichtigung_of`), Kz 110 (`marker`), der Status des Berichts (`RevisionStatus`, `revision_status`), die Änderung eines Auftrags an das Unternehmensregister (`register_changes`, `fee_factor`) |

Der Kern ist reines Python ohne Frappe, mit 100 % Testabdeckung (`steuerbote/jahresmeldung/tests`). Die Frappe-Tests der Grundlage laufen an zwei Test-DocTypes, die sie selbst anlegen (`steuerbote/tests/annual_document.py`): „Steuerbote Test Annual Filing“ mit dem Lebenslauf `FILING`, der als Körperschaftsteuererklärung oder E-Bilanz über ERiC geht, und „Steuerbote Test Annual Accounts“ mit `ACCOUNTS`.

### Löschen der Transaktionen eines Unternehmens

„Transaktionen des Unternehmens löschen“ in ERPNext lässt die DocTypes aus `company_data_to_be_ignored` in `hooks.py` aus. Dort stehen die Einstellungen Jahresmeldungen, denn sie halten, was kein Hauptbuch wieder ergibt, etwa den Tag der Feststellung und die Vorträge und Vorauszahlungen der Bescheide, und die Belege der Jahresmeldungen: `Annual VAT Return`, `Electronic Balance Sheet`, `Corporate Income Tax Return`, `Trade Tax Return` und `Annual Accounts`. Einen Namen ohne DocType lehnt der Löschauftrag ab, deshalb nennt `hooks.py` einen Beleg nur, wenn die App seinen DocType mitbringt.

## Grenzen

- Ob ELSTER bei einer berichtigten Körperschaft- oder Gewerbesteuererklärung den Freitext nach § 150 Abs. 7 AO erwartet, ist nicht bestätigt.
- Welchen Status des Berichts eine Korrektur der E-Bilanz trägt, entscheidet die Steuerberatung; Steuerbote prüft nur, dass eine Berichtigung einen nennt und nicht „Korrektur durch Finanzverwaltung“.
- Je Unternehmen eine Steuernummer für Körperschaftsteuer, Gewerbesteuer und E-Bilanz.
- Ohne Hersteller-ID läuft die Übermittlung über ERiC nur als Simulation; die E-Bilanz lässt sich dann nur auf anderem Weg abgeben.

## Quellen

- § 150 Abs. 7 Satz 1 AO; § 4 Abs. 2 EStG; § 42a Abs. 2 GmbHG; § 325 Abs. 1b Satz 1 HGB; JVKostG, Anlage 1 (Kostenverzeichnis), Vorbemerkung 1.4.2, gelesen am 23.11.2026 auf gesetze-im-internet.de.
- ERiC-Dokumentation 44.3.6.0 ([ERiC-44.3.6.0-Dokumentation.zip](https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Dokumentation.zip)): Entwicklerhandbuch Kap. 5.1.2.4.1, 5.1.4.3, 5.1.4.4 und 9.7.1; Jahresdokumentation E50 2026 (Blätter „Allg. Information“, „USt2A - Felder“, „USt2A - Regeln“), E30 2025 („KSt1 - Felder“, „KSt1 - Regeln“) und E20 2025 („GewSt1A - Felder“, „GewSt1A - Regeln“).
- FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d und 9 (esteuer.de, `download/taxonomie/FAQ_Version_2026-01.pdf`); HGB-Taxonomie 6.9, `de-gcd-2025-04-01.xsd`, `de-gcd-2025-04-01-label-de.xml` und `de-gcd-2025-04-01-reference-fiscal.xml`.
- Allgemeine Nutzungsbedingungen für das Unternehmensregister, §§ 13 und 14 ([D088.pdf](https://www.publikations-plattform.de/order/D088.pdf)).
- ELSTER-Hilfe „Benutzeranleitung zum Hochladen von Formulardaten“, Abschnitt „Allgemeines“ (https://www.elster.de/eportal/helpGlobal?themaGlobal=ustva_upload): Mein ELSTER importiert keine der Jahresmeldungen.
