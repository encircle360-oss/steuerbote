"""The steuerliche Überleitungsrechnung of a Handelsbilanz: its entries as the taxonomy takes them, the steuerlicher
Ausgleichsposten, and the Steuerbilanz that results, which ERiC checks as one.

Sources are the Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025 („Leitfaden“), and the rules and
structural errors of Jahresdokumentation_Bilanz_Taxonomie_6_9.ods (ERiC documentation 44.3.6.0).

When. „Ansätze oder Beträge in der Steuerbilanz, die den steuerlichen Vorschriften nicht entsprechen, sind durch
Zusätze oder Anmerkungen den steuerlichen Vorschriften anzupassen“ (§ 5b Abs. 1 Satz 2 EStG): a Handelsbilanz
(Bilanzierungsstandard HGBM) comes with its Überleitungsrechnung, „Die nach § 5b Abs. 1 Satz 2 EStG vorzunehmenden
Anpassungen aller Positionen (auf allen Ebenen), deren Ansätze und Beträge nicht den steuerlichen Vorschriften
entsprechen, haben mit der strukturierten Überleitungsrechnung der Taxonomie zu erfolgen.“ (A.11), at least one valued
entry (rule 170205100). A Steuerbilanz has none: „Ist der Datensatz als Steuerbilanz ... zu behandeln, so ist zu
prüfen, dass er keine Überleitungsrechnung/Umgliederung enthält.“ (B.16.1; rule 170205095).

Entries. The company gives a Transfer per position of Bilanz or GuV that differs: the kind of the Überleitung, the
Wertänderung of the current fiscal year and, for a position of the Bilanz, that of earlier fiscal years, each in the
direction of the position, and why. „In der Überleitungsrechnung werden somit nicht die endgültigen Salden der
übergeleiteten Handelsbilanzpositionen angegeben, sondern es werden Deltawerte angegeben, die zusammen mit dem Saldo
der Handelsbilanz in Summe den Wert der Steuerbilanz ergeben.“ (A.11) Entries of a position no calculation counts,
of a total and of the positions Steuerbote derives are refused: a total changes with the positions under it, and ERiC
changes nothing but the position an entry names, „Es wird also nur immer der Wert einer einzelnen Position geändert“
(B.15.1). So Steuerbote writes the change of each total as an entry of its own, as the examples of the ERiC
documentation do (Anlagenspiegel_brutto_mitUeberleitung.xml).

Tuples. One tuple „Überleitung Handelsbilanzposten auf Steuerbilanzposten“ [hbst.transfer] per kind of the
Überleitung, „ausschließlich Umgliederungen, ausschließlich Änderungen der Wertansätze oder beide“ (A.11), holding an
entry per position the kind changes: „Aktivposition“ for the positions under „Bilanzsumme, Summe Aktiva“ [bs.ass],
„Passivposition“ for those under [bs.eqLiab], „GuV-Posten mit erfolgswirksamen Abweichungen“ for those of the GuV
(B.15.1.1 to B.15.1.3), each with the name of the position and its Wertänderung over the fiscal year: „Da die
Überleitungsrechnung keinem Tabellenbereich zuzurechnen ist und keine Vorjahresangaben enthalten darf, müssen alle ihre
Einträge [dem aktuellen Berichtszeitraumkontext zugeordnet sein]“ (structural error 170145090). „Wenn die
Überleitungsinformationen über mehrere Datensätze verteilt sind, dann besteht die Überleitungsrechnung aus der
Gesamtheit dieser Überleitungsdatensätze.“ (A.11)

Ausgleichsposten. A Wertänderung of the Bilanz changes the Eigenkapital of the Steuerbilanz: the current one its
result, „steuerliches Mehr-/Minderergebnis lfd. Jahr gegenüber HB“
[bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts], those of earlier years „steuerlicher
Ausgleichsposten des letzten Stichtags“ [….finalPrev], as „Eigenkapital, Jahresüberschuss/-fehlbetrag (Bilanz) - bei
Kapitalgesellschaften + Eigenkapital, steuerlicher Ausgleichsposten, steuerliches Mehr-/Minderergebnis lfd. Jahr
gegenüber HB = GuV → Jahresüberschuss/-fehlbetrag“ holds after the Überleitung too (Leitfaden B.14.3.2.3.4.1; rule
170405070). Steuerbote writes both into the tuple of the Wertänderungen, so Aktiva and Passiva of the Steuerbilanz
agree, and the result of the GuV follows: what the entries of the GuV leave of the change of the result goes to the
„Sammelposten für Gewinnänderungen aus der Überleitungsrechnung“ [is.netIncome.collItemChangeProfitHbst], which „darf
... in der Überleitungsrechnung enthalten sein“ (B.13; B.15.2). An Umgliederung moves amounts and changes neither: a
hint where it does.

Steuerbilanz. „Nach der Verarbeitung der Überleitungsrechnung muss sich eine Steuerbilanz errechnet haben, die selbst
den Anforderungen an eine übermittelte Steuerbilanz genügt“ (B.15.1): each position is its amount in the Handelsbilanz
plus its Wertänderungen, of earlier years as well for a position of the Bilanz, or the Wertänderungen alone for a
position the Handelsbilanz does not have (B.15.1.5). The Betriebsvermögensvergleich and the Steuerbilanzwerte of the
Anlagenspiegel take these amounts (steuerbote/ebilanz/calculation.py, anlagenspiegel.py). A position of the Bilanz
„steuerlich“ not permitted is zero after the Überleitung, „nach Ausführung der Überleitung/Umgliederung müssen solche
Positionen den Wert „0“ aufweisen, wenn sie in der Handelsbilanz werthaltig waren“ (B.15.2). „Dabei muss zumindest für
eine Position die Summe der Änderungsbeträge ungleich 0 sein.“ (B.15.1; structural error 170145132)

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from steuerbote.ebilanz.calculation import (
	ASSETS,
	BALANCE_SHEET_NET_INCOME,
	BILANZ,
	COLLECTIVE_ITEM,
	EQUITY_AND_LIABILITIES,
	GUV,
	NET_INCOME,
	Calculation,
)
from steuerbote.ebilanz.positions import (
	Finding,
	Position,
	Structure,
	euro,
	leitfaden,
	qualified,
	rule,
	unqualified,
)
from steuerbote.ustva.rounding import CENT, ZERO
from steuerbote.xbrl.checks import Severity
from steuerbote.xbrl.facts import Item, Period, Tuple, amount, choice
from steuerbote.xbrl.taxonomy import NOT_PERMITTED_FISCAL

TRANSFER = "de-gaap-ci:hbst.transfer"
KIND = "de-gaap-ci:hbst.transfer.kind"
TAX_BALANCE = "de-gaap-ci:bs.eqLiab.equity.netIncome.taxBalanceGenerally"
CURRENT_DIFFERENCE = "de-gaap-ci:bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts"
PREVIOUS_DIFFERENCE = "de-gaap-ci:bs.eqLiab.equity.netIncome.taxBalanceGenerally.finalPrev"
DERIVED = frozenset({BALANCE_SHEET_NET_INCOME, COLLECTIVE_ITEM})


class Kind(StrEnum):
	"""The Art der Überleitung (Leitfaden A.11)."""

	UMGLIEDERUNG = "de-gaap-ci:hbst.transfer.kind.reclassification"
	WERTAENDERUNG = "de-gaap-ci:hbst.transfer.kind.changeValue"
	BEIDES = "de-gaap-ci:hbst.transfer.kind.reclassificationChangeValue"


@dataclass(frozen=True, slots=True)
class Transfer:
	"""A difference of the Steuerbilanz to the Handelsbilanz at one position, in the direction of the position: the
	Wertänderung of the current fiscal year and, for a position of the Bilanz, that of earlier ones, with its reason."""

	kind: Kind
	position: str
	current: Decimal | None
	previous: Decimal | None = None
	reason: str = ""

	def __post_init__(self) -> None:
		object.__setattr__(self, "kind", Kind(self.kind))
		object.__setattr__(self, "position", qualified(self.position))
		for name in ("current", "previous"):
			value = getattr(self, name)
			if value is not None and (
				isinstance(value, bool) or not isinstance(value, Decimal) or value != value.quantize(CENT)
			):
				raise ValueError(
					f"the {name} change of {self.position} is no amount in euros and cents: {value!r}"
				)


@dataclass(frozen=True, slots=True)
class Entry:
	"""What one tuple of the Überleitung changes at one position."""

	position: str
	current: Decimal
	previous: Decimal | None


@dataclass(frozen=True, slots=True)
class Group:
	"""A tuple of the Überleitung: its kind, its entries and the transfers behind them; Steuerbote's own entries of the
	Ausgleichsposten and the Sammelposten have none."""

	kind: Kind
	entries: tuple[Entry, ...]
	transfers: tuple[Transfer, ...]


@dataclass(frozen=True)
class Ueberleitung:
	"""The Überleitungsrechnung of a Handelsbilanz and the Steuerbilanz that results from it."""

	structure: Structure
	groups: tuple[Group, ...]
	steuerbilanz: Mapping[tuple[str, Period], Decimal]
	"""Each position of Bilanz and GuV of the current year with its amount in the Steuerbilanz."""
	findings: tuple[Finding, ...]

	def facts(self) -> tuple[Tuple, ...]:
		"""A tuple hbst.transfer per group, its entries in the order of the positions."""
		tuples = []
		for group in self.groups:
			entries = [_entry(entry) for entry in group.entries]
			tuples.append(Tuple(TRANSFER, (choice(KIND, group.kind.value), *entries)))
		return tuple(tuples)


def ueberleitung(calculation: Calculation, transfers: Iterable[Transfer]) -> Ueberleitung:
	"""The Überleitung of the Handelsbilanz of the calculation by the transfers; for a Steuerbilanz its amounts as they
	are, and a finding for any transfer."""
	structure = calculation.structure
	taxonomy = structure.taxonomy
	transfers = tuple(transfers)
	handelsbilanz = {key: value for key, value in calculation.amounts().items() if not key[1].prior}
	if structure.case.steuerbilanz:
		findings = (
			(
				Finding(
					"170205095",
					"Eine Steuerbilanz hat keine Überleitungsrechnung; Unterschiede zur Handelsbilanz meldet eine "
					"Handelsbilanz (Bilanzierungsstandard HGBM).",
					f"{leitfaden(taxonomy, 'B.16.1')}; {rule(taxonomy, '170205095')}",
					unqualified(TRANSFER),
				),
			)
			if transfers
			else ()
		)
		return Ueberleitung(structure, (), handelsbilanz, findings)
	findings: list[Finding] = []
	kept = [transfer for transfer in transfers if _accepted(structure, transfer, findings)]
	groups: list[tuple[Kind, list[Transfer], dict[str, list[Decimal]]]] = []
	for kind in Kind:
		mine = [transfer for transfer in kept if transfer.kind is kind]
		if mine:
			groups.append((kind, mine, _leaves(mine)))
	changes = _propagated(structure, [leaves for _, _, leaves in groups])
	assets, liabilities, result = (
		changes.get(name, (ZERO, ZERO)) for name in (ASSETS, EQUITY_AND_LIABILITIES, NET_INCOME)
	)
	own: dict[str, list[Decimal]] = {}
	current_difference, previous_difference = assets[0] - liabilities[0], assets[1] - liabilities[1]
	if current_difference:
		own[CURRENT_DIFFERENCE] = [current_difference, ZERO]
	if previous_difference:
		own[PREVIOUS_DIFFERENCE] = [ZERO, previous_difference]
	if current_difference != result[0]:
		own[COLLECTIVE_ITEM] = [current_difference - result[0], ZERO]
	if own:
		position = next(
			(index for index, (kind, _, _) in enumerate(groups) if kind is not Kind.UMGLIEDERUNG), None
		)
		if position is None:
			groups.append((Kind.WERTAENDERUNG, [], own))
		else:
			for name, deltas in own.items():
				target = groups[position][2].setdefault(name, [ZERO, ZERO])
				target[0] += deltas[0]
				target[1] += deltas[1]
	written = []
	total: dict[str, list[Decimal]] = {}
	for kind, mine, leaves in groups:
		propagated = _propagated(structure, [leaves])
		for name, (current, previous) in propagated.items():
			target = total.setdefault(name, [ZERO, ZERO])
			target[0] += current
			target[1] += previous
		written.append(
			Group(
				kind,
				tuple(
					Entry(position.concept, *_values(position, propagated[position.concept]))
					for position in structure.positions
					if any(propagated.get(position.concept, ()))
				),
				tuple(mine),
			)
		)
		if kind is Kind.UMGLIEDERUNG:
			findings.extend(_moved(structure, propagated))
	steuerbilanz = dict(handelsbilanz)
	for name, (current, previous) in total.items():
		position = structure.position(name)
		key = (name, Period.STICHTAG if position.instant else Period.WIRTSCHAFTSJAHR)
		steuerbilanz[key] = steuerbilanz.get(key, ZERO) + current + previous
	if not written:
		findings.append(
			Finding(
				"170205100",
				"Eine Handelsbilanz hat wenigstens einen Eintrag der Überleitungsrechnung; ohne Unterschiede ist sie eine "
				"Einheitsbilanz (Bilanzierungsstandard HAOE).",
				f"{leitfaden(taxonomy, 'B.15.1')}; {rule(taxonomy, '170205100')}",
				unqualified(TRANSFER),
			)
		)
	elif not any(current or previous for current, previous in total.values()):
		findings.append(
			Finding(
				"170145132",
				"Die Einträge der Überleitungsrechnung heben sich auf: Für keine Position ergeben sie zusammen einen "
				"Betrag ungleich 0.",
				f"{leitfaden(taxonomy, 'B.15.1')}; {rule(taxonomy, '170145132', 'Strukturelle Fehler')}",
				unqualified(TRANSFER),
			)
		)
	findings.extend(_resolved(structure, steuerbilanz))
	return Ueberleitung(structure, tuple(written), steuerbilanz, tuple(findings))


def _accepted(structure: Structure, transfer: Transfer, findings: list[Finding]) -> bool:
	"""Whether the transfer is one of a position of Bilanz or GuV the company changes itself, with a reason."""
	taxonomy = structure.taxonomy
	position = structure.position(transfer.position)
	name = unqualified(transfer.position)
	source = leitfaden(taxonomy, "B.15.1")
	problem = None
	if position is None or position.component not in (BILANZ, GUV):
		problem = (
			"170145086",
			f"„{name}“ ist keine Position von Bilanz oder GuV dieser E-Bilanz.",
			f"{source}; {rule(taxonomy, '170145086', 'Strukturelle Fehler')}",
		)
	elif position.davon_of is not None:
		problem = (
			"EB-DAVON",
			f"„{position.label}“ ist eine davon-Position und geht in keine Rechnung ein; die Überleitung ändert die "
			"Position, deren Teil sie ist.",
			f"{source}; {rule(taxonomy, '170145133', 'Strukturelle Fehler')}",
		)
	elif _derived(structure, position):
		problem = (
			"EB-UEBERLEITUNG-BERECHNET",
			f"„{position.label}“ leitet Steuerbote selbst über: Summen aus den Positionen darunter, Ausgleichsposten, "
			"Jahresüberschuss und Sammelposten aus den übrigen Einträgen.",
			source,
		)
	elif transfer.current is None and transfer.previous is None:
		problem = (
			"170145129",
			f"Der Eintrag zu „{position.label}“ hat keine Wertänderung.",
			f"{source}; {rule(taxonomy, '170145129', 'Strukturelle Fehler')}",
		)
	elif transfer.previous is not None and not _entry_of(position.concept)[1]:
		problem = (
			"EB-UEBERLEITUNG-VORPERIODE",
			f"„{position.label}“ ist ein Posten der GuV; nur Positionen der Bilanz haben Wertänderungen aus Vorperioden.",
			leitfaden(taxonomy, "A.11, B.15.1"),
		)
	elif not transfer.reason.strip():
		problem = (
			"EB-UEBERLEITUNG-BEGRUENDUNG",
			f"Der Eintrag zu „{position.label}“ braucht eine Begründung: § 5b Abs. 1 Satz 2 EStG passt nur an, was den "
			"steuerlichen Vorschriften nicht entspricht.",
			"§ 5b Abs. 1 Satz 2 EStG; docs/roadmap.md, Grundsätze",
		)
	if problem is not None:
		code, text, reference = problem
		findings.append(Finding(code, text, reference, name))
	return problem is None


def _derived(structure: Structure, position: Position) -> bool:
	"""Whether Steuerbote writes the entry of the position itself: a total, a part of the Ausgleichsposten, the
	Jahresüberschuss of the Bilanz or the Sammelposten."""
	taxonomy = structure.taxonomy
	if position.concept in DERIVED or position.concept.startswith(TAX_BALANCE):
		return True
	network = taxonomy.calculation[position.role]
	return any(structure.position(arc.child) is not None for arc in network.children(position.concept))


def _leaves(transfers: Iterable[Transfer]) -> dict[str, list[Decimal]]:
	leaves: dict[str, list[Decimal]] = {}
	for transfer in transfers:
		target = leaves.setdefault(transfer.position, [ZERO, ZERO])
		target[0] += transfer.current or ZERO
		target[1] += transfer.previous or ZERO
	return leaves


def _propagated(
	structure: Structure, groups: Iterable[Mapping[str, list[Decimal]]]
) -> dict[str, tuple[Decimal, Decimal]]:
	"""The changes of the positions of the groups with those of each total above them, by the weights of the
	calculation."""
	changes: dict[str, list[Decimal]] = {}
	for leaves in groups:
		for name, (current, previous) in leaves.items():
			weight = Decimal(1)
			position = structure.position(name)
			while position is not None:
				target = changes.setdefault(position.concept, [ZERO, ZERO])
				target[0] += weight * current
				target[1] += weight * previous
				weight *= position.weight
				position = structure.position(position.parent) if position.parent is not None else None
	return {name: (current, previous) for name, (current, previous) in changes.items()}


def _values(position: Position, change: tuple[Decimal, Decimal]) -> tuple[Decimal, Decimal | None]:
	"""The Wertänderungen an entry writes: the current one, and for a position of the Bilanz that of earlier years
	where there is one."""
	current, previous = change
	if not _entry_of(position.concept)[1]:
		return current, None
	return current, previous if previous else None


def _entry_of(concept: str) -> tuple[str, bool]:
	"""The entry of a position, „Aktivposition“ or „Passivposition“ with a Wertänderung of earlier years, else
	„GuV-Posten“ without (Leitfaden B.15.1.1 to B.15.1.3)."""
	if concept == ASSETS or concept.startswith(f"{ASSETS}."):
		return "bsAss", True
	if concept == EQUITY_AND_LIABILITIES or concept.startswith(f"{EQUITY_AND_LIABILITIES}."):
		return "bsEqLiab", True
	return "isChangeNetIncome", False


def _entry(entry: Entry) -> Tuple:
	kind, previous = _entry_of(entry.position)
	period = Period.WIRTSCHAFTSJAHR
	base = f"{TRANSFER}.{kind}"
	children: list[Item] = [
		Item(f"{base}.name", period, entry.position),
		amount(f"{base}.changeValueActualPeriod", period, entry.current),
	]
	if previous and entry.previous is not None:
		children.append(amount(f"{base}.changeValuePreviousPeriod", period, entry.previous))
	return Tuple(f"{TRANSFER}.{kind}", tuple(children))


def _moved(structure: Structure, propagated: Mapping[str, tuple[Decimal, Decimal]]) -> Iterable[Finding]:
	"""An Umgliederung changes neither the Eigenkapital nor the result (Leitfaden A.11)."""
	assets = propagated.get(ASSETS, (ZERO, ZERO))
	liabilities = propagated.get(EQUITY_AND_LIABILITIES, (ZERO, ZERO))
	result = propagated.get(NET_INCOME, (ZERO, ZERO))
	equity = assets[0] + assets[1] - liabilities[0] - liabilities[1]
	if equity or result[0]:
		yield Finding(
			"EB-UMGLIEDERUNG",
			f"Die Umgliederungen ändern das Eigenkapital um {euro(equity)} und das Ergebnis um {euro(result[0])}; eine "
			"Umgliederung verschiebt Beträge, eine Änderung der Wertansätze ist eine Wertänderung.",
			leitfaden(structure.taxonomy, "A.11"),
			unqualified(TRANSFER),
			Severity.HINT,
		)


def _resolved(structure: Structure, steuerbilanz: Mapping[tuple[str, Period], Decimal]) -> Iterable[Finding]:
	"""A position of the Bilanz „steuerlich“ not permitted is zero after the Überleitung (Leitfaden B.15.2)."""
	taxonomy = structure.taxonomy
	for position in structure.of(BILANZ):
		concept = taxonomy.concepts[position.concept]
		value = steuerbilanz.get((position.concept, Period.STICHTAG))
		if not concept.permitted_for(NOT_PERMITTED_FISCAL) and value:
			yield Finding(
				"EB-UEBERLEITUNG-STEUERLICH",
				f"„{position.label}“ ist steuerlich nicht zulässig und hat nach der Überleitung noch {euro(value)}; die "
				"Überleitungsrechnung löst sie auf null auf.",
				f"{leitfaden(taxonomy, 'A.11, B.15.2')}; {rule(taxonomy, '170165095', 'Strukturelle Fehler')}",
				unqualified(position.concept),
			)
