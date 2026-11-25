"""The general ledger of a company as the ledger lines of the core in steuerbote.ustva.

The Umsatzsteuer-Voranmeldung is computed from the GL Entries of the period, not from invoices. The core
expects the caller to leave out what is not turnover of the period (see steuerbote.ustva.calculation), so
the query skips the entries ERPNext flags as cancelled, opening entries, Period Closing Vouchers and the
Journal Entries flagged with the custom field steuerbote_exclude_from_vat_return, such as the settlement of
the tax accounts with the tax office. ERPNext flags a cancelled voucher's entries and their reversal unless
the Accounts Settings enable the immutable ledger: then it flags nothing and posts the reversal on the day
of the cancellation, so a cancellation within the period nets to zero and one in a later period reduces
that period. GL Entries are summed per account number and voucher. The voucher key joins voucher type and
name, because two document types can share a name. A caller that needs only some accounts, such as the
Zusammenfassende Meldung those of Kz 41, 42 and 21, names their numbers and reads nothing else.

load_lines reads by posting date. The Voranmeldung, its report and the annual return read through load_bookings
instead, which keeps the posting date, the time of the entry and the date of the supply a Sales Invoice names, so
that steuerbote.ustva.assignment can place each booking into its Voranmeldungszeitraum (steuerbote/vat_periods.py).
load_bookings reads a cancelled voucher whatever the ledger flags: its entries as they were booked, and the reversal
of each as a cancellation on the posting date of the entries it reverses, entered when the voucher was cancelled
(assignment, „A cancelled voucher“). With the immutable ledger that day may lie in another period, before the voucher
or after it, so it reads the reversals of the vouchers of its time wherever ERPNext posted them.
"""

from collections.abc import Collection, Iterable
from datetime import date, timedelta
from decimal import Decimal

import frappe
from frappe.query_builder.functions import Coalesce, Max, Min, Sum
from frappe.utils import get_datetime, getdate

from steuerbote.ustva import LedgerLine
from steuerbote.ustva.assignment import Booking, service_date
from steuerbote.ustva.rounding import CENT

EXCLUDE_FIELD = "steuerbote_exclude_from_vat_return"
SALES_INVOICE = "Sales Invoice"
# make_reverse_gl_entries of ERPNext (erpnext/accounts/general_ledger.py) writes this and the voucher's name into the
# remarks of every GL Entry that reverses one of a cancelled voucher, with the immutable ledger and without it.
REVERSAL_REMARKS = "On cancellation of "


def load_lines(
	company: str, from_date: date | str, to_date: date | str, account_numbers: Collection[str] | None = None
) -> list[LedgerLine]:
	"""The ledger lines of the company from ``from_date`` to ``to_date``, both included, of every account or
	of the ``account_numbers`` given.

	Accounts without an account number cannot be mapped and are skipped; accounts_without_number lists them.
	"""
	return [
		LedgerLine(
			account_number=row.account_number.strip(),
			debit=_cents(row.debit),
			credit=_cents(row.credit),
			voucher=f"{row.voucher_type}:{row.voucher_no}",
		)
		for row in _ledger_rows(company, from_date, to_date, account_numbers)
	]


def _ledger_rows(
	company: str, from_date: date | str, to_date: date | str, account_numbers: Collection[str] | None
) -> list[frappe._dict]:
	gl_entry = frappe.qb.DocType("GL Entry")
	account = frappe.qb.DocType("Account")
	journal_entry = frappe.qb.DocType("Journal Entry")
	query = (
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
	)
	if account_numbers is not None:
		query = query.where(account.account_number.isin(list(account_numbers) or [""]))
	return (
		query.groupby(account.account_number, gl_entry.voucher_type, gl_entry.voucher_no)
		.orderby(Min(gl_entry.posting_date))
		.orderby(gl_entry.voucher_type)
		.orderby(gl_entry.voucher_no)
		.orderby(account.account_number)
		.run(as_dict=True)
	)


def load_bookings(
	company: str, from_date: date | str, to_date: date | str, by_service_date: bool
) -> list[Booking]:
	"""The bookings of the company that may count from ``from_date`` to ``to_date``, both included, for
	steuerbote.ustva.assignment, with the exclusions of load_lines: those posted in the time and, by service date,
	every booking of a Sales Invoice whose supply falls in it, wherever it is posted. Each Sales Invoice carries the
	date of its supply (assignment.service_date); the assignment decides which of the bookings count."""
	rows = _booking_rows(company, posting_between=(from_date, to_date))
	supplied: list[str] = []
	if by_service_date:
		seen = {(row.account_number, row.voucher_type, row.voucher_no, row.posting_date) for row in rows}
		supplied = _invoices_supplied_between(company, from_date, to_date)
		for row in _booking_rows(company, sales_invoices=supplied):
			if (row.account_number, row.voucher_type, row.voucher_no, row.posting_date) not in seen:
				rows.append(row)
	rows.extend(_reversals(company, getdate(from_date), {(row.voucher_type, row.voucher_no) for row in rows}))
	rows.sort(
		key=lambda row: (
			str(row.posting_date),
			row.voucher_type,
			row.voucher_no,
			row.account_number,
			bool(row.cancellation),
		)
	)
	invoices = _supplies([row.voucher_no for row in rows if row.voucher_type == SALES_INVOICE])
	return [
		Booking(
			account_number=row.account_number.strip(),
			voucher=f"{row.voucher_type}:{row.voucher_no}",
			posting_date=getdate(row.posting_date),
			booked_at=get_datetime(row.booked_at),
			debit=_cents(row.debit),
			credit=_cents(row.credit),
			service_date=invoices.get(row.voucher_no) if row.voucher_type == SALES_INVOICE else None,
			cancellation=bool(row.cancellation),
		)
		for row in rows
	]


def _booking_rows(
	company: str,
	posting_between: tuple[date | str, date | str] | None = None,
	sales_invoices: Collection[str] = (),
	reversals_from: date | None = None,
) -> list[frappe._dict]:
	"""The ledger rows per account, voucher and posting date with the time of their first entry, posted in a time or
	of some Sales Invoices, flagged as cancelled or not; with ``reversals_from``, the reversals posted from that day on
	instead."""
	gl_entry = frappe.qb.DocType("GL Entry")
	account = frappe.qb.DocType("Account")
	journal_entry = frappe.qb.DocType("Journal Entry")
	remarks = Coalesce(gl_entry.remarks, "")
	query = (
		frappe.qb.from_(gl_entry)
		.inner_join(account)
		.on(account.name == gl_entry.account)
		.left_join(journal_entry)
		.on((gl_entry.voucher_type == "Journal Entry") & (journal_entry.name == gl_entry.voucher_no))
		.select(
			account.account_number,
			gl_entry.voucher_type,
			gl_entry.voucher_no,
			gl_entry.posting_date,
			Min(gl_entry.creation).as_("booked_at"),
			Sum(gl_entry.debit).as_("debit"),
			Sum(gl_entry.credit).as_("credit"),
		)
		.where(gl_entry.company == company)
		.where(gl_entry.is_opening == "No")
		.where(gl_entry.voucher_type != "Period Closing Voucher")
		.where(Coalesce(journal_entry[EXCLUDE_FIELD], 0) == 0)
		.where(Coalesce(account.account_number, "") != "")
	)
	if reversals_from is not None:
		query = query.where(remarks.like(f"{REVERSAL_REMARKS}%")).where(
			gl_entry.posting_date >= reversals_from
		)
	else:
		query = query.where(remarks.not_like(f"{REVERSAL_REMARKS}%"))
		if posting_between is not None:
			query = query.where(gl_entry.posting_date.between(*posting_between))
		elif sales_invoices:
			query = query.where(gl_entry.voucher_type == SALES_INVOICE).where(
				gl_entry.voucher_no.isin(list(sales_invoices))
			)
		else:
			return []
	return (
		query.groupby(
			account.account_number, gl_entry.voucher_type, gl_entry.voucher_no, gl_entry.posting_date
		)
		.orderby(gl_entry.posting_date)
		.orderby(gl_entry.voucher_type)
		.orderby(gl_entry.voucher_no)
		.orderby(account.account_number)
		.run(as_dict=True)
	)


def _reversals(company: str, start: date, vouchers: Collection[tuple[str, str]]) -> list[frappe._dict]:
	"""The reversals of the vouchers, each as a cancellation dated on the first posting date of the voucher's own
	entries, which ERPNext posts on one day. A reversal is posted on the day of the voucher or of its cancellation,
	which may precede a voucher dated ahead, but not by a year: the reversals are read from a year before ``start``."""
	if not vouchers:
		return []
	found = [
		row
		for row in _booking_rows(company, reversals_from=start - timedelta(days=366))
		if (row.voucher_type, row.voucher_no) in vouchers
	]
	if not found:
		return []
	booked_on = _first_posting_dates(company, {(row.voucher_type, row.voucher_no) for row in found})
	for row in found:
		row.posting_date = booked_on.get((row.voucher_type, row.voucher_no), row.posting_date)
		row.cancellation = True
	return found


def _first_posting_dates(company: str, vouchers: Collection[tuple[str, str]]) -> dict[tuple[str, str], date]:
	"""The first posting date of the entries of each voucher that are no reversal, by voucher type and name."""
	gl_entry = frappe.qb.DocType("GL Entry")
	rows = (
		frappe.qb.from_(gl_entry)
		.select(gl_entry.voucher_type, gl_entry.voucher_no, Min(gl_entry.posting_date).as_("posting_date"))
		.where(gl_entry.company == company)
		.where(gl_entry.voucher_no.isin(sorted({name for _voucher_type, name in vouchers})))
		.where(Coalesce(gl_entry.remarks, "").not_like(f"{REVERSAL_REMARKS}%"))
		.groupby(gl_entry.voucher_type, gl_entry.voucher_no)
		.run(as_dict=True)
	)
	return {(row.voucher_type, row.voucher_no): getdate(row.posting_date) for row in rows}


def _invoices_supplied_between(company: str, from_date: date | str, to_date: date | str) -> list[str]:
	"""The Sales Invoices of the company whose supply may fall in the time: by their billing period or by a Delivery
	Note; _supplies decides which date counts."""
	invoice = frappe.qb.DocType(SALES_INVOICE)
	by_period = (
		frappe.qb.from_(invoice)
		.select(invoice.name)
		.where(invoice.company == company)
		.where(invoice.docstatus.isin([1, 2]))
		.where(
			invoice.to_date.between(from_date, to_date)
			| (invoice.to_date.isnull() & invoice.from_date.between(from_date, to_date))
		)
		.run(pluck=True)
	)
	item = frappe.qb.DocType("Sales Invoice Item")
	note = frappe.qb.DocType("Delivery Note")
	by_delivery = (
		frappe.qb.from_(item)
		.inner_join(invoice)
		.on(invoice.name == item.parent)
		.inner_join(note)
		.on(note.name == item.delivery_note)
		.select(item.parent)
		.distinct()
		.where(item.parenttype == SALES_INVOICE)
		.where(invoice.company == company)
		.where(invoice.docstatus.isin([1, 2]))
		.where(note.docstatus == 1)
		.where(note.posting_date.between(from_date, to_date))
		.run(pluck=True)
	)
	return sorted({*by_period, *by_delivery})


def _supplies(names: Iterable[str]) -> dict[str, date]:
	"""The date of the supply of each Sales Invoice that names one, by name (assignment.service_date)."""
	names = sorted(set(names))
	if not names:
		return {}
	invoice = frappe.qb.DocType(SALES_INVOICE)
	invoices = (
		frappe.qb.from_(invoice)
		.select(invoice.name, invoice.to_date, invoice.from_date, invoice.is_return, invoice.is_debit_note)
		.where(invoice.name.isin(names))
		.run(as_dict=True)
	)
	item = frappe.qb.DocType("Sales Invoice Item")
	note = frappe.qb.DocType("Delivery Note")
	deliveries = dict(
		frappe.qb.from_(item)
		.inner_join(note)
		.on(note.name == item.delivery_note)
		.select(item.parent, Max(note.posting_date))
		.where(item.parenttype == SALES_INVOICE)
		.where(item.parent.isin(names))
		.where(note.docstatus == 1)
		.groupby(item.parent)
		.run()
	)
	found = {}
	for row in invoices:
		supplied = service_date(
			to_date=_date(row.to_date),
			from_date=_date(row.from_date),
			delivery_date=_date(deliveries.get(row.name)),
			is_return=bool(row.is_return),
			is_debit_note=bool(row.is_debit_note),
		)
		if supplied is not None:
			found[row.name] = supplied
	return found


def _date(value: date | str | None) -> date | None:
	return getdate(value) if value else None


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
	return _by_number(company, numbers, "name")


def account_labels(company: str, numbers: Iterable[str]) -> dict[str, str]:
	"""The Account Name of the company's accounts with these numbers, without number and company, by number;
	unknown numbers are left out."""
	return _by_number(company, numbers, "account_name")


def _by_number(company: str, numbers: Iterable[str], field: str) -> dict[str, str]:
	numbers = list(numbers)
	if not numbers:
		return {}
	accounts = frappe.get_all(
		"Account",
		filters={"company": company, "account_number": ["in", numbers]},
		fields=[field, "account_number"],
	)
	return {account.account_number: account[field] for account in accounts}


def closing_balances(
	company: str, to_date: date | str, account_numbers: Collection[str]
) -> dict[str, Decimal]:
	"""Debit less credit of each of the company's accounts with these numbers from every entry up to ``to_date``, the
	opening entries and the Journal Entries left out of the Voranmeldung included, without cancelled entries; the
	balance a watched timing account carries is this less the movement of the period (steuerbote/ustva/carried.py)."""
	numbers = list(account_numbers)
	if not numbers:
		return {}
	gl_entry = frappe.qb.DocType("GL Entry")
	account = frappe.qb.DocType("Account")
	rows = (
		frappe.qb.from_(gl_entry)
		.inner_join(account)
		.on(account.name == gl_entry.account)
		.select(account.account_number, Sum(gl_entry.debit).as_("debit"), Sum(gl_entry.credit).as_("credit"))
		.where(gl_entry.company == company)
		.where(gl_entry.posting_date <= to_date)
		.where(gl_entry.is_cancelled == 0)
		.where(account.account_number.isin(numbers))
		.groupby(account.account_number)
		.run(as_dict=True)
	)
	found = dict.fromkeys(numbers, Decimal("0.00"))
	for row in rows:
		found[row.account_number.strip()] = _cents(row.debit) - _cents(row.credit)
	return found
