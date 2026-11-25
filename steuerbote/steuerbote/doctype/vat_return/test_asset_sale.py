"""A fixed asset sold through ERPNext itself: a Sales Invoice whose row carries the Asset, which books no revenue but the
disposal of the asset (erpnext/assets/doctype/asset/depreciation.py, get_gl_entries_on_asset_disposal), and an item on
the revenue account for asset sales next to the scrapping of the asset. Both give the price in Kz 81 of the month of
the supply, in the report „UStVA Kennzahlen“ and in the run over the year."""

from decimal import Decimal

import frappe
from erpnext.assets.doctype.asset.asset import make_sales_invoice
from erpnext.assets.doctype.asset.depreciation import scrap_asset
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
)
from steuerbote.ustva import calculate, derive_bases

IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

COMPANY = "Steuerbote Test Anlagenverkauf GmbH"
CUSTOMER = "Steuerbote Testkunde Anlagenkauf"
CATEGORY = "Steuerbote Test Betriebsausstattung"
ASSET_ITEM = "STB-TEST-ANLAGE"
SALE_ITEM = "STB-TEST-ANLAGENVERKAUF"
ITEM_GROUP = "Steuerbote Testartikel"
LOCATION = "Steuerbote Teststandort"
PRICE_LIST = "Steuerbote Test Verkauf"
UOM = "Nos"
# SKR03 numbers; ERPNext needs the account types of an asset category and of an invoice.
ACCOUNTS = {
	"0490": ("Sonstige Betriebs- und Geschäftsausstattung", "Asset", "Fixed Asset"),
	"0499": (
		"Kumulierte Abschreibungen Betriebs- und Geschäftsausstattung",
		"Asset",
		"Accumulated Depreciation",
	),
	"4830": ("Abschreibungen auf Sachanlagen", "Expense", "Depreciation"),
	"2310": ("Anlagenabgänge Sachanlagen (Restbuchwert bei Buchverlust)", "Expense", None),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset", "Receivable"),
	"1776": ("Umsatzsteuer 19 %", "Liability", "Tax"),
	"8400": ("Erlöse 19 % USt", "Income", "Income Account"),
	"8820": ("Erlöse aus Verkäufen Sachanlagevermögen 19 % USt (bei Buchgewinn)", "Income", "Income Account"),
}


def money(value) -> Decimal:
	return Decimal(str(value)).quantize(Decimal("0.01"))


class TestAssetSale(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STAV")
		cls.account = {
			number: frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})
			or make_account(COMPANY, number, name, root_type, account_type=account_type)
			for number, (name, root_type, account_type) in ACCOUNTS.items()
		}
		frappe.db.set_value("Account", cls.account["1776"], "tax_rate", 19)
		cost_center = frappe.db.get_value("Company", COMPANY, "cost_center")
		frappe.db.set_value(
			"Company",
			COMPANY,
			{
				"default_receivable_account": cls.account["1400"],
				"disposal_account": cls.account["2310"],
				"depreciation_cost_center": cost_center,
				"accumulated_depreciation_account": cls.account["0499"],
				"depreciation_expense_account": cls.account["4830"],
				"round_off_account": cls.account["2310"],
				"round_off_cost_center": cost_center,
			},
		)
		make_masters(cls.account)
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)
		ensure_fiscal_year(COMPANY, "2026-01-01")
		frappe.cache.delete_value("fiscal_years")

	def setUp(self):
		frappe.db.savepoint("asset_sale_test")
		self.addCleanup(frappe.db.rollback, save_point="asset_sale_test")

	def asset(self, name: str) -> str:
		"""A submitted asset bought for 1,500.00 and written down by 520.00, as an existing asset of the company."""
		asset = frappe.get_doc(
			{
				"doctype": "Asset",
				"asset_name": name,
				"item_code": ASSET_ITEM,
				"asset_category": CATEGORY,
				"company": COMPANY,
				"location": LOCATION,
				"asset_type": "Existing Asset",
				"purchase_date": "2025-01-15",
				"available_for_use_date": "2025-01-15",
				"calculate_depreciation": 0,
				"net_purchase_amount": 1500,
				"purchase_amount": 1500,
				"opening_accumulated_depreciation": 520,
				"asset_quantity": 1,
			}
		)
		asset.insert(ignore_permissions=True)
		asset.submit()
		return asset.name

	def sell(self, asset: str, posting_date: str, **fields) -> str:
		"""The Sales Invoice ERPNext makes for the asset („Verkaufen“ on the asset), for 800.00 and 19 % tax."""
		invoice = make_sales_invoice(asset, ASSET_ITEM, COMPANY, 1)
		invoice.update(
			{
				"customer": CUSTOMER,
				"posting_date": posting_date,
				"set_posting_time": 1,
				"due_date": posting_date,
				"debit_to": self.account["1400"],
				"currency": "EUR",
				"conversion_rate": 1,
				"selling_price_list": PRICE_LIST,
				"price_list_currency": "EUR",
				"plc_conversion_rate": 1,
				"ignore_pricing_rule": 1,
				"disable_rounded_total": 1,
				**fields,
			}
		)
		invoice.items[0].rate = 800
		invoice.append(
			"taxes",
			{
				"charge_type": "On Net Total",
				"account_head": self.account["1776"],
				"rate": 19,
				"description": "Umsatzsteuer 19 %",
			},
		)
		invoice.insert(ignore_permissions=True)
		invoice.submit()
		return invoice.name

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

	def amounts(self, doc) -> dict[str, Decimal]:
		return {row.kennzahl: money(row.amount) for row in doc.kennzahlen}

	def test_erpnext_books_the_sale_of_an_asset_without_a_revenue_account(self):
		invoice = self.sell(self.asset("Testanlage Buchungen"), "2026-03-10")
		entries = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Sales Invoice", "voucher_no": invoice, "is_cancelled": 0},
			fields=["account", "debit", "credit"],
		)
		number = {name: account for account, name in self.account.items()}
		self.assertEqual(
			sorted((number[row.account], money(row.debit), money(row.credit)) for row in entries),
			[
				("0490", money(0), money(1500)),
				("0499", money(520), money(0)),
				("1400", money(952), money(0)),
				("1776", money(0), money(152)),
				("2310", money(180), money(0)),
			],
		)

	def test_the_sale_through_the_invoice_goes_to_kz_81_with_a_hint(self):
		invoice = self.sell(self.asset("Testanlage Rechnung"), "2026-03-10")
		doc = self.calculated(3)
		self.assertEqual(self.amounts(doc), {"81": money(800), "83": money(152)})
		self.assertEqual((doc.ready, doc.status), (1, "Bereit"))
		check = next(row for row in doc.checks if row.label == "Umsatzsteuer 19 %")
		self.assertEqual((money(check.derived_base), check.passed), (money(800), 1))
		hints = [row for row in doc.hints if row.code == "UMSATZ-OHNE-ERLOESKONTO"]
		self.assertEqual(
			[(row.severity, row.voucher_type, row.voucher_no) for row in hints],
			[("Hinweis", "Sales Invoice", invoice)],
		)
		self.assertIn("auf den Konten 0490, 0499 und 2310", hints[0].text)
		self.assertNotIn("ABGLEICH-RECHNUNGEN", [row.code for row in doc.hints])

	def test_the_report_shows_the_invoice_under_kz_81(self):
		invoice = self.sell(self.asset("Testanlage Bericht"), "2026-03-12")
		_columns, rows = execute({"company": COMPANY, "year": 2026, "rhythm": "monthly", "period_index": 3})
		under_81 = [row for row in rows if row.get("kennzahl") == "81" and row.get("voucher_no") == invoice]
		self.assertEqual([money(row.get("amount")) for row in under_81], [money(800)])

	def test_the_month_of_the_supply_reports_the_sale(self):
		self.sell(
			self.asset("Testanlage Leistungsdatum"),
			"2026-06-03",
			from_date="2026-05-20",
			to_date="2026-05-31",
		)
		self.assertEqual(self.amounts(self.calculated(5)).get("81"), money(800))
		self.assertNotIn("81", self.amounts(self.calculated(6)))

	def test_the_run_over_the_year_derives_the_same_base(self):
		self.sell(self.asset("Testanlage Jahr"), "2026-03-10")
		mapping, lines = mapping_for(COMPANY, 2026), ustjahr_sources.year_lines(COMPANY, 2026)
		self.assertEqual(
			[(base.kennzahl, base.base) for base in derive_bases(lines, mapping)], [("81", Decimal("800.00"))]
		)
		self.assertEqual(calculate(lines, mapping).reported("81"), Decimal("800"))

	def test_an_item_on_the_revenue_account_and_the_scrapped_asset_give_the_same_return(self):
		asset = self.asset("Testanlage Verschrottung")
		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": COMPANY,
				"customer": CUSTOMER,
				"posting_date": "2026-04-10",
				"set_posting_time": 1,
				"due_date": "2026-04-10",
				"debit_to": self.account["1400"],
				"currency": "EUR",
				"conversion_rate": 1,
				"selling_price_list": PRICE_LIST,
				"price_list_currency": "EUR",
				"plc_conversion_rate": 1,
				"ignore_pricing_rule": 1,
				"disable_rounded_total": 1,
				"items": [
					{
						"item_code": SALE_ITEM,
						"qty": 1,
						"rate": 800,
						"income_account": self.account["8820"],
						"cost_center": frappe.db.get_value("Company", COMPANY, "cost_center"),
					}
				],
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": self.account["1776"],
						"rate": 19,
						"description": "Umsatzsteuer 19 %",
					}
				],
			}
		)
		invoice.insert(ignore_permissions=True)
		invoice.submit()
		scrap_asset(asset, "2026-04-10")
		doc = self.calculated(4)
		self.assertEqual(self.amounts(doc), {"81": money(800), "83": money(152)})
		self.assertEqual((doc.ready, doc.status), (1, "Bereit"))
		self.assertNotIn("UMSATZ-OHNE-ERLOESKONTO", [row.code for row in doc.hints])


def make_masters(account: dict[str, str]) -> None:
	"""The records ERPNext needs to sell an asset, without its setup wizard: a unit, an item group, a location, an asset
	category with the accounts of the company, a selling price list, the item of the asset, an item for asset sales and a customer without address."""
	if not frappe.db.exists("UOM", UOM):
		insert_record("UOM", name=UOM, uom_name=UOM, must_be_whole_number=1, enabled=1)
	if not frappe.db.exists("Item Group", ITEM_GROUP):
		insert_record("Item Group", name=ITEM_GROUP, item_group_name=ITEM_GROUP, is_group=0)
	if not frappe.db.exists("Price List", PRICE_LIST):
		insert_record(
			"Price List", name=PRICE_LIST, price_list_name=PRICE_LIST, currency="EUR", selling=1, enabled=1
		)
	if not frappe.db.exists("Location", LOCATION):
		insert_record("Location", name=LOCATION, location_name=LOCATION, is_group=0)
	if not frappe.db.exists("Asset Category", CATEGORY):
		frappe.get_doc(
			{
				"doctype": "Asset Category",
				"asset_category_name": CATEGORY,
				"enable_cwip_accounting": 0,
				"accounts": [
					{
						"company_name": COMPANY,
						"fixed_asset_account": account["0490"],
						"accumulated_depreciation_account": account["0499"],
						"depreciation_expense_account": account["4830"],
					}
				],
			}
		).insert(ignore_permissions=True)
	for code, name, fixed_asset in (
		(ASSET_ITEM, "Testanlage", 1),
		(SALE_ITEM, "Verkauf von Anlagevermögen", 0),
	):
		if not frappe.db.exists("Item", code):
			insert_record(
				"Item",
				name=code,
				item_code=code,
				item_name=name,
				description=name,
				item_group=ITEM_GROUP,
				stock_uom=UOM,
				is_stock_item=0,
				is_fixed_asset=fixed_asset,
				asset_category=CATEGORY if fixed_asset else None,
				is_sales_item=1,
				is_purchase_item=1,
				include_item_in_manufacturing=0,
				disabled=0,
				has_variants=0,
			)
	if not frappe.db.exists("Customer", CUSTOMER):
		# Without an address: the site has no Address Template to show one on the invoice.
		insert_record("Customer", name=CUSTOMER, customer_name=CUSTOMER, customer_type="Company")
