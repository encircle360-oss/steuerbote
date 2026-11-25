"""The report Ertragsteuer-Kontennachweis on the Frappe test site, with the ledger of the worked example „Muster IT
GmbH“ of steuerbote/tests/income_tax.py: Anlage GK line 11 with the balance of each account, and each line of the forms
whose amount comes from the Income Tax Mapping with the accounts and vouchers behind it."""

from datetime import date
from decimal import Decimal

from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from steuerbote.steuerbote.report.ertragsteuer_kontennachweis.ertragsteuer_kontennachweis import execute
from steuerbote.tests import income_tax
from steuerbote.tests.income_tax import COMPANY, YEAR, money

COLUMNS = [
	"line",
	"feldkennung",
	"label",
	"amount",
	"account",
	"posting_date",
	"voucher_type",
	"voucher_no",
	"debit",
	"credit",
	"currency",
]


def d(value: str) -> Decimal:
	return Decimal(value)


class TestErtragsteuerKontennachweis(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.account = income_tax.make_muster_it_gmbh()

	def setUp(self):
		columns, self.rows = execute({"company": COMPANY, "year": str(YEAR)})
		self.assertEqual([column["fieldname"] for column in columns], COLUMNS)
		self.by_node = {row["node"]: row for row in self.rows}

	def test_starts_with_line_11_and_the_balance_of_each_account_of_the_profit_and_loss_account(self):
		first = self.rows[0]
		self.assertEqual(
			(
				first["node"],
				first["parent_node"],
				first["line"],
				first["feldkennung"],
				money(first["amount"]),
			),
			("E8002001", None, "Anlage GK 11", "E8002001", d("88175.00")),
		)
		accounts = [row for row in self.rows if row["parent_node"] == "E8002001"]
		self.assertEqual(len(accounts), 24)
		revenue = self.by_node["E8002001/8400"]
		self.assertEqual(
			(revenue["account"], money(revenue["credit"]), money(revenue["amount"])),
			(self.account["8400"], d("220000.00"), d("220000.00")),
		)
		self.assertEqual(money(self.by_node["E8002001/2200"]["amount"]), d("-10000.00"))
		self.assertEqual({row["currency"] for row in self.rows}, {"EUR"})

	def test_shows_the_vouchers_behind_a_line_with_their_posting_dates(self):
		line = self.by_node["E8100301"]
		self.assertEqual(
			(line["line"], line["feldkennung"], line["indent"], money(line["amount"])),
			("Anlage GK 81", "E8100301", 0, d("10000.00")),
		)
		vouchers = [row for row in self.rows if row["parent_node"] == "E8100301/2200"]
		self.assertEqual(
			[
				(getdate(row["posting_date"]), row["voucher_type"], row["voucher_no"], money(row["debit"]))
				for row in vouchers
			],
			[
				(date(2026, month, 10), "Journal Entry", f"JV-STMIT-VZ-KST-{quarter}", d("2500.00"))
				for quarter, month in ((1, 3), (2, 6), (3, 9), (4, 12))
			],
		)
		self.assertTrue(all(row["account"] == self.account["2200"] for row in vouchers))

	def test_shows_the_lines_of_the_gewerbesteuer_that_come_from_the_mapping(self):
		rent = self.by_node["E4003602"]
		self.assertEqual((rent["line"], money(rent["amount"])), ("GewSt 1 A 55", d("24000.00")))
		self.assertEqual(self.by_node["E4003602/4210"]["account"], self.account["4210"])

	def test_without_a_company_or_a_year_it_shows_its_columns_alone(self):
		for filters in ({"company": COMPANY}, {"year": str(YEAR)}, None):
			with self.subTest(filters=filters):
				columns, rows = execute(filters)
				self.assertEqual(([column["fieldname"] for column in columns], rows), (COLUMNS, []))
