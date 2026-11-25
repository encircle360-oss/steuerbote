"""The Gewerbeertrag of a GmbH or UG from the result of the Körperschaftsteuer (GewSt 1 A and Anlage BEG).

There is one computation: the Gewerbesteuer takes the Summe der Einkünfte, the Termingeschäfte and the holdings of
steuerbote.kst.chain, and the categories of the same Income Tax Mapping. The lines and Feldkennungen are those of
Jahresdokumentation_E20_2025.ods (ERiC documentation 44.3.6.0), provisionally for 2026 (steuerbote.gewst.years).

- Line 39 (E4001703), the Gewinn aus Gewerbebetrieb: „Bei einer Körperschaft ist der Ausgangswert für den Gewinn
  aus Gewerbebetrieb die Summe der Einkünfte laut Anlage ZVE der Körperschaftsteuererklärung. ... Die
  Gewinnauswirkungen der besonderen Verrechnungskreise (zum Beispiel § 15 Absatz 4 EStG) laut Anlage GK der
  Körperschaftsteuererklärung machen Sie rückgängig“ (Anleitung zur Gewerbesteuererklärung 2025); R 7.1 Absatz 4
  GewStR 2009: the Gewinn of a Körperschaft comes before the Verlustabzug of § 10d EStG, and § 15 Absatz 4 EStG does
  not apply (Absatz 3 Satz 1 Nummer 4). So line 39 is Anlage ZVE line 32 less Anlage GK line 51 plus line 52; the
  Zuwendungen are still in it, which Anlage GK line 92 added back and Anlage ZVE line 34 deducts only after line 32,
  so § 8 Nummer 9 GewStG adds nothing.
- Lines 50 to 56, the financing parts of § 8 Nummer 1 GewStG, „in voller Höhe“: the Finanzamt computes the
  Hinzurechnung from them, Steuerbote computes it for the provision (``financing_addback``): „Ein Viertel der
  Summe“ of the interest, the annuities and the shares of silent partners in full, a fifth of the rents of
  movable goods (half of that fifth for electric vehicles and bicycles), half of the rents of immovable goods
  and a quarter of the licences (``financing_parts``), as far as the sum exceeds 200 000 Euro. A part is never
  below 0.
- Anlage BEG per holding, with the shares of the holdings register: line 6 the dividends of the Wirtschaftsjahr,
  line 7 the paragraph of the Kürzung for a holding of at least 15 % at the start of the Erhebungszeitraum (1 for
  § 9 Nummer 2a, 2 for § 9 Nummer 7 GewStG), line 12 the dividends § 8b Absatz 1 KStG exempts, line 14 the others.
  Below 15 % line 15 adds back „Abrunden(0.95 * [E4051201])“ (rule 40954) under § 8 Nummer 5 GewStG, the exempt
  dividends less the 5 % that § 8b Absatz 5 KStG already treats as non-deductible; from 15 % lines 16 to 19 cut the
  dividends that stayed in the profit, less the costs related to them, „Aufrunden([E4051601] - Summe(E4051701,
  E4051801))“ (40965, with 40958 and 40959). Streubesitz below 15 % needs no Anlage BEG: the dividends are taxed in
  the profit and neither added back nor cut. GewSt 1 A line 77 (E4006601) sums line 15, line 81 (E4006801) line 19.
- Line 87 (E4008701), § 9 Nummer 1 Satz 1 GewStG since EZ 2025: „die im Erhebungszeitraum als Betriebsausgabe
  erfasste Grundsteuer für zum Betriebsvermögen des Unternehmers gehörenden Grundbesitz“.
- Lines 92a to 92d, the Zuwendungen of the receipts, line 92d (E4003403) „Aufrunden(Summe(...))“ of them (40053), the
  Zuwendungsvortrag of the previous EZ in line 150 (E4015001) and the turnover and wages in line 94 (E4004001): § 9
  Nummer 5 GewStG cuts them up to 20 % of the Gewinn aus Gewerbebetrieb or 4 per mille of turnover and wages, the
  rest is carried forward. The Finanzamt computes the cut; Steuerbote rounds the cap up to full euros as the
  Körperschaftsteuer does (rules 8901005 and 8901006 of the Jahresdokumentation E30), which is unverified for the
  Gewerbesteuer.

Then the computation that the declaration leaves to the Finanzamt and the Gemeinde, for the provision:
- § 10a GewStG: „Der maßgebende Gewerbeertrag wird bis zu einem Betrag in Höhe von 1 Million Euro um die Fehlbeträge
  gekürzt, die sich bei der Ermittlung des maßgebenden Gewerbeertrags für die vorangegangenen Erhebungszeiträume ...
  ergeben haben“ (Satz 1), „Der 1 Million Euro übersteigende maßgebende Gewerbeertrag ist bis zu 60 Prozent um nach
  Satz 1 nicht berücksichtigte Fehlbeträge der vorangegangenen Erhebungszeiträume zu kürzen“ (Satz 2), after
  steuerbote.kst.losses.minimum_taxation; a negative Gewerbeertrag is a Fehlbetrag that remains at the end of the EZ
  (Satz 7), whose Feststellung the declaration serves (Satz 6). Line 148 (E4014801) holds the Fehlbetrag assessed for
  the previous EZ;
- § 11 Absatz 1 Satz 3 GewStG: „Der Gewerbeertrag ist auf volle 100 Euro nach unten abzurunden“; a Kapitalgesellschaft
  has no Freibetrag; § 11 Absatz 2: „Die Steuermesszahl für den Gewerbeertrag beträgt 3,5 Prozent“; R 14.1 Satz 3
  GewStR 2009: „Der Steuermessbetrag ist erforderlichenfalls auf volle Euro nach unten abzurunden“;
- § 16 GewStG: the Gewerbesteuer is the Messbetrag times the Hebesatz of the Gemeinde, at least the minimum of § 16
  Absatz 4 Satz 2 (steuerbote.gewst.years); with a whole Hebesatz it has no fraction of a cent, any other is rounded to
  cents. Steuerbote has one Gemeinde; a Zerlegung (GewSt 1 D) is a later module;
- § 19 GewStG: the Vorauszahlungen of the EZ are credited; the balance is the Abschlusszahlung, a refund below 0.

Each line is a Line of steuerbote.kst.chain with a Step of STEPS; the amounts of the ledger are declared in whole
euros rounded half up (steuerbote.ustva.rounding). The financing parts and the cuts without a field of their own
are exact, since only the Gewerbeertrag is rounded. Other Hinzurechnungen and Kürzungen (§ 8 Nummer 8, 10 and 12,
§ 9 Nummer 2, 3 and 8) and the Kürzung of the Hinzurechnung for costs of cut dividends (Anlage BEG line 20) are not
in Steuerbote's scope; costs that would need the latter give a hint.

The findings are steuerbote.kst.chain.Finding: a missing Hebesatz and one below the minimum hold the filing back.
expected_rules() names the rules of GewSt 1 A and Anlage BEG that this module computes, for the year check
(steuerbote.kst.years.RuleExpectation).
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from steuerbote.gewst.years import Year, year_of
from steuerbote.kst.categories import Category
from steuerbote.kst.chain import Finding, KstResult, Line, Severity, Source, Step
from steuerbote.kst.holdings import Exemption, HoldingDividends
from steuerbote.kst.losses import minimum_taxation
from steuerbote.kst.years import HUNDRED, RuleExpectation, factor
from steuerbote.kst.years import year_of as kst_year_of
from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import (
	CENT,
	EURO,
	ZERO,
	ceil_euro,
	floor_euro,
	floor_hundred,
	half_up_euro,
	require_decimal,
	to_cents,
)

GEWST1A = "GewSt1A"
GEWERBEERTRAG_BEFORE_LOSS = "gewerbeertrag_before_loss"
GEWERBEERTRAG = "gewerbeertrag"
PER_MILLE = Decimal("1000")
_LEDGER, _COMPUTED = Source.LEDGER, Source.COMPUTED


def _part(key: str, label: str, letter: str, line: str, field: str, category: Category) -> Step:
	"""A financing part of § 8 Nummer 1 GewStG, declared in full."""
	return Step(
		key,
		label,
		f"§ 8 Nummer 1 Buchstabe {letter} GewStG",
		GEWST1A,
		line,
		field,
		1,
		None,
		(category,),
		_LEDGER,
	)


STEPS: tuple[Step, ...] = (
	Step(
		"profit",
		"Gewinn aus Gewerbebetrieb",
		"§ 7 Satz 1 GewStG; R 7.1 Absatz 3 und 4 GewStR 2009",
		GEWST1A,
		"39",
		"E4001703",
		1,
		GEWERBEERTRAG_BEFORE_LOSS,
		(),
		_COMPUTED,
	),
	_part("interest", "Entgelte für Schulden", "a", "50", "E4003202", Category.INTEREST),
	_part("annuities", "Renten und dauernde Lasten", "b", "51", "E4003302", Category.ANNUITIES),
	_part(
		"silent_partner",
		"Gewinnanteile der stillen Gesellschafter",
		"c",
		"52",
		"E4003407",
		Category.SILENT_PARTNER,
	),
	_part(
		"rent_movable",
		"Miet- und Pachtzinsen für bewegliche Wirtschaftsgüter",
		"d Satz 1",
		"53",
		"E4003502",
		Category.RENT_MOVABLE,
	),
	_part(
		"rent_movable_ev",
		"Miet- und Pachtzinsen für Elektrofahrzeuge und Fahrräder",
		"d Satz 2",
		"54",
		"E4004402",
		Category.RENT_MOVABLE_EV,
	),
	_part(
		"rent_immovable",
		"Miet- und Pachtzinsen für unbewegliche Wirtschaftsgüter",
		"e",
		"55",
		"E4003602",
		Category.RENT_IMMOVABLE,
	),
	_part(
		"licences", "Aufwendungen für die Überlassung von Rechten", "f", "56", "E4003703", Category.LICENCES
	),
	Step(
		"financing_parts",
		"Summe der Finanzierungsanteile",
		"§ 8 Nummer 1 GewStG",
		"",
		"",
		None,
		1,
		None,
		(),
		_COMPUTED,
	),
	Step(
		"financing_addback",
		"Hinzurechnung nach § 8 Nummer 1 GewStG",
		"§ 8 Nummer 1 GewStG",
		"",
		"",
		None,
		1,
		GEWERBEERTRAG_BEFORE_LOSS,
		(),
		_COMPUTED,
	),
	Step(
		"dividends_addback",
		"Hinzurechnungsbetrag nach § 8 Nummer 5 GewStG laut Anlagen BEG",
		"§ 8 Nummer 5 GewStG",
		GEWST1A,
		"77",
		"E4006601",
		1,
		GEWERBEERTRAG_BEFORE_LOSS,
		(Category.DIVIDENDS,),
		_COMPUTED,
	),
	Step(
		"property_tax",
		"Als Betriebsausgabe erfasste Grundsteuer",
		"§ 9 Nummer 1 Satz 1 GewStG",
		GEWST1A,
		"87",
		"E4008701",
		-1,
		GEWERBEERTRAG_BEFORE_LOSS,
		(Category.PROPERTY_TAX_OWN,),
		_LEDGER,
	),
	Step(
		"dividends_cut",
		"Kürzung nach § 9 Nummer 2a, 7 und 8 GewStG laut Anlagen BEG",
		"§ 9 Nummer 2a und 7 GewStG",
		GEWST1A,
		"81",
		"E4006801",
		-1,
		GEWERBEERTRAG_BEFORE_LOSS,
		(Category.DIVIDENDS,),
		_COMPUTED,
	),
	Step(
		"donations",
		"Zuwendungen zur Förderung steuerbegünstigter Zwecke",
		"§ 9 Nummer 5 Satz 1 GewStG",
		GEWST1A,
		"92d",
		"E4003403",
		1,
		None,
		(Category.DONATIONS,),
		_COMPUTED,
	),
	Step(
		"donation_cut",
		"Kürzung der Zuwendungen",
		"§ 9 Nummer 5 GewStG",
		"",
		"",
		None,
		-1,
		GEWERBEERTRAG_BEFORE_LOSS,
		(),
		_COMPUTED,
	),
	Step(
		GEWERBEERTRAG_BEFORE_LOSS,
		"Gewerbeertrag vor Verlustabzug",
		"§ 7 Satz 1, §§ 8 und 9 GewStG",
		"",
		"",
		None,
		1,
		GEWERBEERTRAG,
		(),
		_COMPUTED,
	),
	Step(
		"loss_deduction",
		"Gewerbeverlust der vorangegangenen Erhebungszeiträume",
		"§ 10a Satz 1 und 2 GewStG",
		"",
		"",
		None,
		-1,
		GEWERBEERTRAG,
		(),
		_COMPUTED,
	),
	Step(GEWERBEERTRAG, "Gewerbeertrag", "§ 10a GewStG", "", "", None, 1, None, (), _COMPUTED),
	Step(
		"gewerbeertrag_rounded",
		"Gewerbeertrag, auf volle 100 Euro abgerundet",
		"§ 11 Absatz 1 Satz 3 GewStG",
		"",
		"",
		None,
		1,
		None,
		(),
		_COMPUTED,
	),
	Step(
		"messbetrag",
		"Steuermessbetrag",
		"§ 11 Absatz 1 Satz 2 und Absatz 2 GewStG; R 14.1 Satz 3 GewStR 2009",
		"",
		"",
		None,
		1,
		None,
		(),
		_COMPUTED,
	),
	Step("gewst", "Gewerbesteuer", "§ 16 Absatz 1 GewStG", "", "", None, 1, "balance", (), _COMPUTED),
	Step("prepayments", "Vorauszahlungen", "§ 19 GewStG", "", "", None, -1, "balance", (), Source.INPUT),
	Step(
		"balance",
		"Abschlusszahlung oder Erstattung der Gewerbesteuer",
		"§ 20 GewStG",
		"",
		"",
		None,
		1,
		None,
		(),
		_COMPUTED,
	),
)
_BY_KEY = MappingProxyType({item.key: item for item in STEPS})
_PART_PERCENTS = (
	("interest", None),
	("annuities", None),
	("silent_partner", None),
	("rent_movable", "movable_rent_percent"),
	("rent_movable_ev", "movable_rent_ev_percent"),
	("rent_immovable", "immovable_rent_percent"),
	("licences", "licence_percent"),
)


@dataclass(frozen=True, slots=True)
class GewstInputs:
	"""What the Gewerbesteuer needs besides the result of the Körperschaftsteuer.

	``hebesatz`` is the Hebesatz of the Gemeinde in percent, from the settings with its source. The carry-forwards
	are those of the last notices in whole euros: the Fehlbetrag of § 10a GewStG (line 148) and the
	Zuwendungsvortrag (line 150). ``turnover_and_wages`` (line 94) and ``eligible_donations`` (the receipts behind
	line 92d, in cents) default to those of the Körperschaftsteuer; ``prepayments`` are the Vorauszahlungen of the
	EZ in cents.
	"""

	hebesatz: Decimal | None
	loss_carry_forward: Decimal = ZERO
	donation_carry_forward: Decimal = ZERO
	turnover_and_wages: Decimal | None = None
	eligible_donations: Decimal | None = None
	prepayments: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class BegLine:
	"""Anlage BEG of a holding, in whole euros: line 6 ``dividends``, line 7 ``paragraph`` (1 for § 9 Nummer 2a, 2 for
	Nummer 7, None below 15 %), line 12 ``exempt``, line 14 ``not_exempt``, line 15 ``addback``, line 16
	``cut_base``, lines 17 and 18 the costs and line 19 ``cut``."""

	holding: HoldingDividends
	dividends: Decimal
	paragraph: int | None
	exempt: Decimal
	not_exempt: Decimal
	addback: Decimal
	cut_base: Decimal
	financing_costs: Decimal
	other_costs: Decimal
	cut: Decimal


@dataclass(frozen=True, slots=True)
class GewstResult:
	"""The computed lines of an EZ in the order of STEPS, the Anlagen BEG, the carry-forwards at its end, the
	findings and the Hebesatz the Gewerbesteuer was computed with."""

	year: Year
	lines: MappingProxyType[str, Line]
	beg: tuple[BegLine, ...]
	donation_carry_forward: Decimal
	loss_carry_forward: Decimal
	findings: tuple[Finding, ...]
	hebesatz: Decimal | None

	@property
	def ready(self) -> bool:
		"""No finding holds the filing back."""
		return not any(finding.blocking for finding in self.findings)

	@property
	def gewerbeertrag(self) -> Decimal:
		"""The Gewerbeertrag rounded down to full 100 euros, 0 when it is not positive."""
		return self.lines["gewerbeertrag_rounded"].declared

	@property
	def messbetrag(self) -> Decimal:
		return self.lines["messbetrag"].declared

	@property
	def gewst(self) -> Decimal:
		"""The Gewerbesteuer of the Gemeinde, 0 without a Hebesatz."""
		return self.lines["gewst"].declared

	@property
	def balance(self) -> Decimal:
		"""The Abschlusszahlung of Gewerbesteuer, a refund below 0."""
		return self.lines["balance"].declared


class Code(StrEnum):
	HEBESATZ_MISSING = "GEWST-HEBESATZ-FEHLT"
	HEBESATZ_TOO_LOW = "GEWST-HEBESATZ-UNTER-MINDESTSATZ"
	BEG_FINANCING = "GEWST-BEG-FINANZIERUNGSANTEILE"


def compute(kst: KstResult, inputs: GewstInputs, figures: Figures) -> GewstResult:
	"""The Gewerbesteuer of the EZ of the Körperschaftsteuer; see the module docstring."""
	year = year_of(kst.year.year)
	_require_euros(inputs.loss_carry_forward, "the Fehlbetrag")
	_require_euros(inputs.donation_carry_forward, "the Zuwendungsvortrag")
	if inputs.turnover_and_wages is not None:
		_require_euros(inputs.turnover_and_wages, "the Umsätze, Löhne und Gehälter")
	eligible = inputs.eligible_donations
	if eligible is not None and (not _is_cents(eligible) or eligible < ZERO):
		raise ValueError(f"the Zuwendungen must be an amount in cents of at least 0, not {eligible}")
	hebesatz = inputs.hebesatz
	if hebesatz is not None and (not require_decimal(hebesatz).is_finite() or hebesatz <= ZERO):
		raise ValueError(f"the Hebesatz must be a percentage above 0, not {hebesatz}")
	if not _is_cents(inputs.prepayments) or inputs.prepayments < ZERO:
		raise ValueError(
			f"the Vorauszahlungen must be an amount in cents of at least 0, not {inputs.prepayments}"
		)
	classification = kst.classification
	lines: dict[str, Line] = {}

	def put(key: str, exact: Decimal, declared: Decimal | None = None) -> None:
		item = _BY_KEY[key]
		lines[key] = Line(
			item,
			exact,
			exact if declared is None else declared,
			classification.contributions(*item.categories),
		)

	profit = kst.lines["sum_of_income"].declared - kst.lines["derivatives_loss"].declared
	put("profit", profit + kst.lines["derivatives_offset"].declared)
	parts = ZERO
	for key, percent in _PART_PERCENTS:
		exact = max(classification.amount(*_BY_KEY[key].categories), ZERO)
		put(key, exact, half_up_euro(exact))
		share = HUNDRED if percent is None else getattr(year, percent)
		parts += lines[key].declared * share / HUNDRED
	put("financing_parts", parts)
	put("financing_addback", max(parts - year.financing_allowance, ZERO) * year.financing_percent / HUNDRED)

	beg = tuple(
		line for line in (_beg(holding, year, kst) for holding in kst.p8b.holdings) if line is not None
	)
	put("dividends_addback", sum((line.addback for line in beg), ZERO))
	grundsteuer = classification.amount(Category.PROPERTY_TAX_OWN)
	put("property_tax", grundsteuer, half_up_euro(grundsteuer))
	put("dividends_cut", sum((line.cut for line in beg), ZERO))

	receipts = kst.donations.donations.exact if eligible is None else eligible
	put("donations", receipts, ceil_euro(receipts))
	available = inputs.donation_carry_forward + lines["donations"].declared
	turnover = inputs.turnover_and_wages
	if turnover is None:
		turnover = kst.donations.turnover_and_wages or ZERO
	cap = ceil_euro(
		max(
			lines["profit"].declared * year.donation_profit_percent / HUNDRED,
			turnover * year.donation_turnover_per_mille / PER_MILLE,
		)
	)
	put("donation_cut", max(min(available, cap), ZERO))
	put(GEWERBEERTRAG_BEFORE_LOSS, *_total(GEWERBEERTRAG_BEFORE_LOSS, lines))

	before = lines[GEWERBEERTRAG_BEFORE_LOSS].declared
	first, limited = minimum_taxation(before, inputs.loss_carry_forward, year.loss_unlimited, year.loss_share)
	put("loss_deduction", first + limited)
	put(GEWERBEERTRAG, *_total(GEWERBEERTRAG, lines))
	remaining_loss = inputs.loss_carry_forward - first - limited + max(-before, ZERO)
	gewerbeertrag = lines[GEWERBEERTRAG].declared
	put("gewerbeertrag_rounded", gewerbeertrag, floor_hundred(max(gewerbeertrag, ZERO)))
	assessed = lines["gewerbeertrag_rounded"].declared * year.messzahl / HUNDRED
	put("messbetrag", assessed, floor_euro(assessed))
	tax = lines["messbetrag"].declared * (hebesatz or ZERO) / HUNDRED
	put("gewst", tax, to_cents(tax))
	put("prepayments", inputs.prepayments)
	put("balance", *_total("balance", lines))

	return GewstResult(
		year,
		MappingProxyType({item.key: lines[item.key] for item in STEPS}),
		beg,
		available - lines["donation_cut"].declared,
		remaining_loss,
		_findings(year, hebesatz, beg, figures),
		hebesatz,
	)


def _findings(
	year: Year, hebesatz: Decimal | None, beg: tuple[BegLine, ...], figures: Figures
) -> tuple[Finding, ...]:
	found: list[Finding] = []
	if hebesatz is None:
		found.append(
			Finding(
				Code.HEBESATZ_MISSING,
				Severity.ERROR,
				f"Für die Gemeinde fehlt der Hebesatz des Erhebungszeitraums {year.year} mit seiner Quelle.",
				"§ 16 Absatz 1 GewStG",
			)
		)
	elif hebesatz < year.minimum_hebesatz:
		found.append(
			Finding(
				Code.HEBESATZ_TOO_LOW,
				Severity.ERROR,
				f"Der Hebesatz von {hebesatz} % liegt unter dem Mindesthebesatz von {year.minimum_hebesatz} %.",
				"§ 16 Absatz 4 Satz 2 GewStG",
			)
		)
	for line in beg:
		if line.paragraph is not None and line.financing_costs:
			found.append(
				Finding(
					Code.BEG_FINANCING,
					Severity.HINT,
					f"Bei {line.holding.result.holding.name} mindern {figures.money(line.financing_costs)} "
					"Aufwendungen im Sinne des § 8 Nummer 1 GewStG die Kürzung. Um sie kürzt Anlage BEG Zeile 20 die "
					"Hinzurechnung; die Erklärung nennt sie dort und in Zeile 79, die Rückstellung von Steuerbote "
					"rechnet ohne diese Kürzung.",
					"§ 9 Nummer 2a Satz 3 GewStG",
				)
			)
	return tuple(found)


def _beg(holding: HoldingDividends, year: Year, kst: KstResult) -> BegLine | None:
	"""Anlage BEG of a holding, or None for Streubesitz that is neither added back nor cut."""
	qualifies = holding.result.holding.share_at_ez_start >= year.participation_minimum
	exempt = holding.exemption is Exemption.EXEMPT
	if not exempt and not qualifies:
		return None
	dividends = half_up_euro(holding.result.dividends)
	line_12 = dividends if exempt else ZERO
	line_14 = dividends - line_12
	if not qualifies:
		share = (HUNDRED - kst.year.p8b_percent) / HUNDRED
		return BegLine(
			holding, dividends, None, line_12, line_14, floor_euro(share * line_12), ZERO, ZERO, ZERO, ZERO
		)
	paragraph = 2 if holding.result.holding.foreign else 1
	financing = min(half_up_euro(holding.result.financing_costs), line_14)
	other = min(half_up_euro(holding.result.other_costs), line_14 - financing)
	cut = ceil_euro(line_14 - financing - other)
	return BegLine(holding, dividends, paragraph, line_12, line_14, ZERO, line_14, financing, other, cut)


def _total(key: str, lines: dict[str, Line]) -> tuple[Decimal, Decimal]:
	feeding = [lines[item.key] for item in STEPS if item.total == key]
	return (
		sum((line.step.sign * line.exact for line in feeding), ZERO),
		sum((line.step.sign * line.declared for line in feeding), ZERO),
	)


def _require_euros(amount: Decimal, what: str) -> None:
	if not require_decimal(amount).is_finite() or amount != amount.quantize(EURO) or amount < ZERO:
		raise ValueError(f"{what} must be whole euros of at least 0, not {amount}")


def _is_cents(amount: Decimal) -> bool:
	return require_decimal(amount).is_finite() and amount == amount.quantize(CENT)


def expected_rules(year: int) -> tuple[RuleExpectation, ...]:
	"""The rules of the Jahresdokumentation E20 that compute() computes; the 95 % of Anlage BEG line 15 keep what
	§ 8b Absatz 5 KStG of the year leaves."""
	year_of(year)
	kept = factor(HUNDRED - kst_year_of(year).p8b_percent)
	return (
		RuleExpectation("40000", GEWST1A, ("KeinFeldAngegeben(E4001703",)),
		RuleExpectation("40053", GEWST1A, ("[E4003403]!=Aufrunden(Summe(", "E4009221))")),
		RuleExpectation("40954", "BEG", (f"[E4051501]!=Abrunden({kept}*[E4051201]))",)),
		RuleExpectation("40958", "BEG", ("[E4051701]!=Min([E4050801],[E4051601])",)),
		RuleExpectation("40959", "BEG", ("[E4051801]!=Min([E4050901],{[E4051601]-[E4051701]})",)),
		RuleExpectation("40965", "BEG", ("[E4051901]!=Aufrunden({[E4051601]-Summe(E4051701,E4051801)}))",)),
	)
