# Mitwirken an Steuerbote

Issues und Pull Requests sind willkommen. Steuerbote ist eine Frappe-App für ERPNext, die Steuermeldungen an ELSTER berechnet, prüft und übermittelt. Diese Seite beschreibt, wie ein Beitrag abläuft und welche Regeln gelten. Die Regeln gelten für Menschen und für Coding-Agenten gleichermaßen, siehe [AGENTS.md](AGENTS.md).

## Fehler und Wünsche melden

Bitte ein [Issue über die Vorlagen](https://github.com/encircle360-oss/steuerbote/issues/new/choose) anlegen. Vorher lohnt ein Blick in die [Roadmap](docs/roadmap.md) und die offenen Issues. Fragen und fachlicher Austausch gehen in die [Discussions](https://github.com/encircle360-oss/steuerbote/discussions) oder auf [Matrix](https://matrix.to/#/#oss:encircle360.com).

**Keine echten Steuernummern, Zertifikate, PINs, Zugangsdaten, IBANs oder Belegdaten** in Issues, Screenshots, Logs oder Pull Requests. Beträge und Konten dürfen erfunden sein, solange der Fall nachvollziehbar bleibt. Sicherheitslücken bitte nicht öffentlich melden, sondern wie in [SECURITY.md](SECURITY.md) beschrieben.

## Ein Pull Request

1. **Fork und Branch.** Branches heißen nach dem Thema, etwa `ustva-kz-35-andere-steuersaetze`.
2. **Test zuerst.** Jede Änderung beginnt mit einem Test, der ohne sie fehlschlägt. Kein bestehender Test wird abgeschwächt oder gelöscht, um grün zu werden. Der Rechenkern unter `steuerbote/ustva` hat 100 % Testabdeckung, und das bleibt so.
3. **Quelle nennen.** Jede fachliche Regel (Rundung, Kennzahl, Kontenzuordnung, Frist) braucht eine Primärquelle: Gesetz, BMF-Schreiben, Anleitung zum Vordruck, ELSTER- oder ERiC-Dokumentation. Die Quelle steht im Code oder in `docs/`, nicht nur im Pull Request.
4. **Ein Thema pro Pull Request**, Dokumentation im selben Pull Request. Kleine Schritte sind leichter zu prüfen.
5. **Lokal prüfen:** `pre-commit run --all-files` und `pytest`. Wer Frappe-Teile ändert, lässt zusätzlich `bench --site <site> run-tests --app steuerbote` laufen, siehe [Entwicklung](docs/entwicklung.md).
6. **Pull Request stellen.** Die Vorlage fragt nach Änderung, Quelle und Checkliste. Die CI muss grün sein.
7. **Review.** Steuer-, Buchungs- und ELSTER-Logik merged erst, wenn ein Mensch mit Fachkenntnis sie geprüft hat. Rückfragen im Review sind normal und kein Urteil über den Beitrag.

## Regeln im Code

- **Nur die aktuelle Hauptversion** von Frappe und ERPNext (derzeit 16). Keine Kompatibilitätsschichten für ältere Versionen.
- **Geld ist `Decimal`**, nie `float`. Gerundet wird ausschließlich über `steuerbote/ustva/rounding.py`.
- **Englisch im Code**, deutsch in der Dokumentation. Fachbegriffe ohne gute Übersetzung bleiben deutsch: Kennzahl, Voranmeldung, Verprobung, Sondervorauszahlung, Dauerfristverlängerung.
- **Kommentare erklären das Warum**, nie das Was und nie die Geschichte einer Änderung. Eine bessere Benennung schlägt einen Kommentar.
- **Keine neuen Abhängigkeiten ohne Grund.** Was dazukommt, wird exakt gepinnt und im Pull Request begründet.
- **Kein fremder Code.** Andere Projekte dürfen inspirieren; Steuerbote wird eigenständig für ERPNext geschrieben.
- **Stil:** `ruff` mit der Konfiguration in `pyproject.toml` (Tabs, 110 Zeichen, doppelte Anführungszeichen), wie im Frappe-Ökosystem üblich.

## Commits

Commit-Nachrichten sind englisch, im Imperativ und vervollständigen den Satz „If applied, this commit will …“: `add Kennzahl 35 for other tax rates`, `fix truncation of negative bases`. Keine Ticket-Präfixe, keine Fußzeilen. Eine Nachricht beschreibt, was sich ändert und warum, wenn das Warum nicht offensichtlich ist.

## Umgangston

Wir gehen respektvoll miteinander um, nehmen Kritik an der Sache an und nicht persönlich, und gehen davon aus, dass alle ihr Bestes geben. Wer das nicht einhält, wird von den Maintainern angesprochen und notfalls ausgeschlossen.

## Lizenz der Beiträge

Mit deinem Beitrag stimmst du zu, dass er unter der [AGPL-3.0-or-later](LICENSE) veröffentlicht wird, und bestätigst, dass du das Recht hast, ihn unter dieser Lizenz beizusteuern.
