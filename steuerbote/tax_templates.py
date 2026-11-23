"""The accounts the tax templates of a company name, as the template accounts of steuerbote.ustva.tax_templates.

ERPNext takes the taxes of an invoice from templates: each row of a Sales Taxes and Charges Template or a Purchase
Taxes and Charges Template names an account (taxes[].account_head), and an Item Tax Template names the account of
each rate it sets for an item (taxes[].tax_type), every template for one company (field company; ERPNext 16.60.0,
DocTypes sales_taxes_and_charges_template, purchase_taxes_and_charges_template and item_tax_template with their
tables). A Tax Rule only picks one of these templates for an invoice (sales_tax_template, purchase_tax_template) and
never a disabled one (get_tax_template in erpnext/accounts/doctype/tax_rule/tax_rule.py), so the templates of the
company cover the accounts of its Tax Rules. A disabled template gives no invoice its taxes, since the search of a
link field offers no disabled record (frappe/desk/search.py), and is left out. Only the rows are read, through
Frappe's query builder with parameters.
"""

import frappe
from frappe.query_builder.functions import Coalesce

from steuerbote.ustva.tax_templates import TemplateAccount

# Each kind of template, its table and the field of the table that names the account.
TEMPLATES = (
	("Sales Taxes and Charges Template", "Sales Taxes and Charges", "account_head"),
	("Purchase Taxes and Charges Template", "Purchase Taxes and Charges", "account_head"),
	("Item Tax Template", "Item Tax Template Detail", "tax_type"),
)


def template_accounts(company: str) -> list[TemplateAccount]:
	"""Every account the enabled tax templates of the company name, each with these templates.

	The accounts come by account number, those without number last, each kind of template and its templates in
	the order of TEMPLATES and their names.
	"""
	found: dict[str, tuple[str | None, str, list[str]]] = {}
	for doctype, table, field in TEMPLATES:
		for row in _rows(company, doctype, table, field):
			number = (row.account_number or "").strip() or None
			_number, _name, templates = found.setdefault(
				row.account, (number, row.account_name or row.account, [])
			)
			if row.template not in templates:
				templates.append(row.template)
	return [
		TemplateAccount(account, number, name, tuple(templates))
		for account, (number, name, templates) in sorted(
			found.items(), key=lambda item: (item[1][0] is None, item[1][0] or "", item[0])
		)
	]


def _rows(company: str, doctype: str, table: str, field: str) -> list[frappe._dict]:
	template = frappe.qb.DocType(doctype)
	row = frappe.qb.DocType(table)
	account = frappe.qb.DocType("Account")
	return (
		frappe.qb.from_(row)
		.inner_join(template)
		.on(template.name == row.parent)
		.left_join(account)
		.on(account.name == row[field])
		.select(
			row[field].as_("account"),
			account.account_number,
			account.account_name,
			template.name.as_("template"),
		)
		.where(row.parenttype == doctype)
		.where(template.company == company)
		.where(template.disabled == 0)
		.where(Coalesce(row[field], "") != "")
		.orderby(template.name)
		.orderby(row.idx)
		.run(as_dict=True)
	)
