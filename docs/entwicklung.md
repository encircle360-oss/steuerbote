# Entwicklung

Diese Seite beschreibt Aufbau, Einrichtung, Tests, Stil und CI. Wie ein Beitrag abläuft, steht in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Aufbau des Repositories

```text
steuerbote/                    Repository
├── steuerbote/                Python-Paket der Frappe-App
│   ├── hooks.py               App-Metadaten, setzt ERPNext voraus, Eintrag in der App-Übersicht, nennt die Fixtures der App, nimmt die Meldungen, die Belege der Jahresmeldungen und ihre Einstellungen vom Löschen der Transaktionen aus und hängt die Schritte von Kontenzuordnung Ertragsteuern und Bilanzzuordnung in „Steuerbote einrichten“ ein
│   ├── permissions.py         wem die App-Übersicht Steuerbote zeigt
│   ├── ustva/                 Rechenkern der Umsatzsteuer-Voranmeldung, reines Python ohne Frappe-Import
│   │   ├── years.py           Jahrestabelle: welche Jahre Steuerbote abgibt und was jedes Jahr braucht
│   │   ├── kennzahlen.py      Katalog der Kennzahlen des Vordrucks USt 1 A je Jahrgang, 2026 und vorläufig 2027
│   │   ├── rounding.py        Rundung: Bemessungsgrundlagen in vollen Euro, Steuern in Cent, dazu die Rundungen der Jahresmeldungen
│   │   ├── mapping.py         Kontenzuordnung: AccountRule, TaxCheck, Mapping
│   │   ├── defaults.py        Vorgaben für SKR03 und SKR04
│   │   ├── calculation.py     calculate(): Buchungszeilen zu Kennzahlen, Summen, Kz 83 und Verprobung
│   │   ├── period.py          Voranmeldungszeiträume, Fristen und ELSTER-Zeitraumcodes
│   │   ├── plausibility.py    Vorperiodenvergleich und Hinweise aus Rechnungen, Hauptbuch und Vergleich
│   │   ├── carried.py         Übergang eines Saldos, den ein Konto in eine spätere Voranmeldung trägt
│   │   ├── tax_templates.py   Konten der Steuervorlagen ohne Platz in der Kontenzuordnung und ihre Hinweise
│   │   ├── registers.py       Abgleich mit den Berichten Sales Register und Purchase Register
│   │   ├── yearcheck.py       Jahresprüfung: Daten eines Jahres gegen Jahresdokumentation, Schema und Datenartversionmatrix
│   │   ├── documentation.py   liest diese Dateien aus der entpackten ERiC-Dokumentation
│   │   └── tests/             Unit-Tests des Kerns
│   ├── elster/                ELSTER, reines Python ohne Frappe-Import
│   │   ├── steuernummer.py    Steuernummer im 13-stelligen ELSTER-Format
│   │   ├── ustva_xml.py       Voranmeldung als XML: Datei für Mein ELSTER, Nutzdaten für ERiC
│   │   ├── ust1h_xml.py       Vordruck USt 1 H als XML: Nutzdaten für ERiC in beiden Kontexten
│   │   ├── zm_xml.py          Zusammenfassende Meldung als XML: Nutzdaten der Datenart ZMDO für ERiC
│   │   ├── ust2a_xml.py       Umsatzsteuererklärung als XML: Nutzdaten E50 mit USt2A und Vorsatz für ERiC
│   │   ├── kst_xml.py         Körperschaftsteuererklärung als XML: Nutzdaten E30 für ERiC
│   │   ├── gewst_xml.py       Gewerbesteuererklärung als XML: Nutzdaten E20 für ERiC
│   │   ├── ebilanz_xml.py     E-Bilanz als XML: Nutzdaten EBilanz mit der XBRL-Instanz für ERiC
│   │   ├── vorsatz.py         Vorsatz der Erklärungen USt, KSt und GewSt mit dem Copyrightvermerk
│   │   ├── erklaerung.py      Werte der Erklärungen nach ihrem Formatkennzeichen, Felder, Regeln und Vordrucke eines Jahres
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
│   ├── deadlines/             Fristen von Voranmeldung, ZM, Sondervorauszahlung und Jahresmeldungen mit Status, reines Python ohne Frappe-Import; Bericht „Offene Fristen“, tägliche Erinnerung und Fristerinnerung im Frappe-Modul, siehe Fristen
│   ├── mappings/              Vergleich einer Kontenzuordnung mit ihren Vorgaben oder einer Datei in drei Seiten und die Datei einer Kontenzuordnung mit Prüfsumme, reines Python ohne Frappe-Import
│   ├── setup/                 Steuerbote einrichten: Schritte und ihre Reihenfolge, Erkennung von SKR03 und SKR04, Vorschlag des Voranmeldungszeitraums, Start im laufenden Betrieb mit Voranmeldungen vor Steuerbote und Prüfliste (start.py), reines Python ohne Frappe-Import; Seite und Schritte im Frappe-Modul, siehe Einrichtung
│   ├── ustjahr/               Rechenkern der Umsatzsteuererklärung (USt 2 A) mit den Vorgaben ihrer Zeilen für SKR03 und SKR04, reines Python ohne Frappe-Import
│   ├── kst/, gewst/           Rechenkerne von Körperschaft- und Gewerbesteuer mit ihren Jahrestabellen, Vordrucken und den Vorgaben der Kontenzuordnung Ertragsteuern, reines Python ohne Frappe-Import
│   ├── ebilanz/               Kern der E-Bilanz: Positionen, Beträge, Kontensalden, Anlagenspiegel, Überleitung, GCD und Instanz, dazu die Vorgaben der Bilanzzuordnung, reines Python ohne Frappe-Import
│   ├── hgb/                   Jahresabschluss: Größenklassen, Gliederung, Angaben und Offenlegung, die XBRL-Datei für das Unternehmensregister und die Schritte des Hochladens, reines Python ohne Frappe-Import
│   ├── xbrl/                  HGB-Taxonomie und XBRL für E-Bilanz und Offenlegung und die Zeilen der Bilanzzuordnung (mapping.py), reines Python ohne Frappe-Import; tests/arelle_validation.py für den XBRL-Job der CI
│   ├── jahresmeldung/         gemeinsamer Kern der Jahresmeldungen mit Status, Korrekturen, Befunden und Berichtigungen, reines Python ohne Frappe-Import
│   │   ├── documentation.py   liest die Jahresdokumentationen der ERiC-Dokumentation als Daten: Vordrucke mit Kontexten, Feldern, Regeln, Kennzahlen und Texten, Schema und Datenartversionmatrix
│   │   └── yearcheck.py       Jahresprüfung aller Datenarten: Daten eines Jahres oder einer Taxonomie gegen die ERiC-Dokumentation
│   ├── eric/                  ERiC: Datenarten, Einrichtung, Versionsinformationen der Pakete, Mindestversionsliste, ctypes-Anbindung, Worker-Prozess, Simulation; Frappe nur in secrets.py
│   ├── ledger.py              liest das Hauptbuch eines Zeitraums als Buchungszeilen des Kerns und als Buchungen mit Leistungsdatum
│   ├── vat_periods.py         ordnet die Buchungen den Voranmeldungszeiträumen zu, nach Einstellungen und Abgaben
│   ├── invoices.py            liest die Rechnungen eines Zeitraums als Rechnungszeilen für die Hinweise
│   ├── registers.py           führt die Berichte Sales Register und Purchase Register eines Zeitraums aus
│   ├── mapping_sync.py        Zeilen der Kontenzuordnung zur Mapping des Kerns und zu den Einträgen des Vergleichs, reines Python
│   ├── tax_templates.py       liest die Konten der Steuervorlagen eines Unternehmens mit ihren Vorlagen
│   ├── zm_sources.py          liest für die Zusammenfassende Meldung Hauptbuch, Kunden, Adressen und abgegebene Voranmeldungen
│   ├── dauerfrist_sources.py  liest für die Dauerfristverlängerung die abgegebenen Voranmeldungen eines Jahres, die Voranmeldungen vor Steuerbote und das Gründungsdatum
│   ├── prior_filings.py       liest den Start der Bücher in ERPNext und die Voranmeldungen vor Steuerbote
│   ├── holiday_list.py        liest die Feiertage der Fristen aus der Feiertagsliste des Unternehmens
│   ├── ustjahr_sources.py     liest für die Umsatzsteuererklärung das Hauptbuch des Jahres, die abgegebenen Voranmeldungen, die Sondervorauszahlung und die Zahlungen an das Finanzamt
│   ├── income_tax_sources.py  liest für Körperschaft- und Gewerbesteuererklärung die Gewinn- und Verlustrechnung, die Buchungen der Steuern, die Kontenzuordnung Ertragsteuern und die Einstellungen Jahresmeldungen
│   ├── income_tax_mapping_sync.py  Zeilen der Kontenzuordnung Ertragsteuern zur Mapping des Kerns und zu den Einträgen des Vergleichs, reines Python
│   ├── balance_mapping_sync.py  Zeilen der Bilanzzuordnung zur Mapping des Kerns, ihre Vorgaben, ihre Datei und die Eingaben von Jahresabschluss und E-Bilanz, reines Python
│   ├── balances.py            liest die Salden eines Geschäftsjahres, seines Vorjahres und der Eröffnungsbilanz aus dem Hauptbuch
│   ├── ebilanz_sources.py     liest für die E-Bilanz das Geschäftsjahr, die Anlagen, die Abschreibungspläne, die Stammdaten und die abgegebene E-Bilanz des Vorjahres
│   ├── annual_accounts_sources.py  liest für den Jahresabschluss die Bücher des Geschäftsjahres und des Vorjahres über die Bilanzzuordnung
│   ├── headcount.py           zählt für den Jahresabschluss die Arbeitnehmer an den Quartalsenden
│   ├── steuerbote/            Frappe-Modul „Steuerbote“, siehe Architektur
│   │   ├── page/              Seite „Steuerbote einrichten“; setup.py daneben führt ihre Schritte aus
│   │   ├── annual_filing.py   Grundlage der Belege der Jahresmeldungen (AnnualFiling), siehe Jahresmeldungen
│   │   ├── deadlines.py       liest Einstellungen, Belege, Feiertage und Hauptbuch für die Fristen und schickt die Erinnerung
│   │   ├── doctype/           Einstellungen, Kontenzuordnung, Umsatzsteuer-Voranmeldung, Zusammenfassende Meldung, Dauerfristverlängerung, USt-IdNr.-Bestätigung, ELSTER-Übermittlung und Fristerinnerung, dazu Einstellungen Jahresmeldungen, Kontenzuordnung Ertragsteuern, Bilanzzuordnung, Umsatzsteuererklärung, Körperschaft- und Gewerbesteuererklärung, E-Bilanz und Jahresabschluss, alle samt Tabellen; elster_transmission/transmission.py übermittelt jeden Beleg, der über ERiC geht
│   │   ├── report/            Berichte „UStVA Kennzahlen“ mit den Belegen hinter jeder Kennzahl, „Offene Fristen“, „Ertragsteuer-Kontennachweis“ und „E-Bilanz Positionen“
│   │   ├── workspace/         Arbeitsbereich „Steuern“
│   │   ├── sidebar/           Seitenleiste des Moduls mit Gruppen, Symbolen und kurzen Bezeichnungen
│   │   ├── number_card/       Zahlenkarte „Offene Voranmeldungen“
│   │   └── print_format/      Druckformate „Umsatzsteuer-Voranmeldung“, „Zusammenfassende Meldung“, „Dauerfristverlängerung“, „Umsatzsteuererklärung“, „Körperschaftsteuererklärung“, „Gewerbesteuererklärung“, „E-Bilanz“ und „Jahresabschluss“
│   ├── dock/                  Eintrag „Steuern“ in der Leiste von ERPNext
│   ├── fixtures/              Feld „Nicht in der Umsatzsteuer-Voranmeldung“ an der Journalbuchung und Standard-Druckformate der Belege
│   ├── public/                Logo (images/), Symbol der Leiste (icons/) und was die Formulare einbinden: die Übermittlung (js/elster_transmission.js), „USt-IdNrn. prüfen“ (js/vat_id_confirmation.js), die Schaltflächen der Jahresmeldungen (js/annual_filing.js) und der Dialog der Unterschiede einer Zuordnung (js/mapping_differences.js)
│   ├── translations/          deutsche Übersetzungen der Oberfläche (de.csv)
│   ├── tests/                 Frappe-Integrationstests und Hilfen für Testdaten und Übermittlungen, unter e2e/ die Browsertests mit ihren Testdaten, in desk_symbols.txt die Symbole, die der Desk von Frappe und ERPNext hat
│   ├── patches/               Patches, die bench migrate ausführt (patches.txt)
│   └── config/, templates/    Standardverzeichnisse einer Frappe-App; templates/includes/print/ hält das Stylesheet und Kopf- und Fußzeile aller Druckformate, templates/includes/annual_filing/ die Teile der Druckformate der Jahresmeldungen, templates/includes/annual_accounts/ die des Jahresabschlusses
├── docs/                      Dokumentation
│   └── bilder/                Bildschirmfotos der Oberfläche mit Beispieldaten
├── .github/workflows/         CI: Tests, Linters, Security
├── .github/dependabot.yml     wöchentliche Updates für GitHub Actions und pip
├── pyproject.toml             Paketdaten, Einstellungen für ruff, pytest und coverage
├── requirements-dev.txt       Entwicklungswerkzeuge, exakt gepinnt
└── .pre-commit-config.yaml    Hooks für pre-commit
```

Die Kerne unter `steuerbote/ustva`, `steuerbote/zm`, `steuerbote/vatid`, `steuerbote/dauerfrist` und die der Jahresmeldungen (`steuerbote/ustjahr`, `kst`, `gewst`, `ebilanz`, `hgb`, `xbrl` und `jahresmeldung`) importieren nie Frappe. Deshalb lassen sie sich ohne Bench testen. DocTypes und Reports gehören in das Frappe-Modul `steuerbote/steuerbote`. Wie Kern und Frappe-Modul zusammenspielen, beschreibt [Architektur](architektur.md).

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

`steuerbote/elster/tests/test_schema.py` prüft das XML gegen die Schemas der ERiC-Dokumentation: die Datei für Mein ELSTER und die Nutzdaten des Vordrucks USt 1 H gegen `UStVA-2026.xsd`, Nutzdaten und Umschlag gegen `elster11_UStVA_2026_extern.xsd` mit dem ElsterBasisSchema, dazu Reihenfolge, Typen und Längen, die `ustva_xml.py` aus dem Schema übernimmt, und den Vordruck gegen die Beispiele `UStVA_Df_2026.xml` und `UStVA_SoVZ_2026.xml` in Canonical XML 2.0. `test_zm_schema.py` prüft die Nutzdaten der Zusammenfassenden Meldung gegen `zm_000005.xsd` und im Umschlag gegen `elster11_Zm_000005_extern.xsd`, vergleicht sie Byte für Byte mit dem Beispiel `ZMDO_5_send-Auth.xml` und die Werte, die `zm_xml.py` übernimmt, mit Schema und Jahresdokumentation. `steuerbote/eric/tests/test_datenart.py` vergleicht die Beschreibung jeder Datenart in `steuerbote/eric/datenart.py` mit Beispielen, Schemas, Datenartversionmatrix und Jahresdokumentation ZMDO, und `test_header.py` prüft den DatenTeil jeder Datenart im ganzen Umschlag gegen dessen Schema. `test_vorsatz.py` und `test_erklaerung.py` vergleichen Vorsatz und Formatkennzeichen der Erklärungen mit den Jahresdokumentationen E50, E30 und E20, ihren Schemas und Beispielen. `test_ust2a_xml.py`, `test_kst_xml.py` und `test_gewst_xml.py` prüfen die Nutzdaten der Erklärungen gegen `E50-2026.xsd`, `E30-2025.xsd` und `E20-2025.xsd`, die von Körperschaft- und Gewerbesteuer 2026, nachdem der Test Namensraum und Version auf die des Schemas 2025 umgeschrieben hat, und `test_ebilanz_xml.py` die Lieferung der E-Bilanz gegen `ebilanz_000002.xsd`. Die Schemas tragen keine Lizenz, die eine Weitergabe erlaubt, deshalb liegen sie nicht im Repository. Die Tests lesen sie aus der entpackten ERiC-Dokumentation, deren Verzeichnis die Umgebungsvariable `STEUERBOTE_ERIC_DOC_DIR` nennt:

```bash
curl -fLo /tmp/eric-doc.zip https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Dokumentation.zip
echo "bad21c27ecce56d04fc04bccfd2dfa17b9ff2455aa878758100fc73a28492ad5  /tmp/eric-doc.zip" | sha256sum --check
unzip -q /tmp/eric-doc.zip -d /tmp/eric-doc
STEUERBOTE_ERIC_DOC_DIR=/tmp/eric-doc pytest --cov
```

Die Variable nennt das Verzeichnis, in das die Zip-Datei entpackt wurde, oder darin das Verzeichnis `Dokumentation`. Sie gilt ebenso für `bench run-tests`, das die Tests unter `steuerbote/elster` mitnimmt. Ohne die Variable überspringt pytest die Schematests und sagt, warum; in einer CI (Umgebungsvariable `CI`) schlagen sie stattdessen fehl. Die CI lädt die Dokumentation in beiden Testjobs, prüft die SHA-256-Summe und entpackt nur die Verzeichnisse der UStVA und der ZMDO, jede Datenart des Verfahrens ElsterErklaerung mit `Formale_Plausipruefungen.ods`, das Verzeichnis ElsterBilanz, die Datenartversionmatrix und das ElsterBasisSchema. Gepinnt ist 44.3.6.0, die produktive Version. ERiC 45.1.5.0 ist eine Beta, ihr Schema für 2026 gleicht dem von 44.3.6.0 bis auf den Kopfkommentar.

Aus der Beta kommen die Daten der Voranmeldung 2027 vorläufig (`steuerbote/ustva/years.py`). Ihre Tests, etwa `steuerbote/elster/tests/test_schema_2027.py`, lesen Jahresdokumentation, Schema und Beispiele von 2027 aus demselben Verzeichnis und überspringen sich, auch in der CI, solange es eine Dokumentation ohne 2027 ist wie 44.3.6.0 (`eric_schema.ustva_year`). Lokal laufen sie mit der Beta:

```bash
curl -fLo /tmp/eric-doc-45.zip https://download.elster.de/download/eric/eric_45/ERiC-45.1.5.0-Dokumentation.zip
echo "9b43f426d006e1b892bbc9cd15d789c18dc3017f7f0d4d5c0399dfbf48b30b64  /tmp/eric-doc-45.zip" | sha256sum --check
unzip -q /tmp/eric-doc-45.zip -d /tmp/eric-doc-45
STEUERBOTE_ERIC_DOC_DIR=/tmp/eric-doc-45 pytest steuerbote/ustva steuerbote/dauerfrist steuerbote/elster steuerbote/eric
STEUERBOTE_ERIC_DOC_DIR=/tmp/eric-doc-45 pytest steuerbote/jahresmeldung/tests/test_yearcheck.py -k BetaDocumentationTest
```

Mit der Beta prüfen diese Tests auch 2026 gegen deren Dokumentation 2026. Ihre Beispiele des Vordrucks USt 1 H tragen andere erfundene Daten als die von 44.3.6.0, deshalb schlagen dabei beide Kontexte von `Ust1HEnvelopeSchemaTest.test_writes_the_examples_of_the_documentation` fehl, ebenso `BilanzDocumentationTest` in `steuerbote/eric/tests/test_simulation.py` mit dem Beispiel der E-Bilanz; die übrigen Tests unter `steuerbote/jahresmeldung` lesen die Erklärungen von 44.3.6.0. Maßgeblich für 2026 bleibt 44.3.6.0.

### Tests gegen die HGB-Taxonomie

Auch die HGB-Taxonomie trägt keine Lizenz, die eine Weitergabe erlaubt. Die Tests unter `steuerbote/xbrl`, `steuerbote/ebilanz` und `steuerbote/hgb` laufen deshalb gegen eine erfundene Mini-Taxonomie oder einen Auszug und, wenn die Umgebungsvariable `STEUERBOTE_TAXONOMY_6_9` das Paket von esteuer.de nennt, auch gegen das echte Paket; in einer CI schlagen sie ohne die Variable fehl. Der Server von esteuer.de schickt sein Zwischenzertifikat nicht mit, deshalb kommt es mit geprüfter Summe von GlobalSign:

```bash
curl -fLo /tmp/intermediate.crt http://secure.globalsign.com/cacert/gsgccr46dvtlsca2025.crt
echo "b59410f367b986e98e53a9789a6580553a74be515211d9f6ecb6e8a11e83aeaa  /tmp/intermediate.crt" | sha256sum --check
{ cat /etc/ssl/certs/ca-certificates.crt; openssl x509 -inform DER -in /tmp/intermediate.crt; } > /tmp/esteuer.pem
curl -fL --cacert /tmp/esteuer.pem -o /tmp/taxonomy-6.9.zip https://www.esteuer.de/download/taxonomie_20250618/german-gaap-taxonomy-v6.9-2025-04-01-xbrl.zip
echo "accd62202d73c036910fee118b30730f0392934afc9730617788e30a0480df87  /tmp/taxonomy-6.9.zip" | sha256sum --check
STEUERBOTE_ERIC_DOC_DIR=/tmp/eric-doc STEUERBOTE_TAXONOMY_6_9=/tmp/taxonomy-6.9.zip pytest --cov
```

Das Paket 6.10 kommt ebenso dazu, mit der Variablen `STEUERBOTE_TAXONOMY_6_10`; gegen es laufen die Tests der Taxonomie 6.10 (`real.view_6_10()` in `steuerbote/xbrl/tests/real.py`), etwa die Änderungen gegen 6.9 in `steuerbote/xbrl/tests/test_changes.py` und die E-Bilanz und die Offenlegung der erfundenen Unternehmen auf 6.10:

```bash
curl -fL --cacert /tmp/esteuer.pem -o /tmp/taxonomy-6.10.zip https://www.esteuer.de/download/taxonomie_20260615/germany-gaap-taxonomy-v6.10-2026-04-01-xbrl.zip
echo "de00ceaad0e532d238dea24a48160ec335422a3a71c38dd03c7b2b34b32fff76  /tmp/taxonomy-6.10.zip" | sha256sum --check
STEUERBOTE_ERIC_DOC_DIR=/tmp/eric-doc STEUERBOTE_TAXONOMY_6_9=/tmp/taxonomy-6.9.zip STEUERBOTE_TAXONOMY_6_10=/tmp/taxonomy-6.10.zip pytest --cov
```

### XBRL mit Arelle

`steuerbote/xbrl/tests/arelle_validation.py` lässt Arelle (`arelle-release` aus `requirements-dev.txt`) 18 Instanzen beider Profile offline gegen das Paket 6.9 prüfen: fünf der gültigen Beispiele der ERiC-Dokumentation auf der Kerntaxonomie, wie der Writer sie schreibt; die E-Bilanz einer erfundenen GmbH als Einheitsbilanz, als Handelsbilanz mit Überleitung, als Eröffnungsbilanz und als UG, wie `steuerbote/ebilanz/instance.py` sie baut; die Offenlegung einer erfundenen GmbH als Kleinstkapitalgesellschaft und als kleine Gesellschaft; und die sieben Instanzen der Offenlegung aus `steuerbote/hgb/tests/companies.py`, wie `steuerbote/hgb/instance.py` sie baut, prüft und schreibt. Jede Meldung ab Warnung lässt den Lauf scheitern. Mit Dokumentation und Paket wie oben läuft das Skript auch lokal; in der CI dauert es etwa vier Minuten:

```bash
STEUERBOTE_ERIC_DOC_DIR=/tmp/eric-doc python -m steuerbote.xbrl.tests.arelle_validation /tmp/taxonomy-6.9.zip --keep /tmp/xbrl
```

`--keep` behält Paket, Instanzen und die Protokolle von Arelle im Verzeichnis. In der CI macht das ein Job für sich, siehe [CI](#ci).

Mit `--version 6.10` prüft das Skript dieselben Instanzen gegen das Paket 6.10, die Offenlegung mit der Version eines Geschäftsjahres ab 2027, und die gültigen Beispiele der Taxonomie 6.10, wenn die Dokumentation sie hat: 44.3.6.0 hat keine, und das Skript sagt das; mit der Dokumentation 45.1.5.0 sind es wieder 18 Instanzen, in der CI 13:

```bash
STEUERBOTE_ERIC_DOC_DIR=/tmp/eric-doc python -m steuerbote.xbrl.tests.arelle_validation /tmp/taxonomy-6.10.zip --version 6.10 --keep /tmp/xbrl-6.10
```

### Frappe-Tests

Auf einer Site mit ERPNext und Steuerbote:

```bash
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app steuerbote
```

Die Tests schreiben in die Datenbank der Site. Nimm dafür eine eigene Testsite, nie eine Site mit echten Daten.

Der Frappe-Runner durchsucht die ganze App nach Dateien `test_*.py`. Die Tests des Kerns sind `unittest.TestCase`-Klassen, deshalb laufen sie bei `run-tests` ebenfalls mit. Die Frappe-Tests unter `steuerbote/tests` erben von `IntegrationTestCase` aus `frappe.tests`.

### Browsertests

Die Browsertests unter `steuerbote/tests/e2e` bedienen eine laufende Site mit Playwright und Chromium wie ein Mensch am Bildschirm: die Anmeldung, den Eintrag „Steuern“ in der Leiste von ERPNext, den Arbeitsbereich mit seinen Abschnitten und Verknüpfungen, die Seitenleiste mit ihren Gruppen und dem Symbol jedes Eintrags außerhalb einer Gruppe und jeder Gruppe, jede Liste der Seitenleiste, neue Belege, die Umsatzsteuer-Voranmeldung (Berechnen, „USt-IdNrn. prüfen“ bis zur Rückfrage, das Menü ELSTER bis zum Dialog für Zertifikat und Passwort, „XML für Mein ELSTER“, Druckvorschau), die Zusammenfassende Meldung (Berechnen, „USt-IdNrn. prüfen“ bis zur Rückfrage, „CSV für Mein ELSTER“), die Dauerfristverlängerung, die Entwürfe der drei Belege nach dem eigenen Senden (kein „Berechnen“, kein „USt-IdNrn. prüfen“, kein „Verwerfen“), „Steuerbote einrichten“ zweimal für dasselbe Unternehmen, Einstellungen, Kontenzuordnung mit „Vorgaben laden“ samt der Spalte Steuersatz, „Vorgaben aktualisieren“, „Zuordnung exportieren“ und „Zuordnung importieren“, „Vorgaben laden“ der Kontenzuordnung Ertragsteuern mit den DATEV-Konten, die dem Unternehmen fehlen, und ERiC-Einstellungen, die Umsatzsteuererklärung (Berechnen mit den Zeilen der Rechnungen und den Monaten ohne abgegebene Voranmeldung, der Hinweis, dass Mein ELSTER sie nicht importiert, Testsenden in der Simulation bis zur Rückfrage, Druckvorschau), die Körperschaft- und die Gewerbesteuererklärung (Berechnen mit den Befunden der vorläufigen Vordrucke, Druckvorschau), die E-Bilanz (die berechnete E-Bilanz mit ihren Positionen, Berechnen ohne Taxonomie, Druckvorschau, der Bericht „E-Bilanz Positionen“), der Jahresabschluss (Berechnen mit Größenklasse, Bilanz und Angaben, Druckvorschau in Kontoform, die „Vorschau der Offenlegung“ als PDF, die XBRL-Datei erst, wenn er festgestellt werden kann), neue Belege der Jahresmeldungen als Entwurf, die Berichte „UStVA Kennzahlen“ und „Offene Fristen“ und die Sicht eines Benutzers, der nur die Rolle Accounts User hat. Ein Test schlägt fehl, sobald eine seiner Seiten einen JavaScript-Fehler, einen Fehler auf der Konsole oder eine Antwort des Servers mit Status 500 oder mehr sieht; Antworten mit 4xx sind Ablehnungen des Servers, die die Tests an dem messen, was die Oberfläche daraus macht. Ein fehlgeschlagener Test legt Bildschirmfotos seiner Seiten unter `test-results/` ab; die Tests von Seitenleiste und Arbeitsbereich legen dort nach jedem Lauf `sidebar.png` und `workspace.png` ab, die Seitenleiste mit geöffneten Gruppen, und die Tests der Belege, der beiden Berichte und von „Steuerbote einrichten“ die Bilder des README, benannt wie unter `docs/bilder` (siehe [Bilder des README](#bilder-des-readme)).

Die Testdaten legt `steuerbote/tests/e2e/seed.py` mit den Hilfen der Frappe-Tests an, alle erfunden: ein Unternehmen mit SKR03-Konten, Einstellungen und der Kontenzuordnung aus „Vorgaben laden“, drei Rechnungen im Oktober 2026 (Inland 19 %, sonstige Leistung an einen Kunden in Österreich mit USt-IdNr., eine Leistung nach § 13b UStG), eine USt-IdNr.-Bestätigung, eine in Mein ELSTER abgegebene Voranmeldung für September, berechnete Voranmeldung und Zusammenfassende Meldung für Oktober, eine Dauerfristverlängerung, ein zweites Unternehmen ohne Konten mit Voranmeldung und Zusammenfassender Meldung für Oktober und einer Dauerfristverlängerung, alle drei als Entwurf mit der ELSTER-Übermittlung eines echten Sendens (Voranmeldung und Dauerfristverlängerung von ELSTER angenommen, ohne dass sie sich buchen ließen, die Zusammenfassende Meldung mit unbekanntem Ergebnis), ein drittes Unternehmen nur mit SKR03-Konten für „Steuerbote einrichten“, dessen Browsertest vorher löscht, was ein früherer Lauf eingerichtet hat, ein viertes mit SKR03-Konten und der Kontenzuordnung aus „Vorgaben laden“ für „Vorgaben aktualisieren“ und die Datei einer Kontenzuordnung, für das erste Unternehmen die berechnete Umsatzsteuererklärung 2026, die ohne die Voranmeldungen der übrigen Monate auf „Berechnet“ bleibt, ein fünftes Unternehmen mit SKR03-Konten, Einstellungen Jahresmeldungen (eine GmbH mit einem Anteilseigner, einer Betriebsstätte, einem Hebesatz von 400 % mit Quelle und den Vorauszahlungen ihrer Bescheide), der Kontenzuordnung Ertragsteuern aus „Vorgaben laden“ und den Buchungen des Jahres 2026 mit seiner berechneten Körperschaft- und Gewerbesteuererklärung, beide wegen der vorläufigen Vordrucke auf „Berechnet“ und ohne Übermittlung, ein sechstes Unternehmen mit dem berechneten Jahresabschluss 2026 aus den Salden einer erfundenen Kleinstkapitalgesellschaft, dessen Angaben, Feststellung und Unterschriften offen bleiben, ein siebtes mit der E-Bilanz 2026, die der Seed mit der Mini-Taxonomie der Tests berechnet und die ohne eingerichtete Taxonomie auf „Berechnet“ bleibt, ERiC-Einstellungen im Simulationsmodus und den Benutzer `steuerbote-e2e-buchhaltung@example.com` mit der Rolle Accounts User. Ein zweiter Lauf legt nichts doppelt an. Außerdem schließt der Seed den Einrichtungsassistenten ab, gibt der Site die Regionaleinstellungen, die der Einrichtungsassistent einer Site in Deutschland gibt, Datum, Uhrzeit und Zahlen im deutschen Format und die Zeitzone Europe/Berlin, dazu den Euro hinter dem Betrag (31.12.2026 23:59, 1.234,56 €), und stellt Zeitzone und Sprache des Administrators und des Benutzers auf Europe/Berlin und Deutsch. Nimm dafür eine eigene Testsite, nie eine Site mit echten Daten.

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

`bench start` startet neben dem Webserver auch socket.io, mit dem die Seiten sich verbinden; `bench use` macht die Testsite zur Site von `localhost`. Ohne `--admin-password` melden sich die Tests mit `admin` an, dem Passwort der Testsite in der CI. Das Passwort des Benutzers mit der Rolle Accounts User setzt jeder Lauf neu über den Administrator, der Seed vergibt keines. `--headed` zeigt den Browser, `--output` nennt ein anderes Verzeichnis für die Bildschirmfotos. In der CI dauert der ganze Lauf etwa zwei Minuten.

Die Testmodule importieren weder pytest noch Playwright: `bench run-tests` importiert jede Datei `test_*.py` der App, in der Umgebung der Bench, die beides nicht hat. Was die Tests brauchen, auch `expect` von Playwright, geben ihnen die Fixtures in `conftest.py`; `desk.py` hält die Schritte auf den Seiten des Desks.

### Ausdrucke als PDF

Die Vorschau im Browser zeigt keine Seitenumbrüche. Deshalb druckt der Job „Frappe site“ zum Schluss jedes Druckformat als PDF, so wie eine Site es druckt, mit beiden Druckmaschinen, die Frappe anbietet: wkhtmltopdf 0.12.6.1 mit gepatchtem Qt aus den Paketen des wkhtmltopdf-Projekts, dessen SHA-256-Summe der Job prüft, und dem Generator auf Chromium-Basis mit dem Chrome des Runners, beide mit der Schrift Nimbus Sans aus den URW-Schriften wie im Image der Site. Die Adresse der Site zeigt dabei auf einen Host, den es nicht gibt: Ein Druckformat darf nichts nachladen. wkhtmltopdf bekommt das HTML ohne den Verweis auf Frappes Druckpaket, den Frappe jedem Druckformat beifügt und den wkhtmltopdf über die Adresse der Site holen würde; jede andere Adresse im HTML lässt den Ausdruck scheitern. Der Seed legt seine Belege auf Deutsch an, der Sprache des Desks, so dass auch die Texte, die „Berechnen“ speichert, etwa die Befunde, deutsch sind; `steuerbote/tests/print_proof.py` druckt auf Deutsch, bricht ab, wenn die deutschen Übersetzungen fehlen, und nimmt je Druckformat einen Beleg des Seeds und druckt ihn in Varianten, die im Speicher bleiben: „kurz“ wie angelegt, „lang“ mit jeder Tabelle dreimal, 45 Befunden und langen Anmerkungen, „namen“ mit einem langen erfundenen Firmennamen, langen Bezeichnungen, großen negativen Beträgen und als Berichtigung, beim Jahresabschluss dazu die Vorschau der Offenlegung. Mit wkhtmltopdf entsteht jeder Ausdruck ohne das Stylesheet von Frappes Druckpaket, der kurze zusätzlich mit ihm; der Generator auf Chromium-Basis nimmt die Dateien der Bench von der Platte. `steuerbote/tests/printouts.py` prüft dann die Wörter jeder Seite, die `pdftotext -bbox` von Poppler liest: die Zahl der Seiten, „Seite n von N“ und die Nummer des Belegs auf jeder Seite, kein Wort über den Rand, keine zwei Wörter übereinander, keine Überschrift allein am Seitenende, keine letzte Seite mit fast nichts darauf Überschrift und Summe eines Blocks auf derselben Seite, ein bekannter deutscher Text im Ausdruck und kein englisches Wort, das nur eine fehlende Übersetzung druckt. Hat ein Ausdruck ein Problem, wird der Job rot. Das Artefakt `printouts` hält nach jedem Lauf die PDFs, die Wörter ihrer Seiten und `report.md` mit Seiten und Problemen jedes Ausdrucks; was die Prüfungen nicht sehen, zeigt der Blick auf die Seiten. Lokal, gegen eine Bench mit wkhtmltopdf und Poppler:

```bash
bench --site <site> execute steuerbote.tests.e2e.seed.run
bench --site <site> execute steuerbote.tests.print_proof.run --kwargs "{'directory': '/tmp/ausdrucke'}"
```

#### Bilder des README

Die Bilder unter `docs/bilder` kommen aus den Browsertests, mit den erfundenen Daten des Seeds. Ein Test, dessen Seite das README zeigt, ruft `Desk.picture()` mit dem Namen des Bilds auf, sobald die Seite zeigt, was er geprüft hat; das Bild selbst prüft nichts. `Desk.picture()` wartet, bis der Desk nichts mehr lädt und kein Dialog mehr offen ist, und nimmt dann das Fenster von 1440 × 900 Pixeln auf, oben auf der Seite oder mit dem Abschnitt eines Felds direkt unter dem Kopf der Seite, wie die Kennzahlen der Voranmeldung, mit dem Zeiger in der Ecke des Fensters und ohne Fokus. Alle Bilder zusammen kosten den Lauf wenige Sekunden. Für neue Bilder lädt man das Artefakt `browser-tests` eines grünen Laufs herunter, bringt jedes Bild auf 256 Farben, damit es unter 150 KB bleibt, und ersetzt die Datei gleichen Namens unter `docs/bilder`; `workspace.png` wird dafür oben auf 1440 × 900 Pixel zugeschnitten und heißt dort `workspace-steuern.png`, `sidebar.png` wird auf die Seitenleiste zugeschnitten und heißt `seitenleiste.png`. Jedes Bild unter `docs/bilder` zeigt das README oder eine Seite unter `docs/`, und jedes Bild, das das README zeigt, liegt dort; beides prüft `steuerbote/tests/test_docs_overview.py`.

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

Alle drei Workflows laufen bei Pull Requests, bei Pushes auf `main` und von Hand, Security zusätzlich jeden Montag um 04:17 UTC. Sie lesen den Inhalt des Repositories nur (`contents: read`), lediglich CodeQL darf zusätzlich Sicherheitsbefunde schreiben. Ausgecheckt wird ohne gespeicherte Zugangsdaten (`persist-credentials: false`). Am Pull Request stehen damit zehn Prüfungen: die neun Jobs der Workflows und das Ergebnis von CodeQL im Code Scanning von GitHub. Ein Pull Request wird erst gemergt, wenn alle zehn grün sind.

| Workflow | Job | Was er tut |
|---|---|---|
| Tests | Core (without bench) | lädt die ERiC-Dokumentation 44.3.6.0 und die HGB-Taxonomie 6.9 und prüft ihre SHA-256-Summen, dann pytest mit Abdeckung, Schematests, den Tests gegen die Taxonomie und der Jahresprüfung aller Datenarten auf Python 3.14, unter 100 % rot; legt `coverage.xml` als Artefakt ab. |
| Tests | Frappe site (ERPNext v16) | baut mit `frappe-bench` 5.31.1 eine Bench mit Frappe und ERPNext `version-16`, MariaDB 11.8 und Redis als Dienste, installiert ERPNext und Steuerbote auf einer Testsite, lädt die ERiC-Dokumentation und die HGB-Taxonomie für die Schematests und die Tests gegen die Taxonomie und führt `bench run-tests --app steuerbote` aus. Danach baut er die Assets von Frappe, füllt die Testsite mit dem Seed der Browsertests, druckt jedes Druckformat mit wkhtmltopdf als PDF und prüft die Seiten (siehe [Ausdrucke als PDF](#ausdrucke-als-pdf); Artefakt `printouts`), startet Webserver und socket.io und lässt die Browsertests mit Chromium laufen; das Artefakt `browser-tests` hält nach jedem Lauf die Bildschirmfotos von Seitenleiste und Arbeitsbereich, die Bilder des README und die Protokolle des Servers, nach einem Fehlschlag dazu die Bildschirmfotos der Seiten des Tests. |
| Tests | XBRL (Arelle) | lädt die Beispiele der E-Bilanz aus der ERiC-Dokumentation und die HGB-Taxonomie 6.9 und lässt Arelle die 18 Instanzen beider Profile prüfen (`arelle_validation.py`, siehe [XBRL mit Arelle](#xbrl-mit-arelle)), mit eigener Zeitgrenze von 20 Minuten; schlägt er fehl, liegen Instanzen und Protokolle eine Woche im Artefakt `xbrl-instances`, nie eine Datei der Taxonomie. |
| Linters | pre-commit | alle Hooks auf allen Dateien, ohne `no-commit-to-branch`. |
| Linters | Frappe semgrep rules | semgrep 1.185.0 mit den Regeln aus `frappe/semgrep-rules` und den Regeln `python/lang/correctness` aus `semgrep/semgrep-rules`, die die Registry als `r/python.lang.correctness` anbietet, beide auf einen Commit gepinnt; jeder Fund macht den Job rot. |
| Security | Secret scan (gitleaks) | durchsucht die ganze Git-Historie nach Geheimnissen; gitleaks wird mit Prüfsumme geladen. |
| Security | Workflow audit (zizmor) | prüft die GitHub-Actions-Workflows auf Sicherheitsprobleme. |
| Security | Dependency audit (pip-audit) | prüft mit pip-audit 2.10.1 die Pakete aus `requirements-dev.txt` auf bekannte Schwachstellen. |
| Security | CodeQL | statische Analyse des Python-Codes. Läuft nur, solange das Repository öffentlich ist (`if: ${{ !github.event.repository.private }}`), weil CodeQL nur für öffentliche Repositories kostenlos ist. |
| Code Scanning von GitHub | CodeQL | das Ergebnis der Analyse des Jobs CodeQL am Pull Request: ob der geänderte Code neue Befunde hat. |

Adresse und SHA-256-Summe von ERiC-Dokumentation, HGB-Taxonomie und Zwischenzertifikat stehen einmal für alle Jobs im `env` von `tests.yml`. Das Paket der Taxonomie kommt aus einem Cache, dessen Schlüssel seine SHA-256-Summe trägt (`hgb-taxonomie-6.9-<Summe>`); nur ohne Eintrag lädt ein Job es von esteuer.de und legt es danach in den Cache. Geprüft wird die Summe in jedem Fall vor den Tests. Bei Tests bricht ein neuer Lauf für denselben Pull Request oder Branch den laufenden ab. Dependabot schlägt jede Woche Updates für die GitHub Actions und die pip-Abhängigkeiten vor (`.github/dependabot.yml`).

Das Paket 6.10 kommt ebenso in die drei Jobs, mit `TAXONOMY_6_10` und `TAXONOMY_6_10_SHA256` im `env` von `tests.yml` und einem Cache nach seiner Summe (`hgb-taxonomie-6.10-<Summe>`); Core und Frappe geben es den Tests mit `STEUERBOTE_TAXONOMY_6_10`, und der XBRL-Job lässt Arelle ein zweites Mal gegen 6.10 prüfen, dessen Instanzen und Protokolle das Artefakt `xbrl-instances` unter `xbrl-6.10` hält.

## Versionen

- **Frappe und ERPNext:** nur die aktuelle Hauptversion, derzeit 16. `pyproject.toml` verlangt `>=16.54.0,<17.0.0` (`[tool.bench.frappe-dependencies]`), denn erst ab Frappe 16.54.0 zählt der Rate Limiter je Benutzer (`user_based`), den `stash_certificate` braucht, `hooks.py` setzt ERPNext voraus, und die CI baut gegen `version-16`. Frappe und ERPNext installiert bench; sie stehen nicht in den Abhängigkeiten des Pakets. Ältere Hauptversionen werden nicht unterstützt, es gibt keine Kompatibilitätsschichten.
- **Python:** 3.14, in `requires-python`, als `target-version` von ruff und in der CI.
- **Entwicklungswerkzeuge** sind in `requirements-dev.txt` exakt gepinnt, die pre-commit-Hooks über `rev`, semgrep, pip-audit, frappe-bench, gitleaks und zizmor in den Workflows. Die Regeln für semgrep kommen wie die Actions auf einen Commit gepinnt aus ihren Repositories (`linters.yml`); Dependabot hebt diese Commits nicht, ein Update ist Handarbeit. `steuerbote/tests/test_workflows.py` prüft, dass jedes `pip install` eine exakte Version nennt und jede Action und jedes andere Repository einen Commit. Einige Versionen stehen an mehreren Stellen: ruff in `requirements-dev.txt` und `.pre-commit-config.yaml`, zizmor zusätzlich in `security.yml`. Ein Update zieht alle Stellen gleich. Playwright lädt mit `playwright install` die Version von Chromium, zu der es gehört.
- **lxml** baut das XML für ELSTER. Frappe 16 bringt es selbst mit, ohne eine Version festzulegen. `pyproject.toml` verlangt deshalb nur `lxml>=6.0,<7`, damit die App neben Frappe kein anderes lxml erzwingt, und `requirements-dev.txt` pinnt die Version, mit der die Tests laufen.
- **ERiC-Dokumentation** für die Schematests und die Jahresprüfung: Adresse und SHA-256-Summe der Zip-Datei stehen in `tests.yml`, die Version zusätzlich in `steuerbote/elster/tests/eric_schema.py`; `test_workflows.py` prüft, dass beide dieselbe Adresse nennen. Zum Jahreswechsel kommt eine Version, die das neue Jahr kennt, siehe [Jahreswechsel](#jahreswechsel).
- **HGB-Taxonomie** für die Tests gegen die Taxonomie und den XBRL-Job: Adresse und SHA-256-Summe des Pakets stehen in `tests.yml` und in `steuerbote/xbrl/versions.py`, `test_workflows.py` prüft, dass beide übereinstimmen. Eine neue Version kommt als Eintrag in `TAXONOMIES` dazu, siehe [Jahreswechsel](#jahreswechsel).
- **Arelle** (`arelle-release` 2.47.5, Apache-2.0) nur für den XBRL-Job der CI, exakt in `requirements-dev.txt`; die App selbst braucht es nicht.
- **Neue Abhängigkeiten** nur mit Grund, exakt gepinnt und im Pull Request begründet.
- **Dependabot** meldet jede Woche neue Versionen für pip und GitHub Actions.

## Jahreswechsel

Ein neues Jahr ist eine Änderung an Daten, kein Umbau. ELSTER nimmt jede Meldung nur in der Datenart ihres Jahres an, die E-Bilanz nur in der ihrer HGB-Taxonomie. Deshalb führt jedes Modul eine Jahrestabelle mit den Jahren oder Versionen, die es kennt, jedes mit seiner Quelle, und hält jeden Teil eines Jahres in einer eigenen Tabelle nach dem Jahr. Ein `test_years.py` je Modul, bei der E-Bilanz `test_versions.py`, schlägt fehl, solange einer Tabelle ein Jahr fehlt oder eine ein Jahr zu viel hat.

| Modul | Jahrestabelle | Tabellen je Jahr | Die Jahresprüfung liest |
|---|---|---|---|
| Umsatzsteuer-Voranmeldung | `YEARS` in `steuerbote/ustva/years.py` | `CATALOGUES` in `ustva/kennzahlen.py`, `SCHEMAS` in `elster/ustva_xml.py`, `LAYOUTS` in `dauerfrist/form.py` | `Jahresdokumentation_UStVA_<Jahr>.ods`, `UStVA-<Jahr>.xsd`, `Datenartversionmatrix.ods` |
| Umsatzsteuererklärung | `YEARS` in `steuerbote/ustjahr/years.py` | `CATALOGUES` in `ustjahr/form.py`, `LOCAL_RULES` und `LEFT_TO_ERIC` in `ustjahr/rules.py`, `ROLE_FIELDS`, `ANNUAL_ACCOUNTS` und `REVISIONS` in `ustjahr/defaults.py`, `SCHEMAS` in `elster/ust2a_xml.py` | `Jahresdokumentation_E50_<Jahr>.ods` mit den Blättern von USt2A und Vorsatz, `E50-<Jahr>.xsd`, `Datenartversionmatrix.ods` |
| Körperschaftsteuer | `YEARS` in `steuerbote/kst/years.py`, 2026 vorläufig mit den Vordrucken der Jahresdokumentation E30 2025 | `CATALOGUES` und `RECHTSFORMEN` in `kst/form.py`, `SCHEMAS` in `elster/kst_xml.py`; Sätze und Grenzen im Eintrag des Jahres; die Regeln, die der Kern rechnet, nennt `expected_rules` in `kst/chain.py`, `kst/losses.py` und `kst/einlagekonto.py` | `Jahresdokumentation_E30_<Jahr>.ods` mit den Blättern der Vordrucke, „Benutzerdefinierte Typen“ und „Vorsatz - Felder“, `E30-<Jahr>.xsd`, `Datenartversionmatrix.ods` |
| Gewerbesteuer | `YEARS` in `steuerbote/gewst/years.py`, 2026 vorläufig mit E20 2025 | `CATALOGUES` und `RECHTSFORMEN` in `gewst/form.py`, `SCHEMAS` in `elster/gewst_xml.py`; Zahlen im Eintrag des Jahres; `expected_rules` in `gewst/chain.py` | `Jahresdokumentation_E20_<Jahr>.ods` wie bei E30, `E20-<Jahr>.xsd`, `Datenartversionmatrix.ods` |
| E-Bilanz und Offenlegung | `TAXONOMIES` in `steuerbote/xbrl/versions.py` je Version der HGB-Taxonomie, `BILANZ_TAXONOMIES` in `eric/releases.py` je Wirtschaftsjahr | die Tabellen nach der Version, die `xbrl/tests/test_versions.py` nennt | `Jahresdokumentation_Bilanz_Taxonomie_<Version>.ods` mit den Regeln der Vordrucke Kontext und Header, `Datenartversionmatrix.ods` |
| Größenklassen des Jahresabschlusses | die Schwellen in `steuerbote/hgb/size.py` nach dem Geschäftsjahr | keine | nichts: die Schwellen stehen im HGB, nicht in der ERiC-Dokumentation |

### Jahresprüfung

`python -m steuerbote.jahresmeldung.yearcheck` vergleicht die Daten jeder Datenart mit der entpackten ERiC-Dokumentation, im selben Verzeichnis wie bei `STEUERBOTE_ERIC_DOC_DIR` (siehe [Schematests](#schematests)):

```bash
python -m steuerbote.jahresmeldung.yearcheck /tmp/eric-doc               # jede Datenart, jedes Jahr ihrer Tabellen
python -m steuerbote.jahresmeldung.yearcheck /tmp/eric-doc USt KSt 2027  # nur diese Datenarten und nur 2027
python -m steuerbote.jahresmeldung.yearcheck /tmp/eric-doc 6.10          # nur die E-Bilanz mit der Taxonomie 6.10
```

Nach dem Verzeichnis folgen Datenarten (`UStVA`, `USt`, `KSt`, `GewSt` und `Bilanz`, in beliebiger Schreibweise), Jahre und Versionen der HGB-Taxonomie, die nur die E-Bilanz nimmt. Ohne Datenart prüft der Befehl jede, ohne Jahr jedes Jahr ihrer Tabellen, und nennt dann auch die Jahre und Versionen, die die Dokumentation über die Tabellen hinaus hat, etwa `UStVA 2028: not in YEARS of steuerbote/ustva/years.py; Jahresdokumentation_UStVA_2028.ods: documented`. Ein vorläufiges Jahr der Voranmeldung, dessen Jahresdokumentation die Dokumentation nicht hat, übergeht er dabei, so 2027 mit 44.3.6.0; genannt endet es mit 2. Ein Jahr der E-Bilanz ist ein Wirtschaftsjahr: Geprüft wird die Taxonomie, die `BILANZ_TAXONOMIES` ihm gibt, sonst jede, die die BMF-Schreiben für das Jahr zulassen; gibt es keine, sagt das eine Zeile.

Je Abweichung schreibt er eine Zeile, vorn Datenart und Jahr oder Version, dann wie bei der Voranmeldung links Steuerbote, rechts die Datei und was sie sagt, etwa `KSt 2026, rule 8900331 of ZVE: Abrunden([E8007504]*0.15); Jahresdokumentation_E30_2025.ods: not in its Prüfbedingung`. Er endet mit 0, wenn er nichts ausgibt, mit 1 bei einer Abweichung und mit 2, wenn der Dokumentation eine Datei fehlt, die er liest; die übrigen Datenarten prüft er trotzdem. Hat eine Tabelle das Jahr noch nicht, nennt die erste Zeile diese Tabellen, und die Daten des neuesten Jahres treten an seine Stelle: Die Zeilen danach sind genau das, was das neue Jahr ändert. Ein vorläufiges Jahr, derzeit Körperschaft- und Gewerbesteuer 2026 mit den Vordrucken der Jahresdokumentation 2025, vergleicht er mit der neuesten Jahresdokumentation bis zu seinem Jahr; ist das nicht die, die das Jahr nimmt, sagt es eine Zeile.

Er vergleicht:

- **Umsatzsteuer-Voranmeldung:** alles, was `python -m steuerbote.ustva.yearcheck` vergleicht, siehe unten.
- **Umsatzsteuererklärung:** den Katalog des XML (`SCHEMAS` in `elster/ust2a_xml.py`) mit Jahresdokumentation und Schema: Quelle und Versionslabel, Namensraum und Version, die Vordrucke aus „Allg. Information“ und aus dem Schema mit Reihenfolge und maxOccurs, je Feld von USt2A seine Stelle in der Reihenfolge der Jahresdokumentation und des Schemas, Kontext, Formatkennzeichen, Vordruckzeile, Kennzahl, Pflichtfeld, max. Zeilen, Beschreibung (für `$VZ$` das Jahr), Max. Länge eines Texts, regulären Ausdruck und die Werte einer Liste; die Regeln des Vordrucks (`CATALOGUES` in `ustjahr/form.py`) mit Name, Kontext und Regelart; die Prüfbedingung jeder Regel, die Steuerbote selbst prüft (`LOCAL_RULES` in `ustjahr/rules.py`), und dass jede Regel von USt2A selbst geprüft oder ERiC überlassen ist (`LEFT_TO_ERIC`). Die Mitwirkung einer Steuerberatung steht in der Jahresdokumentation in den Zeilen 23 und 123, im Vordruck in den Zeilen 127 bis 129; verglichen wird mit den Zeilen der Jahresdokumentation.
- **Körperschaft- und Gewerbesteuer:** jede Regel, die der Kern rechnet, nach ihrem Fehlercode und den Teilen ihrer Prüfbedingung (`RuleExpectation` in `kst/years.py`), mit den Faktoren des Jahres; den Katalog der Vordrucke (`CATALOGUES` in `kst/form.py` und `gewst/form.py`) wie bei der Umsatzsteuererklärung, die Kennzahl mit ihrem Sachbereich und ohne das Indexfeld WJ, das die Wirtschaftsjahre von Anlage GK und KSt 1 F zählt; was der Writer aus dem Schema nimmt (`SCHEMAS` in `elster/kst_xml.py` und `gewst_xml.py`): die Kontexte, die sich wiederholen, mit ihrem maxOccurs und die Vordrucke mit Indexfeld; die Kategorien der Rechtsformen, die Steuerbote abgibt (`RECHTSFORMEN`), mit `RECHTSFORM_KOERPERSCHAFTEN_V3` und `RECHTSFORM_GEWERBESTEUER_V2` aus „Benutzerdefinierte Typen“.
- **E-Bilanz:** je Version von `TAXONOMIES` ihre Jahresdokumentation und, für die Module der E-Bilanz, die Regeln der Taxonomie rechnen und sich mit ihrem `expected_rules` in `BILANZ_EXPECTING` eintragen, deren Prüfbedingungen.
- **Bei jeder Erklärung** Länge und Pflicht der Texte des Vorsatzes (`TEXTS` in `elster/vorsatz.py`), **bei jeder Datenart** datenartVersion, Plugin und Jahr oder Taxonomie ihrer Zeile in `Datenartversionmatrix.ods`.

Die Dateien liest [`steuerbote/jahresmeldung/documentation.py`](../steuerbote/jahresmeldung/documentation.py) mit der Standardbibliothek: eine Jahresdokumentation mit ihren Vordrucken und deren Blättern Kontexte, Felder, Regeln, Kennzahlen und Texte, mit „Allg. Information“ (Versionslabel, Namensraum, Vordrucke) und, bei der E-Bilanz, der Regelliste der Vordrucke Kontext und Header und den „Strukturellen Fehlern“; das Schema einer Erklärung mit den Feldern jedes Vordrucks und den Werten seiner Listen; die Zeilen der Datenartversionmatrix. Die Tests der Kataloge vergleichen über denselben Leser. Für 2026 und die Taxonomie 6.9 gibt der Befehl mit der ERiC-Dokumentation 44.3.6.0 nichts aus; in der CI prüft das `DocumentationTest` in [`test_yearcheck.py`](../steuerbote/jahresmeldung/tests/test_yearcheck.py). Mit der Beta-Dokumentation 45.1.5.0 nennt er, was kommt: für die Umsatzsteuererklärung 2026 die Jahresdokumentation mit dem Versionslabel 11.0 statt 9.0, die an Feldern und Regeln nichts ändert, und die Taxonomie 6.10. Die Voranmeldung 2026 und 2027 stimmt mit ihr überein; das prüft `BetaDocumentationTest`, mit der Beta.

#### Jahresprüfung der Voranmeldung

`python -m steuerbote.ustva.yearcheck` vergleicht die Daten eines Jahres mit der entpackten ERiC-Dokumentation, im selben Verzeichnis wie bei `STEUERBOTE_ERIC_DOC_DIR` (siehe [Schematests](#schematests)):

```bash
python -m steuerbote.ustva.yearcheck /tmp/eric-doc 2026
```

Ohne Jahr prüft der Befehl jedes Jahr von `YEARS`. Er liest `Jahresdokumentation_UStVA_<Jahr>.ods` mit den Blättern „Anmeldungssteuern - Felder“ und „Anmeldungssteuern - Regeln“, `UStVA-<Jahr>.xsd` und `Datenartversionmatrix.ods`, alles mit der Standardbibliothek ([`documentation.py`](../steuerbote/ustva/documentation.py)), und vergleicht ([`yearcheck.py`](../steuerbote/ustva/yearcheck.py)):

- den Katalog mit den Feldern des Kontexts `Umsatzsteuervoranmeldung`: welche Kennzahlen es gibt, ihre Art nach dem Formatkennzeichen und ihre Zeile nach der Vordruckzeile; mit den Regeln: die Paare aus Bemessungsgrundlage und Steuer, die `FelderNichtGemeinsamAngegeben` nur zusammen annimmt, und Kz 83 als einzige Kennzahl, die eine Regel verlangt; dazu mit den Elementen des Schemas und deren Typen;
- das Schema von `ustva_xml.py` mit dem XSD: Namensraum, Version, Reihenfolge der Elemente und die Kennzahlen ohne Vorzeichen, die auch die Formatkennzeichen U und % der Jahresdokumentation nennen;
- das Layout des Vordrucks USt 1 H mit Feldern und Regeln seiner beiden Kontexte und mit deren Elementen im Schema;
- datenartVersion und Plugin des Jahres und die der ZMDO mit der Datenartversionmatrix.

Je Abweichung schreibt er eine Zeile, links die Daten von Steuerbote, rechts die Datei und was sie sagt, etwa `catalogue 2026, Kz 66: line 38; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 37`. Für 2026 gibt er mit der ERiC-Dokumentation 44.3.6.0 nichts aus, für 2026 und 2027 mit der Beta 45.1.5.0. Er endet mit 0, wenn er nichts ausgibt, mit 1 bei einer Abweichung und mit 2, wenn die Dokumentation eines Jahres fehlt. Hat eine Tabelle das Jahr noch nicht, nennt die erste Zeile diese Tabellen, und der Befehl vergleicht an ihrer Stelle die Daten des neuesten Jahres: Seine Zeilen sind dann genau das, was das neue Jahr ändert. Ein vorläufiges Jahr kommt aus der Dokumentation eines späteren Release; ohne Jahr übergeht der Befehl es, wo die Dokumentation seine Jahresdokumentation nicht hat (`passes_over`), so 2027 mit 44.3.6.0, und genannt endet er mit 2. In der CI prüft `DocumentationTest` in [`test_yearcheck.py`](../steuerbote/ustva/tests/test_yearcheck.py) jedes Jahr von `YEARS`, das die Dokumentation hat, auf diese Weise; 2027 prüft er mit der Beta (`test_2027_agrees_with_the_documentation_of_the_beta_it_comes_from`).

### Umsatzsteuer-Voranmeldung Schritt für Schritt

ELSTER nimmt eine Voranmeldung und den Vordruck USt 1 H nur in der Datenart ihres Jahres an, deshalb hat jedes Jahr seine Daten, je Teil in einer eigenen Tabelle. Welche Jahre es gibt, sagt `YEARS` in [`steuerbote/ustva/years.py`](../steuerbote/ustva/years.py), mit dem BMF-Schreiben der Vordrucke jedes Jahres. Jede andere Tabelle hält genau diese Jahre: [`test_years.py`](../steuerbote/ustva/tests/test_years.py) schlägt fehl, solange einer Tabelle ein Jahr fehlt oder eine ein Jahr zu viel hat.

| Teil | Tabelle | Quelle | Test |
|---|---|---|---|
| Jahr und BMF-Schreiben der Vordrucke | `YEARS` in `steuerbote/ustva/years.py` | BMF-Schreiben „Muster der Vordrucke im Umsatzsteuer-Voranmeldungs- und -Vorauszahlungsverfahren“ | `test_years.py` |
| Kennzahlen des Vordrucks USt 1 A | `CATALOGUES` in `steuerbote/ustva/kennzahlen.py` | Vordruck USt 1 A und Anleitung USt 1 E | `test_kennzahlen.py`, Jahresprüfung |
| Schema `Anmeldungssteuern`: Namensraum, Reihenfolge der Elemente, Kennzahlen ohne Vorzeichen | `SCHEMAS` in `steuerbote/elster/ustva_xml.py` | `UStVA-<Jahr>.xsd` der ERiC-Dokumentation | Jahresprüfung, `test_schema.py` |
| Felder und Regeln des Vordrucks USt 1 H | `LAYOUTS` in `steuerbote/dauerfrist/form.py` | `Jahresdokumentation_UStVA_<Jahr>.ods`, Vordruck USt 1 H | Jahresprüfung, `test_form.py` |
| datenartVersion und Plugin von ERiC | keine: `years.py` bildet `UStVA_<Jahr>` und `checkUStVA_<Jahr>` aus dem Jahr, `datenart.ustva` in `steuerbote/eric/datenart.py` nimmt sie in die Datenart des Jahres | `Datenartversionmatrix.ods` | Jahresprüfung, `test_years.py`, `test_datenart.py`, `test_runtime.py` |
| Zusammenfassende Meldung | keine: Die Datenart ZMDO hat für jedes Jahr die datenartVersion `ZMDO`, das Plugin `checkZMDO` (`ZMDO` in `steuerbote/eric/datenart.py`) und das Schema 000005 (`zm_xml.py`); das Jahr des Meldezeitraums steht in ihren Daten (Feld `jahr`) | `Datenartversionmatrix.ods`, `zm_000005.xsd` | Jahresprüfung, `test_datenart.py`, `test_zm_schema.py` |

Mitte November erscheint die Beta des neuen Hauptrelease von ERiC; ihre Dokumentation enthält Jahresdokumentation und Schema des neuen Jahres ([ERiC](eric.md#versionen-und-jahreswechsel)). Das BMF-Schreiben mit den Vordruckmustern folgt im Dezember, für 2026 am 29. Dezember 2025. Die ersten Meldungen des neuen Jahres sind am 10. Februar fällig: die Sondervorauszahlung und, ohne Dauerfristverlängerung, die Voranmeldung für Januar. Jeder Schritt beginnt mit dem Test.

1. **BMF-Schreiben.** Das Schreiben zu den Vordruckmustern des neuen Jahres lesen; es nennt die Änderungen in einem eigenen Abschnitt, und die Anleitungen markieren sie mit „Neu!“. Das Jahr mit Datum, Geschäftszeichen und Adresse des Schreibens in `YEARS` eintragen und die Jahre in `test_files_2026_and_2027` von `test_years.py` nennen. Ab dann schlagen `PartsTest` fehl, bis jede Tabelle das Jahr hat, und `test_the_data_of_each_year_cite_its_source`, bis die Docstrings von `kennzahlen.py` und `form.py` das Schreiben zitieren. Ohne Schreiben kommt das Jahr vorläufig dazu, siehe [2027, vorläufig aus der Beta](#2027-vorläufig-aus-der-beta).
2. **Katalog.** Erst die Tabelle des neuen Vordrucks USt 1 A in `test_kennzahlen.py` nach dem Muster von `FORM_UST_1_A_2026`, dann `_FORM_<Jahr>` in `kennzahlen.py` mit seinem Eintrag in `CATALOGUES`. Der Katalog des Vorjahres bleibt. Was dabei zu vergleichen ist, auch für Rundung, Fälligkeit und die Vorgaben der Kontenrahmen, steht in [Kennzahlen und Kontenzuordnung](ustva-kennzahlen.md#jahreswechsel). Test: `test_kennzahlen.py`.
3. **Jahresdokumentation.** Die Dokumentation des neuen Release laden und entpacken und `python -m steuerbote.ustva.yearcheck <Verzeichnis> <Jahr>` laufen lassen, gern schon, bevor eine Tabelle das Jahr hat. Jede Zeile wird zu einer Änderung im Katalog, im Schema oder im Layout, bis der Befehl nichts mehr ausgibt. Nennt er ein Formatkennzeichen, das `KINDS_BY_FORMAT` nicht kennt, oder eine weitere Kennzahl, die eine Regel verlangt, muss zuerst der Schreiber des XML lernen, sie zu schreiben. Test: Jahresprüfung, in der CI `DocumentationTest`.
4. **XSD.** Den Eintrag des Jahres in `SCHEMAS` von `ustva_xml.py` anlegen: Namensraum (`targetNamespace` von `UStVA-<Jahr>.xsd`), Reihenfolge der `xs:sequence` von `Umsatzsteuervoranmeldung` und die Kennzahlen ohne Vorzeichen. Dann die gepinnte ERiC-Dokumentation auf eine Version heben, die das Jahr kennt: Adresse und SHA-256-Summe in beiden Jobs von `.github/workflows/tests.yml`, die Version in `steuerbote/elster/tests/eric_schema.py`. Mit der Beta-Dokumentation 45.1.5.0, die 2027 schon enthält, laufen alle Tests für 2026 so durch wie mit 44.3.6.0. Test: Jahresprüfung; `test_schema.py` prüft das geschriebene XML bisher gegen das Schema von 2026 und bekommt das neue Jahr dazu.
5. **Plugin.** Nichts zu ändern, solange die Datenartversionmatrix datenartVersion und Plugin nach dem Jahr benennt: `years.py` bildet beide Namen, `datenart.ustva` nimmt sie in die Datenart des Jahres, und die Laufzeit in `steuerbote/eric/runtime.py` liest mit ihnen die Jahre ihrer Plugins und wählt die Laufzeit nach dem Plugin der Datenart. Im Betrieb die Beta zum Prüfen und Testsenden und die freigegebene Version zum Senden einrichten, siehe [ERiC](eric.md#versionen-und-jahreswechsel). Test: Jahresprüfung, `test_years.py`, `test_datenart.py`, `test_runtime.py`.
6. **USt 1 H.** `_LAYOUT_<Jahr>` in `form.py` aus der Jahresdokumentation anlegen: die Felder jedes Kontexts in der Reihenfolge des Schemas mit regulärem Ausdruck, Formatkennzeichen, Längen und Vordruckzeile, die Regeln beider Kontexte und die Bezeichnungen des Vordrucks USt 1 H, etwa „Davon 1/11 = Sondervorauszahlung <Jahr>“. `LAYOUTS` nimmt es unter seinem Jahr auf. Benennt die Jahresdokumentation eine Regel um, auf die `Ust1H` sich stützt (`Svz_Kz29_ohne_Kz10`, `Svz_Kz38_Pflichtfeld`, `Kz500_Begr_Gemeinsam`, `Kz26_Hinweis`, `Kz500_Hinweis`), braucht `form.py` den neuen Namen. Test: Jahresprüfung, `test_form.py`, `steuerbote/dauerfrist/tests/test_docs.py` mit der Tabelle in [Dauerfristverlängerung](dauerfristverlaengerung.md#vordruck-ust-1-h-in-elster).
7. **Tests.** `pytest --cov` mit der neuen Dokumentation, 100 % Abdeckung bleiben, und `bench run-tests`. Mit einer Kopie von 2027 als 2028 schlagen unter `pytest` nur `test_files_2026_and_2027` und, solange die Docstrings das neue Jahr nicht zitieren, `test_the_data_of_each_year_cite_its_source` fehl: Die Tests eines Jahres ohne Daten nehmen das Jahr nach `LATEST_YEAR`, und die der Umsatzsteuererklärung bauen ihre `Mapping` für das Jahr ihres Vordrucks USt 2 A. Tests, die den neuesten Katalog nehmen (`KENNZAHLEN`, eine `Mapping` ohne Jahr, die Vorgaben), laufen danach gegen das neue Jahr und zeigen, was es an Berechnung und Vorgaben ändert.
8. **Zeiträume: Kz 39 und Dauerfristverlängerung.** Mit der neuen Anleitung prüfen, ob die Sondervorauszahlung weiter in Kz 39 der letzten Voranmeldung des Jahres steht (`SONDERVORAUSZAHLUNG_KENNZAHL`, `bridge.sondervorauszahlung_values`, `crediting_period` in `steuerbote/dauerfrist/period.py`) und ob die Fristen bleiben: der 10. Tag nach dem Zeitraum in `steuerbote/ustva/period.py`, der 10. Februar für die Sondervorauszahlung in `steuerbote/dauerfrist/period.py`. Im Betrieb braucht jedes Jahr mit Dauerfristverlängerung eine Zeile in „Dauerfristverlängerung je Jahr“ der Einstellungen: Bei monatlicher Abgabe schreibt sie der Beleg „Dauerfristverlängerung“ des neuen Jahres mit dem Vermerk seiner Abgabe, bei vierteljährlicher Abgabe mit fortgeltender Verlängerung, für die es keinen Beleg gibt, legt sie jemand von Hand an. Ein Wechsel des Voranmeldungszeitraums kommt als neue Regel ab Januar dazu. Test: `steuerbote/dauerfrist/tests/test_period.py`, `steuerbote/ustva/tests/test_period.py`, `vat_return/test_bridge.py`.
9. **Release.** Die Dokumentation nachziehen ([Kennzahlen](ustva-kennzahlen.md), [Dauerfristverlängerung](dauerfristverlaengerung.md), [ERiC](eric.md), [Roadmap](roadmap.md)), dann die Version in `steuerbote/__init__.py` heben und veröffentlichen, bevor die ersten Meldungen des Jahres fällig sind. Betreiber spielen die neue Version ein und richten die freigegebene ERiC-Version mit dem Plugin des Jahres ein.

#### 2027, vorläufig aus der Beta

2027 kam am 23. November 2026 dazu, bevor das BMF das Schreiben mit den Vordruckmustern 2027 veröffentlicht hatte und ERiC 45 freigegeben war. Die Schritte, wie sie dafür gelaufen sind:

1. **BMF-Schreiben.** Die Liste der BMF-Schreiben auf bundesfinanzministerium.de nannte kein Schreiben zu den Vordrucken 2027, das neueste war vom 13. November 2026. Deshalb trägt `YEARS` für 2027 statt des Schreibens `provisional=True`, die Dokumentation `Beta ERiC 45.1.5.0` und `form_year=2026`, das Jahr des Vordrucks, dessen Zeilen und Bezeichnungen 2027 behält; die Docstrings von `kennzahlen.py` und `form.py` zitieren `Year.source`, die Jahresdokumentation der Beta. Test: `test_years.py`.
2. **Jahresprüfung.** `python -m steuerbote.ustva.yearcheck /tmp/eric-doc-45 2027` nannte vor den Daten von 2027 nur Namensraum und Version des Schemas, Format und Länge von Kz 09 in beiden Kontexten des Vordrucks USt 1 H und die entfallenen Regeln `Df_Kz09_Laenge` und `Svz_Kz09_Laenge`. Ein Vergleich aller Blätter der Jahresdokumentationen 2026 und 2027 fand dazu die Regel 11085156 zu Kz 44, den Wegfall von `UStVA_Laenge_Kz09` und den neuen Text von `Kz500_Hinweis`, siehe [Kennzahlen, Jahrgang 2027](ustva-kennzahlen.md#jahrgang-2027-vorläufig). Test: `test_2027_changes_kz09_and_its_rules_against_2026` mit der Beta.
3. **Katalog, Schema, Layout.** Der Katalog 2027 ist der von 2026 (`_FORM_2027`), das Schema 2027 nimmt Namensraum und Version von 2027 und die Reihenfolge von 2026, das Layout 2027 Kz 09 aus fünf Ziffern ohne die beiden Regeln und „Davon 1/11 = Sondervorauszahlung 2027“. Test: `test_kennzahlen.py`, `test_ustva_xml.py`, `test_ust1h_xml.py` mit Beispieldateien 2027, `test_form.py`, mit der Beta `test_schema_2027.py`.
4. **CI.** Gepinnt bleibt 44.3.6.0; die Tests gegen die Dokumentation 2027 überspringen sich dort, und die Jahresprüfung übergeht ohne Jahr ein vorläufiges Jahr, dessen Jahresdokumentation die Dokumentation nicht hat.
5. **Plugin.** Nichts zu ändern: Das Plugin `checkUStVA_2027` kommt mit ERiC 45, und bis eine freigegebene Laufzeit es hat, meldet „Laufzeitumgebung prüfen“ es als fehlendes Plugin des Jahres 2027 (`next_year_check` in `steuerbote/eric/releases.py`).
6. **Zeiträume.** Die Fristen 2027 mit Wochenenden und Feiertagen, die Sondervorauszahlung 2027 am 10. Februar 2027 und ihre Anrechnung über Kz 39 im Dezember 2027 stehen als Tests in `steuerbote/ustva/tests/test_period.py`, `steuerbote/dauerfrist/tests/test_period.py` und `vat_return/test_bridge.py`.
7. **Simulation.** Die Regeln zum Aufbau gelten 2027 unverändert; neu gibt die Simulation ab 2027 den Hinweis 11085156 zu Kz 44. Test: `test_fake.py`, `RulesDocumentationTest` gegen die Jahresdokumentation jedes Jahres.
8. **Vorläufig an Belegen und Ausdrucken.** Voranmeldung und Dauerfristverlängerung eines vorläufigen Jahres tragen „Vorläufige Vordrucke“, werden nicht „Bereit“, gehen nur mit einer Begründung in den Bemerkungen ab, und ihre Druckformate behalten den Aufbau von 2026 mit „vorläufig (Beta ERiC 45.1.5.0, Vordruck 2026)“ unter dem Titel. Test: `vat_return/test_provisional_files.py`, `test_extension_files.py`, die Frappe-Tests von Voranmeldung, Dauerfristverlängerung und Druckformat.

Was noch kommt: Mit ERiC 45 die gepinnte Dokumentation heben (Adresse und SHA-256-Summe in `tests.yml`, die Version in `eric_schema.py`) und die Jahresprüfung 2027 gegen sie laufen lassen; mit dem BMF-Schreiben den Vordruck USt 1 A 2027 Zeile für Zeile mit dem Katalog vergleichen, den Vordruck USt 1 H 2027 mit dem Layout und beide mit den Druckformaten, die DATEV-Ausgaben 2027 mit den Vorgaben (siehe [Kennzahlen, Jahreswechsel](ustva-kennzahlen.md#jahreswechsel)), dann das Schreiben in `YEARS` eintragen und `provisional` streichen.

### Umsatzsteuererklärung Schritt für Schritt

Die Jahresdokumentation E50 eines Jahres kommt mit der ERiC-Dokumentation, die das Jahr kennt; ab dann nennt die Jahresprüfung ohne Jahr `USt <Jahr>: not in YEARS of steuerbote/ustjahr/years.py`. Jeder Schritt beginnt mit dem Test.

1. **BMF-Schreiben.** Das Schreiben „Muster der Umsatzsteuererklärung <Jahr>“ lesen und das Jahr mit Datum, Geschäftszeichen und Adresse in `YEARS` von `steuerbote/ustjahr/years.py` eintragen. Ab dann schlägt `PartsTest` in `steuerbote/ustjahr/tests/test_years.py` fehl, bis jede Tabelle das Jahr hat.
2. **Jahresprüfung.** `python -m steuerbote.jahresmeldung.yearcheck <Verzeichnis> USt <Jahr>` laufen lassen. Die erste Zeile nennt die Tabellen, denen das Jahr fehlt, jede weitere eine Änderung gegenüber dem Vorjahr.
3. **Katalog.** Den Vordruck des Jahres in `CATALOGUES` von `ustjahr/form.py`: die Felder in der Reihenfolge des Schemas mit Kontext, Zeile, Formatkennzeichen, Bezeichnung und Kennzahl, die Aufteilung der Kennzahlen der Voranmeldung und die Regeln. Test: `steuerbote/ustjahr/tests/test_form.py` und `test_documentation.py` gegen die Jahresdokumentation.
4. **Regeln.** Jede neue oder geänderte Regel in `LOCAL_RULES` von `ustjahr/rules.py` mit ihrer Prüfbedingung oder in `LEFT_TO_ERIC` mit dem Grund. Test: `test_rules.py`.
5. **Vorgaben.** `ROLE_FIELDS`, `ANNUAL_ACCOUNTS` und `REVISIONS` in `ustjahr/defaults.py` für das Jahr, gegen die Kontenrahmen des Jahres. Test: `test_defaults.py`.
6. **XML.** Den Eintrag des Jahres in `SCHEMAS` von `elster/ust2a_xml.py` mit den regulären Ausdrücken und Listen der Jahresdokumentation. Test: `steuerbote/elster/tests/test_ust2a_xml.py` gegen `E50-<Jahr>.xsd`.
7. **Bis die Jahresprüfung nichts mehr ausgibt**, dann Tests, Dokumentation und Release wie bei der Voranmeldung.

### Körperschaft- und Gewerbesteuer Schritt für Schritt

ERiC 44.3.6.0 kennt Körperschaft- und Gewerbesteuer bis 2025, deshalb nimmt 2026 vorläufig die Vordrucke der Jahresdokumentationen E30 und E20 2025 (`documentation_year` und `provisional` in `kst/years.py` und `gewst/years.py`).

1. **Neue Jahresdokumentation.** Sobald eine ERiC-Dokumentation `Jahresdokumentation_E30_2026.ods` oder `Jahresdokumentation_E20_2026.ods` enthält, meldet die Jahresprüfung `KSt 2026, Jahresdokumentation: Jahresdokumentation_E30_2025.ods, provisionally; Datenarten/ElsterErklaerung/KSt/Jahresdokumentation: Jahresdokumentation_E30_2026.ods, the newest up to 2026` und vergleicht die Regeln schon mit der neuen.
2. **Jahr.** Im Eintrag des Jahres in `YEARS` `documentation_year` auf das Jahr setzen, `provisional=False` und die Quellen nachziehen; ein neues Jahr bekommt einen Eintrag. Was das Gesetz nach dem Jahr staffelt, geben `statutory_rate` und `statutory_loss_share` in `kst/years.py` und `statutory_minimum_hebesatz` und `statutory_ev_rent_percent` in `gewst/years.py`; jede andere Zahl gegen ihre Quelle prüfen. Test: `steuerbote/kst/tests/test_years.py`, `steuerbote/gewst/tests/test_years.py`.
3. **Vordrucke.** Die Tabellen von `CATALOGUES` in `kst/form.py` und `gewst/form.py` aus den Blättern „<Vordruck> - Felder“ der neuen Jahresdokumentation, mit ihrer Quelle und ihrem Versionslabel; `RECHTSFORMEN` aus „Benutzerdefinierte Typen“ und `SCHEMAS` in `elster/kst_xml.py` und `gewst_xml.py` aus dem Schema des Jahres. Test: `steuerbote/kst/tests/test_form_documentation.py`, `steuerbote/gewst/tests/test_form_documentation.py`, `steuerbote/elster/tests/test_kst_xml.py` und `test_gewst_xml.py`.
4. **Regeln.** Jede Zeile zu einer Regel nennt einen Teil, den ihre Prüfbedingung nicht mehr enthält: die Rechnung im Kern (`kst/chain.py`, `kst/losses.py`, `kst/einlagekonto.py`, `gewst/chain.py`) und ihr `expected_rules` anpassen. Test: `steuerbote/kst/tests/test_yearcheck.py` und die Jahresprüfung.
5. **Plugin.** „Laufzeitumgebung prüfen“ nennt `checkKSt_<Jahr>` und `checkGewSt_<Jahr>` des Jahres, siehe [ERiC](eric.md#versionen-und-jahreswechsel).

### E-Bilanz und Offenlegung Schritt für Schritt

1. **Neue Taxonomie.** Das BMF veröffentlicht die HGB-Taxonomie jedes Jahr als amtlich vorgeschriebenen Datensatz; ERiC nimmt eine neue Version mit `Jahresdokumentation_Bilanz_Taxonomie_<Version>.ods` und dem Plugin `checkBilanz_<Version>` auf. Die Jahresprüfung ohne Jahr meldet sie, mit der Beta 45.1.5.0 etwa `Bilanz 6.10: not in TAXONOMIES of steuerbote/xbrl/versions.py; Jahresdokumentation_Bilanz_Taxonomie_6_10.ods: documented`.
2. **Version.** Ein Eintrag in `TAXONOMIES` von `xbrl/versions.py` mit BMF-Schreiben, Wirtschaftsjahren, Tag der Echtfälle und dem Paket von esteuer.de mit SHA-256, dazu jede Tabelle nach der Version, die `test_versions.py` verlangt, und das Wirtschaftsjahr in `BILANZ_TAXONOMIES` von `eric/releases.py`. Test: `steuerbote/xbrl/tests/test_versions.py`.
3. **CI.** Adresse und SHA-256 des neuen Pakets kommen in das `env` von `tests.yml`, mit einem Cache nach seiner Summe, und die Tests gegen das Paket bekommen ihre Variable. Test: `steuerbote/tests/test_workflows.py`, der XBRL-Job.
4. **Jahresprüfung.** `python -m steuerbote.jahresmeldung.yearcheck <Verzeichnis> Bilanz <Version>` laufen lassen, bis sie nichts mehr ausgibt; ein Jahr nimmt sie als Wirtschaftsjahr: `… Bilanz <Jahr>` prüft die Taxonomie des Jahres.

#### 6.10

Die Schritte für die Taxonomie 6.10, aus der Dokumentation 45.1.5.0 und den Paketen von esteuer.de:

5. **Änderungen.** Was eine Version gegen die vorige ändert, steht als Daten in `CHANGES` von `steuerbote/xbrl/changes.py`: umbenannte, entfernte und neue Begriffe und die neuen Mussfelder, aus dem Änderungsnachweis zum Taxonomie-Update und den Versionierungsberichten im Paket. Für 6.10 benennt keine Position um, 43 Begriffe sind entfernt, 39 neu, und das einzige neue Mussfeld ist „sonstige Steuern, Grundsteuer“, unter dem „sonstige Steuern“ zum Summenmussfeld wird. Test: `steuerbote/xbrl/tests/test_changes.py` gegen beide Pakete.
6. **Mini-Taxonomie.** `steuerbote/xbrl/tests/mini.py` schreibt das Paket jeder Version, das von 6.10 mit den Modulen vom 2026-04-01, dem Teil „Konto nicht vorhanden oder nicht übermittelbar“ der Kontensalden, dem Mussfeld der Grundsteuer, einer erfundenen Umbenennung und einer Entfernung; `view_6_10()` in `steuerbote/ebilanz/tests/taxonomy.py` setzt die Positionen der E-Bilanz darauf.
7. **Regeln.** Die Regeln der Jahresdokumentation, die sich gegen 6.9 ändern, nach der Version in `eric/simulation/bilanz.py` (`expected_rules("6.10")`), die strukturellen Fehler der Kontensalden 170195106, 170195108, 170195109 und 170195110 in `xbrl/checks.py` und die Kontensalden ohne Konteninformationen in `ebilanz/kontennachweis.py`. Die Jahresprüfung ohne Version lässt eine Version aus, die neuer ist als alles, was die Dokumentation dokumentiert, mit 44.3.6.0 also 6.10; gegen 45.1.5.0 prüft `python -m steuerbote.jahresmeldung.yearcheck <Verzeichnis> Bilanz 6.10` sie und gibt nichts aus.
8. **Bilanzzuordnung.** Eine neue Zuordnung nennt die Positionen von `FIRST`, 6.9; „Auf neue Taxonomie heben“ hebt sie mit `CHANGES` auf die neue Version und ein Import eine Datei der früheren.
9. **Pakete in Tests und CI.** `real.view_6_10()` mit `STEUERBOTE_TAXONOMY_6_10`, die Schritte des Pakets in den drei Jobs von `tests.yml` und der Lauf von Arelle mit `--version 6.10`, siehe [Tests gegen die HGB-Taxonomie](#tests-gegen-die-hgb-taxonomie) und [XBRL mit Arelle](#xbrl-mit-arelle).

10. **Vorgaben.** `GROUPS["6.10"]` in `ebilanz/defaults.py` trägt die Gruppen von 6.9 durch `CHANGES`, mit der Gruppe der sonstigen Steuern zerlegt, denn 6.10 macht „sonstige Steuern“ zum Summenmussfeld über dem Mussfeld der Grundsteuer; Revision 1 mit ihrer SHA-256 in `DIGESTS`. Test: `steuerbote/ebilanz/tests/test_defaults.py`, siehe [Vorgaben der Bilanzzuordnung, Taxonomie 6.10](ebilanz-zuordnung.md#taxonomie-610).
11. **Beleg.** Das Feld „HGB-Taxonomie“ der E-Bilanz bietet die Version an, und `bridge.taxonomy_for` gibt sie den Wirtschaftsjahren, die sie grundsätzlich nehmen. Test: `electronic_balance_sheet/test_bridge.py`, `test_electronic_balance_sheet.py`.

Was noch kommt: mit ERiC 45 die gepinnte Dokumentation heben, dann prüft die Jahresprüfung ohne Version auch 6.10; und mit ERiC 46 die Echtfälle von 6.10 ab Mai 2027.

## Commits

- Commit-Nachrichten sind englisch, im Imperativ und vervollständigen den Satz „If applied, this commit will …“, etwa `add Kennzahl 35 for other tax rates` oder `fix truncation of negative bases`.
- Keine Ticket-Präfixe, keine Fußzeilen (Trailer).
- Die Nachricht sagt, was sich ändert, und warum, wenn das Warum nicht offensichtlich ist.
- Branches heißen nach dem Thema, etwa `ustva-kz-35-andere-steuersaetze`. Auf `main` wird nicht direkt committet.
- Ein Thema pro Pull Request, die Dokumentation im selben Pull Request.
