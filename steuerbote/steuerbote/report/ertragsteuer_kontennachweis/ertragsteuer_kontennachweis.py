"""Ertragsteuer-Kontennachweis: the ledger entries behind each line of the Körperschaftsteuer- and the
Gewerbesteuererklärung of a company for a year.

The report reads what Berechnen of the Corporate Income Tax Return reads, the profit and loss account of the
Wirtschaftsjahr that ends in the year and the Income Tax Mapping of the company (steuerbote/income_tax_sources.py);
attribution.py lays out the postings behind each line. The module looks up the accounts and the posting dates.
"""

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, getdate

from steuerbote import income_tax_sources
from steuerbote.kst import provisions
from steuerbote.ledger import account_names
from steuerbote.steuerbote.annual_filing import fiscal_year_ending_in
from steuerbote.steuerbote.report.ertragsteuer_kontennachweis import attribution

FILTERS = ("company", "year")


def execute(filters: dict | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	filters = frappe._dict(filters or {})
	if any(filters.get(name) in (None, "") for name in FILTERS):
		return get_columns(), []
	company = filters.company
	frappe.has_permission("Company", "read", doc=company, throw=True)
	fiscal_year = fiscal_year_ending_in(company, cint(filters.year))
	mapping = income_tax_sources.mapping(company)
	ledger = income_tax_sources.ledger(
		company,
		getdate(fiscal_year.year_start_date),
		getdate(fiscal_year.year_end_date),
		provisions.ACCOUNTS.get(mapping.chart),
		income_tax_sources.commercial_finance_book(company),
	)
	numbers = {line.account_number for line in ledger.lines}
	currency = frappe.get_cached_value("Company", company, "default_currency")
	rows = attribution.report_rows(
		ledger,
		mapping,
		account_names(company, numbers),
		income_tax_sources.posting_dates(company, attribution.vouchers(ledger)),
		_,
	)
	return get_columns(), [{**row, "currency": currency} for row in rows]


def get_columns() -> list[dict[str, Any]]:
	money = {"fieldtype": "Currency", "options": "currency", "width": 130}
	return [
		{"fieldname": "line", "label": _("Form Line"), "fieldtype": "Data", "width": 130},
		{"fieldname": "feldkennung", "label": _("Field Code"), "fieldtype": "Data", "width": 100},
		{"fieldname": "label", "label": _("Label"), "fieldtype": "Data", "width": 300},
		{"fieldname": "amount", "label": _("Ledger Amount"), **money},
		{
			"fieldname": "account",
			"label": _("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"width": 220,
		},
		{"fieldname": "posting_date", "label": _("Posting Date"), "fieldtype": "Date", "width": 110},
		{
			"fieldname": "voucher_type",
			"label": _("Voucher Type"),
			"fieldtype": "Link",
			"options": "DocType",
			"width": 130,
		},
		{
			"fieldname": "voucher_no",
			"label": _("Voucher No"),
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 170,
		},
		{"fieldname": "debit", "label": _("Debit"), **money},
		{"fieldname": "credit", "label": _("Credit"), **money},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
	]
