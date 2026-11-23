"""The Kontensalden of the E-Bilanz: a tuple „Kontensalden zu einer Position“ for each account of the books with a
balance, and the reason that leaves them out where the taxonomy 6.9 lets it.

Duty. „Für Wirtschaftsjahre, die nach dem 31. Dezember 2024 beginnen, ist der Inhalt der Bilanz und Gewinn- und
Verlustrechnung (GuV) jeweils einschließlich der unverdichteten Kontennachweise mit Kontensalden nach amtlich
vorgeschriebenen Datensatz durch Datenfernübertragung zu übermitteln.“ and „Ein unverdichteter Kontennachweis umfasst
zumindest alle Sachkonten der Buchführung (Hauptbuch), die am Ende des Wirtschaftsjahres einen Saldo aufweisen. Eine
Verdichtung einzelner Sachkonten zu Kontengruppen oder zu anderen Merkmalen ist grundsätzlich nicht zulässig.“ (BMF
letter of 10 June 2025, IV C 6 - S 2133-b/00064/002/006; § 5b Abs. 1 Satz 1 EStG). The accounts of the Nebenbücher are
not sent („Eine zusätzliche Bereitstellung von Konten der Nebenbücher ... hat nicht zu erfolgen.“): ERPNext keeps the
parties as fields of its accounts, so every account of its ledger is a Sachkonto.

Tuples. Each line of steuerbote/ebilanz/calculation.py of the current year, an account with a balance that lands on
a position, becomes one tuple with the four parts „Name der Position“, „Kontonummer“, „Kontobeschreibung“ and
„Kontosaldo“: „Bei Übermittlung eines Kontensaldos müssen für diesen alle Elemente ... übermittelt werden. Diese
dürfen nicht leer übermittelt werden.“ (Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025, B.12; structural
error 170195097). The name is the position with the prefix of its module, a QName (ERiC E-Bilanz-Dokumentation für
HGB-Taxonomie 6.9, Kap. 3.12), always a position valued for the current year (B.12, 170195102), since the lines land
on positions that have an amount; the Kontensaldo is the balance in the direction of the position, as „Die Summe der
Werte zum Element „Kontosaldo“ soll dem Wert der Taxonomieposition entsprechen.“ (Technischer Leitfaden zur
HGB-Taxonomie 6.10, Stand 08.06.2026, B.12.1). The tuples refer to the fiscal year, D-AKTJAHR, as the Kontensaldo is
that „zum Ende-Stichtag der Berichtsperiode“ (Leitfaden 6.9, A.12). Number and description come from the books in the
characters of ELSTER (steuerbote/elster/charset.py).

Checks. With the component announced, „Wird der Berichtsteil „Bilanz“ oder „Eröffnungsbilanz ohne GuV“ angekündigt,
ist zu mindestens einer dazugehörigen Position ein Kontensaldo zu übermitteln.“, and the same for the GuV (B.12;
structural error 170195104), else an error. Two hints look ahead to taxonomy 6.10, which ERiC 46 takes for real cases
from May 2027: there „zu jeder werthaltig übermittelten rechnerisch verknüpften Position, zu der keine werthaltige
rechnerisch verknüpfte Unterposition vorliegt, [ist] das Tupel „Kontensalden zu einer Position“ mindestens einmal zu
übermitteln“, and the sum of the Kontensalden of a position should be its value (Leitfaden 6.10, B.12.1; rule 170195106
of ERiC 45.1.5.0): a position by hand, without an account, and a correction show here, but the Jahresüberschuss of the
Bilanz, whose amount comes from the GuV and its Kontensalden.

Without Kontensalden. „Um Härtefälle zu vermeiden, wird es für die Übermittlung von E-Bilanzen mit der
Taxonomie-Version 6.9 nicht beanstandet, wenn ... die Bilanz und GuV ohne Kontennachweise ... übermittelt werden. In
diesem Fall sind die Kontennachweise auf anderem Weg beim Finanzamt einzureichen und die konkreten Gründe hierfür in
der Taxonomieposition „Erläuterung, warum eine Übermittlung der Kontennachweise noch nicht möglich ist“ darzulegen.“
(BMF letter of 10 June 2025) A case without the component (steuerbote.ebilanz.positions.Case.kontennachweis) needs that
reason, „Wurde der Berichtsbestandteil "Kontensalden" nicht angekündigt, so muss die "Erläuterung, warum die
Übermittlung der Kontennachweise noch nicht möglich ist" werthaltig angegeben sein.“ (rule 170405002), which the GCD
carries (steuerbote/ebilanz/gcd.py); a taxonomy without that position, 6.10 and later, takes no such case.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from steuerbote.ebilanz.calculation import BALANCE_SHEET_NET_INCOME, BILANZ, GUV, Calculation, Line
from steuerbote.ebilanz.positions import Finding, euro, leitfaden, rule, unqualified
from steuerbote.elster.charset import CharsetError, describe, transliterate
from steuerbote.ustva.rounding import ZERO
from steuerbote.xbrl.checks import Severity
from steuerbote.xbrl.facts import Item, Period, Tuple, amount

ACCOUNT_BALANCES = "de-gaap-ci:detailedInformation.accountBalances"
POSITION_NAME = "de-gaap-ci:detailedInformation.accountbalances.positionName"
ACCOUNT_NUMBER = "de-gaap-ci:detailedInformation.accountbalances.accountNumber"
ACCOUNT_DESCRIPTION = "de-gaap-ci:detailedInformation.accountbalances.accountDescription"
BALANCE = "de-gaap-ci:detailedInformation.accountbalances.amount"
NOT_YET_POSSIBLE = "de-gcd:genInfo.report.id.reportElement.reportElements.transmissionNotYetPossible"
LEITFADEN_6_10 = "Technischer Leitfaden zur HGB-Taxonomie 6.10, B.12.1; ERiC 45.1.5.0, Regel 170195106"
BMF_2025 = "BMF-Schreiben vom 10.06.2025, IV C 6 - S 2133-b/00064/002/006"


@dataclass(frozen=True, slots=True)
class Kontennachweis:
	"""The Kontensalden of an E-Bilanz, or the reason it sends none, with what the checks found."""

	lines: tuple[Line, ...]
	"""Each account of the current year with a balance, its texts in the characters of ELSTER."""
	reason: str
	"""Why the E-Bilanz sends no Kontensalden; empty where it sends them."""
	findings: tuple[Finding, ...]

	def facts(self) -> tuple[Tuple, ...]:
		"""A tuple „Kontensalden zu einer Position“ per line, in the order of the lines."""
		period = Period.WIRTSCHAFTSJAHR
		return tuple(
			Tuple(
				ACCOUNT_BALANCES,
				(
					Item(POSITION_NAME, period, line.concept),
					Item(ACCOUNT_NUMBER, period, line.account),
					Item(ACCOUNT_DESCRIPTION, period, line.description),
					amount(BALANCE, period, line.amount),
				),
			)
			for line in self.lines
		)


def kontennachweis(calculation: Calculation, *, reason: str = "") -> Kontennachweis:
	"""The Kontensalden of the calculation, or, for a case without them, the reason why the E-Bilanz sends none."""
	structure = calculation.structure
	taxonomy = structure.taxonomy
	if not structure.case.kontennachweis:
		return Kontennachweis((), reason.strip(), tuple(_without(calculation, reason.strip())))
	findings: list[Finding] = []
	lines = []
	for line in calculation.lines:
		if line.prior:
			continue
		texts = _texts(line, findings, taxonomy)
		if texts is not None:
			lines.append(Line(texts[0], texts[1], line.concept, line.amount))
	findings.extend(_announced(calculation, lines))
	findings.extend(_ahead(calculation, lines))
	return Kontennachweis(tuple(lines), "", tuple(findings))


def _without(calculation: Calculation, reason: str) -> Iterable[Finding]:
	taxonomy = calculation.structure.taxonomy
	if not taxonomy.has(NOT_YET_POSSIBLE):
		yield Finding(
			"EB-KONTENSALDEN",
			f"Die Taxonomie {taxonomy.version} nimmt keine E-Bilanz ohne Kontensalden; nur 6.9 ließ eine Begründung zu.",
			f"{BMF_2025}; Technischer Leitfaden zur HGB-Taxonomie 6.10, B.12.1",
			unqualified(NOT_YET_POSSIBLE),
		)
	elif not reason:
		yield Finding(
			"170405002",
			"Ohne Kontensalden nennt die E-Bilanz die konkreten Gründe, warum ihre Übermittlung noch nicht möglich ist; "
			"die Kontennachweise gehen dann auf anderem Weg an das Finanzamt.",
			f"{BMF_2025}; {leitfaden(taxonomy, 'B.12')}; {rule(taxonomy, '170405002')}",
			unqualified(NOT_YET_POSSIBLE),
		)


def _texts(line: Line, findings: list[Finding], taxonomy) -> tuple[str, str] | None:
	"""Number and description of an account in the characters of ELSTER, or None with the finding why not."""
	try:
		number, description = transliterate(line.account.strip()), transliterate(line.description.strip())
	except CharsetError as error:
		findings.append(
			Finding(
				"EB-KONTENSALDEN",
				f"Konto {line.account}: Nummer oder Bezeichnung enthält Zeichen, die ELSTER nicht nimmt: "
				f"{', '.join(describe(character) for character in error.characters)}.",
				"ERiC E-Bilanz-Dokumentation für HGB-Taxonomie 6.9, Kap. 3.16",
				line.account,
			)
		)
		return None
	if not description:
		findings.append(
			Finding(
				"170195097",
				f"Konto {line.account} hat keine Bezeichnung; der Kontensaldo braucht Nummer und Bezeichnung des Kontos.",
				f"{leitfaden(taxonomy, 'B.12')}; {rule(taxonomy, '170195097', 'Strukturelle Fehler')}",
				line.account,
			)
		)
		return None
	return number, description


def _announced(calculation: Calculation, lines: Iterable[Line]) -> Iterable[Finding]:
	"""At least one Kontensaldo for the Bilanz and one for the GuV (Leitfaden B.12; structural error 170195104)."""
	structure = calculation.structure
	taxonomy = structure.taxonomy
	held = {structure.position(line.concept).component for line in lines}
	for component, label in ((BILANZ, "Bilanz"), (GUV, "GuV")):
		if component in structure.announced and component not in held:
			yield Finding(
				"170195104",
				f"Zu keiner Position der {label} gibt es einen Kontensaldo.",
				f"{leitfaden(taxonomy, 'B.12')}; {rule(taxonomy, '170195104', 'Strukturelle Fehler')}",
				component,
			)


def _ahead(calculation: Calculation, lines: Iterable[Line]) -> Iterable[Finding]:
	"""The hints of taxonomy 6.10: a valued position of the calculation without a valued position under it has a
	Kontensaldo, and the Kontensalden of a position add up to it (Leitfaden 6.10, B.12.1)."""
	structure = calculation.structure
	taxonomy = structure.taxonomy
	sums: dict[str, Decimal] = {}
	for line in lines:
		sums[line.concept] = sums.get(line.concept, ZERO) + line.amount
	for value in calculation.values:
		position = value.position
		if (
			value.period.prior
			or value.amount is None
			or position.davon_of is not None
			or position.concept == BALANCE_SHEET_NET_INCOME
		):
			continue
		network = taxonomy.calculation[position.role]
		valued_below = any(
			calculation.amount(arc.child, value.period) is not None
			for arc in network.children(position.concept)
		)
		if valued_below:
			continue
		name = unqualified(position.concept)
		if position.concept not in sums:
			yield Finding(
				"EB-KONTENSALDEN-FEHLEN",
				f"Zu „{position.label}“ gibt es keinen Kontensaldo, etwa weil der Betrag von Hand stammt; ab der "
				"Taxonomie 6.10 braucht jede solche Position einen.",
				LEITFADEN_6_10,
				name,
				Severity.HINT,
			)
		elif sums[position.concept] != value.amount:
			yield Finding(
				"EB-KONTENSALDEN-SUMME",
				f"Die Kontensalden zu „{position.label}“ ergeben {euro(sums[position.concept])}, die Position meldet "
				f"{euro(value.amount)}; ab der Taxonomie 6.10 sollen sie übereinstimmen.",
				LEITFADEN_6_10,
				name,
				Severity.HINT,
			)
