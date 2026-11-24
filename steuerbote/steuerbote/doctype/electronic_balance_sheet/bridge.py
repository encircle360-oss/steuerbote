"""Pure Python between the Electronic Balance Sheet and the core of the E-Bilanz in steuerbote.ebilanz.

Nothing here imports Frappe. The controller (electronic_balance_sheet.py) reads the books, the assets, the settings and
the Bilanzzuordnung through steuerbote/ebilanz_sources.py, gives them to steuerbote.ebilanz.instance.build() and keeps
what it found in the tables and fields of the document; this module turns the one into the other, so that every rule
is tested without a bench:

- case_of, purpose_of, balance_book: the case of the E-Bilanz from the document, and which balance sheet and finance
  book its balances are read for. The Einheitsbilanz (HAOE) and the Handelsbilanz (HGBM) read the finance book of the
  Handelsbilanz, the Steuerbilanz (AO) that of the Steuerbilanz (Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand
  10.06.2025, „Leitfaden“, B.13); without one, the entries without a finance book.
- adjustments_of: the corrections of the positions and the lines by hand, each with its reason, as the Adjustments of
  steuerbote/ebilanz/calculation.py. They follow the „davon“ lines of the Bilanzzuordnung, so that a correction of a
  „davon“ position wins (steuerbote/balance_mapping_sync.py).
- by_category, category_rows and assets_of: the Anlagenspiegel from the report „Asset Depreciations and Balances“ of
  ERPNext, the assets summed up per asset category, a row per category on the position its fixed asset account goes
  to, with the columns the company enters by hand and their reason (steuerbote/ebilanz/anlagenspiegel.py);
  transfer_values the Überleitungswerte of a Handelsbilanz, asset by asset; asset_findings says which category leaves
  an adjustment of ERPNext out of its columns or has no position, schedule_findings which asset has no depreciation
  schedule in a book of the E-Bilanz or two.
- derived_transfers and transfers_of: the Überleitungsrechnung of a Handelsbilanz from the finance book of the
  Steuerbilanz, a Wertänderung per position whose balances differ between the two books, and the entries by hand.
- equity_of and equity_changes: what the Betriebsvermögensvergleich takes beyond the books.
- position_rows, account_rows, fixed_asset_rows, transfer_rows and totals: what Berechnen writes.
- sources_of and differences: the E-Bilanz of the document as it is stored, for the Nutzdaten, the XBRL file and the
  checks before them, and the positions whose stored amount it no longer gives.
- placement_findings and the findings of Steuerbote (CODES): the taxonomy, the depreciation not posted up to the
  Bilanzstichtag and the Period Closing Voucher.
- taxonomy_for: the version of the HGB-Taxonomie of the Wirtschaftsjahr, the one chosen while the Wirtschaftsjahr may
  take it, else the one it takes „grundsätzlich“ (steuerbote/xbrl/versions.py), 6.10 from 2027 on.

The findings of Steuerbote are German sentences with their source, as those of steuerbote.ebilanz are; their codes
begin with SB-. Errors are BridgeError with an English template and its values, which the Frappe layer translates;
MESSAGES lists the templates.
"""

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from steuerbote.balance_mapping_sync import DAVON_REASON
from steuerbote.ebilanz.anlagenspiegel import BOOK_VALUE, COLUMNS, MANUAL, Row, ValueType, anlagenspiegel
from steuerbote.ebilanz.calculation import (
	ASSETS,
	BVV,
	DEFICIT,
	EQUITY,
	EQUITY_AND_LIABILITIES,
	NET_INCOME,
	AccountBalance,
	Adjustment,
	EquityChanges,
	calculate,
)
from steuerbote.ebilanz.instance import EBilanz, Sources
from steuerbote.ebilanz.positions import (
	AccountingStandard,
	Case,
	Position,
	StatementType,
	Structure,
	euro,
	qualified,
	unqualified,
)
from steuerbote.ebilanz.ueberleitung import PREVIOUS_DIFFERENCE, Kind, Transfer, Ueberleitung
from steuerbote.jahresmeldung.findings import DATA_LENGTH, Finding, Severity
from steuerbote.jahresmeldung.overrides import Columns, correction_of, manual_lines, to_amount
from steuerbote.ustva.rounding import ZERO
from steuerbote.xbrl import versions
from steuerbote.xbrl.facts import Period, Periods
from steuerbote.xbrl.mapping import Placement, Purpose
from steuerbote.xbrl.taxonomy import Balance

LINE_COLUMNS = Columns(
	key="concept",
	amounts=("computed", "ledger_amount", "tax_amount"),
	described=("label", "component", "mark", "depth", "parent_concept", "davon_of", "nil"),
	correction="correction",
	reason="correction_reason",
	reported="reported",
	manual="manual",
)
"""The columns of the table Positionen: the position, the amount Berechnen computed without a correction of the
position itself, the amount of the books and that of the Steuerbilanz, what describes the position, the correction
with its reason, the amount it reports and the mark of a line by hand (steuerbote.jahresmeldung.overrides)."""

JAHRESABSCHLUSS = "Jahresabschluss"
EROEFFNUNGSBILANZ = "Eröffnungsbilanz"
STATEMENT_TYPES = MappingProxyType(
	{JAHRESABSCHLUSS: StatementType.JAHRESABSCHLUSS, EROEFFNUNGSBILANZ: StatementType.EROEFFNUNGSBILANZ}
)
"""The Bilanzart of the document, as the field statement_type holds it, by the Bilanzart of the GCD."""
PURPOSES = MappingProxyType(
	{
		AccountingStandard.EINHEITSBILANZ: Purpose.BOTH,
		AccountingStandard.HANDELSBILANZ: Purpose.COMMERCIAL,
		AccountingStandard.STEUERBILANZ: Purpose.TAX,
	}
)
VALUE_TYPES = MappingProxyType(
	{"StB": ValueType.STEUERBILANZ, "HB": ValueType.HANDELSBILANZ, "Überleitung": ValueType.UEBERLEITUNG}
)
"""The value types of a row of the Anlagenspiegel, as the field value_type holds them (Leitfaden A.14.2.2)."""
TRANSFER_KINDS = MappingProxyType(
	{
		"Wertänderung": Kind.WERTAENDERUNG,
		"Umgliederung": Kind.UMGLIEDERUNG,
		"Umgliederung und Wertänderung": Kind.BEIDES,
	}
)
"""The kinds of an entry of the Überleitungsrechnung, as the field kind holds them (Leitfaden A.11)."""
COMPONENTS = ("B", "GuV", BVV)
DERIVED_REASON = "Unterschied der Salden im Finanzbuch der Steuerbilanz zu denen der Handelsbilanz"
"""Why an entry of the Überleitung that the finance book of the Steuerbilanz gives has its amounts."""
COMPUTED_COLUMNS = (
	"cost_begin",
	"additions",
	"disposals",
	"depreciation_begin",
	"depreciation_regular",
	"depreciation_disposals",
)
"""The columns of a row of the Anlagenspiegel that the report Asset Depreciations and Balances gives."""
MANUAL_COLUMNS = tuple(name for name in COLUMNS if name in MANUAL)
"""The columns of a row the company enters by hand, with its reason (steuerbote.ebilanz.anlagenspiegel.MANUAL)."""
ROW_COLUMNS = (*COMPUTED_COLUMNS, *MANUAL_COLUMNS)
END_COLUMNS = MappingProxyType(
	{"cost_end": "de-gaap-ci:gross", "depreciation_end": "de-gaap-ci:accDepr", "book_value_end": BOOK_VALUE}
)
"""The values at the end of the period a row shows, by the column of the value development that gives them."""
EQUITY_POSITIONS = f"{EQUITY}."
LEITFADEN = "Technischer Leitfaden zur HGB-Taxonomie 6.9"
ELLIPSIS = "…"

NO_STATEMENT_TYPE = "{0} is no Bilanzart of the E-Bilanz: it is Jahresabschluss or Eröffnungsbilanz."
NO_ACCOUNTING_STANDARD = "{0} is no Bilanzierungsstandard of the E-Bilanz: it is HAOE, HGBM or AO."
NO_VALUE_TYPE = "Row {0} of the Anlagenspiegel: {1} is no value type; it is StB, HB or Überleitung."
NO_KIND = "Row {0} of the Überleitungsrechnung: {1} is no kind of the Überleitung."
DOUBLED = "Row {0} of the Positions: Calculate reports {1} already; correct its row instead."
NO_POSITION = "Row {0} of {1} names no position."
MESSAGES = (NO_STATEMENT_TYPE, NO_ACCOUNTING_STANDARD, NO_VALUE_TYPE, NO_KIND, NO_POSITION, DOUBLED)
POSITIONS = "Positions"
ACCOUNTS = "Account Balances"
TRANSFERS = "Überleitungsrechnung"
TABLES = (POSITIONS, ACCOUNTS, TRANSFERS)
"""The tables a message names, by their labels, which the Frappe layer translates."""
TAXONOMY_CODE = "SB-TAXONOMIE"
ASSET_POSITION = "SB-ANLAGE-POSITION"
ASSET_ADJUSTMENT = "SB-ANLAGE-ANPASSUNG"
DEPRECIATION_OPEN = "SB-AFA-OFFEN"
NO_SCHEDULE = "SB-ANLAGE-PLAN"
TWO_SCHEDULES = "SB-ANLAGE-DOPPELT"
NO_CLOSING = "SB-PERIODENABSCHLUSS"
CODES = (
	TAXONOMY_CODE,
	ASSET_POSITION,
	ASSET_ADJUSTMENT,
	DEPRECIATION_OPEN,
	NO_SCHEDULE,
	TWO_SCHEDULES,
	NO_CLOSING,
)
"""The codes of the findings of Steuerbote beside those of steuerbote.ebilanz and of the Bilanzzuordnung."""
TEXT_INPUTS = (
	"accounting_standard",
	"taxonomy_version",
	"commercial_finance_book",
	"tax_finance_book",
	"bvv_previous_equity_reason",
)
AMOUNT_INPUTS = (
	"bvv_previous_equity_override",
	"bvv_contributions",
	"bvv_withdrawals",
	"bvv_capital_adjustments",
)
INPUT_FIELDS = (*TEXT_INPUTS, *AMOUNT_INPUTS)
"""The fields of the document Berechnen reads besides its tables."""
TRANSFER_INPUTS = ("kind", "position", "current", "previous", "reason")

type Record = Mapping[str, Any]


class BridgeError(ValueError):
	"""Rows or fields the E-Bilanz cannot take; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


# The case and the books.


def statement_type_of(value: object) -> StatementType:
	try:
		return STATEMENT_TYPES[str(value)]
	except KeyError:
		raise BridgeError(NO_STATEMENT_TYPE, value) from None


def accounting_standard_of(value: object) -> AccountingStandard:
	try:
		return AccountingStandard(value)
	except ValueError:
		raise BridgeError(NO_ACCOUNTING_STANDARD, value) from None


def case_of(
	legal_form: str, from_date: date, to_date: date, statement_type: object, accounting_standard: object
) -> Case:
	"""The case of the E-Bilanz of a document: the Bilanzstichtag of a Jahresabschluss is the end of the fiscal year
	(rule 170205072), that of an Eröffnungsbilanz its beginning (rule 170205081). The E-Bilanz shows no previous year:
	„Steuerbilanzen dürfen keine Vorjahresangaben ... beinhalten“ (Leitfaden B.8.3), and a Handelsbilanz need not."""
	kind = statement_type_of(statement_type)
	closing = from_date if kind is StatementType.EROEFFNUNGSBILANZ else to_date
	return Case(
		legal_form, Periods(from_date, to_date, closing), accounting_standard_of(accounting_standard), kind
	)


def purpose_of(accounting_standard: object) -> Purpose:
	"""The balance sheet whose rules of the Bilanzzuordnung count: both for the Einheitsbilanz, „deutsches Handelsrecht
	(sog. Einheitsbilanz)“, which the tax administration treats as a Steuerbilanz (Leitfaden B.13), the Handelsbilanz
	for HGBM and the Steuerbilanz for AO."""
	return PURPOSES[accounting_standard_of(accounting_standard)]


def balance_book(accounting_standard: object, commercial: str | None, tax: str | None) -> str | None:
	"""The finance book the balances of the E-Bilanz are read from: that of the Steuerbilanz for AO, else that of the
	Handelsbilanz; None for the entries without a finance book."""
	if accounting_standard_of(accounting_standard) is AccountingStandard.STEUERBILANZ:
		return tax or None
	return commercial or None


def finance_books(accounting_standard: object, commercial: str | None, tax: str | None) -> tuple[str, ...]:
	"""The finance books whose depreciation the E-Bilanz reads, "" for the entries without one: both books of a
	Handelsbilanz with the Steuerbilanz of a finance book of its own, else the book of its balances."""
	standard = accounting_standard_of(accounting_standard)
	books = [balance_book(standard, commercial, tax) or ""]
	if standard is AccountingStandard.HANDELSBILANZ and tax:
		books.append(tax)
	return tuple(dict.fromkeys(books))


# The corrections and lines by hand.


def adjustments_of(rows: Iterable[Record]) -> tuple[Adjustment, ...]:
	"""The corrections of the positions with a reason and the lines by hand, in the order of the table, as the
	Adjustments of steuerbote/ebilanz/calculation.py."""
	rows = list(rows)
	found = []
	for row in rows:
		if row.get(LINE_COLUMNS.manual):
			continue
		correction = correction_of(row, LINE_COLUMNS)
		if correction is not None:
			found.append(Adjustment(_concept(row, POSITIONS), correction.amount, correction.reason))
	found.extend(Adjustment(line.key, line.amount, line.reason) for line in manual_lines(rows, LINE_COLUMNS))
	return tuple(found)


def corrected(rows: Iterable[Record]) -> frozenset[str]:
	"""The positions a correction with a reason changes, with the prefix of their module."""
	return frozenset(
		qualified(_concept(row, POSITIONS))
		for row in rows
		if not row.get(LINE_COLUMNS.manual) and correction_of(row, LINE_COLUMNS) is not None
	)


def by_hand(rows: Iterable[Record]) -> frozenset[str]:
	"""The positions of the lines by hand, with the prefix of their module."""
	return frozenset(qualified(_concept(row, POSITIONS)) for row in rows if row.get(LINE_COLUMNS.manual))


def lines_by_hand(rows: Iterable[Record]) -> list[dict[str, Any]]:
	"""The rows of the positions as a save keeps them: a line by hand names its position without the prefix of its
	module, and a position that has a row of Berechnen takes no line by hand, since its correction is the way to
	report another amount."""
	rows = [dict(row) for row in rows]
	computed = {_concept(row, POSITIONS) for row in rows if not row.get(LINE_COLUMNS.manual)}
	for index, row in enumerate(rows, start=1):
		if not row.get(LINE_COLUMNS.manual):
			continue
		row["concept"] = _concept(row, POSITIONS, index=row.get("idx") or index)
		if row["concept"] in computed:
			raise BridgeError(DOUBLED, row.get("idx") or index, row["concept"])
	return rows


# The rows Berechnen writes.


def position_rows(
	ebilanz: EBilanz,
	davon: Mapping[str, Decimal] = MappingProxyType({}),
	adjusted: Collection[str] = frozenset(),
	manual: Collection[str] = frozenset(),
) -> list[dict[str, Any]]:
	"""The positions the E-Bilanz reports, in the order of their presentation: each amount, each Mussfeld and
	Summenmussfeld without one as NIL, the Oberpositionen, the positions of the Betriebsvermögensvergleich, and the
	positions only the Steuerbilanz of a Handelsbilanz has. ``davon`` gives the value of each „davon“ position from the
	Bilanzzuordnung, ``adjusted`` the positions a correction of the company changes, whose computed amount is that of
	the books, and ``manual`` those of the lines by hand, which keep their own rows."""
	structure = ebilanz.structure
	steuerbilanz = ebilanz.ueberleitung.steuerbilanz
	comparison = ebilanz.betriebsvermoegensvergleich.amounts
	items = {
		item.concept: item
		for item in (*ebilanz.calculation.facts(), *ebilanz.betriebsvermoegensvergleich.facts())
		if not item.period.prior
	}
	adjusted = frozenset(qualified(name) for name in adjusted)
	manual = frozenset(qualified(name) for name in manual)
	rows = []
	for position in structure.positions:
		concept = position.concept
		item = items.get(concept)
		if position.component == BVV:
			ledger, amount, tax = None, comparison.get(concept), comparison.get(concept)
		else:
			value = ebilanz.calculation.value(concept)
			ledger = value.ledger if value is not None else None
			amount = value.amount if value is not None else None
			tax = steuerbilanz.get((concept, _current(position)))
		if concept in manual or (item is None and tax is None):
			continue
		computed = amount
		if concept in adjusted:
			computed = ledger if ledger is not None else davon.get(unqualified(concept))
		rows.append(
			{
				"concept": unqualified(concept),
				"label": position.label,
				"component": position.component,
				"mark": position.mark.value,
				"depth": position.depth,
				"parent_concept": _parent(structure, position),
				"davon_of": unqualified(position.davon_of) if position.davon_of else "",
				"nil": int(item is not None and item.value is None),
				"computed": computed or ZERO,
				"ledger_amount": ledger or ZERO,
				"tax_amount": tax or ZERO,
			}
		)
	return rows


def account_rows(ebilanz: EBilanz, names: Mapping[str, str] = MappingProxyType({})) -> list[dict[str, Any]]:
	"""The Kontensalden: every account of the books that lands on a position, with the position, the number and the
	label of the account and its balance in the direction of the position (steuerbote/ebilanz/kontennachweis.py);
	``names`` gives the account of ERPNext by its number."""
	structure = ebilanz.structure
	return [
		{
			"position": unqualified(line.concept),
			"position_label": structure.label(line.concept),
			"account": names.get(line.account),
			"account_number": line.account,
			"account_label": line.description,
			"amount": line.amount,
		}
		for line in ebilanz.calculation.lines
		if not line.prior
	]


def account_names(placement: Placement) -> dict[str, str]:
	"""The account of ERPNext of each number the placement holds."""
	return {item.balance.number: item.balance.account for item in placement.placed}


def totals(ebilanz: EBilanz) -> dict[str, Decimal]:
	"""The totals the document shows: Summe Aktiva and Summe Passiva, the Jahresüberschuss of the GuV, and of the
	Steuerbilanz after the Überleitung its Jahresüberschuss and its Betriebsvermögen, the Eigenkapital less the „nicht
	durch Eigenkapital gedeckter Fehlbetrag“ (rule 170405114), which the Körperschaftsteuererklärung reads."""
	calculation = ebilanz.calculation
	steuerbilanz = ebilanz.ueberleitung.steuerbilanz
	return {
		"total_assets": calculation.amount(ASSETS) or ZERO,
		"total_equity_and_liabilities": calculation.amount(EQUITY_AND_LIABILITIES) or ZERO,
		"net_income": calculation.amount(NET_INCOME) or ZERO,
		"tax_net_income": steuerbilanz.get((NET_INCOME, Period.WIRTSCHAFTSJAHR), ZERO),
		"tax_equity": steuerbilanz.get((EQUITY, Period.STICHTAG), ZERO)
		- steuerbilanz.get((DEFICIT, Period.STICHTAG), ZERO),
	}


# The Anlagenspiegel.


CATEGORY_AMOUNTS = (
	"cost_begin",
	"additions",
	"disposals",
	"adjustment",
	"depreciation_begin",
	"depreciation",
	"depreciation_disposals",
)


@dataclass(frozen=True, slots=True)
class CategoryValues:
	"""An asset category as the report „Asset Depreciations and Balances“ of ERPNext sums it up for a period and a
	finance book, in euros and cents: the Anschaffungs- und Herstellungskosten at the beginning (value_as_on_from_date,
	with the adjustments before it), the new purchases, the assets sold, scrapped or used up in a capitalization, the
	adjustments of the period on the fixed asset account (adjustment_during_period: Asset Value Adjustment and every
	other posting against the asset), the depreciation at the beginning, the depreciation of the period less its
	reversals, and the depreciation of the assets disposed of. ``account_number`` is the number of the fixed asset
	account of the category, empty without one."""

	category: str
	account_number: str
	cost_begin: Decimal = ZERO
	additions: Decimal = ZERO
	disposals: Decimal = ZERO
	adjustment: Decimal = ZERO
	depreciation_begin: Decimal = ZERO
	depreciation: Decimal = ZERO
	depreciation_disposals: Decimal = ZERO

	def less(self, other: CategoryValues) -> CategoryValues:
		"""What this book has more than ``other``, column by column: the Überleitungswerte of a Handelsbilanz with
		the Steuerbilanz of a finance book of its own (Leitfaden B.14.12.1 c, d)."""
		return CategoryValues(
			self.category,
			self.account_number,
			*(getattr(self, name) - getattr(other, name) for name in CATEGORY_AMOUNTS),
		)

	def plus(self, other: CategoryValues) -> CategoryValues:
		"""Both together, column by column, in the category and with the account of this one."""
		return CategoryValues(
			self.category,
			self.account_number,
			*(getattr(self, name) + getattr(other, name) for name in CATEGORY_AMOUNTS),
		)

	@property
	def empty(self) -> bool:
		"""Whether every column is zero."""
		return not any(getattr(self, name) for name in CATEGORY_AMOUNTS)


def by_category(assets: Iterable[CategoryValues]) -> list[CategoryValues]:
	"""The assets summed up per asset category, the categories in the order of their names."""
	sums: dict[str, CategoryValues] = {}
	for values in assets:
		sums[values.category] = sums[values.category].plus(values) if values.category in sums else values
	return [sums[category] for category in sorted(sums)]


def transfer_values(
	tax: Mapping[str, CategoryValues], commercial: Mapping[str, CategoryValues]
) -> list[CategoryValues]:
	"""The Überleitungswerte of the Anlagenspiegel per asset category: what each asset has more in the books of the
	Steuerbilanz than in those of the Handelsbilanz, both by the name of the asset (ebilanz_sources.book_assets),
	summed up by its category (Leitfaden B.14.12.1 c, d); a category without one is left out."""
	differences = (
		values.less(commercial.get(name) or CategoryValues(values.category, values.account_number))
		for name, values in tax.items()
	)
	return [values for values in by_category(differences) if not values.empty]


def category_rows(
	categories: Iterable[CategoryValues],
	positions: Mapping[str, str | None],
	value_type: str,
	stored: Iterable[Record] = (),
) -> list[dict[str, Any]]:
	"""The rows of the Anlagenspiegel of the asset categories for one value type, each on the position its fixed asset
	account goes to (``positions`` by account number), with the columns by hand and the reason the document holds for
	the category and value type."""
	kept = {
		(row.get("asset_category"), row.get("value_type")): row for row in stored if not row.get("manual")
	}
	rows = []
	for values in categories:
		before = kept.get((values.category, value_type), {})
		rows.append(
			{
				"position": positions.get(values.account_number) or "",
				"value_type": value_type,
				"asset_category": values.category,
				"manual": 0,
				"cost_begin": values.cost_begin,
				"additions": values.additions,
				"disposals": values.disposals,
				"erp_adjustment": values.adjustment,
				"depreciation_begin": values.depreciation_begin,
				"depreciation_regular": values.depreciation,
				"depreciation_disposals": values.depreciation_disposals,
				**{name: to_amount(before.get(name)) for name in MANUAL_COLUMNS},
				"reason": str(before.get("reason") or "").strip(),
			}
		)
	return rows


def rows_by_hand(stored: Iterable[Record]) -> list[dict[str, Any]]:
	"""The rows of the Anlagenspiegel the company entered by hand, as the document holds them."""
	return [
		{
			"position": unqualified(str(row.get("position") or "").strip()),
			"value_type": row.get("value_type") or "StB",
			"asset_category": None,
			"manual": 1,
			"erp_adjustment": ZERO,
			**{name: to_amount(row.get(name)) for name in ROW_COLUMNS},
			"reason": str(row.get("reason") or "").strip(),
		}
		for row in stored
		if row.get("manual")
	]


def kept_assets(stored: Iterable[Record], sent: Iterable[Record]) -> list[dict[str, Any]]:
	"""The rows of the Anlagenspiegel a save keeps: a row of an asset category keeps what Berechnen wrote and takes the
	columns by hand and the reason, and stays even if the save leaves it out; a new row is a row by hand."""
	stored = {row.get("name"): dict(row) for row in stored if row.get("name")}
	rows = []
	for row in sent:
		before = stored.pop(row.get("name"), None) if row.get("name") else None
		if before is None or before.get("manual"):
			rows.append({**row, "asset_category": None, "manual": 1, "erp_adjustment": ZERO})
		else:
			rows.append({**before, **{name: row.get(name) for name in (*MANUAL_COLUMNS, "reason")}})
	rows.extend(row for row in stored.values() if not row.get("manual"))
	return rows


def kept_transfers(stored: Iterable[Record], sent: Iterable[Record]) -> list[dict[str, Any]]:
	"""The entries of the Überleitung a save keeps: an entry of the finance book of the Steuerbilanz as Berechnen wrote
	it, even if the save leaves it out, and the entries by hand as the save sends them."""
	derived = {row.get("name"): dict(row) for row in stored if row.get("name") and row.get("derived")}
	rows = []
	for row in sent:
		before = derived.pop(row.get("name"), None) if row.get("name") else None
		rows.append(before if before is not None else {**row, "derived": 0})
	rows.extend(derived.values())
	return rows


def asset_inputs(rows: Iterable[Record]) -> list[dict[str, Any]]:
	"""What a new document keeps of the rows of the Anlagenspiegel it is made with, such as a Berichtigung: of a row of an
	asset category its columns by hand and its reason, of a row by hand all of it; Berechnen fills the rest."""
	kept = []
	for row in rows:
		if row.get("manual"):
			kept.extend(rows_by_hand([row]))
		else:
			kept.append(
				{
					"asset_category": row.get("asset_category"),
					"value_type": row.get("value_type") or "StB",
					"manual": 0,
					**{name: to_amount(row.get(name)) for name in MANUAL_COLUMNS},
					"reason": str(row.get("reason") or "").strip(),
				}
			)
	return kept


def transfer_inputs(rows: Iterable[Record]) -> list[dict[str, Any]]:
	"""What a new document keeps of the entries of the Überleitung: those by hand."""
	return [
		{name: row.get(name) for name in TRANSFER_INPUTS} | {"derived": 0}
		for row in rows
		if not row.get("derived")
	]


def inputs(
	values: Mapping[str, object], assets: Iterable[Record], transfers: Iterable[Record]
) -> tuple[Any, ...]:
	"""What Berechnen reads of the document besides its positions, comparable between two states of it: the fields of
	INPUT_FIELDS, the columns by hand and the reasons of the Anlagenspiegel with its rows by hand, and the entries of
	the Überleitung by hand."""
	fields = (
		*(_text(values.get(name)) for name in TEXT_INPUTS),
		*(_cents(values.get(name)) for name in AMOUNT_INPUTS),
	)
	rows = tuple(
		(
			_text(row.get("asset_category")),
			_text(row.get("value_type")),
			_text(row.get("position")) if row.get("manual") else "",
			*(_cents(row.get(name)) for name in (ROW_COLUMNS if row.get("manual") else MANUAL_COLUMNS)),
			_text(row.get("reason")),
		)
		for row in assets
	)
	entries = tuple(
		(
			_text(row.get("kind")),
			_text(row.get("position")),
			_cents(row.get("current")),
			_cents(row.get("previous")),
			_text(row.get("reason")),
		)
		for row in transfers
		if not row.get("derived")
	)
	return fields, rows, entries


def assets_of(rows: Iterable[Record]) -> tuple[Row, ...]:
	"""The rows of the Anlagenspiegel as steuerbote/ebilanz/anlagenspiegel.py takes them; a row without a position is
	left out, which asset_findings names, and a column without an amount is none."""
	found = []
	for index, row in enumerate(rows, start=1):
		position = str(row.get("position") or "").strip()
		if not position:
			continue
		kind = row.get("value_type") or "StB"
		if kind not in VALUE_TYPES:
			raise BridgeError(NO_VALUE_TYPE, index, kind)
		found.append(
			Row(
				position,
				VALUE_TYPES[kind],
				**{name: to_amount(row.get(name)) or None for name in ROW_COLUMNS},
				source=str(row.get("asset_category") or ""),
				reason=str(row.get("reason") or "").strip(),
			)
		)
	return tuple(found)


def fixed_asset_rows(structure: Structure, rows: Iterable[Record]) -> list[dict[str, Any]]:
	"""The rows with the label of their position and their values at the end of the period, as the calculation of the
	Anhang sums up their columns (Leitfaden B.14.12.1)."""
	found = []
	for row in rows:
		values = dict(row)
		position = str(values.get("position") or "")
		values["position_label"] = (
			structure.label(qualified(position)) if structure.taxonomy.has(qualified(position)) else ""
		)
		ends = _end_values(structure, assets_of([values]))
		values.update({name: ends.get(concept) or ZERO for name, concept in END_COLUMNS.items()})
		found.append(values)
	return found


def asset_findings(structure: Structure, rows: Iterable[Record]) -> list[Finding]:
	"""What holds the Anlagenspiegel back beyond its own checks: a category whose fixed asset account goes to no
	position of the Anlagevermögen, and one whose columns by hand do not take up exactly the adjustments ERPNext booked
	on its fixed asset account, such as an Asset Value Adjustment, which the report adds to the Anschaffungs- und
	Herstellungskosten while the Anlagenspiegel shows it as a Zuschreibung, an außerplanmäßige Abschreibung or an
	Umbuchung (Leitfaden B.14.12.1)."""
	findings = []
	for row in rows:
		if row.get("manual"):
			continue
		category = str(row.get("asset_category") or "")
		position = str(row.get("position") or "")
		if not position or qualified(position) not in structure.rows:
			findings.append(
				Finding(
					ASSET_POSITION,
					Severity.ERROR,
					f"Das Anlagenkonto der Anlagenkategorie {category} geht in keine Position des Anlagevermögens: "
					"Ordnen Sie es in der Bilanzzuordnung einer Position zu, die eine Zeile des Anlagenspiegels hat. "
					f"(Quelle: {LEITFADEN}, B.14.12.1)",
					_shortened(category),
				)
			)
			continue
		adjustment = to_amount(row.get("erp_adjustment"))
		taken = _book_value(structure, row) - _book_value(
			structure, {**row, **dict.fromkeys(MANUAL_COLUMNS, ZERO)}
		)
		if taken != adjustment:
			findings.append(
				Finding(
					ASSET_ADJUSTMENT,
					Severity.ERROR,
					f"Die Anlagenkategorie {category} hat laut ERPNext Anpassungen von {euro(adjustment)} auf ihrem "
					f"Anlagenkonto, die Spalten von Hand ihrer Zeile nehmen {euro(taken)} auf: Tragen Sie die Anpassungen "
					"mit Begründung als Zuschreibung, außerplanmäßige Abschreibung, Sonderabschreibung oder Umbuchung "
					f"ein. (Quelle: {LEITFADEN}, B.14.12.1; Bericht „Asset Depreciations and Balances“ von ERPNext)",
					_shortened(category),
				)
			)
	return findings


# The Überleitungsrechnung.


def derived_transfers(
	structure: Structure,
	commercial: Iterable[AccountBalance],
	tax: Iterable[AccountBalance],
	commercial_opening: Iterable[AccountBalance] = (),
	tax_opening: Iterable[AccountBalance] = (),
) -> tuple[Transfer, ...]:
	"""The Wertänderungen of the Überleitung from the balances of the two finance books, in the order of the positions:
	each position of Bilanz and GuV whose balances differ, for a position of the Bilanz split into the difference of
	the earlier fiscal years, that at the beginning of the year, and the change of the current one (Leitfaden A.11,
	B.15.1). The Eigenkapital is left out: its difference is the steuerlicher Ausgleichsposten, which the Überleitung
	derives from the other entries (steuerbote/ebilanz/ueberleitung.py)."""
	current = _difference(structure, tax, commercial)
	earlier = _difference(structure, tax_opening, commercial_opening)
	transfers = []
	for position in structure.positions:
		concept = position.concept
		if concept.startswith(EQUITY_POSITIONS) or position.component == BVV:
			continue
		total = current.get(concept, ZERO)
		before = earlier.get(concept, ZERO) if position.instant else ZERO
		if total or before:
			transfers.append(
				Transfer(
					Kind.WERTAENDERUNG,
					concept,
					(total - before) or None,
					before or None,
					DERIVED_REASON,
				)
			)
	return tuple(transfers)


def transfer_rows(derived: Iterable[Transfer], stored: Iterable[Record] = ()) -> list[dict[str, Any]]:
	"""The entries of the Überleitung: those the finance book of the Steuerbilanz gives, then those by hand as the
	document holds them."""
	kinds = {kind: name for name, kind in TRANSFER_KINDS.items()}
	rows = [
		{
			"kind": kinds[transfer.kind],
			"position": unqualified(transfer.position),
			"current": transfer.current or ZERO,
			"previous": transfer.previous or ZERO,
			"reason": transfer.reason,
			"derived": 1,
		}
		for transfer in derived
	]
	rows.extend(
		{
			"kind": row.get("kind") or "Wertänderung",
			"position": unqualified(str(row.get("position") or "").strip()),
			"current": to_amount(row.get("current")),
			"previous": to_amount(row.get("previous")),
			"reason": str(row.get("reason") or "").strip(),
			"derived": 0,
		}
		for row in stored
		if not row.get("derived")
	)
	return rows


def labelled_transfers(structure: Structure, rows: Iterable[Record]) -> list[dict[str, Any]]:
	"""The entries with the label of their position."""
	return [
		{
			**row,
			"position_label": structure.label(qualified(str(row.get("position") or "")))
			if structure.taxonomy.has(qualified(str(row.get("position") or "")))
			else "",
		}
		for row in rows
	]


def transfers_of(rows: Iterable[Record]) -> tuple[Transfer, ...]:
	"""The entries as steuerbote/ebilanz/ueberleitung.py takes them, a Wertänderung without an amount as none."""
	found = []
	for index, row in enumerate(rows, start=1):
		kind = row.get("kind") or "Wertänderung"
		if kind not in TRANSFER_KINDS:
			raise BridgeError(NO_KIND, index, kind)
		found.append(
			Transfer(
				TRANSFER_KINDS[kind],
				_concept(row, TRANSFERS, "position", index),
				to_amount(row.get("current")) or None,
				to_amount(row.get("previous")) or None,
				str(row.get("reason") or "").strip(),
			)
		)
	return tuple(found)


# The Betriebsvermögensvergleich.


def equity_of(structure: Structure, balances: Iterable[AccountBalance]) -> Decimal:
	"""The Betriebsvermögen the balances give: the Eigenkapital less the „nicht durch Eigenkapital gedeckter
	Fehlbetrag“ (rule 170405114)."""
	found = calculate(structure, balances)
	return (found.amount(EQUITY) or ZERO) - (found.amount(DEFICIT) or ZERO)


def last_ausgleichsposten(ueberleitung: Ueberleitung) -> Decimal:
	"""The steuerlicher Ausgleichsposten of the last Bilanzstichtag that the Überleitung gives: the Betriebsvermögen of
	the Steuerbilanz at the beginning of the year is that of the Handelsbilanz with it (Leitfaden B.14.3.2.12)."""
	return ueberleitung.steuerbilanz.get((PREVIOUS_DIFFERENCE, Period.STICHTAG), ZERO)


def equity_changes(
	previous: Decimal,
	*,
	override: object = None,
	override_reason: str | None = None,
	founding: object = None,
	contributions: object = None,
	withdrawals: object = None,
	adjustments: object = None,
) -> EquityChanges:
	"""What the Betriebsvermögensvergleich takes beyond the books: the Betriebsvermögen at the end of the previous
	fiscal year, by the company where it states another with its reason; the Einlagen, those of the founding and the
	others; the Entnahmen and Ausschüttungen; and a Kapitalanpassung. An amount of zero is NIL, which the comparison
	counts as zero (Leitfaden B.14.3.2.12)."""
	reason = str(override_reason or "").strip()
	stated = to_amount(override) if reason else previous
	paid_in = to_amount(founding) + to_amount(contributions)
	return EquityChanges(
		previous_equity=stated,
		capital_adjustments=to_amount(adjustments) or None,
		withdrawals=to_amount(withdrawals) or None,
		contributions=paid_in or None,
	)


# The E-Bilanz of the document as stored.


def sources_of(
	structure: Structure,
	*,
	positions: Iterable[Record],
	accounts: Iterable[Record],
	fixed_assets: Iterable[Record] = (),
	transfers: Iterable[Record] = (),
	equity: EquityChanges | None = None,
	first_year: bool = False,
) -> Sources:
	"""The sources of the E-Bilanz as the document holds them: the Kontensalden as the balances of the books, the
	„davon“ positions with the amount Berechnen gave them, then the corrections and lines by hand, the rows of the
	Anlagenspiegel and the entries of the Überleitung."""
	positions = list(positions)
	balances = []
	for index, row in enumerate(accounts, start=1):
		concept = qualified(_concept(row, ACCOUNTS, "position", index))
		position = structure.position(concept)
		amount = to_amount(row.get("amount"))
		signed = -amount if position is not None and position.balance is Balance.CREDIT else amount
		balances.append(
			AccountBalance(
				str(row.get("account_number") or "").strip(),
				str(row.get("account_label") or ""),
				concept,
				signed,
			)
		)
	davon = tuple(
		Adjustment(row["concept"], to_amount(row.get("computed")), DAVON_REASON)
		for row in positions
		if row.get("davon_of")
		and not row.get("manual")
		and to_amount(row.get("computed"))
		and _without_parts(structure, qualified(row["concept"]))
	)
	return Sources(
		balances=tuple(balances),
		adjustments=(*davon, *adjustments_of(positions)),
		assets=assets_of(fixed_assets),
		transfers=transfers_of(transfers),
		equity=equity or EquityChanges(),
		first_year=first_year,
	)


def differences(ebilanz: EBilanz, positions: Iterable[Record]) -> list[tuple[str, Decimal, Decimal]]:
	"""The positions whose stored amount the E-Bilanz of the document no longer gives, each with the stored amount and
	the one it gives, as after a change of the taxonomy or of the settings since Berechnen."""
	comparison = ebilanz.betriebsvermoegensvergleich.amounts
	found = []
	for row in positions:
		concept = qualified(str(row.get("concept") or ""))
		position = ebilanz.structure.position(concept)
		if position is not None and position.component == BVV:
			given = comparison.get(concept)
		else:
			given = ebilanz.calculation.amount(concept)
		stored = to_amount(row.get("reported"))
		if (given or ZERO) != stored:
			found.append((unqualified(concept), stored, given or ZERO))
	return found


# Findings.


def placement_findings(placement: Placement) -> tuple[Finding, ...]:
	"""The findings of the Bilanzzuordnung for the table Befunde, each text with its source and the account or the
	position it is about as its reference."""
	return tuple(
		Finding(
			finding.code.value,
			finding.severity.value,
			f"{finding.text} (Quelle: {finding.source})",
			_shortened(finding.account or finding.concept),
		)
		for finding in placement.findings
	)


def taxonomy_finding(version: str, unchanged: bool, detail: str) -> tuple[Finding, ...]:
	"""An error where the installed taxonomy of the E-Bilanz is not the one esteuer.de publishes: its files differ from
	its manifest, or the bench names another package (steuerbote/xbrl/taxonomy.py, status). The positions, Mussfelder
	and calculations of the E-Bilanz are those of the „amtlich vorgeschriebener Datensatz“ (§ 5b Abs. 1 Satz 1 EStG)."""
	if unchanged:
		return ()
	return (
		Finding(
			TAXONOMY_CODE,
			Severity.ERROR,
			f"{detail} Die E-Bilanz rechnet nur mit der HGB-Taxonomie {version}, wie esteuer.de sie veröffentlicht. "
			"(Quelle: § 5b Abs. 1 Satz 1 EStG)",
			f"HGB-Taxonomie {version}",
		),
	)


@dataclass(frozen=True, slots=True)
class Unposted:
	"""A depreciation of an asset that its schedule plans up to the Bilanzstichtag and no Journal Entry posted."""

	asset: str
	day: date
	amount: Decimal
	finance_book: str = ""


def depreciation_findings(unposted: Iterable[Unposted], stichtag: date) -> list[Finding]:
	"""An error per asset whose scheduled depreciation up to the Bilanzstichtag is not posted: „Bei Vermögensgegenständen
	des Anlagevermögens, deren Nutzung zeitlich begrenzt ist, sind die Anschaffungs- oder die Herstellungskosten um
	planmäßige Abschreibungen zu vermindern“ (§ 253 Abs. 3 Satz 1 HGB), and the books are what the E-Bilanz reports."""
	by_asset: dict[tuple[str, str], list[Unposted]] = {}
	for entry in unposted:
		by_asset.setdefault((entry.asset, entry.finance_book), []).append(entry)
	findings = []
	for (asset, book), entries in by_asset.items():
		first = min(entry.day for entry in entries)
		amount = sum((entry.amount for entry in entries), ZERO)
		in_book = f" im Finanzbuch {book}" if book else ""
		findings.append(
			Finding(
				DEPRECIATION_OPEN,
				Severity.ERROR,
				f"Die Abschreibungen der Anlage {asset}{in_book} von {euro(amount)} ab dem {first:%d.%m.%Y} bis zum "
				f"Bilanzstichtag {stichtag:%d.%m.%Y} sind nicht gebucht: Buchen Sie sie, dann berechnen Sie die "
				"E-Bilanz neu. (Quelle: § 253 Abs. 3 Satz 1 HGB; § 7 Abs. 1 EStG)",
				_shortened(asset),
			)
		)
	return findings


def schedule_findings(scheduled: Mapping[str, Collection[str]], books: Iterable[str]) -> list[Finding]:
	"""The errors of the depreciation schedules in the finance books the E-Bilanz reads (finance_books), "" for the
	entries without one; ``scheduled`` gives the books of the active schedules of each asset with depreciation.
	ERPNext counts the entries without a finance book in every book, as steuerbote/balances.py and the report Asset
	Depreciations and Balances read them, so an asset needs a schedule in each book or one without a finance book, and
	not both: without one the book holds no depreciation of it, with both it holds both."""
	findings = []
	for book in books:
		where = f"im Finanzbuch {book}" if book else "ohne Finanzbuch"
		for asset, held in scheduled.items():
			if book not in held and "" not in held:
				findings.append(
					Finding(
						NO_SCHEDULE,
						Severity.ERROR,
						f"Die Anlage {asset} wird abgeschrieben, hat aber keinen aktiven Abschreibungsplan {where}"
						f"{' und keinen ohne Finanzbuch' if book else ''}: In den Büchern der E-Bilanz stünde sie "
						"ohne Abschreibungen. (Quelle: § 253 Abs. 3 Satz 1 HGB; § 7 Abs. 1 EStG; ERPNext 16, Asset "
						"Depreciation Schedule)",
						_shortened(asset),
					)
				)
			elif book and book in held and "" in held:
				findings.append(
					Finding(
						TWO_SCHEDULES,
						Severity.ERROR,
						f"Die Anlage {asset} hat einen aktiven Abschreibungsplan {where} und einen ohne Finanzbuch: "
						"ERPNext zählt die Buchungen ohne Finanzbuch in jedem Buch, im Finanzbuch "
						f"{book} stünden beide Abschreibungen. Weichen die Abschreibungen der Bücher ab, gehört jeder "
						"Plan in sein Finanzbuch. (Quelle: steuerbote/balances.py; ERPNext 16, Asset Depreciation "
						"Schedule)",
						_shortened(asset),
					)
				)
	return findings


def closing_finding(statement_type: object, closed_by: Collection[str]) -> tuple[Finding, ...]:
	"""A hint where no Period Closing Voucher closes the fiscal year of a Jahresabschluss: the E-Bilanz takes the result
	from the GuV and needs none, but the books of the year stay open without one (steuerbote/balances.py)."""
	if statement_type_of(statement_type) is StatementType.EROEFFNUNGSBILANZ or closed_by:
		return ()
	return (
		Finding(
			NO_CLOSING,
			Severity.HINT,
			"Für das Geschäftsjahr ist kein Periodenabschlussbeleg gebucht. Die E-Bilanz braucht keinen: Sie nimmt den "
			"Jahresüberschuss aus der GuV und das Ergebnis früherer Jahre ohne Periodenabschlussbeleg auf das "
			"Abschlusskonto der Einstellungen Jahresmeldungen. Die Erfolgskonten des Jahres schließt in ERPNext erst er "
			"ab. (Quelle: steuerbote/balances.py; ERPNext 16, Period Closing Voucher)",
		),
	)


# Helpers.


def _text(value: object) -> str:
	"""A text with its blanks collapsed, empty for nothing."""
	return " ".join(str(value or "").split())


def _cents(value: object) -> str:
	"""An amount as its cents, zero for nothing."""
	return format(to_amount(value), "f")


def _concept(row: Record, table: str, field: str = "concept", index: object = None) -> str:
	concept = unqualified(str(row.get(field) or "").strip())
	if not concept:
		raise BridgeError(NO_POSITION, index if index is not None else row.get("idx") or "?", table)
	return concept


def _current(position: Position) -> Period:
	return Period.STICHTAG if position.instant else Period.WIRTSCHAFTSJAHR


def _parent(structure: Structure, position: Position) -> str:
	"""The nearest position above one in the presentation of its component, without the prefix of its module."""
	network = structure.taxonomy.presentation[position.role]
	return next(
		(unqualified(above) for above in network.ancestors(position.concept) if structure.position(above)),
		"",
	)


def _difference(
	structure: Structure, minuend: Iterable[AccountBalance], subtrahend: Iterable[AccountBalance]
) -> dict[str, Decimal]:
	"""The difference of the balances of two books per position, in the direction of the position."""
	found: dict[str, Decimal] = {}
	for balances, sign in ((minuend, Decimal(1)), (subtrahend, Decimal(-1))):
		for balance in balances:
			concept = qualified(balance.concept or "")
			position = structure.position(concept)
			if position is None:
				continue
			amount = balance.amount if position.balance is Balance.DEBIT else -balance.amount
			found[concept] = found.get(concept, ZERO) + sign * amount
	return {concept: amount for concept, amount in found.items() if amount}


def _without_parts(structure: Structure, concept: str) -> bool:
	"""Whether a position has no position under it in its calculation, so that it takes an amount of its own: the
	„davon“ position a balance goes to, not one that sums up others (steuerbote/ebilanz/calculation.py)."""
	position = structure.position(concept)
	if position is None:
		return False
	network = structure.taxonomy.calculation[position.role]
	return not any(structure.position(arc.child) for arc in network.children(position.concept))


def _end_values(structure: Structure, rows: tuple[Row, ...]) -> Mapping[str, Decimal | None]:
	if not rows:
		return {}
	(row,) = rows
	line = anlagenspiegel(structure, rows, handelsbilanz={}).line(row.position, row.value_type)
	return line.values if line is not None else {}


def _book_value(structure: Structure, row: Record) -> Decimal:
	return _end_values(structure, assets_of([row])).get(BOOK_VALUE) or ZERO


def _shortened(text: str) -> str:
	return text if len(text) <= DATA_LENGTH else text[: DATA_LENGTH - len(ELLIPSIS)] + ELLIPSIS


def taxonomy_for(begin: date, end: date, chosen: str | None) -> str | None:
	"""The version of the HGB-Taxonomie of an E-Bilanz of the Wirtschaftsjahr from begin to end: the one chosen while
	the Wirtschaftsjahr may take it, such as 6.10 for 2026, else the one it takes „grundsätzlich“; a Wirtschaftsjahr no
	version serves keeps the one chosen, which the checks of the E-Bilanz refuse (steuerbote/xbrl/versions.py)."""
	if chosen in {version.version for version in versions.allowed_for(begin, end)}:
		return chosen
	try:
		return versions.for_fiscal_year(begin, end).version
	except versions.UnknownTaxonomyError:
		return chosen
