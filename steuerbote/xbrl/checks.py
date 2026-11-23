"""The checks of a report against its view, which ERiC and the Unternehmensregister apply beyond XBRL itself.

The writer refuses what XBRL or the view cannot take (steuerbote/xbrl/writer.py). These checks find what a valid
instance may still hold wrongly, each as a Finding with a German sentence for the person who files the report, its
source and the position, period and members it is about. Every finding is an error, since ERiC rejects such a
Datensatz (ERiC E-Bilanz-Dokumentation für HGB-Taxonomie 6.9, ERiC 44.3.6.0, Kap. 3). The sources are the Technischer
Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025 („Leitfaden“) and that documentation.

Facets. What a report announces in its GCD, read from the facts as ERiC reads them (Kap. 3.2 to 3.5): the legal
status, the GuV format, the Bilanzierungsstandard, the Bilanzart, the Fertigstellungsstatus and the announced
Berichtsbestandteile. A choice holds its value as an empty string, the others as NIL (Leitfaden B.14.1). The kinds of
legal form of a legal status are those its references in the taxonomy carry, the table of B.4.1: „Gesellschaft mit
beschränkter Haftung ... KST“. A Steuerbilanz is one of „deutsches Steuerrecht“ (AO) or „deutsches Handelsrecht (sog.
Einheitsbilanz)“ (HAOE), a Handelsbilanz one of HGBM (B.13).

Components. Each Berichtsbestandteil is the presentation network of a role, the Anlagenspiegel only its hypercube and
the Überleitung only the positions „hbst.transfer...“ (B.9.3, B.9.4). „Es ist sicherzustellen, dass zu den ...
angekündigten Berichtsbestandteilen auch tatsächlich werthaltige Angaben (ungleich „NIL") für das aktuelle
Wirtschaftsjahr übermittelt werden ... Wird ein Berichtsbestandteil nicht angekündigt, dürfen dazu keine Angaben
übermittelt werden (auch nicht „NIL“).“ (B.9.2)

Mussfelder. Every Mussfeld and Summenmussfeld of the GCD, and for a final Jahresabschluss or Eröffnungsbilanz those of
the announced components, that is transmittable in the fiscal year, for the legal form, the GuV format and the
purposes of the report (B.14.2.1, B.14.2.2, B.14.4), is reported for the current year, „leer“ (NIL) where the books
cannot fill it (B.14.2.3); a part of a tuple inside its tuple. The rows of a table count for each combination of
members that has a value (B.14.12.1 a), which only the component knows, so required() leaves them to it.

Admissibility. Every fact, inside tuples as well (B.14.6): a position the view presents, „Es dürfen nur solche
Positionen übermittelt werden, die in dem Presentation Network erfasst sind“ (B.11), and valid in the fiscal year
(B.14.4.1); of the legal form, even NIL (B.4.2; ERiC Kap. 3.6); of the GuV format (B.14.3.1.15); not marked
„notPermittedFor“ for a purpose of the report: „Einreichung an Finanzverwaltung“ always (B.14.6), „steuerlich“ in a
Steuerbilanz (ERiC Kap. 3.6), „handelsrechtlich“ where the Offenlegung asks for it. A position marked
„onlyPermittedForSoBil_ErgBil“, or a part of a tuple so marked, has a value only in a Sonder- or Ergänzungsbilanz
(A.9.3; ERiC Kap. 3.6), which a GmbH never files: elsewhere it is NIL, as the Mussfelder among them are in the GmbH
example of the ERiC documentation 44.3.6.0 (HandelsbilanzLandwirt_GmbH.xml).

Previous year. „Steuerbilanzen dürfen keine Vorjahresangaben ... beinhalten“, nor the Überleitung of a Handelsbilanz
(B.8.3), nor an Eröffnungsbilanz (ERiC Kap. 3.13).

Calculation. „Der Datensatz ist nach den Vorgaben der Calculation Linkbase daraufhin zu prüfen, dass er rechnerisch
korrekt ist ... Mit „NIL“ übermittelte „leere“ Mussfelder sind in die Berechnungen nicht einzubeziehen.“ (B.14.11) A
total is checked in each context where it has a value and at least one of its items has one, as XBRL 2.1 binds a
calculation (Kap. 5.2.5.2). The rows of a table add up along the Bilanz as well: „Als Grundlage dienen die
übereinstimmenden Positionshierarchien der Berichtsteile „Bilanz“ und „Anhang“.“ (B.14.12.1 b)

Oberpositionen. In the components of B.14.10, „zu jeder angegebenen Position [müssen] auch sämtliche Oberpositionen
aufgeführt werden ... Ist eine Unterposition werthaltig angegeben, so sind auch ihre Oberpositionen werthaltig zu
berichten“, for the current year in each scenario; in the Anhang only the positions of a hypercube (ERiC Kap. 3.9),
whose rows follow the Bilanz too (B.14.12.1 b). Abstract titles are no positions to report.

Summenmussfelder. „Wird eine als Summenmussfeld ausgezeichnete Position ... werthaltig und ungleich 0 berichtet, so ist
mindestens eine ihrer rechnerisch verknüpften Unterpositionen werthaltig zu übermitteln.“, except „Nicht durch
Eigenkapital gedeckter Fehlbetrag“ and „Eigenkapital“ with the positions below them, but for the „steuerlicher
Ausgleichsposten“ (B.14.14).

Contexts. On the written instance: „Jeder der im eingereichten Datensatz spezifizierten Kontexte muss von mindestens
einem Fakt referenziert werden.“, and one entity in all of them (B.14.7).

This module is pure Python with lxml and never imports Frappe.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, StrEnum

from lxml import etree

from steuerbote.xbrl.facts import Fact, Item, Period, Periods, Report, Tuple
from steuerbote.xbrl.taxonomy import (
	APPROPRIATION_PROFITS,
	BALANCE_SHEET,
	DETAILED_INFORMATION,
	GCD,
	INCOME_STATEMENT,
	INCOME_STATEMENT_MICROBILG,
	NOT_PERMITTED_FISCAL,
	NOT_PERMITTED_SUBMISSION,
	NOTES,
	ROLE,
	TRANSFERS_COMMERCIAL_CODE_TO_TAX,
	TRANSFERS_TAX_ASSETS,
	Concept,
	IncomeStatementFormat,
	Kind,
	LegalForm,
	Requirement,
	Taxonomy,
)

XBRLI = "{http://www.xbrl.org/2003/instance}"
NOTES_BELOW_BALANCE_SHEET = f"{ROLE}notesBelowBalanceSheet"
CHANGES_EQUITY_ACCOUNTS = f"{ROLE}changesEquityAccounts"
REPORT_ELEMENT = "de-gcd:genInfo.report.id.reportElement"
LEGAL_STATUS = "de-gcd:genInfo.company.id.legalStatus"
FIXED_ASSETS_CUBES = frozenset({"de-gaap-ci:cube_.nt.ass.gross", "de-gaap-ci:cube_.nt.ass.gross_short"})
TRANSFER = "de-gaap-ci:hbst.transfer"
STEUERBILANZ_STANDARDS = frozenset({"AO", "HAOE"})
"""„Steuerbilanz, wenn „deutsches Steuerrecht“ ... Auch als Steuerbilanz behandelt wird: „deutsches Handelsrecht (sog.
Einheitsbilanz)““ (Leitfaden B.13)."""
FINAL_STATEMENT_TYPES = frozenset({"E", "UBandE", "AB", "LSB", "EB"})
"""The Bilanzarten whose GAAP Mussfelder count when the report is „endgültig“ (Leitfaden B.14.2.2)."""
OBERPOSITION_ROLES = (
	BALANCE_SHEET,
	INCOME_STATEMENT,
	INCOME_STATEMENT_MICROBILG,
	APPROPRIATION_PROFITS,
	CHANGES_EQUITY_ACCOUNTS,
	NOTES,
	f"{ROLE}adjustmentOfIncome",
	f"{ROLE}determinationOfTaxableIncome",
	f"{ROLE}determinationOfTaxableIncomeBusinessPartnership",
	TRANSFERS_TAX_ASSETS,
)
"""The presentation networks of the components whose Oberpositionen are checked (Leitfaden B.14.10.1 to B.14.10.9)."""
SUMMENMUSSFELD_ROLES = (
	BALANCE_SHEET,
	INCOME_STATEMENT,
	INCOME_STATEMENT_MICROBILG,
	CHANGES_EQUITY_ACCOUNTS,
	f"{ROLE}determinationOfTaxableIncome",
	f"{ROLE}determinationOfTaxableIncomeBusinessPartnership",
	TRANSFERS_TAX_ASSETS,
	NOTES,
)
"""The calculation networks of the components of Leitfaden B.14.14, the Anlagenspiegel with its value development."""
SUMMENMUSSFELD_EXEMPT = ("de-gaap-ci:bs.ass.deficitNotCoveredByCapital", "de-gaap-ci:bs.eqLiab.equity")
SUMMENMUSSFELD_CHECKED = frozenset({"de-gaap-ci:bs.eqLiab.equity.netIncome.taxBalanceGenerally"})


class Severity(Enum):
	ERROR = "Fehler"
	HINT = "Hinweis"


class Code(StrEnum):
	COMPONENT = "XBRL-BERICHTSBESTANDTEIL"
	MUSSFELD = "XBRL-MUSSFELD"
	LEGAL_FORM = "XBRL-RECHTSFORM"
	INCOME_STATEMENT_FORMAT = "XBRL-GUV-FORMAT"
	NOT_PERMITTED = "XBRL-UNZULAESSIG"
	NOT_TRANSMITTABLE = "XBRL-NICHT-UEBERMITTELBAR"
	SPECIAL_BALANCE = "XBRL-SONDERBILANZ"
	PRIOR_YEAR = "XBRL-VORJAHR"
	CALCULATION = "XBRL-RECHNUNG"
	OBERPOSITION = "XBRL-OBERPOSITION"
	SUMMENMUSSFELD = "XBRL-SUMMENMUSSFELD"
	CONTEXT = "XBRL-KONTEXT"
	ENTITY = "XBRL-UNTERNEHMEN"


@dataclass(frozen=True, slots=True)
class Finding:
	"""What a check found: a German sentence with its source, and the position, period and members it is about."""

	code: Code
	text: str
	source: str
	concept: str = ""
	period: Period | None = None
	dimensions: tuple[tuple[str, str], ...] = ()
	severity: Severity = Severity.ERROR

	@property
	def blocking(self) -> bool:
		return self.severity is Severity.ERROR


@dataclass(frozen=True, slots=True)
class Component:
	"""A Berichtsbestandteil: its value of genInfo.report.id.reportElement and the presentation network that holds
	its positions (Leitfaden B.9.3, B.9.4)."""

	code: str
	role: str
	label: str
	hypercubes: frozenset[str] = frozenset()
	"""Only the positions of one of these tables."""
	excluded: frozenset[str] = frozenset()
	"""No position of these tables, and none of these positions."""
	prefix: str = ""
	"""Only the positions whose name begins so."""

	@property
	def value(self) -> str:
		"""The value of genInfo.report.id.reportElement that announces the component."""
		return f"{REPORT_ELEMENT}.reportElements.{self.code}"

	def holds(self, taxonomy: Taxonomy, concept: str) -> bool:
		network = taxonomy.presentation.get(self.role)
		if network is None or concept not in network or not concept.startswith(self.prefix):
			return False
		tables = {table.hypercube for table in taxonomy.tables_of(concept)}
		if self.hypercubes and not tables & self.hypercubes:
			return False
		return not tables & self.excluded and concept not in self.excluded


BILANZ = Component("B", BALANCE_SHEET, "Bilanz")
EROEFFNUNGSBILANZ = Component("EB", BALANCE_SHEET, "Eröffnungsbilanz ohne GuV")
GUV = Component("GuV", INCOME_STATEMENT, "GuV")
GUV_MICROBILG = Component("GuVMicroBilG", INCOME_STATEMENT_MICROBILG, "GuV nach MicroBilG")
BETRIEBSVERMOEGENSVERGLEICH = Component(
	"BVV", TRANSFERS_TAX_ASSETS, "Steuerlicher Betriebsvermögensvergleich"
)
ANLAGENSPIEGEL = Component(
	"BAL", NOTES, "Anlagenspiegel (brutto)", hypercubes=frozenset({"de-gaap-ci:cube_.nt.ass.gross"})
)
KONTENNACHWEIS = Component("KS", DETAILED_INFORMATION, "Kontensalden zu einer oder mehrerer Positionen")
UEBERLEITUNG = Component(
	"STU", TRANSFERS_COMMERCIAL_CODE_TO_TAX, "steuerliche Überleitungsrechnung", prefix=TRANSFER
)
ERGEBNISVERWENDUNG = Component("EV", APPROPRIATION_PROFITS, "Ergebnisverwendung")
ANGABEN_UNTER_DER_BILANZ = Component("H", NOTES_BELOW_BALANCE_SHEET, "Angaben unterhalb der Bilanz")
ANHANG = Component(
	"SA", NOTES, "andere Anhangangaben", excluded=FIXED_ASSETS_CUBES | frozenset({"de-gaap-ci:nt.reg"})
)
COMPONENTS = (
	BILANZ,
	EROEFFNUNGSBILANZ,
	GUV,
	GUV_MICROBILG,
	BETRIEBSVERMOEGENSVERGLEICH,
	ANLAGENSPIEGEL,
	KONTENNACHWEIS,
	UEBERLEITUNG,
	ERGEBNISVERWENDUNG,
	ANGABEN_UNTER_DER_BILANZ,
	ANHANG,
)
"""The components Steuerbote knows, in the order of Leitfaden B.9.4 and B.9.3."""

_FACETS = {
	"legal_status": LEGAL_STATUS,
	"income_statement_format": "de-gcd:genInfo.report.id.incomeStatementFormat",
	"accounting_standard": "de-gcd:genInfo.report.id.accountingStandard",
	"statement_type": "de-gcd:genInfo.report.id.statementType",
	"report_status": "de-gcd:genInfo.report.id.reportStatus",
}


@dataclass(frozen=True, slots=True)
class Facets:
	"""What the GCD of a report announces, each choice by the code of its value, such as GMBH or GKV."""

	legal_status: str | None = None
	income_statement_format: str | None = None
	accounting_standard: str | None = None
	statement_type: str | None = None
	report_status: str | None = None
	components: frozenset[str] = field(default_factory=frozenset)

	@classmethod
	def of(cls, report: Report) -> Facets:
		chosen: dict[str, list[str]] = {}
		for fact, _ in report.tuples():
			chosen.setdefault(fact.concept, []).extend(
				_code(fact.concept, child.concept)
				for child in fact.children
				if isinstance(child, Item) and child.value is not None
			)
		return cls(
			**{name: next(iter(chosen.get(concept, ())), None) for name, concept in _FACETS.items()},
			components=frozenset(chosen.get(REPORT_ELEMENT, ())),
		)

	@property
	def format(self) -> IncomeStatementFormat | None:
		try:
			return IncomeStatementFormat(self.income_statement_format)
		except ValueError:
			return None

	@property
	def steuerbilanz(self) -> bool:
		return self.accounting_standard in STEUERBILANZ_STANDARDS

	@property
	def final(self) -> bool:
		return self.statement_type in FINAL_STATEMENT_TYPES and self.report_status == "E"

	@property
	def opening(self) -> bool:
		return self.statement_type == "EB"

	@property
	def purposes(self) -> tuple[str, ...]:
		"""The purposes whose „notPermittedFor“ the report keeps to: the Finanzverwaltung, and a Steuerbilanz."""
		return (NOT_PERMITTED_SUBMISSION, *((NOT_PERMITTED_FISCAL,) if self.steuerbilanz else ()))


def legal_forms(taxonomy: Taxonomy, facets: Facets) -> frozenset[LegalForm]:
	"""The kinds of legal form of the legal status, as its value carries them (Leitfaden B.4.1); none if unknown."""
	for part in taxonomy.parts(LEGAL_STATUS):
		if _code(LEGAL_STATUS, part) == facets.legal_status:
			return taxonomy.concepts[part].fiscal.legal_forms
	return frozenset()


def required(taxonomy: Taxonomy, facets: Facets, periods: Periods) -> tuple[str, ...]:
	"""The Mussfelder and Summenmussfelder of the report, in the order of the GCD and the components."""
	forms = legal_forms(taxonomy, facets)
	networks: list[tuple[str, Component | None]] = [(GCD, None)]
	if facets.final:
		networks += [
			(component.role, component) for component in COMPONENTS if component.code in facets.components
		]
	found: dict[str, None] = {}
	for role, component in networks:
		network = taxonomy.presentation.get(role)
		for name, _ in network.walk() if network is not None else ():
			concept = taxonomy.concepts[name]
			if (
				(component is None or component.holds(taxonomy, name))
				and concept.kind in (Kind.ITEM, Kind.TUPLE)
				and not concept.abstract
				and concept.required_for(
					periods.fiscal_year_begin, periods.balance_sheet_date or periods.fiscal_year_end
				)
				and _applies(concept, forms)
				and _suits(concept, facets.format)
				and all(concept.permitted_for(purpose) for purpose in facets.purposes)
				and not taxonomy.tables_of(name)
			):
				found[name] = None
	return tuple(found)


def components(report: Report, taxonomy: Taxonomy, facets: Facets) -> tuple[Finding, ...]:
	"""A value for each announced component and no fact of another (Leitfaden B.9.2)."""
	source = _source(taxonomy, "B.9.2")
	findings = [
		Finding(
			Code.COMPONENT,
			f"Der Berichtsbestandteil „{component.label}“ ist angekündigt, hat aber keine werthaltige Angabe für das "
			"Wirtschaftsjahr.",
			source,
			component.value,
		)
		for component in COMPONENTS
		if component.code in facets.components
		and not any(
			item.value is not None and not item.period.prior and component.holds(taxonomy, item.concept)
			for item, _ in report.items()
		)
	]

	def unannounced(facts: Iterable[Fact]) -> Iterator[Finding]:
		for fact in facts:
			holders = [component for component in COMPONENTS if component.holds(taxonomy, fact.concept)]
			if holders and not any(component.code in facets.components for component in holders):
				yield Finding(
					Code.COMPONENT,
					f"„{taxonomy.label(fact.concept)}“ gehört zum Berichtsbestandteil „{holders[0].label}“, der nicht "
					"angekündigt ist.",
					source,
					*_where(fact),
				)
			elif isinstance(fact, Tuple):
				yield from unannounced(fact.children)

	return (*findings, *unannounced(report.facts))


def mussfelder(report: Report, taxonomy: Taxonomy, facets: Facets) -> tuple[Finding, ...]:
	"""Each Mussfeld of required() reported for the current year (Leitfaden B.14.2)."""
	items = {item.concept for item, _ in report.items() if not item.period.prior and not item.dimensions}
	tuples = {fact.concept for fact, _ in report.tuples()}
	findings = []
	for name in required(taxonomy, facets, report.periods):
		concept = taxonomy.concepts[name]
		if name in (tuples if concept.kind is Kind.TUPLE else items):
			continue
		kind = "Summenmussfeld" if concept.fiscal.requirement is Requirement.SUMMENMUSSFELD else "Mussfeld"
		findings.append(
			Finding(
				Code.MUSSFELD,
				f"Das {kind} „{taxonomy.label(name)}“ fehlt. Lässt es sich aus der Buchführung nicht belegen, wird es "
				"leer (NIL) übermittelt.",
				_source(taxonomy, "B.14.2 und B.14.2.3"),
				name,
				_current(concept),
			)
		)
	return tuple(findings)


def admissibility(
	report: Report, taxonomy: Taxonomy, facets: Facets, purposes: Iterable[str] | None = None
) -> tuple[Finding, ...]:
	"""Every fact transmittable, valid, of the legal form and GuV format, and permitted for the purposes, by default
	those of the facets."""
	forms = legal_forms(taxonomy, facets)
	purposes = facets.purposes if purposes is None else tuple(purposes)
	begin = report.periods.fiscal_year_begin
	closing = report.periods.balance_sheet_date or report.periods.fiscal_year_end
	findings = []
	for fact in _facts(report.facts):
		label = taxonomy.label(fact.concept)
		concept = taxonomy.concepts.get(fact.concept)
		if concept is None or not taxonomy.presented(fact.concept):
			findings.append(
				Finding(
					Code.NOT_TRANSMITTABLE,
					f"„{label}“ steht in keinem Berichtsbestandteil der Taxonomie und ist nicht übermittelbar.",
					_source(taxonomy, "B.11"),
					*_where(fact),
				)
			)
			continue
		if not concept.valid_for(begin, closing):
			findings.append(
				Finding(
					Code.NOT_TRANSMITTABLE,
					f"„{label}“ gilt im Wirtschaftsjahr nicht und ist nicht übermittelbar.",
					_source(taxonomy, "B.14.4.1"),
					*_where(fact),
				)
			)
		if not _applies(concept, forms):
			findings.append(
				Finding(
					Code.LEGAL_FORM,
					f"„{label}“ ist keine Position der Rechtsform des Unternehmens und wird nicht übermittelt, auch nicht "
					"leer.",
					_source(taxonomy, "B.4.2"),
					*_where(fact),
				)
			)
		if not _suits(concept, facets.format):
			findings.append(
				Finding(
					Code.INCOME_STATEMENT_FORMAT,
					f"„{label}“ gehört zum anderen GuV-Format und wird nicht übermittelt.",
					_source(taxonomy, "B.14.3.1.15"),
					*_where(fact),
				)
			)
		findings.extend(
			Finding(
				Code.NOT_PERMITTED,
				f"„{label}“ ist für „{purpose}“ nicht zulässig (notPermittedFor).",
				_source(taxonomy, "B.14.6"),
				*_where(fact),
			)
			for purpose in purposes
			if not concept.permitted_for(purpose)
		)
	findings.extend(
		Finding(
			Code.SPECIAL_BALANCE,
			f"„{taxonomy.label(item.concept)}“ hat nur in einer Sonder- oder Ergänzungsbilanz einen Wert und wird sonst "
			"leer (NIL) übermittelt.",
			f"{_source(taxonomy, 'A.9.3')}; ERiC E-Bilanz-Dokumentation, Kap. 3.6",
			*_where(item),
		)
		for item, ancestors in report.items()
		if item.value is not None and _special_balance_only(taxonomy, (*ancestors, item))
	)
	return tuple(findings)


def prior_year(report: Report, taxonomy: Taxonomy, facets: Facets) -> tuple[Finding, ...]:
	"""No previous year in a Steuerbilanz or an Eröffnungsbilanz, nor in the Überleitung (Leitfaden B.8.3)."""
	findings = []
	for item, ancestors in report.items():
		if not item.period.prior:
			continue
		if facets.steuerbilanz or facets.opening:
			text = "eine Steuerbilanz und eine Eröffnungsbilanz enthalten keine Vorjahresangaben"
		elif any(fact.concept.startswith(TRANSFER) for fact in (*ancestors, item)):
			text = "die Überleitungsrechnung enthält keine Vorjahresangaben"
		else:
			continue
		findings.append(
			Finding(
				Code.PRIOR_YEAR,
				f"„{taxonomy.label(item.concept)}“ bezieht sich auf das Vorjahr; {text}.",
				f"{_source(taxonomy, 'B.8.3')}; ERiC E-Bilanz-Dokumentation, Kap. 3.13",
				*_where(item),
			)
		)
	return tuple(findings)


def calculation(report: Report, taxonomy: Taxonomy) -> tuple[Finding, ...]:
	"""Each total the sum of its items in its context (Leitfaden B.14.11), and each row of a table the sum of the rows
	of the positions below it in the Bilanz (B.14.12.1 b)."""
	values = _amounts(report)
	findings: dict[tuple, Finding] = {}
	for network in taxonomy.calculation.values():
		for (concept, period, dimensions), value in values.items():
			arcs = network.children(concept)
			found = [
				(arc.weight or 1) * values[key]
				for arc in arcs
				if (key := (arc.child, period, dimensions)) in values
			]
			if found:
				_add_sum(findings, taxonomy, concept, period, dimensions, value, sum(found), "B.14.11")
	balance_sheet = taxonomy.calculation.get(BALANCE_SHEET)
	for (concept, period, dimensions), value in values.items() if balance_sheet is not None else ():
		for dimension, member in dimensions:
			members = _members(taxonomy, concept, dimension)
			found = [
				(arc.weight or 1) * values[key]
				for arc in balance_sheet.children(member)
				if arc.child in members
				and (key := (concept, period, _with(dimensions, dimension, arc.child))) in values
			]
			if found:
				_add_sum(findings, taxonomy, concept, period, dimensions, value, sum(found), "B.14.12.1 b")
	return tuple(findings.values())


def oberpositionen(report: Report, taxonomy: Taxonomy) -> tuple[Finding, ...]:
	"""The Oberpositionen of each position of the current year in its scenario (Leitfaden B.14.10, B.14.12.1 b)."""
	reported = {
		(item.concept, item.period, item.dimensions): item.value is not None
		for item, ancestors in report.items()
		if not ancestors
	}
	findings: dict[tuple, Finding] = {}
	balance_sheet = taxonomy.presentation.get(BALANCE_SHEET)
	for item, ancestors in report.items():
		if ancestors or item.period.prior:
			continue
		expected: list[tuple[str, tuple[tuple[str, str], ...]]] = []
		for role in OBERPOSITION_ROLES:
			network = taxonomy.presentation.get(role)
			if (
				network is None
				or item.concept not in network
				or (role == NOTES and not taxonomy.tables_of(item.concept))
			):
				continue
			expected += [
				(parent, item.dimensions)
				for parent in _ancestors(network, item.concept)
				if not taxonomy.concepts[parent].abstract
			]
		for dimension, member in item.dimensions if balance_sheet is not None else ():
			members = _members(taxonomy, item.concept, dimension)
			expected += [
				(item.concept, _with(item.dimensions, dimension, parent))
				for parent in _ancestors(balance_sheet, member)
				if parent in members
			]
		for parent, dimensions in expected:
			key = (parent, item.period, dimensions)
			if key in findings or reported.get(key, False) or (key in reported and item.value is None):
				continue
			child, above = taxonomy.label(item.concept), taxonomy.label(parent)
			text = (
				f"„{above}“ ist leer, obwohl „{child}“ darunter einen Wert hat; die Oberposition wird mit ihrem Wert "
				"übermittelt."
				if key in reported
				else f"Zu „{child}“ fehlt die Oberposition „{above}“; sie wird übermittelt, leer (NIL), wenn alle "
				"Positionen darunter leer sind."
			)
			findings[key] = Finding(
				Code.OBERPOSITION, text, _source(taxonomy, "B.14.10"), parent, item.period, dimensions
			)
	return tuple(findings.values())


def summenmussfelder(report: Report, taxonomy: Taxonomy) -> tuple[Finding, ...]:
	"""A valued Summenmussfeld other than 0 with at least one valued item (Leitfaden B.14.14)."""
	values = {
		(item.concept, item.period, item.dimensions): item.value
		for item, ancestors in report.items()
		if not ancestors and item.value is not None
	}
	networks = [taxonomy.calculation[role] for role in SUMMENMUSSFELD_ROLES if role in taxonomy.calculation]
	balance_sheet = taxonomy.calculation.get(BALANCE_SHEET)
	findings: dict[tuple, Finding] = {}
	for (concept, period, dimensions), value in values.items():
		if period.prior or value == 0:
			continue
		alternatives: list[list[tuple]] = []
		if taxonomy.concepts[concept].fiscal.requirement is Requirement.SUMMENMUSSFELD and not _exempt(
			taxonomy, concept
		):
			alternatives.append(
				[(arc.child, period, dimensions) for network in networks for arc in network.children(concept)]
			)
		for dimension, member in dimensions if balance_sheet is not None else ():
			if taxonomy.concepts[member].fiscal.requirement is Requirement.SUMMENMUSSFELD:
				members = _members(taxonomy, concept, dimension)
				alternatives.append(
					[
						(concept, period, _with(dimensions, dimension, arc.child))
						for arc in balance_sheet.children(member)
						if arc.child in members
					]
				)
		for keys in alternatives:
			if keys and not any(key in values for key in keys):
				findings[(concept, period, dimensions)] = Finding(
					Code.SUMMENMUSSFELD,
					f"Das Summenmussfeld „{taxonomy.label(concept)}“ hat einen Wert, aber keine der Positionen darunter.",
					_source(taxonomy, "B.14.14"),
					concept,
					period,
					dimensions,
				)
	return tuple(findings.values())


def contexts(instance: etree._Element) -> tuple[Finding, ...]:
	"""Every context of the instance referenced by a fact, with one entity in all of them (Leitfaden B.14.7)."""
	referenced = {element.get("contextRef") for element in instance.iter() if element.get("contextRef")}
	findings = [
		Finding(
			Code.CONTEXT,
			f"Der Kontext {context.get('id')} wird von keiner Angabe verwendet.",
			"Technischer Leitfaden zur HGB-Taxonomie, B.14.7",
		)
		for context in instance.iter(f"{XBRLI}context")
		if context.get("id") not in referenced
	]
	entities = dict.fromkeys(
		(identifier.get("scheme"), identifier.text) for identifier in instance.iter(f"{XBRLI}identifier")
	)
	if len(entities) > 1:
		findings.append(
			Finding(
				Code.ENTITY,
				"Die Kontexte nennen mehr als ein Unternehmen: "
				+ ", ".join(f"{identifier} ({scheme})" for scheme, identifier in entities)
				+ ".",
				"Technischer Leitfaden zur HGB-Taxonomie, B.14.7",
			)
		)
	return tuple(findings)


def _code(choice: str, value: str) -> str:
	"""The code of a value of a choice, such as GMBH of genInfo.company.id.legalStatus.legalStatus.GMBH."""
	return value.removeprefix(f"{choice}.").partition(".")[2]


def _source(taxonomy: Taxonomy, sections: str) -> str:
	return f"Technischer Leitfaden zur HGB-Taxonomie {taxonomy.version}, {sections}"


def _applies(concept: Concept, forms: frozenset[LegalForm]) -> bool:
	"""Whether the position is of one of the kinds of the legal form, „Ausnahme: Bei Rechtsformen, die neben der
	Ausprägung „PG“ auch andere Rechtsformausprägungen enthalten, dürfen zusätzlich auch Positionen übermittelt werden,
	die diesen zusätzlichen Rechtsformausprägungen entsprechen.“ (Leitfaden B.4.2); any position without a legal
	status to tell."""
	return not forms or any(concept.applies_to(form) for form in forms)


def _suits(concept: Concept, income_statement_format: IncomeStatementFormat | None) -> bool:
	return income_statement_format is None or concept.suits(income_statement_format)


def _current(concept: Concept) -> Period | None:
	if concept.kind is Kind.TUPLE:
		return None
	return Period.STICHTAG if concept.period_type == "instant" else Period.WIRTSCHAFTSJAHR


def _where(fact: Fact) -> tuple[str, Period | None, tuple[tuple[str, str], ...]]:
	if isinstance(fact, Item):
		return fact.concept, fact.period, fact.dimensions
	return fact.concept, None, ()


def _facts(facts: Iterable[Fact]) -> Iterator[Fact]:
	for fact in facts:
		yield fact
		if isinstance(fact, Tuple):
			yield from _facts(fact.children)


def _amounts(report: Report) -> dict[tuple[str, Period, tuple[tuple[str, str], ...]], Decimal]:
	"""The amounts of the items outside tuples by position, period and members; NIL is no amount."""
	return {
		(item.concept, item.period, item.dimensions): item.value
		for item, ancestors in report.items()
		if not ancestors and isinstance(item.value, Decimal)
	}


def _add_sum(
	findings: dict[tuple, Finding],
	taxonomy: Taxonomy,
	concept: str,
	period: Period,
	dimensions: tuple[tuple[str, str], ...],
	value: Decimal,
	total: Decimal,
	section: str,
) -> None:
	if value == total or (concept, period, dimensions) in findings:
		return
	findings[(concept, period, dimensions)] = Finding(
		Code.CALCULATION,
		f"„{taxonomy.label(concept)}“ hat {_euro(value)}, die Positionen darunter ergeben {_euro(total)}.",
		_source(taxonomy, section),
		concept,
		period,
		dimensions,
	)


def _members(taxonomy: Taxonomy, concept: str, dimension: str) -> frozenset[str]:
	"""The members of a dimension of the tables of a position."""
	return frozenset(
		member
		for table in taxonomy.tables_of(concept)
		for candidate in table.dimensions
		if candidate.name == dimension
		for member in candidate.members
	)


def _with(
	dimensions: tuple[tuple[str, str], ...], dimension: str, member: str
) -> tuple[tuple[str, str], ...]:
	return tuple((name, member if name == dimension else value) for name, value in dimensions)


def _ancestors(network, name: str) -> tuple[str, ...]:
	"""Every position above one in a network, nearest first, along each of its parents."""
	found: dict[str, None] = {}
	current = [name]
	while current:
		parents = [
			arc.parent for child in current for arc in network.parents(child) if arc.parent not in found
		]
		found.update(dict.fromkeys(parents))
		current = parents
	return tuple(found)


def _exempt(taxonomy: Taxonomy, concept: str) -> bool:
	"""Whether the Summenmussfeld check leaves the position out (Leitfaden B.14.14)."""
	if concept in SUMMENMUSSFELD_CHECKED:
		return False
	network = taxonomy.presentation.get(BALANCE_SHEET)
	above = _ancestors(network, concept) if network is not None else ()
	return any(name in SUMMENMUSSFELD_EXEMPT for name in (concept, *above))


def _special_balance_only(taxonomy: Taxonomy, facts: Iterable[Fact]) -> bool:
	"""Whether a fact or a tuple around it is a position of a Sonder- or Ergänzungsbilanz only."""
	return any(
		concept is not None and concept.fiscal.special_balance_only
		for concept in (taxonomy.concepts.get(fact.concept) for fact in facts)
	)


def _euro(value: Decimal) -> str:
	"""An amount as the German text writes it, such as 1.234,56 €."""
	return f"{value:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".") + " €"
