"""The default Bilanzzuordnung for the DATEV standard charts SKR03 and SKR04, per version of the HGB-Taxonomie.

„Vorgaben laden“ and „Vorgaben aktualisieren“ of the Balance Sheet Mapping read these tables, and „Steuerbote
einrichten“ makes the mapping of a company with them (steuerbote/steuerbote/doctype/balance_sheet_mapping). This
release holds them empty, at revision 0: the defaults of the DATEV charts follow as their own work, from the DATEV
labels „Gültig für 2026“ and the labels, the definitionGuidance and the fiscal references of the taxonomy, without
DATEV's own mapping to the E-Bilanz.

Format. DEFAULTS[version][chart] is a steuerbote.xbrl.mapping.Defaults for each version of TAXONOMIES
(steuerbote/xbrl/versions.py) and each chart of CHARTS, with three tuples of entries. An entry names one account or
a DATEV range by its first and last number, both included and of the same length, as a text such as "1800" or
"1800-1849"; entries do not overlap, and every account of a company within one takes its place with its own number:

- DefaultRule(accounts, concept, opposite=None, purpose=Purpose.BOTH, shareholder=False, remaining_term=None): the
  position of the GAAP module without its prefix, such as "bs.ass.currAss.cashEquiv.bank"; the position a balance on
  the other side goes to, such as "bs.eqLiab.liab.bank.other" (Technischer Leitfaden zur HGB-Taxonomie 6.9, A.13);
  the Abschlusszweck of DATEV, Purpose.COMMERCIAL for HB and Purpose.TAX for SB (Fußnote 4 of the charts); and the
  flags of the Offenlegung, owed to or by the shareholders (§ 42 Abs. 3 GmbHG) and the remaining term of a Forderung
  or Verbindlichkeit as a steuerbote.hgb.statement.RemainingTerm or its row value, "up to one year", "one to five
  years" or "over five years" (§ 268 Abs. 4 and 5 HGB).
- DefaultWatched(accounts, level=WatchLevel.BLOCKING): accounts whose position the defaults cannot decide; a balance
  on one holds the E-Bilanz and the Jahresabschluss back, at WatchLevel.HINT it only adds a hint.
- DefaultExcluded(accounts, reason): accounts outside the Bilanz and the GuV, with the reason on one line, such as the
  Vortrags- and statistical accounts of class 9.

steuerbote.xbrl.mapping checks every position of a rule against the taxonomy of its version, and
steuerbote/ebilanz/tests/test_defaults.py does so for these tables against the package of esteuer.de.

Version. The defaults of a chart and a version of the taxonomy have a version of their own: the chart, the taxonomy,
the edition of the DATEV charts and the revision, such as „SKR03 Taxonomie 6.9 2026.0“ (defaults_version()). Every
change of the defaults of a version raises its revision in REVISIONS, so that the same version always means the same
defaults, and test_defaults.py pins the SHA-256 of the rows of each (Defaults.rows()); a new edition of the DATEV charts
starts at 1 again. A Balance Sheet Mapping keeps the version and the rows it took over, so that Vorgaben aktualisieren
tells a change of the defaults from a change of the user (steuerbote/mappings/diff.py).
"""

from types import MappingProxyType

from steuerbote.xbrl.mapping import Defaults

DATEV_EDITION = 2026
"""The edition of the DATEV charts the defaults follow, „Gültig für 2026“."""
CHARTS = frozenset({"SKR03", "SKR04"})

DEFAULTS: MappingProxyType[str, MappingProxyType[str, Defaults]] = MappingProxyType(
	{
		"6.9": MappingProxyType(
			{
				"SKR03": Defaults("SKR03", "6.9"),
				"SKR04": Defaults("SKR04", "6.9"),
			}
		),
	}
)
REVISIONS: MappingProxyType[str, int] = MappingProxyType({"6.9": 0})


def defaults_for(chart: str, version: str) -> Defaults:
	"""The defaults of a chart for a version of the taxonomy."""
	if version not in DEFAULTS:
		raise KeyError(f"no defaults of the Bilanzzuordnung for the HGB-Taxonomie {version}")
	try:
		return DEFAULTS[version][chart]
	except KeyError:
		known = ", ".join(sorted(CHARTS))
		raise KeyError(
			f"no defaults of the Bilanzzuordnung for chart {chart!r}; known charts: {known}"
		) from None


def defaults_version(chart: str, version: str) -> str:
	"""The version of the defaults of a chart for a version of the taxonomy, such as SKR03 Taxonomie 6.9 2026.0."""
	defaults_for(chart, version)
	return f"{chart} Taxonomie {version} {DATEV_EDITION}.{REVISIONS[version]}"
