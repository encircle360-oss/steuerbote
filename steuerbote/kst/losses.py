"""What the Körperschaftsteuer carries from one year to the next: the Verlustabzug of § 10d EStG (Anlage Verluste).

§ 10d EStG (Stand Art. 1 G v. 15.10.2026 I Nr. 307), which § 8 Absatz 1 KStG applies:
- Absatz 1 Satz 1: „Negative Einkünfte, die bei der Ermittlung des Gesamtbetrags der Einkünfte nicht ausgeglichen
  werden, sind bis zu einem Betrag von 1 000 000 Euro ... vom Gesamtbetrag der Einkünfte des unmittelbar
  vorangegangenen Veranlagungszeitraums ... abzuziehen (Verlustrücktrag)“; Satz 2 goes on to the second preceding
  VZ, and Satz 6: „Auf Antrag des Steuerpflichtigen ist von der Anwendung des Verlustrücktrags nach den Sätzen 1 und
  2 insgesamt abzusehen.“
- Absatz 2 Satz 1: „Nicht ausgeglichene negative Einkünfte, die nicht nach Absatz 1 abgezogen worden sind, sind in
  den folgenden Veranlagungszeiträumen bis zu einem Gesamtbetrag der Einkünfte von 1 Million Euro unbeschränkt,
  darüber hinaus bis zu 70 Prozent des 1 Million Euro übersteigenden Gesamtbetrags der Einkünfte ... abzuziehen
  (Verlustvortrag).“

Anlage Verluste of Jahresdokumentation_E30_2025.ods (ERiC documentation 44.3.6.0) carries the computation in whole
euros, and the rules check it:
- line 11 (E8007801), the Verlustvortrag at the end of the previous VZ, from the last Feststellungsbescheid;
- line 19 (E8008001), the negative Gesamtbetrag der Einkünfte as a positive amount (rule 8900152); line 20
  (E8008102), the Verlustrücktrag „höchstens 1 Million €; bei Verzicht auf den Verlustrücktrag: Eintrag mit 0“, which
  line 19 needs (8900343) and which is no more than the loss and 1 Million Euro (8900124); line 21 (E8008401) is
  line 11 plus line 19 less line 20 (8900342);
- line 22 (E8008501), the positive Gesamtbetrag der Einkünfte (8900129, 8900132); line 25 (E8008601), „Niedrigerer
  Betrag aus Zeile 21 und 24, höchstens 1 Million €“ (8900184); line 26 (E8008701), line 22 less line 25 while both
  the income and the Verlustvortrag have something left (8900141, 8918405, 8918422); line 27 (E8008801), the
  Verlustvortrag left, at most Aufrunden(line 26 * 0.7) (8900170); line 28 (E8009201), the Verlustvortrag at the end
  of the VZ (8900347);
- Anlage ZVE line 56 (E8007001) deducts lines 25 and 27 (8900114).

Steuerbote leaves out what a GmbH of its scope has no use for: the lines of § 8c and § 8d KStG (13 to 16, 29 to
37), of mergers and splits (14a, 16, 23) and of a Sanierungsertrag (18, 19a, 19b). The amount of a Verlustrücktrag
is the company's choice, so the caller passes it; Steuerbote computes neither the income of the preceding years nor
the best split.

The 70 % share is that of the VZ (steuerbote.kst.years), the 1 Million Euro is ``Year.loss_unlimited``.
minimum_taxation() is the rule of both, which § 15 Absatz 4 Satz 2 EStG and § 10a GewStG apply in their own way.
"""

from dataclasses import dataclass
from decimal import Decimal

from steuerbote.kst.years import HUNDRED, Year
from steuerbote.ustva.rounding import EURO, ZERO, ceil_euro, require_decimal


def minimum_taxation(
	amount: Decimal, carry_forward: Decimal, unlimited: Decimal, share: Decimal
) -> tuple[Decimal, Decimal]:
	"""How much of a carry-forward an amount absorbs: the part up to ``unlimited`` in full, then ``share`` percent of
	the amount beyond it, rounded up to full euros as rule 8900170 rounds it. Gives the two parts, each 0 when there
	is nothing to absorb."""
	if amount <= ZERO or carry_forward <= ZERO:
		return ZERO, ZERO
	first = min(carry_forward, amount, unlimited)
	rest = amount - first
	if rest <= ZERO or carry_forward <= first:
		return first, ZERO
	return first, min(carry_forward - first, ceil_euro(rest * share / HUNDRED))


@dataclass(frozen=True, slots=True)
class LossDeduction:
	"""The lines of Anlage Verluste. ``carry_back`` is None when the VZ has a loss and no Verlustrücktrag was chosen,
	which the filing has to settle (``carry_back_missing``); without a loss it is 0."""

	carry_forward: Decimal
	loss: Decimal
	carry_back: Decimal | None
	subtotal: Decimal
	total_income: Decimal
	unlimited: Decimal
	rest: Decimal
	limited: Decimal
	remaining: Decimal
	carry_back_too_high: bool

	@property
	def deduction(self) -> Decimal:
		"""Anlage ZVE line 56: the lines 25 and 27."""
		return self.unlimited + self.limited

	@property
	def carry_back_missing(self) -> bool:
		return self.carry_back is None

	@property
	def required(self) -> bool:
		"""Anlage Verluste is filed with a Verlustvortrag or a loss."""
		return self.carry_forward > ZERO or self.loss > ZERO


def loss_deduction(
	year: Year, total_income: Decimal, carry_forward: Decimal, carry_back: Decimal | None = None
) -> LossDeduction:
	"""Anlage Verluste from the Gesamtbetrag der Einkünfte (Anlage ZVE line 53), the Verlustvortrag at the end of the
	previous VZ and, with a loss, the Verlustrücktrag chosen; all in whole euros."""
	_require_euros(total_income, "the Gesamtbetrag der Einkünfte", negative=True)
	_require_euros(carry_forward, "the Verlustvortrag")
	if carry_back is not None:
		_require_euros(carry_back, "the Verlustrücktrag")
	if total_income < ZERO:
		loss = -total_income
		subtotal = carry_forward + loss - (carry_back or ZERO)
		too_high = carry_back is not None and carry_back > min(year.loss_carry_back, loss)
		return LossDeduction(
			carry_forward, loss, carry_back, subtotal, ZERO, ZERO, ZERO, ZERO, subtotal, too_high
		)
	if carry_back:
		raise ValueError(f"a Verlustrücktrag needs a loss; the Gesamtbetrag der Einkünfte is {total_income}")
	unlimited, limited = minimum_taxation(total_income, carry_forward, year.loss_unlimited, year.loss_share)
	rest = total_income - unlimited if limited else ZERO
	return LossDeduction(
		carry_forward,
		ZERO,
		ZERO,
		carry_forward,
		total_income,
		unlimited,
		rest,
		limited,
		carry_forward - unlimited - limited,
		False,
	)


def _require_euros(amount: Decimal, what: str, negative: bool = False) -> None:
	if (
		not require_decimal(amount).is_finite()
		or amount != amount.quantize(EURO)
		or (amount < ZERO and not negative)
	):
		bound = "" if negative else " of at least 0"
		raise ValueError(f"{what} must be whole euros{bound}, not {amount}")
