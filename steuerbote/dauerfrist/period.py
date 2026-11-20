"""When form USt 1 H is due, and which Voranmeldung credits the Sondervorauszahlung.

- A Voranmeldung is due „bis zum zehnten Tag nach Ablauf jedes Voranmeldungszeitraums“ (§ 18 Absatz 1 Satz 1
  UStG). The Finanzamt extends this „um einen Monat“ on application (§ 46 Satz 1 UStDV), which Period.deadline
  knows as the Dauerfristverlängerung.
- The Antrag is due „bis zu dem Zeitpunkt [...], an dem die Voranmeldung, für die die Fristverlängerung
  erstmals gelten soll, nach § 18 Abs. 1, 2 und 2a des Gesetzes zu übermitteln ist“ (§ 48 Absatz 1 Satz 1
  UStDV), that is without the extension it applies for. A monthly filer computes and registers the
  Sondervorauszahlung in the Antrag and pays it „gleichzeitig“ (Sätze 4 and 5).
- While the extension holds, a monthly filer registers and pays the Sondervorauszahlung of each year „bis zum
  gesetzlichen Zeitpunkt der Übermittlung der ersten Voranmeldung“ (§ 48 Absatz 2 UStDV), the Voranmeldung for
  January: „jährlich bis zum 10. Februar“ (Anleitung USt 5 E 2026, Zeilen 8 bis 9).
- A quarterly filer applies once: „Der Antrag auf Dauerfristverlängerung ist nicht zu stellen, wenn
  Dauerfristverlängerung bereits gewährt worden ist. Er ist nicht jährlich zu wiederholen.“ (form USt 1 H 2026)
  The extension holds until the company gives it up or the Finanzamt revokes it (USt 5 E).
- A deadline on a Saturday, Sunday or public holiday moves to the next working day (§ 108 Absatz 3 AO).
  Period.deadline does that with the holidays the caller passes in, as they differ by state.
- „Die festgesetzte Sondervorauszahlung ist bei der Festsetzung der Vorauszahlung für den letzten
  Voranmeldungszeitraum des Besteuerungszeitraums zu berücksichtigen, für den die Fristverlängerung gilt.“
  (§ 48 Absatz 4 Satz 1 UStDV) The Anleitung USt 1 E 2026 (Zeile 49) puts it in the Voranmeldung for
  December, and for a company that ended its business or gave up the extension during the year in the last
  Voranmeldungszeitraum the extension covers.

The BMF letter of 29 December 2025 (GZ III C 3 - S 7344/00039/007/036) holds form USt 1 H and both Anleitungen.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

from steuerbote.dauerfrist.form import Context
from steuerbote.ustva.period import Period, Rhythm

DECEMBER = 12


@dataclass(frozen=True, slots=True)
class Obligation:
	"""A form USt 1 H a company has to file: its context and its deadline.

	``antrag`` is True when the form applies for the Dauerfristverlängerung, and False for the yearly Anmeldung
	der Sondervorauszahlung while it holds; then section I of the form „ist gegenstandslos“.
	"""

	context: Context
	deadline: date
	antrag: bool


def antrag_deadline(first_period: Period, holidays: Collection[date] = ()) -> date:
	"""The day the Antrag is due: when the first Voranmeldung it is to cover is due without the extension."""
	return first_period.deadline(dauerfristverlaengerung=False, holidays=holidays)


def sondervorauszahlung_deadline(year: int, holidays: Collection[date] = ()) -> date:
	"""The day the Sondervorauszahlung of ``year`` is due while the extension holds: 10 February."""
	return antrag_deadline(Period.month(year, 1), holidays)


def obligation(
	year: int, rhythm: Rhythm, first_period: Period | None = None, holidays: Collection[date] = ()
) -> Obligation | None:
	"""What a company with Dauerfristverlängerung files on form USt 1 H for ``year``, and by when.

	``first_period`` is the first Voranmeldungszeitraum the extension is to cover when the company applies for it
	in ``year``; without it the extension was granted before and holds on. A quarterly filer then files nothing.
	"""
	rhythm = Rhythm(rhythm)
	context = Context.for_rhythm(rhythm)
	if first_period is not None:
		if first_period.year != year:
			raise ValueError(
				f"the first Voranmeldungszeitraum of the extension lies in {first_period.year}, not in {year}"
			)
		if first_period.rhythm is not rhythm:
			raise ValueError(
				"the first Voranmeldungszeitraum of the extension is a "
				f"{first_period.rhythm.value} period for a {rhythm.value} filer"
			)
		return Obligation(context, antrag_deadline(first_period, holidays), antrag=True)
	if not context.with_sondervorauszahlung:
		return None
	return Obligation(context, sondervorauszahlung_deadline(year, holidays), antrag=False)


def crediting_period(year: int, rhythm: Rhythm, last_month: int = DECEMBER) -> Period:
	"""The Voranmeldungszeitraum whose Kz 39 credits the Sondervorauszahlung of ``year``.

	It is the last one of the year the extension covers: December or the fourth quarter, or the period of
	``last_month`` when the extension ends with that month.
	"""
	return Period.containing(Period.month(year, last_month).start, rhythm)
