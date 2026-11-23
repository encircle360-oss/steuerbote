"""What the Körperschaft- and the Gewerbesteuererklärung read from ERPNext (steuerbote/income_tax_sources.py): the
profit and loss account of the Wirtschaftsjahr without the entries ERPNext flags as cancelled, the opening entries, the
Period Closing Voucher and the entries of another Finanzbuch; the accounts without a number; the Vorauszahlungen booked
and the provisions and refunds already posted; the posting dates of the vouchers; the Income Tax Mapping; and the
Annual Filing Settings with the company, its Steuerberatung of the year and the day of the review. Every name and
amount is invented."""

from datetime import date
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import income_tax_sources
from steuerbote.kst.categories import Category
from steuerbote.kst.provisions import ACCOUNTS as PROVISION_ACCOUNTS
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge
from steuerbote.tests import income_tax
from steuerbote.tests.helpers import (
	cancel_voucher,
	ensure_fiscal_year,
	insert_record,
	make_account,
	make_company,
	make_settings,
	post_ledger,
)
from steuerbote.ustva.calculation import LedgerLine

COMPANY = "Steuerbote Test Ertragsteuern Quellen GmbH"
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"4120": ("Gehälter", "Expense"),
	"2200": ("Körperschaftsteuer", "Expense"),
	"2208": ("Solidaritätszuschlag", "Expense"),
	"4320": ("Gewerbesteuer", "Expense"),
	"0963": ("Körperschaftsteuerrückstellung", "Liability"),
	"1540": ("Forderungen aus Gewerbesteuerüberzahlungen", "Asset"),
	"1200": ("Bank", "Asset"),
	"0860": ("Gewinnvortrag vor Verwendung", "Equity"),
}
UNNUMBERED = "Erlöse ohne Kontonummer"
# The Finanzbuch of the Handelsbilanz, whose entries count where the settings name it, and one of another book.
COMMERCIAL_BOOK = "Steuerbote Test Handelsbilanz"
OTHER_BOOK = "Steuerbote Test Steuerbilanz"
WID_NR = "DE123456789"
FROM, TO = date(2026, 1, 1), date(2026, 12, 31)
SKR03 = PROVISION_ACCOUNTS["SKR03"]


def d(value: str) -> Decimal:
	return Decimal(value)


def line(account: str, debit: str, credit: str, voucher: str) -> LedgerLine:
	return LedgerLine(account, d(debit), d(credit), voucher)


class TestIncomeTaxSources(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STEQ")
		a = cls.account = income_tax.make_accounts(COMPANY, ACCOUNTS)
		cls.unnumbered = frappe.db.get_value(
			"Account", {"company": COMPANY, "account_name": UNNUMBERED}
		) or make_account(COMPANY, None, UNNUMBERED, "Income")
		for year in (2025, 2026, 2027):
			ensure_fiscal_year(COMPANY, date(year, 6, 30))
		for book in (COMMERCIAL_BOOK, OTHER_BOOK):
			if not frappe.db.exists("Finance Book", book):
				frappe.get_doc({"doctype": "Finance Book", "finance_book_name": book}).insert(
					ignore_permissions=True
				)
		if frappe.db.exists("GL Entry", {"company": COMPANY}):
			return
		for voucher_type, voucher_no, posting_date, rows in (
			("Sales Invoice", "SINV-STEQ-1", "2026-03-01", [(a["8400"], 0, 1000), (a["1200"], 1000, 0)]),
			("Sales Invoice", "SINV-STEQ-0", "2025-12-31", [(a["8400"], 0, 500), (a["1200"], 500, 0)]),
			("Sales Invoice", "SINV-STEQ-2", "2027-01-02", [(a["8400"], 0, 700), (a["1200"], 700, 0)]),
			("Journal Entry", "JV-STEQ-OHNE", "2026-04-01", [(cls.unnumbered, 0, 250), (a["1200"], 250, 0)]),
			(
				"Journal Entry",
				"JV-STEQ-VZ",
				"2026-03-10",
				[(a["2200"], 2500, 0), (a["2208"], "137.50", 0), (a["1200"], 0, "2637.50")],
			),
			("Journal Entry", "JV-STEQ-RST", "2026-12-31", [(a["2200"], 1680, 0), (a["0963"], 0, 1680)]),
			("Journal Entry", "JV-STEQ-ERST", "2026-12-31", [(a["1540"], 300, 0), (a["4320"], 0, 300)]),
			("Journal Entry", "JV-STEQ-STORNO", "2026-05-10", [(a["4120"], 400, 0), (a["1200"], 0, 400)]),
			(
				"Period Closing Voucher",
				"PCV-STEQ-2026",
				"2026-12-31",
				[(a["8400"], 1000, 0), (a["0860"], 0, 1000)],
			),
		):
			post_ledger(COMPANY, voucher_type, voucher_no, posting_date, rows)
		cancel_voucher("Journal Entry", "JV-STEQ-STORNO")
		for voucher_no, account, amount, fields in (
			("JV-STEQ-EB", a["4120"], 300, {"is_opening": "Yes"}),
			("JV-STEQ-HB", a["4120"], 200, {"is_opening": "No", "finance_book": COMMERCIAL_BOOK}),
			("JV-STEQ-STB", a["4120"], 900, {"is_opening": "No", "finance_book": OTHER_BOOK}),
		):
			for posted, debit, credit in ((account, amount, 0), (a["1200"], 0, amount)):
				insert_record(
					"GL Entry",
					company=COMPANY,
					posting_date="2026-06-30",
					account=posted,
					debit=debit,
					credit=credit,
					voucher_type="Journal Entry",
					voucher_no=voucher_no,
					is_cancelled=0,
					docstatus=1,
					**fields,
				)

	def test_reads_the_profit_and_loss_account_of_the_wirtschaftsjahr_by_account_and_voucher(self):
		ledger = income_tax_sources.ledger(COMPANY, FROM, TO, SKR03, None)
		self.assertEqual(
			list(ledger.lines),
			[
				line("2200", "1680.00", "0", "Journal Entry:JV-STEQ-RST"),
				line("2200", "2500.00", "0", "Journal Entry:JV-STEQ-VZ"),
				line("2208", "137.50", "0", "Journal Entry:JV-STEQ-VZ"),
				line("4320", "0", "300.00", "Journal Entry:JV-STEQ-ERST"),
				line("8400", "0", "1000.00", "Sales Invoice:SINV-STEQ-1"),
			],
		)
		self.assertEqual(ledger.net_income, d("-2767.50"))

	def test_an_account_without_a_number_counts_in_the_jahresueberschuss_and_is_named(self):
		ledger = income_tax_sources.ledger(COMPANY, FROM, TO, SKR03, None)
		self.assertEqual(ledger.unnumbered, (bridge.Unnumbered(self.unnumbered, d("250.00")),))

	def test_the_entries_of_the_finanzbuch_of_the_handelsbilanz_count_and_those_of_another_do_not(self):
		ledger = income_tax_sources.ledger(COMPANY, FROM, TO, SKR03, COMMERCIAL_BOOK)
		self.assertIn(line("4120", "200.00", "0", "Journal Entry:JV-STEQ-HB"), ledger.lines)
		self.assertEqual(
			[entry.voucher for entry in ledger.lines if entry.account_number == "4120"],
			["Journal Entry:JV-STEQ-HB"],
		)
		self.assertEqual(ledger.net_income, d("-2967.50"))

	def test_tells_the_vorauszahlungen_booked_from_the_provisions_and_refunds_posted(self):
		"""A voucher that touches the Rückstellung or the claim to a refund of a tax books no Vorauszahlung."""
		ledger = income_tax_sources.ledger(COMPANY, FROM, TO, SKR03, None)
		self.assertEqual(
			dict(ledger.booked_prepayments), {"KSt": d("2500.00"), "SolZ": d("137.50"), "GewSt": d("0")}
		)
		postings = income_tax_sources.tax_postings(COMPANY, FROM, TO, SKR03, None)
		self.assertEqual(
			sorted(
				(posting.voucher, posting.account_number, posting.debit, posting.credit)
				for posting in postings
			),
			[
				("Journal Entry:JV-STEQ-ERST", "1540", d("300.00"), d("0.00")),
				("Journal Entry:JV-STEQ-ERST", "4320", d("0.00"), d("300.00")),
				("Journal Entry:JV-STEQ-RST", "0963", d("0.00"), d("1680.00")),
				("Journal Entry:JV-STEQ-RST", "2200", d("1680.00"), d("0.00")),
				("Journal Entry:JV-STEQ-VZ", "2200", d("2500.00"), d("0.00")),
				("Journal Entry:JV-STEQ-VZ", "2208", d("137.50"), d("0.00")),
			],
		)
		_, posted = bridge.booked_taxes(postings, SKR03)
		self.assertEqual(posted, {"KSt": d("1680.00"), "SolZ": d("0"), "GewSt": d("-300.00")})

	def test_a_chart_of_its_own_names_no_account_of_the_vorauszahlungen(self):
		ledger = income_tax_sources.ledger(COMPANY, FROM, TO, None, None)
		self.assertIsNone(ledger.booked_prepayments)
		self.assertEqual(ledger.net_income, d("-2767.50"))

	def test_reads_the_posting_date_of_each_voucher(self):
		self.assertEqual(
			income_tax_sources.posting_dates(
				COMPANY,
				["Journal Entry:JV-STEQ-VZ", "Sales Invoice:SINV-STEQ-1", "Journal Entry:JV-STEQ-UNBEKANNT"],
			),
			{"Journal Entry:JV-STEQ-VZ": date(2026, 3, 10), "Sales Invoice:SINV-STEQ-1": date(2026, 3, 1)},
		)
		self.assertEqual(income_tax_sources.posting_dates(COMPANY, []), {})

	def test_reads_the_income_tax_mapping_of_the_company(self):
		with self.assertRaisesRegex(frappe.ValidationError, f"{COMPANY} has no Income Tax Mapping"):
			income_tax_sources.mapping(COMPANY)
		income_tax.make_income_tax_mapping(COMPANY)
		mapping = income_tax_sources.mapping(COMPANY)
		self.assertEqual((mapping.chart, mapping.rule_for("2200").category), ("SKR03", Category.KST))

	def test_reads_the_annual_filing_settings_with_the_company_and_its_steuerberatung_of_the_year(self):
		self.assertIsNone(income_tax_sources.settings(COMPANY, 2026))
		self.assertIsNone(income_tax_sources.commercial_finance_book(COMPANY))
		if not frappe.db.exists("VAT Return Settings", COMPANY):
			make_settings(COMPANY, [(2026, "monthly", 1)], wid_nr=WID_NR)
		frappe.db.set_value("Company", COMPANY, "date_of_establishment", "2020-03-01")
		frappe.get_doc(
			{
				"doctype": "Annual Filing Settings",
				"company": COMPANY,
				"legal_form": "UG",
				"business_purpose": "Beratung",
				"management_seat": "Musterstadt",
				"registered_seat": "Beispielhausen",
				"commercial_finance_book": COMMERCIAL_BOOK,
				"income_tax_review_on": "2026-11-02",
				"advisor_name": "Steuerkanzlei Beispiel",
				"advisor_client_number": "4711",
				"years": [{"year": 2026, "advisor_prepares": 1}],
				"shareholders": [{**income_tax.SHAREHOLDER}],
				"holdings": [{"holding_name": "Beta GmbH", "year": 2026, "percent_on_1_january": 12}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Annual Filing Settings", COMPANY, force=True)
		settings = income_tax_sources.settings(COMPANY, 2026)
		company = settings.company
		self.assertEqual(
			(
				company.name,
				company.rechtsform,
				company.management_seat,
				company.registered_seat,
				company.wid_nr,
				company.business_purpose,
				company.founded_on,
				company.section_8b_7,
				company.accounting_standard,
			),
			(
				COMPANY,
				"370",
				"Musterstadt",
				"Beispielhausen",
				WID_NR,
				"Beratung",
				date(2020, 3, 1),
				False,
				"HAOE",
			),
		)
		self.assertEqual(
			(company.advisor.name, company.advisor.client_number), ("Steuerkanzlei Beispiel", "4711")
		)
		self.assertEqual([shareholder.name for shareholder in settings.shareholders], ["Erika Musterfrau"])
		self.assertEqual(
			[(holding.name, holding.year) for holding in settings.holdings], [("Beta GmbH", 2026)]
		)
		self.assertEqual(settings.reviewed_on, date(2026, 11, 2))
		self.assertIsNone(income_tax_sources.settings(COMPANY, 2027).company.advisor)
		frappe.db.set_value("Annual Filing Settings", COMPANY, "income_tax_review_on", None)
		self.assertIsNone(income_tax_sources.settings(COMPANY, 2026).reviewed_on)
		self.assertEqual(income_tax_sources.commercial_finance_book(COMPANY), COMMERCIAL_BOOK)
