"""The E-Bilanz of the invented GmbH on the mini taxonomy: its parts from the sources, the report the checks of the
profile FISCAL pass, the instance against its golden file, and the findings that hold it back."""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from steuerbote.ebilanz.anlagenspiegel import Row, ValueType
from steuerbote.ebilanz.calculation import BALANCE_SHEET_NET_INCOME, BVV_RESULT, AccountBalance, EquityChanges
from steuerbote.ebilanz.instance import EBilanzError, Sources, build
from steuerbote.ebilanz.kontennachweis import ACCOUNT_BALANCES, NOT_POSSIBLE, NOT_YET_POSSIBLE, POSITION_NAME
from steuerbote.ebilanz.positions import Finding, structure
from steuerbote.ebilanz.tests.taxonomy import gaap, view, view_6_10
from steuerbote.ebilanz.tests.test_anlagenspiegel import LAND, SOFTWARE
from steuerbote.ebilanz.tests.test_calculation import BOOKS, case
from steuerbote.ebilanz.tests.test_gcd import MASTER, OPENING
from steuerbote.ebilanz.tests.test_ueberleitung import ACCRUAL, HANDELSBILANZ, SALES
from steuerbote.ebilanz.tests.test_ueberleitung import SOFTWARE as SELFMADE
from steuerbote.ebilanz.ueberleitung import TRANSFER
from steuerbote.jahresmeldung.findings import DATA_LENGTH
from steuerbote.jahresmeldung.findings import Severity as AnnualSeverity
from steuerbote.xbrl.checks import Severity
from steuerbote.xbrl.facts import Item

D = Decimal
FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "ebilanz-gmbh-2026.xml"
HB, UE = ValueType.HANDELSBILANZ, ValueType.UEBERLEITUNG
# The Betriebsvermögen at the end of 2025: the Stammkapital and the Gewinnvortrag.
EQUITY = EquityChanges(previous_equity=D("27500.00"))
SOURCES = Sources(BOOKS, assets=(SOFTWARE, LAND), equity=EQUITY)
OPENING_BOOKS = (
	AccountBalance("1800", "Bank", "bs.ass.currAss.cashEquiv.bank", D("25000.00")),
	AccountBalance("2900", "Gezeichnetes Kapital", "bs.eqLiab.equity.subscribed.corp", D("-25000.00")),
)


def built(master=MASTER, sources=SOURCES, **fields):
	return build(structure(view(), case(**fields)), master, sources)


def codes(ebilanz) -> list[str]:
	return [finding.code for finding in ebilanz.findings]


def concepts(ebilanz) -> list[str]:
	return [fact.concept for fact in ebilanz.report.facts]


class EinheitsbilanzTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.ebilanz = built()

	def test_is_ready_without_a_finding(self):
		self.assertEqual(self.ebilanz.findings, ())
		self.assertEqual(self.ebilanz.blocking, ())
		self.assertTrue(self.ebilanz.ready)

	def test_keeps_its_parts(self):
		ebilanz = self.ebilanz
		self.assertEqual(ebilanz.calculation.amount("bs.ass"), D("110500.00"))
		self.assertEqual(ebilanz.ueberleitung.groups, ())
		self.assertEqual(ebilanz.betriebsvermoegensvergleich.amounts[BVV_RESULT], D("40000.00"))
		self.assertEqual(len(ebilanz.anlagenspiegel.lines), 4)
		self.assertEqual(len(ebilanz.kontennachweis.lines), len(BOOKS))
		self.assertEqual(ebilanz.master, MASTER)

	def test_reports_the_gcd_first_and_then_the_components(self):
		"""The order of the examples of the ERiC documentation: the GCD, then the GAAP module."""
		facts = self.ebilanz.report.facts
		names = [fact.concept for fact in facts]
		first_gaap = next(index for index, name in enumerate(names) if name.startswith("de-gaap-ci:"))
		self.assertTrue(all(name.startswith("de-gcd:") for name in names[:first_gaap]))
		self.assertTrue(all(name.startswith("de-gaap-ci:") for name in names[first_gaap:]))
		positions = [
			names.index(gaap("bs.ass")),
			names.index(gaap("is.netIncome")),
			names.index(gaap("BVV.profitLoss")),
			next(index for index, fact in enumerate(facts) if isinstance(fact, Item) and fact.dimensions),
			names.index(gaap("detailedInformation.accountBalances")),
		]
		self.assertEqual(positions, sorted(positions))
		self.assertNotIn(TRANSFER, names)

	def test_writes_the_instance_of_its_golden_file(self):
		self.assertEqual(self.ebilanz.xml(), GOLDEN.read_bytes())

	def test_gives_the_instance_for_the_nutzdaten(self):
		self.assertEqual(self.ebilanz.instance().tag, "{http://www.xbrl.org/2003/instance}xbrl")


class HandelsbilanzTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.ebilanz = built(
			sources=Sources(
				HANDELSBILANZ,
				assets=(
					Row(
						"bs.ass.fixAss.intan.concessionBrands",
						HB,
						cost_begin=D("15000.00"),
						additions=D("3000.00"),
						depreciation_begin=D("4000.00"),
						depreciation_regular=D("2000.00"),
						source="Software",
					),
					Row("bs.ass.fixAss.intan.selfmade", HB, additions=D("5000.00"), source="Entwicklung"),
					Row("bs.ass.fixAss.intan.selfmade", UE, additions=D("-5000.00"), source="Entwicklung"),
					Row("bs.ass.fixAss.tan", HB, cost_begin=D("30000.00"), source="Grundstücke"),
				),
				transfers=(SELFMADE, SALES, ACCRUAL),
				equity=EQUITY,
			),
			accounting_standard="HGBM",
		)

	def test_is_ready_with_its_ueberleitung(self):
		"""Leitfaden A.11, B.15.1; rule 170205100."""
		self.assertEqual(self.ebilanz.findings, ())
		self.assertIn(TRANSFER, concepts(self.ebilanz))

	def test_compares_the_betriebsvermoegen_of_the_steuerbilanz(self):
		"""Leitfaden B.14.3.2.12: „dabei sind jeweils die Steuerbilanzwerte oder übergeleiteten Werte maßgebend“. The
		Steuerbilanz has 4.000 € less equity than the Handelsbilanz and a result of 41.000 €."""
		amounts = self.ebilanz.betriebsvermoegensvergleich.amounts
		self.assertEqual(amounts[gaap("BVV.profitLoss.assetsCurrentYear")], D("68500.00"))
		self.assertEqual(amounts[BVV_RESULT], D("41000.00"))
		self.assertEqual(self.ebilanz.calculation.amount("is.netIncome"), D("45000.00"))


class EroeffnungsbilanzTest(TestCase):
	def test_reports_the_bilanz_and_the_anlagenspiegel_without_guv_and_betriebsvermoegensvergleich(self):
		"""Leitfaden B.14.3.1.10; the Anlagenspiegel without assets has the Anlagevermögen at zero."""
		ebilanz = built(sources=Sources(OPENING_BOOKS, first_year=True), statement_type="EB", periods=OPENING)
		self.assertEqual(ebilanz.findings, ())
		names = concepts(ebilanz)
		self.assertIn(gaap("bs.ass"), names)
		self.assertNotIn(gaap("is.netIncome"), names)
		self.assertFalse(any(name.startswith(gaap("BVV")) for name in names))
		(line,) = ebilanz.anlagenspiegel.lines
		self.assertEqual(line.book_value, D("0"))


class FindingsTest(TestCase):
	def test_without_a_steuernummer_there_is_no_instance(self):
		ebilanz = built(replace(MASTER, steuernummer=None))
		self.assertIsNone(ebilanz.report)
		self.assertEqual(codes(ebilanz), ["170205025"])
		self.assertFalse(ebilanz.ready)
		with self.assertRaisesRegex(EBilanzError, "170205025"):
			ebilanz.xml()
		with self.assertRaises(EBilanzError):
			ebilanz.instance()

	def test_holds_the_findings_of_its_parts(self):
		ebilanz = built(
			sources=Sources(
				(*BOOKS, AccountBalance("1590", "Durchlaufende Posten", None, D("0.01"))),
				assets=(SOFTWARE, LAND),
			)
		)
		self.assertIn("EB-NICHT-ZUGEORDNET", codes(ebilanz))
		self.assertIn("170405109", codes(ebilanz))
		self.assertFalse(ebilanz.ready)
		self.assertTrue(all(finding.blocking for finding in ebilanz.blocking))

	def test_holds_the_findings_of_the_checks_of_the_profile(self):
		"""Leitfaden B.9.2: an announced component has a valued fact, which an E-Bilanz without balances lacks."""
		ebilanz = built(sources=Sources(()))
		profile = [finding for finding in ebilanz.findings if finding.code == "XBRL-BERICHTSBESTANDTEIL"]
		self.assertEqual(
			[finding.reference for finding in profile],
			[f"de-gcd:genInfo.report.id.reportElement.reportElements.{code}" for code in ("B", "GuV", "KS")],
		)
		self.assertIsNotNone(ebilanz.report)
		self.assertFalse(ebilanz.ready)

	def test_an_instance_the_writer_refuses_is_a_finding(self):
		ebilanz = built(replace(MASTER, name="Rad \N{SNOWMAN} GmbH"))
		self.assertEqual(codes(ebilanz), ["EB-GCD-ZEICHEN", "EB-INSTANZ"])
		self.assertIn("U+2603", ebilanz.findings[-1].text)
		self.assertIsNone(ebilanz.report)

	def test_gives_its_findings_to_the_table_of_the_annual_document(self):
		ebilanz = replace(
			built(),
			findings=(
				Finding("170205010", "Aktiva und Passiva weichen ab.", "Leitfaden B.14.3.2.2", "bs.ass"),
				Finding("EB-LANG", "Lang.", "Quelle", "x" * 200, Severity.HINT),
			),
		)
		first, second = ebilanz.annual_findings()
		self.assertEqual(
			(first.code, first.severity, first.text, first.reference),
			(
				"170205010",
				AnnualSeverity.ERROR,
				"Aktiva und Passiva weichen ab. (Quelle: Leitfaden B.14.3.2.2)",
				"bs.ass",
			),
		)
		self.assertEqual(second.severity, AnnualSeverity.HINT)
		self.assertEqual(len(second.reference), DATA_LENGTH)
		self.assertTrue(second.reference.endswith("…"))


class SourcesTest(TestCase):
	def test_takes_any_iterable(self):
		sources = Sources(iter(BOOKS), adjustments=[], assets=iter((LAND,)), transfers=())
		self.assertEqual(sources.balances, BOOKS)
		self.assertEqual(sources.assets, (LAND,))
		self.assertEqual(sources.equity, EquityChanges())
		self.assertEqual(sources.reason, "")
		self.assertIsInstance(sources.adjustments, tuple)


class Taxonomy610Test(TestCase):
	"""The E-Bilanz of the invented GmbH on the mini taxonomy 6.10, whose Kontensalden the checks of the profile
	FISCAL take by the structural errors 170195106 to 170195110 (steuerbote/xbrl/checks.py)."""

	@classmethod
	def setUpClass(cls):
		cls.ebilanz = build(structure(view_6_10(), case()), MASTER, SOURCES)

	def test_is_ready_without_a_finding(self):
		self.assertEqual(self.ebilanz.findings, ())
		self.assertTrue(self.ebilanz.ready)

	def test_reports_the_jahresueberschuss_of_the_bilanz_without_an_account(self):
		tuples = [fact for fact in self.ebilanz.report.facts if fact.concept == ACCOUNT_BALANCES]
		self.assertEqual(len(tuples), len(BOOKS) + 1)
		self.assertEqual(
			[(item.concept, item.value) for item in tuples[-1].children][::4],
			[(POSITION_NAME, BALANCE_SHEET_NET_INCOME), (NOT_POSSIBLE, True)],
		)
		self.assertNotIn(NOT_YET_POSSIBLE, concepts(self.ebilanz))

	def test_170195106_names_a_position_left_without_a_kontensaldo(self):
		ebilanz = build(
			structure(view_6_10(), case()),
			MASTER,
			replace(
				SOURCES,
				balances=(
					*BOOKS[:-1],
					AccountBalance("7600", "Podatek łączny", "is.netIncome.tax", D("9000.00")),
				),
			),
		)
		self.assertEqual(codes(ebilanz), ["EB-KONTENSALDEN", "170195106"])
		self.assertEqual(ebilanz.findings[-1].reference, "is.netIncome.tax")
		self.assertFalse(ebilanz.ready)
