# <img src="steuerbote/public/images/steuerbote-logo.svg" alt="" width="32" height="32"> Steuerbote

Steuermeldungen aus ERPNext an ELSTER. Zuerst die Umsatzsteuer-Voranmeldung, danach Dauerfristverlängerung, Zusammenfassende Meldung und die Jahresmeldungen (E-Bilanz, Umsatzsteuer-, Körperschaftsteuer- und Gewerbesteuererklärung).

> **Status: in Entwicklung, noch nicht einsatzfähig.** Rechenkern, Einstellungen, Kontenzuordnung, Meldung, Bericht, Druckformat und die XML-Datei für Mein ELSTER sind da, ebenso die Anbindung an ERiC. Die Zusammenfassende Meldung lässt sich berechnen, ihre USt-IdNrn. beim BZSt bestätigen und als CSV-Datei in Mein ELSTER abgeben. Die Dauerfristverlängerung berechnet die Sondervorauszahlung aus den abgegebenen Voranmeldungen des Vorjahres und übermittelt den Vordruck USt 1 H über ERiC; ohne Hersteller-ID trägt man ihn in Mein ELSTER von Hand ein. Ohne eigene Hersteller-ID läuft die Übermittlung nur als Simulation; die echte Übermittlung folgt mit der Hersteller-ID, siehe [Roadmap](docs/roadmap.md).

## Was Steuerbote macht

- **Kennzahlen aus dem Hauptbuch.** Die Umsatzsteuer-Voranmeldung wird aus den Buchungen (GL Entry) berechnet, nicht aus Rechnungen. Damit zählen auch Journalbuchungen und importierte Buchungsstapel, etwa aus Trading- oder Abrechnungssystemen.
- **Verprobung je Beleg.** Für jede Bemessungsgrundlage wird die rechnerische Steuer mit der gebuchten Steuer verglichen, Beleg für Beleg. Abweichende Belege halten die Meldung an, ebenso Salden auf beobachteten Konten: Konten, die zur Umsatzsteuer gehören, aber in den Vorgaben noch keine Kennzahl haben.
- **Vorperiodenvergleich und Plausibilitätshinweise.** Jede Kennzahl steht neben Vorperiode und Vorjahr, und auffällige Änderungen, EU-Rechnungen ohne USt-IdNr., Rechnungen ohne passende Steuer und Rechnungen, die nicht zum Hauptbuch passen, bekommen einen Hinweis, der die Meldung nie anhält.
- **Rundung wie im Vordruck.** Bemessungsgrundlagen in vollen Euro (Cent werden abgeschnitten), Steuerbeträge mit Cent, so wie es die Anleitung zum Vordruck USt 1 A verlangt.
- **Kontenrahmen frei wählbar.** Vorgaben für SKR03 und SKR04 (Ausgabe 2026) liegen bei. Jedes Konto, das DATEV für die Umsatzsteuer kennzeichnet, ist darin zugeordnet, verprobt, beobachtet oder mit Grund bewusst ohne Kennzahl, einschließlich der Kontenbereiche und der Kontonummern aus den SKR-Vorlagen von ERPNext. Die Zuordnung Konto → Kennzahl arbeitet nur mit Kontonummern, deshalb laufen auch andere Kontenrahmen darüber. Jede Firma hat ihre eigene Kontenzuordnung, vorbelegt aus den Vorgaben.
- **Je Firma und Zeitraum.** Mehrere Firmen in einer ERPNext-Site mit eigenem Kontenrahmen, eigenem Voranmeldungszeitraum (Monat oder Quartal) und eigenem Zertifikat, das bei jeder Übermittlung eingegeben und nur für den laufenden Vorgang verschlüsselt zwischengespeichert (15 Minuten), nie dauerhaft wird. Die Kennzahlen gelten je Jahrgang des Vordrucks; vorhanden ist der Jahrgang 2026, weitere Jahrgänge kommen als eigene Kataloge dazu, damit Vorjahre meldbar bleiben.
- **Übermittlung über ERiC** (Simulation; echte Übermittlung mit Hersteller-ID). Prüfen gegen die ELSTER-Prüfregeln vor der Abgabe, Testsenden und Senden mit Organisationszertifikat, Übermittlungsprotokoll als PDF an der ELSTER-Übermittlung des Belegs, siehe [Übermittlung an ELSTER](docs/uebermittlung.md).
- **Abgabe ohne Hersteller-ID.** Die Voranmeldung als XML-Datei für den Import in Mein ELSTER, mit nachgerechneter Kz 83 und dem Zeichensatz von ELSTER; geprüft und abgesendet wird sie in Mein ELSTER, siehe [Abgabe über Mein ELSTER](docs/abgabe-mein-elster.md).
- **Zusammenfassende Meldung.** Meldezeilen je USt-IdNr. und Art aus den Belegen hinter Kz 41, 42 und 21, im Abgaberhythmus aus den Einstellungen samt Schwelle von 50.000 € und abgeglichen mit den abgegebenen Voranmeldungen. Jede USt-IdNr. lässt sich beim Bundeszentralamt für Steuern (BZSt) bestätigen, VIES antwortet, wenn das BZSt nicht kann. Jede Abfrage bleibt als Nachweis gespeichert, und eine ungültige oder unbestätigte Nummer hält die Meldung an, bis eine Korrektur mit Begründung sie freigibt. Abgegeben wird über eine CSV-Datei für den Import in Mein ELSTER, siehe [Zusammenfassende Meldung](docs/zm.md).
- **Dauerfristverlängerung und Sondervorauszahlung.** Der Beleg „Dauerfristverlängerung“ hält den Vordruck USt 1 H eines Unternehmens für ein Jahr: den Antrag und bei monatlicher Abgabe die Anmeldung der Sondervorauszahlung. „Berechnen“ bildet aus den abgegebenen Voranmeldungen des Vorjahres die Grundlage und ein Elftel davon als Sondervorauszahlung (Kz 38), mit Fälligkeit; eine Grundlage von Hand mit Begründung ersetzt sie, etwa nach einer Gründung im laufenden Jahr. Den Vordruck schreibt Steuerbote als XML und übermittelt ihn mit „Prüfen“, „Testsenden“ und „Senden“ über ERiC wie die Voranmeldung; ohne Hersteller-ID trägt man ihn in Mein ELSTER von Hand ein, mit dem Druckformat als Vorlage, und vermerkt die Abgabe mit „In Mein ELSTER eingetragen“ oder „Als außerhalb abgegeben vermerken“. Die Abgabe schreibt Kz 38 in die Einstellungen, aus denen die letzte Voranmeldung des Jahres die Sondervorauszahlung in Kz 39 abzieht, siehe [Dauerfristverlängerung](docs/dauerfristverlaengerung.md).

## Einblick

Die Bilder zeigen Steuerbote 0.2.0 in einer Testumgebung mit ERPNext 16. Firma, Anschrift, Steuernummern, USt-IdNrn., Belegnummern und Geschäftspartner sind Beispielwerte. Ein Klick auf ein Bild öffnet es in voller Größe.

<table>
  <tr>
    <td align="center" valign="top">
      <a href="docs/bilder/workspace-steuern.png"><img src="docs/bilder/workspace-steuern.png" width="280" alt="ERPNext mit „Steuern“ in der Leiste links und dem Arbeitsbereich Steuern mit Voranmeldungen, Dauerfristanträgen, Zusammenfassenden Meldungen, USt-IdNr.-Prüfungen und Einrichtung"></a><br>
      Arbeitsbereich Steuern
    </td>
    <td align="center" valign="top">
      <a href="docs/bilder/voranmeldung.png"><img src="docs/bilder/voranmeldung.png" width="280" alt="Umsatzsteuer-Voranmeldung mit Hinweisen zu Rechnungen und Vorperiode und dem Vorperiodenvergleich der Kennzahlen"></a><br>
      Voranmeldung mit Hinweisen und Vorperiodenvergleich
    </td>
  </tr>
  <tr>
    <td align="center" valign="top">
      <a href="docs/bilder/bericht-kennzahlen.png"><img src="docs/bilder/bericht-kennzahlen.png" width="280" alt="Bericht UStVA Kennzahlen mit den Belegen hinter jeder Kennzahl, eine stornierte Eingangsrechnung darunter"></a><br>
      Bericht mit den Belegen je Kennzahl
    </td>
    <td align="center" valign="top">
      <a href="docs/bilder/zusammenfassende-meldung.png"><img src="docs/bilder/zusammenfassende-meldung.png" width="280" alt="Zusammenfassende Meldung mit Meldezeile, Summen und Befunden; die USt-IdNr. der Zeile ist laut Bestätigungsabfrage ungültig und hält die Meldung an"></a><br>
      Zusammenfassende Meldung mit Befunden
    </td>
  </tr>
  <tr>
    <td align="center" valign="top">
      <a href="docs/bilder/ust-idnr-bestaetigung.png"><img src="docs/bilder/ust-idnr-bestaetigung.png" width="280" alt="USt-IdNr.-Bestätigung mit angefragter und anfragender USt-IdNr., Dienst, Ergebnis und Zeitpunkt der Abfrage"></a><br>
      USt-IdNr.-Bestätigung als Nachweis
    </td>
    <td align="center" valign="top">
      <a href="docs/bilder/dauerfristverlaengerung.png"><img src="docs/bilder/dauerfristverlaengerung.png" width="280" alt="Dauerfristverlängerung für 2027; Berechnen meldet, dass keine Voranmeldung des Vorjahres abgegeben ist und die Grundlage von Hand einzutragen ist"></a><br>
      Dauerfristverlängerung
    </td>
  </tr>
</table>

## Voraussetzungen

- Frappe und ERPNext ab Version 16. Unterstützt wird nur die jeweils aktuelle Hauptversion.
- Python 3.14.
- Für die Übermittlung: ERiC (ELSTER Rich Client) der Finanzverwaltung auf Linux x86_64 und ein ELSTER-Organisationszertifikat. ERiC darf ein Softwarehersteller nur als Teil seines eigenen Produkts weitergeben, nicht weiterlizenzieren; Steuerbote liefert es deshalb nicht mit, jeder Betreiber lädt es selbst aus dem ELSTER-Entwicklerbereich und richtet es ein, siehe [ERiC](docs/eric.md).

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/encircle360-oss/steuerbote
bench --site <site> install-app steuerbote
```

### Als Teil von erpnext_germanized

[erpnext_germanized](https://github.com/encircle360-oss/erpnext_germanized) ist ein fertiges Container-Image mit ERPNext 16 und den gängigen deutschen Apps, versioniert in der GitHub Container Registry. Steuerbote ist darin bereits enthalten; wer ERPNext neu aufsetzt oder im Container betreibt, braucht die Schritte oben nicht.

### Wo finde ich Steuerbote?

In der Leiste links, bei den Bereichen von ERPNext wie Rechnungswesen und Vertrieb, steht „Steuern“. Der Eintrag öffnet den Arbeitsbereich „Steuern“ mit den Voranmeldungen, den Dauerfristverlängerungen, den Zusammenfassenden Meldungen, dem Bericht „UStVA Kennzahlen“ und den Einstellungen. Ihn sehen Benutzer mit einer der Rollen Accounts User, Accounts Manager oder System Manager.

- Wer die Leiste für alle oder für sich angeordnet hat, bekommt „Steuern“ nicht von selbst dazu, sondern nimmt den Eintrag im Benutzermenü über „Dock verwalten“ auf.
- In der App-Übersicht steht Steuerbote nicht als eigene Kachel, weil es sich in die Leiste von ERPNext einhängt. Als Standard-App eines Benutzers lässt es sich trotzdem wählen. Mehr dazu in [Architektur](docs/architektur.md#platz-im-desk).

## Dokumentation

- [Roadmap](docs/roadmap.md): Arbeitspakete und Reihenfolge
- [Umsatzsteuer-Voranmeldung: Kennzahlen und Kontenzuordnung](docs/ustva-kennzahlen.md)
- [Abgabe über Mein ELSTER](docs/abgabe-mein-elster.md): XML-Datei erzeugen und in Mein ELSTER importieren
- [Zusammenfassende Meldung](docs/zm.md): Meldezeiträume, Abgaberhythmus, Meldezeilen, Abgleich mit der Voranmeldung, Berichtigung, CSV-Datei für Mein ELSTER und der Beleg in ERPNext
- [Prüfung ausländischer USt-IdNrn.](docs/ust-idnr-pruefung.md): Bestätigung beim BZSt, VIES als Ausweichdienst und die gespeicherten Abfragen
- [Dauerfristverlängerung und Sondervorauszahlung](docs/dauerfristverlaengerung.md): Regeln, Fristen, Vordruck USt 1 H mit XML und Übermittlung über ERiC, der Beleg in ERPNext und der Eintrag in Mein ELSTER
- [Architektur](docs/architektur.md): Rechenkern und Frappe-Schicht, DocTypes, Bericht, Arbeitsbereich, Platz im Desk und Druckformat
- [Übermittlung an ELSTER](docs/uebermittlung.md): Prüfen, Testsenden, Senden, Simulationsmodus, ERiC-Einstellungen und Übermittlungsprotokoll
- [Entwicklung](docs/entwicklung.md): Einrichtung, Tests, Stil
- [Mitwirken](CONTRIBUTING.md), [Hinweise für Coding-Agenten](AGENTS.md), [Sicherheit](SECURITY.md)

## Mitwirken und Community

### Beiträge sind willkommen

Steuerbote lebt davon, dass Menschen mit unterschiedlichen Kontenrahmen, Branchen und Steuerfällen mitmachen. Du kannst

- **Maintainer werden**, für einen Bereich (etwa einen Kontenrahmen oder eine Meldung) oder das ganze Projekt,
- **Pull Requests** für Fehlerbehebungen, Funktionen und Dokumentation stellen,
- **testen**, besonders mit anderen Kontenrahmen und Steuerfällen als unseren,
- **Dokumentation und Beispiele** verbessern,
- **Fehler melden** oder Funktionen vorschlagen.

Jeder Beitrag zählt. Du musst kein Steuerprofi sein, wir helfen beim Einstieg.

### So geht es

1. Repository forken und einen Branch anlegen
2. Änderung samt Tests schreiben (Test zuerst, siehe [Mitwirken](CONTRIBUTING.md))
3. Lokal prüfen: `pre-commit run --all-files` und `pytest`
4. Pull Request mit kurzer Beschreibung und Quelle der fachlichen Regel stellen
5. Review gemeinsam durchgehen, bis es passt

### Maintainer werden

Wer dauerhaft Verantwortung übernehmen möchte, zeigt das am einfachsten durch Pull Requests und Hilfe in Issues und Discussions und schreibt dann an **oss@encircle360.com**. Ein Bereich reicht, es muss nicht das ganze Projekt sein.

## Support und professionelle Dienstleistungen

### Community-Support

- **Matrix:** [#oss:encircle360.com](https://matrix.to/#/#oss:encircle360.com) für den direkten Austausch mit Maintainern und Nutzern
- **Issues:** [Fehler und Wünsche zu Steuerbote](https://github.com/encircle360-oss/steuerbote/issues)
- **Discussions:** [Fragen und fachlicher Austausch](https://github.com/encircle360-oss/steuerbote/discussions)
- **Fehler in ERPNext oder Frappe selbst** bitte beim jeweiligen Projekt melden: [frappe/erpnext](https://github.com/frappe/erpnext/issues), [frappe/frappe](https://github.com/frappe/frappe/issues)

### Professioneller Support

Für Einführung, Anpassung an eigene Kontenrahmen, Betrieb, Schulung oder die Begleitung der Einrichtung zusammen mit deiner Steuerberatung: **hello@encircle360.com**

## Haftungsausschluss

Steuerbote wird „wie besehen“ („AS IS“) und ohne jede Gewährleistung bereitgestellt, weder ausdrücklich noch stillschweigend, einschließlich, aber nicht beschränkt auf die Gewährleistung der Marktgängigkeit, der Eignung für einen bestimmten Zweck und der Nichtverletzung von Rechten Dritter.

Steuerbote ist Software, keine Steuerberatung. Mit der Nutzung erkennst du an:

- Du nutzt Steuerbote auf eigenes Risiko. Für jede Steueranmeldung bleibst du selbst verantwortlich, für ihre Richtigkeit, Vollständigkeit und fristgerechte Abgabe.
- Berechnungen, Kontenzuordnungen, Validierungen und Übermittlungen können Fehler enthalten, auch wenn alle Prüfungen grün sind. Prüfe jede Meldung vor der Abgabe und lass die Einrichtung von deiner Steuerberatung bestätigen.
- Gesetze, Vordrucke und ELSTER-Schnittstellen ändern sich. Steuerbote kann dem hinterherhinken.
- Die Maintainer, die encircle360 GmbH und alle Mitwirkenden haften nicht für Schäden oder Verluste jeder Art, die aus der Nutzung oder der Unmöglichkeit der Nutzung entstehen, insbesondere nicht für Steuernachzahlungen, Zinsen, Verspätungs- oder Säumniszuschläge, Bußgelder, verlorene Vorsteuer oder die Kosten einer Nachbearbeitung. Das gilt, soweit ein Haftungsausschluss gesetzlich zulässig ist.
- Steuerbote ist kein Angebot der Finanzverwaltung. ELSTER und ERiC sind Verfahren und Software der Steuerverwaltungen der Länder und des Bundes, Frappe und ERPNext Projekte der Frappe Technologies Pvt. Ltd. Steuerbote steht mit keinem davon in Verbindung.

Für den Einsatz mit zugesichertem Support und Reaktionszeiten sprich uns an: **hello@encircle360.com**

## Lizenz

Steuerbote steht unter der [GNU Affero General Public License v3.0 oder später](LICENSE) (AGPL-3.0-or-later). Sie ist mit der GPL-3.0 von ERPNext kompatibel. ERiC ist nicht Teil dieses Repositories und unterliegt den Nutzungsbedingungen der Finanzverwaltung.

## Maintainer

Steuerbote wird von der **[encircle360 GmbH](https://encircle360.com)** entwickelt und gepflegt.

## Credits und Mitwirkende

Danke an alle Mitwirkenden, Partner und die Open-Source-Community, insbesondere an das [Frappe/ERPNext-Projekt](https://github.com/frappe/erpnext), auf dem Steuerbote aufsetzt. Alle Mitwirkenden stehen in der [Contributors-Liste](https://github.com/encircle360-oss/steuerbote/graphs/contributors).
