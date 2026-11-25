"""What Steuerbote reads of a company that started with it in the middle of its life (steuerbote/setup/start.py): the
first day of its books in ERPNext, from its VAT Return Settings, and its Voranmeldungen filed before Steuerbote, the
submitted VAT Return Prior Filings, the latest made first."""

from collections.abc import Iterable
from datetime import date

import frappe
from frappe.utils import cint, getdate

from steuerbote.setup.start import PriorFiling, before_start
from steuerbote.steuerbote.doctype.vat_return.bridge import to_amount
from steuerbote.ustva import Period, Rhythm

DOCTYPE = "VAT Return Prior Filing"
SETTINGS = "VAT Return Settings"
FIELDS = ("name", "year", "rhythm", "period_index", "filed_on", "kz83", "kz39", "kz41", "kz42", "kz21")


def books_start(company: str) -> date | None:
	"""The first day of the books of the company in ERPNext, None where its settings name none."""
	value = frappe.db.get_value(SETTINGS, company, "books_start")
	return getdate(value) if value else None


def lies_before_start(company: str, period_start: date) -> bool:
	"""Whether a period beginning on the day lies before the start of the books of the company."""
	return before_start(period_start, books_start(company))


def prior_filings(company: str, years: Iterable[int] | None = None) -> list[PriorFiling]:
	"""The submitted Voranmeldungen of the company filed before Steuerbote, of the years given or of all, the latest
	made first."""
	filters: dict = {"company": company, "docstatus": 1}
	if years is not None:
		filters["year"] = ["in", [int(year) for year in years]]
	return [
		of_record(row)
		for row in frappe.get_all(DOCTYPE, filters=filters, fields=FIELDS, order_by="creation desc")
	]


def of_record(row) -> PriorFiling:
	"""The filing a record holds."""
	return PriorFiling(
		Period(cint(row.year), Rhythm(row.rhythm), cint(row.period_index)),
		row.name,
		getdate(row.filed_on),
		to_amount(row.kz83),
		to_amount(row.kz39),
		to_amount(row.kz41),
		to_amount(row.kz42),
		to_amount(row.kz21),
	)
