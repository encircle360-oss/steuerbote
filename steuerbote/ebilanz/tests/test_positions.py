"""The structure of the E-Bilanz of a GmbH or UG on the mini taxonomy: case, components, positions, marks, the
Mussfelder it sends and those it must not send, and the rows and columns of the Anlagenspiegel."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.ebilanz.positions import (
	AccountingStandard,
	Case,
	CaseError,
	Finding,
	Mark,
	StatementType,
	euro,
	finding_of,
	leitfaden,
	qualified,
	rule,
	structure,
	unqualified,
)
from steuerbote.ebilanz.tests.taxonomy import gaap, gcd, view
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import SettingsError
from steuerbote.xbrl import checks
from steuerbote.xbrl.checks import Severity
from steuerbote.xbrl.facts import Period, Periods

YEAR = Periods(date(2026, 1, 1), date(2026, 12, 31))
OPENING = Periods(date(2026, 3, 1), date(2026, 12, 31), date(2026, 3, 1))
WITH_PRIOR = Periods(date(2026, 1, 1), date(2026, 12, 31), None, date(2025, 1, 1), date(2025, 12, 31))


def case(**fields) -> Case:
	return Case(**{"legal_form": "GmbH", "periods": YEAR, **fields})


def codes(components) -> list[str]:
	return [component.code for component in components]


class CaseTest(TestCase):
	def test_takes_a_gmbh_and_a_ug_with_their_legal_status(self):
		self.assertEqual(case().legal_status, "GMBH")
		self.assertEqual(case(legal_form="UG").legal_status, "UG")
		with self.assertRaises(SettingsError):
			case(legal_form="AG")

	def test_a_jahresabschluss_closes_on_the_last_day_and_an_eroeffnungsbilanz_on_the_first(self):
		"""Rules 170205072 and 170205081 of the Jahresdokumentation 6.9; Leitfaden B.14.3.1.6."""
		case(statement_type=StatementType.EROEFFNUNGSBILANZ, periods=OPENING)
		with self.assertRaises(CaseError):
			case(periods=OPENING)
		with self.assertRaises(CaseError):
			case(statement_type="EB")

	def test_only_the_handelsbilanz_of_a_jahresabschluss_shows_the_previous_year(self):
		"""„Steuerbilanzen dürfen keine Vorjahresangaben ... beinhalten“ (Leitfaden B.8.3)."""
		self.assertTrue(case(accounting_standard="HGBM", periods=WITH_PRIOR).prior)
		self.assertFalse(case().prior)
		for standard in ("HAOE", "AO"):
			with self.subTest(standard=standard), self.assertRaises(CaseError):
				case(accounting_standard=standard, periods=WITH_PRIOR)

	def test_takes_the_values_of_the_gcd_as_texts(self):
		found = case(accounting_standard="AO", statement_type="E")
		self.assertIs(found.accounting_standard, AccountingStandard.STEUERBILANZ)
		self.assertIs(found.statement_type, StatementType.JAHRESABSCHLUSS)
		self.assertTrue(found.steuerbilanz)
		self.assertFalse(case(accounting_standard="HGBM").steuerbilanz)


class ComponentsTest(TestCase):
	def test_a_jahresabschluss_has_bilanz_guv_bvv_anlagenspiegel_and_kontensalden(self):
		"""Leitfaden B.14.3.1.10, rule 170205066, B.14.12.1 and § 5b Abs. 1 Satz 1 EStG."""
		self.assertEqual(codes(case().components), ["B", "GuV", "BVV", "BAL", "KS"])

	def test_an_eroeffnungsbilanz_has_no_guv_and_no_bvv(self):
		"""Rules 170405021, 170205021 and 170405101."""
		self.assertEqual(codes(case(statement_type="EB", periods=OPENING).components), ["B", "BAL", "KS"])

	def test_a_handelsbilanz_adds_the_ueberleitung_and_a_reason_leaves_the_kontensalden_out(self):
		self.assertEqual(
			codes(case(accounting_standard="HGBM").components), ["B", "GuV", "BVV", "BAL", "KS", "STU"]
		)
		self.assertEqual(codes(case(kontennachweis=False).components), ["B", "GuV", "BVV", "BAL"])

	def test_the_facets_are_those_of_the_gcd(self):
		facets = case(legal_form="UG", accounting_standard="HGBM").facets
		self.assertEqual(
			(
				facets.legal_status,
				facets.income_statement_format,
				facets.accounting_standard,
				facets.statement_type,
				facets.report_status,
			),
			("UG", "GKV", "HGBM", "E", "E"),
		)
		self.assertEqual(facets.components, {"B", "GuV", "BVV", "BAL", "KS", "STU"})
		self.assertTrue(facets.final)


class PositionsTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.structure = structure(view(), case())

	def mark(self, name: str) -> Mark:
		return self.structure.position(name).mark

	def test_each_component_has_the_positions_of_its_presentation(self):
		names = [unqualified(position.concept) for position in self.structure.of("GuV")]
		self.assertEqual(
			names,
			[
				"is.netIncome",
				"is.netIncome.netSales",
				"is.netIncome.netSales.statutoryDuties",
				"is.netIncome.netSales.statutoryDuties.membershipFees",
				"is.netIncome.materialServices",
				"is.netIncome.tax",
				"is.netIncome.collItemChangeProfitHbst",
			],
		)
		self.assertEqual(self.structure.position("BVV.profitLoss").component, "BVV")
		self.assertEqual(
			self.structure.position("bs.ass").role,
			"http://www.xbrl.de/taxonomies/de-gaap-ci/role/balanceSheet",
		)

	def test_marks_mussfeld_summenmussfeld_auffang_rechnerisch_notwendig_and_davon(self):
		"""Leitfaden A.10.1, A.10.3 and A.10.4: an Auffangposition is „erkennbar durch die Formulierungen im
		beschreibenden Text „nicht zuordenbar“ oder „ohne Zuordnung““."""
		self.assertIs(self.mark("bs.ass.fixAss.intan.concessionBrands"), Mark.MUSSFELD)
		self.assertIs(self.mark("bs.ass.fixAss.intan"), Mark.SUMMENMUSSFELD)
		self.assertIs(self.mark("bs.ass.fixAss.intan.other"), Mark.AUFFANG)
		self.assertIs(self.mark("bs.ass.currAss.cashEquiv.bank"), Mark.RECHNERISCH_NOTWENDIG)
		self.assertIs(self.mark("bs.eqLiab.liab.bank.upTo1year"), Mark.DAVON)
		self.assertIs(self.mark("bs.ass.deficitNotCoveredByCapital"), Mark.OPTIONAL)
		self.assertTrue(Mark.MUSSFELD.required)
		self.assertFalse(Mark.AUFFANG.required)

	def test_a_mussfeld_required_only_from_a_later_year_has_no_mark(self):
		"""fiscalValidSince 2027 of the Kassenbestand of the mini taxonomy (Leitfaden B.14.4.2)."""
		self.assertIs(self.mark("bs.ass.currAss.cashEquiv.cash"), Mark.OPTIONAL)
		self.assertNotIn(gaap("bs.ass.currAss.cashEquiv.cash"), self.structure.required)

	def test_names_the_sum_each_position_adds_up_to_and_the_position_a_davon_belongs_to(self):
		material = self.structure.position("is.netIncome.materialServices")
		self.assertEqual((material.parent, material.weight), (gaap("is.netIncome"), Decimal(-1)))
		top = self.structure.position("bs.ass")
		self.assertEqual((top.parent, top.weight, top.davon_of), (None, Decimal(1), None))
		davon = self.structure.position("bs.eqLiab.liab.bank.upTo1year")
		self.assertEqual((davon.parent, davon.davon_of), (None, gaap("bs.eqLiab.liab.bank")))
		self.assertEqual(
			self.structure.position("bs.eqLiab.liab.bank.upTo1year.shareholders").davon_of,
			gaap("bs.eqLiab.liab.bank"),
		)
		self.assertTrue(self.structure.position("bs.ass").instant)
		self.assertFalse(self.structure.position("is.netIncome").instant)

	def test_a_davon_with_positions_of_its_own_counts_for_the_position_above_it(self):
		"""The calculation adds the Mitgliedsbeiträge up to the davon position only, as it adds the positions of
		„davon Erträge zur Erfüllung satzungsmäßiger Aufgaben“ in the package 6.9."""
		davon = self.structure.position("is.netIncome.netSales.statutoryDuties")
		self.assertEqual(
			(davon.mark, davon.parent, davon.davon_of), (Mark.DAVON, None, gaap("is.netIncome.netSales"))
		)
		part = self.structure.position("is.netIncome.netSales.statutoryDuties.membershipFees")
		self.assertEqual(
			(part.mark, part.parent, part.davon_of),
			(Mark.DAVON, gaap("is.netIncome.netSales.statutoryDuties"), gaap("is.netIncome.netSales")),
		)
		self.assertIsNone(self.structure.position("is.netIncome.netSales").davon_of)
		self.assertIsNone(self.structure.position("BVV.profitLoss").davon_of)

	def test_leaves_out_what_the_case_does_not_admit(self):
		"""Another legal form (Leitfaden B.4.2), the UKV (B.14.3.1.15), „Einreichung an Finanzverwaltung“ (B.14.6),
		„steuerlich“ in a Steuerbilanz (B.16.2) and a position not valid in the fiscal year (B.14.4.1)."""
		for name in (
			"bs.eqLiab.equity.subscribed.limitedLiablePartners",
			"is.netIncome.costOfSales",
			"bs.ass.consolidationDifference",
			"bs.ass.fixAss.intan.selfmade",
			"bs.ass.fixAss.tan.oldEquipment",
			"bs.ass.currAss.cashEquiv.cryptoAssets",
		):
			with self.subTest(name=name):
				self.assertIsNone(self.structure.position(name))

	def test_keeps_the_positions_of_a_sonderbilanz_which_it_sends_nil(self):
		"""Leitfaden A.10.1 and A.9.3."""
		self.assertIsNotNone(self.structure.position("bs.eqLiab.liab.colEntity"))

	def test_a_handelsbilanz_keeps_what_is_not_permitted_steuerlich(self):
		"""„In einer Handelsbilanz sind sie im Rahmen der Überleitungsrechnung aufzulösen.“ (Leitfaden A.11)"""
		handelsbilanz = structure(view(), case(accounting_standard="HGBM"))
		self.assertIsNotNone(handelsbilanz.position("bs.ass.fixAss.intan.selfmade"))
		self.assertIn(gaap("bs.ass.fixAss.intan.selfmade"), handelsbilanz.rows)

	def test_names_a_position_with_or_without_its_prefix(self):
		self.assertIs(self.structure.position("bs.ass"), self.structure.position(gaap("bs.ass")))
		self.assertIsNone(self.structure.position("bs.ass.unknown"))
		self.assertEqual(self.structure.label("bs.ass"), "Bilanzsumme, Summe Aktiva")
		self.assertEqual(qualified("bs.ass"), gaap("bs.ass"))
		self.assertEqual(qualified(gcd("genInfo")), gcd("genInfo"))
		self.assertEqual(leitfaden(view(), "B.14.2"), "Technischer Leitfaden zur HGB-Taxonomie 6.9, B.14.2")
		self.assertEqual(
			rule(view(), "170205010"), "Jahresdokumentation_Bilanz_Taxonomie_6_9.ods, Regel 170205010"
		)
		self.assertEqual(euro(Decimal("-1234567.5")), "-1.234.567,50 €")


class MussfelderTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.structure = structure(view(), case())

	def test_sends_the_mussfelder_of_the_gcd_and_the_components(self):
		"""steuerbote.xbrl.checks.required() for the facets of the case (Leitfaden B.14.2)."""
		self.assertEqual(
			self.structure.required,
			checks.required(view(), case().facets, YEAR),
		)
		self.assertIn(gcd("genInfo.report.id.reportStatus"), self.structure.required)
		self.assertIn(gaap("BVV.profitLoss.contribution"), self.structure.required)

	def test_counts_the_mussfelder_and_summenmussfelder_of_each_component(self):
		counts = {
			component: (
				len(self.structure.mussfelder(component)),
				len(self.structure.mussfelder(component, Mark.SUMMENMUSSFELD)),
			)
			for component in ("B", "GuV", "BVV")
		}
		self.assertEqual(counts, {"B": (10, 11), "GuV": (3, 1), "BVV": (5, 2)})

	def test_refuses_the_mussfelder_of_another_legal_form_or_format(self):
		"""„Alle unzulässigen Mussfelder sind nicht, auch nicht mit NIL-Wert, zu übermitteln.“ (FAQ zur E-Bilanz,
		Version 2026-01, Tz. 4 a)"""
		self.assertEqual(
			self.structure.refused,
			(
				gaap("bs.eqLiab.equity.subscribed.limitedLiablePartners"),
				gaap("is.netIncome.costOfSales"),
				gaap("BVV.profitLoss.EStG6b"),
			),
		)
		for name in self.structure.refused:
			with self.subTest(name=name):
				self.assertNotIn(name, self.structure.required)

	def test_an_eroeffnungsbilanz_has_the_mussfelder_of_its_bilanz_only(self):
		opening = structure(view(), case(statement_type="EB", periods=OPENING))
		self.assertEqual(opening.of("GuV"), ())
		self.assertEqual(opening.announced, {"B", "BAL", "KS"})
		self.assertNotIn(gaap("is.netIncome"), opening.required)
		self.assertIn(gaap("bs.ass"), opening.required)


class AnlagenspiegelTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.structure = structure(view(), case())

	def test_its_rows_are_the_positions_of_the_anlagevermoegen_the_case_admits(self):
		"""Leitfaden B.14.12.1 j; the selbst geschaffene Schutzrechte are „steuerlich“ not permitted."""
		self.assertEqual(
			self.structure.rows,
			tuple(
				gaap(name)
				for name in (
					"bs.ass.fixAss",
					"bs.ass.fixAss.intan",
					"bs.ass.fixAss.intan.concessionBrands",
					"bs.ass.fixAss.tan",
				)
			),
		)

	def test_its_columns_are_the_value_development_with_marks_and_sums(self):
		columns = {unqualified(column.concept): column for column in self.structure.columns}
		self.assertEqual(len(columns), 20)
		self.assertEqual(
			[name for name, column in columns.items() if column.mark is Mark.MUSSFELD],
			[
				"grossCost.beginning",
				"gross.addition",
				"gross.movements",
				"accDepr.beginning",
				"accDepr.DeprPeriod.regular",
				"accDepr.DeprPeriod.extraordinary",
				"accDepr.DeprPeriod.impairment",
				"accDepr.DeprPeriod.EStG7g_2",
				"accDepr.DeprPeriod.EStG6b_3",
				"accDepr.addition",
				"accDepr.release",
				"accDepr.movements",
				"revaluation",
			],
		)
		self.assertEqual(
			[name for name, column in columns.items() if column.mark is Mark.SUMMENMUSSFELD],
			["all", "gross", "accDepr", "accDepr.DeprPeriod"],
		)
		self.assertIs(columns["accDepr.DeprPeriod.misc"].mark, Mark.AUFFANG)
		self.assertEqual((columns["accDepr"].parent, columns["accDepr"].weight), (gaap("all"), Decimal(-1)))
		self.assertEqual((columns["all"].parent, columns["all_Prev_period"].mark), (None, Mark.OPTIONAL))
		self.assertIs(self.structure.column("gross"), columns["gross"])
		self.assertIsNone(self.structure.column("bs.ass"))


class FindingTest(TestCase):
	def test_an_error_blocks_and_a_hint_does_not(self):
		self.assertTrue(Finding("EB-X", "Text.", "Quelle").blocking)
		self.assertFalse(Finding("EB-X", "Text.", "Quelle", severity=Severity.HINT).blocking)

	def test_takes_a_finding_of_the_checks_of_xbrl_with_its_code_and_what_it_is_about(self):
		found = checks.Finding(
			checks.Code.SUMMENMUSSFELD,
			"Text.",
			"Leitfaden",
			gaap("all"),
			Period.WIRTSCHAFTSJAHR,
			(
				(gaap("dim_changes.nt.ass.gross"), gaap("bs.ass.fixAss")),
				(gaap("dim_taxTrans"), gaap("dim_taxBal")),
			),
			Severity.HINT,
		)
		self.assertEqual(
			finding_of(found),
			Finding(
				"XBRL-SUMMENMUSSFELD",
				"Text.",
				"Leitfaden",
				"all wirtschaftsjahr bs.ass.fixAss dim_taxBal",
				Severity.HINT,
			),
		)
		self.assertEqual(finding_of(checks.Finding(checks.Code.CONTEXT, "Text.", "Leitfaden")).reference, "")
