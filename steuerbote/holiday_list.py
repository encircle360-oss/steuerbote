"""The holidays of a company's deadlines, from its Holiday List.

A deadline of the Zusammenfassende Meldung or of the Dauerfristverlängerung that ends on a public holiday moves to
the next working day (§ 108 Absatz 3 AO). Public holidays differ by state, so Steuerbote takes them from the
Default Holiday List of the company (decision of the maintainer, docs/zm.md [Q16]). ERPNext marks the weekly days
off of a list ("Wöchentlich frei"), which steuerbote.ustva.period.deadline_holidays leaves out.
"""

from datetime import date

import frappe
from frappe.utils import getdate

from steuerbote.ustva.period import deadline_holidays


def holidays(company: str) -> frozenset[date]:
	"""The days of the company's Holiday List on which no deadline ends."""
	holiday_list = frappe.db.get_value("Company", company, "default_holiday_list")
	if not holiday_list:
		return frozenset()
	rows = frappe.get_all(
		"Holiday",
		filters={"parent": holiday_list, "parenttype": "Holiday List"},
		fields=["holiday_date", "weekly_off"],
	)
	return deadline_holidays((getdate(row.holiday_date), row.weekly_off) for row in rows)
