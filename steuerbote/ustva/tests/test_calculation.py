from decimal import Decimal
from typing import ClassVar
from unittest import TestCase

from steuerbote.ustva.calculation import (
	TOLERANCE_PER_VOUCHER,
	AccountBalance,
	CheckResult,
	Deviation,
	LedgerLine,
	UstvaResult,
	calculate,
	require_cents,
)
from steuerbote.ustva.defaults import SKR03, SKR04
from steuerbote.ustva.mapping import AccountRule, Mapping, Side, TaxCheck, WatchedAccount, WatchLevel


def line(account: str, debit: str = "0", credit: str = "0", voucher: str | None = None) -> LedgerLine:
	return LedgerLine(account, Decimal(debit), Decimal(credit), voucher)


def d(value: str) -> Decimal:
	return Decimal(value)


def check_of(result: UstvaResult, tax_account: str) -> CheckResult:
	return next(check for check in result.checks if check.tax_accounts == (tax_account,))


class LedgerLineTest(TestCase):
	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			LedgerLine("8400", 0.0, 100.0)  # type: ignore[arg-type]

	def test_rejects_amounts_finer_than_cents(self):
		with self.assertRaisesRegex(ValueError, "finite cents"):
			line("8400", credit="0.001")

	def test_rejects_non_finite_amounts(self):
		for value in ("NaN", "Infinity", "-Infinity"):
			with self.assertRaisesRegex(ValueError, "finite cents"):
				line("8400", credit=value)

	def test_accepts_whole_euros_and_cents(self):
		self.assertEqual(require_cents(d("100")), d("100"))
		self.assertEqual(require_cents(d("100.10")), d("100.10"))

	def test_balance_by_side(self):
		posting = line("8400", debit="10", credit="110")
		self.assertEqual(posting.balance(Side.CREDIT), d("100"))
		self.assertEqual(posting.balance(Side.DEBIT), d("-100"))

	def test_rejects_account_numbers_that_no_rule_could_match(self):
		for account in (8400, None, "", " 8400", "8400 "):
			with self.subTest(account=account), self.assertRaisesRegex(ValueError, "not an account number"):
				LedgerLine(account, credit=d("100"))  # type: ignore[arg-type]

	def test_voucher_is_optional(self):
		self.assertIsNone(line("8400", credit="100").voucher)
		self.assertEqual(
			line("8400", credit="100", voucher="ACC-SINV-2026-00001").voucher, "ACC-SINV-2026-00001"
		)

	def test_voucher_must_be_a_non_empty_string(self):
		for voucher in ("", 1):
			with self.subTest(voucher=voucher), self.assertRaisesRegex(ValueError, "voucher"):
				LedgerLine("8400", credit=d("100"), voucher=voucher)  # type: ignore[arg-type]


class VerifiedMonthTest(TestCase):
	"""The month verified against a real ERPNext ledger in November 2026."""

	mapping: ClassVar[Mapping] = SKR03
	accounts: ClassVar[dict[str, str]] = {
		"revenue_19": "8400",
		"output_tax_19": "1776",
		"revenue_eu_service": "8336",
		"revenue_third_country": "8338",
		"eu_service_19": "3123",
		"output_tax_13b_19": "1787",
		"input_tax_13b_19": "1577",
		"input_tax_19": "1576",
	}

	def setUp(self):
		a = self.accounts
		self.result = calculate(
			[
				line(a["revenue_19"], credit="1000"),
				line(a["output_tax_19"], credit="190"),
				line(a["revenue_eu_service"], credit="2000"),
				line(a["revenue_third_country"], credit="500"),
				line(a["eu_service_19"], debit="300"),
				line(a["output_tax_13b_19"], credit="57"),
				line(a["input_tax_13b_19"], debit="57"),
				line(a["input_tax_19"], debit="95"),
			],
			self.mapping,
		)

	def test_bases(self):
		self.assertEqual(self.result.reported("81"), d("1000"))
		self.assertEqual(self.result.reported("21"), d("2000"))
		self.assertEqual(self.result.reported("45"), d("500"))
		self.assertEqual(self.result.reported("46"), d("300"))

	def test_taxes(self):
		self.assertEqual(self.result.reported("47"), d("57.00"))
		self.assertEqual(self.result.reported("66"), d("95.00"))
		self.assertEqual(self.result.reported("67"), d("57.00"))

	def test_sums_follow_the_form(self):
		self.assertEqual(self.result.output_tax, d("247.00"))
		self.assertEqual(self.result.input_tax, d("152.00"))
		self.assertEqual(self.result.other_tax, d("0.00"))
		self.assertEqual(self.result.sondervorauszahlung, d("0.00"))
		self.assertEqual(self.result.remaining_tax, d("95.00"))
		self.assertEqual(self.result.prepayment, d("95.00"))
		self.assertEqual(self.result.kz83, d("95.00"))
		self.assertEqual(self.result.reported("83"), d("95.00"))

	def test_every_check_passes_and_the_result_is_ready(self):
		for check in self.result.checks:
			self.assertTrue(check.passed, check)
			self.assertEqual(check.deviations, ())
		output_tax_19 = check_of(self.result, self.accounts["output_tax_19"])
		self.assertEqual(output_tax_19.computed_tax, d("190.00"))
		self.assertEqual(output_tax_19.booked_tax, d("190.00"))
		output_tax_13b_19 = check_of(self.result, self.accounts["output_tax_13b_19"])
		self.assertEqual(output_tax_13b_19.computed_tax, d("57.00"))
		self.assertEqual(output_tax_13b_19.booked_tax, d("57.00"))
		self.assertEqual(self.result.unmapped, ())
		self.assertTrue(self.result.ready)

	def test_only_kennzahlen_with_postings_are_reported_plus_83(self):
		self.assertEqual(set(self.result.values), {"81", "21", "45", "46", "47", "66", "67", "83"})

	def test_values_are_read_only(self):
		with self.assertRaises(TypeError):
			self.result.values["81"] = self.result.values["21"]  # type: ignore[index]


class Skr04MonthTest(VerifiedMonthTest):
	"""The verified month booked on the SKR04 accounts of the same roles gives the same Voranmeldung."""

	mapping: ClassVar[Mapping] = SKR04
	accounts: ClassVar[dict[str, str]] = {
		"revenue_19": "4400",
		"output_tax_19": "3806",
		"revenue_eu_service": "4336",
		"revenue_third_country": "4338",
		"eu_service_19": "5923",
		"output_tax_13b_19": "3837",
		"input_tax_13b_19": "1407",
		"input_tax_19": "1406",
	}


class ReverseChargeTest(TestCase):
	def test_service_of_a_non_eu_business_goes_to_84_and_85(self):
		result = calculate(
			[line("3125", debit="1000"), line("1787", credit="190"), line("1577", debit="190")], SKR03
		)
		self.assertEqual(result.reported("84"), d("1000"))
		self.assertEqual(result.reported("85"), d("190.00"))
		self.assertNotIn("46", result.values)
		self.assertNotIn("47", result.values)
		self.assertEqual(result.reported("67"), d("190.00"))
		self.assertEqual(result.kz83, d("0.00"))
		self.assertTrue(result.ready)

	def test_service_of_a_non_eu_business_at_7_percent_goes_to_84_and_85(self):
		result = calculate(
			[line("3115", debit="1000"), line("1785", credit="70"), line("1578", debit="70")], SKR03
		)
		self.assertEqual(result.reported("84"), d("1000"))
		self.assertEqual(result.reported("85"), d("70.00"))
		self.assertEqual(result.reported("67"), d("70.00"))
		self.assertEqual(result.kz83, d("0.00"))
		self.assertTrue(result.ready)

	def test_eu_and_non_eu_services_share_the_19_percent_tax_account(self):
		result = calculate(
			[
				line("3123", debit="300"),
				line("3125", debit="1000"),
				line("1787", credit="247"),
				line("1577", debit="247"),
			],
			SKR03,
		)
		self.assertEqual(result.reported("47"), d("57.00"))
		self.assertEqual(result.reported("85"), d("190.00"))
		check = check_of(result, "1787")
		self.assertEqual(check.computed_tax, d("247.00"))
		self.assertTrue(check.passed)

	def test_reverse_charge_at_7_percent_nets_to_zero(self):
		result = calculate(
			[line("3113", debit="1000"), line("1785", credit="70"), line("1578", debit="70")], SKR03
		)
		self.assertEqual(result.reported("46"), d("1000"))
		self.assertEqual(result.reported("47"), d("70.00"))
		self.assertEqual(result.reported("67"), d("70.00"))
		self.assertEqual(result.kz83, d("0.00"))
		self.assertTrue(result.ready)

	def test_credit_note_reduces_the_base_and_its_tax(self):
		result = calculate(
			[line("3123", credit="100"), line("1787", debit="19"), line("1577", credit="19")], SKR03
		)
		self.assertEqual(result.reported("46"), d("-100"))
		self.assertEqual(result.reported("47"), d("-19.00"))
		self.assertEqual(result.reported("67"), d("-19.00"))
		self.assertEqual(result.kz83, d("0.00"))
		self.assertTrue(result.ready)

	def test_booked_13b_tax_that_does_not_match_the_bases_fails_the_check(self):
		result = calculate([line("3123", debit="300"), line("1787", credit="60")], SKR03)
		self.assertEqual(result.reported("47"), d("57.00"))
		check = check_of(result, "1787")
		self.assertEqual(check.difference, d("3.00"))
		self.assertEqual(check.deviations, (Deviation(None, d("57.00"), d("60.00")),))
		self.assertFalse(check.passed)
		self.assertFalse(result.ready)


class AcquisitionTest(TestCase):
	def test_acquisition_at_19_percent(self):
		result = calculate(
			[line("3425", debit="1000"), line("1774", credit="190"), line("1574", debit="190")], SKR03
		)
		self.assertEqual(result.reported("89"), d("1000"))
		self.assertEqual(result.reported("61"), d("190.00"))
		self.assertEqual(result.output_tax, d("190.00"))
		self.assertEqual(result.kz83, d("0.00"))
		self.assertTrue(result.ready)

	def test_reduced_rates(self):
		result = calculate(
			[
				line("8300", credit="1000"),
				line("1771", credit="70"),
				line("3420", debit="500"),
				line("1772", credit="35"),
				line("1572", debit="35"),
			],
			SKR03,
		)
		self.assertEqual(result.reported("86"), d("1000"))
		self.assertEqual(result.reported("93"), d("500"))
		self.assertEqual(result.reported("61"), d("35.00"))
		self.assertEqual(result.output_tax, d("105.00"))
		self.assertEqual(result.kz83, d("70.00"))
		self.assertTrue(result.ready)


class VoucherRoundingTest(TestCase):
	"""The books round the tax of each document, so the derived tax is rounded per voucher as well."""

	def test_derived_tax_is_rounded_per_voucher_and_nets_to_zero_with_the_booked_input_tax(self):
		lines = []
		for number in (1, 2, 3):
			voucher = f"ACC-PINV-2026-0000{number}"
			lines += [
				line("3123", debit="33.33", voucher=voucher),
				line("1787", credit="6.33", voucher=voucher),
				line("1577", debit="6.33", voucher=voucher),
			]
		result = calculate(lines, SKR03)
		self.assertEqual(result.values["46"].amount, d("99.99"))
		self.assertEqual(result.reported("46"), d("99"))
		self.assertEqual(result.values["47"].amount, d("18.99"))
		self.assertEqual(result.reported("47"), d("18.99"))
		self.assertEqual(result.reported("67"), d("18.99"))
		self.assertEqual(result.kz83, d("0.00"))
		self.assertEqual(check_of(result, "1787").deviations, ())
		self.assertTrue(result.ready)

	def test_lines_without_voucher_are_rounded_once_per_kennzahl_and_rate(self):
		lines = [line("3123", debit="33.33"), line("1787", credit="6.33"), line("1577", debit="6.33")] * 3
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("47"), d("19.00"))
		self.assertEqual(result.reported("67"), d("18.99"))
		self.assertEqual(result.kz83, d("0.01"))

	def test_vouchers_and_lines_without_voucher_are_rounded_separately(self):
		lines = [
			line("3123", debit="33.33", voucher="ACC-PINV-2026-00001"),
			line("3123", debit="33.33"),
			line("3123", debit="33.33", voucher="ACC-PINV-2026-00002"),
			line("3123", debit="33.33"),
		]
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("47"), d("6.33") + d("6.33") + d("12.67"))

	def test_rates_of_one_voucher_are_rounded_separately(self):
		lines = [
			line("3123", debit="33.33", voucher="ACC-PINV-2026-00001"),
			line("3113", debit="33.33", voucher="ACC-PINV-2026-00001"),
		]
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("47"), d("6.33") + d("2.33"))

	def test_accounts_of_one_kennzahl_and_rate_are_rounded_together_per_voucher(self):
		lines = [
			line("3125", debit="33.33", voucher="ACC-PINV-2026-00001"),
			line("3120", debit="33.33", voucher="ACC-PINV-2026-00001"),
		]
		self.assertEqual(calculate(lines, SKR03).reported("85"), d("12.67"))

	def test_one_tax_line_for_two_kennzahlen_can_leave_a_cent_in_kz_83(self):
		voucher = "ACC-PINV-2026-00001"
		lines = [
			line("3123", debit="33.33", voucher=voucher),
			line("3125", debit="33.33", voucher=voucher),
			line("1787", credit="12.67", voucher=voucher),
			line("1577", debit="12.67", voucher=voucher),
		]
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("47"), d("6.33"))
		self.assertEqual(result.reported("85"), d("6.33"))
		self.assertEqual(result.reported("67"), d("12.67"))
		self.assertEqual(result.kz83, d("-0.01"))
		check = check_of(result, "1787")
		self.assertEqual(check.computed_tax, d("12.67"))
		self.assertTrue(check.passed)

	def test_lines_of_one_voucher_on_one_account_are_summed_before_rounding(self):
		lines = [
			line("3123", debit="0.03", voucher="ACC-PINV-2026-00001"),
			line("3123", debit="0.03", voucher="ACC-PINV-2026-00001"),
		]
		self.assertEqual(calculate(lines, SKR03).reported("47"), d("0.01"))

	def test_lines_can_come_from_a_generator(self):
		result = calculate((line("8400", credit="100", voucher=f"V{n}") for n in range(3)), SKR03)
		self.assertEqual(result.reported("81"), d("300"))
		self.assertEqual(check_of(result, "1776").computed_tax, d("57.00"))


BAD_DEBT_MAPPING = Mapping(
	"own",
	(
		AccountRule("8400", "81", Side.CREDIT),
		AccountRule("2406", "81", Side.CREDIT, also_kennzahl="50", also_side=Side.DEBIT),
	),
	(TaxCheck("Umsatzsteuer 19 %", ("8400", "2406"), ("1776",)),),
)


class AlsoKennzahlTest(TestCase):
	"""Line 51: a bad debt reduces Kz 81 and is reported in Kz 50 as well."""

	lines: ClassVar[list[LedgerLine]] = [
		line("8400", credit="1000", voucher="ACC-SINV-2026-00001"),
		line("1776", credit="190", voucher="ACC-SINV-2026-00001"),
		line("2406", debit="100", voucher="ACC-JV-2026-00001"),
		line("1776", debit="19", voucher="ACC-JV-2026-00001"),
		line("1400", credit="119", voucher="ACC-JV-2026-00001"),
	]

	def test_bad_debt_reduces_kz_81_and_is_reported_in_kz_50(self):
		result = calculate(self.lines, BAD_DEBT_MAPPING)
		self.assertEqual(result.reported("81"), d("900"))
		self.assertEqual(result.reported("50"), d("100"))
		self.assertEqual(result.output_tax, d("171.00"))
		self.assertEqual(result.kz83, d("171.00"))
		self.assertTrue(check_of(result, "1776").passed)
		self.assertTrue(result.ready)

	def test_also_kennzahl_never_changes_the_amount_owed(self):
		without = Mapping(
			"own",
			(AccountRule("8400", "81", Side.CREDIT), AccountRule("2406", "81", Side.CREDIT)),
			BAD_DEBT_MAPPING.checks,
		)
		with_also, plain = calculate(self.lines, BAD_DEBT_MAPPING), calculate(self.lines, without)
		self.assertNotIn("50", plain.values)
		for total in ("output_tax", "input_tax", "other_tax", "sondervorauszahlung", "kz83"):
			self.assertEqual(getattr(with_also, total), getattr(plain, total), total)

	def test_informational_tax_kennzahl_is_reported_in_cents_and_does_not_count(self):
		minderung = Mapping(
			"own", (AccountRule("1579", "66", Side.DEBIT, also_kennzahl="37", also_side=Side.CREDIT),)
		)
		result = calculate([line("1579", credit="19.99")], minderung)
		self.assertEqual(result.reported("66"), d("-19.99"))
		self.assertEqual(result.reported("37"), d("19.99"))
		self.assertEqual(result.input_tax, d("-19.99"))
		self.assertEqual(result.kz83, d("19.99"))


class DeviationTest(TestCase):
	def test_only_the_voucher_with_the_wrong_tax_deviates(self):
		lines = [
			line("8400", credit="100", voucher="ACC-SINV-2026-00001"),
			line("1776", credit="19.00", voucher="ACC-SINV-2026-00001"),
			line("8400", credit="200", voucher="ACC-SINV-2026-00002"),
			line("1776", credit="38.50", voucher="ACC-SINV-2026-00002"),
		]
		result = calculate(lines, SKR03)
		check = check_of(result, "1776")
		self.assertEqual(check.deviations, (Deviation("ACC-SINV-2026-00002", d("38.00"), d("38.50")),))
		self.assertEqual(check.deviations[0].difference, d("0.50"))
		self.assertEqual(check.computed_tax, d("57.00"))
		self.assertEqual(check.booked_tax, d("57.50"))
		self.assertEqual(check.difference, d("0.50"))
		self.assertFalse(check.passed)
		self.assertFalse(result.ready)

	def test_errors_that_cancel_out_in_the_total_still_fail_in_ledger_order(self):
		lines = [
			line("8400", credit="200", voucher="ACC-SINV-2026-00002"),
			line("1776", credit="37.50", voucher="ACC-SINV-2026-00002"),
			line("8400", credit="100", voucher="ACC-SINV-2026-00001"),
			line("1776", credit="19.50", voucher="ACC-SINV-2026-00001"),
		]
		check = check_of(calculate(lines, SKR03), "1776")
		self.assertEqual(check.difference, d("0.00"))
		self.assertEqual(
			[deviation.voucher for deviation in check.deviations],
			["ACC-SINV-2026-00002", "ACC-SINV-2026-00001"],
		)
		self.assertFalse(check.passed)

	def test_base_without_booked_tax_deviates(self):
		check = check_of(calculate([line("8400", credit="100", voucher="V1")], SKR03), "1776")
		self.assertEqual(check.deviations, (Deviation("V1", d("19.00"), d("0.00")),))
		self.assertEqual(check.deviations[0].difference, d("-19.00"))

	def test_tax_on_an_unmapped_account_with_many_postings_does_not_pass(self):
		mapping = Mapping(
			"SKR03 without 8410",
			(AccountRule("8400", "81", Side.CREDIT),),
			(TaxCheck("Umsatzsteuer 19 %", ("8400",), ("1776",)),),
		)
		lines = []
		for number in range(1, 5001):
			voucher = f"ACC-SINV-2026-{number:05d}"
			lines += [
				line("8400", credit="100.00", voucher=voucher),
				line("1776", credit="19.00", voucher=voucher),
			]
		lines += [
			line("8410", credit="130.00", voucher="ACC-SINV-2026-05001"),
			line("1776", credit="24.70", voucher="ACC-SINV-2026-05001"),
		]
		result = calculate(lines, mapping)
		check = check_of(result, "1776")
		self.assertEqual(check.postings, 5000)
		self.assertEqual(check.deviations, (Deviation("ACC-SINV-2026-05001", d("0.00"), d("24.70")),))
		self.assertFalse(check.passed)
		self.assertFalse(result.ready)

	def test_lines_with_and_without_voucher_are_checked_as_separate_groups(self):
		lines = [
			line("8400", credit="100", voucher="V1"),
			line("1776", credit="19.02", voucher="V1"),
			*[line("8400", credit="100")] * 3,
			line("1776", credit="57.03"),
		]
		check = check_of(calculate(lines, SKR03), "1776")
		self.assertEqual(check.deviations, (Deviation("V1", d("19.00"), d("19.02")),))
		self.assertEqual(check.postings, 4)
		lines[-1] = line("1776", credit="57.04")
		check = check_of(calculate(lines, SKR03), "1776")
		self.assertEqual(
			check.deviations,
			(Deviation("V1", d("19.00"), d("19.02")), Deviation(None, d("57.00"), d("57.04"))),
		)

	def test_deviation_is_immutable(self):
		deviation = Deviation("V1", d("19.00"), d("19.50"))
		with self.assertRaises(AttributeError):
			deviation.booked_tax = d("19.00")  # type: ignore[misc]


class RoundingTest(TestCase):
	def test_base_is_reported_in_full_euros_and_the_tax_derives_from_the_reported_base(self):
		result = calculate([line("8400", credit="1000.99"), line("1776", credit="190.19")], SKR03)
		self.assertEqual(result.values["81"].amount, d("1000.99"))
		self.assertEqual(result.reported("81"), d("1000"))
		self.assertEqual(result.kz83, d("190.00"))

	def test_check_compares_the_booked_tax_with_the_tax_on_the_exact_base(self):
		result = calculate([line("8400", credit="1000.99"), line("1776", credit="190.19")], SKR03)
		check = check_of(result, "1776")
		self.assertEqual(check.computed_tax, d("190.19"))
		self.assertEqual(check.difference, d("0.00"))
		self.assertTrue(check.passed)

	def test_derived_13b_tax_is_rounded_to_cents(self):
		result = calculate([line("3123", debit="33.33")], SKR03)
		self.assertEqual(result.values["47"].amount, d("6.33"))
		self.assertEqual(result.reported("47"), d("6.33"))

	def test_tax_amounts_are_reported_with_cents(self):
		result = calculate([line("1576", debit="95.55"), line("1571", debit="0.01")], SKR03)
		self.assertEqual(result.reported("66"), d("95.56"))


class ToleranceTest(TestCase):
	def test_check_fails_when_the_booked_tax_deviates(self):
		result = calculate([line("8400", credit="1000"), line("1776", credit="180")], SKR03)
		check = check_of(result, "1776")
		self.assertEqual(check.difference, d("-10.00"))
		self.assertFalse(check.passed)

	def test_one_cent_per_voucher_by_default(self):
		self.assertEqual(TOLERANCE_PER_VOUCHER, d("0.01"))
		lines = [line("8400", credit="1000", voucher="V1"), line("1776", credit="190.01", voucher="V1")]
		check = check_of(calculate(lines, SKR03), "1776")
		self.assertEqual(check.tolerance, d("0.01"))
		self.assertTrue(check.passed)
		lines[1] = line("1776", credit="190.02", voucher="V1")
		self.assertFalse(check_of(calculate(lines, SKR03), "1776").passed)

	def test_tolerance_of_lines_without_voucher_grows_with_their_postings(self):
		lines = [line("8400", credit="100")] * 10 + [line("1776", credit="190.10")]
		check = check_of(calculate(lines, SKR03), "1776")
		self.assertEqual(check.postings, 10)
		self.assertEqual(check.tolerance, d("0.01"))
		self.assertTrue(check.passed)
		lines[-1] = line("1776", credit="190.11")
		self.assertFalse(check_of(calculate(lines, SKR03), "1776").passed)

	def test_tax_without_voucher_and_without_base_is_allowed_one_tolerance(self):
		self.assertTrue(check_of(calculate([line("1776", credit="0.01")], SKR03), "1776").passed)
		self.assertFalse(check_of(calculate([line("1776", credit="0.02")], SKR03), "1776").passed)

	def test_tolerance_boundary_of_one_posting_without_voucher(self):
		lines = [line("8400", credit="1000"), line("1776", credit="190.02")]
		self.assertFalse(check_of(calculate(lines, SKR03), "1776").passed)
		lines = [line("8400", credit="1000"), line("1776", credit="190.01")]
		self.assertTrue(check_of(calculate(lines, SKR03), "1776").passed)

	def test_explicit_tolerance_applies_to_each_voucher(self):
		lines = [line("8400", credit="1000", voucher="V1"), line("1776", credit="190.04", voucher="V1")]
		self.assertTrue(check_of(calculate(lines, SKR03, tolerance=d("0.05")), "1776").passed)
		self.assertFalse(check_of(calculate(lines, SKR03, tolerance=d("0.01")), "1776").passed)
		self.assertEqual(check_of(calculate(lines, SKR03, tolerance=d("0.05")), "1776").tolerance, d("0.05"))

	def test_explicit_tolerance_must_be_decimal(self):
		with self.assertRaises(TypeError):
			calculate([line("8400", credit="1000")], SKR03, tolerance=0.05)  # type: ignore[arg-type]

	def test_tolerance_must_be_finite_and_not_negative(self):
		for tolerance in ("-0.01", "NaN", "Infinity"):
			with self.subTest(tolerance=tolerance), self.assertRaisesRegex(ValueError, "tolerance"):
				calculate([line("8400", credit="1000")], SKR03, tolerance=d(tolerance))

	def test_tolerance_is_checked_even_without_checks(self):
		with self.assertRaises(TypeError):
			calculate([], Mapping("own", ()), tolerance=0.05)  # type: ignore[arg-type]


class SignTest(TestCase):
	def test_credit_note_month_gives_a_negative_base_and_a_surplus(self):
		result = calculate([line("8400", debit="500"), line("1776", debit="95")], SKR03)
		self.assertEqual(result.reported("81"), d("-500"))
		self.assertEqual(result.kz83, d("-95.00"))

	def test_input_tax_only_gives_a_surplus(self):
		result = calculate([line("1576", debit="95")], SKR03)
		self.assertEqual(result.output_tax, d("0.00"))
		self.assertEqual(result.input_tax, d("95.00"))
		self.assertEqual(result.kz83, d("-95.00"))

	def test_negative_cents_are_dropped_towards_zero(self):
		result = calculate([line("8400", debit="0.99")], SKR03)
		self.assertEqual(result.reported("81"), d("0"))

	def test_negative_correction_of_input_tax_increases_the_amount_owed(self):
		result = calculate([line("8400", credit="1000")], SKR03, extra_values={"64": d("-100")})
		self.assertEqual(result.reported("64"), d("-100.00"))
		self.assertEqual(result.input_tax, d("-100.00"))
		self.assertEqual(result.kz83, d("290.00"))

	def test_negative_sondervorauszahlung_is_accepted_and_increases_the_amount_owed(self):
		result = calculate([line("8400", credit="1000")], SKR03, extra_values={"39": d("-100")})
		self.assertEqual(result.reported("39"), d("-100.00"))
		self.assertEqual(result.sondervorauszahlung, d("-100.00"))
		self.assertEqual(result.kz83, d("290.00"))


class FormSumsTest(TestCase):
	def test_other_tax_and_sondervorauszahlung_are_outside_lines_37_to_45(self):
		result = calculate(
			[
				line("8400", credit="1000"),
				line("1576", debit="50"),
				line("1782", credit="10"),
				line("1783", credit="5"),
			],
			SKR03,
			extra_values={"39": d("100")},
		)
		self.assertEqual(result.output_tax, d("190.00"))
		self.assertEqual(result.input_tax, d("50.00"))
		self.assertEqual(result.remaining_tax, d("140.00"))
		self.assertEqual(result.other_tax, d("15.00"))
		self.assertEqual(result.prepayment, d("155.00"))
		self.assertEqual(result.sondervorauszahlung, d("100.00"))
		self.assertEqual(result.kz83, d("55.00"))
		self.assertEqual(result.reported("65"), d("10.00"))
		self.assertEqual(result.reported("69"), d("5.00"))
		self.assertEqual(result.reported("39"), d("100.00"))


class ExtraValuesTest(TestCase):
	def test_extra_values_add_to_booked_amounts(self):
		result = calculate([line("1576", debit="10")], SKR03, extra_values={"66": d("5")})
		self.assertEqual(result.reported("66"), d("15.00"))

	def test_unknown_kennzahl_is_rejected(self):
		with self.assertRaisesRegex(ValueError, "unknown Kennzahl 99"):
			calculate([], SKR03, extra_values={"99": d("1")})

	def test_balance_and_flags_take_no_amount(self):
		for number in ("83", "10", "70", "500"):
			with self.assertRaisesRegex(ValueError, f"Kennzahl {number} takes no amount"):
				calculate([], SKR03, extra_values={number: d("1")})

	def test_floats_and_non_cent_amounts_are_rejected(self):
		with self.assertRaises(TypeError):
			calculate([], SKR03, extra_values={"39": 50.0})  # type: ignore[dict-item]
		with self.assertRaisesRegex(ValueError, "finite cents"):
			calculate([], SKR03, extra_values={"39": d("0.001")})


class ScopeTest(TestCase):
	def test_unmapped_accounts_are_ignored(self):
		result = calculate([line("1200", debit="1190"), line("1400", credit="1190")], SKR03)
		self.assertEqual(set(result.values), {"83"})
		self.assertEqual(result.kz83, d("0.00"))
		self.assertTrue(result.ready)

	def test_watched_accounts_with_a_balance_block_the_filing(self):
		result = calculate([line("8340", credit="100"), line("8190", credit="50")], SKR03)
		self.assertEqual(result.unmapped, ("8190", "8340"))
		self.assertFalse(result.ready)

	def test_watched_accounts_without_balance_do_not_block(self):
		result = calculate([line("8340", credit="100"), line("8340", debit="100")], SKR03)
		self.assertEqual(result.unmapped, ())

	def test_watched_accounts_balance_over_all_vouchers(self):
		lines = [line("8340", credit="100", voucher="V1"), line("8340", debit="100", voucher="V2")]
		self.assertEqual(calculate(lines, SKR03).unmapped, ())

	def test_zero_balances_are_not_reported(self):
		result = calculate([line("8400", credit="100"), line("8400", debit="100")], SKR03)
		self.assertNotIn("81", result.values)

	def test_kz83_is_always_present(self):
		result = calculate([], SKR03)
		self.assertEqual(set(result.values), {"83"})
		self.assertEqual(result.reported("83"), d("0.00"))

	def test_lines_of_the_same_account_are_summed(self):
		result = calculate([line("8400", credit="100"), line("8400", credit="200.50")], SKR03)
		self.assertEqual(result.values["81"].amount, d("300.50"))
		self.assertEqual(result.reported("81"), d("300"))

	def test_accounts_of_one_kennzahl_are_summed(self):
		result = calculate(
			[line("1576", debit="19"), line("1571", debit="7"), line("1570", debit="1")], SKR03
		)
		self.assertEqual(result.reported("66"), d("27.00"))

	def test_unreported_kennzahl_reads_as_zero(self):
		self.assertEqual(calculate([], SKR03).reported("81"), d("0"))

	def test_checks_without_postings_pass_with_zero(self):
		result = calculate([], SKR03)
		self.assertEqual(len(result.checks), len(SKR03.checks))
		for check in result.checks:
			self.assertEqual(check.computed_tax, d("0.00"))
			self.assertEqual(check.booked_tax, d("0.00"))
			self.assertEqual(check.postings, 0)
			self.assertEqual(check.deviations, ())
			self.assertTrue(check.passed)


class WatchLevelTest(TestCase):
	"""A balance on an account watched at the blocking level holds the return; one watched for a hint does not."""

	mapping = Mapping(
		"own",
		(AccountRule("8400", "81", Side.CREDIT),),
		watched=("1548", WatchedAccount("8603", WatchLevel.HINT), WatchedAccount("2654", WatchLevel.HINT)),
	)

	def test_a_balance_watched_for_a_hint_leaves_the_return_ready_and_changes_no_kennzahl(self):
		result = calculate([line("8603", credit="250"), line("1200", debit="250")], self.mapping)
		self.assertEqual(result.unmapped, ())
		self.assertEqual(result.hinted, (AccountBalance("8603", d("0"), d("250")),))
		self.assertEqual(set(result.values), {"83"})
		self.assertEqual(result.kz83, d("0.00"))
		self.assertTrue(result.ready)

	def test_a_balance_watched_at_the_blocking_level_holds_the_return(self):
		result = calculate([line("1548", debit="50"), line("1200", credit="50")], self.mapping)
		self.assertEqual((result.unmapped, result.hinted), (("1548",), ()))
		self.assertFalse(result.ready)

	def test_a_hint_does_not_release_a_return_that_a_blocking_balance_holds(self):
		result = calculate([line("1548", debit="50"), line("8603", credit="50")], self.mapping)
		self.assertEqual(result.unmapped, ("1548",))
		self.assertEqual(result.hinted, (AccountBalance("8603", d("0"), d("50")),))
		self.assertFalse(result.ready)

	def test_a_hinted_account_carries_its_debits_and_credits_over_all_vouchers(self):
		lines = [
			line("8603", credit="300", voucher="V1"),
			line("8603", debit="50", voucher="V2"),
			line("8603", credit="20"),
		]
		self.assertEqual(calculate(lines, self.mapping).hinted, (AccountBalance("8603", d("50"), d("320")),))

	def test_an_account_watched_for_a_hint_without_a_balance_is_left_out(self):
		lines = [line("8603", credit="100", voucher="V1"), line("8603", debit="100", voucher="V2")]
		self.assertEqual(calculate(lines, self.mapping).hinted, ())

	def test_hinted_accounts_are_sorted_by_number(self):
		lines = [line("8603", credit="1"), line("2654", credit="2")]
		self.assertEqual(
			[balance.account_number for balance in calculate(lines, self.mapping).hinted], ["2654", "8603"]
		)

	def test_the_defaults_watch_other_operating_income_for_a_hint(self):
		for mapping, account, bank in ((SKR03, "8603", "1200"), (SKR04, "4830", "1800")):
			with self.subTest(chart=mapping.chart):
				result = calculate([line(account, credit="500"), line(bank, debit="500")], mapping)
				self.assertEqual(result.hinted, (AccountBalance(account, d("0"), d("500")),))
				self.assertEqual(result.unmapped, ())
				self.assertTrue(result.ready)


class AccountBalanceTest(TestCase):
	def test_the_balance_is_debit_less_credit(self):
		self.assertEqual(AccountBalance("8603", d("50"), d("320")).balance, d("-270"))
		self.assertEqual(AccountBalance("1548", d("70"), d("5")).balance, d("65"))

	def test_an_account_balance_is_immutable(self):
		with self.assertRaises(AttributeError):
			AccountBalance("8603", d("0"), d("1")).debit = d("2")  # type: ignore[misc]


class CustomMappingTest(TestCase):
	def test_tax_of_a_reported_pair_can_come_from_a_tax_account_instead(self):
		mapping = Mapping(
			"own",
			(AccountRule("3123", "46", Side.DEBIT), AccountRule("1787", "47", Side.CREDIT)),
		)
		result = calculate([line("3123", debit="300"), line("1787", credit="60")], mapping)
		self.assertEqual(result.reported("46"), d("300"))
		self.assertEqual(result.reported("47"), d("60.00"))
		self.assertEqual(result.checks, ())

	def test_checks_use_the_side_of_the_tax_accounts(self):
		mapping = Mapping(
			"own",
			(AccountRule("1576", "66", Side.DEBIT), AccountRule("3425", "89", Side.DEBIT)),
			(TaxCheck("Vorsteuer aus Erwerb", ("3425",), ("1574",), Side.DEBIT),),
		)
		result = calculate([line("3425", debit="100"), line("1574", debit="19")], mapping)
		self.assertEqual(result.checks[0].booked_tax, d("19.00"))
		self.assertTrue(result.checks[0].passed)


class ResultTest(TestCase):
	def test_result_is_immutable(self):
		result = calculate([], SKR03)
		self.assertIsInstance(result, UstvaResult)
		with self.assertRaises(AttributeError):
			result.output_tax = d("1")  # type: ignore[misc]
