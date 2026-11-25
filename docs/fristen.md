# Fristen

Steuerbote kennt die Fristen der Umsatzsteuer-Voranmeldung, der Zusammenfassenden Meldung und der Sondervorauszahlung und, mit den Einstellungen Jahresmeldungen, die der Jahresmeldungen: Umsatzsteuererklärung, Körperschaftsteuererklärung, Gewerbesteuererklärung, E-Bilanz, Feststellung und Offenlegung des Jahresabschlusses. Der Bericht „Offene Fristen“ zeigt sie für ein Unternehmen oder für alle, eine E-Mail erinnert jeden Tag an die, die nicht abgegeben sind. Welche Fristen es gibt und wann sie fällig sind, rechnet der Kern unter `steuerbote/deadlines` aus den Einstellungen Umsatzsteuer-Voranmeldung, mit den Regeln der Kerne der Voranmeldung, der Zusammenfassenden Meldung und der Dauerfristverlängerung, und aus den Einstellungen Jahresmeldungen, mit den Regeln der Kerne der Umsatzsteuererklärung und des Jahresabschlusses. Er ist reines Python ohne Frappe-Import und hat vollständige Testabdeckung. Die Seite ersetzt keine Steuerberatung.

## Welche Fristen

| Art | Je | Fällig | Quelle |
|---|---|---|---|
| Umsatzsteuer-Voranmeldung | Voranmeldungszeitraum der Einstellungen, monatlich oder vierteljährlich | am 10. Tag nach Ablauf des Zeitraums, mit Dauerfristverlängerung seines Jahres einen Monat später | § 18 Abs. 1 Satz 1 UStG; Anleitung USt 1 E 2026, Zeilen 53 bis 54; § 46 UStDV; `Period.deadline` in `ustva/period.py` |
| Zusammenfassende Meldung | Meldezeitraum des Abgaberhythmus der Einstellungen | am 25. Tag nach Ablauf des Meldezeitraums, ohne Dauerfristverlängerung | § 18a Abs. 1 UStG; BZSt „Fristen“ (ZM); `ReportingPeriod.deadline` in `zm/period.py` |
| Sondervorauszahlung | Jahr mit Dauerfristverlängerung, dessen erster Voranmeldungszeitraum ein Monat ist | mit der ersten Voranmeldung des Jahres ohne die Verlängerung, also am 10. Februar | § 47 Abs. 1 und § 48 Abs. 1 und 2 UStDV; Anleitung USt 5 E 2026, Zeilen 8 bis 9; `antrag_deadline` und `sondervorauszahlung_deadline` in `dauerfrist/period.py` |

- **Voranmeldung.** Eine Frist gibt es für jeden Voranmeldungszeitraum, den die Regeln der Einstellungen vorsehen (`rhythm_for` in `vat_return_settings/rules.py`). Monate mit „Keine“ und Monate vor der ersten Regel haben keine: Den Zeitraum legt das Finanzamt fest, Steuerbote rät ihn nicht.
- **Zusammenfassende Meldung.** Die Meldezeiträume ergeben sich aus dem Abgaberhythmus der Einstellungen wie beim Beleg (`goods_period` und `coverage` in `zm/rhythm.py`), auch die zwei Monate eines Quartals nach einem Wechsel zur monatlichen Abgabe und das Kalenderjahr, siehe [Zusammenfassende Meldung](zm.md#meldezeiträume-und-fristen). Ohne Abgaberhythmus gibt es keine Frist.
- **Sondervorauszahlung.** Ein Unternehmen, das monatlich abgibt, zahlt sie in jedem Jahr mit Dauerfristverlängerung „bis zum gesetzlichen Zeitpunkt der Übermittlung der ersten Voranmeldung“ (§ 48 Abs. 2 Satz 1 UStDV), im Jahr des Antrags mit dem Antrag (§ 48 Abs. 1 UStDV). Beginnen die Voranmeldungen eines Jahres später, etwa im April, ist sie mit der Voranmeldung für April fällig. Wer vierteljährlich abgibt, zahlt keine (§ 47 Abs. 1 UStDV) und hat hier keine Frist. Siehe [Dauerfristverlängerung](dauerfristverlaengerung.md#fristen).
- **Über den Jahreswechsel.** Die Einstellungen halten die Dauerfristverlängerung je Jahr fest; sie gilt aber fort, bis das Unternehmen erklärt, sie nicht mehr in Anspruch zu nehmen, oder das Finanzamt sie widerruft (§ 46 UStDV; Anleitung USt 5 E: „Die Fristverlängerung gilt solange, bis …“). Fehlt die Zeile eines Jahres, nachdem ein früheres Jahr die Verlängerung hat, fällt deshalb keine Frist still weg (`carried_dauerfrist` in `vat_return_settings/rules.py`): Wer monatlich abgibt, behält die Frist der Sondervorauszahlung des Jahres, und die Voranmeldungen des Jahres stehen mit dem Tag ohne Verlängerung im Bericht, der nie zu spät ist; beide tragen den Hinweis „Keine Dauerfristverlängerung für das Jahr erfasst …“. Erst die Zeile des Jahres, mit Haken oder ohne, löst ihn auf; eine Zeile ohne Haken beendet die Verlängerung für die Jahre danach. „Steuerbote einrichten“ nennt das fehlende Jahr ebenso.
- **Wochenende und Feiertage.** „Fällt das Ende einer Frist auf einen Sonntag, einen gesetzlichen Feiertag oder einen Sonnabend, so endet die Frist mit dem Ablauf des nächstfolgenden Werktags.“ (§ 108 Abs. 3 AO; für die ZM über § 18a Abs. 11 UStG) Die Feiertage kommen für alle drei Arten aus der Standard-Feiertagsliste des Unternehmens, ohne die wöchentlich freien Tage (`steuerbote/holiday_list.py`). Gemeint sind die Feiertage am Sitz der Behörde: für Voranmeldung und Sondervorauszahlung die des Landes des Finanzamts, das die Liste deshalb halten soll. Für die ZM ist die Behörde das BZSt; ein Feiertag nur einzelner Länder fällt nie auf den 25. bis 28. eines Monats, den Tagen, auf die eine ZM-Frist fallen kann, so dass dort die Feiertage aller Länder genügen. Hat das Unternehmen keine Liste, nimmt Steuerbote die Feiertage, die in jedem Land gelten: Neujahr, Karfreitag, Ostermontag, 1. Mai, Christi Himmelfahrt, Pfingstmontag, Tag der Deutschen Einheit (Art. 2 Abs. 2 Einigungsvertrag) und beide Weihnachtsfeiertage (`steuerbote/deadlines/holidays.py`). Sie verschieben eine Frist überall; ein Feiertag nur des eigenen Landes, etwa Fronleichnam, der auf den 10. Juni fallen kann, braucht die Liste. Jede Frist, die § 108 Abs. 3 AO verschiebt, trägt dann den Hinweis „Das Unternehmen hat keine Feiertagsliste …“, und „Steuerbote einrichten“ nennt die fehlende Liste. Das Feld „Fälligkeitsdatum“ der Voranmeldung selbst berücksichtigt die Feiertage noch nicht; fällt der 10. auf einen Feiertag der Liste, nennt der Bericht den nächsten Werktag.

Beispiele aus den Tests:

| Frist | Fällig |
|---|---|
| Voranmeldung Oktober 2026 | Dienstag, 10. November 2026 |
| Voranmeldung Dezember 2026, der 10. Januar ist ein Sonntag | Montag, 11. Januar 2027 |
| Voranmeldung November 2026 mit Dauerfristverlängerung | Montag, 11. Januar 2027 |
| Voranmeldung III. Kalendervierteljahr 2026, der 10. Oktober ist ein Samstag | Montag, 12. Oktober 2026 |
| ZM I. Kalendervierteljahr 2026, der 25. April ist ein Samstag | Montag, 27. April 2026 |
| ZM November 2026 mit beiden Weihnachtsfeiertagen in der Liste | Montag, 28. Dezember 2026 |
| Sondervorauszahlung 2027 | Mittwoch, 10. Februar 2027 |
| Sondervorauszahlung 2026, die Voranmeldungen beginnen im April | Montag, 11. Mai 2026 |

**Nicht in der Übersicht** ist der einmalige Antrag auf Dauerfristverlängerung bei vierteljährlicher Abgabe, denn die Einstellungen halten nicht fest, in welchem Jahr er gestellt wurde. Die Einstellungen kennen die Dauerfristverlängerung nur für ein ganzes Jahr, siehe [Annahmen und offene Punkte](dauerfristverlaengerung.md#annahmen-und-offene-punkte). Die Fristen der Umsatzsteuererklärung und der übrigen Jahresmeldungen stehen unter [Jahresmeldungen](#jahresmeldungen).

## Jahresmeldungen

Hat ein Unternehmen [Einstellungen Jahresmeldungen](architektur.md#einstellungen-jahresmeldungen-annual-filing-settings), kennt Steuerbote auch seine Jahresmeldungen. Der Kern `steuerbote/deadlines/annual.py` bildet sie Jahr für Jahr aus den Angaben je Jahr und den Größenmerkmalen der Einstellungen, den Geschäftsjahren (Fiscal Year) und dem Gründungsdatum des Unternehmens (`date_of_establishment`). Ein Jahr ist der Veranlagungs- oder Erhebungszeitraum und das Jahr, in dem das Wirtschaftsjahr endet, so wie die Belege der Jahresmeldungen es zählen ([Jahresmeldungen](jahresmeldungen.md)). Das erste Jahr ist 2026 ([Roadmap](roadmap.md), „Ab 2026“) oder das Gründungsjahr, wenn es später liegt. Ein Unternehmen ohne Einstellungen Jahresmeldungen hat keine dieser Fristen, denn erst sie sagen, ob eine Steuerberatung mitwirkt und wie groß die Gesellschaft ist.

| Art | Je | Fällig | Abgegeben, wenn | Quelle |
|---|---|---|---|---|
| Umsatzsteuererklärung | Kalenderjahr | sieben Monate nach Ablauf des Jahres, mit Steuerberatung am letzten Tag im Februar des zweiten Folgejahres; keine in einem Jahr als Kleinunternehmer | eine Umsatzsteuererklärung des Jahres abgegeben ist | § 18 Abs. 3 Satz 1 und § 19 Abs. 1 Satz 2 UStG; § 149 Abs. 2 Satz 1, Abs. 3 Nr. 4 und Abs. 4 AO; `filing_deadline` in `ustjahr/years.py` |
| Körperschaftsteuererklärung | Veranlagungszeitraum | wie die Umsatzsteuererklärung, mit ihr die Erklärung zum steuerlichen Einlagekonto (KSt 1 F) | eine Körperschaftsteuererklärung des Jahres abgegeben ist | § 31 Abs. 1 und 1a, § 27 Abs. 2 Satz 4 KStG; § 149 Abs. 3 Nr. 2 AO |
| Gewerbesteuererklärung | Erhebungszeitraum | wie die Umsatzsteuererklärung | eine Gewerbesteuererklärung des Jahres abgegeben ist | § 14a Satz 1 GewStG; § 149 Abs. 3 Nr. 3 AO |
| E-Bilanz | Jahr, in dem das Wirtschaftsjahr endet | mit der Körperschaftsteuererklärung des Jahres; im Gründungsjahr ebenso die Eröffnungsbilanz | eine E-Bilanz des Jahres abgegeben ist, im Gründungsjahr auch eine Eröffnungsbilanz | § 5b Abs. 1 Satz 1 und 4 EStG; FAQ zur E-Bilanz, Version 2026-01, Tz. 5 |
| Feststellung Jahresabschluss | Geschäftsjahr | acht Monate nach seinem Ende, elf für eine kleine Gesellschaft | der Jahresabschluss eingereicht und damit festgestellt ist | § 42a Abs. 2 Satz 1 GmbHG; `adoption_deadline` in `hgb/disclosure.py` |
| Offenlegung Jahresabschluss | Geschäftsjahr | ein Jahr nach seinem Ende; keine für ein Tochterunternehmen, das nach § 264 Abs. 3 HGB befreit ist | der Jahresabschluss übermittelt oder eingestellt ist | § 325 Abs. 1a Satz 1 und Abs. 4 Satz 2 HGB; `disclosure_deadline` in `hgb/disclosure.py` |

- **Steuerberatung.** Mit „Mitwirkung einer Steuerberatung“ in den Angaben des Jahres sind die drei Erklärungen und die E-Bilanz „spätestens bis zum letzten Tag des Monats Februar [...] des zweiten auf den Besteuerungszeitraum folgenden Kalenderjahres“ abzugeben (§ 149 Abs. 3 AO), ohne sie „spätestens sieben Monate nach Ablauf des Kalenderjahres“ (§ 149 Abs. 2 Satz 1 AO). Die Verlängerungen nach Art. 97 § 36 EGAO enden mit dem Jahr 2024. Die Regeln sind für die drei Erklärungen dieselben, deshalb rechnet Steuerbote jeden ihrer Tage mit `filing_deadline` des Kerns der Umsatzsteuererklärung.
- **Vorabanforderung.** Ordnet das Finanzamt eine Erklärung früher an (§ 149 Abs. 4 Satz 1 AO), gilt der Tag aus „Vorab angefordert“ der Angaben des Jahres. „In den Fällen der Sätze 1 und 3 erstreckt sich eine Anordnung auf alle Erklärungen im Sinne des Absatzes 3, die vom betroffenen Steuerpflichtigen für den gleichen Besteuerungszeitraum oder Besteuerungszeitpunkt abzugeben sind“ (§ 149 Abs. 4 Satz 7 AO): Der früheste Tag eines Jahres gilt deshalb für alle drei Erklärungen und die E-Bilanz, auch wenn die Einstellungen ihn nur bei einer nennen. Eine Vorabanforderung gibt es nur, wo eine Steuerberatung mitwirkt; das prüfen die Einstellungen.
- **Wochenende und Feiertage.** Die Tage der Erklärungen und der E-Bilanz verschiebt § 108 Abs. 3 AO wie die der Voranmeldung auf den nächsten Werktag, mit den Feiertagen der Standard-Feiertagsliste des Unternehmens; für 2026 ist der 31. Juli 2027 ein Samstag. Die Tage des Jahresabschlusses verschiebt Steuerbote nicht: Ob § 193 BGB sie verschiebt, ist ungeprüft, deshalb nennt der Bericht den früheren Tag mit einem Hinweis.
- **Kleinunternehmer.** In einem Jahr mit „Kleinunternehmer“ gibt es keine Umsatzsteuererklärung, denn für ihn finden „die Erklärungspflichten (§ 18 Absatz 1 bis 4)“ keine Anwendung (§ 19 Abs. 1 Satz 2 UStG).
- **Keine Umsatzsteuererklärung geschuldet.** Wer kein Kleinunternehmer ist und trotzdem keine Erklärung schuldet, etwa eine Holding, die nur Anteile hält und veräußert und damit kein Unternehmer im Sinne des § 2 UStG ist, oder ein Unternehmen, das das Finanzamt befreit hat, erklärt das in den Angaben des Jahres mit „Keine Umsatzsteuererklärung geschuldet“ und einem Grund aus der Liste: „Kein Unternehmer (§ 2 UStG)“, „Vom Finanzamt befreit“ oder „Anderer Grund“, dieser mit einem Vermerk, der ihn nennt; „Aktenzeichen und Vermerk“ hält etwa Schreiben und Datum des Finanzamts fest. Das ist eine Erklärung des Unternehmens, die es mit seiner Steuerberatung abstimmt: Steuerbote beurteilt die umsatzsteuerliche Stellung nicht, sondern übernimmt sie. Der Bericht und die Erinnerung nennen für das Jahr dann keine Umsatzsteuererklärung, eine Umsatzsteuererklärung des Jahres lässt sich weder anlegen noch berechnen, und „Steuerbote einrichten“ nennt die Erklärung mit ihrem Grund. Ohne den Haken bleibt alles, wie es war: Die Erklärung ist geschuldet. Ein Grund ohne Haken, der Haken ohne Grund und eine Vorabanforderung der Umsatzsteuererklärung in einem solchen Jahr lehnen die Einstellungen ab.
- **E-Bilanz.** Sie hat keine eigene Frist und geht mit der Körperschaftsteuererklärung des Veranlagungszeitraums, in dem das Wirtschaftsjahr endet (FAQ zur E-Bilanz, Tz. 5); Steuerbote nennt sie mit deren Tag. „Im Fall der Eröffnung des Betriebs sind die Sätze 1 bis 3 entsprechend anzuwenden“ (§ 5b Abs. 1 Satz 4 EStG): Im Gründungsjahr nennt der Bericht deshalb neben der E-Bilanz „2026“ die Eröffnungsbilanz in einer eigenen Zeile „Eröffnungsbilanz 2026“ am selben Tag, und erst mit beiden ist die E-Bilanz des Jahres abgegeben. Dass die Eröffnungsbilanz bis dahin genügt, ist eine Annahme und ungeprüft.
- **Größenklasse.** Ob die Gesellschaft klein ist (§ 267 Abs. 1 HGB; eine Kleinstkapitalgesellschaft ist es auch, § 267a Abs. 1 HGB), nimmt Steuerbote aus den Größenmerkmalen der Einstellungen: der angewandten Größenklasse zum Abschlussstichtag des Geschäftsjahres. Fehlt sie, gelten acht Monate, und der Bericht sagt es.
- **Geschäftsjahr.** Das Geschäftsjahr eines Jahres endet am letzten Tag des spätesten Geschäftsjahres (Fiscal Year), das in diesem Jahr endet und das Unternehmen oder kein Unternehmen nennt; gibt es keines, am 31. Dezember, denn Steuerbote nimmt das Wirtschaftsjahr als Kalenderjahr.
- **Befreiung.** In einem Jahr mit „Befreit nach § 264 Abs. 3 HGB“ gibt es keine Offenlegung. Die Feststellung bleibt, denn § 42a Abs. 2 GmbHG gilt weiter.
- **Zu spät.** „Gegen denjenigen, der seiner Verpflichtung zur Abgabe einer Steuererklärung nicht oder nicht fristgemäß nachkommt, kann ein Verspätungszuschlag festgesetzt werden“ (§ 152 Abs. 1 Satz 1 AO). Festzusetzen ist er, wenn die Erklärung nicht binnen 14 Monaten nach Ablauf des Kalenderjahrs oder nach einer Vorabanforderung nicht bis zu dem bestimmten Zeitpunkt abgegeben ist (§ 152 Abs. 2 Nr. 1 und 3 AO). Steuerbote rechnet keinen Zuschlag; eine überschrittene Frist bleibt im Bericht, bis sie abgegeben ist.
- **Nicht in der Übersicht** sind die Abschlusszahlung der Umsatzsteuererklärung, denn sie ist „einen Monat nach dem Eingang der Steueranmeldung fällig“ (§ 18 Abs. 4 Satz 1 UStG) und folgt der Abgabe, sowie die Vorauszahlungen der Körperschaft- und Gewerbesteuer.

### Beispiele der Jahresmeldungen

Aus den Tests:

| Frist | Fällig |
|---|---|
| Umsatzsteuererklärung 2026, der 31. Juli 2027 ist ein Samstag | Montag, 2. August 2027 |
| Körperschaftsteuererklärung 2026 mit Steuerberatung | Dienstag, 29. Februar 2028 |
| Gewerbesteuererklärung 2026, vorab angefordert für Samstag, den 16. Oktober 2027 | Montag, 18. Oktober 2027 |
| E-Bilanz 2026 | Montag, 2. August 2027 |
| Eröffnungsbilanz einer GmbH, gegründet im März 2027 | Montag, 31. Juli 2028 |
| Feststellung des Jahresabschlusses 2026 einer kleinen Gesellschaft | Dienstag, 30. November 2027 |
| Feststellung des Jahresabschlusses 2026 ohne Größenklasse | Dienstag, 31. August 2027 |
| Offenlegung des Jahresabschlusses 2026 | Freitag, 31. Dezember 2027 |
| Offenlegung des Jahresabschlusses 2027, ohne Verschiebung vom Sonntag | Sonntag, 31. Dezember 2028 |

### Hinweise

Der Bericht und die Erinnerung nennen in der Spalte „Hinweis“, worauf der Tag einer Frist beruht, wo es mehr ist als die Regel ihrer Art (`Note` in `deadlines/annual.py`):

| Hinweis | Wann |
|---|---|
| Mit Steuerberatung (§ 149 Abs. 3 AO) | die Angaben des Jahres nennen die Mitwirkung einer Steuerberatung und keine Vorabanforderung |
| Vorabanforderung des Finanzamts (§ 149 Abs. 4 AO) | eine Erklärung des Jahres ist vorab angefordert |
| Keine eigene Frist: mit der Körperschaftsteuererklärung | an jeder E-Bilanz |
| Eröffnungsbilanz des Gründungsjahres (§ 5b Abs. 1 Satz 4 EStG); die Frist ist angenommen | an der Eröffnungsbilanz |
| Keine Größenklasse für das Geschäftsjahr: acht Monate (§ 42a Abs. 2 GmbHG) | an der Feststellung, wenn die Größenmerkmale für den Abschlussstichtag keine Klasse halten |
| Fällt auf ein Wochenende; ob § 193 BGB den Tag verschiebt, ist ungeprüft | an der Feststellung und der Offenlegung |
| Keine Dauerfristverlängerung für das Jahr erfasst, aber eine für ein früheres Jahr, die gilt, bis sie aufgegeben oder widerrufen ist (§ 46 UStDV): das Jahr in den Einstellungen Umsatzsteuer-Voranmeldung erfassen, mit oder ohne Verlängerung | an den Voranmeldungen und der Sondervorauszahlung eines Jahres ohne Zeile, siehe [Über den Jahreswechsel](#welche-fristen) |
| Das Unternehmen hat keine Feiertagsliste: Nur die Feiertage aller Länder verschieben den Tag (§ 108 Abs. 3 AO) | an jeder Frist außer Feststellung und Offenlegung, wenn das Unternehmen keine Standard-Feiertagsliste hat |

### Aus den Einstellungen Jahresmeldungen

| Feld | Bezeichnung | Wofür |
|---|---|---|
| `years` | Angaben je Jahr | je Jahr die folgenden Felder; ein Jahr ohne Zeile hat weder Steuerberatung noch Vorabanforderung |
| `advisor_prepares` | Mitwirkung einer Steuerberatung | die drei Erklärungen und die E-Bilanz am letzten Tag im Februar des zweiten Folgejahres |
| `early_request_ust` | Vorab angefordert: Umsatzsteuererklärung | der Tag einer Vorabanforderung, wie die beiden folgenden |
| `early_request_kst` | Vorab angefordert: Körperschaftsteuererklärung | |
| `early_request_gewst` | Vorab angefordert: Gewerbesteuererklärung | |
| `kleinunternehmer` | Kleinunternehmer | keine Umsatzsteuererklärung |
| `no_vat_return` | Keine Umsatzsteuererklärung geschuldet | keine Umsatzsteuererklärung, eine Erklärung des Unternehmens, siehe [Belege der Jahresmeldungen](#belege-der-jahresmeldungen) |
| `no_vat_return_reason` | Grund | Pflicht mit dem Haken: Kein Unternehmer (§ 2 UStG), Vom Finanzamt befreit oder Anderer Grund |
| `no_vat_return_note` | Aktenzeichen und Vermerk | etwa Schreiben und Datum des Finanzamts; Pflicht beim anderen Grund |
| `exempt_264_3` | Befreit nach § 264 Abs. 3 HGB | keine Offenlegung |
| `size_history` | Größenmerkmale je Geschäftsjahr | die angewandte Größenklasse zum Abschlussstichtag für die Feststellung |

Der Tag, an dem die Einstellungen angelegt wurden, gilt für die Jahresmeldungen wie der der Einstellungen Umsatzsteuer-Voranmeldung für die übrigen Fristen, siehe [Welche Fristen erscheinen](#welche-fristen-erscheinen).

### Belege der Jahresmeldungen

Welcher Beleg welche Art abgibt, hält ein Verzeichnis je DocType fest (`DOCTYPES` in `deadlines/annual.py`). Steuerbote liest die Belege an den Feldern, die jeder Beleg einer Jahresmeldung trägt (`standard_fields` in `jahresmeldung/lifecycle.py`, siehe [Jahresmeldungen](jahresmeldungen.md)): Jahr, Status, Abgegeben über und Abgegeben am, dazu die ELSTER-Übermittlungen des Belegs.

| DocType | Art | Wie er abgibt |
|---|---|---|
| `Annual VAT Return` | Umsatzsteuererklärung | eingereicht, oder über Steuerbote gesendet mit Annahme oder unbekanntem Ergebnis, auch wenn er danach ein Entwurf blieb |
| `Corporate Income Tax Return` | Körperschaftsteuererklärung | ebenso |
| `Trade Tax Return` | Gewerbesteuererklärung | ebenso |
| `Electronic Balance Sheet` | E-Bilanz | ebenso; eine mit der Bilanzart (`statement_type`) „Eröffnungsbilanz“ gibt die Eröffnungsbilanz ab |
| `Annual Accounts` | Feststellung Jahresabschluss, Offenlegung Jahresabschluss | eingereicht stellt er fest; „Übermittelt“ oder „Eingestellt“ legt er offen, nach dem Upload auch, wenn er für eine Änderung storniert und ersetzt wird, denn „Für die Wahrung der Fristen [...] ist der Zeitpunkt der Übermittlung der Unterlagen maßgebend“ (§ 325 Abs. 4 Satz 2 HGB); ein stornierter stellt nichts mehr fest |

**Neue Module.** Die App bringt den DocType jedes dieser Belege mit, deshalb liest Steuerbote sie auf jeder Site. Ein Modul, dessen Belege ihre Fristen anders als über diese Felder abgeben, ergänzt seinen Eintrag im Verzeichnis. Sein Fälligkeitsdatum gibt einem Beleg `annual_deadline(company, kind, year)` in `steuerbote/steuerbote/deadlines.py`, für die Eröffnungsbilanz mit `opening_balance=True`: derselbe Tag wie im Bericht.

## Abgegeben, offen oder fehlt

Jede Frist hat einen Status. Er kommt aus den Belegen des Unternehmens für ihren Zeitraum:

| Status | Bedeutung |
|---|---|
| Abgegeben | ein Beleg des Zeitraums trägt den Vermerk der Abgabe |
| Offen | es gibt einen Beleg, aber keiner ist abgegeben |
| Fehlt | es gibt keinen Beleg |

Als abgegeben zählt:

- **Voranmeldung:** eine Meldung des Zeitraums ist eingereicht, also „Abgegeben“ oder „Ersetzt“.
- **Zusammenfassende Meldung:** eine Meldung des Meldezeitraums ist eingereicht, nach einem Senden über ERiC oder mit „In Mein ELSTER abgegeben“ oder „Als außerhalb abgegeben vermerken“, auch eine Berichtigung.
- **Sondervorauszahlung:** eine Dauerfristverlängerung des Unternehmens für das Jahr ist eingereicht. Eine Anmeldung, die für ihre Berichtigung storniert wurde, bleibt abgegeben, denn das Finanzamt hat sie.
- **Jahresmeldungen:** wie unter [Belege der Jahresmeldungen](#belege-der-jahresmeldungen): eine Erklärung oder E-Bilanz des Jahres ist eingereicht, der Jahresabschluss für die Feststellung eingereicht und für die Offenlegung übermittelt oder eingestellt.

Ebenso zählt jeder dieser Belege als abgegeben, sobald er über Steuerbote gesendet wurde, mit Annahme durch ELSTER oder unbekanntem Ergebnis, auch wenn er danach ein Entwurf blieb oder storniert oder verworfen wurde, denn das Finanzamt oder das BZSt hat ihn oder kann ihn haben; abgegeben ist er am Tag, an dem die Übermittlung endete. Das ist dieselbe Regel wie im [Lebenslauf einer Meldung](architektur.md#lebenslauf-einer-meldung) (`filings` in `elster_transmission/transmission.py`).

Gibt es mehrere Belege, zeigt die Frist den zuletzt angelegten abgegebenen, sonst den zuletzt angelegten, und daneben den Status, den dieser Beleg hat, etwa „Berechnet“ oder „Festgestellt“ (Spalte „Stand des Belegs“).

**Keine Nullmeldung.** Eine Zusammenfassende Meldung ist nur für einen Meldezeitraum abzugeben, in dem etwas zu melden ist (§ 18a Abs. 1 UStG); „Sog. „Nullmeldungen“ sind nicht abzugeben“ (BZSt, Anleitung zur ZM, III.1). Ohne Beleg nimmt Steuerbote eine ZM deshalb nur an, wenn im Meldezeitraum ein Beleg auf ein Konto der Kz 41 oder 42 bucht, in den Monaten seiner Lieferungen, oder auf ein Konto der Kz 21, in den Monaten seiner sonstigen Leistungen. Das Hauptbuch liest es wie „Berechnen“ (`zm_sources.shares`) mit der Kontenzuordnung des Unternehmens. Passt keine Kontenzuordnung zum Jahr, zählt jeder Meldezeitraum. Hebt sich ein Beleg mit einer Gutschrift auf, nimmt Steuerbote die ZM trotzdem an; die Meldung hätte dann keine Zeile.

## Welche Fristen erscheinen

Der Bericht und die Erinnerung nennen dieselben Fristen, der Bericht bis zu seiner Vorschau, die Erinnerung bis zu ihrem Vorlauf:

- jede Frist, die von heute an bis zum letzten Tag der Vorschau oder des Vorlaufs fällig ist, mit jedem Status;
- jede Frist, die überschritten und nicht abgegeben ist, bis sie abgegeben ist: mit Beleg immer, ohne Beleg, wenn sie am Tag oder nach dem Tag fällig war, an dem die Einstellungen angelegt wurden, die sie verlangen, die Einstellungen Umsatzsteuer-Voranmeldung oder die Einstellungen Jahresmeldungen. Ob eine Frist davor außerhalb von Steuerbote eingehalten wurde, kann Steuerbote nicht wissen. Eine abgegebene Frist, die vorbei ist, erscheint nicht mehr.

Fristen am selben Tag stehen in der Reihenfolge Voranmeldung, Zusammenfassende Meldung, Sondervorauszahlung, Umsatzsteuererklärung, Körperschaftsteuererklärung, Gewerbesteuererklärung, E-Bilanz, Feststellung Jahresabschluss, Offenlegung Jahresabschluss.

Vor dem Start der Bücher erscheint keine Frist: Nennen die Einstellungen Umsatzsteuer-Voranmeldung in „Bücher in ERPNext ab“ den ersten Tag der Bücher in ERPNext, lässt `upcoming` jede Voranmeldung und Zusammenfassende Meldung eines Zeitraums aus, der davor beginnt, und die Sondervorauszahlung und die Jahresmeldungen eines Jahres vor dem Jahr des Starts (`books_start` von `CompanyRules`). Diese Zeiträume gibt ab, wer die Bücher dieser Zeit führt, etwa die Voranmeldung für Dezember bei einem Start am 1. Januar; Steuerbote erinnert nicht an sie. Siehe [Start mit Steuerbote im laufenden Betrieb](einrichtung.md#start-mit-steuerbote-im-laufenden-betrieb).

## Der Bericht „Offene Fristen“

Der Bericht steht im Arbeitsbereich „Steuern“ im Abschnitt „Fristen“ und in der Seitenleiste unter „Berichte“, für die Rollen Accounts Manager, Accounts User und System Manager.

| Filter | Inhalt |
|---|---|
| Unternehmen | ein Unternehmen; leer alle Unternehmen mit Einstellungen Umsatzsteuer-Voranmeldung oder Einstellungen Jahresmeldungen, die der Benutzer lesen darf |
| Vorschau (Tage) | wie viele Tage ab heute der Bericht vorausschaut, Vorgabe 60 |

| Spalte | Inhalt |
|---|---|
| Unternehmen | das Unternehmen |
| Art | Umsatzsteuer-Voranmeldung, Zusammenfassende Meldung, Sondervorauszahlung oder eine der [Jahresmeldungen](#jahresmeldungen) |
| Zeitraum | der Voranmeldungszeitraum, der Meldezeitraum, das Jahr der Sondervorauszahlung oder der Jahresmeldung, im Gründungsjahr auch „Eröffnungsbilanz 2026“ |
| Fällig am | der Tag der Frist |
| Tage | die Tage bis dahin, negativ für eine überschrittene Frist |
| Status | Abgegeben, Offen oder Fehlt |
| Beleg | der Beleg; fehlt er, legt „Erstellen“ einen neuen mit Unternehmen und Zeitraum an, eine Eröffnungsbilanz mit ihrer Bilanzart |
| Stand des Belegs | der Status, den der Beleg hat, etwa „Entwurf“, „Berechnet“, „Bereit“, „Abgegeben“, „Festgestellt“ oder „Übermittelt“ |
| Hinweis | worauf der Tag beruht, siehe [Hinweise](#hinweise) |

Die Zeilen stehen nach dem Tag der Frist geordnet. Der Bericht rechnet nichts selbst: Er liest mit `steuerbote/steuerbote/deadlines.py` Einstellungen, Belege, Feiertage und Hauptbuch, und der Kern bildet die Fristen.

## Die Erinnerung

Jeden Tag läuft der Job `send_reminders` (`scheduler_events` in `hooks.py`, „daily“). Er geht jedes Unternehmen mit Einstellungen Umsatzsteuer-Voranmeldung oder Einstellungen Jahresmeldungen durch. Nennen seine Einstellungen Umsatzsteuer-Voranmeldung Empfänger, schickt er ihnen eine E-Mail mit den Fristen, die nicht abgegeben sind und innerhalb des Vorlaufs fällig werden oder überschritten sind, wie unter [Welche Fristen erscheinen](#welche-fristen-erscheinen), auch denen der Jahresmeldungen. Die E-Mail ist deutsch: „Steuerbote: offene Fristen für …“, darin eine Tabelle wie der Bericht mit Art, Zeitraum, Fällig am, Tage, Status, einem Link auf den Beleg oder auf einen neuen Beleg des Zeitraums, Stand des Belegs und Hinweis, darunter ein Link auf den Bericht. Die Tabelle hat Linien und Abstand als HTML-Attribute, die jedes E-Mail-Programm ohne Stylesheet zeigt, und lädt nichts von außen. Der Textteil der E-Mail kommt aus einer eigenen Vorlage (`steuerbote/templates/emails/steuerbote_deadline_reminder.txt`) und nennt jede Frist mit der vollen Adresse ihres Belegs und die Adresse des Berichts, so dass auch ein E-Mail-Programm ohne HTML die Links zeigt. Sie geht über die E-Mail-Warteschlange von Frappe und braucht ein ausgehendes E-Mail-Konto.
- **Das ausgehende E-Mail-Konto ist eines der Site.** Sobald eine Site ein Standard-Konto für ausgehende E-Mails hat, sendet nicht nur die Erinnerung, sondern jede E-Mail-Quelle der Site: Benachrichtigungen, Erinnerungen anderer Apps und alles, was in der E-Mail-Warteschlange (Email Queue) wartet. Wer ein Konto einschaltet, prüft vorher die Warteschlange und die Benachrichtigungen der Site. Die Fußzeile unter jeder E-Mail, etwa „Sent via ERPNext“, ist eine Einstellung der Site, nicht von Steuerbote: Sie steht in den Systemeinstellungen (System Settings) unter „Standard-E-Mail-Fußzeile deaktivieren“ und „Fußzeile“.

- **Jeden Tag, bis abgegeben ist.** Eine Frist steht vom ersten Tag des Vorlaufs an jeden Tag in der E-Mail, auch nach ihrem Ablauf, bis ihr Beleg abgegeben ist. Ist an einem Tag nichts offen, geht keine E-Mail.
- **Nie zweimal am selben Tag.** Jede Frist der E-Mail hält eine „Fristerinnerung“ (`Deadline Reminder`) fest. Läuft der Job an einem Tag noch einmal, schickt er nur Fristen, an die an diesem Tag noch nicht erinnert wurde, etwa nach einem längeren Vorlauf, und sonst nichts.
- **Ohne Empfänger** geht nichts hinaus, und es gibt keinen Fehler. Empfänger und Vorlauf stehen in den Einstellungen Umsatzsteuer-Voranmeldung; ein Unternehmen, das nur Einstellungen Jahresmeldungen hat, bekommt keine Erinnerung, der Bericht zeigt seine Fristen trotzdem.
- **Ungültige Einträge.** Eine Zeile, die keine E-Mail-Adresse ist, lehnt schon das Speichern der Einstellungen ab und nennt sie. Steht doch eine im Feld, etwa aus der Zeit vor dieser Prüfung, bekommt sie keine E-Mail, und das Fehlerprotokoll (Error Log) nennt sie, in der Sprache der Site wie jeder Eintrag des Jobs.
- **Ohne ausgehendes E-Mail-Konto** erreicht die Erinnerung niemanden. Das Speichern der Einstellungen sagt es, wenn sie Empfänger nennen, und „Steuerbote einrichten“ ebenso.
- **Fehler bei einem Unternehmen.** Scheitert die Erinnerung eines Unternehmens, etwa an seinen Einstellungen, nimmt Steuerbote ihre Änderungen zurück, schreibt den Fehler in das Fehlerprotokoll und macht mit den anderen Unternehmen weiter.

### Fristerinnerung (`Deadline Reminder`)

Ein Dokument je Frist und Tag einer Erinnerung, mit den Adressen, an die sie ging. Nur der Server legt es an, niemand ändert es; ein System Manager darf es löschen, dann kann an die Frist am selben Tag noch einmal erinnert werden. Sein Name ist aus Unternehmen, Art, Zeitraum, Fälligkeit und Tag gebildet, deshalb lässt sich dieselbe Erinnerung nicht zweimal anlegen. Die Liste steht in der Seitenleiste als „Fristerinnerungen“.

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `company` | Unternehmen | |
| `kind` | Art | eine der Arten des Berichts |
| `period_label` | Zeitraum | wie im Bericht |
| `due_date` | Fällig am | der Tag der Frist zur Zeit der Erinnerung |
| `sent_on` | Gesendet am | der Tag der Erinnerung |
| `recipients` | Empfänger | die Adressen, an die die Erinnerung ging, eine je Zeile |

## Einstellungen

Im Abschnitt „Fristen“ der Einstellungen Umsatzsteuer-Voranmeldung:

| Feld | Bezeichnung | Inhalt |
|---|---|---|
| `deadline_recipients` | Empfänger der Erinnerung | E-Mail-Adressen, eine je Zeile; leer geht keine Erinnerung hinaus; eine Zeile, die keine Adresse ist, lehnt das Speichern ab |
| `reminder_days` | Vorlauf (Tage) | ab wie vielen Tagen vor der Fälligkeit die Erinnerung eine Frist nennt, Vorgabe 7 |

Die Fristen selbst kommen aus den Regeln der Einstellungen: Voranmeldungszeiträume, Dauerfristverlängerung je Jahr und Abgaberhythmus der Zusammenfassenden Meldung, siehe [Einstellungen je Unternehmen und Zeitraum](architektur.md#einstellungen-je-unternehmen-und-zeitraum), und für die Jahresmeldungen aus den Einstellungen Jahresmeldungen, siehe [Aus den Einstellungen Jahresmeldungen](#aus-den-einstellungen-jahresmeldungen).

## Aufbau

| Modul | Aufgabe |
|---|---|
| `steuerbote/deadlines/obligations.py` | welche Meldungen die Regeln für welchen Zeitraum verlangen und wann sie fällig sind, im Kern ohne Frappe |
| `steuerbote/deadlines/annual.py` | welche Jahresmeldungen ein Jahr verlangt und wann sie fällig sind, wann ein Beleg einer Jahresmeldung sie abgibt, und das Verzeichnis der DocTypes, die sie abgeben, im Kern ohne Frappe |
| `steuerbote/deadlines/holidays.py` | die Feiertage aller Länder für ein Unternehmen ohne Feiertagsliste, im Kern ohne Frappe |
| `steuerbote/deadlines/overview.py` | Status aus den Belegen, die Fristen bis zur Vorschau und die überschrittenen (`upcoming`), im Kern ohne Frappe |
| `steuerbote/steuerbote/deadlines.py` | liest Einstellungen, Geschäftsjahre, Belege, Feiertage und Hauptbuch, gibt einem Beleg einer Jahresmeldung sein Fälligkeitsdatum (`annual_deadline`), schickt die Erinnerung und legt die Fristerinnerungen an, prüft für „Steuerbote einrichten“ Feiertagsliste, Dauerfristverlängerung, Empfänger und E-Mail-Konto (`check_setup`), mit Frappe |
| `steuerbote/steuerbote/report/offene_fristen/` | Bericht „Offene Fristen“ |
| `steuerbote/steuerbote/doctype/deadline_reminder/` | Fristerinnerung |

## Quellen

Die Gesetze der Jahresmeldungen gelesen am 23. November 2026 auf gesetze-im-internet.de.

- **§ 18 Abs. 1, 3 und 4 UStG:** <https://www.gesetze-im-internet.de/ustg_1980/__18.html>
- **§ 18a UStG:** <https://www.gesetze-im-internet.de/ustg_1980/__18a.html>
- **§ 19 Abs. 1 UStG:** <https://www.gesetze-im-internet.de/ustg_1980/__19.html>
- **§§ 46 bis 48 UStDV:** <https://www.gesetze-im-internet.de/ustdv_1980/__46.html>, <https://www.gesetze-im-internet.de/ustdv_1980/__47.html>, <https://www.gesetze-im-internet.de/ustdv_1980/__48.html>
- **§ 108 AO:** <https://www.gesetze-im-internet.de/ao_1977/__108.html>
- **§ 149 Abs. 2 bis 4 AO:** <https://www.gesetze-im-internet.de/ao_1977/__149.html>
- **§ 152 AO:** <https://www.gesetze-im-internet.de/ao_1977/__152.html>
- **Art. 97 § 36 EGAO:** <https://www.gesetze-im-internet.de/aoeg_1977/art_97__36.html>
- **§ 5b EStG:** <https://www.gesetze-im-internet.de/estg/__5b.html>
- **§§ 27 und 31 KStG:** <https://www.gesetze-im-internet.de/kstg_1977/__27.html>, <https://www.gesetze-im-internet.de/kstg_1977/__31.html>
- **§ 14a GewStG:** <https://www.gesetze-im-internet.de/gewstg/__14a.html>
- **§ 42a GmbHG:** <https://www.gesetze-im-internet.de/gmbhg/__42a.html>
- **§§ 264, 267, 267a und 325 HGB:** <https://www.gesetze-im-internet.de/hgb/__264.html>, <https://www.gesetze-im-internet.de/hgb/__267.html>, <https://www.gesetze-im-internet.de/hgb/__267a.html>, <https://www.gesetze-im-internet.de/hgb/__325.html>
- **§ 193 BGB:** <https://www.gesetze-im-internet.de/bgb/__193.html>
- **FAQ zur E-Bilanz**, Version 2026-01, Tz. 5, im Bereich „Schnittstellen zur E-Bilanz § 5b EStG“ von <https://www.esteuer.de/>
- **BMF-Schreiben vom 29. Dezember 2025**, GZ III C 3 - S 7344/00039/007/036, mit den Anleitungen USt 1 E 2026 und USt 5 E 2026, siehe [Dauerfristverlängerung](dauerfristverlaengerung.md#quellen)
- **BZSt „Fristen“ (ZM):** <https://www.bzst.de/DE/Unternehmen/Umsatzsteuer/ZusammenfassendeMeldung/Fristen/fristen_node.html>
- **BZSt „Anleitung zur Zusammenfassenden Meldung“** (USt ZM 1/2021), Textziffer III.1: <https://www.bzst.de/SharedDocs/Downloads/DE/ZM/zm_ausfuellanleitung.pdf?__blob=publicationFile&v=14>
