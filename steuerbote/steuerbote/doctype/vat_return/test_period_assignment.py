"""A VAT Return computes its period from the bookings the VAT Return Settings assign to it (steuerbote.vat_periods),
records the rule, and shows what changed after the filing of a period: on the return being prepared and on the
filed one."""

from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import ustjahr_sources
from steuerbote.steuerbote.doctype.vat_return.vat_return import mapping_for
from steuerbote.steuerbote.report.ustva_kennzahlen.ustva_kennzahlen import execute
from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	insert_record,
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
	post_purchase_invoice,
	post_sales_invoice,
)
from steuerbote.tests.late_documents import ACCOUNTS, filed_return, sales_invoice, set_rule
from steuerbote.ustva import Period, calculate

IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

COMPANY = "Steuerbote Test Nachzügler GmbH"
JULY = Period.month(2026, 7)
SEPTEMBER = Period.month(2026, 9)
AUGUST = Period.month(2026, 8)


class TestPeriodAssignment(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STNZ")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)
		ensure_fiscal_year(COMPANY, "2026-01-01")
		frappe.cache.delete_value("fiscal_years")

	def setUp(self):
		frappe.db.savepoint("period_assignment_test")
		self.addCleanup(frappe.db.rollback, save_point="period_assignment_test")

	def invoice(self, name: str, posting: str, booked: str, **fields) -> str:
		return sales_invoice(COMPANY, self.account, name, posting, booked, **fields)

	def calculated(self, month: int):
		doc = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": month,
			}
		).insert()
		doc.calculate()
		doc.reload()
		return doc

	def amount(self, doc, kennzahl: str) -> Decimal:
		row = next((row for row in doc.kennzahlen if row.kennzahl == kennzahl), None)
		return Decimal(str(row.amount)) if row else Decimal(0)

	def test_the_month_of_the_supply_reports_an_invoice_written_later_and_the_return_records_the_rule(self):
		self.invoice("SINV-NZ-0001", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31")
		july = self.calculated(7)
		self.assertEqual(self.amount(july, "81"), Decimal("1000.00"))
		self.assertEqual((july.period_basis, july.late_treatment), ("By Service Date", "Corrected Return"))
		self.assertEqual(self.amount(self.calculated(8), "81"), Decimal(0))

	def test_by_posting_date_the_month_of_the_invoice_reports_it(self):
		set_rule(COMPANY, "By Posting Date")
		self.invoice("SINV-NZ-0002", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31")
		august = self.calculated(8)
		self.assertEqual(self.amount(august, "81"), Decimal("1000.00"))
		self.assertEqual(august.period_basis, "By Posting Date")

	def test_the_hints_set_the_invoice_against_the_month_of_its_supply(self):
		a = self.account
		post_sales_invoice(
			COMPANY,
			"SINV-NZ-0006",
			"Testkunde",
			"2026-08-03",
			[(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)],
			items=[(a["8400"], 1000)],
			taxes=[(a["1776"], 190)],
			to_date="2026-07-31",
		)
		codes = {row.code for row in self.calculated(7).hints} | {
			row.code for row in self.calculated(8).hints
		}
		self.assertNotIn("ABGLEICH-RECHNUNGEN", codes)

	def test_the_reconciliation_with_the_registers_names_the_invoice_in_both_months(self):
		self.invoice("SINV-NZ-0007", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31")
		rows = {
			month: [
				(row.subject, Decimal(str(row.register_amount)), row.compared)
				for row in self.calculated(month).register_reconciliation
				if row.subject.startswith("In ")
			]
			for month in (7, 8)
		}
		self.assertEqual(
			rows,
			{
				7: [
					(
						"In einem anderen Zeitraum gebucht, in dieser Meldung (Kz 81): SINV-NZ-0007",
						Decimal("1000.00"),
						0,
					)
				],
				8: [
					(
						"In diesem Zeitraum gebucht, in der Meldung eines anderen Zeitraums (Kz 81): SINV-NZ-0007",
						Decimal("-1000.00"),
						0,
					)
				],
			},
		)

	def test_the_report_shows_the_invoice_in_the_month_of_its_supply(self):
		self.invoice("SINV-NZ-0003", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31")
		_columns, rows = execute({"company": COMPANY, "year": 2026, "rhythm": "monthly", "period_index": 7})
		self.assertIn("SINV-NZ-0003", {row.get("voucher_no") for row in rows})

	def test_a_late_invoice_asks_for_the_corrected_return_on_the_current_and_on_the_filed_return(self):
		july = filed_return(COMPANY, JULY, "2026-08-10 12:00:00")
		self.invoice("SINV-NZ-0004", "2026-09-20", "2026-09-20 09:00:00", to_date="2026-07-31")
		september = self.calculated(9)
		self.assertEqual(self.amount(september, "81"), Decimal(0))
		rows = [(row.period_label, row.kind, row.voucher_no) for row in september.late_changes]
		self.assertIn(("Juli 2026", "Booked after Filing", "SINV-NZ-0004"), rows)
		self.assertIn(("Juli 2026", "Changed since Filing", None), rows)
		changes = july.changes_since_filing()
		self.assertTrue(any(row["needs_correction"] for row in changes))
		self.assertIn("SINV-NZ-0004", {row["voucher_no"] for row in changes})

	def test_in_the_current_period_the_late_invoice_is_reported_in_the_month_being_prepared(self):
		set_rule(COMPANY, late="Current Period")
		july = filed_return(COMPANY, JULY, "2026-08-10 12:00:00")
		self.invoice("SINV-NZ-0005", "2026-09-05", "2026-09-05 09:00:00", to_date="2026-07-31")
		august = self.calculated(8)
		self.assertEqual(self.amount(august, "81"), Decimal("1000.00"))
		self.assertEqual(august.late_treatment, "Current Period")
		(row,) = august.late_changes
		self.assertEqual((row.period_label, row.voucher_no), ("Juli 2026", "SINV-NZ-0005"))
		changes = july.changes_since_filing()
		self.assertEqual([row["voucher_no"] for row in changes], ["SINV-NZ-0005"])
		self.assertFalse(changes[0]["needs_correction"])

	def test_a_filed_return_makes_its_corrected_return_once(self):
		july = filed_return(COMPANY, JULY, "2026-08-10 12:00:00")
		name = july.make_correction()
		correction = frappe.get_doc("VAT Return", name)
		self.assertEqual((correction.is_correction, correction.period_index, correction.docstatus), (1, 7, 0))
		self.assertEqual(july.make_correction(), name)

	def reverse_charge(self, posting: str):
		"""A service under § 13b UStG booked on an expense account: its base is derived from its tax."""
		a = self.account
		return post_journal_entry(
			COMPANY,
			posting,
			[(a["4980"], 1000, 0), (a["1577"], 190, 0), (a["1787"], 0, 190), (a["1200"], 0, 1000)],
		)

	def reverse_charge_check(self, doc):
		return next(row for row in doc.checks if row.label == "Umsatzsteuer nach § 13b UStG 19 %")

	def test_by_service_date_a_derived_base_stays_with_its_tax_in_the_month_of_its_posting(self):
		self.invoice("SINV-NZ-0007", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31")
		entry = self.reverse_charge("2026-08-12")
		july, august = self.calculated(7), self.calculated(8)
		self.assertEqual((self.amount(july, "81"), self.amount(july, "84")), (Decimal("1000.00"), Decimal(0)))
		self.assertEqual(
			(self.amount(august, "81"), self.amount(august, "84"), self.amount(august, "85")),
			(Decimal(0), Decimal("1000.00"), Decimal("190.00")),
		)
		check = self.reverse_charge_check(august)
		self.assertEqual((Decimal(str(check.derived_base)), check.passed), (Decimal("1000.00"), 1))
		_columns, rows = execute({"company": COMPANY, "year": 2026, "rhythm": "monthly", "period_index": 8})
		self.assertIn(entry.name, {row.get("voucher_no") for row in rows})
		year = calculate(ustjahr_sources.year_lines(COMPANY, 2026), mapping_for(COMPANY, 2026))
		self.assertEqual(
			(year.values["81"].amount, year.values["84"].amount), (Decimal("1000.00"), Decimal("1000.00"))
		)

	def test_by_posting_date_the_invoice_and_the_derived_base_share_the_month_of_their_posting(self):
		set_rule(COMPANY, "By Posting Date")
		self.invoice("SINV-NZ-0008", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31")
		self.reverse_charge("2026-08-12")
		august = self.calculated(8)
		self.assertEqual(
			(self.amount(august, "81"), self.amount(august, "84"), self.amount(august, "85")),
			(Decimal("1000.00"), Decimal("1000.00"), Decimal("190.00")),
		)
		self.assertEqual(self.reverse_charge_check(august).passed, 1)

	def test_a_late_voucher_with_a_derived_base_moves_with_its_tax(self):
		set_rule(COMPANY, late="Current Period")
		july = filed_return(COMPANY, JULY, "2026-08-10 12:00:00")
		entry = self.reverse_charge("2026-07-20")
		august = self.calculated(8)
		self.assertEqual(
			(self.amount(august, "84"), self.amount(august, "85")), (Decimal("1000.00"), Decimal("190.00"))
		)
		check = self.reverse_charge_check(august)
		self.assertEqual((Decimal(str(check.derived_base)), check.passed), (Decimal("1000.00"), 1))
		self.assertEqual([row["voucher_no"] for row in july.changes_since_filing()], [entry.name])

	def test_only_a_filed_return_makes_a_corrected_return(self):
		with self.assertRaises(frappe.ValidationError):
			self.calculated(10).make_correction()


START_COMPANY = "Steuerbote Test Buchstart GmbH"
JUNE = Period.month(2026, 6)


class TestBeforeTheStart(IntegrationTestCase):
	"""The books of the company start on 1 July 2026; June was filed outside Steuerbote on 8 July."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(START_COMPANY, "STBS")
		cls.account = {
			number: make_account(START_COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(START_COMPANY, [(2026, "monthly", 1)], books_start="2026-07-01")
		make_mapping(START_COMPANY)
		frappe.get_doc(
			{
				"doctype": "VAT Return Prior Filing",
				"company": START_COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": 6,
				"filed_on": "2026-07-08",
				"kz83": 500,
				"source_document": "Übermittlungsprotokoll",
				"reason": "Erfunden: vor Steuerbote abgegeben",
			}
		).insert().submit()

	def setUp(self):
		frappe.db.savepoint("before_the_start_test")
		self.addCleanup(frappe.db.rollback, save_point="before_the_start_test")

	def july(self):
		doc = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": START_COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": 7,
			}
		).insert()
		doc.calculate()
		doc.reload()
		return doc

	def june_invoice(self) -> None:
		"""Booked on 2 July, before June was filed on 8 July, but in ERPNext, so not in the June return."""
		sales_invoice(
			START_COMPANY,
			self.account,
			"SINV-BS-0001",
			"2026-07-02",
			"2026-07-02 09:00:00",
			to_date="2026-06-30",
		)

	def kz81(self, doc) -> Decimal:
		row = next((row for row in doc.kennzahlen if row.kennzahl == "81"), None)
		return Decimal(str(row.amount)) if row else Decimal(0)

	def test_a_booking_for_a_period_filed_before_steuerbote_says_where_its_correction_goes(self):
		self.june_invoice()
		july = self.july()
		self.assertEqual(self.kz81(july), Decimal(0))
		(row,) = july.late_changes
		self.assertEqual((row.period_label, row.voucher_no), ("Juni 2026", "SINV-BS-0001"))
		self.assertIn("filed outside Steuerbote", row.message)

	def test_in_the_current_period_it_is_reported_in_the_first_period_of_the_books(self):
		set_rule(START_COMPANY, late="Current Period")
		self.june_invoice()
		july = self.july()
		self.assertEqual(self.kz81(july), Decimal("1000.00"))
		(row,) = july.late_changes
		self.assertEqual((row.period_label, row.voucher_no), ("Juni 2026", "SINV-BS-0001"))
		self.assertIn("reported in this period", row.message)

	def test_the_period_before_the_start_still_makes_no_return(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "VAT Return",
					"company": START_COMPANY,
					"year": 2026,
					"rhythm": "monthly",
					"period_index": 6,
				}
			).insert()


SUPPLIER_COMPANY = "Steuerbote Test Lieferant EU GmbH"
PRAGUE = "Vltava Analytics s.r.o."


class TestSupplierOfAnotherMemberState(IntegrationTestCase):
	"""A service under § 13b UStG from a supplier established in another member state goes to Kz 46 (§ 13b Abs. 1
	UStG) by the facts of its supplier; the period rule must hand these facts on wherever it reads the ledger."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(SUPPLIER_COMPANY, "STEU")
		cls.account = {
			number: make_account(SUPPLIER_COMPANY, number, name, root_type)
			for number, (name, root_type) in {
				**ACCOUNTS,
				"1600": ("Verbindlichkeiten aus Lieferungen und Leistungen", "Liability"),
			}.items()
		}
		make_settings(SUPPLIER_COMPANY, [(2026, "monthly", 1)])
		make_mapping(SUPPLIER_COMPANY)
		ensure_fiscal_year(SUPPLIER_COMPANY, "2026-01-01")
		insert_record(
			"Supplier", name=PRAGUE, supplier_name=PRAGUE, country="Czech Republic", tax_id="CZ12345678"
		)

	def setUp(self):
		frappe.db.savepoint("supplier_period_test")
		self.addCleanup(frappe.db.rollback, save_point="supplier_period_test")

	def post(self) -> str:
		"""A July invoice written in August and an August service from Prague on an expense account."""
		a = self.account
		sales_invoice(
			SUPPLIER_COMPANY, a, "SINV-EU-0001", "2026-08-03", "2026-08-03 09:00:00", to_date="2026-07-31"
		)
		name = post_purchase_invoice(
			SUPPLIER_COMPANY,
			"PINV-EU-0001",
			PRAGUE,
			"2026-08-12",
			[(a["4980"], 1000, 0), (a["1577"], 190, 0), (a["1787"], 0, 190)],
			items=[(a["4980"], 1000)],
		)
		insert_record(
			"GL Entry",
			company=SUPPLIER_COMPANY,
			posting_date="2026-08-12",
			account=a["1600"],
			debit=0,
			credit=1000,
			party_type="Supplier",
			party=PRAGUE,
			voucher_type="Purchase Invoice",
			voucher_no=name,
			is_cancelled=0,
			is_opening="No",
			docstatus=1,
		)
		return name

	def assert_kz_46_in_august(self, voucher: str, kz81_in_august: Decimal) -> None:
		doc = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": SUPPLIER_COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": 8,
			}
		).insert()
		doc.calculate()
		doc.reload()
		amounts = {row.kennzahl: Decimal(str(row.amount)) for row in doc.kennzahlen}
		self.assertEqual((amounts.get("46"), amounts.get("84", Decimal(0))), (Decimal("1000.00"), Decimal(0)))
		self.assertEqual(amounts.get("81", Decimal(0)), kz81_in_august)
		mapping = mapping_for(SUPPLIER_COMPANY, 2026)
		(run,) = ustjahr_sources.period_runs(SUPPLIER_COMPANY, [AUGUST], mapping, Decimal("0.01")).values()
		self.assertEqual((run.values["46"].amount, run.values.get("84")), (Decimal("1000.00"), None))
		_columns, rows = execute(
			{"company": SUPPLIER_COMPANY, "year": 2026, "rhythm": "monthly", "period_index": 8}
		)
		under = {row["parent_kennzahl"] for row in rows if row.get("voucher_no") == voucher}
		self.assertEqual(under, {"46", "47", "67"})

	def test_by_service_date_the_service_from_another_member_state_stays_on_kz_46(self):
		self.assert_kz_46_in_august(self.post(), Decimal(0))

	def test_by_posting_date_the_service_from_another_member_state_stays_on_kz_46(self):
		set_rule(SUPPLIER_COMPANY, "By Posting Date")
		self.assert_kz_46_in_august(self.post(), Decimal("1000.00"))
