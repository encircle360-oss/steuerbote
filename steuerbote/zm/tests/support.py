"""Test data of the ZM core: figures in the German number format and invented vouchers and USt-IdNrn."""

from decimal import Decimal

from steuerbote.zm.lines import VoucherAmount


def d(value: str) -> Decimal:
	return Decimal(value)


class GermanFigures:
	"""The figures as a site with the number format #.###,## shows them."""

	def money(self, amount: Decimal) -> str:
		digits = f"{amount:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
		return f"{digits} €"

	def percent(self, value: Decimal) -> str:
		return f"{value:.1f}".replace(".", ",") + " %"


FIGURES = GermanFigures()

# Invented numbers in the form of their country.
AUSTRIA = "ATU12345678"
FRANCE = "FR12345678901"
SPAIN = "ESX1234567X"


def invoice(
	number: str,
	amount: str,
	kennzahl: str = "41",
	party: str | None = "Muster GmbH",
	vat_id: str | None = AUSTRIA,
	destination: str | None = None,
	voucher_type: str = "Sales Invoice",
) -> VoucherAmount:
	return VoucherAmount(f"{voucher_type}:{number}", kennzahl, d(amount), party, vat_id, destination)
