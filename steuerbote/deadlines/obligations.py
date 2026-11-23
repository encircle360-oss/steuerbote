"""Which filings the VAT Return Settings of a company owe, for which period, and when each is due.

The rules and their sources are those of the cores; this module asks them period by period:

- Umsatzsteuer-Voranmeldung: one for each Voranmeldungszeitraum the rules of the settings set
  (vat_return_settings.rules.rhythm_for). A month the Finanzamt exempts from the Voranmeldungen owes none, and
  neither does a month before the first rule. Period.deadline gives the day: the 10th day after the end of the
  period, one month later with the Dauerfristverlängerung of its year, and the next working day for a Saturday,
  a Sunday or a holiday (§ 18 Absatz 1 Satz 1 UStG, § 46 UStDV, § 108 Absatz 3 AO).
- Zusammenfassende Meldung: one for each Meldezeitraum of the rhythm in the settings (steuerbote.zm.rhythm,
  goods_period and coverage). ReportingPeriod.deadline gives the day: the 25th day after the end of the
  Meldezeitraum, never extended, and moved off weekends and holidays as the Voranmeldung is (§ 18a Absatz 1 and
  11 UStG, § 108 Absatz 3 AO).
- Sondervorauszahlung: one for each year with the Dauerfristverlängerung whose first Voranmeldungszeitraum is a
  month. It is due when that Voranmeldung is due without the extension (§ 48 Absatz 1 and 2 UStDV,
  steuerbote.dauerfrist.period.antrag_deadline): on 10 February for January, as sondervorauszahlung_deadline
  has it, and later for a company whose Voranmeldungen begin later in the year. A quarterly filer applies for
  the extension once and pays no Sondervorauszahlung (§ 47 Absatz 1 UStDV), so it owes nothing here.

The annual filings, from the Umsatzsteuererklärung to the Offenlegung of the Jahresabschluss, are the kinds of
steuerbote.deadlines.annual, which owes them from the Annual Filing Settings.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

from steuerbote import dauerfrist
from steuerbote.steuerbote.doctype.vat_return_settings import rules
from steuerbote.ustva.period import Period, Rhythm
from steuerbote.zm import rhythm as zm_rhythm
from steuerbote.zm.period import ReportingPeriod

if TYPE_CHECKING:
	from steuerbote.deadlines.annual import Note, OpeningBalance

MONTHS_PER_YEAR = 12


class Kind(Enum):
	"""What falls due. The names read the same in every language, like the status of a VAT Return."""

	VORANMELDUNG = "Umsatzsteuer-Voranmeldung"
	ZUSAMMENFASSENDE_MELDUNG = "Zusammenfassende Meldung"
	SONDERVORAUSZAHLUNG = "Sondervorauszahlung"
	UMSATZSTEUERERKLAERUNG = "Umsatzsteuererklärung"
	KOERPERSCHAFTSTEUERERKLAERUNG = "Körperschaftsteuererklärung"
	GEWERBESTEUERERKLAERUNG = "Gewerbesteuererklärung"
	E_BILANZ = "E-Bilanz"
	FESTSTELLUNG = "Feststellung Jahresabschluss"
	OFFENLEGUNG = "Offenlegung Jahresabschluss"


@dataclass(frozen=True, slots=True)
class Obligation:
	"""A filing the settings owe: its kind, its period, the label of the period and the day it is due.

	``period`` is the Voranmeldungszeitraum, the Meldezeitraum or, for the Sondervorauszahlung and the annual filings,
	the year; the Eröffnungsbilanz of the founding year has a period of its own beside the year of the E-Bilanz.
	``coverage`` holds the months a Meldezeitraum reports and is None for the other kinds. ``notes`` say what the day
	rests on where it is more than the rule of its kind, such as a Steuerberatung or an unknown size class.
	"""

	kind: Kind
	period: Period | ReportingPeriod | int | OpeningBalance
	label: str
	due: date
	coverage: zm_rhythm.Coverage | None = None
	notes: tuple[Note, ...] = ()


def obligations(
	period_rules: Iterable[rules.PeriodRule],
	prepayments: Iterable[rules.Prepayment],
	zm_rules: Iterable[zm_rhythm.Rule],
	until: date,
	holidays: Collection[date] = (),
) -> list[Obligation]:
	"""Every filing the settings owe that is due on or before ``until``, kind by kind in the order of the periods."""
	period_rules, prepayments = tuple(period_rules), tuple(prepayments)
	return [
		*voranmeldungen(period_rules, prepayments, until, holidays),
		*zusammenfassende_meldungen(zm_rules, until, holidays),
		*sondervorauszahlungen(period_rules, prepayments, until, holidays),
	]


def voranmeldungen(
	period_rules: Iterable[rules.PeriodRule],
	prepayments: Iterable[rules.Prepayment],
	until: date,
	holidays: Collection[date] = (),
) -> Iterator[Obligation]:
	"""The Voranmeldungen due on or before ``until``, from the first rule on."""
	period_rules, prepayments = tuple(period_rules), tuple(prepayments)
	seen: set[Period] = set()
	for year, month in _months(period_rules, until):
		try:
			rhythm = rules.rhythm_for(period_rules, year, month)
		except rules.NoVoranmeldungError:
			continue
		period = Period.containing(date(year, month, 1), rhythm)
		if period in seen:
			continue
		seen.add(period)
		extended = rules.has_dauerfrist(prepayments, period.year)
		due = period.deadline(dauerfristverlaengerung=extended, holidays=holidays)
		if due <= until:
			yield Obligation(Kind.VORANMELDUNG, period, period.label, due)


def zusammenfassende_meldungen(
	zm_rules: Iterable[zm_rhythm.Rule], until: date, holidays: Collection[date] = ()
) -> Iterator[Obligation]:
	"""The Zusammenfassende Meldungen due on or before ``until``, one for each Meldezeitraum from the first rule
	on; ZmError for rules that leave months open, as coverage() checks them."""
	zm_rules = tuple(zm_rules)
	seen: set[ReportingPeriod] = set()
	for year, month in _months(zm_rules, until):
		period = zm_rhythm.goods_period(zm_rules, year, month)
		if period in seen:
			continue
		seen.add(period)
		due = period.deadline(holidays)
		if due <= until:
			covered = zm_rhythm.coverage(zm_rules, period)
			yield Obligation(Kind.ZUSAMMENFASSENDE_MELDUNG, period, period.label, due, covered)


def sondervorauszahlungen(
	period_rules: Iterable[rules.PeriodRule],
	prepayments: Iterable[rules.Prepayment],
	until: date,
	holidays: Collection[date] = (),
) -> Iterator[Obligation]:
	"""The Sondervorauszahlungen due on or before ``until``, one for each year with the Dauerfristverlängerung
	whose first Voranmeldungszeitraum is a month."""
	period_rules = tuple(period_rules)
	years = sorted({prepayment.year for prepayment in prepayments if prepayment.dauerfristverlaengerung})
	for year in years:
		first = first_voranmeldungszeitraum(period_rules, year)
		if first is None or first.rhythm is not Rhythm.MONTHLY:
			continue
		due = dauerfrist.antrag_deadline(first, holidays)
		if due <= until:
			yield Obligation(Kind.SONDERVORAUSZAHLUNG, year, str(year), due)


def first_voranmeldungszeitraum(period_rules: Iterable[rules.PeriodRule], year: int) -> Period | None:
	"""The first Voranmeldungszeitraum the rules set in ``year``, or None if they set none."""
	period_rules = tuple(period_rules)
	for month in range(1, MONTHS_PER_YEAR + 1):
		try:
			rhythm = rules.rhythm_for(period_rules, year, month)
		except rules.SettingsError:
			continue
		return Period.containing(date(year, month, 1), rhythm)
	return None


def _months(given: Iterable[rules.PeriodRule | zm_rhythm.Rule], until: date) -> Iterator[tuple[int, int]]:
	"""Year and month from the start of the first of the rules to the month of ``until``."""
	starts = [rule.start for rule in given]
	if not starts:
		return
	year, month = min(starts)
	for index in range(year * MONTHS_PER_YEAR + month - 1, until.year * MONTHS_PER_YEAR + until.month):
		yield index // MONTHS_PER_YEAR, index % MONTHS_PER_YEAR + 1
