"""The Einlagen of a year as the books show them: § 4 Abs. 1 Satz 1 und 8 EStG with § 8 Abs. 1 KStG, the same in every
year, the founding year among them. All accounts and amounts are invented, SKR04 numbers placed as the defaults place
them."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.ebilanz.contributions import Line, booked_contributions

CONCEPTS = {
	"1800": "bs.ass.currAss.cashEquiv.bank",
	"1298": "bs.ass.currAss.receiv.other.other",
	"2900": "de-gaap-ci:bs.eqLiab.equity.subscribed.corp",
	"2908": "bs.eqLiab.equity.subscribed.corp",
	"2910": "bs.eqLiab.equity.subscribed.unpaidCap",
	"2920": "bs.eqLiab.equity.capRes",
	"2960": "bs.eqLiab.equity.revenueRes.other",
	"2970": "bs.eqLiab.equity.retainedEarnings",
	"3300": "bs.eqLiab.otherLiab.other",
	"4400": "is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales",
	"7300": "is.netIncome.regular.operatingTC.otherCost.other",
}


def d(value: str) -> Decimal:
	return Decimal(value)


def lines(voucher: str, *rows: tuple[str, str, str]) -> list[Line]:
	return [Line(voucher, account, d(debit), d(credit)) for account, debit, credit in rows]


class BookedContributionsTest(TestCase):
	def test_share_capital_and_capital_reserve_paid_in_are_einlagen(self):
		"""Stammkapital at the founding, a capital increase and a payment into the Kapitalrücklage (§ 272 Abs. 2 Nr. 4
		HGB) bring Wirtschaftsgüter in from outside the company: Einlagen."""
		booked = [
			*lines("JE-1", ("1800", "25000.00", "0"), ("2900", "0", "25000.00")),
			*lines("JE-2", ("1800", "12000.00", "0"), ("2900", "0", "10000.00"), ("2920", "0", "2000.00")),
			*lines("JE-3", ("1800", "500.50", "0"), ("2920", "0", "500.50")),
		]
		self.assertEqual(booked_contributions(booked, CONCEPTS), d("37500.50"))

	def test_moves_within_the_eigenkapital_are_none(self):
		"""A Kapitalerhöhung aus Gesellschaftsmitteln, a release of the Kapitalrücklage into a reserve and the Stammkapital
		subscribed but not called in bring nothing in."""
		booked = [
			*lines("JE-1", ("2960", "8000.00", "0"), ("2908", "0", "8000.00")),
			*lines("JE-2", ("2920", "1000.00", "0"), ("2960", "0", "1000.00")),
			*lines("JE-3", ("2910", "25000.00", "0"), ("2900", "0", "25000.00")),
		]
		self.assertEqual(booked_contributions(booked, CONCEPTS), d("0.00"))

	def test_the_payment_of_capital_not_called_in_and_a_claim_called_in_are_einlagen(self):
		"""Paid later, the Stammkapital not called in is brought in by the payment; called in, the claim on the shareholder
		is a Wirtschaftsgut of the company when it arises (§ 272 Abs. 1 Satz 2 und 3 HGB)."""
		booked = [
			*lines("JE-1", ("1800", "12500.00", "0"), ("2910", "0", "12500.00")),
			*lines("JE-2", ("1298", "5000.00", "0"), ("2910", "0", "5000.00")),
		]
		self.assertEqual(booked_contributions(booked, CONCEPTS), d("17500.00"))

	def test_what_leaves_the_eigenkapital_or_is_no_capital_is_no_einlage(self):
		"""A release of the Kapitalrücklage into the GuV, a distribution and a profit booked on a reserve are no Einlage;
		an account without a place counts outside the Eigenkapital."""
		booked = [
			*lines("JE-1", ("2920", "3000.00", "0"), ("7300", "0", "3000.00")),
			*lines("JE-2", ("2970", "4000.00", "0"), ("3300", "0", "4000.00")),
			*lines("JE-3", ("1800", "900.00", "0"), ("2960", "0", "900.00")),
			*lines("JE-4", ("9999", "700.00", "0"), ("2920", "0", "700.00")),
		]
		self.assertEqual(booked_contributions(booked, CONCEPTS), d("700.00"))

	def test_a_voucher_counts_only_what_reaches_the_capital_from_outside_the_eigenkapital(self):
		booked = lines("JE-1", ("1800", "1000.00", "0"), ("2960", "4000.00", "0"), ("2900", "0", "5000.00"))
		self.assertEqual(booked_contributions(booked, CONCEPTS), d("1000.00"))
		self.assertEqual(booked_contributions([], CONCEPTS), d("0.00"))
