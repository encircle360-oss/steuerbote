"""What the Körperschaftsteuer carries from one year to the next: the Verlustabzug of § 10d EStG (Anlage Verluste),
the Termingeschäfte of § 15 Absatz 4 Satz 3 EStG and the Zuwendungen of § 9 Absatz 1 Nummer 2 KStG (Anlage Z).

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

§ 15 Absatz 4 EStG: losses „dürfen weder mit anderen Einkünften aus Gewerbebetrieb noch mit Einkünften aus anderen
Einkunftsarten ausgeglichen werden; sie dürfen auch nicht nach § 10d abgezogen werden“ (Satz 1), „Die Verluste
mindern jedoch nach Maßgabe des § 10d die Gewinne, die der Steuerpflichtige in dem unmittelbar vorangegangenen und
in den folgenden Wirtschaftsjahren ... erzielt hat oder erzielt“ (Satz 2), and Satz 3: „Die Sätze 1 und 2 gelten
entsprechend für Verluste aus Termingeschäften, durch die der Steuerpflichtige einen Differenzausgleich oder einen
durch den Wert einer veränderlichen Bezugsgröße bestimmten Geldbetrag oder Vorteil erlangt.“ The gains and losses
of the year net within the pool; derivatives() adds a net loss back in Anlage GK line 51 (E8002104, „Dazu: Nicht
ausgleichsfähige Verluste aus Termingeschäften nach § 15 Absatz 4 Satz 3 EStG ...“) and carries it forward, and sets a
net gain against the carry-forward in line 52 (E8002105, „Davon ab: Verrechnung von Gewinnen aus Termingeschäften
des laufenden Jahres mit dem Verlustvortrag ...“), after the rule of § 10d as minimum_taxation() applies it. Both
lines are whole euros without a direction, so half up. Steuerbote does not carry a loss back into the preceding
year's gains from Termingeschäfte; that and hedges of shares (Satz 5) are for the Steuerberatung.

For the Gewerbesteuer § 15 Absatz 4 EStG does not apply (R 7.1 Absatz 3 Satz 1 Nummer 4 with Absatz 4 Satz 3
GewStR 2009): steuerbote.gewst.chain reverses lines 51 and 52.

§ 9 Absatz 1 Nummer 2 Satz 1 KStG makes Zuwendungen deductible „bis zur Höhe von insgesamt a) 20 Prozent des
Einkommens oder b) 4 Promille der Summe der gesamten Umsätze und der im Kalenderjahr aufgewendeten Löhne und
Gehälter“, Einkommen „vor Abzug der in Absatz 1 Nr. 2 bezeichneten Zuwendungen und vor dem Verlustabzug nach § 10d“
(Absatz 2 Satz 1), which is the Summe der Einkünfte of Anlage ZVE line 32; Satz 9: „Abziehbare Zuwendungen, die die
Höchstbeträge nach Satz 1 überschreiten, sind im Rahmen der Höchstbeträge in den folgenden Veranlagungszeiträumen
abzuziehen.“ Anlage Z carries it in whole euros: line 1 (E8009401), the Zuwendungsvortrag of the previous VZ; line 5
(E8005602), the Zuwendungen of the year, Aufrunden of the sum of the receipts (rule 8901012); line 6 (E8009701),
their sum (8900204); line 7 (E8006101), the deductible part, the lower of line 6 and Aufrunden of the higher cap
(8901005, 8901006), which Anlage ZVE line 34 deducts; line 8 (E8010101), the Zuwendungsvortrag left (8900351); line 10
(E8006001), the turnover and wages, which the rules ask for once the Zuwendungen exceed 20 % of a positive Summe der
Einkünfte, or there is none (8900101). Only Zuwendungen for the purposes of §§ 52 to 54 AO with a receipt count;
donations to political parties or without a qualifying recipient are added back but never deducted, so the caller
passes the Zuwendungen of its receipts.

expected_rules() names the rules of Anlage Verluste, Anlage Z and Anlage ZVE that this module computes, with the
limits of the VZ, for the year check (steuerbote.kst.years.RuleExpectation).
"""

from dataclasses import dataclass
from decimal import Decimal

from steuerbote.kst.holdings import Amount
from steuerbote.kst.years import HUNDRED, RuleExpectation, Year, factor, year_of
from steuerbote.ustva.rounding import CENT, EURO, ZERO, ceil_euro, half_up_euro, require_decimal


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


@dataclass(frozen=True, slots=True)
class Derivatives:
	"""The Termingeschäfte of the year: the gains and losses in cents, the carry-forward of the pool at the end of the
	previous VZ and at the end of this one in whole euros, and the lines 51 (``added_back``) and 52 (``offset``)."""

	gains: Decimal
	losses: Decimal
	carry_forward: Decimal
	added_back: Amount
	offset: Amount
	remaining: Decimal

	@property
	def net(self) -> Decimal:
		return self.gains - self.losses


def derivatives(year: Year, gains: Decimal, losses: Decimal, carry_forward: Decimal) -> Derivatives:
	"""The pool of § 15 Absatz 4 Satz 3 EStG from the categories derivatives_gain and derivatives_loss."""
	for amount, what in ((gains, "the gains"), (losses, "the losses")):
		if not require_decimal(amount).is_finite() or amount != amount.quantize(CENT) or amount < ZERO:
			raise ValueError(
				f"{what} from Termingeschäfte must be an amount in cents of at least 0, not {amount}"
			)
	_require_euros(carry_forward, "the Verlustvortrag of § 15 Absatz 4 EStG")
	net = gains - losses
	if net < ZERO:
		added_back = Amount(-net, half_up_euro(-net))
		return Derivatives(
			gains, losses, carry_forward, added_back, _NONE, carry_forward + added_back.declared
		)
	first, limited = minimum_taxation(half_up_euro(net), carry_forward, year.loss_unlimited, year.loss_share)
	offset = Amount(first + limited, first + limited)
	return Derivatives(gains, losses, carry_forward, _NONE, offset, carry_forward - offset.declared)


_NONE = Amount(ZERO, ZERO)
PER_MILLE = Decimal("1000")


@dataclass(frozen=True, slots=True)
class Donations:
	"""Anlage Z: the Zuwendungsvortrag of the previous VZ (line 1), the Zuwendungen of the year (line 5), the turnover
	and wages (line 10, None while unknown) and the deductible part (line 7). ``turnover_missing`` says that the
	rules need line 10 and it is unknown."""

	carry_forward: Decimal
	donations: Amount
	turnover_and_wages: Decimal | None
	deductible: Decimal
	turnover_missing: bool

	@property
	def available(self) -> Decimal:
		"""Line 6: the Zuwendungsvortrag and the Zuwendungen of the year."""
		return self.carry_forward + self.donations.declared

	@property
	def remaining(self) -> Decimal:
		"""Line 8: the Zuwendungsvortrag at the end of the VZ."""
		return self.available - self.deductible

	@property
	def required(self) -> bool:
		"""Anlage Z is filed with Zuwendungen or a Zuwendungsvortrag."""
		return self.available > ZERO


def donations(
	year: Year,
	sum_of_income: Decimal,
	eligible: Decimal,
	carry_forward: Decimal,
	turnover_and_wages: Decimal | None = None,
) -> Donations:
	"""Anlage Z from the Summe der Einkünfte (Anlage ZVE line 32), the Zuwendungen of the receipts in cents, the
	Zuwendungsvortrag and the turnover and wages, all but the Zuwendungen in whole euros."""
	_require_euros(sum_of_income, "the Summe der Einkünfte", negative=True)
	if not require_decimal(eligible).is_finite() or eligible != eligible.quantize(CENT) or eligible < ZERO:
		raise ValueError(f"the Zuwendungen must be an amount in cents of at least 0, not {eligible}")
	_require_euros(carry_forward, "the Zuwendungsvortrag")
	if turnover_and_wages is not None:
		_require_euros(turnover_and_wages, "the Umsätze, Löhne und Gehälter")
	line_5 = Amount(eligible, ceil_euro(eligible))
	available = carry_forward + line_5.declared
	income_cap = sum_of_income * year.donation_income_percent / HUNDRED
	turnover_cap = (turnover_and_wages or ZERO) * year.donation_turnover_per_mille / PER_MILLE
	deductible = max(min(available, ceil_euro(max(income_cap, turnover_cap))), ZERO)
	missing = (
		turnover_and_wages is None
		and available > ZERO
		and (sum_of_income <= ZERO or available > ceil_euro(income_cap))
	)
	return Donations(carry_forward, line_5, turnover_and_wages, deductible, missing)


def _require_euros(amount: Decimal, what: str, negative: bool = False) -> None:
	if (
		not require_decimal(amount).is_finite()
		or amount != amount.quantize(EURO)
		or (amount < ZERO and not negative)
	):
		bound = "" if negative else " of at least 0"
		raise ValueError(f"{what} must be whole euros{bound}, not {amount}")


def expected_rules(year: int) -> tuple[RuleExpectation, ...]:
	"""The rules of the Jahresdokumentation E30 that loss_deduction() and donations() compute."""
	data = year_of(year)
	income = factor(data.donation_income_percent)
	turnover = factor(data.donation_turnover_per_mille / 10)
	return (
		RuleExpectation("8900184", "Verluste", ("[E8008601]!=Min(", f",{data.loss_unlimited})")),
		RuleExpectation(
			"8900170",
			"Verluste",
			(f"Aufrunden({{[E8008501]-[E8008502]-[E8008601]}}*{factor(data.loss_share)}))",),
		),
		RuleExpectation(
			"8900347",
			"Verluste",
			("[E8009201]!=[E8007801]", "+[E8008001]", "-[E8008102]", "-[E8008602]", "-[E8008801]"),
		),
		RuleExpectation("8900342", "Verluste", ("[E8008401]!=[E8007801]", "+[E8008001]", "-[E8008102]")),
		RuleExpectation("8900124", "Verluste", (f"Min({data.loss_carry_back},[E8008001]",)),
		RuleExpectation("8900114", "ZVE", ("[E8007001]!=Summe(E8008601,E8008801",)),
		RuleExpectation("8900204", "Z", ("[E8009701]!={[E8009401]", "+[E8005602]")),
		RuleExpectation("8901012", "Z", ("[E8005602]!=Aufrunden(Summe(", "E8005604))")),
		RuleExpectation("8901005", "Z", (f"Min(Aufrunden({{[E8005401]*{income}}})",)),
		RuleExpectation("8901006", "Z", (f"Min(Aufrunden({{Summe(E8006001,E8001101)*{turnover}}})",)),
		RuleExpectation("8900351", "Z", ("[E8010101]!=[E8009401]", "+[E8005602]", "-[E8006101]")),
		RuleExpectation("8900101", "Z", (f"Aufrunden({{[E8005401]*{income}",)),
	)
