from decimal import Decimal

import frappe
from frappe.desk.query_report import run
from frappe.tests import IntegrationTestCase

from steuerbote.steuerbote.report.ustva_kennzahlen.ustva_kennzahlen import execute
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)

# Files monthly, with Dauerfristverlängerung and a Sondervorauszahlung in 2026.
COMPANY = "Steuerbote Test Kennzahlenbericht GmbH"

# The SKR03 accounts of the month in VerifiedMonthTest of the core, a bank and a receivables account.
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"8338": ("Erlöse Drittland nicht steuerbar", "Income"),
	"3123": ("Sonstige Leistungen EU 19 %", "Expense"),
	"1787": ("Umsatzsteuer nach § 13b UStG 19 %", "Liability"),
	"1577": ("Vorsteuer nach § 13b UStG 19 %", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1200": ("Bank", "Asset"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}


def money(value) -> Decimal | None:
	return None if value is None else Decimal(str(value)).quantize(Decimal("0.01"))


def filters(period: int, **values) -> dict:
	return {"company": COMPANY, "year": 2026, "rhythm": "monthly", "period_index": period, **values}


class TestUStVAKennzahlen(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STKZ")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)], [(2026, True, "1200.00")])
		make_mapping(COMPANY)

		a = cls.account
		march = "2026-03-10"
		cls.sale = post_journal_entry(
			COMPANY, march, [(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)]
		)
		cls.service = post_journal_entry(COMPANY, "2026-03-11", [(a["1400"], 2000, 0), (a["8336"], 0, 2000)])
		cls.export = post_journal_entry(COMPANY, "2026-03-12", [(a["1400"], 500, 0), (a["8338"], 0, 500)])
		cls.reverse_charge = post_journal_entry(
			COMPANY,
			"2026-03-13",
			[(a["3123"], 300, 0), (a["1577"], 57, 0), (a["1787"], 0, 57), (a["1200"], 0, 300)],
		)
		cls.purchase = post_journal_entry(COMPANY, "2026-03-14", [(a["1576"], 95, 0), (a["1200"], 0, 95)])
		cls.cancelled = post_journal_entry(
			COMPANY, "2026-03-20", [(a["1400"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)]
		)
		cls.cancelled.cancel()
		cls.settlement = post_journal_entry(
			COMPANY, "2026-03-31", [(a["1776"], 190, 0), (a["1200"], 0, 190)], exclude=True
		)

	def rows(self, period: int) -> list[dict]:
		_columns, rows = execute(filters(period))
		return rows

	def test_shows_each_kennzahl_with_the_vouchers_behind_it(self):
		a = self.account
		self.assertEqual(
			[
				(
					row["indent"],
					row["kennzahl"],
					row["line"],
					row["voucher_no"],
					row["account"],
					money(row["amount"]),
					money(row["reported"]),
				)
				for row in self.rows(3)
			],
			[
				(0, "81", 13, None, None, money(1000), money(1000)),
				(1, "81", None, self.sale.name, a["8400"], money(1000), None),
				(0, "46", 30, None, None, money(300), money(300)),
				(1, "46", None, self.reverse_charge.name, a["3123"], money(300), None),
				(0, "47", 30, None, None, money(57), money(57)),
				(1, "47", None, self.reverse_charge.name, a["3123"], money(57), None),
				(0, "21", 35, None, None, money(2000), money(2000)),
				(1, "21", None, self.service.name, a["8336"], money(2000), None),
				(0, "45", 36, None, None, money(500), money(500)),
				(1, "45", None, self.export.name, a["8338"], money(500), None),
				(0, None, 37, None, None, None, money(247)),
				(0, "66", 38, None, None, money(95), money(95)),
				(1, "66", None, self.purchase.name, a["1576"], money(95), None),
				(0, "67", 41, None, None, money(57), money(57)),
				(1, "67", None, self.reverse_charge.name, a["1577"], money(57), None),
				(0, None, 45, None, None, None, money(95)),
				(0, None, 48, None, None, None, money(95)),
				(0, "83", 50, None, None, money(95), money(95)),
			],
		)

	def test_a_voucher_row_carries_its_type_date_and_postings(self):
		row = next(row for row in self.rows(3) if row["voucher_no"] == self.reverse_charge.name)
		self.assertEqual(
			(
				row["voucher_type"],
				str(row["posting_date"]),
				money(row["debit"]),
				money(row["credit"]),
				row["currency"],
			),
			("Journal Entry", "2026-03-13", money(300), money(0), "EUR"),
		)

	def test_leaves_out_the_cancelled_and_the_excluded_journal_entry(self):
		vouchers = {row["voucher_no"] for row in self.rows(3)}
		self.assertNotIn(self.cancelled.name, vouchers)
		self.assertNotIn(self.settlement.name, vouchers)

	def test_december_deducts_the_sondervorauszahlung(self):
		self.assertEqual(
			[(row["kennzahl"], row["line"], money(row["reported"])) for row in self.rows(12)],
			[
				(None, 37, money(0)),
				(None, 45, money(0)),
				(None, 48, money(0)),
				("39", 49, money(1200)),
				("83", 50, money(-1200)),
			],
		)

	def test_a_period_number_that_does_not_exist_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "there is no Voranmeldungszeitraum 13"):
			execute(filters(13))

	def test_without_all_filters_the_report_is_empty(self):
		columns, rows = execute({"company": COMPANY, "year": 2026, "rhythm": "monthly"})
		self.assertEqual(
			([column["fieldname"] for column in columns][:3], rows), (["kennzahl", "line", "label"], [])
		)

	def test_runs_as_the_installed_tree_report(self):
		report = run("UStVA Kennzahlen", filters=filters(3), is_tree=True, parent_field="parent_kennzahl")
		self.assertEqual(frappe.db.get_value("Report", "UStVA Kennzahlen", "ref_doctype"), "VAT Return")
		balance = next(row for row in report["result"] if row["kennzahl"] == "83")
		self.assertEqual(money(balance["reported"]), money(95))
		self.assertEqual(
			[column["fieldname"] for column in report["columns"]],
			[
				"kennzahl",
				"line",
				"label",
				"posting_date",
				"voucher_type",
				"voucher_no",
				"account",
				"debit",
				"credit",
				"amount",
				"reported",
				"currency",
			],
		)
