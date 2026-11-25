"""What a Voranmeldung owes besides its Kennzahlen: a period that has ended, and the Zusammenfassende Meldung of its
turnover in other member states.

**The end of the period.** Under the Soll-Versteuerung the tax arises „mit Ablauf des Voranmeldungszeitraums, in dem
die Leistungen ausgeführt worden sind“ (§ 13 Abs. 1 Nr. 1 Buchst. a Satz 1 UStG), and the Voranmeldung is filed „bis
zum 10. Tag nach Ablauf jedes Voranmeldungszeitraums“ (§ 18 Abs. 1 Satz 1 UStG). Before the last day of the period has
passed, its turnover is not complete, and a return filed then would make every later booking of the period a booking
after the filing. Such a return is not ready and is filed only with remarks; ERiC itself notes a period that has not
ended. A draft may still be prepared and calculated early.

**The Zusammenfassende Meldung.** A company that reports innergemeinschaftliche Lieferungen (Kz 41), Lieferungen of
a Dreiecksgeschäft (Kz 42, § 25b Abs. 2 UStG) or sonstige Leistungen whose tax the recipient owes in another member
state (Kz 21) files a Zusammenfassende Meldung for them (§ 18a Abs. 1 and 2 UStG). Steuerbote knows its deadlines from
the rhythm the VAT Return Settings record; a return with such turnover in a month without that rhythm says so.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Sequence
from collections.abc import Mapping as ReadOnlyMapping
from datetime import date
from decimal import Decimal

from steuerbote.ustva.period import Period, day_label
from steuerbote.ustva.plausibility import Code, Figures, Hint
from steuerbote.ustva.rounding import ZERO

# The Kennzahlen whose turnover the Zusammenfassende Meldung reports, in the order of the form USt 1 A 2026.
ZM_KENNZAHLEN = ("41", "42", "21")


def has_ended(period: Period, today: date) -> bool:
	"""Whether the last day of the period has passed."""
	return today > period.end


def period_hints(period: Period, today: date) -> list[Hint]:
	"""A warning on a period whose last day has not passed."""
	if has_ended(period, today):
		return []
	end = day_label(period.end)
	text = (
		f"{period.label} endet erst am {end}. Die Steuer entsteht mit Ablauf des Voranmeldungszeitraums "
		"(§ 13 Abs. 1 Nr. 1 Buchst. a UStG), und die Voranmeldung wird nach seinem Ablauf abgegeben (§ 18 Abs. 1 "
		f"Satz 1 UStG): Bis dahin ist die Meldung nicht bereit. Berechnen Sie sie nach dem {end} erneut."
	)
	return [Hint(Code.PERIOD_NOT_ENDED, text)]


def zm_rhythm_hints(
	amounts: ReadOnlyMapping[str, Decimal], months_without_rhythm: Sequence[str], figures: Figures
) -> list[Hint]:
	"""A warning when a Kennzahl of the Zusammenfassende Meldung has an amount and months of the period, named in
	``months_without_rhythm``, have no rhythm of the Meldung."""
	reported = [(number, amounts[number]) for number in ZM_KENNZAHLEN if amounts.get(number, ZERO) != ZERO]
	if not reported or not months_without_rhythm:
		return []
	(first, first_amount), *others = reported
	named = [f"Kz {first} meldet {figures.money(first_amount)}"]
	named += [f"Kz {number} {figures.money(amount)}" for number, amount in others]
	text = (
		f"{_listed(named)}, aber die Einstellungen nennen für {_listed(months_without_rhythm)} keinen Rhythmus der "
		"Zusammenfassenden Meldung. Für innergemeinschaftliche Lieferungen, Dreiecksgeschäfte und sonstige Leistungen, "
		"deren Steuer der Empfänger in einem anderen Mitgliedstaat schuldet, ist eine Zusammenfassende Meldung "
		"abzugeben (§ 18a Abs. 1 und 2 UStG): Tragen Sie den Rhythmus in den Einstellungen Umsatzsteuer-Voranmeldung "
		"ein, dann kennt Steuerbote die Meldung und ihre Frist."
	)
	return [Hint(Code.ZM_WITHOUT_RHYTHM, text)]


def _listed(items: Iterable[str]) -> str:
	items = list(items)
	return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} und {items[-1]}"
