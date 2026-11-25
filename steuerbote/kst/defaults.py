"""The defaults of the Income Tax Mapping for the DATEV charts SKR03 and SKR04, editions valid for 2026.

Sources: DATEV-Kontenrahmen nach dem Bilanzrichtlinie-Umsetzungsgesetz, Standardkontenrahmen SKR 03 (Art.-Nr. 11174)
and SKR 04 (Art.-Nr. 11175), „Gültig für 2026“, with the column Programmverbindung (footnote 4) and the
„Erläuterungen zur Kennzeichnung von Konten für die Programmverbindung zwischen Rechnungswesen-Programmen und
Steuerprogrammen“; and ERPNext's own SKR03 and SKR04 templates (de_kontenplan_SKR03.json and de_kontenplan_SKR04.json,
version 16), which carry some accounts of older DATEV editions.

The column Programmverbindung marks with K and G „die Konten ..., die über die Schnittstelle in Rechnungswesen-
Programmen an das entsprechende Steuerprogramm ... Gewerbesteuer (G) und Körperschaftsteuer (K) weitergegeben und an
entsprechender Stelle der Steuerberechnung zu Grunde gelegt werden“. „Die Gewerbesteuer-Berechnung für Körperschaften
ist in das Produkt Körperschaftsteuer integriert. Daher ist an Konten mit gewerbesteuerlichem Merkmal auch ein „K“ für
diese Programmverbindung zu finden“: for a GmbH or UG the accounts marked K count, also for the Gewerbesteuer. An
account marked G alone is one of a partnership or of a natural person, but for those of the Grundsteuer of § 9
Nummer 1 GewStG and of the Zinsschranke of § 4h EStG, whose labels give them a place for a GmbH as well.

Every account the chart marks K or G has one place:
- a category of steuerbote.kst.categories, where its label settles what its balance is for the Körperschaftsteuer or
  the Gewerbesteuer; the category names the law, the label the account;
- watched at the level Sperrt, where the effect of its balance needs a decision of the company or its Steuerberatung,
  or a line by hand that Steuerbote does not compute, such as the Überleitung to the Steuerbilanz, an Organschaft or
  a Mitunternehmerschaft (REASONS);
- watched at the level Hinweis, where a balance asks for a look rather than a change, such as a Tantieme (REASONS);
- outside the mapping (OUTSIDE): the accounts of the equity that DATEV hands to KSt 1 F only („Das Konto wird in
  Körperschaftsteuer ausschließlich in die Positionen Eigen-/Nennkapital zum Schluss des vorangegangenen
  Wirtschaftsjahres übernommen“, footnote 17), the accounts of partnerships and natural persons, and SKR03 2130 to
  2139, which DATEV reserves.

Besides, the defaults hold accounts the chart does not mark: Bewirtungskosten, whose deductible 70 % give a hint
when nothing is booked as non-deductible; the accounts of the results of securities of the Umlaufvermögen and of the
valuation of Finanzmittelfonds, which hold the results of a GmbH that trades in financial instruments and get no
trading class (steuerbote.kst.categories); and the accounts of ERPNext's templates named in the comments of _ROWS.

The marks K and G extend to „die nachfolgenden Konten bis zum nächsten standardmäßig belegten Konto“. The defaults
do not follow that: ERPNext's SKR04 template puts older accounts into such gaps whose meaning differs, such as 7640
Gewerbesteuernachzahlungen Vorjahre after 7639 Anrechnung/Abzug ausländischer Quellensteuer, so each account has a
row of its own and an account of the company without one gets no default.

default_mapping() gives the Mapping of a chart, default_accounts() each account of it with its DATEV label, which
Vorgaben laden shows for the accounts a company lacks. NON_DEDUCTIBLE_DONATIONS names the Zuwendungen of line 92
that Anlage Z does not deduct. DATEV_EDITION and REVISION name the defaults, as in steuerbote.ustva.defaults.

This module is pure Python and never imports Frappe.
"""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from steuerbote.kst.categories import AccountRule, Category, Mapping
from steuerbote.ustva.mapping import WatchedAccount, WatchLevel

CHARTS = ("SKR03", "SKR04")
BLOCKING, HINT = WatchLevel.BLOCKING, WatchLevel.HINT

# The edition of the DATEV charts these defaults follow, and the revision of the defaults within it. Every change of
# the defaults raises REVISION, and a new edition starts it at 1 again, so that the same version always means the
# same defaults: test_defaults.py pins the content of each version.
DATEV_EDITION = 2026
REVISION = 2


class Reason(StrEnum):
	"""Why the defaults watch an account instead of giving it a category."""

	INTEREST_ON_TAXES = "interest_on_taxes"
	DISCOUNTING = "discounting"
	DEFERRED_TAXES = "deferred_taxes"
	LOAN_WRITEDOWN = "loan_writedown"
	REORGANISATION = "reorganisation"
	ORGANSCHAFT = "organschaft"
	PARTNERSHIP_SHARE = "partnership_share"
	HOLDING_SALE = "holding_sale"
	CAPITAL_REDUCTION = "capital_reduction"
	REINVESTMENT_SURCHARGE = "reinvestment_surcharge"
	PHOTOVOLTAICS = "photovoltaics"
	IAB_EARLIER = "iab_earlier"
	ZINSSCHRANKE = "zinsschranke"
	UEBERLEITUNG = "ueberleitung"
	TANTIEME = "tantieme"
	HOLDING_COSTS = "holding_costs"
	HOLDING_INCOME = "holding_income"
	SHARE_RESULTS = "share_results"


REASONS: MappingProxyType[Reason, str] = MappingProxyType(
	{
		Reason.INTEREST_ON_TAXES: (
			"Deductible interest under §§ 233a to 237 AO on taxes that are no taxes on income: whether GewSt 1 A line 50 "
			"takes it as Entgelt für Schulden (§ 8 Nummer 1 Buchstabe a GewStG), the Steuerberatung decides."
		),
		Reason.DISCOUNTING: (
			"The Abzinsung of provisions in the Handelsbilanz, which the Steuerbilanz does not follow (§ 6 Absatz 1 "
			"Nummer 3a Buchstabe e EStG): the Überleitung to the Steuerbilanz takes it back by hand, and it is no "
			"Entgelt für Schulden (H 8.1 (1) GewStH 2024, Aufzinsungsbeträge)."
		),
		Reason.DEFERRED_TAXES: (
			"Latente Steuern of the Handelsbilanz under § 274 HGB, or as a provision for passive latente Steuern under "
			"§ 249 Absatz 1 HGB, which the Steuerbilanz does not know: a line of the Überleitung by hand."
		),
		Reason.LOAN_WRITEDOWN: (
			"Gewinnminderungen of loans to a holding or a shareholder (§ 8b Absatz 3 Sätze 4 to 8 KStG), Anlage GK "
			"lines 187 and 189, which Steuerbote does not compute."
		),
		Reason.REORGANISATION: (
			"A Verschmelzung or another Umwandlung, whose result §§ 11 to 13 UmwStG settle for Körperschaften; "
			"Steuerbote does not compute it."
		),
		Reason.ORGANSCHAFT: (
			"The transfer of profits and losses of an Organschaft (§§ 14 to 19 KStG), which Steuerbote does not compute."
		),
		Reason.PARTNERSHIP_SHARE: (
			"A share in the result of a Mitunternehmerschaft, which its Feststellung gives and § 8 Nummer 8 and § 9 "
			"Nummer 2 GewStG correct; Steuerbote does not compute it."
		),
		Reason.HOLDING_SALE: (
			"The gain on the sale of a holding, exempt under § 8b Absatz 2 KStG for shares of a Körperschaft (Anlage GK "
			"lines 161 to 166b) and taxable for the share of a Mitunternehmerschaft: which, the Steuerberatung decides."
		),
		Reason.CAPITAL_REDUCTION: (
			"The Ertrag aus der Kapitalherabsetzung, which the Gewinn- und Verlustrechnung shows after the "
			"Jahresüberschuss (§ 240 Satz 1 AktG): a line by hand where the ledger counts it in the Jahresüberschuss."
		),
		Reason.REINVESTMENT_SURCHARGE: (
			"The Gewinnzuschlag of § 6b Absatz 7 and § 6c EStG, booked außerbilanziell: a line of Anlage GK by hand."
		),
		Reason.PHOTOVOLTAICS: (
			"The income of § 3 Nummer 72 EStG and its expenses under § 3c Absatz 1 EStG, booked außerbilanziell: a line "
			"of Anlage GK by hand."
		),
		Reason.IAB_EARLIER: (
			"The Hinzurechnung of Investitionsabzugsbeträge of the second and third previous Wirtschaftsjahr (§ 7g "
			"Absatz 2 Satz 1 EStG), Anlage GK lines 71 and 70, which steuerbote.kst.chain takes by hand."
		),
		Reason.ZINSSCHRANKE: "The Zinsschranke of § 4h EStG and § 8a KStG, which Steuerbote does not compute.",
		Reason.UEBERLEITUNG: (
			"The Gewinnkorrektur of § 60 Absatz 2 EStDV, the Überleitung to the Steuerbilanz: a line of Anlage GK line 11 "
			"by hand."
		),
		Reason.TANTIEME: (
			"A Tantieme may be a verdeckte Gewinnausschüttung (§ 8 Absatz 3 Satz 2 KStG), which Anlage GK lines 73 to 75 "
			"add back by hand."
		),
		Reason.HOLDING_COSTS: (
			"Costs of holdings, which reduce the Kürzung of a holding of at least 15 % in Anlage BEG lines 8 and 9 (§ 9 "
			"Nummer 2a Satz 3 GewStG); DATEV hands the account to the Körperschaftsteuer of an Organgesellschaft only "
			"(footnote 16)."
		),
		Reason.HOLDING_INCOME: (
			"Income from holdings of no named legal form: a dividend of a Kapitalgesellschaft is exempt under § 8b "
			"Absatz 1 KStG and § 9 Nummer 2a GewStG only on an account of the category Bezüge aus Anteilen, while the "
			"share of a Mitunternehmerschaft is taxed by its Feststellung; DATEV marks the account for neither, so its "
			"balance would count in full. The company books it apart or gives the account its category."
		),
		Reason.SHARE_RESULTS: (
			"Income, gains, losses and write-downs of securities and Finanzanlagen that may be Bezüge, Gewinne or "
			"Gewinnminderungen aus Anteilen an Kapitalgesellschaften (§ 8b Absätze 1 to 3 KStG), which DATEV marks only on "
			"their own accounts: a balance asks whether it holds such results, which then belong on those accounts."
		),
	}
)


class Outside(StrEnum):
	"""Why an account the chart marks K or G has no place in the mapping."""

	EQUITY = "equity"
	PARTNERSHIP = "partnership"
	RESERVED = "reserved"


@dataclass(frozen=True, slots=True)
class DefaultAccount:
	"""An account of the defaults of a chart with its DATEV label: its category, or the level it is watched at and
	why."""

	number: str
	label: str
	category: Category | None = None
	level: WatchLevel | None = None
	reason: Reason | None = None

	def __post_init__(self) -> None:
		if (self.category is None) == (self.level is None):
			raise ValueError(
				f"account {self.number}: a default has a category or a level, not both or neither"
			)
		if (self.level is None) != (self.reason is None):
			raise ValueError(f"account {self.number}: a watched default needs its reason, a rule has none")


@dataclass(frozen=True, slots=True)
class _Row:
	"""An account of SKR03 and its twin in SKR04, None where a chart has none, with the same place in both."""

	skr03: str | None
	skr04: str | None
	label: str
	label04: str
	category: Category | None = None
	level: WatchLevel | None = None
	reason: Reason | None = None

	def accounts(self) -> tuple[DefaultAccount | None, DefaultAccount | None]:
		place = {"category": self.category, "level": self.level, "reason": self.reason}
		return (
			None if self.skr03 is None else DefaultAccount(self.skr03, self.label, **place),
			None if self.skr04 is None else DefaultAccount(self.skr04, self.label04 or self.label, **place),
		)


def _rule(skr03: str | None, skr04: str | None, category: Category, label: str, label04: str = "") -> _Row:
	return _Row(skr03, skr04, label, label04, category=category)


def _watch(
	skr03: str | None, skr04: str | None, level: WatchLevel, reason: Reason, label: str, label04: str = ""
) -> _Row:
	return _Row(skr03, skr04, label, label04, level=level, reason=reason)


# The accounts in SKR03 and SKR04 with the DATEV label of the SKR03 account, and that of the SKR04 account where it
# reads otherwise; the label of an account of ERPNext's templates is that of the template.
_ROWS: tuple[_Row, ...] = (
	# Anlage GK lines 81 to 84 and 87: the taxes on income, which § 10 Nummer 2 KStG and § 4 Absatz 5b EStG do not let
	# reduce the income; with their refunds of earlier years on the other side. The foreign taxes are a later module.
	_rule("2200", "7600", Category.KST, "Körperschaftsteuer"),
	_rule("2203", "7603", Category.KST, "Körperschaftsteuer für Vorjahre"),
	_rule("2204", "7604", Category.KST, "Körperschaftsteuererstattungen für Vorjahre"),
	_rule("2208", "7608", Category.SOLZ, "Solidaritätszuschlag"),
	_rule("2209", "7609", Category.SOLZ, "Solidaritätszuschlag für Vorjahre"),
	_rule("2210", "7607", Category.SOLZ, "Solidaritätszuschlagerstattungen für Vorjahre"),
	_rule("2216", "7633", Category.SOLZ, "Anrechenbarer Solidaritätszuschlag auf Kapitalertragsteuer 25 %"),
	_rule("2213", "7630", Category.KAPEST, "Kapitalertragsteuer 25 %"),
	_rule("4320", "7610", Category.GEWST, "Gewerbesteuer"),
	_rule(
		"2281",
		"7641",
		Category.GEWST,
		"Gewerbesteuernachzahlungen und Gewerbesteuererstattungen für Vorjahre nach § 4 Abs. 5b EStG",
	),
	_rule(
		"2283",
		"7643",
		Category.GEWST,
		"Erträge aus der Auflösung von Gewerbesteuerrückstellungen nach § 4 Abs. 5b EStG",
	),
	# Older DATEV accounts of ERPNext's SKR04 template for the Gewerbesteuer of earlier years.
	_rule(None, "7640", Category.GEWST, "Gewerbesteuernachzahlungen Vorjahre"),
	_rule(None, "7642", Category.GEWST, "Gewerbesteuererstattungen Vorjahre"),
	_rule(None, "7644", Category.GEWST, "Erträge aus der Auflösung von Gewerbesteuerrückstellungen"),
	_rule(
		"2218", "7638", Category.FOREIGN_TAX, "Ausländische Steuer auf im Inland steuerfreie DBA-Einkünfte"
	),
	_rule(
		"2219",
		"7639",
		Category.FOREIGN_TAX,
		"Anrechnung/Abzug ausländische Quellensteuer",
		"Anrechnung/Abzug ausländischer Quellensteuer",
	),
	# Line 88: the Nebenleistungen to these taxes; refunded Nachzahlungszinsen of the Gewerbesteuer (2653, SKR04 7107)
	# and of the other taxes (2658, SKR04 7106) reduce them, since a Körperschaft treats them „erfolgsneutral“ (R 10.1
	# Absatz 2 Satz 3 KStR 2022), while Erstattungszinsen stay taxable (Satz 2) on 2657 (SKR04 7105).
	_rule(
		"2102",
		"7302",
		Category.ANCILLARY,
		"Steuerlich nicht abzugsfähige andere Nebenleistungen zu Steuern § 4 Abs. 5b EStG",
	),
	_rule(
		"2104", "7304", Category.ANCILLARY, "Steuerlich nicht abzugsfähige andere Nebenleistungen zu Steuern"
	),
	_rule("2105", "7308", Category.ANCILLARY, "Zinsaufwendungen § 233a AO nicht abzugsfähig"),
	_rule("2108", "7306", Category.ANCILLARY, "Zinsaufwendungen §§ 234 bis 237 AO nicht abzugsfähig"),
	_rule(
		"4397",
		"6437",
		Category.ANCILLARY,
		"Steuerlich nicht abzugsfähige Verspätungszuschläge und Zwangsgelder",
	),
	_rule("2658", "7106", Category.ANCILLARY, "Zinserträge § 233a AO, steuerfrei (Anlage GK KSt)"),
	_rule("2653", "7107", Category.ANCILLARY, "Zinserträge § 233a AO und § 4 Abs. 5b EStG, steuerfrei"),
	# Line 89: the half of the Aufsichtsratsvergütungen that § 10 Nummer 4 KStG does not let deduct; DATEV books the
	# deductible half on 2386 (SKR04 6876), which has no category.
	_rule("2385", "6875", Category.SUPERVISORY_BOARD, "Nicht abziehbare Hälfte der Aufsichtsratsvergütungen"),
	# Line 90: non-deductible expenses; the deductible 70 % of the Bewirtungskosten only give a hint when nothing is
	# booked as non-deductible (steuerbote.kst.chain), and DATEV does not mark that account.
	_rule("4635", "6620", Category.GIFTS_NONDEDUCTIBLE, "Geschenke nicht abzugsfähig ohne § 37b EStG"),
	_rule("4636", "6621", Category.GIFTS_NONDEDUCTIBLE, "Geschenke nicht abzugsfähig mit § 37b EStG"),
	_rule(
		"4637",
		"6622",
		Category.GIFTS_NONDEDUCTIBLE,
		"Pauschale Steuer für Geschenke und Zuwendungen nicht abzugsfähig",
	),
	_rule("4654", "6644", Category.ENTERTAINMENT_NONDEDUCTIBLE, "Nicht abzugsfähige Bewirtungskosten"),
	_rule(
		"4652",
		"6642",
		Category.OTHER_NONDEDUCTIBLE,
		"Sonstige eingeschränkt abziehbare Betriebsausgaben (nicht abziehbarer Anteil)",
	),
	_rule(
		"4655",
		"6645",
		Category.OTHER_NONDEDUCTIBLE,
		"Nicht abzugsfähige Betriebsausgaben aus Werbe- und Repräsentationskosten",
	),
	_rule("2308", "6968", Category.OTHER_NONDEDUCTIBLE, "Sonstige nicht abziehbare Aufwendungen"),
	# An older DATEV account of ERPNext's SKR03 template.
	_rule(
		"4665",
		None,
		Category.OTHER_NONDEDUCTIBLE,
		"nicht abzugsfähige Betriebsausg. aus Werbe-, Repräs.- u. Reisekosten",
	),
	_rule("4650", "6640", Category.ENTERTAINMENT_DEDUCTIBLE, "Bewirtungskosten"),
	# Line 92: all Zuwendungen; NON_DEDUCTIBLE_DONATIONS names those that Anlage Z does not deduct.
	_rule("2380", "6390", Category.DONATIONS, "Zuwendungen, Spenden, steuerlich nicht abziehbar"),
	_rule(
		"2381", "6391", Category.DONATIONS, "Zuwendungen, Spenden für wissenschaftliche und kulturelle Zwecke"
	),
	_rule("2382", "6392", Category.DONATIONS, "Zuwendungen, Spenden für mildtätige Zwecke"),
	_rule(
		"2383",
		"6393",
		Category.DONATIONS,
		"Zuwendungen, Spenden für kirchliche, religiöse und gemeinnützige Zwecke",
	),
	_rule("2384", "6394", Category.DONATIONS, "Zuwendungen, Spenden an politische Parteien"),
	_rule(
		"2387",
		"6395",
		Category.DONATIONS,
		"Zuwendungen, Spenden in das zu erhaltende Vermögen (Vermögensstock) einer Stiftung für gemeinnützige Zwecke",
	),
	_rule(
		None,
		"6396",
		Category.DONATIONS,
		"Zuwendungen, Spenden an Stiftungen f. gemeinnützige Zwecke i. S. d. § 52 Abs. 2 Nr. 4 AO",
	),
	_rule(
		"2389",
		"6397",
		Category.DONATIONS,
		"Zuwendungen, Spenden in das zu erhaltende Vermögen (Vermögensstock) einer Stiftung für kirchliche, religiöse und gemeinnützige Zwecke",
	),
	_rule(
		"2390",
		"6398",
		Category.DONATIONS,
		"Zuwendungen, Spenden an Stiftungen in das zu erhaltende Vermögen (Vermögensstock) für wissenschaftliche, mildtätige, kulturelle Zwecke",
	),
	# Lines 96 and 102: the Investitionszulage and other tax-free income.
	_rule("2744", "4980", Category.INVESTMENT_GRANT, "Investitionszulagen (steuerfrei)"),
	_rule(
		"2746", "4981", Category.TAX_FREE, "Steuerfreie Erträge aus der Auflösung von steuerlichen Rücklagen"
	),
	_rule("2747", "4982", Category.TAX_FREE, "Sonstige steuerfreie Betriebseinnahmen"),
	# § 8b KStG, lines 151 to 201: DATEV passes these accounts as wholly exempt or non-deductible and leaves the 5 % to
	# the computation (footnote 9), as steuerbote.kst.holdings does. A sale at a gain books its price and the book value
	# on two accounts of share_gain, one at a loss on two of share_loss.
	_rule(
		"2615",
		"7005",
		Category.DIVIDENDS,
		"Erträge aus Anteilen an Kapitalgesellschaften (Beteiligung) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 KStG",
	),
	_rule(
		"2616",
		"7006",
		Category.DIVIDENDS,
		"Erträge aus Anteilen an Kapitalgesellschaften (verbundene Unternehmen) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 KStG",
	),
	_rule(
		"2625",
		"7014",
		Category.DIVIDENDS,
		"Erträge aus Anteilen an Kapitalgesellschaften (Finanzanlagevermögen) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 und 4 KStG",
	),
	_rule(
		"2626",
		"7015",
		Category.DIVIDENDS,
		"Erträge aus Anteilen an Kapitalgesellschaften (verbundene Unternehmen) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 KStG",
	),
	_rule(
		"2655",
		"7103",
		Category.DIVIDENDS,
		"Erträge aus Anteilen an Kapitalgesellschaften (Umlaufvermögen) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 und 4 KStG",
	),
	_rule(
		"2656",
		"7104",
		Category.DIVIDENDS,
		"Erträge aus Anteilen an Kapitalgesellschaften (verbundene Unternehmen) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 KStG",
	),
	# An older DATEV account of ERPNext's SKR04 template for dividends that § 9 Nummer 2a GewStG cuts.
	_rule(
		None,
		"7007",
		Category.DIVIDENDS,
		"Sonstige GewSt-freie Gewinne aus Anteilen an einer Kap.Ges. (Kürzung gem. § 9 Nr. 2a GewStG)",
	),
	_rule(
		"2726",
		"4906",
		Category.SHARE_GAIN,
		"Erträge aus dem Abgang von Gegenständen des Umlaufvermögens (außer Vorräte) § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG",
	),
	_rule(
		"2724",
		"4904",
		Category.SHARE_GAIN,
		"Abgänge Wertpapiere des Umlaufvermögens § 8b Abs. 2 KStG (Buchwert bei Buchgewinn)",
	),
	_rule(
		"8839",
		"4852",
		Category.SHARE_GAIN,
		"Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG (bei Buchgewinn)",
	),
	_rule(
		"2318",
		"4858",
		Category.SHARE_GAIN,
		"Anlagenabgänge Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG (Restbuchwert bei Buchgewinn)",
	),
	_rule(
		"8852",
		"4867",
		Category.SHARE_GAIN,
		"Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG und § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG",
		"Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG, § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG",
	),
	# Older DATEV accounts of ERPNext's SKR04 template for the sale of shares of a Körperschaft.
	_rule(
		None,
		"4901",
		Category.SHARE_GAIN,
		"Erträge aus der Veräußerung von Anteilen an Kap.Ges. (Finanzanlageverm., inländ. Kap.Ges.)",
	),
	_rule(
		None,
		"6903",
		Category.SHARE_LOSS,
		"Verluste aus der Veräußerung von Anteilen an Kap.Ges. (Finanzanlagevermögen, inl. Kap.Ges.)",
	),
	_rule(
		"2326",
		"6906",
		Category.SHARE_LOSS,
		"Verluste aus dem Abgang von Gegenständen des Umlaufvermögens (außer Vorräte) § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG",
	),
	_rule(
		"2324",
		"6904",
		Category.SHARE_LOSS,
		"Abgänge Wertpapiere des Umlaufvermögens § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (Buchwert bei Buchverlust)",
	),
	_rule(
		"8819",
		"6892",
		Category.SHARE_LOSS,
		"Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (bei Buchverlust)",
	),
	_rule(
		"2313",
		"6898",
		Category.SHARE_LOSS,
		"Anlagenabgänge Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V m. § 8b Abs. 3 S. 3 KStG (Restbuchwert bei Buchverlust)",
		"Anlagenabgänge Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (Restbuchwert bei Buchverlust)",
	),
	_rule(
		"2328",
		"6908",
		Category.SHARE_LOSS,
		"Abgang von Wirtschaftsgütern des Umlaufvermögens § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG nach § 4 Abs. 3 S. 4 EStG",
	),
	_rule(
		"4976",
		"6857",
		Category.SHARE_SALE_COSTS,
		"Veräußerungskosten § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG (bei Buchgewinn)",
	),
	_rule(
		"4977",
		"6858",
		Category.SHARE_SALE_COSTS,
		"Veräußerungskosten § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (bei Buchverlust)",
		"Veräußerungskosten § 3 Nr. 40 EStG bzw. § 8b Abs. 2 i. V. m. § 8b Abs. 3 S. 3 KStG (bei Buchverlust)",
	),
	_rule(
		"2713",
		"4913",
		Category.SHARE_WRITEUP,
		"Erträge aus Zuschreibungen des Finanzanlagevermögens § 3 Nr. 40 EStG bzw. § 8b Abs. 3 S. 9 KStG",
	),
	_rule(
		"2714",
		"4914",
		Category.SHARE_WRITEUP,
		"Erträge aus Zuschreibungen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG",
	),
	_rule(
		"2716",
		"4916",
		Category.SHARE_WRITEUP,
		"Erträge aus Zuschreibungen des Umlaufvermögens § 3 Nr. 40 EStG bzw. § 8b Abs. 3 S. 9 KStG",
	),
	_rule(
		"4871",
		"7204",
		Category.SHARE_WRITEDOWN,
		"Abschreibungen auf Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 3 KStG (dauerhaft)",
	),
	_rule(
		"4873",
		"7255",
		Category.SHARE_WRITEDOWN,
		"Abschreibungen auf Finanzanlagen auf Grund § 6b EStG-Rücklage, § 3 Nr. 40 EStG bzw. § 8b Abs. 3 KStG",
	),
	_rule(
		"4876",
		"7214",
		Category.SHARE_WRITEDOWN,
		"Abschreibungen auf Wertpapiere des Umlaufvermögens § 3 Nr. 40 EStG bzw. § 8b Abs. 3 KStG",
	),
	# The results of trading in financial instruments, which a GmbH that trades books on these accounts. They get no class:
	# whether a result is one of shares, of Termingeschäfte, of investment funds or fully taxable, the Steuerberatung
	# decides, and until then the account holds the filing back (steuerbote.kst.categories). DATEV does not mark them.
	_rule(
		"2654",
		"7115",
		Category.TRADING_UNCLASSIFIED,
		"Erträge aus anderen Wertpapieren und Ausleihungen des Umlaufvermögens",
	),
	_rule("2166", "6883", Category.TRADING_UNCLASSIFIED, "Aufwendungen aus Bewertung Finanzmittelfonds"),
	# § 7g EStG, Anlage GK lines 67 and 72, booked außerbilanziell; the Gegenkonten 9971 and 9973 have no category.
	_rule(
		"9970",
		"9970",
		Category.IAB_DEDUCTION,
		"Investitionsabzugsbetrag § 7g Abs. 1 EStG, außerbilanziell (Soll)",
	),
	_rule(
		"9972",
		"9972",
		Category.IAB_ADDBACK,
		"Hinzurechnung Investitionsabzugsbetrag § 7g Abs. 2 EStG aus dem vorangegangenen Wirtschaftsjahr, außerbilanziell (Haben)",
	),
	# GewSt 1 A lines 50 to 57: the financing parts of § 8 Nummer 1 GewStG, declared in full. Interest a GmbH pays to
	# its shareholders (2114, 2117) is Entgelt für Schulden as well; DATEV marks these accounts K alone, since it
	# computes the Gewerbesteuer of a Körperschaft in its program of the Körperschaftsteuer.
	_rule("2100", "7300", Category.INTEREST, "Zinsen und ähnliche Aufwendungen"),
	_rule("2109", "7309", Category.INTEREST, "Zinsaufwendungen an verbundene Unternehmen"),
	_rule("2110", "7310", Category.INTEREST, "Zinsaufwendungen für kurzfristige Verbindlichkeiten"),
	_rule("2114", "7316", Category.INTEREST, "Zinsen für Gesellschafterdarlehen"),
	_rule(
		"2115",
		"7350",
		Category.INTEREST,
		"Zinsen und ähnliche Aufwendungen §§ 3 Nr. 40 und 3c EStG bzw. § 8b Abs. 1 und 4 KStG",
	),
	_rule(
		"2116",
		"7351",
		Category.INTEREST,
		"Zinsen und ähnliche Aufwendungen an verbundene Unternehmen §§ 3 Nr. 40 und 3c EStG bzw. § 8b Abs. 1 KStG",
	),
	_rule(
		"2117",
		"7317",
		Category.INTEREST,
		"Zinsen an Gesellschafter mit einer Beteiligung von mehr als 25 % bzw. diesen nahe stehende Personen",
	),
	_rule("2118", "7318", Category.INTEREST, "Zinsen auf Kontokorrentkonten"),
	_rule(
		"2119",
		"7319",
		Category.INTEREST,
		"Zinsaufwendungen für kurzfristige Verbindlichkeiten an verbundene Unternehmen",
	),
	_rule("2120", "7320", Category.INTEREST, "Zinsaufwendungen für langfristige Verbindlichkeiten"),
	# An account of ERPNext's SKR03 template.
	_rule("2121", None, Category.INTEREST, "Zinsaufwendungen für KFZ Finanzierung"),
	_rule(
		"2123", "7323", Category.INTEREST, "Abschreibungen auf ein Agio oder Disagio/Damnum zur Finanzierung"
	),
	_rule(
		"2124",
		"7324",
		Category.INTEREST,
		"Abschreibungen auf ein Agio oder Disagio/Damnum zur Finanzierung des Anlagevermögens",
	),
	_rule(
		"2125", "7325", Category.INTEREST, "Zinsaufwendungen für Gebäude, die zum Betriebsvermögen gehören"
	),
	_rule("2126", "7326", Category.INTEREST, "Zinsen zur Finanzierung des Anlagevermögens"),
	_rule(
		"2129",
		"7329",
		Category.INTEREST,
		"Zinsaufwendungen für langfristige Verbindlichkeiten an verbundene Unternehmen",
	),
	# Diskontbeträge count as Entgelte für Schulden (§ 8 Nummer 1 Buchstabe a Satz 2 GewStG): older DATEV accounts of
	# ERPNext's SKR04 template, reserved in the edition for 2026.
	_rule(None, "7340", Category.INTEREST, "Diskontaufwendungen"),
	_rule(None, "7349", Category.INTEREST, "Diskontaufwendungen an verb. Unternehmen"),
	# Bauzeitzinsen that are capitalised are no Entgelte für Schulden (H 8.1 (1) GewStH 2024): they reduce the interest.
	_rule(
		"8994",
		"4824",
		Category.INTEREST,
		"Aktivierte Eigenleistungen (den Herstellungskosten zurechenbare Fremdkapitalzinsen)",
	),
	# Renten und dauernde Lasten (Buchstabe b) and the shares of a typisch stiller Gesellschafter (Buchstabe c).
	_rule("2127", "7327", Category.ANNUITIES, "Renten und dauernde Lasten"),
	_rule(
		"2493",
		"7399",
		Category.SILENT_PARTNER,
		"Abgeführte Gewinnanteile (Soll) /ausgeglichene Verlustanteile (Haben) bei typisch stiller Beteiligung § 8 GewStG",
	),
	# Rent and leasing of movable assets (Buchstabe d), of electric vehicles and bicycles at half of it until 2030
	# (Buchstabe d Satz 2), of immovable assets (Buchstabe e), also when paid to a shareholder, and licences
	# (Buchstabe f).
	_rule(
		"3170",
		"5970",
		Category.RENT_MOVABLE,
		"Fremdleistungen (Miet- und Pachtzinsen bewegliche Wirtschaftsgüter)",
	),
	_rule("4570", "6560", Category.RENT_MOVABLE, "Mietleasing Kfz"),
	_rule(
		"4810",
		"6498",
		Category.RENT_MOVABLE,
		"Mietleasing bewegliche Wirtschaftsgüter für technische Anlagen und Maschinen",
	),
	_rule(
		"4958",
		"6833",
		Category.RENT_MOVABLE,
		"Vergütungen an Gesellschafter für die miet- oder pachtweise Überlassung ihrer beweglichen Wirtschaftsgüter",
	),
	_rule("4960", "6835", Category.RENT_MOVABLE, "Mieten für Einrichtungen (bewegliche Wirtschaftsgüter)"),
	_rule("4961", "6836", Category.RENT_MOVABLE, "Pacht (bewegliche Wirtschaftsgüter)"),
	_rule(
		"4963",
		"6838",
		Category.RENT_MOVABLE,
		"Aufwendungen für gemietete oder gepachtete bewegliche Wirtschaftsgüter, die gewerbesteuerlich hinzuzurechnen sind",
	),
	_rule(
		"4965",
		"6840",
		Category.RENT_MOVABLE,
		"Mietleasing bewegliche Wirtschaftsgüter für Betriebs- und Geschäftsausstattung",
	),
	_rule(
		"4575",
		"6565",
		Category.RENT_MOVABLE_EV,
		"Mietleasingaufwendungen für Elektrofahrzeuge und Fahrräder, die gewerbesteuerlich hinzuzurechnen sind",
	),
	_rule(
		"3175",
		"5975",
		Category.RENT_IMMOVABLE,
		"Fremdleistungen (Miet- und Pachtzinsen unbewegliche Wirtschaftsgüter)",
	),
	_rule("4210", "6310", Category.RENT_IMMOVABLE, "Miete (unbewegliche Wirtschaftsgüter)"),
	_rule(
		"4211",
		"6317",
		Category.RENT_IMMOVABLE,
		"Aufwendungen für gemietete oder gepachtete unbewegliche Wirtschaftsgüter, die gewerbesteuerlich hinzuzurechnen sind",
	),
	_rule("4215", "6316", Category.RENT_IMMOVABLE, "Leasing (unbewegliche Wirtschaftsgüter)"),
	_rule("4220", "6315", Category.RENT_IMMOVABLE, "Pacht (unbewegliche Wirtschaftsgüter)"),
	_rule(
		"4222",
		"6313",
		Category.RENT_IMMOVABLE,
		"Vergütungen an Gesellschafter für die miet- oder pachtweise Überlassung ihrer unbeweglichen Wirtschaftsgüter",
	),
	_rule("4550", "6550", Category.RENT_IMMOVABLE, "Garagenmiete"),
	_rule("3180", "5980", Category.LICENCES, "Fremdleistungen (Entgelte für Rechte und Lizenzen)"),
	_rule(
		"4964",
		"6837",
		Category.LICENCES,
		"Aufwendungen für die zeitlich befristete Überlassung von Rechten (Lizenzen, Konzessionen)",
	),
	# GewSt 1 A line 87: the Grundsteuer of the company's own property, which § 9 Nummer 1 Satz 1 GewStG cuts from EZ
	# 2025. DATEV marks it G alone.
	_rule("2375", "7680", Category.PROPERTY_TAX_OWN, "Grundsteuer"),
	# Watched at the level Sperrt: the effect of these accounts needs a decision or a line by hand (REASONS).
	_watch("2107", "7305", BLOCKING, Reason.INTEREST_ON_TAXES, "Zinsaufwendungen § 233a AO abzugsfähig"),
	_watch(
		"2111", "7311", BLOCKING, Reason.INTEREST_ON_TAXES, "Zinsaufwendungen §§ 234 bis 237 AO abzugsfähig"
	),
	_watch(
		"2148",
		"7366",
		BLOCKING,
		Reason.DISCOUNTING,
		"Steuerlich nicht abzugsfähige Zinsaufwendungen aus der Abzinsung von Rückstellungen",
	),
	_watch(
		"2682",
		"7140",
		BLOCKING,
		Reason.DISCOUNTING,
		"Steuerfreie Zinserträge aus der Abzinsung von Rückstellungen",
	),
	_watch(
		"2250",
		"7645",
		BLOCKING,
		Reason.DEFERRED_TAXES,
		"Aufwendungen aus der Zuführung und Auflösung von latenten Steuern",
	),
	_watch(
		"2255",
		"7649",
		BLOCKING,
		Reason.DEFERRED_TAXES,
		"Erträge aus der Zuführung und Auflösung von latenten Steuern",
	),
	_watch(
		"2260",
		"7646",
		BLOCKING,
		Reason.DEFERRED_TAXES,
		"Aufwendungen aus der Zuführung zu Steuerrückstellungen für Steuerstundung (BStBK)",
	),
	_watch(
		"2265",
		"7648",
		BLOCKING,
		Reason.DEFERRED_TAXES,
		"Erträge aus der Auflösung von Steuerrückstellungen für Steuerstundung (BStBK)",
	),
	# Older DATEV accounts of ERPNext's SKR04 template, whose numbers the edition for 2026 reserves.
	_watch(None, "7464", BLOCKING, Reason.DEFERRED_TAXES, "Außerordentliche Erträge: latente Steuern"),
	_watch(
		None,
		"7563",
		BLOCKING,
		Reason.DEFERRED_TAXES,
		"Außerordentliche Aufwendungen aus der Anwendung von Übergangsvorschriften (Latente Steuern)",
	),
	_watch(
		None,
		"7452",
		BLOCKING,
		Reason.HOLDING_SALE,
		"Erträge durch den Verkauf von bedeutenden Beteiligungen",
	),
	_watch(
		"2440",
		"6290",
		BLOCKING,
		Reason.LOAN_WRITEDOWN,
		"Abschreibungen auf Forderungen gegenüber Kapitalgesellschaften, an denen eine Beteiligung besteht (soweit unüblich hoch), § 3c EStG bzw. § 8b Abs. 3 KStG",
	),
	_watch(
		"2441",
		"6291",
		BLOCKING,
		Reason.LOAN_WRITEDOWN,
		"Abschreibungen auf Forderungen gegenüber Gesellschaftern und nahestehende Personen (soweit unüblich hoch), § 3 Nr. 40 EStG bzw. § 8b Abs. 3 KStG",
		"Abschreibungen auf Forderungen gegenüber Gesellschaftern und nahe stehende Personen (soweit unüblich hoch), § 3 Nr. 40 EStG bzw. § 8b Abs. 3 KStG",
	),
	_watch("2004", "7551", BLOCKING, Reason.REORGANISATION, "Verluste durch Verschmelzung und Umwandlung"),
	_watch("2504", "7451", BLOCKING, Reason.REORGANISATION, "Erträge durch Verschmelzung und Umwandlung"),
	_watch("2490", "7390", BLOCKING, Reason.ORGANSCHAFT, "Aufwendungen aus Verlustübernahme"),
	_watch(
		"2494",
		"7394",
		BLOCKING,
		Reason.ORGANSCHAFT,
		"Abgeführte Gewinne auf Grund eines Gewinn- oder Teilgewinnabführungsvertrags",
	),
	_watch("2790", "7190", BLOCKING, Reason.ORGANSCHAFT, "Erträge aus Verlustübernahme"),
	_watch(
		"2794",
		"7194",
		BLOCKING,
		Reason.ORGANSCHAFT,
		"Erhaltene Gewinne auf Grund eines Gewinn- oder Teilgewinnabführungsvertrags",
	),
	_watch(
		"2603",
		"7004",
		BLOCKING,
		Reason.PARTNERSHIP_SHARE,
		"Erträge aus Beteiligungen an Personengesellschaften (verbundene Unternehmen), § 9 GewStG bzw. § 18 EStG",
	),
	_watch("2614", "7003", BLOCKING, Reason.PARTNERSHIP_SHARE, "Erträge aus atypisch stillen Beteiligungen"),
	_watch(
		"2618",
		"7008",
		BLOCKING,
		Reason.PARTNERSHIP_SHARE,
		"Gewinnanteile aus gewerblichen und selbständigen Mitunternehmerschaften, § 9 GewStG bzw. § 18 EStG",
	),
	_watch(
		"4872",
		"7208",
		BLOCKING,
		Reason.PARTNERSHIP_SHARE,
		"Aufwendungen auf Grund von Verlustanteilen an gewerblichen und selbständigen Mitunternehmerschaften, § 8 GewStG bzw. § 18 EStG",
	),
	_watch("2745", "7755", BLOCKING, Reason.CAPITAL_REDUCTION, "Ertrag aus der Kapitalherabsetzung"),
	_watch(
		"9890",
		"9890",
		BLOCKING,
		Reason.REINVESTMENT_SURCHARGE,
		"Statistisches Konto für den Gewinnzuschlag nach §§ 6b Abs. 7 und 6c EStG (Haben)",
	),
	_watch(
		"9906",
		"9906",
		BLOCKING,
		Reason.PHOTOVOLTAICS,
		"Steuerfreie Einnahmen und Entnahmen nach § 3 Nr. 72 EStG (Soll)",
	),
	_watch(
		"9908",
		"9908",
		BLOCKING,
		Reason.PHOTOVOLTAICS,
		"Nicht abzugsfähige Betriebsausgaben nach § 3c Abs. 1 EStG i. V. m. § 3 Nr. 72 EStG (Haben)",
	),
	_watch(
		"9916",
		"9916",
		BLOCKING,
		Reason.IAB_EARLIER,
		"Hinzurechnung Investitionsabzugsbetrag § 7g Abs. 2 EStG aus dem 2. vorangegangenen Wirtschaftsjahr, außerbilanziell (Haben)",
	),
	_watch(
		"9917",
		"9917",
		BLOCKING,
		Reason.IAB_EARLIER,
		"Hinzurechnung Investitionsabzugsbetrag § 7g Abs. 2 EStG aus dem 3. vorangegangenen Wirtschaftsjahr, außerbilanziell (Haben)",
	),
	_watch(
		"9976",
		"9976",
		BLOCKING,
		Reason.ZINSSCHRANKE,
		"Nicht abzugsfähige Zinsaufwendungen nach § 4h EStG (Haben)",
	),
	_watch(
		"9978",
		"9978",
		BLOCKING,
		Reason.ZINSSCHRANKE,
		"Abziehbare Zinsaufwendungen aus Vorjahren nach § 4h EStG (Soll)",
	),
	_watch(
		"9984",
		"9984",
		BLOCKING,
		Reason.UEBERLEITUNG,
		"Gewinnkorrektur nach § 60 Abs. 2 EStDV - Erhöhung handelsrechtliches Ergebnis durch Habenbuchung - Minderung handelsrechtliches Ergebnis durch Sollbuchung",
	),
	# Watched at the level Hinweis: a balance asks for a look, not for a change (REASONS).
	_watch("4126", "6026", HINT, Reason.TANTIEME, "Tantiemen Gesellschafter-Geschäftsführer"),
	_watch("4129", "6029", HINT, Reason.TANTIEME, "Tantiemen Arbeitnehmer"),
	_watch(
		"4975",
		"6856",
		HINT,
		Reason.HOLDING_COSTS,
		"Aufwendungen aus Anteilen an Kapitalgesellschaften §§ 3 Nr. 40 und 3c EStG bzw. § 8b Abs. 1 und 4 KStG",
	),
	# Not marked K by DATEV, but where results of shares under § 8b KStG may be booked (REASONS).
	_watch("2600", "7000", BLOCKING, Reason.HOLDING_INCOME, "Erträge aus Beteiligungen"),
	_watch(
		"2619",
		"7009",
		BLOCKING,
		Reason.HOLDING_INCOME,
		"Erträge aus Beteiligungen an verbundenen Unternehmen",
	),
	_watch(
		"2620",
		"7010",
		HINT,
		Reason.SHARE_RESULTS,
		"Erträge aus anderen Wertpapieren und Ausleihungen des Finanzanlagevermögens",
	),
	_watch("2640", "7020", HINT, Reason.SHARE_RESULTS, "Zins- und Dividendenerträge"),
	_watch(
		"2725",
		"4905",
		HINT,
		Reason.SHARE_RESULTS,
		"Erträge aus dem Abgang von Gegenständen des Umlaufvermögens (außer Vorräte)",
		"Erträge aus dem Abgang von Gegenständen des Umlaufvermögens außer Vorräte",
	),
	_watch(
		"2325",
		"6905",
		HINT,
		Reason.SHARE_RESULTS,
		"Verluste aus dem Abgang von Gegenständen des Umlaufvermögens (außer Vorräte)",
		"Verluste aus dem Abgang von Gegenständen des Umlaufvermögens außer Vorräte",
	),
	_watch("4870", "7200", HINT, Reason.SHARE_RESULTS, "Abschreibungen auf Finanzanlagen (dauerhaft)"),
	_watch(
		"4877",
		"7207",
		HINT,
		Reason.SHARE_RESULTS,
		"Abschreibungen auf Finanzanlagen - verbundene Unternehmen",
	),
	_watch("4875", "7210", HINT, Reason.SHARE_RESULTS, "Abschreibungen auf Wertpapiere des Umlaufvermögens"),
	_watch(
		"4878",
		"7217",
		HINT,
		Reason.SHARE_RESULTS,
		"Abschreibungen auf Wertpapiere des Umlaufvermögens - verbundene Unternehmen",
	),
)

OUTSIDE: MappingProxyType[str, MappingProxyType[Outside, tuple[str, ...]]] = MappingProxyType(
	{
		"SKR03": MappingProxyType(
			{
				Outside.EQUITY: (
					"0800",
					"0809",
					"0810",
					"0811",
					"0812",
					"0813",
					"0819",
					"0840",
					"0841",
					"0842",
					"0843",
					"0844",
					"0845",
					"0846",
					"0848",
					"0851",
					"0852",
					"0855",
					"0856",
					"0860",
					"0868",
					"9297",
				),
				Outside.PARTNERSHIP: (
					"2113",
					"2128",
					"3185",
					"4128",
					"4137",
					"4148",
					"4154",
					"4158",
					"4168",
					"4197",
					"4219",
					"4289",
					"4672",
					"4679",
					"4948",
					"4949",
					"4959",
				),
				Outside.RESERVED: ("2130",),
			}
		),
		"SKR04": MappingProxyType(
			{
				Outside.EQUITY: (
					"2900",
					"2901",
					"2902",
					"2903",
					"2906",
					"2908",
					"2909",
					"2920",
					"2925",
					"2926",
					"2927",
					"2928",
					"2929",
					"2930",
					"2937",
					"2950",
					"2960",
					"2961",
					"2962",
					"2970",
					"2978",
					"9297",
				),
				Outside.PARTNERSHIP: (
					"5985",
					"6028",
					"6038",
					"6068",
					"6074",
					"6078",
					"6118",
					"6148",
					"6314",
					"6319",
					"6672",
					"6689",
					"6823",
					"6824",
					"6834",
					"7313",
					"7328",
				),
				Outside.RESERVED: (),
			}
		),
	}
)
"""The accounts the chart marks K or G that have no place in the mapping, by why not: the equity of KSt 1 F lines 17 and
18 (footnote 17), which is no account of the profit and loss account; the accounts of partnerships and natural
persons, which DATEV marks G alone, such as the Sondervergütungen of a Mitunternehmer (§ 15 EStG), the
Hinzurechnungsbetrag of § 4 Absatz 4a EStG or the home office; and the range SKR03 2130 to 2139, which DATEV reserves
(„R“: „Diese Konten dürfen erst dann bebucht werden, wenn ihnen eine andere Funktion zugeteilt wurde“)."""

NON_DEDUCTIBLE_DONATIONS: MappingProxyType[str, frozenset[str]] = MappingProxyType(
	{"SKR03": frozenset({"2380", "2384"}), "SKR04": frozenset({"6390", "6394"})}
)
"""The Zuwendungen of Anlage GK line 92 that Anlage Z does not deduct: those the chart calls „steuerlich nicht
abziehbar“, and those to political parties, which are no Betriebsausgaben (§ 4 Absatz 6 EStG with § 8 Absatz 1 KStG)
and no Zuwendungen of § 9 Absatz 1 Nummer 2 KStG."""


def _accounts(index: int) -> tuple[DefaultAccount, ...]:
	return tuple(account for row in _ROWS if (account := row.accounts()[index]) is not None)


ACCOUNTS: MappingProxyType[str, tuple[DefaultAccount, ...]] = MappingProxyType(
	{chart: _accounts(index) for index, chart in enumerate(CHARTS)}
)
"""Each account of the defaults of a chart with its label, its category or its level."""

DEFAULTS: MappingProxyType[str, Mapping] = MappingProxyType(
	{
		chart: Mapping(
			chart=chart,
			rules=tuple(
				AccountRule(account.number, account.category)
				for account in accounts
				if account.category is not None
			),
			watched=tuple(
				WatchedAccount(account.number, account.level)
				for account in accounts
				if account.level is not None
			),
		)
		for chart, accounts in ACCOUNTS.items()
	}
)


def default_mapping(chart: str) -> Mapping:
	"""The default Income Tax Mapping of a chart; KeyError for a chart without defaults."""
	return DEFAULTS[_known(chart)]


def default_accounts(chart: str) -> tuple[DefaultAccount, ...]:
	"""The accounts of the default mapping of a chart with their DATEV labels; KeyError for a chart without
	defaults."""
	return ACCOUNTS[_known(chart)]


def defaults_version(chart: str) -> str:
	"""The version of the defaults of a chart: the chart, the DATEV edition and the revision, such as SKR03 2026.1."""
	return f"{_known(chart)} {DATEV_EDITION}.{REVISION}"


def _known(chart: str) -> str:
	if chart not in DEFAULTS:
		raise KeyError(
			f"no default Income Tax Mapping for chart {chart!r}; known charts: {', '.join(DEFAULTS)}"
		)
	return chart
