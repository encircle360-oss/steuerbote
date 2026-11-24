# Sicherheit

## Unterstützte Versionen

Sicherheitskorrekturen gibt es für den Branch `main` und die jeweils neueste Veröffentlichung. Ältere Stände werden nicht nachgepflegt.

## Sicherheitslücke melden

Bitte **nicht** als öffentliches Issue. Melde sie über die private Meldefunktion von GitHub: [„Report a vulnerability“](https://github.com/encircle360-oss/steuerbote/security/advisories/new) unter *Security*. Die Meldung sehen nur du und die Maintainer des Repositorys. Ohne GitHub-Konto sende eine Beschreibung an **oss@encircle360.com**.

Hilfreich sind: betroffene Version, Schritte zum Nachstellen, mögliche Auswirkungen und, wenn vorhanden, ein Vorschlag zur Behebung. Keine echten Steuerdaten, Zertifikate, PINs oder Zugangsdaten mitschicken.

Wir bestätigen den Eingang so schnell wie möglich, in der Regel innerhalb weniger Werktage, und stimmen die Veröffentlichung einer Korrektur mit dir ab.

## Was Steuerbote beim Umgang mit Geheimnissen zusichert

- Zertifikat und PIN für die ELSTER-Übermittlung werden zur Laufzeit abgefragt und nicht gespeichert, nicht protokolliert und nicht an Dritte weitergegeben.
- Steuerbote spricht nur mit den ELSTER-Servern der Finanzverwaltung (über ERiC), mit dem Bundeszentralamt für Steuern und, wenn es nicht antworten kann, mit VIES der EU-Kommission, um USt-IdNrn. zu bestätigen, mit `www.elster.de` und `download.elster.de`, von denen die wöchentliche Prüfung der ERiC-Versionen ohne Zugangsdaten die Mindestversionsliste und die Versionsinformationen lädt, und mit der eigenen ERPNext-Instanz.
- Abhängigkeiten, die Werkzeuge der CI und deren Regeln sind exakt gepinnt; Dependabot, `pip-audit`, Geheimnis-Scans, `zizmor`, die Frappe-`semgrep`-Regeln und CodeQL laufen in der CI.

Lücken in ERiC oder ELSTER selbst meldest du bitte direkt an die Finanzverwaltung über [elster.de](https://www.elster.de).
