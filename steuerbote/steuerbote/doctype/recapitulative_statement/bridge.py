"""Pure Python between the Recapitulative Statement and the core in steuerbote.zm.

Nothing here imports Frappe. The module turns the voucher shares of the ledger into the voucher amounts of the
core, the core's lines, reconciliation, comparison and findings into the rows of the statement's tables, and the
rows back into the core's values: the voucher amounts and the overrides with their Begründung. So every save
rebuilds the lines with steuerbote.zm.lines.build, from the vouchers Berechnen stored, the overrides of the rows
and the latest confirmation of each USt-IdNr., which the controller reads from its records, and an override
lifts its block at once, while the controller only moves data. Every amount and every rule is the core's.

A number that was never confirmed counts as unconfirmed, as does one whose confirmation got no answer: both
hold the statement back from „Bereit“ until the BZSt confirms the number or the line is overridden with a
Begründung (decision of the maintainer, docs/zm.md, [Q16]). The core lets a number without an outcome pass, so
the statement passes an outcome for every number its lines have.

For ERiC the module hands the statement as it is filed to steuerbote.elster.zm_xml: the Unternehmer from the VAT
Return Settings and the Zusammenfassende Meldung from the lines of the statement.
"""

from collections.abc import Iterable, Sequence
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from steuerbote.elster import zm_xml
from steuerbote.steuerbote.doctype.vat_return.bridge import Row, split_voucher, to_amount
from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import ZERO
from steuerbote.zm.comparison import ComparisonRow
from steuerbote.zm.correction import correct
from steuerbote.zm.errors import ZmError
from steuerbote.zm.findings import Code, Finding, Severity
from steuerbote.zm.lines import (
	ART_ORDER,
	KENNZAHL_ART,
	NO_REASON,
	OVERRIDDEN_TWICE,
	Art,
	Line,
	Meldezeile,
	Override,
	Statement,
	Validity,
	VoucherAmount,
	build,
	line_order,
	line_vat_id,
)
from steuerbote.zm.period import Kind, ReportingPeriod
from steuerbote.zm.reconciliation import Filed, Reconciliation, Share
from steuerbote.zm.rhythm import Coverage
from steuerbote.zm.ustid import normalize

BERICHTIGUNG = "Berichtigung"

# The codes of steuerbote.zm.lines: they depend on the lines alone, so every save finds them anew.
LINE_CODES: frozenset[str] = frozenset(
	{
		Code.NO_PARTY,
		Code.NO_VAT_ID,
		Code.MALFORMED_VAT_ID,
		Code.INVALID_VAT_ID,
		Code.UNCONFIRMED_VAT_ID,
		Code.DESTINATION,
		Code.OWN_LINE,
	}
)
HINT_FIELDS = ("severity", "code", "text", "voucher_type", "voucher_no", "party")
CONFIRMATION_FIELDS = (
	"confirmation",
	"confirmation_date",
	"confirmation_service",
	"confirmation_outcome",
	"confirmation_status",
	"consultation_id",
)
# The result of a confirmation as a VAT ID Confirmation keeps it, and what it means for a line.
VALIDITY: ReadOnlyMapping[str, Validity] = MappingProxyType(
	{"valid": Validity.CONFIRMED, "invalid": Validity.INVALID}
)
TOTAL_FIELDS: ReadOnlyMapping[Art, str] = MappingProxyType(
	{Art.L: "total_l", Art.D: "total_d", Art.S: "total_s"}
)
COVERAGE_FIELDS = ("goods_from", "goods_to", "services_from", "services_to")


@dataclass(frozen=True, slots=True)
class Party:
	"""The customer a voucher names: the Customer, its name, its USt-IdNr. as ERPNext holds it and the country
	where the goods arrive, as ERPNext names it."""

	customer: str | None = None
	name: str | None = None
	vat_id: str | None = None
	destination: str | None = None


@dataclass(frozen=True, slots=True)
class FiledReturn:
	"""A filed Voranmeldung: its first and last day and the final amount of each of its Kennzahlen."""

	start: date
	end: date
	amounts: ReadOnlyMapping[str, Decimal] = field(default_factory=dict)


def reporting_period(kind: str, year: int, index: int) -> ReportingPeriod:
	"""The Meldezeitraum of a statement: its kind, its year and, but for the year, its number. ValueError for a
	kind or a number that steuerbote.zm.period does not know."""
	match Kind(kind):
		case Kind.MONTH:
			return ReportingPeriod.month(year, index)
		case Kind.TWO_MONTHS:
			return ReportingPeriod.two_months(year, index)
		case Kind.QUARTER:
			return ReportingPeriod.quarter(year, index)
	return ReportingPeriod.calendar_year(year)


def coverage_fields(covered: Coverage) -> dict[str, date | None]:
	"""The first and last day of the months whose Lieferungen and whose sonstige Leistungen a statement reports,
	as its fields keep them."""
	goods_from, goods_to = covered.goods_span
	services_from, services_to = covered.services_span or (None, None)
	return {
		"goods_from": goods_from,
		"goods_to": goods_to,
		"services_from": services_from,
		"services_to": services_to,
	}


def kept_coverage(period: ReportingPeriod, row: Row) -> Coverage | None:
	"""The months a statement of ``period`` keeps in its fields, None where it keeps none."""
	goods = _kept_months(row.get("goods_from"), row.get("goods_to"))
	if not goods:
		return None
	return Coverage(period, goods, _kept_months(row.get("services_from"), row.get("services_to")))


def overlapping(covered: Coverage, filings: Iterable[Row]) -> Row | None:
	"""The first of the filed statements that reports the Lieferungen of a month whose Lieferungen ``covered``
	reports, or the sonstige Leistungen of a month whose sonstige Leistungen it reports. A statement that keeps
	no months counts with all the months of its Meldezeitraum, for both."""
	for row in filings:
		goods, services = _kept_spans(row)
		if _overlap(covered.goods_span, goods) or _overlap(covered.services_span, services):
			return row
	return None


def _kept_months(first: object, last: object) -> tuple[int, ...]:
	start, end = _day(first), _day(last)
	return tuple(range(start.month, end.month + 1)) if start and end else ()


def _kept_spans(row: Row) -> tuple[tuple[date, date] | None, tuple[date, date] | None]:
	goods = _span_of(row.get("goods_from"), row.get("goods_to"))
	if goods is None:
		period = _span_of(row.get("from_date"), row.get("to_date"))
		return period, period
	return goods, _span_of(row.get("services_from"), row.get("services_to"))


def _span_of(first: object, last: object) -> tuple[date, date] | None:
	start, end = _day(first), _day(last)
	return (start, end) if start and end else None


def _overlap(one: tuple[date, date] | None, other: tuple[date, date] | None) -> bool:
	return one is not None and other is not None and one[0] <= other[1] and other[0] <= one[1]


def _day(value: object) -> date | None:
	"""A Date field as Frappe gives it: a date from the database, an ISO string from the form, or empty."""
	if isinstance(value, date):
		return value
	return date.fromisoformat(str(value)) if value else None


def csv_file_name(period: ReportingPeriod, correction: bool) -> str:
	"""The name of the CSV file for Mein ELSTER, such as ZM-2026-03.csv or ZM-2026-Q2-berichtigt.csv."""
	match period.kind:
		case Kind.MONTH:
			span = f"{period.year}-{period.first_month:02d}"
		case Kind.TWO_MONTHS:
			span = f"{period.year}-{period.first_month:02d}-{period.last_month:02d}"
		case Kind.QUARTER:
			span = f"{period.year}-Q{(period.first_month - 1) // 3 + 1}"
		case _:
			span = str(period.year)
	return f"ZM-{span}{'-berichtigt' if correction else ''}.csv"


def voucher_amounts_of(shares: Iterable[Share], parties: ReadOnlyMapping[str, Party]) -> list[VoucherAmount]:
	"""What each voucher adds to Kz 41, 42 and 21, with the customer it names.

	A share of 0 changes no line. A share without voucher stays out of the lines and on the side of the ledger,
	where the reconciliation names it.
	"""
	amounts = []
	for item in shares:
		if item.kennzahl not in KENNZAHL_ART or item.voucher is None or not item.amount:
			continue
		party = parties.get(item.voucher, Party())
		amounts.append(
			VoucherAmount(
				item.voucher, item.kennzahl, item.amount, party.name, party.vat_id, party.destination
			)
		)
	return amounts


def voucher_rows(
	amounts: Iterable[VoucherAmount], parties: ReadOnlyMapping[str, Party]
) -> list[dict[str, Any]]:
	rows = []
	for item in amounts:
		voucher_type, voucher_no = split_voucher(item.voucher)
		rows.append(
			{
				"voucher_type": voucher_type,
				"voucher_no": voucher_no,
				"customer": parties.get(item.voucher, Party()).customer,
				"party": item.party,
				"vat_id": item.vat_id,
				"kennzahl": item.kennzahl,
				"art": item.art.value,
				"amount": item.amount,
				"destination": item.destination,
			}
		)
	return rows


def voucher_amounts(rows: Iterable[Row]) -> list[VoucherAmount]:
	"""The voucher amounts of the rows of the vouchers' table."""
	return [
		VoucherAmount(
			f"{row.get('voucher_type')}:{row.get('voucher_no')}",
			str(row.get("kennzahl") or ""),
			to_amount(row.get("amount")),
			row.get("party") or None,
			row.get("vat_id") or None,
			row.get("destination") or None,
		)
		for row in rows
	]


def overrides_of(rows: Iterable[Row]) -> dict[tuple[str, Art], Override]:
	"""The overrides of the rows of the lines, by USt-IdNr. and Art as the lines show them.

	An override takes effect once it has a Begründung, so that 0 drops a line. An amount without one is refused
	rather than ignored, since its author expects it to count.
	"""
	overrides: dict[tuple[str, Art], Override] = {}
	for row in rows:
		reason = str(row.get("override_reason") or "").strip()
		amount = to_amount(row.get("override"))
		if not reason:
			if amount:
				raise ZmError(NO_REASON)
			continue
		art = Art(row.get("art"))
		key = (line_vat_id(row.get("vat_id"), art), art)
		if key in overrides:
			raise ZmError(OVERRIDDEN_TWICE, *key)
		overrides[key] = Override(amount, reason)
	return overrides


def line_vat_ids(
	amounts: Iterable[VoucherAmount], overrides: ReadOnlyMapping[tuple[str, Art], Override]
) -> set[str]:
	"""The USt-IdNrn. of the lines that the voucher amounts and the overrides make."""
	return {line_vat_id(item.vat_id, item.art) for item in amounts} | {vat_id for vat_id, _art in overrides}


def validity_for(
	vat_ids: Iterable[str], records: ReadOnlyMapping[str, Row], span: tuple[date, date] | None = None
) -> dict[str, Validity]:
	"""The validity of each USt-IdNr. after the result of its latest confirmation; without one, unconfirmed.

	The BZSt answers for the moment of the query. A number it finds not valid then counts as valid for the months
	of ``span`` when the answer says it was valid all through them, as evatr-2006 does with gueltigAb and
	gueltigBis („Sie war gültig im Zeitraum, der durch die Werte in den Feldern gueltigAb und gueltigBis
	beschrieben ist.“) and evatr-2002 with gueltigAb („Sie ist erst gültig ab dem Datum im Feld gueltigAb.“),
	statuses of the eVatR API.
	"""
	return {vat_id: _validity(records.get(vat_id), span) for vat_id in vat_ids if vat_id}


def _validity(record: Row | None, span: tuple[date, date] | None) -> Validity:
	validity = VALIDITY.get((record or {}).get("result") or "", Validity.UNCONFIRMED)
	if validity is Validity.INVALID and span is not None and _valid_through(record, span):
		return Validity.CONFIRMED
	return validity


def _valid_through(record: Row, span: tuple[date, date]) -> bool:
	valid_from, valid_until = _day(record.get("valid_from")), _day(record.get("valid_until"))
	if valid_from is None and valid_until is None:
		return False
	return (valid_from is None or valid_from <= span[0]) and (valid_until is None or span[1] <= valid_until)


def asked_on(records: ReadOnlyMapping[str, Row]) -> dict[str, date]:
	"""The day each USt-IdNr. was last asked about, as its latest confirmation keeps it."""
	found = {}
	for vat_id, record in records.items():
		day = confirmation_fields(record)["confirmation_date"]
		if day:
			found[vat_id] = day
	return found


def covered_span(covered: Coverage) -> tuple[date, date]:
	"""The first and the last day of the months whose lines a statement reports."""
	goods_from, goods_to = covered.goods_span
	services_from, services_to = covered.services_span or covered.goods_span
	return min(goods_from, services_from), max(goods_to, services_to)


def statement_of(voucher_rows: Iterable[Row], line_rows: Sequence[Row], figures: Figures) -> Statement:
	"""The lines of the statement as its rows hold them: the vouchers, the overrides and the confirmations."""
	amounts = voucher_amounts(voucher_rows)
	overrides = overrides_of(line_rows)
	records = {str(row.get("vat_id") or ""): {"result": row.get("confirmation_outcome")} for row in line_rows}
	return build(amounts, figures, validity_for(line_vat_ids(amounts, overrides), records), overrides)


def confirmation_fields(record: Row) -> dict[str, Any]:
	"""The latest VAT ID Confirmation of a number as the lines of the number show it."""
	requested_at = record.get("requested_at")
	return {
		"confirmation": record.get("name"),
		"confirmation_date": requested_at.date() if isinstance(requested_at, datetime) else requested_at,
		"confirmation_service": record.get("service"),
		"confirmation_outcome": record.get("result"),
		"confirmation_status": record.get("status_code"),
		"consultation_id": record.get("consultation_id"),
	}


def line_rows(
	statement: Statement,
	confirmations: ReadOnlyMapping[str, ReadOnlyMapping[str, Any]],
	period: ReportingPeriod,
	held: ReadOnlyMapping[tuple[str, Art], Decimal] | None = None,
) -> list[dict[str, Any]]:
	"""A row per line, in the order of the lines, with the latest confirmation of its USt-IdNr.

	Each row says whether the file for Mein ELSTER reports it: an Erstmeldung its Meldezeilen. ``held`` is what
	the BZSt holds for the Meldezeitraum, for a Berichtigung (steuerbote.zm.correction.as_filed): each row then
	shows what was filed for it, the file reports the lines that change it, and a line filed before that has no
	vouchers and no override any more gets a row of its own, which the Berichtigung cancels with 0.
	"""
	rows = {line.key: _line_row(line) for line in statement.lines}
	in_file = {line.key for line in file_lines(statement, period, held)[0]}
	if held is not None:
		for key, amount in held.items():
			if amount and key not in rows:
				rows[key] = _line_row(Line(*key))
	for key, row in rows.items():
		row.update(
			{
				"filed_amount": (held or {}).get(key, ZERO),
				"in_file": int(key in in_file),
				**dict.fromkeys(CONFIRMATION_FIELDS),
				**confirmations.get(key[0], {}),
			}
		)
	return [rows[key] for key in sorted(rows, key=line_order)]


def _line_row(line: Line) -> dict[str, Any]:
	party = next((name.strip() for item in line.vouchers if (name := item.party or "").strip()), "")
	return {
		"vat_id": line.vat_id,
		"art": line.art.value,
		"party": party,
		"amount": line.amount,
		"override": line.override.amount if line.override else ZERO,
		"override_reason": line.override.reason if line.override else "",
		"reported": line.reported,
		"blocked": int(line.blocked),
		"manual": int(line.manual),
	}


def hint_rows(findings: Iterable[Finding]) -> list[dict[str, Any]]:
	rows = []
	for finding in findings:
		voucher_type, voucher_no = split_voucher(finding.voucher)
		rows.append(
			{
				"severity": finding.severity.value,
				"code": finding.code.value,
				"text": finding.text,
				"voucher_type": voucher_type,
				"voucher_no": voucher_no,
				"party": finding.party,
			}
		)
	return rows


def merged_hints(statement: Statement, rows: Iterable[Row]) -> list[dict[str, Any]]:
	"""The findings of the lines anew, then the stored findings of the threshold, the reconciliation and the
	comparison, which only Berechnen changes."""
	kept = [
		{name: row.get(name) for name in HINT_FIELDS} for row in rows if row.get("code") not in LINE_CODES
	]
	return [*hint_rows(statement.findings), *kept]


def ready(statement: Statement, hints: Iterable[Row]) -> bool:
	"""No line holds the statement back, and no error that an override cannot lift: the threshold and the
	reconciliation with the ledger."""
	return statement.ready and not any(
		row.get("severity") == Severity.ERROR.value and row.get("code") not in LINE_CODES for row in hints
	)


def totals(meldezeilen: Iterable[Meldezeile]) -> dict[str, Decimal]:
	sums = dict.fromkeys(ART_ORDER, ZERO)
	for meldezeile in meldezeilen:
		sums[meldezeile.art] += meldezeile.amount
	return {TOTAL_FIELDS[art]: amount for art, amount in sums.items()}


def reconciliation_rows(reconciliation: Reconciliation) -> list[dict[str, Any]]:
	"""A row per Art. A Currency field stores no blank, so a Kennzahl without filed Voranmeldungen holds 0 and
	says that it is not known."""
	return [
		{
			"art": row.art.value,
			"kennzahl": row.kennzahl,
			"ledger": row.ledger,
			"statement": row.statement,
			"difference": row.difference,
			"reported": row.reported,
			"filed": ZERO if row.filed is None else row.filed,
			"filed_known": int(row.filed is not None),
			"deviating_vouchers": len(row.differences),
			"balanced": int(not row.differences),
			"manual": row.manual,
		}
		for row in reconciliation.rows
	]


def comparison_rows(rows: Iterable[ComparisonRow]) -> list[dict[str, Any]]:
	"""A row per line of either period; without a previous amount the share of the difference holds 0."""
	return [
		{
			"vat_id": row.vat_id,
			"art": row.art.value,
			"current": row.current,
			"previous": row.previous,
			"difference": row.difference,
			"difference_percent": ZERO if row.difference_percent is None else row.difference_percent,
			"flagged": int(row.flagged),
		}
		for row in rows
	]


def filed(
	returns: Iterable[FiledReturn], span: tuple[date, date] | None, kennzahlen: Iterable[str]
) -> dict[str, Filed]:
	"""The Kennzahlen of the filed Voranmeldungen whose periods make up the months of the span, each month once.

	Voranmeldungen that leave a month out, or cover one twice, compare with nothing, so they give nothing.
	"""
	if span is None:
		return {}
	inside = [item for item in returns if span[0] <= item.start and item.end <= span[1]]
	months = sorted(month for item in inside for month in _months(item.start, item.end))
	if months != _months(*span):
		return {}
	return {
		number: Filed(sum((item.amounts.get(number, ZERO) for item in inside), ZERO), len(inside))
		for number in kennzahlen
	}


def _months(start: date, end: date) -> list[tuple[int, int]]:
	return [
		(index // 12, index % 12 + 1)
		for index in range(start.year * 12 + start.month - 1, end.year * 12 + end.month)
	]


def filed_meldezeilen(rows: Iterable[Row]) -> list[Meldezeile]:
	"""What a filed statement reported: the lines of its file."""
	return [
		Meldezeile(str(row.get("vat_id") or ""), Art(row.get("art")), to_amount(row.get("reported")))
		for row in rows
		if int(row.get("in_file") or 0)
	]


def file_lines(
	statement: Statement, period: ReportingPeriod, held: ReadOnlyMapping[tuple[str, Art], Decimal] | None
) -> tuple[tuple[Meldezeile, ...], bool]:
	"""The Meldezeilen of the file and whether it is a Berichtigung: the lines that change what the BZSt holds,
	when ``held`` gives it."""
	if held is None:
		return statement.meldezeilen, False
	return correct(period, held, statement.meldezeilen).lines, True


def unternehmer(settings: Row, country: str | None) -> zm_xml.Unternehmer:
	"""The company as the Zusammenfassende Meldung names it, from its VAT Return Settings: its own USt-IdNr., the
	name and address of the Datenlieferant, without a name of its own that of the company, its phone and its
	Teilnehmernummer, if it has one; ``country`` is the code of the country of the company.

	The settings hold street and house number in one field, which goes into strasse; the rules require the street
	and leave the house number to the filer (Jahresdokumentation ZMDO 2, 170025002).
	"""
	return zm_xml.Unternehmer(
		ust_idnr=settings.get("ust_idnr") or "",
		name=settings.get("filer_name") or settings.get("company"),
		street=settings.get("street"),
		postal_code=settings.get("postal_code") or None,
		city=settings.get("city"),
		country=country,
		phone=settings.get("phone") or None,
		teilnehmernummer=settings.get("teilnehmernummer") or None,
	)


def zm(
	period: ReportingPeriod,
	statement: Statement,
	held: ReadOnlyMapping[tuple[str, Art], Decimal] | None,
	anzeige: object,
	widerruf: object,
) -> zm_xml.Zm:
	"""The Zusammenfassende Meldung for ERiC: the Meldezeilen of the statement, for a Berichtigung with what the BZSt
	holds for the Meldezeitraum (``held``, see line_rows), and the Anzeige and its Widerruf of its check fields."""
	return zm_xml.Zm(
		period, statement.meldezeilen, filed=held, anzeige=_checked(anzeige), widerruf=_checked(widerruf)
	)


def _checked(value: object) -> bool:
	"""The value of a check field; Frappe hands out 0 and 1, as numbers or text."""
	return bool(int(value or 0))


def numbers_to_confirm(rows: Iterable[Row]) -> list[str]:
	"""The USt-IdNrn. of the lines the statement reports, each once."""
	return sorted(
		{
			vat_id
			for row in rows
			if (vat_id := str(row.get("vat_id") or ""))
			and reportable(vat_id, Art(row.get("art")))
			and to_amount(row.get("reported"))
		}
	)


def customer_of(voucher_rows: Iterable[Row], vat_id: str) -> str | None:
	"""The Customer of the first voucher of the lines of a USt-IdNr. that names one."""
	for row in voucher_rows:
		art = KENNZAHL_ART[str(row.get("kennzahl"))]
		if row.get("customer") and line_vat_id(row.get("vat_id"), art) == vat_id:
			return row.get("customer")
	return None


def reportable(vat_id: str, art: Art) -> bool:
	"""The ZM can report a line of ``art`` under ``vat_id`` as it stands."""
	return normalize(vat_id, services=art is Art.S) == vat_id
