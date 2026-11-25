"""Compute the Kennzahlen of one Voranmeldungszeitraum from ledger lines.

The input is the general ledger of the period, one line per posting and account, in company
currency and in cents. The ledger is the source rather than invoices so that journal entries and
imported batches count too. The caller leaves out what does not belong to the period's turnover:
entries the ledger flags as cancelled, opening entries, period closing entries, and the entries
that clear the tax accounts against the tax office.

Each line can name its voucher, the document the posting belongs to: in ERPNext the voucher_no of
the GL Entry, joined with its voucher_type if two document types can share a name. The books round
the tax once per document, not once per month, so every tax computed here from base accounts is
computed per voucher too. The tax the rules' rates derive is rounded to cents per voucher, tax
Kennzahl and rate, as a document rounds each of its tax lines, and the tax Kennzahl is the sum of
these amounts. A Verprobung compares, voucher by voucher, the tax booked on its tax accounts with
the tax on its bases. Rounding the month's sum instead drifts from the books, and from the input tax
booked on the same documents: three services of 33.33 at 19 % carry 6.33 tax each, 18.99 together,
while 19 % of their sum is 19.00. Lines without a voucher count as one document per tax Kennzahl and
rate, and per check.

The tax of the bases with a statutory rate (Kennzahl 81, 86, 89 and 93) has no Kennzahl of its own: the form
transmits only the base, in full euros, and Kz 83 with cents. How it enters the sums and Kz 83 is the setting
StatutoryTax of the company:

- FROM_BASE, the default: the rate times the reported base in full euros, as the form computes it („Steuer“ next to
  lines 13, 14, 25 and 26 of USt 1 A 2026). The cents of the bases drop out of the tax as well.
- AS_BOOKED: the tax the vouchers of the Verprobung of the base book on its tax accounts (booked_taxes()), so Kz 83
  is the balance of the tax accounts to the cent. A voucher that shows bases of two Kennzahlen at a statutory rate in
  one Verprobung, such as the acquisitions without Vorsteuerabzug at 7 and 19 %, splits its booked tax by the exact
  tax of each base (rounding.apportion_cents); a voucher that also shows a base whose tax has a Kennzahl of its own
  leaves that tax, as derived for that Kennzahl, to it; a voucher that books tax without any base gives it to the
  first Kennzahl at a statutory rate of its Verprobung. A base outside every Verprobung takes the tax of its rate per
  voucher, as a document rounds it. The bases themselves are reported in full euros either way, and the Verprobung
  is the same.

The Jahresdokumentation UStVA 2026 has no rule that computes Kz 83 again from the bases, so ERiC takes both. The
derived taxes with a Kennzahl of their own, such as Kz 47 and 85, are the same in both.

A purchase whose tax the company owes itself, an innergemeinschaftlicher Erwerb or a Leistung under § 13b UStG, is
often booked without a base account of its own: its net goes to an ordinary expense, asset or goods account, and a
tax key or the tax template of the invoice books its tax on the tax accounts of the Verprobung. For a Verprobung that
names a ``derived_base`` (mapping.py), derive_bases() finds the base of every voucher that books tax on its tax
accounts but nothing on its base accounts:

- from the voucher: the lines on accounts without any place in the mapping, whose balance on the side of the bases
  times the rate gives the booked tax, closest first and within a cent. A line of another purpose in the same
  voucher, such as a bank fee, stays out, because with it the tax no longer fits. When two sets of lines fit equally
  well with different sums, when none fits, or when the voucher has more than MOST_LINES such accounts, the lines do
  not tell the base;
- otherwise from the tax: tax / rate, to cents (rounding.base_from_tax), whose tax is the booked tax again. The
  result names such a voucher, and the return gives a hint for it. Lines without voucher always take this way.

A Verprobung that also names a ``derived_base_eu`` sends the base of a voucher to it when residence.place() classifies
the voucher as a sonstige Leistung of § 3a Absatz 2 UStG of a business established in another member state (§ 13b
Absatz 1 UStG, Kz 46), from what the caller knows of the voucher (``vouchers``, by the voucher of the ledger lines);
every other voucher, and every voucher while its classification stays open, takes the ``derived_base`` (Kz 84). The
result carries the Findings of these decisions, and two more on the vouchers of sections C and D: a voucher of an
innergemeinschaftlicher Erwerb whose supplier is established in the Drittlandsgebiet, and a voucher on a base account
of the ``derived_base_eu`` whose supplier is not established in another member state or that a person classified
otherwise. Without ``vouchers`` every derived base takes the ``derived_base`` and nothing is found.

A voucher with a posting on a base account of the Verprobung keeps it as before: it says where its base is, so a tax
that does not fit stays a deviation and nothing is counted twice. The derived base goes to its Kennzahl and, for a
base with a tax Kennzahl of its own, its tax is derived per voucher with the bases of the base accounts; the
Verprobung counts it as computed tax.

Turnover is the mirror case. A Verprobung of output tax at a statutory rate that names its own Kennzahl, 81 or 86
(mapping.DERIVED_TURNOVER_KENNZAHLEN), takes the base of a voucher that books more output tax on its tax accounts than
its base accounts carry, as ERPNext's sale of a fixed asset through a Sales Invoice does: it books no revenue, but the
receivable, the cost of the asset, its accumulated depreciation, the gain or loss on the company's disposal account and
the tax (erpnext/assets/doctype/asset/depreciation.py, get_gl_entries_on_asset_disposal); the lines on the asset, the
depreciation and the disposal account add up to the price. For such a check derive_bases() takes the remaining tax of
every voucher, the booked tax less the tax of its base accounts rounded to cents, when it is output tax of more than a
cent, and finds its base in the lines of the voucher as above. It never takes a base from the tax alone: a voucher
whose lines do not explain the remaining tax, a negative remaining tax such as input tax booked on the output-tax
account, a correction of the tax account or a credit note, and the lines without voucher stay a deviation of the
Verprobung, for a person to look at. The base keeps the statutory tax of its Kennzahl, from the base in full euros or
as booked like every other part of its voucher (StatutoryTax).

A balance on a watched account never enters a Kennzahl. At the blocking level it holds the return
(``unmapped``); at the hint level the result carries the account's debits and credits (``hinted``) for a
hint, and the return stays ready.
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from itertools import combinations
from types import MappingProxyType

from steuerbote.ustva.kennzahlen import (
	BALANCE_KENNZAHL,
	INPUT_TAX_LINES,
	OTHER_TAX_LINES,
	OUTPUT_TAX_LINES,
	SONDERVORAUSZAHLUNG_KENNZAHL,
	Effect,
	Kennzahl,
	Kind,
)
from steuerbote.ustva.mapping import Mapping, Side, TaxCheck, WatchLevel, is_account_number
from steuerbote.ustva.residence import Classification, Finding, Placement, Problem, Residence, Voucher, place
from steuerbote.ustva.rounding import (
	CENT,
	HUNDRED,
	ZERO,
	apportion_cents,
	base_from_tax,
	require_decimal,
	tax_from_base,
	to_cents,
	to_full_euros,
)

# Leaves room for books that round a document's tax differently, half to even or per item.
TOLERANCE_PER_VOUCHER = CENT
# How far the tax of the lines that make a derived base may miss the booked tax: a tax rounded per item.
DERIVATION_TOLERANCE = CENT
# The most accounts of a voucher whose sets derive_bases() tries, 4095 sets; a larger voucher takes the tax.
MOST_LINES = 12


class StatutoryTax(StrEnum):
	"""The setting „Steuer zu Umsätzen mit festem Steuersatz“ of the VAT Return Settings, see the module."""

	FROM_BASE = "From the Base in Full Euros"
	AS_BOOKED = "As Booked"


DEFAULT_STATUTORY_TAX = StatutoryTax.FROM_BASE


def require_cents(amount: Decimal) -> Decimal:
	require_decimal(amount)
	if not amount.is_finite() or amount != amount.quantize(CENT):
		raise ValueError(f"ledger amounts must be finite cents, not {amount}")
	return amount


@dataclass(frozen=True, slots=True)
class LedgerLine:
	"""One posting on one account, and the voucher it belongs to if the caller knows it.

	An empty voucher name is refused: it would pass for a document of its own.
	"""

	account_number: str
	debit: Decimal = ZERO
	credit: Decimal = ZERO
	voucher: str | None = None

	def __post_init__(self) -> None:
		if not is_account_number(self.account_number):
			raise ValueError(f"{self.account_number!r} is not an account number")
		require_cents(self.debit)
		require_cents(self.credit)
		if self.voucher is not None and not (isinstance(self.voucher, str) and self.voucher):
			raise ValueError(f"voucher must be a document name or None, not {self.voucher!r}")

	def balance(self, side: Side) -> Decimal:
		return _balance(self.debit, self.credit, side)


def _balance(debit: Decimal, credit: Decimal, side: Side) -> Decimal:
	if side is Side.CREDIT:
		return credit - debit
	return debit - credit


@dataclass(frozen=True, slots=True)
class KennzahlValue:
	"""The exact amount of a Kennzahl and the amount the form takes. ``tax`` is the tax a base at a statutory rate adds
	to the sums, in cents, as the setting StatutoryTax gives it; None for every other Kennzahl."""

	kennzahl: str
	amount: Decimal
	reported: Decimal
	tax: Decimal | None = None


@dataclass(frozen=True, slots=True)
class BookedTax:
	"""The part of the tax a voucher books on the tax accounts of a Verprobung that belongs to a base at a statutory
	rate: ``account`` is the base account, None for a derived base or a tax booked without a base. ``voucher`` is None
	for the lines without voucher."""

	kennzahl: str
	voucher: str | None
	account: str | None
	tax: Decimal


@dataclass(frozen=True, slots=True)
class Deviation:
	"""A voucher whose booked tax differs from the tax on its bases by more than the tolerance.

	``voucher`` is None for the lines that came without a voucher, which are checked as one group.
	"""

	voucher: str | None
	computed_tax: Decimal
	booked_tax: Decimal

	@property
	def difference(self) -> Decimal:
		return self.booked_tax - self.computed_tax


@dataclass(frozen=True, slots=True)
class DerivedBase:
	"""The base of a voucher that books the tax of a Verprobung but nothing on its base accounts.

	``label`` names the Verprobung, ``tax`` the tax the voucher books on its tax accounts, for turnover the part beyond
	the tax of its base accounts, and ``base`` the exact base that goes to ``kennzahl`` at ``rate``. ``accounts`` are the accounts of the voucher whose balances make up the base;
	none when the base was taken from the tax. ``voucher`` is None for the lines without voucher. ``placement`` is the
	decision of residence.place() for a Verprobung with a ``derived_base_eu``, None for every other.
	"""

	label: str
	voucher: str | None
	kennzahl: str
	rate: Decimal
	tax: Decimal
	base: Decimal
	accounts: tuple[str, ...]
	placement: Placement | None = None

	@property
	def from_tax(self) -> bool:
		return not self.accounts


@dataclass(frozen=True, slots=True)
class CheckResult:
	"""Verprobung: the tax booked on the tax accounts against the tax that belongs to the base accounts.

	The check runs per voucher, because that is where the books round the tax: the tax on a voucher's
	exact bases, rounded to cents, against the tax booked in the same voucher. Totals alone would let
	errors in two documents cancel out and would hide a wrong document in a month with many. A voucher
	passes within ``tolerance``. The lines without a voucher may each have been rounded on their own,
	so they pass within ``tolerance`` per posting on the base accounts, at least one ``tolerance``.
	``computed_tax``, ``booked_tax``, ``difference`` and ``postings`` are totals over all vouchers. ``derived`` holds the
	bases derived for vouchers without base account, whose tax counts as computed.
	"""

	label: str
	base_accounts: tuple[str, ...]
	tax_accounts: tuple[str, ...]
	computed_tax: Decimal
	booked_tax: Decimal
	postings: int
	tolerance: Decimal
	deviations: tuple[Deviation, ...]
	derived: tuple[DerivedBase, ...] = ()

	@property
	def derived_base(self) -> Decimal:
		"""The bases derived for vouchers without base account, together."""
		return sum((derived.base for derived in self.derived), ZERO)

	@property
	def difference(self) -> Decimal:
		return self.booked_tax - self.computed_tax

	@property
	def passed(self) -> bool:
		return not self.deviations


@dataclass(frozen=True, slots=True)
class AccountBalance:
	"""The debits and credits of one account in the period."""

	account_number: str
	debit: Decimal
	credit: Decimal

	@property
	def balance(self) -> Decimal:
		"""Debit less credit: positive on the debit side, negative on the credit side."""
		return self.debit - self.credit


@dataclass(frozen=True, slots=True)
class UstvaResult:
	"""The sums follow the form: line 37, lines 38 to 44, lines 46 and 47, Kennzahl 39, Kennzahl 83.

	``unmapped`` names the accounts watched at the blocking level that have a balance, ``hinted`` the
	debits and credits of those watched at the hint level that have one, both by account number. ``findings`` names
	the vouchers of sections C and D a person should look at, see the module.
	"""

	values: ReadOnlyMapping[str, KennzahlValue]
	checks: tuple[CheckResult, ...]
	unmapped: tuple[str, ...]
	output_tax: Decimal
	input_tax: Decimal
	other_tax: Decimal
	sondervorauszahlung: Decimal
	hinted: tuple[AccountBalance, ...] = ()
	findings: tuple[Finding, ...] = ()

	@property
	def remaining_tax(self) -> Decimal:
		"""Line 45: output tax less input tax."""
		return to_cents(self.output_tax - self.input_tax)

	@property
	def prepayment(self) -> Decimal:
		"""Line 48: the Vorauszahlung or Überschuss before the Sondervorauszahlung."""
		return to_cents(self.remaining_tax + self.other_tax)

	@property
	def kz83(self) -> Decimal:
		return self.values[BALANCE_KENNZAHL].reported

	@property
	def derived(self) -> tuple[DerivedBase, ...]:
		"""The derived bases of every Verprobung, in the order of the checks, each in the order of the ledger."""
		return tuple(derived for check in self.checks for derived in check.derived)

	@property
	def derived_bases(self) -> ReadOnlyMapping[str, Decimal]:
		"""The derived bases by the Kennzahl they go to."""
		sums: dict[str, Decimal] = {}
		for derived in self.derived:
			sums[derived.kennzahl] = sums.get(derived.kennzahl, ZERO) + derived.base
		return MappingProxyType(sums)

	@property
	def ready(self) -> bool:
		"""Every Verprobung passes and no account watched at the blocking level has a balance."""
		return not self.unmapped and all(check.passed for check in self.checks)

	def reported(self, kennzahl: str) -> Decimal:
		value = self.values.get(kennzahl)
		return value.reported if value else ZERO


def calculate(
	lines: Iterable[LedgerLine],
	mapping: Mapping,
	extra_values: ReadOnlyMapping[str, Decimal] | None = None,
	tolerance: Decimal = TOLERANCE_PER_VOUCHER,
	vouchers: ReadOnlyMapping[str, Voucher] | None = None,
	statutory_tax: StatutoryTax = DEFAULT_STATUTORY_TAX,
	taxes: ReadOnlyMapping[str, Decimal] | None = None,
) -> UstvaResult:
	"""Aggregate the ledger into Kennzahlen, derive the taxes the form derives, and balance Kennzahl 83.

	``extra_values`` carries amounts that are not booked on a mapped account, such as the
	Sondervorauszahlung in Kennzahl 39. Like booked amounts they may be negative, Kennzahl 39 included:
	the Anleitung to the form (USt 1 E 2026, "So werden die Vordrucke ausgefüllt") says „Kennzeichnen
	Sie negative Beträge durch ein Minuszeichen.“ ``tolerance`` is how far the booked tax of one voucher
	may differ from the tax on its bases, see CheckResult. Amounts are exact; ``reported`` follows the
	rounding rules.

	Derived tax is rounded per voucher, per Kennzahl and per rate. A voucher whose single booked tax
	line covers bases of two Kennzahlen at the same rate, such as 3123 (Kz 46) and 3125 (Kz 84) at
	19 %, can therefore differ from that line by one cent in Kz 47 and 85 together, and Kz 83 keeps the
	cent. The Verprobung rounds all bases of a voucher at once and stays exact; the per-voucher tolerance
	of 0.01 absorbs a booked line that was rounded differently.

	``vouchers`` holds what the caller knows of the vouchers of sections C and D (purchase_vouchers), see the module.

	``statutory_tax`` decides the tax of the bases at a statutory rate, see the module. ``taxes`` gives that tax as
	booked for Kennzahlen of the extra values, as a return keeps it with its amounts as filed; it adds to what the
	ledger books, and a Kennzahl without a booked or given tax takes the tax of its base.
	"""
	tolerance = _require_tolerance(tolerance)
	statutory_tax = StatutoryTax(statutory_tax)
	catalogue = mapping.catalogue
	given = _given_taxes(taxes or {}, catalogue, statutory_tax)
	ledger = _Ledger(lines)
	derived = _derive(ledger, mapping, vouchers)
	amounts = _amounts_by_kennzahl(ledger, mapping, derived)
	_add_extra_values(amounts, extra_values or {}, catalogue)
	booked: dict[str, Decimal] = {}
	if statutory_tax is StatutoryTax.AS_BOOKED:
		for share in _booked(ledger, mapping, derived):
			_add(booked, share.kennzahl, share.tax)
		for number, amount in given.items():
			_add(booked, number, amount)
	values = {
		number: _value(catalogue[number], amounts.get(number, ZERO), booked.get(number))
		for number in dict.fromkeys((*amounts, *booked))
		if amounts.get(number) or booked.get(number)
	}

	output_tax = input_tax = other_tax = sondervorauszahlung = ZERO
	for value in values.values():
		kennzahl = catalogue[value.kennzahl]
		contribution = value.tax if kennzahl.derives_tax else value.reported
		if kennzahl.number == SONDERVORAUSZAHLUNG_KENNZAHL:
			sondervorauszahlung += contribution
		elif kennzahl.effect is Effect.INCREASES and kennzahl.line in OUTPUT_TAX_LINES:
			output_tax += contribution
		elif kennzahl.effect is Effect.REDUCES and kennzahl.line in INPUT_TAX_LINES:
			input_tax += contribution
		elif kennzahl.effect is Effect.INCREASES and kennzahl.line in OTHER_TAX_LINES:
			other_tax += contribution
	balance = to_cents(output_tax - input_tax + other_tax - sondervorauszahlung)
	values[BALANCE_KENNZAHL] = KennzahlValue(BALANCE_KENNZAHL, balance, balance)

	return UstvaResult(
		values=MappingProxyType(values),
		checks=tuple(
			_check(check, mapping, ledger, tolerance, derived.get(check.label, ()))
			for check in mapping.checks
		),
		unmapped=tuple(sorted(a for a in mapping.watched_at(WatchLevel.BLOCKING) if ledger.has_balance(a))),
		output_tax=to_cents(output_tax),
		input_tax=to_cents(input_tax),
		other_tax=to_cents(other_tax),
		sondervorauszahlung=to_cents(sondervorauszahlung),
		hinted=tuple(
			ledger.account_balance(a)
			for a in sorted(mapping.watched_at(WatchLevel.HINT))
			if ledger.has_balance(a)
		),
		findings=() if vouchers is None else _findings(ledger, mapping, derived, vouchers),
	)


def _given_taxes(
	taxes: ReadOnlyMapping[str, Decimal],
	catalogue: ReadOnlyMapping[str, Kennzahl],
	statutory_tax: StatutoryTax,
) -> dict[str, Decimal]:
	if taxes and statutory_tax is not StatutoryTax.AS_BOOKED:
		raise ValueError("the taxes of the bases at a statutory rate are given only as booked")
	for number, amount in taxes.items():
		kennzahl = catalogue.get(number)
		if kennzahl is None or not kennzahl.derives_tax:
			raise ValueError(f"Kennzahl {number} is no base at a statutory rate")
		require_cents(amount)
	return dict(taxes)


def _require_tolerance(tolerance: Decimal) -> Decimal:
	require_decimal(tolerance)
	if not tolerance.is_finite() or tolerance < ZERO:
		raise ValueError(f"tolerance must be a finite amount of at least zero, not {tolerance}")
	return tolerance


@dataclass(frozen=True, slots=True)
class _Total:
	debit: Decimal = ZERO
	credit: Decimal = ZERO
	postings: int = 0

	def plus(self, line: LedgerLine) -> _Total:
		return _Total(self.debit + line.debit, self.credit + line.credit, self.postings + 1)

	def balance(self, side: Side) -> Decimal:
		return _balance(self.debit, self.credit, side)


class _Ledger:
	"""The lines summed per account and voucher; vouchers keep the order of their first line, the accounts of a voucher
	the order of theirs."""

	__slots__ = ("_by_account", "_by_voucher", "_first_line")

	def __init__(self, lines: Iterable[LedgerLine]) -> None:
		self._by_account: dict[str, dict[str | None, _Total]] = {}
		self._by_voucher: dict[str | None, dict[str, None]] = {}
		self._first_line: dict[str | None, int] = {}
		for line in lines:
			vouchers = self._by_account.setdefault(line.account_number, {})
			vouchers[line.voucher] = vouchers.get(line.voucher, _Total()).plus(line)
			self._by_voucher.setdefault(line.voucher, {})[line.account_number] = None
			self._first_line.setdefault(line.voucher, len(self._first_line))

	def accounts_of(self, voucher: str | None) -> Iterable[str]:
		return self._by_voucher.get(voucher, {}).keys()

	@property
	def accounts(self) -> Iterable[str]:
		return self._by_account.keys()

	def vouchers(self, account_number: str) -> ReadOnlyMapping[str | None, _Total]:
		return self._by_account.get(account_number, {})

	def has_balance(self, account_number: str) -> bool:
		return sum((t.balance(Side.DEBIT) for t in self.vouchers(account_number).values()), ZERO) != ZERO

	def account_balance(self, account_number: str) -> AccountBalance:
		totals = self.vouchers(account_number).values()
		return AccountBalance(
			account_number,
			sum((total.debit for total in totals), ZERO),
			sum((total.credit for total in totals), ZERO),
		)

	def first_line(self, voucher: str | None) -> int:
		return self._first_line[voucher]


def derive_bases(
	lines: Iterable[LedgerLine], mapping: Mapping, vouchers: ReadOnlyMapping[str, Voucher] | None = None
) -> tuple[DerivedBase, ...]:
	"""The bases calculate() derives for vouchers that book the tax of a Verprobung but none of its bases, in the order
	of the checks, each in the order of the ledger."""
	derived = _derive(_Ledger(lines), mapping, vouchers)
	return tuple(base for check in mapping.checks for base in derived.get(check.label, ()))


def booked_taxes(
	lines: Iterable[LedgerLine], mapping: Mapping, vouchers: ReadOnlyMapping[str, Voucher] | None = None
) -> tuple[BookedTax, ...]:
	"""The tax of the bases at a statutory rate as booked, see the module: per voucher and base, in the order of the
	checks, each in the order of the ledger, and then the bases outside every Verprobung."""
	ledger = _Ledger(lines)
	return tuple(_booked(ledger, mapping, _derive(ledger, mapping, vouchers)))


@dataclass(frozen=True, slots=True)
class _Part:
	"""A base of a voucher in a Verprobung: on ``account``, or derived without one."""

	account: str | None
	kennzahl: str
	base: Decimal
	rate: Decimal

	@property
	def tax(self) -> Decimal:
		return self.base * self.rate / HUNDRED


def _booked(
	ledger: _Ledger, mapping: Mapping, derived: ReadOnlyMapping[str, tuple[DerivedBase, ...]]
) -> list[BookedTax]:
	catalogue = mapping.catalogue
	found: list[BookedTax] = []
	checked: set[str] = set()
	for check in mapping.checks:
		checked.update(check.base_accounts)
		parts: dict[str | None, list[_Part]] = {}
		for account in check.base_accounts:
			rule = mapping.rule_for(account)
			rate = mapping.rate_for(rule)
			for voucher, total in ledger.vouchers(account).items():
				parts.setdefault(voucher, []).append(
					_Part(account, rule.kennzahl, total.balance(rule.side), rate)
				)
		for base in derived.get(check.label, ()):
			parts.setdefault(base.voucher, []).append(_Part(None, base.kennzahl, base.base, base.rate))
		numbers = (
			*(mapping.rule_for(account).kennzahl for account in check.base_accounts),
			check.derived_base,
		)
		own = next((number for number in numbers if number and catalogue[number].derives_tax), None)
		if own is None:
			continue
		booked: dict[str | None, Decimal] = {}
		for account in check.tax_accounts:
			for voucher, total in ledger.vouchers(account).items():
				_add(booked, voucher, total.balance(check.side))
		for voucher in sorted(parts.keys() | booked.keys(), key=ledger.first_line):
			found.extend(_shares(voucher, parts.get(voucher, []), booked.get(voucher, ZERO), own, catalogue))
	loose: dict[tuple[str, str | None], list[_Part]] = {}
	for account in ledger.accounts:
		rule = mapping.rule_for(account)
		if rule is None or account in checked or not catalogue[rule.kennzahl].derives_tax:
			continue
		rate = mapping.rate_for(rule)
		for voucher, total in ledger.vouchers(account).items():
			loose.setdefault((rule.kennzahl, voucher), []).append(
				_Part(account, rule.kennzahl, total.balance(rule.side), rate)
			)
	for (_kennzahl, voucher), group in loose.items():
		tax = tax_from_base(sum((part.base for part in group), ZERO), group[0].rate)
		found.extend(_split(voucher, group, tax))
	return found


def _shares(
	voucher: str | None,
	parts: list[_Part],
	booked: Decimal,
	own: str,
	catalogue: ReadOnlyMapping[str, Kennzahl],
) -> list[BookedTax]:
	"""The booked tax of one voucher in one Verprobung over its bases at a statutory rate, less the tax its other bases
	report in their own tax Kennzahl, rounded per tax Kennzahl and rate as calculate() rounds it."""
	if not parts:
		return [BookedTax(own, voucher, None, booked)] if booked else []
	statutory = [part for part in parts if catalogue[part.kennzahl].derives_tax]
	if not statutory:
		return []
	others: dict[tuple[str | None, Decimal], Decimal] = {}
	for part in (part for part in parts if not catalogue[part.kennzahl].derives_tax):
		key = (catalogue[part.kennzahl].tax_kennzahl, part.rate)
		others[key] = others.get(key, ZERO) + part.base
	reported = sum((tax_from_base(base, rate) for (_tax, rate), base in others.items()), ZERO)
	return _split(voucher, statutory, booked - reported)


def _split(voucher: str | None, parts: list[_Part], tax: Decimal) -> list[BookedTax]:
	shares = apportion_cents([part.tax for part in parts], tax)
	return [
		BookedTax(part.kennzahl, voucher, part.account, share)
		for part, share in zip(parts, shares, strict=True)
	]


def purchase_vouchers(lines: Iterable[LedgerLine], mapping: Mapping) -> tuple[str, ...]:
	"""The vouchers whose suppliers calculate() asks about: those that post on a base or tax account of a Verprobung of
	sections C and D, in the order of the ledger."""
	ledger = _Ledger(lines)
	accounts = {
		account
		for check in mapping.checks
		if mapping.is_purchase(check)
		for account in (*check.base_accounts, *check.tax_accounts)
	}
	found = {voucher for account in accounts for voucher in ledger.vouchers(account) if voucher is not None}
	return tuple(sorted(found, key=ledger.first_line))


def _derive(
	ledger: _Ledger, mapping: Mapping, vouchers: ReadOnlyMapping[str, Voucher] | None
) -> dict[str, tuple[DerivedBase, ...]]:
	"""The derived bases of each Verprobung with a derived_base, by its label."""
	found: dict[str, tuple[DerivedBase, ...]] = {}
	for check in mapping.checks:
		if check.derived_base is None:
			continue
		if mapping.derives_turnover(check):
			found[check.label] = _turnover(check, ledger, mapping)
			continue
		kennzahl, rate, side = check.derived_base, mapping.derived_rate(check), mapping.base_side(check)
		booked: dict[str | None, Decimal] = {}
		for account_number in check.tax_accounts:
			for voucher, total in ledger.vouchers(account_number).items():
				booked[voucher] = booked.get(voucher, ZERO) + total.balance(check.side)
		with_bases = {voucher for account in check.base_accounts for voucher in ledger.vouchers(account)}
		found[check.label] = tuple(
			_derived(check, kennzahl, voucher, tax, rate, side, ledger, mapping, vouchers)
			for voucher, tax in sorted(booked.items(), key=lambda item: ledger.first_line(item[0]))
			if tax and voucher not in with_bases
		)
	return found


def _turnover(check: TaxCheck, ledger: _Ledger, mapping: Mapping) -> tuple[DerivedBase, ...]:
	"""The bases of the output tax the vouchers book beyond the tax of their base accounts, see the module."""
	rate, side = mapping.derived_rate(check), mapping.base_side(check)
	booked: dict[str | None, Decimal] = {}
	for account_number in check.tax_accounts:
		for voucher, total in ledger.vouchers(account_number).items():
			_add(booked, voucher, total.balance(check.side))
	carried: dict[str | None, Decimal] = {}
	for account_number in check.base_accounts:
		rule = mapping.rule_for(account_number)
		for voucher, total in ledger.vouchers(account_number).items():
			_add(carried, voucher, total.balance(rule.side) * mapping.rate_for(rule) / HUNDRED)
	found: list[DerivedBase] = []
	for voucher in sorted(booked, key=ledger.first_line):
		remaining = booked[voucher] - to_cents(carried.get(voucher, ZERO))
		if voucher is None or remaining <= DERIVATION_TOLERANCE:
			continue
		accounts = _lines_of_the_base(voucher, remaining, rate, side, ledger, mapping)
		if accounts:
			base = sum((ledger.vouchers(account)[voucher].balance(side) for account in accounts), ZERO)
			found.append(
				DerivedBase(check.label, voucher, check.derived_base, rate, remaining, base, accounts)
			)
	return tuple(found)


def _placement(
	check: TaxCheck, voucher: str | None, vouchers: ReadOnlyMapping[str, Voucher] | None
) -> Placement | None:
	"""The decision on a voucher whose base the check may send to its derived_base_eu; None for every other."""
	if check.derived_base_eu is None or vouchers is None:
		return None
	return place(voucher, vouchers.get(voucher))


def _derived(
	check: TaxCheck,
	kennzahl: str,
	voucher: str | None,
	tax: Decimal,
	rate: Decimal,
	side: Side,
	ledger: _Ledger,
	mapping: Mapping,
	vouchers: ReadOnlyMapping[str, Voucher] | None,
) -> DerivedBase:
	accounts = _lines_of_the_base(voucher, tax, rate, side, ledger, mapping)
	if accounts:
		base = sum((ledger.vouchers(account)[voucher].balance(side) for account in accounts), ZERO)
	else:
		base = base_from_tax(tax, rate)
	placement = _placement(check, voucher, vouchers)
	if placement is not None and placement.classification is Classification.EU_SERVICE:
		kennzahl = check.derived_base_eu
	return DerivedBase(check.label, voucher, kennzahl, rate, tax, base, accounts, placement)


def _lines_of_the_base(
	voucher: str | None, tax: Decimal, rate: Decimal, side: Side, ledger: _Ledger, mapping: Mapping
) -> tuple[str, ...]:
	"""The accounts of the voucher whose balances make the base of its tax, or none when the lines do not tell it."""
	if voucher is None:
		return ()
	balances = {
		account: balance
		for account in ledger.accounts_of(voucher)
		if not mapping.has_place(account) and (balance := ledger.vouchers(account)[voucher].balance(side))
	}
	if not balances or len(balances) > MOST_LINES:
		return ()
	closest: Decimal | None = None
	fitting: dict[Decimal, tuple[str, ...]] = {}
	for size in range(1, len(balances) + 1):
		for accounts in combinations(balances, size):
			base = sum((balances[account] for account in accounts), ZERO)
			miss = abs(tax_from_base(base, rate) - tax)
			if miss > DERIVATION_TOLERANCE or (closest is not None and miss > closest):
				continue
			if closest is None or miss < closest:
				closest, fitting = miss, {}
			fitting.setdefault(base, accounts)
	if len(fitting) != 1:
		return ()
	(accounts,) = fitting.values()
	return accounts


def _findings(
	ledger: _Ledger,
	mapping: Mapping,
	derived: ReadOnlyMapping[str, tuple[DerivedBase, ...]],
	vouchers: ReadOnlyMapping[str, Voucher],
) -> tuple[Finding, ...]:
	"""What a person should look at in sections C and D, each finding once, in the order of the checks."""
	found: dict[Finding, None] = {}
	for check in mapping.checks:
		for base in derived.get(check.label, ()):
			if base.placement is not None:
				alternative = (
					check.derived_base if base.kennzahl == check.derived_base_eu else check.derived_base_eu
				)
				for finding in base.placement.findings:
					found[_with_kennzahl(finding, base.kennzahl, alternative)] = None
		if mapping.is_acquisition(check):
			for voucher in _vouchers_of(ledger, (*check.base_accounts, *check.tax_accounts)):
				found.update(dict.fromkeys(_acquisition_findings(voucher, vouchers.get(voucher))))
		if check.derived_base_eu is not None:
			accounts = [
				account
				for account in check.base_accounts
				if mapping.rule_for(account).kennzahl == check.derived_base_eu
			]
			for voucher in _vouchers_of(ledger, accounts):
				placement = place(voucher, vouchers.get(voucher))
				if placement.classification is Classification.OTHER:
					facts = (str(placement.source), str(placement.residence or ""))
					finding = Finding(
						Problem.EU_SERVICE_ACCOUNT_OUTSIDE,
						voucher,
						", ".join(supplier.name for supplier in vouchers[voucher].suppliers),
						facts,
						check.derived_base_eu,
						check.derived_base,
					)
					found[finding] = None
	return tuple(found)


def _with_kennzahl(finding: Finding, kennzahl: str, alternative: str) -> Finding:
	return Finding(finding.problem, finding.voucher, finding.supplier, finding.facts, kennzahl, alternative)


def _vouchers_of(ledger: _Ledger, accounts: Iterable[str]) -> list[str]:
	"""The vouchers that post on the accounts, in the order of the ledger; the lines without voucher name none."""
	found = {voucher for account in accounts for voucher in ledger.vouchers(account) if voucher is not None}
	return sorted(found, key=ledger.first_line)


def _acquisition_findings(voucher: str, facts: Voucher | None) -> list[Finding]:
	"""An innergemeinschaftlicher Erwerb needs goods that come from another member state (§ 1a Absatz 1 Nummer 1
	UStG); a supplier established in the Drittlandsgebiet makes that worth a look."""
	if facts is None:
		return []
	outside = [
		supplier
		for supplier in facts.suppliers
		if place(voucher, Voucher(facts.day, (supplier,))).residence is Residence.THIRD_COUNTRY
	]
	return [
		Finding(
			Problem.ACQUISITION_OUTSIDE_EU,
			voucher,
			supplier.name,
			((supplier.country or supplier.address_country or "").strip(),),
		)
		for supplier in outside
	]


def _amounts_by_kennzahl(
	ledger: _Ledger, mapping: Mapping, derived: ReadOnlyMapping[str, tuple[DerivedBase, ...]]
) -> dict[str, Decimal]:
	amounts: dict[str, Decimal] = {}
	derived_bases: dict[tuple[str, Decimal, str | None], Decimal] = {}
	for account_number in ledger.accounts:
		rule = mapping.rule_for(account_number)
		if rule is None:
			continue
		vouchers = ledger.vouchers(account_number)
		_add(amounts, rule.kennzahl, sum((total.balance(rule.side) for total in vouchers.values()), ZERO))
		if rule.also_kennzahl is not None:
			also = sum((total.balance(rule.also_side) for total in vouchers.values()), ZERO)
			_add(amounts, rule.also_kennzahl, also)
		if rule.tax_rate is not None:
			tax_kennzahl = mapping.catalogue[rule.kennzahl].tax_kennzahl
			for voucher, total in vouchers.items():
				key = (tax_kennzahl, rule.tax_rate, voucher)
				derived_bases[key] = derived_bases.get(key, ZERO) + total.balance(rule.side)
	for bases in derived.values():
		for base in bases:
			_add(amounts, base.kennzahl, base.base)
			tax_kennzahl = mapping.catalogue[base.kennzahl].tax_kennzahl
			if tax_kennzahl is not None:
				key = (tax_kennzahl, base.rate, base.voucher)
				derived_bases[key] = derived_bases.get(key, ZERO) + base.base
	for (tax_kennzahl, rate, _voucher), base in derived_bases.items():
		_add(amounts, tax_kennzahl, tax_from_base(base, rate))
	return amounts


def _add(amounts: dict[str, Decimal], kennzahl: str, amount: Decimal) -> None:
	amounts[kennzahl] = amounts.get(kennzahl, ZERO) + amount


def _add_extra_values(
	amounts: dict[str, Decimal],
	extra_values: ReadOnlyMapping[str, Decimal],
	catalogue: ReadOnlyMapping[str, Kennzahl],
) -> None:
	for number, amount in extra_values.items():
		kennzahl = catalogue.get(number)
		if kennzahl is None:
			raise ValueError(f"unknown Kennzahl {number}")
		if not kennzahl.holds_amount or number == BALANCE_KENNZAHL:
			raise ValueError(f"Kennzahl {number} takes no amount")
		_add(amounts, number, require_cents(amount))


def _value(kennzahl: Kennzahl, amount: Decimal, booked: Decimal | None) -> KennzahlValue:
	"""``booked`` is the tax as booked of a base at a statutory rate, None where it takes the tax of its base."""
	reported = to_full_euros(amount) if kennzahl.kind is Kind.BASE else to_cents(amount)
	tax = None
	if kennzahl.derives_tax:
		tax = to_cents(booked) if booked is not None else tax_from_base(reported, kennzahl.rate)
	return KennzahlValue(kennzahl.number, amount, reported, tax)


@dataclass(slots=True)
class _VoucherSums:
	computed: Decimal = ZERO
	booked: Decimal = ZERO
	postings: int = 0


def _check(
	check: TaxCheck, mapping: Mapping, ledger: _Ledger, tolerance: Decimal, derived: tuple[DerivedBase, ...]
) -> CheckResult:
	sums: dict[str | None, _VoucherSums] = {}
	for base in derived:
		sums.setdefault(base.voucher, _VoucherSums()).computed += base.base * base.rate / HUNDRED
	for account_number in check.base_accounts:
		rule = mapping.rule_for(account_number)
		rate = mapping.rate_for(rule)
		for voucher, total in ledger.vouchers(account_number).items():
			voucher_sums = sums.setdefault(voucher, _VoucherSums())
			voucher_sums.computed += total.balance(rule.side) * rate / HUNDRED
			voucher_sums.postings += total.postings
	for account_number in check.tax_accounts:
		for voucher, total in ledger.vouchers(account_number).items():
			sums.setdefault(voucher, _VoucherSums()).booked += total.balance(check.side)

	computed_total = booked_total = ZERO
	deviations: list[Deviation] = []
	for voucher in sorted(sums, key=ledger.first_line):
		computed, booked = to_cents(sums[voucher].computed), to_cents(sums[voucher].booked)
		allowed = tolerance if voucher is not None else tolerance * max(1, sums[voucher].postings)
		if abs(booked - computed) > allowed:
			deviations.append(Deviation(voucher, computed, booked))
		computed_total += computed
		booked_total += booked
	return CheckResult(
		label=check.label,
		base_accounts=check.base_accounts,
		tax_accounts=check.tax_accounts,
		computed_tax=to_cents(computed_total),
		booked_tax=to_cents(booked_total),
		postings=sum(voucher_sums.postings for voucher_sums in sums.values()),
		tolerance=tolerance,
		deviations=tuple(deviations),
		derived=derived,
	)
