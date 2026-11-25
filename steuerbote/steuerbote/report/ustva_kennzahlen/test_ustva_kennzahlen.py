from collections.abc import Iterable
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.desk.query_report import run
from frappe.tests import IntegrationTestCase

from steuerbote import ustva
from steuerbote.steuerbote.doctype.vat_return.vat_return import settings_for
from steuerbote.steuerbote.report.ustva_kennzahlen import ustva_kennzahlen as report
from steuerbote.steuerbote.report.ustva_kennzahlen.ustva_kennzahlen import PARTY_FIELDS, execute
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)

# Files monthly, with Dauerfristverlängerung and a Sondervorauszahlung in 2026.
COMPANY = "Steuerbote Test Kennzahlenbericht GmbH"

# The SKR03 accounts of the month in VerifiedMonthTest of the core, an account for intra-community
# deliveries, a bank and a receivables account.
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"8338": ("Erlöse Drittland nicht steuerbar", "Income"),
	"8125": ("Steuerfreie innergemeinschaftliche Lieferungen", "Income"),
	"3123": ("Sonstige Leistungen EU 19 %", "Expense"),
	"1787": ("Umsatzsteuer nach § 13b UStG 19 %", "Liability"),
	"1577": ("Vorsteuer nach § 13b UStG 19 %", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1200": ("Bank", "Asset"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}

NO_CATALOGUE_2025 = "No comparison with {0}: Steuerbote has no Kennzahlen for 2025 yet."
MAPPING_DOES_NOT_FIT = "No comparison with {0}: the VAT Return Mapping does not fit the form of {1} ({2})."


def money(value) -> Decimal | None:
	return None if value is None else Decimal(str(value)).quantize(Decimal("0.01"))


def filters(period: int, **values) -> dict:
	return {"company": COMPANY, "year": 2026, "rhythm": "monthly", "period_index": period, **values}


def post_invoice(
	doctype: str,
	name: str,
	party: str,
	party_name: str | None,
	posting_date: str,
	rows: Iterable[tuple[str, float, float]],
) -> str:
	"""A submitted invoice as the report sees it: its header with the party and its GL Entries.

	Submitting a real invoice needs items, price lists and a chart of accounts with receivables and payables,
	none of which the report reads.
	"""
	party_field, party_name_field = PARTY_FIELDS[doctype]
	frappe.get_doc(
		{
			"doctype": doctype,
			"name": name,
			"company": COMPANY,
			"posting_date": posting_date,
			party_field: party,
			party_name_field: party_name,
			"docstatus": 1,
		}
	).db_insert()
	for account, debit, credit in rows:
		frappe.get_doc(
			{
				"doctype": "GL Entry",
				"company": COMPANY,
				"posting_date": posting_date,
				"account": account,
				"debit": debit,
				"credit": credit,
				"voucher_type": doctype,
				"voucher_no": name,
				"is_cancelled": 0,
				"is_opening": "No",
				"docstatus": 1,
			}
		).db_insert()
	return name


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
		# February, the previous period of March: a smaller sale, a slightly smaller service, the same
		# purchase and an intra-community delivery that March does not have.
		post_journal_entry(
			COMPANY, "2026-02-10", [(a["1400"], 952, 0), (a["8400"], 0, 800), (a["1776"], 0, 152)]
		)
		post_journal_entry(COMPANY, "2026-02-11", [(a["1400"], 1950, 0), (a["8336"], 0, 1950)])
		post_journal_entry(COMPANY, "2026-02-14", [(a["1576"], 95, 0), (a["1200"], 0, 95)])
		post_journal_entry(COMPANY, "2026-02-16", [(a["1400"], 800, 0), (a["8125"], 0, 800)])

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

		april = "2026-04-15"
		cls.invoice = post_invoice(
			"Sales Invoice",
			"SINV-STKZ-0001",
			"CUST-0001",
			"Kunde GmbH",
			april,
			[(a["1400"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)],
		)
		cls.invoice_without_name = post_invoice(
			"Sales Invoice",
			"SINV-STKZ-0002",
			"CUST-0002",
			None,
			april,
			[(a["1400"], 59.5, 0), (a["8400"], 0, 50), (a["1776"], 0, 9.5)],
		)
		cls.bill = post_invoice(
			"Purchase Invoice",
			"PINV-STKZ-0001",
			"SUPP-0001",
			"Lieferant AG",
			april,
			[(a["1576"], 19, 0), (a["1200"], 0, 19)],
		)

		# With the immutable ledger, ERPNext keeps the GL Entries of a cancelled voucher and posts their
		# reversal on the day of the cancellation: in May for the first entry, in June for the second. Both
		# reversals count on the day of their entry, in May, which no return has filed.
		cls.cancelled_in_may = post_journal_entry(
			COMPANY, "2026-05-12", [(a["1400"], 238, 0), (a["8400"], 0, 200), (a["1776"], 0, 38)]
		)
		cls.cancelled_in_june = post_journal_entry(
			COMPANY, "2026-05-14", [(a["1400"], 357, 0), (a["8400"], 0, 300), (a["1776"], 0, 57)]
		)
		with cls.change_settings("Accounts Settings", {"enable_immutable_ledger": 1}):
			with cls.freeze_time("2026-05-20 12:00:00"):
				cls.cancelled_in_may.cancel()
			with cls.freeze_time("2026-06-03 12:00:00"):
				cls.cancelled_in_june.cancel()

	def rows(self, period: int, **values) -> list[dict]:
		_columns, rows = execute(filters(period, **values))
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
				(0, None, None, None, None, None, None),
				(0, "81", 13, None, None, money(1000), money(1000)),
				(1, "81", None, self.sale.name, a["8400"], money(1000), None),
				(0, "41", 19, None, None, money(0), money(0)),
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

	def test_a_voucher_row_carries_its_type_date_postings_and_print_view(self):
		row = next(row for row in self.rows(3) if row["voucher_no"] == self.reverse_charge.name)
		self.assertEqual(
			(
				row["voucher_type"],
				str(row["posting_date"]),
				money(row["debit"]),
				money(row["credit"]),
				row["currency"],
				row["party"],
				row["print_link"],
			),
			(
				"Journal Entry",
				"2026-03-13",
				money(300),
				money(0),
				"EUR",
				None,
				f'<a href="/printview?doctype=Journal%20Entry&amp;name={self.reverse_charge.name}" '
				'target="_blank">Print</a>',
			),
		)

	def test_an_invoice_names_its_customer_or_supplier(self):
		vouchers = {row["voucher_no"]: row for row in self.rows(4) if row["indent"]}
		self.assertEqual(
			{name: (row["voucher_type"], row["party"]) for name, row in vouchers.items()},
			{
				self.invoice: ("Sales Invoice", "Kunde GmbH"),
				self.invoice_without_name: ("Sales Invoice", "CUST-0002"),
				self.bill: ("Purchase Invoice", "Lieferant AG"),
			},
		)
		self.assertEqual(
			vouchers[self.bill]["print_link"],
			'<a href="/printview?doctype=Purchase%20Invoice&amp;name=PINV-STKZ-0001" target="_blank">Print</a>',
		)

	def test_compares_each_kennzahl_and_sum_with_the_previous_period(self):
		self.assertEqual(
			[
				(
					row["kennzahl"],
					row["line"],
					money(row["previous_period"]),
					money(row["previous_year"]),
					money(row["difference"]),
				)
				for row in self.rows(3)
				if not row["indent"]
			],
			[
				(None, None, None, None, None),
				("81", 13, money(800), None, money(200)),
				("41", 19, money(800), None, money(-800)),
				("46", 30, money(0), None, money(300)),
				("47", 30, money(0), None, money(57)),
				("21", 35, money(1950), None, money(50)),
				("45", 36, money(0), None, money(500)),
				(None, 37, money(152), None, money(95)),
				("66", 38, money(95), None, money(0)),
				("67", 41, money(0), None, money(57)),
				(None, 45, money(57), None, money(38)),
				(None, 48, money(57), None, money(38)),
				("83", 50, money(57), None, money(38)),
			],
		)

	def test_a_year_without_kennzahlen_leaves_its_comparison_empty_with_a_note(self):
		march = self.rows(3)
		self.assertEqual(march[0]["label"], NO_CATALOGUE_2025.format("März 2025"))
		january = self.rows(1)
		self.assertEqual(
			[row["label"] for row in january[:2]],
			[NO_CATALOGUE_2025.format("Dezember 2025"), NO_CATALOGUE_2025.format("Januar 2025")],
		)
		self.assertEqual(
			{(row["previous_period"], row["previous_year"], row["difference"]) for row in january},
			{(None, None, None)},
		)
		self.assertEqual(self.rows(1, only_deviations=1), january)

	def test_a_mapping_that_does_not_fit_a_compared_year_leaves_its_comparison_empty(self):
		reason = "account 8400: unknown Kennzahl 81"
		with patch.object(ustva.Mapping, "for_year", side_effect=ustva.MappingError(reason)):
			rows = self.rows(3)
		self.assertEqual(
			[row["label"] for row in rows[:2]],
			[
				MAPPING_DOES_NOT_FIT.format("Februar 2026", 2026, reason),
				MAPPING_DOES_NOT_FIT.format("März 2025", 2025, reason),
			],
		)
		self.assertEqual({row["previous_period"] for row in rows}, {None})

	def test_only_deviations_keeps_the_kennzahlen_beyond_both_default_thresholds(self):
		self.assertEqual(
			[
				(row["indent"], row["kennzahl"], row["line"], row["voucher_no"])
				for row in self.rows(3, only_deviations=1)
			],
			[
				(0, None, None, None),
				(0, "41", 19, None),
				(0, "46", 30, None),
				(1, "46", None, self.reverse_charge.name),
				(0, "45", 36, None),
				(1, "45", None, self.export.name),
			],
		)

	def test_only_deviations_takes_the_thresholds_of_the_settings(self):
		settings = settings_for(COMPANY)
		settings.comparison_threshold_percent = 10
		settings.comparison_threshold_amount = 30
		with patch.object(report, "settings_for", return_value=settings):
			rows = self.rows(3, only_deviations=1)
		self.assertEqual(
			[(row["kennzahl"], row["line"]) for row in rows if not row["indent"]],
			[
				(None, None),
				("81", 13),
				("41", 19),
				("46", 30),
				("47", 30),
				("45", 36),
				(None, 37),
				("67", 41),
				(None, 45),
				(None, 48),
				("83", 50),
			],
		)

	def test_leaves_out_the_cancelled_and_the_excluded_journal_entry(self):
		vouchers = {row["voucher_no"] for row in self.rows(3)}
		self.assertNotIn(self.cancelled.name, vouchers)
		self.assertNotIn(self.settlement.name, vouchers)

	def test_a_voucher_cancelled_before_its_month_is_filed_shows_in_no_month(self):
		"""With the immutable ledger, the reversal of a voucher cancelled in a later month counts on the voucher's day:
		neither the month of the voucher nor that of the cancellation reports it."""
		for period in (5, 6):
			rows = self.rows(period)
			with self.subTest(period=period):
				vouchers = {row["voucher_no"] for row in rows}
				self.assertNotIn(self.cancelled_in_may.name, vouchers)
				self.assertNotIn(self.cancelled_in_june.name, vouchers)
				kennzahl = next((row for row in rows if row["kennzahl"] == "81" and not row["indent"]), {})
				self.assertEqual(money(kennzahl.get("reported") or 0), money(0))

	def test_december_deducts_the_sondervorauszahlung(self):
		self.assertEqual(
			[(row["kennzahl"], row["line"], money(row["reported"])) for row in self.rows(12)],
			[
				(None, None, None),
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
		result = run("UStVA Kennzahlen", filters=filters(3), is_tree=True, parent_field="parent_kennzahl")
		self.assertEqual(frappe.db.get_value("Report", "UStVA Kennzahlen", "ref_doctype"), "VAT Return")
		balance = next(row for row in result["result"] if row["kennzahl"] == "83")
		self.assertEqual(money(balance["reported"]), money(95))
		self.assertEqual(
			[column["fieldname"] for column in result["columns"]],
			[
				"kennzahl",
				"line",
				"label",
				"posting_date",
				"voucher_type",
				"voucher_no",
				"print_link",
				"party",
				"account",
				"debit",
				"credit",
				"amount",
				"reported",
				"previous_period",
				"previous_year",
				"difference",
				"currency",
			],
		)
		voucher_no = next(column for column in result["columns"] if column["fieldname"] == "voucher_no")
		self.assertEqual((voucher_no["fieldtype"], voucher_no["options"]), ("Dynamic Link", "voucher_type"))
