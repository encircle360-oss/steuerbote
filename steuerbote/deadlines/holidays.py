"""The public holidays of every German state, for a company whose deadlines have no Holiday List.

„Fällt das Ende einer Frist auf einen Sonntag, einen gesetzlichen Feiertag oder einen Sonnabend, so endet die Frist
mit dem Ablauf des nächstfolgenden Werktags.“ (§ 108 Abs. 3 AO) The holidays are those at the seat of the authority:
the Finanzamt for the Voranmeldung and the Sondervorauszahlung, the BZSt for the Zusammenfassende Meldung. The states
set them in their Feiertagsgesetze; every state names Neujahr, Karfreitag, Ostermontag, the 1st of May, Christi
Himmelfahrt, Pfingstmontag and both Christmas holidays, and the Tag der Deutschen Einheit is a holiday by federal law
(Art. 2 Abs. 2 Einigungsvertrag). These days move a deadline wherever the authority sits, so a company without a
Holiday List of its own gets them; a holiday of its state only, such as Fronleichnam, needs the list.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable
from datetime import date, timedelta

# Days after Easter Sunday: Karfreitag, Ostermontag, Christi Himmelfahrt and Pfingstmontag.
EASTER_OFFSETS = (-2, 1, 39, 50)
# Month and day: Neujahr, 1st of May, Tag der Deutschen Einheit and both Christmas holidays.
FIXED = ((1, 1), (5, 1), (10, 3), (12, 25), (12, 26))


def easter_sunday(year: int) -> date:
	"""Easter Sunday of the Gregorian calendar, by the computus of Meeus, Jones and Butcher."""
	golden = year % 19
	century, years = divmod(year, 100)
	leap_centuries, leftover = divmod(century, 4)
	correction = (century + 8) // 25
	moon = (century - correction + 1) // 3
	epact = (19 * golden + century - leap_centuries - moon + 15) % 30
	quarters, rest = divmod(years, 4)
	weekday = (32 + 2 * leftover + 2 * quarters - epact - rest) % 7
	shift = (golden + 11 * epact + 22 * weekday) // 451
	month, day = divmod(epact + weekday - 7 * shift + 114, 31)
	return date(year, month, day + 1)


def nationwide(years: Iterable[int]) -> frozenset[date]:
	"""The holidays of every state in ``years``."""
	found: set[date] = set()
	for year in years:
		easter = easter_sunday(year)
		found.update(easter + timedelta(days=offset) for offset in EASTER_OFFSETS)
		found.update(date(year, month, day) for month, day in FIXED)
	return frozenset(found)
