from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.ledger import EXCLUDE_FIELD, account_names, accounts_without_number, load_lines
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)
from steuerbote.ustva import LedgerLine, Period, calculate

COMPANY = "Steuerbote Test Hauptbuch GmbH"
NEIGHBOUR = "Steuerbote Test Hauptbuch Nachbar GmbH"


def lines_of(voucher: str, *lines: tuple[str, str, str]) -> list[LedgerLine]:
	return [LedgerLine(account, Decimal(debit), Decimal(credit), voucher) for account, debit, credit in lines]


class LedgerTest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STHB")
		cls.revenue = make_account(COMPANY, "8400", "Erlöse 19 % USt", "Income")
		cls.output_tax = make_account(COMPANY, "1776", "Umsatzsteuer 19 %", "Liability")
		cls.bank = make_account(COMPANY, "1200", "Bank", "Asset")
		cls.cash = make_account(COMPANY, None, "Kasse", "Asset")
		make_settings(COMPANY, [(2026, "monthly", 1)])
		cls.mapping = make_mapping(COMPANY)
		make_company(NEIGHBOUR, "STHN")
		cls.neighbour_revenue = make_account(NEIGHBOUR, "8400", "Erlöse 19 % USt", "Income")
		cls.neighbour_bank = make_account(NEIGHBOUR, "1200", "Bank", "Asset")

	def test_sums_each_account_per_voucher_in_cents(self):
		entry = post_journal_entry(
			COMPANY,
			"2026-01-15",
			[
				(self.bank, "1191.18", 0),
				(self.revenue, 0, "600.59"),
				(self.revenue, 0, "400.40"),
				(self.output_tax, 0, "190.19"),
			],
		)
		lines = load_lines(COMPANY, "2026-01-01", "2026-01-31")
		self.assertEqual(
			lines,
			lines_of(
				f"Journal Entry:{entry.name}",
				("1200", "1191.18", "0"),
				("1776", "0", "190.19"),
				("8400", "0", "1000.99"),
			),
		)
		self.assertEqual([str(line.credit) for line in lines], ["0.00", "190.19", "1000.99"])

	def test_orders_the_vouchers_by_posting_date(self):
		later = post_journal_entry(COMPANY, "2026-09-20", [(self.bank, 10, 0), (self.revenue, 0, 10)])
		earlier = post_journal_entry(COMPANY, "2026-09-05", [(self.bank, 20, 0), (self.revenue, 0, 20)])
		vouchers = [line.voucher for line in load_lines(COMPANY, "2026-09-01", "2026-09-30")]
		self.assertEqual(
			vouchers,
			[f"Journal Entry:{name}" for name in (earlier.name, earlier.name, later.name, later.name)],
		)

	def test_leaves_out_cancelled_entries_and_their_reversals(self):
		entry = post_journal_entry(COMPANY, "2026-02-10", [(self.bank, 119, 0), (self.revenue, 0, 119)])
		entry.cancel()
		self.assertEqual(load_lines(COMPANY, "2026-02-01", "2026-02-28"), [])

	def test_leaves_out_journal_entries_excluded_from_the_return(self):
		kept = post_journal_entry(COMPANY, "2026-03-10", [(self.bank, 50, 0), (self.revenue, 0, 50)])
		excluded = post_journal_entry(
			COMPANY, "2026-03-31", [(self.output_tax, 190, 0), (self.bank, 0, 190)], exclude=True
		)
		self.assertEqual(frappe.db.get_value("Journal Entry", excluded.name, EXCLUDE_FIELD), 1)
		self.assertEqual(
			load_lines(COMPANY, "2026-03-01", "2026-03-31"),
			lines_of(f"Journal Entry:{kept.name}", ("1200", "50", "0"), ("8400", "0", "50")),
		)

	def test_leaves_out_opening_entries(self):
		post_journal_entry(
			COMPANY,
			"2026-04-01",
			[(self.bank, 500, 0), (self.output_tax, 0, 500)],
			voucher_type="Opening Entry",
		)
		self.assertEqual(load_lines(COMPANY, "2026-04-01", "2026-04-30"), [])

	def test_leaves_out_period_closing_vouchers(self):
		# Submitting a Period Closing Voucher would close 2026 for every other test; its GL Entries are
		# all the query sees of it.
		closing = frappe.new_doc("GL Entry")
		closing.update(
			{
				"name": frappe.generate_hash(length=10),
				"company": COMPANY,
				"posting_date": "2026-05-31",
				"account": self.revenue,
				"debit": 1000,
				"credit": 0,
				"voucher_type": "Period Closing Voucher",
				"voucher_no": "STHB-PCV-2026",
				"is_opening": "No",
				"is_cancelled": 0,
				"docstatus": 1,
			}
		)
		closing.db_insert()
		self.assertEqual(load_lines(COMPANY, "2026-05-01", "2026-05-31"), [])

	def test_reads_the_company_and_the_dates_asked_for(self):
		inside = post_journal_entry(COMPANY, "2026-06-30", [(self.bank, 30, 0), (self.revenue, 0, 30)])
		post_journal_entry(COMPANY, "2026-07-01", [(self.bank, 40, 0), (self.revenue, 0, 40)])
		post_journal_entry(
			NEIGHBOUR, "2026-06-15", [(self.neighbour_bank, 60, 0), (self.neighbour_revenue, 0, 60)]
		)
		self.assertEqual(
			load_lines(COMPANY, "2026-06-01", "2026-06-30"),
			lines_of(f"Journal Entry:{inside.name}", ("1200", "30", "0"), ("8400", "0", "30")),
		)

	def test_skips_accounts_without_number_and_lists_them(self):
		entry = post_journal_entry(COMPANY, "2026-08-12", [(self.cash, 100, 0), (self.revenue, 0, 100)])
		self.assertEqual(
			load_lines(COMPANY, "2026-08-01", "2026-08-31"),
			lines_of(f"Journal Entry:{entry.name}", ("8400", "0", "100")),
		)
		self.assertEqual(accounts_without_number(COMPANY), [self.cash])

	def test_reads_only_the_accounts_asked_for(self):
		entry = post_journal_entry(
			COMPANY, "2026-11-12", [(self.bank, 119, 0), (self.revenue, 0, 100), (self.output_tax, 0, 19)]
		)
		self.assertEqual(
			load_lines(COMPANY, "2026-11-01", "2026-11-30", account_numbers=["8400", "9999"]),
			lines_of(f"Journal Entry:{entry.name}", ("8400", "0", "100")),
		)
		self.assertEqual(load_lines(COMPANY, "2026-11-01", "2026-11-30", account_numbers=[]), [])
		self.assertEqual(len(load_lines(COMPANY, "2026-11-01", "2026-11-30")), 3)

	def test_account_names_by_number(self):
		self.assertEqual(
			account_names(COMPANY, ["8400", "1776", "9999"]), {"8400": self.revenue, "1776": self.output_tax}
		)
		self.assertEqual(account_names(COMPANY, []), {})

	def test_the_lines_of_a_period_meet_the_mapping_of_the_company(self):
		post_journal_entry(
			COMPANY, "2026-10-05", [(self.bank, 119, 0), (self.revenue, 0, 100), (self.output_tax, 0, 19)]
		)
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		period = Period(2026, settings.rhythm_for(2026, 10), 10)
		result = calculate(load_lines(COMPANY, period.start, period.end), self.mapping.to_mapping(2026))
		self.assertEqual((result.reported("81"), result.kz83), (Decimal("100"), Decimal("19.00")))
		self.assertEqual([check.label for check in result.checks], ["Umsatzsteuer 19 %"])
		self.assertTrue(result.ready)
