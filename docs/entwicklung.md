# Entwicklung

Diese Seite beschreibt Aufbau, Einrichtung, Tests, Stil und CI. Wie ein Beitrag abläuft, steht in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Aufbau des Repositories

```text
steuerbote/                    Repository
├── steuerbote/                Python-Paket der Frappe-App
│   ├── hooks.py               App-Metadaten, setzt ERPNext voraus, Eintrag in der App-Übersicht, nennt die Fixtures der App und nimmt die Meldungen vom Löschen der Transaktionen aus
│   ├── permissions.py         wem die App-Übersicht Steuerbote zeigt
│   ├── ustva/                 Rechenkern der Umsatzsteuer-Voranmeldung, reines Python ohne Frappe-Import
│   │   ├── years.py           Jahrestabelle: welche Jahre Steuerbote abgibt und was jedes Jahr braucht
│   │   ├── kennzahlen.py      Katalog der Kennzahlen des Vordrucks USt 1 A je Jahrgang, bisher 2026
│   │   ├── rounding.py        Rundung: Bemessungsgrundlagen in vollen Euro, Steuern in Cent
│   │   ├── mapping.py         Kontenzuordnung: AccountRule, TaxCheck, Mapping
│   │   ├── defaults.py        Vorgaben für SKR03 und SKR04
│   │   ├── calculation.py     calculate(): Buchungszeilen zu Kennzahlen, Summen, Kz 83 und Verprobung
│   │   ├── period.py          Voranmeldungszeiträume, Fristen und ELSTER-Zeitraumcodes
│   │   ├── plausibility.py    Vorperiodenvergleich und Hinweise aus Rechnungen, Hauptbuch und Vergleich
│   │   ├── yearcheck.py       Jahresprüfung: Daten eines Jahres gegen Jahresdokumentation, Schema und Datenartversionmatrix
│   │   ├── documentation.py   liest diese Dateien aus der entpackten ERiC-Dokumentation
│   │   └── tests/             Unit-Tests des Kerns
│   ├── elster/                ELSTER, reines Python ohne Frappe-Import
│   │   ├── steuernummer.py    Steuernummer im 13-stelligen ELSTER-Format
│   │   ├── ustva_xml.py       Voranmeldung als XML: Datei für Mein ELSTER, Nutzdaten für ERiC
│   │   ├── ust1h_xml.py       Vordruck USt 1 H als XML: Nutzdaten für ERiC in beiden Kontexten
│   │   ├── zm_xml.py          Zusammenfassende Meldung als XML: Nutzdaten der Datenart ZMDO für ERiC
│   │   ├── charset.py         Zeichensatz von ELSTER und Ersatz typografischer Zeichen
│   │   ├── envelope.py        ganzer Umschlag Elster mit TransferHeader, nur für die Schematests
│   │   └── tests/             Unit-Tests und Tests gegen die Schemas der ERiC-Dokumentation
│   ├── zm/                    Rechenkern der Zusammenfassenden Meldung, reines Python ohne Frappe-Import
│   │   ├── period.py          Meldezeiträume, ELSTER-Codes und Fristen
│   │   ├── rhythm.py          Abgaberhythmus je Monat samt Schwelle von 50.000 €
│   │   ├── lines.py           Meldezeilen je USt-IdNr. und Art aus den Belegen hinter Kz 41, 42 und 21
│   │   ├── ustid.py           Schreibweise der USt-IdNrn. und welche eine Zeile nicht melden kann
│   │   ├── findings.py        was die Meldung anhält und was jemand ansehen sollte
│   │   ├── reconciliation.py  Abgleich mit Kz 41, 42 und 21 der Voranmeldungen
│   │   ├── comparison.py      Vorperiodenvergleich je USt-IdNr. und Art
│   │   ├── correction.py      Berichtigung: welche Zeilen sie meldet und welchen Zeitraum sie berichtigt
│   │   ├── csv_file.py        CSV-Datei für den Import in Mein ELSTER
│   │   └── tests/             Unit-Tests des Kerns
│   ├── vatid/                 Bestätigung ausländischer USt-IdNrn. beim BZSt, VIES als Ausweichdienst, reines Python ohne Frappe-Import
│   ├── dauerfrist/            Rechenkern von Dauerfristverlängerung und Sondervorauszahlung (USt 1 H), reines Python ohne Frappe-Import
│   ├── deadlines/             Fristen von Voranmeldung, ZM und Sondervorauszahlung mit Status, reines Python ohne Frappe-Import; Bericht „Offene Fristen“, tägliche Erinnerung und Fristerinnerung im Frappe-Modul, siehe Fristen
│   ├── eric/                  ERiC: Datenarten, Einrichtung, ctypes-Anbindung, Worker-Prozess, Simulation; Frappe nur in secrets.py
│   ├── ledger.py              liest das Hauptbuch eines Zeitraums als Buchungszeilen des Kerns
│   ├── invoices.py            liest die Rechnungen eines Zeitraums als Rechnungszeilen für die Hinweise
│   ├── mapping_sync.py        Zeilen der Kontenzuordnung zur Mapping des Kerns, reines Python
│   ├── zm_sources.py          liest für die Zusammenfassende Meldung Hauptbuch, Kunden, Adressen und abgegebene Voranmeldungen
│   ├── dauerfrist_sources.py  liest für die Dauerfristverlängerung die abgegebenen Voranmeldungen eines Jahres und das Gründungsdatum
│   ├── holiday_list.py        liest die Feiertage der Fristen aus der Feiertagsliste des Unternehmens
│   ├── steuerbote/            Frappe-Modul „Steuerbote“, siehe Architektur
│   │   ├── doctype/           Einstellungen, Kontenzuordnung, Umsatzsteuer-Voranmeldung, Zusammenfassende Meldung, Dauerfristverlängerung, USt-IdNr.-Bestätigung und ELSTER-Übermittlung samt Tabellen; elster_transmission/transmission.py übermittelt Voranmeldung, Dauerfristverlängerung und Zusammenfassende Meldung
│   │   ├── report/            Bericht „UStVA Kennzahlen“ mit den Belegen hinter jeder Kennzahl
│   │   ├── workspace/         Arbeitsbereich „Steuern“
│   │   ├── sidebar/           Seitenleiste des Moduls mit kurzen Bezeichnungen
│   │   ├── number_card/       Zahlenkarte „Offene Voranmeldungen“
│   │   └── print_format/      Druckformate „Umsatzsteuer-Voranmeldung“, „Zusammenfassende Meldung“ und „Dauerfristverlängerung“
│   ├── dock/                  Eintrag „Steuern“ in der Leiste von ERPNext
│   ├── fixtures/              Feld „Nicht in der Umsatzsteuer-Voranmeldung“ an der Journalbuchung und Standard-Druckformate der Belege
│   ├── public/                Logo (images/), Symbol der Leiste (icons/) und die Übermittlung, die die Formulare einbinden (js/elster_transmission.js)
│   ├── translations/          deutsche Übersetzungen der Oberfläche (de.csv)
│   ├── tests/                 Frappe-Integrationstests und Hilfen für Testdaten und Übermittlungen, unter e2e/ die Browsertests mit ihren Testdaten
│   ├── patches/               Patches, die bench migrate ausführt (patches.txt)
│   └── config/, templates/    Standardverzeichnisse einer Frappe-App, noch leer
├── docs/                      Dokumentation
│   └── bilder/                Bildschirmfotos der Oberfläche mit Beispieldaten
├── .github/workflows/         CI: Tests, Linters, Security
├── .github/dependabot.yml     wöchentliche Updates für GitHub Actions und pip
├── pyproject.toml             Paketdaten, Einstellungen für ruff, pytest und coverage
├── requirements-dev.txt       Entwicklungswerkzeuge, exakt gepinnt
└── .pre-commit-config.yaml    Hooks für pre-commit
```

Die Kerne unter `steuerbote/ustva`, `steuerbote/zm`, `steuerbote/vatid` und `steuerbote/dauerfrist` importieren nie Frappe. Deshalb lassen sie sich ohne Bench testen. DocTypes und Reports gehören in das Frappe-Modul `steuerbote/steuerbote`. Wie Kern und Frappe-Modul zusammenspielen, beschreibt [Architektur](architektur.md).

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

   `requirements-dev.txt` bringt coverage, lxml, playwright, pre-commit, pytest, pytest-cov, ruff und zizmor in festen Versionen. `pre-commit install` richtet die Hooks aus `.pre-commit-config.yaml` ein. Der Hook `no-commit-to-branch` verhindert Commits direkt auf `main`.

## Tests

### Kern ohne Bench

```bash
pytest          # nur die reinen Module ohne Frappe
pytest --cov    # mit Abdeckung, wie in der CI
```

`pytest` sammelt nur die Tests der reinen Module, etwa unter `steuerbote/ustva` und `steuerbote/elster` (`testpaths` in `pyproject.toml`), und braucht weder Frappe noch eine Bench. `pytest --cov` misst dazu die Abdeckung des Kerns, Zeilen und Zweige, ohne die Tests selbst. Unter 100 % schlägt der Lauf fehl (`fail_under = 100`), und der Bericht zeigt die fehlenden Zeilen.

### Schematests

`steuerbote/elster/tests/test_schema.py` prüft das XML gegen die Schemas der ERiC-Dokumentation: die Datei für Mein ELSTER und die Nutzdaten des Vordrucks USt 1 H gegen `UStVA-2026.xsd`, Nutzdaten und Umschlag gegen `elster11_UStVA_2026_extern.xsd` mit dem ElsterBasisSchema, dazu Reihenfolge, Typen und Längen, die `ustva_xml.py` aus dem Schema übernimmt, und den Vordruck gegen die Beispiele `UStVA_Df_2026.xml` und `UStVA_SoVZ_2026.xml` in Canonical XML 2.0. `test_zm_schema.py` prüft die Nutzdaten der Zusammenfassenden Meldung gegen `zm_000005.xsd` und im Umschlag gegen `elster11_Zm_000005_extern.xsd`, vergleicht sie Byte für Byte mit dem Beispiel `ZMDO_5_send-Auth.xml` und die Werte, die `zm_xml.py` übernimmt, mit Schema und Jahresdokumentation. `steuerbote/eric/tests/test_datenart.py` vergleicht die Beschreibung jeder Datenart in `steuerbote/eric/datenart.py` mit Beispielen, Schemas, Datenartversionmatrix und Jahresdokumentation ZMDO, und `test_header.py` prüft den DatenTeil jeder Datenart im ganzen Umschlag gegen dessen Schema. Die Schemas tragen keine Lizenz, die eine Weitergabe erlaubt, deshalb liegen sie nicht im Repository. Die Tests lesen sie aus der entpackten ERiC-Dokumentation, deren Verzeichnis die Umgebungsvariable `STEUERBOTE_ERIC_DOC_DIR` nennt:

```bash
curl -fLo /tmp/eric-doc.zip https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Dokumentation.zip
echo "bad21c27ecce56d04fc04bccfd2dfa17b9ff2455aa878758100fc73a28492ad5  /tmp/eric-doc.zip" | sha256sum --check
unzip -q /tmp/eric-doc.zip -d /tmp/eric-doc
STEUERBOTE_ERIC_DOC_DIR=/tmp/eric-doc pytest --cov
```

Die Variable nennt das Verzeichnis, in das die Zip-Datei entpackt wurde, oder darin das Verzeichnis `Dokumentation`. Sie gilt ebenso für `bench run-tests`, das die Tests unter `steuerbote/elster` mitnimmt. Ohne die Variable überspringt pytest die Schematests und sagt, warum; in einer CI (Umgebungsvariable `CI`) schlagen sie stattdessen fehl. Die CI lädt die Dokumentation in beiden Testjobs, prüft die SHA-256-Summe und entpackt nur die Schemas und Beispiele der UStVA, das Verzeichnis der ZMDO mit Schema, Beispiel und Jahresdokumentation, die Datenartversionmatrix und das ElsterBasisSchema. Gepinnt ist 44.3.6.0, die produktive Version. ERiC 45.1.5.0 ist eine Beta, ihr Schema für 2026 gleicht dem von 44.3.6.0 bis auf den Kopfkommentar.

### Frappe-Tests

Auf einer Site mit ERPNext und Steuerbote:

```bash
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app steuerbote
```

Die Tests schreiben in die Datenbank der Site. Nimm dafür eine eigene Testsite, nie eine Site mit echten Daten.

Der Frappe-Runner durchsucht die ganze App nach Dateien `test_*.py`. Die Tests des Kerns sind `unittest.TestCase`-Klassen, deshalb laufen sie bei `run-tests` ebenfalls mit. Die Frappe-Tests unter `steuerbote/tests` erben von `IntegrationTestCase` aus `frappe.tests`.

### Browsertests

Die Browsertests unter `steuerbote/tests/e2e` bedienen eine laufende Site mit Playwright und Chromium wie ein Mensch am Bildschirm: die Anmeldung, den Eintrag „Steuern“ in der Leiste von ERPNext und den Arbeitsbereich mit seinen Verknüpfungen, jede Liste der Seitenleiste, neue Belege, die Umsatzsteuer-Voranmeldung (Berechnen, das Menü ELSTER bis zum Dialog für Zertifikat und Passwort, „XML für Mein ELSTER“, Druckvorschau), die Zusammenfassende Meldung (Berechnen, „CSV für Mein ELSTER“), die Dauerfristverlängerung, Einstellungen, Kontenzuordnung mit „Vorgaben laden“ samt der Spalte Steuersatz und ERiC-Einstellungen, die Berichte „UStVA Kennzahlen“ und „Offene Fristen“ und die Sicht eines Benutzers, der nur die Rolle Accounts User hat. Ein Test schlägt fehl, sobald eine seiner Seiten einen JavaScript-Fehler, einen Fehler auf der Konsole oder eine Antwort des Servers mit Status 500 oder mehr sieht; Antworten mit 4xx sind Ablehnungen des Servers, die die Tests an dem messen, was die Oberfläche daraus macht. Ein fehlgeschlagener Test legt Bildschirmfotos seiner Seiten unter `test-results/` ab.

Die Testdaten legt `steuerbote/tests/e2e/seed.py` mit den Hilfen der Frappe-Tests an, alle erfunden: ein Unternehmen mit SKR03-Konten, Einstellungen und der Kontenzuordnung aus „Vorgaben laden“, drei Rechnungen im Oktober 2026 (Inland 19 %, sonstige Leistung an einen Kunden in Österreich mit USt-IdNr., eine Leistung nach § 13b UStG), eine USt-IdNr.-Bestätigung, eine in Mein ELSTER abgegebene Voranmeldung für September, berechnete Voranmeldung und Zusammenfassende Meldung für Oktober, eine Dauerfristverlängerung, ERiC-Einstellungen im Simulationsmodus und den Benutzer `steuerbote-e2e-buchhaltung@example.com` mit der Rolle Accounts User. Ein zweiter Lauf legt nichts doppelt an. Außerdem schließt der Seed den Einrichtungsassistenten ab und stellt die Sprache des Administrators und des Benutzers auf Deutsch. Nimm dafür eine eigene Testsite, nie eine Site mit echten Daten.

Lokal, gegen eine Bench mit einer Testsite:

```bash
# in der Bench
bench --site <site> execute steuerbote.tests.e2e.seed.run
bench build --app frappe   # nur nötig, wenn die Bench mit --skip-assets angelegt wurde
bench use <site>
bench start

# im Checkout, mit den Werkzeugen aus requirements-dev.txt
playwright install chromium
pytest steuerbote/tests/e2e --base-url http://localhost:8000 --admin-password <Passwort des Administrators>
```

`bench start` startet neben dem Webserver auch socket.io, mit dem die Seiten sich verbinden; `bench use` macht die Testsite zur Site von `localhost`. Ohne `--admin-password` melden sich die Tests mit `admin` an, dem Passwort der Testsite in der CI. Das Passwort des Benutzers mit der Rolle Accounts User setzt jeder Lauf neu über den Administrator, der Seed vergibt keines. `--headed` zeigt den Browser, `--output` nennt ein anderes Verzeichnis für die Bildschirmfotos. Der ganze Lauf dauert etwa eine Minute.

Die Testmodule importieren weder pytest noch Playwright: `bench run-tests` importiert jede Datei `test_*.py` der App, in der Umgebung der Bench, die beides nicht hat. Was die Tests brauchen, auch `expect` von Playwright, geben ihnen die Fixtures in `conftest.py`; `desk.py` hält die Schritte auf den Seiten des Desks.

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
| Tests | Core (without bench) | lädt die ERiC-Dokumentation 44.3.6.0 und prüft ihre SHA-256-Summe, dann pytest mit Abdeckung und Schematests auf Python 3.14, unter 100 % rot; legt `coverage.xml` als Artefakt ab. |
| Tests | Frappe site (ERPNext v16) | baut mit `frappe-bench` 5.31.1 eine Bench mit Frappe und ERPNext `version-16`, MariaDB 11.8 und Redis als Dienste, installiert ERPNext und Steuerbote auf einer Testsite, lädt die ERiC-Dokumentation für die Schematests und führt `bench run-tests --app steuerbote` aus. Danach baut er die Assets von Frappe, füllt die Testsite mit dem Seed der Browsertests, startet Webserver und socket.io und lässt die Browsertests mit Chromium laufen; schlägt einer fehl, liegen Bildschirmfotos und die Protokolle des Servers im Artefakt `browser-tests`. |
| Linters | pre-commit | alle Hooks auf allen Dateien, ohne `no-commit-to-branch`. |
| Linters | Frappe semgrep rules | semgrep 1.185.0 mit den Regeln aus `frappe/semgrep-rules` und den Regeln `python/lang/correctness` aus `semgrep/semgrep-rules`, die die Registry als `r/python.lang.correctness` anbietet, beide auf einen Commit gepinnt; jeder Fund macht den Job rot. |
| Security | Secret scan (gitleaks) | durchsucht die ganze Git-Historie nach Geheimnissen; gitleaks wird mit Prüfsumme geladen. |
| Security | Workflow audit (zizmor) | prüft die GitHub-Actions-Workflows auf Sicherheitsprobleme. |
| Security | Dependency audit (pip-audit) | prüft mit pip-audit 2.10.1 die Pakete aus `requirements-dev.txt` auf bekannte Schwachstellen. |
| Security | CodeQL | statische Analyse des Python-Codes. Läuft erst, wenn das Repository öffentlich ist, weil CodeQL nur für öffentliche Repositories kostenlos ist. |

Bei Tests bricht ein neuer Lauf für denselben Pull Request oder Branch den laufenden ab. Dependabot schlägt jede Woche Updates für die GitHub Actions und die pip-Abhängigkeiten vor (`.github/dependabot.yml`).

## Versionen

- **Frappe und ERPNext:** nur die aktuelle Hauptversion, derzeit 16. `pyproject.toml` verlangt `>=16.54.0,<17.0.0` (`[tool.bench.frappe-dependencies]`), denn erst ab Frappe 16.54.0 zählt der Rate Limiter je Benutzer (`user_based`), den `stash_certificate` braucht, `hooks.py` setzt ERPNext voraus, und die CI baut gegen `version-16`. Frappe und ERPNext installiert bench; sie stehen nicht in den Abhängigkeiten des Pakets. Ältere Hauptversionen werden nicht unterstützt, es gibt keine Kompatibilitätsschichten.
- **Python:** 3.14, in `requires-python`, als `target-version` von ruff und in der CI.
- **Entwicklungswerkzeuge** sind in `requirements-dev.txt` exakt gepinnt, die pre-commit-Hooks über `rev`, semgrep, pip-audit, frappe-bench, gitleaks und zizmor in den Workflows. Die Regeln für semgrep kommen wie die Actions auf einen Commit gepinnt aus ihren Repositories (`linters.yml`); Dependabot hebt diese Commits nicht, ein Update ist Handarbeit. `steuerbote/tests/test_workflows.py` prüft, dass jedes `pip install` eine exakte Version nennt und jede Action und jedes andere Repository einen Commit. Einige Versionen stehen an mehreren Stellen: ruff in `requirements-dev.txt` und `.pre-commit-config.yaml`, zizmor zusätzlich in `security.yml`. Ein Update zieht alle Stellen gleich. Playwright lädt mit `playwright install` die Version von Chromium, zu der es gehört.
- **lxml** baut das XML für ELSTER. Frappe 16 bringt es selbst mit, ohne eine Version festzulegen. `pyproject.toml` verlangt deshalb nur `lxml>=6.0,<7`, damit die App neben Frappe kein anderes lxml erzwingt, und `requirements-dev.txt` pinnt die Version, mit der die Tests laufen.
- **ERiC-Dokumentation** für die Schematests und die Jahresprüfung: Adresse und SHA-256-Summe der Zip-Datei stehen in `tests.yml`, die Version zusätzlich in `steuerbote/elster/tests/eric_schema.py`. Zum Jahreswechsel kommt eine Version, die das neue Jahr kennt, siehe [Jahreswechsel](#jahreswechsel).
- **Neue Abhängigkeiten** nur mit Grund, exakt gepinnt und im Pull Request begründet.
- **Dependabot** meldet jede Woche neue Versionen für pip und GitHub Actions.

## Jahreswechsel

Ein neues Jahr ist eine Änderung an Daten, kein Umbau. ELSTER nimmt eine Voranmeldung und den Vordruck USt 1 H nur in der Datenart ihres Jahres an, deshalb hat jedes Jahr seine Daten, je Teil in einer eigenen Tabelle. Welche Jahre es gibt, sagt `YEARS` in [`steuerbote/ustva/years.py`](../steuerbote/ustva/years.py), mit dem BMF-Schreiben der Vordrucke jedes Jahres. Jede andere Tabelle hält genau diese Jahre: [`test_years.py`](../steuerbote/ustva/tests/test_years.py) schlägt fehl, solange einer Tabelle ein Jahr fehlt oder eine ein Jahr zu viel hat.

| Teil | Tabelle | Quelle | Test |
|---|---|---|---|
| Jahr und BMF-Schreiben der Vordrucke | `YEARS` in `steuerbote/ustva/years.py` | BMF-Schreiben „Muster der Vordrucke im Umsatzsteuer-Voranmeldungs- und -Vorauszahlungsverfahren“ | `test_years.py` |
| Kennzahlen des Vordrucks USt 1 A | `CATALOGUES` in `steuerbote/ustva/kennzahlen.py` | Vordruck USt 1 A und Anleitung USt 1 E | `test_kennzahlen.py`, Jahresprüfung |
| Schema `Anmeldungssteuern`: Namensraum, Reihenfolge der Elemente, Kennzahlen ohne Vorzeichen | `SCHEMAS` in `steuerbote/elster/ustva_xml.py` | `UStVA-<Jahr>.xsd` der ERiC-Dokumentation | Jahresprüfung, `test_schema.py` |
| Felder und Regeln des Vordrucks USt 1 H | `LAYOUTS` in `steuerbote/dauerfrist/form.py` | `Jahresdokumentation_UStVA_<Jahr>.ods`, Vordruck USt 1 H | Jahresprüfung, `test_form.py` |
| datenartVersion und Plugin von ERiC | keine: `years.py` bildet `UStVA_<Jahr>` und `checkUStVA_<Jahr>` aus dem Jahr, `datenart.ustva` in `steuerbote/eric/datenart.py` nimmt sie in die Datenart des Jahres | `Datenartversionmatrix.ods` | Jahresprüfung, `test_years.py`, `test_datenart.py`, `test_runtime.py` |
| Zusammenfassende Meldung | keine: Die Datenart ZMDO hat für jedes Jahr die datenartVersion `ZMDO`, das Plugin `checkZMDO` (`ZMDO` in `steuerbote/eric/datenart.py`) und das Schema 000005 (`zm_xml.py`); das Jahr des Meldezeitraums steht in ihren Daten (Feld `jahr`) | `Datenartversionmatrix.ods`, `zm_000005.xsd` | Jahresprüfung, `test_datenart.py`, `test_zm_schema.py` |

### Jahresprüfung

`python -m steuerbote.ustva.yearcheck` vergleicht die Daten eines Jahres mit der entpackten ERiC-Dokumentation, im selben Verzeichnis wie bei `STEUERBOTE_ERIC_DOC_DIR` (siehe [Schematests](#schematests)):

```bash
python -m steuerbote.ustva.yearcheck /tmp/eric-doc 2026
```

Ohne Jahr prüft der Befehl jedes Jahr von `YEARS`. Er liest `Jahresdokumentation_UStVA_<Jahr>.ods` mit den Blättern „Anmeldungssteuern - Felder“ und „Anmeldungssteuern - Regeln“, `UStVA-<Jahr>.xsd` und `Datenartversionmatrix.ods`, alles mit der Standardbibliothek ([`documentation.py`](../steuerbote/ustva/documentation.py)), und vergleicht ([`yearcheck.py`](../steuerbote/ustva/yearcheck.py)):

- den Katalog mit den Feldern des Kontexts `Umsatzsteuervoranmeldung`: welche Kennzahlen es gibt, ihre Art nach dem Formatkennzeichen und ihre Zeile nach der Vordruckzeile; mit den Regeln: die Paare aus Bemessungsgrundlage und Steuer, die `FelderNichtGemeinsamAngegeben` nur zusammen annimmt, und Kz 83 als einzige Kennzahl, die eine Regel verlangt; dazu mit den Elementen des Schemas und deren Typen;
- das Schema von `ustva_xml.py` mit dem XSD: Namensraum, Version, Reihenfolge der Elemente und die Kennzahlen ohne Vorzeichen, die auch die Formatkennzeichen U und % der Jahresdokumentation nennen;
- das Layout des Vordrucks USt 1 H mit Feldern und Regeln seiner beiden Kontexte und mit deren Elementen im Schema;
- datenartVersion und Plugin des Jahres und die der ZMDO mit der Datenartversionmatrix.

Je Abweichung schreibt er eine Zeile, links die Daten von Steuerbote, rechts die Datei und was sie sagt, etwa `catalogue 2026, Kz 66: line 38; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 37`. Für 2026 gibt er mit der ERiC-Dokumentation 44.3.6.0 nichts aus. Er endet mit 0, wenn er nichts ausgibt, mit 1 bei einer Abweichung und mit 2, wenn die Dokumentation eines Jahres fehlt. Hat eine Tabelle das Jahr noch nicht, nennt die erste Zeile diese Tabellen, und der Befehl vergleicht an ihrer Stelle die Daten des neuesten Jahres: Seine Zeilen sind dann genau das, was das neue Jahr ändert. In der CI prüft `DocumentationTest` in [`test_yearcheck.py`](../steuerbote/ustva/tests/test_yearcheck.py) jedes Jahr von `YEARS` auf diese Weise.

### Schritt für Schritt

Mitte November erscheint die Beta des neuen Hauptrelease von ERiC; ihre Dokumentation enthält Jahresdokumentation und Schema des neuen Jahres ([ERiC](eric.md#versionen-und-jahreswechsel)). Das BMF-Schreiben mit den Vordruckmustern folgt im Dezember, für 2026 am 29. Dezember 2025. Die ersten Meldungen des neuen Jahres sind am 10. Februar fällig: die Sondervorauszahlung und, ohne Dauerfristverlängerung, die Voranmeldung für Januar. Jeder Schritt beginnt mit dem Test.

1. **BMF-Schreiben.** Das Schreiben zu den Vordruckmustern des neuen Jahres lesen; es nennt die Änderungen in einem eigenen Abschnitt, und die Anleitungen markieren sie mit „Neu!“. Das Jahr mit Datum, Geschäftszeichen und Adresse des Schreibens in `YEARS` eintragen und die Jahre in `test_files_2026` von `test_years.py` nennen. Ab dann schlagen `PartsTest` fehl, bis jede Tabelle das Jahr hat, und `test_the_data_of_each_year_cite_its_bmf_letter`, bis die Docstrings von `kennzahlen.py` und `form.py` das Schreiben zitieren.
2. **Katalog.** Erst die Tabelle des neuen Vordrucks USt 1 A in `test_kennzahlen.py` nach dem Muster von `FORM_UST_1_A_2026`, dann `_FORM_<Jahr>` in `kennzahlen.py` mit seinem Eintrag in `CATALOGUES`. Der Katalog des Vorjahres bleibt. Was dabei zu vergleichen ist, auch für Rundung, Fälligkeit und die Vorgaben der Kontenrahmen, steht in [Kennzahlen und Kontenzuordnung](ustva-kennzahlen.md#jahreswechsel). Test: `test_kennzahlen.py`.
3. **Jahresdokumentation.** Die Dokumentation des neuen Release laden und entpacken und `python -m steuerbote.ustva.yearcheck <Verzeichnis> <Jahr>` laufen lassen, gern schon, bevor eine Tabelle das Jahr hat. Jede Zeile wird zu einer Änderung im Katalog, im Schema oder im Layout, bis der Befehl nichts mehr ausgibt. Nennt er ein Formatkennzeichen, das `KINDS_BY_FORMAT` nicht kennt, oder eine weitere Kennzahl, die eine Regel verlangt, muss zuerst der Schreiber des XML lernen, sie zu schreiben. Test: Jahresprüfung, in der CI `DocumentationTest`.
4. **XSD.** Den Eintrag des Jahres in `SCHEMAS` von `ustva_xml.py` anlegen: Namensraum (`targetNamespace` von `UStVA-<Jahr>.xsd`), Reihenfolge der `xs:sequence` von `Umsatzsteuervoranmeldung` und die Kennzahlen ohne Vorzeichen. Dann die gepinnte ERiC-Dokumentation auf eine Version heben, die das Jahr kennt: Adresse und SHA-256-Summe in beiden Jobs von `.github/workflows/tests.yml`, die Version in `steuerbote/elster/tests/eric_schema.py`. Mit der Beta-Dokumentation 45.1.5.0, die 2027 schon enthält, laufen alle Tests für 2026 so durch wie mit 44.3.6.0. Test: Jahresprüfung; `test_schema.py` prüft das geschriebene XML bisher gegen das Schema von 2026 und bekommt das neue Jahr dazu.
5. **Plugin.** Nichts zu ändern, solange die Datenartversionmatrix datenartVersion und Plugin nach dem Jahr benennt: `years.py` bildet beide Namen, `datenart.ustva` nimmt sie in die Datenart des Jahres, und die Laufzeit in `steuerbote/eric/runtime.py` liest mit ihnen die Jahre ihrer Plugins und wählt die Laufzeit nach dem Plugin der Datenart. Im Betrieb die Beta zum Prüfen und Testsenden und die freigegebene Version zum Senden einrichten, siehe [ERiC](eric.md#versionen-und-jahreswechsel). Test: Jahresprüfung, `test_years.py`, `test_datenart.py`, `test_runtime.py`.
6. **USt 1 H.** `_LAYOUT_<Jahr>` in `form.py` aus der Jahresdokumentation anlegen: die Felder jedes Kontexts in der Reihenfolge des Schemas mit regulärem Ausdruck, Formatkennzeichen, Längen und Vordruckzeile, die Regeln beider Kontexte und die Bezeichnungen des Vordrucks USt 1 H, etwa „Davon 1/11 = Sondervorauszahlung <Jahr>“. `LAYOUTS` nimmt es unter seinem Jahr auf. Benennt die Jahresdokumentation eine Regel um, auf die `Ust1H` sich stützt (`Svz_Kz29_ohne_Kz10`, `Svz_Kz38_Pflichtfeld`, `Kz500_Begr_Gemeinsam`, `Kz26_Hinweis`, `Kz500_Hinweis`), braucht `form.py` den neuen Namen. Test: Jahresprüfung, `test_form.py`, `steuerbote/dauerfrist/tests/test_docs.py` mit der Tabelle in [Dauerfristverlängerung](dauerfristverlaengerung.md#vordruck-ust-1-h-in-elster).
7. **Tests.** `pytest --cov` mit der neuen Dokumentation, 100 % Abdeckung bleiben, und `bench run-tests`. Mit einer Kopie von 2026 als 2027 schlagen unter `pytest` nur `test_files_2026` und `test_a_year_without_its_form_is_refused_by_the_core` in `steuerbote/steuerbote/doctype/vat_return_extension/test_bridge.py` fehl. Dieser Test und die Frappe-Tests in `test_vat_return_extension.py` nehmen 2027 als Jahr, dessen Vordruck USt 1 H Steuerbote nicht kennt, und gehen auf das nächste Jahr. Tests, die den neuesten Katalog nehmen (`KENNZAHLEN`, eine `Mapping` ohne Jahr, die Vorgaben), laufen danach gegen das neue Jahr und zeigen, was es an Berechnung und Vorgaben ändert.
8. **Zeiträume: Kz 39 und Dauerfristverlängerung.** Mit der neuen Anleitung prüfen, ob die Sondervorauszahlung weiter in Kz 39 der letzten Voranmeldung des Jahres steht (`SONDERVORAUSZAHLUNG_KENNZAHL`, `bridge.sondervorauszahlung_values`, `crediting_period` in `steuerbote/dauerfrist/period.py`) und ob die Fristen bleiben: der 10. Tag nach dem Zeitraum in `steuerbote/ustva/period.py`, der 10. Februar für die Sondervorauszahlung in `steuerbote/dauerfrist/period.py`. Im Betrieb braucht jedes Jahr mit Dauerfristverlängerung eine Zeile in „Dauerfristverlängerung je Jahr“ der Einstellungen: Bei monatlicher Abgabe schreibt sie der Beleg „Dauerfristverlängerung“ des neuen Jahres mit dem Vermerk seiner Abgabe, bei vierteljährlicher Abgabe mit fortgeltender Verlängerung, für die es keinen Beleg gibt, legt sie jemand von Hand an. Ein Wechsel des Voranmeldungszeitraums kommt als neue Regel ab Januar dazu. Test: `steuerbote/dauerfrist/tests/test_period.py`, `steuerbote/ustva/tests/test_period.py`, `vat_return/test_bridge.py`.
9. **Release.** Die Dokumentation nachziehen ([Kennzahlen](ustva-kennzahlen.md), [Dauerfristverlängerung](dauerfristverlaengerung.md), [ERiC](eric.md), [Roadmap](roadmap.md)), dann die Version in `steuerbote/__init__.py` heben und veröffentlichen, bevor die ersten Meldungen des Jahres fällig sind. Betreiber spielen die neue Version ein und richten die freigegebene ERiC-Version mit dem Plugin des Jahres ein.

## Commits

- Commit-Nachrichten sind englisch, im Imperativ und vervollständigen den Satz „If applied, this commit will …“, etwa `add Kennzahl 35 for other tax rates` oder `fix truncation of negative bases`.
- Keine Ticket-Präfixe, keine Fußzeilen (Trailer).
- Die Nachricht sagt, was sich ändert, und warum, wenn das Warum nicht offensichtlich ist.
- Branches heißen nach dem Thema, etwa `ustva-kz-35-andere-steuersaetze`. Auf `main` wird nicht direkt committet.
- Ein Thema pro Pull Request, die Dokumentation im selben Pull Request.
