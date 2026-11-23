"""The data of the browser tests on a test site, made with the helpers of the Frappe tests:

	bench --site <site> execute steuerbote.tests.e2e.seed.run

A company with SKR03 accounts, its VAT Return Settings and the mapping of "Vorgaben laden", three invoices of
October 2026, a VAT ID Confirmation, a VAT Return for September filed in Mein ELSTER, a calculated VAT Return and
Recapitulative Statement for October, a draft Dauerfristverlängerung for 2026, ERiC Settings that simulate and a user
with the role Accounts User alone. A second company without accounts has the drafts of October and of 2026 that went
to ELSTER, each with the record of its Senden. A third company has SKR03 accounts and nothing else, for Steuerbote
einrichten, and a fourth has SKR03 accounts and the mapping of "Vorgaben laden", for Vorgaben aktualisieren. Every record is invented (steuerbote/tests/e2e/data.py) and made once,
so the seed runs again on the same site without a change; a second run only calculates the documents of the first
company again. It also marks the setup wizard complete and sets the language of the Administrator and the user to
German, so that the desk opens as a German accountant sees it. Take a site of its own for it, never one with real
data.

Of the annual filings, the seed makes the Umsatzsteuererklärung of the first company for 2026 and calculates it.
A fifth company has SKR03 accounts, Annual Filing Settings, the Kontenzuordnung Ertragsteuern of "Vorgaben laden"
and a ledger of 2026, with its Körperschaft- and Gewerbesteuererklärung for the year, calculated; nothing of it
goes to ELSTER.

A sixth company has Annual Filing Settings and its Jahresabschluss for the year, calculated from the balances of the
invented Kleinstkapitalgesellschaft of steuerbote/hgb/tests/companies.py, which the seed hands Berechnen in place of
the books, since the site has no HGB-Taxonomie to place them with. The Print Settings write PDF files with PlutoPrint,
which needs no browser on the server.
"""

from datetime import date
from unittest.mock import patch

import frappe
from frappe.model.document import Document
from frappe.utils import today

from steuerbote import annual_accounts_sources
from steuerbote.hgb.tests import companies
from steuerbote.steuerbote.doctype.elster_transmission.elster_transmission import SEND, SUCCEEDED, UNKNOWN
from steuerbote.steuerbote.doctype.vat_id_confirmation.vat_id_confirmation import store
from steuerbote.tests import income_tax
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
# SKR03 numbers of the company that Steuerbote einrichten sets up: those that tell the chart and a watched account.
SETUP_ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1548": ("Vorsteuer im Folgejahr abziehbar", "Asset"),
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
	calculate_annual_vat_return()
	make_income_tax_returns()
	make_annual_accounts()
	make_sent_drafts()
	make_setup_company()
	make_mapping_company()
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


def make_settings_once(company: str = data.COMPANY) -> None:
	"""Monthly filing with Dauerfristverlängerung, and the ZM monthly with the sonstige Leistungen in their own
	month, through all of the year."""
	if frappe.db.exists("VAT Return Settings", company):
		return
	make_settings(
		company,
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


def make_sent_drafts() -> None:
	"""The drafts of SENT_COMPANY as the background job leaves them after a real Senden (transmission.py): ELSTER
	accepted the VAT Return and the Dauerfristverlängerung, but submitting them failed, and whether the
	Recapitulative Statement reached ELSTER is unknown. The return and the statement are calculated first, as only a
	calculated document is sent; the Dauerfristverlängerung has no filed Voranmeldung of the year before that
	Berechnen could read."""
	company = data.SENT_COMPANY
	make_company(company, data.SENT_ABBR)
	make_settings_once(company)
	if not frappe.db.exists("VAT Return Mapping", company):
		make_mapping(company)
	month = {"company": company, "year": data.YEAR, "period_index": data.MONTH}
	sent_once(draft("VAT Return", {**month, "rhythm": "monthly"}), SUCCEEDED, calculate=True)
	sent_once(draft("Recapitulative Statement", {**month, "period_kind": "month"}), UNKNOWN, calculate=True)
	sent_once(draft("VAT Return Extension", {"company": company, "year": data.YEAR}), SUCCEEDED)


def make_setup_company() -> None:
	"""The company of Steuerbote einrichten: accounts only. Its browser test removes what an earlier run set up."""
	make_company(data.SETUP_COMPANY, data.SETUP_ABBR)
	for number, (name, root_type) in SETUP_ACCOUNTS.items():
		if not frappe.db.exists("Account", {"company": data.SETUP_COMPANY, "account_number": number}):
			make_account(data.SETUP_COMPANY, number, name, root_type)


def make_mapping_company() -> None:
	"""The company of Vorgaben aktualisieren: the accounts of Steuerbote einrichten and the mapping of their defaults."""
	make_company(data.MAPPING_COMPANY, data.MAPPING_ABBR)
	for number, (name, root_type) in {
		**SETUP_ACCOUNTS,
		"8603": ("Sonstige betriebliche Erträge", "Income"),
	}.items():
		if not frappe.db.exists("Account", {"company": data.MAPPING_COMPANY, "account_number": number}):
			make_account(data.MAPPING_COMPANY, number, name, root_type)
	if not frappe.db.exists("VAT Return Mapping", data.MAPPING_COMPANY):
		make_mapping(data.MAPPING_COMPANY)


def sent_once(doc: Document, status: str, calculate: bool = False) -> None:
	"""The record of a real Senden of the draft with the status, unless it has one: a simulated run reaches no
	Finanzamt and keeps nothing (filings in transmission.py)."""
	if doc.sent_record():
		return
	if calculate:
		doc.calculate()
	transferticket = data.TRANSFERTICKET if status == SUCCEEDED else None
	doc.new_transmission(SEND, simulated=False, status=status, transferticket=transferticket)


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


def calculate_annual_vat_return() -> None:
	"""The Umsatzsteuererklärung of the year, calculated: of its Voranmeldungen only that of FILED_MONTH is filed, so
	Berechnen finds every other month without its Voranmeldung and leaves the return Berechnet, not Bereit."""
	doc = draft("Annual VAT Return", {"company": data.COMPANY, "year": data.YEAR})
	doc.calculate()


# SKR03 numbers of the company of the Körperschaft- and the Gewerbesteuererklärung: revenue, salaries and rent, the
# taxes on income with their provisions, and a bank.
INCOME_TAX_ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"4120": ("Gehälter", "Expense"),
	"4210": ("Miete (unbewegliche Wirtschaftsgüter)", "Expense"),
	"2200": ("Körperschaftsteuer", "Expense"),
	"2208": ("Solidaritätszuschlag", "Expense"),
	"4320": ("Gewerbesteuer", "Expense"),
	"0963": ("Körperschaftsteuerrückstellung", "Liability"),
	"0956": ("Gewerbesteuerrückstellung nach § 4 Abs. 5b EStG", "Liability"),
	"1200": ("Bank", "Asset"),
}
# Its year: revenue of 150,000 euros, salaries of 60,000 and rent of 18,000, and the Vorauszahlungen of its notices,
# 2,500 euros Körperschaftsteuer with 137.50 Solidaritätszuschlag and 2,000 euros Gewerbesteuer a quarter.
INCOME_TAX_LEDGER = (
	("JV-STE2K-ERLOES", f"{data.YEAR}-06-30", (("8400", 0, 150000), ("1200", 150000, 0))),
	("JV-STE2K-GEHALT", f"{data.YEAR}-12-31", (("4120", 60000, 0), ("1200", 0, 60000))),
	("JV-STE2K-MIETE", f"{data.YEAR}-12-31", (("4210", 18000, 0), ("1200", 0, 18000))),
	*(
		(
			f"JV-STE2K-VZ-KST-{month}",
			f"{data.YEAR}-{month:02d}-10",
			(("2200", 2500, 0), ("2208", "137.50", 0), ("1200", 0, "2637.50")),
		)
		for month in (3, 6, 9, 12)
	),
	*(
		(f"JV-STE2K-VZ-GEWST-{month}", f"{data.YEAR}-{month:02d}-15", (("4320", 2000, 0), ("1200", 0, 2000)))
		for month in (2, 5, 8, 11)
	),
)
INCOME_TAX_AGS = "09999999"
INCOME_TAX_SETTINGS = {
	"legal_form": "GmbH",
	"business_purpose": "IT-Beratung",
	"management_seat": "Musterstadt",
	"registered_seat": "Musterstadt",
	"street": "Musterstraße",
	"house_number": "1",
	"postal_code": "12345",
	"city": "Musterstadt",
	"country": "Germany",
	"income_tax_review_on": f"{data.YEAR}-11-02",
	"shareholders": [
		{
			"shareholder_name": "Max Mustermann",
			"kind": "Natural Person",
			"percent": 100,
			"nominal_amount": 25000,
			"from_date": "2020-01-01",
			"street": "Musterstraße 2",
			"postal_code_and_town": "12345 Musterstadt",
		}
	],
	"establishments": [
		{
			"municipality": "Musterstadt",
			"postal_code": "12345",
			"ags": INCOME_TAX_AGS,
			"from_date": "2020-01-01",
		}
	],
	"trade_tax_rates": [
		{
			"ags": INCOME_TAX_AGS,
			"year": data.YEAR,
			"hebesatz": 400,
			"source": f"Haushaltssatzung {data.YEAR} der Gemeinde Musterstadt",
		}
	],
	"prepayments": [
		*(
			{"tax": tax, "year": data.YEAR, "due_date": f"{data.YEAR}-{month:02d}-10", "amount": amount}
			for tax, amount in (("KSt", 2500), ("SolZ", 137.5))
			for month in (3, 6, 9, 12)
		),
		*(
			{"tax": "GewSt", "year": data.YEAR, "due_date": f"{data.YEAR}-{month:02d}-15", "amount": 2000}
			for month in (2, 5, 8, 11)
		),
	],
}


def make_income_tax_returns() -> None:
	"""The company of INCOME_TAX_COMPANY with its Körperschaft- and Gewerbesteuererklärung of the year, calculated: the
	forms of the year are provisional, so Berechnen leaves both Berechnet with the finding that says so."""
	company = data.INCOME_TAX_COMPANY
	make_company(company, data.INCOME_TAX_ABBR)
	accounts = income_tax.make_accounts(company, INCOME_TAX_ACCOUNTS)
	ensure_fiscal_year(company, INVOICE_DATE)
	if not frappe.db.exists("Annual Filing Settings", company):
		frappe.get_doc(
			{"doctype": "Annual Filing Settings", "company": company, **INCOME_TAX_SETTINGS}
		).insert(ignore_permissions=True)
	income_tax.make_income_tax_mapping(company)
	for voucher_no, posting_date, rows in INCOME_TAX_LEDGER:
		income_tax.post_once(company, accounts, "Journal Entry", voucher_no, posting_date, rows)
	draft("Corporate Income Tax Return", {"company": company, "year": data.YEAR}).calculate()
	draft("Trade Tax Return", {"company": company, "year": data.YEAR}).calculate()


ACCOUNTS_SETTINGS = {
	"legal_form": "GmbH",
	"registered_seat": "Musterstadt",
	"register_court": "Amtsgericht Musterstadt",
	"register_type": "HRB",
	"register_number": "99905",
	"street": "Musterweg",
	"house_number": "12",
	"postal_code": "12345",
	"city": "Musterstadt",
	"country": "Germany",
	"directors": [
		{
			"director_name": data.ACCOUNTS_DIRECTOR,
			"role": "Geschäftsführerin",
			"from_date": "2020-01-01",
			"signs": 1,
		}
	],
}


def make_annual_accounts() -> None:
	"""The company of ACCOUNTS_COMPANY with its Jahresabschluss of the year, calculated from the balances of the invented
	Kleinstkapitalgesellschaft; the Angaben, the Feststellung and the signatures stay open."""
	company = data.ACCOUNTS_COMPANY
	make_company(company, data.ACCOUNTS_ABBR)
	ensure_fiscal_year(company, INVOICE_DATE)
	if not frappe.db.exists("Annual Filing Settings", company):
		frappe.get_doc({"doctype": "Annual Filing Settings", "company": company, **ACCOUNTS_SETTINGS}).insert(
			ignore_permissions=True
		)
	sources = annual_accounts_sources.Sources(
		companies.KLEINST_2026,
		companies.KLEINST_2025,
		(date(data.YEAR - 1, 1, 1), date(data.YEAR - 1, 12, 31)),
		companies.PARENTS,
		(),
		"SKR03",
		None,
	)
	with patch.object(annual_accounts_sources, "statement_sources", return_value=sources):
		draft("Annual Accounts", {"company": company, "year": data.YEAR}).calculate()
	frappe.db.set_single_value("Print Settings", "pdf_generator", "PlutoPrint")
