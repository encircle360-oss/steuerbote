"""The Gewerbeertrag of a GmbH from the result of the Körperschaftsteuer: GewSt 1 A and Anlage BEG."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.gewst.chain import STEPS, GewstInputs, compute
from steuerbote.kst import chain as kst
from steuerbote.kst.categories import AccountRule, Category, Mapping, TradingClass
from steuerbote.kst.holdings import Holding, HoldingResult
from steuerbote.kst.tests.support import FIGURES, credit, debit

ZERO = Decimal("0")
MAPPING = Mapping(
	"SKR03",
	(
		AccountRule("2110", Category.INTEREST),
		AccountRule("2140", Category.ANNUITIES),
		AccountRule("2120", Category.SILENT_PARTNER),
		AccountRule("4570", Category.RENT_MOVABLE),
		AccountRule("4571", Category.RENT_MOVABLE_EV),
		AccountRule("4210", Category.RENT_IMMOVABLE),
		AccountRule("4964", Category.LICENCES),
		AccountRule("2375", Category.PROPERTY_TAX_OWN),
		AccountRule("2383", Category.DONATIONS),
		AccountRule("2625", Category.DIVIDENDS),
		AccountRule("2654", Category.TRADING_UNCLASSIFIED, TradingClass.DERIVATIVES),
		AccountRule("2166", Category.TRADING_UNCLASSIFIED, TradingClass.DERIVATIVES),
	),
)


def koerperschaftsteuer(*lines, **kwargs) -> kst.KstResult:
	kwargs.setdefault("loss_carry_back", ZERO)
	return kst.compute(kst.KstInputs(2026, tuple(lines), MAPPING, **kwargs), FIGURES)


def gewerbesteuer(*lines, kst_inputs: dict | None = None, **kwargs):
	kwargs.setdefault("hebesatz", Decimal("400"))
	return compute(koerperschaftsteuer(*lines, **(kst_inputs or {})), GewstInputs(**kwargs), FIGURES)


def holding(name: str, share: str, ez_share: str | None = None, foreign: bool = False) -> Holding:
	return Holding(name, Decimal(share), Decimal(ez_share or share), foreign=foreign)


class StepsTest(TestCase):
	def test_every_step_has_a_key_of_its_own_a_label_and_a_law(self):
		keys = [step.key for step in STEPS]
		self.assertEqual(len(keys), len(set(keys)))
		for step in STEPS:
			with self.subTest(step=step.key):
				self.assertTrue(step.label)
				self.assertRegex(step.law, r"§ \d+")

	def test_names_the_lines_of_gewst_1_a(self):
		lines = {step.key: (step.line, step.field) for step in STEPS if step.field}
		self.assertEqual(
			lines,
			{
				"profit": ("39", "E4001703"),
				"interest": ("50", "E4003202"),
				"annuities": ("51", "E4003302"),
				"silent_partner": ("52", "E4003407"),
				"rent_movable": ("53", "E4003502"),
				"rent_movable_ev": ("54", "E4004402"),
				"rent_immovable": ("55", "E4003602"),
				"licences": ("56", "E4003703"),
				"dividends_addback": ("77", "E4006601"),
				"dividends_cut": ("81", "E4006801"),
				"property_tax": ("87", "E4008701"),
				"donations": ("92d", "E4003403"),
			},
		)


class ProfitTest(TestCase):
	"""Line 39: the Summe der Einkünfte of Anlage ZVE with the effects of § 15 Absatz 4 EStG reversed."""

	def test_is_the_summe_der_einkuenfte(self):
		result = gewerbesteuer(credit("8400", "100000.00"))
		self.assertEqual(result.lines["profit"].declared, Decimal("100000"))

	def test_deducts_the_loss_of_the_termingeschaefte_that_the_koerperschaftsteuer_adds_back(self):
		result = gewerbesteuer(
			credit("8400", "100000.00"), credit("2654", "40000.00"), debit("2166", "55000.00")
		)
		self.assertEqual(result.lines["profit"].declared, Decimal("85000"))

	def test_adds_the_gain_of_the_termingeschaefte_that_the_koerperschaftsteuer_sets_against_its_pool(self):
		result = gewerbesteuer(
			credit("8400", "100000.00"),
			credit("2654", "4000.00"),
			kst_inputs={"derivatives_carry_forward": Decimal("10000")},
		)
		self.assertEqual(result.lines["profit"].declared, Decimal("104000"))


class FinancingTest(TestCase):
	"""§ 8 Nummer 1 GewStG: lines 50 to 57 in full; a quarter of the parts beyond 200 000 Euro is added back."""

	def test_declares_the_amounts_in_full_and_adds_back_nothing_below_the_allowance(self):
		result = gewerbesteuer(
			credit("8400", "200000.00"),
			debit("2110", "5000.00"),
			debit("4570", "6000.00"),
			debit("4210", "24000.00"),
			debit("4964", "10000.00"),
		)
		self.assertEqual(
			[
				result.lines[key].declared
				for key in ("interest", "rent_movable", "rent_immovable", "licences")
			],
			[Decimal("5000"), Decimal("6000"), Decimal("24000"), Decimal("10000")],
		)
		self.assertEqual(result.lines["financing_parts"].declared, Decimal("20700"))
		self.assertEqual(result.lines["financing_addback"].declared, ZERO)

	def test_adds_back_a_quarter_of_the_parts_beyond_200_000_euro(self):
		result = gewerbesteuer(
			credit("8400", "2000000.00"),
			debit("2110", "150000.00"),
			debit("2140", "10000.00"),
			debit("2120", "20000.00"),
			debit("4570", "100000.00"),
			debit("4571", "100000.00"),
			debit("4210", "100000.00"),
			debit("4964", "40000.00"),
		)
		self.assertEqual(result.lines["financing_parts"].declared, Decimal("270000"))
		self.assertEqual(result.lines["financing_addback"].declared, Decimal("17500"))

	def test_takes_no_negative_part(self):
		result = gewerbesteuer(credit("8400", "1000.00"), credit("2110", "300.00"))
		self.assertEqual(result.lines["interest"].declared, ZERO)


class HoldingsTest(TestCase):
	"""Anlage BEG: § 8 Nummer 5 below 15 % at the start of the EZ, § 9 Nummer 2a and 7 from it."""

	def test_adds_back_95_percent_of_the_exempt_dividends_of_a_holding_below_15_percent(self):
		beta = HoldingResult(holding("Beta GmbH", "12"), Decimal("12000.00"))
		result = gewerbesteuer(credit("2625", "12000.00"), kst_inputs={"holdings": (beta,)})
		(line,) = result.beg
		self.assertEqual(
			(line.dividends, line.exempt, line.not_exempt, line.addback),
			(Decimal("12000"), Decimal("12000"), ZERO, Decimal("11400")),
		)
		self.assertIsNone(line.paragraph)
		self.assertEqual(result.lines["dividends_addback"].declared, Decimal("11400"))
		self.assertEqual(result.lines["dividends_cut"].declared, ZERO)

	def test_rounds_the_95_percent_down(self):
		beta = HoldingResult(holding("Beta GmbH", "12"), Decimal("1001.00"))
		result = gewerbesteuer(credit("2625", "1001.00"), kst_inputs={"holdings": (beta,)})
		self.assertEqual(result.beg[0].addback, Decimal("950"))

	def test_a_holding_of_15_percent_adds_back_nothing(self):
		beta = HoldingResult(holding("Beta GmbH", "15"), Decimal("12000.00"))
		result = gewerbesteuer(credit("2625", "12000.00"), kst_inputs={"holdings": (beta,)})
		(line,) = result.beg
		self.assertEqual((line.paragraph, line.addback, line.cut), (1, ZERO, ZERO))

	def test_cuts_the_taxed_dividends_of_a_holding_of_15_percent_less_their_costs(self):
		gamma = HoldingResult(
			holding("Gamma S.A.", "20", foreign=True),
			Decimal("10000.00"),
			financing_costs=Decimal("1000.00"),
			other_costs=Decimal("500.40"),
		)
		result = gewerbesteuer(
			credit("2625", "10000.00"), kst_inputs={"holdings": (gamma,), "trading_book": True}
		)
		(line,) = result.beg
		self.assertEqual(line.paragraph, 2)
		self.assertEqual(
			(line.exempt, line.not_exempt, line.cut_base), (ZERO, Decimal("10000"), Decimal("10000"))
		)
		self.assertEqual(
			(line.financing_costs, line.other_costs, line.cut),
			(Decimal("1000"), Decimal("500"), Decimal("8500")),
		)
		self.assertEqual(result.lines["dividends_cut"].declared, Decimal("8500"))

	def test_streubesitz_below_15_percent_needs_no_anlage_beg(self):
		gamma = HoldingResult(holding("Gamma AG", "1"), Decimal("8000.00"))
		result = gewerbesteuer(credit("2625", "8000.00"), kst_inputs={"holdings": (gamma,)})
		self.assertEqual(result.beg, ())
		self.assertEqual(result.lines["profit"].declared, Decimal("8000"))


class CutsTest(TestCase):
	def test_cuts_the_grundsteuer_booked_as_an_expense(self):
		result = gewerbesteuer(credit("8400", "10000.00"), debit("2375", "800.00"))
		self.assertEqual(result.lines["property_tax"].declared, Decimal("800"))
		self.assertEqual(result.lines["gewerbeertrag_before_loss"].declared, Decimal("8400"))

	def test_cuts_the_zuwendungen_within_20_percent_of_the_profit(self):
		result = gewerbesteuer(credit("8400", "98200.00"), debit("2383", "1000.00"))
		self.assertEqual(result.lines["donations"].declared, Decimal("1000"))
		self.assertEqual(result.lines["donation_cut"].declared, Decimal("1000"))
		self.assertEqual(result.donation_carry_forward, ZERO)

	def test_carries_the_zuwendungen_beyond_the_limit_forward(self):
		result = gewerbesteuer(
			credit("8400", "1000.00"),
			debit("2383", "500.00"),
			donation_carry_forward=Decimal("100"),
			turnover_and_wages=Decimal("10000"),
			kst_inputs={"turnover_and_wages": Decimal("10000")},
		)
		self.assertEqual(result.lines["donation_cut"].declared, Decimal("200"))
		self.assertEqual(result.donation_carry_forward, Decimal("400"))

	def test_the_turnover_cap_counts_when_it_is_higher(self):
		result = gewerbesteuer(
			credit("8400", "1000.00"),
			debit("2383", "500.00"),
			turnover_and_wages=Decimal("100000"),
			kst_inputs={"turnover_and_wages": Decimal("100000")},
		)
		self.assertEqual(result.lines["donation_cut"].declared, Decimal("400"))
		self.assertEqual(result.donation_carry_forward, Decimal("100"))

	def test_takes_the_zuwendungen_and_the_turnover_of_the_koerperschaftsteuer_unless_given(self):
		result = gewerbesteuer(
			credit("8400", "1000.00"),
			debit("2383", "500.00"),
			eligible_donations=Decimal("300.00"),
			kst_inputs={"turnover_and_wages": Decimal("100000")},
		)
		self.assertEqual(result.lines["donations"].declared, Decimal("300"))
		self.assertEqual(result.lines["donation_cut"].declared, Decimal("300"))

	def test_the_gewerbeertrag_before_the_fehlbetraege(self):
		beta = HoldingResult(holding("Beta GmbH", "12"), Decimal("12000.00"))
		result = gewerbesteuer(
			credit("8400", "86200.00"),
			credit("2625", "12000.00"),
			debit("2383", "1000.00"),
			kst_inputs={"holdings": (beta,)},
		)
		self.assertEqual(result.lines["profit"].declared, Decimal("86800"))
		self.assertEqual(result.lines["gewerbeertrag_before_loss"].declared, Decimal("97200"))


class InputTest(TestCase):
	def test_takes_whole_euros_and_cents_where_the_forms_have_them(self):
		with self.assertRaisesRegex(ValueError, "the Fehlbetrag must be whole euros of at least 0"):
			gewerbesteuer(credit("8400", "1.00"), loss_carry_forward=Decimal("0.5"))
		with self.assertRaisesRegex(ValueError, "the Zuwendungsvortrag must be whole euros of at least 0"):
			gewerbesteuer(credit("8400", "1.00"), donation_carry_forward=Decimal("-1"))
		with self.assertRaisesRegex(
			ValueError, "the Umsätze, Löhne und Gehälter must be whole euros of at least 0"
		):
			gewerbesteuer(credit("8400", "1.00"), turnover_and_wages=Decimal("1.5"))
		with self.assertRaisesRegex(ValueError, "the Zuwendungen must be an amount in cents of at least 0"):
			gewerbesteuer(credit("8400", "1.00"), eligible_donations=Decimal("-1.00"))
