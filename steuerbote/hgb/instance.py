"""The XBRL instance of the Offenlegung: the festgestellter Jahresabschluss of a Kleinstkapitalgesellschaft or a small
GmbH or UG for the Unternehmensregister, in the profile DISCLOSURE of steuerbote/xbrl/profiles.py.

The register takes the Jahresabschluss „im strukturierten Format Extensible Markup Language (XML)“ (§ 11 Abs. 2 Satz 1
Nr. 4 URV), as XBRL on the HGB-Taxonomie in the views „de-gaap-ci-2025-04-01 ... Einzelabschluss“ and, for a
Kleinstkapitalgesellschaft, „de-gaap-ci-2025-04-01-microbilg ... Einzelabschluss MicroBilG“, each with
de-gcd-2025-04-01 („Arbeitshilfe für die Einreichung von Jahresabschlüssen/Finanzberichten im XBRL-Format“ of the
Unternehmensregister, Stand September 2025). The version is the one of the fiscal year (steuerbote/xbrl/versions.py),
6.9 for 2026, which the register has taken since 15 October 2025.

build(statement, size, notes, disclosure, gcd) gives the Instance: the facts of steuerbote/xbrl/facts.py, the view
they reference, the company, the periods, the concepts the class publishes and what holds the file back. It needs no
taxonomy, so the Annual Accounts can build it and show its findings before anyone installs one. write(instance,
taxonomy) writes it through the writer of steuerbote/xbrl/writer.py after the checks of the profile.

Balance sheet. The statement of steuerbote/hgb/statement.py in full euros (in_full_euros(); that the register wants
full euros is unverified, so the amounts carry decimals="0"): the positions the class shows, „nur die in den Absätzen
2 und 3 mit Buchstaben bezeichneten Posten“ for a Kleinst (§ 266 Abs. 1 Satz 4 HGB) and those „mit Buchstaben und
römischen Zahlen“ for klein (Satz 3), with the totals of both sides, and nothing below them, since the register shows
„lediglich die Positionen, zu denen Werte berichtet werden, sowie deren übergeordnete Positionen“ (Arbeitshilfe).
Each Posten stands at the Abschlussstichtag and at that of the previous year: „In der Bilanz ... ist zu jedem Posten
der entsprechende Betrag des vorhergehenden Geschäftsjahrs anzugeben.“ (§ 265 Abs. 2 Satz 1 HGB) A Posten without an
amount in either year is left out (§ 265 Abs. 8 HGB; ``Line.shown``), unless a Posten under it is reported: „Ist eine
Unterposition werthaltig angegeben, so sind auch ihre Oberpositionen werthaltig zu berichten“ (Technischer Leitfaden
zur HGB-Taxonomie 6.9, B.14.10). The income statement is withheld (§ 326 Abs. 1 Satz 1 and Abs. 2 Satz 1 HGB).

Vermerke. A Vermerk the class notes at a position (steuerbote/hgb/schemes.py) is its „davon“ concept, which the
taxonomy presents under the position whose balances it covers, its ``scope``. Where the class shows that position,
the Vermerk is a fact at both closing dates. A Kleinst notes the remaining terms and the shareholders of its
receivables at „B. Umlaufvermögen“ and its Ausleihungen an Gesellschafter at „A. Anlagevermögen“, but the taxonomy
has their concepts only under „B. II.“ and „A. III.“, which a Kleinst does not show: reported, they would call for
those positions. Those Vermerke stand as text under the balance sheet instead, each with its position, its wording
and its amounts. The uncalled contributions and own shares are „offen abzusetzen“ from the Gezeichnetes Kapital
(§ 272 Abs. 1 Satz 2 und Abs. 1a Satz 1 HGB); the taxonomy takes them as positive amounts it subtracts from the
Gezeichnetes Kapital of a Kapitalgesellschaft (weight -1 in its calculation linkbase), so the instance reports the
Nennbetrag as bs.eqLiab.equity.subscribed.corp beside them, and the Posten keeps what remains.

Angaben. A Kleinst states its Angaben „unter der Bilanz“ (§ 264 Abs. 1 Satz 5 HGB), in the role
notesBelowBalanceSheet, and klein its Anhang (§ 326 Abs. 1 Satz 1 HGB) in the role notes. SLOTS names for each Angabe
the class publishes the concept of its text and of its amount; „Der Anhang braucht die die Gewinn- und
Verlustrechnung betreffenden Angaben nicht zu enthalten.“ (§ 326 Abs. 1 Satz 2 HGB) An Angabe answered „ja“ states
its text, and the amount of its answer where the taxonomy has a position for it, or else after the text. Where two
Angaben share a position, their texts follow one another in the order of the catalogue of steuerbote/hgb/notes.py.

- Firma, Sitz, Registergericht and Registernummer, and the Liquidation where it applies (§ 264 Abs. 1a HGB), stand
  in both classes as notesBelowBalanceSheet.geninfo.* (RegisterData.concepts()).
- The Haftungsverhältnisse stand kind by kind in full euros at the Abschlussstichtag under bs.contingLiab, with what
  concerns the Altersversorgung and the verbundene or assoziierte Unternehmen „jeweils gesondert“, and the
  „gewährten Pfandrechte und sonstigen Sicherheiten“ in the text (§ 268 Abs. 7 HGB; contingencies()). Their amounts
  of the previous year are not written: whether § 265 Abs. 2 HGB asks for them is unverified.
- The Vorschüsse and Kredite to the members of an organ stand group by group as text, „unter Angabe der Zinssätze,
  der wesentlichen Bedingungen und der gegebenenfalls im Geschäftsjahr zurückgezahlten oder erlassenen Beträge sowie
  die zugunsten dieser Personen eingegangenen Haftungsverhältnisse“ (§ 285 Nr. 9 Buchst. c HGB; advances()).
- The average number of employees of klein (§ 285 Nr. 7 HGB) is a number, nt.employeesAveragePeriod.

The places in the Anhang of klein follow the labels of the taxonomy 6.9 and await the review of a Steuerberatung, as
the catalogue does; the fair values of § 285 Nr. 20 HGB, for which the taxonomy has no position of their own, take
its heading nt.genInfo.

Signatures. „Der Jahresabschluß ist vom Kaufmann unter Angabe des Datums zu unterzeichnen.“ (§ 245 Satz 1 HGB), and
„Nach § 245 HGB ist beim Jahresabschluss die Angabe aller Unterzeichner sowie des Datums erforderlich.“
(Publikations-Plattform, Fragen und Antworten, „Übermittlung von Jahresabschlüssen“) Klein names them in its Anhang
as „Unterschrift der Geschäftsleitung“ (nt.directorsSign), with place and day once where all signatures share them
and with each person otherwise. A Kleinst has no Anhang, so its signatures close the text under its balance sheet,
each with place, day and „gez.“.

Texts. Every text keeps to the characters the writer takes (steuerbote/xbrl/writer.py): the common typographic ones
are replaced line by line (steuerbote/elster/charset.py), and one it cannot replace is dropped with a finding.

GCD. The master data of the report, „ein Modul mit allgemeinen Informationen über das Dokument, den Bericht und das
berichtende Unternehmen“ (Arbeitshilfe). Which of its fields the register needs is unverified: its documentation for
software, „Informationen für Ersteller von Jahresabschlüssen/Finanzberichten mit XBRL-Kenntnissen und für
Softwareanbieter“, needs an activation. So the instance states every field of de-gcd-2025-04-01 that a festgestellter
Jahresabschluss of a small GmbH fills, each value as its label in the taxonomy names it:

- the report: „Jahresabschluss“ (reportType JA), „endgültig“ (reportStatus E), the day of the Feststellung, which
  „ist anzugeben“ (§ 328 Abs. 1a Satz 1 HGB; dateofapproval), the status of the report (revisionStatus, erstmalig
  unless the master data name another for a changed Jahresabschluss, § 325 Abs. 1b HGB), the parts transmitted
  (reportElement: the Bilanz and the „Angaben unterhalb der Bilanz“, for klein the „andere Anhangangaben“, § 326
  Abs. 1 Satz 1 und Abs. 2 Satz 1 HGB), where the Angaben of § 264 Abs. 1a HGB, those of a Kleinst and the
  Haftungsverhältnisse stand (allocation), „Jahresabschluss“ (statementType E), whether the balance sheet shows a
  Bilanzgewinn (§ 268 Abs. 1 Satz 2 HGB), „deutsches Handelsrecht“ (HGBM), the „Kerntaxonomie“ (K), the format of the
  income statement it withholds (GKV or UKV), „nicht konsolidiert/ Einzelabschluss“ (EA), the fiscal year and the
  previous one, and no audit: „Der Jahresabschluß und der Lagebericht von Kapitalgesellschaften, die nicht kleine im
  Sinne des § 267 Abs. 1 sind, sind durch einen Abschlußprüfer zu prüfen.“ (§ 316 Abs. 1 Satz 1 HGB);
- the company: its firm, „Gesellschaft mit beschränkter Haftung“ also for an UG, since the taxonomy documents
  legalStatus.UG as „Nicht vorgesehen für Bundesanzeiger, Erfassung unter "Gesellschaft mit beschränkter Haftung"“,
  the day of its founding, its Handelsregister with court and number (§ 264 Abs. 1a HGB), its size class
  (SizeClass.gcd) and the scheme its balance sheet follows (reportedSizeClassBs), its seat with the address, „in
  Liquidation“ where § 264 Abs. 1a Satz 2 HGB asks for it, and that it is not kapitalmarktorientiert, „Eine
  Kapitalgesellschaft im Sinn des § 264d gilt stets als große.“ (§ 267 Abs. 3 Satz 2 HGB);
- the day the file is written, where the master data name it.

The GCD leaves out the persons who prepared the file (genInfo.doc.author) and the shareholders: neither is part of
the Jahresabschluss, and the register publishes what it receives.

The company. Every context names it by Registergericht and Registernummer in the scheme REGISTER_SCHEME: the register
keeps companies by them (§ 3 Abs. 2 URV), and which identifier it expects in a context is unverified.

Findings. What holds the Jahresabschluss back holds its file back: the errors of the statement of both years, the
answers and entries of the Angaben and the register data (steuerbote/hgb/notes.py), a Feststellung within the fiscal
year (steuerbote/hgb/disclosure.py), and what the file itself cannot carry (Code).

This module is pure Python and never imports Frappe.
"""

import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from steuerbote.elster.charset import CharsetError, describe, transliterate
from steuerbote.hgb.disclosure import Mode, Publication, Signature, adoption_problems
from steuerbote.hgb.notes import (
	AdvanceTotal,
	Answer,
	CatalogueEntry,
	Contingency,
	ContingentLiability,
	NoteAnswer,
	OfficerAdvance,
	RegisterData,
	advances,
	answer_problems,
	catalogue,
	contingencies,
	entry_problems,
	register_problems,
)
from steuerbote.hgb.schemes import BalanceSheetScheme, Position, VermerkKind
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import (
	BILANZGEWINN,
	AnnualStatement,
	BalanceSheet,
	Finding,
	Line,
	Severity,
	VermerkLine,
	in_full_euros,
)
from steuerbote.jahresmeldung.corrections import RevisionStatus, revision_status_concept
from steuerbote.ustva.period import day_label
from steuerbote.ustva.rounding import apportion_full_euros, half_up_euro
from steuerbote.xbrl.facts import Entity, Fact, Item, Period, Periods, Tuple, amount, choice
from steuerbote.xbrl.profiles import DISCLOSURE
from steuerbote.xbrl.taxonomy import View
from steuerbote.xbrl.versions import Version, for_fiscal_year

REGISTER_SCHEME = "http://www.handelsregister.de"
"""The scheme of the identifier of the company: its Registergericht and Registernummer."""
GAAP = "de-gaap-ci:"
GCD = "de-gcd:genInfo."
WJ = Period.WIRTSCHAFTSJAHR
SUBSCRIBED = "bs.eqLiab.equity.subscribed"
NENNBETRAG = "bs.eqLiab.equity.subscribed.corp"
"""„Gezeichnetes Kapital ..., gezeichnetes Kapital (Kapitalgesellschaften)“, from which the deductions are offset."""
CONTINGENCIES = "bs.contingLiab"
OTHER_BELOW = "ntmi.other"
"""„Sonstige Angaben unter der Bilanz nach MicroBilG“."""
SIGNATURE = "nt.directorsSign"
"""„Unterschrift der Geschäftsleitung“."""
_SIGNATURE_PARTS = ("place", "date", "type", "type.name", "person", "person.name", "person.otherattributes")
_DEDUCTIONS = frozenset({VermerkKind.UNCALLED_CAPITAL, VermerkKind.OWN_SHARES})
_PREPARED = (SizeClass.KLEINST, SizeClass.KLEIN)
_COMPONENTS = MappingProxyType({SizeClass.KLEINST: ("B", "H"), SizeClass.KLEIN: ("B", "H", "SA")})
"""The Berichtsbestandteile: Bilanz, „Angaben unterhalb der Bilanz“ and „andere Anhangangaben“."""
_REPORTED_SCHEMES = MappingProxyType({SizeClass.KLEINST: "Kst", SizeClass.KLEIN: "K"})
_LIQUIDATION = "Die Gesellschaft befindet sich in Liquidation."
_ORGAN = "Geschäftsführung"
_ZERO = Decimal("0")
_CHARACTERS_REFERENCE = "Einheitliche Elster-Datenschnittstelle XML, Kap. 2.2; ERiC E-Bilanz-Dokumentation für HGB-Taxonomie 6.9, Kap. 3.16"


class InstanceError(ValueError):
	"""The inputs do not make an Offenlegung Steuerbote writes."""


class Code(StrEnum):
	"""What the file cannot carry; the other codes of the findings are those of steuerbote/hgb/statement.py, notes.py
	and disclosure.py."""

	CHARACTERS = "JA-XBRL-ZEICHEN"
	NUMBER = "JA-XBRL-ARBEITNEHMER"
	ENTRIES = "JA-XBRL-EINTRAEGE"
	AMOUNT = "JA-XBRL-BETRAG"


@dataclass(frozen=True, slots=True)
class Slot:
	"""Where an Angabe of the catalogue stands in the taxonomy 6.9: the concept of its text and that of its amount."""

	code: str
	text: str = ""
	amount: str = ""


SLOTS: MappingProxyType[SizeClass, tuple[Slot, ...]] = MappingProxyType(
	{
		SizeClass.KLEINST: (
			Slot("HAFTUNGSVERHAELTNISSE", OTHER_BELOW, CONTINGENCIES),
			Slot("ORGANKREDITE", "nt.relationships.creditsToMembers"),
			Slot("ZUSAETZLICHE-ANGABEN", OTHER_BELOW),
			Slot("EIGENKAPITAL-NULL", OTHER_BELOW),
		),
		SizeClass.KLEIN: (
			Slot(
				"ZUSAETZLICHE-ANGABEN",
				"nt.additionalNotes.additDisclosuresIfFinStatmntDoesNotPresentTrueAndFairView",
			),
			Slot("DARSTELLUNGSSTETIGKEIT", "nt.genInfo.changeInPresentation"),
			Slot("VORJAHRESBETRAEGE", "nt.genInfo.lackOfComparabilityToPriorStatements"),
			Slot("MITZUGEHOERIGKEIT", "nt.genInfo.asetsOrLiabilitiesUnderServeralHeadings"),
			Slot("HAFTUNGSVERHAELTNISSE", "nt.otherInfo.contingLiab", CONTINGENCIES),
			Slot("BEWERTUNGSMETHODEN", "nt.genInfo.measurement"),
			Slot("METHODENABWEICHUNGEN", "nt.genInfo.changeInMeasuremt"),
			Slot("FREMDKAPITALZINSEN", "nt.genInfo.interestInManufCost"),
			Slot("VERBINDLICHKEITEN", "nt.bsInfo.totalAmountLiabOver5Years"),
			Slot("FINANZIELLE-VERPFLICHTUNGEN", "nt.otherInfo.contingLiab"),
			Slot("ARBEITNEHMER", amount="nt.employeesAveragePeriod"),
			Slot("ORGANKREDITE", "nt.relationships.creditsToMembers"),
			Slot("FIRMENWERT", "nt.isInfo.reasonsGoodwillAmortisationsLonger5Years"),
			Slot("MUTTERUNTERNEHMEN", "nt.assocComp.parentsNameSmall"),
			Slot("ZEITWERT", "nt.genInfo"),
			Slot("BEWERTUNGSEINHEITEN", "nt.genInfo.DisclosuresMasurementUnits"),
			Slot("VERRECHNUNG", "nt.genInfo.DisclosuresOffsetAssets"),
		),
	}
)
"""The place of each Angabe a class publishes, in the order of the catalogue: under the balance sheet of a Kleinst
the concepts the catalogue names, in the Anhang of klein those whose labels in the taxonomy 6.9 say what the law
asks."""


@dataclass(frozen=True, slots=True)
class Address:
	"""The address of the company, as the Annual Filing Settings hold it."""

	street: str
	house_number: str
	postal_code: str
	city: str
	country: str = "Deutschland"


@dataclass(frozen=True, slots=True)
class MasterData:
	"""What the GCD of the Offenlegung states besides the statement and the Angaben."""

	periods: Periods
	adopted_on: date
	"""The day of the Feststellung, „Das Datum der Feststellung oder der Billigung ... ist anzugeben.“ (§ 328 Abs. 1a
    Satz 1 HGB)"""
	address: Address | None = None
	founded_on: date | None = None
	generated_on: date | None = None
	"""The day the file is written; None leaves it out, so that the same Jahresabschluss gives the same bytes."""
	revision: RevisionStatus = RevisionStatus.FIRST


@dataclass(frozen=True, slots=True)
class Notes:
	"""The Angaben of the Jahresabschluss: the register data, the answers to the catalogue of steuerbote/hgb/notes.py,
	the Haftungsverhältnisse and Vorschüsse behind two of them, and the signatures."""

	register: RegisterData
	answers: tuple[NoteAnswer, ...] = ()
	contingent: tuple[ContingentLiability, ...] = ()
	advances: tuple[OfficerAdvance, ...] = ()
	signatures: tuple[Signature, ...] = ()


@dataclass(frozen=True, slots=True)
class Instance:
	"""The Offenlegung of one Jahresabschluss: its facts for the view of its class, and what holds it back."""

	size_class: SizeClass
	mode: Mode
	version: Version
	view: View
	entity: Entity
	periods: Periods
	facts: tuple[Fact, ...]
	published: tuple[str, ...]
	"""The concepts of the GAAP module the class publishes, for the check of the profile."""
	findings: tuple[Finding, ...] = ()


def build(
	statement: AnnualStatement, size: SizeClass, notes: Notes, disclosure: Publication, gcd: MasterData
) -> Instance:
	"""The instance of the Offenlegung of the Jahresabschluss ``statement``, as steuerbote/hgb/statement.py built it
	for the class ``size``, with the Angaben ``notes``, the Publication of steuerbote/hgb/disclosure.py and the master
	data ``gcd``."""
	_require_fit(statement, size, disclosure, gcd.periods)
	entity = _entity(notes.register)
	full = in_full_euros(statement)
	sheet = full.balance_sheet
	texts = _Texts()
	entries = catalogue(size, equity_zero=sheet.equity == 0)
	angaben = _Angaben(sheet, size, notes, entries, texts)
	stated = tuple(angaben.facts())
	facts = (
		*_master_data(full, size, notes.register, gcd, texts, contingencies=angaben.contingencies_stated),
		*_balance_sheet(sheet),
		*stated,
	)
	findings = (
		*(finding for finding in statement.findings if finding.blocking),
		*answer_problems(entries, notes.answers),
		*entry_problems(notes.contingent, notes.advances),
		*register_problems(notes.register),
		*adoption_problems(gcd.periods.fiscal_year_end, gcd.adopted_on, (), ()),
		*angaben.findings,
		*texts.findings.values(),
	)
	return Instance(
		size,
		disclosure.mode,
		for_fiscal_year(gcd.periods.fiscal_year_begin, gcd.periods.fiscal_year_end),
		DISCLOSURE.view(kleinst=size is SizeClass.KLEINST),
		entity,
		gcd.periods,
		facts,
		tuple(dict.fromkeys(_published(sheet.scheme, size))),
		findings,
	)


def _require_fit(
	statement: AnnualStatement, size: SizeClass, disclosure: Publication, periods: Periods
) -> None:
	sheet = statement.balance_sheet
	if size not in _PREPARED:
		raise InstanceError(
			f"Steuerbote writes the Offenlegung of Kleinst and klein only, not of a {size.value}"
		)
	if sheet.size_class is not size:
		raise InstanceError(f"the statement is one of a {sheet.size_class.value}, not of a {size.value}")
	if disclosure.size_class is not size:
		raise InstanceError(
			f"the publication is one of a {disclosure.size_class.value}, not of a {size.value}"
		)
	if sheet.scheme.year != periods.fiscal_year_end.year:
		raise InstanceError(
			f"the statement is one of the fiscal year ending in {sheet.scheme.year}, the periods end in "
			f"{periods.fiscal_year_end.year}"
		)
	if (sheet.prior_aktiva_total is None) != (periods.prior_fiscal_year_end is None):
		has = "has" if sheet.prior_aktiva_total is not None else "has no"
		raise InstanceError(f"the statement {has} a previous year, the periods do not agree")


def _entity(register: RegisterData) -> Entity:
	if not register.registergericht.strip() or not register.registernummer.strip():
		raise InstanceError(
			"every context names the company by its Registergericht and Registernummer, and the register data lack one"
		)
	return Entity(REGISTER_SCHEME, " ".join(f"{register.registergericht} {register.registernummer}".split()))


def _items(concept: str, current: Decimal, prior: Decimal | None) -> Iterator[Item]:
	yield amount(f"{GAAP}{concept}", Period.STICHTAG, current)
	if prior is not None:
		yield amount(f"{GAAP}{concept}", Period.VORJAHR_STICHTAG, prior)


def _balance_sheet(sheet: BalanceSheet) -> Iterator[Item]:
	"""Each side: its total, then each written position with its Vermerke."""
	scheme, size = sheet.scheme, sheet.size_class
	sides = (
		(scheme.aktiva, sheet.aktiva, sheet.aktiva_total, sheet.prior_aktiva_total),
		(scheme.passiva, sheet.passiva, sheet.passiva_total, sheet.prior_passiva_total),
	)
	for total, lines, current, prior in sides:
		yield from _items(total.concept, current, prior)
		written = _written(scheme, lines)
		for line in lines:
			if line.position.concept in written:
				yield from _items(line.position.concept, line.amount, line.prior)
				yield from _vermerke(scheme, size, line)


def _written(scheme: BalanceSheetScheme, lines: Iterable[Line]) -> set[str]:
	"""The positions with an amount in either year and those above them."""
	lines = tuple(lines)
	shown = {line.position.concept for line in lines}
	written: set[str] = set()
	for line in lines:
		if not line.shown:
			continue
		position: Position | None = line.position
		while position is not None and position.concept in shown:
			written.add(position.concept)
			position = scheme.parent(position.concept)
	return written


def _vermerke(scheme: BalanceSheetScheme, size: SizeClass, line: Line) -> Iterator[Item]:
	"""The Vermerke of a line the class can report, and for the Gezeichnetes Kapital the Nennbetrag they are offset
	from."""
	reported = [noted for noted in line.vermerke if noted.shown and scheme.shows(noted.vermerk.scope, size)]
	deductions = [noted for noted in reported if noted.vermerk.kind in _DEDUCTIONS]
	if line.position.concept == SUBSCRIBED and deductions:
		yield from _items(
			NENNBETRAG,
			line.amount - sum((noted.amount for noted in deductions), _ZERO),
			None if line.prior is None else line.prior - sum((_prior(noted) for noted in deductions), _ZERO),
		)
	for noted in reported:
		sign = -1 if noted.vermerk.kind in _DEDUCTIONS else 1
		yield from _items(
			noted.vermerk.concept, sign * noted.amount, None if noted.prior is None else sign * noted.prior
		)


def _prior(noted: VermerkLine) -> Decimal:
	return noted.prior or _ZERO


def _unreported_vermerke(sheet: BalanceSheet) -> Iterator[str]:
	"""The Vermerke of the class at positions whose concepts the taxonomy presents only under a position it does not
	show, each with its position and the amounts of both years."""
	scheme, size = sheet.scheme, sheet.size_class
	for line in sheet.aktiva + sheet.passiva:
		for noted in line.vermerke:
			if noted.shown and not scheme.shows(noted.vermerk.scope, size):
				prior = "" if noted.prior is None else f" (Vorjahr: {_euro(noted.prior)})"
				yield f"{line.position.marker} {line.label}, {noted.vermerk.label}: {_euro(noted.amount)}{prior}"


def _published(scheme: BalanceSheetScheme, size: SizeClass) -> Iterator[str]:
	"""The positions of the class with their totals, the Vermerke it reports, the Nennbetrag of its Gezeichnetes
	Kapital, and the places of its Angaben and signatures."""
	yield scheme.aktiva.concept
	yield scheme.passiva.concept
	for position in scheme.visible(size):
		yield position.concept
		for vermerk in scheme.vermerke(position.concept, size):
			if scheme.shows(vermerk.scope, size):
				yield vermerk.concept
		if position.concept == SUBSCRIBED:
			yield NENNBETRAG
	yield from RegisterData.concepts().values()
	yield CONTINGENCIES
	for kind in Contingency:
		yield from (kind.concept, kind.pensions_concept, kind.group_concept)
	for slot in SLOTS[size]:
		yield from (concept for concept in (slot.text, slot.amount) if concept)
	if size is SizeClass.KLEIN:
		yield from (f"{SIGNATURE}.{part}" for part in _SIGNATURE_PARTS)


class _Texts:
	"""The texts of the file in the characters the writer takes, with a finding for each text it cannot keep."""

	def __init__(self) -> None:
		self.findings: dict[str, Finding] = {}

	def clean(self, value: str, where: str) -> str:
		lines = []
		for line in unicodedata.normalize("NFC", value.strip()).splitlines():
			try:
				lines.append(transliterate(line).rstrip())
			except CharsetError as error:
				self._refused(value, where, error.characters)
				kept = "".join(character for character in line if character not in error.characters)
				lines.append(transliterate(kept).rstrip())
		return "\n".join(lines)

	def _refused(self, value: str, where: str, characters: tuple[str, ...]) -> None:
		text = (
			f"„{value.strip()}“ enthält Zeichen, die die XBRL-Datei nicht nimmt: "
			f"{', '.join(describe(character) for character in characters)}."
		)
		self.findings.setdefault(
			text, Finding(Code.CHARACTERS, Severity.ERROR, text, _CHARACTERS_REFERENCE, where)
		)


class _Angaben:
	"""The facts of the Angaben of one class: register data, Haftungsverhältnisse, texts, the number of employees
	and the signatures."""

	def __init__(
		self,
		sheet: BalanceSheet,
		size: SizeClass,
		notes: Notes,
		entries: Iterable[CatalogueEntry],
		texts: _Texts,
	) -> None:
		self.size, self.notes, self.texts = size, notes, texts
		self.findings: list[Finding] = []
		self.contingencies_stated = False
		self.paragraphs: dict[str, list[str]] = {slot.text: [] for slot in SLOTS[size] if slot.text}
		self.amounts: list[Item] = []
		answers: dict[str, NoteAnswer] = {}
		for answer in notes.answers:
			answers.setdefault(answer.code, answer)
		published = {entry.item.code for entry in entries if entry.published}
		if size is SizeClass.KLEINST:
			self._paragraph(OTHER_BELOW, "\n".join(_unreported_vermerke(sheet)))
		for slot in SLOTS[size]:
			answer = answers.get(slot.code)
			stated = slot.code in published and answer is not None and answer.answer is Answer.YES
			self._require_answer_for_entries(slot.code, stated)
			if stated and answer is not None:
				self._state(slot, answer)
		if size is SizeClass.KLEINST:
			self._paragraph(OTHER_BELOW, "\n".join(self._signed(signature) for signature in notes.signatures))

	def facts(self) -> Iterator[Fact]:
		register = self.notes.register
		concepts = RegisterData.concepts()
		for field in ("firma", "sitz", "registergericht", "registernummer"):
			yield Item(
				f"{GAAP}{concepts[field]}", WJ, self.texts.clean(getattr(register, field), concepts[field])
			)
		if register.in_liquidation:
			yield Item(f"{GAAP}{concepts['in_liquidation']}", WJ, _LIQUIDATION)
		yield from (item for item in self.amounts if item.period is Period.STICHTAG)
		for concept, paragraphs in self.paragraphs.items():
			if paragraphs:
				yield Item(f"{GAAP}{concept}", WJ, "\n\n".join(paragraphs))
		yield from (item for item in self.amounts if item.period is WJ)
		if self.size is SizeClass.KLEIN:
			yield from self._signature_block()

	def _paragraph(self, concept: str, paragraph: str) -> None:
		if paragraph:
			self.paragraphs[concept].append(paragraph)

	def _require_answer_for_entries(self, code: str, stated: bool) -> None:
		"""Entries of Haftungsverhältnisse or Vorschüsse need their Angabe answered „ja“, or the file would lose them."""
		entries = {"HAFTUNGSVERHAELTNISSE": self.notes.contingent, "ORGANKREDITE": self.notes.advances}.get(
			code
		)
		if entries and not stated:
			self.findings.append(
				Finding(
					Code.ENTRIES,
					Severity.ERROR,
					f"Zur Angabe {code} sind Einträge erfasst, die Angabe ist aber nicht mit „ja“ beantwortet; ohne "
					"„ja“ fehlen die Einträge in der XBRL-Datei.",
					"§ 264 Abs. 1 Satz 5, § 268 Abs. 7, § 285 Nr. 9 Buchst. c HGB",
					code,
				)
			)

	def _state(self, slot: Slot, answer: NoteAnswer) -> None:
		text = self.texts.clean(answer.text, slot.code)
		if slot.amount == CONTINGENCIES:
			self.contingencies_stated = True
			self._paragraph(slot.text, text)
			self._contingencies(slot, answer)
		elif slot.code == "ORGANKREDITE":
			totals = advances(self.notes.advances)
			if not totals:
				self._paragraph(slot.text, _with_amount(text, answer.amount))
				return
			self._require_total(slot.code, answer, sum((total.amount for total in totals), _ZERO))
			for total in totals:
				self._paragraph(slot.text, self.texts.clean(_advance_text(total), slot.code))
			self._paragraph(slot.text, text)
		elif slot.amount:
			self._number(slot, answer)
		else:
			self._paragraph(slot.text, _with_amount(text, answer.amount))

	def _require_total(self, code: str, answer: NoteAnswer, exact: Decimal) -> None:
		"""The amount of an answer with entries behind it is their total."""
		if answer.amount is not None and answer.amount != exact:
			self.findings.append(
				Finding(
					Code.AMOUNT,
					Severity.ERROR,
					f"Der Betrag der Angabe {code} ist nicht die Summe ihrer Einträge von {_euro(exact)}.",
					"§ 268 Abs. 7, § 285 Nr. 9 Buchst. c HGB",
					code,
					answer.amount,
				)
			)

	def _contingencies(self, slot: Slot, answer: NoteAnswer) -> None:
		totals = contingencies(self.notes.contingent)
		if not totals:
			if answer.amount is not None:
				self.amounts.append(
					amount(f"{GAAP}{CONTINGENCIES}", Period.STICHTAG, half_up_euro(answer.amount))
				)
			return
		self._require_total(slot.code, answer, sum((total.amount for total in totals), _ZERO))
		rounded = apportion_full_euros(tuple(total.amount for total in totals))
		self.amounts.append(amount(f"{GAAP}{CONTINGENCIES}", Period.STICHTAG, sum(rounded, _ZERO)))
		securities = []
		for total, kind_amount in zip(totals, rounded, strict=True):
			kind = total.kind
			self.amounts.append(amount(f"{GAAP}{kind.concept}", Period.STICHTAG, kind_amount))
			for concept, part in ((kind.pensions_concept, total.pensions), (kind.group_concept, total.group)):
				if part:
					value = kind_amount if part == total.amount else half_up_euro(part)
					self.amounts.append(amount(f"{GAAP}{concept}", Period.STICHTAG, value))
			if total.securities:
				granted = "; ".join(self.texts.clean(entry, slot.code) for entry in total.securities)
				securities.append(f"{kind.value}, gewährte Pfandrechte und sonstige Sicherheiten: {granted}")
		self._paragraph(slot.text, "\n".join(securities))

	def _number(self, slot: Slot, answer: NoteAnswer) -> None:
		if answer.amount is None:
			self.findings.append(
				Finding(
					Code.NUMBER,
					Severity.ERROR,
					"Die durchschnittliche Zahl der Arbeitnehmer braucht die XBRL-Datei als Zahl.",
					"§ 285 Nr. 7 HGB",
					slot.code,
				)
			)
			return
		exponent = answer.amount.as_tuple().exponent
		decimals = -exponent if isinstance(exponent, int) and exponent < 0 else 0
		self.amounts.append(Item(f"{GAAP}{slot.amount}", WJ, answer.amount, decimals=decimals))

	def _when(self, signature: Signature) -> str:
		day = "" if signature.signed_on is None else day_label(signature.signed_on)
		return ", ".join(part for part in (self.texts.clean(signature.place, SIGNATURE), day) if part)

	def _signed(self, signature: Signature) -> str:
		"""A signature of a Kleinst under its balance sheet, such as „Musterstadt, 12. Mai 2027: gez. Erika Beispiel,
		Geschäftsführerin“."""
		who = ", ".join(
			part
			for part in (
				self.texts.clean(signature.name, SIGNATURE),
				self.texts.clean(signature.function, SIGNATURE),
			)
			if part
		)
		when = self._when(signature)
		return f"{when}: gez. {who}" if when else f"gez. {who}"

	def _signature_block(self) -> Iterator[Fact]:
		signatures = self.notes.signatures
		places = tuple(
			dict.fromkeys(self.texts.clean(signature.place, SIGNATURE) for signature in signatures)
		)
		days = tuple(dict.fromkeys(signature.signed_on for signature in signatures))
		shared = len(places) == 1 and len(days) == 1 and bool(places[0]) and days[0] is not None
		if shared:
			yield Item(f"{GAAP}{SIGNATURE}.place", WJ, places[0])
			yield Item(f"{GAAP}{SIGNATURE}.date", WJ, days[0])
		persons: dict[Tuple, None] = {}
		for signature in signatures:
			person: list[Fact] = [
				Item(f"{GAAP}{SIGNATURE}.person.name", WJ, self.texts.clean(signature.name, SIGNATURE))
			]
			when = "" if shared else self._when(signature)
			if when:
				person.append(Item(f"{GAAP}{SIGNATURE}.person.otherattributes", WJ, when))
			organ = self.texts.clean(signature.function, SIGNATURE) or _ORGAN
			persons[
				Tuple(
					f"{GAAP}{SIGNATURE}.type",
					(
						Item(f"{GAAP}{SIGNATURE}.type.name", WJ, organ),
						Tuple(f"{GAAP}{SIGNATURE}.person", tuple(person)),
					),
				)
			] = None
		yield from persons


def _advance_text(total: AdvanceTotal) -> str:
	"""The Vorschüsse and Kredite of one group with the parts § 285 Nr. 9 Buchst. c HGB names."""
	rates = tuple(dict.fromkeys(rate for rate in total.interest_rates if rate is not None))
	head = f"{total.group.value}: Vorschüsse und Kredite {_euro(total.amount)}"
	if rates:
		named = " und ".join(f"{_rate(rate)} %" for rate in rates)
		head += f", {'Zinssatz' if len(rates) == 1 else 'Zinssätze'} {named} im Jahr"
	parts = [head]
	conditions = tuple(
		dict.fromkeys(condition.strip() for condition in total.conditions if condition.strip())
	)
	if conditions:
		parts.append(f"wesentliche Bedingungen: {'; '.join(conditions)}")
	if total.repaid:
		parts.append(f"im Geschäftsjahr zurückgezahlt {_euro(total.repaid)}")
	if total.waived:
		parts.append(f"im Geschäftsjahr erlassen {_euro(total.waived)}")
	if total.guarantees:
		parts.append(f"zu ihren Gunsten eingegangene Haftungsverhältnisse: {'; '.join(total.guarantees)}")
	return "; ".join(parts) + "."


def _with_amount(text: str, value: Decimal | None) -> str:
	"""A text with the amount of its answer after it, for a place of the taxonomy that takes no amount."""
	if value is None:
		return text
	return f"{text} ({_euro(value)})" if text else _euro(value)


def _euro(value: Decimal) -> str:
	"""An amount in full euros as a German text writes it, such as 1.234 €."""
	return f"{half_up_euro(value):,.0f} €".replace(",", ".")


def _rate(value: Decimal) -> str:
	"""A rate as a German text writes it, such as 3,5."""
	return f"{value.normalize():f}".replace(".", ",")


def _master_data(
	statement: AnnualStatement,
	size: SizeClass,
	register: RegisterData,
	gcd: MasterData,
	texts: _Texts,
	*,
	contingencies: bool,
) -> Iterator[Fact]:
	"""The GCD: report, periods, audit and company, in the order of de-gcd-2025-04-01-presentation.xml."""
	periods = gcd.periods
	if gcd.generated_on is not None:
		yield Item(f"{GCD}doc.id.generationDate", WJ, gcd.generated_on)
	yield _choice("report.id.reportType", "reportType.JA")
	yield Item(f"{GCD}report.id.reportStatus.reportStatus.dateofapproval", WJ, gcd.adopted_on)
	yield _choice("report.id.reportStatus", "reportStatus.E")
	yield choice(f"{GCD}report.id.revisionStatus", f"de-gcd:{revision_status_concept(gcd.revision)}")
	yield _choice("report.id.reportElement", *(f"reportElements.{code}" for code in _COMPONENTS[size]))
	yield _choice("report.id.reportElement.allocation.genInfo", "toBalance")
	if size is SizeClass.KLEINST:
		yield _choice("report.id.reportElement.allocation.notesMicroBilG", "toBalance")
	if contingencies:
		where = "toBalance" if size is SizeClass.KLEINST else "inNotes"
		yield _choice("report.id.reportElement.allocation.contingencies", where)
	yield _choice("report.id.statementType", "statementType.E")
	bilanzgewinn = any(line.position.concept == BILANZGEWINN for line in statement.balance_sheet.passiva)
	yield Item(f"{GCD}report.id.incomeStatementendswithBalProfit", WJ, bilanzgewinn)
	yield _choice("report.id.accountingStandard", "accountingStandard.HGBM")
	yield _choice("report.id.specialAccountingStandard", "K")
	method = statement.income_statement.scheme.method.name
	yield _choice("report.id.incomeStatementFormat", f"incomeStatementFormat.{method}")
	yield _choice("report.id.consolidationRange", "consolidationRange.EA")
	yield Item(f"{GCD}report.period.fiscalYearBegin", WJ, periods.fiscal_year_begin)
	yield Item(f"{GCD}report.period.fiscalYearEnd", WJ, periods.fiscal_year_end)
	yield Item(f"{GCD}report.period.balSheetClosingDate", WJ, periods.balance_sheet_date)
	if periods.prior_fiscal_year_begin is not None:
		yield Item(f"{GCD}report.period.fiscalPreviousYearBegin", WJ, periods.prior_fiscal_year_begin)
		yield Item(f"{GCD}report.period.fiscalPreviousYearEnd", WJ, periods.prior_fiscal_year_end)
		yield Item(
			f"{GCD}report.period.balSheetClosingDatePreviousYear", WJ, periods.prior_balance_sheet_date
		)
	yield _choice("report.audit.noAudit", "noAuditRequi")
	yield Item(f"{GCD}company.id.name", WJ, texts.clean(register.firma, "genInfo.company.id.name"))
	yield _choice("company.id.legalStatus", "legalStatus.GMBH")
	if gcd.founded_on is not None:
		yield Item(f"{GCD}company.id.FoundationDate", WJ, gcd.founded_on)
	yield _choice("company.id.Incorporation.Type", "Type.HR")
	court = texts.clean(register.registergericht, "genInfo.company.id.Incorporation.court")
	yield Item(f"{GCD}company.id.Incorporation.court", WJ, court)
	yield _choice("company.id.sizeClass", f"sizeClass.{size.gcd}")
	yield _choice("company.id.reportedSizeClassBs", _REPORTED_SCHEMES[size])
	yield Item(f"{GCD}company.id.location", WJ, texts.clean(register.sitz, "genInfo.company.id.location"))
	if gcd.address is not None:
		address = gcd.address
		for part, value in (
			("street", address.street),
			("houseNo", address.house_number),
			("zipCode", address.postal_code),
			("city", address.city),
			("country", address.country),
		):
			yield Item(
				f"{GCD}company.id.location.{part}",
				WJ,
				texts.clean(value, f"genInfo.company.id.location.{part}"),
			)
	number = texts.clean(register.registernummer, "genInfo.company.id.idNo.type.companyId.HRN")
	yield Tuple(f"{GCD}company.id.idNo", (Item(f"{GCD}company.id.idNo.type.companyId.HRN", WJ, number),))
	if register.in_liquidation:
		yield _choice("company.id.CompanyStatus", "companyStatus.L")
	yield Item(f"{GCD}company.disclosureCriterion.scope.CapitalMarketOrientationHGBs264d", WJ, False)


def _choice(concept: str, *values: str) -> Tuple:
	"""A choice of the GCD, its values named below it."""
	return choice(f"{GCD}{concept}", *(f"{GCD}{concept}.{value}" for value in values))
