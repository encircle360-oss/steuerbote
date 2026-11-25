from datetime import date
from decimal import Decimal
from typing import ClassVar
from unittest import TestCase

from steuerbote.ustva.calculation import (
	TOLERANCE_PER_VOUCHER,
	AccountBalance,
	CheckResult,
	DerivedBase,
	Deviation,
	LedgerLine,
	UstvaResult,
	calculate,
	derive_bases,
	purchase_vouchers,
	require_cents,
)
from steuerbote.ustva.defaults import SKR03, SKR04
from steuerbote.ustva.mapping import AccountRule, Mapping, Side, TaxCheck, WatchedAccount, WatchLevel
from steuerbote.ustva.residence import (
	Classification,
	Finding,
	Placement,
	Problem,
	Residence,
	Source,
	Supplier,
	Voucher,
)


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


REVERSE_CHARGE_19 = "Umsatzsteuer nach § 13b UStG 19 %"
ACQUISITION_19 = "Umsatzsteuer aus innergemeinschaftlichem Erwerb 19 %"


def purchase(voucher: str | None, *postings: tuple[str, str, str]) -> list[LedgerLine]:
	"""The lines of one voucher, each posting as account, debit and credit."""
	return [line(account, debit, credit, voucher) for account, debit, credit in postings]


class DerivedBaseTest(TestCase):
	"""A voucher that books the tax of a Verprobung but nothing on its base accounts, as a purchase on an ordinary
	expense account with a reverse-charge or acquisition tax template does: the base is read from the voucher."""

	def test_reverse_charge_on_an_expense_account_goes_to_84_and_85(self):
		lines = purchase(
			"V1",
			("4980", "1000.00", "0"),
			("1577", "190.00", "0"),
			("1787", "0", "190.00"),
			("1600", "0", "1000.00"),
		)
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("84"), d("1000"))
		self.assertEqual(result.reported("85"), d("190.00"))
		self.assertEqual(result.reported("67"), d("190.00"))
		self.assertEqual(result.output_tax, d("190.00"))
		self.assertEqual(result.kz83, d("0.00"))
		check = check_of(result, "1787")
		self.assertEqual(
			check.derived,
			(DerivedBase(REVERSE_CHARGE_19, "V1", "84", d("19"), d("190.00"), d("1000.00"), ("4980",)),),
		)
		self.assertEqual(check.derived_base, d("1000.00"))
		self.assertEqual((check.computed_tax, check.booked_tax), (d("190.00"), d("190.00")))
		self.assertTrue(check.passed)
		self.assertTrue(result.ready)

	def test_acquisition_on_an_expense_account_goes_to_89_and_its_tax_to_line_37(self):
		lines = purchase(
			"V1",
			("4930", "500.00", "0"),
			("1574", "95.00", "0"),
			("1774", "0", "95.00"),
			("1600", "0", "500.00"),
		)
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("89"), d("500"))
		self.assertEqual(result.reported("61"), d("95.00"))
		self.assertEqual(result.output_tax, d("95.00"))
		self.assertEqual(result.kz83, d("0.00"))
		self.assertEqual(check_of(result, "1774").derived[0].label, ACQUISITION_19)
		self.assertTrue(result.ready)

	def test_acquisition_at_7_percent_goes_to_93(self):
		lines = purchase("V1", ("3200", "300.00", "0"), ("1572", "21.00", "0"), ("1772", "0", "21.00"))
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("93"), d("300"))
		self.assertEqual(result.output_tax, d("21.00"))
		self.assertTrue(result.ready)

	def test_reverse_charge_at_7_percent_goes_to_84_at_7_percent(self):
		lines = purchase("V1", ("4900", "100.00", "0"), ("1578", "7.00", "0"), ("1785", "0", "7.00"))
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("84"), d("100"))
		self.assertEqual(result.reported("85"), d("7.00"))
		self.assertEqual(check_of(result, "1785").derived[0].rate, d("7"))

	def test_skr04_derives_as_skr03(self):
		lines = purchase("V1", ("6300", "1000.00", "0"), ("1407", "190.00", "0"), ("3837", "0", "190.00"))
		result = calculate(lines, SKR04)
		self.assertEqual(result.reported("84"), d("1000"))
		self.assertEqual(result.reported("85"), d("190.00"))
		self.assertTrue(result.ready)

	def test_a_line_of_another_purpose_in_the_voucher_stays_out_of_the_base(self):
		lines = purchase(
			"V1",
			("4980", "250.00", "0"),
			("4970", "1.50", "0"),
			("1577", "47.50", "0"),
			("1787", "0", "47.50"),
			("1200", "0", "251.50"),
		)
		check = check_of(calculate(lines, SKR03), "1787")
		self.assertEqual(check.derived[0].base, d("250.00"))
		self.assertEqual(check.derived[0].accounts, ("4980",))

	def test_several_lines_of_one_voucher_make_its_base(self):
		lines = purchase(
			"V1",
			("4980", "100.00", "0"),
			("4930", "50.00", "0"),
			("1577", "28.50", "0"),
			("1787", "0", "28.50"),
			("1600", "0", "150.00"),
		)
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("84"), d("150"))
		self.assertEqual(check_of(result, "1787").derived[0].accounts, ("4980", "4930"))

	def test_a_tax_rounded_per_item_matches_within_a_cent(self):
		lines = purchase(
			"V1",
			("4980", "33.33", "0"),
			("4930", "33.33", "0"),
			("4900", "33.33", "0"),
			("1577", "18.99", "0"),
			("1787", "0", "18.99"),
		)
		result = calculate(lines, SKR03)
		check = check_of(result, "1787")
		self.assertEqual(check.derived[0].base, d("99.99"))
		self.assertFalse(check.derived[0].from_tax)
		self.assertEqual(result.reported("85"), d("19.00"))
		self.assertEqual(check.difference, d("-0.01"))
		self.assertTrue(check.passed)

	def test_two_readings_of_the_voucher_take_the_base_from_the_tax(self):
		lines = purchase(
			"V1",
			("4980", "100.00", "0"),
			("4970", "0.02", "0"),
			("1577", "19.00", "0"),
			("1787", "0", "19.00"),
		)
		result = calculate(lines, SKR03)
		derived = check_of(result, "1787").derived[0]
		self.assertEqual(
			derived, DerivedBase(REVERSE_CHARGE_19, "V1", "84", d("19"), d("19.00"), d("100.00"), ())
		)
		self.assertTrue(derived.from_tax)
		self.assertEqual(result.reported("84"), d("100"))
		self.assertTrue(result.ready)

	def test_no_reading_of_the_voucher_takes_the_base_from_the_tax(self):
		lines = purchase(
			"V1",
			("4980", "150.00", "0"),
			("1576", "9.50", "0"),
			("1577", "19.00", "0"),
			("1787", "0", "19.00"),
			("1600", "0", "178.50"),
		)
		derived = check_of(calculate(lines, SKR03), "1787").derived[0]
		self.assertEqual((derived.base, derived.accounts), (d("100.00"), ()))

	def test_a_voucher_with_too_many_lines_takes_the_base_from_the_tax(self):
		accounts = [f"49{number:02d}" for number in range(13)]
		lines = [
			*purchase("V1", *((account, "10.00", "0") for account in accounts)),
			line("1787", "0", "1.90", "V1"),
		]
		derived = check_of(calculate(lines, SKR03), "1787").derived[0]
		self.assertEqual((derived.base, derived.accounts), (d("10.00"), ()))

	def test_lines_without_voucher_take_the_base_from_the_tax(self):
		lines = purchase(None, ("4980", "1000.00", "0"), ("1577", "190.00", "0"), ("1787", "0", "190.00"))
		result = calculate(lines, SKR03)
		self.assertEqual(
			check_of(result, "1787").derived,
			(DerivedBase(REVERSE_CHARGE_19, None, "84", d("19"), d("190.00"), d("1000.00"), ()),),
		)
		self.assertEqual(result.reported("84"), d("1000"))

	def test_credit_note_reduces_the_base_and_its_tax(self):
		lines = purchase(
			"V1",
			("4980", "0", "200.00"),
			("1577", "0", "38.00"),
			("1787", "38.00", "0"),
			("1600", "200.00", "0"),
		)
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("84"), d("-200"))
		self.assertEqual(result.reported("85"), d("-38.00"))
		self.assertEqual(result.kz83, d("0.00"))
		self.assertTrue(result.ready)

	def test_negative_acquisition_drops_its_cents_towards_zero(self):
		lines = purchase("V1", ("4930", "0", "164.79"), ("1574", "0", "31.31"), ("1774", "31.31", "0"))
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("89"), d("-164"))
		self.assertEqual(result.output_tax, d("-31.16"))

	def test_a_reversal_and_its_rebooking_in_one_voucher_derive_nothing(self):
		lines = purchase(
			"V1",
			("4260", "0", "72.40"),
			("4980", "72.40", "0"),
			("1577", "13.76", "13.76"),
			("1787", "13.76", "13.76"),
		)
		result = calculate(lines, SKR03)
		self.assertEqual(check_of(result, "1787").derived, ())
		self.assertNotIn("84", result.values)

	def test_a_voucher_with_a_base_account_of_the_check_keeps_its_verprobung(self):
		lines = purchase(
			"V1",
			("3125", "1000.00", "0"),
			("4980", "500.00", "0"),
			("1577", "285.00", "0"),
			("1787", "0", "285.00"),
		)
		result = calculate(lines, SKR03)
		check = check_of(result, "1787")
		self.assertEqual(check.derived, ())
		self.assertEqual(result.reported("84"), d("1000"))
		self.assertEqual(check.deviations, (Deviation("V1", d("190.00"), d("285.00")),))
		self.assertFalse(result.ready)

	def test_a_base_account_and_its_tax_are_never_counted_twice(self):
		lines = [
			*purchase("V1", ("3425", "1000.00", "0"), ("1574", "190.00", "0"), ("1774", "0", "190.00")),
			*purchase("V2", ("4930", "200.00", "0"), ("1574", "38.00", "0"), ("1774", "0", "38.00")),
		]
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("89"), d("1200"))
		self.assertEqual(result.output_tax, d("228.00"))
		check = check_of(result, "1774")
		self.assertEqual([derived.voucher for derived in check.derived], ["V2"])
		self.assertEqual((check.computed_tax, check.booked_tax), (d("228.00"), d("228.00")))

	def test_taxes_of_two_checks_in_one_voucher_find_their_own_lines(self):
		lines = purchase(
			"V1",
			("4930", "100.00", "0"),
			("4980", "50.00", "0"),
			("1574", "19.00", "0"),
			("1774", "0", "19.00"),
			("1577", "9.50", "0"),
			("1787", "0", "9.50"),
		)
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("89"), d("100"))
		self.assertEqual(result.reported("84"), d("50"))
		self.assertEqual(result.reported("85"), d("9.50"))
		self.assertTrue(result.ready)

	def test_the_tax_of_derived_bases_is_rounded_per_voucher(self):
		lines = [
			posting
			for number in range(3)
			for posting in purchase(
				f"V{number}", ("4980", "33.33", "0"), ("1787", "0", "6.33"), ("1577", "6.33", "0")
			)
		]
		result = calculate(lines, SKR03)
		self.assertEqual(result.reported("84"), d("99"))
		self.assertEqual(result.reported("85"), d("18.99"))
		self.assertEqual(result.kz83, d("0.00"))

	def test_a_check_without_derived_base_keeps_failing(self):
		mapping = Mapping(
			"SKR03 without derived bases",
			(AccountRule("3125", "84", Side.DEBIT, d("19")), AccountRule("1577", "67", Side.DEBIT)),
			(TaxCheck(REVERSE_CHARGE_19, ("3125",), ("1787",)),),
		)
		lines = purchase("V1", ("4980", "1000.00", "0"), ("1577", "190.00", "0"), ("1787", "0", "190.00"))
		result = calculate(lines, mapping)
		check = check_of(result, "1787")
		self.assertEqual(check.derived, ())
		self.assertEqual(check.deviations, (Deviation("V1", d("0.00"), d("190.00")),))
		self.assertNotIn("84", result.values)
		self.assertFalse(result.ready)

	def test_an_own_mapping_may_report_the_derived_base_in_46(self):
		mapping = Mapping(
			"own",
			(
				AccountRule("3123", "46", Side.DEBIT, d("19")),
				AccountRule("3125", "84", Side.DEBIT, d("19")),
				AccountRule("1577", "67", Side.DEBIT),
			),
			(TaxCheck(REVERSE_CHARGE_19, ("3123", "3125"), ("1787",), derived_base="46"),),
		)
		lines = purchase("V1", ("4980", "1000.00", "0"), ("1577", "190.00", "0"), ("1787", "0", "190.00"))
		result = calculate(lines, mapping)
		self.assertEqual(result.reported("46"), d("1000"))
		self.assertEqual(result.reported("47"), d("190.00"))
		self.assertNotIn("84", result.values)

	def test_watched_and_mapped_accounts_are_no_part_of_a_base(self):
		lines = purchase(
			"V1",
			("1548", "1000.00", "0"),
			("8400", "0", "1000.00"),
			("4980", "1000.00", "0"),
			("1787", "0", "190.00"),
			("1577", "190.00", "0"),
			("1776", "0", "190.00"),
			("1576", "0", "0"),
		)
		derived = check_of(calculate(lines, SKR03), "1787").derived[0]
		self.assertEqual(derived.accounts, ("4980",))

	def test_the_result_sums_the_derived_bases_by_kennzahl(self):
		lines = [
			*purchase("V1", ("4980", "100.00", "0"), ("1787", "0", "19.00"), ("1577", "19.00", "0")),
			*purchase("V2", ("4930", "40.00", "0"), ("1774", "0", "7.60"), ("1574", "7.60", "0")),
			*purchase("V3", ("4900", "10.00", "0"), ("1787", "0", "1.90"), ("1577", "1.90", "0")),
		]
		result = calculate(lines, SKR03)
		self.assertEqual(dict(result.derived_bases), {"84": d("110.00"), "89": d("40.00")})
		self.assertEqual([derived.voucher for derived in result.derived], ["V2", "V1", "V3"])

	def test_derive_bases_gives_what_calculate_derives(self):
		lines = [
			*purchase("V1", ("4980", "100.00", "0"), ("1787", "0", "19.00"), ("1577", "19.00", "0")),
			*purchase("V2", ("4930", "40.00", "0"), ("1774", "0", "7.60"), ("1574", "7.60", "0")),
		]
		self.assertEqual(derive_bases(lines, SKR03), calculate(lines, SKR03).derived)

	def test_derived_base_is_immutable(self):
		derived = DerivedBase(REVERSE_CHARGE_19, "V1", "84", d("19"), d("19.00"), d("100.00"), ("4980",))
		with self.assertRaises(AttributeError):
			derived.base = d("0")  # type: ignore[misc]


DAY = date(2027, 3, 10)
PRAGUE = Supplier("Vltava Software s.r.o.", "Czech Republic", vat_id="CZ12345678")
BOSTON = Supplier("Harbor Analytics Inc.", "United States")
REVERSE_CHARGE_7 = "Umsatzsteuer nach § 13b UStG 7 %"


def known(*suppliers: Supplier, **fields) -> Voucher:
	return Voucher(DAY, suppliers, **fields)


def service(voucher: str, net: str = "1000.00", tax: str = "190.00") -> list[LedgerLine]:
	"""A service of § 13b UStG on an expense account, its tax booked by a tax key or template on 1577 and 1787."""
	return purchase(voucher, ("4980", net, "0"), ("1577", tax, "0"), ("1787", "0", tax), ("1600", "0", net))


class SupplierResidenceTest(TestCase):
	"""The derived base of § 13b UStG goes to Kz 46 when its supplier is established in another member state and the
	service is one of § 3a Absatz 2 UStG, to Kz 84 otherwise; residence.py decides from what the caller knows."""

	def test_a_supplier_of_another_member_state_sends_the_base_to_46_and_47(self):
		result = calculate(service("PI-1"), SKR03, vouchers={"PI-1": known(PRAGUE)})
		self.assertEqual((result.reported("46"), result.reported("47")), (d("1000"), d("190.00")))
		self.assertNotIn("84", result.values)
		self.assertEqual(result.kz83, d("0.00"))
		(derived,) = check_of(result, "1787").derived
		self.assertEqual(
			derived,
			DerivedBase(
				REVERSE_CHARGE_19,
				"PI-1",
				"46",
				d("19"),
				d("190.00"),
				d("1000.00"),
				("4980",),
				Placement(Classification.EU_SERVICE, Residence.OTHER_MEMBER_STATE, Source.COUNTRY),
			),
		)
		self.assertTrue(result.ready)
		self.assertEqual(result.findings, ())

	def test_a_supplier_of_the_drittlandsgebiet_keeps_the_base_in_84(self):
		result = calculate(service("PI-1"), SKR03, vouchers={"PI-1": known(BOSTON)})
		self.assertEqual((result.reported("84"), result.reported("85")), (d("1000"), d("190.00")))
		self.assertNotIn("46", result.values)
		self.assertEqual(result.findings, ())

	def test_the_7_percent_check_sends_it_to_46_at_7_percent(self):
		lines = purchase("PI-1", ("4900", "100.00", "0"), ("1578", "7.00", "0"), ("1785", "0", "7.00"))
		result = calculate(lines, SKR03, vouchers={"PI-1": known(PRAGUE)})
		self.assertEqual((result.reported("46"), result.reported("47")), (d("100"), d("7.00")))
		self.assertEqual(check_of(result, "1785").derived[0].label, REVERSE_CHARGE_7)

	def test_one_month_splits_by_supplier_and_the_bases_and_taxes_add_up(self):
		lines = [*service("PI-1"), *service("PI-2", "500.00", "95.00"), *service("PI-3", "33.33", "6.33")]
		vouchers = {"PI-1": known(PRAGUE), "PI-2": known(BOSTON), "PI-3": known(PRAGUE)}
		split = calculate(lines, SKR03, vouchers=vouchers)
		together = calculate(lines, SKR03)
		self.assertEqual((split.reported("46"), split.reported("47")), (d("1033"), d("196.33")))
		self.assertEqual((split.reported("84"), split.reported("85")), (d("500"), d("95.00")))
		self.assertEqual(split.reported("46") + split.reported("84"), together.reported("84"))
		self.assertEqual(split.reported("47") + split.reported("85"), together.reported("85"))
		self.assertEqual(split.kz83, together.kz83)

	def test_without_what_the_caller_knows_every_base_stays_in_84(self):
		result = calculate(service("PI-1"), SKR03)
		self.assertEqual(result.reported("84"), d("1000"))
		self.assertIsNone(check_of(result, "1787").derived[0].placement)
		self.assertEqual(result.findings, ())

	def test_a_voucher_the_caller_does_not_know_stays_in_84_without_a_finding(self):
		result = calculate([*service("PI-1"), *service("PI-2")], SKR03, vouchers={"PI-1": known(PRAGUE)})
		self.assertEqual((result.reported("46"), result.reported("84")), (d("1000"), d("1000")))
		self.assertEqual(result.findings, ())

	def test_lines_without_voucher_stay_in_84(self):
		lines = purchase(None, ("4980", "100.00", "0"), ("1577", "19.00", "0"), ("1787", "0", "19.00"))
		result = calculate(lines, SKR03, vouchers={"PI-1": known(PRAGUE)})
		self.assertEqual(result.reported("84"), d("100"))
		self.assertEqual(result.findings, ())

	def test_a_journal_entry_without_supplier_stays_in_84_with_a_finding(self):
		result = calculate(service("Journal Entry:J1"), SKR03, vouchers={"Journal Entry:J1": known()})
		self.assertEqual(result.reported("84"), d("1000"))
		self.assertEqual(
			result.findings,
			(Finding(Problem.NO_SUPPLIER, "Journal Entry:J1", kennzahl="84", alternative="46"),),
		)

	def test_a_voucher_classified_by_a_person_goes_where_it_says(self):
		other = calculate(
			service("PI-1"), SKR03, vouchers={"PI-1": known(PRAGUE, classification="Other Reverse Charge")}
		)
		self.assertEqual(other.reported("84"), d("1000"))
		eu = calculate(service("J1"), SKR03, vouchers={"J1": known(classification=Classification.EU_SERVICE)})
		self.assertEqual(eu.reported("46"), d("1000"))
		self.assertEqual((other.findings, eu.findings), ((), ()))

	def test_a_finding_names_the_kennzahl_the_base_went_to_and_the_other_one(self):
		supplier = Supplier("Harbor Analytics Inc.", "United States", vat_id="IE9999999W")
		result = calculate(service("PI-1"), SKR03, vouchers={"PI-1": known(supplier)})
		self.assertEqual(
			result.findings,
			(Finding(Problem.VAT_ID_PREFIX, "PI-1", supplier.name, ("United States", "IE"), "84", "46"),),
		)
		addressed = Supplier("Vltava Software s.r.o.", "Czech Republic", "United States")
		result = calculate(service("PI-2"), SKR03, vouchers={"PI-2": known(addressed)})
		self.assertEqual(
			result.findings,
			(
				Finding(
					Problem.ADDRESS_ELSEWHERE,
					"PI-2",
					addressed.name,
					("Czech Republic", "United States"),
					"46",
					"84",
				),
			),
		)

	def test_a_voucher_in_both_checks_is_found_once(self):
		lines = [
			*service("Journal Entry:J1", "100.00", "19.00"),
			*purchase(
				"Journal Entry:J1", ("4900", "100.00", "0"), ("1578", "7.00", "0"), ("1785", "0", "7.00")
			),
		]
		result = calculate(lines, SKR03, vouchers={"Journal Entry:J1": known()})
		self.assertEqual(len(result.derived), 2)
		self.assertEqual([finding.problem for finding in result.findings], [Problem.NO_SUPPLIER])

	def test_a_base_account_always_wins_over_the_supplier(self):
		lines = purchase("PI-1", ("3125", "1000.00", "0"), ("1577", "190.00", "0"), ("1787", "0", "190.00"))
		result = calculate(lines, SKR03, vouchers={"PI-1": known(PRAGUE)})
		self.assertEqual(result.reported("84"), d("1000"))
		self.assertEqual(result.derived, ())
		self.assertEqual(result.findings, ())

	def test_a_base_account_of_46_with_a_supplier_outside_the_member_states_is_a_finding(self):
		lines = purchase("PI-1", ("3123", "1000.00", "0"), ("1577", "190.00", "0"), ("1787", "0", "190.00"))
		result = calculate(lines, SKR03, vouchers={"PI-1": known(BOSTON)})
		self.assertEqual(result.reported("46"), d("1000"))
		self.assertEqual(
			result.findings,
			(
				Finding(
					Problem.EU_SERVICE_ACCOUNT_OUTSIDE,
					"PI-1",
					BOSTON.name,
					("country", "third country"),
					"46",
					"84",
				),
			),
		)
		stated = calculate(
			lines, SKR03, vouchers={"PI-1": known(PRAGUE, classification=Classification.OTHER)}
		)
		self.assertEqual(stated.findings[0].facts, ("voucher", "other member state"))
		self.assertEqual(calculate(lines, SKR03, vouchers={"PI-1": known(PRAGUE)}).findings, ())
		self.assertEqual(calculate(lines, SKR03, vouchers={}).findings, ())

	def test_an_acquisition_from_a_supplier_of_the_drittlandsgebiet_is_a_finding(self):
		derived = purchase("PI-1", ("4930", "500.00", "0"), ("1574", "95.00", "0"), ("1774", "0", "95.00"))
		booked = purchase("PI-2", ("3425", "200.00", "0"), ("1574", "38.00", "0"), ("1774", "0", "38.00"))
		addressed = Supplier("Granite Supply Corp.", address_country="Canada")
		vouchers = {"PI-1": known(BOSTON, PRAGUE), "PI-2": known(addressed)}
		result = calculate([*derived, *booked], SKR03, vouchers=vouchers)
		self.assertEqual(result.reported("89"), d("700"))
		self.assertEqual(
			result.findings,
			(
				Finding(Problem.ACQUISITION_OUTSIDE_EU, "PI-1", BOSTON.name, ("United States",)),
				Finding(Problem.ACQUISITION_OUTSIDE_EU, "PI-2", addressed.name, ("Canada",)),
			),
		)
		self.assertEqual(calculate(derived, SKR03, vouchers={"PI-1": known(PRAGUE)}).findings, ())
		self.assertEqual(calculate(derived, SKR03, vouchers={}).findings, ())

	def test_derive_bases_gives_what_calculate_derives(self):
		lines = [*service("PI-1"), *service("PI-2")]
		vouchers = {"PI-1": known(PRAGUE), "PI-2": known(BOSTON)}
		self.assertEqual(
			derive_bases(lines, SKR03, vouchers), calculate(lines, SKR03, vouchers=vouchers).derived
		)
		self.assertEqual([base.kennzahl for base in derive_bases(lines, SKR03, vouchers)], ["46", "84"])

	def test_a_mapping_without_a_kennzahl_for_the_member_states_keeps_every_base_in_its_derived_base(self):
		mapping = Mapping(
			"own",
			(AccountRule("3125", "84", Side.DEBIT, d("19")),),
			(TaxCheck(REVERSE_CHARGE_19, ("3125",), ("1787",), derived_base="84"),),
		)
		result = calculate(service("PI-1"), mapping, vouchers={"PI-1": known(PRAGUE)})
		self.assertEqual(result.reported("84"), d("1000"))
		self.assertIsNone(result.derived[0].placement)

	def test_the_vouchers_to_ask_about_are_those_of_sections_c_and_d(self):
		lines = [
			*service("PI-1"),
			line("8400", credit="100", voucher="SI-1"),
			line("1776", credit="19", voucher="SI-1"),
			line("3425", debit="10", voucher="PI-2"),
			line("1774", credit="1.90", voucher="PI-3"),
			line("3123", debit="5", voucher=None),
			line("1787", credit="0.95", voucher="PI-1"),
		]
		self.assertEqual(purchase_vouchers(lines, SKR03), ("PI-1", "PI-2", "PI-3"))
		self.assertEqual(purchase_vouchers([], SKR03), ())


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
