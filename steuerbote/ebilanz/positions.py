"""What the E-Bilanz of a GmbH or UG reports for its case: the components, the positions with their marks, the
Mussfelder it sends and those it must not send, and the rows and columns of the Anlagenspiegel.

Sources are the Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025 („Leitfaden“), the BMF letters on the
E-Bilanz and the Jahresdokumentation_Bilanz_Taxonomie_6_9.ods of the ERiC documentation 44.3.6.0, sheet „Kontext -
Regeln“, cited by the Fehlercode of a rule.

Case. A GmbH or UG (steuerbote/steuerbote/doctype/annual_filing_settings/rules.py: legal_form(), legal_status(),
genInfo.company.id.legalStatus GMBH or UG, a Rechtsform of the kind „KSt“, Leitfaden B.4.1) reports its GuV in the
Gesamtkostenverfahren, Steuerbote's only GuV-Format („GKV only“, decision of the build contract of stage 3, 3.2).
Its Bilanzierungsstandard says what the Bilanz is: „Handelsbilanz, wenn „deutsches Handelsrecht“ [HGBM] ... Steuerbilanz,
wenn „deutsches Steuerrecht“ [AO]. Auch als Steuerbilanz behandelt wird: „deutsches Handelsrecht (sog.
Einheitsbilanz)“ [HAOE]“ (B.13), HAOE by default. Its Bilanzart is the Jahresabschluss, or the Eröffnungsbilanz of
the founding year, for which § 5b Abs. 1 Satz 4 EStG applies the duty „entsprechend“. The Bilanzstichtag of a
Jahresabschluss is the end of the fiscal year (rule 170205072), that of an Eröffnungsbilanz its beginning (170205081;
B.14.3.1.6). Only a Handelsbilanz may show the previous year: „Steuerbilanzen dürfen keine Vorjahresangaben ...
beinhalten“ (B.8.3).

Components. „Bei allen anderen Belegungen der Position „Bilanzart“ ... müssen zwingend die Ausprägungen „Bilanz“ ...
und „GuV“ ... werthaltig berichtet werden“, and with a GuV the „Steuerlicher Betriebsvermögensvergleich“ (B.14.3.1.10;
rules 170205090, 170205091, 170205066); an Eröffnungsbilanz has the Bilanz and neither GuV nor
Betriebsvermögensvergleich (170405021, 170205021, 170405101). The Anlagenspiegel (brutto) comes with every Bilanzart:
„Für Wirtschaftsjahre, die nach dem 31. Dezember 2016 beginnen, ist der „Anlagenspiegel (brutto)“ [table.nt.ass.gross]
zu übermitteln.“ (B.14.12.1); „Der Anlagenspiegel ist entsprechend des BMF-Schreibens vom 24. Mai 2016, BStBl I S. 500,
für Wirtschaftsjahre, die nach dem 31. Dezember 2016 beginnen, weiterhin als Mussfeld ausgestaltet und daher
verpflichtend zu übermitteln.“ (BMF letter of 10 June 2025, IV C 6 - S 2133-b/00064/002/006). The Jahresdokumentation
of 6.9 marks its rule 170405045 deleted (Änderungsinformation GELOESCHT), so ERiC 44.3.6.0 no longer checks that the
component is there; the duty stays. The Kontensalden come with every Bilanzart, for Bilanz and GuV: „Für
Wirtschaftsjahre, die nach dem 31. Dezember 2024 beginnen, ist der Inhalt der Bilanz und Gewinn- und Verlustrechnung
(GuV) jeweils einschließlich der unverdichteten Kontennachweise mit Kontensalden ... zu übermitteln.“ (BMF letter of 10
June 2025; § 5b Abs. 1 Satz 1 EStG), unless the case leaves them out with a reason (steuerbote/ebilanz/kontennachweis.py).
A Handelsbilanz adds the steuerliche Überleitungsrechnung, which a Steuerbilanz must not have (B.15.1, B.16.1; rules
170205100, 170205095). There is no Ergebnisverwendung: the Bilanz shows the Jahresüberschuss and no Bilanzgewinn (build
contract, 3.2: „GKV only, no EV“; B.9.1.2).

Positions. Each monetary position of the presentation network of the Bilanz, the GuV and the Betriebsvermögensvergleich
(B.9.4.1, B.9.4.2, B.9.3.12) that the case admits: valid in the fiscal year (B.14.4.1), of the legal form, „nur
Positionen mit der Auszeichnung „legalFormKSt“ = „true“ und Positionen, die keiner Rechtsform zugeordnet sind“ (B.4.2),
of the GKV (B.14.3.1.15), not marked „Einreichung an Finanzverwaltung“ (B.14.6) nor, in a Steuerbilanz, „steuerlich“
(B.16.2). A position of a Sonder- or Ergänzungsbilanz only stays, NIL: „Sofern sich eine Position ... mit
Mussfeld-Auszeichnung ... z.B. aufgrund der Rechtsform nicht mit Werten füllen lässt, so ist ... die entsprechende
Position „leer“ (technisch: NIL-Wert) zu übermitteln.“ (A.10.1), as in the GmbH example of the ERiC documentation
44.3.6.0; a value on one is a finding (A.9.3). Each has a mark:

- Mussfeld: „Die Übermittlung aller als „Mussfeld“ gekennzeichneten Positionen ist ... als Mindestumfang des amtlich
  vorgeschriebenen Datensatzes im Sinne des § 5b EStG erforderlich“, NIL where the books cannot fill it (A.10.1);
- Summenmussfeld: „Oberpositionen, die über rechnerisch verknüpften Mussfeldern stehen“ (A.10.3);
- Auffangposition, „erkennbar durch die Formulierungen im beschreibenden Text „nicht zuordenbar“ oder „ohne
  Zuordnung““, for a split the books cannot give (A.10.4);
- rechnerisch notwendig: „Diese Positionen sind dann zwingend mit Werten zu übermitteln, wenn ohne diese Übermittlung
  die Summe der Positionen auf der gleichen Ebene einer Rechenregel nicht dem Wert der Oberposition entspricht“ (A.10.3);
- davon: a position the calculation of its component leaves out, „davon-Positionen“ of the Anlage zu Rn. 11 of the BMF
  letter of 28 September 2011, BStBl I S. 855; its amount is part of the position above it.

Mussfelder. The Mussfelder and Summenmussfelder of the report are those of steuerbote.xbrl.checks.required() for the
GCD and the components the case announces (B.14.2). „Alle unzulässigen Mussfelder sind nicht, auch nicht mit
NIL-Wert, zu übermitteln“ (FAQ zur E-Bilanz, Version 2026-01, Tz. 4 a; BMF letter of 27 May 2024, BStBl I S. 928, from
taxonomy 6.9): refused names the Mussfelder of the components that the case does not admit, those of another legal
form above all. For a GmbH with the GKV in 2026, taxonomy 6.9 has 82 Mussfelder and 49 Summenmussfelder in the Bilanz,
155 and 59 in the GuV, 5 and 2 in the Betriebsvermögensvergleich and 52 in the GCD, and 13 and 4 per row of the
Anlagenspiegel (steuerbote/ebilanz/tests/test_real_taxonomy.py).

Anlagenspiegel. Its rows are the members of „Positionen des Anlagevermögens“ [dim_changes.nt.ass.gross] of the legal
form, „Der Anlagenspiegel darf keine Angaben zu rechtsformfremden Positionen ... enthalten“ (B.14.12.1 j), its columns
the monetary primary items of the value development under „Wertentwicklung“ [piTitle.nt.ass.gross], each with its mark
and its place in the calculation of the Anhang.

Findings. Every module of steuerbote/ebilanz reports a Finding: a code, a German sentence for the person who files
the E-Bilanz, its source, what it is about, and its severity; an error holds the E-Bilanz back from „Bereit“
(steuerbote/jahresmeldung/findings.py). The code is the Fehlercode of a rule of the Jahresdokumentation where one says
the same, else one of Steuerbote beginning with EB-. A finding of steuerbote/xbrl/checks.py keeps its code.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from steuerbote.steuerbote.doctype.annual_filing_settings.rules import legal_form, legal_status
from steuerbote.xbrl import checks
from steuerbote.xbrl.checks import Component, Facets, Severity
from steuerbote.xbrl.facts import Periods
from steuerbote.xbrl.taxonomy import (
	BALANCE_SHEET,
	FIXED_ASSETS_GROSS,
	INCOME_STATEMENT,
	NOTES,
	TRANSFERS_TAX_ASSETS,
	Balance,
	Concept,
	IncomeStatementFormat,
	Network,
	PeriodType,
	Requirement,
	Taxonomy,
)

GAAP = "de-gaap-ci"
GKV = IncomeStatementFormat.GKV
FINAL = "E"
"""„endgültig“: „Ein Datensatz mit dem „Fertigstellungsstatus des Berichts“ ... „vorläufig“ ... stellt weder eine
fristwahrende Übersendung dar, noch erfüllt er eine Abgabeverpflichtung.“ (Leitfaden B.14.3.1.1)"""
AUFFANG_WORDS = ("nicht zuordenbar", "ohne Zuordnung")
LEITFADEN = "Technischer Leitfaden zur HGB-Taxonomie"
FIXED_ASSETS = "bs.ass.fixAss"


class StatementType(StrEnum):
	"""The Bilanzart of the GCD, genInfo.report.id.statementType (Leitfaden B.14.3.1.3)."""

	JAHRESABSCHLUSS = "E"
	EROEFFNUNGSBILANZ = "EB"


class AccountingStandard(StrEnum):
	"""The Bilanzierungsstandard of the GCD, genInfo.report.id.accountingStandard (Leitfaden B.13)."""

	EINHEITSBILANZ = "HAOE"
	HANDELSBILANZ = "HGBM"
	STEUERBILANZ = "AO"

	@property
	def steuerbilanz(self) -> bool:
		return self is not AccountingStandard.HANDELSBILANZ


class Mark(StrEnum):
	"""What the taxonomy asks of a position (Leitfaden A.10), as the positions of the E-Bilanz show it."""

	MUSSFELD = "Muss"
	SUMMENMUSSFELD = "Summenmuss"
	AUFFANG = "Auffang"
	RECHNERISCH_NOTWENDIG = "rechnerisch notwendig"
	DAVON = "davon"
	OPTIONAL = ""

	@property
	def required(self) -> bool:
		"""Whether the position is reported, NIL where the books cannot fill it."""
		return self in (Mark.MUSSFELD, Mark.SUMMENMUSSFELD)


@dataclass(frozen=True, slots=True)
class Finding:
	"""What a check of the E-Bilanz found: its code, a German sentence, its source and what it is about."""

	code: str
	text: str
	source: str
	reference: str = ""
	"""The position, account or row the finding is about, without the prefix of the GAAP module."""
	severity: Severity = Severity.ERROR

	@property
	def blocking(self) -> bool:
		"""Whether the finding holds the E-Bilanz back from „Bereit“: an error does, a hint does not."""
		return self.severity is Severity.ERROR


def finding_of(found: checks.Finding) -> Finding:
	"""A finding of steuerbote/xbrl/checks.py as one of the E-Bilanz, by its position, period and members."""
	parts = [unqualified(found.concept)] if found.concept else []
	if found.period is not None:
		parts.append(found.period.value)
	parts.extend(unqualified(member) for _, member in found.dimensions)
	return Finding(found.code.value, found.text, found.source, " ".join(parts), found.severity)


def leitfaden(taxonomy: Taxonomy, sections: str) -> str:
	return f"{LEITFADEN} {taxonomy.version}, {sections}"


def rule(taxonomy: Taxonomy, code: str, sheet: str = "Regel") -> str:
	"""A rule of the Jahresdokumentation of the version in the ERiC documentation 44.3.6.0, by its Fehlercode."""
	return f"Jahresdokumentation_Bilanz_Taxonomie_{taxonomy.version.replace('.', '_')}.ods, {sheet} {code}"


def qualified(name: str) -> str:
	"""A name of the GAAP module with its prefix, as the facts name it."""
	return name if ":" in name else f"{GAAP}:{name}"


def unqualified(name: str) -> str:
	"""A name of the GAAP module without its prefix, as the Bilanzzuordnung and the findings name it."""
	return name.removeprefix(f"{GAAP}:")


class CaseError(ValueError):
	"""A case the E-Bilanz cannot be built for."""


@dataclass(frozen=True, slots=True)
class Case:
	"""What decides the structure of an E-Bilanz: legal form, periods, Bilanzierungsstandard, Bilanzart, Kontensalden.

	``legal_form`` is that of the Annual Filing Settings, GmbH or UG. ``kontennachweis`` is False only for the E-Bilanz
	of taxonomy 6.9 that leaves the Kontensalden out with a reason (steuerbote/ebilanz/kontennachweis.py).
	"""

	legal_form: str
	periods: Periods
	accounting_standard: AccountingStandard = AccountingStandard.EINHEITSBILANZ
	statement_type: StatementType = StatementType.JAHRESABSCHLUSS
	kontennachweis: bool = True

	def __post_init__(self) -> None:
		legal_form(self.legal_form)
		object.__setattr__(self, "accounting_standard", AccountingStandard(self.accounting_standard))
		object.__setattr__(self, "statement_type", StatementType(self.statement_type))
		periods = self.periods
		closing = periods.balance_sheet_date
		if self.opening and closing != periods.fiscal_year_begin:
			raise CaseError(
				"an Eröffnungsbilanz has its Bilanzstichtag on the first day of the fiscal year (rule 170205081)"
			)
		if not self.opening and closing != periods.fiscal_year_end:
			raise CaseError(
				"a Jahresabschluss has its Bilanzstichtag on the last day of the fiscal year (rule 170205072)"
			)
		if periods.prior_fiscal_year_end is not None and (
			self.accounting_standard.steuerbilanz or self.opening
		):
			raise CaseError(
				"only the Handelsbilanz of a Jahresabschluss shows the previous year (Leitfaden B.8.3, ERiC Kap. 3.13)"
			)

	@property
	def legal_status(self) -> str:
		"""The legal status of the GCD, GMBH or UG."""
		return legal_status(self.legal_form)

	@property
	def opening(self) -> bool:
		return self.statement_type is StatementType.EROEFFNUNGSBILANZ

	@property
	def steuerbilanz(self) -> bool:
		return self.accounting_standard.steuerbilanz

	@property
	def prior(self) -> bool:
		"""Whether the report shows the previous year, which only a Handelsbilanz may (Leitfaden B.8.3)."""
		return self.periods.prior_fiscal_year_end is not None

	@property
	def components(self) -> tuple[Component, ...]:
		"""The components the case announces, in the order of steuerbote.xbrl.checks.COMPONENTS."""
		codes = {checks.BILANZ.code, checks.ANLAGENSPIEGEL.code}
		if not self.opening:
			codes |= {checks.GUV.code, checks.BETRIEBSVERMOEGENSVERGLEICH.code}
		if self.kontennachweis:
			codes.add(checks.KONTENNACHWEIS.code)
		if not self.steuerbilanz:
			codes.add(checks.UEBERLEITUNG.code)
		return tuple(component for component in checks.COMPONENTS if component.code in codes)

	@property
	def facets(self) -> Facets:
		"""What the GCD of the report announces, as steuerbote.xbrl.checks reads it."""
		return Facets(
			legal_status=self.legal_status,
			income_statement_format=GKV.value,
			accounting_standard=self.accounting_standard.value,
			statement_type=self.statement_type.value,
			report_status=FINAL,
			components=frozenset(component.code for component in self.components),
		)


STATEMENTS = MappingProxyType(
	{
		checks.BILANZ.code: BALANCE_SHEET,
		checks.GUV.code: INCOME_STATEMENT,
		checks.BETRIEBSVERMOEGENSVERGLEICH.code: TRANSFERS_TAX_ASSETS,
	}
)
"""The components with positions of their own, each with the role of its presentation and its calculation."""


@dataclass(frozen=True, slots=True)
class Position:
	"""A position of Bilanz, GuV or Betriebsvermögensvergleich that the case admits."""

	concept: str
	label: str
	component: str
	"""The component it belongs to: B, GuV or BVV."""
	mark: Mark
	depth: int
	"""Its depth in the presentation of the component."""
	parent: str | None
	"""The position it adds up to in the calculation of its component, None for a total of the top or a davon."""
	weight: Decimal
	"""Its weight in that sum, 1 or -1."""
	davon_of: str | None
	"""For a davon position, the position above it whose amount includes its own; None for a position the calculation
	counts."""
	balance: Balance | None
	instant: bool
	"""Whether it refers to the Bilanzstichtag, else to the fiscal year."""

	@property
	def role(self) -> str:
		return STATEMENTS[self.component]


@dataclass(frozen=True, slots=True)
class Column:
	"""A column of the value development of the Anlagenspiegel: a primary item, its mark and its sum."""

	concept: str
	label: str
	mark: Mark
	parent: str | None
	weight: Decimal


@dataclass(frozen=True)
class Structure:
	"""What the E-Bilanz of a case reports, on one view of the taxonomy."""

	taxonomy: Taxonomy
	case: Case
	components: tuple[Component, ...]
	positions: tuple[Position, ...]
	"""Of Bilanz, GuV and Betriebsvermögensvergleich, by component in the order of their presentation."""
	required: tuple[str, ...]
	"""Every Mussfeld and Summenmussfeld the report sends, NIL where the books cannot fill it (Leitfaden B.14.2)."""
	refused: tuple[str, ...]
	"""The Mussfelder and Summenmussfelder of the components that the case does not admit: not sent, not even NIL."""
	rows: tuple[str, ...]
	"""The positions of the Anlagevermögen the Anlagenspiegel takes, as members of dim_changes.nt.ass.gross."""
	columns: tuple[Column, ...]
	"""The columns of its value development."""
	_positions: dict[str, Position] = field(init=False, repr=False, compare=False)

	def __post_init__(self) -> None:
		object.__setattr__(self, "_positions", {position.concept: position for position in self.positions})

	def position(self, name: str) -> Position | None:
		"""The position of a concept, named with the prefix of its module or without; None if the case has none."""
		return self._positions.get(qualified(name))

	def of(self, component: str) -> tuple[Position, ...]:
		"""The positions of a component, B, GuV or BVV."""
		return tuple(position for position in self.positions if position.component == component)

	def mussfelder(self, component: str, mark: Mark = Mark.MUSSFELD) -> tuple[str, ...]:
		"""The Mussfelder of a component the report sends, or its Summenmussfelder."""
		required = set(self.required)
		return tuple(
			position.concept
			for position in self.of(component)
			if position.mark is mark and position.concept in required
		)

	def column(self, name: str) -> Column | None:
		return next((column for column in self.columns if column.concept == qualified(name)), None)

	@property
	def announced(self) -> frozenset[str]:
		return frozenset(component.code for component in self.components)

	def label(self, name: str) -> str:
		return self.taxonomy.label(qualified(name))


def structure(taxonomy: Taxonomy, case: Case) -> Structure:
	"""The structure of the E-Bilanz of a case on the fiscal view of a version of the taxonomy."""
	periods = case.periods
	facets = case.facets
	forms = checks.legal_forms(taxonomy, facets)
	begin, closing = periods.fiscal_year_begin, periods.balance_sheet_date or periods.fiscal_year_end
	purposes = facets.purposes
	required = checks.required(taxonomy, facets, periods)
	required_set = frozenset(required)

	def admitted(concept: Concept) -> bool:
		return (
			concept.valid_for(begin, closing)
			and (not forms or any(concept.applies_to(form) for form in forms))
			and concept.suits(GKV)
			and all(concept.permitted_for(purpose) for purpose in purposes)
		)

	positions: list[Position] = []
	refused: dict[str, None] = {}
	for component in case.components:
		role = STATEMENTS.get(component.code)
		network = taxonomy.presentation.get(role) if role else None
		if network is None:
			continue
		calculation = taxonomy.calculation[role]
		for name, depth in network.walk():
			concept = taxonomy.concepts[name]
			if not concept.monetary or concept.abstract:
				continue
			if not admitted(concept):
				if concept.required_for(begin, closing):
					refused[name] = None
				continue
			arcs = calculation.parents(name)
			counted = _counted(taxonomy, network, calculation, name)
			positions.append(
				Position(
					concept=name,
					label=taxonomy.label(name),
					component=component.code,
					mark=_mark(taxonomy, concept, name, davon=not counted),
					depth=depth,
					parent=arcs[0].parent if arcs else None,
					weight=(arcs[0].weight or Decimal(1)) if arcs else Decimal(1),
					davon_of=None if counted else _counted_ancestor(taxonomy, network, calculation, name),
					balance=concept.balance,
					instant=concept.period_type is PeriodType.INSTANT,
				)
			)
	rows, columns = _fixed_assets(taxonomy, admitted)
	return Structure(
		taxonomy=taxonomy,
		case=case,
		components=case.components,
		positions=tuple(_marked_for_the_year(positions, required_set)),
		required=required,
		refused=tuple(refused),
		rows=rows,
		columns=columns,
	)


def _marked_for_the_year(positions: Iterable[Position], required: frozenset[str]) -> Iterator[Position]:
	"""The positions in their order, a Mussfeld not yet or no longer required in the fiscal year without its mark
	(fiscalValidSince, fiscalValidThrough; Leitfaden B.14.4.2)."""
	for position in positions:
		if position.mark.required and position.concept not in required:
			position = _with_mark(position, Mark.OPTIONAL)
		yield position


def _with_mark(position: Position, mark: Mark) -> Position:
	return Position(
		position.concept,
		position.label,
		position.component,
		mark,
		position.depth,
		position.parent,
		position.weight,
		position.davon_of,
		position.balance,
		position.instant,
	)


def _mark(taxonomy: Taxonomy, concept: Concept, name: str, *, davon: bool) -> Mark:
	requirement = concept.fiscal.requirement
	if requirement is Requirement.SUMMENMUSSFELD:
		return Mark.SUMMENMUSSFELD
	if requirement is not None and requirement.mandatory:
		return Mark.MUSSFELD
	if any(words in taxonomy.label(name) for words in AUFFANG_WORDS):
		return Mark.AUFFANG
	if requirement is Requirement.RECHNERISCH_NOTWENDIG:
		return Mark.RECHNERISCH_NOTWENDIG
	return Mark.DAVON if davon else Mark.OPTIONAL


def _counted(taxonomy: Taxonomy, presentation: Network, calculation: Network, name: str) -> bool:
	"""Whether the calculation adds the position up to a total of the component: one at the top of its presentation,
	under no position but abstract titles such as „Bilanz“ [bs]. A davon position the calculation leaves out is not, and
	neither is one it adds up to a davon only, such as „davon Erträge zur Erfüllung satzungsmäßiger Aufgaben“
	[is.netIncome.regular.operatingTC.otherOpRevenue.statutoryDuties] of the package 6.9 with the positions under it."""
	if name not in calculation:
		return False
	top = name
	while arcs := calculation.parents(top):
		top = arcs[0].parent
	return not any(
		not taxonomy.concepts[ancestor].abstract for ancestor in _presentation_ancestors(presentation, top)
	)


def _counted_ancestor(
	taxonomy: Taxonomy, presentation: Network, calculation: Network, name: str
) -> str | None:
	"""The nearest position above a davon position in the presentation that the calculation counts, whose amount
	includes that of the davon position."""
	return next(
		(
			ancestor
			for ancestor in _presentation_ancestors(presentation, name)
			if _counted(taxonomy, presentation, calculation, ancestor)
		),
		None,
	)


def _presentation_ancestors(presentation: Network, name: str) -> Iterator[str]:
	"""The positions above one in the presentation, nearest first, along the first parent of each."""
	while arcs := presentation.parents(name):
		name = arcs[0].parent
		yield name


def _fixed_assets(taxonomy: Taxonomy, admitted) -> tuple[tuple[str, ...], tuple[Column, ...]]:
	table = taxonomy.table(FIXED_ASSETS_GROSS)
	changes = next(dimension for dimension in table.dimensions if dimension.domain == qualified(FIXED_ASSETS))
	rows = tuple(member for member in changes.members if admitted(taxonomy.concepts[member]))
	calculation = taxonomy.calculation.get(NOTES)
	columns = []
	for name in table.primary_items:
		concept = taxonomy.concepts[name]
		if not concept.monetary or concept.abstract:
			continue
		arcs = calculation.parents(name) if calculation is not None else ()
		columns.append(
			Column(
				concept=name,
				label=taxonomy.label(name),
				mark=_mark(taxonomy, concept, name, davon=False),
				parent=arcs[0].parent if arcs else None,
				weight=(arcs[0].weight or Decimal(1)) if arcs else Decimal(1),
			)
		)
	return rows, tuple(columns)
