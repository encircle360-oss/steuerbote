"""The Körperschaftsteuererklärung of a company in ERPNext and the core of steuerbote.kst, converted without Frappe.

The Corporate Income Tax Return keeps what the core takes and what it computed in rows with the field names of its
DocTypes; this module turns the one into the other, so that the controller only reads and stores, and every rule is
tested without a bench. The forms are those of steuerbote.kst.form, for 2026 provisionally those of
Jahresdokumentation_E30_2025.ods of the ERiC documentation 44.3.6.0 (steuerbote.kst.years).

What the core takes (compute):
- the ledger of the Wirtschaftsjahr (Ledger): the postings of the accounts of the profit and loss account that have a
  number, which classify() of steuerbote.kst.categories sorts by the Income Tax Mapping, and the Jahresüberschuss of
  all of them, Anlage GK line 11 before the Überleitung to the Steuerbilanz. Without an E-Bilanz the Überleitung comes
  by hand: the ledger with a manual reconciliation, adopted answer Q2 of the research of stage 3;
- the E-Bilanz of the Wirtschaftsjahr the return names (EBilanz), contract of stage 3, 3.3: „GK 11 from the
  E-Bilanz (is.netIncome ± Überleitung)“. Line 11 is then the Jahresüberschuss of its GuV, under HGBM that of the
  Handelsbilanz, and the Überleitung to the Jahresüberschuss of its Steuerbilanz a ManualLine of the step net_income
  (ueberleitung_lines), as the form takes line 11 „bei Handelsbilanz: nach Berücksichtigung der
  Überleitungsrechnung nach § 5b Absatz 1 Satz 2 EStG beziehungsweise § 60 Absatz 2 EStDV“
  (Jahresdokumentation_E30_2025.ods, sheet „GK - Felder“, E8002001); an Einheitsbilanz (HAOE) and a Steuerbilanz (AO)
  have no Überleitung. The filed E-Bilanz of the previous Wirtschaftsjahr (PriorEBilanz) gives KSt 1 F lines 17 and
  18, the Eigenkapital laut Steuerbilanz and the Nennkapital at its end (§ 27 Absatz 1 Satz 5 KStG), which the return
  else states by hand (previous_equity);
- the lines of the return: a line by hand is a ManualLine of its step (steuerbote.kst.chain), such as the Überleitung
  of line 11 or a verdeckte Gewinnausschüttung of line 75 (§ 8 Absatz 3 Satz 2 KStG); a correction of a line files
  another amount, which the core takes as the ManualLine of the difference, so that the sums of the form add it. Only
  the lines of the books and the lines left to hand take one (CORRECTABLE); every other line follows from them, from
  the tables of the return or from the settings, and a correction there would leave the sums of the form behind;
- the tables of the return: the dividends of the holdings with their costs (§ 8b Absatz 1 and 4 KStG), the sales,
  write-ups and write-downs of shares, whose single values Anlage GK lines 161 to 187 declare (HOLDING_KINDS), the
  Steuerbescheinigungen (Anlage WA lines 2 and 3, § 36 Absatz 2 Nummer 2 EStG), the Zuwendungsbestätigungen (Anlage
  Z line 5, § 9 Absatz 1 Nummer 2 KStG), the Leistungen of the Wirtschaftsjahr (KSt 1 F lines 3 to 13) and the
  Einlagen (Anlage GK lines 78, 93 and 94, § 8 Absatz 3 Satz 3 to 6 KStG; KSt 1 F lines 91, 92, 95 and 200 to 206);
- the Annual Filing Settings (Settings): the flag of § 8b Absatz 7 KStG, the holdings register, the Vorauszahlungen of
  the notices, which the core takes rather than the ledger (adopted Q6), and the carry-forwards of the last notices
  at the end of the previous Wirtschaftsjahr (§ 10d EStG, § 15 Absatz 4 EStG, Zuwendungen, Einlagekonto and
  Sonderausweis of §§ 27 and 28 KStG), which count once confirmed against their notice.

The Verlustrücktrag counts only for a loss: steuerbote.kst.losses refuses one for a positive Gesamtbetrag der
Einkünfte, so compute() asks the core first without it and takes it only where the year has a loss.

What the return keeps: line_rows() makes a row of the table of lines of each amount of the Vordrucke that
steuerbote.kst.form gives for the result, GK, ZVE, WA, Verluste, Z and KSt 1 F, by its Feldkennung, with the form,
the line and the Beschreibung of its field, which the Jahresdokumentation also prints as its Drucktext, and the amount
of the books of a line of the books beside it. filed_vordrucke() makes the Vordrucke again from the rows as stored,
with what the computation does not know (KSt 1 from the settings, the single values of the tables, Anlage WA line 15),
for the Nutzdaten of steuerbote.elster.kst_xml and for the check of the rules of the Jahresdokumentation that
Steuerbote checks itself (rule_findings, the rules of steuerbote.eric.simulation.kst).

What holds the return back, beside the findings of the core (findings_of): the forms of a provisional VZ, missing or
incomplete settings, shareholders that do not hold 99 to 100 % on a day of the Wirtschaftsjahr (rule 8931029 of the
KSt 1), a carry-forward that is not confirmed or not in whole euros, an Überleitung missing where the settings or the
E-Bilanz keep a Handelsbilanz with Überleitungsrechnung, an E-Bilanz whose Jahresüberschuss is not that of the books
the return reads, an Überleitung from the E-Bilanz with another by hand beside it (ebilanz_findings), an account of the
books with a balance that the defaults of its chart give a place for and the mapping of the company does not, an
account of the profit and loss account without a number, Zuwendungen without their receipts, § 8b results of the
books without their single values, the dividends of a holding the register does not name, and a Verlustrücktrag
without a loss. A hint names Vorauszahlungen of the settings that differ from those booked, Kapitalertragsteuer of
the Steuerbescheinigungen that differs from that booked, receipts of Zuwendungen that differ from the books, contracts
with shareholders whose single values Steuerbote does not file, the Jahresüberschuss of an E-Bilanz that reads another
finance book than the return, and where KSt 1 F lines 17 and 18 come from (equity_findings).

The texts are templates in English with their values apart (MESSAGES, LABELS), which the Frappe layer translates; the
findings of the core are German already.

This module is pure Python and never imports Frappe.
"""

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Any
from xml.etree import ElementTree

from steuerbote.elster import kst_xml
from steuerbote.elster.erklaerung import Field
from steuerbote.elster.ustva_xml import XmlError
from steuerbote.elster.vorsatz import Vorsatz
from steuerbote.eric.datenart import kst as kst_datenart
from steuerbote.eric.simulation import kst as kst_rules
from steuerbote.jahresmeldung.findings import Finding, Severity
from steuerbote.jahresmeldung.overrides import Columns, correction_of, to_amount
from steuerbote.kst import chain
from steuerbote.kst.categories import Category, classify
from steuerbote.kst.categories import Mapping as IncomeTaxMapping
from steuerbote.kst.chain import STEPS, KstInputs, KstResult, ManualLine, Source
from steuerbote.kst.defaults import NON_DEDUCTIBLE_DONATIONS, default_accounts
from steuerbote.kst.einlagekonto import Einlagekonto, roll_forward
from steuerbote.kst.form import (
	CERTIFIED_REDUCTION,
	DIRECT,
	HOLDING_DIVIDENDS,
	HOLDING_KIND,
	HOLDING_NAME,
	HOLDING_SHARE,
	INDEXED,
	STEP_FIELDS,
	WJ,
	Entry,
	Vordruck,
	catalogue_for,
	kst1f,
	vordrucke,
)
from steuerbote.kst.holdings import Exemption, Holding, HoldingResult, exemption
from steuerbote.kst.provisions import ProvisionAccounts
from steuerbote.kst.years import year_of
from steuerbote.setup import start
from steuerbote.steuerbote.doctype.annual_filing_settings import rules
from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import ZERO, floor_euro, half_up_euro

type Row = Mapping[str, Any]
type Translate = Callable[[str], str]

LINE_COLUMNS = Columns(
	key="feldkennung",
	amounts=("form_amount", "ledger_amount"),
	described=("form", "line", "label"),
)
"""The columns of the table of lines: the Feldkennung is the key, the amount of the form what the line files without a
correction, the amount of the books what the ledger gives a line of the books before its corrections."""

FORMS_OF_LINES = ("GK", "ZVE", "WA", "Verluste", "Z", "KSt1F")
"""The Vordrucke whose amounts the table of lines holds."""
_BOOKS = frozenset({Source.NET_INCOME, Source.LEDGER})

PAID, UNPAID, NOT_BOOKED, OTHER = (
	"Booked to Profit and Paid",
	"Booked to Profit, Not Paid",
	"Not Booked to Profit",
	"Other Contribution",
)
CONTRIBUTION_STEPS = MappingProxyType(
	{PAID: "contributions_paid", UNPAID: "contributions_unpaid", NOT_BOOKED: "contributions_not_booked"}
)
"""The treatments of an Einlage by the step of Anlage GK it goes to: lines 93, 94 and 78. An Einlage of another kind,
such as a payment into the Kapitalrücklage, changes no income and counts in KSt 1 F line 95 alone."""
CONTRIBUTION_TREATMENTS = (PAID, UNPAID, NOT_BOOKED, OTHER)
CASH, IN_KIND = "Cash Contribution", "Contribution in Kind"
CONTRIBUTION_KINDS = MappingProxyType({CASH: "1", IN_KIND: "2"})
"""The kind of an Einlage as KSt 1 F line 205 (E8241515) writes it: 1 Bareinlage, 2 Sacheinlage."""

CORRECTABLE = frozenset(
	step.key
	for step in STEPS
	if step.source in (Source.NET_INCOME, Source.LEDGER, Source.MANUAL)
	and step.key not in CONTRIBUTION_STEPS.values()
)
"""The steps whose line takes a correction or a line by hand: the lines of the books and those the computation leaves
to hand. The Einlagen of lines 78, 93 and 94 come from the table of Einlagen, which also gives KSt 1 F."""
CORRECTABLE_FIELDS = MappingProxyType({STEP_FIELDS[key]: key for key in sorted(CORRECTABLE)})
"""The Feldkennungen of the correctable steps, with the key of their step."""
WHOLE_EUROS = frozenset({"N", "U", "G", "M"})
"""The Formatkennzeichen of whole euros (steuerbote.elster.erklaerung.FORMATS)."""
ZERO_REFUSED = frozenset({"G", "M", "R", "S"})
"""The Formatkennzeichen that take no zero: a field of them is left out at zero."""
YEAR_PLACEHOLDER = re.compile(r"\$VZ(?:([+-])([0-9]+))?\$")
"""The year of the return in a Beschreibung of the Jahresdokumentation, $VZ$, or a year before or after it, such as
$VZ-1$ in „im Wirtschaftsjahr $VZ-1$/$VZ$“."""

DIVIDENDS, SALE, WRITE_UP, WRITE_DOWN = ("Dividends", "Sale", "Write-up", "Write-down")
HOLDING_KINDS = (DIVIDENDS, SALE, WRITE_UP, WRITE_DOWN)
"""The kinds of a row of the § 8b results: the dividends of a holding of the register, and each sale, write-up and
write-down of shares, as Anlage GK lines 162 to 166a, 167b to 167c and 185 to 186 declare them. A sale names its price,
its costs and the book value of the shares, whose difference is its gain or its loss (sale_result): Anlage GK takes
them together (rules 8956041, 8906032 and 8906419)."""
GAIN, LOSS = "gain", "loss"
"""A sale by its result, as the lines of Anlage GK that sum single values tell them apart."""
EXEMPTIONS = MappingProxyType(
	{
		Exemption.EXEMPT: "§ 8b Abs. 1 KStG",
		Exemption.STREUBESITZ: "Streubesitz",
		Exemption.TRADING_BOOK: "§ 8b Abs. 7 KStG",
	}
)
"""What § 8b KStG makes of the dividends of a holding, as the column exemption shows it."""
SINGLE_VALUES = MappingProxyType(
	{"p8b_gains": GAIN, "p8b_losses": LOSS, "p8b_writeups": WRITE_UP, "p8b_writedowns": WRITE_DOWN}
)
"""The § 8b lines of Anlage GK that sum single values, by their step and the rows that give them, the sales with a gain,
those with a loss, the write-ups and the write-downs: lines 166b, 166c, 176 and 188 (rules 8956070, 8956072, 8905507
and 8905516)."""

ORDINARY = "Ordinary Distribution"
DISTRIBUTION_KINDS = MappingProxyType({ORDINARY: "1", "Hidden Distribution": "2", "Liquidation Advance": "3"})
"""The Art der Leistung of KSt 1 F line 3 (E8122020) by the option of the table of Leistungen: 1 a Gewinnausschüttung
on an ordinary resolution, 2 a verdeckte Gewinnausschüttung, 3 an advance on the result of a liquidation
(Jahresdokumentation_E30_2025.ods, sheet „KSt1F - Felder“). A GmbH or UG pays no Leistung of § 20 Absatz 1 Nummer 9
and 10 Buchstabe a EStG (4, rule 8920316) and is no company that opted under § 1a KStG (5, rule 8920051)."""

INLAND, ABROAD = "1", "2"
"""Where the recipient of a Zuwendung lies, Anlage Z line 5 (E8005605) and GewSt 1 A line 92c (E4009222): 1 in
Germany, 2 in the EU or EEA abroad."""
SUPPLEMENT_KEYS = ("1", "2", "3", "4")
"""The keys of the qualified free text of § 150 Absatz 7 Satz 1 AO in KSt 1 line 13 (E8001305), filed with its text
(E8001304) or not at all (rule 8900735)."""
HGB_WITH_RECONCILIATION = "HGBM"
"""The Bilanzierungsstandard of a Handelsbilanz with Überleitungsrechnung (Annual Filing Settings), whose Anlage GK
line 11 needs the Überleitung to the Steuerbilanz (§ 60 Absatz 2 Satz 1 EStDV)."""
WHOLE_EURO = Decimal("1")
"""Anlage GK line 11 files whole euros, so a Jahresüberschuss of the E-Bilanz less than a euro off that of the books
changes no more than its rounding."""
NET_INCOME_LINE = "Anlage GK Zeile 11"
PRIOR_EQUITY_LINES = "KSt 1 F Zeilen 17 und 18"
SHARES_ON_EACH_DAY = (Decimal(99), Decimal(100))
"""Rule 8931029 of the KSt 1: on each day the shares of the Anteilseigner add up to 99 to 100 %."""
TAXES = ("KSt", "SolZ")
"""The taxes of the Vorauszahlungen of the Körperschaftsteuererklärung, as the Annual Filing Settings name them."""
TAX_KEYS = ("KSt", "SolZ", "GewSt")
"""The taxes of the Vorauszahlungen of the Annual Filing Settings, in the order of steuerbote.kst.provisions."""
CARRY_FORWARDS = MappingProxyType(
	{
		"loss_carry_forward": rules.CarryForwardKind.LOSS,
		"derivatives_carry_forward": rules.CarryForwardKind.TERMINGESCHAEFTE,
		"donation_carry_forward": rules.CarryForwardKind.DONATIONS_KST,
		"einlagekonto": rules.CarryForwardKind.EINLAGEKONTO,
		"sonderausweis": rules.CarryForwardKind.SONDERAUSWEIS,
	}
)
"""The carry-forwards of the Körperschaftsteuer at the end of the previous Wirtschaftsjahr, by what takes them: the
first three KstInputs, the last two steuerbote.kst.einlagekonto."""

# KSt 1, by the Feldkennungen of Jahresdokumentation_E30_2025.ods, sheet „KSt1 - Felder“.
EINLAGEKONTO_DECLARED = "E8000016"
COMPANY_NAME, WID_NR = "E8000101", "E8000102"
MANAGEMENT_SEAT, REGISTERED_SEAT, RECHTSFORM = "E8000501", "E8000601", "E8001105"
SUPPLEMENT_KEY, SUPPLEMENT_TEXT = "E8001305", "E8001304"
WJ_FROM, WJ_TO, FOUNDED = "E8002606", "E8002607", "E8000703"
TRADING_BOOK, SECTION_8_9, SHAREHOLDERS_CHANGED = "E8001008", "E8001007", "E8122601"
SHAREHOLDER_NAME, SHAREHOLDER_STREET, SHAREHOLDER_TOWN = "E8122101", "E8122102", "E8122103"
SHAREHOLDER_DATA_CHANGED = "E8122111"
SHAREHOLDER_TAX_NUMBER, SHAREHOLDER_IDNR, SHAREHOLDER_WID_NR, SHAREHOLDER_FOREIGN_ID = (
	"E8122109",
	"E8122110",
	"E8122112",
	"E8122113",
)
SHARE_EUROS, SHARE_PERCENT, SHARE_FROM, SHARE_TO = "E8122104", "E8122105", "E8122106", "E8122107"
ADVISOR = "E8001901"
ADVISOR_FIELDS = MappingProxyType(
	{
		"phone": "E8019914",
		"name": "E8019910",
		"first_name": "E8019911",
		"street": "E8019912",
		"town": "E8019913",
		"details": "E8019915",
		"client_number": "E8019916",
		"clerk": "E8019918",
	}
)
"""The Steuerberatung of KSt 1 lines 100a to 102, by the attribute of Advisor that holds each."""
IDENTIFIERS = frozenset(
	{SHAREHOLDER_TAX_NUMBER, SHAREHOLDER_IDNR, SHAREHOLDER_WID_NR, SHAREHOLDER_FOREIGN_ID}
)
"""The numbers of the Anteilseigner, which go to ELSTER and into no print: a body other than the Finanzbehörde may
process the Identifikationsnummer only as far as a transmission to it needs it (§ 139b Absatz 2 Satz 2 Nummer 1 AO)."""
MOST_SHARE_PERIODS = 3
"""KSt1/AE/Einzel/Besitzdauer repeats at most three times (E30-2025.xsd)."""
# Anlage GK lines 162 to 166a, 167b to 167c and 185 to 186.
SALE_NAME, SALE_DATE, SALE_GAIN_FIELD, SALE_LOSS_FIELD = "E8561202", "E8561213", "E8561211", "E8561403"
SALE_PRICE, SALE_COSTS, BOOK_VALUE = "E8561204", "E8561205", "E8561206"
WRITE_UP_NAME, WRITE_UP_FIELD = "E8561239", "E8561210"
WRITE_DOWN_NAME, WRITE_DOWN_FIELD = "E8561402", "E8561408"
# Anlage WA line 15 and Anlage Z line 5.
SHAREHOLDER_CONTRACTS = "E8122801"
DONATION_RECIPIENT, DONATION_AMOUNT, DONATION_ABROAD = "E8005603", "E8005604", "E8005605"
DONATIONS_ABROAD = "E8009601"
# KSt 1 F lines 3 to 13 and 200 to 206.
DISTRIBUTION_KIND, DISTRIBUTION_RESOLVED, DISTRIBUTION_OUTFLOW = "E8122020", "E8122021", "E8122022"
DISTRIBUTION_AMOUNT, DISTRIBUTION_CERTIFIED = "E8122023", "E8122024"
DISTRIBUTIONS_TOTAL, SEVERAL_CERTIFIED = "E8121406", "E8122011"
CONTRIBUTION_NAME, CONTRIBUTION_DATE, CONTRIBUTION_KIND, CONTRIBUTION_DESCRIPTION = (
	"E8241510",
	"E8241514",
	"E8241515",
	"E8241516",
)

# The rules of the Vordrucke never read the Vorsatz (steuerbote.eric.simulation.kst.Erklaerung leaves it out), and the
# Nutzdaten cannot be written without one, so the check of the rules writes them with this one.
FOR_THE_RULES = Vorsatz("9999099999999", "Steuerbote", "Steuerbote", "Steuerbote", "Steuerbote")

PROVISIONAL = "KST-VORLAEUFIG"
NO_SETTINGS = "KST-EINSTELLUNGEN-FEHLEN"
DETAILS_MISSING = "KST-ANGABEN-FEHLEN"
SHARES = "KST-ANTEILSEIGNER"
UNCONFIRMED = "KST-VORTRAG-UNBESTAETIGT"
NOT_IN_EUROS = "KST-VORTRAG-CENT"
CARRY_FORWARD_MISSING = "KST-VORTRAG-FEHLT"
NO_UEBERLEITUNG = "KST-UEBERLEITUNG-FEHLT"
UNMAPPED = "KST-KONTO-OHNE-ZUORDNUNG"
UNNUMBERED = "KST-KONTO-OHNE-NUMMER"
PREPAYMENTS = "KST-VORAUSZAHLUNGEN"
CAPITAL_GAINS_TAX = "KST-KAPEST"
NO_RECEIPTS = "KST-ZUWENDUNGEN-BESTAETIGUNG"
RECEIPTS_DIFFER = "KST-ZUWENDUNGEN-ABWEICHUNG"
NO_SINGLE_VALUES = "KST-8B-EINZELANGABEN"
UNKNOWN_HOLDING = "KST-BETEILIGUNG-UNBEKANNT"
CARRY_BACK_WITHOUT_LOSS = "KST-VERLUSTRUECKTRAG-OHNE-VERLUST"
CONTRACTS = "KST-WA-VERTRAEGE"
NUTZDATEN = "KST-NUTZDATEN"
NOT_REVIEWED = "KST-PRUEFUNG-FEHLT"
PERIODS = "KST-BESITZDAUER"
EBILANZ_DIFFERS = "KST-EBILANZ-ABWEICHUNG"
UEBERLEITUNG_TWICE = "KST-UEBERLEITUNG-DOPPELT"
EQUITY_SOURCE = "KST-EIGENKAPITAL-QUELLE"
CODES = (
	PROVISIONAL,
	NO_SETTINGS,
	DETAILS_MISSING,
	SHARES,
	UNCONFIRMED,
	NOT_IN_EUROS,
	NO_UEBERLEITUNG,
	UNMAPPED,
	UNNUMBERED,
	PREPAYMENTS,
	CAPITAL_GAINS_TAX,
	NO_RECEIPTS,
	RECEIPTS_DIFFER,
	NO_SINGLE_VALUES,
	UNKNOWN_HOLDING,
	CARRY_BACK_WITHOUT_LOSS,
	CONTRACTS,
	NUTZDATEN,
	NOT_REVIEWED,
	PERIODS,
	EBILANZ_DIFFERS,
	UEBERLEITUNG_TWICE,
	EQUITY_SOURCE,
)
"""The codes of the findings of this module, beside those of the core and the Fehlercodes of the rules."""

PROVISIONAL_TEXT = (
	"Steuerbote has the forms of {0} provisionally from the Jahresdokumentation {1}: until ELSTER publishes those of "
	"{0}, the return is not ready. A filing needs this error acknowledged with the reason why it goes nonetheless."
)
NO_SETTINGS_TEXT = (
	"The company has no Annual Filing Settings, which give the Rechtsform, the seats and the shareholders."
)
DETAILS_MISSING_TEXT = "The Annual Filing Settings of {0} lack what the return needs: {1}."
SHARES_TEXT = (
	"On {0} the shareholders of the Annual Filing Settings hold {1}; KSt 1 needs 99 to 100 % on every day of the "
	"Wirtschaftsjahr (rule 8931029)."
)
UNCONFIRMED_TEXT = (
	"{0} as of {1} in the Annual Filing Settings is not confirmed against its notice; the return takes only "
	"confirmed carry-forwards."
)
NOT_IN_EUROS_TEXT = "{0} as of {1} is {2}, not whole euros as a notice states it; the return takes {3}."
CARRY_FORWARD_MISSING_TEXT = (
	"{0} has no amount as of {1} in the Annual Filing Settings. In its first year in Steuerbote the return takes the "
	"carry-forwards of the last notice: enter it, 0 as well, and confirm it against the notice."
)
NO_UEBERLEITUNG_TEXT = (
	"The Annual Filing Settings keep a Handelsbilanz with Überleitungsrechnung, and line 11 of Anlage GK has no line by "
	"hand with the Überleitung to the Steuerbilanz. Add each step of it as a line by hand of E8002001 with its reason."
)
UNMAPPED_TEXT = (
	"Account {0} has a balance (debit {1}, credit {2}), and the defaults of {3} give it a place for the "
	"Körperschaftsteuer and the Gewerbesteuer, but the Income Tax Mapping of the company has no row for it."
)
UNNUMBERED_TEXT = (
	"Account {0} of the profit and loss account has a balance of {1} and no account number, so the Income Tax "
	"Mapping cannot place it."
)
PREPAYMENTS_TEXT = "The Vorauszahlungen {0} of the Annual Filing Settings come to {1}, those booked on the account of the tax to {2}."
CAPITAL_GAINS_TAX_TEXT = (
	"The Kapitalertragsteuer of the Steuerbescheinigungen comes to {0}, that booked as an expense to {1}."
)
NO_RECEIPTS_TEXT = (
	"The books hold deductible Zuwendungen of {0}, and the return lists no receipt. Enter each Zuwendungsbestätigung "
	"under Donations: Anlage Z line 5 and GewSt 1 A lines 92a to 92c name them."
)
RECEIPTS_DIFFER_TEXT = (
	"The receipts of the Zuwendungen come to {0}, the deductible Zuwendungen in the books to {1}."
)
NO_SINGLE_VALUES_TEXT = (
	"Anlage GK line {0} declares {1}, and the § 8b results list no single value of it. Enter each sale, write-up or "
	"write-down there with the company it concerns."
)
UNKNOWN_HOLDING_TEXT = (
	"The dividends of {0} name no holding of the Annual Filing Settings for {1}, so the share at the start of the "
	"calendar year of § 8b Absatz 4 KStG is unknown; enter the holding there."
)
CARRY_BACK_WITHOUT_LOSS_TEXT = "A Verlustrücktrag of {0} needs a loss, and the Gesamtbetrag der Einkünfte is {1}; the return leaves it out."
CONTRACTS_TEXT = (
	"Line 15 of Anlage WA says that contracts with shareholders were concluded or changed in the year; Steuerbote "
	"does not file the single values of line 16, which the Steuerberatung adds."
)
NUTZDATEN_TEXT = "The return cannot be written as ELSTER takes it: {0}"
NOT_REVIEWED_TEXT = (
	"The Annual Filing Settings name no day on which a Steuerberatung confirmed the classes of the trading accounts, "
	"the status under § 8b Abs. 7 KStG and the review list of the returns; the Körperschaft- and the "
	"Gewerbesteuererklärung wait for it."
)
PERIODS_TEXT = (
	"{0} holds shares in {1} periods of the Wirtschaftsjahr, and KSt 1 lines 23 to 23b take three of them."
)
UEBERLEITUNG_REASON = "Überleitungsrechnung of the E-Bilanz {0}"
EBILANZ_DIFFERS_TEXT = (
	"The Jahresüberschuss of the E-Bilanz {0} is {1}, that of the profit and loss account of the books {2}: a "
	"difference of {3}. After a posting such as that of the provisions, calculate the E-Bilanz again and then the "
	"return, so that line 11 of Anlage GK rests on the books its other lines come from."
)
EBILANZ_OTHER_BOOKS_TEXT = (
	"The E-Bilanz {0} reads another finance book than the return: its Jahresüberschuss is {1}, that of the profit and "
	"loss account the return reads {2}, a difference of {3}."
)
NO_UEBERLEITUNG_EBILANZ_TEXT = (
	"The E-Bilanz {0} is a Handelsbilanz with Überleitungsrechnung and has no entry of the Überleitung, so line 11 of "
	"Anlage GK takes the Jahresüberschuss of the Handelsbilanz as it is. Enter the Überleitung in the E-Bilanz, then "
	"calculate it and the return again."
)
UEBERLEITUNG_TWICE_TEXT = (
	"Line 11 of Anlage GK takes the Jahresüberschuss of the E-Bilanz {0} after its Überleitung, and the lines by hand "
	"and corrections of E8002001 would count beside it. Enter each step of the Überleitung in the E-Bilanz and take "
	"them out of the return."
)
EQUITY_FROM_EBILANZ_TEXT = (
	"KSt 1 F lines 17 and 18 take the Eigenkapital laut Steuerbilanz of {0} and the Nennkapital of {1} at the end of "
	"the previous Wirtschaftsjahr from the E-Bilanz {2} filed for {3}."
)
EQUITY_OVER_HAND_TEXT = (
	"KSt 1 F lines 17 and 18 take the Eigenkapital laut Steuerbilanz of {0} and the Nennkapital of {1} at the end of "
	"the previous Wirtschaftsjahr from the E-Bilanz {2} filed for {3}; the amounts by hand, {4} and {5}, do not count."
)
EQUITY_BY_HAND_TEXT = (
	"KSt 1 F lines 17 and 18 take the amounts by hand, {0} and {1}: no E-Bilanz of {2} is filed whose Steuerbilanz "
	"would give them."
)
NOT_CORRECTABLE = (
	"The line {0} follows from other lines, the tables of the return or the settings, so it takes no correction and no "
	"line by hand: correct those instead."
)
NOT_A_LINE = (
	"The return has no line {0} that takes a line by hand. Name the Feldkennung of a line of the books or of one "
	"the computation leaves to hand, such as E8002701 for a verdeckte Gewinnausschüttung."
)
NOT_WHOLE = "The line {0} files whole euros, not {1}."
NOT_AN_OPTION = "Row {1} of the {0}: {2} is no option."
NOT_POSITIVE = "Row {1} of the {0}: the amount is above zero."
ROW_NOT_IN_EUROS = "Row {1} of the {0}: the amount is whole euros."
ROW_NEGATIVE = "Row {1} of the {0}: {2} is not below zero."
REDUCTION_ABOVE_AMOUNT = (
	"Row {1} of the {0}: the certified reduction of the Einlagekonto is above the Leistung."
)
NO_DESCRIPTION = "Row {1} of the {0}: a contribution in kind needs its description."
SALE_WITHOUT_DAY = "Row {1} of the {0}: a sale needs its day."
SALE_WITHOUT_RESULT = (
	"Row {1} of the {0}: the price less the costs and the book value gives neither a gain nor a loss, which Anlage GK "
	"takes."
)
DAY_OUTSIDE = "Row {1} of the {0}: the {2} lies in the Wirtschaftsjahr, from {3} to {4}."
NO_RESOLUTION = (
	"Row {1} of the {0}: a Gewinnausschüttung on an ordinary resolution needs the date of the resolution."
)
OUTFLOW_BEFORE_RESOLUTION = "Row {1} of the {0}: the outflow lies before the resolution."
FIELD_NOT_IN_EUROS = "{0} is whole euros."
FIELD_NEGATIVE = "{0} is not below zero."
MESSAGES = (
	PROVISIONAL_TEXT,
	NO_SETTINGS_TEXT,
	DETAILS_MISSING_TEXT,
	SHARES_TEXT,
	UNCONFIRMED_TEXT,
	NOT_IN_EUROS_TEXT,
	CARRY_FORWARD_MISSING_TEXT,
	NO_UEBERLEITUNG_TEXT,
	UNMAPPED_TEXT,
	UNNUMBERED_TEXT,
	PREPAYMENTS_TEXT,
	CAPITAL_GAINS_TAX_TEXT,
	NO_RECEIPTS_TEXT,
	RECEIPTS_DIFFER_TEXT,
	NO_SINGLE_VALUES_TEXT,
	UNKNOWN_HOLDING_TEXT,
	CARRY_BACK_WITHOUT_LOSS_TEXT,
	CONTRACTS_TEXT,
	NUTZDATEN_TEXT,
	NOT_REVIEWED_TEXT,
	PERIODS_TEXT,
	UEBERLEITUNG_REASON,
	EBILANZ_DIFFERS_TEXT,
	EBILANZ_OTHER_BOOKS_TEXT,
	NO_UEBERLEITUNG_EBILANZ_TEXT,
	UEBERLEITUNG_TWICE_TEXT,
	EQUITY_FROM_EBILANZ_TEXT,
	EQUITY_OVER_HAND_TEXT,
	EQUITY_BY_HAND_TEXT,
	NOT_CORRECTABLE,
	NOT_A_LINE,
	NOT_WHOLE,
	NOT_AN_OPTION,
	NOT_POSITIVE,
	ROW_NOT_IN_EUROS,
	ROW_NEGATIVE,
	REDUCTION_ABOVE_AMOUNT,
	NO_DESCRIPTION,
	SALE_WITHOUT_DAY,
	SALE_WITHOUT_RESULT,
	DAY_OUTSIDE,
	NO_RESOLUTION,
	OUTFLOW_BEFORE_RESOLUTION,
	FIELD_NOT_IN_EUROS,
	FIELD_NEGATIVE,
)
"""Every text of this module, which the Frappe layer translates."""
LABELS = MappingProxyType(
	{
		"rechtsform": "Legal Form",
		"management_seat": "Place of Management",
		"registered_seat": "Registered Seat",
		"holding_results": "§ 8b results",
		"credits": "tax certificates",
		"donations": "donations",
		"distributions": "distributions",
		"contributions": "contributions",
		"financing_costs": "Related Costs under § 8 Nr. 1 GewStG (BEG Line 8)",
		"other_costs": "Other Related Costs (BEG Line 9)",
		"sale_price": "Sale Price",
		"sale_costs": "Sale Costs",
		"book_value": "Book Value",
		"outflow_date": "Date of the Outflow",
		"contribution_date": "Date of the Contribution",
		"capital_gains_tax": "Kapitalertragsteuer",
		"solz": "Solidaritätszuschlag",
		"loss_carry_back": "Verlustrücktrag",
		"turnover_and_wages": "Turnover, Wages and Salaries (Anlage Z Line 10)",
		"previous_equity": "Equity at the End of the Previous Wirtschaftsjahr (KSt 1 F Line 17)",
		"previous_nominal_capital": "Nennkapital at the End of the Previous Wirtschaftsjahr (KSt 1 F Line 18)",
	}
)
"""What the texts name, by the field or table it is: the labels of the DocTypes or the names of their tables, which
the Frappe layer translates."""


class BridgeError(ValueError):
	"""What a save refuses: a template of MESSAGES with its values, which the Frappe layer translates."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


@dataclass(frozen=True, slots=True)
class Unnumbered:
	"""An account of the profit and loss account without a number, with its balance in the Wirtschaftsjahr, credit
	less debit."""

	account: str
	balance: Decimal


@dataclass(frozen=True, slots=True)
class Ledger:
	"""What the ledger of the Wirtschaftsjahr gives the returns: the postings of the accounts of the profit and loss
	account that have a number, the Jahresüberschuss of all of them, those without a number that have a balance, and
	the Vorauszahlungen booked, by the tax of the Annual Filing Settings (KSt, SolZ, GewSt); None for a chart of its
	own, whose accounts of the taxes Steuerbote does not know."""

	lines: tuple[LedgerLine, ...]
	net_income: Decimal
	unnumbered: tuple[Unnumbered, ...] = ()
	booked_prepayments: Mapping[str, Decimal] | None = field(default_factory=dict)

	def __post_init__(self) -> None:
		object.__setattr__(self, "lines", tuple(self.lines))
		object.__setattr__(self, "unnumbered", tuple(self.unnumbered))
		if self.booked_prepayments is not None:
			object.__setattr__(self, "booked_prepayments", MappingProxyType(dict(self.booked_prepayments)))


@dataclass(frozen=True, slots=True)
class Advisor:
	"""The Steuerberatung that takes part in the returns of the year, KSt 1 lines 100 to 102 (§ 149 Absatz 3 AO)."""

	name: str | None = None
	first_name: str | None = None
	street: str | None = None
	town: str | None = None
	phone: str | None = None
	details: str | None = None
	client_number: str | None = None
	clerk: str | None = None


@dataclass(frozen=True, slots=True)
class Company:
	"""What KSt 1 and GewSt 1 A say of the company: its name and W-IdNr, the seats of §§ 10 and 11 AO, the key of its
	Rechtsform (None without one), the Gegenstand des Unternehmens, the day it was founded, the flag of § 8b Absatz 7
	KStG, the Bilanzierungsstandard and the Steuerberatung of the year."""

	name: str
	rechtsform: str | None = None
	management_seat: str | None = None
	registered_seat: str | None = None
	wid_nr: str | None = None
	business_purpose: str | None = None
	founded_on: date | None = None
	section_8b_7: bool = False
	accounting_standard: str = "HAOE"
	advisor: Advisor | None = None


@dataclass(frozen=True, slots=True)
class Settings:
	"""The Annual Filing Settings of the company as the returns read them (annual_filing_settings/rules.py)."""

	company: Company
	shareholders: tuple[rules.Shareholder, ...] = ()
	holdings: tuple[rules.Holding, ...] = ()
	prepayments: tuple[rules.Prepayment, ...] = ()
	carry_forwards: tuple[rules.CarryForward, ...] = ()
	establishments: tuple[rules.Establishment, ...] = ()
	trade_tax_rates: tuple[rules.TradeTaxRate, ...] = ()
	reviewed_on: date | None = None
	"""The day a Steuerberatung confirmed the classes of the trading accounts, the status under § 8b Absatz 7 KStG and
	the review list of the returns (decision 6.4 of the contract of stage 3), which both returns wait for."""

	def __post_init__(self) -> None:
		for name in (
			"shareholders",
			"holdings",
			"prepayments",
			"carry_forwards",
			"establishments",
			"trade_tax_rates",
		):
			object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class EBilanz:
	"""The E-Bilanz of the Wirtschaftsjahr as Anlage GK line 11 takes it: its name and Bilanzierungsstandard (HAOE,
	HGBM or AO), the Jahresüberschuss of its GuV, which under HGBM is that of the Handelsbilanz, the Jahresüberschuss of
	its Steuerbilanz after the Überleitung, the number of its entries of the Überleitung, and whether it reads the
	finance book the return reads."""

	name: str
	accounting_standard: str
	net_income: Decimal
	tax_net_income: Decimal
	transfers: int = 0
	same_books: bool = True


@dataclass(frozen=True, slots=True)
class PriorEBilanz:
	"""The E-Bilanz filed for the previous Wirtschaftsjahr that no Berichtigung replaced: its name, its year, and the
	Betriebsvermögen and the gezeichnetes Kapital of its Steuerbilanz at the Bilanzstichtag, in euros and cents."""

	name: str
	year: int
	equity: Decimal
	nominal_capital: Decimal


@dataclass(frozen=True, slots=True)
class Return:
	"""The Körperschaftsteuererklärung as stored: its VZ and Wirtschaftsjahr, the rows of its tables and what it says
	beside them. The turnover and wages of Anlage Z line 10 count once stated, 0 too; an equity of 0 counts as not
	given. ``ebilanz`` is the E-Bilanz the return names for Anlage GK line 11, ``prior_ebilanz`` the filed E-Bilanz
	of the previous Wirtschaftsjahr for KSt 1 F lines 17 and 18, each None without one."""

	year: int
	from_date: date
	to_date: date
	lines: tuple[Row, ...] = ()
	holding_results: tuple[Row, ...] = ()
	credits: tuple[Row, ...] = ()
	donations: tuple[Row, ...] = ()
	distributions: tuple[Row, ...] = ()
	contributions: tuple[Row, ...] = ()
	supplement_key: str | None = None
	supplement_text: str | None = None
	shareholder_contracts: bool = False
	carry_back_chosen: bool = False
	loss_carry_back: Decimal = ZERO
	turnover_and_wages_given: bool = False
	turnover_and_wages: Decimal = ZERO
	previous_equity: Decimal = ZERO
	previous_nominal_capital: Decimal = ZERO
	ebilanz: EBilanz | None = None
	prior_ebilanz: PriorEBilanz | None = None
	first_year: bool = False
	"""The first year of the company in Steuerbote: no return of the previous year was filed through it, and the
	company did not begin in the year (steuerbote/setup/start.py)."""

	def __post_init__(self) -> None:
		for name in ("lines", "holding_results", "credits", "donations", "distributions", "contributions"):
			object.__setattr__(self, name, tuple(getattr(self, name)))

	@property
	def opening_day(self) -> date:
		"""The end of the previous Wirtschaftsjahr, as of which the notices state the carry-forwards."""
		return self.from_date - timedelta(days=1)


@dataclass(frozen=True, slots=True)
class Computation:
	"""What Berechnen gives: the result of the core, the steuerliches Einlagekonto with its KSt 1 F, the rows of the
	table of lines, the values of the fields of the return and the findings."""

	result: KstResult
	einlagekonto: Einlagekonto
	kst1f: Vordruck
	lines: list[dict[str, Any]]
	values: dict[str, Decimal]
	findings: tuple[Finding, ...]


def compute(
	ret: Return,
	ledger: Ledger,
	mapping: IncomeTaxMapping,
	settings: Settings | None,
	figures: Figures,
	translate: Translate,
) -> Computation:
	"""Berechnen of the Körperschaftsteuererklärung; see the module docstring."""
	found: list[Finding] = []
	carry_forwards = {
		name: carry_forward(
			settings.carry_forwards if settings else (), kind, ret.opening_day, figures, translate, found
		)
		for name, kind in CARRY_FORWARDS.items()
	}
	missing_carry_forwards(
		settings.carry_forwards if settings else (),
		(rules.CarryForwardKind.LOSS, rules.CarryForwardKind.EINLAGEKONTO),
		ret,
		translate,
		found,
	)
	base = _inputs(ret, ledger, mapping, settings, carry_forwards, translate, found)
	manual = (*base.manual, *_manual_lines(ret.lines, chain.compute(base, figures)))
	result = chain.compute(replace(base, manual=manual), figures)
	if ret.carry_back_chosen:
		carry_back = to_amount(ret.loss_carry_back)
		if result.total_income < ZERO:
			result = chain.compute(replace(base, manual=manual, loss_carry_back=carry_back), figures)
		elif carry_back:
			text = translate(CARRY_BACK_WITHOUT_LOSS_TEXT).format(
				figures.money(carry_back), figures.money(result.total_income)
			)
			found.append(_error(CARRY_BACK_WITHOUT_LOSS, text, "§ 10d Absatz 1 EStG"))
	account = _einlagekonto(ret, carry_forwards, figures)
	booked, not_booked, other = contributions_by_line(ret.contributions)
	known = account.distributable is not None
	equity, nominal = previous_equity(ret)
	einlagekonto = kst1f(
		account,
		wj=WJ[0],
		previous_equity=equity if known else None,
		previous_nominal_capital=nominal if known else None,
		contributions_booked=booked,
		contributions_not_booked=not_booked,
		other_contributions=other,
	)
	found[:0] = findings_of((*result.findings, *account.findings))
	found.extend(_readiness(ret, ledger, mapping, settings, result, figures, translate))
	return Computation(
		result,
		account,
		einlagekonto,
		line_rows(result, (*vordrucke(result), einlagekonto)),
		values_of(result, account),
		tuple(found),
	)


def findings_of(found: Iterable[chain.Finding]) -> list[Finding]:
	"""The findings of the core as the table Befunde holds them."""
	return [Finding(item.code, item.severity, item.text, item.reference) for item in found]


def line_rows(result: KstResult, computed: Iterable[Vordruck]) -> list[dict[str, Any]]:
	"""The rows of the table of lines: each amount outside a repeated context of the Vordrucke, in the order of the
	catalogue, with its form, line and Beschreibung and, for a line of the books, the amount of the books."""
	catalogue = catalogue_for(result.year.year)
	steps = {feldkennung: key for key, feldkennung in STEP_FIELDS.items()}
	ranks = {item.feldkennung: rank for rank, item in enumerate(catalogue.fields)}
	rows = []
	for vordruck in computed:
		for entry in vordruck.entries:
			if entry.rows or not isinstance(entry.value, Decimal):
				continue
			step = steps.get(entry.feldkennung)
			books = step is not None and chain.step(step).source in _BOOKS
			rows.append(
				{
					**describe(shown(catalogue.field(entry.feldkennung), result.year.year)),
					"form_amount": entry.value,
					"ledger_amount": result.lines[step].ledger if books else ZERO,
				}
			)
	return sorted(rows, key=lambda row: ranks[row["feldkennung"]])


def describe(item: Field) -> dict[str, str]:
	"""What a row of the table of lines says of its field: Feldkennung, form, line and Beschreibung."""
	return {
		"feldkennung": item.feldkennung,
		"form": item.form,
		"line": "" if item.line is None else str(item.line),
		"label": item.label,
	}


def shown(item: Field, year: int) -> Field:
	"""A field as the return shows it: its Beschreibung with the years of the return in place of the placeholders of
	the Jahresdokumentation."""

	def filled(match: re.Match[str]) -> str:
		sign, offset = match.groups()
		return str(year - int(offset) if sign == "-" else year + int(offset or 0))

	return replace(item, label=YEAR_PLACEHOLDER.sub(filled, item.label))


def normalized(feldkennung: object) -> str:
	"""A Feldkennung as the catalogue writes it, such as E8002701 for e8002701."""
	return str(feldkennung or "").strip().upper()


def manual_field(year: int, feldkennung: object) -> Field:
	"""The field a line by hand names by its Feldkennung, which has to be one of a correctable step, as the return
	shows it."""
	key = normalized(feldkennung)
	if key not in CORRECTABLE_FIELDS:
		raise BridgeError(NOT_A_LINE, key or "-")
	return shown(catalogue_for(year).field(key), year)


def check_lines(year: int, rows: Iterable[Row]) -> None:
	"""A correction and a line by hand stand on the lines of the books and those left to hand, and file what their
	field takes: whole euros where it takes no cents."""
	catalogue = catalogue_for(year)
	for row in rows:
		key = normalized(row.get("feldkennung"))
		correction = correction_of(row, LINE_COLUMNS)
		if row.get("manual"):
			manual_field(year, key)
		elif correction is not None and key not in CORRECTABLE_FIELDS:
			raise BridgeError(NOT_CORRECTABLE, key)
		amount = correction.amount if correction is not None else ZERO
		if catalogue.field(key).format in WHOLE_EUROS and amount != amount.to_integral_value():
			raise BridgeError(NOT_WHOLE, key, format(amount, "f"))


def check_tables(ret: Return, translate: Translate) -> None:
	"""The rows of the tables of the return and its amounts, as the core and the Vordrucke take them."""

	def where(table: str, row: Row) -> tuple[str, object]:
		return translate(LABELS[table]), row.get("idx") or "?"

	for row in ret.holding_results:
		kind, at = row.get("kind"), where("holding_results", row)
		_option(kind, HOLDING_KINDS, at)
		if kind == SALE:
			for column in ("sale_price", "sale_costs", "book_value"):
				_not_negative(row.get(column), at, translate(LABELS[column]))
			if _day(row.get("result_date")) is None:
				raise BridgeError(SALE_WITHOUT_DAY, *at)
			if not sale_result(row):
				raise BridgeError(SALE_WITHOUT_RESULT, *at)
		else:
			_positive(row.get("amount"), at, euros=kind == WRITE_DOWN)
		for column in ("financing_costs", "other_costs"):
			_not_negative(row.get(column), at, translate(LABELS[column]))
	for row in ret.credits:
		for column in ("capital_gains_tax", "solz"):
			_not_negative(row.get(column), where("credits", row), translate(LABELS[column]))
	for row in ret.donations:
		_positive(row.get("amount"), where("donations", row))
	for row in ret.distributions:
		at = where("distributions", row)
		_option(row.get("kind"), DISTRIBUTION_KINDS, at)
		_positive(row.get("amount"), at, euros=True)
		certified = to_amount(row.get("certified_reduction"))
		if certified and certified != certified.to_integral_value():
			raise BridgeError(ROW_NOT_IN_EUROS, *at)
		if certified > to_amount(row.get("amount")):
			raise BridgeError(REDUCTION_ABOVE_AMOUNT, *at)
		outflow = _in_the_year(ret, row, "outflow_date", at, translate)
		if row.get("kind") == ORDINARY:
			resolved = _day(row.get("resolution_date"))
			if resolved is None:
				raise BridgeError(NO_RESOLUTION, *at)
			if outflow < resolved:
				raise BridgeError(OUTFLOW_BEFORE_RESOLUTION, *at)
	for row in ret.contributions:
		at = where("contributions", row)
		_option(row.get("treatment"), CONTRIBUTION_TREATMENTS, at)
		_option(row.get("kind") or CASH, CONTRIBUTION_KINDS, at)
		if row.get("kind") == IN_KIND and not str(row.get("description") or "").strip():
			raise BridgeError(NO_DESCRIPTION, *at)
		_positive(row.get("amount"), at, euros=True)
		_in_the_year(ret, row, "contribution_date", at, translate)
	for name in ("loss_carry_back", "turnover_and_wages", "previous_nominal_capital", "previous_equity"):
		amount = to_amount(getattr(ret, name))
		if amount != amount.to_integral_value():
			raise BridgeError(FIELD_NOT_IN_EUROS, translate(LABELS[name]))
		if amount < ZERO and name != "previous_equity":
			raise BridgeError(FIELD_NEGATIVE, translate(LABELS[name]))


def sale_result(row: Row) -> Decimal:
	"""The result of a sale of shares: the price, or the value in its place, less the costs of the sale and the book
	value of the shares (§ 8b Absatz 2 Satz 2 KStG); above zero a gain, below zero a loss."""
	return (
		to_amount(row.get("sale_price")) - to_amount(row.get("sale_costs")) - to_amount(row.get("book_value"))
	)


def holding_exemption(year: int, row: Row, settings: Settings | None) -> tuple[rules.Holding | None, str]:
	"""The holding of the register that a row of dividends names, and what § 8b KStG makes of its dividends, as the
	columns of the row show them; nothing for a row of another kind or of a holding the register does not name."""
	if row.get("kind") != DIVIDENDS:
		return None, ""
	registered = registered_holding(year, row, settings)
	if registered is None:
		return None, ""
	trading_book = settings is not None and settings.company.section_8b_7
	return registered, EXEMPTIONS[exemption(holding_of(registered), year_of(year), trading_book)]


def filed_vordrucke(ret: Return, rows: Iterable[Row], settings: Settings | None) -> tuple[Vordruck, ...]:
	"""The Vordrucke the return files, from its lines as stored and what the computation does not know: KSt 1 from the
	settings, the single values of the tables and Anlage WA line 15. A line by hand is in the line of its field. With
	Leistungen, KSt 1 F line 12 holds the certified reductions of the Einlagekonto, if need be 0, since each Leistung
	states its own (rules 8912016 and 8920254)."""
	catalogue = catalogue_for(ret.year)
	entries: dict[str, list[Entry]] = {"KSt1": kst1_entries(ret, settings)}
	for row in rows:
		if row.get("manual"):
			continue
		item = catalogue.field(normalized(row.get("feldkennung")))
		amount = to_amount(row.get("reported"))
		if amount or item.format not in ZERO_REFUSED:
			entries.setdefault(item.form, []).append(Entry(item.feldkennung, amount))
	entries.setdefault("GK", []).extend(_gk_details(ret, settings))
	entries.setdefault("WA", []).append(Entry(SHAREHOLDER_CONTRACTS, ret.shareholder_contracts))
	if entries.get("Z"):
		entries["Z"].extend(_receipts(ret.donations))
	kst1f_entries = entries.setdefault("KSt1F", [])
	kst1f_entries.extend(_kst1f_details(ret))
	if ret.distributions and all(entry.feldkennung != CERTIFIED_REDUCTION for entry in kst1f_entries):
		kst1f_entries.append(Entry(CERTIFIED_REDUCTION, ZERO))
	return tuple(
		Vordruck(form, tuple(found), WJ[0] if form in INDEXED else None) for form, found in entries.items()
	)


def kst1_entries(ret: Return, settings: Settings | None) -> list[Entry]:
	"""KSt 1 from the settings and the return: the company, its seats and Rechtsform, the qualified free text, the
	Wirtschaftsjahr, the flags of lines 14a, 16 and 17, the shareholders of lines 21 to 27 and the Steuerberatung of
	lines 100 to 102. KSt 1 F goes with every return of a Kapitalgesellschaft (rules 8931022 and 8900709)."""
	found = [Entry(EINLAGEKONTO_DECLARED, True)]
	company = settings.company if settings else None
	if company is not None:
		for feldkennung, value in (
			(COMPANY_NAME, company.name),
			(WID_NR, company.wid_nr),
			(MANAGEMENT_SEAT, company.management_seat),
			(REGISTERED_SEAT, company.registered_seat),
			(RECHTSFORM, company.rechtsform),
		):
			if value:
				found.append(Entry(feldkennung, value))
	if ret.supplement_key:
		found.append(Entry(SUPPLEMENT_KEY, ret.supplement_key))
	if (ret.supplement_text or "").strip():
		found.append(Entry(SUPPLEMENT_TEXT, ret.supplement_text.strip()))
	found += [Entry(WJ_FROM, ret.from_date), Entry(WJ_TO, ret.to_date)]
	if company is not None and company.founded_on and ret.from_date <= company.founded_on <= ret.to_date:
		found.append(Entry(FOUNDED, True))
	if company is not None and company.section_8b_7:
		found.append(Entry(TRADING_BOOK, True))
	found.append(Entry(SECTION_8_9, False))
	shareholders = settings.shareholders if settings else ()
	found.extend(shareholder_entries(ret, shareholders))
	found.append(Entry(SHAREHOLDERS_CHANGED, shareholders_changed(ret, shareholders)))
	if company is not None and company.advisor is not None:
		found.append(Entry(ADVISOR, True))
		for attribute, feldkennung in ADVISOR_FIELDS.items():
			if value := getattr(company.advisor, attribute):
				found.append(Entry(feldkennung, value))
	return found


def shareholders_changed(ret: Return, shareholders: Iterable[rules.Shareholder]) -> bool:
	"""KSt 1 line 27, „Die oben genannten Angaben zu den Anteilseignern haben sich gegenüber dem Vorjahr geändert“:
	a holding period begins in the Wirtschaftsjahr, or one ends in it before its last day. A company founded in the
	year has its shareholders from a day of the year, so they changed."""
	last = ret.to_date - timedelta(days=1)
	return any(
		ret.from_date <= shareholder.from_date <= ret.to_date
		or (shareholder.to_date is not None and ret.from_date <= shareholder.to_date <= last)
		for shareholder in shareholders
	)


def shareholder_entries(ret: Return, shareholders: Iterable[rules.Shareholder]) -> list[Entry]:
	"""KSt 1 lines 21 to 23b: each Anteilseigner of the Wirtschaftsjahr once, by its name, with each of its holding
	periods in it, at most three, cut to the Wirtschaftsjahr, and line 21a, whether its data changed against the
	previous year, as shareholders_changed() tells it for its periods: ERiC refuses an Anteilseigner without line 21a
	(rule 8912022 of the Jahresdokumentation KSt 2025; validation with ERiC 44.3.6.0)."""
	found = []
	for person, periods in enumerate(_persons(ret, shareholders).values()):
		first = periods[0]
		for feldkennung, value in (
			(SHAREHOLDER_TAX_NUMBER, first.tax_number),
			(SHAREHOLDER_IDNR, first.idnr),
			(SHAREHOLDER_WID_NR, first.wid_nr),
			(SHAREHOLDER_FOREIGN_ID, first.foreign_id),
			(SHAREHOLDER_NAME, first.name),
			(SHAREHOLDER_STREET, first.street),
			(SHAREHOLDER_TOWN, first.postal_code_and_town),
		):
			if value:
				found.append(Entry(feldkennung, value, (person,)))
		found.append(Entry(SHAREHOLDER_DATA_CHANGED, shareholders_changed(ret, periods), (person,)))
		ordered = sorted(periods, key=lambda item: item.from_date)[:MOST_SHARE_PERIODS]
		for instance, period in enumerate(ordered):
			rows = (person, instance)
			found += [
				Entry(SHARE_EUROS, period.nominal_amount, rows),
				Entry(SHARE_PERCENT, period.percent, rows),
				Entry(SHARE_FROM, max(period.from_date, ret.from_date), rows),
				Entry(SHARE_TO, min(period.to_date or ret.to_date, ret.to_date), rows),
			]
	return found


def rule_findings(year: int, filed: Iterable[Vordruck], translate: Translate) -> list[Finding]:
	"""The rules of the Jahresdokumentation that Steuerbote checks itself (steuerbote.eric.simulation.kst.RULES) on
	the Vordrucke as filed, each with its Fehlercode; Vordrucke ELSTER would not take at all are one error."""
	return checked_rules(
		kst_xml.to_nutzdaten, kst_rules.RULES, kst_datenart(year), filed, translate, NUTZDATEN
	)


def checked_rules(
	write: Callable[[int, Iterable[Vordruck], Vorsatz], str],
	found_rules: Iterable[Callable[..., Any]],
	kind: Any,
	filed: Iterable[Vordruck],
	translate: Translate,
	code: str,
) -> list[Finding]:
	"""The rules of a Datenart on the Nutzdaten that ``write`` makes of the Vordrucke, which the Körperschaftsteuer
	and the Gewerbesteuer share; ``code`` is that of the error of Vordrucke ELSTER would not take."""
	try:
		written = write(kind.year, tuple(filed), FOR_THE_RULES)
	except ValueError as error:
		return [_error(code, translate(NUTZDATEN_TEXT).format(xml_text(error, translate)), kind.name)]
	root = ElementTree.fromstring(written)  # noqa: S314 - written by steuerbote.elster just now
	found = []
	for rule in found_rules:
		message = rule(root, kind, None)
		if message is not None:
			found.append(_error(message.code, message.text, message.field or kind.name))
	return found


def provisional(year: int) -> tuple[bool, int]:
	"""Whether the VZ takes the forms of an earlier Jahresdokumentation E30, and the year of the one it takes."""
	data = year_of(year)
	return data.provisional, data.documentation_year


def provisional_finding(code: str, year: int, documentation_year: int, translate: Translate) -> Finding:
	"""The forms of a provisional year hold the return back: ELSTER has not published them, so neither ERiC nor the
	forms of Mein ELSTER are known to take the return as Steuerbote writes it (contract of stage 3, 1.2)."""
	text = translate(PROVISIONAL_TEXT).format(year, documentation_year)
	return _error(code, text, f"Jahresdokumentation {documentation_year}")


def contributions_by_line(rows: Iterable[Row]) -> tuple[Decimal, Decimal, Decimal]:
	"""The Einlagen of KSt 1 F lines 91, 92 and 95: booked to profit and paid, not booked to profit, and the others.
	Einlagen not paid by the end of the Wirtschaftsjahr do not enter the Einlagekonto (§ 27 Absatz 1 Satz 1 KStG:
	„geleisteten Einlagen“)."""
	rows = list(rows)

	def total(treatment: str) -> Decimal:
		return _sum(row.get("amount") for row in rows if row.get("treatment") == treatment)

	return total(PAID), total(NOT_BOOKED), total(OTHER)


def previous_equity(ret: Return) -> tuple[Decimal | None, Decimal | None]:
	"""KSt 1 F lines 17 and 18, the Eigenkapital laut Steuerbilanz and the Nennkapital at the end of the previous
	Wirtschaftsjahr: the Betriebsvermögen and the gezeichnetes Kapital of the Steuerbilanz of the E-Bilanz filed for
	it, in the whole euros the lines take, rounded half up as no direction is given (adopted answer Q5 of the research
	of stage 3); without one those the return gives by hand, None while it gives neither."""
	prior = ret.prior_ebilanz
	if prior is not None:
		return half_up_euro(to_amount(prior.equity)), half_up_euro(to_amount(prior.nominal_capital))
	equity, nominal = to_amount(ret.previous_equity), to_amount(ret.previous_nominal_capital)
	if not (equity or nominal):
		return None, None
	return equity, nominal


def values_of(result: KstResult, account: Einlagekonto) -> dict[str, Decimal]:
	"""The fields of the computation of the return."""
	lines = result.lines
	return {
		"net_income": lines["net_income"].declared,
		"business_income": result.business_income,
		"sum_of_income": result.sum_of_income,
		"total_income": result.total_income,
		"zve": result.zve,
		"kst": result.kst,
		"solz": result.solz,
		"capital_gains_tax_credit": lines["capital_gains_tax_credit"].declared,
		"solz_credit": lines["solz_credit"].declared,
		"kst_prepayments": lines["kst_prepayments"].declared,
		"solz_prepayments": lines["solz_prepayments"].declared,
		"kst_balance": result.kst_balance,
		"solz_balance": result.solz_balance,
		"einlagekonto": account.closing,
	}


def carry_forward(
	stated: Iterable[rules.CarryForward],
	kind: rules.CarryForwardKind,
	day: date,
	figures: Figures,
	translate: Translate,
	found: list[Finding],
	codes: tuple[str, str] = (UNCONFIRMED, NOT_IN_EUROS),
) -> Decimal:
	"""The latest carry-forward of the kind as of the day, in whole euros, 0 without one. The returns take only a
	confirmed one (Annual Filing Settings): one that is not confirmed counts 0, with a finding with the first of
	``codes``, and one not in whole euros counts rounded, with a finding with the second."""
	latest = rules.latest_carry_forward(stated, kind, day)
	if latest is None:
		return ZERO
	unconfirmed, not_in_euros = codes
	named = translate(str(kind))
	as_of = latest.as_of.strftime("%d.%m.%Y")
	if not latest.confirmed:
		found.append(_error(unconfirmed, translate(UNCONFIRMED_TEXT).format(named, as_of), "Einstellungen"))
		return ZERO
	euros = half_up_euro(latest.amount)
	if euros != latest.amount:
		text = translate(NOT_IN_EUROS_TEXT).format(
			named, as_of, figures.money(latest.amount), figures.money(euros)
		)
		found.append(_error(not_in_euros, text, "Einstellungen"))
	return euros


def missing_carry_forwards(
	stated: Iterable[rules.CarryForward],
	kinds: Iterable[rules.CarryForwardKind],
	ret: Return,
	translate: Translate,
	found: list[Finding],
	code: str = CARRY_FORWARD_MISSING,
) -> None:
	"""An error for each kind of ``kinds`` without an amount as of the opening day, in the first year of the company in
	Steuerbote: its last returns went elsewhere, so 0 for a carry-forward nobody entered would be a guess."""
	if not ret.first_year:
		return
	stated = tuple(stated)
	day = ret.opening_day.strftime("%d.%m.%Y")
	for kind in start.missing_carry_forwards(stated, ret.opening_day):
		if kind in kinds:
			text = translate(CARRY_FORWARD_MISSING_TEXT).format(translate(str(kind)), day)
			found.append(_error(code, text, "Einstellungen"))


def prepayments_of(year: int, settings: Settings | None) -> dict[str, Decimal]:
	"""The Vorauszahlungen of the notices of the year, by tax (§ 37 EStG with § 31 Absatz 1 KStG; § 19 GewStG)."""
	paid = dict.fromkeys((tax.value for tax in rules.Tax), ZERO)
	for prepayment in settings.prepayments if settings else ():
		if prepayment.year == year:
			paid[prepayment.tax.value] += prepayment.amount
	return paid


def booked_prepayment_findings(
	year: int,
	ledger: Ledger,
	settings: Settings,
	taxes: Sequence[str],
	figures: Figures,
	translate: Translate,
	code: str = PREPAYMENTS,
) -> list[Finding]:
	"""A hint where the Vorauszahlungen of the notices differ from those booked on the account of the tax, which the
	returns compare as adopted answer Q6 of the research of stage 3 asks; nothing for a chart of its own."""
	if ledger.booked_prepayments is None:
		return []
	noted = prepayments_of(year, settings)
	found = []
	for tax in taxes:
		booked = ledger.booked_prepayments.get(tax, ZERO)
		if noted[tax] != booked:
			text = translate(PREPAYMENTS_TEXT).format(tax, figures.money(noted[tax]), figures.money(booked))
			found.append(Finding(code, Severity.HINT, text, "§ 37 EStG; § 19 GewStG"))
	return found


def common_findings(
	ledger: Ledger,
	mapping: IncomeTaxMapping,
	settings: Settings | None,
	figures: Figures,
	translate: Translate,
) -> list[Finding]:
	"""What holds both returns back beside the forms of their year: missing settings, an account with a balance whose
	place the defaults of its chart give and the mapping lacks, and an account of the profit and loss account without a
	number."""
	found = []
	if settings is None:
		found.append(_error(NO_SETTINGS, translate(NO_SETTINGS_TEXT), "Einstellungen"))
	found.extend(unmapped(ledger, mapping, figures, translate))
	for account in ledger.unnumbered:
		text = translate(UNNUMBERED_TEXT).format(account.account, figures.money(account.balance))
		found.append(_error(UNNUMBERED, text, "Kontenzuordnung Ertragsteuern"))
	return found


def unmapped(
	ledger: Ledger, mapping: IncomeTaxMapping, figures: Figures, translate: Translate
) -> list[Finding]:
	"""The accounts with a balance that the defaults of the chart give a place in the mapping, a category or a watch,
	and the mapping of the company does not: DATEV marks them for its tax programs (Programmverbindung K or G,
	steuerbote.kst.defaults). A chart of its own has no defaults to compare with."""
	try:
		defaults = {account.number for account in default_accounts(mapping.chart)}
	except KeyError:
		return []
	placed = {rule.account_number for rule in mapping.rules} | {
		item.account_number for item in mapping.watched
	}
	totals: dict[str, list[Decimal]] = {}
	for line in ledger.lines:
		total = totals.setdefault(line.account_number, [ZERO, ZERO])
		total[0] += line.debit
		total[1] += line.credit
	found = []
	for number, (debit, credit) in sorted(totals.items()):
		if number in defaults and number not in placed and debit != credit:
			text = translate(UNMAPPED_TEXT).format(
				number, figures.money(debit), figures.money(credit), mapping.chart
			)
			found.append(_error(UNMAPPED, text, "Kontenzuordnung Ertragsteuern"))
	return found


@dataclass(frozen=True, slots=True)
class Posting:
	"""What one voucher of the Wirtschaftsjahr posts on one account of the taxes on income, of their provisions or of
	the claims to their refund (steuerbote.kst.provisions.ACCOUNTS); ``voucher`` is "<voucher type>:<voucher name>"."""

	voucher: str
	account_number: str
	debit: Decimal
	credit: Decimal


def booked_taxes(
	postings: Iterable[Posting], accounts: ProvisionAccounts
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
	"""What the books hold of each tax of the Wirtschaftsjahr, by the tax of the Annual Filing Settings: the
	Vorauszahlungen, the debits less the credits on the expense account of the tax of the vouchers that touch neither its
	Rückstellung nor its claim to a refund, and the provisions, those of the vouchers that do. A provision posted by the
	draft Journal Entry of Rückstellungen vorschlagen is one of the latter, so it never counts as a Vorauszahlung."""
	by_voucher: dict[str, list[Posting]] = {}
	for posting in postings:
		by_voucher.setdefault(posting.voucher, []).append(posting)
	prepayments: dict[str, Decimal] = {}
	posted: dict[str, Decimal] = {}
	for tax, taxed in zip(TAX_KEYS, (accounts.kst, accounts.solz, accounts.gewst), strict=True):
		prepayments[tax] = posted[tax] = ZERO
		for items in by_voucher.values():
			numbers = {item.account_number for item in items}
			amount = sum(
				(item.debit - item.credit for item in items if item.account_number == taxed.expense), ZERO
			)
			target = posted if numbers & {taxed.provision, taxed.refund} else prepayments
			target[tax] += amount
	return prepayments, posted


def registered_holding(year: int, row: Row, settings: Settings | None) -> rules.Holding | None:
	"""The holding of the register of the year that a row names, by its name."""
	name = _name_key(row.get("holding_name"))
	return next(
		(
			holding
			for holding in (settings.holdings if settings else ())
			if holding.year == year and _name_key(holding.name) == name
		),
		None,
	)


def holding_of(registered: rules.Holding) -> Holding:
	"""The holding of steuerbote.kst.holdings: its shares at the start of the calendar year and of the
	Erhebungszeitraum, each standing in for the other where the register gives one alone, and whether the company has
	its management and seat abroad (§ 9 Nummer 7 GewStG instead of Nummer 2a)."""
	at_year_start = registered.percent_on_1_january
	at_ez_start = registered.percent_at_start_of_ez
	first = at_year_start if at_year_start is not None else at_ez_start
	first = first if first is not None else ZERO
	return Holding(
		registered.name,
		first,
		at_ez_start if at_ez_start is not None else first,
		foreign=bool(registered.country) and registered.country != rules.GERMANY,
	)


def xml_text(error: ValueError, translate: Translate) -> str:
	"""The text of what the writer of the Nutzdaten refused, in the language of ``translate``."""
	if isinstance(error, XmlError):
		label = translate(error.label) if error.label else ""
		return translate(error.template).format(*error.values, label=label)
	return str(error)


def error(code: str, text: str, reference: str) -> Finding:
	"""An error of the table Befunde; the reference keeps to the length of its field."""
	return _error(code, text, reference)


# Inputs.


def _inputs(
	ret: Return,
	ledger: Ledger,
	mapping: IncomeTaxMapping,
	settings: Settings | None,
	carry_forwards: Mapping[str, Decimal],
	translate: Translate,
	found: list[Finding],
) -> KstInputs:
	"""The KstInputs of the VZ without the lines of the table of lines."""
	holdings = []
	for row in ret.holding_results:
		if row.get("kind") != DIVIDENDS:
			continue
		registered = registered_holding(ret.year, row, settings)
		if registered is None:
			text = translate(UNKNOWN_HOLDING_TEXT).format(row.get("holding_name"), ret.year)
			found.append(_error(UNKNOWN_HOLDING, text, "§ 8b Absatz 4 Satz 1 KStG"))
			continue
		holdings.append(
			HoldingResult(
				holding_of(registered),
				to_amount(row.get("amount")),
				to_amount(row.get("financing_costs")),
				to_amount(row.get("other_costs")),
			)
		)
	prepayments = prepayments_of(ret.year, settings)
	return KstInputs(
		ret.year,
		ledger.lines,
		mapping,
		net_income=ledger.net_income if ret.ebilanz is None else to_amount(ret.ebilanz.net_income),
		manual=(*_contribution_lines(ret.contributions), *ueberleitung_lines(ret.ebilanz, translate)),
		holdings=tuple(holdings),
		trading_book=settings is not None and settings.company.section_8b_7,
		loss_carry_forward=carry_forwards["loss_carry_forward"],
		derivatives_carry_forward=carry_forwards["derivatives_carry_forward"],
		donation_carry_forward=carry_forwards["donation_carry_forward"],
		eligible_donations=eligible_donations(ret, ledger, mapping),
		turnover_and_wages=to_amount(ret.turnover_and_wages) if ret.turnover_and_wages_given else None,
		capital_gains_tax_credit=_sum(row.get("capital_gains_tax") for row in ret.credits),
		solz_credit=_sum(row.get("solz") for row in ret.credits),
		kst_prepayments=prepayments["KSt"],
		solz_prepayments=prepayments["SolZ"],
	)


def _manual_lines(rows: Iterable[Row], books: KstResult) -> list[ManualLine]:
	"""The lines by hand of the table, and each correction as the difference to the books and the lines by hand of its
	step, so that the line files the corrected amount."""
	rows = list(rows)
	manual: list[ManualLine] = []
	by_hand: dict[str, Decimal] = {}
	for row in rows:
		if row.get("manual"):
			key = _correctable(row)
			amount = to_amount(row.get("correction"))
			manual.append(ManualLine(key, amount, str(row.get("correction_reason")).strip()))
			by_hand[key] = by_hand.get(key, ZERO) + amount
	for row in rows:
		correction = None if row.get("manual") else correction_of(row, LINE_COLUMNS)
		if correction is None:
			continue
		key = _correctable(row)
		difference = correction.amount - books.lines[key].exact - by_hand.get(key, ZERO)
		if difference:
			manual.append(ManualLine(key, difference, correction.reason))
	return manual


def _correctable(row: Row) -> str:
	key = normalized(row.get("feldkennung"))
	if key not in CORRECTABLE_FIELDS:
		raise BridgeError(NOT_CORRECTABLE, key)
	return CORRECTABLE_FIELDS[key]


def _contribution_lines(rows: Iterable[Row]) -> tuple[ManualLine, ...]:
	"""The Einlagen of the year in the steps of Anlage GK lines 93, 94 and 78, each with the shareholder and the day
	as its reason."""
	return tuple(
		ManualLine(
			CONTRIBUTION_STEPS[row.get("treatment")], to_amount(row.get("amount")), _contribution_reason(row)
		)
		for row in rows
		if row.get("treatment") in CONTRIBUTION_STEPS
	)


def _contribution_reason(row: Row) -> str:
	day = _day(row.get("contribution_date"))
	parts = (str(row.get("shareholder") or "").strip(), day.strftime("%d.%m.%Y") if day else "")
	return ", ".join(part for part in parts if part) or str(row.get("treatment"))


def ueberleitung_lines(ebilanz: EBilanz | None, translate: Translate) -> tuple[ManualLine, ...]:
	"""The Überleitung of the E-Bilanz as the ManualLine of the step net_income that takes line 11 of Anlage GK from
	the Jahresüberschuss of its Handelsbilanz to that of its Steuerbilanz: „bei Handelsbilanz: nach Berücksichtigung
	der Überleitungsrechnung nach § 5b Absatz 1 Satz 2 EStG beziehungsweise § 60 Absatz 2 EStDV“
	(Jahresdokumentation_E30_2025.ods, E8002001). The Steuerbilanz is what the core of the E-Bilanz computed of the
	entries, with the steuerlicher Ausgleichsposten and the Sammelposten of the GuV (steuerbote/ebilanz/ueberleitung.py),
	so an Einheitsbilanz and a Steuerbilanz give none."""
	if ebilanz is None:
		return ()
	difference = to_amount(ebilanz.tax_net_income) - to_amount(ebilanz.net_income)
	if not difference:
		return ()
	return (ManualLine("net_income", difference, translate(UEBERLEITUNG_REASON).format(ebilanz.name)),)


def eligible_donations(ret: Return, ledger: Ledger, mapping: IncomeTaxMapping) -> Decimal:
	"""The Zuwendungen Anlage Z deducts: those of the receipts once the return lists one, else those of the books
	without the accounts that are no Zuwendungen of § 9 Absatz 1 Nummer 2 KStG (NON_DEDUCTIBLE_DONATIONS)."""
	if ret.donations:
		return _sum(row.get("amount") for row in ret.donations)
	return deductible_in_books(ledger, mapping)


def deductible_in_books(ledger: Ledger, mapping: IncomeTaxMapping) -> Decimal:
	"""The Zuwendungen of the books that § 9 Absatz 1 Nummer 2 KStG deducts within its limits."""
	excluded = NON_DEDUCTIBLE_DONATIONS.get(mapping.chart, frozenset())
	lines = [line for line in ledger.lines if line.account_number not in excluded]
	return max(classify(lines, mapping).amount(Category.DONATIONS), ZERO)


def _einlagekonto(ret: Return, carry_forwards: Mapping[str, Decimal], figures: Figures) -> Einlagekonto:
	"""The steuerliches Einlagekonto of the Wirtschaftsjahr (§ 27 KStG)."""
	certified = [to_amount(row.get("certified_reduction")) for row in ret.distributions]
	booked, not_booked, other = contributions_by_line(ret.contributions)
	equity, nominal = previous_equity(ret)
	return roll_forward(
		carry_forwards["einlagekonto"],
		figures,
		sonderausweis=carry_forwards["sonderausweis"],
		distributions=_sum(row.get("amount") for row in ret.distributions),
		certified_reduction=sum(certified, ZERO),
		several_certified=len(certified) > 1 and any(certified),
		previous_equity=equity,
		previous_nominal_capital=nominal,
		contributions_booked=booked,
		contributions_not_booked=not_booked,
		other_contributions=other,
	)


# What holds the return back.


def _readiness(
	ret: Return,
	ledger: Ledger,
	mapping: IncomeTaxMapping,
	settings: Settings | None,
	result: KstResult,
	figures: Figures,
	translate: Translate,
) -> list[Finding]:
	found = []
	is_provisional, documentation_year = provisional(ret.year)
	if is_provisional:
		found.append(provisional_finding(PROVISIONAL, ret.year, documentation_year, translate))
	found.extend(common_findings(ledger, mapping, settings, figures, translate))
	found.extend(_donations(ret, ledger, mapping, figures, translate))
	found.extend(_single_values(ret, result, figures, translate))
	if ret.shareholder_contracts:
		found.append(Finding(CONTRACTS, Severity.HINT, translate(CONTRACTS_TEXT), "Anlage WA Zeile 16"))
	found.extend(_capital_gains_tax(ret, result, figures, translate))
	found.extend(ebilanz_findings(ret, ledger, figures, translate))
	found.extend(equity_findings(ret, figures, translate))
	if settings is None:
		return found
	if settings.reviewed_on is None:
		found.append(_error(NOT_REVIEWED, translate(NOT_REVIEWED_TEXT), "Einstellungen"))
	found.extend(_details(settings, translate))
	found.extend(_shares(ret, settings, figures, translate))
	for periods in _persons(ret, settings.shareholders).values():
		if len(periods) > MOST_SHARE_PERIODS:
			text = translate(PERIODS_TEXT).format(periods[0].name, len(periods))
			found.append(_error(PERIODS, text, "KSt 1 Zeilen 23 bis 23b"))
	if (
		ret.ebilanz is None
		and settings.company.accounting_standard == HGB_WITH_RECONCILIATION
		and not _has_ueberleitung(ret.lines)
	):
		found.append(_error(NO_UEBERLEITUNG, translate(NO_UEBERLEITUNG_TEXT), "§ 60 Absatz 2 EStDV"))
	found.extend(booked_prepayment_findings(ret.year, ledger, settings, TAXES, figures, translate))
	return found


def ebilanz_findings(ret: Return, ledger: Ledger, figures: Figures, translate: Translate) -> list[Finding]:
	"""What holds a return back that takes line 11 of Anlage GK from its E-Bilanz: a Jahresüberschuss of the E-Bilanz
	other than that of the books the other lines of Anlage GK come from, as after a posting the E-Bilanz has not been
	calculated with, a hint where the E-Bilanz reads another finance book; the Überleitung of a Handelsbilanz with
	Überleitungsrechnung that the E-Bilanz lacks (§ 60 Absatz 2 Satz 1 EStDV); and lines by hand or corrections of
	line 11 beside the Überleitung of the E-Bilanz, which would count it twice."""
	ebilanz = ret.ebilanz
	if ebilanz is None:
		return []
	found = []
	difference = to_amount(ebilanz.net_income) - to_amount(ledger.net_income)
	if abs(difference) >= WHOLE_EURO:
		template = EBILANZ_DIFFERS_TEXT if ebilanz.same_books else EBILANZ_OTHER_BOOKS_TEXT
		text = translate(template).format(
			ebilanz.name,
			figures.money(to_amount(ebilanz.net_income)),
			figures.money(to_amount(ledger.net_income)),
			figures.money(difference),
		)
		severity = Severity.ERROR if ebilanz.same_books else Severity.HINT
		found.append(Finding(EBILANZ_DIFFERS, severity, text, NET_INCOME_LINE))
	if ebilanz.accounting_standard == HGB_WITH_RECONCILIATION and not ebilanz.transfers:
		text = translate(NO_UEBERLEITUNG_EBILANZ_TEXT).format(ebilanz.name)
		found.append(_error(NO_UEBERLEITUNG, text, "§ 60 Absatz 2 EStDV"))
	if _has_ueberleitung(ret.lines):
		text = translate(UEBERLEITUNG_TWICE_TEXT).format(ebilanz.name)
		found.append(_error(UEBERLEITUNG_TWICE, text, NET_INCOME_LINE))
	return found


def equity_findings(ret: Return, figures: Figures, translate: Translate) -> list[Finding]:
	"""A hint that says where KSt 1 F lines 17 and 18 come from: the E-Bilanz filed for the previous Wirtschaftsjahr,
	whose Steuerbilanz the lines name, „Eigenkapital laut Steuerbilanz“ (Jahresdokumentation_E30_2025.ods, E8201001),
	or the amounts the return gives by hand; none where the return has neither."""
	prior = ret.prior_ebilanz
	by_hand = (to_amount(ret.previous_equity), to_amount(ret.previous_nominal_capital))
	if prior is not None:
		equity, nominal = previous_equity(ret)
		values = (figures.money(equity), figures.money(nominal), prior.name, prior.year)
		if any(by_hand) and by_hand != (equity, nominal):
			text = translate(EQUITY_OVER_HAND_TEXT).format(
				*values, *(figures.money(amount) for amount in by_hand)
			)
		else:
			text = translate(EQUITY_FROM_EBILANZ_TEXT).format(*values)
	elif any(by_hand):
		text = translate(EQUITY_BY_HAND_TEXT).format(
			*(figures.money(amount) for amount in by_hand), ret.year - 1
		)
	else:
		return []
	return [Finding(EQUITY_SOURCE, Severity.HINT, text, PRIOR_EQUITY_LINES)]


def _details(settings: Settings, translate: Translate) -> list[Finding]:
	"""KSt 1 lines 6, 7 and 9 are Pflichtfelder (Jahresdokumentation_E30_2025.ods, sheet „KSt1 - Felder“)."""
	company = settings.company
	missing = [
		translate(LABELS[name])
		for name in ("rechtsform", "management_seat", "registered_seat")
		if not getattr(company, name)
	]
	if not missing:
		return []
	text = translate(DETAILS_MISSING_TEXT).format(company.name, ", ".join(missing))
	return [_error(DETAILS_MISSING, text, "KSt 1 Zeilen 6 bis 9")]


def _shares(ret: Return, settings: Settings, figures: Figures, translate: Translate) -> list[Finding]:
	"""Rule 8931029 on each day of the Wirtschaftsjahr: the shares change on the first day of a holding period and on
	the day after its last, so those days and the first of the year are checked."""
	days = {ret.from_date}
	for shareholder in settings.shareholders:
		days.add(shareholder.from_date)
		if shareholder.to_date is not None:
			days.add(shareholder.to_date + timedelta(days=1))
	low, high = SHARES_ON_EACH_DAY
	for day in sorted(day for day in days if ret.from_date <= day <= ret.to_date):
		total = rules.share_total(settings.shareholders, day)
		if not low <= total <= high:
			text = translate(SHARES_TEXT).format(day.strftime("%d.%m.%Y"), figures.percent(total))
			return [_error(SHARES, text, "KSt 1 Zeilen 21 bis 27; Regel 8931029")]
	return []


def _has_ueberleitung(rows: Iterable[Row]) -> bool:
	net_income = STEP_FIELDS["net_income"]
	return any(
		normalized(row.get("feldkennung")) == net_income
		and bool(row.get("manual") or correction_of(row, LINE_COLUMNS) is not None)
		for row in rows
	)


def _capital_gains_tax(
	ret: Return, result: KstResult, figures: Figures, translate: Translate
) -> list[Finding]:
	"""A hint where the Kapitalertragsteuer of the Steuerbescheinigungen differs from that booked as an expense, which
	Anlage GK line 83 adds back."""
	certified = _sum(row.get("capital_gains_tax") for row in ret.credits)
	booked = result.classification.amount(Category.KAPEST)
	if certified == booked:
		return []
	text = translate(CAPITAL_GAINS_TAX_TEXT).format(figures.money(certified), figures.money(booked))
	return [Finding(CAPITAL_GAINS_TAX, Severity.HINT, text, "§ 36 Absatz 2 Nummer 2 EStG")]


def _donations(
	ret: Return, ledger: Ledger, mapping: IncomeTaxMapping, figures: Figures, translate: Translate
) -> list[Finding]:
	"""Anlage Z line 5 and GewSt 1 A lines 92a to 92c name each Zuwendung of the year by its receipt (§ 50 Absatz 1
	EStDV: „Zuwendungen ... dürfen nur abgezogen werden, wenn ... eine Zuwendungsbestätigung“ is held)."""
	in_books = deductible_in_books(ledger, mapping)
	if not ret.donations:
		if not in_books:
			return []
		text = translate(NO_RECEIPTS_TEXT).format(figures.money(in_books))
		return [_error(NO_RECEIPTS, text, "§ 9 Absatz 1 Nummer 2 KStG; § 50 EStDV")]
	receipts = _sum(row.get("amount") for row in ret.donations)
	if receipts == in_books:
		return []
	text = translate(RECEIPTS_DIFFER_TEXT).format(figures.money(receipts), figures.money(in_books))
	return [Finding(RECEIPTS_DIFFER, Severity.HINT, text, "§ 9 Absatz 1 Nummer 2 KStG")]


def _single_values(ret: Return, result: KstResult, figures: Figures, translate: Translate) -> list[Finding]:
	"""Anlage GK lines 166b, 166c, 176 and 188 sum the single values of each sale, write-up and write-down (rules
	8956070, 8956072, 8905507 and 8905516); a line of the books without any holds the return back."""
	kinds = {_single_value_kind(row) for row in ret.holding_results}
	found = []
	for key, kind in SINGLE_VALUES.items():
		line = result.lines[key]
		if line.declared and kind not in kinds:
			text = translate(NO_SINGLE_VALUES_TEXT).format(line.step.line, figures.money(line.declared))
			found.append(_error(NO_SINGLE_VALUES, text, f"Anlage GK Zeile {line.step.line}"))
	return found


# The details of the Vordrucke.


def _gk_details(ret: Return, settings: Settings | None) -> list[Entry]:
	"""The single values of Anlage GK lines 162 to 166a, 167b to 167c and 185 to 186, and lines 151 to 155 of the
	holdings whose dividends § 8b Absatz 1 KStG exempts. A sale states its day, its price, its costs, the book value and
	its gain or its loss together (rule 8956041)."""
	found = []
	sales = writeups = writedowns = 0
	for row in ret.holding_results:
		kind, name, amount = row.get("kind"), row.get("holding_name"), to_amount(row.get("amount"))
		if kind == SALE:
			found.append(Entry(SALE_NAME, name, (sales,)))
			if sold_on := _day(row.get("result_date")):
				found.append(Entry(SALE_DATE, sold_on, (sales,)))
			for feldkennung, column in (
				(SALE_PRICE, "sale_price"),
				(SALE_COSTS, "sale_costs"),
				(BOOK_VALUE, "book_value"),
			):
				found.append(Entry(feldkennung, to_amount(row.get(column)), (sales,)))
			result = sale_result(row)
			if result > ZERO:
				found.append(Entry(SALE_GAIN_FIELD, result, (sales,)))
			else:
				found.append(Entry(SALE_LOSS_FIELD, -result, (sales,)))
			sales += 1
		elif kind == WRITE_UP:
			found += [Entry(WRITE_UP_NAME, name, (writeups,)), Entry(WRITE_UP_FIELD, amount, (writeups,))]
			writeups += 1
		elif kind == WRITE_DOWN:
			found += [
				Entry(WRITE_DOWN_NAME, name, (writedowns,)),
				Entry(WRITE_DOWN_FIELD, amount, (writedowns,)),
			]
			writedowns += 1
	return [*found, *_exempt_holdings(ret, settings)]


def _exempt_holdings(ret: Return, settings: Settings | None) -> list[Entry]:
	"""Anlage GK lines 151 to 155 for each holding whose dividends § 8b Absatz 1 KStG exempts, as steuerbote.kst.form
	writes them: name, share at the start of the calendar year, kind and dividends. The register gives no share bought
	in one acquisition during the year (§ 8b Absatz 4 Satz 6 KStG), so an exempt holding is one held directly at the
	start of the calendar year."""
	found = []
	year = year_of(ret.year)
	trading_book = settings is not None and settings.company.section_8b_7
	for row in ret.holding_results:
		registered = registered_holding(ret.year, row, settings) if row.get("kind") == DIVIDENDS else None
		if registered is None:
			continue
		holding = holding_of(registered)
		if exemption(holding, year, trading_book) is not Exemption.EXEMPT:
			continue
		rows = (len(found) // 4,)
		found += [
			Entry(HOLDING_NAME, holding.name, rows),
			Entry(HOLDING_SHARE, holding.share_at_year_start, rows),
			Entry(HOLDING_KIND, DIRECT, rows),
			Entry(HOLDING_DIVIDENDS, to_amount(row.get("amount")), rows),
		]
	return found


def _receipts(rows: Iterable[Row]) -> list[Entry]:
	"""Anlage Z line 5: each Zuwendungsbestätigung with its recipient, amount and where the recipient lies, and line 9
	with those abroad, rounded down (rules 8901015 and 8901017)."""
	rows = list(rows)
	found = []
	for row_number, row in enumerate(rows):
		found += [
			Entry(DONATION_RECIPIENT, str(row.get("recipient")).strip(), (row_number,)),
			Entry(DONATION_AMOUNT, to_amount(row.get("amount")), (row_number,)),
			Entry(DONATION_ABROAD, ABROAD if row.get("abroad") else INLAND, (row_number,)),
		]
	abroad = [row for row in rows if row.get("abroad")]
	if abroad:
		found.append(Entry(DONATIONS_ABROAD, floor_euro(_sum(row.get("amount") for row in abroad))))
	return found


def _kst1f_details(ret: Return) -> list[Entry]:
	"""The single Leistungen of KSt 1 F lines 3 to 6 with their sum in line 7 and line 13, each with its kind, its day,
	its amount and the reduction of the Einlagekonto certified for it, if need be 0 (rule 8912016), and the single
	Einlagen of lines 200 to 206 that lines 91, 92 and 95 count."""
	found = []
	for row_number, row in enumerate(ret.distributions):
		rows = (row_number,)
		found.append(Entry(DISTRIBUTION_KIND, DISTRIBUTION_KINDS[row.get("kind")], rows))
		for feldkennung, column in (
			(DISTRIBUTION_RESOLVED, "resolution_date"),
			(DISTRIBUTION_OUTFLOW, "outflow_date"),
		):
			if day := _day(row.get(column)):
				found.append(Entry(feldkennung, day, rows))
		found.append(Entry(DISTRIBUTION_AMOUNT, to_amount(row.get("amount")), rows))
		found.append(Entry(DISTRIBUTION_CERTIFIED, to_amount(row.get("certified_reduction")), rows))
	if ret.distributions:
		found.append(Entry(DISTRIBUTIONS_TOTAL, _sum(row.get("amount") for row in ret.distributions)))
		if len(ret.distributions) > 1 and any(
			to_amount(row.get("certified_reduction")) for row in ret.distributions
		):
			found.append(Entry(SEVERAL_CERTIFIED, True))
	counted = [row for row in ret.contributions if row.get("treatment") != UNPAID]
	for row_number, row in enumerate(counted):
		rows = (row_number,)
		found.append(Entry(CONTRIBUTION_NAME, str(row.get("shareholder")).strip(), rows))
		if day := _day(row.get("contribution_date")):
			found.append(Entry(CONTRIBUTION_DATE, day, rows))
		found.append(Entry(CONTRIBUTION_KIND, CONTRIBUTION_KINDS[row.get("kind") or CASH], rows))
		if row.get("kind") == IN_KIND:
			found.append(Entry(CONTRIBUTION_DESCRIPTION, str(row.get("description")).strip(), rows))
	return found


# Helpers.


def _single_value_kind(row: Row) -> object:
	kind = row.get("kind")
	if kind == SALE:
		return GAIN if sale_result(row) > ZERO else LOSS
	return kind


def _in_the_year(ret: Return, row: Row, column: str, where: tuple[str, object], translate: Translate) -> date:
	"""The day of a column of a row, which has to lie in the Wirtschaftsjahr (rules 8920296 and 8920293)."""
	day = _day(row.get(column))
	if day is None or not ret.from_date <= day <= ret.to_date:
		raise BridgeError(
			DAY_OUTSIDE,
			*where,
			translate(LABELS[column]),
			ret.from_date.strftime("%d.%m.%Y"),
			ret.to_date.strftime("%d.%m.%Y"),
		)
	return day


def _persons(ret: Return, shareholders: Iterable[rules.Shareholder]) -> dict[str, list[rules.Shareholder]]:
	"""The holding periods of the Wirtschaftsjahr, by the name of the Anteilseigner."""
	persons: dict[str, list[rules.Shareholder]] = {}
	for shareholder in shareholders:
		if shareholder.from_date <= ret.to_date and (
			shareholder.to_date is None or shareholder.to_date >= ret.from_date
		):
			persons.setdefault(_name_key(shareholder.name), []).append(shareholder)
	return persons


def _name_key(name: object) -> str:
	return " ".join(str(name or "").casefold().split())


def _day(value: object) -> date | None:
	"""A date field as a date: Frappe hands one out as a date or, after a save in the same request, as its text."""
	if not value:
		return None
	if isinstance(value, date):
		return value
	return date.fromisoformat(str(value)[:10])


def _sum(values: Iterable[object]) -> Decimal:
	return sum((to_amount(value) for value in values), ZERO)


def _option(value: object, options: Iterable[str], where: tuple[str, object]) -> None:
	if value not in options:
		raise BridgeError(NOT_AN_OPTION, *where, value)


def _positive(value: object, where: tuple[str, object], euros: bool = False) -> None:
	amount = to_amount(value)
	if amount <= ZERO:
		raise BridgeError(NOT_POSITIVE, *where)
	if euros and amount != amount.to_integral_value():
		raise BridgeError(ROW_NOT_IN_EUROS, *where)


def _not_negative(value: object, where: tuple[str, object], label: str) -> None:
	if to_amount(value) < ZERO:
		raise BridgeError(ROW_NEGATIVE, *where, label)


def _error(code: str, text: str, reference: str) -> Finding:
	return Finding(code, Severity.ERROR, text, reference[:140])
