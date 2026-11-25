"""The Vordrucke of the Gewerbesteuererklärung per EZ and the fields of the lines the computation fills."""

import re
from dataclasses import replace
from decimal import Decimal
from types import MappingProxyType
from unittest import TestCase

from steuerbote.elster.erklaerung import FORMATS, Form, python_pattern
from steuerbote.eric.datenart import gewst
from steuerbote.gewst import chain
from steuerbote.gewst.form import (
	CATALOGUES,
	FORMS,
	RECHTSFORMEN,
	STEP_FIELDS,
	catalogue_for,
	vordrucke,
)
from steuerbote.gewst.years import YEARS
from steuerbote.kst.form import Vordruck, checked
from steuerbote.kst.holdings import Exemption, Holding, HoldingDividends, HoldingResult
from steuerbote.kst.tests.support import FIGURES
from steuerbote.kst.tests.test_golden import gewerbesteuer, koerperschaftsteuer
from steuerbote.ustva.years import UnknownYearError

CATALOGUE = CATALOGUES[2026]


def amounts(vordruck: Vordruck) -> dict[str, object]:
	return {entry.feldkennung: entry.value for entry in vordruck.entries}


class YearsTest(TestCase):
	def test_hold_exactly_the_years_of_the_year_table(self):
		self.assertEqual(tuple(CATALOGUES), tuple(YEARS))
		self.assertEqual(tuple(RECHTSFORMEN), tuple(YEARS))

	def test_a_year_without_vordrucke_is_refused(self):
		self.assertIs(catalogue_for(2026), CATALOGUE)
		with self.assertRaises(UnknownYearError) as raised:
			catalogue_for(2027)
		self.assertEqual(
			str(raised.exception), "no Vordrucke of the Gewerbesteuer for 2027; known years: 2026"
		)


class CatalogueTest(TestCase):
	def test_is_the_gewerbesteuer_of_the_ez_from_the_jahresdokumentation_2025(self):
		self.assertEqual(CATALOGUE.datenart, gewst(2026))
		self.assertEqual(
			CATALOGUE.source, "Jahresdokumentation_E20_2025.ods, Versionslabel 11.0, provisionally for 2026"
		)

	def test_the_vordrucke_of_a_gmbh_in_the_order_of_the_schema(self):
		self.assertEqual(FORMS, (Form("GewSt1A", 1, True), Form("BEG", 99), Form("Vorsatz", 1, True)))
		self.assertEqual(CATALOGUE.mandatory_forms, ("GewSt1A", "Vorsatz"))

	def test_holds_every_field_of_gewst_1_a_and_anlage_beg(self):
		self.assertEqual(len([f for f in CATALOGUE.fields if f.form == "GewSt1A"]), 176)
		self.assertEqual(len([f for f in CATALOGUE.fields if f.form == "BEG"]), 35)
		for field in CATALOGUE.fields:
			with self.subTest(feldkennung=field.feldkennung):
				self.assertIn(field.format, FORMATS)
				re.compile(python_pattern(field.pattern))
		self.assertEqual(
			{field.feldkennung for field in CATALOGUE.fields if field.required},
			{"E4000101", "E4000201", "E4050201", "E4050601"},
		)

	def test_names_lines_formats_and_lists_of_the_jahresdokumentation(self):
		profit = CATALOGUE.field("E4001703")
		self.assertEqual(
			(profit.form, profit.context, profit.line, profit.format), ("GewSt1A", "Gewinn", "39", "N")
		)
		self.assertEqual(CATALOGUE.field("E4003403").line, "92d")
		self.assertEqual(CATALOGUE.field("E4050701").options, ("1", "2", "3"))
		self.assertEqual(CATALOGUE.field("E4000501").options[:2], ("350", "370"))
		self.assertEqual(CATALOGUE.field("E4050201").length, 25)

	def test_holds_the_rules_steuerbote_checks(self):
		self.assertEqual(
			[rule.code for rule in CATALOGUE.rules],
			[
				"40000",
				"40038",
				"40047",
				"40029",
				"40051",
				"40052",
				"40053",
				"40054",
				"40954",
				"40958",
				"40959",
				"40965",
			],
		)
		self.assertFalse(any(rule.hint for rule in CATALOGUE.rules))

	def test_no_rule_holds_its_fehlertext_of_the_jahresdokumentation(self):
		self.assertEqual({rule.text for rule in CATALOGUE.rules}, {""})

	def test_the_rechtsformen_steuerbote_files_are_koerperschaften(self):
		self.assertEqual(
			{code: dict(categories) for code, categories in RECHTSFORMEN[2026].items()},
			{"350": {"Rechtsformgruppe": "KOE"}, "370": {"Rechtsformgruppe": "KOE"}},
		)


class StepsTest(TestCase):
	def test_every_step_with_a_field_has_it_in_the_catalogue_on_its_form_and_line(self):
		for step in chain.STEPS:
			if step.field is None:
				continue
			with self.subTest(step=step.key):
				field = CATALOGUE.field(STEP_FIELDS[step.key])
				self.assertEqual((field.form, field.line), (step.form, step.line))
		self.assertEqual(STEP_FIELDS["profit"], "E4001703")

	def test_a_catalogue_that_lacks_a_field_of_a_step_is_refused(self):
		fields = tuple(field for field in CATALOGUE.fields if field.feldkennung != "E4001703")
		with self.assertRaisesRegex(ValueError, "no field E4001703 of the step profit"):
			checked(replace(CATALOGUE, fields=fields), chain.STEPS)


class VordruckeTest(TestCase):
	"""The worked example „Muster IT GmbH“: the holding of 12 % in Beta GmbH is below 15 %, so its exempt dividends
	come back under § 8 Nummer 5 GewStG."""

	def test_gewst_1_a_holds_the_amounts_of_the_steps_that_are_not_zero(self):
		(gewst_1a, beg) = vordrucke(gewerbesteuer(koerperschaftsteuer()))
		self.assertEqual(gewst_1a.form, "GewSt1A")
		self.assertEqual(
			amounts(gewst_1a),
			{
				"E4001703": Decimal("97200"),
				"E4003202": Decimal("5000"),
				"E4003502": Decimal("6000"),
				"E4003602": Decimal("24000"),
				"E4003703": Decimal("10000"),
				"E4004103": Decimal("0"),
				"E4006601": Decimal("11400"),
				"E4003403": Decimal("1000"),
			},
		)
		self.assertEqual(beg.form, "BEG")
		self.assertEqual(
			amounts(beg),
			{
				"E4050201": "Beta GmbH",
				"E4050601": Decimal("12000"),
				"E4051201": Decimal("12000"),
				"E4051401": Decimal("0"),
				"E4051501": Decimal("11400"),
			},
		)

	def test_line_56_goes_with_line_57_and_line_12_with_line_14(self):
		"""ERiC refuses line 56 of GewSt 1 A without line 57 (rule 40260, „FelderNichtGemeinsamAngegeben(E4003703,
		E4004103)“) and, for a Körperschaft, line 12 of Anlage BEG without line 14 (rule 40944), Jahresdokumentation
		GewSt 2025; validation of the worked example with ERiC 44.3.6.0. Line 57 holds the part of line 56 paid to
		beschränkt Steuerpflichtige (§ 50a Absatz 1 Nummer 3 EStG), which the books do not tell apart: zero, a limit
		docs/ertragsteuern.md names."""
		(gewst_1a, beg) = vordrucke(gewerbesteuer(koerperschaftsteuer()))
		self.assertEqual(
			(gewst_1a.value("E4003703"), gewst_1a.value("E4004103")), (Decimal("10000"), Decimal("0"))
		)
		self.assertEqual((beg.value("E4051201"), beg.value("E4051401")), (Decimal("12000"), Decimal("0")))
		result = gewerbesteuer(koerperschaftsteuer())
		lines = dict(result.lines)
		lines["licences"] = replace(lines["licences"], declared=Decimal("0"))
		(without, _) = vordrucke(replace(result, lines=MappingProxyType(lines)))
		self.assertEqual((without.value("E4003703"), without.value("E4004103")), (None, None))

	def test_a_holding_of_at_least_15_percent_cuts_its_dividends_with_the_costs_beside_them(self):
		"""§ 8b Absatz 7 KStG taxes the dividends in full, so § 9 Nummer 2a GewStG cuts them: lines 7, 8, 9, 14 and 16
		to 19, with line 12 at zero beside line 14."""
		holding = HoldingResult(
			Holding("Delta GmbH", Decimal("20"), Decimal("20")),
			Decimal("10000.00"),
			financing_costs=Decimal("1000.40"),
			other_costs=Decimal("500.00"),
		)
		taxed = HoldingDividends(holding, Exemption.TRADING_BOOK, acquisition_counts=False)
		result = koerperschaftsteuer()
		kst = replace(result, p8b=replace(result.p8b, holdings=(*result.p8b.holdings, taxed)))
		(gewst_1a, *begs) = vordrucke(chain.compute(kst, chain.GewstInputs(Decimal("400")), FIGURES))
		delta = next(beg for beg in begs if beg.value("E4050201") == "Delta GmbH")
		self.assertEqual(
			amounts(delta),
			{
				"E4050201": "Delta GmbH",
				"E4050601": Decimal("10000"),
				"E4050701": "1",
				"E4050801": Decimal("1000"),
				"E4050901": Decimal("500"),
				"E4051201": Decimal("0"),
				"E4051401": Decimal("10000"),
				"E4051601": Decimal("10000"),
				"E4051701": Decimal("1000"),
				"E4051801": Decimal("500"),
				"E4051901": Decimal("8500"),
				"E4052001": Decimal("1000"),
			},
		)
		self.assertEqual(
			(gewst_1a.value("E4006701"), gewst_1a.value("E4006801")), (Decimal("1000"), Decimal("8500"))
		)

	def test_a_schachtel_whose_dividends_are_exempt_files_its_lines_at_zero(self):
		"""Line 12 with line 14, beside line 7 line 16, beside it line 19, and line 81 of GewSt 1 A summing line 19:
		rules 40944, 40946, 40949 and 40491 of the Jahresdokumentation GewSt 2025 want them at zero as well
		(validation with ERiC 44.3.6.0)."""
		holding = HoldingResult(Holding("Theta GmbH", Decimal("40"), Decimal("40")), Decimal("6000.00"))
		exempt = HoldingDividends(holding, Exemption.EXEMPT, acquisition_counts=False)
		result = koerperschaftsteuer()
		kst = replace(result, p8b=replace(result.p8b, holdings=(exempt,)))
		(gewst_1a, theta) = vordrucke(chain.compute(kst, chain.GewstInputs(Decimal("400")), FIGURES))
		self.assertEqual(
			amounts(theta),
			{
				"E4050201": "Theta GmbH",
				"E4050601": Decimal("6000"),
				"E4050701": "1",
				"E4051201": Decimal("6000"),
				"E4051401": Decimal("0"),
				"E4051601": Decimal("0"),
				"E4051901": Decimal("0"),
			},
		)
		self.assertEqual((gewst_1a.value("E4006701"), gewst_1a.value("E4006801")), (None, Decimal("0")))

	def test_a_holding_of_at_least_15_percent_without_dividends_or_costs_files_lines_2_6_and_7(self):
		holding = HoldingResult(Holding("Eta GmbH", Decimal("30"), Decimal("30")), Decimal("0.40"))
		taxed = HoldingDividends(holding, Exemption.EXEMPT, acquisition_counts=False)
		result = koerperschaftsteuer()
		kst = replace(result, p8b=replace(result.p8b, holdings=(*result.p8b.holdings, taxed)))
		(_, *begs) = vordrucke(chain.compute(kst, chain.GewstInputs(Decimal("400")), FIGURES))
		eta = next(beg for beg in begs if beg.value("E4050201") == "Eta GmbH")
		self.assertEqual(amounts(eta), {"E4050201": "Eta GmbH", "E4050601": Decimal("0"), "E4050701": "1"})
