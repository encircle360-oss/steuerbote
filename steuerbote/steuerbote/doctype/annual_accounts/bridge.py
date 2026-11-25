"""Pure Python between the Annual Accounts and the core of the Jahresabschluss in steuerbote.hgb.

Nothing here imports Frappe. The controller (annual_accounts.py) reads the sources through
steuerbote/annual_accounts_sources.py and steuerbote/headcount.py, runs the core and keeps what it computed in the
lines, tables and fields of the document; this module turns the one into the other, so that every rule is tested
without a bench:

- Size (criteria, decide, applied_class): the criteria of § 267 Abs. 4a, Abs. 1 and Abs. 5 HGB on both
  Abschlussstichtage, the class steuerbote.hgb.size decides from them and from the class of the previous year, and
  the class a Begründung sets by hand instead.
- Headcount (headcounts, average_employees): the employees of each quarter end of § 267 Abs. 5 HGB, without the
  Employment Types the Annual Filing Settings leave out, and their average.
- Statements (statements, line_rows): the statement of the books (steuerbote.hgb.statement.build) and the one the
  document files, which takes each correction of a line as a balance of its difference on the position, so that
  the totals, the Jahresergebnis and the check of Aktiva and Passiva take it in. Only a line that takes balances
  itself takes a correction: no total, no result the statement computes, no position with positions under it that
  the class shows, and no Vermerk.
- Notes (note_rows, notes_kept, answers_of): the catalogue of steuerbote.hgb.notes for the class with the answers the
  company gave, kept by code.
- Signatories, register data, the findings of the core as rows of the table Befunde, what holds the Feststellung
  back (filing_problems), the Ergebnisverwendung with the rows of its draft Journal Entry, what the Übermittlung and
  the Einstellung need, and the inputs of the XBRL of steuerbote.hgb.instance (notes_of, master_data).

Messages are English templates with positional placeholders, kept apart from their values, so that the Frappe layer
translates the template before it formats it; MESSAGES lists them for the translations. The texts of the core of
steuerbote.hgb are German and pass as values.
"""

import json
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from steuerbote.hgb import size as hgb_size
from steuerbote.hgb.disclosure import Director, Mode, Signature, transmission_problems
from steuerbote.hgb.instance import Address, MasterData, Notes
from steuerbote.hgb.notes import (
	Answer,
	CatalogueEntry,
	NoteAnswer,
	NotesError,
	RegisterData,
	answer_problems,
	catalogue,
	register_problems,
)
from steuerbote.hgb.schemes import (
	Level,
	Method,
	Position,
	VermerkKind,
	balance_sheet_scheme,
	income_statement_scheme,
)
from steuerbote.hgb.size import Criteria, Origin, SizeClass, SizeDecision
from steuerbote.hgb.statement import (
	BILANZGEWINN,
	EQUITY,
	NET_INCOME,
	PROFIT_CARRIED_FORWARD,
	AnnualStatement,
	Balance,
	Line,
	ProfitPresentation,
	RemainingTerm,
	build,
	entered,
	ug_reserve_minimum,
)
from steuerbote.jahresmeldung.corrections import RevisionStatus
from steuerbote.jahresmeldung.findings import DATA_LENGTH
from steuerbote.jahresmeldung.findings import Finding as AnnualFinding
from steuerbote.jahresmeldung.findings import Severity as AnnualSeverity
from steuerbote.jahresmeldung.overrides import Columns, correction_of, to_amount
from steuerbote.steuerbote.doctype.annual_filing_settings import rules as settings_rules
from steuerbote.ustva.period import day_label
from steuerbote.ustva.rounding import ZERO
from steuerbote.xbrl.facts import Periods

type Row = Mapping[str, Any]

LINE_COLUMNS = Columns(
	key="concept",
	amounts=("amount", "prior"),
	described=(
		"statement",
		"marker",
		"label",
		"level",
		"parent_concept",
		"shown",
		"takes_correction",
		"sources",
	),
	correction="correction",
	reason="correction_reason",
	reported="reported",
	manual="manual",
)
"""The columns of the table Zeilen: the concept of the position or of its Vermerk, the amount of the year and of the
previous year, what describes the line, the correction with its reason, the amount it files and the mark of a line by
hand, which the Jahresabschluss does not take (steuerbote.jahresmeldung.overrides)."""


class Statement(StrEnum):
	"""Where a line stands: a side of the Bilanz, or the GuV, which Kleinst and klein do not disclose."""

	AKTIVA = "Aktiva"
	PASSIVA = "Passiva"
	GUV = "GuV"


VERMERK = "Vermerk"
"""The level of a line that notes a part of the position above it („davon“)."""
AKTIVA_TOTAL = "bs.ass"
PASSIVA_TOTAL = "bs.eqLiab"
GUV_NET_INCOME = "is.netIncome"
CORRECTION_SOURCE = "Korrektur"
EMPLOYEES_CODE = "ARBEITNEHMER"
ZERO_EQUITY_CODE = "EIGENKAPITAL-NULL"

SIZE_CLASSES = MappingProxyType(
	{
		settings_rules.SizeClass.KLEINST: SizeClass.KLEINST,
		settings_rules.SizeClass.KLEIN: SizeClass.KLEIN,
		settings_rules.SizeClass.MITTELGROSS: SizeClass.MITTELGROSS,
		settings_rules.SizeClass.GROSS: SizeClass.GROSS,
	}
)
"""The size classes as the Annual Filing Settings and the document name them, with the class of steuerbote.hgb.size."""


class DisclosureMode(StrEnum):
	"""How the document discloses, as the field kleinst_mode of the Annual Filing Settings names it for a Kleinst."""

	HINTERLEGUNG = "Hinterlegung"
	VEROEFFENTLICHUNG = "Veröffentlichung"


MODES = MappingProxyType(
	{DisclosureMode.HINTERLEGUNG: Mode.HINTERLEGUNG, DisclosureMode.VEROEFFENTLICHUNG: Mode.OFFENLEGUNG}
)
PRESENTATIONS = MappingProxyType({presentation.value: presentation for presentation in ProfitPresentation})


class Code(StrEnum):
	"""The codes of Steuerbote for the findings of the Annual Accounts beyond those of the core of steuerbote.hgb."""

	NO_CLASS = "JA-GROESSENKLASSE"
	CLASS_BY_HAND = "JA-GROESSENKLASSE-HAND"
	NOT_PREPARED = "JA-KLASSE"
	EMPLOYEES_BY_HAND = "JA-ARBEITNEHMER-HAND"
	EMPLOYMENT_TYPE = "JA-ARBEITNEHMER-ART"
	NO_PRIOR_YEAR = "JA-VORJAHR-FEHLT"
	SIZE_HISTORY = "JA-GROESSE-EINSTELLUNGEN"
	UG_RESERVE = "JA-UG-RUECKLAGE"
	DEPOSIT = "JA-HINTERLEGUNG"
	CORRECTION = "JA-KORREKTUR"


# Messages of the save, of Berechnen and of the Feststellung, which the Frappe layer translates.
STALE = "Calculate {0} again before its Feststellung: a correction, an Angabe or another entry changed since Berechnen."
NO_CLASS = (
	"No size class applies to {0}: the Annual Filing Settings need the class of the year before, or enter the size "
	"class by hand with its reason."
)
NOT_BALANCED = (
	"Aktiva of {0} and Passiva of {1} differ; a Jahresabschluss is festgestellt only once both agree "
	"(§ 242 Abs. 1, § 266 Abs. 1 Satz 1 HGB)."
)
NET_INCOME_DIFFERS = (
	"The Jahresergebnis of the Bilanz, {0}, is not that of the GuV, {1} (§ 266 Abs. 3 A. V., § 275 HGB)."
)
REGISTER_MISSING = "{0} Enter them in the Annual Filing Settings and calculate again."
NOTES_OPEN = "The Angaben are not complete: {0}"
ZERO_EQUITY = (
	"The Eigenkapital is zero: say under the Bilanz why the Stammkapital is used up (Angabe EIGENKAPITAL-NULL; "
	"Bundesamt für Justiz, FAQ zu Inhalts- und Formverstößen)."
)
NOT_ADOPTED = (
	"Enter the day of the Feststellung: the shareholders adopt the Jahresabschluss (§ 42a Abs. 2 GmbHG)."
)
ADOPTED_EARLY = (
	"The Feststellung on {0} lies within the fiscal year, which ends on {1} (§ 42a Abs. 2 Satz 1 GmbHG)."
)
ADOPTED_LATER = "The Feststellung on {0} lies in the future."
CORRECTION_REFUSED = (
	"The line {0} takes no correction: correct a line that takes balances itself, and the totals and the "
	"Jahresergebnis follow it with Berechnen."
)
NO_LINE_BY_HAND = (
	"The Jahresabschluss takes no line by hand: every position of its class has its line, correct that."
)
NEGATIVE_APPROPRIATION = "The Ergebnisverwendung takes no negative amount: {0}."
APPROPRIATION_TOO_HIGH = (
	"The Ergebnisverwendung distributes {0}, more than the Bilanzgewinn of {1} (Jahresergebnis and "
	"Gewinnvortrag/Verlustvortrag)."
)
OVERRIDE_WITHOUT_REASON = "{0} by hand needs its reason."
HINTERLEGUNG_FOR_KLEINST = (
	"Only a Kleinstkapitalgesellschaft deposits its Bilanz (§ 326 Abs. 2 HGB); a {0} publishes it."
)
NO_CLASS_YET = "Gesellschaft ohne entschiedene Größenklasse"
PRIOR_WITHOUT_SOURCE = (
	"The Vorjahr by hand names where its figures come from, such as the festgestellter Jahresabschluss."
)
PRIOR_POSITION = "{0} is no position of the Bilanz or the GuV of {1}."
TRANSMITTED_LATER = "The Übermittlung on {0} lies in the future."
TRANSMISSION_REFUSED = "{0}"
NO_NOTICE = (
	"A Hinterlegung needs the box ticked in the order that makes the Mitteilung of § 326 Abs. 2 Satz 2 HGB; "
	"without it the order is no Hinterlegung."
)
NO_ORDER_NUMBER = "Enter the Auftragsnummer of the order, as Meine Daten, Aufträge & Abrufe shows it."
PUBLISHED_EARLY = "The Einstellung on {0} lies before the Übermittlung on {1}."
PUBLISHED_LATER = "The Einstellung on {0} lies in the future."
NO_APPROPRIATION = (
	"The Ergebnisverwendung puts nothing into the reserves and distributes nothing; there is nothing to post."
)
NO_APPROPRIATION_ACCOUNTS = "Steuerbote knows the accounts of the Ergebnisverwendung of SKR03 and SKR04, not those of a chart of its own."
MESSAGES = (
	STALE,
	NO_CLASS,
	NOT_BALANCED,
	NET_INCOME_DIFFERS,
	REGISTER_MISSING,
	NOTES_OPEN,
	ZERO_EQUITY,
	NOT_ADOPTED,
	ADOPTED_EARLY,
	ADOPTED_LATER,
	CORRECTION_REFUSED,
	NO_LINE_BY_HAND,
	NEGATIVE_APPROPRIATION,
	APPROPRIATION_TOO_HIGH,
	OVERRIDE_WITHOUT_REASON,
	HINTERLEGUNG_FOR_KLEINST,
	PRIOR_WITHOUT_SOURCE,
	PRIOR_POSITION,
	TRANSMITTED_LATER,
	TRANSMISSION_REFUSED,
	NO_NOTICE,
	NO_ORDER_NUMBER,
	PUBLISHED_EARLY,
	PUBLISHED_LATER,
	NO_APPROPRIATION,
	NO_APPROPRIATION_ACCOUNTS,
)


@dataclass(frozen=True, slots=True)
class Problem:
	"""Something that holds a step of the document back: an English template and its values."""

	template: str
	values: tuple[object, ...] = ()


class BridgeError(ValueError):
	"""An entry of the document that the core cannot take; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


# Size


def size_class_of(value: object) -> SizeClass | None:
	"""The class of steuerbote.hgb.size of a class as the document stores it, None for none."""
	if not value:
		return None
	return SIZE_CLASSES[settings_rules.SizeClass(value)]


def stored_class(size_class: SizeClass | None) -> str:
	"""A class of steuerbote.hgb.size as the document stores it, empty for none."""
	if size_class is None:
		return ""
	return next(stored for stored, core in SIZE_CLASSES.items() if core is size_class).value


def criteria(
	closing_date: date, bilanzsumme: Decimal, umsatzerloese: Decimal, employees: Decimal
) -> Criteria:
	"""The criteria of one Abschlussstichtag; a negative amount, as the books of a year with more credit notes than
	sales give it, counts as zero, since it exceeds no threshold."""
	return Criteria(closing_date, max(bilanzsumme, ZERO), max(umsatzerloese, ZERO), max(employees, ZERO))


def previous_criteria(record: settings_rules.SizeRecord | None, books: Criteria | None) -> Criteria | None:
	"""The criteria of the previous Abschlussstichtag: those the Annual Filing Settings record for it, where they hold
	all three, else those of the books of the year before."""
	if record is not None and None not in (record.balance_sheet_total, record.revenue, record.employees):
		return criteria(record.fiscal_year_end, record.balance_sheet_total, record.revenue, record.employees)
	return books


def decide(
	current: Criteria,
	previous: Criteria | None,
	previous_class: SizeClass | None,
	*,
	founded_in_year: bool,
	excluded_from_kleinst: bool,
) -> SizeDecision:
	"""The class of the fiscal year (§ 267 Abs. 4 HGB); the year a company is founded in is the first after its
	Neugründung."""
	return hgb_size.decide(
		current,
		previous,
		previous_class,
		first_after=Origin.NEUGRUENDUNG if founded_in_year else None,
		excluded_from_kleinst=excluded_from_kleinst,
	)


def applied_class(
	decision: SizeDecision, override: SizeClass | None, reason: str
) -> tuple[SizeClass | None, tuple[AnnualFinding, ...]]:
	"""The class the Jahresabschluss takes: the one by hand with its reason, else the one decided; and the findings,
	an error without a class and a hint where the class by hand is not the one decided."""
	if override is not None:
		if not reason.strip():
			raise BridgeError(OVERRIDE_WITHOUT_REASON, "Größenklasse")
		if override is decision.applied:
			return override, ()
		decided = decision.applied.value if decision.applied else "keine"
		return override, (
			AnnualFinding(
				Code.CLASS_BY_HAND,
				AnnualSeverity.HINT,
				f"Die Größenklasse von Hand, {override.value}, ersetzt die entschiedene ({decided}): {reason.strip()}",
				override.reference,
			),
		)
	if decision.applied is None:
		return None, (
			AnnualFinding(
				Code.NO_CLASS,
				AnnualSeverity.ERROR,
				"Keine Größenklasse ist entschieden: Die Merkmale der beiden Abschlussstichtage weichen voneinander ab, "
				"und die Einstellungen Jahresmeldungen nennen die Größenklasse des Vorjahres nicht (§ 267 Abs. 4 "
				"Satz 1 HGB). Nennen Sie sie dort oder geben Sie die Größenklasse von Hand mit Begründung an.",
				"§ 267 Abs. 4 HGB",
			),
		)
	return decision.applied, ()


def size_findings(
	decision: SizeDecision, applied: SizeClass | None, history: settings_rules.SizeRecord | None
) -> tuple[AnnualFinding, ...]:
	"""The hints of the size: a holding of § 267a Abs. 3 HGB that is klein instead of Kleinst, a class Steuerbote
	prepares no Anhang and no Offenlegung for, and a closing date the size history of the settings lacks."""
	found = []
	if decision.kleinst_excluded:
		found.append(
			AnnualFinding(
				Code.NOT_PREPARED,
				AnnualSeverity.HINT,
				"Die Gesellschaft ist nach § 267a Abs. 3 HGB keine Kleinstkapitalgesellschaft und stellt den "
				"Jahresabschluss einer kleinen Gesellschaft auf.",
				"§ 267a Abs. 3 HGB",
			)
		)
	if applied is not None and not applied.is_small:
		found.append(
			AnnualFinding(
				Code.NOT_PREPARED,
				AnnualSeverity.HINT,
				f"Für eine {applied.value} bereitet Steuerbote Anhang und Offenlegung nicht vor; Bilanz und GuV stehen "
				"im Druck, die Offenlegung übernimmt die Steuerberatung oder der Abschlussprüfer.",
				"§§ 325, 327 HGB",
			)
		)
	if history is None or history.size_class != stored_class(applied):
		found.append(
			AnnualFinding(
				Code.SIZE_HISTORY,
				AnnualSeverity.HINT,
				"Die Größenmerkmale der Einstellungen Jahresmeldungen nennen für den Abschlussstichtag nicht die "
				"angewandte Größenklasse; bis sie eine nennen, rechnet die Frist der Feststellung mit der angewandten.",
				"§ 42a Abs. 2 Satz 1 GmbHG",
			)
		)
	return tuple(found)


# Headcount


@dataclass(frozen=True, slots=True)
class Employee:
	"""An employee of the company as the Employee of ERPNext holds him: the days of joining and leaving, and the
	Employment Type HRMS adds, empty without it."""

	joined: date
	relieved: date | None = None
	employment_type: str = ""

	def employed_on(self, day: date) -> bool:
		return self.joined <= day and (self.relieved is None or day <= self.relieved)


def headcounts(
	employees: Iterable[Employee], closing_date: date, not_counted: Collection[str]
) -> dict[date, int]:
	"""The employees on each quarter end of § 267 Abs. 5 HGB, without those of the Employment Types not counted."""
	counted = [employee for employee in employees if employee.employment_type not in not_counted]
	return {
		day: sum(1 for employee in counted if employee.employed_on(day))
		for day in hgb_size.headcount_dates(closing_date)
	}


def average_employees(counts: Mapping[date, int], closing_date: date) -> Decimal:
	return hgb_size.average_employees(counts, closing_date)


def headcount_text(counts: Mapping[date, int]) -> str:
	"""The headcounts as the document shows them, such as „31.03.2026: 2; 30.06.2026: 3“."""
	return "; ".join(f"{day:%d.%m.%Y}: {count}" for day, count in sorted(counts.items()))


def employees_applied(counted: Decimal, override: Decimal | None, reason: str) -> tuple[Decimal, tuple]:
	"""The Arbeitnehmer the size takes: those by hand with their reason, else those counted; a hint by hand."""
	if override is None:
		return counted, ()
	if not reason.strip():
		raise BridgeError(OVERRIDE_WITHOUT_REASON, "Arbeitnehmer")
	return override, (
		AnnualFinding(
			Code.EMPLOYEES_BY_HAND,
			AnnualSeverity.HINT,
			f"Die Arbeitnehmer von Hand, {_number(override)}, ersetzen die gezählten ({_number(counted)}): "
			f"{reason.strip()}",
			"§ 267 Abs. 5 HGB",
		),
	)


def employment_type_finding(not_counted: Collection[str], typed: bool) -> tuple[AnnualFinding, ...]:
	"""A hint where the settings leave Employment Types out but the employees carry none, as without HRMS."""
	if typed or not not_counted:
		return ()
	return (
		AnnualFinding(
			Code.EMPLOYMENT_TYPE,
			AnnualSeverity.HINT,
			"Die Einstellungen Jahresmeldungen nennen nicht gezählte Arten der Beschäftigung, die Mitarbeiter haben "
			"aber keine Art der Beschäftigung (HRMS fehlt): Steuerbote zählt jeden Mitarbeiter. Ziehen Sie die zu "
			"ihrer Berufsausbildung Beschäftigten von Hand ab.",
			"§ 267 Abs. 5 HGB",
		),
	)


# Statements


@dataclass(frozen=True, slots=True)
class Statements:
	"""The statement of the books and the one the document files with its corrections."""

	books: AnnualStatement
	filed: AnnualStatement
	balances: tuple[Balance, ...] = ()
	"""The balances of the statement the document files: those of the books and the differences of the corrections."""
	refused: tuple[str, ...] = ()
	"""The concepts of corrections the class takes on no line of its own, which the statement leaves out."""


def statements(
	year: int,
	size_class: SizeClass,
	balances: Sequence[Balance],
	*,
	parents: Mapping[str, str],
	prior: Sequence[Balance] | None = None,
	prior_net_income: Decimal | None = None,
	presentation: ProfitPresentation = ProfitPresentation.BEFORE_APPROPRIATION,
	corrections: Mapping[str, Decimal] | None = None,
) -> Statements:
	"""The statement of the books and the one with each correction as the balance of its difference on its line, by
	the Gesamtkostenverfahren: the ledger knows the nature of an expense, not its function (steuerbote.hgb.schemes)."""
	options = {
		"parents": parents,
		"prior": prior,
		"prior_net_income": prior_net_income,
		"method": Method.GKV,
		"presentation": presentation,
	}
	books = build(year, size_class, balances, **options)
	takes = correctable(books)
	lines = {line.position.concept: line for line in _all_lines(books)}
	deltas, refused = [], []
	for concept, amount in (corrections or {}).items():
		if concept not in takes:
			refused.append(concept)
			continue
		line = lines[concept]
		if amount != line.amount:
			deltas.append(entered(line.position, amount - line.amount, source=CORRECTION_SOURCE))
	filed_balances = (*balances, *deltas)
	filed = build(year, size_class, filed_balances, **options) if deltas else books
	return Statements(books, filed, filed_balances, tuple(refused))


def correctable(statement: AnnualStatement) -> frozenset[str]:
	"""The lines that take a correction: those of a position that takes balances itself, which no position the class
	shows lies under and which the statement does not compute."""
	sheet = statement.balance_sheet
	shown = {line.position.concept for line in sheet.aktiva + sheet.passiva}
	takes = {
		line.position.concept
		for line in sheet.aktiva + sheet.passiva
		if not line.position.computed and not any(child.concept in shown for child in line.position.children)
	}
	takes.update(
		line.position.concept
		for line in statement.income_statement.lines
		if not line.position.computed and not line.position.children
	)
	return frozenset(takes)


def corrections_of(rows: Iterable[Row]) -> dict[str, Decimal]:
	"""The corrections the lines hold, by concept: an amount once it has its reason."""
	found = {}
	for row in rows:
		correction = correction_of(row, LINE_COLUMNS)
		if correction is not None:
			found[str(row.get(LINE_COLUMNS.key) or "").strip()] = correction.amount
	return found


def correction_problems(rows: Iterable[Row]) -> tuple[Problem, ...]:
	"""A line by hand, and a correction of a line that takes none."""
	problems = []
	for row in rows:
		if row.get(LINE_COLUMNS.manual):
			problems.append(Problem(NO_LINE_BY_HAND))
		elif correction_of(row, LINE_COLUMNS) is not None and not row.get("takes_correction"):
			problems.append(Problem(CORRECTION_REFUSED, (row.get(LINE_COLUMNS.key),)))
	return tuple(problems)


def refused_findings(refused: Iterable[str]) -> tuple[AnnualFinding, ...]:
	"""An error for each correction the class takes on no line: Berechnen keeps it, the statement leaves it out."""
	return tuple(
		AnnualFinding(
			Code.CORRECTION,
			AnnualSeverity.ERROR,
			f"Die Korrektur von {concept} zählt in der Bilanz dieser Größenklasse nicht, denn ihre Zeile nimmt keine "
			"Salden auf: Korrigieren Sie eine Zeile darunter oder nehmen Sie die Korrektur heraus.",
			concept,
		)
		for concept in refused
	)


def _all_lines(statement: AnnualStatement) -> tuple[Line, ...]:
	sheet = statement.balance_sheet
	return (*sheet.aktiva, *sheet.passiva, *statement.income_statement.lines)


def line_rows(found: Statements, parents: Mapping[str, str]) -> list[dict[str, Any]]:
	"""The lines of the document: each side of the Bilanz with the positions its class shows, each with its Vermerke
	and the total of the side last, then the GuV. A line that takes a correction holds the amount of the books, every
	other the amount the document files, so that what each line reports is the statement with the corrections. Each
	names the sources of the balances under it, along ``parents`` as the statement sums them up."""
	takes = correctable(found.books)
	books = {line.position.concept: line for line in _all_lines(found.books)}
	sources = _sources(found, parents)
	sheet = found.filed.balance_sheet
	rows: list[dict[str, Any]] = []
	sides = (
		(
			Statement.AKTIVA,
			sheet.aktiva,
			AKTIVA_TOTAL,
			"Summe Aktiva",
			sheet.aktiva_total,
			sheet.prior_aktiva_total,
		),
		(
			Statement.PASSIVA,
			sheet.passiva,
			PASSIVA_TOTAL,
			"Summe Passiva",
			sheet.passiva_total,
			sheet.prior_passiva_total,
		),
	)
	for side, lines, total, label, amount, prior in sides:
		concepts = {line.position.concept for line in lines}
		for line in lines:
			parent = sheet.scheme.parent(line.position.concept)
			while parent is not None and parent.concept not in concepts:
				parent = sheet.scheme.parent(parent.concept)
			above = parent.concept if parent else ""
			rows.extend(_rows_of(side, line, books, above, takes, sources))
		rows.append(_total(side, total, label, amount, prior))
	income = found.filed.income_statement
	for line in income.lines:
		parent = income.scheme.parent(line.position.concept)
		rows.extend(_rows_of(Statement.GUV, line, books, parent.concept if parent else "", takes, sources))
	return rows


def _sources(found: Statements, parents: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
	"""The sources of the balances by each line they add up to: a balance lands on the nearest position of the scheme
	at or above its concept, and counts in every line above that one."""
	sheet, income = found.filed.balance_sheet, found.filed.income_statement
	lines = {line.position.concept for line in _all_lines(found.filed)}
	named: dict[str, list[str]] = {}
	for balance in found.balances:
		if not balance.source:
			continue
		for scheme in (sheet.scheme, income.scheme):
			position = _position_of(balance.concept, scheme, parents)
			while position is not None:
				if position.concept in lines:
					named.setdefault(position.concept, []).append(balance.source)
				position = scheme.parent(position.concept)
	return {concept: tuple(dict.fromkeys(names)) for concept, names in named.items()}


def _position_of(concept: str, scheme: Any, parents: Mapping[str, str]) -> Position | None:
	"""The nearest position of the scheme at or above the concept, along ``parents``."""
	current: str | None = concept
	seen: set[str] = set()
	while current is not None and current not in seen:
		seen.add(current)
		if scheme.has(current):
			return scheme.position(current)
		current = parents.get(current)
	return None


def _rows_of(
	side: Statement,
	filed: Line,
	books: Mapping[str, Line],
	parent: str,
	takes: frozenset[str],
	sources: Mapping[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
	position = filed.position
	takes_correction = position.concept in takes
	book = books[position.concept]
	rows = [
		{
			"statement": side.value,
			"concept": position.concept,
			"marker": position.marker,
			"label": filed.label,
			"level": position.level.value,
			"parent_concept": parent,
			"shown": int(filed.shown or book.shown),
			"takes_correction": int(takes_correction),
			"amount": book.amount if takes_correction else filed.amount,
			"prior": filed.prior or ZERO,
			"sources": ", ".join(sources.get(position.concept, ())),
		}
	]
	for noted in filed.vermerke:
		rows.append(
			{
				"statement": side.value,
				"concept": noted.vermerk.concept,
				"marker": "",
				"label": noted.vermerk.label,
				"level": VERMERK,
				"parent_concept": position.concept,
				"shown": int(noted.shown),
				"takes_correction": 0,
				"amount": noted.amount,
				"prior": noted.prior or ZERO,
				"sources": "",
			}
		)
	return rows


def _total(
	side: Statement, concept: str, label: str, amount: Decimal, prior: Decimal | None
) -> dict[str, Any]:
	return {
		"statement": side.value,
		"concept": concept,
		"marker": "",
		"label": label,
		"level": Level.TOTAL.value,
		"parent_concept": "",
		"shown": 1,
		"takes_correction": 0,
		"amount": amount,
		"prior": prior or ZERO,
		"sources": "",
	}


def reported(rows: Iterable[Row], concept: str) -> Decimal | None:
	"""What the line of a concept reports, None without such a line."""
	for row in rows:
		if row.get(LINE_COLUMNS.key) == concept and not row.get(LINE_COLUMNS.manual):
			return to_amount(row.get(LINE_COLUMNS.reported))
	return None


def statement_values(statement: AnnualStatement) -> dict[str, Decimal]:
	"""The fields of the document the statement gives, from its form of klein, which shows the Gewinnvortrag or the
	Bilanzgewinn with it: Bilanzsumme and Umsatzerlöse for the size, the Jahresergebnis, the Gewinnvortrag or
	Verlustvortrag and the Eigenkapital."""
	sheet, income = statement.balance_sheet, statement.income_statement
	if sheet.size_class is SizeClass.KLEINST:
		raise ValueError("the Gewinnvortrag needs the balance sheet of a class that shows the roman numerals")
	return {
		"bilanzsumme": sheet.bilanzsumme,
		"umsatzerloese": income.sales,
		"net_income": income.net_income,
		"carried_forward": _carried_forward(sheet.passiva),
		"equity": sheet.equity,
	}


def _carried_forward(passiva: Iterable[Line]) -> Decimal:
	"""The Gewinnvortrag or Verlustvortrag: its line before the appropriation, after part of it the Vermerk of the
	Bilanzgewinn (§ 268 Abs. 1 Satz 2 HGB)."""
	lines = {line.position.concept: line for line in passiva}
	if PROFIT_CARRIED_FORWARD in lines:
		return lines[PROFIT_CARRIED_FORWARD].amount
	(noted,) = (
		noted
		for noted in lines[BILANZGEWINN].vermerke
		if noted.vermerk.kind is VermerkKind.PROFIT_CARRIED_FORWARD
	)
	return noted.amount


def prior_values(statement: AnnualStatement) -> dict[str, Decimal] | None:
	"""Bilanzsumme and Umsatzerlöse of the previous year, None without one."""
	sheet, income = statement.balance_sheet, statement.income_statement
	if sheet.prior_bilanzsumme is None:
		return None
	return {"bilanzsumme": sheet.prior_bilanzsumme, "umsatzerloese": income.prior_sales or ZERO}


def prior_balances(rows: Iterable[Row], year: int) -> tuple[Balance, ...]:
	"""The Vorjahr by hand: each row a figure of the last festgestellter Jahresabschluss at its position of the Bilanz
	or the GuV, with the flags its Vermerke need (steuerbote.hgb.statement.entered)."""
	positions = _positions(year)
	balances = []
	for row in rows:
		concept = str(row.get("concept") or "").strip()
		position = positions.get(concept)
		if position is None or position.computed:
			raise BridgeError(PRIOR_POSITION, concept, year)
		term = row.get("remaining_term") or None
		balances.append(
			entered(
				position,
				to_amount(row.get("amount")),
				shareholder=bool(row.get("shareholder")),
				remaining_term=RemainingTerm(term) if term else None,
			)
		)
	return tuple(balances)


def prior_labels(rows: Iterable[Row], year: int) -> list[str]:
	"""The label of the position of each row of the Vorjahr by hand, as a save writes it."""
	positions = _positions(year)
	labels = []
	for row in rows:
		concept = str(row.get("concept") or "").strip()
		position = positions.get(concept)
		if position is None or position.computed:
			raise BridgeError(PRIOR_POSITION, concept, year)
		labels.append(f"{position.marker} {position.label}".strip())
	return labels


def _positions(year: int) -> dict[str, Position]:
	return {
		position.concept: position
		for scheme in (balance_sheet_scheme(year), income_statement_scheme(year, Method.GKV))
		for position in scheme.positions()
	}


# Notes


def catalogue_of(size_class: SizeClass | None, *, equity_zero: bool) -> tuple[CatalogueEntry, ...]:
	"""The Angaben the class owes, none for a class without a catalogue of Steuerbote."""
	if size_class is None:
		return ()
	try:
		return catalogue(size_class, equity_zero=equity_zero)
	except NotesError:
		return ()


def note_rows(entries: Iterable[CatalogueEntry], stored: Iterable[Row]) -> list[dict[str, Any]]:
	"""The rows of the table Angaben for the catalogue, each with the answer, text and amount the company gave it; the
	Arbeitnehmer start answered „ja“, since their number is that of the document (§ 285 Nr. 7 HGB)."""
	answers = {str(row.get("code")): row for row in stored if row.get("code")}
	rows = []
	for entry in entries:
		item = entry.item
		before = answers.get(item.code, {})
		first = "ja" if item.code == EMPLOYEES_CODE else ""
		rows.append(
			{
				"code": item.code,
				"label": item.label,
				"reference": item.reference,
				"requirement": entry.requirement.value,
				"published": int(entry.published),
				"answer": before.get("answer") or first,
				"text": before.get("text") or "",
				"amount": to_amount(before.get("amount")),
			}
		)
	return rows


def notes_kept(stored: Iterable[Row], sent: Iterable[Row]) -> list[dict[str, Any]]:
	"""The rows of the table Angaben after a save: those Berechnen stored, each with the answer, text and amount the
	save sends for it; a row of the save Berechnen did not store is left out."""
	by_name = {row.get("name"): row for row in sent if row.get("name")}
	kept = []
	for row in stored:
		answer = by_name.get(row.get("name"), row)
		kept.append(
			{
				**{key: value for key, value in row.items() if key not in ("answer", "text", "amount")},
				"answer": answer.get("answer") or "",
				"text": answer.get("text") or "",
				"amount": to_amount(answer.get("amount")),
			}
		)
	return kept


def answers_of(rows: Iterable[Row], employees: Decimal) -> tuple[NoteAnswer, ...]:
	"""The answers of the rows: the number of the Arbeitnehmer is the average of the document (§ 285 Nr. 7 HGB),
	and an amount of zero is no amount, since a Currency field of Frappe stores no empty one."""
	answers = []
	for row in rows:
		if not row.get("answer"):
			continue
		code = str(row.get("code"))
		amount = to_amount(row.get("amount"))
		if code == EMPLOYEES_CODE:
			value: Decimal | None = employees
		else:
			value = amount or None
		answers.append(NoteAnswer(code, Answer(row["answer"]), str(row.get("text") or ""), value))
	return tuple(answers)


# Signatories and directors


def day_of(value: object) -> date | None:
	"""A date field as a date: Frappe hands out a date as stored, the text of a form as sent, or nothing."""
	if not value:
		return None
	if isinstance(value, date):
		return value
	return date.fromisoformat(str(value)[:10])


def signatures_of(rows: Iterable[Row]) -> tuple[Signature, ...]:
	return tuple(
		Signature(
			str(row.get("signatory_name") or "").strip(),
			str(row.get("function") or "").strip(),
			str(row.get("place") or "").strip(),
			day_of(row.get("signed_on")),
		)
		for row in rows
	)


def signing_directors(directors: Iterable[settings_rules.Director]) -> tuple[Director, ...]:
	"""The Geschäftsführer of the settings who sign the Jahresabschluss (§ 245 Satz 1 HGB)."""
	return tuple(
		Director(director.name, director.from_date, director.to_date)
		for director in directors
		if director.signs
	)


def signatory_rows(
	directors: Iterable[settings_rules.Director], day: date, place: str
) -> list[dict[str, Any]]:
	"""The signatories a new Jahresabschluss starts with: each Geschäftsführer who signs and is in office on the
	day, with his function, the place and no date yet."""
	return [
		{"signatory_name": director.name, "function": director.role or "", "place": place, "signed_on": None}
		for director in directors
		if director.signs and director.period.covers(day)
	]


# Register data


def register_values(company_name: str, settings: Row) -> dict[str, str]:
	"""What § 264 Abs. 1a HGB names, from the Annual Filing Settings: the Firma, the Sitz, the Registergericht and
	the Registernummer with its Registerart, such as „HRB 12345“."""
	kind = str(settings.get("register_type") or "").strip()
	number = str(settings.get("register_number") or "").strip()
	if kind and number and not number.startswith(kind):
		number = f"{kind} {number}"
	return {
		"firma": company_name.strip(),
		"sitz": str(settings.get("registered_seat") or "").strip(),
		"register_court": str(settings.get("register_court") or "").strip(),
		"register_number": number,
	}


def register_of(values: Row, *, in_liquidation: bool) -> RegisterData:
	return RegisterData(
		str(values.get("firma") or ""),
		str(values.get("sitz") or ""),
		str(values.get("register_court") or ""),
		str(values.get("register_number") or ""),
		in_liquidation,
	)


# Findings


def annual_findings(found: Iterable[Any], *, prior_year: bool = False) -> list[AnnualFinding]:
	"""The findings of the core as the table Befunde keeps them: the code and the severity, the sentence with its
	source, and as the reference the account, the position or the Angabe it is about; ``prior_year`` marks those of
	the books of the previous year, as steuerbote.hgb.statement marks its own."""
	findings = []
	for finding in found:
		source = getattr(finding, "reference", "") if hasattr(finding, "prior_year") else finding.source
		text = f"{finding.text} ({source})" if source and source not in finding.text else finding.text
		if prior_year:
			text = f"Vorjahr: {text}"
		reference = getattr(finding, "account", "") or getattr(finding, "concept", "") or ""
		findings.append(
			AnnualFinding(
				str(finding.code),
				AnnualSeverity.of(finding.severity),
				text,
				reference[:DATA_LENGTH],
			)
		)
	return findings


def prior_finding(has_prior: bool, founded_in_year: bool) -> tuple[AnnualFinding, ...]:
	"""An error where the books have no previous year, no Vorjahr by hand stands in and the company was not founded
	in the fiscal year: „In der Bilanz sowie in der Gewinn- und Verlustrechnung ist zu jedem Posten der entsprechende
	Betrag des vorhergehenden Geschäftsjahrs anzugeben.“ (§ 265 Abs. 2 Satz 1 HGB)"""
	if has_prior or founded_in_year:
		return ()
	return (
		AnnualFinding(
			Code.NO_PRIOR_YEAR,
			AnnualSeverity.ERROR,
			"Das Hauptbuch hat kein Vorjahr, und die Gesellschaft ist nicht im Geschäftsjahr gegründet: Tragen Sie die "
			"Beträge des letzten festgestellten Jahresabschlusses unter „Vorjahr von Hand“ ein (§ 265 Abs. 2 Satz 1 HGB).",
			"§ 265 Abs. 2 HGB",
		),
	)


def xbrl_code(code: str) -> bool:
	"""Whether a code is one of the file of the Offenlegung: of steuerbote/xbrl/checks.py or of steuerbote/hgb/instance.py."""
	return code.startswith(("XBRL-", "JA-XBRL-"))


# The inputs of the statement


def statement_data(
	found: Statements, prior: Sequence[Balance] | None, parents: Mapping[str, str], **options: Any
) -> str:
	"""What the statement the document files is built from, as the JSON the document keeps: its balances with the
	corrections, those of the previous year, and of the hierarchy of the taxonomy the part their concepts add up
	along, so that the XBRL of a festgestellter Jahresabschluss is built from the figures it was festgestellt with,
	whatever the books say later."""
	concepts = {balance.concept for balance in (*found.balances, *(prior or ()))}
	chains: dict[str, str] = {}
	for concept in concepts:
		current = concept
		while current in parents and current not in chains:
			chains[current] = parents[current]
			current = parents[current]
	presentation = options.get("presentation", ProfitPresentation.BEFORE_APPROPRIATION)
	net_income = options.get("prior_net_income")
	data = {
		"balances": [_balance_data(balance) for balance in found.balances],
		"prior": None if prior is None else [_balance_data(balance) for balance in prior],
		"prior_net_income": None if net_income is None else str(net_income),
		"parents": dict(sorted(chains.items())),
		"presentation": presentation.value,
	}
	return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def statement_from_data(text: str, year: int, size_class: SizeClass) -> AnnualStatement:
	"""The statement the document files, built again from the JSON statement_data wrote."""
	data = json.loads(text)
	prior = data["prior"]
	net_income = data["prior_net_income"]
	return build(
		year,
		size_class,
		tuple(_balance_of(entry) for entry in data["balances"]),
		parents=data["parents"],
		prior=None if prior is None else tuple(_balance_of(entry) for entry in prior),
		prior_net_income=None if net_income is None else Decimal(net_income),
		method=Method.GKV,
		presentation=PRESENTATIONS[data["presentation"]],
	)


def _balance_data(balance: Balance) -> list[Any]:
	term = balance.remaining_term
	return [
		balance.concept,
		str(balance.amount),
		balance.shareholder,
		term.value if term else None,
		balance.source,
	]


def _balance_of(entry: Sequence[Any]) -> Balance:
	concept, amount, shareholder, term, source = entry
	return Balance(concept, Decimal(amount), shareholder, RemainingTerm(term) if term else None, source)


# Feststellung


def filing_problems(
	name: str,
	rows: Sequence[Row],
	notes: Sequence[Row],
	register: RegisterData,
	*,
	size_class: SizeClass | None,
	adopted_on: date | None,
	to_date: date,
	today: date,
	codes: Collection[str],
	recalculate: str,
) -> tuple[Problem, ...]:
	"""What holds the Feststellung back, whatever is acknowledged: a calculation older than its entries, no size
	class, Aktiva and Passiva apart, a Jahresergebnis of the Bilanz other than that of the GuV, missing data of § 264
	Abs. 1a HGB, an Angabe of the catalogue not answered, an Eigenkapital of zero without its explanation, and no day
	of the Feststellung or one within the fiscal year or to come."""
	problems = []
	if recalculate in codes:
		problems.append(Problem(STALE, (name,)))
	if size_class is None:
		problems.append(Problem(NO_CLASS, (name,)))
	aktiva, passiva = reported(rows, AKTIVA_TOTAL) or ZERO, reported(rows, PASSIVA_TOTAL) or ZERO
	if aktiva != passiva:
		problems.append(Problem(NOT_BALANCED, (_euro(aktiva), _euro(passiva))))
	guv, bilanz = reported(rows, GUV_NET_INCOME), reported(rows, NET_INCOME)
	if guv is not None and bilanz is not None and guv != bilanz:
		problems.append(Problem(NET_INCOME_DIFFERS, (_euro(bilanz), _euro(guv))))
	problems.extend(Problem(REGISTER_MISSING, (finding.text,)) for finding in register_problems(register))
	problems.extend(_notes_problems(rows, notes, size_class))
	if adopted_on is None:
		problems.append(Problem(NOT_ADOPTED))
	elif adopted_on <= to_date:
		problems.append(Problem(ADOPTED_EARLY, (day_label(adopted_on), day_label(to_date))))
	elif adopted_on > today:
		problems.append(Problem(ADOPTED_LATER, (day_label(adopted_on),)))
	return tuple(problems)


def _notes_problems(rows: Sequence[Row], notes: Sequence[Row], size_class: SizeClass | None) -> list[Problem]:
	equity_zero = reported(rows, EQUITY) == ZERO
	entries = catalogue_of(size_class, equity_zero=equity_zero)
	if not entries:
		return []
	found = answer_problems(entries, answers_of(notes, ZERO))
	problems = []
	if any(finding.concept == ZERO_EQUITY_CODE for finding in found):
		problems.append(Problem(ZERO_EQUITY))
	others = [finding.text for finding in found if finding.concept != ZERO_EQUITY_CODE]
	if others:
		problems.append(Problem(NOTES_OPEN, (" ".join(others),)))
	return problems


# Ergebnisverwendung


@dataclass(frozen=True, slots=True)
class AppropriationAccounts:
	"""The accounts of the Ergebnisverwendung of a chart: the gesetzliche Rücklage, the andere Gewinnrücklagen and the
	Verbindlichkeiten gegenüber Gesellschaftern für offene Ausschüttungen."""

	legal_reserve: str
	other_reserves: str
	dividends: str


APPROPRIATION_ACCOUNTS = MappingProxyType(
	{
		"SKR03": AppropriationAccounts("0846", "0855", "0755"),
		"SKR04": AppropriationAccounts("2930", "2960", "3519"),
	}
)
"""The accounts of the DATEV charts „Gültig für 2026“, SKR 03 (Art.-Nr. 11174) and SKR 04 (Art.-Nr. 11175): 0846 and
2930 „Gesetzliche Rücklage“, 0855 and 2960 „Andere Gewinnrücklagen“, 0755 and 3519 „Verbindlichkeiten gegenüber
Gesellschaftern für offene Ausschüttungen“."""


@dataclass(frozen=True, slots=True)
class Appropriation:
	"""The Ergebnisverwendung the shareholders resolve with the Feststellung (§ 42a Abs. 2 Satz 1, § 29 GmbHG): what
	goes into the Gewinnrücklagen, for an UG into the gesetzliche Rücklage, and what is distributed, of the
	Jahresergebnis with the Gewinnvortrag or Verlustvortrag; the rest is carried forward."""

	net_income: Decimal
	carried_forward: Decimal
	reserve: Decimal = ZERO
	dividend: Decimal = ZERO
	ug: bool = False

	@property
	def bilanzgewinn(self) -> Decimal:
		return self.net_income + self.carried_forward

	@property
	def minimum_reserve(self) -> Decimal:
		"""What an UG puts into its gesetzliche Rücklage at least (§ 5a Abs. 3 Satz 1 GmbHG), nothing for a GmbH."""
		return ug_reserve_minimum(self.net_income, self.carried_forward) if self.ug else ZERO

	@property
	def carried(self) -> Decimal:
		"""Vortrag auf neue Rechnung."""
		return self.bilanzgewinn - self.reserve - self.dividend


def appropriation_problems(appropriation: Appropriation, *, calculated: bool = True) -> tuple[Problem, ...]:
	"""What a save refuses: a negative amount, and, once Berechnen has given the Bilanzgewinn, more distributed than it
	holds, „Die Gesellschafter haben Anspruch auf den Jahresüberschuß zuzüglich eines Gewinnvortrags und abzüglich eines
	Verlustvortrags“ (§ 29 Abs. 1 Satz 1 GmbHG)."""
	negative = [_euro(amount) for amount in (appropriation.reserve, appropriation.dividend) if amount < ZERO]
	if negative:
		return (Problem(NEGATIVE_APPROPRIATION, (", ".join(negative),)),)
	used = appropriation.reserve + appropriation.dividend
	if calculated and used and used > max(appropriation.bilanzgewinn, ZERO):
		return (Problem(APPROPRIATION_TOO_HIGH, (_euro(used), _euro(appropriation.bilanzgewinn))),)
	return ()


def appropriation_findings(appropriation: Appropriation) -> tuple[AnnualFinding, ...]:
	"""An error where an UG puts less than the quarter of § 5a Abs. 3 Satz 1 GmbHG into its gesetzliche Rücklage."""
	if appropriation.reserve >= appropriation.minimum_reserve:
		return ()
	return (
		AnnualFinding(
			Code.UG_RESERVE,
			AnnualSeverity.ERROR,
			f"Eine UG (haftungsbeschränkt) stellt ein Viertel des um einen Verlustvortrag geminderten "
			f"Jahresüberschusses in die gesetzliche Rücklage ein, hier mindestens {_euro(appropriation.minimum_reserve)}; "
			f"die Ergebnisverwendung nennt {_euro(appropriation.reserve)} (§ 5a Abs. 3 Satz 1 GmbHG).",
			"§ 5a Abs. 3 GmbHG",
		),
	)


@dataclass(frozen=True, slots=True)
class EntryRow:
	"""A row of the draft Journal Entry of the Ergebnisverwendung: an account number, debit or credit, and why."""

	account: str
	debit: Decimal
	credit: Decimal
	remark: str


def appropriation_rows(
	appropriation: Appropriation,
	accounts: AppropriationAccounts,
	closing_account: str,
	*,
	reserve_in_books: bool,
) -> tuple[EntryRow, ...]:
	"""The rows of the draft Journal Entry of the Ergebnisverwendung: the closing account, which holds the result
	and the Gewinnvortrag, gives what goes into the reserves and what is distributed. A balance sheet drawn up after
	part of the appropriation holds the reserve of the year in the books already (§ 268 Abs. 1 Satz 2 HGB), so the
	entry then posts the distribution alone."""
	reserve = ZERO if reserve_in_books else appropriation.reserve
	if not reserve and not appropriation.dividend:
		raise BridgeError(NO_APPROPRIATION)
	rows = [EntryRow(closing_account, reserve + appropriation.dividend, ZERO, "Ergebnisverwendung")]
	if reserve:
		account = accounts.legal_reserve if appropriation.ug else accounts.other_reserves
		label = (
			"Einstellung in die gesetzliche Rücklage"
			if appropriation.ug
			else "Einstellung in andere Gewinnrücklagen"
		)
		rows.append(EntryRow(account, ZERO, reserve, label))
	if appropriation.dividend:
		rows.append(
			EntryRow(accounts.dividends, ZERO, appropriation.dividend, "Ausschüttung an die Gesellschafter")
		)
	return tuple(rows)


# Übermittlung and Einstellung


def transmission_record_problems(
	*,
	adopted_on: date | None,
	transmitted_on: date,
	today: date,
	signatures: tuple[Signature, ...],
	mode: Mode,
	notice: bool,
	order_number: str,
) -> tuple[Problem, ...]:
	"""What the Übermittlung needs: a day not to come, after the Feststellung, a dated signature (steuerbote.hgb
	.disclosure.transmission_problems), the box of the Hinterlegung for one, and the Auftragsnummer."""
	problems = []
	if transmitted_on > today:
		problems.append(Problem(TRANSMITTED_LATER, (day_label(transmitted_on),)))
	problems.extend(
		Problem(TRANSMISSION_REFUSED, (finding.text,))
		for finding in transmission_problems(adopted_on, transmitted_on, signatures)
	)
	if mode is Mode.HINTERLEGUNG and not notice:
		problems.append(Problem(NO_NOTICE))
	if not order_number.strip():
		problems.append(Problem(NO_ORDER_NUMBER))
	return tuple(problems)


def publication_record_problems(transmitted_on: date, published_on: date, today: date) -> tuple[Problem, ...]:
	"""What the Einstellung needs: a day after the Übermittlung and not to come."""
	if published_on < transmitted_on:
		return (Problem(PUBLISHED_EARLY, (day_label(published_on), day_label(transmitted_on))),)
	if published_on > today:
		return (Problem(PUBLISHED_LATER, (day_label(published_on),)),)
	return ()


# Offenlegung


def mode_of(value: object, size_class: SizeClass | None) -> Mode:
	"""How the document discloses: a Kleinst as its field says, the default of the settings or of steuerbote.hgb
	.disclosure without one; every other class publishes (§ 326 Abs. 2 HGB)."""
	if size_class is not SizeClass.KLEINST:
		if value == DisclosureMode.HINTERLEGUNG:
			raise BridgeError(HINTERLEGUNG_FOR_KLEINST, size_class.value if size_class else NO_CLASS_YET)
		return Mode.OFFENLEGUNG
	return MODES[DisclosureMode(value)] if value else Mode.HINTERLEGUNG


def stored_mode(mode: Mode) -> str:
	return next(stored for stored, core in MODES.items() if core is mode).value


def deposit_finding(size_class: SizeClass | None, mode: Mode) -> tuple[AnnualFinding, ...]:
	"""A hint where a Kleinst publishes what it could deposit (§ 326 Abs. 2 HGB)."""
	if size_class is not SizeClass.KLEINST or mode is Mode.HINTERLEGUNG:
		return ()
	return (
		AnnualFinding(
			Code.DEPOSIT,
			AnnualSeverity.HINT,
			"Die Kleinstkapitalgesellschaft veröffentlicht ihre Bilanz, die sie auch hinterlegen könnte; hinterlegt "
			"ist sie nur auf Antrag einsehbar (§ 326 Abs. 2, § 9 Abs. 6 Satz 3 HGB).",
			"§ 326 Abs. 2 HGB",
		),
	)


# XBRL


def periods_of(from_date: date, to_date: date, prior_from: date | None, prior_to: date | None) -> Periods:
	"""The fiscal year and, where the statement has one, the previous year (§ 265 Abs. 2 Satz 1 HGB)."""
	return Periods(from_date, to_date, None, prior_from, prior_to)


def prior_period(from_date: date, books: tuple[date, date] | None) -> tuple[date, date]:
	"""The previous fiscal year: that of the books where they have one, else the twelve months before the fiscal
	year, as a Vorjahr by hand of a company new to ERPNext has no Fiscal Year."""
	if books is not None:
		return books
	try:
		start = from_date.replace(year=from_date.year - 1)
	except ValueError:
		start = date(from_date.year - 1, 2, 28)
	return start, from_date - timedelta(days=1)


def address_of(address: settings_rules.Address) -> Address | None:
	"""The address of the settings as the GCD states it, None without street, number, postal code and town."""
	number = (address.house_number or "") + (address.house_number_suffix or "")
	if not (address.street and number and address.postal_code and address.city):
		return None
	country = "Deutschland" if address.in_germany else address.country
	return Address(address.street, number, address.postal_code, address.city, country)


def notes_of(
	register: RegisterData, answers: tuple[NoteAnswer, ...], signatures: tuple[Signature, ...]
) -> Notes:
	"""The Angaben of the XBRL: the register data, the answers and the signatures; the Haftungsverhältnisse and the
	Vorschüsse stand in the texts and amounts of their answers."""
	return Notes(register, answers, (), (), signatures)


def master_data(
	periods: Periods,
	adopted_on: date,
	address: Address | None,
	*,
	founded_on: date | None,
	generated_on: date | None,
	changed: bool,
) -> MasterData:
	"""The GCD of the XBRL; a Jahresabschluss that amends one transmitted before is a changed one, „Wird der
	Jahresabschluss [...] geändert, so ist auch die Änderung [...] offenzulegen“ (§ 325 Abs. 1b Satz 1 HGB)."""
	return MasterData(
		periods,
		adopted_on,
		address,
		founded_on=founded_on,
		generated_on=generated_on,
		revision=RevisionStatus.CHANGED if changed else RevisionStatus.FIRST,
	)


def _euro(amount: Decimal) -> str:
	"""An amount in euros and cents as a German text writes it, such as 1.234,56 €."""
	text = f"{amount:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
	return f"{text} €"


def _number(value: Decimal) -> str:
	return f"{value.normalize():f}".replace(".", ",")
