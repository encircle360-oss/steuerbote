"""The Sondervorauszahlung of a monthly filer with Dauerfristverlängerung: Zeilen 8 and 9 of form USt 1 H.

§ 47 UStDV (https://www.gesetze-im-internet.de/ustdv_1980/__47.html):

- Absatz 1: „Die Fristverlängerung ist bei einem Unternehmer, der die Voranmeldungen monatlich zu übermitteln
  hat, unter der Auflage zu gewähren, dass dieser eine Sondervorauszahlung auf die Steuer eines jeden
  Kalenderjahres entrichtet. Die Sondervorauszahlung beträgt ein Elftel der Summe der Vorauszahlungen für das
  vorangegangene Kalenderjahr.“
- Absatz 2: „Hat der Unternehmer seine gewerbliche oder berufliche Tätigkeit nur in einem Teil des
  vorangegangenen Kalenderjahres ausgeübt, so ist die Summe der Vorauszahlungen dieses Zeitraums in eine
  Jahressumme umzurechnen. Angefangene Kalendermonate sind hierbei als volle Kalendermonate zu behandeln.“
- Absatz 3: „Hat der Unternehmer seine gewerbliche oder berufliche Tätigkeit im laufenden Kalenderjahr
  begonnen, so ist die Sondervorauszahlung auf der Grundlage der zu erwartenden Vorauszahlungen dieses
  Kalenderjahres zu berechnen.“

The Anleitung USt 5 E 2026 (BMF letter of 29 December 2025, GZ III C 3 - S 7344/00039/007/036, Zeilen 8 bis 9)
sums the Vorauszahlungen „ohne Berücksichtigung der Sondervorauszahlung“, and Zeile 8 of USt 1 H is the „Summe
der verbleibenden Umsatzsteuer-Vorauszahlungen zuzüglich der zu berücksichtigenden Sondervorauszahlung“: Kz 83
of the Voranmeldungen of the previous year plus the Sondervorauszahlung that Kz 39 credited in them. Its
example takes 39.000 € in Kz 83 and 5.000 € in Kz 39 to 44.000 € in Zeile 8 and 4.000 € in Zeile 9. „Ergibt
sich bei der Berechnung der Sondervorauszahlung in Zeile 8 ein Überschuss zu Ihren Gunsten, ist die
Sondervorauszahlung in Zeile 9 mit 0 € einzutragen.“ For a business that begins in the year it adds: „Die
Sondervorauszahlung soll der durchschnittlichen Vorauszahlung eines Kalendermonats entsprechen.“

Zeile 9 is Kz 38, whole euros without sign (Jahresdokumentation_UStVA_2026.ods of the ERiC documentation
44.3.6.0: GeldBetragOhneCent, Formatkennzeichen U, Vordruckzeile 9). Zeile 8 has no field and is not
transmitted. Neither the law nor the Anleitung says how the eleventh becomes whole euros, so Steuerbote drops
the cents as it does for a Bemessungsgrundlage; this is an assumption to be confirmed with the ELSTER hotline.
The base keeps its cents, and the fraction of an annual sum, so that the cents are dropped once, from Kz 38.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from steuerbote.ustva.rounding import CENT, ZERO, require_decimal, to_full_euros

MONTHS_PER_YEAR = 12
ELEVEN = Decimal(11)


def previous_year_base(
	kz83: Iterable[Decimal], kz39: Decimal = ZERO, months_active: int = MONTHS_PER_YEAR
) -> Decimal:
	"""Zeile 8 of USt 1 H: the Vorauszahlungen of the previous year with the Sondervorauszahlung they credited.

	``kz83`` holds Kz 83 of each Voranmeldung of the previous calendar year as filed, the latest filing of each
	Voranmeldungszeitraum, and ``kz39`` the Sondervorauszahlung their Kz 39 credited. A business that was active
	in ``months_active`` months of that year only has the sum converted into an annual sum; see
	months_of_activity for how the months count.
	"""
	amounts = [_cents(amount, "Kz 83") for amount in kz83]
	if not amounts:
		raise ValueError("the base needs Kz 83 of at least one Voranmeldung of the previous year")
	credited = _cents(kz39, "Kz 39")
	if credited < ZERO:
		raise ValueError(f"Kz 39 takes no negative amount, not {kz39}")
	months = _months(months_active)
	total = sum(amounts, start=ZERO) + credited
	if months == MONTHS_PER_YEAR:
		return total
	return total * MONTHS_PER_YEAR / months


def sondervorauszahlung(base: Decimal) -> Decimal:
	"""Zeile 9 of USt 1 H, Kz 38: one eleventh of the base in whole euros, 0 when the base is not positive."""
	if not require_decimal(base).is_finite():
		raise ValueError(f"the base is not an amount: {base}")
	if base <= ZERO:
		return ZERO
	return to_full_euros(base / ELEVEN)


def expected_sondervorauszahlung(expected: Decimal, months_active: int) -> Decimal:
	"""Kz 38 for a business that begins in the year: the average Vorauszahlung of a calendar month.

	``expected`` is the sum of the Vorauszahlungen the business expects for the year, ``months_active`` the
	number of months in which it is active. An expected surplus gives 0, as a surplus in Zeile 8 does. The
	months come from months_of_activity, which counts the month of the start in full as § 47 Absatz 2 Satz 2
	UStDV does for the previous year; for the year of the start neither the law nor the Anleitung says how to
	count them, which makes this an assumption.
	"""
	amount = _cents(expected, "the expected Vorauszahlungen")
	months = _months(months_active)
	if amount <= ZERO:
		return ZERO
	return to_full_euros(amount / months)


def months_of_activity(year: int, began: date) -> int:
	"""The calendar months of ``year`` in which a business that began on ``began`` was active.

	The month of the start counts in full: „Angefangene Kalendermonate sind hierbei als volle Kalendermonate zu
	behandeln“ (§ 47 Absatz 2 Satz 2 UStDV). A business that began before the year was active in all of it.
	"""
	if not _is_int(year) or not 1 <= year <= 9999:
		raise ValueError(f"year must be a four-digit year, not {year!r}")
	if not isinstance(began, date):
		raise TypeError(f"began must be a date, not {type(began).__name__}")
	if began.year > year:
		raise ValueError(f"a business that began on {began.isoformat()} began after {year}")
	if began.year < year:
		return MONTHS_PER_YEAR
	return MONTHS_PER_YEAR - began.month + 1


def _cents(amount: Decimal, name: str) -> Decimal:
	if not require_decimal(amount).is_finite() or amount != amount.quantize(CENT):
		raise ValueError(f"{name} must be an amount in cents, not {amount}")
	return amount


def _months(months: int) -> int:
	if not _is_int(months) or not 1 <= months <= MONTHS_PER_YEAR:
		raise ValueError(f"the months of activity must be between 1 and 12, not {months!r}")
	return months


def _is_int(value: object) -> bool:
	"""True is an int to Python, but neither a year nor a number of months."""
	return isinstance(value, int) and not isinstance(value, bool)
