"""Amounts in the messages of the Umsatzsteuererklärung as a German text writes them (steuerbote/ustjahr/text.py)."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.ustjahr import text


class EurosTest(TestCase):
	def test_an_amount_has_a_comma_before_the_cents_and_points_between_the_thousands(self):
		for amount, written in (
			("2706", "2.706,00"),
			("-7737.77", "-7.737,77"),
			("0", "0,00"),
			("1234567.891", "1.234.567,89"),
			("47.5", "47,50"),
		):
			with self.subTest(amount=amount):
				self.assertEqual(text.euros(Decimal(amount)), written)
