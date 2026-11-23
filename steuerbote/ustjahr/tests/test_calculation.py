"""The fields of the Umsatzsteuererklärung from the ledger of the year, and the amounts as the return files them."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.ustjahr.calculation import (
	MANUAL_NO_PARAGRAPH,
	MANUAL_NOT_FED,
	MANUAL_WITHOUT_REASON,
	MESSAGES,
	NACHSTEUER,
	NOT_AN_INPUT,
	NOT_CENTS,
	NOT_WHOLE_EUROS,
	CalculationError,
	FieldValue,
	ManualLine,
	business_period,
	calculate,
	entries,
)
from steuerbote.ustjahr.form import CATALOGUES, SOLL, Finding, Severity
from steuerbote.ustjahr.split import AnnualRule, Choice, split
from steuerbote.ustva import calculate as calculate_ustva
from steuerbote.ustva.calculation import AccountBalance, LedgerLine
from steuerbote.ustva.mapping import AccountRule, Mapping, Side, TaxCheck, WatchedAccount, WatchLevel
from steuerbote.ustva.rounding import ZERO, tax_from_base, to_full_euros

CATALOGUE = CATALOGUES[2026]
RATE_19 = Decimal("19")
MAPPING = Mapping(
	"test",
	(
		AccountRule("8400", "81", Side.CREDIT),
		AccountRule("8910", "81", Side.CREDIT),
		AccountRule("2406", "81", Side.CREDIT, also_kennzahl="50", also_side=Side.DEBIT),
		AccountRule("8300", "86", Side.CREDIT),
		AccountRule("8125", "41", Side.CREDIT),
		AccountRule("8100", "48", Side.CREDIT),
		AccountRule("8105", "48", Side.CREDIT),
		AccountRule("3425", "89", Side.DEBIT),
		AccountRule("3123", "46", Side.DEBIT, RATE_19),
		AccountRule("1576", "66", Side.DEBIT),
		AccountRule("1574", "61", Side.DEBIT),
		AccountRule("1577", "67", Side.DEBIT),
		AccountRule("1558", "64", Side.DEBIT),
		AccountRule("1559", "64", Side.DEBIT),
		AccountRule("1782", "65", Side.CREDIT),
		AccountRule("1794", "69", Side.CREDIT),
	),
	checks=(
		TaxCheck("Umsatzsteuer 19 %", ("8400", "8910", "2406"), ("1776",)),
		TaxCheck("Umsatzsteuer 7 %", ("8300",), ("1771",)),
		TaxCheck("Umsatzsteuer aus innergemeinschaftlichem Erwerb 19 %", ("3425",), ("1774",)),
		TaxCheck("Umsatzsteuer nach § 13b UStG 19 %", ("3123",), ("1787",)),
	),
	watched=("1769", "3075", "3151"),
)
ROLES = {"1558": "E3008701", "1559": "E3008702", "8910": "E3003405", "1794": "E3101702", "8105": "E3104401"}
ANNUAL_RULES = (
	AnnualRule("3552", "E3100801", Side.DEBIT),
	AnnualRule("3075", "E3102804", Side.DEBIT),
	AnnualRule("1769", "E3102805", Side.CREDIT),
	AnnualRule("3553", "E3101701", Side.DEBIT),
)
SPLIT = split(MAPPING, (Choice("8100", "E3104502", "4 Nummer 14"),), ROLES, ANNUAL_RULES)


def line(account: str, debit: str = "0", credit: str = "0", voucher: str | None = None) -> LedgerLine:
	return LedgerLine(account, Decimal(debit), Decimal(credit), voucher)


def sale(
	voucher: str, base: str, account: str = "8400", tax_account: str = "1776", rate: str = "19"
) -> list[LedgerLine]:
	net = Decimal(base)
	tax = tax_from_base(net, Decimal(rate))
	return [
		line("1400", debit=str(net + tax), voucher=voucher),
		line(account, credit=base, voucher=voucher),
		line(tax_account, credit=str(tax), voucher=voucher),
	]


def amounts(result, *elements: str) -> tuple[Decimal, ...]:
	return tuple(result.values[element].amount for element in elements)


class LinesTest(TestCase):
	def test_a_line_holds_the_exact_amount_of_its_accounts_over_the_year(self):
		result = calculate([*sale("R1", "1000.50"), *sale("R2", "234.49")], SPLIT)
		value = result.values["E3003303"]
		self.assertEqual(value, FieldValue("E3003303", Decimal("1234.99"), ZERO, ZERO, Decimal("1234")))
		self.assertEqual(value.amount, Decimal("1234.99"))

	def test_the_lines_of_a_kennzahl_that_splits_add_up_to_it(self):
		lines = [*sale("R1", "1000.00"), *sale("R2", "80.00", account="8910")]
		result = calculate(lines, SPLIT)
		self.assertEqual(amounts(result, "E3003303", "E3003405"), (Decimal("1000.00"), Decimal("80.00")))
		self.assertEqual(result.ustva.values["81"].amount, Decimal("1080.00"))

	def test_bases_are_the_whole_euros_of_the_exact_annual_amount(self):
		result = calculate([line("8400", credit="1234.99"), line("8125", debit="10.50")], SPLIT)
		self.assertEqual(result.values["E3003303"].form, Decimal("1234"))
		self.assertEqual(result.values["E3103301"].form, Decimal("-10"))

	def test_taxes_of_their_own_are_cents(self):
		result = calculate([line("1576", debit="100.01"), line("1576", credit="0.02")], SPLIT)
		self.assertEqual(result.values["E3006201"].form, Decimal("99.99"))

	def test_a_rate_line_takes_its_rate_of_the_exact_annual_base_half_up(self):
		"""Option B of the research: the tax of the exact annual base, unverified as the practice of ERiC."""
		result = calculate(sale("R1", "1000.50"), SPLIT)
		value = result.values["E3003304"]
		self.assertEqual(value.ledger, Decimal("190.0950"))
		self.assertEqual(value.form, Decimal("190.10"))
		self.assertEqual(result.values["E3003303"].form, Decimal("1000"))

	def test_twelve_months_ending_in_99_cents_stay_within_the_euro_of_erics_rate_rule(self):
		"""Rule 30639 allows 1 euro between the tax and 19 % of the base filed in whole euros. Twelve Voranmeldungen
		of 100.99 each filed 100 euros and 19.00 euros, 228.00 together, 2.09 euros off 19 % of the 1211 euros of the
		year; the tax of the exact annual base is 0.17 euros off."""
		months = [line("8400", credit="100.99", voucher=f"R{month}") for month in range(1, 13)]
		monthly = sum((tax_from_base(to_full_euros(Decimal("100.99")), RATE_19) for _ in range(12)), ZERO)
		result = calculate(months, SPLIT)
		base, tax = result.values["E3003303"].form, result.values["E3003304"].form
		self.assertEqual((base, tax, monthly), (Decimal("1211"), Decimal("230.26"), Decimal("228.00")))
		self.assertGreater(abs(monthly - base * RATE_19 / 100), Decimal("1"))
		self.assertLessEqual(abs(tax - base * RATE_19 / 100), Decimal("0.19"))

	def test_a_tax_of_its_own_is_derived_per_voucher_as_in_the_voranmeldung(self):
		lines = [line("3123", debit="33.33", voucher=f"E{number}") for number in range(3)]
		lines += [line("1577", debit="6.33", voucher=f"E{number}") for number in range(3)]
		result = calculate(lines, SPLIT)
		self.assertEqual(amounts(result, "E3102205", "E3102206"), (Decimal("99.99"), Decimal("18.99")))
		self.assertEqual(result.values["E3102206"].amount, result.ustva.values["47"].amount)
		self.assertEqual(result.values["E3006502"].amount, Decimal("18.99"))

	def test_a_mapped_tax_account_feeds_the_tax_of_its_line(self):
		mapping = Mapping(
			"test",
			(AccountRule("3123", "46", Side.DEBIT), AccountRule("1787", "47", Side.CREDIT)),
		)
		result = calculate([line("3123", debit="100.00"), line("1787", credit="19.00")], split(mapping))
		self.assertEqual(amounts(result, "E3102205", "E3102206"), (Decimal("100.00"), Decimal("19.00")))

	def test_the_informational_kennzahl_of_a_rule_goes_to_its_line(self):
		"""A bad debt reduces Kz 81 and reports the reduction in Kz 50, which is Kz 650 in line 84."""
		result = calculate([line("2406", debit="500.00")], SPLIT)
		self.assertEqual(amounts(result, "E3003303", "E3106101"), (Decimal("-500.00"), Decimal("500.00")))

	def test_a_repayment_under_section_15a_goes_into_its_column_without_sign(self):
		result = calculate([line("1559", credit="500.00"), line("1558", debit="1500.00")], SPLIT)
		self.assertEqual(amounts(result, "E3008701", "E3008702"), (Decimal("1500.00"), Decimal("500.00")))
		self.assertEqual(result.ustva.values["64"].amount, Decimal("1000.00"))

	def test_accounts_only_the_annual_return_reads_add_their_balance(self):
		lines = [line("3552", debit="2000.00"), line("3075", debit="400.00"), line("1769", credit="76.00")]
		result = calculate(lines, SPLIT)
		self.assertEqual(
			result.values["E3100801"], FieldValue("E3100801", ZERO, Decimal("2000.00"), ZERO, Decimal("2000"))
		)
		self.assertEqual(amounts(result, "E3102804", "E3102805"), (Decimal("400.00"), Decimal("76.00")))

	def test_lines_by_hand_add_their_amount(self):
		manual = (ManualLine("E3008701", Decimal("300.00"), "§ 44 Absatz 3 UStDV, not booked"),)
		result = calculate([line("1558", debit="1500.00")], SPLIT, manual)
		value = result.values["E3008701"]
		self.assertEqual(
			(value.ledger, value.manual, value.amount),
			(Decimal("1500.00"), Decimal("300.00"), Decimal("1800.00")),
		)
		self.assertEqual(result.manual, manual)

	def test_a_line_by_hand_on_a_base_moves_its_rate_line(self):
		result = calculate([], SPLIT, (ManualLine("E3003303", Decimal("100.00"), "a sale the books lack"),))
		self.assertEqual(
			result.values["E3003304"],
			FieldValue("E3003304", ZERO, ZERO, Decimal("19.0000"), Decimal("19.00")),
		)

	def test_only_the_fields_with_an_amount_are_listed_in_the_order_of_the_form(self):
		result = calculate([line("1576", debit="10.00"), *sale("R1", "100.00")], SPLIT)
		self.assertEqual(list(result.values), ["E3003303", "E3003304", "E3006201"])
		self.assertEqual(calculate([], SPLIT).values, {})

	def test_the_reported_amounts_are_those_of_the_form(self):
		result = calculate(sale("R1", "1000.50"), SPLIT)
		self.assertEqual(dict(result.reported), {"E3003303": Decimal("1000"), "E3003304": Decimal("190.10")})

	def test_takes_the_year_of_the_split(self):
		self.assertEqual(calculate([], SPLIT).year, 2026)


class KennzahlenOfTheYearTest(TestCase):
	"""The lines hold the amounts of the Kennzahlen of the Voranmeldung over the year, Kennzahl by Kennzahl."""

	def test_the_lines_of_each_kennzahl_add_up_to_its_amount_over_the_year(self):
		lines = [
			*sale("R1", "1000.50"),
			*sale("R2", "80.33", account="8910"),
			*sale("R3", "70.00", account="8300", tax_account="1771", rate="7"),
			line("2406", debit="100.00", voucher="A1"),
			line("1776", debit="19.00", voucher="A1"),
			line("8125", credit="5000.00", voucher="R4"),
			line("8100", credit="1200.00", voucher="R5"),
			line("8105", credit="800.00", voucher="R6"),
			line("3425", debit="300.00", voucher="E1"),
			line("1774", credit="57.00", voucher="E1"),
			line("1574", debit="57.00", voucher="E1"),
			*[line("3123", debit="33.33", voucher=f"E{number}") for number in range(2, 5)],
			*[line("1787", credit="6.33", voucher=f"E{number}") for number in range(2, 5)],
			line("1577", debit="18.99", voucher="E5"),
			line("1576", debit="250.00", voucher="E6"),
			line("1558", debit="300.00", voucher="J1"),
			line("1559", credit="120.00", voucher="J2"),
			line("1782", credit="40.00", voucher="J3"),
			line("1794", credit="38.00", voucher="J4"),
		]
		result = calculate(lines, SPLIT)
		year = calculate_ustva(lines, MAPPING)
		self.assertEqual(result.ustva, year)
		for number, value in year.values.items():
			if number == "83":
				continue
			children = CATALOGUE.children(number)
			with self.subTest(kennzahl=number):
				total = sum(
					(
						child.sign * result.values[child.element].ledger
						for child in children
						if child.element in result.values
					),
					ZERO,
				)
				self.assertEqual(total, value.amount)


class VerprobungTest(TestCase):
	def test_the_verprobung_and_the_watched_accounts_come_from_one_run_over_the_year(self):
		lines = [*sale("R1", "100.00"), line("8400", credit="10.00", voucher="R2")]
		result = calculate(lines, SPLIT)
		self.assertEqual(result.checks, calculate_ustva(lines, MAPPING).checks)
		self.assertFalse(result.checks[0].passed)
		self.assertFalse(result.ready)
		self.assertTrue(calculate(sale("R1", "100.00"), SPLIT).ready)

	def test_a_watched_account_blocks_unless_the_annual_return_reads_it(self):
		result = calculate(
			[line("3151", debit="10.00"), line("3075", debit="10.00"), line("1769", credit="1.90")], SPLIT
		)
		self.assertEqual(result.ustva.unmapped, ("1769", "3075", "3151"))
		self.assertEqual(result.unmapped, ("3151",))
		self.assertFalse(result.ready)
		self.assertTrue(calculate([line("3075", debit="10.00")], SPLIT).ready)

	def test_the_accounts_watched_for_a_hint_come_along(self):
		mapping = Mapping(
			"test",
			(AccountRule("8400", "81", Side.CREDIT),),
			watched=(WatchedAccount("8603", WatchLevel.HINT),),
		)
		result = calculate([line("8603", credit="12.00")], split(mapping))
		self.assertEqual(result.hinted, (AccountBalance("8603", ZERO, Decimal("12.00")),))
		self.assertTrue(result.ready)


class ParagraphTest(TestCase):
	"""Lines 46, 52 and 54: „Umsätze nach § … UStG“ (form USt 2 A 2026)."""

	def test_the_paragraph_of_an_account_with_a_balance_names_its_line(self):
		result = calculate([line("8100", credit="1200.00")], SPLIT)
		self.assertEqual(dict(result.paragraphs), {"E3104501": ("4 Nummer 14",)})

	def test_an_account_without_a_balance_names_no_paragraph(self):
		result = calculate([line("8100", credit="1200.00"), line("8100", debit="1200.00")], SPLIT)
		self.assertEqual(dict(result.paragraphs), {})

	def test_the_paragraphs_of_several_accounts_and_lines_by_hand_are_kept_once_in_order(self):
		mapping = Mapping(
			"test",
			(
				AccountRule("8100", "48", Side.CREDIT),
				AccountRule("8101", "48", Side.CREDIT),
				AccountRule("8102", "48", Side.CREDIT),
			),
		)
		choices = (
			Choice("8100", "E3104502", "4 Nummer 14"),
			Choice("8101", "E3104502", "4 Nummer 16"),
			Choice("8102", "E3104502", "4 Nummer 14"),
		)
		manual = (ManualLine("E3104502", Decimal("10.00"), "by hand", "4 Nummer 21"),)
		lines = [line(account, credit="10.00") for account in ("8100", "8101", "8102")]
		result = calculate(lines, split(mapping, choices), manual)
		self.assertEqual(dict(result.paragraphs), {"E3104501": ("4 Nummer 14", "4 Nummer 16", "4 Nummer 21")})


class NachsteuerTest(TestCase):
	"""Kz 65 holds the Steuer infolge des Wechsels der Besteuerungsform and the Nachsteuer wegen Steuersatzänderung
	(USt 1 A 2026, line 46), which the annual return parts into line 39 (Kz 317) and line 40 (Kz 319)."""

	def test_a_kz_65_by_default_goes_into_kz_319_with_a_hint(self):
		result = calculate([line("1782", credit="40.00")], SPLIT)
		self.assertEqual(result.values["E3005901"].amount, Decimal("40.00"))
		self.assertEqual(
			result.findings,
			(Finding("NACHSTEUER-ZEILE", Severity.HINT, NACHSTEUER, ("1782",), ("E3005901", "E3102901")),),
		)
		self.assertEqual(
			result.findings[0].text,
			"The Nachsteuer of account 1782 goes into Kz 319 (line 40), the Nachsteuer wegen Steuersatzänderung. "
			"Steuer infolge des Wechsels der Besteuerungsform belongs in Kz 317 (line 39): give the mapping rule "
			"that annual field if it applies.",
		)

	def test_no_hint_without_a_balance_or_with_an_annual_field_of_the_rule(self):
		self.assertEqual(calculate([], SPLIT).findings, ())
		chosen = split(MAPPING, (Choice("1782", "E3102901"),), ROLES, ANNUAL_RULES)
		result = calculate([line("1782", credit="40.00")], chosen)
		self.assertEqual((result.values["E3102901"].amount, result.findings), (Decimal("40.00"), ()))


class ManualLineTest(TestCase):
	def test_a_line_by_hand_needs_a_reason(self):
		for reason in ("", "   "):
			with self.subTest(reason=reason), self.assertRaises(CalculationError) as caught:
				ManualLine("E3008701", Decimal("1.00"), reason)
			self.assertEqual(
				(caught.exception.template, caught.exception.values), (MANUAL_WITHOUT_REASON, ("E3008701",))
			)

	def test_a_line_by_hand_is_in_cents(self):
		with self.assertRaisesRegex(ValueError, "ledger amounts must be finite cents"):
			ManualLine("E3008701", Decimal("1.001"), "reason")
		with self.assertRaises(TypeError):
			ManualLine("E3008701", 1.0, "reason")  # type: ignore[arg-type]

	def test_refuses_a_paragraph_for_a_line_that_names_none(self):
		with self.assertRaises(CalculationError) as caught:
			calculate([], SPLIT, (ManualLine("E3003303", Decimal("1.00"), "reason", "4 Nummer 1"),))
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (MANUAL_NO_PARAGRAPH, ("E3003303",))
		)

	def test_refuses_a_line_by_hand_for_a_field_no_account_feeds(self):
		for element in ("E3003304", "E3006001", "E3000901", SOLL, "E3005401", "E9999999"):
			with self.subTest(element=element), self.assertRaises(CalculationError) as caught:
				calculate([], SPLIT, (ManualLine(element, Decimal("1.00"), "reason"),))
			self.assertEqual(
				(caught.exception.template, caught.exception.values), (MANUAL_NOT_FED, (element,))
			)


EXAMPLE_2026 = {
	"E3003405": Decimal("5276"),
	"E3003406": Decimal("1002.44"),
	"E3003703": Decimal("-14292"),
	"E3003704": Decimal("-1000.44"),
}


class EntriesTest(TestCase):
	"""The amounts as the return files them: zeros left out, pairs together, the sums of the form, Kz 816, line 125
	and Kz 820 always."""

	def test_the_example_of_the_eric_documentation(self):
		"""Beispiele/USt_2026.xml of the ERiC documentation 44.3.6.0: its amounts and its section K."""
		self.assertEqual(
			dict(entries(CATALOGUE, EXAMPLE_2026, Decimal("902.00"))),
			{
				**EXAMPLE_2026,
				"E3006001": Decimal("2.00"),
				"E3009201": Decimal("2.00"),
				"E3009801": Decimal("2.00"),
				"E3010201": Decimal("2.00"),
				"E3010601": Decimal("2.00"),
				"E3011101": Decimal("2.00"),
				"E3011301": Decimal("902.00"),
				"E3011401": Decimal("-900.00"),
			},
		)

	def test_follows_the_order_of_the_form(self):
		filed = entries(CATALOGUE, {"E3006201": Decimal("10.00"), **EXAMPLE_2026}, ZERO)
		order = [field.element for field in CATALOGUE.fields]
		self.assertEqual(list(filed), sorted(filed, key=order.index))

	def test_leaves_zeros_out(self):
		filed = entries(CATALOGUE, {**EXAMPLE_2026, "E3006201": ZERO, "E3103301": ZERO}, ZERO)
		self.assertNotIn("E3006201", filed)
		self.assertNotIn("E3103301", filed)
		self.assertNotIn("E3006901", filed)

	def test_files_a_base_and_its_tax_together(self):
		"""Rule 30649 takes Kz 177 and its tax only together: a base of 0.40 euros is 0 euros with 0.08 euros tax."""
		filed = entries(CATALOGUE, {"E3003303": ZERO, "E3003304": Decimal("0.08")}, ZERO)
		self.assertEqual((filed["E3003303"], filed["E3003304"]), (ZERO, Decimal("0.08")))
		filed = entries(CATALOGUE, {"E3002801": Decimal("10")}, ZERO)
		self.assertNotIn("E3003303", filed)

	def test_a_sum_is_filed_when_a_part_is_even_if_it_is_zero(self):
		filed = entries(CATALOGUE, {"E3006201": Decimal("10.00"), "E3006401": Decimal("-10.00")}, ZERO)
		self.assertEqual((filed["E3006901"], filed["E3009901"], filed["E3010201"]), (ZERO, ZERO, ZERO))
		self.assertNotIn("E3006001", filed)
		self.assertNotIn("E3009201", filed)
		self.assertNotIn("E3009801", filed)

	def test_section_k_follows_the_form(self):
		values = {
			"E3003303": Decimal("10000"),
			"E3003304": Decimal("1900.00"),
			"E3100902": Decimal("1000"),
			"E3100903": Decimal("190.00"),
			"E3102805": Decimal("38.00"),
			"E3101702": Decimal("19.00"),
			"E3102206": Decimal("57.00"),
			"E3006201": Decimal("500.00"),
			"E3006301": Decimal("190.00"),
			"E3008701": Decimal("100.00"),
			"E3008802": Decimal("40.00"),
			"E3010301": Decimal("5.00"),
			"E3010401": Decimal("3.00"),
		}
		filed = entries(CATALOGUE, values, Decimal("1000.00"))
		expected = {
			"E3006001": "1900.00",
			"E3101501": "190.00",
			"E3102904": "38.00",
			"E3102401": "19.00",
			"E3102601": "57.00",
			"E3006901": "690.00",
			"E3008901": "100.00",
			"E3008902": "40.00",
			"E3009201": "1900.00",
			"E3009401": "190.00",
			"E3009602": "38.00",
			"E3009501": "19.00",
			"E3009502": "57.00",
			"E3009801": "2204.00",
			"E3009901": "690.00",
			"E3010001": "100.00",
			"E3010201": "1414.00",
			"E3009701": "40.00",
			"E3010601": "1462.00",
			"E3011101": "1462.00",
			"E3011301": "1000.00",
			"E3011401": "462.00",
		}
		for element, amount in expected.items():
			with self.subTest(element=element):
				self.assertEqual(filed[element], Decimal(amount))

	def test_kz_816_line_125_and_kz_820_are_always_filed(self):
		"""Rules 30070, 30915 and 30620."""
		filed = entries(CATALOGUE, {"E3103301": Decimal("100")}, Decimal("-50.00"))
		self.assertEqual(
			{element: filed[element] for element in ("E3011101", SOLL, "E3011401")},
			{"E3011101": ZERO, SOLL: Decimal("-50.00"), "E3011401": Decimal("50.00")},
		)

	def test_a_year_without_amounts_files_kz_177_with_zero(self):
		"""Rule 30449 wants one amount of the form; the research suggests Kz 177 = 0 with its tax, unverified."""
		self.assertEqual(
			dict(entries(CATALOGUE, {}, Decimal("100.00"))),
			{
				"E3003303": ZERO,
				"E3003304": ZERO,
				"E3006001": ZERO,
				"E3009201": ZERO,
				"E3009801": ZERO,
				"E3010201": ZERO,
				"E3010601": ZERO,
				"E3011101": ZERO,
				"E3011301": Decimal("100.00"),
				"E3011401": Decimal("-100.00"),
			},
		)
		self.assertIn("E3003303", entries(CATALOGUE, {"E3003303": ZERO}, ZERO))

	def test_refuses_an_amount_for_a_field_the_form_computes_or_the_company_states(self):
		for element in ("E3006001", SOLL, "E3011101", "E3000901", "E9999999"):
			with self.subTest(element=element), self.assertRaises(CalculationError) as caught:
				entries(CATALOGUE, {element: Decimal("1.00")}, ZERO)
			self.assertEqual((caught.exception.template, caught.exception.values), (NOT_AN_INPUT, (element,)))

	def test_refuses_cents_where_the_form_takes_whole_euros(self):
		with self.assertRaises(CalculationError) as caught:
			entries(CATALOGUE, {"E3003303": Decimal("10.50")}, ZERO)
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (NOT_WHOLE_EUROS, ("E3003303", "10.50"))
		)

	def test_refuses_fractions_of_a_cent(self):
		with self.assertRaises(CalculationError) as caught:
			entries(CATALOGUE, {"E3006201": Decimal("10.005")}, ZERO)
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (NOT_CENTS, ("E3006201", "10.005"))
		)
		with self.assertRaises(CalculationError) as caught:
			entries(CATALOGUE, {}, Decimal("0.001"))
		self.assertEqual((caught.exception.template, caught.exception.values), (NOT_CENTS, (SOLL, "0.001")))

	def test_takes_decimals_only(self):
		with self.assertRaises(TypeError):
			entries(CATALOGUE, {"E3006201": 10.0}, ZERO)  # type: ignore[dict-item]


class BusinessPeriodTest(TestCase):
	"""Lines 19 and 20: „Dauer der Unternehmereigenschaft (falls nicht vom 1. Januar bis zum 31. Dezember 2026)“."""

	def test_a_company_founded_during_the_year_files_from_its_start(self):
		self.assertEqual(business_period(2026, date(2026, 3, 15)), (date(2026, 3, 15), date(2026, 12, 31)))

	def test_a_company_of_the_whole_year_names_no_period(self):
		for began in (None, date(2026, 1, 1), date(2019, 6, 1)):
			with self.subTest(began=began):
				self.assertIsNone(business_period(2026, began))

	def test_a_company_founded_after_the_year_files_no_return_for_it(self):
		with self.assertRaisesRegex(ValueError, "began on 2027-01-04, after 2026"):
			business_period(2026, date(2027, 1, 4))


class MessagesTest(TestCase):
	def test_lists_every_template_once_for_the_translations(self):
		self.assertEqual(
			MESSAGES,
			(
				MANUAL_WITHOUT_REASON,
				MANUAL_NOT_FED,
				MANUAL_NO_PARAGRAPH,
				NOT_AN_INPUT,
				NOT_WHOLE_EUROS,
				NOT_CENTS,
				NACHSTEUER,
			),
		)

	def test_an_error_keeps_template_and_values_apart(self):
		error = CalculationError(NOT_AN_INPUT, "E3006001")
		self.assertEqual(
			(error.template, error.values, str(error)),
			(NOT_AN_INPUT, ("E3006001",), NOT_AN_INPUT.format("E3006001")),
		)
		self.assertIsInstance(error, ValueError)
