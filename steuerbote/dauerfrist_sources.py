"""What the Dauerfristverlängerung reads from ERPNext: the VAT Returns filed for a year, with the Voranmeldungen filed
before Steuerbote for the periods no VAT Return covers (steuerbote/prior_filings.py), and the day the company began. The holidays of its deadlines come from steuerbote.holiday_list, as those of the Zusammenfassende Meldung.

A VAT Return counts as filed once it is submitted with the status Abgegeben. A corrected return (Kz 10) sets
the returns of its period before it to Ersetzt, so they drop out, and the latest filing of each period counts.
Kz 83 and Kz 39 are the amounts the return keeps as filed: Kz 83 is the one its file for Mein ELSTER writes,
and Kz 39 the Sondervorauszahlung it deducted.
"""

from datetime import date

import frappe
from frappe.utils import cint, getdate

from steuerbote.prior_filings import prior_filings
from steuerbote.steuerbote.doctype.vat_return.bridge import to_amount
from steuerbote.steuerbote.doctype.vat_return.vat_return import DOCTYPE as VAT_RETURN
from steuerbote.steuerbote.doctype.vat_return.vat_return import FILED
from steuerbote.steuerbote.doctype.vat_return_extension.bridge import FiledReturn, with_prior
from steuerbote.ustva import Period, Rhythm


def filed_returns(company: str, year: int) -> tuple[FiledReturn, ...]:
	"""The latest filed VAT Return of each Voranmeldungszeitraum of the company in ``year``, and the latest
	Voranmeldung filed before Steuerbote of each period no VAT Return covers."""
	rows = frappe.get_all(
		VAT_RETURN,
		filters={"company": company, "year": year, "docstatus": 1, "status": FILED},
		fields=["name", "rhythm", "period_index", "kz83", "sondervorauszahlung"],
		order_by="creation desc",
	)
	return with_prior(
		(
			FiledReturn(
				Period(year, Rhythm(row.rhythm), cint(row.period_index)),
				row.name,
				to_amount(row.kz83),
				to_amount(row.sondervorauszahlung),
			)
			for row in rows
		),
		prior_filings(company, {year}),
	)


def date_of_establishment(company: str) -> date | None:
	"""The day the company began, as its Date of Establishment says, if it says."""
	began = frappe.db.get_value("Company", company, "date_of_establishment")
	return getdate(began) if began else None
