"""The invented „Steuerbote Test Zusammenspiel GmbH“ as ERPNext keeps it, for the Frappe tests of the annual filings
together: the Jahresabschluss, the E-Bilanz, the Körperschaft- and the Gewerbesteuererklärung, the
Umsatzsteuererklärung and Offene Fristen of one year.

A GmbH with SKR04 accounts, founded on 2 January 2025 with a Stammkapital of 25,000 euros, earns 20,000 euros in 2025.
In 2026 it sells for 200,000 euros, buys goods for 60,000, pays salaries of 50,000 and rent of 11,960 for its office,
and the Vorauszahlungen of its notices, 2,500 euros Körperschaftsteuer with 137.50 Solidaritätszuschlag and 2,000 euros
Gewerbesteuer a quarter: a Jahresüberschuss of 59,490 euros before the provisions and a Bilanzsumme of 104,490. Its
zu versteuerndes Einkommen is 78,040 euros, its Körperschaftsteuer 11,706 with 643.83 Solidaritätszuschlag, and at a
Hebesatz of 400 % on a Gewerbeertrag of 78,040, 78,000 once rounded, its Gewerbesteuer 10,920; „Rückstellungen
vorschlagen“ proposes 1,706, 93.83 and 2,920 euros, after which the Jahresüberschuss is 54,770.17. The rent keeps the
Solidaritätszuschlag off half a euro, which lines 11 and 82 of Anlage GK would both round up once the provisions are
posted. With Umsatzerlöse of 200,000 euros, a Bilanzsumme of 104,490 and no employees it is a
Kleinstkapitalgesellschaft at both closing dates (§ 267a Abs. 1 HGB).

The Annual Filing Settings name the shareholder, the Geschäftsführerin who signs, the register, the one Betriebsstätte
with its Hebesatz and the Vorauszahlungen; the Income Tax Mapping, the Balance Sheet Mapping and the VAT Return Mapping
take the defaults of SKR04 („Vorgaben laden“), the Balance Sheet Mapping with the HGB-Taxonomie 6.9 installed as
„Taxonomie einrichten“ installs it. For a Handelsbilanz with Überleitungsrechnung, a Rückstellung für drohende Verluste
of 2,000 euros counts in the Handelsbilanz alone, since § 5 Abs. 4a EStG keeps it out of the Steuerbilanz, which the
finance book of the Steuerbilanz reverses (DROHVERLUST). The ledger is written as GL Entries of Journal Entries
(post_ledger), which is all the annual documents read of it. Every name, number and amount is invented.

A test class makes the records unless the site has them (make_company_with_books), and each test takes out the
documents it made (discard) and the postings it made for itself (post_for_the_test).
"""

from collections.abc import Iterable
from copy import deepcopy
from datetime import date
from decimal import Decimal
from typing import Any
from unittest import TestCase

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from steuerbote.steuerbote.doctype.annual_filing_settings.annual_filing_settings import record_adoption
from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	insert_record,
	make_company,
	make_mapping,
	make_settings,
	post_ledger,
)
from steuerbote.tests.income_tax import make_accounts

COMPANY = "Steuerbote Test Zusammenspiel GmbH"
ABBR = "STZS"
YEAR = 2026
FOUNDED = date(2025, 1, 2)
SETTINGS = "Annual Filing Settings"
ACCOUNTS_DOCTYPE = "Annual Accounts"
EBILANZ = "Electronic Balance Sheet"
CORPORATE = "Corporate Income Tax Return"
TRADE = "Trade Tax Return"
VAT = "Annual VAT Return"
TRANSMISSION = "ELSTER Transmission"
JOURNAL_ENTRY = "Journal Entry"
TAX_BOOK = "Steuerbilanz Steuerbote Test Zusammenspiel"
ACCOUNTS = {
	"1800": ("Bank", "Asset"),
	"1435": ("Forderungen aus Gewerbesteuerüberzahlungen", "Asset"),
	"1450": ("Körperschaftsteuerrückforderung", "Asset"),
	"2900": ("Gezeichnetes Kapital", "Equity"),
	"2970": ("Gewinnvortrag vor Verwendung", "Equity"),
	"3035": ("Gewerbesteuerrückstellung nach § 4 Abs. 5b EStG", "Liability"),
	"3040": ("Körperschaftsteuerrückstellung", "Liability"),
	"3075": ("Rückstellungen für drohende Verluste aus schwebenden Geschäften", "Liability"),
	"4400": ("Erlöse 19 % USt", "Income"),
	"5400": ("Wareneingang 19 % Vorsteuer", "Expense"),
	"6020": ("Gehälter", "Expense"),
	"6310": ("Miete (unbewegliche Wirtschaftsgüter)", "Expense"),
	"6960": ("Periodenfremde Aufwendungen", "Expense"),
	"7600": ("Körperschaftsteuer", "Expense"),
	"7608": ("Solidaritätszuschlag", "Expense"),
	"7610": ("Gewerbesteuer", "Expense"),
}
CLOSING_ACCOUNT = "2970"

type Rows = tuple[tuple[str, str | int, str | int], ...]
LEDGER: tuple[tuple[str, str, Rows], ...] = (
	("KAPITAL", "2025-01-02", (("1800", "25000", 0), ("2900", 0, "25000"))),
	("ERLOES-2025", "2025-06-30", (("1800", "100000", 0), ("4400", 0, "100000"))),
	("WARE-2025", "2025-06-30", (("5400", "40000", 0), ("1800", 0, "40000"))),
	("GEHALT-2025", "2025-12-31", (("6020", "40000", 0), ("1800", 0, "40000"))),
	("ERLOES", "2026-06-30", (("1800", "200000", 0), ("4400", 0, "200000"))),
	("WARE", "2026-06-30", (("5400", "60000", 0), ("1800", 0, "60000"))),
	("GEHALT", "2026-12-31", (("6020", "50000", 0), ("1800", 0, "50000"))),
	("MIETE", "2026-12-31", (("6310", "11960", 0), ("1800", 0, "11960"))),
	*(
		(
			f"VZ-KST-{month}",
			f"2026-{month:02d}-10",
			(("7600", "2500", 0), ("7608", "137.50", 0), ("1800", 0, "2637.50")),
		)
		for month in (3, 6, 9, 12)
	),
	*(
		(f"VZ-GEWST-{month}", f"2026-{month:02d}-15", (("7610", "2000", 0), ("1800", 0, "2000")))
		for month in (2, 5, 8, 11)
	),
)
"""The Journal Entries of the company: name, posting date and rows of (account number, debit, credit)."""
DROHVERLUST = (
	("DROHVERLUST", (("6960", "2000", 0), ("3075", 0, "2000")), None),
	("DROHVERLUST-STEUERLICH", (("3075", "2000", 0), ("6960", 0, "2000")), TAX_BOOK),
)
"""A Rückstellung für drohende Verluste of the Handelsbilanz, which the finance book of the Steuerbilanz reverses."""
AGS = "09999998"
DIRECTOR = "Erika Beispiel"
SEAT = "Musterstadt"
REVIEWED_ON = "2026-11-02"
ANNUAL_FILING_SETTINGS = {
	"legal_form": "GmbH",
	"business_purpose": "Softwareentwicklung",
	"management_seat": SEAT,
	"registered_seat": SEAT,
	"register_court": "Amtsgericht Musterstadt",
	"register_type": "HRB",
	"register_number": "99907",
	"street": "Musterweg",
	"house_number": "7",
	"postal_code": "12345",
	"city": SEAT,
	"country": "Germany",
	"income_tax_review_on": REVIEWED_ON,
	"shareholders": [
		{
			"shareholder_name": "Max Mustermann",
			"kind": "Natural Person",
			"percent": 100,
			"nominal_amount": 25000,
			"from_date": "2025-01-02",
			"street": "Musterweg 8",
			"postal_code_and_town": "12345 Musterstadt",
		}
	],
	"directors": [
		{"director_name": DIRECTOR, "role": "Geschäftsführerin", "from_date": "2025-01-02", "signs": 1}
	],
	"establishments": [{"municipality": SEAT, "postal_code": "12345", "ags": AGS, "from_date": "2025-01-02"}],
	"trade_tax_rates": [
		{
			"ags": AGS,
			"year": YEAR,
			"hebesatz": 400,
			"source": "Haushaltssatzung 2026 der Gemeinde Musterstadt",
		}
	],
	"prepayments": [
		*(
			{"tax": tax, "year": YEAR, "due_date": f"2026-{month:02d}-10", "amount": amount}
			for tax, amount in (("KSt", 2500), ("SolZ", 137.5))
			for month in (3, 6, 9, 12)
		),
		*(
			{"tax": "GewSt", "year": YEAR, "due_date": f"2026-{month:02d}-15", "amount": 2000}
			for month in (2, 5, 8, 11)
		),
	],
}
DATENLIEFERANT = {
	"filer_name": COMPANY,
	"street": "Musterweg 7",
	"postal_code": "12345",
	"city": SEAT,
	"phone": "01234 567890",
	"email": "buchhaltung@example.org",
}
ADOPTED_ON = "2027-05-12"
"""The day the shareholders adopt the Jahresabschluss 2026, after the fiscal year; the tests run on a day after it
(AFTER_ADOPTION), so that it lies neither in the fiscal year nor in the future."""
AFTER_ADOPTION = "2027-05-20 10:00:00"
REMARKS = (
	"Mit der Steuerberatung abgestimmt: Die Vordrucke 2026 entsprechen denen der Jahresdokumentation 2025."
)
FILED_NOTE = "Am 20. Mai 2027 durch die Steuerberatung übermittelt, das Protokoll liegt in den Unterlagen."


def money(value: object) -> Decimal:
	"""A currency field as the tests compare it, in cents."""
	return Decimal(str(flt(value, 2))).quantize(Decimal("0.01"))


def make_company_with_books() -> dict[str, str]:
	"""The company with its accounts, Fiscal Years, finance book, settings, mappings and ledger, each made unless the
	site has it; the Balance Sheet Mapping wants the taxonomy installed (steuerbote.tests.ebilanz.configured).
	Returns the accounts by number."""
	make_company(COMPANY, ABBR)
	frappe.db.set_value("Company", COMPANY, "date_of_establishment", FOUNDED)
	accounts = make_accounts(COMPANY, ACCOUNTS)
	for year in (YEAR - 1, YEAR, YEAR + 1):
		ensure_fiscal_year(COMPANY, date(year, 6, 30))
	if not frappe.db.exists("Finance Book", TAX_BOOK):
		frappe.get_doc({"doctype": "Finance Book", "finance_book_name": TAX_BOOK}).insert(
			ignore_permissions=True
		)
	if not frappe.db.exists("VAT Return Settings", COMPANY):
		make_settings(COMPANY, [(YEAR, "monthly", 1)], **DATENLIEFERANT)
	if not frappe.db.exists(SETTINGS, COMPANY):
		frappe.get_doc(
			{
				"doctype": SETTINGS,
				"company": COMPANY,
				"closing_account": accounts[CLOSING_ACCOUNT],
				**deepcopy(ANNUAL_FILING_SETTINGS),
			}
		).insert(ignore_permissions=True)
	for doctype in ("Income Tax Mapping", "Balance Sheet Mapping"):
		if not frappe.db.exists(doctype, COMPANY):
			mapping = frappe.new_doc(doctype)
			mapping.update({"company": COMPANY, "chart": "SKR04"})
			if doctype == "Balance Sheet Mapping":
				mapping.taxonomy_version = "6.9"
			mapping.load_defaults()
			mapping.insert(ignore_permissions=True)
	if not frappe.db.exists("VAT Return Mapping", COMPANY):
		make_mapping(COMPANY, "SKR04")
	for voucher, posting_date, rows in LEDGER:
		post_once(accounts, f"JV-{ABBR}-{voucher}", posting_date, rows)
	return accounts


def post_once(
	accounts: dict[str, str],
	voucher_no: str,
	posting_date: str,
	rows: Rows,
	finance_book: str | None = None,
) -> None:
	"""The GL Entries of a Journal Entry by account numbers, unless the voucher has some."""
	if frappe.db.exists("GL Entry", {"voucher_type": JOURNAL_ENTRY, "voucher_no": voucher_no}):
		return
	post_ledger(
		COMPANY,
		JOURNAL_ENTRY,
		voucher_no,
		posting_date,
		[(accounts[number], debit, credit) for number, debit, credit in rows],
	)
	if finance_book:
		frappe.db.set_value(
			"GL Entry",
			{"voucher_type": JOURNAL_ENTRY, "voucher_no": voucher_no},
			"finance_book",
			finance_book,
		)


def post_for_the_test(
	test: TestCase,
	accounts: dict[str, str],
	voucher_no: str,
	posting_date: str,
	rows: Rows,
	finance_book: str | None = None,
) -> None:
	"""The GL Entries of a Journal Entry for one test, which its cleanup takes out again."""
	test.addCleanup(frappe.db.delete, "GL Entry", {"voucher_type": JOURNAL_ENTRY, "voucher_no": voucher_no})
	post_once(accounts, voucher_no, posting_date, rows, finance_book)


def post_drohverlust(test: TestCase, accounts: dict[str, str]) -> None:
	"""The Rückstellung für drohende Verluste of the Handelsbilanz and its reversal in the finance book of the
	Steuerbilanz, for one test."""
	for voucher, rows, book in DROHVERLUST:
		post_for_the_test(test, accounts, f"JV-{ABBR}-{voucher}", "2026-12-31", rows, book)


def set_for_the_test(test: TestCase, doctype: str, name: str, **values: Any) -> None:
	"""Values of a record for one test, written as stored; the cleanup writes the stored ones again."""
	kept = frappe.db.get_value(doctype, name, list(values), as_dict=True)
	test.addCleanup(frappe.db.set_value, doctype, name, dict(kept))
	frappe.db.set_value(doctype, name, values)


def new_document(doctype: str, **fields: Any) -> Document:
	return frappe.get_doc({"doctype": doctype, "company": COMPANY, "year": YEAR, **fields}).insert()


def calculated(doctype: str, **fields: Any) -> Document:
	doc = new_document(doctype, **fields)
	doc.calculate()
	doc.reload()
	return doc


def filed_ebilanz_of_2025(test: TestCase, equity: str, subscribed: str) -> str:
	"""The E-Bilanz of 2025 as it stands once filed outside Steuerbote, with the Betriebsvermögen and the gezeichnetes
	Kapital of its Steuerbilanz, for one test; written as stored, since the tests of KSt 1 F read nothing else of it."""
	name = f"EB-2025-{ABBR}-1"
	test.addCleanup(frappe.db.delete, "Electronic Balance Sheet Position", {"parent": name})
	test.addCleanup(frappe.db.delete, EBILANZ, {"name": name})
	insert_record(
		EBILANZ,
		name=name,
		company=COMPANY,
		year=YEAR - 1,
		statement_type="Jahresabschluss",
		accounting_standard="HAOE",
		taxonomy_version="6.9",
		status="Abgegeben",
		docstatus=1,
		filed_via="other_way",
		tax_equity=equity,
	)
	insert_record(
		"Electronic Balance Sheet Position",
		name=f"{name}-1",
		parent=name,
		parenttype=EBILANZ,
		parentfield="positions",
		idx=1,
		concept="bs.eqLiab.equity.subscribed",
		computed=subscribed,
		reported=subscribed,
		tax_amount=subscribed,
		manual=0,
	)
	return name


def discard() -> None:
	"""Take the annual documents of the company out with their ELSTER Transmissions and files, the Journal Entries of the
	provisions with their GL Entries, and the day of the Feststellung out of the settings: a filed document cannot be
	cancelled. The Gewerbesteuererklärungen go first, since they name a Körperschaftsteuererklärung, which names an
	E-Bilanz, which names a Jahresabschluss."""
	for doctype in (TRADE, CORPORATE, VAT, EBILANZ, ACCOUNTS_DOCTYPE):
		for name in frappe.get_all(doctype, filters={"company": COMPANY}, pluck="name"):
			frappe.db.delete(TRANSMISSION, {"document_type": doctype, "document": name})
			frappe.db.delete("File", {"attached_to_doctype": doctype, "attached_to_name": name})
			frappe.db.set_value(doctype, name, "docstatus", 2, update_modified=False)
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
	for name in frappe.get_all(JOURNAL_ENTRY, filters={"company": COMPANY}, pluck="name"):
		frappe.db.delete("GL Entry", {"voucher_type": JOURNAL_ENTRY, "voucher_no": name})
		frappe.db.delete("Journal Entry Account", {"parent": name})
		frappe.db.delete(JOURNAL_ENTRY, {"name": name})
	record_adoption(COMPANY, YEAR, None)


def submitted_provisions(corporate: Document) -> str:
	"""Rückstellungen vorschlagen and submit the draft Journal Entry, as the company does once it checked it."""
	entry = frappe.get_doc(JOURNAL_ENTRY, corporate.propose_provisions())
	entry.submit()
	return entry.name


def festgestellt(answers: Iterable[str] = ()) -> Document:
	"""The Jahresabschluss of the year, calculated, its Angaben answered „nein“ but the Arbeitnehmer and those named,
	adopted on ADOPTED_ON with the signature of the Geschäftsführerin, and submitted, which is its Feststellung; call it
	on a day after the adoption (AFTER_ADOPTION)."""
	doc = calculated(ACCOUNTS_DOCTYPE, remarks=REMARKS)
	named = set(answers)
	for row in doc.notes:
		if row.code != "ARBEITNEHMER" and row.code not in named:
			row.answer = "nein"
	doc.save()
	doc.adopted_on = ADOPTED_ON
	for row in doc.signatories:
		row.signed_on = ADOPTED_ON
	doc.save()
	doc.calculate()
	doc.reload()
	doc.submit()
	return doc


def amended(cancelled: Document) -> Document:
	"""The amendment of a cancelled Jahresabschluss, calculated on the books of today, which keeps its Angaben and
	signatories, adopted again on ADOPTED_ON and submitted; call it on a day after the adoption (AFTER_ADOPTION)."""
	doc = frappe.copy_doc(cancelled)
	doc.update({"docstatus": 0, "amended_from": cancelled.name})
	doc.insert()
	doc.calculate()
	doc.reload()
	doc.adopted_on = ADOPTED_ON
	for row in doc.signatories:
		row.signed_on = ADOPTED_ON
	doc.save()
	doc.calculate()
	doc.reload()
	doc.submit()
	return doc


def finding_codes(doc: Document) -> list[str]:
	return [row.code for row in doc.findings]


def blocking_codes(doc: Document) -> list[str]:
	return [row.code for row in doc.findings if row.blocking]


def hint_codes(doc: Document) -> list[str]:
	return [row.code for row in doc.findings if not row.blocking]


def line(doc: Document, feldkennung: str):
	(row,) = (row for row in doc.lines if row.feldkennung == feldkennung and not row.manual)
	return row
