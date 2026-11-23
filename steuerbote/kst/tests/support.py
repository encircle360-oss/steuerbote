"""Invented ledger lines and mappings for the tests of the core."""

from decimal import Decimal

from steuerbote.ustva.calculation import LedgerLine


def debit(account: str, amount: str, voucher: str | None = "JV-1") -> LedgerLine:
	return LedgerLine(account, debit=Decimal(amount), voucher=voucher)


def credit(account: str, amount: str, voucher: str | None = "JV-1") -> LedgerLine:
	return LedgerLine(account, credit=Decimal(amount), voucher=voucher)


class GermanFigures:
	"""The figures as a site with the number format #.###,## shows them."""

	def money(self, amount: Decimal) -> str:
		digits = f"{amount:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
		return f"{digits} €"

	def percent(self, value: Decimal) -> str:
		return f"{value:.1f}".replace(".", ",") + " %"


FIGURES = GermanFigures()
