# Steuerbote

Steuermeldungen aus ERPNext an ELSTER. Zuerst die Umsatzsteuer-Voranmeldung, danach Dauerfristverlängerung, Zusammenfassende Meldung und die Jahresmeldungen (E-Bilanz, Umsatzsteuer-, Körperschaftsteuer- und Gewerbesteuererklärung).

> **Status: in Entwicklung, noch nicht einsatzfähig.** Der Rechenkern der Umsatzsteuer-Voranmeldung steht und ist vollständig getestet. Einstellungen, Oberfläche und die Übermittlung über ERiC folgen, siehe [Roadmap](docs/roadmap.md).

## Was Steuerbote macht

- **Kennzahlen aus dem Hauptbuch.** Die Umsatzsteuer-Voranmeldung wird aus den Buchungen (GL Entry) berechnet, nicht aus Rechnungen. Damit zählen auch Journalbuchungen und importierte Buchungsstapel, etwa aus Trading- oder Abrechnungssystemen.
- **Verprobung je Beleg.** Für jede Bemessungsgrundlage wird die rechnerische Steuer mit der gebuchten Steuer verglichen, Beleg für Beleg. Abweichende Belege halten die Meldung an, ebenso Salden auf beobachteten Konten: Konten, die zur Umsatzsteuer gehören, aber in den Vorgaben noch keine Kennzahl haben.
- **Rundung wie im Vordruck.** Bemessungsgrundlagen in vollen Euro (Cent werden abgeschnitten), Steuerbeträge mit Cent, so wie es die Anleitung zum Vordruck USt 1 A verlangt.
- **Kontenrahmen frei wählbar.** Vorgaben für SKR03 und SKR04 (Ausgabe 2026) liegen bei. Jedes Konto, das DATEV für die Umsatzsteuer kennzeichnet, ist darin zugeordnet, verprobt, beobachtet oder mit Grund bewusst ohne Kennzahl, einschließlich der Kontenbereiche und der Kontonummern aus den SKR-Vorlagen von ERPNext. Die Zuordnung Konto → Kennzahl arbeitet nur mit Kontonummern, deshalb laufen auch andere Kontenrahmen darüber. Eigene Anpassungen je Firma folgen mit den Einstellungen (geplant).
- **Je Firma und Zeitraum** (geplant). Mehrere Firmen in einer ERPNext-Site mit eigenem Kontenrahmen, eigenem Voranmeldungszeitraum (Monat oder Quartal) und eigenem Zertifikat. Der Rechenkern kennt Zeiträume und Fristen schon heute. Die Kennzahlen gelten je Jahrgang des Vordrucks; vorhanden ist der Jahrgang 2026, weitere Jahrgänge kommen als eigene Kataloge dazu, damit Vorjahre meldbar bleiben.
- **Übermittlung über ERiC** (geplant). Validierung gegen die ELSTER-Prüfregeln vor der Abgabe, Übermittlung mit Organisationszertifikat, Übermittlungsprotokoll als PDF am Beleg.
- **Abgabe ohne Hersteller-ID** (geplant). Ausdruck zum Abtippen oder XML-Datei für den Import in Mein ELSTER.

## Voraussetzungen

- Frappe und ERPNext ab Version 16. Unterstützt wird nur die jeweils aktuelle Hauptversion.
- Python 3.14.
- Für die Übermittlung: ERiC (ELSTER Rich Client) der Finanzverwaltung auf Linux x86_64 und ein ELSTER-Organisationszertifikat. ERiC darf nicht weiterverbreitet werden und wird bei der Einrichtung aus dem ELSTER-Entwicklerbereich geladen.

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/encircle360-oss/steuerbote
bench --site <site> install-app steuerbote
```

## Dokumentation

- [Roadmap](docs/roadmap.md): Arbeitspakete und Reihenfolge
- [Umsatzsteuer-Voranmeldung: Kennzahlen und Kontenzuordnung](docs/ustva-kennzahlen.md)
- [Architektur](docs/architektur.md): Rechenkern und Frappe-Schicht, DocTypes, Bericht, Arbeitsbereich und Druckformat
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
