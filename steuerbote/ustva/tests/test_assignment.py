from datetime import date, datetime
from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva.assignment import (
	DEFAULT_BASIS,
	DEFAULT_TREATMENT,
	INVOICE_DATE_KENNZAHLEN,
	Assignment,
	Booking,
	Change,
	Filing,
	LateTreatment,
	PeriodBasis,
	changes,
	filed_outside,
	invoice_date_accounts,
	periods_with_the_books,
	service_date,
)
from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.defaults import SKR03
from steuerbote.ustva.mapping import AccountRule, Mapping, Side
from steuerbote.ustva.period import Period

JULY = Period.month(2026, 7)
AUGUST = Period.month(2026, 8)
SEPTEMBER = Period.month(2026, 9)
OCTOBER = Period.month(2026, 10)
MONTHS_2026 = tuple(Period.month(2026, month) for month in range(1, 13))


def at(day: int, month: int, hour: int = 12) -> datetime:
	return datetime(2026, month, day, hour)


THIRD_OF_AUGUST = at(3, 8)


def booking(
	voucher: str = "Sales Invoice:SINV-0001",
	posting: date = date(2026, 8, 3),
	booked: datetime = THIRD_OF_AUGUST,
	service: date | None = None,
	account: str = "8400",
	credit: str = "1000.00",
) -> Booking:
	return Booking(account, voucher, posting, booked, credit=Decimal(credit), service_date=service)


def filed(period: Period, first: datetime, latest: datetime | None = None) -> Filing:
	return Filing(period, first, latest or first)


class ServiceDateTest(TestCase):
	"""Which date of a Sales Invoice names the time of its supply."""

	def test_the_end_of_the_billing_period_comes_first(self):
		self.assertEqual(
			service_date(
				to_date=date(2026, 7, 31),
				from_date=date(2026, 7, 1),
				delivery_date=date(2026, 6, 30),
				is_return=False,
				is_debit_note=False,
			),
			date(2026, 7, 31),
		)

	def test_a_period_with_a_start_only_takes_the_start(self):
		self.assertEqual(
			service_date(
				to_date=None,
				from_date=date(2026, 7, 1),
				delivery_date=None,
				is_return=False,
				is_debit_note=False,
			),
			date(2026, 7, 1),
		)

	def test_without_a_billing_period_the_latest_delivery_note_dates_the_supply(self):
		self.assertEqual(
			service_date(
				to_date=None,
				from_date=None,
				delivery_date=date(2026, 6, 30),
				is_return=False,
				is_debit_note=False,
			),
			date(2026, 6, 30),
		)

	def test_an_invoice_without_any_of_them_has_no_service_date(self):
		self.assertIsNone(
			service_date(
				to_date=None, from_date=None, delivery_date=None, is_return=False, is_debit_note=False
			)
		)

	def test_a_credit_note_or_a_debit_note_changes_the_base_when_it_is_issued(self):
		for is_return, is_debit_note in ((True, False), (False, True)):
			with self.subTest(is_return=is_return, is_debit_note=is_debit_note):
				self.assertIsNone(
					service_date(
						to_date=date(2026, 7, 31),
						from_date=date(2026, 7, 1),
						delivery_date=date(2026, 7, 15),
						is_return=is_return,
						is_debit_note=is_debit_note,
					)
				)


class BookingTest(TestCase):
	def test_is_the_ledger_line_of_its_voucher(self):
		self.assertEqual(
			booking().line(),
			LedgerLine("8400", Decimal("0.00"), Decimal("1000.00"), "Sales Invoice:SINV-0001"),
		)

	def test_refuses_what_a_ledger_line_refuses(self):
		with self.assertRaises(ValueError):
			booking(account=" 8400")
		with self.assertRaises(ValueError):
			booking(credit="0.001")

	def test_refuses_a_booking_without_its_voucher(self):
		with self.assertRaisesRegex(ValueError, "voucher"):
			booking(voucher="")


class FilingTest(TestCase):
	def test_the_latest_filing_does_not_precede_the_first(self):
		with self.assertRaisesRegex(ValueError, "first"):
			Filing(JULY, at(10, 8), at(9, 8))


class InvoiceDateAccountsTest(TestCase):
	def test_are_the_accounts_of_kz_41_42_and_21(self):
		self.assertEqual(INVOICE_DATE_KENNZAHLEN, frozenset({"41", "42", "21"}))
		accounts = invoice_date_accounts(SKR03)
		expected = {rule.account_number for rule in SKR03.rules if rule.kennzahl in INVOICE_DATE_KENNZAHLEN}
		self.assertEqual(accounts, expected)
		self.assertIn("8125", accounts)
		self.assertIn("8336", accounts)
		self.assertNotIn("8400", accounts)

	def test_an_own_mapping_keeps_the_invoice_date_on_its_accounts_of_these_kennzahlen(self):
		mapping = Mapping(
			"Eigener Kontenrahmen",
			[AccountRule("8400", "81", Side.CREDIT), AccountRule("8501", "21", Side.CREDIT)],
		)
		self.assertEqual(invoice_date_accounts(mapping), frozenset({"8501"}))


class TaxDateTest(TestCase):
	def test_by_service_date_a_sales_invoice_counts_in_the_period_of_its_supply(self):
		assignment = Assignment(PeriodBasis.SERVICE_DATE, LateTreatment.CORRECTION, MONTHS_2026)
		self.assertEqual(assignment.tax_date(booking(service=date(2026, 7, 31))), date(2026, 7, 31))

	def test_a_supply_after_the_invoice_counts_when_it_is_performed(self):
		assignment = Assignment(PeriodBasis.SERVICE_DATE, LateTreatment.CORRECTION, MONTHS_2026)
		self.assertEqual(assignment.tax_date(booking(service=date(2026, 9, 30))), date(2026, 9, 30))

	def test_without_a_service_date_the_posting_date_counts(self):
		assignment = Assignment(PeriodBasis.SERVICE_DATE, LateTreatment.CORRECTION, MONTHS_2026)
		self.assertEqual(assignment.tax_date(booking(voucher="Journal Entry:JV-1")), date(2026, 8, 3))

	def test_by_posting_date_the_service_date_counts_for_nothing(self):
		assignment = Assignment(PeriodBasis.POSTING_DATE, LateTreatment.CORRECTION, MONTHS_2026)
		self.assertEqual(assignment.tax_date(booking(service=date(2026, 7, 31))), date(2026, 8, 3))

	def test_the_accounts_of_kz_41_42_and_21_keep_the_posting_date(self):
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE,
			LateTreatment.CORRECTION,
			MONTHS_2026,
			invoice_date_accounts=invoice_date_accounts(SKR03),
		)
		self.assertEqual(
			assignment.tax_date(booking(account="8125", service=date(2026, 7, 31))), date(2026, 8, 3)
		)
		self.assertEqual(
			assignment.tax_date(booking(account="8400", service=date(2026, 7, 31))), date(2026, 7, 31)
		)

	def test_the_defaults_are_the_legal_rule_and_the_corrected_return(self):
		self.assertIs(DEFAULT_BASIS, PeriodBasis.SERVICE_DATE)
		self.assertIs(DEFAULT_TREATMENT, LateTreatment.CORRECTION)


class PlacementTest(TestCase):
	def test_a_booking_in_an_open_period_is_reported_there(self):
		placement = Assignment(PeriodBasis.SERVICE_DATE, LateTreatment.CORRECTION, MONTHS_2026).place(
			booking(service=date(2026, 7, 31))
		)
		self.assertEqual((placement.tax_period, placement.period, placement.late), (JULY, JULY, False))
		self.assertFalse(placement.moved)
		self.assertFalse(placement.needs_correction)
		self.assertEqual(placement.date, date(2026, 7, 31))

	def test_a_booking_before_the_filing_is_not_late(self):
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE, LateTreatment.CORRECTION, MONTHS_2026, [filed(JULY, at(10, 8))]
		)
		placement = assignment.place(booking(service=date(2026, 7, 31), booked=at(3, 8)))
		self.assertFalse(placement.late)

	def test_with_the_corrected_return_a_late_booking_stays_in_the_period_of_its_supply(self):
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE, LateTreatment.CORRECTION, MONTHS_2026, [filed(JULY, at(10, 8))]
		)
		placement = assignment.place(
			booking(posting=date(2026, 9, 20), booked=at(20, 9), service=date(2026, 7, 31))
		)
		self.assertEqual((placement.tax_period, placement.period), (JULY, JULY))
		self.assertTrue(placement.late)
		self.assertTrue(placement.needs_correction)

	def test_a_corrected_return_filed_after_the_booking_holds_it(self):
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE,
			LateTreatment.CORRECTION,
			MONTHS_2026,
			[filed(JULY, at(10, 8), at(25, 9))],
		)
		placement = assignment.place(
			booking(posting=date(2026, 9, 20), booked=at(20, 9), service=date(2026, 7, 31))
		)
		self.assertFalse(placement.late)

	def test_in_the_current_period_a_late_booking_goes_to_the_period_being_prepared_when_it_was_booked(self):
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE,
			LateTreatment.CURRENT_PERIOD,
			MONTHS_2026,
			[filed(JULY, at(10, 8)), filed(AUGUST, at(10, 9))],
		)
		placement = assignment.place(
			booking(posting=date(2026, 9, 5), booked=at(5, 9), service=date(2026, 7, 31))
		)
		self.assertEqual((placement.tax_period, placement.period), (JULY, AUGUST))
		self.assertTrue(placement.late)
		self.assertTrue(placement.moved)
		self.assertFalse(placement.needs_correction)
		self.assertEqual(placement.date, AUGUST.start)
		later = assignment.place(
			booking(posting=date(2026, 9, 20), booked=at(20, 9), service=date(2026, 7, 31))
		)
		self.assertEqual(later.period, SEPTEMBER)

	def test_in_the_current_period_the_first_filing_decides_so_a_correction_does_not_take_the_booking_back(
		self,
	):
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE,
			LateTreatment.CURRENT_PERIOD,
			MONTHS_2026,
			[filed(JULY, at(10, 8), at(1, 10))],
		)
		placement = assignment.place(
			booking(posting=date(2026, 9, 20), booked=at(20, 9), service=date(2026, 7, 31))
		)
		self.assertEqual(placement.period, AUGUST)

	def test_a_booking_never_moves_into_the_next_year(self):
		december = Period.month(2026, 12)
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE,
			LateTreatment.CURRENT_PERIOD,
			(*MONTHS_2026, Period.month(2027, 1)),
			[filed(december, datetime(2027, 1, 10))],
		)
		placement = assignment.place(
			booking(posting=date(2027, 1, 20), booked=datetime(2027, 1, 20), service=date(2026, 12, 31))
		)
		self.assertEqual((placement.tax_period, placement.period), (december, december))
		self.assertTrue(placement.needs_correction)

	def test_follows_a_change_of_rhythm_in_the_year(self):
		periods = (Period.quarter(2026, 1), Period.quarter(2026, 2), Period.quarter(2026, 3), OCTOBER)
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE,
			LateTreatment.CURRENT_PERIOD,
			periods,
			[filed(Period.quarter(2026, 3), at(10, 10))],
		)
		placement = assignment.place(
			booking(posting=date(2026, 10, 20), booked=at(20, 10), service=date(2026, 8, 31))
		)
		self.assertEqual((placement.tax_period, placement.period), (Period.quarter(2026, 3), OCTOBER))

	def test_a_date_outside_the_periods_has_no_period_and_counts_by_its_date(self):
		assignment = Assignment(PeriodBasis.SERVICE_DATE, LateTreatment.CURRENT_PERIOD, (JULY,))
		placement = assignment.place(booking(posting=date(2026, 8, 3)))
		self.assertIsNone(placement.tax_period)
		self.assertIsNone(placement.period)
		self.assertFalse(placement.late)
		self.assertEqual(placement.date, date(2026, 8, 3))

	def test_refuses_periods_that_overlap_or_run_backwards(self):
		for periods in ((AUGUST, JULY), (Period.quarter(2026, 3), AUGUST)):
			with self.subTest(periods=periods), self.assertRaisesRegex(ValueError, "order"):
				Assignment(PeriodBasis.SERVICE_DATE, LateTreatment.CORRECTION, periods)


class LinesTest(TestCase):
	"""Every booking is reported in exactly one period: none twice, none lost."""

	def bookings(self) -> list[Booking]:
		return [
			booking("Sales Invoice:A", date(2026, 7, 20), at(20, 7), date(2026, 7, 15)),
			booking("Sales Invoice:B", date(2026, 8, 3), at(3, 8), date(2026, 7, 31)),
			booking("Sales Invoice:C", date(2026, 9, 5), at(5, 9), date(2026, 7, 31)),
			booking("Sales Invoice:D", date(2026, 9, 20), at(20, 9), date(2026, 8, 31)),
			booking("Journal Entry:E", date(2026, 8, 31), at(15, 9)),
			booking("Journal Entry:F", date(2026, 9, 30), at(30, 9), account="1776", credit="190.00"),
			booking("Sales Invoice:G", date(2026, 10, 2), at(2, 10), date(2026, 11, 30)),
		]

	def filings(self) -> list[Filing]:
		return [filed(JULY, at(10, 8)), filed(AUGUST, at(10, 9))]

	def test_each_booking_lands_in_exactly_one_period(self):
		for treatment in LateTreatment:
			for basis in PeriodBasis:
				with self.subTest(treatment=treatment, basis=basis):
					assignment = Assignment(basis, treatment, MONTHS_2026, self.filings())
					reported = [
						line for period in MONTHS_2026 for line in assignment.lines(self.bookings(), period)
					]
					self.assertCountEqual(reported, [item.line() for item in self.bookings()])

	def test_a_year_is_the_sum_of_its_periods(self):
		for treatment in LateTreatment:
			with self.subTest(treatment=treatment):
				assignment = Assignment(PeriodBasis.SERVICE_DATE, treatment, MONTHS_2026, self.filings())
				year = assignment.lines_between(self.bookings(), date(2026, 1, 1), date(2026, 12, 31))
				months = [
					line for period in MONTHS_2026 for line in assignment.lines(self.bookings(), period)
				]
				self.assertCountEqual(year, months)

	def test_with_the_corrected_return_the_periods_follow_the_service_dates(self):
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE, LateTreatment.CORRECTION, MONTHS_2026, self.filings()
		)
		vouchers = {
			period.index: [line.voucher for line in assignment.lines(self.bookings(), period)]
			for period in (JULY, AUGUST, SEPTEMBER, OCTOBER, Period.month(2026, 11))
		}
		self.assertEqual(
			vouchers,
			{
				7: ["Sales Invoice:A", "Sales Invoice:B", "Sales Invoice:C"],
				8: ["Sales Invoice:D", "Journal Entry:E"],
				9: ["Journal Entry:F"],
				10: [],
				11: ["Sales Invoice:G"],
			},
		)

	def test_in_the_current_period_the_late_bookings_follow_the_open_period(self):
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE, LateTreatment.CURRENT_PERIOD, MONTHS_2026, self.filings()
		)
		vouchers = {
			period.index: [line.voucher for line in assignment.lines(self.bookings(), period)]
			for period in (JULY, AUGUST, SEPTEMBER)
		}
		self.assertEqual(
			vouchers,
			{
				7: ["Sales Invoice:A", "Sales Invoice:B"],
				8: ["Sales Invoice:C"],
				9: ["Sales Invoice:D", "Journal Entry:E", "Journal Entry:F"],
			},
		)

	def test_by_posting_date_without_filings_the_lines_are_those_of_the_posting_dates(self):
		assignment = Assignment(PeriodBasis.POSTING_DATE, LateTreatment.CORRECTION, MONTHS_2026)
		for period in MONTHS_2026:
			with self.subTest(period=period):
				self.assertEqual(
					assignment.lines(self.bookings(), period),
					[item.line() for item in self.bookings() if period.contains(item.posting_date)],
				)

	def test_a_period_of_another_rhythm_takes_the_lines_of_its_days(self):
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE, LateTreatment.CORRECTION, MONTHS_2026, self.filings()
		)
		third = assignment.lines(self.bookings(), Period.quarter(2026, 3))
		self.assertCountEqual(
			[line.voucher for line in third],
			[
				"Sales Invoice:A",
				"Sales Invoice:B",
				"Sales Invoice:C",
				"Sales Invoice:D",
				"Journal Entry:E",
				"Journal Entry:F",
			],
		)


class LateTest(TestCase):
	def test_names_the_bookings_after_the_filing_of_their_period_in_the_order_of_their_booking(self):
		bookings = [
			booking("Sales Invoice:D", date(2026, 9, 20), at(20, 9), date(2026, 7, 31)),
			booking("Sales Invoice:C", date(2026, 9, 5), at(5, 9), date(2026, 7, 31)),
			booking("Sales Invoice:B", date(2026, 8, 3), at(3, 8), date(2026, 7, 31)),
		]
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE, LateTreatment.CORRECTION, MONTHS_2026, [filed(JULY, at(10, 8))]
		)
		self.assertEqual(
			[placement.booking.voucher for placement in assignment.late(bookings)],
			["Sales Invoice:C", "Sales Invoice:D"],
		)

	def test_names_a_voucher_once_with_all_its_accounts(self):
		bookings = [
			booking("Sales Invoice:C", date(2026, 9, 5), at(5, 9), date(2026, 7, 31)),
			booking(
				"Sales Invoice:C",
				date(2026, 9, 5),
				at(5, 9),
				date(2026, 7, 31),
				account="1776",
				credit="190.00",
			),
		]
		assignment = Assignment(
			PeriodBasis.SERVICE_DATE, LateTreatment.CORRECTION, MONTHS_2026, [filed(JULY, at(10, 8))]
		)
		(placement,) = assignment.late_vouchers(bookings)
		self.assertEqual(placement.booking.voucher, "Sales Invoice:C")


class ChangesTest(TestCase):
	def test_names_each_kennzahl_whose_amount_differs_from_the_filed_one(self):
		self.assertEqual(
			changes(
				{"81": Decimal("1000.00"), "66": Decimal("19.00")},
				{"81": Decimal("1500.00"), "66": Decimal("19.00"), "86": Decimal("100.00")},
			),
			(
				Change("81", Decimal("1000.00"), Decimal("1500.00")),
				Change("86", Decimal("0"), Decimal("100.00")),
			),
		)

	def test_a_kennzahl_that_is_gone_now_reads_zero(self):
		self.assertEqual(
			changes({"81": Decimal("1000.00")}, {}), (Change("81", Decimal("1000.00"), Decimal("0")),)
		)

	def test_leaves_out_kz_83_and_kz_39_which_follow_from_the_others_and_the_settings(self):
		self.assertEqual(changes({"83": Decimal(1), "39": Decimal(2)}, {"83": Decimal(3)}), ())

	def test_the_difference_is_the_amount_now_less_the_amount_filed(self):
		self.assertEqual(Change("81", Decimal("1000.00"), Decimal("1500.00")).difference, Decimal("500.00"))


class BeforeTheBooksTest(TestCase):
	"""Periods before the start of the books in ERPNext were filed outside Steuerbote, from other books."""

	def test_a_period_filed_before_steuerbote_replaces_those_of_the_rules_in_its_months(self):
		rules = [Period.month(2026, month) for month in range(1, 13)]
		prior = [Period.quarter(2026, 1), Period.month(2026, 4)]
		self.assertEqual(
			periods_with_the_books(rules, prior, date(2026, 7, 1), (2026,)),
			(
				Period.quarter(2026, 1),
				*(Period.month(2026, month) for month in range(4, 13)),
			),
		)

	def test_a_month_before_the_start_without_a_period_counts_as_a_month(self):
		rules = [Period.month(2026, month) for month in range(7, 13)]
		self.assertEqual(
			periods_with_the_books(rules, [], date(2026, 3, 1), (2026,)),
			(Period.month(2026, 1), Period.month(2026, 2), *rules),
		)

	def test_without_a_start_the_periods_of_the_rules_stay(self):
		rules = [Period.month(2026, month) for month in range(1, 13)]
		self.assertEqual(
			periods_with_the_books(rules, [Period.quarter(2026, 1)], None, (2026,)), tuple(rules)
		)

	def test_every_period_before_the_start_counts_as_filed_before_any_booking(self):
		periods = (Period.month(2026, 5), Period.month(2026, 6), JULY)
		filings = filed_outside(periods, date(2026, 7, 1))
		self.assertEqual(
			[filing.period for filing in filings], [Period.month(2026, 5), Period.month(2026, 6)]
		)
		self.assertEqual(
			{(filing.first, filing.latest) for filing in filings}, {(datetime.min, datetime.min)}
		)
		self.assertEqual(filed_outside(periods, None), ())

	def test_a_booking_for_a_period_before_the_start_is_late_whenever_it_was_booked(self):
		june = Period.month(2026, 6)
		periods = (june, JULY, AUGUST)
		for treatment, reported in ((LateTreatment.CORRECTION, june), (LateTreatment.CURRENT_PERIOD, JULY)):
			with self.subTest(treatment=treatment):
				assignment = Assignment(
					PeriodBasis.SERVICE_DATE, treatment, periods, filed_outside(periods, date(2026, 7, 1))
				)
				placement = assignment.place(
					booking(posting=date(2026, 7, 2), booked=at(2, 7), service=date(2026, 6, 30))
				)
				self.assertTrue(placement.late)
				self.assertEqual((placement.tax_period, placement.period), (june, reported))
