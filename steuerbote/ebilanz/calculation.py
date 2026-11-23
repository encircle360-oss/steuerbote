"""The amounts of the E-Bilanz from the balances of the books: each position in its direction, the sums of the
calculation linkbase, the Jahresüberschuss of the Bilanz from the GuV, the previous year of a Handelsbilanz, the
corrections and lines by hand, and the Betriebsvermögensvergleich.

Sources are the Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025 („Leitfaden“), and the rules of
Jahresdokumentation_Bilanz_Taxonomie_6_9.ods (ERiC documentation 44.3.6.0, sheet „Kontext - Regeln“) and its sheet
„Strukturelle Fehler“, each cited by its Fehlercode.

Input. The Bilanzzuordnung maps each account of the books to a position of the GAAP module, and the balances reader
of Steuerbote sums the accounts of the Bilanz up to the Bilanzstichtag with the opening entries and those of the GuV
over the fiscal year, without the Period Closing Voucher of the fiscal year. calculate() takes what both give as plain
values: an AccountBalance per account, its number and description, the position it maps to or None, and its balance
as debit minus credit in euros and cents; for the Handelsbilanz that shows the previous year (steuerbote.ebilanz.
positions.Case.prior), the balances of the previous year as well. An Adjustment is a correction of a position or a
line by hand, with its reason (steuerbote/jahresmeldung/overrides.py), in the direction of the position.

Signs. „Entspricht die Soll/Haben-Auszeichnung eines Kontos der Soll/Haben-Auszeichnung der Position, dann ist der
Kontensaldo unverändert zu weiteren zugeordneten Konten zu addieren, um den Positionswert zu bestimmen. Bei
abweichenden Soll/Haben-Auszeichnungen eines Kontos, ist der Kontosaldo mit „-1“ zu multiplizieren“ (A.13): a balance
on a debit position adds as debit minus credit, one on a credit position as credit minus debit, so an
Erlösschmälerung on a credit account of the books counts against the Umsatzerlöse.

Sums. A total is the sum of the positions under it in the calculation of its component, each with its weight, „Der
Datensatz ist nach den Vorgaben der Calculation Linkbase daraufhin zu prüfen, dass er rechnerisch korrekt ist“
(B.14.11). A total without a position under it that has an amount has none itself. A balance mapped onto a total that
positions under it share is not added by the calculation, so the total would not be their sum: the amount belongs on
a position under it, the one „Rechnerisch notwendig, soweit vorhanden“ or the Auffangposition (A.10.3, A.10.4).

Jahresüberschuss. Without the Period Closing Voucher no account of the Bilanz holds the result of the fiscal year.
The Bilanz shows it as „Eigenkapital, Jahresüberschuss/-fehlbetrag (Bilanz) - bei Kapitalgesellschaften“
[bs.eqLiab.equity.netIncome], and the result of the GuV is its amount: „Wird kein Bilanzgewinn ausgewiesen und die
Position „Rechtsform“ mit ... einer ausschließlich der Kategorie "KST" zugeordneten Ausprägung berichtet, so muss der
Jahresüberschuss/-fehlbetrag laut GuV mit dem Wert des folgenden Ausdrucks übereinstimmen: Eigenkapital,
Jahresüberschuss/-fehlbetrag (Bilanz) - bei Kapitalgesellschaften + Eigenkapital, steuerlicher Ausgleichsposten,
steuerliches Mehr-/Minderergebnis lfd. Jahr gegenüber HB“ (rule 170405070, B.14.3.2.3.4.1). There is no
Ergebnisverwendung in stage 3 (build contract, 3.2), so the Bilanz shows no Bilanzgewinn: „Ist ... „Bilanz enthält
Ausweis des Bilanzgewinns/Bilanzverlustes“ ... mit „nein“ angegeben, so dürfen im Berichtsteil „Bilanz“ folgende
Positionen nicht werthaltig angegeben sein: „Eigenkapital, Bilanzgewinn / Bilanzverlust (Bilanz) - bei
Kapitalgesellschaften““ (B.9.1.2, rule 170405081). An Eröffnungsbilanz has no GuV and no result.

Refused balances, each a finding that blocks:

- a balance without a position, EB-NICHT-ZUGEORDNET: the E-Bilanz would leave it out;
- a balance on a position the case does not have, EB-POSITION: unknown, of another legal form or format, not for the
  Finanzverwaltung or, in a Steuerbilanz, „steuerlich“ not permitted: „Die mit „steuerlich“ unzulässig
  (notPermittedFor) gekennzeichneten Positionen dürfen in der Steuerbilanz nicht enthalten sein“ (B.16.2; structural
  error 170165095); or of a Sonder- or Ergänzungsbilanz only (A.9.3);
- one on a davon position, EB-DAVON, whose amount is only part of the position above it, so the calculation would
  leave the balance out; its amount is a line by hand;
- one on a position the E-Bilanz computes, EB-BERECHNET: the Jahresüberschuss of the Bilanz and the positions of the
  Betriebsvermögensvergleich;
- one on the Bilanzgewinn (170405081), and one on the Sammelposten für Gewinnänderungen aus der Überleitungsrechnung,
  which „darf im Instanz-Dokument nicht direkt aufgeführt, sondern nur innerhalb der Überleitung/Umgliederung
  referenziert werden“ (structural error 170155121, B.13);
- a balance on a total that positions under it share, EB-SUMME.

Checks. „Summe Aktiva = Summe Passiva“ (B.14.3.2.2, rule 170205010), each valued (170205011, 170205012), for the
current year and, in a Handelsbilanz that shows it, the previous one; a correction of a total, EB-KORREKTUR-SUMME,
which the positions under it decide.

Betriebsvermögensvergleich. „Wird der Berichtsteil „Steuerlicher Betriebsvermögensvergleich“ [BVV] (steuerlicher BVV)
werthaltig übermittelt, werden die in den folgenden Unterabschnitten beschriebenen Prüfungen durchgeführt; dabei sind
jeweils die Steuerbilanzwerte oder übergeleiteten Werte maßgebend.“ (B.14.3.2.12) betriebsvermoegensvergleich() takes
those amounts, of a Steuerbilanz or of the Überleitung of a Handelsbilanz, and what the books do not say, EquityChanges:
the Betriebsvermögen at the end of the previous fiscal year, a Kapitalanpassung, the Entnahmen and Ausschüttungen and
the Einlagen of the fiscal year. The Betriebsvermögen at its end is „bs.eqLiab.equity ./.
bs.ass.deficitNotCoveredByCapital“ (rule 170405114), and the result of the comparison „muss gleich dem
Jahresüberschuss/-fehlbetrag nach steuerlichem BVV sein“ (rule 170405109): where it is not, an Einlage or Ausschüttung
is missing. A value the books do not say is NIL, „Mit NIL übermittelte sowie nicht im Datensatz vorhandene Positionen
sind mit Wert 0 in die angegebenen Berechnungen einzubeziehen“ (B.14.3.2.12). The founding year has no previous
fiscal year: its Betriebsvermögen at the end of the previous year is zero, and the Stammkapital paid in is an Einlage.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType

from steuerbote.ebilanz.positions import (
	Finding,
	Mark,
	Position,
	Structure,
	euro,
	leitfaden,
	qualified,
	rule,
	unqualified,
)
from steuerbote.ustva.rounding import CENT, ZERO
from steuerbote.xbrl.facts import Item, Period, amount, nil
from steuerbote.xbrl.taxonomy import Balance

ASSETS = "de-gaap-ci:bs.ass"
EQUITY_AND_LIABILITIES = "de-gaap-ci:bs.eqLiab"
EQUITY = "de-gaap-ci:bs.eqLiab.equity"
DEFICIT = "de-gaap-ci:bs.ass.deficitNotCoveredByCapital"
NET_INCOME = "de-gaap-ci:is.netIncome"
BALANCE_SHEET_NET_INCOME = "de-gaap-ci:bs.eqLiab.equity.netIncome"
BILANZGEWINN = "de-gaap-ci:bs.eqLiab.equity.profitLoss"
COLLECTIVE_ITEM = "de-gaap-ci:is.netIncome.collItemChangeProfitHbst"
BVV_RESULT = "de-gaap-ci:BVV.profitLoss"
BVV_CURRENT = "de-gaap-ci:BVV.profitLoss.assetsCurrentYear"
BVV_PREVIOUS = "de-gaap-ci:BVV.profitLoss.assetsPreviousYear.assets"
BVV_ADJUSTMENTS = "de-gaap-ci:BVV.profitLoss.assetsPreviousYear.capAdjustments"
BVV_WITHDRAWALS = "de-gaap-ci:BVV.profitLoss.withdrawalDistrib"
BVV_CONTRIBUTIONS = "de-gaap-ci:BVV.profitLoss.contribution"
BILANZ, GUV, BVV = "B", "GuV", "BVV"

type Key = tuple[str, Period]


@dataclass(frozen=True, slots=True)
class AccountBalance:
	"""The balance of an account of the books as debit minus credit, and the position the Bilanzzuordnung maps it to.

	``concept`` names a position of the GAAP module with its prefix or without, None for an account it does not map;
	``prior`` marks a balance of the previous year, which only a Handelsbilanz shows.
	"""

	account: str
	description: str
	concept: str | None
	amount: Decimal
	prior: bool = False

	def __post_init__(self) -> None:
		_require_cents(self.amount, f"the balance of account {self.account}")
		if not str(self.account).strip():
			raise ValueError("an account balance names its account")
		if self.concept is not None:
			object.__setattr__(self, "concept", qualified(self.concept))


@dataclass(frozen=True, slots=True)
class Adjustment:
	"""An amount a position reports instead of the one of the books, in the direction of the position, with its
	reason: a correction, or a line by hand for a position without balances."""

	concept: str
	amount: Decimal
	reason: str
	prior: bool = False

	def __post_init__(self) -> None:
		_require_cents(self.amount, f"the adjustment of {self.concept}")
		if not isinstance(self.reason, str) or not self.reason.strip():
			raise ValueError(f"the adjustment of {self.concept} says why")
		object.__setattr__(self, "concept", qualified(self.concept))


@dataclass(frozen=True, slots=True)
class Line:
	"""An account of the books as the E-Bilanz counts it: the position it lands on and its balance in the direction
	of that position."""

	account: str
	description: str
	concept: str
	amount: Decimal
	prior: bool = False


@dataclass(frozen=True, slots=True)
class Value:
	"""What a position reports for a period: the amount of the books and the amount it reports, None for none."""

	position: Position
	period: Period
	ledger: Decimal | None
	amount: Decimal | None
	adjustment: Adjustment | None = None

	@property
	def concept(self) -> str:
		return self.position.concept


@dataclass(frozen=True)
class Calculation:
	"""The amounts of Bilanz and GuV, and later of the Betriebsvermögensvergleich, with what was found on the way."""

	structure: Structure
	values: tuple[Value, ...]
	lines: tuple[Line, ...]
	"""Every account that lands on a position, in the order of the balances."""
	findings: tuple[Finding, ...]
	_by_key: Mapping[Key, Value] = field(init=False, repr=False, compare=False)

	def __post_init__(self) -> None:
		object.__setattr__(
			self, "_by_key", MappingProxyType({(value.concept, value.period): value for value in self.values})
		)

	def value(self, concept: str, period: Period | None = None) -> Value | None:
		"""The value of a position for a period, by default the current one of its period type."""
		position = self.structure.position(concept)
		if position is None:
			return None
		return self._by_key.get((position.concept, period or _current(position)))

	def amount(self, concept: str, period: Period | None = None) -> Decimal | None:
		found = self.value(concept, period)
		return None if found is None else found.amount

	def amounts(self) -> dict[Key, Decimal]:
		"""Every amount reported, by position and period."""
		return {key: value.amount for key, value in self._by_key.items() if value.amount is not None}

	def facts(self) -> tuple[Item, ...]:
		"""The items of the positions: each amount, each Mussfeld and Summenmussfeld of the current year without one
		as NIL (Leitfaden B.14.2.3), and above each item its Oberpositionen, NIL where they have no amount (B.14.10)."""
		return items(self.structure, self.amounts())


def calculate(
	structure: Structure, balances: Iterable[AccountBalance], adjustments: Iterable[Adjustment] = ()
) -> Calculation:
	"""The amounts of Bilanz and GuV from the balances of the books and the adjustments of the company."""
	balances = tuple(balances)
	adjustments = tuple(adjustments)
	case = structure.case
	findings: list[Finding] = []
	direct: dict[Key, Decimal] = {}
	lines: list[Line] = []
	for balance in balances:
		if balance.prior and not case.prior:
			raise ValueError(f"the E-Bilanz shows no previous year for account {balance.account}")
		position = _booked_position(structure, balance, findings)
		if position is None:
			continue
		period = _period(position, balance.prior)
		signed = balance.amount if position.balance is Balance.DEBIT else -balance.amount
		direct[(position.concept, period)] = direct.get((position.concept, period), ZERO) + signed
		lines.append(Line(balance.account, balance.description, position.concept, signed, balance.prior))
	periods = (Period.STICHTAG, Period.WIRTSCHAFTSJAHR)
	if case.prior:
		periods += (Period.VORJAHR_STICHTAG, Period.VORJAHR)
	ledger = _summed(structure, direct, periods, findings, lines)
	corrected = dict(direct)
	chosen: dict[Key, Adjustment] = {}
	for adjustment in adjustments:
		if adjustment.prior and not case.prior:
			raise ValueError(
				f"the E-Bilanz shows no previous year for the adjustment of {adjustment.concept}"
			)
		position = _adjusted_position(structure, adjustment, findings)
		if position is None:
			continue
		key = (position.concept, _period(position, adjustment.prior))
		corrected[key] = adjustment.amount
		chosen[key] = adjustment
	reported = _summed(structure, corrected, periods, [], ())
	values = []
	for position in structure.positions:
		for period in periods if position.component in (BILANZ, GUV) else ():
			key = (position.concept, period)
			if reported.get(key) is not None or ledger.get(key) is not None:
				values.append(Value(position, period, ledger.get(key), reported.get(key), chosen.get(key)))
	findings.extend(_balanced(structure, reported, case.prior))
	return Calculation(structure, tuple(values), tuple(lines), tuple(findings))


@dataclass(frozen=True, slots=True)
class EquityChanges:
	"""What the books do not tell the Betriebsvermögensvergleich, in euros and cents, None for NIL.

	``previous_equity`` is the Betriebsvermögen at the end of the previous fiscal year, the Eigenkapital of its
	Steuerbilanz, zero in the founding year; ``withdrawals`` are the Entnahmen and Ausschüttungen, ``contributions``
	the Einlagen and Kapitalzuführungen of the fiscal year, ``capital_adjustments`` a Kapitalanpassung.
	"""

	previous_equity: Decimal | None = None
	capital_adjustments: Decimal | None = None
	withdrawals: Decimal | None = None
	contributions: Decimal | None = None

	def __post_init__(self) -> None:
		for name in ("previous_equity", "capital_adjustments", "withdrawals", "contributions"):
			value = getattr(self, name)
			if value is not None:
				_require_cents(value, name)


@dataclass(frozen=True)
class Betriebsvermoegensvergleich:
	"""The Betriebsvermögensvergleich of the E-Bilanz: its amounts and what its checks found."""

	structure: Structure
	amounts: Mapping[str, Decimal | None]
	"""Each position of the comparison with its amount, None for NIL."""
	findings: tuple[Finding, ...]

	def facts(self) -> tuple[Item, ...]:
		return items(
			self.structure,
			{
				(concept, Period.WIRTSCHAFTSJAHR): value
				for concept, value in self.amounts.items()
				if value is not None
			},
			(BVV,),
		)


def betriebsvermoegensvergleich(
	structure: Structure, amounts: Mapping[Key, Decimal], changes: EquityChanges
) -> Betriebsvermoegensvergleich:
	"""The comparison from the amounts of the Steuerbilanz, or of the Überleitung of a Handelsbilanz, and the changes
	of the equity the books do not say (Leitfaden B.14.3.2.12)."""
	taxonomy = structure.taxonomy
	equity = amounts.get((EQUITY, Period.STICHTAG), ZERO)
	deficit = amounts.get((DEFICIT, Period.STICHTAG), ZERO)
	leaves: dict[Key, Decimal] = {(BVV_CURRENT, Period.WIRTSCHAFTSJAHR): equity - deficit}
	for concept, value in (
		(BVV_PREVIOUS, changes.previous_equity),
		(BVV_ADJUSTMENTS, changes.capital_adjustments),
		(BVV_WITHDRAWALS, changes.withdrawals),
		(BVV_CONTRIBUTIONS, changes.contributions),
	):
		if value is not None and structure.position(concept) is not None:
			leaves[(concept, Period.WIRTSCHAFTSJAHR)] = value
	summed = _summed(structure, leaves, (Period.WIRTSCHAFTSJAHR,), [], (), components=(BVV,))
	result = {
		position.concept: summed.get((position.concept, Period.WIRTSCHAFTSJAHR))
		for position in structure.of(BVV)
	}
	findings = []
	net_income = amounts.get((NET_INCOME, Period.WIRTSCHAFTSJAHR))
	compared = result.get(BVV_RESULT) or ZERO
	if net_income is not None and net_income != compared:
		findings.append(
			Finding(
				"170405109",
				f"Der Betriebsvermögensvergleich ergibt {euro(compared)}, der Jahresüberschuss der GuV ist "
				f"{euro(net_income)}: Es fehlen Einlagen oder Ausschüttungen von {euro(compared - net_income)}, "
				"oder das Betriebsvermögen des Vorjahres stimmt nicht.",
				f"{leitfaden(taxonomy, 'B.14.3.2.12')}; {rule(taxonomy, '170405109')}",
				unqualified(BVV_RESULT),
			)
		)
	return Betriebsvermoegensvergleich(structure, MappingProxyType(result), tuple(findings))


def items(
	structure: Structure, amounts: Mapping[Key, Decimal], components: tuple[str, ...] = (BILANZ, GUV)
) -> tuple[Item, ...]:
	"""The items of the positions of the components: each amount, NIL for each required position of the current year
	without one, and the Oberpositionen of each item, NIL where they have no amount (Leitfaden B.14.2.3, B.14.10)."""
	required = frozenset(structure.required)
	reported: dict[Key, Decimal | None] = {}
	for position in structure.positions:
		if position.component not in components:
			continue
		for period in _periods(position, structure.case.prior):
			key = (position.concept, period)
			if key in amounts:
				reported[key] = amounts[key]
			elif position.mark.required and position.concept in required and not period.prior:
				reported[key] = None
	for concept, period in tuple(reported):
		if period.prior:
			continue
		network = structure.taxonomy.presentation[structure.position(concept).role]
		for above in _presentation_ancestors(network, concept):
			if structure.position(above) is not None and (above, period) not in reported:
				reported[(above, period)] = None
	ordered = []
	for position in structure.positions:
		for period in _periods(position, structure.case.prior):
			key = (position.concept, period)
			if key in reported:
				value = reported[key]
				ordered.append(
					nil(position.concept, period)
					if value is None
					else amount(position.concept, period, value)
				)
	return tuple(ordered)


def _booked_position(
	structure: Structure, balance: AccountBalance, findings: list[Finding]
) -> Position | None:
	"""The position a balance lands on, or None with the finding why it lands on none."""
	taxonomy = structure.taxonomy
	if balance.amount == ZERO:
		return None
	account = (
		f"Konto {balance.account} ({balance.description})"
		if balance.description
		else f"Konto {balance.account}"
	)
	source = leitfaden(taxonomy, "A.13")
	if balance.concept is None:
		findings.append(
			Finding(
				"EB-NICHT-ZUGEORDNET",
				f"{account} hat einen Saldo von {euro(balance.amount)}, aber keine Position in der Bilanzzuordnung; die "
				"E-Bilanz ließe ihn aus.",
				"§ 5b Abs. 1 Satz 1 EStG; " + source,
				balance.account,
			)
		)
		return None
	position = structure.position(balance.concept)
	name = unqualified(balance.concept)
	if position is None:
		if taxonomy.has(balance.concept):
			why = (
				f"„{taxonomy.label(balance.concept)}“ zugeordnet, einer Position, die diese E-Bilanz nicht hat: nicht "
				"für die Rechtsform, das GuV-Format oder die Finanzverwaltung, nicht gültig im Wirtschaftsjahr oder, in "
				"einer Steuerbilanz, steuerlich nicht zulässig."
			)
		else:
			why = f"„{name}“ zugeordnet, die es in der Taxonomie {taxonomy.version} nicht gibt."
		findings.append(
			Finding(
				"EB-POSITION",
				f"{account} ist {why}",
				leitfaden(taxonomy, "B.4.2, B.11, B.14.3.1.15, B.14.4.1, B.14.6, B.16.2"),
				name,
			)
		)
		return None
	if position.component not in (BILANZ, GUV):
		findings.append(
			Finding(
				"EB-BERECHNET",
				f"{account} ist „{position.label}“ zugeordnet, einer Position des Betriebsvermögensvergleichs, den die "
				"E-Bilanz aus Bilanz, GuV und den Angaben zu Einlagen und Ausschüttungen berechnet.",
				leitfaden(taxonomy, "B.14.3.2.12"),
				name,
			)
		)
		return None
	refusal = _refusal(structure, position)
	if refusal is not None:
		code, text, reference = refusal
		findings.append(
			Finding(code, f"{account} ist „{position.label}“ zugeordnet: {text}", reference, name)
		)
		return None
	return position


def _refusal(structure: Structure, position: Position) -> tuple[str, str, str] | None:
	"""Why a position takes no balance of the books, as code, text and source; None if it takes one."""
	taxonomy = structure.taxonomy
	if position.davon_of is not None:
		return (
			"EB-DAVON",
			f"Eine davon-Position ist nur ein Teil von „{taxonomy.label(position.davon_of)}“ und geht in keine Rechnung "
			"ein; das Konto gehört auf die Position, deren Teil es ist, der davon-Betrag ist eine Zeile von Hand.",
			"BMF-Schreiben vom 28.09.2011, BStBl I S. 855, Anlage zu Rn. 11",
		)
	if position.concept == BALANCE_SHEET_NET_INCOME:
		return (
			"EB-BERECHNET",
			"Den Jahresüberschuss der Bilanz übernimmt die E-Bilanz aus der GuV; ein Konto darauf zählte ihn doppelt.",
			f"{leitfaden(taxonomy, 'B.14.3.2.3.4.1')}; {rule(taxonomy, '170405070')}",
		)
	if position.concept == BILANZGEWINN:
		return (
			"170405081",
			"Die E-Bilanz zeigt den Jahresüberschuss und keinen Bilanzgewinn; eine Ergebnisverwendung kennt Steuerbote "
			"noch nicht.",
			f"{leitfaden(taxonomy, 'B.9.1.2')}; {rule(taxonomy, '170405081')}",
		)
	if position.concept == COLLECTIVE_ITEM:
		return (
			"170155121",
			"Der Sammelposten steht nur in der Überleitungsrechnung, nie in Bilanz oder GuV.",
			f"{leitfaden(taxonomy, 'B.13')}; {rule(taxonomy, '170155121', 'Strukturelle Fehler')}",
		)
	if structure.taxonomy.concepts[position.concept].fiscal.special_balance_only:
		return (
			"EB-POSITION",
			"Die Position hat nur in einer Sonder- oder Ergänzungsbilanz einen Wert.",
			leitfaden(taxonomy, "A.9.3"),
		)
	return None


def _adjusted_position(
	structure: Structure, adjustment: Adjustment, findings: list[Finding]
) -> Position | None:
	position = structure.position(adjustment.concept)
	taxonomy = structure.taxonomy
	name = unqualified(adjustment.concept)
	if position is None or position.component not in (BILANZ, GUV):
		findings.append(
			Finding(
				"EB-POSITION",
				f"Die Korrektur von „{name}“ hat keine Position in Bilanz oder GuV dieser E-Bilanz.",
				leitfaden(taxonomy, "B.11"),
				name,
			)
		)
		return None
	network = taxonomy.calculation[position.role]
	parts = [arc for arc in network.children(position.concept) if structure.position(arc.child) is not None]
	if parts or position.concept == BALANCE_SHEET_NET_INCOME:
		findings.append(
			Finding(
				"EB-KORREKTUR-SUMME",
				f"„{position.label}“ ergibt sich aus den Positionen darunter; korrigiert wird eine von ihnen.",
				leitfaden(taxonomy, "B.14.11"),
				name,
			)
		)
		return None
	return position


def _summed(
	structure: Structure,
	direct: Mapping[Key, Decimal],
	periods: tuple[Period, ...],
	findings: list[Finding],
	lines: Iterable[Line],
	components: tuple[str, ...] = (BILANZ, GUV),
) -> dict[Key, Decimal | None]:
	"""Each position with its amount: its own, or the sum of the positions under it; the Jahresüberschuss of the
	Bilanz from the GuV. A total with an own amount and positions under it that have one is a finding."""
	taxonomy = structure.taxonomy
	result: dict[Key, Decimal | None] = {}
	accounts = {}
	for line in lines:
		accounts.setdefault((line.concept, _period(structure.position(line.concept), line.prior)), []).append(
			line
		)

	def total(position: Position, period: Period) -> Decimal | None:
		key = (position.concept, period)
		if key in result:
			return result[key]
		own = direct.get(key)
		result_of_the_year = structure.position(NET_INCOME)
		if position.concept == BALANCE_SHEET_NET_INCOME and result_of_the_year is not None:
			own = total(result_of_the_year, _duration(period))
		network = taxonomy.calculation[position.role]
		parts = [
			(arc.weight or Decimal(1)) * part
			for arc in network.children(position.concept)
			if (child := structure.position(arc.child)) is not None
			and (part := total(child, period)) is not None
		]
		if parts and own is not None:
			findings.append(_on_a_total(structure, position, period, own, accounts.get(key, ())))
		found = None if own is None and not parts else (own or ZERO) + sum(parts, ZERO)
		result[key] = found
		return found

	for position in structure.positions:
		if position.component in components:
			for period in periods:
				if period.instant == position.instant:
					total(position, period)
	return result


def _on_a_total(
	structure: Structure, position: Position, period: Period, own: Decimal, lines: Iterable[Line]
) -> Finding:
	taxonomy = structure.taxonomy
	candidates = [
		f"„{child.label}“"
		for arc in taxonomy.calculation[position.role].children(position.concept)
		if (child := structure.position(arc.child)) is not None
		and child.mark in (Mark.AUFFANG, Mark.RECHNERISCH_NOTWENDIG)
	]
	accounts = ", ".join(line.account for line in lines)
	text = (
		f"Auf „{position.label}“ selbst stehen {euro(own)}"
		+ (f" (Konten {accounts})" if accounts else "")
		+ ", obwohl Positionen darunter Beträge haben; ihre Summe ergäbe die Position ohne diesen Betrag. Er gehört "
		+ (
			f"auf eine Position darunter, etwa {' oder '.join(candidates)}."
			if candidates
			else "auf eine Position darunter."
		)
	)
	reference = unqualified(position.concept) + (f" {period.value}" if period.prior else "")
	return Finding("EB-SUMME", text, leitfaden(taxonomy, "A.10.3, A.10.4, B.14.11"), reference)


def _balanced(structure: Structure, amounts: Mapping[Key, Decimal | None], prior: bool) -> list[Finding]:
	"""„Summe Aktiva = Summe Passiva“, both valued (Leitfaden B.14.3.2.2; rules 170205010 to 170205012)."""
	taxonomy = structure.taxonomy
	findings = []
	for period in (Period.STICHTAG, *((Period.VORJAHR_STICHTAG,) if prior else ())):
		assets = amounts.get((ASSETS, period))
		liabilities = amounts.get((EQUITY_AND_LIABILITIES, period))
		suffix = " des Vorjahres" if period.prior else ""
		for code, concept, found in (
			("170205011", ASSETS, assets),
			("170205012", EQUITY_AND_LIABILITIES, liabilities),
		):
			if found is None:
				findings.append(
					Finding(
						code,
						f"„{taxonomy.label(concept)}“{suffix} hat keinen Betrag: Die Bilanz hat keine Position mit Saldo.",
						f"{leitfaden(taxonomy, 'B.14.3.2.1')}; {rule(taxonomy, code)}",
						unqualified(concept),
					)
				)
		if assets is not None and liabilities is not None and assets != liabilities:
			findings.append(
				Finding(
					"170205010",
					f"Die Summe der Aktiva{suffix} ist {euro(assets)}, die der Passiva {euro(liabilities)}: Es fehlen "
					f"{euro(abs(assets - liabilities))}, etwa ein Konto ohne Saldo im Bericht oder eine Buchung.",
					f"{leitfaden(taxonomy, 'B.14.3.2.2')}; {rule(taxonomy, '170205010')}",
					unqualified(ASSETS),
				)
			)
	return findings


def _period(position: Position, prior: bool) -> Period:
	if position.instant:
		return Period.VORJAHR_STICHTAG if prior else Period.STICHTAG
	return Period.VORJAHR if prior else Period.WIRTSCHAFTSJAHR


def _current(position: Position) -> Period:
	return _period(position, False)


def _duration(period: Period) -> Period:
	return Period.VORJAHR if period.prior else Period.WIRTSCHAFTSJAHR


def _periods(position: Position, prior: bool) -> tuple[Period, ...]:
	return (_period(position, False), *((_period(position, True),) if prior else ()))


def _presentation_ancestors(network, name: str):
	while arcs := network.parents(name):
		name = arcs[0].parent
		yield name


def _require_cents(value: object, what: str) -> None:
	if isinstance(value, bool) or not isinstance(value, Decimal):
		raise TypeError(f"{what} is a Decimal, not {type(value).__name__}")
	if not value.is_finite() or value != value.quantize(CENT):
		raise ValueError(f"{what} is {value}, not an amount in euros and cents")
