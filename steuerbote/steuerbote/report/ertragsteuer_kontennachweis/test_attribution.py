"""The rows of the report Ertragsteuer-Kontennachweis, without a bench."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.kst import chain as kst_chain
from steuerbote.kst.categories import AccountRule, Category, Mapping
from steuerbote.steuerbote.doctype.corporate_income_tax_return.bridge import Ledger, Unnumbered
from steuerbote.steuerbote.report.ertragsteuer_kontennachweis import attribution
from steuerbote.ustva.calculation import LedgerLine

ZERO = Decimal("0")
MAPPING = Mapping(
	"SKR03",
	(
		AccountRule("2200", Category.KST),
		AccountRule("2110", Category.INTEREST),
		AccountRule("2655", Category.DIVIDENDS),
		AccountRule("4654", Category.ENTERTAINMENT_NONDEDUCTIBLE),
		AccountRule("4635", Category.GIFTS_NONDEDUCTIBLE),
	),
)
LINES = (
	LedgerLine("8400", ZERO, Decimal("50000.00"), "Sales Invoice:ACC-SINV-2026-00001"),
	LedgerLine("2200", Decimal("2500.00"), ZERO, "Journal Entry:ACC-JV-2026-00003"),
	LedgerLine("2200", Decimal("2500.00"), ZERO, "Journal Entry:ACC-JV-2026-00001"),
	LedgerLine("2200", ZERO, Decimal("200.00"), "Journal Entry:ACC-JV-2026-00002"),
	LedgerLine("2110", Decimal("1000.00"), ZERO, "Journal Entry:ACC-JV-2026-00004"),
	LedgerLine("2655", ZERO, Decimal("3000.00"), "Payment Entry:ACC-PAY-2026-00001"),
	LedgerLine("4654", Decimal("300.00"), ZERO, "Purchase Invoice:ACC-PINV-2026-00001"),
	LedgerLine("4635", Decimal("100.00"), ZERO, None),
)
LEDGER = Ledger(LINES, Decimal("46900.00"))
NAMES = {"2200": "2200 - Körperschaftsteuer - MIT", "8400": "8400 - Erlöse 19 % USt - MIT"}
DATES = {
	"Journal Entry:ACC-JV-2026-00001": date(2026, 3, 10),
	"Journal Entry:ACC-JV-2026-00002": date(2026, 6, 30),
	"Journal Entry:ACC-JV-2026-00003": date(2026, 6, 10),
}


def node(rows, name: str) -> dict:
	(found,) = (row for row in rows if row["node"] == name)
	return found


class ReportRowsTest(TestCase):
	def setUp(self):
		self.rows = attribution.report_rows(LEDGER, MAPPING, NAMES, DATES)

	def test_starts_with_the_jahresueberschuss_of_line_11_and_each_account(self):
		self.assertEqual(
			self.rows[0],
			{
				"node": "E8002001",
				"parent_node": None,
				"indent": 0,
				"line": "Anlage GK 11",
				"feldkennung": "E8002001",
				"label": kst_chain.step("net_income").label,
				"amount": Decimal("46900.00"),
				"bold": 1,
			},
		)
		accounts = [row for row in self.rows if row["parent_node"] == "E8002001"]
		self.assertEqual(
			[row["account"] for row in accounts],
			[
				"2110",
				"2200 - Körperschaftsteuer - MIT",
				"2655",
				"4635",
				"4654",
				"8400 - Erlöse 19 % USt - MIT",
			],
		)
		self.assertEqual(
			{key: accounts[1][key] for key in ("debit", "credit", "amount")},
			{"debit": Decimal("5000.00"), "credit": Decimal("200.00"), "amount": Decimal("-4800.00")},
		)

	def test_each_line_of_the_books_with_its_accounts_and_vouchers_by_day(self):
		line = node(self.rows, "E8100301")
		self.assertEqual(
			(line["line"], line["feldkennung"], line["amount"], line["indent"]),
			("Anlage GK 81", "E8100301", Decimal("4800.00"), 0),
		)
		vouchers = [row for row in self.rows if row["parent_node"] == "E8100301/2200"]
		self.assertEqual(
			[
				(row["posting_date"], row["voucher_type"], row["voucher_no"], row["amount"])
				for row in vouchers
			],
			[
				(date(2026, 3, 10), "Journal Entry", "ACC-JV-2026-00001", Decimal("2500.00")),
				(date(2026, 6, 10), "Journal Entry", "ACC-JV-2026-00003", Decimal("2500.00")),
				(date(2026, 6, 30), "Journal Entry", "ACC-JV-2026-00002", Decimal("-200.00")),
			],
		)
		self.assertEqual({row["indent"] for row in vouchers}, {2})

	def test_a_line_of_several_categories_takes_the_accounts_of_each(self):
		line = node(self.rows, "E8101301")
		self.assertEqual(line["amount"], Decimal("400.00"))
		self.assertEqual(
			[row["node"] for row in self.rows if row["parent_node"] == "E8101301"],
			["E8101301/4635", "E8101301/4654"],
		)
		(voucher,) = (row for row in self.rows if row["parent_node"] == "E8101301/4635")
		self.assertEqual(
			(voucher["posting_date"], voucher["voucher_type"], voucher["voucher_no"]), (None, None, None)
		)

	def test_each_set_of_categories_once_in_the_order_of_the_forms(self):
		lines = [row["node"] for row in self.rows if row["indent"] == 0]
		self.assertEqual(lines, ["E8002001", "E8100301", "E8101301", "E8560401", "E4003202"])
		self.assertEqual(node(self.rows, "E4003202")["line"], "GewSt 1 A 50")
		self.assertEqual(node(self.rows, "E8560401")["amount"], Decimal("3000.00"))

	def test_the_accounts_without_a_number_stand_together(self):
		ledger = Ledger(LINES, Decimal("46650.00"), (Unnumbered("Sonstiges - MIT", Decimal("-250.00")),))
		rows = attribution.report_rows(ledger, MAPPING, NAMES, DATES, str.upper)
		self.assertEqual(
			node(rows, "E8002001/-"),
			{
				"node": "E8002001/-",
				"parent_node": "E8002001",
				"indent": 1,
				"label": "ACCOUNTS WITHOUT A NUMBER",
				"amount": Decimal("-250.00"),
			},
		)
		self.assertNotIn("E8002001/-", [row["node"] for row in self.rows])

	def test_the_vouchers_whose_days_the_report_reads(self):
		self.assertEqual(
			attribution.vouchers(LEDGER),
			[
				"Journal Entry:ACC-JV-2026-00001",
				"Journal Entry:ACC-JV-2026-00002",
				"Journal Entry:ACC-JV-2026-00003",
				"Journal Entry:ACC-JV-2026-00004",
				"Payment Entry:ACC-PAY-2026-00001",
				"Purchase Invoice:ACC-PINV-2026-00001",
				"Sales Invoice:ACC-SINV-2026-00001",
			],
		)
