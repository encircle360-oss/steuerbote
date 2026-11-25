"""Abgleich mit Registern: Berechnen sets the reports Sales Register and Purchase Register of the period against the
ledger amounts of the return, and a difference needs an explanation before the return is transmitted, made into a
file or filed."""

from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import fmt_money

from steuerbote.registers import register_lines
from steuerbote.tests.helpers import (
	insert_record,
	make_account,
	make_company,
	make_customer,
	make_mapping,
	make_settings,
	post_journal_entry,
	post_purchase_invoice,
	post_sales_invoice,
	submitted_without_record,
)
from steuerbote.ustva import KENNZAHLEN
from steuerbote.ustva.registers import Register

# The companies, their accounts, parties and vouchers are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

# Sells and buys with invoices in October and November 2026, books a journal entry besides in November and only one
# in September.
COMPANY = "Steuerbote Test Register GmbH"
ABBR = "STRG"
# Its invoices of October stay out of the reconciliation of COMPANY.
OTHER_COMPANY = "Steuerbote Test Register Zwei GmbH"
FILED_IN_MEIN_ELSTER = "In Mein ELSTER abgegeben"
DATENLIEFERANT = {"street": "Hauptstraße 1", "postal_code": "80331", "city": "München"}
CUSTOMER = "Register Muster GmbH"
SUPPLIER = "Register Nord Software AB"
DEVIATION = "REGISTER-ABWEICHUNG"

# SKR03 numbers: the sale at 19 %, the EU service, the § 13b service with its taxes, a domestic purchase with its
# Vorsteuer on an expense account without a place in the mapping, receivables, payables and a bank.
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"3123": ("Sonstige Leistungen EU 19 %", "Expense"),
	"1787": ("Umsatzsteuer nach § 13b UStG 19 %", "Liability"),
	"1577": ("Vorsteuer nach § 13b UStG 19 %", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"4930": ("Bürobedarf", "Expense"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
	"1600": ("Verbindlichkeiten aus Lieferungen und Leistungen", "Liability"),
	"1200": ("Bank", "Asset"),
}


def money(value) -> Decimal:
	return Decimal(str(value)).quantize(Decimal("0.01"))


def euros(amount: str) -> str:
	return fmt_money(Decimal(amount), currency="EUR")


def post_month(company: str, abbr: str, a: dict[str, str], day: str) -> None:
	"""A sale at 19 %, an EU service and two purchases, each invoice with its items, tax rows and GL Entries."""
	month = day[:7].replace("-", "")
	post_sales_invoice(
		company,
		f"SINV-{abbr}-{month}-1",
		CUSTOMER,
		day,
		[(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)],
		items=[(a["8400"], 1000)],
		taxes=[(a["1776"], 190)],
	)
	post_sales_invoice(
		company,
		f"SINV-{abbr}-{month}-2",
		CUSTOMER,
		day,
		[(a["1400"], 2000, 0), (a["8336"], 0, 2000)],
		items=[(a["8336"], 2000)],
	)
	post_purchase_invoice(
		company,
		f"PINV-{abbr}-{month}-1",
		SUPPLIER,
		day,
		[(a["3123"], 300, 0), (a["1577"], 57, 0), (a["1787"], 0, 57), (a["1600"], 0, 300)],
		items=[(a["3123"], 300)],
		taxes=[(a["1577"], 57), (a["1787"], -57)],
	)
	post_purchase_invoice(
		company,
		f"PINV-{abbr}-{month}-2",
		SUPPLIER,
		day,
		[(a["4930"], 100, 0), (a["1576"], 19, 0), (a["1600"], 0, 119)],
		items=[(a["4930"], 100)],
		taxes=[(a["1576"], 19)],
	)


class TestRegisterReconciliation(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for company, abbr in ((COMPANY, ABBR), (OTHER_COMPANY, "STRZ")):
			make_company(company, abbr)
			accounts = {
				number: make_account(company, number, name, root_type)
				for number, (name, root_type) in ACCOUNTS.items()
			}
			make_settings(company, [(2026, "monthly", 1)], **DATENLIEFERANT)
			make_mapping(company)
			if company == COMPANY:
				cls.account = accounts
		make_customer(CUSTOMER, "Germany", "DE123456789")
		insert_record("Supplier", name=SUPPLIER, supplier_name=SUPPLIER, country="Sweden")
		a = cls.account
		post_month(COMPANY, ABBR, a, "2026-10-05")
		post_month(OTHER_COMPANY, "STRZ", accounts, "2026-10-05")
		post_sales_invoice(
			COMPANY,
			f"SINV-{ABBR}-OPEN",
			CUSTOMER,
			"2026-10-01",
			[],
			items=[(a["8336"], 700)],
			is_opening="Yes",
		)
		cancelled = post_sales_invoice(
			COMPANY,
			f"SINV-{ABBR}-CANC",
			CUSTOMER,
			"2026-10-06",
			[],
			items=[(a["8400"], 500)],
			taxes=[(a["1776"], 95)],
		)
		frappe.db.set_value("Sales Invoice", cancelled, "docstatus", 2)
		post_month(COMPANY, ABBR, a, "2026-11-05")
		post_journal_entry(
			COMPANY, "2026-11-20", [(a["1400"], 595, 0), (a["8400"], 0, 500), (a["1776"], 0, 95)]
		)
		post_journal_entry(
			COMPANY, "2026-09-10", [(a["1400"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)]
		)

	def setUp(self):
		"""November has ended, so its return can be ready."""
		super().setUp()
		self.enterContext(self.freeze_time("2026-12-15 09:00:00", tick=True))

	def roll_back_afterwards(self) -> None:
		frappe.db.savepoint("register_test")
		self.addCleanup(frappe.db.rollback, save_point="register_test")

	def calculated(self, period: int, **fields):
		doc = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": period,
				**fields,
			}
		).insert()
		doc.calculate()
		doc.reload()
		return doc

	def rows(self, doc) -> list[tuple]:
		return [
			(
				row.register,
				row.subject,
				money(row.register_amount),
				money(row.ledger_amount),
				money(row.difference),
				row.compared,
			)
			for row in doc.register_reconciliation
		]

	def test_reads_what_both_registers_show_of_the_submitted_invoices_of_the_company(self):
		a = self.account
		lines = register_lines(COMPANY, "2026-10-01", "2026-10-31")
		self.assertEqual(
			sorted(
				(line.register, line.account, line.account_number, line.amount, line.opening)
				for line in lines
			),
			sorted(
				[
					(Register.SALES, a["8400"], "8400", money(1000), False),
					(Register.SALES, a["1776"], "1776", money(190), False),
					(Register.SALES, a["8336"], "8336", money(2000), False),
					(Register.SALES, a["8336"], "8336", money(700), True),
					(Register.PURCHASES, a["3123"], "3123", money(300), False),
					(Register.PURCHASES, a["1577"], "1577", money(57), False),
					(Register.PURCHASES, a["1787"], "1787", money(-57), False),
					(Register.PURCHASES, a["4930"], "4930", money(100), False),
					(Register.PURCHASES, a["1576"], "1576", money(19), False),
				]
			),
		)

	def test_a_period_without_invoices_reads_nothing_and_says_nothing(self):
		frappe.local.message_log = []
		self.assertEqual(register_lines(COMPANY, "2026-07-01", "2026-07-31"), [])
		self.assertEqual(frappe.local.message_log, [])
		self.assertFalse(frappe.flags.mute_messages)

	def test_invoices_that_make_the_whole_ledger_reconcile_without_a_difference(self):
		doc = self.calculated(10)
		self.assertEqual((doc.ready, doc.status), (1, "Bereit"))
		self.assertEqual(
			self.rows(doc),
			[
				(
					"Sales Register",
					"Kz 81 Steuerpflichtige Umsätze zum Steuersatz von 19 %",
					money(1000),
					money(1000),
					money(0),
					1,
				),
				("Sales Register", "Konto 1776 Umsatzsteuer 19 %", money(190), money(190), money(0), 1),
				(
					"Sales Register",
					"Kz 21 Nicht steuerbare sonstige Leistungen gemäß § 18b Satz 1 Nummer 2 UStG",
					money(2000),
					money(2000),
					money(0),
					1,
				),
				(
					"Sales Register",
					"Eröffnungsrechnungen, die die Meldung auslässt: 8336",
					money(700),
					money(0),
					money(0),
					0,
				),
				(
					"Purchase Register",
					f"Kz 46 {KENNZAHLEN['46'].label}",
					money(300),
					money(300),
					money(0),
					1,
				),
				(
					"Purchase Register",
					"Konto 1787 Umsatzsteuer nach § 13b UStG 19 %",
					money(57),
					money(57),
					money(0),
					1,
				),
				(
					"Purchase Register",
					"Konto 1576 Abziehbare Vorsteuer 19 %",
					money(19),
					money(19),
					money(0),
					1,
				),
				(
					"Purchase Register",
					"Konto 1577 Vorsteuer nach § 13b UStG 19 %",
					money(57),
					money(57),
					money(0),
					1,
				),
				(
					"Purchase Register",
					"Konten ohne Platz in der Kontenzuordnung: 4930",
					money(100),
					money(0),
					money(0),
					0,
				),
			],
		)
		self.assertEqual(
			[(row.kennzahl, row.account) for row in doc.register_reconciliation if row.account],
			[
				("", self.account["1776"]),
				("", self.account["1787"]),
				("66", self.account["1576"]),
				("67", self.account["1577"]),
			],
		)
		self.assertEqual([row.code for row in doc.hints if row.code == DEVIATION], [])

	def test_a_journal_entry_beside_the_invoices_is_a_difference_with_a_hint_that_holds_nothing(self):
		doc = self.calculated(11)
		self.assertEqual((doc.ready, doc.status), (1, "Bereit"))
		self.assertEqual(
			[(row.subject, money(row.difference)) for row in doc.register_reconciliation if row.difference],
			[
				("Kz 81 Steuerpflichtige Umsätze zum Steuersatz von 19 %", money(500)),
				("Konto 1776 Umsatzsteuer 19 %", money(95)),
			],
		)
		base = (
			f"Kz 81: Laut Übersicht über den Umsatz (Sales Register) {euros('1000.00')}, laut Hauptbuch "
			f"{euros('1500.00')}; die Differenz von {euros('500.00')} braucht vor der Abgabe eine Erklärung."
		)
		tax = (
			f"Konto 1776 Umsatzsteuer 19 %: Laut Übersicht über den Umsatz (Sales Register) {euros('190.00')}, "
			f"laut Hauptbuch {euros('285.00')}; die Differenz von {euros('95.00')} braucht vor der Abgabe eine "
			"Erklärung."
		)
		self.assertEqual(
			[(row.severity, row.text) for row in doc.hints if row.code == DEVIATION],
			[("Hinweis", base), ("Hinweis", tax)],
		)

	def test_a_difference_without_explanation_holds_the_transmission_the_file_and_the_filing(self):
		self.roll_back_afterwards()
		doc = self.calculated(11)
		refused = "difference without an explanation|Differenz ohne Erklärung"
		for operation in ("validate", "test_send", "send"):
			with (
				self.subTest(operation=operation),
				patch("frappe.enqueue") as enqueue,
				self.assertRaisesRegex(frappe.ValidationError, refused),
			):
				doc.transmit(operation)
			enqueue.assert_not_called()
		with self.assertRaisesRegex(frappe.ValidationError, refused):
			doc.make_import_file()
		with self.assertRaisesRegex(frappe.ValidationError, refused):
			doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		doc.reload()
		with self.assertRaisesRegex(frappe.ValidationError, refused):
			submitted_without_record(doc)

	def test_an_explanation_in_each_row_lets_the_return_be_filed(self):
		self.roll_back_afterwards()
		doc = self.calculated(11)
		for row in doc.register_reconciliation:
			if row.difference:
				row.explanation = "Privatanteil per Journalbuchung vom 20. November"
		doc.save()
		doc.reload()
		self.assertTrue(doc.make_import_file())
		doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		self.assertEqual((doc.docstatus, doc.status), (1, "Abgegeben"))

	def test_one_explanation_missing_still_holds_the_return(self):
		self.roll_back_afterwards()
		doc = self.calculated(11)
		next(row for row in doc.register_reconciliation if row.difference).explanation = "Privatanteil"
		doc.save()
		with self.assertRaisesRegex(frappe.ValidationError, "Konto 1776"):
			doc.make_import_file()

	def test_the_remarks_explain_the_differences_as_they_do_for_a_return_that_is_not_ready(self):
		self.roll_back_afterwards()
		doc = self.calculated(
			11, remarks="Privatanteil per Journalbuchung, abgestimmt mit der Steuerberatung"
		)
		self.assertTrue(doc.make_import_file())
		doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		self.assertEqual(doc.status, "Abgegeben")

	def test_a_save_keeps_the_reconciliation_and_takes_only_the_explanations(self):
		doc = self.calculated(11)
		row = next(row for row in doc.register_reconciliation if row.difference)
		row.update(
			{"subject": "Kz 86", "difference": 0, "register_amount": 1500, "explanation": " Privatanteil "}
		)
		doc.save()
		doc.reload()
		stored = next(row for row in doc.register_reconciliation if row.explanation)
		self.assertEqual(
			(stored.subject, money(stored.register_amount), money(stored.difference), stored.explanation),
			(
				"Kz 81 Steuerpflichtige Umsätze zum Steuersatz von 19 %",
				money(1000),
				money(500),
				"Privatanteil",
			),
		)

	def test_berechnen_keeps_an_explanation_as_long_as_its_amounts_stay(self):
		self.roll_back_afterwards()
		doc = self.calculated(11)
		for row in doc.register_reconciliation:
			row.explanation = "Privatanteil" if row.difference else ""
		doc.save()
		doc.calculate()
		doc.reload()
		self.assertEqual(
			[row.explanation for row in doc.register_reconciliation if row.difference], ["Privatanteil"] * 2
		)
		a = self.account
		post_journal_entry(
			COMPANY, "2026-11-25", [(a["1400"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)]
		)
		doc.calculate()
		doc.reload()
		self.assertEqual([row.explanation for row in doc.register_reconciliation if row.difference], ["", ""])

	def test_a_period_whose_registers_book_on_no_account_is_not_compared(self):
		doc = self.calculated(9)
		self.assertEqual(
			self.rows(doc),
			[
				(
					"Sales Register",
					"Keine Rechnung des Zeitraums bucht auf ein Konto, nicht abgeglichen",
					money(0),
					money(0),
					money(0),
					0,
				)
			],
		)
		self.assertEqual([row.code for row in doc.hints if row.code == DEVIATION], [])
		self.assertTrue(doc.make_import_file())

	def test_a_new_return_starts_without_a_reconciliation_and_a_saved_one_keeps_its_period(self):
		doc = self.calculated(11)
		copy = frappe.copy_doc(doc).insert()
		self.assertEqual(copy.register_reconciliation, [])
		rows = len(doc.register_reconciliation)
		doc.period_index = 10
		with self.assertRaises(frappe.CannotChangeConstantError):
			doc.save()
		doc.reload()
		self.assertEqual((len(doc.register_reconciliation), doc.period_index), (rows, 11))
