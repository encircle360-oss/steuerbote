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
characters of ELSTER (steuerbote/elster/charset.py). From taxonomy 6.10 on the tuple has a fifth part, „Konto nicht
vorhanden oder nicht übermittelbar“ [detailedInformation.accountbalances.notPossible], NIL for an account, as the
examples of Taxonomie_6_10 of the ERiC documentation 45.1.5.0 write it.

Checks. With the component announced, „Wird der Berichtsteil „Bilanz“ oder „Eröffnungsbilanz ohne GuV“ angekündigt,
ist zu mindestens einer dazugehörigen Position ein Kontensaldo zu übermitteln.“, and the same for the GuV (B.12;
structural error 170195104), else an error. Two hints look ahead to taxonomy 6.10, which ERiC 46 takes for real cases
from May 2027: there „zu jeder werthaltig übermittelten rechnerisch verknüpften Position, zu der keine werthaltige
rechnerisch verknüpfte Unterposition vorliegt, [ist] das Tupel „Kontensalden zu einer Position“ mindestens einmal zu
übermitteln“, and the sum of the Kontensalden of a position should be its value (Leitfaden 6.10, B.12.1; rule 170195106
of ERiC 45.1.5.0): a position by hand, without an account, and a correction show here, but the Jahresüberschuss of the
Bilanz, whose amount comes from the GuV and its Kontensalden.

Checks from 6.10 on. Jahresdokumentation_Bilanz_Taxonomie_6_10.ods deletes 170195104 („GELÖSCHT“) for structural error
170195106, „Ein Kontennachweis ist für eine solche Position genau dann erforderlich, wenn sie selbst werthaltig ist und
zu keiner rechnerisch verknüpften Unterposition ein Wert übermittelt wird.“, which the profile FISCAL checks with
170195108 to 170195110 (steuerbote/xbrl/checks.py). A position that takes a Kontensaldo and that no account of the
books lands on, the Jahresüberschuss of the Bilanz and a position by hand, takes the „in Ausnahmefällen anwendbaren
Variante ohne Konteninformationen“: „Kontonummer“ and „Kontobeschreibung“ „nicht werthaltig“, „Konto nicht vorhanden
oder nicht übermittelbar“ „mit dem Wert „true““, „maximal einmal zu einer Position“, and its amount the one of the
position (Leitfaden 6.10, B.12.1); a position by hand shows as a hint. The Kontensalden of a position add up to its
value (B.12.1, quoted above): a correction of a position with accounts is an error, as it belongs in the books. An
account refused for its characters or its description holds the E-Bilanz back by its own finding and takes no
Kontensaldo without account information, since renaming the account sends it.

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

from steuerbote.ebilanz.calculation import BALANCE_SHEET_NET_INCOME, BILANZ, GUV, Calculation, Line, Value
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
NOT_POSSIBLE = "de-gaap-ci:detailedInformation.accountbalances.notPossible"
LEITFADEN_6_10 = "Technischer Leitfaden zur HGB-Taxonomie 6.10, B.12.1; ERiC 45.1.5.0, Regel 170195106"
BMF_2025 = "BMF-Schreiben vom 10.06.2025, IV C 6 - S 2133-b/00064/002/006"


@dataclass(frozen=True, slots=True)
class Kontennachweis:
	"""The Kontensalden of an E-Bilanz, or the reason it sends none, with what the checks found."""

	lines: tuple[Line, ...]
	"""Each account of the current year with a balance, its texts in the characters of ELSTER, and from taxonomy 6.10
	on a line without account, number and description empty, for each position that takes a Kontensaldo and that no
	account lands on."""
	reason: str
	"""Why the E-Bilanz sends no Kontensalden; empty where it sends them."""
	findings: tuple[Finding, ...]
	not_possible: bool = False
	"""Whether the tuples have the part „Konto nicht vorhanden oder nicht übermittelbar“, as from taxonomy 6.10 on."""

	def facts(self) -> tuple[Tuple, ...]:
		"""A tuple „Kontensalden zu einer Position“ per line, in the order of the lines, a line without account with
		Kontonummer and Kontobeschreibung NIL."""
		period = Period.WIRTSCHAFTSJAHR
		return tuple(
			Tuple(
				ACCOUNT_BALANCES,
				(
					Item(POSITION_NAME, period, line.concept),
					Item(ACCOUNT_NUMBER, period, line.account or None),
					Item(ACCOUNT_DESCRIPTION, period, line.description or None),
					amount(BALANCE, period, line.amount),
					*((Item(NOT_POSSIBLE, period, not line.account or None),) if self.not_possible else ()),
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
	if taxonomy.has(NOT_POSSIBLE):
		return _of_6_10(calculation, lines, findings)
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


def _of_6_10(calculation: Calculation, lines: list[Line], findings: list[Finding]) -> Kontennachweis:
	"""The Kontensalden of a taxonomy with the part notPossible, 6.10 and later: a line without account for each
	position that takes a Kontensaldo and that no account lands on, and the Kontensalden of each position with accounts
	adding up to it (Leitfaden 6.10, B.12.1)."""
	taxonomy = calculation.structure.taxonomy
	sums: dict[str, Decimal] = {}
	for line in calculation.lines:
		if not line.prior:
			sums[line.concept] = sums.get(line.concept, ZERO) + line.amount
	without = []
	for value in _taking_a_kontensaldo(calculation):
		position = value.position
		name = unqualified(position.concept)
		if position.concept not in sums:
			without.append(Line("", "", position.concept, value.amount))
			if position.concept != BALANCE_SHEET_NET_INCOME:
				findings.append(
					Finding(
						"EB-KONTENSALDEN-OHNE-KONTO",
						f"Auf „{position.label}“ bucht kein Konto, der Betrag stammt von Hand; die E-Bilanz meldet ihn als "
						"Kontensaldo ohne Konteninformationen.",
						f"{leitfaden(taxonomy, 'B.12.1')}; {rule(taxonomy, '170195106', 'Strukturelle Fehler')}",
						name,
						Severity.HINT,
					)
				)
		elif sums[position.concept] != value.amount:
			findings.append(
				Finding(
					"EB-KONTENSALDEN-SUMME",
					f"Die Kontensalden zu „{position.label}“ ergeben {euro(sums[position.concept])}, die Position meldet "
					f"{euro(value.amount)}; sie sollen übereinstimmen, die Korrektur gehört in die Bücher.",
					leitfaden(taxonomy, "B.12.1"),
					name,
				)
			)
	return Kontennachweis((*lines, *without), "", tuple(findings), not_possible=True)


def _taking_a_kontensaldo(calculation: Calculation) -> Iterable[Value]:
	"""The values of the current year that take a Kontensaldo: valued, in the calculation of their component, and
	without a valued position under them there (Leitfaden 6.10, B.12.1; structural error 170195106)."""
	taxonomy = calculation.structure.taxonomy
	for value in calculation.values:
		if value.period.prior or value.amount is None:
			continue
		network = taxonomy.calculation[value.position.role]
		if value.concept in network and not any(
			calculation.amount(arc.child, value.period) is not None for arc in network.children(value.concept)
		):
			yield value
