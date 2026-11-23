"""What a Kleinst states under its balance sheet and what klein states in its Anhang.

Kleinst. „Kleinstkapitalgesellschaften (§ 267a) brauchen den Jahresabschluss nicht um einen Anhang zu erweitern,
wenn sie 1. die in § 268 Absatz 7 genannten Angaben, 2. die in § 285 Nummer 9 Buchstabe c genannten Angaben und
3. im Falle einer Aktiengesellschaft die in § 160 Absatz 3 Satz 2 des Aktiengesetzes genannten Angaben unter der
Bilanz angeben.“ (§ 264 Abs. 1 Satz 5 HGB) „Macht eine Kleinstkapitalgesellschaft von der Erleichterung nach
Absatz 1 Satz 5 Gebrauch, sind nach Satz 2 erforderliche zusätzliche Angaben unter der Bilanz zu machen.“
(§ 264 Abs. 2 Satz 4 HGB) The third Angabe is for an Aktiengesellschaft only, so a GmbH or UG never makes it; the
catalogue keeps it to say so. „Kleinstkapitalgesellschaften haben unter der Bilanz darzulegen, warum
gegebenenfalls das Stammkapital aufgebraucht und daher das Eigenkapital mit Null ausgewiesen ist.“ (Bundesamt für
Justiz, FAQ zu Inhalts- und Formverstößen, read on 23 November 2026) With an Eigenkapital of zero the catalogue
therefore requires that explanation.

Klein. The Anhang holds the Angaben of §§ 264, 265, 268, 277, 284 and 285 HGB that § 288 Abs. 1 and § 274a HGB
do not spare a small company (EXEMPT_FOR_KLEIN), in the order of the law. „Der Anhang braucht die die Gewinn- und
Verlustrechnung betreffenden Angaben nicht zu enthalten.“ (§ 326 Abs. 1 Satz 2 HGB) Those items are prepared for
the Feststellung but not published; whether § 285 Nr. 31 counts among them is unverified.

Every class. „In dem Jahresabschluss sind die Firma, der Sitz, das Registergericht und die Nummer, unter der die
Gesellschaft in das Handelsregister eingetragen ist, anzugeben. Befindet sich die Gesellschaft in Liquidation oder
Abwicklung, ist auch diese Tatsache anzugeben.“ (§ 264 Abs. 1a HGB, RegisterData)

Entries. The Haftungsverhältnisse are those „aus der Begebung und Übertragung von Wechseln, aus Bürgschaften,
Wechsel- und Scheckbürgschaften und aus Gewährleistungsverträgen sowie Haftungsverhältnisse aus der Bestellung von
Sicherheiten für fremde Verbindlichkeiten“ (§ 251 Satz 1 HGB), stated „jeweils gesondert unter Angabe der
gewährten Pfandrechte und sonstigen Sicherheiten“, with „Verpflichtungen betreffend die Altersversorgung und
Verpflichtungen gegenüber verbundenen oder assoziierten Unternehmen jeweils gesondert“ (§ 268 Abs. 7 HGB):
contingencies() adds the entries up kind by kind. „Haftungsverhältnisse sind auch anzugeben, wenn ihnen
gleichwertige Rückgriffsforderungen gegenüberstehen.“ (§ 251 Satz 2 HGB) The Vorschüsse and Kredite go to the
members „des Geschäftsführungsorgans, eines Aufsichtsrats, eines Beirats oder einer ähnlichen Einrichtung jeweils
für jede Personengruppe“, „unter Angabe der Zinssätze, der wesentlichen Bedingungen und der gegebenenfalls im
Geschäftsjahr zurückgezahlten oder erlassenen Beträge sowie die zugunsten dieser Personen eingegangenen
Haftungsverhältnisse“ (§ 285 Nr. 9 Buchst. c HGB): advances() adds them up group by group. Each kind names its
concept of the taxonomy 6.9 under „bs.contingLiab“.

An item is required, or required only where its fact exists (a Haftungsverhältnis, a Vorschuss); the Annual
Accounts answer each with ja, nein or entfällt, and a ja with a text or an amount (answer_problems()). Mittelgroß
and groß have a fuller Anhang, which Steuerbote does not prepare. Every item awaits the review of a
Steuerberatung, and REVIEW_ITEMS names what is open. Text of §§ 264, 265, 268, 277, 284, 285, 288, 326 HGB as
read on gesetze-im-internet.de on 23 November 2026.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, StrEnum
from types import MappingProxyType

from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import Finding, Severity


class NotesError(ValueError):
	"""Steuerbote has no catalogue for the class."""


class Requirement(Enum):
	REQUIRED = "Pflicht"
	IF_APPLICABLE = "wenn zutreffend"


class Placement(Enum):
	UNDER_BALANCE_SHEET = "unter der Bilanz"
	NOTES = "Anhang"


@dataclass(frozen=True, slots=True)
class NoteItem:
	"""An Angabe: its code for the Annual Accounts, its wording, its source, what each class owes (None: nothing),
	whether it concerns the income statement and its concept of the taxonomy 6.9 under the balance sheet."""

	code: str
	label: str
	reference: str
	kleinst: Requirement | None
	klein: Requirement | None
	income_statement: bool = False
	concept: str = ""
	when_equity_zero: bool = False


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
	"""An item as one class owes it: required or where it applies, where it stands and whether it is published."""

	item: NoteItem
	requirement: Requirement
	placement: Placement
	published: bool


_IF = Requirement.IF_APPLICABLE
_MUST = Requirement.REQUIRED

_ADDITIONAL = NoteItem(
	"ZUSAETZLICHE-ANGABEN",
	"Zusätzliche Angaben, wenn besondere Umstände dazu führen, dass der Jahresabschluss kein den tatsächlichen "
	"Verhältnissen entsprechendes Bild der Vermögens-, Finanz- und Ertragslage vermittelt",
	"§ 264 Abs. 2 Satz 2 und 4 HGB",
	_IF,
	_IF,
	concept="ntmi.other",
)
_CONTINGENCIES = NoteItem(
	"HAFTUNGSVERHAELTNISSE",
	"Haftungsverhältnisse nach § 251 HGB, jeweils gesondert unter Angabe der gewährten Pfandrechte und sonstigen "
	"Sicherheiten; Verpflichtungen betreffend die Altersversorgung und gegenüber verbundenen oder assoziierten "
	"Unternehmen gesondert vermerkt",
	"§ 264 Abs. 1 Satz 5 Nr. 1, § 268 Abs. 7, § 251 HGB",
	_IF,
	_IF,
	concept="bs.contingLiab",
)
_ADVANCES = NoteItem(
	"ORGANKREDITE",
	"Vorschüsse und Kredite an Mitglieder der Geschäftsführung, eines Aufsichtsrats, eines Beirats oder einer "
	"ähnlichen Einrichtung, je Personengruppe, mit Zinssätzen, wesentlichen Bedingungen, den im Geschäftsjahr "
	"zurückgezahlten oder erlassenen Beträgen und den zu ihren Gunsten eingegangenen Haftungsverhältnissen",
	"§ 264 Abs. 1 Satz 5 Nr. 2, § 285 Nr. 9 Buchst. c HGB",
	_IF,
	_IF,
	concept="nt.relationships.creditsToMembers",
)
_OWN_SHARES = NoteItem(
	"EIGENE-AKTIEN",
	"Angaben über Bestand und Erwerb eigener Aktien, nur für eine Aktiengesellschaft",
	"§ 264 Abs. 1 Satz 5 Nr. 3 HGB, § 160 Abs. 3 Satz 2 AktG",
	None,
	None,
	concept="nt.bsInfo.infoOnOwnSharesS",
)
_ZERO_EQUITY = NoteItem(
	"EIGENKAPITAL-NULL",
	"Darlegung, warum das Stammkapital aufgebraucht ist und das Eigenkapital daher mit null ausgewiesen wird",
	"§ 42 Abs. 1 GmbHG; Bundesamt für Justiz, FAQ zu Inhalts- und Formverstößen",
	_MUST,
	None,
	concept="ntmi.other",
	when_equity_zero=True,
)

CATALOGUE: tuple[NoteItem, ...] = (
	_ADDITIONAL,
	NoteItem(
		"DARSTELLUNGSSTETIGKEIT",
		"Abweichungen in der Form der Darstellung, insbesondere der Gliederung, gegenüber dem Vorjahr, begründet",
		"§ 265 Abs. 1 Satz 2 HGB",
		None,
		_IF,
	),
	NoteItem(
		"VORJAHRESBETRAEGE",
		"Nicht vergleichbare oder angepasste Beträge des Vorjahres, angegeben und erläutert",
		"§ 265 Abs. 2 Satz 2 und 3 HGB",
		None,
		_IF,
	),
	NoteItem(
		"MITZUGEHOERIGKEIT",
		"Mitzugehörigkeit eines Vermögensgegenstands oder einer Schuld zu anderen Posten der Bilanz",
		"§ 265 Abs. 3 HGB",
		None,
		_IF,
	),
	_CONTINGENCIES,
	NoteItem(
		"AUSSERPLANMAESSIGE-ABSCHREIBUNGEN",
		"Außerplanmäßige Abschreibungen nach § 253 Abs. 3 Satz 5 und 6 HGB",
		"§ 277 Abs. 3 Satz 1 HGB",
		None,
		_IF,
		income_statement=True,
	),
	NoteItem(
		"BEWERTUNGSMETHODEN",
		"Die auf die Posten der Bilanz und der Gewinn- und Verlustrechnung angewandten Bilanzierungs- und "
		"Bewertungsmethoden",
		"§ 284 Abs. 2 Nr. 1 HGB",
		None,
		_MUST,
	),
	NoteItem(
		"METHODENABWEICHUNGEN",
		"Abweichungen von Bilanzierungs- und Bewertungsmethoden, begründet, mit ihrem Einfluss auf die Vermögens-, "
		"Finanz- und Ertragslage",
		"§ 284 Abs. 2 Nr. 2 HGB",
		None,
		_IF,
	),
	NoteItem(
		"FREMDKAPITALZINSEN",
		"Einbeziehung von Zinsen für Fremdkapital in die Herstellungskosten",
		"§ 284 Abs. 2 Nr. 4 HGB",
		None,
		_IF,
	),
	NoteItem(
		"VERBINDLICHKEITEN",
		"Gesamtbetrag der Verbindlichkeiten mit einer Restlaufzeit von mehr als fünf Jahren und der durch "
		"Pfandrechte oder ähnliche Rechte gesicherten Verbindlichkeiten mit Art und Form der Sicherheiten",
		"§ 285 Nr. 1 HGB",
		None,
		_IF,
	),
	NoteItem(
		"FINANZIELLE-VERPFLICHTUNGEN",
		"Gesamtbetrag der sonstigen finanziellen Verpflichtungen außerhalb der Bilanz, soweit für die Beurteilung "
		"der Finanzlage von Bedeutung; Verpflichtungen betreffend die Altersversorgung und gegenüber verbundenen "
		"oder assoziierten Unternehmen gesondert",
		"§ 285 Nr. 3a HGB",
		None,
		_IF,
	),
	NoteItem(
		"ARBEITNEHMER",
		"Durchschnittliche Zahl der während des Geschäftsjahrs beschäftigten Arbeitnehmer",
		"§ 285 Nr. 7, § 288 Abs. 1 Nr. 2 HGB",
		None,
		_MUST,
	),
	_ADVANCES,
	NoteItem(
		"FIRMENWERT",
		"Erläuterung des Zeitraums, über den ein entgeltlich erworbener Geschäfts- oder Firmenwert abgeschrieben wird",
		"§ 285 Nr. 13 HGB",
		None,
		_IF,
	),
	NoteItem(
		"MUTTERUNTERNEHMEN",
		"Name und Sitz des Mutterunternehmens, das den Konzernabschluss für den kleinsten Kreis von Unternehmen "
		"aufstellt",
		"§ 285 Nr. 14a, § 288 Abs. 1 Nr. 3 HGB",
		None,
		_IF,
	),
	NoteItem(
		"ZEITWERT",
		"Grundlegende Annahmen der Bewertung von Finanzinstrumenten zum beizulegenden Zeitwert, Umfang und Art "
		"jeder Kategorie derivativer Finanzinstrumente",
		"§ 285 Nr. 20 HGB",
		None,
		_IF,
	),
	NoteItem(
		"BEWERTUNGSEINHEITEN",
		"Bewertungseinheiten nach § 254 HGB: einbezogene Beträge, abgesicherte Risiken und erwartete Transaktionen",
		"§ 285 Nr. 23 HGB",
		None,
		_IF,
	),
	NoteItem(
		"VERRECHNUNG",
		"Verrechnung von Vermögensgegenständen und Schulden nach § 246 Abs. 2 Satz 2 HGB: Anschaffungskosten, "
		"beizulegender Zeitwert, Erfüllungsbetrag und verrechnete Aufwendungen und Erträge",
		"§ 285 Nr. 25 HGB",
		None,
		_IF,
	),
	NoteItem(
		"AUSSERGEWOEHNLICHES",
		"Betrag und Art der Erträge und Aufwendungen von außergewöhnlicher Größenordnung oder außergewöhnlicher "
		"Bedeutung",
		"§ 285 Nr. 31 HGB",
		None,
		_IF,
		income_statement=True,
	),
	_OWN_SHARES,
	_ZERO_EQUITY,
)

_KLEINST_ORDER = (_CONTINGENCIES, _ADVANCES, _ADDITIONAL, _ZERO_EQUITY)

EXEMPT_FOR_KLEIN: tuple[str, ...] = (
	"§ 264c Abs. 2 Satz 9 HGB",
	"§ 265 Abs. 4 Satz 2 HGB",
	"§ 284 Abs. 2 Nr. 3 HGB",
	"§ 284 Abs. 3 HGB",
	"§ 285 Nr. 2, 3, 4, 8, 9 Buchst. a und b, Nr. 10 bis 12, 14, 15, 15a, 17 bis 19, 21, 22, 24, 26 bis 30a, "
	"32 bis 34 HGB",
	"die Trennung nach Gruppen bei § 285 Nr. 7 HGB",
	"der Ort des Konzernabschlusses bei § 285 Nr. 14a HGB",
	"§ 268 Abs. 4 Satz 2, Abs. 5 Satz 3 und Abs. 6 HGB",
	"§ 274 HGB",
)
"""What small companies need not state: § 288 Abs. 1 Nr. 1 to 3 and § 274a HGB."""


def catalogue(size_class: SizeClass, *, equity_zero: bool = False) -> tuple[CatalogueEntry, ...]:
	"""The Angaben ``size_class`` owes: Kleinst under its balance sheet, klein in its Anhang; ``equity_zero`` adds
	the explanation an Eigenkapital of zero needs."""
	match size_class:
		case SizeClass.KLEINST:
			return tuple(
				CatalogueEntry(item, item.kleinst, Placement.UNDER_BALANCE_SHEET, published=True)
				for item in _KLEINST_ORDER
				if item.kleinst is not None and (equity_zero or not item.when_equity_zero)
			)
		case SizeClass.KLEIN:
			return tuple(
				CatalogueEntry(item, item.klein, Placement.NOTES, published=not item.income_statement)
				for item in CATALOGUE
				if item.klein is not None
			)
		case _:
			raise NotesError(
				f"Steuerbote prepares the Anhang of Kleinst and klein only, not of a {size_class.value}"
			)


class Answer(Enum):
	YES = "ja"
	NO = "nein"
	NOT_APPLICABLE = "entfällt"


@dataclass(frozen=True, slots=True)
class NoteAnswer:
	"""The answer of the Annual Accounts to an item, as a row of the table Angaben holds it."""

	code: str
	answer: Answer
	text: str = ""
	amount: Decimal | None = None

	def __post_init__(self) -> None:
		if self.amount is not None and not isinstance(self.amount, Decimal):
			raise TypeError(f"amount must be Decimal, not {type(self.amount).__name__}")


class NoteCode(StrEnum):
	UNANSWERED = "JA-ANGABE-OFFEN"
	DENIED = "JA-ANGABE-PFLICHT"
	EMPTY = "JA-ANGABE-LEER"
	UNKNOWN = "JA-ANGABE-UNBEKANNT"
	TWICE = "JA-ANGABE-DOPPELT"
	NEGATIVE = "JA-ANGABE-NEGATIV"
	NO_RATE = "JA-ORGANKREDIT-ZINSSATZ"
	NO_CONDITIONS = "JA-ORGANKREDIT-BEDINGUNGEN"
	REGISTER = "JA-REGISTERANGABEN"


def answer_problems(entries: Iterable[CatalogueEntry], answers: Iterable[NoteAnswer]) -> tuple[Finding, ...]:
	"""What the answers leave open: an item without an answer, a required one without ja, a ja without text or
	amount, an answer to an item the class does not owe and one answered twice; each holds the Jahresabschluss
	back."""
	entries, answers = tuple(entries), tuple(answers)
	by_code = {entry.item.code: entry for entry in entries}
	counts = Counter(answer.code for answer in answers)
	findings: list[Finding] = []
	for entry in entries:
		item = entry.item
		if not counts[item.code]:
			findings.append(
				_finding(NoteCode.UNANSWERED, f"Die Angabe „{item.label}“ ist nicht beantwortet.", item)
			)
	seen: set[str] = set()
	for answer in answers:
		entry = by_code.get(answer.code)
		if entry is None:
			findings.append(
				Finding(
					NoteCode.UNKNOWN,
					Severity.ERROR,
					f"Die Angabe {answer.code} gehört nicht zu den Angaben dieses Jahresabschlusses.",
					"§ 264 Abs. 1 Satz 5, §§ 284 bis 288 HGB",
					answer.code,
				)
			)
			continue
		item = entry.item
		if answer.code in seen:
			findings.append(
				_finding(NoteCode.TWICE, f"Die Angabe „{item.label}“ ist mehrfach beantwortet.", item)
			)
			continue
		seen.add(answer.code)
		if entry.requirement is Requirement.REQUIRED and answer.answer is not Answer.YES:
			findings.append(
				_finding(
					NoteCode.DENIED,
					f"Die Angabe „{item.label}“ ist Pflicht; „{answer.answer.value}“ genügt nicht.",
					item,
				)
			)
		elif answer.answer is Answer.YES and not answer.text.strip() and answer.amount is None:
			findings.append(
				_finding(
					NoteCode.EMPTY,
					f"Die Angabe „{item.label}“ trifft zu, hat aber weder Text noch Betrag.",
					item,
				)
			)
	return tuple(findings)


def _finding(code: NoteCode, text: str, item: NoteItem) -> Finding:
	return Finding(code, Severity.ERROR, text, item.reference, item.code)


_ZERO = Decimal("0")
_CONTINGENCIES_REFERENCE = "§ 268 Abs. 7, § 251 HGB"
_ADVANCES_REFERENCE = "§ 285 Nr. 9 Buchst. c HGB"


class Contingency(Enum):
	"""The kinds of Haftungsverhältnisse of § 251 HGB in its order, each with its concept of the taxonomy 6.9."""

	BILLS = "Verbindlichkeiten aus der Begebung und Übertragung von Wechseln"
	GUARANTEES = "Verbindlichkeiten aus Bürgschaften"
	BILL_AND_CHEQUE_GUARANTEES = "Verbindlichkeiten aus Wechsel- und Scheckbürgschaften"
	WARRANTIES = "Verbindlichkeiten aus Gewährleistungsverträgen"
	COLLATERAL = "Haftungsverhältnisse aus der Bestellung von Sicherheiten für fremde Verbindlichkeiten"

	@property
	def concept(self) -> str:
		return _CONTINGENCY_CONCEPTS[self]

	@property
	def pensions_concept(self) -> str:
		"""„davon betreffend Altersversorgung“."""
		return f"{self.concept}.pension"

	@property
	def group_concept(self) -> str:
		"""„davon gegenüber verbundenen/assoziierten Unternehmen“."""
		return f"{self.concept}.assoc"


_CONTINGENCY_CONCEPTS = MappingProxyType(
	{
		Contingency.BILLS: "bs.contingLiab.notes",
		Contingency.GUARANTEES: "bs.contingLiab.guarantees",
		Contingency.BILL_AND_CHEQUE_GUARANTEES: "bs.contingLiab.guaranteesNotes",
		Contingency.WARRANTIES: "bs.contingLiab.warranty",
		Contingency.COLLATERAL: "bs.contingLiab.collateralisation",
	}
)


@dataclass(frozen=True, slots=True)
class ContingentLiability:
	"""One Haftungsverhältnis: its kind and amount, the securities granted for it and whether it concerns the
	Altersversorgung or verbundene or assoziierte Unternehmen."""

	kind: Contingency
	amount: Decimal
	securities: str = ""
	pensions: bool = False
	group: bool = False

	def __post_init__(self) -> None:
		_require_decimal("amount", self.amount)


@dataclass(frozen=True, slots=True)
class ContingencyTotal:
	kind: Contingency
	amount: Decimal
	pensions: Decimal
	group: Decimal
	securities: tuple[str, ...]


def contingencies(entries: Iterable[ContingentLiability]) -> tuple[ContingencyTotal, ...]:
	"""The Haftungsverhältnisse kind by kind in the order of § 251 HGB, each kind with entries once."""
	entries = tuple(entries)
	totals = []
	for kind in Contingency:
		of_kind = [entry for entry in entries if entry.kind is kind]
		if of_kind:
			totals.append(
				ContingencyTotal(
					kind,
					sum((entry.amount for entry in of_kind), _ZERO),
					sum((entry.amount for entry in of_kind if entry.pensions), _ZERO),
					sum((entry.amount for entry in of_kind if entry.group), _ZERO),
					tuple(dict.fromkeys(entry.securities for entry in of_kind if entry.securities.strip())),
				)
			)
	return tuple(totals)


class OfficerGroup(Enum):
	MANAGEMENT = "Mitglieder des Geschäftsführungsorgans"
	SUPERVISORY_BOARD = "Mitglieder des Aufsichtsrats"
	ADVISORY_BOARD = "Mitglieder des Beirats"
	SIMILAR_BODY = "Mitglieder einer ähnlichen Einrichtung"


class AdvanceKind(Enum):
	ADVANCE = "Vorschuss"
	LOAN = "Kredit"


@dataclass(frozen=True, slots=True)
class OfficerAdvance:
	"""A Vorschuss or Kredit to a member of an organ: the group, the amount granted, the interest rate in percent a
	year (zero when it bears none), the essential conditions, what was repaid or waived in the fiscal year and the
	Haftungsverhältnisse entered into for the member."""

	group: OfficerGroup
	kind: AdvanceKind
	amount: Decimal
	interest_rate: Decimal | None
	conditions: str
	repaid: Decimal = _ZERO
	waived: Decimal = _ZERO
	guarantees: str = ""

	def __post_init__(self) -> None:
		for name in ("amount", "repaid", "waived"):
			_require_decimal(name, getattr(self, name))
		if self.interest_rate is not None:
			_require_decimal("interest_rate", self.interest_rate)


@dataclass(frozen=True, slots=True)
class AdvanceTotal:
	group: OfficerGroup
	amount: Decimal
	repaid: Decimal
	waived: Decimal
	interest_rates: tuple[Decimal | None, ...]
	conditions: tuple[str, ...]
	guarantees: tuple[str, ...]


def advances(entries: Iterable[OfficerAdvance]) -> tuple[AdvanceTotal, ...]:
	"""The Vorschüsse and Kredite group by group in the order of § 285 Nr. 9 HGB, each group with entries once."""
	entries = tuple(entries)
	totals = []
	for group in OfficerGroup:
		of_group = [entry for entry in entries if entry.group is group]
		if of_group:
			totals.append(
				AdvanceTotal(
					group,
					sum((entry.amount for entry in of_group), _ZERO),
					sum((entry.repaid for entry in of_group), _ZERO),
					sum((entry.waived for entry in of_group), _ZERO),
					tuple(entry.interest_rate for entry in of_group),
					tuple(entry.conditions for entry in of_group),
					tuple(entry.guarantees for entry in of_group if entry.guarantees.strip()),
				)
			)
	return tuple(totals)


def entry_problems(
	contingent: Iterable[ContingentLiability], officer_advances: Iterable[OfficerAdvance]
) -> tuple[Finding, ...]:
	"""What the entries leave open: a negative amount, and an advance without its interest rate or its essential
	conditions."""
	findings: list[Finding] = []
	for liability in contingent:
		if liability.amount < 0:
			findings.append(
				_entry_finding(
					NoteCode.NEGATIVE,
					f"„{liability.kind.value}“ hat einen negativen Betrag.",
					_CONTINGENCIES_REFERENCE,
				)
			)
	for advance in officer_advances:
		label = f"{advance.kind.value} an {advance.group.value}"
		numbers = (advance.amount, advance.repaid, advance.waived, advance.interest_rate or _ZERO)
		if any(number < 0 for number in numbers):
			findings.append(
				_entry_finding(
					NoteCode.NEGATIVE, f"Der {label} hat einen negativen Betrag.", _ADVANCES_REFERENCE
				)
			)
		if advance.interest_rate is None:
			findings.append(
				_entry_finding(
					NoteCode.NO_RATE,
					f"Für den {label} fehlt der Zinssatz, null für einen zinslosen.",
					_ADVANCES_REFERENCE,
				)
			)
		if not advance.conditions.strip():
			findings.append(
				_entry_finding(
					NoteCode.NO_CONDITIONS,
					f"Für den {label} fehlen die wesentlichen Bedingungen.",
					_ADVANCES_REFERENCE,
				)
			)
	return tuple(findings)


def _entry_finding(code: NoteCode, text: str, reference: str) -> Finding:
	return Finding(code, Severity.ERROR, text, reference)


def _require_decimal(name: str, value: object) -> None:
	if not isinstance(value, Decimal):
		raise TypeError(f"{name} must be Decimal, not {type(value).__name__}")


_REGISTER_FIELDS = MappingProxyType(
	{
		"firma": ("Firma", "notesBelowBalanceSheet.geninfo.company"),
		"sitz": ("Sitz", "notesBelowBalanceSheet.geninfo.location"),
		"registergericht": ("Registergericht", "notesBelowBalanceSheet.geninfo.court"),
		"registernummer": ("Registernummer", "notesBelowBalanceSheet.geninfo.number"),
		"in_liquidation": (
			"in Liquidation oder Abwicklung",
			"notesBelowBalanceSheet.geninfo.liquidationOrWindingUp",
		),
	}
)


@dataclass(frozen=True, slots=True)
class RegisterData:
	"""What § 264 Abs. 1a HGB wants named in the Jahresabschluss; the Annual Filing Settings hold it."""

	firma: str
	sitz: str
	registergericht: str
	registernummer: str
	in_liquidation: bool = False

	@staticmethod
	def concepts() -> dict[str, str]:
		"""The concept of the taxonomy 6.9 of each field."""
		return {field: concept for field, (_, concept) in _REGISTER_FIELDS.items()}


def register_problems(data: RegisterData) -> tuple[Finding, ...]:
	"""One error naming each field of § 264 Abs. 1a HGB that is empty."""
	missing = [
		label
		for field, (label, _) in _REGISTER_FIELDS.items()
		if field != "in_liquidation" and not getattr(data, field).strip()
	]
	if not missing:
		return ()
	return (
		Finding(
			NoteCode.REGISTER,
			Severity.ERROR,
			f"Im Jahresabschluss fehlen {', '.join(missing)} der Gesellschaft.",
			"§ 264 Abs. 1a HGB",
		),
	)


@dataclass(frozen=True, slots=True)
class ReviewItem:
	code: str
	text: str
	reference: str


REVIEW_ITEMS: tuple[ReviewItem, ...] = (
	ReviewItem(
		"KLEINST-EIGENKAPITAL",
		"Die Bilanz einer Kleinstkapitalgesellschaft zeigt das Eigenkapital nur als „A. Eigenkapital“. Ob § 42 Abs. 1 "
		"GmbHG, nach dem das Stammkapital als gezeichnetes Kapital auszuweisen ist, den Ausweis auch hier verlangt, "
		"klärt die Steuerberatung.",
		"§ 266 Abs. 1 Satz 4 HGB, § 42 Abs. 1 GmbHG",
	),
	ReviewItem(
		"AUSSERGEWOEHNLICHES",
		"Ob die Angabe nach § 285 Nr. 31 HGB die Gewinn- und Verlustrechnung betrifft und eine kleine "
		"Kapitalgesellschaft sie deshalb nicht offenlegt, ist ungeprüft; die Steuerberatung klärt es.",
		"§ 285 Nr. 31, § 326 Abs. 1 Satz 2 HGB",
	),
	ReviewItem(
		"KATALOG",
		"Der Katalog der Angaben folgt dem Gesetzestext; die Steuerberatung prüft ihn vor dem ersten "
		"Jahresabschluss.",
		"§ 264 Abs. 1 Satz 5, §§ 284 bis 288 HGB",
	),
)
