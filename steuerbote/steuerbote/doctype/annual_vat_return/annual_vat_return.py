"""Annual VAT Return: the Umsatzsteuererklärung of one company for one year, form USt 2 A (§ 18 Absatz 3 UStG).

The document lives on the base of the annual documents (steuerbote/steuerbote/annual_filing.py, docs/jahresmeldungen.md):
its status, Berechnen with the corrections and lines by hand, the findings, the filing, the Berichtigung and the
transmission through ERiC are those of AnnualFiling and Transmittable. This controller gives it the Umsatzsteuer:

- Berechnen (compute) reads the ledger of the year and the VAT Return Mapping with its lines of the annual return,
  the filed Voranmeldungen, the Sondervorauszahlung and the payments (steuerbote/ustjahr_sources.py), and runs the
  core in steuerbote/ustjahr: calculation.calculate() for the lines, soll.vorauszahlungssoll() for line 125,
  reconciliation.reconcile() against the Voranmeldungen and their runs on today's ledger, journal_entries() for the
  hints on Journal Entries, and, on the lines as filed, rules.check() (check_reported). bridge.py moves the results
  into the lines and tables of the document.
- Berechnen sets the sales of the return against the Umsatzerlöse of the festgestellter Jahresabschluss of the year,
  else of its filed E-Bilanz (revenue.py), with the threshold in euros of the Vorperiodenvergleich of the VAT Return
  Settings as the tolerance: a difference beyond it is a hint, never an error.
- „Bereit“ follows from the findings and the checks of the core together: the Verprobung passes and no account
  watched at the blocking level has a balance (AnnualResult.ready), every Voranmeldungszeitraum is filed or waived with
  a reason (Soll.ready), the reconciliation leaves no rest (Reconciliation.ready), and no rule of the Jahresdokumentation
  that Steuerbote checks finds an error, the paragraphs of lines 46, 52 and 54 included.
- A save takes the corrections and lines by hand, the Vorauszahlungssoll by the Finanzamt with its reason, the
  reasons for periods without a Voranmeldung, the statements of the company and the Grundstücke of line 95, and sets
  the sums of the form, Kz 816, line 125 and Kz 820 from the lines as filed (set_amounts). A change of anything
  Berechnen reads leaves a calculated return Berechnet until Berechnen checks it again.
- The deadline is the day Offene Fristen lists for the Umsatzsteuererklärung of the year (annual_deadline in
  steuerbote/steuerbote/deadlines.py): § 149 Absatz 2 to 4 AO with the Steuerberatung and the Vorabanforderung of the
  Annual Filing Settings. The Abschlusszahlung is due one month after the return arrived (§ 18 Absatz 4 Satz 1 UStG,
  soll.payment_due), which the filing sets.
- Prüfen, Testsenden and Senden go through ERiC in the Datenart USt of the year (datenart.ust) with the Nutzdaten E50
  of steuerbote/elster/ust2a_xml.py, in the simulation until the Hersteller-ID exists. Mein ELSTER imports no
  Umsatzsteuererklärung: it is typed in there from the print format „Umsatzsteuererklärung“, and the filing is noted
  with „In Mein ELSTER abgegeben“.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate

from steuerbote import prior_filings, ustjahr_sources
from steuerbote.dauerfrist_sources import date_of_establishment
from steuerbote.deadlines import Kind
from steuerbote.elster import ust2a_xml
from steuerbote.eric import datenart as eric_datenart
from steuerbote.holiday_list import holidays
from steuerbote.jahresmeldung import findings as annual_findings
from steuerbote.jahresmeldung.findings import Finding, Severity
from steuerbote.jahresmeldung.lifecycle import Event
from steuerbote.jahresmeldung.overrides import to_amount
from steuerbote.ledger import account_names, closing_balances
from steuerbote.setup import start
from steuerbote.steuerbote.annual_filing import FINDINGS_TABLE, RECALCULATE, AnnualFiling, Calculation
from steuerbote.steuerbote.deadlines import annual_deadline
from steuerbote.steuerbote.doctype.annual_filing_settings.annual_filing_settings import settings_of
from steuerbote.steuerbote.doctype.annual_vat_return import bridge, layout, revenue
from steuerbote.steuerbote.doctype.elster_transmission.transmission import Transmittable
from steuerbote.steuerbote.doctype.vat_return import bridge as vat_return_bridge
from steuerbote.steuerbote.doctype.vat_return.vat_return import settings_for, statutory_tax_of
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import xml_errors
from steuerbote.steuerbote.report.ustva_kennzahlen.comparison import Thresholds
from steuerbote.suppliers import load_vouchers
from steuerbote.ustjahr import calculation, form, reconciliation, rules, soll, split
from steuerbote.ustva import carried
from steuerbote.ustva.defaults import TIMING_ACCOUNTS
from steuerbote.ustva.years import UnknownYearError

DOCTYPE = "Annual VAT Return"
PERIODS = "periods"
PROPERTIES = "properties"
# What Berechnen reads from the document besides its lines, by the fields of the document.
INPUT_FIELDS = (*bridge.STATEMENT_FIELDS, "soll_override", "soll_override_reason")


class AnnualVATReturn(AnnualFiling, Transmittable, Document):
	LINES = "lines"
	LINE_COLUMNS = bridge.LINE_COLUMNS
	CALCULATED_TABLES = ("reconciliation", "checks", "deviations", "unmapped")
	CALCULATED_FIELDS = (
		"soll_voranmeldungen",
		"soll_credited",
		"sondervorauszahlung",
		"soll_computed",
		"payment_due",
	)

	# The hooks of the base.

	def compute(self) -> Calculation:
		"""Berechnen: the lines, the Vorauszahlungssoll and the reconciliation of the year from the sources."""
		year = self._year()
		settings = settings_for(self.company)
		tolerance = to_amount(settings.tolerance)
		statutory_tax = statutory_tax_of(settings)
		stored = self._rows(self.LINES)
		with core_errors():
			annual_split = ustjahr_sources.annual_split(self.company, year)
			mapping = annual_split.mapping
			lines = ustjahr_sources.year_lines(self.company, year)
			manual = self._lines(bridge.manual_lines, stored)
			vouchers = load_vouchers(self.company, lines, mapping)
			result = calculation.calculate(lines, annual_split, manual, tolerance, vouchers, statutory_tax)
			result, released = _released(self.company, result, lines, mapping, year)
			periods = bridge.year_periods(
				settings.get_period_rules(), year, date_of_establishment(self.company)
			)
			filed = ustjahr_sources.filed_voranmeldungen(self.company, year)
			runs = ustjahr_sources.period_runs(
				self.company, bridge.periods_to_run(periods, filed), mapping, tolerance, statutory_tax
			)
			reasons = bridge.waivers_of(self._rows(PERIODS))
			previous = self._previous_kz816()
			accounts = tuple(account_names(self.company, bridge.payment_accounts(mapping.chart)))
			payments = ustjahr_sources.payment_lines(self.company, year, accounts)
			paid_before = start.prior_payments(
				payments, prior_filings.prior_filings(self.company, {year - 1})
			)
			payments = bridge.without_prior_payments(payments, paid_before)
			found_soll = soll.vorauszahlungssoll(
				year,
				filed,
				bridge.due_periods(periods),
				ustjahr_sources.sondervorauszahlung(settings, year),
				bridge.waived(periods, reasons),
				previous,
				bridge.soll_override(self.soll_override, self.soll_override_reason),
				bridge.paid(payments, accounts),
			)
			found = reconciliation.reconcile(
				result, found_soll, runs, self._lines(bridge.corrected, result, stored)
			)
			named, vouchers = bridge.journal_entry_lines(lines)
			journal_entries = reconciliation.journal_entries(year, named, mapping, vouchers)
		year_settings = self._year_settings()
		kleinunternehmer = bool(year_settings and year_settings.kleinunternehmer)
		values: dict[str, Any] = {
			"soll_voranmeldungen": found_soll.voranmeldungen,
			"soll_credited": found_soll.credited,
			"sondervorauszahlung": found_soll.sondervorauszahlung,
			"soll_computed": previous if previous is not None else found_soll.computed,
		}
		unmapped = replace(result.ustva, unmapped=result.unmapped)
		return Calculation(
			lines=bridge.line_rows(result),
			tables={
				PERIODS: bridge.period_rows(periods, found, reasons),
				"reconciliation": bridge.reconciliation_rows(found, year),
				"checks": vat_return_bridge.check_rows(result.ustva),
				"deviations": vat_return_bridge.deviation_rows(result.ustva),
				"unmapped": vat_return_bridge.unmapped_rows(
					unmapped, lines, account_names(self.company, result.unmapped)
				),
			},
			values=values,
			findings=bridge.findings(
				(
					*bridge.start_findings(year, prior_filings.books_start(self.company)),
					*bridge.own_findings(result, annual_split, kleinunternehmer),
					*bridge.release_findings(released, year),
					*bridge.prior_payment_findings(paid_before, year),
					*result.findings,
					*found_soll.findings,
					*found.findings,
					*journal_entries,
					*bridge.switch_findings(
						year,
						ustjahr_sources.switch_to_regelbesteuerung(self.company, year),
						getdate(self.kz136) if self.kz136 else None,
					),
				),
				_,
			),
			passed=result.ready and found_soll.ready and found.ready,
		)

	def check_reported(self, lines) -> list[Finding]:
		"""The checks of Steuerbote and the rules of the Jahresdokumentation that it checks itself, on the values the
		return files with the lines as Berechnen keeps them, and the hint where its sales are not the Umsatzerlöse of
		the year."""
		year = self._year()
		settings = settings_for(self.company)
		with core_errors():
			found = rules.check(year, self._filed_values(lines), getdate())
			hint = revenue.findings(
				form.catalogue_for(year),
				bridge.filed_amounts(lines),
				ustjahr_sources.annual_revenue(self.company, year),
				Thresholds.of(None, settings.get("comparison_threshold_amount")).amount,
			)
		return bridge.findings((*found, *hint), _)

	def compute_deadline(self) -> date | None:
		"""The day the return is due, as Offene Fristen lists it: seven months after the year, the last day of February of
		the second year after it with a Steuerberatung, or the earliest day of a Vorabanforderung of the year, moved off
		a Saturday, a Sunday or a holiday of the company; none without Annual Filing Settings, before their first year or
		in a year of a Kleinunternehmer, who owes no return (§ 19 Absatz 1 Satz 2 UStG)."""
		return annual_deadline(self.company, Kind.UMSATZSTEUERERKLAERUNG, cint(self.year))

	def set_amounts(self) -> None:
		"""The sums of the form, Kz 816, line 125 and Kz 820, from the lines as filed."""
		self.update(self._amounts())

	def amounts_kept(self, stored: Document) -> bool:
		return all(
			to_amount(stored.get(fieldname)) == amount for fieldname, amount in self._amounts().items()
		)

	def correction_values(self) -> dict[str, Any]:
		"""A Berichtigung starts with the statements of the company, the Bescheiddaten, the Grundstücke of line 95 and the
		reasons for the periods without a Voranmeldung; its Vorauszahlungssoll is the Kz 816 of this return."""
		return {
			**{fieldname: self.get(fieldname) for fieldname in bridge.STATEMENT_FIELDS},
			"bescheid": self.bescheid,
			PROPERTIES: [
				{column: row.get(column) for column in bridge.GRUNDSTUECK_FIELDS} for row in self.properties
			],
			PERIODS: [
				{"period_code": row.period_code, "waiver_reason": row.waiver_reason}
				for row in self.periods
				if row.waiver_reason
			],
		}

	def bescheiddaten(self) -> bool:
		"""Whether the Vorsatz asks for the Bescheiddaten for electronic retrieval, Bescheid 1, as the return says."""
		return bool(cint(self.bescheid))

	# Transmittable.

	def datenart(self) -> eric_datenart.Datenart:
		"""The Datenart USt of the year of the return."""
		return eric_datenart.ust(cint(self.year))

	def nutzdaten(self, hersteller_id: str) -> str:
		"""The Nutzdaten E50 of the return as saved, with its Grundstücke and the Vorsatz; the Erklärung carries no
		Hersteller-ID of its own."""
		year = self._year()
		with core_errors(), xml_errors(_("ELSTER Transmission")):
			values = self._filed_values(self._rows(self.LINES))
			return ust2a_xml.to_nutzdaten(year, values, self.vorsatz(), self._grundstuecke())

	# Frappe.

	def before_insert(self) -> None:
		"""A new return keeps of its periods only the reasons why it is filed without their Voranmeldung."""
		reasons = bridge.waivers_of(self._rows(PERIODS))
		super().before_insert()
		self.set(
			PERIODS, [{"period_code": code, "waiver_reason": reason} for code, reason in reasons.items()]
		)

	def validate(self) -> None:
		before = self.get_doc_before_save()
		if not (self.company and self.year):
			super().validate()
			return
		catalogue = self._catalogue()
		self._keep_the_periods(before)
		self._name_the_lines_by_hand(before, catalogue)
		super().validate()
		self._describe_the_lines_by_hand(catalogue)
		self._check_the_grundstuecke()
		self._require_berechnen_after_a_change(before)

	def before_submit(self) -> None:
		"""Filing sets the day the Abschlusszahlung is due: one month after the return arrived, which for a filing
		through ERiC is the day of the acceptance and else the day noted (§ 18 Absatz 4 Satz 1 UStG); a refund has
		none."""
		super().before_submit()
		due = None
		if to_amount(self.kz820) > 0 and self.filed_on:
			due = soll.payment_due(getdate(self.filed_on), holidays(self.company))
		self.payment_due = due

	# What the print format reads.

	def annual_vat_print(self) -> dict[str, Any]:
		"""The sections of form USt 2 A with the values the return files and its Grundstücke, for the print format
		„Umsatzsteuererklärung“ (layout.print_sections)."""
		year = self._year()
		with core_errors():
			values = self._filed_values(self._rows(self.LINES))
		return {"sections": layout.print_sections(year, values, self._grundstuecke())}

	# The rules of a save.

	def _keep_the_periods(self, before: Document | None) -> None:
		"""A save keeps the table Voranmeldungszeiträume as Berechnen stored it and takes the reasons alone."""
		if before is None or self.flags.calculating:
			return
		self.set(PERIODS, bridge.waivers_kept(self._rows(PERIODS, before), self._rows(PERIODS)))

	def _name_the_lines_by_hand(self, before: Document | None, catalogue: form.Catalogue) -> None:
		"""A line by hand names its field by the Feldkennung or by its Kennzahl, such as 320; it keeps the Feldkennung."""
		stored = {row.name: cint(row.manual) for row in (before.get(self.LINES) if before else ())}
		for row in self.get(self.LINES):
			if stored.get(row.name, 1):
				row.feldkennung = bridge.feldkennung_of(catalogue, row.feldkennung)

	def _describe_the_lines_by_hand(self, catalogue: form.Catalogue) -> None:
		"""A line by hand takes the description of its field, which has to be one the ledger feeds."""
		for row in self.get(self.LINES):
			if cint(row.manual):
				with core_errors():
					field = bridge.manual_field(catalogue, row.feldkennung, row.paragraph)
				row.update(
					{key: value for key, value in bridge.describe(field).items() if key != "feldkennung"}
				)

	def _check_the_grundstuecke(self) -> None:
		"""Line 95 lists the Grundstücke of Kz 370, at most 99, each with values the XML takes."""
		if self.get(PROPERTIES) and not cint(self.kz370):
			frappe.throw(
				_(
					"Line 95 lists the Grundstücke first used in the year once Kz 370 says so: tick Kz 370 or remove the Grundstücke."
				)
			)
		with xml_errors(_("Annual VAT Return")):
			bridge.check_grundstuecke(self._year(), self._grundstuecke())

	def _require_berechnen_after_a_change(self, before: Document | None) -> None:
		"""A calculated return whose statements, Vorauszahlungssoll by the Finanzamt, reasons for periods or
		Grundstücke changed is Berechnet again, with a finding that asks for Berechnen."""
		if before is None or self.flags.calculating or self.status not in self.LIFECYCLE.calculated:
			return
		if _inputs(before) == _inputs(self):
			return
		self.status = self.LIFECYCLE.move(self.status, Event.CHANGE)
		self.ready = 0
		stored = annual_findings.of_rows(self._rows(FINDINGS_TABLE))
		if any(finding.code == RECALCULATE for finding in stored):
			return
		recalculate = Finding(
			RECALCULATE,
			Severity.ERROR,
			_(
				"An entry that Berechnen reads changed since Berechnen: a statement, the Vorauszahlungssoll by the Finanzamt, a reason for a period without a Voranmeldung or a Grundstück. Calculate again, so that Berechnen checks the return with it."
			),
		)
		self.add_finding(recalculate)

	# Helpers.

	def _year(self) -> int:
		year = cint(self.year)
		self._catalogue()
		return year

	def _catalogue(self) -> form.Catalogue:
		"""The form USt 2 A of the year of the return, with the schema of its XML."""
		try:
			catalogue = form.catalogue_for(cint(self.year))
			ust2a_xml.schema_for(cint(self.year))
		except UnknownYearError, ust2a_xml.XmlError:
			frappe.throw(_("Steuerbote has no form USt 2 A for {0} yet.").format(cint(self.year)))
		return catalogue

	def _amounts(self) -> dict[str, Decimal]:
		year = self._year()
		with core_errors():
			amounts = calculation.entries(
				form.catalogue_for(year), bridge.filed_amounts(self._rows(self.LINES)), self._soll()
			)
		return bridge.sums(amounts)

	def _soll(self) -> Decimal:
		"""Line 125 as the return files it: the Soll by the Finanzamt once it has a reason, else the one Berechnen
		computed."""
		with core_errors():
			override = bridge.soll_override(self.soll_override, self.soll_override_reason)
		return bridge.vorauszahlungssoll(self.soll_computed, override)

	def _filed_values(self, rows) -> dict[str, object]:
		year = self._year()
		statements = {fieldname: self.get(fieldname) for fieldname in bridge.STATEMENT_FIELDS}
		statements["kz136"] = getdate(self.kz136) if self.kz136 else None
		details = bridge.details(
			year,
			ustjahr_sources.company(self.company),
			statements,
			correction=bool(cint(self.is_correction)),
			began=date_of_establishment(self.company),
			advisor=ustjahr_sources.advisor(self.company, year),
		)
		with core_errors():
			return bridge.filed_values(year, rows, self._soll(), details)

	def _grundstuecke(self) -> tuple[dict[str, object], ...]:
		if not cint(self.kz370):
			return ()
		return bridge.grundstuecke(self._rows(PROPERTIES))

	def _previous_kz816(self) -> Decimal | None:
		"""The Kz 816 of the return a Berichtigung corrects, its Vorauszahlungssoll (soll.vorauszahlungssoll)."""
		if not cint(self.is_correction) or not self.corrects:
			return None
		return to_amount(frappe.db.get_value(DOCTYPE, self.corrects, "kz816"))

	def _year_settings(self):
		settings = settings_of(self.company)
		return settings.year_settings(cint(self.year)) if settings else None

	def _rows(self, table: str, doc: Document | None = None) -> list[dict[str, Any]]:
		return [row.as_dict() for row in (doc or self).get(table) or ()]


@contextmanager
def core_errors() -> Iterator[None]:
	"""Show what the core of the Umsatzsteuererklärung refuses as a message in the language of the user."""
	try:
		yield
	except (
		calculation.CalculationError,
		soll.SollError,
		reconciliation.ReconciliationError,
		split.SplitError,
	) as error:
		frappe.throw(_(error.template).format(*error.values), title=_("Annual VAT Return"))


def _inputs(doc: Document) -> tuple:
	"""What Berechnen reads of the document besides its lines, comparable between two states of it."""
	values = {fieldname: _input(doc, fieldname) for fieldname in INPUT_FIELDS}
	rows = {
		table: [row.as_dict() for row in doc.get(table) or ()] for table in (doc.LINES, PERIODS, PROPERTIES)
	}
	return bridge.inputs(values, rows[doc.LINES], rows[PERIODS], rows[PROPERTIES])


def _input(doc: Document, fieldname: str) -> str:
	value = doc.get(fieldname)
	fieldtype = doc.meta.get_field(fieldname).fieldtype
	if fieldtype in ("Check", "Int"):
		return str(cint(value))
	if fieldtype in ("Currency", "Float"):
		return format(to_amount(value), "f")
	if fieldtype == "Date":
		return getdate(value).isoformat() if value else ""
	return " ".join(str(value or "").split())


def _released(
	company: str, result: calculation.AnnualResult, lines: list, mapping, year: int
) -> tuple[calculation.AnnualResult, tuple[carried.Release, ...]]:
	"""The result without the block of a watched timing account whose movement over the year releases the balance it
	carried into the year, such as the opening balance of input tax deductible in January (steuerbote/ustva/carried.py)."""
	timing = TIMING_ACCOUNTS.get(mapping.chart, ())
	candidates = [account for account in result.unmapped if account in timing]
	if not candidates:
		return result, ()
	balances = carried.carried_balances(closing_balances(company, date(year, 12, 31), candidates), lines)
	found = carried.releases(result.unmapped, lines, balances, timing)
	return replace(result, unmapped=carried.still_blocked(result.unmapped, found)), found
