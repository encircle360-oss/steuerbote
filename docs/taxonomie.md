# HGB-Taxonomie

Die E-Bilanz geht „nach amtlich vorgeschriebenem Datensatz“ an das Finanzamt (§ 5b Abs. 1 EStG). Dieser Datensatz ist die HGB-Taxonomie: ein Satz von XBRL-Schemas und Linkbases, den XBRL Deutschland e.V. pflegt und den das Bundesministerium der Finanzen jedes Jahr in einer neuen Version veröffentlicht, für 6.9 mit dem Schreiben vom 10.06.2025 (IV C 6 - S 2133-b/00064/002/006, BStBl I S. 1450). Sie besteht aus Modulen: dem Modul der Stammdaten, der GCD (`de-gcd`), und der Kerntaxonomie für branchenunabhängige Anwendungen (`de-gaap-ci`), mit Einstiegspunkten für die steuerliche und die handelsrechtliche Sicht (Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025, A.2 und A.5). Jede Position der Taxonomie hat einen Namen wie `bs.ass.currAss.cashEquiv.bank`, eine deutsche Bezeichnung, eine Richtung, ihren Platz in Darstellung und Rechnung und die steuerlichen Merkmale: Mussfeld, Summenmussfeld, Rechtsform, GuV-Format und wofür sie nicht zulässig ist.

Steuerbote liest aus der Taxonomie, was die [E-Bilanz](ebilanz.md) meldet, und prüft die [Bilanzzuordnung](architektur.md#bilanzzuordnung-balance-sheet-mapping) gegen sie; die [Offenlegung](offenlegung.md) des Jahresabschlusses schreibt ihre Datei auf derselben Taxonomie. Steuerbote liefert die Taxonomie nicht aus: Ihre Dateien sagen nur „(c) XBRL Deutschland e.V. - see http://www.xbrl.de“, und keine Lizenz erlaubt, sie weiterzugeben. Der Betreiber richtet sie deshalb auf dem Server ein, wie die Laufzeitumgebung von ERiC.

## Versionen

| Version | BMF-Schreiben | Wirtschaftsjahre | Echtfälle über ERiC | Paket |
|---|---|---|---|---|
| 6.9 | 10.06.2025, IV C 6 - S 2133-b/00064/002/006, BStBl I S. 1450 | grundsätzlich die, die nach dem 31.12.2025 beginnen, 2026 oder 2026/2027; nicht beanstandet für 2025 oder 2025/2026; letztmalig für die, die vor dem 31.12.2027 enden | ab 26.05.2026 | `german-gaap-taxonomy-v6.9-2025-04-01-xbrl.zip` von esteuer.de, SHA-256 `accd62202d73c036910fee118b30730f0392934afc9730617788e30a0480df87` |

Steuerbote kennt heute die Version 6.9, die einzige, mit der sich das Wirtschaftsjahr 2026 abgeben lässt. Die Version 6.10 hat das Bundesministerium der Finanzen mit dem Schreiben vom 8. Juni 2026 veröffentlicht; Echtfälle nimmt ERiC mit ihr ab Version 46 im Mai 2027. Dann kommt sie als zweiter Eintrag in `TAXONOMIES` (`steuerbote/xbrl/versions.py`) dazu, mit ihrem Paket, ihrer Prüfsumme und ihren Wirtschaftsjahren, und das Feld „HGB-Taxonomie“ (`taxonomy_version`) der E-Bilanz bietet sie an. Ab 6.10 braucht jede Position mit Betrag ihre Kontensalden; die E-Bilanz 6.9 weist schon heute mit einem Hinweis darauf hin (`EB-KONTENSALDEN-FEHLEN`, `EB-KONTENSALDEN-SUMME`). Was ein neues Jahr und eine neue Version im Code ändern, steht in [Entwicklung, Jahresprüfung](entwicklung.md#jahresprüfung).

Eine Eröffnungsbilanz nimmt eine Version, mit der sich auch die Schlussbilanz des ersten Wirtschaftsjahres übermitteln lässt („Übersicht über die Verwendung der Taxonomie-Versionen für die Übermittlung der E-Bilanz an die Finanzverwaltung“, Stand 03.06.2026), also die ihres Wirtschaftsjahres.

## Einrichten

Die Taxonomie richtet ein System Manager einmal je Bench ein, nicht je Site:

1. **Paket holen.** Das Paket der Version von esteuer.de laden, im Bereich „Schnittstellen zur E-Bilanz § 5b EStG“, für 6.9 <https://www.esteuer.de/download/taxonomie_20250618/german-gaap-taxonomy-v6.9-2025-04-01-xbrl.zip>, und seine SHA-256-Summe mit der aus der Tabelle oben vergleichen, etwa mit `sha256sum`.
2. **Paket nennen.** Das Paket auf den Server legen und in der `common_site_config.json` der Bench nennen, mit seinem absoluten Pfad und seiner Prüfsumme:

   ```bash
   bench set-config -g steuerbote_taxonomy_6_9 /opt/steuerbote/german-gaap-taxonomy-v6.9-2025-04-01-xbrl.zip
   bench set-config -g steuerbote_taxonomy_6_9_sha256 accd62202d73c036910fee118b30730f0392934afc9730617788e30a0480df87
   ```

   Steuerbote nimmt nur die Prüfsumme, die esteuer.de für das Paket veröffentlicht. Die Taxonomien liegen in `sites/taxonomy` der Bench; `steuerbote_taxonomy_root` nennt ein anderes Verzeichnis. Beides liegt außerhalb jeder Site, damit der Webserver die Dateien nicht ausliefert und keine Sicherung einer Site sie mitnimmt.
3. **„Taxonomie einrichten“** in den ERiC-Einstellungen prüft im Hintergrund die Prüfsumme, bevor es etwas entpackt, nimmt nur gewöhnliche Dateien auf sicheren Pfaden, legt das Paket unter `<Verzeichnis>/6.9/package` ab, jede Ansicht daneben als JSON und das Manifest `steuerbote-taxonomy.json` mit der SHA-256-Summe jeder Datei. Das Formular meldet, wenn es fertig ist. Dasselbe Paket ein zweites Mal ändert nichts; ein anderes Paket einer eingerichteten Version lehnt es ab.
4. **„Laufzeitumgebung prüfen“** meldet je Version (`taxonomy_6_9`), ob die `common_site_config.json` ihr Paket nennt, ob sie eingerichtet ist und ob ihre Dateien dem Manifest entsprechen.

Die E-Bilanz rechnet nur mit einer eingerichteten Taxonomie: Ohne sie lehnt „Berechnen“ ab und nennt den Weg über „Taxonomie einrichten“; weichen ihre Dateien vom Manifest ab, hält der Befund `SB-TAXONOMIE` die E-Bilanz vor „Bereit“ an. Die Bilanzzuordnung speichert auch ohne Taxonomie, sagt dann aber, dass sie ihre Positionen nicht geprüft hat.

## Ansichten und Profile

Ein Dokument auf der Taxonomie referenziert die GCD und genau einen Einstiegspunkt der Kerntaxonomie (Leitfaden B.3). Steuerbote liest je Einstiegspunkt eine Ansicht (`View` in `steuerbote/xbrl/taxonomy.py`) und schreibt zwei Arten von Berichten, die Profile von `steuerbote/xbrl/profiles.py`:

| Profil | Bericht | Ansicht | Einstiegspunkt |
|---|---|---|---|
| `FISCAL` | E-Bilanz nach § 5b EStG | `fiscal` | `de-gaap-ci-2025-04-01-shell-fiscal.xsd`, „GAAP steuerlicher Einzelabschluss“ |
| `DISCLOSURE` | Offenlegung nach §§ 325, 326 HGB | `commercial`, für eine Kleinstkapitalgesellschaft `commercial-microbilg` | `de-gaap-ci-2025-04-01-shell.xsd`, „GAAP Einzelabschluss“, und `de-gaap-ci-2025-04-01-shell-microbilg.xsd`, „GAAP Einzelabschluss MicroBilG“ |

Die steuerliche Ansicht hat eigene Bezeichnungen, die der Finanzverwaltung (Leitfaden A.3), und die Merkmale, nach denen die E-Bilanz meldet: Mussfelder und Summenmussfelder, die sie als NIL meldet, wo die Bücher sie nicht füllen, die Positionen, die „steuerlich“ nicht zulässig sind, und die Auffangpositionen. Die E-Bilanz nimmt die Positionen ihres Falls aus dieser Ansicht (`steuerbote/ebilanz/positions.py`), die Simulation von ERiC prüft ihre Nutzdaten mit ihr (`steuerbote/eric/simulation/bilanz.py`). Die Offenlegung nimmt die handelsrechtlichen Ansichten.

Die Dokumente nennen die Dateien der Taxonomie mit absoluten Adressen unter `http://www.xbrl.de/taxonomies/` (Leitfaden A.6), die der Server von XBRL Deutschland nicht ausliefert. Steuerbote liest sie aus dem eingerichteten Paket.

## Quellen

- EStG § 5b, gelesen am 23.11.2026 auf gesetze-im-internet.de.
- BMF-Schreiben vom 10.06.2025, IV C 6 - S 2133-b/00064/002/006, BStBl I S. 1450: die Taxonomie 6.9 als amtlich vorgeschriebener Datensatz.
- Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025, A.2, A.3, A.5, A.6 und B.3; „Übersicht über die Verwendung der Taxonomie-Versionen für die Übermittlung der E-Bilanz an die Finanzverwaltung“, Stand 03.06.2026; beide auf <https://www.esteuer.de/>.
- „Arbeitshilfe für die Einreichung von Jahresabschlüssen/Finanzberichten im XBRL-Format“ des Unternehmensregisters, Stand September 2025.
