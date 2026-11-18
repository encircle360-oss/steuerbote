## Was ändert sich?

<!-- Ein Thema pro Pull Request. Was ändert sich für Anwender, was intern? -->

## Quelle

<!-- Welche Primärquelle belegt eine fachliche Änderung? Gesetz, BMF-Schreiben, ELSTER-Dokumentation, ERPNext-Dokumentation. -->

## Checkliste

- [ ] Tests zuerst: Jede Änderung hat einen Test, der ohne sie fehlschlägt. Kein Test wurde abgeschwächt.
- [ ] Die Dokumentation unter `docs/` und im README passt zum Code.
- [ ] Keine echten Steuernummern, Zertifikate, PINs, Zugangsdaten oder Belegdaten in Code, Tests, Fixtures oder Screenshots.
- [ ] Geldbeträge sind `Decimal`, nie `float`.
- [ ] `pre-commit run --all-files` und `pytest` laufen lokal durch.
