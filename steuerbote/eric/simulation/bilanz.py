"""The simulation of the E-Bilanz, Datenart Bilanz: the frame of ebilanz_000002.xsd around the XBRL instance, the rules
of the Jahresdokumentation in RULES and, with the taxonomy, the Mussfelder and the calculation linkbase.

Sources are the ERiC documentation 44.3.6.0: Datenarten/ElsterBilanz/Bilanz/Schema/ebilanz_000002.xsd, whose EBilanz
holds the stichtag „im Format YYYYMMTT“ and then xbrli:xbrl and has the attribute version, an integer from 1 to 2;
Jahresdokumentation_Bilanz_Taxonomie_6_9.ods, whose stichtag is a „Datum JJJJMMTT mit Zusatzprüfung“ (sheet „Header -
Felder“) and whose sheet „Kontext - Regeln“ lists the rules ERiC checks an E-Bilanz with, cited by their Fehlercode;
the ERiC-Entwicklerhandbuch, Tabelle 9-20: ERiC checks no schema of the Nutzdaten of the Datenart Bilanz,
„Nutzdatenschemavalidierung: Nein“, so the simulation does not either; and the Technischer Leitfaden zur
HGB-Taxonomie 6.9, Stand 10.06.2025 („Leitfaden“).

Instance. The rules read the instance as the Prüfbedingungen name its positions, [gcd:…] one of the GCD and [gaap:…]
one of the GAAP module, by their local names: an item of the GAAP module in a context of the current year without a
scenario, an item or a tuple of the GCD wherever it stands. A position is given, „FeldAngegeben“, when it holds a
value other than NIL, a tuple when one of its items does; a choice is the value it reports, such as statementType.E.
The amounts of a Handelsbilanz are those of the Steuerbilanz after the Überleitung: „Nach der Verarbeitung der
Überleitungsrechnung muss sich eine Steuerbilanz errechnet haben, die selbst den Anforderungen an eine übermittelte
Steuerbilanz genügt“ (Leitfaden B.15.1), each position with the Wertänderungen of the entries that name it; rule
170405071 checks the Handelsbilanz before it. A position the rule computes with and the instance does not give counts
as zero: „Nicht (werthaltig) berichtete Positionen werden beim rechnerischen Abgleich so behandelt, als seien sie mit
dem Wert 0 versehen“ (rules 170405109 and 170405114).

RULES. The rules of „Kontext - Regeln“ of the Regelart Fehler on the GCD, the components and the amounts that apply to
an E-Bilanz of the Kerntaxonomie, each reported with its Fehlercode, as ERiC reports it:

- the GCD: Berichtsstatus, Konsolidierungsumfang, Ausweis des Bilanzgewinns, Bilanzstichtag, Beginn and Ende des
  Wirtschaftsjahres, Name and Firmensitz, Einkunftsart (170205045 to 170205053, 170205070, 170205071, 170405036), the
  Steuernummer or for an Eröffnungsbilanz the Bundesfinanzamtsnummer (170205025, 170205026), the Finanzamt of the
  NutzdatenHeader (170205001), the stichtag of the frame (170205022) and the Bilanzstichtag by the Bilanzart
  (170205072, 170205081), and the fiscal years of the version of the taxonomy (170205007, 170205017, 170205018);
- the components by the Bilanzart (170205090, 170205091, 170405021, 170205021, 170405101, 170205028), the
  Betriebsvermögensvergleich with every GuV (170205066), the Kontensalden or the reason without them (170405002), and
  the Überleitung of a Handelsbilanz only (170205095, 170205100);
- the amounts: Summe Aktiva and Summe Passiva given and equal (170205011, 170205012, 170205010), the Jahresüberschuss of
  the GuV as that of the Bilanz with the steuerlicher Ausgleichsposten for a GmbH or UG without a Bilanzgewinn after and
  before the Überleitung (170405070, 170405071), the Jahresüberschuss and the Betriebsvermögen of the
  Betriebsvermögensvergleich (170405109, 170405114), and no Anlagenspiegel in its Kurzform (170405047).

The texts of the messages are Steuerbote's: the Jahresdokumentation carries no licence that allows passing it on
(steuerbote/eric/simulation/kst.py). expected_rules() names the terms of each Prüfbedingung a rule reads, which the
year check compares with the Jahresdokumentation of the version (steuerbote/jahresmeldung/yearcheck.py,
BILANZ_EXPECTING). The Anlagenspiegel is due for every fiscal year that begins after 31 December 2016 (Leitfaden
B.14.12.1; BMF letters of 24 May 2016 and of 10 June 2025), but the Jahresdokumentation 6.9 marks its rule 170405045
deleted, so ERiC 44.3.6.0 does not check it: the simulation reports an instance without it as SIM-011.

Taxonomy. With the fiscal view of the version registered (register_taxonomy(), with the package the operator
installed), the simulation reads the instance into the facts of steuerbote/xbrl/facts.py and checks the Mussfelder of
the legal form and the components (steuerbote.xbrl.checks.mussfelder(), Leitfaden B.14.2) and the calculation linkbase
(checks.calculation(), B.14.11), which the plugin of ERiC checks; a value or member that names a concept does so by the
prefixes of the taxonomy, as steuerbote/xbrl/writer.py writes them. Without the taxonomy SIM-001 says that these
checks were left out. steuerbote.xbrl needs lxml, which the simulation runs without (steuerbote/eric/fake.py), so it is
imported only for a registered taxonomy.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING
from xml.etree import ElementTree

from steuerbote.eric.datenart import Datenart
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import ERROR, Message
from steuerbote.eric.simulation import Checks, Structure
from steuerbote.kst.years import RuleExpectation
from steuerbote.xbrl.versions import UnknownTaxonomyError, Version, version_of

if TYPE_CHECKING:
	from steuerbote.xbrl.facts import Report
	from steuerbote.xbrl.taxonomy import Taxonomy

XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRL = f"{XBRLI}xbrl"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"
NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
LINK = "{http://www.xbrl.org/2003/linkbase}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
TAXONOMY_URL = "http://www.xbrl.de/taxonomies/"
GCD_MODULE = "de-gcd-"
GAAP_MODULE = "de-gaap-ci-"
VERSIONS = range(1, 3)
"""The versions of the interface ebilanz_000002.xsd takes."""
STICHTAG_FORMAT = "%Y%m%d"
SHEET = "Kontext"
"""The Vordruck of the rules, sheet „Kontext - Regeln“."""
ANLAGENSPIEGEL = "SIM-011"
DUE_SINCE = date(2016, 12, 31)
"""The Anlagenspiegel is due for every fiscal year that begins after this day (Leitfaden B.14.12.1)."""
TAXONOMY_CHECK = "SIM-012"
KONTENSALDEN_SINCE = date(2024, 12, 31)
"""The Kontensalden are due for every fiscal year beginning after this day: „Nach § 5b EStG ist für Wirtschaftsjahre,
die nach dem 31. Dezember 2024 beginnen, der Kontennachweis zur Bilanz und GuV verpflichtend zu übermitteln.“
(Technischer Leitfaden zur HGB-Taxonomie 6.10, Stand 08.06.2026, B.12.1), which rule 170405002 of 6.10 checks: „Der
Berichtsbestandteil "Kontensalden" muss angekündigt werden, wenn der Beginn des Wirtschaftsjahres nach dem 31.12.2024
liegt.“"""


REPORT_ELEMENT = "genInfo.report.id.reportElement"
STATEMENT_TYPE = "genInfo.report.id.statementType"
STATEMENT_TYPE_TAX = "genInfo.report.id.statementType.tax"
ACCOUNTING_STANDARD = "genInfo.report.id.accountingStandard"
LEGAL_STATUS = "genInfo.company.id.legalStatus"
TRANSMISSION_OPTION = "genInfo.company.id.transmissionOptionofCorpWithSpecialCaseProfitDetermination"
ENTITY_WITH_TAXABLE_PURPOSE = "genInfo.company.id.entityWithTaxablePurposeBusiness"
ID_NUMBERS = "genInfo.company.id.idNo"
ST13 = "genInfo.company.id.idNo.type.companyId.ST13"
BF4 = "genInfo.company.id.idNo.type.companyId.BF4"
BAL_PROFIT = "genInfo.report.id.incomeStatementendswithBalProfit"
NOT_YET_POSSIBLE = "genInfo.report.id.reportElement.reportElements.transmissionNotYetPossible"
FISCAL_YEAR_BEGIN = "genInfo.report.period.fiscalYearBegin"
FISCAL_YEAR_END = "genInfo.report.period.fiscalYearEnd"
CLOSING_DATE = "genInfo.report.period.balSheetClosingDate"
PREVIOUS_BEGIN = "genInfo.report.period.fiscalPreviousYearBegin"
PREVIOUS_END = "genInfo.report.period.fiscalPreviousYearEnd"
FIXED_ASSETS = "dim_changes.nt.ass.gross"
FIXED_ASSETS_SHORT = "dim_changes.nt.ass.gross_short"
ENTRIES = ("hbst.transfer.bsAss", "hbst.transfer.bsEqLiab", "hbst.transfer.isChangeNetIncome")
CHANGES = ("changeValueActualPeriod", "changeValuePreviousPeriod")

OPENING_STATEMENTS = frozenset({"statementType.EB", "statementType.LAB"})
"""Eröffnungsbilanz and Liquidationsanfangsbilanz, which have neither GuV nor Betriebsvermögensvergleich."""
WITHOUT_GUV = OPENING_STATEMENTS | {"statementType.AB", "statementType.UB"}
LIQUIDATION = frozenset({"statementType.LSB", "statementType.LZB"})
"""Liquidationsschluss- and Liquidationszwischenbilanz, whose fiscal year may begin before the version's."""
LATER_VERSION_TOLERATED = OPENING_STATEMENTS | {"statementType.UB", "statementType.UJ", "statementType.ZW"}
"""The Bilanzarten that may take the version of the year before (Leitfaden B.18)."""
SPECIAL_BALANCES = frozenset({"statementTypeTax.SB", "statementTypeTax.EB"})
"""Sonderbilanz and Ergänzungsbilanz of a partnership."""
SEPARATE_TABLES = frozenset(
	{
		"transmissionOptionofCorpWithSpecialCaseProfitDetermination.taxablePurposeBusinessTable",
		"transmissionOptionCorporateEntitySpecialCaseProfitDetermination.AdjustmentsWithoutUmbrellaBody",
	}
)
"""The variants of a Körperschaft with a wirtschaftlicher Geschäftsbetrieb without Bilanz and GuV of its own."""
SPECIAL_CASES = frozenset(
	{
		"entityWithTaxablePurposeBusiness.normal",
		"entityWithTaxablePurposeBusiness.taxPrivileged",
		"entityWithTaxablePurposeBusiness.publicLaw",
	}
)
STEUERBOTE_LEGAL_STATUS = frozenset({"legalStatus.GMBH", "legalStatus.UG"})
"""The legal forms Steuerbote files for, of the kind „KSt“ alone (Leitfaden B.4.1), for rules 170405070 and 170405071,
which apply to every such legal form and to the KGaA; the simulation names no other."""
STEUERBILANZ = frozenset({"accountingStandard.AO", "accountingStandard.HAOE"})
SPECIAL_ACCOUNTING_STANDARD = "genInfo.report.id.specialAccountingStandard"
OWN_BRANCHES = frozenset(
	{"specialAccountingStandard.RKV", "specialAccountingStandard.RZV", "specialAccountingStandard.RVV"}
)
"""RechKredV, RechZahlV and RechVersV, whose taxonomies have the totals of a Bilanz of their own: the branches
„Banken“, „Zahlungsinstitute“ and „Versicherungen“ of the Prüfbedingungen (Leitfaden B.14.3.1.13)."""
BRANCH = '[gcd:genInfo.report.id.specialAccountingStandard.mappedTo.branch]=="Keine"'

_TAXONOMIES: dict[str, Callable[[], Taxonomy]] = {}


def register_taxonomy(version: str, view: Callable[[], Taxonomy]) -> None:
	"""Let the simulation check the instances of a version, such as 6.9, against the fiscal view ``view()`` gives."""
	_TAXONOMIES[version] = view


def unregister_taxonomy(version: str) -> None:
	_TAXONOMIES.pop(version, None)


@dataclass(frozen=True)
class Instance:
	"""What the rules read of an E-Bilanz: its frame, its GCD, the amounts of the current year and the Überleitung."""

	stichtag: str
	"""The stichtag of the frame, JJJJMMTT."""
	gcd: tuple[ElementTree.Element, ...]
	"""Every element of the GCD module, outermost first."""
	amounts: Mapping[str, Decimal]
	"""The amounts of the GAAP module in the contexts of the current year without a scenario, by their local names."""
	changes: Mapping[str, Decimal]
	"""The Wertänderungen of the Überleitung by the position they name, of the current and of earlier years."""
	dimensions: frozenset[str]
	"""The local names of the dimensions of the contexts a valued fact refers to."""

	def elements(self, name: str) -> Iterator[ElementTree.Element]:
		return (element for element in self.gcd if _local(element) == name)

	def given(self, name: str) -> bool:
		"""FeldAngegeben: the position holds a value other than NIL, the tuple an item that does."""
		return any(_valued(element) for element in self.elements(name))

	def chosen(self, name: str) -> tuple[str, ...]:
		"""The values a choice reports, as the Prüfbedingungen name them by the last two parts of their names, such
		as statementType.E for genInfo.report.id.statementType.statementType.E."""
		return tuple(
			".".join(_local(child).split(".")[-2:])
			for element in self.elements(name)
			if element.get(NIL) != "true"
			for child in element
			if _valued(child)
		)

	def chooses(self, name: str, values: Iterable[str]) -> bool:
		return bool(set(self.chosen(name)) & set(values))

	def text(self, name: str) -> str:
		"""The value of a position of the GCD, empty for NIL or none."""
		return next(
			((element.text or "").strip() for element in self.elements(name) if element.get(NIL) != "true"),
			"",
		)

	def date(self, name: str) -> date | None:
		try:
			return date.fromisoformat(self.text(name))
		except ValueError:
			return None

	def company_number(self, name: str) -> str:
		"""ST13 or BF4 of the company itself, in genInfo.company.id.idNo."""
		return next(
			(
				(child.text or "").strip()
				for element in self.elements(ID_NUMBERS)
				for child in element
				if _local(child) == name and child.get(NIL) != "true"
			),
			"",
		)

	def announced(self, component: str) -> bool:
		return self.given(f"{REPORT_ELEMENT}.reportElements.{component}")

	@property
	def statement_type(self) -> str:
		return next(iter(self.chosen(STATEMENT_TYPE)), "")

	@property
	def special_balance(self) -> bool:
		return self.chooses(STATEMENT_TYPE_TAX, SPECIAL_BALANCES)

	@property
	def separate_tables(self) -> bool:
		return self.chooses(TRANSMISSION_OPTION, SEPARATE_TABLES)

	@property
	def balance_sheet_of_its_own(self) -> bool:
		"""Whether the Bilanz has totals of its own branch, of banks, payment institutions or insurers, which rules on
		the branches „Keine“ and „Sonstige“ leave aside."""
		return self.chooses(SPECIAL_ACCOUNTING_STANDARD, OWN_BRANCHES)

	def amount(self, name: str, *, transferred: bool = True) -> Decimal | None:
		"""The amount of a position, after the Überleitung unless ``transferred`` is False; None where neither the
		position nor an entry gives one."""
		own = self.amounts.get(name)
		change = self.changes.get(name) if transferred else None
		if own is None and change is None:
			return None
		return (own or Decimal(0)) + (change or Decimal(0))

	def zero(self, name: str, *, transferred: bool = True) -> Decimal:
		found = self.amount(name, transferred=transferred)
		return Decimal(0) if found is None else found

	def has(self, name: str) -> bool:
		return name in self.amounts


@dataclass(frozen=True, slots=True)
class BilanzRule:
	"""A rule of „Kontext - Regeln“: its Fehlercode and name, Steuerbote's text, the field it reports and when it
	strikes, with the terms of its Prüfbedingung."""

	code: str
	name: str
	text: str
	field: str
	strikes: Callable[[Instance, Datenart, EnvelopeHeader], bool]
	terms: Callable[[str], tuple[str, ...]]
	"""The terms of the Prüfbedingung, written without blanks, by the version of the taxonomy."""

	def __call__(self, root: ElementTree.Element, kind: Datenart, header: EnvelopeHeader) -> Message | None:
		if not self.strikes(read(root), kind, header):
			return None
		return Message(
			self.code,
			f"Die Regel {self.code} ({self.name}) der Jahresdokumentation Bilanz {kind.taxonomy} schlägt an: "
			f"{self.text}",
			ERROR,
			self.field,
		)

	def expectation(self, version: str) -> RuleExpectation:
		return RuleExpectation(self.code, SHEET, self.terms(version))


def _always(*terms: str) -> Callable[[str], tuple[str, ...]]:
	return lambda version: terms


def _not_given(name: str) -> str:
	return f"FeldNichtAngegeben(gcd:{name})"


def _gcd_rule(code: str, name: str, field: str, label: str, *, nil: bool = False) -> BilanzRule:
	"""A rule that the GCD gives a position: werthaltig, or for a date not NIL."""
	term = f"FeldAngegeben(gcd:{field}.NIL)" if nil else _not_given(field)
	return BilanzRule(
		code,
		name,
		f"„{label}“ fehlt im GCD.",
		field,
		lambda instance, kind, header: not instance.given(field),
		_always(term),
	)


def _version_window(kind: Datenart) -> Version | None:
	try:
		return version_of(kind.taxonomy)
	except UnknownTaxonomyError:
		return None


def _first_begin(version: str) -> date:
	"""The first day a fiscal year of the version may begin on."""
	return version_of(version).tolerated_begins_after + timedelta(days=1)


def _last_end(version: str, *, tolerated: bool = False) -> date:
	"""The last day a fiscal year of the version may end on, a year later for a Bilanzart that may take the version of
	the year before (Leitfaden B.18)."""
	last = version_of(version).last_ends_before
	return (last.replace(year=last.year + 1) if tolerated else last) - timedelta(days=1)


def _datum(day: date) -> str:
	return f'Datum("{day:%d}","{day:%m}","{day:%Y}")'


def _begins_too_early(instance: Instance, kind: Datenart, header: EnvelopeHeader) -> bool:
	begin = instance.date(FISCAL_YEAR_BEGIN)
	return (
		_version_window(kind) is not None
		and instance.statement_type not in LIQUIDATION
		and begin is not None
		and begin < _first_begin(kind.taxonomy)
	)


def _ends_too_late(tolerated: bool) -> Callable[[Instance, Datenart, EnvelopeHeader], bool]:
	def strikes(instance: Instance, kind: Datenart, header: EnvelopeHeader) -> bool:
		end = instance.date(FISCAL_YEAR_END)
		return (
			_version_window(kind) is not None
			and instance.given(STATEMENT_TYPE)
			and (instance.statement_type in LATER_VERSION_TOLERATED) is tolerated
			and end is not None
			and end > _last_end(kind.taxonomy, tolerated=tolerated)
		)

	return strikes


def _takes_a_reason(kind: Datenart) -> bool:
	"""Whether the taxonomy takes a reason for an E-Bilanz without Kontensalden; an unknown one is checked as 6.9."""
	window = _version_window(kind)
	return window is None or window.kontensalden_reason


def _without_kontensalden(instance: Instance, kind: Datenart) -> bool:
	"""Rule 170405002: the Kontensalden not announced, in 6.9 without the reason, from 6.10 for a fiscal year beginning
	after the day the duty starts."""
	if instance.announced("KS"):
		return False
	if _takes_a_reason(kind):
		return not instance.given(NOT_YET_POSSIBLE)
	begin = instance.date(FISCAL_YEAR_BEGIN)
	return begin is not None and begin > KONTENSALDEN_SINCE


def _kontensalden_terms(version: str) -> tuple[str, ...]:
	announced = _not_given(f"{REPORT_ELEMENT}.reportElements.KS")
	if version_of(version).kontensalden_reason:
		return (announced, _not_given(NOT_YET_POSSIBLE))
	return (
		announced,
		f"FeldAngegeben(gcd:{FISCAL_YEAR_BEGIN})",
		f"[gcd:{FISCAL_YEAR_BEGIN}]>{_datum(KONTENSALDEN_SINCE)}",
	)


def _kst_without_bilanzgewinn(instance: Instance) -> bool:
	"""A GmbH or UG of the Kerntaxonomie without a Bilanzgewinn, as rules 170405070 and 170405071 take them."""
	return (
		not instance.balance_sheet_of_its_own
		and instance.chooses(LEGAL_STATUS, STEUERBOTE_LEGAL_STATUS)
		and instance.given(BAL_PROFIT)
		and instance.text(BAL_PROFIT) != "true"
		and not instance.has("microBilG")
		and not instance.has("bs.eqLiab.equity.endowmentCapital")
		and not instance.chooses(ENTITY_WITH_TAXABLE_PURPOSE, SPECIAL_CASES)
	)


def _net_income_differs(instance: Instance, *, transferred: bool) -> bool:
	net_income = instance.amount("is.netIncome", transferred=transferred)
	return net_income is not None and net_income != instance.zero(
		"bs.eqLiab.equity.netIncome", transferred=transferred
	) + instance.zero(
		"bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts", transferred=transferred
	)


RULES: tuple[BilanzRule, ...] = (
	_gcd_rule(
		"170205045", "FehlendeAngabeBerichtsstatus", "genInfo.report.id.revisionStatus", "Status des Berichts"
	),
	_gcd_rule(
		"170205046",
		"FehlendeAngabeKonsolidierungsumfang",
		"genInfo.report.id.consolidationRange",
		"Konsolidierungsumfang",
	),
	_gcd_rule(
		"170205047",
		"FehlendeAngabeAusweisBilanzgewinn",
		BAL_PROFIT,
		"Bilanz enthält Ausweis des Bilanzgewinns/Bilanzverlustes",
	),
	_gcd_rule("170205048", "FehlendeAngabeBilanzstichtag", CLOSING_DATE, "Bilanzstichtag", nil=True),
	_gcd_rule(
		"170205070", "FehlendeAngabeBeginnWJ", FISCAL_YEAR_BEGIN, "Beginn des Wirtschaftsjahres", nil=True
	),
	_gcd_rule("170205071", "FehlendeAngabeEndeWJ", FISCAL_YEAR_END, "Ende des Wirtschaftsjahres", nil=True),
	_gcd_rule(
		"170205049", "FehlendeAngabeUnternehmensname", "genInfo.company.id.name", "Name des Unternehmens"
	),
	_gcd_rule(
		"170205051", "FehlendeAngabeFirmensitzOrt", "genInfo.company.id.location.city", "Firmensitz, Ort"
	),
	_gcd_rule(
		"170205052",
		"FehlendeAngabeFirmensitzPLZ",
		"genInfo.company.id.location.zipCode",
		"Firmensitz, Postleitzahl",
	),
	_gcd_rule(
		"170205053",
		"FehlendeAngabeFirmensitzStrasse",
		"genInfo.company.id.location.street",
		"Firmensitz, Straße",
	),
	_gcd_rule(
		"170405036",
		"FehlendeAngabeEinkunftsart",
		"genInfo.company.id.incomeClassification",
		"Zuordnung zur Einkunftsart",
	),
	BilanzRule(
		"170205025",
		"FehlendeAngabeSteuernummer",
		"Die 13-stellige Steuernummer des Unternehmens fehlt; ohne sie geht nur eine Eröffnungsbilanz.",
		ST13,
		lambda instance, kind, header: (
			instance.given(STATEMENT_TYPE)
			and instance.statement_type != "statementType.EB"
			and not instance.special_balance
			and not instance.company_number(ST13)
		),
		_always('[gcd:genInfo.report.id.statementType]!="statementType.EB"', _not_given(ST13)),
	),
	BilanzRule(
		"170205026",
		"FehlendeAngabeFANummer",
		"Die Eröffnungsbilanz nennt weder die Steuernummer noch die Bundesfinanzamtsnummer des Unternehmens.",
		BF4,
		lambda instance, kind, header: (
			instance.statement_type == "statementType.EB"
			and not instance.special_balance
			and not instance.company_number(ST13)
			and not instance.company_number(BF4)
		),
		_always(
			'[gcd:genInfo.report.id.statementType]=="statementType.EB"', _not_given(ST13), _not_given(BF4)
		),
	),
	BilanzRule(
		"170205001",
		"SteuernummerPasstNichtZurFANummerNichtSondErgBilanz",
		"Die Steuernummer des Unternehmens gehört nicht zum Finanzamt des NutzdatenHeaders.",
		ST13,
		lambda instance, kind, header: (
			not instance.special_balance
			and bool(instance.company_number(ST13))
			and instance.company_number(ST13)[:4] != header.empfaenger
		),
		_always("BereichAlsString(gcd:genInfo.company.id.idNo.type.companyId.ST13,1,4)!=[ndh:Empfaenger]"),
	),
	BilanzRule(
		"170205022",
		"InkonsistenteAngabenBilanzstichtag",
		"Der Bilanzstichtag des GCD ist nicht der stichtag der E-Bilanz.",
		CLOSING_DATE,
		lambda instance, kind, header: (
			instance.date(CLOSING_DATE) is not None
			and f"{instance.date(CLOSING_DATE):%Y%m%d}" != instance.stichtag
		),
		_always("[gcd:genInfo.report.period.balSheetClosingDate]!=[ndh:stichtag]"),
	),
	BilanzRule(
		"170205072",
		"UnerlaubteAngabeEndeWJUngleichBilanzstichtagAbschlussAufgabe",
		"Ein Jahresabschluss hat seinen Bilanzstichtag am Ende des Wirtschaftsjahres.",
		CLOSING_DATE,
		lambda instance, kind, header: (
			instance.statement_type
			in ("statementType.AB", "statementType.E", "statementType.LSB", "statementType.UBandE")
			and None not in (instance.date(CLOSING_DATE), instance.date(FISCAL_YEAR_END))
			and instance.date(CLOSING_DATE) != instance.date(FISCAL_YEAR_END)
		),
		_always("[gcd:genInfo.report.period.fiscalYearEnd]!=[gcd:genInfo.report.period.balSheetClosingDate]"),
	),
	BilanzRule(
		"170205081",
		"UnerlaubteAngabeBeginnWJUngleichBilanzstichtagEroeffLiquid",
		"Eine Eröffnungsbilanz hat ihren Bilanzstichtag am Beginn des Wirtschaftsjahres.",
		CLOSING_DATE,
		lambda instance, kind, header: (
			instance.statement_type in OPENING_STATEMENTS
			and None not in (instance.date(CLOSING_DATE), instance.date(FISCAL_YEAR_BEGIN))
			and instance.date(CLOSING_DATE) != instance.date(FISCAL_YEAR_BEGIN)
		),
		_always(
			"[gcd:genInfo.report.period.fiscalYearBegin]!=[gcd:genInfo.report.period.balSheetClosingDate]"
		),
	),
	BilanzRule(
		"170205007",
		"UnerlaubteAngabeBeginnWJNichtLiquid",
		"Das Wirtschaftsjahr beginnt vor den Wirtschaftsjahren, für die die Version der HGB-Taxonomie gilt.",
		FISCAL_YEAR_BEGIN,
		_begins_too_early,
		lambda version: (f"[gcd:genInfo.report.period.fiscalYearBegin]<{_datum(_first_begin(version))}",),
	),
	BilanzRule(
		"170205018",
		"UnerlaubteAngabeEndeWJBilanzartStandard",
		"Das Wirtschaftsjahr endet nach den Wirtschaftsjahren, für die die Version der HGB-Taxonomie gilt.",
		FISCAL_YEAR_END,
		_ends_too_late(tolerated=False),
		lambda version: (f"[gcd:genInfo.report.period.fiscalYearEnd]>{_datum(_last_end(version))}",),
	),
	BilanzRule(
		"170205017",
		"UnerlaubteAngabeEndeWJBilanzartNichtStandard",
		"Das Wirtschaftsjahr endet nach den Wirtschaftsjahren, für die die Version der HGB-Taxonomie auch die "
		"Eröffnungsbilanz nimmt.",
		FISCAL_YEAR_END,
		_ends_too_late(tolerated=True),
		lambda version: (
			f"[gcd:genInfo.report.period.fiscalYearEnd]>{_datum(_last_end(version, tolerated=True))}",
		),
	),
	BilanzRule(
		"170205090",
		"FehlendeAngabeBerichtsbestandteilBBilanzart",
		"Die Bilanz ist nicht angekündigt.",
		f"{REPORT_ELEMENT}.reportElements.B",
		lambda instance, kind, header: (
			instance.given(STATEMENT_TYPE)
			and instance.statement_type not in OPENING_STATEMENTS
			and not instance.separate_tables
			and not instance.announced("B")
		),
		_always(_not_given(f"{REPORT_ELEMENT}.reportElements.B")),
	),
	BilanzRule(
		"170205091",
		"FehlendeAngabeBerichtsbestandteilGuVBilanzart",
		"Die GuV ist nicht angekündigt.",
		f"{REPORT_ELEMENT}.reportElements.GuV",
		lambda instance, kind, header: (
			instance.given(STATEMENT_TYPE)
			and instance.statement_type not in WITHOUT_GUV
			and not instance.separate_tables
			and not instance.has("microBilG")
			and not instance.announced("GuV")
		),
		_always(_not_given(f"{REPORT_ELEMENT}.reportElements.GuV")),
	),
	BilanzRule(
		"170405021",
		"FehlendeAngabeBerichtsbestandteilBOderEBBilanzart",
		"Die Eröffnungsbilanz kündigt weder die Bilanz noch die Eröffnungsbilanz ohne GuV an.",
		f"{REPORT_ELEMENT}.reportElements.B",
		lambda instance, kind, header: (
			instance.statement_type in OPENING_STATEMENTS
			and not instance.separate_tables
			and not instance.announced("B")
			and not instance.announced("EB")
		),
		_always(
			_not_given(f"{REPORT_ELEMENT}.reportElements.B"),
			_not_given(f"{REPORT_ELEMENT}.reportElements.EB"),
		),
	),
	BilanzRule(
		"170205021",
		"UnerlaubteAngabeBerichtsbestandteilGuVBilanzart",
		"Eine Eröffnungsbilanz hat keine GuV.",
		f"{REPORT_ELEMENT}.reportElements.GuV",
		lambda instance, kind, header: (
			instance.statement_type in OPENING_STATEMENTS and instance.announced("GuV")
		),
		_always(f"FeldAngegeben(gcd:{REPORT_ELEMENT}.reportElements.GuV)"),
	),
	BilanzRule(
		"170405101",
		"UnerlaubteAngabeBerichtsbestandteilBVVBilanzart",
		"Eine Eröffnungsbilanz hat keinen Betriebsvermögensvergleich.",
		f"{REPORT_ELEMENT}.reportElements.BVV",
		lambda instance, kind, header: (
			instance.statement_type in OPENING_STATEMENTS and instance.announced("BVV")
		),
		_always(f"FeldAngegeben(gcd:{REPORT_ELEMENT}.reportElements.BVV)"),
	),
	BilanzRule(
		"170205028",
		"UnerlaubteAngabeBerichtsbestandteilEBBilanzart",
		"Nur eine Eröffnungsbilanz kündigt die Eröffnungsbilanz ohne GuV an.",
		f"{REPORT_ELEMENT}.reportElements.EB",
		lambda instance, kind, header: (
			instance.given(STATEMENT_TYPE)
			and instance.statement_type not in OPENING_STATEMENTS
			and instance.announced("EB")
		),
		_always(f"FeldAngegeben(gcd:{REPORT_ELEMENT}.reportElements.EB)"),
	),
	BilanzRule(
		"170205066",
		"FehlendeAngabeBerichtsbestandteilBVV",
		"Mit der GuV kommt der Betriebsvermögensvergleich, der nicht angekündigt ist.",
		f"{REPORT_ELEMENT}.reportElements.BVV",
		lambda instance, kind, header: (
			not instance.announced("BVV")
			and (instance.announced("GuV") or instance.announced("GuVMicroBilG"))
			and not instance.given(TRANSMISSION_OPTION)
		),
		_always(_not_given(f"{REPORT_ELEMENT}.reportElements.BVV")),
	),
	BilanzRule(
		"170405002",
		"FehlendeAngabeBerichtsbestandteilKS",
		"Die Kontensalden sind nicht angekündigt; nur die HGB-Taxonomie 6.9 nimmt dafür eine Begründung im GCD.",
		f"{REPORT_ELEMENT}.reportElements.KS",
		lambda instance, kind, header: _without_kontensalden(instance, kind),
		lambda version: _kontensalden_terms(version),
	),
	BilanzRule(
		"170205095",
		"UnerlaubteAngabeBerichtsbestandteilSTUSteuerbilanz",
		"Eine Steuerbilanz hat keine Überleitungsrechnung.",
		f"{REPORT_ELEMENT}.reportElements.STU",
		lambda instance, kind, header: (
			instance.chooses(ACCOUNTING_STANDARD, STEUERBILANZ) and instance.announced("STU")
		),
		_always(f"FeldAngegeben(gcd:{REPORT_ELEMENT}.reportElements.STU)"),
	),
	BilanzRule(
		"170205100",
		"FehlendeAngabenUeberleitungHandelsbilanz",
		"Die Handelsbilanz hat keinen Eintrag der Überleitungsrechnung mit einer Wertänderung.",
		"hbst.transfer",
		lambda instance, kind, header: (
			instance.chooses(ACCOUNTING_STANDARD, ("accountingStandard.HGBM",))
			and not instance.given(TRANSMISSION_OPTION)
			and not instance.has("DeterminationOfTaxableIncomeSpec.forProfitOrganization.taxableIncome")
			and not instance.changes
		),
		_always(
			'[gcd:genInfo.report.id.accountingStandard]=="accountingStandard.HGBM"',
			"taxTrans*/gaap:hbst.transfer.bsAss.changeValueActualPeriod",
		),
	),
	BilanzRule(
		"170205011",
		"FehlendeAngabeSummeAktiva",
		"Die Summe Aktiva fehlt.",
		"bs.ass",
		lambda instance, kind, header: (
			not instance.balance_sheet_of_its_own
			and not instance.separate_tables
			and not instance.has("bs.ass")
		),
		_always(BRANCH, "FeldNichtAngegeben(gaap:bs.ass)"),
	),
	BilanzRule(
		"170205012",
		"FehlendeAngabeSummePassiva",
		"Die Summe Passiva fehlt.",
		"bs.eqLiab",
		lambda instance, kind, header: (
			not instance.balance_sheet_of_its_own
			and not instance.separate_tables
			and not instance.has("bs.eqLiab")
		),
		_always(BRANCH, "FeldNichtAngegeben(gaap:bs.eqLiab)"),
	),
	BilanzRule(
		"170205010",
		"AktivaUngleichPassiva",
		"Summe Aktiva und Summe Passiva weichen voneinander ab.",
		"bs.ass",
		lambda instance, kind, header: (
			not instance.balance_sheet_of_its_own
			and instance.has("bs.ass")
			and instance.has("bs.eqLiab")
			and instance.amount("bs.ass") != instance.amount("bs.eqLiab")
		),
		_always(BRANCH, "[gaap:bs.ass]!=[gaap:bs.eqLiab]"),
	),
	BilanzRule(
		"170405070",
		"JUebGuvUngleichBilanzgewOhneAusweisKST",
		"Der Jahresüberschuss der GuV ist nicht der der Bilanz mit dem steuerlichen Ausgleichsposten des Jahres.",
		"is.netIncome",
		lambda instance, kind, header: (
			_kst_without_bilanzgewinn(instance) and _net_income_differs(instance, transferred=True)
		),
		_always(
			"[gaap:is.netIncome]!=[gaap:bs.eqLiab.equity.netIncome]"
			"+[gaap:bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts]",
			'"legalStatus.KGAA"',
		),
	),
	BilanzRule(
		"170405071",
		"JUebGuvUngleichBilanzgewOhneAusweisKSTVorUeR",
		"Schon vor der Überleitung ist der Jahresüberschuss der GuV nicht der der Bilanz mit dem steuerlichen "
		"Ausgleichsposten des Jahres.",
		"is.netIncome",
		lambda instance, kind, header: (
			_kst_without_bilanzgewinn(instance)
			and instance.chooses(ACCOUNTING_STANDARD, ("accountingStandard.HGBM",))
			and _net_income_differs(instance, transferred=False)
		),
		_always(
			"[gaap:is.netIncome.beforeTransfer]!=[gaap:bs.eqLiab.equity.netIncome.beforeTransfer]"
			"+[gaap:bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts.beforeTransfer]"
		),
	),
	BilanzRule(
		"170405109",
		"JUebGuVUngleichJUebBVV",
		"Der Jahresüberschuss des Betriebsvermögensvergleichs ist nicht der der GuV.",
		"BVV.profitLoss",
		lambda instance, kind, header: (
			instance.announced("BVV")
			and not instance.balance_sheet_of_its_own
			and not instance.has("microBilG")
			and instance.amount("is.netIncome") is not None
			and instance.amount("is.netIncome") != instance.zero("BVV.profitLoss")
		),
		_always(
			'FeldWertInWerteListe(gcd:genInfo.report.id.specialAccountingStandard.mappedTo.branch,"Keine","Sonstige")',
			"[gaap:is.netIncome]!=[gaap:BVV.profitLoss]",
		),
	),
	BilanzRule(
		"170405114",
		"BVEndeWJBilanzUngleichBVEndeWJBVV",
		"Das Betriebsvermögen am Ende des Wirtschaftsjahres im Betriebsvermögensvergleich ist nicht das Eigenkapital "
		"der Bilanz ohne den nicht durch Eigenkapital gedeckten Fehlbetrag.",
		"BVV.profitLoss.assetsCurrentYear",
		lambda instance, kind, header: (
			instance.announced("BVV")
			and not instance.balance_sheet_of_its_own
			and instance.zero("BVV.profitLoss.assetsCurrentYear")
			!= instance.zero("bs.eqLiab.equity") - instance.zero("bs.ass.deficitNotCoveredByCapital")
		),
		_always(
			'FeldWertInWerteListe(gcd:genInfo.report.id.specialAccountingStandard.mappedTo.branch,"Keine","Sonstige")',
			"[gaap:BVV.profitLoss.assetsCurrentYear]!=[gaap:bs.eqLiab.equity]-[gaap:bs.ass.deficitNotCoveredByCapital]",
		),
	),
	BilanzRule(
		"170405047",
		"UnerlaubteAngabeTabelleAnlagenspiegelBruttoKurz",
		"Der Anlagenspiegel (brutto) in seiner Kurzform ist nicht zugelassen.",
		FIXED_ASSETS_SHORT,
		lambda instance, kind, header: FIXED_ASSETS_SHORT in instance.dimensions,
		_always("FeldAngegeben(gaap:cube_.nt.ass.gross_short.reported)"),
	),
)
"""The rules of „Kontext - Regeln“ the simulation checks, in the order of the module docstring."""


def _anlagenspiegel(root: ElementTree.Element, kind: Datenart, header: EnvelopeHeader) -> Message | None:
	"""The Anlagenspiegel (brutto), which ERiC 44.3.6.0 no longer checks (Leitfaden B.14.12.1)."""
	instance = read(root)
	begin = instance.date(FISCAL_YEAR_BEGIN)
	if (
		FIXED_ASSETS in instance.dimensions
		or instance.balance_sheet_of_its_own
		or not (instance.announced("B") or instance.announced("EB"))
		or begin is None
		or begin <= DUE_SINCE
	):
		return None
	return Message(
		ANLAGENSPIEGEL,
		"Der Anlagenspiegel (brutto) fehlt; er ist für jedes Wirtschaftsjahr zu übermitteln, das nach dem 31.12.2016 "
		"beginnt (Technischer Leitfaden zur HGB-Taxonomie, B.14.12.1; BMF-Schreiben vom 10.06.2025). ERiC 44.3.6.0 "
		"prüft es nicht mehr, da die Jahresdokumentation 6.9 ihre Regel 170405045 gestrichen hat.",
		ERROR,
		FIXED_ASSETS,
	)


def _taxonomy_checks(root: ElementTree.Element, kind: Datenart, header: EnvelopeHeader) -> Message | None:
	"""The first Mussfeld the instance lacks, the first calculation it gets wrong or, from taxonomy 6.10 on, the first
	position its Kontensalden get wrong (steuerbote.xbrl.checks.kontensalden()), with a registered taxonomy."""
	view = _TAXONOMIES.get(kind.taxonomy or "")
	instance = root.find(XBRL)
	shell = version_of(kind.taxonomy).fiscal_shell if view is not None else ""
	if view is None or not any(
		(reference.get(XLINK_HREF) or "").endswith(shell) for reference in instance.iter(f"{LINK}schemaRef")
	):
		return None
	from steuerbote.xbrl import checks
	from steuerbote.xbrl.checks import Facets
	from steuerbote.xbrl.taxonomy import TaxonomyError

	taxonomy = view()
	try:
		report = _report(instance, taxonomy)
	except (TaxonomyError, ValueError, LookupError, ArithmeticError) as error:
		return Message(
			TAXONOMY_CHECK,
			f"Die XBRL-Instanz lässt sich mit der HGB-Taxonomie {taxonomy.version} nicht lesen: {error}.",
			ERROR,
			"xbrl",
		)
	facets = Facets.of(report)
	found = (
		*checks.components(report, taxonomy, facets),
		*checks.mussfelder(report, taxonomy, facets),
		*checks.calculation(report, taxonomy),
		*checks.kontensalden(report, taxonomy, facets),
	)
	finding = next((finding for finding in found if finding.blocking), None)
	if finding is None:
		return None
	return Message(finding.code.value, f"{finding.text} ({finding.source})", ERROR, finding.concept or None)


@lru_cache(maxsize=1)
def read(root: ElementTree.Element) -> Instance:
	"""What the rules read of the EBilanz of the Nutzdaten."""
	instance = root.find(XBRL)
	gcd = tuple(element for element in instance.iter() if _module(element) == GCD_MODULE)
	dates = {
		_local(element): (element.text or "").strip()
		for element in gcd
		if element.get(NIL) != "true" and _local(element).startswith("genInfo.report.period.")
	}
	current = {
		(dates.get(CLOSING_DATE, ""),),
		(dates.get(FISCAL_YEAR_BEGIN, ""), dates.get(FISCAL_YEAR_END, "")),
	}
	contexts = {context.get("id"): context for context in instance.iter(f"{XBRLI}context")}
	scenarios = {name: _dimensions(context) for name, context in contexts.items()}
	present = {
		name for name, context in contexts.items() if not scenarios[name] and _period(context) in current
	}
	amounts: dict[str, Decimal] = {}
	for element in instance:
		if (
			_module(element) == GAAP_MODULE
			and element.get("contextRef") in present
			and element.get(NIL) != "true"
		):
			value = _number(element.text)
			if value is not None:
				amounts[_local(element)] = value
	dimensions = frozenset(
		dimension
		for element in instance.iter()
		if element.get("contextRef") in scenarios and element.get(NIL) != "true"
		for dimension in scenarios[element.get("contextRef")]
	)
	return Instance(
		(root.findtext("{*}stichtag") or "").strip(),
		gcd,
		MappingProxyType(amounts),
		MappingProxyType(_changes(instance)),
		dimensions,
	)


def _changes(instance: ElementTree.Element) -> dict[str, Decimal]:
	changes: dict[str, Decimal] = {}
	for transfer in instance:
		if _local(transfer) != "hbst.transfer":
			continue
		for entry in transfer:
			if _local(entry) not in ENTRIES:
				continue
			name = next((_qname(child.text) for child in entry if _local(child).endswith(".name")), "")
			for child in entry:
				value = _number(child.text) if child.get(NIL) != "true" else None
				if _local(child).rpartition(".")[2] in CHANGES and value is not None:
					changes[name] = changes.get(name, Decimal(0)) + value
	return changes


def _report(instance: ElementTree.Element, taxonomy: Taxonomy) -> Report:
	"""The facts of the instance, its values typed as steuerbote/xbrl/facts.py takes them."""
	from steuerbote.xbrl.facts import Entity, Item, Period, Periods, Report, Tuple
	from steuerbote.xbrl.taxonomy import Kind

	prefixes = {namespace: prefix for prefix, namespace in taxonomy.namespaces.items()}
	dates = {}
	for element in instance:
		if _local(element).startswith("genInfo.report.period.") and element.get(NIL) != "true":
			dates[_local(element)] = date.fromisoformat((element.text or "").strip())
	periods = Periods(
		dates[FISCAL_YEAR_BEGIN],
		dates[FISCAL_YEAR_END],
		dates.get(CLOSING_DATE),
		dates.get(PREVIOUS_BEGIN),
		dates.get(PREVIOUS_END),
	)
	contexts = {context.get("id"): context for context in instance.iter(f"{XBRLI}context")}

	def name_of(element: ElementTree.Element) -> str:
		namespace, _, local = element.tag[1:].partition("}")
		return f"{prefixes.get(namespace, namespace)}:{local}"

	def period_of(context: ElementTree.Element) -> Period:
		instant = context.findtext(f"{XBRLI}period/{XBRLI}instant")
		if instant is not None:
			day = date.fromisoformat(instant.strip())
			return Period.STICHTAG if day == periods.balance_sheet_date else Period.VORJAHR_STICHTAG
		end = date.fromisoformat((context.findtext(f"{XBRLI}period/{XBRLI}endDate") or "").strip())
		return Period.WIRTSCHAFTSJAHR if end == periods.fiscal_year_end else Period.VORJAHR

	def facts(elements: Iterable[ElementTree.Element]) -> tuple:
		return tuple(found for element in elements if (found := fact(element)) is not None)

	def fact(element: ElementTree.Element):
		name = name_of(element)
		concept = taxonomy.concept(name)
		if concept.kind is Kind.TUPLE:
			if element.get(NIL) == "true":
				return Tuple(name, nil=True)
			return Tuple(name, facts(element))
		context = contexts[element.get("contextRef")]
		if next(context.iter(f"{XBRLDI}typedMember"), None) is not None:
			return None
		dimensions = tuple(
			(_qualified(member.get("dimension", ""), taxonomy), _qualified(member.text, taxonomy))
			for member in context.iter(f"{XBRLDI}explicitMember")
		)
		text = (element.text or "").strip()
		value = None
		if element.get(NIL) != "true":
			value = Decimal(text) if concept.numeric else (element.text or "")
		decimals = element.get("decimals")
		return Item(
			name,
			period_of(context),
			value,
			dimensions,
			None if concept.monetary or decimals is None or value is None else int(decimals),
		)

	identifier = next(iter(instance.iter(f"{XBRLI}identifier")), None)
	if identifier is None:
		raise ValueError("no context names the company")
	return Report(
		Entity(identifier.get("scheme", ""), (identifier.text or "").strip()),
		periods,
		tuple(reference.get(XLINK_HREF, "") for reference in instance.iter(f"{LINK}schemaRef")),
		facts(element for element in instance if not element.tag.startswith((XBRLI, LINK))),
	)


def _qualified(name: str | None, taxonomy: Taxonomy) -> str:
	"""A QName of the instance by the prefixes of the taxonomy, as Steuerbote writes them."""
	prefix, _, local = (name or "").strip().rpartition(":")
	return f"{prefix}:{local}" if prefix in taxonomy.namespaces else f"de-gaap-ci:{local}"


def _module(element: ElementTree.Element) -> str:
	"""The module of the taxonomy an element belongs to, de-gcd- or de-gaap-ci-, else empty."""
	namespace = element.tag[1:].partition("}")[0] if element.tag.startswith("{") else ""
	module = namespace.removeprefix(TAXONOMY_URL)
	return next((prefix for prefix in (GCD_MODULE, GAAP_MODULE) if module.startswith(prefix)), "")


def _local(element: ElementTree.Element) -> str:
	return element.tag.rpartition("}")[2]


def _qname(text: str | None) -> str:
	return (text or "").strip().rpartition(":")[2]


def _valued(element: ElementTree.Element) -> bool:
	if element.get(NIL) == "true":
		return False
	return len(element) == 0 or any(_valued(child) for child in element)


def _number(text: str | None) -> Decimal | None:
	try:
		value = Decimal((text or "").strip())
	except InvalidOperation:
		return None
	return value if value.is_finite() else None


def _period(context: ElementTree.Element) -> tuple[str, ...]:
	period = context.find(f"{XBRLI}period")
	instant = period.findtext(f"{XBRLI}instant") if period is not None else None
	if instant is not None:
		return (instant.strip(),)
	return tuple(
		(period.findtext(f"{XBRLI}{name}") or "").strip() if period is not None else ""
		for name in ("startDate", "endDate")
	)


def _dimensions(context: ElementTree.Element) -> frozenset[str]:
	"""The local names of the dimensions of a context, explicit and typed ones."""
	return frozenset(
		member.get("dimension", "").rpartition(":")[2]
		for kind in ("explicitMember", "typedMember")
		for member in context.iter(f"{XBRLDI}{kind}")
	)


def expected_rules(version: str) -> tuple[RuleExpectation, ...]:
	"""The rules of „Kontext - Regeln“ the simulation checks, with the terms of their Prüfbedingungen."""
	return tuple(rule.expectation(version) for rule in RULES)


def _structure(root: ElementTree.Element, kind: Datenart) -> Structure:
	version = root.get("version", "")
	if (
		root.tag != f"{{{kind.namespace}}}{kind.root}"
		or not version.isdigit()
		or int(version) not in VERSIONS
	):
		begins = f"Die Nutzdaten beginnen nicht mit {kind.root} in der Version {kind.root_version}"
		return None, Message("SIM-003", f"{begins} im Namensraum {kind.namespace}.", ERROR, kind.root)
	stichtag = root.find(f"{{{kind.namespace}}}stichtag")
	if stichtag is None:
		text = "Die E-Bilanz braucht den Stichtag vor der XBRL-Instanz (ebilanz_000002.xsd)."
		return None, Message("SIM-004", text, ERROR, "stichtag")
	if root.find(XBRL) is None:
		text = "Die E-Bilanz braucht die XBRL-Instanz xbrli:xbrl nach dem Stichtag (ebilanz_000002.xsd)."
		return None, Message("SIM-004", text, ERROR, "xbrl")
	if [child.tag for child in root] != [stichtag.tag, XBRL]:
		text = "Die E-Bilanz enthält genau den Stichtag und danach die XBRL-Instanz (ebilanz_000002.xsd)."
		return None, Message("SIM-003", text, ERROR, kind.root)
	if _stichtag(stichtag.text) is None:
		text = (
			f"Der Stichtag {(stichtag.text or '').strip()} ist kein Datum JJJJMMTT (Jahresdokumentation, Header - "
			"Felder)."
		)
		return None, Message("SIM-010", text, ERROR, "stichtag")
	return root, None


def _stichtag(text: str | None) -> datetime | None:
	value = (text or "").strip()
	if len(value) != len("JJJJMMTT") or not value.isdigit():
		return None
	try:
		return datetime.strptime(value, STICHTAG_FORMAT)
	except ValueError:
		return None


def _filing(root: ElementTree.Element, kind: Datenart) -> list[str]:
	stichtag = _stichtag(root.findtext(f"{{{kind.namespace}}}stichtag"))
	return [f"Stichtag: {stichtag:%d.%m.%Y}", f"Taxonomie: {kind.taxonomy}"]


def _structure_only(kind: Datenart, reason: str) -> str:
	if kind.taxonomy in _TAXONOMIES:
		checked = (
			f"Die Simulation prüft den Rahmen der E-Bilanz, Regeln der Jahresdokumentation und mit der HGB-Taxonomie "
			f"{kind.taxonomy} die Mussfelder und die Rechenregeln der XBRL-Instanz, nicht ihr Schema"
		)
	else:
		checked = (
			"Die Simulation prüft den Rahmen der E-Bilanz und Regeln der Jahresdokumentation; ohne die HGB-Taxonomie "
			f"{kind.taxonomy} prüft sie die Mussfelder und die Rechenregeln der XBRL-Instanz nicht"
		)
	return f"{checked}: {reason}"


FRAME = Checks(_structure, _filing, _structure_only, schema=False)
"""The checks of the frame alone, without the rules of the instance."""
CHECKS = FRAME._replace(rules=(*RULES, _anlagenspiegel, _taxonomy_checks))
