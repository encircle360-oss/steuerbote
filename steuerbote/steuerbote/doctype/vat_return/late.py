"""What a VAT Return says about bookings and amounts of filed periods that changed after the filing.

A return being prepared lists in its table „Nach der Abgabe geändert“ (late_changes) each booking that was made
after the filing of an earlier period of the same or the previous year, and each cancellation made then of a voucher of
that period, that either belongs to that period and needs its corrected return (Kz 10), or was moved into this period
(steuerbote.ustva.assignment), and each Kennzahl of a
filed period whose ledger amount differs today from the amount its return took. A filed return says the same of its
own period when it is opened. The rows are recorded with the return, so what it decided stays traceable.

Messages are English templates with positional placeholders, which the Frappe layer translates before formatting
them. This module is pure Python and never imports Frappe.
"""

from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from steuerbote.ustva.assignment import Change, Placement
from steuerbote.ustva.period import Period

BOOKED_AFTER_FILING = "Booked after Filing"
CANCELLED_AFTER_FILING = "Cancelled after Filing"
CHANGED_SINCE_FILING = "Changed since Filing"

MOVED_HERE = "Belongs to {0} and was booked after {0} was filed: reported in this period."
MOVED_TO = "Booked after the filing: reported in {0}."
NEEDS_CORRECTION = (
	"Belongs to {0} and was booked after {0} was filed: make a corrected return (Kz 10) of {0}."
)
CHANGED_AMOUNT = "Kz {0}: filed {1}, now {2}."
REPORTED_BY_CORRECTION = (
	"Belongs to {0} and was booked after {0} was filed: reported by this corrected return."
)
OUTSIDE_MOVED_HERE = "Belongs to {0}, which was filed outside Steuerbote before the start of its books: reported in this period."
OUTSIDE_NEEDS_CORRECTION = "Belongs to {0}, which was filed outside Steuerbote before the start of its books: its corrected return (Kz 10) goes where {0} was filed, or Documents for a Filed Period set to Current Period reports it in the period open when it was booked."
MESSAGES = (
	BOOKED_AFTER_FILING,
	CANCELLED_AFTER_FILING,
	CHANGED_SINCE_FILING,
	MOVED_HERE,
	MOVED_TO,
	NEEDS_CORRECTION,
	CHANGED_AMOUNT,
	REPORTED_BY_CORRECTION,
	OUTSIDE_MOVED_HERE,
	OUTSIDE_NEEDS_CORRECTION,
)


@dataclass(frozen=True, slots=True)
class Row:
	"""A row of the table: the filed period it concerns, what kind of change, the voucher, when it was booked, and
	the message as template and values."""

	period: Period
	kind: str
	template: str
	values: tuple[str, ...]
	voucher_type: str = ""
	voucher_no: str = ""
	booked_at: datetime | None = None

	@property
	def needs_correction(self) -> bool:
		return self.template in (NEEDS_CORRECTION, CHANGED_AMOUNT, OUTSIDE_NEEDS_CORRECTION)


def _voucher(placement: Placement, period: Period, template: str, values: tuple[str, ...]) -> Row:
	voucher_type, _, voucher_no = placement.booking.voucher.partition(":")
	kind = CANCELLED_AFTER_FILING if placement.booking.cancellation else BOOKED_AFTER_FILING
	return Row(period, kind, template, values, voucher_type, voucher_no, placement.booking.booked_at)


def current_rows(
	placements: Iterable[Placement], current: Period, outside: Collection[Period] = frozenset()
) -> list[Row]:
	"""The late bookings a return of ``current`` reports itself or names for a corrected return of an earlier
	period; a period of ``outside`` was filed outside Steuerbote, which cannot correct it."""
	rows = []
	for placement in placements:
		tax_period = placement.tax_period
		if tax_period is None:
			continue
		elsewhere = tax_period in outside
		if placement.moved and placement.period == current:
			template = OUTSIDE_MOVED_HERE if elsewhere else MOVED_HERE
			rows.append(_voucher(placement, tax_period, template, (tax_period.label,)))
		elif placement.needs_correction and tax_period.start < current.start:
			template = OUTSIDE_NEEDS_CORRECTION if elsewhere else NEEDS_CORRECTION
			rows.append(_voucher(placement, tax_period, template, (tax_period.label,)))
	return rows


def filed_rows(placements: Iterable[Placement], period: Period) -> list[Row]:
	"""The late bookings of ``period`` as its filed return names them: moved to another period, or needing the
	corrected return."""
	rows = []
	for placement in placements:
		if placement.tax_period != period or not placement.late:
			continue
		if placement.moved:
			rows.append(_voucher(placement, period, MOVED_TO, ((placement.period or period).label,)))
		else:
			rows.append(_voucher(placement, period, NEEDS_CORRECTION, (period.label,)))
	return rows


def correction_rows(placements: Iterable[Placement], period: Period) -> list[Row]:
	"""The late bookings of ``period`` that its corrected return reports: those that stay in the period."""
	return [
		_voucher(placement, period, REPORTED_BY_CORRECTION, (period.label,))
		for placement in placements
		if placement.tax_period == period and placement.needs_correction
	]


def change_rows(period: Period, changes: Iterable[Change], money: Callable[[Decimal], str]) -> list[Row]:
	"""A row per Kennzahl of the filed period whose ledger amount changed, the amounts as ``money`` writes them."""
	return [
		Row(
			period,
			CHANGED_SINCE_FILING,
			CHANGED_AMOUNT,
			(change.kennzahl, money(change.filed), money(change.now)),
		)
		for change in changes
	]
