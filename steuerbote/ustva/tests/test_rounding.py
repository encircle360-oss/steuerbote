from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva.rounding import (
	floor_euro,
	floor_hundred,
	require_decimal,
	tax_from_base,
	to_cents,
	to_full_euros,
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
