"""The Zusammenfassende Meldung against the Voranmeldung: ΣL = Kz 41, ΣD = Kz 42 and ΣS = Kz 21.

The ZM and the Voranmeldung report the same turnover: the ZM per Erwerber (§ 18a Absatz 7 UStG), the Voranmeldung
in Kz 41, 42 and 21 (§ 18b UStG; form USt 1 A 2026, lines 19, 33 and 35, whose Anleitung says of lines 19 and 35
„übermitteln Sie bitte Zusammenfassende Meldungen an das Bundeszentralamt für Steuern“). Both take the same
period for each kind of turnover (§ 18a Absatz 8 and § 18b Satz 2 and 3 UStG) and § 17 UStG alike (§ 18a Absatz 7
Satz 2, § 18b Satz 4 UStG). The BZSt compares them: „Nach Eingang der ZM beim BZSt erfolgt ein Abgleich der
gemeldeten innergemeinschaftlichen Umsatzarten mit den Angaben in den Umsatzsteuer-Voranmeldungen und
-Jahreserklärungen“ (BZSt, „Berichtigung einer ZM“).

Two checks, over the same months, those of Coverage in steuerbote.zm.rhythm: the goods months for Kz 41 and 42,
the services months for Kz 21.

1. The exact amounts of the vouchers in the lines against those the ledger gives each Kennzahl, voucher by voucher.
   They agree unless a voucher is missing on one side or carries another amount; such a voucher is named and holds
   the ZM back.
2. The Meldezeilen against the Kennzahlen of the Voranmeldungen filed for these months. Each line and each
   Voranmeldung drops less than a euro (steuerbote.zm.lines, rounding.to_full_euros), so they part by less than
   one euro per line of the Art and per Voranmeldung. A larger difference, such as one from an override, gets a
   hint and holds nothing back.
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import ZERO
from steuerbote.zm.errors import ZmError
from steuerbote.zm.findings import Code, Finding, voucher_no
from steuerbote.zm.lines import ART_KENNZAHL, ART_ORDER, KENNZAHL_ART, Art, Statement, require_whole_euros

NO_RETURN = "Kennzahlen of filed Voranmeldungen come from at least one Voranmeldung, not from {0}."


class Share(Protocol):
	"""What one voucher adds to one Kennzahl, as Contribution of the report „UStVA Kennzahlen“ gives it."""

	@property
	def voucher(self) -> str | None: ...

	@property
	def kennzahl(self) -> str: ...

	@property
	def amount(self) -> Decimal: ...


@dataclass(frozen=True, slots=True)
class Filed:
	"""A Kennzahl as the filed Voranmeldungen of the months report it: the sum of their amounts in whole euros,
	and how many Voranmeldungen these are."""

	amount: Decimal
	returns: int

	def __post_init__(self) -> None:
		require_whole_euros(self.amount)
		if not isinstance(self.returns, int) or isinstance(self.returns, bool) or self.returns < 1:
			raise ZmError(NO_RETURN, self.returns)


@dataclass(frozen=True, slots=True)
class VoucherDifference:
	voucher: str | None
	ledger: Decimal
	statement: Decimal

	@property
	def difference(self) -> Decimal:
		return self.statement - self.ledger


@dataclass(frozen=True, slots=True)
class Reconciled:
	"""One Art against its Kennzahl.

	``ledger`` is the exact amount of the Kennzahl, ``statement`` the exact sum of the lines of the Art,
	``reported`` the sum of their Meldezeilen and ``filed`` the Kennzahl of the filed Voranmeldungen, None when
	the caller has none.
	"""

	art: Art
	ledger: Decimal
	statement: Decimal
	reported: Decimal
	filed: Decimal | None
	differences: tuple[VoucherDifference, ...]

	@property
	def kennzahl(self) -> str:
		return ART_KENNZAHL[self.art]

	@property
	def difference(self) -> Decimal:
		return self.statement - self.ledger


@dataclass(frozen=True, slots=True)
class Reconciliation:
	rows: tuple[Reconciled, ...]
	findings: tuple[Finding, ...]

	@property
	def balanced(self) -> bool:
		"""Every voucher of Kz 41, 42 and 21 is in the lines with its amount, and nothing else is."""
		return not any(row.differences for row in self.rows)


def reconcile(
	statement: Statement,
	ledger: Iterable[Share],
	figures: Figures,
	filed: ReadOnlyMapping[str, Filed] | None = None,
) -> Reconciliation:
	"""Reconcile the lines with what the ledger gives Kz 41, 42 and 21 over the same months, and with the
	Kennzahlen of the filed Voranmeldungen in ``filed``, keyed by Kennzahl; shares of other Kennzahlen are left
	out."""
	booked: dict[Art, dict[str | None, Decimal]] = {art: {} for art in ART_ORDER}
	for item in ledger:
		art = KENNZAHL_ART.get(item.kennzahl)
		if art is not None:
			booked[art][item.voucher] = booked[art].get(item.voucher, ZERO) + item.amount
	in_lines: dict[Art, dict[str | None, Decimal]] = {art: {} for art in ART_ORDER}
	for line in statement.lines:
		for voucher_amount in line.vouchers:
			vouchers = in_lines[line.art]
			vouchers[voucher_amount.voucher] = (
				vouchers.get(voucher_amount.voucher, ZERO) + voucher_amount.amount
			)
	rows: list[Reconciled] = []
	findings: list[Finding] = []
	for art in ART_ORDER:
		returns = (filed or {}).get(ART_KENNZAHL[art])
		row = _row(art, statement, booked[art], in_lines[art], returns)
		rows.append(row)
		findings.extend(_ledger_finding(row.kennzahl, difference, figures) for difference in row.differences)
		if returns is not None and abs(row.reported - returns.amount) >= _tolerance(statement, art, returns):
			text = (
				f"Die abgegebenen Voranmeldungen melden in Kz {row.kennzahl} {figures.money(returns.amount)}, die "
				f"Zeilen {art.value} der ZM {figures.money(row.reported)}."
			)
			findings.append(Finding(Code.FILED_RETURNS, text))
	return Reconciliation(tuple(rows), tuple(findings))


def _row(
	art: Art,
	statement: Statement,
	booked: dict[str | None, Decimal],
	in_lines: dict[str | None, Decimal],
	filed: Filed | None,
) -> Reconciled:
	differences = tuple(
		VoucherDifference(voucher, booked.get(voucher, ZERO), in_lines.get(voucher, ZERO))
		for voucher in [*booked, *(voucher for voucher in in_lines if voucher not in booked)]
		if booked.get(voucher, ZERO) != in_lines.get(voucher, ZERO)
	)
	return Reconciled(
		art=art,
		ledger=sum(booked.values(), ZERO),
		statement=sum(in_lines.values(), ZERO),
		reported=sum((line.amount for line in statement.meldezeilen if line.art is art), ZERO),
		filed=filed.amount if filed else None,
		differences=differences,
	)


def _tolerance(statement: Statement, art: Art, returns: Filed) -> int:
	"""A difference of this many euros or more is no rounding: each line of the Art and each Voranmeldung drops
	less than one euro."""
	return sum(1 for line in statement.lines if line.art is art and line.valid) + returns.returns


def _ledger_finding(kennzahl: str, difference: VoucherDifference, figures: Figures) -> Finding:
	subject = (
		f"Beleg {voucher_no(difference.voucher)} geht" if difference.voucher else "Buchungen ohne Beleg gehen"
	)
	text = (
		f"{subject} laut Hauptbuch mit {figures.money(difference.ledger)} in Kz {kennzahl} ein, in die ZM mit "
		f"{figures.money(difference.statement)}."
	)
	return Finding(Code.LEDGER, text, difference.voucher)
