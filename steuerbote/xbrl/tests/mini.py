"""A mini taxonomy: a package in the form of the HGB-Taxonomie 6.9 with a handful of invented positions.

The real package may not be passed on, so the tests of steuerbote/xbrl run against this one. It has the structure of
german-gaap-taxonomy-v6.9-2025-04-01-xbrl.zip: the modules de-gcd-2025-04-01 and de-gaap-ci-2025-04-01, each with its
schema, entry points and linkbases, a role schema reached by a relative path into the other module, labels with a
fiscal variant that prohibits and replaces some of them, the fiscal references with Mussfelder, legal forms, GuV
formats and „notPermittedFor“, validity dates, tuples with sequences and choices, and the table of the Anlagenspiegel
with its hypercube, dimensions and primary items. A file of the Konzernsicht (-group) is in the package but in no entry
point Steuerbote reads, as in the real one.

The labels and amounts are invented; the names follow the real taxonomy where a test needs a familiar position, and
are made up elsewhere. ``write(directory)`` writes the package, ``archive(directory)`` zips it as esteuer.de
publishes the real one, with the module directories at the top.
"""

import hashlib
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from steuerbote.xbrl.versions import TAXONOMIES

VERSION = TAXONOMIES["6.9"]
GCD = VERSION.gcd
GAAP = VERSION.gaap
GCD_NS = VERSION.gcd_namespace
GAAP_NS = VERSION.gaap_namespace
XS = "http://www.w3.org/2001/XMLSchema"
LINK = "http://www.xbrl.org/2003/linkbase"
XLINK = "http://www.w3.org/1999/xlink"
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDT = "http://xbrl.org/2005/xbrldt"
HGBREF = "http://www.xbrl.de/taxonomies/de-ref-2010-02-19"
REF = "http://www.xbrl.org/2006/ref"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
HGBROLE_NS = "http://www.xbrl.de/taxonomies/hgbrole-2025-04-01"
ROLE = "http://www.xbrl.de/taxonomies/de-gaap-ci/role/"
GCD_ROLE = "http://www.xbrl.de/taxonomies/de-gcd/role/gcd"
HGBROLE = "http://www.xbrl.de/taxonomies/hgbrole/role/hgbrole"
LINK_ROLE = "http://www.xbrl.org/2003/role/link"
LABEL_ROLE = "http://www.xbrl.org/2003/role/label"
TERSE_ROLE = "http://www.xbrl.org/2003/role/terseLabel"
GUIDANCE_ROLE = "http://www.xbrl.org/2003/role/definitionGuidance"
DOCUMENTATION_ROLE = "http://www.xbrl.org/2003/role/documentation"
TERSE60_ROLE = "http://www.xbrl.de/roles/labels/terse60Label"
FISCAL_REFERENCE_ROLE = "http://www.xbrl.org/2003/role/mandatoryDisclosureRef"
REFERENCE_ROLE = "http://www.xbrl.org/2003/role/reference"
PARENT_CHILD = "http://www.xbrl.org/2003/arcrole/parent-child"
SUMMATION_ITEM = "http://www.xbrl.org/2003/arcrole/summation-item"
CONCEPT_LABEL = "http://www.xbrl.org/2003/arcrole/concept-label"
CONCEPT_REFERENCE = "http://www.xbrl.org/2003/arcrole/concept-reference"
DIM = "http://xbrl.org/int/dim/arcrole/"
INSTANCE_XSD = "http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd"
XBRLDT_XSD = "http://www.xbrl.org/2005/xbrldt-2005.xsd"

BALANCE_SHEET = f"{ROLE}balanceSheet"
INCOME_STATEMENT = f"{ROLE}incomeStatement"
INCOME_STATEMENT_MICROBILG = f"{ROLE}incomeStatementMicroBilG"
TRANSFERS_TAX_ASSETS = f"{ROLE}transfersTaxAssets"
DETAILED_INFORMATION = f"{ROLE}detailedInformation"
TRANSFERS_TO_TAX = f"{ROLE}transfersCommercialCodeToTax"
NOTES = f"{ROLE}notes"
FIXED_ASSETS_TABLE = f"{ROLE}notesTableStatementOfChangesInFixedAssetsGross"

MONETARY = "xbrli:monetaryItemType"
STRING = "xbrli:stringItemType"
DATE = "xbrli:dateItemType"
BOOLEAN = "xbrli:booleanItemType"
QNAME = "xbrli:QNameItemType"
POSITIVE_INTEGER = "xbrli:positiveIntegerItemType"
DECIMAL = "xbrli:decimalItemType"

MUSS = "Mussfeld"
SUMME = "Summenmussfeld"
RECHNERISCH = "Rechnerisch notwendig, soweit vorhanden"
ALL_FORMS = ("EU", "KSt", "PG")


@dataclass(frozen=True)
class Particle:
	ref: str
	min_occurs: int = 0
	max_occurs: int | None = 1


@dataclass(frozen=True)
class Concept:
	"""An element of a schema with its labels and references."""

	name: str
	type: str | None = MONETARY
	period: str | None = "instant"
	balance: str | None = None
	abstract: bool = False
	nillable: bool = True
	substitution: str = "xbrli:item"
	group: str | None = None
	"""sequence or choice for a tuple."""
	group_max: str | None = None
	particles: tuple[Particle, ...] = ()
	label: str = ""
	terse: str = ""
	guidance: str = ""
	requirement: str | None = None
	legal_forms: tuple[str, ...] = ALL_FORMS
	false_forms: tuple[str, ...] = ()
	operating: str | None = "neutral"
	not_permitted: tuple[str, ...] = ()
	fiscal_valid_since: str | None = None
	valid_since: str | None = None
	valid_through: str | None = None
	sonder_ergaenzung_only: bool = False


def item(name: str, label: str, **values) -> Concept:
	return Concept(name, label=label, **values)


def tuple_of(name: str, label: str, group: str, *particles: Particle, **values) -> Concept:
	return Concept(
		name,
		type=None,
		period=None,
		substitution="xbrli:tuple",
		group=group,
		particles=particles,
		label=label,
		**values,
	)


def choice(prefix: str, name: str, label: str, values: Iterable[str], **head) -> list[Concept]:
	"""A tuple with a choice of empty string items in the substitution group of its head (Leitfaden A.8, B.14.1)."""
	head_name = f"{name}.head"
	concepts = [
		tuple_of(name, label, "choice", Particle(f"{prefix}:{head_name}", 1, 1), **head),
		item(
			head_name, f"{label} (Auswahl)", type=STRING, period="duration", abstract=True, requirement=None
		),
	]
	for value in values:
		value_name, _, rest = value.partition("|")
		options = dict(part.split("=", 1) for part in rest.split(";") if part)
		concepts.append(
			item(
				f"{name}.{value_name}",
				f"{label}: {value_name}",
				type=STRING,
				period="duration",
				substitution=f"{prefix}:{head_name}",
				requirement=options.get("requirement"),
				legal_forms=tuple(options["forms"].split(",")) if "forms" in options else ALL_FORMS,
			)
		)
	return concepts


GCD_CONCEPTS: list[Concept] = [
	item("genInfo", "Dokumentinformationen", type=STRING, period="duration", abstract=True),
	item("genInfo.doc.id.generationDate", "Erstellungsdatum", type=DATE, period="duration"),
	*choice(
		"de-gcd",
		"genInfo.report.id.reportStatus",
		"Fertigstellungsstatus",
		("reportStatus.E", "reportStatus.V"),
		requirement=MUSS,
	),
	*choice(
		"de-gcd",
		"genInfo.report.id.reportElement",
		"Berichtsbestandteile",
		(
			f"reportElements.B|requirement={MUSS}",
			f"reportElements.GuV|requirement={MUSS}",
			f"reportElements.BVV|requirement={MUSS}",
			f"reportElements.BAL|requirement={MUSS}",
			f"reportElements.KS|requirement={MUSS}",
			f"reportElements.STU|requirement={MUSS}",
			f"reportElements.EB|requirement={MUSS}",
			f"reportElements.SGE|requirement={MUSS};forms=EU,PG",
		),
		group_max="unbounded",
		requirement=MUSS,
	),
	*choice(
		"de-gcd",
		"genInfo.report.id.statementType",
		"Bilanzart",
		("statementType.E", "statementType.EB"),
		requirement=MUSS,
	),
	*choice(
		"de-gcd",
		"genInfo.report.id.accountingStandard",
		"Bilanzierungsstandard",
		("accountingStandard.HAOE", "accountingStandard.HGBM", "accountingStandard.AO"),
		requirement=MUSS,
	),
	*choice(
		"de-gcd",
		"genInfo.report.id.incomeStatementFormat",
		"GuV-Format",
		("incomeStatementFormat.GKV", "incomeStatementFormat.UKV"),
		requirement=MUSS,
	),
	item(
		"genInfo.report.period.fiscalYearBegin",
		"Beginn des Wirtschaftsjahres",
		type=DATE,
		period="duration",
		requirement=MUSS,
	),
	item(
		"genInfo.report.period.fiscalYearEnd",
		"Ende des Wirtschaftsjahres",
		type=DATE,
		period="duration",
		requirement=MUSS,
	),
	item(
		"genInfo.report.period.balSheetClosingDate",
		"Bilanzstichtag",
		type=DATE,
		period="duration",
		requirement=MUSS,
	),
	item(
		"genInfo.company.id.name", "Name des Unternehmens", type=STRING, period="duration", requirement=MUSS
	),
	item(
		"genInfo.company.id.location.houseNo",
		"Firmensitz, Hausnummer",
		type=STRING,
		period="duration",
		requirement=MUSS,
	),
	*choice(
		"de-gcd",
		"genInfo.company.id.legalStatus",
		"Rechtsform",
		("legalStatus.GMBH|forms=KSt", "legalStatus.UG|forms=KSt", "legalStatus.EU|forms=EU"),
		requirement=MUSS,
	),
	tuple_of(
		"genInfo.company.id.idNo",
		"Unternehmenskennnummern",
		"sequence",
		Particle("de-gcd:genInfo.company.id.idNo.type.companyId.ST13"),
		Particle("de-gcd:genInfo.company.id.idNo.type.companyId.BF4"),
		requirement=MUSS,
	),
	item(
		"genInfo.company.id.idNo.type.companyId.ST13",
		"13-stellige Steuernummer",
		type=STRING,
		period="duration",
		requirement=MUSS,
	),
	item(
		"genInfo.company.id.idNo.type.companyId.BF4", "Bundesfinanzamtsnummer", type=STRING, period="duration"
	),
	tuple_of(
		"genInfo.company.id.shareholder",
		"Gesellschafter",
		"sequence",
		Particle("de-gcd:genInfo.company.id.shareholder.name", 1, 1),
		Particle("de-gcd:genInfo.company.id.shareholder.currentnumber"),
		Particle("de-gcd:genInfo.company.id.shareholder.ShareDivideKey"),
		requirement=MUSS,
	),
	item(
		"genInfo.company.id.shareholder.name",
		"Name des Gesellschafters",
		type=STRING,
		period="duration",
		requirement=MUSS,
	),
	item(
		"genInfo.company.id.shareholder.currentnumber",
		"Laufende Nummer des Gesellschafters",
		type=POSITIVE_INTEGER,
		period="duration",
	),
	tuple_of(
		"genInfo.company.id.shareholder.ShareDivideKey",
		"Beteiligungsschlüssel",
		"sequence",
		Particle("de-gcd:genInfo.company.id.shareholder.ShareDivideKey.numerator", 1, 1),
		Particle("de-gcd:genInfo.company.id.shareholder.ShareDivideKey.denominator", 1, 1),
		legal_forms=("PG",),
	),
	item(
		"genInfo.company.id.shareholder.ShareDivideKey.numerator", "Zähler", type=DECIMAL, period="duration"
	),
	item(
		"genInfo.company.id.shareholder.ShareDivideKey.denominator", "Nenner", type=DECIMAL, period="duration"
	),
	item(
		"genInfo.company.id.optionKStGs1a",
		"Option nach § 1a KStG",
		type=BOOLEAN,
		period="duration",
		legal_forms=("PG",),
		requirement=MUSS,
	),
]

GAAP_CONCEPTS: list[Concept] = [
	item("bs.ass", "Bilanzsumme, Summe Aktiva", balance="debit", requirement=SUMME),
	item("bs.ass.fixAss", "Anlagevermögen", balance="debit", requirement=SUMME),
	item("bs.ass.fixAss.intan", "Immaterielle Vermögensgegenstände", balance="debit", requirement=SUMME),
	item(
		"bs.ass.fixAss.intan.concessionBrands",
		"entgeltlich erworbene Konzessionen",
		balance="debit",
		requirement=MUSS,
		terse="Konzessionen",
	),
	item(
		"bs.ass.fixAss.intan.selfmade",
		"selbst geschaffene Schutzrechte",
		balance="debit",
		requirement=RECHNERISCH,
		not_permitted=("steuerlich",),
	),
	item(
		"bs.ass.fixAss.tan",
		"Sachanlagen",
		balance="debit",
		requirement=MUSS,
		guidance="Grundstücke, Bauten, Maschinen und Ausstattung.",
	),
	item(
		"bs.ass.fixAss.tan.oldEquipment",
		"Betriebsausstattung alter Art",
		balance="debit",
		valid_through="2020-12-31",
	),
	item("bs.ass.currAss", "Umlaufvermögen", balance="debit", requirement=SUMME),
	item(
		"bs.ass.currAss.cashEquiv",
		"Kassenbestand, Guthaben bei Kreditinstituten",
		balance="debit",
		requirement=SUMME,
	),
	item(
		"bs.ass.currAss.cashEquiv.bank",
		"Guthaben bei Kreditinstituten",
		balance="debit",
		requirement=RECHNERISCH,
	),
	item(
		"bs.ass.currAss.cashEquiv.cash",
		"Kassenbestand",
		balance="debit",
		requirement=MUSS,
		fiscal_valid_since="2027-01-01",
	),
	item("bs.ass.currAss.cashEquiv.cryptoAssets", "Kryptowerte", balance="debit", valid_since="2027-01-01"),
	item(
		"bs.ass.consolidationDifference",
		"Unterschiedsbetrag aus der Kapitalkonsolidierung",
		balance="debit",
		not_permitted=("Einreichung an Finanzverwaltung",),
	),
	item("bs.eqLiab", "Bilanzsumme, Summe Passiva", balance="credit", requirement=SUMME),
	item("bs.eqLiab.equity", "Eigenkapital", balance="credit", requirement=SUMME),
	item("bs.eqLiab.equity.subscribed", "Gezeichnetes Kapital", balance="credit", requirement=SUMME),
	item(
		"bs.eqLiab.equity.subscribed.corp",
		"Gezeichnetes Kapital (Kapitalgesellschaft)",
		balance="credit",
		requirement=MUSS,
		legal_forms=("KSt",),
		terse="Gez. Kapital (KapG)",
	),
	item(
		"bs.eqLiab.equity.subscribed.limitedLiablePartners",
		"Kommandit-Kapital",
		balance="credit",
		requirement=MUSS,
		legal_forms=("PG",),
	),
	item(
		"bs.eqLiab.equity.netIncome", "Jahresüberschuss/Jahresfehlbetrag", balance="credit", requirement=MUSS
	),
	item("bs.eqLiab.liab", "Verbindlichkeiten", balance="credit", requirement=SUMME),
	item(
		"bs.eqLiab.liab.bank",
		"Verbindlichkeiten gegenüber Kreditinstituten",
		balance="credit",
		requirement=MUSS,
	),
	item(
		"bs.eqLiab.liab.bank.upTo1year",
		"davon mit einer Restlaufzeit bis zu einem Jahr",
		balance="credit",
		requirement=None,
	),
	item(
		"is.netIncome",
		"Jahresüberschuss/Jahresfehlbetrag",
		period="duration",
		balance="credit",
		requirement=SUMME,
	),
	item("is.netIncome.netSales", "Umsatzerlöse", period="duration", balance="credit", requirement=MUSS),
	item(
		"is.netIncome.materialServices",
		"Materialaufwand",
		period="duration",
		balance="debit",
		requirement=MUSS,
		operating="GKV",
	),
	item(
		"is.netIncome.costOfSales",
		"Herstellungskosten",
		period="duration",
		balance="debit",
		requirement=MUSS,
		operating="UKV",
	),
	item(
		"is.netIncome.tax",
		"Steuern vom Einkommen und vom Ertrag",
		period="duration",
		balance="debit",
		requirement=MUSS,
		false_forms=("EU",),
		legal_forms=("KSt", "PG"),
	),
	item(
		"ismi.netIncome", "Jahresüberschuss/Jahresfehlbetrag (MicroBilG)", period="duration", balance="credit"
	),
	item("ismi.netIncome.netSales", "Umsatzerlöse (MicroBilG)", period="duration", balance="credit"),
	item(
		"BVV.profitLoss",
		"Gewinn/Verlust laut Betriebsvermögensvergleich",
		period="duration",
		balance="credit",
		requirement=MUSS,
	),
	item(
		"BVV.profitLoss.assetsCurrentYear",
		"Betriebsvermögen am Ende des Wirtschaftsjahres",
		period="duration",
		requirement=MUSS,
	),
	item(
		"BVV.profitLoss.assetsPreviousYear",
		"Betriebsvermögen am Ende des Vorjahres",
		period="duration",
		requirement=MUSS,
	),
	item(
		"detailedInformation",
		"Detailinformationen zu Positionen",
		type=STRING,
		period="duration",
		abstract=True,
	),
	tuple_of(
		"detailedInformation.accountBalances",
		"Kontensalden zu einer Position",
		"sequence",
		Particle("de-gaap-ci:detailedInformation.accountbalances.positionName", 1, 1),
		Particle("de-gaap-ci:detailedInformation.accountbalances.accountNumber", 1, 1),
		Particle("de-gaap-ci:detailedInformation.accountbalances.accountDescription", 1, 1),
		Particle("de-gaap-ci:detailedInformation.accountbalances.amount", 1, 1),
	),
	item(
		"detailedInformation.accountbalances.positionName", "Name der Position", type=QNAME, period="duration"
	),
	item("detailedInformation.accountbalances.accountNumber", "Kontonummer", type=STRING, period="duration"),
	item(
		"detailedInformation.accountbalances.accountDescription",
		"Kontobeschreibung",
		type=STRING,
		period="duration",
	),
	item("detailedInformation.accountbalances.amount", "Kontosaldo", period="duration"),
	tuple_of(
		"hbst.transfer",
		"Überleitungsrechnung",
		"sequence",
		Particle("de-gaap-ci:hbst.transfer.kind", 1, 1),
		Particle("de-gaap-ci:hbst.transfer.bsAss", 0, None),
	),
	*choice("de-gaap-ci", "hbst.transfer.kind", "Art der Überleitung", ("reclassification", "changeValue")),
	tuple_of(
		"hbst.transfer.bsAss",
		"Aktivposition",
		"sequence",
		Particle("de-gaap-ci:hbst.transfer.bsAss.name", 1, 1),
		Particle("de-gaap-ci:hbst.transfer.bsAss.changeValueActualPeriod", 0, 1),
	),
	item("hbst.transfer.bsAss.name", "Name der Position", type=QNAME, period="duration"),
	item(
		"hbst.transfer.bsAss.changeValueActualPeriod",
		"Wertänderung aus dem aktuellen Wirtschaftsjahr",
		period="duration",
	),
]

DIMENSION_CONCEPTS: list[Concept] = [
	item("table.nt.ass.gross", "Anlagenspiegel (brutto)", type=STRING, period="duration", abstract=True),
	Concept(
		"cube_.nt.ass.gross",
		type=STRING,
		period="duration",
		abstract=True,
		substitution="xbrldt:hypercubeItem",
		label="Hypercube Anlagenspiegel",
	),
	Concept(
		"dim_taxTrans",
		type=STRING,
		period="duration",
		abstract=True,
		substitution="xbrldt:dimensionItem",
		label="steuerliche Überleitung",
	),
	Concept(
		"dim_changes.nt.ass.gross",
		type=STRING,
		period="duration",
		abstract=True,
		substitution="xbrldt:dimensionItem",
		label="Positionen des Anlagevermögens",
	),
	item("dim_taxBal", "Steuerbilanzwert", type=STRING, period="duration", abstract=True),
	item("dim_comBal", "Handelsbilanzwert", type=STRING, period="duration", abstract=True),
	item("dim_diffComToTaxBal", "Überleitungswert", type=STRING, period="duration", abstract=True),
	item("piTitle.nt.ass.gross", "Wertentwicklung", type=STRING, period="duration", abstract=True),
	item("all", "Buchwert zum Ende der Periode", period="duration", requirement=MUSS),
	item(
		"gross",
		"Anschaffungs- und Herstellungskosten zum Ende der Periode",
		period="duration",
		requirement=SUMME,
	),
	item(
		"grossCost.beginning",
		"Anschaffungs- und Herstellungskosten zum Anfang der Periode",
		period="duration",
		requirement=MUSS,
	),
	item("gross.addition", "Zugänge", period="duration", requirement=MUSS),
	item("accDepr", "Kumulierte Abschreibungen zum Ende der Periode", period="duration", requirement=SUMME),
	item("accDepr.DeprPeriod", "Abschreibungen im Wirtschaftsjahr", period="duration", requirement=MUSS),
	item("all_Prev_period", "Buchwert zum Ende der Vorperiode", period="duration"),
]
"""The table of the Anlagenspiegel, as de-gaap-ci-2025-04-01-dimensions.xsd defines it: the hypercube with its
dimensions „steuerliche Überleitung“ and „Positionen des Anlagevermögens“ and the primary items of the value
development."""


def _relations(spec: str) -> list[tuple[str, str, str]]:
	"""Arcs written one per line as „parent > child [weight]“, the weight for a calculation."""
	arcs = []
	for line in spec.strip().splitlines():
		parent, _, rest = line.partition(">")
		child, _, weight = rest.strip().partition(" ")
		arcs.append((parent.strip(), child.strip(), weight.strip() or "1"))
	return arcs


BALANCE_SHEET_PRESENTATION = _relations(
	"""
	bs.ass > bs.ass.fixAss
	bs.ass.fixAss > bs.ass.fixAss.intan
	bs.ass.fixAss.intan > bs.ass.fixAss.intan.concessionBrands
	bs.ass.fixAss.intan > bs.ass.fixAss.intan.selfmade
	bs.ass.fixAss > bs.ass.fixAss.tan
	bs.ass.fixAss.tan > bs.ass.fixAss.tan.oldEquipment
	bs.ass > bs.ass.currAss
	bs.ass.currAss > bs.ass.currAss.cashEquiv
	bs.ass.currAss.cashEquiv > bs.ass.currAss.cashEquiv.bank
	bs.ass.currAss.cashEquiv > bs.ass.currAss.cashEquiv.cash
	bs.ass.currAss.cashEquiv > bs.ass.currAss.cashEquiv.cryptoAssets
	bs.ass > bs.ass.consolidationDifference
	bs.eqLiab > bs.eqLiab.equity
	bs.eqLiab.equity > bs.eqLiab.equity.subscribed
	bs.eqLiab.equity.subscribed > bs.eqLiab.equity.subscribed.corp
	bs.eqLiab.equity.subscribed > bs.eqLiab.equity.subscribed.limitedLiablePartners
	bs.eqLiab.equity > bs.eqLiab.equity.netIncome
	bs.eqLiab > bs.eqLiab.liab
	bs.eqLiab.liab > bs.eqLiab.liab.bank
	bs.eqLiab.liab.bank > bs.eqLiab.liab.bank.upTo1year
	"""
)
BALANCE_SHEET_CALCULATION = _relations(
	"""
	bs.ass > bs.ass.fixAss
	bs.ass.fixAss > bs.ass.fixAss.intan
	bs.ass.fixAss.intan > bs.ass.fixAss.intan.concessionBrands
	bs.ass.fixAss.intan > bs.ass.fixAss.intan.selfmade
	bs.ass.fixAss > bs.ass.fixAss.tan
	bs.ass.fixAss.tan > bs.ass.fixAss.tan.oldEquipment
	bs.ass > bs.ass.currAss
	bs.ass.currAss > bs.ass.currAss.cashEquiv
	bs.ass.currAss.cashEquiv > bs.ass.currAss.cashEquiv.bank
	bs.ass.currAss.cashEquiv > bs.ass.currAss.cashEquiv.cash
	bs.ass.currAss.cashEquiv > bs.ass.currAss.cashEquiv.cryptoAssets
	bs.ass > bs.ass.consolidationDifference
	bs.eqLiab > bs.eqLiab.equity
	bs.eqLiab.equity > bs.eqLiab.equity.subscribed
	bs.eqLiab.equity.subscribed > bs.eqLiab.equity.subscribed.corp
	bs.eqLiab.equity.subscribed > bs.eqLiab.equity.subscribed.limitedLiablePartners
	bs.eqLiab.equity > bs.eqLiab.equity.netIncome
	bs.eqLiab > bs.eqLiab.liab
	bs.eqLiab.liab > bs.eqLiab.liab.bank
	"""
)
INCOME_STATEMENT_ARCS = _relations(
	"""
	is.netIncome > is.netIncome.netSales 1
	is.netIncome > is.netIncome.materialServices -1
	is.netIncome > is.netIncome.costOfSales -1
	is.netIncome > is.netIncome.tax -1
	"""
)
MICROBILG_ARCS = _relations("ismi.netIncome > ismi.netIncome.netSales 1")
TRANSFERS_TAX_ASSETS_ARCS = _relations(
	"""
	BVV.profitLoss > BVV.profitLoss.assetsCurrentYear 1
	BVV.profitLoss > BVV.profitLoss.assetsPreviousYear -1
	"""
)
DETAILED_INFORMATION_ARCS = _relations(
	"""
	detailedInformation > detailedInformation.accountBalances
	detailedInformation.accountBalances > detailedInformation.accountbalances.positionName
	detailedInformation.accountBalances > detailedInformation.accountbalances.accountNumber
	detailedInformation.accountBalances > detailedInformation.accountbalances.accountDescription
	detailedInformation.accountBalances > detailedInformation.accountbalances.amount
	"""
)
TRANSFERS_TO_TAX_ARCS = _relations(
	"""
	hbst.transfer > hbst.transfer.kind
	hbst.transfer.kind > hbst.transfer.kind.reclassification
	hbst.transfer.kind > hbst.transfer.kind.changeValue
	hbst.transfer > hbst.transfer.bsAss
	hbst.transfer.bsAss > hbst.transfer.bsAss.name
	hbst.transfer.bsAss > hbst.transfer.bsAss.changeValueActualPeriod
	"""
)
FIXED_ASSETS_PRIMARY_ITEMS = _relations(
	"""
	table.nt.ass.gross > piTitle.nt.ass.gross
	piTitle.nt.ass.gross > all
	all > gross
	gross > grossCost.beginning
	gross > gross.addition
	all > accDepr
	accDepr > accDepr.DeprPeriod
	piTitle.nt.ass.gross > all_Prev_period
	"""
)
FIXED_ASSETS_CALCULATION = _relations(
	"""
	all > gross 1
	all > accDepr -1
	gross > grossCost.beginning 1
	gross > gross.addition 1
	accDepr > accDepr.DeprPeriod 1
	"""
)
FIXED_ASSETS_MEMBERS = _relations(
	"""
	bs.ass.fixAss > bs.ass.fixAss.intan
	bs.ass.fixAss.intan > bs.ass.fixAss.intan.concessionBrands
	bs.ass.fixAss.intan > bs.ass.fixAss.intan.selfmade
	bs.ass.fixAss > bs.ass.fixAss.tan
	"""
)
GCD_PRESENTATION = _relations(
	"""
	genInfo > genInfo.doc.id.generationDate
	genInfo > genInfo.report.id.reportStatus
	genInfo.report.id.reportStatus > genInfo.report.id.reportStatus.reportStatus.E
	genInfo.report.id.reportStatus > genInfo.report.id.reportStatus.reportStatus.V
	genInfo > genInfo.report.id.reportElement
	genInfo.report.id.reportElement > genInfo.report.id.reportElement.reportElements.B
	genInfo.report.id.reportElement > genInfo.report.id.reportElement.reportElements.GuV
	genInfo.report.id.reportElement > genInfo.report.id.reportElement.reportElements.BVV
	genInfo.report.id.reportElement > genInfo.report.id.reportElement.reportElements.BAL
	genInfo.report.id.reportElement > genInfo.report.id.reportElement.reportElements.KS
	genInfo.report.id.reportElement > genInfo.report.id.reportElement.reportElements.STU
	genInfo.report.id.reportElement > genInfo.report.id.reportElement.reportElements.EB
	genInfo.report.id.reportElement > genInfo.report.id.reportElement.reportElements.SGE
	genInfo > genInfo.report.id.statementType
	genInfo.report.id.statementType > genInfo.report.id.statementType.statementType.E
	genInfo.report.id.statementType > genInfo.report.id.statementType.statementType.EB
	genInfo > genInfo.report.id.accountingStandard
	genInfo.report.id.accountingStandard > genInfo.report.id.accountingStandard.accountingStandard.HAOE
	genInfo.report.id.accountingStandard > genInfo.report.id.accountingStandard.accountingStandard.HGBM
	genInfo.report.id.accountingStandard > genInfo.report.id.accountingStandard.accountingStandard.AO
	genInfo > genInfo.report.id.incomeStatementFormat
	genInfo.report.id.incomeStatementFormat > genInfo.report.id.incomeStatementFormat.incomeStatementFormat.GKV
	genInfo.report.id.incomeStatementFormat > genInfo.report.id.incomeStatementFormat.incomeStatementFormat.UKV
	genInfo > genInfo.report.period.fiscalYearBegin
	genInfo > genInfo.report.period.fiscalYearEnd
	genInfo > genInfo.report.period.balSheetClosingDate
	genInfo > genInfo.company.id.name
	genInfo > genInfo.company.id.location.houseNo
	genInfo > genInfo.company.id.legalStatus
	genInfo.company.id.legalStatus > genInfo.company.id.legalStatus.legalStatus.GMBH
	genInfo.company.id.legalStatus > genInfo.company.id.legalStatus.legalStatus.UG
	genInfo.company.id.legalStatus > genInfo.company.id.legalStatus.legalStatus.EU
	genInfo > genInfo.company.id.idNo
	genInfo.company.id.idNo > genInfo.company.id.idNo.type.companyId.ST13
	genInfo.company.id.idNo > genInfo.company.id.idNo.type.companyId.BF4
	genInfo > genInfo.company.id.shareholder
	genInfo.company.id.shareholder > genInfo.company.id.shareholder.name
	genInfo.company.id.shareholder > genInfo.company.id.shareholder.currentnumber
	genInfo.company.id.shareholder > genInfo.company.id.shareholder.ShareDivideKey
	genInfo.company.id.shareholder.ShareDivideKey > genInfo.company.id.shareholder.ShareDivideKey.numerator
	genInfo.company.id.shareholder.ShareDivideKey > genInfo.company.id.shareholder.ShareDivideKey.denominator
	genInfo > genInfo.company.id.optionKStGs1a
	"""
)
FISCAL_LABELS = {
	"bs.eqLiab.equity.subscribed.corp": ("Gezeichnetes Kapital", "Gez. Kapital"),
	"bs.ass.fixAss.tan": ("Sachanlagen (steuerlich)", None),
}
"""The labels de-gaap-ci-2025-04-01-label-fiscal-de.xml puts in place of those of the commercial view: label and
terse label, None for one it leaves."""
TERSE60 = {"bs.ass.fixAss.intan.concessionBrands": "Konzessionen, Rechte, Lizenzen"}
GROUP_ARCS = _relations("bs.ass > bs.ass.groupOnly")
"""An arc of the Konzernsicht, de-gaap-ci-2025-04-01-presentation-balanceSheet-group.xml, which no entry point of
Steuerbote reads."""


@dataclass
class _Linkbase:
	"""The XML of one linkbase, written in the order of the calls."""

	root: etree._Element = field(init=False)

	def __post_init__(self) -> None:
		self.root = etree.Element(
			f"{{{LINK}}}linkbase",
			nsmap={"link": LINK, "xlink": XLINK, "xbrldt": XBRLDT, "hgbref": HGBREF, "ref": REF},
		)

	def role_ref(self, role: str, href: str) -> None:
		etree.SubElement(
			self.root,
			f"{{{LINK}}}roleRef",
			{"roleURI": role, f"{{{XLINK}}}type": "simple", f"{{{XLINK}}}href": href},
		)

	def link(self, kind: str, role: str) -> etree._Element:
		return etree.SubElement(
			self.root, f"{{{LINK}}}{kind}", {f"{{{XLINK}}}type": "extended", f"{{{XLINK}}}role": role}
		)

	def bytes(self) -> bytes:
		etree.indent(self.root, space="  ")
		return etree.tostring(self.root, xml_declaration=True, encoding="utf-8")


def _loc(link: etree._Element, href: str, label: str) -> None:
	etree.SubElement(
		link,
		f"{{{LINK}}}loc",
		{f"{{{XLINK}}}type": "locator", f"{{{XLINK}}}href": href, f"{{{XLINK}}}label": label},
	)


def _arc(link: etree._Element, kind: str, arcrole: str, source: str, target: str, **attributes: str) -> None:
	values = {
		f"{{{XLINK}}}type": "arc",
		f"{{{XLINK}}}arcrole": arcrole,
		f"{{{XLINK}}}from": source,
		f"{{{XLINK}}}to": target,
	}
	for name, value in attributes.items():
		key = f"{{{XBRLDT}}}{name.removeprefix('xbrldt_')}" if name.startswith("xbrldt_") else name
		values[key] = value
	etree.SubElement(link, f"{{{LINK}}}{kind}", values)


def _relationship_link(
	linkbase: _Linkbase,
	kind: str,
	role: str,
	arcrole: str,
	arcs: Sequence[tuple[str, str, str]],
	schema: str,
	prefix: str,
	*,
	weighted: bool = False,
) -> None:
	link = linkbase.link(f"{kind}Link", role)
	located: set[str] = set()
	for index, (parent, child, weight) in enumerate(arcs, start=1):
		for name in (parent, child):
			if name not in located:
				located.add(name)
				_loc(link, f"{schema}#{prefix}_{name}", f"{prefix}_{name}")
		attributes = {"order": str(index)}
		if weighted:
			attributes["weight"] = weight
		_arc(link, f"{kind}Arc", arcrole, f"{prefix}_{parent}", f"{prefix}_{child}", **attributes)


def _schema(target: str, prefix: str, nsmap_extra: dict[str, str] | None = None) -> etree._Element:
	nsmap = {"xs": XS, "link": LINK, "xlink": XLINK, "xbrli": XBRLI, "xbrldt": XBRLDT, prefix: target}
	nsmap |= nsmap_extra or {}
	return etree.Element(
		f"{{{XS}}}schema", {"targetNamespace": target, "elementFormDefault": "qualified"}, nsmap=nsmap
	)


def _appinfo(schema: etree._Element) -> etree._Element:
	annotation = etree.SubElement(schema, f"{{{XS}}}annotation")
	return etree.SubElement(annotation, f"{{{XS}}}appinfo")


def _linkbase_ref(appinfo: etree._Element, href: str, kind: str) -> None:
	etree.SubElement(
		appinfo,
		f"{{{LINK}}}linkbaseRef",
		{
			f"{{{XLINK}}}type": "simple",
			f"{{{XLINK}}}href": href,
			f"{{{XLINK}}}role": f"http://www.xbrl.org/2003/role/{kind}LinkbaseRef",
			f"{{{XLINK}}}arcrole": "http://www.w3.org/1999/xlink/properties/linkbase",
		},
	)


def _import(schema: etree._Element, namespace: str, location: str) -> None:
	etree.SubElement(schema, f"{{{XS}}}import", {"namespace": namespace, "schemaLocation": location})


def _element(schema: etree._Element, prefix: str, concept: Concept) -> None:
	attributes = {
		"name": concept.name,
		"id": f"{prefix}_{concept.name}",
		"substitutionGroup": concept.substitution,
		"nillable": "true" if concept.nillable else "false",
	}
	if concept.abstract:
		attributes["abstract"] = "true"
	if concept.type is not None:
		attributes["type"] = concept.type
	if concept.period is not None:
		attributes[f"{{{XBRLI}}}periodType"] = concept.period
	if concept.balance is not None:
		attributes[f"{{{XBRLI}}}balance"] = concept.balance
	element = etree.SubElement(schema, f"{{{XS}}}element", attributes)
	if concept.group is None:
		return
	complex_type = etree.SubElement(element, f"{{{XS}}}complexType")
	group_attributes = {} if concept.group_max is None else {"maxOccurs": concept.group_max}
	group = etree.SubElement(complex_type, f"{{{XS}}}{concept.group}", group_attributes)
	for particle in concept.particles:
		occurs = {"ref": particle.ref}
		if concept.group == "sequence" or particle.min_occurs != 1:
			occurs["minOccurs"] = str(particle.min_occurs)
		if concept.group == "sequence" or particle.max_occurs != 1:
			occurs["maxOccurs"] = "unbounded" if particle.max_occurs is None else str(particle.max_occurs)
		etree.SubElement(group, f"{{{XS}}}element", occurs)
	etree.SubElement(complex_type, f"{{{XS}}}attribute", {"name": "id", "type": "xs:ID", "use": "optional"})


def _role_type(appinfo: etree._Element, role: str, definition: str, used_on: str) -> None:
	role_type = etree.SubElement(
		appinfo, f"{{{LINK}}}roleType", {"roleURI": role, "id": role.rsplit("/", 1)[1]}
	)
	etree.SubElement(role_type, f"{{{LINK}}}definition").text = definition
	etree.SubElement(role_type, f"{{{LINK}}}usedOn").text = used_on


def _bytes(element: etree._Element) -> bytes:
	etree.indent(element, space="  ")
	return etree.tostring(element, xml_declaration=True, encoding="utf-8")


def _labels(prefix: str, schema: str, concepts: Iterable[Concept], *, language: str = "de") -> bytes:
	linkbase = _Linkbase()
	link = linkbase.link("labelLink", LINK_ROLE)
	for concept in concepts:
		_loc(link, f"{schema}#{prefix}_{concept.name}", f"{prefix}_{concept.name}")
		for role, text, suffix in (
			(LABEL_ROLE, concept.label, ""),
			(TERSE_ROLE, concept.terse, "_terse"),
			(
				DOCUMENTATION_ROLE,
				f"Dokumentation zu {concept.label}" if concept.label else "",
				"_documentation",
			),
		):
			if not text:
				continue
			resource = f"label_{prefix}_{concept.name}{suffix}"
			label = etree.SubElement(
				link,
				f"{{{LINK}}}label",
				{
					f"{{{XLINK}}}type": "resource",
					f"{{{XLINK}}}label": resource,
					f"{{{XLINK}}}role": role,
					XML_LANG: language,
					"id": resource,
				},
			)
			label.text = text if language == "de" else f"{text} (English)"
			_arc(link, "labelArc", CONCEPT_LABEL, f"{prefix}_{concept.name}", resource)
	return linkbase.bytes()


def _guidance(prefix: str, schema: str, concepts: Iterable[Concept]) -> bytes:
	linkbase = _Linkbase()
	link = linkbase.link("labelLink", LINK_ROLE)
	for concept in concepts:
		if not concept.guidance:
			continue
		_loc(link, f"{schema}#{prefix}_{concept.name}", f"{prefix}_{concept.name}")
		resource = f"guidance_{prefix}_{concept.name}"
		label = etree.SubElement(
			link,
			f"{{{LINK}}}label",
			{
				f"{{{XLINK}}}type": "resource",
				f"{{{XLINK}}}label": resource,
				f"{{{XLINK}}}role": GUIDANCE_ROLE,
				XML_LANG: "de",
			},
		)
		label.text = concept.guidance
		_arc(link, "labelArc", CONCEPT_LABEL, f"{prefix}_{concept.name}", resource)
	return linkbase.bytes()


def _fiscal_labels(prefix: str, schema: str, labels_file: str) -> bytes:
	"""Prohibit the labels of the commercial view and put the fiscal ones in their place, as
	de-gaap-ci-2025-04-01-label-fiscal-de.xml does with priority 1."""
	linkbase = _Linkbase()
	link = linkbase.link("labelLink", LINK_ROLE)
	for name, (label, terse) in FISCAL_LABELS.items():
		concept = f"{prefix}_{name}"
		_loc(link, f"{schema}#{concept}", concept)
		for role, text, suffix in ((LABEL_ROLE, label, ""), (TERSE_ROLE, terse, "_terse")):
			if text is None:
				continue
			base = f"label_{concept}{suffix}"
			_loc(link, f"{labels_file}#{base}", f"ext{base}")
			_arc(link, "labelArc", CONCEPT_LABEL, concept, f"ext{base}", priority="1", use="prohibited")
			resource = f"fiscal_{concept}{suffix}"
			element = etree.SubElement(
				link,
				f"{{{LINK}}}label",
				{
					f"{{{XLINK}}}type": "resource",
					f"{{{XLINK}}}label": resource,
					f"{{{XLINK}}}role": role,
					XML_LANG: "de",
					"id": resource,
				},
			)
			element.text = text
			_arc(link, "labelArc", CONCEPT_LABEL, concept, resource, priority="1")
	return linkbase.bytes()


def _terse60(prefix: str, schema: str) -> bytes:
	linkbase = _Linkbase()
	link = linkbase.link("labelLink", LINK_ROLE)
	for name, text in TERSE60.items():
		concept = f"{prefix}_{name}"
		_loc(link, f"{schema}#{concept}", concept)
		resource = f"terse60_{concept}"
		element = etree.SubElement(
			link,
			f"{{{LINK}}}label",
			{
				f"{{{XLINK}}}type": "resource",
				f"{{{XLINK}}}label": resource,
				f"{{{XLINK}}}role": TERSE60_ROLE,
				XML_LANG: "de",
			},
		)
		element.text = text
		_arc(link, "labelArc", CONCEPT_LABEL, concept, resource)
	return linkbase.bytes()


def _fiscal_references(prefix: str, schema: str, concepts: Iterable[Concept]) -> bytes:
	linkbase = _Linkbase()
	link = linkbase.link("referenceLink", LINK_ROLE)
	for concept in concepts:
		_loc(link, f"{schema}#{prefix}_{concept.name}", f"{prefix}_{concept.name}")
		resource = f"reference_{prefix}_{concept.name}"
		reference = etree.SubElement(
			link,
			f"{{{LINK}}}reference",
			{
				f"{{{XLINK}}}type": "resource",
				f"{{{XLINK}}}label": resource,
				f"{{{XLINK}}}role": FISCAL_REFERENCE_ROLE,
				"id": resource,
			},
		)
		for form in concept.false_forms:
			etree.SubElement(reference, f"{{{HGBREF}}}legalForm{form}").text = "false"
		for form in concept.legal_forms:
			etree.SubElement(reference, f"{{{HGBREF}}}legalForm{form}").text = "true"
		if concept.operating is not None:
			etree.SubElement(reference, f"{{{HGBREF}}}typeOperatingResult").text = concept.operating
		for value in concept.not_permitted:
			etree.SubElement(reference, f"{{{HGBREF}}}notPermittedFor").text = value
		if concept.sonder_ergaenzung_only:
			etree.SubElement(reference, f"{{{HGBREF}}}onlyPermittedForSoBil_ErgBil").text = "true"
		if concept.fiscal_valid_since is not None:
			etree.SubElement(reference, f"{{{HGBREF}}}fiscalValidSince").text = concept.fiscal_valid_since
		if concept.requirement is not None:
			etree.SubElement(reference, f"{{{HGBREF}}}fiscalRequirement").text = concept.requirement
		_arc(link, "referenceArc", CONCEPT_REFERENCE, f"{prefix}_{concept.name}", resource)
	return linkbase.bytes()


def _references(prefix: str, schema: str, concepts: Iterable[Concept]) -> bytes:
	"""The reference linkbase of the commercial view: the paragraphs of the law and the validity dates."""
	linkbase = _Linkbase()
	link = linkbase.link("referenceLink", LINK_ROLE)
	for concept in concepts:
		if concept.valid_since is None and concept.valid_through is None:
			continue
		_loc(link, f"{schema}#{prefix}_{concept.name}", f"{prefix}_{concept.name}")
		resource = f"reference_{prefix}_{concept.name}"
		reference = etree.SubElement(
			link,
			f"{{{LINK}}}reference",
			{
				f"{{{XLINK}}}type": "resource",
				f"{{{XLINK}}}label": resource,
				f"{{{XLINK}}}role": REFERENCE_ROLE,
			},
		)
		etree.SubElement(reference, f"{{{REF}}}Name").text = "HGB"
		etree.SubElement(reference, f"{{{REF}}}Paragraph").text = "266"
		if concept.valid_since is not None:
			etree.SubElement(reference, f"{{{HGBREF}}}ValidSince").text = concept.valid_since
		if concept.valid_through is not None:
			etree.SubElement(reference, f"{{{HGBREF}}}ValidThrough").text = concept.valid_through
		_arc(link, "referenceArc", CONCEPT_REFERENCE, f"{prefix}_{concept.name}", resource)
	return linkbase.bytes()


def write(directory: Path) -> Path:
	"""Write the package into directory, the module directories at its top, and return the directory."""
	gcd_dir = directory / GCD
	gaap_dir = directory / GAAP
	gcd_dir.mkdir(parents=True, exist_ok=True)
	gaap_dir.mkdir(parents=True, exist_ok=True)
	files: dict[Path, bytes] = {}
	files |= _gcd_files(gcd_dir)
	files |= _gaap_files(gaap_dir)
	for path, data in files.items():
		path.write_bytes(data)
	return directory


def _gcd_files(directory: Path) -> dict[Path, bytes]:
	schema_name = f"{GCD}.xsd"
	schema = _schema(GCD_NS, "de-gcd", {"de-hgbrole": HGBROLE_NS})
	appinfo = _appinfo(schema)
	for name, kind in ((f"{GCD}-label-de.xml", "label"), (f"{GCD}-label-en.xml", "label")):
		_linkbase_ref(appinfo, name, kind)
	_linkbase_ref(appinfo, f"{GCD}-reference-fiscal.xml", "reference")
	_role_type(appinfo, GCD_ROLE, "GCD (Global Common Document)", "link:presentationLink")
	_import(schema, HGBROLE_NS, "hgbrole-2025-04-01.xsd")
	_import(schema, XBRLI, INSTANCE_XSD)
	for concept in GCD_CONCEPTS:
		_element(schema, "de-gcd", concept)

	hgbrole = _schema(HGBROLE_NS, "de-hgbrole")
	_role_type(_appinfo(hgbrole), HGBROLE, "Rolle der HGB-Taxonomie", "link:presentationLink")

	shell = _schema(f"{GCD_NS}/shell", "gcd-shell", {"de-gcd": GCD_NS})
	_linkbase_ref(_appinfo(shell), f"{GCD}-presentation.xml", "presentation")
	_import(shell, GCD_NS, schema_name)

	presentation = _Linkbase()
	_relationship_link(
		presentation, "presentation", GCD_ROLE, PARENT_CHILD, GCD_PRESENTATION, schema_name, "de-gcd"
	)
	return {
		directory / schema_name: _bytes(schema),
		directory / "hgbrole-2025-04-01.xsd": _bytes(hgbrole),
		directory / f"{GCD}-shell.xsd": _bytes(shell),
		directory / f"{GCD}-presentation.xml": presentation.bytes(),
		directory / f"{GCD}-label-de.xml": _labels("de-gcd", schema_name, GCD_CONCEPTS),
		directory / f"{GCD}-label-en.xml": _labels("de-gcd", schema_name, GCD_CONCEPTS, language="en"),
		directory / f"{GCD}-reference-fiscal.xml": _fiscal_references("de-gcd", schema_name, GCD_CONCEPTS),
	}


def _gaap_files(directory: Path) -> dict[Path, bytes]:
	schema_name = f"{GAAP}.xsd"
	dimensions_name = f"{GAAP}-dimensions.xsd"
	labels_name = f"{GAAP}-label-de.xml"
	schema = _schema(GAAP_NS, "de-gaap-ci", {"de-hgbrole": HGBROLE_NS})
	appinfo = _appinfo(schema)
	_linkbase_ref(appinfo, labels_name, "label")
	_linkbase_ref(appinfo, f"{GAAP}-label-guidance-de.xml", "label")
	_linkbase_ref(appinfo, f"{GAAP}-reference.xml", "reference")
	_linkbase_ref(appinfo, f"{GAAP}-reference-fiscal.xml", "reference")
	for role, definition in (
		(BALANCE_SHEET, "Bilanz"),
		(INCOME_STATEMENT, "Gewinn- und Verlustrechnung"),
		(INCOME_STATEMENT_MICROBILG, "Gewinn- und Verlustrechnung nach MicroBilG"),
		(TRANSFERS_TAX_ASSETS, "Steuerlicher Betriebsvermögensvergleich"),
		(DETAILED_INFORMATION, "Detailinformationen zu Positionen"),
		(TRANSFERS_TO_TAX, "Steuerliche Modifikationen"),
		(NOTES, "Anhang"),
		(FIXED_ASSETS_TABLE, "Anlagenspiegel (brutto)"),
	):
		_role_type(appinfo, role, definition, "link:presentationLink")
	_import(schema, HGBROLE_NS, f"../{GCD}/hgbrole-2025-04-01.xsd")
	_import(schema, XBRLI, INSTANCE_XSD)
	_import(schema, GAAP_NS, dimensions_name)
	for concept in GAAP_CONCEPTS:
		_element(schema, "de-gaap-ci", concept)
	_element(schema, "de-gaap-ci", item("bs.ass.groupOnly", "Nur im Konzern", balance="debit"))

	dimensions = _schema(GAAP_NS, "de-gaap-ci")
	dimension_appinfo = _appinfo(dimensions)
	_linkbase_ref(dimension_appinfo, f"{GAAP}-dimensions-label-de.xml", "label")
	_linkbase_ref(dimension_appinfo, f"{GAAP}-dimensions-reference-fiscal.xml", "reference")
	_import(dimensions, XBRLDT, XBRLDT_XSD)
	for concept in DIMENSION_CONCEPTS:
		_element(dimensions, "de-gaap-ci", concept)
	# The domain of a typed dimension is an element in no substitution group: no concept.
	etree.SubElement(
		dimensions,
		f"{{{XS}}}element",
		{"name": "dim_keyType", "id": "de-gaap-ci_dim_keyType", "type": "xs:string"},
	)

	linkbases = {
		f"{GAAP}-presentation-balanceSheet.xml": (
			"presentation",
			BALANCE_SHEET,
			BALANCE_SHEET_PRESENTATION,
			schema_name,
		),
		f"{GAAP}-calculation-balanceSheet.xml": (
			"calculation",
			BALANCE_SHEET,
			BALANCE_SHEET_CALCULATION,
			schema_name,
		),
		f"{GAAP}-presentation-incomeStatement.xml": (
			"presentation",
			INCOME_STATEMENT,
			INCOME_STATEMENT_ARCS,
			schema_name,
		),
		f"{GAAP}-calculation-incomeStatement.xml": (
			"calculation",
			INCOME_STATEMENT,
			INCOME_STATEMENT_ARCS,
			schema_name,
		),
		f"{GAAP}-presentation-incomeStatementMicroBilG.xml": (
			"presentation",
			INCOME_STATEMENT_MICROBILG,
			MICROBILG_ARCS,
			schema_name,
		),
		f"{GAAP}-calculation-incomeStatementMicroBilG.xml": (
			"calculation",
			INCOME_STATEMENT_MICROBILG,
			MICROBILG_ARCS,
			schema_name,
		),
		f"{GAAP}-presentation-transfersTaxAssets.xml": (
			"presentation",
			TRANSFERS_TAX_ASSETS,
			TRANSFERS_TAX_ASSETS_ARCS,
			schema_name,
		),
		f"{GAAP}-calculation-transfersTaxAssets.xml": (
			"calculation",
			TRANSFERS_TAX_ASSETS,
			TRANSFERS_TAX_ASSETS_ARCS,
			schema_name,
		),
		f"{GAAP}-presentation-detailedInformation.xml": (
			"presentation",
			DETAILED_INFORMATION,
			DETAILED_INFORMATION_ARCS,
			schema_name,
		),
		f"{GAAP}-presentation-transfersCommercialCodeToTax.xml": (
			"presentation",
			TRANSFERS_TO_TAX,
			TRANSFERS_TO_TAX_ARCS,
			schema_name,
		),
		f"{GAAP}-dimensions-presentation-notesTableStmOfChgInFAssGross.xml": (
			"presentation",
			NOTES,
			FIXED_ASSETS_PRIMARY_ITEMS,
			dimensions_name,
		),
		f"{GAAP}-dimensions-calculation-notesTableStmOfChgInFAssGross.xml": (
			"calculation",
			NOTES,
			FIXED_ASSETS_CALCULATION,
			dimensions_name,
		),
		f"{GAAP}-dimensions-definition-notesTableStmOfChgInFAssGross-gen.xml": (
			"definition",
			FIXED_ASSETS_TABLE,
			FIXED_ASSETS_MEMBERS,
			schema_name,
		),
		f"{GAAP}-presentation-balanceSheet-group.xml": (
			"presentation",
			BALANCE_SHEET,
			GROUP_ARCS,
			schema_name,
		),
	}
	arcroles = {
		"presentation": PARENT_CHILD,
		"calculation": SUMMATION_ITEM,
		"definition": f"{DIM}domain-member",
	}
	files: dict[Path, bytes] = {}
	for name, (kind, role, arcs, located_in) in linkbases.items():
		linkbase = _Linkbase()
		linkbase.role_ref(role, f"{schema_name}#{role.rsplit('/', 1)[1]}")
		_relationship_link(
			linkbase,
			kind,
			role,
			arcroles[kind],
			arcs,
			located_in,
			"de-gaap-ci",
			weighted=kind == "calculation",
		)
		files[directory / name] = linkbase.bytes()
	files[directory / f"{GAAP}-dimensions-definition-notesTableStmOfChgInFAssGross.xml"] = _table_definition(
		dimensions_name, schema_name
	)

	shell = _schema(f"{GAAP_NS}/shell", "gaap-shell", {"de-gaap-ci": GAAP_NS})
	shell_appinfo = _appinfo(shell)
	commercial_linkbases = [
		name
		for name in (*linkbases, f"{GAAP}-dimensions-definition-notesTableStmOfChgInFAssGross.xml")
		if "MicroBilG" not in name and not name.endswith("-group.xml")
	]
	for name in commercial_linkbases:
		_linkbase_ref(shell_appinfo, name, _kind_of(name))
	_import(shell, XBRLI, INSTANCE_XSD)
	_import(shell, GAAP_NS, schema_name)

	microbilg = _schema(f"{GAAP_NS}/shell-microbilg", "gaap-shell-microbilg", {"de-gaap-ci": GAAP_NS})
	microbilg_appinfo = _appinfo(microbilg)
	for name in commercial_linkbases:
		if "incomeStatement" not in name:
			_linkbase_ref(microbilg_appinfo, name, _kind_of(name))
	for name in (
		f"{GAAP}-presentation-incomeStatementMicroBilG.xml",
		f"{GAAP}-calculation-incomeStatementMicroBilG.xml",
	):
		_linkbase_ref(microbilg_appinfo, name, _kind_of(name))
	_import(microbilg, GAAP_NS, schema_name)

	fiscal = _schema(f"{GAAP_NS}/shell-fiscal", "gaap-shell-fiscal", {"de-gaap-ci": GAAP_NS})
	fiscal_appinfo = _appinfo(fiscal)
	_linkbase_ref(fiscal_appinfo, f"{GAAP}-label-fiscal-de.xml", "label")
	_linkbase_ref(fiscal_appinfo, f"{GAAP}-label-fiscal-terse60-de.xml", "label")
	_import(fiscal, f"{GAAP_NS}/shell", f"{GAAP}-shell.xsd")

	group = _schema(f"{GAAP_NS}/shell-group", "gaap-shell-group", {"de-gaap-ci": GAAP_NS})
	_linkbase_ref(_appinfo(group), f"{GAAP}-presentation-balanceSheet-group.xml", "presentation")
	_import(group, f"{GAAP_NS}/shell", f"{GAAP}-shell.xsd")

	all_concepts = [*GAAP_CONCEPTS, item("bs.ass.groupOnly", "Nur im Konzern", balance="debit")]
	files |= {
		directory / schema_name: _bytes(schema),
		directory / dimensions_name: _bytes(dimensions),
		directory / f"{GAAP}-shell.xsd": _bytes(shell),
		directory / f"{GAAP}-shell-microbilg.xsd": _bytes(microbilg),
		directory / f"{GAAP}-shell-fiscal.xsd": _bytes(fiscal),
		directory / f"{GAAP}-shell-group.xsd": _bytes(group),
		directory / labels_name: _labels("de-gaap-ci", schema_name, all_concepts),
		directory / f"{GAAP}-label-guidance-de.xml": _guidance("de-gaap-ci", schema_name, all_concepts),
		directory / f"{GAAP}-label-fiscal-de.xml": _fiscal_labels("de-gaap-ci", schema_name, labels_name),
		directory / f"{GAAP}-label-fiscal-terse60-de.xml": _terse60("de-gaap-ci", schema_name),
		directory / f"{GAAP}-reference.xml": _references("de-gaap-ci", schema_name, all_concepts),
		directory / f"{GAAP}-reference-fiscal.xml": _fiscal_references(
			"de-gaap-ci", schema_name, GAAP_CONCEPTS
		),
		directory / f"{GAAP}-dimensions-label-de.xml": _labels(
			"de-gaap-ci", dimensions_name, DIMENSION_CONCEPTS
		),
		directory / f"{GAAP}-dimensions-reference-fiscal.xml": _fiscal_references(
			"de-gaap-ci", dimensions_name, DIMENSION_CONCEPTS
		),
	}
	return files


def _kind_of(name: str) -> str:
	for kind in ("presentation", "calculation", "definition"):
		if f"-{kind}-" in name:
			return kind
	raise ValueError(name)


def _table_definition(dimensions: str, schema: str) -> bytes:
	"""The hypercube of the Anlagenspiegel: the primary items under table.nt.ass.gross, its two dimensions with their
	domains, as de-gaap-ci-2025-04-01-dimensions-definition-notesTableStmOfChgInFAssGross.xml has them."""
	linkbase = _Linkbase()
	link = linkbase.link("definitionLink", FIXED_ASSETS_TABLE)
	names = {
		"table.nt.ass.gross": dimensions,
		"cube_.nt.ass.gross": dimensions,
		"dim_taxTrans": dimensions,
		"dim_taxBal": dimensions,
		"dim_comBal": dimensions,
		"dim_diffComToTaxBal": dimensions,
		"dim_changes.nt.ass.gross": dimensions,
		"bs.ass.fixAss": schema,
		**{name: dimensions for parent, child, _ in FIXED_ASSETS_PRIMARY_ITEMS for name in (parent, child)},
	}
	for name, file in names.items():
		_loc(link, f"{file}#de-gaap-ci_{name}", f"de-gaap-ci_{name}")
	arcs = [
		("all", "table.nt.ass.gross", "cube_.nt.ass.gross", {"xbrldt_contextElement": "scenario"}),
		("hypercube-dimension", "cube_.nt.ass.gross", "dim_taxTrans", {}),
		("dimension-domain", "dim_taxTrans", "dim_taxBal", {}),
		("domain-member", "dim_taxBal", "dim_diffComToTaxBal", {"order": "2"}),
		("domain-member", "dim_taxBal", "dim_comBal", {}),
		("hypercube-dimension", "cube_.nt.ass.gross", "dim_changes.nt.ass.gross", {"order": "2"}),
		("dimension-domain", "dim_changes.nt.ass.gross", "bs.ass.fixAss", {}),
		*(
			("domain-member", parent, child, {"order": str(index)})
			for index, (parent, child, _) in enumerate(FIXED_ASSETS_PRIMARY_ITEMS, start=1)
		),
	]
	for arcrole, source, target, attributes in arcs:
		_arc(
			link,
			"definitionArc",
			f"{DIM}{arcrole}",
			f"de-gaap-ci_{source}",
			f"de-gaap-ci_{target}",
			**attributes,
		)
	return linkbase.bytes()


def archive(directory: Path, name: str = VERSION.archive_name) -> tuple[Path, str]:
	"""The package as a zip with the module directories at its top, and its SHA-256."""
	package = write(directory / "package")
	path = directory / name
	with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zipped:
		for file in sorted(package.rglob("*")):
			if file.is_file():
				zipped.write(file, file.relative_to(package).as_posix())
	return path, hashlib.sha256(path.read_bytes()).hexdigest()
