"""The Bilanzzuordnung of a company: which position of the HGB-Taxonomie each account of its books goes to.

The E-Bilanz (§ 5b EStG) and the Offenlegung of the Jahresabschluss (§§ 325, 326 HGB) read the same books through
the same mapping: the E-Bilanz reports the positions themselves, the Offenlegung sums them up to the scheme of § 266
HGB along the hierarchy of the taxonomy (steuerbote/hgb/statement.py). A Mapping belongs to one company, one chart of
accounts (SKR03, SKR04 or one of its own) and one version of the taxonomy whose positions it names, and is plain
data. Every account has one place in it:

- A Rule: the account goes to a position, named without the prefix of the GAAP module, as steuerbote/hgb and
  Taxonomy.parents() name them. A balance on the other side of the position goes to the position for the opposite
  balance, if the rule names one: a bank account „würde bei einem Saldo im „Soll“ auf der Aktivseite ... zugeordnet
  werden. Ist der Saldo jedoch im „Haben“ (d.h. das Konto wurde „überzogen“) so erfolgt der Ausweis auf der
  Passivseite unter den Verbindlichkeiten in der Position „Verbindlichkeiten gegenüber Kreditinstituten““
  (Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025, A.13).
- Each rule carries its Abschlusszweck, as the DATEV charts mark accounts „ausschließlich für die Handelsbilanz“ (HB)
  or „ausschließlich für die Steuerbilanz“ (SB) (DATEV SKR 03, Art.-Nr. 11174, and SKR 04, Art.-Nr. 11175, „Gültig
  für 2026“, Fußnote 4): a rule for both counts in every balance sheet, one for the Handelsbilanz or the Steuerbilanz
  only in that one (Rule.counts_for).
- Each rule carries the flags the Offenlegung notes below the positions: whether the balance is owed to or by the
  shareholders, „Ausleihungen, Forderungen und Verbindlichkeiten gegenüber Gesellschaftern sind in der Regel als
  solche jeweils gesondert auszuweisen oder im Anhang anzugeben“ (§ 42 Abs. 3 GmbHG), and its remaining term, „Der
  Betrag der Forderungen mit einer Restlaufzeit von mehr als einem Jahr ist bei jedem gesondert ausgewiesenen Posten
  zu vermerken“ and likewise the Verbindlichkeiten „mit einer Restlaufzeit bis zu einem Jahr“ and „von mehr als einem
  Jahr“ (§ 268 Abs. 4 Satz 1, Abs. 5 Satz 1 HGB). The terms are those of steuerbote.hgb.statement.RemainingTerm; the
  E-Bilanz reports no Restlaufzeiten.
- A netting group: rules that name the same group form one settlement position, whose combined balance decides the
  side every account of it goes to. „Posten der Aktivseite dürfen nicht mit Posten der Passivseite ... verrechnet
  werden“ (§ 246 Abs. 2 Satz 1 HGB), but claims and debts towards the same creditor that can be set off against each
  other (§ 387 BGB; for claims from the Steuerschuldverhältnis § 226 Abs. 1 AO) are no separate Vermögensgegenstand
  and Schuld, as the commentaries on § 246 HGB accept: the Vorsteuer is deducted from the Umsatzsteuer of the same
  period (§ 16 Abs. 2 Satz 1 UStG), and what remains of earlier periods and years is set off against the same
  Finanzamt. The usual assignments of the standard charts therefore show the VAT accounts on the asset or the
  liability side by the balance of the group. A rule of a group names the position for the opposite balance, so that
  the group has a position on each side; a netted group is a hint to confirm with the Steuerberatung. Every other
  account keeps its own sign, a bank account above all (A.13).
- Parties: an account of type Receivable or Payable, whose every posting ERPNext keeps with its party, is split by
  party at the Stichtag. „Posten der Aktivseite dürfen nicht mit Posten der Passivseite ... verrechnet werden“
  (§ 246 Abs. 2 Satz 1 HGB): a customer with a credit balance is a sonstige Verbindlichkeit, not a smaller Forderung
  against the others, and a supplier with a debit balance a sonstiger Vermögensgegenstand. Each party goes to the
  position on the side of its own balance: the position of the rule, or its position for the opposite balance, or,
  where the rule names none, the one of its kind (RECLASSIFICATION). A customer and a supplier that ERPNext links as
  one party (Party Link) are set off against each other (§ 387 BGB) and go together to the position on the side of
  their net balance. Postings without a party count on their own, with a hint. The parts of an account on one
  position are one balance again, so that the Kontennachweis of the E-Bilanz lists the account under each position
  with its part, and the parts add up to the ledger.
- A Watched account: an account whose position is not decided. A balance on it holds the E-Bilanz and the
  Jahresabschluss back; at the level hint it only adds a hint, as in the VAT Return Mapping since v0.4.0
  (steuerbote/ustva/mapping.py).
- An Excluded account: an account outside the Bilanz and the GuV, with the reason, such as the Vortrags- and
  statistical accounts of class 9 of the DATEV charts.

An account in two places is refused, so that a balance never counts twice. Account numbers are compared as written,
like every account number of Steuerbote.

Positions. check() tells what the rules may not name, against a view of the taxonomy (steuerbote/xbrl/taxonomy.py):

- a position the taxonomy does not have: „Es dürfen bei der Einreichung nur Positionen der zugelassenen,
  standardisierten Taxonomie-Schemata ... verwendet werden“ (Leitfaden B.10);
- an abstract position and one that takes no amount in euros: a balance is an amount, which only a monetary item
  holds (XBRL 2.1, Kap. 5.1.1; Leitfaden A.13);
- a position outside the Bilanz and the GuV, the parts § 5b Abs. 1 Satz 1 EStG names with their Kontennachweise and
  the presentation networks balanceSheet and incomeStatement hold (Leitfaden B.9.3, B.11);
- a position of another legal form: Steuerbote serves the GmbH and the UG, and a Kapitalgesellschaft reports „nur
  Positionen mit der Auszeichnung „legalFormKSt“ = „true“ und Positionen, die keiner Rechtsform zugeordnet sind“
  (Leitfaden B.4.2);
- a position marked „Einreichung an Finanzverwaltung“ (Leitfaden A.9.3, B.14.6) or „onlyPermittedForSoBil_ErgBil“,
  which has a value only in a Sonder- or Ergänzungsbilanz (A.9.3) that a GmbH never files;
- a position of the Umsatzkostenverfahren: Steuerbote draws the GuV up by the Gesamtkostenverfahren, and „dürfen
  Positionen mit der Auszeichnung typeOperatingResult = UKV nicht übermittelt werden“ (Leitfaden B.14.3.1.15), as
  the ledger knows the kind of an expense, not its function;
- a position without a debit or credit balance, for which „muss aus dem fachlichen Kontext heraus individuell
  entschieden werden, ob eine Multiplikation mit „-1“ ... erforderlich ist“ (Leitfaden A.13);
- a position for the opposite balance on the same side as the position, or in the other part;
- with the part of each account, a position of the other part: the Bilanz holds the Vermögen and the Schulden at
  the Stichtag, the GuV the Aufwendungen and Erträge of the Geschäftsjahr (§ 242 Abs. 1 und 2 HGB), and ERPNext sums
  a balance sheet account up to the day and a profit and loss account within the year (its report_type, Part);
- a remaining term on a position that is neither a Forderung nor a Verbindlichkeit (§ 268 Abs. 4 and 5 HGB), and a
  shareholder flag on one that is no Ausleihung, Forderung or Verbindlichkeit (§ 42 Abs. 3 GmbHG): the flags are
  where the Offenlegung notes them, at the position or at the position for the opposite balance.

Each Problem has an English template for the form of the mapping and a German sentence for the findings of a
document, as the findings of steuerbote/xbrl/checks.py and steuerbote/hgb/statement.py read.

Placement. place() puts the balances of the books (Books, as steuerbote/balances.py reads them) on their positions,
for the balance sheet of a purpose: the Handelsbilanz, the Steuerbilanz or, with Purpose.BOTH, the Einheitsbilanz.

- Signs: „Entspricht die Soll/Haben-Auszeichnung eines Kontos der Soll/Haben-Auszeichnung der Position, dann ist der
  Kontensaldo unverändert zu weiteren zugeordneten Konten zu addieren ... Bei abweichenden Soll/Haben-Auszeichnungen
  eines Kontos, ist der Kontosaldo mit „-1“ zu multiplizieren“ (Leitfaden A.13). A balance is debit minus credit; its
  value is that on a debit position and the negative on a credit one, so Erlösschmälerungen on an account of the
  Umsatzerlöse lower them. A balance on the other side of a position goes to the position for the opposite balance,
  where the rule names one, and there counts as it is.
- A „davon“ position is in no calculation, „Mit „NIL“ übermittelte „leere“ Mussfelder“ aside (Leitfaden B.14.11), and
  the taxonomy 6.10 holds: „Zu rechnerisch nicht verknüpften Positionen darf das Tupel „Kontensalden zu einer
  Position“ nicht übermittelt werden“ (Technischer Leitfaden 6.10, B.12.1). A balance on one counts in the position
  the presentation puts it under, the nearest a calculation holds (Placed.position); the Offenlegung reads the „davon“
  position itself for its Vermerk (Placed.concept, steuerbote/hgb/statement.py).
- Completeness: „Der Jahresabschluß hat sämtliche Vermögensgegenstände, Schulden, Rechnungsabgrenzungsposten sowie
  Aufwendungen und Erträge zu enthalten“ (§ 246 Abs. 1 Satz 1 HGB). A balance on an account without a place in the
  mapping, on one without an account number, on a watched one at the level blocking and on a refused position is an
  error, which holds the E-Bilanz and the Jahresabschluss back from „Bereit“ (steuerbote/jahresmeldung/findings.py).
  A watched account at the level hint, an account outside the Bilanz and the GuV and a rule of another purpose leave
  their balance out with a hint; the documents check that Aktiva and Passiva still agree.
- Auffangpositionen, „erkennbar durch die Formulierungen im beschreibenden Text „nicht zuordenbar“ oder „ohne
  Zuordnung““ (Leitfaden A.10.4), take a balance with a hint, since they serve only where „eine durch Mussfelder
  vorgegebene Differenzierung ... nicht aus der Buchhaltung ableitbar“ is.
- With the fiscal year, a position not valid in it is an error: „Die Übermittelbarkeit kann zeitlich eingeschränkt
  sein“ (Leitfaden B.11, B.14.4.1).
- The result of earlier fiscal years that no Period Closing Voucher closed (Books.earlier_result) goes to the closing
  account, as a Period Closing Voucher books it there (closing_account_head of ERPNext 16), with a hint: the
  Gewinnvortrag or Verlustvortrag (§ 266 Abs. 3 A. IV. HGB). Without a closing account it is an error, since the
  balance sheet would lack it. The Period Closing Voucher of the fiscal year itself is never read.
- A view of another version than the mapping names is an error: the positions of a version are the „amtlich
  vorgeschriebener Datensatz“ of its letter (§ 5b Abs. 1 Satz 1 EStG; steuerbote/xbrl/versions.py).

Findings are those of steuerbote/xbrl/checks.py in kind: a Code, Fehler or Hinweis, a German sentence and its source,
with the account, the position and the balance they are about.

Defaults. The default mapping of a chart for a version of the taxonomy (steuerbote/ebilanz/defaults.py) names
accounts by number and by range, as the DATEV charts group them (Accounts): its entries, DefaultRule, DefaultWatched
and DefaultExcluded, give every account of a company within their range the place of the entry, with the account's
own number (Defaults.for_accounts). Entries do not overlap, so an account takes one place.

Errors are MappingError with an English template and its values, which the Frappe layer translates; MESSAGES and the
templates of REFUSALS are those templates. This module is pure Python and never imports Frappe.
"""

import re
from collections.abc import Iterable, Iterator
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from steuerbote.hgb.statement import RemainingTerm
from steuerbote.ustva.mapping import WatchLevel, is_account_number
from steuerbote.xbrl.taxonomy import (
	BALANCE_SHEET,
	GAAP_PREFIX,
	INCOME_STATEMENT,
	LABEL,
	NOT_PERMITTED_SUBMISSION,
	Balance,
	IncomeStatementFormat,
	LegalForm,
	Taxonomy,
)
from steuerbote.xbrl.versions import FIRST, TAXONOMIES

NOT_AN_ACCOUNT_NUMBER = "{0} is no account number: it is a text without blanks at either end."
NO_POSITION = "Account {0} has no position."
SAME_OPPOSITE = "Account {0}: the position for the opposite balance is its position itself."
NO_PURPOSE = "Account {0}: {1} is no Abschlusszweck; it is both, commercial or tax."
NO_REMAINING_TERM = "Account {0}: {1} is no remaining term."
NO_FLAG = "Account {0}: whether the balance is owed to or by the shareholders is yes or no, not {1}."
NO_LEVEL = "Account {0}: the level of a watched account is blocking or hint, not {1}."
NO_REASON = "Account {0} lies outside the Bilanz and the GuV, but the mapping does not say why."
NETTING_WITHOUT_OPPOSITE = (
	"Account {0} belongs to the netting group {1}, so it needs the position for the opposite balance as well."
)
TWICE = "Account {0} has more than one row in the Balance Sheet Mapping."
UNKNOWN_VERSION = "Steuerbote knows no HGB-Taxonomie {0}."
MESSAGES = (
	NOT_AN_ACCOUNT_NUMBER,
	NO_POSITION,
	SAME_OPPOSITE,
	NO_PURPOSE,
	NO_REMAINING_TERM,
	NO_FLAG,
	NO_LEVEL,
	NO_REASON,
	NETTING_WITHOUT_OPPOSITE,
	TWICE,
	UNKNOWN_VERSION,
)

REMAINING_TERMS: MappingProxyType[str, RemainingTerm] = MappingProxyType(
	{
		"up to one year": RemainingTerm.UP_TO_ONE_YEAR,
		"one to five years": RemainingTerm.ONE_TO_FIVE_YEARS,
		"over five years": RemainingTerm.OVER_FIVE_YEARS,
	}
)
"""The remaining terms by the values a row of the mapping holds them under."""
_TERM_VALUES = MappingProxyType({term: value for value, term in REMAINING_TERMS.items()})
KAPITALGESELLSCHAFT = LegalForm.KST
"""The kind of legal form of a GmbH and an UG, the companies Steuerbote serves (Leitfaden B.4.1)."""
INCOME_STATEMENT_FORMAT = IncomeStatementFormat.GKV
TERM_SCOPES = ("bs.ass.currAss.receiv", "bs.eqLiab.liab")
"""The Forderungen und sonstigen Vermögensgegenstände and the Verbindlichkeiten (§ 266 Abs. 2 B. II., Abs. 3 C. HGB),
whose remaining terms § 268 Abs. 4 Satz 1 and Abs. 5 Satz 1 HGB note."""
SHAREHOLDER_SCOPES = (
	"bs.ass.fixAss.fin.loansToSharehold",
	"bs.ass.fixAss.fin.loansToAffil",
	"bs.ass.fixAss.fin.loansToParticip",
	"bs.ass.fixAss.fin.otherLoans",
	*TERM_SCOPES,
)
"""The Ausleihungen (§ 266 Abs. 2 A. III. 2., 4. and 6. HGB and those to the shareholders), Forderungen and
Verbindlichkeiten, which § 42 Abs. 3 GmbHG notes „gegenüber Gesellschaftern“."""


class MappingError(ValueError):
	"""Rows the mapping cannot hold; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


class AccountKind(StrEnum):
	"""The account types of ERPNext whose postings carry a party (party_type and party of the GL Entry)."""

	RECEIVABLE = "Receivable"
	PAYABLE = "Payable"


RECLASSIFICATION: MappingProxyType[AccountKind, str] = MappingProxyType(
	{
		AccountKind.RECEIVABLE: "bs.eqLiab.liab.other.other",
		AccountKind.PAYABLE: "bs.ass.currAss.receiv.other.other",
	}
)
"""Where the parties on the other side go when the rule of their account names no position for the opposite balance:
customers with a credit balance to the übrige sonstige Verbindlichkeiten (§ 266 Abs. 3 C. 8. HGB), suppliers with a
debit balance to the übrige sonstige Vermögensgegenstände (§ 266 Abs. 2 B. II. 4. HGB), as the defaults place the
opposite balance of the Forderungen and Verbindlichkeiten aus Lieferungen und Leistungen (steuerbote/ebilanz/
defaults.py)."""


class Part(StrEnum):
	"""The part of the Jahresabschluss an account and a position belong to."""

	BALANCE_SHEET = "Bilanz"
	INCOME_STATEMENT = "GuV"

	@property
	def role(self) -> str:
		"""The presentation network of the part (Leitfaden B.9.3)."""
		return BALANCE_SHEET if self is Part.BALANCE_SHEET else INCOME_STATEMENT

	@classmethod
	def of_report_type(cls, report_type: str) -> Part:
		"""The part of an account of ERPNext by its report_type, which its root type sets: „Balance Sheet“ for Asset,
		Liability and Equity, „Profit and Loss“ for Income and Expense (erpnext/accounts/doctype/account/account.py)."""
		try:
			return {"Balance Sheet": cls.BALANCE_SHEET, "Profit and Loss": cls.INCOME_STATEMENT}[report_type]
		except KeyError:
			raise ValueError(f"{report_type!r} is no report type of an account of ERPNext") from None


class Purpose(StrEnum):
	"""The Abschlusszweck of a rule: which balance sheets the account is booked for (DATEV, Fußnote 4)."""

	BOTH = "both"
	COMMERCIAL = "commercial"
	"""HB: the Handelsbilanz only."""
	TAX = "tax"
	"""SB: the Steuerbilanz only."""


@dataclass(frozen=True, slots=True)
class Rule:
	"""An account that goes to a position, with the position for a balance on the other side, its Abschlusszweck
	and the flags of the Offenlegung."""

	account_number: str
	concept: str
	opposite: str | None = None
	purpose: Purpose = Purpose.BOTH
	shareholder: bool = False
	remaining_term: RemainingTerm | None = None
	netting: str | None = None
	"""The netting group of the account, None for an account that keeps its own sign."""

	def __post_init__(self) -> None:
		number = _require_number(self.account_number)
		concept = _concept_name(self.concept)
		if not concept:
			raise MappingError(NO_POSITION, number)
		opposite = _concept_name(self.opposite) or None
		if opposite == concept:
			raise MappingError(SAME_OPPOSITE, number)
		object.__setattr__(self, "concept", concept)
		object.__setattr__(self, "opposite", opposite)
		try:
			object.__setattr__(self, "purpose", Purpose(self.purpose))
		except ValueError:
			raise MappingError(NO_PURPOSE, number, self.purpose) from None
		if not isinstance(self.shareholder, bool):
			raise MappingError(NO_FLAG, number, self.shareholder)
		term = self.remaining_term
		if term is not None and not isinstance(term, RemainingTerm):
			if term not in REMAINING_TERMS:
				raise MappingError(NO_REMAINING_TERM, number, term)
			object.__setattr__(self, "remaining_term", REMAINING_TERMS[term])
		netting = " ".join(str(self.netting or "").split()) or None
		if netting is not None and opposite is None:
			raise MappingError(NETTING_WITHOUT_OPPOSITE, number, netting)
		object.__setattr__(self, "netting", netting)

	@property
	def term_value(self) -> str | None:
		"""The remaining term as a row of the mapping holds it."""
		return None if self.remaining_term is None else _TERM_VALUES[self.remaining_term]

	def counts_for(self, purpose: Purpose) -> bool:
		"""Whether the balance counts in a balance sheet of the purpose: a rule for both in every one, a rule for the
		Handelsbilanz or the Steuerbilanz in that one alone. The Einheitsbilanz, „deutsches Handelsrecht (sog.
		Einheitsbilanz)“, which the tax administration treats as a Steuerbilanz (Leitfaden B.13), is a balance sheet for
		both, so only the rules for both count in it."""
		return self.purpose is Purpose.BOTH or self.purpose is purpose


@dataclass(frozen=True, slots=True)
class Watched:
	"""An account whose position is not decided: a balance on it holds the documents back, or at the level hint only
	adds a hint."""

	account_number: str
	level: WatchLevel = WatchLevel.BLOCKING

	def __post_init__(self) -> None:
		number = _require_number(self.account_number)
		try:
			object.__setattr__(self, "level", WatchLevel(self.level))
		except ValueError:
			raise MappingError(NO_LEVEL, number, self.level) from None


@dataclass(frozen=True, slots=True)
class Excluded:
	"""An account outside the Bilanz and the GuV, with the reason on one line."""

	account_number: str
	reason: str

	def __post_init__(self) -> None:
		number = _require_number(self.account_number)
		reason = " ".join(str(self.reason or "").split())
		if not reason:
			raise MappingError(NO_REASON, number)
		object.__setattr__(self, "reason", reason)


type Place = Rule | Watched | Excluded


@dataclass(frozen=True, slots=True)
class Mapping:
	"""The Bilanzzuordnung of a company: its chart, the version of the taxonomy its positions belong to, and the place
	of each account."""

	chart: str
	rules: tuple[Rule, ...] = ()
	watched: tuple[Watched, ...] = ()
	excluded: tuple[Excluded, ...] = ()
	taxonomy_version: str = FIRST.version
	_by_number: MappingProxyType[str, Place] = field(init=False, repr=False, compare=False)

	def __post_init__(self) -> None:
		if self.taxonomy_version not in TAXONOMIES:
			raise MappingError(UNKNOWN_VERSION, self.taxonomy_version)
		object.__setattr__(self, "rules", tuple(self.rules))
		object.__setattr__(self, "watched", tuple(self.watched))
		object.__setattr__(self, "excluded", tuple(self.excluded))
		places: dict[str, Place] = {}
		for place in self._places():
			if place.account_number in places:
				raise MappingError(TWICE, place.account_number)
			places[place.account_number] = place
		object.__setattr__(self, "_by_number", MappingProxyType(places))

	def _places(self) -> Iterable[Place]:
		yield from self.rules
		yield from self.watched
		yield from self.excluded

	@property
	def numbers(self) -> frozenset[str]:
		"""Every account the mapping gives a place."""
		return frozenset(self._by_number)

	def place_of(self, account_number: str) -> Place | None:
		"""The rule, the watched entry or the exclusion of an account; None for an account without a place."""
		return self._by_number.get(account_number)


def _require_number(value: object) -> str:
	if not is_account_number(value):
		raise MappingError(NOT_AN_ACCOUNT_NUMBER, value)
	return value


def _concept_name(value: object) -> str:
	"""A position without blanks and without the prefix of the GAAP module."""
	return str(value or "").strip().removeprefix(f"{GAAP_PREFIX}:")


@dataclass(frozen=True, slots=True)
class Refusal:
	"""Why a rule may not name a position: an English template for the form, a German sentence for the findings of a
	document, both with the account as {0} and the position as {1}, and the source of the rule."""

	template: str
	sentence: str
	source: str


UNKNOWN_POSITION = Refusal(
	"Account {0}: the HGB-Taxonomie {2} has no position {1}.",
	"Konto {0}: Die HGB-Taxonomie {2} kennt keine Position {1}.",
	"Technischer Leitfaden zur HGB-Taxonomie 6.9, B.10",
)
ABSTRACT = Refusal(
	"Account {0}: {1} is an abstract position, which takes no amount.",
	"Konto {0}: {1} ist eine abstrakte Position, die keinen Betrag aufnimmt.",
	"XBRL 2.1, Kap. 5.1.1",
)
NOT_MONETARY = Refusal(
	"Account {0}: {1} takes no amount in euros.",
	"Konto {0}: {1} nimmt keinen Betrag in Euro auf.",
	"Technischer Leitfaden zur HGB-Taxonomie 6.9, A.13",
)
NOT_A_STATEMENT_POSITION = Refusal(
	"Account {0}: {1} is no position of the Bilanz or the GuV.",
	"Konto {0}: {1} ist keine Position der Bilanz oder der GuV.",
	"§ 5b Abs. 1 Satz 1 EStG; Technischer Leitfaden zur HGB-Taxonomie 6.9, B.9.3, B.11",
)
LEGAL_FORM = Refusal(
	"Account {0}: {1} is no position of a Kapitalgesellschaft.",
	"Konto {0}: {1} ist keine Position einer Kapitalgesellschaft.",
	"Technischer Leitfaden zur HGB-Taxonomie 6.9, B.4.2",
)
SUBMISSION = Refusal(
	"Account {0}: {1} may not be sent to the tax administration („Einreichung an Finanzverwaltung“).",
	"Konto {0}: {1} darf nicht an die Finanzverwaltung übermittelt werden („Einreichung an Finanzverwaltung“).",
	"Technischer Leitfaden zur HGB-Taxonomie 6.9, A.9.3, B.14.6",
)
SPECIAL_BALANCE = Refusal(
	"Account {0}: {1} takes a value only in a Sonder- or Ergänzungsbilanz.",
	"Konto {0}: {1} hat nur in einer Sonder- oder Ergänzungsbilanz einen Wert.",
	"Technischer Leitfaden zur HGB-Taxonomie 6.9, A.9.3",
)
COST_OF_SALES = Refusal(
	"Account {0}: {1} is a position of the Umsatzkostenverfahren; Steuerbote draws the GuV up by the "
	"Gesamtkostenverfahren.",
	"Konto {0}: {1} ist eine Position des Umsatzkostenverfahrens; Steuerbote stellt die GuV nach dem "
	"Gesamtkostenverfahren auf.",
	"Technischer Leitfaden zur HGB-Taxonomie 6.9, B.14.3.1.15",
)
NO_SIDE = Refusal(
	"Account {0}: {1} has no debit or credit balance, so the sign of a balance on it is undecided.",
	"Konto {0}: {1} hat kein Soll oder Haben, so dass das Vorzeichen eines Saldos darauf offen ist.",
	"Technischer Leitfaden zur HGB-Taxonomie 6.9, A.13",
)
SAME_SIDE = Refusal(
	"Account {0}: the position for the opposite balance {1} lies on the same side as {2}.",
	"Konto {0}: Die Position für den Gegensaldo {1} liegt auf derselben Seite wie {2}.",
	"Technischer Leitfaden zur HGB-Taxonomie 6.9, A.13",
)
OTHER_PARTS = Refusal(
	"Account {0}: {1} and its position for the opposite balance {2} belong to different parts, the Bilanz and the "
	"GuV.",
	"Konto {0}: {1} und die Position für den Gegensaldo {2} gehören zu verschiedenen Teilen, Bilanz und GuV.",
	"§ 242 Abs. 1 und 2 HGB",
)
BALANCE_SHEET_ACCOUNT = Refusal(
	"Account {0} is a balance sheet account, but {1} is a position of the GuV.",
	"Konto {0} ist ein Bestandskonto, aber {1} ist eine Position der GuV.",
	"§ 242 Abs. 1 und 2 HGB",
)
INCOME_STATEMENT_ACCOUNT = Refusal(
	"Account {0} is a profit and loss account, but {1} is a position of the Bilanz.",
	"Konto {0} ist ein Erfolgskonto, aber {1} ist eine Position der Bilanz.",
	"§ 242 Abs. 1 und 2 HGB",
)
REMAINING_TERM = Refusal(
	"Account {0}: a remaining term goes only with Forderungen and Verbindlichkeiten, and {1} is neither.",
	"Konto {0}: Eine Restlaufzeit gibt es nur für Forderungen und Verbindlichkeiten, und {1} ist keins von beiden.",
	"§ 268 Abs. 4 Satz 1, Abs. 5 Satz 1 HGB",
)
SHAREHOLDER = Refusal(
	"Account {0}: only Ausleihungen, Forderungen and Verbindlichkeiten are noted as owed to or by the "
	"shareholders, and {1} is none of them.",
	"Konto {0}: Nur Ausleihungen, Forderungen und Verbindlichkeiten werden gegenüber Gesellschaftern vermerkt, und "
	"{1} ist keins davon.",
	"§ 42 Abs. 3 GmbHG",
)
REFUSALS = (
	UNKNOWN_POSITION,
	ABSTRACT,
	NOT_MONETARY,
	NOT_A_STATEMENT_POSITION,
	LEGAL_FORM,
	SUBMISSION,
	SPECIAL_BALANCE,
	COST_OF_SALES,
	NO_SIDE,
	SAME_SIDE,
	OTHER_PARTS,
	BALANCE_SHEET_ACCOUNT,
	INCOME_STATEMENT_ACCOUNT,
	REMAINING_TERM,
	SHAREHOLDER,
)


@dataclass(frozen=True, slots=True)
class Problem:
	"""A rule refused: why, and the values of the template and the sentence, the account first."""

	refusal: Refusal
	values: tuple[object, ...]

	@property
	def account_number(self) -> str:
		return str(self.values[0])

	@property
	def message(self) -> str:
		"""The English message, which the Frappe layer gives through its translation of the template instead."""
		return self.refusal.template.format(*self.values)

	@property
	def text(self) -> str:
		"""The German sentence for the findings of a document."""
		return self.refusal.sentence.format(*self.values)

	@property
	def source(self) -> str:
		return self.refusal.source


def check(
	mapping: Mapping, taxonomy: Taxonomy, parts: ReadOnlyMapping[str, Part] | None = None
) -> tuple[Problem, ...]:
	"""Every problem of the rules of the mapping against a view of the taxonomy, rule by rule; ``parts`` gives the
	part of each account whose part is known, which its positions must belong to."""
	return tuple(
		problem
		for rule in mapping.rules
		for problem in rule_problems(rule, taxonomy, (parts or {}).get(rule.account_number))
	)


def rule_problems(rule: Rule, taxonomy: Taxonomy, part: Part | None = None) -> tuple[Problem, ...]:
	"""The problems of a rule: first those of each of its positions, then those of the rule as a whole."""
	number, concept, opposite = rule.account_number, rule.concept, rule.opposite
	concepts = (concept,) if opposite is None else (concept, opposite)
	found = [
		problem for name in concepts if (problem := position_problem(taxonomy, number, name)) is not None
	]
	if found:
		return tuple(found)
	own = part_of(taxonomy, concept)
	if opposite is not None:
		if part_of(taxonomy, opposite) is not own:
			found.append(Problem(OTHER_PARTS, (number, concept, opposite)))
		elif taxonomy.concept(opposite).balance is taxonomy.concept(concept).balance:
			found.append(Problem(SAME_SIDE, (number, opposite, concept)))
	if part is not None and part is not own:
		refusal = BALANCE_SHEET_ACCOUNT if part is Part.BALANCE_SHEET else INCOME_STATEMENT_ACCOUNT
		found.append(Problem(refusal, (number, concept)))
	if rule.remaining_term is not None and not _within(taxonomy, concepts, TERM_SCOPES):
		found.append(Problem(REMAINING_TERM, (number, concept)))
	if rule.shareholder and not _within(taxonomy, concepts, SHAREHOLDER_SCOPES):
		found.append(Problem(SHAREHOLDER, (number, concept)))
	return tuple(found)


def position_problem(taxonomy: Taxonomy, account_number: str, concept: str) -> Problem | None:
	"""Why an account may not go to a position on its own, None where it may."""
	values = (account_number, concept, taxonomy.version)
	if not taxonomy.has(concept):
		return Problem(UNKNOWN_POSITION, values)
	position = taxonomy.concept(concept)
	if position.abstract:
		refusal = ABSTRACT
	elif not position.monetary:
		refusal = NOT_MONETARY
	elif part_of(taxonomy, concept) is None:
		refusal = NOT_A_STATEMENT_POSITION
	elif not position.applies_to(KAPITALGESELLSCHAFT):
		refusal = LEGAL_FORM
	elif not position.permitted_for(NOT_PERMITTED_SUBMISSION):
		refusal = SUBMISSION
	elif position.fiscal.special_balance_only:
		refusal = SPECIAL_BALANCE
	elif not position.suits(INCOME_STATEMENT_FORMAT):
		refusal = COST_OF_SALES
	elif position.balance is None:
		refusal = NO_SIDE
	else:
		return None
	return Problem(refusal, values)


def part_of(taxonomy: Taxonomy, concept: str) -> Part | None:
	"""The part whose presentation network holds a position, None for one of neither."""
	name = _qualified(concept)
	for part in Part:
		network = taxonomy.presentation.get(part.role)
		if network is not None and name in network:
			return part
	return None


def _within(taxonomy: Taxonomy, concepts: Iterable[str], scopes: Iterable[str]) -> bool:
	"""Whether one of the positions is a scope or lies below one in the presentation of the Bilanz."""
	network = taxonomy.presentation.get(BALANCE_SHEET)
	wanted = {_qualified(scope) for scope in scopes}
	for concept in concepts:
		name = _qualified(concept)
		above = network.ancestors(name) if network is not None else ()
		if wanted.intersection((name, *above)):
			return True
	return False


def _qualified(concept: str) -> str:
	return concept if ":" in concept else f"{GAAP_PREFIX}:{concept}"


ZERO = Decimal(0)
CATCH_ALL_WORDS = ("nicht zuordenbar", "ohne Zuordnung")
"""The words that mark an Auffangposition in its label (Leitfaden A.10.4)."""
COMPLETENESS = "§ 246 Abs. 1 Satz 1 HGB"
NETTING_SOURCE = "§ 246 Abs. 2 Satz 1 HGB; § 387 BGB; § 226 Abs. 1 AO; § 16 Abs. 2 Satz 1 UStG"
_PURPOSES = MappingProxyType(
	{Purpose.COMMERCIAL: ("Handelsbilanz", "HB"), Purpose.TAX: ("Steuerbilanz", "SB")}
)


@dataclass(frozen=True, slots=True)
class PartyBalance:
	"""What one party owes or is owed on an account of type Receivable or Payable: its type and name, empty for postings
	without a party, debit and credit, and the key a Party Link gives a customer and a supplier that are one party."""

	party_type: str
	party: str
	debit: Decimal = ZERO
	credit: Decimal = ZERO
	linked: str = ""

	@property
	def amount(self) -> Decimal:
		return self.debit - self.credit


@dataclass(frozen=True, slots=True)
class AccountBalance:
	"""The balance of an account of the books: its name in ERPNext, its number, empty without one, its label, its
	part, and debit and credit in euros and cents; an account of type Receivable or Payable with its kind and the
	balance of each party, which add up to it."""

	account: str
	number: str
	label: str
	part: Part
	debit: Decimal = ZERO
	credit: Decimal = ZERO
	kind: AccountKind | None = None
	parties: tuple[PartyBalance, ...] = ()

	def __post_init__(self) -> None:
		for name in ("debit", "credit"):
			if not isinstance(getattr(self, name), Decimal):
				raise TypeError(f"the {name} of account {self.account} is a Decimal")
		object.__setattr__(self, "parties", tuple(self.parties))
		if self.parties and (
			sum((item.debit for item in self.parties), ZERO) != self.debit
			or sum((item.credit for item in self.parties), ZERO) != self.credit
		):
			raise ValueError(f"the parties of account {self.account} do not add up to its balance")

	@property
	def amount(self) -> Decimal:
		"""Debit minus credit."""
		return self.debit - self.credit


@dataclass(frozen=True, slots=True)
class Books:
	"""The balances of a fiscal year or of an Eröffnungsbilanz, and the result of earlier fiscal years that no Period
	Closing Voucher closed, as debit minus credit of the profit and loss accounts."""

	balances: tuple[AccountBalance, ...] = ()
	earlier_result: Decimal = ZERO

	def __post_init__(self) -> None:
		object.__setattr__(self, "balances", tuple(self.balances))


class Severity(StrEnum):
	ERROR = "Fehler"
	HINT = "Hinweis"


class Code(StrEnum):
	UNPLACED = "BILANZ-OHNE-PLATZ"
	NO_NUMBER = "BILANZ-OHNE-KONTONUMMER"
	WATCHED = "BILANZ-BEOBACHTET"
	EXCLUDED = "BILANZ-AUSSERHALB"
	PURPOSE = "BILANZ-ABSCHLUSSZWECK"
	POSITION = "BILANZ-POSITION"
	NOT_VALID = "BILANZ-NICHT-GUELTIG"
	CATCH_ALL = "BILANZ-AUFFANGPOSITION"
	EARLIER_RESULT = "BILANZ-ERGEBNISVORTRAG"
	NO_CLOSING_ACCOUNT = "BILANZ-ABSCHLUSSKONTO"
	TAXONOMY = "BILANZ-TAXONOMIE"
	NETTED = "BILANZ-VERRECHNUNG"
	RECLASSIFIED = "BILANZ-UMGLIEDERUNG"
	NO_PARTY = "BILANZ-OHNE-PARTEI"
	PARTY_SET_OFF = "BILANZ-PARTEI-VERRECHNET"
	CURRENCY_NETTED = "BILANZ-WAEHRUNG-SALDIERT"


@dataclass(frozen=True, slots=True)
class Finding:
	"""What placing the balances found: a German sentence with its source, and the account (its number, or its name
	without one), the position and the balance it is about."""

	code: Code
	severity: Severity
	text: str
	source: str
	account: str = ""
	concept: str = ""
	amount: Decimal | None = None

	@property
	def blocking(self) -> bool:
		return self.severity is Severity.ERROR


@dataclass(frozen=True, slots=True)
class Placed:
	"""A balance on its position: ``concept`` is the position the rule gives it, ``position`` the one its value counts
	in, the same but for a „davon“ position, and ``value`` the balance in the direction of ``position``."""

	balance: AccountBalance
	rule: Rule
	concept: str
	position: str
	value: Decimal
	reclassified: bool = False
	"""Whether the balance is the part of the parties of the account on the other side of its position."""

	@property
	def amount(self) -> Decimal:
		return self.balance.amount


@dataclass(frozen=True, slots=True)
class Placement:
	"""The balances on their positions, those left out of the balance sheet, and what holds it back or wants a
	look."""

	placed: tuple[Placed, ...]
	left_out: tuple[AccountBalance, ...]
	findings: tuple[Finding, ...]

	@property
	def ready(self) -> bool:
		"""Whether no finding holds the documents back."""
		return not any(finding.blocking for finding in self.findings)


def place(
	mapping: Mapping,
	books: Books,
	taxonomy: Taxonomy,
	purpose: Purpose,
	*,
	closing_account: str | None = None,
	fiscal_year: tuple[date, date] | None = None,
	reclassification: ReadOnlyMapping[AccountKind, str] = RECLASSIFICATION,
) -> Placement:
	"""The balances of the books on their positions in the balance sheet of the purpose, with the earlier result on the
	closing account and, given the fiscal year, only positions valid in it; the parties of an account of type
	Receivable or Payable each on the side of their balance, those whose rule names no position for the opposite
	balance on the one ``reclassification`` gives their kind."""
	findings: list[Finding] = []
	if taxonomy.version != mapping.taxonomy_version:
		findings.append(
			Finding(
				Code.TAXONOMY,
				Severity.ERROR,
				f"Die Bilanzzuordnung nennt die Positionen der HGB-Taxonomie {mapping.taxonomy_version}, der Beleg "
				f"rechnet mit der Taxonomie {taxonomy.version}.",
				"§ 5b Abs. 1 Satz 1 EStG",
			)
		)
	balances = _with_earlier_result(books, closing_account, findings)
	groups = _group_balances(mapping, balances, taxonomy, purpose)
	linked = _linked_parties(mapping, balances, taxonomy, purpose, reclassification)
	placed: list[Placed] = []
	left_out: list[AccountBalance] = []
	for balance in balances:
		if not balance.amount and not any(item.amount for item in balance.parties):
			continue
		found = list(_findings_of(mapping, balance, taxonomy, purpose, fiscal_year, groups))
		findings.extend(found)
		if _left_out(found):
			left_out.append(balance)
			continue
		rule = mapping.place_of(balance.number)
		if balance.parties and rule.netting is None:
			parts = _party_parts(rule, balance, taxonomy, linked, reclassification)
			placed.extend(part for part, _count in parts)
			findings.extend(_party_findings(balance, parts))
		else:
			placed.append(_placed(mapping, balance, taxonomy, groups))
	findings.extend(_netted(placed))
	findings.extend(_currency_netted(placed))
	findings.extend(_set_off(linked))
	return Placement(tuple(placed), tuple(left_out), tuple(findings))


def _group_balances(
	mapping: Mapping, balances: Iterable[AccountBalance], taxonomy: Taxonomy, purpose: Purpose
) -> dict[str, Decimal]:
	"""The combined balance of each netting group, of the accounts that count in the balance sheet of the purpose and
	whose rule names positions it may."""
	groups: dict[str, Decimal] = {}
	for balance in balances:
		rule = mapping.place_of(balance.number) if balance.number else None
		if (
			isinstance(rule, Rule)
			and rule.netting is not None
			and rule.counts_for(purpose)
			and not rule_problems(rule, taxonomy, balance.part)
		):
			groups[rule.netting] = groups.get(rule.netting, ZERO) + balance.amount
	return groups


@dataclass(frozen=True, slots=True)
class _Link:
	"""A customer and a supplier that are one party: the position of the side of their net balance."""

	concept: str
	amount: Decimal
	parties: tuple[str, ...]
	count: int


def _party_concept(
	rule: Rule, amount: Decimal, kind: AccountKind | None, taxonomy: Taxonomy, reclassification
) -> str:
	"""The position of a party on the side of its own balance: that of the rule, its position for the opposite balance,
	or the one of the kind of the account."""
	opposite = rule.opposite or reclassification.get(kind)
	return _concept_for(replace(rule, opposite=opposite), amount, taxonomy)


def _linked_parties(
	mapping: Mapping,
	balances: Iterable[AccountBalance],
	taxonomy: Taxonomy,
	purpose: Purpose,
	reclassification: ReadOnlyMapping[AccountKind, str],
) -> dict[str, _Link]:
	"""For each key of a Party Link, the net balance of its parties on every account that counts and the position of
	the side of it: that of the part on the same side, the first one where they are even."""
	parts: dict[str, list[tuple[Rule, AccountBalance, PartyBalance]]] = {}
	for balance in balances:
		rule = mapping.place_of(balance.number) if balance.number else None
		if not (
			isinstance(rule, Rule)
			and rule.netting is None
			and rule.counts_for(purpose)
			and not rule_problems(rule, taxonomy, balance.part)
		):
			continue
		for item in balance.parties:
			if item.linked and item.amount:
				parts.setdefault(item.linked, []).append((rule, balance, item))
	links: dict[str, _Link] = {}
	for key, found in parts.items():
		net = sum((item.amount for _, _, item in found), ZERO)
		rule, balance, item = next(
			(part for part in found if (part[2].amount > 0) == (net > 0) and net), found[0]
		)
		concept = _party_concept(rule, item.amount, balance.kind, taxonomy, reclassification)
		links[key] = _Link(concept, net, tuple(dict.fromkeys(part[2].party for part in found)), len(found))
	return links


def _party_parts(
	rule: Rule,
	balance: AccountBalance,
	taxonomy: Taxonomy,
	linked: ReadOnlyMapping[str, _Link],
	reclassification: ReadOnlyMapping[AccountKind, str],
) -> list[tuple[Placed, int]]:
	"""The parties of the account on their positions, the parts of one position summed up to one balance, each with the
	number of named parties in it."""
	sums: dict[str, tuple[Decimal, Decimal]] = {}
	counts: dict[str, int] = {}
	for item in balance.parties:
		if not item.amount:
			continue
		link = linked.get(item.linked) if item.linked else None
		concept = (
			link.concept
			if link
			else _party_concept(rule, item.amount, balance.kind, taxonomy, reclassification)
		)
		debit, credit = sums.get(concept, (ZERO, ZERO))
		sums[concept] = (debit + item.debit, credit + item.credit)
		counts[concept] = counts.get(concept, 0) + int(bool(item.party))
	parts = []
	for concept, (debit, credit) in sums.items():
		part = replace(balance, debit=debit, credit=credit, parties=())
		position = position_of(taxonomy, concept)
		value = _value(taxonomy, position, part.amount)
		parts.append((Placed(part, rule, concept, position, value, concept != rule.concept), counts[concept]))
	return parts


def _party_findings(balance: AccountBalance, parts: Iterable[tuple[Placed, int]]) -> Iterator[Finding]:
	"""A hint for the parties of the account on the other side of its position, and one for postings without a
	party."""
	name = _named(balance)
	for part, count in parts:
		if not (part.reclassified and count):
			continue
		parties = "1 Partei" if count == 1 else f"{count} Parteien"
		yield Finding(
			Code.RECLASSIFIED,
			Severity.HINT,
			f"{name}: {parties} mit einem Saldo auf der Gegenseite, zusammen {euro(abs(part.amount))}, stehen unter "
			f"{part.concept}: Forderungen und Verbindlichkeiten verschiedener Parteien werden nicht verrechnet.",
			"§ 246 Abs. 2 Satz 1 HGB",
			balance.number,
			part.concept,
			part.amount,
		)
	without = sum((item.amount for item in balance.parties if not item.party), ZERO)
	if without:
		yield Finding(
			Code.NO_PARTY,
			Severity.HINT,
			f"{name} hat Buchungen ohne Partei über {euro(abs(without))}: Sie zählen für sich nach ihrem Saldo. "
			"Ordnen Sie sie einer Partei zu, wenn sie zu einem Kunden oder Lieferanten gehören.",
			"§ 246 Abs. 2 Satz 1 HGB",
			balance.number,
			amount=without,
		)


def _set_off(linked: ReadOnlyMapping[str, _Link]) -> Iterator[Finding]:
	"""A hint for each customer and supplier that ERPNext links as one party and that are set off."""
	for key, link in linked.items():
		if link.count < 2:
			continue
		yield Finding(
			Code.PARTY_SET_OFF,
			Severity.HINT,
			f"Kunde und Lieferant „{key}“ sind in ERPNext als eine Partei verknüpft ({', '.join(link.parties)}); "
			f"Forderung und Verbindlichkeit sind verrechnet und stehen mit {euro(abs(link.amount))} unter "
			f"{link.concept}.",
			"§ 387 BGB; § 246 Abs. 2 Satz 1 HGB",
			key,
			link.concept,
			link.amount,
		)


def _netted(placed: Iterable[Placed]) -> Iterator[Finding]:
	"""A hint for each netting group of more than one account with a balance: what it nets, to what and where."""
	members: dict[str, list[Placed]] = {}
	for item in placed:
		if item.rule.netting is not None:
			members.setdefault(item.rule.netting, []).append(item)
	for group, items in members.items():
		if len(items) < 2:
			continue
		total = sum((item.amount for item in items), ZERO)
		concept = items[0].concept
		side = "Aktivseite" if total >= 0 else "Passivseite"
		numbers = ", ".join(item.balance.number for item in items)
		yield Finding(
			Code.NETTED,
			Severity.HINT,
			f"Die Konten der Verrechnungsgruppe „{group}“ ({numbers}) stehen verrechnet mit {euro(abs(total))} auf "
			f"der {side} ({concept}): Forderungen und Verbindlichkeiten gegenüber demselben Gläubiger, die "
			"gegeneinander aufgerechnet werden können, bilden eine Position. Lassen Sie die Gruppe von der "
			"Steuerberatung bestätigen.",
			NETTING_SOURCE,
			group,
			concept,
			total,
		)


CURRENCY_POSITIONS = (
	"is.netIncome.regular.operatingTC.otherCost.currLoss",
	"is.netIncome.regular.operatingTC.otherOpRevenue.currGains",
)
"""The positions of the Erträge and Aufwendungen aus der Währungsumrechnung, which the GuV shows apart (§ 277 Abs. 5
Satz 2 HGB) and § 246 Abs. 2 Satz 1 HGB does not let net."""


def _currency_netted(placed: Iterable[Placed]) -> Iterator[Finding]:
	"""A hint for each account of the currency translation that books gains and losses in the year and so shows only
	their balance, as the Wechselkursneubewertung of ERPNext does on one account."""
	for item in placed:
		balance = item.balance
		if (
			balance.part is Part.INCOME_STATEMENT
			and item.concept.rpartition(":")[2] in CURRENCY_POSITIONS
			and balance.debit > ZERO
			and balance.credit > ZERO
		):
			yield Finding(
				Code.CURRENCY_NETTED,
				Severity.HINT,
				f"Konto {balance.number} bucht im Jahr Erträge und Aufwendungen aus der Währungsumrechnung (Haben "
				f"{euro(balance.credit)}, Soll {euro(balance.debit)}) und zeigt nur ihren Saldo von "
				f"{euro(abs(balance.amount))}. Die GuV weist beide gesondert aus (§ 277 Abs. 5 Satz 2 HGB), verrechnet "
				"werden dürfen sie nicht (§ 246 Abs. 2 Satz 1 HGB): Buchen Sie Erträge und Aufwendungen aus der "
				"Währungsumrechnung auf getrennte Konten, auch wo die Wechselkursneubewertung von ERPNext beide auf ein "
				"Konto bucht: Buchen Sie dann die Erträge vor dem Abschluss auf das Konto der Erträge um. Welche Konten "
				"ERPNext dafür nimmt, sagt der Schritt „Konten der Wechselkursdifferenzen“ von „Steuerbote einrichten“.",
				"§ 277 Abs. 5 Satz 2, § 246 Abs. 2 Satz 1 HGB",
				balance.number,
				item.concept,
				balance.amount,
			)


def euro(value: Decimal) -> str:
	"""An amount as a German text writes it, such as 1.234,56 €."""
	return f"{value:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".") + " €"


def catch_all(taxonomy: Taxonomy, concept: str) -> bool:
	"""Whether the position is an Auffangposition by the words of its label (Leitfaden A.10.4)."""
	label = taxonomy.label(_qualified(concept), LABEL)
	return any(words in label for words in CATCH_ALL_WORDS)


def position_of(taxonomy: Taxonomy, concept: str) -> str:
	"""The position the value of a position counts in: itself where a calculation of its part holds it, else the
	nearest above it in the presentation that one holds."""
	part = part_of(taxonomy, concept)
	name = _qualified(concept)
	calculation = taxonomy.calculation.get(part.role) if part is not None else None
	if calculation is None or name in calculation:
		return _unqualified(name)
	above = taxonomy.presentation[part.role].ancestors(name)
	return _unqualified(next((ancestor for ancestor in above if ancestor in calculation), name))


def _with_earlier_result(
	books: Books, closing_account: str | None, findings: list[Finding]
) -> tuple[AccountBalance, ...]:
	result = books.earlier_result
	if not result:
		return books.balances
	if closing_account is None:
		findings.append(
			Finding(
				Code.NO_CLOSING_ACCOUNT,
				Severity.ERROR,
				"Das Ergebnis früherer Geschäftsjahre schließt kein Periodenabschlussbeleg ab, und kein Abschlusskonto "
				"nimmt es auf: Buchen Sie den Periodenabschlussbeleg, oder bestimmen Sie das Abschlusskonto in den "
				"Einstellungen Jahresmeldungen.",
				"§ 266 Abs. 3 A. IV. HGB",
				amount=result,
			)
		)
		return books.balances
	kind = "Verlust" if result > 0 else "Gewinn"
	findings.append(
		Finding(
			Code.EARLIER_RESULT,
			Severity.HINT,
			f"Den {kind} früherer Geschäftsjahre schließt kein Periodenabschlussbeleg ab; Steuerbote rechnet ihn wie "
			f"ein Periodenabschlussbeleg dem Abschlusskonto {closing_account} zu.",
			"§ 266 Abs. 3 A. IV. HGB",
			closing_account,
			amount=result,
		)
	)
	debit, credit = (result, ZERO) if result > 0 else (ZERO, -result)
	balances = list(books.balances)
	for index, balance in enumerate(balances):
		if balance.number == closing_account:
			balances[index] = replace(balance, debit=balance.debit + debit, credit=balance.credit + credit)
			return tuple(balances)
	closing = AccountBalance(closing_account, closing_account, "", Part.BALANCE_SHEET, debit, credit)
	return (*balances, closing)


def _findings_of(
	mapping: Mapping,
	balance: AccountBalance,
	taxonomy: Taxonomy,
	purpose: Purpose,
	fiscal_year: tuple[date, date] | None,
	groups: ReadOnlyMapping[str, Decimal],
) -> Iterator[Finding]:
	"""What the balance of an account wants: why it goes to no position, or what to look at where it goes."""
	name, amount = _named(balance), balance.amount
	if not balance.number:
		yield Finding(
			Code.NO_NUMBER,
			Severity.ERROR,
			f"Das Konto {balance.account} hat einen Saldo, aber keine Kontonummer, unter der die Bilanzzuordnung es "
			"nennen könnte: Geben Sie ihm eine.",
			COMPLETENESS,
			balance.account,
			amount=amount,
		)
		return
	number = balance.number
	place = mapping.place_of(number)
	match place:
		case None:
			yield Finding(
				Code.UNPLACED,
				Severity.ERROR,
				f"{name} hat einen Saldo, aber keinen Platz in der Bilanzzuordnung: Ordnen Sie es einer Position zu, "
				"oder sagen Sie, warum es außerhalb von Bilanz und GuV liegt. Die Vorgaben geben Konten, die der "
				"Kontenrahmen nicht beschriftet, keinen Platz; die Steuerberatung entscheidet ihn. „Konten prüfen“ in "
				"der Bilanzzuordnung nennt alle Konten ohne Platz.",
				COMPLETENESS,
				number,
				amount=amount,
			)
		case Watched(level=WatchLevel.BLOCKING):
			yield Finding(
				Code.WATCHED,
				Severity.ERROR,
				f"{name} hat einen Saldo, aber die Bilanzzuordnung beobachtet es ohne Position: Ordnen Sie es einer "
				"Position zu.",
				COMPLETENESS,
				number,
				amount=amount,
			)
		case Watched():
			yield Finding(
				Code.WATCHED,
				Severity.HINT,
				f"{name} hat einen Saldo; die Bilanzzuordnung beobachtet es ohne Position, sein Saldo geht in keine "
				"Position ein.",
				COMPLETENESS,
				number,
				amount=amount,
			)
		case Excluded(reason=reason):
			yield Finding(
				Code.EXCLUDED,
				Severity.HINT,
				f"{name} hat einen Saldo, liegt aber außerhalb von Bilanz und GuV ({reason}); sein Saldo geht in "
				"keine Position ein.",
				COMPLETENESS,
				number,
				amount=amount,
			)
		case Rule() if not place.counts_for(purpose):
			statement, mark = _PURPOSES[place.purpose]
			yield Finding(
				Code.PURPOSE,
				Severity.HINT,
				f"{name} ist nur für die {statement} gebucht (Abschlusszweck {mark}) und geht nicht in diese Bilanz "
				"ein.",
				"DATEV-Kontenrahmen SKR 03 und SKR 04, Fußnote 4",
				number,
				place.concept,
				amount,
			)
		case _:
			yield from _rule_findings(
				place, balance, taxonomy, fiscal_year, _side_amount(place, balance, groups)
			)


def _rule_findings(
	rule: Rule,
	balance: AccountBalance,
	taxonomy: Taxonomy,
	fiscal_year: tuple[date, date] | None,
	side_amount: Decimal,
) -> Iterator[Finding]:
	name, amount = _named(balance), balance.amount
	problems = rule_problems(rule, taxonomy, balance.part)
	for problem in problems:
		yield Finding(
			Code.POSITION,
			Severity.ERROR,
			problem.text,
			problem.source,
			balance.number,
			str(problem.values[1]),
			amount,
		)
	if problems:
		return
	concept = _concept_for(rule, side_amount, taxonomy)
	if fiscal_year is not None and not taxonomy.concept(concept).valid_for(*fiscal_year):
		begin, end = fiscal_year
		yield Finding(
			Code.NOT_VALID,
			Severity.ERROR,
			f"{name} geht in die Position {concept}, die im Wirtschaftsjahr vom {begin:%d.%m.%Y} bis "
			f"{end:%d.%m.%Y} nicht übermittelt werden darf.",
			"Technischer Leitfaden zur HGB-Taxonomie 6.9, B.11, B.14.4.1",
			balance.number,
			concept,
			amount,
		)
	if catch_all(taxonomy, concept):
		yield Finding(
			Code.CATCH_ALL,
			Severity.HINT,
			f"{name} geht in die Auffangposition „{taxonomy.label(_qualified(concept))}“ ({concept}): Prüfen Sie, ob "
			"die Buchführung eine genauere Position hergibt.",
			"Technischer Leitfaden zur HGB-Taxonomie 6.9, A.10.4",
			balance.number,
			concept,
			amount,
		)


def _left_out(found: Iterable[Finding]) -> bool:
	"""Whether the findings of a balance keep it from its position: every one but the hint on an Auffangposition."""
	return any(finding.code is not Code.CATCH_ALL for finding in found)


def _placed(
	mapping: Mapping, balance: AccountBalance, taxonomy: Taxonomy, groups: ReadOnlyMapping[str, Decimal]
) -> Placed:
	rule = mapping.place_of(balance.number)
	concept = _concept_for(rule, _side_amount(rule, balance, groups), taxonomy)
	position = position_of(taxonomy, concept)
	return Placed(balance, rule, concept, position, _value(taxonomy, position, balance.amount))


def _side_amount(rule: Rule, balance: AccountBalance, groups: ReadOnlyMapping[str, Decimal]) -> Decimal:
	"""The balance that decides the side of an account: that of its netting group, else its own."""
	return groups.get(rule.netting, balance.amount) if rule.netting is not None else balance.amount


def _concept_for(rule: Rule, amount: Decimal, taxonomy: Taxonomy) -> str:
	"""The position a balance goes to: the opposite position for one on the other side of the rule's position. A
	balanced netting group goes to the debit side, where its accounts add up to nothing."""
	side = taxonomy.concept(rule.concept).balance
	other_side = (amount < 0) if side is Balance.DEBIT else (amount >= 0 if rule.netting else amount > 0)
	return rule.opposite if rule.opposite is not None and other_side else rule.concept


def _value(taxonomy: Taxonomy, concept: str, amount: Decimal) -> Decimal:
	return amount if taxonomy.concept(concept).balance is Balance.DEBIT else -amount


def _named(balance: AccountBalance) -> str:
	return " ".join(part for part in ("Konto", balance.number, balance.label) if part)


def _unqualified(name: str) -> str:
	return name.removeprefix(f"{GAAP_PREFIX}:")


_ACCOUNT_DIGITS = re.compile(r"[0-9]+")


@dataclass(frozen=True, slots=True)
class Accounts:
	"""An account of a chart, or a range of them from first to last, both included and of the same number of
	digits."""

	first: str
	last: str

	def __post_init__(self) -> None:
		first, last = self.first, self.last
		if not (
			isinstance(first, str)
			and isinstance(last, str)
			and _ACCOUNT_DIGITS.fullmatch(first)
			and _ACCOUNT_DIGITS.fullmatch(last)
			and len(first) == len(last)
			and first <= last
		):
			raise ValueError(f"{first}-{last} is no range of account numbers of the same length")

	@classmethod
	def of(cls, text: str) -> Accounts:
		"""The accounts of a text such as 1800 or 1800-1849."""
		first, separator, last = str(text).partition("-")
		return cls(first, last if separator else first)

	def __contains__(self, number: object) -> bool:
		return (
			isinstance(number, str) and len(number) == len(self.first) and self.first <= number <= self.last
		)

	def __str__(self) -> str:
		return self.first if self.first == self.last else f"{self.first}-{self.last}"


@dataclass(frozen=True, slots=True)
class DefaultRule:
	"""A rule of the defaults for an account or a range: the fields of Rule but the account number."""

	accounts: Accounts
	concept: str
	opposite: str | None = None
	purpose: Purpose = Purpose.BOTH
	shareholder: bool = False
	remaining_term: RemainingTerm | None = None
	netting: str | None = None

	def __post_init__(self) -> None:
		accounts = _accounts(self.accounts)
		object.__setattr__(self, "accounts", accounts)
		rule = self.rule(accounts.first)
		for name in ("concept", "opposite", "purpose", "remaining_term", "netting"):
			object.__setattr__(self, name, getattr(rule, name))

	def rule(self, number: str) -> Rule:
		return Rule(
			number,
			self.concept,
			self.opposite,
			self.purpose,
			self.shareholder,
			self.remaining_term,
			self.netting,
		)


@dataclass(frozen=True, slots=True)
class DefaultWatched:
	"""A watched account of the defaults, or a range of them."""

	accounts: Accounts
	level: WatchLevel = WatchLevel.BLOCKING

	def __post_init__(self) -> None:
		accounts = _accounts(self.accounts)
		object.__setattr__(self, "accounts", accounts)
		object.__setattr__(self, "level", Watched(accounts.first, self.level).level)


@dataclass(frozen=True, slots=True)
class DefaultExcluded:
	"""An account of the defaults outside the Bilanz and the GuV, or a range of them, with the reason."""

	accounts: Accounts
	reason: str

	def __post_init__(self) -> None:
		accounts = _accounts(self.accounts)
		object.__setattr__(self, "accounts", accounts)
		object.__setattr__(self, "reason", Excluded(accounts.first, self.reason).reason)


type DefaultEntry = DefaultRule | DefaultWatched | DefaultExcluded


@dataclass(frozen=True, slots=True)
class Defaults:
	"""The default mapping of a chart for a version of the taxonomy, by account and range."""

	chart: str
	taxonomy_version: str
	rules: tuple[DefaultRule, ...] = ()
	watched: tuple[DefaultWatched, ...] = ()
	excluded: tuple[DefaultExcluded, ...] = ()

	def __post_init__(self) -> None:
		if self.taxonomy_version not in TAXONOMIES:
			raise MappingError(UNKNOWN_VERSION, self.taxonomy_version)
		object.__setattr__(self, "rules", tuple(self.rules))
		object.__setattr__(self, "watched", tuple(self.watched))
		object.__setattr__(self, "excluded", tuple(self.excluded))
		entries = self._entries()
		for index, entry in enumerate(entries):
			for other in entries[index + 1 :]:
				if _overlap(entry.accounts, other.accounts):
					raise ValueError(
						f"the defaults of {self.chart} for {self.taxonomy_version} give the accounts {entry.accounts} "
						f"and {other.accounts} two places"
					)

	def _entries(self) -> tuple[DefaultEntry, ...]:
		return (*self.rules, *self.watched, *self.excluded)

	def entry_for(self, number: str) -> DefaultEntry | None:
		return next((entry for entry in self._entries() if number in entry.accounts), None)

	def covers(self, number: str) -> bool:
		return self.entry_for(number) is not None

	def uncovered(self, numbers: Iterable[str]) -> tuple[str, ...]:
		"""The accounts no entry holds, sorted."""
		return tuple(sorted(number for number in set(numbers) if not self.covers(number)))

	def for_accounts(
		self, numbers: Iterable[str], levels: ReadOnlyMapping[str, WatchLevel | str] = MappingProxyType({})
	) -> Mapping:
		"""The mapping the defaults give a company with these accounts, each account in the place of the entry that
		holds it and in the order of the numbers; a watched account keeps the level the company gave it in ``levels``."""
		rules: list[Rule] = []
		watched: list[Watched] = []
		excluded: list[Excluded] = []
		for number in sorted(set(numbers)):
			match self.entry_for(number):
				case DefaultRule() as entry:
					rules.append(entry.rule(number))
				case DefaultWatched() as entry:
					watched.append(Watched(number, levels.get(number) or entry.level))
				case DefaultExcluded() as entry:
					excluded.append(Excluded(number, entry.reason))
		return Mapping(self.chart, tuple(rules), tuple(watched), tuple(excluded), self.taxonomy_version)

	def rows(self) -> dict[str, list[dict]]:
		"""The entries as plain data, by kind and in their order, for the digest that pins a version of them; a rule
		names its netting group only where it has one, so that the digest of defaults without one stays as it was."""
		return {
			"rules": [
				{
					"accounts": str(rule.accounts),
					"concept": rule.concept,
					"opposite": rule.opposite,
					"purpose": rule.purpose.value,
					"shareholder": rule.shareholder,
					"remaining_term": rule.rule(rule.accounts.first).term_value,
					**({"netting": rule.netting} if rule.netting else {}),
				}
				for rule in self.rules
			],
			"watched": [
				{"accounts": str(entry.accounts), "level": entry.level.value} for entry in self.watched
			],
			"excluded": [
				{"accounts": str(entry.accounts), "reason": entry.reason} for entry in self.excluded
			],
		}


def _accounts(value: Accounts | str) -> Accounts:
	return value if isinstance(value, Accounts) else Accounts.of(value)


def _overlap(one: Accounts, other: Accounts) -> bool:
	return len(one.first) == len(other.first) and one.first <= other.last and other.first <= one.last
