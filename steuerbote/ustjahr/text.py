"""Amounts in the messages of the Umsatzsteuererklärung as a German text writes them: a comma before the cents and a
point between the thousands, such as 2.706,00.

This module is pure Python and never imports Frappe.
"""

from decimal import Decimal

from steuerbote.ustva.rounding import to_cents


def euros(amount: Decimal) -> str:
	"""The amount in euros and cents, such as -7.737,77."""
	return f"{to_cents(amount):,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
