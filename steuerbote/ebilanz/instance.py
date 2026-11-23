"""The E-Bilanz of a case: its parts from the sources of the books, the report on the fiscal view of the taxonomy, and
every finding on the way.

„Der Inhalt der Bilanz sowie der Gewinn- und Verlustrechnung ist nach amtlich vorgeschriebenem Datensatz durch
Datenfernübertragung zu übermitteln.“ (§ 5b Abs. 1 Satz 1 EStG) The Datensatz is XBRL on the HGB-Taxonomie that the
BMF publishes each year (BMF letters of 28 September 2011, BStBl I S. 855, Rn. 8, and of 10 June 2025): the profile
FISCAL of steuerbote/xbrl/profiles.py, „GAAP steuerlicher Einzelabschluss“ with the GCD (Technischer Leitfaden zur
HGB-Taxonomie 6.9, Stand 10.06.2025, A.5, B.3), written by steuerbote/xbrl/writer.py.

build() takes the structure of the case (steuerbote/ebilanz/positions.py), the master data of the GCD
(steuerbote/ebilanz/gcd.py) and the Sources, what the Frappe layer reads from the books and the settings as plain
values, and makes each part in turn:

1. the amounts of Bilanz and GuV from the balances and the adjustments (calculation.py);
2. the Überleitungsrechnung of a Handelsbilanz and the Steuerbilanz that results from it, or for a Steuerbilanz its
   amounts as they are (ueberleitung.py), which ERiC checks as a Steuerbilanz (B.15.1);
3. the Betriebsvermögensvergleich on the amounts of that Steuerbilanz (B.14.3.2.12), with the changes of the equity
   the books do not say;
4. the Anlagenspiegel (brutto) from the rows of the assets, checked against the Bilanz and that Steuerbilanz
   (anlagenspiegel.py);
5. the Kontensalden, or the reason a case of taxonomy 6.9 leaves them out (kontennachweis.py);
6. the GCD with the components the case announces and that reason (gcd.py).

The report holds the facts in this order: the GCD, Bilanz and GuV, the Betriebsvermögensvergleich, the Anlagenspiegel,
the Kontensalden and the Überleitung. Its company is the Steuernummer of the master data; without one there is no
report, which gcd.check() explains. The checks of the profile run on it (steuerbote/xbrl/checks.py): the announced
components, the Mussfelder, the admissible positions, the previous year, the calculation linkbase, the Oberpositionen,
the Summenmussfelder and the contexts. Their findings join those of the parts, the codes of steuerbote/xbrl/checks.py
kept (steuerbote.ebilanz.positions.finding_of()). An instance the writer refuses is a finding as well.

An E-Bilanz is ready when it has a report and no finding blocks: an error holds it back from „Bereit“, a hint does not
(steuerbote/jahresmeldung/findings.py). annual_findings() gives its findings for the table „Befunde“ of the annual
document, each text with its source.

This module is pure Python with lxml and never imports Frappe.
"""

from dataclasses import dataclass, field

from lxml import etree

from steuerbote.ebilanz import gcd
from steuerbote.ebilanz.anlagenspiegel import Anlagenspiegel, Row, anlagenspiegel
from steuerbote.ebilanz.calculation import (
	AccountBalance,
	Adjustment,
	Betriebsvermoegensvergleich,
	Calculation,
	EquityChanges,
	betriebsvermoegensvergleich,
	calculate,
)
from steuerbote.ebilanz.gcd import MasterData
from steuerbote.ebilanz.kontennachweis import Kontennachweis, kontennachweis
from steuerbote.ebilanz.positions import Finding, Structure, finding_of
from steuerbote.ebilanz.ueberleitung import Transfer, Ueberleitung, ueberleitung
from steuerbote.jahresmeldung import findings as annual
from steuerbote.xbrl import writer
from steuerbote.xbrl.facts import Report
from steuerbote.xbrl.profiles import FISCAL
from steuerbote.xbrl.writer import WriterError

WRITER = "steuerbote/xbrl/writer.py; Technischer Leitfaden zur HGB-Taxonomie 6.9, B.14.13"
ELLIPSIS = "…"


class EBilanzError(ValueError):
	"""An E-Bilanz without an instance to write."""


@dataclass(frozen=True, slots=True)
class Sources:
	"""What the books and the settings give the E-Bilanz, as plain values.

	``balances`` are those of each account (steuerbote.ebilanz.calculation.AccountBalance), ``adjustments`` the
	corrections and lines by hand, ``assets`` the rows of the Anlagenspiegel, ``transfers`` the entries of the
	Überleitung of a Handelsbilanz, ``equity`` the changes of the equity the Betriebsvermögensvergleich needs,
	``first_year`` whether the fiscal year is the first of the company, and ``reason`` why a case without Kontensalden
	sends none.
	"""

	balances: tuple[AccountBalance, ...]
	adjustments: tuple[Adjustment, ...] = ()
	assets: tuple[Row, ...] = ()
	transfers: tuple[Transfer, ...] = ()
	equity: EquityChanges = field(default_factory=EquityChanges)
	first_year: bool = False
	reason: str = ""

	def __post_init__(self) -> None:
		for name in ("balances", "adjustments", "assets", "transfers"):
			object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True)
class EBilanz:
	"""The E-Bilanz of a case: its parts, its report and what was found on the way."""

	structure: Structure
	master: MasterData
	calculation: Calculation
	ueberleitung: Ueberleitung
	betriebsvermoegensvergleich: Betriebsvermoegensvergleich
	anlagenspiegel: Anlagenspiegel
	kontennachweis: Kontennachweis
	report: Report | None
	"""The facts of the instance, None without a company to name or where the writer refuses them."""
	findings: tuple[Finding, ...]

	@property
	def blocking(self) -> tuple[Finding, ...]:
		"""The findings that hold the E-Bilanz back from „Bereit“."""
		return tuple(finding for finding in self.findings if finding.blocking)

	@property
	def ready(self) -> bool:
		return self.report is not None and not self.blocking

	def instance(self) -> etree._Element:
		"""The instance, as the Nutzdaten of the ElsterXML take it (steuerbote/elster/ebilanz_xml.py)."""
		return writer.instance(self._report(), self.structure.taxonomy)

	def xml(self) -> bytes:
		"""The instance as a document of its own, as „XBRL exportieren“ gives it."""
		return writer.write(self._report(), self.structure.taxonomy)

	def annual_findings(self) -> tuple[annual.Finding, ...]:
		"""The findings for the table „Befunde“ of the annual document, each text with its source."""
		return tuple(
			annual.Finding(
				finding.code,
				finding.severity,
				f"{finding.text} (Quelle: {finding.source})",
				_shortened(finding.reference, annual.DATA_LENGTH),
			)
			for finding in self.findings
		)

	def _report(self) -> Report:
		if self.report is None:
			raise EBilanzError(
				"the E-Bilanz has no instance: "
				+ "; ".join(f"{finding.code} {finding.text}" for finding in self.blocking)
			)
		return self.report


def build(structure: Structure, master: MasterData, sources: Sources) -> EBilanz:
	"""The E-Bilanz of the structure from the master data and the sources, with every finding of its parts and of the
	checks of the profile FISCAL."""
	case = structure.case
	taxonomy = structure.taxonomy
	calculation = calculate(structure, sources.balances, sources.adjustments)
	transferred = ueberleitung(calculation, sources.transfers)
	comparison = betriebsvermoegensvergleich(structure, transferred.steuerbilanz, sources.equity)
	fixed_assets = anlagenspiegel(
		structure,
		sources.assets,
		handelsbilanz=calculation.amounts(),
		steuerbilanz=None if case.steuerbilanz else transferred.steuerbilanz,
		first_year=sources.first_year,
	)
	accounts = kontennachweis(calculation, reason=sources.reason)
	found: list[Finding] = [
		*calculation.findings,
		*transferred.findings,
		*comparison.findings,
		*fixed_assets.findings,
		*accounts.findings,
		*gcd.check(structure, master, reason=accounts.reason),
	]
	company = gcd.entity(master)
	report = None
	if company is not None:
		report = FISCAL.report(
			taxonomy,
			company,
			case.periods,
			(
				*gcd.facts(structure, master, reason=accounts.reason),
				*calculation.facts(),
				*comparison.facts(),
				*fixed_assets.facts(),
				*accounts.facts(),
				*transferred.facts(),
			),
		)
		try:
			found.extend(finding_of(finding) for finding in FISCAL.check(report, taxonomy))
		except WriterError as error:
			found.append(
				Finding("EB-INSTANZ", f"Die XBRL-Instanz lässt sich so nicht schreiben: {error}.", WRITER)
			)
			report = None
	return EBilanz(
		structure,
		master,
		calculation,
		transferred,
		comparison,
		fixed_assets,
		accounts,
		report,
		tuple(found),
	)


def _shortened(text: str, length: int) -> str:
	return text if len(text) <= length else text[: length - len(ELLIPSIS)] + ELLIPSIS
