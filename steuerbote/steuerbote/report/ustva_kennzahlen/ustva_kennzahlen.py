"""UStVA Kennzahlen: the Kennzahlen of one Voranmeldungszeitraum, the vouchers behind each of them, and the
amounts of the previous period and of the same period one year earlier.

The report reads what "Berechnen" on a VAT Return reads: the general ledger of the period through
steuerbote.vat_periods, with the same exclusions and the same assignment to the Voranmeldungszeitraum, and the
company's VAT Return Mapping and VAT Return Settings.
The core computes the Kennzahlen, attribution.py finds the vouchers behind them, and comparison.py sets them
beside the previous period of the same rhythm and the same period one year earlier, which this module
computes the same way from the ledger, with the mapping on the form of their year. Otherwise the module only
reads the data and looks up posting dates, account names, the parties of invoices and which vouchers are
cancelled.
"""

from collections.abc import Iterable
from types import MappingProxyType
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, escape_html, formatdate

from steuerbote import prior_filings, ustva
from steuerbote.ledger import account_labels, account_names
from steuerbote.setup.start import before_start
from steuerbote.steuerbote.doctype.vat_return import bridge
from steuerbote.steuerbote.doctype.vat_return.vat_return import (
	mapping_for,
	released,
	settings_for,
	statutory_tax_of,
)
from steuerbote.steuerbote.report.ustva_kennzahlen import comparison
from steuerbote.steuerbote.report.ustva_kennzahlen.attribution import (
	contributions,
	report_rows,
	vouchers_by_type,
)
from steuerbote.suppliers import load_vouchers
from steuerbote.vat_periods import VatLedger

FILTERS = ("company", "year", "rhythm", "period_index")
# Optional: only the Kennzahlen and sums that deviate from the previous period.
ONLY_DEVIATIONS = "only_deviations"

# The party of an invoice: the field that links it and the field with its name.
PARTY_FIELDS = MappingProxyType(
	{
		"Sales Invoice": ("customer", "customer_name"),
		"Purchase Invoice": ("supplier", "supplier_name"),
	}
)


def execute(filters: dict | None = None) -> tuple:
	"""The columns and rows of the report; for a year or period it cannot show, no rows and the reason as the message of
	the report, which leaves the grid ready for other filters."""
	filters = frappe._dict(filters or {})
	if any(filters.get(name) in (None, "") for name in FILTERS):
		return get_columns(), []
	company = filters.company
	frappe.has_permission("Company", "read", doc=company, throw=True)
	period, reason = _period(filters)
	if period is None:
		return get_columns(), [], reason
	settings = settings_for(company)
	mapping = mapping_for(company, period.year)
	ledger = VatLedger.for_period(company, period)
	lines = ledger.lines(period)
	result, released_hints = released(
		company, _calculate(lines, mapping, period, settings), lines, mapping, period
	)
	previous, previous_note = _compared(ledger, period.previous(), mapping, settings)
	previous_year, previous_year_note = _compared(ledger, comparison.year_before(period), mapping, settings)
	by_kennzahl = contributions(lines, mapping, load_vouchers(company, lines, mapping))
	numbers = {account for items in by_kennzahl.values() for item in items for account in item.accounts}
	vouchers = [item.voucher for items in by_kennzahl.values() for item in items]
	rows = report_rows(
		result,
		mapping.catalogue,
		by_kennzahl,
		posting_dates=ledger.posting_dates(period),
		account_names=account_names(company, numbers),
		parties=_parties(vouchers),
		print_label=_("Print"),
		cancelled_label=_("Cancelled voucher"),
		currency=frappe.get_cached_value("Company", company, "default_currency"),
		cancelled=_cancelled(vouchers),
		shown=comparison.compared_kennzahlen(previous, previous_year),
	)
	rows = comparison.compared_rows(rows, previous, previous_year)
	if cint(filters.get(ONLY_DEVIATIONS)):
		rows = comparison.only_deviations(rows, _thresholds(settings))
	notes = [comparison.note_row(note) for note in (previous_note, previous_year_note) if note]
	blocked = comparison.blocked_notes(result.unmapped, account_labels(company, result.unmapped))
	notes += [comparison.note_row(text) for text in (*blocked, *(hint.text for hint in released_hints))]
	return get_columns(), notes + rows


def get_columns() -> list[dict[str, Any]]:
	"""The amounts come right after the Kennzahl, so that a narrow window shows them without scrolling; the vouchers
	behind a Kennzahl follow."""
	money = {"fieldtype": "Currency", "options": "currency", "width": 130}
	return [
		{"fieldname": "kennzahl", "label": _("Kennzahl"), "fieldtype": "Data", "width": 100},
		{"fieldname": "line", "label": _("Form Line"), "fieldtype": "Int", "width": 90},
		{"fieldname": "label", "label": _("Label"), "fieldtype": "Data", "width": 300},
		{"fieldname": "reported", "label": _("Form Amount"), **money},
		{"fieldname": "amount", "label": _("Ledger Amount"), **money},
		{"fieldname": "previous_period", "label": _("Previous Period"), **money},
		{"fieldname": "previous_year", "label": _("Previous Year"), **money},
		{"fieldname": "difference", "label": _("Difference to Previous Period"), **money, "width": 170},
		{"fieldname": "posting_date", "label": _("Posting Date"), "fieldtype": "Date", "width": 110},
		{
			"fieldname": "voucher_type",
			"label": _("Voucher Type"),
			"fieldtype": "Link",
			"options": "DocType",
			"width": 130,
		},
		{
			"fieldname": "voucher_no",
			"label": _("Voucher No"),
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 170,
		},
		{"fieldname": "print_link", "label": _("Print"), "fieldtype": "Data", "width": 90},
		{"fieldname": "party", "label": _("Party"), "fieldtype": "Data", "width": 180},
		{
			"fieldname": "account",
			"label": _("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"width": 220,
		},
		{"fieldname": "debit", "label": _("Debit"), **money},
		{"fieldname": "credit", "label": _("Credit"), **money},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
	]


def _period(filters: frappe._dict) -> tuple[ustva.Period | None, str | None]:
	"""The period of the filters, or None and why the report cannot show it."""
	year = cint(filters.year)
	try:
		ustva.catalogue_for(year)
	except ustva.UnknownYearError:
		return None, _("Steuerbote has no Kennzahlen for {0} yet.").format(year)
	try:
		return ustva.Period(year, ustva.Rhythm(filters.rhythm), cint(filters.period_index)), None
	except ValueError:
		return None, _(
			"Filing {0}, there is no Voranmeldungszeitraum {1}: months run from 1 to 12, quarters from 1 to 4."
		).format(_(filters.rhythm), escape_html(str(filters.period_index)))


def _calculate(
	lines: list[ustva.LedgerLine], mapping: ustva.Mapping, period: ustva.Period, settings: Document
) -> ustva.UstvaResult:
	"""What "Berechnen" computes for the period, Kz 39 included in the last period of the year, with the tax of the
	bases at a statutory rate as the settings choose it, so lines 37, 45 and 48 are those of the return."""
	try:
		return ustva.calculate(
			lines,
			mapping,
			extra_values=bridge.sondervorauszahlung_values(
				period,
				settings.has_dauerfrist(period.year),
				bridge.to_amount(settings.sondervorauszahlung(period.year)),
			),
			vouchers=load_vouchers(settings.company, lines, mapping),
			statutory_tax=statutory_tax_of(settings),
		)
	except ValueError as error:
		frappe.throw(str(error))


def _compared(
	ledger: VatLedger, period: ustva.Period, mapping: ustva.Mapping, settings: Document
) -> tuple[ustva.UstvaResult | None, str | None]:
	"""What a period to compare with reported, computed from its ledger with the company's mapping on the form
	of its own year, or why the report cannot compare with it."""
	books_start = prior_filings.books_start(ledger.company)
	if before_start(period.start, books_start):
		return None, _(
			"No comparison with {0}: it lies before the start of the books in Steuerbote on {1}."
		).format(period.label, formatdate(books_start))
	try:
		year_mapping = mapping.for_year(period.year)
	except ustva.UnknownYearError:
		return None, _("No comparison with {0}: Steuerbote has no Kennzahlen for {1} yet.").format(
			period.label, period.year
		)
	except ustva.MappingError as error:
		return None, _(
			"No comparison with {0}: the VAT Return Mapping does not fit the form of {1} ({2})."
		).format(period.label, period.year, str(error))
	return _calculate(ledger.lines(period), year_mapping, period, settings), None


def _thresholds(settings: Document) -> comparison.Thresholds:
	"""The thresholds of the company's VAT Return Settings, or the defaults where the settings have none."""
	return comparison.Thresholds.of(
		settings.get("comparison_threshold_percent"), settings.get("comparison_threshold_amount")
	)


def _parties(vouchers: Iterable[str | None]) -> dict[str, str]:
	"""The customer or supplier of each invoice among the vouchers, by voucher key, one query per type."""
	parties = {}
	for voucher_type, names in vouchers_by_type(vouchers, PARTY_FIELDS).items():
		party, party_name = PARTY_FIELDS[voucher_type]
		invoices = frappe.get_all(
			voucher_type, filters={"name": ["in", names]}, fields=["name", party, party_name]
		)
		for invoice in invoices:
			parties[f"{voucher_type}:{invoice.name}"] = invoice[party_name] or invoice[party]
	return parties


def _cancelled(vouchers: Iterable[str | None]) -> set[str]:
	"""The keys of the cancelled vouchers among the vouchers, one query per voucher type.

	The ledger lists cancelled vouchers when the Accounts Settings enable the immutable ledger: ERPNext then
	keeps the GL Entries of a cancelled voucher and posts their reversal on the day of the cancellation.
	"""
	return {
		f"{voucher_type}:{name}"
		for voucher_type, names in vouchers_by_type(vouchers).items()
		for name in frappe.get_all(
			voucher_type, filters={"name": ["in", names], "docstatus": 2}, pluck="name"
		)
	}
