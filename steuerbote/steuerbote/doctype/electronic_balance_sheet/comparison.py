"""The Handelsbilanz of the E-Bilanz against the Jahresabschluss of its year (Annual Accounts), without Frappe.

Why. „Wird der Gewinn nach § 4 Absatz 1, § 5 oder § 5a ermittelt, so ist der Inhalt der Bilanz, der Gewinn- und
Verlustrechnung [...] nach amtlich vorgeschriebenem Datensatz durch Datenfernübertragung zu übermitteln“ (§ 5b Abs. 1
Satz 1 EStG): the Bilanz the E-Bilanz transmits is that of the Jahresabschluss, whose Feststellung the shareholders
resolve (§ 42a Abs. 2 Satz 1 GmbHG), and for a Gewerbetreibender it is the base of the Steuerbilanz, „das
Betriebsvermögen anzusetzen [...], das nach den handelsrechtlichen Grundsätzen ordnungsmäßiger Buchführung auszuweisen
ist“ (§ 5 Abs. 1 Satz 1 EStG). Where the Steuerbilanz differs, the Handelsbilanz stays and the Überleitungsrechnung
adapts it (§ 5b Abs. 1 Satz 2 EStG, § 60 Abs. 2 Satz 1 EStDV, Leitfaden A.11). A Handelsbilanz in the E-Bilanz that is
not the festgestellte one is no Überleitung: it is a Bilanz of other books, as after a posting since the Feststellung.

What. Both read the same books through the same Balance Sheet Mapping, the Jahresabschluss in the commercial view of the
HGB-Taxonomie with the positions of the § 266 HGB scheme of its size class, the E-Bilanz in the fiscal view with its
deeper positions, whose ancestors the scheme positions are (steuerbote/hgb/schemes.py). So compared() takes, of the
statement the Jahresabschluss files in the full euros its Offenlegung shows (steuerbote.hgb.statement.in_full_euros):

- for a Handelsbilanz with Überleitungsrechnung (HGBM), every position of its Bilanz, the Summe Aktiva and the Summe
  Passiva and the Jahresüberschuss of its GuV, against the amounts of the Handelsbilanz of the E-Bilanz, the side
  before the Überleitung, wherever the E-Bilanz carries the position;
- for an Einheitsbilanz (HAOE), which the tax administration takes as a Steuerbilanz (Leitfaden B.13) and whose
  positions the company may have adapted to the tax rules already, the Summe Aktiva and the Jahresüberschuss as a check
  of plausibility;
- for a Steuerbilanz (AO) nothing: it is drawn up for the taxes on its own and is no Handelsbilanz.

A position of the Jahresabschluss in full euros is less than a euro from its amount in euros and cents, as the E-Bilanz
reports it, so a difference of less than a euro is rounding. A difference beyond it is an error where the
Jahresabschluss is festgestellt, which holds the E-Bilanz back from „Bereit“, and a hint where it is not yet, since the
Jahresabschluss may still change. A company may draw its Jahresabschluss up outside Steuerbote, so without one nothing
is compared, which the empty field of the E-Bilanz shows; before Berechnen built the statement of one, a hint says
that nothing was compared.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from steuerbote.ebilanz.positions import AccountingStandard, euro
from steuerbote.hgb.statement import AnnualStatement, in_full_euros
from steuerbote.jahresmeldung.findings import Finding, Severity

DIFFERENCE = "SB-JA-ABWEICHUNG"
MISSING = "SB-JA-FEHLT"
CODES = (DIFFERENCE, MISSING)
"""The codes of the findings of the comparison, which the bridge lists among those of Steuerbote (bridge.CODES)."""
AKTIVA, PASSIVA, NET_INCOME = "bs.ass", "bs.eqLiab", "is.netIncome"
ROUNDING = Decimal("1")
"""A position in full euros is less than a euro from its euros and cents (steuerbote.ustva.rounding)."""
SOURCES = (
	"§ 5 Abs. 1 Satz 1, § 5b Abs. 1 Satz 1 und 2 EStG; § 60 Abs. 2 Satz 1 EStDV; § 42a Abs. 2 Satz 1 GmbHG"
)


@dataclass(frozen=True, slots=True)
class Accounts:
	"""The Jahresabschluss the E-Bilanz is compared with: its name, the statement it files, None while Berechnen has not
	built one, and whether it is festgestellt and not replaced."""

	name: str
	statement: AnnualStatement | None
	festgestellt: bool


@dataclass(frozen=True, slots=True)
class Difference:
	"""A position whose amount in the E-Bilanz is not that of the Jahresabschluss, beyond rounding."""

	concept: str
	label: str
	ebilanz: Decimal
	accounts: Decimal

	@property
	def amount(self) -> Decimal:
		return self.ebilanz - self.accounts


def compared(
	statement: AnnualStatement, standard: AccountingStandard
) -> tuple[tuple[str, str, Decimal], ...]:
	"""The positions of the Jahresabschluss the comparison takes, each by its concept without the prefix of its module,
	with its label and its amount in full euros; see the module docstring."""
	if standard is AccountingStandard.STEUERBILANZ:
		return ()
	rounded = in_full_euros(statement)
	sheet = rounded.balance_sheet
	aktiva = (AKTIVA, "Summe Aktiva", sheet.aktiva_total)
	result = (NET_INCOME, "Jahresüberschuss/Jahresfehlbetrag", rounded.income_statement.net_income)
	if standard is AccountingStandard.EINHEITSBILANZ:
		return (aktiva, result)
	lines = tuple(
		(line.position.concept, line.label, line.amount) for line in (*sheet.aktiva, *sheet.passiva)
	)
	return (*lines, aktiva, (PASSIVA, "Summe Passiva", sheet.passiva_total), result)


def differences(
	statement: AnnualStatement, standard: AccountingStandard, amount_of: Callable[[str], Decimal | None]
) -> tuple[Difference, ...]:
	"""The positions of compared() whose amount in the E-Bilanz, as ``amount_of`` gives it by concept, is a euro or more
	from that of the Jahresabschluss; a position the E-Bilanz does not carry is left out."""
	found = []
	for concept, label, accounts in compared(statement, standard):
		ebilanz = amount_of(concept)
		if ebilanz is not None and abs(ebilanz - accounts) >= ROUNDING:
			found.append(Difference(concept, label, ebilanz, accounts))
	return tuple(found)


def findings(
	accounts: Accounts | None, standard: AccountingStandard, amount_of: Callable[[str], Decimal | None]
) -> tuple[Finding, ...]:
	"""The findings of the comparison for the table Befunde of the E-Bilanz; see the module docstring."""
	if accounts is None or standard is AccountingStandard.STEUERBILANZ:
		return ()
	if accounts.statement is None:
		return (
			Finding(
				MISSING,
				Severity.HINT,
				f"Der Jahresabschluss {accounts.name} ist nicht berechnet: Berechnen vergleicht die Handelsbilanz der "
				f"E-Bilanz mit ihm, sobald er es ist. (Quelle: {SOURCES})",
				accounts.name,
			),
		)
	if accounts.festgestellt:
		severity = Severity.ERROR
		what = f"im festgestellten Jahresabschluss {accounts.name}"
		then = (
			"Die Handelsbilanz der E-Bilanz ist die festgestellte; ändert eine Buchung nach der Feststellung die "
			"Bücher, wird der Jahresabschluss storniert, berichtigt und neu festgestellt, und eine Abweichung der "
			"Steuerbilanz gehört in die Überleitungsrechnung."
		)
	else:
		severity = Severity.HINT
		what = f"im Jahresabschluss {accounts.name}, der nicht festgestellt ist,"
		then = "Berechnen Sie den Jahresabschluss neu, bevor er festgestellt wird."
	return tuple(
		Finding(DIFFERENCE, severity, _difference_text(difference, what, then), difference.concept)
		for difference in differences(accounts.statement, standard, amount_of)
	)


def _difference_text(difference: Difference, what: str, then: str) -> str:
	return (
		f"{difference.label} [{difference.concept}] beträgt in der E-Bilanz {euro(difference.ebilanz)}, {what} "
		f"{euro(difference.accounts)}: ein Unterschied von {euro(difference.amount)}. {then} (Quelle: {SOURCES})"
	)
