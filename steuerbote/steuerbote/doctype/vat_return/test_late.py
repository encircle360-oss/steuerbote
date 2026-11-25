from datetime import date, datetime
from decimal import Decimal
from unittest import TestCase

from steuerbote.steuerbote.doctype.vat_return.late import (
	BOOKED_AFTER_FILING,
	CHANGED_AMOUNT,
	CHANGED_SINCE_FILING,
	MOVED_HERE,
	MOVED_TO,
	NEEDS_CORRECTION,
	Row,
	change_rows,
	current_rows,
	filed_rows,
)
from steuerbote.ustva.assignment import Booking, Change, Placement
from steuerbote.ustva.period import Period

JULY = Period.month(2026, 7)
AUGUST = Period.month(2026, 8)
SEPTEMBER = Period.month(2026, 9)
BOOKED = datetime(2026, 9, 5, 9, 30)


def placement(
	tax_period: Period | None, period: Period | None, late: bool, voucher: str = "Sales Invoice:SINV-1"
):
	booking = Booking("8400", voucher, date(2026, 9, 5), BOOKED, credit=Decimal("100.00"))
	return Placement(booking, date(2026, 7, 31), tax_period, period, late)


class CurrentRowsTest(TestCase):
	def test_a_booking_moved_into_the_period_is_reported_there(self):
		self.assertEqual(
			current_rows([placement(JULY, AUGUST, late=True)], AUGUST),
			[Row(JULY, BOOKED_AFTER_FILING, MOVED_HERE, ("Juli 2026",), "Sales Invoice", "SINV-1", BOOKED)],
		)

	def test_a_booking_for_an_earlier_filed_period_asks_for_its_corrected_return(self):
		(row,) = current_rows([placement(JULY, JULY, late=True)], SEPTEMBER)
		self.assertEqual((row.period, row.template, row.values), (JULY, NEEDS_CORRECTION, ("Juli 2026",)))
		self.assertTrue(row.needs_correction)

	def test_leaves_out_what_another_period_reports_and_what_is_not_late(self):
		self.assertEqual(
			current_rows(
				[
					placement(JULY, AUGUST, late=True),
					placement(JULY, JULY, late=False),
					placement(None, None, late=False),
					placement(SEPTEMBER, SEPTEMBER, late=True),
				],
				SEPTEMBER,
			),
			[],
		)


class FiledRowsTest(TestCase):
	def test_names_where_each_late_booking_of_the_period_went(self):
		rows = filed_rows(
			[
				placement(JULY, AUGUST, late=True, voucher="Sales Invoice:SINV-1"),
				placement(JULY, JULY, late=True, voucher="Journal Entry:JV-2"),
				placement(AUGUST, AUGUST, late=True, voucher="Sales Invoice:SINV-3"),
				placement(JULY, JULY, late=False, voucher="Sales Invoice:SINV-4"),
			],
			JULY,
		)
		self.assertEqual(
			[(row.voucher_no, row.template, row.values) for row in rows],
			[("SINV-1", MOVED_TO, ("August 2026",)), ("JV-2", NEEDS_CORRECTION, ("Juli 2026",))],
		)
		self.assertFalse(rows[0].needs_correction)


class ChangeRowsTest(TestCase):
	def test_names_the_amount_filed_and_the_amount_now(self):
		(row,) = change_rows(
			JULY, [Change("81", Decimal("1000.00"), Decimal("1500.00"))], lambda amount: f"{amount} €"
		)
		self.assertEqual(
			row, Row(JULY, CHANGED_SINCE_FILING, CHANGED_AMOUNT, ("81", "1000.00 €", "1500.00 €"))
		)
		self.assertTrue(row.needs_correction)
