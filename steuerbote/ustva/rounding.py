"""Rounding rules of the filings, the only place where steuerbote rounds an amount.

The Anleitung to form USt 1 A 2026 (BMF letter of 29 December 2025, GZ III C 3 - S 7344/00039/007/036)
says: "Tragen Sie bei den Bemessungsgrundlagen bitte nur Beträge in vollen Euro ein; bei den Umsatzsteuer-
und Vorsteuerbeträgen ist dagegen stets auch die Eintragung von Centbeträgen erforderlich."

Full euros means the cents are dropped, towards zero, for negative amounts as well. Tax amounts keep
their cents and are rounded half up. Every amount is a Decimal; floats are rejected because binary
floating point cannot represent cents exactly.

The annual filings round by the rules of their own laws and of the Jahresdokumentation of their Datenart, each
function below with its source.
"""

from decimal import ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_UP, Decimal

EURO = Decimal("1")
CENT = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0")


def require_decimal(amount: object) -> Decimal:
	if isinstance(amount, Decimal):
		return amount
	raise TypeError(f"amounts must be Decimal, not {type(amount).__name__}")


def to_full_euros(amount: Decimal) -> Decimal:
	"""Drop the cents of a Bemessungsgrundlage, towards zero."""
	return _without_negative_zero(require_decimal(amount).quantize(EURO, rounding=ROUND_DOWN))


def to_cents(amount: Decimal) -> Decimal:
	"""Round a tax amount to cents, half up."""
	return _without_negative_zero(require_decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP))


def tax_from_base(base: Decimal, rate_percent: Decimal) -> Decimal:
	"""The tax the form derives from a base, e.g. 19 % of Kennzahl 81."""
	return to_cents(require_decimal(base) * require_decimal(rate_percent) / HUNDRED)


def floor_euro(amount: Decimal) -> Decimal:
	"""Round down to whole euros: the Körperschaftsteuer and the Steuermessbetrag.

	„Die sich im Zuge der Festsetzung ergebenden einzelnen Körperschaftsteuerbeträge sind jeweils zu Gunsten des
	Steuerpflichtigen auf volle Euro-Beträge zu runden.“ (§ 31 Abs. 1 Satz 2 KStG); rule 8900331 of
	Jahresdokumentation_E30_2025.ods computes the Körperschaftsteuer as Abrunden([E8007504] * 0.15), „auf volle Euro
	abgerundet“. „Der Steuermessbetrag ist erforderlichenfalls auf volle Euro nach unten abzurunden“ (R 14.1 Satz 3
	GewStR 2009, Amtliches Gewerbesteuer-Handbuch 2024). Both round amounts that are not negative; a negative amount
	goes down as well, away from zero.
	"""
	return _without_negative_zero(require_decimal(amount).quantize(EURO, rounding=ROUND_FLOOR))


def floor_hundred(amount: Decimal) -> Decimal:
	"""Round down to full 100 euros: the Gewerbeertrag.

	„Der Gewerbeertrag ist auf volle 100 Euro nach unten abzurunden“ (§ 11 Abs. 1 Satz 3 GewStG). A negative amount
	goes down as well, to the next lower multiple of 100.
	"""
	hundreds = (require_decimal(amount) / HUNDRED).quantize(EURO, rounding=ROUND_FLOOR)
	return _without_negative_zero(hundreds * HUNDRED)


def _without_negative_zero(amount: Decimal) -> Decimal:
	return amount + ZERO
