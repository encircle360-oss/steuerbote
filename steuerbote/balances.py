"""The balances of the books of a company for the Bilanz and the GuV of a fiscal year and for its Eröffnungsbilanz, as
the Books of steuerbote.xbrl.mapping that the Balance Sheet Mapping places on its positions.

steuerbote.ledger.load_lines reads the General Ledger of a period for the Voranmeldung and stays as it is. This module
reads it for the annual documents, the E-Bilanz and the Jahresabschluss, from the GL Entries of the company in its
currency, each account with its name, number, label and part, debit and credit in cents:

- An account of the Bilanz (report_type „Balance Sheet“) sums every entry up to the Stichtag, the opening entries
  included; an account of the GuV („Profit and Loss“) the entries of the fiscal year. ERPNext refuses a profit and
  loss account in an opening entry (check_pl_account in erpnext/accounts/doctype/gl_entry/gl_entry.py), so the GuV
  holds none.
- What ERPNext flags as cancelled stays out (is_cancelled = 0). With the immutable ledger of the Accounts Settings
  ERPNext flags nothing and posts the reversal on the day of the cancellation (make_reverse_gl_entries in
  erpnext/accounts/general_ledger.py): a voucher cancelled after the Stichtag stays in its year, and the reversal
  falls into the year of the cancellation.
- A Period Closing Voucher posts, on the last day of its period, the balance of each profit and loss account to the
  closing account (get_pcv_gl_entries in erpnext/accounts/doctype/period_closing_voucher/period_closing_voucher.py).
  Those of the fiscal year itself stay out: with them the GuV would show nothing, and the Bilanz would show the result
  of the year twice, once on the closing account and once as the Jahresüberschuss the documents take from the GuV.
  Every entry of a Period Closing Voucher from the first day of the fiscal year on is left out, and those of earlier
  years stay in, so that their results show on the closing account as the Gewinnvortrag or Verlustvortrag.
- The result of earlier fiscal years that no Period Closing Voucher closed is the balance of the profit and loss
  accounts before the fiscal year (Books.earlier_result); the mapping adds it to the closing account, as a Period
  Closing Voucher would. The documents need no Period Closing Voucher, and none counts twice.
- A finance book is chosen as the reports of ERPNext choose it: its entries and those without a finance book
  (apply_additional_conditions in erpnext/accounts/report/financial_statements.py, without „Include Default FB
  Entries“); without one, only the entries without a finance book.
- An account without an account number keeps an empty number, so that the mapping can name its balance as one it
  cannot place.

books() reads a fiscal year, opening_books() the Eröffnungsbilanz of the day a company begins: the accounts of the
Bilanz with every entry before the day and the opening entries up to it, and no account of the GuV.
fiscal_year_books() reads a Fiscal Year with the year before it, which the Jahresabschluss shows beside it (§ 265
Abs. 2 Satz 1 HGB); that is None where the company has no Fiscal Year before or no entry up to its end but opening entries, as in its
first year or its first year in ERPNext, or where its VAT Return Settings start the books after the first day of
that year (steuerbote/setup/start.py). It names the Period Closing Vouchers of the year, which the documents do not
need. closing_account() is the account the Annual Filing Settings name for the result, with its number.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import frappe
from erpnext.accounts.utils import get_fiscal_year
from frappe.query_builder import Criterion
from frappe.query_builder.functions import Sum
from frappe.utils import getdate

from steuerbote.ustva.rounding import CENT
from steuerbote.xbrl.mapping import ZERO, AccountBalance, Books, Part

PERIOD_CLOSING_VOUCHER = "Period Closing Voucher"
BALANCE_SHEET = "Balance Sheet"
PROFIT_AND_LOSS = "Profit and Loss"
SETTINGS = "Annual Filing Settings"


@dataclass(frozen=True)
class FiscalYearBooks:
	"""The books of a fiscal year and of the year before it, None without one."""

	fiscal_year: str
	from_date: date
	to_date: date
	current: Books
	prior: Books | None
	prior_from_date: date | None
	prior_to_date: date | None
	closed_by: tuple[str, ...]
	"""The submitted Period Closing Vouchers whose period ends in the fiscal year, which the books leave out."""


def books(
	company: str,
	from_date: date | str,
	to_date: date | str,
	*,
	finance_book: str | None = None,
	closing_account: str | None = None,
) -> Books:
	"""The balances of the fiscal year from ``from_date`` to ``to_date``: the Bilanz at the Stichtag, the GuV of the
	year and the result of earlier years no Period Closing Voucher closed. ``closing_account``, an account of the
	company, is among them even without an entry, so that the earlier result finds its name and label."""
	from_date, to_date = getdate(from_date), getdate(to_date)
	gl_entry = frappe.qb.DocType("GL Entry")
	in_books = (gl_entry.posting_date <= to_date) & ~(
		(gl_entry.voucher_type == PERIOD_CLOSING_VOUCHER) & (gl_entry.posting_date >= from_date)
	)
	balances = [
		*_balances(company, finance_book, in_books, BALANCE_SHEET),
		*_balances(company, finance_book, in_books & (gl_entry.posting_date >= from_date), PROFIT_AND_LOSS),
	]
	if closing_account and closing_account not in {balance.account for balance in balances}:
		balances.append(_without_entries(closing_account))
	earlier = _balances(company, finance_book, gl_entry.posting_date < from_date, PROFIT_AND_LOSS)
	return Books(
		tuple(sorted(balances, key=_order)),
		sum((balance.amount for balance in earlier), ZERO),
	)


def opening_books(company: str, day: date | str, *, finance_book: str | None = None) -> Books:
	"""The Eröffnungsbilanz on the day: the accounts of the Bilanz with every entry before it and the opening entries up
	to it, and the result of the years before, if the books hold any."""
	day = getdate(day)
	gl_entry = frappe.qb.DocType("GL Entry")
	opening = (gl_entry.posting_date < day) | (
		(gl_entry.is_opening == "Yes") & (gl_entry.posting_date <= day)
	)
	earlier = _balances(company, finance_book, gl_entry.posting_date < day, PROFIT_AND_LOSS)
	return Books(
		tuple(sorted(_balances(company, finance_book, opening, BALANCE_SHEET), key=_order)),
		sum((balance.amount for balance in earlier), ZERO),
	)


def fiscal_year_books(
	company: str,
	fiscal_year: str,
	*,
	finance_book: str | None = None,
	closing_account: str | None = None,
) -> FiscalYearBooks:
	"""The books of a Fiscal Year and of the one before it, with the Period Closing Vouchers of the year."""
	from_date, to_date = (
		getdate(value)
		for value in frappe.db.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"])
	)
	before = get_fiscal_year(from_date - timedelta(days=1), company=company, raise_on_missing=False)
	prior, prior_from, prior_to = None, None, None
	if before:
		prior_from, prior_to = getdate(before[1]), getdate(before[2])
		if _has_prior_books(company, prior_from, prior_to):
			prior = books(
				company, prior_from, prior_to, finance_book=finance_book, closing_account=closing_account
			)
		else:
			prior_from = prior_to = None
	return FiscalYearBooks(
		fiscal_year,
		from_date,
		to_date,
		books(company, from_date, to_date, finance_book=finance_book, closing_account=closing_account),
		prior,
		prior_from,
		prior_to,
		period_closing_vouchers(company, from_date, to_date),
	)


def period_closing_vouchers(company: str, from_date: date | str, to_date: date | str) -> tuple[str, ...]:
	"""The submitted Period Closing Vouchers of the company whose period ends within the days."""
	return tuple(
		frappe.get_all(
			PERIOD_CLOSING_VOUCHER,
			filters={
				"company": company,
				"docstatus": 1,
				"period_end_date": ["between", [getdate(from_date), getdate(to_date)]],
			},
			order_by="period_end_date, name",
			pluck="name",
		)
	)


def closing_account(company: str) -> tuple[str, str] | None:
	"""The account the Annual Filing Settings name for the result of the year (closing_account), with its number;
	None where they name none."""
	account = frappe.db.get_value(SETTINGS, company, "closing_account")
	if not account:
		return None
	return account, frappe.db.get_value("Account", account, "account_number") or ""


def _balances(
	company: str, finance_book: str | None, condition: Criterion, report_type: str
) -> list[AccountBalance]:
	gl_entry = frappe.qb.DocType("GL Entry")
	account = frappe.qb.DocType("Account")
	book = finance_book or ""
	rows = (
		frappe.qb.from_(gl_entry)
		.inner_join(account)
		.on(account.name == gl_entry.account)
		.select(
			account.name,
			account.account_number,
			account.account_name,
			Sum(gl_entry.debit).as_("debit"),
			Sum(gl_entry.credit).as_("credit"),
		)
		.where(gl_entry.company == company)
		.where(gl_entry.is_cancelled == 0)
		.where(account.report_type == report_type)
		.where(gl_entry.finance_book.isin([book, ""]) | gl_entry.finance_book.isnull())
		.where(condition)
		.groupby(account.name, account.account_number, account.account_name)
		.run(as_dict=True)
	)
	part = Part.of_report_type(report_type)
	return [
		AccountBalance(
			row.name,
			(row.account_number or "").strip(),
			row.account_name or "",
			part,
			_cents(row.debit),
			_cents(row.credit),
		)
		for row in rows
	]


def _without_entries(name: str) -> AccountBalance:
	values = frappe.db.get_value(
		"Account", name, ["account_number", "account_name", "report_type"], as_dict=True
	)
	return AccountBalance(
		name,
		(values.account_number or "").strip(),
		values.account_name or "",
		Part.of_report_type(values.report_type),
	)


def _has_prior_books(company: str, from_date: date, to_date: date) -> bool:
	"""Whether the books hold the year before: an entry up to its end that is no opening entry, and no start of the
	books in ERPNext after its first day (steuerbote/setup/start.py). Opening balances alone, posted on its last day,
	hold its Bilanz without its GuV."""
	books_start = frappe.db.get_value("VAT Return Settings", company, "books_start")
	if books_start and getdate(books_start) > from_date:
		return False
	return bool(
		frappe.db.exists(
			"GL Entry",
			{"company": company, "is_cancelled": 0, "is_opening": "No", "posting_date": ["<=", to_date]},
		)
	)


def _order(balance: AccountBalance) -> tuple[str, str]:
	return balance.number, balance.account


def _cents(amount: float | Decimal | None) -> Decimal:
	"""GL amounts arrive as floats; through their shortest repr they become the cents they were booked in."""
	return Decimal(str(amount or 0)).quantize(CENT)
