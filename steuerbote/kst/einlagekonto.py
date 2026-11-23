"""The steuerliches Einlagekonto of § 27 KStG, which KSt 1 F declares for every Wirtschaftsjahr.

§ 27 KStG (zuletzt geändert durch Art. 30 G v. 4.2.2026 I Nr. 33):
- Absatz 1 Satz 1 and 2: the Kapitalgesellschaft „hat die nicht in das Nennkapital geleisteten Einlagen am Schluss
  jedes Wirtschaftsjahrs auf einem besonderen Konto (steuerliches Einlagekonto) auszuweisen“, which „ist ausgehend
  von dem Bestand am Ende des vorangegangenen Wirtschaftsjahrs um die jeweiligen Zu- und Abgänge des
  Wirtschaftsjahrs fortzuschreiben“;
- Satz 3: Leistungen „mindern das steuerliche Einlagekonto unabhängig von ihrer handelsrechtlichen Einordnung nur,
  soweit sie den auf den Schluss des vorangegangenen Wirtschaftsjahrs ermittelten ausschüttbaren Gewinn übersteigen
  (Einlagenrückgewähr)“; Satz 4: „Der Bestand des steuerlichen Einlagekontos kann durch Leistungen nicht negativ
  werden“; Satz 5: „Als ausschüttbarer Gewinn gilt das um das gezeichnete Kapital geminderte in der Steuerbilanz
  ausgewiesene Eigenkapital abzüglich des Bestands des steuerlichen Einlagekontos.“
- Absatz 2 Satz 4: „Kapitalgesellschaften haben auf den Schluss jedes Wirtschaftsjahrs Erklärungen zur gesonderten
  Feststellung von Besteuerungsgrundlagen abzugeben“, so KSt 1 F is filed even from 0 to 0;
- Absatz 5 Satz 2: without a Steuerbescheinigung „gilt der Betrag der Einlagenrückgewähr als mit 0 Euro
  bescheinigt“.

KSt 1 F of Jahresdokumentation_E30_2025.ods (ERiC documentation 44.3.6.0), in whole euros:
- line 42 (E8240103), the Bestand at the end of the previous Wirtschaftsjahr, the last Feststellung; one of lines 40
  to 43 is mandatory (rule 8924512), so line 42 is declared even with 0; line 43 (E8240201), the Sonderausweis of
  § 28 Absatz 1 Satz 3 KStG, which Steuerbote carries unchanged, as it handles no change of the Nennkapital;
- line 11 (E8200502), the Leistungen of the Wirtschaftsjahr without the Rückzahlung von Nennkapital; line 12
  (E8122003), the reductions of the Einlagekonto the Steuerbescheinigungen certify;
- lines 17 to 20 at the end of the previous Wirtschaftsjahr: the Eigenkapital laut Steuerbilanz (E8201001), the
  Nennkapital (E8201101), the positive Bestand (E8201201) and the ausschüttbarer Gewinn (E8201301), Max(17 - 18 - 19,
  0) (rule 8920021); they are needed with Leistungen and a Bestand (8920011);
- line 46 (E8241717), the Zwischensumme of line 42, declared only when the Bestand is positive and the Leistungen
  exceed the ausschüttbarer Gewinn (8920012, 8920013, 8920019); line 49 (E8240501), line 47 = line 11 less line 48 =
  line 20 (8924077, 8924079, 8924401);
- line 50 (E8242201), the Abzug: Max(Min(46, 49, 12), 0) (8920076) for one Leistung, or several without a
  certificate. Several Leistungen with at least one certified reduction (line 13, E8122011, with line 51) Steuerbote
  leaves to the Steuerberatung;
- lines 91 (E8241501, the Einlagen booked to profit, Anlage GK line 93), 92 (E8241502, the Einlagen not booked,
  Anlage GK line 78) and 95 (E8241601, other Einlagen of the year such as an Agio or a payment into the
  Kapitalrücklage);
- line 152 (E8245601), the Endbestand: line 42 less line 50 plus lines 91, 92 and 95, the part of rule 8924445 that
  applies to a GmbH of Steuerbote's scope; mandatory with line 42 (8920227).

roll_forward() gives the lines and, as steuerbote.kst.chain.Finding, what holds KSt 1 F back.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from steuerbote.kst.chain import Finding, Severity
from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import EURO, ZERO, require_decimal


class Code(StrEnum):
	EQUITY_MISSING = "KST-EINLAGEKONTO-EIGENKAPITAL"
	SEVERAL_CERTIFIED = "KST-EINLAGEKONTO-MEHRERE-LEISTUNGEN"


@dataclass(frozen=True, slots=True)
class Einlagekonto:
	"""The lines of KSt 1 F. ``distributable`` (line 20) and ``excess`` (line 49) are None without the equity of the
	previous year, ``subtotal`` (line 46) is None where the rules leave it out."""

	opening: Decimal
	sonderausweis: Decimal
	distributions: Decimal
	certified_reduction: Decimal
	positive_opening: Decimal
	distributable: Decimal | None
	subtotal: Decimal | None
	excess: Decimal | None
	reduction: Decimal
	contributions: Decimal
	closing: Decimal
	findings: tuple[Finding, ...]

	@property
	def closing_sonderausweis(self) -> Decimal:
		return self.sonderausweis


def roll_forward(
	opening: Decimal,
	figures: Figures,
	*,
	sonderausweis: Decimal = ZERO,
	distributions: Decimal = ZERO,
	certified_reduction: Decimal = ZERO,
	several_certified: bool = False,
	previous_equity: Decimal | None = None,
	previous_nominal_capital: Decimal | None = None,
	contributions_booked: Decimal = ZERO,
	contributions_not_booked: Decimal = ZERO,
	other_contributions: Decimal = ZERO,
) -> Einlagekonto:
	"""KSt 1 F of a Wirtschaftsjahr from the Bestand at the end of the previous one and what happened in it."""
	_require_euros(opening, "the Bestand at the end of the previous Wirtschaftsjahr", negative=True)
	_require_euros(sonderausweis, "the Sonderausweis")
	_require_euros(distributions, "the Leistungen")
	_require_euros(certified_reduction, "the bescheinigte Minderung")
	for equity, what in (
		(previous_equity, "the Eigenkapital laut Steuerbilanz"),
		(previous_nominal_capital, "the Nennkapital"),
	):
		if equity is not None:
			_require_euros(equity, what, negative=True)
	for amount in (contributions_booked, contributions_not_booked, other_contributions):
		_require_euros(amount, "the Einlagen")

	findings: list[Finding] = []
	positive = max(opening, ZERO)
	known = previous_equity is not None and previous_nominal_capital is not None
	distributable = max(previous_equity - previous_nominal_capital - positive, ZERO) if known else None
	excess = distributions - distributable if distributable is not None else None
	subtotal: Decimal | None = None
	reduction = ZERO
	if distributions and positive:
		if distributable is None:
			findings.append(
				Finding(
					Code.EQUITY_MISSING,
					Severity.ERROR,
					f"Im Wirtschaftsjahr wurden {figures.money(distributions)} ausgeschüttet, und das steuerliche "
					"Einlagekonto hat einen Bestand. KSt 1 F braucht in den Zeilen 17 und 18 das Eigenkapital laut "
					"Steuerbilanz und das Nennkapital zum Schluss des vorangegangenen Wirtschaftsjahres.",
					"§ 27 Absatz 1 Satz 5 KStG; Regel 8920011",
				)
			)
		elif several_certified:
			findings.append(
				Finding(
					Code.SEVERAL_CERTIFIED,
					Severity.ERROR,
					"Bei mehreren Leistungen mit bescheinigter Minderung des Einlagekontos (KSt 1 F Zeilen 13 und 51) "
					"berechnet Steuerbote den Abzug nicht; er ist mit der Steuerberatung abzustimmen.",
					"§ 27 Absatz 1 Satz 3 und Absatz 5 KStG",
				)
			)
		elif excess is not None and excess > ZERO:
			subtotal = positive
			reduction = max(min(positive, excess, certified_reduction), ZERO)
	contributions = contributions_booked + contributions_not_booked + other_contributions
	return Einlagekonto(
		opening,
		sonderausweis,
		distributions,
		certified_reduction,
		positive,
		distributable,
		subtotal,
		excess,
		reduction,
		contributions,
		opening - reduction + contributions,
		tuple(findings),
	)


def _require_euros(amount: Decimal, what: str, negative: bool = False) -> None:
	if (
		not require_decimal(amount).is_finite()
		or amount != amount.quantize(EURO)
		or (amount < ZERO and not negative)
	):
		bound = "" if negative else " of at least 0"
		raise ValueError(f"{what} must be whole euros{bound}, not {amount}")
