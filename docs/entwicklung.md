# Entwicklung

Diese Seite beschreibt Aufbau, Einrichtung, Tests, Stil und CI. Wie ein Beitrag abläuft, steht in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Aufbau des Repositories

```text
steuerbote/                    Repository
├── steuerbote/                Python-Paket der Frappe-App
│   ├── hooks.py               App-Metadaten, setzt ERPNext voraus
│   ├── ustva/                 Rechenkern der Umsatzsteuer-Voranmeldung, reines Python ohne Frappe-Import
│   │   ├── kennzahlen.py      Katalog der Kennzahlen des Vordrucks USt 1 A je Jahrgang, bisher 2026
│   │   ├── rounding.py        Rundung: Bemessungsgrundlagen in vollen Euro, Steuern in Cent
│   │   ├── mapping.py         Kontenzuordnung: AccountRule, TaxCheck, Mapping
│   │   ├── defaults.py        Vorgaben für SKR03 und SKR04
│   │   ├── calculation.py     calculate(): Buchungszeilen zu Kennzahlen, Summen, Kz 83 und Verprobung
│   │   ├── period.py          Voranmeldungszeiträume, Fristen und ELSTER-Zeitraumcodes
│   │   └── tests/             Unit-Tests des Kerns
│   ├── steuerbote/            Frappe-Modul „Steuerbote“ für DocTypes und Reports, noch leer
│   ├── tests/                 Frappe-Integrationstests
│   └── config/, patches/, public/, templates/
│                              Standardverzeichnisse einer Frappe-App, noch leer
├── docs/                      Dokumentation
├── .github/workflows/         CI: Tests, Linters, Security
├── .github/dependabot.yml     wöchentliche Updates für GitHub Actions und pip
├── pyproject.toml             Paketdaten, Einstellungen für ruff, pytest und coverage
├── requirements-dev.txt       Entwicklungswerkzeuge, exakt gepinnt
└── .pre-commit-config.yaml    Hooks für pre-commit
```

Der Kern unter `steuerbote/ustva` importiert nie Frappe. Deshalb lässt er sich ohne Bench testen. DocTypes und Reports gehören in das Frappe-Modul `steuerbote/steuerbote`.

## Einrichtung

Du brauchst Python 3.14 und eine Bench mit Frappe und ERPNext 16, dazu eine Site, auf der ERPNext installiert ist.

1. Klone deinen Fork und hol die App in die Bench:

   ```bash
   git clone https://github.com/<dein-konto>/steuerbote.git ~/src/steuerbote
   cd $PATH_TO_YOUR_BENCH
   bench get-app --soft-link ~/src/steuerbote
   bench --site <site> install-app steuerbote
   ```

   Mit `--soft-link` verlinkt bench den Checkout nach `apps/steuerbote`. Änderungen im Checkout gelten damit sofort in der Bench. Ohne die Option klont bench den Checkout nach `apps/` (Remote `upstream`), so wie es die CI mit `bench get-app steuerbote "$GITHUB_WORKSPACE"` macht.

2. Installiere die Entwicklungswerkzeuge im Checkout und richte die Git-Hooks ein:

   ```bash
   cd ~/src/steuerbote
   python3.14 -m venv .venv
   . .venv/bin/activate
   pip install -r requirements-dev.txt
   pre-commit install
   ```

   `requirements-dev.txt` bringt coverage, pre-commit, pytest, pytest-cov, ruff und zizmor in festen Versionen. `pre-commit install` richtet die Hooks aus `.pre-commit-config.yaml` ein. Der Hook `no-commit-to-branch` verhindert Commits direkt auf `main`.

## Tests

### Kern ohne Bench

```bash
pytest          # nur steuerbote/ustva
pytest --cov    # mit Abdeckung, wie in der CI
```

`pytest` sammelt nur die Tests unter `steuerbote/ustva` (`testpaths` in `pyproject.toml`) und braucht weder Frappe noch eine Bench. `pytest --cov` misst dazu die Abdeckung des Kerns, Zeilen und Zweige, ohne die Tests selbst. Unter 100 % schlägt der Lauf fehl (`fail_under = 100`), und der Bericht zeigt die fehlenden Zeilen.

### Frappe-Tests

Auf einer Site mit ERPNext und Steuerbote:

```bash
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app steuerbote
```

Die Tests schreiben in die Datenbank der Site. Nimm dafür eine eigene Testsite, nie eine Site mit echten Daten.

Der Frappe-Runner durchsucht die ganze App nach Dateien `test_*.py`. Die Tests des Kerns sind `unittest.TestCase`-Klassen, deshalb laufen sie bei `run-tests` ebenfalls mit. Die Frappe-Tests unter `steuerbote/tests` erben von `IntegrationTestCase` aus `frappe.tests`.

## Testgetrieben arbeiten

1. **Rot:** Schreib zuerst einen Test, der ohne die Änderung fehlschlägt, und sieh ihn fehlschlagen.
2. **Grün:** Schreib die kleinste Änderung, die ihn bestehen lässt.
3. **Aufräumen:** Verbessere Namen und Struktur, während alle Tests grün bleiben.

Dabei gilt:

- Kein bestehender Test wird abgeschwächt oder gelöscht, um grün zu werden. Der Kern behält 100 % Abdeckung.
- Jede fachliche Regel hat eine Primärquelle, im Code oder in `docs/`. So zitiert `rounding.py` die Anleitung zum Vordruck, und `kennzahlen.py` nennt das BMF-Schreiben mit Datum und Geschäftszeichen.
- Testdaten sind erfunden. Keine echten Steuernummern, Zertifikate, PINs, Zugangsdaten, IBANs oder Belege, auch nicht in Fixtures.
- Dateien unter `fixtures/` behalten ihre ursprünglichen Zeilenenden und ihre Kodierung (`.gitattributes`).
- Testnamen beschreiben die Regel, etwa `test_drops_the_cents_towards_zero_for_negative_amounts`.

## Stil

- **ruff** mit der Konfiguration in `pyproject.toml`: Einrückung mit Tabs, Zeilen bis 110 Zeichen, doppelte Anführungszeichen, Python 3.14 als Ziel. `ruff format` formatiert auch Codebeispiele in Docstrings.
- **Regelgruppen:** F (pyflakes), E und W (pycodestyle), I (Reihenfolge der Importe), UP (moderne Syntax), B (bugbear), RUF (eigene Regeln von ruff), S (Sicherheitsprüfungen nach bandit), SIM (Vereinfachungen), C4 (Comprehensions), T20 (kein `print`). Ausgenommen sind E101 und W191 wegen der Tabs und E501, weil die Zeilenlänge der Formatierer setzt. In Tests ist `assert` erlaubt (S101).
- **pre-commit** führt `ruff check --fix` und `ruff format` aus. Außerdem prüft es Leerzeichen am Zeilenende (außer in Markdown), den Zeilenumbruch am Dateiende, Merge-Konflikte, Python-Syntax, JSON, TOML und YAML, große Dateien, vergessene Debug-Anweisungen und private Schlüssel, dazu die Workflows mit zizmor.
- **Englisch im Code**, auch in Kommentaren und Docstrings. Fachbegriffe ohne gute Übersetzung bleiben deutsch: Kennzahl, Voranmeldung, Verprobung, Sondervorauszahlung, Dauerfristverlängerung. Ebenso stehen im Code etwa Bemessungsgrundlage und Voranmeldungszeitraum.
- **Kommentare erklären das Warum**, nie das Was und nie die Geschichte einer Änderung. Eine bessere Benennung schlägt einen Kommentar.
- **Geld ist `Decimal`**, nie `float`. Gerundet wird nur über `steuerbote/ustva/rounding.py`.
- **Werte im Kern sind unveränderlich:** Datenklassen mit `frozen=True, slots=True`, nur lesbare Abbildungen über `MappingProxyType`.
- **Dokumentation auf Deutsch**, kurz und sachlich.

## CI

Alle drei Workflows laufen bei Pull Requests, bei Pushes auf `main` und von Hand, Security zusätzlich jeden Montag um 04:17 UTC. Sie lesen den Inhalt des Repositories nur (`contents: read`), lediglich CodeQL darf zusätzlich Sicherheitsbefunde schreiben. Ausgecheckt wird ohne gespeicherte Zugangsdaten (`persist-credentials: false`). Ein Pull Request wird erst gemergt, wenn alle Jobs grün sind.

| Workflow | Job | Was er tut |
|---|---|---|
| Tests | Core (without bench) | pytest mit Abdeckung auf Python 3.14, unter 100 % rot; legt `coverage.xml` als Artefakt ab. |
| Tests | Frappe site (ERPNext v16) | baut eine Bench mit Frappe und ERPNext `version-16`, MariaDB 11.8 und Redis als Dienste, installiert ERPNext und Steuerbote auf einer Testsite und führt `bench run-tests --app steuerbote` aus. |
| Linters | pre-commit | alle Hooks auf allen Dateien, ohne `no-commit-to-branch`. |
| Linters | Frappe semgrep rules | semgrep mit den Regeln aus `frappe/semgrep-rules` und `r/python.lang.correctness`; jeder Fund macht den Job rot. |
| Security | Secret scan (gitleaks) | durchsucht die ganze Git-Historie nach Geheimnissen; gitleaks wird mit Prüfsumme geladen. |
| Security | Workflow audit (zizmor) | prüft die GitHub-Actions-Workflows auf Sicherheitsprobleme. |
| Security | Dependency audit (pip-audit) | prüft die Pakete aus `requirements-dev.txt` auf bekannte Schwachstellen. |
| Security | CodeQL | statische Analyse des Python-Codes. Läuft erst, wenn das Repository öffentlich ist, weil CodeQL nur für öffentliche Repositories kostenlos ist. |

Bei Tests bricht ein neuer Lauf für denselben Pull Request oder Branch den laufenden ab. Dependabot schlägt jede Woche Updates für die GitHub Actions und die pip-Abhängigkeiten vor (`.github/dependabot.yml`).

## Versionen

- **Frappe und ERPNext:** nur die aktuelle Hauptversion, derzeit 16. `pyproject.toml` verlangt `>=16.0.0,<17.0.0` (`[tool.bench.frappe-dependencies]`), `hooks.py` setzt ERPNext voraus, und die CI baut gegen `version-16`. Frappe und ERPNext installiert bench; sie stehen nicht in den Abhängigkeiten des Pakets. Ältere Hauptversionen werden nicht unterstützt, es gibt keine Kompatibilitätsschichten.
- **Python:** 3.14, in `requires-python`, als `target-version` von ruff und in der CI.
- **Entwicklungswerkzeuge** sind in `requirements-dev.txt` exakt gepinnt, die pre-commit-Hooks über `rev`, semgrep, gitleaks und zizmor in den Workflows. Einige Versionen stehen an mehreren Stellen: ruff in `requirements-dev.txt` und `.pre-commit-config.yaml`, zizmor zusätzlich in `security.yml`. Ein Update zieht alle Stellen gleich.
- **Neue Abhängigkeiten** nur mit Grund, exakt gepinnt und im Pull Request begründet.
- **Dependabot** meldet jede Woche neue Versionen für pip und GitHub Actions.

## Commits

- Commit-Nachrichten sind englisch, im Imperativ und vervollständigen den Satz „If applied, this commit will …“, etwa `add Kennzahl 35 for other tax rates` oder `fix truncation of negative bases`.
- Keine Ticket-Präfixe, keine Fußzeilen (Trailer).
- Die Nachricht sagt, was sich ändert, und warum, wenn das Warum nicht offensichtlich ist.
- Branches heißen nach dem Thema, etwa `ustva-kz-35-andere-steuersaetze`. Auf `main` wird nicht direkt committet.
- Ein Thema pro Pull Request, die Dokumentation im selben Pull Request.
