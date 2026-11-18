# Hinweise für Coding-Agenten

Der Einsatz von KI-Werkzeugen und Coding-Agenten ist in diesem Projekt ausdrücklich erlaubt, für Maintainer wie für Mitwirkende. Verantwortlich bleibt immer der Mensch, der den Pull Request stellt und die Änderung versteht. Diese Datei ist der Einstieg. Die Regeln stehen in [CONTRIBUTING.md](CONTRIBUTING.md) und [docs/entwicklung.md](docs/entwicklung.md) und gelten für Menschen und Agenten gleichermaßen.

## Was ein Agent wissen muss

- **Projekt:** Frappe-App für ERPNext, nur die aktuelle Hauptversion (derzeit 16), Python 3.14, Tabs, `ruff`.
- **Struktur:** `steuerbote/ustva` ist der reine Python-Kern ohne Frappe-Import (Tests mit `pytest`). `steuerbote/steuerbote` ist das Frappe-Modul mit DocTypes und Reports. `steuerbote/tests` enthält Frappe-Integrationstests (`bench run-tests`).
- **Sprache:** Code und Kommentare englisch, Fachbegriffe deutsch (Kennzahl, Voranmeldung, Verprobung, Sondervorauszahlung). Dokumentation, Issues und Pull Requests deutsch.
- **Quellen:** Die fachlichen Regeln stehen mit Quelle in [docs/ustva-kennzahlen.md](docs/ustva-kennzahlen.md). Was dort nicht steht, wird nicht aus dem Gedächtnis ergänzt, sondern nachgeschlagen und belegt.

## Leitplanken

1. **Test zuerst.** Erst ein Test, der fehlschlägt, dann die Änderung. Kein Test wird abgeschwächt, übersprungen oder gelöscht, um grün zu werden. Der Kern hat 100 % Abdeckung, und das bleibt so.
2. **Quelle im Code.** Jede fachliche Regel nennt ihre Primärquelle: Gesetz, BMF-Schreiben, Anleitung zum Vordruck, ELSTER- oder ERiC-Dokumentation.
3. **Geld ist `Decimal`.** Nie `float`. Rundung nur über `steuerbote/ustva/rounding.py`.
4. **Keine echten Daten.** Keine Steuernummern, Zertifikate, PINs, Zugangsdaten, IBANs oder Belege in Code, Tests, Fixtures, Logs, Issues oder Commits. Testdaten sind erfunden.
5. **Keine Geheimnisse beim Agenten.** Zertifikat und PIN gibt ein Mensch zur Laufzeit ein. Ein Agent fragt nie danach, liest sie nie aus und speichert sie nie.
6. **Ein Pull Request, ein Thema.** Dokumentation im selben Pull Request. Kleine Schritte.
7. **Nichts Ungeprüftes nach `main`.** Ein Mensch mit Fachkenntnis prüft Steuer-, Buchungs- und ELSTER-Logik vor dem Merge. Die CI muss grün sein.
8. **Keine neuen Abhängigkeiten ohne Grund.** Was dazukommt, wird exakt gepinnt und begründet.
9. **Nichts Fremdes übernehmen.** Andere Projekte dürfen inspirieren. Code wird eigenständig für ERPNext geschrieben.
10. **Prüfen, was sicher prüfbar ist:** `pre-commit run --all-files`, `pytest`, bei Frappe-Änderungen `bench --site <site> run-tests --app steuerbote`.

## Wiederkehrende Aufgaben

- **Neue Kennzahl oder Zuordnung:** Quelle in `docs/ustva-kennzahlen.md` eintragen, Test schreiben, Katalog in `kennzahlen.py` oder Vorgabe in `defaults.py` ergänzen, Dokumentation anpassen.
- **Jahreswechsel:** Das BMF-Schreiben zu den Vordruckmustern des neuen Jahres lesen, den Katalog Zeile für Zeile gegen den Vordruck prüfen, Tests und Quellenangaben aktualisieren.
- **Neuer Kontenrahmen:** Eine Zuordnung nach dem Muster in `defaults.py` anlegen, jede Kontonummer gegen die offizielle Kontenrahmen-Ausgabe prüfen, Tests nach dem Muster von `test_defaults.py` ergänzen.
