"""The balances of the books for the E-Bilanz and the Jahresabschluss (steuerbote/balances.py): a small chart with an
Eröffnungsbilanz, postings of two years, Period Closing Vouchers, cancellations, a finance book and an account without
number, read on a site."""

from datetime import date
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import balances
from steuerbote.tests.helpers import (
	cancel_voucher,
	ensure_fiscal_year,
	insert_record,
	make_account,
	make_company,
	post_journal_entry,
	post_ledger,
)
from steuerbote.xbrl.mapping import AccountBalance, Books, Part

COMPANY = "Steuerbote Test Salden GmbH"
OPEN = "Steuerbote Test Salden Offen GmbH"
NEIGHBOUR = "Steuerbote Test Salden Nachbar GmbH"
PCV = balances.PERIOD_CLOSING_VOUCHER
SAVEPOINT = "steuerbote_test_balances"
# SKR04 accounts of a small GmbH.
ACCOUNTS = {
	"1800": ("Bank", "Asset"),
	"2900": ("Gezeichnetes Kapital", "Equity"),
	"2970": ("Gewinnvortrag vor Verwendung", "Equity"),
	"3300": ("Verbindlichkeiten aus Lieferungen und Leistungen", "Liability"),
	"4400": ("Erlöse 19 % USt", "Income"),
	"6300": ("Sonstige betriebliche Aufwendungen", "Expense"),
}


def make_accounts(company: str) -> dict[str, str]:
	return {
		number: frappe.db.get_value("Account", {"company": company, "account_number": number})
		or make_account(company, number, label, root_type)
		for number, (label, root_type) in ACCOUNTS.items()
	}


def amounts(found: Books) -> dict[str, tuple[Decimal, Decimal]]:
	return {balance.number or balance.account: (balance.debit, balance.credit) for balance in found.balances}


def euros(debit: str = "0", credit: str = "0") -> tuple[Decimal, Decimal]:
	return Decimal(debit).quantize(Decimal("0.01")), Decimal(credit).quantize(Decimal("0.01"))


class IntegrationTestBalances(IntegrationTestCase):
	"""The founding in 2025, a year closed by its Period Closing Voucher, and 2026."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for year in (2025, 2026, 2027):
			ensure_fiscal_year(COMPANY, date(year, 6, 30))
		make_company(COMPANY, "STSD")
		cls.accounts = accounts = make_accounts(COMPANY)
		post_journal_entry(
			COMPANY,
			"2025-01-01",
			[(accounts["1800"], 25000, 0), (accounts["2900"], 0, 25000)],
			voucher_type="Opening Entry",
		)
		post_ledger(
			COMPANY,
			"Journal Entry",
			"STSD-2025-1",
			"2025-06-01",
			[(accounts["1800"], 1000, 0), (accounts["4400"], 0, 1000)],
		)
		post_ledger(
			COMPANY,
			PCV,
			"STSD-PCV-2025",
			"2025-12-31",
			[(accounts["4400"], 1000, 0), (accounts["2970"], 0, 1000)],
		)
		post_ledger(
			COMPANY,
			"Journal Entry",
			"STSD-2026-1",
			"2026-03-01",
			[(accounts["1800"], 500, 0), (accounts["4400"], 0, 500)],
		)
		post_ledger(
			COMPANY,
			"Journal Entry",
			"STSD-2026-2",
			"2026-04-01",
			[(accounts["6300"], 200, 0), (accounts["1800"], 0, 200)],
		)
		post_ledger(
			COMPANY,
			PCV,
			"STSD-PCV-2026",
			"2026-12-31",
			[(accounts["4400"], 500, 0), (accounts["6300"], 0, 200), (accounts["2970"], 0, 300)],
		)
		post_ledger(
			COMPANY,
			"Journal Entry",
			"STSD-2027-1",
			"2027-01-15",
			[(accounts["1800"], 50, 0), (accounts["4400"], 0, 50)],
		)
		insert_record(
			PCV,
			name="STSD-PCV-2026",
			company=COMPANY,
			period_start_date="2026-01-01",
			period_end_date="2026-12-31",
			closing_account_head=accounts["2970"],
			docstatus=1,
		)
		make_company(NEIGHBOUR, "STSN")
		neighbour = make_accounts(NEIGHBOUR)
		post_ledger(
			NEIGHBOUR,
			"Journal Entry",
			"STSN-2026-1",
			"2026-03-01",
			[(neighbour["1800"], 7, 0), (neighbour["4400"], 0, 7)],
		)

	def setUp(self):
		super().setUp()
		# A test that posts more takes it back, so that every test reads the books of setUpClass.
		frappe.db.savepoint(SAVEPOINT)
		self.addCleanup(frappe.db.rollback, save_point=SAVEPOINT)

	def test_the_bilanz_sums_up_to_the_stichtag_and_the_guv_within_the_year(self):
		"""Every entry of an account of the Bilanz up to the Stichtag, the opening entry included, and of an account of
		the GuV within the fiscal year; nothing after the Stichtag and nothing of another company."""
		found = balances.books(COMPANY, "2026-01-01", "2026-12-31")
		self.assertEqual(
			amounts(found),
			{
				"1800": euros("26500", "200"),
				"2900": euros(credit="25000"),
				"2970": euros(credit="1000"),
				"4400": euros(credit="500"),
				"6300": euros("200"),
			},
		)
		self.assertEqual(found.earlier_result, Decimal(0))
		self.assertEqual(
			found.balances[0],
			AccountBalance(self.accounts["1800"], "1800", "Bank", Part.BALANCE_SHEET, *euros("26500", "200")),
		)
		self.assertEqual(
			{balance.number: balance.part for balance in found.balances}["4400"], Part.INCOME_STATEMENT
		)

	def test_the_period_closing_voucher_of_the_year_stays_out_and_those_before_show_as_gewinnvortrag(self):
		"""The Aktiva of 26,300 € are the Passiva of 25,000 € Kapital, 1,000 € Gewinnvortrag of 2025 and the
		Jahresüberschuss of 300 € the GuV of 2026 gives."""
		found = amounts(balances.books(COMPANY, "2026-01-01", "2026-12-31"))
		aktiva = found["1800"][0] - found["1800"][1]
		passiva = sum(found[number][1] - found[number][0] for number in ("2900", "2970"))
		result = found["4400"][1] - found["6300"][0]
		self.assertEqual((aktiva, passiva, result), (Decimal("26300"), Decimal("26000"), Decimal("300")))

	def test_the_fiscal_year_names_its_period_closing_voucher_and_reads_the_year_before(self):
		year = balances.fiscal_year_books(
			COMPANY, frappe.db.get_value("Fiscal Year", {"year_start_date": "2026-01-01"})
		)
		self.assertEqual((year.from_date, year.to_date), (date(2026, 1, 1), date(2026, 12, 31)))
		self.assertEqual(year.closed_by, ("STSD-PCV-2026",))
		self.assertEqual((year.prior_from_date, year.prior_to_date), (date(2025, 1, 1), date(2025, 12, 31)))
		self.assertEqual(
			amounts(year.prior),
			{"1800": euros("26000"), "2900": euros(credit="25000"), "4400": euros(credit="1000")},
		)
		self.assertEqual(amounts(year.current), amounts(balances.books(COMPANY, "2026-01-01", "2026-12-31")))

	def test_the_first_year_of_the_books_has_no_year_before(self):
		year = balances.fiscal_year_books(
			COMPANY, frappe.db.get_value("Fiscal Year", {"year_start_date": "2025-01-01"})
		)
		self.assertEqual((year.prior, year.prior_from_date, year.prior_to_date), (None, None, None))

	def test_the_eroeffnungsbilanz_holds_the_opening_entries(self):
		found = balances.opening_books(COMPANY, "2025-01-01")
		self.assertEqual(amounts(found), {"1800": euros("25000"), "2900": euros(credit="25000")})
		self.assertEqual(found.earlier_result, Decimal(0))

	def test_a_cancelled_voucher_stays_out_and_an_immutable_cancellation_falls_into_its_own_year(self):
		"""ERPNext flags a cancelled voucher and its reversal; with the immutable ledger it posts the reversal on the day
		of the cancellation and flags nothing (make_reverse_gl_entries of ERPNext 16)."""
		accounts = self.accounts
		post_ledger(
			COMPANY,
			"Journal Entry",
			"STSD-2026-9",
			"2026-05-01",
			[(accounts["1800"], 80, 0), (accounts["4400"], 0, 80)],
		)
		cancel_voucher("Journal Entry", "STSD-2026-9")
		post_ledger(
			COMPANY,
			"Journal Entry",
			"STSD-2026-8",
			"2026-06-01",
			[(accounts["1800"], 30, 0), (accounts["4400"], 0, 30)],
		)
		cancel_voucher("Journal Entry", "STSD-2026-8", immutable_on="2027-02-01")
		self.assertEqual(
			amounts(balances.books(COMPANY, "2026-01-01", "2026-12-31"))["4400"], euros(credit="530")
		)
		self.assertEqual(
			amounts(balances.books(COMPANY, "2027-01-01", "2027-12-31"))["4400"], euros("30", "50")
		)

	def test_a_finance_book_takes_its_entries_and_those_without_a_book(self):
		insert_record(
			"GL Entry",
			company=COMPANY,
			posting_date="2026-12-31",
			account=self.accounts["6300"],
			debit=40,
			credit=0,
			voucher_type="Journal Entry",
			voucher_no="STSD-2026-SB",
			finance_book="Steuerbilanz",
			is_cancelled=0,
			is_opening="No",
			docstatus=1,
		)
		self.assertEqual(amounts(balances.books(COMPANY, "2026-01-01", "2026-12-31"))["6300"], euros("200"))
		self.assertEqual(
			amounts(balances.books(COMPANY, "2026-01-01", "2026-12-31", finance_book="Steuerbilanz"))["6300"],
			euros("240"),
		)
		self.assertEqual(
			amounts(balances.books(COMPANY, "2026-01-01", "2026-12-31", finance_book="Handelsbilanz"))[
				"6300"
			],
			euros("200"),
		)

	def test_an_account_without_number_keeps_an_empty_number(self):
		cash = frappe.db.get_value(
			"Account", {"company": COMPANY, "account_name": "Kasse ohne Nummer"}
		) or make_account(COMPANY, None, "Kasse ohne Nummer", "Asset")
		post_ledger(
			COMPANY,
			"Journal Entry",
			"STSD-2026-K",
			"2026-07-01",
			[(cash, 15, 0), (self.accounts["4400"], 0, 15)],
		)
		(found,) = (
			balance
			for balance in balances.books(COMPANY, "2026-01-01", "2026-12-31").balances
			if balance.account == cash
		)
		self.assertEqual(
			(found.number, found.label, found.amount), ("", "Kasse ohne Nummer", Decimal("15.00"))
		)


class IntegrationTestEarlierResult(IntegrationTestCase):
	"""A year no Period Closing Voucher closed: its result is the earlier result of the next year."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for year in (2025, 2026):
			ensure_fiscal_year(OPEN, date(year, 6, 30))
		make_company(OPEN, "STSO")
		cls.accounts = accounts = make_accounts(OPEN)
		post_ledger(
			OPEN,
			"Journal Entry",
			"STSO-2025-1",
			"2025-06-01",
			[(accounts["1800"], 1000, 0), (accounts["4400"], 0, 1000)],
		)
		post_ledger(
			OPEN,
			"Journal Entry",
			"STSO-2025-2",
			"2025-07-01",
			[(accounts["6300"], 400, 0), (accounts["1800"], 0, 400)],
		)

	def test_the_result_of_an_earlier_year_without_period_closing_voucher_is_the_earlier_result(self):
		found = balances.books(OPEN, "2026-01-01", "2026-12-31")
		self.assertEqual(found.earlier_result, Decimal("-600.00"))
		self.assertEqual(amounts(found), {"1800": euros("1000", "400")})

	def test_the_closing_account_is_among_the_balances_even_without_an_entry(self):
		found = balances.books(OPEN, "2026-01-01", "2026-12-31", closing_account=self.accounts["2970"])
		self.assertEqual(
			[balance for balance in found.balances if balance.account == self.accounts["2970"]],
			[
				AccountBalance(
					self.accounts["2970"], "2970", "Gewinnvortrag vor Verwendung", Part.BALANCE_SHEET
				)
			],
		)

	def test_the_closing_account_of_the_settings_comes_with_its_number(self):
		self.assertIsNone(balances.closing_account(OPEN))
		insert_record(balances.SETTINGS, name=OPEN, company=OPEN, closing_account=self.accounts["2970"])
		self.assertEqual(balances.closing_account(OPEN), (self.accounts["2970"], "2970"))
