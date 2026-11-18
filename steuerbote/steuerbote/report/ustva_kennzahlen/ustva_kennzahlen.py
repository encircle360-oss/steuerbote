"""UStVA Kennzahlen: the Kennzahlen of one Voranmeldungszeitraum and the vouchers behind each of them.

The report reads what "Berechnen" on a VAT Return reads: the general ledger of the period through
steuerbote.ledger, with the same exclusions, and the company's VAT Return Mapping and VAT Return Settings.
The core computes the Kennzahlen, attribution.py finds the vouchers behind them, and this module only
reads the data and looks up posting dates, account names and the parties of invoices.
"""

from collections.abc import Iterable
from datetime import date
from types import MappingProxyType
from typing import Any

import frappe
from frappe import _
from frappe.query_builder.functions import Min
from frappe.utils import cint

from steuerbote import ustva
from steuerbote.ledger import account_names, load_lines
from steuerbote.steuerbote.doctype.vat_return import bridge
from steuerbote.steuerbote.doctype.vat_return.vat_return import mapping_for, settings_for
from steuerbote.steuerbote.report.ustva_kennzahlen.attribution import (
	contributions,
	report_rows,
	vouchers_by_type,
)

FILTERS = ("company", "year", "rhythm", "period_index")

# The party of an invoice: the field that links it and the field with its name.
PARTY_FIELDS = MappingProxyType(
	{
		"Sales Invoice": ("customer", "customer_name"),
		"Purchase Invoice": ("supplier", "supplier_name"),
	}
)


def execute(filters: dict | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	filters = frappe._dict(filters or {})
	if any(filters.get(name) in (None, "") for name in FILTERS):
		return get_columns(), []
	company = filters.company
	frappe.has_permission("Company", "read", doc=company, throw=True)
	period = _period(filters)
	settings = settings_for(company)
	mapping = mapping_for(company, period.year)
	lines = load_lines(company, period.start, period.end)
	try:
		result = ustva.calculate(
			lines,
			mapping,
			extra_values=bridge.sondervorauszahlung_values(
				period,
				settings.has_dauerfrist(period.year),
				bridge.to_amount(settings.sondervorauszahlung(period.year)),
			),
		)
	except ValueError as error:
		frappe.throw(str(error))
	by_kennzahl = contributions(lines, mapping)
	numbers = {account for items in by_kennzahl.values() for item in items for account in item.accounts}
	rows = report_rows(
		result,
		mapping.catalogue,
		by_kennzahl,
		posting_dates=_posting_dates(company, period),
		account_names=account_names(company, numbers),
		parties=_parties(item.voucher for items in by_kennzahl.values() for item in items),
		print_label=_("Print"),
		currency=frappe.get_cached_value("Company", company, "default_currency"),
	)
	return get_columns(), rows


def get_columns() -> list[dict[str, Any]]:
	money = {"fieldtype": "Currency", "options": "currency", "width": 130}
	return [
		{"fieldname": "kennzahl", "label": _("Kennzahl"), "fieldtype": "Data", "width": 100},
		{"fieldname": "line", "label": _("Form Line"), "fieldtype": "Int", "width": 90},
		{"fieldname": "label", "label": _("Label"), "fieldtype": "Data", "width": 300},
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
		{"fieldname": "amount", "label": _("Ledger Amount"), **money},
		{"fieldname": "reported", "label": _("Form Amount"), **money},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
	]


def _period(filters: frappe._dict) -> ustva.Period:
	year = cint(filters.year)
	try:
		ustva.catalogue_for(year)
	except ustva.UnknownYearError:
		frappe.throw(_("Steuerbote has no Kennzahlen for {0} yet.").format(year))
	try:
		return ustva.Period(year, ustva.Rhythm(filters.rhythm), cint(filters.period_index))
	except ValueError:
		frappe.throw(
			_(
				"Filing {0}, there is no Voranmeldungszeitraum {1}: months run from 1 to 12, quarters from 1 to 4."
			).format(_(filters.rhythm), filters.period_index)
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


def _posting_dates(company: str, period: ustva.Period) -> dict[str, date]:
	"""The posting date of each voucher of the period, by the voucher key of steuerbote.ledger."""
	gl_entry = frappe.qb.DocType("GL Entry")
	vouchers = (
		frappe.qb.from_(gl_entry)
		.select(gl_entry.voucher_type, gl_entry.voucher_no, Min(gl_entry.posting_date).as_("posting_date"))
		.where(gl_entry.company == company)
		.where(gl_entry.posting_date.between(period.start, period.end))
		.where(gl_entry.is_cancelled == 0)
		.groupby(gl_entry.voucher_type, gl_entry.voucher_no)
		.run(as_dict=True)
	)
	return {f"{voucher.voucher_type}:{voucher.voucher_no}": voucher.posting_date for voucher in vouchers}
