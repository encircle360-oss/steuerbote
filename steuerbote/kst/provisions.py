"""The provisions for Körperschaftsteuer, Solidaritätszuschlag and Gewerbesteuer that Steuerbote proposes: the rows
of a draft Journal Entry, never a posting.

The balance of each tax at the end of the Wirtschaftsjahr is the tax less the credits and the Vorauszahlungen
(steuerbote.kst.chain, steuerbote.gewst.chain). A balance due is an ungewisse Verbindlichkeit, for which § 249
Absatz 1 Satz 1 HGB requires a Rückstellung; a balance below 0 is a claim to a refund. Posting is the company's act:
it changes the books behind the E-Bilanz and the filed returns, so the Frappe layer makes these rows a Journal Entry
that the user checks and submits. Every tax on income is added back in Anlage GK lines 81 to 84, so the posted
provisions change the Jahresüberschuss but not the zu versteuerndes Einkommen.

The Solidaritätszuschlag goes to the provision of the Körperschaftsteuer, as the DATEV charts have no Rückstellung
of its own for it. The accounts of the DATEV charts „Gültig für 2026“ (Art.-Nr. 11174 and 11175):

| Tax | SKR03 expense, provision, refund | SKR04 expense, provision, refund |
|---|---|---|
| Körperschaftsteuer | 2200, 0963 „Körperschaftsteuerrückstellung“, 1549 „Körperschaftsteuerrückforderung“ | 7600, 3040, 1450 |
| Solidaritätszuschlag | 2208, 0963, 1549 | 7608, 3040, 1450 |
| Gewerbesteuer | 4320, 0956 „Gewerbesteuerrückstellung nach § 4 Abs. 5b EStG“, 1540 „Forderungen aus Gewerbesteuerüberzahlungen“ | 7610, 3035, 1435 |

A company with a chart of its own passes its ProvisionAccounts. The rows are for the whole balance of the year, and
posting them does not change it. A posting after the provisions changes the balances, while the provisions in the
books stay; § 249 Abs. 1 Satz 1 HGB asks for them in full, so propose() takes what the books hold of each tax, its
provision as a positive amount and its claim to a refund as a negative one, and proposes the difference
(differences()): more provision, a provision released, a claim posted or reduced, each an „Anpassung“.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from steuerbote.gewst.chain import GewstResult
from steuerbote.kst.chain import KstResult
from steuerbote.ustva.mapping import MappingError, is_account_number
from steuerbote.ustva.rounding import CENT, ZERO, require_decimal


class Tax(StrEnum):
	KST = "Körperschaftsteuer"
	SOLZ = "Solidaritätszuschlag"
	GEWST = "Gewerbesteuer"


@dataclass(frozen=True, slots=True)
class TaxAccounts:
	"""The accounts of one tax: its expense, its Rückstellung and the claim to a refund."""

	expense: str
	provision: str
	refund: str

	def __post_init__(self) -> None:
		for account in (self.expense, self.provision, self.refund):
			if not is_account_number(account):
				raise MappingError(f"{account!r} is not an account number")


@dataclass(frozen=True, slots=True)
class ProvisionAccounts:
	kst: TaxAccounts
	solz: TaxAccounts
	gewst: TaxAccounts


ACCOUNTS: MappingProxyType[str, ProvisionAccounts] = MappingProxyType(
	{
		"SKR03": ProvisionAccounts(
			TaxAccounts("2200", "0963", "1549"),
			TaxAccounts("2208", "0963", "1549"),
			TaxAccounts("4320", "0956", "1540"),
		),
		"SKR04": ProvisionAccounts(
			TaxAccounts("7600", "3040", "1450"),
			TaxAccounts("7608", "3040", "1450"),
			TaxAccounts("7610", "3035", "1435"),
		),
	}
)


@dataclass(frozen=True, slots=True)
class ProvisionRow:
	"""One debit and one credit of the same positive amount for the tax of a year; ``refund`` marks a claim."""

	tax: Tax
	amount: Decimal
	debit_account: str
	credit_account: str
	year: int
	refund: bool = False
	adjustment: bool = False

	def __post_init__(self) -> None:
		if (
			not require_decimal(self.amount).is_finite()
			or self.amount != self.amount.quantize(CENT)
			or self.amount <= ZERO
		):
			raise ValueError(f"{self.tax}: a row needs a positive amount in cents, not {self.amount}")

	@property
	def remark(self) -> str:
		"""The text of the row, as the Journal Entry shows it."""
		what = "Erstattungsanspruch" if self.refund else "Rückstellung"
		return f"{'Anpassung ' if self.adjustment else ''}{what} {self.tax} {self.year}"


def balances(kst: KstResult, gewst: GewstResult | None) -> dict[Tax, Decimal]:
	"""The balance of each tax of the year; without ``gewst`` the Körperschaftsteuer and the Solidaritätszuschlag."""
	found = {Tax.KST: kst.kst_balance, Tax.SOLZ: kst.solz_balance}
	if gewst is not None:
		if gewst.hebesatz is None:
			raise ValueError("the Gewerbesteuer has no Hebesatz, so it has no balance to provide for")
		found[Tax.GEWST] = gewst.balance
	return found


def differences(
	kst: KstResult, gewst: GewstResult | None, posted: Mapping[Tax, Decimal]
) -> dict[Tax, Decimal]:
	"""Each tax whose balance is not what the books hold of it, with the balance less the posted amount."""
	found = {tax: balance - posted.get(tax, ZERO) for tax, balance in balances(kst, gewst).items()}
	return {tax: difference for tax, difference in found.items() if difference}


def propose(
	kst: KstResult,
	gewst: GewstResult | None,
	accounts: ProvisionAccounts,
	posted: Mapping[Tax, Decimal] = MappingProxyType({}),
) -> tuple[ProvisionRow, ...]:
	"""The rows that bring the books to the balances of the year, from what they hold of each tax in ``posted``; a tax
	without a difference has none. Without ``gewst`` only the Körperschaftsteuer and the Solidaritätszuschlag are
	proposed."""
	year = kst.year.year
	taxed_by = {Tax.KST: accounts.kst, Tax.SOLZ: accounts.solz, Tax.GEWST: accounts.gewst}
	rows = []
	for tax, balance in balances(kst, gewst).items():
		taxed, before = taxed_by[tax], posted.get(tax, ZERO)
		adjustment = bool(before)
		provision = max(balance, ZERO) - max(before, ZERO)
		claim = max(-balance, ZERO) - max(-before, ZERO)
		if provision > ZERO:
			rows.append(ProvisionRow(tax, provision, taxed.expense, taxed.provision, year, False, adjustment))
		elif provision < ZERO:
			rows.append(
				ProvisionRow(tax, -provision, taxed.provision, taxed.expense, year, False, adjustment)
			)
		if claim > ZERO:
			rows.append(ProvisionRow(tax, claim, taxed.refund, taxed.expense, year, True, adjustment))
		elif claim < ZERO:
			rows.append(ProvisionRow(tax, -claim, taxed.expense, taxed.refund, year, True, adjustment))
	return tuple(rows)
