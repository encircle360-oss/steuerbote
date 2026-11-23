"""What the Umsatzsteuererklärung reads from ERPNext for its core in steuerbote/ustjahr.

- The ledger of the calendar year, the Besteuerungszeitraum (§ 16 Absatz 1 Satz 2 UStG), and that of each
  Voranmeldungszeitraum of it, through steuerbote/ledger.py as the Voranmeldung reads it, and the run of the
  Voranmeldung on each period with the VAT Return Mapping of the year (period_runs): the reconciliation sets the
  return against them.
- The line of the annual return of each account: the VAT Return Mapping of the company, to_split(year).
- The filed Voranmeldungen of the year (filed_voranmeldungen): a VAT Return counts once it is submitted with the
  status Abgegeben, and a corrected return (Kz 10) sets the returns of its period before it to Ersetzt, so the latest
  filing of each period counts, as for the Dauerfristverlängerung (steuerbote/dauerfrist_sources.py). Each comes with
  its Kz 83 and Kz 39 as filed and every Kennzahl of its table Kennzahlen.
- The Sondervorauszahlung of the year from the VAT Return Settings, which the last Voranmeldung of a year with
  Dauerfristverlängerung deducts in Kz 39 (§ 48 Absatz 4 UStDV); without Dauerfristverlängerung there is none.
- The postings on the accounts of the payments to the Finanzamt (payment_lines), all of them, also the Journal
  Entries that the Voranmeldung leaves out, since a payment is one whatever the flag says.
- The day of the switch to the Regelbesteuerung, Kz 70 of the filed Voranmeldungen, for Kz 136 of the return.
- What section A of the form says of the company (company), and the Steuerberatung of a year it takes part in
  (advisor), from the Company, the VAT Return Settings and the Annual Filing Settings.
"""

from collections.abc import Collection, Iterable
from datetime import date
from decimal import Decimal

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import cint, getdate

from steuerbote.jahresmeldung.overrides import to_amount
from steuerbote.ledger import load_lines
from steuerbote.steuerbote.doctype.annual_filing_settings.annual_filing_settings import settings_of
from steuerbote.steuerbote.doctype.annual_vat_return import bridge
from steuerbote.steuerbote.doctype.vat_return.vat_return import DOCTYPE as VAT_RETURN
from steuerbote.steuerbote.doctype.vat_return.vat_return import FILED
from steuerbote.ustjahr.soll import Filed
from steuerbote.ustjahr.split import Split
from steuerbote.ustva import LedgerLine, Mapping, Period, Rhythm, UstvaResult, calculate
from steuerbote.ustva.rounding import ZERO

MAPPING_DOCTYPE = "VAT Return Mapping"
SETTINGS_DOCTYPE = "VAT Return Settings"
KENNZAHL_DOCTYPE = "VAT Return Kennzahl"
DECEMBER = 12
LAST_OF_DECEMBER = 31


def year_lines(company: str, year: int) -> list[LedgerLine]:
	"""The ledger lines of the calendar year."""
	return load_lines(company, date(year, 1, 1), date(year, DECEMBER, LAST_OF_DECEMBER))


def annual_split(company: str, year: int) -> Split:
	"""The line of the annual return of each account of the VAT Return Mapping of the company."""
	if not frappe.db.exists(MAPPING_DOCTYPE, company):
		frappe.throw(
			_(
				"{0} has no VAT Return Mapping. Create one for the company, for example from the defaults of its chart, before calculating a VAT Return."
			).format(company)
		)
	return frappe.get_doc(MAPPING_DOCTYPE, company).to_split(year)


def period_runs(
	company: str, periods: Iterable[Period], mapping: Mapping, tolerance: Decimal
) -> dict[Period, UstvaResult]:
	"""The run of the Voranmeldung on today's ledger of each period, as Berechnen of a VAT Return runs it without the
	Sondervorauszahlung, which the reconciliation takes from Kz 39 of the filed return."""
	return {
		period: calculate(load_lines(company, period.start, period.end), mapping, tolerance=tolerance)
		for period in periods
	}


def filed_voranmeldungen(company: str, year: int) -> tuple[Filed, ...]:
	"""The latest filed VAT Return of each Voranmeldungszeitraum of the company in ``year``."""
	returns = frappe.get_all(
		VAT_RETURN,
		filters={"company": company, "year": year, "docstatus": 1, "status": FILED},
		fields=["name", "rhythm", "period_index", "kz83", "sondervorauszahlung"],
		order_by="creation desc",
	)
	if not returns:
		return ()
	rows = frappe.get_all(
		KENNZAHL_DOCTYPE,
		filters={"parenttype": VAT_RETURN, "parent": ["in", [entry.name for entry in returns]]},
		fields=["parent", "kennzahl", "amount", "reported", "final"],
	)
	kennzahlen: dict[str, list] = {}
	for row in rows:
		kennzahlen.setdefault(row.parent, []).append(row)
	return bridge.latest_per_period(
		Filed(
			Period(year, Rhythm(entry.rhythm), cint(entry.period_index)),
			entry.name,
			to_amount(entry.kz83),
			to_amount(entry.sondervorauszahlung),
			bridge.filed_kennzahlen(kennzahlen.get(entry.name, ())),
		)
		for entry in returns
	)


def switch_to_regelbesteuerung(company: str, year: int) -> date | None:
	"""The day of the switch from the Kleinunternehmer-Regelung that a filed Voranmeldung of the year names in Kz 70,
	the earliest if several do."""
	days = frappe.get_all(
		VAT_RETURN,
		filters={
			"company": company,
			"year": year,
			"docstatus": 1,
			"status": FILED,
			"regelbesteuerung_from": ["is", "set"],
		},
		pluck="regelbesteuerung_from",
	)
	return min((getdate(day) for day in days), default=None)


def sondervorauszahlung(settings, year: int) -> Decimal:
	"""The Sondervorauszahlung of the year in the VAT Return Settings, in a year with Dauerfristverlängerung."""
	return to_amount(settings.sondervorauszahlung(year)) if settings.has_dauerfrist(year) else ZERO


def payment_lines(company: str, year: int, accounts: Collection[str]) -> list[LedgerLine]:
	"""The postings of the year on the accounts of the payments to the Finanzamt, per voucher and account, without
	cancelled entries, opening entries and Period Closing Vouchers."""
	if not accounts:
		return []
	gl_entry = frappe.qb.DocType("GL Entry")
	account = frappe.qb.DocType("Account")
	rows = (
		frappe.qb.from_(gl_entry)
		.inner_join(account)
		.on(account.name == gl_entry.account)
		.select(
			account.account_number,
			gl_entry.voucher_type,
			gl_entry.voucher_no,
			Sum(gl_entry.debit).as_("debit"),
			Sum(gl_entry.credit).as_("credit"),
		)
		.where(gl_entry.company == company)
		.where(gl_entry.posting_date.between(date(year, 1, 1), date(year, DECEMBER, LAST_OF_DECEMBER)))
		.where(gl_entry.is_cancelled == 0)
		.where(gl_entry.is_opening == "No")
		.where(gl_entry.voucher_type != "Period Closing Voucher")
		.where(account.account_number.isin(list(accounts)))
		.groupby(account.account_number, gl_entry.voucher_type, gl_entry.voucher_no)
		.run(as_dict=True)
	)
	return [
		LedgerLine(
			account_number=row.account_number.strip(),
			debit=to_amount(row.debit),
			credit=to_amount(row.credit),
			voucher=f"{row.voucher_type}:{row.voucher_no}",
		)
		for row in rows
	]


def company(name: str) -> bridge.Company:
	"""Section A of the form: the name of the company, the W-IdNr., phone and email of the VAT Return Settings, and
	the Art des Unternehmens and the address of the Annual Filing Settings, where the company has them."""
	settings = settings_of(name)
	contact = (
		frappe.db.get_value(SETTINGS_DOCTYPE, name, ["wid_nr", "phone", "email"], as_dict=True)
		or frappe._dict()
	)
	return bridge.Company(
		name=frappe.db.get_value("Company", name, "company_name") or name,
		wid_nr=contact.wid_nr,
		business_purpose=settings.business_purpose if settings else None,
		address=settings.get_address() if settings else None,
		phone=contact.phone,
		email=contact.email,
	)


def advisor(name: str, year: int) -> bridge.Advisor | None:
	"""The Steuerberatung of the Annual Filing Settings, in a year they mark as prepared with its Mitwirkung (§ 149
	Absatz 3 AO); None in any other year."""
	settings = settings_of(name)
	year_settings = settings.year_settings(year) if settings else None
	if year_settings is None or not year_settings.advisor_prepares:
		return None
	return bridge.Advisor(
		name=settings.advisor_name,
		first_name=settings.advisor_first_name,
		street=settings.advisor_street,
		town=settings.advisor_town,
		phone=settings.advisor_phone,
		details=settings.advisor_details,
		client_number=settings.advisor_client_number,
		clerk=settings.advisor_clerk,
	)
