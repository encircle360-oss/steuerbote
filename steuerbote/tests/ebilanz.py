"""The invented „Steuerbote Test E-Bilanz GmbH“ as ERPNext keeps it, for the Frappe tests of the E-Bilanz and of the
report E-Bilanz Positionen.

A GmbH with SKR04 accounts, founded on 1 March 2026, has its short first Wirtschaftsjahr from 1 March to 31 December
2026 in a Fiscal Year of its own, beside the calendar year 2026 of every company. On its first day it pays in its
Stammkapital of 25,000 euros (an opening entry), then buys a laptop for 3,600 euros, software for 1,440 and a plot of
land for 10,000, sells for 50,000 and pays rent of 12,000. At the end of the year it depreciates the laptop by 900 and
the software by 320, books 1,500 for the costs of its Jahresabschluss and closes the year with a Period Closing
Voucher onto 2970: a Jahresüberschuss of 35,280 euros and a Bilanzsumme of 61,780. The laptop and the software have
depreciation schedules without a finance book, the land has none. For a Handelsbilanz with the finance book of the
Steuerbilanz, a Rückstellung für drohende Verluste of 2,000 euros counts in the Handelsbilanz alone, as § 5 Abs. 4a
EStG keeps it out of the Steuerbilanz (DROHVERLUST).

The assets, their categories and schedules, the Period Closing Voucher and the GL Entries are written as ERPNext stores
them (insert_record), since the E-Bilanz reads nothing else of them; the Balance Sheet Mapping names a position of the
HGB-Taxonomie 6.9 for each account but the Geldtransit. A test class makes the records unless the site has them
(make_company_with_books), and a test that changes one of them for itself takes it back (post_for_the_test,
set_for_the_test). Every name, number and amount is invented.
"""

import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from steuerbote.steuerbote.doctype.vat_return import transmission_adapter
from steuerbote.steuerbote.doctype.vat_return.vat_return import FILED
from steuerbote.tests.helpers import ensure_fiscal_year, insert_record, make_company, make_settings
from steuerbote.tests.income_tax import make_accounts
from steuerbote.xbrl.tests import real

COMPANY = "Steuerbote Test E-Bilanz GmbH"
ABBR = "STEB"
YEAR = 2026
FOUNDED = date(2026, 3, 1)
END = date(2026, 12, 31)
FISCAL_YEAR = "2026 Steuerbote Test E-Bilanz"
DOCTYPE = "Electronic Balance Sheet"
SETTINGS = "Annual Filing Settings"
MAPPING = "Balance Sheet Mapping"
TRANSMISSION = "ELSTER Transmission"
PERIOD_CLOSING_VOUCHER_DOCTYPE = "Period Closing Voucher"
TAX_BOOK = "Steuerbilanz Steuerbote Test"
TAXONOMY_ROOT = "steuerbote_taxonomy_root"
ACCOUNTS = {
	"0135": ("EDV-Software", "Asset"),
	"0136": ("Kumulierte Abschreibungen EDV-Software", "Asset"),
	"0215": ("Unbebaute Grundstücke", "Asset"),
	"0650": ("Büroeinrichtung", "Asset"),
	"0651": ("Kumulierte Abschreibungen Büroeinrichtung", "Asset"),
	"1360": ("Geldtransit", "Asset"),
	"1800": ("Bank", "Asset"),
	"2900": ("Gezeichnetes Kapital", "Equity"),
	"2970": ("Gewinnvortrag vor Verwendung", "Equity"),
	"3070": ("Sonstige Rückstellungen", "Liability"),
	"3075": ("Rückstellungen für drohende Verluste", "Liability"),
	"4400": ("Erlöse 19 % USt", "Income"),
	"6200": ("Abschreibungen auf immaterielle Vermögensgegenstände", "Expense"),
	"6220": ("Abschreibungen auf Sachanlagen", "Expense"),
	"6230": ("Außerplanmäßige Abschreibungen auf Sachanlagen", "Expense"),
	"6310": ("Miete", "Expense"),
	"6827": ("Abschluss- und Prüfungskosten", "Expense"),
	"6960": ("Periodenfremde Aufwendungen", "Expense"),
}
# The position of each account in the HGB-Taxonomie 6.9, without the prefix de-gaap-ci:; 1360 has none.
RULES = {
	"0135": "bs.ass.fixAss.intan.concessionBrands",
	"0136": "bs.ass.fixAss.intan.concessionBrands",
	"0215": "bs.ass.fixAss.tan.landBuildings.landWithoutBuildings",
	"0650": "bs.ass.fixAss.tan.otherEquipm.office",
	"0651": "bs.ass.fixAss.tan.otherEquipm.office",
	"1800": "bs.ass.currAss.cashEquiv.bank",
	"2900": "bs.eqLiab.equity.subscribed.corp",
	"2970": "bs.eqLiab.equity.retainedEarnings",
	"3070": "bs.eqLiab.accruals.other.other",
	"3075": "bs.eqLiab.accruals.other.imminentLoss",
	"4400": "is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.generalRateVAT",
	"6200": "is.netIncome.regular.operatingTC.deprAmort.fixAss.otherIntan",
	"6220": "is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.other",
	"6230": "is.netIncome.regular.operatingTC.deprAmort.fixAss.specific.except.tan",
	"6310": "is.netIncome.regular.operatingTC.otherCost.leaseFix.other",
	"6827": "is.netIncome.regular.operatingTC.otherCost.legalConsulting",
	"6960": "is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
}
ANNUAL_FILING_SETTINGS = {
	"legal_form": "GmbH",
	"business_purpose": "Softwareentwicklung",
	"management_seat": "München",
	"registered_seat": "München",
	"street": "Musterweg",
	"house_number": "12",
	"postal_code": "80331",
	"city": "München",
	"country": "Germany",
}
# Each asset category with its fixed asset account, the account of its cumulated depreciation and its depreciation
# expense, by the numbers of ACCOUNTS.
CATEGORIES = {
	"Steuerbote Test Büroausstattung": ("0650", "0651", "6220"),
	"Steuerbote Test Software": ("0135", "0136", "6200"),
	"Steuerbote Test Grundstücke": ("0215", None, None),
}
LAPTOP = "STEB-ANLAGE-LAPTOP"
SOFTWARE = "STEB-ANLAGE-SOFTWARE"
LAND = "STEB-ANLAGE-GRUNDSTUECK"
# Each asset: its label, category, purchase day and amount, and the rows of its depreciation schedule without a finance
# book, (day, amount, the Journal Entry that posted it); the land is not depreciated.
ASSETS = {
	LAPTOP: (
		"Laptop",
		"Steuerbote Test Büroausstattung",
		"2026-04-01",
		3600,
		(
			("2026-12-31", 900, "STEB-AFA-LAPTOP-2026"),
			("2027-12-31", 1200, None),
			("2028-12-31", 1200, None),
			("2029-03-31", 300, None),
		),
	),
	SOFTWARE: (
		"Buchhaltungssoftware",
		"Steuerbote Test Software",
		"2026-05-01",
		1440,
		(
			("2026-12-31", 320, "STEB-AFA-SOFTWARE-2026"),
			("2027-12-31", 480, None),
			("2028-12-31", 480, None),
			("2029-04-30", 160, None),
		),
	),
	LAND: ("Grundstück Musterweg", "Steuerbote Test Grundstücke", "2026-06-01", 10000, ()),
}
OPENING_ENTRY = "STEB-GRUENDUNG"
PERIOD_CLOSING_VOUCHER = "STEB-PCV-2026"
# The vouchers of the Wirtschaftsjahr: (voucher type, voucher no., day, rows of (number, debit, credit), the asset a
# depreciation is booked against). The opening entry is ERPNext's is_opening; the Period Closing Voucher moves the
# result onto 2970.
LEDGER = (
	("Journal Entry", OPENING_ENTRY, "2026-03-01", (("1800", 25000, 0), ("2900", 0, 25000)), None),
	("Journal Entry", "STEB-LAPTOP", "2026-04-01", (("0650", 3600, 0), ("1800", 0, 3600)), None),
	("Journal Entry", "STEB-SOFTWARE", "2026-05-01", (("0135", 1440, 0), ("1800", 0, 1440)), None),
	("Journal Entry", "STEB-GRUNDSTUECK", "2026-06-01", (("0215", 10000, 0), ("1800", 0, 10000)), None),
	("Journal Entry", "STEB-UMSATZ", "2026-09-30", (("1800", 50000, 0), ("4400", 0, 50000)), None),
	("Journal Entry", "STEB-MIETE", "2026-10-31", (("6310", 12000, 0), ("1800", 0, 12000)), None),
	("Journal Entry", "STEB-AFA-LAPTOP-2026", "2026-12-31", (("6220", 900, 0), ("0651", 0, 900)), LAPTOP),
	("Journal Entry", "STEB-AFA-SOFTWARE-2026", "2026-12-31", (("6200", 320, 0), ("0136", 0, 320)), SOFTWARE),
	("Journal Entry", "STEB-ABSCHLUSS", "2026-12-31", (("6827", 1500, 0), ("3070", 0, 1500)), None),
	(
		"Period Closing Voucher",
		PERIOD_CLOSING_VOUCHER,
		"2026-12-31",
		(
			("4400", 50000, 0),
			("6310", 0, 12000),
			("6220", 0, 900),
			("6200", 0, 320),
			("6827", 0, 1500),
			("2970", 0, 35280),
		),
		None,
	),
)
# The Rückstellung für drohende Verluste of the Handelsbilanz, and the entry of the finance book of the Steuerbilanz
# that takes it out again.
DROHVERLUST = (
	("STEB-DROHVERLUST", (("6960", 2000, 0), ("3075", 0, 2000)), None),
	("STEB-DROHVERLUST-STEUERLICH", (("3075", 2000, 0), ("6960", 0, 2000)), TAX_BOOK),
)


def money(value: object) -> Decimal:
	"""A currency field as the tests compare it, in cents."""
	return Decimal(str(flt(value, 2))).quantize(Decimal("0.01"))


def make_company_with_books() -> dict[str, str]:
	"""The company with its accounts, Fiscal Years, settings, mapping, assets and ledger, each made unless the site has
	it; returns the accounts by number."""
	make_company(COMPANY, ABBR)
	frappe.db.set_value("Company", COMPANY, "date_of_establishment", FOUNDED)
	accounts = make_accounts(COMPANY, ACCOUNTS)
	ensure_fiscal_year(COMPANY, date(YEAR, 1, 15))
	if not frappe.db.exists("Fiscal Year", FISCAL_YEAR):
		frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": FISCAL_YEAR,
				"year_start_date": FOUNDED,
				"year_end_date": END,
				"is_short_year": 1,
				"companies": [{"company": COMPANY}],
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Finance Book", TAX_BOOK):
		frappe.get_doc({"doctype": "Finance Book", "finance_book_name": TAX_BOOK}).insert(
			ignore_permissions=True
		)
	if not frappe.db.exists("VAT Return Settings", COMPANY):
		make_settings(COMPANY, [(YEAR, "monthly", 1)])
	if not frappe.db.exists(SETTINGS, COMPANY):
		frappe.get_doc(
			{
				"doctype": SETTINGS,
				"company": COMPANY,
				"closing_account": accounts["2970"],
				**ANNUAL_FILING_SETTINGS,
			}
		).insert(ignore_permissions=True)
	make_assets(accounts)
	for voucher_type, voucher_no, posting_date, rows, asset in LEDGER:
		post_once(accounts, voucher_type, voucher_no, posting_date, rows, against=asset)
	if not frappe.db.exists(PERIOD_CLOSING_VOUCHER_DOCTYPE, PERIOD_CLOSING_VOUCHER):
		insert_record(
			PERIOD_CLOSING_VOUCHER_DOCTYPE,
			name=PERIOD_CLOSING_VOUCHER,
			company=COMPANY,
			fiscal_year=FISCAL_YEAR,
			period_start_date=FOUNDED,
			period_end_date=END,
			transaction_date=END,
			posting_date=END,
			closing_account_head=accounts["2970"],
			docstatus=1,
		)
	return accounts


def make_mapping(accounts: dict[str, str]) -> None:
	"""The Balance Sheet Mapping of RULES, unless the company has one, saved as without the taxonomy: the label of a
	position can be longer than the field of a rule takes, as the 150 characters of „…, auf Sachanlagen, übrige
	Abschreibungen auf Sachanlagen“ against 140, and Berechnen checks the positions against the taxonomy anyway."""
	if frappe.db.exists(MAPPING, COMPANY):
		return
	mapping = frappe.get_doc(
		{
			"doctype": MAPPING,
			"company": COMPANY,
			"chart": "SKR04",
			"taxonomy_version": "6.9",
			"rules": [
				{
					"account": accounts[number],
					"account_number": number,
					"concept": concept,
					"purpose": "both",
				}
				for number, concept in RULES.items()
			],
		}
	)
	mapping.flags.taxonomy_noted = True
	with configured(None):
		mapping.insert(ignore_permissions=True)


def make_assets(accounts: dict[str, str]) -> None:
	"""The asset categories with their accounts for the company, the assets and their depreciation schedules, as ERPNext
	stores them once submitted."""
	for category, (fixed, cumulated, expense) in CATEGORIES.items():
		if frappe.db.exists("Asset Category", category):
			continue
		insert_record("Asset Category", name=category, asset_category_name=category)
		insert_record(
			"Asset Category Account",
			name=f"{category}-{ABBR}",
			parent=category,
			parenttype="Asset Category",
			parentfield="accounts",
			idx=1,
			company_name=COMPANY,
			fixed_asset_account=accounts[fixed],
			accumulated_depreciation_account=accounts[cumulated] if cumulated else None,
			depreciation_expense_account=accounts[expense] if expense else None,
		)
	for name, (label, category, purchased, amount, schedule) in ASSETS.items():
		if frappe.db.exists("Asset", name):
			continue
		insert_record(
			"Asset",
			name=name,
			asset_name=label,
			company=COMPANY,
			asset_category=category,
			purchase_date=purchased,
			available_for_use_date=purchased,
			net_purchase_amount=amount,
			calculate_depreciation=int(bool(schedule)),
			opening_accumulated_depreciation=0,
			status="Partially Depreciated" if schedule else "Submitted",
			docstatus=1,
		)
		if schedule:
			make_schedule(name, schedule)


def make_schedule(
	asset: str, rows: Iterable[tuple[str, int, str | None]], finance_book: str | None = None
) -> str:
	"""An active depreciation schedule of the asset in the finance book, without one for None."""
	name = f"{asset}-{finance_book or 'ohne'}"
	insert_record(
		"Asset Depreciation Schedule",
		name=name,
		asset=asset,
		company=COMPANY,
		finance_book=finance_book,
		status="Active",
		docstatus=1,
	)
	cumulated = 0
	for index, (day, amount, journal_entry) in enumerate(rows, start=1):
		cumulated += amount
		insert_record(
			"Depreciation Schedule",
			name=f"{name}-{index}",
			parent=name,
			parenttype="Asset Depreciation Schedule",
			parentfield="depreciation_schedule",
			idx=index,
			schedule_date=day,
			depreciation_amount=amount,
			accumulated_depreciation_amount=cumulated,
			journal_entry=journal_entry,
		)
	return name


def post_once(
	accounts: dict[str, str],
	voucher_type: str,
	voucher_no: str,
	posting_date: str,
	rows: Iterable[tuple[str, int, int]],
	*,
	against: str | None = None,
	finance_book: str | None = None,
) -> None:
	"""The GL Entries of a voucher by account numbers, unless the voucher has some: the opening entry as ERPNext marks
	it, a depreciation against its asset."""
	if frappe.db.exists("GL Entry", {"voucher_type": voucher_type, "voucher_no": voucher_no}):
		return
	for number, debit, credit in rows:
		insert_record(
			"GL Entry",
			company=COMPANY,
			posting_date=posting_date,
			account=accounts[number],
			debit=debit,
			credit=credit,
			debit_in_account_currency=debit,
			credit_in_account_currency=credit,
			voucher_type=voucher_type,
			voucher_no=voucher_no,
			against_voucher_type="Asset" if against else None,
			against_voucher=against,
			finance_book=finance_book,
			is_cancelled=0,
			is_opening="Yes" if voucher_no == OPENING_ENTRY else "No",
			docstatus=1,
		)


def post_for_the_test(
	test: TestCase,
	accounts: dict[str, str],
	voucher_no: str,
	posting_date: str,
	rows: Iterable[tuple[str, int, int]],
	*,
	voucher_type: str = "Journal Entry",
	against: str | None = None,
	finance_book: str | None = None,
) -> None:
	"""The GL Entries of a voucher for one test, which its cleanup takes out again."""
	test.addCleanup(frappe.db.delete, "GL Entry", {"voucher_type": voucher_type, "voucher_no": voucher_no})
	post_once(
		accounts,
		voucher_type,
		voucher_no,
		posting_date,
		rows,
		against=against,
		finance_book=finance_book,
	)


def set_for_the_test(test: TestCase, doctype: str, name: str, **values: Any) -> None:
	"""Values of a record for one test, written as stored; the cleanup writes the stored ones again."""
	kept = frappe.db.get_value(doctype, name, list(values), as_dict=True)
	test.addCleanup(frappe.db.set_value, doctype, name, dict(kept))
	frappe.db.set_value(doctype, name, values)


def filed_voranmeldung(test: TestCase, index: int, kennzahlen: dict[str, int]) -> None:
	"""A Voranmeldung of the year as the VAT Return keeps it once filed, with its Kennzahlen as filed, for one test."""
	name = f"STEB-USTVA-{YEAR}-{index:02d}"
	test.addCleanup(frappe.db.delete, "VAT Return Kennzahl", {"parent": name})
	test.addCleanup(frappe.db.delete, "VAT Return", {"name": name})
	insert_record(
		"VAT Return",
		name=name,
		company=COMPANY,
		year=YEAR,
		rhythm="monthly",
		period_index=index,
		kz83=0,
		sondervorauszahlung=0,
		status=FILED,
		docstatus=1,
	)
	for row, (kennzahl, amount) in enumerate(kennzahlen.items(), start=1):
		insert_record(
			"VAT Return Kennzahl",
			name=f"{name}-{kennzahl}",
			parent=name,
			parenttype="VAT Return",
			parentfield="kennzahlen",
			idx=row,
			kennzahl=kennzahl,
			amount=amount,
			reported=amount,
			final=amount,
		)


def taxonomy_root() -> Path:
	"""The directory of the HGB-Taxonomie 6.9 installed as Taxonomie einrichten installs it, from the package of
	STEUERBOTE_TAXONOMY_6_9."""
	return real.installation().path.parent


@contextmanager
def configured(root: Path | None) -> Iterator[None]:
	"""common_site_config.json of the bench naming root as the directory of the taxonomies; for None an empty
	directory of its own, so that no taxonomy is installed."""
	config = frappe._dict({TAXONOMY_ROOT: str(root or tempfile.mkdtemp(prefix="steuerbote-ohne-taxonomie-"))})
	with patch.object(transmission_adapter, "common_site_config", return_value=config):
		yield


def discard_documents() -> None:
	"""Take the E-Bilanzen of the tests out with their ELSTER Transmissions and files: a filed E-Bilanz cannot be
	cancelled."""
	frappe.db.delete(TRANSMISSION, {"document_type": DOCTYPE})
	for name in frappe.get_all(DOCTYPE, filters={"company": COMPANY}, pluck="name"):
		frappe.db.delete("File", {"attached_to_doctype": DOCTYPE, "attached_to_name": name})
		frappe.db.set_value(DOCTYPE, name, "docstatus", 2, update_modified=False)
		frappe.delete_doc(DOCTYPE, name, force=True, ignore_permissions=True)


def new_document(**fields: Any) -> Document:
	"""An E-Bilanz of the company for the year, a Jahresabschluss unless the fields say otherwise."""
	return frappe.get_doc({"doctype": DOCTYPE, "company": COMPANY, "year": YEAR, **fields}).insert()


def finding_codes(doc: Document) -> list[str]:
	return [row.code for row in doc.findings]


def blocking_codes(doc: Document) -> list[str]:
	return [row.code for row in doc.findings if row.blocking]


def hint_codes(doc: Document) -> list[str]:
	return [row.code for row in doc.findings if not row.blocking]
