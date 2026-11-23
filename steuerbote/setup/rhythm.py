"""The Voranmeldungszeitraum the setup proposes for the year it runs in, after § 18 Absatz 2 and 2a UStG.

The law, as gesetze-im-internet.de gives it on 23 November 2026 (https://www.gesetze-im-internet.de/ustg_1980/__18.html):

- Satz 1: „Voranmeldungszeitraum ist das Kalendervierteljahr.“
- Satz 2: „Beträgt die Steuer für das vorangegangene Kalenderjahr mehr als 9 000 Euro, ist der Kalendermonat
  Voranmeldungszeitraum.“
- Satz 3: „Beträgt die Steuer für das vorangegangene Kalenderjahr nicht mehr als 2 000 Euro, kann das Finanzamt den
  Unternehmer von der Verpflichtung zur Abgabe der Voranmeldungen und Entrichtung der Vorauszahlungen befreien.“
- Satz 4: „Nimmt der Unternehmer seine berufliche oder gewerbliche Tätigkeit auf, ist im laufenden und folgenden
  Kalenderjahr Voranmeldungszeitraum der Kalendermonat.“
- Satz 6: „Für die Besteuerungszeiträume 2021 bis 2026 ist abweichend von Satz 4 in den Fällen, in denen der
  Unternehmer seine gewerbliche oder berufliche Tätigkeit nur in einem Teil des vorangegangenen Kalenderjahres
  ausgeübt hat, die tatsächliche Steuer in eine Jahressteuer umzurechnen und in den Fällen, in denen der Unternehmer
  seine gewerbliche oder berufliche Tätigkeit im laufenden Kalenderjahr aufnimmt, die voraussichtliche Steuer des
  laufenden Kalenderjahres maßgebend.“
- Absatz 2a Satz 1: „Der Unternehmer kann an Stelle des Kalendervierteljahres den Kalendermonat als
  Voranmeldungszeitraum wählen, wenn sich für das vorangegangene Kalenderjahr ein Überschuss zu seinen Gunsten von
  mehr als 9 000 Euro ergibt.“

propose() follows these sentences for a year, the day the company began (its Date of Establishment) and the tax of
the year before:

- A company that began in the year or the year before files monthly from 2027 on (Satz 4). For 2026 and earlier
  Satz 6 replaces Satz 4: the expected tax of the year, or the tax of the part year turned into a tax for a whole
  year, decides. Steuerbote knows neither, so it proposes nothing then, nor for a company that begins after the
  year.
- Otherwise the tax of the previous year decides; without it there is no proposal. Above 9,000 € the company files
  monthly (Satz 2), else quarterly (Satz 1).
- With a tax of at most 2,000 € the Finanzamt may exempt the company from the Voranmeldungen (Satz 3), and with a
  surplus above 9,000 € the company may choose the month (Absatz 2a). Only the Finanzamt or the company decides
  these, so the proposal stays quarterly and says that the other way is open.

Satz 5, the monthly Voranmeldung of a Vorratsgesellschaft or Firmenmantel, rests on facts the books do not hold. The
Finanzamt sets the Voranmeldungszeitraum in the end, so the setup names its proposal and the user checks it. This
module is pure Python and never imports Frappe.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from steuerbote.steuerbote.doctype.vat_return_settings.rules import FilingRhythm
from steuerbote.ustva.rounding import require_decimal

MONTHLY_ABOVE = Decimal("9000")
EXEMPTION_UP_TO = Decimal("2000")
MONTH_OF_CHOICE_ABOVE = Decimal("9000")
# The last Besteuerungszeitraum in which Satz 6 replaces Satz 4 for a company that began its business.
LAST_YEAR_OF_SATZ_6 = 2026
QUARTER_START_MONTHS = (1, 4, 7, 10)


class Reason(Enum):
	"""Why the setup proposes a Voranmeldungszeitraum, or why it proposes none."""

	STARTED = "started"
	STARTED_THIS_YEAR = "started_this_year"
	STARTED_LAST_YEAR = "started_last_year"
	NOT_STARTED = "not_started"
	NO_TAX = "no_tax"
	TAX_ABOVE_LIMIT = "tax_above_limit"
	TAX_UP_TO_LIMIT = "tax_up_to_limit"


@dataclass(frozen=True, slots=True)
class Proposal:
	"""The proposed Voranmeldungszeitraum, None for none, with its reason and the tax of the previous year it rests
	on. ``exemption_possible`` and ``month_possible`` name what the Finanzamt or the company may still decide."""

	rhythm: FilingRhythm | None
	reason: Reason
	tax: Decimal | None = None
	exemption_possible: bool = False
	month_possible: bool = False


def needs_tax(year: int, began: date | None) -> bool:
	"""Whether the proposal for the year rests on the tax of the previous year, so that the caller has to find it."""
	return began is None or began.year < year - 1


def propose(year: int, began: date | None, previous_year_tax: Decimal | None) -> Proposal:
	"""The Voranmeldungszeitraum of § 18 Absatz 2 UStG for the year."""
	if not needs_tax(year, began):
		return _started(year, began)
	if previous_year_tax is None:
		return Proposal(None, Reason.NO_TAX)
	tax = require_decimal(previous_year_tax)
	if tax > MONTHLY_ABOVE:
		return Proposal(FilingRhythm.MONTHLY, Reason.TAX_ABOVE_LIMIT, tax)
	return Proposal(
		FilingRhythm.QUARTERLY,
		Reason.TAX_UP_TO_LIMIT,
		tax,
		exemption_possible=tax <= EXEMPTION_UP_TO,
		month_possible=-tax > MONTH_OF_CHOICE_ABOVE,
	)


def first_month(year: int, began: date | None) -> int:
	"""The month the first rule of the settings starts in: the quarter of the start of a company that began in the
	year, as a Voranmeldungszeitraum changes with a Kalendervierteljahr (vat_return_settings/rules.py); else 1."""
	if began is None or began.year != year:
		return 1
	return max(month for month in QUARTER_START_MONTHS if month <= began.month)


def _started(year: int, began: date) -> Proposal:
	if began.year > year:
		return Proposal(None, Reason.NOT_STARTED)
	if year > LAST_YEAR_OF_SATZ_6:
		return Proposal(FilingRhythm.MONTHLY, Reason.STARTED)
	return Proposal(None, Reason.STARTED_THIS_YEAR if began.year == year else Reason.STARTED_LAST_YEAR)
