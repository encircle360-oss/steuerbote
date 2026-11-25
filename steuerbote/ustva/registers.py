"""The Voranmeldung against ERPNext's reports Sales Register and Purchase Register.

Steuerbote computes the Voranmeldung from the general ledger (calculation.py), and the Verprobung checks the tax of
each voucher against its bases. This module adds the reconciliation the principles of the roadmap promise: the sums
of the registers against the amounts the return takes from the ledger, for the person who files it. The registers
list the submitted invoices of the period, the Sales Register the Sales Invoices and the Purchase Register the
Purchase Invoices, with a column per account the invoices book on: the net of their items on an income or expense
account, their tax on a tax account (erpnext/accounts/report/sales_register/sales_register.py and
purchase_register/purchase_register.py, ERPNext 16.60.0). The Frappe layer reads them as register lines, one per
invoice and account.

What is compared, per register:

- the Bemessungsgrundlage of each Kennzahl the register's invoices fill: the net of the accounts of the Kennzahl's
  rules against the Kennzahl's exact amount in the ledger, before the form rounds it;
- the tax on each tax account, an account a Verprobung checks or a rule maps to a tax Kennzahl, against the balance
  of the account in the ledger on the side of the check or the rule.

The difference is the ledger amount less the register amount, rounded to cents. What the return takes from no
invoice of the register, such as a journal entry on a revenue account, is a difference too: the principles say „Eine
Abweichung muss erklärt sein, bevor die Meldung abgegeben wird“ (docs/roadmap.md, Grundsätze), and each difference gets
a hint.

The registers and the ledger lines compared go by posting date, the return by the period of the supply and of a late
booking (steuerbote/ustva/assignment.py). The registers list no cancelled invoice, and the return counts a
cancellation on the day of the voucher it reverses, so the caller leaves a cancelled voucher and its reversal out of
the ledger lines, wherever the immutable ledger posted the reversal. Given the lines the return is computed from (``reported``), an information
row per Kennzahl of a register names the vouchers the return reports in another period than the one they are posted
in, with the amount by which they change the Kennzahl: those posted elsewhere and reported here, and those posted here
and reported elsewhere. It is compared with nothing; a person sees why the Kennzahl of the return is not the amount of
its row.

What cannot be compared is named with its amount and compared with nothing: a register that books on no account in
the period, whose every difference would only be the ledger amount; the opening invoices, which the register lists
and the return leaves out with the opening entries (steuerbote.ledger); the accounts the defaults leave without
Kennzahl on purpose; accounts without a place in the mapping, watched accounts and accounts without number, none of
which enters a Kennzahl; and accounts of a Kennzahl the register does not reconcile.
"""

from collections.abc import Collection, Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, StrEnum
from types import MappingProxyType

from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.kennzahlen import Kennzahl, Kind
from steuerbote.ustva.mapping import AccountRule, Mapping, Side, TaxCheck, is_account_number
from steuerbote.ustva.plausibility import Code, Figures, Hint
from steuerbote.ustva.rounding import ZERO, require_decimal, to_cents


class Register(StrEnum):
	"""ERPNext's report the amounts of a row come from, by its name."""

	SALES = "Sales Register"
	PURCHASES = "Purchase Register"


# A Sales Invoice credits its income and tax accounts; a Purchase Invoice debits its expense accounts and the tax it
# adds and credits the tax it deducts, which the Purchase Register shows as negative (get_invoice_tax_map in
# purchase_register.py). So each register shows the side its invoices book on as positive.
SIDES: MappingProxyType[Register, Side] = MappingProxyType(
	{Register.SALES: Side.CREDIT, Register.PURCHASES: Side.DEBIT}
)

# How the texts name the reports: as the German desk of ERPNext does (erpnext/locale/de.po), and in English.
NAMES: MappingProxyType[Register, str] = MappingProxyType(
	{
		Register.SALES: "Übersicht über den Umsatz (Sales Register)",
		Register.PURCHASES: "Übersicht über Einkäufe (Purchase Register)",
	}
)

# The Kennzahlen each register fills, by the sections of the form USt 1 A 2026. Sections A, B and E (lines 13 to 23
# and 33 to 36) hold the Lieferungen, sonstigen Leistungen and unentgeltlichen Wertabgaben of the company, which it
# invoices with Sales Invoices. Sections C and D (lines 24 to 32) hold what it acquires or receives and owes the tax
# for, and section F the Vorsteuer from invoices of others, from innergemeinschaftliche Erwerbe, Einfuhrumsatzsteuer
# and § 13b UStG (Kz 66, 61, 62 and 67, lines 38 to 41); these come with Purchase Invoices. No invoice of a register
# gives the rest: Vorsteuer by Durchschnittssätze (Kz 63, § 23a UStG), for new vehicles and Kleinunternehmer (Kz 59,
# § 15 Absatz 4a UStG) or corrected after § 15a UStG (Kz 64), which the company computes itself; the other taxes of
# section G, of sales and purchases alike (Kz 65 and 69); the Sondervorauszahlung (Kz 39) and the informational Kz 50
# and 37.
SALES_KENNZAHLEN = frozenset(
	{"81", "86", "87", "35", "36", "77", "76", "80"}
	| {"41", "44", "49", "43", "48"}
	| {"42", "60", "21", "45"}
)
PURCHASE_KENNZAHLEN = frozenset(
	{"91", "89", "93", "90", "95", "98", "94", "96"}
	| {"46", "47", "73", "74", "84", "85"}
	| {"66", "61", "62", "67"}
)
_KENNZAHLEN: MappingProxyType[Register, frozenset[str]] = MappingProxyType(
	{Register.SALES: SALES_KENNZAHLEN, Register.PURCHASES: PURCHASE_KENNZAHLEN}
)


class Reason(Enum):
	"""Why amounts are not compared, as a row names it, in the order of the rows."""

	REPORTED_HERE = "In einem anderen Zeitraum gebucht, in dieser Meldung"
	REPORTED_ELSEWHERE = "In diesem Zeitraum gebucht, in der Meldung eines anderen Zeitraums"
	NO_ACCOUNT = "Keine Rechnung des Zeitraums bucht auf ein Konto, nicht abgeglichen"
	OPENING = "Eröffnungsrechnungen, die die Meldung auslässt"
	DELIBERATELY_WITHOUT_KENNZAHL = "Konten bewusst ohne Kennzahl"
	NO_PLACE = "Konten ohne Platz in der Kontenzuordnung"
	WATCHED = "Beobachtete Konten"
	OTHER_REGISTER = "Konten von Kennzahlen, die diese Übersicht nicht abgleicht"
	NO_NUMBER = "Konten ohne Kontonummer"


@dataclass(frozen=True, slots=True)
class RegisterLine:
	"""What one invoice of a register shows in the column of one account, on the side of the register.

	``account`` is the name of the account in ERPNext, ``account_number`` None for an account without number;
	``opening`` marks an opening invoice. Amounts are in company currency, as exact as the report gives them.
	"""

	register: Register
	account: str
	account_number: str | None
	amount: Decimal
	opening: bool = False

	def __post_init__(self) -> None:
		object.__setattr__(self, "register", Register(self.register))
		if not self.account:
			raise ValueError("a register line names no account")
		if self.account_number is not None and not is_account_number(self.account_number):
			raise ValueError(f"{self.account_number!r} is not an account number")
		if not require_decimal(self.amount).is_finite():
			raise ValueError(f"register amounts must be finite, not {self.amount}")


@dataclass(frozen=True, slots=True)
class Row:
	"""A row of the reconciliation: what the register shows and, when compared, what the ledger gives.

	A row compares the Bemessungsgrundlage of a Kennzahl (``kennzahl``) or the tax on a tax account
	(``account_number``, with ``kennzahl`` when a rule maps it to one). A row not compared has the ``reason`` and the
	``accounts`` behind its amount and no ledger amount; an information row on vouchers reported in another period
	names their Kennzahl and, in ``accounts``, the vouchers.
	"""

	register: Register
	register_amount: Decimal
	ledger_amount: Decimal | None = None
	kennzahl: str = ""
	account_number: str = ""
	reason: Reason | None = None
	accounts: tuple[str, ...] = ()

	@property
	def compared(self) -> bool:
		return self.ledger_amount is not None

	@property
	def difference(self) -> Decimal | None:
		"""The ledger amount less the register amount; None for a row not compared."""
		return None if self.ledger_amount is None else self.ledger_amount - self.register_amount


@dataclass(frozen=True, slots=True)
class _TaxAccount:
	account_number: str
	side: Side
	kennzahl: str
	position: int


class _Roles:
	"""What the mapping makes of each account for the registers."""

	def __init__(self, mapping: Mapping) -> None:
		catalogue = mapping.catalogue
		self.position = {number: index for index, number in enumerate(catalogue)}
		self.bases: dict[Register, dict[str, list[AccountRule]]] = {register: {} for register in Register}
		self.taxes: dict[Register, list[_TaxAccount]] = {register: [] for register in Register}
		for rule in mapping.rules:
			register = _register_of(rule.kennzahl)
			if register is None:
				continue
			if catalogue[rule.kennzahl].kind is Kind.BASE:
				self.bases[register].setdefault(rule.kennzahl, []).append(rule)
			else:
				position = self.position[rule.kennzahl]
				self.taxes[register].append(
					_TaxAccount(rule.account_number, rule.side, rule.kennzahl, position)
				)
		for check in mapping.checks:
			register = _register_of_check(check, mapping)
			if register is None:
				continue
			position = self.position[mapping.rule_for(check.base_accounts[0]).kennzahl]
			for account in check.tax_accounts:
				self.taxes[register].append(_TaxAccount(account, check.side, "", position))

	def accounts(self, register: Register) -> set[str]:
		"""The accounts the register reconciles."""
		bases = {rule.account_number for rules in self.bases[register].values() for rule in rules}
		return bases | {tax.account_number for tax in self.taxes[register]}


def _register_of(kennzahl: str) -> Register | None:
	return next((register for register, numbers in _KENNZAHLEN.items() if kennzahl in numbers), None)


def _register_of_check(check: TaxCheck, mapping: Mapping) -> Register | None:
	"""The register of the bases of a Verprobung; none when they belong to two registers or to none."""
	registers = {_register_of(mapping.rule_for(account).kennzahl) for account in check.base_accounts}
	return registers.pop() if len(registers) == 1 else None


class _Balances:
	"""The debits and credits of the ledger per account."""

	def __init__(self, lines: Iterable[LedgerLine]) -> None:
		self._debit: dict[str, Decimal] = {}
		self._credit: dict[str, Decimal] = {}
		for line in lines:
			self._debit[line.account_number] = self._debit.get(line.account_number, ZERO) + line.debit
			self._credit[line.account_number] = self._credit.get(line.account_number, ZERO) + line.credit

	def balance(self, account_number: str, side: Side) -> Decimal:
		debit = self._debit.get(account_number, ZERO)
		credit = self._credit.get(account_number, ZERO)
		return credit - debit if side is Side.CREDIT else debit - credit


def reconcile(
	lines: Iterable[RegisterLine],
	ledger: Iterable[LedgerLine],
	mapping: Mapping,
	deliberately_without_kennzahl: Collection[str] = frozenset(),
	reported: Iterable[LedgerLine] | None = None,
) -> tuple[Row, ...]:
	"""The rows of both registers, the Sales Register first.

	``lines`` are what the registers show for the period, ``ledger`` the ledger lines of the period by posting date,
	and ``deliberately_without_kennzahl`` the accounts the defaults of the chart leave without Kennzahl on purpose.
	``reported`` are the lines the return is computed from, which give the information rows on vouchers reported in
	another period; without them there are none. The compared rows of a register follow the form, each tax account
	after the Kennzahl of its rule or of the first base of its Verprobung; the rows not compared follow, in the order
	of Reason.
	"""
	lines = tuple(lines)
	ledger = tuple(ledger)
	roles = _Roles(mapping)
	balances = _Balances(ledger)
	moved = _moved(roles, ledger, tuple(reported) if reported is not None else ledger)
	rows: list[Row] = []
	for register in Register:
		of_register = [line for line in lines if line.register is register]
		found = _rows(
			register, of_register, roles, balances, mapping, frozenset(deliberately_without_kennzahl)
		)
		at = sum(1 for row in found if row.compared)
		rows.extend([*found[:at], *moved[register], *found[at:]])
	return tuple(rows)


def _moved(
	roles: _Roles, posted: tuple[LedgerLine, ...], reported: tuple[LedgerLine, ...]
) -> dict[Register, list[Row]]:
	"""The information rows of each register on the vouchers whose amount for a Kennzahl the return reports in another
	period than the ledger posts it, in the order of the form: those reported here, then those reported elsewhere.

	A voucher only the return has for the Kennzahl is reported here, one only the ledger has elsewhere; one both have
	with another amount goes by the sign of the difference."""
	found: dict[Register, list[Row]] = {register: [] for register in Register}
	for register in Register:
		for kennzahl, rules in sorted(
			roles.bases[register].items(), key=lambda item: roles.position[item[0]]
		):
			sides = {rule.account_number: rule.side for rule in rules}
			before, after = _by_voucher(posted, sides), _by_voucher(reported, sides)
			moved: dict[Reason, dict[str, Decimal]] = {}
			for voucher in dict.fromkeys((*before, *after)):
				posting, reporting = before.get(voucher, ZERO), after.get(voucher, ZERO)
				difference = reporting - posting
				if not difference:
					continue
				here = difference > ZERO if posting and reporting else not posting
				reason = Reason.REPORTED_HERE if here else Reason.REPORTED_ELSEWHERE
				moved.setdefault(reason, {})[voucher] = difference
			for reason in (Reason.REPORTED_HERE, Reason.REPORTED_ELSEWHERE):
				if reason in moved:
					amount = to_cents(sum(moved[reason].values(), ZERO))
					vouchers = tuple(_name(voucher) for voucher in moved[reason])
					found[register].append(
						Row(register, amount, kennzahl=kennzahl, reason=reason, accounts=vouchers)
					)
	return found


def _by_voucher(lines: Iterable[LedgerLine], sides: ReadOnlyMapping[str, Side]) -> dict[str, Decimal]:
	"""The balance of the accounts on their sides per voucher, in the order of the lines; the assignment moves vouchers
	only, so lines without voucher are left out."""
	found: dict[str, Decimal] = {}
	for line in lines:
		side = sides.get(line.account_number)
		if side is not None and line.voucher is not None:
			found[line.voucher] = found.get(line.voucher, ZERO) + line.balance(side)
	return found


def _name(voucher: str) -> str:
	"""The name of a voucher without its type, as the ledger keys it (steuerbote.ledger)."""
	return voucher.partition(":")[2] or voucher


def _rows(
	register: Register,
	lines: list[RegisterLine],
	roles: _Roles,
	balances: _Balances,
	mapping: Mapping,
	deliberately_without_kennzahl: frozenset[str],
) -> list[Row]:
	reconciled = roles.accounts(register)
	if not lines:
		if any(balances.balance(account, SIDES[register]) for account in reconciled):
			return [Row(register, ZERO, reason=Reason.NO_ACCOUNT)]
		return []
	shown: dict[str, Decimal] = {}
	apart: dict[Reason, dict[str, Decimal]] = {}
	for line in lines:
		reason = _reason(line, reconciled, mapping, deliberately_without_kennzahl)
		if reason is None:
			shown[line.account_number] = shown.get(line.account_number, ZERO) + line.amount
		else:
			key = line.account_number or line.account
			by_account = apart.setdefault(reason, {})
			by_account[key] = by_account.get(key, ZERO) + line.amount
	compared = [
		*_base_rows(register, roles, shown, balances),
		*_tax_rows(register, roles, shown, balances),
	]
	compared.sort(key=lambda item: item[0])
	return [
		*(row for _key, row in compared),
		*(
			Row(
				register,
				to_cents(sum(apart[reason].values(), ZERO)),
				reason=reason,
				accounts=_listed(apart[reason]),
			)
			for reason in Reason
			if reason in apart
		),
	]


def _reason(
	line: RegisterLine, reconciled: set[str], mapping: Mapping, deliberately_without_kennzahl: frozenset[str]
) -> Reason | None:
	"""Why the amount of a line is not compared; None when its account is one the register reconciles."""
	number = line.account_number
	if line.opening:
		return Reason.OPENING
	if number is None:
		return Reason.NO_NUMBER
	if number in reconciled:
		return None
	if not mapping.has_place(number):
		if number in deliberately_without_kennzahl:
			return Reason.DELIBERATELY_WITHOUT_KENNZAHL
		return Reason.NO_PLACE
	if any(watched.account_number == number for watched in mapping.watched):
		return Reason.WATCHED
	return Reason.OTHER_REGISTER


def _on_side(amount: Decimal, register: Register, side: Side) -> Decimal:
	"""An amount of the register on the side an account carries its balance."""
	return amount if side is SIDES[register] else -amount


def _base_rows(
	register: Register, roles: _Roles, shown: dict[str, Decimal], balances: _Balances
) -> list[tuple[tuple[int, int, str], Row]]:
	found = []
	for kennzahl, rules in roles.bases[register].items():
		amount = sum(
			(_on_side(shown.get(rule.account_number, ZERO), register, rule.side) for rule in rules), ZERO
		)
		ledger = sum((balances.balance(rule.account_number, rule.side) for rule in rules), ZERO)
		if amount or ledger:
			row = Row(register, to_cents(amount), to_cents(ledger), kennzahl=kennzahl)
			found.append(((roles.position[kennzahl], 0, ""), row))
	return found


def _tax_rows(
	register: Register, roles: _Roles, shown: dict[str, Decimal], balances: _Balances
) -> list[tuple[tuple[int, int, str], Row]]:
	found = []
	for tax in roles.taxes[register]:
		amount = _on_side(shown.get(tax.account_number, ZERO), register, tax.side)
		ledger = balances.balance(tax.account_number, tax.side)
		if amount or ledger:
			row = Row(register, to_cents(amount), to_cents(ledger), tax.kennzahl, tax.account_number)
			found.append(((tax.position, 1, tax.account_number), row))
	return found


def _listed(amounts: ReadOnlyMapping[str, Decimal]) -> tuple[str, ...]:
	return tuple(sorted(amounts))


def subject(row: Row, catalogue: ReadOnlyMapping[str, Kennzahl], names: ReadOnlyMapping[str, str]) -> str:
	"""What a row is about, as its table shows it: the Kennzahl with its label, the account with its name as far as
	``names`` holds it by number, or the reason with the accounts behind the amount."""
	if row.reason is not None and row.kennzahl:
		return f"{row.reason.value} (Kz {row.kennzahl}): {', '.join(row.accounts)}"
	if row.reason is not None:
		return f"{row.reason.value}: {', '.join(row.accounts)}" if row.accounts else row.reason.value
	if row.account_number:
		return _account(row.account_number, names)
	return f"Kz {row.kennzahl} {catalogue[row.kennzahl].label}"


def _account(number: str, names: ReadOnlyMapping[str, str]) -> str:
	name = names.get(number)
	return f"Konto {number} {name}" if name else f"Konto {number}"


def hints(rows: Iterable[Row], names: ReadOnlyMapping[str, str], figures: Figures) -> list[Hint]:
	"""A hint per compared row with a difference, in the order of the rows; ``names`` names the accounts."""
	found = []
	for row in rows:
		if not row.difference:
			continue
		who = _account(row.account_number, names) if row.account_number else f"Kz {row.kennzahl}"
		text = (
			f"{who}: Laut {NAMES[row.register]} {figures.money(row.register_amount)}, laut Hauptbuch "
			f"{figures.money(row.ledger_amount)}; die Differenz von {figures.money(row.difference)} braucht vor "
			"der Abgabe eine Erklärung."
		)
		found.append(Hint(Code.REGISTER_DEVIATION, text))
	return found
