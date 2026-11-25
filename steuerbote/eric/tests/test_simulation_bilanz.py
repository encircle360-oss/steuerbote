"""The rules of the simulation of the E-Bilanz on the invented GmbH of steuerbote/ebilanz: the rules of „Kontext -
Regeln“ of Jahresdokumentation_Bilanz_Taxonomie_6_9.ods, the Anlagenspiegel, and with the mini taxonomy the
components, the Mussfelder and the calculation linkbase."""

from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from unittest import TestCase
from xml.etree import ElementTree

from lxml import etree

from steuerbote.ebilanz.anlagenspiegel import Row, ValueType
from steuerbote.ebilanz.instance import Sources, build
from steuerbote.ebilanz.positions import structure
from steuerbote.ebilanz.tests.taxonomy import view, view_6_10
from steuerbote.ebilanz.tests.test_calculation import case
from steuerbote.ebilanz.tests.test_gcd import MASTER, OPENING
from steuerbote.ebilanz.tests.test_instance import EQUITY, OPENING_BOOKS, SOURCES, built
from steuerbote.ebilanz.tests.test_ueberleitung import ACCRUAL, HANDELSBILANZ, SALES
from steuerbote.ebilanz.tests.test_ueberleitung import SOFTWARE as SELFMADE
from steuerbote.elster import ebilanz_xml
from steuerbote.eric.fake import Simulation
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import ERROR, HINT, Operation
from steuerbote.eric.simulation import bilanz
from steuerbote.kst.years import RuleExpectation

D = Decimal
GCD = "{http://www.xbrl.de/taxonomies/de-gcd-2025-04-01}"
GAAP = "{http://www.xbrl.de/taxonomies/de-gaap-ci-2025-04-01}"
XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"
LINK = "{http://www.xbrl.org/2003/linkbase}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
ELEMENTS = "genInfo.report.id.reportElement.reportElements"
DATENLIEFERANT = "Beispiel Werkstatt GmbH; Musterweg; 12; a; ; 12345; Musterstadt; Deutschland; ; "
HEADER = EnvelopeHeader(
	hersteller_id="00000",
	datenlieferant="Beispiel Werkstatt GmbH",
	produkt_name="Steuerbote",
	produkt_version="0.1.0",
	empfaenger="9198",
	datenart_version="Bilanz_6.9",
	testmerker=None,
	nutzdaten_ticket="1",
	nutzdaten_datenlieferant=DATENLIEFERANT,
)
HB, UE = ValueType.HANDELSBILANZ, ValueType.UEBERLEITUNG
HANDELSBILANZ_ASSETS = (
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
)
EINHEITSBILANZ = ebilanz_xml.to_nutzdaten(built())
EROEFFNUNGSBILANZ = ebilanz_xml.to_nutzdaten(
	built(sources=Sources(OPENING_BOOKS, first_year=True), statement_type="EB", periods=OPENING)
)
HANDELSBILANZ_NUTZDATEN = ebilanz_xml.to_nutzdaten(
	built(
		sources=Sources(
			HANDELSBILANZ, assets=HANDELSBILANZ_ASSETS, transfers=(SELFMADE, SALES, ACCRUAL), equity=EQUITY
		),
		accounting_standard="HGBM",
	)
)

type Edit = Callable[[etree._Element], None]


def errors(text: str, header: EnvelopeHeader = HEADER) -> list[tuple[str, str | None]]:
	result = Simulation().run(Operation.VALIDATE, text, header)
	return [(message.code, message.field) for message in result.messages if message.severity == ERROR]


def codes(text: str, header: EnvelopeHeader = HEADER) -> list[str]:
	return [code for code, _ in errors(text, header)]


def changed(text: str, *edits: Edit) -> str:
	root = etree.fromstring(text.encode("utf-8"))
	for edit in edits:
		edit(root)
	return etree.tostring(root, encoding="unicode")


def first(root: etree._Element, name: str, module: str = GCD) -> etree._Element:
	return next(root.iter(f"{module}{name}"))


def removed(name: str, module: str = GCD) -> Edit:
	def edit(root: etree._Element) -> None:
		for found in list(root.iter(f"{module}{name}")):
			found.getparent().remove(found)

	return edit


def emptied(name: str, module: str = GCD) -> Edit:
	"""The position as NIL, a tuple with its items NIL."""

	def edit(root: etree._Element) -> None:
		found = first(root, name, module)
		items = [found] if len(found) == 0 else [item for item in found.iter() if len(item) == 0]
		for item in items:
			item.text = None
			item.set(NIL, "true")
			item.attrib.pop("decimals", None)

	return edit


def valued(name: str, text: str, module: str = GCD) -> Edit:
	def edit(root: etree._Element) -> None:
		found = first(root, name, module)
		found.attrib.pop(NIL, None)
		found.text = text

	return edit


def amount(name: str, value: str) -> Edit:
	"""An amount of the GAAP module in the current year."""

	def edit(root: etree._Element) -> None:
		found = next(
			found
			for found in root.iter(f"{GAAP}{name}")
			if found.get("contextRef") in ("I-AKTJAHR", "D-AKTJAHR")
		)
		found.attrib.pop(NIL, None)
		found.set("decimals", "2")
		found.text = value

	return edit


def renamed(old: str, new: str, module: str = GCD) -> Edit:
	def edit(root: etree._Element) -> None:
		first(root, old, module).tag = f"{module}{new}"

	return edit


def stichtag(text: str) -> Edit:
	def edit(root: etree._Element) -> None:
		root[0].text = text

	return edit


def closing(day: str) -> Edit:
	"""The Bilanzstichtag of the GCD and the stichtag of the frame."""

	def edit(root: etree._Element) -> None:
		valued("genInfo.report.period.balSheetClosingDate", day)(root)
		stichtag(day.replace("-", ""))(root)

	return edit


class ValidTest(TestCase):
	def test_the_e_bilanzen_of_steuerbote_keep_every_rule(self):
		for name, text in (
			("Einheitsbilanz", EINHEITSBILANZ),
			("Eröffnungsbilanz", EROEFFNUNGSBILANZ),
			("Handelsbilanz", HANDELSBILANZ_NUTZDATEN),
			("UG", ebilanz_xml.to_nutzdaten(built(legal_form="UG"))),
		):
			with self.subTest(name=name):
				self.assertEqual(errors(text), [])

	def test_says_what_it_checks_without_the_taxonomy(self):
		result = Simulation().run(Operation.VALIDATE, EINHEITSBILANZ, HEADER)
		(hint,) = (message for message in result.messages if message.code == "SIM-001")
		self.assertEqual(hint.severity, HINT)
		self.assertIn("ohne die HGB-Taxonomie 6.9", hint.text)
		self.assertIn("Tabelle 9-20", hint.text)


class GcdRulesTest(TestCase):
	def test_the_gcd_gives_the_positions_the_rules_ask_for(self):
		for code, edit in (
			("170205045", removed("genInfo.report.id.revisionStatus")),
			("170205046", removed("genInfo.report.id.consolidationRange")),
			("170205047", removed("genInfo.report.id.incomeStatementendswithBalProfit")),
			("170205048", emptied("genInfo.report.period.balSheetClosingDate")),
			("170205070", emptied("genInfo.report.period.fiscalYearBegin")),
			("170205071", emptied("genInfo.report.period.fiscalYearEnd")),
			("170205049", removed("genInfo.company.id.name")),
			("170205051", emptied("genInfo.company.id.location.city")),
			("170205052", emptied("genInfo.company.id.location.zipCode")),
			("170205053", emptied("genInfo.company.id.location.street")),
			("170405036", removed("genInfo.company.id.incomeClassification")),
		):
			with self.subTest(code=code):
				self.assertIn(code, codes(changed(EINHEITSBILANZ, edit)))

	def test_names_the_rule_and_the_field_in_its_message(self):
		result = Simulation().run(
			Operation.VALIDATE, changed(EINHEITSBILANZ, removed("genInfo.company.id.name")), HEADER
		)
		(error,) = (message for message in result.messages if message.severity == ERROR)
		self.assertEqual(error.field, "genInfo.company.id.name")
		self.assertTrue(
			error.text.startswith(
				"Die Regel 170205049 (FehlendeAngabeUnternehmensname) der Jahresdokumentation Bilanz 6.9 schlägt an:"
			)
		)

	def test_the_steuernummer_and_its_finanzamt(self):
		"""Rules 170205025, 170205026 and 170205001; a Sonderbilanz takes them from the Gesamthand."""
		without = changed(EINHEITSBILANZ, emptied("genInfo.company.id.idNo.type.companyId.ST13"))
		self.assertEqual(errors(without), [("170205025", "genInfo.company.id.idNo.type.companyId.ST13")])
		opening = changed(
			EROEFFNUNGSBILANZ,
			emptied("genInfo.company.id.idNo.type.companyId.ST13"),
			emptied("genInfo.company.id.idNo.type.companyId.BF4"),
		)
		self.assertEqual(codes(opening), ["170205026"])
		named = changed(EROEFFNUNGSBILANZ, emptied("genInfo.company.id.idNo.type.companyId.ST13"))
		self.assertEqual(codes(named), [])
		self.assertEqual(codes(EINHEITSBILANZ, replace(HEADER, empfaenger="9199")), ["170205001"])
		special = changed(without, special_balance)
		self.assertEqual(codes(special, replace(HEADER, empfaenger="9199")), [])

	def test_the_stichtag_of_the_frame_is_the_bilanzstichtag(self):
		"""Rule 170205022; Leitfaden B.2.2."""
		self.assertEqual(codes(changed(EINHEITSBILANZ, stichtag("20261230"))), ["170205022"])

	def test_the_bilanzstichtag_by_the_bilanzart(self):
		"""Rules 170205072 and 170205081; Leitfaden B.14.3.1.6. The contexts of another day are of no current year,
		so the amounts go missing as well."""
		self.assertIn("170205072", codes(changed(EINHEITSBILANZ, closing("2026-12-30"))))
		self.assertIn("170205081", codes(changed(EROEFFNUNGSBILANZ, closing("2026-03-02"))))
		self.assertNotIn("170205081", codes(changed(EINHEITSBILANZ, closing("2026-12-30"))))

	def test_the_fiscal_years_of_the_version(self):
		"""Rules 170205007, 170205018 and 170205017; Leitfaden B.18."""
		early = changed(EINHEITSBILANZ, valued("genInfo.report.period.fiscalYearBegin", "2024-12-31"))
		self.assertIn("170205007", codes(early))
		liquidation = changed(
			early,
			renamed(
				"genInfo.report.id.statementType.statementType.E",
				"genInfo.report.id.statementType.statementType.LSB",
			),
		)
		self.assertNotIn("170205007", codes(liquidation))
		late = changed(EINHEITSBILANZ, valued("genInfo.report.period.fiscalYearEnd", "2027-12-31"))
		self.assertIn("170205018", codes(late))
		self.assertNotIn(
			"170205018",
			codes(changed(EINHEITSBILANZ, valued("genInfo.report.period.fiscalYearEnd", "2027-12-30"))),
		)
		opening = changed(EROEFFNUNGSBILANZ, valued("genInfo.report.period.fiscalYearEnd", "2027-12-31"))
		self.assertEqual(codes(opening), [])
		self.assertIn(
			"170205017",
			codes(changed(EROEFFNUNGSBILANZ, valued("genInfo.report.period.fiscalYearEnd", "2028-12-31"))),
		)
		self.assertNotIn("170205007", codes(early, replace(HEADER, datenart_version="Bilanz_6.11")))


def special_balance(root: etree._Element) -> None:
	"""A Sonderbilanz of a partnership: statementType.tax with the value SB."""
	tuple_ = etree.SubElement(root[1], f"{GCD}genInfo.report.id.statementType.tax")
	etree.SubElement(
		tuple_, f"{GCD}genInfo.report.id.statementType.tax.statementTypeTax.SB", contextRef="D-AKTJAHR"
	)


def chosen(tuple_name: str, value: str) -> Edit:
	"""A choice that reports another value, by the last part of its name."""

	def edit(root: etree._Element) -> None:
		found = first(root, tuple_name)
		(child,) = list(found)
		child.tag = f"{GCD}{tuple_name}.{value}"

	return edit


def added_choice(tuple_name: str, value: str) -> Edit:
	def edit(root: etree._Element) -> None:
		tuple_ = etree.SubElement(root[1], f"{GCD}{tuple_name}")
		etree.SubElement(tuple_, f"{GCD}{tuple_name}.{value}", contextRef="D-AKTJAHR")

	return edit


class ComponentRulesTest(TestCase):
	def test_the_components_by_the_bilanzart(self):
		"""Leitfaden B.14.3.1.10; rules 170205090, 170205091, 170405021, 170205021, 170405101 and 170205028."""
		for code, text in (
			("170205090", changed(EINHEITSBILANZ, emptied(f"{ELEMENTS}.B"))),
			("170205091", changed(EINHEITSBILANZ, emptied(f"{ELEMENTS}.GuV"))),
			("170405021", changed(EROEFFNUNGSBILANZ, emptied(f"{ELEMENTS}.B"))),
			("170205021", changed(EROEFFNUNGSBILANZ, valued(f"{ELEMENTS}.GuV", ""))),
			("170405101", changed(EROEFFNUNGSBILANZ, valued(f"{ELEMENTS}.BVV", ""))),
			("170205028", changed(EINHEITSBILANZ, valued(f"{ELEMENTS}.EB", ""))),
		):
			with self.subTest(code=code):
				self.assertIn(code, codes(text))
		self.assertEqual(
			codes(changed(EROEFFNUNGSBILANZ, emptied(f"{ELEMENTS}.B"), valued(f"{ELEMENTS}.EB", ""))), []
		)

	def test_a_koerperschaft_with_tables_of_its_betriebe_has_no_bilanz_of_its_own(self):
		"""Rules 170205090, 170205091, 170405021, 170205011 and 170205012 leave the Übermittlungsvariante aside."""
		tables = added_choice(
			"genInfo.company.id.transmissionOptionofCorpWithSpecialCaseProfitDetermination",
			"taxablePurposeBusinessTable",
		)
		text = changed(
			EINHEITSBILANZ,
			emptied(f"{ELEMENTS}.B"),
			emptied(f"{ELEMENTS}.GuV"),
			removed("bs.ass", GAAP),
			removed("bs.eqLiab", GAAP),
			tables,
		)
		for code in ("170205090", "170205091", "170205011", "170205012"):
			with self.subTest(code=code):
				self.assertNotIn(code, codes(text))

	def test_the_betriebsvermoegensvergleich_comes_with_every_guv(self):
		"""Rule 170205066; Leitfaden B.14.3.1.10."""
		self.assertEqual(codes(changed(EINHEITSBILANZ, emptied(f"{ELEMENTS}.BVV"))), ["170205066"])

	def test_without_kontensalden_the_gcd_says_why(self):
		"""Rule 170405002; Leitfaden B.12."""
		without = changed(EINHEITSBILANZ, emptied(f"{ELEMENTS}.KS"))
		self.assertEqual(codes(without), ["170405002"])
		self.assertEqual(
			codes(changed(without, valued(f"{ELEMENTS}.transmissionNotYetPossible", "Grund"))), []
		)

	def test_the_ueberleitung_of_a_handelsbilanz_only(self):
		"""Rules 170205095 and 170205100; Leitfaden B.15.1, B.16.1."""
		self.assertEqual(codes(changed(EINHEITSBILANZ, valued(f"{ELEMENTS}.STU", ""))), ["170205095"])
		without = changed(HANDELSBILANZ_NUTZDATEN, removed("hbst.transfer", GAAP))
		self.assertIn("170205100", codes(without))


class AmountRulesTest(TestCase):
	def test_summe_aktiva_and_summe_passiva(self):
		"""Rules 170205011, 170205012 and 170205010; Leitfaden B.14.3.2.2."""
		self.assertIn("170205011", codes(changed(EINHEITSBILANZ, removed("bs.ass", GAAP))))
		self.assertIn("170205012", codes(changed(EINHEITSBILANZ, removed("bs.eqLiab", GAAP))))
		self.assertEqual(codes(changed(EINHEITSBILANZ, amount("bs.ass", "110000.00"))), ["170205010"])
		self.assertIn("170205011", codes(changed(EINHEITSBILANZ, amount("bs.ass", "NaN"))))
		self.assertIn("170205011", codes(changed(EINHEITSBILANZ, amount("bs.ass", "viel"))))

	def test_the_jahresueberschuss_of_the_guv_is_that_of_the_bilanz(self):
		"""Rules 170405070 and 170405071; Leitfaden B.14.3.2.3.4.1."""
		text = changed(EINHEITSBILANZ, amount("bs.eqLiab.equity.netIncome", "39000.00"))
		self.assertIn("170405070", codes(text))
		for exempt in (
			chosen("genInfo.company.id.legalStatus", "legalStatus.AG"),
			valued("genInfo.report.id.incomeStatementendswithBalProfit", "true"),
			added_choice("genInfo.company.id.entityWithTaxablePurposeBusiness", "normal"),
		):
			with self.subTest(exempt=exempt):
				self.assertNotIn("170405070", codes(changed(text, exempt)))
		before = changed(HANDELSBILANZ_NUTZDATEN, amount("bs.eqLiab.equity.netIncome", "44000.00"))
		self.assertIn("170405071", codes(before))
		self.assertNotIn("170405071", codes(text))

	def test_the_betriebsvermoegensvergleich(self):
		"""Rules 170405109 and 170405114; Leitfaden B.14.3.2.12."""
		self.assertEqual(codes(changed(EINHEITSBILANZ, amount("BVV.profitLoss", "39000.00"))), ["170405109"])
		self.assertEqual(
			codes(changed(EINHEITSBILANZ, amount("BVV.profitLoss.assetsCurrentYear", "67000.00"))),
			["170405114"],
		)

	def test_the_amounts_of_a_handelsbilanz_are_those_after_the_ueberleitung(self):
		"""Leitfaden B.15.1: the Betriebsvermögensvergleich of the invented Handelsbilanz has the 41.000 € of its
		Steuerbilanz, while the GuV shows 45.000 €."""
		self.assertEqual(
			bilanz.read(etree_root(HANDELSBILANZ_NUTZDATEN)).amount("is.netIncome"), D("41000.00")
		)
		self.assertEqual(
			bilanz.read(etree_root(HANDELSBILANZ_NUTZDATEN)).amount("is.netIncome", transferred=False),
			D("45000.00"),
		)

	def test_a_branch_of_its_own_leaves_the_rules_on_its_totals_aside(self):
		"""The Prüfbedingungen ask for the branches „Keine“ or „Sonstige“; banks, payment institutions and insurers
		report totals of their own (Leitfaden B.14.3.1.13)."""
		text = changed(
			EINHEITSBILANZ,
			amount("bs.ass", "110000.00"),
			amount("BVV.profitLoss", "1.00"),
			amount("bs.eqLiab.equity.netIncome", "1.00"),
			chosen("genInfo.report.id.specialAccountingStandard", "RKV"),
		)
		self.assertEqual(codes(text), [])


def etree_root(text: str) -> ElementTree.Element:
	return ElementTree.fromstring(text)


class AnlagenspiegelTest(TestCase):
	def test_the_anlagenspiegel_is_due(self):
		"""Leitfaden B.14.12.1; BMF letter of 10 June 2025; rule 170405045 is deleted in the Jahresdokumentation 6.9."""

		def without_anlagenspiegel(root: etree._Element) -> None:
			for found in [
				found for found in root[1] if (found.get("contextRef") or "").startswith("D-AKTJAHR-")
			]:
				root[1].remove(found)

		text = changed(EINHEITSBILANZ, without_anlagenspiegel)
		self.assertEqual(errors(text), [("SIM-011", "dim_changes.nt.ass.gross")])
		self.assertEqual(codes(changed(text, emptied(f"{ELEMENTS}.B"))), ["170205090"])
		bank = chosen("genInfo.report.id.specialAccountingStandard", "RKV")
		self.assertEqual(codes(changed(text, bank)), [])
		old = changed(text, valued("genInfo.report.period.fiscalYearBegin", "2016-12-31"))
		self.assertNotIn("SIM-011", codes(old))

	def test_the_kurzform_is_not_admitted(self):
		"""Rule 170405047; Leitfaden B.14.12.1."""

		def short(root: etree._Element) -> None:
			for member in root.iter(f"{XBRLDI}explicitMember"):
				if member.get("dimension") == "de-gaap-ci:dim_changes.nt.ass.gross":
					member.set("dimension", "de-gaap-ci:dim_changes.nt.ass.gross_short")
					return

		self.assertEqual(
			errors(changed(EINHEITSBILANZ, short)), [("170405047", "dim_changes.nt.ass.gross_short")]
		)


class TaxonomyTest(TestCase):
	"""With the mini taxonomy registered for 6.9."""

	def setUp(self):
		bilanz.register_taxonomy("6.9", view)
		self.addCleanup(bilanz.unregister_taxonomy, "6.9")

	def test_the_e_bilanzen_of_steuerbote_pass(self):
		for text in (EINHEITSBILANZ, EROEFFNUNGSBILANZ, HANDELSBILANZ_NUTZDATEN):
			with self.subTest(text=text[:40]):
				self.assertEqual(errors(text), [])
		result = Simulation().run(Operation.VALIDATE, EINHEITSBILANZ, HEADER)
		(hint,) = (message for message in result.messages if message.code == "SIM-001")
		self.assertIn("mit der HGB-Taxonomie 6.9 die Mussfelder und die Rechenregeln", hint.text)

	def test_finds_a_missing_mussfeld(self):
		"""steuerbote.xbrl.checks.mussfelder(); Leitfaden B.14.2."""
		self.assertEqual(
			errors(changed(EINHEITSBILANZ, removed("genInfo.company.id.shareholder"))),
			[("XBRL-MUSSFELD", "de-gcd:genInfo.company.id.shareholder")],
		)

	def test_a_choice_nil_as_a_whole_is_no_fact(self):
		"""ERiC 44.3.6.0 refuses a Mussfeld whose tuple is NIL as a whole with rule 170155092, for it has no fact in a
		context of the current year (validation of Bilanz_6.9); the simulation is not more lenient."""

		def nil_as_a_whole(root: etree._Element) -> None:
			found = first(root, "genInfo.company.id.domesticBranchOfForeignCompany")
			for child in list(found):
				found.remove(child)
			found.set(NIL, "true")

		self.assertEqual(
			errors(changed(EINHEITSBILANZ, nil_as_a_whole)),
			[("XBRL-MUSSFELD", "de-gcd:genInfo.company.id.domesticBranchOfForeignCompany")],
		)

	def test_finds_a_wrong_sum_of_the_calculation_linkbase(self):
		"""steuerbote.xbrl.checks.calculation(); Leitfaden B.14.11."""
		((code, _),) = errors(changed(EINHEITSBILANZ, amount("bs.ass.fixAss", "41000.00")))
		self.assertEqual(code, "XBRL-RECHNUNG")

	def test_finds_an_announced_component_without_facts(self):
		"""steuerbote.xbrl.checks.components(); Leitfaden B.9.2."""
		self.assertEqual(
			errors(changed(EINHEITSBILANZ, removed("detailedInformation.accountBalances", GAAP))),
			[("XBRL-BERICHTSBESTANDTEIL", f"de-gcd:{ELEMENTS}.KS")],
		)

	def test_an_instance_it_cannot_read(self):
		for edit in (
			renamed("bs.ass", "bs.unknown", GAAP),
			amount("bs.ass.fixAss", "viel"),
			emptied("genInfo.report.period.fiscalYearBegin"),
			removed("context", XBRLI),
		):
			with self.subTest(edit=edit):
				self.assertIn("SIM-012", codes(changed(EINHEITSBILANZ, edit)))

	def test_reads_members_by_the_prefixes_of_the_taxonomy_and_leaves_typed_dimensions_out(self):
		def other_prefix(root: etree._Element) -> None:
			member = next(root.iter(f"{XBRLDI}explicitMember"))
			member.text = member.text.replace("de-gaap-ci:", "andere:")

		def typed(root: etree._Element) -> None:
			scenario = next(root.iter(f"{XBRLI}scenario"))
			typed_member = etree.SubElement(
				scenario, f"{XBRLDI}typedMember", dimension="de-gaap-ci:dim_betrieb"
			)
			etree.SubElement(typed_member, f"{GAAP}betrieb").text = "1"

		self.assertEqual(errors(changed(EINHEITSBILANZ, other_prefix)), [])
		self.assertNotIn("SIM-012", codes(changed(EINHEITSBILANZ, typed)))

	def test_checks_only_the_kerntaxonomie_of_its_version(self):
		def branch(root: etree._Element) -> None:
			for reference in root.iter(f"{LINK}schemaRef"):
				reference.set(
					XLINK_HREF, reference.get(XLINK_HREF).replace("shell-fiscal", "shell-fiscal-bra")
				)

		text = changed(EINHEITSBILANZ, removed("genInfo.company.id.shareholder"), branch)
		self.assertEqual(errors(text), [])


class ExpectedRulesTest(TestCase):
	def test_names_each_rule_with_the_terms_of_its_pruefbedingung(self):
		"""The year check compares them with „Kontext - Regeln“ (steuerbote/jahresmeldung/yearcheck.py)."""
		expected = bilanz.expected_rules("6.9")
		self.assertEqual([expectation.code for expectation in expected], [rule.code for rule in bilanz.RULES])
		self.assertTrue(all(isinstance(expectation, RuleExpectation) for expectation in expected))
		self.assertEqual({expectation.sheet for expectation in expected}, {"Kontext - Regeln"})
		terms = {expectation.code: expectation.terms for expectation in expected}
		self.assertEqual(
			terms["170205007"], ('[gcd:genInfo.report.period.fiscalYearBegin]<Datum("01","01","2025")',)
		)
		self.assertEqual(
			terms["170205018"], ('[gcd:genInfo.report.period.fiscalYearEnd]>Datum("30","12","2027")',)
		)
		self.assertEqual(
			terms["170205017"], ('[gcd:genInfo.report.period.fiscalYearEnd]>Datum("30","12","2028")',)
		)
		self.assertEqual(len(set(terms)), len(bilanz.RULES))


HEADER_6_10 = replace(HEADER, datenart_version="Bilanz_6.10")


class Taxonomy610RulesTest(TestCase):
	"""The rules of „Kontext - Regeln“ of Jahresdokumentation_Bilanz_Taxonomie_6_10.ods (ERiC documentation 45.1.5.0)
	that differ from those of 6.9, for an E-Bilanz of the Datenart Bilanz_6.10."""

	def test_the_fiscal_years_of_6_10(self):
		"""Rules 170205007, 170205018 and 170205017 of 6.10: „Version 6.10 der HGB-Taxonomie darf nur für
		Wirtschaftsjahre verwendet werden, die nach dem 31.12.2025 beginnen“, „die vor dem 31.12.2028 enden“, and an
		Eröffnungsbilanz „vor dem 31.12.2029“."""
		self.assertNotIn("170205007", codes(EINHEITSBILANZ, HEADER_6_10))
		early = changed(EINHEITSBILANZ, valued("genInfo.report.period.fiscalYearBegin", "2025-12-31"))
		self.assertIn("170205007", codes(early, HEADER_6_10))
		self.assertNotIn("170205007", codes(early))
		late = changed(EINHEITSBILANZ, valued("genInfo.report.period.fiscalYearEnd", "2028-12-31"))
		self.assertIn("170205018", codes(late, HEADER_6_10))
		in_time = changed(EINHEITSBILANZ, valued("genInfo.report.period.fiscalYearEnd", "2028-12-30"))
		self.assertNotIn("170205018", codes(in_time, HEADER_6_10))
		self.assertIn("170205018", codes(in_time))
		opening = changed(EROEFFNUNGSBILANZ, valued("genInfo.report.period.fiscalYearEnd", "2029-12-31"))
		self.assertIn("170205017", codes(opening, HEADER_6_10))
		opening_in_time = changed(
			EROEFFNUNGSBILANZ, valued("genInfo.report.period.fiscalYearEnd", "2029-12-30")
		)
		self.assertNotIn("170205017", codes(opening_in_time, HEADER_6_10))

	def test_6_10_takes_the_kontensalden_without_a_reason(self):
		"""Rule 170405002 of 6.10: „Der Berichtsbestandteil "Kontensalden" muss angekündigt werden, wenn der Beginn des
		Wirtschaftsjahres nach dem 31.12.2024 liegt.“; the reason of 6.9 counts no more."""
		without = changed(
			EINHEITSBILANZ,
			emptied(f"{ELEMENTS}.KS"),
			valued(f"{ELEMENTS}.transmissionNotYetPossible", "Grund"),
		)
		self.assertEqual(codes(without), [])
		self.assertEqual(codes(without, HEADER_6_10), ["170405002"])
		earlier = changed(without, valued("genInfo.report.period.fiscalYearBegin", "2024-12-31"))
		self.assertNotIn("170405002", codes(earlier, HEADER_6_10))
		self.assertIn("170205007", codes(earlier, HEADER_6_10))

	def test_names_the_terms_of_6_10(self):
		"""What the year check compares with Jahresdokumentation_Bilanz_Taxonomie_6_10.ods."""
		expected = {expectation.code: expectation.terms for expectation in bilanz.expected_rules("6.10")}
		self.assertEqual(list(expected), [rule.code for rule in bilanz.RULES])
		self.assertEqual(
			expected["170205007"], ('[gcd:genInfo.report.period.fiscalYearBegin]<Datum("01","01","2026")',)
		)
		self.assertEqual(
			expected["170205018"], ('[gcd:genInfo.report.period.fiscalYearEnd]>Datum("30","12","2028")',)
		)
		self.assertEqual(
			expected["170205017"], ('[gcd:genInfo.report.period.fiscalYearEnd]>Datum("30","12","2029")',)
		)
		self.assertEqual(
			expected["170405002"],
			(
				f"FeldNichtAngegeben(gcd:{ELEMENTS}.KS)",
				"FeldAngegeben(gcd:genInfo.report.period.fiscalYearBegin)",
				'[gcd:genInfo.report.period.fiscalYearBegin]>Datum("31","12","2024")',
			),
		)
		self.assertEqual(
			{expectation.code: expectation.terms for expectation in bilanz.expected_rules("6.9")}[
				"170405002"
			],
			(
				f"FeldNichtAngegeben(gcd:{ELEMENTS}.KS)",
				f"FeldNichtAngegeben(gcd:{ELEMENTS}.transmissionNotYetPossible)",
			),
		)


GAAP_6_10 = "{http://www.xbrl.de/taxonomies/de-gaap-ci-2026-04-01}"


class Taxonomy610Test(TestCase):
	"""With the mini taxonomy 6.10 registered for 6.10: the Kontensalden of an E-Bilanz of the Datenart Bilanz_6.10
	by the structural errors 170195106 to 170195110 of its Jahresdokumentation (steuerbote.xbrl.checks.kontensalden())."""

	@classmethod
	def setUpClass(cls):
		cls.nutzdaten = ebilanz_xml.to_nutzdaten(build(structure(view_6_10(), case()), MASTER, SOURCES))

	def setUp(self):
		bilanz.register_taxonomy("6.10", view_6_10)
		self.addCleanup(bilanz.unregister_taxonomy, "6.10")

	def test_the_e_bilanz_of_steuerbote_passes(self):
		self.assertEqual(errors(self.nutzdaten, HEADER_6_10), [])

	def test_170195106_a_valued_position_without_a_kontensaldo(self):
		"""The Jahresüberschuss of the Bilanz without its Kontensaldo without account information."""

		def without_the_last_kontensaldo(root: etree._Element) -> None:
			*_rest, last = root.iter(f"{GAAP_6_10}detailedInformation.accountBalances")
			last.getparent().remove(last)

		self.assertEqual(
			errors(changed(self.nutzdaten, without_the_last_kontensaldo), HEADER_6_10),
			[("170195106", "de-gaap-ci:bs.eqLiab.equity.netIncome")],
		)
