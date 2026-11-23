"""What the Zusammenfassende Meldung reads from ERPNext: the ledger of Kz 41, 42 and 21, the customers of the
vouchers, the filed Voranmeldungen and the customers' names and addresses for the confirmation. The Voranmeldung
reads the vouchers and customers of its period the same way for the confirmation of their USt-IdNrn.

The lines come from the ledger, voucher by voucher (decision of the maintainer, docs/zm.md): steuerbote.ledger
reads the GL Entries with the exclusions of the Voranmeldung, only on the accounts that the VAT Return Mapping
gives Kz 41, 42 or 21, and attribution.contributions() splits them by voucher with the rules of calculate(). The
Lieferungen (Kz 41 and 42) come from the goods months of the Meldezeitraum and the sonstige Leistungen (Kz 21)
from its services months (steuerbote.zm.rhythm.Coverage), each by posting date (decision of the maintainer).

ERPNext knows the customer of a voucher in three ways, and reads each with one query per kind of voucher:

- a Sales Invoice names its customer and keeps the customer's tax_id, read-only, as it was when the invoice was
  made; its shipping address, or else its billing address, gives the country where the goods arrive;
- a Payment Entry, such as one with a Skonto, names its customer, and the Sales Invoices it pays give the
  USt-IdNr. and the country, the first of them that has one; without it, the customer's tax_id counts;
- a Journal Entry names a customer in its accounts, and counts only when it names a single one; the Sales
  Invoices its rows refer to give the USt-IdNr. and the country, as for a Payment Entry, so that a credit note
  entered as a Journal Entry counts under the number of the invoice it reduces; without one, the customer's tax_id
  counts.

ERPNext has no field for a Dreiecksgeschäft: it is a voucher on an account of Kz 42 in the mapping. Other
vouchers name no customer, and the ZM says so of each of them.
"""

from collections.abc import Collection, Iterable, Iterator
from datetime import date
from decimal import Decimal

import frappe

from steuerbote.ledger import load_lines
from steuerbote.steuerbote.doctype.recapitulative_statement.bridge import FiledReturn, Party
from steuerbote.steuerbote.doctype.vat_return.bridge import to_amount
from steuerbote.steuerbote.report.ustva_kennzahlen.attribution import (
	Contribution,
	contributions,
	vouchers_by_type,
)
from steuerbote.ustva import Mapping
from steuerbote.ustva.rounding import ZERO
from steuerbote.vatid.result import Details
from steuerbote.zm.lines import ART_KENNZAHL, Art
from steuerbote.zm.period import ReportingPeriod
from steuerbote.zm.rhythm import Coverage

GOODS = (ART_KENNZAHL[Art.L], ART_KENNZAHL[Art.D])
SERVICES = (ART_KENNZAHL[Art.S],)
CUSTOMER = "Customer"
SALES_INVOICE = "Sales Invoice"
PAYMENT_ENTRY = "Payment Entry"
JOURNAL_ENTRY = "Journal Entry"
FILED = "Abgegeben"
ADDRESS_FIELDS = ("name", "address_line1", "pincode", "city")


def shares(company: str, coverage: Coverage, mapping: Mapping) -> list[Contribution]:
	"""What each voucher adds to Kz 41 and 42 in the goods months and to Kz 21 in the services months."""
	return [*goods_shares(company, coverage, mapping), *services_shares(company, coverage, mapping)]


def goods_shares(company: str, coverage: Coverage, mapping: Mapping) -> list[Contribution]:
	"""What each voucher adds to Kz 41 and 42 in the goods months."""
	return _shares(company, coverage.goods_span, mapping, GOODS)


def services_shares(company: str, coverage: Coverage, mapping: Mapping) -> list[Contribution]:
	"""What each voucher adds to Kz 21 in the services months, nothing without them."""
	if coverage.services_span is None:
		return []
	return _shares(company, coverage.services_span, mapping, SERVICES)


def span_shares(company: str, span: tuple[date, date], mapping: Mapping) -> list[Contribution]:
	"""What each voucher adds to Kz 41, 42 and 21 from the first to the last day of ``span``, such as a
	Voranmeldungszeitraum."""
	return _shares(company, span, mapping, (*GOODS, *SERVICES))


def _shares(
	company: str, span: tuple[date, date], mapping: Mapping, kennzahlen: Collection[str]
) -> list[Contribution]:
	accounts = accounts_of(mapping, kennzahlen)
	if not accounts:
		return []
	by_kennzahl = contributions(load_lines(company, *span, account_numbers=accounts), mapping)
	return [item for number in kennzahlen for item in by_kennzahl.get(number, ())]


def accounts_of(mapping: Mapping, kennzahlen: Collection[str]) -> set[str]:
	"""The account numbers whose rules feed one of the Kennzahlen."""
	return {
		rule.account_number
		for rule in mapping.rules
		if rule.kennzahl in kennzahlen or rule.also_kennzahl in kennzahlen
	}


def deliveries(company: str, window: tuple[date, date], mapping: Mapping) -> dict[tuple[int, int], Decimal]:
	"""Kz 41 and 42 together in each month of the window, the exact amounts the threshold of § 18a Absatz 1 UStG
	reads; one query per month, so that every month has the exclusions of the Voranmeldung."""
	accounts = accounts_of(mapping, GOODS)
	found = {}
	for year, month in _months(*window):
		period = ReportingPeriod.month(year, month)
		lines = load_lines(company, period.start, period.end, account_numbers=accounts) if accounts else []
		by_kennzahl = contributions(lines, mapping)
		found[(year, month)] = sum(
			(item.amount for number in GOODS for item in by_kennzahl.get(number, ())), ZERO
		)
	return found


def _months(start: date, end: date) -> Iterator[tuple[int, int]]:
	for index in range(start.year * 12 + start.month - 1, end.year * 12 + end.month):
		yield index // 12, index % 12 + 1


def parties(vouchers: Iterable[str | None]) -> dict[str, Party]:
	"""The customer of each voucher that names one, by the voucher key of steuerbote.ledger."""
	by_type = vouchers_by_type(vouchers, (SALES_INVOICE, PAYMENT_ENTRY, JOURNAL_ENTRY))
	found: dict[str, Party] = {}
	found.update(_sales_invoices(by_type.get(SALES_INVOICE, [])))
	found.update(_payment_entries(by_type.get(PAYMENT_ENTRY, [])))
	found.update(_journal_entries(by_type.get(JOURNAL_ENTRY, [])))
	return found


def _sales_invoices(names: list[str]) -> dict[str, Party]:
	if not names:
		return {}
	invoices = frappe.get_all(
		SALES_INVOICE,
		filters={"name": ["in", names]},
		fields=["name", "customer", "customer_name", "tax_id", "customer_address", "shipping_address_name"],
	)
	countries = _countries(
		address
		for invoice in invoices
		for address in (invoice.shipping_address_name, invoice.customer_address)
		if address
	)
	return {
		f"{SALES_INVOICE}:{invoice.name}": Party(
			invoice.customer,
			invoice.customer_name or invoice.customer,
			invoice.tax_id,
			countries.get(invoice.shipping_address_name) or countries.get(invoice.customer_address),
		)
		for invoice in invoices
	}


def _payment_entries(names: list[str]) -> dict[str, Party]:
	if not names:
		return {}
	payments = frappe.get_all(
		PAYMENT_ENTRY,
		filters={"name": ["in", names], "party_type": CUSTOMER},
		fields=["name", "party", "party_name"],
	)
	references = frappe.get_all(
		"Payment Entry Reference",
		filters={"parent": ["in", names], "parenttype": PAYMENT_ENTRY, "reference_doctype": SALES_INVOICE},
		fields=["parent", "reference_name"],
		order_by="idx asc",
	)
	paid = _invoices_referred_to(references)
	tax_ids = _tax_ids(payment.party for payment in payments)
	return {
		f"{PAYMENT_ENTRY}:{payment.name}": _party(
			payment.party, payment.party_name, paid.get(payment.name, []), tax_ids.get(payment.party)
		)
		for payment in payments
	}


def _journal_entries(names: list[str]) -> dict[str, Party]:
	if not names:
		return {}
	rows = frappe.get_all(
		"Journal Entry Account",
		filters={"parent": ["in", names], "parenttype": JOURNAL_ENTRY, "party_type": CUSTOMER},
		fields=["parent", "party", "reference_type", "reference_name"],
		order_by="idx asc",
	)
	customers: dict[str, set[str]] = {}
	for row in rows:
		if row.party:
			customers.setdefault(row.parent, set()).add(row.party)
	single = {entry: next(iter(named)) for entry, named in customers.items() if len(named) == 1}
	referred = _invoices_referred_to(
		row for row in rows if row.parent in single and row.reference_type == SALES_INVOICE
	)
	records = _customers(single.values())
	found = {}
	for entry, customer in single.items():
		record = records.get(customer, frappe._dict())
		found[f"{JOURNAL_ENTRY}:{entry}"] = _party(
			customer, record.customer_name, referred.get(entry, []), record.tax_id
		)
	return found


def _invoices_referred_to(references: Iterable[frappe._dict]) -> dict[str, list[Party]]:
	"""The Sales Invoices that rows with a parent and a reference_name refer to, by parent, in their order."""
	references = [reference for reference in references if reference.reference_name]
	invoices = _sales_invoices(sorted({reference.reference_name for reference in references}))
	referred: dict[str, list[Party]] = {}
	for reference in references:
		invoice = invoices.get(f"{SALES_INVOICE}:{reference.reference_name}")
		if invoice is not None:
			referred.setdefault(reference.parent, []).append(invoice)
	return referred


def _party(customer: str, name: str | None, invoices: list[Party], tax_id: str | None) -> Party:
	"""The customer of a payment or a journal entry, with the USt-IdNr. and the country of the first Sales
	Invoice it refers to that names them; without such an invoice the customer's tax_id counts."""
	vat_id = next((invoice.vat_id for invoice in invoices if invoice.vat_id), None)
	destination = next((invoice.destination for invoice in invoices if invoice.destination), None)
	return Party(customer, name or customer, vat_id or tax_id, destination)


def _customers(names: Iterable[str]) -> dict[str, frappe._dict]:
	names = sorted(set(names))
	if not names:
		return {}
	customers = frappe.get_all(
		CUSTOMER,
		filters={"name": ["in", names]},
		fields=["name", "customer_name", "tax_id", "customer_primary_address"],
	)
	return {customer.name: customer for customer in customers}


def _tax_ids(names: Iterable[str]) -> dict[str, str]:
	return {name: customer.tax_id for name, customer in _customers(names).items() if customer.tax_id}


def _countries(addresses: Iterable[str]) -> dict[str, str]:
	names = sorted(set(addresses))
	if not names:
		return {}
	rows = frappe.get_all("Address", filters={"name": ["in", names]}, fields=["name", "country"])
	return {row.name: row.country for row in rows if row.country}


def filed_returns(company: str, span: tuple[date, date] | None) -> list[FiledReturn]:
	"""The filed Voranmeldungen of the company within the span, with their Kz 41, 42 and 21 as filed.

	A filed return is submitted and not replaced: a corrected return (Kz 10) files the whole period anew.
	"""
	if span is None:
		return []
	returns = frappe.get_all(
		"VAT Return",
		filters={
			"company": company,
			"docstatus": 1,
			"status": FILED,
			"from_date": [">=", span[0]],
			"to_date": ["<=", span[1]],
		},
		fields=["name", "from_date", "to_date"],
	)
	if not returns:
		return []
	rows = frappe.get_all(
		"VAT Return Kennzahl",
		filters={
			"parent": ["in", [item.name for item in returns]],
			"parenttype": "VAT Return",
			"kennzahl": ["in", [*GOODS, *SERVICES]],
		},
		fields=["parent", "kennzahl", "final"],
	)
	amounts: dict[str, dict[str, Decimal]] = {}
	for row in rows:
		amounts.setdefault(row.parent, {})[row.kennzahl] = to_amount(row.final)
	return [FiledReturn(item.from_date, item.to_date, amounts.get(item.name, {})) for item in returns]


def customer_details(customer: str | None) -> Details | None:
	"""Name and address of a customer for the qualified query: its name and its primary address, or else the
	latest of its addresses; None without a name or a town."""
	if not customer:
		return None
	record = _customers([customer]).get(customer)
	if record is None:
		return None
	address = _address(record.customer_primary_address) or _linked_address(customer)
	if address is None or not ((record.customer_name or "").strip() and (address.city or "").strip()):
		return None
	try:
		return Details(record.customer_name, address.city, address.pincode or "", address.address_line1 or "")
	except ValueError:
		return None


def _address(name: str | None) -> frappe._dict | None:
	if not name:
		return None
	return frappe.db.get_value("Address", name, ADDRESS_FIELDS, as_dict=True)


def _linked_address(customer: str) -> frappe._dict | None:
	links = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Address", "link_doctype": CUSTOMER, "link_name": customer},
		pluck="parent",
	)
	if not links:
		return None
	addresses = frappe.get_all(
		"Address",
		filters={"name": ["in", links], "disabled": 0},
		fields=list(ADDRESS_FIELDS),
		order_by="is_primary_address desc, modified desc",
		limit=1,
	)
	return addresses[0] if addresses else None
