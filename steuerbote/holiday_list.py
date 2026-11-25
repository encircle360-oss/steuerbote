"""The holidays of a company's deadlines, from its Holiday List.

A deadline of the Zusammenfassende Meldung or of the Dauerfristverlängerung that ends on a public holiday moves to
the next working day (§ 108 Absatz 3 AO). Public holidays differ by state, so Steuerbote takes them from the
Default Holiday List of the company (decision of the maintainer, docs/zm.md [Q16]), which is to hold those of the
state of its Finanzamt. ERPNext marks the weekly days off of a list ("Wöchentlich frei"), which
steuerbote.ustva.period.deadline_holidays leaves out. A company without a list gets the holidays of every state
(steuerbote.deadlines.holidays), which move a deadline wherever the authority sits, and has_list() tells the report,
the reminder and the setup to say so.
"""

from datetime import date

import frappe
from frappe.utils import getdate

from steuerbote.deadlines.holidays import nationwide
from steuerbote.ustva.period import deadline_holidays

# The years whose holidays of every state a company without a list gets, wide enough for every deadline Steuerbote
# computes.
NATIONWIDE_YEARS = range(2000, 2101)


def has_list(company: str) -> bool:
	"""Whether the company names a Default Holiday List."""
	return bool(frappe.db.get_value("Company", company, "default_holiday_list"))


def holidays(company: str) -> frozenset[date]:
	"""The days of the company's Holiday List on which no deadline ends; without a list those of every state."""
	holiday_list = frappe.db.get_value("Company", company, "default_holiday_list")
	if not holiday_list:
		return nationwide(NATIONWIDE_YEARS)
	rows = frappe.get_all(
		"Holiday",
		filters={"parent": holiday_list, "parenttype": "Holiday List"},
		fields=["holiday_date", "weekly_off"],
	)
	return deadline_holidays((getdate(row.holiday_date), row.weekly_off) for row in rows)
