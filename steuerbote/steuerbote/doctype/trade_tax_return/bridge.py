"""The Gewerbesteuererklärung of a company in ERPNext and the core of steuerbote.gewst, converted without Frappe.

There is one computation (research of stage 3, KSt note 5.1): the Trade Tax Return builds on the Körperschaftsteuer
of the Corporate Income Tax Return of its company and year, whose result steuerbote.gewst.chain takes, and adds what
the settings say of the Gewerbesteuer. The forms are those of steuerbote.gewst.form, for 2026 provisionally those of
Jahresdokumentation_E20_2025.ods of the ERiC documentation 44.3.6.0 (steuerbote.gewst.years).

What the core takes beside the Körperschaftsteuer (compute): the Hebesatz of the Gemeinde of the only Betriebsstätte
in the Erhebungszeitraum, with its source in the Annual Filing Settings (adopted answer Q14 of the research), the
Fehlbetrag of § 10a GewStG and the Zuwendungsvortrag of the last notices, which count once confirmed, and the
Vorauszahlungen of the notices of § 19 GewStG, which the core takes rather than the ledger (adopted Q6). Steuerbote
files for one Betriebsstätte in one Gemeinde (adopted Q7); none or more hold the return back until a Zerlegung
(GewSt 1 D) exists.

What the return keeps: the rows of the table of lines are the amounts of GewSt 1 A that steuerbote.gewst.form gives
for the result, with those the settings add (line 94 with the turnover and wages the Körperschaftsteuer states, 0 too, lines
148 and 150 with the carry-forwards of the previous Erhebungszeitraum); an Anlage BEG of each holding of
GewstResult.beg is a row of the table of holdings, the Gemeinde a row of the table of Gemeinden. The return takes no
correction and no line by hand: line 39 follows from the Summe der Einkünfte of the Körperschaftsteuer, before the
Termingeschäfte of § 15 Absatz 4 EStG (steuerbote.gewst.chain), and the other lines come from the Income Tax Mapping,
so a correction belongs there. filed_vordrucke() makes the Vordrucke again from the
rows as stored, with GewSt 1 A lines 3 to 33 from the settings and the Zuwendungsbestätigungen of lines 92a to 92c
that the Körperschaftsteuer lists.

What holds the return back, beside the findings of the core: the forms of a provisional EZ, none or more than one
Betriebsstätte, missing Gegenstand des Unternehmens or Rechtsform, a carry-forward that is not confirmed or not in
whole euros, and every error of the Körperschaftsteuer it builds on but the forms of its year, which this return
states for its own. A hint names Vorauszahlungen of the settings that differ from those booked.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from steuerbote.elster import gewst_xml
from steuerbote.eric.datenart import gewst as gewst_datenart
from steuerbote.eric.simulation import gewst as gewst_rules
from steuerbote.gewst.chain import STEPS, GewstInputs, GewstResult
from steuerbote.gewst.chain import compute as compute_gewst
from steuerbote.gewst.form import BEG_LINES, catalogue_for, vordrucke
from steuerbote.gewst.years import year_of
from steuerbote.jahresmeldung.findings import Finding
from steuerbote.jahresmeldung.overrides import Columns, to_amount
from steuerbote.kst.chain import Source
from steuerbote.kst.form import Entry, Vordruck
from steuerbote.steuerbote.doctype.annual_filing_settings import rules
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge as kst
from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import ZERO, half_up_euro, to_cents

type Row = kst.Row
type Translate = kst.Translate

LINE_COLUMNS = Columns(
	key="feldkennung",
	amounts=("form_amount", "ledger_amount"),
	described=("form", "line", "label"),
)
"""The columns of the table of lines, as those of the Körperschaftsteuererklärung."""

PARAGRAPHS = MappingProxyType({1: "§ 9 Nr. 2a GewStG", 2: "§ 9 Nr. 7 GewStG"})
"""The Kürzung of Anlage BEG line 7 (E4050701) as the table of holdings shows it: 1 § 9 Nummer 2a, 2 § 9 Nummer 7."""
_PARAGRAPH_KEYS = MappingProxyType({label: str(key) for key, label in PARAGRAPHS.items()})
CARRY_FORWARDS = MappingProxyType(
	{
		"loss_carry_forward": rules.CarryForwardKind.FEHLBETRAG,
		"donation_carry_forward": rules.CarryForwardKind.DONATIONS_GEWST,
	}
)
"""The carry-forwards of GewstInputs by the kind of the Annual Filing Settings."""
TAXES = ("GewSt",)

# GewSt 1 A by the Feldkennungen of Jahresdokumentation_E20_2025.ods, sheet „GewSt1A - Felder“.
COMPANY_NAME, BUSINESS_PURPOSE, WID_NR, RECHTSFORM = "E4000101", "E4000201", "E4000502", "E4000501"
SUPPLEMENT_KEY, SUPPLEMENT_TEXT = "E4003204", "E4003205"
SEVERAL_MUNICIPALITIES, MOVED = "E4001506", "E4001102"
POSTAL_CODE, PLACE, HEBENUMMER = "E4001110", "E4001111", "E4001803"
TURNOVER_AND_WAGES = "E4004001"
LOSS_CARRY_FORWARD, DONATION_CARRY_FORWARD = "E4014801", "E4015001"
RECEIPT_RECIPIENT, RECEIPT_AMOUNT, RECEIPT_ABROAD = "E4009220", "E4009221", "E4009222"
# Anlage BEG, sheet „BEG - Felder“.
BEG_NAME, BEG_DIVIDENDS, BEG_PARAGRAPH = "E4050201", "E4050601", "E4050701"
BEG_FINANCING_COSTS, BEG_OTHER_COSTS, BEG_EXEMPT, BEG_NOT_EXEMPT = (
	"E4050801",
	"E4050901",
	"E4051201",
	"E4051401",
)
BEG_COLUMNS = MappingProxyType(
	{
		"addback": "addback",
		"cut_base": "cut_base",
		"financing_costs": "cut_financing_costs",
		"other_costs": "cut_other_costs",
		"cut": "cut",
	}
)
"""The columns of the table of holdings that hold Anlage BEG lines 15 to 19, by the attribute of BegLine."""

PROVISIONAL = "GEWST-VORLAEUFIG"
ESTABLISHMENTS = "GEWST-BETRIEBSSTAETTE"
DETAILS_MISSING = "GEWST-ANGABEN-FEHLEN"
UNCONFIRMED = "GEWST-VORTRAG-UNBESTAETIGT"
NOT_IN_EUROS = "GEWST-VORTRAG-CENT"
PREPAYMENTS = "GEWST-VORAUSZAHLUNGEN"
NUTZDATEN = "GEWST-NUTZDATEN"
CODES = (PROVISIONAL, ESTABLISHMENTS, DETAILS_MISSING, UNCONFIRMED, NOT_IN_EUROS, PREPAYMENTS, NUTZDATEN)
"""The codes of the findings of this module, beside those of the core, of the Körperschaftsteuer it builds on and the
Fehlercodes of the rules."""

NO_ESTABLISHMENT_TEXT = (
	"The Annual Filing Settings name no Betriebsstätte in {0}: GewSt 1 A lines 26 to 33 need the Gemeinde of the one "
	"Betriebsstätte."
)
SEVERAL_ESTABLISHMENTS_TEXT = (
	"The Annual Filing Settings name {0} Betriebsstätten in {1}. Steuerbote files the Gewerbesteuererklärung of one "
	"Betriebsstätte in one Gemeinde; a Zerlegung (GewSt 1 D) it does not compute."
)
DETAILS_MISSING_TEXT = "The Annual Filing Settings of {0} lack what GewSt 1 A needs: {1}."
NOT_CORRECTED = (
	"The Gewerbesteuererklärung takes no correction and no line by hand: line 39 follows from the "
	"Körperschaftsteuererklärung and the other lines come from the Income Tax Mapping, so correct them there."
)
NO_CORPORATE_INCOME_TAX_RETURN = "{0} has no Körperschaftsteuererklärung for {1}: the Gewerbesteuererklärung builds on it, so make it first."
OTHER_KEY = "{0} is the Körperschaftsteuererklärung of {1} for {2}, not of {3} for {4}."
MESSAGES = (
	NO_ESTABLISHMENT_TEXT,
	SEVERAL_ESTABLISHMENTS_TEXT,
	DETAILS_MISSING_TEXT,
	NOT_CORRECTED,
	NO_CORPORATE_INCOME_TAX_RETURN,
	OTHER_KEY,
)
"""Every text of this module, which the Frappe layer translates; the findings it shares with the
Körperschaftsteuererklärung take the texts of steuerbote/steuerbote/doctype/corporate_income_tax_return/bridge.py."""
LABELS = MappingProxyType({"business_purpose": "Business Purpose", "rechtsform": "Legal Form"})


@dataclass(frozen=True, slots=True)
class Return:
	"""The Gewerbesteuererklärung as stored: its EZ and Wirtschaftsjahr and the qualified free text of § 150 Absatz 7
	Satz 1 AO in GewSt 1 A line 21 (E4003204 and E4003205, filed together or not at all: rule 40128)."""

	year: int
	from_date: date
	to_date: date
	supplement_key: str | None = None
	supplement_text: str | None = None

	@property
	def opening_day(self) -> date:
		return kst.Return(self.year, self.from_date, self.to_date).opening_day


@dataclass(frozen=True, slots=True)
class Computation:
	"""What Berechnen gives: the result of the core, the rows of the tables of lines, Gemeinden and holdings, the
	values of the fields of the return and the findings."""

	result: GewstResult
	lines: list[dict[str, Any]]
	municipalities: list[dict[str, Any]]
	holdings: list[dict[str, Any]]
	values: dict[str, Decimal]
	findings: tuple[Finding, ...]


def compute(
	ret: Return,
	corporate: kst.Computation,
	ledger: kst.Ledger,
	settings: kst.Settings | None,
	figures: Figures,
	translate: Translate,
) -> Computation:
	"""Berechnen of the Gewerbesteuererklärung on the Körperschaftsteuer of its year; see the module docstring."""
	found: list[Finding] = []
	carry_forwards = {
		name: kst.carry_forward(
			settings.carry_forwards if settings else (),
			kind,
			ret.opening_day,
			figures,
			translate,
			found,
			(UNCONFIRMED, NOT_IN_EUROS),
		)
		for name, kind in CARRY_FORWARDS.items()
	}
	establishment = _establishment(ret, settings, translate, found)
	rate = rules.hebesatz_of(settings.trade_tax_rates, establishment.ags, ret.year) if establishment else None
	inputs = GewstInputs(
		rate.hebesatz if rate else None,
		prepayments=kst.prepayments_of(ret.year, settings)["GewSt"],
		**carry_forwards,
	)
	result = compute_gewst(corporate.result, inputs, figures)
	gewst_1a, *_ = vordrucke(result)
	added = _carry_forward_lines(carry_forwards)
	turnover = corporate.result.donations.turnover_and_wages
	if turnover is not None:
		added.append(Entry(TURNOVER_AND_WAGES, turnover))
	lines = line_rows(result, gewst_1a.extended(*added))
	found[:0] = kst.findings_of(result.findings)
	found.extend(_readiness(ret, corporate, ledger, settings, figures, translate))
	return Computation(
		result,
		lines,
		[_municipality(establishment, rate, result)] if establishment else [],
		[holding_row(line) for line in result.beg],
		values_of(result),
		tuple(found),
	)


def line_rows(result: GewstResult, gewst_1a: Vordruck) -> list[dict[str, Any]]:
	"""The rows of the table of lines: each amount of GewSt 1 A outside a repeated context, in the order of the
	catalogue, with its line and Beschreibung and, for a line of the books, the amount of the books."""
	catalogue = catalogue_for(result.year.year)
	steps = {step.field: step for step in STEPS if step.field}
	ranks = {item.feldkennung: rank for rank, item in enumerate(catalogue.fields)}
	rows = []
	for entry in gewst_1a.entries:
		if entry.rows or not isinstance(entry.value, Decimal):
			continue
		step = steps.get(entry.feldkennung)
		books = step is not None and step.source is Source.LEDGER
		rows.append(
			{
				**kst.describe(kst.shown(catalogue.field(entry.feldkennung), result.year.year)),
				"form_amount": entry.value,
				"ledger_amount": result.lines[step.key].exact if books else ZERO,
			}
		)
	return sorted(rows, key=lambda row: ranks[row["feldkennung"]])


def holding_row(line: Any) -> dict[str, Any]:
	"""A row of the table of holdings: Anlage BEG of a holding (steuerbote.gewst.chain.BegLine), lines 2, 6 to 9, 12
	and 14 to 19."""
	holding = line.holding.result
	paragraph = line.paragraph
	return {
		"holding_name": holding.holding.name,
		"paragraph": PARAGRAPHS.get(paragraph, "") if paragraph is not None else "",
		"dividends": line.dividends,
		"financing_costs": half_up_euro(holding.financing_costs) if paragraph is not None else ZERO,
		"other_costs": half_up_euro(holding.other_costs) if paragraph is not None else ZERO,
		"exempt": line.exempt,
		"not_exempt": line.not_exempt,
		**{column: getattr(line, attribute) for attribute, column in BEG_COLUMNS.items()},
	}


def values_of(result: GewstResult) -> dict[str, Decimal]:
	"""The fields of the computation of the return; the Hinzurechnung of § 8 Nummer 1 GewStG in cents, which only the
	provision needs, as the Finanzamt computes it from the parts declared in full."""
	return {
		"profit": result.lines["profit"].declared,
		"financing_addback": to_cents(result.lines["financing_addback"].declared),
		"gewerbeertrag": result.gewerbeertrag,
		"messbetrag": result.messbetrag,
		"hebesatz": result.hebesatz or ZERO,
		"gewst": result.gewst,
		"prepayments": result.lines["prepayments"].declared,
		"balance": result.balance,
	}


def filed_vordrucke(
	ret: Return,
	rows: Iterable[Row],
	holdings: Iterable[Row],
	municipalities: Iterable[Row],
	donations: Iterable[Row],
	settings: kst.Settings | None,
) -> tuple[Vordruck, ...]:
	"""The Vordrucke the return files: GewSt 1 A from its lines as stored, the settings and the receipts of the
	Zuwendungen, and an Anlage BEG of each row of the table of holdings."""
	catalogue = catalogue_for(ret.year)
	entries = general_entries(ret, settings, municipalities)
	for row in rows:
		item = catalogue.field(kst.normalized(row.get("feldkennung")))
		amount = to_amount(row.get("reported"))
		if amount or item.format not in kst.ZERO_REFUSED:
			entries.append(Entry(item.feldkennung, amount))
	for number, row in enumerate(donations):
		entries += [
			Entry(RECEIPT_RECIPIENT, str(row.get("recipient")).strip(), (number,)),
			Entry(RECEIPT_AMOUNT, to_amount(row.get("amount")), (number,)),
			Entry(RECEIPT_ABROAD, kst.ABROAD if row.get("abroad") else kst.INLAND, (number,)),
		]
	return (Vordruck("GewSt1A", tuple(entries)), *(beg_vordruck(row) for row in holdings))


def general_entries(ret: Return, settings: kst.Settings | None, municipalities: Iterable[Row]) -> list[Entry]:
	"""GewSt 1 A lines 3 to 33: the company, its Gegenstand and Rechtsform, the qualified free text, and the one
	Betriebsstätte in one Gemeinde that did not move, with its Postleitzahl, place and Hebenummer (rules 40038, 40047
	and 40029)."""
	found = []
	company = settings.company if settings else None
	if company is not None:
		for feldkennung, value in (
			(COMPANY_NAME, company.name),
			(BUSINESS_PURPOSE, company.business_purpose),
			(WID_NR, company.wid_nr),
			(RECHTSFORM, company.rechtsform),
		):
			if value:
				found.append(Entry(feldkennung, value))
	if ret.supplement_key:
		found.append(Entry(SUPPLEMENT_KEY, ret.supplement_key))
	if (ret.supplement_text or "").strip():
		found.append(Entry(SUPPLEMENT_TEXT, ret.supplement_text.strip()))
	found += [Entry(SEVERAL_MUNICIPALITIES, False), Entry(MOVED, False)]
	for row in list(municipalities)[:1]:
		for feldkennung, column in (
			(POSTAL_CODE, "postal_code"),
			(PLACE, "municipality"),
			(HEBENUMMER, "hebenummer"),
		):
			if value := str(row.get(column) or "").strip():
				found.append(Entry(feldkennung, value))
	return found


def beg_vordruck(row: Row) -> Vordruck:
	"""Anlage BEG of a row of the table of holdings, as steuerbote.gewst.form writes it: the name and the dividends, the
	Kürzung of line 7 with the costs of lines 8 and 9 that are not zero, line 12 beside line 14, and lines 14 to 19
	that are not zero (rules 40921, 40933 and 40969)."""
	entries = [
		Entry(BEG_NAME, str(row.get("holding_name")).strip()),
		Entry(BEG_DIVIDENDS, to_amount(row.get("dividends"))),
	]
	paragraph = _PARAGRAPH_KEYS.get(str(row.get("paragraph") or ""))
	if paragraph:
		entries.append(Entry(BEG_PARAGRAPH, paragraph))
		for feldkennung, column in (
			(BEG_FINANCING_COSTS, "financing_costs"),
			(BEG_OTHER_COSTS, "other_costs"),
		):
			if costs := to_amount(row.get(column)):
				entries.append(Entry(feldkennung, costs))
	exempt, not_exempt = to_amount(row.get("exempt")), to_amount(row.get("not_exempt"))
	if exempt or not_exempt:
		entries.append(Entry(BEG_EXEMPT, exempt))
	if not_exempt:
		entries.append(Entry(BEG_NOT_EXEMPT, not_exempt))
	columns = dict(BEG_COLUMNS)
	for attribute, feldkennung in BEG_LINES:
		if amount := to_amount(row.get(columns[attribute])):
			entries.append(Entry(feldkennung, amount))
	return Vordruck("BEG", tuple(entries))


def rule_findings(year: int, filed: Iterable[Vordruck], translate: Translate) -> list[Finding]:
	"""The rules of the Jahresdokumentation E20 that Steuerbote checks itself (steuerbote.eric.simulation.gewst.RULES)
	on the Vordrucke as filed, each with its Fehlercode."""
	return kst.checked_rules(
		gewst_xml.to_nutzdaten, gewst_rules.RULES, gewst_datenart(year), filed, translate, NUTZDATEN
	)


def provisional(year: int) -> tuple[bool, int]:
	"""Whether the EZ takes the forms of an earlier Jahresdokumentation E20, and the year of the one it takes."""
	data = year_of(year)
	return data.provisional, data.documentation_year


def taken_over(corporate: kst.Computation) -> list[Finding]:
	"""The errors of the Körperschaftsteuer that hold the Gewerbesteuer back too: its Gewinn is the Summe der Einkünfte
	of the Körperschaftsteuer and its Anlagen BEG come from the holdings of the same computation. The forms of the
	year are the one error this return states for its own."""
	return [finding for finding in corporate.findings if finding.blocking and finding.code != kst.PROVISIONAL]


def _readiness(
	ret: Return,
	corporate: kst.Computation,
	ledger: kst.Ledger,
	settings: kst.Settings | None,
	figures: Figures,
	translate: Translate,
) -> list[Finding]:
	found = []
	is_provisional, documentation_year = provisional(ret.year)
	if is_provisional:
		found.append(kst.provisional_finding(PROVISIONAL, ret.year, documentation_year, translate))
	found.extend(taken_over(corporate))
	if settings is None:
		return found
	company = settings.company
	missing = [
		translate(LABELS[name]) for name in ("business_purpose", "rechtsform") if not getattr(company, name)
	]
	if missing:
		text = translate(DETAILS_MISSING_TEXT).format(company.name, ", ".join(missing))
		found.append(kst.error(DETAILS_MISSING, text, "GewSt 1 A Zeilen 4 und 14"))
	found.extend(
		kst.booked_prepayment_findings(ret.year, ledger, settings, TAXES, figures, translate, PREPAYMENTS)
	)
	return found


def _establishment(
	ret: Return, settings: kst.Settings | None, translate: Translate, found: list[Finding]
) -> rules.Establishment | None:
	"""The one Betriebsstätte of the Erhebungszeitraum; a finding for none or more."""
	if settings is None:
		return None
	present = rules.establishments_in(settings.establishments, ret.from_date, ret.to_date)
	if len(present) == 1:
		return present[0]
	if present:
		text = translate(SEVERAL_ESTABLISHMENTS_TEXT).format(len(present), ret.year)
	else:
		text = translate(NO_ESTABLISHMENT_TEXT).format(ret.year)
	found.append(kst.error(ESTABLISHMENTS, text, "§§ 28 bis 31 GewStG; GewSt 1 A Zeilen 26 bis 33"))
	return None


def _municipality(
	establishment: rules.Establishment, rate: rules.TradeTaxRate | None, result: GewstResult
) -> dict[str, Any]:
	"""The row of the Gemeinde of the Betriebsstätte: its AGS, its Hebesatz with the source, and the Messbetrag, the
	Gewerbesteuer, the Vorauszahlungen and the Abschlusszahlung, all of which fall to it (§ 4 Absatz 1 GewStG)."""
	return {
		"municipality": establishment.municipality,
		"postal_code": establishment.postal_code,
		"ags": establishment.ags,
		"hebenummer": establishment.hebenummer or "",
		"hebesatz": rate.hebesatz if rate else ZERO,
		"hebesatz_source": rate.source if rate else "",
		"messbetrag": result.messbetrag,
		"gewst": result.gewst,
		"prepayments": result.lines["prepayments"].declared,
		"balance": result.balance,
	}


def _carry_forward_lines(carry_forwards: dict[str, Decimal]) -> list[Entry]:
	"""GewSt 1 A lines 148 and 150: the Fehlbetrag and the Zuwendungsvortrag assessed for the previous Erhebungszeitraum,
	where there is one."""
	found = []
	for name, feldkennung in (
		("loss_carry_forward", LOSS_CARRY_FORWARD),
		("donation_carry_forward", DONATION_CARRY_FORWARD),
	):
		if carry_forwards[name]:
			found.append(Entry(feldkennung, carry_forwards[name]))
	return found
