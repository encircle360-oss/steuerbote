"""The annual deadlines of a company: which annual filings it owes for a year and when each is due.

Erklärungen. The Umsatzsteuererklärung „für das Kalenderjahr“ (§ 18 Abs. 3 Satz 1 UStG), the
Körperschaftsteuererklärung (§ 31 Abs. 1a KStG) with the Feststellungserklärung of the steuerliches Einlagekonto,
KSt 1 F (§ 27 Abs. 2 Satz 4 KStG), and the Erklärung zur Festsetzung des Gewerbesteuermessbetrags (§ 14a Satz 1
GewStG) refer to a calendar year, so they are due „spätestens sieben Monate nach Ablauf des Kalenderjahres“ (§ 149
Abs. 2 Satz 1 AO). Prepared by a Steuerberatung, all three are due „spätestens bis zum letzten Tag des Monats Februar
[...] des zweiten auf den Besteuerungszeitraum folgenden Kalenderjahres“ (§ 149 Abs. 3 Nr. 2, 3 and 4 AO). The Finanzamt
may order them earlier (§ 149 Abs. 4 Satz 1 AO), and „In den Fällen der Sätze 1 und 3 erstreckt sich eine Anordnung auf
alle Erklärungen im Sinne des Absatzes 3, die vom betroffenen Steuerpflichtigen für den gleichen Besteuerungszeitraum
oder Besteuerungszeitpunkt abzugeben sind“ (Satz 7), so the earliest day the Annual Filing Settings record for an
Erklärung of the year holds for all three. The rules are the same for the three Erklärungen, so
steuerbote.ustjahr.years.filing_deadline gives each of their days, moved off a Saturday, a Sunday and a holiday of the
company to the next working day (§ 108 Abs. 3 AO). A Kleinunternehmer files no Umsatzsteuererklärung: for him „die
Erklärungspflichten (§ 18 Absatz 1 bis 4)“ do not apply (§ 19 Abs. 1 Satz 2 UStG). What the Umsatzsteuererklärung
leaves to pay „ist [...] einen Monat nach dem Eingang der Steueranmeldung fällig“ (§ 18 Abs. 4 Satz 1 UStG), a day that
follows the filing, so it is no deadline here.

E-Bilanz. „der Inhalt der Bilanz, der Gewinn- und Verlustrechnung [...] ist nach amtlich vorgeschriebenem Datensatz
durch Datenfernübertragung zu übermitteln“ (§ 5b Abs. 1 Satz 1 EStG), with no deadline of its own: it goes with the
Körperschaftsteuererklärung of the VZ the Wirtschaftsjahr ends in (FAQ zur E-Bilanz, Version 2026-01, Tz. 5), so it
takes that day. „Im Fall der Eröffnung des Betriebs sind die Sätze 1 bis 3 entsprechend anzuwenden“ (Satz 4): in the
year of the founding the Eröffnungsbilanz goes as well, as a deadline of its own beside the E-Bilanz of the year and on
its day, which is an assumption and unverified.

Jahresabschluss. „Die Gesellschafter haben spätestens bis zum Ablauf der ersten acht Monate oder, wenn es sich um eine
kleine Gesellschaft handelt (§ 267 Abs. 1 des Handelsgesetzbuchs), bis zum Ablauf der ersten elf Monate des
Geschäftsjahrs über die Feststellung des Jahresabschlusses [...] zu beschließen“ (§ 42a Abs. 2 Satz 1 GmbHG), and the
documents „sind spätestens ein Jahr nach dem Abschlussstichtag des Geschäftsjahrs zu übermitteln, auf das sie sich
beziehen“ (§ 325 Abs. 1a Satz 1 HGB), unless the company is a subsidiary exempt under § 264 Abs. 3 HGB.
steuerbote.hgb.disclosure gives both days from the closing day and the size class the settings applied to the fiscal
year: without a class the shorter period, and no day moved off a weekend, since whether § 193 BGB applies is
unverified; a note says so.

Late. „Gegen denjenigen, der seiner Verpflichtung zur Abgabe einer Steuererklärung nicht oder nicht fristgemäß
nachkommt, kann ein Verspätungszuschlag festgesetzt werden“ (§ 152 Abs. 1 Satz 1 AO); it must be once an Erklärung
of a calendar year is not filed „binnen 14 Monaten nach Ablauf des Kalenderjahrs“, or after an early order „nicht bis
zu dem in der Anordnung bestimmten Zeitpunkt“ (§ 152 Abs. 2 Nr. 1 and 3 AO). The overview lists the deadlines; it
computes no surcharge.

A year is the VZ, the EZ and the year the Wirtschaftsjahr ends in, which is how the annual documents count it
(steuerbote.jahresmeldung.lifecycle.standard_fields). The first year is 2026 (docs/roadmap.md, „Ab 2026“), or the year
of the founding if later. This module is pure Python and never imports Frappe.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from enum import Enum

from steuerbote.deadlines.obligations import Kind, Obligation
from steuerbote.hgb import disclosure
from steuerbote.hgb.size import SizeClass
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import (
	SizeRecord,
	YearSettings,
	size_class_on,
	year_settings,
)
from steuerbote.ustjahr.years import filing_deadline

FIRST_YEAR = 2026
"""The first year of the annual filings (docs/roadmap.md, „Ab 2026“)."""
KINDS = (
	Kind.UMSATZSTEUERERKLAERUNG,
	Kind.KOERPERSCHAFTSTEUERERKLAERUNG,
	Kind.GEWERBESTEUERERKLAERUNG,
	Kind.E_BILANZ,
	Kind.FESTSTELLUNG,
	Kind.OFFENLEGUNG,
)
"""The kinds of the annual deadlines, in the order a year lists them."""
DECEMBER = 12
LAST_OF_DECEMBER = 31


class Note(Enum):
	"""What the day of a deadline rests on beyond the rule of its kind; the Frappe layer names each in the language
	of its reader."""

	ADVISOR = "advisor"
	"""A Steuerberatung prepares the Erklärungen of the year: the last day of February (§ 149 Abs. 3 AO)."""
	EARLY_REQUEST = "early_request"
	"""The Finanzamt ordered the Erklärungen of the year earlier (§ 149 Abs. 4 AO)."""
	WITH_KST = "with_kst"
	"""The E-Bilanz has no deadline of its own and goes with the Körperschaftsteuererklärung."""
	OPENING_BALANCE = "opening_balance"
	"""The Eröffnungsbilanz of the founding year, due with the E-Bilanz of the year by assumption."""
	ASSUMED_CLASS = "assumed_class"
	"""The settings hold no size class for the fiscal year, so the shorter period of § 42a Abs. 2 GmbHG applies."""
	ON_WEEKEND = "on_weekend"
	"""The day is a Saturday or a Sunday and stays, since whether § 193 BGB moves it is unverified."""


@dataclass(frozen=True, slots=True)
class OpeningBalance:
	"""The period of the Eröffnungsbilanz of the founding year, beside the year of the E-Bilanz."""

	year: int

	@property
	def label(self) -> str:
		return f"Eröffnungsbilanz {self.year}"


@dataclass(frozen=True, slots=True)
class AnnualYear:
	"""What the deadlines of one year rest on: the last day of the Wirtschaftsjahr that ends in it, whether a
	Steuerberatung prepares its Erklärungen, whether the company is a Kleinunternehmer, the earliest day the Finanzamt
	ordered an Erklärung of the year for, the size class of the fiscal year, whether the company is exempt from the
	Offenlegung, and whether the company was founded in it."""

	year: int
	fiscal_year_end: date
	advisor_prepares: bool = False
	kleinunternehmer: bool = False
	early_request: date | None = None
	size_class: SizeClass | None = None
	exempt_264_3: bool = False
	founding: bool = False


@dataclass(frozen=True, slots=True)
class AnnualRules:
	"""What the Annual Filing Settings, the Fiscal Years and the company say about its annual deadlines.

	``years`` are the years of the settings; a year without one has neither a Steuerberatung nor an early order.
	``fiscal_year_ends`` are the last days of the Fiscal Years of the company; a year in which none ends closes on
	31 December, since Steuerbote takes the Wirtschaftsjahr to be the calendar year. ``size_history`` holds the size
	class the settings applied to each Abschlussstichtag. ``founded_on`` is the day the company was founded; it sets
	the first year, if it is later than 2026, and the Eröffnungsbilanz of that year. ``since`` is the day the settings
	were made: an overdue deadline before it without a document is left out, as for the VAT Return Settings.
	"""

	years: tuple[YearSettings, ...] = ()
	fiscal_year_ends: tuple[date, ...] = ()
	size_history: tuple[SizeRecord, ...] = ()
	founded_on: date | None = None
	since: date | None = None

	def __post_init__(self) -> None:
		for name in ("years", "fiscal_year_ends", "size_history"):
			object.__setattr__(self, name, tuple(getattr(self, name)))

	@property
	def first_year(self) -> int:
		return max(FIRST_YEAR, self.founded_on.year) if self.founded_on else FIRST_YEAR

	def year(self, year: int) -> AnnualYear:
		"""The year as its deadlines read it."""
		settings = year_settings(self.years, year) or YearSettings(year)
		closing = max(
			(day for day in self.fiscal_year_ends if day.year == year),
			default=date(year, DECEMBER, LAST_OF_DECEMBER),
		)
		applied = size_class_on(self.size_history, closing)
		requests = [day for day in settings.early_requests.values() if day is not None]
		return AnnualYear(
			year,
			closing,
			advisor_prepares=settings.advisor_prepares,
			kleinunternehmer=settings.kleinunternehmer,
			early_request=min(requests, default=None),
			size_class=None if applied is None else SizeClass[applied.name],
			exempt_264_3=settings.exempt_264_3,
			founding=year >= FIRST_YEAR and self.founded_on is not None and self.founded_on.year == year,
		)


def year_obligations(year: AnnualYear, holidays: Collection[date] = ()) -> list[Obligation]:
	"""The annual filings the year owes, in the order of KINDS, each with the day it is due and its notes."""
	label = str(year.year)
	due = filing_deadline(year.year, year.advisor_prepares, year.early_request, holidays)
	notes = (Note.EARLY_REQUEST,) if year.early_request else (Note.ADVISOR,) if year.advisor_prepares else ()
	erklaerungen = (Kind.KOERPERSCHAFTSTEUERERKLAERUNG, Kind.GEWERBESTEUERERKLAERUNG)
	if not year.kleinunternehmer:
		erklaerungen = (Kind.UMSATZSTEUERERKLAERUNG, *erklaerungen)
	owed = [Obligation(kind, year.year, label, due, notes=notes) for kind in erklaerungen]
	owed.append(Obligation(Kind.E_BILANZ, year.year, label, due, notes=(Note.WITH_KST, *notes)))
	if year.founding:
		opening = OpeningBalance(year.year)
		owed.append(
			Obligation(Kind.E_BILANZ, opening, opening.label, due, notes=(Note.OPENING_BALANCE, *notes))
		)
	adoption = disclosure.adoption_deadline(year.fiscal_year_end, year.size_class)
	owed.append(Obligation(Kind.FESTSTELLUNG, year.year, label, adoption.due, notes=_notes_of(adoption)))
	if not year.exempt_264_3:
		transmission = disclosure.disclosure_deadline(year.fiscal_year_end)
		owed.append(
			Obligation(Kind.OFFENLEGUNG, year.year, label, transmission.due, notes=_notes_of(transmission))
		)
	return owed


def annual_obligations(rules: AnnualRules, until: date, holidays: Collection[date] = ()) -> list[Obligation]:
	"""Every annual filing the rules owe that is due on or before ``until``, year by year from the first year on."""
	return [
		owed
		for year in range(rules.first_year, until.year + 1)
		for owed in year_obligations(rules.year(year), holidays)
		if owed.due <= until
	]


def annual_due(
	rules: AnnualRules,
	kind: Kind,
	year: int,
	holidays: Collection[date] = (),
	*,
	opening_balance: bool = False,
) -> date | None:
	"""The day the annual filing of ``kind`` for ``year`` is due, as the overview lists it, or None where the year owes
	none: the Fälligkeitsdatum of an annual document. ``opening_balance`` asks for the Eröffnungsbilanz of the
	E-Bilanz."""
	if year < rules.first_year:
		return None
	period = OpeningBalance(year) if opening_balance else year
	return next(
		(
			owed.due
			for owed in year_obligations(rules.year(year), holidays)
			if (owed.kind, owed.period) == (kind, period)
		),
		None,
	)


def _notes_of(deadline: disclosure.Deadline) -> tuple[Note, ...]:
	return tuple(
		note
		for note, applies in (
			(Note.ASSUMED_CLASS, deadline.assumed_class),
			(Note.ON_WEEKEND, deadline.on_weekend),
		)
		if applies
	)
