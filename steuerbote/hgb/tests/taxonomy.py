"""The mini taxonomy of the Offenlegung: the part of the HGB-Taxonomie 6.9 that the instances of
steuerbote/hgb/instance.py report, for the tests that run without the package.

The package may not be passed on (steuerbote/xbrl/tests/real.py), and the mini taxonomy of steuerbote/xbrl/tests/mini.py
has neither the role notesBelowBalanceSheet nor the fields of the GCD an Offenlegung states. This one is an extract of
the views COMMERCIAL and COMMERCIAL_MICROBILG of 6.9, which agree on all of it: every concept an instance of a
Kleinstkapitalgesellschaft or of a small company can report, the positions above it in the presentation of the Bilanz,
of the Angaben unter der Bilanz, of the Anhang and of the GCD, and the heads of the choices, each with the kind,
substitution group, type, period type, balance and abstract of the real one, a tuple with those of its particles the
instances use. Its relationships are the arcs among them of those four presentation networks and of the calculation of
the Bilanz, with their order and weight. Neither the fiscal references, which hold the legal forms a position is for,
nor the labels nor the tables of the definition linkbase are part of it, so the checks of the profile DISCLOSURE find
on it what concerns the structure, and a finding names a concept by its name. test_real_taxonomy.py checks every
concept and arc against the package.
"""

from collections.abc import Iterator
from decimal import Decimal
from functools import cache
from types import MappingProxyType

from steuerbote.xbrl.checks import NOTES_BELOW_BALANCE_SHEET
from steuerbote.xbrl.taxonomy import (
	BALANCE_SHEET,
	GCD,
	NOTES,
	Arc,
	Balance,
	Concept,
	Content,
	Kind,
	Network,
	Particle,
	PeriodType,
	Taxonomy,
	View,
)
from steuerbote.xbrl.versions import TAXONOMIES

VERSION = TAXONOMIES["6.9"]
GAAP_PREFIX = "de-gaap-ci"
GCD_PREFIX = "de-gcd"
NAMESPACES = MappingProxyType({GAAP_PREFIX: VERSION.gaap_namespace, GCD_PREFIX: VERSION.gcd_namespace})
MONETARY = "xbrli:monetaryItemType"
STRING = "xbrli:stringItemType"
DATE = "xbrli:dateItemType"
BOOLEAN = "xbrli:booleanItemType"
DECIMAL = "xbrli:decimalItemType"
INSTANT = PeriodType.INSTANT
DURATION = PeriodType.DURATION
ROLES = MappingProxyType(
	{
		BALANCE_SHEET: "Bilanz",
		NOTES_BELOW_BALANCE_SHEET: "Angaben unter der Bilanz",
		NOTES: "Anhang",
		GCD: "GCD (Global Common Document)",
	}
)
"""The roles of the extract with their definitions in the schemas."""


def _names(names: str) -> tuple[str, ...]:
	return tuple(names.split())


def _items(
	prefix: str,
	item_type: str,
	period: PeriodType,
	names: str,
	*,
	balance: Balance | None = None,
	abstract: bool = False,
	kind: Kind = Kind.ITEM,
) -> Iterator[Concept]:
	group = {
		Kind.ITEM: "xbrli:item",
		Kind.HYPERCUBE: "xbrldt:hypercubeItem",
		Kind.DIMENSION: "xbrldt:dimensionItem",
	}
	for name in _names(names):
		yield Concept(
			f"{prefix}:{name}",
			NAMESPACES[prefix],
			kind,
			group[kind],
			item_type,
			period,
			balance,
			abstract,
			nillable=True,
		)


def _tuple(prefix: str, name: str, group: str, *particles: Particle, max_occurs: int | None = 1) -> Concept:
	return Concept(
		f"{prefix}:{name}",
		NAMESPACES[prefix],
		Kind.TUPLE,
		"xbrli:tuple",
		nillable=True,
		content=Content(group, 1, max_occurs, particles),
	)


def _sequence(prefix: str, name: str, *parts: tuple[str, int]) -> Concept:
	"""A tuple of a sequence, each part with its minOccurs and a maxOccurs of 1."""
	return _tuple(prefix, name, "sequence", *(Particle(f"{prefix}:{part}", low, 1) for part, low in parts))


def _choice(name: str, head: str, *values: str, many: bool = False) -> Iterator[Concept]:
	"""A choice of the GCD: its tuple, the abstract head of its values, and the values in the substitution group of
	the head. The head and the values are named below the tuple, a name from genInfo on as it stands."""

	def full(part: str) -> str:
		return part if part.startswith("genInfo.") else f"{name}.{part}"

	head_name = f"{GCD_PREFIX}:{full(head)}"
	yield _tuple(GCD_PREFIX, name, "choice", Particle(head_name), max_occurs=None if many else 1)
	yield from _items(GCD_PREFIX, STRING, DURATION, full(head), abstract=True)
	for value in values:
		yield Concept(
			f"{GCD_PREFIX}:{full(value)}",
			NAMESPACES[GCD_PREFIX],
			Kind.ITEM,
			head_name,
			STRING,
			DURATION,
			nillable=True,
		)


def _arcs(prefix: str, spec: str, *, weighted: bool = False) -> tuple[Arc, ...]:
	"""Arcs written one per line as „parent > child number“, the number the order of a presentation or the weight of a
	calculation, whose order is 1 throughout."""
	arcs = []
	for line in spec.strip().splitlines():
		parent, _, rest = line.partition(">")
		child, _, number = rest.strip().partition(" ")
		parent, child = f"{prefix}:{parent.strip()}", f"{prefix}:{child.strip()}"
		if weighted:
			arcs.append(Arc(parent, child, weight=Decimal(number)))
		else:
			arcs.append(Arc(parent, child, Decimal(number)))
	return tuple(arcs)


ASSETS = """
	bs.ass
	bs.ass.fixAss bs.ass.fixAss.intan bs.ass.fixAss.tan bs.ass.fixAss.fin bs.ass.fixAss.fin.LoansToShareholder
	bs.ass.currAss bs.ass.currAss.inventory bs.ass.currAss.receiv bs.ass.currAss.receiv.above1year
	bs.ass.currAss.receiv.shareholder bs.ass.currAss.securities bs.ass.currAss.cashEquiv
	bs.ass.prepaidExp bs.ass.defTax bs.ass.SurplusFromOffsetting bs.ass.deficitNotCoveredByCapital
	bs.eqLiab.equity.subscribed.ownSharesdeducted bs.eqLiab.equity.subscribed.unpaidCap
"""
"""The amounts of the Aktiva and those the Gezeichnetes Kapital deducts, each with the balance debit."""
EQUITY_AND_LIABILITIES = """
	bs.eqLiab
	bs.eqLiab.equity bs.eqLiab.equity.subscribed bs.eqLiab.equity.subscribed.corp bs.eqLiab.equity.capRes
	bs.eqLiab.equity.revenueRes bs.eqLiab.equity.retainedEarnings bs.eqLiab.equity.netIncome bs.eqLiab.equity.profitLoss
	bs.eqLiab.equity.profitLoss.retainedEarnings bs.eqLiab.equity.deficitNotCoveredByCapital
	bs.eqLiab.accruals bs.eqLiab.liab bs.eqLiab.liab.upTo1year bs.eqLiab.liab.above1year
	bs.eqLiab.liab.ofWhichToShareholders bs.eqLiab.defIncome bs.eqLiab.defTax
	bs.contingLiab
	bs.contingLiab.notes bs.contingLiab.notes.assoc bs.contingLiab.notes.pension
	bs.contingLiab.guarantees bs.contingLiab.guarantees.assoc bs.contingLiab.guarantees.pension
	bs.contingLiab.guaranteesNotes bs.contingLiab.guaranteesNotes.assoc bs.contingLiab.guaranteesNotes.pension
	bs.contingLiab.warranty bs.contingLiab.warranty.assoc bs.contingLiab.warranty.pension
	bs.contingLiab.collateralisation bs.contingLiab.collateralisation.assoc bs.contingLiab.collateralisation.pension
"""
"""The amounts of the Passiva and of the Haftungsverhältnisse, each with the balance credit."""
TEXTS = """
	notesBelowBalanceSheet
	notesBelowBalanceSheet.geninfo notesBelowBalanceSheet.geninfo.company notesBelowBalanceSheet.geninfo.location
	notesBelowBalanceSheet.geninfo.court notesBelowBalanceSheet.geninfo.number
	notesBelowBalanceSheet.geninfo.liquidationOrWindingUp
	ntmi ntmi.other
	nt
	nt.genInfo nt.genInfo.measurement nt.genInfo.changeInMeasuremt nt.genInfo.interestInManufCost
	nt.genInfo.changeInPresentation nt.genInfo.asetsOrLiabilitiesUnderServeralHeadings
	nt.genInfo.lackOfComparabilityToPriorStatements nt.genInfo.DisclosuresMasurementUnits
	nt.genInfo.DisclosuresOffsetAssets
	nt.bsInfo nt.bsInfo.totalAmountLiabOver5Years nt.bsInfo.analysisOfLiab nt.bsinfo.analysisOfReceiv
	nt.isInfo nt.isInfo.reasonsGoodwillAmortisationsLonger5Years
	nt.additionalNotes nt.additionalNotes.additDisclosuresIfFinStatmntDoesNotPresentTrueAndFairView
	nt.otherInfo nt.otherInfo.contingLiab
	nt.assocComp nt.assocComp.parentsNameSmall
	nt.relationships nt.relationships.creditsToMembers
	nt.directorsSign nt.directorsSign.place nt.directorsSign.type.name nt.directorsSign.person.name
	nt.directorsSign.person.otherattributes
"""
"""The texts of the Angaben unter der Bilanz and of the Anhang, and the positions above them."""
TABLES = "table.nt.ass.gross table.nt.ass.gross_short table.liab table.receiv"
"""The tables of the Anhang whose dimensions take positions of the Bilanz: the Anlagenspiegel, the
Verbindlichkeitenspiegel and the Forderungsspiegel."""

GCD_HEADINGS = """
	genInfo genInfo.doc genInfo.doc.id genInfo.report genInfo.report.id
	genInfo.report.id.reportStatus.approvalAndDisclosureDate genInfo.report.audit genInfo.report.period
	genInfo.company genInfo.company.id genInfo.company.disclosureCriterion genInfo.company.disclosureCriterion.scope
"""
GCD_DATES = """
	genInfo.doc.id.generationDate genInfo.report.id.reportStatus.reportStatus.dateofapproval
	genInfo.report.period.fiscalYearBegin genInfo.report.period.fiscalYearEnd genInfo.report.period.balSheetClosingDate
	genInfo.report.period.fiscalPreviousYearBegin genInfo.report.period.fiscalPreviousYearEnd
	genInfo.report.period.balSheetClosingDatePreviousYear genInfo.company.id.FoundationDate
"""
GCD_TEXTS = """
	genInfo.company.id.name genInfo.company.id.Incorporation genInfo.company.id.Incorporation.court
	genInfo.company.id.location genInfo.company.id.location.street genInfo.company.id.location.houseNo
	genInfo.company.id.location.zipCode genInfo.company.id.location.city genInfo.company.id.location.country
	genInfo.company.id.idNo.type.companyId.HRN
"""
HRN = "genInfo.company.id.idNo.type.companyId.HRN"


def _concepts() -> Iterator[Concept]:
	yield from _items(GAAP_PREFIX, STRING, INSTANT, "bs", abstract=True)
	yield from _items(GAAP_PREFIX, MONETARY, INSTANT, ASSETS, balance=Balance.DEBIT)
	yield from _items(GAAP_PREFIX, MONETARY, INSTANT, EQUITY_AND_LIABILITIES, balance=Balance.CREDIT)
	yield from _items(GAAP_PREFIX, STRING, DURATION, TEXTS)
	yield from _items(GAAP_PREFIX, DATE, DURATION, "nt.directorsSign.date")
	yield from _items(GAAP_PREFIX, DECIMAL, DURATION, "nt.employeesAveragePeriod")
	yield _sequence(
		GAAP_PREFIX,
		"nt.directorsSign.type",
		("nt.directorsSign.type.name", 1),
		("nt.directorsSign.person", 0),
	)
	yield _sequence(
		GAAP_PREFIX,
		"nt.directorsSign.person",
		("nt.directorsSign.person.name", 1),
		("nt.directorsSign.person.otherattributes", 0),
	)
	yield from _items(GAAP_PREFIX, STRING, INSTANT, "nt.ass")
	yield from _items(GAAP_PREFIX, STRING, DURATION, TABLES, abstract=True)
	yield from _items(
		GAAP_PREFIX,
		STRING,
		DURATION,
		"cube_.nt.ass.gross cube_.nt.ass.gross_short tab_liab tab_receiv",
		abstract=True,
		kind=Kind.HYPERCUBE,
	)
	yield from _items(
		GAAP_PREFIX,
		STRING,
		DURATION,
		"dim_changes.nt.ass.gross dim_changes.nt.ass.gross_short dim_liab dim_receiv",
		abstract=True,
		kind=Kind.DIMENSION,
	)
	yield from _items(GCD_PREFIX, STRING, DURATION, GCD_HEADINGS, abstract=True)
	yield from _items(GCD_PREFIX, DATE, DURATION, GCD_DATES)
	yield from _items(GCD_PREFIX, STRING, DURATION, GCD_TEXTS)
	yield from _items(
		GCD_PREFIX,
		BOOLEAN,
		DURATION,
		"genInfo.report.id.incomeStatementendswithBalProfit "
		"genInfo.company.disclosureCriterion.scope.CapitalMarketOrientationHGBs264d",
	)
	yield _sequence(GCD_PREFIX, "genInfo.company.id.idNo", (HRN, 0))
	yield _sequence(GCD_PREFIX, "genInfo.report.id.accordingTo", ("genInfo.report.id.accordingTo.idNo", 0))
	yield _sequence(GCD_PREFIX, "genInfo.report.id.accordingTo.idNo", (HRN, 0))
	yield from _choice("genInfo.report.id.reportType", "reportType.head", "reportType.JA")
	yield from _choice("genInfo.report.id.reportStatus", "reportStatus.head", "reportStatus.E")
	yield from _choice(
		"genInfo.report.id.revisionStatus",
		"revisionStatus.head",
		*(f"revisionStatus.{status}" for status in ("E", "B", "G", "BG", "I", "sK")),
	)
	yield from _choice(
		"genInfo.report.id.reportElement",
		"reportElements.head",
		"reportElements.B",
		"reportElements.H",
		"reportElements.SA",
		many=True,
	)
	yield from _choice("genInfo.report.id.reportElement.allocation.genInfo", "head", "toBalance")
	yield from _choice("genInfo.report.id.reportElement.allocation.notesMicroBilG", "head", "toBalance")
	yield from _choice(
		"genInfo.report.id.reportElement.allocation.contingencies", "head", "toBalance", "inNotes"
	)
	yield from _choice("genInfo.report.id.statementType", "statementType.head", "statementType.E")
	yield from _choice(
		"genInfo.report.id.accountingStandard", "accountingStandard.head", "accountingStandard.HGBM"
	)
	yield from _choice("genInfo.report.id.specialAccountingStandard", "head", "K", many=True)
	yield from _choice(
		"genInfo.report.id.mainAccountingStandard", "genInfo.report.id.specialAccountingStandard.head"
	)
	yield from _choice(
		"genInfo.report.id.incomeStatementFormat",
		"incomeStatementFormat.head",
		"incomeStatementFormat.GKV",
		"incomeStatementFormat.UKV",
	)
	yield from _choice(
		"genInfo.report.id.consolidationRange", "consolidationRange.head", "consolidationRange.EA"
	)
	yield from _choice(
		"genInfo.report.audit.noAudit", "genInfo.report.audit.noGCC_Audit.head", "noAuditRequi"
	)
	yield from _choice("genInfo.company.id.legalStatus", "legalStatus.head", "legalStatus.GMBH")
	yield from _choice("genInfo.company.id.Incorporation.Type", "Type.head", "Type.HR")
	yield from _choice("genInfo.company.id.sizeClass", "sizeClass.head", "sizeClass.KK", "sizeClass.KstK")
	yield from _choice("genInfo.company.id.reportedSizeClassBs", "head", "K", "Kst")
	yield from _choice("genInfo.company.id.CompanyStatus", "companyStatus.head", "companyStatus.L")


CONCEPTS: MappingProxyType[str, Concept] = MappingProxyType(
	{concept.name: concept for concept in _concepts()}
)


BALANCE_SHEET_ARCS = _arcs(
	GAAP_PREFIX,
	"""
	bs > bs.ass 1
	bs.ass > bs.ass.fixAss 3
	bs.ass.fixAss > bs.ass.fixAss.intan 1
	bs.ass.fixAss > bs.ass.fixAss.tan 2
	bs.ass.fixAss > bs.ass.fixAss.fin 3
	bs.ass.fixAss.fin > bs.ass.fixAss.fin.LoansToShareholder 0.1
	bs.ass > bs.ass.currAss 5
	bs.ass.currAss > bs.ass.currAss.inventory 1
	bs.ass.currAss > bs.ass.currAss.receiv 2
	bs.ass.currAss.receiv > bs.ass.currAss.receiv.above1year 0.5
	bs.ass.currAss.receiv > bs.ass.currAss.receiv.shareholder 1.4
	bs.ass.currAss > bs.ass.currAss.securities 3
	bs.ass.currAss > bs.ass.currAss.cashEquiv 4
	bs.ass > bs.ass.prepaidExp 6
	bs.ass > bs.ass.defTax 7
	bs.ass > bs.ass.SurplusFromOffsetting 7.5
	bs.ass > bs.ass.deficitNotCoveredByCapital 10
	bs > bs.eqLiab 2
	bs.eqLiab > bs.eqLiab.equity 1
	bs.eqLiab.equity > bs.eqLiab.equity.subscribed 1
	bs.eqLiab.equity.subscribed > bs.eqLiab.equity.subscribed.corp 1
	bs.eqLiab.equity.subscribed > bs.eqLiab.equity.subscribed.ownSharesdeducted 1.1
	bs.eqLiab.equity.subscribed > bs.eqLiab.equity.subscribed.unpaidCap 1.2
	bs.eqLiab.equity > bs.eqLiab.equity.capRes 6
	bs.eqLiab.equity > bs.eqLiab.equity.revenueRes 8
	bs.eqLiab.equity > bs.eqLiab.equity.retainedEarnings 11
	bs.eqLiab.equity > bs.eqLiab.equity.netIncome 12
	bs.eqLiab.equity > bs.eqLiab.equity.profitLoss 13
	bs.eqLiab.equity.profitLoss > bs.eqLiab.equity.profitLoss.retainedEarnings 0.5
	bs.eqLiab.equity > bs.eqLiab.equity.deficitNotCoveredByCapital 15
	bs.eqLiab > bs.eqLiab.accruals 4
	bs.eqLiab > bs.eqLiab.liab 5
	bs.eqLiab.liab > bs.eqLiab.liab.upTo1year 0.5
	bs.eqLiab.liab > bs.eqLiab.liab.above1year 0.55
	bs.eqLiab.liab > bs.eqLiab.liab.ofWhichToShareholders 0.6
	bs.eqLiab > bs.eqLiab.defIncome 6
	bs.eqLiab > bs.eqLiab.defTax 7
	""",
)
NOTES_BELOW_BALANCE_SHEET_ARCS = _arcs(
	GAAP_PREFIX,
	"""
	notesBelowBalanceSheet > notesBelowBalanceSheet.geninfo 0.5
	notesBelowBalanceSheet.geninfo > notesBelowBalanceSheet.geninfo.company 1
	notesBelowBalanceSheet.geninfo > notesBelowBalanceSheet.geninfo.location 2
	notesBelowBalanceSheet.geninfo > notesBelowBalanceSheet.geninfo.court 3
	notesBelowBalanceSheet.geninfo > notesBelowBalanceSheet.geninfo.number 4
	notesBelowBalanceSheet.geninfo > notesBelowBalanceSheet.geninfo.liquidationOrWindingUp 5
	notesBelowBalanceSheet > bs.contingLiab 1
	bs.contingLiab > bs.contingLiab.notes 1
	bs.contingLiab.notes > bs.contingLiab.notes.assoc 1
	bs.contingLiab.notes > bs.contingLiab.notes.pension 2
	bs.contingLiab > bs.contingLiab.guarantees 2
	bs.contingLiab.guarantees > bs.contingLiab.guarantees.assoc 1
	bs.contingLiab.guarantees > bs.contingLiab.guarantees.pension 2
	bs.contingLiab > bs.contingLiab.guaranteesNotes 3
	bs.contingLiab.guaranteesNotes > bs.contingLiab.guaranteesNotes.assoc 1
	bs.contingLiab.guaranteesNotes > bs.contingLiab.guaranteesNotes.pension 2
	bs.contingLiab > bs.contingLiab.warranty 4
	bs.contingLiab.warranty > bs.contingLiab.warranty.assoc 1
	bs.contingLiab.warranty > bs.contingLiab.warranty.pension 2
	bs.contingLiab > bs.contingLiab.collateralisation 5
	bs.contingLiab.collateralisation > bs.contingLiab.collateralisation.assoc 1
	bs.contingLiab.collateralisation > bs.contingLiab.collateralisation.pension 2
	notesBelowBalanceSheet > ntmi 2
	ntmi > nt.relationships.creditsToMembers 1
	ntmi > ntmi.other 3
	""",
)
NOTES_ARCS = _arcs(
	GAAP_PREFIX,
	"""
	nt > nt.ass 1
	nt.ass > table.nt.ass.gross 1
	table.nt.ass.gross > cube_.nt.ass.gross 1
	cube_.nt.ass.gross > dim_changes.nt.ass.gross 2
	dim_changes.nt.ass.gross > bs.ass.fixAss 3
	bs.ass.fixAss > bs.ass.fixAss.intan 1
	bs.ass.fixAss > bs.ass.fixAss.tan 2
	bs.ass.fixAss > bs.ass.fixAss.fin 3
	bs.ass.fixAss.fin > bs.ass.fixAss.fin.LoansToShareholder 0.1
	nt.ass > table.nt.ass.gross_short 1.5
	table.nt.ass.gross_short > cube_.nt.ass.gross_short 1
	cube_.nt.ass.gross_short > dim_changes.nt.ass.gross_short 2
	dim_changes.nt.ass.gross_short > bs.ass.fixAss 2
	nt > nt.genInfo 6
	nt.genInfo > nt.genInfo.measurement 1
	nt.genInfo > nt.genInfo.changeInMeasuremt 2
	nt.genInfo > nt.genInfo.interestInManufCost 3
	nt.genInfo > nt.isInfo.reasonsGoodwillAmortisationsLonger5Years 3.5
	nt.genInfo > nt.genInfo.changeInPresentation 5
	nt.genInfo > nt.genInfo.asetsOrLiabilitiesUnderServeralHeadings 18
	nt.genInfo > nt.genInfo.lackOfComparabilityToPriorStatements 20
	nt.genInfo > nt.genInfo.DisclosuresMasurementUnits 48
	nt.genInfo > nt.genInfo.DisclosuresOffsetAssets 50
	nt > nt.bsInfo 7
	nt.bsInfo > nt.bsinfo.analysisOfReceiv 1.5
	nt.bsinfo.analysisOfReceiv > table.receiv 1
	table.receiv > tab_receiv 1
	tab_receiv > dim_receiv 1
	dim_receiv > bs.ass.currAss.receiv 1
	nt.bsInfo > nt.bsInfo.totalAmountLiabOver5Years 17
	nt.bsInfo > nt.bsInfo.analysisOfLiab 19
	nt.bsInfo.analysisOfLiab > table.liab 1
	table.liab > tab_liab 1
	tab_liab > dim_liab 1
	dim_liab > bs.eqLiab.liab 1
	nt > nt.isInfo 8
	nt.isInfo > nt.isInfo.reasonsGoodwillAmortisationsLonger5Years 5
	nt > nt.additionalNotes 10
	nt.additionalNotes > nt.additionalNotes.additDisclosuresIfFinStatmntDoesNotPresentTrueAndFairView 1
	nt > nt.otherInfo 12
	nt.otherInfo > nt.otherInfo.contingLiab 1
	nt > nt.assocComp 13
	nt.assocComp > nt.assocComp.parentsNameSmall 3.1
	nt > nt.relationships 14
	nt.relationships > nt.relationships.creditsToMembers 9
	nt > nt.directorsSign 15
	nt.directorsSign > nt.directorsSign.place 1
	nt.directorsSign > nt.directorsSign.date 2
	nt.directorsSign > nt.directorsSign.type 3
	nt.directorsSign.type > nt.directorsSign.type.name 1
	nt.directorsSign.type > nt.directorsSign.person 2
	nt.directorsSign.person > nt.directorsSign.person.name 3
	nt.directorsSign.person > nt.directorsSign.person.otherattributes 5
	nt > nt.employeesAveragePeriod 16
	""",
)
"""The Anhang, with the tables whose dimensions take positions of the Bilanz: two parents for
nt.isInfo.reasonsGoodwillAmortisationsLonger5Years and for bs.ass.fixAss, as in the package."""
GCD_ARCS = _arcs(
	GCD_PREFIX,
	"""
	genInfo > genInfo.doc 1
	genInfo.doc > genInfo.doc.id 1
	genInfo.doc.id > genInfo.doc.id.generationDate 1
	genInfo > genInfo.report 2
	genInfo.report > genInfo.report.id 1
	genInfo.report.id > genInfo.report.id.reportType 1
	genInfo.report.id.reportType > genInfo.report.id.reportType.reportType.JA 6
	genInfo.report.id > genInfo.report.id.reportStatus.approvalAndDisclosureDate 1.5
	genInfo.report.id.reportStatus.approvalAndDisclosureDate > genInfo.report.id.reportStatus.reportStatus.dateofapproval 1
	genInfo.report.id > genInfo.report.id.reportStatus 2
	genInfo.report.id.reportStatus > genInfo.report.id.reportStatus.reportStatus.E 2
	genInfo.report.id > genInfo.report.id.revisionStatus 2.5
	genInfo.report.id.revisionStatus > genInfo.report.id.revisionStatus.revisionStatus.E 1
	genInfo.report.id.revisionStatus > genInfo.report.id.revisionStatus.revisionStatus.B 2
	genInfo.report.id.revisionStatus > genInfo.report.id.revisionStatus.revisionStatus.G 3
	genInfo.report.id.revisionStatus > genInfo.report.id.revisionStatus.revisionStatus.BG 4
	genInfo.report.id.revisionStatus > genInfo.report.id.revisionStatus.revisionStatus.I 5
	genInfo.report.id.revisionStatus > genInfo.report.id.revisionStatus.revisionStatus.sK 7
	genInfo.report.id > genInfo.report.id.reportElement 3
	genInfo.report.id.reportElement > genInfo.report.id.reportElement.reportElements.B 2
	genInfo.report.id.reportElement > genInfo.report.id.reportElement.reportElements.H 6.5
	genInfo.report.id.reportElement > genInfo.report.id.reportElement.reportElements.SA 14
	genInfo.report.id > genInfo.report.id.reportElement.allocation.genInfo 4.25
	genInfo.report.id.reportElement.allocation.genInfo > genInfo.report.id.reportElement.allocation.genInfo.toBalance 1
	genInfo.report.id > genInfo.report.id.reportElement.allocation.notesMicroBilG 4.26
	genInfo.report.id.reportElement.allocation.notesMicroBilG > genInfo.report.id.reportElement.allocation.notesMicroBilG.toBalance 1
	genInfo.report.id > genInfo.report.id.reportElement.allocation.contingencies 4.3
	genInfo.report.id.reportElement.allocation.contingencies > genInfo.report.id.reportElement.allocation.contingencies.toBalance 1
	genInfo.report.id.reportElement.allocation.contingencies > genInfo.report.id.reportElement.allocation.contingencies.inNotes 2
	genInfo.report.id > genInfo.report.id.statementType 5
	genInfo.report.id.statementType > genInfo.report.id.statementType.statementType.E 1
	genInfo.report.id > genInfo.report.id.incomeStatementendswithBalProfit 7.5
	genInfo.report.id > genInfo.report.id.accountingStandard 8
	genInfo.report.id.accountingStandard > genInfo.report.id.accountingStandard.accountingStandard.HGBM 1.5
	genInfo.report.id > genInfo.report.id.specialAccountingStandard 8.5
	genInfo.report.id.specialAccountingStandard > genInfo.report.id.specialAccountingStandard.K 1
	genInfo.report.id > genInfo.report.id.mainAccountingStandard 8.6
	genInfo.report.id.mainAccountingStandard > genInfo.report.id.specialAccountingStandard.K 1
	genInfo.report.id > genInfo.report.id.incomeStatementFormat 9
	genInfo.report.id.incomeStatementFormat > genInfo.report.id.incomeStatementFormat.incomeStatementFormat.GKV 1
	genInfo.report.id.incomeStatementFormat > genInfo.report.id.incomeStatementFormat.incomeStatementFormat.UKV 2
	genInfo.report.id > genInfo.report.id.consolidationRange 10
	genInfo.report.id.consolidationRange > genInfo.report.id.consolidationRange.consolidationRange.EA 1
	genInfo.report.id > genInfo.report.id.accordingTo 12
	genInfo.report.id.accordingTo > genInfo.report.id.accordingTo.idNo 2
	genInfo.report.id.accordingTo.idNo > genInfo.company.id.idNo.type.companyId.HRN 1
	genInfo.report > genInfo.report.period 1.5
	genInfo.report.period > genInfo.report.period.fiscalYearBegin 3
	genInfo.report.period > genInfo.report.period.fiscalYearEnd 4
	genInfo.report.period > genInfo.report.period.balSheetClosingDate 5
	genInfo.report.period > genInfo.report.period.fiscalPreviousYearBegin 6
	genInfo.report.period > genInfo.report.period.fiscalPreviousYearEnd 7
	genInfo.report.period > genInfo.report.period.balSheetClosingDatePreviousYear 8
	genInfo.report > genInfo.report.audit 2
	genInfo.report.audit > genInfo.report.audit.noAudit 0.5
	genInfo.report.audit.noAudit > genInfo.report.audit.noAudit.noAuditRequi 1
	genInfo > genInfo.company 3
	genInfo.company > genInfo.company.id 1
	genInfo.company.id > genInfo.company.id.name 1
	genInfo.company.id > genInfo.company.id.legalStatus 2
	genInfo.company.id.legalStatus > genInfo.company.id.legalStatus.legalStatus.GMBH 2.08
	genInfo.company.id > genInfo.company.id.FoundationDate 5
	genInfo.company.id > genInfo.company.id.Incorporation 6
	genInfo.company.id.Incorporation > genInfo.company.id.Incorporation.Type 0.5
	genInfo.company.id.Incorporation.Type > genInfo.company.id.Incorporation.Type.Type.HR 1
	genInfo.company.id.Incorporation > genInfo.company.id.Incorporation.court 5
	genInfo.company.id > genInfo.company.id.sizeClass 8
	genInfo.company.id.sizeClass > genInfo.company.id.sizeClass.sizeClass.KK 3
	genInfo.company.id.sizeClass > genInfo.company.id.sizeClass.sizeClass.KstK 3.5
	genInfo.company.id > genInfo.company.id.reportedSizeClassBs 8.5
	genInfo.company.id.reportedSizeClassBs > genInfo.company.id.reportedSizeClassBs.K 3
	genInfo.company.id.reportedSizeClassBs > genInfo.company.id.reportedSizeClassBs.Kst 4
	genInfo.company.id > genInfo.company.id.location 9
	genInfo.company.id.location > genInfo.company.id.location.street 1
	genInfo.company.id.location > genInfo.company.id.location.houseNo 2
	genInfo.company.id.location > genInfo.company.id.location.zipCode 3
	genInfo.company.id.location > genInfo.company.id.location.city 4
	genInfo.company.id.location > genInfo.company.id.location.country 5
	genInfo.company.id > genInfo.company.id.idNo 9.5
	genInfo.company.id.idNo > genInfo.company.id.idNo.type.companyId.HRN 1
	genInfo.company.id > genInfo.company.id.CompanyStatus 13
	genInfo.company.id.CompanyStatus > genInfo.company.id.CompanyStatus.companyStatus.L 3
	genInfo.company > genInfo.company.disclosureCriterion 1.5
	genInfo.company.disclosureCriterion > genInfo.company.disclosureCriterion.scope 2
	genInfo.company.disclosureCriterion.scope > genInfo.company.disclosureCriterion.scope.CapitalMarketOrientationHGBs264d 1
	""",
)
CALCULATION_ARCS = _arcs(
	GAAP_PREFIX,
	"""
	bs.ass > bs.ass.fixAss 1
	bs.ass.fixAss > bs.ass.fixAss.intan 1
	bs.ass.fixAss > bs.ass.fixAss.tan 1
	bs.ass.fixAss > bs.ass.fixAss.fin 1
	bs.ass > bs.ass.currAss 1
	bs.ass.currAss > bs.ass.currAss.inventory 1
	bs.ass.currAss > bs.ass.currAss.receiv 1
	bs.ass.currAss > bs.ass.currAss.securities 1
	bs.ass.currAss > bs.ass.currAss.cashEquiv 1
	bs.ass > bs.ass.prepaidExp 1
	bs.ass > bs.ass.defTax 1
	bs.ass > bs.ass.deficitNotCoveredByCapital 1
	bs.ass > bs.ass.SurplusFromOffsetting 1
	bs.eqLiab > bs.eqLiab.equity 1
	bs.eqLiab.equity > bs.eqLiab.equity.subscribed 1
	bs.eqLiab.equity.subscribed > bs.eqLiab.equity.subscribed.ownSharesdeducted -1
	bs.eqLiab.equity.subscribed > bs.eqLiab.equity.subscribed.unpaidCap -1
	bs.eqLiab.equity.subscribed > bs.eqLiab.equity.subscribed.corp 1
	bs.eqLiab.equity > bs.eqLiab.equity.capRes 1
	bs.eqLiab.equity > bs.eqLiab.equity.revenueRes 1
	bs.eqLiab.equity > bs.eqLiab.equity.retainedEarnings 1
	bs.eqLiab.equity > bs.eqLiab.equity.netIncome 1
	bs.eqLiab.equity > bs.eqLiab.equity.profitLoss 1
	bs.eqLiab.equity > bs.eqLiab.equity.deficitNotCoveredByCapital 1
	bs.eqLiab > bs.eqLiab.accruals 1
	bs.eqLiab > bs.eqLiab.liab 1
	bs.eqLiab > bs.eqLiab.defIncome 1
	bs.eqLiab > bs.eqLiab.defTax 1
	""",
	weighted=True,
)
PRESENTATION = MappingProxyType(
	{
		BALANCE_SHEET: BALANCE_SHEET_ARCS,
		NOTES_BELOW_BALANCE_SHEET: NOTES_BELOW_BALANCE_SHEET_ARCS,
		NOTES: NOTES_ARCS,
		GCD: GCD_ARCS,
	}
)


@cache
def view(name: View) -> Taxonomy:
	"""The mini taxonomy in a view of the profile DISCLOSURE, with the entry points of that view."""
	return Taxonomy(
		version=VERSION.version,
		view=name,
		entry_points=name.entry_points(VERSION),
		namespaces=NAMESPACES,
		concepts=CONCEPTS,
		roles=ROLES,
		labels=MappingProxyType({}),
		presentation=MappingProxyType({role: Network(role, arcs) for role, arcs in PRESENTATION.items()}),
		calculation=MappingProxyType({BALANCE_SHEET: Network(BALANCE_SHEET, CALCULATION_ARCS)}),
		definition=MappingProxyType({}),
	)
