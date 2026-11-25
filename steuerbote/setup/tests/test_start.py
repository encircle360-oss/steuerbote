import re
from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.setup import start
from steuerbote.setup.start import Check, Facts, Item, PriorFiling, StartError
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import CarryForward, CarryForwardKind
from steuerbote.ustva.period import Period

START = date(2027, 1, 1)
FILED = date(2026, 2, 10)


def filing(period: Period, kz83: str = "1000.00", **amounts: str) -> PriorFiling:
	values = {key: Decimal(value) for key, value in amounts.items()}
	return PriorFiling(period, f"VVS-{period.year}-{period.code}", FILED, Decimal(kz83), **values)


def months(year: int, first: int = 1, last: int = 12, kz83: str = "1000.00") -> list[PriorFiling]:
	return [filing(Period.month(year, month), kz83) for month in range(first, last + 1)]


class BooksStartTest(TestCase):
	def test_the_start_is_the_first_day_of_a_month(self):
		self.assertEqual(start.check_start(date(2027, 1, 1)), date(2027, 1, 1))
		self.assertEqual(start.check_start(date(2027, 7, 1)), date(2027, 7, 1))
		with self.assertRaises(StartError) as caught:
			start.check_start(date(2027, 1, 15))
		self.assertEqual(caught.exception.template, start.NOT_FIRST_OF_MONTH)
		self.assertEqual(caught.exception.values, ("15. Januar 2027",))

	def test_a_period_that_begins_before_the_start_lies_before_it(self):
		self.assertTrue(start.before_start(Period.month(2026, 12).start, START))
		self.assertFalse(start.before_start(Period.month(2027, 1).start, START))
		self.assertTrue(start.before_start(Period.quarter(2027, 1).start, date(2027, 2, 1)))

	def test_without_a_start_nothing_lies_before_it(self):
		self.assertFalse(start.before_start(date(1990, 1, 1), None))

	def test_a_prior_filing_belongs_to_a_period_before_the_start(self):
		start.check_prior_period(Period.month(2026, 12), START)
		start.check_prior_period(Period.month(2031, 5), None)
		with self.assertRaises(StartError) as caught:
			start.check_prior_period(Period.month(2027, 1), START)
		self.assertEqual(caught.exception.template, start.NOT_BEFORE_START)
		self.assertEqual(caught.exception.values, ("Januar 2027", "1. Januar 2027"))
		self.assertIn("Januar 2027", str(caught.exception))


class PriorFilingTest(TestCase):
	def test_holds_the_amounts_as_filed_in_cents(self):
		filed = filing(Period.month(2026, 12), "-250.50", kz39="1781.00", kz41="12000.00")
		self.assertEqual(
			(filed.kz83, filed.kz39, filed.kz41, filed.kz42, filed.kz21),
			(
				Decimal("-250.50"),
				Decimal("1781.00"),
				Decimal("12000.00"),
				Decimal("0.00"),
				Decimal("0.00"),
			),
		)
		with self.assertRaises(ValueError):
			filing(Period.month(2026, 12), "1.005")
		with self.assertRaises(ValueError):
			filing(Period.month(2026, 12), kz21="0.001")

	def test_names_its_months(self):
		self.assertEqual(filing(Period.quarter(2026, 4)).months, ((2026, 10), (2026, 11), (2026, 12)))
		self.assertEqual(filing(Period.month(2026, 3)).months, ((2026, 3),))

	def test_the_latest_filing_of_a_period_counts(self):
		first = filing(Period.month(2026, 5), "100.00")
		corrected = PriorFiling(Period.month(2026, 5), "VVS-2026-00009", date(2026, 9, 1), Decimal("120.00"))
		same_day = PriorFiling(Period.month(2026, 5), "VVS-2026-00010", date(2026, 9, 1), Decimal("130.00"))
		april = filing(Period.month(2026, 4), "90.00")
		self.assertEqual(start.latest([first, corrected, april]), (april, corrected))
		self.assertEqual(start.latest([same_day, corrected]), (same_day,))
		self.assertEqual(start.latest([]), ())

	def test_finds_a_filing_of_another_period_whose_months_overlap(self):
		quarter = filing(Period.quarter(2026, 4))
		december = filing(Period.month(2026, 12))
		november = filing(Period.month(2026, 11))
		self.assertEqual(start.overlapping(december, [quarter]), quarter)
		self.assertIsNone(start.overlapping(december, [november, filing(Period.month(2026, 12), "5.00")]))


class FromPriorFilingsTest(TestCase):
	def test_the_tax_of_a_whole_year_is_kz_83_with_the_sondervorauszahlung_credited(self):
		filings = months(2026)
		filings[11] = filing(Period.month(2026, 12), "-781.00", kz39="1781.00")
		self.assertEqual(start.year_tax(filings, 2026), Decimal("12000.00"))

	def test_quarters_cover_their_months(self):
		filings = [filing(Period.quarter(2026, quarter), "3000.00") for quarter in range(1, 5)]
		self.assertEqual(start.year_tax(filings, 2026), Decimal("12000.00"))

	def test_without_every_month_the_tax_is_unknown(self):
		self.assertIsNone(start.year_tax(months(2026, 1, 11), 2026))
		self.assertIsNone(start.year_tax(months(2025), 2026))

	def test_a_company_that_began_in_the_year_needs_its_months_from_then_on(self):
		self.assertEqual(start.year_tax(months(2026, 5), 2026, first_month=5), Decimal("8000.00"))
		self.assertIsNone(start.year_tax(months(2026, 6), 2026, first_month=5))

	def test_only_the_latest_filing_of_a_period_counts(self):
		filings = [
			PriorFiling(Period.month(2026, 1), "VVS-2026-00099", date(2026, 6, 1), Decimal("1500.00")),
			*months(2026),
		]
		self.assertEqual(start.year_tax(filings, 2026), Decimal("12500.00"))

	def test_the_deliveries_of_a_period_lie_in_its_first_month(self):
		filings = [
			filing(Period.quarter(2026, 3), kz41="30000.00", kz42="5000.00"),
			filing(Period.month(2026, 10), kz41="100.00"),
		]
		self.assertEqual(
			start.deliveries(filings),
			{
				(2026, 7): Decimal("35000.00"),
				(2026, 8): Decimal("0.00"),
				(2026, 9): Decimal("0.00"),
				(2026, 10): Decimal("100.00"),
			},
		)

	def test_names_the_months_before_the_start_that_no_filing_covers(self):
		filings = [*months(2026, 1, 9), filing(Period.quarter(2026, 4))]
		self.assertEqual(start.missing_months(START, None, filings), ())
		self.assertEqual(start.missing_months(START, None, months(2026, 1, 10)), ((2026, 11), (2026, 12)))
		self.assertEqual(start.missing_months(date(2027, 3, 1), None, months(2026)), ((2027, 1), (2027, 2)))

	def test_months_before_the_company_began_are_not_missing(self):
		self.assertEqual(start.missing_months(START, date(2026, 11, 20), months(2026, 11)), ())
		self.assertEqual(start.missing_months(START, date(2026, 11, 20), []), ((2026, 11), (2026, 12)))
		self.assertEqual(start.missing_months(START, date(2027, 1, 1), []), ())
		self.assertEqual(start.missing_months(None, None, []), ())


LOSS = CarryForwardKind.LOSS
EINLAGEKONTO = CarryForwardKind.EINLAGEKONTO
FEHLBETRAG = CarryForwardKind.FEHLBETRAG
YEAR_END = date(2026, 12, 31)


def stated(kind: CarryForwardKind, as_of: date = YEAR_END, amount: str = "0.00") -> CarryForward:
	return CarryForward(kind, as_of, Decimal(amount), confirmed=True)


class CarryForwardsTest(TestCase):
	def test_names_each_kind_the_first_returns_need_without_an_amount_as_of_the_day(self):
		self.assertEqual(start.missing_carry_forwards([], YEAR_END), (LOSS, FEHLBETRAG, EINLAGEKONTO))
		self.assertEqual(
			start.missing_carry_forwards(
				[
					stated(LOSS),
					stated(EINLAGEKONTO, amount="25000.00"),
					stated(FEHLBETRAG, date(2025, 12, 31)),
				],
				YEAR_END,
			),
			(FEHLBETRAG,),
		)

	def test_an_amount_of_0_counts(self):
		amounts = [stated(LOSS), stated(FEHLBETRAG), stated(EINLAGEKONTO)]
		self.assertEqual(start.missing_carry_forwards(amounts, YEAR_END), ())

	def test_the_kinds_are_those_the_returns_carry_from_their_notices(self):
		self.assertEqual(start.FIRST_YEAR_KINDS, (LOSS, FEHLBETRAG, EINLAGEKONTO))


class ChecklistTest(TestCase):
	def items(self, facts: Facts) -> dict[Item, Check]:
		return {check.item: check for check in start.checklist(facts)}

	def test_without_a_start_it_only_says_what_one_is_for(self):
		checks = start.checklist(Facts(None))
		self.assertEqual(checks, (Check(Item.START, None, start.START_MISSING, ()),))

	def test_names_every_item_in_the_order_a_user_works_through_them(self):
		checks = start.checklist(Facts(START, annual_settings=True))
		self.assertEqual(
			[check.item for check in checks],
			[
				Item.START,
				Item.OPENING_ENTRIES,
				Item.PRIOR_RETURNS,
				Item.PRIOR_PAYMENTS,
				Item.DAUERFRIST,
				Item.CARRY_FORWARDS,
				Item.PREPAYMENTS,
				Item.PRIOR_YEAR_ACCOUNTS,
			],
		)

	def test_a_complete_start_has_no_open_item(self):
		checks = self.items(Facts(START, annual_settings=True))
		self.assertEqual(
			{item: check.done for item, check in checks.items()},
			{
				Item.START: True,
				Item.OPENING_ENTRIES: True,
				Item.PRIOR_RETURNS: True,
				Item.PRIOR_PAYMENTS: True,
				Item.DAUERFRIST: None,
				Item.CARRY_FORWARDS: True,
				Item.PREPAYMENTS: None,
				Item.PRIOR_YEAR_ACCOUNTS: None,
			},
		)
		self.assertEqual(checks[Item.START].values, ("1. Januar 2027",))
		self.assertEqual(checks[Item.PRIOR_RETURNS].values, ("1. Januar 2027",))
		self.assertEqual(checks[Item.DAUERFRIST].values, (2027,))
		self.assertEqual(checks[Item.CARRY_FORWARDS].values, ("31. Dezember 2026",))
		self.assertEqual(checks[Item.PREPAYMENTS].values, (2027,))
		self.assertEqual(checks[Item.PRIOR_YEAR_ACCOUNTS].values, (2026,))

	def test_names_what_is_open(self):
		checks = self.items(
			Facts(
				START,
				unflagged=("ACC-JV-2027-00001", "ACC-JV-2027-00002"),
				missing_prior=((2026, 11), (2026, 12)),
				annual_settings=True,
				missing_carry_forwards=(LOSS, EINLAGEKONTO),
			)
		)
		self.assertEqual(
			checks[Item.OPENING_ENTRIES],
			Check(
				Item.OPENING_ENTRIES,
				False,
				start.OPENING_UNFLAGGED,
				("1. Januar 2027", "ACC-JV-2027-00001, ACC-JV-2027-00002"),
			),
		)
		self.assertEqual(
			checks[Item.PRIOR_RETURNS],
			Check(Item.PRIOR_RETURNS, False, start.PRIOR_MISSING, ("November 2026, Dezember 2026",)),
		)
		self.assertEqual(
			checks[Item.CARRY_FORWARDS],
			Check(
				Item.CARRY_FORWARDS,
				False,
				start.CARRY_FORWARDS_MISSING,
				("31. Dezember 2026", "Loss Carried Forward (§ 10d EStG), Einlagekonto (§ 27 KStG)"),
			),
		)

	def test_without_annual_filing_settings_it_asks_for_them(self):
		checks = self.items(Facts(START))
		self.assertEqual(
			checks[Item.CARRY_FORWARDS],
			Check(Item.CARRY_FORWARDS, False, start.ANNUAL_SETTINGS_MISSING, ("31. Dezember 2026",)),
		)

	def test_every_text_is_a_message_of_the_module(self):
		facts = (
			Facts(None),
			Facts(START),
			Facts(START, annual_settings=True),
			Facts(START, ("X",), ((2026, 1),), True, (LOSS,)),
		)
		for checks in map(start.checklist, facts):
			for check in checks:
				with self.subTest(check=check):
					self.assertIn(check.template, start.MESSAGES)
					self.assertEqual(len(set(re.findall(r"\{(\d+)\}", check.template))), len(check.values))


def payment(voucher: str, debit: str = "0", credit: str = "0", account: str = "1780"):
	from steuerbote.ustva.calculation import LedgerLine

	return LedgerLine(account, Decimal(debit), Decimal(credit), f"Journal Entry:{voucher}")


class PriorPaymentsTest(TestCase):
	"""A payment in the first year on the accounts of the Vorauszahlungen that pays Kz 83 of a Voranmeldung filed before
	Steuerbote belongs to that return, not to the Vorauszahlungen of the new year."""

	NOVEMBER = filing(Period.month(2026, 11), "900.00")
	DECEMBER = filing(Period.month(2026, 12), "1200.00", kz39="2500.00")

	def test_a_payment_of_kz_83_of_a_return_filed_before_belongs_to_it(self):
		lines = [
			payment("JV-1", debit="900.00"),
			payment("JV-2", debit="1200.00"),
			payment("JV-3", debit="2681.00", account="1781"),
		]
		found = start.prior_payments(lines, [self.DECEMBER, self.NOVEMBER])
		self.assertEqual(
			[(item.voucher, item.amount, item.filing.period.label) for item in found],
			[
				("Journal Entry:JV-1", Decimal("900.00"), "November 2026"),
				("Journal Entry:JV-2", Decimal("1200.00"), "Dezember 2026"),
			],
		)

	def test_a_refund_of_a_surplus_as_well(self):
		surplus = filing(Period.month(2026, 12), "-400.00")
		(found,) = start.prior_payments([payment("JV-1", credit="400.00")], [surplus])
		self.assertEqual(found.amount, Decimal("-400.00"))

	def test_a_voucher_counts_with_all_its_lines_and_once(self):
		lines = [payment("JV-1", debit="1000.00"), payment("JV-1", debit="200.00", account="1781")]
		(found,) = start.prior_payments(lines, [self.DECEMBER, filing(Period.month(2026, 10), "1200.00")])
		self.assertEqual(found.filing, self.DECEMBER)

	def test_each_return_is_paid_once_and_a_return_of_nothing_never(self):
		lines = [payment("JV-1", debit="1200.00"), payment("JV-2", debit="1200.00")]
		self.assertEqual(len(start.prior_payments(lines, [self.DECEMBER])), 1)
		self.assertEqual(
			start.prior_payments([payment("JV-1")], [filing(Period.month(2026, 12), "0.00")]), ()
		)

	def test_only_the_latest_filing_of_a_period_is_paid(self):
		corrected = PriorFiling(
			Period.month(2026, 12), "VVS-2026-00099", date(2027, 3, 1), Decimal("1300.00")
		)
		found = start.prior_payments([payment("JV-1", debit="1200.00")], [self.DECEMBER, corrected])
		self.assertEqual(found, ())

	def test_the_checklist_names_them(self):
		checks = {
			check.item: check
			for check in start.checklist(Facts(START, annual_settings=True, prior_payments=("JV-1", "JV-2")))
		}
		self.assertEqual(
			checks[Item.PRIOR_PAYMENTS],
			Check(Item.PRIOR_PAYMENTS, False, start.PRIOR_PAYMENTS_FOUND, ("JV-1, JV-2",)),
		)
		self.assertIn(start.PRIOR_PAYMENTS_FOUND, start.MESSAGES)
		self.assertIn(start.PRIOR_PAYMENTS_CLEAN, start.MESSAGES)
