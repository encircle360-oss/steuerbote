# Sicherheit

## Unterstützte Versionen

Sicherheitskorrekturen gibt es für den Branch `main` und die jeweils neueste Veröffentlichung. Ältere Stände werden nicht nachgepflegt.

## Sicherheitslücke melden

Bitte **nicht** als öffentliches Issue. Sende eine Beschreibung an **oss@encircle360.com** oder, sobald das Repository öffentlich ist, über die private Meldefunktion von GitHub („Report a vulnerability“ unter *Security*).

Hilfreich sind: betroffene Version, Schritte zum Nachstellen, mögliche Auswirkungen und, wenn vorhanden, ein Vorschlag zur Behebung. Keine echten Steuerdaten, Zertifikate, PINs oder Zugangsdaten mitschicken.

Wir bestätigen den Eingang so schnell wie möglich, in der Regel innerhalb weniger Werktage, und stimmen die Veröffentlichung einer Korrektur mit dir ab.

## Was Steuerbote beim Umgang mit Geheimnissen zusichert

- Zertifikat und PIN für die ELSTER-Übermittlung werden zur Laufzeit abgefragt und nicht gespeichert, nicht protokolliert und nicht an Dritte weitergegeben.
- Steuerbote spricht nur mit den ELSTER-Servern der Finanzverwaltung (über ERiC) und mit der eigenen ERPNext-Instanz.
- Abhängigkeiten sind exakt gepinnt; Dependabot, `pip-audit`, Geheimnis-Scans, `zizmor` und die Frappe-`semgrep`-Regeln laufen in der CI.

Lücken in ERiC oder ELSTER selbst meldest du bitte direkt an die Finanzverwaltung über [elster.de](https://www.elster.de).
