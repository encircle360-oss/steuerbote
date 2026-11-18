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
) -> Document:
	"""VAT Return Settings with rules (year, rhythm, valid from month) and prepayments (year,
	Dauerfristverlängerung, Sondervorauszahlung), under an invented Steuernummer of Bayern."""
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
		}
	).insert(ignore_permissions=True)


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
