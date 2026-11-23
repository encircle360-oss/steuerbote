"""The computation of the Körperschaftsteuer of a GmbH or UG, from the Jahresüberschuss to the Abschlusszahlung.

The order is that of R 7.1 Absatz 1 KStR 2022: the Jahresüberschuss, corrected to the Steuerbilanz, the corrections
outside the books (Anlage GK), the Summe der Einkünfte, the Zuwendungen, the Gesamtbetrag der Einkünfte, the
Verlustabzug, the zu versteuerndes Einkommen (Anlage ZVE); then the tax (§ 23 KStG), the Solidaritätszuschlag, the
credits of Anlage WA and the Vorauszahlungen. The lines and Feldkennungen are those of
Jahresdokumentation_E30_2025.ods (ERiC documentation 44.3.6.0), provisionally for 2026 (steuerbote.kst.years).

STEPS holds each step as data (Step): its key, the label of the form in German, its law, its form, line and
Feldkennung, its sign, the total it feeds and the categories of the Income Tax Mapping whose postings stand behind
it. ``source`` says where its amount comes from:
- NET_INCOME: the Jahresüberschuss of the ledger, Anlage GK line 11, which the form takes „bei Handelsbilanz: nach
  Berücksichtigung der Überleitungsrechnung nach § 5b Absatz 1 Satz 2 EStG beziehungsweise § 60 Absatz 2 EStDV zur
  Anpassung an die steuerlich maßgeblichen Wertansätze“; so the manual lines of the step are the Überleitung to the
  Steuerbilanz, each with its reason, until the E-Bilanz gives it;
- LEDGER: the amount of its categories, which manual lines with a reason may correct;
- MANUAL: manual lines with a reason only, such as a verdeckte Gewinnausschüttung (§ 8 Absatz 3 Satz 2 KStG);
- INPUT: what the caller knows from outside the books: the Kapitalertragsteuer and the Solidaritätszuschlag of the
  Steuerbescheinigungen (Anlage WA lines 2 and 3, § 36 Absatz 2 Nummer 2 EStG) and the Vorauszahlungen of the notices;
- COMPUTED: the computation: § 8b KStG (steuerbote.kst.holdings), § 15 Absatz 4 EStG, § 10d EStG and the
  Zuwendungen (steuerbote.kst.losses), the totals and the tax;
- LATER: a step of a later module, the Teilfreistellung of the InvStG and the Anlage AESt; its amount is 0, and a
  balance on its category holds the filing back.

A total is the sum of the declared amounts of the steps that name it, each with its sign, as the rules of the
Jahresdokumentation add them: Anlage GK line 300 (rule 8906062), line 201 (8956047), Anlage ZVE line 32 (8900207),
line 53 (8900413), line 70 (8900431). Steps beyond the declaration have neither form nor field.

compute() takes the KstInputs of a VZ: the ledger lines of the Wirtschaftsjahr (all accounts of the profit and loss
account, without the Period Closing Voucher and the opening entries, as steuerbote.ustva.LedgerLine), the Income Tax
Mapping, the manual lines with their reasons, the dividends of the holdings register and what the settings and the
notices say. It gives a KstResult with a Line per step: ``exact`` in cents, ``declared`` as the form takes it, the
postings behind it (``contributions``) and its manual lines. A line of the ledger is declared in whole euros rounded
half up, since the Jahresdokumentation gives no direction (steuerbote.ustva.rounding); the lines of § 8b and of the
Termingeschäfte round as their modules say. ``figures`` writes the amounts of the findings in the number format of
the site (steuerbote.ustva.plausibility.Figures).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from steuerbote.kst.categories import Category, Classification, Contribution, Mapping, classify
from steuerbote.kst.holdings import Amount, HoldingResult, P8b, p8b
from steuerbote.kst.losses import Derivatives, derivatives
from steuerbote.kst.years import Year, year_of
from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import CENT, ZERO, half_up_euro, require_decimal


class Source(Enum):
	NET_INCOME = "net_income"
	LEDGER = "ledger"
	MANUAL = "manual"
	INPUT = "input"
	COMPUTED = "computed"
	LATER = "later"


@dataclass(frozen=True, slots=True)
class Step:
	"""A step of the computation. ``sign`` is how its amount enters ``total``, the key of the step it feeds."""

	key: str
	label: str
	law: str
	form: str
	line: str
	field: str | None
	sign: int
	total: str | None
	categories: tuple[Category, ...]
	source: Source


GK, ZVE, WA = "GK", "ZVE", "WA"
BUSINESS_INCOME = "business_income"
P8B_TOTAL = "p8b_total"
_NET, _LEDGER, _MANUAL, _INPUT, _COMPUTED, _LATER = (
	Source.NET_INCOME,
	Source.LEDGER,
	Source.MANUAL,
	Source.INPUT,
	Source.COMPUTED,
	Source.LATER,
)
_DERIVATIVES = (Category.DERIVATIVES_GAIN, Category.DERIVATIVES_LOSS)
_IAB_ADDBACK_LAW = "§ 7g Absatz 2 Satz 1 EStG"


def _gk(key: str, label: str, law: str, line: str, field: str, sign: int, *categories: Category) -> Step:
	"""A line of Anlage GK that the categories of the mapping feed into line 300."""
	return Step(key, label, law, GK, line, field, sign, BUSINESS_INCOME, categories, _LEDGER)


STEPS: tuple[Step, ...] = (
	Step(
		"net_income",
		"Jahresüberschuss/-fehlbetrag laut Handels- oder Steuerbilanz",
		"§ 8 Absatz 1 KStG, § 4 Absatz 1 Satz 1 und § 5 Absatz 1 EStG; § 5b Absatz 1 Satz 2 EStG, § 60 Absatz 2 EStDV",
		GK,
		"11",
		"E8002001",
		1,
		BUSINESS_INCOME,
		(),
		_NET,
	),
	Step(
		"derivatives_loss",
		"Nicht ausgleichsfähige Verluste aus Termingeschäften",
		"§ 15 Absatz 4 Satz 3 EStG",
		GK,
		"51",
		"E8002104",
		1,
		BUSINESS_INCOME,
		_DERIVATIVES,
		_COMPUTED,
	),
	Step(
		"derivatives_offset",
		"Verrechnung von Gewinnen aus Termingeschäften mit dem Verlustvortrag",
		"§ 15 Absatz 4 Satz 2 und 3 EStG",
		GK,
		"52",
		"E8002105",
		-1,
		BUSINESS_INCOME,
		_DERIVATIVES,
		_COMPUTED,
	),
	_gk(
		"iab_deduction",
		"Investitionsabzugsbeträge des laufenden Wirtschaftsjahres",
		"§ 7g Absatz 1 EStG",
		"67",
		"E8002602",
		-1,
		Category.IAB_DEDUCTION,
	),
	Step(
		"iab_addback_3",
		"Hinzurechnung von Investitionsabzugsbeträgen aus dem drittletzten Veranlagungszeitraum",
		_IAB_ADDBACK_LAW,
		GK,
		"70",
		"E8002603",
		1,
		BUSINESS_INCOME,
		(),
		_MANUAL,
	),
	Step(
		"iab_addback_2",
		"Hinzurechnung von Investitionsabzugsbeträgen aus dem vorletzten Veranlagungszeitraum",
		_IAB_ADDBACK_LAW,
		GK,
		"71",
		"E8002604",
		1,
		BUSINESS_INCOME,
		(),
		_MANUAL,
	),
	_gk(
		"iab_addback",
		"Hinzurechnung von Investitionsabzugsbeträgen aus dem vorangegangenen Veranlagungszeitraum",
		_IAB_ADDBACK_LAW,
		"72",
		"E8002605",
		1,
		Category.IAB_ADDBACK,
	),
	Step(
		"hidden_distributions",
		"Verdeckte Gewinnausschüttungen",
		"§ 8 Absatz 3 Satz 2 KStG",
		GK,
		"75",
		"E8002701",
		1,
		BUSINESS_INCOME,
		(),
		_MANUAL,
	),
	Step(
		"profit_participation_rights",
		"Ausschüttungen auf Genussrechte",
		"§ 8 Absatz 3 Satz 2 KStG",
		GK,
		"75c",
		"E8002709",
		1,
		BUSINESS_INCOME,
		(),
		_MANUAL,
	),
	Step(
		"contributions_not_booked",
		"Nicht erfolgswirksam gebuchte Einlagen",
		"§ 8 Absatz 3 Satz 4 KStG",
		GK,
		"78",
		"E8002801",
		1,
		BUSINESS_INCOME,
		(),
		_MANUAL,
	),
	_gk("corporate_tax", "Körperschaftsteuer", "§ 10 Nummer 2 KStG", "81", "E8100301", 1, Category.KST),
	_gk(
		"solidarity_surcharge",
		"Solidaritätszuschlag",
		"§ 10 Nummer 2 KStG",
		"82",
		"E8100501",
		1,
		Category.SOLZ,
	),
	_gk(
		"capital_gains_tax",
		"Kapitalertragsteuer auf vereinnahmte Kapitalerträge",
		"§ 10 Nummer 2 KStG",
		"83",
		"E8100601",
		1,
		Category.KAPEST,
	),
	_gk("trade_tax", "Gewerbesteuer", "§ 4 Absatz 5b EStG", "84", "E8100702", 1, Category.GEWST),
	_gk(
		"foreign_taxes",
		"Ausländische Steuern vom Einkommen",
		"§ 10 Nummer 2 KStG",
		"87",
		"E8101001",
		1,
		Category.FOREIGN_TAX,
	),
	_gk(
		"ancillary",
		"Nebenleistungen zu den Steuern",
		"§ 10 Nummer 2 zweiter Halbsatz KStG",
		"88",
		"E8101101",
		1,
		Category.ANCILLARY,
	),
	_gk(
		"supervisory_board",
		"Hälfte der Vergütungen an den Aufsichtsrat",
		"§ 10 Nummer 4 KStG",
		"89",
		"E8101201",
		1,
		Category.SUPERVISORY_BOARD,
	),
	_gk(
		"nondeductible",
		"Sonstige nichtabziehbare Aufwendungen",
		"§ 4 Absatz 5 Satz 1 EStG, § 10 Nummer 3 KStG, § 160 AO",
		"90",
		"E8101301",
		1,
		Category.GIFTS_NONDEDUCTIBLE,
		Category.ENTERTAINMENT_NONDEDUCTIBLE,
		Category.OTHER_NONDEDUCTIBLE,
	),
	_gk(
		"donations",
		"Sämtliche Spenden und Mitgliedsbeiträge",
		"§ 9 Absatz 2 Satz 1 KStG",
		"92",
		"E8101401",
		1,
		Category.DONATIONS,
	),
	Step(
		"contributions_paid",
		"Erfolgswirksam gebuchte und geleistete Einlagen",
		"§ 8 Absatz 3 Satz 3 KStG",
		GK,
		"93",
		"E8003301",
		-1,
		BUSINESS_INCOME,
		(),
		_MANUAL,
	),
	Step(
		"contributions_unpaid",
		"Erfolgswirksam gebuchte, nicht geleistete Einlagen",
		"§ 8 Absatz 3 Satz 3 KStG",
		GK,
		"94",
		"E8003401",
		-1,
		BUSINESS_INCOME,
		(),
		_MANUAL,
	),
	_gk(
		"investment_grant",
		"Investitionszulage",
		"§ 13 Satz 1 InvZulG 2010",
		"96",
		"E8003601",
		-1,
		Category.INVESTMENT_GRANT,
	),
	_gk(
		"tax_free",
		"Sonstige steuerfreie Einnahmen",
		"§ 3 und § 3c Absatz 1 EStG",
		"102",
		"E8003701",
		-1,
		Category.TAX_FREE,
	),
	Step(
		"p8b_dividends",
		"Steuerfreie Bezüge",
		"§ 8b Absatz 1 und 4 KStG",
		GK,
		"156",
		"E8560401",
		-1,
		P8B_TOTAL,
		(Category.DIVIDENDS,),
		_COMPUTED,
	),
	Step(
		"p8b_dividends_nondeductible",
		"Nichtabziehbare Ausgaben, 5 % der steuerfreien Bezüge",
		"§ 8b Absatz 5 Satz 1 KStG",
		GK,
		"160",
		"E8560801",
		1,
		P8B_TOTAL,
		(Category.DIVIDENDS,),
		_COMPUTED,
	),
	Step(
		"p8b_gains",
		"Steuerfreie Gewinne aus der Veräußerung von Anteilen",
		"§ 8b Absatz 2 Satz 1 und 2 KStG",
		GK,
		"166b",
		"E8561212",
		-1,
		P8B_TOTAL,
		(Category.SHARE_GAIN, Category.SHARE_SALE_COSTS),
		_COMPUTED,
	),
	Step(
		"p8b_losses",
		"Nicht abziehbare Verluste aus der Veräußerung von Anteilen",
		"§ 8b Absatz 3 Satz 3 KStG",
		GK,
		"166c",
		"E8561410",
		1,
		P8B_TOTAL,
		(Category.SHARE_LOSS, Category.SHARE_SALE_COSTS),
		_COMPUTED,
	),
	Step(
		"p8b_writeups",
		"Steuerfreie Wertaufholungen",
		"§ 8b Absatz 2 Satz 3 KStG",
		GK,
		"176",
		"E8561220",
		-1,
		P8B_TOTAL,
		(Category.SHARE_WRITEUP,),
		_COMPUTED,
	),
	Step(
		"p8b_gains_nondeductible",
		"Nichtabziehbare Ausgaben, 5 % der steuerfreien Gewinne",
		"§ 8b Absatz 3 Satz 1 KStG",
		GK,
		"181",
		"E8561301",
		1,
		P8B_TOTAL,
		(Category.SHARE_GAIN, Category.SHARE_WRITEUP),
		_COMPUTED,
	),
	Step(
		"p8b_writedowns",
		"Nicht abziehbare Gewinnminderungen, etwa Teilwertabschreibungen",
		"§ 8b Absatz 3 Satz 3 KStG",
		GK,
		"188",
		"E8561411",
		1,
		P8B_TOTAL,
		(Category.SHARE_WRITEDOWN,),
		_COMPUTED,
	),
	Step(
		P8B_TOTAL,
		"Korrektur nach § 8b KStG",
		"§ 8b KStG",
		GK,
		"201",
		"E8562101",
		1,
		BUSINESS_INCOME,
		(),
		_COMPUTED,
	),
	Step(
		"investment_funds",
		"Teilfreistellung nach dem Investmentsteuergesetz",
		"§ 20 InvStG",
		GK,
		"221",
		"E8011302",
		1,
		BUSINESS_INCOME,
		(Category.FUNDS,),
		_LATER,
	),
	Step(
		BUSINESS_INCOME,
		"Einkünfte aus Gewerbebetrieb",
		"§ 8 Absatz 2 KStG",
		GK,
		"300",
		"E8109901",
		1,
		None,
		(),
		_COMPUTED,
	),
	Step(
		"business_income_zve",
		"Einkünfte aus Gewerbebetrieb laut Anlage GK Zeile 300",
		"§ 8 Absatz 2 KStG",
		ZVE,
		"2",
		"E8004904",
		1,
		"sum_of_income",
		(),
		_COMPUTED,
	),
	Step(
		"foreign_tax_deduction",
		"Abzuziehende ausländische Steuern",
		"§ 26 Absatz 1 Satz 1 Nummer 1 KStG, § 34c Absatz 2 EStG",
		ZVE,
		"20",
		"E8004201",
		-1,
		"sum_of_income",
		(),
		_LATER,
	),
	Step(
		"sum_of_income",
		"Summe der Einkünfte",
		"§ 8 Absatz 1 KStG, § 2 Absatz 3 EStG",
		ZVE,
		"32",
		"E8005401",
		1,
		"total_income",
		(),
		_COMPUTED,
	),
	Step(
		"donation_deduction",
		"Abziehbare Zuwendungen laut Anlage Z Zeile 7",
		"§ 9 Absatz 1 Nummer 2 KStG",
		ZVE,
		"34",
		"E8005601",
		-1,
		"total_income",
		(Category.DONATIONS,),
		_COMPUTED,
	),
	Step(
		"total_income",
		"Gesamtbetrag der Einkünfte",
		"§ 8 Absatz 1 KStG, § 2 Absatz 3 EStG",
		ZVE,
		"53",
		"E8006901",
		1,
		"zve",
		(),
		_COMPUTED,
	),
	Step(
		"loss_deduction",
		"Verlustabzug laut Anlage Verluste Zeilen 25 und 27",
		"§ 10d Absatz 2 EStG",
		ZVE,
		"56",
		"E8007001",
		-1,
		"zve",
		(),
		_COMPUTED,
	),
	Step(
		"zve",
		"Zu versteuerndes Einkommen",
		"§ 7 Absatz 1 und 2 KStG",
		ZVE,
		"70",
		"E8007501",
		1,
		None,
		(),
		_COMPUTED,
	),
	Step(
		"corporate_income_tax",
		"Körperschaftsteuer",
		"§ 23 Absatz 1 und § 31 Absatz 1 Satz 2 KStG",
		ZVE,
		"71",
		"E8007502",
		1,
		"kst_remaining",
		(),
		_COMPUTED,
	),
	Step(
		"capital_gains_tax_credit",
		"Anrechenbare Kapitalertragsteuer laut Steuerbescheinigungen",
		"§ 36 Absatz 2 Satz 1 Nummer 2 EStG",
		WA,
		"2",
		"E8120401",
		-1,
		"kst_remaining",
		(),
		_INPUT,
	),
	Step(
		"kst_remaining",
		"Verbleibende Körperschaftsteuer",
		"§ 36 Absatz 2 EStG, § 31 Absatz 1 KStG",
		"",
		"",
		None,
		1,
		"kst_balance",
		(),
		_COMPUTED,
	),
	Step(
		"kst_prepayments",
		"Vorauszahlungen auf die Körperschaftsteuer",
		"§ 36 Absatz 2 Satz 1 Nummer 1 und § 37 EStG",
		"",
		"",
		None,
		-1,
		"kst_balance",
		(),
		_INPUT,
	),
	Step(
		"kst_balance",
		"Abschlusszahlung oder Erstattung der Körperschaftsteuer",
		"§ 36 Absatz 4 EStG",
		"",
		"",
		None,
		1,
		None,
		(),
		_COMPUTED,
	),
	Step(
		"solz",
		"Solidaritätszuschlag",
		"§ 3 Absatz 1 Nummer 1 und § 4 SolZG",
		"",
		"",
		None,
		1,
		"solz_remaining",
		(),
		_COMPUTED,
	),
	Step(
		"solz_credit",
		"Solidaritätszuschlag zur Kapitalertragsteuer laut Steuerbescheinigungen",
		"§ 36 Absatz 2 Satz 1 Nummer 2 EStG, § 1 Absatz 2 SolZG",
		WA,
		"3",
		"E8120601",
		-1,
		"solz_remaining",
		(),
		_INPUT,
	),
	Step(
		"solz_remaining",
		"Verbleibender Solidaritätszuschlag",
		"§ 36 Absatz 2 EStG, § 1 Absatz 2 SolZG",
		"",
		"",
		None,
		1,
		"solz_balance",
		(),
		_COMPUTED,
	),
	Step(
		"solz_prepayments",
		"Vorauszahlungen auf den Solidaritätszuschlag",
		"§ 1 Absatz 4 SolZG",
		"",
		"",
		None,
		-1,
		"solz_balance",
		(),
		_INPUT,
	),
	Step(
		"solz_balance",
		"Abschlusszahlung oder Erstattung des Solidaritätszuschlags",
		"§ 36 Absatz 4 EStG, § 1 Absatz 2 SolZG",
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


def step(key: str) -> Step:
	try:
		return _BY_KEY[key]
	except KeyError:
		raise KeyError(f"no step {key!r}") from None


_TAKES_MANUAL_LINES = frozenset({Source.NET_INCOME, Source.LEDGER, Source.MANUAL})
_P8B_LINES = (
	("p8b_dividends", "exempt_dividends"),
	("p8b_dividends_nondeductible", "dividends_nondeductible"),
	("p8b_gains", "gains"),
	("p8b_losses", "losses"),
	("p8b_writeups", "writeups"),
	("p8b_gains_nondeductible", "gains_nondeductible"),
	("p8b_writedowns", "writedowns"),
)


@dataclass(frozen=True, slots=True)
class ManualLine:
	"""An amount entered by hand with its reason, in the direction of its step: a verdeckte Gewinnausschüttung as a
	positive amount, an Überleitung that lowers the profit as a negative one."""

	step: str
	amount: Decimal
	reason: str

	def __post_init__(self) -> None:
		try:
			found = step(self.step)
		except KeyError as error:
			raise ValueError(error.args[0]) from None
		if found.source not in _TAKES_MANUAL_LINES:
			raise ValueError(f"step {self.step} takes no manual line, its amount is {found.source.value}")
		if not _is_cents(self.amount):
			raise ValueError(f"step {self.step}: a manual line needs an amount in cents, not {self.amount}")
		if not isinstance(self.reason, str) or not self.reason.strip():
			raise ValueError(f"step {self.step}: a manual line needs a reason")


@dataclass(frozen=True, slots=True)
class Line:
	"""A step as computed: ``exact`` in cents, ``declared`` as the form takes it, and what stands behind it."""

	step: Step
	exact: Decimal
	declared: Decimal
	contributions: tuple[Contribution, ...] = ()
	manual: tuple[ManualLine, ...] = ()

	@property
	def ledger(self) -> Decimal:
		"""The part of the exact amount that comes from the books, without the manual lines."""
		return self.exact - sum((line.amount for line in self.manual), ZERO)


@dataclass(frozen=True, slots=True)
class KstInputs:
	"""What compute() needs for a VZ besides the books.

	``net_income`` is the Jahresüberschuss when it comes from elsewhere, such as the E-Bilanz; without it the ledger
	lines give it. ``holdings`` are the dividends of the holdings register, ``trading_book`` the flag of § 8b Absatz 7
	KStG in the settings. The carry-forwards are those of the last notices, in whole euros: the Verlustvortrag of
	§ 10d EStG, the Verlustvortrag of the Termingeschäfte and the Zuwendungsvortrag; ``loss_carry_back`` is the
	Verlustrücktrag chosen for a loss, 0 for none. ``eligible_donations`` are the Zuwendungen of the receipts, by
	default those of the category donations, ``turnover_and_wages`` the sum of Anlage Z line 10. The credits and
	Vorauszahlungen come from the Steuerbescheinigungen and the notices, in cents.
	"""

	year: int
	lines: tuple[LedgerLine, ...]
	mapping: Mapping
	net_income: Decimal | None = None
	manual: tuple[ManualLine, ...] = ()
	holdings: tuple[HoldingResult, ...] = ()
	trading_book: bool = False
	loss_carry_forward: Decimal = ZERO
	loss_carry_back: Decimal | None = None
	derivatives_carry_forward: Decimal = ZERO
	donation_carry_forward: Decimal = ZERO
	eligible_donations: Decimal | None = None
	turnover_and_wages: Decimal | None = None
	capital_gains_tax_credit: Decimal = ZERO
	solz_credit: Decimal = ZERO
	kst_prepayments: Decimal = ZERO
	solz_prepayments: Decimal = ZERO

	def __post_init__(self) -> None:
		for name in ("lines", "manual", "holdings"):
			object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class KstResult:
	"""The computed lines of a VZ in the order of STEPS, and the results of the modules behind them."""

	year: Year
	lines: MappingProxyType[str, Line]
	classification: Classification
	p8b: P8b
	derivatives: Derivatives

	@property
	def business_income(self) -> Decimal:
		"""Anlage GK line 300."""
		return self.lines[BUSINESS_INCOME].declared


def compute(inputs: KstInputs, figures: Figures) -> KstResult:
	"""The Körperschaftsteuer of a VZ; see the module docstring."""
	year = year_of(inputs.year)
	classification = classify(inputs.lines, inputs.mapping)
	manual = _by_step(inputs.manual)
	lines: dict[str, Line] = {}
	for item in STEPS:
		if item.source in (Source.LEDGER, Source.MANUAL):
			exact = classification.amount(*item.categories) + _sum(manual.get(item.key, ()))
			lines[item.key] = Line(
				item,
				exact,
				half_up_euro(exact),
				classification.contributions(*item.categories),
				manual.get(item.key, ()),
			)
	net_income = (
		sum((line.credit - line.debit for line in inputs.lines), ZERO)
		if inputs.net_income is None
		else inputs.net_income
	) + _sum(manual.get("net_income", ()))
	lines["net_income"] = Line(
		step("net_income"), net_income, half_up_euro(net_income), (), manual.get("net_income", ())
	)

	pool = derivatives(
		year,
		classification.amount(Category.DERIVATIVES_GAIN),
		classification.amount(Category.DERIVATIVES_LOSS),
		inputs.derivatives_carry_forward,
	)
	_put(lines, "derivatives_loss", pool.added_back, classification)
	_put(lines, "derivatives_offset", pool.offset, classification)

	shares = p8b(
		year,
		dividends=classification.amount(Category.DIVIDENDS),
		holdings=inputs.holdings,
		gains=classification.amount(Category.SHARE_GAIN),
		sale_costs=classification.amount(Category.SHARE_SALE_COSTS),
		losses=classification.amount(Category.SHARE_LOSS),
		writedowns=classification.amount(Category.SHARE_WRITEDOWN),
		writeups=classification.amount(Category.SHARE_WRITEUP),
		trading_book=inputs.trading_book,
	)
	for key, name in _P8B_LINES:
		_put(lines, key, getattr(shares, name), classification)
	_put(lines, P8B_TOTAL, _total(P8B_TOTAL, lines))
	_put(lines, "investment_funds", Amount(ZERO, ZERO), classification)
	_put(lines, BUSINESS_INCOME, _total(BUSINESS_INCOME, lines))

	return KstResult(
		year,
		MappingProxyType({item.key: lines[item.key] for item in STEPS if item.key in lines}),
		classification,
		shares,
		pool,
	)


def _put(
	lines: dict[str, Line], key: str, amount: Amount, classification: Classification | None = None
) -> None:
	item = step(key)
	contributions = classification.contributions(*item.categories) if classification else ()
	lines[key] = Line(item, amount.exact, amount.declared, contributions)


def _total(key: str, lines: dict[str, Line]) -> Amount:
	"""The sum of the lines that feed the total, each with its sign: exact and declared."""
	feeding = [lines[item.key] for item in STEPS if item.total == key]
	return Amount(
		sum((line.step.sign * line.exact for line in feeding), ZERO),
		sum((line.step.sign * line.declared for line in feeding), ZERO),
	)


def _by_step(manual: Iterable[ManualLine]) -> dict[str, tuple[ManualLine, ...]]:
	grouped: dict[str, list[ManualLine]] = {}
	for line in manual:
		grouped.setdefault(line.step, []).append(line)
	return {key: tuple(lines) for key, lines in grouped.items()}


def _sum(manual: Iterable[ManualLine]) -> Decimal:
	return sum((line.amount for line in manual), ZERO)


def _is_cents(amount: Decimal) -> bool:
	return require_decimal(amount).is_finite() and amount == amount.quantize(CENT)
