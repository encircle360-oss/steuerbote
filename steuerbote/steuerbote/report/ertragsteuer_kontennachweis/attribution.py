"""The rows of the report Ertragsteuer-Kontennachweis without Frappe: the ledger entries behind each line of the
Körperschaftsteuer- and the Gewerbesteuererklärung.

The report reads what Berechnen of the Corporate Income Tax Return reads, the profit and loss account of the
Wirtschaftsjahr and the Income Tax Mapping (steuerbote/income_tax_sources.py), and classify() of steuerbote.kst.categories
sorts its postings by category, keeping each posting of each voucher on each account (Contribution). report_rows()
lays them out as a tree, line by line in the order of the forms:

- Anlage GK line 11, the Jahresüberschuss of the books, with each account of the profit and loss account and its
  balance, credit less debit, and the accounts without a number together, as no mapping places them;
- each step of steuerbote.kst.chain and steuerbote.gewst.chain whose amount comes from categories of the mapping, once
  for each set of categories, with the form, line and Feldkennung of the step, the amount of the books in the
  direction of its categories (an expense debit less credit, an income credit less debit), each account behind it and
  each voucher on the account with its posting date.

The amount of a line is the amount of the books, before the computation: Anlage GK line 156 shows all dividends of the
categories, of which § 8b KStG exempts some, and the lines of the books before their corrections and lines by hand,
which the return shows. Each row names its node and that of its parent, which the tree of the report reads.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from steuerbote.gewst import chain as gewst_chain
from steuerbote.kst import chain as kst_chain
from steuerbote.kst.categories import Category, Contribution, classify
from steuerbote.kst.categories import Mapping as IncomeTaxMapping
from steuerbote.kst.chain import Step
from steuerbote.steuerbote.doctype.corporate_income_tax_return.bridge import Ledger
from steuerbote.steuerbote.doctype.corporate_income_tax_return.layout import TITLES
from steuerbote.ustva.rounding import ZERO

NET_INCOME = "net_income"
UNNUMBERED = "Accounts without a number"
"""The label of the accounts without a number, which the Frappe layer translates."""


def report_rows(
	ledger: Ledger,
	mapping: IncomeTaxMapping,
	account_names: Mapping[str, str],
	posting_dates: Mapping[str, date],
	translate: Callable[[str], str] = str,
) -> list[dict[str, Any]]:
	"""The rows of the report; see the module docstring. ``account_names`` gives the account of each number, the keys of
	``posting_dates`` are the vouchers as "<voucher type>:<voucher name>"."""
	classification = classify(ledger.lines, mapping)
	rows = _net_income(ledger, account_names, translate)
	shown: set[tuple[Category, ...]] = set()
	for step in (*kst_chain.STEPS, *gewst_chain.STEPS):
		if not step.categories or step.categories in shown:
			continue
		contributions = classification.contributions(*step.categories)
		if not contributions:
			continue
		shown.add(step.categories)
		rows.extend(_step(step, contributions, account_names, posting_dates))
	return rows


def vouchers(ledger: Ledger) -> list[str]:
	"""The vouchers of the postings of the ledger, whose posting dates the report reads."""
	return sorted({line.voucher for line in ledger.lines if line.voucher})


def _net_income(
	ledger: Ledger, account_names: Mapping[str, str], translate: Callable[[str], str]
) -> list[dict[str, Any]]:
	step = kst_chain.step(NET_INCOME)
	node = step.field or NET_INCOME
	rows = [_line(step, node, ledger.net_income)]
	balances: dict[str, list[Decimal]] = {}
	for line in ledger.lines:
		balance = balances.setdefault(line.account_number, [ZERO, ZERO])
		balance[0] += line.debit
		balance[1] += line.credit
	for number, (debit, credit) in sorted(balances.items()):
		rows.append(
			{
				"node": f"{node}/{number}",
				"parent_node": node,
				"indent": 1,
				"account": account_names.get(number, number),
				"debit": debit,
				"credit": credit,
				"amount": credit - debit,
			}
		)
	if ledger.unnumbered:
		rows.append(
			{
				"node": f"{node}/-",
				"parent_node": node,
				"indent": 1,
				"label": translate(UNNUMBERED),
				"amount": sum((account.balance for account in ledger.unnumbered), ZERO),
			}
		)
	return rows


def _step(
	step: Step,
	contributions: Iterable[Contribution],
	account_names: Mapping[str, str],
	posting_dates: Mapping[str, date],
) -> list[dict[str, Any]]:
	contributions = list(contributions)
	node = step.field or step.key
	rows = [_line(step, node, sum((item.amount for item in contributions), ZERO))]
	by_account: dict[str, list[Contribution]] = {}
	for item in contributions:
		by_account.setdefault(item.account_number, []).append(item)
	for number, items in sorted(by_account.items()):
		account_node = f"{node}/{number}"
		rows.append(
			{
				"node": account_node,
				"parent_node": node,
				"indent": 1,
				"account": account_names.get(number, number),
				"debit": sum((item.debit for item in items), ZERO),
				"credit": sum((item.credit for item in items), ZERO),
				"amount": sum((item.amount for item in items), ZERO),
			}
		)
		for item in sorted(
			items, key=lambda entry: (posting_dates.get(entry.voucher or "", date.min), entry.voucher or "")
		):
			voucher_type, _, voucher_no = (item.voucher or "").partition(":")
			rows.append(
				{
					"node": f"{account_node}/{item.voucher}",
					"parent_node": account_node,
					"indent": 2,
					"account": account_names.get(number, number),
					"posting_date": posting_dates.get(item.voucher or ""),
					"voucher_type": voucher_type or None,
					"voucher_no": voucher_no or None,
					"debit": item.debit,
					"credit": item.credit,
					"amount": item.amount,
				}
			)
	return rows


def _line(step: Step, node: str, amount: Decimal) -> dict[str, Any]:
	return {
		"node": node,
		"parent_node": None,
		"indent": 0,
		"line": f"{TITLES[step.form]} {step.line}",
		"feldkennung": step.field or "",
		"label": step.label,
		"amount": amount,
		"bold": 1,
	}
