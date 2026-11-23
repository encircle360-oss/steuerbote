# Einrichtung

Bevor ein Unternehmen seine erste Umsatzsteuer-Voranmeldung berechnet, braucht es zwei Dokumente: die Einstellungen Umsatzsteuer-Voranmeldung mit Steuernummer, Bundesland und Voranmeldungszeitraum und die Kontenzuordnung Umsatzsteuer, die sagt, welches Konto in welche Kennzahl geht. „Steuerbote einrichten“ legt beide in einem Schritt an, so weit Steuerbote sie aus dem Unternehmen ableiten kann, und sagt, was offen bleibt. Die ERiC-Einstellungen gelten für die ganze Site und richtet der Betreiber ein, siehe [ERiC](eric.md). Die Seite ersetzt keine Steuerberatung.

## Steuerbote einrichten

Die Seite „Steuerbote einrichten“ öffnet die Verknüpfung „Einrichten“ im Abschnitt „Einrichtung“ des Arbeitsbereichs „Steuern“, oder die Adresse `/desk/steuerbote-setup`; `?company=` in der Adresse wählt das Unternehmen. Öffnen und ausführen dürfen sie System Manager und Accounts Manager (Rollen der Seite und `frappe.only_for` in `set_up`), und jedes Dokument entsteht mit den Rechten des Benutzers. Ein Benutzer, der nur die Rolle Accounts User hat, sieht die Verknüpfung nicht.

„Einrichten“ führt für das gewählte Unternehmen jeden Schritt aus und zeigt danach je Schritt das Ergebnis, die Hinweise und das Dokument:

| Ergebnis | Bedeutung |
|---|---|
| Angelegt | der Schritt hat sein Dokument angelegt oder ergänzt |
| Übersprungen | das Dokument gab es schon; der Schritt lässt es, wie es ist |
| Offen | der Schritt kann nicht entscheiden, was nur der Benutzer oder das Finanzamt festlegt |
| Fehlgeschlagen | der Schritt brach ab; was er schon geschrieben hatte, ist zurückgenommen |
| Nicht ausgeführt | ein Schritt, den er braucht, hat kein Dokument angelegt oder gefunden |

Hinweise, die mit „Offen“ beginnen, nennen, was der Benutzer noch tun muss. Jeder Schritt legt nur an, was fehlt: Ein zweiter Lauf ändert nichts und sagt „Nichts geändert: … war schon eingerichtet.“ Jeder Schritt läuft in einem eigenen Savepoint der Datenbank, so dass ein Schritt, der fehlschlägt, die anderen nicht mitnimmt.

### Die Schritte

| Schritt | Legt an | Bleibt offen |
|---|---|---|
| Einstellungen Umsatzsteuer-Voranmeldung (`vat_return_settings`) | die Einstellungen mit dem erkannten Kontenrahmen, Soll-Versteuerung und den Vorgaben des DocTypes, ohne Dauerfristverlängerung; das Speichern übernimmt die eigene USt-IdNr. aus dem Feld „Steuernummer“ (`tax_id`) des Unternehmens, wenn es eine deutsche USt-IdNr. ist (`own_vat_id` in `vat_return_settings/rules.py`), und den Datenlieferanten aus Unternehmen und Adresse (`set_datenlieferant`) | Bundesland und Steuernummer: Kein Feld von ERPNext hält sie verlässlich, `tax_id` ist je nach Unternehmen USt-IdNr. oder Steuernummer. Die Einstellungen sind deshalb ohne diese Pflichtfelder gespeichert; das nächste Speichern im Formular verlangt sie. |
| Kontenzuordnung Umsatzsteuer (`vat_return_mapping`) | die Kontenzuordnung mit „Vorgaben laden“ für SKR03 oder SKR04, gekürzt auf die Konten des Unternehmens | bei einem eigenen Kontenrahmen oder einem, der zugleich nach SKR03 und SKR04 aussieht, eine Zuordnung ohne Zeilen: Jedes Konto der Voranmeldung braucht dann eine Regel von Hand oder wird beobachtet |
| Voranmeldungszeitraum (`filing_period`, braucht die beiden ersten) | in Einstellungen ohne Voranmeldungszeitraum die erste Regel ab dem Jahr des Laufs, wo § 18 Abs. 2 UStG den Zeitraum bestimmt | sonst der Zeitraum, den das Finanzamt festgelegt hat |

### Kontenrahmen erkennen

Welcher Kontenrahmen gilt, sagt zuerst die Vorlage, aus der der Kontenplan des Unternehmens angelegt wurde (`Company.chart_of_accounts`). ERPNext 16 bringt „SKR03 mit Kontonummern“ und „SKR04 mit Kontonummern“ mit (`de_kontenplan_SKR03.json` und `de_kontenplan_SKR04.json`); nennt die Vorlage genau einen der beiden, gilt er. Wurde der Kontenplan aus einem anderen Unternehmen kopiert („Existing Company“), zählt dessen Vorlage. Sonst entscheiden die Kontonummern: Drei Konten, auf die jedes Unternehmen mit Umsatzsteuer bucht, nummerieren die Kontenrahmen verschieden.

| Konto (DATEV-Kontenrahmen 2026) | SKR03 | SKR04 |
|---|---|---|
| Erlöse 19 % USt | 8400 | 4400 |
| Umsatzsteuer 19 % | 1776 | 3806 |
| Abziehbare Vorsteuer 19 % | 1576 | 1406 |

Hat das Unternehmen alle drei Konten genau eines Kontenrahmens, gilt dieser (`steuerbote/setup/chart.py`, Rollen `revenue_19`, `output_tax_19` und `input_tax_19` in `defaults.py`). Die Tests prüfen das an den Vorlagen von ERPNext und an den Konten der DATEV-Kontenrahmen.

### Voranmeldungszeitraum

Den Voranmeldungszeitraum legt das Finanzamt fest. Die Einrichtung schlägt ihn nur vor, wo § 18 Abs. 2 UStG ihn aus Daten bestimmt, die Steuerbote hat (Stand des Gesetzes auf gesetze-im-internet.de am 23.11.2026, `steuerbote/setup/rhythm.py`):

- „Voranmeldungszeitraum ist das Kalendervierteljahr. Beträgt die Steuer für das vorangegangene Kalenderjahr mehr als 9 000 Euro, ist der Kalendermonat Voranmeldungszeitraum.“ (Sätze 1 und 2) Die Steuer des Vorjahres rechnet die Einrichtung wie „Berechnen“ als Kz 83 des ganzen Jahres aus dem Hauptbuch, mit der Kontenzuordnung des Unternehmens. Das geht nur, wenn Steuerbote die Kennzahlen des Vorjahres kennt, die Zuordnung die Vorgaben von SKR03 oder SKR04 hat, das Hauptbuch Buchungen des Jahres enthält, kein Konto der Stufe „Sperrt“ einen Saldo und keine Verprobung eine Differenz hat. Für 2026 gibt es deshalb keinen Vorschlag aus der Steuer: Steuerbote kennt die Kennzahlen 2025 nicht.
- „Beträgt die Steuer für das vorangegangene Kalenderjahr nicht mehr als 2 000 Euro, kann das Finanzamt den Unternehmer von der Verpflichtung zur Abgabe der Voranmeldungen […] befreien.“ (Satz 3) Ob es das tut, entscheidet das Finanzamt; der Vorschlag bleibt vierteljährlich und nennt die Möglichkeit.
- „Nimmt der Unternehmer seine berufliche oder gewerbliche Tätigkeit auf, ist im laufenden und folgenden Kalenderjahr Voranmeldungszeitraum der Kalendermonat.“ (Satz 4) Den Beginn nimmt die Einrichtung aus dem Gründungsdatum des Unternehmens (`date_of_establishment`). „Für die Besteuerungszeiträume 2021 bis 2026“ gilt stattdessen Satz 6: Maßgeblich ist bei einem Beginn im laufenden Jahr „die voraussichtliche Steuer des laufenden Kalenderjahres“, bei einem Beginn im Vorjahr dessen Steuer, „in eine Jahressteuer umzurechnen“. Beides kennt Steuerbote nicht, also gibt es bis 2026 keinen Vorschlag; ab 2027 schlägt die Einrichtung den Kalendermonat vor.
- Mit einem Überschuss von mehr als 9.000 € im Vorjahr kann das Unternehmen den Kalendermonat wählen (Abs. 2a); auch das nennt der Vorschlag nur.

Satz 5 (Vorratsgesellschaft und Firmenmantel) hängt an Tatsachen, die das Hauptbuch nicht kennt. Die Regel beginnt im Januar des Jahres des Laufs, bei einem Unternehmen, das in diesem Jahr begonnen hat, mit dem Kalendervierteljahr seines Beginns, denn ein Wechsel beginnt mit einem Kalendervierteljahr. Für frühere Zeiträume trägt der Benutzer weitere Regeln ein. Ein Vorschlag endet immer mit dem offenen Punkt, ihn mit der Festlegung des Finanzamts abzugleichen.

Beispiele aus den Tests:

| Fall | Ergebnis |
|---|---|
| Einrichtung im November 2026, Buchungen 2025 außerhalb von Steuerbote | kein Vorschlag, Steuerbote kennt die Kennzahlen 2025 nicht |
| Einrichtung im Januar 2027, Kz 83 laut Hauptbuch 2026 11.400,00 € | monatlich ab Januar 2027 |
| Einrichtung im Januar 2027, Kz 83 laut Hauptbuch 2026 1.900,00 € | vierteljährlich ab Januar 2027, mit dem Hinweis auf die Befreiung |
| Einrichtung im Januar 2027, Gründung im Mai 2026 | monatlich ab Januar 2027 (Satz 4) |
| Einrichtung im November 2026, Gründung im Mai 2026 | kein Vorschlag (Satz 6) |

### Weitere Schritte

Andere Module und Apps hängen eigene Schritte über den Hook `steuerbote_setup_steps` in ihrer `hooks.py` an, ein Dict je Schritt:

```python
steuerbote_setup_steps = [
	{
		"key": "balance_sheet_mapping",
		"label": "Balance Sheet Mapping",
		"order": 50,
		"needs": ["vat_return_settings"],
		"run": "steuerbote.steuerbote.doctype.balance_sheet_mapping.setup.run",
	},
]
```

- `key`: eindeutig, Kleinbuchstaben, Ziffern und Unterstriche. `label`: englisch, mit Übersetzung in `translations/de.csv`. `order`: ganze Zahl; die eingebauten Schritte haben 10, 20 und 30. `needs`: die Schlüssel der Schritte, deren Dokument der Schritt braucht; er läuft nach ihnen und nur, wenn sie ihr Dokument angelegt oder gefunden haben. `run`: der Pfad der Funktion.
- `run(context)` bekommt einen `SetupContext` mit `company`, `today`, `chart` (`Detection` mit `chart` und `basis`) und `results`, den Ergebnissen der Schritte vor ihm, und gibt ein `StepResult` zurück: `outcome` (`Outcome.CREATED`, `SKIPPED`, `UNDECIDED`), `notes` (`Note` mit englischer Vorlage, Werten und `open`) und `document` als (DocType, Name). Eine Ausnahme setzt den Schritt auf „Fehlgeschlagen“ und nimmt zurück, was er geschrieben hatte.
- Ein Schritt legt nur an, was fehlt, und lässt ein vorhandenes Dokument, wie es ist, damit ein zweiter Lauf nichts ändert.

`steuerbote/setup/steps.py` prüft die Einträge (`Step.from_hook`) und bringt die Schritte in ihre Reihenfolge (`plan`): jeden nach denen, die er braucht, sonst nach `order` und Schlüssel. Ein Eintrag, der dem nicht folgt, etwa ein unbekannter Schlüssel in `needs` oder Schritte, die einander im Kreis brauchen, hält die Einrichtung mit dem Grund an.

## Quellen

- § 18 Abs. 2 und 2a UStG, https://www.gesetze-im-internet.de/ustg_1980/__18.html, abgerufen am 23.11.2026.
- ERPNext 16 (`version-16`): die Vorlagen `erpnext/accounts/doctype/account/chart_of_accounts/verified/de_kontenplan_SKR03.json` und `de_kontenplan_SKR04.json` und das DocType Company mit `chart_of_accounts`, `create_chart_of_accounts_based_on`, `existing_company`, `tax_id` und `date_of_establishment`.
- DATEV-Kontenrahmen SKR 03 und SKR 04, „Gültig für 2026“, wie in [Kennzahlen und Kontenzuordnung](ustva-kennzahlen.md) zitiert.
