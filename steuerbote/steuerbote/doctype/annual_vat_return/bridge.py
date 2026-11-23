"""Pure Python between the Annual VAT Return and the core of the Umsatzsteuererklärung in steuerbote.ustjahr.

Nothing here imports Frappe. The controller (annual_vat_return.py) reads the sources through
steuerbote/ustjahr_sources.py, runs the core and keeps what it computed in the lines, tables and fields of the
document; this module turns the one into the other, so that every rule is tested without a bench:

- year_periods: the Voranmeldungszeiträume of the year as the VAT Return Settings set them, and a month of its own
  for every month that owes no Voranmeldung, so that the runs of the periods read the ledger of the whole year, which
  the annual return covers (§ 18 Absatz 3 Satz 1 UStG: „für das Kalenderjahr“); periods_to_run adds a filed period
  the settings no longer set;
- line_rows, filed_amounts, manual_lines and corrected: the lines of the return from AnnualResult, what they file,
  the lines by hand the computation takes in and the corrections of the company before Berechnen keeps them;
- soll_override, waived and waivers_kept: the Vorauszahlungssoll the Finanzamt set and the periods the company files
  the return without a Voranmeldung for, each with its reason;
- period_rows, reconciliation_rows and own_findings: the tables of the reconciliation with the filed Voranmeldungen,
  and the findings of the Verprobung and of the watched accounts; findings turns every finding of the core into one
  of the table Befunde;
- sums and filed_values: the sums of the form as the document keeps them, and the values the return files, with the
  details of the company (details) and the Grundstücke of line 95 (grundstuecke, check_grundstuecke);
- journal_entry_lines and payment_accounts: what the hints on Journal Entries and on the payments read.

Messages are English templates with positional placeholders, kept apart from their values as in the core, so that
the Frappe layer translates the template before it formats it; MESSAGES lists them for the translations.
"""

import re
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from steuerbote.elster import ust2a_xml
from steuerbote.elster.erklaerung import NOT_IN_FORMAT, python_pattern, value_text
from steuerbote.elster.ustva_xml import XmlError
from steuerbote.jahresmeldung import corrections
from steuerbote.jahresmeldung.findings import DATA_LENGTH
from steuerbote.jahresmeldung.findings import Finding as AnnualFinding
from steuerbote.jahresmeldung.findings import Severity as AnnualSeverity
from steuerbote.jahresmeldung.overrides import Columns, correction_of, reported, to_amount
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import Address
from steuerbote.steuerbote.doctype.vat_return_settings import rules as settings_rules
from steuerbote.ustjahr.calculation import (
	MANUAL_NO_PARAGRAPH,
	MANUAL_NOT_FED,
	AnnualResult,
	CalculationError,
	ManualLine,
	business_period,
	entries,
)
from steuerbote.ustjahr.form import (
	GRUNDSTUECKE,
	KZ_816,
	KZ_820,
	SOLL,
	Catalogue,
	Field,
	Finding,
	Severity,
	catalogue_for,
)
from steuerbote.ustjahr.reconciliation import Cause, Reconciliation
from steuerbote.ustjahr.rules import DIGITS_BEFORE_THE_COMMA, MORE_DIGITS_BEFORE_THE_COMMA
from steuerbote.ustjahr.soll import SOLL as SOLL_SUBJECT
from steuerbote.ustjahr.soll import WITHOUT_REASON, Filed, FiledKennzahl, Override, SollError
from steuerbote.ustjahr.split import Split
from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.kennzahlen import catalogue_for as ustva_catalogue_for
from steuerbote.ustva.period import Period
from steuerbote.ustva.rounding import ZERO, to_cents

MONTHS_PER_YEAR = 12
LINE_COLUMNS = Columns(
	key="feldkennung",
	amounts=("form_amount", "ledger_amount"),
	described=("label", "kennzahl", "line", "formatkennzeichen", "ustva", "paragraph"),
	correction="correction",
	reason="correction_reason",
	reported="reported",
	manual="manual",
)
"""The columns of the table Zeilen: the Feldkennung, the amount of the form and that of the ledger, what describes the
line, the correction with its reason, the amount it files and the mark of a line by hand (steuerbote.jahresmeldung
.overrides)."""

# The fields of the document that keep the sums of the form, each by the Feldkennung of its line.
SUM_FIELDS = MappingProxyType(
	{
		"line_41": "E3006001",
		"line_50": "E3104201",
		"line_62": "E3101501",
		"line_64": "E3102904",
		"line_70": "E3102401",
		"line_74": "E3102601",
		"line_93": "E3006901",
		"line_108_deductible": "E3008901",
		"line_108_repayable": "E3008902",
		"line_109": "E3009201",
		"line_110": "E3009401",
		"line_111": "E3009602",
		"line_112": "E3009501",
		"line_113": "E3009502",
		"line_114": "E3009801",
		"line_115": "E3009901",
		"line_116": "E3010001",
		"line_117": "E3010201",
		"line_118": "E3009701",
		"line_122": "E3010601",
		"kz816": KZ_816,
		"vorauszahlungssoll": SOLL,
		"kz820": KZ_820,
	}
)

# What the company states on the return itself, by the field of the document and the Feldkennung of form USt 2 A:
# Kz 129 in line 22 and the questions and reasons of § 15a UStG in lines 95 to 104, yes fields and crosses
# (Formatkennzeichen J and X, JD sheet „Allg. Information“).
FLAGS = MappingProxyType(
	{
		"kz129": "E3001701",
		"kz370": "E3007301",
		"kz371": "E3007601",
		"kz372": "E3008501",
		"kz369": "E3008601",
		"change_by_sale": "E3007801",
		"change_by_withdrawal": "E3007802",
		"change_of_taxation": "E3007803",
		"change_of_small_business": "E3007804",
		"change_of_use": "E3007901",
		"change_of_letting": "E3008001",
		"change_of_own_use": "E3008202",
		"change_for_other_reasons": "E3008401",
	}
)
# Kz 500 in line 23, its text, the reason of line 104, and Kz 136, the day of the switch from the
# Kleinunternehmer-Regelung in line 18.
TEXTS = MappingProxyType(
	{"kz500": "E3002201", "kz500_text": "E3002202", "change_reason": "E3008402", "kz136": "E3001601"}
)
STATEMENT_FIELDS = (*FLAGS, *TEXTS)
"""The fields of the document that the return files as the statements of the company."""

KZ_110 = corrections.berichtigung_of("USt").fields[0]
KZ_133 = "E3002203"
SOLL_VERSTEUERUNG = "1"
"""Kz 133, „Die Steuer wurde berechnet nach 1 = vereinbarten Entgelten (§ 16 Absatz 1 Satz 1 UStG)“: the VAT Return
Settings know the Soll-Versteuerung only (taxation_type)."""
BUSINESS_PERIOD = "E3001401"
"""Line 19, the first span of the „Dauer der Unternehmereigenschaft (falls nicht vom 1. Januar bis zum 31. Dezember)“."""
MITWIRKUNG = "E3002602"
"""Line 127: „Die Steuererklärung wurde unter Mitwirkung einer selbständig und eigenverantwortlich tätigen und zur
Hilfeleistung in Steuersachen nach §§ 3 und 4 des Steuerberatungsgesetzes befugten Person oder Vereinigung
angefertigt.“"""

# The Grundstücke of line 95 by the column of the table and the Feldkennung of the context Ang_Grdst.
GRUNDSTUECK_FIELDS = MappingProxyType(
	{
		"location": "E3007401",
		"first_use": "E3007402",
		"kind_of_use": "E3007403",
		"extent_of_use": "E3007404",
		"input_tax_total": "E3007405",
		"input_tax_deducted": "E3007406",
	}
)
GRUNDSTUECK_AMOUNTS = frozenset({"extent_of_use", "input_tax_total", "input_tax_deducted"})
FIRST_USE = "first_use"

# The accounts of the Vorauszahlungen paid to the Finanzamt, the Sondervorauszahlung included: DATEV Kontenrahmen
# 2026, SKR 03 „1780 Umsatzsteuer-Vorauszahlungen“ and „1781 Umsatzsteuer-Vorauszahlungen 1/11“, SKR 04 3820 and
# 3830 of the same names. The defaults of the Voranmeldung leave them without Kennzahl for that reason
# (steuerbote/ustva/defaults.py).
PAYMENT_ACCOUNTS = MappingProxyType({"SKR03": ("1780", "1781"), "SKR04": ("3820", "3830")})
# The cause of the difference of a period, as the table Voranmeldungszeiträume names it.
CAUSES = MappingProxyType(
	{
		Cause.NONE: "No Difference",
		Cause.LATE_POSTINGS: "Late Postings",
		Cause.CORRECTIONS: "Corrections without Posting",
		Cause.LATE_POSTINGS_AND_CORRECTIONS: "Late Postings and Corrections",
		Cause.NOT_FILED: "Not Filed",
	}
)
JOURNAL_ENTRY = "Journal Entry"
MORE = ", …"

VERPROBUNG = (
	"The Verprobung {0} does not pass over the year: {1} vouchers book another tax than their bases give, "
	"{2} euros in all."
)
BLOCKED = (
	"Account {0} is watched at the blocking level and has a balance in {1} that goes into no line of the return: "
	"map it, or give it a row for the annual return only."
)
WATCHED = "Account {0} is watched for a hint and has a balance of {1} euros in {2} that goes into no line of the return."
KLEINUNTERNEHMER = (
	"The Annual Filing Settings mark {0} as a year of a Kleinunternehmer, who owes no Umsatzsteuererklärung "
	"(§ 19 Absatz 1 Satz 2 UStG) unless the Finanzamt asks for one (§ 149 Absatz 1 Satz 2 AO)."
)
SWITCH_MISSING = (
	"A filed Voranmeldung of {0} dates the switch from the Kleinunternehmer-Regelung to the Regelbesteuerung (Kz 70) "
	"on {1}, but Kz 136 of the return names no day: give Kz 136 the day of the switch."
)
SWITCH_OTHER = (
	"A filed Voranmeldung of {0} dates the switch from the Kleinunternehmer-Regelung to the Regelbesteuerung (Kz 70) "
	"on {1}, but Kz 136 of the return on {2}: give Kz 136 the day of the switch."
)
MESSAGES = (VERPROBUNG, BLOCKED, WATCHED, KLEINUNTERNEHMER, SWITCH_MISSING, SWITCH_OTHER)


@dataclass(frozen=True, slots=True)
class YearPeriod:
	"""A Voranmeldungszeitraum of the year, and whether the settings require a Voranmeldung for it."""

	period: Period
	due: bool


@dataclass(frozen=True, slots=True)
class Company:
	"""What section A of form USt 2 A says of the company: the name, the W-IdNr. of line 4, the Art des Unternehmens of
	line 7, the address of lines 8 to 13, and phone and email of lines 14 and 15."""

	name: str
	wid_nr: str | None = None
	business_purpose: str | None = None
	address: Address | None = None
	phone: str | None = None
	email: str | None = None


@dataclass(frozen=True, slots=True)
class Advisor:
	"""The Steuerberatung that takes part in the return of the year, lines 128 and 129 (Mitwirk of the JD), as the
	Annual Filing Settings hold it."""

	name: str | None = None
	first_name: str | None = None
	street: str | None = None
	town: str | None = None
	phone: str | None = None
	details: str | None = None
	client_number: str | None = None
	clerk: str | None = None


# The Feldkennungen of the Steuerberatung by the attribute of Advisor (JD sheet "USt2A - Felder", context Mitwirk).
_ADVISOR_FIELDS = MappingProxyType(
	{
		"clerk": "E3002509",
		"client_number": "E3002506",
		"name": "E3002501",
		"first_name": "E3002502",
		"street": "E3002503",
		"town": "E3002504",
		"phone": "E3002505",
		"details": "E3002508",
	}
)


def year_periods(
	period_rules: Iterable[settings_rules.PeriodRule], year: int, began: date | None = None
) -> tuple[YearPeriod, ...]:
	"""The Voranmeldungszeiträume of ``year`` in their order, each month in one of them.

	A month takes the period of the rules of the VAT Return Settings (rhythm_for); a month they exempt from the
	Voranmeldungen or that comes before their first rule is a month of its own, for which no Voranmeldung is due
	(§ 18 Absatz 2 Satz 3 UStG lets the Finanzamt exempt a company). Neither is a period that ends before the company
	began, ``began``, since a Voranmeldung is due for the time a company is a Unternehmer (§ 18 Absatz 1 and § 16
	Absatz 3 UStG).
	"""
	periods: dict[Period, bool] = {}
	for month in range(1, MONTHS_PER_YEAR + 1):
		first = date(year, month, 1)
		try:
			rhythm = settings_rules.rhythm_for(period_rules, year, month)
		except settings_rules.SettingsError:
			periods.setdefault(Period.month(year, month), False)
			continue
		period = Period.containing(first, rhythm)
		periods.setdefault(period, began is None or period.end >= began)
	return tuple(YearPeriod(period, due) for period, due in periods.items())


def due_periods(periods: Iterable[YearPeriod]) -> tuple[Period, ...]:
	return tuple(entry.period for entry in periods if entry.due)


def periods_to_run(periods: Iterable[YearPeriod], filed: Iterable[Filed]) -> tuple[Period, ...]:
	"""The periods to run the Voranmeldung on today's ledger for: those of the year, and each filed one the settings
	no longer set, in the order of their start. The reconciliation needs a run for every filed period."""
	known = [entry.period for entry in periods]
	extra = [entry.period for entry in filed if entry.period not in known]
	return tuple(sorted(dict.fromkeys((*known, *extra)), key=lambda period: (period.start, period.end)))


def filed_kennzahlen(rows: Iterable[Mapping[str, Any]]) -> dict[str, FiledKennzahl]:
	"""The Kennzahlen of a filed VAT Return from the rows of its table Kennzahlen: the amount of the ledger when it was
	filed (amount), that of the form (reported) and what it filed after the corrections of the company (final)."""
	return {
		str(row.get("kennzahl")): FiledKennzahl(
			to_amount(row.get("amount")), to_amount(row.get("reported")), to_amount(row.get("final"))
		)
		for row in rows
		if row.get("kennzahl")
	}


def latest_per_period(filed: Iterable[Filed]) -> tuple[Filed, ...]:
	"""The filing that counts for each period, from filings listed the latest first: a corrected Voranmeldung (Kz 10)
	files its period anew."""
	latest: dict[Period, Filed] = {}
	for entry in filed:
		latest.setdefault(entry.period, entry)
	return tuple(sorted(latest.values(), key=lambda entry: entry.period.start))


def line_rows(result: AnnualResult) -> list[dict[str, Any]]:
	"""The rows of the table Zeilen that Berechnen writes: one for every field of the form with an amount, in the
	order of the form. The amount of the form is the one the return files without a correction; that of the ledger
	is the exact amount of the accounts, in cents, the paragraph that of the accounts on the line."""
	catalogue = catalogue_for(result.year)
	rows = []
	for element, value in result.values.items():
		field = catalogue.field(element)
		rows.append(
			{
				**describe(field),
				"paragraph": ", ".join(result.paragraphs.get(field.paragraph, ())) if field.paragraph else "",
				"form_amount": value.form,
				"ledger_amount": to_cents(value.ledger + value.annual_only),
			}
		)
	return rows


def describe(field: Field) -> dict[str, Any]:
	"""What describes a line of the table Zeilen: the Feldkennung, the label of the JD, the Kennzahl, the line of the
	form, the Formatkennzeichen and the Kennzahl of the Voranmeldung whose amounts it takes."""
	return {
		"feldkennung": field.element,
		"label": field.label,
		"kennzahl": field.kennzahl or "",
		"line": field.line,
		"formatkennzeichen": field.format.value,
		"ustva": field.ustva or "",
	}


def feldkennung_of(catalogue: Catalogue, text: object) -> str:
	"""The Feldkennung a line by hand names, by itself or by the Kennzahl of its field, such as 320 for E3006201."""
	name = str(text or "").strip()
	field = catalogue.kennzahlen.get(name)
	return field.element if field is not None else name.upper()


def manual_field(catalogue: Catalogue, element: str, paragraph: object = None) -> Field:
	"""The field of a line by hand: one the ledger feeds, and a paragraph only on lines 46, 52 and 54, as
	calculation.calculate() takes it. CalculationError for any other."""
	try:
		field = catalogue.field(element)
	except KeyError:
		raise CalculationError(MANUAL_NOT_FED, element) from None
	if not field.fed:
		raise CalculationError(MANUAL_NOT_FED, element)
	if str(paragraph or "").strip() and field.paragraph is None:
		raise CalculationError(MANUAL_NO_PARAGRAPH, element)
	return field


def inputs(
	values: Mapping[str, object],
	lines: Iterable[Mapping[str, Any]] = (),
	periods: Iterable[Mapping[str, Any]] = (),
	properties: Iterable[Mapping[str, Any]] = (),
) -> tuple:
	"""What Berechnen reads from the document besides the corrections and lines by hand, which the base compares
	itself: the statements of the company and the Vorauszahlungssoll by the Finanzamt (``values``), the paragraph of
	each line by hand, the reason of each period waived and the Grundstücke of line 95. A save that changes it leaves
	a calculated return Berechnet until Berechnen checks it again."""
	return (
		tuple(sorted((name, _text(value)) for name, value in values.items())),
		tuple(
			sorted(
				(str(row.get(LINE_COLUMNS.key) or ""), _text(row.get("paragraph")))
				for row in lines
				if row.get(LINE_COLUMNS.manual)
			)
		),
		tuple(sorted(waivers_of(periods).items())),
		tuple(tuple(_cell(column, row.get(column)) for column in GRUNDSTUECK_FIELDS) for row in properties),
	)


def _cell(column: str, value: object) -> str:
	if column in GRUNDSTUECK_AMOUNTS:
		return format(to_amount(value), "f")
	return value.isoformat() if isinstance(value, date) else _text(value)


def filed_amounts(rows: Iterable[Mapping[str, Any]]) -> dict[str, Decimal]:
	"""What the lines Berechnen computed file, by Feldkennung: their correction once it has a reason, else the amount
	of the form. A line by hand files nothing of its own, since Berechnen took its amount into the line of its field."""
	return {
		str(row.get(LINE_COLUMNS.key)): reported(row, LINE_COLUMNS)
		for row in rows
		if not row.get(LINE_COLUMNS.manual)
	}


def manual_lines(rows: Iterable[Mapping[str, Any]]) -> tuple[ManualLine, ...]:
	"""The lines by hand for the computation, each with its field, amount, reason and paragraph."""
	lines = []
	for row in rows:
		if row.get(LINE_COLUMNS.manual):
			paragraph = " ".join(str(row.get("paragraph") or "").split()) or None
			lines.append(
				ManualLine(
					str(row.get(LINE_COLUMNS.key) or "").strip(),
					reported(row, LINE_COLUMNS),
					str(row.get(LINE_COLUMNS.reason) or "").strip(),
					paragraph,
				)
			)
	return tuple(lines)


def corrected(result: AnnualResult, rows: Iterable[Mapping[str, Any]]) -> dict[str, Decimal]:
	"""The amounts of the return after the corrections the document holds, as Berechnen keeps them by Feldkennung:
	what the reconciliation compares with the Voranmeldungen."""
	amounts = dict(result.reported)
	for row in rows:
		if row.get(LINE_COLUMNS.manual):
			continue
		correction = correction_of(row, LINE_COLUMNS)
		if correction is not None:
			amounts[str(row.get(LINE_COLUMNS.key))] = correction.amount
	return amounts


def soll_override(amount: object, reason: object) -> Override | None:
	"""The Vorauszahlungssoll the Finanzamt set, once it has a reason, such as its Bescheid; an amount without a reason
	is refused rather than ignored, as a correction is (steuerbote.jahresmeldung.overrides)."""
	text = " ".join(str(reason or "").split())
	value = to_amount(amount)
	if not text:
		if value:
			raise SollError(WITHOUT_REASON, SOLL_SUBJECT)
		return None
	return Override(value, text)


def vorauszahlungssoll(computed: object, override: Override | None) -> Decimal:
	"""Line 125 as the return files it: the Soll the Finanzamt set, else the one Berechnen computed."""
	return override.amount if override is not None else to_amount(computed)


def waivers_of(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
	"""The reasons the company gives for filing the return without the Voranmeldung of a period, by period code."""
	reasons = {}
	for row in rows:
		reason = " ".join(str(row.get("waiver_reason") or "").split())
		if reason and row.get("period_code"):
			reasons[str(row.get("period_code"))] = reason
	return reasons


def waived(periods: Iterable[YearPeriod], reasons: Mapping[str, str]) -> dict[Period, str]:
	"""The due periods the company waives, each with its reason."""
	return {
		entry.period: reasons[entry.period.code]
		for entry in periods
		if entry.due and entry.period.code in reasons
	}


def waivers_kept(
	stored: Iterable[Mapping[str, Any]], sent: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
	"""What a save keeps of the table Voranmeldungszeiträume: every row as Berechnen stored it, with the reason the save
	sends for the row of the same name. A row the save leaves out keeps its reason, and a row it adds is not taken, as
	the explanations of the reconciliation with the registers of the Voranmeldung (vat_return/bridge.py)."""
	sent_by_name = {row.get("name"): row for row in sent if row.get("name")}
	kept = []
	for row in stored:
		reason = row.get("waiver_reason")
		if (saved := sent_by_name.get(row.get("name"))) is not None:
			reason = saved.get("waiver_reason")
		kept.append({**row, "waiver_reason": " ".join(str(reason or "").split())})
	return kept


def period_rows(
	periods: Iterable[YearPeriod], reconciliation: Reconciliation, reasons: Mapping[str, str]
) -> list[dict[str, Any]]:
	"""The rows of the table Voranmeldungszeiträume: each period of the year, Kz 83 and Kz 39 as filed, Kz 83 on
	today's ledger, the difference with its parts and its cause, and the reason of a period waived."""
	due = {entry.period for entry in periods if entry.due}
	return [
		{
			"period_code": line.period.code,
			"period_label": line.period.label,
			"due": int(line.period in due),
			"vat_return": line.vat_return,
			"kz83": line.kz83,
			"kz39": line.kz39,
			"kz83_now": line.kz83_now,
			"difference": line.difference,
			"late": line.late,
			"corrections": line.corrections,
			"cause": CAUSES[line.cause],
			"waiver_reason": reasons.get(line.period.code, ""),
		}
		for line in reconciliation.periods
	]


def reconciliation_rows(reconciliation: Reconciliation, year: int) -> list[dict[str, Any]]:
	"""The rows of the table Abgleich je Kennzahl: each Kennzahl of the Voranmeldung with an amount, as filed, by the
	ledger then and now and in the return, with the parts of the difference, and last Kz 820 against the Kz 83 of
	the periods. Every amount in cents."""
	ustva = ustva_catalogue_for(year)
	rows = [
		{
			"kennzahl": line.kennzahl,
			"label": ustva[line.kennzahl].label,
			**_cents(
				filed=line.filed,
				filed_ledger=line.filed_ledger,
				ledger_now=line.ledger_now,
				annual=line.annual,
				late=line.late,
				corrections=line.corrections,
				unfiled=line.unfiled,
				sondervorauszahlung=ZERO,
				soll=ZERO,
				rounding=line.rounding,
				annual_only=line.annual_only,
				rest=line.rest,
			),
		}
		for line in reconciliation.kennzahlen
	]
	balance = reconciliation.balance
	kz820 = catalogue_for(year).field(KZ_820)
	rows.append(
		{
			"kennzahl": kz820.kennzahl,
			"label": kz820.label,
			**_cents(
				filed=ZERO,
				filed_ledger=ZERO,
				ledger_now=ZERO,
				annual=balance.kz820,
				late=balance.late,
				corrections=balance.corrections,
				unfiled=balance.unfiled,
				sondervorauszahlung=balance.sondervorauszahlung,
				soll=balance.soll,
				rounding=balance.rounding,
				annual_only=balance.annual_only,
				rest=balance.rest,
			),
		}
	)
	return rows


def own_findings(result: AnnualResult, split: Split, kleinunternehmer: bool = False) -> tuple[Finding, ...]:
	"""The findings of the Frappe layer on the run over the year: an error for every Verprobung that does not pass and
	every account watched at the blocking level with a balance, which hold the return as they hold a Voranmeldung, a
	hint for every account watched for a hint with a balance that no line of the return reads, and a hint in a year
	the settings mark as one of a Kleinunternehmer."""
	year = result.year
	found = [
		Finding(
			"SB-VERPROBUNG",
			Severity.ERROR,
			VERPROBUNG,
			(check.label, len(check.deviations), _euros(check.difference)),
		)
		for check in result.checks
		if not check.passed
	]
	found += [
		Finding("SB-KONTO-SPERRT", Severity.ERROR, BLOCKED, (account, year)) for account in result.unmapped
	]
	found += [
		Finding(
			"SB-KONTO-HINWEIS", Severity.HINT, WATCHED, (hinted.account_number, _euros(hinted.balance), year)
		)
		for hinted in result.hinted
		if hinted.balance and split.assignment(hinted.account_number) is None
	]
	if kleinunternehmer:
		found.append(Finding("SB-KLEINUNTERNEHMER", Severity.HINT, KLEINUNTERNEHMER, (year,)))
	return tuple(found)


def switch_findings(year: int, switch: date | None, kz136: date | None) -> tuple[Finding, ...]:
	"""A hint when Kz 136 of the return, line 18, names another day of the switch from the Kleinunternehmer-Regelung
	than Kz 70 of the filed Voranmeldungen, which names it for the Voranmeldung (USt 1 E 2026, Zeile 12)."""
	if switch is None or switch == kz136:
		return ()
	if kz136 is None:
		return (Finding("SB-KZ136", Severity.HINT, SWITCH_MISSING, (year, f"{switch:%d.%m.%Y}")),)
	values = (year, f"{switch:%d.%m.%Y}", f"{kz136:%d.%m.%Y}")
	return (Finding("SB-KZ136", Severity.HINT, SWITCH_OTHER, values),)


def findings(found: Iterable[Finding], translate: Callable[[str], str]) -> list[AnnualFinding]:
	"""The findings of the core as the table Befunde keeps them: code and severity of the rule, the message in the
	words ``translate`` gives the template, and the fields it names as the reference."""
	return [
		AnnualFinding(
			finding.code,
			AnnualSeverity.of(finding.severity),
			translate(finding.template).format(*finding.values),
			reference(finding.fields),
		)
		for finding in found
	]


def reference(fields: Iterable[str]) -> str:
	"""The fields a finding names, as many as the reference of the table Befunde holds."""
	text = ""
	for element in fields:
		candidate = f"{text}, {element}" if text else element
		if len(candidate) > DATA_LENGTH - len(MORE):
			return f"{text}{MORE}"
		text = candidate
	return text


def sums(amounts: Mapping[str, Decimal]) -> dict[str, Decimal]:
	"""The sums of the form, Kz 816, line 125 and Kz 820 as the fields of the document keep them, from the amounts of
	entries(); a sum the return does not file is zero."""
	return {fieldname: amounts.get(element, ZERO) for fieldname, element in SUM_FIELDS.items()}


def filed_values(
	year: int,
	rows: Iterable[Mapping[str, Any]],
	soll: Decimal,
	statements: Mapping[str, object] | None = None,
) -> dict[str, object]:
	"""The values the return files, by Feldkennung, as rules.check() and the XML take them: the amounts of the lines
	through entries(), the paragraph of each line of 46, 52 and 54 with an amount, and the statements of the
	company (details). CalculationError for an amount the form does not take."""
	catalogue = catalogue_for(year)
	rows = list(rows)
	amounts = entries(catalogue, filed_amounts(rows), soll)
	values: dict[str, object] = dict(amounts)
	for row in rows:
		element = str(row.get(LINE_COLUMNS.key) or "")
		paragraph = str(row.get("paragraph") or "").strip()
		if row.get(LINE_COLUMNS.manual) or not paragraph or not amounts.get(element):
			continue
		text = catalogue.field(element).paragraph
		if text is not None:
			values[text] = paragraph
	values.update(statements or {})
	return values


def details(
	year: int,
	company: Company,
	statements: Mapping[str, object],
	*,
	correction: bool = False,
	began: date | None = None,
	advisor: Advisor | None = None,
) -> dict[str, object]:
	"""The values of the return that the company states, by Feldkennung: Kz 110 of a Berichtigung (steuerbote
	.jahresmeldung.corrections), section A from the company and its Annual Filing Settings, Kz 133 for the
	Soll-Versteuerung, line 19 from the day the company began (calculation.business_period), the statements of the
	document by the fields of FLAGS and TEXTS, and lines 127 to 129 of a year a Steuerberatung takes part in. A text
	without characters is left out, as is a flag that is not set."""
	values: dict[str, object] = {}
	if corrections.marker(corrections.berichtigung_of("USt"), is_correction=correction):
		values[KZ_110] = True
	address = company.address or Address()
	texts = {
		"E3000401": company.wid_nr,
		"E3000901": company.name,
		"E3001001": company.business_purpose,
		"E3001101": address.street,
		"E3001203": address.house_number,
		"E3001204": address.house_number_suffix,
		"E3001205": address.supplement,
		"E3001206": address.postal_code if address.in_germany else None,
		"E3001207": address.city,
		"E3001202": company.phone,
		"E3001301": company.email,
	}
	values.update(_texts(texts))
	values[KZ_133] = SOLL_VERSTEUERUNG
	span = business_period(year, began) if began is not None and began.year <= year else None
	if span is not None:
		values[BUSINESS_PERIOD] = span
	for fieldname, element in FLAGS.items():
		if statements.get(fieldname):
			values[element] = True
	for fieldname, element in TEXTS.items():
		value = statements.get(fieldname)
		if isinstance(value, date):
			values[element] = value
		elif value is not None and (text := " ".join(str(value).split())):
			values[element] = text
	if advisor is not None:
		values[MITWIRKUNG] = True
		values.update(_texts({element: getattr(advisor, name) for name, element in _ADVISOR_FIELDS.items()}))
	return values


def grundstuecke(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, object], ...]:
	"""The Grundstücke of line 95, each by the Feldkennungen of the context Ang_Grdst, as the XML takes them: texts on
	one line, the day of the first use as a date, also from the text of a date field (YYYY-MM-DD), the extent and the
	amounts as Decimal; an empty value or a zero is left out, and so is a row without any value."""
	found = []
	for row in rows:
		values: dict[str, object] = {}
		for column, element in GRUNDSTUECK_FIELDS.items():
			value = row.get(column)
			if column in GRUNDSTUECK_AMOUNTS:
				amount = Decimal(str(value or ZERO))
				if amount:
					values[element] = amount
			elif column == FIRST_USE and value:
				values[element] = value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
			elif text := " ".join(str(value or "").split()):
				values[element] = text
		if values:
			found.append(values)
	return tuple(found)


def check_grundstuecke(year: int, rows: Iterable[Mapping[str, object]]) -> None:
	"""Refuse Grundstücke of line 95 that the XML would refuse: more than the 99 the context Ang_Grdst repeats (JD
	sheet "USt2A - Kontexte"), or a value its Formatkennzeichen or the „Format als regulärer Ausdruck“ of its field
	does not take. XmlError with the template of the writer."""
	rows = tuple(rows)
	if len(rows) > GRUNDSTUECKE:
		raise XmlError(ust2a_xml.TOO_MANY_GRUNDSTUECKE, GRUNDSTUECKE, len(rows))
	schema = ust2a_xml.schema_for(year)
	for row in rows:
		for element, value in row.items():
			field = schema.field(element)
			text = value_text(
				value,
				field.format,
				label=field.label,
				length=field.length,
				options=field.options,
				integer_digits=MORE_DIGITS_BEFORE_THE_COMMA.get(element, DIGITS_BEFORE_THE_COMMA),
			)
			if text is not None and field.pattern and not re.fullmatch(python_pattern(field.pattern), text):
				raise XmlError(NOT_IN_FORMAT, text, label=field.label)


def journal_entry_lines(lines: Iterable[LedgerLine]) -> tuple[tuple[LedgerLine, ...], frozenset[str]]:
	"""The ledger lines with each Journal Entry named by its name alone, and the names of the Journal Entries among
	them, for reconciliation.journal_entries(); steuerbote/ledger.py keys a voucher by its type and its name."""
	named = []
	vouchers = set()
	for line in lines:
		voucher_type, _, name = (line.voucher or "").partition(":")
		if voucher_type == JOURNAL_ENTRY and name:
			line = replace(line, voucher=name)
			vouchers.add(name)
		named.append(line)
	return tuple(named), frozenset(vouchers)


def payment_accounts(chart: str) -> tuple[str, ...]:
	"""The accounts of the payments to the Finanzamt in the chart, none for a chart of its own."""
	return PAYMENT_ACCOUNTS.get(chart, ())


def paid(lines: Iterable[LedgerLine], accounts: Collection[str]) -> Decimal | None:
	"""Debit less credit on the accounts of the payments: what the ledger shows as paid to the Finanzamt, a refund
	received less; None without such accounts."""
	if not accounts:
		return None
	return to_cents(
		sum((line.debit - line.credit for line in lines if line.account_number in accounts), ZERO)
	)


def _text(value: object) -> str:
	return " ".join(str(value if value is not None else "").split())


def _texts(values: Mapping[str, object]) -> dict[str, str]:
	return {
		element: text for element, value in values.items() if (text := " ".join(str(value or "").split()))
	}


def _cents(**amounts: Decimal) -> dict[str, Decimal]:
	return {name: to_cents(amount) for name, amount in amounts.items()}


def _euros(amount: Decimal) -> str:
	return format(to_cents(amount), "f")
