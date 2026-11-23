"""Two invented companies for the tests of the Offenlegung: a Kleinstkapitalgesellschaft and a small GmbH, each with
the books of 2026 and 2025, its Angaben, signatures and master data.

The companies, their register entries, persons, addresses and amounts are invented. Each year of books balances,
as double entry does: its cash is the balance of every other account, so Aktiva and Passiva agree. instances() gives
the instances of the Offenlegung the tests write from them, and steuerbote/hgb/tests/fixtures holds the files of the
two companies.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path
from types import MappingProxyType

from lxml import etree

from steuerbote.hgb import instance
from steuerbote.hgb.disclosure import Mode, Signature, publication
from steuerbote.hgb.instance import Address, Instance, MasterData, Notes
from steuerbote.hgb.notes import (
	AdvanceKind,
	Answer,
	Contingency,
	ContingentLiability,
	NoteAnswer,
	OfficerAdvance,
	OfficerGroup,
	RegisterData,
)
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import Balance, ProfitPresentation, RemainingTerm, build
from steuerbote.xbrl.facts import Periods

SHORT = RemainingTerm.UP_TO_ONE_YEAR
MEDIUM = RemainingTerm.ONE_TO_FIVE_YEARS
LONG = RemainingTerm.OVER_FIVE_YEARS

GKV = "is.netIncome.regular.operatingTC"
SALES = f"{GKV}.grossTradingProfit.totalOutput.netSales"
SALES_19 = f"{SALES}.grossSales.generalRateVAT"
MATERIAL = f"{GKV}.grossTradingProfit.materialServices.material"
SALARIES = f"{GKV}.staff.salaries"
DEPRECIATION = f"{GKV}.deprAmort.fixAss"
OTHER_COSTS = f"{GKV}.otherCost"
INCOME_TAX = "is.netIncome.tax"
BANK = "bs.ass.currAss.cashEquiv.bank"
VAT_RECEIVABLE = "bs.ass.currAss.receiv.other.vat"
SUBSCRIBED = "bs.eqLiab.equity.subscribed.corp"
UNCALLED = "bs.eqLiab.equity.subscribed.unpaidCap"
OWN_SHARES = "bs.eqLiab.equity.subscribed.ownSharesdeducted"
VAT_PAYABLE = "bs.eqLiab.liab.other.theroffTax.vat"

PARENTS = {
	BANK: "bs.ass.currAss.cashEquiv",
	VAT_RECEIVABLE: "bs.ass.currAss.receiv.other",
	SUBSCRIBED: "bs.eqLiab.equity.subscribed",
	UNCALLED: "bs.eqLiab.equity.subscribed",
	OWN_SHARES: "bs.eqLiab.equity.subscribed",
	VAT_PAYABLE: "bs.eqLiab.liab.other.theroffTax",
	"bs.eqLiab.liab.other.theroffTax": "bs.eqLiab.liab.other",
	SALES_19: f"{SALES}.grossSales",
	f"{SALES}.grossSales": SALES,
}
"""An extract of the calculation linkbase of the HGB-Taxonomie 6.9: each concept with the one it adds up to."""

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = ("kleinst", "klein")
"""The instances whose files the fixtures hold, as offenlegung-<name>.xbrl."""
FISCAL_YEAR = Periods(date(2026, 1, 1), date(2026, 12, 31), None, date(2025, 1, 1), date(2025, 12, 31))
FIRST_YEAR = Periods(date(2026, 1, 1), date(2026, 12, 31))
ADDRESS = Address("Musterweg", "12", "12345", "Musterstadt")
GENERATED_ON = date(2027, 7, 1)


def balanced(*balances: Balance) -> tuple[Balance, ...]:
	"""The balances with the bank account that makes them add up to zero."""
	rest = sum((balance.amount for balance in balances), Decimal("0"))
	return (*balances, Balance(BANK, -rest, source="1200 Bank"))


def euros(amount: str) -> Decimal:
	return Decimal(amount)


# Beispiel Werkstatt GmbH, a Kleinstkapitalgesellschaft: a workshop with two employees.
KLEINST_2026 = balanced(
	Balance("bs.ass.fixAss.tan.otherEquipm", euros("18400.40"), source="0420 Technische Anlagen"),
	Balance("bs.ass.currAss.inventory.finishedAndMerch", euros("6200.00"), source="3980 Bestand Waren"),
	Balance("bs.ass.currAss.receiv.trade", euros("9870.25"), remaining_term=SHORT, source="1400 Forderungen"),
	Balance(
		"bs.ass.currAss.receiv.shareholders",
		euros("2500.00"),
		shareholder=True,
		remaining_term=SHORT,
		source="1300 Forderungen gegen Gesellschafter",
	),
	Balance("bs.ass.prepaidExp", euros("480.00"), source="0980 Aktive Rechnungsabgrenzung"),
	Balance(SUBSCRIBED, euros("-25000.00"), source="0800 Gezeichnetes Kapital"),
	Balance("bs.eqLiab.equity.retainedEarnings", euros("-12100.00"), source="0860 Gewinnvortrag"),
	Balance("bs.eqLiab.accruals.tax", euros("-2900.00"), source="0950 Steuerrückstellungen"),
	Balance("bs.eqLiab.accruals.other", euros("-1500.00"), source="0970 Sonstige Rückstellungen"),
	Balance("bs.eqLiab.liab.bank", euros("-9000.00"), remaining_term=MEDIUM, source="0650 Darlehen"),
	Balance("bs.eqLiab.liab.trade", euros("-4321.50"), remaining_term=SHORT, source="1600 Verbindlichkeiten"),
	Balance(
		"bs.eqLiab.liab.shareholders",
		euros("-3000.00"),
		shareholder=True,
		remaining_term=SHORT,
		source="0755 Verbindlichkeiten gegenüber Gesellschaftern",
	),
	Balance(VAT_PAYABLE, euros("-1850.00"), remaining_term=SHORT, source="1776 Umsatzsteuer 19 %"),
	Balance(SALES_19, euros("-180000.00"), source="8400 Erlöse 19 % USt"),
	Balance(MATERIAL, euros("60000.00"), source="3400 Wareneingang 19 % Vorsteuer"),
	Balance(SALARIES, euros("55000.00"), source="4120 Gehälter"),
	Balance(DEPRECIATION, euros("4600.00"), source="4830 Abschreibungen auf Sachanlagen"),
	Balance(OTHER_COSTS, euros("38000.00"), source="4900 Sonstige betriebliche Aufwendungen"),
	Balance(INCOME_TAX, euros("3400.00"), source="4320 Gewerbesteuer"),
)
KLEINST_2025 = balanced(
	Balance("bs.ass.fixAss.tan.otherEquipm", euros("21000.00")),
	Balance("bs.ass.currAss.inventory.finishedAndMerch", euros("4800.00")),
	Balance("bs.ass.currAss.receiv.trade", euros("7200.00"), remaining_term=SHORT),
	Balance("bs.ass.currAss.receiv.shareholders", euros("1500.00"), shareholder=True, remaining_term=SHORT),
	Balance("bs.ass.prepaidExp", euros("300.00")),
	Balance(SUBSCRIBED, euros("-25000.00")),
	Balance("bs.eqLiab.accruals.tax", euros("-2100.00")),
	Balance("bs.eqLiab.accruals.other", euros("-1700.00")),
	Balance("bs.eqLiab.liab.bank", euros("-12000.00"), remaining_term=MEDIUM),
	Balance("bs.eqLiab.liab.trade", euros("-3950.75"), remaining_term=SHORT),
	Balance("bs.eqLiab.liab.shareholders", euros("-2000.00"), shareholder=True, remaining_term=SHORT),
	Balance(VAT_PAYABLE, euros("-1600.00"), remaining_term=SHORT),
	Balance(SALES_19, euros("-150000.00")),
	Balance(MATERIAL, euros("50000.00")),
	Balance(SALARIES, euros("48000.00")),
	Balance(DEPRECIATION, euros("4200.00")),
	Balance(OTHER_COSTS, euros("33000.00")),
	Balance(INCOME_TAX, euros("2700.00")),
)

# Beispiel Handel GmbH, a small company: a trade with 24 employees, part of its Stammkapital not yet called.
KLEIN_2026 = balanced(
	Balance("bs.ass.fixAss.intan.concessionBrands", euros("12500.00"), source="0027 EDV-Software"),
	Balance("bs.ass.fixAss.tan.landBuildings", euros("400000.00"), source="0090 Geschäftsbauten"),
	Balance("bs.ass.fixAss.tan.otherEquipm", euros("85300.00"), source="0650 Büroeinrichtung"),
	Balance("bs.ass.fixAss.fin.particip", euros("25000.00"), source="0510 Beteiligungen"),
	Balance("bs.ass.currAss.inventory.finishedAndMerch", euros("410000.00"), source="3980 Bestand Waren"),
	Balance(
		"bs.ass.currAss.receiv.trade", euros("380449.40"), remaining_term=SHORT, source="1400 Forderungen"
	),
	Balance(
		"bs.ass.currAss.receiv.trade",
		euros("20000.00"),
		remaining_term=MEDIUM,
		source="1401 Forderungen mit Restlaufzeit über einem Jahr",
	),
	Balance(VAT_RECEIVABLE, euros("15200.00"), remaining_term=SHORT, source="1576 Abziehbare Vorsteuer 19 %"),
	Balance("bs.ass.prepaidExp", euros("4800.00"), source="0980 Aktive Rechnungsabgrenzung"),
	Balance(SUBSCRIBED, euros("-50000.00"), source="0800 Gezeichnetes Kapital"),
	Balance(UNCALLED, euros("12500.00"), source="0820 Nicht eingeforderte ausstehende Einlagen"),
	Balance("bs.eqLiab.equity.capRes", euros("-20000.00"), source="0840 Kapitalrücklage"),
	Balance("bs.eqLiab.equity.revenueRes.other", euros("-100000.00"), source="0855 Andere Gewinnrücklagen"),
	Balance("bs.eqLiab.equity.retainedEarnings", euros("-245000.00"), source="0860 Gewinnvortrag"),
	Balance("bs.eqLiab.accruals.tax", euros("-38000.00"), source="0950 Steuerrückstellungen"),
	Balance("bs.eqLiab.accruals.other", euros("-27500.00"), source="0970 Sonstige Rückstellungen"),
	Balance("bs.eqLiab.liab.bank", euros("-400000.00"), remaining_term=MEDIUM, source="0640 Darlehen"),
	Balance("bs.eqLiab.liab.bank", euros("-120000.00"), remaining_term=LONG, source="0660 Darlehen"),
	Balance(
		"bs.eqLiab.liab.trade", euros("-298000.00"), remaining_term=SHORT, source="1600 Verbindlichkeiten"
	),
	Balance(VAT_PAYABLE, euros("-41000.00"), remaining_term=SHORT, source="1776 Umsatzsteuer 19 %"),
	Balance(SALES_19, euros("-4200000.00"), source="8400 Erlöse 19 % USt"),
	Balance(MATERIAL, euros("2900000.00"), source="3400 Wareneingang 19 % Vorsteuer"),
	Balance(SALARIES, euros("820000.00"), source="4120 Gehälter"),
	Balance(DEPRECIATION, euros("52000.00"), source="4830 Abschreibungen auf Sachanlagen"),
	Balance(OTHER_COSTS, euros("260000.00"), source="4900 Sonstige betriebliche Aufwendungen"),
	Balance(INCOME_TAX, euros("61000.00"), source="7600 Körperschaftsteuer"),
)
KLEIN_2025 = balanced(
	Balance("bs.ass.fixAss.intan.concessionBrands", euros("15000.00")),
	Balance("bs.ass.fixAss.tan.landBuildings", euros("412000.00")),
	Balance("bs.ass.fixAss.tan.otherEquipm", euros("91200.00")),
	Balance("bs.ass.fixAss.fin.particip", euros("25000.00")),
	Balance("bs.ass.currAss.inventory.finishedAndMerch", euros("365000.00")),
	Balance("bs.ass.currAss.receiv.trade", euros("341870.10"), remaining_term=SHORT),
	Balance(VAT_RECEIVABLE, euros("11800.00"), remaining_term=SHORT),
	Balance("bs.ass.prepaidExp", euros("3900.00")),
	Balance(SUBSCRIBED, euros("-50000.00")),
	Balance(UNCALLED, euros("12500.00")),
	Balance("bs.eqLiab.equity.capRes", euros("-20000.00")),
	Balance("bs.eqLiab.equity.revenueRes.other", euros("-100000.00")),
	Balance("bs.eqLiab.equity.retainedEarnings", euros("-162000.00")),
	Balance("bs.eqLiab.accruals.tax", euros("-31000.00")),
	Balance("bs.eqLiab.accruals.other", euros("-24000.00")),
	Balance("bs.eqLiab.liab.bank", euros("-450000.00"), remaining_term=MEDIUM),
	Balance("bs.eqLiab.liab.bank", euros("-130000.00"), remaining_term=LONG),
	Balance("bs.eqLiab.liab.trade", euros("-275000.00"), remaining_term=SHORT),
	Balance(VAT_PAYABLE, euros("-36500.00"), remaining_term=SHORT),
	Balance(SALES_19, euros("-3900000.00")),
	Balance(MATERIAL, euros("2700000.00")),
	Balance(SALARIES, euros("790000.00")),
	Balance(DEPRECIATION, euros("50000.00")),
	Balance(OTHER_COSTS, euros("222000.00")),
	Balance(INCOME_TAX, euros("55000.00")),
)


def kleinst_statement():
	return build(2026, SizeClass.KLEINST, KLEINST_2026, parents=PARENTS, prior=KLEINST_2025)


def klein_statement():
	return build(2026, SizeClass.KLEIN, KLEIN_2026, parents=PARENTS, prior=KLEIN_2025)


KLEINST_REGISTER = RegisterData(
	"Beispiel Werkstatt GmbH", "Musterstadt", "Amtsgericht Musterstadt", "HRB 12345"
)
KLEIN_REGISTER = RegisterData("Beispiel Handel GmbH", "Musterstadt", "Amtsgericht Musterstadt", "HRB 67890")
YES, NO, NOT_APPLICABLE = Answer.YES, Answer.NO, Answer.NOT_APPLICABLE

KLEINST_NOTES = Notes(
	KLEINST_REGISTER,
	(
		NoteAnswer("HAFTUNGSVERHAELTNISSE", YES, amount=euros("15000.00")),
		NoteAnswer("ORGANKREDITE", YES, amount=euros("8000.00")),
		NoteAnswer("ZUSAETZLICHE-ANGABEN", NO),
	),
	(
		ContingentLiability(
			Contingency.GUARANTEES,
			euros("15000.00"),
			securities="Abtretung von Forderungen aus Lieferungen und Leistungen",
		),
	),
	(
		OfficerAdvance(
			OfficerGroup.MANAGEMENT,
			AdvanceKind.LOAN,
			euros("8000.00"),
			Decimal("3.5"),
			"Laufzeit bis zum 31. Dezember 2028, Tilgung in Jahresraten",
			repaid=euros("2000.00"),
		),
	),
	(Signature("Erika Beispiel", "Geschäftsführerin", "Musterstadt", date(2027, 5, 12)),),
)
KLEIN_NOTES = Notes(
	KLEIN_REGISTER,
	(
		NoteAnswer("ZUSAETZLICHE-ANGABEN", NO),
		NoteAnswer("DARSTELLUNGSSTETIGKEIT", NO),
		NoteAnswer("VORJAHRESBETRAEGE", NO),
		NoteAnswer("MITZUGEHOERIGKEIT", NO),
		NoteAnswer("HAFTUNGSVERHAELTNISSE", YES, amount=euros("80000.00")),
		NoteAnswer("AUSSERPLANMAESSIGE-ABSCHREIBUNGEN", NO),
		NoteAnswer(
			"BEWERTUNGSMETHODEN",
			YES,
			"Die immateriellen Vermögensgegenstände und die Sachanlagen sind zu Anschaffungskosten, vermindert um "
			"planmäßige lineare Abschreibungen, bewertet. Die Waren sind zu Anschaffungskosten oder zum niedrigeren "
			"beizulegenden Wert angesetzt, die Forderungen zum Nennwert.",
		),
		NoteAnswer("METHODENABWEICHUNGEN", NO),
		NoteAnswer("FREMDKAPITALZINSEN", NO),
		NoteAnswer(
			"VERBINDLICHKEITEN",
			YES,
			"Verbindlichkeiten gegenüber Kreditinstituten mit einer Restlaufzeit von mehr als fünf Jahren, durch eine "
			"Grundschuld auf dem Geschäftsgebäude gesichert",
			euros("120000.00"),
		),
		NoteAnswer(
			"FINANZIELLE-VERPFLICHTUNGEN",
			YES,
			"Aus Mietverträgen für Lagerflächen bestehen sonstige finanzielle Verpflichtungen von 96.000 €.",
		),
		NoteAnswer("ARBEITNEHMER", YES, amount=Decimal("23.75")),
		NoteAnswer("ORGANKREDITE", NO),
		NoteAnswer("FIRMENWERT", NOT_APPLICABLE),
		NoteAnswer("MUTTERUNTERNEHMEN", NOT_APPLICABLE),
		NoteAnswer("ZEITWERT", NOT_APPLICABLE),
		NoteAnswer("BEWERTUNGSEINHEITEN", NOT_APPLICABLE),
		NoteAnswer("VERRECHNUNG", NOT_APPLICABLE),
		NoteAnswer(
			"AUSSERGEWOEHNLICHES",
			YES,
			"Die sonstigen betrieblichen Erträge enthalten einen einmaligen Ertrag aus einem Vergleich.",
		),
	),
	(
		ContingentLiability(Contingency.WARRANTIES, euros("30000.00")),
		ContingentLiability(
			Contingency.COLLATERAL,
			euros("50000.00"),
			securities="Grundschuld auf dem Geschäftsgebäude",
			group=True,
		),
	),
	(),
	(
		Signature("Erika Beispiel", "Geschäftsführerin", "Musterstadt", date(2027, 6, 30)),
		Signature("Max Muster", "Geschäftsführer", "Musterstadt", date(2027, 6, 30)),
	),
)

KLEINST_GCD = MasterData(
	FISCAL_YEAR, date(2027, 5, 12), ADDRESS, founded_on=date(2024, 3, 1), generated_on=GENERATED_ON
)
KLEIN_GCD = MasterData(
	FISCAL_YEAR, date(2027, 6, 30), ADDRESS, founded_on=date(2010, 1, 15), generated_on=GENERATED_ON
)
KLEINST_DISCLOSURE = publication(SizeClass.KLEINST, Mode.HINTERLEGUNG)
KLEIN_DISCLOSURE = publication(SizeClass.KLEIN)


@cache
def instances() -> Mapping[str, Instance]:
	"""The instances the tests write, by the names of their files: the two companies, the small one with own shares,
	with a Fehlbetrag and with a Bilanzgewinn, and the Kleinstkapitalgesellschaft in liquidation and in its first
	fiscal year."""
	kleinst, klein = SizeClass.KLEINST, SizeClass.KLEIN
	klein_first_year = replace(KLEIN_GCD, periods=FIRST_YEAR)
	own_shares = (*KLEIN_2026, Balance(OWN_SHARES, euros("5000.00")), Balance(BANK, euros("-5000.00")))
	deficit = (
		Balance(BANK, euros("1000.00")),
		Balance(SUBSCRIBED, euros("-25000.00")),
		Balance("bs.eqLiab.equity.retainedEarnings", euros("30000.00")),
		Balance("bs.eqLiab.liab.trade", euros("-6000.00"), remaining_term=SHORT),
	)
	bilanzgewinn = build(
		2026,
		klein,
		KLEIN_2026,
		parents=PARENTS,
		prior=KLEIN_2025,
		presentation=ProfitPresentation.AFTER_PARTIAL_APPROPRIATION,
	)
	liquidation = replace(KLEINST_NOTES, register=replace(KLEINST_REGISTER, in_liquidation=True))
	first_year = build(2026, kleinst, KLEINST_2026, parents=PARENTS)
	return MappingProxyType(
		{
			"kleinst": instance.build(
				kleinst_statement(), kleinst, KLEINST_NOTES, KLEINST_DISCLOSURE, KLEINST_GCD
			),
			"klein": instance.build(klein_statement(), klein, KLEIN_NOTES, KLEIN_DISCLOSURE, KLEIN_GCD),
			"klein-eigene-anteile": instance.build(
				build(2026, klein, own_shares, parents=PARENTS),
				klein,
				KLEIN_NOTES,
				KLEIN_DISCLOSURE,
				klein_first_year,
			),
			"klein-fehlbetrag": instance.build(
				build(2026, klein, deficit, parents=PARENTS),
				klein,
				KLEIN_NOTES,
				KLEIN_DISCLOSURE,
				klein_first_year,
			),
			"klein-bilanzgewinn": instance.build(
				bilanzgewinn, klein, KLEIN_NOTES, KLEIN_DISCLOSURE, KLEIN_GCD
			),
			"kleinst-liquidation": instance.build(
				kleinst_statement(), kleinst, liquidation, KLEINST_DISCLOSURE, KLEINST_GCD
			),
			"kleinst-erstes-geschaeftsjahr": instance.build(
				first_year,
				kleinst,
				KLEINST_NOTES,
				KLEINST_DISCLOSURE,
				replace(KLEINST_GCD, periods=FIRST_YEAR),
			),
		}
	)


def golden(name: str) -> bytes:
	"""The file of an instance of GOLDEN as the fixtures hold it."""
	return (FIXTURES / f"offenlegung-{name}.xbrl").read_bytes()


def canonical(document: bytes) -> bytes:
	"""The document in the canonical form of XML (Canonical XML 2.0), without the whitespace around its elements."""
	return etree.tostring(etree.fromstring(document), method="c14n2", strip_text=True)
