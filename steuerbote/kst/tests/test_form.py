"""The Vordrucke of the Körperschaftsteuererklärung per VZ and the fields of the lines the computation fills."""

import re
from dataclasses import replace
from decimal import Decimal
from unittest import TestCase

from steuerbote.elster.erklaerung import FORMATS, Form, python_pattern
from steuerbote.eric.datenart import kst
from steuerbote.kst.chain import STEPS, KstInputs, compute
from steuerbote.kst.einlagekonto import roll_forward
from steuerbote.kst.form import (
	CATALOGUES,
	FORMS,
	INDEXED,
	RECHTSFORMEN,
	STEP_FIELDS,
	WJ,
	Entry,
	Vordruck,
	catalogue_for,
	checked,
	entries,
	kst1f,
	step_field,
	table_fields,
	vordrucke,
)
from steuerbote.kst.tests.support import FIGURES, credit, debit
from steuerbote.kst.tests.test_golden import MAPPING, koerperschaftsteuer
from steuerbote.kst.years import YEARS
from steuerbote.ustva.years import UnknownYearError

CATALOGUE = CATALOGUES[2026]
ZERO = Decimal("0")
FIELDS_PER_FORM = {"KSt1": 50, "GK": 270, "ZVE": 113, "Z": 20, "Verluste": 35, "WA": 56, "KSt1F": 185}
MANDATORY_FIELDS = {
	"E8000101",
	"E8000501",
	"E8000601",
	"E8001105",
	"E8109901",
	"E8009201",
	"E8010101",
}


def values(vordruck: Vordruck) -> dict[tuple[str, tuple[int, ...]], object]:
	return {(entry.feldkennung, entry.rows): entry.value for entry in vordruck.entries}


def by_form(result) -> dict[str, Vordruck]:
	found = vordrucke(result)
	return {vordruck.form: vordruck for vordruck in found}


def amounts(vordruck: Vordruck) -> dict[str, Decimal]:
	return {entry.feldkennung: entry.value for entry in vordruck.entries if not entry.rows}


class YearsTest(TestCase):
	def test_hold_exactly_the_years_of_the_year_table(self):
		self.assertEqual(tuple(CATALOGUES), tuple(YEARS))
		self.assertEqual(tuple(RECHTSFORMEN), tuple(YEARS))

	def test_a_year_without_vordrucke_is_refused(self):
		self.assertIs(catalogue_for(2026), CATALOGUE)
		with self.assertRaises(UnknownYearError) as raised:
			catalogue_for(2025)
		self.assertEqual(
			str(raised.exception), "no Vordrucke of the Körperschaftsteuer for 2025; known years: 2026"
		)


class CatalogueTest(TestCase):
	"""2026 takes the Vordrucke of Jahresdokumentation_E30_2025.ods (Versionslabel 7.0), provisionally."""

	def test_is_the_koerperschaftsteuer_of_the_vz_from_the_jahresdokumentation_2025(self):
		self.assertEqual(CATALOGUE.datenart, kst(2026))
		self.assertEqual(
			CATALOGUE.source, "Jahresdokumentation_E30_2025.ods, Versionslabel 7.0, provisionally for 2026"
		)
		self.assertTrue(YEARS[2026].provisional)

	def test_the_vordrucke_of_a_gmbh_in_the_order_of_the_schema(self):
		self.assertEqual(
			FORMS,
			(
				Form("KSt1", 1, True),
				Form("GK", 2),
				Form("ZVE"),
				Form("Z"),
				Form("Verluste"),
				Form("WA"),
				Form("KSt1F", 2),
				Form("Vorsatz", 1, True),
			),
		)
		self.assertEqual(CATALOGUE.mandatory_forms, ("KSt1", "Vorsatz"))
		self.assertEqual(INDEXED, {"GK", "KSt1F"})
		self.assertEqual(WJ, ("WJ1", "WJ2"))

	def test_holds_every_field_of_each_vordruck_but_the_vorsatz(self):
		counted = dict.fromkeys(FIELDS_PER_FORM, 0)
		for field in CATALOGUE.fields:
			counted[field.form] += 1
		self.assertEqual(counted, FIELDS_PER_FORM)
		self.assertNotIn("Vorsatz", {field.form for field in CATALOGUE.fields})
		self.assertNotIn("WJ", {field.feldkennung for field in CATALOGUE.fields})

	def test_every_field_has_a_format_steuerbote_writes_and_a_pattern_python_reads(self):
		for field in CATALOGUE.fields:
			with self.subTest(feldkennung=field.feldkennung):
				self.assertIn(field.format, FORMATS)
				self.assertRegex(field.feldkennung, r"^E\d{7}$")
				re.compile(python_pattern(field.pattern))
				self.assertEqual(field.label, " ".join(field.label.split()))
				if field.format == "C":
					self.assertIsNotNone(field.length)

	def test_a_listenfeld_takes_the_values_its_pattern_quotes(self):
		rechtsform = CATALOGUE.field("E8001105")
		self.assertEqual(rechtsform.format, "H")
		self.assertEqual(rechtsform.options[:2], ("350", "370"))
		self.assertEqual(rechtsform.text("350"), "350")
		self.assertEqual(CATALOGUE.field("E8001305").options, ("1", "2", "3", "4"))
		self.assertEqual(CATALOGUE.field("E8000101").options, ())

	def test_names_the_lines_kennzahlen_and_mandatory_fields_of_the_jahresdokumentation(self):
		gk_11 = CATALOGUE.field("E8002001")
		self.assertEqual((gk_11.form, gk_11.context, gk_11.line, gk_11.format), ("GK", "Bilanz", "11", "N"))
		self.assertEqual(gk_11.kennzahl, "13.110")
		self.assertEqual(CATALOGUE.field("E8002709").line, "75c")
		self.assertIsNone(CATALOGUE.field("E8000016").line)
		self.assertEqual(CATALOGUE.field("E8000101").length, 103)
		self.assertEqual(
			{field.feldkennung for field in CATALOGUE.fields if field.required}, MANDATORY_FIELDS
		)

	def test_holds_the_rules_steuerbote_checks(self):
		codes = [rule.code for rule in CATALOGUE.rules]
		self.assertEqual(len(codes), len(set(codes)))
		self.assertEqual(len(codes), 54)
		for code in ("8906062", "8900207", "8900413", "8900431", "8900331", "8956020", "8956042", "8956040"):
			self.assertIn(code, codes)
		for code in ("8900184", "8900170", "8920021", "8924445", "8920076", "8924401", "8912019"):
			self.assertIn(code, codes)
		hints = [rule.code for rule in CATALOGUE.rules if rule.hint]
		self.assertEqual(hints, ["8912019"])
		(rule,) = (rule for rule in CATALOGUE.rules if rule.code == "8900331")
		self.assertEqual(rule.name, "Regel_120031_1A_KSt")
		self.assertIn("/ZVE/Steuerberechnung/Regel/E8007504", rule.fields)

	def test_no_rule_holds_its_fehlertext_of_the_jahresdokumentation(self):
		self.assertEqual({rule.text for rule in CATALOGUE.rules}, {""})

	def test_the_rechtsformen_steuerbote_files_are_kapitalgesellschaften_with_gewerbliche_einkuenfte_only(
		self,
	):
		self.assertEqual(
			{code: dict(categories) for code, categories in RECHTSFORMEN[2026].items()},
			{"350": {"RF_Gruppe": "1", "NurG": "1"}, "370": {"RF_Gruppe": "1", "NurG": "1"}},
		)


class TableTest(TestCase):
	def test_reads_a_line_per_field_with_a_dash_for_an_empty_cell(self):
		(field,) = table_fields(
			"KSt1",
			"\n-\tE8000016\t-\tX\t-\t-\t-\tX\tErklärung zur gesonderten Feststellung\n",
		)
		self.assertEqual(
			(
				field.form,
				field.context,
				field.feldkennung,
				field.line,
				field.length,
				field.required,
				field.kennzahl,
			),
			("KSt1", "", "E8000016", None, None, False, None),
		)
		(text,) = table_fields("GK", "Bilanz\tE8000110\t1\tC\t999\tJa\t13.1\t.{1,999}\tBezeichnung")
		self.assertEqual(
			(text.context, text.line, text.length, text.required, text.kennzahl),
			("Bilanz", "1", 999, True, "13.1"),
		)


class StepsTest(TestCase):
	"""Every step of steuerbote.kst.chain with a field finds it in the catalogue, on its form and line."""

	def test_every_step_with_a_field_has_it_in_the_catalogue_on_its_form_and_line(self):
		for step in STEPS:
			if step.field is None:
				continue
			with self.subTest(step=step.key):
				field = step_field(2026, step.key)
				self.assertEqual(
					(field.feldkennung, field.form, field.line), (step.field, step.form, step.line)
				)
		self.assertEqual(STEP_FIELDS["business_income"], "E8109901")
		self.assertEqual(len(STEP_FIELDS), len([step for step in STEPS if step.field]))
		with self.assertRaises(KeyError):
			step_field(2026, "kst_balance")

	def test_a_catalogue_without_a_field_of_a_step_is_refused(self):
		fields = tuple(field for field in CATALOGUE.fields if field.feldkennung != "E8002001")
		with self.assertRaisesRegex(ValueError, "no field E8002001 of the step net_income"):
			checked(replace(CATALOGUE, fields=fields))

	def test_a_catalogue_that_moves_a_field_of_a_step_is_refused(self):
		fields = tuple(
			replace(field, line="12") if field.feldkennung == "E8002001" else field
			for field in CATALOGUE.fields
		)
		with self.assertRaisesRegex(
			ValueError, "the step net_income is GK line 11, its field E8002001 GK line 12"
		):
			checked(replace(CATALOGUE, fields=fields))
		self.assertIs(checked(CATALOGUE), CATALOGUE)


class EntryTest(TestCase):
	def test_numbers_the_instances_of_the_repeated_contexts_from_zero(self):
		self.assertEqual(Entry("E8122101", "Muster", [0, 2]).rows, (0, 2))
		for rows in ((-1,), (True,), ("1",)):
			with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, "count from 0"):
				Entry("E8122101", "Muster", rows)

	def test_a_vordruck_finds_and_extends_its_entries(self):
		vordruck = Vordruck("GK", entries({"E8002001": Decimal("100")}), "WJ1")
		extended = vordruck.extended(Entry("E8560403", "Beta GmbH", (0,)))
		self.assertEqual((extended.form, extended.wj), ("GK", "WJ1"))
		self.assertEqual(extended.value("E8002001"), Decimal("100"))
		self.assertEqual(extended.value("E8560403", (0,)), "Beta GmbH")
		self.assertIsNone(extended.value("E8560403"))
		self.assertEqual(len(vordruck.entries), 1)
		self.assertEqual(Vordruck("WA", [Entry("E8122801", True)]).entries, (Entry("E8122801", True),))


class VordruckeTest(TestCase):
	"""The amounts of the worked example „Muster IT GmbH“ (test_golden.py) in the Vordrucke."""

	def test_anlage_gk_holds_the_amounts_of_the_steps_that_are_not_zero_and_line_300(self):
		gk = by_form(koerperschaftsteuer())["GK"]
		self.assertEqual(gk.wj, "WJ1")
		self.assertEqual(
			amounts(gk),
			{
				"E8002001": Decimal("88175"),
				"E8002104": Decimal("15000"),
				"E8100301": Decimal("10000"),
				"E8100501": Decimal("825"),
				"E8100601": Decimal("5000"),
				"E8100702": Decimal("15000"),
				"E8101101": Decimal("200"),
				"E8101301": Decimal("900"),
				"E8101401": Decimal("1000"),
				"E8560401": Decimal("12000"),
				"E8560801": Decimal("600"),
				"E8561212": Decimal("30000"),
				"E8561410": Decimal("12000"),
				"E8561301": Decimal("1500"),
				"E8561411": Decimal("4000"),
				"E8562101": Decimal("-23900"),
				"E8109901": Decimal("112200"),
			},
		)

	def test_lines_151_to_155_name_each_holding_with_exempt_dividends(self):
		"""Beta GmbH, held 12 % at the start of the year, is exempt; Gamma AG at 0.5 % is Streubesitz."""
		gk = by_form(koerperschaftsteuer())["GK"]
		rows = {key: value for key, value in values(gk).items() if key[1]}
		self.assertEqual(
			rows,
			{
				("E8560403", (0,)): "Beta GmbH",
				("E8560406", (0,)): Decimal("12"),
				("E8560407", (0,)): "1",
				("E8560404", (0,)): Decimal("12000.00"),
			},
		)

	def test_anlage_zve_holds_lines_2_32_53_and_70_and_the_tax_with_its_base(self):
		zve = by_form(koerperschaftsteuer())["ZVE"]
		self.assertEqual(
			amounts(zve),
			{
				"E8004904": Decimal("112200"),
				"E8005401": Decimal("112200"),
				"E8005601": Decimal("1000"),
				"E8006901": Decimal("111200"),
				"E8007501": Decimal("111200"),
				"E8007504": Decimal("111200"),
				"E8007502": Decimal("16680"),
			},
		)

	def test_anlage_wa_holds_the_credits_of_the_steuerbescheinigungen(self):
		self.assertEqual(
			amounts(by_form(koerperschaftsteuer())["WA"]),
			{"E8120401": Decimal("5000.00"), "E8120601": Decimal("275.00")},
		)

	def test_anlage_z_holds_the_zuwendungen_and_no_anlage_verluste_without_a_loss(self):
		found = by_form(koerperschaftsteuer())
		self.assertEqual(list(found), ["GK", "ZVE", "WA", "Z"])
		self.assertEqual(
			amounts(found["Z"]),
			{
				"E8005602": Decimal("1000"),
				"E8009701": Decimal("1000"),
				"E8006101": Decimal("1000"),
				"E8010101": ZERO,
			},
		)

	def test_a_zero_is_left_out_but_for_the_amounts_the_rules_require(self):
		result = compute(KstInputs(2026, (credit("8400", "0.40"),), MAPPING), FIGURES)
		found = by_form(result)
		self.assertEqual(list(found), ["GK", "ZVE", "WA"])
		self.assertEqual(amounts(found["GK"]), {"E8002001": ZERO, "E8109901": ZERO})
		self.assertEqual(
			amounts(found["ZVE"]),
			{"E8004904": ZERO, "E8005401": ZERO, "E8006901": ZERO, "E8007501": ZERO},
		)
		self.assertEqual(found["WA"].entries, ())


class LossesTest(TestCase):
	"""Anlage Verluste with the lines the rules of the JD ask for in each case."""

	def result(self, profit: str, carry_forward: str = "0", carry_back: str | None = None):
		lines = (credit("8400", profit),) if not profit.startswith("-") else (debit("4120", profit[1:]),)
		inputs = KstInputs(
			2026,
			lines,
			MAPPING,
			loss_carry_forward=Decimal(carry_forward),
			loss_carry_back=None if carry_back is None else Decimal(carry_back),
		)
		return by_form(compute(inputs, FIGURES))

	def test_a_carry_forward_that_the_income_takes_in_full(self):
		self.assertEqual(
			amounts(self.result("300000.00", "200000")["Verluste"]),
			{
				"E8007801": Decimal("200000"),
				"E8008401": Decimal("200000"),
				"E8008501": Decimal("300000"),
				"E8008601": Decimal("200000"),
				"E8008602": Decimal("200000"),
				"E8009201": ZERO,
			},
		)

	def test_the_minimum_taxation_fills_lines_26_and_27(self):
		"""3 Mio € income against 2.5 Mio € carry-forward: 1 Mio € in full, then 70 % of the rest, 1.4 Mio €."""
		self.assertEqual(
			amounts(self.result("3000000.00", "2500000")["Verluste"]),
			{
				"E8007801": Decimal("2500000"),
				"E8008401": Decimal("2500000"),
				"E8008501": Decimal("3000000"),
				"E8008601": Decimal("1000000"),
				"E8008602": Decimal("1000000"),
				"E8008701": Decimal("2000000"),
				"E8008702": Decimal("1500000"),
				"E8008801": Decimal("1400000"),
				"E8009201": Decimal("100000"),
			},
		)

	def test_a_loss_with_its_verlustruecktrag(self):
		self.assertEqual(
			amounts(self.result("-50000.00", "0", "20000")["Verluste"]),
			{"E8008001": Decimal("50000"), "E8008102": Decimal("20000"), "E8009201": Decimal("30000")},
		)

	def test_a_loss_without_a_decision_on_the_verlustruecktrag_leaves_line_20_open(self):
		self.assertEqual(
			amounts(self.result("-50000.00", "10000")["Verluste"]),
			{"E8007801": Decimal("10000"), "E8008001": Decimal("50000"), "E8009201": Decimal("60000")},
		)


class DonationsTest(TestCase):
	def test_a_zuwendungsvortrag_without_zuwendungen_of_the_year_with_the_turnover(self):
		inputs = KstInputs(
			2026,
			(credit("8400", "10000.00"),),
			MAPPING,
			donation_carry_forward=Decimal("5000"),
			turnover_and_wages=Decimal("100000"),
		)
		self.assertEqual(
			amounts(by_form(compute(inputs, FIGURES))["Z"]),
			{
				"E8009401": Decimal("5000"),
				"E8009701": Decimal("5000"),
				"E8006101": Decimal("2000"),
				"E8010101": Decimal("3000"),
				"E8006001": Decimal("100000"),
			},
		)

	def test_a_zve_of_zero_files_no_line_71(self):
		inputs = KstInputs(2026, (debit("4120", "100.00"),), MAPPING, loss_carry_back=ZERO)
		zve = by_form(compute(inputs, FIGURES))["ZVE"]
		self.assertNotIn("E8007504", amounts(zve))
		self.assertNotIn("E8007502", amounts(zve))
		self.assertEqual(amounts(zve)["E8007501"], Decimal("-100"))


class Kst1fTest(TestCase):
	"""KSt 1 F from the steuerliches Einlagekonto of steuerbote.kst.einlagekonto."""

	def test_a_company_without_einlagen_files_zero_to_zero(self):
		vordruck = kst1f(roll_forward(ZERO, FIGURES))
		self.assertEqual((vordruck.form, vordruck.wj), ("KSt1F", "WJ1"))
		self.assertEqual(amounts(vordruck), {"E8240103": ZERO, "E8245601": ZERO})
		self.assertEqual(kst1f(roll_forward(ZERO, FIGURES), wj="WJ2").wj, "WJ2")

	def test_the_einlagen_of_the_year_go_to_lines_91_92_and_95(self):
		account = roll_forward(
			Decimal("1000"),
			FIGURES,
			contributions_booked=Decimal("100"),
			contributions_not_booked=Decimal("200"),
			other_contributions=Decimal("5000"),
		)
		vordruck = kst1f(
			account,
			contributions_booked=Decimal("100"),
			contributions_not_booked=Decimal("200"),
			other_contributions=Decimal("5000"),
		)
		self.assertEqual(
			amounts(vordruck),
			{
				"E8240103": Decimal("1000"),
				"E8241501": Decimal("100"),
				"E8241502": Decimal("200"),
				"E8241601": Decimal("5000"),
				"E8245601": Decimal("6300"),
			},
		)

	def test_the_einlagen_have_to_be_those_the_einlagekonto_took(self):
		account = roll_forward(ZERO, FIGURES, other_contributions=Decimal("5000"))
		with self.assertRaises(ValueError) as raised:
			kst1f(account, contributions_booked=Decimal("5000"), other_contributions=Decimal("5000"))
		self.assertEqual(
			str(raised.exception),
			"the Einlagen of lines 91, 92 and 95 add up to 10000, the Einlagekonto took 5000",
		)

	def test_carries_the_sonderausweis_into_line_152(self):
		account = roll_forward(Decimal("1000"), FIGURES, sonderausweis=Decimal("700"))
		self.assertEqual(
			amounts(kst1f(account)),
			{
				"E8240103": Decimal("1000"),
				"E8240201": Decimal("700"),
				"E8245601": Decimal("1000"),
				"E8245602": Decimal("700"),
			},
		)

	def test_a_distribution_beyond_the_distributable_profit_fills_lines_11_to_20_and_46_to_50(self):
		"""Eigenkapital 60,000 less Nennkapital 25,000 less the Bestand of 30,000 leaves 5,000 to distribute; of the
		Leistungen of 12,000 the Einlagekonto gives the 7,000 beyond, as far as certified."""
		account = roll_forward(
			Decimal("30000"),
			FIGURES,
			distributions=Decimal("12000"),
			certified_reduction=Decimal("7000"),
			previous_equity=Decimal("60000"),
			previous_nominal_capital=Decimal("25000"),
		)
		vordruck = kst1f(account, previous_equity=Decimal("60000"), previous_nominal_capital=Decimal("25000"))
		self.assertEqual(
			amounts(vordruck),
			{
				"E8240103": Decimal("30000"),
				"E8200502": Decimal("12000"),
				"E8122003": Decimal("7000"),
				"E8201001": Decimal("60000"),
				"E8201101": Decimal("25000"),
				"E8201201": Decimal("30000"),
				"E8201301": Decimal("5000"),
				"E8241717": Decimal("30000"),
				"E8240302": Decimal("12000"),
				"E8240401": Decimal("5000"),
				"E8240501": Decimal("7000"),
				"E8242201": Decimal("7000"),
				"E8245601": Decimal("23000"),
			},
		)

	def test_a_distribution_within_the_distributable_profit_leaves_line_46_and_50_out(self):
		account = roll_forward(
			Decimal("30000"),
			FIGURES,
			distributions=Decimal("4000"),
			previous_equity=Decimal("60000"),
			previous_nominal_capital=Decimal("25000"),
		)
		found = amounts(
			kst1f(account, previous_equity=Decimal("60000"), previous_nominal_capital=Decimal("25000"))
		)
		self.assertEqual(found["E8240501"], Decimal("-1000"))
		self.assertNotIn("E8241717", found)
		self.assertNotIn("E8242201", found)
		self.assertEqual(found["E8245601"], Decimal("30000"))

	def test_lines_17_to_20_need_the_equity_the_einlagekonto_was_computed_with(self):
		account = roll_forward(
			Decimal("30000"),
			FIGURES,
			distributions=Decimal("4000"),
			previous_equity=Decimal("60000"),
			previous_nominal_capital=Decimal("25000"),
		)
		with self.assertRaises(ValueError) as raised:
			kst1f(account)
		self.assertEqual(
			str(raised.exception),
			"lines 17 and 18 of KSt 1 F need the Eigenkapital and the Nennkapital of the previous year",
		)
		with self.assertRaises(ValueError) as raised:
			kst1f(account, previous_equity=Decimal("70000"), previous_nominal_capital=Decimal("25000"))
		self.assertEqual(
			str(raised.exception),
			"the Eigenkapital 70000 and the Nennkapital 25000 do not give the ausschüttbarer Gewinn 5000 of the "
			"Einlagekonto",
		)
