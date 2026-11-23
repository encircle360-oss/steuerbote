"""The worked example „Muster IT GmbH“: a GmbH with SKR03, a calendar-year Wirtschaftsjahr, one Betriebsstätte with
a Hebesatz of 400 %, no carry-forwards and an Einlagekonto of 0. All figures are invented.

The ledger: revenue less expenses of 100 000 € (among them rent 24 000 €, car leasing 6 000 €, software licences
10 000 €, interest 5 000 €, entertainment 1 400 € and 600 €, gifts 300 €, a Verspätungszuschlag 200 € and a donation
1 000 €), CFD gains 40 000 € and losses 55 000 € classed as Termingeschäfte, dividends of 8 000 € from listed shares
below 10 % and of 12 000 € from a holding of 12 %, gains of 30 000 € and losses of 12 000 € on sales of shares, a
write-down of 4 000 €: 119 000 € before taxes on income. Booked in the year: Vorauszahlungen of 10 000 € KSt, 550 € SolZ
and 15 000 € GewSt, Kapitalertragsteuer of 5 000 € and 275 € SolZ on it.

The result: zu versteuerndes Einkommen 111 200 €, Körperschaftsteuer 16 680,00 €, Solidaritätszuschlag 917,40 €,
due 1 680,00 € and 92,40 €; Gewerbeertrag 107 600 €, Messbetrag 3 766 €, Gewerbesteuer 15 064,00 €, due 64,00 €.
"""

from decimal import Decimal
from unittest import TestCase

from steuerbote.gewst import chain as gewst
from steuerbote.kst import chain as kst
from steuerbote.kst.categories import AccountRule, Category, Mapping, TradingClass
from steuerbote.kst.einlagekonto import roll_forward
from steuerbote.kst.holdings import Holding, HoldingResult
from steuerbote.kst.provisions import ACCOUNTS, ProvisionRow, Tax, propose
from steuerbote.kst.tests.support import FIGURES, credit, debit

ZERO = Decimal("0")
MAPPING = Mapping(
	"SKR03",
	(
		AccountRule("2200", Category.KST),
		AccountRule("2208", Category.SOLZ),
		AccountRule("2216", Category.SOLZ),
		AccountRule("2213", Category.KAPEST),
		AccountRule("4320", Category.GEWST),
		AccountRule("4397", Category.ANCILLARY),
		AccountRule("4635", Category.GIFTS_NONDEDUCTIBLE),
		AccountRule("4654", Category.ENTERTAINMENT_NONDEDUCTIBLE),
		AccountRule("4650", Category.ENTERTAINMENT_DEDUCTIBLE),
		AccountRule("2383", Category.DONATIONS),
		AccountRule("2655", Category.DIVIDENDS),
		AccountRule("2625", Category.DIVIDENDS),
		AccountRule("2726", Category.SHARE_GAIN),
		AccountRule("2326", Category.SHARE_LOSS),
		AccountRule("4876", Category.SHARE_WRITEDOWN),
		AccountRule("2654", Category.TRADING_UNCLASSIFIED, TradingClass.DERIVATIVES),
		AccountRule("2166", Category.TRADING_UNCLASSIFIED, TradingClass.DERIVATIVES),
		AccountRule("2110", Category.INTEREST),
		AccountRule("4570", Category.RENT_MOVABLE),
		AccountRule("4210", Category.RENT_IMMOVABLE),
		AccountRule("4964", Category.LICENCES),
	),
)
LEDGER = (
	credit("8400", "220000.00", "SINV-1"),
	debit("4120", "60000.00", "PAY-1"),
	debit("4210", "24000.00", "PINV-1"),
	debit("4570", "6000.00", "PINV-2"),
	debit("4964", "10000.00", "PINV-3"),
	debit("2110", "5000.00", "JV-1"),
	debit("4650", "1400.00", "PINV-4"),
	debit("4654", "600.00", "PINV-4"),
	debit("4635", "300.00", "PINV-5"),
	debit("4397", "200.00", "JV-2"),
	debit("2383", "1000.00", "JV-3"),
	debit("4980", "11500.00", "PINV-6"),
	credit("2654", "40000.00", "TRADE-1"),
	debit("2166", "55000.00", "TRADE-2"),
	credit("2655", "8000.00", "DIV-1"),
	credit("2625", "12000.00", "DIV-2"),
	credit("2726", "30000.00", "SALE-1"),
	debit("2326", "12000.00", "SALE-2"),
	debit("4876", "4000.00", "TW-1"),
	*(debit("2200", "2500.00", f"KST-{quarter}") for quarter in range(1, 5)),
	*(debit("2208", "137.50", f"SOLZ-{quarter}") for quarter in range(1, 5)),
	*(debit("4320", "3750.00", f"GEWST-{quarter}") for quarter in range(1, 5)),
	debit("2213", "5000.00", "DIV-1"),
	debit("2216", "275.00", "DIV-1"),
)
HOLDINGS = (
	HoldingResult(Holding("Gamma AG", Decimal("0.5"), Decimal("0.5")), Decimal("8000.00")),
	HoldingResult(Holding("Beta GmbH", Decimal("12"), Decimal("12")), Decimal("12000.00")),
)


def koerperschaftsteuer(*extra) -> kst.KstResult:
	inputs = kst.KstInputs(
		2026,
		(*LEDGER, *extra),
		MAPPING,
		holdings=HOLDINGS,
		capital_gains_tax_credit=Decimal("5000.00"),
		solz_credit=Decimal("275.00"),
		kst_prepayments=Decimal("10000.00"),
		solz_prepayments=Decimal("550.00"),
	)
	return kst.compute(inputs, FIGURES)


def gewerbesteuer(result: kst.KstResult) -> gewst.GewstResult:
	return gewst.compute(result, gewst.GewstInputs(Decimal("400"), prepayments=Decimal("15000.00")), FIGURES)


def declared(result, *keys: str) -> dict[str, Decimal]:
	return {key: result.lines[key].declared for key in keys}


class MusterItGmbhTest(TestCase):
	def test_the_lines_of_anlage_gk(self):
		result = koerperschaftsteuer()
		self.assertEqual(
			declared(
				result,
				"net_income",
				"derivatives_loss",
				"corporate_tax",
				"solidarity_surcharge",
				"capital_gains_tax",
				"trade_tax",
				"ancillary",
				"nondeductible",
				"donations",
				"p8b_dividends",
				"p8b_dividends_nondeductible",
				"p8b_gains",
				"p8b_losses",
				"p8b_gains_nondeductible",
				"p8b_writedowns",
				"p8b_total",
				"business_income",
			),
			{
				"net_income": Decimal("88175"),
				"derivatives_loss": Decimal("15000"),
				"corporate_tax": Decimal("10000"),
				"solidarity_surcharge": Decimal("825"),
				"capital_gains_tax": Decimal("5000"),
				"trade_tax": Decimal("15000"),
				"ancillary": Decimal("200"),
				"nondeductible": Decimal("900"),
				"donations": Decimal("1000"),
				"p8b_dividends": Decimal("12000"),
				"p8b_dividends_nondeductible": Decimal("600"),
				"p8b_gains": Decimal("30000"),
				"p8b_losses": Decimal("12000"),
				"p8b_gains_nondeductible": Decimal("1500"),
				"p8b_writedowns": Decimal("4000"),
				"p8b_total": Decimal("-23900"),
				"business_income": Decimal("112200"),
			},
		)

	def test_the_koerperschaftsteuer_and_the_solidaritaetszuschlag(self):
		result = koerperschaftsteuer()
		self.assertEqual(
			declared(result, "sum_of_income", "donation_deduction", "total_income", "loss_deduction", "zve"),
			{
				"sum_of_income": Decimal("112200"),
				"donation_deduction": Decimal("1000"),
				"total_income": Decimal("111200"),
				"loss_deduction": ZERO,
				"zve": Decimal("111200"),
			},
		)
		self.assertEqual((result.kst, result.solz), (Decimal("16680"), Decimal("917.40")))
		self.assertEqual((result.kst_balance, result.solz_balance), (Decimal("1680.00"), Decimal("92.40")))
		self.assertEqual(result.derivatives.remaining, Decimal("15000"))
		self.assertEqual(result.findings, ())

	def test_the_gewerbesteuer(self):
		result = gewerbesteuer(koerperschaftsteuer())
		self.assertEqual(
			declared(
				result,
				"profit",
				"financing_parts",
				"financing_addback",
				"dividends_addback",
				"donation_cut",
				"gewerbeertrag",
			),
			{
				"profit": Decimal("97200"),
				"financing_parts": Decimal("20700"),
				"financing_addback": ZERO,
				"dividends_addback": Decimal("11400"),
				"donation_cut": Decimal("1000"),
				"gewerbeertrag": Decimal("107600"),
			},
		)
		self.assertEqual((result.gewerbeertrag, result.messbetrag), (Decimal("107600"), Decimal("3766")))
		self.assertEqual((result.gewst, result.balance), (Decimal("15064.00"), Decimal("64.00")))
		self.assertEqual([line.holding.result.holding.name for line in result.beg], ["Beta GmbH"])
		self.assertEqual(result.findings, ())

	def test_the_provisions(self):
		tax = koerperschaftsteuer()
		self.assertEqual(
			propose(tax, gewerbesteuer(tax), ACCOUNTS["SKR03"]),
			(
				ProvisionRow(Tax.KST, Decimal("1680.00"), "2200", "0963", 2026),
				ProvisionRow(Tax.SOLZ, Decimal("92.40"), "2208", "0963", 2026),
				ProvisionRow(Tax.GEWST, Decimal("64.00"), "4320", "0956", 2026),
			),
		)

	def test_the_zve_stays_the_same_once_the_provisions_are_posted(self):
		before = koerperschaftsteuer()
		posted = tuple(
			debit(row.debit_account, str(row.amount), "JV-PROVISIONS")
			for row in propose(before, gewerbesteuer(before), ACCOUNTS["SKR03"])
		)
		after = koerperschaftsteuer(*posted)
		self.assertEqual(after.lines["net_income"].exact, Decimal("86338.60"))
		self.assertEqual(after.lines["net_income"].declared, Decimal("86339"))
		self.assertEqual(after.lines["solidarity_surcharge"].declared, Decimal("917"))
		self.assertEqual((after.business_income, after.zve), (before.business_income, before.zve))
		self.assertEqual((after.kst, after.solz), (before.kst, before.solz))
		self.assertEqual(gewerbesteuer(after).gewst, gewerbesteuer(before).gewst)

	def test_the_einlagekonto_goes_from_zero_to_zero(self):
		found = roll_forward(ZERO, FIGURES)
		self.assertEqual((found.opening, found.closing, found.findings), (ZERO, ZERO, ()))
