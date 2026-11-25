"""The Vorauszahlungssoll of line 125, the Abschlusszahlung of Kz 820 and the day it is due.

Line 125 (E3011301), „Vorauszahlungssoll 2026 (einschließlich Sondervorauszahlung)“, is mandatory (rule 30915). The
Anleitung says: „Vorauszahlungssoll ist die Summe der angemeldeten bzw. festgesetzten Umsatzsteuer-Vorauszahlungen/
Überschüsse aus dem Voranmeldungsverfahren einschließlich der Sondervorauszahlung für die Dauerfristverlängerung. Ob
die Vorauszahlungen bereits entrichtet sind oder ob das Finanzamt einen Überschuss bereits ausgezahlt hat, ist für das
Vorauszahlungssoll ohne Bedeutung.“ (USt 2 E 2026, Zeilen 124 bis 126)

So the Soll is the sum of Kz 83 of the latest filed Voranmeldung of each Voranmeldungszeitraum of the year, plus the
Sondervorauszahlung of the year from the settings. The Sondervorauszahlung is paid apart from the Voranmeldungen, and
the last Voranmeldung of the year deducts it in Kz 39 (§ 48 Absatz 4 UStDV), so the Soll equals the sum of Kz 83 and
Kz 39 when that Voranmeldung credited it; a hint names a difference. Whether the amounts were paid does not matter,
but a hint names payments of the ledger that differ from the Soll.

A period the settings require without a filed Voranmeldung blocks the return: its Kz 83 is missing from the Soll. The
company may waive it with a reason, for a Voranmeldung filed outside Steuerbote say, whose amount then comes with an
override.

„In den Fällen, in denen bereits eine Festsetzung der Umsatzsteuer für den Besteuerungszeitraum erfolgt ist, tragen
Sie bitte die bisher festgesetzte Umsatzsteuer als Vorauszahlungssoll ein.“ (USt 2 E 2026, Zeilen 124 bis 126) A
filed annual return is a Steueranmeldung, which stands for a Festsetzung unter Vorbehalt der Nachprüfung (§ 168
Satz 1 AO), so a corrected return (Kz 110) takes the Kz 816 of the return it corrects. A Festsetzung that differs, a
Bescheid or an estimate, is an override with its reason.

Kz 820 is Kz 816 less the Soll (rule 30638): „Noch an die Finanzkasse zu entrichten - Abschlusszahlung -
Erstattungsanspruch“. The Abschlusszahlung „ist einen Monat nach dem Eingang der Steueranmeldung fällig“ (§ 18
Absatz 4 Satz 1 UStG).
"""

import calendar
from collections.abc import Collection, Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from steuerbote.ustjahr import text
from steuerbote.ustjahr.form import Finding, Severity
from steuerbote.ustva.calculation import require_cents
from steuerbote.ustva.period import Period, next_working_day
from steuerbote.ustva.rounding import ZERO, to_cents

DECEMBER = 12

OTHER_YEAR = "{0} is no Voranmeldungszeitraum of {1}."
PERIOD_TWICE = "{0} is filed twice; give the latest filing of each Voranmeldungszeitraum."
WITHOUT_REASON = "{0} needs a reason."
MISSING_PERIOD = "No filed Voranmeldung covers {0}: file it, or waive it with a reason."
SONDERVORAUSZAHLUNG = (
	"The Voranmeldungen credited {0} euros of Sondervorauszahlung in Kz 39, the settings name {1} euros for {2}. "
	"The last Voranmeldung of the year deducts it (§ 48 Absatz 4 UStDV); the Vorauszahlungssoll counts the "
	"Sondervorauszahlung of the settings."
)
OVERRIDDEN = "The Vorauszahlungssoll of {0} euros replaces the {1} euros of the Voranmeldungen: {2}"
PAYMENTS = (
	"The ledger shows {0} euros paid to the Finanzamt for the Voranmeldungen of {1}, the Vorauszahlungssoll is {2} "
	"euros. Whether they were paid does not matter for the Soll; a difference may be a payment still open."
)
MESSAGES = (
	OTHER_YEAR,
	PERIOD_TWICE,
	WITHOUT_REASON,
	MISSING_PERIOD,
	SONDERVORAUSZAHLUNG,
	OVERRIDDEN,
	PAYMENTS,
)
SOLL = "Vorauszahlungssoll"


class SollError(ValueError):
	"""The input of the Vorauszahlungssoll is broken; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


class SollSource(Enum):
	"""Where line 125 comes from."""

	VORANMELDUNGEN = "voranmeldungen"
	PREVIOUS_RETURN = "previous return"
	OVERRIDE = "override"


@dataclass(frozen=True, slots=True)
class FiledKennzahl:
	"""A Kennzahl of a filed Voranmeldung, as its VAT Return keeps it: the exact amount of the ledger when it was
	filed, the amount of the form, and the amount filed after the corrections of the company."""

	amount: Decimal
	reported: Decimal
	final: Decimal

	def __post_init__(self) -> None:
		for amount in (self.amount, self.reported, self.final):
			require_cents(amount)


@dataclass(frozen=True, slots=True)
class Filed:
	"""A Voranmeldung of the year as filed: its Voranmeldungszeitraum, the name of its VAT Return, its Kz 83 and the
	Sondervorauszahlung its Kz 39 credited, as steuerbote/dauerfrist_sources.py reads them. ``lines`` are its
	Kennzahlen by number, for the reconciliation."""

	period: Period
	name: str
	kz83: Decimal
	kz39: Decimal = ZERO
	lines: ReadOnlyMapping[str, FiledKennzahl] = MappingProxyType({})

	def __post_init__(self) -> None:
		require_cents(self.kz83)
		require_cents(self.kz39)
		object.__setattr__(self, "lines", MappingProxyType(dict(self.lines)))


@dataclass(frozen=True, slots=True)
class Override:
	"""A Vorauszahlungssoll the Finanzamt set, with the reason, such as its Bescheid."""

	amount: Decimal
	reason: str

	def __post_init__(self) -> None:
		require_cents(self.amount)
		object.__setattr__(self, "reason", _reason(self.reason, SOLL))


@dataclass(frozen=True, slots=True)
class Soll:
	"""Line 125 and what it is made of.

	``voranmeldungen`` is the sum of Kz 83 of the filed Voranmeldungen, ``credited`` the sum of their Kz 39.
	``missing`` names the periods the settings require that no Voranmeldung covers and the company did not waive;
	``waived`` the waived ones with their reasons.
	"""

	amount: Decimal
	source: SollSource
	voranmeldungen: Decimal
	sondervorauszahlung: Decimal
	credited: Decimal
	filed: tuple[Filed, ...]
	missing: tuple[Period, ...]
	waived: tuple[tuple[Period, str], ...]
	override: Override | None
	findings: tuple[Finding, ...]

	@property
	def computed(self) -> Decimal:
		"""The Soll from the Voranmeldungen and the Sondervorauszahlung, before a correction or an override."""
		return self.voranmeldungen + self.sondervorauszahlung

	@property
	def ready(self) -> bool:
		"""Every period the settings require is filed or waived."""
		return not self.missing


def vorauszahlungssoll(
	year: int,
	filed: Iterable[Filed],
	due: Iterable[Period],
	sondervorauszahlung: Decimal = ZERO,
	waived: ReadOnlyMapping[Period, str] | None = None,
	previous_kz816: Decimal | None = None,
	override: Override | None = None,
	paid: Decimal | None = None,
) -> Soll:
	"""Line 125 of the annual return of ``year``.

	``filed`` is the latest filed Voranmeldung of each period, ``due`` the Voranmeldungszeiträume the settings require
	for the year, and ``sondervorauszahlung`` that of the year from the settings. ``waived`` gives the reason for each
	due period the company files without a Voranmeldung. ``previous_kz816`` is the Kz 816 of the return a corrected
	return corrects, ``override`` the Soll the Finanzamt set, and ``paid`` what the ledger shows as paid on the
	Voranmeldungen of the year, for a hint.
	"""
	require_cents(sondervorauszahlung)
	returns = _filed(year, filed)
	reasons = {period: _reason(reason, period.label) for period, reason in (waived or {}).items()}
	due_periods = tuple(dict.fromkeys(_of_year(year, period) for period in due))
	covered = {entry.period for entry in returns}
	missing = tuple(period for period in due_periods if period not in covered and period not in reasons)
	voranmeldungen = to_cents(sum((entry.kz83 for entry in returns), ZERO))
	credited = to_cents(sum((entry.kz39 for entry in returns), ZERO))
	computed = voranmeldungen + sondervorauszahlung
	if override is not None:
		amount, source = override.amount, SollSource.OVERRIDE
	elif previous_kz816 is not None:
		amount, source = require_cents(previous_kz816), SollSource.PREVIOUS_RETURN
	else:
		amount, source = computed, SollSource.VORANMELDUNGEN
	findings = [
		Finding("ZEITRAUM-FEHLT", Severity.ERROR, MISSING_PERIOD, (period.label,)) for period in missing
	]
	if credited != sondervorauszahlung:
		values = (_euros(credited), _euros(sondervorauszahlung), year)
		findings.append(Finding("SONDERVORAUSZAHLUNG-KZ39", Severity.HINT, SONDERVORAUSZAHLUNG, values))
	if override is not None:
		values = (_euros(override.amount), _euros(computed), override.reason)
		findings.append(Finding("SOLL-UEBERSCHRIEBEN", Severity.HINT, OVERRIDDEN, values))
	if paid is not None and require_cents(paid) != amount:
		findings.append(Finding("ZAHLUNGEN", Severity.HINT, PAYMENTS, (_euros(paid), year, _euros(amount))))
	return Soll(
		amount=amount,
		source=source,
		voranmeldungen=voranmeldungen,
		sondervorauszahlung=sondervorauszahlung,
		credited=credited,
		filed=returns,
		missing=missing,
		waived=tuple(
			(period, reasons[period]) for period in sorted(reasons, key=lambda period: period.start)
		),
		override=override,
		findings=tuple(findings),
	)


def abschlusszahlung(kz816: Decimal, soll: Decimal) -> Decimal:
	"""Kz 820: Kz 816 less the Vorauszahlungssoll, positive to pay and negative for a refund (rule 30638)."""
	return to_cents(require_cents(kz816) - require_cents(soll))


def payment_due(received: date, holidays: Collection[date] = ()) -> date:
	"""The day the Abschlusszahlung is due: one month after the return arrived (§ 18 Absatz 4 Satz 1 UStG).

	The month ends on the day of the same number, or on the last day of a shorter month (§ 188 Absatz 2 and 3 BGB,
	§ 108 Absatz 1 AO), and moves off a Saturday, a Sunday or one of the ``holidays`` (§ 108 Absatz 3 AO, which
	applies to a day of payment: „Fälligkeitstermine geben das Ende einer Frist an“, AEAO zu § 108).
	"""
	year, month = (
		(received.year + 1, 1) if received.month == DECEMBER else (received.year, received.month + 1)
	)
	day = min(received.day, calendar.monthrange(year, month)[1])
	return next_working_day(date(year, month, day), holidays)


def _filed(year: int, filed: Iterable[Filed]) -> tuple[Filed, ...]:
	by_period: dict[Period, Filed] = {}
	for entry in filed:
		_of_year(year, entry.period)
		if entry.period in by_period:
			raise SollError(PERIOD_TWICE, entry.period.label)
		by_period[entry.period] = entry
	return tuple(sorted(by_period.values(), key=lambda entry: entry.period.start))


def _of_year(year: int, period: Period) -> Period:
	if period.year != year:
		raise SollError(OTHER_YEAR, period.label, year)
	return period


def _reason(reason: str, subject: str) -> str:
	text = " ".join(reason.split()) if isinstance(reason, str) else ""
	if not text:
		raise SollError(WITHOUT_REASON, subject)
	return text


def _euros(amount: Decimal) -> str:
	return text.euros(amount)
