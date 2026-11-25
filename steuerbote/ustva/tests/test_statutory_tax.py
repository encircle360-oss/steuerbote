"""The setting „Steuer zu Umsätzen mit festem Steuersatz“: the tax of Kz 81, 86, 89 and 93 from the base in full euros,
as the form computes it, or as booked on the vouchers of their Verprobung."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva.calculation import (
	DEFAULT_STATUTORY_TAX,
	BookedTax,
	LedgerLine,
	StatutoryTax,
	UstvaResult,
	booked_taxes,
	calculate,
)
from steuerbote.ustva.defaults import SKR03
from steuerbote.ustva.mapping import AccountRule, Mapping, Side, TaxCheck

BOOKED = StatutoryTax.AS_BOOKED
FROM_BASE = StatutoryTax.FROM_BASE


def d(value: str) -> Decimal:
	return Decimal(value)


def line(account: str, debit: str = "0", credit: str = "0", voucher: str | None = None) -> LedgerLine:
	return LedgerLine(account, d(debit), d(credit), voucher)


def sale(
	voucher: str | None, net: str, tax: str, revenue: str = "8400", tax_account: str = "1776"
) -> list[LedgerLine]:
	"""A Sales Invoice on the revenue and tax account; a negative net and tax make a credit note."""
	if net.startswith("-"):
		return [
			line(revenue, debit=net[1:], voucher=voucher),
			line(tax_account, debit=tax[1:], voucher=voucher),
		]
	return [line(revenue, credit=net, voucher=voucher), line(tax_account, credit=tax, voucher=voucher)]


def both(lines: list[LedgerLine], mapping: Mapping = SKR03) -> tuple[UstvaResult, UstvaResult]:
	return calculate(lines, mapping), calculate(lines, mapping, statutory_tax=BOOKED)


class SettingTest(TestCase):
	def test_the_values_of_the_setting(self):
		self.assertEqual(StatutoryTax.FROM_BASE.value, "From the Base in Full Euros")
		self.assertEqual(StatutoryTax.AS_BOOKED.value, "As Booked")

	def test_the_default_is_the_tax_the_form_computes(self):
		self.assertIs(DEFAULT_STATUTORY_TAX, FROM_BASE)
		lines = [*sale("V1", "33.33", "6.33"), *sale("V2", "33.33", "6.33"), *sale("V3", "33.33", "6.33")]
		self.assertEqual(calculate(lines, SKR03), calculate(lines, SKR03, statutory_tax=FROM_BASE))


class AsBookedTest(TestCase):
	def test_three_documents_rounded_each_give_kz83_as_on_the_tax_account(self):
		lines = [*sale("V1", "33.33", "6.33"), *sale("V2", "33.33", "6.33"), *sale("V3", "33.33", "6.33")]
		from_base, booked = both(lines)
		self.assertEqual((from_base.reported("81"), booked.reported("81")), (d("99"), d("99")))
		self.assertEqual(from_base.values["81"].tax, d("18.81"))
		self.assertEqual(booked.values["81"].tax, d("18.99"))
		self.assertEqual((from_base.output_tax, booked.output_tax), (d("18.81"), d("18.99")))
		self.assertEqual((from_base.kz83, booked.kz83), (d("18.81"), d("18.99")))

	def test_the_verprobung_is_the_same_either_way(self):
		lines = [*sale("V1", "33.33", "6.33"), *sale("V2", "100.00", "19.50"), line("1776", credit="1.00")]
		from_base, booked = both(lines)
		self.assertEqual(from_base.checks, booked.checks)
		self.assertEqual(len(booked.checks[0].deviations), 2)
		self.assertFalse(booked.ready)

	def test_a_base_below_one_euro_reports_zero_and_keeps_its_tax(self):
		from_base, booked = both(sale("V1", "0.80", "0.15"))
		self.assertEqual((from_base.reported("81"), from_base.values["81"].tax), (d("0"), d("0.00")))
		self.assertEqual((booked.reported("81"), booked.values["81"].amount), (d("0"), d("0.80")))
		self.assertEqual(booked.values["81"].tax, d("0.15"))
		self.assertEqual((from_base.kz83, booked.kz83), (d("0.00"), d("0.15")))

	def test_lines_without_voucher_count_as_one_document(self):
		from_base, booked = both(sale(None, "50.50", "9.60"))
		self.assertEqual((from_base.kz83, booked.kz83), (d("9.50"), d("9.60")))

	def test_a_credit_note_takes_back_the_tax_it_books(self):
		lines = [
			*sale("V1", "100.50", "19.10"),
			*sale("V2", "-100.50", "-19.10"),
			*sale("V3", "10.10", "1.92"),
		]
		from_base, booked = both(lines)
		self.assertEqual(booked.reported("81"), d("10"))
		self.assertEqual((from_base.kz83, booked.kz83), (d("1.90"), d("1.92")))

	def test_a_negative_base_takes_its_booked_tax_too(self):
		lines = [*sale("V2", "-100.50", "-19.10"), *sale("V4", "-10.10", "-1.92")]
		from_base, booked = both(lines)
		self.assertEqual(booked.reported("81"), d("-110"))
		self.assertEqual((from_base.kz83, booked.kz83), (d("-20.90"), d("-21.02")))

	def test_seven_percent_goes_the_same_way(self):
		from_base, booked = both(
			[*sale("V1", "10.07", "0.70", "8300", "1771"), *sale("V2", "10.07", "0.70", "8300", "1771")]
		)
		self.assertEqual(booked.reported("86"), d("20"))
		self.assertEqual((from_base.values["86"].tax, booked.values["86"].tax), (d("1.40"), d("1.40")))
		from_base, booked = both(sale("V1", "10.93", "0.77", "8300", "1771"))
		self.assertEqual((from_base.values["86"].tax, booked.values["86"].tax), (d("0.70"), d("0.77")))

	def test_tax_booked_without_a_base_goes_to_the_kennzahl_of_its_verprobung(self):
		from_base, booked = both([line("1776", credit="1.00", voucher="V1")])
		self.assertNotIn("81", from_base.values)
		self.assertEqual(booked.values["81"].amount, d("0"))
		self.assertEqual((booked.values["81"].reported, booked.values["81"].tax), (d("0"), d("1.00")))
		self.assertEqual((from_base.kz83, booked.kz83), (d("0.00"), d("1.00")))
		self.assertFalse(booked.ready)

	def test_other_kennzahlen_have_no_tax_of_their_own(self):
		_, booked = both([*sale("V1", "100.00", "19.00"), line("8125", credit="50", voucher="V2")])
		self.assertIsNone(booked.values["41"].tax)
		self.assertIsNone(booked.values["83"].tax)


class AcquisitionTest(TestCase):
	def test_a_base_derived_from_the_tax_takes_the_tax_booked(self):
		lines = [
			line("4930", debit="500.53", voucher="V1"),
			line("1574", debit="95.10", voucher="V1"),
			line("1774", credit="95.10", voucher="V1"),
			line("1600", credit="500.53", voucher="V1"),
		]
		from_base, booked = both(lines)
		self.assertEqual(booked.derived[0].base, d("500.53"))
		self.assertEqual((booked.reported("89"), booked.values["89"].tax), (d("500"), d("95.10")))
		self.assertEqual(booked.reported("61"), d("95.10"))
		self.assertEqual((from_base.kz83, booked.kz83), (d("-0.10"), d("0.00")))

	def test_a_verprobung_of_two_rates_splits_the_tax_of_a_voucher_by_its_bases(self):
		lines = [
			line("3435", debit="100.10", voucher="V1"),
			line("3430", debit="50.10", voucher="V1"),
			line("1779", credit="22.54", voucher="V1"),
		]
		from_base, booked = both(lines)
		self.assertEqual((SKR03.rule_for("3435").kennzahl, SKR03.rule_for("3430").kennzahl), ("89", "93"))
		self.assertTrue(booked.ready)
		self.assertEqual((from_base.values["89"].tax, from_base.values["93"].tax), (d("19.00"), d("3.50")))
		self.assertEqual((booked.values["89"].tax, booked.values["93"].tax), (d("19.03"), d("3.51")))
		self.assertEqual(booked.kz83, d("22.54"))
		self.assertCountEqual(
			booked_taxes(lines, SKR03),
			(BookedTax("93", "V1", "3430", d("3.51")), BookedTax("89", "V1", "3435", d("19.03"))),
		)

	def test_the_split_of_46_and_84_keeps_its_own_tax_kennzahlen(self):
		lines = [
			line("3123", debit="300.33", voucher="V1"),
			line("1577", debit="57.06", voucher="V1"),
			line("1787", credit="57.06", voucher="V1"),
			line("4980", debit="100.00", voucher="V2"),
			line("1577", debit="19.00", voucher="V2"),
			line("1787", credit="19.00", voucher="V2"),
		]
		from_base, booked = both(lines)
		self.assertEqual(from_base.values, booked.values)
		self.assertEqual((booked.reported("47"), booked.reported("85")), (d("57.06"), d("19.00")))
		self.assertEqual(booked_taxes(lines, SKR03), ())


class CustomMappingTest(TestCase):
	def test_a_base_without_verprobung_takes_the_tax_of_each_voucher(self):
		mapping = Mapping("own", (AccountRule("8400", "81", Side.CREDIT),))
		lines = [line("8400", credit="33.33", voucher="V1"), line("8400", credit="33.33", voucher="V2")]
		from_base, booked = both(lines, mapping)
		self.assertEqual((from_base.kz83, booked.kz83), (d("12.54"), d("12.66")))
		self.assertEqual(
			booked_taxes(lines, mapping),
			(BookedTax("81", "V1", "8400", d("6.33")), BookedTax("81", "V2", "8400", d("6.33"))),
		)

	def test_a_voucher_with_another_rate_in_the_verprobung_leaves_that_tax_to_its_kennzahl(self):
		mapping = Mapping(
			"own",
			(AccountRule("8400", "81", Side.CREDIT), AccountRule("8990", "35", Side.CREDIT, d("10"))),
			(TaxCheck("Umsatzsteuer", ("8400", "8990"), ("1776",)),),
		)
		lines = [
			line("8400", credit="100.00", voucher="V1"),
			line("8990", credit="100.00", voucher="V1"),
			line("1776", credit="29.01", voucher="V1"),
			line("8990", credit="100.00", voucher="V2"),
			line("1776", credit="10.01", voucher="V2"),
		]
		from_base, booked = both(lines, mapping)
		self.assertEqual(booked.reported("36"), d("20.00"))
		self.assertEqual((from_base.values["81"].tax, booked.values["81"].tax), (d("19.00"), d("19.01")))
		self.assertEqual((from_base.kz83, booked.kz83), (d("39.00"), d("39.01")))


class GivenTaxesTest(TestCase):
	"""The amounts of a return as filed: the bases with the tax its rows keep."""

	empty = Mapping(chart="", rules=())

	def test_a_given_tax_replaces_the_tax_of_the_base(self):
		result = calculate(
			(), self.empty, extra_values={"81": d("99")}, statutory_tax=BOOKED, taxes={"81": d("18.99")}
		)
		self.assertEqual((result.values["81"].tax, result.kz83), (d("18.99"), d("18.99")))

	def test_a_kennzahl_without_a_given_tax_takes_the_tax_of_its_base(self):
		result = calculate((), self.empty, extra_values={"81": d("99")}, statutory_tax=BOOKED, taxes={})
		self.assertEqual(result.kz83, d("18.81"))

	def test_a_given_tax_without_a_base_counts(self):
		result = calculate((), self.empty, statutory_tax=BOOKED, taxes={"81": d("0.15")})
		self.assertEqual((result.values["81"].reported, result.values["81"].tax), (d("0"), d("0.15")))
		self.assertEqual(result.kz83, d("0.15"))

	def test_refuses_a_tax_the_form_does_not_derive(self):
		for number in ("36", "47", "66", "999"):
			with self.subTest(number=number), self.assertRaisesRegex(ValueError, "statutory rate"):
				calculate((), self.empty, statutory_tax=BOOKED, taxes={number: d("1.00")})

	def test_refuses_given_taxes_from_the_base(self):
		with self.assertRaisesRegex(ValueError, "as booked"):
			calculate((), self.empty, taxes={"81": d("1.00")})

	def test_refuses_a_tax_finer_than_cents(self):
		with self.assertRaisesRegex(ValueError, "finite cents"):
			calculate((), self.empty, statutory_tax=BOOKED, taxes={"81": d("0.001")})
