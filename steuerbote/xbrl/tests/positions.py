"""The fiscal view of the mini taxonomy (steuerbote/xbrl/tests/mini.py) with the positions the tests of the
Bilanzzuordnung need besides: Finanzanlagen with their Ausleihungen, Forderungen with a „davon“ position and an
Auffangposition, sonstige Verbindlichkeiten with their „davon“ position, a Gewinnvortrag, GuV positions for wages and
interest, and a position without a debit or credit balance. Their names follow the real taxonomy, the last one is
invented; labels are those of the real taxonomy, shortened.
"""

from collections.abc import Iterable
from dataclasses import replace
from decimal import Decimal
from functools import cache
from types import MappingProxyType

from steuerbote.xbrl.taxonomy import (
	BALANCE_SHEET,
	INCOME_STATEMENT,
	LABEL,
	MONETARY,
	Arc,
	Balance,
	Concept,
	Fiscal,
	Kind,
	Network,
	PeriodType,
	Requirement,
	Taxonomy,
)
from steuerbote.xbrl.tests import mini

GAAP = "de-gaap-ci"

# name, parent, label, balance, whether the calculation holds it
BALANCE_SHEET_POSITIONS = (
	("bs.ass.fixAss.fin", "bs.ass.fixAss", "Finanzanlagen", Balance.DEBIT, True),
	(
		"bs.ass.fixAss.fin.sharesInAffil",
		"bs.ass.fixAss.fin",
		"Anteile an verbundenen Unternehmen",
		Balance.DEBIT,
		True,
	),
	("bs.ass.fixAss.fin.otherLoans", "bs.ass.fixAss.fin", "Sonstige Ausleihungen", Balance.DEBIT, True),
	(
		"bs.ass.currAss.receiv",
		"bs.ass.currAss",
		"Forderungen und sonstige Vermögensgegenstände",
		Balance.DEBIT,
		True,
	),
	(
		"bs.ass.currAss.receiv.trade",
		"bs.ass.currAss.receiv",
		"Forderungen aus Lieferungen und Leistungen",
		Balance.DEBIT,
		True,
	),
	(
		"bs.ass.currAss.receiv.trade.above1year",
		"bs.ass.currAss.receiv.trade",
		"Forderungen aus Lieferungen und Leistungen, davon mit einer Restlaufzeit von mehr als einem Jahr",
		Balance.DEBIT,
		False,
	),
	(
		"bs.ass.currAss.receiv.other.misc",
		"bs.ass.currAss.receiv",
		"Forderungen und sonstige Vermögensgegenstände, sonstige Vermögensgegenstände, nicht zuordenbar",
		Balance.DEBIT,
		True,
	),
	("bs.ass.noSide", "bs.ass", "Position ohne Soll oder Haben", None, True),
	(
		"bs.eqLiab.equity.retainedEarnings",
		"bs.eqLiab.equity",
		"Gewinnvortrag/Verlustvortrag",
		Balance.CREDIT,
		True,
	),
	("bs.eqLiab.liab.other", "bs.eqLiab.liab", "sonstige Verbindlichkeiten", Balance.CREDIT, True),
	(
		"bs.eqLiab.liab.other.theroffTax",
		"bs.eqLiab.liab.other",
		"sonstige Verbindlichkeiten, davon aus Steuern",
		Balance.CREDIT,
		True,
	),
)
INCOME_STATEMENT_POSITIONS = (
	("is.netIncome.staff", "is.netIncome", "Personalaufwand", Balance.DEBIT, True),
	(
		"is.netIncome.interestIncome",
		"is.netIncome",
		"sonstige Zinsen und ähnliche Erträge",
		Balance.CREDIT,
		True,
	),
	(
		"is.netIncome.interestIncome.assoc",
		"is.netIncome.interestIncome",
		"sonstige Zinsen und ähnliche Erträge, davon aus verbundenen Unternehmen",
		Balance.CREDIT,
		False,
	),
)


@cache
def view() -> Taxonomy:
	"""The fiscal view of the mini taxonomy with the positions above."""
	return with_positions(mini.view(), BALANCE_SHEET_POSITIONS, INCOME_STATEMENT_POSITIONS)


def with_positions(
	base: Taxonomy, balance_sheet: Iterable[tuple], income_statement: Iterable[tuple]
) -> Taxonomy:
	"""The view with positions added below their parents, in the presentation and, where they say so, in the
	calculation of their part."""
	concepts = dict(base.concepts)
	labels = dict(base.labels)
	presentation = dict(base.presentation)
	calculation = dict(base.calculation)
	for role, positions, period in (
		(BALANCE_SHEET, tuple(balance_sheet), PeriodType.INSTANT),
		(INCOME_STATEMENT, tuple(income_statement), PeriodType.DURATION),
	):
		shown, summed = list(presentation[role].arcs), list(calculation[role].arcs)
		for name, parent, label, balance, calculated in positions:
			qualified, above = f"{GAAP}:{name}", f"{GAAP}:{parent}"
			concepts[qualified] = Concept(
				name=qualified,
				namespace=mini.GAAP_NS,
				kind=Kind.ITEM,
				substitution_group="xbrli:item",
				item_type=MONETARY,
				period_type=period,
				balance=balance,
				nillable=True,
				fiscal=Fiscal(requirement=Requirement.RECHNERISCH_NOTWENDIG),
			)
			labels[qualified] = MappingProxyType({LABEL: label})
			shown.append(Arc(above, qualified))
			if calculated:
				summed.append(Arc(above, qualified, weight=_weight(concepts[above], balance)))
		presentation[role] = Network(role, tuple(shown))
		calculation[role] = Network(role, tuple(summed))
	return replace(
		base,
		concepts=MappingProxyType(concepts),
		labels=MappingProxyType(labels),
		presentation=MappingProxyType(presentation),
		calculation=MappingProxyType(calculation),
	)


def _weight(parent: Concept, balance: Balance | None) -> Decimal:
	"""1 for an item on the side of its total, -1 for one on the other side (Technischer Leitfaden 6.9, A.13)."""
	return Decimal(1) if balance is None or parent.balance in (None, balance) else Decimal(-1)
