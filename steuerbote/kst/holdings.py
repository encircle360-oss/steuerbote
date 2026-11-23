"""§ 8b KStG per holding: which dividends are exempt, and the lines 156 to 201 of Anlage GK.

§ 8b KStG (zuletzt geändert durch Art. 30 G v. 4.2.2026 I Nr. 33):
- Absatz 1 Satz 1: „Bezüge im Sinne des § 20 Abs. 1 Nr. 1, 2, 9 und 10 Buchstabe a des Einkommensteuergesetzes
  bleiben bei der Ermittlung des Einkommens außer Ansatz.“
- Absatz 4 Satz 1: they count „wenn die Beteiligung zu Beginn des Kalenderjahres unmittelbar weniger als 10 Prozent
  des Grund- oder Stammkapitals betragen hat“ (Streubesitz); Satz 6: „Für Zwecke dieses Absatzes gilt der Erwerb
  einer Beteiligung von mindestens 10 Prozent als zu Beginn des Kalenderjahres erfolgt“; Satz 7: the 5 % of Absatz 5
  do not apply to them.
- Absatz 5 Satz 1: „Von den Bezügen im Sinne des Absatzes 1, die bei der Ermittlung des Einkommens außer Ansatz
  bleiben, gelten 5 Prozent als Ausgaben, die nicht als Betriebsausgaben abgezogen werden dürfen.“
- Absatz 2: gains on the sale of shares „bleiben ... außer Ansatz“; the gain is the price „nach Abzug der
  Veräußerungskosten“ less the book value (Satz 2); the same holds for the gain „aus dem Ansatz des in § 6 Absatz 1
  Nummer 2 Satz 3 des Einkommensteuergesetzes bezeichneten Werts“, the Wertaufholung (Satz 3).
- Absatz 3 Satz 1: of these gains „gelten 5 Prozent als Ausgaben, die nicht als Betriebsausgaben abgezogen werden
  dürfen“; Satz 3: „Gewinnminderungen, die im Zusammenhang mit dem in Absatz 2 genannten Anteil entstehen, sind bei
  der Ermittlung des Einkommens nicht zu berücksichtigen“, so losses on sales and Teilwertabschreibungen are added
  back in full.
- Absatz 7: none of this applies to the trading book of credit and financial institutions and to the shares of
  Finanzunternehmen held to more than 50 % by them. Whether that is the case is a question for the Steuerberatung;
  Steuerbote applies Absatz 7 only when the settings say so (``trading_book``), and then taxes every dividend, gain
  and loss as any other income.

The holdings register of the settings names each holding (Holding) with its share at the start of the calendar year
and, for the Gewerbesteuer, at the start of the Erhebungszeitraum; a HoldingResult holds the dividends (Bezüge) a
holding paid in the Wirtschaftsjahr and the costs related to them (Anlage BEG lines 6, 8 and 9). Dividends that no
holding of the register accounts for count as Streubesitz: Steuerbote exempts a dividend only for a holding the
register shows (``unassigned_dividends``). The gains, losses, write-downs and write-ups come from the categories of
the Income Tax Mapping; Absatz 4 makes no difference for them.

p8b() gives the lines of Anlage GK with the rounding of Jahresdokumentation_E30_2025.ods (ERiC documentation
44.3.6.0), which rounds each line in the taxpayer's favour:
- line 156 (E8560401), the exempt dividends: „Aufrunden(Summe(... E8560404))“ (rule 8956007);
- line 160 (E8560801), their 5 %: „Abrunden([E8560401] * 0.05)“ (8956020);
- line 166b (E8561212), the exempt gains: „Aufrunden(Summe(... E8561211))“ (8956040);
- line 166c (E8561410), the losses: „Abrunden(Summe(... E8561403))“ (8956044);
- line 176 (E8561220), the write-ups: „Aufrunden(Summe(... E8561210))“ (8905506);
- line 181 (E8561301), the 5 % of the gains: „Abrunden(Summe(E8561212, E8561220, E8561237) * 0.05)“ (8956042);
- line 188 (E8561411), the write-downs, whole euros without a direction, so half up (steuerbote.ustva.rounding);
- line 201 (E8562101), the correction: lines 160, 166c, 181 and 188 less lines 156, 166b and 176 (8956047).
Sale costs reduce the gains; costs beyond the gains add to the losses, since the costs of a sale at a loss are part
of that loss. The exact amounts keep their cents, the declared ones are whole euros.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from steuerbote.kst.years import HUNDRED, Year
from steuerbote.ustva.rounding import CENT, ZERO, ceil_euro, floor_euro, half_up_euro, require_decimal


class Exemption(Enum):
	"""What § 8b KStG makes of the dividends of a holding."""

	EXEMPT = "§ 8b Absatz 1 KStG"
	STREUBESITZ = "§ 8b Absatz 4 Satz 1 KStG"
	TRADING_BOOK = "§ 8b Absatz 7 KStG"


@dataclass(frozen=True, slots=True)
class Holding:
	"""A holding of the register; the shares are percentages of the capital of the company held directly.

	``acquired_in_year`` is the share bought in one acquisition during the calendar year, ``foreign`` says the company
	has its management and seat abroad (§ 9 Nummer 7 GewStG instead of Nummer 2a).
	"""

	name: str
	share_at_year_start: Decimal
	share_at_ez_start: Decimal
	acquired_in_year: Decimal = ZERO
	foreign: bool = False

	def __post_init__(self) -> None:
		if not isinstance(self.name, str) or not self.name.strip():
			raise ValueError("a holding needs a name")
		for share, what in (
			(self.share_at_year_start, "the share at the start of the year"),
			(self.share_at_ez_start, "the share at the start of the Erhebungszeitraum"),
			(self.acquired_in_year, "the share acquired in the year"),
		):
			if not require_decimal(share).is_finite() or not ZERO <= share <= HUNDRED:
				raise ValueError(f"{self.name}: {what} is a percentage from 0 to 100, not {share}")


@dataclass(frozen=True, slots=True)
class HoldingResult:
	"""The dividends a holding paid in the Wirtschaftsjahr, gross of Kapitalertragsteuer, and the costs directly
	related to them: those that § 8 Nummer 1 GewStG counts (``financing_costs``, Anlage BEG line 8) and the others
	(line 9)."""

	holding: Holding
	dividends: Decimal
	financing_costs: Decimal = ZERO
	other_costs: Decimal = ZERO

	def __post_init__(self) -> None:
		for amount, what in (
			(self.dividends, "the dividends"),
			(self.financing_costs, "the financing costs"),
			(self.other_costs, "the other costs"),
		):
			if not _is_cents(amount) or amount < ZERO:
				raise ValueError(
					f"{self.holding.name}: {what} must be an amount in cents of at least 0, not {amount}"
				)


@dataclass(frozen=True, slots=True)
class HoldingDividends:
	"""A holding's dividends and what § 8b makes of them; ``acquisition_counts`` says that § 8b Absatz 4 Satz 6
	exempts them, the kind 2 of Anlage GK line 151 (E8560407)."""

	result: HoldingResult
	exemption: Exemption
	acquisition_counts: bool


@dataclass(frozen=True, slots=True)
class Amount:
	"""A line of the declaration: exact in cents, and as declared in whole euros."""

	exact: Decimal
	declared: Decimal


_NONE = Amount(ZERO, ZERO)


@dataclass(frozen=True, slots=True)
class P8b:
	"""The lines 156 to 201 of Anlage GK. ``taxed_dividends`` are the dividends that stay in the income, those of
	Streubesitz or of the trading book and those of no holding (``unassigned_dividends``); ``excess_dividends`` are
	the dividends of the holdings beyond those of the ledger, which the filing has to explain."""

	holdings: tuple[HoldingDividends, ...]
	exempt_dividends: Amount
	dividends_nondeductible: Amount
	gains: Amount
	losses: Amount
	writeups: Amount
	gains_nondeductible: Amount
	writedowns: Amount
	total: Amount
	taxed_dividends: Decimal
	unassigned_dividends: Decimal
	excess_dividends: Decimal


def exemption(holding: Holding, year: Year, trading_book: bool = False) -> Exemption:
	"""§ 8b Absatz 1, 4 and 7 KStG for the dividends of a holding."""
	if trading_book:
		return Exemption.TRADING_BOOK
	minimum = year.p8b_minimum_holding
	if holding.share_at_year_start >= minimum or holding.acquired_in_year >= minimum:
		return Exemption.EXEMPT
	return Exemption.STREUBESITZ


def p8b(
	year: Year,
	*,
	dividends: Decimal,
	holdings: Iterable[HoldingResult],
	gains: Decimal,
	sale_costs: Decimal,
	losses: Decimal,
	writedowns: Decimal,
	writeups: Decimal,
	trading_book: bool = False,
) -> P8b:
	"""The lines of § 8b of the year from the amounts of the categories, in cents, and the dividends of the holdings."""
	minimum = year.p8b_minimum_holding
	found = tuple(
		HoldingDividends(
			result,
			exemption(result.holding, year, trading_book),
			not trading_book
			and result.holding.share_at_year_start < minimum <= result.holding.acquired_in_year,
		)
		for result in holdings
	)
	assigned = sum((h.result.dividends for h in found), ZERO)
	unassigned = max(dividends - assigned, ZERO)
	taxed = unassigned + sum((h.result.dividends for h in found if h.exemption is not Exemption.EXEMPT), ZERO)
	excess = max(assigned - dividends, ZERO)
	if trading_book:
		return P8b(found, _NONE, _NONE, _NONE, _NONE, _NONE, _NONE, _NONE, _NONE, taxed, unassigned, excess)

	share = year.p8b_percent / HUNDRED
	exempt = sum((h.result.dividends for h in found if h.exemption is Exemption.EXEMPT), ZERO)
	line_156 = Amount(exempt, ceil_euro(exempt))
	line_160 = Amount(exempt * share, floor_euro(line_156.declared * share))
	gain = max(gains - sale_costs, ZERO)
	line_166b = Amount(gain, ceil_euro(gain))
	loss = max(losses + max(sale_costs - gains, ZERO), ZERO)
	line_166c = Amount(loss, floor_euro(loss))
	writeup = max(writeups, ZERO)
	line_176 = Amount(writeup, ceil_euro(writeup))
	line_181 = Amount((gain + writeup) * share, floor_euro((line_166b.declared + line_176.declared) * share))
	writedown = max(writedowns, ZERO)
	line_188 = Amount(writedown, half_up_euro(writedown))
	added, subtracted = (line_160, line_166c, line_181, line_188), (line_156, line_166b, line_176)
	line_201 = Amount(
		sum((a.exact for a in added), ZERO) - sum((a.exact for a in subtracted), ZERO),
		sum((a.declared for a in added), ZERO) - sum((a.declared for a in subtracted), ZERO),
	)
	return P8b(
		found,
		line_156,
		line_160,
		line_166b,
		line_166c,
		line_176,
		line_181,
		line_188,
		line_201,
		taxed,
		unassigned,
		excess,
	)


def _is_cents(amount: Decimal) -> bool:
	return require_decimal(amount).is_finite() and amount == amount.quantize(CENT)
