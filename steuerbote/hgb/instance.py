"""The XBRL instance of the Offenlegung: the festgestellter Jahresabschluss of a Kleinstkapitalgesellschaft or a small
GmbH or UG for the Unternehmensregister, in the profile DISCLOSURE of steuerbote/xbrl/profiles.py.

The register takes the Jahresabschluss „im strukturierten Format Extensible Markup Language (XML)“ (§ 11 Abs. 2 Satz 1
Nr. 4 URV), as XBRL on the HGB-Taxonomie in the views „de-gaap-ci-2025-04-01 ... Einzelabschluss“ and, for a
Kleinstkapitalgesellschaft, „de-gaap-ci-2025-04-01-microbilg ... Einzelabschluss MicroBilG“, each with
de-gcd-2025-04-01 („Arbeitshilfe für die Einreichung von Jahresabschlüssen/Finanzberichten im XBRL-Format“ of the
Unternehmensregister, Stand September 2025). The version is the one of the fiscal year (steuerbote/xbrl/versions.py),
6.9 for 2026, which the register has taken since 15 October 2025.

build(statement, size, notes, disclosure, gcd) gives the Instance: the facts of steuerbote/xbrl/facts.py, the view
they reference, the company, the periods and the concepts the class publishes. It needs no taxonomy, so the Annual
Accounts can build it and show what holds it back before anyone installs one. write(instance, taxonomy) writes it
through the writer of steuerbote/xbrl/writer.py after the checks of the profile.

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
those positions. Those Vermerke are no facts of the instance. The uncalled contributions and own shares are „offen abzusetzen“ from the Gezeichnetes
Kapital (§ 272 Abs. 1 Satz 2 und Abs. 1a Satz 1 HGB); the taxonomy takes them as positive amounts it subtracts from
the Gezeichnetes Kapital of a Kapitalgesellschaft (weight -1 in its calculation linkbase), so the instance reports the
Nennbetrag as bs.eqLiab.equity.subscribed.corp beside them, and the Posten keeps what remains.

The company. Every context names it by Registergericht and Registernummer in the scheme REGISTER_SCHEME: the register
keeps companies by them (§ 3 Abs. 2 URV), and which identifier it expects in a context is unverified.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from steuerbote.hgb.disclosure import Mode, Publication, Signature
from steuerbote.hgb.notes import ContingentLiability, NoteAnswer, OfficerAdvance, RegisterData
from steuerbote.hgb.schemes import BalanceSheetScheme, Position, VermerkKind
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import AnnualStatement, BalanceSheet, Finding, Line, VermerkLine, in_full_euros
from steuerbote.jahresmeldung.corrections import RevisionStatus
from steuerbote.xbrl.facts import Entity, Fact, Item, Period, Periods, amount
from steuerbote.xbrl.profiles import DISCLOSURE
from steuerbote.xbrl.taxonomy import View
from steuerbote.xbrl.versions import Version, for_fiscal_year

REGISTER_SCHEME = "http://www.handelsregister.de"
"""The scheme of the identifier of the company: its Registergericht and Registernummer."""
GAAP = "de-gaap-ci:"
SUBSCRIBED = "bs.eqLiab.equity.subscribed"
NENNBETRAG = "bs.eqLiab.equity.subscribed.corp"
"""„Gezeichnetes Kapital ..., gezeichnetes Kapital (Kapitalgesellschaften)“, from which the deductions are offset."""
_DEDUCTIONS = frozenset({VermerkKind.UNCALLED_CAPITAL, VermerkKind.OWN_SHARES})
_PREPARED = (SizeClass.KLEINST, SizeClass.KLEIN)


class InstanceError(ValueError):
	"""The inputs do not make an Offenlegung Steuerbote writes."""


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
	sheet = in_full_euros(statement).balance_sheet
	facts = tuple(_balance_sheet(sheet))
	return Instance(
		size,
		disclosure.mode,
		for_fiscal_year(gcd.periods.fiscal_year_begin, gcd.periods.fiscal_year_end),
		DISCLOSURE.view(kleinst=size is SizeClass.KLEINST),
		_entity(notes.register),
		gcd.periods,
		facts,
		tuple(_published(sheet.scheme, size)),
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
			line.amount - sum((noted.amount for noted in deductions), Decimal("0")),
			None
			if line.prior is None
			else line.prior - sum((_prior(noted) for noted in deductions), Decimal("0")),
		)
	for noted in reported:
		sign = -1 if noted.vermerk.kind in _DEDUCTIONS else 1
		yield from _items(
			noted.vermerk.concept, sign * noted.amount, None if noted.prior is None else sign * noted.prior
		)


def _prior(noted: VermerkLine) -> Decimal:
	return noted.prior or Decimal("0")


def _published(scheme: BalanceSheetScheme, size: SizeClass) -> Iterator[str]:
	"""The positions of the class with their totals, the Vermerke it reports and the Nennbetrag of its Gezeichnetes
	Kapital."""
	yield scheme.aktiva.concept
	yield scheme.passiva.concept
	for position in scheme.visible(size):
		yield position.concept
		for vermerk in scheme.vermerke(position.concept, size):
			if scheme.shows(vermerk.scope, size):
				yield vermerk.concept
		if position.concept == SUBSCRIBED:
			yield NENNBETRAG
