"""The GCD of the E-Bilanz of the invented GmbH: the company and the report from its master data and its case, NIL for
every other Mussfeld of a GmbH, and what the master data lack or get wrong."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.ebilanz.gcd import (
	COUNTRY,
	Gesellschafter,
	MasterData,
	check,
	entity,
	facts,
	gcd,
	gesellschafter,
)
from steuerbote.ebilanz.positions import structure
from steuerbote.ebilanz.tests.taxonomy import view
from steuerbote.ebilanz.tests.test_calculation import WITH_PRIOR, case
from steuerbote.jahresmeldung.corrections import RevisionStatus
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import Shareholder, ShareholderKind
from steuerbote.xbrl.checks import Severity
from steuerbote.xbrl.facts import Entity, Item, Period, Periods, Tuple

MASTER = MasterData(
	name="Beispiel Werkstatt GmbH",
	street="Musterweg",
	postal_code="12345",
	city="Musterstadt",
	steuernummer="9198011310010",
	house_number="12a",
	business="Reparatur von Fahrrädern",
)
OPENING = Periods(date(2026, 3, 1), date(2026, 12, 31), date(2026, 3, 1))
REPORT_ELEMENT = gcd("genInfo.report.id.reportElement")
ST13 = gcd("genInfo.company.id.idNo.type.companyId.ST13")
BF4 = gcd("genInfo.company.id.idNo.type.companyId.BF4")
NOT_YET_POSSIBLE = gcd("genInfo.report.id.reportElement.reportElements.transmissionNotYetPossible")
SHAREHOLDER = gcd("genInfo.company.id.shareholder")
WJ = Period.WIRTSCHAFTSJAHR


def of(master=MASTER, *, reason="", taxonomy=None, **fields):
	return facts(structure(taxonomy or view(), case(**fields)), master, reason=reason)


def checked(master=MASTER, *, reason="", taxonomy=None, **fields):
	return check(structure(taxonomy or view(), case(**fields)), master, reason=reason)


def by_concept(found) -> dict:
	return {fact.concept: fact for fact in found}


def values(fact: Tuple) -> list[tuple[str, object]]:
	return [(child.concept, child.value) for child in fact.children]


def chosen(name: str, *choices: str) -> list[tuple[str, object]]:
	return [(gcd(f"{name}.{value}"), "") for value in choices]


def codes(found) -> list[str]:
	return [finding.code for finding in found]


class CompanyTest(TestCase):
	def test_names_the_company_and_its_firmensitz_in_germany(self):
		"""Leitfaden B.14.3.1.16; a GmbH has its Sitz in Germany (§ 4a GmbHG)."""
		found = by_concept(of())
		for name, value in (
			("genInfo.company.id.name", "Beispiel Werkstatt GmbH"),
			("genInfo.company.id.location.street", "Musterweg"),
			("genInfo.company.id.location.houseNo", "12a"),
			("genInfo.company.id.location.zipCode", "12345"),
			("genInfo.company.id.location.city", "Musterstadt"),
			("genInfo.company.id.location.country", COUNTRY),
			("genInfo.company.id.business", "Reparatur von Fahrrädern"),
		):
			with self.subTest(name):
				self.assertEqual(found[gcd(name)], Item(gcd(name), Period.WIRTSCHAFTSJAHR, value))
		self.assertEqual(COUNTRY, "Deutschland")

	def test_states_the_legal_status_of_a_gmbh_or_an_ug_and_income_from_trade(self):
		"""Leitfaden B.4.1, B.14.3.1.17; B.14.3.1.9 and rule 170405037."""
		found = by_concept(of())
		self.assertEqual(
			values(found[gcd("genInfo.company.id.legalStatus")]),
			chosen("genInfo.company.id.legalStatus", "legalStatus.GMBH"),
		)
		self.assertEqual(
			values(by_concept(of(legal_form="UG"))[gcd("genInfo.company.id.legalStatus")]),
			chosen("genInfo.company.id.legalStatus", "legalStatus.UG"),
		)
		self.assertEqual(
			values(found[gcd("genInfo.company.id.incomeClassification")]),
			chosen("genInfo.company.id.incomeClassification", "trade"),
		)

	def test_names_the_steuernummer_and_the_finanzamt_it_belongs_to(self):
		"""Leitfaden B.14.3.1.18 and B.2.1: the Bundesfinanzamtsnummer is the first four digits of the
		Steuernummer, as in the GmbH example of the ERiC documentation."""
		found = by_concept(of())
		self.assertEqual(
			values(found[gcd("genInfo.company.id.idNo")]), [(ST13, "9198011310010"), (BF4, "9198")]
		)
		self.assertEqual(MASTER.finanzamt, "9198")

	def test_takes_the_texts_in_the_characters_of_elster(self):
		master = replace(MASTER, name="\N{DOUBLE LOW-9 QUOTATION MARK}Rad\N{LEFT DOUBLE QUOTATION MARK} GmbH")
		self.assertEqual(by_concept(of(master))[gcd("genInfo.company.id.name")].value, '"Rad" GmbH')

	def test_sends_the_house_number_and_the_business_nil_where_the_settings_have_none(self):
		"""Leitfaden B.14.3.1.16: „Die Angabe „Firmensitz, Hausnummer“ ... kann auch „leer“ übermittelt werden.“"""
		found = by_concept(of(replace(MASTER, house_number="", business=" ")))
		self.assertTrue(found[gcd("genInfo.company.id.location.houseNo")].nil)
		self.assertTrue(found[gcd("genInfo.company.id.business")].nil)

	def test_the_company_in_the_contexts_is_its_steuernummer(self):
		"""Leitfaden B.14.7; the scheme of the ERiC examples."""
		self.assertEqual(entity(MASTER), Entity.steuernummer("9198011310010"))
		self.assertIsNone(entity(replace(MASTER, steuernummer=None, bundesfinanzamtsnummer="9198")))
		self.assertIsNone(entity(replace(MASTER, steuernummer="919801131001")))


class ReportTest(TestCase):
	def test_reports_a_final_first_jahresabschluss_of_a_gmbh(self):
		"""Leitfaden B.14.3.1.1 to B.14.3.1.3, B.14.3.1.7, B.14.3.1.8, B.14.3.1.12 to B.14.3.1.15."""
		found = by_concept(of())
		for name, value in (
			("genInfo.report.id.reportStatus", "reportStatus.E"),
			("genInfo.report.id.revisionStatus", "revisionStatus.E"),
			("genInfo.report.id.statementType", "statementType.E"),
			("genInfo.report.id.accountingStandard", "accountingStandard.HAOE"),
			("genInfo.report.id.specialAccountingStandard", "K"),
			("genInfo.report.id.incomeStatementFormat", "incomeStatementFormat.GKV"),
			("genInfo.report.id.consolidationRange", "consolidationRange.EA"),
		):
			with self.subTest(name):
				self.assertEqual(values(found[gcd(name)]), chosen(name, value))
		self.assertEqual(
			found[gcd("genInfo.report.id.incomeStatementendswithBalProfit")],
			Item(gcd("genInfo.report.id.incomeStatementendswithBalProfit"), Period.WIRTSCHAFTSJAHR, False),
		)

	def test_a_berichtigung_states_how_it_corrects(self):
		"""Leitfaden B.14.3.1.2; FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d."""
		found = by_concept(of(replace(MASTER, revision_status=RevisionStatus.CORRECTED)))
		self.assertEqual(
			values(found[gcd("genInfo.report.id.revisionStatus")]),
			chosen("genInfo.report.id.revisionStatus", "revisionStatus.B"),
		)

	def test_names_the_accounting_standard_of_a_handelsbilanz(self):
		found = by_concept(of(accounting_standard="HGBM"))
		self.assertEqual(
			values(found[gcd("genInfo.report.id.accountingStandard")]),
			chosen("genInfo.report.id.accountingStandard", "accountingStandard.HGBM"),
		)

	def test_states_the_day_it_was_written(self):
		found = by_concept(of(replace(MASTER, generated=date(2027, 5, 3))))
		self.assertEqual(found[gcd("genInfo.doc.id.generationDate")].value, date(2027, 5, 3))
		self.assertNotIn(gcd("genInfo.doc.id.generationDate"), by_concept(of()))


class ReportElementsTest(TestCase):
	def test_announces_the_components_of_the_case_and_sends_the_other_mussfelder_nil(self):
		"""Leitfaden A.10.1 and B.14.3.1.10; the GmbH example of the ERiC documentation sends EB, EV and KS NIL. The
		Steuerliche Gewinnermittlung is no Mussfeld of a GmbH, so it is not sent (FAQ zur E-Bilanz, Tz. 4 a)."""
		found = by_concept(of())
		element = "genInfo.report.id.reportElement.reportElements"
		self.assertEqual(
			values(found[REPORT_ELEMENT]),
			[
				*chosen(element, "B", "GuV", "BVV", "BAL", "KS"),
				(gcd(f"{element}.STU"), None),
				(gcd(f"{element}.EB"), None),
				(gcd(f"{element}.EV"), None),
			],
		)

	def test_a_handelsbilanz_announces_its_ueberleitung(self):
		"""Leitfaden B.15.1, rule 170205100."""
		found = by_concept(of(accounting_standard="HGBM"))
		self.assertIn(
			(gcd("genInfo.report.id.reportElement.reportElements.STU"), ""), values(found[REPORT_ELEMENT])
		)

	def test_without_kontensalden_the_gcd_says_why(self):
		"""BMF letter of 10 June 2025; Leitfaden B.12; rule 170405002."""
		found = by_concept(
			of(
				reason="Die Kontennachweise folgen \N{EN DASH} wie besprochen \N{EN DASH} auf Papier.",
				kontennachweis=False,
			)
		)
		self.assertIn(
			(gcd("genInfo.report.id.reportElement.reportElements.KS"), None), values(found[REPORT_ELEMENT])
		)
		self.assertEqual(
			found[NOT_YET_POSSIBLE],
			Item(
				NOT_YET_POSSIBLE,
				Period.WIRTSCHAFTSJAHR,
				"Die Kontennachweise folgen - wie besprochen - auf Papier.",
			),
		)

	def test_with_kontensalden_the_reason_is_nil(self):
		"""Rule 170405024 hints at Kontensalden announced with a reason."""
		self.assertTrue(by_concept(of(reason="Grund"))[NOT_YET_POSSIBLE].nil)
		self.assertTrue(by_concept(of(kontennachweis=False))[NOT_YET_POSSIBLE].nil)

	def test_an_eroeffnungsbilanz_announces_the_bilanz_without_guv_and_betriebsvermoegensvergleich(self):
		"""Leitfaden B.14.3.1.10, rules 170405021, 170205021 and 170405101; B.14.3.1.6, rule 170205081."""
		found = by_concept(of(statement_type="EB", periods=OPENING))
		element = "genInfo.report.id.reportElement.reportElements"
		self.assertEqual(
			values(found[REPORT_ELEMENT]),
			[
				*chosen(element, "B", "BAL", "KS"),
				(gcd(f"{element}.GuV"), None),
				(gcd(f"{element}.BVV"), None),
				(gcd(f"{element}.STU"), None),
				(gcd(f"{element}.EB"), None),
				(gcd(f"{element}.EV"), None),
			],
		)
		self.assertEqual(
			values(found[gcd("genInfo.report.id.statementType")]),
			chosen("genInfo.report.id.statementType", "statementType.EB"),
		)
		self.assertEqual(found[gcd("genInfo.report.period.balSheetClosingDate")].value, date(2026, 3, 1))
		self.assertFalse(found[gcd("genInfo.report.id.incomeStatementendswithBalProfit")].value)


class PeriodsTest(TestCase):
	def test_states_the_fiscal_year_and_its_bilanzstichtag(self):
		"""Leitfaden B.14.3.1.4 and B.14.3.1.6; rules 170205048, 170205070 and 170205071."""
		found = by_concept(of())
		self.assertEqual(found[gcd("genInfo.report.period.fiscalYearBegin")].value, date(2026, 1, 1))
		self.assertEqual(found[gcd("genInfo.report.period.fiscalYearEnd")].value, date(2026, 12, 31))
		self.assertEqual(found[gcd("genInfo.report.period.balSheetClosingDate")].value, date(2026, 12, 31))

	def test_sends_the_previous_fiscal_year_nil_in_the_first(self):
		found = by_concept(of())
		for name in ("fiscalPreviousYearBegin", "fiscalPreviousYearEnd", "balSheetClosingDatePreviousYear"):
			with self.subTest(name):
				self.assertTrue(found[gcd(f"genInfo.report.period.{name}")].nil)

	def test_names_the_previous_fiscal_year_of_the_master_data_or_of_a_handelsbilanz(self):
		"""Leitfaden B.14.3.1.5 and B.14.3.1.6."""
		previous = (date(2025, 1, 1), date(2025, 12, 31))
		for found in (
			by_concept(of(replace(MASTER, previous_fiscal_year=previous))),
			by_concept(of(accounting_standard="HGBM", periods=WITH_PRIOR)),
		):
			self.assertEqual(
				found[gcd("genInfo.report.period.fiscalPreviousYearBegin")].value, date(2025, 1, 1)
			)
			self.assertEqual(
				found[gcd("genInfo.report.period.fiscalPreviousYearEnd")].value, date(2025, 12, 31)
			)
			self.assertEqual(
				found[gcd("genInfo.report.period.balSheetClosingDatePreviousYear")].value, date(2025, 12, 31)
			)


class MussfelderTest(TestCase):
	def test_sends_the_other_mussfelder_of_a_gmbh_nil_in_the_order_of_the_presentation(self):
		"""Leitfaden A.10.1 and B.14.2.3: a tuple with Mussfelder holds them as NIL, a choice without one is NIL as a
		whole; a Mussfeld of another legal form is not sent (FAQ zur E-Bilanz, Tz. 4 a)."""
		found = of()
		self.assertEqual(
			[fact.concept for fact in found],
			[
				gcd(name)
				for name in (
					"genInfo.report.id.reportStatus",
					"genInfo.report.id.reportElement",
					"genInfo.report.id.statementType",
					"genInfo.report.id.accountingStandard",
					"genInfo.report.id.incomeStatementFormat",
					"genInfo.report.period.fiscalYearBegin",
					"genInfo.report.period.fiscalYearEnd",
					"genInfo.report.period.balSheetClosingDate",
					"genInfo.company.id.name",
					"genInfo.company.id.location.houseNo",
					"genInfo.company.id.legalStatus",
					"genInfo.company.id.idNo",
					"genInfo.company.id.shareholder",
					"genInfo.report.id.revisionStatus",
					"genInfo.report.id.reportElement.reportElements.transmissionNotYetPossible",
					"genInfo.report.id.incomeStatementendswithBalProfit",
					"genInfo.report.id.specialAccountingStandard",
					"genInfo.report.id.consolidationRange",
					"genInfo.report.period.fiscalPreviousYearBegin",
					"genInfo.report.period.fiscalPreviousYearEnd",
					"genInfo.report.period.balSheetClosingDatePreviousYear",
					"genInfo.company.id.location.street",
					"genInfo.company.id.location.zipCode",
					"genInfo.company.id.location.city",
					"genInfo.company.id.location.country",
					"genInfo.company.id.business",
					"genInfo.company.id.incomeClassification",
					"genInfo.company.id.domesticBranchOfForeignCompany",
					"genInfo.company.id.entityWithTaxablePurposeBusiness",
				)
			],
		)
		found = by_concept(found)
		self.assertEqual(found[SHAREHOLDER], nil_shareholder())
		self.assertNotIn(gcd("genInfo.company.id.optionKStGs1a"), found)

	def test_a_choice_without_a_value_reports_one_auswahlwert_nil_in_the_fiscal_year(self):
		"""ERiC rule 170155092 counts a fact of a Mussfeld only in the contexts of the current year, and a tuple has no
		context: a choice NIL as a whole is no fact (real validation with ERiC 44.3.6.0, Bilanz_6.9). The GmbH example
		of the ERiC documentation 44.3.6.0, HandelsbilanzLandwirt_GmbH.xml, reports these Auswahlwerte NIL."""
		found = by_concept(of())
		self.assertEqual(
			found[gcd("genInfo.company.id.domesticBranchOfForeignCompany")],
			Tuple(
				gcd("genInfo.company.id.domesticBranchOfForeignCompany"),
				(Item(gcd("genInfo.company.id.domesticBranchOfForeignCompany.other"), WJ, None),),
			),
		)
		self.assertEqual(
			found[gcd("genInfo.company.id.entityWithTaxablePurposeBusiness")],
			Tuple(
				gcd("genInfo.company.id.entityWithTaxablePurposeBusiness"),
				(
					Item(
						gcd(
							"genInfo.company.id.entityWithTaxablePurposeBusiness.merchantVesselsInInternationalTraffic"
						),
						WJ,
						None,
					),
				),
			),
		)

	def test_no_tuple_is_nil_as_a_whole(self):
		def tuples(found):
			for fact in found:
				if isinstance(fact, Tuple):
					yield fact
					yield from tuples(fact.children)

		for fields in ({}, {"statement_type": "EB", "periods": OPENING}, {"accounting_standard": "HGBM"}):
			with self.subTest(**fields):
				self.assertEqual([fact.concept for fact in tuples(of(**fields)) if fact.nil], [])

	def test_sends_every_mussfeld_of_the_gcd(self):
		"""Leitfaden B.14.2: each Mussfeld of the GCD of the structure, inside its tuple where it is a part."""
		found = of()
		reported = {fact.concept for fact in found}
		for fact in found:
			if isinstance(fact, Tuple):
				reported |= {child.concept for child in fact.children}
		gcd_required = [name for name in structure(view(), case()).required if name.startswith("de-gcd:")]
		self.assertEqual([name for name in gcd_required if name not in reported], [])


def nil_shareholder() -> Tuple:
	"""The Gesellschafter of a company without shareholders in its settings, as the GmbH example of the ERiC
	documentation 44.3.6.0 reports them."""
	return Tuple(
		SHAREHOLDER,
		(
			Item(gcd("genInfo.company.id.shareholder.name"), WJ, None),
			Item(gcd("genInfo.company.id.shareholder.id"), WJ, None),
			Item(gcd("genInfo.company.id.shareholder.taxnumber"), WJ, None),
			Item(gcd("genInfo.company.id.shareholder.taxid"), WJ, None),
			Item(gcd("genInfo.company.id.shareholder.WID"), WJ, None),
			Tuple(
				gcd("genInfo.company.id.shareholder.legalStatus"),
				(Item(gcd("genInfo.company.id.shareholder.legalStatus.legalStatus.NPP"), WJ, None),),
			),
			Tuple(
				gcd("genInfo.company.id.shareholder.ShareDivideKey"),
				(
					Item(gcd("genInfo.company.id.shareholder.ShareDivideKey.numerator"), WJ, None),
					Item(gcd("genInfo.company.id.shareholder.ShareDivideKey.denominator"), WJ, None),
				),
			),
		),
	)


def shareholder(name: str, kind: ShareholderKind, percent: str, *, row: int = 1, **fields) -> Shareholder:
	return Shareholder(
		row=row,
		name=name,
		kind=kind,
		nominal_amount=Decimal(25000),
		percent=Decimal(percent),
		from_date=fields.pop("from_date", date(2020, 1, 1)),
		**fields,
	)


HOLDING = Gesellschafter("Muster Beteiligungs GmbH", ShareholderKind.CORPORATION, Decimal(60))
PERSON = Gesellschafter("Erika Beispiel", ShareholderKind.NATURAL_PERSON, Decimal(40))


class GesellschafterTest(TestCase):
	"""genInfo.company.id.shareholder, a Mussfeld of the GCD of a GmbH (Leitfaden B.14.2.1), reported once per
	shareholder of the Annual Filing Settings with what the settings say of them."""

	def test_each_shareholder_with_its_legal_status_and_share(self):
		"""The legal status of a corporation is KOER, of a partnership PG; that of a natural person tells Privat- from
		Betriebsvermögen (NPP, NPB), which the settings do not record, so it is NIL. The share is the Beteiligungsschlüssel
		as Zähler and Nenner in lowest terms (de-gcd-2025-04-01.xsd: digits only)."""
		partnership = Gesellschafter("Muster KG", ShareholderKind.PARTNERSHIP, Decimal("33.3333"))
		found = [
			fact
			for fact in of(replace(MASTER, shareholders=(HOLDING, PERSON, partnership)))
			if fact.concept == SHAREHOLDER
		]
		self.assertEqual(len(found), 3)

		def status(fact):
			return next(child for child in fact.children if child.concept.endswith(".legalStatus")).children

		def key(fact):
			divide = next(child for child in fact.children if child.concept.endswith(".ShareDivideKey"))
			return [child.value for child in divide.children]

		self.assertEqual(
			[fact.children[0].value for fact in found],
			["Muster Beteiligungs GmbH", "Erika Beispiel", "Muster KG"],
		)
		self.assertEqual(
			[status(fact) for fact in found],
			[
				(Item(gcd("genInfo.company.id.shareholder.legalStatus.legalStatus.KOER"), WJ, ""),),
				(Item(gcd("genInfo.company.id.shareholder.legalStatus.legalStatus.NPP"), WJ, None),),
				(Item(gcd("genInfo.company.id.shareholder.legalStatus.legalStatus.PG"), WJ, ""),),
			],
		)
		self.assertEqual([key(fact) for fact in found], [["3", "5"], ["2", "5"], ["333333", "1000000"]])

	def test_keeps_the_numbers_of_the_shareholders_for_the_kst_1(self):
		"""Steuernummer, IdNr. and W-IdNr. of a shareholder are kept for the KSt 1 (§ 139b Abs. 2 AO for the IdNr.), so
		the E-Bilanz sends them NIL, with every part in the order of the tuple."""
		(found,) = [
			fact for fact in of(replace(MASTER, shareholders=(HOLDING,))) if fact.concept == SHAREHOLDER
		]
		self.assertEqual(
			[
				(child.concept.rpartition(".shareholder.")[2], getattr(child, "value", None))
				for child in found.children
			],
			[
				("name", "Muster Beteiligungs GmbH"),
				("id", None),
				("taxnumber", None),
				("taxid", None),
				("WID", None),
				("legalStatus", None),
				("ShareDivideKey", None),
			],
		)

	def test_without_shareholders_one_gesellschafter_nil(self):
		self.assertEqual(by_concept(of())[SHAREHOLDER], nil_shareholder())

	def test_the_shareholders_on_the_bilanzstichtag(self):
		"""The Gesellschafter who hold shares on the Bilanzstichtag, as the Bilanz shows the company on that day."""
		holders = (
			shareholder("Alt GmbH", ShareholderKind.CORPORATION, "100", to_date=date(2026, 6, 30)),
			shareholder("Neu GmbH", ShareholderKind.CORPORATION, "100", row=2, from_date=date(2026, 7, 1)),
		)
		self.assertEqual(
			gesellschafter(holders, date(2026, 12, 31)),
			(Gesellschafter("Neu GmbH", ShareholderKind.CORPORATION, Decimal(100)),),
		)
		self.assertEqual(
			gesellschafter(holders, date(2026, 3, 1)),
			(Gesellschafter("Alt GmbH", ShareholderKind.CORPORATION, Decimal(100)),),
		)

	def test_a_name_in_the_characters_of_elster(self):
		"""ERiC E-Bilanz-Dokumentation für HGB-Taxonomie 6.9, Kap. 3.16."""
		person = replace(PERSON, name="Erika \N{SNOWMAN}")
		(finding,) = checked(replace(MASTER, shareholders=(person,)))
		self.assertEqual(finding.code, "EB-GCD-ZEICHEN")
		self.assertEqual(finding.reference, gcd("genInfo.company.id.shareholder.name"))
		self.assertIn("Gesellschafter", finding.text)


class CheckTest(TestCase):
	def test_complete_master_data_find_nothing(self):
		self.assertEqual(checked(), ())
		self.assertEqual(checked(statement_type="EB", periods=OPENING), ())
		self.assertEqual(checked(reason="Grund", kontennachweis=False), ())
		previous = replace(MASTER, previous_fiscal_year=(date(2025, 1, 1), date(2025, 12, 31)))
		self.assertEqual(checked(previous), ())
		self.assertEqual(checked(previous, accounting_standard="HGBM", periods=WITH_PRIOR), ())

	def test_names_what_the_firmensitz_lacks(self):
		"""Leitfaden B.14.3.1.16; rules 170205049, 170205053, 170205052 and 170205051."""
		found = checked(replace(MASTER, name="", street=" ", postal_code="", city=""))
		self.assertEqual(codes(found), ["170205049", "170205053", "170205052", "170205051"])
		self.assertEqual(found[0].reference, gcd("genInfo.company.id.name"))
		self.assertIn("Name des Unternehmens", found[0].text)
		self.assertIn("B.14.3.1.16", found[0].source)
		self.assertIn("170205049", found[0].source)
		self.assertTrue(all(finding.blocking for finding in found))

	def test_names_characters_elster_does_not_take(self):
		"""ERiC E-Bilanz-Dokumentation für HGB-Taxonomie 6.9, Kap. 3.16."""
		found = checked(replace(MASTER, city="Musterstadt \N{SNOWMAN}"))
		self.assertEqual(codes(found), ["EB-GCD-ZEICHEN"])
		self.assertEqual(found[0].reference, gcd("genInfo.company.id.location.city"))
		self.assertIn("U+2603", found[0].text)
		(finding,) = checked(reason="Grund \N{SNOWMAN}", kontennachweis=False)
		self.assertEqual(finding.reference, NOT_YET_POSSIBLE)
		self.assertIn(
			"\N{SNOWMAN}",
			by_concept(of(reason="Grund \N{SNOWMAN}", kontennachweis=False))[NOT_YET_POSSIBLE].value,
		)

	def test_a_jahresabschluss_needs_the_steuernummer(self):
		"""Leitfaden B.14.3.1.18; rule 170205025."""
		(finding,) = checked(replace(MASTER, steuernummer=None))
		self.assertEqual(finding.code, "170205025")
		self.assertEqual(finding.reference, ST13)

	def test_the_steuernummer_has_the_form_of_elster(self):
		"""13 digits with a 0 as the fifth; its Prüfziffer is ERiC's to check (Leitfaden B.14.8)."""
		for number in ("919801131001", "9198111310010", "9198 011310010"):
			with self.subTest(number):
				self.assertEqual(codes(checked(replace(MASTER, steuernummer=number))), ["EB-STEUERNUMMER"])

	def test_the_bundesfinanzamtsnummer_is_that_of_the_steuernummer(self):
		"""Leitfaden B.2.1; rule 170205002."""
		(finding,) = checked(replace(MASTER, bundesfinanzamtsnummer="9199"))
		self.assertEqual(finding.code, "EB-FINANZAMT")
		self.assertEqual(finding.reference, BF4)
		self.assertEqual(checked(replace(MASTER, bundesfinanzamtsnummer="9198")), ())

	def test_an_eroeffnungsbilanz_without_steuernummer_names_its_finanzamt_and_waits_for_the_steuernummer(
		self,
	):
		"""Leitfaden B.14.3.1.18, rule 170205026; which identifier its contexts name is unverified (B.14.7)."""
		without = replace(MASTER, steuernummer=None)
		self.assertEqual(
			codes(checked(without, statement_type="EB", periods=OPENING)), ["170205026", "EB-KENNUNG"]
		)
		self.assertEqual(
			codes(
				checked(replace(without, bundesfinanzamtsnummer="91"), statement_type="EB", periods=OPENING)
			),
			["170205026", "EB-KENNUNG"],
		)
		named = replace(without, bundesfinanzamtsnummer="9198")
		self.assertEqual(codes(checked(named, statement_type="EB", periods=OPENING)), ["EB-KENNUNG"])
		self.assertEqual(named.finanzamt, "9198")
		self.assertIsNone(without.finanzamt)
		found = by_concept(of(named, statement_type="EB", periods=OPENING))
		self.assertEqual(values(found[gcd("genInfo.company.id.idNo")]), [(ST13, None), (BF4, "9198")])

	def test_the_previous_fiscal_year_of_the_master_data_ends_before_the_fiscal_year(self):
		"""Leitfaden B.14.3.1.6; rules 170405009 and 170405006."""
		backwards = (date(2025, 12, 31), date(2025, 1, 1))
		self.assertEqual(codes(checked(replace(MASTER, previous_fiscal_year=backwards))), ["170405009"])
		overlapping = (date(2025, 2, 1), date(2026, 1, 31))
		self.assertEqual(codes(checked(replace(MASTER, previous_fiscal_year=overlapping))), ["170405006"])

	def test_the_version_of_the_taxonomy_serves_the_fiscal_year(self):
		"""Leitfaden B.18; rules 170205007, 170205018 and 170205017; BMF letter of 10 June 2025."""
		early = Periods(date(2024, 1, 1), date(2024, 12, 31))
		self.assertEqual(codes(checked(periods=early)), ["170205007"])
		late = Periods(date(2027, 1, 1), date(2027, 12, 31))
		(finding,) = checked(periods=late)
		self.assertEqual(finding.code, "170205018")
		self.assertIn("B.18", finding.source)
		self.assertIn("BMF letter of 10 June 2025", finding.source)
		tolerated = Periods(date(2027, 3, 1), date(2027, 12, 31), date(2027, 3, 1))
		self.assertEqual(checked(statement_type="EB", periods=tolerated), ())
		too_late = Periods(date(2028, 3, 1), date(2028, 12, 31), date(2028, 3, 1))
		self.assertEqual(codes(checked(statement_type="EB", periods=too_late)), ["170205017"])

	def test_a_version_steuerbote_does_not_know(self):
		(finding,) = checked(taxonomy=replace(view(), version="6.11"))
		self.assertEqual(finding.code, "EB-TAXONOMIE")
		self.assertIn("6.11", finding.text)

	def test_every_finding_holds_the_e_bilanz_back(self):
		found = checked(
			replace(MASTER, name="", steuernummer=None), periods=Periods(date(2024, 1, 1), date(2024, 12, 31))
		)
		self.assertEqual(codes(found), ["170205049", "170205025", "170205007"])
		self.assertTrue(all(finding.severity is Severity.ERROR for finding in found))
