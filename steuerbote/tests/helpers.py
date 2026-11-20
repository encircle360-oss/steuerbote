"""Test data for the Frappe tests: companies, accounts, journal entries, VAT Return Settings and Mapping.

Every test module builds a company of its own with exactly the accounts it needs, so no test depends on
ERPNext's test records or on another module's data.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import frappe
from erpnext.accounts.utils import get_fiscal_year
from frappe.model.document import Document
from frappe.utils import getdate

from steuerbote.ledger import EXCLUDE_FIELD

ROOT_ACCOUNTS = {
	"Asset": "Assets",
	"Liability": "Liabilities",
	"Equity": "Equity",
	"Income": "Income",
	"Expense": "Expenses",
}

type Amount = Decimal | float | int | str


def make_company(name: str, abbr: str, currency: str = "EUR", country: str = "Germany") -> str:
	"""A company without ERPNext's chart of accounts; make_account adds the accounts a test needs."""
	if frappe.db.exists("Company", name):
		return name
	company = frappe.new_doc("Company")
	company.update({"company_name": name, "abbr": abbr, "default_currency": currency, "country": country})
	frappe.local.flags.ignore_chart_of_accounts = True
	try:
		company.insert(ignore_permissions=True)
	finally:
		frappe.local.flags.ignore_chart_of_accounts = False
	return company.name


def make_account(
	company: str, number: str | None, name: str, root_type: str, parent: str | None = None, **fields
) -> str:
	"""A ledger account; without a parent it goes under the company's root group of its root type."""
	account = frappe.get_doc(
		{
			"doctype": "Account",
			"company": company,
			"account_number": number,
			"account_name": name,
			"parent_account": parent or _root_account(company, root_type),
			"is_group": 0,
			**fields,
		}
	)
	account.insert(ignore_permissions=True)
	return account.name


def _root_account(company: str, root_type: str) -> str:
	account_name = ROOT_ACCOUNTS[root_type]
	existing = frappe.db.get_value(
		"Account",
		{
			"company": company,
			"account_name": account_name,
			"is_group": 1,
			"parent_account": ["is", "not set"],
		},
	)
	if existing:
		return existing
	root = frappe.get_doc(
		{
			"doctype": "Account",
			"company": company,
			"account_name": account_name,
			"is_group": 1,
			"root_type": root_type,
		}
	)
	# parent_account is mandatory on the form, and a root account has none.
	root.flags.ignore_mandatory = True
	root.insert(ignore_permissions=True)
	return root.name


def post_journal_entry(
	company: str,
	posting_date: date | str,
	rows: Iterable[tuple[str, Amount, Amount]],
	exclude: bool = False,
	**fields,
) -> Document:
	"""A submitted journal entry with one row per (account, debit, credit).

	``exclude`` sets the flag that leaves the entry out of the Umsatzsteuer-Voranmeldung; ``fields`` go to
	the entry itself, such as ``voucher_type="Opening Entry"``.
	"""
	_ensure_fiscal_year(company, posting_date)
	cost_center = frappe.db.get_value("Company", company, "cost_center")
	entry = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"company": company,
			"posting_date": posting_date,
			EXCLUDE_FIELD: int(exclude),
			"accounts": [
				{
					"account": account,
					"debit_in_account_currency": debit,
					"credit_in_account_currency": credit,
					"cost_center": cost_center,
				}
				for account, debit, credit in rows
			],
			**fields,
		}
	)
	entry.insert(ignore_permissions=True)
	entry.submit()
	return entry


def make_settings(
	company: str,
	period_rules: Iterable[tuple[int, str, int]],
	prepayments: Iterable[tuple[int, bool, Amount]] = (),
	**fields,
) -> Document:
	"""VAT Return Settings with rules (year, rhythm, valid from month) and prepayments (year,
	Dauerfristverlängerung, Sondervorauszahlung), under an invented Steuernummer of Bayern; ``fields`` go to
	the settings themselves, such as the Datenlieferant."""
	return frappe.get_doc(
		{
			"doctype": "VAT Return Settings",
			"company": company,
			"state": "Bayern",
			"tax_number": "123/456/78901",
			"period_rules": [
				{"year": year, "rhythm": rhythm, "valid_from_month": month}
				for year, rhythm, month in period_rules
			],
			"prepayments": [
				{"year": year, "dauerfristverlaengerung": int(dauerfrist), "sondervorauszahlung": amount}
				for year, dauerfrist, amount in prepayments
			],
			**fields,
		}
	).insert(ignore_permissions=True)


def submitted_without_record(vat_return: Document) -> None:
	"""Submit a VAT Return the way returns were submitted before Steuerbote recorded every filing: without
	an ELSTER Transmission."""
	vat_return.flags.filed_outside = True
	vat_return.submit()


def make_mapping(company: str, chart: str = "SKR03") -> Document:
	"""A VAT Return Mapping with the defaults of the chart for the accounts the company has."""
	mapping = frappe.new_doc("VAT Return Mapping")
	mapping.update({"company": company, "chart": chart})
	mapping.load_defaults()
	return mapping.insert(ignore_permissions=True)


def _ensure_fiscal_year(company: str, posting_date: date | str) -> None:
	if get_fiscal_year(posting_date, company=company, raise_on_missing=False):
		return
	year = getdate(posting_date).year
	frappe.get_doc(
		{
			"doctype": "Fiscal Year",
			"year": str(year),
			"year_start_date": date(year, 1, 1),
			"year_end_date": date(year, 12, 31),
		}
	).insert(ignore_permissions=True)


def insert_record(doctype: str, **fields) -> str:
	"""A record written as ERPNext keeps it once submitted, without the validations of its form.

	Submitting real invoices and payments needs items, price lists and a chart of accounts with receivables that
	neither the ledger nor the Zusammenfassende Meldung reads, so their rows are written as ERPNext stores them.
	"""
	doc = frappe.get_doc({"doctype": doctype, **fields})
	doc.db_insert()
	return doc.name


def make_customer(
	name: str, country: str, tax_id: str | None = None, city: str = "Teststadt", primary: bool = True
) -> str:
	"""A customer with an address in the country, which is its primary address or, without ``primary``, only
	linked to it; returns the address."""
	address = insert_record(
		"Address",
		name=f"{name}-Billing",
		address_title=name,
		address_type="Billing",
		address_line1="Teststraße 1",
		pincode="12345",
		city=city,
		country=country,
		is_primary_address=1,
	)
	insert_record(
		"Dynamic Link",
		name=f"{address}-Link",
		parent=address,
		parenttype="Address",
		parentfield="links",
		idx=1,
		link_doctype="Customer",
		link_name=name,
	)
	insert_record(
		"Customer",
		name=name,
		customer_name=name,
		tax_id=tax_id,
		customer_primary_address=address if primary else None,
	)
	return address


def post_ledger(
	company: str,
	voucher_type: str,
	voucher_no: str,
	posting_date: str,
	rows: Iterable[tuple[str, Amount, Amount]],
) -> None:
	"""The GL Entries of a voucher, one per (account, debit, credit)."""
	for account, debit, credit in rows:
		insert_record(
			"GL Entry",
			company=company,
			posting_date=posting_date,
			account=account,
			debit=debit,
			credit=credit,
			voucher_type=voucher_type,
			voucher_no=voucher_no,
			is_cancelled=0,
			is_opening="No",
			docstatus=1,
		)


def post_sales_invoice(
	company: str,
	name: str,
	customer: str,
	posting_date: str,
	rows: Iterable[tuple[str, Amount, Amount]],
	**fields,
) -> str:
	"""A submitted Sales Invoice with the customer's tax_id, as ERPNext fetches it, and its GL Entries; ``fields``
	go to the invoice, such as its addresses."""
	insert_record(
		"Sales Invoice",
		name=name,
		company=company,
		posting_date=posting_date,
		customer=customer,
		customer_name=customer,
		tax_id=frappe.db.get_value("Customer", customer, "tax_id"),
		docstatus=1,
		is_opening="No",
		**fields,
	)
	post_ledger(company, "Sales Invoice", name, posting_date, rows)
	return name


def post_payment_entry(
	company: str,
	name: str,
	customer: str,
	posting_date: str,
	invoices: Iterable[str],
	rows: Iterable[tuple[str, Amount, Amount]],
) -> str:
	"""A submitted Payment Entry of a customer that pays the Sales Invoices, with its GL Entries."""
	insert_record(
		"Payment Entry",
		name=name,
		company=company,
		posting_date=posting_date,
		payment_type="Receive",
		party_type="Customer",
		party=customer,
		party_name=customer,
		docstatus=1,
	)
	for index, invoice in enumerate(invoices, start=1):
		insert_record(
			"Payment Entry Reference",
			name=f"{name}-{index}",
			parent=name,
			parenttype="Payment Entry",
			parentfield="references",
			idx=index,
			reference_doctype="Sales Invoice",
			reference_name=invoice,
		)
	post_ledger(company, "Payment Entry", name, posting_date, rows)
	return name


def post_customer_journal_entry(
	company: str, name: str, posting_date: str, rows: Iterable[tuple[str, Amount, Amount, str | None]]
) -> str:
	"""A submitted Journal Entry with one row per (account, debit, credit, customer or None) and its GL Entries."""
	rows = list(rows)
	insert_record(
		"Journal Entry",
		name=name,
		company=company,
		posting_date=posting_date,
		voucher_type="Journal Entry",
		docstatus=1,
	)
	for index, (account, debit, credit, customer) in enumerate(rows, start=1):
		insert_record(
			"Journal Entry Account",
			name=f"{name}-{index}",
			parent=name,
			parenttype="Journal Entry",
			parentfield="accounts",
			idx=index,
			account=account,
			debit=debit,
			credit=credit,
			party_type="Customer" if customer else None,
			party=customer,
		)
	post_ledger(company, "Journal Entry", name, posting_date, [row[:3] for row in rows])
	return name
