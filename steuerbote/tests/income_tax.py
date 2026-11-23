"""The worked example „Muster IT GmbH“ (steuerbote/kst/tests/test_golden.py) as ERPNext keeps it, for the Frappe tests
of the Körperschaft- and the Gewerbesteuererklärung and of the report Ertragsteuer-Kontennachweis.

A GmbH with SKR03 accounts and the calendar year as its Wirtschaftsjahr 2026 books revenue less expenses of 100,000
euros (among them rent 24,000, car leasing 6,000, software licences 10,000, interest 5,000, entertainment 1,400 and
600, gifts 300, a Verspätungszuschlag 200 and a donation 1,000), CFD gains of 40,000 and losses of 55,000, dividends of
8,000 from Gamma AG (0.5 %) and of 12,000 from Beta GmbH (12 %), a gain of 30,000 and a loss of 12,000 on sales of
shares and a write-down of 4,000: 119,000 euros before taxes on income. Booked in the year: Vorauszahlungen of 10,000
euros Körperschaftsteuer, 550 Solidaritätszuschlag and 15,000 Gewerbesteuer, and Kapitalertragsteuer of 5,000 with 275
Solidaritätszuschlag on the dividends. The ledger is written as GL Entries of the vouchers (post_ledger), since the
returns read nothing else of them.

The Annual Filing Settings name the shareholder, the holdings register, the Vorauszahlungen of the notices, the one
Betriebsstätte with a Hebesatz of 400 % and the day the Steuerberatung reviewed the returns; the Income Tax Mapping
takes the defaults of SKR03 („Vorgaben laden“) with the CFD accounts 2654 and 2166 classed as Termingeschäfte; a return
lists the § 8b results, the two Steuerbescheinigungen and the receipt of the donation (RETURN_TABLES). The result: zu
versteuerndes Einkommen 111,200 euros, Körperschaftsteuer 16,680.00, Solidaritätszuschlag 917.40, due 1,680.00 and
92.40; Gewerbeertrag 107,600, Messbetrag 3,766, Gewerbesteuer 15,064.00, due 64.00. Every name, number and amount is
invented.

A test class makes the records unless the site has them (make_muster_it_gmbh), and a test that changes one of them for
itself sets it back (change_for_the_test, post_for_the_test).
"""

from collections.abc import Callable, Iterable
from copy import deepcopy
from datetime import date
from decimal import Decimal
from typing import Any
from unittest import TestCase

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	make_account,
	make_company,
	make_settings,
	post_ledger,
)

COMPANY = "Steuerbote Test Muster IT GmbH"
ABBR = "STMIT"
YEAR = 2026
CORPORATE = "Corporate Income Tax Return"
TRADE = "Trade Tax Return"
SETTINGS = "Annual Filing Settings"
MAPPING = "Income Tax Mapping"
JOURNAL_ENTRY = "Journal Entry"
TRANSMISSION = "ELSTER Transmission"
# The accounts of SKR03 the example books on, with the provisions and claims of steuerbote.kst.provisions and 2219,
# the foreign taxes, which the example leaves without a balance.
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"4120": ("Gehälter", "Expense"),
	"4210": ("Miete (unbewegliche Wirtschaftsgüter)", "Expense"),
	"4570": ("Mietleasing Kfz", "Expense"),
	"4964": (
		"Aufwendungen für die zeitlich befristete Überlassung von Rechten (Lizenzen, Konzessionen)",
		"Expense",
	),
	"2110": ("Zinsaufwendungen für kurzfristige Verbindlichkeiten", "Expense"),
	"4650": ("Bewirtungskosten", "Expense"),
	"4654": ("Nicht abzugsfähige Bewirtungskosten", "Expense"),
	"4635": ("Geschenke nicht abzugsfähig ohne § 37b EStG", "Expense"),
	"4397": ("Steuerlich nicht abzugsfähige Verspätungszuschläge und Zwangsgelder", "Expense"),
	"2383": ("Zuwendungen, Spenden für kirchliche, religiöse und gemeinnützige Zwecke", "Expense"),
	"4980": ("Sonstiger Betriebsbedarf", "Expense"),
	"2654": ("Erträge aus anderen Wertpapieren und Ausleihungen des Umlaufvermögens", "Income"),
	"2166": ("Aufwendungen aus Bewertung Finanzmittelfonds", "Expense"),
	"2655": ("Erträge aus Anteilen an Kapitalgesellschaften (Umlaufvermögen)", "Income"),
	"2625": ("Erträge aus Anteilen an Kapitalgesellschaften (Finanzanlagevermögen)", "Income"),
	"2726": ("Erträge aus dem Abgang von Gegenständen des Umlaufvermögens (außer Vorräte)", "Income"),
	"2326": ("Verluste aus dem Abgang von Gegenständen des Umlaufvermögens (außer Vorräte)", "Expense"),
	"4876": ("Abschreibungen auf Wertpapiere des Umlaufvermögens", "Expense"),
	"2200": ("Körperschaftsteuer", "Expense"),
	"2208": ("Solidaritätszuschlag", "Expense"),
	"4320": ("Gewerbesteuer", "Expense"),
	"2213": ("Kapitalertragsteuer 25 %", "Expense"),
	"2216": ("Anrechenbarer Solidaritätszuschlag auf Kapitalertragsteuer 25 %", "Expense"),
	"2219": ("Anrechnung/Abzug ausländische Quellensteuer", "Expense"),
	"0963": ("Körperschaftsteuerrückstellung", "Liability"),
	"0956": ("Gewerbesteuerrückstellung nach § 4 Abs. 5b EStG", "Liability"),
	"1549": ("Körperschaftsteuerrückforderung", "Asset"),
	"1540": ("Forderungen aus Gewerbesteuerüberzahlungen", "Asset"),
	"1200": ("Bank", "Asset"),
}
DERIVATIVES = ("2654", "2166")
"""The CFD accounts, which the Steuerberatung classes as Termingeschäfte (§ 15 Absatz 4 Satz 3 EStG)."""

type Rows = tuple[tuple[str, str | int, str | int], ...]
LEDGER: tuple[tuple[str, str, str, Rows], ...] = (
	("Sales Invoice", "SINV-STMIT-1", "2026-06-30", (("8400", 0, "220000.00"), ("1200", "220000.00", 0))),
	("Journal Entry", "JV-STMIT-GEHALT", "2026-12-31", (("4120", "60000.00", 0), ("1200", 0, "60000.00"))),
	(
		"Purchase Invoice",
		"PINV-STMIT-MIETE",
		"2026-12-31",
		(("4210", "24000.00", 0), ("1200", 0, "24000.00")),
	),
	(
		"Purchase Invoice",
		"PINV-STMIT-LEASING",
		"2026-12-31",
		(("4570", "6000.00", 0), ("1200", 0, "6000.00")),
	),
	(
		"Purchase Invoice",
		"PINV-STMIT-LIZENZ",
		"2026-12-31",
		(("4964", "10000.00", 0), ("1200", 0, "10000.00")),
	),
	("Journal Entry", "JV-STMIT-ZINS", "2026-12-31", (("2110", "5000.00", 0), ("1200", 0, "5000.00"))),
	(
		"Purchase Invoice",
		"PINV-STMIT-BEWIRTUNG",
		"2026-09-15",
		(("4650", "1400.00", 0), ("4654", "600.00", 0), ("1200", 0, "2000.00")),
	),
	("Purchase Invoice", "PINV-STMIT-GESCHENK", "2026-12-10", (("4635", "300.00", 0), ("1200", 0, "300.00"))),
	("Journal Entry", "JV-STMIT-ZUSCHLAG", "2026-08-20", (("4397", "200.00", 0), ("1200", 0, "200.00"))),
	("Journal Entry", "JV-STMIT-SPENDE", "2026-11-30", (("2383", "1000.00", 0), ("1200", 0, "1000.00"))),
	(
		"Purchase Invoice",
		"PINV-STMIT-BEDARF",
		"2026-12-31",
		(("4980", "11500.00", 0), ("1200", 0, "11500.00")),
	),
	(
		"Journal Entry",
		"JV-STMIT-CFD-GEWINN",
		"2026-04-15",
		(("2654", 0, "40000.00"), ("1200", "40000.00", 0)),
	),
	(
		"Journal Entry",
		"JV-STMIT-CFD-VERLUST",
		"2026-10-15",
		(("2166", "55000.00", 0), ("1200", 0, "55000.00")),
	),
	(
		"Journal Entry",
		"JV-STMIT-DIV-GAMMA",
		"2026-05-20",
		(("2655", 0, "8000.00"), ("2213", "2000.00", 0), ("2216", "110.00", 0), ("1200", "5890.00", 0)),
	),
	(
		"Journal Entry",
		"JV-STMIT-DIV-BETA",
		"2026-06-15",
		(("2625", 0, "12000.00"), ("2213", "3000.00", 0), ("2216", "165.00", 0), ("1200", "8835.00", 0)),
	),
	(
		"Journal Entry",
		"JV-STMIT-VERKAUF-DELTA",
		"2026-04-30",
		(("2726", 0, "30000.00"), ("1200", "30000.00", 0)),
	),
	(
		"Journal Entry",
		"JV-STMIT-VERKAUF-EPSILON",
		"2026-09-30",
		(("2326", "12000.00", 0), ("1200", 0, "12000.00")),
	),
	("Journal Entry", "JV-STMIT-TW-ZETA", "2026-12-31", (("4876", "4000.00", 0), ("1200", 0, "4000.00"))),
	*(
		(
			"Journal Entry",
			f"JV-STMIT-VZ-KST-{quarter}",
			f"2026-{month:02d}-10",
			(("2200", "2500.00", 0), ("2208", "137.50", 0), ("1200", 0, "2637.50")),
		)
		for quarter, month in ((1, 3), (2, 6), (3, 9), (4, 12))
	),
	*(
		(
			"Journal Entry",
			f"JV-STMIT-VZ-GEWST-{quarter}",
			f"2026-{month:02d}-15",
			(("4320", "3750.00", 0), ("1200", 0, "3750.00")),
		)
		for quarter, month in ((1, 2), (2, 5), (3, 8), (4, 11))
	),
)
"""The vouchers of the year: type, name, posting date and rows of (account number, debit, credit)."""

AGS = "09999999"
HEBESATZ_SOURCE = "Haushaltssatzung 2026 der Gemeinde Musterstadt"
# The day the Steuerberatung confirmed the classes of the trading accounts and the review list of the returns, which the
# Körperschaft- and the Gewerbesteuererklärung wait for (decision 6.4 of the contract of stage 3).
REVIEWED_ON = "2026-11-02"
SHAREHOLDER = {
	"shareholder_name": "Erika Musterfrau",
	"kind": "Natural Person",
	"percent": 100,
	"nominal_amount": 25000,
	"from_date": "2020-01-01",
	"street": "Musterweg 2",
	"postal_code_and_town": "12345 Musterstadt",
}
ESTABLISHMENT = {"municipality": "Musterstadt", "postal_code": "12345", "ags": AGS, "from_date": "2020-01-01"}
ANNUAL_FILING_SETTINGS = {
	"legal_form": "GmbH",
	"business_purpose": "Softwareentwicklung",
	"management_seat": "Musterstadt",
	"registered_seat": "Musterstadt",
	"street": "Musterweg",
	"house_number": "1",
	"postal_code": "12345",
	"city": "Musterstadt",
	"country": "Germany",
	"income_tax_review_on": REVIEWED_ON,
	"shareholders": [SHAREHOLDER],
	"establishments": [ESTABLISHMENT],
	"trade_tax_rates": [{"ags": AGS, "year": YEAR, "hebesatz": 400, "source": HEBESATZ_SOURCE}],
	"holdings": [
		{
			"holding_name": "Gamma AG",
			"year": YEAR,
			"percent_on_1_january": 0.5,
			"percent_at_start_of_ez": 0.5,
		},
		{"holding_name": "Beta GmbH", "year": YEAR, "percent_on_1_january": 12, "percent_at_start_of_ez": 12},
	],
	"prepayments": [
		*(
			{"tax": tax, "year": YEAR, "due_date": f"2026-{month:02d}-10", "amount": amount}
			for tax, amount in (("KSt", 2500), ("SolZ", 137.5))
			for month in (3, 6, 9, 12)
		),
		*(
			{"tax": "GewSt", "year": YEAR, "due_date": f"2026-{month:02d}-15", "amount": 3750}
			for month in (2, 5, 8, 11)
		),
	],
}
DATENLIEFERANT = {
	"filer_name": COMPANY,
	"street": "Musterweg 1",
	"postal_code": "12345",
	"city": "Musterstadt",
	"phone": "01234 567890",
	"email": "buchhaltung@example.org",
}
RETURN_TABLES = {
	"holding_results": [
		{"kind": "Dividends", "holding_name": "Gamma AG", "amount": 8000},
		{"kind": "Dividends", "holding_name": "Beta GmbH", "amount": 12000},
		{
			"kind": "Sale",
			"holding_name": "Delta AG",
			"result_date": "2026-04-30",
			"sale_price": 80000,
			"sale_costs": 1000,
			"book_value": 49000,
		},
		{
			"kind": "Sale",
			"holding_name": "Epsilon GmbH",
			"result_date": "2026-09-30",
			"sale_price": 20000,
			"sale_costs": 0,
			"book_value": 32000,
		},
		{"kind": "Write-down", "holding_name": "Zeta GmbH", "amount": 4000},
	],
	"credits": [
		{"issuer": "Musterbank AG", "certificate_date": "2026-05-20", "capital_gains_tax": 2000, "solz": 110},
		{"issuer": "Beta GmbH", "certificate_date": "2026-06-15", "capital_gains_tax": 3000, "solz": 165},
	],
	"donations": [{"recipient": "Musterverein e. V.", "amount": 1000}],
}
"""What the company enters in the Körperschaftsteuererklärung: the dividends of the holdings, the sales of shares with
their price, costs and book value, a gain of 30,000 and a loss of 12,000, the write-down with the company it concerns,
the Steuerbescheinigungen and the Zuwendungsbestätigung."""


def money(value: object) -> Decimal:
	"""A currency field as the tests compare it, in cents."""
	return Decimal(str(flt(value, 2))).quantize(Decimal("0.01"))


def make_muster_it_gmbh() -> dict[str, str]:
	"""The company with its accounts, Fiscal Year, VAT Return Settings, Annual Filing Settings, Income Tax Mapping and
	ledger, each made unless the site has it; returns the accounts by number."""
	make_company(COMPANY, ABBR)
	accounts = make_accounts(COMPANY, ACCOUNTS)
	ensure_fiscal_year(COMPANY, date(YEAR, 6, 30))
	if not frappe.db.exists("VAT Return Settings", COMPANY):
		make_settings(COMPANY, [(YEAR, "monthly", 1)], **DATENLIEFERANT)
	if not frappe.db.exists(SETTINGS, COMPANY):
		frappe.get_doc({"doctype": SETTINGS, "company": COMPANY, **deepcopy(ANNUAL_FILING_SETTINGS)}).insert(
			ignore_permissions=True
		)
	make_income_tax_mapping(COMPANY, DERIVATIVES)
	for voucher_type, voucher_no, posting_date, rows in LEDGER:
		post_once(COMPANY, accounts, voucher_type, voucher_no, posting_date, rows)
	return accounts


def make_accounts(company: str, accounts: dict[str, tuple[str, str]]) -> dict[str, str]:
	"""The accounts of the company by number, each made unless it has one of that number."""
	return {
		number: frappe.db.get_value("Account", {"company": company, "account_number": number})
		or make_account(company, number, name, root_type)
		for number, (name, root_type) in accounts.items()
	}


def make_income_tax_mapping(company: str, derivatives: Iterable[str] = ()) -> None:
	"""The Income Tax Mapping of „Vorgaben laden“, with the trading accounts named classed as Termingeschäfte, unless
	the company has one."""
	if frappe.db.exists(MAPPING, company):
		return
	mapping = frappe.new_doc(MAPPING)
	mapping.update({"company": company, "chart": "SKR03"})
	mapping.load_defaults()
	classed = set(derivatives)
	for row in mapping.rules:
		if row.account_number in classed:
			row.trading_class = "derivatives"
	mapping.insert(ignore_permissions=True)


def post_once(
	company: str, accounts: dict[str, str], voucher_type: str, voucher_no: str, posting_date: str, rows: Rows
) -> None:
	"""The GL Entries of a voucher by account numbers, unless the voucher has some."""
	if frappe.db.exists(
		"GL Entry", {"company": company, "voucher_type": voucher_type, "voucher_no": voucher_no}
	):
		return
	post_ledger(
		company,
		voucher_type,
		voucher_no,
		posting_date,
		[(accounts[number], debit, credit) for number, debit, credit in rows],
	)


def post_for_the_test(
	test: TestCase,
	voucher_no: str,
	posting_date: str,
	rows: Iterable[tuple[str, str | int, str | int]],
	company: str = COMPANY,
) -> None:
	"""The GL Entries of a Journal Entry by account name for one test, which its cleanup takes out again."""
	test.addCleanup(frappe.db.delete, "GL Entry", {"voucher_type": JOURNAL_ENTRY, "voucher_no": voucher_no})
	post_ledger(company, JOURNAL_ENTRY, voucher_no, posting_date, list(rows))


def change_for_the_test(test: TestCase, doctype: str, name: str, change: Callable[[Document], Any]) -> None:
	"""Change a record for one test: ``change`` edits it, the record is saved, and the cleanup of the test saves it
	again as it was."""
	doc = frappe.get_doc(doctype, name)
	kept = doc.as_dict(no_default_fields=True)
	test.addCleanup(_restore, doctype, name, kept)
	change(doc)
	doc.save(ignore_permissions=True)


def _restore(doctype: str, name: str, kept: dict[str, Any]) -> None:
	doc = frappe.get_doc(doctype, name)
	doc.update(kept)
	doc.save(ignore_permissions=True)


def discard_returns() -> None:
	"""Take the returns of the tests out with their ELSTER Transmissions and the Journal Entries of their provisions: a
	filed return cannot be cancelled, and a submitted Journal Entry would stay in the ledger of the next test. The
	Gewerbesteuererklärungen go first, since they name a Körperschaftsteuererklärung."""
	for doctype in (TRADE, CORPORATE):
		frappe.db.delete(TRANSMISSION, {"document_type": doctype})
		for name in frappe.get_all(doctype, pluck="name"):
			frappe.db.set_value(doctype, name, "docstatus", 2, update_modified=False)
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
	for name in frappe.get_all(JOURNAL_ENTRY, filters={"company": COMPANY}, pluck="name"):
		frappe.db.delete("GL Entry", {"voucher_type": JOURNAL_ENTRY, "voucher_no": name})
		frappe.db.delete("Journal Entry Account", {"parent": name})
		frappe.db.delete(JOURNAL_ENTRY, {"name": name})


def new_return(company: str = COMPANY, tables: dict | None = None, **fields: Any) -> Document:
	"""A Körperschaftsteuererklärung of the year with the tables of the example, or those given."""
	tables = RETURN_TABLES if tables is None else tables
	return frappe.get_doc(
		{"doctype": CORPORATE, "company": company, "year": YEAR, **deepcopy(tables), **fields}
	).insert()


def finding_codes(doc: Document) -> list[str]:
	return [row.code for row in doc.findings]


def blocking_codes(doc: Document) -> list[str]:
	return [row.code for row in doc.findings if row.blocking]


def hint_codes(doc: Document) -> list[str]:
	return [row.code for row in doc.findings if not row.blocking]
