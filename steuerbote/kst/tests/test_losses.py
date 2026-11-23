"""§ 10d EStG, § 15 Absatz 4 EStG and § 9 Absatz 1 Nummer 2 KStG: what the Körperschaftsteuer carries over."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.kst.losses import loss_deduction, minimum_taxation
from steuerbote.kst.years import YEARS

YEAR = YEARS[2026]
ZERO = Decimal("0")
MILLION = Decimal("1000000")


class MinimumTaxationTest(TestCase):
	"""§ 10d Absatz 2 Satz 1 EStG: 1 Million Euro in full, 70 % of the rest, the 70 % rounded up (rule 8900170)."""

	def test_deducts_up_to_one_million_in_full(self):
		self.assertEqual(
			minimum_taxation(Decimal("800000"), Decimal("900000"), MILLION, Decimal("70")),
			(Decimal("800000"), ZERO),
		)

	def test_deducts_no_more_than_the_carry_forward(self):
		self.assertEqual(
			minimum_taxation(Decimal("800000"), Decimal("300000"), MILLION, Decimal("70")),
			(Decimal("300000"), ZERO),
		)

	def test_deducts_70_percent_of_the_amount_beyond_one_million_rounded_up(self):
		self.assertEqual(
			minimum_taxation(Decimal("1000001"), Decimal("5000000"), MILLION, Decimal("70")),
			(MILLION, Decimal("1")),
		)
		self.assertEqual(
			minimum_taxation(Decimal("2000000"), Decimal("5000000"), MILLION, Decimal("70")),
			(MILLION, Decimal("700000")),
		)

	def test_the_limited_part_is_no_more_than_what_the_carry_forward_has_left(self):
		self.assertEqual(
			minimum_taxation(Decimal("2000000"), Decimal("1200000"), MILLION, Decimal("70")),
			(MILLION, Decimal("200000")),
		)

	def test_a_negative_amount_or_carry_forward_deducts_nothing(self):
		self.assertEqual(
			minimum_taxation(Decimal("-5"), Decimal("100"), MILLION, Decimal("70")), (ZERO, ZERO)
		)
		self.assertEqual(minimum_taxation(Decimal("100"), ZERO, MILLION, Decimal("70")), (ZERO, ZERO))


class PositiveIncomeTest(TestCase):
	"""Anlage Verluste lines 11 and 22 to 28 with a positive Gesamtbetrag der Einkünfte."""

	def test_without_carry_forward_deducts_nothing_and_needs_no_anlage_verluste(self):
		found = loss_deduction(YEAR, Decimal("111200"), ZERO)
		self.assertEqual(found.deduction, ZERO)
		self.assertEqual(found.remaining, ZERO)
		self.assertFalse(found.required)

	def test_deducts_the_carry_forward_from_the_gesamtbetrag_der_einkuenfte(self):
		found = loss_deduction(YEAR, Decimal("111200"), Decimal("50000"))
		self.assertEqual(
			(found.total_income, found.unlimited, found.rest, found.limited, found.remaining),
			(Decimal("111200"), Decimal("50000"), ZERO, ZERO, ZERO),
		)
		self.assertEqual(found.deduction, Decimal("50000"))
		self.assertTrue(found.required)

	def test_keeps_what_the_income_does_not_absorb(self):
		found = loss_deduction(YEAR, Decimal("40000"), Decimal("50000"))
		self.assertEqual((found.deduction, found.remaining), (Decimal("40000"), Decimal("10000")))

	def test_beyond_one_million_deducts_70_percent_of_the_rest_rule_8900184_and_8900170(self):
		found = loss_deduction(YEAR, Decimal("1500001"), Decimal("3000000"))
		self.assertEqual(found.unlimited, MILLION)
		self.assertEqual(found.rest, Decimal("500001"))
		self.assertEqual(found.limited, Decimal("350001"))
		self.assertEqual(found.deduction, Decimal("1350001"))
		self.assertEqual(found.remaining, Decimal("1649999"))

	def test_an_income_of_zero_keeps_the_carry_forward(self):
		found = loss_deduction(YEAR, ZERO, Decimal("50000"))
		self.assertEqual(
			(found.total_income, found.deduction, found.remaining), (ZERO, ZERO, Decimal("50000"))
		)


class NegativeIncomeTest(TestCase):
	"""Anlage Verluste lines 19 to 21 and 28 with a negative Gesamtbetrag der Einkünfte."""

	def test_adds_the_loss_to_the_carry_forward_less_the_carry_back(self):
		found = loss_deduction(YEAR, Decimal("-30000"), Decimal("50000"), Decimal("10000"))
		self.assertEqual(
			(found.loss, found.carry_back, found.subtotal),
			(Decimal("30000"), Decimal("10000"), Decimal("70000")),
		)
		self.assertEqual((found.deduction, found.remaining), (ZERO, Decimal("70000")))
		self.assertTrue(found.required)

	def test_a_carry_back_of_zero_waives_it(self):
		found = loss_deduction(YEAR, Decimal("-30000"), ZERO, ZERO)
		self.assertEqual(found.remaining, Decimal("30000"))
		self.assertFalse(found.carry_back_missing)

	def test_a_loss_needs_the_carry_back_or_its_waiver_rule_8900343(self):
		found = loss_deduction(YEAR, Decimal("-30000"), ZERO)
		self.assertTrue(found.carry_back_missing)
		self.assertIsNone(found.carry_back)
		self.assertEqual(found.remaining, Decimal("30000"))

	def test_the_carry_back_is_no_more_than_the_loss_and_one_million_rule_8900124(self):
		self.assertTrue(loss_deduction(YEAR, Decimal("-30000"), ZERO, Decimal("30001")).carry_back_too_high)
		self.assertFalse(loss_deduction(YEAR, Decimal("-30000"), ZERO, Decimal("30000")).carry_back_too_high)
		self.assertTrue(
			loss_deduction(YEAR, Decimal("-2000000"), ZERO, Decimal("1000001")).carry_back_too_high
		)

	def test_a_carry_back_without_loss_is_refused(self):
		with self.assertRaisesRegex(ValueError, "a Verlustrücktrag needs a loss"):
			loss_deduction(YEAR, Decimal("100"), ZERO, Decimal("1"))


class InputTest(TestCase):
	def test_takes_whole_euros(self):
		with self.assertRaisesRegex(ValueError, "the Gesamtbetrag der Einkünfte must be whole euros"):
			loss_deduction(YEAR, Decimal("1.50"), ZERO)
		with self.assertRaisesRegex(ValueError, "the Verlustvortrag must be whole euros of at least 0"):
			loss_deduction(YEAR, Decimal("100"), Decimal("-1"))
		with self.assertRaisesRegex(ValueError, "the Verlustrücktrag must be whole euros of at least 0"):
			loss_deduction(YEAR, Decimal("-100"), ZERO, Decimal("0.5"))
