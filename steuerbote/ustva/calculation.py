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

The tax of the bases with a statutory rate (Kennzahl 81, 86, 89 and 93) is not summed from the
ledger at all: the form derives it from the reported base in full euros.

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

A balance on a watched account never enters a Kennzahl. At the blocking level it holds the return
(``unmapped``); at the hint level the result carries the account's debits and credits (``hinted``) for a
hint, and the return stays ready.
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from decimal import Decimal
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
	kennzahl: str
	amount: Decimal
	reported: Decimal


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

	``label`` names the Verprobung, ``tax`` the tax the voucher books on its tax accounts and ``base`` the exact base
	that goes to ``kennzahl`` at ``rate``. ``accounts`` are the accounts of the voucher whose balances make up the base;
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
	"""
	tolerance = _require_tolerance(tolerance)
	catalogue = mapping.catalogue
	ledger = _Ledger(lines)
	derived = _derive(ledger, mapping, vouchers)
	amounts = _amounts_by_kennzahl(ledger, mapping, derived)
	_add_extra_values(amounts, extra_values or {}, catalogue)
	values = {number: _value(catalogue[number], amount) for number, amount in amounts.items() if amount}

	output_tax = input_tax = other_tax = sondervorauszahlung = ZERO
	for value in values.values():
		kennzahl = catalogue[value.kennzahl]
		contribution = _contribution(kennzahl, value)
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


def _value(kennzahl: Kennzahl, amount: Decimal) -> KennzahlValue:
	reported = to_full_euros(amount) if kennzahl.kind is Kind.BASE else to_cents(amount)
	return KennzahlValue(kennzahl.number, amount, reported)


def _contribution(kennzahl: Kennzahl, value: KennzahlValue) -> Decimal:
	if kennzahl.derives_tax:
		return tax_from_base(value.reported, kennzahl.rate)
	return value.reported


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
