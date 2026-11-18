"""The general ledger of a company as the ledger lines of the core in steuerbote.ustva.

The Umsatzsteuer-Voranmeldung is computed from the GL Entries of the period, not from invoices. The core
expects the caller to leave out what is not turnover of the period (see steuerbote.ustva.calculation), so
the query skips cancelled entries and their reversals, opening entries, Period Closing Vouchers and the
Journal Entries flagged with the custom field steuerbote_exclude_from_vat_return, such as the settlement of
the tax accounts with the tax office. GL Entries are summed per account number and voucher. The voucher key
joins voucher type and name, because two document types can share a name.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import frappe
from frappe.query_builder.functions import Coalesce, Min, Sum

from steuerbote.ustva import LedgerLine
from steuerbote.ustva.rounding import CENT

EXCLUDE_FIELD = "steuerbote_exclude_from_vat_return"


def load_lines(company: str, from_date: date | str, to_date: date | str) -> list[LedgerLine]:
	"""The ledger lines of the company from ``from_date`` to ``to_date``, both included.

	Accounts without an account number cannot be mapped and are skipped; accounts_without_number lists them.
	"""
	return [
		LedgerLine(
			account_number=row.account_number.strip(),
			debit=_cents(row.debit),
			credit=_cents(row.credit),
			voucher=f"{row.voucher_type}:{row.voucher_no}",
		)
		for row in _ledger_rows(company, from_date, to_date)
	]


def _ledger_rows(company: str, from_date: date | str, to_date: date | str) -> list[frappe._dict]:
	gl_entry = frappe.qb.DocType("GL Entry")
	account = frappe.qb.DocType("Account")
	journal_entry = frappe.qb.DocType("Journal Entry")
	return (
		frappe.qb.from_(gl_entry)
		.inner_join(account)
		.on(account.name == gl_entry.account)
		.left_join(journal_entry)
		.on((gl_entry.voucher_type == "Journal Entry") & (journal_entry.name == gl_entry.voucher_no))
		.select(
			account.account_number,
			gl_entry.voucher_type,
			gl_entry.voucher_no,
			Sum(gl_entry.debit).as_("debit"),
			Sum(gl_entry.credit).as_("credit"),
		)
		.where(gl_entry.company == company)
		.where(gl_entry.posting_date.between(from_date, to_date))
		.where(gl_entry.is_cancelled == 0)
		.where(gl_entry.is_opening == "No")
		.where(gl_entry.voucher_type != "Period Closing Voucher")
		.where(Coalesce(journal_entry[EXCLUDE_FIELD], 0) == 0)
		.where(Coalesce(account.account_number, "") != "")
		.groupby(account.account_number, gl_entry.voucher_type, gl_entry.voucher_no)
		.orderby(Min(gl_entry.posting_date))
		.orderby(gl_entry.voucher_type)
		.orderby(gl_entry.voucher_no)
		.orderby(account.account_number)
		.run(as_dict=True)
	)


def _cents(amount: float | Decimal | None) -> Decimal:
	"""GL amounts arrive as floats; through their shortest repr they become the cents they were booked in."""
	return Decimal(str(amount or 0)).quantize(CENT)


def accounts_without_number(company: str) -> list[str]:
	"""The ledger accounts of the company that have no account number, so no rule can map them."""
	return frappe.get_all(
		"Account",
		filters={"company": company, "is_group": 0, "account_number": ["is", "not set"]},
		order_by="name",
		pluck="name",
	)


def account_names(company: str, numbers: Iterable[str]) -> dict[str, str]:
	"""The names of the company's accounts with these numbers, by number; unknown numbers are left out."""
	numbers = list(numbers)
	if not numbers:
		return {}
	accounts = frappe.get_all(
		"Account",
		filters={"company": company, "account_number": ["in", numbers]},
		fields=["name", "account_number"],
	)
	return {account.account_number: account.name for account in accounts}
