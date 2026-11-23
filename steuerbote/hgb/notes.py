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

An item is required, or required only where its fact exists (a Haftungsverhältnis, a Vorschuss); the Annual
Accounts answer each with ja, nein or entfällt. Mittelgroß and groß have a fuller Anhang, which Steuerbote does not
prepare. Every item awaits the review of a Steuerberatung. Text of §§ 264, 265, 268, 277, 284, 285, 288, 326 HGB as
read on gesetze-im-internet.de on 23 November 2026.
"""

from dataclasses import dataclass
from enum import Enum

from steuerbote.hgb.size import SizeClass


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
