"""The checks of a report, against the mini taxonomy (steuerbote/xbrl/tests/mini.py).

The report of these tests is the E-Bilanz of an invented GmbH for 2026 with the Gesamtkostenverfahren, which announces
Bilanz, GuV and Betriebsvermögensvergleich and adds up: Aktiva of 100 €, a Jahresüberschuss of 45 €. The Offenlegung of
the same GmbH as a Kleinstkapitalgesellschaft shows the letters of its Bilanz for 2026 and 2025.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase

from lxml import etree

from steuerbote.xbrl import checks, writer
from steuerbote.xbrl.checks import BILANZ, COMPONENTS, Code, Facets, Severity
from steuerbote.xbrl.facts import (
	Entity,
	Fact,
	Item,
	Period,
	Periods,
	Report,
	Tuple,
	amount,
	choice,
	nil,
)
from steuerbote.xbrl.taxonomy import BALANCE_SHEET, LegalForm, View
from steuerbote.xbrl.tests import mini

WJ = Period.WIRTSCHAFTSJAHR
ST = Period.STICHTAG
G = "de-gcd:genInfo."
A = "de-gaap-ci:"
ELEMENTS = f"{G}report.id.reportElement"
PERIODS = Periods(date(2026, 1, 1), date(2026, 12, 31))
PRIOR = Periods(
	date(2026, 1, 1),
	date(2026, 12, 31),
	prior_fiscal_year_begin=date(2025, 1, 1),
	prior_fiscal_year_end=date(2025, 12, 31),
)
# Invented: a Steuernummer of the test Finanzamt 9198 of the ERiC documentation.
ENTITY = Entity.steuernummer("9198011310010")
TAX_BALANCE = (f"{A}dim_taxTrans", f"{A}dim_taxBal")


def element(code: str) -> str:
	return f"{ELEMENTS}.reportElements.{code}"


def gcd(
	*,
	elements: tuple[str, ...] = ("B", "GuV", "BVV"),
	status: str = "E",
	statement: str = "E",
	standard: str = "HAOE",
	income: str = "GKV",
	legal: str = "GMBH",
) -> tuple[Fact, ...]:
	"""The GCD of the report: its Mussfelder, the shareholder NIL, as the GmbH example of the ERiC documentation
	44.3.6.0 (HandelsbilanzLandwirt_GmbH.xml) sends them."""
	mussfelder = ("B", "GuV", "BVV", "BAL", "KS", "STU", "EB")
	return (
		choice(f"{G}report.id.reportStatus", f"{G}report.id.reportStatus.reportStatus.{status}"),
		choice(
			ELEMENTS,
			*(element(code) for code in elements),
			unreported=tuple(element(code) for code in mussfelder if code not in elements),
		),
		choice(f"{G}report.id.statementType", f"{G}report.id.statementType.statementType.{statement}"),
		choice(
			f"{G}report.id.accountingStandard",
			f"{G}report.id.accountingStandard.accountingStandard.{standard}",
		),
		choice(
			f"{G}report.id.incomeStatementFormat",
			f"{G}report.id.incomeStatementFormat.incomeStatementFormat.{income}",
		),
		Item(f"{G}report.period.fiscalYearBegin", WJ, date(2026, 1, 1)),
		Item(f"{G}report.period.fiscalYearEnd", WJ, date(2026, 12, 31)),
		Item(f"{G}report.period.balSheetClosingDate", WJ, date(2026, 12, 31)),
		Item(f"{G}company.id.name", WJ, "Beispiel GmbH"),
		Item(f"{G}company.id.location.houseNo", WJ, "1"),
		choice(f"{G}company.id.legalStatus", f"{G}company.id.legalStatus.legalStatus.{legal}"),
		Tuple(f"{G}company.id.idNo", (Item(f"{G}company.id.idNo.type.companyId.ST13", WJ, "9198011310010"),)),
		Tuple(f"{G}company.id.shareholder", (nil(f"{G}company.id.shareholder.name", WJ),)),
	)


def euros(concept: str, value: str, period: Period = ST, dimensions=()) -> Item:
	return amount(f"{A}{concept}", period, Decimal(value), dimensions)


BILANZ_FACTS = (
	euros("bs.ass", "100"),
	euros("bs.ass.fixAss", "60"),
	euros("bs.ass.fixAss.intan", "20"),
	euros("bs.ass.fixAss.intan.concessionBrands", "20"),
	euros("bs.ass.fixAss.tan", "40"),
	euros("bs.ass.currAss", "40"),
	euros("bs.ass.currAss.cashEquiv", "40"),
	euros("bs.ass.currAss.cashEquiv.bank", "40"),
	euros("bs.eqLiab", "100"),
	euros("bs.eqLiab.equity", "70"),
	euros("bs.eqLiab.equity.subscribed", "25"),
	euros("bs.eqLiab.equity.subscribed.corp", "25"),
	euros("bs.eqLiab.equity.netIncome", "45"),
	nil(f"{A}bs.eqLiab.equity.netIncome.taxBalanceGenerally", ST),
	euros("bs.eqLiab.liab", "30"),
	euros("bs.eqLiab.liab.bank", "30"),
)
GUV_FACTS = (
	euros("is.netIncome", "45", WJ),
	euros("is.netIncome.netSales", "100", WJ),
	euros("is.netIncome.materialServices", "40", WJ),
	euros("is.netIncome.tax", "15", WJ),
)
BVV_FACTS = (
	euros("BVV.profitLoss", "45", WJ),
	euros("BVV.profitLoss.assetsCurrentYear", "70", WJ),
	euros("BVV.profitLoss.assetsPreviousYear", "25", WJ),
)


def report(*facts: Fact, periods: Periods = PERIODS) -> Report:
	return Report(ENTITY, periods, writer.entry_points(mini.view()), facts)


def complete(*facts: Fact, periods: Periods = PERIODS, **values) -> Report:
	"""The report of the GmbH with further facts."""
	return report(*gcd(**values), *BILANZ_FACTS, *GUV_FACTS, *BVV_FACTS, *facts, periods=periods)


def without(report_: Report, *concepts: str) -> Report:
	"""The report without the top level facts of the concepts."""
	return replace(report_, facts=tuple(fact for fact in report_.facts if fact.concept not in concepts))


def replaced(report_: Report, *facts: Item) -> Report:
	"""The report with the facts in place of those of their concept and period."""
	keys = {(fact.concept, fact.period) for fact in facts}
	kept = tuple(
		fact
		for fact in report_.facts
		if not isinstance(fact, Item) or (fact.concept, fact.period) not in keys
	)
	return replace(report_, facts=(*kept, *facts))


def codes(findings) -> list[tuple[Code, str]]:
	return [(finding.code, finding.concept) for finding in findings]


class CompleteReportTest(TestCase):
	def test_the_report_of_the_gmbh_passes_every_check(self):
		report_ = complete()
		facets = Facets.of(report_)
		taxonomy = mini.view()
		self.assertEqual(checks.components(report_, taxonomy, facets), ())
		self.assertEqual(checks.mussfelder(report_, taxonomy, facets), ())
		self.assertEqual(checks.admissibility(report_, taxonomy, facets), ())
		self.assertEqual(checks.prior_year(report_, taxonomy, facets), ())
		self.assertEqual(checks.calculation(report_, taxonomy), ())
		self.assertEqual(checks.oberpositionen(report_, taxonomy), ())
		self.assertEqual(checks.summenmussfelder(report_, taxonomy), ())
		self.assertEqual(checks.contexts(writer.instance(report_, taxonomy)), ())


class FindingTest(TestCase):
	def test_a_finding_is_an_error_in_german_with_its_source(self):
		(finding,) = checks.mussfelder(
			without(complete(), f"{A}bs.ass.fixAss.tan"), mini.view(), Facets.of(complete())
		)
		self.assertEqual(finding.code, Code.MUSSFELD)
		self.assertEqual(finding.code.value, "XBRL-MUSSFELD")
		self.assertIs(finding.severity, Severity.ERROR)
		self.assertEqual(finding.severity.value, "Fehler")
		self.assertTrue(finding.blocking)
		self.assertEqual(finding.concept, f"{A}bs.ass.fixAss.tan")
		self.assertIn("„Sachanlagen (steuerlich)“", finding.text)
		self.assertIn("B.14.2", finding.source)


class FacetsTest(TestCase):
	"""What the GCD of a report announces, read from its facts as ERiC reads it (ERiC E-Bilanz-Dokumentation 44.3.6.0,
	Kap. 3.2 to 3.5)."""

	def test_reads_the_choices_of_the_gcd(self):
		self.assertEqual(
			Facets.of(complete()),
			Facets(
				legal_status="GMBH",
				income_statement_format="GKV",
				accounting_standard="HAOE",
				statement_type="E",
				report_status="E",
				components=frozenset({"B", "GuV", "BVV"}),
			),
		)

	def test_without_a_gcd_it_announces_nothing(self):
		self.assertEqual(Facets.of(report(*BILANZ_FACTS)), Facets())

	def test_the_kinds_of_legal_form_of_the_legal_status(self):
		"""The kinds of Leitfaden B.4.1, „Gesellschaft mit beschränkter Haftung ... KST“, as the references of each value
		of genInfo.company.id.legalStatus carry them; none without a legal status."""
		taxonomy = mini.view()
		self.assertEqual(checks.legal_forms(taxonomy, Facets.of(complete())), {LegalForm.KST})
		self.assertEqual(checks.legal_forms(taxonomy, Facets.of(complete(legal="EU"))), {LegalForm.EU})
		self.assertEqual(checks.legal_forms(taxonomy, Facets()), frozenset())
		self.assertEqual(checks.legal_forms(taxonomy, Facets(legal_status="XYZ")), frozenset())

	def test_a_steuerbilanz_or_a_handelsbilanz(self):
		"""„Handelsbilanz, wenn „deutsches Handelsrecht“ [HGBM]; Steuerbilanz, wenn „deutsches Steuerrecht“ [AO]. Auch
		als Steuerbilanz behandelt wird: „deutsches Handelsrecht (sog. Einheitsbilanz)“ [HAOE].“ (Leitfaden B.13)"""
		for standard, steuerbilanz in (("HAOE", True), ("AO", True), ("HGBM", False)):
			with self.subTest(standard=standard):
				self.assertEqual(Facets.of(complete(standard=standard)).steuerbilanz, steuerbilanz)
		self.assertFalse(Facets().steuerbilanz)

	def test_a_guv_format_other_than_gkv_and_ukv(self):
		"""„anderes Gewinnermittlungsverfahren“ [S] and its „Erläuterungen“ [SERL] are neither format of
		typeOperatingResult, so no position is left out for its format (Leitfaden A.9.1, B.14.3.1.15)."""
		facets = Facets(legal_status="GMBH", income_statement_format="SERL", components=frozenset({"GuV"}))
		self.assertIsNone(facets.format)
		required = checks.required(
			mini.view(), replace(facets, report_status="E", statement_type="E"), PERIODS
		)
		self.assertIn(f"{A}is.netIncome.materialServices", required)
		self.assertIn(f"{A}is.netIncome.costOfSales", required)

	def test_a_final_jahresabschluss_or_eroeffnungsbilanz(self):
		"""The GAAP Mussfelder count for „Jahresabschluss“, „Eröffnungsbilanz“ and the other kinds of B.14.2.2 when the
		report is „endgültig“."""
		self.assertTrue(Facets.of(complete()).final)
		self.assertTrue(Facets.of(complete(statement="EB")).final)
		self.assertTrue(Facets.of(complete(statement="EB")).opening)
		self.assertFalse(Facets.of(complete(status="V")).final)
		self.assertFalse(Facets.of(complete()).opening)


class ComponentsTest(TestCase):
	"""„Es ist sicherzustellen, dass zu den ... angekündigten Berichtsbestandteilen auch tatsächlich werthaltige
	Angaben (ungleich „NIL") für das aktuelle Wirtschaftsjahr übermittelt werden ... Wird ein Berichtsbestandteil
	nicht angekündigt, dürfen dazu keine Angaben übermittelt werden (auch nicht „NIL“).“ (Leitfaden B.9.2)"""

	def test_each_component_is_a_presentation_network(self):
		self.assertEqual((BILANZ.code, BILANZ.role), ("B", BALANCE_SHEET))
		self.assertEqual(BILANZ.value, element("B"))
		self.assertEqual(
			[component.code for component in COMPONENTS],
			["B", "EB", "GuV", "GuVMicroBilG", "BVV", "BAL", "KS", "STU", "EV", "H", "SA"],
		)

	def test_an_announced_component_has_a_value(self):
		report_ = without(complete(), *(fact.concept for fact in BVV_FACTS))
		self.assertEqual(
			codes(checks.components(report_, mini.view(), Facets.of(report_))),
			[(Code.COMPONENT, element("BVV"))],
		)
		nil_only = replaced(complete(), *(nil(fact.concept, fact.period) for fact in BVV_FACTS))
		self.assertEqual(
			codes(checks.components(nil_only, mini.view(), Facets.of(nil_only))),
			[(Code.COMPONENT, element("BVV"))],
		)

	def test_a_component_not_announced_has_no_facts(self):
		report_ = complete(elements=("B", "GuV"))
		self.assertEqual(
			codes(checks.components(report_, mini.view(), Facets.of(report_))),
			[(Code.COMPONENT, fact.concept) for fact in BVV_FACTS],
		)

	def test_the_anlagenspiegel_by_its_hypercube_and_the_ueberleitung_by_its_name(self):
		"""„Die Position ist dem XBRL-Hypercube „Anlagenspiegel (brutto)" [cube_.nt.ass.gross] zugeordnet.“ (B.9.4.8);
		„Der „name“ der Position beginnt mit „hbst.transfer".“ (B.9.3.10)"""
		row = (TAX_BALANCE, (f"{A}dim_changes.nt.ass.gross", f"{A}bs.ass.fixAss"))
		transfer = Tuple(
			f"{A}hbst.transfer",
			(
				choice(f"{A}hbst.transfer.kind", f"{A}hbst.transfer.kind.changeValue"),
				Tuple(
					f"{A}hbst.transfer.bsAss",
					(
						Item(f"{A}hbst.transfer.bsAss.name", WJ, f"{A}bs.ass.fixAss.tan"),
						euros("hbst.transfer.bsAss.changeValueActualPeriod", "5", WJ),
					),
				),
			),
		)
		facts = (euros("all", "60", WJ, row), transfer)
		self.assertEqual(
			codes(checks.components(complete(*facts), mini.view(), Facets.of(complete()))),
			[(Code.COMPONENT, f"{A}all"), (Code.COMPONENT, f"{A}hbst.transfer")],
		)
		announced = complete(*facts, elements=("B", "GuV", "BVV", "BAL", "STU"))
		self.assertEqual(checks.components(announced, mini.view(), Facets.of(announced)), ())

	def test_the_anhang_outside_the_anlagenspiegel(self):
		"""„andere Anhangangaben“ are the positions of the Anhang in no hypercube of the Anlagenspiegel and other than the
		„Anlagenverzeichnis“ [nt.reg] (Leitfaden B.9.4.6), while the Anlagenspiegel holds the positions of its hypercube
		only (B.9.4.8); the Anlagenverzeichnis is a component Steuerbote does not know."""
		row = (TAX_BALANCE, (f"{A}dim_changes.nt.ass.gross", f"{A}bs.ass.fixAss"))
		facts = (
			euros("all", "60", WJ, row),
			Item(f"{A}nt.otherInfo", WJ, "Keine weiteren Angaben"),
			Item(f"{A}nt.reg", WJ, "siehe Fußnote"),
		)
		without_sa = complete(*facts, elements=("B", "GuV", "BVV", "BAL"))
		findings = checks.components(without_sa, mini.view(), Facets.of(without_sa))
		self.assertEqual(codes(findings), [(Code.COMPONENT, f"{A}nt.otherInfo")])
		self.assertIn("„andere Anhangangaben“", findings[0].text)
		with_sa = complete(*facts, elements=("B", "GuV", "BVV", "BAL", "SA"))
		self.assertEqual(checks.components(with_sa, mini.view(), Facets.of(with_sa)), ())


class MussfelderTest(TestCase):
	"""„Der übermittelte Datensatz ist darauf hin zu überprüfen, dass er alle in der Taxonomie Steuer als Mussfelder
	definierten ... Positionen im Datensatz enthält“: transmittable in the fiscal year, for the legal form and the GuV
	format, in an announced component (Leitfaden B.14.2.1, B.14.2.2); „Nicht aus der Buchführung mit Werten zu
	belegende Mussfelder ... müssen im Datensatz „leer“ (technisch mit „NIL“) übermittelt werden.“ (B.14.2.3)"""

	def test_the_mussfelder_of_a_gmbh_with_the_gkv(self):
		self.assertEqual(
			checks.required(mini.view(), Facets.of(complete()), PERIODS),
			(
				f"{G}report.id.reportStatus",
				f"{G}report.id.reportElement",
				*(element(code) for code in ("B", "GuV", "BVV", "BAL", "KS", "STU", "EB")),
				f"{G}report.id.statementType",
				f"{G}report.id.accountingStandard",
				f"{G}report.id.incomeStatementFormat",
				f"{G}report.period.fiscalYearBegin",
				f"{G}report.period.fiscalYearEnd",
				f"{G}report.period.balSheetClosingDate",
				f"{G}company.id.name",
				f"{G}company.id.location.houseNo",
				f"{G}company.id.legalStatus",
				f"{G}company.id.idNo",
				f"{G}company.id.idNo.type.companyId.ST13",
				f"{G}company.id.shareholder",
				f"{G}company.id.shareholder.name",
				f"{A}bs.ass",
				f"{A}bs.ass.fixAss",
				f"{A}bs.ass.fixAss.intan",
				f"{A}bs.ass.fixAss.intan.concessionBrands",
				f"{A}bs.ass.fixAss.tan",
				f"{A}bs.ass.currAss",
				f"{A}bs.ass.currAss.cashEquiv",
				f"{A}bs.eqLiab",
				f"{A}bs.eqLiab.equity",
				f"{A}bs.eqLiab.equity.subscribed",
				f"{A}bs.eqLiab.equity.subscribed.corp",
				f"{A}bs.eqLiab.equity.netIncome",
				f"{A}bs.eqLiab.equity.netIncome.taxBalanceGenerally",
				f"{A}bs.eqLiab.liab",
				f"{A}bs.eqLiab.liab.bank",
				f"{A}is.netIncome",
				f"{A}is.netIncome.netSales",
				f"{A}is.netIncome.materialServices",
				f"{A}is.netIncome.tax",
				f"{A}BVV.profitLoss",
				f"{A}BVV.profitLoss.assetsCurrentYear",
				f"{A}BVV.profitLoss.assetsPreviousYear",
			),
		)

	def test_a_missing_mussfeld(self):
		report_ = without(complete(), f"{A}bs.ass.fixAss.tan", f"{G}company.id.name")
		findings = checks.mussfelder(report_, mini.view(), Facets.of(report_))
		self.assertEqual(
			codes(findings),
			[(Code.MUSSFELD, f"{G}company.id.name"), (Code.MUSSFELD, f"{A}bs.ass.fixAss.tan")],
		)
		self.assertEqual(findings[1].period, ST)

	def test_a_summenmussfeld_is_named_so(self):
		"""„Summenmussfelder sind stets zu übermitteln.“ (Leitfaden A.9.3)"""
		(finding,) = checks.mussfelder(
			without(complete(), f"{A}bs.ass.fixAss"), mini.view(), Facets.of(complete())
		)
		self.assertEqual(finding.concept, f"{A}bs.ass.fixAss")
		self.assertIn("Das Summenmussfeld „Anlagevermögen“ fehlt.", finding.text)

	def test_nil_fills_a_mussfeld(self):
		report_ = replaced(complete(), nil(f"{A}bs.ass.fixAss.tan", ST))
		self.assertEqual(checks.mussfelder(report_, mini.view(), Facets.of(report_)), ())

	def test_a_mussfeld_of_the_previous_year_fills_none(self):
		report_ = replaced(
			without(complete(periods=PRIOR), f"{A}bs.ass.fixAss.tan"),
			euros("bs.ass.fixAss.tan", "40", Period.VORJAHR_STICHTAG),
		)
		self.assertEqual(
			codes(checks.mussfelder(report_, mini.view(), Facets.of(report_))),
			[(Code.MUSSFELD, f"{A}bs.ass.fixAss.tan")],
		)

	def test_a_mussfeld_inside_a_tuple(self):
		"""The shareholder of the GmbH example: a tuple of NIL values, not a NIL tuple."""
		report_ = without(complete(), f"{G}company.id.shareholder")
		self.assertEqual(
			codes(checks.mussfelder(report_, mini.view(), Facets.of(report_))),
			[
				(Code.MUSSFELD, f"{G}company.id.shareholder"),
				(Code.MUSSFELD, f"{G}company.id.shareholder.name"),
			],
		)
		nil_tuple = complete(Tuple(f"{G}company.id.shareholder", nil=True))
		nil_tuple = replace(
			nil_tuple,
			facts=tuple(
				fact
				for fact in nil_tuple.facts
				if not (isinstance(fact, Tuple) and fact.concept.endswith("shareholder") and not fact.nil)
			),
		)
		self.assertEqual(
			codes(checks.mussfelder(nil_tuple, mini.view(), Facets.of(nil_tuple))),
			[(Code.MUSSFELD, f"{G}company.id.shareholder.name")],
		)

	def test_the_mussfelder_of_the_legal_form_and_the_format(self):
		"""„Bei den den Kapitalgesellschaften zuzuordnenden Rechtsform-Arten, dürfen nur Positionen mit der Auszeichnung
		„legalFormKSt“ = „true“ ... übermittelt werden“ (B.4.2); the GuV format of B.14.3.1.15."""
		required = checks.required(mini.view(), Facets.of(complete(legal="EU", income="UKV")), PERIODS)
		self.assertIn(f"{A}is.netIncome.costOfSales", required)
		self.assertIn(element("SGE"), required)
		for concept in (
			f"{A}is.netIncome.materialServices",
			f"{A}is.netIncome.tax",
			f"{A}bs.eqLiab.equity.subscribed.corp",
			f"{A}bs.eqLiab.equity.subscribed.limitedLiablePartners",
		):
			self.assertNotIn(concept, required)

	def test_the_mussfelder_of_the_fiscal_year(self):
		"""fiscalValidSince 2027-01-01 makes Kassenbestand a Mussfeld from the fiscal year 2027 (B.14.4.2)."""
		later = Periods(date(2027, 1, 1), date(2027, 12, 31))
		self.assertNotIn(
			f"{A}bs.ass.currAss.cashEquiv.cash", checks.required(mini.view(), Facets.of(complete()), PERIODS)
		)
		self.assertIn(
			f"{A}bs.ass.currAss.cashEquiv.cash", checks.required(mini.view(), Facets.of(complete()), later)
		)

	def test_only_those_of_the_announced_components(self):
		required = checks.required(mini.view(), Facets.of(complete(elements=("B",))), PERIODS)
		self.assertIn(f"{A}bs.ass", required)
		self.assertNotIn(f"{A}is.netIncome", required)
		self.assertNotIn(f"{A}BVV.profitLoss", required)

	def test_the_gaap_mussfelder_only_of_a_final_report(self):
		required = checks.required(mini.view(), Facets.of(complete(status="V")), PERIODS)
		self.assertIn(f"{G}company.id.name", required)
		self.assertNotIn(f"{A}bs.ass", required)

	def test_the_rows_of_a_table_are_left_to_their_component(self):
		"""The Mussfelder of the Anlagenspiegel count for each combination of members that has a value (B.14.12.1
		a), which only the component knows."""
		required = checks.required(
			mini.view(), Facets.of(complete(elements=("B", "GuV", "BVV", "BAL"))), PERIODS
		)
		self.assertNotIn(f"{A}all", required)
		self.assertNotIn(f"{A}grossCost.beginning", required)


class AdmissibilityTest(TestCase):
	def test_a_position_of_another_legal_form(self):
		"""„Unabhängig von der Wahl des Einstiegsschemas werden alle Angaben zu rechtsformfremden GCD-Positionen moniert,
		auch solche in Form eines „NIL-Eintrags“.“ (ERiC E-Bilanz-Dokumentation, Kap. 3.6; Leitfaden B.4.2)"""
		report_ = complete(
			nil(f"{A}bs.eqLiab.equity.subscribed.limitedLiablePartners", ST),
			Item(f"{G}company.id.optionKStGs1a", WJ, False),
		)
		self.assertEqual(
			codes(checks.admissibility(report_, mini.view(), Facets.of(report_))),
			[
				(Code.LEGAL_FORM, f"{A}bs.eqLiab.equity.subscribed.limitedLiablePartners"),
				(Code.LEGAL_FORM, f"{G}company.id.optionKStGs1a"),
			],
		)

	def test_a_position_of_the_other_format(self):
		"""„Wenn das GuV-Format „Gesamtkostenverfahren“ ... ausgewählt wurde, dann dürfen Positionen mit der Auszeichnung
		typeOperatingResult = UKV nicht übermittelt werden.“ (Leitfaden B.14.3.1.15)"""
		report_ = complete(nil(f"{A}is.netIncome.costOfSales", WJ))
		self.assertEqual(
			codes(checks.admissibility(report_, mini.view(), Facets.of(report_))),
			[(Code.INCOME_STATEMENT_FORMAT, f"{A}is.netIncome.costOfSales")],
		)

	def test_a_position_not_permitted_for_the_purpose(self):
		"""„dürfen Positionen oder Auswahlelemente, die als „notPermittedFor = Einreichung an Finanzverwaltung“
		gekennzeichnet sind, nicht enthalten sein“ (Leitfaden B.14.6); a Steuerbilanz neither with those „steuerlich“
		(ERiC E-Bilanz-Dokumentation, Kap. 3.6). The E-Bilanz of a Handelsbilanz sends the steuerlicher Ausgleichsposten,
		„handelsrechtlich“ not permitted, as NIL, as the GmbH example of the ERiC documentation does; the Offenlegung
		asks for „handelsrechtlich“ and refuses it (A.9.2)."""
		report_ = complete(
			euros("bs.ass.consolidationDifference", "0"), euros("bs.ass.fixAss.intan.selfmade", "0")
		)
		self.assertEqual(
			codes(checks.admissibility(report_, mini.view(), Facets.of(report_))),
			[
				(Code.NOT_PERMITTED, f"{A}bs.ass.consolidationDifference"),
				(Code.NOT_PERMITTED, f"{A}bs.ass.fixAss.intan.selfmade"),
			],
		)
		handelsbilanz = complete(euros("bs.ass.fixAss.intan.selfmade", "0"), standard="HGBM")
		self.assertEqual(checks.admissibility(handelsbilanz, mini.view(), Facets.of(handelsbilanz)), ())
		self.assertEqual(
			codes(
				checks.admissibility(
					handelsbilanz, mini.view(), Facets.of(handelsbilanz), purposes=("handelsrechtlich",)
				)
			),
			[(Code.NOT_PERMITTED, f"{A}bs.eqLiab.equity.netIncome.taxBalanceGenerally")],
		)

	def test_a_position_that_cannot_be_transmitted(self):
		"""„Es dürfen nur solche Positionen übermittelt werden, die in dem Presentation Network erfasst sind, welches im
		Zuge der „taxonomy discovery“ ... des jeweiligen Einstiegsschemas aufgebaut wird. Die Übermittelbarkeit kann
		zeitlich eingeschränkt sein“ (Leitfaden B.11, B.14.4.1)."""
		report_ = complete(
			euros("bs.ass.groupOnly", "0"),
			euros("bs.ass.currAss.cashEquiv.cryptoAssets", "0"),
			euros("bs.ass.fixAss.tan.oldEquipment", "0"),
		)
		self.assertEqual(
			codes(checks.admissibility(report_, mini.view(), Facets.of(report_))),
			[
				(Code.NOT_TRANSMITTABLE, f"{A}bs.ass.groupOnly"),
				(Code.NOT_TRANSMITTABLE, f"{A}bs.ass.currAss.cashEquiv.cryptoAssets"),
				(Code.NOT_TRANSMITTABLE, f"{A}bs.ass.fixAss.tan.oldEquipment"),
			],
		)
		later = replace(report_, periods=Periods(date(2027, 1, 1), date(2027, 12, 31)))
		self.assertNotIn(
			(Code.NOT_TRANSMITTABLE, f"{A}bs.ass.currAss.cashEquiv.cryptoAssets"),
			codes(checks.admissibility(later, mini.view(), Facets.of(later))),
		)

	def test_a_position_of_a_sonder_or_ergaenzungsbilanz_only_as_nil(self):
		"""„Die mit „onlyPermittedForSoBil_ErgBil“ = true gekennzeichneten Positionen dürfen nur bei der Übermittlung
		einer Sonder- oder Ergänzungsbilanz werthaltig übermittelt werden.“ (Leitfaden A.9.3) ERiC rejects them otherwise
		(ERiC E-Bilanz-Dokumentation, Kap. 3.6), and a GmbH files neither: a value is refused, inside a tuple so marked as
		well, NIL is not."""
		according = f"{G}report.id.accordingTo"
		valued = complete(
			euros("bs.eqLiab.liab.colEntity", "0"),
			Tuple(according, (Item(f"{according}.name", WJ, "Beispiel GbR"),)),
		)
		findings = checks.admissibility(valued, mini.view(), Facets.of(valued))
		self.assertEqual(
			codes(findings),
			[
				(Code.SPECIAL_BALANCE, f"{A}bs.eqLiab.liab.colEntity"),
				(Code.SPECIAL_BALANCE, f"{according}.name"),
			],
		)
		self.assertIn("A.9.3", findings[0].source)
		nil_only = complete(
			nil(f"{A}bs.eqLiab.liab.colEntity", ST), Tuple(according, (nil(f"{according}.name", WJ),))
		)
		self.assertEqual(checks.admissibility(nil_only, mini.view(), Facets.of(nil_only)), ())

	def test_the_parts_of_a_tuple_too(self):
		"""„wirkt sich die Auszeichnung einer Tupel-Position mit „notPermittedFor = Einreichung an Finanzverwaltung“
		implizit auf alle ihre Unterelemente aus“ (Leitfaden B.14.6): each fact is checked, inside tuples as well."""
		report_ = without(complete(), ELEMENTS)
		report_ = replace(
			report_,
			facts=(
				*report_.facts,
				choice(
					ELEMENTS,
					element("B"),
					element("GuV"),
					element("BVV"),
					unreported=(element("BAL"), element("KS"), element("STU"), element("EB"), element("SGE")),
				),
			),
		)
		self.assertEqual(
			codes(checks.admissibility(report_, mini.view(), Facets.of(report_))),
			[(Code.LEGAL_FORM, element("SGE"))],
		)


class PriorYearTest(TestCase):
	def test_a_steuerbilanz_has_no_previous_year(self):
		"""„Steuerbilanzen dürfen keine Vorjahresangaben und somit weder einen periodenbezogenen noch einen
		stichtagsbezogenen Vorjahreskontext beinhalten.“ (Leitfaden B.8.3)"""
		report_ = complete(euros("bs.ass", "90", Period.VORJAHR_STICHTAG), periods=PRIOR)
		findings = checks.prior_year(report_, mini.view(), Facets.of(report_))
		self.assertEqual(codes(findings), [(Code.PRIOR_YEAR, f"{A}bs.ass")])
		self.assertEqual(findings[0].period, Period.VORJAHR_STICHTAG)

	def test_an_eroeffnungsbilanz_neither(self):
		"""„Wurde der vorliegende Datensatz als „Steuerbilanz“ oder „Eröffnungsbilanz“ kategorisiert, so wird
		ausgeschlossen, dass die enthaltenen Fakten sich auf Vorjahreskontexte beziehen.“ (ERiC
		E-Bilanz-Dokumentation, Kap. 3.13)"""
		report_ = complete(
			euros("bs.ass", "90", Period.VORJAHR_STICHTAG), periods=PRIOR, standard="HGBM", statement="EB"
		)
		self.assertEqual(
			codes(checks.prior_year(report_, mini.view(), Facets.of(report_))),
			[(Code.PRIOR_YEAR, f"{A}bs.ass")],
		)

	def test_a_handelsbilanz_may_show_it_but_not_in_the_ueberleitung(self):
		"""„Handelsbilanzen dürfen auch Angaben zum Vorjahr ... enthalten ... Für den Bereich der
		Überleitungsrechnung sind Vorjahresangaben unzulässig.“ (Leitfaden B.8.3)"""
		transfer = Tuple(
			f"{A}hbst.transfer",
			(
				choice(f"{A}hbst.transfer.kind", f"{A}hbst.transfer.kind.changeValue"),
				Tuple(
					f"{A}hbst.transfer.bsAss",
					(
						Item(f"{A}hbst.transfer.bsAss.name", Period.VORJAHR, f"{A}bs.ass.fixAss.tan"),
						euros("hbst.transfer.bsAss.changeValueActualPeriod", "5", Period.VORJAHR),
					),
				),
			),
		)
		report_ = complete(
			euros("bs.ass", "90", Period.VORJAHR_STICHTAG), transfer, periods=PRIOR, standard="HGBM"
		)
		self.assertEqual(
			codes(checks.prior_year(report_, mini.view(), Facets.of(report_))),
			[
				(Code.PRIOR_YEAR, f"{A}hbst.transfer.bsAss.name"),
				(Code.PRIOR_YEAR, f"{A}hbst.transfer.bsAss.changeValueActualPeriod"),
			],
		)


class CalculationTest(TestCase):
	"""„Der Datensatz ist nach den Vorgaben der Calculation Linkbase daraufhin zu prüfen, dass er rechnerisch korrekt
	ist ... Mit „NIL“ übermittelte „leere“ Mussfelder sind in die Berechnungen nicht einzubeziehen.“ (Leitfaden
	B.14.11)"""

	def test_a_total_is_the_sum_of_its_items(self):
		report_ = replaced(complete(), euros("bs.ass", "110"))
		findings = checks.calculation(report_, mini.view())
		self.assertEqual(codes(findings), [(Code.CALCULATION, f"{A}bs.ass")])
		self.assertIn("110,00 €", findings[0].text)
		self.assertIn("100,00 €", findings[0].text)
		self.assertEqual(findings[0].period, ST)

	def test_with_the_weight_of_each_item(self):
		report_ = replaced(complete(), euros("is.netIncome.tax", "25", WJ))
		self.assertEqual(
			codes(checks.calculation(report_, mini.view())), [(Code.CALCULATION, f"{A}is.netIncome")]
		)

	def test_nil_is_left_out(self):
		report_ = replaced(
			complete(),
			euros("bs.ass.fixAss", "40"),
			nil(f"{A}bs.ass.fixAss.intan", ST),
			nil(f"{A}bs.ass.fixAss.intan.concessionBrands", ST),
			euros("bs.ass", "80"),
		)
		self.assertEqual(checks.calculation(report_, mini.view()), ())

	def test_a_total_without_items_is_not_checked(self):
		report_ = without(complete(), f"{A}bs.ass.fixAss.intan.concessionBrands")
		self.assertEqual(checks.calculation(report_, mini.view()), ())

	def test_each_context_on_its_own(self):
		report_ = complete(
			euros("bs.ass", "50", Period.VORJAHR_STICHTAG),
			euros("bs.ass.fixAss", "40", Period.VORJAHR_STICHTAG),
			periods=PRIOR,
		)
		findings = checks.calculation(report_, mini.view())
		self.assertEqual(codes(findings), [(Code.CALCULATION, f"{A}bs.ass")])
		self.assertEqual(findings[0].period, Period.VORJAHR_STICHTAG)

	def test_the_rows_of_a_table_add_up_along_the_bilanz(self):
		"""„Alle Angaben zu einer gegebenen Position der Wertentwicklung werden der Oberpositions- und rechnerischen
		Prüfung unterzogen. Als Grundlage dienen die übereinstimmenden Positionshierarchien der Berichtsteile „Bilanz“
		und „Anhang“.“ (Leitfaden B.14.12.1 b)"""

		def row(member: str) -> tuple:
			return (TAX_BALANCE, (f"{A}dim_changes.nt.ass.gross", f"{A}{member}"))

		facts = (
			euros("gross", "60", WJ, row("bs.ass.fixAss")),
			euros("gross", "20", WJ, row("bs.ass.fixAss.intan")),
			euros("gross", "30", WJ, row("bs.ass.fixAss.tan")),
			euros("grossCost.beginning", "10", WJ, row("bs.ass.fixAss.tan")),
			euros("gross.addition", "10", WJ, row("bs.ass.fixAss.tan")),
		)
		findings = checks.calculation(report(*facts), mini.view())
		self.assertEqual(codes(findings), [(Code.CALCULATION, f"{A}gross"), (Code.CALCULATION, f"{A}gross")])
		self.assertEqual(
			[finding.dimensions for finding in findings],
			[tuple(sorted(row("bs.ass.fixAss.tan"))), tuple(sorted(row("bs.ass.fixAss")))],
		)


class OberpositionenTest(TestCase):
	"""„Das bedeutet, dass zu jeder angegebenen Position auch sämtliche Oberpositionen aufgeführt werden müssen (ggf.
	mit NIL, wenn auch die Unterpositionen alle mit NIL übermittelt wurden). Ist eine Unterposition werthaltig
	angegeben, so sind auch ihre Oberpositionen werthaltig zu berichten.“ (Leitfaden B.14.10)"""

	def test_each_position_with_its_oberpositionen(self):
		findings = checks.oberpositionen(report(euros("bs.ass.fixAss.tan", "40")), mini.view())
		self.assertEqual(
			codes(findings), [(Code.OBERPOSITION, f"{A}bs.ass.fixAss"), (Code.OBERPOSITION, f"{A}bs.ass")]
		)
		self.assertIn("„Sachanlagen (steuerlich)“", findings[0].text)

	def test_a_position_with_a_value_has_oberpositionen_with_a_value(self):
		report_ = replaced(complete(), nil(f"{A}bs.ass.fixAss", ST))
		self.assertEqual(
			codes(checks.oberpositionen(report_, mini.view())), [(Code.OBERPOSITION, f"{A}bs.ass.fixAss")]
		)

	def test_nil_takes_nil(self):
		facts = (nil(f"{A}bs.ass.fixAss.tan", ST), nil(f"{A}bs.ass.fixAss", ST), nil(f"{A}bs.ass", ST))
		self.assertEqual(checks.oberpositionen(report(*facts), mini.view()), ())
		self.assertEqual(
			codes(checks.oberpositionen(report(*facts[:1]), mini.view())),
			[(Code.OBERPOSITION, f"{A}bs.ass.fixAss"), (Code.OBERPOSITION, f"{A}bs.ass")],
		)

	def test_a_davon_position_too(self):
		"""„Ob die betreffenden Positionen rechnerisch verknüpft sind, ist in diesem Zusammenhang unerheblich.“"""
		report_ = without(complete(euros("bs.eqLiab.liab.bank.upTo1year", "10")), f"{A}bs.eqLiab.liab.bank")
		self.assertEqual(
			codes(checks.oberpositionen(report_, mini.view())),
			[(Code.OBERPOSITION, f"{A}bs.eqLiab.liab.bank")],
		)

	def test_not_the_previous_year(self):
		"""„Die genannten Forderungen beziehen sich ausschließlich auf Angaben zum aktuellen Berichtszeitraum bzw. zum
		aktuellen Stichtag und gelten nicht für Vorjahresangaben.“"""
		report_ = report(euros("bs.ass.fixAss.tan", "40", Period.VORJAHR_STICHTAG), periods=PRIOR)
		self.assertEqual(checks.oberpositionen(report_, mini.view()), ())

	def test_the_rows_of_the_anlagenspiegel(self):
		"""„Bezogen auf die Positionen des Anlagespiegels gilt dies auch im Bereich „Anhang“; entscheidend für die
		Kategorisierung als Anlagespiegel-Position ist dabei die Zuordnung des zugrundeliegenden Konzepts zu einem
		XBRL-Hypercube.“ (ERiC E-Bilanz-Dokumentation, Kap. 3.9), along the value development and along the positions of
		the Bilanz (Leitfaden B.14.12.1 b): the text positions „Anlagenspiegel“ and „Anhang“ above the table are in no
		hypercube, and the abstract titles are no positions to report."""
		tan = (TAX_BALANCE, (f"{A}dim_changes.nt.ass.gross", f"{A}bs.ass.fixAss.tan"))
		fixed = (TAX_BALANCE, (f"{A}dim_changes.nt.ass.gross", f"{A}bs.ass.fixAss"))
		findings = checks.oberpositionen(report(euros("gross", "30", WJ, tan)), mini.view())
		self.assertEqual(
			[(finding.concept, finding.dimensions) for finding in findings],
			[(f"{A}all", tuple(sorted(tan))), (f"{A}gross", tuple(sorted(fixed)))],
		)


class SummenmussfelderTest(TestCase):
	"""„Wird eine als Summenmussfeld ausgezeichnete Position ... werthaltig und ungleich 0 berichtet, so ist mindestens
	eine ihrer rechnerisch verknüpften Unterpositionen werthaltig zu übermitteln.“ (Leitfaden B.14.14)"""

	def test_a_summenmussfeld_with_a_value_has_an_item_with_a_value(self):
		report_ = replaced(complete(), nil(f"{A}bs.ass.fixAss.intan.concessionBrands", ST))
		self.assertEqual(
			codes(checks.summenmussfelder(report_, mini.view())),
			[(Code.SUMMENMUSSFELD, f"{A}bs.ass.fixAss.intan")],
		)

	def test_zero_or_nil_needs_none(self):
		for value in (euros("bs.ass.fixAss.intan", "0"), nil(f"{A}bs.ass.fixAss.intan", ST)):
			with self.subTest(value=value):
				report_ = replaced(without(complete(), f"{A}bs.ass.fixAss.intan.concessionBrands"), value)
				self.assertEqual(checks.summenmussfelder(report_, mini.view()), ())

	def test_a_row_of_the_anlagenspiegel_at_a_summenmussfeld(self):
		"""„Die Prüfung wird entsprechend beim „Anlagenspiegel (brutto)“ ... bezogen auf „Positionen des
		Anlagevermögens“ [dim_changes.nt.ass.gross] und Positionen der „Wertentwicklung“ [piTitle.nt.ass.gross]
		durchgeführt.“ The rows below a row follow the Bilanz (B.14.12.1 b)."""
		fixed = (TAX_BALANCE, (f"{A}dim_changes.nt.ass.gross", f"{A}bs.ass.fixAss"))
		tangible = (TAX_BALANCE, (f"{A}dim_changes.nt.ass.gross", f"{A}bs.ass.fixAss.tan"))
		findings = checks.summenmussfelder(report(euros("all", "60", WJ, fixed)), mini.view())
		self.assertEqual(
			[(finding.code, finding.concept, finding.dimensions, finding.severity) for finding in findings],
			[(Code.SUMMENMUSSFELD, f"{A}all", tuple(sorted(fixed)), Severity.HINT)],
		)
		self.assertIn("In der Zeile „Anlagevermögen“, einem Summenmussfeld,", findings[0].text)
		rows = report(euros("all", "60", WJ, fixed), euros("all", "60", WJ, tangible))
		self.assertEqual(checks.summenmussfelder(rows, mini.view()), ())

	def test_in_the_anlagenspiegel_a_hint(self):
		"""The examples of the ERiC documentation 44.3.6.0 it calls valid report Summenmussfelder of the Anlagenspiegel
		without a value below them, such as „Abschreibungen der Periode“ [accDepr.DeprPeriod] in
		Anlagenspiegel_brutto_ohneUeberleitung.xml, so ERiC does not reject them: in a table the finding is a hint,
		along the value development as well."""
		tangible = (TAX_BALANCE, (f"{A}dim_changes.nt.ass.gross", f"{A}bs.ass.fixAss.tan"))
		(finding,) = checks.summenmussfelder(report(euros("gross", "30", WJ, tangible)), mini.view())
		self.assertEqual((finding.concept, finding.severity), (f"{A}gross", Severity.HINT))
		self.assertFalse(finding.blocking)
		self.assertIn(
			"Das Summenmussfeld „Anschaffungs- und Herstellungskosten zum Ende der Periode“", finding.text
		)
		with_items = report(euros("gross", "30", WJ, tangible), euros("gross.addition", "30", WJ, tangible))
		self.assertEqual(checks.summenmussfelder(with_items, mini.view()), ())

	def test_not_the_eigenkapital(self):
		"""„Die Prüfung ist bei den folgenden Positionen des Berichtsteils „Bilanz“ nicht durchzuführen: ... „Eigenkapital“
		[bs.eqLiab.equity] einschließlich aller Summenmussfelder unterhalb dieser Position“."""
		report_ = without(complete(), f"{A}bs.eqLiab.equity.subscribed.corp")
		self.assertEqual(checks.summenmussfelder(report_, mini.view()), ())

	def test_but_the_steuerlicher_ausgleichsposten(self):
		"""„Ausnahme: Bei der Position „Eigenkapital, steuerlicher Ausgleichsposten“
		[bs.eqLiab.equity.netIncome.taxBalanceGenerally] ist die Summenmussfeldprüfung durchzuführen.“"""
		report_ = replaced(
			complete(standard="AO"), euros("bs.eqLiab.equity.netIncome.taxBalanceGenerally", "5")
		)
		self.assertEqual(
			codes(checks.summenmussfelder(report_, mini.view())),
			[(Code.SUMMENMUSSFELD, f"{A}bs.eqLiab.equity.netIncome.taxBalanceGenerally")],
		)


class ContextsTest(TestCase):
	"""„Jeder der im eingereichten Datensatz spezifizierten Kontexte muss von mindestens einem Fakt referenziert
	werden.“ and one entity in all of them (Leitfaden B.14.7), checked on the instance itself."""

	def test_a_context_no_fact_refers_to(self):
		root = writer.instance(complete(), mini.view())
		extra = etree.fromstring(etree.tostring(root.find("{http://www.xbrl.org/2003/instance}context")))
		extra.set("id", "D-UNBENUTZT")
		root.insert(3, extra)
		findings = checks.contexts(root)
		self.assertEqual([finding.code for finding in findings], [Code.CONTEXT])
		self.assertIn("D-UNBENUTZT", findings[0].text)

	def test_one_entity(self):
		root = writer.instance(complete(), mini.view())
		identifier = root.find(".//{http://www.xbrl.org/2003/instance}identifier")
		identifier.text = "9198011310011"
		self.assertEqual([finding.code for finding in checks.contexts(root)], [Code.ENTITY])


KLEINST = (
	"bs.ass",
	"bs.ass.fixAss",
	"bs.ass.currAss",
	"bs.eqLiab",
	"bs.eqLiab.equity",
	"bs.eqLiab.liab",
)
"""What the Offenlegung of a Kleinstkapitalgesellschaft shows of the mini taxonomy: the totals and the positions with
letters (§ 266 Abs. 1 Satz 4 HGB), named as steuerbote/hgb/schemes.py names them, without the prefix."""
DISCLOSED = {
	"bs.ass": ("100", "90"),
	"bs.ass.fixAss": ("60", "50"),
	"bs.ass.currAss": ("40", "40"),
	"bs.eqLiab": ("100", "90"),
	"bs.eqLiab.equity": ("70", "60"),
	"bs.eqLiab.liab": ("30", "30"),
}


def disclosure(*facts: Fact, periods: Periods = PRIOR, view: View = View.COMMERCIAL_MICROBILG) -> Report:
	"""The Offenlegung of the GmbH as a Kleinstkapitalgesellschaft for 2026 and 2025, with further facts."""
	balance_sheet = [
		euros(concept, value, period)
		for concept, values in DISCLOSED.items()
		for value, period in zip(values, (ST, Period.VORJAHR_STICHTAG), strict=True)
	]
	return Report(ENTITY, periods, writer.entry_points(mini.view(view)), (*balance_sheet, *facts))


class PublishedTest(TestCase):
	"""„Auf Kleinstkapitalgesellschaften (§ 267a) ist § 325 Absatz 1 mit der Maßgabe anzuwenden, dass die Mitglieder
	des vertretungsberechtigten Organs nur die Bilanz zu übermitteln haben“ (§ 326 Abs. 2 Satz 1 HGB), at the levels
	of § 266 Abs. 1 Satz 4 HGB, and the register shows every position reported: „lediglich die Positionen, zu denen Werte
	berichtet werden, sowie deren übergeordnete Positionen“ („Arbeitshilfe für die Einreichung von
	Jahresabschlüssen/Finanzberichten im XBRL-Format“, Stand September 2025)."""

	def test_the_offenlegung_of_the_kleinst_publishes_its_bilanz(self):
		report_ = disclosure(Item(f"{G}company.id.name", WJ, "Beispiel GmbH"))
		self.assertEqual(checks.published(report_, mini.view(View.COMMERCIAL_MICROBILG), KLEINST), ())

	def test_no_position_below_the_levels_of_the_class(self):
		report_ = disclosure(euros("bs.ass.fixAss.tan", "60"))
		findings = checks.published(report_, mini.view(View.COMMERCIAL_MICROBILG), KLEINST)
		self.assertEqual(codes(findings), [(Code.NOT_PUBLISHED, f"{A}bs.ass.fixAss.tan")])
		self.assertIn("„Sachanlagen“", findings[0].text)
		self.assertIn("§ 266 Abs. 1", findings[0].source)
		self.assertEqual(
			checks.published(
				report_, mini.view(View.COMMERCIAL_MICROBILG), (*KLEINST, f"{A}bs.ass.fixAss.tan")
			),
			(),
		)

	def test_no_component_a_small_company_withholds(self):
		"""The GuV (§ 326 Abs. 1 Satz 1 HGB), and the Kontensalden and the Betriebsvermögensvergleich, which are no
		part of the Jahresabschluss to disclose (§ 325 Abs. 1 Satz 1 HGB): the Kontensalden would publish the balance of
		each account. A component is withheld even where the concepts name its positions."""
		account = Tuple(
			f"{A}detailedInformation.accountBalances",
			(
				Item(f"{A}detailedInformation.accountbalances.positionName", WJ, f"{A}bs.ass.currAss"),
				Item(f"{A}detailedInformation.accountbalances.accountNumber", WJ, "1200"),
				Item(f"{A}detailedInformation.accountbalances.accountDescription", WJ, "Bank"),
				euros("detailedInformation.accountbalances.amount", "40", WJ),
			),
		)
		report_ = disclosure(
			euros("is.netIncome", "10", WJ), euros("BVV.profitLoss", "10", WJ), account, view=View.COMMERCIAL
		)
		findings = checks.published(
			report_, mini.view(View.COMMERCIAL), (*KLEINST, "is.netIncome", "BVV.profitLoss")
		)
		self.assertEqual(
			codes(findings),
			[
				(Code.NOT_PUBLISHED, f"{A}is.netIncome"),
				(Code.NOT_PUBLISHED, f"{A}BVV.profitLoss"),
				(Code.NOT_PUBLISHED, f"{A}detailedInformation.accountBalances"),
			],
		)
		self.assertIn("„GuV“", findings[0].text)
		self.assertIn("§ 326", findings[0].source)
		self.assertIn("„Kontensalden zu einer oder mehrerer Positionen“", findings[2].text)

	def test_the_parts_of_a_tuple_of_the_gcd(self):
		"""The master data of the GCD are no positions of the Jahresabschluss and are not restricted."""
		report_ = disclosure(
			Tuple(
				f"{G}company.id.idNo", (Item(f"{G}company.id.idNo.type.companyId.ST13", WJ, "9198011310010"),)
			)
		)
		self.assertEqual(checks.published(report_, mini.view(View.COMMERCIAL_MICROBILG), KLEINST), ())


class ClosingDatesTest(TestCase):
	"""„In der Bilanz sowie in der Gewinn- und Verlustrechnung ist zu jedem Posten der entsprechende Betrag des
	vorhergehenden Geschäftsjahrs anzugeben.“ (§ 265 Abs. 2 Satz 1 HGB) „Ein Posten der Bilanz ..., der keinen Betrag
	ausweist, braucht nicht aufgeführt zu werden, es sei denn, daß im vorhergehenden Geschäftsjahr unter diesem Posten
	ein Betrag ausgewiesen wurde.“ (§ 265 Abs. 8 HGB)"""

	def test_each_posten_for_both_closing_dates(self):
		report_ = disclosure()
		self.assertEqual(checks.closing_dates(report_, mini.view(View.COMMERCIAL_MICROBILG)), ())
		report_ = replace(
			report_,
			facts=tuple(
				fact
				for fact in report_.facts
				if (fact.concept, fact.period)
				not in ((f"{A}bs.ass.fixAss", Period.VORJAHR_STICHTAG), (f"{A}bs.ass.currAss", ST))
			),
		)
		findings = checks.closing_dates(report_, mini.view(View.COMMERCIAL_MICROBILG))
		self.assertEqual(
			[(finding.code, finding.concept, finding.period) for finding in findings],
			[
				(Code.PRIOR_YEAR_AMOUNT, f"{A}bs.ass.fixAss", ST),
				(Code.PRIOR_YEAR_AMOUNT, f"{A}bs.ass.currAss", Period.VORJAHR_STICHTAG),
			],
		)
		self.assertIn("Vorjahres", findings[0].text)
		self.assertEqual(findings[0].source, "§ 265 Abs. 2 Satz 1 HGB")
		self.assertEqual(findings[1].source, "§ 265 Abs. 8 HGB")

	def test_not_a_davon_vermerk(self):
		"""A „davon“ position is no Posten: the calculation linkbase does not add it up."""
		report_ = disclosure(euros("bs.eqLiab.liab.bank.upTo1year", "10"))
		self.assertEqual(checks.closing_dates(report_, mini.view(View.COMMERCIAL_MICROBILG)), ())

	def test_not_in_the_first_fiscal_year(self):
		"""A company in its first fiscal year has no previous year to give."""
		report_ = Report(
			ENTITY,
			PERIODS,
			writer.entry_points(mini.view(View.COMMERCIAL_MICROBILG)),
			(euros("bs.ass", "100"), euros("bs.ass.fixAss", "100")),
		)
		self.assertEqual(checks.closing_dates(report_, mini.view(View.COMMERCIAL_MICROBILG)), ())


ACCOUNT_BALANCES = f"{A}detailedInformation.accountBalances"
NOT_POSSIBLE = f"{A}detailedInformation.accountbalances.notPossible"
LEAVES = (
	("bs.ass.fixAss.intan.concessionBrands", "20"),
	("bs.ass.fixAss.tan", "40"),
	("bs.ass.currAss.cashEquiv.bank", "40"),
	("bs.eqLiab.equity.subscribed.corp", "25"),
	("bs.eqLiab.equity.netIncome", "45"),
	("bs.eqLiab.liab.bank", "30"),
	("is.netIncome.netSales", "100"),
	("is.netIncome.materialServices", "40"),
	("is.netIncome.tax", "15"),
)
"""The positions of Bilanz and GuV of the report with a value and none under them in the calculation."""


def kontensaldo(position: str, value: str, account: tuple[str, str] | None = ("1200", "Konto"), *, flag=None):
	"""A tuple „Kontensalden zu einer Position“ of 6.10, with account information or, without, notPossible true."""
	number, description = account or (None, None)
	return Tuple(
		ACCOUNT_BALANCES,
		(
			Item(f"{A}detailedInformation.accountbalances.positionName", WJ, f"{A}{position}"),
			Item(f"{A}detailedInformation.accountbalances.accountNumber", WJ, number),
			Item(f"{A}detailedInformation.accountbalances.accountDescription", WJ, description),
			amount(f"{A}detailedInformation.accountbalances.amount", WJ, Decimal(value)),
			Item(NOT_POSSIBLE, WJ, (account is None) if flag is None else flag),
		),
	)


def report_6_10(*facts: Fact, elements: tuple[str, ...] = ("B", "GuV", "BVV", "KS")) -> Report:
	"""The report of the GmbH on the mini taxonomy 6.10 with its Kontensalden and further facts."""
	return Report(
		ENTITY,
		PERIODS,
		writer.entry_points(mini.view(View.FISCAL, mini.VERSION_6_10)),
		(*gcd(elements=elements), *BILANZ_FACTS, *GUV_FACTS, *BVV_FACTS, *facts),
	)


def kontensalden(*facts: Fact, leaves=LEAVES, **values) -> tuple[tuple[str, str], ...]:
	report_ = report_6_10(*(kontensaldo(position, value) for position, value in leaves), *facts, **values)
	view = mini.view(View.FISCAL, mini.VERSION_6_10)
	return tuple(
		(finding.code.value, finding.concept)
		for finding in checks.kontensalden(report_, view, Facets.of(report_))
	)


class KontensaldenTest(TestCase):
	"""The Kontensalden of the taxonomy 6.10, Technischer Leitfaden zur HGB-Taxonomie 6.10, B.12.1 and B.12.2, as the
	structural errors 170195106 to 170195110 of Jahresdokumentation_Bilanz_Taxonomie_6_10.ods check them."""

	def test_a_report_with_a_kontensaldo_for_each_valued_position_without_one_below(self):
		self.assertEqual(kontensalden(), ())

	def test_170195106_a_valued_position_without_a_valued_one_below_has_a_kontensaldo(self):
		"""„Ein Kontennachweis ist für eine solche Position genau dann erforderlich, wenn sie selbst werthaltig ist und
		zu keiner rechnerisch verknüpften Unterposition ein Wert übermittelt wird.“; a total and a NIL position need
		none."""
		found = kontensalden(leaves=[leaf for leaf in LEAVES if leaf[0] != "bs.ass.fixAss.tan"])
		self.assertEqual(found, (("170195106", f"{A}bs.ass.fixAss.tan"),))
		self.assertEqual(
			kontensalden(kontensaldo("bs.ass.fixAss.tan", "40", None), leaves=LEAVES[:1] + LEAVES[2:]), ()
		)

	def test_170195106_asks_nothing_while_the_kontensalden_are_not_announced(self):
		"""Rule 170405002 says then that the component is missing."""
		self.assertEqual(kontensalden(leaves=(), elements=("B", "GuV", "BVV")), ())

	def test_170195107_leaves_the_tables_of_a_betrieb_gewerblicher_art_to_eric(self):
		"""170195107 asks the Kontensalden of the positions of a Betrieb gewerblicher Art or wirtschaftlicher
		Geschäftsbetrieb in the hypercubes of the steuerliche Gewinnermittlung für besondere Fälle, which a GmbH does
		not send: a valued fact with members is no position of Bilanz and GuV of its own."""
		dimensions = (TAX_BALANCE, (f"{A}dim_changes.nt.ass.gross", f"{A}bs.ass.fixAss.tan"))
		self.assertEqual(kontensalden(euros("all", "40", WJ, dimensions)), ())

	def test_170195108_one_kontensaldo_without_account_information_at_most(self):
		"""„Das Tupel „Kontensalden zu einer Position“ mit der Variante ohne Konteninformationen darf maximal einmal zu
		einer Position übermittelt werden.“"""
		found = kontensalden(
			kontensaldo("bs.ass.currAss.cashEquiv.bank", "1", None),
			kontensaldo("bs.ass.currAss.cashEquiv.bank", "2", None),
		)
		self.assertEqual(found, (("170195108", f"{A}bs.ass.currAss.cashEquiv.bank"),))
		self.assertEqual(kontensalden(kontensaldo("bs.ass.currAss.cashEquiv.bank", "1", None)), ())

	def test_170195109_outside_bilanz_and_guv_not_only_one_without_account_information(self):
		"""„Das Tupel „Kontensalden zu einer Position“ in der Variante ohne Konteninformationen darf nicht als das einzige
		Tupel zu einer Position übermittelt werden.“ for another component (B.12.2)."""
		found = kontensalden(kontensaldo("BVV.profitLoss", "45", None))
		self.assertEqual(found, (("170195109", f"{A}BVV.profitLoss"),))
		self.assertEqual(
			kontensalden(kontensaldo("BVV.profitLoss", "40"), kontensaldo("BVV.profitLoss", "5", None)), ()
		)

	def test_170195110_no_account_information_in_a_kontensaldo_without_an_account(self):
		"""„In der in Ausnahmefällen anwendbaren Variante ohne Konteninformationen dürfen die Elemente „Kontonummer“ ...
		und „Kontobeschreibung“ ... nicht werthaltig übermittelt werden“."""
		found = kontensalden(kontensaldo("bs.eqLiab.liab.bank", "1", ("3150", "Darlehen"), flag=True))
		self.assertEqual(found, (("170195110", f"{A}bs.eqLiab.liab.bank"),))

	def test_each_finding_names_its_rule_and_holds_the_report_back(self):
		report_ = report_6_10(*(kontensaldo(position, value) for position, value in LEAVES[1:]))
		view = mini.view(View.FISCAL, mini.VERSION_6_10)
		(finding,) = checks.kontensalden(report_, view, Facets.of(report_))
		self.assertEqual(finding.severity, Severity.ERROR)
		self.assertIn("Konzessionen", finding.text)
		self.assertIn("B.12.1", finding.source)
		self.assertIn("170195106", finding.source)

	def test_the_taxonomy_6_9_has_no_such_rules(self):
		"""6.9 asks one Kontensaldo for Bilanz and GuV each (structural error 170195104), which the E-Bilanz checks
		itself (steuerbote/ebilanz/kontennachweis.py)."""
		report_ = complete(elements=("B", "GuV", "BVV", "KS"))

		self.assertEqual(checks.kontensalden(report_, mini.view(), Facets.of(report_)), ())
