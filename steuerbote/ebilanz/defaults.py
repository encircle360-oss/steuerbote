"""The default Bilanzzuordnung for the DATEV standard charts SKR03 and SKR04, per version of the HGB-Taxonomie.

„Vorgaben laden“ and „Vorgaben aktualisieren“ of the Balance Sheet Mapping read these tables, and „Steuerbote
einrichten“ makes the mapping of a company with them (steuerbote/steuerbote/doctype/balance_sheet_mapping).

Sources. The DATEV-Kontenrahmen nach dem Bilanzrichtlinie-Umsetzungsgesetz, Standardkontenrahmen SKR 03 (Art.-Nr.
11174) and SKR 04 (Art.-Nr. 11175), „Gültig für 2026“, with their labels and the columns Bilanzposten (Fußnote 2) and
Abschlusszweck (Fußnote 4); the labels, the definitionGuidance and the fiscal properties of the positions of the
HGB-Taxonomie 6.9; the Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025 („Leitfaden“); and ERPNext's own
SKR03 and SKR04 templates (de_kontenplan_SKR03.json and de_kontenplan_SKR04.json, version 16), which carry accounts of
older DATEV editions. DATEV's own mapping to the E-Bilanz is none of them: each place follows from the label of the
account and the label of the position.

Places. GROUPS holds every account the DATEV charts label and every account of ERPNext's templates once, with its
label and its twin in the other chart, in groups of the same place and in the order of SKR04:
- _position(): the deepest position the label names that the E-Bilanz of a GmbH asks for, a Mussfeld or a position
  „Rechnerisch notwendig, soweit vorhanden“ beside Mussfelder (Leitfaden A.10.1, A.10.3). An account that holds what
  the taxonomy splits into Mussfelder, such as Grundstücke with and without Bauten, or the Umsatzerlöse of every rate,
  goes to the Auffangposition, „nicht zuordenbar“ or „ohne Zuordnung“ (A.10.4), and place() marks a balance on it with
  the hint BILANZ-AUFFANGPOSITION;
- the position for a balance on the other side, where DATEV gives the account a Bilanzposten for each side, „... oder
  ...“ (Leitfaden A.13); the Gegenkonto of a split by remaining term keeps the side of the accounts it splits;
- the Abschlusszweck DATEV marks, HB or SB. Where the content of an account exists in one balance sheet only, the
  defaults say so although DATEV marks the account for both: the latente Steuern (§ 274 HGB), the provisions of the
  Steuerstundung and the Aufwandsrückstellungen for the Handelsbilanz, the release of steuerfreie Rücklagen and the
  transfer of a § 6b-Rücklage for the Steuerbilanz; a mark of DATEV they never contradict;
- the shareholder flag on every position gegenüber Gesellschaftern (§ 42 Abs. 3 GmbHG), and the remaining term the
  label names: „Restlaufzeit bis 1 Jahr“, „1 bis 5 Jahre“ and „größer 5 Jahre“, and „größer 1 Jahr“ as one to five
  years, which the Vermerk of § 268 Abs. 4 Satz 1 HGB counts as more than one year. An account whose label names no
  term has none, so that the Offenlegung asks for it where a Vermerk needs it;
- _watched(): at the level blocking, an account of a partnership, a sole trader, a Genossenschaft, a Sonder- or
  Ergänzungsbilanz or the Einnahmenüberschussrechnung, which a GmbH does not have, of the Ergebnisverwendung, or one
  DATEV leaves free;
- _outside(): outside the Bilanz and the GuV, the statistical and Vortragskonten of class 9, the interim accounts
  that are balanced at the Bilanzstichtag and the kalkulatorische Kosten, with the reason of Outside.
REASONS says why where the labels of the account and the position do not tell the place alone, and the page
docs/ebilanz-zuordnung.md explains the choices and what the Steuerberatung should review.

Format. DEFAULTS[version][chart] is a steuerbote.xbrl.mapping.Defaults for each version of TAXONOMIES
(steuerbote/xbrl/versions.py) and each chart of CHARTS, with three tuples of entries. An entry names one account or
a DATEV range by its first and last number, both included and of the same length, as a text such as "1800" or
"1800-1849"; entries do not overlap, and every account of a company within one takes its place with its own number:

- DefaultRule(accounts, concept, opposite=None, purpose=Purpose.BOTH, shareholder=False, remaining_term=None): the
  position of the GAAP module without its prefix, such as "bs.ass.currAss.cashEquiv.bank"; the position a balance on
  the other side goes to, such as "bs.eqLiab.liab.bank.other" (Technischer Leitfaden zur HGB-Taxonomie 6.9, A.13);
  the Abschlusszweck of DATEV, Purpose.COMMERCIAL for HB and Purpose.TAX for SB (Fußnote 4 of the charts); and the
  flags of the Offenlegung, owed to or by the shareholders (§ 42 Abs. 3 GmbHG) and the remaining term of a Forderung
  or Verbindlichkeit as a steuerbote.hgb.statement.RemainingTerm or its row value, "up to one year", "one to five
  years" or "over five years" (§ 268 Abs. 4 and 5 HGB).
- DefaultWatched(accounts, level=WatchLevel.BLOCKING): accounts whose position the defaults cannot decide; a balance
  on one holds the E-Bilanz and the Jahresabschluss back, at WatchLevel.HINT it only adds a hint.
- DefaultExcluded(accounts, reason): accounts outside the Bilanz and the GuV, with the reason on one line, such as the
  Vortrags- and statistical accounts of class 9.

steuerbote.xbrl.mapping checks every position of a rule against the taxonomy of its version, and
steuerbote/ebilanz/tests/test_defaults.py does so for these tables against the package of esteuer.de.

Version. The defaults of a chart and a version of the taxonomy have a version of their own: the chart, the taxonomy,
the edition of the DATEV charts and the revision, such as „SKR03 Taxonomie 6.9 2026.1“ (defaults_version()). Every
change of the defaults of a version raises its revision in REVISIONS, so that the same version always means the same
defaults, and test_defaults.py pins the SHA-256 of the rows of each (Defaults.rows()); a new edition of the DATEV charts
starts at 1 again. Revision 0 was the empty table before the defaults of the DATEV charts. A Balance Sheet Mapping
keeps the version and the rows it took over, so that Vorgaben aktualisieren tells a change of the defaults from a
change of the user (steuerbote/mappings/diff.py).

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import NamedTuple

from steuerbote.hgb.statement import RemainingTerm
from steuerbote.ustva.mapping import WatchLevel
from steuerbote.xbrl.mapping import DefaultExcluded, DefaultRule, Defaults, DefaultWatched, Purpose

DATEV_EDITION = 2026
"""The edition of the DATEV charts the defaults follow, „Gültig für 2026“."""
CHARTS = frozenset({"SKR03", "SKR04"})


class Reason(StrEnum):
	"""Why a group of the defaults takes its place where the labels of the account and the position do not tell
	it alone; REASONS gives the source."""

	AAG_REFUND = "aag_refund"
	ACCOUNTING_COSTS = "accounting_costs"
	AFFILIATED_INTEREST = "affiliated_interest"
	AFFILIATED_INTEREST_EXPENSE = "affiliated_interest_expense"
	ALLOWANCE = "allowance"
	APPROPRIATION = "appropriation"
	ATTENTION = "attention"
	BANK_LIABILITY = "bank_liability"
	BEFORE_SPLIT = "before_split"
	BOTH_SIDES = "both_sides"
	BUILDINGS_OWN_LAND = "buildings_own_land"
	CAPITALISED_GWG = "capitalised_gwg"
	CASH_FUND_VALUATION = "cash_fund_valuation"
	CASH_IN_TRANSIT = "cash_in_transit"
	COOPERATIVE = "cooperative"
	CREDITOR_PREPAYMENT = "creditor_prepayment"
	CURRENT_ASSETS_MIXED = "current_assets_mixed"
	DEBTOR_COUNTER = "debtor_counter"
	DEFERRAL_PROVISION = "deferral_provision"
	DEFERRED_TAXES = "deferred_taxes"
	DISPOSAL_KIND = "disposal_kind"
	DONATIONS = "donations"
	ERPNEXT_COST_OF_GOODS = "erpnext_cost_of_goods"
	EUR = "eur"
	EXEMPT_NO_DEDUCTION = "exempt_no_deduction"
	EXPENSE_PROVISIONS = "expense_provisions"
	EXTRAORDINARY_OLD = "extraordinary_old"
	FLAT_RATE_23 = "flat_rate_23"
	FLAT_RATE_INPUT = "flat_rate_input"
	FLAT_RATE_REFUND = "flat_rate_refund"
	FOREIGN_TAX_DBA = "foreign_tax_dba"
	FREE_USE = "free_use"
	GARAGE_RENT = "garage_rent"
	GIFTS_BUSINESS_USE = "gifts_business_use"
	GMBH_SHAREHOLDERS = "gmbh_shareholders"
	GMBH_SHARES_SHORT = "gmbh_shares_short"
	HIRE_PURCHASE = "hire_purchase"
	INCIDENTAL_COSTS = "incidental_costs"
	INDIRECT_DEPRECIATION = "indirect_depreciation"
	INTEREST_DIVIDEND = "interest_dividend"
	INTEREST_MIXED = "interest_mixed"
	INTERNAL_SALES = "internal_sales"
	INVENTORY_CHANGE_MIXED = "inventory_change_mixed"
	IST_CLEARING = "ist_clearing"
	LAND_LEVIES = "land_levies"
	LAND_SHARE = "land_share"
	LATE_FEES_DEDUCTIBLE = "late_fees_deductible"
	LEASE_INCIDENTALS = "lease_incidentals"
	LEGAL_FORM_SPLIT = "legal_form_split"
	LOAN_INCOME = "loan_income"
	LOANS_INCOME_MIXED = "loans_income_mixed"
	MANAGER_NOT_SHAREHOLDER = "manager_not_shareholder"
	MANAGER_TRAVEL = "manager_travel"
	MATERIAL_MIXED = "material_mixed"
	MITUNTERNEHMERSCHAFT = "mitunternehmerschaft"
	MIXED_EQUIPMENT = "mixed_equipment"
	MIXED_LAND = "mixed_land"
	NET_DISPOSAL = "net_disposal"
	NONDEDUCTIBLE_INPUT = "nondeductible_input"
	NONDEDUCTIBLE_INPUT_MATERIAL = "nondeductible_input_material"
	OFFICE = "office"
	OFFSET_INTEREST = "offset_interest"
	OFFSET_OTHER = "offset_other"
	OFFSET_PENSIONS = "offset_pensions"
	OLD_SPECIAL_ITEM = "old_special_item"
	OTHER_LIMITED = "other_limited"
	OTHER_SHAREHOLDERS = "other_shareholders"
	OVERDRAWN = "overdrawn"
	OWN_SHARES = "own_shares"
	PARTNERSHIP = "partnership"
	PARTNERSHIP_INCOME = "partnership_income"
	PENSION_ASSETS_TAX = "pension_assets_tax"
	PENSION_KIND = "pension_kind"
	PREMIUMS = "premiums"
	PREVIOUS_YEARS = "previous_years"
	RATE_16 = "rate_16"
	RATE_16_PURCHASE = "rate_16_purchase"
	RATE_16_REDUCTION = "rate_16_reduction"
	RECEIVED_NOT_BILLED = "received_not_billed"
	RESERVED = "reserved"
	REVERSE_CHARGE_ABROAD = "reverse_charge_abroad"
	REVERSE_CHARGE_DEDUCTION = "reverse_charge_deduction"
	ROOM_COSTS = "room_costs"
	SALARIES_MIXED = "salaries_mixed"
	SCAFFOLDING = "scaffolding"
	SEC_6B_TRANSFER = "sec_6b_transfer"
	SECURITIES_INCOME_MIXED = "securities_income_mixed"
	SHARE_COSTS = "share_costs"
	SHAREHOLDER_INTEREST = "shareholder_interest"
	SILENT_ATYPICAL = "silent_atypical"
	SILENT_PROFIT = "silent_profit"
	SILENT_TYPICAL_RESULT = "silent_typical_result"
	SOCIAL_MIXED = "social_mixed"
	SOCIAL_SECURITY_BOTH = "social_security_both"
	SOLE_TRADER = "sole_trader"
	SONDERBILANZ = "sonderbilanz"
	SPECIAL_DEPRECIATION_RELEASE = "special_depreciation_release"
	SPLIT_COUNTER = "split_counter"
	START_UP_COSTS = "start_up_costs"
	SUPERVISORY_BOARD = "supervisory_board"
	SUPPLEMENTARY_CAPITAL = "supplementary_capital"
	TAX_BALANCE = "tax_balance"
	TAX_KIND = "tax_kind"
	TAX_RESERVE_RELEASE = "tax_reserve_release"
	TAXABLE_ABROAD = "taxable_abroad"
	TEMPLATE_SRBNB = "template_srbnb"
	TENANT_FIXTURES = "tenant_fixtures"
	TOOLS = "tools"
	TRAVEL_EXEMPT = "travel_exempt"
	TRIANGULAR_FIRST = "triangular_first"
	TRIANGULAR_LAST = "triangular_last"
	TYPICAL_SILENT = "typical_silent"
	TYPICAL_SILENT_LIABILITY = "typical_silent_liability"
	TYPICAL_SILENT_RECEIVABLE = "typical_silent_receivable"
	UNUSUAL_OTHER = "unusual_other"
	VALUATION_CORRECTION = "valuation_correction"
	VAT = "vat"
	VAT_NOT_DUE = "vat_not_due"
	VAT_SPLIT = "vat_split"
	VOLUNTARY_TAX_FREE = "voluntary_tax_free"
	WARRANTY = "warranty"
	WITHDRAWALS = "withdrawals"
	WRITE_DOWN_MIXED = "write_down_mixed"


REASONS: MappingProxyType[Reason, str] = MappingProxyType(
	{
		Reason.AAG_REFUND: (
			"DATEV puts the refunds of the Aufwendungsausgleichsgesetz under the sonstige "
			"betriebliche Erträge (Bilanzposten, Fußnote 2)."
		),
		Reason.ACCOUNTING_COSTS: (
			"Abschluss-, Prüfungs- and Buchführungskosten are the fees of the Steuerberatung and the "
			"Wirtschaftsprüfer, which the Mussfeld „Rechts- und Beratungskosten“ of the taxonomy "
			"takes; its „Verwaltungsaufwendungen“ are the costs of the company's own Rechnungswesen "
			"(definitionGuidance)."
		),
		Reason.AFFILIATED_INTEREST: (
			"Interest from affiliated companies: the position „Erträge aus Forderungen an "
			"Gesellschaften und Gesellschafter“ of the taxonomy, which holds those „aus Forderungen "
			"an verbundene Unternehmen“ below it."
		),
		Reason.AFFILIATED_INTEREST_EXPENSE: (
			"Interest to affiliated companies goes to the parent, which as a shareholder of more than "
			"25 % takes the Mussfeld of the interest to such shareholders and the persons close to "
			"them, to sister companies, which are such persons, or to subsidiaries, which are "
			"neither: the Auffangposition takes it (Leitfaden A.10.4)."
		),
		Reason.ALLOWANCE: (
			"A Wertberichtigung reduces the Forderungen it belongs to: DATEV gives it their "
			"Bilanzposten with „H-Saldo“ (Fußnote 2)."
		),
		Reason.APPROPRIATION: (
			"An account of the Ergebnisverwendung, which follows the Jahresüberschuss (§ 268 Abs. 1 "
			"HGB, § 158 Abs. 1 AktG): the E-Bilanz of Steuerbote shows the Jahresüberschuss and no "
			"Bilanzgewinn (Leitfaden B.9.1.2, steuerbote/ebilanz/calculation.py), so the "
			"Steuerberatung decides where the balance goes."
		),
		Reason.ATTENTION: (
			"„Keine Bewirtung liegt vor bei Gewährung von Aufmerksamkeiten in geringem Umfang (wie "
			"Kaffee, Tee, Gebäck)“ (R 4.10 Abs. 5 EStR), beside whose accounts DATEV keeps this one: "
			"„andere ordentliche sonstige betriebliche Aufwendungen“, „im Unternehmen auf einzelnen "
			"Konten zugeordnete Aufwendungen“ (definitionGuidance). Aufmerksamkeiten for the staff (R "
			"19.6 Abs. 1 LStR) would be „sonstige Aufwendungen für Personal“."
		),
		Reason.BANK_LIABILITY: (
			"DATEV gives the account „Verbindlichkeiten gegenüber Kreditinstituten oder "
			"Kassenbestand, Bundesbankguthaben, Guthaben bei Kreditinstituten und Schecks“ (Fußnote "
			"2): a debit balance is Guthaben (Leitfaden A.13)."
		),
		Reason.BEFORE_SPLIT: (
			"Sonstige Verbindlichkeiten „vor Restlaufzeitdifferenzierung“, as DATEV labels them, "
			"which the Gegenkonto of the split sets off: they keep the position of the accounts split "
			"from them."
		),
		Reason.BOTH_SIDES: (
			"DATEV gives the account a Bilanzposten for each side, „... oder ...“ (Fußnote 2): a "
			"balance on the other side goes to the position for the opposite balance (Leitfaden "
			"A.13)."
		),
		Reason.BUILDINGS_OWN_LAND: (
			"DATEV keeps the Grund und Boden of built land apart on Grundstückswerte eigener bebauter "
			"Grundstücke, so this account holds the Gebäude-Anteil."
		),
		Reason.CAPITALISED_GWG: (
			"„Abschreibungen auf aktivierte GWG sind hier nicht auszuweisen“ (definitionGuidance of "
			"„Sofortabschreibung GWG“)."
		),
		Reason.CASH_FUND_VALUATION: (
			"DATEV puts the account under the sonstige betriebliche Erträge or Aufwendungen "
			"(Bilanzposten, Fußnote 2); what it holds, the valuation of the Finanzmittelfonds or the "
			"results of trading, the Steuerberatung looks at."
		),
		Reason.CASH_IN_TRANSIT: (
			"Money on its way between Kasse and Bank at the Bilanzstichtag is an asset, and DATEV "
			"gives the account „Sonstige Vermögensgegenstände oder Sonstige Verbindlichkeiten“ "
			"(Fußnote 2): unlike an Interimskonto, it may hold a balance at the Bilanzstichtag, which "
			"the side of the balance places (Leitfaden A.13)."
		),
		Reason.COOPERATIVE: (
			"An account of a Genossenschaft, by its label: the Geschäftsanteile and Geschäftsguthaben "
			"of its members, its Ergebnisrücklagen and the genossenschaftliche Rückvergütung (§ 337 "
			"HGB, § 22 KStG), which a GmbH or UG does not have."
		),
		Reason.CREDITOR_PREPAYMENT: (
			"DATEV gives the account „Sonstige Vermögensgegenstände H-Saldo“ (Fußnote 2)."
		),
		Reason.CURRENT_ASSETS_MIXED: (
			"The account writes down Umlaufvermögen of every kind, Vorräte as well as Forderungen and "
			"sonstige Vermögensgegenstände, which the taxonomy has in Mussfelder of their own: the "
			"Auffangposition takes it (Leitfaden A.10.4)."
		),
		Reason.DEBTOR_COUNTER: (
			"The Gegenkonto reduces the Forderungen aus Lieferungen und Leistungen: DATEV gives it "
			"their Bilanzposten with „H-Saldo“ (Fußnote 2)."
		),
		Reason.DEFERRAL_PROVISION: (
			"The provision of the Steuerstundung after the Bundessteuerberaterkammer is one for "
			"passive latente Steuern under § 249 Abs. 1 HGB, which the Steuerbilanz does not know: "
			"like the latente Steuern of § 274 HGB, it counts in the Handelsbilanz alone and goes to "
			"the latente Steuern of the taxonomy."
		),
		Reason.DEFERRED_TAXES: (
			"Latente Steuern exist in the Handelsbilanz only (§ 274 HGB): the position is "
			"„steuerlich“ not permitted, so the rule counts in the Handelsbilanz alone, as for the "
			"Bilanz accounts of the latente Steuern that DATEV marks HB."
		),
		Reason.DISPOSAL_KIND: (
			"The account does not tell whether the asset was immateriell, a Sachanlage or a "
			"Finanzanlage, by which the taxonomy splits the results of disposals: the Auffangposition "
			"takes it (Leitfaden A.10.4)."
		),
		Reason.DONATIONS: (
			"The definitionGuidance of „sonstige steuerlich beschränkt abziehbare Betriebsausgaben“ "
			"names „Spenden“."
		),
		Reason.ERPNEXT_COST_OF_GOODS: (
			"ERPNext's templates make the Herstellungskosten their Cost of Goods Sold and the "
			"Verwaltungskosten, in SKR03 also the Vertriebskosten, Expenses Included In Valuation: "
			"with perpetual inventory they hold the Materialaufwand of the goods sold, while DATEV "
			"uses them as statistical accounts of the Umsatzkostenverfahren that set off with their "
			"Gegenkonto. Either way they belong to the Materialaufwand, whose Auffangposition takes "
			"them (Leitfaden A.10.4)."
		),
		Reason.EUR: (
			"An account of the Gewinnermittlung nach § 4 Abs. 3 EStG, by its label or DATEV's "
			"Abschlusszweck EÜR (Fußnote 4), which a GmbH or UG, keeping books by law, does not have "
			"(§§ 238, 242 HGB, § 8 Abs. 1 KStG, § 5 Abs. 1 EStG)."
		),
		Reason.EXEMPT_NO_DEDUCTION: (
			"Steuerfreie Umsätze without Vorsteuerabzug are those of § 4 Nr. 8 to 29 UStG (§ 15 Abs. "
			"2 Satz 1 Nr. 1 UStG; Kennzahl 48 of the Voranmeldung)."
		),
		Reason.EXPENSE_PROVISIONS: (
			"Aufwandsrückstellungen of § 249 Abs. 2 HGB a. F., which a company may keep under Art. 67 "
			"Abs. 3 Satz 1 EGHGB, exist in the Handelsbilanz only: a Passivierungswahlrecht of the "
			"Handelsbilanz is a Passivierungsverbot of the Steuerbilanz (BFH, Beschluss vom 3. 2. "
			"1969, GrS 2/68)."
		),
		Reason.EXTRAORDINARY_OLD: (
			"Since the BilRUG the GuV has no außerordentliche Erträge und Aufwendungen any more (§ "
			"275 HGB); the account of an older edition does not tell what it holds: the "
			"Auffangposition takes it (Leitfaden A.10.4)."
		),
		Reason.FLAT_RATE_23: (
			"The allgemeine Durchschnittssätze of §§ 23 and 23a UStG are open only to Unternehmer "
			"that are not obliged to keep books; a GmbH or UG keeps books by law (§ 238 Abs. 1 HGB, § "
			"13 Abs. 3 GmbHG)."
		),
		Reason.FLAT_RATE_INPUT: (
			"The Vorsteuer of the Durchschnittssätze of § 24 UStG is neither the Regelsteuersatz nor "
			"the ermäßigte Steuersatz; the definitionGuidance names „Erwerb ... zu "
			"Durchschnittssätzen i.S.d. §§ 23, 24 UStG“ for the position „ohne Zuordnung nach "
			"Umsatzsteuertatbeständen“."
		),
		Reason.FLAT_RATE_REFUND: (
			"The Vergütung under § 24 UStG belongs to the Umsätze taxed by Durchschnittssätze."
		),
		Reason.FOREIGN_TAX_DBA: (
			"Foreign tax on income exempt at home under a Doppelbesteuerungsabkommen is not credited "
			"(§ 26 Abs. 1 KStG)."
		),
		Reason.FREE_USE: (
			"„(zur freien Verfügung)“, as DATEV labels the range: the company gives the accounts "
			"their meaning, and with it their position."
		),
		Reason.GARAGE_RENT: (
			"A garage is an unbewegliches Wirtschaftsgut, and DATEV hands the account to the "
			"Gewerbesteuer as the rent of one (marks G and K of the Programmverbindung): the Miet- "
			"und Pachtaufwendungen für unbewegliche Wirtschaftsgüter take it rather than the "
			"Aufwendungen für den Fuhrpark."
		),
		Reason.GIFTS_BUSINESS_USE: (
			"Gifts the recipient can use only in his business are no Geschenke under § 4 Abs. 5 Satz "
			"1 Nr. 1 EStG (R 4.10 Abs. 2 Satz 4 EStR)."
		),
		Reason.GMBH_SHAREHOLDERS: (
			"Every Gesellschafter of a GmbH or UG is a GmbH-Gesellschafter: the Mussfeld "
			"„Ausleihungen an GmbH-Gesellschafter“ of the taxonomy takes the Ausleihungen an "
			"Gesellschafter (§ 42 Abs. 3 GmbHG)."
		),
		Reason.GMBH_SHARES_SHORT: (
			"The taxonomy has the GmbH-Anteile among the Finanzanlagen only; those held for a short "
			"time are sonstige Vermögensgegenstände, as DATEV puts them (Bilanzposten, Fußnote 2)."
		),
		Reason.HIRE_PURCHASE: (
			"DATEV puts the Kaufleasing under the Abschreibungen auf Sachanlagen (Bilanzposten, Fußnote 2)."
		),
		Reason.INCIDENTAL_COSTS: (
			"Bezugsnebenkosten, Leergut and Zölle belong to the purchase of Roh-, Hilfs- und "
			"Betriebsstoffe or of Waren, which the account does not tell: the Auffangposition of the "
			"Materialaufwand takes it (Leitfaden A.10.4)."
		),
		Reason.INDIRECT_DEPRECIATION: (
			"A Wertberichtigung of an asset reduces the position of the asset; the Bilanz of a "
			"Kapitalgesellschaft shows the assets net (§ 266 Abs. 2 HGB)."
		),
		Reason.INTEREST_DIVIDEND: (
			"Zins- und Dividendenerträge in one account, which the taxonomy splits: the "
			"Auffangposition takes it (Leitfaden A.10.4)."
		),
		Reason.INTEREST_MIXED: (
			"The account holds interest of every kind, which the taxonomy splits, among them the "
			"Zinsen nach § 233a AO and those to shareholders: the Auffangposition takes it (Leitfaden "
			"A.10.4)."
		),
		Reason.INTERNAL_SALES: (
			"The definitionGuidance of „nicht steuerbare Umsatzerlöse“ names the „Innenumsätze "
			"zwischen Unternehmensteilen“."
		),
		Reason.INVENTORY_CHANGE_MIXED: (
			"The account holds the Bestandsveränderungen of Roh-, Hilfs- und Betriebsstoffe and of "
			"Waren alike, which the taxonomy has in two Mussfelder: the Auffangposition of the "
			"Materialaufwand takes it (Leitfaden A.10.4)."
		),
		Reason.IST_CLEARING: (
			"Under the Ist-Versteuerung (§ 20 UStG), which a GmbH or UG may use, the account may hold "
			"a balance at the Bilanzstichtag; DATEV gives it „Sonstige Vermögensgegenstände oder "
			"Sonstige Verbindlichkeiten“ (Fußnote 2), and the side of the balance places it "
			"(Leitfaden A.13)."
		),
		Reason.LAND_LEVIES: (
			"Abgaben for betrieblich genutzten Grundbesitz, such as for Abfall, Abwasser and "
			"Straßenreinigung, are Gebühren and Beiträge, while the Grundsteuer has an account of its "
			"own: the position „Versicherungsprämien, Gebühren und Beiträge“ of the taxonomy, as for "
			"the sonstigen Abgaben."
		),
		Reason.LAND_SHARE: (
			"„Der Grund und Boden bei bebauten Grundstücken ist in der Position ... Grund und "
			"Boden-Anteil auszuweisen“ (definitionGuidance of „unbebaute Grundstücke“)."
		),
		Reason.LATE_FEES_DEDUCTIBLE: (
			"Only the steuerlich nicht abzugsfähige Verspätungszuschläge and Zwangsgelder belong to "
			"the steuerlich beschränkt abziehbare Betriebsausgaben (definitionGuidance); these are "
			"ordinary."
		),
		Reason.LEASE_INCIDENTALS: (
			"Miet- und Pachtnebenkosten hold heating, water, cleaning and the like, which the "
			"taxonomy has in positions of their own beside the rent, and DATEV does not hand the "
			"account to the Gewerbesteuer as rent, as it does the Miete (marks G and K of the "
			"Programmverbindung): the Auffangposition takes it (Leitfaden A.10.4)."
		),
		Reason.LEGAL_FORM_SPLIT: (
			"The account does not tell the legal form of the company it concerns, by which the "
			"taxonomy splits the position: the Auffangposition „nach Rechtsform nicht zuordenbar“ "
			"takes it (Leitfaden A.10.4)."
		),
		Reason.LOAN_INCOME: (
			"„z.B. Zinserträge aus Darlehen an verbundene Kapitalgesellschaften“ (definitionGuidance "
			"of „Erträge aus Ausleihungen an Gesellschaften und Gesellschafter“)."
		),
		Reason.LOANS_INCOME_MIXED: (
			"The account holds the income of Ausleihungen of every kind, which the taxonomy splits "
			"into those to Gesellschaften and Gesellschafter and the sonstigen Ausleihungen: the "
			"Auffangposition takes it (Leitfaden A.10.4)."
		),
		Reason.MANAGER_NOT_SHAREHOLDER: (
			"„Vergütungen an Gesellschafter-Geschäftsführer“ are those of a Geschäftsführer who is a "
			"shareholder (definitionGuidance); this account holds those of the others."
		),
		Reason.MANAGER_TRAVEL: (
			"A GmbH or UG has no Unternehmer who travels; its Geschäftsführer travels as an employee "
			"(§ 1 Abs. 1 LStDV)."
		),
		Reason.MATERIAL_MIXED: (
			"The account holds Roh-, Hilfs- und Betriebsstoffe and bezogene Waren alike, which the "
			"taxonomy splits in Summenmussfelder: the Auffangposition of the Materialaufwand takes it "
			"(Leitfaden A.10.4)."
		),
		Reason.MITUNTERNEHMERSCHAFT: (
			"A share in a gewerblich tätige or geprägte Personengesellschaft is one in a "
			"Mitunternehmerschaft (§ 15 Abs. 1 Satz 1 Nr. 2, Abs. 3 EStG); a vermögensverwaltende one "
			"takes the position of its own. The split is fiscal only (definitionGuidance of „Anteile "
			"an Kapitalgesellschaften“)."
		),
		Reason.MIXED_EQUIPMENT: (
			"The account holds every kind of andere Anlagen, Betriebs- und Geschäftsausstattung, "
			"which the taxonomy splits into Pkw and the positions beside it: the Auffangposition "
			"takes it (Leitfaden A.10.4)."
		),
		Reason.MIXED_LAND: (
			"The account holds land, rights equivalent to land and buildings alike, which the "
			"taxonomy splits in Mussfelder: the Auffangposition takes it (Leitfaden A.10.4)."
		),
		Reason.NET_DISPOSAL: (
			"The account holds the net result of a sale, the proceeds less the Restbuchwert, which "
			"the taxonomy shows apart as Erlöse and Anlagenabgänge: the Auffangposition takes it "
			"(Leitfaden A.10.4)."
		),
		Reason.NONDEDUCTIBLE_INPUT: (
			"DATEV books the nicht abziehbare Vorsteuer on accounts of its own under the sonstige "
			"betriebliche Aufwendungen (Bilanzposten, Fußnote 2): a tax the company bears, „sonstige "
			"Steuern, soweit in den sonstigen Aufwendungen ausgewiesen“, „Verbrauchssteuern, "
			"Verkehrssteuern ... sowie andere Steuern“ (definitionGuidance)."
		),
		Reason.NONDEDUCTIBLE_INPUT_MATERIAL: (
			"DATEV puts the nicht abziehbare Vorsteuer of class 5 into the Materialaufwand "
			"(Bilanzposten, Fußnote 2), without telling Roh-, Hilfs- und Betriebsstoffe from Waren: "
			"the Auffangposition of the Materialaufwand takes it (Leitfaden A.10.4)."
		),
		Reason.OFFICE: (
			"Laden- and Büroeinrichtung are Geschäftsausstattung, the position „andere Anlagen, "
			"Betriebs- und Geschäftsausstattung, Geschäftsausstattung“ of the taxonomy; DATEV puts "
			"them under andere Anlagen, Betriebs- und Geschäftsausstattung (Bilanzposten, Fußnote 2)."
		),
		Reason.OFFSET_INTEREST: (
			"„Entsprechend ist mit den zugehörigen Aufwendungen und Erträgen aus der Abzinsung und "
			"aus dem zu verrechnenden Vermögen zu verfahren“ (§ 246 Abs. 2 Satz 2 HGB): DATEV gives "
			"the account both sides, „Zinsen und ähnliche Aufwendungen oder Sonstige Zinsen und "
			"ähnliche Erträge“ (Fußnote 2), and the positions of the Vermögensverrechnung take the "
			"balance by its side (Leitfaden A.13)."
		),
		Reason.OFFSET_OTHER: (
			"The assets set off against the obligations comparable to the Altersversorgung, which are "
			"sonstige Rückstellungen (§ 246 Abs. 2 Satz 2 HGB): both share the position."
		),
		Reason.OFFSET_PENSIONS: (
			"„Vermögensgegenstände, die dem Zugriff aller übrigen Gläubiger entzogen sind und "
			"ausschließlich der Erfüllung von Schulden aus Altersversorgungsverpflichtungen ... "
			"dienen, sind mit diesen Schulden zu verrechnen“ (§ 246 Abs. 2 Satz 2 HGB): assets and "
			"provision share the position, so they set off. The account does not tell Direktzusagen "
			"from those to shareholders, which are Mussfelder, so the Auffangposition takes it "
			"(Leitfaden A.10.4); an excess of the assets is the aktive Unterschiedsbetrag aus der "
			"Vermögensverrechnung, which takes a change of this row."
		),
		Reason.OLD_SPECIAL_ITEM: (
			"„Diese Position ist nur für Sonderposten zulässig, die spätestens zum 31.12.2009 ... "
			"gebildet wurden“ (definitionGuidance of the Sonderposten mit Rücklageanteil); later ones "
			"take a position under „Sonstige Sonderposten“."
		),
		Reason.OTHER_LIMITED: (
			"The Mussfeld „sonstige steuerlich beschränkt abziehbare Betriebsausgaben“ takes these "
			"Betriebsausgaben „ohne Bewirtungskosten“ (definitionGuidance), the abziehbar part as "
			"well as the nicht abziehbar one."
		),
		Reason.OTHER_SHAREHOLDERS: (
			"Every Gesellschafter of a GmbH or UG is a GmbH-Gesellschafter, the „sonstigen“ of the "
			"DATEV label as well: the Mussfeld „Forderungen gegen GmbH-Gesellschafter“ of the "
			"taxonomy takes the account (§ 42 Abs. 3 GmbHG)."
		),
		Reason.OVERDRAWN: (
			"„Ist der Saldo jedoch im „Haben“ (d.h. das Konto wurde „überzogen“) so erfolgt der "
			"Ausweis auf der Passivseite unter den Verbindlichkeiten in der Position "
			"„Verbindlichkeiten gegenüber Kreditinstituten““ (Leitfaden A.13)."
		),
		Reason.OWN_SHARES: ("The costs of acquiring own shares are expenses (§ 272 Abs. 1a Satz 3 HGB)."),
		Reason.PARTNERSHIP: (
			"An account of a Personengesellschaft or an Einzelunternehmen, by its label, which a GmbH "
			"or UG does not have; its positions belong to other legal forms (Leitfaden B.4.2)."
		),
		Reason.PARTNERSHIP_INCOME: (
			"The share in the profit of a Personengesellschaft that is a Mitunternehmerschaft (§ 15 "
			"Abs. 1 Satz 1 Nr. 2 EStG), as the label with § 9 GewStG says: the position „Gewinnanteil "
			"aus Beteiligungen an Mitunternehmerschaften“ of the taxonomy."
		),
		Reason.PENSION_ASSETS_TAX: (
			"In the Steuerbilanz the assets that serve the pensions are not set off against them (§ 5 "
			"Abs. 1a Satz 1 EStG); DATEV puts the account under sonstige Vermögensgegenstände "
			"(Bilanzposten, Fußnote 2)."
		),
		Reason.PENSION_KIND: (
			"The account does not tell Direktzusagen from Zuschussverpflichtungen and from those to "
			"shareholders, which are Mussfelder: the Auffangposition takes it (Leitfaden A.10.4)."
		),
		Reason.PREMIUMS: (
			"Zugaben are Zuwendungen „zusätzlich zur ohnehin vereinbarten Leistung oder "
			"Gegenleistung“ (§ 37b Abs. 1 Satz 1 Nr. 1 EStG), no Geschenke (Nr. 2): they promote the "
			"sale, the Werbeaufwand of the taxonomy, while DATEV keeps the Geschenke on accounts of "
			"their own."
		),
		Reason.PREVIOUS_YEARS: (
			"Nachzahlungen and Erstattungen for earlier years on one account: the side of the balance "
			"chooses (Leitfaden A.13)."
		),
		Reason.RATE_16: (
			"16 % and 15 % are no rate of today; the definitionGuidance of „sonstige "
			"Umsatzsteuersätze“ names the rates of earlier years."
		),
		Reason.RATE_16_PURCHASE: (
			"The Wareneinkauf has positions for the Regelsteuersatz and the ermäßigte Steuersatz of "
			"today only: the Nachlässe at 16 % or 15 %, rates of earlier years, go to the "
			"Auffangposition „ohne Zuordnung nach Umsatzsteuertatbeständen“ (Leitfaden A.10.4)."
		),
		Reason.RATE_16_REDUCTION: (
			"16 % and 15 % are no rate of today: „Hier sind alle Erlösschmälerungen anzugeben, die "
			"einem anderen Steuersatz unterliegen“ (definitionGuidance of „übrige Steuersätze“)."
		),
		Reason.RECEIVED_NOT_BILLED: (
			"ERPNext books goods received and not yet invoiced on this account (Stock Received But "
			"Not Billed): a Verbindlichkeit aus Lieferungen und Leistungen whose invoice is still to "
			"come."
		),
		Reason.RESERVED: (
			"„(reserviertes Konto)“: DATEV keeps the account for later use; it takes no postings."
		),
		Reason.REVERSE_CHARGE_ABROAD: (
			"A sonstige Leistung taxable in another EU country is not steuerbar at home (§ 3a Abs. 2 "
			"UStG); the definitionGuidance of „nicht steuerbare Umsatzerlöse“ names „alle Lieferungen "
			"und sonstige Leistungen deren umsatzsteuerlicher Leistungsort sich nicht im Inland "
			"befindet“."
		),
		Reason.REVERSE_CHARGE_DEDUCTION: (
			"The account names § 13b UStG but not whether its Vorsteuer is deductible, by which the "
			"taxonomy splits the Leistungen: the Auffangposition „ohne Zuordnung nach "
			"Umsatzsteuertatbeständen“ takes it (Leitfaden A.10.4)."
		),
		Reason.ROOM_COSTS: (
			"Raumkosten hold rent, energy, cleaning and repairs, which the taxonomy has in Mussfelder "
			"of their own: the Auffangposition takes them (Leitfaden A.10.4)."
		),
		Reason.SALARIES_MIXED: (
			"The account holds every kind of Löhne und Gehälter, which the taxonomy splits in "
			"Mussfelder such as the Vergütungen an Gesellschafter-Geschäftsführer: the "
			"Auffangposition takes it (Leitfaden A.10.4)."
		),
		Reason.SCAFFOLDING: (
			"Gerüst- und Schalungsmaterial serves the operations, not the office: the position "
			"„andere Anlagen, Betriebs- und Geschäftsausstattung, Betriebsausstattung“ of the "
			"taxonomy."
		),
		Reason.SEC_6B_TRANSFER: (
			"A § 6b-Rücklage transferred onto Finanzanlagen (§ 6b Abs. 10 EStG) reduces their "
			"Anschaffungskosten in the Steuerbilanz alone, as DATEV marks SKR04 7250 and SKR03 4874 "
			"SB; it is no außerplanmäßige Abschreibung, so the Auffangposition of the Abschreibungen "
			"auf Finanzanlagen takes it (Leitfaden A.10.4)."
		),
		Reason.SECURITIES_INCOME_MIXED: (
			"The account holds the income of Wertpapiere and Ausleihungen alike, which the taxonomy "
			"splits by legal form and kind: the Auffangposition takes it (Leitfaden A.10.4)."
		),
		Reason.SHARE_COSTS: (
			"DATEV puts the account under the sonstige betriebliche Aufwendungen (Bilanzposten, "
			"Fußnote 2); the taxonomy has no position for the expenses of a holding."
		),
		Reason.SHAREHOLDER_INTEREST: (
			"Whether the shareholder holds more than 25 %, which the Mussfeld of the interest to "
			"shareholders asks, the account does not tell: the Auffangposition takes it (Leitfaden "
			"A.10.4)."
		),
		Reason.SILENT_ATYPICAL: (
			"Einlagen and results of an atypisch stiller Gesellschafter belong to the "
			"Mitunternehmerschaft, not to the Steuerbilanz of the GmbH (definitionGuidance of "
			"„Verbindlichkeiten gegenüber stillen Gesellschaftern“): the Steuerberatung decides their "
			"place."
		),
		Reason.SILENT_PROFIT: (
			"The share of a stiller Gesellschafter in the profit, not yet paid, is a Verbindlichkeit "
			"to him; DATEV puts the account under sonstige Verbindlichkeiten (Bilanzposten, Fußnote "
			"2)."
		),
		Reason.SILENT_TYPICAL_RESULT: (
			"The share of a typisch stiller Gesellschafter in the profit is abgeführter Gewinn, his "
			"share in the loss a Verlustübernahme (§ 277 Abs. 3 Satz 2 HGB): the side of the balance "
			"chooses."
		),
		Reason.SOCIAL_MIXED: (
			"The account holds soziale Abgaben and Aufwendungen für Altersversorgung und "
			"Unterstützung alike, which the taxonomy splits: the Auffangposition takes it (Leitfaden "
			"A.10.4)."
		),
		Reason.SOCIAL_SECURITY_BOTH: (
			"DATEV gives the account „Sonstige Vermögensgegenstände oder Sonstige Verbindlichkeiten“ "
			"(Fußnote 2): a credit balance is owed to a Träger der Sozialversicherung, a "
			"Verbindlichkeit im Rahmen der sozialen Sicherheit (§ 266 Abs. 3 C. 8 HGB; Leitfaden "
			"A.13)."
		),
		Reason.SOLE_TRADER: (
			"An account of an Einzelunternehmer or a Mitunternehmer, by its label and § 4 Abs. 4a and "
			"5 EStG, which a GmbH or UG does not have."
		),
		Reason.SONDERBILANZ: (
			"An account of the Sonder- or Ergänzungsbilanz of a Mitunternehmer (DATEV Fußnote 28), "
			"which a GmbH or UG does not file (Leitfaden A.9.3)."
		),
		Reason.SPECIAL_DEPRECIATION_RELEASE: (
			"Steuerrechtliche Sonderabschreibungen went into the Sonderposten mit Rücklageanteil (§ "
			"281 Abs. 1 HGB a. F., continued under Art. 67 Abs. 3 EGHGB); their release is an Ertrag "
			"aus der Auflösung of that Sonderposten."
		),
		Reason.SPLIT_COUNTER: (
			"The Gegenkonto of a split by remaining term sets off the accounts it splits, so it keeps "
			"their position: a position for the opposite balance would take it away from them. "
			"DATEV's Bilanzposten for both sides (Fußnote 2) concerns the balance split as a whole."
		),
		Reason.START_UP_COSTS: (
			"Aufwendungen für die Ingangsetzung und Erweiterung des Geschäftsbetriebs were a "
			"Bilanzierungshilfe of the Handelsbilanz before the BilMoG (§ 269 HGB a. F., Art. 67 Abs. "
			"5 EGHGB), which the Steuerbilanz never knew."
		),
		Reason.SUPERVISORY_BOARD: (
			"The definitionGuidance of „sonstige steuerlich beschränkt abziehbare Betriebsausgaben“ "
			"names the „Aufwendungen für Aufsichts- und Verwaltungsrat“ (§ 10 Nr. 4 KStG)."
		),
		Reason.SUPPLEMENTARY_CAPITAL: (
			"Eingeforderte Nachschüsse go to the Kapitalrücklage (§ 42 Abs. 2 Satz 3 GmbHG)."
		),
		Reason.TAX_BALANCE: (
			"The steuerlicher Ausgleichsposten follows from the Überleitungsrechnung (Leitfaden A.11; "
			"steuerbote/ebilanz/ueberleitung.py), not from an account of the books."
		),
		Reason.TAX_KIND: (
			"The account does not tell which tax it provides for, while the Gewerbesteuerrückstellung "
			"is a Mussfeld: the Auffangposition takes it (Leitfaden A.10.4)."
		),
		Reason.TAX_RESERVE_RELEASE: (
			"Since the BilMoG the Handelsbilanz forms no steuerfreie Rücklagen (§ 247 Abs. 3 HGB a. "
			"F.), and DATEV marks their Einstellung SB: their release belongs to the Steuerbilanz "
			"alone, although the account carries no mark SB."
		),
		Reason.TAXABLE_ABROAD: (
			"A purchase taxable in a Drittland or another EU country, and a steuerfreie Einfuhr (§ 5 "
			"UStG), bear no German Vorsteuer (§ 15 Abs. 1 UStG): the position „Wareneinkauf ohne "
			"Vorsteuerabzug“ of the taxonomy."
		),
		Reason.TEMPLATE_SRBNB: (
			"ERPNext's SKR03 template books goods received and not yet invoiced on this account "
			"(Stock Received But Not Billed): a Verbindlichkeit aus Lieferungen und Leistungen whose "
			"invoice is still to come, as on 70001 of the SKR04 template. The remaining term of the "
			"DATEV label does not fit what the template books there, so the defaults leave it to the "
			"company."
		),
		Reason.TENANT_FIXTURES: (
			"„Hier sind auch die Mietereinbauten, sofern es sich um keine technischen Anlagen und "
			"Maschinen handelt, einzutragen“ (definitionGuidance of „Bauten auf fremden "
			"Grundstücken“); DATEV puts the account under andere Anlagen, Betriebs- und "
			"Geschäftsausstattung."
		),
		Reason.TOOLS: (
			"Werkzeuge serve the business as Betriebsausstattung; DATEV keeps them with it under "
			"andere Anlagen, Betriebs- und Geschäftsausstattung."
		),
		Reason.TRAVEL_EXEMPT: (
			"The definitionGuidance of „sonstige umsatzsteuerfreie Umsätze“ names the „steuerfreie "
			"Reiseleistungen nach § 25 Abs. 2 UStG“."
		),
		Reason.TRIANGULAR_FIRST: (
			"The first purchaser of an innergemeinschaftliches Dreiecksgeschäft makes an "
			"innergemeinschaftlicher Erwerb, which § 25b Abs. 3 UStG deems taxed."
		),
		Reason.TRIANGULAR_LAST: (
			"The last purchaser of an innergemeinschaftliches Dreiecksgeschäft makes no "
			"innergemeinschaftlicher Erwerb: he receives a supply taxable at home, owes its tax (§ "
			"25b Abs. 2 UStG) and deducts it as Vorsteuer (§ 25b Abs. 5 UStG), at the Regelsteuersatz "
			"the label names."
		),
		Reason.TYPICAL_SILENT: (
			"„Hierunter fallen z.B. als Beteiligung aktivierte stille Gesellschaften, die keine "
			"steuerliche Mitunternehmerschaft darstellen (typisch stille Beteiligungen)“ "
			"(definitionGuidance)."
		),
		Reason.TYPICAL_SILENT_LIABILITY: (
			"„Aus Sicht der Finanzverwaltung liegt bei Einlagen typisch stiller Gesellschafter "
			"Fremdkapital ... vor“ (definitionGuidance); DATEV puts the account under sonstige "
			"Verbindlichkeiten (Bilanzposten, Fußnote 2)."
		),
		Reason.TYPICAL_SILENT_RECEIVABLE: (
			"A typisch stiller Gesellschafter is no shareholder; DATEV puts the account under "
			"sonstige Vermögensgegenstände (Bilanzposten, Fußnote 2)."
		),
		Reason.UNUSUAL_OTHER: (
			"Abschreibungen auf Vermögensgegenstände des Umlaufvermögens, soweit diese die üblichen "
			"überschreiten (§ 275 Abs. 2 Nr. 7 Buchstabe b HGB), on sonstige Vermögensgegenstände: "
			"the taxonomy has them with the Forderungen."
		),
		Reason.VALUATION_CORRECTION: (
			"The Bewertungskorrektur belongs to the position it corrects, which DATEV names as its "
			"Bilanzposten (Fußnote 2), and lowers or raises it by the side of its balance (Leitfaden "
			"A.13)."
		),
		Reason.VAT: (
			"Vorsteuer and Umsatzsteuer are Forderungen or Verbindlichkeiten against the Finanzamt by "
			"the side of the balance; DATEV gives sonstige Vermögensgegenstände or sonstige "
			"Verbindlichkeiten (Fußnote 2; Leitfaden A.13)."
		),
		Reason.VAT_NOT_DUE: (
			"DATEV gives Umsatzsteuer not yet due „Steuerrückstellungen (allgemein) oder Sonstige "
			"Vermögensgegenstände“ (Fußnote 2; Leitfaden A.13)."
		),
		Reason.VAT_SPLIT: (
			"The account does not tell the Umsatzsteuer of its amounts, by which the taxonomy splits "
			"the position: the Auffangposition „ohne Zuordnung nach Umsatzsteuertatbeständen“ takes "
			"it (Leitfaden A.10.4)."
		),
		Reason.VOLUNTARY_TAX_FREE: (
			"Lohnsteuerfreie freiwillige soziale Aufwendungen are „Sonstige Unterstützungsleistungen "
			"des Arbeitgebers, z.B. nach § 3 Nr. 34 EStG“ (definitionGuidance of „Aufwendungen für "
			"Unterstützung“)."
		),
		Reason.WARRANTY: (
			"The definitionGuidance of „andere ordentliche sonstige betriebliche Aufwendungen“ names "
			"„Schadensersatz“; the taxonomy has no position for Gewährleistung."
		),
		Reason.WITHDRAWALS: (
			"Unentgeltliche Wertabgaben (§ 3 Abs. 1b and 9a UStG) go to „sonstige Sach-, Nutzungs- "
			"und Leistungsentnahmen“, „unabhängig ihrer umsatzsteuerlichen Behandlungen“ "
			"(definitionGuidance); the private Kfz-Nutzung and the Warenentnahmen, which the "
			"definitionGuidance leaves to positions of their own, have those only for "
			"Einzelunternehmer and Mitunternehmer (Leitfaden B.4.2). A GmbH or UG books what a "
			"shareholder takes as a verdeckte Gewinnausschüttung, which the Steuerberatung looks at."
		),
		Reason.WRITE_DOWN_MIXED: (
			"The account does not tell what kind of Finanzanlage it writes down, by which the "
			"taxonomy splits the außerplanmäßige Abschreibungen: the Auffangposition takes it "
			"(Leitfaden A.10.4)."
		),
	}
)


class Outside(StrEnum):
	"""Why accounts lie outside the Bilanz and the GuV, as the rows of a Balance Sheet Mapping give it."""

	BWA = "Abgrenzung für die BWA, zum Abschluss aufgelöst"
	CALCULATORY = "Kalkulatorische Kosten und ihre Verrechnung, keine Aufwendungen der GuV"
	CARRYFORWARD = "Vortragskonto der Eröffnungsbuchungen, ausgeglichen nach dem Vortrag"
	INTERIM = "Interimskonto, ausgeglichen zum Bilanzstichtag"
	NOTED = "Vermerk mit Gegenkonto, kein Posten der Bilanz"
	PARTNERSHIP_STATISTICAL = "Ergebnisverteilung einer Personengesellschaft, außerhalb von Bilanz und GuV"
	STATISTICAL = "Statistisches Konto der Klasse 9 mit Gegenkonto, außerhalb von Bilanz und GuV"


class Account(NamedTuple):
	"""An account or a DATEV range of SKR03, its twin in SKR04, None where a chart has none, and its DATEV label; for an
	account of ERPNext's template that the DATEV edition does not have, the label of the template."""

	skr03: str | None
	skr04: str | None
	label: str

	def number(self, chart: str) -> str | None:
		"""The account or range in a chart, SKR03 or SKR04."""
		return self.skr03 if chart == "SKR03" else self.skr04


@dataclass(frozen=True, slots=True)
class Group:
	"""Accounts with one place: a position, with the position for the opposite balance, the Abschlusszweck and the flags
	of the Offenlegung; watched at a level; or outside the Bilanz and the GuV. ``reason`` says why where the labels do
	not tell the place alone."""

	accounts: tuple[Account, ...]
	concept: str | None = None
	opposite: str | None = None
	purpose: Purpose = Purpose.BOTH
	shareholder: bool = False
	remaining_term: RemainingTerm | None = None
	level: WatchLevel | None = None
	outside: Outside | None = None
	reason: Reason | None = None

	def entries(self, chart: str) -> Iterator[DefaultRule | DefaultWatched | DefaultExcluded]:
		"""The entries of the defaults of a chart for the accounts of the group it has."""
		for account in self.accounts:
			number = account.number(chart)
			if number is None:
				continue
			if self.concept is not None:
				yield DefaultRule(
					number, self.concept, self.opposite, self.purpose, self.shareholder, self.remaining_term
				)
			elif self.level is not None:
				yield DefaultWatched(number, self.level)
			else:
				yield DefaultExcluded(number, self.outside)


type _Row = tuple[str | None, str | None, str]


def _position(
	concept: str,
	*accounts: _Row,
	opposite: str | None = None,
	purpose: Purpose = Purpose.BOTH,
	shareholder: bool = False,
	remaining_term: RemainingTerm | None = None,
	reason: Reason | None = None,
) -> Group:
	return Group(_accounts(accounts), concept, opposite, purpose, shareholder, remaining_term, reason=reason)


def _watched(reason: Reason, *accounts: _Row, level: WatchLevel = WatchLevel.BLOCKING) -> Group:
	return Group(_accounts(accounts), level=level, reason=reason)


def _outside(outside: Outside, *accounts: _Row) -> Group:
	return Group(_accounts(accounts), outside=outside)


def _accounts(rows: Iterable[_Row]) -> tuple[Account, ...]:
	return tuple(Account(*row) for row in rows)


_GROUPS_6_9: tuple[Group, ...] = (
	_watched(
		Reason.PARTNERSHIP,
		(
			"9920",
			"0050",
			"Ausstehende Einlagen auf das Komplementär-Kapital, nicht eingefordert (Vollhafter)",
		),
		("9930", "0060", "Ausstehende Einlagen auf das Komplementär-Kapital, eingefordert (Vollhafter)"),
		("9940", "0070", "Ausstehende Einlagen auf das Kommandit-Kapital, nicht eingefordert (Teilhafter)"),
		("9950", "0080", "Ausstehende Einlagen auf das Kommandit-Kapital, eingefordert (Teilhafter)"),
	),
	_watched(
		Reason.COOPERATIVE,
		("0005", "0090", "Rückständige fällige Einzahlungen auf Geschäftsanteile"),
	),
	_position(
		"bs.ass.fixAss.intan.concessionBrands",
		(
			"0010",
			"0100",
			"Entgeltlich erworbene Konzessionen, gewerbliche Schutzrechte und ähnliche Rechte und Werte sowie Lizenzen an solchen Rechten und Werten",
		),
		("0015", "0110", "Konzessionen"),
		("0020", "0120", "Gewerbliche Schutzrechte"),
		("0025", "0130", "Ähnliche Rechte und Werte"),
		("0027", "0135", "EDV-Software"),
		("0030", "0140", "Lizenzen an gewerblichen Schutzrechten und ähnlichen Rechten und Werten"),
	),
	_position(
		"bs.ass.fixAss.intan.selfmade",
		("0043", "0143", "Selbst geschaffene immaterielle Vermögensgegenstände"),
		("0044", "0144", "EDV-Software"),
		("0045", "0145", "Lizenzen und Franchiseverträge"),
		("0046", "0146", "Konzessionen und gewerbliche Schutzrechte"),
		("0047", "0147", "Rezepte, Verfahren, Prototypen"),
		purpose=Purpose.COMMERCIAL,
	),
	_position(
		"bs.ass.fixAss.intan.development",
		("0048", "0148", "Immaterielle Vermögensgegenstände in Entwicklung"),
		purpose=Purpose.COMMERCIAL,
	),
	_position(
		"bs.ass.fixAss.intan.goodwill",
		("0035", "0150", "Geschäfts- oder Firmenwert"),
	),
	_position(
		"bs.ass.fixAss.intan.advPaym",
		("0039", "0170", "Geleistete Anzahlungen auf immaterielle Vermögensgegenstände"),
		("0038", "0179", "Anzahlungen auf Geschäfts- oder Firmenwert"),
	),
	_position(
		"bs.ass.fixAss.tan.landBuildings.misc",
		(
			"0050",
			"0200",
			"Grundstücke, grundstücksgleiche Rechte und Bauten einschließlich der Bauten auf fremden Grundstücken",
		),
		reason=Reason.MIXED_LAND,
	),
	_position(
		"bs.ass.fixAss.tan.landBuildings.rightEquivalentToLandWithoutBuildings",
		("0060", "0210", "Grundstücksgleiche Rechte ohne Bauten"),
	),
	_position(
		"bs.ass.fixAss.tan.landBuildings.landWithoutBuildings",
		("0065", "0215", "Unbebaute Grundstücke"),
	),
	_position(
		"bs.ass.fixAss.tan.landBuildings.rightEquivalentToLandWithoutBuildings",
		("0070", "0220", "Grundstücksgleiche Rechte (Erbbaurecht, Dauerwohnrecht, unbebaute Grundstücke)"),
	),
	_position(
		"bs.ass.fixAss.tan.landBuildings.other",
		("0075", "0225", "Grundstücke mit Substanzverzehr"),
	),
	_watched(
		Reason.SOLE_TRADER,
		("0059", "0229", "Grundstücksanteil des häuslichen Arbeitszimmers"),
	),
	_position(
		"bs.ass.fixAss.tan.landBuildings.buildingsOnOwnLand.buildings",
		("0080", "0230", "Bauten auf eigenen Grundstücken und grundstücksgleichen Rechten"),
		reason=Reason.BUILDINGS_OWN_LAND,
	),
	_position(
		"bs.ass.fixAss.tan.landBuildings.buildingsOnOwnLand.land",
		("0085", "0235", "Grundstückswerte eigener bebauter Grundstücke"),
		reason=Reason.LAND_SHARE,
	),
	_position(
		"bs.ass.fixAss.tan.landBuildings.buildingsOnOwnLand.buildings",
		("0090", "0240", "Geschäftsbauten"),
		("0100", "0250", "Fabrikbauten"),
		("0115", "0260", "Andere Bauten"),
		("0110", "0270", "Garagen"),
		("0111", "0280", "Außenanlagen für Geschäfts-, Fabrik- und andere Bauten"),
		("0112", "0285", "Hof- und Wegebefestigungen"),
		("0113", "0290", "Einrichtungen für Geschäfts-, Fabrik- und andere Bauten"),
		("0140", "0300", "Wohnbauten"),
		("0145", "0305", "Garagen"),
		("0146", "0310", "Außenanlagen"),
		("0147", "0315", "Hof- und Wegebefestigungen"),
		("0148", "0320", "Einrichtungen für Wohnbauten"),
	),
	_watched(
		Reason.SOLE_TRADER,
		("0149", "0329", "Gebäudeteil des häuslichen Arbeitszimmers"),
	),
	_position(
		"bs.ass.fixAss.tan.landBuildings.buildingsOnNonOwnedLand",
		("0160", "0330", "Bauten auf fremden Grundstücken"),
		("0165", "0340", "Geschäftsbauten"),
		("0170", "0350", "Fabrikbauten"),
		("0190", "0360", "Wohnbauten"),
		("0191", None, "Garagen"),
		("0192", None, "Außenanlagen"),
		("0193", None, "Hof- und Wegebefestigungen"),
		("0194", None, "Einrichtungen für Wohnbauten"),
		("0179", "0370", "Andere Bauten"),
		("0175", "0380", "Garagen"),
		("0176", "0390", "Außenanlagen"),
		("0177", "0395", "Hof- und Wegebefestigungen"),
		("0178", "0398", "Einrichtungen für Geschäfts-, Fabrik-, Wohn- und andere Bauten"),
	),
	_position(
		"bs.ass.fixAss.tan.machinery",
		("0200", "0400", "Technische Anlagen und Maschinen"),
	),
	_position(
		"bs.ass.fixAss.tan.machinery",
		(None, "0409", "Wertberichtigung Technische Anlagen und Maschinen"),
		reason=Reason.INDIRECT_DEPRECIATION,
	),
	_position(
		"bs.ass.fixAss.tan.machinery",
		("0240", "0420", "Technische Anlagen"),
		("0210", "0440", "Maschinen"),
		("0260", "0450", "Transportanlagen und Ähnliches"),
		("0220", "0460", "Maschinengebundene Werkzeuge"),
		("0280", "0470", "Betriebsvorrichtungen"),
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.misc",
		("0300", "0500", "Andere Anlagen, Betriebs- und Geschäftsausstattung"),
		reason=Reason.MIXED_EQUIPMENT,
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.other",
		("0310", "0510", "Andere Anlagen"),
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.passengerCars",
		("0320", "0520", "Pkw"),
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.comVehicle",
		("0350", "0540", "Lkw"),
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.otherTransportMeans",
		("0380", "0560", "Sonstige Transportmittel"),
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.factory",
		("0440", "0620", "Werkzeuge"),
		reason=Reason.TOOLS,
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.factory",
		("0400", "0630", "Betriebsausstattung"),
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.office",
		("0410", "0635", "Geschäftsausstattung"),
		("0430", "0640", "Ladeneinrichtung"),
		("0420", "0650", "Büroeinrichtung"),
		reason=Reason.OFFICE,
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.factory",
		("0460", "0660", "Gerüst- und Schalungsmaterial"),
		reason=Reason.SCAFFOLDING,
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.gwg",
		("0480", "0670", "Geringwertige Wirtschaftsgüter"),
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.gwgsammelposten",
		("0485", "0675", "Wirtschaftsgüter (Sammelposten)"),
	),
	_position(
		"bs.ass.fixAss.tan.landBuildings.buildingsOnNonOwnedLand",
		("0450", "0680", "Einbauten in fremde Grundstücke"),
		reason=Reason.TENANT_FIXTURES,
	),
	_position(
		"bs.ass.fixAss.tan.otherEquipm.otherbga",
		("0490", "0690", "Sonstige Betriebs- und Geschäftsausstattung"),
	),
	_position(
		"bs.ass.fixAss.tan.inConstrAdvPaym",
		(None, "0700", "Geleistete Anzahlungen und Anlagen im Bau"),
		("0079", "0705", "Anzahlungen auf Grund und Boden"),
		("0120", "0710", "Geschäfts-, Fabrik- und andere Bauten im Bau auf eigenen Grundstücken"),
		("0129", "0720", "Anzahlungen auf Geschäfts-, Fabrik- und andere Bauten auf eigenen Grundstücken"),
		("0150", "0725", "Wohnbauten im Bau auf eigenen Grundstücken"),
		("0159", "0735", "Anzahlungen auf Wohnbauten auf eigenen Grundstücken"),
		("0180", "0740", "Geschäfts-, Fabrik- und andere Bauten im Bau auf fremden Grundstücken"),
		("0189", "0750", "Anzahlungen auf Geschäfts-, Fabrik- und andere Bauten auf fremden Grundstücken"),
		("0195", "0755", "Wohnbauten im Bau auf fremden Grundstücken"),
		("0199", "0765", "Anzahlungen auf Wohnbauten auf fremden Grundstücken"),
		("0290", "0770", "Technische Anlagen und Maschinen im Bau"),
		("0299", "0780", "Anzahlungen auf technische Anlagen und Maschinen"),
		("0498", "0785", "Andere Anlagen, Betriebs- und Geschäftsausstattung im Bau"),
		("0499", "0795", "Anzahlungen auf andere Anlagen, Betriebs- und Geschäftsausstattung"),
	),
	_position(
		"bs.ass.fixAss.fin.sharesInAffil.other",
		("0500", "0800", "Anteile an verbundenen Unternehmen (Anlagevermögen)"),
		reason=Reason.LEGAL_FORM_SPLIT,
	),
	_position(
		"bs.ass.fixAss.fin.sharesInAffil.partnerships.commPart.other",
		("0501", "0803", "Anteile an verbundenen Unternehmen, Personengesellschaften"),
		reason=Reason.MITUNTERNEHMERSCHAFT,
	),
	_position(
		"bs.ass.fixAss.fin.sharesInAffil.corporations",
		("0502", "0804", "Anteile an verbundenen Unternehmen, Kapitalgesellschaften"),
	),
	_position(
		"bs.ass.fixAss.fin.sharesInAffil.partnerships.commPart.other",
		(
			"0509",
			"0805",
			"Anteile an herrschender oder mehrheitlich beteiligter Gesellschaft, Personengesellschaften",
		),
		reason=Reason.MITUNTERNEHMERSCHAFT,
	),
	_watched(
		Reason.PARTNERSHIP,
		("0538", "0806", "Anteile einer GmbH & Co. KG an einer Komplementär-GmbH"),
	),
	_position(
		"bs.ass.fixAss.fin.sharesInAffil.corporations",
		(
			"0503",
			"0808",
			"Anteile an herrschender oder mehrheitlich beteiligter Gesellschaft, Kapitalgesellschaften",
		),
	),
	_position(
		"bs.ass.fixAss.fin.sharesInAffil.other",
		("0504", "0809", "Anteile an herrschender oder mehrheitlich beteiligter Gesellschaft"),
		reason=Reason.LEGAL_FORM_SPLIT,
	),
	_position(
		"bs.ass.fixAss.fin.loansToAffil.other",
		("0505", "0810", "Ausleihungen an verbundene Unternehmen"),
		reason=Reason.LEGAL_FORM_SPLIT,
	),
	_position(
		"bs.ass.fixAss.fin.loansToAffil.partnerships.other",
		("0506", "0813", "Ausleihungen an verbundene Unternehmen, Personengesellschaften"),
	),
	_position(
		"bs.ass.fixAss.fin.loansToAffil.corporations",
		("0507", "0814", "Ausleihungen an verbundene Unternehmen, Kapitalgesellschaften"),
	),
	_position(
		"bs.ass.fixAss.fin.loansToAffil.soleProprietor",
		("0508", "0815", "Ausleihungen an verbundene Unternehmen, Einzelunternehmen"),
	),
	_position(
		"bs.ass.fixAss.fin.particip.other",
		("0510", "0820", "Beteiligungen"),
		reason=Reason.LEGAL_FORM_SPLIT,
	),
	_watched(
		Reason.PARTNERSHIP,
		(None, "0829", "Beteiligung einer GmbH & Co. KG an einer Komplementär-GmbH"),
	),
	_position(
		"bs.ass.fixAss.fin.particip.other",
		("0513", "0830", "Typisch stille Beteiligungen"),
		reason=Reason.TYPICAL_SILENT,
	),
	_position(
		"bs.ass.fixAss.fin.particip.partnerships.commPart.silentAtyp",
		("0516", "0840", "Atypisch stille Beteiligungen"),
	),
	_position(
		"bs.ass.fixAss.fin.particip.corporations",
		("0517", "0850", "Beteiligungen an Kapitalgesellschaften"),
	),
	_position(
		"bs.ass.fixAss.fin.particip.partnerships.commPart.other",
		("0518", "0860", "Beteiligungen an Personengesellschaften"),
		reason=Reason.MITUNTERNEHMERSCHAFT,
	),
	_watched(
		Reason.PARTNERSHIP,
		("0519", None, "Beteiligung einer GmbH & Co. KG an einer Komplementär GmbH"),
	),
	_position(
		"bs.ass.fixAss.fin.loansToParticip.other",
		("0520", "0880", "Ausleihungen an Unternehmen, mit denen ein Beteiligungsverhältnis besteht"),
		reason=Reason.LEGAL_FORM_SPLIT,
	),
	_position(
		"bs.ass.fixAss.fin.loansToParticip.partnerships.other",
		(
			"0523",
			"0883",
			"Ausleihungen an Unternehmen, mit denen ein Beteiligungsverhältnis besteht, Personengesellschaften",
		),
	),
	_position(
		"bs.ass.fixAss.fin.loansToParticip.corporations",
		(
			"0524",
			"0885",
			"Ausleihungen an Unternehmen, mit denen ein Beteiligungsverhältnis besteht, Kapitalgesellschaften",
		),
	),
	_position(
		"bs.ass.fixAss.fin.securities",
		("0525", "0900", "Wertpapiere des Anlagevermögens"),
		(
			"0530",
			"0910",
			"Wertpapiere mit Gewinnbeteiligungsansprüchen, die dem Teileinkünfteverfahren unterliegen",
		),
		("0535", "0920", "Festverzinsliche Wertpapiere"),
	),
	_position(
		"bs.ass.fixAss.fin.otherLoans.other",
		("0540", "0930", "Übrige sonstige Ausleihungen"),
		("0550", "0940", "Darlehen"),
		("0565", None, "Darlehen"),
	),
	_position(
		"bs.ass.fixAss.fin.loansToSharehold.gmbh",
		("0580", "0960", "Ausleihungen an Gesellschafter"),
		("0582", "0961", "Ausleihungen an GmbH-Gesellschafter"),
		shareholder=True,
		reason=Reason.GMBH_SHAREHOLDERS,
	),
	_watched(
		Reason.PARTNERSHIP,
		("0584", "0962", "Ausleihungen an persönlich haftende Gesellschafter"),
		("0586", "0963", "Ausleihungen an Kommanditisten"),
	),
	_position(
		"bs.ass.fixAss.fin.otherLoans.other",
		(None, "0964", "Ausleihungen an stille Gesellschafter"),
		("0590", "0970", "Ausleihungen an nahe stehende Personen"),
	),
	_position(
		"bs.ass.fixAss.fin.otherFinAss.coopShares",
		("0570", "0980", "Genossenschaftsanteile zum langfristigen Verbleib"),
	),
	_position(
		"bs.ass.fixAss.fin.otherFinAss.reInsurClaim",
		("0595", "0990", "Rückdeckungsansprüche aus Lebensversicherungen zum langfristigen Verbleib"),
	),
	_position(
		"bs.ass.currAss.inventory.material",
		("3970-3979", "1000-1039", "Roh-, Hilfs- und Betriebsstoffe (Bestand)"),
	),
	_position(
		"bs.ass.currAss.inventory.inProgress",
		("7000", "1040-1049", "Unfertige Erzeugnisse, unfertige Leistungen (Bestand)"),
		("7050", "1050-1079", "Unfertige Erzeugnisse (Bestand)"),
		("7080", "1080-1089", "Unfertige Leistungen (Bestand)"),
		("7090", "1090-1094", "In Ausführung befindliche Bauaufträge"),
		("7095", "1095-1099", "In Arbeit befindliche Aufträge"),
	),
	_position(
		"bs.ass.currAss.inventory.finishedAndMerch",
		("7100", "1100-1109", "Fertige Erzeugnisse und Waren (Bestand)"),
		("7110", "1110-1139", "Fertige Erzeugnisse (Bestand)"),
		("7140", None, "Waren (Bestand)"),
		("3980-3989", "1140-1179", "Waren (Bestand)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.misc",
		("3990-3999", None, "Verrechnete Stoffkosten (Gegenkonto zu 4000-99)"),
		("4000-4099", None, "Material- und Stoffverbrauch"),
		reason=Reason.MATERIAL_MIXED,
	),
	_position(
		"bs.ass.currAss.inventory.advPaymPaid",
		("1510", "1180", "Geleistete Anzahlungen auf Vorräte"),
		("1511", None, "Geleistete Anzahlungen, 7 % Vorsteuer"),
		(None, "1181", "Geleistete Anzahlungen 7 % Vorsteuer"),
		("1512", "1182", "Geleistete Anzahlungen, 5 % Vorsteuer"),
		("1517", "1184", "Geleistete Anzahlungen, 16 % Vorsteuer"),
		("1518", None, "Geleistete Anzahlungen, 19 % Vorsteuer"),
		(None, "1185", "Geleistete Anz., 15 % Vorsteuer"),
		(None, "1186", "Geleistete Anzahlungen 19 % Vorsteuer"),
	),
	_position(
		"bs.ass.currAss.inventory.advPaymReceived",
		("1722", "1190", "Erhaltene Anzahlungen auf Bestellungen (von Vorräten offen abgesetzt)"),
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		("1400", "1200", "Forderungen aus Lieferungen und Leistungen"),
		("1401-1406", "1201-1206", "Forderungen aus Lieferungen und Leistungen"),
		("1410-1444", "1210-1214", "Forderungen aus Lieferungen und Leistungen ohne Kontokorrent"),
		opposite="bs.eqLiab.liab.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_watched(
		Reason.EUR,
		(
			"1445",
			"1215",
			"Forderungen aus Lieferungen und Leistungen zum allgemeinen Umsatzsteuersatz oder eines Kleinunternehmers (EÜR)",
		),
		("1446", "1216", "Forderungen aus Lieferungen und Leistungen zum ermäßigten Umsatzsteuersatz (EÜR)"),
		(
			"1447",
			"1217",
			"Forderungen aus steuerfreien oder nicht steuerbaren Lieferungen und Leistungen (EÜR)",
		),
		(
			"1448",
			"1218",
			"Forderungen aus Lieferungen und Leistungen nach Durchschnittssätzen nach § 24 UStG (EÜR)",
		),
		("1449", None, "Gegenkonto 1445-1448 bei Aufteilung der Forderungen nach Steuersätzen (EÜR)"),
		(None, "1219", "Gegenkonto 1215-1218 bei Aufteilung der Forderungen nach Steuersätzen (EÜR)"),
		("1450", "1220", "Forderungen nach § 11 Abs. 1 Satz 2 EStG für § 4 Abs. 3 EStG"),
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		(
			"1451",
			"1221",
			"Forderungen aus Lieferungen und Leistungen ohne Kontokorrent - Restlaufzeit bis 1 Jahr",
		),
		opposite="bs.eqLiab.liab.other.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		(
			"1455",
			"1225",
			"Forderungen aus Lieferungen und Leistungen ohne Kontokorrent - Restlaufzeit größer 1 Jahr",
		),
		opposite="bs.eqLiab.liab.other.other",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		(None, "1235", "Wechsel aus Lieferungen und Leistungen, bundesbankfähig"),
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		("1460", "1240", "Zweifelhafte Forderungen"),
		opposite="bs.eqLiab.liab.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		("1461", "1241", "Zweifelhafte Forderungen - Restlaufzeit bis 1 Jahr"),
		opposite="bs.eqLiab.liab.other.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		("1465", "1245", "Zweifelhafte Forderungen - Restlaufzeit größer 1 Jahr"),
		opposite="bs.eqLiab.liab.other.other",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		("0998", "1246", "Einzelwertberichtigungen auf Forderungen - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.ALLOWANCE,
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		("0999", "1247", "Einzelwertberichtigungen auf Forderungen - Restlaufzeit größer 1 Jahr"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.ALLOWANCE,
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		("0996", "1248", "Pauschalwertberichtigung auf Forderungen - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.ALLOWANCE,
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		("0997", "1249", "Pauschalwertberichtigung auf Forderungen - Restlaufzeit größer 1 Jahr"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.ALLOWANCE,
	),
	_position(
		"bs.ass.currAss.receiv.trade.shareholders",
		("1490", "1250", "Forderungen aus Lieferungen und Leistungen gegen Gesellschafter"),
		opposite="bs.eqLiab.liab.shareholders.gmbh",
		shareholder=True,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.trade.shareholders",
		(
			"1491",
			"1251",
			"Forderungen aus Lieferungen und Leistungen gegen Gesellschafter - Restlaufzeit bis 1 Jahr",
		),
		opposite="bs.eqLiab.liab.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.trade.shareholders",
		(
			"1495",
			"1255",
			"Forderungen aus Lieferungen und Leistungen gegen Gesellschafter - Restlaufzeit größer 1 Jahr",
		),
		opposite="bs.eqLiab.liab.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		("1498", "1258", "Gegenkonto zu sonstigen Vermögensgegenständen bei Buchungen über Debitorenkonto"),
		reason=Reason.DEBTOR_COUNTER,
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		("1499", None, "Gegenkonto 1451-1497 bei Aufteilung Debitorenkonto"),
		(
			None,
			"1259",
			"Gegenkonto 1221-1229, 1240-1245,1250-1257, 1270-1279, 1290-1297 bei Aufteilung Debitorenkonto",
		),
		reason=Reason.SPLIT_COUNTER,
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		("1594", "1260", "Forderungen gegen verbundene Unternehmen"),
		opposite="bs.eqLiab.liab.assocComp.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		("1595", "1261", "Forderungen gegen verbundene Unternehmen - Restlaufzeit bis 1 Jahr"),
		opposite="bs.eqLiab.liab.assocComp.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		("1596", "1265", "Forderungen gegen verbundene Unternehmen - Restlaufzeit größer 1 Jahr"),
		opposite="bs.eqLiab.liab.assocComp.other",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		(None, "1266", "Besitzwechsel gg. verb. Unternehmen"),
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		(None, "1267", "Besitzwechsel gg. verb. Unternehmen (b. 1 J.)"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		(None, "1268", "Besitzwechsel gg. verb. Unternehmen (größer 1 J.)"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		(None, "1269", "Besitzwechsel gg. verb. Unternehmen, bundesbankfähig"),
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		("1470", "1270", "Forderungen aus Lieferungen und Leistungen gegen verbundene Unternehmen"),
		opposite="bs.eqLiab.liab.assocComp.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		(
			"1471",
			"1271",
			"Forderungen aus Lieferungen und Leistungen gegen verbundene Unternehmen - Restlaufzeit bis 1 Jahr",
		),
		opposite="bs.eqLiab.liab.assocComp.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		(
			"1475",
			"1275",
			"Forderungen aus Lieferungen und Leistungen gegen verbundene Unternehmen - Restlaufzeit größer 1 Jahr",
		),
		opposite="bs.eqLiab.liab.assocComp.other",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		(
			"1478",
			"1276",
			"Wertberichtigungen auf Forderungen gegen verbundene Unternehmen - Restlaufzeit bis 1 Jahr",
		),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.ALLOWANCE,
	),
	_position(
		"bs.ass.currAss.receiv.affil",
		(
			"1479",
			"1277",
			"Wertberichtigungen auf Forderungen gegen verbundene Unternehmen - Restlaufzeit größer 1 Jahr",
		),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.ALLOWANCE,
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		("1597", "1280", "Forderungen gegen Unternehmen, mit denen ein Beteiligungsverhältnis besteht"),
		opposite="bs.eqLiab.liab.particip.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		(
			"1598",
			"1281",
			"Forderungen gegen Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit bis 1 Jahr",
		),
		opposite="bs.eqLiab.liab.particip.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		(
			"1599",
			"1285",
			"Forderungen gegen Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit größer 1 Jahr",
		),
		opposite="bs.eqLiab.liab.particip.other",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		(None, "1286", "Besitzwechsel gg. Unt., mit denen ein Beteiligungsverh. besteht"),
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		(None, "1287", "Besitzwechsel gg. Unt., mit denen ein Beteiligungsverh. besteht (b. 1 J.)"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		(None, "1288", "Besitzwechsel gg. Unt., mit denen ein Beteiligungsverh. besteht (größer 1 J.)"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		(None, "1289", "Besitzwechsel gg. Unt., mit denen ein Beteiligungsverh. besteht, bundesbankfähig"),
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		(
			"1480",
			"1290",
			"Forderungen aus Lieferungen und Leistungen gegen Unternehmen, mit denen ein Beteiligungsverhältnis besteht",
		),
		opposite="bs.eqLiab.liab.particip.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		(
			"1481",
			"1291",
			"Forderungen aus Lieferungen und Leistungen gegen Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit bis 1 Jahr",
		),
		opposite="bs.eqLiab.liab.particip.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		(
			"1485",
			"1295",
			"Forderungen aus Lieferungen und Leistungen gegen Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit größer 1 Jahr",
		),
		opposite="bs.eqLiab.liab.particip.other",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		(
			"1488",
			"1296",
			"Wertberichtigungen auf Forderungen gegen Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit bis 1 Jahr",
		),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.ALLOWANCE,
	),
	_position(
		"bs.ass.currAss.receiv.particip",
		(
			"1489",
			"1297",
			"Wertberichtigungen auf Forderungen gegen Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit größer 1 Jahr",
		),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.ALLOWANCE,
	),
	_position(
		"bs.ass.currAss.receiv.other.unpaidCapital",
		(
			None,
			"1298",
			"Ausstehende Einlagen auf das gezeichnete Kapital, eingefordert (Forderungen, nicht eingeforderte ausstehende Einlagen s. Konto 2910)",
		),
	),
	_position(
		"bs.ass.currAss.receiv.other.unpaidSupplementaryCalls",
		(None, "1299", "Nachschüsse (Forderungen, Gegenkonto 2929)"),
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1500", "1300", "Sonstige Vermögensgegenstände"),
		opposite="bs.eqLiab.liab.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1501", "1301", "Sonstige Vermögensgegenstände - Restlaufzeit bis 1 Jahr"),
		opposite="bs.eqLiab.liab.other.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1502", "1305", "Sonstige Vermögensgegenstände - Restlaufzeit größer 1 Jahr"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.ass.currAss.receiv.other.bodies",
		("1503", None, "Forderungen gegen Vorstandsmitglieder und Geschäftsführer - Restlaufzeit bis 1 Jahr"),
		opposite="bs.eqLiab.liab.other.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.bodies",
		(
			"1504",
			None,
			"Forderungen gegen Vorstandsmitglieder und Geschäftsführer - Restlaufzeit größer 1 Jahr",
		),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.ass.currAss.receiv.other.bodies",
		("1505", None, "Forderungen gegen Aufsichtsrats- und Beiratsmitglieder - Restlaufzeit bis 1 Jahr"),
		opposite="bs.eqLiab.liab.other.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.bodies",
		("1506", None, "Forderungen gegen Aufsichtsrats- und Beiratsmitglieder - Restlaufzeit größer 1 Jahr"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.ass.currAss.receiv.shareholders.gmbh",
		("1507", None, "Forderungen gegen sonstige Gesellschafter - Restlaufzeit bis 1 Jahr"),
		opposite="bs.eqLiab.liab.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.OTHER_SHAREHOLDERS,
	),
	_position(
		"bs.ass.currAss.receiv.shareholders.gmbh",
		("1508", None, "Forderungen gegen sonstige Gesellschafter - Restlaufzeit größer 1 Jahr"),
		opposite="bs.eqLiab.liab.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.OTHER_SHAREHOLDERS,
	),
	_position(
		"bs.ass.currAss.receiv.shareholders.gmbh",
		("1381", "1307", "Forderungen gegen GmbH-Gesellschafter"),
		opposite="bs.eqLiab.liab.shareholders.gmbh",
		shareholder=True,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.shareholders.gmbh",
		("1382", "1308", "Forderungen gegen GmbH-Gesellschafter - Restlaufzeit bis 1 Jahr"),
		opposite="bs.eqLiab.liab.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.shareholders.gmbh",
		("1383", "1309", "Forderungen gegen GmbH-Gesellschafter - Restlaufzeit größer 1 Jahr"),
		opposite="bs.eqLiab.liab.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.bodies",
		(None, "1310", "Forderungen gegen Vorstandsmitglieder und Geschäftsführer"),
		opposite="bs.eqLiab.liab.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.bodies",
		(None, "1311", "Forderungen gegen Vorstandsmitglieder und Geschäftsführer - Restlaufzeit bis 1 Jahr"),
		opposite="bs.eqLiab.liab.other.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.bodies",
		(
			None,
			"1315",
			"Forderungen gegen Vorstandsmitglieder und Geschäftsführer - Restlaufzeit größer 1 Jahr",
		),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_watched(
		Reason.PARTNERSHIP,
		("1385", "1317", "Forderungen gegen persönlich haftende Gesellschafter"),
		("1386", "1318", "Forderungen gegen persönlich haftende Gesellschafter - Restlaufzeit bis 1 Jahr"),
		("1387", "1319", "Forderungen gegen persönlich haftende Gesellschafter - Restlaufzeit größer 1 Jahr"),
	),
	_position(
		"bs.ass.currAss.receiv.other.bodies",
		(None, "1320", "Forderungen gegen Aufsichtsrats- und Beirats-Mitglieder"),
		opposite="bs.eqLiab.liab.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.bodies",
		(None, "1321", "Forderungen gegen Aufsichtsrats- und Beirats-Mitglieder - Restlaufzeit bis 1 Jahr"),
		opposite="bs.eqLiab.liab.other.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.bodies",
		(
			None,
			"1325",
			"Forderungen gegen Aufsichtsrats- und Beirats-Mitglieder - Restlaufzeit größer 1 Jahr",
		),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.ass.currAss.receiv.shareholders.gmbh",
		(None, "1330", "Forderungen gegen sonstige Gesellschafter"),
		opposite="bs.eqLiab.liab.shareholders.gmbh",
		shareholder=True,
		reason=Reason.OTHER_SHAREHOLDERS,
	),
	_position(
		"bs.ass.currAss.receiv.shareholders.gmbh",
		(None, "1331", "Forderungen gegen sonstige Gesellschafter - Restlaufzeit bis 1 Jahr"),
		opposite="bs.eqLiab.liab.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.OTHER_SHAREHOLDERS,
	),
	_position(
		"bs.ass.currAss.receiv.shareholders.gmbh",
		(None, "1335", "Forderungen gegen sonstige Gesellschafter - Restlaufzeit größer 1 Jahr"),
		opposite="bs.eqLiab.liab.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.OTHER_SHAREHOLDERS,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1376", "1337", "Forderungen gegen typisch stille Gesellschafter"),
		reason=Reason.TYPICAL_SILENT_RECEIVABLE,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1377", "1338", "Forderungen gegen typisch stille Gesellschafter - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.TYPICAL_SILENT_RECEIVABLE,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1378", "1339", "Forderungen gegen typisch stille Gesellschafter - Restlaufzeit größer 1 Jahr"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.TYPICAL_SILENT_RECEIVABLE,
	),
	_outside(
		Outside.INTERIM,
		("1380", None, "Überleitungskonto Kostenstelle"),
	),
	_position(
		"bs.ass.currAss.receiv.other.employees",
		("1530", "1340", "Forderungen gegen Personal aus Lohn- und Gehaltsabrechnung"),
	),
	_position(
		"bs.ass.currAss.receiv.other.employees",
		(
			"1531",
			"1341",
			"Forderungen gegen Personal aus Lohn- und Gehaltsabrechnung - Restlaufzeit bis 1 Jahr",
		),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.ass.currAss.receiv.other.employees",
		(
			"1537",
			"1345",
			"Forderungen gegen Personal aus Lohn- und Gehaltsabrechnung - Restlaufzeit größer 1 Jahr",
		),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_watched(
		Reason.SONDERBILANZ,
		(
			"1389",
			"1349",
			"Ansprüche aus betrieblicher Altersversorgung und Pensionsansprüche (Mitunternehmer)",
		),
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1525", "1350", "Kautionen"),
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1526", "1351", "Kautionen - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1527", "1355", "Kautionen - Restlaufzeit größer 1 Jahr"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1550", "1360", "Darlehen"),
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1551", "1361", "Darlehen - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1555", "1365", "Darlehen - Restlaufzeit größer 1 Jahr"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.ass.currAss.receiv.other.socInsur",
		("1520", "1369", "Forderungen gegenüber Krankenkassen aus Aufwendungsausgleichsgesetz"),
		opposite="bs.eqLiab.liab.other.thereoffSocSec",
		reason=Reason.SOCIAL_SECURITY_BOTH,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1590", "1370", "Durchlaufende Posten"),
		("1592", "1374", "Fremdgeld"),
		("1521", "1375", "Agenturwarenabrechnung"),
		opposite="bs.eqLiab.liab.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.vat",
		("1528", "1376", "Nachträglich abziehbare Vorsteuer nach § 15a Abs. 2 UStG"),
		("1529", "1377", "Zurückzuzahlende Vorsteuer nach § 15a Abs. 2 UStG"),
		opposite="bs.eqLiab.liab.other.theroffTax",
		reason=Reason.VAT,
	),
	_position(
		"bs.ass.currAss.receiv.other.reInsurClaim",
		("1355", "1378", "Ansprüche aus Rückdeckungsversicherungen"),
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		(
			"1356",
			"1380",
			"Vermögensgegenstände zur Erfüllung von Pensionsrückstellungen und ähnlichen Verpflichtungen zum langfristigen Verbleib",
		),
		purpose=Purpose.TAX,
		reason=Reason.PENSION_ASSETS_TAX,
	),
	_position(
		"bs.eqLiab.accruals.pensions.other",
		(
			"1357",
			"1381",
			"Vermögensgegenstände zur Saldierung mit Pensionsrückstellungen und ähnlichen Verpflichtungen zum langfristigen Verbleib nach § 246 Abs. 2 HGB",
		),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.OFFSET_PENSIONS,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		(
			"1353",
			"1382",
			"Vermögensgegenstände zur Erfüllung von mit der Altersversorgung vergleichbaren langfristigen Verpflichtungen",
		),
		purpose=Purpose.TAX,
		reason=Reason.PENSION_ASSETS_TAX,
	),
	_position(
		"bs.eqLiab.accruals.other",
		(
			"1354",
			"1383",
			"Vermögensgegenstände zur Saldierung mit der Altersversorgung vergleichbaren langfristigen Verpflichtungen nach § 246 Abs. 2 HGB",
		),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.OFFSET_OTHER,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1350", "1390", "GmbH-Anteile zum kurzfristigen Verbleib"),
		reason=Reason.GMBH_SHARES_SHORT,
	),
	_position(
		"bs.ass.currAss.receiv.other.jointWork",
		("1519", "1391", "Forderungen gegen Arbeitsgemeinschaften"),
		opposite="bs.eqLiab.liab.other.jointVent",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.profSharRights",
		("1522", "1393", "Genussrechte"),
	),
	_position(
		"bs.ass.currAss.receiv.other.secondaryPaym",
		("1524", "1394", "Einzahlungsansprüche zu Nebenleistungen oder Zuzahlungen"),
	),
	_position(
		"bs.ass.currAss.receiv.other.coopShares",
		("1352", "1395", "Genossenschaftsanteile zum kurzfristigen Verbleib"),
	),
	_position(
		"bs.ass.currAss.receiv.other.vat",
		(
			"1556",
			"1396",
			"Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter",
		),
		("1557", "1397", "Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, bewegliche Wirtschaftsgüter"),
		(
			"1558",
			"1398",
			"Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter",
		),
		("1559", "1399", "Zurückzuzahlende Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche Wirtschaftsgüter"),
		("1570", "1400", "Abziehbare Vorsteuer"),
		("1571", "1401", "Abziehbare Vorsteuer 7 %"),
		("1572", "1402", "Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb"),
		("1574", "1404", "Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb 19 %"),
		("1576", "1406", "Abziehbare Vorsteuer 19 %"),
		("1577", "1407", "Abziehbare Vorsteuer nach § 13b UStG 19 %"),
		("1578", "1408", "Abziehbare Vorsteuer nach § 13b UStG"),
		("1560", "1410", "Aufzuteilende Vorsteuer"),
		("1561", "1411", "Aufzuteilende Vorsteuer 7 %"),
		("1562", "1412", "Aufzuteilende Vorsteuer aus innergemeinschaftlichem Erwerb"),
		("1563", "1413", "Aufzuteilende Vorsteuer aus innergemeinschaftlichem Erwerb 19 %"),
		("1566", "1416", "Aufzuteilende Vorsteuer 19 %"),
		("1567", "1417", "Aufzuteilende Vorsteuer nach §§ 13a und 13b UStG"),
		("1569", "1419", "Aufzuteilende Vorsteuer nach §§ 13a und 13b UStG 19 %"),
		opposite="bs.eqLiab.liab.other.theroffTax",
		reason=Reason.VAT,
	),
	_position(
		"bs.ass.currAss.receiv.other.vat",
		("1545", "1420", "Forderungen aus Umsatzsteuer-Vorauszahlungen"),
	),
	_position(
		"bs.ass.currAss.receiv.other.vat",
		(None, "1421", "Umsatzsteuerforderungen laufendes Jahr"),
		("1546", "1422", "Umsatzsteuerforderungen Vorjahr"),
		("1539", "1425", "Umsatzsteuerforderungen frühere Jahre"),
		opposite="bs.eqLiab.liab.other.theroffTax",
		reason=Reason.VAT,
	),
	_position(
		"bs.ass.currAss.receiv.other.otherTaxRec",
		("1547", "1427", "Forderungen aus entrichteten Verbrauchsteuern"),
		opposite="bs.eqLiab.liab.other.theroffTax",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.vat",
		(
			"1585",
			"1431",
			"Abziehbare Vorsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager",
		),
		(
			"1584",
			"1432",
			"Abziehbare Vorsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen von Lieferanten ohne USt-Identifikationsnummer",
		),
		("1588", "1433", "Entstandene Einfuhrumsatzsteuer"),
		("1548", "1434", "Vorsteuer in Folgeperiode/im Folgejahr abziehbar"),
		opposite="bs.eqLiab.liab.other.theroffTax",
		reason=Reason.VAT,
	),
	_position(
		"bs.ass.currAss.receiv.other.tradeTaxOverpayment",
		("1540", "1435", "Forderungen aus Gewerbesteuerüberzahlungen"),
		opposite="bs.eqLiab.liab.other.theroffTax",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.vat",
		("1573", "1436", "Vorsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts"),
		opposite="bs.eqLiab.liab.other.theroffTax",
		reason=Reason.VAT,
	),
	_position(
		"bs.ass.currAss.receiv.other.otherTaxRec",
		("1542", "1440", "Steuererstattungsansprüche gegenüber anderen Ländern"),
	),
	_position(
		"bs.ass.currAss.receiv.other.corpTaxOverpayment",
		("1549", "1450", "Körperschaftsteuerrückforderung"),
		opposite="bs.eqLiab.liab.other.theroffTax",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.ass.currAss.receiv.other.otherTaxRec",
		("1543", "1456", "Forderungen an das Finanzamt aus abgeführtem Bauabzugsbetrag"),
	),
	_position(
		"bs.ass.currAss.receiv.other.socInsur",
		("1544", "1457", "Forderung gegenüber Bundesagentur für Arbeit"),
		opposite="bs.eqLiab.liab.other.thereoffSocSec",
		reason=Reason.SOCIAL_SECURITY_BOTH,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1360", "1460", "Geldtransit"),
		opposite="bs.eqLiab.liab.other.other",
		reason=Reason.CASH_IN_TRANSIT,
	),
	_watched(
		Reason.EUR,
		("1371", None, "Verrechnungskonto Gewinnermittlung § 4 Abs. 3 EStG, nicht ergebniswirksam"),
		("1580", "1480", "Gegenkonto Vorsteuer § 4 Abs. 3 EStG"),
		("1581", "1481", "Auflösung Vorsteuer aus Vorjahr § 4 Abs. 3 EStG"),
		("1582", "1482", "Vorsteuer aus Investitionen § 4 Abs. 3 EStG"),
	),
	_watched(
		Reason.FLAT_RATE_23,
		(None, "1484", "Vorsteuer nach allgemeinen Durchschnittssätzen UStVA Kz. 63"),
	),
	_watched(
		Reason.EUR,
		(None, "1486", "Verrechnungskonto für Gewinnermittlung § 4 Abs. 3 EStG, nicht ergebniswirksam"),
		("1372", "1487", "Wirtschaftsgüter des Umlaufvermögens nach § 4 Abs. 3 Satz 4 EStG"),
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1390", "1490", "Verrechnungskonto Ist-Versteuerung"),
		opposite="bs.eqLiab.liab.other.other",
		reason=Reason.IST_CLEARING,
	),
	_watched(
		Reason.EUR,
		("1391", "1491", "Neutralisierung ertragswirksamer Sachverhalte für § 4 Abs. 3 EStG"),
	),
	_watched(
		Reason.SONDERBILANZ,
		("1394", "1494", "Forderungen gegen Gesellschaft/Gesamthand"),
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1593", "1495", "Verrechnungskonto erhaltene Anzahlungen bei Buchung über Debitorenkonto"),
		opposite="bs.ass.currAss.receiv.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_outside(
		Outside.INTERIM,
		(None, "1498", "Überleitungskonto Kostenstellen"),
	),
	_position(
		"bs.ass.currAss.securities.affil",
		("1340", "1500", "Anteile an verbundenen Unternehmen (Umlaufvermögen)"),
		("1344", "1504", "Anteile an herrschender oder mehrheitlich beteiligter Gesellschaft"),
	),
	_position(
		"bs.ass.currAss.securities.other",
		("1348", "1510", "Sonstige Wertpapiere"),
		(None, "1520", "Finanzwechsel"),
		("1329", "1525", "Andere Wertpapiere mit unwesentlichen Wertschwankungen"),
		("1349", "1530", "Wertpapieranlagen im Rahmen der kurzfristigen Finanzdisposition"),
	),
	_position(
		"bs.ass.currAss.cashEquiv.cheques",
		(None, "1550", "Schecks"),
	),
	_position(
		"bs.ass.currAss.cashEquiv.cash",
		("1000", "1600", "Kasse"),
		("1010", "1610", "Nebenkasse 1"),
		("1020", "1620", "Nebenkasse 2"),
	),
	_position(
		"bs.ass.currAss.cashEquiv.bank",
		("1100", "1700", "Bank (Postbank)"),
		("1110", "1710", "Bank (Postbank"),
		("1120", "1720", "Bank (Postbank"),
		("1130", "1730", "Bank (Postbank"),
		opposite="bs.eqLiab.liab.bank.other",
		reason=Reason.OVERDRAWN,
	),
	_position(
		"bs.ass.currAss.cashEquiv.centralBank",
		("1190", "1780", "LZB-Guthaben"),
		("1195", "1790", "Bundesbankguthaben"),
		opposite="bs.eqLiab.liab.bank.other",
		reason=Reason.OVERDRAWN,
	),
	_position(
		"bs.ass.currAss.cashEquiv.bank",
		("1200", "1800", "Bank"),
		("1210", "1810", "Bank 1"),
		("1220", "1820", "Bank 2"),
		("1230", "1830", "Bank 3"),
		("1240", "1840", "Bank 4"),
		("1250", "1850", "Bank 5"),
		(
			"1290",
			"1890",
			"Finanzmittelanlagen im Rahmen der kurzfristigen Finanzdisposition (nicht im Finanzmittelfonds enthalten)",
		),
		opposite="bs.eqLiab.liab.bank.other",
		reason=Reason.OVERDRAWN,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		(
			"1295",
			"1895",
			"Verbindlichkeiten gegenüber Kreditinstituten (nicht im Finanzmittelfonds enthalten)",
		),
		opposite="bs.ass.currAss.cashEquiv.bank",
		reason=Reason.BANK_LIABILITY,
	),
	_position(
		"bs.ass.prepaidExp",
		("0980", "1900", "Aktive Rechnungsabgrenzung"),
	),
	_position(
		"bs.ass.prepaidExp",
		("0984", "1920", "Als Aufwand berücksichtigte Zölle und Verbrauchsteuern auf Vorräte"),
		("0985", "1930", "Als Aufwand berücksichtigte Umsatzsteuer auf Anzahlungen"),
		purpose=Purpose.TAX,
	),
	_position(
		"bs.ass.prepaidExp",
		("0986", "1940", "Damnum/Disagio"),
	),
	_position(
		"bs.ass.defTax",
		("0983", "1950", "Aktive latente Steuern"),
		purpose=Purpose.COMMERCIAL,
	),
	_watched(
		Reason.PARTNERSHIP,
		("0870", "2000", "Festkapital"),
		("0871", None, "Kapital (fester Anteil, nur Einzelunternehmen)"),
		(None, "2001", "Kapital (fester Anteil nur Einzelunternehmen)"),
		("0880", "2010", "Variables Kapital"),
		("0881", "2011", "Kapital (variabler Anteil, nur Einzelunternehmen)"),
		("0890", "2020", "Gesellschafter-Darlehen"),
		(None, "2030-2049", "(zur freien Verfügung)"),
		("0900", "2050", "Kommandit-Kapital"),
		("0910", "2060", "Verlustausgleichskonto"),
		("0920", "2070", "Gesellschafter-Darlehen"),
		("1800", "2100", "Privatentnahmen allgemein"),
		("1801", "2101", "Privatentnahmen allgemein (nur Einzelunternehmen)"),
		(None, "2110", "Privatentnahmen allgemein"),
		(None, "2111", "Privatentnahmen allgemein (nur Einzelunternehmen)"),
		(None, "2120", "Privatentnahmen allgemein"),
		(None, "2121", "Privatentnahmen allgemein (nur Einzelunternehmen)"),
		("1880", "2130", "Unentgeltliche Wertabgaben"),
		("1881", "2131", "Unentgeltliche Wertabgaben (nur Einzelunternehmen)"),
		(None, "2140", "Unentgeltliche Wertabgaben"),
		(None, "2141", "Unentgeltliche Wertabgaben (nur Einzelunternehmen)"),
		("1810", "2150", "Privatsteuern"),
		("1811", "2151", "Privatsteuern (nur Einzelunternehmen)"),
		(None, "2160", "Privatsteuern"),
		(None, "2161", "Privatsteuern (nur Einzelunternehmen)"),
		(None, "2170", "Privatsteuern"),
		(None, "2171", "Privatsteuern (nur Einzelunternehmen)"),
		("1890", "2180", "Privateinlagen"),
		("1891", "2181", "Privateinlagen (nur Einzelunternehmen)"),
		(None, "2190", "Privateinlagen"),
		(None, "2191", "Privateinlagen (nur Einzelunternehmen)"),
		("1820", "2200", "Sonderausgaben beschränkt abzugsfähig"),
		("1821", "2201", "Sonderausgaben beschränkt abzugsfähig (nur Einzelunternehmen)"),
		(None, "2210", "Sonderausgaben beschränkt abzugsfähig"),
		(None, "2211", "Sonderausgaben beschränkt abzugsfähig (nur Einzelunternehmen)"),
		(None, "2220", "Sonderausgaben beschränkt abzugsfähig"),
		(None, "2221", "Sonderausgaben beschränkt abzugsfähig (nur Einzelunternehmen)"),
		("1830", "2230", "Sonderausgaben unbeschränkt abzugsfähig"),
		("1831", "2231", "Sonderausgaben unbeschränkt abzugsfähig (nur Einzelunternehmen)"),
		(None, "2240", "Sonderausgaben unbeschränkt abzugsfähig"),
		(None, "2241", "Sonderausgaben unbeschränkt abzugsfähig (nur Einzelunternehmen)"),
		("1840", "2250", "Zuwendungen, Spenden"),
		("1841", "2251", "Zuwendungen, Spenden (nur Einzelunternehmen)"),
		(None, "2260", "Zuwendungen, Spenden"),
		(None, "2261", "Zuwendungen, Spenden (nur Einzelunternehmen)"),
		(None, "2270", "Zuwendungen, Spenden"),
		(None, "2271", "Zuwendungen, Spenden (nur Einzelunternehmen)"),
		("1850", "2280", "Außergewöhnliche Belastungen"),
		("1851", "2281", "Außergewöhnliche Belastungen (nur Einzelunternehmen)"),
		(None, "2290", "Außergewöhnliche Belastungen"),
		(None, "2291", "Außergewöhnliche Belastungen (nur Einzelunternehmen)"),
		("1860", "2300", "Grundstücksaufwand"),
		("1861", "2301", "Grundstücksaufwand (nur Einzelunternehmen)"),
		("1869", "2309", "Grundstücksaufwand (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen)"),
		(None, "2310", "Grundstücksaufwand"),
		(None, "2311", "Grundstücksaufwand (nur Einzelunternehmen)"),
		(None, "2319", "Grundstücksaufwand (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen)"),
		(None, "2320", "Grundstücksaufwand"),
		(None, "2321", "Grundstücksaufwand (nur Einzelunternehmen)"),
		(None, "2329", "Grundstücksaufwand (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen)"),
		(None, "2330", "Grundstücksaufwand"),
		(None, "2331", "Grundstücksaufwand (nur Einzelunternehmen)"),
		(None, "2339", "Grundstücksaufwand (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen)"),
		(None, "2340", "Grundstücksaufwand"),
		(None, "2341", "Grundstücksaufwand (nur Einzelunternehmen)"),
		(None, "2349", "Grundstücksaufwand (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen)"),
		("1870", "2350", "Grundstücksertrag"),
		("1871", "2351", "Grundstücksertrag (nur Einzelunternehmen)"),
		("1879", "2359", "Grundstücksertrag (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen)"),
		(None, "2360", "Grundstücksertrag"),
		(None, "2361", "Grundstücksertrag (nur Einzelunternehmen)"),
		(None, "2369", "Grundstücksertrag (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen)"),
		(None, "2370", "Grundstücksertrag"),
		(None, "2371", "Grundstücksertrag (nur Einzelunternehmen)"),
		(None, "2379", "Grundstücksertrag (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen)"),
		(None, "2380", "Grundstücksertrag"),
		(None, "2381", "Grundstücksertrag (nur Einzelunternehmen)"),
		(None, "2389", "Grundstücksertrag (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen)"),
		(None, "2390", "Grundstücksertrag"),
		(None, "2391", "Grundstücksertrag (nur Einzelunternehmen)"),
		(None, "2399", "Grundstücksertrag (Umsatzsteuerschlüssel möglich, nur Einzelunternehmen)"),
		("1900", "2500", "Auszahlungen allgemein (Teilhafter), Fremdkapital"),
		(None, "2510", "Auszahlungen allgemein (Teilhafter), Fremdkapital"),
		(None, "2520", "Auszahlungen allgemein (Teilhafter), Fremdkapital"),
		("1980", "2530", "Unentgeltliche Wertabgaben (Teilhafter), Fremdkapital"),
		(None, "2540", "Unentgeltliche Wertabgaben (Teilhafter), Fremdkapital"),
		("1910", "2550", "Privatsteuern (Teilhafter), Fremdkapital"),
		(None, "2560", "Privatsteuern (Teilhafter), Fremdkapital"),
		(None, "2570", "Privatsteuern (Teilhafter), Fremdkapital"),
		("1990", "2580", "Einzahlungen (Teilhafter), Fremdkapital"),
		(None, "2590", "Einzahlungen (Teilhafter), Fremdkapital"),
		("1920", "2600", "Sonderausgaben beschränkt abzugsfähig (Teilhafter), Fremdkapital"),
		(None, "2610", "Sonderausgaben beschränkt abzugsfähig (Teilhafter), Fremdkapital"),
		(None, "2620", "Sonderausgaben beschränkt abzugsfähig (Teilhafter), Fremdkapital"),
		("1930", "2630", "Sonderausgaben unbeschränkt abzugsfähig (Teilhafter), Fremdkapital"),
		(None, "2640", "Sonderausgaben unbeschränkt abzugsfähig (Teilhafter), Fremdkapital"),
		("1940", "2650", "Zuwendungen, Spenden (Teilhafter), Fremdkapital"),
		(None, "2660", "Zuwendungen, Spenden (Teilhafter), Fremdkapital"),
		(None, "2670", "Zuwendungen, Spenden (Teilhafter), Fremdkapital"),
		("1950", "2680", "Außergewöhnliche Belastungen (Teilhafter), Fremdkapital"),
		(None, "2690", "Außergewöhnliche Belastungen (Teilhafter), Fremdkapital"),
		("1960", "2700", "Grundstücksaufwand (Teilhafter), Fremdkapital"),
		(None, "2710", "Grundstücksaufwand (Teilhafter), Fremdkapital"),
		(None, "2720", "Grundstücksaufwand (Teilhafter), Fremdkapital"),
		(None, "2730", "Grundstücksaufwand (Teilhafter), Fremdkapital"),
		(None, "2740", "Grundstücksaufwand (Teilhafter), Fremdkapital"),
		("1970", "2750", "Grundstücksertrag (Teilhafter), Fremdkapital"),
		(None, "2760", "Grundstücksertrag (Teilhafter), Fremdkapital"),
		(None, "2770", "Grundstücksertrag (Teilhafter), Fremdkapital"),
		(None, "2780", "Grundstücksertrag (Teilhafter), Fremdkapital"),
		(None, "2790", "Grundstücksertrag (Teilhafter), Fremdkapital"),
	),
	_position(
		"bs.eqLiab.equity.subscribed.corp",
		("0800", "2900", "Gezeichnetes Kapital"),
	),
	_watched(
		Reason.COOPERATIVE,
		("0810", "2901", "Geschäftsguthaben der verbleibenden Mitglieder"),
		("0811", "2902", "Geschäftsguthaben der ausscheidenden Mitglieder"),
		("0812", "2903", "Geschäftsguthaben aus gekündigten Geschäftsanteilen"),
	),
	_outside(
		Outside.NOTED,
		("0813", "2906", "Rückständige fällige Einzahlungen auf Geschäftsanteile, vermerkt"),
		("0815", "2907", "Gegenkonto Rückständige fällige Einzahlungen auf Geschäftsanteile, vermerkt"),
	),
	_position(
		"bs.eqLiab.equity.subscribed.corp",
		("0809", "2908", "Kapitalerhöhung aus Gesellschaftsmitteln"),
	),
	_position(
		"bs.eqLiab.equity.subscribed.ownSharesdeducted",
		("0819", "2909", "Erworbene eigene Anteile"),
	),
	_position(
		"bs.eqLiab.equity.subscribed.unpaidCap",
		(
			"0820-0829",
			None,
			"Ausstehende Einlagen auf das gezeichnete Kapital, nicht eingefordert (Passivausweis, vom gezeichneten Kapital offen abgesetzt; eingeforderte ausstehende Einlagen s. Konten 0830-0838)",
		),
	),
	_position(
		"bs.ass.currAss.receiv.other.unpaidCapital",
		(
			"0830-0838",
			None,
			"Ausstehende Einlagen auf das gezeichnete Kapital, eingefordert (Forderungen, nicht eingeforderte ausstehende Einlagen s. Konten 0820-0829)",
		),
	),
	_position(
		"bs.ass.currAss.receiv.other.unpaidSupplementaryCalls",
		("0839", None, "Nachschüsse (Forderungen, Gegenkonto 0845)"),
	),
	_position(
		"bs.eqLiab.equity.subscribed.unpaidCap",
		(
			None,
			"2910",
			"Ausstehende Einlagen auf das gezeichnete Kapital, nicht eingefordert (Passivausweis, vom gezeichneten Kapital offen abgesetzt; eingeforderte ausstehende Einlagen s. Konto 1298)",
		),
	),
	_position(
		"bs.eqLiab.equity.capRes",
		("0840", "2920", "Kapitalrücklage"),
		("0841", "2925", "Kapitalrücklage durch Ausgabe von Anteilen über Nennbetrag"),
		(
			"0842",
			"2926",
			"Kapitalrücklage durch Ausgabe von Schuldverschreibungen für Wandlungsrechte und Optionsrechte zum Erwerb von Anteilen",
		),
		("0843", "2927", "Kapitalrücklage durch Zuzahlungen gegen Gewährung eines Vorzugs für Anteile"),
		("0844", None, "Kapitalrücklage durch andere Zuzahlungen in das Eigenkapital"),
	),
	_position(
		"bs.eqLiab.equity.capRes",
		("0845", None, "Nachschusskapital (Gegenkonto 0839)"),
		reason=Reason.SUPPLEMENTARY_CAPITAL,
	),
	_position(
		"bs.eqLiab.equity.capRes",
		(None, "2928", "Kapitalrücklage durch Zuzahlungen in das Eigenkapital"),
	),
	_position(
		"bs.eqLiab.equity.capRes",
		(None, "2929", "Nachschusskapital (Gegenkonto 1299)"),
		reason=Reason.SUPPLEMENTARY_CAPITAL,
	),
	_position(
		"bs.eqLiab.equity.revenueRes.legal",
		("0846", "2930", "Gesetzliche Rücklage"),
	),
	_position(
		"bs.eqLiab.equity.revenueRes.sharesParentComp",
		(
			"0849",
			"2935",
			"Rücklage für Anteile an einem herrschenden oder mehrheitlich beteiligten Unternehmen",
		),
	),
	_watched(
		Reason.COOPERATIVE,
		("0852", "2937", "Andere Ergebnisrücklagen"),
	),
	_position(
		"bs.eqLiab.equity.revenueRes.statutory",
		("0851", "2950", "Satzungsmäßige Rücklagen"),
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"0989",
			"2959",
			"Gesamthänderisch gebundene Rücklagen (mit Aufteilung für Kapitalkontenentwicklung)",
		),
	),
	_position(
		"bs.eqLiab.equity.revenueRes.other",
		("0855", "2960", "Andere Gewinnrücklagen"),
		("0848", "2961", "Andere Gewinnrücklagen aus dem Erwerb eigener Anteile"),
		("0856", "2962", "Eigenkapitalanteil von Wertaufholungen"),
	),
	_position(
		"bs.eqLiab.equity.revenueRes.other",
		("0853", "2963", "Gewinnrücklagen aus den Übergangsvorschriften BilMoG"),
		(
			"0854",
			"2964",
			"Gewinnrücklagen aus den Übergangsvorschriften BilMoG (Zuschreibung Sachanlagevermögen)",
		),
		(
			"0857",
			"2965",
			"Gewinnrücklagen aus den Übergangsvorschriften BilMoG (Zuschreibung Finanzanlagevermögen)",
		),
		(
			"0858",
			"2966",
			"Gewinnrücklagen aus den Übergangsvorschriften BilMoG (Auflösung der Sonderposten mit Rücklageanteil)",
		),
		("0859", "2967", "Latente Steuern (Gewinnrücklage Haben) aus erfolgsneutralen Verrechnungen"),
		("0988", "2968", "Latente Steuern (Gewinnrücklage Soll) aus erfolgsneutralen Verrechnungen"),
		(
			"0987",
			"2969",
			"Rechnungsabgrenzungsposten (Gewinnrücklage Soll) aus erfolgsneutralen Verrechnungen",
		),
		purpose=Purpose.COMMERCIAL,
	),
	_position(
		"bs.eqLiab.equity.retainedEarnings",
		("0860", "2970", "Gewinnvortrag vor Verwendung"),
	),
	_watched(
		Reason.PARTNERSHIP,
		("0865", "2975", "Gewinnvortrag vor Verwendung (mit Aufteilung für Kapitalkontenentwicklung)"),
		("0867", "2977", "Verlustvortrag vor Verwendung (mit Aufteilung für Kapitalkontenentwicklung)"),
	),
	_position(
		"bs.eqLiab.equity.retainedEarnings",
		("0868", "2978", "Verlustvortrag vor Verwendung"),
	),
	_position(
		"bs.eqLiab.otherSpecRes.other.other",
		("0930", "2980", "Übrige andere Sonderposten"),
	),
	_position(
		"bs.eqLiab.otherSpecRes.other.EStG6b",
		("0931", "2981", "Steuerfreie Rücklagen nach § 6b EStG"),
		purpose=Purpose.TAX,
	),
	_position(
		"bs.eqLiab.otherSpecRes.other.replacement",
		("0932", "2982", "Rücklage für Ersatzbeschaffung"),
		purpose=Purpose.TAX,
	),
	_position(
		"bs.eqLiab.otherSpecRes.other.subsidies",
		("0946", "2988", "Rücklage für Zuschüsse"),
		purpose=Purpose.TAX,
	),
	_position(
		"bs.eqLiab.pretaxRes",
		(None, "2989", "Sonderposten mit Rücklageanteil nach § 52 Abs.16 EStG"),
		("0940", "2990", "Sonderposten mit Rücklageanteil, Sonderabschreibungen"),
		(None, "2993", "Sonderposten mit Rücklageanteil nach § 7g Abs. 2 EStG n. F."),
		reason=Reason.OLD_SPECIAL_ITEM,
	),
	_position(
		"bs.eqLiab.otherSpecRes.other.releaseWithdrawalEStG4g",
		("0945", "2995", "Ausgleichsposten bei Entnahmen § 4g EStG"),
		purpose=Purpose.TAX,
	),
	_position(
		"bs.eqLiab.pretaxRes",
		("0947", "2997", "Sonderposten mit Rücklageanteil nach § 7g Abs. 5 EStG"),
		reason=Reason.OLD_SPECIAL_ITEM,
	),
	_position(
		"bs.eqLiab.otherSpecRes.subsidies",
		("0948", "2998", "Sonderposten für Zuschüsse Dritter"),
	),
	_position(
		"bs.eqLiab.otherSpecRes.subsidies",
		("0949", "2999", "Sonderposten für Investitionszulagen"),
		purpose=Purpose.COMMERCIAL,
	),
	_position(
		"bs.eqLiab.accruals.pensions.other",
		("0950", "3000", "Rückstellungen für Pensionen und ähnliche Verpflichtungen"),
		reason=Reason.PENSION_KIND,
	),
	_position(
		"bs.eqLiab.accruals.pensions.shareholder",
		(
			"0952",
			"3005",
			"Rückstellungen für Pensionen und ähnliche Verpflichtungen gegenüber Gesellschaftern oder nahe stehenden Personen",
		),
	),
	_position(
		"bs.eqLiab.accruals.pensions.other",
		(
			"0951",
			"3009",
			"Rückstellungen für Pensionen und ähnliche Verpflichtungen zur Saldierung mit Vermögensgegenständen zum langfristigen Verbleib nach § 246 Abs. 2 HGB",
		),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.OFFSET_PENSIONS,
	),
	_position(
		"bs.eqLiab.accruals.pensions.direct",
		("0953", "3010", "Rückstellungen für Direktzusagen"),
	),
	_position(
		"bs.eqLiab.accruals.pensions.externalFunds",
		(
			"0954",
			"3011",
			"Rückstellungen für Zuschussverpflichtungen für Pensionskassen und Lebensversicherungen",
		),
	),
	_position(
		"bs.eqLiab.accruals.pensions.other",
		(None, "3015", "Rückstellungen für pensionsähnliche Verpflichtungen"),
		reason=Reason.PENSION_KIND,
	),
	_position(
		"bs.eqLiab.accruals.tax.misc",
		("0955", "3020", "Steuerrückstellungen"),
		reason=Reason.TAX_KIND,
	),
	_position(
		"bs.eqLiab.accruals.tax.gewst",
		(None, "3030", "Gewerbesteuerrückstellung"),
		("0956", "3035", "Gewerbesteuerrückstellung nach § 4 Abs. 5b EStG"),
	),
	_position(
		"bs.eqLiab.accruals.tax.kst",
		("0963", "3040", "Körperschaftsteuerrückstellung"),
	),
	_position(
		"bs.eqLiab.accruals.tax.defTax",
		("0962", "3050", "Steuerrückstellung aus Steuerstundung (BStBK)"),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.DEFERRAL_PROVISION,
	),
	_position(
		"bs.eqLiab.accruals.tax.defTax",
		("0969", "3060", "Rückstellung für latente Steuern"),
		purpose=Purpose.COMMERCIAL,
	),
	_position(
		"bs.eqLiab.defTax",
		("0968", "3065", "Passive latente Steuern"),
		purpose=Purpose.COMMERCIAL,
	),
	_position(
		"bs.eqLiab.accruals.other",
		("0970", "3070", "Sonstige Rückstellungen"),
		("0965", "3074", "Rückstellungen für Personalkosten"),
		(
			"0971",
			"3075",
			"Rückstellungen für unterlassene Aufwendungen für Instandhaltung, Nachholung in den ersten drei Monaten",
		),
		(
			"0964",
			"3076",
			"Rückstellungen für mit der Altersversorgung vergleichbare langfristige Verpflichtungen zum langfristigen Verbleib",
		),
	),
	_position(
		"bs.eqLiab.accruals.other",
		(
			"0967",
			"3077",
			"Rückstellungen für mit der Altersversorgung vergleichbare langfristige Verpflichtungen zur Saldierung mit Vermögensgegenständen zum langfristigen Verbleib nach § 246 Abs. 2 HGB",
		),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.OFFSET_OTHER,
	),
	_position(
		"bs.eqLiab.accruals.other",
		("0961", "3079", "Urlaubsrückstellungen"),
		("0973", "3085", "Rückstellungen für Abraum- und Abfallbeseitigung"),
		("0974", None, "Rückstellungen für Gewährleistungen (Gegenkonto 4790)"),
		(None, "3090", "Rückstellungen für Gewährleistungen (Gegenkonto 6790)"),
	),
	_position(
		"bs.eqLiab.accruals.other",
		("0976", "3092", "Rückstellungen für drohende Verluste aus schwebenden Geschäften"),
		purpose=Purpose.COMMERCIAL,
	),
	_position(
		"bs.eqLiab.accruals.other",
		("0977", "3095", "Rückstellungen für Abschluss- und Prüfungskosten"),
		("0966", "3096", "Rückstellungen zur Erfüllung der Aufbewahrungspflichten"),
	),
	_position(
		"bs.eqLiab.accruals.other",
		(None, "3098", "Aufwandsrückstellungen gemäß § 249 Abs. 2 HGB a. F."),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.EXPENSE_PROVISIONS,
	),
	_position(
		"bs.eqLiab.accruals.other",
		("0979", "3099", "Rückstellungen für Umweltschutz"),
	),
	_position(
		"bs.eqLiab.liab.securities",
		("0600", "3100", "Anleihen, nicht konvertibel"),
	),
	_position(
		"bs.eqLiab.liab.securities",
		("0601", "3101", "Anleihen, nicht konvertibel - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.eqLiab.liab.securities",
		("0605", "3105", "Anleihen, nicht konvertibel - Restlaufzeit 1 bis 5 Jahre"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.securities",
		("0610", "3110", "Anleihen, nicht konvertibel - Restlaufzeit größer 5 Jahre"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.securities",
		("0615", None, "Anleihen konvertibel"),
	),
	_position(
		"bs.eqLiab.liab.securities",
		("0616", None, "Anleihen konvertibel - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.eqLiab.liab.securities",
		("0620", None, "Anleihen konvertibel - Restlaufzeit 1 bis 5 Jahre"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.securities",
		("0625", None, "Anleihen konvertibel - Restlaufzeit größer 5 Jahre"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.securities",
		(None, "3120", "Anleihen, konvertibel"),
	),
	_position(
		"bs.eqLiab.liab.securities",
		(None, "3121", "Anleihen, konvertibel - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.eqLiab.liab.securities",
		(None, "3125", "Anleihen, konvertibel - Restlaufzeit 1 bis 5 Jahre"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.securities",
		(None, "3130", "Anleihen, konvertibel - Restlaufzeit größer 5 Jahre"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		("0630", "3150", "Verbindlichkeiten gegenüber Kreditinstituten"),
		opposite="bs.ass.currAss.cashEquiv.bank",
		reason=Reason.BANK_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		("0631", "3151", "Verbindlichkeiten gegenüber Kreditinstituten - Restlaufzeit bis 1 Jahr"),
		opposite="bs.ass.currAss.cashEquiv.bank",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BANK_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		("0640", "3160", "Verbindlichkeiten gegenüber Kreditinstituten - Restlaufzeit 1 bis 5 Jahre"),
		opposite="bs.ass.currAss.cashEquiv.bank",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BANK_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		("0650", "3170", "Verbindlichkeiten gegenüber Kreditinstituten - Restlaufzeit größer 5 Jahre"),
		opposite="bs.ass.currAss.cashEquiv.bank",
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		reason=Reason.BANK_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		("0660", "3180", "Verbindlichkeiten gegenüber Kreditinstituten aus Teilzahlungsverträgen"),
		opposite="bs.ass.currAss.cashEquiv.bank",
		reason=Reason.BANK_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		(
			"0661",
			"3181",
			"Verbindlichkeiten gegenüber Kreditinstituten aus Teilzahlungsverträgen - Restlaufzeit bis 1 Jahr",
		),
		opposite="bs.ass.currAss.cashEquiv.bank",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BANK_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		(
			"0670",
			"3190",
			"Verbindlichkeiten gegenüber Kreditinstituten aus Teilzahlungsverträgen - Restlaufzeit 1 bis 5 Jahre",
		),
		opposite="bs.ass.currAss.cashEquiv.bank",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BANK_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		(
			"0680",
			"3200",
			"Verbindlichkeiten gegenüber Kreditinstituten aus Teilzahlungsverträgen - Restlaufzeit größer 5 Jahre",
		),
		opposite="bs.ass.currAss.cashEquiv.bank",
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		reason=Reason.BANK_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		("0690", "3210", "Verbindlichkeiten gegenüber Kreditinstituten, vor Restlaufzeitdifferenzierung"),
		opposite="bs.ass.currAss.cashEquiv.bank",
		reason=Reason.BANK_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		("0699", None, "Gegenkonto 0630-0689 bei Aufteilung der Konten 0690-0698"),
		(None, "3249", "Gegenkonto 3150-3209 bei Aufteilung der Konten 3210-3248"),
		reason=Reason.SPLIT_COUNTER,
	),
	_position(
		"bs.eqLiab.liab.advPaym",
		("1710", "3250", "Erhaltene Anzahlungen auf Bestellungen (Verbindlichkeiten)"),
		("1711", "3260", "Erhaltene, versteuerte Anzahlungen 7 % USt (Verbindlichkeiten)"),
		("1712", "3261", "Erhaltene, versteuerte Anzahlungen 5 % USt (Verbindlichkeiten)"),
		("1714", "3264", "Erhaltene, versteuerte Anzahlungen 0 % USt (Verbindlichkeiten)"),
		("1717", "3270", "Erhaltene, versteuerte Anzahlungen 16 % USt (Verbindlichkeiten)"),
		(None, "3271", "Erhaltene, versteuerte Anz. 15 % USt (Verb.)"),
		("1718", "3272", "Erhaltene, versteuerte Anzahlungen 19 % USt (Verbindlichkeiten)"),
		("1715", "3279", "Erhaltene Anzahlungen - Nachsteuer"),
	),
	_position(
		"bs.eqLiab.liab.advPaym",
		("1719", "3280", "Erhaltene Anzahlungen - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.eqLiab.liab.advPaym",
		("1720", "3284", "Erhaltene Anzahlungen - Restlaufzeit 1 bis 5 Jahre"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.advPaym",
		("1721", "3285", "Erhaltene Anzahlungen - Restlaufzeit größer 5 Jahre"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.trade.genOther",
		("1600", "3300", "Verbindlichkeiten aus Lieferungen und Leistungen"),
		("1601-1603", "3301-3303", "Verbindlichkeiten aus Lieferungen und Leistungen"),
		opposite="bs.ass.currAss.receiv.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_watched(
		Reason.EUR,
		(
			"1605",
			"3305",
			"Verbindlichkeiten aus Lieferungen und Leistungen zum allgemeinen Umsatzsteuersatz (EÜR)",
		),
		(
			"1606",
			"3306",
			"Verbindlichkeiten aus Lieferungen und Leistungen zum ermäßigten Umsatzsteuersatz (EÜR)",
		),
		("1607", None, "Verbindlichkeiten aus Lieferungen und Leistungen ohne Vorsteuerabzug (EÜR)"),
		("1609", None, "Gegenkonto 1605-1607 bei Aufteilung der Verbindlichkeiten nach Steuersätzen (EÜR)"),
		(None, "3307", "Verbindlichkeiten aus Lieferungen und Leistungen ohne Vorsteuer (EÜR)"),
		(None, "3309", "Gegenkonto 3305-3307 bei Aufteilung der Verbindlichkeiten nach Steuersätzen (EÜR)"),
	),
	_position(
		"bs.eqLiab.liab.trade.genOther",
		("1610-1623", "3310-3333", "Verbindlichkeiten aus Lieferungen und Leistungen ohne Kontokorrent"),
		opposite="bs.ass.currAss.receiv.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_watched(
		Reason.EUR,
		(
			"1624",
			"3334",
			"Verbindlichkeiten aus Lieferungen und Leistungen für Investitionen für § 4 Abs. 3 EStG",
		),
	),
	_position(
		"bs.eqLiab.liab.trade.genOther",
		(
			"1625",
			"3335",
			"Verbindlichkeiten aus Lieferungen und Leistungen ohne Kontokorrent - Restlaufzeit bis 1 Jahr",
		),
		opposite="bs.ass.currAss.receiv.other.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.trade.genOther",
		(
			"1626",
			"3337",
			"Verbindlichkeiten aus Lieferungen und Leistungen ohne Kontokorrent - Restlaufzeit 1 bis 5 Jahre",
		),
		opposite="bs.ass.currAss.receiv.other.other",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.trade.genOther",
		(
			"1628",
			"3338",
			"Verbindlichkeiten aus Lieferungen und Leistungen ohne Kontokorrent - Restlaufzeit größer 5 Jahre",
		),
		opposite="bs.ass.currAss.receiv.other.other",
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.trade.shareholders",
		("1650", "3340", "Verbindlichkeiten aus Lieferungen und Leistungen gegenüber Gesellschaftern"),
		opposite="bs.ass.currAss.receiv.shareholders.gmbh",
		shareholder=True,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.trade.shareholders",
		(
			"1651",
			"3341",
			"Verbindlichkeiten aus Lieferungen und Leistungen gegenüber Gesellschaftern - Restlaufzeit bis 1 Jahr",
		),
		opposite="bs.ass.currAss.receiv.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.trade.shareholders",
		(
			"1655",
			"3345",
			"Verbindlichkeiten aus Lieferungen und Leistungen gegenüber Gesellschaftern - Restlaufzeit 1 bis 5 Jahre",
		),
		opposite="bs.ass.currAss.receiv.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.trade.shareholders",
		(
			"1658",
			"3348",
			"Verbindlichkeiten aus Lieferungen und Leistungen gegenüber Gesellschaftern - Restlaufzeit größer 5 Jahre",
		),
		opposite="bs.ass.currAss.receiv.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.trade.genOther",
		("1659", None, "Gegenkonto 1625-1658 bei Aufteilung Kreditorenkonto"),
		(None, "3349", "Gegenkonto 3335-3348, 3420-3449, 3470-3499 bei Aufteilung Kreditorenkonto"),
		reason=Reason.SPLIT_COUNTER,
	),
	_position(
		"bs.eqLiab.liab.notes",
		(None, "3350", "Verb. aus der Annahme gezogener Wechsel und aus der Ausstellung eigener Wechsel"),
	),
	_position(
		"bs.eqLiab.liab.notes",
		(
			None,
			"3351",
			"Verb. aus der Annahme gezogener Wechsel und aus der Ausstellung eigener Wechsel (b. 1 J.)",
		),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.eqLiab.liab.notes",
		(
			None,
			"3380",
			"Verb. aus der Annahme gezogener Wechsel und aus der Ausstellung eigner Wechsel (1-5 J.)",
		),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.notes",
		(
			None,
			"3390",
			"Verb. aus der Annahme gezogener Wechsel und der Ausstellung eigener Wechsel (größer 5 J.)",
		),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.assocComp.other",
		("0700", "3400", "Verbindlichkeiten gegenüber verbundenen Unternehmen"),
		opposite="bs.ass.currAss.receiv.affil",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.assocComp.other",
		("0701", "3401", "Verbindlichkeiten gegenüber verbundenen Unternehmen - Restlaufzeit bis 1 Jahr"),
		opposite="bs.ass.currAss.receiv.affil",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.assocComp.other",
		("0705", "3405", "Verbindlichkeiten gegenüber verbundenen Unternehmen - Restlaufzeit 1 bis 5 Jahre"),
		opposite="bs.ass.currAss.receiv.affil",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.assocComp.other",
		("0710", "3410", "Verbindlichkeiten gegenüber verbundenen Unternehmen - Restlaufzeit größer 5 Jahre"),
		opposite="bs.ass.currAss.receiv.affil",
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.assocComp.other",
		(
			"1630",
			"3420",
			"Verbindlichkeiten aus Lieferungen und Leistungen gegenüber verbundenen Unternehmen",
		),
		opposite="bs.ass.currAss.receiv.affil",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.assocComp.other",
		(
			"1631",
			"3421",
			"Verbindlichkeiten aus Lieferungen und Leistungen gegenüber verbundenen Unternehmen - Restlaufzeit bis 1 Jahr",
		),
		opposite="bs.ass.currAss.receiv.affil",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.assocComp.other",
		(
			"1635",
			"3425",
			"Verbindlichkeiten aus Lieferungen und Leistungen gegenüber verbundenen Unternehmen - Restlaufzeit 1 bis 5 Jahre",
		),
		opposite="bs.ass.currAss.receiv.affil",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.assocComp.other",
		(
			"1638",
			"3430",
			"Verbindlichkeiten aus Lieferungen und Leistungen gegenüber verbundenen Unternehmen - Restlaufzeit größer 5 Jahre",
		),
		opposite="bs.ass.currAss.receiv.affil",
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.particip.other",
		(
			"0715",
			"3450",
			"Verbindlichkeiten gegenüber Unternehmen, mit denen ein Beteiligungsverhältnis besteht",
		),
		opposite="bs.ass.currAss.receiv.particip",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.particip.other",
		(
			"0716",
			"3451",
			"Verbindlichkeiten gegenüber Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit bis 1 Jahr",
		),
		opposite="bs.ass.currAss.receiv.particip",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.particip.other",
		(
			"0720",
			"3455",
			"Verbindlichkeiten gegenüber Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit 1 bis 5 Jahre",
		),
		opposite="bs.ass.currAss.receiv.particip",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.particip.other",
		(
			"0725",
			"3460",
			"Verbindlichkeiten gegenüber Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit größer 5 Jahre",
		),
		opposite="bs.ass.currAss.receiv.particip",
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.particip.other",
		(
			"1640",
			"3470",
			"Verbindlichkeiten aus Lieferungen und Leistungen gegenüber Unternehmen, mit denen ein Beteiligungsverhältnis besteht",
		),
		opposite="bs.ass.currAss.receiv.particip",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.particip.other",
		(
			"1641",
			"3471",
			"Verbindlichkeiten aus Lieferungen und Leistungen gegenüber Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit bis 1 Jahr",
		),
		opposite="bs.ass.currAss.receiv.particip",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.particip.other",
		(
			"1645",
			"3475",
			"Verbindlichkeiten aus Lieferungen und Leistungen gegenüber Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit 1 bis 5 Jahre",
		),
		opposite="bs.ass.currAss.receiv.particip",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.particip.other",
		(
			"1648",
			"3480",
			"Verbindlichkeiten aus Lieferungen und Leistungen gegenüber Unternehmen, mit denen ein Beteiligungsverhältnis besteht - Restlaufzeit größer 5 Jahre",
		),
		opposite="bs.ass.currAss.receiv.particip",
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1700", "3500", "Sonstige Verbindlichkeiten"),
		opposite="bs.ass.currAss.receiv.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1701", "3501", "Sonstige Verbindlichkeiten - Restlaufzeit bis 1 Jahr"),
		opposite="bs.ass.currAss.receiv.other.other",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.trade.genOther",
		("1702", None, "Sonstige Verbindlichkeiten - Restlaufzeit 1 bis 5 Jahre"),
		reason=Reason.TEMPLATE_SRBNB,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		(None, "3504", "Sonstige Verbindlichkeiten - Restlaufzeit 1 bis 5 Jahre"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1703", "3507", "Sonstige Verbindlichkeiten - Restlaufzeit größer 5 Jahre"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_watched(
		Reason.EUR,
		("1704", "3509", "Sonstige Verbindlichkeiten nach § 11 Abs. 2 Satz 2 EStG für § 4 Abs. 3 EStG"),
	),
	_position(
		"bs.eqLiab.liab.shareholders.gmbh",
		("0730", "3510", "Verbindlichkeiten gegenüber Gesellschaftern"),
		opposite="bs.ass.currAss.receiv.shareholders.gmbh",
		shareholder=True,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.shareholders.gmbh",
		("0731", "3511", "Verbindlichkeiten gegenüber Gesellschaftern - Restlaufzeit bis 1 Jahr"),
		opposite="bs.ass.currAss.receiv.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.shareholders.gmbh",
		("0740", "3514", "Verbindlichkeiten gegenüber Gesellschaftern - Restlaufzeit 1 bis 5 Jahre"),
		shareholder=True,
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.shareholders.gmbh",
		("0750", "3517", "Verbindlichkeiten gegenüber Gesellschaftern - Restlaufzeit größer 5 Jahre"),
		shareholder=True,
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.shareholders.gmbh",
		("0755", "3519", "Verbindlichkeiten gegenüber Gesellschaftern für offene Ausschüttungen"),
		shareholder=True,
	),
	_position(
		"bs.eqLiab.liab.other.silentPartner",
		("0760", "3520", "Verbindlichkeiten gegenüber typisch stillen Gesellschaftern"),
		reason=Reason.TYPICAL_SILENT_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.other.silentPartner",
		(
			"0761",
			"3521",
			"Verbindlichkeiten gegenüber typisch stillen Gesellschaftern - Restlaufzeit bis 1 Jahr",
		),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.TYPICAL_SILENT_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.other.silentPartner",
		(
			"0764",
			"3524",
			"Verbindlichkeiten gegenüber typisch stillen Gesellschaftern - Restlaufzeit 1 bis 5 Jahre",
		),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.TYPICAL_SILENT_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.other.silentPartner",
		(
			"0767",
			"3527",
			"Verbindlichkeiten gegenüber typisch stillen Gesellschaftern - Restlaufzeit größer 5 Jahre",
		),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		reason=Reason.TYPICAL_SILENT_LIABILITY,
	),
	_watched(
		Reason.SILENT_ATYPICAL,
		("0770", "3530", "Verbindlichkeiten gegenüber atypisch stillen Gesellschaftern"),
		(
			"0771",
			"3531",
			"Verbindlichkeiten gegenüber atypisch stillen Gesellschaftern - Restlaufzeit bis 1 Jahr",
		),
		(
			"0774",
			"3534",
			"Verbindlichkeiten gegenüber atypisch stillen Gesellschaftern - Restlaufzeit 1 bis 5 Jahre",
		),
		(
			"0777",
			"3537",
			"Verbindlichkeiten gegenüber atypisch stillen Gesellschaftern - Restlaufzeit größer 5 Jahre",
		),
	),
	_position(
		"bs.eqLiab.liab.other.profitPartLoans",
		("0780", "3540", "Partiarische Darlehen"),
	),
	_position(
		"bs.eqLiab.liab.other.profitPartLoans",
		("0781", "3541", "Partiarische Darlehen - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.eqLiab.liab.other.profitPartLoans",
		("0784", "3544", "Partiarische Darlehen - Restlaufzeit 1 bis 5 Jahre"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.other.profitPartLoans",
		("0787", "3547", "Partiarische Darlehen - Restlaufzeit größer 5 Jahre"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1732", "3550", "Erhaltene Kautionen"),
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1733", "3551", "Erhaltene Kautionen - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1734", "3554", "Erhaltene Kautionen - Restlaufzeit 1 bis 5 Jahre"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1735", "3557", "Erhaltene Kautionen - Restlaufzeit größer 5 Jahre"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1705", "3560", "Darlehen"),
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1706", "3561", "Darlehen - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1707", "3564", "Darlehen - Restlaufzeit 1 bis 5 Jahre"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1708", "3567", "Darlehen - Restlaufzeit größer 5 Jahre"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("0790", "3570", "Sonstige Verbindlichkeiten, vor Restlaufzeitdifferenzierung (nur Bilanzierer)"),
		reason=Reason.BEFORE_SPLIT,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		(
			"0799",
			None,
			"Gegenkonto 0730-0789 und 1665-1678 und 1695-1698 bei Aufteilung der Konten 0790-0798",
		),
		(None, "3599", "Gegenkonto 3500-3569 und 3640-3658 bei Aufteilung der Konten 3570-3598"),
		reason=Reason.SPLIT_COUNTER,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1731", "3600", "Agenturwarenabrechnung"),
		("1730", "3610", "Kreditkartenabrechnung"),
		opposite="bs.ass.currAss.receiv.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.jointVent",
		("1691", "3611", "Verbindlichkeiten gegenüber Arbeitsgemeinschaften"),
		opposite="bs.ass.currAss.receiv.other.jointWork",
		reason=Reason.BOTH_SIDES,
	),
	_watched(
		Reason.EUR,
		("1692", "3612", "Neutralisierung aufwandswirksamer Sachverhalte für § 4 Abs. 3 EStG"),
		("1693", "3613", "Ergebnisneutrale Sachverhalte für § 4 Abs. 3 EStG"),
	),
	_position(
		"bs.eqLiab.liab.other.silentPartner",
		("1709", "3620", "Gewinnverfügungskonto stille Gesellschafter - sonstige Verbindlichkeiten"),
		opposite="bs.ass.currAss.receiv.other.other",
		reason=Reason.SILENT_PROFIT,
	),
	_outside(
		Outside.INTERIM,
		(None, "3630", "Sonstige Verrechnungskonten (Interimskonto)"),
	),
	_watched(
		Reason.SONDERBILANZ,
		("1757", "3634", "Verbindlichkeiten gegenüber Gesellschaft/Gesamthand"),
	),
	_watched(
		Reason.COOPERATIVE,
		("1758", "3635", "Sonstige Verbindlichkeiten aus genossenschaftlicher Rückvergütung"),
	),
	_position(
		"bs.eqLiab.liab.shareholders.gmbh",
		("1665", "3640", "Verbindlichkeiten gegenüber GmbH-Gesellschaftern"),
		opposite="bs.ass.currAss.receiv.shareholders.gmbh",
		shareholder=True,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.shareholders.gmbh",
		("1666", "3641", "Verbindlichkeiten gegenüber GmbH-Gesellschaftern - Restlaufzeit bis 1 Jahr"),
		opposite="bs.ass.currAss.receiv.shareholders.gmbh",
		shareholder=True,
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.shareholders.gmbh",
		("1667", "3642", "Verbindlichkeiten gegenüber GmbH-Gesellschaftern - Restlaufzeit 1 bis 5 Jahre"),
		shareholder=True,
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.shareholders.gmbh",
		("1668", "3643", "Verbindlichkeiten gegenüber GmbH-Gesellschaftern - Restlaufzeit größer 5 Jahre"),
		shareholder=True,
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_watched(
		Reason.PARTNERSHIP,
		("1670", "3645", "Verbindlichkeiten gegenüber persönlich haftenden Gesellschaftern"),
		(
			"1671",
			"3646",
			"Verbindlichkeiten gegenüber persönlich haftenden Gesellschaftern - Restlaufzeit bis 1 Jahr",
		),
		(
			"1672",
			"3647",
			"Verbindlichkeiten gegenüber persönlich haftenden Gesellschaftern - Restlaufzeit 1 bis 5 Jahre",
		),
		(
			"1673",
			"3648",
			"Verbindlichkeiten gegenüber persönlich haftenden Gesellschaftern - Restlaufzeit größer 5 Jahre",
		),
		("1675", "3650", "Verbindlichkeiten gegenüber Kommanditisten"),
		("1676", "3651", "Verbindlichkeiten gegenüber Kommanditisten - Restlaufzeit bis 1 Jahr"),
		("1677", "3652", "Verbindlichkeiten gegenüber Kommanditisten - Restlaufzeit 1 bis 5 Jahre"),
		("1678", "3653", "Verbindlichkeiten gegenüber Kommanditisten - Restlaufzeit größer 5 Jahre"),
	),
	_position(
		"bs.eqLiab.liab.other.silentPartner",
		("1695", "3655", "Verbindlichkeiten gegenüber stillen Gesellschaftern"),
		reason=Reason.TYPICAL_SILENT_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.other.silentPartner",
		("1696", "3656", "Verbindlichkeiten gegenüber stillen Gesellschaftern - Restlaufzeit bis 1 Jahr"),
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.TYPICAL_SILENT_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.other.silentPartner",
		("1697", "3657", "Verbindlichkeiten gegenüber stillen Gesellschaftern - Restlaufzeit 1 bis 5 Jahre"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.TYPICAL_SILENT_LIABILITY,
	),
	_position(
		"bs.eqLiab.liab.other.silentPartner",
		("1698", "3658", "Verbindlichkeiten gegenüber stillen Gesellschaftern - Restlaufzeit größer 5 Jahre"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		reason=Reason.TYPICAL_SILENT_LIABILITY,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("1793", "3695", "Verrechnungskonto geleistete Anzahlungen bei Buchung über Kreditorenkonto"),
		reason=Reason.CREDITOR_PREPAYMENT,
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1736", "3700", "Verbindlichkeiten aus Steuern und Abgaben"),
		opposite="bs.ass.currAss.receiv.other.otherTaxRec",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1737", "3701", "Verbindlichkeiten aus Steuern und Abgaben - Restlaufzeit bis 1 Jahr"),
		opposite="bs.ass.currAss.receiv.other.otherTaxRec",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1738", "3710", "Verbindlichkeiten aus Steuern und Abgaben - Restlaufzeit 1 bis 5 Jahre"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1739", "3715", "Verbindlichkeiten aus Steuern und Abgaben - Restlaufzeit größer 5 Jahre"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.other.employees",
		("1740", "3720", "Verbindlichkeiten aus Lohn und Gehalt"),
		opposite="bs.ass.currAss.receiv.other.employees",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1748", "3725", "Verbindlichkeiten für Einbehaltungen von Arbeitnehmern"),
		opposite="bs.ass.currAss.receiv.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1749", "3726", "Verbindlichkeiten an das Finanzamt aus abzuführendem Bauabzugsbetrag"),
		("1741", "3730", "Verbindlichkeiten aus Lohn- und Kirchensteuer"),
		opposite="bs.ass.currAss.receiv.other.otherTaxRec",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.thereoffSocSec",
		("1742", "3740", "Verbindlichkeiten im Rahmen der sozialen Sicherheit"),
		opposite="bs.ass.currAss.receiv.other.socInsur",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.thereoffSocSec",
		("1743", "3741", "Verbindlichkeiten im Rahmen der sozialen Sicherheit - Restlaufzeit bis 1 Jahr"),
		opposite="bs.ass.currAss.receiv.other.socInsur",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.thereoffSocSec",
		("1744", "3750", "Verbindlichkeiten im Rahmen der sozialen Sicherheit - Restlaufzeit 1 bis 5 Jahre"),
		opposite="bs.ass.currAss.receiv.other.socInsur",
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.thereoffSocSec",
		("1745", "3755", "Verbindlichkeiten im Rahmen der sozialen Sicherheit - Restlaufzeit größer 5 Jahre"),
		opposite="bs.ass.currAss.receiv.other.socInsur",
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		(
			"1746",
			None,
			"Verbindlichkeiten aus Einbehaltungen (KapESt und SolZ, KiSt auf Kap-ESt) für offene Ausschüttungen",
		),
		opposite="bs.ass.currAss.receiv.other.otherTaxRec",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.thereoffSocSec",
		("1759", "3759", "Voraussichtliche Beitragsschuld gegenüber den Sozialversicherungsträgern"),
		opposite="bs.ass.currAss.receiv.other.socInsur",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		(
			None,
			"3760",
			"Verbindlichkeiten aus Einbehaltungen (KapESt und SolZ, KiSt auf KapESt) für offene Ausschüttungen",
		),
		("1747", "3761", "Verbindlichkeiten für Verbrauchsteuern"),
		opposite="bs.ass.currAss.receiv.other.otherTaxRec",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.employees",
		("1750", "3770", "Verbindlichkeiten aus Vermögensbildung"),
		opposite="bs.ass.currAss.receiv.other.employees",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.employees",
		("1751", "3771", "Verbindlichkeiten aus Vermögensbildung - Restlaufzeit bis 1 Jahr"),
		opposite="bs.ass.currAss.receiv.other.employees",
		remaining_term=RemainingTerm.UP_TO_ONE_YEAR,
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.other.employees",
		("1752", "3780", "Verbindlichkeiten aus Vermögensbildung - Restlaufzeit 1 bis 5 Jahre"),
		remaining_term=RemainingTerm.ONE_TO_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.other.employees",
		("1753", "3785", "Verbindlichkeiten aus Vermögensbildung - Restlaufzeit größer 5 Jahre"),
		remaining_term=RemainingTerm.OVER_FIVE_YEARS,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("1796", "3786", "Ausgegebene Geschenkgutscheine"),
	),
	_position(
		"bs.eqLiab.liab.other.employees",
		("1755", "3790", "Lohn- und Gehaltsverrechnungskonto"),
		opposite="bs.ass.currAss.receiv.other.employees",
		reason=Reason.BOTH_SIDES,
	),
	_watched(
		Reason.EUR,
		("1756", "3791", "Lohn- und Gehaltsverrechnung nach § 11 Abs. 2 Satz 2 EStG für § 4 Abs. 3 EStG"),
		("1795", "3796", "Verbindlichkeiten im Rahmen der sozialen Sicherheit für § 4 Abs. 3 EStG"),
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		(
			"1728",
			"3798",
			"Umsatzsteuer aus im anderen EU-Land steuerpflichtigen elektronischen Dienstleistungen",
		),
		("1729", "3799", "Steuerzahlungen aus im anderen EU-Land steuerpflichtigen Leistungen"),
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1770", "3800", "Umsatzsteuer"),
		("1771", "3801", "Umsatzsteuer 7 %"),
		("1772", "3802", "Umsatzsteuer aus innergemeinschaftlichem Erwerb"),
		("1774", "3804", "Umsatzsteuer aus innergemeinschaftlichem Erwerb 19 %"),
		("1776", "3806", "Umsatzsteuer 19 %"),
		("1777", "3807", "Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen"),
		("1778", "3808", "Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 19 %"),
		("1779", "3809", "Umsatzsteuer aus innergemeinschaftlichem Erwerb ohne Vorsteuerabzug"),
		opposite="bs.ass.currAss.receiv.other.vat",
		reason=Reason.VAT,
	),
	_position(
		"bs.eqLiab.accruals.tax.other",
		("1760", "3810", "Umsatzsteuer nicht fällig"),
		("1761", "3811", "Umsatzsteuer nicht fällig 7 %"),
		("1762", "3812", "Umsatzsteuer nicht fällig aus im Inland steuerpflichtigen EU-Lieferungen"),
		("1764", "3814", "Umsatzsteuer nicht fällig aus im Inland steuerpflichtigen EU-Lieferungen 19 %"),
		("1766", "3816", "Umsatzsteuer nicht fällig 19 %"),
		opposite="bs.ass.currAss.receiv.other.vat",
		reason=Reason.VAT_NOT_DUE,
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1767", "3817", "Umsatzsteuer aus im anderen EU-Land steuerpflichtigen Lieferungen"),
		(
			"1768",
			"3818",
			"Umsatzsteuer aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen/Werklieferungen",
		),
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1794", "3819", "Umsatzsteuer aus Erwerb als letzter Abnehmer innerhalb eines Dreiecksgeschäfts"),
		("1780", "3820", "Umsatzsteuer-Vorauszahlungen"),
		("1781", "3830", "Umsatzsteuer-Vorauszahlungen 1/11"),
		opposite="bs.ass.currAss.receiv.other.vat",
		reason=Reason.VAT,
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1798", "3831", "Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen, nur OSS"),
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1782", "3832", "Nachsteuer, UStVA Kz. 65"),
		(
			"1784",
			"3834",
			"Umsatzsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen von Lieferanten ohne Umsatzsteuer-Identifikationsnummer",
		),
		("1785", "3835", "Umsatzsteuer nach § 13b UStG"),
		("1787", "3837", "Umsatzsteuer nach § 13b UStG 19 %"),
		("1769", "3839", "Umsatzsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager"),
		("1789", "3840", "Umsatzsteuer laufendes Jahr"),
		("1790", "3841", "Umsatzsteuerverbindlichkeiten Vorjahr"),
		("1791", "3845", "Umsatzsteuerverbindlichkeiten frühere Jahre"),
		opposite="bs.ass.currAss.receiv.other.vat",
		reason=Reason.VAT,
	),
	_outside(
		Outside.INTERIM,
		("1792", None, "Sonstige Verrechnungskonten (Interimskonten)"),
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		(None, "3850", "Einfuhrumsatzsteuer aufgeschoben bis"),
		("1783", "3851", "In Rechnung unrichtig oder unberechtigt ausgewiesene Steuerbeträge, UStVA Kz. 69"),
		(None, "3852", "In Rechnung unrichtig oder unberechtigtausgewiesene Steuerbeträge, UStVA Kz. 69"),
		opposite="bs.ass.currAss.receiv.other.vat",
		reason=Reason.VAT,
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1754", "3854", "Steuerzahlungen an andere Länder"),
		("1797", "3860", "Verbindlichkeiten aus Umsatzsteuer-Vorauszahlungen"),
	),
	_position(
		"bs.eqLiab.liab.other.theroffTax",
		("1725", "3865", "Umsatzsteuer in Folgeperiode fällig (§§ 13 Abs. 1 Nr. 6 und 13b Abs. 2 UStG)"),
		opposite="bs.ass.currAss.receiv.other.vat",
		reason=Reason.VAT,
	),
	_position(
		"bs.eqLiab.defIncome",
		("0990", "3900", "Passive Rechnungsabgrenzung"),
	),
	_outside(
		Outside.BWA,
		("0992", None, "Abgrenzungen unterjährig pauschal gebuchter Abschreibungen für BWA"),
		(None, "3950", "Abgrenzung unterjährig pauschal gebuchter Abschreibungen für BWA"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.unknownVAT",
		("8000-8099", "4000-4099", "Umsatzerlöse (Zur freien Verfügung)"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_8.other",
		("8100-8104", "4100-4104", "Steuerfreie Umsätze § 4 Nr. 8 ff. UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_8.UStG4_12",
		("8105", "4105", "Steuerfreie Umsätze nach § 4 Nr. 12 UStG (Vermietung und Verpachtung)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptOther",
		("8110", "4110", "Sonstige steuerfreie Umsätze Inland"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_1a",
		("8120", "4120", "Steuerfreie Umsätze nach § 4 Nr. 1a UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_1b",
		("8125", "4125", "Steuerfreie innergemeinschaftliche Lieferungen nach § 4 Nr. 1b UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.triangularTransactionUStG25b_2_4",
		(
			"8130",
			"4130",
			"Lieferungen des ersten Abnehmers bei innergemeinschaftlichen Dreiecksgeschäften § 25b Abs. 2 UStG",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.UStG25_25a",
		("8189", "4131", "Umsatzerlöse nach § 25 UStG ohne USt"),
		("8197", "4132", "Umsatzerlöse nach § 25a UStG ohne USt"),
		("8198", "4133", "Umsatzerlöse nach § 25 UStG 19 % USt"),
		("8199", "4134", "Umsatzerlöse nach § 25a UStG 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_1b",
		(
			"8135",
			"4135",
			"Steuerfreie innergemeinschaftliche Lieferungen von Neufahrzeugen an Abnehmer ohne Umsatzsteuer-Identifikationsnummer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptOther",
		("8140", None, "Steuerfreie Umsätze Offshore usw."),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.UStG25_25a",
		("8191", "4136", "Umsatzerlöse nach §§ 25 und 25a UStG 19 % USt"),
		("8193", "4138", "Umsatzerlöse nach §§ 25 und 25a UStG ohne USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptOther",
		("8194", "4139", "Umsatzerlöse aus Reiseleistungen § 25 Abs. 2 UStG, steuerfrei"),
		reason=Reason.TRAVEL_EXEMPT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptOther",
		(None, "4140", "Steuerfreie Umsätze Offshore etc."),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_2til7",
		("8150", "4150", "Sonstige steuerfreie Umsätze (z. B. § 4 Nr. 2 bis 7 UStG)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_8.other",
		("8160", "4160", "Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend, § 4 UStG"),
		("8165", "4165", "Steuerfreie Umsätze ohne Vorsteuerabzug zum Gesamtumsatz gehörend"),
		reason=Reason.EXEMPT_NO_DEDUCTION,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.UStG24",
		("8190", "4180", "Erlöse, die mit den Durchschnittssätzen des § 24 UStG versteuert werden"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG19_1",
		("8192", "4184", "Steuerfreie Erlöse Kleinunternehmer nach § 19 Abs. 1 UStG"),
		(None, "4185", "Erlöse aus Kleinunternehmer i. S. d. § 19 Abs. 1 UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.generalRateVAT",
		(None, "4186", "Erlöse aus Geldspielautomaten 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.unknownVAT",
		("8200", "4200", "Erlöse"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.0VATrateUStG12_3",
		("8290", "4290", "Erlöse 0 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.reducedRateVAT",
		("8300-8309", "4300-4309", "Erlöse 7 % USt"),
		("8310-8314", "4310-4314", "Erlöse aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.generalRateVAT",
		("8315-8319", "4315-4319", "Erlöse aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.untaxable",
		(
			"8320-8329",
			"4320-4329",
			"Erlöse aus im anderen EU-Land steuerpflichtigen Lieferungen, im Inland nicht steuerbar",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.otherRateVAT",
		(None, "4330", "Erlöse aus im Inland steuerpfl. EU-Lieferungen 16 % USt"),
		reason=Reason.RATE_16,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.untaxable",
		("8331", "4331", "Erlöse aus im anderen EU-Land steuerpflichtigen elektronischen Dienstleistungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.reducedRateVAT",
		("8334", "4334", "Erlöse 7 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.UStG13b",
		(
			"8335",
			"4335",
			"Erlöse aus Lieferungen von Mobilfunkgeräten, Tablet-Computern, Spielekonsolen und integrierten Schaltkreisen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.untaxable",
		(
			"8336",
			"4336",
			"Erlöse aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen, für die der Leistungsempfänger die Umsatzsteuer schuldet",
		),
		reason=Reason.REVERSE_CHARGE_ABROAD,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.UStG13b",
		(
			"8337",
			"4337",
			"Erlöse aus Leistungen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.untaxable",
		(
			"8338",
			"4338",
			"Erlöse aus im Drittland steuerbaren Leistungen, im Inland nicht steuerbare Umsätze",
		),
		(
			"8339",
			"4339",
			"Erlöse aus im anderen EU-Land steuerbaren Leistungen, im Inland nicht steuerbare Umsätze",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.otherRateVAT",
		("8340-8349", "4340-4349", "Erlöse 16 % USt"),
		reason=Reason.RATE_16,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.generalRateVAT",
		("8400-8409", "4400-4409", "Erlöse 19 % USt"),
		("8410-8419", "4410-4419", "Erlöse 19 % USt"),
		("8449", "4449", "Erlöse aus im Inland steuerpflichtigen elektronischen Dienstleistungen 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.unknownVAT",
		("8499", "4499", "Nebenerlöse (Bezug zu Materialaufwand)"),
		reason=Reason.VAT_SPLIT,
	),
	_watched(
		Reason.SONDERBILANZ,
		("8500", "4500", "Sonderbetriebseinnahmen, Tätigkeitsvergütung"),
		("8501", "4501", "Sonderbetriebseinnahmen, Miet-/Pachteinnahmen"),
		("8502", "4502", "Sonderbetriebseinnahmen, Zinseinnahmen"),
		("8503", "4503", "Sonderbetriebseinnahmen, Haftungsvergütung"),
		("8504", "4504", "Sonderbetriebseinnahmen, Pensionszahlungen"),
		("8505", "4505", "Sonderbetriebseinnahmen, sonstige Sonderbetriebseinnahmen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.unknownVAT",
		("8520", "4510", "Erlöse Abfallverwertung"),
		("8540", "4520", "Erlöse Leergut"),
		("8510", "4560", "Provisionsumsätze"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_8.other",
		("8514", "4564", "Provisionsumsätze, steuerfrei § 4 Nr. 8 ff. UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_2til7",
		("8515", "4565", "Provisionsumsätze, steuerfrei § 4 Nr. 5 UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.reducedRateVAT",
		(None, "4566", "Provisionsumsätze 7% USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.generalRateVAT",
		("8519", "4569", "Provisionsumsätze 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.unknownVAT",
		("8570", "4570", "Sonstige Erträge aus Provisionen, Lizenzen und Patenten"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_8.other",
		(
			None,
			"4574",
			"Sonstige Erträge aus Provisionen, Lizenzen und Patenten, steuerfrei § 4 Nr. 8ff UStG",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_2til7",
		(None, "4575", "Sonstige Erträge aus Provisionen, Lizenzen und Patenten, steuerfrei § 4 Nr. 5 UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.reducedRateVAT",
		(None, "4576", "Sonstige Erträge aus Provisionen, Lizenzen und Patenten 7% USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.generalRateVAT",
		(None, "4579", "Sonstige Erträge aus Provisionen, Lizenzen und Patenten 19% USt"),
	),
	_watched(
		Reason.EUR,
		("8580", "4580", "Statistisches Konto Erlöse zum allgemeinen Umsatzsteuersatz (EÜR)"),
		("8581", "4581", "Statistisches Konto Erlöse zum ermäßigten Umsatzsteuersatz (EÜR)"),
		("8582", "4582", "Statistisches Konto Erlöse steuerfrei und nicht steuerbar (EÜR)"),
		("8589", None, "Gegenkonto 8580-8582 bei Aufteilung der Erlöse nach Steuersätzen (EÜR)"),
		(None, "4589", "Gegenkonto 4580-4582 bei Aufteilung der Erlöse nach Steuersätzen (EÜR)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.ownConsumption.otherWithdrawals",
		("8900", "4600", "Unentgeltliche Wertabgaben"),
		("8905", "4605", "Entnahme von Gegenständen ohne USt"),
		(
			"8915-8916",
			"4610-4615",
			"Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt",
		),
		(
			"8917",
			"4616",
			"Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 7 % USt",
		),
		(
			"8919",
			"4619",
			"Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) ohne USt",
		),
		(
			"8910-8913",
			"4620-4626",
			"Entnahme durch den Unternehmer für Zwecke außerhalb des Unternehmens (Waren) 19 % USt",
		),
		("8930", "4630-4635", "Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt"),
		("8931", "4636", "Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 7 % USt"),
		("8906", "4637", "Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt"),
		(
			"8918",
			"4638",
			"Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt (Telefon-Nutzung)",
		),
		(
			"8924",
			"4639",
			"Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens ohne USt (Fahrzeug-Nutzung)",
		),
		("8920", "4640-4644", "Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt"),
		(
			"8921",
			"4645",
			"Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Fahrzeug-Nutzung)",
		),
		(
			"8922",
			"4646",
			"Verwendung von Gegenständen für Zwecke außerhalb des Unternehmens 19 % USt (Telefon-Nutzung)",
		),
		("8932", "4650-4655", "Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt"),
		("8933", "4656", "Unentgeltliche Erbringung einer sonstigen Leistung 7 % USt"),
		("8929", "4659", "Unentgeltliche Erbringung einer sonstigen Leistung ohne USt"),
		("8925-8927", "4660-4666", "Unentgeltliche Erbringung einer sonstigen Leistung 19 % USt"),
		("8945-8946", "4670-4675", "Unentgeltliche Zuwendung von Waren 7 % USt"),
		("8947", "4676", "Unentgeltliche Zuwendung von Waren 7 % USt"),
		("8949", "4679", "Unentgeltliche Zuwendung von Waren ohne USt"),
		("8940-8943", "4680-4684", "Unentgeltliche Zuwendung von Waren 19 % USt"),
		("8935-8937", "4686-4687", "Unentgeltliche Zuwendung von Gegenständen 19 % USt"),
		("8939", "4689", "Unentgeltliche Zuwendung von Gegenständen ohne USt"),
		reason=Reason.WITHDRAWALS,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.untaxable",
		("8950", "4690", "Nicht steuerbare Umsätze (Innenumsätze)"),
		reason=Reason.INTERNAL_SALES,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.UStG24",
		("8955", "4695", "Umsatzsteuervergütungen nach § 24 UStG"),
		reason=Reason.FLAT_RATE_REFUND,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.taxFromGrossSales",
		("8959", "4699", "Direkt mit dem Umsatz verbundene Steuern"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.inventoryChange",
		("8960", None, "Bestandsveränderungen unfertige Erzeugnisse"),
		("8970", None, "Bestandsveränderungen unfertige Leistungen"),
		("8975", None, "Bestandsveränderungen in Ausführung befindliche Bauaufträge"),
		("8977", None, "Bestandsveränderungen in Arbeit befindliche Aufträge"),
		("8980", None, "Bestandsveränderungen fertige Erzeugnisse"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.unknownVAT",
		("8700", "4700", "Erlösschmälerungen"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.taxExemptUStG4_8",
		("8701", "4701", "Erlösschmälerungen für steuerfreie Umsätze nach § 4 Nr. 8 ff. UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.taxExemptUStG4_2til7",
		("8702", "4702", "Erlösschmälerungen für steuerfreie Umsätze nach § 4 Nr. 2 bis 7 UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.taxExemptUStG4_8",
		("8703", "4703", "Erlösschmälerungen für sonstige steuerfreie Umsätze ohne Vorsteuerabzug"),
		reason=Reason.EXEMPT_NO_DEDUCTION,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.taxExemptOther",
		("8704", "4704", "Erlösschmälerungen für sonstige steuerfreie Umsätze mit Vorsteuerabzug"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.taxExemptUStG4_1a",
		("8705", "4705", "Erlösschmälerungen aus steuerfreien Umsätzen § 4 Nr. 1a UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.UStGs25_2_4",
		(
			"8706",
			"4706",
			"Erlösschmälerungen für steuerfreie innergemeinschaftliche Dreiecksgeschäfte nach § 25b Abs. 2 und 4 UStG",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.taxExemptUSt19_1",
		("8707", "4707", "Erlösschmälerungen für steuerfreie Umsätze nach § 19 Abs. 1 UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.UStGss25and25a",
		("8708", "4708", "Erlösschmälerungen für Umsätze nach § 25 UStG 19 % USt"),
		("8709", "4709", "Erlösschmälerungen für Umsätze nach § 25a UStG 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.reducedRateVAT",
		("8710-8711", "4710-4711", "Erlösschmälerungen 7 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.0VATrateUStG12_3",
		("8719", "4719", "Erlösschmälerungen 0 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.generalRateVAT",
		("8720-8721", "4720-4721", "Erlösschmälerungen 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.otherRateVAT",
		(None, "4723", "Erlösschmälerungen 16 % USt"),
		reason=Reason.RATE_16_REDUCTION,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.taxExemptUStG4_1b",
		("8724", "4724", "Erlösschmälerungen aus steuerfreien innergemeinschaftlichen Lieferungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.reducedRateVAT",
		("8725", "4725", "Erlösschmälerungen aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.generalRateVAT",
		("8726", "4726", "Erlösschmälerungen aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.untaxable",
		("8727", "4727", "Erlösschmälerungen aus im anderen EU-Land steuerpflichtigen Lieferungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.otherRateVAT",
		(None, "4729", "Erlösschmälerungen aus im Inland steuerpfl. EU-Lieferungen 16 % USt"),
		reason=Reason.RATE_16_REDUCTION,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.unknownVAT",
		("8730", "4730", "Gewährte Skonti"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.reducedRateVAT",
		("8731", "4731", "Gewährte Skonti 7 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.0VATrateUStG12_3",
		("8734", "4734", "Gewährte Skonti 0 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.generalRateVAT",
		("8736", "4736", "Gewährte Skonti 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.untaxed",
		(
			"8738",
			"4738",
			"Gewährte Skonti aus Lieferungen von Mobilfunkgeräten etc., für die der Leistungsempfänger die Umsatzsteuer nach § 13b Abs. 2 Nr. 10 UStG schuldet",
		),
		(
			"8741",
			"4741",
			"Gewährte Skonti aus Leistungen, für die der Leistungsempfänger die Umsatzsteuer nach § 13b UStG schuldet",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.untaxable",
		(
			"8742",
			"4742",
			"Gewährte Skonti aus Erlösen aus im anderen EU-Land steuerpflichtigen sonstigen Leistungen, für die der Leistungsempfänger die Umsatzsteuer schuldet",
		),
		reason=Reason.REVERSE_CHARGE_ABROAD,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.taxExemptUStG4_1b",
		(
			"8743",
			"4743",
			"Gewährte Skonti aus steuerfreien innergemeinschaftlichen Lieferungen § 4 Nr. 1b UStG",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.unknownVAT",
		("8745", "4745", "Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.reducedRateVAT",
		("8746", "4746", "Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.generalRateVAT",
		("8748", "4748", "Gewährte Skonti aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.reducedRateVAT",
		("8750-8751", "4750-4751", "Gewährte Boni 7 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.generalRateVAT",
		("8760-8761", "4760-4761", "Gewährte Boni 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.unknownVAT",
		("8769", "4769", "Gewährte Boni"),
		("8770", "4770", "Gewährte Rabatte"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.reducedRateVAT",
		("8780-8781", "4780-4781", "Gewährte Rabatte 7 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.reductionsFromGrossSales.generalRateVAT",
		("8790-8791", "4790-4791", "Gewährte Rabatte 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.inventoryChange",
		(None, "4800", "Bestandsveränderungen - fertige Erzeugnisse"),
		(None, "4810", "Bestandsveränderungen - unfertige Erzeugnisse"),
		(None, "4815", "Bestandsveränderungen - unfertige Leistungen"),
		(None, "4816", "Bestandsveränderungen in Ausführung befindlicher Bauaufträge"),
		(None, "4818", "Bestandsveränderungen in Arbeit befindlicher Aufträge"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.ownWork",
		("8990", "4820", "Andere aktivierte Eigenleistungen"),
		(
			"8994",
			"4824",
			"Aktivierte Eigenleistungen (den Herstellungskosten zurechenbare Fremdkapitalzinsen)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.ownWork",
		(
			"8995",
			"4825",
			"Aktivierte Eigenleistungen zur Erstellung von selbst geschaffenen immateriellen Vermögensgegenständen",
		),
		purpose=Purpose.COMMERCIAL,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.miscellaneous",
		("8603", "4830", "Sonstige betriebliche Erträge"),
		("8606", "4832", "Sonstige betriebliche Erträge von verbundenen Unternehmen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.unknownVAT",
		("8607", "4833", "Andere Nebenerlöse"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.miscellaneous",
		("8649", "4834", "Sonstige Erträge betrieblich und regelmäßig 16 % USt"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.misc",
		("8650", None, "Erlöse Zinsen und Diskontspesen"),
		reason=Reason.INTEREST_MIXED,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.affiliated",
		("8660", None, "Erlöse Zinsen und Diskontspesen aus verbundenen Unternehmen"),
		reason=Reason.AFFILIATED_INTEREST,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.miscellaneous",
		("8605", "4835", "Sonstige Erträge betrieblich und regelmäßig"),
		("8640-8644", "4836", "Sonstige Erträge betrieblich und regelmäßig 19 % USt"),
		(None, "4837", "Sonstige Erträge betriebsfremd und regelmäßig"),
		("8604", "4838", "Erstattete Vorsteuer anderer Länder"),
		("2709", "4839", "Sonstige Erträge unregelmäßig"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.currGains",
		("2660", "4840", "Erträge aus der Währungsumrechnung"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.miscellaneous",
		("8609", "4841", "Sonstige Erträge betrieblich und regelmäßig, steuerfrei § 4 Nr. 8 ff. UStG"),
		("8625-8629", "4842", "Sonstige betriebliche Erträge, steuerfrei z. B. § 4 Nr. 2 bis 7 UStG"),
		("8630-8634", None, "Sonstige Erträge betrieblich und regelmäßig 7 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.miscellaneous",
		("2666", "4843", "Erträge aus Bewertung Finanzmittelfonds"),
		reason=Reason.CASH_FUND_VALUATION,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposFixAss.sale.tan",
		(
			"8827",
			"4844",
			"Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchgewinn)",
		),
		("8820-8825", "4845", "Erlöse aus Verkäufen Sachanlagevermögen 19 % USt (bei Buchgewinn)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.currGains",
		("2661", "4847", "Erträge aus der Währungsumrechnung (nicht § 256a HGB)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposFixAss.sale.tan",
		(
			"8828",
			"4848",
			"Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1b UStG (bei Buchgewinn)",
		),
		("8829", "4849", "Erlöse aus Verkäufen Sachanlagevermögen (bei Buchgewinn)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposFixAss.sale.intan",
		("8837", "4850", "Erlöse aus Verkäufen immaterieller Vermögensgegenstände (bei Buchgewinn)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposFixAss.sale.fin",
		("8838", "4851", "Erlöse aus Verkäufen Finanzanlagen (bei Buchgewinn)"),
		(
			"8839",
			"4852",
			"Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG (bei Buchgewinn)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposFixAss.bookValue.tan",
		("2315", "4855", "Anlagenabgänge Sachanlagen (Restbuchwert bei Buchgewinn)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposFixAss.bookValue.intan",
		("2316", "4856", "Anlagenabgänge immaterielle Vermögensgegenstände (Restbuchwert bei Buchgewinn)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposFixAss.bookValue.fin",
		("2317", "4857", "Anlagenabgänge Finanzanlagen (Restbuchwert bei Buchgewinn)"),
		(
			"2318",
			"4858",
			"Anlagenabgänge Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG (Restbuchwert bei Buchgewinn)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.disposFixAss.misc",
		("2320", None, "Verluste aus dem Abgang von Gegenständen des Anlagevermögens"),
		reason=Reason.DISPOSAL_KIND,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.unknownVAT",
		("2750", "4860", "Grundstückserträge"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.taxExemptUStG4_8.UStG4_12",
		("2751", "4861", "Erlöse aus Vermietung und Verpachtung, umsatzsteuerfrei § 4 Nr. 12 UStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.generalRateVAT",
		("2752", "4862", "Erlöse aus Vermietung und Verpachtung 19 % USt"),
	),
	_watched(
		Reason.EUR,
		(
			"8850",
			"4865",
			"Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens 19 % USt für § 4 Abs. 3 Satz 4 EStG",
		),
		(
			"8851",
			"4866",
			"Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG",
		),
		(
			"8852",
			None,
			"Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG und § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG",
		),
		(
			"8853",
			None,
			"Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens nach § 4 Abs 3 Satz 4 EStG",
		),
		(
			None,
			"4867",
			"Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens, umsatzsteuerfrei § 4 Nr. 8 ff. UStG i. V. m. § 4 Abs. 3 Satz 4 EStG, § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG",
		),
		(
			None,
			"4869",
			"Erlöse aus Verkäufen von Wirtschaftsgütern des Umlaufvermögens nach § 4 Abs. 3 Satz 4 EStG",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposFixAss.nonAllocable",
		(None, "4900", "Erträge aus Abgang von Gegenständen des Anlagevermögens"),
		reason=Reason.DISPOSAL_KIND,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposFixAss.nonAllocable",
		(
			None,
			"4901",
			"Erträge aus der Veräußerung von Anteilen an Kap.Ges. (Finanzanlageverm., inländ. Kap.Ges.)",
		),
		reason=Reason.NET_DISPOSAL,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposCurrAss",
		(None, "4904", "Abgänge Wertpapiere des Umlaufvermögens § 8b Abs. 2 KStG (Buchwert bei Buchgewinn"),
		(None, "4905", "Erträge aus dem Abgang von Gegenständen des Umlaufvermögens außer Vorräte"),
		(
			"2726",
			"4906",
			"Erträge aus dem Abgang von Gegenständen des Umlaufvermögens (außer Vorräte) § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.revalFixAss",
		("2710", "4910", "Erträge aus Zuschreibungen des Sachanlagevermögens"),
		("2711", "4911", "Erträge aus Zuschreibungen des immateriellen Anlagevermögens"),
		("2712", "4912", "Erträge aus Zuschreibungen des Finanzanlagevermögens"),
		(
			"2713",
			"4913",
			"Erträge aus Zuschreibungen des Finanzanlagevermögens § 3 Nr. 40 EStG bzw. § 8b Abs. 3 S. 9 KStG",
		),
		("2714", "4914", "Erträge aus Zuschreibungen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.revalCurrAss",
		("2715", "4915", "Erträge aus Zuschreibungen des Umlaufvermögens (außer Vorräte)"),
		(
			"2716",
			"4916",
			"Erträge aus Zuschreibungen des Umlaufvermögens § 3 Nr. 40 EStG bzw. § 8b Abs. 3 S. 9 KStG",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposCurrAss",
		("2724", None, "Abgänge Wertpapiere des Umlaufvermögens § 8b Abs. 2 KStG (Buchwert bei Buchgewinn)"),
		("2725", None, "Erträge aus dem Abgang von Gegenständen des Umlaufvermögens (außer Vorräte)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releaseLossProv.globalValuation",
		("2730", "4920", "Erträge aus der Herabsetzung der Pauschalwertberichtigung auf Forderungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releaseLossProv.specificValuation",
		("2731", "4923", "Erträge aus der Herabsetzung der Einzelwertberichtigung auf Forderungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.recoveryWriteoffs",
		("2732", "4925", "Erträge aus abgeschriebenen Forderungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releasePreTaxRes.EStG6b_3",
		("2727", "4927", "Erträge aus der Auflösung einer steuerlichen Rücklage nach § 6b Abs. 3 EStG"),
		purpose=Purpose.TAX,
		reason=Reason.TAX_RESERVE_RELEASE,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releasePreTaxRes.other",
		("2728", "4928", "Erträge aus der Auflösung einer steuerlichen Rücklage nach § 6b Abs. 10 EStG"),
		purpose=Purpose.TAX,
		reason=Reason.TAX_RESERVE_RELEASE,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releasePreTaxRes.substEStR6_6",
		("2729", "4929", "Erträge aus der Auflösung der Rücklage für Ersatzbeschaffung, R 6.6 EStR"),
		purpose=Purpose.TAX,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releaseProv",
		("2735", "4930", "Erträge aus der Auflösung von Rückstellungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releasLiab",
		("2736", "4932", "Erträge aus der Herabsetzung von Verbindlichkeiten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releasePreTaxRes.other",
		(None, "4934", "Erträge aus der Auflösung einer steuerlichen Rücklage (Existenzgründerrücklage)"),
		("2740", "4935", "Erträge aus der Auflösung sonstiger steuerlicher Rücklagen"),
		(None, "4936", "Erträge aus der Auflösung von steuerlichen Rücklagen (Ansparabschreibungen)"),
		purpose=Purpose.TAX,
		reason=Reason.TAX_RESERVE_RELEASE,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releasePreTaxRes.other",
		("2741", "4937", "Erträge aus der Auflösung steuerrechtlicher Sonderabschreibungen"),
		reason=Reason.SPECIAL_DEPRECIATION_RELEASE,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releasePreTaxRes.EStG4g",
		("2737", "4938", "Erträge aus der Auflösung einer steuerlichen Rücklage nach § 4g EStG"),
		purpose=Purpose.TAX,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releasePreTaxRes.other",
		(None, "4939", "Erträge aus der Auflösung von steuerlichen Rücklagen nach § 52 Abs. 16 EStG"),
		purpose=Purpose.TAX,
		reason=Reason.TAX_RESERVE_RELEASE,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.ownConsumption.nonCashBenefitsOther",
		("8590", "4940", "Verrechnete sonstige Sachbezüge (keine Waren)"),
		("8591", "4941", "Sachbezüge 7 % USt (Waren)"),
		("8595", "4945", "Sachbezüge 19 % USt (Waren)"),
		("8610", "4946", "Verrechnete sonstige Sachbezüge"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.ownConsumption.nonCashBenefitsCompCar",
		("8611", "4947", "Verrechnete sonstige Sachbezüge aus Fahrzeug-Gestellung 19 % USt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.ownConsumption.nonCashBenefitsOther",
		("8613", "4948", "Verrechnete sonstige Sachbezüge 19 % USt"),
		("8614", "4949", "Verrechnete sonstige Sachbezüge ohne Umsatzsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.miscellaneous",
		("2520", "4960", "Periodenfremde Erträge"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.insuranceRefunds",
		("2742", "4970", "Versicherungsentschädigungen und Schadenersatzleistungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.miscellaneous",
		("2749", "4972", "Erstattungen Aufwendungsausgleichsgesetz"),
		reason=Reason.AAG_REFUND,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.subsidies",
		("2743", "4975", "Investitionszuschüsse (steuerpflichtig)"),
		("2744", "4980", "Investitionszulagen (steuerfrei)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.releasePreTaxRes.other",
		("2746", "4981", "Steuerfreie Erträge aus der Auflösung von steuerlichen Rücklagen"),
		purpose=Purpose.TAX,
		reason=Reason.TAX_RESERVE_RELEASE,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.miscellaneous",
		("2747", "4982", "Sonstige steuerfreie Betriebseinnahmen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.acqudFreeOfCharge",
		("2760", "4987", "Erträge aus der Aktivierung unentgeltlich erworbener Vermögensgegenstände"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.miscellaneous",
		("2762", "4989", "Kostenerstattungen, Rückvergütungen und Gutschriften für frühere Jahre"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.unknownVAT",
		("2764", None, "Erträge aus Verwaltungskostenumlage"),
		(None, "4992", "Erträge aus Verwaltungskostenumlagen"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.misc",
		(None, "5000-5099", "Aufwendungen für Roh-, Hilfs- und Betriebsstoffe und für bezogene Waren"),
		reason=Reason.MATERIAL_MIXED,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.unknownVAT",
		("3000", "5100", "Einkauf Roh-, Hilfs- und Betriebsstoffe"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.reducedRateVAT",
		("3010-3019", "5110-5119", "Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.noDeductVAT",
		("3029", "5129", "Einkauf Roh-, Hilfs- und Betriebsstoffe ohne Vorsteuerabzug"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.generalRateVAT",
		("3030-3039", "5130-5139", "Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.intraEU",
		(
			"3060",
			"5160",
			"Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer",
		),
		(
			"3062-3063",
			"5162-5163",
			"Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
		(
			"3066",
			"5166",
			"Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb ohne Vorsteuer und 7 % Umsatzsteuer",
		),
		(
			"3067",
			"5167",
			"Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb ohne Vorsteuer und 19 % Umsatzsteuer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.unknownVAT",
		("3070", "5170", "Einkauf Roh-, Hilfs- und Betriebsstoffe 5,5 % Vorsteuer"),
		("3071", "5171", "Einkauf Roh-, Hilfs- und Betriebsstoffe 7,8 % Vorsteuer"),
		reason=Reason.FLAT_RATE_INPUT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.reducedRateVAT",
		(
			"3075",
			"5175",
			"Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.generalRateVAT",
		(
			"3076",
			"5176",
			"Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.generalRateVAT",
		(
			"3089",
			"5189",
			"Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
		reason=Reason.TRIANGULAR_LAST,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.unknownVAT",
		("3090", "5190", "Energiestoffe (Fertigung)"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.reducedRateVAT",
		("3091", None, "Energiestoffe (Fertigung) 7 % VSt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.generalRateVAT",
		("3092", None, "Energiestoffe (Fertigung) 19 % VSt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.reducedRateVAT",
		(None, "5191", "Energiestoffe (Fertigung) 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.generalRateVAT",
		(None, "5192", "Energiestoffe (Fertigung) 19 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.unknownVAT",
		("3200", "5200", "Wareneingang"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.reducedRateVAT",
		("3300-3309", "5300-5309", "Wareneingang 7 % Vorsteuer"),
		("3347", "5347", "Wareneingang 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.withoutVAT",
		("3349", "5349", "Wareneingang ohne Vorsteuerabzug"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.generalRateVAT",
		("3400-3409", "5400-5409", "Wareneingang 19 % Vorsteuer"),
		("3418", "5418", "Wareneingang 19 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.intraEU",
		("3420-3424", "5420-5424", "Innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer"),
		("3425-3429", "5425-5429", "Innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer"),
		("3430", "5430", "Innergemeinschaftlicher Erwerb ohne Vorsteuer und 7 % Umsatzsteuer"),
		("3435", "5435", "Innergemeinschaftlicher Erwerb ohne Vorsteuer und 19 % Umsatzsteuer"),
		(
			"3440",
			"5440",
			"Innergemeinschaftlicher Erwerb von Neufahrzeugen von Lieferanten ohne Umsatzsteuer-Identifikationsnummer 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.unknownVAT",
		("3505-3509", "5505-5509", "Wareneingang 5,5 % Vorsteuer"),
		("3540-3549", "5540-5549", "Wareneingang zum Durchschnittssatz nach § 24 UStG 7,8 % Vorsteuer"),
		reason=Reason.FLAT_RATE_INPUT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.intraEU",
		("3550", "5550", "Steuerfreier innergemeinschaftlicher Erwerb"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.withoutVAT",
		("3551", "5551", "Wareneingang im Drittland steuerbar"),
		reason=Reason.TAXABLE_ABROAD,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.intraEU",
		("3552", "5552", "Erwerb 1. Abnehmer innerhalb eines Dreiecksgeschäftes"),
		reason=Reason.TRIANGULAR_FIRST,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.generalRateVAT",
		(
			"3553",
			"5553",
			"Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
		reason=Reason.TRIANGULAR_LAST,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.withoutVAT",
		("3558", "5558", "Wareneingang im anderen EU-Land steuerbar"),
		("3559", "5559", "Steuerfreie Einfuhren"),
		reason=Reason.TAXABLE_ABROAD,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.reducedRateVAT",
		("3560", "5560", "Waren aus einem Umsatzsteuerlager, § 13a UStG 7 % Vorsteuer und 7 % Umsatzsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.generalRateVAT",
		(
			"3565",
			"5565",
			"Waren aus einem Umsatzsteuerlager, § 13a UStG 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.misc",
		("3600-3609", "5600-5609", "Nicht abziehbare Vorsteuer"),
		("3610-3619", "5610-5619", "Nicht abziehbare Vorsteuer 7 %"),
		("3660-3669", "5660-5669", "Nicht abziehbare Vorsteuer 19 %"),
		reason=Reason.NONDEDUCTIBLE_INPUT_MATERIAL,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.unknownVAT",
		("3700", "5700", "Nachlässe"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.unknownVAT",
		("3701", "5701", "Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.reducedRateVAT",
		("3710-3711", "5710-5711", "Nachlässe 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.reducedRateVAT",
		("3714", "5714", "Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.generalRateVAT",
		("3715", "5715", "Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.intraEU",
		(
			"3717",
			"5717",
			"Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer",
		),
		(
			"3718",
			"5718",
			"Nachlässe aus Einkauf Roh-, Hilfs- und Betriebsstoffe, innergemeinschaftlicher Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.generalRateVAT",
		("3720-3721", "5720-5721", "Nachlässe 19 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.unknownVAT",
		(None, "5722", "Nachlässe 16 % Vorsteuer"),
		(None, "5723", "Nachlässe 15 % Vorsteuer"),
		reason=Reason.RATE_16_PURCHASE,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.intraEU",
		("3724", "5724", "Nachlässe aus innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer"),
		("3725", "5725", "Nachlässe aus innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer"),
		(None, "5726", "Nachlässe aus innergem. Erwerb 16 % Vorsteuer und 16 % Umsatzsteuer"),
		(None, "5727", "Nachlässe aus innergem. Erwerb 15 % Vorsteuer und 15 % Umsatzsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.unknownVAT",
		("3730", "5730", "Erhaltene Skonti"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.reducedRateVAT",
		("3731", "5731", "Erhaltene Skonti 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.unknownVAT",
		("3733", "5733", "Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.reducedRateVAT",
		("3734", "5734", "Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.generalRateVAT",
		("3736", "5736", "Erhaltene Skonti 19 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.generalRateVAT",
		("3738", "5738", "Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.intraEU",
		(
			"3741",
			"5741",
			"Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
		(
			"3743",
			"5743",
			"Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer",
		),
		(
			"3744",
			"5744",
			"Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe aus steuerpflichtigem innergemeinschaftlichem Erwerb",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.intraEU",
		("3745", "5745", "Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb"),
		(
			"3746",
			"5746",
			"Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb 7 % Vorsteuer und 7 % Umsatzsteuer",
		),
		(
			"3748",
			"5748",
			"Erhaltene Skonti aus steuerpflichtigem innergemeinschaftlichem Erwerb 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.reducedRateVAT",
		("3750-3751", "5750-5751", "Erhaltene Boni 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.unknownVAT",
		("3753", "5753", "Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.reducedRateVAT",
		("3754", "5754", "Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.generalRateVAT",
		("3755", "5755", "Erhaltene Boni aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.generalRateVAT",
		("3760-3761", "5760-5761", "Erhaltene Boni 19 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.unknownVAT",
		("3769", "5769", "Erhaltene Boni"),
		("3770", "5770", "Erhaltene Rabatte"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.reducedRateVAT",
		("3780-3781", "5780-5781", "Erhaltene Rabatte 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.unknownVAT",
		("3783", "5783", "Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.reducedRateVAT",
		("3784", "5784", "Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.generalRateVAT",
		("3785", "5785", "Erhaltene Rabatte aus Einkauf Roh-, Hilfs- und Betriebsstoffe 19 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.unknownVAT",
		("3787", "5787", "Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 9,0 % Vorsteuer"),
		reason=Reason.FLAT_RATE_INPUT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.generalRateVAT",
		("3790-3791", "5790-5791", "Erhaltene Rabatte 19 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.generalRateVAT",
		(
			"3792",
			"5792",
			"Erhaltene Skonti aus Erwerb Roh-, Hilfs- und Betriebsstoffe als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
		reason=Reason.TRIANGULAR_LAST,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.generalRateVAT",
		(
			"3793",
			"5793",
			"Erhaltene Skonti aus Erwerb Waren als letzter Abnehmer innerhalb Dreiecksgeschäft 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
		reason=Reason.TRIANGULAR_LAST,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.unknownVAT",
		("3794", "5794", "Erhaltene Skonti 5,5 % Vorsteuer"),
		("3795", "5795", "Erhaltene Skonti 9,0 % Vorsteuer"),
		reason=Reason.FLAT_RATE_INPUT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.unknownVAT",
		("3798", "5798", "Erhaltene Skonti aus Einkauf Roh-, Hilfs- und Betriebsstoffe 5,5 % Vorsteuer"),
		reason=Reason.FLAT_RATE_INPUT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.misc",
		("3800", "5800", "Bezugsnebenkosten"),
		("3830", "5820", "Leergut"),
		("3850", "5840", "Zölle und Einfuhrabgaben"),
		reason=Reason.INCIDENTAL_COSTS,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.misc",
		(None, "5860", "Verrechnete Stoffkosten (Gegenkonto 5000-99)"),
		reason=Reason.MATERIAL_MIXED,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.misc",
		("3960-3969", "5880", "Bestandsveränderungen Roh-, Hilfs- und Betriebsstoffe sowie bezogene Waren"),
		reason=Reason.INVENTORY_CHANGE_MIXED,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.purchased.inventoryChange",
		("3950-3954", "5881", "Bestandsveränderungen Waren"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.rawMatConsSup.inventoryChange",
		("3955-3959", "5885", "Bestandsveränderungen Roh-, Hilfs- und Betriebsstoffe"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.services.unknownVAT",
		("3100", "5900", "Fremdleistungen"),
		reason=Reason.VAT_SPLIT,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.services.OtherDedInputTax",
		("3106", "5906", "Fremdleistungen 19 % Vorsteuer"),
		("3108", "5908", "Fremdleistungen 7 % Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.services.OtherNonDedInputTax",
		("3109", "5909", "Fremdleistungen ohne Vorsteuer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.services.UStG13bDedInputTax",
		(
			"3110",
			"5910",
			"Bauleistungen eines im Inland ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer",
		),
		(
			"3113",
			"5913",
			"Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer",
		),
		(
			"3115",
			"5915",
			"Leistungen eines im Ausland ansässigen Unternehmers 7 % Vorsteuer und 7 % Umsatzsteuer",
		),
		(
			"3120-3121",
			"5920-5921",
			"Bauleistungen eines im Inland ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
		(
			"3123",
			"5923",
			"Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
		(
			"3125-3126",
			"5925-5926",
			"Leistungen eines im Ausland ansässigen Unternehmers 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.services.UStG13bNonDedInputTax",
		(
			"3130",
			"5930",
			"Bauleistungen eines im Inland ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer",
		),
		(
			"3133",
			"5933",
			"Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer",
		),
		(
			"3135",
			"5935",
			"Leistungen eines im Ausland ansässigen Unternehmers ohne Vorsteuer und 7 % Umsatzsteuer",
		),
		(
			"3140-3141",
			"5940-5941",
			"Bauleistungen eines im Inland ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer",
		),
		(
			"3143",
			"5943",
			"Sonstige Leistungen eines im anderen EU-Land ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer",
		),
		(
			"3145-3146",
			"5945-5946",
			"Leistungen eines im Ausland ansässigen Unternehmers ohne Vorsteuer und 19 % Umsatzsteuer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.services.unknownVAT",
		(
			"3150",
			"5950",
			"Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird",
		),
		reason=Reason.REVERSE_CHARGE_DEDUCTION,
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.services.UStG13bDedInputTax",
		(
			"3151",
			"5951",
			"Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird 19 % Vorsteuer und 19 % Umsatzsteuer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.services.UStG13bNonDedInputTax",
		(
			"3153",
			"5953",
			"Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird ohne Vorsteuer aber mit Umsatzsteuer",
		),
		(
			"3154",
			"5954",
			"Erhaltene Skonti aus Leistungen, für die als Leistungsempfänger die Steuer nach § 13b UStG geschuldet wird ohne Vorsteuer, mit 19 % Umsatzsteuer",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.services.UStG13bDedInputTax",
		("3160", "5960", "Leistungen nach § 13b UStG mit Vorsteuerabzug"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.services.UStG13bNonDedInputTax",
		("3165", "5965", "Leistungen nach § 13b UStG ohne Vorsteuerabzug"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.services.unknownVAT",
		("3170", "5970", "Fremdleistungen (Miet- und Pachtzinsen bewegliche Wirtschaftsgüter)"),
		("3175", "5975", "Fremdleistungen (Miet- und Pachtzinsen unbewegliche Wirtschaftsgüter)"),
		("3180", "5980", "Fremdleistungen (Entgelte für Rechte und Lizenzen)"),
		reason=Reason.VAT_SPLIT,
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"3185",
			"5985",
			"Fremdleistungen (Vergütungen für die Überlassung von Wirtschaftsgütern - mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.nonAllocable",
		("4100", "6000", "Löhne und Gehälter"),
		reason=Reason.SALARIES_MIXED,
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.misc",
		("4110", "6010", "Löhne"),
		("4120", "6020", "Gehälter"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.managerPartner",
		("4124", "6024", "Geschäftsführergehälter der GmbH-Gesellschafter"),
		("4126", "6026", "Tantiemen Gesellschafter-Geschäftsführer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.misc",
		("4127", "6027", "Geschäftsführergehälter"),
		reason=Reason.MANAGER_NOT_SHAREHOLDER,
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"4128",
			"6028",
			"Vergütungen an angestellte Mitunternehmer § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.misc",
		("4129", "6029", "Tantiemen Arbeitnehmer"),
		("4190", "6030", "Aushilfslöhne"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.minijobs",
		("4195", "6035", "Löhne für Minijobs"),
		("4194", "6036", "Pauschale Steuer für Minijobber"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.managerPartner",
		("4196", "6037", "Pauschale Steuer für Gesellschafter-Geschäftsführer"),
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"4197",
			"6038",
			"Pauschale Steuer für angestellte Mitunternehmer § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.misc",
		("4198", "6039", "Pauschale Steuer für Arbeitnehmer"),
		("4199", "6040", "Pauschale Steuer für Aushilfen"),
		("4180", "6045", "Bedienungsgelder"),
		("4125", "6050", "Ehegattengehalt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.voluntayBenefits",
		("4145", "6060", "Freiwillige soziale Aufwendungen, lohnsteuerpflichtig"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.minijobs",
		("4146", "6066", "Freiwillige Zuwendungen an Minijobber"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.managerPartner",
		("4147", "6067", "Freiwillige Zuwendungen an Gesellschafter-Geschäftsführer"),
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"4148",
			"6068",
			"Freiwillige Zuwendungen an angestellte Mitunternehmer § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.misc",
		("4149", "6069", "Pauschale Steuer auf sonstige Bezüge (z. B. Fahrtkostenzuschüsse)"),
		("4150", "6070", "Krankengeldzuschüsse"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.minijobs",
		("4151", "6071", "Sachzuwendungen und Dienstleistungen an Minijobber"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.inKind",
		("4152", "6072", "Sachzuwendungen und Dienstleistungen an Arbeitnehmer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.managerPartner",
		("4153", "6073", "Sachzuwendungen und Dienstleistungen an Gesellschafter-Geschäftsführer"),
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"4154",
			"6074",
			"Sachzuwendungen und Dienstleistungen an angestellte Mitunternehmer § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.misc",
		("4155", "6075", "Zuschüsse der Agenturen für Arbeit (Haben)"),
		("4156", "6076", "Aufwendungen aus der Veränderung von Urlaubsrückstellungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.managerPartner",
		(
			"4157",
			"6077",
			"Aufwendungen aus der Veränderung von Urlaubsrückstellungen für Gesellschafter-Geschäftsführer",
		),
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"4158",
			"6078",
			"Aufwendungen aus der Veränderung von Urlaubsrückstellungen für angestellte Mitunternehmer § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.minijobs",
		("4159", "6079", "Aufwendungen aus der Veränderung von Urlaubsrückstellungen für Minijobber"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.salaries.misc",
		("4170", "6080", "Vermögenswirksame Leistungen"),
		("4175", None, "Fahrtkostenerstattung - Wohnung/Arbeitsstätte"),
		(None, "6090", "Fahrtkostenerstattung Wohnung/Arbeitsstätte"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.social.other",
		(None, "6100", "Soziale Abgaben und Aufwendungen für Altersversorgung und für Unterstützung"),
		reason=Reason.SOCIAL_MIXED,
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.social.socExp.other",
		("4130", "6110", "Gesetzliche soziale Aufwendungen"),
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"4137",
			"6118",
			"Gesetzliche soziale Aufwendungen für Mitunternehmer § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.social.socExp.other",
		("4138", "6120", "Beiträge zur Berufsgenossenschaft"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.social.welfare",
		("4140", "6130", "Freiwillige soziale Aufwendungen, lohnsteuerfrei"),
		reason=Reason.VOLUNTARY_TAX_FREE,
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.social.pensions.other",
		("4165", "6140", "Aufwendungen für Altersversorgung"),
		("4167", "6147", "Pauschale Steuer auf sonstige Bezüge (z. B. Direktversicherungen)"),
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"4168",
			"6148",
			"Aufwendungen für Altersversorgung für Mitunternehmer § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.social.pensions.shareholderManager",
		("4166", "6149", "Aufwendungen für Altersversorgung für Gesellschafter-Geschäftsführer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.social.pensions.other",
		("4160", "6150", "Versorgungskassen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.social.welfare",
		("4169", "6160", "Aufwendungen für Unterstützung"),
	),
	_position(
		"is.netIncome.regular.operatingTC.staff.social.socExp.other",
		("4141", "6170", "Sonstige soziale Abgaben"),
		("4144", "6171", "Soziale Abgaben für Minijobber"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.otherIntan",
		("4822", "6200", "Abschreibungen auf immaterielle Vermögensgegenstände"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.otherIntan",
		("4823", "6201", "Abschreibungen auf selbst geschaffene immaterielle Vermögensgegenstände"),
		purpose=Purpose.COMMERCIAL,
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.goodwill",
		("4824", "6205", "Abschreibungen auf den Geschäfts- oder Firmenwert"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.specific.except.goodwill",
		("4825", "6209", "Außerplanmäßige Abschreibungen auf den Geschäfts- oder Firmenwert"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.specific.except.otherIntan",
		("4826", "6210", "Außerplanmäßige Abschreibungen auf immaterielle Vermögensgegenstände"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.specific.except.otherIntan",
		(
			"4827",
			"6211",
			"Außerplanmäßige Abschreibungen auf selbst geschaffene immaterielle Vermögensgegenstände",
		),
		purpose=Purpose.COMMERCIAL,
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.other",
		("4830", "6220", "Abschreibungen auf Sachanlagen (ohne AfA auf Fahrzeuge und Gebäude)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.buildings",
		("4831", "6221", "Abschreibungen auf Gebäude"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.other",
		("4832", "6222", "Abschreibungen auf Fahrzeuge"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.buildings",
		("4833", None, "Abschreibungen auf Gebäudeanteil des häuslichen Arbeitszimmers"),
		(None, "6223", "Abschreibungen auf Gebäudeteil des häuslichen Arbeitszimmers"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.specific.except.tan",
		("4840", "6230", "Außerplanmäßige Abschreibungen auf Sachanlagen"),
		(
			"4841",
			"6231",
			"Absetzung für außergewöhnliche technische und wirtschaftliche Abnutzung der Gebäude",
		),
		(
			"4842",
			"6232",
			"Absetzung für außergewöhnliche technische und wirtschaftliche Abnutzung der Fahrzeuge",
		),
		(
			"4843",
			"6233",
			"Absetzung für außergewöhnliche technische und wirtschaftliche Abnutzung sonstiger Wirtschaftsgüter",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.specific.impairment",
		("4850", "6240", "Abschreibungen auf Sachanlagen auf Grund steuerlicher Sondervorschriften"),
		("4851", "6241", "Sonderabschreibungen nach § 7g Abs. 5 EStG (ohne Fahrzeuge)"),
		("4852", "6242", "Sonderabschreibungen nach § 7g Abs. 5 EStG (für Fahrzeuge)"),
		purpose=Purpose.TAX,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.deductValueEStG7g_2",
		(
			"4853",
			"6243",
			"Kürzung der Anschaffungs- oder Herstellungskosten nach § 7g Abs. 2 EStG (ohne Fahrzeuge)",
		),
		(
			"4854",
			"6244",
			"Kürzung der Anschaffungs- oder Herstellungskosten nach § 7g Abs. 2 EStG (für Fahrzeuge)",
		),
		purpose=Purpose.TAX,
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.lowValueAs",
		("4855", None, "Sofortabschreibung geringwertiger Wirtschaftsgüter"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.specific.impairment",
		("4856", "6245", "Sonderabschreibungen nach § 7b EStG (Mietwohnungsneubau)"),
		purpose=Purpose.TAX,
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.specific.EStG6b_3",
		("4859", "6249", "Abzugsbetrag nach § 6b EStG"),
		purpose=Purpose.TAX,
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.other",
		("4815", "6250", "Kaufleasing"),
		reason=Reason.HIRE_PURCHASE,
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.lowValueAs",
		(None, "6260", "Sofortabschreibungen geringwertiger Wirtschaftsgüter"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.other",
		("4860", "6262", "Abschreibungen auf aktivierte, geringwertige Wirtschaftsgüter"),
		reason=Reason.CAPITALISED_GWG,
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.lowValueAsCollItem",
		("4862", "6264", "Abschreibungen auf den Sammelposten Wirtschaftsgüter"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.specific.except.tan",
		("4865", "6266", "Außerplanmäßige Abschreibungen auf aktivierte, geringwertige Wirtschaftsgüter"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.fixAss.other",
		(
			None,
			"6268",
			"Abschreibungen auf Aufwendungen f. die Ingangsetzung und Erweiterung des Geschäftsbetriebs",
		),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.START_UP_COSTS,
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.currAss.receiv.other",
		(
			"4880",
			"6270",
			"Abschreibungen auf sonstige Vermögensgegenstände des Umlaufvermögens (soweit unüblich hoch)",
		),
		reason=Reason.UNUSUAL_OTHER,
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.currAss.misc",
		("4882", "6272", "Abschreibungen auf Umlaufvermögen, steuerrechtlich bedingt (soweit unüblich hoch)"),
		purpose=Purpose.TAX,
		reason=Reason.CURRENT_ASSETS_MIXED,
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.currAss.inventory",
		(None, "6278", "Abschreibungen auf Roh-, Hilfs- und Betriebsstoffe/Waren (soweit unüblich hoch)"),
		(None, "6279", "Abschreibungen auf fertige und unfertige Erzeugnisse (soweit unüblich hoch)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.currAss.receiv.other",
		("2430", "6280", "Forderungsverluste (soweit unüblich hoch)"),
		("2431", "6281", "Forderungsverluste 7 % USt (soweit unüblich hoch)"),
		(None, "6285", "Forderungsverluste 16% USt (soweit unüblich hoch)"),
		("2436", "6286", "Forderungsverluste 19 % USt (soweit unüblich hoch)"),
		(None, "6287", "Forderungsverluste 15% USt (soweit unüblich hoch)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.currAss.receiv.againstCorpParticip",
		(
			"2440",
			"6290",
			"Abschreibungen auf Forderungen gegenüber Kapitalgesellschaften, an denen eine Beteiligung besteht (soweit unüblich hoch), § 3c EStG bzw. § 8b Abs. 3 KStG",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.currAss.receiv.sharehRelPart",
		(
			"2441",
			None,
			"Abschreibungen auf Forderungen gegenüber Gesellschaftern und nahestehende Personen (soweit unüblich hoch), § 3 Nr. 40 EStG bzw. § 8b Abs. 3 KStG",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.transferValuatonPresentYear.global",
		("2450", None, "Einstellungen in die Pauschalwertberichtigung auf Forderungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.transferValuatonPresentYear.specific",
		("2451", None, "Einstellungen in die Einzelwertberichtigung auf Forderungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.currAss.receiv.sharehRelPart",
		(
			None,
			"6291",
			"Abschreibungen auf Forderungen gegenüber Gesellschaftern und nahe stehende Personen (soweit unüblich hoch), § 3 Nr. 40 EStG bzw. § 8b Abs. 3 KStG",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.miscellaneous",
		("4900", "6300", "Sonstige betriebliche Aufwendungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		(
			"4902",
			"6302",
			"Interimskonto für Aufwendungen in einem anderen Land, bei denen eine Vorsteuervergütung möglich ist",
		),
		("4909", "6303", "Fremdleistungen/Fremdarbeiten"),
		(None, "6304", "Sonstige Aufwendungen betrieblich und regelmäßig"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.misc",
		("4200", "6305", "Raumkosten"),
		reason=Reason.ROOM_COSTS,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leaseFix.other",
		("4210", "6310", "Miete (unbewegliche Wirtschaftsgüter)"),
	),
	_watched(
		Reason.SOLE_TRADER,
		("4212", "6312", "Miete/Aufwendungen für doppelte Haushaltsführung Unternehmer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leaseFix.shareholders",
		(
			"4222",
			"6313",
			"Vergütungen an Gesellschafter für die miet- oder pachtweise Überlassung ihrer unbeweglichen Wirtschaftsgüter",
		),
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"4219",
			"6314",
			"Vergütungen an Mitunternehmer für die mietweise Überlassung ihrer unbeweglichen Wirtschaftsgüter § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leaseFix.other",
		("4220", "6315", "Pacht (unbewegliche Wirtschaftsgüter)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leasingAll.immovable",
		("4215", "6316", "Leasing (unbewegliche Wirtschaftsgüter)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leaseFix.other",
		(
			"4211",
			"6317",
			"Aufwendungen für gemietete oder gepachtete unbewegliche Wirtschaftsgüter, die gewerbesteuerlich hinzuzurechnen sind",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.misc",
		("4228", "6318", "Miet- und Pachtnebenkosten, die gewerbesteuerlich nicht hinzuzurechnen sind"),
		reason=Reason.LEASE_INCIDENTALS,
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"4229",
			"6319",
			"Vergütungen an Mitunternehmer für die pachtweise Überlassung ihrer unbeweglichen Wirtschaftsgüter § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.energyCost",
		("4230", "6320", "Heizung"),
		("4240", "6325", "Gas, Strom, Wasser"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("4250", "6330", "Reinigung"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.fixingLandBuildings",
		("4260", "6335", "Instandhaltung betrieblicher Räume"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.insurance",
		("4270", "6340", "Abgaben für betrieblich genutzten Grundbesitz"),
		reason=Reason.LAND_LEVIES,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("4280", "6345", "Sonstige Raumkosten"),
	),
	_watched(
		Reason.SOLE_TRADER,
		("4287", "6347", "Tagespauschale für die Tätigkeit in der häuslichen Wohnung"),
		("4288", "6348", "Aufwendungen für ein häusliches Arbeitszimmer (abziehbarer Anteil)"),
		("4289", "6349", "Aufwendungen für ein häusliches Arbeitszimmer (nicht abziehbarer Anteil)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("4290", None, "Grundstücksaufwendungen betrieblich"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherTaxes",
		("4300", None, "Nicht abziehbare Vorsteuer"),
		("4301", None, "Nicht abziehbare Vorsteuer 7 %"),
		("4306", None, "Nicht abziehbare Vorsteuer 19 %"),
		reason=Reason.NONDEDUCTIBLE_INPUT,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		(None, "6350", "Grundstücksaufwendungen, betrieblich"),
		("2350", "6352", "Sonstige Grundstücksaufwendungen (neutral)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.other",
		("2380", "6390", "Zuwendungen, Spenden, steuerlich nicht abziehbar"),
		("2381", "6391", "Zuwendungen, Spenden für wissenschaftliche und kulturelle Zwecke"),
		("2382", "6392", "Zuwendungen, Spenden für mildtätige Zwecke"),
		("2383", "6393", "Zuwendungen, Spenden für kirchliche, religiöse und gemeinnützige Zwecke"),
		("2384", "6394", "Zuwendungen, Spenden an politische Parteien"),
		(
			"2387",
			"6395",
			"Zuwendungen, Spenden in das zu erhaltende Vermögen (Vermögensstock) einer Stiftung für gemeinnützige Zwecke",
		),
		(
			None,
			"6396",
			"Zuwendungen, Spenden an Stiftungen f. gemeinnützige Zwecke i. S. d. § 52 Abs. 2 Nr. 4 AO",
		),
		(
			"2389",
			"6397",
			"Zuwendungen, Spenden in das zu erhaltende Vermögen (Vermögensstock) einer Stiftung für kirchliche, religiöse und gemeinnützige Zwecke",
		),
		(
			"2390",
			"6398",
			"Zuwendungen, Spenden an Stiftungen in das zu erhaltende Vermögen (Vermögensstock) für wissenschaftliche, mildtätige, kulturelle Zwecke",
		),
		reason=Reason.DONATIONS,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.insurance",
		("4360", "6400", "Versicherungen"),
		("4366", "6405", "Versicherungen für Gebäude"),
		("4370", "6410", "Netto-Prämie für Rückdeckung künftiger Versorgungsleistungen"),
		("4380", "6420", "Beiträge"),
		("4390", "6430", "Sonstige Abgaben"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("4396", "6436", "Steuerlich abzugsfähige Verspätungszuschläge und Zwangsgelder"),
		reason=Reason.LATE_FEES_DEDUCTIBLE,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.other",
		("4397", "6437", "Steuerlich nicht abzugsfähige Verspätungszuschläge und Zwangsgelder"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.staffRelated",
		("4139", "6440", "Ausgleichsabgabe nach dem Schwerbehindertengesetz"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.fixingLandBuildings",
		("4801", "6450", "Reparaturen und Instandhaltung von Bauten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.fixing",
		("4800", "6460", "Reparaturen und Instandhaltung von technischen Anlagen und Maschinen"),
		(
			"4805",
			"6470",
			"Reparaturen und Instandhaltung von anderen Anlagen und Betriebs- und Geschäftsausstattung",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.provisions",
		("4808", "6475", "Zuführung zu Aufwandsrückstellungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.fixing",
		(None, "6485", "Reparaturen und Instandhaltung von anderen Anlagen"),
		("4809", "6490", "Sonstige Reparaturen und Instandhaltung"),
		("4806", "6495", "Wartungskosten für Hard- und Software"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leasingAll.moveable",
		("4810", "6498", "Mietleasing bewegliche Wirtschaftsgüter für technische Anlagen und Maschinen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.vehicles",
		("4500", "6500", "Fahrzeugkosten"),
		("4520", "6520", "Fahrzeug-Versicherungen"),
		("4530", "6530", "Laufende Fahrzeug-Betriebskosten"),
		("4540", "6540", "Fahrzeug-Reparaturen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leaseFix.other",
		("4550", "6550", "Garagenmiete"),
		reason=Reason.GARAGE_RENT,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leasingAll.moveable",
		("4570", "6560", "Mietleasing Kfz"),
		(
			"4575",
			"6565",
			"Mietleasingaufwendungen für Elektrofahrzeuge und Fahrräder, die gewerbesteuerlich hinzuzurechnen sind",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.vehicles",
		("4580", "6570", "Sonstige Fahrzeugkosten"),
		("4560", "6580", "Mautgebühren"),
		("4590", "6590", "Kosten für betrieblich genutzte zum Privatvermögen gehörende Fahrzeuge"),
		("4595", "6595", "Fremdfahrzeugkosten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.marketing",
		("4600", "6600", "Werbekosten"),
		("4605", "6605", "Streuartikel"),
		("4610", None, "Werbekosten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.gifts.deductible",
		("4630", "6610", "Geschenke abzugsfähig ohne § 37b EStG"),
		("4631", "6611", "Geschenke abzugsfähig mit § 37b EStG"),
		("4632", "6612", "Pauschale Steuer für Geschenke und Zuwendungen abzugsfähig"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.gifts.nondeductible",
		("4635", "6620", "Geschenke nicht abzugsfähig ohne § 37b EStG"),
		("4636", "6621", "Geschenke nicht abzugsfähig mit § 37b EStG"),
		("4637", "6622", "Pauschale Steuer für Geschenke und Zuwendungen nicht abzugsfähig"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.gifts.deductible",
		("4638", "6625", "Geschenke ausschließlich betrieblich genutzt"),
		reason=Reason.GIFTS_BUSINESS_USE,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.marketing",
		("4639", "6629", "Zugaben mit § 37b EStG"),
		reason=Reason.PREMIUMS,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.marketing",
		("4640", "6630", "Repräsentationskosten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.entertainment.deductible",
		("4650", "6640", "Bewirtungskosten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.other",
		("4651", "6641", "Sonstige eingeschränkt abziehbare Betriebsausgaben (abziehbarer Anteil)"),
		reason=Reason.OTHER_LIMITED,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.other",
		("4652", "6642", "Sonstige eingeschränkt abziehbare Betriebsausgaben (nicht abziehbarer Anteil)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("4653", "6643", "Aufmerksamkeiten"),
		reason=Reason.ATTENTION,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.entertainment.nonDeductible",
		("4654", "6644", "Nicht abzugsfähige Bewirtungskosten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.other",
		("4655", "6645", "Nicht abzugsfähige Betriebsausgaben aus Werbe- und Repräsentationskosten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.employee",
		("4660", "6650", "Reisekosten Arbeitnehmer"),
		("4666", "6660", "Reisekosten Arbeitnehmer Übernachtungsaufwand"),
		("4663", "6663", "Reisekosten Arbeitnehmer Fahrtkosten"),
		("4664", "6664", "Reisekosten Arbeitnehmer Verpflegungsmehraufwand"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.other",
		("4665", None, "nicht abzugsfähige Betriebsausg. aus Werbe-, Repräs.- u. Reisekosten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.employee",
		("4668", "6668", "Kilometergelderstattung Arbeitnehmer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.employee",
		("4670", "6670", "Reisekosten Unternehmer"),
		reason=Reason.MANAGER_TRAVEL,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.other",
		("4672", "6672", "Reisekosten Unternehmer (nicht abziehbarer Anteil)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.employee",
		("4673", "6673", "Reisekosten Unternehmer Fahrtkosten"),
		("4674", "6674", "Reisekosten Unternehmer Verpflegungsmehraufwand"),
		("4676", "6680", "Reisekosten Unternehmer Übernachtungsaufwand und Reisenebenkosten"),
		reason=Reason.MANAGER_TRAVEL,
	),
	_watched(
		Reason.SOLE_TRADER,
		(
			"4678",
			"6688",
			"Fahrten zwischen Wohnung und Betriebsstätte und Familienheimfahrten (abziehbarer Anteil) - Fahrzeuge im Betriebsvermögen",
		),
		(
			"4679",
			"6689",
			"Fahrten zwischen Wohnung und Betriebsstätte und Familienheimfahrten (nicht abziehbarer Anteil) - Fahrzeuge im Betriebsvermögen",
		),
		(
			"4680",
			"6690",
			"Fahrten zwischen Wohnung und Betriebsstätte und Familienheimfahrten (Haben) - Fahrzeuge im Betriebsvermögen",
		),
		("4681", "6691", "Verpflegungsmehraufwendungen im Rahmen der doppelten Haushaltsführung Unternehmer"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.freight",
		("4700", "6700", "Kosten der Warenabgabe"),
		("4710", "6710", "Verpackungsmaterial"),
		("4730", "6740", "Ausgangsfrachten"),
		("4750", "6760", "Transportversicherungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.fees",
		("4760", "6770", "Verkaufsprovisionen"),
		("4780", "6780", "Fremdarbeiten (Vertrieb)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("4790", None, "Aufwand für Gewährleistungen"),
		(None, "6790", "Aufwand für Gewährleistung"),
		reason=Reason.WARRANTY,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.communication",
		("4910", "6800", "Porto"),
		("4920", "6805", "Telefon"),
		("4921", None, "Mobilfunk D2"),
		("4922", None, "Internet"),
		("4925", "6810", "Internetkosten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("4930", "6815", "Bürobedarf"),
		("4940", "6820", "Zeitschriften, Bücher, digitale Medien (Fachliteratur)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.training",
		("4945", "6821", "Fortbildungskosten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.staffRelated",
		("4946", "6822", "Freiwillige Sozialleistungen"),
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"4948",
			"6823",
			"Sonstige Vergütungen an Mitunternehmer § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
		(
			"4949",
			"6824",
			"Haftungsvergütung an Mitunternehmer § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.legalConsulting",
		("4950", "6825", "Rechts- und Beratungskosten"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.legalConsulting",
		("4957", "6827", "Abschluss- und Prüfungskosten"),
		("4955", "6830", "Buchführungskosten"),
		reason=Reason.ACCOUNTING_COSTS,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leaseMoveable.shareholders",
		(
			"4958",
			"6833",
			"Vergütungen an Gesellschafter für die miet- oder pachtweise Überlassung ihrer beweglichen Wirtschaftsgüter",
		),
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"4959",
			"6834",
			"Vergütungen an Mitunternehmer für die miet- oder pachtweise Überlassung ihrer beweglichen Wirtschaftsgüter § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leaseMoveable.other",
		("4960", "6835", "Mieten für Einrichtungen (bewegliche Wirtschaftsgüter)"),
		("4961", "6836", "Pacht (bewegliche Wirtschaftsgüter)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.concessLicenses",
		(
			"4964",
			"6837",
			"Aufwendungen für die zeitlich befristete Überlassung von Rechten (Lizenzen, Konzessionen)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leaseMoveable.other",
		(
			"4963",
			"6838",
			"Aufwendungen für gemietete oder gepachtete bewegliche Wirtschaftsgüter, die gewerbesteuerlich hinzuzurechnen sind",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.leasingAll.moveable",
		("4965", "6840", "Mietleasing bewegliche Wirtschaftsgüter für Betriebs- und Geschäftsausstattung"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("4985", "6845", "Werkzeuge und Kleingeräte"),
		("4980", "6850", "Sonstiger Betriebsbedarf"),
	),
	_watched(
		Reason.COOPERATIVE,
		("4984", "6854", "Genossenschaftliche Rückvergütung an Mitglieder"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("4970", "6855", "Nebenkosten des Geldverkehrs"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		(
			"4975",
			"6856",
			"Aufwendungen aus Anteilen an Kapitalgesellschaften §§ 3 Nr. 40 und 3c EStG bzw. § 8b Abs. 1 und 4 KStG",
		),
		reason=Reason.SHARE_COSTS,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.disposalCorp",
		("4976", "6857", "Veräußerungskosten § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG (bei Buchgewinn)"),
		(
			"4977",
			None,
			"Veräußerungskosten § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (bei Buchverlust)",
		),
		(
			None,
			"6858",
			"Veräußerungskosten § 3 Nr. 40 EStG bzw. § 8b Abs. 2 i. V. m. § 8b Abs. 3 S. 3 KStG (bei Buchverlust)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("4969", "6859", "Aufwendungen für Abraum- und Abfallbeseitigung"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherTaxes",
		("2170", "6860", "Nicht abziehbare Vorsteuer"),
		("2171", "6865", "Nicht abziehbare Vorsteuer 7 %"),
		("2176", "6871", "Nicht abziehbare Vorsteuer 19 %"),
		reason=Reason.NONDEDUCTIBLE_INPUT,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.other",
		("2385", "6875", "Nicht abziehbare Hälfte der Aufsichtsratsvergütungen"),
		("2386", "6876", "Abziehbare Aufsichtsratsvergütungen"),
		reason=Reason.SUPERVISORY_BOARD,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.custodyFee",
		("4971", "6879", "Verwahrentgelt"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.currLoss",
		("2150", "6880", "Aufwendungen aus der Währungsumrechnung"),
		("2151", "6881", "Aufwendungen aus der Währungsumrechnung (nicht § 256a HGB)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("2166", "6883", "Aufwendungen aus Bewertung Finanzmittelfonds"),
		reason=Reason.CASH_FUND_VALUATION,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.disposFixAss.sale.tan",
		(
			"8807",
			"6884",
			"Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1a UStG (bei Buchverlust)",
		),
		("8801-8806", "6885", "Erlöse aus Verkäufen Sachanlagevermögen 19 % USt (bei Buchverlust)"),
		(
			"8808",
			"6888",
			"Erlöse aus Verkäufen Sachanlagevermögen steuerfrei § 4 Nr. 1b UStG (bei Buchverlust)",
		),
		("8800", "6889", "Erlöse aus Verkäufen Sachanlagevermögen (bei Buchverlust)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.disposFixAss.sale.intan",
		("8817", "6890", "Erlöse aus Verkäufen immaterieller Vermögensgegenstände (bei Buchverlust)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.disposFixAss.sale.fin",
		("8818", "6891", "Erlöse aus Verkäufen Finanzanlagen (bei Buchverlust)"),
		(
			"8819",
			"6892",
			"Erlöse aus Verkäufen Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (bei Buchverlust)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.disposFixAss.bookValue.tan",
		("2310", "6895", "Anlagenabgänge Sachanlagen (Restbuchwert bei Buchverlust)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.disposFixAss.bookValue.intan",
		("2311", "6896", "Anlagenabgänge immaterielle Vermögensgegenstände (Restbuchwert bei Buchverlust)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.disposFixAss.bookValue.fin",
		("2312", "6897", "Anlagenabgänge Finanzanlagen (Restbuchwert bei Buchverlust)"),
		(
			"2313",
			None,
			"Anlagenabgänge Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V m. § 8b Abs. 3 S. 3 KStG (Restbuchwert bei Buchverlust)",
		),
		(
			None,
			"6898",
			"Anlagenabgänge Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (Restbuchwert bei Buchverlust)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.disposFixAss.misc",
		(None, "6900", "Verluste aus dem Abgang von Gegenständen des Anlagevermögens"),
		reason=Reason.DISPOSAL_KIND,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.disposFixAss.misc",
		(
			None,
			"6903",
			"Verluste aus der Veräußerung von Anteilen an Kap.Ges. (Finanzanlagevermögen, inl. Kap.Ges.)",
		),
		reason=Reason.NET_DISPOSAL,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.disposCurrAss",
		(
			"2324",
			"6904",
			"Abgänge Wertpapiere des Umlaufvermögens § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG (Buchwert bei Buchverlust)",
		),
		("2325", None, "Verluste aus dem Abgang von Gegenständen des Umlaufvermögens (außer Vorräte)"),
		(None, "6905", "Verluste aus dem Abgang von Gegenständen des Umlaufvermögens außer Vorräte"),
		(
			"2326",
			"6906",
			"Verluste aus dem Abgang von Gegenständen des Umlaufvermögens (außer Vorräte) § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG",
		),
	),
	_watched(
		Reason.EUR,
		("2327", "6907", "Abgang von Wirtschaftsgütern des Umlaufvermögens nach § 4 Abs. 3 Satz 4 EstG"),
		(
			"2328",
			"6908",
			"Abgang von Wirtschaftsgütern des Umlaufvermögens § 3 Nr. 40 EStG bzw. § 8b Abs. 2 KStG i. V. m. § 8b Abs. 3 S. 3 KStG nach § 4 Abs. 3 S. 4 EStG",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.regAllowance",
		(
			"4886",
			"6910",
			"Abschreibungen auf Umlaufvermögen außer Vorräte und Wertpapiere des Umlaufvermögens (übliche Höhe)",
		),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.regAllowance",
		(
			"4887",
			"6912",
			"Abschreibungen auf Umlaufvermögen außer Vorräte und Wertpapiere des Umlaufvermögens, steuerrechtlich bedingt (übliche Höhe)",
		),
		purpose=Purpose.TAX,
	),
	_position(
		"is.netIncome.regular.operatingTC.deprAmort.currAss.inventory",
		("4892", None, "Abschreibungen auf Roh-, Hilfs- und Betriebsstoffe/Waren (soweit unübliche Höhe)"),
		("4893", None, "Abschreibungen auf fertige und unfertige Erzeugnisse (soweit unübliche Höhe)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("2347", "6918", "Aufwendungen aus dem Erwerb eigener Anteile"),
		reason=Reason.OWN_SHARES,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.transferValuatonPresentYear.global",
		(None, "6920", "Einstellung in die Pauschalwertberichtigung auf Forderungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.addPreTaxRes.EStG6b_3",
		("2342", "6922", "Einstellungen in die steuerliche Rücklage nach § 6b Abs. 3 EStG"),
		purpose=Purpose.TAX,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.transferValuatonPresentYear.specific",
		(None, "6923", "Einstellung in die Einzelwertberichtigung auf Forderungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.addPreTaxRes.other",
		("2343", "6924", "Einstellungen in die steuerliche Rücklage nach § 6b Abs. 10 EStG"),
		("2345", "6927", "Einstellungen in sonstige steuerliche Rücklagen"),
		purpose=Purpose.TAX,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.addPreTaxRes.substEStR6_6",
		("2344", "6928", "Einstellungen in die Rücklage für Ersatzbeschaffung nach R 6.6 EStR"),
		purpose=Purpose.TAX,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.addPreTaxRes.EStG4g",
		("2339", "6929", "Einstellungen in die steuerliche Rücklage nach § 4g EStG"),
		purpose=Purpose.TAX,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.regAllowance",
		("2400", "6930", "Forderungsverluste (übliche Höhe)"),
		("2401", "6931", "Forderungsverluste 7 % USt (übliche Höhe)"),
		("2402", "6932", "Forderungsverluste aus steuerfreien EU-Lieferungen (übliche Höhe)"),
		(
			"2403",
			"6933",
			"Forderungsverluste aus im Inland steuerpflichtigen EU-Lieferungen 7 % USt (übliche Höhe)",
		),
		(None, "6934", "Forderungsverluste aus im Inland steuerpfl. EU-Lieferungen 16 % USt (übliche Höhe)"),
		(None, "6935", "Forderungsverluste 16% USt (übliche Höhe)"),
		("2406", "6936", "Forderungsverluste 19 % USt (übliche Höhe)"),
		(None, "6937", "Forderungsverluste 15% USt (übliche Höhe)"),
		(
			"2408",
			"6938",
			"Forderungsverluste aus im Inland steuerpflichtigen EU-Lieferungen 19 % USt (übliche Höhe)",
		),
		(None, "6939", "Forderungsverluste aus im Inland steuerpfl. EU-Lieferungen 15% USt (übliche Höhe)"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		("2020", "6960", "Periodenfremde Aufwendungen"),
		(None, "6967", "Sonstige Aufwendungen betriebsfremd und regelmäßig"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.other",
		("2308", "6968", "Sonstige nicht abziehbare Aufwendungen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.otherOrdinary",
		(None, "6969", "Sonstige Aufwendungen unregelmäßig"),
	),
	_outside(
		Outside.CALCULATORY,
		("4990", "6970", "Kalkulatorischer Unternehmerlohn"),
		("4991", None, "Kalkulatorische Miete und Pacht"),
		(None, "6972", "Kalkulatorische Miete/Pacht"),
		("4992", "6974", "Kalkulatorische Zinsen"),
		("4993", "6976", "Kalkulatorische Abschreibungen"),
		("4994", "6978", "Kalkulatorische Wagnisse"),
		("4995", "6979", "Kalkulatorischer Lohn für unentgeltliche Mitarbeiter"),
		("2890", "6980", "Verrechneter kalkulatorischer Unternehmerlohn"),
		("2891", None, "Verrechnete kalkulatorische Miete und Pacht"),
		(None, "6982", "Verrechnete kalkulatorische Miete/Pacht"),
		("2892", "6984", "Verrechnete kalkulatorische Zinsen"),
		("2893", "6986", "Verrechnete kalkulatorische Abschreibungen"),
		("2894", "6988", "Verrechnete kalkulatorische Wagnisse"),
		("2895", "6989", "Verrechneter kalkulatorischer Lohn für unentgeltliche Mitarbeiter"),
	),
	_position(
		"is.netIncome.regular.operatingTC.grossTradingProfit.materialServices.material.misc",
		("4996", "6990", "Herstellungskosten"),
		("4997", "6992", "Verwaltungskosten"),
		("4998", "6994", "Vertriebskosten"),
		("4999", None, "Gegenkonto 4996-4998"),
		(None, "6999", "Gegenkonto 6990-6998"),
		reason=Reason.ERPNEXT_COST_OF_GOODS,
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earnings.other",
		("2600", "7000", "Erträge aus Beteiligungen"),
		reason=Reason.LEGAL_FORM_SPLIT,
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earnings.silentPart",
		("2613", "7002", "Erträge aus typisch stillen Beteiligungen"),
	),
	_position(
		"is.netIncome.regular.fin.commPart",
		("2614", "7003", "Erträge aus atypisch stillen Beteiligungen"),
	),
	_position(
		"is.netIncome.regular.fin.commPart",
		(
			"2603",
			"7004",
			"Erträge aus Beteiligungen an Personengesellschaften (verbundene Unternehmen), § 9 GewStG bzw. § 18 EStG",
		),
		reason=Reason.PARTNERSHIP_INCOME,
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earnings.corporations",
		(
			"2615",
			"7005",
			"Erträge aus Anteilen an Kapitalgesellschaften (Beteiligung) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 KStG",
		),
		(
			"2616",
			"7006",
			"Erträge aus Anteilen an Kapitalgesellschaften (verbundene Unternehmen) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 KStG",
		),
		(
			None,
			"7007",
			"Sonstige GewSt-freie Gewinne aus Anteilen an einer Kap.Ges. (Kürzung gem. § 9 Nr. 2a GewStG)",
		),
	),
	_position(
		"is.netIncome.regular.fin.commPart",
		(
			"2618",
			"7008",
			"Gewinnanteile aus gewerblichen und selbständigen Mitunternehmerschaften, § 9 GewStG bzw. § 18 EStG",
		),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earnings.other",
		("2619", "7009", "Erträge aus Beteiligungen an verbundenen Unternehmen"),
		reason=Reason.LEGAL_FORM_SPLIT,
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningSecurities.misc",
		("2620", "7010", "Erträge aus anderen Wertpapieren und Ausleihungen des Finanzanlagevermögens"),
		reason=Reason.SECURITIES_INCOME_MIXED,
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningSecurities.misc",
		("2621", "7011", "Erträge aus Ausleihungen des Finanzanlagevermögens"),
		reason=Reason.LOANS_INCOME_MIXED,
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningSecurities.shareholder",
		("2622", "7012", "Erträge aus Ausleihungen des Finanzanlagevermögens an verbundenen Unternehmen"),
		reason=Reason.LOAN_INCOME,
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningSecurities.partnerships",
		("2623", "7013", "Erträge aus Anteilen an Personengesellschaften (Finanzanlagevermögen)"),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningSecurities.corporations",
		(
			"2625",
			"7014",
			"Erträge aus Anteilen an Kapitalgesellschaften (Finanzanlagevermögen) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 und 4 KStG",
		),
		(
			"2626",
			"7015",
			"Erträge aus Anteilen an Kapitalgesellschaften (verbundene Unternehmen) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 KStG",
		),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningSecurities.partnerships",
		("2646", "7016", "Erträge aus Anteilen an Personengesellschaften (verbundene Unternehmen)"),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningSecurities.corporations",
		(
			"2647",
			"7017",
			"Erträge aus anderen Wertpapieren des Finanzanlagevermögens an Kapitalgesellschaften (verbundene Unternehmen)",
		),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningSecurities.partnerships",
		(
			"2648",
			"7018",
			"Erträge aus anderen Wertpapieren des Finanzanlagevermögens an Personengesellschaften (verbundene Unternehmen)",
		),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningSecurities.misc",
		(
			"2649",
			"7019",
			"Erträge aus anderen Wertpapieren und Ausleihungen des Finanzanlagevermögens aus verbundenen Unternehmen",
		),
		reason=Reason.SECURITIES_INCOME_MIXED,
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningSecurities.interestDividend.nonAllocable",
		("2640", "7020", "Zins- und Dividendenerträge"),
		reason=Reason.INTEREST_DIVIDEND,
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningSecurities.minorInterestReceived",
		("2641", "7030", "Erhaltene Ausgleichszahlungen (als außenstehender Aktionär)"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.misc",
		("2650", "7100", "Sonstige Zinsen und ähnliche Erträge"),
		reason=Reason.INTEREST_MIXED,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.securities.dividends",
		(
			"2655",
			"7103",
			"Erträge aus Anteilen an Kapitalgesellschaften (Umlaufvermögen) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 und 4 KStG",
		),
		(
			"2656",
			"7104",
			"Erträge aus Anteilen an Kapitalgesellschaften (verbundene Unternehmen) § 3 Nr. 40 EStG bzw. § 8b Abs. 1 KStG",
		),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.deposits.AO233a",
		("2657", "7105", "Zinserträge § 233a AO, steuerpflichtig"),
		("2658", "7106", "Zinserträge § 233a AO, steuerfrei (Anlage GK KSt)"),
		("2653", "7107", "Zinserträge § 233a AO und § 4 Abs. 5b EStG, steuerfrei"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.affiliated",
		("2659", "7109", "Sonstige Zinsen und ähnliche Erträge aus verbundenen Unternehmen"),
		reason=Reason.AFFILIATED_INTEREST,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.other",
		(None, "7110", "Sonstige Zinserträge"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.misc",
		("2654", "7115", "Erträge aus anderen Wertpapieren und Ausleihungen des Umlaufvermögens"),
		reason=Reason.SECURITIES_INCOME_MIXED,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.affiliated",
		(None, "7119", "Sonstige Zinserträge aus verbundenen Unternehmen"),
		reason=Reason.AFFILIATED_INTEREST,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.other",
		("2680", "7120", "Zinsähnliche Erträge"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.affiliated",
		("2689", "7129", "Zinsähnliche Erträge aus verbundenen Unternehmen"),
		reason=Reason.AFFILIATED_INTEREST,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.miscellaneous",
		("2700", None, "Andere betriebs- und/oder periodenfremde (neutrale) sonstige Erträge"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.discount",
		(None, "7130", "Diskonterträge"),
		(None, "7139", "Diskonterträge aus verbundenen Unternehmen"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.valueDiscount",
		("2682", "7140", "Steuerfreie Zinserträge aus der Abzinsung von Rückstellungen"),
		(
			"2683",
			"7141",
			"Zinserträge aus der Abzinsung von auf Rentenverpflichtungen beruhenden Verbindlichkeiten, für die eine Gegenleistung nicht mehr zu erwarten ist",
		),
		("2684", "7142", "Zinserträge aus der Abzinsung von Rückstellungen"),
		(
			"2685",
			"7143",
			"Zinserträge aus der Abzinsung von Pensionsrückstellungen und ähnlichen/vergleichbaren Verpflichtungen",
		),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.income.offsetAssets",
		(
			"2686",
			"7144",
			"Zinserträge aus der Abzinsung von Pensionsrückstellungen und ähnlichen/vergleichbaren Verpflichtungen zur Verrechnung nach § 246 Abs. 2 HGB",
		),
		("2687", "7145", "Erträge aus Vermögensgegenständen zur Verrechnung nach § 246 Abs. 2 HGB"),
		opposite="is.netIncome.regular.fin.netInterest.expenses.offsetting",
		purpose=Purpose.COMMERCIAL,
		reason=Reason.OFFSET_INTEREST,
	),
	_position(
		"is.netIncome.incomeSharing.loss",
		("2790", "7190", "Erträge aus Verlustübernahme"),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.earningProfSharing",
		("2792", "7192", "Erhaltene Gewinne auf Grund einer Gewinngemeinschaft"),
		("2794", "7194", "Erhaltene Gewinne auf Grund eines Gewinn- oder Teilgewinnabführungsvertrags"),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.amortFinanc.financialsExcept.misc",
		("4870", "7200", "Abschreibungen auf Finanzanlagen (dauerhaft)"),
		reason=Reason.WRITE_DOWN_MIXED,
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.amortFinanc.financialsExcept.misc",
		("4866", "7201", "Abschreibungen auf Finanzanlagen (nicht dauerhaft)"),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.WRITE_DOWN_MIXED,
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.amortFinanc.financialsExcept.participCorp",
		(
			"4871",
			"7204",
			"Abschreibungen auf Finanzanlagen § 3 Nr. 40 EStG bzw. § 8b Abs. 3 KStG (dauerhaft)",
		),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.amortFinanc.financialsExcept.misc",
		("4877", "7207", "Abschreibungen auf Finanzanlagen - verbundene Unternehmen"),
		reason=Reason.WRITE_DOWN_MIXED,
	),
	_position(
		"is.netIncome.regular.fin.lossCommPart",
		(
			"4872",
			"7208",
			"Aufwendungen auf Grund von Verlustanteilen an gewerblichen und selbständigen Mitunternehmerschaften, § 8 GewStG bzw. § 18 EStG",
		),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.amortFinanc.secCurrAss",
		("4875", "7210", "Abschreibungen auf Wertpapiere des Umlaufvermögens"),
		(
			"4876",
			"7214",
			"Abschreibungen auf Wertpapiere des Umlaufvermögens § 3 Nr. 40 EStG bzw. § 8b Abs. 3 KStG",
		),
		("4878", "7217", "Abschreibungen auf Wertpapiere des Umlaufvermögens - verbundene Unternehmen"),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.amortFinanc.other",
		("4874", "7250", "Abschreibungen auf Finanzanlagen auf Grund § 6b EStG-Rücklage"),
		(
			"4873",
			"7255",
			"Abschreibungen auf Finanzanlagen auf Grund § 6b EStG-Rücklage, § 3 Nr. 40 EStG bzw. § 8b Abs. 3 KStG",
		),
		purpose=Purpose.TAX,
		reason=Reason.SEC_6B_TRANSFER,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.misc",
		("2100", "7300", "Zinsen und ähnliche Aufwendungen"),
		reason=Reason.INTEREST_MIXED,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.relatedPayments",
		("2102", "7302", "Steuerlich nicht abzugsfähige andere Nebenleistungen zu Steuern § 4 Abs. 5b EStG"),
		("2103", "7303", "Steuerlich abzugsfähige andere Nebenleistungen zu Steuern"),
		("2104", "7304", "Steuerlich nicht abzugsfähige andere Nebenleistungen zu Steuern"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.AO233a",
		("2107", "7305", "Zinsaufwendungen § 233a AO abzugsfähig"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.AO234to237",
		("2108", "7306", "Zinsaufwendungen §§ 234 bis 237 AO nicht abzugsfähig"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.AO233a",
		("2105", "7308", "Zinsaufwendungen § 233a AO nicht abzugsfähig"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.misc",
		("2109", "7309", "Zinsaufwendungen an verbundene Unternehmen"),
		reason=Reason.AFFILIATED_INTEREST_EXPENSE,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.other",
		("2110", "7310", "Zinsaufwendungen für kurzfristige Verbindlichkeiten"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.AO234to237",
		("2111", "7311", "Zinsaufwendungen §§ 234 bis 237 AO abzugsfähig"),
	),
	_watched(
		Reason.SOLE_TRADER,
		("2113", "7313", "Nicht abzugsfähige Schuldzinsen nach § 4 Abs. 4a EStG (Hinzurechnungsbetrag)"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.PartnersLoans.misc",
		("2114", "7316", "Zinsen für Gesellschafterdarlehen"),
		reason=Reason.SHAREHOLDER_INTEREST,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.PartnersLoans.participationOver25pt",
		(
			"2117",
			"7317",
			"Zinsen an Gesellschafter mit einer Beteiligung von mehr als 25 % bzw. diesen nahe stehende Personen",
		),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.other",
		("2118", "7318", "Zinsen auf Kontokorrentkonten"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.misc",
		("2119", "7319", "Zinsaufwendungen für kurzfristige Verbindlichkeiten an verbundene Unternehmen"),
		reason=Reason.AFFILIATED_INTEREST_EXPENSE,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.other",
		("2120", "7320", "Zinsaufwendungen für langfristige Verbindlichkeiten"),
		("2121", None, "Zinsaufwendungen für KFZ Finanzierung"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.amortDiscount",
		("2123", "7323", "Abschreibungen auf ein Agio oder Disagio/Damnum zur Finanzierung"),
		(
			"2124",
			"7324",
			"Abschreibungen auf ein Agio oder Disagio/Damnum zur Finanzierung des Anlagevermögens",
		),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.other",
		("2125", "7325", "Zinsaufwendungen für Gebäude, die zum Betriebsvermögen gehören"),
		("2126", "7326", "Zinsen zur Finanzierung des Anlagevermögens"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.annuities",
		("2127", "7327", "Renten und dauernde Lasten"),
	),
	_watched(
		Reason.PARTNERSHIP,
		(
			"2128",
			"7328",
			"Zinsaufwendungen für Kapitalüberlassung durch Mitunternehmer § 15 EStG (mit Sonderbetriebseinnahme korrespondierend)",
		),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.regularInterest.misc",
		("2129", "7329", "Zinsaufwendungen für langfristige Verbindlichkeiten an verbundene Unternehmen"),
		reason=Reason.AFFILIATED_INTEREST_EXPENSE,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.other",
		("2140", "7330", "Zinsähnliche Aufwendungen"),
		("2149", "7339", "Zinsähnliche Aufwendungen an verbundene Unternehmen"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.discount",
		(None, "7340", "Diskontaufwendungen"),
		(None, "7349", "Diskontaufwendungen an verb. Unternehmen"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.misc",
		(
			"2115",
			"7350",
			"Zinsen und ähnliche Aufwendungen §§ 3 Nr. 40 und 3c EStG bzw. § 8b Abs. 1 und 4 KStG",
		),
		(
			"2116",
			"7351",
			"Zinsen und ähnliche Aufwendungen an verbundene Unternehmen §§ 3 Nr. 40 und 3c EStG bzw. § 8b Abs. 1 KStG",
		),
		reason=Reason.INTEREST_MIXED,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.loanFees",
		("2141", "7355", "Kreditprovisionen und Verwaltungskostenbeiträge"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.calcInterestOnPensProv",
		("2142", "7360", "Zinsanteil der Zuführungen zu Pensionsrückstellungen"),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.valueDiscount",
		(
			"2143",
			"7361",
			"Zinsaufwendungen aus der Abzinsung von auf Rentenverpflichtungen beruhenden Verbindlichkeiten, für die eine Gegenleistung nicht mehr zu erwarten ist",
		),
		("2144", "7362", "Zinsaufwendungen aus der Abzinsung von Rückstellungen"),
		(
			"2145",
			"7363",
			"Zinsaufwendungen aus der Abzinsung von Pensionsrückstellungen und ähnlichen/vergleichbaren Verpflichtungen",
		),
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.offsetting",
		(
			"2146",
			"7364",
			"Zinsaufwendungen aus der Abzinsung von Pensionsrückstellungen und ähnlichen/vergleichbaren Verpflichtungen zur Verrechnung nach § 246 Abs. 2 HGB",
		),
		("2147", "7365", "Aufwendungen aus Vermögensgegenständen zur Verrechnung nach § 246 Abs. 2 HGB"),
		opposite="is.netIncome.regular.fin.netInterest.income.offsetAssets",
		purpose=Purpose.COMMERCIAL,
		reason=Reason.OFFSET_INTEREST,
	),
	_position(
		"is.netIncome.regular.fin.netInterest.expenses.valueDiscount",
		(
			"2148",
			"7366",
			"Steuerlich nicht abzugsfähige Zinsaufwendungen aus der Abzinsung von Rückstellungen",
		),
	),
	_position(
		"is.netIncome.regular.fin.netParticipation.loss",
		("2490", "7390", "Aufwendungen aus Verlustübernahme"),
	),
	_position(
		"is.netIncome.incomeSharing.gain",
		("2492", "7392", "Abgeführte Gewinne auf Grund einer Gewinngemeinschaft"),
		("2494", "7394", "Abgeführte Gewinne auf Grund eines Gewinn- oder Teilgewinnabführungsvertrags"),
	),
	_watched(
		Reason.SILENT_ATYPICAL,
		(
			"2491",
			"7398",
			"Abgeführte Gewinnanteile (Soll) /ausgeglichene Verlustanteile (Haben) bei atypisch stiller Beteiligung",
		),
	),
	_position(
		"is.netIncome.incomeSharing.gain",
		(
			"2493",
			"7399",
			"Abgeführte Gewinnanteile (Soll) /ausgeglichene Verlustanteile (Haben) bei typisch stiller Beteiligung § 8 GewStG",
		),
		opposite="is.netIncome.incomeSharing.loss",
		reason=Reason.SILENT_TYPICAL_RESULT,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.nonAllocable",
		(None, "7400", "Außerordentliche Erträge"),
		(None, "7401", "Außerordentliche Erträge finanzwirksam"),
		(None, "7450", "Außerordentliche Erträge nicht finanzwirksam"),
		reason=Reason.EXTRAORDINARY_OLD,
	),
	_position(
		"is.netIncome.extraord.income.merger",
		("2504", "7451", "Erträge durch Verschmelzung und Umwandlung"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.miscellaneous",
		("2510", None, "Sonstige betriebsfremde Erträge"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.disposFixAss.nonAllocable",
		(None, "7452", "Erträge durch den Verkauf von bedeutenden Beteiligungen"),
		(None, "7453", "Ertäge durch den Verkauf von bedeutenden Grundstücken"),
		reason=Reason.NET_DISPOSAL,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.nonAllocable",
		(None, "7454", "Gewinn aus der Veräußerung oder der Aufgabe von Geschäftsaktivitäten nach Steuern"),
		(None, "7460", "Außerordentliche Erträge aus der Anwendung von Übergangsvorschriften"),
		reason=Reason.EXTRAORDINARY_OLD,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.revalFixAss",
		(None, "7461", "Außerordentliche Erträge: Zuschreibung f. Sachanlagevermögen"),
		(None, "7462", "Außerordentliche Erträge: Zuschreibung f. Finanzanlagevermögen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.revalCurrAss",
		(None, "7463", "Außerordentliche Erträge: Wertpapiere im Umlaufvermögen"),
	),
	_position(
		"is.netIncome.tax.deferred",
		(None, "7464", "Außerordentliche Erträge: latente Steuern"),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.DEFERRED_TAXES,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.misc",
		(None, "7500", "Außerordentliche Aufwendungen"),
		(None, "7501", "Außerordentliche Aufwendungen finanzwirksam"),
		(None, "7550", "Außerordentliche Aufwendungen nicht finanzwirksam"),
		reason=Reason.EXTRAORDINARY_OLD,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.merger",
		("2004", "7551", "Verluste durch Verschmelzung und Umwandlung"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.misc",
		(None, "7552", "Verluste durch außergewöhnliche Schadensfälle"),
		reason=Reason.EXTRAORDINARY_OLD,
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.restructuring",
		("2007", "7553", "Aufwendungen für Restrukturierungs- und Sanierungsmaßnahmen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.misc",
		(None, "7554", "Verluste aus Geschäftsaufgabe oder -veräußerung nach Steuern"),
		(None, "7560", "Außerordentliche Aufwendungen aus der Anwendung von Übergangsvorschriften"),
		(
			None,
			"7561",
			"Außerordentliche Aufwendungen aus der Anwendung von Übergangsvorschriften (Pensionsrückst.)",
		),
		(
			None,
			"7562",
			"Außerordentliche Aufwendungen aus der Anwendung von Übergangsvorschriften (Bilanzierungshilfen)",
		),
		reason=Reason.EXTRAORDINARY_OLD,
	),
	_position(
		"is.netIncome.tax.deferred",
		(
			None,
			"7563",
			"Außerordentliche Aufwendungen aus der Anwendung von Übergangsvorschriften (Latente Steuern)",
		),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.DEFERRED_TAXES,
	),
	_position(
		"is.netIncome.tax.kst",
		("2200", "7600", "Körperschaftsteuer"),
	),
	_position(
		"is.netIncome.tax.prevPeriodPaid",
		("2203", "7603", "Körperschaftsteuer für Vorjahre"),
		opposite="is.netIncome.tax.prevPeriodReceived",
		reason=Reason.PREVIOUS_YEARS,
	),
	_position(
		"is.netIncome.tax.prevPeriodReceived",
		("2204", "7604", "Körperschaftsteuererstattungen für Vorjahre"),
		("2210", "7607", "Solidaritätszuschlagerstattungen für Vorjahre"),
	),
	_position(
		"is.netIncome.tax.soli",
		("2208", "7608", "Solidaritätszuschlag"),
	),
	_position(
		"is.netIncome.tax.prevPeriodPaid",
		("2209", "7609", "Solidaritätszuschlag für Vorjahre"),
		opposite="is.netIncome.tax.prevPeriodReceived",
		reason=Reason.PREVIOUS_YEARS,
	),
	_position(
		"is.netIncome.tax.gewst",
		("4320", "7610", "Gewerbesteuer"),
	),
	_position(
		"is.netIncome.tax.kest",
		("2213", "7630", "Kapitalertragsteuer 25 %"),
	),
	_position(
		"is.netIncome.tax.soli",
		("2216", "7633", "Anrechenbarer Solidaritätszuschlag auf Kapitalertragsteuer 25 %"),
	),
	_position(
		"is.netIncome.tax.nonDeductableForeignIncomeTaxes",
		("2218", "7638", "Ausländische Steuer auf im Inland steuerfreie DBA-Einkünfte"),
		reason=Reason.FOREIGN_TAX_DBA,
	),
	_position(
		"is.netIncome.tax.deductableForeignIncomeTaxes",
		("2219", None, "Anrechnung/Abzug ausländische Quellensteuer"),
		(None, "7639", "Anrechnung/Abzug ausländischer Quellensteuer"),
	),
	_position(
		"is.netIncome.tax.prevPeriodPaid",
		(None, "7640", "Gewerbesteuernachzahlungen Vorjahre"),
	),
	_position(
		"is.netIncome.tax.prevPeriodPaid",
		(
			"2281",
			"7641",
			"Gewerbesteuernachzahlungen und Gewerbesteuererstattungen für Vorjahre nach § 4 Abs. 5b EStG",
		),
		opposite="is.netIncome.tax.prevPeriodReceived",
		reason=Reason.PREVIOUS_YEARS,
	),
	_position(
		"is.netIncome.tax.prevPeriodReceived",
		(None, "7642", "Gewerbesteuererstattungen Vorjahre"),
	),
	_position(
		"is.netIncome.tax.releaseTaxProv",
		("2283", "7643", "Erträge aus der Auflösung von Gewerbesteuerrückstellungen nach § 4 Abs. 5b EStG"),
		(None, "7644", "Erträge aus der Auflösung von Gewerbesteuerrückstellungen"),
	),
	_position(
		"is.netIncome.tax.deferred",
		("2250", "7645", "Aufwendungen aus der Zuführung und Auflösung von latenten Steuern"),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.DEFERRED_TAXES,
	),
	_position(
		"is.netIncome.tax.deferred",
		("2260", "7646", "Aufwendungen aus der Zuführung zu Steuerrückstellungen für Steuerstundung (BStBK)"),
		("2265", "7648", "Erträge aus der Auflösung von Steuerrückstellungen für Steuerstundung (BStBK)"),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.DEFERRAL_PROVISION,
	),
	_position(
		"is.netIncome.tax.deferred",
		("2255", "7649", "Erträge aus der Zuführung und Auflösung von latenten Steuern"),
		purpose=Purpose.COMMERCIAL,
		reason=Reason.DEFERRED_TAXES,
	),
	_position(
		"is.netIncome.otherTaxes",
		("4340", "7650", "Sonstige Betriebssteuern"),
		("4350", "7675", "Verbrauchsteuer (sonstige Steuern)"),
		("4355", "7678", "Ökosteuer"),
		("2375", "7680", "Grundsteuer"),
		("4510", "7685", "Kfz-Steuer"),
		("2285", "7690", "Steuernachzahlungen Vorjahre für sonstige Steuern"),
		("2287", "7692", "Steuererstattungen Vorjahre für sonstige Steuern"),
		("2289", "7694", "Erträge aus der Auflösung von Rückstellungen für sonstige Steuern"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherCost.miscellaneous",
		("2300", None, "Sonstige Aufwendungen"),
	),
	_watched(
		Reason.APPROPRIATION,
		("2860", "7700", "Gewinnvortrag nach Verwendung"),
		("2865", "7705", "Gewinnvortrag nach Verwendung (mit Aufteilung für Kapitalkontenentwicklung)"),
		("2868", "7720", "Verlustvortrag nach Verwendung"),
		("2867", "7725", "Verlustvortrag nach Verwendung (mit Aufteilung für Kapitalkontenentwicklung)"),
		("2795", "7730", "Entnahmen aus der Kapitalrücklage"),
		("2796", "7735", "Entnahmen aus der gesetzlichen Rücklage"),
		("2798", "7740", "Entnahmen aus dem Ausgleichsposten für aktivierte eigene Anteile"),
		(
			"2840",
			"7743",
			"Entnahmen aus der Rücklage für Anteile an einem herrschenden oder mehrheitlich beteiligten Unternehmen",
		),
		("2850", "7744", "Entnahmen aus anderen Ergebnisrücklagen"),
		("2797", "7745", "Entnahmen aus satzungsmäßigen Rücklagen"),
		("2799", "7750", "Entnahmen aus anderen Gewinnrücklagen"),
		(
			"2841",
			"7751",
			"Entnahmen aus gesamthänderisch gebundenen Rücklagen (mit Aufteilung für Kapitalkontenentwicklung)",
		),
		("2745", "7755", "Ertrag aus der Kapitalherabsetzung"),
		(
			"2495",
			"7760",
			"Einstellungen in die Kapitalrücklage nach den Vorschriften über die vereinfachte Kapitalherabsetzung",
		),
		("2496", "7765", "Einstellungen in die gesetzliche Rücklage"),
		("2498", "7770", "Einstellungen in den Ausgleichsposten für aktivierte eigene Anteile"),
		(
			"2480",
			"7773",
			"Einstellungen in die Rücklage für Anteile an einem herrschenden oder mehrheitlich beteiligten Unternehmen",
		),
		("2497", "7775", "Einstellungen in satzungsmäßige Rücklagen"),
		("2499", "7780", "Einstellungen in andere Gewinnrücklagen"),
	),
	_position(
		"is.netIncome.regular.operatingTC.otherOpRevenue.nonAllocable",
		("2500", None, "Außerordentliche Erträge"),
		reason=Reason.EXTRAORDINARY_OLD,
	),
	_watched(
		Reason.APPROPRIATION,
		(
			"2481",
			"7781",
			"Einstellungen in gesamthänderisch gebundene Rücklagen (mit Aufteilung für Kapitalkontenentwicklung)",
		),
		("2485", "7785", "Einstellungen in andere Ergebnisrücklagen"),
		("2488", "7788", "Änderung steuerlicher Ausgleichsposten (Körperschaften)"),
		(
			"2489",
			"7789",
			"Änderung steuerlicher Ausgleichsposten (Personengesellschaften, Einzelunternehmen)",
		),
		("2870", "7790", "Vorabausschüttung"),
	),
	_watched(
		Reason.FREE_USE,
		("4400-4499", "7800-7899", "(zur freien Verfügung)"),
	),
	_watched(
		Reason.RESERVED,
		(None, "7900", "(reserviertes Konto)"),
	),
	_outside(
		Outside.CARRYFORWARD,
		("9000", "9000", "Saldenvorträge, Sachkonten"),
		("9001-9007", "9001-9007", "Saldenvorträge, Sachkonten"),
		("9008", "9008", "Saldenvorträge, Debitoren"),
		("9009", "9009", "Saldenvorträge, Kreditoren"),
		("9051", "9051", "Offene Posten aus 2021"),
		("9052", "9052", "Offene Posten aus 2022"),
		("9053", "9053", "Offene Posten aus 2023"),
		("9054", "9054", "Offene Posten aus 2024"),
		("9055", "9055", "Offene Posten aus 2025"),
		("9056", "9056", "Offene Posten aus 2026"),
		("9090", "9090", "Summenvortragskonto"),
	),
	_outside(
		Outside.STATISTICAL,
		("9101", "9101", "Verkaufstage"),
		("9102", "9102", "Anzahl der Barkunden"),
		("9120", "9120", "Erweiterungsinvestitionen"),
		("9135", "9135", "Auftragseingang im Geschäftsjahr"),
	),
	_watched(
		Reason.PARTNERSHIP,
		("9141", "9141", "Variables Kapital TH"),
		("9142", None, "Variables Kapital - Anteil für Teilhafter"),
		(None, "9142", "Variables Kapital - Anteil Teilhafter"),
		("9143", "9143", "Privatsteuern Kapitalertragsteuer (Sammelposten)"),
		("9144", "9144", "Privatsteuern Solidaritätszuschlag (Sammelposten)"),
		("9145", "9145", "Privatsteuern Kirchensteuer (Sammelposten)"),
		("9146", None, "Variables Kapital Vollhafter - Übertragung einer § 6b EStG-Rücklage"),
		("9147", None, "Variables Kapital Teilhafter - Übertragung einer § 6b EStG-Rücklage"),
		(None, "9146", "Variables Kapital Vollhafter - Übertragung einer"),
		(None, "9147", "Variables Kapital Teilhafter - Übertragung einer"),
		("9150", "9150", "Festkapital - andere Kapitalkontenanpassungen VH"),
		("9151", "9151", "Variables Kapital - andere Kapitalkontenanpassungen VH"),
		("9152", "9152", "Verlust-/Vortragskonto - andere Kapitalkontenanpassungen VH"),
		("9153", "9153", "Kapitalkonto III - andere Kapitalkontenanpassungen VH"),
		(
			"9154",
			"9154",
			"Ausstehende Einlagen auf das Komplementär-Kapital, nicht eingefordert - andere Kapitalkontenanpassungen VH",
		),
		(
			"9155",
			"9155",
			"Verrechnungskonto für Einzahlungsverpflichtungen - andere Kapitalkontenanpassungen VH",
		),
		("9157", "9157", "Privatsteuern Kapitalertragsteuer (Vollhafter)"),
		("9158", "9158", "Privatsteuern Solidaritätszuschlag (Vollhafter)"),
		("9159", "9159", "Privatsteuern Kirchensteuer (Vollhafter)"),
		("9160", "9160", "Kommandit-Kapital - andere Kapitalkontenanpassungen TH"),
		("9161", "9161", "Variables Kapital - andere Kapitalkontenanpassungen TH"),
		("9162", "9162", "Verlustausgleichskonto - andere Kapitalkontenanpassungen TH"),
		("9163", "9163", "Kapitalkonto III - andere Kapitalkontenanpassungen TH"),
		(
			"9164",
			"9164",
			"Ausstehende Einlagen auf das Kommandit-Kapital, nicht eingefordert - andere Kapitalkontenanpassungen TH",
		),
		(
			"9165",
			"9165",
			"Verrechnungskonto für Einzahlungsverpflichtungen - andere Kapitalkontenanpassungen TH",
		),
		("9167", "9167", "Privatsteuern Kapitalertragsteuer (Teilhafter), Eigenkapital"),
		("9168", "9168", "Privatsteuern Solidaritätszuschlag (Teilhafter), Eigenkapital"),
		("9169", "9169", "Privatsteuern Kirchensteuer (Teilhafter), Eigenkapital"),
		("9170", "9170", "Festkapital - Umbuchungen VH"),
		("9171", "9171", "Variables Kapital - Umbuchungen VH"),
		("9172", "9172", "Verlust-/Vortragskonto - Umbuchungen VH"),
		("9173", "9173", "Kapitalkonto III - Umbuchungen VH"),
		(
			"9174",
			"9174",
			"Ausstehende Einlagen auf das Komplementär-Kapital, nicht eingefordert - Umbuchungen VH",
		),
		("9175", "9175", "Verrechnungskonto für Einzahlungsverpflichtungen - Umbuchungen VH"),
		("9180", "9180", "Kommandit-Kapital - Umbuchungen TH"),
		("9181", "9181", "Variables Kapital - Umbuchungen TH"),
		("9182", "9182", "Verlustausgleichskonto - Umbuchungen TH"),
		("9183", "9183", "Kapitalkonto III - Umbuchungen TH"),
		(
			"9184",
			"9184",
			"Ausstehende Einlagen auf das Kommandit-Kapital, nicht eingefordert - Umbuchungen TH",
		),
		("9185", "9185", "Verrechnungskonto für Einzahlungsverpflichtungen - Umbuchungen TH"),
		("9186", "9186", "Privatsteuern Kapitalertragsteuer (Teilhafter), Fremdkapital"),
		("9187", "9187", "Privatsteuern Solidaritätszuschlag (Teilhafter), Fremdkapital"),
		("9188", "9188", "Privatsteuern Kirchensteuer (Teilhafter), Fremdkapital"),
		("9189", "9189", "Verrechnungskonto für Umbuchungen zwischen Gesellschafter-Eigenkapitalkonten"),
	),
	_outside(
		Outside.STATISTICAL,
		("9190", "9190", "Gegenkonto für statistische Mengeneinheiten Konten 9101-9102"),
		("9199", "9199", "Gegenkonto zu Konten 9120 und 9135"),
		("9200", "9200", "Beschäftigte Personen"),
		("9209", "9209", "Gegenkonto zu 9200"),
		("9210", "9210", "Produktive Löhne"),
		("9219", "9219", "Gegenkonto zu 9210"),
		("9220", "9220", "Gezeichnetes Kapital in DM (Art. 42 Abs. 3 Satz 1 EGHGB)"),
		("9229", "9229", "Gegenkonto zu 9220"),
		("9240", "9240", "Investitionsverbindlichkeiten bei den Leistungsverbindlichkeiten"),
		("9241", "9241", "Investitionsverbindlichkeiten aus Sachanlagekäufen bei Leistungsverbindlichkeiten"),
		(
			"9242",
			"9242",
			"Investitionsverbindlichkeiten aus Käufen von immateriellen Vermögensgegenständen bei Leistungsverbindlichkeiten",
		),
		(
			"9243",
			"9243",
			"Investitionsverbindlichkeiten aus Käufen von Finanzanlagen bei Leistungsverbindlichkeiten",
		),
		("9244", None, "Gegenkonto zu Konten 9240-9243"),
		(None, "9244", "Gegenkonto zu Konto 9240-43"),
		("9245", "9245", "Forderungen aus Sachanlageverkäufen bei sonstigen Vermögensgegenständen"),
		(
			"9246",
			"9246",
			"Forderungen aus Verkäufen immaterieller Vermögensgegenstände bei sonstigen Vermögensgegenständen",
		),
		("9247", "9247", "Forderungen aus Verkäufen von Finanzanlagen bei sonstigen Vermögensgegenständen"),
		("9249", None, "Gegenkonto zu Konten 9245-9247"),
		(None, "9249", "Gegenkonto zu Konto 9245-47"),
		("9260", "9260", "Kurzfristige Rückstellungen"),
		("9262", "9262", "Mittelfristige Rückstellungen"),
		("9264", "9264", "Langfristige Rückstellungen, außer Pensionen"),
		("9269", "9269", "Gegenkonto zu Konten 9260-9268"),
		("9270", "9270", "Gegenkonto zu 9271-9279 (Soll-Buchung)"),
		("9271", "9271", "Verbindlichkeiten aus der Begebung und Übertragung von Wechseln"),
		(
			"9272",
			"9272",
			"Verbindlichkeiten aus der Begebung und Übertragung von Wechseln gegenüber verbundenen/assoziierten Unternehmen",
		),
		("9273", "9273", "Verbindlichkeiten aus Bürgschaften, Wechsel- und Scheckbürgschaften"),
		(
			"9274",
			"9274",
			"Verbindlichkeiten aus Bürgschaften, Wechsel- und Scheckbürgschaften gegenüber verbundenen/assoziierten Unternehmen",
		),
		("9275", "9275", "Verbindlichkeiten aus Gewährleistungsverträgen"),
		(
			"9276",
			"9276",
			"Verbindlichkeiten aus Gewährleistungsverträgen gegenüber verbundenen/assoziierten Unternehmen",
		),
		("9277", "9277", "Haftung aus der Bestellung von Sicherheiten für fremde Verbindlichkeiten"),
		(
			"9278",
			"9278",
			"Haftung aus der Bestellung von Sicherheiten für fremde Verbindlichkeiten gegenüber verbundenen/assoziierten Unternehmen",
		),
		("9279", "9279", "Verpflichtungen aus Treuhandvermögen"),
		("9280", "9280", "Gegenkonto zu 9281-9284"),
		("9281", "9281", "Verpflichtungen aus Miet- und Leasingverträgen"),
		("9282", "9282", "Verpflichtungen aus Miet- und Leasingverträgen gegenüber verbundenen Unternehmen"),
		("9283", "9283", "Andere Verpflichtungen nach § 285 Nr. 3a HGB"),
		("9284", "9284", "Andere Verpflichtungen nach § 285 Nr. 3a HGB gegenüber verbundenen Unternehmen"),
		(
			"9285",
			"9285",
			"Unterschiedsbetrag aus der Abzinsung von Altersversorgungsverpflichtungen nach § 253 Abs. 6 HGB (Haben)",
		),
		("9286", "9286", "Gegenkonto zu 9285"),
		("9287", "9287", "Zinsen bei Buchungen über Debitoren bei § 4 Abs. 3 EStG"),
		("9288", "9288", "Mahngebühren bei Buchungen über Debitoren bei § 4 Abs. 3 EStG"),
		("9289", "9289", "Gegenkonto zu 9287 und 9288"),
		("9290", "9290", "Statistisches Konto steuerfreie Auslagen"),
		("9291", "9291", "Gegenkonto zu 9290"),
		("9292", "9292", "Statistisches Konto Fremdgeld"),
		("9293", "9293", "Gegenkonto zu 9292"),
	),
	_watched(
		Reason.SILENT_ATYPICAL,
		("9295", "9295", "Einlagen atypisch stiller Gesellschafter"),
	),
	_watched(
		Reason.TAX_BALANCE,
		("9297", "9297", "Steuerlicher Ausgleichsposten (Körperschaften"),
	),
	_watched(
		Reason.PARTNERSHIP,
		("9298", "9298", "Steuerlicher Ausgleichsposten VH (Personengesellschaften, Einzelunternehmen)"),
		("9299", "9299", "Steuerlicher Ausgleichsposten TH (Personengesellschaften)"),
	),
	_outside(
		Outside.STATISTICAL,
		("9390-9394", None, "(Zur freien Verfügung)"),
		("9395-9399", None, "(Zur freien Verfügung)"),
		(None, "9390", "Konto für Branchenlösungen (Werte 1), (Zur freien Verfügung)"),
		(None, "9391", "Konto für Branchenlösungen (Werte 2), (Zur freien Verfügung)"),
		(None, "9392", "Konto für Branchenlösungen (Werte 3), (Zur freien Verfügung)"),
		(None, "9393", "Konto für Branchenlösungen (Werte 4), (Zur freien Verfügung)"),
		(None, "9394", "Gegenkonto für Branchenlösungen (Werte), (Zur freien Verfügung)"),
		(None, "9395", "Konto für Branchenlösungen (Menge 1), (Zur freien Verfügung)"),
		(None, "9396", "Konto für Branchenlösungen (Menge 2), (Zur freien Verfügung)"),
		(None, "9397", "Konto für Branchenlösungen (Menge 3), (Zur freien Verfügung)"),
		(None, "9398", "Konto für Branchenlösungen (Menge 4), (Zur freien Verfügung)"),
		(None, "9399", "Gegenkonto für Branchenlösungen (Menge), (Zur freien Verfügung)"),
	),
	_watched(
		Reason.PARTNERSHIP,
		("9400", "9400", "Privatentnahmen allgemein (Teilhafter), Eigenkapital"),
		("9410", "9410", "Privatsteuern (Teilhafter), Eigenkapital"),
		("9420", "9420", "Sonderausgaben beschränkt abzugsfähig (Teilhafter), Eigenkapital"),
		("9430", "9430", "Sonderausgaben unbeschränkt abzugsfähig (Teilhafter), Eigenkapital"),
		("9440", "9440", "Zuwendungen, Spenden (Teilhafter), Eigenkapital"),
		("9450", "9450", "Außergewöhnliche Belastungen (Teilhafter), Eigenkapital"),
		("9460", "9460", "Grundstücksaufwand (Teilhafter), Eigenkapital"),
		("9470", "9470", "Grundstücksertrag (Teilhafter), Eigenkapital"),
		("9480", "9480", "Unentgeltliche Wertabgaben (Teilhafter), Eigenkapital"),
		("9490", "9490", "Privateinlagen (Teilhafter), Eigenkapital"),
	),
	_outside(
		Outside.PARTNERSHIP_STATISTICAL,
		("9500", None, "Anteil für Konto 0900 Teilhafter - Kommandit-Kapital"),
		("9510", None, "Anteil für Konto 0910 Teilhafter - Verlustausgleichskonto"),
		("9520", None, "Anteil für Konto 0920 Teilhafter - Gesellschafter-Darlehen"),
		("9530", None, "Anteil für Konto 9950 Teilhafter - Ausstehende Einlagen auf das"),
		("9540", None, "Anteil für Konto 9930 Vollhafter - Ausstehende Einlagen auf das"),
		(None, "9500", "Anteil für Konto 2000 Vollhafter - Festkapital"),
		(None, "9510", "Anteil für Konto 2010 Vollhafter - Variables Kapital"),
		(None, "9520", "Anteil für Konto 2020 Vollhafter - Gesellschafter-Darlehen"),
		("9550", "9530", "Anteil für Konto 9810 Vollhafter - Kapitalkonto III"),
		(None, "9540", "Anteil für Konto 0060 Vollhafter - Ausstehende Einlagen auf das"),
		(None, "9550", "Anteil für Konto 2050 Teilhafter - Kommandit-Kapital"),
		(None, "9560", "Anteil für Konto 2060 Teilhafter - Verlustausgleichskonto"),
		(None, "9570", "Anteil für Konto 2070 Teilhafter - Gesellschafter-Darlehen"),
		("9560", "9580", "Anteil für Konto 9820 Vollhafter - Verlustvortrag"),
		("9570", None, "Anteil für Konto 0870 Vollhafter - Festkapital"),
		("9580", None, "Anteil für Konto 0880 Vollhafter - Variables Kapital"),
		("9590", None, "Anteil für Konto 0890 Vollhafter - Gesellschafter-Darlehen"),
		(None, "9590", "Anteil für Konto 0080 Teilhafter - Ausstehende Einlagen auf das"),
		("9600", "9600", "Name des Gesellschafters Vollhafter"),
		("9610", "9610", "Tätigkeitsvergütung Vollhafter"),
		("9620", "9620", "Tantieme Vollhafter"),
		("9630", "9630", "Darlehensverzinsung Vollhafter"),
		("9640", "9640", "Gebrauchsüberlassung Vollhafter"),
		("9650", "9650", "Sonstige Vergütungen Vollhafter"),
		("9660", "9660", "Sonstige Vergütungen Vollhafter"),
		("9670", "9670", "Sonstige Vergütungen Vollhafter"),
		("9680", "9680", "Sonstige Vergütungen Vollhafter"),
		("9690", "9690", "Restanteil Vollhafter"),
		("9700", "9700", "Name des Gesellschafters Teilhafter"),
		("9710", "9710", "Tätigkeitsvergütung Teilhafter"),
		("9720", "9720", "Tantieme Teilhafter"),
		("9730", "9730", "Darlehensverzinsung Teilhafter"),
		("9740", "9740", "Gebrauchsüberlassung Teilhafter"),
		("9750", "9750", "Sonstige Vergütungen Teilhafter"),
		("9760", "9760", "Sonstige Vergütungen Teilhafter"),
		("9770", "9770", "Sonstige Vergütungen Teilhafter"),
		("9780", "9780", "Anteil für Konto 9840 Teilhafter - Kapitalkonto III"),
		("9790", "9790", "Restanteil Teilhafter"),
		("9791", "9791", "Anteil Rücklagen variables Kapitalkonto Vollhafter"),
		("9792", "9792", "Anteil Rücklagen Kapitalkonto III Vollhafter"),
		("9793", "9793", "Anteil Rücklagen Verlust-/Vortragskonto Vollhafter"),
		("9794", "9794", "Gegenkonto Anteil Rücklagen Vollhafter"),
		("9795", "9795", "Anteil Rücklagen variables Kapitalkonto Teilhafter"),
		("9796", "9796", "Anteil Rücklagen Kapitalkonto III Teilhafter"),
		("9797", "9797", "Anteil Rücklagen Verlustausgleichskonto Teilhafter"),
		("9798", "9798", "Gegenkonto Anteil Rücklagen Teilhafter"),
	),
	_watched(
		Reason.PARTNERSHIP,
		("9802", "9802", "Gesamthänderisch gebundene Rücklagen - andere Kapitalkontenanpassungen"),
		("9803", None, "Gewinnvortrag/Verlustvortrag - andere Kapitalkonten-"),
		(None, "9803", "Gewinnvortrag/Verlustvortrag andere Kapitalkontenanpassungen"),
		("9804", "9804", "Gesamthänderisch gebundene Rücklagen - Umbuchungen"),
		("9805", "9805", "Gewinnvortrag/Verlustvortrag - Umbuchungen"),
		("9806", "9806", "Zuzurechnender Anteil am Jahresüberschuss/Jahresfehlbetrag - je Gesellschafter"),
		("9807", "9807", "Zuzurechnender Anteil am Bilanzgewinn/Bilanzverlust - je Gesellschafter"),
		("9808", "9808", "Gegenkonto für zuzurechnenden Anteil am Jahresüberschuss/Jahresfehlbetrag"),
		("9809", "9809", "Gegenkonto für zuzurechnenden Anteil am Bilanzgewinn/Bilanzverlust"),
		("9810", "9810", "Kapitalkonto III"),
		("9820", "9820", "Verlust-/Vortragskonto"),
		("9830", "9830", "Verrechnungskonto für Einzahlungsverpflichtungen"),
		("9840", "9840", "Kapitalkonto III"),
		("9850", "9850", "Verrechnungskonto für Einzahlungsverpflichtungen"),
		("9860", "9860", "Einzahlungsverpflichtungen persönlich haftender Gesellschafter (Vollhafter)"),
		("9870", "9870", "Einzahlungsverpflichtungen Kommanditisten (Teilhafter)"),
		("9880", "9880", "Ausgleichsposten für aktivierte eigene Anteile"),
		(
			"9883",
			"9883",
			"Nicht durch Vermögenseinlagen gedeckte Entnahmen persönlich haftender Gesellschafter",
		),
		("9884", "9884", "Nicht durch Vermögenseinlagen gedeckte Entnahmen Kommanditisten"),
		(
			"9885",
			"9885",
			"Verrechnungskonto für nicht durch Vermögenseinlagen gedeckte Entnahmen persönlich haftender Gesellschafter",
		),
		(
			"9886",
			"9886",
			"Verrechnungskonto für nicht durch Vermögenseinlagen gedeckte Entnahmen Kommanditisten",
		),
	),
	_outside(
		Outside.STATISTICAL,
		("9887", "9887", "Steueraufwand der Gesellschafter"),
		("9889", "9889", "Gegenkonto zu 9887"),
		("9890", "9890", "Statistisches Konto für den Gewinnzuschlag nach §§ 6b Abs. 7 und 6c EStG (Haben)"),
		("9891", "9891", "Gegenkonto zu statistischen Konten für den Gewinnzuschlag (Soll)"),
		("9892", None, "Veränderung der gesamthänderisch gebundenen Rücklagen (Einlagen/Entnahmen"),
		(None, "9892", "Veränderung der gesamthänderisch gebundenen Rücklagen (Einlagen/Entnahmen)"),
		("9893", "9893", "Umsatzsteuer in den Forderungen zum allgemeinen Umsatzsteuersatz (EÜR)"),
		("9894", "9894", "Umsatzsteuer in den Forderungen zum ermäßigten Umsatzsteuersatz (EÜR)"),
		("9895", "9895", "Gegenkonto 9893-9894 für die Aufteilung der Umsatzsteuer (EÜR)"),
		("9896", "9896", "Vorsteuer in den Verbindlichkeiten zum allgemeinen Umsatzsteuersatz (EÜR)"),
		("9897", "9897", "Vorsteuer in den Verbindlichkeiten zum ermäßigten Umsatzsteuersatz (EÜR)"),
		("9898", "9898", "Vorsteuer in den Verbindlichkeiten aus verschiedenen Kosten (EÜR)"),
		("9899", "9899", "Gegenkonto 9896-9897 für die Aufteilung der Vorsteuer (EÜR)"),
		("9900", "9900", "Umsatzsteuer nicht fällig - sonstige Erlöse (EÜR)"),
		("9901", "9901", "Gegenkonto zu 9900"),
		("9902", "9902", "Umsatzsteuer in den Forderungen aus sonstigen Erlösen (EÜR)"),
		("9906", "9906", "Steuerfreie Einnahmen und Entnahmen nach § 3 Nr. 72 EStG (Soll)"),
		("9907", "9907", "Gegenkonto zu steuerfreien Einnahmen und Entnahmen nach § 3 Nr. 72 EStG (Haben)"),
		(
			"9908",
			"9908",
			"Nicht abzugsfähige Betriebsausgaben nach § 3c Abs. 1 EStG i. V. m. § 3 Nr. 72 EStG (Haben)",
		),
		(
			"9909",
			"9909",
			"Gegenkonto zu nicht abzugsfähigen Betriebsausgaben nach § 3c Abs. 1 EStG i. V. m. § 3 Nr. 72 EStG (Soll)",
		),
		("9910", "9910", "Gegenkonto zur Minderung der Entnahmen § 4 Abs. 4a EStG"),
		("9911", "9911", "Minderung der Entnahmen § 4 Abs. 4a EStG (Haben)"),
		("9912", "9912", "Erhöhung der Entnahmen § 4 Abs. 4a EStG"),
		("9913", "9913", "Gegenkonto zur Erhöhung der Entnahmen § 4 Abs. 4a EStG (Haben)"),
		(
			"9916",
			"9916",
			"Hinzurechnung Investitionsabzugsbetrag § 7g Abs. 2 EStG aus dem 2. vorangegangenen Wirtschaftsjahr, außerbilanziell (Haben)",
		),
		(
			"9917",
			"9917",
			"Hinzurechnung Investitionsabzugsbetrag § 7g Abs. 2 EStG aus dem 3. vorangegangenen Wirtschaftsjahr, außerbilanziell (Haben)",
		),
		(
			"9918",
			"9918",
			"Rückgängigmachung Investitionsabzugsbetrag § 7g Abs. 3 und 4 EStG im 2. vorangegangenen Wirtschaftsjahr",
		),
		(
			"9919",
			"9919",
			"Rückgängigmachung Investitionsabzugsbetrag § 7g Abs. 3 und 4 EStG im 3. vorangegangenen Wirtschaftsjahr",
		),
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		(
			"9960",
			"9960",
			"Bewertungskorrektur zu Forderungen aus Lieferungen und Leistungen (Währungsumrechnung)",
		),
		reason=Reason.VALUATION_CORRECTION,
	),
	_position(
		"bs.eqLiab.liab.other.other",
		("9961", "9961", "Bewertungskorrektur zu sonstigen Verbindlichkeiten (Währungsumrechnung)"),
		reason=Reason.VALUATION_CORRECTION,
	),
	_position(
		"bs.ass.currAss.cashEquiv.bank",
		(
			"9962",
			"9962",
			"Bewertungskorrektur zu Guthaben bei Kreditinstituten (Bewertung Finanzmittelfonds)",
		),
		reason=Reason.VALUATION_CORRECTION,
	),
	_position(
		"bs.eqLiab.liab.bank.other",
		(
			"9963",
			"9963",
			"Bewertungskorrektur zu Verbindlichkeiten gegenüber Kreditinstituten (Bewertung Finanzmittelfonds)",
		),
		reason=Reason.VALUATION_CORRECTION,
	),
	_position(
		"bs.eqLiab.liab.trade.genOther",
		(
			"9964",
			"9964",
			"Bewertungskorrektur zu Verbindlichkeiten aus Lieferungen und Leistungen (Währungsumrechnung)",
		),
		reason=Reason.VALUATION_CORRECTION,
	),
	_position(
		"bs.ass.currAss.receiv.other.other",
		("9965", "9965", "Bewertungskorrektur zu sonstigen Vermögensgegenständen (Währungsumrechnung)"),
		reason=Reason.VALUATION_CORRECTION,
	),
	_outside(
		Outside.STATISTICAL,
		("9970", "9970", "Investitionsabzugsbetrag § 7g Abs. 1 EStG, außerbilanziell (Soll)"),
		(
			"9971",
			"9971",
			"Investitionsabzugsbetrag § 7g Abs. 1 EStG, außerbilanziell (Haben) - Gegenkonto zu 9970",
		),
		(
			"9972",
			"9972",
			"Hinzurechnung Investitionsabzugsbetrag § 7g Abs. 2 EStG aus dem vorangegangenen Wirtschaftsjahr, außerbilanziell (Haben)",
		),
		(
			"9973",
			None,
			"Hinzurechnung Investitionsabzugsbetrag § 7g Abs. 2 EStG aus den vorangegangenen Wirtschaftsjahren, außerbilanziell (Soll) - Gegenkonto zu 9972, 9916, 9917",
		),
		(
			None,
			"9973",
			"Hinzurechnung Investitionsabzugsbetrag § 7g Abs. 2 EStG aus den vorangegangenen Wirtschaftsjahren, außerbilanziell (Soll) - Gegenkonto zu 9972, 9916,",
		),
		(
			"9974",
			"9974",
			"Rückgängigmachung Investitionsabzugsbetrag § 7g Abs. 3 und 4 EStG im vorangegangenen Wirtschaftsjahr",
		),
		(
			"9975",
			None,
			"Rückgängigmachung Investitionsabzugsbetrag § 7g Abs. 3 und 4 EStG in den vorangegangenen Wirtschaftsjahren - Gegenkonto zu 9974, 9918, 9919",
		),
		(
			None,
			"9975",
			"Rückgängigmachung Investitionsabzugsbetrag § 7g Abs. 3 und 4 EStG in den vorangegangenen Wirtschaftsjahren - Gegenkonto zu 9974, 9918,",
		),
		("9976", "9976", "Nicht abzugsfähige Zinsaufwendungen nach § 4h EStG (Haben)"),
		("9977", "9977", "Nicht abzugsfähige Zinsaufwendungen nach § 4h EStG (Soll) - Gegenkonto zu 9976"),
		("9978", "9978", "Abziehbare Zinsaufwendungen aus Vorjahren nach § 4h EStG (Soll)"),
		(
			"9979",
			"9979",
			"Abziehbare Zinsaufwendungen aus Vorjahren nach § 4h EStG (Haben) - Gegenkonto zu 9978",
		),
		("9980", "9980", "Anteil Belastung auf Verbindlichkeitskonten"),
		("9981", "9981", "Verrechnungskonto für Anteil Belastung auf Verbindlichkeitskonten"),
		("9982", "9982", "Anteil Gutschrift auf Verbindlichkeitskonten"),
		("9983", "9983", "Verrechnungskonto für Anteil Gutschrift auf Verbindlichkeitskonten"),
		("9984", "9984", "Gewinnkorrektur nach § 60 Abs. 2 EStDV - Erhöhung handelsrechtliches"),
		("9985", "9985", "Gegenkonto zu 9984"),
		("9986", "9986", "Ergebnisverteilung auf Fremdkapital"),
		("9987", "9987", "Korrekturkonto für die Überleitungsrechnung"),
		("9989", "9989", "Gegenkonto zu 9986-9988"),
		("9990", "9990", "Erträge von außergewöhnlicher Größenordnung oder Bedeutung"),
		("9991", "9991", "Erträge (aperiodisch)"),
		("9992", "9992", "Erträge von außergewöhnlicher Größenordnung oder Bedeutung (aperiodisch)"),
		("9993", "9993", "Aufwendungen von außergewöhnlicher Größenordnung oder Bedeutung"),
		("9994", "9994", "Aufwendungen (aperiodisch)"),
		("9995", "9995", "Aufwendungen von außergewöhnlicher Größenordnung oder Bedeutung (aperiodisch)"),
		("9998", "9998", "Gegenkonto zu 9990-9997"),
	),
	_position(
		"bs.ass.currAss.receiv.trade.other",
		(None, "10000", "Debitoren"),
		opposite="bs.eqLiab.liab.other.other",
		reason=Reason.BOTH_SIDES,
	),
	_position(
		"bs.eqLiab.liab.trade.genOther",
		(None, "70001", "Wareneingangs-Verrechnungskonto"),
		opposite="bs.ass.currAss.receiv.other.other",
		reason=Reason.RECEIVED_NOT_BILLED,
	),
)

GROUPS: MappingProxyType[str, tuple[Group, ...]] = MappingProxyType({"6.9": _GROUPS_6_9})
"""The groups of the defaults for each version of the taxonomy, whose positions they name."""


def _defaults(chart: str, version: str) -> Defaults:
	entries = [entry for group in GROUPS[version] for entry in group.entries(chart)]
	return Defaults(
		chart,
		version,
		rules=tuple(entry for entry in entries if isinstance(entry, DefaultRule)),
		watched=tuple(entry for entry in entries if isinstance(entry, DefaultWatched)),
		excluded=tuple(entry for entry in entries if isinstance(entry, DefaultExcluded)),
	)


DEFAULTS: MappingProxyType[str, MappingProxyType[str, Defaults]] = MappingProxyType(
	{
		version: MappingProxyType({chart: _defaults(chart, version) for chart in sorted(CHARTS)})
		for version in GROUPS
	}
)
REVISIONS: MappingProxyType[str, int] = MappingProxyType({"6.9": 1})


def defaults_for(chart: str, version: str) -> Defaults:
	"""The defaults of a chart for a version of the taxonomy."""
	if version not in DEFAULTS:
		raise KeyError(f"no defaults of the Bilanzzuordnung for the HGB-Taxonomie {version}")
	try:
		return DEFAULTS[version][chart]
	except KeyError:
		known = ", ".join(sorted(CHARTS))
		raise KeyError(
			f"no defaults of the Bilanzzuordnung for chart {chart!r}; known charts: {known}"
		) from None


def defaults_version(chart: str, version: str) -> str:
	"""The version of the defaults of a chart for a version of the taxonomy, such as SKR03 Taxonomie 6.9 2026.1."""
	defaults_for(chart, version)
	return f"{chart} Taxonomie {version} {DATEV_EDITION}.{REVISIONS[version]}"
