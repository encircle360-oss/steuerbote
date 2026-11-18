from decimal import Decimal
from unittest import TestCase

from steuerbote.steuerbote.report.ustva_kennzahlen.attribution import COLUMNS, contributions, report_rows
from steuerbote.steuerbote.report.ustva_kennzahlen.comparison import (
	compared_kennzahlen,
	compared_rows,
	note_row,
	year_before,
)
from steuerbote.ustva import LedgerLine, Period, UstvaResult, calculate
from steuerbote.ustva.defaults import SKR03


def d(value: str) -> Decimal:
	return Decimal(value)


def line(account: str, debit: str = "0", credit: str = "0", voucher: str | None = None) -> LedgerLine:
	return LedgerLine(account, Decimal(debit), Decimal(credit), voucher)


# The month of the report: a sale at 19 %, a service to a business in another EU country and a purchase.
MARCH = (
	line("1400", debit="1190", voucher="Journal Entry:JE-1"),
	line("8400", credit="1000", voucher="Journal Entry:JE-1"),
	line("1776", credit="190", voucher="Journal Entry:JE-1"),
	line("1400", debit="2000", voucher="Journal Entry:JE-2"),
	line("8336", credit="2000", voucher="Journal Entry:JE-2"),
	line("1576", debit="95", voucher="Journal Entry:JE-3"),
	line("1200", credit="95", voucher="Journal Entry:JE-3"),
)
# The month before: a smaller sale, a slightly smaller service, the same purchase and an intra-community
# delivery that March does not have.
FEBRUARY = (
	line("1400", debit="952", voucher="Journal Entry:JE-4"),
	line("8400", credit="800", voucher="Journal Entry:JE-4"),
	line("1776", credit="152", voucher="Journal Entry:JE-4"),
	line("1400", debit="1950", voucher="Journal Entry:JE-5"),
	line("8336", credit="1950", voucher="Journal Entry:JE-5"),
	line("1576", debit="95", voucher="Journal Entry:JE-6"),
	line("1200", credit="95", voucher="Journal Entry:JE-6"),
	line("1400", debit="800", voucher="Journal Entry:JE-7"),
	line("8125", credit="800", voucher="Journal Entry:JE-7"),
)
# March one year earlier: a sale at 19 % only.
MARCH_A_YEAR_BEFORE = (
	line("1400", debit="1071", voucher="Journal Entry:JE-8"),
	line("8400", credit="900", voucher="Journal Entry:JE-8"),
	line("1776", credit="171", voucher="Journal Entry:JE-8"),
)


def result_of(lines: tuple[LedgerLine, ...] | None) -> UstvaResult | None:
	return None if lines is None else calculate(lines, SKR03)


def compared(
	previous: tuple[LedgerLine, ...] | None = FEBRUARY,
	previous_year: tuple[LedgerLine, ...] | None = MARCH_A_YEAR_BEFORE,
) -> list[dict]:
	"""The rows of March, compared with the previous period and the same period a year before."""
	before, year_ago = result_of(previous), result_of(previous_year)
	rows = report_rows(
		calculate(MARCH, SKR03),
		SKR03.catalogue,
		contributions(MARCH, SKR03),
		posting_dates={},
		account_names={},
		parties={},
		print_label="Drucken",
		currency="EUR",
		shown=compared_kennzahlen(before, year_ago),
	)
	return compared_rows(rows, before, year_ago)


def comparison_of(rows: list[dict]) -> list[tuple]:
	return [
		(
			row["kennzahl"],
			row["line"],
			row["reported"],
			row["previous_period"],
			row["previous_year"],
			row["difference"],
		)
		for row in rows
		if not row["indent"]
	]


class ComparedRowsTest(TestCase):
	def test_kennzahlen_and_sums_carry_what_the_compared_periods_reported(self):
		self.assertEqual(
			comparison_of(compared()),
			[
				("81", 13, d("1000"), d("800"), d("900"), d("200")),
				("41", 19, d("0"), d("800"), d("0"), d("-800")),
				("21", 35, d("2000"), d("1950"), d("0"), d("50")),
				(None, 37, d("190.00"), d("152.00"), d("171.00"), d("38.00")),
				("66", 38, d("95.00"), d("95.00"), d("0"), d("0.00")),
				(None, 45, d("95.00"), d("57.00"), d("171.00"), d("38.00")),
				(None, 48, d("95.00"), d("57.00"), d("171.00"), d("38.00")),
				("83", 50, d("95.00"), d("57.00"), d("171.00"), d("38.00")),
			],
		)

	def test_voucher_rows_are_not_compared(self):
		vouchers = [row for row in compared() if row["indent"]]
		self.assertEqual(len(vouchers), 3)
		for row in vouchers:
			with self.subTest(voucher=row["voucher_no"]):
				self.assertEqual(
					(row["previous_period"], row["previous_year"], row["difference"]), (None, None, None)
				)

	def test_without_a_previous_period_its_column_and_the_difference_stay_empty(self):
		first_two = comparison_of(compared(previous=None))[:2]
		self.assertEqual(
			first_two,
			[("81", 13, d("1000"), None, d("900"), None), ("21", 35, d("2000"), None, d("0"), None)],
		)

	def test_without_a_previous_year_its_column_stays_empty(self):
		first_two = comparison_of(compared(previous_year=None))[:2]
		self.assertEqual(
			first_two,
			[("81", 13, d("1000"), d("800"), None, d("200")), ("41", 19, d("0"), d("800"), None, d("-800"))],
		)

	def test_a_note_row_stays_as_it_is(self):
		note = note_row("Kein Vergleich mit März 2025.")
		self.assertEqual(compared_rows([note], result_of(FEBRUARY), result_of(MARCH_A_YEAR_BEFORE)), [note])

	def test_every_row_has_every_column(self):
		for row in compared():
			self.assertLessEqual(set(COLUMNS), row.keys())


class ComparedKennzahlenTest(TestCase):
	def test_the_kennzahlen_reported_in_any_compared_period(self):
		self.assertEqual(
			compared_kennzahlen(result_of(FEBRUARY), None, result_of(MARCH_A_YEAR_BEFORE)),
			{"81", "21", "41", "66", "83"},
		)

	def test_without_compared_periods_there_is_nothing_more_to_show(self):
		self.assertEqual(compared_kennzahlen(None, None), frozenset())


class YearBeforeTest(TestCase):
	def test_the_same_period_one_year_earlier(self):
		self.assertEqual(year_before(Period.month(2026, 3)), Period.month(2025, 3))
		self.assertEqual(year_before(Period.quarter(2026, 1)), Period.quarter(2025, 1))


class NoteRowTest(TestCase):
	def test_a_note_is_a_row_of_its_own_with_the_text_as_label(self):
		self.assertEqual(
			note_row("Kein Vergleich mit Dezember 2025."),
			{
				**dict.fromkeys(COLUMNS),
				"label": "Kein Vergleich mit Dezember 2025.",
				"indent": 0,
				"parent_kennzahl": None,
				"bold": 0,
			},
		)
