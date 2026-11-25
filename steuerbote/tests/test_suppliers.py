"""The suppliers behind the vouchers of § 13b UStG on a site: read from the GL Entries, the Supplier, its primary
address and the classifications of the VAT Return Mapping, and the Voranmeldung that splits by them into Kz 46 and 84.
Suppliers, numbers and amounts are invented."""

from datetime import date
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.ledger import load_lines
from steuerbote.suppliers import classifications, load_vouchers
from steuerbote.tests.helpers import (
	insert_record,
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
	post_purchase_invoice,
)
from steuerbote.ustva import Classification, Supplier, Voucher, calculate

COMPANY = "Steuerbote Test Lieferanten GmbH"
OTHER_COMPANY = "Steuerbote Test Andere Lieferanten GmbH"
MAPPING = "VAT Return Mapping"
ACCOUNTS = {
	"4980": ("Betriebsbedarf", "Expense"),
	"3123": ("Sonstige Leistungen EU 19 % Vorsteuer und 19 % Umsatzsteuer", "Expense"),
	"1787": ("Umsatzsteuer nach § 13b UStG 19 %", "Liability"),
	"1577": ("Abziehbare Vorsteuer nach § 13b UStG 19 %", "Asset"),
	"1600": ("Verbindlichkeiten aus Lieferungen und Leistungen", "Liability"),
	"1200": ("Bank", "Asset"),
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}
PRAGUE = "Vltava Software s.r.o."
BOSTON = "Harbor Analytics Inc."
LYON = "Rhône Conseil SARL"
NOWHERE = "Nebula Tools LLC"
TEMPLATE = "Reverse Charge Leistungen - STLF"


def make_supplier(
	name: str, country: str | None = None, tax_id: str | None = None, address: str | None = None
):
	"""A supplier with a country in its master data and, given ``address``, a primary address in that country."""
	primary = None
	if address is not None:
		primary = insert_record(
			"Address",
			name=f"{name}-Billing",
			address_title=name,
			address_type="Billing",
			address_line1="Teststraße 1",
			city="Teststadt",
			country=address,
			is_primary_address=1,
		)
	insert_record(
		"Supplier",
		name=name,
		supplier_name=name,
		country=country,
		tax_id=tax_id,
		supplier_primary_address=primary,
	)


def money(value: str) -> Decimal:
	return Decimal(value)


class IntegrationTestSuppliers(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STLF")
		make_company(OTHER_COMPANY, "STLA")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)
		make_supplier(PRAGUE, "Czech Republic", "CZ12345678")
		make_supplier(BOSTON, "United States", "IE9999999W")
		make_supplier(LYON, address="France")
		make_supplier(NOWHERE)
		insert_record("Purchase Taxes and Charges Template", name=TEMPLATE, title=TEMPLATE, company=COMPANY)
		a = cls.account
		cls.prague = cls.service("PI-STLF-1", PRAGUE, "2026-05-04", "1000")
		cls.boston = cls.service("PI-STLF-2", BOSTON, "2026-05-05", "500")
		cls.lyon = cls.service("PI-STLF-3", LYON, "2026-05-06", "200", taxes_and_charges=TEMPLATE)
		cls.nowhere = cls.service("PI-STLF-4", NOWHERE, "2026-05-07", "100")
		cls.journal = post_journal_entry(
			COMPANY,
			"2026-05-08",
			[(a["4980"], 300, 0), (a["1577"], 57, 0), (a["1787"], 0, 57), (a["1200"], 0, 300)],
		).name
		post_journal_entry(
			COMPANY, "2026-05-09", [(a["1400"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)]
		)

	@classmethod
	def service(cls, name: str, supplier: str, day: str, net: str, **fields) -> str:
		"""A Purchase Invoice of a service under § 13b UStG on an expense account, the supplier on its payable line."""
		a = cls.account
		tax = str(money(net) * Decimal("0.19"))
		post_purchase_invoice(
			COMPANY,
			name,
			supplier,
			day,
			[(a["4980"], net, 0), (a["1577"], tax, 0), (a["1787"], 0, tax)],
			items=[(a["4980"], net)],
			**fields,
		)
		insert_record(
			"GL Entry",
			company=COMPANY,
			posting_date=day,
			account=a["1600"],
			debit=0,
			credit=net,
			party_type="Supplier",
			party=supplier,
			voucher_type="Purchase Invoice",
			voucher_no=name,
			is_cancelled=0,
			is_opening="No",
			docstatus=1,
		)
		return name

	def setUp(self):
		frappe.db.savepoint("suppliers_test")
		self.addCleanup(frappe.db.rollback, save_point="suppliers_test")

	def vouchers(self) -> dict[str, Voucher]:
		lines = load_lines(COMPANY, date(2026, 5, 1), date(2026, 5, 31))
		mapping = frappe.get_doc(MAPPING, COMPANY).to_mapping(2026)
		return load_vouchers(COMPANY, lines, mapping)

	def classify(self, *rows: tuple[str, str, str]) -> None:
		mapping = frappe.get_doc(MAPPING, COMPANY)
		for doctype, name, classification in rows:
			mapping.append(
				"reverse_charge",
				{"reference_doctype": doctype, "reference_name": name, "classification": classification},
			)
		mapping.save()

	def test_reads_the_supplier_of_each_voucher_of_section_d(self):
		vouchers = self.vouchers()
		self.assertEqual(
			list(vouchers),
			[
				f"Purchase Invoice:{self.prague}",
				f"Purchase Invoice:{self.boston}",
				f"Purchase Invoice:{self.lyon}",
				f"Purchase Invoice:{self.nowhere}",
				f"Journal Entry:{self.journal}",
			],
		)
		self.assertEqual(
			vouchers[f"Purchase Invoice:{self.prague}"],
			Voucher(date(2026, 5, 4), (Supplier(PRAGUE, "Czech Republic", None, "CZ12345678"),)),
		)
		self.assertEqual(
			vouchers[f"Purchase Invoice:{self.lyon}"],
			Voucher(date(2026, 5, 6), (Supplier(LYON, None, "France"),), tax_template=TEMPLATE),
		)
		self.assertEqual(vouchers[f"Purchase Invoice:{self.nowhere}"].suppliers, (Supplier(NOWHERE),))
		self.assertEqual(vouchers[f"Journal Entry:{self.journal}"], Voucher(date(2026, 5, 8)))

	def test_reads_the_classifications_of_the_mapping(self):
		self.classify(
			("Supplier", BOSTON, "EU Service"),
			("Purchase Invoice", self.prague, "Other Reverse Charge"),
			("Purchase Taxes and Charges Template", TEMPLATE, "Other Reverse Charge"),
			("Journal Entry", self.journal, "EU Service"),
		)
		self.assertEqual(
			classifications(COMPANY),
			{
				("Supplier", BOSTON): Classification.EU_SERVICE,
				("Purchase Invoice", self.prague): Classification.OTHER,
				("Purchase Taxes and Charges Template", TEMPLATE): Classification.OTHER,
				("Journal Entry", self.journal): Classification.EU_SERVICE,
			},
		)
		vouchers = self.vouchers()
		self.assertIs(vouchers[f"Purchase Invoice:{self.prague}"].classification, Classification.OTHER)
		self.assertIs(
			vouchers[f"Purchase Invoice:{self.boston}"].suppliers[0].classification, Classification.EU_SERVICE
		)
		self.assertIs(vouchers[f"Purchase Invoice:{self.lyon}"].template_classification, Classification.OTHER)
		self.assertIs(vouchers[f"Journal Entry:{self.journal}"].classification, Classification.EU_SERVICE)
		self.assertEqual(classifications(OTHER_COMPANY), {})

	def test_a_document_is_classified_once(self):
		with self.assertRaisesRegex(frappe.ValidationError, "is classified twice under § 13b UStG"):
			self.classify(("Supplier", BOSTON, "EU Service"), ("Supplier", BOSTON, "Other Reverse Charge"))

	def test_a_voucher_of_another_company_is_refused(self):
		insert_record(
			"Purchase Invoice", name="PI-STLA-1", company=OTHER_COMPANY, supplier=PRAGUE, docstatus=1
		)
		with self.assertRaisesRegex(frappe.ValidationError, "does not belong to company"):
			self.classify(("Purchase Invoice", "PI-STLA-1", "EU Service"))

	def test_the_voranmeldung_splits_by_the_supplier(self):
		doc = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": 5,
			}
		).insert()
		doc.calculate()
		doc.reload()
		amounts = {row.kennzahl: money(str(row.final)).quantize(Decimal("0.01")) for row in doc.kennzahlen}
		self.assertEqual((amounts["46"], amounts["47"]), (money("1200.00"), money("228.00")))
		self.assertEqual((amounts["84"], amounts["85"]), (money("900.00"), money("171.00")))
		self.assertEqual(amounts["67"], money("399.00"))
		self.assertEqual(amounts["83"], money("19.00"))
		hints = [
			(row.code, row.voucher_type, row.voucher_no) for row in doc.hints if row.code.startswith("SITZ-")
		]
		self.assertEqual(
			hints,
			[
				("SITZ-WIDERSPRUCH", "Purchase Invoice", self.boston),
				("SITZ-OFFEN", "Purchase Invoice", self.nowhere),
				("SITZ-OFFEN", "Journal Entry", self.journal),
			],
		)
		self.assertTrue(doc.ready)

	def test_a_classification_moves_a_voucher_without_supplier_to_46(self):
		self.classify(("Journal Entry", self.journal, "EU Service"))
		vouchers = self.vouchers()
		lines = load_lines(COMPANY, date(2026, 5, 1), date(2026, 5, 31))
		mapping = frappe.get_doc(MAPPING, COMPANY).to_mapping(2026)
		result = calculate(lines, mapping, vouchers=vouchers)
		self.assertEqual(result.reported("46"), money("1500"))
		self.assertEqual(result.reported("84"), money("600"))
