"""Plausibility of the input tax: the Vorsteuer a voucher books against the rate its purchase accounts name.

Kz 66 holds the Vorsteuer „aus Rechnungen von anderen Unternehmern“ (form USt 1 A 2026, line 38), and only „die
gesetzlich geschuldete Steuer für Lieferungen und sonstige Leistungen, die von einem anderen Unternehmer für sein
Unternehmen ausgeführt worden sind“ is deductible (§ 15 Abs. 1 Satz 1 Nr. 1 Satz 1 UStG), with a proper invoice (Satz 2).
A tax shown higher than the law owes is owed by the issuer (§ 14c Abs. 1 UStG) but is no deductible Vorsteuer, and the
rates are 19 % and, for the supplies of § 12 Abs. 2 UStG, 7 % (§ 12 Abs. 1 and 2 UStG).

The ledger does not see the invoice. What it does see is the account a purchase is booked on: the charts SKR 03 and SKR 04 name the
rate of the Vorsteuer of their goods and material accounts, such as SKR 03 3300 „Wareneingang 7 % Vorsteuer“
(defaults.purchase_rates). input_tax_hints() compares, voucher by voucher, the Vorsteuer booked on the accounts of Kz 66
with the tax these rates give the bases, rounded per rate as a document rounds its tax lines, and within the same
tolerance per voucher as the Verprobung of the Umsatzsteuer. A voucher that also books a purchase on an account without
a rate is left alone, because its Vorsteuer may belong to that line, and so are the lines without a voucher. A
difference is a warning, never a block: the invoice may show the tax as booked, and only the person who files the
return can look at it.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from decimal import Decimal

from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.mapping import Mapping
from steuerbote.ustva.plausibility import Code, Figures, Hint
from steuerbote.ustva.rounding import HUNDRED, ZERO, to_cents

INPUT_TAX_KENNZAHL = "66"
CHECK = (
	"Abziehbar ist nur die gesetzlich geschuldete Steuer, die eine ordnungsgemäße Rechnung ausweist "
	"(§ 15 Abs. 1 Satz 1 Nr. 1 UStG): Bitte prüfen Sie Rechnung und Steuervorlage."
)


def input_tax_hints(
	lines: Iterable[LedgerLine],
	mapping: Mapping,
	rates: ReadOnlyMapping[str, Decimal],
	tolerance: Decimal,
	figures: Figures,
) -> list[Hint]:
	"""A warning per voucher whose Vorsteuer departs from the rates of its purchase accounts by more than
	``tolerance``, in the order of the vouchers' first lines."""
	input_tax_accounts = {
		rule.account_number for rule in mapping.rules if rule.kennzahl == INPUT_TAX_KENNZAHL
	}
	by_voucher: dict[str, list[LedgerLine]] = {}
	for line in lines:
		if line.voucher is not None:
			by_voucher.setdefault(line.voucher, []).append(line)
	found = []
	for voucher, voucher_lines in by_voucher.items():
		hint = _voucher_hint(voucher, voucher_lines, rates, input_tax_accounts, tolerance, figures)
		if hint is not None:
			found.append(hint)
	return found


def _voucher_hint(
	voucher: str,
	lines: list[LedgerLine],
	rates: ReadOnlyMapping[str, Decimal],
	input_tax_accounts: set[str],
	tolerance: Decimal,
	figures: Figures,
) -> Hint | None:
	bases: dict[str, Decimal] = {}
	booked = ZERO
	others: dict[str, Decimal] = {}
	for line in lines:
		balance = line.debit - line.credit
		if line.account_number in rates:
			bases[line.account_number] = bases.get(line.account_number, ZERO) + balance
		elif line.account_number in input_tax_accounts:
			booked += balance
		else:
			others[line.account_number] = others.get(line.account_number, ZERO) + balance
	total = sum(bases.values(), ZERO)
	if not total or any(balance * total > ZERO for balance in others.values()):
		return None
	by_rate: dict[Decimal, Decimal] = {}
	for account, base in bases.items():
		by_rate[rates[account]] = by_rate.get(rates[account], ZERO) + base
	expected = sum((to_cents(base * rate / HUNDRED) for rate, base in by_rate.items()), ZERO)
	if abs(booked - expected) <= tolerance:
		return None
	voucher_type, _, voucher_no = voucher.partition(":")
	accounts = ", ".join(
		f"{figures.money(base)} auf Konto {account} ({rates[account]} % Vorsteuer)"
		for account, base in bases.items()
	)
	if len(by_rate) == 1:
		(rate,) = by_rate
		should = f"{rate} % wären {figures.money(expected)}"
	else:
		should = f"die Sätze der Konten ergeben {figures.money(expected)}"
	text = f"Der Beleg {voucher_no} bucht {accounts} und {figures.money(booked)} Vorsteuer; {should}. {CHECK}"
	return Hint(Code.INPUT_TAX_DEVIATION, text, voucher_type, voucher_no)
