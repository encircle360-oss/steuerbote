from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.setup.rhythm import Proposal, Reason, first_month, needs_tax, propose
from steuerbote.steuerbote.doctype.vat_return_settings.rules import FilingRhythm

MONTHLY = FilingRhythm.MONTHLY
QUARTERLY = FilingRhythm.QUARTERLY
LONG_AGO = date(2019, 3, 1)


class TaxOfThePreviousYearTest(TestCase):
	"""§ 18 Absatz 2 Sätze 1 bis 3 and Absatz 2a UStG."""

	def test_more_than_9000_euros_of_tax_make_the_month(self):
		self.assertEqual(
			propose(2027, LONG_AGO, Decimal("9000.01")),
			Proposal(MONTHLY, Reason.TAX_ABOVE_LIMIT, Decimal("9000.01")),
		)

	def test_9000_euros_of_tax_keep_the_quarter(self):
		self.assertEqual(
			propose(2027, LONG_AGO, Decimal("9000.00")),
			Proposal(QUARTERLY, Reason.TAX_UP_TO_LIMIT, Decimal("9000.00")),
		)

	def test_at_most_2000_euros_the_finanzamt_may_exempt_the_company(self):
		for tax in ("2000.00", "0", "-500.00"):
			with self.subTest(tax=tax):
				proposal = propose(2027, LONG_AGO, Decimal(tax))
				self.assertEqual((proposal.rhythm, proposal.exemption_possible), (QUARTERLY, True))
		self.assertFalse(propose(2027, LONG_AGO, Decimal("2000.01")).exemption_possible)

	def test_a_surplus_above_9000_euros_lets_the_company_choose_the_month(self):
		proposal = propose(2027, LONG_AGO, Decimal("-9000.01"))
		self.assertEqual(
			proposal, Proposal(QUARTERLY, Reason.TAX_UP_TO_LIMIT, Decimal("-9000.01"), True, True)
		)
		self.assertFalse(propose(2027, LONG_AGO, Decimal("-9000.00")).month_possible)

	def test_without_the_tax_of_the_previous_year_there_is_no_proposal(self):
		self.assertEqual(propose(2026, LONG_AGO, None), Proposal(None, Reason.NO_TAX))
		self.assertEqual(propose(2026, None, None), Proposal(None, Reason.NO_TAX))

	def test_a_company_without_a_date_of_establishment_goes_by_its_tax(self):
		self.assertEqual(propose(2027, None, Decimal("12000")).rhythm, MONTHLY)

	def test_the_tax_is_a_decimal(self):
		with self.assertRaises(TypeError):
			propose(2027, LONG_AGO, 12000.0)  # type: ignore[arg-type]


class StartTest(TestCase):
	"""§ 18 Absatz 2 Sätze 4 and 6 UStG."""

	def test_from_2027_a_company_files_monthly_in_the_year_it_began_and_the_next(self):
		for began in (date(2027, 5, 15), date(2026, 1, 1)):
			with self.subTest(began=began):
				self.assertEqual(propose(2027, began, Decimal("100")), Proposal(MONTHLY, Reason.STARTED))

	def test_until_2026_the_expected_tax_of_the_year_decides_which_steuerbote_does_not_know(self):
		self.assertEqual(propose(2026, date(2026, 2, 1), None), Proposal(None, Reason.STARTED_THIS_YEAR))

	def test_until_2026_the_tax_of_the_part_year_turned_into_a_whole_year_decides(self):
		self.assertEqual(
			propose(2026, date(2025, 8, 1), Decimal("50000")), Proposal(None, Reason.STARTED_LAST_YEAR)
		)

	def test_two_years_after_the_start_the_tax_decides(self):
		self.assertEqual(propose(2027, date(2025, 12, 31), Decimal("100")).reason, Reason.TAX_UP_TO_LIMIT)

	def test_a_company_that_begins_after_the_year_gets_no_proposal(self):
		self.assertEqual(propose(2026, date(2027, 1, 1), None), Proposal(None, Reason.NOT_STARTED))

	def test_only_a_proposal_from_the_tax_needs_the_tax(self):
		self.assertTrue(needs_tax(2027, None))
		self.assertTrue(needs_tax(2027, date(2025, 12, 31)))
		self.assertFalse(needs_tax(2027, date(2026, 1, 1)))
		self.assertFalse(needs_tax(2027, date(2027, 6, 1)))
		self.assertFalse(needs_tax(2027, date(2028, 6, 1)))


class FirstMonthTest(TestCase):
	def test_the_rule_starts_in_january(self):
		self.assertEqual(first_month(2027, None), 1)
		self.assertEqual(first_month(2027, date(2026, 11, 1)), 1)

	def test_a_company_that_began_in_the_year_starts_with_the_quarter_of_its_start(self):
		for month, first in ((1, 1), (3, 1), (4, 4), (6, 4), (7, 7), (9, 7), (10, 10), (12, 10)):
			with self.subTest(month=month):
				self.assertEqual(first_month(2027, date(2027, month, 15)), first)
