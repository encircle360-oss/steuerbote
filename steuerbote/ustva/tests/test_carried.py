"""A watched timing account that releases the balance it carries into a period, such as the Vorsteuer of a December
invoice deductible in January, blocks no Voranmeldung; any other movement on it still does."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva import carried
from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.carried import Release
from steuerbote.ustva.defaults import TIMING_ACCOUNTS
from steuerbote.ustva.plausibility import Code, Severity
from steuerbote.ustva.tests.test_plausibility import FIGURES

TIMING = ("1548", "1725")


def d(value: str) -> Decimal:
	return Decimal(value)


def line(
	account: str, debit: str = "0", credit: str = "0", voucher: str = "Journal Entry:JV-1"
) -> LedgerLine:
	return LedgerLine(account, d(debit), d(credit), voucher)


# Vorsteuer of 1.900 € deductible in January: the books carry it on 1548 into the year, and January moves it to 1576.
JANUARY = [line("1548", credit="1900.00"), line("1576", debit="1900.00")]


class TimingAccountsTest(TestCase):
	def test_are_the_accounts_of_vorsteuer_and_umsatzsteuer_of_a_later_period(self):
		self.assertEqual(dict(TIMING_ACCOUNTS), {"SKR03": ("1548", "1725"), "SKR04": ("1434", "3865")})


class CarriedBalancesTest(TestCase):
	def test_the_balance_at_the_end_of_the_period_less_its_movement(self):
		closing = {"1548": d("0.00"), "1725": d("-500.00")}
		self.assertEqual(
			carried.carried_balances(closing, JANUARY), {"1548": d("1900.00"), "1725": d("-500.00")}
		)


class ReleasesTest(TestCase):
	def test_releasing_the_balance_carried_in_is_no_block(self):
		found = carried.releases(("1548",), JANUARY, {"1548": d("1900.00")}, TIMING)
		self.assertEqual(found, (Release("1548", d("1900.00"), d("-1900.00")),))
		self.assertEqual(carried.still_blocked(("1548", "1560"), found), ("1560",))

	def test_a_part_of_it_as_well(self):
		january = [line("1548", credit="900.00"), line("1548", debit="100.00", voucher="Journal Entry:JV-2")]
		(found,) = carried.releases(("1548",), january, {"1548": d("1900.00")}, TIMING)
		self.assertEqual(found.released, d("-800.00"))

	def test_umsatzsteuer_due_in_this_period(self):
		lines = [line("1725", debit="500.00"), line("1776", credit="500.00")]
		self.assertEqual(
			carried.releases(("1725",), lines, {"1725": d("-500.00")}, TIMING),
			(Release("1725", d("-500.00"), d("500.00")),),
		)

	def test_more_than_was_carried_still_blocks(self):
		self.assertEqual(carried.releases(("1548",), JANUARY, {"1548": d("1000.00")}, TIMING), ())

	def test_a_new_balance_still_blocks(self):
		lines = [line("1548", debit="1900.00")]
		self.assertEqual(carried.releases(("1548",), lines, {"1548": d("1900.00")}, TIMING), ())
		self.assertEqual(carried.releases(("1548",), lines, {}, TIMING), ())

	def test_only_a_timing_account(self):
		lines = [line("1560", credit="1900.00")]
		self.assertEqual(carried.releases(("1560",), lines, {"1560": d("1900.00")}, TIMING), ())

	def test_only_a_blocked_account(self):
		self.assertEqual(carried.releases((), JANUARY, {"1548": d("1900.00")}, TIMING), ())


class ReleaseHintsTest(TestCase):
	def test_names_the_account_what_it_released_and_what_it_carried(self):
		(hint,) = carried.release_hints(
			[Release("1548", d("1900.00"), d("-1900.00"))],
			{"1548": "Vorsteuer in Folgeperiode/im Folgejahr abziehbar"},
			FIGURES,
		)
		self.assertEqual((hint.code, hint.severity), (Code.WATCHED_ACCOUNT, Severity.HINT))
		self.assertEqual(
			hint.text,
			"Konto 1548 Vorsteuer in Folgeperiode/im Folgejahr abziehbar löst 1.900,00 € des Saldos auf, den es aus "
			"der Zeit davor trägt (1.900,00 € im Soll). Ein solcher Übergang in eine spätere Voranmeldung hält sie "
			"nicht an; die Steuer steht in der Kennzahl des Gegenkontos.",
		)

	def test_an_account_without_a_name(self):
		(hint,) = carried.release_hints([Release("1725", d("-500.00"), d("500.00"))], {}, FIGURES)
		self.assertTrue(hint.text.startswith("Konto 1725 löst 500,00 € des Saldos auf"))
		self.assertIn("(500,00 € im Haben)", hint.text)
