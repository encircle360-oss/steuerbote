"""Invented Sales Invoices with the time of their entry, Delivery Notes and filed returns, for the tests of the
assignment to the Voranmeldungszeitraum (test_vat_periods.py, vat_return/test_period_assignment.py)."""

from decimal import Decimal

import frappe

from steuerbote.tests.helpers import insert_record
from steuerbote.ustva import Period

ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"8125": ("Steuerfreie innergemeinschaftliche Lieferungen", "Income"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
	"1200": ("Bank", "Asset"),
	"3123": ("Sonstige Leistungen EU 19 %", "Expense"),
	"1787": ("Umsatzsteuer nach § 13b UStG 19 %", "Liability"),
	"1577": ("Vorsteuer nach § 13b UStG 19 %", "Asset"),
	"4980": ("Betriebsbedarf", "Expense"),
}
FILING_NOTE = "Erfunden: abgegeben in Mein ELSTER."


def sales_invoice(
	company: str,
	accounts: dict[str, str],
	name: str,
	posting: str,
	booked: str,
	net: str = "1000.00",
	tax: str = "190.00",
	revenue: str = "8400",
	**fields,
) -> str:
	"""A submitted Sales Invoice with its GL Entries on receivables, ``revenue`` and 1776, entered at ``booked``;
	returns its voucher key. ``fields`` go to the invoice, such as to_date or is_return."""
	insert_record(
		"Sales Invoice",
		name=name,
		company=company,
		posting_date=posting,
		customer="Testkunde",
		customer_name="Testkunde",
		docstatus=1,
		**fields,
	)
	gross = Decimal(net) + Decimal(tax)
	for account, debit, credit in (
		(accounts["1400"], gross, 0),
		(accounts[revenue], 0, net),
		(accounts["1776"], 0, tax),
	):
		if debit or credit:
			insert_record(
				"GL Entry",
				company=company,
				posting_date=posting,
				account=account,
				debit=debit,
				credit=credit,
				voucher_type="Sales Invoice",
				voucher_no=name,
				is_cancelled=0,
				is_opening="No",
				docstatus=1,
				creation=booked,
			)
	return f"Sales Invoice:{name}"


def delivery_note(company: str, name: str, posting: str, invoice: str) -> None:
	"""A submitted Delivery Note that an item of the Sales Invoice ``invoice`` names."""
	insert_record("Delivery Note", name=name, company=company, posting_date=posting, docstatus=1)
	insert_record(
		"Sales Invoice Item",
		name=f"{invoice}-item-dn",
		parent=invoice,
		parenttype="Sales Invoice",
		parentfield="items",
		idx=1,
		docstatus=1,
		item_name="Ware",
		qty=1,
		delivery_note=name,
	)


def filed_return(company: str, period: Period, at: str):
	"""A monthly return of the period, calculated and filed outside Steuerbote, its filing recorded at ``at``."""
	doc = frappe.get_doc(
		{
			"doctype": "VAT Return",
			"company": company,
			"year": period.year,
			"rhythm": "monthly",
			"period_index": period.index,
		}
	).insert()
	doc.calculate()
	doc.reload()
	doc.remarks = FILING_NOTE
	doc.save()
	record = doc.mark_filed_outside(FILING_NOTE)
	frappe.db.set_value("ELSTER Transmission", record, "finished_at", at)
	doc.reload()
	return doc


def set_rule(company: str, basis: str = "By Service Date", late: str = "Corrected Return") -> None:
	frappe.db.set_value("VAT Return Settings", company, {"period_basis": basis, "late_documents": late})
