"""The Anlagenspiegel (brutto) of the E-Bilanz from the rows of the assets: a row per position of the Anlagevermögen and
value type, the rows above it, the columns of its value development, and the checks of the Technischer Leitfaden.

„Für Wirtschaftsjahre, die nach dem 31. Dezember 2016 beginnen, ist der „Anlagenspiegel (brutto)“ [table.nt.ass.gross]
zu übermitteln.“ (Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025, B.14.12.1; BMF letters of 24 May 2016,
BStBl I S. 500, and of 10 June 2025), for every size of company: the relief of § 288 Abs. 1 Nr. 1 HGB is one of the
Offenlegung. Its Kurzform, „Anlagenspiegel (brutto), Kurzform“ [cube_.nt.ass.gross_short], is not admitted: „Es wird nur
noch der „Anlagenspiegel (brutto)“ zugelassen.“ (rule 170405047), so Steuerbote writes none.

Rows. The Frappe layer gives a Row per asset category and value type from the Asset module of ERPNext, the columns of
the report „Asset Depreciations and Balances“: the Anschaffungs- und Herstellungskosten at the beginning, the
additions, the disposals and the depreciation at the beginning, of the year and on the disposals, each on the position
the fixed asset account of the category maps to. What the Asset module does not book by category the company enters
by hand, with its reason: Umbuchungen, Zuschreibungen, außerplanmäßige Abschreibungen, Sonderabschreibungen, the
Herabsetzung of § 7g Abs. 2 EStG and the Abzug of § 6b EStG, and a row by hand needs one as well. Rows of the same
position and value type add up. Each row is a member of „Positionen des Anlagevermögens“ [dim_changes.nt.ass.gross]
(steuerbote.ebilanz.positions.Structure.rows), each value type a member of „steuerliche Überleitung“ [dim_taxTrans]:
the Handelsbilanzwert, the Steuerbilanzwert or the Überleitungswert (A.14.2.2).

Rows above. „Alle Angaben zu einer gegebenen Position der Wertentwicklung werden der Oberpositions- und rechnerischen
Prüfung unterzogen. Als Grundlage dienen die übereinstimmenden Positionshierarchien der Berichtsteile „Bilanz“ und
„Anhang“.“ (B.14.12.1 b): each row adds up to the row of the position above it in the calculation of the Bilanz, up to
the Anlagevermögen [bs.ass.fixAss]. An E-Bilanz without fixed assets sends that row with a Buchwert of zero, as the
Eröffnungsbilanz of the ERiC documentation 44.3.6.0 (SteuerbilanzAutoverkaeufer-Eroeffnung_PersG.xml) does: an
announced component has a valued fact (B.9.2).

Columns. The primary items of the value development add up as the calculation of the Anhang says (steuerbote.ebilanz.
positions.Structure.columns): the Anschaffungs- und Herstellungskosten at the end of the period, the cumulated
depreciation, the depreciation of the period with its kinds, and the Buchwert at the end of the period, „Buchwert zum
Ende der Periode“ [all] = gross ./. accDepr + revaluation. „Liegt zu einer Kombination von Dimensionswertekombinationen
... eine werthaltige Angabe vor, so sind für ebendiese Dimensionswertekombination ... alle gültigen Mussfelder der
Wertentwicklung zu berichten (nicht notwendigerweise werthaltig)“ (B.14.12.1 a): NIL where a row has none. A previous
Buchwert given makes „Buchwert zum Ende der Vorperiode“ [all_Prev_period].

Value types. „Wird für die Position Bilanzierungsstandard die Ausprägung „deutsches Handelsrecht (sog. Einheitsbilanz)“
... angegeben ... Im Anlagenspiegel sind einheitlich die „Steuerbilanzwerte“ [dim_taxBal] zu übermitteln.
„Handelsbilanzwerte“ [dim_comBal] oder „Überleitungswerte“ [dim_diffComToTaxBal] sind nicht zulässig.“ (f), and a
Steuerbilanz under „deutsches Steuerrecht“ gives Steuerbilanzwerte as well (g). A Handelsbilanz gives
Handelsbilanzwerte, and with Überleitungswerte the Steuerbilanzwerte too, which Steuerbote derives: „muss sich aus ihnen
rechnerisch der unter „Steuerbilanzwert“ [dim_taxBal] berichtete Wert ergeben“ (c, d). A position „steuerlich“ not
permitted is no row of a Steuerbilanz (steuerbote/ebilanz/positions.py); in a Handelsbilanz its Handelsbilanzwert and
Überleitungswert add up to zero, and its Steuerbilanzwert is sent with that zero: „Werden im Anlagenspiegel für eine als
„steuerlich“ unzulässig (notPermittedFor) gekennzeichnete Position ... Steuerbilanzwerte ... berichtet, so müssen diese
gleich 0 sein.“ (i) ERiC 44.3.6.0 wants it: without it structural error 170185133 refuses the Anlagenspiegel, and
170165096 refuses a Steuerbilanzwert of such a position only outside the tables (validation of Bilanz_6.9).

Checks. The Buchwert at the end of each row is the value of its position in the Bilanz, the Handelsbilanzwert that of
the Handelsbilanz, the Steuerbilanzwert that of the Steuerbilanz after the Überleitung, where the Bilanz reports the
position (e to g; structural error 170185136). „Anschaffungs- und Herstellungskosten zum Anfang der Periode ./.
Kumulierte Abschreibungen zum Anfang der Periode = Buchwert zum Ende der Vorperiode“ where the previous Buchwert is
given (h; structural error 170185137). In the first fiscal year of a company every value at the beginning of the
period is zero, as nothing was acquired before it. A row of a position not of the legal form is none (j).

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from steuerbote.ebilanz.positions import (
	FIXED_ASSETS,
	Finding,
	Structure,
	euro,
	leitfaden,
	qualified,
	rule,
	unqualified,
)
from steuerbote.ustva.rounding import CENT, ZERO
from steuerbote.xbrl.facts import Item, Period, amount, nil
from steuerbote.xbrl.taxonomy import BALANCE_SHEET, NOT_PERMITTED_FISCAL

CHANGES = "de-gaap-ci:dim_changes.nt.ass.gross"
TAX_TRANSFER = "de-gaap-ci:dim_taxTrans"
BOOK_VALUE = "de-gaap-ci:all"
PRIOR_BOOK_VALUE = "de-gaap-ci:all_Prev_period"
COST_BEGINNING = "de-gaap-ci:grossCost.beginning"
DEPRECIATION_BEGINNING = "de-gaap-ci:accDepr.beginning"
EXPLAINED = (
	"docs/roadmap.md, Grundsätze: „Eine Abweichung muss erklärt sein, bevor die Meldung abgegeben wird“"
)


class ValueType(StrEnum):
	"""The members of „steuerliche Überleitung“ [dim_taxTrans] (Leitfaden A.14.2.2)."""

	HANDELSBILANZ = "de-gaap-ci:dim_comBal"
	UEBERLEITUNG = "de-gaap-ci:dim_diffComToTaxBal"
	STEUERBILANZ = "de-gaap-ci:dim_taxBal"

	@property
	def label(self) -> str:
		return {
			ValueType.HANDELSBILANZ: "Handelsbilanzwert",
			ValueType.UEBERLEITUNG: "Überleitungswert",
			ValueType.STEUERBILANZ: "Steuerbilanzwert",
		}[self]


COLUMNS = {
	"cost_begin": "de-gaap-ci:grossCost.beginning",
	"additions": "de-gaap-ci:gross.addition",
	"disposals": "de-gaap-ci:gross.release",
	"transfers": "de-gaap-ci:gross.movements",
	"writeups": "de-gaap-ci:revaluation",
	"depreciation_begin": "de-gaap-ci:accDepr.beginning",
	"depreciation_regular": "de-gaap-ci:accDepr.DeprPeriod.regular",
	"depreciation_extraordinary": "de-gaap-ci:accDepr.DeprPeriod.extraordinary",
	"depreciation_special": "de-gaap-ci:accDepr.DeprPeriod.impairment",
	"depreciation_7g": "de-gaap-ci:accDepr.DeprPeriod.EStG7g_2",
	"depreciation_6b": "de-gaap-ci:accDepr.DeprPeriod.EStG6b_3",
	"depreciation_other": "de-gaap-ci:accDepr.DeprPeriod.misc",
	"depreciation_additions": "de-gaap-ci:accDepr.addition",
	"depreciation_disposals": "de-gaap-ci:accDepr.release",
	"depreciation_transfers": "de-gaap-ci:accDepr.movements",
	"prior_book_value": "de-gaap-ci:all_Prev_period",
}
"""Each field of a Row with the column of the value development it fills."""
MANUAL = frozenset(
	{
		"transfers",
		"writeups",
		"depreciation_extraordinary",
		"depreciation_special",
		"depreciation_7g",
		"depreciation_6b",
		"depreciation_other",
		"depreciation_additions",
		"depreciation_transfers",
	}
)
"""The columns the report „Asset Depreciations and Balances“ of ERPNext does not give, which the company enters by hand
with its reason."""


@dataclass(frozen=True, slots=True)
class Row:
	"""A row of the Anlagenspiegel: a position of the Anlagevermögen, a value type and the amounts of its columns in
	euros and cents, None where the row has none; ``source`` is the asset category it comes from, empty for a row by
	hand, and ``reason`` says why the columns by hand and a row by hand have their amounts."""

	position: str
	value_type: ValueType = ValueType.STEUERBILANZ
	cost_begin: Decimal | None = None
	additions: Decimal | None = None
	disposals: Decimal | None = None
	transfers: Decimal | None = None
	writeups: Decimal | None = None
	depreciation_begin: Decimal | None = None
	depreciation_regular: Decimal | None = None
	depreciation_extraordinary: Decimal | None = None
	depreciation_special: Decimal | None = None
	depreciation_7g: Decimal | None = None
	depreciation_6b: Decimal | None = None
	depreciation_other: Decimal | None = None
	depreciation_additions: Decimal | None = None
	depreciation_disposals: Decimal | None = None
	depreciation_transfers: Decimal | None = None
	prior_book_value: Decimal | None = None
	source: str = ""
	reason: str = ""

	def __post_init__(self) -> None:
		object.__setattr__(self, "position", qualified(self.position))
		object.__setattr__(self, "value_type", ValueType(self.value_type))
		for name in COLUMNS:
			value = getattr(self, name)
			if value is not None and (
				isinstance(value, bool) or not isinstance(value, Decimal) or value != value.quantize(CENT)
			):
				raise ValueError(
					f"the {name} of the row {self.position} is no amount in euros and cents: {value!r}"
				)

	def amounts(self) -> dict[str, Decimal]:
		"""The columns the row fills, by concept."""
		return {COLUMNS[name]: value for name in COLUMNS if (value := getattr(self, name)) is not None}

	@property
	def manual(self) -> tuple[str, ...]:
		"""The columns by hand the row fills with an amount other than zero."""
		return tuple(name for name in sorted(MANUAL) if getattr(self, name))


@dataclass(frozen=True, slots=True)
class Line:
	"""A row as the Anlagenspiegel sends it: a position, a value type and every column, None for none."""

	position: str
	value_type: ValueType
	values: Mapping[str, Decimal | None]
	rows: tuple[Row, ...] = ()
	"""The rows of the assets behind it; none for a row that adds up the rows below it."""

	@property
	def book_value(self) -> Decimal | None:
		return self.values.get(BOOK_VALUE)

	@property
	def dimensions(self) -> tuple[tuple[str, str], ...]:
		return ((CHANGES, self.position), (TAX_TRANSFER, self.value_type.value))


@dataclass(frozen=True)
class Anlagenspiegel:
	"""The rows of the Anlagenspiegel with what its checks found."""

	structure: Structure
	lines: tuple[Line, ...]
	findings: tuple[Finding, ...]
	_required: frozenset[str] = field(init=False, repr=False, compare=False)

	def __post_init__(self) -> None:
		begin = self.structure.case.periods.fiscal_year_begin
		closing = (
			self.structure.case.periods.balance_sheet_date or self.structure.case.periods.fiscal_year_end
		)
		object.__setattr__(
			self,
			"_required",
			frozenset(
				column.concept
				for column in self.structure.columns
				if column.mark.required
				and self.structure.taxonomy.concepts[column.concept].required_for(begin, closing)
			),
		)

	def facts(self) -> tuple[Item, ...]:
		"""Each column of each row over the fiscal year in its scenario, NIL for a Mussfeld without an amount
		(Leitfaden B.14.12.1 a)."""
		items = []
		for line in self.lines:
			for column in self.structure.columns:
				value = line.values.get(column.concept)
				if value is not None:
					items.append(amount(column.concept, Period.WIRTSCHAFTSJAHR, value, line.dimensions))
				elif column.concept in self._required:
					items.append(nil(column.concept, Period.WIRTSCHAFTSJAHR, line.dimensions))
		return tuple(items)

	def line(self, position: str, value_type: ValueType = ValueType.STEUERBILANZ) -> Line | None:
		return next(
			(
				line
				for line in self.lines
				if line.position == qualified(position) and line.value_type is ValueType(value_type)
			),
			None,
		)


def anlagenspiegel(
	structure: Structure,
	rows: Iterable[Row],
	*,
	handelsbilanz: Mapping[tuple[str, Period], Decimal],
	steuerbilanz: Mapping[tuple[str, Period], Decimal] | None = None,
	first_year: bool = False,
) -> Anlagenspiegel:
	"""The Anlagenspiegel of the rows of the assets, checked against the amounts of the Bilanz: ``handelsbilanz``
	those the Bilanz reports, ``steuerbilanz`` those after the Überleitung of a Handelsbilanz, by default the same.
	``first_year`` marks the first fiscal year of the company, whose values at the beginning are zero."""
	case = structure.case
	steuerbilanz = handelsbilanz if steuerbilanz is None else steuerbilanz
	findings: list[Finding] = []
	types = (
		(ValueType.HANDELSBILANZ, ValueType.UEBERLEITUNG)
		if not case.steuerbilanz
		else (ValueType.STEUERBILANZ,)
	)
	kept: list[Row] = []
	for row in rows:
		problem = _refused(structure, row, types)
		if problem is not None:
			findings.append(problem)
		else:
			kept.append(row)
		findings.extend(_unexplained(structure, row))
		if first_year:
			findings.extend(_begun(structure, row))
	if not kept:
		kept.append(Row(FIXED_ASSETS, types[0], source="Anlagevermögen ohne Anlagen"))
	leaves: dict[tuple[str, ValueType], dict[str, Decimal]] = {}
	behind: dict[tuple[str, ValueType], list[Row]] = {}
	for row in kept:
		values = leaves.setdefault((row.position, row.value_type), {})
		for concept, value in row.amounts().items():
			values[concept] = values.get(concept, ZERO) + value
		behind.setdefault((row.position, row.value_type), []).append(row)
	if ValueType.UEBERLEITUNG in {value_type for _, value_type in leaves}:
		_derive_steuerbilanz(leaves)
	summed = _summed_rows(structure, leaves)
	lines = []
	for position in structure.rows:
		for value_type in ValueType:
			key = (position, value_type)
			if key not in summed:
				continue
			values = _columns(structure, summed[key])
			if not any(value is not None for value in values.values()):
				values[BOOK_VALUE] = ZERO
			lines.append(Line(position, value_type, values, tuple(behind.get(key, ()))))
	findings.extend(_not_permitted(structure, summed))
	for line in lines:
		findings.extend(_checked(structure, line, handelsbilanz, steuerbilanz))
	return Anlagenspiegel(structure, tuple(lines), tuple(findings))


def _refused(structure: Structure, row: Row, types: tuple[ValueType, ...]) -> Finding | None:
	taxonomy = structure.taxonomy
	name = unqualified(row.position)
	if row.position not in structure.rows:
		label = taxonomy.label(row.position) if taxonomy.has(row.position) else name
		return Finding(
			"EB-ANLAGENSPIEGEL-ZEILE",
			f"„{label}“ ist keine Zeile des Anlagenspiegels dieser E-Bilanz: keine Position des Anlagevermögens, nicht "
			"für die Rechtsform oder, in einer Steuerbilanz, steuerlich nicht zulässig.",
			leitfaden(taxonomy, "B.14.12.1 j"),
			name,
		)
	if row.value_type not in types:
		standard = structure.case.accounting_standard.value
		return Finding(
			"EB-ANLAGENSPIEGEL-WERT",
			f"Die Zeile „{taxonomy.label(row.position)}“ meldet {row.value_type.label}e; unter dem Bilanzierungsstandard "
			f"{standard} nimmt der Anlagenspiegel "
			+ (
				"nur Steuerbilanzwerte."
				if structure.case.steuerbilanz
				else "Handelsbilanzwerte und Überleitungswerte, aus denen Steuerbote die Steuerbilanzwerte ableitet."
			),
			leitfaden(taxonomy, "B.14.12.1 c, d, f, g"),
			name,
		)
	return None


def _unexplained(structure: Structure, row: Row) -> Iterable[Finding]:
	"""A column by hand and a row by hand say why."""
	if row.reason.strip():
		return
	taxonomy = structure.taxonomy
	name = unqualified(row.position)
	label = taxonomy.label(row.position) if taxonomy.has(row.position) else name
	if not row.source.strip():
		yield Finding(
			"EB-ANLAGENSPIEGEL-BEGRUENDUNG",
			f"Die Zeile „{label}“ ist von Hand und braucht eine Begründung.",
			EXPLAINED,
			name,
		)
	elif row.manual:
		columns = ", ".join(taxonomy.label(COLUMNS[name_]) for name_ in row.manual)
		yield Finding(
			"EB-ANLAGENSPIEGEL-BEGRUENDUNG",
			f"Die Zeile „{label}“ aus {row.source} hat Beträge von Hand ({columns}) und braucht eine Begründung.",
			EXPLAINED,
			name,
		)


def _begun(structure: Structure, row: Row) -> Iterable[Finding]:
	taxonomy = structure.taxonomy
	for name in ("cost_begin", "depreciation_begin", "prior_book_value"):
		value = getattr(row, name)
		if value:
			yield Finding(
				"EB-ANLAGENSPIEGEL-ANFANG",
				f"Im ersten Wirtschaftsjahr hat „{taxonomy.label(row.position)}“ zu „{taxonomy.label(COLUMNS[name])}“ "
				f"{euro(value)}; vor dem ersten Wirtschaftsjahr gab es kein Anlagevermögen.",
				leitfaden(taxonomy, "B.14.12.1 h"),
				unqualified(row.position),
			)


def _derive_steuerbilanz(leaves: dict[tuple[str, ValueType], dict[str, Decimal]]) -> None:
	"""The Steuerbilanzwerte of a Handelsbilanz: its Handelsbilanzwerte plus the Überleitungswerte (Leitfaden
	B.14.12.1 c, d)."""
	positions = {position for position, _ in leaves}
	for position in positions:
		values: dict[str, Decimal] = {}
		for value_type in (ValueType.HANDELSBILANZ, ValueType.UEBERLEITUNG):
			for concept, value in leaves.get((position, value_type), {}).items():
				values[concept] = values.get(concept, ZERO) + value
		leaves[(position, ValueType.STEUERBILANZ)] = values


def _summed_rows(
	structure: Structure, leaves: Mapping[tuple[str, ValueType], Mapping[str, Decimal]]
) -> dict[tuple[str, ValueType], dict[str, Decimal]]:
	"""The rows with those above them, each the sum of the rows under it in the calculation of the Bilanz."""
	calculation = structure.taxonomy.calculation[BALANCE_SHEET]
	rows = frozenset(structure.rows)
	summed: dict[tuple[str, ValueType], dict[str, Decimal]] = {}
	for (position, value_type), values in leaves.items():
		current, weight = position, Decimal(1)
		while True:
			target = summed.setdefault((current, value_type), {})
			for concept, value in values.items():
				target[concept] = target.get(concept, ZERO) + weight * value
			arcs = calculation.parents(current)
			if current == qualified(FIXED_ASSETS) or not arcs or arcs[0].parent not in rows:
				break
			weight *= arcs[0].weight or Decimal(1)
			current = arcs[0].parent
	return summed


def _columns(structure: Structure, given: Mapping[str, Decimal]) -> dict[str, Decimal | None]:
	"""Every column of a row: the amounts given, and each sum of the calculation of the Anhang from them."""
	values: dict[str, Decimal | None] = {}

	def column(concept: str) -> Decimal | None:
		if concept in values:
			return values[concept]
		parts = [
			child.weight * part
			for child in structure.columns
			if child.parent == concept and (part := column(child.concept)) is not None
		]
		own = given.get(concept)
		found = own if not parts else (own or ZERO) + sum(parts, ZERO)
		values[concept] = found
		return found

	for entry in structure.columns:
		column(entry.concept)
	return values


def _fiscally_not_permitted(structure: Structure, position: str, value_type: ValueType) -> bool:
	"""Whether the row is a Steuerbilanzwert of a position „steuerlich“ not permitted."""
	concept = structure.taxonomy.concepts[position]
	return value_type is ValueType.STEUERBILANZ and not concept.permitted_for(NOT_PERMITTED_FISCAL)


def _not_permitted(
	structure: Structure, summed: Mapping[tuple[str, ValueType], Mapping[str, Decimal]]
) -> Iterable[Finding]:
	"""A position „steuerlich“ not permitted has a Steuerbilanzwert of zero (Leitfaden B.14.12.1 i)."""
	taxonomy = structure.taxonomy
	for (position, value_type), values in summed.items():
		if not _fiscally_not_permitted(structure, position, value_type):
			continue
		book_value = _columns(structure, values).get(BOOK_VALUE) or ZERO
		if book_value:
			yield Finding(
				"EB-ANLAGENSPIEGEL-STEUERLICH",
				f"„{taxonomy.label(position)}“ ist steuerlich nicht zulässig; Handelsbilanzwert und Überleitungswert "
				f"ergeben zusammen {euro(book_value)} statt null.",
				f"{leitfaden(taxonomy, 'B.14.12.1 i')}; {rule(taxonomy, '170165096', 'Strukturelle Fehler')}",
				unqualified(position),
			)


def _checked(
	structure: Structure,
	line: Line,
	handelsbilanz: Mapping[tuple[str, Period], Decimal],
	steuerbilanz: Mapping[tuple[str, Period], Decimal],
) -> Iterable[Finding]:
	taxonomy = structure.taxonomy
	name = unqualified(line.position)
	if line.value_type is not ValueType.UEBERLEITUNG:
		balance = (steuerbilanz if line.value_type is ValueType.STEUERBILANZ else handelsbilanz).get(
			(line.position, Period.STICHTAG)
		)
		book_value = line.book_value or ZERO
		if balance is not None and balance != book_value:
			yield Finding(
				"170185136",
				f"Der {line.value_type.label} „Buchwert zum Ende der Periode“ von „{taxonomy.label(line.position)}“ ist "
				f"im Anlagenspiegel {euro(book_value)}, in der Bilanz {euro(balance)}.",
				f"{leitfaden(taxonomy, 'B.14.12.1 e bis g')}; {rule(taxonomy, '170185136', 'Strukturelle Fehler')}",
				name,
			)
	prior = line.values.get(PRIOR_BOOK_VALUE)
	if prior is not None:
		opening = (line.values.get(COST_BEGINNING) or ZERO) - (
			line.values.get(DEPRECIATION_BEGINNING) or ZERO
		)
		if opening != prior:
			yield Finding(
				"170185137",
				f"Zu „{taxonomy.label(line.position)}“ ergeben die Anschaffungs- und Herstellungskosten abzüglich der "
				f"kumulierten Abschreibungen zum Anfang der Periode {euro(opening)}, der Buchwert zum Ende der Vorperiode "
				f"ist {euro(prior)}.",
				f"{leitfaden(taxonomy, 'B.14.12.1 h')}; {rule(taxonomy, '170185137', 'Strukturelle Fehler')}",
				name,
			)
