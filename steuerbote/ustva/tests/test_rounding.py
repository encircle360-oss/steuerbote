from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva.rounding import (
	apportion_full_euros,
	base_from_tax,
	ceil_cents,
	ceil_euro,
	floor_euro,
	floor_hundred,
	half_up_euro,
	require_decimal,
	tax_from_base,
	to_cents,
	to_full_euros,
	truncate_cents,
)


class ToFullEurosTest(TestCase):
	def test_drops_the_cents(self):
		self.assertEqual(to_full_euros(Decimal("1000.99")), Decimal("1000"))

	def test_drops_the_cents_towards_zero_for_negative_amounts(self):
		self.assertEqual(to_full_euros(Decimal("-1000.99")), Decimal("-1000"))

	def test_keeps_whole_amounts(self):
		self.assertEqual(to_full_euros(Decimal("250")), Decimal("250"))

	def test_never_returns_negative_zero(self):
		self.assertEqual(str(to_full_euros(Decimal("-0.40"))), "0")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			to_full_euros(10.5)


class ToCentsTest(TestCase):
	def test_rounds_half_up(self):
		self.assertEqual(to_cents(Decimal("0.005")), Decimal("0.01"))
		self.assertEqual(to_cents(Decimal("0.004")), Decimal("0.00"))

	def test_rounds_half_away_from_zero_for_negative_amounts(self):
		self.assertEqual(to_cents(Decimal("-0.005")), Decimal("-0.01"))

	def test_never_returns_negative_zero(self):
		self.assertEqual(str(to_cents(Decimal("-0.001"))), "0.00")

	def test_keeps_two_decimals_on_whole_amounts(self):
		self.assertEqual(str(to_cents(Decimal("190"))), "190.00")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			to_cents(0.1)


class TaxFromBaseTest(TestCase):
	def test_nineteen_percent(self):
		self.assertEqual(tax_from_base(Decimal("1000"), Decimal("19")), Decimal("190.00"))

	def test_seven_percent(self):
		self.assertEqual(tax_from_base(Decimal("999"), Decimal("7")), Decimal("69.93"))

	def test_rounds_the_tax_half_up(self):
		self.assertEqual(tax_from_base(Decimal("0.5"), Decimal("19")), Decimal("0.10"))

	def test_negative_base_gives_negative_tax(self):
		self.assertEqual(tax_from_base(Decimal("-500"), Decimal("19")), Decimal("-95.00"))

	def test_rejects_float_rate(self):
		with self.assertRaises(TypeError):
			tax_from_base(Decimal("100"), 19.0)


class BaseFromTaxTest(TestCase):
	"""The base whose tax a voucher books, where no line of the voucher shows it: tax / rate, to cents."""

	def test_nineteen_percent(self):
		self.assertEqual(base_from_tax(Decimal("190.00"), Decimal("19")), Decimal("1000.00"))

	def test_rounds_the_base_half_up_to_cents(self):
		self.assertEqual(base_from_tax(Decimal("11.98"), Decimal("19")), Decimal("63.05"))
		self.assertEqual(base_from_tax(Decimal("0.01"), Decimal("7")), Decimal("0.14"))

	def test_the_tax_of_the_base_is_the_tax_again(self):
		for cents in range(-1000, 1001, 7):
			tax = Decimal(cents) / 100
			for rate in (Decimal("19"), Decimal("7"), Decimal("10.7")):
				with self.subTest(tax=tax, rate=rate):
					self.assertEqual(tax_from_base(base_from_tax(tax, rate), rate), tax)

	def test_negative_tax_gives_a_negative_base(self):
		self.assertEqual(base_from_tax(Decimal("-31.31"), Decimal("19")), Decimal("-164.79"))

	def test_never_returns_negative_zero(self):
		self.assertEqual(str(base_from_tax(Decimal("-0.00"), Decimal("19"))), "0.00")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			base_from_tax(19.0, Decimal("19"))  # type: ignore[arg-type]
		with self.assertRaises(TypeError):
			base_from_tax(Decimal("19"), 19.0)  # type: ignore[arg-type]


class RequireDecimalTest(TestCase):
	def test_passes_decimals_through(self):
		amount = Decimal("1.23")
		self.assertIs(require_decimal(amount), amount)

	def test_names_the_offending_type(self):
		with self.assertRaisesRegex(TypeError, "not int"):
			require_decimal(1)


class FloorEuroTest(TestCase):
	"""§ 31 Abs. 1 Satz 2 KStG with rule 8900331 of Jahresdokumentation_E30_2025.ods, R 14.1 Satz 3 GewStR."""

	def test_rounds_the_koerperschaftsteuer_down_to_whole_euros(self):
		self.assertEqual(floor_euro(Decimal("111200") * Decimal("0.15")), Decimal("16680"))
		self.assertEqual(floor_euro(Decimal("16680.99")), Decimal("16680"))

	def test_rounds_the_steuermessbetrag_down_to_whole_euros(self):
		self.assertEqual(floor_euro(Decimal("107600") * Decimal("0.035")), Decimal("3766"))

	def test_keeps_whole_amounts(self):
		self.assertEqual(floor_euro(Decimal("250.00")), Decimal("250"))

	def test_goes_down_for_negative_amounts_as_well(self):
		self.assertEqual(floor_euro(Decimal("-0.40")), Decimal("-1"))

	def test_never_returns_negative_zero(self):
		self.assertEqual(str(floor_euro(Decimal("-0.00"))), "0")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			floor_euro(16680.5)


class FloorHundredTest(TestCase):
	"""§ 11 Abs. 1 Satz 3 GewStG: „Der Gewerbeertrag ist auf volle 100 Euro nach unten abzurunden“."""

	def test_rounds_the_gewerbeertrag_down_to_full_hundreds(self):
		self.assertEqual(floor_hundred(Decimal("107654.32")), Decimal("107600"))
		self.assertEqual(floor_hundred(Decimal("99.99")), Decimal("0"))

	def test_keeps_full_hundreds(self):
		self.assertEqual(floor_hundred(Decimal("107600")), Decimal("107600"))

	def test_goes_down_for_negative_amounts_as_well(self):
		self.assertEqual(floor_hundred(Decimal("-150")), Decimal("-200"))

	def test_writes_whole_euros(self):
		self.assertEqual(str(floor_hundred(Decimal("107654.32"))), "107600")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			floor_hundred(107654.32)


class TruncateCentsTest(TestCase):
	"""§ 4 Satz 3 SolZG: „Bruchteile eines Cents bleiben außer Ansatz.“"""

	def test_drops_the_fractions_of_a_cent_of_the_solidaritaetszuschlag(self):
		self.assertEqual(truncate_cents(Decimal("16680") * Decimal("0.055")), Decimal("917.40"))
		self.assertEqual(truncate_cents(Decimal("1234.5678")), Decimal("1234.56"))

	def test_drops_them_towards_zero_for_negative_amounts(self):
		self.assertEqual(truncate_cents(Decimal("-0.019")), Decimal("-0.01"))

	def test_keeps_two_decimals(self):
		self.assertEqual(str(truncate_cents(Decimal("92.4"))), "92.40")

	def test_never_returns_negative_zero(self):
		self.assertEqual(str(truncate_cents(Decimal("-0.009"))), "0.00")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			truncate_cents(917.4)


class CeilEuroTest(TestCase):
	"""„Aufrunden“ in the rules 8956040 and 8900170 of Jahresdokumentation_E30_2025.ods."""

	def test_rounds_up_to_whole_euros(self):
		self.assertEqual(ceil_euro(Decimal("1000.01")), Decimal("1001"))
		self.assertEqual(
			ceil_euro((Decimal("1500000") - Decimal("1000000")) * Decimal("0.7")), Decimal("350000")
		)
		self.assertEqual(ceil_euro(Decimal("333.33") * Decimal("0.7")), Decimal("234"))

	def test_keeps_whole_amounts(self):
		self.assertEqual(ceil_euro(Decimal("1000.00")), Decimal("1000"))

	def test_goes_up_for_negative_amounts_as_well(self):
		self.assertEqual(ceil_euro(Decimal("-1000.99")), Decimal("-1000"))

	def test_never_returns_negative_zero(self):
		self.assertEqual(str(ceil_euro(Decimal("-0.40"))), "0")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			ceil_euro(1000.01)


class HalfUpEuroTest(TestCase):
	"""Declared amounts in whole euros where no source names the direction, an unverified policy."""

	def test_rounds_half_up_to_whole_euros(self):
		self.assertEqual(half_up_euro(Decimal("1234.50")), Decimal("1235"))
		self.assertEqual(half_up_euro(Decimal("1234.49")), Decimal("1234"))

	def test_rounds_half_away_from_zero_for_negative_amounts(self):
		self.assertEqual(half_up_euro(Decimal("-1234.50")), Decimal("-1235"))

	def test_never_returns_negative_zero(self):
		self.assertEqual(str(half_up_euro(Decimal("-0.40"))), "0")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			half_up_euro(1234.5)


class CeilCentsTest(TestCase):
	def test_rounds_any_fraction_of_a_cent_up(self):
		self.assertEqual(ceil_cents(Decimal("2250.0025")), Decimal("2250.01"))
		self.assertEqual(ceil_cents(Decimal("2625.0000")), Decimal("2625.00"))

	def test_keeps_two_decimals_on_whole_amounts(self):
		self.assertEqual(str(ceil_cents(Decimal("100"))), "100.00")

	def test_rounds_towards_positive_infinity_without_negative_zero(self):
		self.assertEqual(str(ceil_cents(Decimal("-0.001"))), "0.00")
		self.assertEqual(ceil_cents(Decimal("-1.009")), Decimal("-1.00"))

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			ceil_cents(0.1)


def euros(*values: str) -> tuple[Decimal, ...]:
	return tuple(Decimal(value) for value in values)


class ApportionFullEurosTest(TestCase):
	"""Full euros for parts that keep adding up to their total, such as the positions of a balance sheet."""

	def test_rounds_each_part_half_up_where_that_meets_the_total(self):
		self.assertEqual(apportion_full_euros(euros("1.40", "2.60"), Decimal("4")), euros("1", "3"))

	def test_takes_a_euro_from_the_part_rounded_up_the_most(self):
		self.assertEqual(
			apportion_full_euros(euros("6350.50", "37929.50"), Decimal("44280")), euros("6350", "37930")
		)

	def test_adds_a_euro_to_the_part_rounded_down_the_most(self):
		self.assertEqual(
			apportion_full_euros(euros("0.40", "0.45", "0.40"), Decimal("1")), euros("0", "1", "0")
		)

	def test_takes_the_rounded_sum_of_the_parts_without_a_total(self):
		self.assertEqual(apportion_full_euros(euros("1.25", "1.25")), euros("2", "1"))

	def test_keeps_whole_parts_and_zero_as_they_are(self):
		self.assertEqual(
			apportion_full_euros(euros("25000", "0.50", "0", "0.50"), Decimal("25001")),
			euros("25000", "0", "0", "1"),
		)

	def test_counts_negative_parts_with_their_sign(self):
		self.assertEqual(apportion_full_euros(euros("-1.50", "3.00"), Decimal("2")), euros("-1", "3"))

	def test_refuses_a_total_the_parts_cannot_reach_without_moving_a_whole_part(self):
		with self.assertRaises(ValueError):
			apportion_full_euros(euros("1", "2"), Decimal("4"))

	def test_refuses_a_total_with_cents(self):
		with self.assertRaises(ValueError):
			apportion_full_euros(euros("1.50"), Decimal("1.50"))

	def test_never_returns_negative_zero(self):
		self.assertEqual([str(part) for part in apportion_full_euros(euros("-0.40"), Decimal("0"))], ["0"])

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			apportion_full_euros((0.5,), Decimal("1"))
		with self.assertRaises(TypeError):
			apportion_full_euros(euros("0.5"), 1.0)
