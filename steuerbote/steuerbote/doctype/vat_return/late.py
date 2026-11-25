"""What a VAT Return says about bookings and amounts of filed periods that changed after the filing.

A return being prepared lists in its table „Nach der Abgabe geändert“ (late_changes) each booking that was made
after the filing of an earlier period of the same or the previous year and either belongs to that period and needs
its corrected return (Kz 10), or was moved into this period (steuerbote.ustva.assignment), and each Kennzahl of a
filed period whose ledger amount differs today from the amount its return took. A filed return says the same of its
own period when it is opened. The rows are recorded with the return, so what it decided stays traceable.

Messages are English templates with positional placeholders, which the Frappe layer translates before formatting
them. This module is pure Python and never imports Frappe.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from steuerbote.ustva.assignment import Change, Placement
from steuerbote.ustva.period import Period

BOOKED_AFTER_FILING = "Booked after Filing"
CHANGED_SINCE_FILING = "Changed since Filing"

MOVED_HERE = "Belongs to {0} and was booked after {0} was filed: reported in this period."
MOVED_TO = "Booked after the filing: reported in {0}."
NEEDS_CORRECTION = (
	"Belongs to {0} and was booked after {0} was filed: make a corrected return (Kz 10) of {0}."
)
CHANGED_AMOUNT = "Kz {0}: filed {1}, now {2}."
MESSAGES = (BOOKED_AFTER_FILING, CHANGED_SINCE_FILING, MOVED_HERE, MOVED_TO, NEEDS_CORRECTION, CHANGED_AMOUNT)


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
		return self.template in (NEEDS_CORRECTION, CHANGED_AMOUNT)


def _voucher(placement: Placement, period: Period, template: str, values: tuple[str, ...]) -> Row:
	voucher_type, _, voucher_no = placement.booking.voucher.partition(":")
	return Row(
		period, BOOKED_AFTER_FILING, template, values, voucher_type, voucher_no, placement.booking.booked_at
	)


def current_rows(placements: Iterable[Placement], current: Period) -> list[Row]:
	"""The late bookings a return of ``current`` reports itself or names for a corrected return of an earlier
	period."""
	rows = []
	for placement in placements:
		tax_period = placement.tax_period
		if tax_period is None:
			continue
		if placement.moved and placement.period == current:
			rows.append(_voucher(placement, tax_period, MOVED_HERE, (tax_period.label,)))
		elif placement.needs_correction and tax_period.start < current.start:
			rows.append(_voucher(placement, tax_period, NEEDS_CORRECTION, (tax_period.label,)))
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
