"""The data of the browser tests on a test site, made with the helpers of the Frappe tests:

	bench --site <site> execute steuerbote.tests.e2e.seed.run

A company with SKR03 accounts, its VAT Return Settings and the mapping of "Vorgaben laden", three invoices of
October 2026, a VAT ID Confirmation, a VAT Return for September filed in Mein ELSTER, a calculated VAT Return and
Recapitulative Statement for October, a draft Dauerfristverlängerung for 2026, ERiC Settings that simulate and a user
with the role Accounts User alone. Every record is invented (steuerbote/tests/e2e/data.py) and made once, so the
seed runs again on the same site without a change; a second run only calculates the documents again. It also
marks the setup wizard complete and sets the language of the Administrator and the user to German, so that the
desk opens as a German accountant sees it. Take a site of its own for it, never one with real data.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import today

from steuerbote.steuerbote.doctype.vat_id_confirmation.vat_id_confirmation import store
from steuerbote.tests.e2e import data
from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	insert_record,
	make_account,
	make_company,
	make_customer,
	make_mapping,
	make_settings,
	make_user,
	post_ledger,
	post_sales_invoice,
)
from steuerbote.vatid.service import confirm
from steuerbote.vatid.tests.fakes import FakeClock, FakeFetch, bzst

# SKR03 numbers of the invoices, a bank, receivables and payables.
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"3123": ("Sonstige Leistungen EU 19 %", "Expense"),
	"1787": ("Umsatzsteuer nach § 13b UStG 19 %", "Liability"),
	"1577": ("Vorsteuer nach § 13b UStG 19 %", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1200": ("Bank", "Asset"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
	"1600": ("Verbindlichkeiten aus Lieferungen und Leistungen", "Liability"),
}
# The default bank account of the company, whose balance a chart of ERPNext's home workspace shows.
BANK = "1200"
# The Datenlieferant that the file for Mein ELSTER names.
DATENLIEFERANT = {"street": "Musterstraße 1", "postal_code": "12345", "city": "Musterstadt"}
DESK_LANGUAGE = "de"
INVOICE_DATE = f"{data.YEAR}-{data.MONTH:02d}-15"
FILED_IN_MEIN_ELSTER = "mein_elster"


def run() -> None:
	complete_setup()
	make_company(data.COMPANY, data.ABBR)
	accounts = make_accounts()
	complete_company(accounts)
	make_settings_once()
	if not frappe.db.exists("VAT Return Mapping", data.COMPANY):
		make_mapping(data.COMPANY)
	post_invoices(accounts)
	confirm_eu_vat_id()
	file_previous_month()
	calculate_vat_return()
	calculate_recapitulative_statement()
	make_extension()
	simulate_eric()
	make_desk_users()
	frappe.clear_cache()


def complete_setup() -> None:
	"""What the setup wizard leaves when it completes (frappe.desk.page.setup_wizard): without it, the desk opens
	the wizard instead of the page asked for."""
	frappe.db.set_value(
		"Installed Application", {"app_name": ("in", ["frappe", "erpnext"])}, "is_setup_complete", 1
	)
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
	frappe.db.set_default("desktop:home_page", "workspace")


def make_accounts() -> dict[str, str]:
	accounts = {}
	for number, (name, root_type) in ACCOUNTS.items():
		fields = {"account_type": "Bank"} if number == BANK else {}
		accounts[number] = frappe.db.get_value(
			"Account", {"company": data.COMPANY, "account_number": number}
		) or make_account(data.COMPANY, number, name, root_type, **fields)
	return accounts


def complete_company(accounts: dict[str, str]) -> None:
	"""What the setup of ERPNext gives a company and the charts of its home workspace read: a fiscal year for
	the invoices and one for today, and a default bank account."""
	for day in (INVOICE_DATE, today()):
		ensure_fiscal_year(data.COMPANY, day)
	frappe.db.set_value("Company", data.COMPANY, "default_bank_account", accounts[BANK])


def make_settings_once() -> None:
	"""Monthly filing with Dauerfristverlängerung, and the ZM monthly with the sonstige Leistungen in their own
	month, through all of the year."""
	if frappe.db.exists("VAT Return Settings", data.COMPANY):
		return
	make_settings(
		data.COMPANY,
		[(data.YEAR, "monthly", 1)],
		[(data.YEAR, True, "1100.00")],
		ust_idnr=data.OWN_VAT_ID,
		zm_rules=[{"year": data.YEAR, "valid_from_month": 1, "rhythm": "monthly", "services_monthly": 1}],
		**DATENLIEFERANT,
	)


def post_invoices(accounts: dict[str, str]) -> None:
	"""The invoices as ERPNext keeps them once submitted, with their GL Entries (steuerbote.tests.helpers)."""
	a = accounts
	domestic_address = customer(data.DOMESTIC_CUSTOMER, "Germany")
	eu_address = customer(data.EU_CUSTOMER, "Austria", data.EU_VAT_ID, city="Wien")
	if not frappe.db.exists("Supplier", data.EU_SUPPLIER):
		insert_record("Supplier", name=data.EU_SUPPLIER, supplier_name=data.EU_SUPPLIER, country="Austria")
	if not frappe.db.exists("Sales Invoice", data.DOMESTIC_INVOICE):
		post_sales_invoice(
			data.COMPANY,
			data.DOMESTIC_INVOICE,
			data.DOMESTIC_CUSTOMER,
			INVOICE_DATE,
			[
				(a["1400"], data.DOMESTIC_NET + data.DOMESTIC_TAX, 0),
				(a["8400"], 0, data.DOMESTIC_NET),
				(a["1776"], 0, data.DOMESTIC_TAX),
			],
			customer_address=domestic_address,
		)
	if not frappe.db.exists("Sales Invoice", data.EU_INVOICE):
		post_sales_invoice(
			data.COMPANY,
			data.EU_INVOICE,
			data.EU_CUSTOMER,
			INVOICE_DATE,
			[(a["1400"], data.EU_NET, 0), (a["8336"], 0, data.EU_NET)],
			customer_address=eu_address,
		)
	if not frappe.db.exists("Purchase Invoice", data.REVERSE_CHARGE_INVOICE):
		insert_record(
			"Purchase Invoice",
			name=data.REVERSE_CHARGE_INVOICE,
			company=data.COMPANY,
			posting_date=INVOICE_DATE,
			supplier=data.EU_SUPPLIER,
			supplier_name=data.EU_SUPPLIER,
			docstatus=1,
			is_opening="No",
		)
		post_ledger(
			data.COMPANY,
			"Purchase Invoice",
			data.REVERSE_CHARGE_INVOICE,
			INVOICE_DATE,
			[
				(a["3123"], data.REVERSE_CHARGE_NET, 0),
				(a["1577"], data.REVERSE_CHARGE_TAX, 0),
				(a["1787"], 0, data.REVERSE_CHARGE_TAX),
				(a["1600"], 0, data.REVERSE_CHARGE_NET),
			],
		)


def customer(name: str, country: str, tax_id: str | None = None, **fields) -> str:
	"""The customer with its address in the country, made if there is none; returns the address."""
	if frappe.db.exists("Customer", name):
		return frappe.db.get_value("Customer", name, "customer_primary_address")
	return make_customer(name, country, tax_id, **fields)


def confirm_eu_vat_id() -> None:
	"""A valid answer of the BZSt for the USt-IdNr. of the EU customer, from the fake transport of the tests of
	steuerbote.vatid, so that the line of the Zusammenfassende Meldung is confirmed and no query leaves the site."""
	if frappe.db.exists("VAT ID Confirmation", {"company": data.COMPANY, "requested": data.EU_VAT_ID}):
		return
	answer = confirm(data.EU_VAT_ID, data.OWN_VAT_ID, None, FakeFetch(bzst("evatr-0000")), FakeClock())
	store(answer, data.COMPANY)


def file_previous_month() -> None:
	"""The VAT Return of FILED_MONTH, filed in Mein ELSTER: the filing leaves an ELSTER Transmission."""
	filters = {"company": data.COMPANY, "year": data.YEAR, "period_index": data.FILED_MONTH, "docstatus": 1}
	if frappe.db.exists("VAT Return", filters):
		return
	doc = vat_return(data.FILED_MONTH)
	doc.calculate()
	doc.reload()
	doc.mark_filed_outside(filed_via=FILED_IN_MEIN_ELSTER)


def calculate_vat_return() -> None:
	doc = vat_return(data.MONTH)
	doc.calculate()


def vat_return(month: int) -> Document:
	"""The draft VAT Return of the month, made if there is none."""
	return draft(
		"VAT Return",
		{"company": data.COMPANY, "year": data.YEAR, "rhythm": "monthly", "period_index": month},
	)


def calculate_recapitulative_statement() -> None:
	doc = draft(
		"Recapitulative Statement",
		{"company": data.COMPANY, "year": data.YEAR, "period_kind": "month", "period_index": data.MONTH},
	)
	doc.calculate()


def make_extension() -> None:
	"""The Dauerfristverlängerung of the year as a draft: no Voranmeldung of the year before is filed, so
	Berechnen asks for the base by hand, which the test of the form expects."""
	draft("VAT Return Extension", {"company": data.COMPANY, "year": data.YEAR})


def draft(doctype: str, fields: dict) -> Document:
	"""The draft document with the fields, made if there is none."""
	name = frappe.db.get_value(doctype, {**fields, "docstatus": 0})
	if name:
		return frappe.get_doc(doctype, name)
	return frappe.get_doc({"doctype": doctype, **fields}).insert()


def simulate_eric() -> None:
	"""ERiC Settings without runtime and Hersteller-ID: Prüfen and Testsenden only simulate."""
	settings = frappe.get_single("ERiC Settings")
	settings.update(
		{
			"hersteller_id": "",
			"datenlieferant": "",
			"installed_version": "",
			"lib_dir": "",
			"log_dir": "",
			"privacy_notice_confirmed": 0,
		}
	)
	settings.save()


def make_desk_users() -> None:
	make_user(data.ACCOUNTANT, data.ACCOUNTANT_ROLE)
	for user in ("Administrator", data.ACCOUNTANT):
		frappe.db.set_value("User", user, "language", DESK_LANGUAGE)
		frappe.defaults.set_user_default("company", data.COMPANY, user)
