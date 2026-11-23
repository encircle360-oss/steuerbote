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

A Finding is one sentence in German with its code and its reference, the shape of the findings of the annual
filings: an error holds the filing back from „Bereit“ (``KstResult.ready``), a hint changes nothing. The errors are
a trading account without class, a balance on a later category (foreign taxes, investment funds), a watched account
of the blocking level with a balance, dividends of the holdings beyond those of the ledger, a loss without
Verlustrücktrag or its waiver (rule 8900343) or with one beyond the loss or 1 Million Euro (8900124), Zuwendungen that
need the turnover of Anlage Z line 10 without it (8900101), and an Investitionsabzugsbetrag beyond 200 000 Euro
(§ 7g Absatz 1 Satz 4 EStG). The hints: a watched account of the hint level with a balance; entertainment booked as
deductible with nothing as non-deductible (§ 4 Absatz 5 Satz 1 Nummer 2 EStG), with the 30 % that the 70 % booked
imply; dividends of no holding, taxed as Streubesitz; the trading book of § 8b Absatz 7 KStG, which KSt 1 line 16
declares; a Solidaritätszuschlag of the Steuerbescheinigungen that is not 5.5 % of their Kapitalertragsteuer within
0.05 € (rule 8912019); Entgelte für Schulden of 3 Millionen Euro or more, from which the Zinsschranke of § 4h EStG and
§ 8a KStG may apply, which Steuerbote does not compute; an Investitionsabzugsbetrag with a profit beyond 200 000
Euro without it (§ 7g Absatz 1 Satz 2 Nummer 1 Buchstabe b EStG).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, StrEnum
from types import MappingProxyType

from steuerbote.kst.categories import Category, Classification, Contribution, Mapping, classify
from steuerbote.kst.holdings import Amount, HoldingResult, P8b, p8b
from steuerbote.kst.losses import (
	Derivatives,
	Donations,
	LossDeduction,
	derivatives,
	donations,
	loss_deduction,
)
from steuerbote.kst.years import HUNDRED, Year, year_of
from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import (
	CENT,
	ZERO,
	floor_euro,
	half_up_euro,
	require_decimal,
	to_cents,
	truncate_cents,
)


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


class Severity(Enum):
	ERROR = "Fehler"
	HINT = "Hinweis"


class Code(StrEnum):
	UNCLASSIFIED_TRADING = "KST-HANDEL-OHNE-KLASSE"
	FOREIGN_TAX = "KST-AUSLAENDISCHE-STEUERN"
	FUNDS = "KST-INVESTMENTFONDS"
	WATCHED = "KST-KONTO-OHNE-KATEGORIE"
	WATCHED_HINT = "KST-KONTO-BEOBACHTET"
	ENTERTAINMENT = "KST-BEWIRTUNG"
	STREUBESITZ = "KST-STREUBESITZ"
	EXCESS_DIVIDENDS = "KST-BEZUEGE-UEBER-HAUPTBUCH"
	TRADING_BOOK = "KST-8B-ABSATZ-7"
	CARRY_BACK_MISSING = "KST-VERLUSTRUECKTRAG-FEHLT"
	CARRY_BACK_TOO_HIGH = "KST-VERLUSTRUECKTRAG-ZU-HOCH"
	TURNOVER_MISSING = "KST-UMSATZ-FEHLT"
	SOLZ_ON_KAPEST = "KST-SOLZ-KAPEST"
	INTEREST_BARRIER = "KST-ZINSSCHRANKE"
	IAB_LIMIT = "KST-IAB-HOECHSTBETRAG"
	IAB_PROFIT = "KST-IAB-GEWINNGRENZE"


@dataclass(frozen=True, slots=True)
class Finding:
	"""A sentence in German on the filing; ``reference`` names its law or the rule of the Jahresdokumentation."""

	code: str
	severity: Severity
	text: str
	reference: str

	@property
	def blocking(self) -> bool:
		return self.severity is Severity.ERROR


# Rule 8912019 compares with „UngleichMitToleranz5“, 5 cents either way.
SOLZ_TOLERANCE = Decimal("0.05")
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
	donations: Donations
	losses: LossDeduction
	findings: tuple[Finding, ...]

	@property
	def ready(self) -> bool:
		"""No finding holds the filing back."""
		return not any(finding.blocking for finding in self.findings)

	@property
	def business_income(self) -> Decimal:
		"""Anlage GK line 300."""
		return self.lines[BUSINESS_INCOME].declared

	@property
	def sum_of_income(self) -> Decimal:
		"""Anlage ZVE line 32, the base of the Gewerbesteuer."""
		return self.lines["sum_of_income"].declared

	@property
	def total_income(self) -> Decimal:
		"""Anlage ZVE line 53."""
		return self.lines["total_income"].declared

	@property
	def zve(self) -> Decimal:
		"""Anlage ZVE line 70."""
		return self.lines["zve"].declared

	@property
	def kst(self) -> Decimal:
		"""Anlage ZVE line 71, the festzusetzende Körperschaftsteuer."""
		return self.lines["corporate_income_tax"].declared

	@property
	def kst_balance(self) -> Decimal:
		"""The Abschlusszahlung of Körperschaftsteuer, a refund below zero (§ 36 Absatz 4 EStG)."""
		return self.lines["kst_balance"].declared

	@property
	def solz(self) -> Decimal:
		"""The Solidaritätszuschlag: 5.5 % of the festzusetzende Körperschaftsteuer, the fractions of a cent dropped."""
		return self.lines["solz"].declared

	@property
	def solz_balance(self) -> Decimal:
		"""The Abschlusszahlung of Solidaritätszuschlag, a refund below zero."""
		return self.lines["solz_balance"].declared


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

	business_income = lines[BUSINESS_INCOME]
	_put(lines, "business_income_zve", Amount(business_income.exact, business_income.declared))
	_put(lines, "foreign_tax_deduction", Amount(ZERO, ZERO))
	_put(lines, "sum_of_income", _total("sum_of_income", lines))
	gifts = donations(
		year,
		lines["sum_of_income"].declared,
		max(classification.amount(Category.DONATIONS), ZERO)
		if inputs.eligible_donations is None
		else inputs.eligible_donations,
		inputs.donation_carry_forward,
		inputs.turnover_and_wages,
	)
	_put(lines, "donation_deduction", Amount(gifts.deductible, gifts.deductible), classification)
	_put(lines, "total_income", _total("total_income", lines))
	losses = loss_deduction(
		year, lines["total_income"].declared, inputs.loss_carry_forward, inputs.loss_carry_back
	)
	_put(lines, "loss_deduction", Amount(losses.deduction, losses.deduction))
	_put(lines, "zve", _total("zve", lines))
	taxed = max(lines["zve"].declared, ZERO) * year.rate / HUNDRED
	_put(lines, "corporate_income_tax", Amount(taxed, floor_euro(taxed)))
	for key in ("capital_gains_tax_credit", "kst_prepayments", "solz_credit", "solz_prepayments"):
		given = getattr(inputs, key)
		if not _is_cents(given) or given < ZERO:
			raise ValueError(f"{key} must be an amount in cents of at least 0, not {given}")
		_put(lines, key, Amount(given, given))
	_put(lines, "kst_remaining", _total("kst_remaining", lines))
	_put(lines, "kst_balance", _total("kst_balance", lines))
	surcharge = lines["corporate_income_tax"].declared * year.solz_rate / HUNDRED
	_put(lines, "solz", Amount(surcharge, truncate_cents(surcharge)))
	_put(lines, "solz_remaining", _total("solz_remaining", lines))
	_put(lines, "solz_balance", _total("solz_balance", lines))

	return KstResult(
		year,
		MappingProxyType({item.key: lines[item.key] for item in STEPS if item.key in lines}),
		classification,
		shares,
		pool,
		gifts,
		losses,
		_findings(inputs, year, lines, classification, shares, gifts, losses, figures),
	)


def _findings(
	inputs: KstInputs,
	year: Year,
	lines: dict[str, Line],
	classification: Classification,
	shares: P8b,
	gifts: Donations,
	losses: LossDeduction,
	figures: Figures,
) -> tuple[Finding, ...]:
	money = figures.money
	found: list[Finding] = []
	error, hint = Severity.ERROR, Severity.HINT
	for account in classification.unclassified:
		found.append(
			Finding(
				Code.UNCLASSIFIED_TRADING,
				error,
				f"Konto {account.account_number}: Das Handelsergebnis (Haben {money(account.credit)}, Soll "
				f"{money(account.debit)}) hat keine Klasse. Die Steuerberatung legt fest, ob es aus Anteilen, aus "
				"Termingeschäften, aus Investmentfonds oder aus voll steuerpflichtigen Geschäften stammt.",
				"§ 8b KStG, § 15 Absatz 4 Satz 3 EStG, § 20 InvStG",
			)
		)
	if Category.FOREIGN_TAX in classification.later:
		amount = money(classification.amount(Category.FOREIGN_TAX))
		found.append(
			Finding(
				Code.FOREIGN_TAX,
				error,
				f"Auf ausländische Steuern sind {amount} gebucht. Ihre Anrechnung oder ihren Abzug mit der Anlage "
				"AESt berechnet Steuerbote noch nicht.",
				"§ 26 KStG, § 34c EStG",
			)
		)
	if Category.FUNDS in classification.later:
		amount = money(classification.amount(Category.FUNDS))
		found.append(
			Finding(
				Code.FUNDS,
				error,
				f"Das Ergebnis aus Investmentfonds beträgt {amount}. Die Teilfreistellung berechnet Steuerbote noch "
				"nicht.",
				"§ 20 InvStG",
			)
		)
	for account in classification.watched:
		found.append(
			Finding(
				Code.WATCHED,
				error,
				f"Konto {account.account_number} hat einen Saldo (Soll {money(account.debit)}, Haben "
				f"{money(account.credit)}), aber keine Kategorie der Kontenzuordnung Ertragsteuern.",
				"Kontenzuordnung Ertragsteuern",
			)
		)
	for account in classification.hinted:
		found.append(
			Finding(
				Code.WATCHED_HINT,
				hint,
				f"Konto {account.account_number} hat einen Saldo (Soll {money(account.debit)}, Haben "
				f"{money(account.credit)}); die Kontenzuordnung Ertragsteuern beobachtet es.",
				"Kontenzuordnung Ertragsteuern",
			)
		)
	deductible = classification.amount(Category.ENTERTAINMENT_DEDUCTIBLE)
	if deductible > ZERO and not classification.amount(Category.ENTERTAINMENT_NONDEDUCTIBLE):
		share = year.entertainment_deductible_percent
		implied = to_cents(deductible * (HUNDRED - share) / share)
		found.append(
			Finding(
				Code.ENTERTAINMENT,
				hint,
				f"Auf abzugsfähige Bewirtungskosten sind {money(deductible)} gebucht, auf nicht abzugsfähige nichts. "
				f"Sind die gebuchten Kosten die abzugsfähigen {share} %, sind {money(implied)} nicht abziehbar.",
				"§ 4 Absatz 5 Satz 1 Nummer 2 EStG",
			)
		)
	if shares.unassigned_dividends:
		found.append(
			Finding(
				Code.STREUBESITZ,
				hint,
				f"Bezüge von {money(shares.unassigned_dividends)} gehören zu keiner Beteiligung der Einstellungen und "
				"bleiben als Streubesitz steuerpflichtig. Eine Beteiligung von mindestens 10 % zu Beginn des "
				"Kalenderjahres gehört in die Einstellungen.",
				"§ 8b Absatz 4 Satz 1 KStG",
			)
		)
	if shares.excess_dividends:
		found.append(
			Finding(
				Code.EXCESS_DIVIDENDS,
				error,
				f"Die Beteiligungen nennen {money(shares.excess_dividends)} mehr Bezüge, als das Hauptbuch auf den "
				"Konten der Bezüge aus Anteilen hat.",
				"§ 8b Absatz 1 KStG",
			)
		)
	if inputs.trading_book:
		found.append(
			Finding(
				Code.TRADING_BOOK,
				hint,
				"Nach den Einstellungen gilt § 8b Absatz 7 KStG: Bezüge, Gewinne und Verluste aus Anteilen sind voll "
				"steuerpflichtig, und die Erklärung gibt das in KSt 1 Zeile 16 an.",
				"§ 8b Absatz 7 KStG",
			)
		)
	if losses.carry_back_missing:
		found.append(
			Finding(
				Code.CARRY_BACK_MISSING,
				error,
				f"Der Gesamtbetrag der Einkünfte ist negativ ({money(-losses.loss)}). Die Anlage Verluste braucht in "
				"Zeile 20 den Verlustrücktrag; 0 verzichtet auf ihn.",
				"§ 10d Absatz 1 EStG; Regel 8900343",
			)
		)
	if losses.carry_back_too_high:
		found.append(
			Finding(
				Code.CARRY_BACK_TOO_HIGH,
				error,
				f"Der Verlustrücktrag von {money(losses.carry_back or ZERO)} ist höher als der Verlust von "
				f"{money(losses.loss)} oder {money(year.loss_carry_back)}.",
				"§ 10d Absatz 1 Satz 1 EStG; Regel 8900124",
			)
		)
	if gifts.turnover_missing:
		found.append(
			Finding(
				Code.TURNOVER_MISSING,
				error,
				f"Die Zuwendungen von {money(gifts.available)} übersteigen {year.donation_income_percent} % der "
				"Summe der Einkünfte. Die Anlage Z braucht in Zeile 10 die Umsätze, Löhne und Gehälter des "
				"Kalenderjahres, gegebenenfalls 0.",
				"§ 9 Absatz 1 Nummer 2 KStG; Regel 8900101",
			)
		)
	expected = to_cents(inputs.capital_gains_tax_credit * year.solz_rate / HUNDRED)
	if inputs.capital_gains_tax_credit and abs(expected - inputs.solz_credit) > SOLZ_TOLERANCE:
		found.append(
			Finding(
				Code.SOLZ_ON_KAPEST,
				hint,
				f"Der Solidaritätszuschlag der Steuerbescheinigungen ({money(inputs.solz_credit)}) weicht von "
				f"{year.solz_rate} % der Kapitalertragsteuer ({money(expected)}) um mehr als "
				f"{money(SOLZ_TOLERANCE)} ab.",
				"§ 4 SolZG; Regel 8912019",
			)
		)
	interest = classification.amount(Category.INTEREST)
	if interest >= year.interest_barrier:
		found.append(
			Finding(
				Code.INTEREST_BARRIER,
				hint,
				f"Die Entgelte für Schulden betragen {money(interest)}. Ab {money(year.interest_barrier)} "
				"Nettozinsaufwand kann die Zinsschranke greifen, die Steuerbote nicht berechnet.",
				"§ 4h Absatz 2 Satz 1 Buchstabe a EStG, § 8a KStG",
			)
		)
	iab = lines["iab_deduction"].declared
	if iab > year.iab_total_limit:
		found.append(
			Finding(
				Code.IAB_LIMIT,
				error,
				f"Investitionsabzugsbeträge von {money(iab)} übersteigen den Höchstbetrag von "
				f"{money(year.iab_total_limit)} je Betrieb.",
				"§ 7g Absatz 1 Satz 4 EStG",
			)
		)
	added_back = sum((lines[key].declared for key in ("iab_addback", "iab_addback_2", "iab_addback_3")), ZERO)
	profit = lines[BUSINESS_INCOME].declared + iab - added_back
	if iab and profit > year.iab_profit_limit:
		found.append(
			Finding(
				Code.IAB_PROFIT,
				hint,
				f"Investitionsabzugsbeträge setzen einen Gewinn ohne sie von höchstens {money(year.iab_profit_limit)} "
				f"voraus; die Einkünfte ohne sie betragen {money(profit)}.",
				"§ 7g Absatz 1 Satz 2 Nummer 1 Buchstabe b EStG",
			)
		)
	return tuple(found)


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
