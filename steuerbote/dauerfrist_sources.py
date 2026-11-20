"""What the Dauerfristverlängerung reads from ERPNext: the VAT Returns filed for a year, the day the company
began and the holidays of its Holiday List.

A VAT Return counts as filed once it is submitted with the status Abgegeben. A corrected return (Kz 10) sets
the returns of its period before it to Ersetzt, so they drop out, and the latest filing of each period counts.
Kz 83 and Kz 39 are the amounts the return keeps as filed: Kz 83 is the one its file for Mein ELSTER writes,
and Kz 39 the Sondervorauszahlung it deducted.
"""

from datetime import date

import frappe
from frappe.utils import cint, getdate

from steuerbote.steuerbote.doctype.vat_return.bridge import to_amount
from steuerbote.steuerbote.doctype.vat_return.vat_return import DOCTYPE as VAT_RETURN
from steuerbote.steuerbote.doctype.vat_return.vat_return import FILED
from steuerbote.steuerbote.doctype.vat_return_extension.bridge import FiledReturn, latest_per_period
from steuerbote.ustva import Period, Rhythm


def filed_returns(company: str, year: int) -> tuple[FiledReturn, ...]:
	"""The latest filed VAT Return of each Voranmeldungszeitraum of the company in ``year``."""
	rows = frappe.get_all(
		VAT_RETURN,
		filters={"company": company, "year": year, "docstatus": 1, "status": FILED},
		fields=["name", "rhythm", "period_index", "kz83", "sondervorauszahlung"],
		order_by="creation desc",
	)
	return latest_per_period(
		FiledReturn(
			Period(year, Rhythm(row.rhythm), cint(row.period_index)),
			row.name,
			to_amount(row.kz83),
			to_amount(row.sondervorauszahlung),
		)
		for row in rows
	)


def date_of_establishment(company: str) -> date | None:
	"""The day the company began, as its Date of Establishment says, if it says."""
	began = frappe.db.get_value("Company", company, "date_of_establishment")
	return getdate(began) if began else None


def holidays(company: str) -> frozenset[date]:
	"""The days of the company's Holiday List that move a deadline on them to the next working day.

	§ 108 Absatz 3 AO moves a deadline off a Sunday, a public holiday or a Saturday. The core handles the
	weekend, so the weekly days off of the list are left out: a list may give the company another weekday off,
	which moves no deadline.
	"""
	holiday_list = frappe.db.get_value("Company", company, "default_holiday_list")
	if not holiday_list:
		return frozenset()
	holiday = frappe.qb.DocType("Holiday")
	days = (
		frappe.qb.from_(holiday)
		.select(holiday.holiday_date)
		.where(holiday.parenttype == "Holiday List")
		.where(holiday.parent == holiday_list)
		.where(holiday.weekly_off == 0)
		.run(pluck=True)
	)
	return frozenset(getdate(day) for day in days)
