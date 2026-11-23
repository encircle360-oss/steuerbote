"""The E-Bilanz against the HGB-Taxonomie 6.9 of esteuer.de and the examples of the ERiC documentation 44.3.6.0.

The package and the documentation are not part of the repository (steuerbote/xbrl/tests/real.py,
steuerbote/elster/tests/eric_schema.py): without them these tests are skipped, except in a CI. The invented GmbH is
that of the tests on the mini taxonomy, its accounts mapped to the positions of the package.
"""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from lxml import etree

from steuerbote.ebilanz.anlagenspiegel import Row, ValueType
from steuerbote.ebilanz.calculation import AccountBalance, EquityChanges
from steuerbote.ebilanz.gcd import facts
from steuerbote.ebilanz.instance import Sources, build
from steuerbote.ebilanz.positions import Case, Mark, structure
from steuerbote.ebilanz.tests.test_gcd import MASTER
from steuerbote.ebilanz.ueberleitung import Kind, Transfer
from steuerbote.elster.tests.eric_schema import bilanz_example
from steuerbote.xbrl.facts import Periods, Tuple
from steuerbote.xbrl.tests import real

D = Decimal
YEAR = Periods(date(2026, 1, 1), date(2026, 12, 31))
OPENING = Periods(date(2026, 3, 1), date(2026, 12, 31), date(2026, 3, 1))
OUTPUT = "is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput"
GCD_NAMESPACE = "http://www.xbrl.de/taxonomies/de-gcd-2025-04-01"
XBRL = "{http://www.xbrl.org/2003/instance}xbrl"
BOOKS = (
	AccountBalance("0135", "EDV-Software", "bs.ass.fixAss.intan.concessionBrands", D("12000.00")),
	AccountBalance(
		"0215", "Unbebaute Grundstücke", "bs.ass.fixAss.tan.landBuildings.landWithoutBuildings", D("30000.00")
	),
	AccountBalance("1800", "Bank", "bs.ass.currAss.cashEquiv.bank", D("68500.00")),
	AccountBalance("2900", "Gezeichnetes Kapital", "bs.eqLiab.equity.subscribed.corp", D("-25000.00")),
	AccountBalance(
		"2970", "Gewinnvortrag vor Verwendung", "bs.eqLiab.equity.retainedEarnings", D("-2500.00")
	),
	AccountBalance(
		"3150", "Verbindlichkeiten gegenüber Kreditinstituten", "bs.eqLiab.liab.bank.other", D("-40000.00")
	),
	AccountBalance("3070", "Sonstige Rückstellungen", "bs.eqLiab.accruals.other", D("-3000.00")),
	AccountBalance(
		"4400", "Erlöse 19 % USt", f"{OUTPUT}.netSales.grossSales.generalRateVAT", D("-120000.00")
	),
	AccountBalance(
		"4700",
		"Erlösschmälerungen",
		f"{OUTPUT}.netSales.reductionsFromGrossSales.generalRateVAT",
		D("1000.00"),
	),
	AccountBalance(
		"5400",
		"Wareneingang 19 % Vorsteuer",
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.generalRateVAT",
		D("70000.00"),
	),
	AccountBalance("7600", "Körperschaftsteuer", "is.netIncome.tax.kst", D("9000.00")),
)
SOFTWARE = {
	"cost_begin": D("15000.00"),
	"additions": D("3000.00"),
	"depreciation_begin": D("4000.00"),
	"depreciation_regular": D("2000.00"),
	"source": "Software",
}
ASSETS = (
	Row("bs.ass.fixAss.intan.concessionBrands", **SOFTWARE),
	Row(
		"bs.ass.fixAss.tan.landBuildings.landWithoutBuildings", cost_begin=D("30000.00"), source="Grundstücke"
	),
)
EQUITY = EquityChanges(previous_equity=D("27500.00"))
HANDELSBILANZ = (
	*BOOKS,
	AccountBalance("0144", "Selbst geschaffene Software", "bs.ass.fixAss.intan.selfmade", D("5000.00")),
	AccountBalance("4820", "Andere aktivierte Eigenleistungen", f"{OUTPUT}.ownWork", D("-5000.00")),
)
TRANSFERS = (
	Transfer(
		Kind.WERTAENDERUNG,
		"bs.ass.fixAss.intan.selfmade",
		D("-5000.00"),
		reason="Aktivierungsverbot § 5 Abs. 2 EStG",
	),
	Transfer(
		Kind.WERTAENDERUNG, f"{OUTPUT}.ownWork", D("-5000.00"), reason="Aktivierungsverbot § 5 Abs. 2 EStG"
	),
	Transfer(
		Kind.WERTAENDERUNG,
		"bs.eqLiab.accruals.other",
		D("-1000.00"),
		reason="Drohverlustrückstellung, § 5 Abs. 4a EStG",
	),
)
HB, UE = ValueType.HANDELSBILANZ, ValueType.UEBERLEITUNG
OPENING_BOOKS = (
	AccountBalance("1800", "Bank", "bs.ass.currAss.cashEquiv.bank", D("25000.00")),
	AccountBalance("2900", "Gezeichnetes Kapital", "bs.eqLiab.equity.subscribed.corp", D("-25000.00")),
)
HANDELSBILANZ_ASSETS = (
	Row("bs.ass.fixAss.intan.concessionBrands", HB, **SOFTWARE),
	Row("bs.ass.fixAss.intan.selfmade", HB, additions=D("5000.00"), source="Entwicklung"),
	Row("bs.ass.fixAss.intan.selfmade", UE, additions=D("-5000.00"), source="Entwicklung"),
	Row(
		"bs.ass.fixAss.tan.landBuildings.landWithoutBuildings",
		HB,
		cost_begin=D("30000.00"),
		source="Grundstücke",
	),
)


class StructureTest(TestCase):
	"""The Mussfelder of a GmbH with the Gesamtkostenverfahren in 2026, as the research note on the E-Bilanz counts them
	(2.5) and the build contract of stage 3 binds them (3.2)."""

	@classmethod
	def setUpClass(cls):
		cls.structure = structure(real.view(), Case("GmbH", YEAR))

	def test_bilanz_guv_and_betriebsvermoegensvergleich(self):
		for component, expected in (("B", (82, 49)), ("GuV", (155, 59)), ("BVV", (5, 2))):
			with self.subTest(component=component):
				self.assertEqual(
					(
						len(self.structure.mussfelder(component)),
						len(self.structure.mussfelder(component, Mark.SUMMENMUSSFELD)),
					),
					expected,
				)

	def test_the_gcd(self):
		self.assertEqual(len([name for name in self.structure.required if name.startswith("de-gcd:")]), 52)

	def test_the_anlagenspiegel_per_row(self):
		marks = [column.mark for column in self.structure.columns]
		self.assertEqual((marks.count(Mark.MUSSFELD), marks.count(Mark.SUMMENMUSSFELD)), (13, 4))
		self.assertEqual(self.structure.rows[0], "de-gaap-ci:bs.ass.fixAss")

	def test_a_ug_has_the_mussfelder_of_a_gmbh(self):
		ug = structure(real.view(), Case("UG", YEAR))
		self.assertEqual(ug.required, self.structure.required)
		self.assertEqual(ug.refused, self.structure.refused)

	def test_refuses_the_mussfelder_of_partnerships(self):
		"""FAQ zur E-Bilanz, Version 2026-01, Tz. 4 a: not sent, not even NIL."""
		self.assertIn("de-gaap-ci:bs.ass.currAss.receiv.unpaidCapitalPartners", self.structure.refused)
		self.assertFalse(set(self.structure.refused) & set(self.structure.required))


class InventedGmbHTest(TestCase):
	"""The E-Bilanz of the invented GmbH, as an Einheitsbilanz, a Handelsbilanz with its Überleitung, an
	Eröffnungsbilanz and as a UG, passes every check of the profile FISCAL on the package."""

	def assert_ready(self, ebilanz):
		self.assertEqual([(finding.code, finding.reference) for finding in ebilanz.findings], [])
		self.assertTrue(ebilanz.ready)
		self.assertTrue(ebilanz.xml().startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))

	def test_an_einheitsbilanz(self):
		self.assert_ready(
			build(
				structure(real.view(), Case("GmbH", YEAR)),
				MASTER,
				Sources(BOOKS, assets=ASSETS, equity=EQUITY),
			)
		)

	def test_a_handelsbilanz_with_its_ueberleitung(self):
		self.assert_ready(
			build(
				structure(real.view(), Case("GmbH", YEAR, accounting_standard="HGBM")),
				MASTER,
				Sources(HANDELSBILANZ, assets=HANDELSBILANZ_ASSETS, transfers=TRANSFERS, equity=EQUITY),
			)
		)

	def test_an_eroeffnungsbilanz(self):
		self.assert_ready(
			build(
				structure(real.view(), Case("GmbH", OPENING, statement_type="EB")),
				MASTER,
				Sources(OPENING_BOOKS, first_year=True),
			)
		)

	def test_an_ug(self):
		self.assert_ready(
			build(
				structure(real.view(), Case("UG", YEAR)), MASTER, Sources(BOOKS, assets=ASSETS, equity=EQUITY)
			)
		)


class GcdExampleTest(TestCase):
	"""The GCD against that of the GmbH example of the ERiC documentation, HandelsbilanzLandwirt_GmbH.xml, a
	Handelsbilanz of a fiscal year from 1 July 2025 with the previous year, without Kontensalden. The example is one of
	agriculture, „Branchen“ LuF on its Branchentaxonomie, where Steuerbote reports the Kerntaxonomie."""

	@classmethod
	def setUpClass(cls):
		instance = etree.fromstring(bilanz_example("6.9")).find(f".//{XBRL}")
		cls.example = {
			f"de-gcd:{etree.QName(element).localname}"
			for element in instance.iter()
			if isinstance(element.tag, str) and etree.QName(element).namespace == GCD_NAMESPACE
		}
		case = Case(
			"GmbH",
			Periods(date(2025, 7, 1), date(2026, 6, 30), None, date(2023, 7, 1), date(2025, 6, 30)),
			accounting_standard="HGBM",
			kontennachweis=False,
		)
		cls.structure = structure(real.view(), case)
		cls.ours = set()
		for fact in facts(cls.structure, MASTER, reason="NoKS"):
			cls._collect(fact)

	@classmethod
	def _collect(cls, fact):
		cls.ours.add(fact.concept)
		if isinstance(fact, Tuple):
			for child in fact.children:
				cls._collect(child)

	def test_reports_nothing_the_example_does_not_but_the_kerntaxonomie(self):
		self.assertEqual(
			sorted(self.ours - self.example), ["de-gcd:genInfo.report.id.specialAccountingStandard.K"]
		)

	def test_the_example_reports_every_mussfeld_of_the_gcd_of_a_gmbh(self):
		required = {name for name in self.structure.required if name.startswith("de-gcd:")}
		self.assertEqual(sorted(required - self.example), [])
		self.assertEqual(sorted(required - self.ours), [])
