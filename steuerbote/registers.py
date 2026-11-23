"""ERPNext's reports Sales Register and Purchase Register of a company and period, as the register lines of
steuerbote.ustva.registers.

Both reports take the filters company, from_date and to_date and list the submitted invoices of the company whose
posting date lies in between, both days included; a cancelled invoice is no longer submitted and stays out
(execute and get_invoices with docstatus 1 in sales_register.py and purchase_register.py, apply_common_conditions in
erpnext/accounts/report/utils.py, ERPNext 16.60.0). Each report has a column per account its invoices book on,
labelled with the name of the account and keyed by it (frappe.scrub): an income or expense account with the net of
the items, a tax account with the tax of the rows. Each row is an invoice, and each of its cells in such a column
becomes a register line. The reports list opening invoices, which the return leaves out, so their lines are marked.
Without invoices a report announces "No record found", which Berechnen does not show. The reports apply the
permissions of the user who calculates, as on their pages.
"""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import frappe
from erpnext.accounts.report.purchase_register import purchase_register
from erpnext.accounts.report.sales_register import sales_register

from steuerbote.ustva.registers import Register, RegisterLine

# Each register, the function of its report and the invoices it lists.
REPORTS: tuple[tuple[Register, Callable, str], ...] = (
	(Register.SALES, sales_register.execute, "Sales Invoice"),
	(Register.PURCHASES, purchase_register.execute, "Purchase Invoice"),
)


def register_lines(company: str, from_date: date | str, to_date: date | str) -> list[RegisterLine]:
	"""What both registers show for the company from ``from_date`` to ``to_date``: a line per invoice and account,
	the Sales Register first; an empty cell gives no line."""
	numbers = dict(
		frappe.get_all(
			"Account", filters={"company": company}, fields=["name", "account_number"], as_list=True
		)
	)
	lines: list[RegisterLine] = []
	for register, execute, doctype in REPORTS:
		columns, rows = _report(execute, company, from_date, to_date)
		accounts = {
			column["fieldname"]: column["label"]
			for column in columns
			if column.get("label") in numbers and column.get("fieldname") == frappe.scrub(column["label"])
		}
		opening = _opening_invoices(doctype, [row["voucher_no"] for row in rows])
		for row in rows:
			for fieldname, account in accounts.items():
				if amount := row.get(fieldname):
					lines.append(
						RegisterLine(
							register,
							account,
							(numbers[account] or "").strip() or None,
							Decimal(str(amount)),
							row["voucher_no"] in opening,
						)
					)
	return lines


def _report(execute: Callable, company: str, from_date: date | str, to_date: date | str) -> tuple[list, list]:
	"""Columns and rows of a register; the message of an empty report stays unseen."""
	muted = frappe.flags.mute_messages
	frappe.flags.mute_messages = True
	try:
		result = execute(frappe._dict(company=company, from_date=from_date, to_date=to_date))
	finally:
		frappe.flags.mute_messages = muted
	return result[0], result[1]


def _opening_invoices(doctype: str, names: list[str]) -> set[str]:
	if not names:
		return set()
	return set(frappe.get_all(doctype, filters={"name": ["in", names], "is_opening": "Yes"}, pluck="name"))
