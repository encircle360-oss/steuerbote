"""What the E-Bilanz reads from ERPNext for its core in steuerbote/ebilanz.

- The balances of the books through steuerbote/balances.py (books_of): the Bilanz up to the Stichtag and the GuV of
  the Wirtschaftsjahr, without its Period Closing Voucher, and the Period Closing Vouchers of the year; for an
  Eröffnungsbilanz the books on its day (opening_books). The Balance Sheet Mapping places them.
- The assets (book_assets): the report „Asset Depreciations and Balances“ of ERPNext, grouped by asset, for the
  Wirtschaftsjahr, which sums up Asset, Asset Depreciation Schedule, Asset Value Adjustment, Asset Capitalization and
  the disposals; for a finance book, the report holds only the assets with a depreciation schedule in it, so every
  other asset comes from the report without one, whose entries without a finance book ERPNext counts in every book.
  Each asset is in its asset category, with the fixed asset account of the category for the company. Then the
  finance books of the active schedules of each asset (schedules) and the depreciation the schedules plan up to the
  Bilanzstichtag that no Journal Entry posted (unposted_depreciation).
- What the GCD says of the company (master_data): its name, the address, the Steuernummer for the income taxes and
  the Gegenstand des Unternehmens of the Annual Filing Settings, and the previous fiscal year (previous_fiscal_year),
  none in the founding year.
- The Betriebsvermögen of the Steuerbilanz the filed E-Bilanz of the previous year reported (filed_tax_equity), and the
  check of the installed taxonomy (taxonomy_check), as „Laufzeitumgebung prüfen“ reports it.
- For the Körperschaftsteuererklärung: the E-Bilanz of the year whose Jahresüberschuss Anlage GK line 11 takes
  (ebilanz_for_income_tax), and the filed E-Bilanz of a year (filed_ebilanz) with the gezeichnetes Kapital of its
  Steuerbilanz (subscribed_capital) for KSt 1 F lines 17 and 18.
- The Jahresabschluss of the year whose Handelsbilanz Berechnen compares with that of the E-Bilanz
  (annual_accounts_for_ebilanz), with the statement it files as the comparison takes it (annual_accounts_comparison),
  and whether it was cancelled since (cancelled_annual_accounts).
"""

from datetime import date, timedelta
from decimal import Decimal

import frappe
from erpnext.accounts.report.asset_depreciations_and_balances import asset_depreciations_and_balances
from erpnext.accounts.utils import get_fiscal_year
from frappe.query_builder.functions import IfNull
from frappe.utils import cint, cstr, getdate

from steuerbote import balances
from steuerbote.ebilanz.gcd import MasterData, gesellschafter
from steuerbote.hgb.size import SizeClass
from steuerbote.jahresmeldung.corrections import RevisionStatus
from steuerbote.jahresmeldung.lifecycle import Status
from steuerbote.jahresmeldung.overrides import to_amount
from steuerbote.steuerbote.doctype.annual_accounts import bridge as accounts_bridge
from steuerbote.steuerbote.doctype.electronic_balance_sheet import comparison
from steuerbote.steuerbote.doctype.electronic_balance_sheet.bridge import (
	EROEFFNUNGSBILANZ,
	JAHRESABSCHLUSS,
	CategoryValues,
	Unposted,
)
from steuerbote.steuerbote.doctype.eric_settings import eric_settings
from steuerbote.xbrl.mapping import Books
from steuerbote.xbrl.versions import TAXONOMIES

DOCTYPE = "Electronic Balance Sheet"
ANNUAL_ACCOUNTS = "Annual Accounts"
POSITION = "Electronic Balance Sheet Position"
SUBSCRIBED = "bs.eqLiab.equity.subscribed"
INCOME_TAX_STATUSES = (Status.CALCULATED, Status.READY, Status.FILED)
"""What an E-Bilanz has to be for the Körperschaftsteuererklärung to take its Jahresüberschuss: calculated, ready or
filed; a draft that Berechnen has not read holds no figures, and a replaced one gave way to its Berichtigung."""
GROUP_BY_ASSET = "Asset"
DISPOSALS = ("value_of_sold_asset", "value_of_scrapped_asset", "value_of_capitalized_asset")


def books_of(
	company: str,
	fiscal_year: str,
	from_date: date,
	statement_type: str,
	*,
	finance_book: str | None,
	closing_account: str | None,
) -> tuple[Books, tuple[str, ...]]:
	"""The books of the E-Bilanz and the Period Closing Vouchers of its Wirtschaftsjahr: those of the Fiscal Year for a
	Jahresabschluss, those on its first day for an Eröffnungsbilanz."""
	if statement_type == EROEFFNUNGSBILANZ:
		return balances.opening_books(company, from_date, finance_book=finance_book), ()
	found = balances.fiscal_year_books(
		company, fiscal_year, finance_book=finance_book, closing_account=closing_account
	)
	return found.current, found.closed_by


def opening_books(company: str, day: date, finance_book: str | None) -> Books:
	"""The books at the beginning of the Wirtschaftsjahr: the Betriebsvermögen of the previous year and the Einlagen of
	the founding come from them."""
	return balances.opening_books(company, day, finance_book=finance_book)


def book_assets(
	company: str, from_date: date, to_date: date, finance_book: str | None
) -> dict[str, CategoryValues]:
	"""Each asset of the company in the books of the finance book, by its name, as the report Asset Depreciations and
	Balances sums it up for the days: of an asset with a depreciation schedule in the book the report for the book,
	of every other asset the report without a finance book; None for the entries without one."""
	found = _asset_values(company, from_date, to_date, None)
	if finance_book:
		found.update(_asset_values(company, from_date, to_date, finance_book))
	return found


def fixed_asset_accounts(company: str) -> dict[str, str]:
	"""The number of the fixed asset account of each asset category for the company, empty without one."""
	rows = frappe.get_all(
		"Asset Category Account",
		filters={"company_name": company, "parenttype": "Asset Category"},
		fields=["parent", "fixed_asset_account"],
	)
	names = [row.fixed_asset_account for row in rows if row.fixed_asset_account]
	numbers = dict(
		frappe.get_all(
			"Account", filters={"name": ["in", names]}, fields=["name", "account_number"], as_list=True
		)
		if names
		else ()
	)
	return {row.parent: cstr(numbers.get(row.fixed_asset_account)).strip() for row in rows}


def unposted_depreciation(company: str, stichtag: date, finance_books: tuple[str, ...]) -> list[Unposted]:
	"""The depreciation the active schedules of the submitted assets of the company plan up to the Bilanzstichtag in
	the finance books, "" for the entries without one, and that no Journal Entry posted; of an asset disposed of, up
	to its disposal."""
	schedule = frappe.qb.DocType("Asset Depreciation Schedule")
	row = frappe.qb.DocType("Depreciation Schedule")
	asset = frappe.qb.DocType("Asset")
	found = (
		frappe.qb.from_(schedule)
		.inner_join(row)
		.on((row.parent == schedule.name) & (row.parenttype == "Asset Depreciation Schedule"))
		.inner_join(asset)
		.on(asset.name == schedule.asset)
		.select(asset.name, row.schedule_date, row.depreciation_amount, schedule.finance_book)
		.where(asset.company == company)
		.where(asset.docstatus == 1)
		.where(schedule.docstatus == 1)
		.where(schedule.status == "Active")
		.where(row.schedule_date <= stichtag)
		.where(IfNull(row.journal_entry, "") == "")
		.where(IfNull(schedule.finance_book, "").isin(list(finance_books)))
		.where(asset.disposal_date.isnull() | (row.schedule_date <= asset.disposal_date))
		.orderby(asset.name)
		.orderby(row.schedule_date)
		.run(as_dict=True)
	)
	return [
		Unposted(
			entry.name,
			getdate(entry.schedule_date),
			to_amount(entry.depreciation_amount),
			entry.finance_book or "",
		)
		for entry in found
	]


def schedules(company: str, from_date: date, stichtag: date) -> dict[str, frozenset[str]]:
	"""The finance books, "" for none, of the active depreciation schedules of each submitted asset of the company with
	depreciation that it bought up to the Bilanzstichtag and held in the Wirtschaftsjahr."""
	asset = frappe.qb.DocType("Asset")
	schedule = frappe.qb.DocType("Asset Depreciation Schedule")
	names = (
		frappe.qb.from_(asset)
		.select(asset.name)
		.where(asset.company == company)
		.where(asset.docstatus == 1)
		.where(asset.calculate_depreciation == 1)
		.where(asset.purchase_date <= stichtag)
		.where(asset.disposal_date.isnull() | (asset.disposal_date >= from_date))
		.orderby(asset.name)
		.run(pluck=True)
	)
	found: dict[str, set[str]] = {name: set() for name in names}
	if names:
		for name, book in (
			frappe.qb.from_(schedule)
			.select(schedule.asset, IfNull(schedule.finance_book, ""))
			.where(schedule.docstatus == 1)
			.where(schedule.status == "Active")
			.where(schedule.asset.isin(names))
			.run()
		):
			found[name].add(book)
	return {name: frozenset(books) for name, books in found.items()}


def master_data(
	company: str,
	settings,
	*,
	revision_status: str | None,
	previous_fiscal_year: tuple[date, date] | None,
	generated: date,
	stichtag: date,
) -> MasterData:
	"""The GCD of the company from the Annual Filing Settings: its name, the address with the house number and its
	suffix, the Steuernummer for the income taxes in the 13 digits of ELSTER, the Gegenstand des Unternehmens and the
	shareholders on the Bilanzstichtag; the Status des Berichts of the document, erstmalig without one."""
	address = settings.get_address()
	return MasterData(
		name=frappe.db.get_value("Company", company, "company_name") or company,
		street=address.street or "",
		postal_code=address.postal_code or "",
		city=address.city or "",
		steuernummer=settings.elster_tax_number() or None,
		house_number=(address.house_number or "") + (address.house_number_suffix or ""),
		business=settings.business_purpose or "",
		revision_status=RevisionStatus(revision_status or RevisionStatus.FIRST),
		previous_fiscal_year=previous_fiscal_year,
		generated=generated,
		shareholders=gesellschafter(settings.get_shareholders(), stichtag),
	)


def previous_fiscal_year(company: str, from_date: date) -> tuple[date, date] | None:
	"""The Fiscal Year of the company before the Wirtschaftsjahr, None without one."""
	before = get_fiscal_year(from_date - timedelta(days=1), company=company, raise_on_missing=False)
	if not before:
		return None
	return getdate(before[1]), getdate(before[2])


def filed_tax_equity(company: str, year: int) -> Decimal | None:
	"""The Betriebsvermögen of the Steuerbilanz that the filed E-Bilanz of the Jahresabschluss of the year reported,
	the latest that no Berichtigung replaced; None without one."""
	name = filed_ebilanz(company, year)
	return None if name is None else to_amount(frappe.db.get_value(DOCTYPE, name, "tax_equity"))


def filed_ebilanz(company: str, year: int) -> str | None:
	"""The filed E-Bilanz of the Jahresabschluss of the company and year, the latest that no Berichtigung replaced;
	None without one."""
	found = frappe.get_all(
		DOCTYPE,
		filters={
			"company": company,
			"year": year,
			"statement_type": JAHRESABSCHLUSS,
			"docstatus": 1,
			"status": Status.FILED.value,
		},
		order_by="creation desc",
		limit=1,
		pluck="name",
	)
	return found[0] if found else None


def subscribed_capital(name: str) -> Decimal:
	"""The gezeichnetes Kapital the Steuerbilanz of an E-Bilanz reports, its position „Gezeichnetes Kapital“
	[bs.eqLiab.equity.subscribed]; 0 without the position."""
	return to_amount(
		frappe.db.get_value(
			POSITION,
			{"parent": name, "parenttype": DOCTYPE, "concept": SUBSCRIBED, "manual": 0},
			"tax_amount",
		)
	)


def ebilanz_for_income_tax(company: str, year: int, named: str | None) -> str | None:
	"""The E-Bilanz whose Jahresüberschuss the Körperschaftsteuererklärung of the company and year takes for Anlage GK
	line 11: the one named, while it is the Jahresabschluss of the key, calculated or filed and not replaced, else the
	newest such E-Bilanz; None without one, so that line 11 is the Jahresüberschuss of the books."""
	filters = {
		"company": company,
		"year": year,
		"statement_type": JAHRESABSCHLUSS,
		"docstatus": ["!=", 2],
		"status": ["in", [status.value for status in INCOME_TAX_STATUSES]],
	}
	if named and frappe.db.exists(DOCTYPE, {"name": named, **filters}):
		return named
	found = frappe.get_all(DOCTYPE, filters=filters, order_by="creation desc", limit=1, pluck="name")
	return found[0] if found else None


def annual_accounts_for_ebilanz(company: str, year: int, named: str | None) -> str | None:
	"""The Jahresabschluss whose Handelsbilanz Berechnen compares with the E-Bilanz of the company and year: the one
	named, while it is of the company and year and neither cancelled nor replaced, else the festgestellte one of the
	key, else its draft; None without one."""
	filters = {
		"company": company,
		"year": year,
		"docstatus": ["!=", 2],
		"status": ["!=", Status.REPLACED.value],
	}
	if named and frappe.db.exists(ANNUAL_ACCOUNTS, {"name": named, **filters}):
		return named
	found = frappe.get_all(
		ANNUAL_ACCOUNTS, filters=filters, order_by="docstatus desc, creation desc", limit=1, pluck="name"
	)
	return found[0] if found else None


def annual_accounts_comparison(name: str | None) -> comparison.Accounts | None:
	"""The Jahresabschluss as the comparison takes it: the statement it files, built again from what it keeps of it
	(statement_from_data of steuerbote/steuerbote/doctype/annual_accounts/bridge.py) in the form of its size class, or
	of klein while it has none, as its Berechnen builds it; None without one."""
	if not name:
		return None
	found = frappe.db.get_value(
		ANNUAL_ACCOUNTS,
		name,
		["name", "year", "docstatus", "status", "size_class", "statement_data"],
		as_dict=True,
	)
	if found is None:
		return None
	statement = None
	if found.statement_data:
		size_class = accounts_bridge.size_class_of(found.size_class) or SizeClass.KLEIN
		statement = accounts_bridge.statement_from_data(found.statement_data, cint(found.year), size_class)
	festgestellt = cint(found.docstatus) == 1 and found.status != Status.REPLACED.value
	return comparison.Accounts(found.name, statement, festgestellt)


def cancelled_annual_accounts(name: str) -> bool:
	return cint(frappe.db.get_value(ANNUAL_ACCOUNTS, name, "docstatus")) == 2


def taxonomy_check(version: str) -> tuple[bool, str]:
	"""Whether the taxonomy of the version is installed and unchanged, with what „Laufzeitumgebung prüfen“ says of it
	(steuerbote.xbrl.taxonomy.status)."""
	name = f"taxonomy_{TAXONOMIES[version].version.replace('.', '_')}"
	check = next(check for check in eric_settings.taxonomy_status() if check.name == name)
	return check.ok, check.detail


def _asset_values(
	company: str, from_date: date, to_date: date, finance_book: str | None
) -> dict[str, CategoryValues]:
	"""Each asset as the report sums it up grouped by asset for the finance book, in its asset category."""
	rows = _report(company, from_date, to_date, GROUP_BY_ASSET, finance_book)
	names = [row.get("name") for row in rows if row.get("name")]
	categories = dict(
		frappe.get_all(
			"Asset", filters={"name": ["in", names]}, fields=["name", "asset_category"], as_list=True
		)
		if names
		else ()
	)
	accounts = fixed_asset_accounts(company)
	return {
		row["name"]: _values(row, categories[row["name"]], accounts)
		for row in rows
		if categories.get(row.get("name"))
	}


def _report(company: str, from_date: date, to_date: date, group_by: str, finance_book: str | None) -> list:
	"""The rows of the report Asset Depreciations and Balances, without the messages it shows on its page."""
	muted = frappe.flags.mute_messages
	frappe.flags.mute_messages = True
	try:
		_columns, rows = asset_depreciations_and_balances.execute(
			frappe._dict(
				company=company,
				from_date=from_date,
				to_date=to_date,
				group_by=group_by,
				finance_book=finance_book,
			)
		)
	finally:
		frappe.flags.mute_messages = muted
	return list(rows or ())


def _values(row, category: str, accounts: dict[str, str]) -> CategoryValues:
	return CategoryValues(
		category,
		accounts.get(category, ""),
		cost_begin=_amount(row, "value_as_on_from_date"),
		additions=_amount(row, "value_of_new_purchase"),
		disposals=sum((_amount(row, name) for name in DISPOSALS), Decimal(0)),
		adjustment=_amount(row, "adjustment_during_period"),
		depreciation_begin=_amount(row, "accumulated_depreciation_as_on_from_date"),
		depreciation=_amount(row, "depreciation_amount_during_the_period")
		- _amount(row, "depreciation_eliminated_via_reversal"),
		depreciation_disposals=_amount(row, "depreciation_eliminated_during_the_period"),
	)


def _amount(row, name: str) -> Decimal:
	return to_amount(row.get(name))
