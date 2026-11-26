"""The suppliers behind the vouchers of sections C and D, as the core in steuerbote.ustva.residence reads them.

calculate() asks for what is known of each voucher that posts on a base or tax account of a Verprobung of a purchase
whose tax the company owes (purchase_vouchers): its day, its suppliers, and the classifications under § 13b UStG a
person stated in the VAT Return Mapping. The core decides; this module only reads.

- **Suppliers** are the parties of type Supplier on the GL Entries of the voucher: the payable line of a Purchase
  Invoice, the line of a Journal Entry or Payment Entry with a supplier. A voucher without one has none.
- **Day** is the first posting date of the voucher, the day whose member states count (§ 13b Absatz 7 Satz 4 UStG
  names the day of the supply, which the ledger does not keep).
- **Country** is the field Land (country) of the Supplier, **address** the country of its primary address
  (supplier_primary_address), **VAT ID** its field Steuernummer (tax_id), which ERPNext uses for the USt-IdNr.
- **Classifications** are the rows of the table „Einordnung nach § 13b UStG“ of the company's VAT Return Mapping: a
  row of a Purchase Invoice or Journal Entry classifies that voucher, a row of a Supplier the supplier and a row of a
  Purchase Taxes and Charges Template every Purchase Invoice with that template.
"""

from collections.abc import Iterable
from datetime import date

import frappe

from steuerbote.ustva import Classification, LedgerLine, Mapping, Supplier, Voucher, purchase_vouchers
from steuerbote.vatid.partners import party_label

MAPPING_DOCTYPE = "VAT Return Mapping"
PURCHASE_INVOICE = "Purchase Invoice"
SUPPLIER = "Supplier"
TAX_TEMPLATE = "Purchase Taxes and Charges Template"


def load_vouchers(company: str, lines: Iterable[LedgerLine], mapping: Mapping) -> dict[str, Voucher]:
	"""What is known of the vouchers of sections C and D among the lines, by their key in the ledger lines."""
	keys = purchase_vouchers(lines, mapping)
	if not keys:
		return {}
	stated = classifications(company)
	entries = _entries(company, keys)
	suppliers = _suppliers({party for _, _, parties in entries.values() for party in parties})
	templates = _templates([key.partition(":")[2] for key in keys if key.startswith(f"{PURCHASE_INVOICE}:")])
	found: dict[str, Voucher] = {}
	for key in keys:
		if key not in entries:
			continue
		voucher_type, day, parties = entries[key]
		name = key.partition(":")[2]
		template = templates.get(name) if voucher_type == PURCHASE_INVOICE else None
		found[key] = Voucher(
			day=day,
			suppliers=tuple(
				_with_classification(suppliers[party], stated.get((SUPPLIER, party)))
				for party in parties
				if party in suppliers
			),
			classification=stated.get((voucher_type, name)),
			tax_template=template,
			template_classification=stated.get((TAX_TEMPLATE, template)) if template else None,
		)
	return found


def classifications(company: str) -> dict[tuple[str, str], Classification]:
	"""The classifications under § 13b UStG of the company's VAT Return Mapping, by document type and name."""
	rows = frappe.get_all(
		"VAT Return Mapping Reverse Charge",
		filters={"parenttype": MAPPING_DOCTYPE, "parent": company, "parentfield": "reverse_charge"},
		fields=["reference_doctype", "reference_name", "classification"],
	)
	return {
		(row.reference_doctype, row.reference_name): Classification(row.classification)
		for row in rows
		if row.reference_name and row.classification
	}


def _entries(company: str, keys: Iterable[str]) -> dict[str, tuple[str, date, tuple[str, ...]]]:
	"""Per voucher key: its type, its first posting date and its suppliers in the order of their names."""
	by_type: dict[str, list[str]] = {}
	for key in keys:
		voucher_type, _, name = key.partition(":")
		by_type.setdefault(voucher_type, []).append(name)
	gl_entry = frappe.qb.DocType("GL Entry")
	found: dict[str, tuple[str, date, tuple[str, ...]]] = {}
	for voucher_type, names in by_type.items():
		rows = (
			frappe.qb.from_(gl_entry)
			.select(gl_entry.voucher_no, gl_entry.posting_date, gl_entry.party_type, gl_entry.party)
			.where(gl_entry.company == company)
			.where(gl_entry.is_cancelled == 0)
			.where(gl_entry.voucher_type == voucher_type)
			.where(gl_entry.voucher_no.isin(names))
			.orderby(gl_entry.posting_date)
			.run(as_dict=True)
		)
		for row in rows:
			key = f"{voucher_type}:{row.voucher_no}"
			_, day, parties = found.get(key, (voucher_type, row.posting_date, ()))
			if row.party_type == SUPPLIER and row.party and row.party not in parties:
				parties = tuple(sorted((*parties, row.party)))
			found[key] = (voucher_type, day, parties)
	return found


def _suppliers(names: Iterable[str]) -> dict[str, Supplier]:
	"""The suppliers by name, with the country, the country of the primary address and the VAT ID."""
	names = sorted(set(names))
	if not names:
		return {}
	rows = frappe.get_all(
		SUPPLIER,
		filters={"name": ["in", names]},
		fields=["name", "supplier_name", "country", "tax_id", "supplier_primary_address"],
	)
	primary = [row.supplier_primary_address for row in rows if row.supplier_primary_address]
	addresses = (
		{
			address.name: address.country
			for address in frappe.get_all(
				"Address", filters={"name": ["in", primary]}, fields=["name", "country"]
			)
		}
		if primary
		else {}
	)
	return {
		row.name: Supplier(
			name=party_label(row.name, row.supplier_name),
			country=row.country or None,
			address_country=addresses.get(row.supplier_primary_address) or None,
			vat_id=row.tax_id or None,
		)
		for row in rows
	}


def _with_classification(supplier: Supplier, classification: Classification | None) -> Supplier:
	if classification is None:
		return supplier
	return Supplier(
		supplier.name, supplier.country, supplier.address_country, supplier.vat_id, classification
	)


def _templates(names: list[str]) -> dict[str, str]:
	"""The tax template of each Purchase Invoice that has one, by invoice."""
	if not names:
		return {}
	rows = frappe.get_all(
		PURCHASE_INVOICE, filters={"name": ["in", names]}, fields=["name", "taxes_and_charges"]
	)
	return {row.name: row.taxes_and_charges for row in rows if row.taxes_and_charges}
