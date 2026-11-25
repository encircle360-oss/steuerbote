"""The vouchers behind each Kennzahl, for the report UStVA Kennzahlen. Pure Python, no Frappe.

contributions() splits the core's calculate() by voucher with the core's own rules, so the vouchers of a
Kennzahl add up to the amount calculate() computes for it. An account with a rule gives its balance on the
rule's side to the rule's Kennzahl and, with an additional Kennzahl, its balance on that side to it. A rule
with a tax rate adds the tax derived from the bases of a voucher: per voucher, tax Kennzahl and rate, the
bases of all accounts are summed and the tax is rounded once, as in calculate(). A base the core derives for a
voucher without base account (derive_bases) contributes to its Kennzahl with the accounts whose lines make it, or the
tax accounts of its Verprobung when it was taken from the tax, and to the derived tax of its voucher. Lines without a
voucher count as one voucher.

report_rows() turns the result and the contributions into the rows of the report in the order of the form:
a row per Kennzahl, followed by its vouchers one level deeper, and the sums the form computes itself in
lines 37, 45 and 48. Their wording follows the form USt 1 A 2026 (BMF letter of 29 December 2025,
GZ III C 3 - S 7344/00039/007/036). A voucher row names the customer or supplier of an invoice and links
to the print view of its voucher, or says that the voucher is cancelled; vouchers_by_type() groups the
vouchers so that the report reads the parties and the cancelled vouchers with one query per voucher type.
"""

from collections.abc import Collection, Iterable, Sequence
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from html import escape
from typing import Any
from urllib.parse import quote, urlencode

from steuerbote.steuerbote.doctype.vat_return.bridge import split_voucher
from steuerbote.ustva import Kennzahl, LedgerLine, Mapping, Side, UstvaResult, derive_bases, tax_from_base
from steuerbote.ustva.rounding import ZERO

COLUMNS = (
	"kennzahl",
	"line",
	"label",
	"posting_date",
	"voucher_type",
	"voucher_no",
	"print_link",
	"party",
	"account",
	"debit",
	"credit",
	"amount",
	"reported",
	"previous_period",
	"previous_year",
	"difference",
)

# Line, wording on the form and the UstvaResult attribute holding the sum.
SUM_LINES = (
	(37, "Umsatzsteuer (Summe der Zeilen 13 bis 18 und 25 bis 32)", "output_tax"),
	(45, "Verbleibender Betrag (Zeile 37 abzüglich der Zeilen 38 bis 44)", "remaining_tax"),
	(48, "Umsatzsteuer-Vorauszahlung/Überschuss (Summe der Zeilen 45 bis 47)", "prepayment"),
)


@dataclass(frozen=True, slots=True)
class Contribution:
	"""What one voucher adds to one Kennzahl, and the postings it comes from.

	``accounts`` are the account numbers whose balances make up the amount: one for a balance that a rule
	reports, one or more for a tax derived from the bases of the voucher at one rate. ``debit`` and
	``credit`` are the postings of these accounts in the voucher.
	"""

	kennzahl: str
	voucher: str | None
	accounts: tuple[str, ...]
	debit: Decimal
	credit: Decimal
	amount: Decimal


@dataclass(slots=True)
class _Postings:
	debit: Decimal = ZERO
	credit: Decimal = ZERO

	def balance(self, side: Side) -> Decimal:
		if side is Side.CREDIT:
			return self.credit - self.debit
		return self.debit - self.credit


@dataclass(slots=True)
class _DerivedBase:
	accounts: list[str] = field(default_factory=list)
	postings: _Postings = field(default_factory=_Postings)
	base: Decimal = ZERO


def contributions(lines: Iterable[LedgerLine], mapping: Mapping) -> dict[str, list[Contribution]]:
	"""The contributions of the lines to each Kennzahl, vouchers in the order of their first line."""
	lines = tuple(lines)
	postings: dict[tuple[str, str | None], _Postings] = {}
	first_line: dict[str | None, int] = {}
	for ledger_line in lines:
		key = (ledger_line.account_number, ledger_line.voucher)
		total = postings.setdefault(key, _Postings())
		total.debit += ledger_line.debit
		total.credit += ledger_line.credit
		first_line.setdefault(ledger_line.voucher, len(first_line))

	found: dict[str, list[Contribution]] = {}
	derived: dict[tuple[str, Decimal, str | None], _DerivedBase] = {}
	for (account, voucher), total in postings.items():
		rule = mapping.rule_for(account)
		if rule is None:
			continue
		reported = ((rule.kennzahl, rule.side), (rule.also_kennzahl, rule.also_side))
		for kennzahl, side in reported:
			if kennzahl is not None:
				found.setdefault(kennzahl, []).append(
					Contribution(
						kennzahl, voucher, (account,), total.debit, total.credit, total.balance(side)
					)
				)
		if rule.tax_rate is not None:
			tax_kennzahl = mapping.catalogue[rule.kennzahl].tax_kennzahl
			base = derived.setdefault((tax_kennzahl, rule.tax_rate, voucher), _DerivedBase())
			base.accounts.append(account)
			base.postings.debit += total.debit
			base.postings.credit += total.credit
			base.base += total.balance(rule.side)
	checks = {check.label: check for check in mapping.checks}
	for found_base in derive_bases(lines, mapping):
		accounts = found_base.accounts or checks[found_base.label].tax_accounts
		shown = [account for account in accounts if (account, found_base.voucher) in postings]
		debit = sum((postings[(account, found_base.voucher)].debit for account in shown), ZERO)
		credit = sum((postings[(account, found_base.voucher)].credit for account in shown), ZERO)
		found.setdefault(found_base.kennzahl, []).append(
			Contribution(
				found_base.kennzahl, found_base.voucher, tuple(shown), debit, credit, found_base.base
			)
		)
		tax_kennzahl = mapping.catalogue[found_base.kennzahl].tax_kennzahl
		if tax_kennzahl is not None:
			base = derived.setdefault((tax_kennzahl, found_base.rate, found_base.voucher), _DerivedBase())
			base.accounts.extend(shown)
			base.postings.debit += debit
			base.postings.credit += credit
			base.base += found_base.base
	for (tax_kennzahl, rate, voucher), base in derived.items():
		found.setdefault(tax_kennzahl, []).append(
			Contribution(
				tax_kennzahl,
				voucher,
				tuple(base.accounts),
				base.postings.debit,
				base.postings.credit,
				tax_from_base(base.base, rate),
			)
		)
	for items in found.values():
		items.sort(key=lambda item: first_line[item.voucher])
	return found


def report_rows(
	result: UstvaResult,
	catalogue: ReadOnlyMapping[str, Kennzahl],
	by_kennzahl: ReadOnlyMapping[str, Sequence[Contribution]],
	*,
	posting_dates: ReadOnlyMapping[str, date],
	account_names: ReadOnlyMapping[str, str],
	parties: ReadOnlyMapping[str, str],
	print_label: str,
	cancelled_label: str,
	currency: str,
	cancelled: Collection[str] = (),
	shown: Collection[str] = (),
) -> list[dict[str, Any]]:
	"""The rows of the report in the order of the form: Kennzahlen with their vouchers, and the sums.

	A Kennzahl appears when it has an amount or vouchers, so vouchers that cancel each other out stay
	visible, or when it is one of the Kennzahlen in ``shown``, such as those a compared period reports.
	``posting_dates``, ``account_names`` and ``parties`` look up the voucher keys and account numbers; a
	party is shown as ERPNext keeps its name. ``print_label`` is the text of the link to the print view.
	A voucher whose key is in ``cancelled`` shows ``cancelled_label`` instead of the link, because Frappe
	prints no cancelled document unless its Print Settings allow it.
	"""
	blocks: list[tuple[int, int, list[dict[str, Any]]]] = []
	for position, kennzahl in enumerate(catalogue.values()):
		value = result.values.get(kennzahl.number)
		items = by_kennzahl.get(kennzahl.number, ())
		if value is None and not items and kennzahl.number not in shown:
			continue
		rows = [
			_row(
				kennzahl=kennzahl.number,
				line=kennzahl.line,
				label=kennzahl.label,
				amount=value.amount if value else ZERO,
				reported=value.reported if value else ZERO,
				bold=1,
				currency=currency,
			)
		]
		rows += [
			_voucher_row(
				item,
				posting_dates,
				account_names,
				parties,
				_print_column(item.voucher, print_label, cancelled, cancelled_label),
				currency,
			)
			for item in items
		]
		blocks.append((kennzahl.line, position, rows))
	for line, label, total in SUM_LINES:
		blocks.append(
			(
				line,
				len(catalogue),
				[_row(line=line, label=label, reported=getattr(result, total), bold=1, currency=currency)],
			)
		)
	return [row for _line, _position, rows in sorted(blocks, key=lambda block: block[:2]) for row in rows]


def _voucher_row(
	item: Contribution,
	posting_dates: ReadOnlyMapping[str, date],
	account_names: ReadOnlyMapping[str, str],
	parties: ReadOnlyMapping[str, str],
	print_column: str | None,
	currency: str,
) -> dict[str, Any]:
	voucher_type, voucher_no = split_voucher(item.voucher)
	single_name = account_names.get(item.accounts[0]) if len(item.accounts) == 1 else None
	return _row(
		kennzahl=item.kennzahl,
		label=None if single_name else ", ".join(item.accounts),
		posting_date=posting_dates.get(item.voucher) if item.voucher else None,
		voucher_type=voucher_type,
		voucher_no=voucher_no,
		print_link=print_column,
		party=parties.get(item.voucher) if item.voucher else None,
		account=single_name,
		debit=item.debit,
		credit=item.credit,
		amount=item.amount,
		indent=1,
		parent_kennzahl=item.kennzahl,
		currency=currency,
	)


def _print_column(
	voucher: str | None, print_label: str, cancelled: Collection[str], cancelled_label: str
) -> str | None:
	"""HTML for the column Print of a voucher: the link to its print view, or the label of a cancelled one."""
	if not voucher:
		return None
	if voucher in cancelled:
		return escape(cancelled_label)
	return _print_link(*split_voucher(voucher), print_label)


def _print_link(voucher_type: str, voucher_no: str, label: str) -> str:
	"""HTML for a Data column of the report: a link that opens the print view of the voucher in a new tab."""
	query = urlencode({"doctype": voucher_type, "name": voucher_no}, quote_via=quote)
	return f'<a href="{escape(f"/printview?{query}")}" target="_blank">{escape(label)}</a>'


def vouchers_by_type(
	vouchers: Iterable[str | None], voucher_types: Collection[str] | None = None
) -> dict[str, list[str]]:
	"""The names of the vouchers by voucher type, each name once: of the given voucher types or, without
	them, of every voucher type."""
	found: dict[str, set[str]] = {}
	for voucher in vouchers:
		if not voucher:
			continue
		voucher_type, voucher_no = split_voucher(voucher)
		if voucher_types is None or voucher_type in voucher_types:
			found.setdefault(voucher_type, set()).add(voucher_no)
	return {voucher_type: sorted(names) for voucher_type, names in found.items()}


def _row(indent: int = 0, parent_kennzahl: str | None = None, bold: int = 0, **values: Any) -> dict[str, Any]:
	return {
		**dict.fromkeys(COLUMNS),
		**values,
		"indent": indent,
		"parent_kennzahl": parent_kennzahl,
		"bold": bold,
	}
