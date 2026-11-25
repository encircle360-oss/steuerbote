"""The invoices of a company and period as the invoice lines of steuerbote.ustva.plausibility.

The Umsatzsteuer-Voranmeldung is computed from the ledger alone (steuerbote.ledger); the invoices only feed
its hints. A line is what one submitted invoice books on one account: the net amount of its items there and
the tax ERPNext computed for these items (Item Wise Tax Detail, one row per item and tax), both in company
currency, with the party, the country of the invoice's address and the party's VAT id from the Customer or
Supplier. Sales Invoices give their items' income accounts, Purchase Invoices their expense accounts. A
return carries negative amounts, as ERPNext stores it. Like the ledger query, the lines keep to the posting
dates of the period and leave out invoices marked as opening entries. Only the accounts asked for are read,
with two queries per kind of invoice, through Frappe's query builder with parameters.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import frappe
from frappe.query_builder.functions import Sum

from steuerbote.ustva.plausibility import AssetSale, InvoiceLine
from steuerbote.ustva.rounding import CENT, ZERO


@dataclass(frozen=True, slots=True)
class _Invoices:
	"""Where a kind of invoice keeps what a line needs."""

	doctype: str
	items: str
	account: str
	party: str
	party_name: str
	party_doctype: str
	address: str


SALES = _Invoices(
	"Sales Invoice",
	"Sales Invoice Item",
	"income_account",
	"customer",
	"customer_name",
	"Customer",
	"customer_address",
)
PURCHASES = _Invoices(
	"Purchase Invoice",
	"Purchase Invoice Item",
	"expense_account",
	"supplier",
	"supplier_name",
	"Supplier",
	"supplier_address",
)


def load_lines(
	company: str,
	from_date: date | str,
	to_date: date | str,
	sales_accounts: Collection[str],
	purchase_accounts: Collection[str],
	sales_invoices: Collection[str] | None = None,
) -> list[InvoiceLine]:
	"""The lines of the company's submitted invoices from ``from_date`` to ``to_date``, both included, on the
	given account numbers: sales invoices first, each kind by posting date, invoice and account. ``sales_invoices``
	names the Sales Invoices to read instead of those posted in the time: those the Voranmeldung reports in its
	period, which by service date need not be posted in it (steuerbote.vat_periods)."""
	return [
		*_lines(SALES, company, from_date, to_date, sales_accounts, sales_invoices),
		*_lines(PURCHASES, company, from_date, to_date, purchase_accounts),
	]


def _lines(
	kind: _Invoices,
	company: str,
	from_date: date | str,
	to_date: date | str,
	accounts: Collection[str],
	names: Collection[str] | None = None,
) -> list[InvoiceLine]:
	if not accounts:
		return []
	taxes = {
		(row.voucher_no, row.account_number): _cents(row.tax_amount)
		for row in _taxes(kind, company, from_date, to_date, accounts, names)
	}
	return [
		InvoiceLine(
			voucher_type=kind.doctype,
			voucher_no=row.voucher_no,
			posting_date=row.posting_date,
			party=row.party_name or row.party,
			party_country=row.country,
			party_tax_id=row.tax_id,
			account_number=row.account_number.strip(),
			net_amount=_cents(row.net_amount),
			tax_amount=taxes.get((row.voucher_no, row.account_number), ZERO),
			is_return=bool(row.is_return),
		)
		for row in _nets(kind, company, from_date, to_date, accounts, names)
	]


def _items(
	kind: _Invoices,
	company: str,
	from_date: date | str,
	to_date: date | str,
	accounts: Collection[str],
	names: Collection[str] | None,
):
	"""The items of the period's submitted invoices, or of the invoices ``names``, on the accounts, with their invoice
	and account."""
	invoice = frappe.qb.DocType(kind.doctype)
	item = frappe.qb.DocType(kind.items)
	account = frappe.qb.DocType("Account")
	query = (
		frappe.qb.from_(item)
		.inner_join(invoice)
		.on(invoice.name == item.parent)
		.inner_join(account)
		.on(account.name == item[kind.account])
		.where(item.parenttype == kind.doctype)
		.where(invoice.company == company)
		.where(invoice.docstatus == 1)
		.where(invoice.is_opening == "No")
		.where(account.account_number.isin(list(accounts)))
	)
	if names is None:
		query = query.where(invoice.posting_date.between(from_date, to_date))
	else:
		query = query.where(invoice.name.isin(sorted(names) or [""]))
	return query, invoice, item, account


def _nets(
	kind: _Invoices,
	company: str,
	from_date: date | str,
	to_date: date | str,
	accounts: Collection[str],
	names: Collection[str] | None,
):
	query, invoice, item, account = _items(kind, company, from_date, to_date, accounts, names)
	party = frappe.qb.DocType(kind.party_doctype)
	address = frappe.qb.DocType("Address")
	columns = (
		invoice.name,
		invoice.posting_date,
		invoice.is_return,
		invoice[kind.party],
		invoice[kind.party_name],
		party.tax_id,
		address.country,
		account.account_number,
	)
	return (
		query.left_join(party)
		.on(party.name == invoice[kind.party])
		.left_join(address)
		.on(address.name == invoice[kind.address])
		.select(
			invoice.name.as_("voucher_no"),
			invoice.posting_date,
			invoice.is_return,
			invoice[kind.party].as_("party"),
			invoice[kind.party_name].as_("party_name"),
			party.tax_id,
			address.country,
			account.account_number,
			Sum(item.base_net_amount).as_("net_amount"),
		)
		.groupby(*columns)
		.orderby(invoice.posting_date)
		.orderby(invoice.name)
		.orderby(account.account_number)
		.run(as_dict=True)
	)


def _taxes(
	kind: _Invoices,
	company: str,
	from_date: date | str,
	to_date: date | str,
	accounts: Collection[str],
	names: Collection[str] | None,
):
	"""The tax of the items per invoice and account; ERPNext keeps a deducted tax, such as the § 13b tax a
	purchase invoice adds and deducts again, as a negative amount."""
	query, invoice, item, account = _items(kind, company, from_date, to_date, accounts, names)
	tax = frappe.qb.DocType("Item Wise Tax Detail")
	return (
		query.inner_join(tax)
		.on((tax.item_row == item.name) & (tax.parent == invoice.name) & (tax.parenttype == kind.doctype))
		.select(invoice.name.as_("voucher_no"), account.account_number, Sum(tax.amount).as_("tax_amount"))
		.groupby(invoice.name, account.account_number)
		.run(as_dict=True)
	)


def _cents(amount: float | Decimal | None) -> Decimal:
	"""Currency values arrive as floats; through their shortest repr they become the cents they were stored in."""
	return Decimal(str(amount or 0)).quantize(CENT)


def asset_sales_without_tax(
	company: str, from_date: date | str, to_date: date | str, names: Collection[str] | None = None
) -> list[AssetSale]:
	"""The company's submitted Sales Invoices without tax that sell a fixed asset through the row with the Asset
	(is_fixed_asset and asset of Sales Invoice Item, ERPNext 16), each with the price of its asset rows, by invoice;
	returns and opening entries are left out. ``names`` as for load_lines."""
	invoice = frappe.qb.DocType(SALES.doctype)
	item = frappe.qb.DocType(SALES.items)
	party = frappe.qb.DocType(SALES.party_doctype)
	address = frappe.qb.DocType("Address")
	query = (
		frappe.qb.from_(item)
		.inner_join(invoice)
		.on(invoice.name == item.parent)
		.left_join(party)
		.on(party.name == invoice[SALES.party])
		.left_join(address)
		.on(address.name == invoice[SALES.address])
		.where(item.parenttype == SALES.doctype)
		.where(invoice.company == company)
		.where(invoice.docstatus == 1)
		.where(invoice.is_opening == "No")
		.where(invoice.is_return == 0)
		.where(invoice.base_total_taxes_and_charges == 0)
		.where(item.is_fixed_asset == 1)
		.where(item.asset.isnotnull() & (item.asset != ""))
	)
	if names is None:
		query = query.where(invoice.posting_date.between(from_date, to_date))
	else:
		query = query.where(invoice.name.isin(sorted(names) or [""]))
	columns = (invoice.name, invoice[SALES.party], invoice[SALES.party_name], party.tax_id, address.country)
	rows = (
		query.select(*columns, Sum(item.base_net_amount).as_("net_amount"))
		.groupby(*columns)
		.orderby(invoice.name)
		.run(as_dict=True)
	)
	return [
		AssetSale(
			voucher_no=row.name,
			party=row[SALES.party_name] or row[SALES.party],
			party_country=row.country,
			party_tax_id=row.tax_id,
			net_amount=_cents(row.net_amount),
		)
		for row in rows
	]
