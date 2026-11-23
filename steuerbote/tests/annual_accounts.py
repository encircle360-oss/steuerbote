"""Two invented companies for the Frappe tests of the Annual Accounts, with SKR03 accounts, the books of 2025 and 2026,
their Annual Filing Settings and their Bilanzzuordnung, and the HGB-Taxonomie 6.9 they are placed with.

- KLEINST, „Steuerbote Test Jahresabschluss Kleinst GmbH“: a Stammkapital of 25,000 euros in January 2025, sales of
  60,000 and costs of 47,900 in 2025, a profit of 12,100 that no Period Closing Voucher closes; in 2026 sales of
  120,000, of which 8,000 open with 1,520 Umsatzsteuer, costs of 98,800, of which 4,000 open, a provision of 1,800
  for the Gewerbesteuer and office furniture of 18,000. Bilanzsumme 65,620 euros, Jahresüberschuss 21,200: a
  Kleinstkapitalgesellschaft at both closing dates (§ 267a Abs. 1 HGB).
- KLEIN, „Steuerbote Test Jahresabschluss Klein GmbH“: the same Stammkapital with a bank loan of 500,000 euros, sales
  of 1,000,000 and costs of 900,000 in 2025; in 2026 sales of 1,200,000, costs of 1,090,000 and a repayment of
  100,000. Bilanzsumme 714,000 euros, Jahresüberschuss 110,000: above two thresholds of a Kleinstkapitalgesellschaft,
  a small company at both closing dates (§ 267 Abs. 1 HGB).

The ledger is written as GL Entries of Journal Entries (post_ledger), which is all the Annual Accounts read of it. The
taxonomy is the package of esteuer.de that STEUERBOTE_TAXONOMY_6_9 names (steuerbote/xbrl/tests/real.py); a test class
installs it with installed_taxonomy before it makes a company, since saving the Bilanzzuordnung checks its positions.
Every name, number and amount is invented.
"""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date
from unittest.mock import patch

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.model.document import Document

from steuerbote.steuerbote.doctype.annual_filing_settings.annual_filing_settings import record_adoption
from steuerbote.steuerbote.doctype.eric_settings import eric_settings
from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	insert_record,
	make_account,
	make_company,
	post_ledger,
)
from steuerbote.xbrl.tests import real

DOCTYPE = "Annual Accounts"
SETTINGS = "Annual Filing Settings"
MAPPING = "Balance Sheet Mapping"
JOURNAL_ENTRY = "Journal Entry"
EMPLOYEE = "Employee"
YEAR = 2026
SHORT, MID = "up to one year", "one to five years"
# SKR03 numbers with the position of the Handelsbilanz each goes to, the position for a balance on the other side and
# the Restlaufzeit; the accounts of the Ergebnisverwendung hold no balance.
ACCOUNTS = {
	"0420": ("Büroeinrichtung", "Asset", "bs.ass.fixAss.tan.otherEquipm", None, None),
	"1200": ("Bank", "Asset", "bs.ass.currAss.cashEquiv.bank", "bs.eqLiab.liab.bank.other", None),
	"1400": (
		"Forderungen aus Lieferungen und Leistungen",
		"Asset",
		"bs.ass.currAss.receiv.trade.other",
		None,
		SHORT,
	),
	"0800": ("Gezeichnetes Kapital", "Equity", "bs.eqLiab.equity.subscribed.corp", None, None),
	"0846": ("Gesetzliche Rücklage", "Equity", "bs.eqLiab.equity.revenueRes.legal", None, None),
	"0855": ("Andere Gewinnrücklagen", "Equity", "bs.eqLiab.equity.revenueRes.other", None, None),
	"0860": ("Gewinnvortrag vor Verwendung", "Equity", "bs.eqLiab.equity.retainedEarnings", None, None),
	"0650": (
		"Verbindlichkeiten gegenüber Kreditinstituten",
		"Liability",
		"bs.eqLiab.liab.bank.other",
		None,
		MID,
	),
	"0755": (
		"Verbindlichkeiten gegenüber Gesellschaftern für offene Ausschüttungen",
		"Liability",
		"bs.eqLiab.liab.shareholders",
		None,
		SHORT,
	),
	"0956": ("Gewerbesteuerrückstellung", "Liability", "bs.eqLiab.accruals.tax.gewst", None, None),
	"1600": (
		"Verbindlichkeiten aus Lieferungen und Leistungen",
		"Liability",
		"bs.eqLiab.liab.trade.genOther",
		None,
		SHORT,
	),
	"1776": ("Umsatzsteuer 19 %", "Liability", "bs.eqLiab.liab.other.theroffTax", None, SHORT),
	"8400": (
		"Erlöse 19 % USt",
		"Income",
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.generalRateVAT",
		None,
		None,
	),
	"3400": (
		"Wareneingang 19 % Vorsteuer",
		"Expense",
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material",
		None,
		None,
	),
	"4120": ("Gehälter", "Expense", "is.netIncome.regular.operatingTC.staff.salaries", None, None),
	"4210": ("Miete", "Expense", "is.netIncome.regular.operatingTC.otherCost.leaseFix.other", None, None),
	"4320": ("Gewerbesteuer", "Expense", "is.netIncome.tax.gewst", None, None),
}
CLOSING_ACCOUNT = "0860"

type Rows = tuple[tuple[str, str, str | int], ...]


@dataclass(frozen=True)
class Company:
	name: str
	abbr: str
	register_number: str
	ledger: tuple[tuple[str, str, tuple[tuple[str, str | int, str | int], ...]], ...]
	"""The Journal Entries of the company: name, posting date and rows of (account number, debit, credit)."""


KLEINST = Company(
	"Steuerbote Test Jahresabschluss Kleinst GmbH",
	"STJK",
	"99901",
	(
		("KAPITAL", "2025-01-02", (("1200", "25000", 0), ("0800", 0, "25000"))),
		("ERLOES-2025", "2025-06-30", (("1200", "60000", 0), ("8400", 0, "60000"))),
		("MATERIAL-2025", "2025-06-30", (("3400", "20000", 0), ("1200", 0, "20000"))),
		("GEHALT-2025", "2025-12-31", (("4120", "25000", 0), ("1200", 0, "25000"))),
		("MIETE-2025", "2025-12-31", (("4210", "2900", 0), ("1200", 0, "2900"))),
		("ANLAGE", "2026-03-01", (("0420", "18000", 0), ("1200", 0, "18000"))),
		("MATERIAL-BAR", "2026-05-31", (("3400", "36000", 0), ("1200", 0, "36000"))),
		("ERLOES-BAR", "2026-06-30", (("1200", "112000", 0), ("8400", 0, "112000"))),
		("ERLOES-OFFEN", "2026-12-15", (("1400", "9520", 0), ("8400", 0, "8000"), ("1776", 0, "1520"))),
		("MATERIAL-OFFEN", "2026-12-20", (("3400", "4000", 0), ("1600", 0, "4000"))),
		("GEHALT", "2026-12-31", (("4120", "45000", 0), ("1200", 0, "45000"))),
		("MIETE", "2026-12-31", (("4210", "12000", 0), ("1200", 0, "12000"))),
		("GEWST", "2026-12-31", (("4320", "1800", 0), ("0956", 0, "1800"))),
	),
)
KLEIN = Company(
	"Steuerbote Test Jahresabschluss Klein GmbH",
	"STJL",
	"99902",
	(
		("KAPITAL", "2025-01-02", (("1200", "25000", 0), ("0800", 0, "25000"))),
		("DARLEHEN", "2025-01-02", (("1200", "500000", 0), ("0650", 0, "500000"))),
		("ERLOES-2025", "2025-06-30", (("1200", "1000000", 0), ("8400", 0, "1000000"))),
		("MATERIAL-2025", "2025-06-30", (("3400", "500000", 0), ("1200", 0, "500000"))),
		("GEHALT-2025", "2025-12-31", (("4120", "400000", 0), ("1200", 0, "400000"))),
		("ANLAGE", "2026-03-01", (("0420", "40000", 0), ("1200", 0, "40000"))),
		("MATERIAL-BAR", "2026-05-31", (("3400", "550000", 0), ("1200", 0, "550000"))),
		("ERLOES-BAR", "2026-06-30", (("1200", "1100000", 0), ("8400", 0, "1100000"))),
		("ERLOES-OFFEN", "2026-12-15", (("1400", "119000", 0), ("8400", 0, "100000"), ("1776", 0, "19000"))),
		("MATERIAL-OFFEN", "2026-12-20", (("3400", "50000", 0), ("1600", 0, "50000"))),
		("GEHALT", "2026-12-31", (("4120", "450000", 0), ("1200", 0, "450000"))),
		("MIETE", "2026-12-31", (("4210", "30000", 0), ("1200", 0, "30000"))),
		("GEWST", "2026-12-31", (("4320", "10000", 0), ("0956", 0, "10000"))),
		("TILGUNG", "2026-12-31", (("0650", "100000", 0), ("1200", 0, "100000"))),
	),
)
DIRECTOR = "Erika Beispiel"
DIRECTOR_ROLE = "Geschäftsführerin"
SEAT = "Musterstadt"
COURT = "Amtsgericht Musterstadt"
ADOPTED_ON = "2027-05-12"
"""The day the shareholders adopt the Jahresabschluss 2026, after the fiscal year; the tests that need it to lie in the
past run on a day after it (AFTER_ADOPTION)."""
AFTER_ADOPTION = "2027-05-20 10:00:00"


def settings_of(company: Company, accounts: dict[str, str]) -> dict:
	return {
		"doctype": SETTINGS,
		"company": company.name,
		"legal_form": "GmbH",
		"registered_seat": SEAT,
		"register_court": COURT,
		"register_type": "HRB",
		"register_number": company.register_number,
		"street": "Musterweg",
		"house_number": "1",
		"postal_code": "12345",
		"city": SEAT,
		"country": "Germany",
		"closing_account": accounts[CLOSING_ACCOUNT],
		"directors": [
			{"director_name": DIRECTOR, "role": DIRECTOR_ROLE, "from_date": "2025-01-01", "signs": 1},
		],
	}


def installed_taxonomy() -> AbstractContextManager:
	"""The HGB-Taxonomie 6.9 as Taxonomie einrichten installs it, as the site's own: a test class enters it before it
	makes a company."""
	return patch.object(eric_settings, "taxonomy_root", return_value=real.installation().path.parent)


def make_company_with_books(company: Company) -> dict[str, str]:
	"""The company with its accounts, Fiscal Years, ledger, Annual Filing Settings and Bilanzzuordnung, each made unless
	the site has it; returns the accounts by number."""
	make_company(company.name, company.abbr)
	accounts = {
		number: frappe.db.get_value("Account", {"company": company.name, "account_number": number})
		or make_account(company.name, number, name, root_type)
		for number, (name, root_type, *_place) in ACCOUNTS.items()
	}
	for year in (YEAR - 1, YEAR, YEAR + 1):
		ensure_fiscal_year(company.name, date(year, 6, 30))
	for voucher, posting_date, rows in company.ledger:
		voucher_no = f"JV-{company.abbr}-{voucher}"
		if not frappe.db.exists("GL Entry", {"voucher_type": JOURNAL_ENTRY, "voucher_no": voucher_no}):
			post_ledger(
				company.name,
				JOURNAL_ENTRY,
				voucher_no,
				posting_date,
				[(accounts[number], debit, credit) for number, debit, credit in rows],
			)
	if not frappe.db.exists(SETTINGS, company.name):
		frappe.get_doc(settings_of(company, accounts)).insert(ignore_permissions=True)
	if not frappe.db.exists(MAPPING, company.name):
		mapping = frappe.new_doc(MAPPING)
		mapping.update({"company": company.name, "chart": "SKR03", "taxonomy_version": "6.9"})
		for number, (_name, _root_type, concept, opposite, term) in ACCOUNTS.items():
			mapping.append(
				"rules",
				{
					"account": accounts[number],
					"concept": concept,
					"opposite_concept": opposite,
					"remaining_term": term,
				},
			)
		mapping.insert(ignore_permissions=True)
	return accounts


def employment_type_field() -> None:
	"""The Employment Type of the Employee, as HRMS adds it (hrms/setup.py), on a site without HRMS. It changes the
	table of the Employee, which commits; the field stays for every later test, which reads no other."""
	if not frappe.get_meta(EMPLOYEE).has_field("employment_type"):
		create_custom_field(
			EMPLOYEE,
			{
				"fieldname": "employment_type",
				"label": "Employment Type",
				"fieldtype": "Data",
				"insert_after": "status",
			},
		)


def employ(company: Company, number: int, joined: str, relieved: str | None = None, kind: str = "") -> str:
	"""An Employee of the company with the days of joining and leaving and the Employment Type."""
	return insert_record(
		EMPLOYEE,
		name=f"HR-EMP-{company.abbr}-{number:04d}",
		employee_name=f"Mitarbeiter {number}",
		first_name=f"Mitarbeiter {number}",
		company=company.name,
		status="Active" if relieved is None else "Left",
		date_of_joining=joined,
		relieving_date=relieved,
		employment_type=kind,
	)


def new_accounts(company: Company, **fields) -> Document:
	return frappe.get_doc({"doctype": DOCTYPE, "company": company.name, "year": YEAR, **fields}).insert()


def calculated(company: Company, **fields) -> Document:
	doc = new_accounts(company, **fields)
	doc.calculate()
	doc.reload()
	return doc


def answer(doc: Document, answers: dict[str, tuple[str, str, int | float]] | None = None) -> None:
	"""Answer every Angabe „nein“, the Arbeitnehmer „ja“, and those named as given; then save."""
	given = answers or {}
	for row in doc.notes:
		if row.code in given:
			row.answer, row.text, row.amount = given[row.code]
		elif row.code != "ARBEITNEHMER":
			row.answer = "nein"
	if any(row.code == "BEWERTUNGSMETHODEN" for row in doc.notes) and "BEWERTUNGSMETHODEN" not in given:
		(row,) = (row for row in doc.notes if row.code == "BEWERTUNGSMETHODEN")
		row.answer = "ja"
		row.text = "Die Vermögensgegenstände sind zu Anschaffungskosten bewertet, die Verbindlichkeiten zum Erfüllungsbetrag."
	doc.save()


def adopted(doc: Document, day: str = ADOPTED_ON) -> Document:
	"""Enter the day of the Feststellung and date each signature with it, then calculate again."""
	doc.adopted_on = day
	for row in doc.signatories:
		row.signed_on = day
	doc.save()
	doc.calculate()
	doc.reload()
	return doc


def ready_for_the_feststellung(company: Company, answers: dict | None = None, **fields) -> Document:
	doc = calculated(company, **fields)
	answer(doc, answers)
	doc.reload()
	return adopted(doc)


def discard(company: Company) -> None:
	"""Take the Annual Accounts of the company out with their files and the Journal Entries of their Ergebnisverwendung,
	and the day of the Feststellung out of its settings."""
	for name in frappe.get_all(DOCTYPE, filters={"company": company.name}, pluck="name"):
		frappe.db.set_value(DOCTYPE, name, "docstatus", 2, update_modified=False)
		frappe.delete_doc(DOCTYPE, name, force=True, ignore_permissions=True)
	for name in frappe.get_all(JOURNAL_ENTRY, filters={"company": company.name}, pluck="name"):
		frappe.db.delete("Journal Entry Account", {"parent": name})
		frappe.db.delete(JOURNAL_ENTRY, {"name": name})
	if frappe.db.exists(SETTINGS, company.name):
		record_adoption(company.name, YEAR, None)
	frappe.db.delete(EMPLOYEE, {"company": company.name})


def change_settings(test, company: Company, **values) -> None:
	"""Change the settings of the company for one test; its cleanup sets them back."""
	doc = frappe.get_doc(SETTINGS, company.name)
	kept = {
		key: [row.as_dict(no_default_fields=True) for row in value] if isinstance(value, list) else value
		for key, value in ((key, doc.get(key)) for key in values)
	}
	test.addCleanup(_set_settings, company.name, kept)
	_set_settings(company.name, values)


def _set_settings(name: str, values: dict) -> None:
	doc = frappe.get_doc(SETTINGS, name)
	doc.update(values)
	doc.save(ignore_permissions=True)


def codes(doc: Document) -> list[str]:
	return [row.code for row in doc.findings]


def blocking(doc: Document) -> list[str]:
	return [row.code for row in doc.findings if row.blocking]


def line(doc: Document, concept: str):
	(row,) = (row for row in doc.lines if row.concept == concept)
	return row
