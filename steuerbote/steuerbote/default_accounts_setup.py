"""The step „Standardkonten des Unternehmens“ of Steuerbote einrichten (hook steuerbote_setup_steps).

ERPNext books a cash discount of a payment onto the Default Payment Discount Account of the company
(default_discount_account), a write-off onto its Write Off Account (write_off_account) and the cents of a rounding onto
its Round Off Account (round_off_account). An account there that a return watches without a place holds that return on
every such booking: Gewährte Skonti or Forderungsverluste without a rate hold the Umsatzsteuer-Voranmeldung, since they
name no Kennzahl, and an account the defaults of the chart do not know at all holds the E-Bilanz and the
Körperschaftsteuererklärung. The step names each such account and what to choose instead; it changes nothing.
"""

import frappe
from frappe import _

from steuerbote.setup.steps import Note, Outcome, StepResult

FIELDS = ("default_discount_account", "write_off_account", "round_off_account")
DISCOUNT = "Default Payment Discount Account"
WRITE_OFF = "Write Off Account"
ROUND_OFF = "Round Off Account"
LABELS = dict(zip(FIELDS, (DISCOUNT, WRITE_OFF, ROUND_OFF), strict=True))

HOLDS_VAT = "The {0} of {1} is account {2}, which names no rate: every amount ERPNext books there holds the Umsatzsteuer-Voranmeldung until the account has a row in the VAT Return Mapping. Choose an account of its kind with the rate instead ({3}), or give the account a row with its Kennzahl if every amount on it belongs to one rate."
UNKNOWN = "The {0} of {1} is account {2}, which the defaults of {3} do not know: every amount ERPNext books there holds the E-Bilanz and the Körperschaftsteuererklärung until the account has its rows in the Balance Sheet Mapping and the Income Tax Mapping. Choose an account of the chart, or add the rows."
FINE = "The default accounts of {0} for cash discounts, write-offs and roundings hold no return."
MESSAGES = (HOLDS_VAT, UNKNOWN, FINE, DISCOUNT, WRITE_OFF, ROUND_OFF)


def check(context) -> StepResult:
	"""The step company_default_accounts: a note per default account that would hold a return, else done."""
	company = context.company
	chart = context.chart.chart
	document = ("Company", company)
	if chart not in ("SKR03", "SKR04"):
		return StepResult(Outcome.SKIPPED, (), document)
	from steuerbote.ebilanz.defaults import defaults_for
	from steuerbote.ustva.defaults import RATE_ACCOUNTS

	chosen = frappe.db.get_value("Company", company, list(FIELDS), as_dict=True)
	numbers = {
		field: frappe.db.get_value("Account", chosen[field], "account_number")
		for field in FIELDS
		if chosen.get(field)
	}
	blocking = blocking_accounts(company, chart, context.today.year)
	known = defaults_for(chart, "6.9")
	spans = [entry.accounts for entry in (*known.rules, *known.watched, *known.excluded)]
	notes = []
	for field, number in numbers.items():
		if not number:
			continue
		label = _(LABELS[field])
		if number in blocking:
			rates = RATE_ACCOUNTS[chart].get(number, ())
			listed = ", ".join(f"{rate.number} ({rate.rate})" for rate in rates)
			notes.append(Note(HOLDS_VAT, (label, company, number, listed), open=True))
		elif not any(number in accounts for accounts in spans):
			notes.append(Note(UNKNOWN, (label, company, number, chart), open=True))
	if notes:
		return StepResult(Outcome.UNDECIDED, tuple(notes), document)
	return StepResult(Outcome.SKIPPED, (Note(FINE, (company,)),), document)


def blocking_accounts(company: str, chart: str, year: int) -> set[str]:
	"""The accounts the Voranmeldung of the company watches at the blocking level: those of its VAT Return Mapping, or
	those of the defaults of its chart while it has none or one the year rejects."""
	from steuerbote.ustva import defaults as vat_defaults
	from steuerbote.ustva.mapping import WatchLevel

	if frappe.db.exists("VAT Return Mapping", company):
		try:
			mapping = frappe.get_doc("VAT Return Mapping", company).to_mapping(year)
		except frappe.ValidationError:
			mapping = vat_defaults.default_mapping(chart, year)
	else:
		mapping = vat_defaults.default_mapping(chart, year)
	return set(mapping.watched_at(WatchLevel.BLOCKING))
