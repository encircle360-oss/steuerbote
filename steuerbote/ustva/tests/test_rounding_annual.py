"""The rounding rules of the annual filings: Körperschaftsteuer, Solidaritätszuschlag and Gewerbesteuer."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva.rounding import ceil_euro, floor_euro, floor_hundred, half_up_euro, truncate_cents


class FloorEuroTest(TestCase):
	"""The Körperschaftsteuer and the Steuermessbetrag are rounded down to full euros."""

	def test_drops_the_cents_of_a_positive_amount(self):
		self.assertEqual(floor_euro(Decimal("16680.99")), Decimal("16680"))

	def test_rounds_a_negative_amount_towards_minus_infinity(self):
		self.assertEqual(floor_euro(Decimal("-0.01")), Decimal("-1"))

	def test_keeps_whole_amounts_and_never_returns_negative_zero(self):
		self.assertEqual(floor_euro(Decimal("3766")), Decimal("3766"))
		self.assertEqual(str(floor_euro(Decimal("-0"))), "0")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			floor_euro(1.5)


class FloorHundredTest(TestCase):
	"""The Gewerbeertrag is rounded down to full 100 euros."""

	def test_rounds_down_to_full_hundreds(self):
		self.assertEqual(floor_hundred(Decimal("107699.99")), Decimal("107600"))
		self.assertEqual(floor_hundred(Decimal("107600")), Decimal("107600"))

	def test_gives_zero_below_one_hundred(self):
		self.assertEqual(str(floor_hundred(Decimal("99.99"))), "0")

	def test_rounds_a_negative_amount_towards_minus_infinity(self):
		self.assertEqual(floor_hundred(Decimal("-0.50")), Decimal("-100"))

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			floor_hundred(150.0)


class TruncateCentsTest(TestCase):
	"""The Solidaritätszuschlag drops the fractions of a cent."""

	def test_drops_the_fractions_of_a_cent(self):
		self.assertEqual(truncate_cents(Decimal("917.4099")), Decimal("917.40"))
		self.assertEqual(truncate_cents(Decimal("0.019")), Decimal("0.01"))

	def test_truncates_towards_zero_without_negative_zero(self):
		self.assertEqual(truncate_cents(Decimal("-1.239")), Decimal("-1.23"))
		self.assertEqual(str(truncate_cents(Decimal("-0.009"))), "0.00")

	def test_keeps_two_decimals_on_whole_amounts(self):
		self.assertEqual(str(truncate_cents(Decimal("917"))), "917.00")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			truncate_cents(0.5)


class CeilEuroTest(TestCase):
	"""What the Jahresdokumentation calls Aufrunden: up to full euros."""

	def test_rounds_any_cent_up(self):
		self.assertEqual(ceil_euro(Decimal("22440.01")), Decimal("22441"))
		self.assertEqual(ceil_euro(Decimal("22440")), Decimal("22440"))

	def test_rounds_a_negative_amount_towards_plus_infinity_without_negative_zero(self):
		self.assertEqual(ceil_euro(Decimal("-1.99")), Decimal("-1"))
		self.assertEqual(str(ceil_euro(Decimal("-0.99"))), "0")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			ceil_euro(0.5)


class HalfUpEuroTest(TestCase):
	"""Declared amounts where the Jahresdokumentation gives no direction: half up, an unverified policy."""

	def test_rounds_half_up(self):
		self.assertEqual(half_up_euro(Decimal("86338.60")), Decimal("86339"))
		self.assertEqual(half_up_euro(Decimal("917.40")), Decimal("917"))
		self.assertEqual(half_up_euro(Decimal("0.50")), Decimal("1"))

	def test_rounds_half_away_from_zero_for_negative_amounts_without_negative_zero(self):
		self.assertEqual(half_up_euro(Decimal("-0.50")), Decimal("-1"))
		self.assertEqual(str(half_up_euro(Decimal("-0.49"))), "0")

	def test_rejects_floats(self):
		with self.assertRaises(TypeError):
			half_up_euro(0.5)
