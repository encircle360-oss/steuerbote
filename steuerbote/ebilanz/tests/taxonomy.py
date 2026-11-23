"""The mini taxonomy of steuerbote/xbrl/tests/mini.py with the positions an E-Bilanz of a GmbH reads beyond them.

The tests of steuerbote/ebilanz run against the fiscal view of that mini taxonomy, which F5 keeps for the tests of
steuerbote/xbrl, extended in place of a package of its own: the concepts below with their labels and arcs, in the
form the HGB-Taxonomie 6.9 gives them (de-gaap-ci-2025-04-01, de-gcd-2025-04-01). They are what the modules of the
E-Bilanz read and the mini taxonomy leaves out: the Jahresüberschuss and the steuerlicher Ausgleichsposten of the
Eigenkapital, the Bilanzgewinn, the Rückstellungen for an Überleitung, an Auffangposition, the Sammelposten of the GuV,
the Betriebsvermögensvergleich with Entnahmen and Einlagen, every column of the value development of the
Anlagenspiegel with its calculation, the entries of the Überleitungsrechnung, and the GCD a report of a GmbH fills.
The names, requirements, legal forms and weights are those of the package 6.9; the labels are invented where a test
needs none of the real ones.
"""

from dataclasses import replace
from decimal import Decimal
from functools import cache
from types import MappingProxyType

from steuerbote.xbrl.taxonomy import (
	DOMAIN_MEMBER,
	LABEL,
	Arc,
	Balance,
	Concept,
	Content,
	DefinitionArc,
	Fiscal,
	Kind,
	LegalForm,
	Network,
	Particle,
	PeriodType,
	Requirement,
	Taxonomy,
	View,
)
from steuerbote.xbrl.tests import mini

GAAP = "de-gaap-ci"
GCD = "de-gcd"
NAMESPACES = {GAAP: mini.GAAP_NS, GCD: mini.GCD_NS}
MONETARY = "xbrli:monetaryItemType"
STRING = "xbrli:stringItemType"
DATE = "xbrli:dateItemType"
BOOLEAN = "xbrli:booleanItemType"
QNAME = "xbrli:QNameItemType"
INSTANT = PeriodType.INSTANT
DURATION = PeriodType.DURATION
DEBIT = Balance.DEBIT
CREDIT = Balance.CREDIT
MUSS = Requirement.MUSSFELD
SUMME = Requirement.SUMMENMUSSFELD
RECHNERISCH = Requirement.RECHNERISCH_NOTWENDIG
KST = frozenset({LegalForm.KST})
PARTNERSHIPS = frozenset({LegalForm.EU, LegalForm.PG})
EVERY_FORM = frozenset(LegalForm)
NOT_COMMERCIAL = frozenset({"handelsrechtlich"})


def _concept(
	name: str,
	*,
	kind: Kind = Kind.ITEM,
	item_type: str | None = MONETARY,
	period: PeriodType | None = INSTANT,
	balance: Balance | None = None,
	requirement: Requirement | None = None,
	forms: frozenset[LegalForm] = EVERY_FORM,
	not_permitted: frozenset[str] = frozenset(),
	substitution: str | None = None,
	content: Content | None = None,
	abstract: bool = False,
) -> Concept:
	prefix = name.partition(":")[0]
	return Concept(
		name=name,
		namespace=NAMESPACES[prefix],
		kind=kind,
		substitution_group=substitution or ("xbrli:tuple" if kind is Kind.TUPLE else "xbrli:item"),
		item_type=None if kind is Kind.TUPLE else item_type,
		period_type=None if kind is Kind.TUPLE else period,
		balance=balance,
		abstract=abstract,
		nillable=True,
		content=content,
		fiscal=Fiscal(
			requirement=requirement,
			legal_forms=forms,
			operating_results=frozenset({"neutral"}),
			not_permitted_for=not_permitted,
		),
	)


def gaap(name: str) -> str:
	return f"{GAAP}:{name}"


def gcd(name: str) -> str:
	return f"{GCD}:{name}"


def _sequence(*parts: tuple[str, int, int | None]) -> Content:
	return Content("sequence", 1, 1, tuple(Particle(name, low, high) for name, low, high in parts))


def _choice_values(head: str, label: str, values: dict[str, Requirement | None], **options) -> dict:
	"""A tuple with a choice of the substitutes of its abstract head, each value a string item (Leitfaden A.8)."""
	head_name = f"{head}.head"
	found = {
		head: (
			_concept(
				head,
				kind=Kind.TUPLE,
				content=Content("choice", 1, options.pop("maximum", 1), (Particle(head_name, 1, 1),)),
				**options,
			),
			label,
		),
		head_name: (
			_concept(head_name, item_type=STRING, period=DURATION, abstract=True, forms=frozenset()),
			f"{label} (Auswahl)",
		),
	}
	for value, requirement in values.items():
		found[f"{head}.{value}"] = (
			_concept(
				f"{head}.{value}",
				item_type=STRING,
				period=DURATION,
				requirement=requirement,
				substitution=head_name,
			),
			f"{label}: {value.rpartition('.')[2]}",
		)
	return found


BALANCE_SHEET_CONCEPTS = {
	gaap("bs.ass.deficitNotCoveredByCapital"): (
		_concept(gaap("bs.ass.deficitNotCoveredByCapital"), balance=DEBIT),
		"Nicht durch Eigenkapital gedeckter Fehlbetrag",
	),
	gaap("bs.ass.fixAss.intan.other"): (
		_concept(gaap("bs.ass.fixAss.intan.other"), balance=DEBIT, requirement=RECHNERISCH),
		"Immaterielle Vermögensgegenstände, nicht zuordenbar",
	),
	gaap("bs.eqLiab.equity.retainedEarnings"): (
		_concept(gaap("bs.eqLiab.equity.retainedEarnings"), balance=CREDIT, requirement=MUSS, forms=KST),
		"Eigenkapital, Gewinn-/Verlustvortrag - bei Kapitalgesellschaften",
	),
	gaap("bs.eqLiab.equity.profitLoss"): (
		_concept(gaap("bs.eqLiab.equity.profitLoss"), balance=CREDIT, requirement=MUSS, forms=KST),
		"Eigenkapital, Bilanzgewinn / Bilanzverlust (Bilanz) - bei Kapitalgesellschaften",
	),
	gaap("bs.eqLiab.equity.netIncome.taxBalanceGenerally.finalPrev"): (
		_concept(
			gaap("bs.eqLiab.equity.netIncome.taxBalanceGenerally.finalPrev"),
			balance=CREDIT,
			requirement=MUSS,
			not_permitted=NOT_COMMERCIAL,
		),
		"steuerlicher Ausgleichsposten des letzten Stichtags",
	),
	gaap("bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts"): (
		_concept(
			gaap("bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts"),
			balance=CREDIT,
			requirement=MUSS,
			not_permitted=NOT_COMMERCIAL,
		),
		"steuerliches Mehr-/Minderergebnis lfd. Jahr gegenüber HB",
	),
	gaap("bs.eqLiab.accruals"): (
		_concept(gaap("bs.eqLiab.accruals"), balance=CREDIT, requirement=SUMME),
		"Rückstellungen",
	),
	gaap("bs.eqLiab.accruals.other"): (
		_concept(gaap("bs.eqLiab.accruals.other"), balance=CREDIT, requirement=MUSS),
		"sonstige Rückstellungen",
	),
	gaap("bs.eqLiab.liab.bank.upTo1year.shareholders"): (
		_concept(gaap("bs.eqLiab.liab.bank.upTo1year.shareholders"), balance=CREDIT),
		"davon mit einer Restlaufzeit bis zu einem Jahr, davon gegenüber Gesellschaftern",
	),
}
"""Beyond the Bilanz of the mini taxonomy: the deficit, an Auffangposition, the Gewinnvortrag, the Bilanzgewinn, the
parts of the steuerlicher Ausgleichsposten and the Rückstellungen."""

BALANCE_SHEET_ARCS = (
	("bs.ass", "bs.ass.deficitNotCoveredByCapital", 1),
	("bs.ass.fixAss.intan", "bs.ass.fixAss.intan.other", 1),
	("bs.eqLiab.equity", "bs.eqLiab.equity.retainedEarnings", 1),
	("bs.eqLiab.equity", "bs.eqLiab.equity.profitLoss", 1),
	(
		"bs.eqLiab.equity.netIncome.taxBalanceGenerally",
		"bs.eqLiab.equity.netIncome.taxBalanceGenerally.finalPrev",
		1,
	),
	(
		"bs.eqLiab.equity.netIncome.taxBalanceGenerally",
		"bs.eqLiab.equity.netIncome.taxBalanceGenerally.transferDiffTaxAccounts",
		1,
	),
	("bs.eqLiab", "bs.eqLiab.accruals", 1),
	("bs.eqLiab.accruals", "bs.eqLiab.accruals.other", 1),
)
"""Each in the presentation and in the calculation of the Bilanz, with its weight."""
BALANCE_SHEET_DAVON = (("bs.eqLiab.liab.bank.upTo1year", "bs.eqLiab.liab.bank.upTo1year.shareholders"),)
"""A davon position under a davon position, in the presentation only, as „davon Optionsanleihen“ under „davon mit einer
Restlaufzeit bis zu einem Jahr“ of the Anleihen in the package 6.9."""

INCOME_STATEMENT_CONCEPTS = {
	gaap("is.netIncome.collItemChangeProfitHbst"): (
		_concept(
			gaap("is.netIncome.collItemChangeProfitHbst"),
			period=DURATION,
			balance=CREDIT,
			requirement=RECHNERISCH,
		),
		"Sammelposten für Gewinnänderungen aus der Überleitungsrechnung",
	),
	gaap("is.netIncome.netSales.statutoryDuties"): (
		_concept(gaap("is.netIncome.netSales.statutoryDuties"), period=DURATION, balance=CREDIT),
		"Umsatzerlöse, davon aus satzungsmäßigen Aufgaben",
	),
	gaap("is.netIncome.netSales.statutoryDuties.membershipFees"): (
		_concept(
			gaap("is.netIncome.netSales.statutoryDuties.membershipFees"), period=DURATION, balance=CREDIT
		),
		"davon aus satzungsmäßigen Aufgaben, Mitgliedsbeiträge",
	),
}
INCOME_STATEMENT_ARCS = (("is.netIncome", "is.netIncome.collItemChangeProfitHbst", 1),)
INCOME_STATEMENT_DAVON = (
	("is.netIncome.netSales", "is.netIncome.netSales.statutoryDuties", None),
	("is.netIncome.netSales.statutoryDuties", "is.netIncome.netSales.statutoryDuties.membershipFees", 1),
)
"""A davon position with positions of its own under it, which the calculation adds up to the davon position only, as
„davon Erträge zur Erfüllung satzungsmäßiger Aufgaben“ of the sonstige betriebliche Erträge in the package 6.9."""

BVV_CONCEPTS = {
	gaap("BVV"): (
		_concept(gaap("BVV"), item_type=STRING, period=DURATION, abstract=True),
		"Steuerlicher Betriebsvermögensvergleich",
	),
	gaap("BVV.profitLoss"): (
		_concept(gaap("BVV.profitLoss"), period=DURATION, requirement=SUMME),
		"Jahresüberschuss/-fehlbetrag (BVV)",
	),
	gaap("BVV.profitLoss.assetsCurrentYear"): (
		_concept(gaap("BVV.profitLoss.assetsCurrentYear"), period=DURATION, balance=CREDIT, requirement=MUSS),
		"Betriebsvermögen zum Ende des Wirtschaftsjahres",
	),
	gaap("BVV.profitLoss.assetsPreviousYear"): (
		_concept(
			gaap("BVV.profitLoss.assetsPreviousYear"), period=DURATION, balance=CREDIT, requirement=SUMME
		),
		"Betriebsvermögen zum Ende des vorangegangenen Wirtschaftsjahres (nach Kapitalanpassung)",
	),
	gaap("BVV.profitLoss.assetsPreviousYear.assets"): (
		_concept(
			gaap("BVV.profitLoss.assetsPreviousYear.assets"),
			period=DURATION,
			balance=CREDIT,
			requirement=MUSS,
		),
		"Betriebsvermögen zum Ende des vorangegangenen Wirtschaftsjahres",
	),
	gaap("BVV.profitLoss.assetsPreviousYear.capAdjustments"): (
		_concept(
			gaap("BVV.profitLoss.assetsPreviousYear.capAdjustments"),
			period=DURATION,
			balance=CREDIT,
			requirement=MUSS,
		),
		"Kapitalanpassung",
	),
	gaap("BVV.profitLoss.withdrawalDistrib"): (
		_concept(gaap("BVV.profitLoss.withdrawalDistrib"), period=DURATION, balance=DEBIT, requirement=MUSS),
		"Entnahmen / Ausschüttungen im laufenden Wirtschaftsjahr",
	),
	gaap("BVV.profitLoss.contribution"): (
		_concept(gaap("BVV.profitLoss.contribution"), period=DURATION, balance=CREDIT, requirement=MUSS),
		"Einlagen / Kapitalzuführungen im laufenden Wirtschaftsjahr",
	),
	gaap("BVV.profitLoss.EStG6b"): (
		_concept(
			gaap("BVV.profitLoss.EStG6b"),
			period=DURATION,
			balance=CREDIT,
			requirement=MUSS,
			forms=PARTNERSHIPS,
		),
		"Kapitaländerung durch Übertragung einer § 6b EStG Rücklage",
	),
}
"""The Betriebsvermögensvergleich of the package 6.9, in place of the two positions of the mini taxonomy."""

BVV_ARCS = (
	("BVV.profitLoss", "BVV.profitLoss.assetsCurrentYear", 1),
	("BVV.profitLoss", "BVV.profitLoss.assetsPreviousYear", -1),
	("BVV.profitLoss.assetsPreviousYear", "BVV.profitLoss.assetsPreviousYear.assets", 1),
	("BVV.profitLoss.assetsPreviousYear", "BVV.profitLoss.assetsPreviousYear.capAdjustments", 1),
	("BVV.profitLoss", "BVV.profitLoss.withdrawalDistrib", 1),
	("BVV.profitLoss", "BVV.profitLoss.contribution", -1),
	("BVV.profitLoss", "BVV.profitLoss.EStG6b", -1),
)

FIXED_ASSET_COLUMNS = {
	"all": (SUMME, "Buchwert zum Ende der Periode"),
	"gross": (SUMME, "Anschaffungs- und Herstellungskosten zum Ende der Periode"),
	"grossCost.beginning": (MUSS, "Anschaffungs- und Herstellungskosten zum Anfang der Periode"),
	"gross.addition": (MUSS, "Anschaffungs- und Herstellungskosten, Zugänge"),
	"gross.release": (RECHNERISCH, "Anschaffungs- und Herstellungskosten, Abgänge"),
	"gross.movements": (MUSS, "Anschaffungs- und Herstellungskosten, Umbuchungen"),
	"accDepr": (SUMME, "Kumulierte Abschreibungen zum Ende der Periode"),
	"accDepr.beginning": (MUSS, "Kumulierte Abschreibungen zum Anfang der Periode"),
	"accDepr.DeprPeriod": (SUMME, "Abschreibungen, Sonderabschreibungen und sonstige Abzüge der Periode"),
	"accDepr.DeprPeriod.regular": (MUSS, "planmäßige Abschreibung"),
	"accDepr.DeprPeriod.extraordinary": (MUSS, "außerplanmäßige Abschreibung"),
	"accDepr.DeprPeriod.impairment": (MUSS, "Sonderabschreibung"),
	"accDepr.DeprPeriod.EStG7g_2": (MUSS, "Herabsetzungsbetrag nach § 7g Abs. 2 EStG"),
	"accDepr.DeprPeriod.EStG6b_3": (MUSS, "Abzugsbetrag nach § 6b EStG"),
	"accDepr.DeprPeriod.misc": (RECHNERISCH, "AfA nicht zuordenbar"),
	"accDepr.addition": (MUSS, "Kumulierte Abschreibungen, erfolgsneutrale Zugänge"),
	"accDepr.release": (MUSS, "Kumulierte Abschreibungen, erfolgsneutrale Abgänge"),
	"accDepr.movements": (MUSS, "Kumulierte Abschreibungen, Umbuchungen"),
	"revaluation": (MUSS, "Zuschreibungen"),
}
"""The columns of the value development of the Anlagenspiegel (brutto) in the package 6.9, with their requirement."""

FIXED_ASSET_CALCULATION = (
	("all", "gross", 1),
	("all", "accDepr", -1),
	("all", "revaluation", 1),
	("gross", "grossCost.beginning", 1),
	("gross", "gross.addition", 1),
	("gross", "gross.release", -1),
	("gross", "gross.movements", 1),
	("accDepr", "accDepr.beginning", 1),
	("accDepr", "accDepr.DeprPeriod", 1),
	("accDepr", "accDepr.addition", 1),
	("accDepr", "accDepr.release", -1),
	("accDepr", "accDepr.movements", 1),
	("accDepr.DeprPeriod", "accDepr.DeprPeriod.regular", 1),
	("accDepr.DeprPeriod", "accDepr.DeprPeriod.extraordinary", 1),
	("accDepr.DeprPeriod", "accDepr.DeprPeriod.impairment", 1),
	("accDepr.DeprPeriod", "accDepr.DeprPeriod.EStG7g_2", 1),
	("accDepr.DeprPeriod", "accDepr.DeprPeriod.EStG6b_3", 1),
	("accDepr.DeprPeriod", "accDepr.DeprPeriod.misc", 1),
)
"""The calculation of the columns in the Anhang, as de-gaap-ci-2025-04-01-dimensions-calculation-… has it."""

TRANSFER = "hbst.transfer"
TRANSFER_CONCEPTS = {
	gaap(TRANSFER): (
		_concept(
			gaap(TRANSFER),
			kind=Kind.TUPLE,
			content=_sequence(
				(gaap("hbst.transfer.kind"), 1, 1),
				(gaap("hbst.transfer.bsAss"), 0, None),
				(gaap("hbst.transfer.bsEqLiab"), 0, None),
				(gaap("hbst.transfer.isChangeNetIncome"), 0, None),
			),
		),
		"Überleitung Handelsbilanzposten auf Steuerbilanzposten",
	),
	**_choice_values(
		gaap("hbst.transfer.kind"),
		"Art der Überleitung",
		{"reclassification": None, "changeValue": None, "reclassificationChangeValue": None},
	),
	gaap("hbst.transfer.bsAss"): (
		_concept(
			gaap("hbst.transfer.bsAss"),
			kind=Kind.TUPLE,
			content=_sequence(
				(gaap("hbst.transfer.bsAss.name"), 1, 1),
				(gaap("hbst.transfer.bsAss.changeValueActualPeriod"), 0, 1),
				(gaap("hbst.transfer.bsAss.changeValuePreviousPeriod"), 0, 1),
			),
		),
		"Aktivposition",
	),
	gaap("hbst.transfer.bsAss.name"): (
		_concept(gaap("hbst.transfer.bsAss.name"), item_type=QNAME, period=DURATION),
		"Name der Aktivposition",
	),
	gaap("hbst.transfer.bsAss.changeValueActualPeriod"): (
		_concept(gaap("hbst.transfer.bsAss.changeValueActualPeriod"), period=DURATION),
		"Wertänderung aus dem aktuellen Wirtschaftsjahr",
	),
	gaap("hbst.transfer.bsAss.changeValuePreviousPeriod"): (
		_concept(gaap("hbst.transfer.bsAss.changeValuePreviousPeriod"), period=DURATION),
		"Wertänderung aus Vorperioden",
	),
	gaap("hbst.transfer.bsEqLiab"): (
		_concept(
			gaap("hbst.transfer.bsEqLiab"),
			kind=Kind.TUPLE,
			content=_sequence(
				(gaap("hbst.transfer.bsEqLiab.name"), 1, 1),
				(gaap("hbst.transfer.bsEqLiab.changeValueActualPeriod"), 0, 1),
				(gaap("hbst.transfer.bsEqLiab.changeValuePreviousPeriod"), 0, 1),
			),
		),
		"Passivposition",
	),
	gaap("hbst.transfer.bsEqLiab.name"): (
		_concept(gaap("hbst.transfer.bsEqLiab.name"), item_type=QNAME, period=DURATION),
		"Name der Passivposition",
	),
	gaap("hbst.transfer.bsEqLiab.changeValueActualPeriod"): (
		_concept(gaap("hbst.transfer.bsEqLiab.changeValueActualPeriod"), period=DURATION),
		"Wertänderung aus dem aktuellen Wirtschaftsjahr",
	),
	gaap("hbst.transfer.bsEqLiab.changeValuePreviousPeriod"): (
		_concept(gaap("hbst.transfer.bsEqLiab.changeValuePreviousPeriod"), period=DURATION),
		"Wertänderung aus Vorperioden",
	),
	gaap("hbst.transfer.isChangeNetIncome"): (
		_concept(
			gaap("hbst.transfer.isChangeNetIncome"),
			kind=Kind.TUPLE,
			content=_sequence(
				(gaap("hbst.transfer.isChangeNetIncome.name"), 1, 1),
				(gaap("hbst.transfer.isChangeNetIncome.changeValueActualPeriod"), 1, 1),
			),
		),
		"GuV-Posten mit erfolgswirksamen Abweichungen",
	),
	gaap("hbst.transfer.isChangeNetIncome.name"): (
		_concept(gaap("hbst.transfer.isChangeNetIncome.name"), item_type=QNAME, period=DURATION),
		"GuV-Posten",
	),
	gaap("hbst.transfer.isChangeNetIncome.changeValueActualPeriod"): (
		_concept(gaap("hbst.transfer.isChangeNetIncome.changeValueActualPeriod"), period=DURATION),
		"Wertänderung aus dem aktuellen Wirtschaftsjahr",
	),
}
"""The Überleitungsrechnung of the package 6.9 but the entries of the Ergebnisverwendung, in place of the tuple of the
mini taxonomy."""

TRANSFER_ARCS = (
	("hbst.transfer", "hbst.transfer.kind"),
	("hbst.transfer.kind", "hbst.transfer.kind.reclassification"),
	("hbst.transfer.kind", "hbst.transfer.kind.changeValue"),
	("hbst.transfer.kind", "hbst.transfer.kind.reclassificationChangeValue"),
	("hbst.transfer", "hbst.transfer.bsAss"),
	("hbst.transfer.bsAss", "hbst.transfer.bsAss.name"),
	("hbst.transfer.bsAss", "hbst.transfer.bsAss.changeValueActualPeriod"),
	("hbst.transfer.bsAss", "hbst.transfer.bsAss.changeValuePreviousPeriod"),
	("hbst.transfer", "hbst.transfer.bsEqLiab"),
	("hbst.transfer.bsEqLiab", "hbst.transfer.bsEqLiab.name"),
	("hbst.transfer.bsEqLiab", "hbst.transfer.bsEqLiab.changeValueActualPeriod"),
	("hbst.transfer.bsEqLiab", "hbst.transfer.bsEqLiab.changeValuePreviousPeriod"),
	("hbst.transfer", "hbst.transfer.isChangeNetIncome"),
	("hbst.transfer.isChangeNetIncome", "hbst.transfer.isChangeNetIncome.name"),
	("hbst.transfer.isChangeNetIncome", "hbst.transfer.isChangeNetIncome.changeValueActualPeriod"),
)

GCD_CONCEPTS = {
	**_choice_values(
		gcd("genInfo.report.id.revisionStatus"),
		"Status des Berichts",
		dict.fromkeys(("revisionStatus.E", "revisionStatus.B", "revisionStatus.G", "revisionStatus.K")),
		requirement=MUSS,
	),
	gcd("genInfo.report.id.reportElement.reportElements.EV"): (
		_concept(
			gcd("genInfo.report.id.reportElement.reportElements.EV"),
			item_type=STRING,
			period=DURATION,
			requirement=MUSS,
			forms=frozenset({LegalForm.KST, LegalForm.PG}),
			substitution=gcd("genInfo.report.id.reportElement.head"),
		),
		"Berichtsbestandteile, Ergebnisverwendung",
	),
	gcd("genInfo.report.id.reportElement.reportElements.transmissionNotYetPossible"): (
		_concept(
			gcd("genInfo.report.id.reportElement.reportElements.transmissionNotYetPossible"),
			item_type=STRING,
			period=DURATION,
			requirement=MUSS,
		),
		"Erläuterung, warum die Übermittlung der Kontennachweise noch nicht möglich ist",
	),
	gcd("genInfo.report.id.incomeStatementendswithBalProfit"): (
		_concept(
			gcd("genInfo.report.id.incomeStatementendswithBalProfit"),
			item_type=BOOLEAN,
			period=DURATION,
			requirement=MUSS,
		),
		"Bilanz enthält Ausweis des Bilanzgewinns/Bilanzverlustes",
	),
	**_choice_values(
		gcd("genInfo.report.id.specialAccountingStandard"),
		"Branchen",
		dict.fromkeys(("K", "LUF")),
		requirement=MUSS,
		maximum=None,
	),
	**_choice_values(
		gcd("genInfo.report.id.consolidationRange"),
		"Konsolidierungsumfang",
		dict.fromkeys(("consolidationRange.EA", "consolidationRange.KA")),
		requirement=MUSS,
	),
	**{
		gcd(f"genInfo.report.period.{name}"): (
			_concept(gcd(f"genInfo.report.period.{name}"), item_type=DATE, period=DURATION, requirement=MUSS),
			label,
		)
		for name, label in (
			("fiscalPreviousYearBegin", "Beginn des Wirtschaftsjahres (Vorjahr)"),
			("fiscalPreviousYearEnd", "Ende des Wirtschaftsjahres (Vorjahr)"),
			("balSheetClosingDatePreviousYear", "Bilanzstichtag (Vorjahr)"),
		)
	},
	**{
		gcd(f"genInfo.company.id.location.{name}"): (
			_concept(
				gcd(f"genInfo.company.id.location.{name}"),
				item_type=STRING,
				period=DURATION,
				requirement=MUSS,
			),
			label,
		)
		for name, label in (
			("street", "Firmensitz, Straße"),
			("zipCode", "Firmensitz, Postleitzahl"),
			("city", "Firmensitz, Ort"),
			("country", "Firmensitz, Land"),
		)
	},
	gcd("genInfo.company.id.business"): (
		_concept(gcd("genInfo.company.id.business"), item_type=STRING, period=DURATION, requirement=MUSS),
		"Geschäftstätigkeit",
	),
	**_choice_values(
		gcd("genInfo.company.id.incomeClassification"),
		"Zuordnung zur Einkunftsart",
		dict.fromkeys(("trade", "selfEmployment")),
		requirement=MUSS,
	),
	**_choice_values(
		gcd("genInfo.company.id.domesticBranchOfForeignCompany"),
		"Inländische Betriebsstätte eines ausländischen Unternehmens",
		dict.fromkeys(("other",)),
		requirement=MUSS,
	),
}
"""The GCD a report of a GmbH fills beyond the mini taxonomy, with the requirements of the package 6.9."""

GCD_ARCS = (
	("genInfo", "genInfo.report.id.revisionStatus"),
	*(
		("genInfo.report.id.revisionStatus", f"genInfo.report.id.revisionStatus.revisionStatus.{value}")
		for value in ("E", "B", "G", "K")
	),
	("genInfo.report.id.reportElement", "genInfo.report.id.reportElement.reportElements.EV"),
	("genInfo", "genInfo.report.id.reportElement.reportElements.transmissionNotYetPossible"),
	("genInfo", "genInfo.report.id.incomeStatementendswithBalProfit"),
	("genInfo", "genInfo.report.id.specialAccountingStandard"),
	*(
		(
			"genInfo.report.id.specialAccountingStandard",
			f"genInfo.report.id.specialAccountingStandard.{value}",
		)
		for value in ("K", "LUF")
	),
	("genInfo", "genInfo.report.id.consolidationRange"),
	*(
		("genInfo.report.id.consolidationRange", f"genInfo.report.id.consolidationRange.{value}")
		for value in ("consolidationRange.EA", "consolidationRange.KA")
	),
	("genInfo", "genInfo.report.period.fiscalPreviousYearBegin"),
	("genInfo", "genInfo.report.period.fiscalPreviousYearEnd"),
	("genInfo", "genInfo.report.period.balSheetClosingDatePreviousYear"),
	*(
		("genInfo", f"genInfo.company.id.location.{name}")
		for name in ("street", "zipCode", "city", "country")
	),
	("genInfo", "genInfo.company.id.business"),
	("genInfo", "genInfo.company.id.incomeClassification"),
	*(
		("genInfo.company.id.incomeClassification", f"genInfo.company.id.incomeClassification.{value}")
		for value in ("trade", "selfEmployment")
	),
	("genInfo", "genInfo.company.id.domesticBranchOfForeignCompany"),
	(
		"genInfo.company.id.domesticBranchOfForeignCompany",
		"genInfo.company.id.domesticBranchOfForeignCompany.other",
	),
)


NOT_YET_POSSIBLE = gcd("genInfo.report.id.reportElement.reportElements.transmissionNotYetPossible")


@cache
def view() -> Taxonomy:
	"""The fiscal view of the mini taxonomy with the concepts and arcs above."""
	return _extended(mini.view())


@cache
def view_6_10() -> Taxonomy:
	"""The same on the mini taxonomy 6.10, the concepts in the namespaces of its modules, without the reason of 6.9
	for an E-Bilanz without Kontensalden, which 6.10 deletes (Änderungsnachweis zum Taxonomie-Update 2026, 2.)."""
	return _extended(mini.view(View.FISCAL, mini.VERSION_6_10), frozenset({NOT_YET_POSSIBLE}))


def _extended(base: Taxonomy, excluded: frozenset[str] = frozenset()) -> Taxonomy:
	"""A view of the mini taxonomy with the concepts and arcs above but the excluded ones, each concept in the
	namespace the view gives its module."""
	added = {
		name: (replace(concept, namespace=base.namespaces[concept.prefix]), label)
		for name, (concept, label) in {
			**BALANCE_SHEET_CONCEPTS,
			**INCOME_STATEMENT_CONCEPTS,
			**BVV_CONCEPTS,
			**TRANSFER_CONCEPTS,
			**GCD_CONCEPTS,
			**{
				gaap(name): (
					_concept(gaap(name), period=DURATION, requirement=requirement),
					label,
				)
				for name, (requirement, label) in FIXED_ASSET_COLUMNS.items()
			},
		}.items()
		if name not in excluded
	}
	concepts = {**base.concepts, **{name: concept for name, (concept, _) in added.items()}}
	labels = {name: dict(roles) for name, roles in base.labels.items()}
	for name, (_, label) in added.items():
		labels[name] = {LABEL: label}
	presentation = {role: list(network.arcs) for role, network in base.presentation.items()}
	calculation = {role: list(network.arcs) for role, network in base.calculation.items()}
	definition = {role: list(arcs) for role, arcs in base.definition.items()}

	for parent, child, weight in BALANCE_SHEET_ARCS:
		_add(presentation, mini.BALANCE_SHEET, gaap(parent), gaap(child))
		_add(calculation, mini.BALANCE_SHEET, gaap(parent), gaap(child), weight)
	for parent, child in BALANCE_SHEET_DAVON:
		_add(presentation, mini.BALANCE_SHEET, gaap(parent), gaap(child))
	for parent, child, weight in INCOME_STATEMENT_ARCS:
		_add(presentation, mini.INCOME_STATEMENT, gaap(parent), gaap(child))
		_add(calculation, mini.INCOME_STATEMENT, gaap(parent), gaap(child), weight)
	for parent, child, weight in INCOME_STATEMENT_DAVON:
		_add(presentation, mini.INCOME_STATEMENT, gaap(parent), gaap(child))
		if weight is not None:
			_add(calculation, mini.INCOME_STATEMENT, gaap(parent), gaap(child), weight)
	presentation[mini.TRANSFERS_TAX_ASSETS] = []
	calculation[mini.TRANSFERS_TAX_ASSETS] = []
	_add(presentation, mini.TRANSFERS_TAX_ASSETS, gaap("BVV"), gaap("BVV.profitLoss"))
	for parent, child, weight in BVV_ARCS:
		_add(presentation, mini.TRANSFERS_TAX_ASSETS, gaap(parent), gaap(child))
		_add(calculation, mini.TRANSFERS_TAX_ASSETS, gaap(parent), gaap(child), weight)
	presentation[mini.TRANSFERS_TO_TAX] = []
	for parent, child in TRANSFER_ARCS:
		_add(presentation, mini.TRANSFERS_TO_TAX, gaap(parent), gaap(child))
	for parent, child in GCD_ARCS:
		if gcd(child) not in excluded:
			_add(presentation, mini.GCD_ROLE, gcd(parent), gcd(child))

	calculation[mini.NOTES] = []
	for parent, child, weight in FIXED_ASSET_CALCULATION:
		_add(calculation, mini.NOTES, gaap(parent), gaap(child), weight)
	columns = {parent: [] for parent, _, _ in FIXED_ASSET_CALCULATION}
	for parent, child, _ in FIXED_ASSET_CALCULATION:
		columns[parent].append(child)
	table = [
		arc
		for arc in definition[mini.FIXED_ASSETS_TABLE]
		if not (arc.arcrole == DOMAIN_MEMBER and arc.source.startswith(gaap("")) and _is_column(arc))
	]
	order = len(table)
	presentation[mini.NOTES] = [
		arc
		for arc in presentation[mini.NOTES]
		if not (arc.parent in _COLUMN_PARENTS or arc.child in _COLUMNS)
	]
	for parent, child in (
		("piTitle.nt.ass.gross", "all"),
		*((parent, child) for parent, children in columns.items() for child in children),
		("piTitle.nt.ass.gross", "all_Prev_period"),
	):
		order += 1
		table.append(DefinitionArc(DOMAIN_MEMBER, gaap(parent), gaap(child), Decimal(order)))
		_add(presentation, mini.NOTES, gaap(parent), gaap(child))
	definition[mini.FIXED_ASSETS_TABLE] = table

	return replace(
		base,
		concepts=MappingProxyType(concepts),
		labels=MappingProxyType({name: MappingProxyType(roles) for name, roles in labels.items()}),
		presentation=MappingProxyType(
			{role: Network(role, tuple(arcs)) for role, arcs in presentation.items()}
		),
		calculation=MappingProxyType(
			{role: Network(role, tuple(arcs)) for role, arcs in calculation.items()}
		),
		definition=MappingProxyType({role: tuple(arcs) for role, arcs in definition.items()}),
	)


_COLUMNS = frozenset(gaap(name) for name in (*FIXED_ASSET_COLUMNS, "all_Prev_period"))
_COLUMN_PARENTS = frozenset(gaap(name) for name in ("piTitle.nt.ass.gross", "all", "gross", "accDepr"))


def _is_column(arc: DefinitionArc) -> bool:
	return arc.target in _COLUMNS


def _add(
	networks: dict[str, list[Arc]], role: str, parent: str, child: str, weight: int | None = None
) -> None:
	arcs = networks.setdefault(role, [])
	arcs.append(Arc(parent, child, Decimal(len(arcs) + 1), None if weight is None else Decimal(weight)))
