"""What the Körperschaftsteuer- and the Gewerbesteuererklärung read from ERPNext for their cores in steuerbote/kst and
steuerbote/gewst, through the bridge steuerbote/steuerbote/doctype/corporate_income_tax_return/bridge.py.

- The profit and loss account of the Wirtschaftsjahr (ledger): the GL Entries of the accounts of the root types Income
  and Expense from the first to the last day of the Fiscal Year, as Anlage GK line 11 takes the Jahresüberschuss of the
  Handelsbilanz (§ 8 Absatz 1 KStG with § 4 Absatz 1 and § 5 Absatz 1 EStG). The entries ERPNext flags as cancelled,
  the opening entries and the Period Closing Voucher stay out, since they are no income or expense of the year (the
  Period Closing Voucher moves the result to the balance sheet). Unlike the Voranmeldung, the query keeps the Journal
  Entries flagged to stay out of it: the flag is one of the Umsatzsteuer. Of the Finanzbücher, the entries of none
  count and those of the Finanzbuch der Handelsbilanz of the Annual Filing Settings; the Überleitung to the
  Steuerbilanz comes by hand until the E-Bilanz gives it (adopted answer Q2 of the research of stage 3). The entries
  are summed per account and voucher, the voucher keyed "<voucher type>:<voucher name>" as steuerbote/ledger.py keys
  it; an account without a number counts in the Jahresüberschuss, and the return names it, as no mapping can place it.
- What the books hold of the taxes on income (tax_postings): the postings of the vouchers of the Wirtschaftsjahr on the
  accounts of the taxes, their provisions and the claims to their refund of steuerbote.kst.provisions.ACCOUNTS, from
  which the bridge takes the Vorauszahlungen booked and the provisions already posted.
- The Income Tax Mapping of the company (mapping) and its Annual Filing Settings (settings), with the W-IdNr of the
  VAT Return Settings, the name and the founding day of the Company, the Steuerberatung of the year and the day a
  Steuerberatung reviewed the returns, which they wait for (decision 6.4 of the contract of stage 3).
"""

from collections.abc import Iterable
from datetime import date

import frappe
from frappe import _
from frappe.query_builder.functions import Coalesce, Sum
from frappe.utils import cint, cstr, getdate

from steuerbote.jahresmeldung.overrides import to_amount
from steuerbote.kst.categories import Mapping
from steuerbote.kst.provisions import ProvisionAccounts
from steuerbote.steuerbote.doctype.annual_filing_settings.annual_filing_settings import settings_of
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge
from steuerbote.ustva import LedgerLine
from steuerbote.ustva.rounding import ZERO

MAPPING_DOCTYPE = "Income Tax Mapping"
PROFIT_AND_LOSS = ("Income", "Expense")
PERIOD_CLOSING_VOUCHER = "Period Closing Voucher"


def ledger(
	company: str, from_date: date, to_date: date, accounts: ProvisionAccounts | None, finance_book: str | None
) -> bridge.Ledger:
	"""The profit and loss account of the Wirtschaftsjahr and the Vorauszahlungen booked in it; see the module
	docstring. Without ``accounts``, for a chart of its own, the books name no account of the Vorauszahlungen, so the
	ledger holds none to compare with the settings (None)."""
	lines: list[LedgerLine] = []
	unnumbered: dict[str, list] = {}
	net_income = ZERO
	for row in _profit_and_loss(company, from_date, to_date, finance_book):
		debit, credit = to_amount(row.debit), to_amount(row.credit)
		net_income += credit - debit
		number = cstr(row.account_number).strip()
		if number:
			lines.append(LedgerLine(number, debit, credit, f"{row.voucher_type}:{row.voucher_no}"))
		else:
			unnumbered.setdefault(row.account, []).append(credit - debit)
	booked = None
	if accounts is not None:
		booked, _posted = bridge.booked_taxes(
			tax_postings(company, from_date, to_date, accounts, finance_book), accounts
		)
	return bridge.Ledger(
		tuple(lines),
		net_income,
		tuple(
			bridge.Unnumbered(account, sum(balances, ZERO))
			for account, balances in sorted(unnumbered.items())
			if sum(balances, ZERO)
		),
		booked,
	)


def tax_postings(
	company: str, from_date: date, to_date: date, accounts: ProvisionAccounts, finance_book: str | None
) -> list[bridge.Posting]:
	"""The postings of the vouchers of the Wirtschaftsjahr on the accounts of the taxes on income, their provisions and
	the claims to their refund, per voucher and account."""
	numbers = sorted(
		{
			number
			for taxed in (accounts.kst, accounts.solz, accounts.gewst)
			for number in (taxed.expense, taxed.provision, taxed.refund)
		}
	)
	gl_entry, account = frappe.qb.DocType("GL Entry"), frappe.qb.DocType("Account")
	query = (
		_entries(gl_entry, account, company, from_date, to_date, finance_book)
		.where(account.account_number.isin(numbers))
		.select(
			account.account_number,
			gl_entry.voucher_type,
			gl_entry.voucher_no,
			Sum(gl_entry.debit).as_("debit"),
			Sum(gl_entry.credit).as_("credit"),
		)
		.groupby(account.account_number, gl_entry.voucher_type, gl_entry.voucher_no)
	)
	return [
		bridge.Posting(
			f"{row.voucher_type}:{row.voucher_no}",
			cstr(row.account_number).strip(),
			to_amount(row.debit),
			to_amount(row.credit),
		)
		for row in query.run(as_dict=True)
	]


def posting_dates(company: str, vouchers: Iterable[str]) -> dict[str, date]:
	"""The posting date of each voucher, keyed "<voucher type>:<voucher name>", as the GL Entries of the company have
	it."""
	keys = sorted(set(vouchers))
	if not keys:
		return {}
	gl_entry = frappe.qb.DocType("GL Entry")
	names = sorted({key.partition(":")[2] for key in keys})
	rows = (
		frappe.qb.from_(gl_entry)
		.select(gl_entry.voucher_type, gl_entry.voucher_no, gl_entry.posting_date)
		.where(gl_entry.company == company)
		.where(gl_entry.voucher_no.isin(names))
		.run(as_dict=True)
	)
	found: dict[str, date] = {}
	for row in rows:
		key = f"{row.voucher_type}:{row.voucher_no}"
		if key in keys:
			day = getdate(row.posting_date)
			found[key] = min(found.get(key, day), day)
	return found


def mapping(company: str) -> Mapping:
	"""The Income Tax Mapping of the company as the Mapping of steuerbote.kst.categories."""
	if not frappe.db.exists(MAPPING_DOCTYPE, company):
		frappe.throw(
			_(
				"{0} has no Income Tax Mapping. Create it for the company, for example with the defaults of its chart, before calculating the return."
			).format(company),
			title=_("Income Tax Mapping"),
		)
	return frappe.get_doc(MAPPING_DOCTYPE, company).to_mapping()


def settings(company: str, year: int) -> bridge.Settings | None:
	"""The Annual Filing Settings of the company as the bridge reads them, None without them."""
	doc = settings_of(company)
	if doc is None:
		return None
	year_settings = doc.year_settings(year)
	advisor = None
	if year_settings is not None and year_settings.advisor_prepares:
		advisor = bridge.Advisor(
			name=_text(doc.advisor_name),
			first_name=_text(doc.advisor_first_name),
			street=_text(doc.advisor_street),
			town=_text(doc.advisor_town),
			phone=_text(doc.advisor_phone),
			details=_text(doc.advisor_details),
			client_number=_text(doc.advisor_client_number),
			clerk=_text(doc.advisor_clerk),
		)
	founded_on = frappe.db.get_value("Company", company, "date_of_establishment")
	return bridge.Settings(
		bridge.Company(
			name=frappe.db.get_value("Company", company, "company_name") or company,
			rechtsform=doc.rechtsform() if doc.legal_form else None,
			management_seat=_text(doc.management_seat),
			registered_seat=_text(doc.registered_seat),
			wid_nr=_text(frappe.db.get_value("VAT Return Settings", company, "wid_nr")),
			business_purpose=_text(doc.business_purpose),
			founded_on=getdate(founded_on) if founded_on else None,
			section_8b_7=bool(cint(doc.section_8b_7)),
			accounting_standard=doc.accounting_standard or "HAOE",
			advisor=advisor,
		),
		shareholders=tuple(doc.get_shareholders()),
		holdings=tuple(doc.get_holdings()),
		prepayments=tuple(doc.get_prepayments()),
		carry_forwards=tuple(doc.get_carry_forwards()),
		establishments=tuple(doc.get_establishments()),
		trade_tax_rates=tuple(doc.get_trade_tax_rates()),
		reviewed_on=getdate(doc.income_tax_review_on) if doc.income_tax_review_on else None,
	)


def commercial_finance_book(company: str) -> str | None:
	"""The Finanzbuch der Handelsbilanz of the Annual Filing Settings, None for the entries of no Finanzbuch alone."""
	return frappe.db.get_value("Annual Filing Settings", company, "commercial_finance_book") or None


def _profit_and_loss(company: str, from_date: date, to_date: date, finance_book: str | None) -> list:
	gl_entry, account = frappe.qb.DocType("GL Entry"), frappe.qb.DocType("Account")
	return (
		_entries(gl_entry, account, company, from_date, to_date, finance_book)
		.where(account.root_type.isin(PROFIT_AND_LOSS))
		.select(
			account.name.as_("account"),
			account.account_number,
			gl_entry.voucher_type,
			gl_entry.voucher_no,
			Sum(gl_entry.debit).as_("debit"),
			Sum(gl_entry.credit).as_("credit"),
		)
		.groupby(account.name, account.account_number, gl_entry.voucher_type, gl_entry.voucher_no)
		.orderby(account.account_number)
		.orderby(gl_entry.voucher_type)
		.orderby(gl_entry.voucher_no)
		.run(as_dict=True)
	)


def _entries(gl_entry, account, company: str, from_date: date, to_date: date, finance_book: str | None):
	"""The GL Entries of the Wirtschaftsjahr that count: not cancelled, no opening entry, no Period Closing Voucher,
	of no Finanzbuch or of the one named."""
	books = Coalesce(gl_entry.finance_book, "")
	in_book = books == "" if not finance_book else books.isin(["", finance_book])
	return (
		frappe.qb.from_(gl_entry)
		.inner_join(account)
		.on(account.name == gl_entry.account)
		.where(gl_entry.company == company)
		.where(gl_entry.posting_date.between(from_date, to_date))
		.where(gl_entry.is_cancelled == 0)
		.where(gl_entry.is_opening == "No")
		.where(gl_entry.voucher_type != PERIOD_CLOSING_VOUCHER)
		.where(in_book)
	)


def _text(value: object) -> str | None:
	return cstr(value).strip() or None
